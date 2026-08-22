'use strict';

// ── Asignación de medicación — frontend SPA ──────────────────────────────────────
// Bridges people (qr-tis) and medication boxes (datamatrix). Flow:
//   1) pick a person (must exist in QR-TIS)  2) build/keep their medication plan
//   3) each month, pre-assign real boxes (reserve them) and, when dispensing in the
//      external health app, click each Data Matrix to "Asignar" (mark it utilizado).
// QR codes render with qrcode-generator; Data Matrix with bwip-js; scanning ZXing.

const API = '/asignacion/api';
const $ = id => document.getElementById(id);
const main = () => $('qt-main');

const S = {
  settings: null, qrSettings: null, month: null, user: null,
  view: 'home',
  overview: [], overviewQuery: '',
  search: [], searchQuery: '',
  person: null, ficha: null, ym: null,
  notif: { due: [], upcoming: [], counts: { due: 0, upcoming: 0 }, today: null },
  peopleFilter: null,   // when set (array of ids), the home shows only these (from an email link)
  isAdmin: false, noteColors: [], notesBadge: { notes: 0, new_notes: 0 },
  board: { boards: [], currentId: null, notes: [], users: [], userId: null },
  stickers: null, stkYm: null, stkStatus: 'pending', stkGroupBy: 'med', stkFilter: [], stkFilterRes: [], stkNotesOnly: false,
  ov: { res: [], estado: 'all', notesOnly: false, cartOnly: false, q: '' },
  cart: new Set(), cartPeople: new Map(),
  planView: 'full', planSort: 'def',
};
try { S.planView = localStorage.getItem('asig_plan_view') || 'full'; S.planSort = localStorage.getItem('asig_plan_sort') || 'def'; } catch { /* */ }

// ── Tiny helpers ────────────────────────────────────────────────────────────────
function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function norm(s) { return String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
function fmtTis(t) { return String(t || '').replace(/(\d{4})(\d{4})/, '$1 $2'); }
async function api(path, opts) {
  const r = await fetch(API + path, opts);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json().catch(() => ({})) : {};
  if (!r.ok) { const err = new Error(data.error || `Error ${r.status}`); err.status = r.status; err.data = data; throw err; }
  return data;
}
function jbody(obj) { return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) }; }
// CIMA photo URL. The ?r bump forces browsers to drop images cached under the old
// long max-age (which could be low-res thumbnails); from then on ETag revalidation
// keeps them fresh.
const FOTO_REV = '2';
function fotoUrl(cn, tipo) { return `${API}/cima/foto/${encodeURIComponent(cn || '')}/${tipo}?r=${FOTO_REV}`; }
function fmtDate(s) { if (!s) return ''; const d = new Date(String(s).replace(' ', 'T') + 'Z'); return isNaN(d) ? s : d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' }); }
function fmtYm(ym) { if (!ym) return ''; const [y, m] = ym.split('-'); const names = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']; return `${names[Number(m) - 1] || m} ${y}`; }

let toastTimer = null;
function toast(msg, kind) { const t = $('toast'); t.textContent = msg; t.className = 'qt-toast' + (kind ? ' ' + kind : ''); t.hidden = false; if (toastTimer) clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 2800); }
function confirmBox(title, body, okLabel) {
  return new Promise(resolve => {
    $('confirm-title').textContent = title; $('confirm-body').textContent = body; $('confirm-yes').textContent = okLabel || 'Aceptar';
    const m = $('confirm-modal'); m.hidden = false;
    const done = v => { m.hidden = true; $('confirm-yes').onclick = null; $('confirm-no').onclick = null; resolve(v); };
    $('confirm-yes').onclick = () => done(true); $('confirm-no').onclick = () => done(false);
  });
}
function openTool(html) { const box = $('tool-modal-box'); box.classList.remove('az-modal-wide'); box.innerHTML = html; $('tool-modal').hidden = false; }
function closeTool() { $('tool-modal').hidden = true; const box = $('tool-modal-box'); box.classList.remove('az-modal-wide'); box.innerHTML = ''; }
// A big modal showing a CIMA image (box 'caja' or pill 'pastilla') large.
function openImageModal(med, tipo, label, emoji) {
  openTool(`<div class="qt-modal-h"><h3>${emoji} ${esc(med.nombre || 'Medicamento')}</h3><button class="qt-x" id="im-close">×</button></div>
    <div class="az-img-modal"><img src="${fotoUrl(med.cn, tipo)}" alt="${label}" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'az-noresult',textContent:'No hay imagen disponible.'}))"></div>
    <div class="az-form-hint" style="text-align:center">${label} · AEMPS · CIMA</div>`);
  $('tool-modal-box').classList.add('az-modal-wide');
  $('im-close').onclick = closeTool;
}

// Expiry status (mirrors the Data Matrix app).
function expiryState(iso) { if (!iso) return ''; const d = new Date(iso + 'T00:00:00Z'); if (isNaN(d)) return ''; const days = Math.floor((d - new Date()) / 86400000); if (days < 0) return 'vencida'; if (days <= 90) return 'pronto'; return ''; }
function cadDisplay(iso) { if (!iso) return '—'; const st = expiryState(iso); const cls = st === 'vencida' ? 'cad-bad' : st === 'pronto' ? 'cad-soon' : ''; return `<span class="dm-cad ${cls}">${fmtDate(iso)}${st === 'vencida' ? ' ⚠' : st === 'pronto' ? ' ⏳' : ''}</span>`; }

// ── QR rendering (client-side SVG, qrcode-generator) ─────────────────────────────
function qrSvg(text, o) {
  o = o || {};
  const dark = o.dark || '#0f172a', light = o.light || '#ffffff';
  const style = o.style === 'dots' ? 'dots' : 'square';
  const ecc = ['L', 'M', 'Q', 'H'].includes(o.ecc) ? o.ecc : 'M';
  const size = o.size || 300, margin = 4;
  let qr;
  try { qr = qrcode(0, ecc); qr.addData(String(text)); qr.make(); }
  catch (e) { return `<svg width="${size}" height="${size}"></svg>`; }
  const n = qr.getModuleCount(), tot = n + margin * 2;
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
// QR colour a person inherits from their group/residence (QR·TIS group colours).
function asigGroupColor(p) {
  const gc = (S.qrSettings && S.qrSettings.group_colors) || {};
  if (!p || !Array.isArray(p.groups)) return null;
  for (const g of p.groups) if (gc[g]) return gc[g];
  return null;
}
function qrOpts(p, size) {
  const st = S.qrSettings || {};
  return { dark: (p && p.qr_dark) || asigGroupColor(p) || st.qr_dark || '#0f172a', light: (p && p.qr_light) || st.qr_light || '#ffffff', style: (p && p.qr_style) || st.qr_style || 'square', ecc: st.qr_ecc || 'M', size };
}

// ── Data Matrix rendering (client, bwip-js) ──────────────────────────────────────
function dmSvg(raw, o) {
  o = o || {};
  const dark = (o.dark || '#0f172a').replace('#', ''), light = (o.light || '#ffffff').replace('#', ''), size = o.size || 150;
  let svg;
  try { svg = bwipjs.toSVG({ bcid: 'datamatrix', text: String(raw || ''), barcolor: dark, backgroundcolor: light, paddingwidth: 1, paddingheight: 1 }); }
  catch (e) { return `<svg width="${size}" height="${size}"></svg>`; }
  return svg.replace(/<svg /, `<svg width="${size}" height="${size}" shape-rendering="crispEdges" `);
}
// Scannable EAN-13 barcode ("precinto") for the Salud app.
function eanSvg(ean) {
  const s = String(ean || '').replace(/\D/g, '');
  if (s.length < 12) return '';
  try {
    const svg = bwipjs.toSVG({ bcid: 'ean13', text: s, includetext: true, textxalign: 'center', height: 16, paddingwidth: 2, paddingheight: 2 });
    return svg.replace(/<svg /, '<svg class="az-ean-svg" shape-rendering="crispEdges" ');
  } catch (e) { return ''; }
}
function shapeSvg(shape, color, px) {
  px = px || 16; const c = color || '#1273b8';
  const s = { circle: `<circle cx="12" cy="12" r="9" fill="${c}"/>`, square: `<rect x="3.5" y="3.5" width="17" height="17" rx="3" fill="${c}"/>`,
    triangle: `<path d="M12 3l9 16H3z" fill="${c}"/>`, diamond: `<path d="M12 2l10 10-10 10L2 12z" fill="${c}"/>`,
    hexagon: `<path d="M7 3h10l5 9-5 9H7l-5-9z" fill="${c}"/>`, star: `<path d="M12 2l2.9 6 6.6.6-5 4.3 1.6 6.5L12 22l-5.7 3.4 1.6-6.5-5-4.3 6.6-.6z" fill="${c}"/>`,
    pentagon: `<path d="M12 2l10 7.3-3.8 11.7H5.8L2 9.3z" fill="${c}"/>`, cross: `<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" fill="${c}"/>` }[shape] || `<circle cx="12" cy="12" r="9" fill="${c}"/>`;
  return `<svg class="dm-shape" width="${px}" height="${px}" viewBox="0 0 24 24" aria-hidden="true">${s}</svg>`;
}

// ── Scanner (camera → ZXing, decodes Data Matrix + QR) ───────────────────────────
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
      controls = ctrl; if (stopped) return;
      note.textContent = 'Apunta al código Data Matrix de la caja…';
      if (result) { const text = result.getText(); stop(); onResult(text); }
    }).then(c => { controls = c; }).catch(e => { note.textContent = 'No se pudo acceder a la cámara: ' + e.message; note.className = 'qt-scan-note err'; });
  } catch (e) { note.textContent = 'Lector no disponible: ' + e.message; note.className = 'qt-scan-note err'; }
}

// ── Boot ─────────────────────────────────────────────────────────────────────────
async function boot() {
  try {
    const meta = await api('/meta');
    S.settings = meta.settings; S.qrSettings = meta.qrSettings; S.month = meta.month; S.user = meta.user;
    S.isAdmin = !!meta.isAdmin; S.noteColors = meta.noteColors || []; S.notesBadge = meta.notesBadge || S.notesBadge;
    S.board.userId = meta.user.id;
    renderNotesBadge();
    checkNoteAlerts();                                  // aviso destacado si alguien me marcó una nota
    $('help-btn').onclick = viewHelp;
    $('bell-btn').onclick = openNotifications;
    $('notif-btn').onclick = openNotifManager;
    $('notes-btn').onclick = viewBoard;
    $('cart-toggle').onclick = () => { const p = $('cart-panel'); if (p.classList.contains('open')) closeCart(); else openCart(); };
    $('scrim').onclick = () => { closeCart(); };
    $('go-home').onclick = (e) => { e.preventDefault(); S.peopleFilter = null; viewHome(); };
    await reloadCart();
    await refreshNotifications();
    // Deep links from the notification emails: ?person=<id> or ?people=<id,id,…>.
    const params = new URLSearchParams(location.search);
    if (params.has('help')) { await viewHome(); viewHelp(); return; }
    const personId = Number(params.get('person'));
    const peopleCsv = params.get('people');
    if (personId) { await viewHome(); openPerson(personId); return; }
    if (peopleCsv) { S.peopleFilter = peopleCsv.split(',').map(Number).filter(Boolean); await viewHome(); return; }
    await viewHome();
  } catch (e) { main().innerHTML = `<div class="qt-empty">No se pudo cargar: ${esc(e.message)}</div>`; }
}

// ── Notifications / release-date search (bell) ───────────────────────────────────
function todayIsoClient() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
const NOTIF_MODES = [['all', 'Toda la medicación'], ['any', 'Al menos uno'], ['box', 'Por medicamento']];

// Bell badge: how many are "ready to assign" today, under the saved grouping mode.
async function refreshNotifications() {
  const mode = (S.settings && S.settings.notify_mode) || 'all';
  try { S.rel = await api('/release?criterion=lte&mode=' + mode); } catch (e) { return; }
  const badge = $('bell-count'); if (!badge) return;
  const n = S.rel.counts ? S.rel.counts.matched : 0;
  badge.textContent = n; badge.hidden = !n;
  $('bell-btn').classList.toggle('has-due', !!n);
}

// One medication (mode 'box' = por medicamento).
function notifMedRow(e, matched) {
  const eff = fmtDate(e.effective_at || e.release_at);
  const offNote = (e.release_at && e.release_at !== e.effective_at) ? ` <small class="az-off">of. ${fmtDate(e.release_at)}</small>` : '';
  const when = matched
    ? `<span class="az-note-when st-due">✅ ${e.days === 0 ? 'hoy' : e.days < 0 ? 'desde hace ' + Math.abs(e.days) + ' día(s)' : eff}${offNote}</span>`
    : `<span class="az-note-when st-soon">🗓 ${e.days > 0 ? 'en ' + e.days + ' día(s) · ' : ''}${eff}${offNote}</span>`;
  return `<button class="az-note" data-open="${e.person.id}">
    <span class="az-note-shape">${shapeSvg(e.shape, e.color, 18)}</span>
    <span class="az-note-body"><b>${esc(e.person.apellidos)}, ${esc(e.person.nombre)}</b><small>${esc(e.nombre || 'Medicamento')}</small></span>
    ${when}
  </button>`;
}
// One person aggregating their dated medications (mode 'all' / 'any').
function notifPersonRow(e, mode) {
  const done = e.aggDays <= 0;
  const agg = done
    ? (mode === 'all' ? '✅ todas ya están disponibles' : '✅ ya hay alguna disponible')
    : (mode === 'all' ? `todas disponibles el ${fmtDate(e.aggDate)} · faltan ${e.aggDays} día(s)` : `la primera disponible el ${fmtDate(e.aggDate)} · faltan ${e.aggDays} día(s)`);
  const meds = e.meds.map(m => {
    const eff = fmtDate(m.effective_at || m.release_at);
    const offNote = (m.release_at && m.release_at !== m.effective_at) ? ` <small class="az-off">of. ${fmtDate(m.release_at)}</small>` : '';
    return `<div class="az-note-sub"><span>${shapeSvg(m.shape, m.color, 12)} ${esc(m.nombre || 'Medicamento')}</span><span class="${m.satisfied ? 'st-due' : 'st-soon'}">${m.satisfied ? '✅' : '🗓'} ${eff}${offNote}</span></div>`;
  }).join('');
  return `<div class="az-note-person">
    <div class="az-note-person-h">
      <button class="az-note az-note-flex" data-open="${e.person.id}">
        <span class="az-note-body"><b>${esc(e.person.apellidos)}, ${esc(e.person.nombre)}</b><small>${esc(agg)} · ${e.releasedByToday}/${e.total} ya disponible(s)</small></span>
      </button>
      <button class="az-note-exp" data-exp="${e.person.id}" title="Ver los medicamentos">▾ ${e.total}</button>
    </div>
    <div class="az-note-boxes" id="exp-${e.person.id}" hidden>${meds}</div>
  </div>`;
}
function notifResultsHtml(data) {
  const rowFn = (data.mode === 'box') ? (e, m) => notifMedRow(e, m) : (e) => notifPersonRow(e, data.mode);
  const isToday = data.date === data.today;
  const okLabel = data.criterion === 'exact'
    ? `Salen exactamente el ${fmtDate(data.date)}`
    : (isToday ? 'Ya se pueden asignar (hoy)' : `Disponibles para el ${fmtDate(data.date)}`);
  const noLabel = data.criterion === 'exact' ? `Otras fechas` : (isToday ? 'Próximas a liberar' : `Aún no, para el ${fmtDate(data.date)}`);
  const sec = (title, arr, ok) => `<div class="az-note-sec"><div class="az-note-h">${ok ? '✅' : '🗓'} ${title} (${arr.length})</div>${arr.length ? `<div class="az-notelist">${arr.map(e => rowFn(e, ok)).join('')}</div>` : '<div class="az-empty-sm">Nada aquí.</div>'}</div>`;
  return sec(okLabel, data.matched, true) + sec(noLabel, data.pending, false);
}
async function notifLoad(stt) {
  const results = $('nt-results'); if (!results) return;
  results.innerHTML = '<div class="az-empty-sm">Cargando…</div>';
  const params = new URLSearchParams({ criterion: stt.criterion, mode: stt.mode });
  if (stt.date) params.set('date', stt.date);
  let data;
  try { data = await api('/release?' + params.toString()); } catch (e) { results.innerHTML = `<div class="az-noresult">${esc(e.message)}</div>`; return; }
  S.rel = data;
  results.innerHTML = notifResultsHtml(data);
  results.querySelectorAll('[data-open]').forEach(b => b.addEventListener('click', () => { closeTool(); openPerson(Number(b.dataset.open), b.dataset.ym || undefined); }));
  results.querySelectorAll('[data-exp]').forEach(h => h.addEventListener('click', () => { const box = document.getElementById('exp-' + h.dataset.exp); if (box) box.hidden = !box.hidden; }));
}
function openNotifications() {
  const stt = { date: todayIsoClient(), criterion: 'lte', mode: (S.settings && S.settings.notify_mode) || 'all' };
  const seg = (name, opts, cur) => `<div class="az-seg" data-seg="${name}">${opts.map(([v, l]) => `<button data-v="${v}" class="${v === cur ? 'on' : ''}">${l}</button>`).join('')}</div>`;
  openTool(`<div class="qt-modal-h"><h3>🔔 Liberación en Salud</h3><button class="qt-x" id="nt-close">×</button></div>
    <p class="qt-tool-note">Cajas <b>pre-asignadas</b> con fecha prevista de salir (liberarse) en la aplicación de Salud. Hasta que no salen, no puedes asignarlas.</p>
    <div class="az-note-ctl">
      <label>Avisar por: ${seg('mode', NOTIF_MODES, stt.mode)}</label>
      <label>Criterio: ${seg('criterion', [['lte', 'En o antes de'], ['exact', 'Fecha exacta']], stt.criterion)}</label>
      <label>Fecha: <input type="date" id="nt-date" class="qt-input" value="${stt.date}"></label>
    </div>
    <div id="nt-results"></div>`);
  $('nt-close').onclick = closeTool;
  $('tool-modal-box').querySelectorAll('.az-seg').forEach(seg => seg.querySelectorAll('button').forEach(btn => btn.addEventListener('click', async () => {
    const name = seg.dataset.seg, v = btn.dataset.v;
    seg.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === btn));
    stt[name] = v;
    if (name === 'mode') { S.settings.notify_mode = v; try { await api('/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ notify_mode: v }) }); } catch {} refreshNotifications(); }
    notifLoad(stt);
  })));
  $('nt-date').addEventListener('change', () => { stt.date = $('nt-date').value || todayIsoClient(); notifLoad(stt); });
  notifLoad(stt);
}

// ── Scheduled email notifications (manager) ──────────────────────────────────────
let notifState = { items: [], userEmail: '' };
const WD_LABELS = { '0': 'D', '1': 'L', '2': 'M', '3': 'X', '4': 'J', '5': 'V', '6': 'S' };
async function openNotifManager() {
  try { const d = await api('/notif'); notifState = { items: d.items, userEmail: d.userEmail || '' }; }
  catch (e) { toast(e.message, 'err'); return; }
  renderNotifList();
}
function fmtNotifSchedule(n) {
  if (n.schedule_kind === 'once') return `una vez · ${fmtDate(n.once_date)} · ${n.send_time}`;
  const days = (n.weekdays || '').split(',').filter(Boolean);
  return `recurrente · ${days.length ? days.map(d => WD_LABELS[d] || d).join(' ') : 'todos los días'} · ${n.send_time}`;
}
function notifRowHtml(n) {
  const type = n.ntype === 'all' ? 'Toda la medicación' : '≥1 medicamento';
  const crit = n.criterion === 'lte' ? 'acumulado' : 'novedades del día';
  const rc = (n.recipients || '').split(',').map(s => s.trim()).filter(Boolean);
  return `<div class="az-notif ${n.enabled ? '' : 'is-off'}">
    <div class="az-notif-body">
      <b>${esc(n.name || type)}</b>
      <small>${esc(type)} · ${esc(crit)} · ${esc(fmtNotifSchedule(n))}</small>
      <small>✉️ ${rc.length ? esc(rc.join(', ')) : 'sin destinatarios'}${n.last_sent_date ? ' · último: ' + fmtDate(n.last_sent_date) : ''}</small>
    </div>
    <div class="az-notif-actions">
      <button class="qt-toggle ${n.enabled ? 'on' : ''}" data-tg="${n.id}" title="Activar/desactivar">${n.enabled ? 'ON' : 'OFF'}</button>
      <button class="qt-iconbtn" data-edit="${n.id}" title="Editar">✏️</button>
      <button class="qt-iconbtn" data-send="${n.id}" title="Enviar ahora">✉️</button>
      <button class="qt-iconbtn danger" data-del="${n.id}" title="Borrar">🗑</button>
    </div>
  </div>`;
}
function renderNotifList() {
  openTool(`<div class="qt-modal-h"><h3>✉️ Notificaciones por email</h3><button class="qt-x" id="nt2-close">×</button></div>
    <p class="qt-tool-note">Programa avisos: la app envía un email con las personas a las que les sale medicación (con su QR para Salud, los Data Matrix y enlaces a la app).</p>
    <div style="margin-bottom:12px"><button class="qt-btn qt-btn-primary" id="nt2-new">➕ Nueva notificación</button></div>
    <div class="az-notiflist">${notifState.items.length ? notifState.items.map(notifRowHtml).join('') : '<div class="az-empty-sm">Aún no hay notificaciones. Crea una con «Nueva notificación».</div>'}</div>`);
  $('nt2-close').onclick = closeTool;
  $('nt2-new').onclick = () => notifForm(null);
  const box = $('tool-modal-box');
  box.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => notifForm(notifState.items.find(x => x.id === Number(b.dataset.edit))));
  box.querySelectorAll('[data-tg]').forEach(b => b.onclick = async () => { try { await api('/notif/' + b.dataset.tg + '/toggle', { method: 'POST' }); await openNotifManager(); } catch (e) { toast(e.message, 'err'); } });
  box.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => { if (!(await confirmBox('Borrar notificación', '¿Borrar esta notificación programada?', 'Borrar'))) return; try { await api('/notif/' + b.dataset.del, { method: 'DELETE' }); await openNotifManager(); } catch (e) { toast(e.message, 'err'); } });
  box.querySelectorAll('[data-send]').forEach(b => b.onclick = async () => { if (!(await confirmBox('Enviar ahora', '¿Enviar este email ahora a los destinatarios?', 'Enviar'))) return; try { const r = await api('/notif/' + b.dataset.send + '/send', jbody({})); toast(r.sent ? `Enviado · ${r.count} persona(s).` : 'No se envió (0 personas).'); } catch (e) { toast(e.message, 'err'); } });
}
function notifForm(n) {
  const f = {
    id: n ? n.id : null, name: n ? (n.name || '') : '', ntype: n ? n.ntype : 'any',
    criterion: n ? n.criterion : 'exact', schedule_kind: n ? n.schedule_kind : 'once',
    once_date: n && n.once_date ? n.once_date : todayIsoClient(), weekdays: n ? (n.weekdays || '') : '',
    send_time: n ? n.send_time : '08:00', recipients: n ? n.recipients : (notifState.userEmail || ''),
  };
  const seg = (name, opts) => `<div class="az-seg" data-fseg="${name}">${opts.map(([v, l]) => `<button type="button" data-v="${v}" class="${v === f[name] ? 'on' : ''}">${l}</button>`).join('')}</div>`;
  const WD = [['1', 'L'], ['2', 'M'], ['3', 'X'], ['4', 'J'], ['5', 'V'], ['6', 'S'], ['0', 'D']];
  const wdSet = new Set(f.weekdays.split(',').filter(Boolean));
  openTool(`<div class="qt-modal-h"><h3>${f.id ? 'Editar' : 'Nueva'} notificación</h3><button class="qt-x" id="nf-close">×</button></div>
    <div class="az-form">
      <label class="az-flabel">Nombre (opcional)</label>
      <input class="qt-input" id="nf-name" maxlength="120" value="${esc(f.name)}" placeholder="p. ej. Aviso diario 08:00">
      <label class="az-flabel">Tipo de notificación</label>${seg('ntype', [['any', 'Al menos un medicamento'], ['all', 'Toda la medicación']])}
      <label class="az-flabel">Criterio del día</label>${seg('criterion', [['exact', 'Novedades del día'], ['lte', 'Acumulado a la fecha']])}
      <label class="az-flabel">Cuándo</label>${seg('schedule_kind', [['once', 'Una vez'], ['recurring', 'Recurrente']])}
      <div id="nf-once" ${f.schedule_kind === 'once' ? '' : 'hidden'}><label class="az-flabel">Fecha</label><input type="date" class="qt-input" id="nf-date" value="${esc(f.once_date)}" style="max-width:200px"></div>
      <div id="nf-rec" ${f.schedule_kind === 'recurring' ? '' : 'hidden'}><label class="az-flabel">Días de la semana <small>(ninguno = todos los días)</small></label>
        <div class="az-wd">${WD.map(([v, l]) => `<label class="az-wd-item"><input type="checkbox" data-wd="${v}" ${wdSet.has(v) ? 'checked' : ''}> ${l}</label>`).join('')}</div></div>
      <label class="az-flabel">Hora <small>(formato 24h / militar)</small></label>
      <input type="time" class="qt-input" id="nf-time" value="${esc(f.send_time)}" style="max-width:150px">
      <label class="az-flabel">Destinatarios <small>(emails separados por comas)</small></label>
      <input class="qt-input" id="nf-rcpt" value="${esc(f.recipients)}" placeholder="tucorreo@ejemplo.com, otro@ejemplo.com">
      <div class="qt-modal-actions" style="justify-content:flex-start;flex-wrap:wrap;gap:8px;margin-top:14px">
        <button class="qt-btn qt-btn-primary" id="nf-save">💾 Guardar</button>
        <button class="qt-btn qt-btn-ghost" id="nf-preview">👁 Vista previa</button>
        ${f.id ? `<button class="qt-btn qt-btn-teal" id="nf-send">✉️ Enviar ahora</button>` : ''}
        <button class="qt-btn qt-btn-ghost" id="nf-back">← Volver</button>
      </div>
      <div class="az-form-hint">La vista previa se abre en una pestaña nueva con la fecha de referencia (la del envío único, o hoy). «Enviar ahora» usa la versión guardada.</div>
    </div>`);
  $('nf-close').onclick = closeTool;
  $('nf-back').onclick = () => renderNotifList();
  $('tool-modal-box').querySelectorAll('.az-seg[data-fseg]').forEach(sg => sg.querySelectorAll('button').forEach(btn => btn.onclick = () => {
    const name = sg.dataset.fseg; f[name] = btn.dataset.v; sg.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === btn));
    if (name === 'schedule_kind') { $('nf-once').hidden = f.schedule_kind !== 'once'; $('nf-rec').hidden = f.schedule_kind !== 'recurring'; }
  }));
  const readDraft = () => ({
    name: $('nf-name').value, ntype: f.ntype, criterion: f.criterion, schedule_kind: f.schedule_kind,
    once_date: $('nf-date') ? $('nf-date').value : '',
    weekdays: [...$('tool-modal-box').querySelectorAll('[data-wd]:checked')].map(c => c.dataset.wd).join(','),
    send_time: $('nf-time').value, recipients: $('nf-rcpt').value,
  });
  $('nf-save').onclick = async () => {
    const d = readDraft();
    try {
      if (f.id) await api('/notif/' + f.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) });
      else await api('/notif', jbody(d));
      toast('Notificación guardada.'); await openNotifManager();
    } catch (e) { toast(e.message, 'err'); }
  };
  $('nf-preview').onclick = async () => {
    const d = readDraft(); d.ref_date = (d.schedule_kind === 'once' && d.once_date) ? d.once_date : todayIsoClient();
    try { const r = await api('/notif/preview', jbody(d)); const w = window.open('', '_blank'); if (w) { w.document.write(r.html); w.document.close(); } else toast('Permite las ventanas emergentes para ver la vista previa.', 'err'); }
    catch (e) { toast(e.message, 'err'); }
  };
  if ($('nf-send')) $('nf-send').onclick = async () => {
    if (!(await confirmBox('Enviar ahora', '¿Enviar este email ahora a los destinatarios guardados?', 'Enviar'))) return;
    try { const r = await api('/notif/' + f.id + '/send', jbody({})); toast(r.sent ? `Enviado · ${r.count} persona(s).` : 'No se envió.'); } catch (e) { toast(e.message, 'err'); }
  };
}

