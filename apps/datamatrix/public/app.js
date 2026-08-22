'use strict';

// ── Gestor de códigos Data Matrix — frontend ────────────────────────────────────
// Boxes of medication identified by their GS1 Data Matrix. Scan-in to add,
// scan-out (or a button) to mark "utilizada". Data Matrix codes are generated in
// the browser (bwip-js) coloured per medication; scanning uses ZXing.

const API = '/datamatrix/api';
const $ = id => document.getElementById(id);
const main = () => $('qt-main');

const S = {
  items: [], byId: new Map(), settings: null, user: null, counts: { activo: 0, utilizado: 0 },
  palette: [], shapes: [],
  cart: new Set(),
  query: '', andor: 'AND',
  sort: { key: 'nombre', dir: 'asc' },
  selected: new Set(), hidden: new Set(),
  listMode: 'table', groupBy: false, archive: false, uncatOnly: false, preasigOnly: false,
  medFilter: null, // filter list to a GTIN
  currentItemId: null, view: 'home', nav: [],
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function norm(s) { return String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
async function api(path, opts) {
  const r = await fetch(API + path, opts);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json().catch(() => ({})) : {};
  if (!r.ok) { const err = new Error(data.error || `Error ${r.status}`); err.status = r.status; err.data = data; throw err; }
  return data;
}
function jbody(obj) { return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) }; }
async function apiBlob(path, body) {
  const r = await fetch(API + path, jbody(body));
  if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || ('Error ' + r.status)); }
  return r.blob();
}
function downloadBlob(blob, name) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); }
function stamp() { const d = new Date(); const p = n => String(n).padStart(2, '0'); return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`; }

let toastTimer = null;
function toast(msg, kind) { const t = $('toast'); t.textContent = msg; t.className = 'qt-toast' + (kind ? ' ' + kind : ''); t.hidden = false; if (toastTimer) clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 2600); }
function confirmBox(title, body, okLabel) {
  return new Promise(resolve => {
    $('confirm-title').textContent = title; $('confirm-body').textContent = body; $('confirm-yes').textContent = okLabel || 'Aceptar';
    const m = $('confirm-modal'); m.hidden = false;
    const done = v => { m.hidden = true; $('confirm-yes').onclick = null; $('confirm-no').onclick = null; resolve(v); };
    $('confirm-yes').onclick = () => done(true); $('confirm-no').onclick = () => done(false);
  });
}
function fmtDate(s) { if (!s) return ''; const d = new Date(String(s).replace(' ', 'T') + 'Z'); return isNaN(d) ? s : d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' }); }
function fmtDateTime(s) { if (!s) return ''; const d = new Date(String(s).replace(' ', 'T') + 'Z'); return isNaN(d) ? s : d.toLocaleString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); }

// Expiry status: 'vencida' | 'pronto' (≤ 90 días) | ''
function expiryState(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00Z'); if (isNaN(d)) return '';
  const days = Math.floor((d - new Date()) / 86400000);
  if (days < 0) return 'vencida';
  if (days <= 90) return 'pronto';
  return '';
}
function cadDisplay(iso) {
  if (!iso) return '—';
  const st = expiryState(iso);
  const cls = st === 'vencida' ? 'cad-bad' : st === 'pronto' ? 'cad-soon' : '';
  const label = fmtDate(iso);
  return `<span class="dm-cad ${cls}">${label}${st === 'vencida' ? ' ⚠' : st === 'pronto' ? ' ⏳' : ''}</span>`;
}

// ── Data Matrix rendering (client, via bwip-js) ─────────────────────────────────
function dmSvg(raw, o) {
  o = o || {};
  const dark = (o.dark || '#0f172a').replace('#', ''), light = (o.light || '#ffffff').replace('#', ''), size = o.size || 200;
  let svg;
  try { svg = bwipjs.toSVG({ bcid: 'datamatrix', text: String(raw || ''), barcolor: dark, backgroundcolor: light, paddingwidth: 1, paddingheight: 1 }); }
  catch (e) { return `<svg width="${size}" height="${size}"></svg>`; }
  // The browser build emits <svg viewBox="…"> with no width/height — inject an
  // explicit pixel size so it renders (and scales) at the requested size.
  return svg.replace(/<svg /, `<svg width="${size}" height="${size}" shape-rendering="crispEdges" `);
}
function dmOpts(it, size) { return { dark: it.color || S.settings.dm_dark || '#0f172a', light: S.settings.dm_light, size }; }

// A small coloured shape badge per medication (visual association).
function shapeSvg(shape, color, px) {
  px = px || 16; const c = color || '#1273b8';
  const s = { circle: `<circle cx="12" cy="12" r="9" fill="${c}"/>`,
    square: `<rect x="3.5" y="3.5" width="17" height="17" rx="3" fill="${c}"/>`,
    triangle: `<path d="M12 3l9 16H3z" fill="${c}"/>`,
    diamond: `<path d="M12 2l10 10-10 10L2 12z" fill="${c}"/>`,
    hexagon: `<path d="M7 3h10l5 9-5 9H7l-5-9z" fill="${c}"/>`,
    star: `<path d="M12 2l2.9 6 6.6.6-5 4.3 1.6 6.5L12 22l-5.7 3.4 1.6-6.5-5-4.3 6.6-.6z" fill="${c}"/>`,
    pentagon: `<path d="M12 2l10 7.3-3.8 11.7H5.8L2 9.3z" fill="${c}"/>`,
    cross: `<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" fill="${c}"/>` }[shape] || `<circle cx="12" cy="12" r="9" fill="${c}"/>`;
  return `<svg class="dm-shape" width="${px}" height="${px}" viewBox="0 0 24 24" aria-hidden="true">${s}</svg>`;
}

// A small badge for boxes reserved/dispensed via the Asignación app.
//   preasignada → reserved for a person (still in stock)
//   asignada    → dispensed to that person
function asigBadge(it) {
  if (!it || !it.asig_state) return '';
  const who = it.assignee_name ? ' · ' + esc(it.assignee_name) : '';
  return it.asig_state === 'asignada'
    ? `<span class="dm-asig dm-asig-done" title="Asignada${who}">✓ Asignada${who}</span>`
    : `<span class="dm-asig dm-asig-pre" title="Pre-asignada${who}">🔗 Pre-asignada${who}</span>`;
}

// ── Data loading ────────────────────────────────────────────────────────────────
async function reloadItems() {
  const { items, counts } = await api('/items?status=' + (S.archive ? 'utilizado' : 'activo'));
  S.items = items; S.byId = new Map(items.map(i => [i.id, i])); if (counts) S.counts = counts;
}
async function reloadCart() { const { ids } = await api('/cart'); S.cart = new Set(ids); updateCartCount(); }
function updateCartCount() { $('cart-count').textContent = S.cart.size; }

