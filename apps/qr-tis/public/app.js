'use strict';

// ── Gestión de QR (TIS) — frontend SPA ──────────────────────────────────────────
// Three views: (1) introducir, (2) visualizar (listado), (3) ficha con QR grande.
// Plus a per-user cart. QR codes are generated in the browser (qrcode-generator)
// so the size/colour "mando" is instant; decoding for the scan-input uses jsQR.

const API = '/qr-tis/api';
const $ = id => document.getElementById(id);
const main = () => $('qt-main');

const S = {
  people: [], byId: new Map(), settings: null, user: null, canAsignacion: false,
  cart: new Set(),
  query: '', andor: 'AND',
  sort: { key: 'apellidos', dir: 'asc' },
  selected: new Set(), hidden: new Set(),
  showListQr: false, selectedOnly: false, cartView: false, hideDeceased: false, notesOnly: false,
  listMode: 'table', // 'table' | 'cards'
  groupFilter: null, groupsOpen: false, // group filter cards (collapsed by default)
  currentPersonId: null, view: 'home',
  nav: [], // ordered person ids for the Anterior/Siguiente context of the ficha
};

// Open a person's ficha carrying the navigation context it came from (an ordered
// list of ids), so Anterior/Siguiente cycle exactly that subset — not the whole DB.
function gotoFicha(id, navIds) { S.nav = Array.isArray(navIds) ? navIds.slice() : []; viewFicha(id); }

// ── Tiny helpers ────────────────────────────────────────────────────────────────
function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
// Accent/ñ-insensitive, lowercase — for the fast search.
function norm(s) { return String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
function fmtTis(t) { return String(t || '').replace(/(\d{4})(\d{4})/, '$1 $2'); }

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json().catch(() => ({})) : {};
  if (!r.ok) throw new Error(data.error || `Error ${r.status}`);
  return data;
}
function jbody(obj) { return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) }; }

let toastTimer = null;
function toast(msg, kind) {
  const t = $('toast'); t.textContent = msg; t.className = 'qt-toast' + (kind ? ' ' + kind : ''); t.hidden = false;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}
function confirmBox(title, body, okLabel) {
  return new Promise(resolve => {
    $('confirm-title').textContent = title;
    $('confirm-body').textContent = body;
    $('confirm-yes').textContent = okLabel || 'Aceptar';
    const m = $('confirm-modal'); m.hidden = false;
    const done = v => { m.hidden = true; $('confirm-yes').onclick = null; $('confirm-no').onclick = null; resolve(v); };
    $('confirm-yes').onclick = () => done(true);
    $('confirm-no').onclick = () => done(false);
  });
}

// ── QR rendering (client-side SVG) ──────────────────────────────────────────────
function qrSvg(text, o) {
  o = o || {};
  const dark = o.dark || '#000000', light = o.light || '#ffffff';
  const style = o.style === 'dots' ? 'dots' : 'square';
  const ecc = ['L', 'M', 'Q', 'H'].includes(o.ecc) ? o.ecc : 'M';
  const size = o.size || 300, margin = 4;
  let qr;
  try { qr = qrcode(0, ecc); qr.addData(String(text)); qr.make(); }
  catch (e) { return `<svg width="${size}" height="${size}"></svg>`; }
  const n = qr.getModuleCount(), tot = n + margin * 2;
  // The three 7×7 finder patterns must stay solid squares or scanners lose the
  // locator. Data modules can be rounded ("dots"), but they overlap slightly so
  // they stay connected — separate circles with gaps don't scan reliably.
  const inFinder = (r, c) => (r < 7 && c < 7) || (r < 7 && c >= n - 7) || (r >= n - 7 && c < 7);
  let d = '';
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) {
    const x = c + margin, y = r + margin;
    d += (style === 'dots' && !inFinder(r, c))
      ? `<rect x="${(x - 0.02).toFixed(2)}" y="${(y - 0.02).toFixed(2)}" width="1.04" height="1.04" rx="0.5" ry="0.5"/>`
      : `<rect x="${(x - 0.02).toFixed(2)}" y="${(y - 0.02).toFixed(2)}" width="1.04" height="1.04"/>`;
  }
  const rendering = style === 'dots' ? 'geometricPrecision' : 'crispEdges';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${tot} ${tot}" shape-rendering="${rendering}"><rect width="${tot}" height="${tot}" fill="${light}"/><g fill="${dark}">${d}</g></svg>`;
}

// Effective QR options for a person: colour/background/style come from the person
// (per-person), falling back to the shared defaults; size and robustness are global.
// The QR colour a person inherits from their group/residence, if any (first group
// that has a colour assigned). Used as the default when the person has no override.
function groupColorFor(p) {
  const gc = (S.settings && S.settings.group_colors) || {};
  if (!p || !Array.isArray(p.groups)) return null;
  for (const g of p.groups) if (gc[g]) return gc[g];
  return null;
}
// A single group's colour, and helpers to tint its name chips/cards with it.
function groupColorByName(n) { const gc = (S.settings && S.settings.group_colors) || {}; return gc[n] || null; }
function gcCls(n) { return groupColorByName(n) ? ' has-gc' : ''; }
function gcStyle(n) { const c = groupColorByName(n); return c ? ` style="--gc:${esc(c)}"` : ''; }
// What the person's QR must encode: the real pharmacy code when set, else the TIS
// (fallback while codes are still being loaded). Never shown as text — only encoded.
function qrValue(p) { return (p && p.qr_code) ? p.qr_code : (p ? p.tis : ''); }
function qrOpts(p, size) {
  const st = S.settings;
  return {
    dark: (p && p.qr_dark) || groupColorFor(p) || st.qr_dark,
    light: (p && p.qr_light) || st.qr_light,
    style: (p && p.qr_style) || st.qr_style,
    ecc: st.qr_ecc,
    size,
  };
}

// ── Data loading ────────────────────────────────────────────────────────────────
async function reloadPeople() {
  const { items } = await api('/people');
  S.people = items;
  S.byId = new Map(items.map(p => [p.id, p]));
}
async function reloadCart() {
  const { ids } = await api('/cart');
  S.cart = new Set(ids);
  updateCartCount();
}
function updateCartCount() { $('cart-count').textContent = S.cart.size; }

// ── Settings (the QR "mando") ────────────────────────────────────────────────────
let settingsTimer = null;
function saveSettingsDebounced() {
  if (settingsTimer) clearTimeout(settingsTimer);
  settingsTimer = setTimeout(async () => {
    try { const { settings } = await api('/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(S.settings) }); S.settings = settings; }
    catch (e) { toast(e.message, 'err'); }
  }, 400);
}

// Persist a person's per-person QR overrides (colour/background/style), debounced.
let pqrTimer = null, pqrId = null, pqrPatch = {};
function savePersonQrDebounced(id, patch) {
  if (pqrId !== id) pqrPatch = {};
  pqrId = id; pqrPatch = { ...pqrPatch, ...patch };
  if (pqrTimer) clearTimeout(pqrTimer);
  pqrTimer = setTimeout(async () => {
    const saveId = pqrId, savePatch = pqrPatch; pqrId = null; pqrPatch = {};
    try {
      const { item } = await api('/people/' + saveId, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(savePatch) });
      S.byId.set(item.id, item); const i = S.people.findIndex(x => x.id === item.id); if (i >= 0) S.people[i] = item;
    } catch (e) { toast(e.message, 'err'); }
  }, 400);
}

// ── Views ─────────────────────────────────────────────────────────────────────
function showView(name, arg) {
  if (name === 'home') return viewHome();
  if (name === 'form') return viewForm();
  if (name === 'list') return viewList();
  if (name === 'ficha') return viewFicha(arg);
}

// Home — two clear cards (add a person / consult everyone).
function viewHome() {
  S.view = 'home';
  const card = (n, go, ico, title, desc) =>
    `<button class="qt-card" data-go="${go}">
       <div class="qt-card-n">0${n}</div>
       <div class="qt-card-ico">${ico}</div>
       <h3>${title}</h3><p>${desc}</p>
     </button>`;
  const icoAdd = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M24 12v24M12 24h24"/><rect x="6" y="6" width="36" height="36" rx="8" opacity="0.35"/></svg>`;
  const icoQr = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4"><rect x="8" y="8" width="12" height="12" rx="2"/><rect x="28" y="8" width="12" height="12" rx="2"/><rect x="8" y="28" width="12" height="12" rx="2"/><path d="M28 28h5v5M40 28v5h-5M28 40h5M35 35v5h5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  main().innerHTML =
    `<div class="qt-hero"><h1>Gestión de QR (TIS)</h1><p>Personas y su Código TIS como códigos QR listos para escanear. <a id="hero-help" style="color:var(--brand);font-weight:600;cursor:pointer">¿Cómo funciona? Abre la ayuda ❔</a></p></div>
     <div class="qt-cards qt-cards-2">
       ${card(1, 'form', icoAdd, 'Introducir persona', 'Da de alta a alguien: nombre, apellidos y Código TIS (a mano o escaneando un QR). Genera su código al instante.')}
       ${card(2, 'list', icoQr, 'Consultar personas', 'Busca, filtra y ordena a todas las personas —como lista o como tarjetas— y pulsa a cualquiera para ver y usar su QR en grande.')}
     </div>`;
  main().querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => showView(b.dataset.go)));
  const hh = $('hero-help'); if (hh) hh.onclick = viewHelp;
}

// ── (1) Introducir ──────────────────────────────────────────────────────────────
function viewForm() {
  S.view = 'form';
  main().innerHTML =
    `<button class="qt-back" id="back">← Inicio</button>
     <div class="qt-panel qt-form">
       <div class="qt-section-title">Introducir persona / TIS</div>
       <div class="qt-section-sub">Los campos marcados con <span style="color:var(--danger)">*</span> son obligatorios</div>
       <div class="qt-form-err" id="f-err"></div>
       <div class="qt-field">
         <label>Nº de farmacia <span class="req">*</span></label>
         <input class="qt-input" id="f-farmacia" placeholder="00000" inputmode="numeric" maxlength="5" autocomplete="off" style="font-family:var(--mono);letter-spacing:.28em;text-align:center" />
         <div class="qt-field-hint">5 cifras que asigna la farmacia (los ceros a la izquierda cuentan). No puede repetirse. <strong>Si no dispones de un número, añade 00000</strong> (este sí puede repetirse).</div>
       </div>
       <div class="qt-field">
         <label>Nombre <span class="req">*</span></label>
         <input class="qt-input" id="f-nombre" placeholder="p. ej. José" autocomplete="off" />
       </div>
       <div class="qt-field">
         <label>Apellidos <span class="req">*</span></label>
         <input class="qt-input" id="f-apellidos" placeholder="p. ej. Pérez García" autocomplete="off" />
       </div>
       <div class="qt-field">
         <label>Grupo (residencia)</label>
         <input class="qt-input" id="f-grupo" placeholder="p. ej. Residencia San José" autocomplete="off" />
         <div class="qt-field-hint">Opcional. También puedes añadirlo o cambiarlo más adelante desde la ficha de la persona.</div>
       </div>
       <div class="qt-field">
         <label>Código TIS <span class="req">*</span></label>
         <div class="qt-tis-wrap">
           <input class="qt-input" id="f-tis" placeholder="00000000" inputmode="numeric" maxlength="8" autocomplete="off" />
         </div>
         <div class="qt-field-hint">8 cifras. Los ceros a la izquierda cuentan. Enfoca aquí y escanea con el lector, o escríbelo a mano.</div>
       </div>
       <div class="qt-field">
         <label>Código del QR (opcional)</label>
         <textarea class="qt-input qt-input-tall" id="f-qrcode" rows="3" autocomplete="off" placeholder="Escanea con el lector (emulador de teclado) o escribe el código…"></textarea>
         <div class="qt-field-hint">Es lo que codifica realmente el QR (acepta cualquier texto alfanumérico, sin límite de longitud). Enfoca aquí y escanea con el lector, o escríbelo. <strong>No se muestra</strong> en la app. Vacío = el QR usa el Código TIS.</div>
       </div>
       <div class="qt-form-actions">
         <button class="qt-btn qt-btn-ghost" id="f-cancel">Cancelar</button>
         <button class="qt-btn qt-btn-primary" id="f-save">Generar QR ✦</button>
       </div>
     </div>`;
  $('back').onclick = viewHome;
  $('f-cancel').onclick = viewHome;
  const tisEl = $('f-tis');
  const grupoEl = $('f-grupo');
  const qrEl = $('f-qrcode');
  tisEl.addEventListener('input', () => { tisEl.value = tisEl.value.replace(/\D/g, '').slice(0, 8); });
  $('f-save').onclick = submitForm;
  const farmEl = $('f-farmacia');
  farmEl.addEventListener('input', () => { farmEl.value = farmEl.value.replace(/\D/g, '').slice(0, 5); });
  farmEl.focus();
  [farmEl, tisEl, $('f-nombre'), $('f-apellidos'), grupoEl].forEach(el => el.addEventListener('keydown', e => { if (e.key === 'Enter') submitForm(); }));
  // El lector de códigos termina el escaneo con un Enter; en un <textarea> eso
  // insertaría un salto de línea en vez de enviar el formulario.
  qrEl.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); submitForm(); } });
}

async function submitForm() {
  const pharmacy_no = $('f-farmacia').value.replace(/\D/g, '');
  const nombre = $('f-nombre').value.trim();
  const apellidos = $('f-apellidos').value.trim();
  const group_name = $('f-grupo').value.trim();
  const tis = $('f-tis').value.replace(/\D/g, '');
  const qr_code = $('f-qrcode').value;
  const err = $('f-err');
  $('f-farmacia').classList.toggle('is-invalid', !/^\d{5}$/.test(pharmacy_no));
  $('f-nombre').classList.toggle('is-invalid', !nombre);
  $('f-apellidos').classList.toggle('is-invalid', !apellidos);
  $('f-tis').classList.toggle('is-invalid', !/^\d{8}$/.test(tis));
  if (!/^\d{5}$/.test(pharmacy_no)) { err.textContent = 'El Nº de farmacia debe tener exactamente 5 cifras.'; return; }
  if (!nombre || !apellidos) { err.textContent = 'Nombre y apellidos son obligatorios.'; return; }
  if (!/^\d{8}$/.test(tis)) { err.textContent = 'El Código TIS debe tener exactamente 8 cifras.'; return; }
  err.textContent = '';
  try {
    const { item } = await api('/people', jbody({ pharmacy_no, nombre, apellidos, tis, group_name, qr_code }));
    await reloadPeople();
    toast('Persona guardada ✓', 'ok');
    S.nav = [];
    viewFicha(item.id, { justCreated: true });
  } catch (e) { err.textContent = e.message; }
}

