'use strict';

// ── Gestión de QR (TIS) — frontend SPA ──────────────────────────────────────────
// Three views: (1) introducir, (2) visualizar (listado), (3) ficha con QR grande.
// Plus a per-user cart. QR codes are generated in the browser (qrcode-generator)
// so the size/colour "mando" is instant; decoding for the scan-input uses jsQR.

const API = '/qr-tis/api';
const $ = id => document.getElementById(id);
const main = () => $('qt-main');

const S = {
  people: [], byId: new Map(), settings: null, user: null,
  cart: new Set(),
  query: '', andor: 'AND',
  sort: { key: 'apellidos', dir: 'asc' },
  selected: new Set(), hidden: new Set(),
  showListQr: false, selectedOnly: false, cartView: false,
  currentPersonId: null, view: 'home',
};

// ── Tiny helpers ────────────────────────────────────────────────────────────────
function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
// Accent/ñ-insensitive, lowercase — for the fast search.
function norm(s) { return String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
function fmtTis(t) { return String(t || '').replace(/(\d{3})(\d{2})(\d{2})/, '$1 $2 $3'); }

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

// ── Views ─────────────────────────────────────────────────────────────────────
function showView(name, arg) {
  if (name === 'home') return viewHome();
  if (name === 'form') return viewForm();
  if (name === 'list') return viewList();
  if (name === 'ficha') return viewFicha(arg);
}

// Home — three big cards
function viewHome() {
  S.view = 'home';
  const card = (n, go, ico, title, desc) =>
    `<button class="qt-card" data-go="${go}">
       <div class="qt-card-n">0${n}</div>
       <div class="qt-card-ico">${ico}</div>
       <h3>${title}</h3><p>${desc}</p>
     </button>`;
  const icoAdd = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M24 12v24M12 24h24"/><rect x="6" y="6" width="36" height="36" rx="8" opacity="0.35"/></svg>`;
  const icoList = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M16 14h24M16 24h24M16 34h24"/><circle cx="9" cy="14" r="2"/><circle cx="9" cy="24" r="2"/><circle cx="9" cy="34" r="2"/></svg>`;
  const icoQr = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4"><rect x="8" y="8" width="12" height="12" rx="2"/><rect x="28" y="8" width="12" height="12" rx="2"/><rect x="8" y="28" width="12" height="12" rx="2"/><path d="M28 28h5v5M40 28v5h-5M28 40h5M35 35v5h5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  main().innerHTML =
    `<div class="qt-hero"><h1>Gestión de QR (TIS)</h1><p>Personas y su Código TIS como códigos QR listos para escanear.</p></div>
     <div class="qt-cards">
       ${card(1, 'form', icoAdd, 'Introducir persona', 'Nombre, apellidos y Código TIS (a mano o escaneando un QR). Genera al instante su código.')}
       ${card(2, 'list', icoList, 'Visualizar listado', 'Todas las personas con búsqueda potente, orden, selección, grupos y carrito.')}
       ${card(3, 'use', icoQr, 'Utilizar el QR', 'Muestra el QR de una persona a gran tamaño y ajustable para escanearlo.')}
     </div>`;
  main().querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => {
    const go = b.dataset.go;
    if (go === 'use') { if (S.currentPersonId && S.byId.has(S.currentPersonId)) viewFicha(S.currentPersonId); else viewList(); }
    else showView(go);
  }));
}