// ── Settings save (debounced) ────────────────────────────────────────────────────
let settingsTimer = null;
function saveSettingsDebounced() { if (settingsTimer) clearTimeout(settingsTimer); settingsTimer = setTimeout(async () => { try { const { settings } = await api('/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(S.settings) }); S.settings = settings; } catch (e) { toast(e.message, 'err'); } }, 400); }

// Per-medication (product) save, debounced.
let pmTimer = null, pmGtin = null, pmPatch = {};
function saveProductDebounced(gtin, patch) {
  if (pmGtin !== gtin) pmPatch = {}; pmGtin = gtin; pmPatch = { ...pmPatch, ...patch };
  if (pmTimer) clearTimeout(pmTimer);
  pmTimer = setTimeout(async () => {
    const g = pmGtin, p = pmPatch; pmGtin = null; pmPatch = {};
    try { await api('/product/' + encodeURIComponent(g), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) }); await reloadItems(); } catch (e) { toast(e.message, 'err'); }
  }, 400);
}

// ── Views ─────────────────────────────────────────────────────────────────────
function showView(name) { if (name === 'home') return viewHome(); if (name === 'scan') return viewScan(); if (name === 'list') return viewList(); }

function viewHome() {
  S.view = 'home';
  const card = (n, go, ico, title, desc) => `<button class="qt-card" data-go="${go}"><div class="qt-card-n">0${n}</div><div class="qt-card-ico">${ico}</div><h3>${title}</h3><p>${desc}</p></button>`;
  const icoScan = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 16V10h6M40 16V10h-6M8 32v6h6M40 32v6h-6"/><path d="M14 24h20" stroke-width="3"/></svg>`;
  const icoList = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M10 12v26M10 38h28" stroke-linecap="round"/><rect x="16" y="14" width="5" height="5" fill="currentColor" stroke="none"/><rect x="26" y="14" width="5" height="5" fill="currentColor" stroke="none"/><rect x="16" y="24" width="5" height="5" fill="currentColor" stroke="none"/><rect x="34" y="24" width="4" height="4" fill="currentColor" stroke="none"/></svg>`;
  main().innerHTML =
    `<div class="qt-hero"><h1>Gestor de códigos Data Matrix</h1><p>Inventario de cajas de medicación por su Data Matrix. <a id="hero-help" style="color:var(--brand);font-weight:600;cursor:pointer">¿Cómo funciona? Abre la ayuda ❔</a></p></div>
     <div class="qt-cards qt-cards-2">
       ${card(1, 'scan', icoScan, 'Escanear', 'Da <b>entrada</b> a cajas escaneando su Data Matrix, o marca la <b>salida</b> (utilizada). La app segrega los datos automáticamente.')}
       ${card(2, 'list', icoList, 'Inventario', 'Consulta lo que hay sin utilizar: busca, agrupa por medicamento, ordena y usa el carrito. Pulsa una caja para ver su Data Matrix.')}
     </div>
     <div class="dm-home-counts"><span class="dm-count-pill"><b id="hc-activo">${S.counts.activo}</b> sin utilizar</span><span class="dm-count-pill muted"><b id="hc-usada">${S.counts.utilizado}</b> utilizadas</span></div>`;
  main().querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => showView(b.dataset.go)));
  const hh = $('hero-help'); if (hh) hh.onclick = viewHelp;
}

// ── (1) Escanear (entrada / salida) ─────────────────────────────────────────────
function viewScan() {
  S.view = 'scan';
  if (!S._scanMode) S._scanMode = 'in';
  if (!S._scanLog) S._scanLog = [];
  main().innerHTML =
    `<button class="qt-back" id="back">← Inicio</button>
     <div class="qt-section-title">Escanear códigos</div>
     <div class="qt-section-sub">Con un lector de sobremesa, haz clic en el campo y escanea (se procesa al pulsar Enter). En móvil, usa la cámara.</div>
     <div class="dm-scan-mode qt-seg" id="scan-mode">
       <button data-m="in" class="${S._scanMode === 'in' ? 'sel' : ''}">⬇ Entrada (añadir)</button>
       <button data-m="out" class="${S._scanMode === 'out' ? 'sel' : ''}">⬆ Salida (utilizada)</button>
     </div>
     <div class="dm-scan-box ${S._scanMode === 'out' ? 'is-out' : ''}">
       <label class="dm-scan-label">${S._scanMode === 'in' ? 'Escanea para AÑADIR al inventario' : 'Escanea para marcar UTILIZADA (sale del inventario)'}</label>
       <div class="dm-scan-row">
         <input class="qt-input dm-raw" id="raw-in" placeholder="Escanea o pega aquí el Data Matrix…" autocomplete="off" spellcheck="false">
         <button class="qt-btn qt-btn-ghost" id="raw-cam" title="Usar la cámara">📷</button>
       </div>
       <div class="dm-scan-hint">El contenido RAW se reconoce y se reparte en sus campos automáticamente.</div>
     </div>
     <div class="dm-scan-log" id="scan-log"></div>
     <div class="qt-actions" style="margin-top:16px"><button class="qt-btn qt-btn-primary" id="go-inv">Ver inventario →</button></div>`;
  $('back').onclick = viewHome;
  $('go-inv').onclick = viewList;
  $('scan-mode').querySelectorAll('button').forEach(b => b.addEventListener('click', () => { S._scanMode = b.dataset.m; viewScan(); }));
  const raw = $('raw-in'); raw.focus();
  raw.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); const v = raw.value; raw.value = ''; if (v.trim()) processScan(v); raw.focus(); } });
  $('raw-cam').onclick = () => openScanner(S._scanMode === 'in' ? 'Escanea para AÑADIR' : 'Escanea para marcar UTILIZADA', (text) => { processScan(text); });
  renderScanLog();
}
function renderScanLog() {
  const box = $('scan-log'); if (!box) return;
  if (!S._scanLog.length) { box.innerHTML = '<div class="dm-scan-empty">Aún no has escaneado nada en esta sesión.</div>'; return; }
  box.innerHTML = S._scanLog.slice(0, 12).map((e, idx) => {
    const it = e.item;
    const cls = e.kind === 'added' ? 'ok' : e.kind === 'used' ? 'used' : 'warn';
    const isDup = e.kind === 'dup' || e.kind === 'dupused';
    const badge = { added: '✓ Añadida', used: '⬆ Utilizada', dup: '• Ya estaba', dupused: '• Ya utilizada', notfound: '⚠ No estaba', err: '✕ Error' }[e.kind] || e.kind;
    const name = it ? (it.nombre || it.gtin || '—') : (e.msg || '');
    const meta = it ? `${it.serial ? 'Nº ' + esc(it.serial) : ''}${it.caducidad ? ' · Cad ' + fmtDate(it.caducidad) : ''}` : '';
    const go = it ? `<a class="dm-line-go">${isDup ? '🔎 Ver la caja →' : 'Ver ficha →'}</a>` : '';
    return `<div class="dm-scan-line ${cls}${idx === 0 ? ' is-new' : ''}${isDup ? ' is-dup' : ''}" ${it ? `data-open="${it.id}"` : ''}>` +
      `<span class="dm-line-badge">${badge}</span><span class="dm-line-name">${esc(name)}</span><span class="dm-line-meta">${meta}</span>${go}</div>`;
  }).join('');
  box.querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => gotoFicha(Number(el.dataset.open), [])));
}
async function processScan(text) {
  try {
    if (S._scanMode === 'out') {
      const r = await api('/use', jbody({ raw: text }));
      if (r.notFound) { S._scanLog.unshift({ kind: 'notfound', msg: 'Código no encontrado en el inventario' }); toast('No estaba en el inventario', 'err'); }
      else if (r.already) { S._scanLog.unshift({ kind: 'dupused', item: r.item }); toast('Ya estaba utilizada', 'err'); }
      else { S._scanLog.unshift({ kind: 'used', item: r.item }); toast('Utilizada: ' + (r.item.nombre || r.item.gtin || ''), 'ok'); }
    } else {
      const r = await api('/scan', jbody({ raw: text }));
      if (r.duplicate) { S._scanLog.unshift({ kind: r.status === 'utilizado' ? 'dupused' : 'dup', item: r.item }); toast(r.status === 'utilizado' ? 'Esa caja ya se utilizó' : 'Ya estaba en el inventario', 'err'); }
      else { S._scanLog.unshift({ kind: 'added', item: r.item }); toast('Añadida: ' + (r.item.nombre || r.item.gtin || 'caja'), 'ok'); }
    }
    await reloadItems(); renderScanLog();
  } catch (e) { S._scanLog.unshift({ kind: 'err', msg: e.message }); renderScanLog(); toast(e.message, 'err'); }
}

// ── Scanner (camera → ZXing, decodes Data Matrix + QR) ──────────────────────────
let _zxReader = null;
function openScanner(title, onResult) {
  const modal = $('scan-modal'), video = $('scan-video'), note = $('scan-note');
  $('scan-title').textContent = title || 'Escanear';
  let stopped = false, controls = null;
  const stop = () => { stopped = true; try { if (controls) controls.stop(); } catch { } try { const s = video.srcObject; if (s) s.getTracks().forEach(t => t.stop()); } catch { } video.srcObject = null; modal.hidden = true; };
  $('scan-close').onclick = stop;
  modal.hidden = false; note.textContent = 'Solicitando cámara…'; note.className = 'qt-scan-note';
  try {
    const hints = new Map();
    hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, [ZXing.BarcodeFormat.DATA_MATRIX, ZXing.BarcodeFormat.QR_CODE]);
    if (!_zxReader) _zxReader = new ZXing.BrowserMultiFormatReader(hints, { delayBetweenScanAttempts: 120 });
    _zxReader.decodeFromVideoDevice(undefined, video, (result, err, ctrl) => {
      controls = ctrl;
      if (stopped) return;
      note.textContent = 'Apunta al código Data Matrix…';
      if (result) { const text = result.getText(); stop(); onResult(text); }
    }).then(c => { controls = c; }).catch(e => { note.textContent = 'No se pudo acceder a la cámara: ' + e.message; note.className = 'qt-scan-note err'; });
  } catch (e) { note.textContent = 'Lector no disponible: ' + e.message; note.className = 'qt-scan-note err'; }
}