// ── (3) Ficha — big QR ──────────────────────────────────────────────────────────
function viewFicha(id, opts) {
  opts = opts || {};
  const p = S.byId.get(id);
  if (!p) { toast('Persona no encontrada.', 'err'); return viewList(); }
  S.view = 'ficha'; S.currentPersonId = id;
  // Mark as "handled" so it surfaces in Recientes (fire-and-forget).
  if (!opts.justCreated) { api('/people/' + id + '/touch', { method: 'POST' }).catch(() => {}); }
  const inCart = S.cart.has(id);
  const st = S.settings;
  const qrHtml = p.active
    ? `<div class="qt-qr-box" id="ficha-qr">${qrSvg(qrValue(p), qrOpts(p, st.qr_size))}</div>`
    : p.deceased
      ? `<div class="qt-inactive-banner qt-deceased-banner">✝ Persona <strong>fallecida</strong>${p.deceased_at ? '<br>' + fmtDate(p.deceased_at) : ''}.<br>El QR no está disponible.</div>`
      : `<div class="qt-inactive-banner">Persona <strong>inactiva</strong>.<br>El QR no está disponible hasta reactivarla.</div>`;
  const groupChip = (p.groups && p.groups.length)
    ? p.groups.map(g => `<span class="qt-chip-group${gcCls(g)}"${gcStyle(g)} data-gsel="${esc(g)}" title="Seleccionar el grupo">👥 ${esc(g)}</span>`).join(' ')
    : '';
  // Anterior / Siguiente cycle the navigation context the ficha came from.
  const nav = (S.nav || []).filter(nid => S.byId.has(nid));
  const navIdx = nav.indexOf(id);
  const hasNav = navIdx >= 0 && nav.length > 1;
  const navBar = hasNav
    ? `<div class="qt-navpair">
         <span class="qt-navpos">${navIdx + 1} / ${nav.length}</span>
         <button class="qt-btn qt-btn-ghost qt-btn-sm" id="nav-prev" ${navIdx <= 0 ? 'disabled' : ''}>← Anterior</button>
         <button class="qt-btn qt-btn-ghost qt-btn-sm" id="nav-next" ${navIdx >= nav.length - 1 ? 'disabled' : ''}>Siguiente →</button>
       </div>`
    : '';
  main().innerHTML =
    `<div class="qt-ficha-top">
       <button class="qt-back" id="back">← ${opts.justCreated ? 'Inicio' : 'Volver'}</button>
       ${navBar}
     </div>
     <div class="qt-panel qt-ficha">
       <div class="qt-qr-stage">
         <div class="qt-qr-name">${esc(p.nombre)} ${esc(p.apellidos)}</div>
         ${qrHtml}
         <div class="qt-qr-tis">${p.active ? fmtTis(p.tis) : ''}</div>
         ${p.active ? mandoHtml(st, p) : ''}
       </div>
       <div class="qt-ficha-info">
         <h2>${esc(p.nombre)} ${esc(p.apellidos)}</h2>
         <div class="qt-ficha-meta">Alta: ${fmtDate(p.created_at)}${groupChip ? ' · ' : ''}${groupChip}</div>
         <div class="qt-pharm-badge">
           <span class="lbl">Nº de farmacia</span>
           <span class="num">${p.pharmacy_no ? esc(p.pharmacy_no) : '—'}</span>
         </div>
         <div class="qt-kv">
           <div class="qt-kv-row"><span class="k">Nº Farmacia</span><span class="v mono">${p.pharmacy_no ? esc(p.pharmacy_no) : '—'}</span></div>
           <div class="qt-kv-row"><span class="k">Nombre</span><span class="v">${esc(p.nombre)}</span></div>
           <div class="qt-kv-row"><span class="k">Apellidos</span><span class="v">${esc(p.apellidos)}</span></div>
           <div class="qt-kv-row"><span class="k">Código TIS</span><span class="v mono">${esc(p.tis)}</span></div>
           <div class="qt-kv-row"><span class="k">Estado</span><span class="v">${p.deceased ? `<span style="color:var(--muted)">✝ Fallecida${p.deceased_at ? ' · ' + fmtDate(p.deceased_at) : ''}</span>` : p.active ? '<span style="color:var(--ok)">● Activa</span>' : '<span style="color:var(--muted)">● Inactiva</span>'}</span></div>
         </div>
         <div id="group-area"></div>
         <div id="ficha-note">${p.note ? `<div class="az-ent-note" style="background:${esc(p.note.color || '#FEF08A')};margin:10px 0">${esc(p.note.text)}</div>` : ''}</div>
         <div class="qt-ficha-actions">
           ${S.canAsignacion ? '<span id="med-link-slot" class="qt-medlink-slot"></span>' : ''}
           <button class="qt-btn qt-btn-primary" id="act-edit">✏️ Editar información</button>
           <button class="qt-btn qt-btn-ghost" id="act-note">📝 ${p.note ? 'Editar nota' : 'Añadir nota'}</button>
           <button class="qt-btn ${inCart ? 'qt-btn-ghost' : 'qt-btn-teal'}" id="act-cart">${inCart ? '✓ En el carrito' : '🛒 Añadir al carrito'}</button>
           <button class="qt-btn qt-btn-ghost" id="act-group">👥 ${(p.groups && p.groups.length) ? 'Gestionar grupos' : 'Añadir a grupo'}</button>
           ${p.deceased ? '' : `<button class="qt-btn qt-btn-ghost" id="act-active">${p.active ? '⊘ Inactivar' : '✓ Activar'}</button>`}
           <button class="qt-btn qt-btn-ghost qt-btn-deceased" id="act-deceased">${p.deceased ? '↩ Quitar fallecimiento' : '✝ Dar por fallecida'}</button>
           <button class="qt-btn qt-btn-ghost" id="act-list">☰ Ver listado</button>
           <button class="qt-btn qt-btn-danger" id="act-del">🗑 Eliminar</button>
         </div>
       </div>
     </div>`;
  $('back').onclick = opts.justCreated ? viewHome : viewList;
  if (hasNav) {
    if (navIdx > 0) $('nav-prev').onclick = () => viewFicha(nav[navIdx - 1]);
    if (navIdx < nav.length - 1) $('nav-next').onclick = () => viewFicha(nav[navIdx + 1]);
  }
  $('act-edit').onclick = () => editPerson(p);
  if ($('act-note')) $('act-note').onclick = () => editPersonNote(id, () => viewFicha(id, opts));
  $('act-list').onclick = viewList;
  if (p.active) wireMando(p, () => { const box = $('ficha-qr'); if (box) box.innerHTML = qrSvg(qrValue(p), qrOpts(p, S.settings.qr_size)); });
  $('act-cart').onclick = async () => { await toggleCart(id); viewFicha(id, opts); };
  if ($('act-active')) $('act-active').onclick = async () => { await setActive(p, !p.active); viewFicha(id, opts); };
  $('act-deceased').onclick = async () => { if (await toggleDeceased(p)) viewFicha(id, opts); };
  $('act-del').onclick = async () => { if (await removePerson(p)) viewList(); };
  $('act-group').onclick = () => renderGroupManager(p);
  main().querySelectorAll('[data-gsel]').forEach(el => el.onclick = () => selectGroup(el.dataset.gsel, true));
  if (opts.openGroups) renderGroupManager(p);
  if (S.canAsignacion) loadMedLink(p);
}

// Fill the ficha's medication button from the Asignación app (async, non-blocking).
// Shows a count when the person already has a plan, or a "create plan" call to
// action when they don't. Both jump to the person's medication ficha.
async function loadMedLink(p) {
  const slot = $('med-link-slot'); if (!slot) return;
  let s;
  try { s = (await api('/people/' + p.id + '/med-summary')).summary; }
  catch { return; }   // no access / error → leave the slot empty
  if (!slot.isConnected) return;
  const href = '/asignacion?person=' + p.id;
  if (s.has_plan) {
    const n = s.active_count || s.plan_count;
    slot.outerHTML = `<a class="qt-btn qt-btn-teal" href="${href}" title="Ver y gestionar la medicación de esta persona">💊 Medicación · ${n} medicamento${n === 1 ? '' : 's'}</a>`;
  } else {
    slot.outerHTML = `<a class="qt-btn qt-btn-ghost qt-medlink-empty" href="${href}" title="Abrir su ficha de medicación para empezar el plan">💊 Crear plan de medicación</a>`;
  }
}

// Multi-group manager: current groups as removable chips + a field to add more.
function renderGroupManager(p) {
  const area = $('group-area');
  const groups = p.groups || [];
  const saveGroups = async (next) => {
    try {
      const { item } = await api('/people/' + p.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ groups: next }) });
      S.byId.set(item.id, item);
      const i = S.people.findIndex(x => x.id === item.id); if (i >= 0) S.people[i] = item;
      viewFicha(p.id, { openGroups: true });
    } catch (e) { toast(e.message, 'err'); }
  };
  area.innerHTML =
    `<div class="qt-group-mgr">
       <div class="qt-group-mgr-h">Grupos de esta persona</div>
       <div class="qt-group-chips">${groups.length
        ? groups.map((g, i) => `<span class="qt-group-echip${gcCls(g)}"${gcStyle(g)}>${esc(g)}<button data-rm="${i}" title="Quitar del grupo">×</button></span>`).join('')
        : '<span style="color:var(--muted);font-size:.85rem">Todavía no pertenece a ningún grupo.</span>'}</div>
       <div class="qt-group-inline">
         <input id="grp-input" placeholder="Escribe un grupo y pulsa Añadir" maxlength="80" autocomplete="off" />
         <button class="qt-btn qt-btn-primary qt-btn-sm" id="grp-add">Añadir</button>
       </div>
     </div>`;
  const inp = $('grp-input'); inp.focus();
  const add = () => {
    const g = inp.value.trim();
    if (!g) return;
    if (groups.some(x => x.toLowerCase() === g.toLowerCase())) { toast('Ya pertenece a ese grupo.', 'err'); return; }
    saveGroups([...groups, g]);
  };
  $('grp-add').onclick = add;
  inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); add(); } });
  area.querySelectorAll('[data-rm]').forEach(b => b.onclick = () => saveGroups(groups.filter((_, i) => i !== Number(b.dataset.rm))));
}

// Edit a person's core information (Nº farmacia, nombre, apellidos, TIS).
function editPerson(p) {
  openModal(
    `<div class="qt-modal-h"><h3>Editar información</h3><button class="qt-x" data-close>×</button></div>
     <div class="qt-form-err" id="e-err"></div>
     <div class="qt-field"><label>Nº de farmacia <span class="req">*</span></label>
       <input class="qt-input" id="e-farm" maxlength="5" inputmode="numeric" value="${esc(p.pharmacy_no || '')}" style="font-family:var(--mono);letter-spacing:.28em;text-align:center">
       <div class="qt-field-hint">No puede repetirse. Si no dispones de un número, añade 00000.</div></div>
     <div class="qt-field"><label>Nombre <span class="req">*</span></label><input class="qt-input" id="e-nombre" value="${esc(p.nombre)}"></div>
     <div class="qt-field"><label>Apellidos <span class="req">*</span></label><input class="qt-input" id="e-apellidos" value="${esc(p.apellidos)}"></div>
     <div class="qt-field"><label>Código TIS <span class="req">*</span></label>
       <div class="qt-tis-wrap"><input class="qt-input" id="e-tis" maxlength="8" inputmode="numeric" value="${esc(p.tis)}" style="font-family:var(--mono);letter-spacing:.28em;text-align:center"><button type="button" class="qt-scan-btn" id="e-scan" title="Escanear QR">⛶</button></div></div>
     <div class="qt-field"><label>Código del QR (opcional)</label>
       <input class="qt-input" id="e-qrcode" value="${esc(p.qr_code || '')}" autocomplete="off" placeholder="Escanea con el lector (emulador de teclado) o escribe el código…">
       <div class="qt-field-hint">Es lo que codifica el QR (más largo que el TIS). Enfoca aquí y escanea con el lector, o escríbelo. <strong>No se muestra</strong> en la app. Vacío = el QR usa el TIS.</div></div>
     <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" data-close>Cancelar</button><button class="qt-btn qt-btn-primary" id="e-save">Guardar cambios</button></div>`
  );
  const farm = $('e-farm'), tis = $('e-tis');
  farm.addEventListener('input', () => { farm.value = farm.value.replace(/\D/g, '').slice(0, 5); });
  tis.addEventListener('input', () => { tis.value = tis.value.replace(/\D/g, '').slice(0, 8); });
  $('e-scan').onclick = () => openScanner((raw, digits) => { tis.value = (digits && digits.length >= 8) ? digits.slice(0, 8) : (digits || ''); });
  const save = async () => {
    const pharmacy_no = farm.value.replace(/\D/g, ''), nombre = $('e-nombre').value.trim(), apellidos = $('e-apellidos').value.trim(), t = tis.value.replace(/\D/g, '');
    const err = $('e-err');
    if (!/^\d{5}$/.test(pharmacy_no)) { err.textContent = 'El Nº de farmacia debe tener exactamente 5 cifras.'; return; }
    if (!nombre || !apellidos) { err.textContent = 'Nombre y apellidos son obligatorios.'; return; }
    if (!/^\d{8}$/.test(t)) { err.textContent = 'El Código TIS debe tener exactamente 8 cifras.'; return; }
    try {
      const { item } = await api('/people/' + p.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pharmacy_no, nombre, apellidos, tis: t, qr_code: $('e-qrcode').value }) });
      S.byId.set(item.id, item);
      const i = S.people.findIndex(x => x.id === item.id); if (i >= 0) S.people[i] = item;
      closeModal(); toast('Información actualizada', 'ok'); viewFicha(p.id);
    } catch (e) { $('e-err').textContent = e.message; }
  };
  $('e-save').onclick = save;
}

