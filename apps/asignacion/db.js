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
    gtin       TEXT,                      -- datamatrix medication (GTIN) — null until a box links it
    cn         TEXT,                      -- Código Nacional (identity when there's no GTIN yet)
    nombre     TEXT,                      -- medication name (typed; used when the catalogue has none)
    barcode    TEXT,                      -- EAN / código de barras (optional)
    qty        INTEGER NOT NULL DEFAULT 1,-- boxes per period
    notes      TEXT,
    active     INTEGER NOT NULL DEFAULT 1,
    release_at   TEXT,                    -- official Salud release date of the NEXT box (recurring, per medication)
    advance_days INTEGER NOT NULL DEFAULT 15, -- effective date = release_at − advance_days
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    notify_mode   TEXT,
    updated_by    INTEGER,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS asig_notif (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT,
    ntype         TEXT NOT NULL DEFAULT 'any',       -- 'any' (≥1 medicamento) | 'all' (toda la medicación)
    criterion     TEXT NOT NULL DEFAULT 'exact',     -- 'exact' (novedades del día) | 'lte' (acumulado ≤ fecha)
    schedule_kind TEXT NOT NULL DEFAULT 'once',       -- 'once' | 'recurring'
    once_date     TEXT,                               -- YYYY-MM-DD (once)
    weekdays      TEXT,                               -- CSV 0-6 (recurring; vacío = todos los días)
    send_time     TEXT NOT NULL DEFAULT '08:00',      -- HH:MM (24h)
    recipients    TEXT NOT NULL DEFAULT '',           -- CSV de emails
    enabled       INTEGER NOT NULL DEFAULT 1,
    last_sent_date TEXT,                              -- YYYY-MM-DD del último envío
    last_sent_at   DATETIME,
    created_by    INTEGER,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  -- ── Post-its (notas adhesivas) en tablones ─────────────────────────────────
  CREATE TABLE IF NOT EXISTS asig_board (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    author_id  INTEGER,                            -- null = tablón semilla del sistema
    ord        INTEGER NOT NULL DEFAULT 0,         -- orden de las pestañas
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS asig_note (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id   INTEGER NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    color      TEXT NOT NULL DEFAULT '#FEF08A',
    pos_x      REAL NOT NULL DEFAULT 20,
    pos_y      REAL NOT NULL DEFAULT 20,
    width      REAL NOT NULL DEFAULT 240,
    height     REAL NOT NULL DEFAULT 200,
    visibility TEXT NOT NULL DEFAULT 'privada',    -- 'privada' | 'todos' | 'personalizada'
    author_id  INTEGER,
    edited_by  INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE INDEX IF NOT EXISTS idx_asig_note_board ON asig_note(board_id);
  CREATE TABLE IF NOT EXISTS asig_note_viewer (
    note_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (note_id, user_id)
  );
  CREATE TABLE IF NOT EXISTS asig_note_seen (
    note_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (note_id, user_id)
  );

  -- ── Pauta por franja horaria (Pastillero) ──────────────────────────────────
  -- Reparto de un medicamento del plan en las 4 franjas del día, CON VIGENCIA:
  -- cada cambio de pauta inserta una fila nueva con la fecha desde la que aplica
  -- (nunca se sobreescribe), así el histórico queda intacto y el mes siguiente
  -- hereda solo la última pauta sin ningún reseteo. Engancha a asig_plan.id (la
  -- medicación recurrente), no al periodo mensual.
  CREATE TABLE IF NOT EXISTS asig_dose_schedule (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id        INTEGER NOT NULL,
    effective_from TEXT NOT NULL,             -- 'YYYY-MM-DD', vigente desde este día en adelante
    desayuno       INTEGER NOT NULL DEFAULT 0,
    comida         INTEGER NOT NULL DEFAULT 0,
    cena           INTEGER NOT NULL DEFAULT 0,
    noche          INTEGER NOT NULL DEFAULT 0,
    created_by     INTEGER,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(plan_id, effective_from)
  );
  CREATE INDEX IF NOT EXISTS idx_asig_dose_plan ON asig_dose_schedule(plan_id, effective_from);
`);

// Lightweight migration for DBs created before the release date existed.
try { db.prepare('ALTER TABLE asig_line ADD COLUMN release_at TEXT').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE asig_settings ADD COLUMN notify_mode TEXT').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE asig_note ADD COLUMN alert INTEGER NOT NULL DEFAULT 0').run(); } catch { /* already present */ }
// Días de anticipación: la fecha efectiva (en la que ya se puede actuar) es la
// fecha oficial de Salud menos estos días. Por defecto 15, ajustable por línea.
try { db.prepare('ALTER TABLE asig_line ADD COLUMN advance_days INTEGER NOT NULL DEFAULT 15').run(); } catch { /* already present */ }
// The release date + anticipation now live on the MEDICATION (recurring plan), not
// on the ephemeral box: a box is dispensed and gone, but the medication returns
// every month on the same Salud date.
try { db.prepare('ALTER TABLE asig_plan ADD COLUMN release_at TEXT').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE asig_plan ADD COLUMN advance_days INTEGER NOT NULL DEFAULT 15').run(); } catch { /* already present */ }

// Plan medications can now exist by Código Nacional before any GTIN/Data Matrix.
// Old asig_plan had `gtin NOT NULL` + inline UNIQUE(person_id,gtin); rebuild it so
// gtin is nullable and CN-only rows are possible. (No FKs reference asig_plan.)
{
  const planCols = db.prepare('PRAGMA table_info(asig_plan)').all().map(c => c.name);
  if (!planCols.includes('cn')) {
    db.transaction(() => {
      db.exec(`
        CREATE TABLE asig_plan_new (
          id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER NOT NULL,
          gtin TEXT, cn TEXT, nombre TEXT, barcode TEXT,
          qty INTEGER NOT NULL DEFAULT 1, notes TEXT, active INTEGER NOT NULL DEFAULT 1,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO asig_plan_new (id, person_id, gtin, qty, notes, active, created_at, updated_at)
          SELECT id, person_id, gtin, qty, notes, active, created_at, updated_at FROM asig_plan;
        DROP TABLE asig_plan;
        ALTER TABLE asig_plan_new RENAME TO asig_plan;
        CREATE INDEX IF NOT EXISTS idx_asig_plan_person ON asig_plan(person_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_asig_plan_person_gtin ON asig_plan(person_id, gtin) WHERE gtin IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_asig_plan_person_cn ON asig_plan(person_id, cn) WHERE gtin IS NULL AND cn IS NOT NULL;
      `);
    })();
  }
}
// Partial unique indexes — created AFTER the migration so `cn` is guaranteed to
// exist: one catalogued med (by GTIN) and one CN-only med (by CN) per person.
db.exec(`
  CREATE UNIQUE INDEX IF NOT EXISTS idx_asig_plan_person_gtin ON asig_plan(person_id, gtin) WHERE gtin IS NOT NULL;
  CREATE UNIQUE INDEX IF NOT EXISTS idx_asig_plan_person_cn ON asig_plan(person_id, cn) WHERE gtin IS NULL AND cn IS NOT NULL;

  -- Direct assignments recorded WITHOUT a Data Matrix box: the medication was
  -- assigned in Salud by scanning its barcode ("precinto"). One row = one unit.
  CREATE TABLE IF NOT EXISTS asig_precinto (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id   INTEGER NOT NULL,
    person_id   INTEGER NOT NULL,
    plan_id     INTEGER,
    gtin        TEXT, cn TEXT, barcode TEXT, nombre TEXT,
    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by  INTEGER
  );
  CREATE INDEX IF NOT EXISTS idx_asig_precinto_period ON asig_precinto(period_id);
`);

// ── Precinto "pegado" (stuck on the official Salud sheet) + photo evidence ────────
// Salud makes the pharmacy cut each ASSIGNED medication's barcode ("precinto") and
// stick it on an official 4×7 A4 sheet before month-end; unstuck ⇒ unpaid. Every
// assigned unit — a Data Matrix line (state 'asignada') or an asig_precinto row —
// is one physical precinto to stick. We track that per source row, plus a photo
// evidence store (proof it was sent) associated to the precintos it covers.
db.exec(`
  CREATE TABLE IF NOT EXISTS asig_evidencia (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ym         TEXT,
    photo      BLOB NOT NULL,
    mime       TEXT,
    note       TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER
  );
  CREATE INDEX IF NOT EXISTS idx_asig_evidencia_ym ON asig_evidencia(ym);
`);
for (const t of ['asig_line', 'asig_precinto']) {
  try { db.prepare(`ALTER TABLE ${t} ADD COLUMN pegado INTEGER NOT NULL DEFAULT 0`).run(); } catch { /* present */ }
  try { db.prepare(`ALTER TABLE ${t} ADD COLUMN pegado_at DATETIME`).run(); } catch { /* present */ }
  try { db.prepare(`ALTER TABLE ${t} ADD COLUMN pegado_method TEXT`).run(); } catch { /* present */ }
  try { db.prepare(`ALTER TABLE ${t} ADD COLUMN evidencia_id INTEGER`).run(); } catch { /* present */ }
}

// ── Notes attached to an entity (a person or a physical precinto) ─────────────────
// A small, pretty note ("qué le pasa"): one per entity, upsert, with a colour.
// entity_type: 'person' | 'sticker'; entity_key: person id, or "<source>:<id>".
db.exec(`
  CREATE TABLE IF NOT EXISTS asig_entnote (
    entity_type TEXT NOT NULL,
    entity_key  TEXT NOT NULL,
    text        TEXT NOT NULL,
    color       TEXT,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by  INTEGER,
    PRIMARY KEY (entity_type, entity_key)
  );
  -- Per-user cart of people (like the other apps).
  CREATE TABLE IF NOT EXISTS asig_cart (
    user_id   INTEGER NOT NULL,
    person_id INTEGER NOT NULL,
    added_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, person_id)
  );
  -- A person's medication plan can exist "empty" (created on purpose, no meds yet)
  -- so it persists and shows as "con plan" even before any medication is added.
  CREATE TABLE IF NOT EXISTS asig_plan_created (
    person_id  INTEGER PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER
  );
`);

console.log('[asignacion] Database ready at:', DB_PATH);

// notify_mode: how the release bell groups a person's pending boxes —
//   'all' (ready when ALL are out), 'any' (ready when any is out), 'box' (per box).
const DEFAULT_SETTINGS = { ficha_qr_size: 300, ficha_dm_size: 150, notify_mode: 'all' };

// ── Plan (recurring medications per person) ──────────────────────────────────────
function listPlan(personId) {
  return db.prepare('SELECT * FROM asig_plan WHERE person_id = ? ORDER BY id').all(personId);
}
// How many DIFFERENT medications are being handled: distinct CN across active plans.
function distinctCnCount() {
  return db.prepare("SELECT COUNT(DISTINCT cn) n FROM asig_plan WHERE active = 1 AND cn IS NOT NULL AND cn <> ''").get().n;
}
// Active plan medications across ALL people that match a Código Nacional or a GTIN
// — used to find who could use a given Data Matrix box (the "conexión del CN").
function plansByCnOrGtin(cn, gtin) {
  const c = cn ? String(cn) : null, g = gtin ? String(gtin) : null;
  if (!c && !g) return [];
  return db.prepare(
    `SELECT * FROM asig_plan
      WHERE active = 1 AND ((@cn IS NOT NULL AND cn = @cn) OR (@gtin IS NOT NULL AND gtin = @gtin))
      ORDER BY id`
  ).all({ cn: c, gtin: g });
}
// Lightweight medication summary for a person (used by the QR·TIS ficha button).
function personMedSummary(personId) {
  const rows = db.prepare('SELECT active FROM asig_plan WHERE person_id = ?').all(personId);
  const active_count = rows.filter(r => r.active).length;
  const latest = latestPeriod(personId);
  const flagged = !!db.prepare('SELECT 1 FROM asig_plan_created WHERE person_id = ?').get(personId);
  return { plan_count: rows.length, active_count, has_plan: rows.length > 0 || flagged, empty_plan: rows.length === 0 && flagged, latest_ym: latest ? latest.ym : null };
}
// Mark a person's plan as created (empty is fine); persists so it counts as a plan.
function createEmptyPlan(personId, userId) {
  db.prepare('INSERT OR IGNORE INTO asig_plan_created (person_id, created_by) VALUES (?, ?)').run(personId, userId != null ? userId : null);
  return true;
}
function getPlanLine(id) { return db.prepare('SELECT * FROM asig_plan WHERE id = ?').get(id) || null; }

// ── Pauta por franja (Pastillero) ─────────────────────────────────────────────
const SLOTS = ['desayuno', 'comida', 'cena', 'noche'];
const cleanSlotQty = v => Math.max(0, Math.min(9, Math.round(Number(v)) || 0));
const todayIso = () => new Date().toISOString().slice(0, 10);
// Set (or replace) the dose distribution effective FROM this date onward. Never
// overwrites a past change — a new effective_from is a new row, so history stays
// intact; re-saving the SAME date updates that day's row instead of duplicating it.
function setDoseSchedule(planId, effectiveFrom, doses, userId) {
  const from = /^\d{4}-\d{2}-\d{2}$/.test(String(effectiveFrom || '')) ? effectiveFrom : todayIso();
  const row = { plan_id: planId, effective_from: from, created_by: userId != null ? userId : null };
  for (const s of SLOTS) row[s] = cleanSlotQty(doses && doses[s]);
  db.prepare(
    `INSERT INTO asig_dose_schedule (plan_id, effective_from, desayuno, comida, cena, noche, created_by)
     VALUES (@plan_id, @effective_from, @desayuno, @comida, @cena, @noche, @created_by)
     ON CONFLICT(plan_id, effective_from) DO UPDATE SET
       desayuno = excluded.desayuno, comida = excluded.comida, cena = excluded.cena, noche = excluded.noche,
       created_by = excluded.created_by`
  ).run(row);
  return getDoseHistory(planId);
}
// The schedule in effect on a given date: the most recent row with
// effective_from ≤ date. Null when nothing has been set yet (pauta sin definir).
function getDoseScheduleForDate(planId, date) {
  const d = /^\d{4}-\d{2}-\d{2}$/.test(String(date || '')) ? date : todayIso();
  return db.prepare(
    `SELECT * FROM asig_dose_schedule WHERE plan_id = ? AND effective_from <= ?
       ORDER BY effective_from DESC LIMIT 1`
  ).get(planId, d) || null;
}
// Full history of pauta changes for a medication, oldest first.
function getDoseHistory(planId) {
  return db.prepare('SELECT * FROM asig_dose_schedule WHERE plan_id = ? ORDER BY effective_from').all(planId);
}
function planByGtin(personId, gtin) {
  return db.prepare('SELECT * FROM asig_plan WHERE person_id = ? AND gtin = ?').get(personId, gtin) || null;
}
// A CN-only plan med (no GTIN yet) — the "info before Data Matrix" state.
function planByCn(personId, cn) {
  return db.prepare('SELECT * FROM asig_plan WHERE person_id = ? AND cn = ? AND gtin IS NULL').get(personId, cn) || null;
}
const cleanQty = (v, dflt = 1) => (v != null ? Math.max(1, Math.min(99, Math.round(Number(v)) || 1)) : dflt);
// Add/update a plan medication. Identify by GTIN (catalogued) or, when there's no
// GTIN yet, by Código Nacional. Both keep nombre/barcode/qty/notes.
function addPlanMed(personId, data) {
  const gtin = data.gtin ? String(data.gtin).trim() : null;
  const cn = data.cn ? String(data.cn).trim() : null;
  const nombre = data.nombre != null ? (String(data.nombre).trim() || null) : null;
  const barcode = data.barcode != null ? (String(data.barcode).trim() || null) : null;
  const cur = gtin ? planByGtin(personId, gtin) : (cn ? planByCn(personId, cn) : null);
  if (cur) {
    db.prepare(`UPDATE asig_plan SET qty = @qty, notes = @notes, active = @active,
       cn = COALESCE(@cn, cn), nombre = COALESCE(@nombre, nombre), barcode = COALESCE(@barcode, barcode),
       updated_at = CURRENT_TIMESTAMP WHERE id = @id`).run({
      id: cur.id, qty: cleanQty(data.qty, cur.qty || 1),
      notes: data.notes !== undefined ? (data.notes || null) : (cur.notes || null),
      active: data.active != null ? (data.active ? 1 : 0) : (cur.active != null ? cur.active : 1),
      cn, nombre, barcode,
    });
    return getPlanLine(cur.id);
  }
  const info = db.prepare(
    `INSERT INTO asig_plan (person_id, gtin, cn, nombre, barcode, qty, notes, active, updated_at)
     VALUES (@person_id, @gtin, @cn, @nombre, @barcode, @qty, @notes, @active, CURRENT_TIMESTAMP)`
  ).run({
    person_id: personId, gtin, cn, nombre, barcode,
    qty: cleanQty(data.qty), notes: data.notes || null,
    active: data.active != null ? (data.active ? 1 : 0) : 1,
  });
  return getPlanLine(info.lastInsertRowid);
}
// Back-compat helper for the GTIN path.
function upsertPlan(personId, gtin, data) { return addPlanMed(personId, { ...data, gtin }); }
// Edit qty/notes/active of a plan row by id (works for CN-only rows too).
function updatePlanById(id, data) {
  const cur = getPlanLine(id); if (!cur) return null;
  db.prepare(`UPDATE asig_plan SET qty = @qty, notes = @notes, active = @active, updated_at = CURRENT_TIMESTAMP WHERE id = @id`).run({
    id, qty: cleanQty(data.qty, cur.qty || 1),
    notes: data.notes !== undefined ? (data.notes || null) : (cur.notes || null),
    active: data.active != null ? (data.active ? 1 : 0) : (cur.active != null ? cur.active : 1),
  });
  return getPlanLine(id);
}
// Edit a plan medication's identity/name. For a CN-only med you can change name,
// Código Nacional and barcode; for a catalogued med (has GTIN) only the name.
function editPlanMed(id, data) {
  const cur = getPlanLine(id); if (!cur) return null;
  const nombre = data.nombre !== undefined ? (String(data.nombre).trim() || null) : cur.nombre;
  if (cur.gtin) { db.prepare('UPDATE asig_plan SET nombre = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run(nombre, id); return getPlanLine(id); }
  db.prepare('UPDATE asig_plan SET nombre = @nombre, cn = @cn, barcode = @barcode, updated_at = CURRENT_TIMESTAMP WHERE id = @id').run({
    id, nombre,
    cn: data.cn !== undefined ? (String(data.cn).replace(/\D/g, '') || null) : cur.cn,
    barcode: data.barcode !== undefined ? (data.barcode ? String(data.barcode).replace(/\D/g, '') : null) : cur.barcode,
  });
  return getPlanLine(id);
}
// A CN-only plan med "graduates" once a real box gives us its GTIN. If the person
// already has that GTIN in the plan, merge (drop the CN-only row); else set gtin.
function reconcilePlanGtin(id, gtin) {
  const cur = getPlanLine(id); if (!cur || !gtin || cur.gtin) return cur;
  const existing = planByGtin(cur.person_id, gtin);
  if (existing && existing.id !== cur.id) { db.prepare('DELETE FROM asig_plan WHERE id = ?').run(cur.id); return existing; }
  db.prepare('UPDATE asig_plan SET gtin = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run(gtin, id);
  return getPlanLine(id);
}
function deletePlanLine(id) { return db.prepare('DELETE FROM asig_plan WHERE id = ?').run(id).changes > 0; }
// Reverse of reconcilePlanGtin: drop the GTIN so a med with a CN goes back to
// "pendiente de caja" (CN-only) when its box is removed. Only if it still has a CN.
function clearPlanGtin(id) {
  const cur = getPlanLine(id); if (!cur || !cur.gtin || !cur.cn) return cur;
  db.prepare('UPDATE asig_plan SET gtin = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run(id);
  return getPlanLine(id);
}
// Set (or clear, with null) the official Salud release date of a plan medication.
function setPlanRelease(id, isoDate) {
  db.prepare('UPDATE asig_plan SET release_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run(isoDate || null, id);
  return getPlanLine(id);
}
function setPlanAdvance(id, days) {
  db.prepare('UPDATE asig_plan SET advance_days = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run(clampAdvance(days), id);
  return getPlanLine(id);
}
// All active plan medications that carry a release date (for the bell / notifications).
function plansForRelease() {
  return db.prepare("SELECT * FROM asig_plan WHERE active = 1 AND release_at IS NOT NULL ORDER BY release_at, id").all();
}
// The most recent still-reserved (pre-asignada) box for a person's medication, by
// GTIN — used to show its Data Matrix in the notification email (may be none).
function findPendingLineForMed(personId, gtin) {
  if (!gtin) return null;
  return db.prepare("SELECT * FROM asig_line WHERE person_id = ? AND gtin = ? AND state = 'preasignada' ORDER BY id DESC LIMIT 1").get(personId, gtin) || null;
}
// The plan medication a box/line belongs to (match by GTIN, then by Código Nacional).
function planForItem(personId, gtin, cn) {
  if (gtin) { const g = planByGtin(personId, gtin); if (g) return g; }
  if (cn) { const c = planByCn(personId, cn); if (c) return c; }
  return null;
}
// Person ids that have at least one plan line (for the overview list).
function planPersonIds() {
  const set = new Set(db.prepare('SELECT DISTINCT person_id FROM asig_plan').all().map(r => r.person_id));
  for (const r of db.prepare('SELECT person_id FROM asig_plan_created').all()) set.add(r.person_id);
  return [...set];
}
function personsWithPlanSet() { return new Set(planPersonIds()); }

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
// Días de anticipación por defecto (la farmacia suele actuar 15 días antes de la
// fecha oficial de Salud). Ajustable por línea (medicamento + persona).
const DEFAULT_ADVANCE = 15;
function clampAdvance(v) {
  const n = Math.round(Number(v));
  if (!Number.isFinite(n)) return DEFAULT_ADVANCE;
  return Math.min(365, Math.max(0, n));
}
// Fecha efectiva = fecha oficial − días de anticipación (ISO 'YYYY-MM-DD' o null).
function effectiveDate(isoOfficial, advanceDays) {
  if (!isoOfficial || !/^\d{4}-\d{2}-\d{2}$/.test(isoOfficial)) return null;
  const d = new Date(isoOfficial + 'T00:00:00');
  if (isNaN(d)) return null;
  d.setDate(d.getDate() - clampAdvance(advanceDays));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
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
    `INSERT INTO asig_line (period_id, person_id, gtin, item_id, box_key, state, release_at, advance_days, assigned_at)
     VALUES (@period_id, @person_id, @gtin, @item_id, @box_key, @state, @release_at, @advance_days, @assigned_at)`
  ).run({
    period_id: data.period_id, person_id: data.person_id, gtin: data.gtin || null,
    item_id: data.item_id, box_key: data.box_key || null,
    state: data.state === 'asignada' ? 'asignada' : 'preasignada',
    release_at: data.release_at || null,
    advance_days: data.advance_days == null ? DEFAULT_ADVANCE : clampAdvance(data.advance_days),
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
// Set the days-of-anticipation for this line (medication + person).
function setLineAdvance(id, days) {
  db.prepare('UPDATE asig_line SET advance_days = ? WHERE id = ?').run(clampAdvance(days), id);
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
  const prec = db.prepare("SELECT COUNT(*) n FROM asig_precinto WHERE period_id = ?").get(periodId).n;
  return { preasignada: pre, asignada: asig + prec, total: pre + asig + prec };
}

// ── Precinto (direct assignments without a Data Matrix box) ───────────────────────
function getPrecinto(id) { return db.prepare('SELECT * FROM asig_precinto WHERE id = ?').get(id) || null; }
function listPrecinto(periodId) { return db.prepare('SELECT * FROM asig_precinto WHERE period_id = ? ORDER BY id').all(periodId); }
function addPrecinto(data, userId) {
  const info = db.prepare(
    `INSERT INTO asig_precinto (period_id, person_id, plan_id, gtin, cn, barcode, nombre, created_by)
     VALUES (@period_id, @person_id, @plan_id, @gtin, @cn, @barcode, @nombre, @created_by)`
  ).run({
    period_id: data.period_id, person_id: data.person_id, plan_id: data.plan_id != null ? data.plan_id : null,
    gtin: data.gtin || null, cn: data.cn || null, barcode: data.barcode || null, nombre: data.nombre || null,
    created_by: userId != null ? userId : null,
  });
  return getPrecinto(info.lastInsertRowid);
}
function deletePrecinto(id) { return db.prepare('DELETE FROM asig_precinto WHERE id = ?').run(id).changes > 0; }
// How many precinto assignments each plan medication has in a period.
function precintoCountByPlan(periodId) {
  const map = new Map();
  for (const r of db.prepare('SELECT plan_id, COUNT(*) n FROM asig_precinto WHERE period_id = ? GROUP BY plan_id').all(periodId)) map.set(r.plan_id, r.n);
  return map;
}
// Same day of the next month (clamped to the last day). ISO in → ISO out.
function nextMonthSameDay(iso) {
  const base = /^\d{4}-\d{2}-\d{2}$/.test(iso || '') ? new Date(iso + 'T00:00:00') : new Date();
  const day = base.getDate();
  const d = new Date(base.getFullYear(), base.getMonth() + 1, 1);
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  d.setDate(Math.min(day, last));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// ── Precintos físicos (pegado en la hoja oficial) ────────────────────────────────
// A "sticker" is any ASSIGNED unit that yields a physical barcode to cut & stick:
// a Data Matrix line in state 'asignada', or an asig_precinto row. Pegado state is
// stored on each source table; we read them together, filtered by month (period.ym).
function assignedLinesForYm(ym) {
  return db.prepare(
    `SELECT l.* FROM asig_line l JOIN asig_period p ON p.id = l.period_id
     WHERE p.ym = ? AND l.state = 'asignada' ORDER BY l.id`
  ).all(ym);
}
function precintosForYm(ym) {
  return db.prepare(
    `SELECT pr.* FROM asig_precinto pr JOIN asig_period p ON p.id = pr.period_id
     WHERE p.ym = ? ORDER BY pr.id`
  ).all(ym);
}
// Months that have at least one assigned sticker (for the month selector), newest first.
function stickerMonths() {
  const a = db.prepare(`SELECT p.ym ym, COUNT(*) n FROM asig_line l JOIN asig_period p ON p.id = l.period_id WHERE l.state = 'asignada' GROUP BY p.ym`).all();
  const b = db.prepare(`SELECT p.ym ym, COUNT(*) n FROM asig_precinto pr JOIN asig_period p ON p.id = pr.period_id GROUP BY p.ym`).all();
  const m = new Map();
  for (const r of [...a, ...b]) m.set(r.ym, (m.get(r.ym) || 0) + r.n);
  return [...m.entries()].map(([ym, total]) => ({ ym, total })).sort((x, y) => y.ym.localeCompare(x.ym));
}
function setLinePegado(id, pegado, method, evidenciaId) {
  if (pegado) db.prepare(`UPDATE asig_line SET pegado = 1, pegado_at = CURRENT_TIMESTAMP, pegado_method = ?, evidencia_id = ? WHERE id = ?`).run(method || 'manual', evidenciaId != null ? evidenciaId : null, id);
  else db.prepare(`UPDATE asig_line SET pegado = 0, pegado_at = NULL, pegado_method = NULL, evidencia_id = NULL WHERE id = ?`).run(id);
  return db.prepare('SELECT * FROM asig_line WHERE id = ?').get(id) || null;
}
function setPrecintoPegado(id, pegado, method, evidenciaId) {
  if (pegado) db.prepare(`UPDATE asig_precinto SET pegado = 1, pegado_at = CURRENT_TIMESTAMP, pegado_method = ?, evidencia_id = ? WHERE id = ?`).run(method || 'manual', evidenciaId != null ? evidenciaId : null, id);
  else db.prepare(`UPDATE asig_precinto SET pegado = 0, pegado_at = NULL, pegado_method = NULL, evidencia_id = NULL WHERE id = ?`).run(id);
  return db.prepare('SELECT * FROM asig_precinto WHERE id = ?').get(id) || null;
}
// Photo evidence (proof the precintos were sent stuck). Stored as a BLOB.
function addEvidencia(data, userId) {
  const info = db.prepare(
    `INSERT INTO asig_evidencia (ym, photo, mime, note, created_by) VALUES (@ym, @photo, @mime, @note, @created_by)`
  ).run({ ym: data.ym || null, photo: data.photo, mime: data.mime || 'image/jpeg', note: data.note || null, created_by: userId != null ? userId : null });
  return info.lastInsertRowid;
}
function getEvidencia(id) { return db.prepare('SELECT * FROM asig_evidencia WHERE id = ?').get(id) || null; }
function listEvidencia(ym) { return db.prepare('SELECT id, ym, mime, note, created_at, created_by FROM asig_evidencia WHERE ym = ? ORDER BY id DESC').all(ym); }

// ── Entity notes (person / sticker) ──────────────────────────────────────────────
function getEntNote(type, key) { return db.prepare('SELECT entity_type, entity_key, text, color, updated_at FROM asig_entnote WHERE entity_type = ? AND entity_key = ?').get(type, String(key)) || null; }
function setEntNote(type, key, data, userId) {
  const text = String(data && data.text != null ? data.text : '').trim();
  if (!text) { db.prepare('DELETE FROM asig_entnote WHERE entity_type = ? AND entity_key = ?').run(type, String(key)); return null; }
  db.prepare(`INSERT INTO asig_entnote (entity_type, entity_key, text, color, updated_at, updated_by)
     VALUES (@t, @k, @text, @color, CURRENT_TIMESTAMP, @u)
     ON CONFLICT(entity_type, entity_key) DO UPDATE SET text = excluded.text, color = excluded.color, updated_at = CURRENT_TIMESTAMP, updated_by = excluded.updated_by`)
    .run({ t: type, k: String(key), text: text.slice(0, 2000), color: data.color || null, u: userId != null ? userId : null });
  return getEntNote(type, key);
}
function entNotesMap(type) {
  const m = new Map();
  for (const r of db.prepare('SELECT entity_key, text, color, updated_at FROM asig_entnote WHERE entity_type = ?').all(type)) m.set(r.entity_key, { text: r.text, color: r.color, updated_at: r.updated_at });
  return m;
}

// ── Per-user cart of people ──────────────────────────────────────────────────────
function cartIds(userId) { return db.prepare('SELECT person_id FROM asig_cart WHERE user_id = ? ORDER BY added_at, person_id').all(userId).map(r => r.person_id); }
function cartAdd(userId, personId) { db.prepare('INSERT OR IGNORE INTO asig_cart (user_id, person_id) VALUES (?, ?)').run(userId, personId); return cartIds(userId); }
function cartRemove(userId, personId) { db.prepare('DELETE FROM asig_cart WHERE user_id = ? AND person_id = ?').run(userId, personId); return cartIds(userId); }
function cartClear(userId) { db.prepare('DELETE FROM asig_cart WHERE user_id = ?').run(userId); return []; }

// ── Scheduled email notifications ────────────────────────────────────────────────
function listNotifs() { return db.prepare('SELECT * FROM asig_notif ORDER BY enabled DESC, send_time, id').all(); }
function getNotif(id) { return db.prepare('SELECT * FROM asig_notif WHERE id = ?').get(id) || null; }
function createNotif(data, userId) {
  const info = db.prepare(
    `INSERT INTO asig_notif (name, ntype, criterion, schedule_kind, once_date, weekdays, send_time, recipients, enabled, created_by)
     VALUES (@name, @ntype, @criterion, @schedule_kind, @once_date, @weekdays, @send_time, @recipients, @enabled, @created_by)`
  ).run({
    name: data.name || null, ntype: data.ntype, criterion: data.criterion, schedule_kind: data.schedule_kind,
    once_date: data.once_date || null, weekdays: data.weekdays || null, send_time: data.send_time,
    recipients: data.recipients || '', enabled: data.enabled != null ? (data.enabled ? 1 : 0) : 1,
    created_by: userId != null ? userId : null,
  });
  return getNotif(info.lastInsertRowid);
}
function updateNotif(id, data) {
  const cur = getNotif(id); if (!cur) return null;
  const n = {
    name: data.name !== undefined ? (data.name || null) : cur.name,
    ntype: data.ntype || cur.ntype, criterion: data.criterion || cur.criterion,
    schedule_kind: data.schedule_kind || cur.schedule_kind,
    once_date: data.once_date !== undefined ? (data.once_date || null) : cur.once_date,
    weekdays: data.weekdays !== undefined ? (data.weekdays || null) : cur.weekdays,
    send_time: data.send_time || cur.send_time,
    recipients: data.recipients !== undefined ? (data.recipients || '') : cur.recipients,
    enabled: data.enabled != null ? (data.enabled ? 1 : 0) : cur.enabled,
  };
  db.prepare(
    `UPDATE asig_notif SET name=@name, ntype=@ntype, criterion=@criterion, schedule_kind=@schedule_kind,
       once_date=@once_date, weekdays=@weekdays, send_time=@send_time, recipients=@recipients, enabled=@enabled,
       updated_at=CURRENT_TIMESTAMP WHERE id=@id`
  ).run({ ...n, id });
  return getNotif(id);
}
function deleteNotif(id) { return db.prepare('DELETE FROM asig_notif WHERE id = ?').run(id).changes > 0; }
function setNotifEnabled(id, on) { db.prepare('UPDATE asig_notif SET enabled=?, updated_at=CURRENT_TIMESTAMP WHERE id=?').run(on ? 1 : 0, id); return getNotif(id); }
// Mark a notification as fired today (and disable one-time ones so they don't repeat).
function markNotifSent(id, dateIso) {
  const n = getNotif(id); if (!n) return null;
  db.prepare('UPDATE asig_notif SET last_sent_date=?, last_sent_at=CURRENT_TIMESTAMP, enabled=? WHERE id=?')
    .run(dateIso, n.schedule_kind === 'once' ? 0 : n.enabled, id);
  return getNotif(id);
}
// Notifications that should fire now (fire if the time has passed today, not sent
// today, and today matches the schedule). `wd` is the day of week (0=Sun..6=Sat).
function dueNotifs(dateIso, timeHhmm, wd) {
  return listNotifs().filter(n => {
    if (!n.enabled) return false;
    if (n.last_sent_date === dateIso) return false;
    if (String(n.send_time) > timeHhmm) return false;
    if (n.schedule_kind === 'once') return n.once_date === dateIso;
    const days = (n.weekdays || '').split(',').map(s => s.trim()).filter(Boolean);
    return days.length === 0 || days.includes(String(wd));
  });
}

// ── Post-its (boards + notes) ─────────────────────────────────────────────────────
const NOTE_COLORS = ['#FEF08A', '#BFDBFE', '#BBF7D0', '#FBCFE8', '#FDE68A', '#DDD6FE', '#FECACA', '#E2E8F0'];
const NOTE_MIN_W = 160, NOTE_MIN_H = 140, NOTE_MAX_W = 900, NOTE_MAX_H = 900;
function cleanNoteColor(c) { return NOTE_COLORS.includes(c) ? c : NOTE_COLORS[0]; }
function clampW(n) { const x = Number(n); return Number.isFinite(x) ? Math.min(NOTE_MAX_W, Math.max(NOTE_MIN_W, x)) : 240; }
function clampH(n) { const x = Number(n); return Number.isFinite(x) ? Math.min(NOTE_MAX_H, Math.max(NOTE_MIN_H, x)) : 200; }

// A note is visible to a user if they authored it, it's for everyone, or they are
// an explicit viewer of a 'personalizada' note.
const VIS_WHERE = `(n.author_id = @uid OR n.visibility = 'todos' OR (n.visibility = 'personalizada' AND EXISTS (SELECT 1 FROM asig_note_viewer v WHERE v.note_id = n.id AND v.user_id = @uid)))`;

function ensureSeedBoard() {
  const c = db.prepare('SELECT COUNT(*) c FROM asig_board').get().c;
  if (!c) db.prepare("INSERT INTO asig_board (name, author_id, ord) VALUES ('Tablón', NULL, 0)").run();
}
function getBoard(id) { return db.prepare('SELECT * FROM asig_board WHERE id = ?').get(id) || null; }
function boardCount() { return db.prepare('SELECT COUNT(*) c FROM asig_board').get().c; }
// Boards with, per board, how many notes the user can see and how many are new.
function listBoards(uid) {
  ensureSeedBoard();
  const boards = db.prepare('SELECT * FROM asig_board ORDER BY ord, id').all();
  const vis = db.prepare(`SELECT COUNT(*) c FROM asig_note n WHERE n.board_id = @board AND ${VIS_WHERE}`);
  const neu = db.prepare(`SELECT COUNT(*) c FROM asig_note n WHERE n.board_id = @board AND ${VIS_WHERE} AND NOT EXISTS (SELECT 1 FROM asig_note_seen s WHERE s.note_id = n.id AND s.user_id = @uid)`);
  return boards.map(b => ({ ...b, note_count: vis.get({ board: b.id, uid }).c, new_count: neu.get({ board: b.id, uid }).c }));
}
function createBoard(name, uid) {
  const ord = db.prepare('SELECT COALESCE(MAX(ord), -1) + 1 o FROM asig_board').get().o;
  const info = db.prepare('INSERT INTO asig_board (name, author_id, ord) VALUES (?, ?, ?)').run(name, uid != null ? uid : null, ord);
  return getBoard(info.lastInsertRowid);
}
function renameBoard(id, name) { db.prepare('UPDATE asig_board SET name = ? WHERE id = ?').run(name, id); return getBoard(id); }
const deleteBoard = db.transaction((id) => {
  const ids = db.prepare('SELECT id FROM asig_note WHERE board_id = ?').all(id).map(r => r.id);
  for (const nid of ids) { db.prepare('DELETE FROM asig_note_viewer WHERE note_id = ?').run(nid); db.prepare('DELETE FROM asig_note_seen WHERE note_id = ?').run(nid); }
  db.prepare('DELETE FROM asig_note WHERE board_id = ?').run(id);
  return db.prepare('DELETE FROM asig_board WHERE id = ?').run(id).changes > 0;
});

function getNote(id) { return db.prepare('SELECT * FROM asig_note WHERE id = ?').get(id) || null; }
function noteViewers(noteId) { return db.prepare('SELECT user_id FROM asig_note_viewer WHERE note_id = ? ORDER BY user_id').all(noteId).map(r => r.user_id); }
// Can this user see the note (visibility rule)?
function canSeeNote(note, uid) {
  if (!note) return false;
  if (note.author_id === uid) return true;
  if (note.visibility === 'todos') return true;
  if (note.visibility === 'personalizada') return noteViewers(note.id).includes(uid);
  return false;
}
// Notes of a board visible to the user, decorated with viewer_ids + is_new.
function listNotes(boardId, uid) {
  const rows = db.prepare(`SELECT n.*, (NOT EXISTS (SELECT 1 FROM asig_note_seen s WHERE s.note_id = n.id AND s.user_id = @uid)) AS is_new
     FROM asig_note n WHERE n.board_id = @board AND ${VIS_WHERE} ORDER BY n.id`).all({ board: boardId, uid });
  return rows.map(n => ({ ...n, is_new: !!n.is_new, viewer_ids: n.visibility === 'personalizada' ? noteViewers(n.id) : [] }));
}
function createNote(data, uid) {
  const info = db.prepare(
    `INSERT INTO asig_note (board_id, content, color, pos_x, pos_y, width, height, visibility, author_id, edited_by)
     VALUES (@board_id, @content, @color, @pos_x, @pos_y, @width, @height, @visibility, @author_id, @edited_by)`
  ).run({
    board_id: data.board_id, content: String(data.content || ''), color: cleanNoteColor(data.color),
    pos_x: Number(data.pos_x) || 20, pos_y: Number(data.pos_y) || 20, width: clampW(data.width), height: clampH(data.height),
    visibility: ['todos', 'personalizada'].includes(data.visibility) ? data.visibility : 'privada',
    author_id: uid != null ? uid : null, edited_by: uid != null ? uid : null,
  });
  const note = getNote(info.lastInsertRowid);
  db.prepare('INSERT OR IGNORE INTO asig_note_seen (note_id, user_id) VALUES (?, ?)').run(note.id, uid); // el autor ya la ha "visto"
  return note;
}
// Partial update: only the provided fields change. Sizes/colours are validated.
function updateNote(id, patch, uid) {
  const cur = getNote(id); if (!cur) return null;
  const set = {}, out = [];
  if (patch.content !== undefined) set.content = String(patch.content);
  if (patch.color !== undefined) set.color = cleanNoteColor(patch.color);
  if (patch.pos_x !== undefined) set.pos_x = Math.max(0, Number(patch.pos_x) || 0);
  if (patch.pos_y !== undefined) set.pos_y = Math.max(0, Number(patch.pos_y) || 0);
  if (patch.width !== undefined) set.width = clampW(patch.width);
  if (patch.height !== undefined) set.height = clampH(patch.height);
  if (patch.visibility !== undefined) set.visibility = ['todos', 'personalizada', 'privada'].includes(patch.visibility) ? patch.visibility : cur.visibility;
  if (patch.alert !== undefined) set.alert = patch.alert ? 1 : 0;
  // Una nota privada no tiene destinatarios: el aviso deja de tener sentido.
  if (set.visibility === 'privada') set.alert = 0;
  const keys = Object.keys(set);
  if (keys.length) {
    db.prepare(`UPDATE asig_note SET ${keys.map(k => `${k} = @${k}`).join(', ')}, edited_by = @eb, updated_at = CURRENT_TIMESTAMP WHERE id = @id`).run({ ...set, eb: uid != null ? uid : null, id });
  }
  return getNote(id);
}
function setNoteViewers(noteId, ids) {
  db.prepare('DELETE FROM asig_note_viewer WHERE note_id = ?').run(noteId);
  const ins = db.prepare('INSERT OR IGNORE INTO asig_note_viewer (note_id, user_id) VALUES (?, ?)');
  for (const uid of (ids || [])) if (Number.isInteger(uid)) ins.run(noteId, uid);
  return noteViewers(noteId);
}
const deleteNote = db.transaction((id) => {
  db.prepare('DELETE FROM asig_note_viewer WHERE note_id = ?').run(id);
  db.prepare('DELETE FROM asig_note_seen WHERE note_id = ?').run(id);
  return db.prepare('DELETE FROM asig_note WHERE id = ?').run(id).changes > 0;
});
// Mark every note the user can see (optionally in one board) as seen.
function markNotesSeen(uid, boardId) {
  const where = boardId ? 'AND n.board_id = @board' : '';
  db.prepare(`INSERT OR IGNORE INTO asig_note_seen (note_id, user_id) SELECT n.id, @uid FROM asig_note n WHERE ${VIS_WHERE} ${where}`).run({ uid, board: boardId || 0 });
}
// Notas que otro usuario me ha marcado con aviso y aún no he visto.
// (alert=1, no soy el autor, la puedo ver, y no está marcada como vista por mí.)
const ALERT_WHERE = `n.alert = 1 AND n.author_id IS NOT @uid AND ${VIS_WHERE}
  AND NOT EXISTS (SELECT 1 FROM asig_note_seen s WHERE s.note_id = n.id AND s.user_id = @uid)`;
function pendingAlerts(uid) {
  return db.prepare(
    `SELECT n.id, n.board_id, n.content, n.color, n.author_id, n.updated_at, b.name AS board_name
       FROM asig_note n JOIN asig_board b ON b.id = n.board_id
      WHERE ${ALERT_WHERE} ORDER BY n.updated_at DESC, n.id DESC`
  ).all({ uid });
}
// Re-avisar: el autor "reabre" la nota borrando el visto de los demás y re-activando el aviso.
const repokeNote = db.transaction((noteId, authorId) => {
  db.prepare('DELETE FROM asig_note_seen WHERE note_id = ? AND user_id IS NOT ?').run(noteId, authorId);
  db.prepare('UPDATE asig_note SET alert = 1 WHERE id = ?').run(noteId);
  return getNote(noteId);
});
// Header badge: how many notes the user can see, how many are still new, y cuántas le avisan.
function notesBadge(uid) {
  const total = db.prepare(`SELECT COUNT(*) c FROM asig_note n WHERE ${VIS_WHERE}`).get({ uid }).c;
  const neu = db.prepare(`SELECT COUNT(*) c FROM asig_note n WHERE ${VIS_WHERE} AND NOT EXISTS (SELECT 1 FROM asig_note_seen s WHERE s.note_id = n.id AND s.user_id = @uid)`).get({ uid }).c;
  const alerts = db.prepare(`SELECT COUNT(*) c FROM asig_note n WHERE ${ALERT_WHERE}`).get({ uid }).c;
  return { notes: total, new_notes: neu, alerts };
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
    `INSERT INTO asig_settings (id, ficha_qr_size, ficha_dm_size, notify_mode, updated_by, updated_at)
     VALUES (1, @ficha_qr_size, @ficha_dm_size, @notify_mode, @updated_by, CURRENT_TIMESTAMP)
     ON CONFLICT(id) DO UPDATE SET ficha_qr_size = excluded.ficha_qr_size,
       ficha_dm_size = excluded.ficha_dm_size, notify_mode = excluded.notify_mode,
       updated_by = excluded.updated_by, updated_at = CURRENT_TIMESTAMP`
  ).run({ ficha_qr_size: s.ficha_qr_size, ficha_dm_size: s.ficha_dm_size, notify_mode: s.notify_mode, updated_by: userId != null ? userId : null });
  return getSettings();
}

module.exports = {
  db, DEFAULT_SETTINGS,
  listPlan, plansByCnOrGtin, distinctCnCount, personMedSummary, getPlanLine, planByGtin, planByCn, addPlanMed, upsertPlan, updatePlanById, editPlanMed, reconcilePlanGtin, clearPlanGtin, deletePlanLine, planPersonIds,
  SLOTS, setDoseSchedule, getDoseScheduleForDate, getDoseHistory,
  createEmptyPlan, personsWithPlanSet,
  setPlanRelease, setPlanAdvance, plansForRelease, planForItem, findPendingLineForMed,
  getPeriod, findPeriod, getOrCreatePeriod, listPeriods, latestPeriod, setPeriodStatus, deletePeriod, periodPersonIds,
  DEFAULT_ADVANCE, clampAdvance, effectiveDate,
  listLines, getLine, findLine, lineByItem, addLine, setLineState, setLineRelease, setLineAdvance, pendingReleaseLines, deleteLine, periodCounts,
  getPrecinto, listPrecinto, addPrecinto, deletePrecinto, precintoCountByPlan, nextMonthSameDay,
  assignedLinesForYm, precintosForYm, stickerMonths, setLinePegado, setPrecintoPegado,
  addEvidencia, getEvidencia, listEvidencia,
  getEntNote, setEntNote, entNotesMap,
  cartIds, cartAdd, cartRemove, cartClear,
  listNotifs, getNotif, createNotif, updateNotif, deleteNotif, setNotifEnabled, markNotifSent, dueNotifs,
  NOTE_COLORS, listBoards, getBoard, boardCount, createBoard, renameBoard, deleteBoard,
  getNote, listNotes, createNote, updateNote, deleteNote, noteViewers, setNoteViewers, canSeeNote, markNotesSeen, notesBadge,
  pendingAlerts, repokeNote,
  getSettings, saveSettings,
};