// ── Ficha ─────────────────────────────────────────────────────────────────────
function gotoFicha(id, navIds) { S.nav = Array.isArray(navIds) ? navIds.slice() : []; viewFicha(id); }
function viewFicha(id, opts) {
  opts = opts || {};
  const it = S.byId.get(id) || S._extra && S._extra.get && S._extra.get(id);
  if (!it) { toast('No encontrado.', 'err'); return viewList(); }
  S.view = 'ficha'; S.currentItemId = id;
  if (!opts.justScanned) api('/item/' + id + '/touch', { method: 'POST' }).catch(() => {});
  const inCart = S.cart.has(id);
  const st = S.settings;
  const used = it.status === 'utilizado';
  const nav = (S.nav || []).filter(nid => S.byId.has(nid));
  const navIdx = nav.indexOf(id), hasNav = navIdx >= 0 && nav.length > 1;
  const navBar = hasNav ? `<div class="qt-navpair"><span class="qt-navpos">${navIdx + 1} / ${nav.length}</span><button class="qt-btn qt-btn-ghost qt-btn-sm" id="nav-prev" ${navIdx <= 0 ? 'disabled' : ''}>← Anterior</button><button class="qt-btn qt-btn-ghost qt-btn-sm" id="nav-next" ${navIdx >= nav.length - 1 ? 'disabled' : ''}>Siguiente →</button></div>` : '';
  const dmHtml = `<div class="qt-qr-box" id="ficha-dm">${dmSvg(it.raw, dmOpts(it, st.dm_size))}</div>`;
  main().innerHTML =
    `<div class="qt-ficha-top"><button class="qt-back" id="back">← ${opts.justScanned ? 'Escanear' : 'Volver'}</button>${navBar}</div>
     <div class="qt-panel qt-ficha">
       <div class="qt-qr-stage">
         <div class="qt-qr-name">${shapeSvg(it.shape, it.color, 20)} ${esc(it.nombre || 'Medicamento sin nombre')}</div>
         ${dmHtml}
         <div class="qt-qr-tis" style="font-size:1rem;letter-spacing:.06em">${it.serial ? 'Nº ' + esc(it.serial) : (it.gtin ? 'GTIN ' + esc(it.gtin) : '')}</div>
         ${mandoHtml(st, it)}
       </div>
       <div class="qt-ficha-info">
         <h2>${esc(it.nombre || 'Medicamento sin nombre')}</h2>
         <div class="qt-ficha-meta">Alta: ${fmtDate(it.created_at)} · ${used ? '<span style="color:var(--muted)">● Utilizada</span>' : '<span style="color:var(--ok)">● Sin utilizar</span>'}</div>
         ${it.asig_state ? `<div class="qt-ficha-meta">${asigBadge(it)}</div>` : ''}
         <div class="qt-kv">
           <div class="qt-kv-row"><span class="k">Medicamento</span><span class="v">${esc(it.nombre || '—')}</span></div>
           <div class="qt-kv-row"><span class="k">GTIN</span><span class="v mono">${esc(it.gtin || '—')}</span></div>
           <div class="qt-kv-row"><span class="k">Nº de serie</span><span class="v mono">${esc(it.serial || '—')}</span></div>
           <div class="qt-kv-row"><span class="k">Lote</span><span class="v mono">${esc(it.lote || '—')}</span></div>
           <div class="qt-kv-row"><span class="k">Caducidad</span><span class="v">${cadDisplay(it.caducidad)}</span></div>
           <div class="qt-kv-row"><span class="k">Código Nacional</span><span class="v mono">${esc(it.cn || '—')}</span></div>
         </div>
         <div id="prod-area"></div>
         <div class="qt-ficha-actions">
           ${used
        ? `<button class="qt-btn qt-btn-primary" id="act-unuse">↩ Devolver al inventario</button>`
        : `<button class="qt-btn qt-btn-teal" id="act-use">⬆ Marcar utilizada</button>`}
           <button class="qt-btn ${inCart ? 'qt-btn-ghost' : 'qt-btn-ghost'}" id="act-cart">${inCart ? '✓ En el carrito' : '🛒 Añadir al carrito'}</button>
           <button class="qt-btn qt-btn-ghost" id="act-prod">✏️ Nombre / color del medicamento</button>
           <button class="qt-btn qt-btn-ghost" id="act-list">☰ Ver inventario</button>
           <button class="qt-btn qt-btn-danger" id="act-del">🗑 Eliminar</button>
         </div>
         <details class="dm-raw-details"><summary>Ver contenido RAW</summary><code class="dm-raw-code">${esc(it.raw)}</code></details>
       </div>
     </div>`;
  $('back').onclick = opts.justScanned ? viewScan : viewList;
  $('act-list').onclick = viewList;
  if (hasNav) { if (navIdx > 0) $('nav-prev').onclick = () => viewFicha(nav[navIdx - 1]); if (navIdx < nav.length - 1) $('nav-next').onclick = () => viewFicha(nav[navIdx + 1]); }
  wireMando(it, () => { const box = $('ficha-dm'); if (box) box.innerHTML = dmSvg(it.raw, dmOpts(it, S.settings.dm_size)); });
  const useBtn = $('act-use'); if (useBtn) useBtn.onclick = async () => { await setUsed(it, true); viewList(); };
  const unBtn = $('act-unuse'); if (unBtn) unBtn.onclick = async () => { await setUsed(it, false); viewFicha(id, opts); };
  $('act-cart').onclick = async () => { await toggleCart(id); viewFicha(id, opts); };
  $('act-prod').onclick = () => editProduct(it);
  $('act-del').onclick = async () => { if (await removeItem(it)) viewList(); };
}

function editProduct(it) {
  const area = $('prod-area');
  const gtin = it.gtin;
  if (!gtin) { area.innerHTML = '<div class="dm-note">Esta caja no tiene GTIN; no se puede asociar un medicamento.</div>'; return; }
  const swatches = S.palette.slice(0, 12);
  area.innerHTML =
    `<div class="qt-group-mgr">
       <div class="qt-group-mgr-h">Medicamento (GTIN ${esc(gtin)}) — afecta a todas sus cajas</div>
       <div class="qt-field" style="margin:0 0 10px"><div class="dm-cima-row"><input class="qt-input" id="pm-nombre" placeholder="Nombre comercial del medicamento" value="${esc(it.nombre || '')}" maxlength="160"><button class="qt-btn qt-btn-ghost qt-btn-sm" id="pm-cima" title="Traer el nombre desde CIMA (AEMPS)${it.cn ? ' · CN ' + esc(it.cn) : ''}">🔎 CIMA</button></div>${it.cn ? '' : '<small class="dm-note" style="margin-top:4px">Esta caja no trae Código Nacional; escribe el nombre a mano.</small>'}</div>
       <div id="pm-fotos"></div>
       <div class="qt-mando-row"><label>Color</label><div class="qt-swatches" id="pm-swatches">${swatches.map(c => `<div class="qt-swatch${c === it.color ? ' sel' : ''}" data-c="${c}" style="background:${c}"></div>`).join('')}</div><input type="color" class="qt-color-input" id="pm-color" value="${it.color}"></div>
       <div class="qt-mando-row"><label>Forma</label><div class="qt-shape-picker" id="pm-shapes">${S.shapes.map(sh => `<button class="dm-shape-btn ${sh === it.shape ? 'sel' : ''}" data-s="${sh}" title="${sh}">${shapeSvg(sh, it.color, 20)}</button>`).join('')}</div></div>
       <div class="qt-group-inline"><button class="qt-btn qt-btn-primary qt-btn-sm" id="pm-save">Guardar</button></div>
     </div>`;
  const nombre = $('pm-nombre'); nombre.focus();
  const save = async (patch) => { try { await api('/product/' + encodeURIComponent(gtin), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) }); await reloadItems(); viewFicha(it.id); setTimeout(() => editProduct(S.byId.get(it.id) || it), 0); } catch (e) { toast(e.message, 'err'); } };
  $('pm-save').onclick = () => save({ nombre: nombre.value.trim() });
  nombre.addEventListener('keydown', e => { if (e.key === 'Enter') save({ nombre: nombre.value.trim() }); });
  // Fill the name from CIMA (AEMPS) using the box's Código Nacional.
  $('pm-cima').onclick = async () => {
    const cn = String(it.cn || '').replace(/\D/g, '');
    if (!/^\d{5,7}$/.test(cn)) { toast('Esta caja no trae un Código Nacional válido; escribe el nombre a mano.', 'err'); return; }
    const btn = $('pm-cima'); btn.disabled = true; const prev = btn.textContent; btn.textContent = '…';
    try {
      const { item } = await api('/cima/cn/' + cn);
      if (!item || !item.nombre) toast('CIMA no encontró ese Código Nacional.', 'err');
      else {
        nombre.value = item.nombre;
        const f = item.fotos || {};
        const fcn = item.cn || cn;
        const one = (x, tipo, lbl) => x ? `<a class="dm-cima-foto" href="${esc(x.full || (API + '/cima/foto/' + fcn + '/' + tipo))}" target="_blank" rel="noopener" title="Ver ${lbl} (AEMPS)"><img src="${esc(API + '/cima/foto/' + fcn + '/' + tipo)}" alt="${lbl}" loading="lazy" onerror="this.style.display='none'"><span>${lbl}</span></a>` : '';
        const fh = one(f.caja, 'caja', 'Caja') + one(f.pastilla, 'pastilla', 'Pastilla');
        const box = $('pm-fotos'); if (box) box.innerHTML = fh ? `<div class="dm-cima-fotos">${fh}</div><small class="dm-note" style="margin-top:2px">Imágenes: AEMPS · CIMA</small>` : '';
        toast('Nombre traído de CIMA (AEMPS). Pulsa «Guardar».', 'ok'); nombre.focus();
      }
    } catch (e) { toast((e.offline || (e.data && e.data.offline)) ? 'No se pudo consultar CIMA ahora; escribe el nombre a mano.' : e.message, 'err'); }
    finally { btn.disabled = false; btn.textContent = prev; }
  };
  $('pm-color').addEventListener('input', e => save({ color: e.target.value }));
  area.querySelectorAll('#pm-swatches .qt-swatch').forEach(sw => sw.addEventListener('click', () => save({ color: sw.dataset.c })));
  area.querySelectorAll('#pm-shapes .dm-shape-btn').forEach(b => b.addEventListener('click', () => save({ shape: b.dataset.s })));
}

// ── The "mando" (DM size global; colour/shape per medication via product) ────────
function mandoHtml(st, it) {
  return `<div class="qt-mando">
    <div class="qt-mando-h">⚙ Ajustes del Data Matrix</div>
    <div class="qt-mando-row"><label>Tamaño</label><input type="range" id="m-size" min="140" max="560" step="10" value="${st.dm_size}"><span class="qt-mando-note">compartido</span></div>
    <div class="qt-mando-row"><label>Fondo</label><input type="color" class="qt-color-input" id="m-light" value="${st.dm_light}"><span class="qt-mando-note">El color es por medicamento (arriba)</span></div>
  </div>`;
}
function wireMando(it, rerender) {
  $('m-size').addEventListener('input', e => { S.settings.dm_size = Number(e.target.value); rerender(); saveSettingsDebounced(); });
  $('m-light').addEventListener('input', e => { S.settings.dm_light = e.target.value; rerender(); saveSettingsDebounced(); });
}