// ── The QR "mando" ──────────────────────────────────────────────────────────────
// Colour, background and style are PER PERSON; size and robustness are shared.
function mandoHtml(st, p) {
  const swatches = ['#0f172a', '#1273b8', '#0a9d8e', '#7c3aed', '#c23a3a', '#b26a00', '#000000'];
  const gc = groupColorFor(p);
  const dark = (p && p.qr_dark) || gc || st.qr_dark;
  const light = (p && p.qr_light) || st.qr_light;
  const style = (p && p.qr_style) || st.qr_style;
  const hasOv = !!(p && (p.qr_dark || p.qr_light || p.qr_style));
  return `<div class="qt-mando">
    <div class="qt-mando-h">⚙ Ajustes del QR</div>
    <div class="qt-mando-row"><label>Tamaño</label><input type="range" id="m-size" min="160" max="620" step="10" value="${st.qr_size}"><span class="qt-mando-note">compartido</span></div>
    <div class="qt-mando-row"><label>Color</label>
      <div class="qt-swatches" id="m-swatches">${swatches.map(c => `<div class="qt-swatch${c === dark ? ' sel' : ''}" data-c="${c}" style="background:${c}"></div>`).join('')}</div>
      <input type="color" class="qt-color-input" id="m-dark" value="${dark}" title="Color personalizado">
      <button type="button" class="qt-mando-gc" id="m-groupcolors" title="Colores por grupo / residencia">🏠🎨</button>
    </div>
    ${gc && !(p && p.qr_dark) ? `<div class="qt-mando-note" style="margin:-4px 0 6px">🏠 Este QR toma el color de su <b>residencia/grupo</b>. Elige un color personal arriba para cambiarlo solo en esta persona.</div>` : ''}
    <div class="qt-mando-row"><label>Fondo</label>
      <input type="color" class="qt-color-input" id="m-light" value="${light}" title="Color de fondo">
      <label style="width:auto">Estilo</label>
      <div class="qt-seg" id="m-style">
        <button data-s="square" class="${style !== 'dots' ? 'sel' : ''}">Cuadrado</button>
        <button data-s="dots" class="${style === 'dots' ? 'sel' : ''}">Puntos</button>
      </div>
    </div>
    <div class="qt-mando-note" style="margin:-4px 0 8px">🎨 Color, fondo y estilo son <b>de esta persona</b>. ${hasOv ? '<a id="m-reset" style="color:var(--brand);cursor:pointer;font-weight:600">Usar los de por defecto</a>' : ''}</div>
    <div class="qt-mando-row"><label>Robustez</label>
      <div class="qt-seg" id="m-ecc">
        ${['L', 'M', 'Q', 'H'].map(e => `<button data-e="${e}" class="${st.qr_ecc === e ? 'sel' : ''}">${e}</button>`).join('')}
      </div>
      <span class="qt-mando-note">compartida</span>
    </div>
  </div>`;
}
function wireMando(p, rerender) {
  const applyGlobal = () => { rerender(); saveSettingsDebounced(); };
  const applyPerson = (patch) => { Object.assign(p, patch); rerender(); savePersonQrDebounced(p.id, patch); };
  const syncSwatch = () => { const dark = p.qr_dark || groupColorFor(p) || S.settings.qr_dark; $('m-swatches').querySelectorAll('.qt-swatch').forEach(sw => sw.classList.toggle('sel', sw.dataset.c === dark)); };
  if ($('m-groupcolors')) $('m-groupcolors').onclick = () => openGroupColors(p);
  $('m-size').addEventListener('input', e => { S.settings.qr_size = Number(e.target.value); applyGlobal(); });
  $('m-dark').addEventListener('input', e => { $('m-dark').value = e.target.value; applyPerson({ qr_dark: e.target.value }); syncSwatch(); });
  $('m-light').addEventListener('input', e => { applyPerson({ qr_light: e.target.value }); });
  $('m-swatches').querySelectorAll('.qt-swatch').forEach(sw => sw.addEventListener('click', () => {
    $('m-dark').value = sw.dataset.c; applyPerson({ qr_dark: sw.dataset.c }); syncSwatch();
  }));
  $('m-style').querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    $('m-style').querySelectorAll('button').forEach(x => x.classList.toggle('sel', x === b)); applyPerson({ qr_style: b.dataset.s });
  }));
  $('m-ecc').querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    S.settings.qr_ecc = b.dataset.e; $('m-ecc').querySelectorAll('button').forEach(x => x.classList.toggle('sel', x === b)); applyGlobal();
  }));
  const reset = $('m-reset');
  if (reset) reset.onclick = async () => {
    try {
      const { item } = await api('/people/' + p.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ qr_dark: null, qr_light: null, qr_style: null }) });
      S.byId.set(item.id, item); const i = S.people.findIndex(x => x.id === item.id); if (i >= 0) S.people[i] = item;
      viewFicha(p.id);
    } catch (e) { toast(e.message, 'err'); }
  };
}

// Assign a QR colour to each group/residence. The colour becomes the default QR
// colour of every person in that group (a personal colour still overrides it).
function openGroupColors(current) {
  const SW = ['#0f172a', '#1273b8', '#0a9d8e', '#7c3aed', '#c23a3a', '#b26a00', '#128a5b', '#d81b60', '#000000'];
  const groups = [...new Set(S.people.flatMap(p => p.groups || []))].sort((a, b) => a.localeCompare(b, 'es'));
  const map = { ...((S.settings && S.settings.group_colors) || {}) };
  const rowHtml = g => {
    const cur = map[g] || '';
    return `<div class="qt-gc-row" data-g="${esc(g)}">
      <span class="qt-gc-name">👥 ${esc(g)}</span>
      <span class="qt-gc-swatches">${SW.map(c => `<button type="button" class="qt-gc-sw${cur.toLowerCase() === c ? ' sel' : ''}" data-c="${c}" style="background:${c}" title="${c}"></button>`).join('')}</span>
      <input type="color" class="qt-gc-input" value="${cur || '#0f172a'}" title="Color personalizado">
      <button type="button" class="qt-gc-clear ${cur ? '' : 'is-none'}" title="Sin color (usar el de por defecto)">${cur ? '✕' : '—'}</button>
    </div>`;
  };
  openModal(`<div class="qt-modal-h"><h3>🎨 Colores por grupo / residencia</h3><button class="qt-x" data-close>×</button></div>
    <p class="qt-note">Asigna un color de QR a cada grupo para <b>distinguir residencias de un vistazo</b>. Se aplica a todas las personas del grupo; si alguien tiene un color propio, ese manda.</p>
    ${groups.length ? `<div class="qt-gc-list">${groups.map(rowHtml).join('')}</div>` : '<div class="qt-note warn">Todavía no hay grupos. Añade grupos a las personas (en su ficha) y vuelve aquí.</div>'}
    <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" data-close>Cancelar</button>${groups.length ? '<button class="qt-btn qt-btn-primary" id="gc-save">Guardar colores</button>' : ''}</div>`);
  const box = $('tool-modal-box');
  box.querySelectorAll('.qt-gc-row').forEach(row => {
    const g = row.dataset.g;
    const input = row.querySelector('.qt-gc-input');
    const clear = row.querySelector('.qt-gc-clear');
    const setSel = () => row.querySelectorAll('.qt-gc-sw').forEach(sw => sw.classList.toggle('sel', (map[g] || '').toLowerCase() === sw.dataset.c));
    row.querySelectorAll('.qt-gc-sw').forEach(sw => sw.onclick = () => { map[g] = sw.dataset.c; input.value = sw.dataset.c; clear.classList.remove('is-none'); clear.textContent = '✕'; setSel(); });
    input.oninput = () => { map[g] = input.value; clear.classList.remove('is-none'); clear.textContent = '✕'; setSel(); };
    clear.onclick = () => { delete map[g]; clear.classList.add('is-none'); clear.textContent = '—'; setSel(); };
  });
  if ($('gc-save')) $('gc-save').onclick = async () => {
    try {
      const { settings } = await api('/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...S.settings, group_colors: map }) });
      S.settings = settings; closeModal(); toast('Colores por grupo guardados.', 'ok');
      if (current && S.view === 'ficha') viewFicha(current.id); else if (S.view === 'list') renderRows();
    } catch (e) { toast(e.message, 'err'); }
  };
}

// ── (2) Visualizar — listado ─────────────────────────────────────────────────────
function viewList() {
  S.view = 'list';
  const st = S.settings;
  main().innerHTML =
    `<div class="qt-list-top">
       <button class="qt-back" id="back">← Inicio</button>
       <div class="qt-actions-bar">
         <button class="qt-action" id="a-excel-io"><span class="em">📄</span><span class="lbl">Plantilla / Importar<small>personas + código QR</small></span></button>
         <button class="qt-action" id="a-export-xlsx"><span class="em">📊</span><span class="lbl">Exportar Excel<small>elige campos y orden</small></span></button>
         <button class="qt-action" id="a-export-pdf"><span class="em">🖨️</span><span class="lbl">Exportar PDF<small>QR de tamaño variable</small></span></button>
         <button class="qt-action" id="a-recent"><span class="em">🕘</span><span class="lbl">Recientes<small>últimas 10 manejadas</small></span></button>
       </div>
     </div>
     <div class="qt-section-title">Listado de personas</div>
     <div class="qt-section-sub">Busca, ordena, selecciona, agrupa y usa el carrito. Haz clic en una persona para ver su QR. <button class="qt-link-discreet" id="qr-pending-btn" hidden></button></div>
     <div class="qt-groups" id="groups"></div>
     <div class="qt-search-wrap">
       <div class="qt-search"><span class="ico">🔎</span>
         <input id="q" placeholder="Buscar por Nº de farmacia, nombre, apellidos, TIS o grupo… (p. ej. «os rez»)" value="${esc(S.query)}" autocomplete="off">
       </div>
       <div class="qt-andor" id="andor" title="AND = todas las palabras · OR = cualquier palabra">
         <button data-v="AND" class="${S.andor === 'AND' ? 'sel' : ''}">AND</button>
         <button data-v="OR" class="${S.andor === 'OR' ? 'sel' : ''}">OR</button>
       </div>
     </div>
     <div class="qt-toolbar">
       <span class="qt-count" id="list-count"></span>
       <div class="qt-seg qt-mode" id="list-mode" title="Ver como lista o como tarjetas">
         <button data-m="table" class="${S.listMode !== 'cards' ? 'sel' : ''}">▤ Listado</button>
         <button data-m="cards" class="${S.listMode === 'cards' ? 'sel' : ''}">▦ Tarjetas</button>
       </div>
       ${S.listMode !== 'cards' ? `<button class="qt-toggle ${S.showListQr ? 'on' : ''}" id="tg-qr">▦ QR en el listado</button>` : ''}
       <span class="qt-inline-size" id="qr-size-wrap" ${(S.listMode === 'cards' || S.showListQr) ? '' : 'hidden'}>
         Tamaño QR <input type="range" id="list-qr-size" min="80" max="${S.listMode === 'cards' ? 200 : 360}" step="10" value="${S.listMode === 'cards' ? st.card_qr_size : st.list_qr_size}"><span id="list-qr-size-v">${S.listMode === 'cards' ? st.card_qr_size : st.list_qr_size}px</span>
       </span>
       ${S.listMode === 'cards' ? `<span class="qt-inline-sort">Ordenar
         <select class="qt-select" id="cards-sort">${SORT_FIELDS.map(f => `<option value="${f.key}" ${S.sort.key === f.key ? 'selected' : ''}>${f.label}</option>`).join('')}</select>
         <select class="qt-select" id="cards-dir"><option value="asc" ${S.sort.dir === 'asc' ? 'selected' : ''}>▲</option><option value="desc" ${S.sort.dir === 'desc' ? 'selected' : ''}>▼</option></select></span>` : ''}
       <button class="qt-toggle ${S.selectedOnly ? 'on' : ''}" id="tg-selected">✔ Solo seleccionadas</button>
       <button class="qt-toggle ${S.cartView ? 'on' : ''}" id="tg-cart">🛒 Solo carrito</button>
       <button class="qt-toggle ${S.hideDeceased ? 'on' : ''}" id="tg-deceased" title="Ocultar del listado las personas fallecidas">✝ Ocultar fallecidas (${S.people.filter(p => p.deceased).length})</button>
       <button class="qt-toggle ${S.notesOnly ? 'on' : ''}" id="tg-notes" title="Mostrar solo las personas con nota">📝 Con nota (${S.people.filter(p => p.note && p.note.text).length})</button>
       <button class="qt-toggle" id="clear-sel">✕ Quitar selección</button>
     </div>
     <div id="hidden-note"></div>
     <div id="list-body"></div>`;
  $('back').onclick = viewHome;
  $('a-excel-io').onclick = toolExcelIO;
  refreshQrPendingBtn();
  $('a-export-xlsx').onclick = toolExportExcel;
  $('a-export-pdf').onclick = toolExportPdf;
  $('a-recent').onclick = toolRecent;
  const q = $('q');
  q.addEventListener('input', () => { S.query = q.value; renderRows(); });
  $('andor').querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    S.andor = b.dataset.v; $('andor').querySelectorAll('button').forEach(x => x.classList.toggle('sel', x === b)); renderRows();
  }));
  $('list-mode').querySelectorAll('button').forEach(b => b.addEventListener('click', () => { S.listMode = b.dataset.m; viewList(); }));
  if ($('tg-qr')) $('tg-qr').onclick = () => { S.showListQr = !S.showListQr; viewList(); };
  $('tg-selected').onclick = () => { S.selectedOnly = !S.selectedOnly; viewList(); };
  $('tg-cart').onclick = () => { S.cartView = !S.cartView; viewList(); };
  $('tg-deceased').onclick = () => { S.hideDeceased = !S.hideDeceased; viewList(); };
  if ($('tg-notes')) $('tg-notes').onclick = () => { S.notesOnly = !S.notesOnly; viewList(); };
  $('clear-sel').onclick = () => { S.selected.clear(); renderRows(); };
  if ($('cards-sort')) {
    $('cards-sort').addEventListener('change', () => { S.sort.key = $('cards-sort').value; renderRows(); });
    $('cards-dir').addEventListener('change', () => { S.sort.dir = $('cards-dir').value; renderRows(); });
  }
  if ($('list-qr-size')) {
    const sizeEl = $('list-qr-size');
    sizeEl.addEventListener('input', () => {
      const v = Number(sizeEl.value);
      if (S.listMode === 'cards') S.settings.card_qr_size = v; else S.settings.list_qr_size = v;
      $('list-qr-size-v').textContent = v + 'px';
      saveSettingsDebounced(); renderRows();
    });
  }
  renderGroupsPanel();
  renderRows();
}

// Sort fields offered in the cards-view "Ordenar" dropdown (the table sorts by
// clicking its headers).
const SORT_FIELDS = [
  { key: 'pharmacy_no', label: 'Nº Farmacia' },
  { key: 'nombre', label: 'Nombre' },
  { key: 'apellidos', label: 'Apellidos' },
  { key: 'tis', label: 'Código TIS' },
  { key: 'group_name', label: 'Grupo' },
  { key: 'active', label: 'Estado' },
];

// Collapsible panel of "quantifiable" group cards that filter the list. Collapsed
// by default; expanding shows one card per group with its people count.
function renderGroupsPanel() {
  const wrap = $('groups');
  if (!wrap) return;
  const counts = new Map(); // display name → { name, count }
  for (const p of S.people) for (const g of (p.groups || [])) {
    const k = norm(g);
    if (!counts.has(k)) counts.set(k, { name: g, count: 0 });
    counts.get(k).count++;
  }
  const groups = [...counts.values()].sort((a, b) => a.name.localeCompare(b.name, 'es', { numeric: true }));
  wrap.innerHTML =
    `<div class="qt-groups-head">
       <button class="qt-groups-toggle" id="groups-toggle" aria-expanded="${S.groupsOpen}">
         <span class="chev ${S.groupsOpen ? 'open' : ''}">▸</span> Grupos <span class="qt-groups-count">${groups.length}</span>
       </button>
       ${S.groupFilter ? `<button class="qt-groups-clear" id="groups-clear" title="Quitar el filtro">Filtrando: ${esc(S.groupFilter)} ✕</button>` : ''}
     </div>
     <div class="qt-groups-cards" id="groups-cards" ${S.groupsOpen ? '' : 'hidden'}>
       ${groups.length
        ? groups.map(g => `<button class="qt-groupcard ${S.groupFilter && norm(S.groupFilter) === norm(g.name) ? 'active' : ''}${gcCls(g.name)}"${gcStyle(g.name)} data-gfilter="${esc(g.name)}"><span class="gc-count">${g.count}</span><span class="gc-name">${esc(g.name)}</span></button>`).join('')
        : '<span class="qt-groups-empty">Todavía no hay grupos. Añádelos desde la ficha de una persona.</span>'}
     </div>`;
  $('groups-toggle').onclick = () => { S.groupsOpen = !S.groupsOpen; renderGroupsPanel(); };
  const clr = $('groups-clear'); if (clr) clr.onclick = () => { S.groupFilter = null; renderGroupsPanel(); renderRows(); };
  wrap.querySelectorAll('[data-gfilter]').forEach(c => c.onclick = () => {
    const g = c.dataset.gfilter;
    S.groupFilter = (S.groupFilter && norm(S.groupFilter) === norm(g)) ? null : g; // toggle
    renderGroupsPanel(); renderRows();
  });
}

