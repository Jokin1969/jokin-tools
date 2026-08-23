'use strict';

// ── Gestor de códigos Data Matrix — API + UI ────────────────────────────────────
// Mounted at /datamatrix (gated by requireApp('datamatrix')). Boxes are added by
// scanning their GS1 Data Matrix (parsed into fields), can be marked "utilizada"
// (leaves the inventory), and are shown as scannable Data Matrix codes coloured per
// medication. Data Matrix codes are generated client-side (bwip-js); the PDF export
// generates them server-side.

const express = require('express');
const path = require('path');
const db = require('./db');
const gs1 = require('./gs1');
const visual = require('./visual');
const cima = require('./cima');
const cimaCache = require('./cima-cache');

const router = express.Router();
const PUB = path.join(__dirname, 'public');
const json = express.json({ limit: '512kb' });
const jsonBig = express.json({ limit: '6mb' });

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[datamatrix] error:', err);
  res.status(status).json({ error: err.message || 'Error en Gestor de Data Matrix.' });
}
function bad(msg, status = 400) { const e = new Error(msg); e.status = status; return e; }

function setDownload(res, filename, mime) {
  const ascii = filename.replace(/[^\x20-\x7E]/g, '_').replace(/["\\]/g, '_');
  res.setHeader('Content-Type', mime);
  res.setHeader('Content-Disposition', `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(filename)}`);
}

function cleanRaw(v) {
  const s = String(v == null ? '' : v).trim();
  if (!s) throw bad('El código Data Matrix está vacío.');
  if (s.length > 2000) throw bad('El contenido del Data Matrix es demasiado largo.');
  return s;
}
const CLR = /^#[0-9a-fA-F]{6}$/;
const clampN = (n, lo, hi, d) => { const x = Math.round(Number(n)); return Number.isFinite(x) ? Math.min(hi, Math.max(lo, x)) : d; };

// Resolve a stored item into what the UI needs (name + effective colour/shape).
function publicItem(it) {
  if (!it) return it;
  // Three-state assignment view (shared with the Asignación app):
  //   preasignada = reserved for a person, still in stock (status 'activo')
  //   asignada    = dispensed to that person (status 'utilizado' + assignee)
  const asig_state = it.assignee_id != null ? (it.status === 'utilizado' ? 'asignada' : 'preasignada') : null;
  const cc = it.cn ? db.cimaCacheGet(String(it.cn).replace(/\D/g, '')) : null;
  return {
    id: it.id, raw: it.raw, gtin: it.gtin || null, serial: it.serial || null,
    lote: it.lote || null, caducidad: it.caducidad || null, cn: it.cn || null,
    foto_caja: !!(cc && cc.has_caja), foto_pastilla: !!(cc && cc.has_pastilla),
    cima_updated_at: cc ? cc.updated_at : null,
    status: it.status, used_at: it.used_at || null,
    nombre: it.nombre || null,
    color: visual.resolveColor(it.gtin, it.color),
    shape: visual.resolveShape(it.gtin, it.shape),
    assignee_id: it.assignee_id != null ? it.assignee_id : null,
    assignee_name: it.assignee_name || null,
    assignee_pharmacy: it.assignee_pharmacy || null,
    assignee_group: it.assignee_group || null,
    archived: it.archived ? 1 : 0,
    asig_state,
    created_at: it.created_at, updated_at: it.updated_at,
  };
}

// Parse a raw string into the fields we store.
function fieldsFromRaw(raw) {
  const f = gs1.parse(raw);
  return { raw, box_key: gs1.boxKey(f, raw), gtin: gs1.normGtin(f.gtin), serial: f.serial, lote: f.lote, caducidad: gs1.expiryToIso(f.caducidad), cn: gs1.cnForCima(f) };
}
// Fill a box's medication name from CIMA (cached, tolerant of offline). Best-effort:
// on failure the product stays a stub and can be named later. Never throws.
async function nameProductFromCima(gtin, cn) {
  if (!gtin) return;
  const prod = db.getProduct(gtin);
  if (!prod) db.upsertProduct(gtin, { cn: cn || null });        // stub so a name can attach
  if (!cn || (prod && prod.nombre)) return;                      // no CN, or already named
  try {
    const it = await cimaCache.lookupByCnCached(cn);
    if (it && it.nombre) db.upsertProduct(gtin, { nombre: it.nombre, cn: it.cn || cn });
  } catch { /* CIMA offline → leave the stub; the name can be filled later */ }
}

// ── UI ───────────────────────────────────────────────────────────────────────
router.get('/', (req, res) => res.sendFile(path.join(PUB, 'index.html')));
router.use('/assets', express.static(PUB));

router.get('/api/meta', (req, res) => {
  try {
    res.json({
      settings: db.getSettings(),
      counts: db.counts(),
      palette: visual.PALETTE, shapes: visual.SHAPES,
      user: { id: req.user.id, email: req.user.email, name: req.user.name || req.user.email },
    });
  } catch (err) { fail(res, err); }
});

// ── Scan IN (entrada): add a box, or report it's already known ──────────────────
router.post('/api/scan', json, async (req, res) => {
  try {
    const raw = cleanRaw(req.body && req.body.raw);
    const data = fieldsFromRaw(raw);
    const existing = db.findByKey(data.box_key);
    if (existing) return res.json({ duplicate: true, status: existing.status, item: publicItem(existing) });
    const item = db.createItem(data, req.user.id);
    await nameProductFromCima(data.gtin, data.cn);   // identify the medication via CIMA
    res.status(201).json({ item: publicItem(db.findByKey(data.box_key) || item) });
  } catch (err) { fail(res, err); }
});

// ── Scan OUT (salida): mark a known box as utilizada ────────────────────────────
router.post('/api/use', json, (req, res) => {
  try {
    const raw = cleanRaw(req.body && req.body.raw);
    const data = fieldsFromRaw(raw);
    const existing = db.findByKey(data.box_key);
    if (!existing) return res.json({ notFound: true });
    if (existing.status === 'utilizado') return res.json({ already: true, item: publicItem(existing) });
    const used = db.setUsed(existing.id, true);
    res.json({ ok: true, item: publicItem(used) });
  } catch (err) { fail(res, err); }
});

// ── Items ─────────────────────────────────────────────────────────────────────
router.get('/api/items', (req, res) => {
  try {
    const counts = db.counts();   // also runs auto-archive
    const tab = ['utilizado', 'archivado'].includes(req.query.status) ? req.query.status : 'activo';
    res.json({ items: db.listItems(tab).map(publicItem), counts });
  } catch (err) { fail(res, err); }
});
router.get('/api/item/:id(\\d+)', (req, res) => {
  try { const it = db.getItem(Number(req.params.id)); if (!it) return res.status(404).json({ error: 'No encontrado.' }); res.json({ item: publicItem(it) }); }
  catch (err) { fail(res, err); }
});
router.post('/api/item/:id(\\d+)/used', json, (req, res) => {
  try {
    const used = !!(req.body && req.body.used);
    const cur = db.getItem(Number(req.params.id));
    if (!cur) return res.status(404).json({ error: 'No encontrado.' });
    // A box linked to a person (asociada/asignada desde Asignación) NO se gestiona
    // desde aquí: evitar que se devuelva/marque a mano y se descuadre con el plan.
    if (cur.assignee_id != null) {
      return res.status(409).json({
        error: `Esta caja está ${cur.status === 'utilizado' ? 'asignada' : 'asociada'} a ${cur.assignee_name || 'una persona'} desde Asignación. Para devolverla al inventario, quítala desde la ficha del plan de esa persona.`,
        managed_by_asignacion: true,
        assignee_id: cur.assignee_id, assignee_name: cur.assignee_name || null,
      });
    }
    const it = db.setUsed(Number(req.params.id), used);
    res.json({ item: publicItem(it) });
  } catch (err) { fail(res, err); }
});
// Move an archived box back to «Utilizadas» (the UI gates this behind a typed
// confirmation). It won't auto-archive again.
router.post('/api/item/:id(\\d+)/unarchive', json, (req, res) => {
  try {
    const cur = db.getItem(Number(req.params.id));
    if (!cur) return res.status(404).json({ error: 'No encontrado.' });
    const it = db.unarchiveItem(cur.id);
    res.json({ item: publicItem(it) });
  } catch (err) { fail(res, err); }
});
router.post('/api/item/:id(\\d+)/touch', (req, res) => {
  try { const it = db.touchItem(Number(req.params.id)); if (!it) return res.status(404).json({ error: 'No encontrado.' }); res.json({ ok: true }); }
  catch (err) { fail(res, err); }
});
router.get('/api/item/:id(\\d+)', (req, res) => {
  try { const it = db.getItem(Number(req.params.id)); if (!it) return res.status(404).json({ error: 'No encontrado.' }); res.json({ item: publicItem(it) }); }
  catch (err) { fail(res, err); }
});
router.delete('/api/item/:id(\\d+)', (req, res) => {
  try { const ok = db.deleteItem(Number(req.params.id)); if (!ok) return res.status(404).json({ error: 'No encontrado.' }); res.json({ ok: true }); }
  catch (err) { fail(res, err); }
});
// Bulk delete (the selected boxes) — permanent.
router.post('/api/items/delete', jsonBig, (req, res) => {
  try {
    const ids = Array.isArray(req.body && req.body.ids) ? req.body.ids.map(Number).filter(Number.isInteger) : null;
    if (!ids || !ids.length) throw bad('No se recibieron cajas.');
    if (ids.length > 5000) throw bad('Demasiadas cajas.');
    res.json({ deleted: db.deleteMany(ids) });
  } catch (err) { fail(res, err); }
});

// ── Products (GTIN → nombre / colour / shape) ────────────────────────────────────
router.get('/api/products', (req, res) => {
  try { res.json({ items: db.listProducts() }); } catch (err) { fail(res, err); }
});
router.put('/api/product/:gtin([0-9A-Za-z]+)', json, (req, res) => {
  try {
    const b = req.body || {};
    const patch = {};
    if (b.nombre !== undefined) patch.nombre = b.nombre ? String(b.nombre).trim().slice(0, 160) : null;
    if (b.color !== undefined) patch.color = CLR.test(String(b.color || '')) ? b.color : null;
    if (b.shape !== undefined) patch.shape = visual.SHAPES.includes(b.shape) ? b.shape : null;
    res.json({ item: db.upsertProduct(req.params.gtin, patch) });
  } catch (err) { fail(res, err); }
});
// ── Update everything from CIMA (name + box/pill images + fetch date) ───────────
// Re-queries CIMA for EVERY medication (deduped by GTIN, resolving its Código
// Nacional) — not just the ones missing a name — so names and images are always up
// to date; the cache stores the new fetch date and replaces changed images. Stops
// early and reports if CIMA is offline.
router.post('/api/cima/complete', json, async (req, res) => {
  try {
    const prods = db.listProducts().filter(p => p.gtin);
    let checked = 0, refreshed = 0, renamed = 0, missing = 0, offline = false;
    for (const p of prods) {
      const cn = p.cn || gs1.cnForCima({ gtin: p.gtin }) || db.firstItemCnForGtin(p.gtin);
      if (!cn) { missing++; continue; }
      checked++;
      try {
        const it = await cimaCache.lookupByCnCached(cn);   // re-fetch: data + images + updated_at
        if (it && it.nombre) {
          if ((p.nombre || null) !== it.nombre) renamed++;
          db.upsertProduct(p.gtin, { nombre: it.nombre, cn: it.cn || cn });
          if (!it.cached) refreshed++;   // came from the network (fresh)
        } else missing++;
      } catch (e) { if (e.offline) { offline = true; break; } missing++; }
    }
    res.json({ ok: true, total: prods.length, checked, refreshed, renamed, missing, offline });
  } catch (err) { fail(res, err); }
});

// ── CIMA (AEMPS) lookup — fill a medication's name from its Código Nacional ──────
router.get('/api/cima/cn/:cn([0-9]+)', async (req, res) => {
  try {
    if (req.query.debug) return res.json(await cima.probeByCn(req.params.cn));  // raw + mapped, to verify field names
    res.json({ item: await cimaCache.lookupByCnCached(req.params.cn) });        // cached + offline fallback
  } catch (err) { res.status(err.status || 502).json({ error: err.message, offline: !!err.offline }); }
});
// Serve a medication photo (box/pill) from the local cache (works offline).
// Revalidation (ETag) instead of a long max-age, so a refreshed photo
// (thumbnail → full-size) reaches the browser instead of the stale cached one.
router.get('/api/cima/foto/:cn([0-9]+)/:tipo(caja|pastilla)', async (req, res) => {
  try {
    const buf = await cimaCache.foto(req.params.cn, req.params.tipo);
    if (!buf) return res.status(404).end();
    const row = db.cimaCacheGet(String(req.params.cn).replace(/\D/g, ''));
    const etag = `"${req.params.cn}-${req.params.tipo}-${(row && row.updated_at) || ''}-${buf.length}"`;
    res.set('Content-Type', 'image/jpeg');
    res.set('Cache-Control', 'no-cache');
    res.set('ETag', etag);
    if (req.headers['if-none-match'] === etag) return res.status(304).end();
    res.send(buf);
  } catch { res.status(404).end(); }
});
router.get('/api/cima/search', async (req, res) => {
  try { res.json({ items: await cima.searchByName(req.query.q || '') }); }
  catch (err) { res.status(err.status || 502).json({ error: err.message, offline: !!err.offline }); }
});
router.post('/api/products/import', jsonBig, (req, res) => {
  try {
    const rows = Array.isArray(req.body && req.body.rows) ? req.body.rows : null;
    if (!rows) throw bad('No se recibieron filas.');
    if (rows.length > 20000) throw bad('Demasiadas filas.');
    const clean = rows
      .map(r => {
        const cn = r.cn ? String(r.cn).replace(/\D/g, '').slice(0, 12) || null : null;
        // GTIN from the barcode; if there isn't one, reconstruct it from the CN.
        const fromBar = gs1.normGtin(r.gtin);
        const gtin = (fromBar && fromBar.replace(/^0+/, '').length >= 8) ? fromBar : gs1.cnToGtin(cn);
        return { gtin, cn, nombre: r.nombre ? String(r.nombre).trim().slice(0, 160) : null };
      })
      .filter(r => r.gtin);
    const n = db.importProducts(clean);
    res.json({ imported: n, total: rows.length, skipped: rows.length - clean.length });
  } catch (err) { fail(res, err); }
});

// ── Bulk import of boxes from RAW codes ─────────────────────────────────────────
router.post('/api/import', jsonBig, async (req, res) => {
  try {
    const rows = Array.isArray(req.body && req.body.rows) ? req.body.rows : null;
    if (!rows) throw bad('No se recibieron filas para importar.');
    if (rows.length > 10000) throw bad('Demasiadas filas (máximo 10000).');
    const errors = [];
    const seen = new Set();
    const valid = [];
    rows.forEach((r, i) => {
      const rowNo = r.__row != null ? r.__row : i + 1;
      try {
        const raw = cleanRaw(r.raw);
        const data = fieldsFromRaw(raw);
        if (seen.has(data.box_key) || db.findByKey(data.box_key)) throw bad('Ya está en la base de datos (duplicado).');
        seen.add(data.box_key);
        valid.push(data);
      } catch (e) { errors.push({ row: rowNo, error: e.message }); }
    });
    const created = valid.length ? db.createManyItems(valid, req.user.id) : [];
    // Identify each medication via CIMA — one by one (deduped by GTIN), with the
    // cache + downloaded box/pill images. Tolerant of offline: names/images fill in
    // now if reachable, or later otherwise.
    let named = 0; const doneGtins = new Set();
    for (const d of valid) {
      if (!d.gtin || doneGtins.has(d.gtin)) continue;
      doneGtins.add(d.gtin);
      const before = db.getProduct(d.gtin);
      await nameProductFromCima(d.gtin, d.cn);
      const after = db.getProduct(d.gtin);
      if (after && after.nombre && (!before || !before.nombre)) named++;
    }
    res.json({ created: created.length, named, errors, total: rows.length });
  } catch (err) { fail(res, err); }
});

// ── Recently handled (active only) ──────────────────────────────────────────────
router.get('/api/recent', (req, res) => {
  try { res.json({ items: db.recentItems(10).map(publicItem) }); } catch (err) { fail(res, err); }
});

// ── Settings ────────────────────────────────────────────────────────────────────
router.put('/api/settings', json, (req, res) => {
  try {
    const b = req.body || {}, d = db.DEFAULT_SETTINGS;
    res.json({ settings: db.saveSettings({
      dm_size: clampN(b.dm_size, 120, 900, d.dm_size),
      list_dm_size: clampN(b.list_dm_size, 70, 420, d.list_dm_size),
      card_dm_size: clampN(b.card_dm_size, 80, 220, d.card_dm_size),
      dm_light: CLR.test(String(b.dm_light || '')) ? b.dm_light : d.dm_light,
    }, req.user.id) });
  } catch (err) { fail(res, err); }
});

// ── Cart ─────────────────────────────────────────────────────────────────────────
router.get('/api/cart', (req, res) => { try { res.json({ ids: db.cartIds(req.user.id) }); } catch (err) { fail(res, err); } });
router.post('/api/cart/:id(\\d+)', (req, res) => { try { res.json({ ids: db.cartAdd(req.user.id, Number(req.params.id)) }); } catch (err) { fail(res, err); } });
router.delete('/api/cart/:id(\\d+)', (req, res) => { try { res.json({ ids: db.cartRemove(req.user.id, Number(req.params.id)) }); } catch (err) { fail(res, err); } });
router.delete('/api/cart', (req, res) => { try { res.json({ ids: db.cartClear(req.user.id) }); } catch (err) { fail(res, err); } });

// ── PDF export: a sheet of Data Matrix codes (per-medication colour) ────────────
router.post('/api/export/pdf', jsonBig, async (req, res) => {
  try {
    const b = req.body || {};
    const size = clampN(b.dm_size, 48, 300, 150);
    const title = (b.title ? String(b.title) : 'Inventario Data Matrix').slice(0, 120);
    let items;
    if (Array.isArray(b.ids) && b.ids.length) {
      if (b.ids.length > 2000) throw bad('Demasiados códigos para el PDF (máximo 2000).');
      const byId = new Map(db.listItems('activo').concat(db.listItems('utilizado')).map(i => [i.id, i]));
      items = b.ids.map(id => byId.get(Number(id))).filter(Boolean).map(publicItem);
    } else {
      items = db.listItems('activo').map(publicItem);
    }
    if (!items.length) throw bad('No hay códigos que exportar.');
    const buf = await buildItemsPdf(items, size, title);
    setDownload(res, `DataMatrix_${title.replace(/[^\w áéíóúñÁÉÍÓÚÑ-]/gi, '_').slice(0, 40)}.pdf`, 'application/pdf');
    res.send(buf);
  } catch (err) { fail(res, err); }
});

async function buildItemsPdf(items, size, title) {
  const PDFDocument = require('pdfkit');
  const bwipjs = require('bwip-js');
  const pngs = await Promise.all(items.map(it =>
    bwipjs.toBuffer({ bcid: 'datamatrix', text: it.raw, scale: 4, padding: 2, barcolor: (it.color || '#0f172a').replace('#', '') }).catch(() => null)
  ));
  return await new Promise((resolve, reject) => {
    const doc = new PDFDocument({ size: 'A4', margin: 40, info: { Title: title } });
    const chunks = [];
    doc.on('data', c => chunks.push(c));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);
    const pageW = doc.page.width, pageH = doc.page.height, M = 40;
    const usableW = pageW - 2 * M, labelH = 46, gap = 18, cellW = Math.max(size, 90);
    const cols = Math.max(1, Math.floor((usableW + gap) / (cellW + gap)));
    const cellH = size + labelH + 10, colGap = cols > 1 ? (usableW - cols * cellW) / (cols - 1) : 0;
    doc.fillColor('#0f2233').font('Helvetica-Bold').fontSize(17).text(title, M, M, { width: usableW });
    doc.fillColor('#5c7086').font('Helvetica').fontSize(9).text(`${items.length} código(s) · Gestor de Data Matrix`, M, M + 22, { width: usableW });
    let top = M + 46;
    items.forEach((it, i) => {
      const col = i % cols;
      if (i > 0 && col === 0) { top += cellH + gap; if (top + cellH > pageH - M) { doc.addPage(); top = M; } }
      const x = M + col * (cellW + colGap), y = top, dx = x + (cellW - size) / 2;
      if (pngs[i]) { try { doc.image(pngs[i], dx, y, { width: size, height: size }); } catch { /* skip */ } }
      doc.fillColor('#0f2233').font('Helvetica-Bold').fontSize(9).text(it.nombre || it.gtin || '—', x, y + size + 3, { width: cellW, align: 'center', height: 12, ellipsis: true });
      doc.fillColor('#5c7086').font('Helvetica').fontSize(7.5)
        .text(`${it.caducidad ? 'Cad ' + it.caducidad + ' · ' : ''}${it.serial ? 'Nº ' + it.serial : ''}`, x, y + size + 15, { width: cellW, align: 'center', height: 11, ellipsis: true });
      if (it.gtin) doc.fillColor('#9aa4b0').font('Courier').fontSize(7).text('GTIN ' + it.gtin, x, y + size + 26, { width: cellW, align: 'center' });
    });
    doc.end();
  });
}

module.exports = router;