// ── Post-its (tablón de notas) ───────────────────────────────────────────────────
function renderNotesBadge() {
  const btn = $('notes-btn'), badge = $('notes-count'); if (!btn) return;
  const b = S.notesBadge || {};
  btn.classList.remove('has-notes', 'has-new');
  if (b.new_notes > 0) { btn.classList.add('has-new'); badge.textContent = b.new_notes; badge.hidden = false; }
  else { badge.hidden = true; if (b.notes > 0) btn.classList.add('has-notes'); }
}
async function refreshNotesBadge() { try { S.notesBadge = await api('/notes/badge'); renderNotesBadge(); } catch { /* keep */ } }

// Al abrir la app: si otro usuario me ha marcado notas con aviso, se lo muestro destacado.
async function checkNoteAlerts() {
  let data; try { data = await api('/notes/alerts'); } catch { return; }
  const items = (data && data.items) || [];
  if (!items.length) return;
  showAlertModal(items);
}
function showAlertModal(items) {
  const cards = items.map(it => `
    <div class="az-alert-item" data-board="${it.board_id}">
      <span class="az-alert-dot" style="background:${esc(it.color || '#FEF08A')}"></span>
      <div class="az-alert-body">
        <div class="az-alert-from"><b>${esc(it.author_name)}</b> · tablón «${esc(it.board_name)}»</div>
        <div class="az-alert-txt">${esc(it.excerpt)}</div>
      </div>
    </div>`).join('');
  const n = items.length;
  openTool(`<div class="az-alert-modal">
      <div class="az-alert-head"><span class="az-alert-bell">🔔</span>
        <h3>${n === 1 ? 'Tienes una nota que requiere tu atención' : `Tienes ${n} notas que requieren tu atención`}</h3></div>
      <p class="az-alert-lead">Alguien te ha dejado ${n === 1 ? 'un recado' : 'recados'} en el tablón de notas. Ábrelo${n === 1 ? '' : 's'} cuando puedas.</p>
      <div class="az-alert-list">${cards}</div>
      <div class="qt-modal-actions">
        <button class="qt-btn qt-btn-ghost" id="al-later">Ahora no</button>
        <button class="qt-btn qt-btn-primary" id="al-open">Ver ${n === 1 ? 'la nota' : 'las notas'} →</button>
      </div>
    </div>`);
  const firstBoard = items[0].board_id;
  $('al-later').onclick = closeTool;
  $('al-open').onclick = () => { closeTool(); if (firstBoard) { localStorage.setItem('asig_board', String(firstBoard)); S.board.currentId = firstBoard; } viewBoard(); };
  $('tool-modal-box').querySelectorAll('.az-alert-item').forEach(el => el.addEventListener('click', () => {
    const bid = Number(el.dataset.board); closeTool(); if (bid) { localStorage.setItem('asig_board', String(bid)); S.board.currentId = bid; } viewBoard();
  }));
}