// ── (1) Introducir ──────────────────────────────────────────────────────────────
function viewForm() {
  S.view = 'form';
  main().innerHTML =
    `<button class="qt-back" id="back">← Inicio</button>
     <div class="qt-panel qt-form">
       <div class="qt-section-title">Introducir persona / TIS</div>
       <div class="qt-section-sub">Todos los campos son obligatorios <span style="color:var(--danger)">*</span></div>
       <div class="qt-form-err" id="f-err"></div>
       <div class="qt-field">
         <label>Nº de farmacia <span class="req">*</span></label>
         <input class="qt-input" id="f-farmacia" placeholder="00000" inputmode="numeric" maxlength="5" autocomplete="off" style="font-family:var(--mono);letter-spacing:.28em;text-align:center" />
         <div class="qt-field-hint">5 cifras que asigna la farmacia. Los ceros a la izquierda cuentan.</div>
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
         <label>Código TIS <span class="req">*</span></label>
         <div class="qt-tis-wrap">
           <input class="qt-input" id="f-tis" placeholder="0000000" inputmode="numeric" maxlength="7" autocomplete="off" />
           <button type="button" class="qt-scan-btn" id="f-scan" title="Escanear QR con la cámara">⛶</button>
         </div>
         <div class="qt-field-hint">7 cifras. Los ceros a la izquierda cuentan. Puedes escribirlo o pulsar ⛶ para escanear un QR.</div>
       </div>
       <div class="qt-form-actions">
         <button class="qt-btn qt-btn-ghost" id="f-cancel">Cancelar</button>
         <button class="qt-btn qt-btn-primary" id="f-save">Generar QR ✦</button>
       </div>
     </div>`;
  $('back').onclick = viewHome;
  $('f-cancel').onclick = viewHome;
  const tisEl = $('f-tis');
  tisEl.addEventListener('input', () => { tisEl.value = tisEl.value.replace(/\D/g, '').slice(0, 7); });
  $('f-scan').onclick = () => openScanner((raw, digits) => {
    tisEl.value = (digits && digits.length >= 7) ? digits.slice(0, 7) : digits || '';
    if (tisEl.value.length === 7) toast('TIS escaneado: ' + tisEl.value, 'ok');
    else toast('QR leído, pero no son 7 cifras. Revísalo.', 'err');
  });
  $('f-save').onclick = submitForm;
  const farmEl = $('f-farmacia');
  farmEl.addEventListener('input', () => { farmEl.value = farmEl.value.replace(/\D/g, '').slice(0, 5); });
  farmEl.focus();
  [farmEl, tisEl, $('f-nombre'), $('f-apellidos')].forEach(el => el.addEventListener('keydown', e => { if (e.key === 'Enter') submitForm(); }));
}

