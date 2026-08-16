'use strict';

// ── Asignación de medicación — database (SEPARATE, self-contained) ───────────────
// Connects the people directory (qr-tis) with the medication boxes (datamatrix).
// This DB only stores the *assignment* layer; people live in qr_tis.db and boxes
// live in datamatrix.db (read/updated in-process through their own modules).
//
//   asig_plan     — a person's recurring medication plan (which medications, how
//                   many boxes per period). Pre-fills each monthly cycle.
//   asig_period   — a monthly assignment cycle per person ('YYYY-MM').
//   asig_line     — a box attached to a person within a period. state:
//                     'preasignada' (reserved, box still in stock) →
//                     'asignada'    (dispensed to the person = box 'utilizado').
//   asig_settings — a single global row of ficha display sizes.

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.ASIG_DB_PATH || '/data/asignacion.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS asig_plan (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id  INTEGER NOT NULL,          -- qr-tis person id
    gtin       TEXT NOT NULL,             -- datamatrix medication (GTIN)
    qty        INTEGER NOT NULL DEFAULT 1,-- boxes per period
    notes      TEXT,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(person_id, gtin)
  );
  CREATE INDEX IF NOT EXISTS idx_asig_plan_person ON asig_plan(person_id);

  CREATE TABLE IF NOT EXISTS asig_period (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id  INTEGER NOT NULL,
    ym         TEXT NOT NULL,             -- 'YYYY-MM'
    status     TEXT NOT NULL DEFAULT 'abierto',  -- 'abierto' | 'cerrado'
    created_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    closed_at  DATETIME,
    UNIQUE(person_id, ym)
  );
  CREATE INDEX IF NOT EXISTS idx_asig_period_person ON asig_period(person_id);

  CREATE TABLE IF NOT EXISTS asig_line (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id   INTEGER NOT NULL,
    person_id   INTEGER NOT NULL,
    gtin        TEXT,
    item_id     INTEGER NOT NULL,         -- datamatrix box id
    box_key     TEXT,
    state       TEXT NOT NULL DEFAULT 'preasignada', -- 'preasignada' | 'asignada'
    release_at  TEXT,                     -- 'YYYY-MM-DD' when Salud will free the box (optional)
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    assigned_at DATETIME,
    UNIQUE(period_id, item_id)
  );
  CREATE INDEX IF NOT EXISTS idx_asig_line_period ON asig_line(period_id);
  CREATE INDEX IF NOT EXISTS idx_asig_line_person ON asig_line(person_id);
  CREATE INDEX IF NOT EXISTS idx_asig_line_item ON asig_line(item_id);

  CREATE TABLE IF NOT EXISTS asig_settings (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    ficha_qr_size INTEGER,
    ficha_dm_size INTEGER,
    updated_by    INTEGER,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

// Lightweight migration for DBs created before the release date existed.
try { db.prepare('ALTER TABLE asig_line ADD COLUMN release_at TEXT').run(); } catch { /* already present */ }

console.log('[asignacion] Database ready at:', DB_PATH);

const DEFAULT_SETTINGS = { ficha_qr_size: 300, ficha_dm_size: 150 };

// ── Plan (recurring medications per person) ──────────────────────────────────────
function listPlan(personId) {
  return db.prepare('SELECT * FROM asig_plan WHERE person_id = ? ORDER BY id').all(personId);
}
function getPlanLine(id) { return db.prepare('SELECT * FROM asig_plan WHERE id = ?').get(id) || null; }
function planByGtin(personId, gtin) {
  return db.prepare('SELECT * FROM asig_plan WHERE person_id = ? AND gtin = ?').get(personId, gtin) || null;
}
function upsertPlan(personId, gtin, data) {
  const cur = planByGtin(personId, gtin) || {};
  const row = {
    person_id: personId, gtin,
    qty: data.qty != null ? Math.max(1, Math.min(99, Math.round(Number(data.qty)) || 1)) : (cur.qty || 1),
    notes: data.notes !== undefined ? (data.notes || null) : (cur.notes || null),
    active: data.active != null ? (data.active ? 1 : 0) : (cur.active != null ? cur.active : 1),
  };
  db.prepare(
    `INSERT INTO asig_plan (person_id, gtin, qty, notes, active, updated_at)
     VALUES (@person_id, @gtin, @qty, @notes, @active, CURRENT_TIMESTAMP)
     ON CONFLICT(person_id, gtin) DO UPDATE SET qty = excluded.qty, notes = excluded.notes,
       active = excluded.active, updated_at = CURRENT_TIMESTAMP`
  ).run(row);
  return planByGtin(personId, gtin);
}
function deletePlanLine(id) { return db.prepare('DELETE FROM asig_plan WHERE id = ?').run(id).changes > 0; }
// Person ids that have at least one plan line (for the overview list).
function planPersonIds() { return db.prepare('SELECT DISTINCT person_id FROM asig_plan').all().map(r => r.person_id); }

// ── Period (monthly cycle per person) ────────────────────────────────────────────
function getPeriod(id) { return db.prepare('SELECT * FROM asig_period WHERE id = ?').get(id) || null; }
function findPeriod(personId, ym) {
  return db.prepare('SELECT * FROM asig_period WHERE person_id = ? AND ym = ?').get(personId, ym) || null;
}
function getOrCreatePeriod(personId, ym, userId) {
  const ex = findPeriod(personId, ym);
  if (ex) return ex;
  const info = db.prepare(
    `INSERT INTO asig_period (person_id, ym, status, created_by) VALUES (?, ?, 'abierto', ?)`
  ).run(personId, ym, userId != null ? userId : null);
  return getPeriod(info.lastInsertRowid);
}
function listPeriods(personId) {
  return db.prepare('SELECT * FROM asig_period WHERE person_id = ? ORDER BY ym DESC, id DESC').all(personId);
}
function latestPeriod(personId) {
  return db.prepare('SELECT * FROM asig_period WHERE person_id = ? ORDER BY ym DESC, id DESC LIMIT 1').get(personId) || null;
}
function setPeriodStatus(id, status) {
  const closed = status === 'cerrado';
  db.prepare('UPDATE asig_period SET status = ?, closed_at = ? WHERE id = ?')
    .run(closed ? 'cerrado' : 'abierto', closed ? new Date().toISOString().replace('T', ' ').slice(0, 19) : null, id);
  return getPeriod(id);
}
const deletePeriod = db.transaction((id) => {
  db.prepare('DELETE FROM asig_line WHERE period_id = ?').run(id);
  return db.prepare('DELETE FROM asig_period WHERE id = ?').run(id).changes > 0;
});
function periodPersonIds() { return db.prepare('SELECT DISTINCT person_id FROM asig_period').all().map(r => r.person_id); }

// ── Line (a box attached to a person within a period) ────────────────────────────
function listLines(periodId) {
  return db.prepare('SELECT * FROM asig_line WHERE period_id = ? ORDER BY gtin, id').all(periodId);
}
function getLine(id) { return db.prepare('SELECT * FROM asig_line WHERE id = ?').get(id) || null; }
function findLine(periodId, itemId) {
  return db.prepare('SELECT * FROM asig_line WHERE period_id = ? AND item_id = ?').get(periodId, itemId) || null;
}
// The most recent line referencing a given box (any period). Used to tell whether
// a box is already reserved/dispensed somewhere.
function lineByItem(itemId) {
  return db.prepare('SELECT * FROM asig_line WHERE item_id = ? ORDER BY id DESC LIMIT 1').get(itemId) || null;
}
function addLine(data) {
  const info = db.prepare(
    `INSERT INTO asig_line (period_id, person_id, gtin, item_id, box_key, state, release_at, assigned_at)
     VALUES (@period_id, @person_id, @gtin, @item_id, @box_key, @state, @release_at, @assigned_at)`
  ).run({
    period_id: data.period_id, person_id: data.person_id, gtin: data.gtin || null,
    item_id: data.item_id, box_key: data.box_key || null,
    state: data.state === 'asignada' ? 'asignada' : 'preasignada',
    release_at: data.release_at || null,
    assigned_at: data.state === 'asignada' ? new Date().toISOString().replace('T', ' ').slice(0, 19) : null,
  });
  return getLine(info.lastInsertRowid);
}
function setLineState(id, state) {
  const asignada = state === 'asignada';
  db.prepare('UPDATE asig_line SET state = ?, assigned_at = ? WHERE id = ?')
    .run(asignada ? 'asignada' : 'preasignada', asignada ? new Date().toISOString().replace('T', ' ').slice(0, 19) : null, id);
  return getLine(id);
}
// Set (or clear, with null) the date on which Salud will free this box.
function setLineRelease(id, isoDate) {
  db.prepare('UPDATE asig_line SET release_at = ? WHERE id = ?').run(isoDate || null, id);
  return getLine(id);
}
function deleteLine(id) { return db.prepare('DELETE FROM asig_line WHERE id = ?').run(id).changes > 0; }
// Still-reserved boxes that carry a planned release date (for the notifications).
function pendingReleaseLines() {
  return db.prepare("SELECT * FROM asig_line WHERE state = 'preasignada' AND release_at IS NOT NULL ORDER BY release_at, id").all();
}

// Counts for a period: how many boxes pre-assigned vs. already dispensed.
function periodCounts(periodId) {
  const pre = db.prepare("SELECT COUNT(*) n FROM asig_line WHERE period_id = ? AND state = 'preasignada'").get(periodId).n;
  const asig = db.prepare("SELECT COUNT(*) n FROM asig_line WHERE period_id = ? AND state = 'asignada'").get(periodId).n;
  return { preasignada: pre, asignada: asig, total: pre + asig };
}

// ── Settings ────────────────────────────────────────────────────────────────────
function getSettings() {
  const row = db.prepare('SELECT * FROM asig_settings WHERE id = 1').get() || {};
  const out = { ...DEFAULT_SETTINGS };
  for (const k of Object.keys(DEFAULT_SETTINGS)) if (row[k] != null) out[k] = row[k];
  return out;
}
function saveSettings(data, userId) {
  const s = { ...getSettings(), ...data };
  db.prepare(
    `INSERT INTO asig_settings (id, ficha_qr_size, ficha_dm_size, updated_by, updated_at)
     VALUES (1, @ficha_qr_size, @ficha_dm_size, @updated_by, CURRENT_TIMESTAMP)
     ON CONFLICT(id) DO UPDATE SET ficha_qr_size = excluded.ficha_qr_size,
       ficha_dm_size = excluded.ficha_dm_size, updated_by = excluded.updated_by, updated_at = CURRENT_TIMESTAMP`
  ).run({ ficha_qr_size: s.ficha_qr_size, ficha_dm_size: s.ficha_dm_size, updated_by: userId != null ? userId : null });
  return getSettings();
}

module.exports = {
  db, DEFAULT_SETTINGS,
  listPlan, getPlanLine, planByGtin, upsertPlan, deletePlanLine, planPersonIds,
  getPeriod, findPeriod, getOrCreatePeriod, listPeriods, latestPeriod, setPeriodStatus, deletePeriod, periodPersonIds,
  listLines, getLine, findLine, lineByItem, addLine, setLineState, setLineRelease, pendingReleaseLines, deleteLine, periodCounts,
  getSettings, saveSettings,
};
