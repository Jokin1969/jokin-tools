'use strict';

// ── Stamp repository (persistent) ────────────────────────────────────────────────
// Saved stamps live in the shared SQLite file on the /data volume, surviving
// redeploys like the QR repository. Each row keeps the full generation config so a
// saved stamp can be recovered and re-edited, plus a small SVG thumbnail and a
// subtitle for the list. Scoped per user. Mirrors qr-store.

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.DB_PATH || '/data/jokin_tools.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS stamps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    name        TEXT NOT NULL,
    subtitle    TEXT,
    config      TEXT NOT NULL,                     -- JSON: full generation config
    thumb       TEXT,                              -- small SVG markup for the list
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE INDEX IF NOT EXISTS idx_stamps_user ON stamps(user_id);
`);

console.log('[batchwork/stamp] Repository ready at:', DB_PATH);

function systematicName(userId) {
  const d = new Date();
  const stamp = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  const where = userId != null ? 'WHERE user_id = ?' : '';
  const args = userId != null ? [userId] : [];
  const total = db.prepare(`SELECT COUNT(*) AS n FROM stamps ${where}`).get(...args).n;
  return `Sello-${stamp}-${String(total + 1).padStart(3, '0')}`;
}

function list(userId) {
  const where = userId != null ? 'WHERE user_id = ?' : '';
  const args = userId != null ? [userId] : [];
  return db.prepare(
    `SELECT id, name, subtitle, thumb, created_at FROM stamps ${where} ORDER BY created_at DESC, id DESC`
  ).all(...args);
}

function get(id, userId) {
  const row = userId != null
    ? db.prepare('SELECT * FROM stamps WHERE id = ? AND user_id = ?').get(id, userId)
    : db.prepare('SELECT * FROM stamps WHERE id = ?').get(id);
  if (!row) return null;
  let config = {};
  try { config = JSON.parse(row.config); } catch { /* corrupt row → empty config */ }
  return { id: row.id, name: row.name, subtitle: row.subtitle, config, thumb: row.thumb, created_at: row.created_at };
}

function create({ name, subtitle, config, thumb }, userId = null) {
  const finalName = (name && String(name).trim()) ? String(name).trim().slice(0, 120) : systematicName(userId);
  const info = db.prepare(
    `INSERT INTO stamps (user_id, name, subtitle, config, thumb) VALUES (@user_id, @name, @subtitle, @config, @thumb)`
  ).run({
    user_id: userId,
    name: finalName,
    subtitle: subtitle ? String(subtitle).slice(0, 160) : null,
    config: JSON.stringify(config || {}),
    thumb: thumb ? String(thumb).slice(0, 200000) : null,
  });
  return get(info.lastInsertRowid, userId);
}

function remove(id, userId) {
  const where = userId != null ? 'id = ? AND user_id = ?' : 'id = ?';
  const args = userId != null ? [id, userId] : [id];
  return db.prepare(`DELETE FROM stamps WHERE ${where}`).run(...args).changes > 0;
}

module.exports = { db, list, get, create, remove, systematicName };
