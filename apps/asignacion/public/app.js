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
};

// ── Tiny helpers ────────────────────────────────────────────────────────────────
function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
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
function openTool(html) { const box = $('tool-modal-box'); box.innerHTML = html; $('tool-modal').hidden = false; }
function closeTool() { $('tool-modal').hidden = true; $('tool-modal-box').innerHTML = ''; }

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
function qrOpts(p, size) {
  const st = S.qrSettings || {};
  return { dark: (p && p.qr_dark) || st.qr_dark || '#0f172a', light: (p && p.qr_light) || st.qr_light || '#ffffff', style: (p && p.qr_style) || st.qr_style || 'square', ecc: st.qr_ecc || 'M', size };
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
    $('help-btn').onclick = viewHelp;
    $('bell-btn').onclick = openNotifications;
    $('go-home').onclick = (e) => { e.preventDefault(); viewHome(); };
    await refreshNotifications();
    await viewHome();
  } catch (e) { main().innerHTML = `<div class="qt-empty">No se pudo cargar: ${esc(e.message)}</div>`; }
}

// ── Notifications (release-date bell) ────────────────────────────────────────────
async function refreshNotifications() {
  try { S.notif = await api('/notifications'); } catch (e) { /* keep previous */ }
  const badge = $('bell-count'); if (!badge) return;
  const n = S.notif.counts ? S.notif.counts.due : 0;
  badge.textContent = n; badge.hidden = !n;
  $('bell-btn').classList.toggle('has-due', !!n);
}
function notifRow(e, kind) {
  const b = e.box;
  const when = kind === 'due'
    ? `<span class="az-note-when st-due">✅ ${e.days === 0 ? 'hoy' : e.days < 0 ? 'desde hace ' + Math.abs(e.days) + ' día(s)' : ''} · ${fmtDate(e.release_at)}</span>`
    : `<span class="az-note-when st-soon">🗓 en ${e.days} día(s) · ${fmtDate(e.release_at)}</span>`;
  return `<button class="az-note" data-open="${e.person.id}" data-ym="${esc(e.ym || '')}">
    <span class="az-note-shape">${b ? shapeSvg(b.shape, b.color, 18) : '📦'}</span>
    <span class="az-note-body"><b>${esc(e.person.apellidos)}, ${esc(e.person.nombre)}</b><small>${esc(b && b.nombre || 'Medicamento')}${b && b.serial ? ' · Nº ' + esc(b.serial) : ''}</small></span>
    ${when}
  </button>`;
}
function openNotifications() {
  const d = S.notif.due || [], u = S.notif.upcoming || [];
  openTool(`<div class="qt-modal-h"><h3>🔔 Avisos de liberación</h3><button class="qt-x" id="nt-close">×</button></div>
    <p class="qt-tool-note">Cajas <b>pre-asignadas</b> con fecha prevista de liberación en la aplicación de Salud.</p>
    <div class="az-note-sec"><div class="az-note-h">✅ Ya se pueden asignar (${d.length})</div>
      ${d.length ? `<div class="az-notelist">${d.map(e => notifRow(e, 'due')).join('')}</div>` : '<div class="az-empty-sm">Nada pendiente de asignar por fecha.</div>'}</div>
    <div class="az-note-sec"><div class="az-note-h">🗓 Próximas a liberar (${u.length})</div>
      ${u.length ? `<div class="az-notelist">${u.map(e => notifRow(e, 'soon')).join('')}</div>` : '<div class="az-empty-sm">No hay próximas programadas.</div>'}</div>`);
  $('nt-close').onclick = closeTool;
  $('tool-modal-box').querySelectorAll('[data-open]').forEach(b => b.addEventListener('click', () => { closeTool(); openPerson(Number(b.dataset.open), b.dataset.ym || undefined); }));
}