async function submitForm() {
  const pharmacy_no = $('f-farmacia').value.replace(/\D/g, '');
  const nombre = $('f-nombre').value.trim();
  const apellidos = $('f-apellidos').value.trim();
  const tis = $('f-tis').value.replace(/\D/g, '');
  const err = $('f-err');
  $('f-farmacia').classList.toggle('is-invalid', !/^\d{5}$/.test(pharmacy_no));
  $('f-nombre').classList.toggle('is-invalid', !nombre);
  $('f-apellidos').classList.toggle('is-invalid', !apellidos);
  $('f-tis').classList.toggle('is-invalid', !/^\d{7}$/.test(tis));
  if (!/^\d{5}$/.test(pharmacy_no)) { err.textContent = 'El Nº de farmacia debe tener exactamente 5 cifras.'; return; }
  if (!nombre || !apellidos) { err.textContent = 'Nombre y apellidos son obligatorios.'; return; }
  if (!/^\d{7}$/.test(tis)) { err.textContent = 'El Código TIS debe tener exactamente 7 cifras.'; return; }
  err.textContent = '';
  try {
    const { item } = await api('/people', jbody({ pharmacy_no, nombre, apellidos, tis }));
    await reloadPeople();
    toast('Persona guardada ✓', 'ok');
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
    ? `<div class="qt-qr-box" id="ficha-qr">${qrSvg(p.tis, { dark: st.qr_dark, light: st.qr_light, style: st.qr_style, ecc: st.qr_ecc, size: st.qr_size })}</div>`
    : `<div class="qt-inactive-banner">Persona <strong>inactiva</strong>.<br>El QR no está disponible hasta reactivarla.</div>`;
  const groupChip = p.group_name
    ? `<span class="qt-chip-group" id="ficha-group" title="Ver el grupo">👥 ${esc(p.group_name)}</span>`
    : '';
  main().innerHTML =
    `<button class="qt-back" id="back">← ${opts.justCreated ? 'Inicio' : 'Volver'}</button>
     <div class="qt-panel qt-ficha">
       <div class="qt-qr-stage">
         <div class="qt-qr-name">${esc(p.nombre)} ${esc(p.apellidos)}</div>
         ${qrHtml}
         <div class="qt-qr-tis">${p.active ? fmtTis(p.tis) : ''}</div>
         ${p.active ? mandoHtml(st) : ''}
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
           <div class="qt-kv-row"><span class="k">Estado</span><span class="v">${p.active ? '<span style="color:var(--ok)">● Activa</span>' : '<span style="color:var(--muted)">● Inactiva</span>'}</span></div>
         </div>
         <div id="group-area"></div>
         <div class="qt-ficha-actions">
           <button class="qt-btn ${inCart ? 'qt-btn-ghost' : 'qt-btn-teal'}" id="act-cart">${inCart ? '✓ En el carrito' : '🛒 Añadir al carrito'}</button>
           <button class="qt-btn qt-btn-ghost" id="act-group">👥 ${p.group_name ? 'Cambiar grupo' : 'Añadir a grupo'}</button>
           <button class="qt-btn qt-btn-ghost" id="act-active">${p.active ? '⊘ Inactivar' : '✓ Activar'}</button>
           <button class="qt-btn qt-btn-ghost" id="act-list">☰ Ver listado</button>
           <button class="qt-btn qt-btn-danger" id="act-del">🗑 Eliminar</button>
         </div>
       </div>
     </div>`;
  $('back').onclick = opts.justCreated ? viewHome : viewList;
  $('act-list').onclick = viewList;
  if (p.active) wireMando(() => { const box = $('ficha-qr'); if (box) box.innerHTML = qrSvg(p.tis, { dark: S.settings.qr_dark, light: S.settings.qr_light, style: S.settings.qr_style, ecc: S.settings.qr_ecc, size: S.settings.qr_size }); });
  $('act-cart').onclick = async () => { await toggleCart(id); viewFicha(id, opts); };
  $('act-active').onclick = async () => { await setActive(p, !p.active); viewFicha(id, opts); };
  $('act-del').onclick = async () => { if (await removePerson(p)) viewList(); };
  $('act-group').onclick = () => renderGroupInline(p);
  const gc = $('ficha-group'); if (gc) gc.onclick = () => selectGroup(p.group_name, true);
}

function renderGroupInline(p) {
  const area = $('group-area');
  area.innerHTML =
    `<div class="qt-group-inline">
       <input id="grp-input" placeholder="Nombre del grupo (vacío = quitar)" value="${esc(p.group_name || '')}" maxlength="80" />
       <button class="qt-btn qt-btn-primary qt-btn-sm" id="grp-save">Guardar</button>
     </div>`;
  const inp = $('grp-input'); inp.focus();
  const save = async () => {
    try {
      const { item } = await api('/people/' + p.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ group_name: inp.value.trim() }) });
      S.byId.set(item.id, item); await reloadPeople();
      toast(item.group_name ? 'Añadida al grupo «' + item.group_name + '»' : 'Quitada del grupo', 'ok');
      viewFicha(p.id);
    } catch (e) { toast(e.message, 'err'); }
  };
  $('grp-save').onclick = save;
  inp.addEventListener('keydown', e => { if (e.key === 'Enter') save(); });
}

