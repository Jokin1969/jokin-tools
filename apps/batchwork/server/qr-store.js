'use strict';

// ── QR repository (persistent) ──────────────────────────────────────────────────
// Saved QR codes live in the shared SQLite file on the /data volume, so they
// survive server redeploys exactly like Bitácora / Re-memory. Each row keeps the
// full generation config (style, colours, ECC, logo dataURL, frame…) so a saved
// code can be recovered and re-edited, plus a small SVG thumbnail for the list.
// Scoped per user.

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.DB_PATH || '/data/jokin_tools.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS qr_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,
    config      TEXT NOT NULL,                     -- JSON: full generation config
    thumb       TEXT,                              -- small SVG markup for the list
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE INDEX IF NOT EXISTS idx_qr_user ON qr_codes(user_id);
`);

console.log('[batchwork/qr] Repository ready at:', DB_PATH);

// A "systematic" fallback name when the user leaves the name field empty.
function systematicName(userId) {
  const d = new Date();
  const stamp = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  const where = userId != null ? 'WHERE user_id = ?' : '';
  const args = userId != null ? [userId] : [];
  const total = db.prepare(`SELECT COUNT(*) AS n FROM qr_codes ${where}`).get(...args).n;
  return `QR-${stamp}-${String(total + 1).padStart(3, '0')}`;
}

function list(userId) {
  const where = userId != null ? 'WHERE user_id = ?' : '';
  const args = userId != null ? [userId] : [];
  return db.prepare(
    `SELECT id, name, url, thumb, created_at FROM qr_codes ${where} ORDER BY created_at DESC, id DESC`
  ).all(...args);
}

function get(id, userId) {
  const row = userId != null
    ? db.prepare('SELECT * FROM qr_codes WHERE id = ? AND user_id = ?').get(id, userId)
    : db.prepare('SELECT * FROM qr_codes WHERE id = ?').get(id);
  if (!row) return null;
  let config = {};
  try { config = JSON.parse(row.config); } catch { /* corrupt row → empty config */ }
  return { id: row.id, name: row.name, url: row.url, config, thumb: row.thumb, created_at: row.created_at };
}

function create({ name, url, config, thumb }, userId = null) {
  const finalName = (name && String(name).trim()) ? String(name).trim().slice(0, 120) : systematicName(userId);
  const info = db.prepare(
    `INSERT INTO qr_codes (user_id, name, url, config, thumb) VALUES (@user_id, @name, @url, @config, @thumb)`
  ).run({
    user_id: userId,
    name: finalName,
    url: String(url),
    config: JSON.stringify(config || {}),
    thumb: thumb ? String(thumb).slice(0, 200000) : null,
  });
  return get(info.lastInsertRowid, userId);
}

function remove(id, userId) {
  const where = userId != null ? 'id = ? AND user_id = ?' : 'id = ?';
  const args = userId != null ? [id, userId] : [id];
  return db.prepare(`DELETE FROM qr_codes WHERE ${where}`).run(...args).changes > 0;
}

module.exports = { db, list, get, create, remove, systematicName };
