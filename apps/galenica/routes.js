'use strict';

// ── Galénica — API + UI ──────────────────────────────────────────────────────────
// Medication REFERENCE catalogue: what a medication IS and looks like, keyed by
// Código Nacional — not an inventory of physical boxes (Data Matrix) and not a
// person's plan (Asignación). Reuses the SAME CIMA cache as those two apps (name,
// principio activo, forma farmacéutica, laboratorio) and the SAME pill-photo
// repository as Pastillero (by CN) — nothing here is a new data source except the
// one CIMA doesn't have: colour, always entered by hand.

const express = require('express');
const path = require('path');
const db = require('./db');
const cimaCache = require('../datamatrix/cima-cache');
const cima = require('../datamatrix/cima');
const gs1 = require('../datamatrix/gs1');

const router = express.Router();
const PUB = path.join(__dirname, 'public');
const json = express.json({ limit: '256kb' });
const jsonBig = express.json({ limit: '4mb' });

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[galenica] error:', err);
  res.status(status).json({ error: err.message || 'Error en Galénica.' });
}
function bad(msg, status = 400) { const e = new Error(msg); e.status = status; return e; }
const cleanCn = v => String(v == null ? '' : v).replace(/\D/g, '');

function publicMed(m) {
  if (!m) return null;
  return {
    id: m.id, cn: m.cn, gtin: m.gtin || null, barcode: m.barcode || null,
    nombre: m.nombre || null, pactivos: m.pactivos || null, forma: m.forma || null,
    color: m.color || null, labtitular: m.labtitular || null,
    comercializado: m.comercializado == null ? null : !!m.comercializado,
    notes: m.notes || null, created_at: m.created_at, updated_at: m.updated_at,
  };
}
// Best-effort CIMA fetch by CN. Never throws: on failure (or when CIMA is
// offline) returns null and the caller just keeps whatever's already stored.
async function fetchCima(cn) {
  try { return await cimaCache.lookupByCnCached(cn); }
  catch { return null; }
}

router.get('/api/meta', (req, res) => {
  try { res.json({ formas: db.distinctFormas(), colors: db.distinctColors() }); }
  catch (err) { fail(res, err); }
});
router.get('/api/meds', (req, res) => {
  try { res.json({ items: db.listMeds().map(publicMed) }); }
  catch (err) { fail(res, err); }
});

// Add one medication by Código Nacional. CIMA fills what it can (best-effort,
// offline-tolerant); colour (and any manual field) is applied on top.
router.post('/api/meds', json, async (req, res) => {
  try {
    const b = req.body || {};
    const cn = cleanCn(b.cn);
    if (!/^\d{4,8}$/.test(cn)) throw bad('Código Nacional no válido.');
    if (db.getByCn(cn)) throw bad(`El CN ${cn} ya está en Galénica.`);
    const it = await fetchCima(cn);
    const med = db.upsertFromCima(cn, {
      gtin: (it && it.gtin) || gs1.cnToGtin(cn),
      barcode: (it && it.barcode) || cima.barcodeFromCn(cn),
      nombre: (it && it.nombre) || b.nombre || null,
      pactivos: it && it.pactivos, forma: it && it.forma, labtitular: it && it.labtitular,
    }, req.user.id);
    const updated = (b.color !== undefined || b.notes !== undefined) ? db.updateMed(med.id, { color: b.color, notes: b.notes }) : med;
    res.json({ item: publicMed(updated), cima_found: !!(it && it.nombre) });
  } catch (err) { fail(res, err); }
});
router.put('/api/meds/:id(\\d+)', json, (req, res) => {
  try {
    const m = db.getMed(Number(req.params.id));
    if (!m) return res.status(404).json({ error: 'No encontrado.' });
    res.json({ item: publicMed(db.updateMed(m.id, req.body || {})) });
  } catch (err) { fail(res, err); }
});
// Re-consult CIMA for this CN — fills gaps and refreshes what changed, exactly
// like "Actualizar desde CIMA" in Data Matrix. Never touches colour/notes.
router.post('/api/meds/:id(\\d+)/cima', json, async (req, res) => {
  try {
    const m = db.getMed(Number(req.params.id));
    if (!m) return res.status(404).json({ error: 'No encontrado.' });
    const it = await fetchCima(m.cn);
    if (!it) return res.json({ item: publicMed(m), cima_found: false, offline: true });
    const updated = db.upsertFromCima(m.cn, { gtin: it.gtin || gs1.cnToGtin(m.cn), barcode: it.barcode || cima.barcodeFromCn(m.cn), nombre: it.nombre, pactivos: it.pactivos, forma: it.forma, labtitular: it.labtitular }, req.user.id);
    res.json({ item: publicMed(updated), cima_found: !!it.nombre });
  } catch (err) { fail(res, err); }
});
router.delete('/api/meds/:id(\\d+)', (req, res) => {
  try {
    const m = db.getMed(Number(req.params.id));
    if (!m) return res.status(404).json({ error: 'No encontrado.' });
    db.deleteMed(m.id);
    res.json({ ok: true });
  } catch (err) { fail(res, err); }
});

// Bulk add: [{cn, color?}] — one CIMA lookup per row, best-effort. Existing CNs
// are refreshed (not duplicated); rows CIMA can't resolve are still kept (by CN
// alone) so nothing typed gets lost, and reported back as "missing".
router.post('/api/import', jsonBig, async (req, res) => {
  try {
    const rows = Array.isArray(req.body && req.body.rows) ? req.body.rows : null;
    if (!rows) throw bad('No se recibieron filas para importar.');
    if (rows.length > 5000) throw bad('Demasiadas filas (máximo 5000 por importación).');
    let created = 0, updated = 0; const missing = [];
    for (const r of rows) {
      const cn = cleanCn(r.cn);
      if (!/^\d{4,8}$/.test(cn)) continue;
      const already = !!db.getByCn(cn);
      const it = await fetchCima(cn);   // best-effort; null on any failure (offline or not found)
      const med = db.upsertFromCima(cn, {
        gtin: (it && it.gtin) || gs1.cnToGtin(cn), barcode: (it && it.barcode) || cima.barcodeFromCn(cn),
        nombre: (it && it.nombre) || r.nombre || null, pactivos: it && it.pactivos, forma: it && it.forma, labtitular: it && it.labtitular,
      }, req.user.id);
      if (r.color !== undefined) db.updateMed(med.id, { color: r.color });
      if (!it || !it.nombre) missing.push(cn);
      already ? updated++ : created++;
    }
    res.json({ created, updated, missing, total: rows.length });
  } catch (err) { fail(res, err); }
});

// ── UI ────────────────────────────────────────────────────────────────────────
router.get('/', (req, res) => res.sendFile(path.join(PUB, 'index.html')));
router.use('/assets', express.static(PUB));

module.exports = router;