// ── The QR "mando" (shared global settings) ─────────────────────────────────────
function mandoHtml(st) {
  const swatches = ['#0f172a', '#1273b8', '#0a9d8e', '#7c3aed', '#c23a3a', '#b26a00', '#000000'];
  return `<div class="qt-mando">
    <div class="qt-mando-h">⚙ Ajustes del QR <span class="qt-mando-note">(compartidos)</span></div>
    <div class="qt-mando-row"><label>Tamaño</label><input type="range" id="m-size" min="160" max="620" step="10" value="${st.qr_size}"></div>
    <div class="qt-mando-row"><label>Color</label>
      <div class="qt-swatches" id="m-swatches">${swatches.map(c => `<div class="qt-swatch${c === st.qr_dark ? ' sel' : ''}" data-c="${c}" style="background:${c}"></div>`).join('')}</div>
      <input type="color" class="qt-color-input" id="m-dark" value="${st.qr_dark}" title="Color personalizado">
    </div>
    <div class="qt-mando-row"><label>Fondo</label>
      <input type="color" class="qt-color-input" id="m-light" value="${st.qr_light}" title="Color de fondo">
      <label style="width:auto">Estilo</label>
      <div class="qt-seg" id="m-style">
        <button data-s="square" class="${st.qr_style !== 'dots' ? 'sel' : ''}">Cuadrado</button>
        <button data-s="dots" class="${st.qr_style === 'dots' ? 'sel' : ''}">Puntos</button>
      </div>
    </div>
    <div class="qt-mando-row"><label>Robustez</label>
      <div class="qt-seg" id="m-ecc">
        ${['L', 'M', 'Q', 'H'].map(e => `<button data-e="${e}" class="${st.qr_ecc === e ? 'sel' : ''}">${e}</button>`).join('')}
      </div>
      <span class="qt-mando-note">Mayor = más denso pero más tolerante</span>
    </div>
  </div>`;
}
function wireMando(rerender) {
  const apply = () => { rerender(); saveSettingsDebounced(); };
  $('m-size').addEventListener('input', e => { S.settings.qr_size = Number(e.target.value); apply(); });
  $('m-dark').addEventListener('input', e => { S.settings.qr_dark = e.target.value; syncSwatch(); apply(); });
  $('m-light').addEventListener('input', e => { S.settings.qr_light = e.target.value; apply(); });
  $('m-swatches').querySelectorAll('.qt-swatch').forEach(sw => sw.addEventListener('click', () => {
    S.settings.qr_dark = sw.dataset.c; $('m-dark').value = sw.dataset.c; syncSwatch(); apply();
  }));
  $('m-style').querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    S.settings.qr_style = b.dataset.s; $('m-style').querySelectorAll('button').forEach(x => x.classList.toggle('sel', x === b)); apply();
  }));
  $('m-ecc').querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    S.settings.qr_ecc = b.dataset.e; $('m-ecc').querySelectorAll('button').forEach(x => x.classList.toggle('sel', x === b)); apply();
  }));
  function syncSwatch() { $('m-swatches').querySelectorAll('.qt-swatch').forEach(sw => sw.classList.toggle('sel', sw.dataset.c === S.settings.qr_dark)); }
}

