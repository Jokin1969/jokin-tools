'use strict';

// ── "Preguntar a un PDF" repository (persistent) ────────────────────────────────
// A digested PDF is stored as: one row in pdfqa_docs (metadata + processing
// status) plus many rows in pdfqa_chunks (a slice of text + its embedding vector
// stored as a raw Float32 BLOB). Everything lives in the shared SQLite file on the
// /data volume so digested documents survive redeploys. Scoped per user.
//
// A 3000-page book produces a few thousand chunks; the embeddings BLOBs dominate
// the size (~6 KB per chunk for text-embedding-3-small's 1536 dims).

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.DB_PATH || '/data/jokin_tools.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS pdfqa_docs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER,
    name         TEXT NOT NULL,
    pages        INTEGER DEFAULT 0,
    chunks       INTEGER DEFAULT 0,
    bytes        INTEGER DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'processing',  -- processing | ready | error
    progress     TEXT,                                -- JSON {phase,current,total,message}
    warning      TEXT,                                -- e.g. "parece escaneado"
    error        TEXT,
    model        TEXT,                                -- embedding model used
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE INDEX IF NOT EXISTS idx_pdfqa_docs_user ON pdfqa_docs(user_id);

  CREATE TABLE IF NOT EXISTS pdfqa_chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      INTEGER NOT NULL,
    idx         INTEGER NOT NULL,
    page_start  INTEGER NOT NULL,
    page_end    INTEGER NOT NULL,
    text        TEXT NOT NULL,
    embedding   BLOB,
    FOREIGN KEY (doc_id) REFERENCES pdfqa_docs(id) ON DELETE CASCADE
  );
  CREATE INDEX IF NOT EXISTS idx_pdfqa_chunks_doc ON pdfqa_chunks(doc_id);
