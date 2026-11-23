const cron = require('node-cron');
const { getMemoriesDueToday, markSent, createQuiz, getOrCreateQuizSettings, logCronRun } = require('./db');
const email = require('./email');
const { createBackup, hasDbChangedSinceLastBackup } = require('./backup');
const quizAi = require('./quiz-ai');

// Guard against being started twice (e.g. a stray require) and expose the
// scheduled tasks so the server can stop them on shutdown.
let tasks = null;

function maxPerRunFromEnv() {
  return Math.max(1, parseInt(process.env.REMEMORY_MAX_PER_RUN || '2', 10));
}

// Cuestionario si el usuario los tiene activos; si cualquier paso del cuestionario
// falla (base de datos, IA, lo que sea), el recordatorio normal. El cuestionario es
// un extra: nunca puede impedir que el recordatorio salga.
async function sendOne(memory, deps) {
  let quizError = null;
  try {
    const settings = getOrCreateQuizSettings(memory.user_id);
    if (settings.enabled) {
      const quiz = createQuiz(memory.id, memory.user_id);
      await deps.generateQuizQuestions(
        quiz.id, memory.description, memory.topic, settings.difficulty_level, settings.questions_per_quiz
      );
      await deps.sendQuizEmail(memory, memory.owner_email, quiz.token);
      return { type: 'quiz' };
    }
  } catch (err) {
    quizError = err.message;
    console.error(`[cron] Cuestionario fallido para la ficha #${memory.id}, se envía el recordatorio normal:`, err.message);
  }
  await deps.sendMemoryEmail(memory, memory.owner_email);
  return quizError ? { type: 'email', quiz_error: quizError } : { type: 'email' };
}

// The send job itself. The schedule and the debug panel's "run now" button both call
// THIS, so the button exercises exactly what the schedule does. `deps` is for tests.
async function runSendJob({ maxPerRun = maxPerRunFromEnv(), trigger = 'cron', deps = {} } = {}) {
  const d = {
    sendMemoryEmail: email.sendMemoryEmail,
    sendQuizEmail: email.sendQuizEmail,
    generateQuizQuestions: quizAi.generateQuizQuestions,
    ...deps,
  };
  const due = getMemoriesDueToday()
    .sort((a, b) => String(a.next_send_date).localeCompare(String(b.next_send_date)));
  const batch = due.slice(0, maxPerRun);
  console.log(`[cron] ${trigger}: ${due.length} pendiente(s) · enviando ${batch.length} (máx ${maxPerRun})`);

  const details = [];
  for (const memory of batch) {
    const entry = { id: memory.id, topic: memory.topic, to: memory.owner_email };
    try {
      Object.assign(entry, await sendOne(memory, d));
      markSent(memory.id, memory.frequency);
      entry.ok = true;
      console.log(`[cron] ✓ Ficha #${memory.id} enviada (${entry.type}) a ${memory.owner_email}`);
    } catch (err) {
      entry.ok = false;
      entry.error = err.message;
      console.error(`[cron] ✗ Ficha #${memory.id} NO enviada:`, err.message);
    }
    details.push(entry);
  }

  const summary = {
    trigger,
    due: due.length,
    sent: details.filter(x => x.ok).length,
    failed: details.filter(x => !x.ok).length,
    details,
  };
  try { logCronRun(summary); } catch (err) { console.error('[cron] No se pudo registrar la ejecución:', err.message); }
  return summary;
}

function startCron() {
  if (tasks) return { stop: stopCron };
  tasks = [];
  // Run at several times of day and send only a few per run, so a morning batch
  // of due reminders trickles out across the day instead of arriving all at once.
  const sendCron = process.env.REMEMORY_SEND_CRON || '50 6,10,14,18 * * *';
  const maxPerRun = maxPerRunFromEnv();

  tasks.push(cron.schedule(sendCron, async () => {
    try {
      await runSendJob({ maxPerRun, trigger: 'cron' });
    } catch (err) {
      console.error('[cron] Fatal error in send job:', err);
      try { logCronRun({ trigger: 'cron', due: 0, sent: 0, failed: 0, details: [{ ok: false, error: `Fallo general: ${err.message}` }] }); } catch { /* ignore */ }
    }
  }, { timezone: 'Europe/Madrid' }));

  console.log(`[cron] Re-memory send job scheduled (${sendCron} Europe/Madrid, ≤${maxPerRun}/run)`);

  // ─── Automatic backup job ─────────────────────────────────────────────────
  // Interval controlled by BACKUP_INTERVAL_HOURS (default: 2)
  const intervalHours = Math.max(1, parseInt(process.env.BACKUP_INTERVAL_HOURS || '2', 10));
  const backupCronExpr = `0 */${intervalHours} * * *`;

  tasks.push(cron.schedule(backupCronExpr, async () => {
    if (!hasDbChangedSinceLastBackup()) {
      console.log('[backup-cron] No changes since last backup, skipping');
      return;
    }
    console.log('[backup-cron] Changes detected, creating automatic backup…');
    try {
      const result = await createBackup();
      console.log(`[backup-cron] ✓ Done: ${result.filename}`);
    } catch (err) {
      console.error('[backup-cron] ✗ Failed:', err.message);
    }
  }, { timezone: 'Europe/Madrid' }));

  console.log(`[cron] Backup job scheduled (every ${intervalHours}h, only on changes)`);
  return { stop: stopCron };
}

// Stop all scheduled tasks (used during graceful shutdown).
function stopCron() {
  if (!tasks) return;
  for (const t of tasks) {
    try { t.stop(); } catch { /* ignore */ }
  }
  tasks = null;
}

module.exports = { startCron, stopCron, runSendJob };
