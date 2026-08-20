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
const authStore = require('../auth/store');
const { canAccess } = require('../auth/apps-registry');

const router = express.Router();

// Usuarios que pueden acceder a ESTA app: las notas solo se comparten entre
// ellos, nunca con el resto del hub. (Un admin ve/entra en todas las apps.)
const APP_ID = 'asignacion';
function appUsers() { return authStore.listUsers().filter(u => canAccess(u, APP_ID)); }
function appUserIds() { return new Set(appUsers().map(u => u.id)); }
const PUB = path.join(__dirname, 'public');
const json = express.json({ limit: '256kb' });

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[asignacion] error:', err);
  res.status(status).json({ error: err.message || 'Error en Asignación de medicación.' });
}
function bad(msg, status = 400) { const e = new Error(msg); e.status = status; return e; }

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
    return {
      id: l.id, gtin: l.gtin || null, cn: l.cn || null, barcode,
      qty: l.qty, notes: l.notes || null, active: l.active,
      nombre, color, shape, available, cn_only: !hasGtin,
      release_at: l.release_at || null, advance_days, effective_at, effective_days, release_state,
      foto_caja: !!(cc && cc.has_caja), foto_pastilla: !!(cc && cc.has_pastilla),
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
    if (gtin && gtin.replace(/^0+/, '').length >= 8) {
      // Catalogued path: the GTIN must exist in the Data Matrix app.
      const known = dmDb.getProduct(gtin) || dmDb.availableItems(gtin).length || dmDb.listItems('utilizado').some(i => i.gtin === gtin);
      if (!known) throw bad('Ese medicamento no está en la app Data Matrix. Añádelo allí primero (escanea una caja o impórtalo).');
      db.addPlanMed(p.id, { gtin, qty: b.qty, notes: b.notes, nombre, barcode, cn });
    } else if (cn) {
      // CN-only path (info before Data Matrix). Promote to catalogued if the CN is
      // already known in the medication catalogue; otherwise keep it CN-only.
      const prod = dmDb.listProducts().find(x => x.cn && String(x.cn) === cn);
      if (prod) db.addPlanMed(p.id, { gtin: prod.gtin, qty: b.qty, notes: b.notes, nombre: nombre || prod.nombre, barcode, cn });
      else {
        if (!nombre) throw bad('Indica el nombre del medicamento.');
        db.addPlanMed(p.id, { cn, nombre, barcode, qty: b.qty, notes: b.notes });
      }
    } else {
      throw bad('Indica el GTIN o el Código Nacional del medicamento.');
    }
    res.json({ plan: planView(p.id) });
  } catch (err) { fail(res, err); }
});
router.patch('/api/plan/:id(\\d+)', json, (req, res) => {
  try {
    const line = db.getPlanLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Línea de plan no encontrada.' });
    const b = req.body || {};
    if (b.qty !== undefined || b.notes !== undefined || b.active !== undefined) {
      db.updatePlanById(line.id, { qty: b.qty, notes: b.notes, active: b.active });
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

// ── Ficha (person + period + attached boxes + plan progress) ─────────────────────
function fichaPayload(person, ym) {
  const period = db.findPeriod(person.id, ym); // may be null until the first box is attached
  const lines = period ? db.listLines(period.id).map(lineView) : [];
  // Per-medication progress within this period.
  const byGtin = new Map();
  for (const ln of lines) {
    const g = ln.gtin || (ln.box && ln.box.gtin) || '—';
    if (!byGtin.has(g)) byGtin.set(g, { attached: 0, asignada: 0 });
    const e = byGtin.get(g); e.attached++; if (ln.state === 'asignada') e.asignada++;
  }
  const precByPlan = period ? db.precintoCountByPlan(period.id) : new Map();
  const plan = planView(person.id).map(pl => {
    const prog = byGtin.get(pl.gtin) || { attached: 0, asignada: 0 };
    const prec = precByPlan.get(pl.id) || 0;   // asignados por precinto (sin caja)
    return { ...pl, boxes: prog.attached, attached: prog.attached + prec, asignada: prog.asignada + prec, precinto: prec };
  });
  const precintos = period ? db.listPrecinto(period.id).map(r => ({ id: r.id, plan_id: r.plan_id, gtin: r.gtin, cn: r.cn, barcode: r.barcode, nombre: r.nombre, assigned_at: r.assigned_at })) : [];
  const counts = period ? db.periodCounts(period.id) : { preasignada: 0, asignada: 0, total: 0 };
  const planned_total = plan.filter(p => p.active).reduce((s, p) => s + p.qty, 0);
  const periods = db.listPeriods(person.id).map(pr => ({ id: pr.id, ym: pr.ym, status: pr.status, counts: db.periodCounts(pr.id) }));
  return {
    person: personView(person), qrSettings: qrDb.getSettings(),
    month: thisMonth(), ym,
    period: period ? { id: period.id, ym: period.ym, status: period.status, created_at: period.created_at, closed_at: period.closed_at } : { id: null, ym, status: 'nuevo' },
    periods, plan, lines, precintos,
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
      });
    }
    const norm = s => String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    rows.sort((a, b) => norm(a.person.apellidos + ' ' + a.person.nombre).localeCompare(norm(b.person.apellidos + ' ' + b.person.nombre), 'es'));
    res.json({ month, items: rows });
  } catch (err) { fail(res, err); }
});

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
router.post('/api/person/:id(\\d+)/preassign', json, (req, res) => {
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
      const data = { raw, box_key: gs1.boxKey(f, raw), gtin: gs1.normGtin(f.gtin), serial: f.serial, lote: f.lote, caducidad: gs1.expiryToIso(f.caducidad), cn: f.cn };
      item = dmDb.findByKey(data.box_key);
      if (!item) {
        item = dmDb.createItem(data, req.user.id);
        if (data.gtin && !dmDb.getProduct(data.gtin)) dmDb.upsertProduct(data.gtin, {});
      }
    }

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
      dmDb.setAssignee(item.id, p.id, personName(p));
      db.addLine({ period_id: period.id, person_id: p.id, gtin: item.gtin, item_id: item.id, box_key: item.box_key, state: 'preasignada' });
    }
    // A CN-only plan med "graduates" to catalogued once we know the box's GTIN.
    if (planMed && !planMed.gtin && item.gtin) db.reconcilePlanGtin(planMed.id, item.gtin);
    res.json(fichaPayload(p, ym));
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
router.post('/api/person/:id(\\d+)/scan', json, (req, res) => {
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
    if (f && f.gtin) { gtin = gs1.normGtin(f.gtin); cn = f.cn || null; isDm = true; }
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
      dmDb.setAssignee(item.id, p.id, personName(p));
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
    const pr = db.getPeriod(line.period_id); const p = qrDb.getPerson(line.person_id);
    res.json(fichaPayload(p, pr.ym));
  } catch (err) { fail(res, err); }
});

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
