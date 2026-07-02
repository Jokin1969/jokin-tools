const path = require('path');

// All imprimir settings come from env, read lazily so Railway picks up changes
// after a redeploy without code edits.
function bool(v, def = false) {
  if (v === undefined || v === '') return def;
  return /^(1|true|yes|on)$/i.test(String(v).trim());
}

function list(v) {
  return String(v || '')
    .split(/[,;\s]+/)
    .map(s => s.trim().toLowerCase())
    .filter(Boolean);
}

function config() {
  const dataDir = path.dirname(process.env.DB_PATH || '/data/jokin_tools.db');
  return {
    enabled: bool(process.env.IMPRIMIR_ENABLED, false),
    imap: {
      host: process.env.IMPRIMIR_IMAP_HOST || 'imap.gmail.com',
      port: Number(process.env.IMPRIMIR_IMAP_PORT) || 993,
      secure: bool(process.env.IMPRIMIR_IMAP_SECURE, true),
      user: process.env.IMPRIMIR_IMAP_USER || '',
      pass: process.env.IMPRIMIR_IMAP_PASS || '',
      mailbox: process.env.IMPRIMIR_IMAP_MAILBOX || 'INBOX',
    },
    // Senders allowed to print. Empty list + allowAll=false ⇒ nothing prints.
    allowlist: list(process.env.IMPRIMIR_ALLOWLIST),
    allowAll: bool(process.env.IMPRIMIR_ALLOW_ALL, false),
    defaultPrinter: process.env.IMPRIMIR_DEFAULT_PRINTER || '',
    agentKey: process.env.IMPRIMIR_AGENT_KEY || '',
    storageDir: process.env.IMPRIMIR_DIR || path.join(dataDir, 'imprimir'),
    maxBytes: (Number(process.env.IMPRIMIR_MAX_MB) || 25) * 1024 * 1024,
    pollCron: process.env.IMPRIMIR_POLL_CRON || '* * * * *',   // every minute
    retentionDays: Number(process.env.IMPRIMIR_RETENTION_DAYS) || 14,
    notifyReceived: bool(process.env.IMPRIMIR_NOTIFY_RECEIVED, true),
    notifySenderNoPdf: bool(process.env.IMPRIMIR_NOTIFY_NO_PDF, true),
  };
}

// Is the email address allowed to submit print jobs?
function isAllowed(cfg, address) {
  const addr = String(address || '').trim().toLowerCase();
  if (!addr) return false;
  if (cfg.allowAll) return true;
  return cfg.allowlist.includes(addr);
}

// A view of the config safe to show on the status page: emails/hosts/printer are
// visible; secrets (passwords, agent key) become booleans only.
function maskedConfig() {
  const c = config();
  return {
    enabled: c.enabled,
    imap: { host: c.imap.host, port: c.imap.port, secure: c.imap.secure, user: c.imap.user, mailbox: c.imap.mailbox, hasPass: !!c.imap.pass },
    allowlist: c.allowlist,
    allowAll: c.allowAll,
    defaultPrinter: c.defaultPrinter,
    hasAgentKey: !!c.agentKey,
    smtp: {
      host: process.env.SMTP_HOST || 'smtp.gmail.com',
      user: process.env.SMTP_USER || '',
      from: process.env.EMAIL_FROM || process.env.SMTP_USER || '',
      hasPass: !!process.env.SMTP_PASS,
    },
    storageDir: c.storageDir,
    pollCron: c.pollCron,
    retentionDays: c.retentionDays,
    maxMB: Math.round(c.maxBytes / 1024 / 1024),
    notifyReceived: c.notifyReceived,
    notifySenderNoPdf: c.notifySenderNoPdf,
  };
}

// Turn the masked config + live diagnostics into a human checklist so the status
// page can say, at a glance, what's ready and what's blocking printing. Pure.
function readiness(mc, diag = {}) {
  const items = [];
  const add = (ok, label, detail, failLevel = 'error') => items.push({ ok, label, detail, level: ok ? 'ok' : failLevel });

  add(mc.enabled, 'Servicio activado',
    mc.enabled ? 'IMPRIMIR_ENABLED=true' : 'Está desactivado. Pon IMPRIMIR_ENABLED=true y redespliega.');
  add(!!(mc.imap.user && mc.imap.hasPass), 'Credenciales del buzón (IMAP)',
    (mc.imap.user && mc.imap.hasPass) ? `${mc.imap.user} · ${mc.imap.host}:${mc.imap.port}` : 'Faltan IMPRIMIR_IMAP_USER / IMPRIMIR_IMAP_PASS (contraseña de aplicación).');
  add(mc.allowAll || (mc.allowlist && mc.allowlist.length > 0), 'Remitentes autorizados',
    mc.allowAll ? 'Cualquiera (IMPRIMIR_ALLOW_ALL=true)' : (mc.allowlist.length ? mc.allowlist.join(', ') : 'Lista vacía: NADIE puede imprimir. Define IMPRIMIR_ALLOWLIST.'));
  add(!!mc.hasAgentKey, 'Clave del agente (API key)',
    mc.hasAgentKey ? 'Configurada' : 'Falta IMPRIMIR_AGENT_KEY; el agente no podrá autenticarse.');
  add(!!mc.defaultPrinter, 'Impresora por defecto',
    mc.defaultPrinter || 'Sin definir (el agente usará la de su config.json).', 'warn');
  add(!!(mc.smtp.user && mc.smtp.hasPass), 'SMTP para avisos por email',
    (mc.smtp.user && mc.smtp.hasPass) ? `${mc.smtp.from}` : 'Sin SMTP: no se enviarán acuses de recibo ni confirmaciones.', 'warn');

  const polled = !!diag.lastPollAt;
  add(polled && diag.lastPollOk === true, 'Último sondeo del buzón',
    !polled ? 'Aún no se ha sondeado el buzón (¿servicio desactivado o recién arrancado?).'
      : (diag.lastPollOk ? `Correcto · ${diag.lastPollAt}` : `Falló: ${diag.lastPollError}`),
    polled && diag.lastPollOk === false ? 'error' : 'warn');
  add(!!diag.lastAgentPullAt, 'Agente de impresión visto',
    diag.lastAgentPullAt ? `Última consulta del agente: ${diag.lastAgentPullAt}`
      : 'El agente aún no ha contactado. ¿Está arrancado en el PC de la impresora, con la URL del servidor y la misma API key?', 'warn');

  return items;
}

module.exports = { config, isAllowed, bool, list, maskedConfig, readiness };
