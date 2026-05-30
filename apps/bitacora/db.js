const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

// Bitácora shares the same SQLite file as the rest of the hub, so a single
// .db backup captures every app's data at once.
const DB_PATH = process.env.DB_PATH || '/data/jokin_tools.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// ─── Schema ───────────────────────────────────────────────────────────────────
// A personal log of memory-related events ("lapsus") the user wants to record
// while lucid, to look back on objectively over time.
db.exec(`
  CREATE TABLE IF NOT EXISTS bitacora (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER,
    fecha         TEXT NOT NULL,                       -- YYYY-MM-DD del hecho
    lugar         TEXT,
    hecho         TEXT NOT NULL,
    nivel         TEXT NOT NULL DEFAULT 'Bajo' CHECK(nivel IN ('Bajo','Medio','Alto')),
    categoria     TEXT,
    como          TEXT,                                -- cómo me di cuenta
    factores      TEXT,                                -- CSV de factores del momento
    notado_otros  INTEGER NOT NULL DEFAULT 0,          -- 0/1 ¿lo notó otra persona?
    notado_quien  TEXT,
    comentario    TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE INDEX IF NOT EXISTS idx_bitacora_user  ON bitacora(user_id);
  CREATE INDEX IF NOT EXISTS idx_bitacora_fecha ON bitacora(fecha);
`);

console.log('[bitacora] Table ready at:', DB_PATH);

// ─── Reference data (kept here so the API can serve it to the UI) ──────────────
const NIVELES = ['Bajo', 'Medio', 'Alto'];
const CATEGORIAS = [
  'Olvido reciente',
  'Repetición',
  'Objeto extraviado',
  'Desorientación',
  'Falso recuerdo',
  'Palabra o nombre',
  'Confusión de datos',
  'Otro',
];
const FACTORES = [
  'Cansancio', 'Falta de sueño', 'Estrés', 'Prisa',
  'Alcohol', 'Enfermedad o fiebre', 'Medicación',
];

// CSV of factors → clean array limited to the known set.
function normFactores(value) {
  const list = Array.isArray(value) ? value : String(value || '').split(',');
  const clean = list.map(s => String(s).trim()).filter(f => FACTORES.includes(f));
  return [...new Set(clean)].join(',');
}

function normNivel(value) {
  return NIVELES.includes(value) ? value : 'Bajo';
}

// ─── CRUD (all scoped by user_id when provided) ─────────────────────────────────
function createEntry(fields, userId = null) {
  const stmt = db.prepare(`
    INSERT INTO bitacora (user_id, fecha, lugar, hecho, nivel, categoria, como, factores, notado_otros, notado_quien, comentario)
    VALUES (@user_id, @fecha, @lugar, @hecho, @nivel, @categoria, @como, @factores, @notado_otros, @notado_quien, @comentario)
  `);
  const info = stmt.run({
    user_id: userId,
    fecha: fields.fecha,
    lugar: fields.lugar || null,
    hecho: fields.hecho,
    nivel: normNivel(fields.nivel),
    categoria: fields.categoria || null,
    como: fields.como || null,
    factores: normFactores(fields.factores),
    notado_otros: fields.notado_otros ? 1 : 0,
    notado_quien: fields.notado_otros ? (fields.notado_quien || null) : null,
    comentario: fields.comentario || null,
  });
  return getEntryById(info.lastInsertRowid, userId);
}

function getEntryById(id, userId) {
  return userId != null
    ? db.prepare('SELECT * FROM bitacora WHERE id = ? AND user_id = ?').get(id, userId)
    : db.prepare('SELECT * FROM bitacora WHERE id = ?').get(id);
}

const UPDATABLE = ['fecha', 'lugar', 'hecho', 'nivel', 'categoria', 'como', 'factores', 'notado_otros', 'notado_quien', 'comentario'];

function updateEntry(id, fields, userId) {
  const updates = [];
  const values = [];
  for (const [k, v] of Object.entries(fields)) {
    if (!UPDATABLE.includes(k)) continue;
    let val = v;
    if (k === 'nivel') val = normNivel(v);
    else if (k === 'factores') val = normFactores(v);
    else if (k === 'notado_otros') val = v ? 1 : 0;
    updates.push(`${k} = ?`);
    values.push(val);
  }
  if (!updates.length) return getEntryById(id, userId);
  values.push(id);
  let where = 'id = ?';
  if (userId != null) { where += ' AND user_id = ?'; values.push(userId); }
  db.prepare(`UPDATE bitacora SET ${updates.join(', ')} WHERE ${where}`).run(...values);
  return getEntryById(id, userId);
}

function deleteEntry(id, userId) {
  const where = userId != null ? 'id = ? AND user_id = ?' : 'id = ?';
  const args = userId != null ? [id, userId] : [id];
  return db.prepare(`DELETE FROM bitacora WHERE ${where}`).run(...args).changes > 0;
}

