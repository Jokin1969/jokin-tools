'use strict';

// ── Asignación — release-date computation (shared by routes, cron and email) ─────
// Groups still-reserved (pre-asignada) boxes that carry a Salud release date by
// person, and answers the search/aggregation the bell and the notifications use.

const qrDb = require('../qr-tis/db');
const dmDb = require('../datamatrix/db');
const dmVisual = require('../datamatrix/visual');
const db = require('./db');

function todayIso() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
function cleanDate(v) { const s = String(v == null ? '' : v).trim(); return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : null; }
function daysUntil(iso) { if (!iso) return null; const a = new Date(todayIso() + 'T00:00:00'), b = new Date(iso + 'T00:00:00'); if (isNaN(b)) return null; return Math.round((b - a) / 86400000); }
const nameKey = p => `${p.apellidos} ${p.nombre}`;
const byName = (a, b) => nameKey(a.person).localeCompare(nameKey(b.person), 'es', { sensitivity: 'base' });

// Lightweight box view (for the API/bell).
function boxLite(item) {
  return item ? {
    nombre: item.nombre || null, gtin: item.gtin || null, serial: item.serial || null,
    caducidad: item.caducidad || null, color: dmVisual.resolveColor(item.gtin, item.color), shape: dmVisual.resolveShape(item.gtin, item.shape),
  } : null;
}

// Effective date = official Salud date − days-of-anticipation (that's when the
// pharmacy can actually act). All the readiness/notification maths run on it.
function effectiveOf(ln) { return db.effectiveDate(ln.release_at, ln.advance_days); }

function releaseGroups() {
  const byId = new Map();
  for (const ln of db.pendingReleaseLines()) {
    const p = qrDb.getPerson(ln.person_id);
    if (!p) continue;
    const item = dmDb.getItem(ln.item_id);
    const pr = db.getPeriod(ln.period_id);
    const eff = effectiveOf(ln);
    if (!byId.has(p.id)) byId.set(p.id, { person: { id: p.id, nombre: p.nombre, apellidos: p.apellidos, tis: p.tis }, boxes: [] });
    byId.get(p.id).boxes.push({
      line_id: ln.id, ym: pr ? pr.ym : null,
      release_at: ln.release_at, advance_days: ln.advance_days, effective_at: eff,
      days: daysUntil(eff), box: boxLite(item),
    });
  }
  return byId;
}

// Bell search: date + criterion (lte/exact) + mode (box/all/any). Alphabetical.
function releaseSearch(q) {
  const today = todayIso();
  const date = cleanDate(q.date) || today;
  const criterion = q.criterion === 'exact' ? 'exact' : 'lte';
  const mode = ['box', 'all', 'any'].includes(q.mode) ? q.mode : (db.getSettings().notify_mode || 'all');
  // All comparisons run on the EFFECTIVE date (official − anticipation days).
  const sat = (eff) => criterion === 'exact' ? eff === date : eff <= date;
  const groups = [...releaseGroups().values()];
  const matched = [], pending = [];

  if (mode === 'box') {
    for (const g of groups) for (const b of g.boxes) (sat(b.effective_at) ? matched : pending).push({ person: g.person, ...b });
    const cmp = (a, b) => byName(a, b) || a.effective_at.localeCompare(b.effective_at);
    matched.sort(cmp); pending.sort(cmp);
  } else {
    for (const g of groups) {
      const dates = g.boxes.map(b => b.effective_at);
      const aggDate = mode === 'all' ? dates.reduce((m, d) => (d > m ? d : m)) : dates.reduce((m, d) => (d < m ? d : m));
      const ready = mode === 'all' ? g.boxes.every(b => sat(b.effective_at)) : g.boxes.some(b => sat(b.effective_at));
      const entry = {
        person: g.person, aggDate, aggDays: daysUntil(aggDate), total: g.boxes.length,
        releasedByToday: g.boxes.filter(b => b.effective_at <= today).length,
        boxes: g.boxes.map(b => ({ ...b, satisfied: sat(b.effective_at) })).sort((a, b) => a.effective_at.localeCompare(b.effective_at)),
      };
      (ready ? matched : pending).push(entry);
    }
    matched.sort(byName); pending.sort(byName);
  }
  return { today, date, criterion, mode, matched, pending, counts: { matched: matched.length, pending: pending.length } };
}

// Rich per-person data for the notification email (keeps the full person + item
// records, so the QR and the Data Matrix can be rendered). `opts` = { ntype, criterion }.
function peopleForNotif(opts, refDate) {
  const criterion = opts.criterion === 'exact' ? 'exact' : 'lte';
  const mode = opts.ntype === 'all' ? 'all' : 'any';
  // The digest fires on the EFFECTIVE date (official − anticipation days).
  const sat = (eff) => criterion === 'exact' ? eff === refDate : eff <= refDate;
  const byId = new Map();
  for (const ln of db.pendingReleaseLines()) {
    const p = qrDb.getPerson(ln.person_id);
    if (!p) continue;
    const item = dmDb.getItem(ln.item_id);
    if (!byId.has(p.id)) byId.set(p.id, { person: p, boxes: [] });
    byId.get(p.id).boxes.push({ line_id: ln.id, item, release_at: ln.release_at, advance_days: ln.advance_days, effective_at: effectiveOf(ln) });
  }
  const people = [];
  for (const g of byId.values()) {
    const satisfying = g.boxes.filter(b => sat(b.effective_at));
    const include = mode === 'all' ? (g.boxes.length > 0 && g.boxes.every(b => sat(b.effective_at))) : satisfying.length > 0;
    if (!include) continue;
    people.push({
      person: g.person, boxes: g.boxes, satisfying,
      total: g.boxes.length, satisfiedCount: satisfying.length,
      allOut: g.boxes.every(b => sat(b.effective_at)),
    });
  }
  people.sort(byName);
  return { refDate, criterion, mode, people };
}

module.exports = { todayIso, cleanDate, daysUntil, releaseGroups, releaseSearch, peopleForNotif };
