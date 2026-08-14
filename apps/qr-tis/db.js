'use strict';

// ── Gestión de QR (TIS) database (SEPARATE, self-contained) ─────────────────────
// People and their 7-digit TIS code (the number used for medication management).
// The TIS is stored as TEXT so leading zeros are preserved and "count". Everything
// lives in its own SQLite file (qr_tis.db) so the app stays portable.
//
//   tis_people   — the shared directory of people (name, surname, TIS, group,
//                  active flag). Shared across everyone with access to the app.
//   tis_settings — a single global row of QR display settings (size, colour,
//                  style…). "Persist until another person changes them" → global.
//   tis_cart     — per-user cart (each user has their own).

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.QR_TIS_DB_PATH || '/data/qr_tis.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS tis_people (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pharmacy_no TEXT,                    -- 5 digits assigned by the pharmacy (leading zeros preserved)
    nombre      TEXT NOT NULL,
    apellidos   TEXT NOT NULL,
    tis         TEXT NOT NULL,           -- 8 digits, leading zeros preserved
    group_name  TEXT,                    -- optional group membership
    qr_dark     TEXT,                    -- per-person QR colour (null = global default)
    qr_light    TEXT,                    -- per-person QR background (null = global default)
    qr_style    TEXT,                    -- per-person QR style 'square'|'dots' (null = global)
    active     INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME DEFAULT CURRENT_TIMESTAMP   -- bumped on create/edit/view ("handled")
  );
  CREATE INDEX IF NOT EXISTS idx_tis_people_active ON tis_people(active);

  CREATE TABLE IF NOT EXISTS tis_settings (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    qr_size      INTEGER,
    qr_dark      TEXT,
    qr_light     TEXT,
    qr_style     TEXT,                  -- 'square' | 'dots'
    qr_ecc       TEXT,                  -- 'L' | 'M' | 'Q' | 'H'
    list_qr_size INTEGER,
    updated_by   INTEGER,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS tis_cart (
    user_id   INTEGER NOT NULL,
    person_id INTEGER NOT NULL,
    added_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, person_id)
  );