// ── Home / panel ─────────────────────────────────────────────────────────────────
async function viewHome() {
  S.view = 'home'; S.person = null; S.ficha = null;
  try { const { items } = await api('/overview'); S.overview = items; } catch (e) { S.overview = []; }
  refreshNotifications();
  renderHome();
}
function renderHome() {
  const rows = S.overview;
  main().innerHTML =
    `<div class="qt-panel az-panel">
       <div class="qt-section-title">Asignación de medicación</div>
       <div class="qt-section-sub">Elige una persona (de QR·TIS) para preparar y asignar su medicación (cajas Data Matrix). Control mensual: ${esc(fmtYm(S.month))}.</div>

       <div class="az-picker">
         <div class="qt-search"><span class="ico">🔎</span><input id="pq" placeholder="Buscar persona por nombre, apellidos, TIS, nº de farmacia…" autocomplete="off" value="${esc(S.searchQuery)}"></div>
         <div id="pq-results" class="az-results"></div>
       </div>

       <div class="qt-section-title" style="margin-top:22px">En seguimiento (${rows.length})</div>
       <div class="qt-section-sub">Personas con plan o asignaciones. El estado es el del mes en curso.</div>
       <div id="ov-body">${overviewHtml(rows)}</div>
     </div>`;
  const pq = $('pq');
  pq.addEventListener('input', () => { S.searchQuery = pq.value; searchPeople(pq.value); });
  if (S.searchQuery) searchPeople(S.searchQuery);
  wireOverview();
}
function statusChip(r) {
  if (!r.plan_count && !r.has_month_period) return `<span class="az-chip az-chip-none">sin plan</span>`;
  const c = r.month_counts;
  if (!r.has_month_period || c.total === 0) return `<span class="az-chip az-chip-todo">⏳ pendiente este mes</span>`;
  const pre = c.preasignada, done = c.asignada;
  if (pre > 0) return `<span class="az-chip az-chip-pre">🔗 ${done} asignada(s) · ${pre} por asignar</span>`;
  return `<span class="az-chip az-chip-done">✓ ${done} asignada(s)</span>`;
}
function overviewHtml(rows) {
  if (!rows.length) return '<div class="qt-empty">Aún no hay personas en seguimiento. Busca una persona arriba y crea su plan.</div>';
  return `<div class="az-cards">` + rows.map(r => {
    const p = r.person;
    return `<div class="az-card ${r.ready_count ? 'has-ready' : ''}" data-open="${p.id}">
      <div class="az-card-h"><span class="az-card-name">${esc(p.apellidos)}, ${esc(p.nombre)}</span>${statusChip(r)}</div>
      ${r.ready_count ? `<div class="az-card-ready">🔔 ${r.ready_count} caja(s) ya se pueden asignar</div>` : ''}
      <div class="az-card-sub">TIS ${esc(fmtTis(p.tis))}${p.pharmacy_no ? ' · Farmacia ' + esc(p.pharmacy_no) : ''}</div>
      <div class="az-card-sub">${r.plan_count} medicamento(s) en el plan · ${r.planned_total} caja(s)/mes${r.latest ? ' · último: ' + esc(fmtYm(r.latest.ym)) : ''}</div>
    </div>`;
  }).join('') + `</div>`;
}
function wireOverview() { main().querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => openPerson(Number(el.dataset.open)))); }

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

         <div class="az-sec-h"><span>💊 Plan de medicación</span><button class="qt-btn qt-btn-ghost qt-btn-sm" id="add-med">➕ Añadir medicamento</button></div>
         <div class="az-plan">${planHtml(f.plan, closed)}</div>

         <div class="az-sec-h"><span>📦 Cajas de la ficha (${f.lines.length})</span><button class="qt-btn qt-btn-ghost qt-btn-sm" id="add-box" ${closed ? 'disabled' : ''}>➕ Añadir DM</button></div>
         <div class="az-lines">${linesHtml(f.lines, closed, dmSize)}</div>
       </div>
     </div>`;

  $('back').onclick = viewHome;
  $('month-sel').onchange = (e) => openPerson(p.id, e.target.value);
  if ($('per-close')) $('per-close').onclick = async () => { try { applyFicha(await api(`/period/${per.id}/close`, { method: 'POST' })); toast('Mes cerrado.'); } catch (er) { toast(er.message, 'err'); } };
  if ($('per-reopen')) $('per-reopen').onclick = async () => { try { applyFicha(await api(`/period/${per.id}/reopen`, { method: 'POST' })); toast('Mes reabierto.'); } catch (er) { toast(er.message, 'err'); } };
  $('add-med').onclick = openMedPicker;
  if ($('add-box')) $('add-box').onclick = () => openAddBox(null);

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

function planHtml(plan, closed) {
  if (!plan.length) return '<div class="az-empty-sm">Sin medicamentos en el plan. Pulsa «➕ Añadir medicamento».</div>';
  return plan.map(m => {
    const need = m.qty, done = m.asignada, att = m.attached;
    const short = att < need;
    return `<div class="az-planrow" data-gtin="${esc(m.gtin)}">
      <span class="az-plan-shape">${shapeSvg(m.shape, m.color, 20)}</span>
      <span class="az-plan-name">${esc(m.nombre || 'Sin nombre')}<small>GTIN ${esc(m.gtin)} · ${m.available} disponible(s) en stock</small></span>
      <span class="az-plan-prog ${short ? 'is-short' : 'is-ok'}">${done}/${need} asignadas · ${att} en ficha</span>
      <span class="az-plan-qty">×<input type="number" class="az-qty" data-plan="${m.id}" value="${m.qty}" min="1" max="99" ${closed ? 'disabled' : ''}></span>
      ${closed ? '' : `<button class="qt-btn qt-btn-teal qt-btn-sm" data-pre="${esc(m.gtin)}">🔗 Pre-asignar</button>`}
      <button class="qt-iconbtn danger" data-delplan="${m.id}" title="Quitar del plan">🗑</button>
    </div>`;
  }).join('');
}
function wirePlan(closed) {
  main().querySelectorAll('[data-delplan]').forEach(b => b.addEventListener('click', async () => {
    if (!(await confirmBox('Quitar del plan', '¿Quitar este medicamento del plan de la persona? No afecta a las cajas ya asignadas.', 'Quitar'))) return;
    try { const { plan } = await api('/plan/' + b.dataset.delplan, { method: 'DELETE' }); S.ficha.plan = mergePlan(S.ficha.plan, plan); renderFicha(); } catch (e) { toast(e.message, 'err'); }
  }));
  main().querySelectorAll('.az-qty').forEach(inp => inp.addEventListener('change', async () => {
    try { await api('/plan/' + inp.dataset.plan, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ qty: Number(inp.value) }) }); await reloadFicha(); } catch (e) { toast(e.message, 'err'); }
  }));
  main().querySelectorAll('[data-pre]').forEach(b => b.addEventListener('click', () => openAddBox(b.dataset.pre)));
}
// Keep progress fields (attached/asignada) when the server returns a bare plan list.
function mergePlan(oldPlan, fresh) { const by = new Map((oldPlan || []).map(p => [p.gtin, p])); return fresh.map(p => ({ ...p, attached: (by.get(p.gtin) || {}).attached || 0, asignada: (by.get(p.gtin) || {}).asignada || 0 })); }

// Release-date chip for a pre-asignada box (when Salud will free it).
function releaseChip(ln) {
  if (ln.release_state === 'lista') return `<span class="az-rel az-rel-ready">✅ Ya se puede asignar${ln.release_at ? ' · desde ' + fmtDate(ln.release_at) : ''}</span>`;
  if (ln.release_state === 'programada') return `<span class="az-rel az-rel-soon">🗓 Se libera ${fmtDate(ln.release_at)} · ${ln.release_days === 1 ? 'mañana' : 'faltan ' + ln.release_days + ' días'}</span>`;
  return `<span class="az-rel az-rel-none">🗓 Sin fecha de liberación</span>`;
}
function lineHtml(ln, closed, dmSize) {
  const box = ln.box;
  if (!box) return `<div class="az-line az-line-gone"><div class="az-line-info"><b>Caja eliminada</b><small>La caja ya no existe en Data Matrix.</small></div><button class="qt-iconbtn danger" data-delline="${ln.id}" title="Quitar">🗑</button></div>`;
  const asignada = ln.state === 'asignada';
  const ready = ln.release_state === 'lista';
  const cls = asignada ? 'is-asignada' : ready ? 'is-ready' : 'is-pre';
  return `<div class="az-line ${cls}" data-id="${ln.id}">
    <div class="az-line-dm ${asignada ? 'is-grey' : ''}" data-raw="${esc(box.raw)}" data-color="${esc(box.color)}">${dmSvg(box.raw, { dark: asignada ? '#9aa7b4' : box.color, light: '#ffffff', size: dmSize })}</div>
    <div class="az-line-info">
      <b>${shapeSvg(box.shape, box.color, 14)} ${esc(box.nombre || 'Sin nombre')}</b>
      <small>${box.serial ? 'Nº ' + esc(box.serial) + ' · ' : ''}${box.caducidad ? 'Cad ' + cadDisplay(box.caducidad) : 'GTIN ' + esc(box.gtin || '—')}</small>
      <span class="az-line-state ${asignada ? 'st-done' : 'st-pre'}">${asignada ? '✓ Asignada' + (ln.assigned_at ? ' · ' + fmtDate(ln.assigned_at) : '') : '🔗 Pre-asignada'}</span>
      ${asignada ? '' : releaseChip(ln)}
    </div>
    <div class="az-line-actions">
      ${asignada
        ? (closed ? '' : `<button class="qt-btn qt-btn-ghost qt-btn-sm" data-unassign="${ln.id}">↩ Revertir</button>`)
        : (closed ? '' : `<button class="qt-btn qt-btn-teal qt-btn-sm" data-assign="${ln.id}">✅ Asignar</button>`)}
      ${asignada || closed ? '' : `<button class="qt-iconbtn" data-release="${ln.id}" title="Fecha de liberación (Salud)">🗓</button>`}
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
function wireLines(closed) {
  main().querySelectorAll('[data-assign]').forEach(b => b.addEventListener('click', async () => {
    try { applyFicha(await api('/line/' + b.dataset.assign + '/assign', { method: 'POST' })); toast('Caja asignada (marcada utilizada).'); } catch (e) { toast(e.message, 'err'); }
  }));
  main().querySelectorAll('[data-unassign]').forEach(b => b.addEventListener('click', async () => {
    try { applyFicha(await api('/line/' + b.dataset.unassign + '/unassign', { method: 'POST' })); toast('Asignación revertida (vuelve a pre-asignada).'); } catch (e) { toast(e.message, 'err'); }
  }));
  main().querySelectorAll('[data-delline]').forEach(b => b.addEventListener('click', async () => {
    if (!(await confirmBox('Quitar caja', '¿Quitar esta caja de la ficha? Se libera la reserva y, si estaba asignada, vuelve al inventario.', 'Quitar'))) return;
    try { applyFicha(await api('/line/' + b.dataset.delline, { method: 'DELETE' })); toast('Caja retirada de la ficha.'); } catch (e) { toast(e.message, 'err'); }
  }));
  main().querySelectorAll('[data-release]').forEach(b => b.addEventListener('click', () => {
    const ln = (S.ficha.lines || []).find(x => x.id === Number(b.dataset.release)); if (ln) openReleasePicker(ln);
  }));
}

