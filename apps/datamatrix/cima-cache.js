'use strict';

// ── CIMA lookup with a local cache (Nivel 1 backup) ──────────────────────────────
// Wraps cima.lookupByCn: every success is stored in the DB (data + downloaded
// thumbnails) so the app keeps working OFFLINE for medications already seen, and
// their images are served by us. cima.js itself stays pure/network-only; this is
// the caching orchestration used by the routes.

const cima = require('./cima');
const db = require('./db');

const IMG_TIMEOUT_MS = Number(process.env.CIMA_IMG_TIMEOUT_MS) || 6000;

// Best-effort binary fetch (returns a Buffer or null; never throws).
async function fetchImage(url, fetchImpl) {
  if (!url) return null;
  const doFetch = fetchImpl || globalThis.fetch;
  if (typeof doFetch !== 'function') return null;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), IMG_TIMEOUT_MS);
  try {
    const r = await doFetch(url, { signal: ctrl.signal });
    if (!r.ok) return null;
    const ab = await r.arrayBuffer();
    const buf = Buffer.from(ab);
    return buf.length ? buf : null;
  } catch { return null; } finally { clearTimeout(timer); }
}

// Reconstruct our public shape from a cached row.
function fromCache(row) {
  if (!row) return null;
  return {
    cn: row.cn, nombre: row.nombre || null, barcode: row.barcode || null, gtin: row.gtin || null,
    nregistro: row.nregistro || null, pactivos: row.pactivos || null, labtitular: row.labtitular || null,
    fotos: {
      caja: row.has_caja ? { full: row.foto_caja_url || null } : null,
      pastilla: row.has_pastilla ? { full: row.foto_pastilla_url || null } : null,
    },
    source: 'cache', cached: true,
  };
}

// Look up by CN, caching the result; fall back to the cache when CIMA is offline.
async function lookupByCnCached(cn, opts = {}) {
  try {
    const item = await cima.lookupByCn(cn, opts);
    if (item) {
      const fc = item.fotos || {};
      const [caja, pastilla] = await Promise.all([
        fetchImage(fc.caja && fc.caja.thumb, opts.fetchImpl),
        fetchImage(fc.pastilla && fc.pastilla.thumb, opts.fetchImpl),
      ]);
      db.cimaCachePut(item.cn || cn, {
        nombre: item.nombre, barcode: item.barcode, gtin: item.gtin, nregistro: item.nregistro,
        pactivos: item.pactivos, labtitular: item.labtitular,
        foto_caja: caja, foto_pastilla: pastilla,
        foto_caja_url: fc.caja && (fc.caja.full || fc.caja.thumb),
        foto_pastilla_url: fc.pastilla && (fc.pastilla.full || fc.pastilla.thumb),
      });
    }
    return item ? { ...item, cached: false } : item;
  } catch (e) {
    // CIMA unreachable → serve from cache if we have it.
    if (e.offline) {
      const row = db.cimaCacheGet(String(cn || '').replace(/\D/g, ''));
      if (row) return fromCache(row);
    }
    throw e;
  }
}

// Serve a cached photo; if missing but its URL is known, download it now and store.
async function foto(cn, tipo) {
  const c = String(cn || '').replace(/\D/g, '');
  let buf = db.cimaCacheFoto(c, tipo);
  if (buf) return buf;
  const row = db.cimaCacheGet(c);
  const url = row && (tipo === 'pastilla' ? row.foto_pastilla_url : row.foto_caja_url);
  if (!url) return null;
  buf = await fetchImage(url);
  if (buf) db.cimaCachePut(c, tipo === 'pastilla' ? { foto_pastilla: buf } : { foto_caja: buf });
  return buf;
}

module.exports = { lookupByCnCached, foto, fetchImage };