async function viewBoard() {
  stopScannerMode(true); stopStkScanner(true);
  S.view = 'board'; S.person = null; S.ficha = null; S.peopleFilter = null;
  try {
    const bd = await api('/boards'); S.board.boards = bd.items; S.board.userId = bd.userId; S.isAdmin = bd.isAdmin;
    let cur = Number(localStorage.getItem('asig_board') || 0);
    if (!S.board.boards.some(b => b.id === cur)) cur = S.board.boards[0] ? S.board.boards[0].id : null;
    S.board.currentId = cur;
    if (!S.board.users.length) { try { const u = await api('/users'); S.board.users = u.items; } catch { /* ignore */ } }
    await loadBoardNotes();
  } catch (e) { toast(e.message, 'err'); }
}
async function loadBoardNotes() {
  const id = S.board.currentId;
  if (id) localStorage.setItem('asig_board', String(id));
  try { const r = id ? await api('/notes?board_id=' + id) : { items: [] }; S.board.notes = r.items; } catch { S.board.notes = []; }
  renderBoard();
  if (id) { try { const r = await api('/notes/seen', jbody({ board_id: id })); if (r.badge) { S.notesBadge = r.badge; renderNotesBadge(); } } catch { /* ignore */ } }
  try { const bd = await api('/boards'); S.board.boards = bd.items; renderBoardTabs(); } catch { /* ignore */ }
}
function renderBoard() {
  main().innerHTML =
    `<div class="qt-ficha-top"><button class="qt-back" id="back">← Volver</button></div>
     <div class="az-board-wrap">
       <div class="az-tabs" id="board-tabs"></div>
       <div class="az-board-toolbar">
         <button class="qt-btn qt-btn-primary qt-btn-sm" id="new-note">➕ Nueva nota</button>
         <span class="az-board-hint">Arrastra por la cabecera · redimensiona por la esquina · el color y el texto se guardan solos. Quien ve una nota, la edita.</span>
       </div>
       <div class="az-canvas" id="board-canvas"></div>
     </div>`;
  $('back').onclick = viewHome;
  $('new-note').onclick = createNoteHere;
  renderBoardTabs();
  renderCanvas();
}
function renderBoardTabs() {
  const wrap = $('board-tabs'); if (!wrap) return;
  const canMng = b => b.author_id === S.board.userId || S.isAdmin;
  wrap.innerHTML = S.board.boards.map(b => `<div class="az-tab ${b.id === S.board.currentId ? 'sel' : ''}" data-b="${b.id}">
      <span class="az-tab-name">${esc(b.name)}${b.new_count ? '<span class="az-tab-dot" title="Notas nuevas"></span>' : ''}</span>
      ${canMng(b) ? `<span class="az-tab-actions"><button data-ren="${b.id}" title="Renombrar">✏️</button><button data-delb="${b.id}" title="Borrar">🗑</button></span>` : ''}
    </div>`).join('') + `<button class="az-tab az-tab-new" id="new-board">＋ Nuevo tablón</button>`;
  wrap.querySelectorAll('[data-b]').forEach(t => t.addEventListener('click', e => { if (e.target.closest('[data-ren],[data-delb]')) return; if (Number(t.dataset.b) === S.board.currentId) return; S.board.currentId = Number(t.dataset.b); loadBoardNotes(); }));
  $('new-board').onclick = async () => { const name = prompt('Nombre del nuevo tablón:'); if (!name || !name.trim()) return; try { const r = await api('/boards', jbody({ name: name.trim() })); S.board.currentId = r.item.id; await viewBoard(); } catch (e) { toast(e.message, 'err'); } };
  wrap.querySelectorAll('[data-ren]').forEach(b => b.addEventListener('click', async () => { const bd = S.board.boards.find(x => x.id === Number(b.dataset.ren)); const name = prompt('Nuevo nombre del tablón:', bd ? bd.name : ''); if (!name || !name.trim()) return; try { await api('/boards/' + b.dataset.ren, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name.trim() }) }); await viewBoard(); } catch (e) { toast(e.message, 'err'); } }));
  wrap.querySelectorAll('[data-delb]').forEach(b => b.addEventListener('click', async () => { if (!(await confirmBox('Borrar tablón', '¿Borrar este tablón y todas sus notas? No se puede deshacer.', 'Borrar'))) return; try { await api('/boards/' + b.dataset.delb, { method: 'DELETE' }); S.board.currentId = null; await viewBoard(); } catch (e) { toast(e.message, 'err'); } }));
}
function renderCanvas() {
  const canvas = $('board-canvas'); if (!canvas) return;
  canvas.innerHTML = '';
  if (!S.board.notes.length) { canvas.innerHTML = '<div class="az-canvas-empty">No hay notas en este tablón. Crea una con «➕ Nueva nota».</div>'; return; }
  for (const n of S.board.notes) canvas.appendChild(buildNoteCard(n));
}
async function createNoteHere() {
  const k = S.board.notes.length;
  try {
    const r = await api('/notes', jbody({ board_id: S.board.currentId, content: '', color: S.noteColors[0], visibility: 'privada', width: 240, height: 200, pos_x: 24 + (k % 6) * 28, pos_y: 24 + (k % 6) * 28 }));
    S.board.notes.push(r.item);
    const canvas = $('board-canvas'); const empty = canvas.querySelector('.az-canvas-empty'); if (empty) empty.remove();
    const card = buildNoteCard(r.item); canvas.appendChild(card); const ta = card.querySelector('textarea'); if (ta) ta.focus();
  } catch (e) { toast(e.message, 'err'); }
}
function saveNote(id, patch) {
  return api('/notes/' + id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) })
    .then(r => { const i = S.board.notes.findIndex(x => x.id === id); if (i >= 0) S.board.notes[i] = r.item; return r.item; })
    .catch(e => { toast(e.message, 'err'); throw e; });
}
// Read the card's current rotation angle (radians) from its computed transform.
function readRotation(el) { const t = getComputedStyle(el).transform; if (!t || t === 'none') return 0; try { const m = new DOMMatrixReadOnly(t); return Math.atan2(m.b, m.a); } catch { return 0; } }
function clampN2(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
function noteMetaIcon(n) { const base = n.visibility === 'todos' ? '🌐 todos' : n.visibility === 'personalizada' ? '👥' : '🔒'; return n.alert ? base + ' 🔔' : base; }
function refreshCardShareState(id) {
  const n = S.board.notes.find(x => x.id === id); if (!n) return;
  const canvas = $('board-canvas'); const card = canvas && canvas.querySelector(`.postit-card[data-id="${id}"]`); if (!card) return;
  const share = card.querySelector('.postit-share'); if (share) { share.classList.remove('shared', 'all'); if (n.has_viewers) share.classList.add('shared'); else if (n.visibility === 'todos') share.classList.add('all'); }
  card.classList.toggle('is-alerting', !!n.alert);
  const meta = card.querySelector('.postit-meta'); if (meta) meta.textContent = noteMetaIcon(n);
}
function buildNoteCard(n) {
  const card = document.createElement('div');
  card.className = 'postit-card' + (n.alert ? ' is-alerting' : ''); card.dataset.id = n.id;
  card.style.left = n.pos_x + 'px'; card.style.top = n.pos_y + 'px';
  card.style.width = n.width + 'px'; card.style.height = n.height + 'px'; card.style.background = n.color;
  const mng = n.puede_gestionar;
  const shareCls = n.has_viewers ? 'shared' : (n.visibility === 'todos' ? 'all' : '');
  card.innerHTML =
    `<div class="postit-head">
       <span class="postit-drag" title="Arrastrar">⠿</span>
       <span class="postit-meta">${noteMetaIcon(n)}</span>
       <span class="postit-actions">
         ${mng ? `<button class="postit-btn postit-share ${shareCls}" title="Compartir">🔗</button>` : ''}
         ${mng ? `<button class="postit-btn postit-del" title="Borrar">🗑</button>` : ''}
       </span>
     </div>
     <div class="postit-swatches">${S.noteColors.map(c => `<button class="postit-swatch ${c === n.color ? 'sel' : ''}" data-c="${c}" style="background:${c}" aria-label="color"></button>`).join('')}</div>
     <textarea class="postit-text" placeholder="Escribe…" spellcheck="false">${esc(n.content)}</textarea>
     <div class="postit-resize" title="Redimensionar"></div>`;
  const head = card.querySelector('.postit-head'), ta = card.querySelector('.postit-text'), handle = card.querySelector('.postit-resize');

  head.addEventListener('pointerdown', e => {
    if (e.target.closest('button')) return;
    e.preventDefault(); try { head.setPointerCapture(e.pointerId); } catch { /* */ }
    const sx = e.clientX, sy = e.clientY, ox = parseFloat(card.style.left) || 0, oy = parseFloat(card.style.top) || 0;
    card.classList.add('dragging'); let nx = ox, ny = oy;
    const move = ev => { nx = Math.max(0, ox + (ev.clientX - sx)); ny = Math.max(0, oy + (ev.clientY - sy)); card.style.left = nx + 'px'; card.style.top = ny + 'px'; };
    const up = () => { head.removeEventListener('pointermove', move); head.removeEventListener('pointerup', up); head.removeEventListener('pointercancel', up); card.classList.remove('dragging'); saveNote(n.id, { pos_x: nx, pos_y: ny }); };
    head.addEventListener('pointermove', move); head.addEventListener('pointerup', up); head.addEventListener('pointercancel', up);
  });

  handle.addEventListener('pointerdown', e => {
    e.preventDefault(); e.stopPropagation(); try { handle.setPointerCapture(e.pointerId); } catch { /* */ }
    card._userResized = true;
    const sx = e.clientX, sy = e.clientY, ow = card.offsetWidth, oh = card.offsetHeight;
    const th = readRotation(card), cos = Math.cos(th), sin = Math.sin(th);
    const move = ev => {
      const dx = ev.clientX - sx, dy = ev.clientY - sy;
      const ldx = dx * cos + dy * sin, ldy = -dx * sin + dy * cos;
      card.style.width = clampN2(ow + ldx, 180, 480) + 'px';
      card.style.height = clampN2(oh + ldy, 160, 560) + 'px';
    };
    const up = () => { handle.removeEventListener('pointermove', move); handle.removeEventListener('pointerup', up); handle.removeEventListener('pointercancel', up); };
    handle.addEventListener('pointermove', move); handle.addEventListener('pointerup', up); handle.addEventListener('pointercancel', up);
  });
  const ro = new ResizeObserver(() => { if (!card._userResized) return; clearTimeout(card._roTimer); card._roTimer = setTimeout(() => saveNote(n.id, { width: card.offsetWidth, height: card.offsetHeight }), 500); });
  ro.observe(card);

  card.querySelectorAll('.postit-swatch').forEach(sw => sw.addEventListener('click', () => {
    const c = sw.dataset.c; card.style.background = c; card.querySelectorAll('.postit-swatch').forEach(x => x.classList.toggle('sel', x === sw)); saveNote(n.id, { color: c });
  }));
  ta.addEventListener('input', () => { clearTimeout(card._txtTimer); card._txtTimer = setTimeout(() => saveNote(n.id, { content: ta.value }), 600); });

  const share = card.querySelector('.postit-share'); if (share) share.addEventListener('click', () => openShareModal(n));
  const del = card.querySelector('.postit-del'); if (del) del.addEventListener('click', async () => { if (!(await confirmBox('Borrar nota', '¿Borrar esta nota?', 'Borrar'))) return; try { await api('/notes/' + n.id, { method: 'DELETE' }); S.board.notes = S.board.notes.filter(x => x.id !== n.id); card.remove(); if (!S.board.notes.length) renderCanvas(); } catch (e) { toast(e.message, 'err'); } });
  return card;
}
function openShareModal(n) {
  const authorId = n.author_id;
  const allUsers = S.board.users.filter(u => u.id !== authorId);
  let allOn = n.visibility === 'todos';
  let alertOn = !!n.alert;
  const checked = new Set(n.visibility === 'personalizada' ? (n.viewer_ids || []) : []);
  if (n.visibility === 'privada' && !checked.size) { try { (JSON.parse(localStorage.getItem('asig_share_last') || '[]')).forEach(id => { if (allUsers.some(u => u.id === id)) checked.add(id); }); } catch { /* */ } }
  const apply = async () => {
    let visibility, viewer_ids = [];
    if (allOn) visibility = 'todos'; else if (checked.size) { visibility = 'personalizada'; viewer_ids = [...checked]; } else visibility = 'privada';
    if (visibility === 'privada') alertOn = false;           // una nota privada no avisa a nadie
    try {
      const item = await saveNote(n.id, { visibility, viewer_ids, alert: alertOn });
      n.alert = !!(item && item.alert);
      if (visibility === 'personalizada') localStorage.setItem('asig_share_last', JSON.stringify(viewer_ids));
      refreshCardShareState(n.id); updHead(); syncAlertUi();
    } catch { /* */ }
  };
  const isShared = () => allOn || checked.size > 0;
  const syncAlertUi = () => {
    const cb = $('sh-alert'); if (cb) { cb.checked = alertOn; cb.disabled = !isShared(); }
    const row = $('sh-alert-row'); if (row) row.classList.toggle('is-dim', !isShared());
    const rp = $('sh-repoke'); if (rp) rp.hidden = !(isShared() && n.alert);
  };
  const render = (filter) => {
    const q = norm(filter || '');
    const list = allUsers.filter(u => !q || norm(u.name + ' ' + u.email).includes(q));
    $('sh-list').innerHTML = list.length ? list.map(u => `<label class="az-shitem ${allOn ? 'is-dim' : ''}"><input type="checkbox" data-u="${u.id}" ${checked.has(u.id) ? 'checked' : ''} ${allOn ? 'disabled' : ''}><span>${esc(u.name)}<small>${esc(u.email)}</small></span></label>`).join('') : '<div class="az-empty-sm">Sin usuarios que coincidan.</div>';
    $('sh-list').querySelectorAll('[data-u]').forEach(cb => cb.addEventListener('change', () => { const id = Number(cb.dataset.u); if (cb.checked) checked.add(id); else checked.delete(id); apply(); }));
  };
  const updHead = () => { const t = $('sh-state'); if (t) t.textContent = allOn ? 'Visible para todos los usuarios de esta app.' : (checked.size ? `Compartida con ${checked.size} usuario(s).` : 'Privada (solo tú).'); };
  openTool(`<div class="qt-modal-h"><h3>🔗 Compartir nota</h3><button class="qt-x" id="sh-close">×</button></div>
    <label class="az-shtoggle"><input type="checkbox" id="sh-all" ${allOn ? 'checked' : ''}> <b>Visible para todos</b></label>
    <div class="qt-tool-note" id="sh-state"></div>
    <div class="qt-search" style="margin:8px 0"><span class="ico">🔎</span><input id="sh-q" placeholder="Buscar usuario…" autocomplete="off"></div>
    <div id="sh-list" class="az-shlist"></div>
    <label class="az-shtoggle az-alert-row" id="sh-alert-row"><input type="checkbox" id="sh-alert"> <b>🔔 Avisar a los destinatarios</b>
      <small>Les saltará un aviso destacado al abrir la app hasta que abran la nota.</small></label>
    <button class="qt-btn qt-btn-ghost qt-btn-sm az-repoke" id="sh-repoke" hidden>🔔 Volver a avisar (aunque ya la vieran)</button>
    <div class="az-form-hint">Quien puede <b>ver</b> la nota también puede <b>editarla</b> (es una conversación sobre el post-it). Los cambios se aplican al instante.</div>`);
  $('sh-close').onclick = closeTool;
  $('sh-all').addEventListener('change', () => { allOn = $('sh-all').checked; render($('sh-q').value); apply(); });
  $('sh-q').addEventListener('input', () => render($('sh-q').value));
  $('sh-alert').addEventListener('change', () => { alertOn = $('sh-alert').checked; apply(); });
  $('sh-repoke').addEventListener('click', async () => {
    try { const r = await api('/notes/' + n.id + '/repoke', { method: 'POST' }); n.alert = !!(r.item && r.item.alert); alertOn = n.alert;
      const i = S.board.notes.findIndex(x => x.id === n.id); if (i >= 0) S.board.notes[i] = r.item;
      refreshCardShareState(n.id); syncAlertUi(); toast('Aviso reenviado a los destinatarios.', 'ok'); } catch (e) { toast(e.message, 'err'); }
  });
  render(''); updHead(); syncAlertUi();
}

// ── Home / panel ─────────────────────────────────────────────────────────────────
async function viewHome() {
  stopScannerMode(true);
  S.view = 'home'; S.person = null; S.ficha = null;
  try { const { items } = await api('/overview'); S.overview = items; } catch (e) { S.overview = []; }
  refreshNotifications();
  refreshNotesBadge();
  renderHome();
}
function renderHome() {
  const filtering = Array.isArray(S.peopleFilter) && S.peopleFilter.length;
  const banner = filtering
    ? `<div class="az-filter-banner">👥 Filtrando por una notificación (${S.peopleFilter.length} persona/s). <a id="clear-filter">Ver todas →</a></div>`
    : '';
  main().innerHTML =
    `<div class="qt-panel az-panel">
       <div class="qt-section-title">Asignación de medicación</div>
       <div class="qt-section-sub">Elige una persona (de QR·TIS) para preparar y asignar su medicación (cajas Data Matrix). Control mensual: ${esc(fmtYm(S.month))}.</div>

       <div class="az-picker">
         <div class="qt-search"><span class="ico">🔎</span><input id="pq" placeholder="Buscar persona por nombre, apellidos, TIS, nº de farmacia…" autocomplete="off" value="${esc(S.searchQuery)}"></div>
         <div id="pq-results" class="az-results"></div>
       </div>
       <div class="az-home-actions"><button class="qt-btn qt-btn-ghost qt-btn-sm" id="import-med">📥 Importar medicación (por Código Nacional)</button></div>

       ${banner}
       <div id="ov-wrap"></div>
     </div>

     <div class="qt-panel az-panel az-stk-panel">
       <div class="qt-section-title">🏷️ Control de precintos <span class="az-stk-sub2">(pegado en la hoja de Salud)</span></div>
       <div class="qt-section-sub">Cada medicación asignada tiene un <b>precinto</b> (código de barras) que hay que recortar y pegar en la hoja oficial <b>4×7</b> antes de fin de mes. Aquí ves cuántos faltan, los ordenas por medicamento (PDF), y marcas los pegados a mano, escaneando o con una foto de prueba.</div>
       <div id="stk-body"><div class="az-empty-sm">Cargando…</div></div>
     </div>`;
  if ($('clear-filter')) $('clear-filter').onclick = () => { S.peopleFilter = null; renderHome(); };
  const pq = $('pq');
  pq.addEventListener('input', () => { S.searchQuery = pq.value; searchPeople(pq.value); });
  if (S.searchQuery) searchPeople(S.searchQuery);
  if ($('import-med')) $('import-med').onclick = openMedImport;
  renderOverviewSection();
  loadStickers(S.stkYm || undefined);
}
// Bulk-import medications by Código Nacional: paste one line per person
// ("<TIS o Nº de farmacia>  cn, cn, cn"). CIMA fills each medication's name/barcode.
function parseMedImport(text) {
  const rows = [];
  for (const raw of String(text || '').split(/\r?\n/)) {
    const nums = raw.match(/\d+/g);
    if (!nums || nums.length < 2) continue;   // need a person code + at least one CN
    rows.push({ person: nums[0], cns: nums.slice(1) });
  }
  return rows;
}
function openMedImport() {
  const st = { by: 'tis' };
  const seg = `<div class="az-seg" id="mi-by"><button type="button" data-v="tis" class="on">TIS</button><button type="button" data-v="pharmacy">Nº de farmacia</button></div>`;
  openTool(`<div class="qt-modal-h"><h3>📥 Importar medicación por Código Nacional</h3><button class="qt-x" id="mi-x">×</button></div>
    <p class="qt-tool-note">Pega <b>una línea por persona</b>: primero su <b>identificador</b> y luego sus <b>Códigos Nacionales</b> separados por comas (o espacios). La app buscará cada medicamento en <b>CIMA</b> para rellenar nombre y código de barras, y lo añadirá al plan (queda «pendiente de caja»).</p>
    <div class="qt-field"><label>Identificar persona por</label>${seg}</div>
    <div class="qt-field"><label>Cajas al mes por defecto</label><input type="number" class="qt-input" id="mi-qty" min="1" max="99" value="1" style="max-width:120px"></div>
    <div class="qt-field"><label>Listado</label><textarea class="qt-input az-mi-ta" id="mi-text" rows="9" placeholder="00930868: 885442, 715000, 659432&#10;00930869  712345 998877&#10;…"></textarea></div>
    <div class="az-mi-preview" id="mi-preview"></div>
    <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" id="mi-cancel">Cancelar</button><button class="qt-btn qt-btn-primary" id="mi-go">📥 Importar</button></div>
    <div id="mi-report"></div>`);
  $('mi-x').onclick = closeTool; $('mi-cancel').onclick = closeTool;
  $('tool-modal-box').querySelectorAll('#mi-by button').forEach(btn => btn.onclick = () => { st.by = btn.dataset.v; $('mi-by').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === btn)); });
  const preview = () => {
    const rows = parseMedImport($('mi-text').value);
    const cns = rows.reduce((s, r) => s + r.cns.length, 0);
    $('mi-preview').innerHTML = rows.length ? `<div class="az-form-hint">Se detectan <b>${rows.length}</b> persona(s) y <b>${cns}</b> código(s) nacional(es).</div>` : '<div class="az-form-hint">Pega el listado arriba.</div>';
  };
  $('mi-text').addEventListener('input', preview); preview();
  $('mi-go').onclick = async () => {
    const rows = parseMedImport($('mi-text').value);
    if (!rows.length) { toast('No hay filas válidas. Revisa el formato.', 'err'); return; }
    const qty = Math.max(1, Math.min(99, Math.round(Number($('mi-qty').value) || 1)));
    const btn = $('mi-go'); btn.disabled = true; btn.textContent = 'Importando (consultando CIMA)…';
    try {
      const r = await api('/plan/import', jbody({ by: st.by, qty, rows }));
      const errs = r.errors || [];
      $('mi-report').innerHTML = `<div class="qt-note ${errs.length ? 'warn' : 'tip'}" style="margin-top:12px">
        <b>✓ Importación terminada.</b><br>
        Personas: <b>${r.people}</b> · Medicamentos añadidos: <b>${r.added}</b> · Actualizados: <b>${r.updated}</b><br>
        CIMA: ${r.cima.reached ? `datos de <b>${r.cima.found}</b>/${r.cima.total} códigos${r.cima.missing ? ` · <b>${r.cima.missing}</b> sin datos (añadidos por CN)` : ''}` : '<b>no disponible</b> ahora (los medicamentos se añadieron solo con su CN; edítalos o pulsa «🔎 CIMA» luego)'}.
        ${errs.length ? `<br><br><b>${errs.length} aviso(s):</b><ul style="margin:6px 0 0;padding-left:18px">${errs.slice(0, 30).map(e => `<li>Línea ${e.line} (${esc(String(e.code))})${e.cn ? ' · CN ' + esc(e.cn) : ''}: ${esc(e.error)}</li>`).join('')}${errs.length > 30 ? `<li>…y ${errs.length - 30} más</li>` : ''}</ul>` : ''}
      </div>`;
      toast(`Importado: ${r.added} añadidos, ${r.updated} actualizados.`, 'ok');
      viewHome();   // refresh overview counts (keeps the modal open with its report)
    } catch (e) { toast(e.message, 'err'); btn.disabled = false; btn.textContent = '📥 Importar'; }
  };
}
function statusChip(r) {
  if (!r.plan_count && !r.has_month_period) return `<span class="az-chip az-chip-none">sin plan</span>`;
  const c = r.month_counts;
  if (!r.has_month_period || c.total === 0) return `<span class="az-chip az-chip-todo">⏳ pendiente este mes</span>`;
  const pre = c.preasignada, done = c.asignada;
  if (pre > 0) return `<span class="az-chip az-chip-pre">🔗 ${done} asignada(s) · ${pre} por asignar</span>`;
  return `<span class="az-chip az-chip-done">✓ ${done} asignada(s)</span>`;
}
// ── Overview filtering (scales to hundreds of people) ────────────────────────────
function ovResidencia(r) { return (r.person.groups && r.person.groups.length) ? r.person.groups.join(' · ') : 'Sin grupo'; }
function ovEstado(r) {
  if ((r.plan_count || 0) === 0) return 'noplan';
  const planned = r.planned_total || 0, asg = r.month_counts ? r.month_counts.asignada : 0;
  return (planned > 0 && asg >= planned) ? 'assigned' : 'partial';
}
function overviewFiltered() {
  const f = S.ov, q = norm(f.q);
  return S.overview.filter(r => {
    if (Array.isArray(S.peopleFilter) && S.peopleFilter.length && !S.peopleFilter.includes(r.person.id)) return false;
    if (f.res.length && !f.res.includes(ovResidencia(r))) return false;
    if (f.estado === 'assigned' && ovEstado(r) !== 'assigned') return false;
    if (f.estado === 'partial' && ovEstado(r) !== 'partial') return false;
    if (f.estado === 'noplan' && ovEstado(r) !== 'noplan') return false;
    if (f.estado === 'ready' && !((r.ready_count || 0) > 0)) return false;
    if (f.notesOnly && !(r.note && r.note.text)) return false;
    if (f.cartOnly && !S.cart.has(r.person.id)) return false;
    if (q) { const hay = norm(`${r.person.apellidos} ${r.person.nombre} ${r.person.tis} ${r.person.pharmacy_no || ''}`); if (!hay.includes(q)) return false; }
    return true;
  });
}
function ovControlsHtml() {
  const f = S.ov;
  const resMap = new Map();
  for (const r of S.overview) { const k = ovResidencia(r); resMap.set(k, (resMap.get(k) || 0) + 1); }
  const resKeys = [...resMap.keys()].sort((a, b) => a === 'Sin grupo' ? 1 : b === 'Sin grupo' ? -1 : a.localeCompare(b, 'es'));
  const hasRes = resKeys.length > 1 || (resKeys.length === 1 && resKeys[0] !== 'Sin grupo');
  const estados = [['all', 'Todas'], ['partial', 'Falta por asignar'], ['assigned', 'Todo asignado'], ['ready', 'Con algo listo'], ['noplan', 'Sin plan']];
  return `<div class="az-ovfilters">
    <div class="qt-search az-ov-search"><span class="ico">🔎</span><input id="ov-q" placeholder="Filtrar en seguimiento (nombre, TIS, farmacia)…" autocomplete="off" value="${esc(f.q)}"></div>
    <div class="az-ovfilter-row"><span class="az-stk-flabel">Estado</span><div class="az-seg az-ovseg" id="ov-estado">${estados.map(([v, l]) => `<button data-v="${v}" class="${f.estado === v ? 'on' : ''}">${l}</button>`).join('')}</div>
      <button class="az-stk-chip ${f.notesOnly ? 'on' : ''}" id="ov-notesonly" title="Solo personas con nota">📝 Con notas</button>
      <button class="az-stk-chip ${f.cartOnly ? 'on' : ''}" id="ov-cartonly" title="Solo las personas del carrito">🛒 Solo carrito</button></div>
    ${hasRes ? `<div class="az-ovfilter-row"><span class="az-stk-flabel">Residencia</span><div class="az-stk-filters">
      <button class="az-stk-chip ${f.res.length === 0 ? 'on' : ''}" data-ov-res="__all">Todas</button>
      ${resKeys.map(k => `<button class="az-stk-chip ${f.res.includes(k) ? 'on' : ''}" data-ov-res="${esc(k)}">${esc(shortLabel(k))} <b>${resMap.get(k)}</b></button>`).join('')}</div></div>` : ''}
  </div>`;
}
function renderOverviewSection() {
  const wrap = $('ov-wrap'); if (!wrap) return;
  const filtered = overviewFiltered();
  wrap.innerHTML = `<div class="qt-section-title" style="margin-top:22px">En seguimiento (<span id="ov-count">${filtered.length}</span>${filtered.length !== S.overview.length ? ' de ' + S.overview.length : ''})</div>
    <div class="qt-section-sub">Personas con plan o asignaciones. El estado es el del mes en curso.</div>
    ${ovControlsHtml()}
    <div id="ov-body">${overviewHtml(filtered)}</div>`;
  // Estado + residence + notes chips → full re-render (buttons, no focus to keep).
  const seg = $('ov-estado'); if (seg) seg.querySelectorAll('[data-v]').forEach(b => b.onclick = () => { S.ov.estado = b.dataset.v; renderOverviewSection(); });
  if ($('ov-notesonly')) $('ov-notesonly').onclick = () => { S.ov.notesOnly = !S.ov.notesOnly; renderOverviewSection(); };
  if ($('ov-cartonly')) $('ov-cartonly').onclick = () => { S.ov.cartOnly = !S.ov.cartOnly; renderOverviewSection(); };
  wrap.querySelectorAll('[data-ov-res]').forEach(c => c.onclick = () => {
    const k = c.dataset.ovRes;
    if (k === '__all') S.ov.res = [];
    else { const set = new Set(S.ov.res || []); set.has(k) ? set.delete(k) : set.add(k); S.ov.res = [...set]; }
    renderOverviewSection();
  });
  // Text filter → update only the body (keep input focus).
  const q = $('ov-q');
  if (q) q.addEventListener('input', () => { S.ov.q = q.value; updateOverviewBody(); });
  wireOverview();
}
function updateOverviewBody() {
  const filtered = overviewFiltered();
  const c = $('ov-count'); if (c) c.textContent = filtered.length;
  const body = $('ov-body'); if (body) { body.innerHTML = overviewHtml(filtered); wireOverview(); }
}
const OV_CAP = 120;
function overviewHtml(rows) {
  if (!S.overview.length) return '<div class="qt-empty">Aún no hay personas en seguimiento. Busca una persona arriba y crea su plan.</div>';
  if (!rows.length) return '<div class="qt-empty">No hay personas que coincidan con el filtro.</div>';
  const shown = rows.slice(0, OV_CAP);
  const more = rows.length > OV_CAP ? `<div class="az-ov-more">Mostrando ${OV_CAP} de ${rows.length}. Afina el filtro (residencia, estado o búsqueda) para acotar.</div>` : '';
  return `<div class="az-cards">` + shown.map(r => {
    const p = r.person, inCart = S.cart.has(p.id);
    const note = r.note ? `<div class="az-ent-note az-ov-note" style="background:${esc(r.note.color || '#FEF08A')}">${esc(r.note.text)}</div>` : '';
    return `<div class="az-card ${r.ready_count ? 'has-ready' : ''}${r.note ? ' has-note' : ''}" data-open="${p.id}">
      <div class="az-card-actions">
        <button class="qt-iconbtn az-card-cart ${inCart ? 'has' : ''}" data-cart="${p.id}" title="${inCart ? 'Quitar del carrito' : 'Añadir al carrito'}">${inCart ? '✓🛒' : '🛒'}</button>
        <button class="qt-iconbtn az-card-note ${r.note ? 'has' : ''}" data-note="${p.id}" title="${r.note ? 'Editar nota' : 'Añadir nota'}">📝</button>
      </div>
      <div class="az-card-h"><span class="az-card-name">${esc(p.apellidos)}, ${esc(p.nombre)}</span>${statusChip(r)}</div>
      ${r.ready_count ? `<div class="az-card-ready">🔔 ${r.ready_count} caja(s) ya se pueden asignar</div>` : ''}
      <div class="az-card-sub">TIS ${esc(fmtTis(p.tis))}${p.pharmacy_no ? ' · Farmacia ' + esc(p.pharmacy_no) : ''}${(p.groups && p.groups.length) ? ' · 🏠 ' + esc(p.groups.join(' · ')) : ''}</div>
      <div class="az-card-sub">${r.plan_count} medicamento(s) en el plan · ${r.planned_total} caja(s)/mes${r.latest ? ' · último: ' + esc(fmtYm(r.latest.ym)) : ''}</div>
      ${note}
    </div>`;
  }).join('') + `</div>` + more;
}
function wireOverview() {
  main().querySelectorAll('.az-card[data-open]').forEach(el => el.addEventListener('click', e => { if (e.target.closest('[data-note],[data-cart]')) return; openPerson(Number(el.dataset.open)); }));
  main().querySelectorAll('[data-note]').forEach(b => b.addEventListener('click', e => {
    e.stopPropagation();
    const id = Number(b.dataset.note), row = S.overview.find(r => r.person.id === id);
    openNoteEditor({ subtitle: row ? `${row.person.apellidos}, ${row.person.nombre}` : '', endpoint: `/note/person/${id}`, current: row && row.note, onSaved: (note) => { if (row) row.note = note; renderOverviewSection(); } });
  }));
  main().querySelectorAll('[data-cart]').forEach(b => b.addEventListener('click', async e => { e.stopPropagation(); await toggleCart(Number(b.dataset.cart)); updateOverviewBody(); }));
}

// ── Cart of people (slide-over, like the other apps) ─────────────────────────────
async function reloadCart() { try { applyCart(await api('/cart')); } catch { /* keep */ } }
function applyCart(data) {
  S.cart = new Set(data.ids || []);
  S.cartPeople = new Map((data.items || []).map(it => [it.person.id, it]));
  updateCartCount();
}
function updateCartCount() { const b = $('cart-count'); if (b) b.textContent = S.cart.size; }
async function toggleCart(id) {
  try { applyCart(await api('/cart/' + id, { method: S.cart.has(id) ? 'DELETE' : 'POST' })); }
  catch (e) { toast(e.message, 'err'); }
}
function openCart() { $('cart-panel').classList.add('open'); $('scrim').hidden = false; renderCart(); }
function closeCart() { $('cart-panel').classList.remove('open'); $('scrim').hidden = true; }
function renderCart() {
  const panel = $('cart-panel'); if (!panel) return;
  const items = [...S.cartPeople.values()], size = 92;
  panel.innerHTML = `
    <div class="qt-cart-head"><h2>🛒 Carrito</h2><span class="qt-cart-count">${items.length}</span><button class="qt-x" id="cart-x">×</button></div>
    <div class="qt-cart-tools">
      <button class="qt-btn qt-btn-ghost qt-btn-sm" id="cart-hide">Ocultar</button>
      <button class="qt-btn ${S.ov.cartOnly ? 'qt-btn-teal' : 'qt-btn-ghost'} qt-btn-sm" id="cart-only">${S.ov.cartOnly ? '✓ ' : ''}Ver solo el carrito</button>
      <button class="qt-btn qt-btn-ghost qt-btn-sm" id="cart-pdf" ${items.length ? '' : 'disabled'} title="PDF de los precintos del mes de estas personas">📄 Precintos (PDF)</button>
      <button class="qt-btn qt-btn-danger qt-btn-sm" id="cart-empty" ${items.length ? '' : 'disabled'}>Vaciar</button>
    </div>
    <div class="qt-cart-body" id="cart-body">${items.length ? items.map(it => cartCardHtml(it, size)).join('') : '<div class="qt-empty">El carrito está vacío.<br>Añádelo desde las tarjetas de «En seguimiento» o desde la ficha de una persona.</div>'}</div>`;
  $('cart-x').onclick = closeCart; $('cart-hide').onclick = closeCart;
  $('cart-only').onclick = () => { S.ov.cartOnly = !S.ov.cartOnly; renderCart(); if (S.view === 'home') renderOverviewSection(); };
  if ($('cart-empty')) $('cart-empty').onclick = async () => {
    if (!(await confirmBox('Vaciar carrito', '¿Vaciar todo el carrito?', 'Vaciar'))) return;
    try { applyCart(await api('/cart', { method: 'DELETE' })); renderCart(); if (S.view === 'home') renderOverviewSection(); } catch (e) { toast(e.message, 'err'); }
  };
  if ($('cart-pdf')) $('cart-pdf').onclick = () => {
    const ym = (S.stickers && S.stickers.ym) || S.month;
    const params = new URLSearchParams({ ym, filter: 'all', order: 'person', persons: JSON.stringify([...S.cart]) });
    window.open(`${API}/stickers/pdf?${params.toString()}`, '_blank');
  };
  panel.querySelectorAll('[data-open]').forEach(el => el.onclick = () => { closeCart(); openPerson(Number(el.dataset.open)); });
  panel.querySelectorAll('[data-remove]').forEach(b => b.onclick = async () => { await toggleCart(Number(b.dataset.remove)); renderCart(); if (S.view === 'home') renderOverviewSection(); });
}
function cartCardHtml(it, size) {
  const p = it.person;
  const qr = p.active ? `<span class="qr" data-open="${p.id}">${qrSvg(p.tis, qrOpts(p, size))}</span>` : `<span class="qr" style="width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center;color:#9aa4b0;font-size:.8rem">Inactiva</span>`;
  const note = it.note ? `<div class="az-ent-note" style="background:${esc(it.note.color || '#FEF08A')};margin-top:8px">${esc(it.note.text)}</div>` : '';
  return `<div class="qt-cart-card">${qr}
    <div class="info">
      <div class="nm" data-open="${p.id}">${esc(p.apellidos)}, ${esc(p.nombre)}</div>
      <div class="ts">${p.pharmacy_no ? 'Farm. ' + esc(p.pharmacy_no) + ' · ' : ''}${esc(fmtTis(p.tis))}</div>
      ${(p.groups && p.groups.length) ? `<div class="ts">🏠 ${esc(p.groups.join(' · '))}</div>` : ''}
      <button class="qt-iconbtn danger" data-remove="${p.id}" title="Sacar del carrito" style="margin-top:8px">✕ Sacar</button>
      ${note}
    </div></div>`;
}

let searchTimer = null;
function searchPeople(q) {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    const box = $('pq-results'); if (!box) return;
    const query = String(q || '').trim();
    if (!query) { box.innerHTML = ''; return; }
    try {
      const { items } = await api('/people?q=' + encodeURIComponent(query));
      if (!items.length) {
        box.innerHTML = `<div class="az-noresult">No hay ninguna persona que coincida en <b>QR (TIS)</b>. Si es nueva, <a href="/qr-tis" target="_blank" rel="noopener">añádela primero en la app de QR (TIS)</a> y vuelve aquí.</div>`;
        return;
      }
      box.innerHTML = items.slice(0, 12).map(p => `<button class="az-result" data-pick="${p.id}"><span class="az-result-name">${esc(p.apellidos)}, ${esc(p.nombre)}</span><span class="az-result-tis">TIS ${esc(fmtTis(p.tis))}${p.pharmacy_no ? ' · Farm. ' + esc(p.pharmacy_no) : ''}</span></button>`).join('');
      box.querySelectorAll('[data-pick]').forEach(b => b.addEventListener('click', () => openPerson(Number(b.dataset.pick))));
    } catch (e) { box.innerHTML = `<div class="az-noresult">${esc(e.message)}</div>`; }
  }, 220);
}

