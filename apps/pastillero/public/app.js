'use strict';

const API = '/pastillero/api';
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const main = () => $('pt-main');

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('application/json') ? await r.json().catch(() => ({})) : {};
  if (!r.ok) throw new Error(data.error || ('Error ' + r.status));
  return data;
}
function jbody(obj) { return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) }; }

let toastTimer = null;
function toast(msg, kind) {
  const t = $('toast'); t.textContent = msg; t.className = 'pt-toast' + (kind ? ' ' + kind : ''); t.hidden = false;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}

// Same per-medication shape system as Data Matrix / Asignación, so a caregiver
// sees the exact same colour/shape the pharmacy already uses for that medication.
// This is the stand-in "pill" until Fase 3 adds real photos per medication.
function shapeSvg(shape, color, px) {
  px = px || 28; const c = color || '#1273b8';
  const s = {
    circle: `<circle cx="12" cy="12" r="9" fill="${c}"/>`, square: `<rect x="3.5" y="3.5" width="17" height="17" rx="3" fill="${c}"/>`,
    triangle: `<path d="M12 3l9 16H3z" fill="${c}"/>`, diamond: `<path d="M12 2l10 10-10 10L2 12z" fill="${c}"/>`,
    hexagon: `<path d="M7 3h10l5 9-5 9H7l-5-9z" fill="${c}"/>`, star: `<path d="M12 2l2.9 6 6.6.6-5 4.3 1.6 6.5L12 22l-5.7 3.4 1.6-6.5-5-4.3 6.6-.6z" fill="${c}"/>`,
    pentagon: `<path d="M12 2l10 7.3-3.8 11.7H5.8L2 9.3z" fill="${c}"/>`, cross: `<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" fill="${c}"/>`,
  }[shape] || `<circle cx="12" cy="12" r="9" fill="${c}"/>`;
  return `<svg class="pt-shape" width="${px}" height="${px}" viewBox="0 0 24 24" aria-hidden="true">${s}</svg>`;
}
function lget(k, d) { try { return localStorage.getItem(k) || d; } catch { return d; } }
function lset(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } }

const S = {
  residencia: null, view: 'login', people: [], peopleNow: null, q: '', personId: null, personName: '', date: null,
  homeView: lget('pt_home_view', 'list'),     // 'list' | 'cards' — whole-residency overview
  fichaView: lget('pt_ficha_view', 'list'),   // 'list' | 'pills' — per-franja rendering
  fichaData: null,                            // last loaded ficha payload (zoom reuses it, no refetch)
  zoom: null,                                 // { date, slot } when the full-screen view is open
};

// ── Boot ──────────────────────────────────────────────────────────────────────
(async function boot() {
  try {
    const { residencia } = await api('/me');
    if (residencia) { S.residencia = residencia; $('res-name').textContent = residencia.group_name; $('btn-logout').hidden = false; viewHome(); }
    else viewLogin();
  } catch { viewLogin(); }
})();

$('btn-logout').onclick = async () => {
  try { await api('/logout', { method: 'POST' }); } catch { /* ignore */ }
  location.reload();
};

// ── Login ─────────────────────────────────────────────────────────────────────
function viewLogin() {
  S.view = 'login';
  $('btn-logout').hidden = true; $('res-name').textContent = '';
  main().innerHTML = `
    <div class="pt-login">
      <div class="pt-login-card">
        <div class="pt-login-ico">💊</div>
        <h1>Pastillero</h1>
        <p>Introduce el código de tu residencia para ver la medicación de cada persona.</p>
        <input class="pt-code-input" id="code" inputmode="text" autocapitalize="characters" autocomplete="off" maxlength="8" placeholder="CÓDIGO">
        <button class="pt-btn pt-btn-primary pt-btn-lg" id="go">Entrar</button>
        <div class="pt-login-err" id="login-err" hidden></div>
      </div>
    </div>`;
  const input = $('code');
  input.addEventListener('input', () => { input.value = input.value.toUpperCase(); });
  input.addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
  $('go').onclick = doLogin;
  input.focus();
}
async function doLogin() {
  const code = $('code').value.trim();
  const err = $('login-err');
  if (!code) { err.textContent = 'Escribe el código.'; err.hidden = false; return; }
  try {
    const r = await api('/login', jbody({ code }));
    S.residencia = r.residencia; $('res-name').textContent = r.residencia.group_name; $('btn-logout').hidden = false;
    viewHome();
  } catch (e) { err.textContent = e.message; err.hidden = false; }
}

// ── Home: the whole residencia at a glance, list or cards, filterable ───────────
const SLOT_ICONS = { desayuno: '🌅', comida: '🍽️', cena: '🌆', noche: '🌙' };
const SLOT_ORDER = ['desayuno', 'comida', 'cena', 'noche'];