`);

// Lightweight migrations for DBs created before these columns existed.
try { db.prepare('ALTER TABLE tis_people ADD COLUMN last_used_at DATETIME').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE tis_people ADD COLUMN pharmacy_no TEXT').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE tis_people ADD COLUMN qr_dark TEXT').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE tis_people ADD COLUMN qr_light TEXT').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE tis_people ADD COLUMN qr_style TEXT').run(); } catch { /* already present */ }

console.log('[qr-tis] Database ready at:', DB_PATH);

const DEFAULT_SETTINGS = {
  qr_size: 340, qr_dark: '#0f172a', qr_light: '#ffffff',
  qr_style: 'square', qr_ecc: 'M', list_qr_size: 150,
};

// ── People ──────────────────────────────────────────────────────────────────────
function listPeople() {
  return db.prepare(
    `SELECT id, pharmacy_no, nombre, apellidos, tis, group_name, qr_dark, qr_light, qr_style, active, created_at, updated_at
       FROM tis_people ORDER BY apellidos COLLATE NOCASE, nombre COLLATE NOCASE, id`
  ).all();
}

function getPerson(id) {
  return db.prepare('SELECT * FROM tis_people WHERE id = ?').get(id) || null;
}

// Uniqueness helpers. The pharmacy number must be unique EXCEPT '00000' (the
// "no number" placeholder, which may repeat). The TIS must always be unique.
// `exceptId` excludes a person from the check (for edits).
function pharmacyTaken(pharmacy_no, exceptId) {
  if (!pharmacy_no || pharmacy_no === '00000') return false;
  const row = exceptId != null
    ? db.prepare('SELECT 1 FROM tis_people WHERE pharmacy_no = ? AND id != ?').get(pharmacy_no, exceptId)
    : db.prepare('SELECT 1 FROM tis_people WHERE pharmacy_no = ?').get(pharmacy_no);
  return !!row;
}
function tisTaken(tis, exceptId) {
  if (!tis) return false;
  const row = exceptId != null
    ? db.prepare('SELECT 1 FROM tis_people WHERE tis = ? AND id != ?').get(tis, exceptId)
    : db.prepare('SELECT 1 FROM tis_people WHERE tis = ?').get(tis);
  return !!row;
}

function createPerson(data, userId) {
  const info = db.prepare(
    `INSERT INTO tis_people (pharmacy_no, nombre, apellidos, tis, group_name, qr_dark, qr_light, qr_style, active, created_by, last_used_at)
     VALUES (@pharmacy_no, @nombre, @apellidos, @tis, @group_name, @qr_dark, @qr_light, @qr_style, 1, @created_by, CURRENT_TIMESTAMP)`
  ).run({
    pharmacy_no: data.pharmacy_no || null,
    nombre: data.nombre, apellidos: data.apellidos, tis: data.tis,
    group_name: data.group_name || null,
    qr_dark: data.qr_dark || null, qr_light: data.qr_light || null, qr_style: data.qr_style || null,
    created_by: userId != null ? userId : null,
  });
  return getPerson(info.lastInsertRowid);
}

// Insert many people in one transaction. `rows` are already validated.
// Returns the created rows.
const createManyPeople = db.transaction((rows, userId) => rows.map(r => createPerson(r, userId)));

// Bump "last handled" without touching updated_at (used when a ficha/QR is opened).
function touchPerson(id) {
  db.prepare('UPDATE tis_people SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?').run(id);
  return getPerson(id);
}

// The N people most recently handled (created / edited / viewed).
function recentPeople(limit) {
  return db.prepare(
    `SELECT id, pharmacy_no, nombre, apellidos, tis, group_name, active,
            COALESCE(last_used_at, updated_at, created_at) AS handled_at
       FROM tis_people
      ORDER BY COALESCE(last_used_at, updated_at, created_at) DESC, id DESC
      LIMIT ?`
  ).all(Math.max(1, Math.min(50, limit || 10)));
}

// Partial update: only the provided fields change.
function updatePerson(id, data) {
  const cur = getPerson(id);
  if (!cur) return null;
  const next = {
    pharmacy_no: data.pharmacy_no !== undefined ? (data.pharmacy_no || null) : cur.pharmacy_no,
    nombre: data.nombre != null ? data.nombre : cur.nombre,
    apellidos: data.apellidos != null ? data.apellidos : cur.apellidos,
    tis: data.tis != null ? data.tis : cur.tis,
    group_name: data.group_name !== undefined ? (data.group_name || null) : cur.group_name,
    qr_dark: data.qr_dark !== undefined ? (data.qr_dark || null) : cur.qr_dark,
    qr_light: data.qr_light !== undefined ? (data.qr_light || null) : cur.qr_light,
    qr_style: data.qr_style !== undefined ? (data.qr_style || null) : cur.qr_style,
    active: data.active != null ? (data.active ? 1 : 0) : cur.active,
  };
  db.prepare(
    `UPDATE tis_people
       SET pharmacy_no = @pharmacy_no, nombre = @nombre, apellidos = @apellidos, tis = @tis,
           group_name = @group_name, qr_dark = @qr_dark, qr_light = @qr_light, qr_style = @qr_style,
           active = @active, updated_at = CURRENT_TIMESTAMP, last_used_at = CURRENT_TIMESTAMP
     WHERE id = @id`
  ).run({ ...next, id });
  return getPerson(id);
}

function deletePerson(id) {
  db.prepare('DELETE FROM tis_cart WHERE person_id = ?').run(id);
  return db.prepare('DELETE FROM tis_people WHERE id = ?').run(id).changes > 0;
}

// ── Global QR settings (single shared row) ──────────────────────────────────────
function getSettings() {
  const row = db.prepare('SELECT * FROM tis_settings WHERE id = 1').get();
  return { ...DEFAULT_SETTINGS, ...(row || {}) };
}

function saveSettings(data, userId) {
  const s = { ...getSettings(), ...data };
  db.prepare(
    `INSERT INTO tis_settings (id, qr_size, qr_dark, qr_light, qr_style, qr_ecc, list_qr_size, updated_by, updated_at)
     VALUES (1, @qr_size, @qr_dark, @qr_light, @qr_style, @qr_ecc, @list_qr_size, @updated_by, CURRENT_TIMESTAMP)
     ON CONFLICT(id) DO UPDATE SET
       qr_size = excluded.qr_size, qr_dark = excluded.qr_dark, qr_light = excluded.qr_light,
       qr_style = excluded.qr_style, qr_ecc = excluded.qr_ecc, list_qr_size = excluded.list_qr_size,
       updated_by = excluded.updated_by, updated_at = CURRENT_TIMESTAMP`
  ).run({
    qr_size: s.qr_size, qr_dark: s.qr_dark, qr_light: s.qr_light,
    qr_style: s.qr_style, qr_ecc: s.qr_ecc, list_qr_size: s.list_qr_size,
    updated_by: userId != null ? userId : null,
  });
  return getSettings();
}

// ── Per-user cart ───────────────────────────────────────────────────────────────
function cartIds(userId) {
  return db.prepare('SELECT person_id FROM tis_cart WHERE user_id = ? ORDER BY added_at, person_id').all(userId).map(r => r.person_id);
}
function cartAdd(userId, personId) {
  db.prepare('INSERT OR IGNORE INTO tis_cart (user_id, person_id) VALUES (?, ?)').run(userId, personId);
  return cartIds(userId);
}
function cartRemove(userId, personId) {
  db.prepare('DELETE FROM tis_cart WHERE user_id = ? AND person_id = ?').run(userId, personId);
  return cartIds(userId);
}
function cartClear(userId) {
  db.prepare('DELETE FROM tis_cart WHERE user_id = ?').run(userId);
  return [];
}

module.exports = {
  db, DEFAULT_SETTINGS,
  listPeople, getPerson, createPerson, createManyPeople, updatePerson, deletePerson,
  pharmacyTaken, tisTaken, touchPerson, recentPeople,
  getSettings, saveSettings,
  cartIds, cartAdd, cartRemove, cartClear,
};
