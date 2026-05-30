const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.DB_PATH || '/data/jokin_tools.db';

// Ensure parent directory exists
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) {
  fs.mkdirSync(dbDir, { recursive: true });
}

const db = new Database(DB_PATH);

// Enable WAL mode for better concurrency
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// ─── Schema ───────────────────────────────────────────────────────────────────
db.exec(`
  CREATE TABLE IF NOT EXISTS memories (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    description    TEXT NOT NULL,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    times_recalled INTEGER DEFAULT 0,
    frequency      TEXT NOT NULL CHECK(frequency IN ('1w','2w','3w','1m','2m','3m','6m','1y')),
    topic          TEXT NOT NULL,
    image_path     TEXT,
    source_url     TEXT,
    active         INTEGER DEFAULT 1,
    next_send_date DATETIME,
    last_sent_date DATETIME
  );

  CREATE TABLE IF NOT EXISTS recall_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id  INTEGER NOT NULL,
    sent_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (memory_id) REFERENCES memories(id)
  );
`);

console.log('[db] Database initialized at:', DB_PATH);

// ─── Migration: per-user ownership ──────────────────────────────────────────────
// Each memory belongs to one user. Older databases predate this column, so add
// it on the fly. Orphan rows (user_id IS NULL) are assigned to an owner at boot
// (see assignOrphanMemories, called from server.js after the admin is seeded).
const memCols = db.prepare('PRAGMA table_info(memories)').all().map(c => c.name);
if (!memCols.includes('user_id')) {
  db.exec('ALTER TABLE memories ADD COLUMN user_id INTEGER');
  console.log('[db] Migrated: added memories.user_id');
}
db.exec('CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)');

// ─── Helpers ──────────────────────────────────────────────────────────────────

const FREQUENCY_DAYS = {
  '1w': 7, '2w': 14, '3w': 21,
  '1m': 30, '2m': 60, '3m': 90,
  '6m': 180, '1y': 365
};

function calcNextSendDate(frequency, fromDate = new Date()) {
  const base = new Date(fromDate);
  const days = FREQUENCY_DAYS[frequency];
  if (!days) throw new Error(`Invalid frequency: ${frequency}`);
  const randomOffset = Math.floor(Math.random() * 7) - 3; // -3 to +3 days
  base.setDate(base.getDate() + days + randomOffset);
  // Set to 07:00 Madrid time — store as UTC-adjusted ISO string
  // We store the target as a local wall-clock string; cron runs in Madrid tz
  base.setHours(7, 0, 0, 0);
  return base.toISOString();
}

// ─── Memories CRUD ────────────────────────────────────────────────────────────

