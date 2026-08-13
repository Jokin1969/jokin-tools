'use strict';

// ── Gestión de QR (TIS) — API + UI ──────────────────────────────────────────────
// Mounted at /qr-tis (gated by requireApp('qr-tis')). Serves the single-page UI and
// a small JSON API over the people directory, the global QR settings and the
// per-user cart. QR codes are generated client-side (vendored qrcode-generator) so
// size/colour changes are instant and lists of QRs need no server round-trips.

const express = require('express');
const path = require('path');
const db = require('./db');

const router = express.Router();
const PUB = path.join(__dirname, 'public');
const json = express.json({ limit: '256kb' });

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[qr-tis] error:', err);
  res.status(status).json({ error: err.message || 'Error en Gestión de QR (TIS).' });
}
function bad(msg, status = 400) { const e = new Error(msg); e.status = status; return e; }

// ── Validation ──────────────────────────────────────────────────────────────────
function cleanName(v, label, max) {
  const s = String(v == null ? '' : v).trim().replace(/\s+/g, ' ');
  if (!s) throw bad(`El campo «${label}» es obligatorio.`);
  return s.slice(0, max);
}
// TIS: exactly 7 digits, leading zeros preserved. Tolerate spaces the user may type.
function cleanTis(v) {
  const s = String(v == null ? '' : v).replace(/\s+/g, '');
  if (!/^\d{7}$/.test(s)) throw bad('El Código TIS debe tener exactamente 7 cifras (los ceros a la izquierda cuentan).');
  return s;
}
function cleanGroup(v) {
  if (v == null) return null;
  const s = String(v).trim().replace(/\s+/g, ' ').slice(0, 80);
  return s || null;
}

const CLR = /^#[0-9a-fA-F]{6}$/;
function cleanSettings(b) {
  const clamp = (n, lo, hi, dflt) => { const x = Math.round(Number(n)); return Number.isFinite(x) ? Math.min(hi, Math.max(lo, x)) : dflt; };
  const d = db.DEFAULT_SETTINGS;
  return {
    qr_size: clamp(b.qr_size, 120, 900, d.qr_size),
    qr_dark: CLR.test(String(b.qr_dark || '')) ? b.qr_dark : d.qr_dark,
    qr_light: CLR.test(String(b.qr_light || '')) ? b.qr_light : d.qr_light,
    qr_style: ['square', 'dots'].includes(b.qr_style) ? b.qr_style : d.qr_style,
    qr_ecc: ['L', 'M', 'Q', 'H'].includes(b.qr_ecc) ? b.qr_ecc : d.qr_ecc,
    list_qr_size: clamp(b.list_qr_size, 70, 420, d.list_qr_size),
  };
}

const publicPerson = (p) => p && ({
  id: p.id, nombre: p.nombre, apellidos: p.apellidos, tis: p.tis,
  group_name: p.group_name || null, active: p.active ? 1 : 0,
  created_at: p.created_at, updated_at: p.updated_at,
});

// ── UI ───────────────────────────────────────────────────────────────────────
router.get('/', (req, res) => res.sendFile(path.join(PUB, 'index.html')));
router.use('/assets', express.static(PUB));

// ── Meta: settings + current user ───────────────────────────────────────────────
router.get('/api/meta', (req, res) => {
  try {
    res.json({
      settings: db.getSettings(),
      user: { id: req.user.id, email: req.user.email, name: req.user.name || req.user.email },
    });
  } catch (err) { fail(res, err); }
});

// ── People ──────────────────────────────────────────────────────────────────────
router.get('/api/people', (req, res) => {
  try { res.json({ items: db.listPeople().map(publicPerson) }); } catch (err) { fail(res, err); }
});

router.get('/api/people/:id(\\d+)', (req, res) => {
  try {
    const p = db.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    res.json({ item: publicPerson(p) });
  } catch (err) { fail(res, err); }
});

router.post('/api/people', json, (req, res) => {
  try {
    const b = req.body || {};
    const data = {
      nombre: cleanName(b.nombre, 'Nombre', 120),
      apellidos: cleanName(b.apellidos, 'Apellidos', 160),
      tis: cleanTis(b.tis),
      group_name: cleanGroup(b.group_name),
    };
    res.status(201).json({ item: publicPerson(db.createPerson(data, req.user.id)) });
  } catch (err) { fail(res, err); }
});

router.patch('/api/people/:id(\\d+)', json, (req, res) => {
  try {
    const b = req.body || {};
    const data = {};
    if (b.nombre != null) data.nombre = cleanName(b.nombre, 'Nombre', 120);
    if (b.apellidos != null) data.apellidos = cleanName(b.apellidos, 'Apellidos', 160);
    if (b.tis != null) data.tis = cleanTis(b.tis);
    if (b.group_name !== undefined) data.group_name = cleanGroup(b.group_name);
    if (b.active != null) data.active = b.active ? 1 : 0;
    const p = db.updatePerson(Number(req.params.id), data);
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    res.json({ item: publicPerson(p) });
  } catch (err) { fail(res, err); }
});

router.delete('/api/people/:id(\\d+)', (req, res) => {
  try {
    const ok = db.deletePerson(Number(req.params.id));
    if (!ok) return res.status(404).json({ error: 'Persona no encontrada.' });
    res.json({ ok: true });
  } catch (err) { fail(res, err); }
});

// ── Global QR settings (shared) ─────────────────────────────────────────────────
router.put('/api/settings', json, (req, res) => {
  try { res.json({ settings: db.saveSettings(cleanSettings(req.body || {}), req.user.id) }); }
  catch (err) { fail(res, err); }
});

// ── Per-user cart ───────────────────────────────────────────────────────────────
router.get('/api/cart', (req, res) => {
  try { res.json({ ids: db.cartIds(req.user.id) }); } catch (err) { fail(res, err); }
});
router.post('/api/cart/:id(\\d+)', (req, res) => {
  try { res.json({ ids: db.cartAdd(req.user.id, Number(req.params.id)) }); } catch (err) { fail(res, err); }
});
router.delete('/api/cart/:id(\\d+)', (req, res) => {
  try { res.json({ ids: db.cartRemove(req.user.id, Number(req.params.id)) }); } catch (err) { fail(res, err); }
});
router.delete('/api/cart', (req, res) => {
  try { res.json({ ids: db.cartClear(req.user.id) }); } catch (err) { fail(res, err); }
});

module.exports = router;
