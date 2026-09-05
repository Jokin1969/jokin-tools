'use strict';

// ── Asignación de medicación — API + UI ──────────────────────────────────────────
// Mounted at /asignacion (gated by requireApp('asignacion')). Bridges two apps:
//   · people come from qr-tis   (read-only here; they must already exist there)
//   · boxes come from datamatrix (read + state changes here)
// The assignment layer (plan, monthly period, attached boxes) lives in this app's
// own database. Boxes move through three states: pre-asignada (reserved for a
// person, still in stock) → asignada (dispensed = 'utilizado' in datamatrix).

const express = require('express');
const path = require('path');
const db = require('./db');
const qrDb = require('../qr-tis/db');
const dmDb = require('../datamatrix/db');
const gs1 = require('../datamatrix/gs1');
const dmVisual = require('../datamatrix/visual');
const release = require('./release');
const email = require('./email');
const cima = require('../datamatrix/cima');
const cimaCache = require('../datamatrix/cima-cache');
const galenicaIngest = require('../galenica/ingest');
const authStore = require('../auth/store');
const { canAccess } = require('../auth/apps-registry');
const { handleHelpPdf } = require('../../lib/help-pdf');

const router = express.Router();

// Usuarios que pueden acceder a ESTA app: las notas solo se comparten entre
// ellos, nunca con el resto del hub. (Un admin ve/entra en todas las apps.)
const APP_ID = 'asignacion';
function appUsers() { return authStore.listUsers().filter(u => canAccess(u, APP_ID)); }
function appUserIds() { return new Set(appUsers().map(u => u.id)); }
const PUB = path.join(__dirname, 'public');
const json = express.json({ limit: '256kb' });
const jsonBig = express.json({ limit: '3mb' });   // bulk medication import

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[asignacion] error:', err);
  res.status(status).json({ error: err.message || 'Error en Asignación de medicación.' });
}
function bad(msg, status = 400) { const e = new Error(msg); e.status = status; return e; }

// Fill a box's medication name (and cache its box/pill images) from CIMA, by the
// box's Código Nacional. Best-effort and offline-tolerant: on failure the product
// stays a stub and can be completed later with "Actualizar desde CIMA". Never throws.
async function nameBoxFromCima(item) {
  if (!item || !item.gtin) return;
  const cn = item.cn || gs1.cnForCima({ gtin: item.gtin });
  if (!cn) return;
  const prod = dmDb.getProduct(item.gtin);
  if (prod && prod.nombre) return;                 // already named → nothing to do
  try {
    const it = await cimaCache.lookupByCnCached(cn);   // re-fetch: name + images, cached
    if (it && it.nombre) dmDb.upsertProduct(item.gtin, { nombre: it.nombre, cn: it.cn || cn });
  } catch { /* CIMA offline → leave the stub; can be completed later */ }
}

// ── Manual / Ayuda → PDF (elegant, branded) ─────────────────────────────────────
router.post('/api/help/pdf', jsonBig, (req, res) => handleHelpPdf(req, res, {
  appLabel: 'Asignación',
  filename: 'Manual_Asignacion.pdf',
  defaultTitle: 'Manual · Asignación de medicación',
  defaultSubtitle: 'Cómo preparar y asignar la medicación de cada persona, paso a paso.',
}));

// Normalise a Código Nacional + barcode pair. When `check` is true (CN-only meds),
// they must be consistent (each derives from the other): fills the missing one and
// rejects an incoherent pair, which prevents mistyped Codes.
function normCnBarcode(rawCn, rawBar, check = true) {
  let cn = rawCn ? String(rawCn).replace(/\D/g, '') || null : null;
  let barcode = rawBar ? String(rawBar).replace(/\D/g, '') || null : null;
  if (barcode && barcode.length === 14 && barcode[0] === '0') barcode = barcode.slice(1);  // GTIN-14 → EAN-13
  if (!check) return { cn, barcode };
  if (!cn && barcode) cn = cima.cnFromBarcode(barcode) || cn;
  if (cn && barcode) {
    const expected = cima.barcodeFromCn(cn);
    if (expected && expected !== barcode) {
      const real = cima.cnFromBarcode(barcode);
      throw bad(`El código de barras (${barcode}) no coincide con el Código Nacional ${cn}${real ? ` (ese barcode es del CN ${real})` : ''}. Revisa ambos.`);
    }
  }
  return { cn, barcode };
}

// Current month as 'YYYY-MM'.
function thisMonth() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; }
function cleanYm(v) { const s = String(v == null ? '' : v).trim(); return /^\d{4}-\d{2}$/.test(s) ? s : thisMonth(); }
// Today (local) as 'YYYY-MM-DD'.
function todayIso() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
// Whole days from today to an ISO date (negative = already past). null if no date.
function daysUntil(iso) { if (!iso) return null; const a = new Date(todayIso() + 'T00:00:00'), b = new Date(iso + 'T00:00:00'); if (isNaN(b)) return null; return Math.round((b - a) / 86400000); }
function cleanDate(v) { const s = String(v == null ? '' : v).trim(); return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : null; }

// ── Views of the two foreign records ─────────────────────────────────────────────
function parseGroups(str) { return String(str == null ? '' : str).split('\n').map(s => s.trim()).filter(Boolean); }
function personView(p) {
  if (!p) return null;
  const groups = parseGroups(p.group_name);
  return {
    id: p.id, pharmacy_no: p.pharmacy_no || null, nombre: p.nombre, apellidos: p.apellidos, tis: p.tis,
    groups, group_name: groups.join('; ') || null, active: p.active ? 1 : 0,
    qr_dark: p.qr_dark || null, qr_light: p.qr_light || null, qr_style: p.qr_style || null,
    qr_code: p.qr_code || null,   // real code the QR encodes (falls back to TIS); never shown as text
  };
}
function personName(p) { return p ? `${p.nombre} ${p.apellidos}`.trim() : ''; }

// A datamatrix box resolved for display (name + effective colour/shape + 3-state).
function boxView(item) {
  if (!item) return null;
  const asig_state = item.assignee_id != null ? (item.status === 'utilizado' ? 'asignada' : 'preasignada') : null;
  return {
    id: item.id, raw: item.raw, gtin: item.gtin || null, serial: item.serial || null,
    lote: item.lote || null, caducidad: item.caducidad || null, cn: item.cn || null,
    status: item.status, nombre: item.nombre || null,
    color: dmVisual.resolveColor(item.gtin, item.color),
    shape: dmVisual.resolveShape(item.gtin, item.shape),
    assignee_id: item.assignee_id != null ? item.assignee_id : null,
    assignee_name: item.assignee_name || null, asig_state,
  };
}

// Resolve one stored line into { ...line, box } (box may be null if it was deleted
// from the datamatrix inventory afterwards).
function lineView(line) {
  const item = dmDb.getItem(line.item_id);
  // Release dates now live on the medication (plan), not on the box.
  return {
    id: line.id, period_id: line.period_id, person_id: line.person_id, gtin: line.gtin,
    item_id: line.item_id, state: line.state, assigned_at: line.assigned_at, created_at: line.created_at,
    box: boxView(item),
  };
}

// The list of medications known to the datamatrix app (for the plan picker).
function medicationList(q) {
  const products = dmDb.listProducts();
  const out = products.map(p => ({
    gtin: p.gtin, cn: p.cn || null, nombre: p.nombre || null,
    color: dmVisual.resolveColor(p.gtin, p.color), shape: dmVisual.resolveShape(p.gtin, p.shape),
    available: dmDb.availableItems(p.gtin).length,
  }));
  const norm = s => String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const tokens = norm(q).split(/\s+/).filter(Boolean);
  const filtered = tokens.length
    ? out.filter(m => { const hay = norm([m.nombre, m.gtin, m.cn].join(' ')); return tokens.every(t => hay.includes(t)); })
    : out;
  filtered.sort((a, b) => norm(a.nombre || a.gtin).localeCompare(norm(b.nombre || b.gtin), 'es', { numeric: true }));
  return filtered;
}
function medMeta(gtin) {
  const p = dmDb.getProduct(gtin);
  return { gtin, nombre: p ? (p.nombre || null) : null, color: dmVisual.resolveColor(gtin, p && p.color), shape: dmVisual.resolveShape(gtin, p && p.shape) };
}

// ── UI ───────────────────────────────────────────────────────────────────────
router.get('/', (req, res) => res.sendFile(path.join(PUB, 'index.html')));
router.use('/assets', express.static(PUB));

router.get('/api/meta', (req, res) => {
  try {
    res.json({
      settings: db.getSettings(),
      qrSettings: qrDb.getSettings(),
      month: thisMonth(),
      user: { id: req.user.id, email: req.user.email, name: req.user.name || req.user.email },
      isAdmin: isAdmin(req),
      noteColors: db.NOTE_COLORS,
      notesBadge: db.notesBadge(req.user.id),
    });
  } catch (err) { fail(res, err); }
});

// ── People (search the qr-tis directory; they must exist there) ──────────────────
router.get('/api/people', (req, res) => {
  try {
    const norm = s => String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const tokens = norm(req.query.q).split(/\s+/).filter(Boolean);
    let people = qrDb.listPeople().map(personView).filter(p => p.active);
    if (tokens.length) people = people.filter(p => { const hay = norm([p.nombre, p.apellidos, p.tis, p.pharmacy_no, p.group_name].join(' ')); return tokens.every(t => hay.includes(t)); });
    people.sort((a, b) => norm(a.apellidos + ' ' + a.nombre).localeCompare(norm(b.apellidos + ' ' + b.nombre), 'es'));
    res.json({ items: people.slice(0, 200) });
  } catch (err) { fail(res, err); }
});

router.get('/api/person/:id(\\d+)', (req, res) => {
  try {
    const p = qrDb.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'La persona no está en la base de datos de QR (TIS). Añádela allí primero.' });
    res.json({ person: personView(p), qrSettings: qrDb.getSettings() });
  } catch (err) { fail(res, err); }
});

