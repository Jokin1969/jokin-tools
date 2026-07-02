const cron = require('node-cron');
const { simpleParser } = require('mailparser');
const { config } = require('./config');
const { classifyMessage, persistEnqueue } = require('./ingest');
const { pollMailbox } = require('./imap');
const db = require('./db');
const mailer = require('./mailer');

let tasks = null;
let running = false;
let warnedNoCreds = false;

// Handle one raw email. Returns true when the message is definitively handled
// (so it can be flagged \Seen); false on a transient error worth retrying.
async function handleSource(source, cfg) {
  const parsed = await simpleParser(source);
  const result = classifyMessage(parsed, cfg);

  if (result.action === 'reject') {
    console.log('[imprimir] Ignorado (remitente no autorizado):', result.sender || '(sin remitente)');
    return true; // don't reply — avoids email backscatter to spoofed senders
  }

  if (result.action === 'no_pdf') {
    console.log('[imprimir] Correo sin PDF de', result.sender);
    if (cfg.notifySenderNoPdf) {
      try { await mailer.sendNoPdf(result.sender, result.subject, result.oversized); }
      catch (e) { console.error('[imprimir] No se pudo avisar (sin PDF):', e.message); }
    }
    return true;
  }

  // enqueue — persistEnqueue may throw on disk errors; let it propagate so the
  // message stays unseen and is retried (enqueue is idempotent).
  const created = persistEnqueue(result, cfg, db);
  console.log(`[imprimir] Encolado(s) ${created.length} trabajo(s) de ${result.sender} (${result.subject || 'sin asunto'})`);
  return true;
}

async function runIngestOnce() {
  const cfg = config();
  if (!cfg.enabled) return;
  if (!cfg.imap.user || !cfg.imap.pass) {
    if (!warnedNoCreds) {
      console.warn('[imprimir] IMPRIMIR_ENABLED=true pero faltan IMPRIMIR_IMAP_USER/PASS — el poll está inactivo.');
      warnedNoCreds = true;
    }
    return;
  }
  if (running) { console.log('[imprimir] Poll anterior aún en curso — se omite este ciclo.'); return; }
  running = true;
  try {
    // Rescue jobs left 'printing' by an agent that died mid-print (>10 min old).
    const requeued = db.requeueStale(3, 10);
    if (requeued) console.log(`[imprimir] ${requeued} trabajo(s) colgado(s) devueltos a la cola.`);

    const res = await pollMailbox(cfg, (src) => handleSource(src, cfg));
    if (res.processed) console.log(`[imprimir] Poll: ${res.processed} mensaje(s) nuevos, ${res.marked} procesado(s).`);
  } catch (e) {
    console.error('[imprimir] Poll falló:', e.message);
  } finally {
    running = false;
  }
}

function startPolling() {
  const cfg = config();
  if (!cfg.enabled) {
    console.log('[imprimir] Deshabilitado (IMPRIMIR_ENABLED no está activo).');
    return { stop: stopPolling };
  }
  if (tasks) return { stop: stopPolling };
  tasks = [];

  tasks.push(cron.schedule(cfg.pollCron, runIngestOnce));
  console.log(`[imprimir] Poll de correo programado (${cfg.pollCron}).`);

  // Daily cleanup of old stored PDFs / finished jobs.
  tasks.push(cron.schedule('30 3 * * *', () => {
    try {
      const n = db.purgeOld(config().retentionDays);
      if (n) console.log(`[imprimir] Limpieza: ${n} trabajo(s) antiguos eliminados.`);
    } catch (e) { console.error('[imprimir] Limpieza falló:', e.message); }
  }, { timezone: 'Europe/Madrid' }));

  return { stop: stopPolling };
}

function stopPolling() {
  if (!tasks) return;
  for (const t of tasks) { try { t.stop(); } catch { /* ignore */ } }
  tasks = null;
}

module.exports = { startPolling, stopPolling, runIngestOnce, handleSource };
