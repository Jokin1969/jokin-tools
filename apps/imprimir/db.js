const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

// Shares the same SQLite file as the rest of the hub (one backup captures all).
const DB_PATH = process.env.DB_PATH || '/data/jokin_tools.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// ─── Schema ───────────────────────────────────────────────────────────────────
// Email-to-print queue: an email arriving at the print mailbox with a PDF
// attachment becomes one queued job per PDF. A local agent (next to the printer)
// pulls queued jobs, prints them and reports back. message_id makes ingestion
// idempotent so the same email is never enqueued twice.
db.exec(`
  CREATE TABLE IF NOT EXISTS print_jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id   TEXT,                       -- email Message-ID (dedupe)
    part_idx     INTEGER NOT NULL DEFAULT 0, -- attachment index within the email
    sender       TEXT,                       -- envelope/from address (allowlisted)
    subject      TEXT,
    filename     TEXT NOT NULL,
    mime         TEXT,
    printer      TEXT,                       -- target printer name
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    file_path    TEXT NOT NULL,              -- stored PDF on the server volume
    status       TEXT NOT NULL DEFAULT 'queued'
                   CHECK(status IN ('queued','printing','done','failed')),
    error        TEXT,
    attempts     INTEGER NOT NULL DEFAULT 0,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    printed_at   DATETIME,
    UNIQUE(message_id, part_idx)
  );
  CREATE INDEX IF NOT EXISTS idx_print_jobs_status ON print_jobs(status, id);

  CREATE TABLE IF NOT EXISTS imprimir_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
  );
`);

console.log('[imprimir] Table ready at:', DB_PATH);

// ─── Settings (persisted, "until changed") ──────────────────────────────────────
function getSetting(key) {
  const row = db.prepare('SELECT value FROM imprimir_settings WHERE key = ?').get(key);
  return row ? row.value : null;
}
function setSetting(key, value) {
  db.prepare('INSERT INTO imprimir_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value')
    .run(key, value == null ? null : String(value));
}

// Default printer chosen in the panel (persists until changed). Falls back to
// the env default elsewhere when this is null.
function getDefaultPrinter() {
  const v = getSetting('default_printer');
  return v && v.trim() ? v.trim() : null;
}
function setDefaultPrinter(name) {
  setSetting('default_printer', name == null ? '' : String(name).trim());
  return getDefaultPrinter();
}

// Printers reported by the local agent (name + when last seen), so the panel and
// other apps can offer a real selector.
function getKnownPrinters() {
  try { return JSON.parse(getSetting('known_printers') || '[]'); } catch { return []; }
}
function reportPrinters(names, nowIso) {
  const clean = [...new Set((names || []).map(n => String(n).trim()).filter(Boolean))];
  const prev = new Map(getKnownPrinters().map(p => [p.name, p]));
  const merged = clean.map(name => ({ name, lastSeen: nowIso || (prev.get(name) && prev.get(name).lastSeen) || null }));
  // keep previously-known printers not in this report (agent might list a subset)
  for (const p of getKnownPrinters()) if (!clean.includes(p.name)) merged.push(p);
  setSetting('known_printers', JSON.stringify(merged));
  return merged;
}

// ─── Queue operations ───────────────────────────────────────────────────────────

// True if this (message_id, part) pair was already enqueued — cheap dedupe guard
// used before writing the PDF to disk.
function jobExists(messageId, partIdx) {
  if (!messageId) return false;
  return !!db.prepare('SELECT 1 FROM print_jobs WHERE message_id = ? AND part_idx = ?').get(messageId, partIdx);
}

function enqueueJob(job) {
  const stmt = db.prepare(`
    INSERT INTO print_jobs (message_id, part_idx, sender, subject, filename, mime, printer, size_bytes, file_path)
    VALUES (@message_id, @part_idx, @sender, @subject, @filename, @mime, @printer, @size_bytes, @file_path)
  `);
  const info = stmt.run({
    message_id: job.message_id || null,
    part_idx: job.part_idx || 0,
    sender: job.sender || null,
    subject: job.subject || null,
    filename: job.filename,
    mime: job.mime || 'application/pdf',
    printer: job.printer || null,
    size_bytes: job.size_bytes || 0,
    file_path: job.file_path,
  });
  return getJob(info.lastInsertRowid);
}

function getJob(id) {
  return db.prepare('SELECT * FROM print_jobs WHERE id = ?').get(id);
}