// ── Open a person's ficha ────────────────────────────────────────────────────────
async function openPerson(id, ym) {
  stopStkScanner(true);
  try {
    const data = await api(`/person/${id}/ficha` + (ym ? '?ym=' + encodeURIComponent(ym) : ''));
    S.person = data.person; S.ficha = data; S.ym = data.ym; S.view = 'ficha';
    renderFicha();
  } catch (e) { toast(e.message, 'err'); }
}
async function reloadFicha() { if (S.person) await openPerson(S.person.id, S.ym); }
// Some endpoints return a full ficha payload — use it directly.
function applyFicha(data) { S.person = data.person; S.ficha = data; S.ym = data.ym; renderFicha(); refreshNotifications(); }

function renderFicha() {
  const f = S.ficha, p = f.person, per = f.period;
  const closed = per.status === 'cerrado';
  const isNew = per.status === 'nuevo';
  const dmSize = S.settings.ficha_dm_size, qrSize = S.settings.ficha_qr_size;

  // Month selector: known periods + the current month if missing.
  const known = new Map(f.periods.map(pr => [pr.ym, pr]));
  if (!known.has(f.month)) known.set(f.month, { ym: f.month, status: 'nuevo', counts: { preasignada: 0, asignada: 0, total: 0 } });
  if (!known.has(f.ym)) known.set(f.ym, { ym: f.ym, status: per.status, counts: { preasignada: 0, asignada: 0, total: 0 } });
  const months = [...known.values()].sort((a, b) => b.ym.localeCompare(a.ym));

  main().innerHTML =
    `<div class="qt-ficha-top"><button class="qt-back" id="back">← Volver</button></div>
     <div class="qt-panel qt-ficha az-ficha">
       <div class="qt-qr-stage az-personcard">
         <div class="qt-qr-name">${esc(p.nombre)} ${esc(p.apellidos)}</div>
         <div class="qt-qr-box" id="ficha-qr">${qrSvg(p.tis, qrOpts(p, qrSize))}</div>
         <div class="qt-qr-tis az-tisbig">${esc(fmtTis(p.tis))}</div>
         <div class="az-person-meta">${p.pharmacy_no ? 'Farmacia ' + esc(p.pharmacy_no) : ''}${p.group_name ? (p.pharmacy_no ? ' · ' : '') + esc(p.group_name) : ''}</div>
         <div class="az-person-note" id="ficha-note">${f.note ? `<div class="az-ent-note" style="background:${esc(f.note.color || '#FEF08A')}">${esc(f.note.text)}</div>` : ''}<div class="az-person-noteact"><button class="qt-btn qt-btn-ghost qt-btn-sm az-person-notebtn" id="ficha-note-btn">📝 ${f.note ? 'Editar nota' : 'Añadir nota'}</button><button class="qt-btn qt-btn-ghost qt-btn-sm" id="ficha-cart">${S.cart.has(p.id) ? '✓ En el carrito' : '🛒 Añadir al carrito'}</button></div></div>
         <div class="az-mando">
           <label>QR <input type="range" id="qr-size" min="160" max="460" step="10" value="${qrSize}"></label>
           <label>DM <input type="range" id="dm-size" min="90" max="240" step="10" value="${dmSize}"></label>
         </div>
       </div>

       <div class="qt-ficha-info az-fichainfo">
         <div class="az-monthbar">
           <label class="az-monthlabel">Mes</label>
           <select class="qt-select" id="month-sel">${months.map(m => `<option value="${m.ym}" ${m.ym === f.ym ? 'selected' : ''}>${esc(fmtYm(m.ym))}${m.status === 'cerrado' ? ' · cerrado' : m.status === 'nuevo' ? ' · nuevo' : ''}</option>`).join('')}</select>
           ${!isNew ? (closed ? `<button class="qt-btn qt-btn-ghost qt-btn-sm" id="per-reopen">↩ Reabrir</button>` : `<button class="qt-btn qt-btn-ghost qt-btn-sm" id="per-close">🔒 Cerrar mes</button>`) : ''}
           <span class="az-monthstate ${closed ? 'is-closed' : ''}">${isNew ? 'Mes nuevo (sin cajas todavía)' : closed ? 'Mes cerrado' : 'Mes abierto'}</span>
         </div>

         ${progressHtml(f.progress)}

         <div class="az-sec-h"><span>💊 Plan de medicación</span><span class="az-sec-h-actions az-plan-tools">
           <label class="az-plan-sortlbl">Ordenar <select class="qt-select qt-select-sm" id="plan-sort"><option value="def" ${S.planSort === 'def' ? 'selected' : ''}>Por defecto</option><option value="nombre" ${S.planSort === 'nombre' ? 'selected' : ''}>Nombre</option><option value="cn" ${S.planSort === 'cn' ? 'selected' : ''}>CN</option></select></label>
           <div class="az-seg az-planview" id="plan-view"><button type="button" data-pv="full" class="${S.planView === 'full' ? 'on' : ''}" title="Vista completa">▤</button><button type="button" data-pv="list" class="${S.planView === 'list' ? 'on' : ''}" title="Lista compacta">≣</button><button type="button" data-pv="cards" class="${S.planView === 'cards' ? 'on' : ''}" title="Tarjetas compactas">▦</button></div>
           <button class="qt-btn qt-btn-ghost qt-btn-sm" id="plan-dup" title="Buscar CN/medicamentos duplicados">🔁 Duplicados</button>
           <button class="qt-btn qt-btn-ghost qt-btn-sm" id="add-med">➕ Añadir medicamento</button>
         </span></div>
         <div class="az-plan az-planmode-${S.planView}">${planHtml(f.plan, closed)}</div>

         <div class="az-sec-h"><span>📦 Cajas de la ficha (${f.lines.length})</span><span class="az-sec-h-actions">${closed ? '' : `<button class="qt-btn qt-btn-teal qt-btn-sm" id="scan-mode" title="Modo escáner: pasa el lector por el precinto o el DM y se asigna solo">📟 Modo escáner</button>`}<button class="qt-btn qt-btn-ghost qt-btn-sm" id="add-box" ${closed ? 'disabled' : ''}>➕ Añadir DM</button></span></div>
         <div class="az-lines">${linesHtml(f.lines, closed, dmSize)}</div>
         ${precintoHtml(f.precintos, closed)}
         ${pendingHtml(f.plan, closed)}
       </div>
     </div>`;

  $('back').onclick = viewHome;
  $('month-sel').onchange = (e) => openPerson(p.id, e.target.value);
  if ($('per-close')) $('per-close').onclick = async () => { try { applyFicha(await api(`/period/${per.id}/close`, { method: 'POST' })); toast('Mes cerrado.'); } catch (er) { toast(er.message, 'err'); } };
  if ($('per-reopen')) $('per-reopen').onclick = async () => { try { applyFicha(await api(`/period/${per.id}/reopen`, { method: 'POST' })); toast('Mes reabierto.'); } catch (er) { toast(er.message, 'err'); } };
  $('add-med').onclick = openMedPicker;
  if ($('plan-sort')) $('plan-sort').onchange = (e) => { S.planSort = e.target.value; try { localStorage.setItem('asig_plan_sort', S.planSort); } catch {} renderFicha(); };
  if ($('plan-view')) $('plan-view').querySelectorAll('[data-pv]').forEach(b => b.onclick = () => { S.planView = b.dataset.pv; try { localStorage.setItem('asig_plan_view', S.planView); } catch {} renderFicha(); });
  if ($('plan-dup')) $('plan-dup').onclick = findPlanDuplicates;
  if ($('add-box')) $('add-box').onclick = () => openAddBox(null);
  if ($('scan-mode')) $('scan-mode').onclick = () => toggleScannerMode(p.id);
  if (scanner.on && scanner.personId === p.id) renderScannerPanel(); else stopScannerMode(true);
  if ($('ficha-note-btn')) $('ficha-note-btn').onclick = () => openNoteEditor({
    subtitle: `${p.apellidos}, ${p.nombre}`, endpoint: `/note/person/${p.id}`, current: f.note,
    onSaved: (note) => { S.ficha.note = note; renderFicha(); },
  });
  if ($('ficha-cart')) $('ficha-cart').onclick = async () => { await toggleCart(p.id); const b = $('ficha-cart'); if (b) b.textContent = S.cart.has(p.id) ? '✓ En el carrito' : '🛒 Añadir al carrito'; };

  // Live size sliders (persist, debounced).
  $('qr-size').oninput = (e) => { const v = Number(e.target.value); $('ficha-qr').innerHTML = qrSvg(p.tis, qrOpts(p, v)); saveSize({ ficha_qr_size: v }); };
  $('dm-size').oninput = (e) => { const v = Number(e.target.value); S.settings.ficha_dm_size = v; document.querySelectorAll('.az-line-dm').forEach(el => { const raw = el.dataset.raw, color = el.dataset.color; el.innerHTML = dmSvg(raw, { dark: color, light: '#ffffff', size: v }); }); saveSize({ ficha_dm_size: v }); };

  wirePlan(closed); wireLines(closed);
}

function progressHtml(pr) {
  const pend = Math.max(pr.planned_total, pr.attached_total);
  return `<div class="az-progress">
    <div class="az-prog-item"><span class="az-prog-n">${pr.planned_total}</span><span class="az-prog-l">plan (cajas/mes)</span></div>
    <div class="az-prog-item"><span class="az-prog-n">${pr.attached_total}</span><span class="az-prog-l">en la ficha</span></div>
    <div class="az-prog-item az-prog-pre"><span class="az-prog-n">${pr.pre_total}</span><span class="az-prog-l">🔗 por asignar</span></div>
    <div class="az-prog-item az-prog-done"><span class="az-prog-n">${pr.asignada_total}</span><span class="az-prog-l">✓ asignadas</span></div>
  </div>`;
}

function planDupKey(m) { return String(m.cn || m.gtin || ('n:' + (m.nombre || ''))); }
function sortedPlan(plan) {
  const s = S.planSort || 'def';
  if (s === 'cn') return plan.slice().sort((a, b) => String(a.cn || a.gtin || '~').localeCompare(String(b.cn || b.gtin || '~'), 'es', { numeric: true }));
  if (s === 'nombre') return plan.slice().sort((a, b) => String(a.nombre || '~').localeCompare(String(b.nombre || '~'), 'es'));
  return plan;
}
// Plan renderer. Three views: 'full' (default, complete), 'list' and 'cards'
// (both compact, to see 10-15 medications at a glance). Sorted per S.planSort.
function planHtml(plan, closed) {
  if (!plan.length) return '<div class="az-empty-sm">Sin medicamentos en el plan. Pulsa «➕ Añadir medicamento».</div>';
  const list = sortedPlan(plan);
  if (S.planView === 'list') return `<div class="az-plan-simple-list">${list.map(planRowSimple).join('')}</div>`;
  if (S.planView === 'cards') return `<div class="az-plan-simple-cards">${list.map(planCardSimple).join('')}</div>`;
  return list.map(m => planRowFull(m, closed)).join('');
}
// Compact one-line row (view: Lista).
function planRowSimple(m) {
  const done = m.asignada || 0, need = m.qty, ok = done >= need;
  const icon = m.foto_caja ? `<img class="az-plan-sfoto" src="${fotoUrl(m.cn, 'caja')}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{}))">` : shapeSvg(m.shape, m.color, 15);
  return `<div class="az-plan-srow" data-dupkey="${esc(planDupKey(m))}">
    <span class="az-plan-sicon">${icon}</span>
    <span class="az-plan-sname">${esc(m.nombre || 'Sin nombre')}</span>
    <span class="az-plan-scn">${m.cn ? 'CN ' + esc(m.cn) : (m.gtin ? esc(m.gtin) : '—')}</span>
    <span class="az-plan-sqty">×${m.qty}</span>
    <span class="az-plan-sprog ${ok ? 'is-ok' : 'is-short'}">${done}/${need}</span>
  </div>`;
}
// Compact small card (view: Tarjetas).
function planCardSimple(m) {
  const done = m.asignada || 0, need = m.qty, ok = done >= need;
  const icon = m.foto_caja ? `<img class="az-plan-cfoto" src="${fotoUrl(m.cn, 'caja')}" alt="" loading="lazy" onerror="this.style.display='none'">` : shapeSvg(m.shape, m.color, 26);
  return `<div class="az-plan-scard" data-dupkey="${esc(planDupKey(m))}">
    <div class="az-plan-scard-ico">${icon}</div>
    <div class="az-plan-scard-body"><b>${esc(m.nombre || 'Sin nombre')}</b><small>${m.cn ? 'CN ' + esc(m.cn) : (m.gtin ? esc(m.gtin) : '')}</small>
      <span class="az-plan-sprog ${ok ? 'is-ok' : 'is-short'}">×${m.qty} · ${done}/${need}</span></div>
  </div>`;
}
function planRowFull(m, closed) {
    const need = m.qty, done = m.asignada || 0, boxes = m.boxes || 0, prec = m.precinto || 0;
    const short = done < need;
    // CN-only meds (info before any Data Matrix) show the national code and a
    // "pendiente de caja" flag; catalogued meds show the GTIN + stock.
    const idline = m.cn_only
      ? `CN ${esc(m.cn || '—')}${m.barcode ? ' · CB ' + esc(m.barcode) : ''} · <b class="az-plan-flag">pendiente de caja</b>${m.available ? ` · ${m.available} compatible(s) en stock` : ''}`
      : `GTIN ${esc(m.gtin)} · ${m.available} disponible(s) en stock`;
    // Box photo (CIMA) instead of the colour shape when we have it cached; click to enlarge.
    const icon = m.foto_caja
      ? `<button class="az-plan-foto-btn" data-boxfoto="${m.id}" title="Ver la caja en grande"><img class="az-plan-foto" src="${fotoUrl(m.cn, 'caja')}" alt="Caja" loading="lazy" onerror="this.style.display='none'"></button>`
      : shapeSvg(m.shape, m.color, 22);
    // "No DM" = no real Data Matrix box in the ficha (precintos don't count).
    const noDm = boxes === 0;
    // Precinto = scannable barcode for Salud. Inline (right) while there's no Data
    // Matrix; behind the 🏷️ button once a DM box exists (the DM is preferred).
    const bcInline = (noDm && m.barcode) ? `<div class="az-plan-bc" data-precinto="${m.id}" title="Ampliar el precinto">${eanSvg(m.barcode)}</div>` : '';
    const progTxt = `${done}/${need} asignadas${boxes ? ' · ' + boxes + ' en ficha' : ''}${prec ? ' · ' + prec + ' por precinto' : ''}`;
    // Manual "mark assigned in Salud" (by precinto, no box) while units remain and
    // there's no DM box to assign from.
    const canPrecinto = !closed && noDm && done < need;
    return `<div class="az-planrow${m.cn_only ? ' is-cnonly' : ''}" data-plan-row="${m.id}" data-dupkey="${esc(planDupKey(m))}">
      <span class="az-plan-shape">${icon}</span>
      <div class="az-plan-name">${esc(m.nombre || 'Sin nombre')}<small>${idline}</small><div class="az-plan-meta">${planReleaseChip(m)}<span class="az-plan-prog ${short ? 'is-short' : 'is-ok'}">${progTxt}</span></div></div>
      ${bcInline}
      <div class="az-plan-actions">
        <span class="az-plan-qty">×<input type="number" class="az-qty" data-plan="${m.id}" value="${m.qty}" min="1" max="99" ${closed ? 'disabled' : ''}></span>
        ${(!noDm && m.barcode) ? `<button class="qt-iconbtn" data-precinto="${m.id}" title="Ver el código de barras (precinto)">🏷️</button>` : ''}
        ${m.foto_pastilla ? `<button class="qt-iconbtn" data-pill="${m.id}" title="Ver la pastilla (AEMPS)">💊</button>` : ''}
        ${canPrecinto ? `<button class="qt-btn qt-btn-teal qt-btn-sm" data-assignprec="${m.id}" title="Marcar como asignada en Salud (por precinto, sin caja)">✅ Asignar</button>` : ''}
        ${closed ? '' : `<button class="qt-btn qt-btn-ghost qt-btn-sm" data-assoc="${m.id}">🔗 ${m.cn_only ? 'Asociar caja' : 'Pre-asignar'}</button>`}
        ${(!closed && m.cn_only) ? `<button class="qt-iconbtn" data-editplan="${m.id}" title="Editar nombre / CN / código de barras">✏️</button>` : ''}
        <button class="qt-iconbtn danger" data-delplan="${m.id}" title="Quitar del plan">🗑</button>
      </div>
    </div>`;
}
// Highlight medications that share the same CN/GTIN (or name) within the plan.
function findPlanDuplicates() {
  const plan = (S.ficha && S.ficha.plan) || [];
  const seen = new Set(), dups = new Set();
  for (const m of plan) { const k = planDupKey(m); if (seen.has(k)) dups.add(k); else seen.add(k); }
  main().querySelectorAll('[data-dupkey]').forEach(el => el.classList.toggle('is-dup', dups.has(el.dataset.dupkey)));
  toast(dups.size ? `${dups.size} medicamento(s) duplicado(s) resaltado(s) en el plan.` : 'Sin duplicados en el plan.', dups.size ? 'err' : 'ok');
}
// Release-state chip for a plan medication. The state (and colour) is driven by
// its Salud release date + anticipation. Clickable → set/edit the date.
function planReleaseChip(m) {
  const off = m.release_at ? fmtDate(m.release_at) : null;
  const eff = m.effective_at ? fmtDate(m.effective_at) : null;
  const adv = m.advance_days != null ? m.advance_days : 15;
  const sub = (off && adv > 0) ? ` <small class="az-rel-off">(${off})</small>` : '';
  if (m.release_state === 'sin_fecha')
    return `<button type="button" class="az-rel az-rel-none az-rel-click" data-planrel="${m.id}" title="Poner fecha de liberación (Salud)">🗓 Sin fecha — pendiente</button>`;
  if (m.release_state === 'disponible')
    return `<button type="button" class="az-rel az-rel-ready az-rel-click" data-planrel="${m.id}" title="Cambiar fecha o días de anticipación">✅ Disponible${eff ? ' desde ' + eff : ''}${sub}</button>`;
  const when = m.effective_days === 0 ? 'hoy' : m.effective_days === 1 ? 'mañana' : 'faltan ' + m.effective_days + ' días';
  return `<button type="button" class="az-rel az-rel-soon az-rel-click" data-planrel="${m.id}" title="Cambiar fecha o días de anticipación">🗓 Disponible ${eff} · ${when}${sub}</button>`;
}
function wirePlan(closed) {
  main().querySelectorAll('[data-delplan]').forEach(b => b.addEventListener('click', async () => {
    if (!(await confirmBox('Quitar del plan', '¿Quitar este medicamento del plan de la persona? No afecta a las cajas ya asignadas.', 'Quitar'))) return;
    try { const { plan } = await api('/plan/' + b.dataset.delplan, { method: 'DELETE' }); S.ficha.plan = mergePlan(S.ficha.plan, plan); renderFicha(); } catch (e) { toast(e.message, 'err'); }
  }));
  main().querySelectorAll('.az-qty').forEach(inp => inp.addEventListener('change', async () => {
    try { await api('/plan/' + inp.dataset.plan, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ qty: Number(inp.value) }) }); await reloadFicha(); } catch (e) { toast(e.message, 'err'); }
  }));
  main().querySelectorAll('[data-assoc]').forEach(b => b.addEventListener('click', () => {
    const med = (S.ficha.plan || []).find(x => x.id === Number(b.dataset.assoc)); if (med) openAddBox(med);
  }));
  main().querySelectorAll('[data-planrel]').forEach(b => b.addEventListener('click', () => {
    const med = (S.ficha.plan || []).find(x => x.id === Number(b.dataset.planrel)); if (med) openPlanReleasePicker(med);
  }));
  main().querySelectorAll('[data-editplan]').forEach(b => b.addEventListener('click', () => {
    const med = (S.ficha.plan || []).find(x => x.id === Number(b.dataset.editplan)); if (med) openEditMed(med);
  }));
  const findMed = (id) => (S.ficha.plan || []).find(x => x.id === Number(id));
  main().querySelectorAll('[data-boxfoto]').forEach(b => b.addEventListener('click', () => { const m = findMed(b.dataset.boxfoto); if (m) openImageModal(m, 'caja', 'Imagen de la caja', '📦'); }));
  main().querySelectorAll('[data-pill]').forEach(b => b.addEventListener('click', () => { const m = findMed(b.dataset.pill); if (m) openImageModal(m, 'pastilla', 'Imagen de la forma farmacéutica', '💊'); }));
  main().querySelectorAll('[data-precinto]').forEach(b => b.addEventListener('click', () => { const m = findMed(b.dataset.precinto); if (m) openPrecinto(m); }));
  main().querySelectorAll('[data-assignprec]').forEach(b => b.addEventListener('click', () => { const m = findMed(b.dataset.assignprec); if (m) openPrecintoAssign(m); }));
}
// Manually mark a medication as "assigned in Salud" by its precinto (no box). Also
// captures the medication's NEXT release date (prefilled: same day next month).
function openPrecintoAssign(med) {
  const prefill = sameDayNextMonth(med.release_at);
  const bc = med.barcode ? eanSvg(med.barcode) : '';
  openTool(`<div class="qt-modal-h"><h3>✅ Asignar en Salud (precinto)</h3><button class="qt-x" id="ap-close">×</button></div>
    <p class="qt-tool-note">Marca una unidad de <b>${esc(med.nombre || 'este medicamento')}</b> como <b>asignada en Salud</b> mediante su <b>precinto</b> (código de barras), sin registrar caja (Data Matrix). Cuenta como asignada del mes.</p>
    ${bc ? `<div class="az-precinto az-precinto-sm">${bc}</div><div class="az-precinto-num">${esc(med.barcode)}</div>` : '<p class="qt-tool-note">Este medicamento no tiene código de barras guardado, pero puedes marcarlo igualmente.</p>'}
    <div class="qt-field"><label>Próxima fecha de liberación (Salud)</label><input type="date" class="qt-input" id="ap-date" value="${esc(prefill)}"><small class="az-field-hint">Propuesta: mismo día del mes siguiente. Déjala vacía si aún no la sabes.</small></div>
    <div class="qt-modal-actions">
      <button class="qt-btn qt-btn-ghost" id="ap-cancel">Cancelar</button>
      <button class="qt-btn qt-btn-teal" id="ap-do">✅ Asignar</button>
    </div>`);
  $('ap-close').onclick = closeTool; $('ap-cancel').onclick = closeTool;
  $('ap-do').onclick = async () => {
    const v = $('ap-date').value;
    if (v && !/^\d{4}-\d{2}-\d{2}$/.test(v)) { toast('Fecha no válida.', 'err'); return; }
    try { applyFicha(await api('/person/' + S.person.id + '/assign-precinto', jbody({ plan_id: med.id, ym: S.ym, next_release_at: v || '' }))); closeTool(); toast('Asignada en Salud (precinto).'); }
    catch (e) { toast(e.message, 'err'); }
  };
}
// Show the box barcode ("precinto") as a scannable EAN-13 for the Salud app.
function openPrecinto(med) {
  const bc = eanSvg(med.barcode);
  openTool(`<div class="qt-modal-h"><h3>🏷️ Precinto (código de barras)</h3><button class="qt-x" id="pc-close">×</button></div>
    <p class="qt-tool-note"><b>${esc(med.nombre || 'Medicamento')}</b><br>Escanéalo en la <b>app de Salud</b> para asignar, mientras esta caja no tenga <b>Data Matrix</b>. Si tienes DM, escanea el DM (es mejor).</p>
    <div class="az-precinto">${bc || '<div class="az-noresult">No hay código de barras para este medicamento.</div>'}</div>
    <div class="az-precinto-num">${esc(med.barcode || '')}</div>`);
  $('pc-close').onclick = closeTool;
}
// Keep progress fields (attached/asignada) when the server returns a bare plan list.
function mergePlan(oldPlan, fresh) { const by = new Map((oldPlan || []).map(p => [p.id, p])); return fresh.map(p => ({ ...p, attached: (by.get(p.id) || {}).attached || 0, asignada: (by.get(p.id) || {}).asignada || 0 })); }