// Table header row (sortable columns).
function headTr() {
  const cols = [{ key: 'sel', label: '', sort: false }];
  if (S.canAsignacion) cols.push({ key: 'plan', label: '💊', sort: false });
  cols.push(
    { key: 'pharmacy_no', label: 'Nº Far.' },
    { key: 'nombre', label: 'Nombre' },
    { key: 'apellidos', label: 'Apellidos' },
    { key: 'tis', label: 'Código TIS' },
    { key: 'group_name', label: 'Grupo' },
    { key: 'active', label: 'Estado' },
  );
  if (S.showListQr) cols.push({ key: 'qr', label: 'QR', sort: false });
  cols.push({ key: 'act', label: '', sort: false });
  return '<tr>' + cols.map(c => {
    if (c.key === 'sel') return `<th class="no-sort qt-th-sel"><input type="checkbox" id="sel-all" class="qt-check" title="Seleccionar / deseleccionar todo el listado"></th>`;
    if (c.sort === false) return `<th class="no-sort">${c.label}</th>`;
    const sorted = S.sort.key === c.key;
    const arrow = sorted ? (S.sort.dir === 'asc' ? '▲' : '▼') : '↕';
    return `<th data-key="${c.key}" class="${sorted ? 'sorted' : ''}">${c.label} <span class="arrow">${arrow}</span></th>`;
  }).join('') + '</tr>';
}
// A pill that shows/links a person's medication plan (green = has, grey = none).
function planPillHtml(p) {
  const has = !!p.has_plan;
  return `<button class="qt-plan-pill ${has ? 'has' : 'none'}" data-plan="${p.id}" title="${has ? 'Ir al plan de medicación' : 'Sin plan — pulsa para crearlo'}" aria-label="Plan de medicación">💊</button>`;
}
function wireHeadSort(container) {
  container.querySelectorAll('th[data-key]').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.key;
    if (S.sort.key === k) S.sort.dir = S.sort.dir === 'asc' ? 'desc' : 'asc';
    else { S.sort.key = k; S.sort.dir = 'asc'; }
    renderRows();
  }));
}

function filteredPeople() {
  let rows = S.people.filter(p => !S.hidden.has(p.id));
  if (S.cartView) rows = rows.filter(p => S.cart.has(p.id));
  if (S.selectedOnly) rows = rows.filter(p => S.selected.has(p.id));
  if (S.hideDeceased) rows = rows.filter(p => !p.deceased);
  if (S.notesOnly) rows = rows.filter(p => p.note && p.note.text);
  if (S.groupFilter) rows = rows.filter(p => (p.groups || []).some(g => norm(g) === norm(S.groupFilter)));
  const tokens = norm(S.query).split(/\s+/).filter(Boolean);
  if (tokens.length) {
    rows = rows.filter(p => {
      const hay = norm([p.pharmacy_no, p.nombre, p.apellidos, p.tis, p.group_name].join(' '));
      return S.andor === 'OR' ? tokens.some(t => hay.includes(t)) : tokens.every(t => hay.includes(t));
    });
  }
  const { key, dir } = S.sort, mul = dir === 'asc' ? 1 : -1;
  rows.sort((a, b) => {
    let av = a[key], bv = b[key];
    if (key === 'active') return (av - bv) * mul;
    av = norm(av == null ? '' : av); bv = norm(bv == null ? '' : bv);
    return av.localeCompare(bv, 'es', { numeric: true }) * mul;
  });
  return rows;
}

// One table row for a person.
function personRowHtml(p) {
  const st = S.settings, sel = S.selected.has(p.id), inCart = S.cart.has(p.id);
  const group = (p.groups && p.groups.length)
    ? `<span class="qt-grouptags">${p.groups.map(g => `<span class="qt-grouptag${gcCls(g)}"${gcStyle(g)} data-group="${esc(g)}" title="Seleccionar todo el grupo">${esc(g)}</span>`).join('')}</span>`
    : '<span style="color:#b3bcc7">—</span>';
  const state = p.deceased
    ? '<span class="qt-state-dot deceased"><span class="dot"></span>✝ Fallecida</span>'
    : p.active
      ? '<span class="qt-state-dot"><span class="dot"></span>Activa</span>'
      : '<span class="qt-state-dot off"><span class="dot"></span>Inactiva</span>';
  const qrCell = S.showListQr
    ? `<td>${p.active ? `<span class="qt-list-qr" data-open="${p.id}">${qrSvg(qrValue(p), qrOpts(p, st.list_qr_size))}</span>` : '<span style="color:#b3bcc7">—</span>'}</td>`
    : '';
  return `<tr class="${p.active ? '' : 'is-inactive'} ${p.deceased ? 'is-deceased' : ''} ${sel ? 'is-selected' : ''}" data-id="${p.id}">
    <td><input type="checkbox" class="qt-check" data-sel="${p.id}" ${sel ? 'checked' : ''}></td>
    ${S.canAsignacion ? `<td class="qt-td-plan">${planPillHtml(p)}</td>` : ''}
    <td><span class="qt-cell-pharm" data-open="${p.id}">${p.pharmacy_no ? esc(p.pharmacy_no) : '<span style=\"color:#c3c9d2\">—</span>'}</span></td>
    <td><span class="qt-cell-name" data-open="${p.id}">${esc(p.nombre)}</span></td>
    <td>${esc(p.apellidos)}</td>
    <td class="qt-cell-tis">${esc(p.tis)}</td>
    <td>${group}</td>
    <td>${state}</td>
    ${qrCell}
    <td><div class="qt-cell-actions">${personActionsHtml(p, inCart)}</div></td>
  </tr>`;
}

// One card for a person (cards view — QR-forward, like the cart).
function personCardHtml(p) {
  const st = S.settings, sel = S.selected.has(p.id), inCart = S.cart.has(p.id);
  const groups = (p.groups && p.groups.length) ? p.groups.map(g => `<span class="qt-grouptag${gcCls(g)}"${gcStyle(g)} data-group="${esc(g)}" title="Seleccionar todo el grupo">${esc(g)}</span>`).join('') : '';
  // The QR box is a fixed square (uniform cards); the QR just scales inside it.
  const qr = p.active
    ? `<span class="qt-pcard-qr" data-open="${p.id}">${qrSvg(qrValue(p), qrOpts(p, st.card_qr_size))}</span>`
    : `<span class="qt-pcard-qr inactive" data-open="${p.id}" style="width:${st.card_qr_size}px;height:${st.card_qr_size}px">${p.deceased ? '✝ Fallecida' : 'Inactiva'}</span>`;
  return `<div class="qt-pcard ${p.active ? '' : 'is-inactive'} ${p.deceased ? 'is-deceased' : ''} ${sel ? 'is-selected' : ''}" data-id="${p.id}">
    <div class="qt-pcard-head">
      <input type="checkbox" class="qt-check" data-sel="${p.id}">
      <span class="qt-cell-pharm" data-open="${p.id}">${p.pharmacy_no ? esc(p.pharmacy_no) : '—'}</span>
      ${S.canAsignacion ? planPillHtml(p) : ''}
      <span class="qt-state-dot ${p.deceased ? 'deceased' : p.active ? '' : 'off'}" style="margin-left:auto" title="${p.deceased ? 'Fallecida' : p.active ? 'Activa' : 'Inactiva'}"><span class="dot"></span></span>
    </div>
    ${qr}
    <div class="qt-pcard-name" data-open="${p.id}">${esc(p.nombre)} ${esc(p.apellidos)}</div>
    <div class="qt-pcard-tis">${esc(p.tis)}</div>
    <div class="qt-pcard-groups">${groups}</div>
    ${p.note ? `<div class="az-ent-note qt-pcard-note" style="background:${esc(p.note.color || '#FEF08A')}">${esc(p.note.text)}</div>` : ''}
    <div class="qt-pcard-actions">${personActionsHtml(p, inCart)}</div>
  </div>`;
}

function personActionsHtml(p, inCart) {
  return `<button class="qt-iconbtn az-note-ic ${p.note ? 'has' : ''}" data-note="${p.id}" title="${p.note ? 'Editar nota' : 'Añadir nota'}">📝</button>
    <button class="qt-iconbtn" data-cart="${p.id}" title="${inCart ? 'Quitar del carrito' : 'Añadir al carrito'}">${inCart ? '✓🛒' : '🛒'}</button>
    ${p.deceased ? '' : `<button class="qt-iconbtn" data-active="${p.id}" title="${p.active ? 'Inactivar' : 'Activar'}">${p.active ? '⊘' : '✓'}</button>`}
    <button class="qt-iconbtn" data-deceased="${p.id}" data-to="${p.deceased ? '0' : '1'}" title="${p.deceased ? 'Quitar fallecimiento' : 'Dar por fallecida'}">${p.deceased ? '↩' : '✝'}</button>
    <button class="qt-iconbtn" data-hide="${p.id}" title="Ocultar del listado (temporal)">👁</button>
    <button class="qt-iconbtn danger" data-del="${p.id}" title="Eliminar">🗑</button>`;
}
// ── Per-person notes (pretty editor + "Con nota" filter) ──────────────────────────
const AZ_NOTE_COLORS = ['#FEF08A', '#FBCFE8', '#BFDBFE', '#BBF7D0', '#FED7AA', '#E9D5FF', '#FECACA'];
function openNoteEditor(opts) {
  const cur = opts.current || {}, cols = AZ_NOTE_COLORS;
  let color = cur.color || cols[0];
  openModal(`<div class="qt-modal-h"><h3>📝 Nota${opts.subtitle ? ' · ' + esc(opts.subtitle) : ''}</h3><button class="qt-x" data-close>×</button></div>
    <p style="color:var(--muted);font-size:.88rem;margin:0 0 8px">Una nota corta para recordar «qué le pasa». Luego puedes filtrar por «📝 Con nota».</p>
    <div class="az-noteedit" id="nte-card" style="background:${esc(color)}"><textarea id="nte-text" class="az-noteedit-ta" maxlength="2000" placeholder="Escribe la nota…">${esc(cur.text || '')}</textarea></div>
    <div class="az-noteedit-cols">${cols.map(c => `<button type="button" class="az-noteedit-sw ${c === color ? 'sel' : ''}" data-c="${esc(c)}" style="background:${esc(c)}" aria-label="color"></button>`).join('')}</div>
    <div class="qt-modal-actions">${cur.text ? '<button class="qt-btn qt-btn-danger" id="nte-del">Borrar nota</button>' : ''}<button class="qt-btn qt-btn-ghost" data-close>Cancelar</button><button class="qt-btn qt-btn-primary" id="nte-save">Guardar</button></div>`);
  const box = $('tool-modal-box');
  box.querySelectorAll('.az-noteedit-sw').forEach(sw => sw.onclick = () => { color = sw.dataset.c; $('nte-card').style.background = color; box.querySelectorAll('.az-noteedit-sw').forEach(x => x.classList.toggle('sel', x === sw)); });
  const save = async (text) => {
    try { const r = await api(opts.endpoint, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, color }) }); closeModal(); opts.onSaved(r.note || null); }
    catch (e) { toast(e.message, 'err'); }
  };
  $('nte-save').onclick = () => save($('nte-text').value);
  if ($('nte-del')) $('nte-del').onclick = () => save('');
  setTimeout(() => { const t = $('nte-text'); if (t) t.focus(); }, 30);
}
function editPersonNote(id, after) {
  const p = S.byId.get(id); if (!p) return;
  openNoteEditor({
    subtitle: `${p.nombre} ${p.apellidos}`, endpoint: `/people/${id}/note`, current: p.note,
    onSaved: (note) => {
      p.note = note; S.byId.set(id, p);
      const i = S.people.findIndex(x => x.id === id); if (i >= 0) S.people[i] = p;
      toast(note ? 'Nota guardada.' : 'Nota borrada.', 'ok');
      if (after) after();
    },
  });
}

// Shared wiring for row/card items (both use the same data-* hooks).
function wireListItems(container) {
  container.querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => gotoFicha(Number(el.dataset.open), filteredPeople().map(x => x.id))));
  container.querySelectorAll('[data-sel]').forEach(cb => cb.addEventListener('change', () => {
    const id = Number(cb.dataset.sel); if (cb.checked) S.selected.add(id); else S.selected.delete(id); renderRows();
  }));
  container.querySelectorAll('[data-group]').forEach(g => g.addEventListener('click', () => selectGroup(g.dataset.group)));
  container.querySelectorAll('[data-plan]').forEach(b => b.addEventListener('click', () => onPlanPill(Number(b.dataset.plan))));
  container.querySelectorAll('[data-note]').forEach(b => b.addEventListener('click', () => editPersonNote(Number(b.dataset.note), renderRows)));
  container.querySelectorAll('[data-cart]').forEach(b => b.addEventListener('click', async () => { await toggleCart(Number(b.dataset.cart)); renderRows(); }));
  container.querySelectorAll('[data-active]').forEach(b => b.addEventListener('click', async () => { const p = S.byId.get(Number(b.dataset.active)); await setActive(p, !p.active); renderRows(); }));
  container.querySelectorAll('[data-deceased]').forEach(b => b.addEventListener('click', async () => { const p = S.byId.get(Number(b.dataset.deceased)); if (await toggleDeceased(p)) renderRows(); }));
  container.querySelectorAll('[data-hide]').forEach(b => b.addEventListener('click', () => { S.hidden.add(Number(b.dataset.hide)); renderRows(); }));
  container.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', async () => { const p = S.byId.get(Number(b.dataset.del)); if (await removePerson(p)) renderRows(); }));
}

