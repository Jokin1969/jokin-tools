'use strict';

// ── Asignación — release-date computation (shared by routes, cron and email) ─────
// The release date lives on the MEDICATION (recurring plan), not on a box: a box is
// dispensed and gone, but the medication returns every month on the same Salud
// date. Availability runs on the EFFECTIVE date = official − anticipation days.

const qrDb = require('../qr-tis/db');
const dmDb = require('../datamatrix/db');
const dmVisual = require('../datamatrix/visual');
const db = require('./db');

function todayIso() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
function cleanDate(v) { const s = String(v == null ? '' : v).trim(); return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : null; }
function daysUntil(iso) { if (!iso) return null; const a = new Date(todayIso() + 'T00:00:00'), b = new Date(iso + 'T00:00:00'); if (isNaN(b)) return null; return Math.round((b - a) / 86400000); }
const nameKey = p => `${p.apellidos} ${p.nombre}`;
const byName = (a, b) => nameKey(a.person).localeCompare(nameKey(b.person), 'es', { sensitivity: 'base' });

// Name/colour/shape for a plan medication (catalogue by GTIN, else the typed name).
function medMeta(pm) {
  const prod = pm.gtin ? dmDb.getProduct(pm.gtin) : null;
  return {
    nombre: (prod && prod.nombre) || pm.nombre || 'Medicamento',
    color: dmVisual.resolveColor(pm.gtin, prod && prod.color),
    shape: dmVisual.resolveShape(pm.gtin, prod && prod.shape),
  };
}
function effectiveOf(pm) { return db.effectiveDate(pm.release_at, pm.advance_days); }

// Group active, dated plan medications by person.
function releaseGroups() {
  const byId = new Map();
  for (const pm of db.plansForRelease()) {
    const p = qrDb.getPerson(pm.person_id);
    if (!p) continue;
    const eff = effectiveOf(pm);
    const meta = medMeta(pm);
    if (!byId.has(p.id)) byId.set(p.id, { person: { id: p.id, nombre: p.nombre, apellidos: p.apellidos, tis: p.tis }, meds: [] });
    byId.get(p.id).meds.push({
      plan_id: pm.id, gtin: pm.gtin || null, cn: pm.cn || null,
      nombre: meta.nombre, color: meta.color, shape: meta.shape,
      release_at: pm.release_at, advance_days: pm.advance_days, effective_at: eff, days: daysUntil(eff),
    });
  }
  return byId;
}

// Bell search: date + criterion (lte/exact) + mode. 'box' now means "per medication".
function releaseSearch(q) {
  const today = todayIso();
  const date = cleanDate(q.date) || today;
  const criterion = q.criterion === 'exact' ? 'exact' : 'lte';
  const mode = ['box', 'all', 'any'].includes(q.mode) ? q.mode : (db.getSettings().notify_mode || 'all');
  const sat = (eff) => criterion === 'exact' ? eff === date : eff <= date;
  const groups = [...releaseGroups().values()];
  const matched = [], pending = [];

  if (mode === 'box') {
    for (const g of groups) for (const m of g.meds) (sat(m.effective_at) ? matched : pending).push({ person: g.person, ...m });
    const cmp = (a, b) => byName(a, b) || a.effective_at.localeCompare(b.effective_at);
    matched.sort(cmp); pending.sort(cmp);
  } else {
    for (const g of groups) {
      const dates = g.meds.map(m => m.effective_at);
      const aggDate = mode === 'all' ? dates.reduce((m, d) => (d > m ? d : m)) : dates.reduce((m, d) => (d < m ? d : m));
      const ready = mode === 'all' ? g.meds.every(m => sat(m.effective_at)) : g.meds.some(m => sat(m.effective_at));
      const entry = {
        person: g.person, aggDate, aggDays: daysUntil(aggDate), total: g.meds.length,
        releasedByToday: g.meds.filter(m => m.effective_at <= today).length,
        meds: g.meds.map(m => ({ ...m, satisfied: sat(m.effective_at) })).sort((a, b) => a.effective_at.localeCompare(b.effective_at)),
      };
      (ready ? matched : pending).push(entry);
    }
    matched.sort(byName); pending.sort(byName);
  }
  return { today, date, criterion, mode, matched, pending, counts: { matched: matched.length, pending: pending.length } };
}

// Rich per-person data for the notification email. For each satisfying medication
// we include its pre-assigned box (if any) so the Data Matrix can be rendered.
function peopleForNotif(opts, refDate) {
  const criterion = opts.criterion === 'exact' ? 'exact' : 'lte';
  const mode = opts.ntype === 'all' ? 'all' : 'any';
  const sat = (eff) => criterion === 'exact' ? eff === refDate : eff <= refDate;
  const byId = new Map();
  for (const pm of db.plansForRelease()) {
    const p = qrDb.getPerson(pm.person_id);
    if (!p) continue;
    const eff = effectiveOf(pm);
    const line = pm.gtin ? db.findPendingLineForMed(pm.person_id, pm.gtin) : null;
    const item = line ? dmDb.getItem(line.item_id) : null;
    const meta = medMeta(pm);
    if (!byId.has(p.id)) byId.set(p.id, { person: p, meds: [] });
    byId.get(p.id).meds.push({ plan_id: pm.id, nombre: meta.nombre, gtin: pm.gtin || null, cn: pm.cn || null, release_at: pm.release_at, effective_at: eff, item });
  }
  const people = [];
  for (const g of byId.values()) {
    const satisfying = g.meds.filter(m => sat(m.effective_at));
    const include = mode === 'all' ? (g.meds.length > 0 && g.meds.every(m => sat(m.effective_at))) : satisfying.length > 0;
    if (!include) continue;
    people.push({
      person: g.person, meds: g.meds, satisfying,
      total: g.meds.length, satisfiedCount: satisfying.length,
      allOut: g.meds.every(m => sat(m.effective_at)),
    });
  }
  people.sort(byName);
  return { refDate, criterion, mode, people };
}

module.exports = { todayIso, cleanDate, daysUntil, releaseGroups, releaseSearch, peopleForNotif };