function lineHtml(ln, closed, dmSize) {
  const box = ln.box;
  if (!box) return `<div class="az-line az-line-gone"><div class="az-line-info"><b>Caja eliminada</b><small>La caja ya no existe en Data Matrix.</small></div><button class="qt-iconbtn danger" data-delline="${ln.id}" title="Quitar">🗑</button></div>`;
  const asignada = ln.state === 'asignada';
  const cls = asignada ? 'is-asignada' : 'is-pre';
  return `<div class="az-line ${cls}" data-id="${ln.id}">
    <div class="az-line-dm ${asignada ? 'is-grey' : ''}" data-raw="${esc(box.raw)}" data-color="${esc(box.color)}">${dmSvg(box.raw, { dark: asignada ? '#9aa7b4' : box.color, light: '#ffffff', size: dmSize })}</div>
    <div class="az-line-info">
      <b>${shapeSvg(box.shape, box.color, 14)} ${esc(box.nombre || 'Sin nombre')}</b>
      <small>${box.serial ? 'Nº ' + esc(box.serial) + ' · ' : ''}${box.caducidad ? 'Cad ' + cadDisplay(box.caducidad) : 'GTIN ' + esc(box.gtin || '—')}</small>
      <span class="az-line-state ${asignada ? 'st-done' : 'st-pre'}">${asignada ? '✓ Asignada' + (ln.assigned_at ? ' · ' + fmtDate(ln.assigned_at) : '') : '🔗 Pre-asignada'}</span>
    </div>
    <div class="az-line-actions">
      ${asignada
        ? (closed ? '' : `<button class="qt-btn qt-btn-ghost qt-btn-sm" data-unassign="${ln.id}">↩ Revertir</button>`)
        : (closed ? '' : `<button class="qt-btn qt-btn-teal qt-btn-sm" data-assign="${ln.id}">✅ Asignar</button>`)}
      ${closed ? '' : `<button class="qt-iconbtn danger" data-delline="${ln.id}" title="Quitar de la ficha">🗑</button>`}
    </div>
  </div>`;
}
function linesHtml(lines, closed, dmSize) {
  if (!lines.length) return '<div class="az-empty-sm">Todavía no hay cajas en la ficha. Pre-asigna desde el plan o pulsa «➕ Añadir DM».</div>';
  // Group by medication.
  const groups = new Map();
  for (const ln of lines) { const g = (ln.box && ln.box.gtin) || ln.gtin || '—'; if (!groups.has(g)) groups.set(g, []); groups.get(g).push(ln); }
  return [...groups.entries()].map(([g, arr]) => {
    const sample = arr.find(x => x.box) || arr[0];
    const name = (sample.box && sample.box.nombre) || 'Sin nombre';
    return `<div class="az-linegroup"><div class="az-linegroup-h">${sample.box ? shapeSvg(sample.box.shape, sample.box.color, 16) : ''} ${esc(name)} <span class="az-lg-count">×${arr.length}</span></div>
      <div class="az-linegrid">${arr.map(ln => lineHtml(ln, closed, dmSize)).join('')}</div></div>`;
  }).join('');
}
// Pending medications (no Data Matrix this month) shown in the boxes section, with
// their box photo and a scannable EAN-13 "precinto" for the Salud app.
function pendingHtml(plan, closed) {
  const pend = (plan || []).filter(m => m.active && (m.boxes || 0) === 0 && (m.asignada || 0) < m.qty);
  if (!pend.length) return '';
  return `<div class="az-pend-h">🏷️ Pendientes de caja — pásale el escáner al <b>precinto</b> (o escanéalo en Salud) mientras no haya Data Matrix</div>
    <div class="az-pendgrid">${pend.map(m => {
      const icon = m.foto_caja
        ? `<button class="az-plan-foto-btn" data-boxfoto="${m.id}" title="Ver la caja en grande"><img class="az-pend-foto" src="${fotoUrl(m.cn, 'caja')}" alt="Caja" loading="lazy" onerror="this.style.display='none'"></button>`
        : `<span class="az-plan-shape">${shapeSvg(m.shape, m.color, 28)}</span>`;
      const bc = m.barcode ? eanSvg(m.barcode) : '';
      const done = m.asignada || 0, prec = m.precinto || 0;
      const prog = (done > 0) ? `<div class="az-pend-prog">✅ ${done}/${m.qty} asignada(s)${prec ? ' (precinto)' : ''}</div>` : '';
      return `<div class="az-pendcard">
        <div class="az-pend-top">${icon}<div class="az-pend-info"><b>${esc(m.nombre || 'Medicamento')}</b><small>${m.cn ? 'CN ' + esc(m.cn) : ''}${m.barcode ? ' · CB ' + esc(m.barcode) : ''}</small></div></div>
        ${bc ? `<div class="az-pend-ean" data-precinto="${m.id}" title="Ampliar el precinto">${bc}</div>` : '<div class="az-empty-sm">Sin código de barras. Añádelo con ✏️ en el plan o con «🔎 CIMA».</div>'}
        ${prog}
        <div class="az-pend-actions">
          ${m.foto_pastilla ? `<button class="qt-iconbtn" data-pill="${m.id}" title="Ver la pastilla (AEMPS)">💊</button>` : ''}
          ${closed ? '' : `<button class="qt-btn qt-btn-teal qt-btn-sm" data-assignprec="${m.id}" title="Marcar como asignada en Salud (precinto)">✅ Asignar</button>`}
          ${closed ? '' : `<button class="qt-btn qt-btn-ghost qt-btn-sm" data-assoc="${m.id}">🔗 Asociar caja</button>`}
        </div>
      </div>`;
    }).join('')}</div>`;
}
// Assignments recorded by "precinto" (no Data Matrix box). Shown in the boxes
// section so they read as "already assigned in Salud", each revertible.
function precintoHtml(precintos, closed) {
  const list = precintos || [];
  if (!list.length) return '';
  return `<div class="az-prec-h">✅ Asignadas por precinto (sin caja) — ${list.length}</div>
    <div class="az-precgrid">${list.map(pc => `<div class="az-preccard" data-precid="${pc.id}">
      <div class="az-prec-body"><b>${esc(pc.nombre || 'Medicamento')}</b><small>${pc.cn ? 'CN ' + esc(pc.cn) : ''}${pc.barcode ? ' · CB ' + esc(pc.barcode) : ''}${pc.assigned_at ? ' · ' + fmtDate(pc.assigned_at) : ''}</small></div>
      <div class="az-prec-actions">${closed ? '' : `<button class="qt-btn qt-btn-ghost qt-btn-sm" data-delprec="${pc.id}" title="Revertir esta asignación">↩ Revertir</button>`}</div>
    </div>`).join('')}</div>`;
}
function wireLines(closed) {
  main().querySelectorAll('[data-assign]').forEach(b => b.addEventListener('click', () => {
    const ln = (S.ficha.lines || []).find(x => x.id === Number(b.dataset.assign)); if (ln) openAssignModal(ln);
  }));
  main().querySelectorAll('[data-unassign]').forEach(b => b.addEventListener('click', async () => {
    try { applyFicha(await api('/line/' + b.dataset.unassign + '/unassign', { method: 'POST' })); toast('Asignación revertida (vuelve a pre-asignada).'); } catch (e) { toast(e.message, 'err'); }
  }));
  main().querySelectorAll('[data-delline]').forEach(b => b.addEventListener('click', async () => {
    if (!(await confirmBox('Quitar caja', '¿Quitar esta caja de la ficha? Se libera la reserva y, si estaba asignada, vuelve al inventario.', 'Quitar'))) return;
    try { applyFicha(await api('/line/' + b.dataset.delline, { method: 'DELETE' })); toast('Caja retirada de la ficha.'); } catch (e) { toast(e.message, 'err'); }
  }));
  main().querySelectorAll('[data-delprec]').forEach(b => b.addEventListener('click', async () => {
    if (!(await confirmBox('Revertir asignación', '¿Revertir esta asignación por precinto? Vuelve a quedar pendiente.', 'Revertir'))) return;
    try { applyFicha(await api('/precinto/' + b.dataset.delprec, { method: 'DELETE' })); toast('Asignación revertida.'); } catch (e) { toast(e.message, 'err'); }
  }));
}

// ── Scanner mode ─────────────────────────────────────────────────────────────────
// "Disposes" the app to receive keyboard input from a barcode scanner (which emulates
// a keyboard: it types the code + Enter). Each Enter assigns the medication directly
// and the panel keeps listening. Works for a DM (associates + assigns the box) or a
// plain precinto barcode (marks assigned without a box).
const scanner = { on: false, personId: null, buf: '', timer: null, handler: null, log: [], busy: false };
function toggleScannerMode(personId) { if (scanner.on && scanner.personId === personId) stopScannerMode(); else startScannerMode(personId); }
function startScannerMode(personId) {
  stopScannerMode(true);
  scanner.on = true; scanner.personId = personId; scanner.buf = ''; scanner.log = [];
  scanner.handler = onScannerKey;
  document.addEventListener('keydown', scanner.handler, true);
  renderScannerPanel();
  const btn = $('scan-mode'); if (btn) btn.classList.add('is-on');
}
function stopScannerMode(silent) {
  if (scanner.handler) { document.removeEventListener('keydown', scanner.handler, true); scanner.handler = null; }
  if (scanner.timer) { clearTimeout(scanner.timer); scanner.timer = null; }
  scanner.on = false; scanner.buf = '';
  const panel = $('scan-panel'); if (panel) panel.remove();
  const btn = $('scan-mode'); if (btn) btn.classList.remove('is-on');
  if (!silent) toast('Modo escáner desactivado.');
}
function isEditableTarget(t) {
  if (!t) return false;
  const tag = (t.tagName || '').toLowerCase();
  return tag === 'input' || tag === 'textarea' || tag === 'select' || t.isContentEditable;
}
function onScannerKey(e) {
  if (!scanner.on) return;
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  if (isEditableTarget(e.target)) return;          // let the user type in real fields
  if (e.key === 'Enter') {
    if (scanner.buf) { e.preventDefault(); const code = scanner.buf; scanner.buf = ''; processScan(code); }
    return;
  }
  if (e.key && e.key.length === 1) {
    scanner.buf += e.key;
    if (scanner.timer) clearTimeout(scanner.timer);
    scanner.timer = setTimeout(() => { scanner.buf = ''; }, 400);   // stray keys don't linger
  }
}
async function processScan(code) {
  if (scanner.busy) return;
  scanner.busy = true;
  try {
    const r = await api('/person/' + scanner.personId + '/scan', jbody({ code, ym: S.ym }));
    scannerLog('ok', `${r.mode === 'dm' ? '📦' : '🏷️'} ${r.med.nombre || 'Medicamento'} · asignada${r.next_release_at ? ' · próxima ' + fmtDate(r.next_release_at) : ''}`);
    if (r.ficha) { S.person = r.ficha.person; S.ficha = r.ficha; S.ym = r.ficha.ym; renderFicha(); refreshNotifications(); }
  } catch (e) {
    scannerLog('err', e.data && e.data.nomatch ? `«${code}» no está en el plan de esta persona` : (e.message || 'Error al escanear') + ` («${code}»)`);
  } finally { scanner.busy = false; }
}
function scannerLog(kind, msg) {
  scanner.log.unshift({ kind, msg, at: new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) });
  if (scanner.log.length > 30) scanner.log.length = 30;
  renderScannerLog();
}
function renderScannerPanel() {
  const markBtn = () => { const b = $('scan-mode'); if (b) b.classList.add('is-on'); };
  if ($('scan-panel')) { renderScannerLog(); markBtn(); return; }
  const el = document.createElement('div');
  el.className = 'az-scanpanel'; el.id = 'scan-panel';
  el.innerHTML = `<div class="az-scanpanel-h"><span class="az-scan-live">📟 Modo escáner <span class="az-scan-dot"></span></span><button class="qt-x" id="scan-panel-x" title="Salir del modo escáner">×</button></div>
    <p class="az-scanpanel-note">Pasa el escáner por el <b>precinto</b> o el <b>Data Matrix</b>. Cada lectura se asigna sola (próxima liberación: mismo día del mes que viene). No hace falta clicar.</p>
    <div class="az-scanlog" id="scan-log"></div>`;
  document.body.appendChild(el);
  $('scan-panel-x').onclick = () => stopScannerMode();
  renderScannerLog();
  const btn = $('scan-mode'); if (btn) btn.classList.add('is-on');
}
function renderScannerLog() {
  const box = $('scan-log'); if (!box) return;
  box.innerHTML = scanner.log.length
    ? scanner.log.map(e => `<div class="az-scanline ${e.kind === 'ok' ? 'is-ok' : 'is-err'}"><span class="az-scan-ic">${e.kind === 'ok' ? '✓' : '✗'}</span><span class="az-scan-msg">${esc(e.msg)}</span><span class="az-scan-at">${esc(e.at)}</span></div>`).join('')
    : '<div class="az-scan-empty">Esperando lecturas…</div>';
}

