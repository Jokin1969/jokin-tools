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
`);

// Lightweight migration for DBs created before the release date existed.
try { db.prepare('ALTER TABLE asig_line ADD COLUMN release_at TEXT').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE asig_settings ADD COLUMN notify_mode TEXT').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE asig_note ADD COLUMN alert INTEGER NOT NULL DEFAULT 0').run(); } catch { /* already present */ }

console.log('[asignacion] Database ready at:', DB_PATH);

// notify_mode: how the release bell groups a person's pending boxes —
//   'all' (ready when ALL are out), 'any' (ready when any is out), 'box' (per box).
const DEFAULT_SETTINGS = { ficha_qr_size: 300, ficha_dm_size: 150, notify_mode: 'all' };

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
  listPlan, getPlanLine, planByGtin, upsertPlan, deletePlanLine, planPersonIds,
  getPeriod, findPeriod, getOrCreatePeriod, listPeriods, latestPeriod, setPeriodStatus, deletePeriod, periodPersonIds,
  listLines, getLine, findLine, lineByItem, addLine, setLineState, setLineRelease, pendingReleaseLines, deleteLine, periodCounts,
  listNotifs, getNotif, createNotif, updateNotif, deleteNotif, setNotifEnabled, markNotifSent, dueNotifs,
  NOTE_COLORS, listBoards, getBoard, boardCount, createBoard, renameBoard, deleteBoard,
  getNote, listNotes, createNote, updateNote, deleteNote, noteViewers, setNoteViewers, canSeeNote, markNotesSeen, notesBadge,
  pendingAlerts, repokeNote,
  getSettings, saveSettings,
};
