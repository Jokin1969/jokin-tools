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

module.exports = { config, isAllowed, bool, list };