// ── Control de precintos (pegado en la hoja oficial de Salud) ─────────────────────
async function loadStickers(ym) {
  const body = $('stk-body'); if (!body) return;
  try { S.stickers = await api('/stickers' + (ym ? '?ym=' + encodeURIComponent(ym) : '')); S.stkYm = S.stickers.ym; }
  catch (e) { body.innerHTML = `<div class="az-noresult">No se pudo cargar el control de precintos: ${esc(e.message)}</div>`; return; }
  renderStickers();
}
function shortLabel(s) { s = String(s || ''); return s.length > 20 ? s.slice(0, 19) + '…' : s; }
function itemsAttr(items) { return JSON.stringify(items.map(i => ({ source: i.source, id: i.id }))); }
function renderStickers() {
  const body = $('stk-body'); if (!body) return;
  const d = S.stickers; if (!d) { body.innerHTML = '<div class="az-empty-sm">Cargando…</div>'; return; }
  const ym = d.ym, t = d.totals, showP = S.stkShowPegados;
  const months = (d.months && d.months.length) ? d.months.slice() : [];
  if (!months.some(m => m.ym === ym)) months.unshift({ ym, total: t.total });
  const monthOpts = months.map(m => `<option value="${m.ym}" ${m.ym === ym ? 'selected' : ''}>${esc(fmtYm(m.ym))} · ${m.total} precinto(s)</option>`).join('');

  // Flatten items with their medication meta, then apply the medication filter +
  // pegados visibility. This drives grouping (by med or by person) and bulk actions.
  const allItems = [];
  for (const g of d.groups) for (const i of g.items) allItems.push({ ...i, medKey: g.key, medNombre: g.nombre, medCn: g.cn, medBarcode: g.barcode, resKey: i.residencia || 'Sin grupo' });
  const medFilter = S.stkFilter || [], resFilter = S.stkFilterRes || [], status = S.stkStatus || 'pending', notesOnly = !!S.stkNotesOnly;
  const inMed = (k) => medFilter.length === 0 || medFilter.includes(k);
  const inRes = (r) => resFilter.length === 0 || resFilter.includes(r);
  const inStatus = (i) => status === 'all' ? true : status === 'pegados' ? i.pegado : !i.pegado;
  const visible = allItems.filter(i => inMed(i.medKey) && inRes(i.resKey) && inStatus(i) && (!notesOnly || (i.note && i.note.text)));
  const visiblePending = visible.filter(i => !i.pegado);
  const pendingItems = visiblePending.map(i => ({ source: i.source, id: i.id }));

  // Medication filter chips (with pending counts).
  const medChips = `<button class="az-stk-chip ${medFilter.length === 0 ? 'on' : ''}" data-stk-chip="__all">Todos <b>${t.por_pegar}</b></button>` +
    d.groups.map(g => { const p = g.items.filter(i => !i.pegado).length; return `<button class="az-stk-chip ${medFilter.includes(g.key) ? 'on' : ''} ${p === 0 ? 'is-done' : ''}" data-stk-chip="${esc(g.key)}" title="${esc(g.nombre || '')}${g.cn ? ' · CN ' + esc(g.cn) : ''}">${esc(shortLabel(g.nombre || g.cn || g.key))} <b>${p}</b></button>`; }).join('');
  // Residence (grupo de QR·TIS) chips — cumulative with the medication filter.
  const resMap = new Map();
  for (const i of allItems) { const k = i.resKey; if (!resMap.has(k)) resMap.set(k, 0); if (!i.pegado) resMap.set(k, resMap.get(k) + 1); }
  const resKeys = [...resMap.keys()].sort((a, b) => a === 'Sin grupo' ? 1 : b === 'Sin grupo' ? -1 : a.localeCompare(b));
  const hasResidencias = resKeys.length > 1 || (resKeys.length === 1 && resKeys[0] !== 'Sin grupo');
  const resChips = `<button class="az-stk-chip ${resFilter.length === 0 ? 'on' : ''}" data-stk-reschip="__all">Todas</button>` +
    resKeys.map(k => `<button class="az-stk-chip ${resFilter.includes(k) ? 'on' : ''} ${resMap.get(k) === 0 ? 'is-done' : ''}" data-stk-reschip="${esc(k)}">${esc(shortLabel(k))} <b>${resMap.get(k)}</b></button>`).join('');

  const groupsHtml = S.stkGroupBy === 'residencia' ? stkByResidenciaHtml(visible) : S.stkGroupBy === 'person' ? stkByPersonHtml(visible) : stkByMedHtml(visible, d.groups);
  body.innerHTML = `
    <div class="az-stk-bar">
      <label class="az-stk-month">Mes <select class="qt-select" id="stk-month">${monthOpts}</select></label>
      <div class="az-stk-counters" id="stk-status">
        <button class="az-stk-count is-pending ${status === 'pending' ? 'on' : ''}" data-stk-status="pending"><span class="n">${t.por_pegar}</span><span class="l">por pegar</span></button>
        <button class="az-stk-count is-ok ${status === 'pegados' ? 'on' : ''}" data-stk-status="pegados"><span class="n">${t.pegados}</span><span class="l">✓ pegados</span></button>
        <button class="az-stk-count ${status === 'all' ? 'on' : ''}" data-stk-status="all"><span class="n">${t.total}</span><span class="l">asignados</span></button>
      </div>
    </div>
    <div class="az-stk-controls">
      <div class="az-seg az-stk-seg" id="stk-groupby"><button data-gb="med" class="${S.stkGroupBy === 'med' ? 'on' : ''}">Por medicamento</button><button data-gb="person" class="${S.stkGroupBy === 'person' ? 'on' : ''}">Por persona</button>${hasResidencias ? `<button data-gb="residencia" class="${S.stkGroupBy === 'residencia' ? 'on' : ''}">Por residencia</button>` : ''}</div>
      <button class="az-stk-chip ${notesOnly ? 'on' : ''}" id="stk-notesonly" title="Mostrar solo los precintos que tienen una nota">📝 Con notas</button>
    </div>
    <div class="az-stk-filterblock"><span class="az-stk-flabel">Medicamento</span><div class="az-stk-filters">${medChips}</div></div>
    ${hasResidencias ? `<div class="az-stk-filterblock"><span class="az-stk-flabel">Residencia</span><div class="az-stk-filters">${resChips}</div></div>` : ''}
    <div class="az-stk-actions">
      <button class="qt-btn qt-btn-primary qt-btn-sm" id="stk-print" title="Elegir qué imprimir y cómo ordenarlo">📄 Imprimir PDF…</button>
      <button class="qt-btn qt-btn-teal qt-btn-sm" id="stk-scan" title="Pasa el escáner por cada precinto para cotejarlo y marcarlo pegado">📟 Escanear para cotejar</button>
    </div>
    <div class="az-stk-bulkbar ${visiblePending.length ? '' : 'is-empty'}">
      <span class="az-stk-bulk-info">${(medFilter.length || resFilter.length) ? '🔎 Filtrado · ' : 'En la vista · '}<b>${visiblePending.length}</b> por pegar</span>
      ${visiblePending.length ? `<button class="qt-btn qt-btn-teal qt-btn-sm" id="stk-bulk-mark">✅ Marcar pegados (${visiblePending.length})</button>
        <label class="qt-btn qt-btn-ghost qt-btn-sm az-stk-photo">📷 Foto y marcar (${visiblePending.length})<input type="file" accept="image/*" capture="environment" id="stk-bulk-photo" hidden></label>` : '<span class="az-stk-complete">✓ Nada pendiente en la vista</span>'}
    </div>
    <div class="az-stk-groups">${groupsHtml}</div>
    ${(d.evidencias && d.evidencias.length) ? stkEvidHtml(d.evidencias) : ''}`;

  $('stk-month').onchange = e => loadStickers(e.target.value);
  $('stk-status').querySelectorAll('[data-stk-status]').forEach(b => b.onclick = () => { S.stkStatus = b.dataset.stkStatus; renderStickers(); });
  if ($('stk-notesonly')) $('stk-notesonly').onclick = () => { S.stkNotesOnly = !S.stkNotesOnly; renderStickers(); };
  $('stk-scan').onclick = () => toggleStkScanner(ym);
  if (stkScan.on) { const b = $('stk-scan'); if (b) b.classList.add('is-on'); }
  $('stk-groupby').querySelectorAll('[data-gb]').forEach(b => b.onclick = () => { S.stkGroupBy = b.dataset.gb; renderStickers(); });
  if ($('stk-print')) $('stk-print').onclick = () => openStkPrintModal();
  body.querySelectorAll('[data-stk-chip]').forEach(c => c.onclick = () => {
    const k = c.dataset.stkChip;
    if (k === '__all') S.stkFilter = [];
    else { const f = new Set(S.stkFilter || []); f.has(k) ? f.delete(k) : f.add(k); S.stkFilter = [...f]; }
    renderStickers();
  });
  body.querySelectorAll('[data-stk-reschip]').forEach(c => c.onclick = () => {
    const k = c.dataset.stkReschip;
    if (k === '__all') S.stkFilterRes = [];
    else { const f = new Set(S.stkFilterRes || []); f.has(k) ? f.delete(k) : f.add(k); S.stkFilterRes = [...f]; }
    renderStickers();
  });
  if ($('stk-bulk-mark')) $('stk-bulk-mark').onclick = async () => {
    if (!(await confirmBox('Marcar pegados', `¿Marcar como pegados los ${pendingItems.length} precintos por pegar de la vista actual?`, 'Marcar'))) return;
    stkMarkItems(pendingItems, 'manual');
  };
  if ($('stk-bulk-photo')) $('stk-bulk-photo').onchange = (e) => stkPhotoMarkItems(e.target, pendingItems);
  wireStkGroups();
}
// Group the visible items by medication (ordered like the server groups).
function stkByMedHtml(visible, groups) {
  const byKey = new Map();
  for (const i of visible) { if (!byKey.has(i.medKey)) byKey.set(i.medKey, []); byKey.get(i.medKey).push(i); }
  if (!byKey.size) return '<div class="az-empty-sm">Nada que mostrar con este filtro.</div>';
  return groups.filter(g => byKey.has(g.key)).map(g => {
    const items = byKey.get(g.key);
    const pending = items.filter(i => !i.pegado);
    const bc = g.barcode ? eanSvg(g.barcode) : '';
    const title = `<b>${esc(g.nombre || 'Medicamento')}</b><small>${g.cn ? 'CN ' + esc(g.cn) : ''}${g.barcode ? ' · ' + esc(g.barcode) : ''}</small>`;
    return stkGroupCard(title, `${g.items.filter(i => i.pegado).length}/${g.items.length}`, pending, items.map(i => stkItemRow(i, 'med')).join(''), bc);
  }).join('');
}
// Group the visible items by person (each may span several medications).
function stkByPersonHtml(visible) {
  const byP = new Map();
  for (const i of visible) { const k = i.person.id; if (!byP.has(k)) byP.set(k, { person: i.person, items: [] }); byP.get(k).items.push(i); }
  const groups = [...byP.values()].sort((a, b) => (a.person.apellidos || '').localeCompare(b.person.apellidos || '') || (a.person.nombre || '').localeCompare(b.person.nombre || ''));
  if (!groups.length) return '<div class="az-empty-sm">Nada que mostrar con este filtro.</div>';
  return groups.map(g => {
    const pending = g.items.filter(i => !i.pegado);
    const title = `<b>${esc(g.person.apellidos)}, ${esc(g.person.nombre)}</b><small>${g.items.length} precinto(s)</small>`;
    return stkGroupCard(title, `${g.items.filter(i => i.pegado).length}/${g.items.length}`, pending, g.items.map(i => stkItemRow(i, 'person')).join(''), '');
  }).join('');
}
// Group the visible items by residence (the person's QR·TIS group), then by person.
function stkByResidenciaHtml(visible) {
  const byR = new Map();
  for (const i of visible) { const k = i.resKey; if (!byR.has(k)) byR.set(k, []); byR.get(k).push(i); }
  const keys = [...byR.keys()].sort((a, b) => a === 'Sin grupo' ? 1 : b === 'Sin grupo' ? -1 : a.localeCompare(b));
  if (!keys.length) return '<div class="az-empty-sm">Nada que mostrar con este filtro.</div>';
  return keys.map(k => {
    const items = byR.get(k).slice().sort((a, b) => (a.person.apellidos || '').localeCompare(b.person.apellidos || '') || (a.medNombre || '').localeCompare(b.medNombre || ''));
    const pending = items.filter(i => !i.pegado);
    const title = `<b>🏠 ${esc(k)}</b><small>${items.length} precinto(s)</small>`;
    return stkGroupCard(title, `${items.filter(i => i.pegado).length}/${items.length}`, pending, items.map(i => stkItemRow(i, 'residencia')).join(''), '');
  }).join('');
}
function stkGroupCard(titleHtml, progText, pending, itemsHtml, bcHtml) {
  return `<div class="az-stk-group ${pending.length ? '' : 'is-complete'}">
    <div class="az-stk-g-head"><div class="az-stk-g-title">${titleHtml}</div><span class="az-stk-badge ${pending.length ? 'is-pending' : 'is-done'}">${progText} pegados</span></div>
    ${bcHtml ? `<div class="az-stk-g-bc">${bcHtml}</div>` : ''}
    <div class="az-stk-g-actions">
      ${pending.length ? `<button class="qt-btn qt-btn-teal qt-btn-sm" data-stk-markset='${itemsAttr(pending)}'>✅ Marcar pegados (${pending.length})</button>
        <label class="qt-btn qt-btn-ghost qt-btn-sm az-stk-photo">📷 Foto y marcar<input type="file" accept="image/*" capture="environment" data-stk-photoset='${itemsAttr(pending)}' hidden></label>` : '<span class="az-stk-complete">✓ Todos pegados</span>'}
    </div>
    <div class="az-stk-items">${itemsHtml || '<div class="az-empty-sm">Nada aquí.</div>'}</div>
  </div>`;
}
function stkItemRow(i, mode) {
  const j = JSON.stringify({ source: i.source, id: i.id });
  const label = mode === 'person' ? `${esc(i.medNombre || 'Medicamento')}${i.medCn ? ' · CN ' + esc(i.medCn) : ''}`
    : mode === 'residencia' ? `${esc(i.person.apellidos)}, ${esc(i.person.nombre)} <small class="az-stk-i-med">· ${esc(shortLabel(i.medNombre || i.medCn || ''))}</small>`
      : `${esc(i.person.apellidos)}, ${esc(i.person.nombre)}`;
  const tag = `${i.source === 'line' ? '📦 DM' : '🏷️'}${i.serial ? ' · ' + esc(i.serial) : ''}`;
  const noteBtn = `<button class="qt-iconbtn az-note-ic ${i.note ? 'has' : ''}" data-stk-note='${j}' title="${i.note ? 'Editar nota' : 'Añadir nota'}">📝</button>`;
  const right = i.pegado
    ? `<span class="az-stk-i-state">✓ pegado${i.method ? ' · ' + esc(i.method) : ''}</span>${i.evidencia_id ? ` <a class="az-stk-evlink" href="${API}/stickers/evidencia/${i.evidencia_id}" target="_blank" rel="noopener" title="Ver la foto de prueba">📷</a>` : ''} <button class="qt-iconbtn" data-stk-unmark='${j}' title="Revertir a por pegar">↩</button>`
    : `<button class="qt-btn qt-btn-teal qt-btn-sm" data-stk-mark='${j}'>✅ Pegado</button>`;
  const noteLine = i.note ? `<div class="az-ent-note" style="background:${esc(i.note.color || '#FEF08A')}">${esc(i.note.text)}</div>` : '';
  return `<div class="az-stk-item ${i.pegado ? 'is-peg' : ''}${i.note ? ' has-note' : ''}"><div class="az-stk-item-main"><span class="az-stk-i-who">${label}</span><span class="az-stk-i-tag">${tag}</span><span class="az-stk-i-right">${noteBtn}${right}</span></div>${noteLine}</div>`;
}
function findStkItem(source, id) { for (const g of ((S.stickers && S.stickers.groups) || [])) for (const it of g.items) if (it.source === source && it.id === Number(id)) return it; return null; }
function stkEvidHtml(evs) {
  return `<div class="az-stk-evsec"><div class="az-stk-ev-h">📷 Fotos de prueba de este mes (${evs.length})</div>
    <div class="az-stk-evgrid">${evs.map(e => `<a class="az-stk-ev" href="${API}/stickers/evidencia/${e.id}" target="_blank" rel="noopener" title="Prueba · ${esc(fmtDate(e.created_at))}"><img src="${API}/stickers/evidencia/${e.id}" alt="Foto de prueba" loading="lazy"></a>`).join('')}</div></div>`;
}
// A small, pretty note editor for a person or a precinto (upsert; empty = borrar).
const AZ_NOTE_COLORS = ['#FEF08A', '#FBCFE8', '#BFDBFE', '#BBF7D0', '#FED7AA', '#E9D5FF', '#FECACA'];
function noteColorList() { return (Array.isArray(S.noteColors) && S.noteColors.length) ? S.noteColors : AZ_NOTE_COLORS; }
function openNoteEditor(opts) {
  const cur = opts.current || {}, cols = noteColorList();
  let color = cur.color || cols[0];
  openTool(`<div class="qt-modal-h"><h3>📝 Nota${opts.subtitle ? ' · ' + esc(opts.subtitle) : ''}</h3><button class="qt-x" id="nte-x">×</button></div>
    <p class="qt-tool-note">Una nota corta para recordar «qué le pasa». Se guarda sola y luego puedes filtrar por «Con notas».</p>
    <div class="az-noteedit" id="nte-card" style="background:${esc(color)}"><textarea id="nte-text" class="az-noteedit-ta" maxlength="2000" placeholder="Escribe la nota…">${esc(cur.text || '')}</textarea></div>
    <div class="az-noteedit-cols">${cols.map(c => `<button class="az-noteedit-sw ${c === color ? 'sel' : ''}" data-c="${esc(c)}" style="background:${esc(c)}" aria-label="color"></button>`).join('')}</div>
    <div class="qt-modal-actions">
      ${cur.text ? '<button class="qt-btn qt-btn-danger" id="nte-del">Borrar nota</button>' : ''}
      <button class="qt-btn qt-btn-ghost" id="nte-cancel">Cancelar</button>
      <button class="qt-btn qt-btn-primary" id="nte-save">Guardar</button>
    </div>`);
  $('nte-x').onclick = closeTool; $('nte-cancel').onclick = closeTool;
  $('tool-modal-box').querySelectorAll('.az-noteedit-sw').forEach(sw => sw.onclick = () => { color = sw.dataset.c; $('nte-card').style.background = color; $('tool-modal-box').querySelectorAll('.az-noteedit-sw').forEach(x => x.classList.toggle('sel', x === sw)); });
  const save = async (text) => {
    try { const r = await api(opts.endpoint, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, color }) }); closeTool(); opts.onSaved(r.note || null); toast(text.trim() ? 'Nota guardada.' : 'Nota borrada.'); }
    catch (e) { toast(e.message, 'err'); }
  };
  $('nte-save').onclick = () => save($('nte-text').value);
  if ($('nte-del')) $('nte-del').onclick = () => save('');
  setTimeout(() => { const ta = $('nte-text'); if (ta) ta.focus(); }, 30);
}
// Ask what to print and how to order it, then open the PDF with those options.
function openStkPrintModal() {
  const d = S.stickers; if (!d) return;
  const ym = d.ym, medF = S.stkFilter || [], resF = S.stkFilterRes || [];
  const nFilter = medF.length + resF.length;
  const hasRes = new Set((d.groups || []).flatMap(g => g.items.map(i => i.residencia || 'Sin grupo'))).size > 1;
  const st = { content: 'pending', order: (['med', 'person', 'residencia'].includes(S.stkGroupBy) ? S.stkGroupBy : 'med'), sub: 'med' };
  const seg = (name, opts) => `<div class="az-seg az-pr-seg" data-prseg="${name}">${opts.map(([v, l]) => `<button type="button" data-v="${v}" class="${v === st[name] ? 'on' : ''}">${l}</button>`).join('')}</div>`;
  openTool(`<div class="qt-modal-h"><h3>📄 Imprimir precintos</h3><button class="qt-x" id="pr-close">×</button></div>
    <p class="qt-tool-note">Elige qué precintos imprimir y cómo ordenarlos. Salen en rejilla <b>4×7</b> por A4 para pegarlos en la hoja oficial y cotejar.</p>
    <div class="az-form">
      <label class="az-flabel">Qué precintos</label>${seg('content', [['pending', 'Solo por pegar'], ['all', 'Todos']])}
      ${nFilter ? `<label class="az-pr-check"><input type="checkbox" id="pr-restrict" checked> Solo los que tengo filtrados ahora (${nFilter} filtro${nFilter > 1 ? 's' : ''})</label>` : ''}
      <label class="az-flabel">Ordenar por</label>${seg('order', [['med', 'Medicamento'], ['person', 'Persona']].concat(hasRes ? [['residencia', 'Residencia']] : []))}
      <div id="pr-sub" ${st.order === 'residencia' ? '' : 'hidden'}><label class="az-flabel">Dentro de cada residencia</label>${seg('sub', [['med', 'Medicamento'], ['person', 'Persona']])}</div>
      <label class="az-pr-check"><input type="checkbox" id="pr-pagebreak"> Empezar cada grupo en una página nueva</label>
      <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" id="pr-cancel">Cancelar</button><button class="qt-btn qt-btn-primary" id="pr-go">📄 Abrir PDF</button></div>
    </div>`);
  $('pr-close').onclick = closeTool; $('pr-cancel').onclick = closeTool;
  $('tool-modal-box').querySelectorAll('.az-pr-seg').forEach(sg => sg.querySelectorAll('button').forEach(btn => btn.onclick = () => {
    const name = sg.dataset.prseg; st[name] = btn.dataset.v; sg.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === btn));
    if (name === 'order') $('pr-sub').hidden = st.order !== 'residencia';
  }));
  $('pr-go').onclick = () => {
    const restrict = $('pr-restrict') && $('pr-restrict').checked;
    const params = new URLSearchParams({ ym, filter: st.content, order: st.order });
    if (st.order === 'residencia') params.set('sub', st.sub);
    if ($('pr-pagebreak').checked) params.set('pagebreak', '1');
    if (restrict && medF.length) params.set('meds', JSON.stringify(medF));
    if (restrict && resF.length) params.set('groups', JSON.stringify(resF));
    window.open(`${API}/stickers/pdf?${params.toString()}`, '_blank');
    closeTool();
  };
}
function wireStkGroups() {
  const body = $('stk-body'); if (!body) return;
  body.querySelectorAll('[data-stk-mark]').forEach(b => b.onclick = () => stkMarkItems([JSON.parse(b.dataset.stkMark)], 'manual'));
  body.querySelectorAll('[data-stk-unmark]').forEach(b => b.onclick = () => stkUnmarkItems([JSON.parse(b.dataset.stkUnmark)]));
  body.querySelectorAll('[data-stk-markset]').forEach(b => b.onclick = async () => {
    const items = JSON.parse(b.dataset.stkMarkset);
    if (items.length > 1 && !(await confirmBox('Marcar pegados', `¿Marcar como pegados ${items.length} precintos? Dejarán de aparecer como por pegar.`, 'Marcar'))) return;
    stkMarkItems(items, 'manual');
  });
  body.querySelectorAll('[data-stk-photoset]').forEach(inp => inp.onchange = () => stkPhotoMarkItems(inp, JSON.parse(inp.dataset.stkPhotoset)));
  body.querySelectorAll('[data-stk-note]').forEach(b => b.onclick = () => {
    const it = JSON.parse(b.dataset.stkNote), item = findStkItem(it.source, it.id);
    openNoteEditor({ subtitle: item ? `${item.person.apellidos}, ${item.person.nombre} · ${item.nombre || ''}` : '', endpoint: `/note/sticker/${it.source}/${it.id}`, current: item && item.note, onSaved: (note) => { if (item) item.note = note; renderStickers(); } });
  });
}
async function stkMarkItems(items, method) {
  if (!items || !items.length) return;
  try { S.stickers = await api('/stickers/mark', jbody({ ym: S.stickers.ym, items, method: method || 'manual' })); renderStickers(); toast(`${items.length} precinto(s) marcados como pegados.`); }
  catch (e) { toast(e.message, 'err'); }
}
async function stkUnmarkItems(items) {
  try { S.stickers = await api('/stickers/unmark', jbody({ ym: S.stickers.ym, items })); renderStickers(); }
  catch (e) { toast(e.message, 'err'); }
}
async function stkPhotoMarkItems(inp, items) {
  const file = inp.files && inp.files[0]; if (!file) return;
  if (!items || !items.length) { toast('No hay precintos pendientes que marcar.', 'err'); inp.value = ''; return; }
  if (file.size > 10 * 1024 * 1024) { toast('La foto es muy grande (máx. 10 MB).', 'err'); inp.value = ''; return; }
  toast('Subiendo foto de prueba…');
  try {
    const dataUrl = await new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });
    const ev = await api('/stickers/evidencia', jbody({ ym: S.stickers.ym, photo: dataUrl }));
    S.stickers = await api('/stickers/mark', jbody({ ym: S.stickers.ym, items, method: 'foto', evidencia_id: ev.evidencia_id }));
    renderStickers(); toast(`${items.length} precinto(s) pegados, con foto de prueba guardada.`);
  } catch (e) { toast(e.message, 'err'); }
}

// Scanner de cotejo para el control de precintos (independiente del de la ficha).
const stkScan = { on: false, ym: null, buf: '', timer: null, handler: null, log: [], busy: false };
function toggleStkScanner(ym) { if (stkScan.on) stopStkScanner(); else startStkScanner(ym); }
function startStkScanner(ym) {
  stopStkScanner(true);
  stkScan.on = true; stkScan.ym = ym; stkScan.buf = ''; stkScan.log = [];
  stkScan.handler = onStkKey; document.addEventListener('keydown', stkScan.handler, true);
  renderStkPanel(); const b = $('stk-scan'); if (b) b.classList.add('is-on');
}
function stopStkScanner(silent) {
  if (stkScan.handler) { document.removeEventListener('keydown', stkScan.handler, true); stkScan.handler = null; }
  if (stkScan.timer) { clearTimeout(stkScan.timer); stkScan.timer = null; }
  stkScan.on = false; stkScan.buf = '';
  const p = $('stk-panel'); if (p) p.remove();
  const b = $('stk-scan'); if (b) b.classList.remove('is-on');
  if (!silent) toast('Escáner de cotejo desactivado.');
}
function onStkKey(e) {
  if (!stkScan.on) return;
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  if (isEditableTarget(e.target)) return;
  if (e.key === 'Enter') { if (stkScan.buf) { e.preventDefault(); const c = stkScan.buf; stkScan.buf = ''; processStkScan(c); } return; }
  if (e.key && e.key.length === 1) { stkScan.buf += e.key; if (stkScan.timer) clearTimeout(stkScan.timer); stkScan.timer = setTimeout(() => { stkScan.buf = ''; }, 400); }
}
async function processStkScan(code) {
  if (stkScan.busy) return; stkScan.busy = true;
  try {
    const r = await api('/stickers/scan', jbody({ ym: stkScan.ym, code }));
    const who = r.matched && r.matched.person ? ` · ${r.matched.person.apellidos}, ${r.matched.person.nombre}` : '';
    stkScanLog('ok', `${r.matched && r.matched.nombre ? r.matched.nombre : 'Medicamento'}${who} · pegado · quedan ${r.remaining}`);
    S.stickers = r; renderStickers();
  } catch (e) {
    stkScanLog('err', e.data && e.data.nomatch ? `«${code}» sin precintos por pegar de ese medicamento` : (e.message || 'Error') + ` («${code}»)`);
  } finally { stkScan.busy = false; }
}
function stkScanLog(kind, msg) {
  stkScan.log.unshift({ kind, msg, at: new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) });
  if (stkScan.log.length > 40) stkScan.log.length = 40;
  renderStkLog();
}
function renderStkPanel() {
  if ($('stk-panel')) { renderStkLog(); return; }
  const el = document.createElement('div');
  el.className = 'az-scanpanel az-stkpanel'; el.id = 'stk-panel';
  el.innerHTML = `<div class="az-scanpanel-h"><span class="az-scan-live">📟 Cotejo de precintos <span class="az-scan-dot"></span></span><button class="qt-x" id="stk-panel-x" title="Salir del cotejo">×</button></div>
    <p class="az-scanpanel-note">Pasa el escáner por cada <b>precinto</b> (o su Data Matrix). Cada lectura marca uno como <b>pegado</b> y descuenta del pendiente. Sigue escuchando.</p>
    <div class="az-scanlog" id="stk-log"></div>`;
  document.body.appendChild(el);
  $('stk-panel-x').onclick = () => stopStkScanner();
  renderStkLog();
}
function renderStkLog() {
  const box = $('stk-log'); if (!box) return;
  box.innerHTML = stkScan.log.length
    ? stkScan.log.map(e => `<div class="az-scanline ${e.kind === 'ok' ? 'is-ok' : 'is-err'}"><span class="az-scan-ic">${e.kind === 'ok' ? '✓' : '✗'}</span><span class="az-scan-msg">${esc(e.msg)}</span><span class="az-scan-at">${esc(e.at)}</span></div>`).join('')
    : '<div class="az-scan-empty">Esperando lecturas…</div>';
}
// Same day next month (clamped to the last day of that month).
function sameDayNextMonth(iso) {
  const base = /^\d{4}-\d{2}-\d{2}$/.test(iso || '') ? new Date(iso + 'T00:00:00') : new Date();
  const day = base.getDate();
  const d = new Date(base.getFullYear(), base.getMonth() + 1, 1);
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  d.setDate(Math.min(day, last));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
// Assigning in Salud is where we capture the medication's NEXT release date.
function openAssignModal(ln) {
  const box = ln.box || {};
  const med = (S.ficha.plan || []).find(m => (m.gtin && box.gtin && m.gtin === box.gtin) || (m.cn && box.cn && m.cn === box.cn));
  const prefill = sameDayNextMonth(med && med.release_at);
  openTool(`<div class="qt-modal-h"><h3>✅ Asignar en Salud</h3><button class="qt-x" id="as-close">×</button></div>
    <p class="qt-tool-note">Vas a marcar esta caja como <b>asignada</b> (se envía a Salud y sale del inventario). Indica <b>cuándo saldrá la próxima</b> de este medicamento; esa fecha gobernará cuándo vuelve a estar disponible.</p>
    <div class="qt-field"><label>Medicamento</label><div class="az-rp-med">${shapeSvg(box.shape, box.color, 18)} ${esc(box.nombre || (med && med.nombre) || 'Sin nombre')}${box.serial ? ' · Nº ' + esc(box.serial) : ''}</div></div>
    <div class="qt-field"><label>Próxima fecha de liberación (Salud)</label><input type="date" class="qt-input" id="as-date" value="${esc(prefill)}"><small class="az-field-hint">Propuesta: mismo día del mes siguiente. Déjala vacía si aún no la sabes.</small></div>
    <div class="qt-modal-actions">
      <button class="qt-btn qt-btn-ghost" id="as-cancel">Cancelar</button>
      <button class="qt-btn qt-btn-teal" id="as-do">✅ Asignar</button>
    </div>`);
  $('as-close').onclick = closeTool; $('as-cancel').onclick = closeTool;
  $('as-do').onclick = async () => {
    const v = $('as-date').value;
    if (v && !/^\d{4}-\d{2}-\d{2}$/.test(v)) { toast('Fecha no válida.', 'err'); return; }
    try { applyFicha(await api('/line/' + ln.id + '/assign', jbody({ next_release_at: v || '' }))); closeTool(); toast(v ? 'Caja asignada. Próxima liberación guardada.' : 'Caja asignada.'); }
    catch (e) { toast(e.message, 'err'); }
  };
}

// Compute an effective ISO date (official − N days) on the client, for live preview.
function effectiveIso(iso, adv) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso || '')) return null;
  const d = new Date(iso + 'T00:00:00'); if (isNaN(d)) return null;
  d.setDate(d.getDate() - Math.min(365, Math.max(0, Math.round(Number(adv) || 0))));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
