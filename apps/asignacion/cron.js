'use strict';

// ── Asignación — notification scheduler ──────────────────────────────────────────
// Every minute (Europe/Madrid), send the scheduled notifications whose time has
// arrived today and that haven't been sent yet today.

const cron = require('node-cron');
const db = require('./db');
const email = require('./email');

let task = null;
let warnedNoSmtp = false;
const TZ = process.env.ASIG_TZ || 'Europe/Madrid';

// Current date/time/weekday in the configured timezone.
function madridNow() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(new Date());
  const g = t => (parts.find(p => p.type === t) || {}).value;
  const date = `${g('year')}-${g('month')}-${g('day')}`;
  let hh = g('hour'); if (hh === '24') hh = '00';
  const time = `${hh}:${g('minute')}`;
  const wd = new Date(date + 'T00:00:00Z').getUTCDay(); // 0=Sun..6=Sat, from the calendar date
  return { date, time, wd };
}

async function tick() {
  if (!email.smtpConfigured()) {
    if (!warnedNoSmtp) { console.warn('[asignacion] cron: SMTP no configurado; las notificaciones no se enviarán hasta definir SMTP_USER/SMTP_PASS.'); warnedNoSmtp = true; }
    return;
  }
  const { date, time, wd } = madridNow();
  let due;
  try { due = db.dueNotifs(date, time, wd); } catch (e) { console.error('[asignacion] cron dueNotifs:', e.message); return; }
  for (const n of due) {
    try {
      const r = await email.sendNotif(n, date);
      db.markNotifSent(n.id, date);
      console.log(`[asignacion] notif #${n.id} → ${r.sent ? `enviada a ${r.recipients.join(', ')} (${r.count} persona/s)` : 'omitida (0 personas)'}`);
    } catch (e) {
      console.error(`[asignacion] notif #${n.id} error:`, e.message); // not marked → reintentar
    }
  }
}

function startCron() {
  if (task) return { stop: stopCron };
  task = cron.schedule('* * * * *', tick, { timezone: TZ });
  console.log(`[asignacion] Notification cron started (cada minuto, ${TZ}).`);
  return { stop: stopCron };
}
function stopCron() { if (task) { try { task.stop(); } catch { /* ignore */ } task = null; } }

module.exports = { startCron, stopCron, tick, madridNow };