// ── Medications (from datamatrix, for the plan picker) ───────────────────────────
router.get('/api/medications', (req, res) => {
  try { res.json({ items: medicationList(req.query.q || '') }); } catch (err) { fail(res, err); }
});
// ── Bulk import: add medications (by Código Nacional) to people's plans ───────────
// Each row = { person: "<TIS or Nº farmacia or id>", cns: ["885442", …] }. For each
// CN we look it up in CIMA (cached) to fill name + barcode, then add it to the plan
// (CN-only, "pendiente de caja"). Re-importing the same CN just updates it.
router.post('/api/plan/import', jsonBig, async (req, res) => {
  try {
    const b = req.body || {};
    const by = b.by === 'pharmacy' ? 'pharmacy' : 'tis';
    const qty = Math.min(99, Math.max(1, Math.round(Number(b.qty) || 1)));
    const rows = Array.isArray(b.rows) ? b.rows : [];
    if (!rows.length) throw bad('No se recibieron filas para importar.');
    if (rows.length > 1000) throw bad('Demasiadas filas (máximo 1000).');
    // Resolve people by the chosen identifier. Compare with leading zeros stripped
    // so "7001" matches the stored "07001" (and the same for the 8-digit TIS).
    const strip = v => String(v == null ? '' : v).replace(/\D/g, '').replace(/^0+/, '');
    const all = qrDb.listPeople();
    const byTis = new Map(all.map(p => [strip(p.tis), p]));
    const byPh = new Map(all.filter(p => p.pharmacy_no && p.pharmacy_no !== '00000').map(p => [strip(p.pharmacy_no), p]));
    const byId = new Map(all.map(p => [String(p.id), p]));
    // Try the chosen identifier first, then fall back to the *other* one (and the
    // raw id) so a person that exists in QR (TIS) is found even when pasted under
    // the "wrong" column — e.g. a Nº de farmacia while importing «por TIS». Once
    // resolved, addPlanMed below creates the (empty) plan and adds the medication.
    const resolve = (code) => {
      const k = strip(code);
      const primary = by === 'pharmacy' ? byPh : byTis;
      const secondary = by === 'pharmacy' ? byTis : byPh;
      return primary.get(k) || secondary.get(k) || byId.get(String(code == null ? '' : code).trim()) || null;
    };
    // Parse rows + collect distinct valid CNs for a single CIMA pass.
    const cnSet = new Set();
    const parsed = rows.map((r, i) => {
      const cns = (Array.isArray(r.cns) ? r.cns : []).map(x => String(x).replace(/\D/g, '')).filter(x => /^\d{4,7}$/.test(x));
      cns.forEach(c => cnSet.add(c));
      return { line: i + 1, code: r.person, person: resolve(r.person), cns };
    });
    // CIMA lookups (cached; tolerant of offline), limited concurrency.
    const info = new Map(); let cimaReached = false, cimaFound = 0;
    const cnList = [...cnSet], CONC = 5;
    for (let k = 0; k < cnList.length; k += CONC) {
      await Promise.all(cnList.slice(k, k + CONC).map(async cn => {
        try { const it = await cimaCache.lookupByCnCached(cn); if (it) { cimaReached = true; info.set(cn, it); if (it.nombre) cimaFound++; } }
        catch { /* offline / not found → add without CIMA info */ }
      }));
    }
    // Apply to plans.
    let added = 0, updated = 0; const errors = [];
    const seenPeople = new Set();
    const unrecByPerson = new Map();   // personId → Set(cns) whose CIMA name wasn't found
    for (const row of parsed) {
      if (!row.person) { errors.push({ line: row.line, code: row.code, error: 'Persona no encontrada en QR (TIS).' }); continue; }
      if (!row.cns.length) { errors.push({ line: row.line, code: row.code, error: 'Sin Códigos Nacionales válidos.' }); continue; }
      // Ensure the plan exists (created empty if the person had none yet) before
      // adding the imported medications.
      if (!seenPeople.has(row.person.id)) { try { db.createEmptyPlan(row.person.id, req.user.id); } catch { /* */ } }
      seenPeople.add(row.person.id);
      for (const cn of row.cns) {
        try {
          const it = info.get(cn) || {};
          const existed = !!db.planByCn(row.person.id, cn);
          db.addPlanMed(row.person.id, { cn, nombre: it.nombre || `Medicamento CN ${cn}`, barcode: it.barcode || null, qty });
          if (existed) updated++; else added++;
          if (!it.nombre) {   // CN not recognised by CIMA → flag on the person's note
            if (!unrecByPerson.has(row.person.id)) unrecByPerson.set(row.person.id, new Set());
            unrecByPerson.get(row.person.id).add(cn);
          }
        } catch (e) { errors.push({ line: row.line, code: row.code, cn, error: e.message }); }
      }
    }
    cnList.forEach(cn => galenicaIngest.ingestCn(cn));   // feed hacia Galénica (fire-and-forget)
    // For people who got a medication with an unrecognised CN, leave a post-it note
    // (the same one shown by «Añadir nota»), without clobbering an existing note.
    let noted = 0;
    for (const [pid, cnSetP] of unrecByPerson) {
      try {
        const cnsArr = [...cnSetP].sort();
        const warn = `⚠️ Tiene una medicación cuyo código nacional (CN) no ha sido reconocido (CN ${cnsArr.join(', ')}). Complétala con «🔎 CIMA» o ✏️.`;
        const existing = db.getEntNote('person', pid);
        if (!existing) { db.setEntNote('person', pid, { text: warn, color: '#FED7AA' }, req.user.id); noted++; }
        else if (!/no ha sido reconocido/i.test(existing.text || '')) { db.setEntNote('person', pid, { text: `${existing.text}\n${warn}`, color: existing.color || '#FED7AA' }, req.user.id); noted++; }
      } catch { /* nota es best-effort */ }
    }
    // Which CNs got NO usable data from CIMA (added with only their Código Nacional).
    // Include the derived barcode and how many people/rows carry each, so they're
    // easy to identify and complete later.
    const missingCns = cnList
      .filter(cn => !(info.get(cn) && info.get(cn).nombre))
      .map(cn => ({
        cn,
        barcode: cima.barcodeFromCn(cn) || null,
        people: parsed.filter(r => r.person && r.cns.includes(cn)).length,
      }))
      .sort((a, b) => a.cn.localeCompare(b.cn));
    res.json({ ok: true, people: seenPeople.size, added, updated, noted, cima: { reached: cimaReached, found: cimaFound, missing: cnSet.size - cimaFound, total: cnSet.size, missingCns }, errors });
  } catch (err) { fail(res, err); }
});
// ── CIMA (AEMPS) lookup — optional: fill name/barcode from a Código Nacional ──────
router.get('/api/cima/cn/:cn([0-9]+)', async (req, res) => {
  try {
    if (req.query.debug) return res.json(await cima.probeByCn(req.params.cn));  // raw + mapped, to verify field names
    res.json({ item: await cimaCache.lookupByCnCached(req.params.cn) });        // cached + offline fallback
  } catch (err) { res.status(err.status || 502).json({ error: err.message, offline: !!err.offline }); }
});
// Serve a medication photo (box/pill) from the local cache (works offline).
// Uses revalidation (ETag) instead of a long max-age so that when a photo is
// refreshed in CIMA (e.g. thumbnail → full-size), the browser picks up the new
// image immediately instead of showing the stale cached one.
router.get('/api/cima/foto/:cn([0-9]+)/:tipo(caja|pastilla)', async (req, res) => {
  try {
    const buf = await cimaCache.foto(req.params.cn, req.params.tipo);
    if (!buf) return res.status(404).end();
    const row = dmDb.cimaCacheGet(String(req.params.cn).replace(/\D/g, ''));
    const etag = `"${req.params.cn}-${req.params.tipo}-${(row && row.updated_at) || ''}-${buf.length}"`;
    res.set('Content-Type', 'image/jpeg');
    res.set('Cache-Control', 'no-cache');   // may store, but must revalidate before reuse
    res.set('ETag', etag);
    if (req.headers['if-none-match'] === etag) return res.status(304).end();
    res.send(buf);
  } catch { res.status(404).end(); }
});
router.get('/api/cima/search', async (req, res) => {
  try { res.json({ items: await cima.searchByName(req.query.q || '') }); }
  catch (err) { res.status(err.status || 502).json({ error: err.message, offline: !!err.offline }); }
});
// Boxes available to pre-assign for a medication (activo + not reserved).
router.get('/api/available/:gtin([0-9A-Za-z]+)', (req, res) => {
  try { res.json({ items: dmDb.availableItems(req.params.gtin).map(boxView) }); } catch (err) { fail(res, err); }
});
// Available boxes for a plan medication that has only a Código Nacional (no GTIN yet).
router.get('/api/available-cn/:cn([0-9A-Za-z]+)', (req, res) => {
  try { res.json({ items: dmDb.availableItemsByCn(req.params.cn).map(boxView) }); } catch (err) { fail(res, err); }
});