// Set the official Salud date AND the days of anticipation for a MEDICATION (plan).
// The effective date (official − anticipation) drives its state and the bell.
function openPlanReleasePicker(med) {
  const cur = med.release_at || '';
  const adv = med.advance_days != null ? med.advance_days : 15;
  openTool(`<div class="qt-modal-h"><h3>🗓 Fecha de liberación</h3><button class="qt-x" id="rp-close">×</button></div>
    <p class="qt-tool-note">La <b>fecha oficial</b> es la que marca Salud para este medicamento. La <b>fecha efectiva</b> (cuando ya se puede coger/asignar y cuando avisa la app) es la oficial menos los <b>días de anticipación</b>. Es del <b>medicamento</b> (recurrente): vale mes a mes hasta que la cambies.</p>
    <div class="qt-field"><label>Medicamento</label><div class="az-rp-med">${shapeSvg(med.shape, med.color, 18)} ${esc(med.nombre || 'Sin nombre')}</div></div>
    <div class="qt-field"><label>Fecha oficial de liberación (Salud)</label><input type="date" class="qt-input" id="rp-date" value="${esc(cur)}"></div>
    <div class="qt-field"><label>Días de anticipación</label><input type="number" class="qt-input" id="rp-adv" min="0" max="365" step="1" value="${esc(String(adv))}"><small class="az-field-hint">Por defecto 15. Se aplica a este medicamento de esta persona.</small></div>
    <div class="az-rp-eff" id="rp-eff"></div>
    <div class="qt-modal-actions">
      ${cur ? '<button class="qt-btn qt-btn-ghost" id="rp-clear">Quitar fecha</button>' : ''}
      <button class="qt-btn qt-btn-ghost" id="rp-cancel">Cancelar</button>
      <button class="qt-btn qt-btn-primary" id="rp-save">Guardar</button>
    </div>`);
  $('rp-close').onclick = closeTool; $('rp-cancel').onclick = closeTool;
  const preview = () => {
    const d = $('rp-date').value, a = $('rp-adv').value;
    const eff = effectiveIso(d, a);
    $('rp-eff').innerHTML = d
      ? (eff ? `Fecha efectiva: <b>${fmtDate(eff)}</b> <span class="az-rp-eff-sub">(oficial ${fmtDate(d)} − ${Math.max(0, Math.round(Number(a) || 0))} días)</span>` : '')
      : '<span class="az-rp-eff-sub">Sin fecha oficial, el medicamento queda «pendiente de fecha».</span>';
  };
  $('rp-date').addEventListener('input', preview); $('rp-adv').addEventListener('input', preview); preview();
  const send = async (payload, okMsg) => {
    try { const r = await api('/plan/' + med.id + '/release', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); S.ficha.plan = mergePlan(S.ficha.plan, r.plan); renderFicha(); closeTool(); toast(okMsg); }
    catch (e) { toast(e.message, 'err'); }
  };
  $('rp-save').onclick = () => {
    const v = $('rp-date').value;
    const a = Math.round(Number($('rp-adv').value));
    if (!v) { toast('Elige una fecha o pulsa «Quitar fecha».', 'err'); return; }
    if (!Number.isFinite(a) || a < 0 || a > 365) { toast('Días de anticipación no válidos (0–365).', 'err'); return; }
    send({ date: v, advance_days: a }, 'Fecha y anticipación guardadas.');
  };
  if ($('rp-clear')) $('rp-clear').onclick = () => send({ date: '' }, 'Fecha eliminada.');
}

// CIMA box + pill photos, served from our local cache endpoint (work offline).
// The click-through opens the full-size image at AEMPS.
function cimaFotosHtml(cn, fotos) {
  if (!fotos || !cn) return '';
  const one = (f, tipo, lbl) => f ? `<a class="az-cima-foto" href="${esc(f.full || fotoUrl(cn, tipo))}" target="_blank" rel="noopener" title="Ver ${lbl} (AEMPS)"><img src="${fotoUrl(cn, tipo)}" alt="${lbl}" loading="lazy" onerror="this.style.display='none'"><span>${lbl}</span></a>` : '';
  const inner = one(fotos.caja, 'caja', 'Caja') + one(fotos.pastilla, 'pastilla', 'Pastilla');
  return inner ? `<div class="az-cima-fotos">${inner}</div><div class="az-form-hint" style="margin-top:2px">Imágenes: AEMPS · CIMA · guardadas</div>` : '';
}
// Edit an existing plan medication (name / CN / barcode) without deleting it.
function openEditMed(med) {
  openTool(`<div class="qt-modal-h"><h3>✏️ Editar medicamento</h3><button class="qt-x" id="em-close">×</button></div>
    <p class="qt-tool-note">Corrige el <b>nombre</b>, el <b>Código Nacional</b> o el <b>código de barras</b> sin tener que borrar y volver a añadir.</p>
    <div class="qt-field"><label>Nombre del medicamento</label><input class="qt-input" id="em-nombre" value="${esc(med.nombre || '')}" maxlength="160" autocomplete="off"></div>
    <div class="qt-field"><label>Código Nacional (CN)</label><div class="az-cn-row"><input class="qt-input" id="em-cn" inputmode="numeric" value="${esc(med.cn || '')}" autocomplete="off"><button class="qt-btn qt-btn-ghost qt-btn-sm" id="em-cima" title="Traer datos desde CIMA (AEMPS)">🔎 CIMA</button></div></div>
    <div class="qt-field"><label>Código de barras (opcional)</label><input class="qt-input" id="em-barcode" inputmode="numeric" value="${esc(med.barcode || '')}" autocomplete="off"></div>
    <div id="em-fotos"></div>
    <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" id="em-cancel">Cancelar</button><button class="qt-btn qt-btn-primary" id="em-save">Guardar</button></div>`);
  $('em-close').onclick = closeTool; $('em-cancel').onclick = closeTool;
  $('em-barcode').addEventListener('input', () => { const bar = $('em-barcode').value.replace(/\D/g, ''); if (!$('em-cn').value.trim() && /^847000\d{7}$/.test(bar)) $('em-cn').value = bar.slice(6, 12); });
  $('em-cima').onclick = async () => {
    const cn = $('em-cn').value.trim();
    if (!/^\d{5,7}$/.test(cn)) { toast('Escribe un Código Nacional (5–7 dígitos).', 'err'); return; }
    const btn = $('em-cima'); btn.disabled = true; const prev = btn.textContent; btn.textContent = '…';
    try { const { item } = await api('/cima/cn/' + cn); if (!item) toast('CIMA no encontró ese Código Nacional.', 'err'); else { if (item.nombre) $('em-nombre').value = item.nombre; if (item.barcode) $('em-barcode').value = item.barcode; $('em-fotos').innerHTML = cimaFotosHtml(item.cn, item.fotos); toast('Datos traídos de CIMA (AEMPS).', 'ok'); } }
    catch (e) { toast((e.offline || (e.data && e.data.offline)) ? 'No se pudo consultar CIMA ahora; edítalo a mano.' : e.message, 'err'); }
    finally { btn.disabled = false; btn.textContent = prev; }
  };
  $('em-save').onclick = async () => {
    const nombre = $('em-nombre').value.trim(), cn = $('em-cn').value.trim(), barcode = $('em-barcode').value.trim();
    if (!cn) { toast('Indica el Código Nacional.', 'err'); return; }
    if (!nombre) { toast('Indica el nombre del medicamento.', 'err'); return; }
    try { const r = await api('/plan/' + med.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre, cn, barcode: barcode || '' }) }); S.ficha.plan = mergePlan(S.ficha.plan, r.plan); renderFicha(); closeTool(); toast('Medicamento actualizado.'); }
    catch (e) { toast(e.message, 'err'); }
  };
}

// ── Medication picker (add a medication to the plan) ─────────────────────────────
function openMedPicker() {
  openTool(`<div class="qt-modal-h"><h3>Añadir medicamento al plan</h3><button class="qt-x" id="mp-close">×</button></div>
    <p class="qt-tool-note">Del <b>catálogo</b> (ya en Data Matrix) o, si aún no lo está, <b>por Código Nacional</b> (información previa, sin caja todavía).</p>
    <div class="qt-search" style="margin-bottom:10px"><span class="ico">🔎</span><input id="mp-q" placeholder="Buscar en el catálogo por nombre, GTIN o CN…" autocomplete="off"></div>
    <div id="mp-list" class="az-medlist"></div>
    <div class="qt-tool-row" style="margin:-2px 0 8px"><button class="qt-btn qt-btn-ghost qt-btn-sm" id="mp-cima-search">🔎 Buscar en CIMA (AEMPS)</button><span class="az-form-hint" style="margin:0">busca el medicamento en la base oficial y trae CN, nombre y código de barras</span></div>
    <div class="az-cnform">
      <div class="az-cnform-h">➕ Añadir por Código Nacional (aún sin Data Matrix)</div>
      <div class="qt-field"><label>Código Nacional (CN)</label>
        <div class="az-cn-row"><input class="qt-input" id="mp-cn" inputmode="numeric" placeholder="p. ej. 712345" autocomplete="off"><button class="qt-btn qt-btn-ghost qt-btn-sm" id="mp-cima" title="Traer nombre y código de barras desde CIMA (AEMPS)">🔎 CIMA</button></div></div>
      <div class="qt-field"><label>Nombre del medicamento</label><input class="qt-input" id="mp-nombre" placeholder="Nombre comercial" autocomplete="off"></div>
      <div class="qt-field"><label>Código de barras (opcional)</label><input class="qt-input" id="mp-barcode" inputmode="numeric" placeholder="EAN / código de barras" autocomplete="off"></div>
      <div class="qt-field"><label>Cajas al mes</label><input class="qt-input" id="mp-qty" type="number" min="1" max="99" value="1"></div>
      <div id="mp-fotos"></div>
      <div class="qt-tool-row"><button class="qt-btn qt-btn-primary" id="mp-add-cn">➕ Añadir al plan</button></div>
      <div class="az-form-hint">Podrás asociarle una caja real más adelante (eligiéndola del inventario o escaneándola), y quedará pre-asignada.</div>
    </div>`);
  $('mp-close').onclick = closeTool;
  const q = $('mp-q');
  const load = async () => {
    try {
      const { items } = await api('/medications?q=' + encodeURIComponent(q.value || ''));
      const list = $('mp-list');
      if (!items.length) { list.innerHTML = `<div class="az-noresult">No hay medicamentos en el catálogo que coincidan. Prueba <b>«🔎 Buscar en CIMA»</b> o <b>«Añadir por Código Nacional»</b> abajo.</div>`; return; }
      list.innerHTML = items.slice(0, 40).map(m => `<button class="az-medrow" data-gtin="${esc(m.gtin)}"><span class="az-plan-shape">${shapeSvg(m.shape, m.color, 18)}</span><span class="az-medrow-name">${esc(m.nombre || 'Sin nombre')}<small>GTIN ${esc(m.gtin)}${m.cn ? ' · CN ' + esc(m.cn) : ''} · ${m.available} en stock</small></span><span class="az-medrow-add">➕</span></button>`).join('');
      list.querySelectorAll('[data-gtin]').forEach(b => b.addEventListener('click', () => addMedToPlan({ gtin: b.dataset.gtin })));
    } catch (e) { $('mp-list').innerHTML = `<div class="az-noresult">${esc(e.message)}</div>`; }
  };
  let t = null; q.addEventListener('input', () => { if (t) clearTimeout(t); t = setTimeout(load, 200); });
  // Fill the CN form from a CIMA record (name + derived barcode + photos).
  const fillFromCima = (it) => {
    if (it.cn) $('mp-cn').value = it.cn;
    if (it.nombre) $('mp-nombre').value = it.nombre;
    if (it.barcode) $('mp-barcode').value = it.barcode;
    if ($('mp-fotos')) $('mp-fotos').innerHTML = cimaFotosHtml(it.cn, it.fotos);
    $('mp-cn').scrollIntoView({ block: 'nearest' });
  };
  // Live assist: derive the CN from a typed Spanish barcode when the CN is empty.
  $('mp-barcode').addEventListener('input', () => {
    const bar = $('mp-barcode').value.replace(/\D/g, '');
    if (!$('mp-cn').value.trim() && /^847000\d{7}$/.test(bar)) $('mp-cn').value = bar.slice(6, 12);
  });
  const cimaErr = (e) => (e.offline || (e.data && e.data.offline)) ? 'No se pudo consultar CIMA ahora; escribe los datos a mano.' : (e.message || 'Error al consultar CIMA.');
  // Look up by the typed Código Nacional.
  $('mp-cima').onclick = async () => {
    const cn = $('mp-cn').value.trim();
    if (!/^\d{5,7}$/.test(cn)) { toast('Escribe un Código Nacional (5–7 dígitos).', 'err'); return; }
    const btn = $('mp-cima'); btn.disabled = true; const prev = btn.textContent; btn.textContent = '…';
    try { const { item } = await api('/cima/cn/' + cn); if (!item) toast('CIMA no encontró ese Código Nacional.', 'err'); else { fillFromCima(item); toast('Datos traídos de CIMA (AEMPS).', 'ok'); } }
    catch (e) { toast(cimaErr(e), 'err'); }
    finally { btn.disabled = false; btn.textContent = prev; }
  };
  // Search CIMA by name and let the user pick a presentation.
  $('mp-cima-search').onclick = async () => {
    if (t) clearTimeout(t);   // don't let the debounced catalog reload clobber the CIMA results
    const text = (q.value || $('mp-nombre').value || '').trim();
    if (text.length < 3) { toast('Escribe al menos 3 letras en el buscador de arriba.', 'err'); return; }
    const list = $('mp-list'); list.innerHTML = '<div class="az-noresult">Buscando en CIMA…</div>';
    try {
      const { items } = await api('/cima/search?q=' + encodeURIComponent(text));
      if (!items.length) { list.innerHTML = '<div class="az-noresult">CIMA no devolvió resultados para esa búsqueda.</div>'; return; }
      list.innerHTML = `<div class="az-form-hint" style="margin:2px 0 6px">Resultados de CIMA (AEMPS) — pulsa uno para rellenar el formulario de abajo:</div>` +
        items.map((m, i) => `<button class="az-medrow" data-cima="${i}"><span class="az-plan-shape">💊</span><span class="az-medrow-name">${esc(m.nombre || 'Sin nombre')}<small>${m.cn ? 'CN ' + esc(m.cn) : 'sin CN'}${m.barcode ? ' · CB ' + esc(m.barcode) : ''}${m.labtitular ? ' · ' + esc(m.labtitular) : ''}</small></span><span class="az-medrow-add">⬇</span></button>`).join('');
      list.querySelectorAll('[data-cima]').forEach(b => b.addEventListener('click', () => { fillFromCima(items[Number(b.dataset.cima)]); toast('Datos copiados de CIMA. Revisa y pulsa «Añadir al plan».', 'ok'); }));
    } catch (e) { list.innerHTML = `<div class="az-noresult">${esc(cimaErr(e))}</div>`; }
  };
  $('mp-add-cn').onclick = () => {
    const cn = $('mp-cn').value.trim(), nombre = $('mp-nombre').value.trim(), barcode = $('mp-barcode').value.trim();
    const qty = Number($('mp-qty').value) || 1;
    if (!cn) { toast('Indica el Código Nacional.', 'err'); return; }
    if (!nombre) { toast('Indica el nombre del medicamento.', 'err'); return; }
    addMedToPlan({ cn, nombre, barcode: barcode || undefined, qty });
  };
  load();
}
async function addMedToPlan(payload) {
  try {
    await api(`/person/${S.person.id}/plan`, jbody({ qty: 1, ...payload }));
    closeTool(); await reloadFicha(); toast('Medicamento añadido al plan.');
  } catch (e) { toast(e.message, 'err'); }
}

// ── Add a box to the ficha (pre-assign): from inventory or by scanning ───────────
// `med` (optional) is a plan medication to link the box to: it scopes the inventory
// (by GTIN, or by Código Nacional for CN-only meds) and passes plan_id so the box
// gets associated to that medication (with a mismatch warning if it doesn't match).
function openAddBox(med) {
  const scoped = med && typeof med === 'object';
  const title = scoped ? `Asociar caja · ${esc(med.nombre || 'medicamento')}` : 'Añadir caja (pre-asignar)';
  const planId = scoped ? med.id : undefined;
  openTool(`<div class="qt-modal-h"><h3>${title}</h3><button class="qt-x" id="ab-close">×</button></div>
    ${scoped && med.cn_only ? `<p class="qt-tool-note">Este medicamento está <b>pendiente de caja</b> (CN ${esc(med.cn || '—')}). Elige una caja del inventario que coincida o escanea una nueva.</p>` : ''}
    <div class="az-tabs"><button class="az-tab sel" data-tab="inv">📦 Del inventario</button><button class="az-tab" data-tab="scan">📷 Escanear / pegar</button></div>
    <div id="ab-inv" class="az-tabpane">
      ${scoped ? '' : `<div class="qt-search" style="margin-bottom:10px"><span class="ico">🔎</span><input id="ab-q" placeholder="Filtrar por medicamento o GTIN…" autocomplete="off"></div>`}
      <div id="ab-list" class="az-medlist"></div>
    </div>
    <div id="ab-scan" class="az-tabpane" hidden>
      <p class="qt-tool-note">Escanea el Data Matrix de la caja con la cámara o pega su contenido. Si la caja no está en Data Matrix, se creará allí como <b>pre-asignada</b>${scoped ? ' y quedará asociada a este medicamento' : ''}.</p>
      <div class="qt-tool-row"><button class="qt-btn qt-btn-teal" id="ab-cam">📷 Cámara</button></div>
      <div class="qt-field"><label>Contenido del Data Matrix</label><textarea class="qt-input" id="ab-raw" rows="3" placeholder="Pega aquí el contenido escaneado…"></textarea></div>
      <div class="qt-tool-row"><button class="qt-btn qt-btn-primary" id="ab-add">🔗 ${scoped ? 'Asociar' : 'Pre-asignar'}</button></div>
    </div>`);
  $('ab-close').onclick = closeTool;
  const panes = { inv: $('ab-inv'), scan: $('ab-scan') };
  $('tool-modal-box').querySelectorAll('.az-tab').forEach(t => t.addEventListener('click', () => {
    $('tool-modal-box').querySelectorAll('.az-tab').forEach(x => x.classList.toggle('sel', x === t));
    Object.entries(panes).forEach(([k, el]) => el.hidden = k !== t.dataset.tab);
  }));

  const renderBoxes = (boxes) => {
    const list = $('ab-list');
    if (!boxes.length) { list.innerHTML = `<div class="az-noresult">No hay cajas disponibles (sin reservar)${scoped ? ' que coincidan con este medicamento' : ''}. Usa la pestaña «Escanear / pegar» para dar entrada a una caja nueva.</div>`; return; }
    list.innerHTML = boxes.slice(0, 60).map(b => `<button class="az-medrow" data-item="${b.id}"><span class="az-plan-shape">${shapeSvg(b.shape, b.color, 18)}</span><span class="az-medrow-name">${esc(b.nombre || 'Sin nombre')}<small>${b.serial ? 'Nº ' + esc(b.serial) + ' · ' : ''}${b.caducidad ? 'Cad ' + esc(b.caducidad) + ' · ' : ''}${b.gtin ? 'GTIN ' + esc(b.gtin) : (b.cn ? 'CN ' + esc(b.cn) : '')}</small></span><span class="az-medrow-add">🔗</span></button>`).join('');
    list.querySelectorAll('[data-item]').forEach(btn => btn.addEventListener('click', () => preassign({ item_id: Number(btn.dataset.item), plan_id: planId })));
  };

  // Inventory tab
  if (scoped) {
    (async () => {
      try {
        const boxes = med.cn_only
          ? (await api('/available-cn/' + encodeURIComponent(med.cn || ''))).items
          : (await api('/available/' + encodeURIComponent(med.gtin))).items;
        renderBoxes(boxes);
      } catch (e) { $('ab-list').innerHTML = `<div class="az-noresult">${esc(e.message)}</div>`; }
    })();
  } else {
    const q = $('ab-q');
    const loadInv = async () => {
      try {
        let boxes = [];
        const meds = (await api('/medications?q=' + encodeURIComponent(q.value || ''))).items;
        const pick = meds.filter(m => m.available > 0);
        const chosen = (pick.length ? pick : meds).slice(0, 15);
        for (const m of chosen) { if (!m.available) continue; const av = (await api('/available/' + encodeURIComponent(m.gtin))).items; boxes = boxes.concat(av); }
        renderBoxes(boxes);
      } catch (e) { $('ab-list').innerHTML = `<div class="az-noresult">${esc(e.message)}</div>`; }
    };
    let t = null; q.addEventListener('input', () => { if (t) clearTimeout(t); t = setTimeout(loadInv, 220); });
    loadInv();
  }

  // Scan tab
  $('ab-cam').onclick = () => openScanner('Escanear caja', (text) => { $('ab-raw').value = text; toast('Código leído. Pulsa el botón para asociar.'); });
  $('ab-add').onclick = () => { const raw = $('ab-raw').value.trim(); if (!raw) { toast('Pega o escanea un código.', 'err'); return; } preassign({ raw, plan_id: planId }); };
}
async function preassign(payload) {
  try {
    const data = await api(`/person/${S.person.id}/preassign`, jbody({ ...payload, ym: S.ym }));
    closeTool(); applyFicha(data); toast(payload.plan_id ? 'Caja asociada (pre-asignada).' : 'Caja pre-asignada.');
  } catch (e) {
    // The box doesn't match the plan medication → ask before forcing.
    if (e.status === 409 && e.data && e.data.mismatch) {
      const med = e.data.med || {}, box = e.data.box || {};
      const idOf = o => o.cn ? 'CN ' + o.cn : (o.gtin ? 'GTIN ' + o.gtin : '—');
      const ok = await confirmBox('La caja no coincide',
        `El plan es «${med.nombre || '—'}» (${idOf(med)}) y la caja escaneada es «${box.nombre || '—'}» (${idOf(box)}). ¿Asociarla de todos modos?`, 'Asociar igualmente');
      if (ok) return preassign({ ...payload, force: true });
      return;
    }
    toast(e.message, 'err');
  }
}