// Set the date on which Salud will free a pre-asignada box (drives the bell).
function openReleasePicker(ln) {
  const box = ln.box || {};
  const cur = ln.release_at || '';
  openTool(`<div class="qt-modal-h"><h3>🗓 Fecha de liberación</h3><button class="qt-x" id="rp-close">×</button></div>
    <p class="qt-tool-note">Fecha en la que la aplicación de Salud liberará esta caja para poder asignarla. Ese día aparecerá en la campana 🔔.</p>
    <div class="qt-field"><label>Medicamento</label><div class="az-rp-med">${shapeSvg(box.shape, box.color, 18)} ${esc(box.nombre || 'Sin nombre')}${box.serial ? ' · Nº ' + esc(box.serial) : ''}</div></div>
    <div class="qt-field"><label>Fecha prevista de liberación</label><input type="date" class="qt-input" id="rp-date" value="${esc(cur)}"></div>
    <div class="qt-modal-actions">
      ${cur ? '<button class="qt-btn qt-btn-ghost" id="rp-clear">Quitar fecha</button>' : ''}
      <button class="qt-btn qt-btn-ghost" id="rp-cancel">Cancelar</button>
      <button class="qt-btn qt-btn-primary" id="rp-save">Guardar</button>
    </div>`);
  $('rp-close').onclick = closeTool; $('rp-cancel').onclick = closeTool;
  const send = async (date) => {
    try { applyFicha(await api('/line/' + ln.id + '/release', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ date }) })); closeTool(); toast(date ? 'Fecha de liberación guardada.' : 'Fecha eliminada.'); }
    catch (e) { toast(e.message, 'err'); }
  };
  $('rp-save').onclick = () => { const v = $('rp-date').value; if (!v) { toast('Elige una fecha o pulsa «Quitar fecha».', 'err'); return; } send(v); };
  if ($('rp-clear')) $('rp-clear').onclick = () => send('');
}

