'use strict';

// ── Pastillero — API + UI ────────────────────────────────────────────────────────
// Two audiences, two gates, mounted on the SAME router at /pastillero:
//   · Caregivers (residencia staff): NO farmacia account. They log in with a
//     shared access code per residencia (see db.js) and can only see the people
//     of THAT residencia's group. Gate: requireResidencia (this file's session).
//   · Farmacia staff: manage the access codes from /pastillero/admin, gated like
//     any other app with requireApp('pastillero') (needs a normal admin/user grant).
//
// Reads people (qr-tis) and the medication plan + dose schedule (asignacion)
// in-process, exactly like Asignación already reads qr-tis and datamatrix.

const express = require('express');
const path = require('path');
const db = require('./db');
const qrDb = require('../qr-tis/db');
const asigDb = require('../asignacion/db');
const dmDb = require('../datamatrix/db');
const dmVisual = require('../datamatrix/visual');
const { requireApp } = require('../auth/middleware');

const router = express.Router();
const PUB = path.join(__dirname, 'public');
const json = express.json({ limit: '64kb' });

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[pastillero] error:', err);
  res.status(status).json({ error: err.message || 'Error en Pastillero.' });
}
function bad(msg, status = 400) { const e = new Error(msg); e.status = status; return e; }

// A person can belong to several groups, newline-joined (same storage as QR-TIS).
function parseGroups(str) { return String(str == null ? '' : str).split('\n').map(s => s.trim()).filter(Boolean); }

// ── Residencia session (own cookie, own store — NOT the farmacia login) ──────────
const COOKIE_NAME = 'pt_sid';
const isProd = process.env.NODE_ENV === 'production';
function parseCookies(header) {
  const out = {};
  if (!header) return out;
  for (const part of header.split(';')) {
    const i = part.indexOf('=');
    if (i < 0) continue;
    const k = part.slice(0, i).trim(), v = part.slice(i + 1).trim();
    if (k) out[k] = decodeURIComponent(v);
  }
  return out;
}
function attachResidencia(req, res, next) {
  const sid = parseCookies(req.headers.cookie)[COOKIE_NAME] || null;
  req.residencia = sid ? db.getSessionResidencia(sid) : null;
  next();
}
router.use(attachResidencia);

function requireResidencia(req, res, next) {
  if (!req.residencia) return res.status(401).json({ error: 'Introduce el código de tu residencia para entrar.' });
  next();
}

// ── Login / logout (public — no farmacia account involved) ──────────────────────
router.post('/api/login', json, (req, res) => {
  try {
    const code = String((req.body && req.body.code) || '').trim().toUpperCase();
    if (!code) throw bad('Escribe el código de tu residencia.');
    const residencia = db.getResidenciaByCode(code);
    if (!residencia) throw bad('Código no reconocido. Compruébalo con tu farmacia.');
    const { sid, maxAgeMs } = db.createSession(residencia.id);
    res.cookie(COOKIE_NAME, sid, { httpOnly: true, sameSite: 'lax', secure: isProd, path: '/', maxAge: maxAgeMs });
    res.json({ ok: true, residencia: { group_name: residencia.group_name } });
  } catch (err) { fail(res, err); }
});
router.post('/api/logout', (req, res) => {
  const sid = parseCookies(req.headers.cookie)[COOKIE_NAME];
  if (sid) db.deleteSession(sid);
  res.clearCookie(COOKIE_NAME, { path: '/', httpOnly: true, sameSite: 'lax', secure: isProd });
  res.json({ ok: true });
});
router.get('/api/me', (req, res) => {
  res.json({ residencia: req.residencia ? { group_name: req.residencia.group_name } : null });
});

// ── Caregiver API (gated: must be logged in with a residencia code) ─────────────
router.use('/api/people', requireResidencia);
router.use('/api/person', requireResidencia);

function norm(s) { return String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }

// ── The daily "now" clock (server-side, so every device agrees) ─────────────────
const SLOT_LABELS = { desayuno: 'Desayuno', comida: 'Comida', cena: 'Cena', noche: 'Noche' };
const SLOT_ORDER = ['desayuno', 'comida', 'cena', 'noche'];
// Hour boundaries (24h, local server time) — same for every residencia for now.
function slotForHour(h) {
  if (h >= 6 && h < 12) return 'desayuno';
  if (h >= 12 && h < 17) return 'comida';
  if (h >= 17 && h < 21) return 'cena';
  return 'noche';
}
function nowInfo() {
  const d = new Date();
  const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const time = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  return { date, time, slot: slotForHour(d.getHours()) };
}
function shiftDateStr(iso, days) {
  const d = new Date(iso + 'T00:00:00');
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
// How many active medications a person has, and when their next dose is due
// (from "now" onward, looking up to 3 days ahead) — for the residency overview.
function personSummary(personId, now) {
  const plans = asigDb.listPlan(personId).filter(pl => pl.active);
  let next_dose = null;
  for (let dayOffset = 0; dayOffset <= 3 && !next_dose; dayOffset++) {
    const date = shiftDateStr(now.date, dayOffset);
    const fromIdx = dayOffset === 0 ? SLOT_ORDER.indexOf(now.slot) : 0;
    for (let i = fromIdx; i < SLOT_ORDER.length; i++) {
      const slot = SLOT_ORDER[i];
      const has = plans.some(pl => { const d = asigDb.getDoseScheduleForDate(pl.id, date); return d && d[slot] > 0; });
      if (has) { next_dose = { date, slot, is_today: dayOffset === 0, is_now: dayOffset === 0 && i === fromIdx }; break; }
    }
  }
  return { med_count: plans.length, next_dose };
}

// People of THIS residencia only (never the whole QR-TIS directory). Empty `q`
// returns everyone — the caregiver overview, not just search results.
router.get('/api/people', (req, res) => {
  try {
    const q = norm(req.query.q || '');
    const group = req.residencia.group_name;
    let people = qrDb.listPeople().filter(p => p.active && !p.deceased && parseGroups(p.group_name).includes(group));
    if (q) {
      const tokens = q.split(/\s+/).filter(Boolean);
      people = people.filter(p => { const hay = norm(`${p.nombre} ${p.apellidos}`); return tokens.every(t => hay.includes(t)); });
    }
    people.sort((a, b) => `${a.apellidos} ${a.nombre}`.localeCompare(`${b.apellidos} ${b.nombre}`, 'es'));
    const now = nowInfo();
    const items = people.slice(0, 200).map(p => ({ id: p.id, nombre: p.nombre, apellidos: p.apellidos, ...personSummary(p.id, now) }));
    res.json({ items, now });
  } catch (err) { fail(res, err); }
});

// Aggregated Pastillero for one person on one date: every active medication's
// dose (if any is defined for that date) grouped into the 4 franjas.
router.get('/api/person/:id(\\d+)/pastillero', (req, res) => {
  try {
    const p = qrDb.getPerson(Number(req.params.id));
    if (!p || !p.active || p.deceased) return res.status(404).json({ error: 'Persona no encontrada.' });
    if (!parseGroups(p.group_name).includes(req.residencia.group_name)) return res.status(403).json({ error: 'Esta persona no pertenece a tu residencia.' });
    const now = nowInfo();
    const date = /^\d{4}-\d{2}-\d{2}$/.test(String(req.query.date || '')) ? req.query.date : now.date;

    const slots = { desayuno: [], comida: [], cena: [], noche: [] };
    let anyDoseDefined = false;
    for (const pl of asigDb.listPlan(p.id)) {
      if (!pl.active) continue;
      const dose = asigDb.getDoseScheduleForDate(pl.id, date);
      if (!dose) continue;   // pauta aún sin definir para este medicamento
      const prod = pl.gtin ? dmDb.getProduct(pl.gtin) : null;
      const nombre = (prod && prod.nombre) || pl.nombre || 'Medicamento';
      const color = dmVisual.resolveColor(pl.gtin, prod && prod.color);
      const shape = dmVisual.resolveShape(pl.gtin, prod && prod.shape);
      for (const slot of SLOT_ORDER) {
        const qty = dose[slot] || 0;
        if (qty > 0) { anyDoseDefined = true; slots[slot].push({ plan_id: pl.id, nombre, color, shape, qty }); }
      }
    }
    res.json({
      person: { id: p.id, nombre: p.nombre, apellidos: p.apellidos },
      date, is_today: date === now.date, now, slots, slot_labels: SLOT_LABELS,
      empty: !anyDoseDefined,
    });
  } catch (err) { fail(res, err); }
});

// ── Admin (farmacia staff): manage residencia access codes ──────────────────────
router.get('/api/admin/residencias', requireApp('pastillero'), (req, res) => {
  try {
    const groups = qrDb.distinctGroups();
    const byGroup = new Map(db.listResidencias().map(r => [r.group_name, r]));
    const items = groups.map(g => {
      const r = byGroup.get(g);
      return { group_name: g, has_code: !!(r && r.access_code), access_code: (r && r.access_code) || null, active: r ? !!r.active : true };
    });
    res.json({ items });
  } catch (err) { fail(res, err); }
});
router.post('/api/admin/residencias/rotate', requireApp('pastillero'), json, (req, res) => {
  try {
    const group = String((req.body && req.body.group_name) || '').trim();
    if (!group) throw bad('Falta la residencia.');
    res.json({ item: db.rotateCode(group) });
  } catch (err) { fail(res, err); }
});
router.post('/api/admin/residencias/active', requireApp('pastillero'), json, (req, res) => {
  try {
    const group = String((req.body && req.body.group_name) || '').trim();
    if (!group) throw bad('Falta la residencia.');
    res.json({ item: db.setResidenciaActive(group, !!(req.body && req.body.active)) });
  } catch (err) { fail(res, err); }
});

// ── UI ────────────────────────────────────────────────────────────────────────
router.get('/', (req, res) => res.sendFile(path.join(PUB, 'index.html')));
router.get('/admin', requireApp('pastillero'), (req, res) => res.sendFile(path.join(PUB, 'admin.html')));
router.use('/assets', express.static(PUB));

module.exports = router;