// ── (2) Inventario ──────────────────────────────────────────────────────────────
const SORT_FIELDS = [
  { key: 'nombre', label: 'Medicamento' }, { key: 'gtin', label: 'GTIN' },
  { key: 'caducidad', label: 'Caducidad' }, { key: 'lote', label: 'Lote' },
  { key: 'serial', label: 'Nº de serie' },
];
function viewList() {
  S.view = 'list'; const st = S.settings;
  main().innerHTML =
    `<div class="qt-list-top">
       <button class="qt-back" id="back">← Inicio</button>
       <div class="qt-actions-bar">
         <button class="qt-action" id="a-scan"><span class="em">📥</span><span class="lbl">Escanear<small>entrada / salida</small></span></button>
         <button class="qt-action" id="a-io"><span class="em">📄</span><span class="lbl">Importar / Catálogo<small>cajas y nombres</small></span></button>
         <button class="qt-action" id="a-xlsx"><span class="em">📊</span><span class="lbl">Exportar Excel<small>elige campos y orden</small></span></button>
         <button class="qt-action" id="a-pdf"><span class="em">🖨️</span><span class="lbl">Exportar PDF<small>Data Matrix a tamaño</small></span></button>
         <button class="qt-action" id="a-recent"><span class="em">🕘</span><span class="lbl">Recientes<small>últimas 10</small></span></button>
       </div>
     </div>
     <div class="qt-section-title">${S.archive ? 'Medicación utilizada (archivo)' : 'Inventario · sin utilizar'}</div>
     <div class="qt-section-sub">Busca, agrupa por medicamento, ordena y usa el carrito. Pulsa una caja para ver su Data Matrix.</div>
     <div class="dm-invtabs"><button class="dm-tab ${S.archive ? '' : 'sel'}" data-arch="0">Sin utilizar (${S.counts.activo})</button><button class="dm-tab ${S.archive ? 'sel' : ''}" data-arch="1">Utilizadas (${S.counts.utilizado})</button></div>
     <div class="qt-search-wrap">
       <div class="qt-search"><span class="ico">🔎</span><input id="q" placeholder="Buscar por medicamento, GTIN, serie, lote, caducidad, CN…" value="${esc(S.query)}" autocomplete="off"></div>
       <div class="qt-andor" id="andor"><button data-v="AND" class="${S.andor === 'AND' ? 'sel' : ''}">AND</button><button data-v="OR" class="${S.andor === 'OR' ? 'sel' : ''}">OR</button></div>
     </div>
     ${S.medFilter ? `<div class="qt-groups-head" style="margin-bottom:10px"><button class="qt-groups-clear" id="med-clear">Medicamento: ${esc(medName(S.medFilter))} ✕</button></div>` : ''}
     <div class="qt-toolbar">
       <span class="qt-count" id="list-count"></span>
       <div class="qt-seg qt-mode" id="list-mode"><button data-m="table" class="${S.listMode !== 'cards' ? 'sel' : ''}">▤ Listado</button><button data-m="cards" class="${S.listMode === 'cards' ? 'sel' : ''}">▦ Tarjetas</button></div>
       ${S.listMode === 'cards' ? `<button class="qt-toggle ${S.groupBy ? 'on' : ''}" id="tg-group">🧬 Agrupar por medicamento</button>` : ''}
       ${S.listMode !== 'cards' ? `<button class="qt-toggle ${S.showListQr ? 'on' : ''}" id="tg-qr">▦ DM en el listado</button>` : ''}
       <span class="qt-inline-size" id="dm-size-wrap" ${(S.listMode === 'cards' || S.showListQr) ? '' : 'hidden'}>Tamaño DM <input type="range" id="list-dm-size" min="80" max="${S.listMode === 'cards' ? 220 : 360}" step="10" value="${S.listMode === 'cards' ? st.card_dm_size : st.list_dm_size}"><span id="list-dm-size-v">${S.listMode === 'cards' ? st.card_dm_size : st.list_dm_size}px</span></span>
       ${S.listMode === 'cards' && !S.groupBy ? `<span class="qt-inline-sort">Ordenar <select class="qt-select" id="cards-sort">${SORT_FIELDS.map(f => `<option value="${f.key}" ${S.sort.key === f.key ? 'selected' : ''}>${f.label}</option>`).join('')}</select><select class="qt-select" id="cards-dir"><option value="asc" ${S.sort.dir === 'asc' ? 'selected' : ''}>▲</option><option value="desc" ${S.sort.dir === 'desc' ? 'selected' : ''}>▼</option></select></span>` : ''}
       <button class="qt-toggle ${S.uncatOnly ? 'on' : ''}" id="tg-uncat" title="Medicamentos sin nombre (aún no catalogados)">🏷️ Sin catalogar (${S.items.filter(x => !x.nombre).length})</button>
       ${!S.archive ? `<button class="qt-toggle ${S.preasigOnly ? 'on' : ''}" id="tg-preasig" title="Cajas reservadas para una persona (desde Asignación)">🔗 Pre-asignadas (${S.items.filter(x => x.asig_state === 'preasignada').length})</button>` : ''}
       <button class="qt-toggle ${S.selectedOnly ? 'on' : ''}" id="tg-selected">✔ Solo seleccionadas</button>
       <button class="qt-toggle ${S.cartView ? 'on' : ''}" id="tg-cart">🛒 Solo carrito</button>
       <button class="qt-toggle" id="clear-sel">✕ Quitar selección</button>
       <button class="qt-toggle dm-danger" id="del-sel" ${S.selected.size ? '' : 'disabled'}>🗑 Eliminar sel. (${S.selected.size})</button>
     </div>
     <div id="hidden-note"></div>
     <div id="list-body"></div>`;
  $('back').onclick = viewHome;
  $('a-scan').onclick = viewScan;
  $('a-io').onclick = toolIO;
  $('a-xlsx').onclick = toolExportExcel;
  $('a-pdf').onclick = toolExportPdf;
  $('a-recent').onclick = toolRecent;
  main().querySelectorAll('[data-arch]').forEach(b => b.addEventListener('click', async () => { const arch = b.dataset.arch === '1'; if (arch === S.archive) return; S.archive = arch; S.medFilter = null; await reloadItems(); viewList(); }));
  const q = $('q'); q.addEventListener('input', () => { S.query = q.value; renderList(); });
  $('andor').querySelectorAll('button').forEach(b => b.addEventListener('click', () => { S.andor = b.dataset.v; $('andor').querySelectorAll('button').forEach(x => x.classList.toggle('sel', x === b)); renderList(); }));
  $('list-mode').querySelectorAll('button').forEach(b => b.addEventListener('click', () => { S.listMode = b.dataset.m; viewList(); }));
  if ($('tg-group')) $('tg-group').onclick = () => { S.groupBy = !S.groupBy; viewList(); };
  if ($('tg-qr')) $('tg-qr').onclick = () => { S.showListQr = !S.showListQr; viewList(); };
  $('tg-uncat').onclick = () => { S.uncatOnly = !S.uncatOnly; viewList(); };
  if ($('tg-preasig')) $('tg-preasig').onclick = () => { S.preasigOnly = !S.preasigOnly; viewList(); };
  $('tg-selected').onclick = () => { S.selectedOnly = !S.selectedOnly; viewList(); };
  $('tg-cart').onclick = () => { S.cartView = !S.cartView; viewList(); };
  $('clear-sel').onclick = () => { S.selected.clear(); renderList(); };
  $('del-sel').onclick = deleteSelected;
  if ($('med-clear')) $('med-clear').onclick = () => { S.medFilter = null; viewList(); };
  if ($('cards-sort')) { $('cards-sort').addEventListener('change', () => { S.sort.key = $('cards-sort').value; renderList(); }); $('cards-dir').addEventListener('change', () => { S.sort.dir = $('cards-dir').value; renderList(); }); }
  if ($('list-dm-size')) { const el = $('list-dm-size'); el.addEventListener('input', () => { const v = Number(el.value); if (S.listMode === 'cards') S.settings.card_dm_size = v; else S.settings.list_dm_size = v; $('list-dm-size-v').textContent = v + 'px'; saveSettingsDebounced(); renderList(); }); }
  renderList();
}
function medName(gtin) { const it = S.items.find(x => x.gtin === gtin); return it ? (it.nombre || gtin) : gtin; }

function filteredItems() {
  let rows = S.items.filter(p => !S.hidden.has(p.id));
  if (S.cartView) rows = rows.filter(p => S.cart.has(p.id));
  if (S.selectedOnly) rows = rows.filter(p => S.selected.has(p.id));
  if (S.medFilter) rows = rows.filter(p => p.gtin === S.medFilter);
  if (S.uncatOnly) rows = rows.filter(p => !p.nombre);
  if (S.preasigOnly) rows = rows.filter(p => p.asig_state === 'preasignada');
  const tokens = norm(S.query).split(/\s+/).filter(Boolean);
  if (tokens.length) rows = rows.filter(p => { const hay = norm([p.nombre, p.gtin, p.serial, p.lote, p.caducidad, p.cn, p.raw].join(' ')); return S.andor === 'OR' ? tokens.some(t => hay.includes(t)) : tokens.every(t => hay.includes(t)); });
  const { key, dir } = S.sort, mul = dir === 'asc' ? 1 : -1;
  rows.sort((a, b) => { const av = norm(a[key] == null ? '' : a[key]), bv = norm(b[key] == null ? '' : b[key]); return av.localeCompare(bv, 'es', { numeric: true }) * mul; });
  return rows;
}