// ── Plan (recurring medications per person) ──────────────────────────────────────
function planView(personId) {
  return db.listPlan(personId).map(l => {
    const hasGtin = !!l.gtin;
    const cat = hasGtin ? medMeta(l.gtin) : null;
    const nombre = (cat && cat.nombre) || l.nombre || null;
    const color = dmVisual.resolveColor(l.gtin, cat && cat.color);
    const shape = dmVisual.resolveShape(l.gtin, cat && cat.shape);
    const available = hasGtin ? dmDb.availableItems(l.gtin).length : (l.cn ? dmDb.availableItemsByCn(l.cn).length : 0);
    // Release date lives on the medication (recurring). It drives the state:
    // sin_fecha (permanent, needs a date) → programada (before effective) → disponible.
    const advance_days = l.advance_days == null ? db.DEFAULT_ADVANCE : l.advance_days;
    const effective_at = db.effectiveDate(l.release_at, advance_days);
    const effective_days = daysUntil(effective_at);
    const release_state = !l.release_at ? 'sin_fecha' : (effective_days != null && effective_days <= 0 ? 'disponible' : 'programada');
    // Barcode ("precinto") for scanning into Salud when there's no Data Matrix.
    const eanFromGtin = (g) => (g && g.length === 14 && g[0] === '0') ? g.slice(1) : g;
    const barcode = l.barcode || (l.cn ? cima.barcodeFromCn(l.cn) : null) || (l.gtin ? eanFromGtin(l.gtin) : null);
    // Cached CIMA photos (by Código Nacional) for this medication.
    const cc = l.cn ? dmDb.cimaCacheGet(l.cn) : null;
    const dose = db.getDoseScheduleForDate(l.id);   // pauta vigente hoy (Pastillero); null = sin definir
    return {
      id: l.id, gtin: l.gtin || null, cn: l.cn || null, barcode,
      qty: l.qty, notes: l.notes || null, active: l.active, si_precisa: !!l.si_precisa,
      nombre, color, shape, available, cn_only: !hasGtin,
      release_at: l.release_at || null, advance_days, effective_at, effective_days, release_state,
      foto_caja: !!(cc && cc.has_caja), foto_pastilla: !!(cc && cc.has_pastilla),
      dose: dose ? { desayuno: dose.desayuno, comida: dose.comida, cena: dose.cena, noche: dose.noche, effective_from: dose.effective_from } : null,
    };
  });
}
router.get('/api/person/:id(\\d+)/plan', (req, res) => {
  try {
    const p = qrDb.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada en QR (TIS).' });
    res.json({ plan: planView(p.id) });
  } catch (err) { fail(res, err); }
});
router.post('/api/person/:id(\\d+)/plan', json, (req, res) => {
  try {
    const p = qrDb.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada en QR (TIS).' });
    const b = req.body || {};
    const gtin = b.gtin ? gs1.normGtin(b.gtin) : null;
    const nombre = b.nombre ? String(b.nombre).trim() : null;
    // CN ⇄ barcode se derivan uno del otro: rellena el que falte y valida la pareja.
    const { cn, barcode } = normCnBarcode(b.cn, b.barcode, !gtin);
    const si_precisa = !!b.si_precisa;
    if (gtin && gtin.replace(/^0+/, '').length >= 8) {
      // Catalogued path: the GTIN must exist in the Data Matrix app.
      const known = dmDb.getProduct(gtin) || dmDb.availableItems(gtin).length || dmDb.listItems('utilizado').some(i => i.gtin === gtin);
      if (!known) throw bad('Ese medicamento no está en la app Data Matrix. Añádelo allí primero (escanea una caja o impórtalo).');
      db.addPlanMed(p.id, { gtin, qty: b.qty, notes: b.notes, nombre, barcode, cn, si_precisa });
    } else if (cn) {
      // CN-only path (info before Data Matrix). Promote to catalogued if the CN is
      // already known in the medication catalogue; otherwise keep it CN-only.
      const prod = dmDb.listProducts().find(x => x.cn && String(x.cn) === cn);
      if (prod) db.addPlanMed(p.id, { gtin: prod.gtin, qty: b.qty, notes: b.notes, nombre: nombre || prod.nombre, barcode, cn, si_precisa });
      else {
        if (!nombre) throw bad('Indica el nombre del medicamento.');
        db.addPlanMed(p.id, { cn, nombre, barcode, qty: b.qty, notes: b.notes, si_precisa });
      }
    } else {
      throw bad('Indica el GTIN o el Código Nacional del medicamento.');
    }
    galenicaIngest.ingestCn(cn);   // feed hacia Galénica (fire-and-forget)
    res.json({ plan: planView(p.id) });
  } catch (err) { fail(res, err); }
});
router.patch('/api/plan/:id(\\d+)', json, (req, res) => {
  try {
    const line = db.getPlanLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Línea de plan no encontrada.' });
    const b = req.body || {};
    if (b.qty !== undefined || b.notes !== undefined || b.active !== undefined || b.si_precisa !== undefined) {
      db.updatePlanById(line.id, { qty: b.qty, notes: b.notes, active: b.active, si_precisa: b.si_precisa });
    }
    // Edit the medication itself (name; and CN/barcode for CN-only meds).
    if (b.nombre !== undefined || b.cn !== undefined || b.barcode !== undefined) {
      const edit = { nombre: b.nombre !== undefined ? b.nombre : undefined };
      if (!line.gtin && (b.cn !== undefined || b.barcode !== undefined)) {
        const { cn, barcode } = normCnBarcode(b.cn !== undefined ? b.cn : line.cn, b.barcode !== undefined ? b.barcode : line.barcode, true);
        if (!cn) throw bad('Indica el Código Nacional.');
        const dup = db.planByCn(line.person_id, cn);           // no duplicar CN en la misma persona
        if (dup && dup.id !== line.id) throw bad('Ya tienes otro medicamento con ese Código Nacional en el plan.');
        edit.cn = cn; edit.barcode = barcode;
      }
      db.editPlanMed(line.id, edit);
      if (edit.cn) galenicaIngest.ingestCn(edit.cn);   // feed hacia Galénica (fire-and-forget)
    }
    res.json({ plan: planView(line.person_id) });
  } catch (err) { fail(res, err); }
});
router.delete('/api/plan/:id(\\d+)', (req, res) => {
  try {
    const line = db.getPlanLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Línea de plan no encontrada.' });
    db.deletePlanLine(line.id);
    res.json({ plan: planView(line.person_id) });
  } catch (err) { fail(res, err); }
});
// Set/clear the official Salud release date and/or the anticipation of a plan
// medication (recurring). The effective date derives from both.
router.put('/api/plan/:id(\\d+)/release', json, (req, res) => {
  try {
    const line = db.getPlanLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Línea de plan no encontrada.' });
    const b = req.body || {};
    if (b.date !== undefined) {
      const date = String(b.date == null ? '' : b.date).trim();
      if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) throw bad('Fecha no válida (AAAA-MM-DD).');
      db.setPlanRelease(line.id, date || null);
    }
    if (b.advance_days !== undefined) {
      const n = Math.round(Number(b.advance_days));
      if (!Number.isFinite(n) || n < 0 || n > 365) throw bad('Días de anticipación no válidos (0–365).');
      db.setPlanAdvance(line.id, n);
    }
    res.json({ plan: planView(line.person_id) });
  } catch (err) { fail(res, err); }
});

// ── Pauta por franja (Pastillero) ─────────────────────────────────────────────
// Change the dose distribution FROM a given date onward (default today). Never
// retroactive: a new row, the old ones stay for history. Next month automatically
// keeps the last one in effect — nothing to "carry over" by hand.
router.put('/api/plan/:id(\\d+)/dose', json, (req, res) => {
  try {
    const line = db.getPlanLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Línea de plan no encontrada.' });
    const b = req.body || {};
    const from = String(b.effective_from == null ? '' : b.effective_from).trim();
    if (from && !/^\d{4}-\d{2}-\d{2}$/.test(from)) throw bad('Fecha no válida (AAAA-MM-DD).');
    const history = db.setDoseSchedule(line.id, from || undefined, b, req.user.id);
    res.json({ history, plan: planView(line.person_id) });
  } catch (err) { fail(res, err); }
});
router.get('/api/plan/:id(\\d+)/dose', (req, res) => {
  try {
    const line = db.getPlanLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Línea de plan no encontrada.' });
    res.json({ history: db.getDoseHistory(line.id), today: db.getDoseScheduleForDate(line.id, req.query.date) });
  } catch (err) { fail(res, err); }
});

// ── Ficha (person + period + attached boxes + plan progress) ─────────────────────
function fichaPayload(person, ym) {
  const period = db.findPeriod(person.id, ym); // may be null until the first box is attached
  const lines = period ? db.listLines(period.id).map(lineView) : [];
  // Per-medication progress within this period.
  const byGtin = new Map();
  for (const ln of lines) {
    const g = ln.gtin || (ln.box && ln.box.gtin) || '—';
    if (!byGtin.has(g)) byGtin.set(g, { attached: 0, asignada: 0, itemId: null, asignadaItemId: null });
    const e = byGtin.get(g); e.attached++;
    if (e.itemId == null) e.itemId = ln.item_id;
    if (ln.state === 'asignada') { e.asignada++; if (e.asignadaItemId == null) e.asignadaItemId = ln.item_id; }
  }
  const precByPlan = period ? db.precintoCountByPlan(period.id) : new Map();
  const plan = planView(person.id).map(pl => {
    const prog = byGtin.get(pl.gtin) || { attached: 0, asignada: 0, itemId: null, asignadaItemId: null };
    const prec = precByPlan.get(pl.id) || 0;   // asignados por precinto (sin caja)
    // The Data Matrix box linked to this med THIS MONTH (prefer the assigned one) —
    // to drive the plan card's state button and its link to the DM ficha.
    return { ...pl, boxes: prog.attached, attached: prog.attached + prec, asignada: prog.asignada + prec, precinto: prec, box_item_id: prog.asignadaItemId || prog.itemId || null };
  });
  const precintos = period ? db.listPrecinto(period.id).map(r => ({ id: r.id, plan_id: r.plan_id, gtin: r.gtin, cn: r.cn, barcode: r.barcode, nombre: r.nombre, assigned_at: r.assigned_at })) : [];
  const counts = period ? db.periodCounts(period.id) : { preasignada: 0, asignada: 0, total: 0 };
  const planned_total = plan.filter(p => p.active).reduce((s, p) => s + p.qty, 0);
  const periods = db.listPeriods(person.id).map(pr => ({ id: pr.id, ym: pr.ym, status: pr.status, counts: db.periodCounts(pr.id) }));
  return {
    person: personView(person), qrSettings: qrDb.getSettings(),
    month: thisMonth(), ym,
    period: period ? { id: period.id, ym: period.ym, status: period.status, created_at: period.created_at, closed_at: period.closed_at } : { id: null, ym, status: 'nuevo' },
    periods, plan, lines, precintos, note: db.getEntNote('person', person.id),
    progress: { planned_total, attached_total: counts.total, asignada_total: counts.asignada, pre_total: counts.preasignada },
  };
}
router.get('/api/person/:id(\\d+)/ficha', (req, res) => {
  try {
    const p = qrDb.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'La persona no está en QR (TIS). Añádela allí primero.' });
    res.json(fichaPayload(p, cleanYm(req.query.ym)));
  } catch (err) { fail(res, err); }
});

