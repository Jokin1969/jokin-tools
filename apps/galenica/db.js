'use strict';

// ── Galénica database (SEPARATE, self-contained) ─────────────────────────────────
// A medication REFERENCE catalogue — what a medication IS and looks like — not an
// inventory of physical boxes (that's Data Matrix) and not a person's plan (that's
// Asignación). One row per Código Nacional. Name/principio activo/forma/laboratorio
// come from CIMA (best-effort, offline-tolerant, cached — see cima-cache.js in
// Data Matrix, reused here); colour is NOT available from CIMA and is always
// entered by hand. The pill photo itself is NOT stored here: it's the shared
// repository at apps/pastillero/pill-images/, referenced by the same CN.

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.GALENICA_DB_PATH || '/data/galenica.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS galenica_med (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cn             TEXT NOT NULL UNIQUE,   -- Código Nacional (natural key)
    gtin           TEXT,                   -- derived from cn
    barcode        TEXT,                   -- derived from cn (EAN-13)
    nombre         TEXT,
    pactivos       TEXT,                   -- principio(s) activo(s) — CIMA
    forma          TEXT,                   -- forma farmacéutica — CIMA (comprimido, cápsula…)
    color          TEXT,                   -- SIEMPRE manual: CIMA no lo da
    labtitular     TEXT,
    comercializado INTEGER,                -- 0/1/NULL (desconocido)
    notes          TEXT,
    created_by     INTEGER,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE INDEX IF NOT EXISTS idx_galenica_nombre ON galenica_med(nombre);
`);

function listMeds() {
  return db.prepare('SELECT * FROM galenica_med ORDER BY nombre COLLATE NOCASE, cn').all();
}
function getMed(id) { return db.prepare('SELECT * FROM galenica_med WHERE id = ?').get(id) || null; }
function getByCn(cn) { return db.prepare('SELECT * FROM galenica_med WHERE cn = ?').get(String(cn || '')) || null; }

// Distinct non-empty values, for the quick-filter chips (forma/color already in use).
function distinctFormas() { return db.prepare("SELECT DISTINCT forma FROM galenica_med WHERE forma IS NOT NULL AND forma <> '' ORDER BY forma COLLATE NOCASE").all().map(r => r.forma); }
function distinctColors() { return db.prepare("SELECT DISTINCT color FROM galenica_med WHERE color IS NOT NULL AND color <> '' ORDER BY color COLLATE NOCASE").all().map(r => r.color); }

const cleanStr = (v, max) => { const s = v == null ? '' : String(v).trim(); return s ? s.slice(0, max || 300) : null; };

// Create (or update, if the CN already exists) from CIMA-shaped data + optional
// manual fields (colour, notes). CIMA-sourced fields only overwrite when a new
// non-empty value arrives (COALESCE), so a manual correction never gets clobbered
// by a stale re-fetch — same pattern as the DM/CIMA cache.
function upsertFromCima(cn, data, userId) {
  const row = {
    cn: String(cn), gtin: data.gtin || null, barcode: data.barcode || null,
    nombre: cleanStr(data.nombre, 300), pactivos: cleanStr(data.pactivos, 500),
    forma: cleanStr(data.forma, 120), labtitular: cleanStr(data.labtitular, 200),
    comercializado: data.comercializado == null ? null : (data.comercializado ? 1 : 0),
    created_by: userId != null ? userId : null,
  };
  db.prepare(
    `INSERT INTO galenica_med (cn, gtin, barcode, nombre, pactivos, forma, labtitular, comercializado, created_by, updated_at)
     VALUES (@cn, @gtin, @barcode, @nombre, @pactivos, @forma, @labtitular, @comercializado, @created_by, CURRENT_TIMESTAMP)
     ON CONFLICT(cn) DO UPDATE SET
       gtin = COALESCE(excluded.gtin, galenica_med.gtin),
       barcode = COALESCE(excluded.barcode, galenica_med.barcode),
       nombre = COALESCE(excluded.nombre, galenica_med.nombre),
       pactivos = COALESCE(excluded.pactivos, galenica_med.pactivos),
       forma = COALESCE(excluded.forma, galenica_med.forma),
       labtitular = COALESCE(excluded.labtitular, galenica_med.labtitular),
       comercializado = COALESCE(excluded.comercializado, galenica_med.comercializado),
       updated_at = CURRENT_TIMESTAMP`
  ).run(row);
  return getByCn(cn);
}
// Manual edit: colour, notes, and (rarely) a correction to a CIMA-sourced field.
// Unlike upsertFromCima this OVERWRITES with exactly what's given (undefined = leave
// alone, empty string = clear) — a human editing the form means it, no COALESCE.
function updateMed(id, data) {
  const cur = getMed(id); if (!cur) return null;
  const pick = (key, max) => data[key] !== undefined ? cleanStr(data[key], max) : cur[key];
  db.prepare(
    `UPDATE galenica_med SET nombre=@nombre, pactivos=@pactivos, forma=@forma, color=@color,
       labtitular=@labtitular, notes=@notes, updated_at=CURRENT_TIMESTAMP WHERE id=@id`
  ).run({
    id, nombre: pick('nombre', 300), pactivos: pick('pactivos', 500), forma: pick('forma', 120),
    color: pick('color', 120), labtitular: pick('labtitular', 200), notes: pick('notes', 1000),
  });
  return getMed(id);
}
function deleteMed(id) { db.prepare('DELETE FROM galenica_med WHERE id = ?').run(id); }

module.exports = {
  db, listMeds, getMed, getByCn, distinctFormas, distinctColors, upsertFromCima, updateMed, deleteMed,
};