function renderList() {
  const rows = filteredItems();
  $('list-count').textContent = `${rows.length} de ${S.items.length}` + (S.selected.size ? ` · ${S.selected.size} sel.` : '') + (S.hidden.size ? ` · ${S.hidden.size} oculta(s)` : '');
  const ds = $('del-sel'); if (ds) { ds.textContent = `🗑 Eliminar sel. (${S.selected.size})`; ds.disabled = !S.selected.size; }
  $('hidden-note').innerHTML = S.hidden.size ? `<div class="qt-hidden-note">👁 <strong>${S.hidden.size}</strong> oculta(s) temporalmente. <a id="unhide">Mostrar todas</a></div>` : '';
  if (S.hidden.size) $('unhide').onclick = () => { S.hidden.clear(); renderList(); };
  const body = $('list-body');
  if (!rows.length) { body.innerHTML = '<div class="qt-empty">No hay cajas que coincidan.</div>'; return; }
  if (S.listMode === 'cards' && S.groupBy) { body.innerHTML = `<div class="qt-pcards" style="--qrw:${S.settings.card_dm_size}px">${groupCardsHtml(rows)}</div>`; wireGroupCards(body); return; }
  if (S.listMode === 'cards') { body.innerHTML = `<div class="qt-pcards" style="--qrw:${S.settings.card_dm_size}px">${rows.map(itemCardHtml).join('')}</div>`; body.querySelectorAll('[data-sel]').forEach(cb => { cb.checked = S.selected.has(Number(cb.dataset.sel)); }); wireListItems(body); return; }
  body.innerHTML = `<div class="qt-table-wrap"><table class="qt-table"><thead>${headTr()}</thead><tbody>${rows.map(itemRowHtml).join('')}</tbody></table></div>`;
  wireHeadSort(body); wireListItems(body);
}

// Group cards: one per medication (GTIN) with count.
function groupCardsHtml(rows) {
  const groups = new Map();
  for (const it of rows) { const k = it.gtin || 'sin-gtin'; if (!groups.has(k)) groups.set(k, { gtin: it.gtin, sample: it, count: 0 }); groups.get(k).count++; }
  const arr = [...groups.values()].sort((a, b) => norm(a.sample.nombre || a.gtin).localeCompare(norm(b.sample.nombre || b.gtin), 'es', { numeric: true }));
  return arr.map(g => {
    const it = g.sample;
    return `<div class="qt-pcard dm-groupcard" data-med="${esc(g.gtin || '')}">
      <div class="qt-pcard-head"><span class="dm-medshape">${shapeSvg(it.shape, it.color, 22)}</span><span class="dm-count-badge" style="background:${it.color}">×${g.count}</span></div>
      <div class="qt-pcard-qr" data-med="${esc(g.gtin || '')}">${dmSvg(it.raw, dmOpts(it, S.settings.card_dm_size))}</div>
      <div class="qt-pcard-name">${esc(it.nombre || it.gtin || 'Sin nombre')}</div>
      <div class="qt-pcard-tis">${g.count} caja(s) · GTIN ${esc(it.gtin || '—')}</div>
      <div class="qt-pcard-groups"></div>
      <div class="qt-pcard-actions"><button class="qt-btn qt-btn-ghost qt-btn-sm" data-med="${esc(g.gtin || '')}">Ver las ${g.count} →</button></div>
    </div>`;
  }).join('');
}
function wireGroupCards(container) { container.querySelectorAll('[data-med]').forEach(el => el.addEventListener('click', () => { S.medFilter = el.dataset.med; S.groupBy = false; viewList(); })); }

function headTr() {
  // DM on the left, then the medication (name + CN), then the expiry. GTIN / serial
  // / lote / RAW are not shown here (they live in the ficha).
  const cols = [
    { key: 'sel', nosort: true }, { key: 'dm', label: 'DM', nosort: true },
    { key: 'nombre', label: 'Medicamento' }, { key: 'caducidad', label: 'Caducidad' },
    { key: 'act', nosort: true },
  ];
  return '<tr>' + cols.map(c => {
    if (c.nosort) return `<th class="no-sort">${c.label || ''}</th>`;
    const sorted = S.sort.key === c.key;
    return `<th data-key="${c.key}" class="${sorted ? 'sorted' : ''}">${c.label} <span class="arrow">${sorted ? (S.sort.dir === 'asc' ? '▲' : '▼') : '↕'}</span></th>`;
  }).join('') + '</tr>';
}
function wireHeadSort(container) { container.querySelectorAll('th[data-key]').forEach(th => th.addEventListener('click', () => { const k = th.dataset.key; if (S.sort.key === k) S.sort.dir = S.sort.dir === 'asc' ? 'desc' : 'asc'; else { S.sort.key = k; S.sort.dir = 'asc'; } renderList(); })); }

function itemActionsHtml(it, inCart) {
  const used = it.status === 'utilizado';
  return `<button class="qt-iconbtn" data-cart="${it.id}" title="${inCart ? 'Quitar del carrito' : 'Añadir al carrito'}">${inCart ? '✓🛒' : '🛒'}</button>
    <button class="qt-iconbtn" data-used="${it.id}" data-to="${used ? '0' : '1'}" title="${used ? 'Devolver al inventario' : 'Marcar utilizada'}">${used ? '↩' : '⬆'}</button>
    <button class="qt-iconbtn" data-hide="${it.id}" title="Ocultar (temporal)">👁</button>
    <button class="qt-iconbtn danger" data-del="${it.id}" title="Eliminar">🗑</button>`;
}
function itemRowHtml(it) {
  const sel = S.selected.has(it.id), inCart = S.cart.has(it.id);
  return `<tr class="${sel ? 'is-selected' : ''}" data-id="${it.id}">
    <td><input type="checkbox" class="qt-check" data-sel="${it.id}" ${sel ? 'checked' : ''}></td>
    <td class="dm-td-dm"><span class="qt-list-qr" data-open="${it.id}">${dmSvg(it.raw, dmOpts(it, S.settings.list_dm_size))}</span></td>
    <td class="dm-td-name">
      <span class="dm-name-2l" data-open="${it.id}" title="${esc(it.nombre || 'Sin nombre')}">${shapeSvg(it.shape, it.color, 13)} <span class="qt-cell-name">${esc(it.nombre || 'Sin nombre')}</span></span>
      <span class="dm-cell-cn">${it.cn ? 'CN ' + esc(it.cn) : ''}${asigBadge(it) ? ' ' + asigBadge(it) : ''}</span>
    </td>
    <td class="dm-td-cad">${cadDisplay(it.caducidad)}</td>
    <td><div class="qt-cell-actions">${itemActionsHtml(it, inCart)}</div></td>
  </tr>`;
}
function itemCardHtml(it) {
  const sel = S.selected.has(it.id), inCart = S.cart.has(it.id);
  return `<div class="qt-pcard ${sel ? 'is-selected' : ''}" data-id="${it.id}" style="border-top:3px solid ${it.color}">
    <div class="qt-pcard-head"><input type="checkbox" class="qt-check" data-sel="${it.id}"><span class="dm-medshape">${shapeSvg(it.shape, it.color, 18)}</span><span class="dm-card-cad" style="margin-left:auto">${cadDisplay(it.caducidad)}</span></div>
    <span class="qt-pcard-qr" data-open="${it.id}">${dmSvg(it.raw, dmOpts(it, S.settings.card_dm_size))}</span>
    <div class="qt-pcard-name" data-open="${it.id}">${esc(it.nombre || 'Sin nombre')}</div>
    <div class="qt-pcard-tis">${it.serial ? 'Nº ' + esc(it.serial) : ('GTIN ' + esc(it.gtin || '—'))}</div>
    <div class="qt-pcard-groups">${asigBadge(it)}</div>
    <div class="qt-pcard-actions">${itemActionsHtml(it, inCart)}</div>
  </div>`;
}
function wireListItems(container) {
  container.querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => gotoFicha(Number(el.dataset.open), filteredItems().map(x => x.id))));
  container.querySelectorAll('[data-sel]').forEach(cb => cb.addEventListener('change', () => { const id = Number(cb.dataset.sel); if (cb.checked) S.selected.add(id); else S.selected.delete(id); renderList(); }));
  container.querySelectorAll('[data-cart]').forEach(b => b.addEventListener('click', async () => { await toggleCart(Number(b.dataset.cart)); renderList(); }));
  container.querySelectorAll('[data-used]').forEach(b => b.addEventListener('click', async () => { const it = S.byId.get(Number(b.dataset.used)); await setUsed(it, b.dataset.to === '1'); await reloadItems(); if (S.view === 'list') renderList(); }));
  container.querySelectorAll('[data-hide]').forEach(b => b.addEventListener('click', () => { S.hidden.add(Number(b.dataset.hide)); renderList(); }));
  container.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', async () => { const it = S.byId.get(Number(b.dataset.del)); if (await removeItem(it)) renderList(); }));
}