// Render the list body as a table or as cards, per S.listMode.
function renderRows() {
  const rows = filteredPeople();
  $('list-count').textContent =
    `${rows.length} de ${S.people.length}` +
    (S.selected.size ? ` · ${S.selected.size} seleccionada(s)` : '') +
    (S.hidden.size ? ` · ${S.hidden.size} oculta(s)` : '');
  $('hidden-note').innerHTML = S.hidden.size
    ? `<div class="qt-hidden-note">👁 Hay <strong>${S.hidden.size}</strong> persona(s) oculta(s) temporalmente. <a id="unhide">Mostrar todas</a></div>` : '';
  if (S.hidden.size) $('unhide').onclick = () => { S.hidden.clear(); renderRows(); };

  const body = $('list-body');
  if (!rows.length) { body.innerHTML = '<div class="qt-empty">No hay personas que coincidan.</div>'; return; }

  if (S.listMode === 'cards') {
    body.innerHTML = `<div class="qt-pcards" style="--qrw:${S.settings.card_qr_size}px">${rows.map(personCardHtml).join('')}</div>`;
    // checkboxes need their checked state set (kept out of the HTML to avoid stale attrs)
    body.querySelectorAll('[data-sel]').forEach(cb => { cb.checked = S.selected.has(Number(cb.dataset.sel)); });
  } else {
    body.innerHTML = `<div class="qt-table-wrap"><table class="qt-table"><thead>${headTr()}</thead><tbody>${rows.map(personRowHtml).join('')}</tbody></table></div>`;
    wireHeadSort(body);
    const selAll = body.querySelector('#sel-all');
    if (selAll) {
      const allSel = rows.length > 0 && rows.every(p => S.selected.has(p.id));
      selAll.checked = allSel;
      selAll.indeterminate = !allSel && rows.some(p => S.selected.has(p.id));
      selAll.onclick = () => { const on = selAll.checked; rows.forEach(p => on ? S.selected.add(p.id) : S.selected.delete(p.id)); renderRows(); };
    }
  }
  wireListItems(body);
}
// Pill click: go to the plan (if it exists) or offer to create an empty one.
function onPlanPill(id) {
  const p = S.byId.get(id); if (!p) return;
  if (p.has_plan) { location.href = '/asignacion?person=' + id; return; }
  openModal(`<div class="qt-modal-h"><h3>💊 Plan de medicación</h3><button class="qt-x" data-close>×</button></div>
    <p style="font-size:.95rem;line-height:1.5"><b>${esc(p.nombre)} ${esc(p.apellidos)}</b> todavía no tiene plan de medicación. ¿Quieres <b>crear su plan</b> (aunque esté vacío) y abrirlo? Así queda listo para añadirle medicación o para una importación en lote.</p>
    <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" data-close>Cancelar</button><button class="qt-btn qt-btn-primary" id="cp-go">Sí, crear y abrir</button></div>`);
  $('cp-go').onclick = async () => {
    try {
      await api('/people/' + id + '/create-plan', { method: 'POST' });
      p.has_plan = true; S.byId.set(id, p); const i = S.people.findIndex(x => x.id === id); if (i >= 0) S.people[i] = p;
      location.href = '/asignacion?person=' + id;
    } catch (e) { toast(e.message, 'err'); }
  };
}

// Select every person in a group (adds to the current selection).
function selectGroup(group, goList) {
  if (!group) return;
  const g = norm(group);
  const ids = S.people.filter(p => (p.groups || []).some(x => norm(x) === g)).map(p => p.id);
  ids.forEach(id => S.selected.add(id));
  toast(`${ids.length} persona(s) del grupo «${group}» seleccionadas`, 'ok');
  if (goList && S.view !== 'list') viewList(); else if (S.view === 'list') renderRows();
}

// ── Shared actions ────────────────────────────────────────────────────────────
async function toggleCart(id) {
  try {
    if (S.cart.has(id)) { const { ids } = await api('/cart/' + id, { method: 'DELETE' }); S.cart = new Set(ids); }
    else { const { ids } = await api('/cart/' + id, { method: 'POST' }); S.cart = new Set(ids); }
    updateCartCount();
    if ($('cart-panel').classList.contains('open')) renderCart();
  } catch (e) { toast(e.message, 'err'); }
}
async function setActive(p, active) {
  try {
    const { item } = await api('/people/' + p.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ active: active ? 1 : 0 }) });
    S.byId.set(item.id, item);
    const i = S.people.findIndex(x => x.id === item.id); if (i >= 0) S.people[i] = item;
    toast(active ? 'Persona activada' : 'Persona inactivada (QR inaccesible)', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}
// Mark/unmark a person as deceased. Marking asks for confirmation (it also makes
// the QR inaccessible); the record is kept and it's reversible.
async function toggleDeceased(p) {
  const marking = !p.deceased;
  if (marking) {
    const ok = await confirmBox('Dar por fallecida',
      `¿Marcar a «${p.nombre} ${p.apellidos}» (TIS ${p.tis}) como fallecida? Se conserva la ficha, pero el QR deja de estar disponible. Podrás revertirlo.`, 'Dar por fallecida');
    if (!ok) return false;
  }
  try {
    const { item } = await api('/people/' + p.id + '/deceased', jbody({ deceased: marking }));
    S.byId.set(item.id, item);
    const i = S.people.findIndex(x => x.id === item.id); if (i >= 0) S.people[i] = item;
    toast(marking ? 'Persona marcada como fallecida' : 'Fallecimiento retirado (persona activada)', 'ok');
    return true;
  } catch (e) { toast(e.message, 'err'); return false; }
}
async function removePerson(p) {
  const ok = await confirmBox('Eliminar persona', `¿Eliminar a «${p.nombre} ${p.apellidos}» (TIS ${p.tis})? Esta acción no se puede deshacer.`, 'Eliminar');
  if (!ok) return false;
  try {
    await api('/people/' + p.id, { method: 'DELETE' });
    S.cart.delete(p.id); S.selected.delete(p.id); updateCartCount();
    await reloadPeople();
    toast('Persona eliminada', 'ok');
    return true;
  } catch (e) { toast(e.message, 'err'); return false; }
}

// ── Cart slide-over ──────────────────────────────────────────────────────────
function openCart() { $('cart-panel').classList.add('open'); $('scrim').hidden = false; renderCart(); }
function closeCart() { $('cart-panel').classList.remove('open'); $('scrim').hidden = true; }
function renderCart() {
  const panel = $('cart-panel');
  const items = S.people.filter(p => S.cart.has(p.id));
  const st = S.settings;
  const size = Math.max(150, Math.min(220, st.list_qr_size));
  const selInCart = items.filter(p => S.selected.has(p.id)).length;
  panel.innerHTML =
    `<div class="qt-cart-head">
       <h2>🛒 Carrito</h2>
       <span style="color:var(--muted);font-size:.9rem">${items.length} persona(s)</span>
       <button class="qt-x" id="cart-x">×</button>
     </div>
     <div class="qt-cart-tools">
       <button class="qt-btn qt-btn-ghost qt-btn-sm" id="cart-hide">Ocultar</button>
       <button class="qt-btn qt-btn-ghost qt-btn-sm" id="cart-selall">Seleccionar todos (${selInCart}/${items.length})</button>
       <button class="qt-btn qt-btn-ghost qt-btn-sm" id="cart-keepsel" ${selInCart ? '' : 'disabled'}>Sacar a los no seleccionados</button>
       <button class="qt-btn qt-btn-ghost qt-btn-sm" id="cart-list">Ver en listado</button>
       <button class="qt-btn qt-btn-danger qt-btn-sm" id="cart-empty" ${items.length ? '' : 'disabled'}>Vaciar</button>
     </div>
     <div class="qt-cart-body" id="cart-body"></div>`;
  $('cart-x').onclick = closeCart;
  $('cart-hide').onclick = closeCart;
  $('cart-list').onclick = () => { S.cartView = true; closeCart(); viewList(); };
  $('cart-selall').onclick = () => {
    const allSel = items.every(p => S.selected.has(p.id));
    items.forEach(p => allSel ? S.selected.delete(p.id) : S.selected.add(p.id));
    renderCart(); if (S.view === 'list') renderRows();
  };
  $('cart-keepsel').onclick = async () => {
    const drop = items.filter(p => !S.selected.has(p.id));
    if (!drop.length) return;
    if (!(await confirmBox('Sacar del carrito', `Se sacarán ${drop.length} persona(s) no seleccionada(s) del carrito.`, 'Sacar'))) return;
    for (const p of drop) { try { const { ids } = await api('/cart/' + p.id, { method: 'DELETE' }); S.cart = new Set(ids); } catch (e) { /* keep going */ } }
    updateCartCount(); renderCart(); if (S.view === 'list') renderRows();
  };
  $('cart-empty').onclick = async () => {
    if (!(await confirmBox('Vaciar carrito', '¿Seguro que quieres vaciar todo el carrito?', 'Vaciar'))) return;
    try { const { ids } = await api('/cart', { method: 'DELETE' }); S.cart = new Set(ids); updateCartCount(); renderCart(); if (S.view === 'list') renderRows(); } catch (e) { toast(e.message, 'err'); }
  };

  const body = $('cart-body');
  if (!items.length) { body.innerHTML = '<div class="qt-empty">El carrito está vacío.<br>Añade personas desde el listado o su ficha.</div>'; return; }
  body.innerHTML = items.map(p => {
    const sel = S.selected.has(p.id);
    const qr = p.active ? `<span class="qr" data-open="${p.id}">${qrSvg(qrValue(p), qrOpts(p, size))}</span>` : `<span class="qr" style="width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center;color:#9aa4b0;font-size:.8rem">Inactiva</span>`;
    const group = (p.groups && p.groups.length) ? p.groups.map(g => `<span class="qt-grouptag${gcCls(g)}"${gcStyle(g)} data-group="${esc(g)}">${esc(g)}</span>`).join(' ') : '';
    return `<div class="qt-cart-card ${sel ? 'is-selected' : ''}">
       ${qr}
       <div class="info">
         <div class="nm" data-open="${p.id}">${esc(p.nombre)} ${esc(p.apellidos)} ${group}</div>
         <div class="ts">${p.pharmacy_no ? 'Farm. ' + esc(p.pharmacy_no) + ' · ' : ''}${esc(p.tis)}</div>
         <label style="display:inline-flex;align-items:center;gap:6px;margin-top:8px;font-size:.82rem;cursor:pointer"><input type="checkbox" class="qt-check" data-sel="${p.id}" ${sel ? 'checked' : ''}> Seleccionar</label>
         <button class="qt-iconbtn danger" data-remove="${p.id}" title="Sacar del carrito" style="margin-left:8px">✕</button>
       </div>
     </div>`;
  }).join('');
  body.querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => { closeCart(); gotoFicha(Number(el.dataset.open), items.map(x => x.id)); }));
  body.querySelectorAll('[data-sel]').forEach(cb => cb.addEventListener('change', () => { const id = Number(cb.dataset.sel); if (cb.checked) S.selected.add(id); else S.selected.delete(id); renderCart(); if (S.view === 'list') renderRows(); }));
  body.querySelectorAll('[data-group]').forEach(g => g.addEventListener('click', () => { closeCart(); selectGroup(g.dataset.group, true); }));
  body.querySelectorAll('[data-remove]').forEach(b => b.addEventListener('click', async () => { await toggleCart(Number(b.dataset.remove)); renderCart(); if (S.view === 'list') renderRows(); }));
}

