'use strict';

// ── Gestión de QR (TIS) — API + UI ──────────────────────────────────────────────
// Mounted at /qr-tis (gated by requireApp('qr-tis')). Serves the single-page UI and
// a small JSON API over the people directory, the global QR settings and the
// per-user cart. QR codes are generated client-side (vendored qrcode-generator) so
// size/colour changes are instant and lists of QRs need no server round-trips.

const express = require('express');
const path = require('path');
const db = require('./db');
const { canAccess } = require('../auth/apps-registry');
const asigDb = require('../asignacion/db');   // cross-app read for the medication button
const { handleHelpPdf } = require('../../lib/help-pdf');

const router = express.Router();
const PUB = path.join(__dirname, 'public');
const json = express.json({ limit: '256kb' });
const jsonBig = express.json({ limit: '4mb' }); // bulk import / big export selections

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[qr-tis] error:', err);
  res.status(status).json({ error: err.message || 'Error en Gestión de QR (TIS).' });
}
function bad(msg, status = 400) { const e = new Error(msg); e.status = status; return e; }

function setDownload(res, filename, mime) {
  const ascii = filename.replace(/[^\x20-\x7E]/g, '_').replace(/["\\]/g, '_');
  res.setHeader('Content-Type', mime);
  res.setHeader('Content-Disposition',
    `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(filename)}`);
}

// Build a printable PDF sheet: a grid of QR codes (server-rendered) with the
// person's name and TIS beneath each. The QR side length (points) is the caller's
// variable. Inactive people show a placeholder instead of a scannable QR.
// `opts.namePriority` flips the emphasis: name/apellidos go big and on top, the QR
// shrinks to a secondary element below it — same overall cell math (a fixed label
// block + the QR), just which one is "the label" and which is "the image" swaps.
async function buildPeoplePdf(people, size, title, st, opts = {}) {
  const PDFDocument = require('pdfkit');
  const QRCode = require('qrcode');
  const gdark = /^#[0-9a-f]{6}$/i.test(st.qr_dark) ? st.qr_dark : '#0f172a';
  // Per-group QR colour (residence distinction): person override > group colour > global.
  const gcMap = (st.group_colors && typeof st.group_colors === 'object') ? st.group_colors : {};
  const groupColor = (p) => {
    for (const g of (p.group_name ? String(p.group_name).split('\n') : [])) {
      const c = gcMap[g.trim()];
      if (/^#[0-9a-f]{6}$/i.test(c || '')) return c;
    }
    return null;
  };
  // Pre-render every QR (PNG) at ~2× for crisp print, honouring each person's colour.
  const pngs = await Promise.all(people.map(p => {
    if (!p.active) return Promise.resolve(null);
    const dark = /^#[0-9a-f]{6}$/i.test(p.qr_dark) ? p.qr_dark : (groupColor(p) || gdark);
    const light = /^#[0-9a-f]{6}$/i.test(p.qr_light) ? p.qr_light : '#ffffff';
    const value = p.qr_code ? String(p.qr_code) : String(p.tis);   // real code when set, else TIS
    return QRCode.toBuffer(value, { type: 'png', errorCorrectionLevel: 'M', margin: 1, width: Math.round(size * 2), color: { dark, light } }).catch(() => null);
  }));
  return await new Promise((resolve, reject) => {
    const doc = new PDFDocument({ size: 'A4', margin: 40, info: { Title: title } });
    const chunks = [];
    doc.on('data', c => chunks.push(c));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    const pageW = doc.page.width, pageH = doc.page.height, M = 40;
    const usableW = pageW - 2 * M;
    const gap = 18;
    const namePriority = !!opts.namePriority;
    // Name-priority: the label block (name + TIS + farmacia) goes ON TOP and grows
    // with nameSize; the QR becomes the small element underneath. Same "size +
    // labelH + 10" cell-height shape either way — only what's inside labelH changes.
    const nameSize = Math.round(Math.min(32, Math.max(10, Number(opts.nameSize) || 20)));
    let nameBoxH = 0, cellW;
    if (namePriority) {
      // Real font metrics, not a guessed average character width — otherwise a
      // narrow cellW makes the "priority" name ellipsize almost immediately
      // (worse than the small-QR mode it's supposed to improve on).
      doc.font('Helvetica-Bold').fontSize(nameSize);
      nameBoxH = Math.ceil(doc.currentLineHeight(true) * 2);   // hasta 2 líneas de nombre
      const maxNameW = people.reduce((m, p) => Math.max(m, doc.widthOfString(`${p.nombre} ${p.apellidos}`)), 0);
      // Ancho pensado para que quepa en una línea la mayoría de nombres reales; uno
      // desproporcionadamente largo simplemente pasa a la segunda línea (o, si ni
      // así cabe, se trunca con «…» — igual que ya se hace en el modo normal). El
      // límite de 220 evita que una única persona con nombre kilométrico fuerce una
      // sola columna para TODA la hoja.
      cellW = Math.max(size, Math.min(maxNameW + 20, 220), 140);
    } else {
      cellW = Math.max(size, 90);
    }
    const tisGap = 4, tisH = 15, pharmGap = 4, pharmH = 12;
    const labelH = namePriority ? (nameBoxH + tisGap + tisH + pharmGap + pharmH) : 44;
    const cols = Math.max(1, Math.floor((usableW + gap) / (cellW + gap)));
    const cellH = size + labelH + 10;
    const colGap = cols > 1 ? (usableW - cols * cellW) / (cols - 1) : 0;

    // Header
    doc.fillColor('#0f2233').font('Helvetica-Bold').fontSize(17).text(title, M, M, { width: usableW });
    doc.fillColor('#5c7086').font('Helvetica').fontSize(9)
      .text(`${people.length} persona(s) · Gestión de QR (TIS)`, M, M + 22, { width: usableW });
    let top = M + 46;

    const drawQr = (i, qx, qy) => {
      if (pngs[i]) {
        try { doc.image(pngs[i], qx, qy, { width: size, height: size }); } catch { /* skip */ }
      } else {
        doc.save().lineWidth(1).strokeColor('#c3c9d2').dash(3, { space: 3 }).rect(qx, qy, size, size).stroke().undash();
        doc.fillColor('#9aa4b0').font('Helvetica').fontSize(9).text('Inactiva', qx, qy + size / 2 - 6, { width: size, align: 'center' });
        doc.restore();
      }
    };

    people.forEach((p, i) => {
      const col = i % cols;
      if (i > 0 && col === 0) {
        top += cellH + gap;
        if (top + cellH > pageH - M) { doc.addPage(); top = M; }
      }
      const x = M + col * (cellW + colGap);
      const y = top;
      const qx = x + (cellW - size) / 2;

      if (namePriority) {
        // Nombre grande arriba (lo que de verdad se lee de un vistazo); el QR,
        // en segundo plano, queda pequeño debajo.
        doc.fillColor('#0f2233').font('Helvetica-Bold').fontSize(nameSize)
          .text(`${p.nombre} ${p.apellidos}`, x, y, { width: cellW, align: 'center', ellipsis: true, height: nameBoxH });
        const tisTop = y + nameBoxH + tisGap;
        doc.fillColor('#1273b8').font('Courier-Bold').fontSize(11)
          .text(String(p.tis), x, tisTop, { width: cellW, align: 'center' });
        const qrTop = tisTop + tisH + pharmGap;
        drawQr(i, qx, qrTop);
        if (p.pharmacy_no) {
          doc.fillColor('#5c7086').font('Helvetica').fontSize(8)
            .text(`Farmacia: ${p.pharmacy_no}`, x, qrTop + size + 4, { width: cellW, align: 'center' });
        }
      } else {
        drawQr(i, qx, y);
        doc.fillColor('#0f2233').font('Helvetica-Bold').fontSize(10)
          .text(`${p.nombre} ${p.apellidos}`, x, y + size + 4, { width: cellW, align: 'center', ellipsis: true, height: 14 });
        doc.fillColor('#1273b8').font('Courier-Bold').fontSize(11)
          .text(String(p.tis), x, y + size + 17, { width: cellW, align: 'center' });
        if (p.pharmacy_no) {
          doc.fillColor('#5c7086').font('Helvetica').fontSize(8)
            .text(`Farmacia: ${p.pharmacy_no}`, x, y + size + 31, { width: cellW, align: 'center' });
        }
      }
    });

    doc.end();
  });
}

// ── Validation ──────────────────────────────────────────────────────────────────
function cleanName(v, label, max) {
  const s = String(v == null ? '' : v).trim().replace(/\s+/g, ' ');
  if (!s) throw bad(`El campo «${label}» es obligatorio.`);
  return s.slice(0, max);
}
// TIS: exactly 7 digits, leading zeros preserved. Tolerate spaces the user may type.
function cleanTis(v) {
  const s = String(v == null ? '' : v).replace(/\s+/g, '');
  if (!/^\d{8}$/.test(s)) throw bad('El Código TIS debe tener exactamente 8 cifras (los ceros a la izquierda cuentan).');
  return s;
}
// Pharmacy number: exactly 5 digits, leading zeros preserved. Required on create/import.
function cleanPharmacy(v, required) {
  const s = String(v == null ? '' : v).replace(/\s+/g, '');
  if (!s) { if (required) throw bad('El Nº de farmacia (5 cifras) es obligatorio.'); return null; }
  if (!/^\d{5}$/.test(s)) throw bad('El Nº de farmacia debe tener exactamente 5 cifras (los ceros a la izquierda cuentan).');
  return s;
}
// The real QR code (magstripe-like: e.g. "%0000…^…^02^APELLIDO/NOMBRE      ? TDG").
// Keep it VERBATIM — %, ^, ?, / and inner/trailing spaces are all significant. Only
// strip line breaks (a keyboard-emulator scanner ends its read with Enter). A value
// that is only whitespace clears the code (the QR falls back to the TIS).
function cleanQrCode(v) {
  const s = String(v == null ? '' : v).replace(/[\r\n]+/g, '');
  if (s.trim() === '') return '';
  if (s.length > 4096) throw bad('El código del QR es demasiado largo.');
  return s;
}
// A person can belong to several groups. They're stored in the group_name column
// joined by newlines (a group name is a single line, so it never collides).
function parseGroups(str) {
  return String(str == null ? '' : str).split('\n').map(s => s.trim()).filter(Boolean);
}
// Accept either an array (from the app) or a string (an imported cell, where
// several groups may be separated by ; or a newline). Normalise, de-dupe
// (case-insensitive), cap the count, and return the newline-joined storage string.
function cleanGroups(input) {
  let arr;
  if (Array.isArray(input)) arr = input;
  else if (input == null) return null;
  else arr = String(input).split(/[\n;]/);
  const seen = new Set(), out = [];
  for (let g of arr) {
    g = String(g == null ? '' : g).trim().replace(/\s+/g, ' ').slice(0, 80);
    if (!g) continue;
    const k = g.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k); out.push(g);
    if (out.length >= 30) break;
  }
  return out.length ? out.join('\n') : null;
}

const CLR = /^#[0-9a-fA-F]{6}$/;
// Per-person QR overrides: a valid hex / style, or null (= fall back to global).
function cleanColorOpt(v) { return CLR.test(String(v == null ? '' : v)) ? v : null; }
function cleanStyleOpt(v) { return ['square', 'dots'].includes(v) ? v : null; }
function cleanSettings(b) {
  const clamp = (n, lo, hi, dflt) => { const x = Math.round(Number(n)); return Number.isFinite(x) ? Math.min(hi, Math.max(lo, x)) : dflt; };
  const d = db.DEFAULT_SETTINGS;
  const out = {
    qr_size: clamp(b.qr_size, 120, 900, d.qr_size),
    qr_dark: CLR.test(String(b.qr_dark || '')) ? b.qr_dark : d.qr_dark,
    qr_light: CLR.test(String(b.qr_light || '')) ? b.qr_light : d.qr_light,
    qr_style: ['square', 'dots'].includes(b.qr_style) ? b.qr_style : d.qr_style,
    qr_ecc: ['L', 'M', 'Q', 'H'].includes(b.qr_ecc) ? b.qr_ecc : d.qr_ecc,
    list_qr_size: clamp(b.list_qr_size, 70, 420, d.list_qr_size),
    card_qr_size: clamp(b.card_qr_size, 80, 200, d.card_qr_size),
  };
  // Per-group QR colours (optional): only include when provided, so normal saves
  // don't wipe them. Keep only valid { "group": "#rrggbb" } pairs.
  if (b.group_colors && typeof b.group_colors === 'object' && !Array.isArray(b.group_colors)) {
    const gc = {};
    for (const [k, v] of Object.entries(b.group_colors)) {
      const name = String(k).trim().slice(0, 80);
      if (name && CLR.test(String(v || ''))) gc[name] = v;
    }
    out.group_colors = gc;
  }
  return out;
}

const publicPerson = (p) => {
  if (!p) return p;
  const groups = parseGroups(p.group_name);
  return {
    id: p.id, pharmacy_no: p.pharmacy_no || null,
    nombre: p.nombre, apellidos: p.apellidos, tis: p.tis,
    groups,                                   // array of group names
    group_name: groups.join('; ') || null,    // display / search / sort string
    qr_dark: p.qr_dark || null, qr_light: p.qr_light || null, qr_style: p.qr_style || null,
    qr_code: p.qr_code || null,                // value the QR encodes (falls back to TIS if empty); never shown as text
    active: p.active ? 1 : 0,
    deceased: p.deceased ? 1 : 0, deceased_at: p.deceased_at || null,
    created_at: p.created_at, updated_at: p.updated_at,
  };
};

// ── UI ───────────────────────────────────────────────────────────────────────
router.get('/', (req, res) => res.sendFile(path.join(PUB, 'index.html')));
router.use('/assets', express.static(PUB));

// ── Meta: settings + current user ───────────────────────────────────────────────
router.get('/api/meta', (req, res) => {
  try {
    res.json({
      settings: db.getSettings(),
      user: { id: req.user.id, email: req.user.email, name: req.user.name || req.user.email },
      canAsignacion: canAccess(req.user, 'asignacion'),   // show the medication button?
    });
  } catch (err) { fail(res, err); }
});

// Medication summary for a person, to drive the "Ver/Crear medicación" button on
// the ficha. Only for users who can access the Asignación app.
router.get('/api/people/:id(\\d+)/med-summary', (req, res) => {
  try {
    if (!canAccess(req.user, 'asignacion')) return res.status(403).json({ error: 'Sin acceso a Asignación.' });
    const p = db.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    res.json({ summary: asigDb.personMedSummary(p.id) });
  } catch (err) { fail(res, err); }
});

// ── People ──────────────────────────────────────────────────────────────────────
router.get('/api/people', (req, res) => {
  try {
    const notes = db.notesMap();
    const canAsig = canAccess(req.user, 'asignacion');
    const planSet = canAsig ? asigDb.personsWithPlanSet() : null;
    res.json({ items: db.listPeople().map(p => ({ ...publicPerson(p), note: notes.get(p.id) || null, ...(planSet ? { has_plan: planSet.has(p.id) } : {}) })) });
  } catch (err) { fail(res, err); }
});
// Create an (empty) medication plan for a person, so it persists and shows as
// "con plan". Only for users with access to Asignación.
router.post('/api/people/:id(\\d+)/create-plan', (req, res) => {
  try {
    if (!canAccess(req.user, 'asignacion')) return res.status(403).json({ error: 'Sin acceso a Asignación.' });
    const p = db.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    asigDb.createEmptyPlan(p.id, req.user.id);
    res.json({ ok: true, has_plan: true });
  } catch (err) { fail(res, err); }
});

router.get('/api/people/:id(\\d+)', (req, res) => {
  try {
    const p = db.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    res.json({ item: { ...publicPerson(p), note: db.getNote(p.id) } });
  } catch (err) { fail(res, err); }
});

// A small note attached to a person (empty text clears it).
router.put('/api/people/:id(\\d+)/note', json, (req, res) => {
  try {
    const p = db.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    res.json({ note: db.setNote(p.id, req.body || {}, req.user.id) });
  } catch (err) { fail(res, err); }
});

router.post('/api/people', json, (req, res) => {
  try {
    const b = req.body || {};
    const data = {
      pharmacy_no: cleanPharmacy(b.pharmacy_no, true),
      nombre: cleanName(b.nombre, 'Nombre', 120),
      apellidos: cleanName(b.apellidos, 'Apellidos', 160),
      tis: cleanTis(b.tis),
      group_name: cleanGroups(b.groups !== undefined ? b.groups : b.group_name),
      qr_code: cleanQrCode(b.qr_code),
      qr_dark: cleanColorOpt(b.qr_dark), qr_light: cleanColorOpt(b.qr_light), qr_style: cleanStyleOpt(b.qr_style),
    };
    if (db.pharmacyTaken(data.pharmacy_no)) throw bad(`El Nº de farmacia ${data.pharmacy_no} ya está asignado a otra persona.`);
    if (db.tisTaken(data.tis)) throw bad(`El Código TIS ${data.tis} ya está asignado a otra persona.`);
    res.status(201).json({ item: publicPerson(db.createPerson(data, req.user.id)) });
  } catch (err) { fail(res, err); }
});

router.patch('/api/people/:id(\\d+)', json, (req, res) => {
  try {
    const b = req.body || {};
    const data = {};
    if (b.pharmacy_no !== undefined) data.pharmacy_no = cleanPharmacy(b.pharmacy_no, false);
    if (b.nombre != null) data.nombre = cleanName(b.nombre, 'Nombre', 120);
    if (b.apellidos != null) data.apellidos = cleanName(b.apellidos, 'Apellidos', 160);
    if (b.tis != null) data.tis = cleanTis(b.tis);
    if (b.groups !== undefined || b.group_name !== undefined) data.group_name = cleanGroups(b.groups !== undefined ? b.groups : b.group_name);
    if (b.qr_dark !== undefined) data.qr_dark = cleanColorOpt(b.qr_dark);
    if (b.qr_light !== undefined) data.qr_light = cleanColorOpt(b.qr_light);
    if (b.qr_style !== undefined) data.qr_style = cleanStyleOpt(b.qr_style);
    if (b.qr_code !== undefined) data.qr_code = cleanQrCode(b.qr_code);
    if (b.active != null) data.active = b.active ? 1 : 0;
    const id = Number(req.params.id);
    if (data.pharmacy_no && db.pharmacyTaken(data.pharmacy_no, id)) throw bad(`El Nº de farmacia ${data.pharmacy_no} ya está asignado a otra persona.`);
    if (data.tis && db.tisTaken(data.tis, id)) throw bad(`El Código TIS ${data.tis} ya está asignado a otra persona.`);
    const p = db.updatePerson(id, data);
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

// ── Bulk import (from a filled-in Excel, parsed client-side) ────────────────────
router.post('/api/import', jsonBig, (req, res) => {
  try {
    const rows = Array.isArray(req.body && req.body.rows) ? req.body.rows : null;
    if (!rows) throw bad('No se recibieron filas para importar.');
    if (rows.length > 5000) throw bad('Demasiadas filas (máximo 5000 por importación).');
    const valid = [];
    const errors = [];
    const seenPh = new Set(), seenTis = new Set(); // catch duplicates WITHIN the file too
    rows.forEach((r, i) => {
      const rowNo = (r.__row != null ? r.__row : i + 1);
      try {
        const rec = {
          pharmacy_no: cleanPharmacy(r.pharmacy_no, true),
          nombre: cleanName(r.nombre, 'Nombre', 120),
          apellidos: cleanName(r.apellidos, 'Apellidos', 160),
          tis: cleanTis(r.tis),
          group_name: cleanGroups(r.group_name),
          qr_code: cleanQrCode(r.qr_code),          // real QR value (empty → QR uses the TIS)
        };
        // TIS must be unique (no exceptions); pharmacy unique except '00000'.
        if (seenTis.has(rec.tis) || db.tisTaken(rec.tis)) throw bad(`Código TIS ${rec.tis} duplicado.`);
        if (rec.pharmacy_no !== '00000' && (seenPh.has(rec.pharmacy_no) || db.pharmacyTaken(rec.pharmacy_no)))
          throw bad(`Nº de farmacia ${rec.pharmacy_no} duplicado.`);
        seenTis.add(rec.tis);
        if (rec.pharmacy_no !== '00000') seenPh.add(rec.pharmacy_no);
        valid.push(rec);
      } catch (e) { errors.push({ row: rowNo, error: e.message }); }
    });
    const created = valid.length ? db.createManyPeople(valid, req.user.id) : [];
    res.json({ created: created.length, errors, total: rows.length });
  } catch (err) { fail(res, err); }
});

// ── QR code association (pharmacy_no → real QR code) ────────────────────────────
// The pharmacy QR encodes a longer code, NOT the TIS. Here we bulk-associate that
// code by pharmacy number: only people whose Nº de farmacia already exists get their
// qr_code updated; nothing else is created or changed.
router.post('/api/qr-codes/import', jsonBig, (req, res) => {
  try {
    const rows = Array.isArray(req.body && req.body.rows) ? req.body.rows : null;
    if (!rows) throw bad('No se recibieron filas para importar.');
    if (rows.length > 20000) throw bad('Demasiadas filas (máximo 20000 por importación).');
    const clean = rows
      .map(r => ({ pharmacy_no: String(r.pharmacy_no == null ? '' : r.pharmacy_no).replace(/\s+/g, ''), qr_code: cleanQrCode(r.qr_code) }))
      .filter(r => r.pharmacy_no);
    const result = db.setQrCodesByPharmacy(clean);
    res.json({ ...result, total: clean.length });
  } catch (err) { fail(res, err); }
});

// Set (or clear) one person's QR code — the keyboard-emulator scanner path.
// Send { qr_code: "…" }; an empty value clears it (the QR falls back to the TIS).
router.put('/api/people/:id(\\d+)/qr-code', json, (req, res) => {
  try {
    const p = db.getPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    const code = cleanQrCode(req.body && req.body.qr_code);
    res.json({ item: publicPerson(db.setQrCode(p.id, code)) });
  } catch (err) { fail(res, err); }
});

// ── Recently handled ────────────────────────────────────────────────────────────
router.get('/api/recent', (req, res) => {
  try { res.json({ items: db.recentPeople(10).map(p => ({ ...publicPerson(p), handled_at: p.handled_at })) }); }
  catch (err) { fail(res, err); }
});

// Mark a person as deceased (or revert). Deceased also makes the QR inaccessible.
router.post('/api/people/:id(\\d+)/deceased', json, (req, res) => {
  try {
    const deceased = !!(req.body && req.body.deceased);
    const p = db.setDeceased(Number(req.params.id), deceased);
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    res.json({ item: publicPerson(p) });
  } catch (err) { fail(res, err); }
});

// Mark a person as "handled" (called when its ficha/QR is opened).
router.post('/api/people/:id(\\d+)/touch', (req, res) => {
  try {
    const p = db.touchPerson(Number(req.params.id));
    if (!p) return res.status(404).json({ error: 'Persona no encontrada.' });
    res.json({ ok: true });
  } catch (err) { fail(res, err); }
});

// ── PDF export: a sheet of QR codes with a chosen (variable) QR size ─────────────
router.post('/api/export/pdf', jsonBig, async (req, res) => {
  try {
    const b = req.body || {};
    const size = Math.round(Math.min(300, Math.max(48, Number(b.qr_size) || 150))); // points
    const title = (b.title ? String(b.title) : 'Listado de códigos TIS').slice(0, 120);
    let people;
    if (Array.isArray(b.ids) && b.ids.length) {
      if (b.ids.length > 2000) throw bad('Demasiadas personas para el PDF (máximo 2000).');
      const byId = new Map(db.listPeople().map(p => [p.id, p]));
      people = b.ids.map(id => byId.get(Number(id))).filter(Boolean);
    } else {
      people = db.listPeople();
    }
    if (!people.length) throw bad('No hay personas que exportar.');
    const st = db.getSettings();
    const namePriority = !!b.name_priority;
    const nameSize = Math.round(Math.min(32, Math.max(10, Number(b.name_size) || 20)));
    const buf = await buildPeoplePdf(people, size, title, st, { namePriority, nameSize });
    setDownload(res, `TIS_${title.replace(/[^\w áéíóúñÁÉÍÓÚÑ-]/gi, '_').slice(0, 40)}.pdf`, 'application/pdf');
    res.send(buf);
  } catch (err) { fail(res, err); }
});

// ── Manual / Ayuda → PDF (elegant, branded) ─────────────────────────────────────
router.post('/api/help/pdf', jsonBig, (req, res) => handleHelpPdf(req, res, {
  appLabel: 'QR (TIS)',
  filename: 'Manual_QR_TIS.pdf',
  defaultTitle: 'Manual de Gestión de QR (TIS)',
  defaultSubtitle: 'Todo lo que puedes hacer, explicado paso a paso.',
}));

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