function createMemory({ description, frequency, topic, image_path, source_url, active = 1, user_id = null }) {
  const nextSend = calcNextSendDate(frequency);
  const stmt = db.prepare(`
    INSERT INTO memories (description, frequency, topic, image_path, source_url, active, next_send_date, user_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);
  const result = stmt.run(description, frequency, topic, image_path || null, source_url || null, active, nextSend, user_id);
  return getMemoryById(result.lastInsertRowid);
}

// When userId is provided, the lookup is scoped to that owner (returns null if
// the memory exists but belongs to someone else).
function getMemoryById(id, userId) {
  const memory = userId != null
    ? db.prepare('SELECT * FROM memories WHERE id = ? AND user_id = ?').get(id, userId)
    : db.prepare('SELECT * FROM memories WHERE id = ?').get(id);
  if (!memory) return null;
  // Attach real times_recalled from recall_log
  const { count } = db.prepare('SELECT COUNT(*) as count FROM recall_log WHERE memory_id = ?').get(id);
  memory.times_recalled = count;
  return memory;
}

function listMemories({ topic, active, frequency, date_from, date_to, recalled_min, recalled_max, search, sort, order, page = 1, limit = 100 } = {}, userId) {
  const conditions = [];
  const params = [];

  if (userId != null) {
    conditions.push('m.user_id = ?');
    params.push(userId);
  }

  if (search && search.trim()) {
    conditions.push(`(m.description LIKE ? OR m.topic LIKE ? OR m.source_url LIKE ?)`);
    const term = `%${search.trim()}%`;
    params.push(term, term, term);
  }

  if (topic) {
    const topics = Array.isArray(topic) ? topic : topic.split(',');
    conditions.push(`m.topic IN (${topics.map(() => '?').join(',')})`);
    params.push(...topics);
  }
  if (active !== undefined && active !== '') {
    conditions.push('m.active = ?');
    params.push(Number(active));
  }
  if (frequency) {
    const freqs = Array.isArray(frequency) ? frequency : frequency.split(',');
    conditions.push(`m.frequency IN (${freqs.map(() => '?').join(',')})`);
    params.push(...freqs);
  }
  if (date_from) {
    conditions.push('m.created_at >= ?');
    params.push(date_from);
  }
  if (date_to) {
    conditions.push('m.created_at <= ?');
    params.push(date_to + ' 23:59:59');
  }

  const whereClause = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';

  // Allowed sort columns
  const sortMap = {
    created_at: 'm.created_at',
    frequency: 'm.frequency',
    times_recalled: 'times_recalled',
    next_send_date: 'm.next_send_date',
    topic: 'm.topic'
  };
  const sortCol = sortMap[sort] || 'm.created_at';
  const sortDir = order === 'asc' ? 'ASC' : 'DESC';

  let havingClause = '';
  if (recalled_min !== undefined && recalled_min !== '') {
    havingClause += `HAVING times_recalled >= ${Number(recalled_min)}`;
  }
  if (recalled_max !== undefined && recalled_max !== '') {
    havingClause += havingClause
      ? ` AND times_recalled <= ${Number(recalled_max)}`
      : `HAVING times_recalled <= ${Number(recalled_max)}`;
  }

  const offset = (Number(page) - 1) * Number(limit);

  const rows = db.prepare(`
    SELECT m.*, (SELECT COUNT(*) FROM recall_log r WHERE r.memory_id = m.id) as times_recalled
    FROM memories m
    ${whereClause}
    ${havingClause}
    ORDER BY ${sortCol} ${sortDir}
    LIMIT ? OFFSET ?
  `).all(...params, Number(limit), offset);

  const { total } = db.prepare(`
    SELECT COUNT(*) as total FROM (
      SELECT m.id, (SELECT COUNT(*) FROM recall_log r WHERE r.memory_id = m.id) as times_recalled
      FROM memories m
      ${whereClause}
      ${havingClause}
    )
  `).get(...params);

  return { rows, total, page: Number(page), limit: Number(limit) };
}

function updateMemory(id, fields, userId) {
  const allowed = ['description', 'frequency', 'topic', 'image_path', 'source_url', 'active', 'next_send_date'];
  const updates = [];
  const values = [];

  for (const [k, v] of Object.entries(fields)) {
    if (allowed.includes(k)) {
      updates.push(`${k} = ?`);
      values.push(v);
    }
  }
  if (!updates.length) return getMemoryById(id, userId);

  // Recalculate next_send_date if frequency changed (and not explicitly provided)
  if (fields.frequency && !fields.next_send_date) {
    updates.push('next_send_date = ?');
    values.push(calcNextSendDate(fields.frequency));
  }

  values.push(id);
  let where = 'id = ?';
  if (userId != null) { where += ' AND user_id = ?'; values.push(userId); }
  db.prepare(`UPDATE memories SET ${updates.join(', ')} WHERE ${where}`).run(...values);
  return getMemoryById(id, userId);
}

function deleteMemory(id, userId) {
  // Guard ownership before removing recall_log rows.
  if (userId != null && !db.prepare('SELECT 1 FROM memories WHERE id = ? AND user_id = ?').get(id, userId)) return;
  db.prepare('DELETE FROM recall_log WHERE memory_id = ?').run(id);
  const where = userId != null ? 'id = ? AND user_id = ?' : 'id = ?';
  db.prepare(`DELETE FROM memories WHERE ${where}`).run(...(userId != null ? [id, userId] : [id]));
}

function toggleMemory(id, userId) {
  const where = userId != null ? 'id = ? AND user_id = ?' : 'id = ?';
  db.prepare(`UPDATE memories SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END WHERE ${where}`)
    .run(...(userId != null ? [id, userId] : [id]));
  return getMemoryById(id, userId);
}

// ─── Recall log & scheduling ──────────────────────────────────────────────────

function getMemoriesDueToday() {
  // Join the owner so the cron can email each memory to its own user. Memories
  // whose owner is missing or deactivated are skipped.
  return db.prepare(`
    SELECT m.*, u.email AS owner_email
    FROM memories m
    JOIN users u ON u.id = m.user_id
    WHERE m.active = 1 AND u.active = 1 AND m.next_send_date <= datetime('now')
  `).all();
}

function markSent(id, frequency) {
  const now = new Date().toISOString();
  db.prepare('INSERT INTO recall_log (memory_id) VALUES (?)').run(id);
  const { count } = db.prepare('SELECT COUNT(*) as count FROM recall_log WHERE memory_id = ?').get(id);
  const nextSend = calcNextSendDate(frequency);
  db.prepare(`
    UPDATE memories
    SET times_recalled = ?, last_sent_date = ?, next_send_date = ?
    WHERE id = ?
  `).run(count, now, nextSend, id);
}

// ─── Navigation: all IDs in order ─────────────────────────────────────────────

function getAllIds(sort = 'created_at', order = 'desc', userId) {
  const sortMap = { created_at: 'created_at', id: 'id', topic: 'topic' };
  const col = sortMap[sort] || 'created_at';
  const dir = order === 'asc' ? 'ASC' : 'DESC';
  const where = userId != null ? 'WHERE user_id = ?' : '';
  const q = `SELECT id FROM memories ${where} ORDER BY ${col} ${dir}`;
  const rows = userId != null ? db.prepare(q).all(userId) : db.prepare(q).all();
  return rows.map(r => r.id);
}

// ─── Reset counter ────────────────────────────────────────────────────────────

function resetCounter(id, userId) {
  if (userId != null && !db.prepare('SELECT 1 FROM memories WHERE id = ? AND user_id = ?').get(id, userId)) return null;
  db.prepare('DELETE FROM recall_log WHERE memory_id = ?').run(id);
  db.prepare('UPDATE memories SET times_recalled = 0 WHERE id = ?').run(id);
  // Recalculate next_send_date from now
  const memory = db.prepare('SELECT frequency FROM memories WHERE id = ?').get(id);
  if (memory) {
    const nextSend = calcNextSendDate(memory.frequency);
    db.prepare('UPDATE memories SET next_send_date = ? WHERE id = ?').run(nextSend, id);
  }
  return getMemoryById(id, userId);
}

// Assign every ownerless memory (pre-migration data) to a user. Returns count.
function assignOrphanMemories(userId) {
  return db.prepare('UPDATE memories SET user_id = ? WHERE user_id IS NULL').run(userId).changes;
}

// Owner (user_id) of the memory that uses this uploaded image filename, or null
// if no memory references it. Used to gate /uploads access per user.
function getImageOwner(filename) {
  const row = db.prepare('SELECT user_id FROM memories WHERE image_path = ?').get(filename);
  return row ? row.user_id : null;
}

// ─── CSV export ───────────────────────────────────────────────────────────────

function getAllMemoriesForExport(userId) {
  const where = userId != null ? 'WHERE m.user_id = ?' : '';
  const q = `
    SELECT
      m.id, m.description, m.created_at, m.frequency, m.topic,
      CASE WHEN m.image_path IS NOT NULL THEN 'true' ELSE 'false' END as has_image,
      m.source_url, m.active, m.next_send_date, m.last_sent_date,
      (SELECT COUNT(*) FROM recall_log r WHERE r.memory_id = m.id) as times_recalled
    FROM memories m
    ${where}
    ORDER BY m.created_at DESC
  `;
  return userId != null ? db.prepare(q).all(userId) : db.prepare(q).all();
}

module.exports = {
  db,
  calcNextSendDate,
  createMemory,
  getMemoryById,
  listMemories,
  getAllIds,
  updateMemory,
  deleteMemory,
  toggleMemory,
  getMemoriesDueToday,
  markSent,
  resetCounter,
  getAllMemoriesForExport,
  assignOrphanMemories,
  getImageOwner,
  FREQUENCY_DAYS
};