// ── Overview (dashboard: who needs assigning this month) ─────────────────────────
router.get('/api/overview', (req, res) => {
  try {
    const month = thisMonth();
    const today = todayIso();
    // Boxes ready to assign (EFFECTIVE date reached), bucketed by person.
    // Medications available now (effective date reached), bucketed by person.
    const readyBy = new Map();
    for (const pm of db.plansForRelease()) {
      const eff = db.effectiveDate(pm.release_at, pm.advance_days);
      if (eff && eff <= today) readyBy.set(pm.person_id, (readyBy.get(pm.person_id) || 0) + 1);
    }
    const ids = new Set([...db.planPersonIds(), ...db.periodPersonIds()]);
    const pnotes = db.entNotesMap('person');
    const rows = [];
    for (const id of ids) {
      const p = qrDb.getPerson(id);
      if (!p) continue; // person deleted from qr-tis
      const plan = db.listPlan(id).filter(l => l.active);
      const planned_total = plan.reduce((s, l) => s + l.qty, 0);
      const period = db.findPeriod(id, month);
      const counts = period ? db.periodCounts(period.id) : { preasignada: 0, asignada: 0, total: 0 };
      const latest = db.latestPeriod(id);
      rows.push({
        person: personView(p), plan_count: plan.length, planned_total,
        month_counts: counts, has_month_period: !!period,
        ready_count: readyBy.get(id) || 0,
        latest: latest ? { ym: latest.ym, status: latest.status } : null,
        note: pnotes.get(String(id)) || null,
        // Searchable text of this person's plan medications (CN · nombre · barcode),
        // for the "buscar por medicamento" filter in the overview.
        med_search: plan.map(l => `${l.cn || ''} ${l.nombre || ''} ${l.barcode || ''}`).join(' '),
      });
    }
    const norm = s => String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    rows.sort((a, b) => norm(a.person.apellidos + ' ' + a.person.nombre).localeCompare(norm(b.person.apellidos + ' ' + b.person.nombre), 'es'));
    res.json({ month, items: rows });
  } catch (err) { fail(res, err); }
});

// ── Disponibilidad de medicamentos (dashboard: quién puede ya recoger algo) ───────
// Per person, splits the active plan into normales / eventuales (si_precisa) and,
// for each side, counts how many are "disponibles" hoy (effective date reached) and
// the OLDEST such date (the one available the longest — most overdue to dispense).
router.get('/api/plan-availability', (req, res) => {
  try {
    const today = todayIso();
    const stat = (lines) => {
      let disp = 0, oldest_days = null, oldest_at = null;
      for (const l of lines) {
        const adv = l.advance_days == null ? db.DEFAULT_ADVANCE : l.advance_days;
        const eff = db.effectiveDate(l.release_at, adv);
        if (eff && eff <= today) {
          disp++;
          const days = daysUntil(eff);
          if (oldest_days === null || days < oldest_days) { oldest_days = days; oldest_at = eff; }
        }
      }
      return { total: lines.length, disp, oldest_days, oldest_at };
    };
    const rows = [];
    for (const id of db.planPersonIds()) {
      const p = qrDb.getPerson(id);
      if (!p) continue; // person deleted from qr-tis
      const plan = db.listPlan(id).filter(l => l.active);
      if (!plan.length) continue;
      const n = stat(plan.filter(l => !l.si_precisa));
      const e = stat(plan.filter(l => l.si_precisa));
      rows.push({
        person: personView(p),
        normal_total: n.total, normal_disp: n.disp, normal_oldest_days: n.oldest_days, normal_oldest_at: n.oldest_at,
        eventual_total: e.total, eventual_disp: e.disp, eventual_oldest_days: e.oldest_days, eventual_oldest_at: e.oldest_at,
      });
    }
    res.json({ today, items: rows });
  } catch (err) { fail(res, err); }
});

// ── Per-user cart of people ──────────────────────────────────────────────────────
function cartPayload(userId) {
  const ids = db.cartIds(userId);
  const pnotes = db.entNotesMap('person');
  const items = ids.map(id => { const p = qrDb.getPerson(id); return p ? { person: personView(p), note: pnotes.get(String(id)) || null } : null; }).filter(Boolean);
  return { ids, items };
}
router.get('/api/cart', (req, res) => { try { res.json(cartPayload(req.user.id)); } catch (err) { fail(res, err); } });
router.post('/api/cart/:id(\\d+)', (req, res) => { try { db.cartAdd(req.user.id, Number(req.params.id)); res.json(cartPayload(req.user.id)); } catch (err) { fail(res, err); } });
router.delete('/api/cart/:id(\\d+)', (req, res) => { try { db.cartRemove(req.user.id, Number(req.params.id)); res.json(cartPayload(req.user.id)); } catch (err) { fail(res, err); } });
router.delete('/api/cart', (req, res) => { try { db.cartClear(req.user.id); res.json(cartPayload(req.user.id)); } catch (err) { fail(res, err); } });

// ── Period lifecycle ─────────────────────────────────────────────────────────────
router.post('/api/person/:id(\\d+)/period', json, (req, res) => {
  try {
    const p = qrDb.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada en QR (TIS).' });
    const ym = cleanYm(req.body && req.body.ym);
    db.getOrCreatePeriod(p.id, ym, req.user.id);
    res.json(fichaPayload(p, ym));
  } catch (err) { fail(res, err); }
});
router.post('/api/period/:id(\\d+)/close', (req, res) => {
  try { const pr = db.getPeriod(Number(req.params.id)); if (!pr) return res.status(404).json({ error: 'Periodo no encontrado.' }); db.setPeriodStatus(pr.id, 'cerrado'); const p = qrDb.getPerson(pr.person_id); res.json(fichaPayload(p, pr.ym)); }
  catch (err) { fail(res, err); }
});
router.post('/api/period/:id(\\d+)/reopen', (req, res) => {
  try { const pr = db.getPeriod(Number(req.params.id)); if (!pr) return res.status(404).json({ error: 'Periodo no encontrado.' }); db.setPeriodStatus(pr.id, 'abierto'); const p = qrDb.getPerson(pr.person_id); res.json(fichaPayload(p, pr.ym)); }
  catch (err) { fail(res, err); }
});

// ── The core: attach (pre-assign), assign, unassign, remove ──────────────────────
// Pre-assign a box to a person for a month. Accepts an existing box id, or a raw
// Data Matrix (scanned) — creating the box in the datamatrix app if it's new, so
// the two apps never drift apart.
router.post('/api/person/:id(\\d+)/preassign', json, async (req, res) => {
  try {
    const p = qrDb.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'La persona no está en QR (TIS). Añádela allí primero.' });
    const b = req.body || {};
    const ym = cleanYm(b.ym);

    // Resolve the box: by id, or by scanning a raw code (create it if unknown).
    let item = null;
    if (b.item_id != null) {
      item = dmDb.getItem(Number(b.item_id));
      if (!item) throw bad('La caja no existe en la app Data Matrix.');
    } else {
      const raw = String(b.raw == null ? '' : b.raw).trim();
      if (!raw) throw bad('No se recibió ninguna caja (id o Data Matrix).');
      const f = gs1.parse(raw);
      const data = { raw, box_key: gs1.boxKey(f, raw), gtin: gs1.normGtin(f.gtin), serial: f.serial, lote: f.lote, caducidad: gs1.expiryToIso(f.caducidad), cn: gs1.cnForCima(f) };
      item = dmDb.findByKey(data.box_key);
      if (!item) {
        item = dmDb.createItem(data, req.user.id);
        if (data.gtin && !dmDb.getProduct(data.gtin)) dmDb.upsertProduct(data.gtin, {});
        galenicaIngest.ingestCn(data.cn);   // feed hacia Galénica (fire-and-forget)
      }
    }
    // Enrich from CIMA (name + box/pill images) so a scanned box never associates
    // with incomplete info; re-read to reflect the resolved name in the response.
    await nameBoxFromCima(item);
    item = dmDb.getItem(item.id) || item;

    // Validate the box can be reserved for this person.
    if (item.status === 'utilizado' && item.assignee_id !== p.id) {
      throw bad(item.assignee_id ? `Esa caja ya está asignada a ${item.assignee_name || 'otra persona'}.` : 'Esa caja ya está marcada como utilizada en Data Matrix.');
    }
    if (item.assignee_id != null && item.assignee_id !== p.id) {
      throw bad(`Esa caja ya está pre-asignada a ${item.assignee_name || 'otra persona'}.`);
    }

    // If we're linking the box to a specific plan medication, check it matches
    // (by GTIN or Código Nacional). On mismatch, warn (409) unless forced.
    const planId = b.plan_id != null ? Number(b.plan_id) : null;
    let planMed = planId ? db.getPlanLine(planId) : null;
    if (planMed && planMed.person_id === p.id) {
      const matches = (planMed.gtin && item.gtin && planMed.gtin === item.gtin) || (planMed.cn && item.cn && planMed.cn === item.cn);
      if (!matches && !b.force) {
        return res.status(409).json({
          error: 'La caja escaneada no parece del mismo medicamento del plan.', mismatch: true,
          box: { nombre: item.nombre || null, gtin: item.gtin || null, cn: item.cn || null },
          med: { nombre: planMed.nombre || null, gtin: planMed.gtin || null, cn: planMed.cn || null },
        });
      }
    }

    const period = db.getOrCreatePeriod(p.id, ym, req.user.id);
    const existing = db.findLine(period.id, item.id);
    if (!existing) {
      dmDb.setAssignee(item.id, p.id, personName(p), p.pharmacy_no || null, parseGroups(p.group_name).join(" · ") || null);
      db.addLine({ period_id: period.id, person_id: p.id, gtin: item.gtin, item_id: item.id, box_key: item.box_key, state: 'preasignada' });
    }
    // A CN-only plan med "graduates" to catalogued once we know the box's GTIN.
    if (planMed && !planMed.gtin && item.gtin) db.reconcilePlanGtin(planMed.id, item.gtin);
    res.json(fichaPayload(p, ym));
  } catch (err) { fail(res, err); }
});