// ── Medication picker (add a medication to the plan) ─────────────────────────────
function openMedPicker() {
  openTool(`<div class="qt-modal-h"><h3>Añadir medicamento al plan</h3><button class="qt-x" id="mp-close">×</button></div>
    <p class="qt-tool-note">Solo medicamentos que ya están en <b>Data Matrix</b>. Si falta alguno, añádelo allí (escanea una caja o impórtalo).</p>
    <div class="qt-search" style="margin-bottom:10px"><span class="ico">🔎</span><input id="mp-q" placeholder="Buscar medicamento por nombre, GTIN o CN…" autocomplete="off"></div>
    <div id="mp-list" class="az-medlist"></div>`);
  $('mp-close').onclick = closeTool;
  const q = $('mp-q');
  const load = async () => {
    try {
      const { items } = await api('/medications?q=' + encodeURIComponent(q.value || ''));
      const list = $('mp-list');
      if (!items.length) { list.innerHTML = `<div class="az-noresult">No hay medicamentos en Data Matrix que coincidan. <a href="/datamatrix" target="_blank" rel="noopener">Ábrelo para añadirlo</a>.</div>`; return; }
      list.innerHTML = items.slice(0, 40).map(m => `<button class="az-medrow" data-gtin="${esc(m.gtin)}"><span class="az-plan-shape">${shapeSvg(m.shape, m.color, 18)}</span><span class="az-medrow-name">${esc(m.nombre || 'Sin nombre')}<small>GTIN ${esc(m.gtin)}${m.cn ? ' · CN ' + esc(m.cn) : ''} · ${m.available} en stock</small></span><span class="az-medrow-add">➕</span></button>`).join('');
      list.querySelectorAll('[data-gtin]').forEach(b => b.addEventListener('click', () => addMedToPlan(b.dataset.gtin)));
    } catch (e) { $('mp-list').innerHTML = `<div class="az-noresult">${esc(e.message)}</div>`; }
  };
  let t = null; q.addEventListener('input', () => { if (t) clearTimeout(t); t = setTimeout(load, 200); });
  load();
}
async function addMedToPlan(gtin) {
  try {
    await api(`/person/${S.person.id}/plan`, jbody({ gtin, qty: 1 }));
    closeTool(); await reloadFicha(); toast('Medicamento añadido al plan.');
  } catch (e) { toast(e.message, 'err'); }
}