// ── Scanner (camera → jsQR) ──────────────────────────────────────────────────
function openScanner(onResult) {
  const modal = $('scan-modal'), video = $('scan-video'), note = $('scan-note'), canvas = $('scan-canvas');
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  let stream = null, raf = null, stopped = false;
  function stop() { stopped = true; if (raf) cancelAnimationFrame(raf); if (stream) stream.getTracks().forEach(t => t.stop()); modal.hidden = true; }
  $('scan-close').onclick = stop;
  modal.hidden = false; note.textContent = 'Solicitando cámara…'; note.className = 'qt-scan-note';
  navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    .then(async s => {
      stream = s; video.srcObject = s; await video.play().catch(() => {});
      note.textContent = 'Apunta la cámara al código QR del TIS…';
      const tick = () => {
        if (stopped) return;
        if (video.readyState === video.HAVE_ENOUGH_DATA && video.videoWidth) {
          canvas.width = video.videoWidth; canvas.height = video.videoHeight;
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const code = jsQR(img.data, img.width, img.height, { inversionAttempts: 'attemptBoth' });
          if (code && code.data) { const digits = code.data.replace(/\D/g, ''); stop(); onResult(code.data, digits); return; }
        }
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    })
    .catch(e => { note.textContent = 'No se pudo acceder a la cámara: ' + e.message + '. Escríbelo a mano.'; note.className = 'qt-scan-note err'; });
}

// ── Manual / Ayuda ───────────────────────────────────────────────────────────────
function viewHelp() {
  S.view = 'help';
  const SECS = [
    { id: 'inicio', icon: '🚀', title: 'Qué es y cómo empezar', html: `
      <p>Esta app guarda <strong>personas</strong> y su <strong>Código TIS</strong> (el número para la gestión de la medicación) y lo convierte en un <strong>código QR</strong> que se puede escanear. Cada persona tiene también un <strong>Nº de farmacia</strong> de 5 cifras.</p>
      <ol class="qt-steps">
        <li><b>Introducir persona</b>: rellena Nº de farmacia, nombre, apellidos y TIS. Al guardar aparece su QR grande.</li>
        <li><b>Consultar personas</b>: entra al listado, busca/filtra/ordena y pulsa a cualquiera para ver y usar su QR en grande.</li>
      </ol>
      <div class="qt-note tip">Los dos accesos están en la portada. Este manual está siempre disponible en el botón <span class="qt-chip-inline">❔ Ayuda</span> de arriba.</div>` },
    { id: 'campos', icon: '🔢', title: 'Los campos y los ceros', html: `
      <ul>
        <li><strong>Nº de farmacia</strong>: 5 cifras que asigna la farmacia. Aparece <strong>primero</strong> en el listado y <strong>no puede repetirse</strong>. Si no dispones de un número, pon <code>00000</code> (este sí puede repetirse).</li>
        <li><strong>Nombre</strong> y <strong>Apellidos</strong>.</li>
        <li><strong>Código TIS</strong>: 8 cifras, <strong>único</strong> (no se puede repetir). Es lo que codifica el QR.</li>
      </ul>
      <div class="qt-note">Si al <b>importar</b> se cuela un Nº de farmacia (que no sea 00000) o un Código TIS repetido, esa fila <b>se avisa y se omite</b>; el resto se importan.</div>
      <div class="qt-note warn"><b>Los ceros a la izquierda cuentan.</b> <code>00123456</code> no es lo mismo que <code>123456</code>. La app los conserva siempre, y al importar desde Excel los recupera aunque Excel los haya borrado.</div>
      <p>Todos los campos son obligatorios al crear una persona a mano.</p>` },
    { id: 'introducir', icon: '➕', title: 'Introducir una persona', html: `
      <p>Portada → <span class="qt-chip-inline">Introducir persona</span>. Escribe los cuatro campos. El Código TIS puedes teclearlo o pulsar el botón <span class="qt-chip-inline">⛶</span> para <strong>escanear un QR</strong> con la cámara: apunta al código y se rellena solo.</p>
      <p>Al guardar verás el <strong>QR grande</strong> de la persona (su ficha), con un botón para ir al listado.</p>
      <div class="qt-note">Escanear requiere permiso de cámara y conexión segura (https). Si no está disponible, escribe el TIS a mano.</div>` },
    { id: 'qr', icon: '🎛️', title: 'El QR y sus ajustes (el «mando»)', html: `
      <p>En la ficha de una persona, bajo el QR, tienes el <strong>mando</strong> para ajustar:</p>
      <ul>
        <li><strong>Tamaño</strong>: hazlo más grande o pequeño.</li>
        <li><strong>Color</strong> del código y <strong>fondo</strong>.</li>
        <li><strong>Estilo</strong>: cuadrado o de puntos.</li>
        <li><strong>Robustez</strong>: mayor = más denso pero más tolerante a manchas/arrugas.</li>
      </ul>
      <div class="qt-note tip"><b>Color, fondo y estilo son de cada persona</b> (una puede tener el QR rojo y otra verde, etc.). El <b>tamaño</b> y la <b>robustez</b> son compartidos para todos. Con «Usar los de por defecto» una persona vuelve a los colores/estilo generales. Todos los estilos se mantienen escaneables.</div>` },
    { id: 'buscar', icon: '🔎', title: 'Buscar (rápido y sin tildes)', html: `
      <p>En el listado, la barra de búsqueda filtra al instante por <strong>Nº de farmacia, nombre, apellidos, TIS o grupo</strong>. No distingue tildes ni la ñ.</p>
      <ul>
        <li><span class="qt-chip-inline">AND</span> (por defecto): deben aparecer <strong>todas</strong> las palabras. Con <code>os rez</code> encuentras a «José Pérez».</li>
        <li><span class="qt-chip-inline">OR</span>: vale con que aparezca <strong>cualquiera</strong> de las palabras.</li>
      </ul>` },
    { id: 'listado', icon: '📋', title: 'Listado o tarjetas, ordenar y ver el QR', html: `
      <p>Con el conmutador <span class="qt-chip-inline">▤ Listado | ▦ Tarjetas</span> eliges cómo verlo:</p>
      <ul>
        <li><strong>Listado</strong> (tabla): pulsa cualquier <strong>cabecera</strong> para ordenar (otra vez para invertir). El botón <span class="qt-chip-inline">▦ QR en el listado</span> añade el QR de cada persona en la tabla.</li>
        <li><strong>Tarjetas</strong>: cada persona como una tarjeta con su <strong>QR bien visible</strong> (como en el carrito), con un desplegable para <strong>ordenar</strong>.</li>
      </ul>
      <p>En ambos modos, el deslizador <strong>Tamaño QR</strong> ajusta lo grande que se ve el código para poder escanearlo.</p>
      <div class="qt-note tip">Al abrir la ficha de una persona desde el listado, arriba a la derecha aparecen <b>← Anterior</b> y <b>Siguiente →</b> que recorren <b>exactamente el listado del que vienes</b> (con su filtro/orden actual), no todas las personas de la base de datos.</div>` },
    { id: 'gestionar', icon: '🗂️', title: 'Editar, seleccionar, ocultar, inactivar, fallecida, eliminar', html: `
      <ul>
        <li><strong>Editar</strong>: en la ficha de una persona, <span class="qt-chip-inline">✏️ Editar información</span> permite corregir el Nº de farmacia, nombre, apellidos y TIS.</li>
        <li><strong>Seleccionar</strong>: casilla de la izquierda. Con <span class="qt-chip-inline">✔ Solo seleccionadas</span> filtras por ellas; <span class="qt-chip-inline">✕ Quitar selección</span> las limpia.</li>
        <li><strong>Ocultar</strong> (icono 👁): quita a alguien de la vista <strong>temporalmente</strong>. Se indica cuántas hay ocultas y puedes volver a mostrarlas. No se recuerda al salir.</li>
        <li><strong>Inactivar</strong> (icono ⊘): la persona se vuelve gris y su <strong>QR queda inaccesible</strong> hasta reactivarla. También desde su ficha.</li>
        <li><strong>Dar por fallecida</strong> (icono ✝, o el botón en la ficha): marca a la persona como <strong>fallecida</strong> (pide confirmación). Se <strong>conserva la ficha</strong> pero el <strong>QR deja de estar disponible</strong> y sale de los flujos activos (incluida la app de Asignación). Es <strong>reversible</strong> con <span class="qt-chip-inline">↩ Quitar fallecimiento</span>. El botón <span class="qt-chip-inline">✝ Ocultar fallecidas</span> del listado las esconde.</li>
        <li><strong>Eliminar</strong> (icono 🗑): borra a la persona (pide confirmación). También desde la ficha.</li>
      </ul>` },
    { id: 'notas', icon: '📝', title: 'Notas por persona', html: `
      <p>Puedes pegar una <b>nota</b> (texto + color) a cada persona, para recordar «qué le pasa». Se añade/edita con el botón <b>📝</b> de su fila o tarjeta en el listado, o en su <b>ficha</b> («📝 Añadir/Editar nota»). La nota se ve en la tarjeta y en la ficha.</p>
      <p>En el listado, el botón <b>«📝 Con nota»</b> filtra para ver solo las personas que tienen una nota. Un texto vacío borra la nota.</p>` },
    { id: 'grupos-color', icon: '🎨', title: 'Un color por residencia (grupo)', html: `
      <p>En la <b>ficha</b> de una persona, junto a los colores del QR, el botón <b>🏠🎨</b> abre <b>«Colores por grupo/residencia»</b>: lista todos los grupos que existen y a cada uno le asignas un <b>color</b> (paleta rápida o selector personalizado; la «✕» lo quita). Sirve para <b>distinguir residencias de un vistazo</b>.</p>
      <p><b>Precedencia del color del QR:</b> color propio de la persona (en «Ajustes del QR») › color de su grupo/residencia › color global por defecto. Si alguien está en varios grupos, se usa el del primero que tenga color.</p>
      <p><b>Dónde se ve ese color:</b></p>
      <ul>
        <li>El <b>QR</b> de esas personas (en el listado, las tarjetas, la ficha y el PDF exportado).</li>
        <li>El <b>nombre del grupo</b> allí donde aparece (etiquetas en el listado, ficha, carrito y gestor de grupos).</li>
        <li>Las <b>tarjetas contadoras</b> del panel «Grupos»: una franja del color y, al seleccionarlas, un degradado en ese mismo color.</li>
        <li>También en el <b>QR de la app de Asignación</b> y en los <b>emails de notificación</b> (usan el mismo color de residencia).</li>
      </ul>` },
    { id: 'grupos', icon: '👥', title: 'Grupos (varios por persona)', html: `
      <p>Una persona puede pertenecer a <strong>varios grupos</strong>. En su ficha, «Gestionar grupos» te deja añadir grupos (chips) y quitarlos con la ×.</p>
      <p>Los grupos se ven en el listado y en el carrito como etiquetas. Al <strong>pulsar una etiqueta de grupo</strong> se seleccionan de golpe todos los que pertenecen a ese grupo. La búsqueda también encuentra por grupo.</p>
      <div class="qt-note tip">Bajo el título del listado hay una cabecera <b>«Grupos»</b> (plegada por defecto). Al desplegarla aparecen <b>tarjetas por grupo con su número de personas</b>: pulsa una para <b>filtrar</b> el listado a ese grupo, y otra vez (o «Filtrando… ✕») para quitar el filtro.</div>` },
    { id: 'carrito', icon: '🛒', title: 'El carrito', html: `
      <p>Cada usuario tiene <strong>su propio carrito</strong>. Añade personas desde el listado (icono 🛒) o desde su ficha. Ábrelo con el botón 🛒 de arriba.</p>
      <ul>
        <li>Muestra cada persona con su <strong>QR a tamaño escaneable</strong>.</li>
        <li>Puedes <strong>seleccionar</strong> dentro del carrito (con contador; la tarjeta marcada se <strong>resalta en azul</strong>), <strong>sacar a los no seleccionados</strong>, <strong>vaciar</strong> (con confirmación) u <strong>ocultar</strong> el panel.</li>
        <li><strong>Ver en listado</strong> filtra la lista a lo que hay en el carrito. Al pulsar una persona vas a su ficha.</li>
      </ul>` },
    { id: 'importar', icon: '📥', title: 'Plantilla e importación (Excel)', html: `
      <p>El botón está <strong>arriba a la derecha</strong> del listado. En <span class="qt-chip-inline">📄 Plantilla / Importar</span>:</p>
      <ol>
        <li><strong>Descarga la plantilla</strong>: un Excel con las columnas <code>Nº Farmacia</code>, <code>Nombre</code>, <code>Apellidos</code>, <code>Código TIS</code>, <code>Código QR (real)</code> y <code>Grupo</code>.</li>
        <li>Rellénala y <strong>súbela</strong>. Se validan las filas; las que fallan o están <strong>duplicadas</strong> (Nº de farmacia distinto de 00000, o TIS) se informan y se omiten; el resto se importan.</li>
      </ol>
      <div class="qt-note tip">El <b>Código QR (real)</b> es el valor que codifica el QR de la persona (más largo que el TIS): se guarda <b>tal cual</b> (respeta espacios y símbolos como <code>% ^ ? /</code>) y <b>no se muestra</b> en la app; el <b>TIS se conserva como número</b>. Si lo dejas en blanco, el QR usará el TIS.</div>
      <div class="qt-note tip">En la columna <code>Grupo</code> puedes poner <b>varios grupos separados por punto y coma</b>: <code>Planta 2; Urgencias</code>. Si dejas el <b>Nº de farmacia</b> en blanco, se pone <code>00000</code> automáticamente.</div>` },
    { id: 'qr-codigo', icon: '🔳', title: 'El código real del QR', html: `
      <p>El QR de cada persona <strong>ya no codifica el TIS</strong>, sino un <strong>código real</strong> (más largo) que usa la farmacia. Ese código <strong>no se muestra</strong> en la app: solo se convierte en QR. El <strong>TIS se sigue viendo</strong> como siempre. Si una persona todavía no tiene código, su QR usa el TIS como antes.</p>
      <p>Hay <strong>dos formas</strong> de asignarlo:</p>
      <ol>
        <li><strong>Al dar de alta (recomendado)</strong>: en la <span class="qt-chip-inline">📄 Plantilla / Importar</span> rellena la columna <strong>Código QR (real)</strong> de cada persona nueva. Al importar, su QR se genera con ese valor y el TIS queda como número. (Ver «Plantilla e importación».)</li>
        <li><strong>Escáner o a mano</strong>: en <span class="qt-chip-inline">✏️ Editar información</span> de la persona hay un campo <strong>«Código del QR»</strong>. Enfócalo y <strong>escanea con el lector</strong> (emulador de teclado) o escríbelo. Vacío = usa el TIS.</li>
      </ol>
      <div class="qt-note tip">Bajo el título del listado, cuando haya personas sin código, aparece un enlace discreto <b>«🔳 N con el QR sin actualizar»</b>: ábrelo para <b>ir completándolos de uno en uno</b> (pulsas una persona, escaneas/escribes su código y aceptas; desaparece de la lista). El código se guarda <b>tal cual</b> (respeta espacios y símbolos como <code>% ^ ? /</code>).</div>` },
    { id: 'exportar', icon: '📦', title: 'Exportar (Excel y PDF)', html: `
      <p>Ambos botones están <strong>arriba a la derecha</strong> del listado.</p>
      <ul>
        <li><span class="qt-chip-inline">📊 Exportar Excel</span>: elige <strong>qué columnas</strong>, el <strong>orden</strong> y qué personas (las que se ven, las seleccionadas o todas).</li>
        <li><span class="qt-chip-inline">🖨️ Exportar PDF</span>: una hoja imprimible de códigos QR con el <strong>nombre, el TIS y el Nº de farmacia</strong>, con <strong>tamaño de QR variable</strong>. Puedes <strong>filtrar por residencias (grupos)</strong> y elegir el <strong>orden</strong>: Nº de farmacia, TIS, Nombre, Apellidos o <strong>Residencia</strong>; si ordenas por residencia, eliges además <strong>cómo ordenar dentro de cada una</strong>. Cada QR sale con el <strong>color de su persona o de su residencia</strong>.</li>
      </ul>` },
    { id: 'recientes', icon: '🕘', title: 'Recientes', html: `
      <p><span class="qt-chip-inline">🕘 Recientes</span> muestra las <strong>últimas 10 personas manejadas</strong> (creadas, editadas o cuya ficha se ha abierto). Pulsa una para ir a su ficha.</p>` },
    { id: 'medicacion', icon: '💊', title: 'Plan de medicación (pastilla) e ir a Asignación', html: `
      <p>En el <strong>listado</strong>, cada persona muestra una <strong>pastilla 💊</strong>: <strong>verde</strong> si ya tiene plan de medicación y <strong>gris</strong> si no. Al pulsarla, si tiene plan te lleva directo a él en <strong>Asignación</strong>; si no, te pregunta si quieres <strong>crear su plan</strong> (aunque quede vacío) y lo abre. Un plan creado <strong>se guarda</strong> aunque no tenga medicamentos todavía. Solo aparece si tienes acceso a Asignación.</p>
      <p>En la <strong>ficha</strong> también está el botón <strong>💊 Medicación</strong>, con el mismo destino.</p>` },
  ];
  const nav = SECS.map(s => `<a data-go="help-${s.id}">${s.icon} ${s.title}</a>`).join('');
  const secs = SECS.map(s => `<section class="qt-help-sec" id="help-${s.id}"><h2><span class="em">${s.icon}</span>${s.title}</h2>${s.html}</section>`).join('');
  main().innerHTML =
    `<button class="qt-back" id="back">← Volver</button>
     <div class="qt-help-hero"><div class="qt-help-hero-txt"><h1>Manual de Gestión de QR (TIS)</h1><p>Todo lo que puedes hacer, explicado paso a paso. Usa el índice para saltar a cada apartado.</p></div><button class="qt-help-dl" id="help-pdf" title="Descargar todo el manual en PDF">⬇ Descargar PDF</button></div>
     <div class="qt-help-wrap">
       <nav class="qt-help-nav">${nav}</nav>
       <div class="qt-help-content">${secs}</div>
     </div>`;
  $('back').onclick = () => (S.currentPersonId ? viewList() : viewHome());
  main().querySelectorAll('.qt-help-nav [data-go]').forEach(a => a.addEventListener('click', () => {
    const el = document.getElementById(a.dataset.go); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
  $('help-pdf').onclick = () => downloadHelpPdf(SECS, 'Manual de Gestión de QR (TIS)', 'Todo lo que puedes hacer, explicado paso a paso.', 'Manual_QR_TIS.pdf');
  window.scrollTo({ top: 0 });
}

// Ask the server to turn the on-screen manual into an elegant, branded PDF.
async function downloadHelpPdf(secs, title, subtitle, filename) {
  const btn = $('help-pdf'); if (!btn) return;
  const prev = btn.innerHTML; btn.disabled = true; btn.innerHTML = '⏳ Generando…';
  try {
    const blob = await apiBlob('/help/pdf', { title, subtitle, sections: secs.map(s => ({ icon: s.icon, title: s.title, html: s.html })) });
    downloadBlob(blob, filename);
    toast('Manual en PDF descargado 📄', 'ok');
  } catch (e) { toast(e.message || 'No se pudo generar el PDF.', 'err'); }
  finally { btn.disabled = false; btn.innerHTML = prev; }
}

// ── Generic tool modal + Excel/PDF/Recientes ────────────────────────────────────
function openModal(html, opts) {
  const box = $('tool-modal-box'); box.innerHTML = html;
  box.classList.toggle('qt-modal-wide', !!(opts && opts.wide));
  $('tool-modal').hidden = false;
  box.querySelectorAll('[data-close]').forEach(b => b.onclick = closeModal);
}
function closeModal() { $('tool-modal').hidden = true; const box = $('tool-modal-box'); box.innerHTML = ''; box.classList.remove('qt-modal-wide'); }

async function apiBlob(path, body) {
  const r = await fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || ('Error ' + r.status)); }
  return r.blob();
}
function downloadBlob(blob, name) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
function stamp() { const d = new Date(); const p = n => String(n).padStart(2, '0'); return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`; }

// Excel eats leading zeros of numbers → recover a fixed-width code by padding.
function padNum(v, n) { let s = String(v == null ? '' : v).replace(/\D/g, ''); if (s.length && s.length < n) s = s.padStart(n, '0'); return s; }
function padTis(v) { return padNum(v, 8); }

const EXPORT_COLS = [
  { key: 'pharmacy_no', label: 'Nº Farmacia', def: true, text: true, get: p => String(p.pharmacy_no || '') },
  { key: 'nombre', label: 'Nombre', def: true, get: p => p.nombre },
  { key: 'apellidos', label: 'Apellidos', def: true, get: p => p.apellidos },
  { key: 'tis', label: 'Código TIS', def: true, text: true, get: p => String(p.tis) },
  { key: 'group_name', label: 'Grupo', def: true, get: p => p.group_name || '' },
  { key: 'active', label: 'Estado', def: false, get: p => (p.deceased ? 'Fallecida' : p.active ? 'Activa' : 'Inactiva') },
  { key: 'created_at', label: 'Fecha de alta', def: false, get: p => fmtDate(p.created_at) },
  { key: 'id', label: 'ID interno', def: false, get: p => p.id },
];

function sortPeople(arr, key, dir) {
  const mul = dir === 'desc' ? -1 : 1;
  return arr.slice().sort((a, b) => {
    if (key === 'active' || key === 'id') return ((a[key] || 0) - (b[key] || 0)) * mul;
    const av = norm(a[key] == null ? '' : a[key]), bv = norm(b[key] == null ? '' : b[key]);
    return av.localeCompare(bv, 'es', { numeric: true }) * mul;
  });
}
// People for an export scope. 'filtered' respects the current search/sort/hide.
function scopePeople(scope) {
  if (scope === 'selected') return S.people.filter(p => S.selected.has(p.id));
  if (scope === 'all') return S.people.slice();
  return filteredPeople();
}
const scopeHtml = (id) =>
  `<div class="qt-tool-row">
     <label>Personas:</label>
     <select class="qt-select" id="${id}">
       <option value="filtered">Las que se ven ahora (${filteredPeople().length})</option>
       <option value="selected">Solo seleccionadas (${S.selected.size})</option>
       <option value="all">Todas (${S.people.length})</option>
     </select>
   </div>`;

// ── Tool 1: plantilla Excel + importación ───────────────────────────────────────
function toolExcelIO() {
  openModal(
    `<div class="qt-modal-h"><h3>Plantilla e importación (Excel)</h3><button class="qt-x" data-close>×</button></div>
     <div class="qt-tool-opt">
       <h4>1 · Descargar plantilla</h4>
       <p>Un Excel con las columnas <strong>Nº Farmacia (5 cifras), Nombre, Apellidos, Código TIS (8 cifras), Código QR (real) y Grupo</strong> listo para rellenar. Los códigos van como texto para no perder los ceros a la izquierda. En <strong>Grupo</strong> puedes poner varios separados por punto y coma (<code>Planta 2; Urgencias</code>).</p>
       <div class="qt-note tip" style="margin:0 0 10px">El <strong>Código QR (real)</strong> es el valor que codifica el QR de la persona (más largo que el TIS); se guarda tal cual y <strong>no se muestra</strong> en la app. El <strong>TIS</strong> se conserva como número. Si dejas el Código QR en blanco, el QR usará el TIS.</p>
       <button class="qt-btn qt-btn-primary" id="tpl-dl">⬇ Descargar plantilla .xlsx</button>
     </div>
     <div class="qt-tool-opt">
       <h4>2 · Importar Excel relleno</h4>
       <p>Sube el mismo Excel con los datos. Se leen Nº Farmacia, Nombre, Apellidos, Código TIS y Código QR (real). Las filas no válidas se informan y se omiten.</p>
       <div class="qt-dropfile" id="imp-drop">📥 Haz clic o arrastra aquí tu Excel (.xlsx / .csv)</div>
       <input type="file" id="imp-file" accept=".xlsx,.xls,.csv" hidden>
       <div class="qt-import-report" id="imp-report"></div>
     </div>`
  );
  $('tpl-dl').onclick = downloadTemplate;
  const drop = $('imp-drop'), file = $('imp-file');
  drop.onclick = () => file.click();
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('drag'); };
  drop.ondragleave = () => drop.classList.remove('drag');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('drag'); if (e.dataTransfer.files[0]) importFile(e.dataTransfer.files[0]); };
  file.onchange = () => { if (file.files[0]) importFile(file.files[0]); };
}

function downloadTemplate() {
  const aoa = [
    ['Nº Farmacia', 'Nombre', 'Apellidos', 'Código TIS', 'Código QR (real)', 'Grupo'],
    ['01234', 'José', 'Pérez García', '00123456', '%0000000000930868^BBBBBBBBBN583421^02^PEREZ/GARCIA/JOSE? TDG', 'Planta 2'],
    ['00250', 'María', 'López Ruiz', '01002000', '', 'Planta 2; Urgencias'],
  ];
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  ws['!cols'] = [{ wch: 12 }, { wch: 22 }, { wch: 26 }, { wch: 14 }, { wch: 46 }, { wch: 26 }];
  // Force the code columns (A: Nº Farmacia, D: Código TIS, E: Código QR) to text so
  // leading zeros and symbols (% ^ ? /) survive untouched.
  for (let r = 1; r <= 2; r++) for (const c of [0, 3, 4]) { const cell = XLSX.utils.encode_cell({ r, c }); if (ws[cell]) { ws[cell].t = 's'; ws[cell].z = '@'; } }
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Personas');
  XLSX.writeFile(wb, 'Plantilla_TIS.xlsx');
}

function parseWorkbook(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = e => {
      try {
        const wb = XLSX.read(new Uint8Array(e.target.result), { type: 'array' });
        const ws = wb.Sheets[wb.SheetNames[0]];
        resolve(XLSX.utils.sheet_to_json(ws, { header: 1, raw: false, defval: '' }));
      } catch (err) { reject(new Error('No se pudo leer el Excel.')); }
    };
    fr.onerror = () => reject(new Error('No se pudo leer el fichero.'));
    fr.readAsArrayBuffer(file);
  });
}

async function importFile(file) {
  const report = $('imp-report');
  report.innerHTML = 'Leyendo…';
  try {
    const aoa = await parseWorkbook(file);
    if (!aoa.length) throw new Error('El Excel está vacío.');
    const header = aoa[0].map(h => norm(String(h)));
    const find = (...names) => header.findIndex(h => names.some(n => h.includes(n)));
    const ci = { pharmacy: find('farmacia'), nombre: find('nombre'), apellidos: find('apellido'), tis: find('tis'), qr: find('codigo qr', 'qr'), grupo: find('grupo') };
    if (ci.pharmacy < 0 || ci.nombre < 0 || ci.apellidos < 0 || ci.tis < 0)
      throw new Error('Faltan columnas. El Excel debe tener «Nº Farmacia», «Nombre», «Apellidos» y «Código TIS».');
    const rows = [];
    for (let i = 1; i < aoa.length; i++) {
      const r = aoa[i];
      const pharmacyRaw = padNum(r[ci.pharmacy], 5);
      const nombre = String(r[ci.nombre] || '').trim();
      const apellidos = String(r[ci.apellidos] || '').trim();
      const tis = padTis(r[ci.tis]);
      const qr_code = ci.qr >= 0 ? String(r[ci.qr] == null ? '' : r[ci.qr]) : '';   // verbatim; backend limpia solo saltos de línea
      const group_name = ci.grupo >= 0 ? String(r[ci.grupo] || '').trim() : '';
      if (!pharmacyRaw && !nombre && !apellidos && !tis) continue; // skip blank rows
      // Empty pharmacy → the "no number" placeholder 00000 (which may repeat).
      const pharmacy_no = pharmacyRaw || '00000';
      rows.push({ __row: i + 1, pharmacy_no, nombre, apellidos, tis, qr_code, group_name });
    }
    if (!rows.length) throw new Error('No hay filas con datos.');
    report.innerHTML = `Importando ${rows.length} fila(s)…`;
    const res = await api('/import', jbody({ rows }));
    await reloadPeople();
    let html = `<div class="ok">✓ ${res.created} persona(s) importada(s)${res.errors.length ? `, ${res.errors.length} con error` : ''}.</div>`;
    if (res.errors.length) html += `<div class="qt-import-errs">${res.errors.map(e => `<div class="err">Fila ${e.row}: ${esc(e.error)}</div>`).join('')}</div>`;
    html += `<div style="margin-top:12px"><button class="qt-btn qt-btn-primary" id="imp-done">Ver listado</button></div>`;
    report.innerHTML = html;
    $('imp-done').onclick = () => { closeModal(); viewList(); };
    toast(`${res.created} importada(s)`, 'ok');
  } catch (e) { report.innerHTML = `<div class="err">✕ ${esc(e.message)}</div>`; }
}


// People whose QR still encodes the TIS (no real code yet). Active only.
function qrPendingPeople() { return (S.people || []).filter(p => p.active && !p.qr_code); }
// Discreet link under the list heading: "N con el QR sin actualizar".
function refreshQrPendingBtn() {
  const b = $('qr-pending-btn'); if (!b) return;
  const n = qrPendingPeople().length;
  if (!n) { b.hidden = true; return; }
  b.hidden = false;
  b.textContent = `🔳 ${n} con el QR sin actualizar`;
  b.title = 'Ver y completar el código real del QR de quienes todavía usan el TIS';
  b.onclick = openQrPending;
}
// A comfortable way to fill the real QR code person by person: a modal listing the
// pending people; click one, scan/type its code, accept → it leaves the list.
function qrpGroupKey(p) { return (p.groups && p.groups.length) ? p.groups.join(' · ') : 'Sin grupo'; }
function openQrPending() {
  openModal(
    `<div class="qt-modal-h"><h3>QR sin actualizar <span id="qrp-count"></span></h3><button class="qt-x" data-close>×</button></div>
     <p style="color:var(--muted);font-size:.9rem;margin:0 0 10px">Personas cuyo QR todavía codifica el <strong>TIS</strong>, <strong>agrupadas por residencia</strong>. Pulsa una, <strong>escanea</strong> (lector emulador de teclado) o escribe su <strong>código real</strong> y acepta: desaparecerá de la lista. O abre su <strong>ficha</strong>.</p>
     <div class="qt-qrp-list" id="qrp-list"></div>`,
    { wide: true }
  );
  renderQrPendingList();
}
function renderQrPendingList() {
  const list = $('qrp-list'); if (!list) return;
  const pending = qrPendingPeople();
  const cnt = $('qrp-count'); if (cnt) cnt.textContent = `(${pending.length})`;
  refreshQrPendingBtn();   // keep the discreet counter in the list behind in sync
  if (!pending.length) { list.innerHTML = '<div class="qt-empty">🎉 Todas las personas tienen su código real. ¡Listo!</div>'; return; }
  // Group by residence, ordered (Sin grupo last), and by surname within each.
  const byG = new Map();
  for (const p of pending) { const k = qrpGroupKey(p); if (!byG.has(k)) byG.set(k, []); byG.get(k).push(p); }
  const keys = [...byG.keys()].sort((a, b) => a === 'Sin grupo' ? 1 : b === 'Sin grupo' ? -1 : a.localeCompare(b, 'es'));
  for (const k of keys) byG.get(k).sort((a, b) => `${a.apellidos} ${a.nombre}`.localeCompare(`${b.apellidos} ${b.nombre}`, 'es'));
  const rowHtml = p => `
    <div class="qt-qrp-item" data-qrp="${p.id}">
      <div class="qt-qrp-head">
        <button class="qt-qrp-main" data-qrp-toggle="${p.id}" title="Escribir / escanear el código">
          <span class="qt-qrp-name">${esc(p.apellidos)}, ${esc(p.nombre)}</span>
          <span class="qt-qrp-meta">${(p.groups && p.groups.length) ? '👥 ' + esc(p.groups.join(' · ')) + ' · ' : ''}Nº ${p.pharmacy_no ? esc(p.pharmacy_no) : '—'} · TIS ${esc(fmtTis(p.tis))}</span>
        </button>
        <button class="qt-btn qt-btn-ghost qt-btn-sm qt-qrp-ficha" data-qrp-open="${p.id}" title="Abrir la ficha de la persona">Ficha ↗</button>
      </div>
      <div class="qt-qrp-edit" hidden>
        <input class="qt-input" data-qrp-input="${p.id}" placeholder="Escanea o escribe el código real…" autocomplete="off">
        <button class="qt-btn qt-btn-primary qt-btn-sm" data-qrp-save="${p.id}">✓ Aceptar</button>
      </div>
    </div>`;
  list.innerHTML = keys.map(k => `
    <div class="qt-qrp-group"><span class="qt-qrp-gname">${k === 'Sin grupo' ? '— Sin grupo' : '👥 ' + esc(k)}</span><span class="qt-qrp-gcount">${byG.get(k).length}</span></div>
    ${byG.get(k).map(rowHtml).join('')}`).join('');
  list.querySelectorAll('[data-qrp-toggle]').forEach(h => h.onclick = () => {
    const item = h.closest('.qt-qrp-item'); const ed = item.querySelector('.qt-qrp-edit');
    const wasHidden = ed.hidden;
    list.querySelectorAll('.qt-qrp-edit').forEach(e => { e.hidden = true; });
    ed.hidden = !wasHidden;
    if (!ed.hidden) { const inp = ed.querySelector('input'); setTimeout(() => inp && inp.focus(), 20); }
  });
  list.querySelectorAll('[data-qrp-open]').forEach(btn => btn.onclick = () => { const id = Number(btn.dataset.qrpOpen); closeModal(); viewFicha(id); });
  list.querySelectorAll('[data-qrp-save]').forEach(btn => btn.onclick = () => saveQrPending(Number(btn.dataset.qrpSave)));
  list.querySelectorAll('[data-qrp-input]').forEach(inp => inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); saveQrPending(Number(inp.dataset.qrpInput)); } }));
}
async function saveQrPending(id) {
  const inp = document.querySelector(`[data-qrp-input="${id}"]`); if (!inp) return;
  const code = inp.value;
  if (!code.trim()) { toast('Escanea o escribe el código antes de aceptar.', 'err'); inp.focus(); return; }
  try {
    const { item } = await api('/people/' + id + '/qr-code', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ qr_code: code }) });
    if (item) { S.byId.set(item.id, item); const i = S.people.findIndex(x => x.id === item.id); if (i >= 0) S.people[i] = item; }
    const row = document.querySelector(`.qt-qrp-item[data-qrp="${id}"]`); if (row) row.remove();
    renderQrPendingList();      // updates the counter / empty state
    toast('Código guardado.', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}

// ── Tool 2: exportar Excel (elige campos y orden) ────────────────────────────────
function toolExportExcel() {
  const cols = EXPORT_COLS.map(c =>
    `<label class="qt-check-row"><input type="checkbox" data-col="${c.key}" ${c.def ? 'checked' : ''}> ${c.label}</label>`).join('');
  const sortOpts = EXPORT_COLS.map(c => `<option value="${c.key}" ${c.key === S.sort.key ? 'selected' : ''}>${c.label}</option>`).join('');
  openModal(
    `<div class="qt-modal-h"><h3>Exportar a Excel</h3><button class="qt-x" data-close>×</button></div>
     <p style="color:var(--muted);font-size:.88rem;margin:0 0 8px">Elige las columnas, el orden y qué personas exportar.</p>
     <div class="qt-field-grid">${cols}</div>
     <div class="qt-tool-row">
       <label>Ordenar por:</label>
       <select class="qt-select" id="ex-sort">${sortOpts}</select>
       <select class="qt-select" id="ex-dir"><option value="asc" ${S.sort.dir === 'asc' ? 'selected' : ''}>Ascendente</option><option value="desc" ${S.sort.dir === 'desc' ? 'selected' : ''}>Descendente</option></select>
     </div>
     ${scopeHtml('ex-scope')}
     <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" data-close>Cancelar</button><button class="qt-btn qt-btn-primary" id="ex-go">⬇ Descargar Excel</button></div>`
  );
  $('ex-go').onclick = () => {
    const chosen = EXPORT_COLS.filter(c => $('tool-modal-box').querySelector(`[data-col="${c.key}"]`).checked);
    if (!chosen.length) { toast('Elige al menos una columna.', 'err'); return; }
    let people = scopePeople($('ex-scope').value);
    people = sortPeople(people, $('ex-sort').value, $('ex-dir').value);
    if (!people.length) { toast('No hay personas que exportar.', 'err'); return; }
    const aoa = [chosen.map(c => c.label)];
    people.forEach((p, i) => aoa.push(chosen.map(c => c.get(p, i))));
    const ws = XLSX.utils.aoa_to_sheet(aoa);
    ws['!cols'] = chosen.map(c => ({ wch: c.key === 'apellidos' ? 26 : c.key === 'nombre' ? 20 : 14 }));
    // Keep number-like codes (Nº Farmacia, TIS) as text so leading zeros survive.
    chosen.forEach((c, ci) => { if (c.text) for (let r = 1; r <= people.length; r++) { const cell = ws[XLSX.utils.encode_cell({ r, c: ci })]; if (cell) { cell.t = 's'; cell.z = '@'; } } });
    const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Personas TIS');
    XLSX.writeFile(wb, `TIS_personas_${stamp()}.xlsx`);
    closeModal(); toast('Excel generado', 'ok');
  };
}

// ── Tool 3: exportar PDF (tamaño de QR variable) ─────────────────────────────────
// Sort value for a person by a field (residence = its groups joined).
function personSortVal(p, key) {
  if (key === 'pharmacy_no') return String(p.pharmacy_no || '');
  if (key === 'tis') return String(p.tis || '');
  if (key === 'nombre') return norm(p.nombre || '');
  if (key === 'apellidos') return norm(p.apellidos || '');
  if (key === 'residencia') return norm((p.groups && p.groups.length) ? p.groups.join(' · ') : '￿'); // sin grupo al final
  return '';
}
function sortPeopleBy(list, order, sub) {
  const cmp = (a, b, k) => personSortVal(a, k).localeCompare(personSortVal(b, k), 'es', { numeric: true });
  return list.slice().sort((a, b) => {
    if (order === 'residencia') return cmp(a, b, 'residencia') || cmp(a, b, sub || 'apellidos') || cmp(a, b, 'nombre');
    return cmp(a, b, order) || cmp(a, b, 'apellidos') || cmp(a, b, 'nombre');
  });
}
function toolExportPdf() {
  const groups = [...new Set(S.people.flatMap(p => p.groups || []))].sort((a, b) => a.localeCompare(b, 'es', { numeric: true }));
  const st = { order: 'apellidos', sub: 'apellidos', res: new Set() };
  const ORDERS = [['pharmacy_no', 'Nº farmacia'], ['tis', 'TIS'], ['nombre', 'Nombre'], ['apellidos', 'Apellidos'], ['residencia', 'Residencia']];
  const SUBS = [['pharmacy_no', 'Nº farmacia'], ['tis', 'TIS'], ['nombre', 'Nombre'], ['apellidos', 'Apellidos']];
  const seg = (id, opts, cur) => `<div class="qt-seg qt-exp-seg" id="${id}">${opts.map(([v, l]) => `<button type="button" data-v="${v}" class="${v === cur ? 'sel' : ''}">${l}</button>`).join('')}</div>`;
  openModal(
    `<div class="qt-modal-h"><h3>Exportar PDF de códigos QR</h3><button class="qt-x" data-close>×</button></div>
     <p style="color:var(--muted);font-size:.88rem;margin:0 0 8px">Una hoja imprimible con los QR y su TIS. Elige qué exportar, cómo ordenarlo y el tamaño.</p>
     <div class="qt-tool-row"><label>Título:</label><input class="qt-select" style="flex:1" id="pdf-title" value="Listado de códigos TIS" maxlength="120"></div>
     <div class="qt-tool-row" style="align-items:center">
       <label>Tamaño del QR:</label>
       <input type="range" id="pdf-size" min="70" max="280" step="10" value="150" style="flex:1;accent-color:var(--brand)">
       <span id="pdf-size-v" style="font-family:var(--mono);font-weight:700;color:var(--brand-2)">150</span>
     </div>
     ${scopeHtml('pdf-scope')}
     ${groups.length ? `<div class="qt-exp-block"><label class="qt-exp-label">Residencias (grupos)</label>
       <div class="qt-exp-chips" id="pdf-res"><button type="button" class="qt-exp-chip sel" data-r="__all">Todas</button>${groups.map(g => `<button type="button" class="qt-exp-chip${gcCls(g)}"${gcStyle(g)} data-r="${esc(g)}">${esc(g)}</button>`).join('')}</div>
       <div class="qt-exp-hint">Sin seleccionar ninguna = todas. Se combina con el ámbito de arriba.</div></div>` : ''}
     <div class="qt-exp-block"><label class="qt-exp-label">Ordenar por</label>${seg('pdf-order', ORDERS, st.order)}
       <div id="pdf-sub-wrap" hidden style="margin-top:8px"><label class="qt-exp-label">Después, dentro de cada residencia</label>${seg('pdf-sub', SUBS, st.sub)}</div></div>
     <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" data-close>Cancelar</button><button class="qt-btn qt-btn-primary" id="pdf-go">⬇ Descargar PDF</button></div>`
  );
  const sz = $('pdf-size'); sz.oninput = () => { $('pdf-size-v').textContent = sz.value; };
  const box = $('tool-modal-box');
  // Residence chips (multi-select; "Todas" clears).
  if ($('pdf-res')) box.querySelectorAll('#pdf-res .qt-exp-chip').forEach(c => c.onclick = () => {
    const r = c.dataset.r;
    if (r === '__all') st.res.clear();
    else { st.res.has(r) ? st.res.delete(r) : st.res.add(r); }
    box.querySelectorAll('#pdf-res .qt-exp-chip').forEach(x => x.classList.toggle('sel', x.dataset.r === '__all' ? st.res.size === 0 : st.res.has(x.dataset.r)));
  });
  // Order segments (+ show the secondary one only when ordering by residence).
  box.querySelector('#pdf-order').querySelectorAll('button').forEach(b => b.onclick = () => {
    st.order = b.dataset.v; box.querySelector('#pdf-order').querySelectorAll('button').forEach(x => x.classList.toggle('sel', x === b));
    $('pdf-sub-wrap').hidden = st.order !== 'residencia';
  });
  box.querySelector('#pdf-sub').querySelectorAll('button').forEach(b => b.onclick = () => {
    st.sub = b.dataset.v; box.querySelector('#pdf-sub').querySelectorAll('button').forEach(x => x.classList.toggle('sel', x === b));
  });
  $('pdf-go').onclick = async () => {
    let people = scopePeople($('pdf-scope').value);
    if (st.res.size) people = people.filter(p => (p.groups || []).some(g => st.res.has(g)));
    people = sortPeopleBy(people, st.order, st.sub);
    if (!people.length) { toast('No hay personas que exportar con esos filtros.', 'err'); return; }
    const btn = $('pdf-go'); btn.disabled = true; btn.textContent = 'Generando…';
    try {
      const blob = await apiBlob('/export/pdf', { ids: people.map(p => p.id), qr_size: Number(sz.value), title: $('pdf-title').value });
      downloadBlob(blob, `TIS_QR_${stamp()}.pdf`);
      closeModal(); toast(`PDF generado · ${people.length} persona(s)`, 'ok');
    } catch (e) { toast(e.message, 'err'); btn.disabled = false; btn.textContent = '⬇ Descargar PDF'; }
  };
}

// ── Tool 4: recientes ────────────────────────────────────────────────────────────
async function toolRecent() {
  openModal(`<div class="qt-modal-h"><h3>Últimas 10 personas manejadas</h3><button class="qt-x" data-close>×</button></div><div id="recent-body">Cargando…</div>`);
  try {
    const { items } = await api('/recent');
    if (!items.length) { $('recent-body').innerHTML = '<div class="qt-empty">Aún no se ha manejado ninguna persona.</div>'; return; }
    $('recent-body').innerHTML = `<div class="qt-recent-list">${items.map(p =>
      `<div class="qt-recent-item ${p.active ? '' : 'off'}" data-open="${p.id}">
         <span class="qt-cell-pharm">${p.pharmacy_no ? esc(p.pharmacy_no) : '—'}</span>
         <span class="nm">${esc(p.nombre)} ${esc(p.apellidos)}</span>
         <span class="ts">${esc(p.tis)}</span>
         <span class="when">${fmtDateTime(p.handled_at)}</span>
       </div>`).join('')}</div>`;
    $('recent-body').querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => { closeModal(); gotoFicha(Number(el.dataset.open), items.map(x => x.id)); }));
  } catch (e) { $('recent-body').innerHTML = `<div class="err" style="color:var(--danger)">${esc(e.message)}</div>`; }
}