// Atomically hand the oldest queued job to the agent: flip it to 'printing' and
// return it. A transaction prevents two pulls grabbing the same job.
const claimTxn = db.transaction(() => {
  const row = db.prepare("SELECT * FROM print_jobs WHERE status = 'queued' ORDER BY id ASC LIMIT 1").get();
  if (!row) return null;
  db.prepare("UPDATE print_jobs SET status = 'printing', attempts = attempts + 1 WHERE id = ?").run(row.id);
  return getJob(row.id);
});
function claimNextJob() {
  return claimTxn();
}

function markDone(id) {
  return db.prepare("UPDATE print_jobs SET status = 'done', printed_at = CURRENT_TIMESTAMP, error = NULL WHERE id = ?").run(id).changes > 0;
}

function markFailed(id, error) {
  return db.prepare("UPDATE print_jobs SET status = 'failed', error = ? WHERE id = ?").run(String(error || '').slice(0, 500), id).changes > 0;
}

// Put a finished job back in the queue for a fresh print (used by the status
// page's "reprint" action). Resets the error and attempt counter.
function requeueJob(id) {
  return db.prepare(
    "UPDATE print_jobs SET status = 'queued', error = NULL, printed_at = NULL, attempts = 0 WHERE id = ?"
  ).run(id).changes > 0;
}

// Return a 'printing' job to the queue (e.g. agent died mid-print, or a stale
// reclaim). Kept simple: only re-queue, never beyond a max attempts count.
function requeueStale(maxAttempts, olderThanMinutes) {
  return db.prepare(`
    UPDATE print_jobs SET status = 'queued'
     WHERE status = 'printing'
       AND attempts < ?
       AND (strftime('%s','now') - strftime('%s', created_at)) > ?
  `).run(maxAttempts, olderThanMinutes * 60).changes;
}

// Delete a single job (and its stored PDF). Used by the per-row trash button.
function deleteJob(id) {
  const job = getJob(id);
  if (!job) return false;
  try { if (job.file_path && fs.existsSync(job.file_path)) fs.unlinkSync(job.file_path); } catch { /* ignore */ }
  return db.prepare('DELETE FROM print_jobs WHERE id = ?').run(id).changes > 0;
}

// Remove all finished (done) jobs and their files. Returns how many were cleared.
function clearDone() {
  const rows = db.prepare("SELECT id, file_path FROM print_jobs WHERE status = 'done'").all();
  const del = db.prepare('DELETE FROM print_jobs WHERE id = ?');
  let n = 0;
  for (const r of rows) {
    try { if (r.file_path && fs.existsSync(r.file_path)) fs.unlinkSync(r.file_path); } catch { /* ignore */ }
    del.run(r.id); n++;
  }
  return n;
}

function listJobs({ status, limit = 100 } = {}) {
  const lim = Math.min(Math.max(Number(limit) || 100, 1), 500);
  if (status) return db.prepare('SELECT * FROM print_jobs WHERE status = ? ORDER BY id DESC LIMIT ?').all(status, lim);
  return db.prepare('SELECT * FROM print_jobs ORDER BY id DESC LIMIT ?').all(lim);
}

function counts() {
  const rows = db.prepare('SELECT status, COUNT(*) AS n FROM print_jobs GROUP BY status').all();
  const out = { queued: 0, printing: 0, done: 0, failed: 0 };
  for (const r of rows) out[r.status] = r.n;
  return out;
}

// Delete done/failed jobs (and their files) older than N days, to keep the
// volume tidy. Returns the number of rows removed.
function purgeOld(days) {
  const rows = db.prepare(`
    SELECT id, file_path FROM print_jobs
     WHERE status IN ('done','failed')
       AND (strftime('%s','now') - strftime('%s', created_at)) > ?
  `).all(days * 86400);
  const del = db.prepare('DELETE FROM print_jobs WHERE id = ?');
  let n = 0;
  for (const r of rows) {
    try { if (r.file_path && fs.existsSync(r.file_path)) fs.unlinkSync(r.file_path); } catch { /* ignore */ }
    del.run(r.id); n++;
  }
  return n;
}

module.exports = {
  db,
  jobExists, enqueueJob, getJob, claimNextJob,
  markDone, markFailed, requeueJob, requeueStale, listJobs, counts, purgeOld,
  deleteJob, clearDone,
  getSetting, setSetting, getDefaultPrinter, setDefaultPrinter, getKnownPrinters, reportPrinters,
};