// ── Add a box to the ficha (pre-assign): from inventory or by scanning ───────────
function openAddBox(gtin) {
  openTool(`<div class="qt-modal-h"><h3>Añadir caja (pre-asignar)${gtin ? '' : ''}</h3><button class="qt-x" id="ab-close">×</button></div>
    <div class="az-tabs"><button class="az-tab sel" data-tab="inv">📦 Del inventario</button><button class="az-tab" data-tab="scan">📷 Escanear / pegar</button></div>
    <div id="ab-inv" class="az-tabpane">
      <div class="qt-search" style="margin-bottom:10px"><span class="ico">🔎</span><input id="ab-q" placeholder="Filtrar por medicamento o GTIN…" autocomplete="off" value="${gtin ? esc(gtin) : ''}"></div>
      <div id="ab-list" class="az-medlist"></div>
    </div>
    <div id="ab-scan" class="az-tabpane" hidden>
      <p class="qt-tool-note">Escanea el Data Matrix de la caja con la cámara o pega su contenido. Si la caja no está en Data Matrix, se creará allí como <b>pre-asignada</b>.</p>
      <div class="qt-tool-row"><button class="qt-btn qt-btn-teal" id="ab-cam">📷 Cámara</button></div>
      <div class="qt-field"><label>Contenido del Data Matrix</label><textarea class="qt-input" id="ab-raw" rows="3" placeholder="Pega aquí el contenido escaneado…"></textarea></div>
      <div class="qt-tool-row"><button class="qt-btn qt-btn-primary" id="ab-add">🔗 Pre-asignar</button></div>
    </div>`);
  $('ab-close').onclick = closeTool;
  const panes = { inv: $('ab-inv'), scan: $('ab-scan') };
  main(); // noop
  $('tool-modal-box').querySelectorAll('.az-tab').forEach(t => t.addEventListener('click', () => {
    $('tool-modal-box').querySelectorAll('.az-tab').forEach(x => x.classList.toggle('sel', x === t));
    Object.entries(panes).forEach(([k, el]) => el.hidden = k !== t.dataset.tab);
  }));

  // Inventory tab
  const q = $('ab-q');
  const loadInv = async () => {
    const list = $('ab-list');
    const query = norm(q.value);
    try {
      // If the filter looks like a specific GTIN, use the fast endpoint; else pull
      // the medication list and show available boxes across matches.
      let boxes = [];
      const meds = (await api('/medications?q=' + encodeURIComponent(q.value || ''))).items;
      const pick = gtin ? meds.filter(m => m.gtin === gtin) : meds.filter(m => m.available > 0);
      const chosen = (pick.length ? pick : meds).slice(0, 15);
      for (const m of chosen) {
        if (!m.available) continue;
        const av = (await api('/available/' + encodeURIComponent(m.gtin))).items;
        boxes = boxes.concat(av);
      }
      if (!boxes.length) { list.innerHTML = `<div class="az-noresult">No hay cajas disponibles (sin reservar) para este filtro. Usa la pestaña «Escanear / pegar» para dar entrada a una caja nueva.</div>`; return; }
      list.innerHTML = boxes.slice(0, 60).map(b => `<button class="az-medrow" data-item="${b.id}"><span class="az-plan-shape">${shapeSvg(b.shape, b.color, 18)}</span><span class="az-medrow-name">${esc(b.nombre || 'Sin nombre')}<small>${b.serial ? 'Nº ' + esc(b.serial) + ' · ' : ''}${b.caducidad ? 'Cad ' + esc(b.caducidad) + ' · ' : ''}GTIN ${esc(b.gtin || '—')}</small></span><span class="az-medrow-add">🔗</span></button>`).join('');
      list.querySelectorAll('[data-item]').forEach(btn => btn.addEventListener('click', () => preassign({ item_id: Number(btn.dataset.item) })));
    } catch (e) { list.innerHTML = `<div class="az-noresult">${esc(e.message)}</div>`; }
  };
  let t = null; q.addEventListener('input', () => { if (t) clearTimeout(t); t = setTimeout(loadInv, 220); });
  loadInv();

  // Scan tab
  $('ab-cam').onclick = () => openScanner('Escanear caja', (text) => { $('ab-raw').value = text; toast('Código leído. Pulsa «Pre-asignar».'); });
  $('ab-add').onclick = () => { const raw = $('ab-raw').value.trim(); if (!raw) { toast('Pega o escanea un código.', 'err'); return; } preassign({ raw }); };
}
async function preassign(payload) {
  try {
    const data = await api(`/person/${S.person.id}/preassign`, jbody({ ...payload, ym: S.ym }));
    closeTool(); applyFicha(data); toast('Caja pre-asignada.');
  } catch (e) { toast(e.message, 'err'); }
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
    { id: 'plan', icon: '💊', title: '2) Plan de medicación', html: `<p>Cada persona tiene un <b>plan</b>: los medicamentos que toma habitualmente y <b>cuántas cajas al mes</b> de cada uno. Los medicamentos <b>solo pueden salir de Data Matrix</b>; si falta alguno, se añade allí (escaneando una caja o importando el catálogo).</p><p>El plan <b>se guarda y se repite cada mes</b>, así no hay que reintroducirlo. Con <b>«➕ Añadir medicamento»</b> lo amplías; con el número <b>× N</b> ajustas las cajas/mes; y la 🗑 lo quita del plan (no toca las cajas ya asignadas).</p>` },
    { id: 'preasignar', icon: '🔗', title: '3) Pre-asignar cajas', html: `<p>Para cada medicamento del plan, reserva una <b>caja real</b> con <b>«🔗 Pre-asignar»</b> (o «➕ Añadir DM»). Puedes:</p><ul><li><b>Elegir del inventario</b>: una caja «sin utilizar» de ese medicamento que ya esté en Data Matrix.</li><li><b>Escanear / pegar</b> su Data Matrix: si la caja no estaba en Data Matrix, <b>se crea allí</b> automáticamente como pre-asignada.</li></ul><p>La caja queda <b>🔗 Pre-asignada</b>: reservada para esa persona pero <b>sigue en stock</b> (no se ha dispensado). Este estado <b>también se ve en la app Data Matrix</b>, para que las dos apps nunca se descuadren.</p>` },
    { id: 'asignar', icon: '✅', title: '4) Asignar de verdad', html: `<p>Cuando ya la asignas en la aplicación de <b>Salud</b>, pulsa <b>«✅ Asignar»</b> sobre esa caja. Pasa a <b>✓ Asignada</b> (se marca <b>utilizada</b> en Data Matrix, sale del inventario) y su Data Matrix se pone en <b>gris</b>.</p><div class="qt-note tip">Los <b>tres estados</b> de una caja: <b>Sin utilizar</b> → <b>🔗 Pre-asignada</b> (reservada) → <b>✓ Asignada</b> (= utilizada). Puedes <b>↩ Revertir</b> una asignación (vuelve a pre-asignada) o <b>🗑 quitar</b> la caja de la ficha (se libera la reserva y, si estaba asignada, vuelve al inventario).</div>` },
    { id: 'liberacion', icon: '🗓️', title: 'Fecha de liberación y avisos 🔔', html: `<p>A veces Salud <b>todavía no ha liberado</b> un Data Matrix y no se puede asignar. En esa caja pre-asignada, pulsa <b>🗓</b> y anota la <b>fecha prevista de liberación</b>.</p><p>Ese día, la caja aparece en la <b>campana 🔔</b> (arriba) dentro de <b>«✅ Ya se pueden asignar»</b>, y mientras tanto la verás en <b>«🗓 Próximas a liberar»</b> con los días que faltan. Cada aviso te lleva directo a la ficha de esa persona.</p><div class="qt-note">Así <b>no hay que recordar</b> cuándo volver: la app avisa sola. La campana muestra un contador rojo de cuántas cajas ya se pueden asignar.</div>` },
    { id: 'mes', icon: '📅', title: 'Control mensual', html: `<p>El control es <b>mensual</b>: cada mes es un <b>periodo</b> propio de la persona, con su propio recuento. Arriba en la ficha puedes <b>cambiar de mes</b> y <b>cerrar</b> un mes cuando esté completo (o <b>reabrirlo</b>).</p><p>Si Salud aún no ha liberado la medicación, deja las cajas <b>pre-asignadas</b> y vuelve más adelante (a veces varias veces al mes) para <b>asignarlas</b> cuando ya se pueda. El histórico de meses anteriores queda guardado.</p>` },
    { id: 'ficha', icon: '🪪', title: 'La ficha de la persona', html: `<p>La ficha muestra los <b>datos de la persona</b> y su <b>QR del TIS</b> bien grande (para escanearlo en la app de Salud), y cada caja como <b>Data Matrix en color</b> (mismo color por medicamento que en la app Data Matrix). Los <b>recuentos</b> de arriba resumen: plan, en la ficha, por asignar y asignadas.</p><p>Con los deslizadores <b>QR</b> y <b>DM</b> ajustas el tamaño de los códigos; el ajuste se recuerda.</p>` },
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