// ── Shared actions ─────────────────────────────────────────────────────────────
async function toggleCart(id) { try { const path = '/cart/' + id; const { ids } = await api(path, { method: S.cart.has(id) ? 'DELETE' : 'POST' }); S.cart = new Set(ids); updateCartCount(); if ($('cart-panel').classList.contains('open')) renderCart(); } catch (e) { toast(e.message, 'err'); } }
async function setUsed(it, used) {
  try {
    const { item } = await api('/item/' + it.id + '/used', jbody({ used }));
    toast(used ? 'Marcada utilizada' : 'Devuelta al inventario', 'ok');
    S.counts = (await api('/items?status=' + (S.archive ? 'utilizado' : 'activo'))).counts || S.counts;
  } catch (e) { toast(e.message, 'err'); }
}
async function removeItem(it) {
  if (!(await confirmBox('Eliminar caja', `¿Eliminar esta caja${it.nombre ? ' de «' + it.nombre + '»' : ''}? No se puede deshacer.`, 'Eliminar'))) return false;
  try { await api('/item/' + it.id, { method: 'DELETE' }); S.cart.delete(it.id); S.selected.delete(it.id); updateCartCount(); await reloadItems(); toast('Eliminada', 'ok'); return true; } catch (e) { toast(e.message, 'err'); return false; }
}
async function deleteSelected() {
  const ids = [...S.selected];
  if (!ids.length) return;
  if (!(await confirmBox('Eliminar seleccionadas', `Se eliminarán ${ids.length} caja(s) por completo de la base de datos. No se puede deshacer.`, 'Eliminar'))) return;
  try {
    const { deleted } = await api('/items/delete', jbody({ ids }));
    ids.forEach(id => { S.selected.delete(id); S.cart.delete(id); });
    updateCartCount(); await reloadItems();
    toast(`${deleted} caja(s) eliminada(s)`, 'ok'); viewList();
  } catch (e) { toast(e.message, 'err'); }
}

// ── Cart ───────────────────────────────────────────────────────────────────────
function openCart() { $('cart-panel').classList.add('open'); $('scrim').hidden = false; renderCart(); }
function closeCart() { $('cart-panel').classList.remove('open'); $('scrim').hidden = true; }
function renderCart() {
  const panel = $('cart-panel'); const items = S.items.filter(p => S.cart.has(p.id)); const st = S.settings;
  const size = Math.max(150, Math.min(210, st.card_dm_size)); const selInCart = items.filter(p => S.selected.has(p.id)).length;
  panel.innerHTML =
    `<div class="qt-cart-head"><h2>🛒 Carrito</h2><span style="color:var(--muted);font-size:.9rem">${items.length}</span><button class="qt-x" id="cart-x">×</button></div>
     <div class="qt-cart-tools"><button class="qt-btn qt-btn-ghost qt-btn-sm" id="cart-hide">Ocultar</button><button class="qt-btn qt-btn-ghost qt-btn-sm" id="cart-selall">Seleccionar todos (${selInCart}/${items.length})</button><button class="qt-btn qt-btn-ghost qt-btn-sm" id="cart-list">Ver en listado</button><button class="qt-btn qt-btn-danger qt-btn-sm" id="cart-empty" ${items.length ? '' : 'disabled'}>Vaciar</button></div>
     <div class="qt-cart-body" id="cart-body"></div>`;
  $('cart-x').onclick = closeCart; $('cart-hide').onclick = closeCart;
  $('cart-list').onclick = () => { S.cartView = true; closeCart(); viewList(); };
  $('cart-selall').onclick = () => { const all = items.every(p => S.selected.has(p.id)); items.forEach(p => all ? S.selected.delete(p.id) : S.selected.add(p.id)); renderCart(); if (S.view === 'list') renderList(); };
  $('cart-empty').onclick = async () => { if (!(await confirmBox('Vaciar carrito', '¿Vaciar el carrito?', 'Vaciar'))) return; try { const { ids } = await api('/cart', { method: 'DELETE' }); S.cart = new Set(ids); updateCartCount(); renderCart(); if (S.view === 'list') renderList(); } catch (e) { toast(e.message, 'err'); } };
  const body = $('cart-body');
  if (!items.length) { body.innerHTML = '<div class="qt-empty">El carrito está vacío.</div>'; return; }
  body.innerHTML = items.map(it => {
    const sel = S.selected.has(it.id);
    return `<div class="qt-cart-card ${sel ? 'is-selected' : ''}"><span class="qr" data-open="${it.id}">${dmSvg(it.raw, dmOpts(it, size))}</span>
      <div class="info"><div class="nm" data-open="${it.id}">${shapeSvg(it.shape, it.color, 15)} ${esc(it.nombre || it.gtin || 'Caja')}</div>
      <div class="ts">${it.serial ? 'Nº ' + esc(it.serial) + ' · ' : ''}Cad ${fmtDate(it.caducidad) || '—'}</div>
      <label style="display:inline-flex;align-items:center;gap:6px;margin-top:8px;font-size:.82rem;cursor:pointer"><input type="checkbox" class="qt-check" data-sel="${it.id}" ${sel ? 'checked' : ''}> Seleccionar</label>
      <button class="qt-iconbtn danger" data-remove="${it.id}" title="Sacar del carrito" style="margin-left:8px">✕</button></div></div>`;
  }).join('');
  body.querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => { closeCart(); gotoFicha(Number(el.dataset.open), items.map(x => x.id)); }));
  body.querySelectorAll('[data-sel]').forEach(cb => cb.addEventListener('change', () => { const id = Number(cb.dataset.sel); if (cb.checked) S.selected.add(id); else S.selected.delete(id); renderCart(); if (S.view === 'list') renderList(); }));
  body.querySelectorAll('[data-remove]').forEach(b => b.addEventListener('click', async () => { await toggleCart(Number(b.dataset.remove)); renderCart(); if (S.view === 'list') renderList(); }));
}

// ── Tools: import/catalog, export Excel/PDF, recientes ───────────────────────────
function openModal(html) { const box = $('tool-modal-box'); box.innerHTML = html; $('tool-modal').hidden = false; box.querySelectorAll('[data-close]').forEach(b => b.onclick = closeModal); }
function closeModal() { $('tool-modal').hidden = true; $('tool-modal-box').innerHTML = ''; }

const EXPORT_COLS = [
  { key: 'nombre', label: 'Medicamento', def: true, get: it => it.nombre || '' },
  { key: 'gtin', label: 'GTIN', def: true, text: true, get: it => String(it.gtin || '') },
  { key: 'serial', label: 'Nº de serie', def: true, text: true, get: it => String(it.serial || '') },
  { key: 'lote', label: 'Lote', def: true, get: it => it.lote || '' },
  { key: 'caducidad', label: 'Caducidad', def: true, get: it => it.caducidad || '' },
  { key: 'cn', label: 'Código Nacional', def: false, text: true, get: it => String(it.cn || '') },
  { key: 'status', label: 'Estado', def: false, get: it => it.status === 'utilizado' ? 'Utilizada' : 'Sin utilizar' },
  { key: 'raw', label: 'RAW', def: false, get: it => it.raw || '' },
];
function scopeItems(scope) { if (scope === 'selected') return S.items.filter(p => S.selected.has(p.id)); if (scope === 'all') return S.items.slice(); return filteredItems(); }
const scopeHtml = id => `<div class="qt-tool-row"><label>Cajas:</label><select class="qt-select" id="${id}"><option value="filtered">Las que se ven (${filteredItems().length})</option><option value="selected">Solo seleccionadas (${S.selected.size})</option><option value="all">Todas (${S.items.length})</option></select></div>`;