function fmtDateLong(iso) {
  const d = new Date(iso + 'T00:00:00');
  const s = d.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
  return s.charAt(0).toUpperCase() + s.slice(1);   // "Miércoles, 26 de agosto" — only the first letter
}
function shiftDate(iso, days) {
  const d = new Date(iso + 'T00:00:00');
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
// Short "when is the next dose" label for a person's overview row/card.
function doseLabel(next, now) {
  if (!next) return null;
  const icon = SLOT_ICONS[next.slot], name = next.slot[0].toUpperCase() + next.slot.slice(1);
  if (next.is_now) return `${icon} Ahora: ${name}`;
  if (next.is_today) return `${icon} Hoy: ${name}`;
  if (now && next.date === shiftDate(now.date, 1)) return `${icon} Mañana: ${name}`;
  return `${icon} ${fmtDateLong(next.date)}: ${name}`;
}

let searchTimer = null;
function viewHome() {
  S.view = 'home';
  main().innerHTML = `
    <div class="pt-home">
      <div class="pt-home-top">
        <div class="pt-search"><span class="ico">🔎</span><input id="q" placeholder="Buscar por nombre…" autocomplete="off" value="${esc(S.q)}"></div>
        <div class="pt-seg" id="home-view">
          <button type="button" data-hv="list" class="${S.homeView === 'list' ? 'on' : ''}" title="Ver como lista">☰</button>
          <button type="button" data-hv="cards" class="${S.homeView === 'cards' ? 'on' : ''}" title="Ver como tarjetas">▦</button>
        </div>
      </div>
      <div id="people-list" class="pt-people-list"></div>
    </div>`;
  const q = $('q');
  q.oninput = () => { S.q = q.value; clearTimeout(searchTimer); searchTimer = setTimeout(loadPeople, 200); };
  $('home-view').querySelectorAll('[data-hv]').forEach(b => b.onclick = () => {
    S.homeView = b.dataset.hv; lset('pt_home_view', S.homeView);
    $('home-view').querySelectorAll('[data-hv]').forEach(x => x.classList.toggle('on', x === b));
    renderPeopleList();
  });
  loadPeople();
}
async function loadPeople() {
  const list = $('people-list');
  if (!list) return;
  list.innerHTML = '<div class="pt-empty">Cargando…</div>';
  try {
    const { items, now } = await api('/people?q=' + encodeURIComponent(S.q));
    S.people = items; S.peopleNow = now;
    renderPeopleList();
  } catch (e) { list.innerHTML = `<div class="pt-empty err">${esc(e.message)}</div>`; }
}
function personRowHtml(p) {
  const label = doseLabel(p.next_dose, S.peopleNow);
  return `<button class="pt-person-row" data-id="${p.id}">
    <span class="pt-person-ico">🧑</span>
    <span class="pt-person-name">${esc(p.apellidos)}, ${esc(p.nombre)}</span>
    ${label ? `<span class="pt-person-dose${p.next_dose.is_now ? ' is-now' : ''}">${label}</span>` : ''}
    <span class="pt-person-arrow">→</span>
  </button>`;
}
function personCardHtml(p) {
  const label = doseLabel(p.next_dose, S.peopleNow);
  return `<button class="pt-person-card" data-id="${p.id}">
    <span class="pt-person-card-ico">🧑</span>
    <span class="pt-person-card-name">${esc(p.apellidos)}, ${esc(p.nombre)}</span>
    <span class="pt-person-card-meds">💊 ${p.med_count} medicamento${p.med_count === 1 ? '' : 's'}</span>
    <span class="pt-person-card-dose${label ? (p.next_dose.is_now ? ' is-now' : '') : ' is-none'}">${label || 'Sin pauta definida'}</span>
  </button>`;
}
function renderPeopleList() {
  const list = $('people-list'); if (!list) return;
  const items = S.people;
  if (!items.length) { list.className = 'pt-people-list'; list.innerHTML = `<div class="pt-empty">${S.q ? 'Nadie coincide con esa búsqueda.' : 'Todavía no hay nadie en tu residencia.'}</div>`; return; }
  list.className = S.homeView === 'cards' ? 'pt-people-cards' : 'pt-people-list';
  list.innerHTML = items.map(p => S.homeView === 'cards' ? personCardHtml(p) : personRowHtml(p)).join('');
  list.querySelectorAll('[data-id]').forEach(b => b.onclick = () => {
    const p = items.find(x => x.id === Number(b.dataset.id));
    viewFicha(p.id, `${p.apellidos}, ${p.nombre}`, null);
  });
}

// ── Ficha: the Pastillero itself ──────────────────────────────────────────────
async function viewFicha(personId, personName, date) {
  S.view = 'ficha'; S.personId = personId; S.personName = personName; S.date = date; S.zoom = null;
  main().innerHTML = `<div class="pt-ficha-loading">Cargando…</div>`;
  try {
    const data = await api(`/person/${personId}/pastillero` + (date ? `?date=${date}` : ''));
    renderFicha(data);
  } catch (e) {
    main().innerHTML = `<div class="pt-empty err">${esc(e.message)}</div><button class="pt-btn pt-btn-ghost" id="back">← Volver</button>`;
    $('back').onclick = viewHome;
  }
}

// One unit of medication = one square. A qty of 2 becomes two identical squares,
// so a caregiver can literally count "3 pastillas: 2 grandes y 1 pequeña".
function expandPills(meds) {
  const out = [];
  for (const m of meds) for (let i = 0; i < m.qty; i++) out.push(m);
  return out;
}
// Never drop a real dose: no hard cap, the grid just wraps into more rows if a
// franja legitimately has more pills than fit in one line.
// In the full-screen zoom, fewer pills means each one gets to be bigger — a
// single pill fills most of the screen, sixteen sit at the baseline size.
function zoomCellBase(count) {
  if (count <= 1) return 150; if (count <= 2) return 128; if (count <= 4) return 104;
  if (count <= 6) return 90; if (count <= 9) return 76; return 64;
}
// How much of the viewport width a cell may claim — generous when few pills
// share the row, tighter once ~4+ need to sit side by side.
function zoomCellVwCap(count) {
  if (count <= 1) return 46; if (count <= 2) return 34; if (count <= 4) return 22; return 20;
}
function pillGridHtml(meds, size) {
  const pills = expandPills(meds);
  if (!pills.length) return `<div class="pt-slot-empty">Sin medicación en esta franja.</div>`;
  if (size === 'lg') {
    const cell = `min(${zoomCellBase(pills.length)}px, ${zoomCellVwCap(pills.length)}vw)`;
    return `<div class="pt-pill-grid pt-pill-grid-lg" style="--cell:${cell}">${pills.map(m =>
      `<div class="pt-pill-cell" title="${esc(m.nombre)}">${shapeSvg(m.shape, m.color, 60)}</div>`).join('')}</div>`;
  }
  return `<div class="pt-pill-grid pt-pill-grid-sm">${pills.map(m =>
    `<div class="pt-pill-cell" title="${esc(m.nombre)}">${shapeSvg(m.shape, m.color, 22)}</div>`).join('')}</div>`;
}
function slotListHtml(meds) {
  if (!meds.length) return `<div class="pt-slot-empty">Sin medicación en esta franja.</div>`;
  return meds.map(m => `
    <div class="pt-med-row">
      ${shapeSvg(m.shape, m.color, 30)}
      <span class="pt-med-name">${esc(m.nombre)}</span>
      <span class="pt-med-qty">×${m.qty}</span>
    </div>`).join('');
}
function slotCardHtml(slot, meds, isCurrent) {
  const body = S.fichaView === 'pills' ? pillGridHtml(meds, 'sm') : slotListHtml(meds);
  return `
    <div class="pt-slot-card ${isCurrent ? 'is-now' : ''}">
      <div class="pt-slot-h">
        <span class="pt-slot-ico">${SLOT_ICONS[slot]}</span>
        <span class="pt-slot-title">${slot[0].toUpperCase()}${slot.slice(1)}</span>
        ${isCurrent ? '<span class="pt-now-badge">AHORA</span>' : ''}
        <button class="pt-zoom-btn" data-zoom="${slot}" title="Ver esta franja en grande">⛶</button>
      </div>
      <div class="pt-slot-body">${body}</div>
    </div>`;
}

function renderFicha(data) {
  S.fichaData = data;
  const { person, date, is_today, now, slots, empty } = data;
  S.date = date;
  const currentSlot = is_today ? now.slot : null;
  const slotsHtml = SLOT_ORDER.map(s => slotCardHtml(s, slots[s], s === currentSlot)).join('');
  main().innerHTML = `
    <div class="pt-ficha-top">
      <button class="pt-back" id="back">← Volver</button>
      <div class="pt-ficha-name">${esc(person.apellidos)}, ${esc(person.nombre)}</div>
    </div>
    <div class="pt-seg pt-ficha-seg" id="ficha-view">
      <button type="button" data-fv="list" class="${S.fichaView === 'list' ? 'on' : ''}">☰ Lista</button>
      <button type="button" data-fv="pills" class="${S.fichaView === 'pills' ? 'on' : ''}">💊 Pastillas</button>
    </div>
    <div class="pt-now-hero" id="now-hero" role="button" tabindex="0" title="Ver esta franja en grande">
      <div class="pt-now-day">${is_today ? 'Hoy' : fmtDateLong(date)}${is_today ? ` · ${now.time}` : ''}</div>
      ${is_today
        ? `<div class="pt-now-slot">${SLOT_ICONS[now.slot]} Le toca ahora: <b>${now.slot[0].toUpperCase()}${now.slot.slice(1)}</b></div>`
        : `<div class="pt-now-slot pt-now-slot-sm">Pulsa para ver una franja a pantalla completa ⛶</div>`}
    </div>
    <div class="pt-date-nav">
      <button class="pt-btn pt-btn-ghost" id="prev-day">← Día anterior</button>
      <button class="pt-btn pt-btn-ghost" id="go-today" ${is_today ? 'disabled' : ''}>Hoy / Ahora</button>
      <button class="pt-btn pt-btn-ghost" id="next-day">Día siguiente →</button>
    </div>
    ${!is_today ? `<div class="pt-date-label">${fmtDateLong(date)}</div>` : ''}
    ${empty ? `<div class="pt-empty">Todavía no hay ninguna pauta por franja definida para esta persona. Pídele a la farmacia que la configure en Asignación.</div>` : ''}
    <div class="pt-slots">${slotsHtml}</div>`;
  $('back').onclick = viewHome;
  $('prev-day').onclick = () => viewFicha(person.id, S.personName, shiftDate(date, -1));
  $('next-day').onclick = () => viewFicha(person.id, S.personName, shiftDate(date, 1));
  $('go-today').onclick = () => viewFicha(person.id, S.personName, null);
  $('ficha-view').querySelectorAll('[data-fv]').forEach(b => b.onclick = () => {
    S.fichaView = b.dataset.fv; lset('pt_ficha_view', S.fichaView); renderFicha(data);
  });
  const openZoomFor = slot => openZoom(slot || currentSlot || 'desayuno');
  $('now-hero').onclick = () => openZoomFor(currentSlot);
  $('now-hero').onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openZoomFor(currentSlot); } };
  main().querySelectorAll('[data-zoom]').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); openZoomFor(b.dataset.zoom); }));
}