// ── DM → candidate people (the "conexión del CN") ───────────────────────────────
// Given a Data Matrix, return every person whose plan has that medication (by CN or
// GTIN) so the box can be associated to one of them. Also resolves the box name from
// CIMA and reports the box's current state.
router.post('/api/dm/candidates', json, async (req, res) => {
  try {
    const raw = String((req.body && req.body.raw) == null ? '' : req.body.raw).trim();
    if (!raw) throw bad('Escanea o pega una Data Matrix.');
    const f = gs1.parse(raw);
    const gtin = gs1.normGtin(f.gtin);
    const cn = gs1.cnForCima(f);
    if (!gtin && !cn) throw bad('No he podido leer el GTIN ni el Código Nacional de esa Data Matrix.');
    // Name: DM catalogue by GTIN, else CIMA (cached, tolerant), else the CN cache.
    let nombre = null;
    if (gtin) { const prod = dmDb.getProduct(gtin); if (prod && prod.nombre) nombre = prod.nombre; }
    if (!nombre && cn) { try { const it = await cimaCache.lookupByCnCached(cn); if (it && it.nombre) nombre = it.nombre; } catch { /* offline */ } }
    if (!nombre && cn) { const cc = dmDb.cimaCacheGet(String(cn).replace(/\D/g, '')); if (cc && cc.nombre) nombre = cc.nombre; }
    const box_key = gs1.boxKey(f, raw);
    const existing = dmDb.findByKey(box_key);
    const dm = {
      raw, gtin, cn, nombre, caducidad: gs1.expiryToIso(f.caducidad), serial: f.serial || null,
      state: existing ? (existing.assignee_id != null ? (existing.status === 'utilizado' ? 'asignada' : 'asociada') : (existing.status === 'utilizado' ? 'utilizada' : 'libre')) : 'nueva',
      assignee_id: existing ? (existing.assignee_id != null ? existing.assignee_id : null) : null,
      assignee_name: existing ? (existing.assignee_name || null) : null,
    };
    let candidates = [];
    for (const pl of db.plansByCnOrGtin(cn, gtin)) {
      const person = qrDb.getPerson(pl.person_id);
      if (!person || !person.active) continue;
      candidates.push({
        person: personView(person),
        plan_id: pl.id,
        med: { nombre: pl.nombre || nombre || null, cn: pl.cn || null, gtin: pl.gtin || null, qty: pl.qty || 1 },
      });
    }
    // If the box is already associated/assigned, show ONLY that person.
    if (dm.assignee_id != null) candidates = candidates.filter(c => c.person.id === dm.assignee_id);
    res.json({ dm, candidates });
  } catch (err) { fail(res, err); }
});

// Assign for real (the click during the health-app assignment): box → 'utilizado'.
// Assign for real (send to Salud). This is also where the NEXT release date of the
// medication is captured: the box is gone, but the medication returns next month.
router.post('/api/line/:id(\\d+)/assign', json, (req, res) => {
  try {
    const line = db.getLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Asignación no encontrada.' });
    const b = req.body || {};
    const next = String(b.next_release_at == null ? '' : b.next_release_at).trim();
    if (next && !/^\d{4}-\d{2}-\d{2}$/.test(next)) throw bad('Fecha de la próxima liberación no válida (AAAA-MM-DD).');
    dmDb.setUsed(line.item_id, true);            // keeps the assignee link
    db.setLineState(line.id, 'asignada');
    // Record the medication's next Salud release date (recurring, on the plan).
    if (b.next_release_at !== undefined) {
      const item = dmDb.getItem(line.item_id);
      const med = db.planForItem(line.person_id, line.gtin || (item && item.gtin), item && item.cn);
      if (med) db.setPlanRelease(med.id, next || null);
    }
    const pr = db.getPeriod(line.period_id); const p = qrDb.getPerson(line.person_id);
    res.json(fichaPayload(p, pr.ym));
  } catch (err) { fail(res, err); }
});
// Revert an assignment (box back to stock, still pre-asignada for the person).
router.post('/api/line/:id(\\d+)/unassign', (req, res) => {
  try {
    const line = db.getLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Asignación no encontrada.' });
    dmDb.setUsed(line.item_id, false);
    db.setLineState(line.id, 'preasignada');
    const pr = db.getPeriod(line.period_id); const p = qrDb.getPerson(line.person_id);
    res.json(fichaPayload(p, pr.ym));
  } catch (err) { fail(res, err); }
});
// Mark a plan medication as assigned in Salud WITHOUT a box, via its "precinto"
// (barcode). One call = one unit. Also captures the medication's next release date.
router.post('/api/person/:id(\\d+)/assign-precinto', json, (req, res) => {
  try {
    const p = qrDb.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    const b = req.body || {};
    const med = db.getPlanLine(Number(b.plan_id));
    if (!med || med.person_id !== p.id) throw bad('Medicamento del plan no encontrado.');
    const ym = cleanYm(b.ym);
    const next = String(b.next_release_at == null ? '' : b.next_release_at).trim();
    if (next && !/^\d{4}-\d{2}-\d{2}$/.test(next)) throw bad('Fecha de la próxima liberación no válida (AAAA-MM-DD).');
    const period = db.getOrCreatePeriod(p.id, ym, req.user.id);
    db.addPrecinto({ period_id: period.id, person_id: p.id, plan_id: med.id, gtin: med.gtin, cn: med.cn, barcode: med.barcode, nombre: med.nombre }, req.user.id);
    if (b.next_release_at !== undefined) db.setPlanRelease(med.id, next || null);
    res.json(fichaPayload(p, ym));
  } catch (err) { fail(res, err); }
});
// Revert a precinto assignment.
router.delete('/api/precinto/:id(\\d+)', (req, res) => {
  try {
    const r = db.getPrecinto(Number(req.params.id)); if (!r) return res.status(404).json({ error: 'No encontrado.' });
    db.deletePrecinto(r.id);
    const pr = db.getPeriod(r.period_id); const p = qrDb.getPerson(r.person_id);
    res.json(fichaPayload(p, pr ? pr.ym : cleanYm()));
  } catch (err) { fail(res, err); }
});
// Scanner endpoint: resolve a scanned code (Data Matrix or barcode/precinto) to a
// plan medication of this person and mark it assigned. For "scanner mode": the
// scanner types the code + Enter, and we assign directly.
router.post('/api/person/:id(\\d+)/scan', json, async (req, res) => {
  try {
    const p = qrDb.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    const b = req.body || {};
    const ym = cleanYm(b.ym);
    const raw = String(b.code == null ? '' : b.code).trim();
    if (!raw) throw bad('Código vacío.');

    // Identify the medication: GS1 Data Matrix (has a GTIN) or a plain EAN-13 precinto.
    const f = gs1.parse(raw);
    const digits = raw.replace(/\D/g, '');
    let gtin = null, cn = null, isDm = false;
    if (f && f.gtin) { gtin = gs1.normGtin(f.gtin); cn = gs1.cnForCima(f) || null; isDm = true; }
    else if (/^\d{12,14}$/.test(digits)) {
      const ean = digits.length === 14 && digits[0] === '0' ? digits.slice(1) : digits;
      cn = cima.cnFromBarcode(ean); gtin = cn ? cima.gtinFromCn(cn) : null;
    } else throw bad('No reconozco el código escaneado.');

    const med = db.planForItem(p.id, gtin, cn);
    if (!med) return res.status(409).json({ error: 'Ese medicamento no está en el plan de esta persona.', nomatch: true, gtin, cn });

    const period = db.getOrCreatePeriod(p.id, ym, req.user.id);
    const nextDate = db.nextMonthSameDay(med.release_at);
    let mode;
    if (isDm) {
      const data = { raw, box_key: gs1.boxKey(f, raw), gtin, serial: f.serial, lote: f.lote, caducidad: gs1.expiryToIso(f.caducidad), cn };
      let item = dmDb.findByKey(data.box_key) || dmDb.createItem(data, req.user.id);
      if (item.assignee_id != null && item.assignee_id !== p.id) throw bad(`Esa caja ya está asociada a ${item.assignee_name || 'otra persona'}.`);
      await nameBoxFromCima(item);   // complete name + images from CIMA before assigning
      dmDb.setAssignee(item.id, p.id, personName(p), p.pharmacy_no || null, parseGroups(p.group_name).join(" · ") || null);
      const line = db.findLine(period.id, item.id);
      if (line) db.setLineState(line.id, 'asignada');
      else db.addLine({ period_id: period.id, person_id: p.id, gtin: item.gtin, item_id: item.id, box_key: item.box_key, state: 'asignada' });
      dmDb.setUsed(item.id, true);
      mode = 'dm';
    } else {
      db.addPrecinto({ period_id: period.id, person_id: p.id, plan_id: med.id, gtin: med.gtin, cn: med.cn, barcode: med.barcode, nombre: med.nombre }, req.user.id);
      mode = 'precinto';
    }
    db.setPlanRelease(med.id, nextDate);   // advance the recurring date
    res.json({ ok: true, mode, med: { id: med.id, nombre: med.nombre || null, cn: med.cn || null, gtin: med.gtin || null }, next_release_at: nextDate, ficha: fichaPayload(p, ym) });
  } catch (err) { fail(res, err); }
});
// Remove a box from the ficha entirely: releases the reservation and, if it had
// been dispensed through this line, returns it to the inventory.
router.delete('/api/line/:id(\\d+)', (req, res) => {
  try {
    const line = db.getLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Asignación no encontrada.' });
    const item = dmDb.getItem(line.item_id);
    if (item) {
      if (item.status === 'utilizado' && item.assignee_id === line.person_id) dmDb.setUsed(line.item_id, false);
      dmDb.setAssignee(line.item_id, null, null);
    }
    db.deleteLine(line.id);
    // Un-graduate: if the medication this box belonged to (by GTIN) is now boxless and
    // still has a Código Nacional, drop its GTIN so it returns to «pendiente de caja»
    // (CN-only look: fondo crema + lápiz de edición), como si nunca se hubiera asociado.
    const gtin = item && item.gtin;
    if (gtin) {
      const stillHasBox = db.listLines(line.period_id).some(l => { const it = dmDb.getItem(l.item_id); return it && it.gtin === gtin; });
      if (!stillHasBox) { const med = db.listPlan(line.person_id).find(pl => pl.gtin === gtin && pl.cn); if (med) db.clearPlanGtin(med.id); }
    }
    const pr = db.getPeriod(line.period_id); const p = qrDb.getPerson(line.person_id);
    res.json(fichaPayload(p, pr.ym));
  } catch (err) { fail(res, err); }
});