// ── Settings (ficha sizes, debounced) ────────────────────────────────────────────
let sizeTimer = null;
function saveSize(patch) {
  S.settings = { ...S.settings, ...patch };
  if (sizeTimer) clearTimeout(sizeTimer);
  sizeTimer = setTimeout(async () => { try { const { settings } = await api('/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(S.settings) }); S.settings = settings; } catch (e) { /* silent */ } }, 400);
}

// ── Manual (full-page, like QR-TIS and Data Matrix) ──────────────────────────────
function viewHelp() {
  S.view = 'help';
  const SECS = [
    { id: 'inicio', icon: '🚀', title: 'Qué es', html: `<p>Une las otras dos apps: las <b>personas</b> vienen de <b>QR (TIS)</b> y las <b>cajas de medicación</b> de <b>Data Matrix</b>. Sirve para preparar la medicación de cada persona y llevar el control de lo que se le va asignando en la aplicación de <b>Salud</b> (que no es la nuestra), mes a mes.</p><div class="qt-note tip">El flujo es siempre el mismo: <b>elegir persona → plan de medicación → pre-asignar cajas → asignar de verdad</b>. Abajo se explica cada paso.</div>` },
    { id: 'persona', icon: '🧑', title: '1) Elegir la persona', html: `<p>En el inicio, busca a la persona por <b>nombre, apellidos, TIS o nº de farmacia</b>. Las personas <b>salen de la app QR (TIS)</b>: si no aparece, hay que <b>darla de alta primero allí</b> (hay un enlace directo) y volver.</p><p>El panel de inicio muestra las personas <b>en seguimiento</b> (con plan o asignaciones) y su estado del mes en curso. Pulsa una para abrir su <b>ficha</b>.</p>` },
    { id: 'importar-med', icon: '📥', title: 'Importar medicación en lote (por Código Nacional)', html: `<p>En el <b>inicio</b>, el botón <b>«📥 Importar medicación (por Código Nacional)»</b> añade medicamentos a muchas personas a la vez. Pega <b>una línea por persona</b>: primero su <b>identificador</b> (TIS o Nº de farmacia, tú eliges arriba) y luego sus <b>Códigos Nacionales</b> separados por comas o espacios. Ejemplo: <code>00930868: 885442, 715000, 659432</code>.</p>
      <div class="qt-note tip">La app busca cada CN en <b>CIMA (AEMPS)</b> para rellenar <b>nombre y código de barras</b>, y lo añade al plan como <b>«pendiente de caja»</b> (con las cajas/mes que indiques). Reimportar el mismo CN <b>lo actualiza</b>, no lo duplica. Si CIMA no responde, se añade igualmente solo con su CN (luego lo completas con «🔎 CIMA» o ✏️). Al terminar verás un resumen con lo añadido y los avisos (personas no encontradas, CN no válidos).</div>` },
    { id: 'plan', icon: '💊', title: '2) Plan de medicación', html: `<p>Cada persona tiene un <b>plan</b>: los medicamentos que toma habitualmente y <b>cuántas cajas al mes</b> de cada uno. Con <b>«➕ Añadir medicamento»</b> lo amplías; con el número <b>× N</b> ajustas las cajas/mes; y la 🗑 lo quita del plan (no toca las cajas ya asignadas). El plan <b>se guarda y se repite cada mes</b>.</p>
      <div class="qt-note tip"><b>Puedes añadir un medicamento de dos formas:</b><ul><li><b>Del catálogo</b>: si ya está en Data Matrix, búscalo por nombre, GTIN o CN y añádelo.</li><li><b>Por Código Nacional</b> (novedad): si la información llega <b>antes de tener el Data Matrix</b>, añádelo solo con su <b>Código Nacional</b> + nombre (y opcionalmente el código de barras). Queda en el plan como <b>«pendiente de caja»</b> (borde discontinuo ámbar), sin caja todavía. Es el paso <b>previo a la pre-asignación</b>.</li></ul>Más adelante le asocias una caja real (ver el paso siguiente) y deja de estar pendiente.</div>
      <div class="qt-note tip"><b>🔎 CIMA (AEMPS).</b> Al añadir por Código Nacional, pulsa <b>«🔎 CIMA»</b> junto al CN para <b>traer el nombre y el código de barras</b> desde la base de datos oficial de medicamentos (AEMPS), o usa <b>«🔎 Buscar en CIMA»</b> para buscar por nombre y elegir. Al traerlo, muestra además la <b>foto de la caja y de la pastilla</b> (fuente: AEMPS). Es una comodidad: si CIMA no está disponible, puedes escribir los datos a mano igual que siempre. La app <b>comprueba que el Código Nacional y el código de barras cuadren</b> (y rellena uno desde el otro), para evitar altas con datos incoherentes. Cada consulta correcta se <b>guarda en local</b> (datos + imágenes), así que ese medicamento sigue funcionando aunque luego CIMA no esté disponible. Y con el botón <b>✏️</b> de un medicamento «pendiente de caja» puedes <b>editar su nombre, CN o código de barras</b> sin tener que borrarlo. (Requiere que el servidor tenga salida a Internet hacia <i>cima.aemps.es</i>.)</div>
      <div class="qt-note tip">En cada medicamento del plan verás, si están disponibles: la <b>foto de la caja</b> (en vez del icono de color), un botón <b>💊</b> para ver la <b>pastilla</b>, y —<b>solo cuando aún no tiene Data Matrix</b>— un botón <b>🏷️ Precinto</b> que muestra el <b>código de barras grande y escaneable</b> para asignarlo en la <b>app de Salud</b>. Si la caja ya tiene Data Matrix, escanéalo mejor (el DM es preferible al precinto).</div>` },
    { id: 'preasignar', icon: '🔗', title: '3) Pre-asignar / asociar cajas', html: `<p>Para cada medicamento del plan, reserva una <b>caja real</b> con <b>«🔗 Pre-asignar»</b> (medicamentos del catálogo) o <b>«🔗 Asociar caja»</b> (medicamentos <b>pendientes de caja</b>, añadidos por Código Nacional). En ambos casos puedes:</p><ul><li><b>Elegir del inventario</b>: una caja «sin utilizar» compatible que ya esté en Data Matrix (para los pendientes de caja, se filtran por su <b>Código Nacional</b>).</li><li><b>Escanear / pegar</b> su Data Matrix: si la caja no estaba en Data Matrix, <b>se crea allí</b> automáticamente como pre-asignada <b>y</b> queda asociada a ese medicamento del plan.</li></ul><p>Si la caja <b>no coincide</b> con el medicamento (por CN/GTIN), la app <b>te avisa</b> y te deja <b>asociarla igualmente</b> si quieres. Al asociar la primera caja, un medicamento «pendiente de caja» pasa a ser normal.</p><p>La caja queda <b>🔗 Pre-asignada</b>: reservada para esa persona pero <b>sigue en stock</b>. Este estado <b>también se ve en la app Data Matrix</b>, para que las dos apps nunca se descuadren.</p>` },
    { id: 'asignar', icon: '✅', title: '4) Asignar de verdad', html: `<p>Cuando ya la asignas en la aplicación de <b>Salud</b>, pulsa <b>«✅ Asignar»</b> sobre esa caja. Pasa a <b>✓ Asignada</b> (se marca <b>utilizada</b> en Data Matrix, sale del inventario) y su Data Matrix se pone en <b>gris</b>.</p>
      <div class="qt-note tip">Al pulsar <b>«✅ Asignar»</b> la app te pide la <b>fecha de la PRÓXIMA liberación</b> de ese medicamento (ya propuesta al <b>mismo día del mes siguiente</b>, editable). Es el momento natural para anotarla: acabas de dispensar la caja y sabes cuándo sale la siguiente. Esa fecha se guarda <b>en el medicamento</b> y gobierna cuándo vuelve a estar disponible (ver la sección siguiente). Puedes dejarla en blanco si aún no la sabes.</div>
      <div class="qt-note tip">Los <b>tres estados</b> de una caja: <b>Sin utilizar</b> → <b>🔗 Pre-asignada</b> (reservada) → <b>✓ Asignada</b> (= utilizada). Puedes <b>↩ Revertir</b> una asignación (vuelve a pre-asignada) o <b>🗑 quitar</b> la caja de la ficha (se libera la reserva y, si estaba asignada, vuelve al inventario). Al asignar, la caja <b>desaparece</b> del inventario; el medicamento vuelve el mes siguiente <b>sin caja</b> hasta que le asocies otra.</div>` },
    { id: 'precinto', icon: '🏷️', title: '5) Asignar sin caja (precinto) y modo escáner', html: `<p>A veces asignas en Salud <b>sin registrar la caja</b> en Data Matrix: basta el <b>precinto</b> (el código de barras). Para eso:</p>
      <ul>
        <li><b>✅ Asignar (manual)</b>: en un medicamento <b>pendiente de caja</b> (o en su tarjeta de «Pendientes de caja»), pulsa <b>«✅ Asignar»</b>. Se marca como <b>asignada por precinto</b> (cuenta como asignada del mes, sin caja) y captura la <b>próxima fecha</b> de liberación.</li>
        <li><b>📟 Modo escáner</b>: pulsa <b>«📟 Modo escáner»</b> en la ficha y pasa el lector por el <b>precinto</b> o el <b>Data Matrix</b>. Como los escáneres emulan un teclado, cada lectura + Enter <b>asigna sola</b> (el DM asocia y asigna la caja; el precinto la marca sin caja) y el panel <b>sigue escuchando</b>, con un registro ✓/✗ en vivo.</li>
      </ul>
      <p>Las asignadas por precinto se ven en <b>«✅ Asignadas por precinto (sin caja)»</b> dentro de la ficha, y se pueden <b>↩ Revertir</b>.</p>` },
    { id: 'pegado', icon: '🏷️', title: 'Control de precintos (pegado en la hoja de Salud)', html: `<p>Salud obliga a <b>recortar el precinto</b> (código de barras) de cada medicación asignada y <b>pegarlo</b> en una hoja oficial de <b>4×7</b> antes de fin de mes. Si no van pegados, <b>no los pagan</b> aunque estén asignados. En el <b>inicio</b>, la sección <b>«🏷️ Control de precintos»</b> lo gestiona.</p>
      <ul>
        <li><b>Cada asignación = un precinto</b>: cuentan tanto las <b>cajas DM asignadas</b> como las asignadas <b>por precinto</b>. Arriba, tres tarjetas-<b>filtro</b>: <b>Por pegar</b>, <b>✓ Pegados</b> y <b>Asignados</b> (todos). Hay selector de <b>mes</b>.</li>
        <li><b>Agrupar</b> por <b>medicamento</b>, <b>persona</b> o <b>residencia</b>; y <b>filtrar</b> por medicamento, por residencia (el grupo de QR·TIS) y por <b>📝 Con notas</b> — todo acumulativo.</li>
        <li><b>📄 Imprimir PDF…</b>: un modal pregunta <b>qué</b> imprimir (por pegar / todos / solo lo filtrado) y <b>cómo ordenarlo</b> (medicamento / persona / residencia, con segundo nivel), y si <b>empezar cada grupo en página nueva</b>. Sale en rejilla <b>4×7</b> para pegar y cotejar.</li>
      </ul>
      <p>Para dar por <b>pegado</b> (deja de aparecer como pendiente) hay tres formas:</p>
      <ol>
        <li><b>A mano</b>: «✅ Pegado» en cada uno, o <b>«✅ Marcar pegados (N)»</b> de todo un grupo o de la vista filtrada.</li>
        <li><b>📟 Escanear para cotejar</b>: pasa el lector por cada precinto; cada lectura marca el <b>siguiente pendiente</b> de ese medicamento y descuenta.</li>
        <li><b>📷 Foto y marcar</b>: adjunta una <b>foto de prueba</b> (se guarda asociada a esos precintos, por si un día reclaman) y los marca pegados.</li>
      </ol>
      <div class="qt-note tip">Los pegados se pueden ver con «Ver también los pegados» y <b>↩ revertir</b>. Las fotos de prueba del mes quedan en una galería al final de la sección.</div>` },
    { id: 'liberacion', icon: '🗓️', title: 'Fecha de liberación, anticipación y avisos 🔔', html: `<p>La <b>fecha de liberación</b> es cuándo Salud deja disponible el medicamento. Vive <b>en el medicamento</b> (no en la caja), porque es <b>recurrente</b>: la caja se dispensa y desaparece, pero el medicamento vuelve cada mes en la misma fecha (p. ej. «sale los 23»).</p>
      <div class="qt-note tip"><b>El medicamento aparece SIEMPRE</b> en el plan; lo que cambia es su <b>estado</b>, marcado por la fecha:<ul><li><b>🗓 Sin fecha — pendiente</b>: no tiene fecha de liberación; se queda así <b>permanentemente</b> hasta que le pongas una.</li><li><b>🗓 Programada</b>: tiene fecha pero aún no llega la <b>efectiva</b>.</li><li><b>✅ Disponible</b>: llegó la fecha efectiva; ya se puede coger/asignar.</li></ul>La etiqueta de estado del medicamento es <b>clicable</b>: abre el modal para poner/cambiar la <b>fecha oficial</b> y los <b>días de anticipación</b>. También se captura sola al <b>Asignar</b> (paso anterior).</div>
      <div class="qt-note tip"><b>Fecha oficial vs. fecha efectiva.</b> La <b>oficial</b> es la que marca Salud; la <b>efectiva</b> es la oficial <b>menos los «días de anticipación»</b> (por defecto <b>15</b>): si sale el 23, ya se puede coger desde el 8. <b>Todos los cálculos</b> (estado en la ficha, la campana 🔔 y las notificaciones por email) usan la <b>efectiva</b>. Los días de anticipación se guardan <b>por medicamento y persona</b>, así que puedes ponerlos distintos en casos excepcionales.</div>
      <p>La <b>campana 🔔</b> (arriba) abre el buscador con tres controles:</p>
      <ul>
        <li><b>Avisar por</b>: <b>Toda la medicación</b> (la persona aparece lista solo cuando <i>todos</i> sus medicamentos están disponibles — un único viaje), <b>Al menos uno</b> (en cuanto lo está el primero) o <b>Por medicamento</b> (uno a uno). Lo que elijas se recuerda y manda el contador rojo de la campana.</li>
        <li><b>Criterio</b>: <b>En o antes de</b> una fecha (lo disponible para esa fecha) o <b>Fecha exacta</b>.</li>
        <li><b>Fecha</b>: por defecto hoy; cámbiala para planificar.</li>
      </ul>
      <p>Los resultados se separan en <b>✅ disponibles</b> y <b>🗓 aún no</b>. En modo por persona, cada fila muestra cuándo estarán <b>todos</b> (o el primero) y un desplegable con cada medicamento y su fecha. Al pulsar te lleva a la ficha.</p>` },
    { id: 'notificaciones', icon: '✉️', title: 'Notificaciones por email', html: `<p>El botón <b>✉️</b> (arriba) abre las <b>notificaciones programadas</b>: la app te envía por email un aviso con las personas a las que les sale medicación en Salud. Puedes crear varias, activarlas/desactivarlas, editarlas o borrarlas.</p>
      <p>Al crear una eliges:</p>
      <ul>
        <li><b>Tipo</b>: <b>Al menos un medicamento</b> o <b>Toda la medicación</b> (agrupa por persona igual que la campana).</li>
        <li><b>Criterio del día</b>: <b>Novedades del día</b> (lo que queda disponible justo ese día) o <b>Acumulado a la fecha</b> (todo lo disponible para ese día). Se calcula sobre la <b>fecha efectiva</b> (oficial − días de anticipación).</li>
        <li><b>Cuándo</b>: <b>Una vez</b> (fecha del calendario) o <b>Recurrente</b> (días de la semana; ninguno = todos los días).</li>
        <li><b>Hora</b> en formato <b>24h (militar)</b>.</li>
        <li><b>Destinatarios</b>: por defecto tu email; añade más separados por comas.</li>
      </ul>
      <p>El email es <b>bonito en HTML</b> e incluye, por cada persona: su <b>QR del TIS</b> (para abrir la app de Salud), sus <b>Data Matrix</b> con los datos de cada caja que le sale, un enlace <b>«Abrir ficha»</b> (va directo a esa persona en la app) y, arriba, <b>«Ver estas N personas en la app»</b> (abre el listado con solo ese grupo).</p>
      <div class="qt-note tip">Pulsa <b>👁 Vista previa</b> para ver el email en una pestaña nueva antes de programarlo, y <b>✉️ Enviar ahora</b> para probarlo en el momento. El envío programado necesita el correo configurado en el servidor (SMTP).</div>` },
    { id: 'seguimiento', icon: '🔎', title: 'Buscar y filtrar «En seguimiento»', html: `<p>El listado <b>«En seguimiento»</b> del inicio está pensado para <b>cientos de personas</b>. Encima tiene sus propios filtros (se combinan entre sí):</p>
      <ul>
        <li><b>Buscador</b>: filtra por nombre, apellidos, TIS o nº de farmacia dentro del seguimiento.</li>
        <li><b>Estado</b>: <b>Falta por asignar</b>, <b>Todo asignado</b>, <b>Con algo listo</b> (ya se puede coger), <b>Sin plan</b>, o Todas.</li>
        <li><b>Residencia</b>: el <b>grupo</b> de la persona en QR (TIS) (lo usamos como residencia).</li>
        <li><b>📝 Con notas</b> y <b>🛒 Solo carrito</b>.</li>
      </ul>
      <p>Se muestran hasta <b>120</b> tarjetas; si hay más, afina el filtro (el contador indica «X de Y»).</p>` },
    { id: 'notas-ent', icon: '📝', title: 'Notas en personas y precintos', html: `<p>Puedes pegar una <b>nota</b> (texto + color) a una <b>persona</b> o a un <b>precinto</b> concreto, para recordar «qué le pasa».</p>
      <ul>
        <li><b>Persona</b>: con el botón <b>📝</b> de su tarjeta en el inicio, o en su <b>ficha</b> (bajo los datos). La nota se ve en ambos sitios.</li>
        <li><b>Precinto</b>: con el botón <b>📝</b> de cada fila en el «Control de precintos».</li>
        <li><b>Filtro «📝 Con notas»</b>: en el seguimiento (personas) y en los precintos, para leer de un vistazo qué pasa.</li>
      </ul>
      <div class="qt-note tip">Estas notas van <b>pegadas a la persona/precinto</b> y son distintas del <b>Tablón de notas (🗒️)</b>, que es un panel libre de post-its del equipo.</div>` },
    { id: 'carrito', icon: '🛒', title: 'Carrito de personas', html: `<p>El botón <b>🛒</b> (arriba) abre el <b>carrito</b>, tu selección personal de personas (como en las otras apps). Añádelas con el <b>🛒</b> de cada tarjeta del seguimiento o desde la <b>ficha</b>.</p>
      <p>En el panel puedes <b>abrir</b> cada persona, <b>sacarla</b> o <b>vaciar</b> el carrito, ver el listado <b>«🛒 Solo carrito»</b>, e <b>imprimir un PDF de los precintos</b> del mes de esas personas (ordenado por persona). Es tu carrito: cada usuario tiene el suyo y se conserva entre sesiones.</p>` },
    { id: 'desde-qr', icon: '🔗', title: 'Ir a la medicación desde QR (TIS)', html: `<p>Desde la <b>ficha de una persona en QR (TIS)</b> hay un botón <b>💊 Medicación</b> que lleva directo a su medicación aquí (indica cuántos medicamentos tiene; si no tiene plan, ofrece crearlo). Solo aparece a quien tenga acceso a esta app.</p>` },
    { id: 'mes', icon: '📅', title: 'Control mensual', html: `<p>El control es <b>mensual</b>: cada mes es un <b>periodo</b> propio de la persona, con su propio recuento. Arriba en la ficha puedes <b>cambiar de mes</b> y <b>cerrar</b> un mes cuando esté completo (o <b>reabrirlo</b>).</p><p>Si Salud aún no ha liberado la medicación, deja las cajas <b>pre-asignadas</b> y vuelve más adelante (a veces varias veces al mes) para <b>asignarlas</b> cuando ya se pueda. El histórico de meses anteriores queda guardado.</p>` },
    { id: 'ficha', icon: '🪪', title: 'La ficha de la persona', html: `<p>La ficha muestra los <b>datos de la persona</b> y su <b>QR del TIS</b> bien grande (para escanearlo en la app de Salud), y cada caja como <b>Data Matrix en color</b> (mismo color por medicamento que en la app Data Matrix). Los <b>recuentos</b> de arriba resumen: plan, en la ficha, por asignar y asignadas.</p><p>Con los deslizadores <b>QR</b> y <b>DM</b> ajustas el tamaño de los códigos; el ajuste se recuerda.</p>` },
    { id: 'notas', icon: '🗒️', title: 'Tablón de notas (post-its)', html: `<p>El botón <b>🗒️</b> (arriba) abre un <b>tablón de notas adhesivas</b> compartidas con el equipo. Puedes tener varios <b>tablones</b> (pestañas): crear, renombrar o borrar (siempre queda al menos uno).</p>
      <ul>
        <li><b>Crear</b>: «➕ Nueva nota». <b>Arrastra</b> por la cabecera para moverla y <b>redimensiona</b> por la esquina inferior derecha. La posición y el tamaño se guardan solos.</li>
        <li><b>Color</b>: los círculos de colores cambian el fondo al instante. <b>Texto</b>: se guarda solo al dejar de escribir.</li>
        <li><b>Compartir</b> (🔗, solo en tus notas): «Visible para todos» o elige usuarios concretos. Solo aparecen los usuarios <b>con acceso a esta app</b> — las notas no se comparten con el resto del hub. <b>Quien puede ver una nota también puede editarla</b> (es una conversación sobre el post-it). Solo el autor (o un administrador) puede borrarla o cambiar con quién se comparte.</li>
        <li><b>🔔 Avisar (recados)</b>: al compartir puedes marcar la nota para que <b>avise</b> a los destinatarios al abrir la app. Se explica en la sección siguiente, <b>«Recados: avisar de una nota»</b>.</li>
      </ul>
      <div class="qt-note tip">El icono <b>🗒️</b> avisa: se pone <b>rojo con un contador</b> cuando tienes <b>notas nuevas sin ver</b>. Las pestañas con novedades muestran un punto. Al abrir un tablón, sus notas se marcan como vistas.</div>` },
    { id: 'recados', icon: '🔔', title: 'Recados: avisar de una nota', html: `<p>Las notas sirven también para <b>dejarse recados entre compañeros</b>: cosas pendientes, información que traspasar, algo que el otro debe tener en cuenta. Para que <b>no pasen desapercibidas</b>, puedes marcar una nota para que <b>avise</b> a las personas con las que la compartes.</p>
      <p><b>Cómo avisar</b> (solo el autor o un administrador):</p>
      <ol>
        <li>Abre <b>🔗 Compartir</b> en tu nota y elige con quién la compartes («todos» o personas concretas).</li>
        <li>Marca la casilla <b>«🔔 Avisar a los destinatarios»</b>. (En una nota <b>privada</b> no está disponible: sin destinatarios no hay a quién avisar.)</li>
      </ol>
      <p><b>Qué ve quien recibe el recado</b>: al <b>abrir la app</b> le aparece un <b>recuadro destacado</b> — <i>«Tienes una nota que requiere tu atención»</i> — con <b>quién</b> se lo dejó, en qué <b>tablón</b> y un <b>extracto</b> del texto. Con <b>«Ver la nota →»</b> (o pulsando el propio recado) va directo al tablón. Si prefiere dejarlo para luego, <b>«Ahora no»</b> y le volverá a salir la próxima vez que entre. Si son varios recados, se listan todos.</p>
      <p><b>El aviso se apaga solo</b> cuando la persona <b>abre el tablón</b> de esa nota (deja de recibir el recuadro). En el tablón, las notas que están avisando se distinguen con un <b>borde ámbar</b> y una campanita <b>🔔</b>.</p>
      <p><b>Volver a avisar</b>: si el destinatario ya la vio pero quieres <b>recordárselo</b>, abre <b>🔗 Compartir</b> y pulsa <b>«🔔 Volver a avisar»</b>. La nota vuelve a avisar aunque ya la hubieran abierto.</p>
      <div class="qt-note tip">Es la forma rápida de decir «oye, mira esto»: escribe el recado en una nota, compártela con quien corresponda y marca 🔔. Esa persona lo verá <b>sí o sí</b> al entrar en la app.</div>` },
    { id: 'viajar', icon: '🔀', title: 'Saltar entre las apps', html: `<p>Arriba, junto al título, tienes el <b>selector</b> <b>QR (TIS) · Data Matrix · Asignación</b> para <b>cambiar de app</b> con un clic. La app en la que estás aparece resaltada.</p>` },
  ];
  const nav = SECS.map(s => `<a data-go="help-${s.id}">${s.icon} ${s.title}</a>`).join('');
  const secs = SECS.map(s => `<section class="qt-help-sec" id="help-${s.id}"><h2><span class="em">${s.icon}</span>${s.title}</h2>${s.html}</section>`).join('');
  main().innerHTML = `<button class="qt-back" id="back">← Volver</button><div class="qt-help-hero"><h1>Manual · Asignación de medicación</h1><p>Cómo preparar y asignar la medicación de cada persona, paso a paso.</p></div><div class="qt-help-wrap"><nav class="qt-help-nav">${nav}</nav><div class="qt-help-content">${secs}</div></div>`;
  $('back').onclick = () => { if (S.person && S.ficha) renderFicha(); else viewHome(); };
  main().querySelectorAll('.qt-help-nav [data-go]').forEach(a => a.addEventListener('click', () => { const el = document.getElementById(a.dataset.go); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }));
  window.scrollTo({ top: 0 });
}

// Close modals on scrim / escape.
document.addEventListener('click', (e) => { if (e.target.classList && e.target.classList.contains('qt-modal')) { e.target.hidden = true; } });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { ['tool-modal', 'scan-modal', 'confirm-modal'].forEach(id => { const m = $(id); if (m && !m.hidden) m.hidden = true; }); } });

boot();