// ── (2) Visualizar — listado ─────────────────────────────────────────────────────
function viewList() {
  S.view = 'list';
  const st = S.settings;
  main().innerHTML =
    `<button class="qt-back" id="back">← Inicio</button>
     <div class="qt-section-title">Listado de personas</div>
     <div class="qt-section-sub">Busca, ordena, selecciona, agrupa y usa el carrito. Haz clic en una persona para ver su QR.</div>
     <div class="qt-actions-bar">
       <button class="qt-action" id="a-excel-io"><span class="em">📄</span><span class="lbl">Plantilla / Importar<small>Excel de personas</small></span></button>
       <button class="qt-action" id="a-export-xlsx"><span class="em">📊</span><span class="lbl">Exportar Excel<small>elige campos y orden</small></span></button>
       <button class="qt-action" id="a-export-pdf"><span class="em">🖨️</span><span class="lbl">Exportar PDF<small>QR de tamaño variable</small></span></button>
       <button class="qt-action" id="a-recent"><span class="em">🕘</span><span class="lbl">Recientes<small>últimas 10 manejadas</small></span></button>
     </div>
     <div class="qt-search-wrap">
       <div class="qt-search"><span class="ico">🔎</span>
         <input id="q" placeholder="Buscar por nombre, apellidos, TIS o grupo… (p. ej. «os rez»)" value="${esc(S.query)}" autocomplete="off">
       </div>
       <div class="qt-andor" id="andor" title="AND = todas las palabras · OR = cualquier palabra">
         <button data-v="AND" class="${S.andor === 'AND' ? 'sel' : ''}">AND</button>
         <button data-v="OR" class="${S.andor === 'OR' ? 'sel' : ''}">OR</button>
       </div>
     </div>
     <div class="qt-toolbar">
       <span class="qt-count" id="list-count"></span>
       <button class="qt-toggle ${S.showListQr ? 'on' : ''}" id="tg-qr">▦ QR en el listado</button>
       <span class="qt-inline-size" id="qr-size-wrap" ${S.showListQr ? '' : 'hidden'}>
         <input type="range" id="list-qr-size" min="80" max="360" step="10" value="${st.list_qr_size}"><span id="list-qr-size-v">${st.list_qr_size}px</span>
       </span>
       <button class="qt-toggle ${S.selectedOnly ? 'on' : ''}" id="tg-selected">✔ Solo seleccionadas</button>
       <button class="qt-toggle ${S.cartView ? 'on' : ''}" id="tg-cart">🛒 Solo carrito</button>
       <button class="qt-toggle" id="clear-sel">✕ Quitar selección</button>
     </div>
     <div id="hidden-note"></div>
     <div class="qt-table-wrap"><table class="qt-table"><thead id="thead"></thead><tbody id="tbody"></tbody></table></div>`;
  $('back').onclick = viewHome;
  $('a-excel-io').onclick = toolExcelIO;
  $('a-export-xlsx').onclick = toolExportExcel;
  $('a-export-pdf').onclick = toolExportPdf;
  $('a-recent').onclick = toolRecent;
  const q = $('q');
  q.addEventListener('input', () => { S.query = q.value; renderRows(); });
  $('andor').querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    S.andor = b.dataset.v; $('andor').querySelectorAll('button').forEach(x => x.classList.toggle('sel', x === b)); renderRows();
  }));
  $('tg-qr').onclick = () => { S.showListQr = !S.showListQr; viewList(); };
  $('tg-selected').onclick = () => { S.selectedOnly = !S.selectedOnly; viewList(); };
  $('tg-cart').onclick = () => { S.cartView = !S.cartView; viewList(); };
  $('clear-sel').onclick = () => { S.selected.clear(); renderRows(); };
  if (S.showListQr) {
    const sizeEl = $('list-qr-size');
    sizeEl.addEventListener('input', () => {
      S.settings.list_qr_size = Number(sizeEl.value); $('list-qr-size-v').textContent = sizeEl.value + 'px';
      saveSettingsDebounced(); renderRows();
    });
  }
  renderHead(); renderRows();
}

function renderHead() {
  const cols = [
    { key: 'sel', label: '', sort: false },
    { key: 'pharmacy_no', label: 'Nº Farmacia' },
    { key: 'nombre', label: 'Nombre' },
    { key: 'apellidos', label: 'Apellidos' },
    { key: 'tis', label: 'Código TIS' },
    { key: 'group_name', label: 'Grupo' },
    { key: 'active', label: 'Estado' },
  ];
  if (S.showListQr) cols.push({ key: 'qr', label: 'QR', sort: false });
  cols.push({ key: 'act', label: '', sort: false });
  $('thead').innerHTML = '<tr>' + cols.map(c => {
    if (c.sort === false) return `<th class="no-sort">${c.label}</th>`;
    const sorted = S.sort.key === c.key;
    const arrow = sorted ? (S.sort.dir === 'asc' ? '▲' : '▼') : '↕';
    return `<th data-key="${c.key}" class="${sorted ? 'sorted' : ''}">${c.label} <span class="arrow">${arrow}</span></th>`;
  }).join('') + '</tr>';
  $('thead').querySelectorAll('th[data-key]').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.key;
    if (S.sort.key === k) S.sort.dir = S.sort.dir === 'asc' ? 'desc' : 'asc';
    else { S.sort.key = k; S.sort.dir = 'asc'; }
    renderHead(); renderRows();
  }));
}