// ── Precintos físicos: control de "pegado" en la hoja oficial de Salud ───────────
// Every ASSIGNED unit this month (a DM line 'asignada' or an asig_precinto row) is a
// physical barcode the pharmacy must cut and stick on the official 4×7 A4 sheet
// before month-end. Here we aggregate them by medication, track which are already
// stuck, produce the ordering PDF, and record photo evidence.
const eanFromGtin = (g) => { const d = String(g || '').replace(/\D/g, ''); return d.length === 14 ? (d[0] === '0' ? d.slice(1) : null) : (d.length === 13 ? d : null); };
function buildStickers(ym) {
  const out = [];
  for (const l of db.assignedLinesForYm(ym)) {
    const item = dmDb.getItem(l.item_id) || {};
    const gtin = l.gtin || item.gtin || null;
    const cn = item.cn || cima.cnFromBarcode(eanFromGtin(gtin) || '') || null;
    const barcode = (cn ? cima.barcodeFromCn(cn) : null) || eanFromGtin(gtin);
    out.push({ source: 'line', id: l.id, person_id: l.person_id, gtin, cn, barcode, nombre: item.nombre || null, serial: item.serial || null,
      pegado: !!l.pegado, pegado_at: l.pegado_at || null, method: l.pegado_method || null, evidencia_id: l.evidencia_id || null, assigned_at: l.assigned_at || l.updated_at || null });
  }
  for (const pr of db.precintosForYm(ym)) {
    const cn = pr.cn || (pr.barcode ? cima.cnFromBarcode(pr.barcode) : null);
    const barcode = pr.barcode || (cn ? cima.barcodeFromCn(cn) : null) || eanFromGtin(pr.gtin);
    out.push({ source: 'precinto', id: pr.id, person_id: pr.person_id, gtin: pr.gtin || null, cn: cn || null, barcode, nombre: pr.nombre || null, serial: null,
      pegado: !!pr.pegado, pegado_at: pr.pegado_at || null, method: pr.pegado_method || null, evidencia_id: pr.evidencia_id || null, assigned_at: pr.assigned_at || null });
  }
  const pcache = new Map();
  const snotes = db.entNotesMap('sticker');
  for (const s of out) {
    if (!pcache.has(s.person_id)) pcache.set(s.person_id, qrDb.getPerson(s.person_id));
    const p = pcache.get(s.person_id);
    const groups = p && p.group_name ? String(p.group_name).split('\n').map(x => x.trim()).filter(Boolean) : [];
    s.person = p ? { id: p.id, nombre: p.nombre, apellidos: p.apellidos } : { id: s.person_id, nombre: '', apellidos: '' };
    s.groups = groups;
    s.residencia = groups.length ? groups.join(' · ') : null;   // grupo(s) de QR (TIS), usado como residencia
    s.note = snotes.get(`${s.source}:${s.id}`) || null;
  }
  return out;
}
function stickerKey(s) { return s.cn || s.barcode || s.gtin || (s.nombre ? 'n:' + s.nombre : '—'); }
function stickerPayload(ym) {
  const stickers = buildStickers(ym);
  const groups = new Map();
  for (const s of stickers) {
    const key = stickerKey(s);
    if (!groups.has(key)) groups.set(key, { key, cn: s.cn, barcode: s.barcode, gtin: s.gtin, nombre: s.nombre, por_pegar: 0, pegados: 0, items: [] });
    const g = groups.get(key);
    if (s.pegado) g.pegados++; else g.por_pegar++;
    if (!g.nombre && s.nombre) g.nombre = s.nombre;
    if (!g.cn && s.cn) g.cn = s.cn;
    if (!g.barcode && s.barcode) g.barcode = s.barcode;
    g.items.push({ source: s.source, id: s.id, person: s.person, groups: s.groups, residencia: s.residencia, note: s.note, barcode: s.barcode, cn: s.cn, nombre: s.nombre, serial: s.serial, pegado: s.pegado, pegado_at: s.pegado_at, method: s.method, evidencia_id: s.evidencia_id, assigned_at: s.assigned_at });
  }
  const groupArr = [...groups.values()].sort((a, b) => (a.nombre || 'zzz').localeCompare(b.nombre || 'zzz') || String(a.cn || '').localeCompare(String(b.cn || '')));
  for (const g of groupArr) {
    g.items.sort((a, b) => (a.person.apellidos || '').localeCompare(b.person.apellidos || '') || (a.person.nombre || '').localeCompare(b.person.nombre || ''));
    g.foto_caja = !!(g.cn && (dmDb.cimaCacheGet(g.cn) || {}).has_caja);   // ¿hay foto de la caja en CIMA?
  }
  const por_pegar = stickers.filter(s => !s.pegado).length;
  return { ym, months: db.stickerMonths(), totals: { por_pegar, pegados: stickers.length - por_pegar, total: stickers.length }, groups: groupArr, evidencias: db.listEvidencia(ym) };
}
function markStickerItems(items, pegado, method, evidenciaId) {
  let n = 0;
  for (const it of (Array.isArray(items) ? items : [])) {
    const id = Number(it && it.id);
    if (!id) continue;
    if (it.source === 'line') { db.setLinePegado(id, pegado, method, evidenciaId); n++; }
    else if (it.source === 'precinto') { db.setPrecintoPegado(id, pegado, method, evidenciaId); n++; }
  }
  return n;
}
router.get('/api/stickers', (req, res) => {
  try { res.json(stickerPayload(cleanYm(req.query.ym))); } catch (err) { fail(res, err); }
});
router.post('/api/stickers/mark', json, (req, res) => {
  try { const b = req.body || {}; markStickerItems(b.items, true, b.method || 'manual', b.evidencia_id != null ? Number(b.evidencia_id) : null); res.json(stickerPayload(cleanYm(b.ym))); } catch (err) { fail(res, err); }
});
router.post('/api/stickers/unmark', json, (req, res) => {
  try { const b = req.body || {}; markStickerItems(b.items, false); res.json(stickerPayload(cleanYm(b.ym))); } catch (err) { fail(res, err); }
});
// Mark ALL still-pending precintos of one medication (group) as stuck.
router.post('/api/stickers/mark-med', json, (req, res) => {
  try {
    const b = req.body || {}; const ym = cleanYm(b.ym); const key = String(b.key || '');
    const pending = buildStickers(ym).filter(s => !s.pegado && stickerKey(s) === key);
    markStickerItems(pending.map(s => ({ source: s.source, id: s.id })), true, b.method || 'manual', b.evidencia_id != null ? Number(b.evidencia_id) : null);
    res.json({ marked: pending.length, ...stickerPayload(ym) });
  } catch (err) { fail(res, err); }
});
// Scanner cotejo: a scanned barcode/DM marks the NEXT pending precinto of that med.
router.post('/api/stickers/scan', json, (req, res) => {
  try {
    const b = req.body || {}; const ym = cleanYm(b.ym); const raw = String(b.code == null ? '' : b.code).trim();
    if (!raw) throw bad('Código vacío.');
    const f = gs1.parse(raw); const digits = raw.replace(/\D/g, '');
    let cn = null, barcode = null, gtin = null;
    if (f && f.gtin) { gtin = gs1.normGtin(f.gtin); cn = f.cn || cima.cnFromBarcode(eanFromGtin(gtin) || ''); barcode = cn ? cima.barcodeFromCn(cn) : eanFromGtin(gtin); }
    else if (/^\d{12,14}$/.test(digits)) { const ean = digits.length === 14 && digits[0] === '0' ? digits.slice(1) : digits; barcode = ean; cn = cima.cnFromBarcode(ean); gtin = cn ? cima.gtinFromCn(cn) : null; }
    else throw bad('No reconozco el código escaneado.');
    const pending = buildStickers(ym).filter(s => !s.pegado && ((cn && s.cn === cn) || (barcode && s.barcode === barcode) || (gtin && s.gtin === gtin)));
    if (!pending.length) return res.status(409).json({ error: 'No queda ningún precinto por pegar de ese medicamento este mes.', nomatch: true, cn, barcode });
    const target = pending[0];
    markStickerItems([{ source: target.source, id: target.id }], true, 'scan', null);
    res.json({ ok: true, matched: { cn: target.cn, nombre: target.nombre, person: target.person }, remaining: pending.length - 1, ...stickerPayload(ym) });
  } catch (err) { fail(res, err); }
});
// Photo evidence (base64 data URL). Returns the id to attach when marking pegado.
const jsonPhoto = express.json({ limit: '12mb' });
router.post('/api/stickers/evidencia', jsonPhoto, (req, res) => {
  try {
    const b = req.body || {}; const ym = cleanYm(b.ym);
    const m = /^data:([^;]+);base64,([\s\S]+)$/.exec(String(b.photo || ''));
    if (!m) throw bad('Foto no válida.');
    const buf = Buffer.from(m[2], 'base64');
    if (!buf.length) throw bad('Foto vacía.');
    if (buf.length > 10 * 1024 * 1024) throw bad('Foto demasiado grande (máx. 10 MB).');
    const id = db.addEvidencia({ ym, photo: buf, mime: m[1], note: b.note || null }, req.user.id);
    res.json({ evidencia_id: id, mime: m[1] });
  } catch (err) { fail(res, err); }
});
router.get('/api/stickers/evidencia/:id(\\d+)', (req, res) => {
  try {
    const ev = db.getEvidencia(Number(req.params.id));
    if (!ev) return res.status(404).end();
    res.set('Content-Type', ev.mime || 'image/jpeg'); res.set('Cache-Control', 'private, max-age=3600'); res.send(ev.photo);
  } catch { res.status(404).end(); }
});
// Notes attached to a person or a precinto (upsert; empty text clears it).
router.put('/api/note/person/:id(\\d+)', json, (req, res) => {
  try {
    const p = qrDb.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    res.json({ note: db.setEntNote('person', p.id, req.body || {}, req.user.id) });
  } catch (err) { fail(res, err); }
});
router.put('/api/note/sticker/:source(line|precinto)/:id(\\d+)', json, (req, res) => {
  try { res.json({ note: db.setEntNote('sticker', `${req.params.source}:${req.params.id}`, req.body || {}, req.user.id) }); }
  catch (err) { fail(res, err); }
});
// PDF: barcodes laid out 4×7 per A4 page, to stick & compare against the official
// Salud sheet. The ordering/grouping and the subset are chosen in the print modal
// (order=med|person|residencia, optional secondary sub, one page per group, and an
// optional restriction to the meds/residencias currently filtered on screen).
const stkMedName = s => (s.nombre || 'zzz') + '|' + (s.cn || s.barcode || '');
const stkPersonName = s => (s.person.apellidos || 'zzz') + '|' + (s.person.nombre || '');
const stkResName = s => (s.residencia || 'zzz~');
router.get('/api/stickers/pdf', async (req, res) => {
  try {
    const ym = cleanYm(req.query.ym);
    const all = req.query.filter === 'all';
    const order = ['med', 'person', 'residencia'].includes(req.query.order) ? req.query.order : 'med';
    const sub = req.query.sub === 'person' ? 'person' : 'med';
    const pagebreak = req.query.pagebreak === '1';
    const parseList = (v) => { if (!v) return []; try { const a = JSON.parse(v); if (Array.isArray(a)) return a.map(String); } catch { /* csv */ } return String(v).split(',').map(s => s.trim()).filter(Boolean); };
    const meds = parseList(req.query.meds);
    const groups = parseList(req.query.groups);
    const persons = parseList(req.query.persons).map(Number).filter(Boolean);
    let stickers = buildStickers(ym);
    if (!all) stickers = stickers.filter(s => !s.pegado);
    if (meds.length) stickers = stickers.filter(s => meds.includes(stickerKey(s)));
    if (groups.length) stickers = stickers.filter(s => groups.includes(s.residencia || '—'));
    if (persons.length) stickers = stickers.filter(s => persons.includes(s.person.id));
    const cmp = (a, b, f) => f(a).localeCompare(f(b));
    stickers.sort((a, b) => {
      if (order === 'residencia') {
        const r = cmp(a, b, stkResName); if (r) return r;
        const first = sub === 'person' ? stkPersonName : stkMedName, second = sub === 'person' ? stkMedName : stkPersonName;
        return cmp(a, b, first) || cmp(a, b, second);
      }
      if (order === 'person') return cmp(a, b, stkPersonName) || cmp(a, b, stkMedName);
      return cmp(a, b, stkMedName) || cmp(a, b, stkPersonName);
    });
    const groupKeyFn = order === 'residencia' ? (s => s.residencia || 'Sin grupo')
      : order === 'person' ? (s => `${s.person.apellidos}, ${s.person.nombre}`)
        : (s => s.nombre || 'Medicamento');
    const orderLabel = order === 'residencia' ? `por residencia · ${sub === 'person' ? 'persona' : 'medicamento'}` : order === 'person' ? 'por persona' : 'por medicamento';
    await buildStickersPdf(res, ym, stickers, all, { pagebreak, groupKeyFn, orderLabel });
  } catch (err) { fail(res, err); }
});
async function buildStickersPdf(res, ym, stickers, includeStuck, opts = {}) {
  const PDFDocument = require('pdfkit');
  const bwipjs = require('bwip-js');
  // Render each DISTINCT barcode once (many precintos repeat), keyed by barcode.
  const uniqueBars = [...new Set(stickers.map(s => s.barcode).filter(b => /^\d{12,13}$/.test(String(b || ''))))];
  const pairs = await Promise.all(uniqueBars.map(async b => {
    try { return [b, await bwipjs.toBuffer({ bcid: 'ean13', text: String(b), scale: 3, height: 10, includetext: true, textxalign: 'center', backgroundcolor: 'ffffff', paddingwidth: 2, paddingheight: 1 })]; }
    catch { return [b, null]; }
  }));
  const pngByBar = new Map(pairs);
  const pngSize = (b) => (b && b.length > 24 && b.readUInt32BE(0) === 0x89504e47) ? { w: b.readUInt32BE(16), h: b.readUInt32BE(20) } : null;

  const doc = new PDFDocument({ size: 'A4', margin: 28 });
  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', `inline; filename="precintos-${ym}.pdf"`);
  doc.pipe(res);
  const COLS = 4, ROWS = 7, per = COLS * ROWS, M = 28, TOP = 58;
  const pageW = doc.page.width - M * 2, gridH = doc.page.height - TOP - M;
  const cellW = pageW / COLS, cellH = gridH / ROWS;
  const total = stickers.length;
  const header = (label) => {
    doc.fontSize(14).fillColor('#0f172a').text(`Precintos ${includeStuck ? '(todos)' : 'por pegar'} · ${ym}`, M, 22, { lineBreak: false });
    doc.fontSize(8).fillColor('#64748b').text(`${total} precinto(s) · ${opts.orderLabel || 'ordenados por medicamento'} · hoja 4 × 7${label ? ' · ' + label : ''}`, M, 41, { width: pageW, lineBreak: false, ellipsis: true });
  };
  // Split into pages: optionally a fresh page whenever the primary group changes.
  const buckets = [];
  if (opts.pagebreak && opts.groupKeyFn) {
    let last = Symbol('none'), cur = null;
    for (const s of stickers) { const k = opts.groupKeyFn(s); if (k !== last) { cur = { label: k, items: [] }; buckets.push(cur); last = k; } cur.items.push(s); }
  } else buckets.push({ label: null, items: stickers });
  const pages = [];
  for (const b of buckets) for (let i = 0; i < b.items.length; i += per) pages.push({ label: b.label, items: b.items.slice(i, i + per) });
  if (!pages.length) { header(); doc.fontSize(11).fillColor('#64748b').text(`No hay precintos ${includeStuck ? '' : 'pendientes '}con estas opciones.`, M, 80); doc.end(); return; }

  const drawCell = (s, idx) => {
    const col = idx % COLS, row = Math.floor(idx / COLS);
    const x = M + col * cellW, y = TOP + row * cellH;
    doc.rect(x + 2, y + 2, cellW - 4, cellH - 4).lineWidth(0.5).stroke('#e2e8f0');
    const png = pngByBar.get(s.barcode);
    let capY = y + 40;
    if (png) {
      const maxW = cellW - 16, maxH = 44, nat = pngSize(png);
      let dw = maxW, dh = maxH;
      if (nat) { const sc = Math.min(maxW / nat.w, maxH / nat.h); dw = nat.w * sc; dh = nat.h * sc; }
      doc.image(png, x + (cellW - dw) / 2, y + 9, { width: dw, height: dh });
      capY = y + 9 + dh + 5;
    } else { doc.fontSize(7.5).fillColor('#b91c1c').text('sin código de barras', x + 6, y + 22, { width: cellW - 12, align: 'center' }); }
    doc.fontSize(6.8).fillColor('#0f172a').text(String(s.nombre || 'Medicamento'), x + 6, capY, { width: cellW - 12, align: 'center', height: 16, ellipsis: true });
    doc.fontSize(6).fillColor('#475569').text(`${s.cn ? 'CN ' + s.cn + ' · ' : ''}${s.person.apellidos}, ${s.person.nombre}`, x + 6, capY + 17, { width: cellW - 12, align: 'center', height: 9, ellipsis: true, lineBreak: false });
    if (s.pegado) doc.fontSize(5.5).fillColor('#16a34a').text('PEGADO', x + 6, capY + 27, { width: cellW - 12, align: 'center', lineBreak: false });
  };
  pages.forEach((pg, pi) => {
    if (pi > 0) doc.addPage();
    header(pg.label);
    pg.items.forEach((s, idx) => drawCell(s, idx));
  });
  doc.end();
}