// ─── List with powerful search & filters ───────────────────────────────────────
function listEntries({ search, nivel, categoria, date_from, date_to, factores, notado, sort, order, page = 1, limit = 100 } = {}, userId) {
  const conditions = [];
  const params = [];

  if (userId != null) { conditions.push('user_id = ?'); params.push(userId); }

  // Free-text search across every text column.
  if (search && search.trim()) {
    const term = `%${search.trim()}%`;
    conditions.push('(hecho LIKE ? OR comentario LIKE ? OR lugar LIKE ? OR como LIKE ? OR categoria LIKE ? OR notado_quien LIKE ?)');
    params.push(term, term, term, term, term, term);
  }
  if (nivel) {
    const list = Array.isArray(nivel) ? nivel : nivel.split(',');
    const clean = list.filter(n => NIVELES.includes(n));
    if (clean.length) { conditions.push(`nivel IN (${clean.map(() => '?').join(',')})`); params.push(...clean); }
  }
  if (categoria) {
    const list = Array.isArray(categoria) ? categoria : categoria.split(',');
    if (list.length) { conditions.push(`categoria IN (${list.map(() => '?').join(',')})`); params.push(...list); }
  }
  if (date_from) { conditions.push('fecha >= ?'); params.push(date_from); }
  if (date_to)   { conditions.push('fecha <= ?'); params.push(date_to); }
  // Match any of the requested factors (substring against the CSV).
  if (factores) {
    const list = Array.isArray(factores) ? factores : factores.split(',');
    const clean = list.map(s => s.trim()).filter(Boolean);
    if (clean.length) {
      conditions.push('(' + clean.map(() => 'factores LIKE ?').join(' OR ') + ')');
      params.push(...clean.map(f => `%${f}%`));
    }
  }
  if (notado === '1' || notado === 1 || notado === true) { conditions.push('notado_otros = 1'); }

  const whereClause = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';

  const sortMap = { fecha: 'fecha', created_at: 'created_at', nivel: 'nivel', categoria: 'categoria', id: 'id' };
  const sortCol = sortMap[sort] || 'fecha';
  const sortDir = order === 'asc' ? 'ASC' : 'DESC';
  // Stable secondary sort so same-date rows keep a deterministic order.
  const orderClause = `ORDER BY ${sortCol} ${sortDir}, id ${sortDir}`;

  const lim = Math.min(Math.max(Number(limit) || 100, 1), 500);
  const offset = (Math.max(Number(page) || 1, 1) - 1) * lim;

  const rows = db.prepare(`SELECT * FROM bitacora ${whereClause} ${orderClause} LIMIT ? OFFSET ?`).all(...params, lim, offset);
  const { total } = db.prepare(`SELECT COUNT(*) AS total FROM bitacora ${whereClause}`).get(...params);

  return { rows, total, page: Math.max(Number(page) || 1, 1), limit: lim };
}

// Ordered ids for client-side prev/next navigation in the detail view.
function getAllIds(sort = 'fecha', order = 'desc', userId) {
  const sortMap = { fecha: 'fecha', created_at: 'created_at', nivel: 'nivel', categoria: 'categoria', id: 'id' };
  const col = sortMap[sort] || 'fecha';
  const dir = order === 'asc' ? 'ASC' : 'DESC';
  const where = userId != null ? 'WHERE user_id = ?' : '';
  const q = `SELECT id FROM bitacora ${where} ORDER BY ${col} ${dir}, id ${dir}`;
  const rows = userId != null ? db.prepare(q).all(userId) : db.prepare(q).all();
  return rows.map(r => r.id);
}

// ─── Summary stats (for the dashboard header) ──────────────────────────────────
function getStats(userId) {
  const where = userId != null ? 'WHERE user_id = ?' : '';
  const args = userId != null ? [userId] : [];
  const total = db.prepare(`SELECT COUNT(*) AS n FROM bitacora ${where}`).get(...args).n;
  const byNivel = {};
  for (const n of NIVELES) {
    const w = userId != null ? 'WHERE user_id = ? AND nivel = ?' : 'WHERE nivel = ?';
    const a = userId != null ? [userId, n] : [n];
    byNivel[n] = db.prepare(`SELECT COUNT(*) AS n FROM bitacora ${w}`).get(...a).n;
  }
  return { total, byNivel };
}

// ─── Export ─────────────────────────────────────────────────────────────────────
function getAllForExport(userId) {
  const where = userId != null ? 'WHERE user_id = ?' : '';
  const q = `SELECT id, fecha, lugar, hecho, nivel, categoria, como, factores, notado_otros, notado_quien, comentario, created_at FROM bitacora ${where} ORDER BY fecha DESC, id DESC`;
  return userId != null ? db.prepare(q).all(userId) : db.prepare(q).all();
}

// ─── Per-user ownership helpers (mirror re-memory) ─────────────────────────────
function assignOrphans(userId) {
  return db.prepare('UPDATE bitacora SET user_id = ? WHERE user_id IS NULL').run(userId).changes;
}
function assignOrphansToConfiguredOwner() {
  const email = (process.env.REMEMORY_OWNER_EMAIL || process.env.ADMIN_EMAIL || '').trim().toLowerCase();
  if (!email) return 0;
  const row = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
  return row ? assignOrphans(row.id) : 0;
}

module.exports = {
  db,
  NIVELES, CATEGORIAS, FACTORES,
  createEntry, getEntryById, updateEntry, deleteEntry,
  listEntries, getAllIds, getStats, getAllForExport,
  assignOrphans, assignOrphansToConfiguredOwner,
};