// ── Zoom: one franja, full screen, big pills ─────────────────────────────────
function openZoom(slot) {
  S.zoom = { date: S.date, slot };
  renderZoom();
}
function closeZoom() {
  S.zoom = null;
  renderFicha(S.fichaData);
}
async function zoomShiftDay(days) {
  const date = shiftDate(S.zoom.date, days);
  try {
    const data = await api(`/person/${S.personId}/pastillero?date=${date}`);
    S.fichaData = data; S.date = date; S.zoom = { date, slot: S.zoom.slot };
    renderZoom();
  } catch (e) { toast(e.message, 'err'); }
}
async function zoomShiftSlot(dir) {
  let idx = SLOT_ORDER.indexOf(S.zoom.slot) + dir;
  let date = S.zoom.date;
  if (idx < 0) { idx = 3; date = shiftDate(date, -1); }
  else if (idx > 3) { idx = 0; date = shiftDate(date, 1); }
  const slot = SLOT_ORDER[idx];
  if (date !== S.zoom.date) {
    try { const data = await api(`/person/${S.personId}/pastillero?date=${date}`); S.fichaData = data; S.date = date; }
    catch (e) { toast(e.message, 'err'); return; }
  }
  S.zoom = { date, slot };
  renderZoom();
}
function renderZoom() {
  const data = S.fichaData;
  const { slot, date } = S.zoom;
  const meds = (data.slots && data.slots[slot]) || [];
  const isToday = date === data.now.date;
  const isNow = isToday && data.now.slot === slot;
  main().innerHTML = `
    <div class="pt-zoom">
      <div class="pt-zoom-top">
        <button class="pt-back" id="zoom-close">✕ Volver</button>
        <div class="pt-zoom-title">${SLOT_ICONS[slot]} ${slot[0].toUpperCase()}${slot.slice(1)}${isNow ? ' <span class="pt-now-badge">AHORA</span>' : ''}</div>
      </div>
      <div class="pt-zoom-day">${isToday ? 'Hoy' : fmtDateLong(date)}</div>
      <div class="pt-zoom-grid-wrap">${pillGridHtml(meds, 'lg')}</div>
      <div class="pt-zoom-nav">
        <button class="pt-btn pt-btn-ghost" id="zoom-prev-slot">← Franja</button>
        <button class="pt-btn pt-btn-ghost" id="zoom-prev-day">← Día</button>
        <button class="pt-btn pt-btn-ghost" id="zoom-next-day">Día →</button>
        <button class="pt-btn pt-btn-ghost" id="zoom-next-slot">Franja →</button>
      </div>
    </div>`;
  $('zoom-close').onclick = closeZoom;
  $('zoom-prev-slot').onclick = () => zoomShiftSlot(-1);
  $('zoom-next-slot').onclick = () => zoomShiftSlot(1);
  $('zoom-prev-day').onclick = () => zoomShiftDay(-1);
  $('zoom-next-day').onclick = () => zoomShiftDay(1);
}