// ── Release search (by date/criterion) + per-person aggregation ─────────────────
router.get('/api/release', (req, res) => {
  try { res.json(release.releaseSearch(req.query || {})); } catch (err) { fail(res, err); }
});

// ── Scheduled email notifications ────────────────────────────────────────────────
function cleanNotif(b, forCreate) {
  const out = {};
  out.name = b.name != null ? String(b.name).trim().slice(0, 120) : null;
  out.ntype = b.ntype === 'all' ? 'all' : 'any';
  out.criterion = b.criterion === 'lte' ? 'lte' : 'exact';
  out.schedule_kind = b.schedule_kind === 'recurring' ? 'recurring' : 'once';
  out.once_date = cleanDate(b.once_date);
  const wd = String(b.weekdays || '').split(',').map(s => s.trim()).filter(s => /^[0-6]$/.test(s));
  out.weekdays = [...new Set(wd)].sort().join(',') || null;
  out.send_time = /^([01]\d|2[0-3]):[0-5]\d$/.test(String(b.send_time || '')) ? b.send_time : '08:00';
  out.recipients = email.parseRecipients(b.recipients).join(', ');
  if (b.enabled !== undefined) out.enabled = b.enabled ? 1 : 0;
  if (forCreate) {
    if (out.schedule_kind === 'once' && !out.once_date) throw bad('Elige la fecha del envío único.');
    if (!out.recipients) throw bad('Añade al menos un destinatario de email válido.');
  }
  return out;
}
router.get('/api/notif', (req, res) => {
  try { res.json({ items: db.listNotifs(), userEmail: req.user.email }); } catch (err) { fail(res, err); }
});
router.post('/api/notif', json, (req, res) => {
  try { res.status(201).json({ item: db.createNotif(cleanNotif(req.body || {}, true), req.user.id) }); } catch (err) { fail(res, err); }
});
router.put('/api/notif/:id(\\d+)', json, (req, res) => {
  try {
    const cur = db.getNotif(Number(req.params.id));
    if (!cur) return res.status(404).json({ error: 'Notificación no encontrada.' });
    const patch = cleanNotif({ ...cur, ...req.body }, true);
    res.json({ item: db.updateNotif(cur.id, patch) });
  } catch (err) { fail(res, err); }
});
router.post('/api/notif/:id(\\d+)/toggle', (req, res) => {
  try { const n = db.getNotif(Number(req.params.id)); if (!n) return res.status(404).json({ error: 'No encontrada.' }); res.json({ item: db.setNotifEnabled(n.id, !n.enabled) }); }
  catch (err) { fail(res, err); }
});
router.delete('/api/notif/:id(\\d+)', (req, res) => {
  try { const ok = db.deleteNotif(Number(req.params.id)); if (!ok) return res.status(404).json({ error: 'No encontrada.' }); res.json({ ok: true }); }
  catch (err) { fail(res, err); }
});
// Preview the email HTML for a draft (no send). Accepts a full notif body.
router.post('/api/notif/preview', json, async (req, res) => {
  try {
    const draft = cleanNotif(req.body || {}, false);
    const refDate = cleanDate(req.body && req.body.ref_date) || release.todayIso();
    const p = await email.previewHtml(draft, refDate);
    res.json({ html: p.html, count: p.count, subject: p.subject, refDate });
  } catch (err) { fail(res, err); }
});
// Send a saved notification right now (test). refDate defaults to today.
router.post('/api/notif/:id(\\d+)/send', json, async (req, res) => {
  try {
    const n = db.getNotif(Number(req.params.id));
    if (!n) return res.status(404).json({ error: 'No encontrada.' });
    const refDate = cleanDate(req.body && req.body.ref_date) || release.todayIso();
    const r = await email.sendNotif(n, refDate, { force: true });
    res.json({ ok: true, ...r });
  } catch (err) { fail(res, err); }
});