function toolIO() {
  openModal(
    `<div class="qt-modal-h"><h3>Importar / Catálogo</h3><button class="qt-x" data-close>×</button></div>
     <div class="qt-tool-opt"><h4>Catálogo de medicamentos (código → nombre)</h4>
       <p>Sube el listado de artículos de <b>Farmatic</b> (o Bot PLUS) en Excel/CSV. Necesita la <code>Descripción</code> y, al menos, el <code>Código de barras</code> (EAN/GTIN) <b>o</b> el <code>Código Nacional</code> (si solo tienes el CN, la app reconstruye el GTIN). Al escanear una caja el nombre se rellena por su código; <b>re-importa cuando cambie</b> y se actualiza en todas las cajas.</p>
       <button class="qt-btn qt-btn-ghost" id="cat-tpl">⬇ Plantilla catálogo</button>
       <div class="qt-dropfile" id="cat-drop" style="margin-top:10px">📥 Importar catálogo (.xlsx / .csv)</div>
       <input type="file" id="cat-file" accept=".xlsx,.xls,.csv" hidden>
       <div class="qt-import-report" id="cat-report"></div>
     </div>
     <div class="qt-tool-opt"><h4>Importar cajas (por su RAW)</h4>
       <p>Sube un Excel con una columna <code>RAW</code> (el contenido de cada Data Matrix). Se dan de alta como «sin utilizar»; los duplicados se avisan y se omiten.</p>
       <button class="qt-btn qt-btn-ghost" id="box-tpl">⬇ Plantilla cajas</button>
       <div class="qt-dropfile" id="box-drop" style="margin-top:10px">📥 Importar cajas (.xlsx / .csv)</div>
       <input type="file" id="box-file" accept=".xlsx,.xls,.csv" hidden>
       <div class="qt-import-report" id="box-report"></div>
     </div>`
  );
  $('cat-tpl').onclick = () => dlSheet([['Código de barras', 'Código Nacional', 'Descripción'], ['8470006991545', '699154', 'Ibuprofeno 600 mg 40 comprimidos'], ['8470008123456', '812345', 'Paracetamol 1 g 40 comprimidos']], 'Catalogo_medicamentos.xlsx', [0, 1]);
  $('box-tpl').onclick = () => { const GS = String.fromCharCode(29); dlSheet([['RAW'], ['0108470006991545' + '21SN0001' + GS + '17261130' + '10LOTE1']], 'Plantilla_cajas.xlsx', [0]); };
  wireDrop('cat-drop', 'cat-file', importCatalog);
  wireDrop('box-drop', 'box-file', importBoxes);
}
function wireDrop(dropId, fileId, fn) { const d = $(dropId), f = $(fileId); d.onclick = () => f.click(); d.ondragover = e => { e.preventDefault(); d.classList.add('drag'); }; d.ondragleave = () => d.classList.remove('drag'); d.ondrop = e => { e.preventDefault(); d.classList.remove('drag'); if (e.dataTransfer.files[0]) fn(e.dataTransfer.files[0]); }; f.onchange = () => { if (f.files[0]) fn(f.files[0]); }; }
function dlSheet(aoa, name, textCols) { const ws = XLSX.utils.aoa_to_sheet(aoa); if (textCols) for (let r = 1; r < aoa.length; r++) for (const c of textCols) { const cell = ws[XLSX.utils.encode_cell({ r, c })]; if (cell) { cell.t = 's'; cell.z = '@'; } } const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Datos'); XLSX.writeFile(wb, name); }
function readSheet(file) { return new Promise((resolve, reject) => { const fr = new FileReader(); fr.onload = e => { try { const wb = XLSX.read(new Uint8Array(e.target.result), { type: 'array' }); resolve(XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header: 1, raw: false, defval: '' })); } catch (err) { reject(new Error('No se pudo leer el Excel.')); } }; fr.onerror = () => reject(new Error('No se pudo leer el fichero.')); fr.readAsArrayBuffer(file); }); }
async function importCatalog(file) {
  const rep = $('cat-report'); rep.innerHTML = 'Leyendo…';
  try {
    const aoa = await readSheet(file); const header = aoa[0].map(h => norm(String(h)));
    // Barcode column (Farmatic: «Código de barras» / EAN); it IS the GTIN.
    const gi = header.findIndex(h => h.includes('barra') || h.includes('barcode') || h.includes('ean') || h.includes('gtin') || h.includes('codbar'));
    // Name column (Farmatic uses «Descripción»).
    const ni = header.findIndex(h => h.includes('descrip') || h.includes('nombre') || h.includes('articulo') || h.includes('denomin') || h.includes('medic'));
    // Optional Código Nacional.
    const ci = header.findIndex(h => (h.includes('nacional') || /(^|\W)cn(\W|$)/.test(h) || h.includes('cod nac') || h.includes('codnac')) && !h.includes('barra'));
    if (ni < 0 || (gi < 0 && ci < 0)) throw new Error('Faltan columnas. Necesito la «Descripción» (nombre) y, al menos, el «Código de barras» (EAN/GTIN) o el «Código Nacional».');
    const rows = aoa.slice(1).map(r => ({
      gtin: gi >= 0 ? String(r[gi] || '').replace(/\D/g, '') : '',
      cn: ci >= 0 ? String(r[ci] || '').replace(/\D/g, '') : '',
      nombre: String(r[ni] || '').trim(),
    })).filter(r => r.gtin.replace(/^0+/, '').length >= 8 || r.cn.length >= 4);
    if (!rows.length) throw new Error('No hay filas con código de barras o Código Nacional válidos.');
    const res = await api('/products/import', jbody({ rows }));
    await reloadItems(); rep.innerHTML = `<div class="ok">✓ ${res.imported} medicamento(s) en el catálogo${res.skipped ? `, ${res.skipped} sin código válido omitidos` : ''}. Los nombres se aplican a todas sus cajas.</div>`;
    toast('Catálogo importado', 'ok');
  } catch (e) { rep.innerHTML = `<div class="err">✕ ${esc(e.message)}</div>`; }
}
async function importBoxes(file) {
  const rep = $('box-report'); rep.innerHTML = 'Leyendo…';
  try {
    const aoa = await readSheet(file); const header = aoa[0].map(h => norm(String(h)));
    let ri = header.findIndex(h => h.includes('raw') || h.includes('data') || h.includes('codigo')); if (ri < 0) ri = 0;
    const rows = aoa.slice(1).map((r, i) => ({ __row: i + 2, raw: String(r[ri] || '').trim() })).filter(r => r.raw);
    if (!rows.length) throw new Error('No hay filas con datos.');
    rep.innerHTML = `Importando ${rows.length}…`;
    const res = await api('/import', jbody({ rows })); await reloadItems();
    let html = `<div class="ok">✓ ${res.created} caja(s) importada(s)${res.errors.length ? `, ${res.errors.length} con error/duplicado` : ''}.</div>`;
    if (res.errors.length) html += `<div class="qt-import-errs">${res.errors.map(e => `<div class="err">Fila ${e.row}: ${esc(e.error)}</div>`).join('')}</div>`;
    html += `<div style="margin-top:12px"><button class="qt-btn qt-btn-primary" id="box-done">Ver inventario</button></div>`;
    rep.innerHTML = html; $('box-done').onclick = () => { closeModal(); viewList(); }; toast(`${res.created} importada(s)`, 'ok');
  } catch (e) { rep.innerHTML = `<div class="err">✕ ${esc(e.message)}</div>`; }
}

function toolExportExcel() {
  const cols = EXPORT_COLS.map(c => `<label class="qt-check-row"><input type="checkbox" data-col="${c.key}" ${c.def ? 'checked' : ''}> ${c.label}</label>`).join('');
  const sortOpts = EXPORT_COLS.filter(c => c.key !== 'raw').map(c => `<option value="${c.key}" ${c.key === S.sort.key ? 'selected' : ''}>${c.label}</option>`).join('');
  openModal(`<div class="qt-modal-h"><h3>Exportar a Excel</h3><button class="qt-x" data-close>×</button></div>
    <p style="color:var(--muted);font-size:.88rem">Elige columnas, orden y qué cajas.</p><div class="qt-field-grid">${cols}</div>
    <div class="qt-tool-row"><label>Ordenar por:</label><select class="qt-select" id="ex-sort">${sortOpts}</select><select class="qt-select" id="ex-dir"><option value="asc">Ascendente</option><option value="desc">Descendente</option></select></div>
    ${scopeHtml('ex-scope')}
    <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" data-close>Cancelar</button><button class="qt-btn qt-btn-primary" id="ex-go">⬇ Descargar Excel</button></div>`);
  $('ex-go').onclick = () => {
    const chosen = EXPORT_COLS.filter(c => $('tool-modal-box').querySelector(`[data-col="${c.key}"]`).checked);
    if (!chosen.length) { toast('Elige al menos una columna.', 'err'); return; }
    let items = scopeItems($('ex-scope').value);
    const key = $('ex-sort').value, dir = $('ex-dir').value, mul = dir === 'desc' ? -1 : 1;
    items = items.slice().sort((a, b) => norm(a[key] == null ? '' : a[key]).localeCompare(norm(b[key] == null ? '' : b[key]), 'es', { numeric: true }) * mul);
    if (!items.length) { toast('No hay cajas que exportar.', 'err'); return; }
    const aoa = [chosen.map(c => c.label)]; items.forEach(it => aoa.push(chosen.map(c => c.get(it))));
    const ws = XLSX.utils.aoa_to_sheet(aoa);
    chosen.forEach((c, ci) => { if (c.text) for (let r = 1; r <= items.length; r++) { const cell = ws[XLSX.utils.encode_cell({ r, c: ci })]; if (cell) { cell.t = 's'; cell.z = '@'; } } });
    const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Inventario'); XLSX.writeFile(wb, `DataMatrix_${stamp()}.xlsx`);
    closeModal(); toast('Excel generado', 'ok');
  };
}
function toolExportPdf() {
  openModal(`<div class="qt-modal-h"><h3>Exportar PDF de Data Matrix</h3><button class="qt-x" data-close>×</button></div>
    <p style="color:var(--muted);font-size:.88rem">Hoja imprimible con los Data Matrix (color por medicamento) y sus datos.</p>
    <div class="qt-tool-row"><label>Título:</label><input class="qt-select" style="flex:1" id="pdf-title" value="Inventario Data Matrix" maxlength="120"></div>
    <div class="qt-tool-row" style="align-items:center"><label>Tamaño:</label><input type="range" id="pdf-size" min="70" max="280" step="10" value="150" style="flex:1;accent-color:var(--brand)"><span id="pdf-size-v" style="font-family:var(--mono);font-weight:700;color:var(--brand-2)">150</span></div>
    ${scopeHtml('pdf-scope')}
    <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" data-close>Cancelar</button><button class="qt-btn qt-btn-primary" id="pdf-go">⬇ Descargar PDF</button></div>`);
  const sz = $('pdf-size'); sz.oninput = () => { $('pdf-size-v').textContent = sz.value; };
  $('pdf-go').onclick = async () => {
    const items = scopeItems($('pdf-scope').value); if (!items.length) { toast('No hay cajas.', 'err'); return; }
    const btn = $('pdf-go'); btn.disabled = true; btn.textContent = 'Generando…';
    try { const blob = await apiBlob('/export/pdf', { ids: items.map(i => i.id), dm_size: Number(sz.value), title: $('pdf-title').value }); downloadBlob(blob, `DataMatrix_${stamp()}.pdf`); closeModal(); toast('PDF generado', 'ok'); } catch (e) { toast(e.message, 'err'); btn.disabled = false; btn.textContent = '⬇ Descargar PDF'; }
  };
}
async function toolRecent() {
  openModal(`<div class="qt-modal-h"><h3>Últimas 10 manejadas</h3><button class="qt-x" data-close>×</button></div><div id="recent-body">Cargando…</div>`);
  try {
    const { items } = await api('/recent');
    if (!items.length) { $('recent-body').innerHTML = '<div class="qt-empty">Nada reciente.</div>'; return; }
    $('recent-body').innerHTML = `<div class="qt-recent-list">${items.map(it => `<div class="qt-recent-item" data-open="${it.id}">${shapeSvg(it.shape, it.color, 16)}<span class="nm">${esc(it.nombre || it.gtin || 'Caja')}</span><span class="ts">${esc(it.serial || '')}</span><span class="when">Cad ${fmtDate(it.caducidad) || '—'}</span></div>`).join('')}</div>`;
    $('recent-body').querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => { closeModal(); gotoFicha(Number(el.dataset.open), items.map(x => x.id)); }));
  } catch (e) { $('recent-body').innerHTML = `<div class="err" style="color:var(--danger)">${esc(e.message)}</div>`; }
}

