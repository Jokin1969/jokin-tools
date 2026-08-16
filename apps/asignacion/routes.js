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

const router = express.Router();
const PUB = path.join(__dirname, 'public');
const json = express.json({ limit: '256kb' });

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[asignacion] error:', err);
  res.status(status).json({ error: err.message || 'Error en Asignación de medicación.' });
}
function bad(msg, status = 400) { const e = new Error(msg); e.status = status; return e; }

// Current month as 'YYYY-MM'.
function thisMonth() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; }
function cleanYm(v) { const s = String(v == null ? '' : v).trim(); return /^\d{4}-\d{2}$/.test(s) ? s : thisMonth(); }

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
// Boxes available to pre-assign for a medication (activo + not reserved).
router.get('/api/available/:gtin([0-9A-Za-z]+)', (req, res) => {
  try { res.json({ items: dmDb.availableItems(req.params.gtin).map(boxView) }); } catch (err) { fail(res, err); }
});

// ── Plan (recurring medications per person) ──────────────────────────────────────
function planView(personId) {
  return db.listPlan(personId).map(l => {
    const m = medMeta(l.gtin);
    return { id: l.id, gtin: l.gtin, qty: l.qty, notes: l.notes || null, active: l.active,
      nombre: m.nombre, color: m.color, shape: m.shape, available: dmDb.availableItems(l.gtin).length };
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
    const gtin = gs1.normGtin(b.gtin);
    if (!gtin || gtin.replace(/^0+/, '').length < 8) throw bad('GTIN no válido.');
    // The medication must exist in the Data Matrix app (a catalogued product or an
    // actual box). Otherwise it has to be added there first.
    const known = dmDb.getProduct(gtin) || dmDb.availableItems(gtin).length || dmDb.listItems('utilizado').some(i => i.gtin === gtin);
    if (!known) throw bad('Ese medicamento no está en la app Data Matrix. Añádelo allí primero (escanea una caja o impórtalo).');
    db.upsertPlan(p.id, gtin, { qty: b.qty, notes: b.notes });
    res.json({ plan: planView(p.id) });
  } catch (err) { fail(res, err); }
});
router.patch('/api/plan/:id(\\d+)', json, (req, res) => {
  try {
    const line = db.getPlanLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Línea de plan no encontrada.' });
    const b = req.body || {};
    db.upsertPlan(line.person_id, line.gtin, { qty: b.qty, notes: b.notes, active: b.active });
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
  const plan = planView(person.id).map(pl => {
    const prog = byGtin.get(pl.gtin) || { attached: 0, asignada: 0 };
    return { ...pl, attached: prog.attached, asignada: prog.asignada };
  });
  const counts = period ? db.periodCounts(period.id) : { preasignada: 0, asignada: 0, total: 0 };
  const planned_total = plan.filter(p => p.active).reduce((s, p) => s + p.qty, 0);
  const periods = db.listPeriods(person.id).map(pr => ({ id: pr.id, ym: pr.ym, status: pr.status, counts: db.periodCounts(pr.id) }));
  return {
    person: personView(person), qrSettings: qrDb.getSettings(),
    month: thisMonth(), ym,
    period: period ? { id: period.id, ym: period.ym, status: period.status, created_at: period.created_at, closed_at: period.closed_at } : { id: null, ym, status: 'nuevo' },
    periods, plan, lines,
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

    const period = db.getOrCreatePeriod(p.id, ym, req.user.id);
    const existing = db.findLine(period.id, item.id);
    if (!existing) {
      dmDb.setAssignee(item.id, p.id, personName(p));
      db.addLine({ period_id: period.id, person_id: p.id, gtin: item.gtin, item_id: item.id, box_key: item.box_key, state: 'preasignada' });
    }
    res.json(fichaPayload(p, ym));
  } catch (err) { fail(res, err); }
});

// Assign for real (the click during the health-app assignment): box → 'utilizado'.
router.post('/api/line/:id(\\d+)/assign', (req, res) => {
  try {
    const line = db.getLine(Number(req.params.id));
    if (!line) return res.status(404).json({ error: 'Asignación no encontrada.' });
    dmDb.setUsed(line.item_id, true);            // keeps the assignee link
    db.setLineState(line.id, 'asignada');
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

// ── Settings (ficha display sizes) ───────────────────────────────────────────────
router.put('/api/settings', json, (req, res) => {
  try {
    const b = req.body || {}, d = db.DEFAULT_SETTINGS;
    const clamp = (n, lo, hi, dflt) => { const x = Math.round(Number(n)); return Number.isFinite(x) ? Math.min(hi, Math.max(lo, x)) : dflt; };
    res.json({ settings: db.saveSettings({
      ficha_qr_size: clamp(b.ficha_qr_size, 120, 600, d.ficha_qr_size),
      ficha_dm_size: clamp(b.ficha_dm_size, 80, 320, d.ficha_dm_size),
    }, req.user.id) });
  } catch (err) { fail(res, err); }
});

module.exports = router;