function filteredPeople() {
  let rows = S.people.filter(p => !S.hidden.has(p.id));
  if (S.cartView) rows = rows.filter(p => S.cart.has(p.id));
  if (S.selectedOnly) rows = rows.filter(p => S.selected.has(p.id));
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

function renderRows() {
  const rows = filteredPeople();
  const st = S.settings;
  const tbody = $('tbody');
  const colspan = S.showListQr ? 9 : 8; // sel + pharmacy + nombre + apellidos + tis + grupo + estado (+ qr) + acciones
  const selInCart = [...S.selected].filter(id => S.cart.has(id)).length;
  $('list-count').textContent =
    `${rows.length} de ${S.people.length}` +
    (S.selected.size ? ` · ${S.selected.size} seleccionada(s)` : '') +
    (S.hidden.size ? ` · ${S.hidden.size} oculta(s)` : '');
  // hidden note
  $('hidden-note').innerHTML = S.hidden.size
    ? `<div class="qt-hidden-note">👁 Hay <strong>${S.hidden.size}</strong> persona(s) oculta(s) temporalmente. <a id="unhide">Mostrar todas</a></div>` : '';
  if (S.hidden.size) $('unhide').onclick = () => { S.hidden.clear(); renderRows(); };

  if (!rows.length) { tbody.innerHTML = `<tr><td colspan="${colspan}"><div class="qt-empty">No hay personas que coincidan.</div></td></tr>`; return; }

  tbody.innerHTML = rows.map(p => {
    const sel = S.selected.has(p.id);
    const group = p.group_name ? `<span class="qt-grouptag" data-group="${esc(p.group_name)}" title="Seleccionar todo el grupo">${esc(p.group_name)}</span>` : '<span style="color:#b3bcc7">—</span>';
    const state = p.active
      ? '<span class="qt-state-dot"><span class="dot"></span>Activa</span>'
      : '<span class="qt-state-dot off"><span class="dot"></span>Inactiva</span>';
    const qrCell = S.showListQr
      ? `<td>${p.active ? `<span class="qt-list-qr" data-open="${p.id}">${qrSvg(p.tis, { dark: st.qr_dark, light: st.qr_light, style: st.qr_style, ecc: st.qr_ecc, size: st.list_qr_size })}</span>` : '<span style="color:#b3bcc7">—</span>'}</td>`
      : '';
    const inCart = S.cart.has(p.id);
    return `<tr class="${p.active ? '' : 'is-inactive'} ${sel ? 'is-selected' : ''}" data-id="${p.id}">
      <td><input type="checkbox" class="qt-check" data-sel="${p.id}" ${sel ? 'checked' : ''}></td>
      <td><span class="qt-cell-pharm" data-open="${p.id}">${p.pharmacy_no ? esc(p.pharmacy_no) : '<span style=\"color:#c3c9d2\">—</span>'}</span></td>
      <td><span class="qt-cell-name" data-open="${p.id}">${esc(p.nombre)}</span></td>
      <td>${esc(p.apellidos)}</td>
      <td class="qt-cell-tis">${esc(p.tis)}</td>
      <td>${group}</td>
      <td>${state}</td>
      ${qrCell}
      <td><div class="qt-cell-actions">
        <button class="qt-iconbtn" data-cart="${p.id}" title="${inCart ? 'Quitar del carrito' : 'Añadir al carrito'}">${inCart ? '✓🛒' : '🛒'}</button>
        <button class="qt-iconbtn" data-active="${p.id}" title="${p.active ? 'Inactivar' : 'Activar'}">${p.active ? '⊘' : '✓'}</button>
        <button class="qt-iconbtn" data-hide="${p.id}" title="Ocultar del listado (temporal)">👁</button>
        <button class="qt-iconbtn danger" data-del="${p.id}" title="Eliminar">🗑</button>
      </div></td>
    </tr>`;
  }).join('');

  // wire
  tbody.querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => viewFicha(Number(el.dataset.open))));
  tbody.querySelectorAll('[data-sel]').forEach(cb => cb.addEventListener('change', () => {
    const id = Number(cb.dataset.sel); if (cb.checked) S.selected.add(id); else S.selected.delete(id); renderRows();
  }));
  tbody.querySelectorAll('[data-group]').forEach(g => g.addEventListener('click', () => selectGroup(g.dataset.group)));
  tbody.querySelectorAll('[data-cart]').forEach(b => b.addEventListener('click', async () => { await toggleCart(Number(b.dataset.cart)); renderRows(); }));
  tbody.querySelectorAll('[data-active]').forEach(b => b.addEventListener('click', async () => { const p = S.byId.get(Number(b.dataset.active)); await setActive(p, !p.active); renderRows(); }));
  tbody.querySelectorAll('[data-hide]').forEach(b => b.addEventListener('click', () => { S.hidden.add(Number(b.dataset.hide)); renderRows(); }));
  tbody.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', async () => { const p = S.byId.get(Number(b.dataset.del)); if (await removePerson(p)) renderRows(); }));
}