// ── Post-its (boards + notes) ─────────────────────────────────────────────────────
function isAdmin(req) { return !!(req.user && req.user.role === 'admin'); }
function canManageNote(note, req) { return note.author_id === req.user.id || isAdmin(req); }
function canManageBoard(b, req) { return b.author_id === req.user.id || isAdmin(req); }
function noteView(n, req) { return { ...n, puede_gestionar: canManageNote(n, req), has_viewers: (n.viewer_ids || []).length > 0 }; }

// Users (for the share modal). Solo los que tienen acceso a esta app: no se
// expone al resto del hub ni se puede compartir una nota fuera de la app.
router.get('/api/users', (req, res) => {
  try { res.json({ items: appUsers().map(u => ({ id: u.id, name: u.name || u.email, email: u.email })), userId: req.user.id }); }
  catch (err) { fail(res, err); }
});

router.get('/api/boards', (req, res) => {
  try { res.json({ items: db.listBoards(req.user.id), userId: req.user.id, isAdmin: isAdmin(req) }); } catch (err) { fail(res, err); }
});
router.post('/api/boards', json, (req, res) => {
  try { const name = String((req.body && req.body.name) || '').trim().slice(0, 80); if (!name) throw bad('El tablón necesita un nombre.'); res.status(201).json({ item: db.createBoard(name, req.user.id) }); }
  catch (err) { fail(res, err); }
});
router.put('/api/boards/:id(\\d+)', json, (req, res) => {
  try {
    const b = db.getBoard(Number(req.params.id)); if (!b) return res.status(404).json({ error: 'Tablón no encontrado.' });
    if (!canManageBoard(b, req)) throw bad('Solo el autor o un administrador puede renombrarlo.', 403);
    const name = String((req.body && req.body.name) || '').trim().slice(0, 80); if (!name) throw bad('Nombre vacío.');
    res.json({ item: db.renameBoard(b.id, name) });
  } catch (err) { fail(res, err); }
});
router.delete('/api/boards/:id(\\d+)', (req, res) => {
  try {
    const b = db.getBoard(Number(req.params.id)); if (!b) return res.status(404).json({ error: 'Tablón no encontrado.' });
    if (db.boardCount() <= 1) throw bad('No puedes borrar el último tablón; siempre debe quedar uno.');
    if (!canManageBoard(b, req)) throw bad('Solo el autor o un administrador puede borrarlo.', 403);
    db.deleteBoard(b.id); res.json({ ok: true });
  } catch (err) { fail(res, err); }
});

router.get('/api/notes', (req, res) => {
  try {
    const boardId = Number(req.query.board_id); if (!boardId) throw bad('Falta board_id.');
    res.json({ items: db.listNotes(boardId, req.user.id).map(n => noteView(n, req)) });
  } catch (err) { fail(res, err); }
});
router.post('/api/notes', json, (req, res) => {
  try {
    const b = req.body || {};
    if (!db.getBoard(Number(b.board_id))) throw bad('Tablón no válido.');
    const note = db.createNote({ board_id: Number(b.board_id), content: b.content, color: b.color, pos_x: b.pos_x, pos_y: b.pos_y, width: b.width, height: b.height, visibility: b.visibility }, req.user.id);
    if (note.visibility === 'personalizada' && Array.isArray(b.viewer_ids)) {
      const allowed = appUserIds(); allowed.add(note.author_id);
      db.setNoteViewers(note.id, b.viewer_ids.map(Number).filter(id => Number.isInteger(id) && allowed.has(id)));
    }
    const full = { ...db.getNote(note.id), viewer_ids: db.noteViewers(note.id), is_new: false };
    res.status(201).json({ item: noteView(full, req) });
  } catch (err) { fail(res, err); }
});
// Partial update. Editing content/pos/size/colour needs "can see"; changing the
// visibility/viewers needs "can manage" (author or admin).
router.put('/api/notes/:id(\\d+)', json, (req, res) => {
  try {
    const note = db.getNote(Number(req.params.id)); if (!note) return res.status(404).json({ error: 'Nota no encontrada.' });
    const b = req.body || {};
    const changingShare = (b.visibility !== undefined) || (b.viewer_ids !== undefined) || (b.alert !== undefined);
    if (changingShare) { if (!canManageNote(note, req)) throw bad('Solo el autor o un administrador puede cambiar quién la ve o avisar.', 403); }
    else if (!db.canSeeNote(note, req.user.id)) throw bad('No tienes acceso a esta nota.', 403);
    const patch = {};
    for (const k of ['content', 'color', 'pos_x', 'pos_y', 'width', 'height', 'visibility', 'alert']) if (b[k] !== undefined) patch[k] = b[k];
    db.updateNote(note.id, patch, req.user.id);
    if (b.viewer_ids !== undefined) {
      // Solo destinatarios con acceso a esta app (más el autor, que siempre puede).
      const allowed = appUserIds(); allowed.add(note.author_id);
      const ids = (Array.isArray(b.viewer_ids) ? b.viewer_ids : []).map(Number).filter(id => Number.isInteger(id) && allowed.has(id));
      db.setNoteViewers(note.id, ids);
    }
    const full = { ...db.getNote(note.id), viewer_ids: db.noteViewers(note.id) };
    res.json({ item: noteView(full, req) });
  } catch (err) { fail(res, err); }
});
router.delete('/api/notes/:id(\\d+)', (req, res) => {
  try {
    const note = db.getNote(Number(req.params.id)); if (!note) return res.status(404).json({ error: 'Nota no encontrada.' });
    if (!canManageNote(note, req)) throw bad('Solo el autor o un administrador puede borrarla.', 403);
    db.deleteNote(note.id); res.json({ ok: true });
  } catch (err) { fail(res, err); }
});
router.post('/api/notes/seen', json, (req, res) => {
  try { const boardId = req.body && req.body.board_id ? Number(req.body.board_id) : null; db.markNotesSeen(req.user.id, boardId); res.json({ badge: db.notesBadge(req.user.id) }); }
  catch (err) { fail(res, err); }
});
router.get('/api/notes/badge', (req, res) => {
  try { res.json(db.notesBadge(req.user.id)); } catch (err) { fail(res, err); }
});
// Notas que otro usuario me ha marcado con aviso y aún no he abierto.
router.get('/api/notes/alerts', (req, res) => {
  try {
    const items = db.pendingAlerts(req.user.id).map((n) => {
      const author = n.author_id != null ? authStore.getUserById(n.author_id) : null;
      const txt = String(n.content || '').replace(/\s+/g, ' ').trim();
      return {
        id: n.id, board_id: n.board_id, board_name: n.board_name, color: n.color,
        excerpt: txt.length > 140 ? txt.slice(0, 140) + '…' : (txt || '(nota sin texto)'),
        author_name: author ? (author.name || author.email) : 'Alguien',
        updated_at: n.updated_at,
      };
    });
    res.json({ items });
  } catch (err) { fail(res, err); }
});
// Re-avisar a los destinatarios (solo el autor o un administrador).
router.post('/api/notes/:id(\\d+)/repoke', (req, res) => {
  try {
    const note = db.getNote(Number(req.params.id)); if (!note) return res.status(404).json({ error: 'Nota no encontrada.' });
    if (!canManageNote(note, req)) throw bad('Solo el autor o un administrador puede volver a avisar.', 403);
    if (note.visibility === 'privada') throw bad('Una nota privada no tiene destinatarios a los que avisar.');
    db.repokeNote(note.id, note.author_id);
    const full = { ...db.getNote(note.id), viewer_ids: db.noteViewers(note.id) };
    res.json({ item: noteView(full, req) });
  } catch (err) { fail(res, err); }
});

// ── Settings (ficha display sizes) ───────────────────────────────────────────────
router.put('/api/settings', json, (req, res) => {
  try {
    const b = req.body || {}, d = db.DEFAULT_SETTINGS;
    const clamp = (n, lo, hi, dflt) => { const x = Math.round(Number(n)); return Number.isFinite(x) ? Math.min(hi, Math.max(lo, x)) : dflt; };
    const patch = {};                                   // only touch the fields provided
    if (b.ficha_qr_size !== undefined) patch.ficha_qr_size = clamp(b.ficha_qr_size, 120, 600, d.ficha_qr_size);
    if (b.ficha_dm_size !== undefined) patch.ficha_dm_size = clamp(b.ficha_dm_size, 80, 320, d.ficha_dm_size);
    if (b.notify_mode !== undefined) patch.notify_mode = ['all', 'any', 'box'].includes(b.notify_mode) ? b.notify_mode : d.notify_mode;
    res.json({ settings: db.saveSettings(patch, req.user.id) });
  } catch (err) { fail(res, err); }
});

module.exports = router;