// ── Manual ───────────────────────────────────────────────────────────────────────
function viewHelp() {
  S.view = 'help';
  const SECS = [
    { id: 'inicio', icon: '🚀', title: 'Qué es', html: `<p>Un inventario de <b>cajas de medicación</b> por su <b>Data Matrix</b>. Escaneas para dar entrada, marcas la salida cuando se usa, y la app te dice qué queda sin utilizar. La información (medicamento, GTIN, nº de serie, lote, caducidad, código nacional) se extrae del propio Data Matrix (GS1).</p>` },
    { id: 'escanear', icon: '📥', title: 'Escanear (entrada y salida)', html: `<p>En <b>Escanear</b> eliges el modo:</p><ul><li><b>Entrada</b>: cada código añade una caja al inventario (queda «sin utilizar»).</li><li><b>Salida</b>: cada código marca esa caja como <b>utilizada</b> (sale del inventario y de las búsquedas).</li></ul><div class="qt-note tip">Con un <b>lector de sobremesa</b> (tipo teclado), haz clic en el campo y escanea; se procesa al pulsar Enter y el foco se queda listo para el siguiente. En móvil, usa el botón 📷.</div>` },
    { id: 'campos', icon: '🔢', title: 'Los datos del Data Matrix', html: `<p>Del código GS1 se extraen: <b>GTIN</b> (identifica el producto), <b>Nº de serie</b> (único por caja), <b>Lote</b>, <b>Caducidad</b> y <b>Código Nacional</b>. El <b>nombre comercial</b> no va en el código: se toma del <b>catálogo GTIN→nombre</b> (importable) o lo escribes en la ficha.</p><div class="qt-note">Los códigos <b>nunca se repiten por completo</b> (el nº de serie los hace únicos). Si reescaneas una caja ya metida, se avisa.</div>` },
    { id: 'usar', icon: '⬆', title: 'Marcar utilizada', html: `<p>Una caja se marca utilizada de tres formas: en modo <b>Salida</b> del escáner, con el botón <b>⬆</b> del listado, o desde su ficha. Al hacerlo <b>sale del inventario</b>; puedes verla en la pestaña <b>«Utilizadas»</b> y devolverla si te equivocaste.</p>` },
    { id: 'cima', icon: '🔎', title: 'Nombre e imágenes desde CIMA (AEMPS)', html: `<p>En la ficha de una caja, el botón <b>«🔎 CIMA»</b> trae el <b>nombre comercial</b> desde la base oficial de medicamentos (AEMPS) usando el <b>Código Nacional</b> de la caja, y muestra la <b>foto de la caja y de la pastilla</b>. Es una comodidad: si CIMA no está disponible o la caja no trae Código Nacional, escribe el nombre a mano. Lo consultado se <b>guarda en local</b> (datos + imágenes), así que sigue disponible aunque luego CIMA no lo esté. (Requiere que el servidor tenga salida hacia <i>cima.aemps.es</i>.)</p>` },
    { id: 'preasig', icon: '🔗', title: 'Pre-asignadas (Asignación)', html: `<p>Desde la app <b>Asignación de medicación</b> una caja puede quedar <b>🔗 Pre-asignada</b> a una persona: sigue <b>en stock</b> (sin utilizar) pero reservada para ella. Se muestra con una etiqueta en el listado, las tarjetas y la ficha, y el filtro <b>🔗 Pre-asignadas (N)</b> las agrupa. Cuando allí se <b>asigna de verdad</b>, la caja pasa a <b>utilizada</b> (✓ Asignada) igual que una salida normal.</p>` },
    { id: 'dm', icon: '🎨', title: 'Data Matrix y colores por medicamento', html: `<p>Cada <b>medicamento</b> recibe un <b>color y una forma</b> propios (automáticos, editables) para asociarlo de un vistazo — todas las cajas del mismo medicamento comparten color. En la ficha, «Nombre / color del medicamento» cambia el nombre, el color y la forma de todas sus cajas. El <b>tamaño</b> del Data Matrix es un ajuste compartido.</p>` },
    { id: 'agrupar', icon: '🧬', title: 'Agrupar por medicamento', html: `<p>En vista <b>Tarjetas</b>, el botón <b>«Agrupar por medicamento»</b> junta las cajas del mismo producto en una sola tarjeta con el <b>recuento</b> (cuántas quedan). Pulsa «Ver las N» para desglosarlas.</p>` },
    { id: 'buscar', icon: '🔎', title: 'Buscar', html: `<p>Busca por <b>medicamento, GTIN, nº de serie, lote, caducidad o código nacional</b> (sin tildes). <b>AND</b> exige todas las palabras; <b>OR</b>, cualquiera.</p>` },
    { id: 'resto', icon: '🗂️', title: 'Listado/tarjetas, carrito, importar y exportar', html: `<p>Como en QR (TIS): conmutador <b>Listado/Tarjetas</b>, ordenar, seleccionar, ocultar (temporal), <b>eliminar</b> (borrado permanente: una a una con 🗑, o en lote con «🗑 Eliminar sel.») y <b>carrito</b> propio. Arriba a la derecha: <b>Importar</b> (catálogo GTIN→nombre y cajas por RAW), <b>Exportar Excel</b> (elige columnas/orden), <b>Exportar PDF</b> (Data Matrix a tamaño variable, con su color) y <b>Recientes</b>.</p><div class="qt-note tip">Las <b>caducadas</b> ⚠ y las <b>próximas a caducar</b> ⏳ (≤ 90 días) se resaltan. El filtro <b>🏷️ Sin catalogar (N)</b> muestra los medicamentos que aún no tienen nombre, para nombrarlos en su ficha o re-importar el catálogo.</div>` },
  ];
  const nav = SECS.map(s => `<a data-go="help-${s.id}">${s.icon} ${s.title}</a>`).join('');
  const secs = SECS.map(s => `<section class="qt-help-sec" id="help-${s.id}"><h2><span class="em">${s.icon}</span>${s.title}</h2>${s.html}</section>`).join('');
  main().innerHTML = `<button class="qt-back" id="back">← Volver</button><div class="qt-help-hero"><h1>Manual · Gestor de Data Matrix</h1><p>Todo lo que puedes hacer, paso a paso.</p></div><div class="qt-help-wrap"><nav class="qt-help-nav">${nav}</nav><div class="qt-help-content">${secs}</div></div>`;
  $('back').onclick = () => (S.currentItemId ? viewList() : viewHome());
  main().querySelectorAll('.qt-help-nav [data-go]').forEach(a => a.addEventListener('click', () => { const el = document.getElementById(a.dataset.go); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }));
  window.scrollTo({ top: 0 });
}

// ── UI state persistence (survive navigation between apps) ──────────────────────
// Keep the same filtered list / selection when going Data Matrix → otra app → back,
// instead of resetting to «todas las cajas». Per-browser, in localStorage.
const UI_KEY = 'dm_ui';
function persistState() {
  try {
    localStorage.setItem(UI_KEY, JSON.stringify({
      view: S.view, query: S.query, andor: S.andor, sort: S.sort,
      listMode: S.listMode, groupBy: S.groupBy, archive: S.archive,
      uncatOnly: S.uncatOnly, preasigOnly: S.preasigOnly, medFilter: S.medFilter,
      selected: [...S.selected], hidden: [...S.hidden], currentItemId: S.currentItemId,
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
    S.groupBy = !!s.groupBy; S.archive = !!s.archive; S.uncatOnly = !!s.uncatOnly; S.preasigOnly = !!s.preasigOnly;
    S.medFilter = (typeof s.medFilter === 'string' && s.medFilter) ? s.medFilter : null;
    if (Array.isArray(s.selected)) S.selected = new Set(s.selected.filter(id => S.byId.has(id)));
    if (Array.isArray(s.hidden)) S.hidden = new Set(s.hidden.filter(id => S.byId.has(id)));
    if (s.currentItemId && S.byId.has(s.currentItemId)) S.currentItemId = s.currentItemId;
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
    S.settings = meta.settings; S.user = meta.user; S.counts = meta.counts || S.counts; S.palette = meta.palette || []; S.shapes = meta.shapes || [];
    await reloadItems(); await reloadCart();
    const saved = restoreState();
    if (new URLSearchParams(location.search).has('help')) viewHelp();
    else if (saved && saved.view === 'ficha' && S.currentItemId && S.byId.has(S.currentItemId)) viewFicha(S.currentItemId);
    else if (saved && saved.view === 'list') viewList();
    else viewHome();
  } catch (e) { main().innerHTML = `<div class="qt-panel"><p style="color:var(--danger)">No se pudo cargar la app: ${esc(e.message)}</p></div>`; }
})();