// Select every person in a group (adds to the current selection).
function selectGroup(group, goList) {
  if (!group) return;
  const g = norm(group);
  const ids = S.people.filter(p => norm(p.group_name) === g).map(p => p.id);
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
    const qr = p.active ? `<span class="qr" data-open="${p.id}">${qrSvg(p.tis, { dark: st.qr_dark, light: st.qr_light, style: st.qr_style, ecc: st.qr_ecc, size })}</span>` : `<span class="qr" style="width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center;color:#9aa4b0;font-size:.8rem">Inactiva</span>`;
    const group = p.group_name ? `<span class="qt-grouptag" data-group="${esc(p.group_name)}">${esc(p.group_name)}</span>` : '';
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
  body.querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => { closeCart(); viewFicha(Number(el.dataset.open)); }));
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

// ── Generic tool modal + Excel/PDF/Recientes ────────────────────────────────────
function openModal(html) {
  const box = $('tool-modal-box'); box.innerHTML = html;
  $('tool-modal').hidden = false;
  box.querySelectorAll('[data-close]').forEach(b => b.onclick = closeModal);
}
function closeModal() { $('tool-modal').hidden = true; $('tool-modal-box').innerHTML = ''; }

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
function padTis(v) { return padNum(v, 7); }

const EXPORT_COLS = [
  { key: 'pharmacy_no', label: 'Nº Farmacia', def: true, text: true, get: p => String(p.pharmacy_no || '') },
  { key: 'nombre', label: 'Nombre', def: true, get: p => p.nombre },
  { key: 'apellidos', label: 'Apellidos', def: true, get: p => p.apellidos },
  { key: 'tis', label: 'Código TIS', def: true, text: true, get: p => String(p.tis) },
  { key: 'group_name', label: 'Grupo', def: true, get: p => p.group_name || '' },
  { key: 'active', label: 'Estado', def: false, get: p => (p.active ? 'Activa' : 'Inactiva') },
  { key: 'created_at', label: 'Fecha de alta', def: false, get: p => fmtDate(p.created_at) },
  { key: 'num', label: 'Nº (secuencia)', def: false, get: (p, i) => i + 1 },
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
       <p>Un Excel con las columnas <strong>Nº Farmacia (5 cifras), Nombre, Apellidos y Código TIS (7 cifras)</strong> listo para rellenar. Los códigos van como texto para no perder los ceros a la izquierda.</p>
       <button class="qt-btn qt-btn-primary" id="tpl-dl">⬇ Descargar plantilla .xlsx</button>
     </div>
     <div class="qt-tool-opt">
       <h4>2 · Importar Excel relleno</h4>
       <p>Sube el mismo Excel con los datos. Se leen Nº Farmacia, Nombre, Apellidos y Código TIS. Las filas no válidas se informan y se omiten.</p>
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
    ['Nº Farmacia', 'Nombre', 'Apellidos', 'Código TIS'],
    ['01234', 'José', 'Pérez García', '0012345'],
    ['00250', 'María', 'López Ruiz', '0100200'],
  ];
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  ws['!cols'] = [{ wch: 12 }, { wch: 22 }, { wch: 26 }, { wch: 14 }];
  // Force the numeric-code columns (A: Nº Farmacia, D: Código TIS) to text so zeros survive.
  for (let r = 1; r <= 2; r++) for (const c of [0, 3]) { const cell = XLSX.utils.encode_cell({ r, c }); if (ws[cell]) { ws[cell].t = 's'; ws[cell].z = '@'; } }
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
    const ci = { pharmacy: find('farmacia'), nombre: find('nombre'), apellidos: find('apellido'), tis: find('tis') };
    if (ci.pharmacy < 0 || ci.nombre < 0 || ci.apellidos < 0 || ci.tis < 0)
      throw new Error('Faltan columnas. El Excel debe tener «Nº Farmacia», «Nombre», «Apellidos» y «Código TIS».');
    const rows = [];
    for (let i = 1; i < aoa.length; i++) {
      const r = aoa[i];
      const pharmacy_no = padNum(r[ci.pharmacy], 5);
      const nombre = String(r[ci.nombre] || '').trim();
      const apellidos = String(r[ci.apellidos] || '').trim();
      const tis = padTis(r[ci.tis]);
      if (!pharmacy_no && !nombre && !apellidos && !tis) continue; // skip blank rows
      rows.push({ __row: i + 1, pharmacy_no, nombre, apellidos, tis });
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

// ── Tool 2: exportar Excel (elige campos y orden) ────────────────────────────────
function toolExportExcel() {
  const cols = EXPORT_COLS.map(c =>
    `<label class="qt-check-row"><input type="checkbox" data-col="${c.key}" ${c.def ? 'checked' : ''}> ${c.label}</label>`).join('');
  const sortOpts = EXPORT_COLS.filter(c => c.key !== 'num').map(c => `<option value="${c.key}" ${c.key === S.sort.key ? 'selected' : ''}>${c.label}</option>`).join('');
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
function toolExportPdf() {
  openModal(
    `<div class="qt-modal-h"><h3>Exportar PDF de códigos QR</h3><button class="qt-x" data-close>×</button></div>
     <p style="color:var(--muted);font-size:.88rem;margin:0 0 8px">Una hoja imprimible con los QR y su TIS. Ajusta el tamaño del QR.</p>
     <div class="qt-tool-row"><label>Título:</label><input class="qt-select" style="flex:1" id="pdf-title" value="Listado de códigos TIS" maxlength="120"></div>
     <div class="qt-tool-row" style="align-items:center">
       <label>Tamaño del QR:</label>
       <input type="range" id="pdf-size" min="70" max="280" step="10" value="150" style="flex:1;accent-color:var(--brand)">
       <span id="pdf-size-v" style="font-family:var(--mono);font-weight:700;color:var(--brand-2)">150</span>
     </div>
     ${scopeHtml('pdf-scope')}
     <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" data-close>Cancelar</button><button class="qt-btn qt-btn-primary" id="pdf-go">⬇ Descargar PDF</button></div>`
  );
  const sz = $('pdf-size'); sz.oninput = () => { $('pdf-size-v').textContent = sz.value; };
  $('pdf-go').onclick = async () => {
    const people = scopePeople($('pdf-scope').value);
    if (!people.length) { toast('No hay personas que exportar.', 'err'); return; }
    const btn = $('pdf-go'); btn.disabled = true; btn.textContent = 'Generando…';
    try {
      const blob = await apiBlob('/export/pdf', { ids: people.map(p => p.id), qr_size: Number(sz.value), title: $('pdf-title').value });
      downloadBlob(blob, `TIS_QR_${stamp()}.pdf`);
      closeModal(); toast('PDF generado', 'ok');
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
    $('recent-body').querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => { closeModal(); viewFicha(Number(el.dataset.open)); }));
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

// ── Boot ────────────────────────────────────────────────────────────────────────
(async () => {
  $('cart-toggle').onclick = () => { if ($('cart-panel').classList.contains('open')) closeCart(); else openCart(); };
  $('scrim').onclick = closeCart;
  $('tool-modal').addEventListener('click', e => { if (e.target === $('tool-modal')) closeModal(); });
  $('go-home').addEventListener('click', e => { e.preventDefault(); viewHome(); });
  try {
    const meta = await api('/meta');
    S.settings = meta.settings; S.user = meta.user;
    await reloadPeople();
    await reloadCart();
    viewHome();
  } catch (e) {
    main().innerHTML = `<div class="qt-panel"><p style="color:var(--danger)">No se pudo cargar la app: ${esc(e.message)}</p></div>`;
  }
})();
