const cron = require('node-cron');
const { getMemoriesDueToday, markSent } = require('./db');
const { sendMemoryEmail } = require('./email');
const { createBackup, hasDbChangedSinceLastBackup } = require('./backup');

// ─── Daily email job: 06:50 Madrid time ──────────────────────────────────────

// Guard against being started twice (e.g. a stray require) and expose the
// scheduled tasks so the server can stop them on shutdown.
let tasks = null;

function startCron() {
  if (tasks) return { stop: stopCron };
  tasks = [];
  // Run at several times of day and send only a few per run, so a morning batch
  // of due reminders trickles out across the day instead of arriving all at once.
  const sendCron = process.env.REMEMORY_SEND_CRON || '50 6,10,14,18 * * *';
  const maxPerRun = Math.max(1, parseInt(process.env.REMEMORY_MAX_PER_RUN || '2', 10));

  tasks.push(cron.schedule(sendCron, async () => {
    console.log('[cron] Running Re-memory send job…');
    try {
      const due = getMemoriesDueToday()
        .sort((a, b) => String(a.next_send_date).localeCompare(String(b.next_send_date)));
      const batch = due.slice(0, maxPerRun);
      console.log(`[cron] ${due.length} due · sending ${batch.length} (máx ${maxPerRun}/run)`);

      for (const memory of batch) {
        try {
          // Each memory is emailed to its own owner.
          await sendMemoryEmail(memory, memory.owner_email);
          markSent(memory.id, memory.frequency);
          console.log(`[cron] ✓ Memory #${memory.id} sent to ${memory.owner_email} and updated`);
        } catch (err) {
          console.error(`[cron] ✗ Failed to send memory #${memory.id}:`, err.message);
        }
      }
      if (due.length > batch.length) {
        console.log(`[cron] ${due.length - batch.length} pendiente(s) para el siguiente turno (reparte los emails).`);
      }
    } catch (err) {
      console.error('[cron] Fatal error in send job:', err);
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

module.exports = { startCron, stopCron };