`);

console.log('[batchwork/pdfqa] Repository ready at:', DB_PATH);

// ── Docs ────────────────────────────────────────────────────────────────────────
function createDoc({ name, bytes, model }, userId = null) {
  const info = db.prepare(
    `INSERT INTO pdfqa_docs (user_id, name, bytes, model, status, progress)
     VALUES (@user_id, @name, @bytes, @model, 'processing', @progress)`
  ).run({
    user_id: userId,
    name: String(name || 'documento.pdf').slice(0, 200),
    bytes: bytes || 0,
    model: model || null,
    progress: JSON.stringify({ phase: 'queued', current: 0, total: 0, message: 'En cola…' }),
  });
  return getDoc(info.lastInsertRowid, userId);
}

function getDoc(id, userId) {
  const row = userId != null
    ? db.prepare('SELECT * FROM pdfqa_docs WHERE id = ? AND user_id = ?').get(id, userId)
    : db.prepare('SELECT * FROM pdfqa_docs WHERE id = ?').get(id);
  if (!row) return null;
  let progress = null;
  try { progress = row.progress ? JSON.parse(row.progress) : null; } catch { /* ignore */ }
  return {
    id: row.id, name: row.name, pages: row.pages, chunks: row.chunks, bytes: row.bytes,
    status: row.status, progress, warning: row.warning, error: row.error,
    model: row.model, created_at: row.created_at,
  };
}

function listDocs(userId) {
  const where = userId != null ? 'WHERE user_id = ?' : '';
  const args = userId != null ? [userId] : [];
  return db.prepare(
    `SELECT id, name, pages, chunks, bytes, status, progress, warning, error, created_at
       FROM pdfqa_docs ${where} ORDER BY created_at DESC, id DESC`
  ).all(...args).map(row => {
    let progress = null;
    try { progress = row.progress ? JSON.parse(row.progress) : null; } catch { /* ignore */ }
    return { ...row, progress };
  });
}

function updateProgress(id, progress) {
  db.prepare('UPDATE pdfqa_docs SET progress = ? WHERE id = ?')
    .run(JSON.stringify(progress || {}), id);
}

function setPages(id, pages) {
  db.prepare('UPDATE pdfqa_docs SET pages = ? WHERE id = ?').run(pages, id);
}

function setWarning(id, warning) {
  db.prepare('UPDATE pdfqa_docs SET warning = ? WHERE id = ?').run(warning || null, id);
}

function markReady(id, { chunks }) {
  db.prepare(
    `UPDATE pdfqa_docs SET status = 'ready', chunks = ?,
       progress = ? WHERE id = ?`
  ).run(chunks, JSON.stringify({ phase: 'ready', current: chunks, total: chunks, message: 'Listo' }), id);
}

function markError(id, message) {
  db.prepare(
    `UPDATE pdfqa_docs SET status = 'error', error = ?,
       progress = ? WHERE id = ?`
  ).run(String(message || 'Error').slice(0, 500),
        JSON.stringify({ phase: 'error', message: String(message || 'Error').slice(0, 200) }), id);
}

function removeDoc(id, userId) {
  const where = userId != null ? 'id = ? AND user_id = ?' : 'id = ?';
  const args = userId != null ? [id, userId] : [id];
  const doc = getDoc(id, userId);
  if (!doc) return false;
  db.prepare('DELETE FROM pdfqa_chunks WHERE doc_id = ?').run(id);
  return db.prepare(`DELETE FROM pdfqa_docs WHERE ${where}`).run(...args).changes > 0;
}

// ── Chunks ──────────────────────────────────────────────────────────────────────
// Embeddings are stored as raw little-endian Float32 BLOBs (Buffer of the
// Float32Array). This is compact and lets us reconstruct the vector cheaply for
// cosine similarity at query time.
function embeddingToBlob(vec) {
  return Buffer.from(Float32Array.from(vec).buffer);
}
function blobToEmbedding(buf) {
  // Copy into a fresh aligned buffer to be safe about byteOffset alignment.
  return new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
}

const insertChunkStmt = db.prepare(
  `INSERT INTO pdfqa_chunks (doc_id, idx, page_start, page_end, text, embedding)
   VALUES (@doc_id, @idx, @page_start, @page_end, @text, @embedding)`
);

// Insert a batch of chunks (each: {idx, pageStart, pageEnd, text, embedding[]}).
const insertChunks = db.transaction((docId, chunks) => {
  for (const c of chunks) {
    insertChunkStmt.run({
      doc_id: docId,
      idx: c.idx,
      page_start: c.pageStart,
      page_end: c.pageEnd,
      text: c.text,
      embedding: c.embedding ? embeddingToBlob(c.embedding) : null,
    });
  }
});

function countChunks(docId) {
  return db.prepare('SELECT COUNT(*) AS n FROM pdfqa_chunks WHERE doc_id = ?').get(docId).n;
}

// Load every chunk's embedding for a doc (used for the cosine search). Returns
// [{id, idx, pageStart, pageEnd, embedding:Float32Array}]. Text is loaded
// separately (only for the winning chunks) to keep this lean.
function loadEmbeddings(docId) {
  const rows = db.prepare(
    'SELECT id, idx, page_start, page_end, embedding FROM pdfqa_chunks WHERE doc_id = ?'
  ).all(docId);
  return rows.map(r => ({
    id: r.id, idx: r.idx, pageStart: r.page_start, pageEnd: r.page_end,
    embedding: r.embedding ? blobToEmbedding(r.embedding) : null,
  }));
}

function getChunkTexts(ids) {
  if (!ids.length) return {};
  const placeholders = ids.map(() => '?').join(',');
  const rows = db.prepare(
    `SELECT id, idx, page_start, page_end, text FROM pdfqa_chunks WHERE id IN (${placeholders})`
  ).all(...ids);
  const map = {};
  for (const r of rows) map[r.id] = { idx: r.idx, pageStart: r.page_start, pageEnd: r.page_end, text: r.text };
  return map;
}

module.exports = {
  db,
  createDoc, getDoc, listDocs, updateProgress, setPages, setWarning,
  markReady, markError, removeDoc,
  insertChunks, countChunks, loadEmbeddings, getChunkTexts,
};
