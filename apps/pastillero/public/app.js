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

const S = { residencia: null, view: 'login', people: [], q: '', personId: null, personName: '', date: null };

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

// ── Home: search ──────────────────────────────────────────────────────────────
let searchTimer = null;
function viewHome() {
  S.view = 'home';
  main().innerHTML = `
    <div class="pt-home">
      <div class="pt-search"><span class="ico">🔎</span><input id="q" placeholder="Buscar por nombre…" autocomplete="off" value="${esc(S.q)}"></div>
      <div id="people-list" class="pt-people-list"></div>
    </div>`;
  const q = $('q');
  q.oninput = () => { S.q = q.value; clearTimeout(searchTimer); searchTimer = setTimeout(loadPeople, 200); };
  q.focus();
  loadPeople();
}
async function loadPeople() {
  const list = $('people-list');
  if (!list) return;
  list.innerHTML = '<div class="pt-empty">Buscando…</div>';
  try {
    const { items } = await api('/people?q=' + encodeURIComponent(S.q));
    S.people = items;
    if (!items.length) { list.innerHTML = `<div class="pt-empty">${S.q ? 'Nadie coincide con esa búsqueda.' : 'Escribe un nombre para empezar.'}</div>`; return; }
    list.innerHTML = items.map(p => `
      <button class="pt-person-row" data-id="${p.id}">
        <span class="pt-person-ico">🧑</span>
        <span class="pt-person-name">${esc(p.apellidos)}, ${esc(p.nombre)}</span>
        <span class="pt-person-arrow">→</span>
      </button>`).join('');
    list.querySelectorAll('[data-id]').forEach(b => b.onclick = () => {
      const p = items.find(x => x.id === Number(b.dataset.id));
      viewFicha(p.id, `${p.apellidos}, ${p.nombre}`, null);
    });
  } catch (e) { list.innerHTML = `<div class="pt-empty err">${esc(e.message)}</div>`; }
}

// ── Ficha: the Pastillero itself ──────────────────────────────────────────────
const SLOT_ICONS = { desayuno: '🌅', comida: '🍽️', cena: '🌆', noche: '🌙' };
const SLOT_ORDER = ['desayuno', 'comida', 'cena', 'noche'];

function fmtDateLong(iso) {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
}
function shiftDate(iso, days) {
  const d = new Date(iso + 'T00:00:00');
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

async function viewFicha(personId, personName, date) {
  S.view = 'ficha'; S.personId = personId; S.personName = personName; S.date = date;
  main().innerHTML = `<div class="pt-ficha-loading">Cargando…</div>`;
  try {
    const data = await api(`/person/${personId}/pastillero` + (date ? `?date=${date}` : ''));
    renderFicha(data);
  } catch (e) {
    main().innerHTML = `<div class="pt-empty err">${esc(e.message)}</div><button class="pt-btn pt-btn-ghost" id="back">← Volver</button>`;
    $('back').onclick = viewHome;
  }
}

function slotCardHtml(slot, meds, isCurrent) {
  const rows = meds.length
    ? meds.map(m => `
        <div class="pt-med-row">
          ${shapeSvg(m.shape, m.color, 30)}
          <span class="pt-med-name">${esc(m.nombre)}</span>
          <span class="pt-med-qty">×${m.qty}</span>
        </div>`).join('')
    : `<div class="pt-slot-empty">Sin medicación en esta franja.</div>`;
  return `
    <div class="pt-slot-card ${isCurrent ? 'is-now' : ''}">
      <div class="pt-slot-h"><span class="pt-slot-ico">${SLOT_ICONS[slot]}</span><span class="pt-slot-title">${slot[0].toUpperCase()}${slot.slice(1)}</span>${isCurrent ? '<span class="pt-now-badge">AHORA</span>' : ''}</div>
      <div class="pt-slot-body">${rows}</div>
    </div>`;
}

function renderFicha(data) {
  const { person, date, is_today, now, slots, empty } = data;
  S.date = date;
  const currentSlot = is_today ? now.slot : null;
  const slotsHtml = SLOT_ORDER.map(s => slotCardHtml(s, slots[s], s === currentSlot)).join('');
  main().innerHTML = `
    <div class="pt-ficha-top">
      <button class="pt-back" id="back">← Volver</button>
      <div class="pt-ficha-name">${esc(person.apellidos)}, ${esc(person.nombre)}</div>
    </div>
    <div class="pt-now-hero">
      <div class="pt-now-day">${is_today ? 'Hoy' : fmtDateLong(date)}${is_today ? ` · ${now.time}` : ''}</div>
      ${is_today ? `<div class="pt-now-slot">${SLOT_ICONS[now.slot]} Le toca ahora: <b>${now.slot[0].toUpperCase()}${now.slot.slice(1)}</b></div>` : ''}
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
}
