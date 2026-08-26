'use strict';

// ── Pastillero database (SEPARATE, self-contained) ───────────────────────────────
// Reads people (qr-tis) and the medication plan + dose schedule (asignacion) from
// their own databases, in-process, like Asignación already does with qr-tis and
// datamatrix. This DB only stores what's specific to Pastillero:
//
//   residencia          — one row per "residencia" (a QR-TIS group used as such),
//                         with the access code the caregivers use to log in.
//   pastillero_session  — the code-login session (own cookie, own store; NOT the
//                         farmacia `users` system — caregivers have no account).
//
// Schema left deliberately narrow for Fase 1 (shared code per residencia). Adding
// named accounts later (residencia_user) is additive, no rework needed here.

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const DB_PATH = process.env.PASTILLERO_DB_PATH || '/data/pastillero.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS residencia (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name  TEXT NOT NULL UNIQUE,     -- matches a QR-TIS group ("residencia")
    access_code TEXT UNIQUE,              -- shared login code for that residencia's staff
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS pastillero_session (
    sid           TEXT PRIMARY KEY,
    residencia_id INTEGER NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at    DATETIME NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_pastillero_session_res ON pastillero_session(residencia_id);
`);

// ── Residencias (access codes) ────────────────────────────────────────────────────
function listResidencias() {
  return db.prepare('SELECT * FROM residencia ORDER BY group_name COLLATE NOCASE').all();
}
function getResidenciaByGroup(groupName) {
  return db.prepare('SELECT * FROM residencia WHERE group_name = ?').get(groupName) || null;
}
function getResidenciaByCode(code) {
  if (!code) return null;
  return db.prepare('SELECT * FROM residencia WHERE access_code = ? AND active = 1').get(String(code)) || null;
}
// Easy-to-type code: uppercase letters/digits, excluding look-alikes (0/O, 1/I/L).
const CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
function generateCode(len = 6) {
  let out = '';
  for (let i = 0; i < len; i++) out += CODE_ALPHABET[crypto.randomInt(CODE_ALPHABET.length)];
  return out;
}
// Create the residencia row if it doesn't exist yet, and (re)generate its code.
// Retries on the rare collision with another residencia's code.
function rotateCode(groupName) {
  let code;
  for (let attempt = 0; attempt < 5; attempt++) {
    code = generateCode();
    if (!db.prepare('SELECT 1 FROM residencia WHERE access_code = ?').get(code)) break;
  }
  db.prepare(
    `INSERT INTO residencia (group_name, access_code, active, updated_at) VALUES (@group_name, @code, 1, CURRENT_TIMESTAMP)
     ON CONFLICT(group_name) DO UPDATE SET access_code = excluded.access_code, active = 1, updated_at = CURRENT_TIMESTAMP`
  ).run({ group_name: groupName, code });
  return getResidenciaByGroup(groupName);
}
function setResidenciaActive(groupName, active) {
  db.prepare(
    `INSERT INTO residencia (group_name, active, updated_at) VALUES (@group_name, @active, CURRENT_TIMESTAMP)
     ON CONFLICT(group_name) DO UPDATE SET active = excluded.active, updated_at = CURRENT_TIMESTAMP`
  ).run({ group_name: groupName, active: active ? 1 : 0 });
  return getResidenciaByGroup(groupName);
}

// ── Sessions (code login) ──────────────────────────────────────────────────────────
const SESSION_DAYS = parseInt(process.env.PASTILLERO_SESSION_DAYS) || 30;
function createSession(residenciaId) {
  const sid = crypto.randomBytes(32).toString('hex');
  const expires = new Date(Date.now() + SESSION_DAYS * 24 * 60 * 60 * 1000).toISOString();
  db.prepare('INSERT INTO pastillero_session (sid, residencia_id, expires_at) VALUES (?, ?, ?)').run(sid, residenciaId, expires);
  return { sid, maxAgeMs: SESSION_DAYS * 24 * 60 * 60 * 1000 };
}
function getSessionResidencia(sid) {
  if (!sid) return null;
  const row = db.prepare('SELECT * FROM pastillero_session WHERE sid = ?').get(sid);
  if (!row) return null;
  if (new Date(row.expires_at).getTime() < Date.now()) { db.prepare('DELETE FROM pastillero_session WHERE sid = ?').run(sid); return null; }
  const res = db.prepare('SELECT * FROM residencia WHERE id = ? AND active = 1').get(row.residencia_id);
  if (!res) { db.prepare('DELETE FROM pastillero_session WHERE sid = ?').run(sid); return null; }
  return res;
}
function deleteSession(sid) { db.prepare('DELETE FROM pastillero_session WHERE sid = ?').run(sid); }
function purgeExpiredSessions() { db.prepare("DELETE FROM pastillero_session WHERE expires_at < datetime('now')").run(); }
setInterval(purgeExpiredSessions, 60 * 60 * 1000).unref?.();

module.exports = {
  db,
  listResidencias, getResidenciaByGroup, getResidenciaByCode, rotateCode, setResidenciaActive,
  createSession, getSessionResidencia, deleteSession,
};
