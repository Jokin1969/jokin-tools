'use strict';

// ── Gestor de códigos Data Matrix — database (SEPARATE, self-contained) ──────────
// Medication boxes identified by their GS1 Data Matrix. Everything lives in its own
// SQLite file (datamatrix.db).
//
//   dm_items    — the scanned boxes (raw + segregated fields, status activo/utilizado)
//   dm_products — GTIN → nombre comercial + colour/shape override (per medication)
//   dm_settings — a single global row of Data Matrix display settings (sizes, bg)
//   dm_cart     — per-user cart

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.DM_DB_PATH || '/data/datamatrix.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS dm_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    raw        TEXT NOT NULL,            -- verbatim Data Matrix content (re-encodable)
    box_key    TEXT,                     -- GTIN|serial (or raw:…) — identity of a box
    gtin       TEXT,
    serial     TEXT,
    lote       TEXT,
    caducidad  TEXT,                     -- ISO YYYY-MM-DD (from AI 17)
    cn         TEXT,                     -- national code (AI 710-714)
    status     TEXT NOT NULL DEFAULT 'activo',   -- 'activo' (sin utilizar) | 'utilizado'
    used_at      DATETIME,
    created_by   INTEGER,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE INDEX IF NOT EXISTS idx_dm_items_status ON dm_items(status);
  CREATE INDEX IF NOT EXISTS idx_dm_items_gtin ON dm_items(gtin);
  CREATE INDEX IF NOT EXISTS idx_dm_items_boxkey ON dm_items(box_key);

  CREATE TABLE IF NOT EXISTS dm_products (
    gtin       TEXT PRIMARY KEY,         -- canonical 14-digit GTIN
    cn         TEXT,                     -- Código Nacional (reference / fallback match)
    nombre     TEXT,
    color      TEXT,                     -- hex override (null = auto from GTIN)
    shape      TEXT,                     -- shape override (null = auto from GTIN)
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS dm_settings (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    dm_size      INTEGER,
    list_dm_size INTEGER,
    card_dm_size INTEGER,
    dm_light     TEXT,
    updated_by   INTEGER,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS dm_cart (
    user_id   INTEGER NOT NULL,
    item_id   INTEGER NOT NULL,
    added_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, item_id)
  );
`);

try { db.prepare('ALTER TABLE dm_products ADD COLUMN cn TEXT').run(); } catch { /* already present */ }
// The cn index must be created AFTER the migration that adds the column (an old
// db_products table won't have `cn` at CREATE-TABLE time).
try { db.prepare('CREATE INDEX IF NOT EXISTS idx_dm_products_cn ON dm_products(cn)').run(); } catch { /* ignore */ }

// ── Assignment link (shared with the "Asignación de medicación" app) ─────────────
// A box can be reserved for a person before it is dispensed. `assignee_id` is the
// qr-tis person the box is (pre)assigned to; `assignee_name` is a denormalised
// snapshot so this app can show the badge without needing the people database.
//   Pre-asignada = status 'activo' AND assignee_id IS NOT NULL (reserved, still in stock)
//   Asignada     = status 'utilizado' AND assignee_id IS NOT NULL (dispensed via assignment)
//   Utilizada    = status 'utilizado' AND assignee_id IS NULL (used straight from this app)
try { db.prepare('ALTER TABLE dm_items ADD COLUMN assignee_id INTEGER').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE dm_items ADD COLUMN assignee_name TEXT').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE dm_items ADD COLUMN assignee_pharmacy TEXT').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE dm_items ADD COLUMN assignee_group TEXT').run(); } catch { /* already present */ }
// Archive: used boxes auto-move to «Archivadas» after a month (keeps traceability
// without cluttering «Utilizadas»). `archived_manual`=1 marks a box a user pulled
// back to «Utilizadas», so auto-archive won't touch it again.
try { db.prepare('ALTER TABLE dm_items ADD COLUMN archived INTEGER NOT NULL DEFAULT 0').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE dm_items ADD COLUMN archived_at DATETIME').run(); } catch { /* already present */ }
try { db.prepare('ALTER TABLE dm_items ADD COLUMN archived_manual INTEGER NOT NULL DEFAULT 0').run(); } catch { /* already present */ }
try { db.prepare('CREATE INDEX IF NOT EXISTS idx_dm_items_assignee ON dm_items(assignee_id)').run(); } catch { /* ignore */ }
// Forma farmacéutica (comprimido, cápsula…) — added for Galénica; also useful here.
try { db.prepare('ALTER TABLE cima_cache ADD COLUMN forma TEXT').run(); } catch { /* already present */ }

// ── CIMA (AEMPS) local cache ─────────────────────────────────────────────────────
// Every successful lookup is stored here (data + downloaded thumbnails) so the app
// keeps working offline for medications already seen, and images load from us.
db.exec(`
  CREATE TABLE IF NOT EXISTS cima_cache (
    cn            TEXT PRIMARY KEY,
    nombre        TEXT,
    barcode       TEXT,
    gtin          TEXT,
    nregistro     TEXT,
    pactivos      TEXT,
    labtitular    TEXT,
    forma         TEXT,
    foto_caja     BLOB,
    foto_pastilla BLOB,
    foto_caja_url     TEXT,
    foto_pastilla_url TEXT,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

console.log('[datamatrix] Database ready at:', DB_PATH);

const DEFAULT_SETTINGS = { dm_size: 300, list_dm_size: 100, card_dm_size: 200, dm_light: '#ffffff' };

// ── Items (boxes) ─────────────────────────────────────────────────────────────────
// Name/colour/shape come from the medication catalogue by GTIN; if that GTIN has
// no catalogue entry, fall back to a match by Código Nacional (when the code
// carried one). Colour/shape still key off the box's own GTIN for a stable look.
const ITEM_SELECT =
  `SELECT i.id, i.raw, i.box_key, i.gtin, i.serial, i.lote, i.caducidad, i.cn, i.status,
          i.used_at, i.created_at, i.updated_at, i.assignee_id, i.assignee_name, i.assignee_pharmacy, i.assignee_group, i.archived,
          COALESCE(p.nombre, pc.nombre) AS nombre, p.color AS color, p.shape AS shape
     FROM dm_items i
     LEFT JOIN dm_products p  ON p.gtin = i.gtin
     LEFT JOIN dm_products pc ON pc.cn = i.cn AND i.cn IS NOT NULL AND i.cn <> ''`;

// tab: 'activo' (stock) | 'utilizado' (used, not archived) | 'archivado' (used, archived).
function listItems(tab) {
  let where = '';
  if (tab === 'activo') where = "WHERE i.status = 'activo'";
  else if (tab === 'utilizado') where = "WHERE i.status = 'utilizado' AND i.archived = 0";
  else if (tab === 'archivado') where = "WHERE i.status = 'utilizado' AND i.archived = 1";
  return db.prepare(`${ITEM_SELECT} ${where} ORDER BY p.nombre COLLATE NOCASE, i.gtin, i.caducidad, i.id`).all();
}
// Auto-archive: used boxes older than `days` (by used_at) move to «Archivadas»,
// unless a user manually pulled them back. Returns how many were archived.
function autoArchive(days) {
  const d = Number.isFinite(days) ? days : 30;
  const cutoff = new Date(Date.now() - d * 86400000).toISOString().replace('T', ' ').slice(0, 19);
  return db.prepare(
    `UPDATE dm_items SET archived = 1, archived_at = CURRENT_TIMESTAMP
      WHERE status = 'utilizado' AND archived = 0 AND archived_manual = 0 AND used_at IS NOT NULL AND used_at <= ?`
  ).run(cutoff).changes;
}
// Manually move an archived box back to «Utilizadas» (won't auto-archive again).
function unarchiveItem(id) {
  db.prepare('UPDATE dm_items SET archived = 0, archived_manual = 1, archived_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run(id);
  return getItem(id);
}
function getItem(id) {
  return db.prepare(`${ITEM_SELECT} WHERE i.id = ?`).get(id) || null;
}
// A box already in the database (any status) with this identity?
function findByKey(boxKey) {
  if (!boxKey) return null;
  return db.prepare(`${ITEM_SELECT} WHERE i.box_key = ?`).get(boxKey) || null;
}

function createItem(data, userId) {
  const info = db.prepare(
    `INSERT INTO dm_items (raw, box_key, gtin, serial, lote, caducidad, cn, status, created_by, last_used_at)
     VALUES (@raw, @box_key, @gtin, @serial, @lote, @caducidad, @cn, 'activo', @created_by, CURRENT_TIMESTAMP)`
  ).run({
    raw: data.raw, box_key: data.box_key || null, gtin: data.gtin || null, serial: data.serial || null,
    lote: data.lote || null, caducidad: data.caducidad || null, cn: data.cn || null,
    created_by: userId != null ? userId : null,
  });
  return getItem(info.lastInsertRowid);
}
const createManyItems = db.transaction((rows, userId) => rows.map(r => createItem(r, userId)));

function setUsed(id, used) {
  const it = db.prepare('SELECT id FROM dm_items WHERE id = ?').get(id);
  if (!it) return null;
  db.prepare(
    `UPDATE dm_items SET status = @status, used_at = @used_at,
            updated_at = CURRENT_TIMESTAMP, last_used_at = CURRENT_TIMESTAMP WHERE id = @id`
  ).run({ id, status: used ? 'utilizado' : 'activo', used_at: used ? new Date().toISOString().replace('T', ' ').slice(0, 19) : null });
  return getItem(id);
}
function touchItem(id) {
  db.prepare('UPDATE dm_items SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?').run(id);
  return getItem(id);
}
// Reserve (or release) a box for a person. Passing assigneeId = null clears it.
// Does NOT change status — pre-asignada keeps the box 'activo' (still in stock);
// the caller marks it 'utilizado' (setUsed) when it is actually dispensed.
function setAssignee(id, assigneeId, assigneeName, assigneePharmacy, assigneeGroup) {
  const it = db.prepare('SELECT id FROM dm_items WHERE id = ?').get(id);
  if (!it) return null;
  db.prepare(
    `UPDATE dm_items SET assignee_id = @assignee_id, assignee_name = @assignee_name, assignee_pharmacy = @assignee_pharmacy, assignee_group = @assignee_group,
            updated_at = CURRENT_TIMESTAMP, last_used_at = CURRENT_TIMESTAMP WHERE id = @id`
  ).run({
    id,
    assignee_id: assigneeId != null ? assigneeId : null,
    assignee_name: assigneeId != null ? (assigneeName || null) : null,
    assignee_pharmacy: assigneeId != null ? (assigneePharmacy || null) : null,
    assignee_group: assigneeId != null ? (assigneeGroup || null) : null,
  });
  return getItem(id);
}
// Boxes available to reserve: 'activo' and not already reserved for someone.
// Optionally restricted to one GTIN (the medication being fulfilled).
function availableItems(gtin) {
  const where = gtin ? "AND i.gtin = ?" : "";
  const args = gtin ? [gtin] : [];
  return db.prepare(
    `${ITEM_SELECT} WHERE i.status = 'activo' AND i.assignee_id IS NULL ${where}
      ORDER BY i.caducidad IS NULL, i.caducidad, i.id`
  ).all(...args);
}
// Available (unreserved) boxes matching a Código Nacional — for linking a box to a
// plan medication that has no GTIN yet.
function availableItemsByCn(cn) {
  if (!cn) return [];
  return db.prepare(
    `${ITEM_SELECT} WHERE i.status = 'activo' AND i.assignee_id IS NULL AND i.cn = ?
      ORDER BY i.caducidad IS NULL, i.caducidad, i.id`
  ).all(String(cn));
}
function recentItems(limit) {
  return db.prepare(
    `${ITEM_SELECT} WHERE i.status = 'activo'
      ORDER BY COALESCE(i.last_used_at, i.updated_at, i.created_at) DESC, i.id DESC LIMIT ?`
  ).all(Math.max(1, Math.min(50, limit || 10)));
}
function deleteItem(id) {
  db.prepare('DELETE FROM dm_cart WHERE item_id = ?').run(id);
  return db.prepare('DELETE FROM dm_items WHERE id = ?').run(id).changes > 0;
}
const deleteMany = db.transaction((ids) => { let n = 0; for (const id of ids) if (deleteItem(id)) n++; return n; });
function counts() {
  autoArchive(30);   // keep «Utilizadas» tidy: used > 1 month → «Archivadas»
  const a = db.prepare("SELECT COUNT(*) n FROM dm_items WHERE status='activo'").get().n;
  const u = db.prepare("SELECT COUNT(*) n FROM dm_items WHERE status='utilizado' AND archived=0").get().n;
  const arch = db.prepare("SELECT COUNT(*) n FROM dm_items WHERE status='utilizado' AND archived=1").get().n;
  const pre = db.prepare("SELECT COUNT(*) n FROM dm_items WHERE status='activo' AND assignee_id IS NOT NULL").get().n;
  return { activo: a, utilizado: u, archivado: arch, preasignada: pre };
}

// ── Products (GTIN → nombre / colour / shape) ────────────────────────────────────
function getProduct(gtin) { return db.prepare('SELECT * FROM dm_products WHERE gtin = ?').get(gtin) || null; }
// A CN seen on any box of this GTIN (helps name a product that has no CN of its own).
function firstItemCnForGtin(gtin) {
  const r = db.prepare("SELECT cn FROM dm_items WHERE gtin = ? AND cn IS NOT NULL AND cn <> '' ORDER BY id LIMIT 1").get(gtin);
  return r ? r.cn : null;
}
// Todos los Código Nacional vistos alguna vez (cajas escaneadas + catálogo de
// productos) — usado por el catch-up de arranque de Galénica (apps/galenica/ingest.js).
function allCns() {
  return db.prepare(
    "SELECT cn FROM dm_items WHERE cn IS NOT NULL AND cn <> '' UNION SELECT cn FROM dm_products WHERE cn IS NOT NULL AND cn <> ''"
  ).all().map(r => r.cn);
}
function listProducts() { return db.prepare('SELECT * FROM dm_products ORDER BY nombre COLLATE NOCASE, gtin').all(); }
function upsertProduct(gtin, data) {
  const cur = getProduct(gtin) || {};
  const row = {
    gtin,
    cn: data.cn !== undefined ? (data.cn || null) : (cur.cn || null),
    nombre: data.nombre !== undefined ? (data.nombre || null) : (cur.nombre || null),
    color: data.color !== undefined ? (data.color || null) : (cur.color || null),
    shape: data.shape !== undefined ? (data.shape || null) : (cur.shape || null),
  };
  db.prepare(
    `INSERT INTO dm_products (gtin, cn, nombre, color, shape, updated_at)
     VALUES (@gtin, @cn, @nombre, @color, @shape, CURRENT_TIMESTAMP)
     ON CONFLICT(gtin) DO UPDATE SET cn = excluded.cn, nombre = excluded.nombre, color = excluded.color,
       shape = excluded.shape, updated_at = CURRENT_TIMESTAMP`
  ).run(row);
  return getProduct(gtin);
}
// Import catalogue rows (GTIN and/or CN → nombre). Idempotent: updates the name
// (and CN) of existing medications and adds new ones; never touches colour/shape
// overrides. Re-import the Farmatic export any time to refresh names everywhere.
const importProducts = db.transaction((rows) => {
  let n = 0;
  for (const r of rows) {
    if (!r.gtin) continue; // keyed by GTIN (the barcode the catalogue lists)
    const cur = getProduct(r.gtin) || {};
    db.prepare(
      `INSERT INTO dm_products (gtin, cn, nombre, color, shape, updated_at)
       VALUES (@gtin, @cn, @nombre, @color, @shape, CURRENT_TIMESTAMP)
       ON CONFLICT(gtin) DO UPDATE SET nombre = excluded.nombre, cn = COALESCE(excluded.cn, dm_products.cn), updated_at = CURRENT_TIMESTAMP`
    ).run({ gtin: r.gtin, cn: r.cn || null, nombre: r.nombre || null, color: cur.color || null, shape: cur.shape || null });
    n++;
  }
  return n;
});

// ── Settings ────────────────────────────────────────────────────────────────────
function getSettings() {
  const row = db.prepare('SELECT * FROM dm_settings WHERE id = 1').get() || {};
  const out = { ...DEFAULT_SETTINGS };
  for (const k of Object.keys(DEFAULT_SETTINGS)) if (row[k] != null) out[k] = row[k];
  return out;
}
function saveSettings(data, userId) {
  const s = { ...getSettings(), ...data };
  db.prepare(
    `INSERT INTO dm_settings (id, dm_size, list_dm_size, card_dm_size, dm_light, updated_by, updated_at)
     VALUES (1, @dm_size, @list_dm_size, @card_dm_size, @dm_light, @updated_by, CURRENT_TIMESTAMP)
     ON CONFLICT(id) DO UPDATE SET dm_size = excluded.dm_size, list_dm_size = excluded.list_dm_size,
       card_dm_size = excluded.card_dm_size, dm_light = excluded.dm_light,
       updated_by = excluded.updated_by, updated_at = CURRENT_TIMESTAMP`
  ).run({ dm_size: s.dm_size, list_dm_size: s.list_dm_size, card_dm_size: s.card_dm_size, dm_light: s.dm_light, updated_by: userId != null ? userId : null });
  return getSettings();
}

// ── Per-user cart ────────────────────────────────────────────────────────────────
function cartIds(userId) { return db.prepare('SELECT item_id FROM dm_cart WHERE user_id = ? ORDER BY added_at, item_id').all(userId).map(r => r.item_id); }
function cartAdd(userId, itemId) { db.prepare('INSERT OR IGNORE INTO dm_cart (user_id, item_id) VALUES (?, ?)').run(userId, itemId); return cartIds(userId); }
function cartRemove(userId, itemId) { db.prepare('DELETE FROM dm_cart WHERE user_id = ? AND item_id = ?').run(userId, itemId); return cartIds(userId); }
function cartClear(userId) { db.prepare('DELETE FROM dm_cart WHERE user_id = ?').run(userId); return []; }

// ── CIMA local cache ─────────────────────────────────────────────────────────────
// Metadata (no blobs) + which photos are stored — for the offline fallback.
function cimaCacheGet(cn) {
  if (!cn) return null;
  return db.prepare(
    `SELECT cn, nombre, barcode, gtin, nregistro, pactivos, labtitular, forma,
            foto_caja_url, foto_pastilla_url,
            (foto_caja IS NOT NULL) AS has_caja, (foto_pastilla IS NOT NULL) AS has_pastilla, updated_at
       FROM cima_cache WHERE cn = ?`
  ).get(String(cn)) || null;
}
// Upsert. Keeps a previously downloaded image if this time we couldn't fetch it.
function cimaCachePut(cn, d = {}) {
  if (!cn) return;
  db.prepare(
    `INSERT INTO cima_cache (cn, nombre, barcode, gtin, nregistro, pactivos, labtitular, forma, foto_caja, foto_pastilla, foto_caja_url, foto_pastilla_url, updated_at)
     VALUES (@cn, @nombre, @barcode, @gtin, @nregistro, @pactivos, @labtitular, @forma, @foto_caja, @foto_pastilla, @foto_caja_url, @foto_pastilla_url, CURRENT_TIMESTAMP)
     ON CONFLICT(cn) DO UPDATE SET
       nombre = COALESCE(excluded.nombre, cima_cache.nombre),
       barcode = COALESCE(excluded.barcode, cima_cache.barcode),
       gtin = COALESCE(excluded.gtin, cima_cache.gtin),
       nregistro = COALESCE(excluded.nregistro, cima_cache.nregistro),
       pactivos = COALESCE(excluded.pactivos, cima_cache.pactivos),
       labtitular = COALESCE(excluded.labtitular, cima_cache.labtitular),
       forma = COALESCE(excluded.forma, cima_cache.forma),
       foto_caja = COALESCE(excluded.foto_caja, cima_cache.foto_caja),
       foto_pastilla = COALESCE(excluded.foto_pastilla, cima_cache.foto_pastilla),
       foto_caja_url = COALESCE(excluded.foto_caja_url, cima_cache.foto_caja_url),
       foto_pastilla_url = COALESCE(excluded.foto_pastilla_url, cima_cache.foto_pastilla_url),
       updated_at = CURRENT_TIMESTAMP`
  ).run({
    cn: String(cn), nombre: d.nombre || null, barcode: d.barcode || null, gtin: d.gtin || null,
    nregistro: d.nregistro || null, pactivos: d.pactivos || null, labtitular: d.labtitular || null, forma: d.forma || null,
    foto_caja: d.foto_caja || null, foto_pastilla: d.foto_pastilla || null,
    foto_caja_url: d.foto_caja_url || null, foto_pastilla_url: d.foto_pastilla_url || null,
  });
}
function cimaCacheFoto(cn, tipo) {
  if (!cn) return null;
  const col = tipo === 'pastilla' ? 'foto_pastilla' : 'foto_caja';
  const row = db.prepare(`SELECT ${col} AS b FROM cima_cache WHERE cn = ?`).get(String(cn));
  return row && row.b ? row.b : null;
}
function cimaCacheCount() { return db.prepare('SELECT COUNT(*) n FROM cima_cache').get().n; }

module.exports = {
  db, DEFAULT_SETTINGS,
  listItems, getItem, findByKey, createItem, createManyItems, setUsed, touchItem, setAssignee, availableItems, availableItemsByCn, recentItems, deleteItem, deleteMany, counts, autoArchive, unarchiveItem,
  getProduct, listProducts, upsertProduct, importProducts, firstItemCnForGtin, allCns,
  getSettings, saveSettings,
  cartIds, cartAdd, cartRemove, cartClear,
  cimaCacheGet, cimaCachePut, cimaCacheFoto, cimaCacheCount,
};