// ── Misc ──────────────────────────────────────────────────────────────────────
function fmtDate(s) {
  if (!s) return '';
  const d = new Date(String(s).replace(' ', 'T') + 'Z');
  if (isNaN(d)) return s;
  return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' });
}
function fmtDateTime(s) {
  if (!s) return '';
  const d = new Date(String(s).replace(' ', 'T') + 'Z');
  if (isNaN(d)) return s;
  return d.toLocaleString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

// ── UI state persistence (survive navigation between apps) ──────────────────────
// So going QR → Asignación → back to QR keeps the same filtered list / selection,
// instead of resetting to «todas las personas». Kept per-browser in localStorage.
const UI_KEY = 'qrtis_ui';
function persistState() {
  try {
    localStorage.setItem(UI_KEY, JSON.stringify({
      view: S.view, query: S.query, andor: S.andor,
      sort: S.sort, listMode: S.listMode,
      showListQr: S.showListQr, selectedOnly: S.selectedOnly, cartView: S.cartView,
      hideDeceased: S.hideDeceased, notesOnly: S.notesOnly,
      groupFilter: S.groupFilter, groupsOpen: S.groupsOpen,
      selected: [...S.selected], hidden: [...S.hidden],
      currentPersonId: S.currentPersonId,
    }));
  } catch { }
}
function restoreState() {
  try {
    const raw = localStorage.getItem(UI_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw);
    if (!s || typeof s !== 'object') return null;
    if (typeof s.query === 'string') S.query = s.query;
    if (s.andor === 'AND' || s.andor === 'OR') S.andor = s.andor;
    if (s.sort && typeof s.sort.key === 'string') S.sort = { key: s.sort.key, dir: s.sort.dir === 'desc' ? 'desc' : 'asc' };
    if (s.listMode === 'table' || s.listMode === 'cards') S.listMode = s.listMode;
    S.showListQr = !!s.showListQr; S.selectedOnly = !!s.selectedOnly; S.cartView = !!s.cartView;
    S.hideDeceased = !!s.hideDeceased; S.notesOnly = !!s.notesOnly;
    S.groupFilter = (typeof s.groupFilter === 'string' && s.groupFilter) ? s.groupFilter : null;
    S.groupsOpen = !!s.groupsOpen;
    if (Array.isArray(s.selected)) S.selected = new Set(s.selected.filter(id => S.byId.has(id)));
    if (Array.isArray(s.hidden)) S.hidden = new Set(s.hidden.filter(id => S.byId.has(id)));
    if (s.currentPersonId && S.byId.has(s.currentPersonId)) S.currentPersonId = s.currentPersonId;
    return s;
  } catch { return null; }
}
window.addEventListener('pagehide', persistState);
window.addEventListener('beforeunload', persistState);

// ── Boot ────────────────────────────────────────────────────────────────────────
(async () => {
  $('cart-toggle').onclick = () => { if ($('cart-panel').classList.contains('open')) closeCart(); else openCart(); };
  $('help-btn').onclick = viewHelp;
  $('scrim').onclick = closeCart;
  $('tool-modal').addEventListener('click', e => { if (e.target === $('tool-modal')) closeModal(); });
  $('go-home').addEventListener('click', e => { e.preventDefault(); viewHome(); });
  try {
    const meta = await api('/meta');
    S.settings = meta.settings; S.user = meta.user; S.canAsignacion = !!meta.canAsignacion;
    await reloadPeople();
    await reloadCart();
    const saved = restoreState();
    const params = new URLSearchParams(location.search);
    const personId = Number(params.get('person'));
    if (params.has('help')) viewHelp();
    else if (personId && S.byId.has(personId)) viewFicha(personId);
    else if (saved && saved.view === 'ficha' && S.currentPersonId && S.byId.has(S.currentPersonId)) viewFicha(S.currentPersonId);
    else if (saved && saved.view === 'list') viewList();
    else if (saved && saved.view === 'form') viewHome();
    else viewHome();
  } catch (e) {
    main().innerHTML = `<div class="qt-panel"><p style="color:var(--danger)">No se pudo cargar la app: ${esc(e.message)}</p></div>`;
  }
})();
