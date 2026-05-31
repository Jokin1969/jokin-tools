/* Bitácora — front-end. Talks to /bitacora/api/*. */
const API = '/bitacora/api';
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

let META = { niveles: ['Bajo', 'Medio', 'Alto'], categorias: [], factores: [] };
const state = { search: '', sort: 'fecha', order: 'desc', page: 1, filters: { nivel: [], categoria: [], factores: [], from: '', to: '', notado: false } };
let currentIds = [];   // ordered ids for prev/next in detail view

// ─── Toast ──────────────────────────────────────────────────────────────────
let toastTimer = null;
function toast(msg, kind = '') {
  const t = $('toast');
  t.textContent = msg;
  t.className = `toast ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add('hidden'), 4000);
}

// ─── Init ─────────────────────────────────────────────────────────────────────
(async function init() {
  try {
    const r = await fetch(`${API}/meta`);
    if (r.ok) META = await r.json();
  } catch { /* defaults */ }

  buildSelect($('f-nivel'), META.niveles);
  buildSelect($('f-categoria'), ['', ...META.categorias], '(sin categoría)');
  buildChips($('f-factores'), META.factores, true);   // form factor chips (multi)
  buildChips($('filter-nivel'), META.niveles, false, 'nivel');
  buildChips($('filter-categoria'), META.categorias, false, 'categoria');
  buildChips($('filter-factores'), META.factores, false, 'factores');

  wireEvents();
  loadList();
  loadStats();
})();

function buildSelect(sel, options, blankLabel) {
  sel.innerHTML = options.map(o =>
    `<option value="${esc(o)}">${o === '' ? esc(blankLabel || '—') : esc(o)}</option>`).join('');
}

// mode multi=true → form (toggle, no reload). Otherwise a filter group.
function buildChips(container, options, isFormFactor, filterKey) {
  container.innerHTML = options.map(o => `<span class="chip" data-val="${esc(o)}">${esc(o)}</span>`).join('');
  container.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      chip.classList.toggle('active');
      if (!isFormFactor) {
        const active = [...container.querySelectorAll('.chip.active')].map(c => c.dataset.val);
        state.filters[filterKey] = active;
        state.page = 1;
        loadList();
      }
    });
  });
}

// ─── Events ─────────────────────────────────────────────────────────────────
function wireEvents() {
  let searchTimer = null;
  $('search').addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.search = e.target.value.trim(); state.page = 1; loadList(); }, 280);
  });
  $('sort').addEventListener('change', (e) => { state.sort = e.target.value; loadList(); });
  $('order').addEventListener('change', (e) => { state.order = e.target.value; loadList(); });
  $('btn-toggle-filters').addEventListener('click', () => {
    const p = $('filters-panel');
    p.classList.toggle('hidden');
    $('btn-toggle-filters').textContent = p.classList.contains('hidden') ? '▼ Filtros' : '▲ Filtros';
  });
  $('filter-from').addEventListener('change', (e) => { state.filters.from = e.target.value; state.page = 1; loadList(); });
  $('filter-to').addEventListener('change', (e) => { state.filters.to = e.target.value; state.page = 1; loadList(); });
  $('filter-notado').addEventListener('change', (e) => { state.filters.notado = e.target.checked; state.page = 1; loadList(); });
  $('btn-reset-filters').addEventListener('click', resetFilters);

  $('btn-new').addEventListener('click', () => openForm());
  $('btn-new-empty').addEventListener('click', () => openForm());
  $('btn-close-form').addEventListener('click', closeForm);
  $('btn-cancel').addEventListener('click', closeForm);
  $('entry-form').addEventListener('submit', submitForm);
  $('f-notado').addEventListener('change', (e) => { $('f-quien-wrap').style.display = e.target.checked ? '' : 'none'; });

  $('btn-close-detail').addEventListener('click', () => $('modal-detail').classList.add('hidden'));
  $('btn-export').addEventListener('click', doExport);
  $('btn-report').addEventListener('click', doReport);
  $('btn-patterns').addEventListener('click', togglePatterns);
  $('btn-close-patterns').addEventListener('click', () => $('patterns-panel').classList.add('hidden'));

  // Close modals on overlay click
  document.querySelectorAll('.modal-overlay').forEach(ov => {
    ov.addEventListener('click', (e) => { if (e.target === ov) ov.classList.add('hidden'); });
  });
}

function resetFilters() {
  state.filters = { nivel: [], categoria: [], factores: [], from: '', to: '', notado: false };
  $('filter-from').value = ''; $('filter-to').value = ''; $('filter-notado').checked = false;
  document.querySelectorAll('#filter-nivel .chip, #filter-categoria .chip, #filter-factores .chip').forEach(c => c.classList.remove('active'));
  state.page = 1;
  loadList();
}

// ─── List ─────────────────────────────────────────────────────────────────────
function buildQuery() {
  const f = state.filters;
  const q = new URLSearchParams();
  if (state.search) q.set('search', state.search);
  q.set('sort', state.sort); q.set('order', state.order); q.set('page', state.page);
  if (f.nivel.length) q.set('nivel', f.nivel.join(','));
  if (f.categoria.length) q.set('categoria', f.categoria.join(','));
  if (f.factores.length) q.set('factores', f.factores.join(','));
  if (f.from) q.set('date_from', f.from);
  if (f.to) q.set('date_to', f.to);
  if (f.notado) q.set('notado', '1');
  return q;
}

async function loadList() {
  try {
    const q = buildQuery();
    const r = await fetch(`${API}/entries?${q}`);
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Error');
    renderList(data);
    // refresh id list for prev/next using same sort
    const idsR = await fetch(`${API}/ids?sort=${state.sort}&order=${state.order}`);
    currentIds = idsR.ok ? await idsR.json() : [];
  } catch (err) {
    toast(err.message, 'err');
  }
}

async function loadStats() {
  try {
    const r = await fetch(`${API}/stats`);
    if (!r.ok) return;
    const s = await r.json();
    $('stat-total').textContent = `${s.total} ${s.total === 1 ? 'entrada' : 'entradas'}`;
  } catch { /* ignore */ }
}

function renderList({ rows, total, page, limit }) {
  const body = $('list-body');
  const empty = $('empty-state');
  if (!rows.length) {
    body.innerHTML = '';
    empty.classList.remove('hidden');
    $('list-count').textContent = '0 resultados';
    $('pagination').innerHTML = '';
    return;
  }
  empty.classList.add('hidden');
  body.innerHTML = rows.map(rowHtml).join('');
  body.querySelectorAll('tr').forEach(tr => tr.addEventListener('click', () => openDetail(Number(tr.dataset.id))));
  $('list-count').textContent = `${total} ${total === 1 ? 'resultado' : 'resultados'}`;
  renderPagination(total, page, limit);
}

function rowHtml(e) {
  const hecho = e.hecho.length > 160 ? e.hecho.slice(0, 160) + '…' : e.hecho;
  // cell-empty marks blank cells so the mobile card layout can hide them.
  const catEmpty = e.categoria ? '' : ' cell-empty';
  const lugarEmpty = e.lugar ? '' : ' cell-empty';
  return `<tr data-id="${e.id}">
    <td class="cell-fecha">${esc(e.fecha)}</td>
    <td class="cell-nivel"><span class="nivel-badge nivel-${esc(e.nivel)}">${esc(e.nivel)}</span></td>
    <td class="cell-cat${catEmpty}">${e.categoria ? `<span class="cat-tag">${esc(e.categoria)}</span>` : '<span class="cell-muted">—</span>'}</td>
    <td class="cell-hecho">${esc(hecho)}</td>
    <td class="cell-lugar cell-muted${lugarEmpty}">${esc(e.lugar || '—')}</td>
    <td class="row-arrow">→</td>
  </tr>`;
}

function renderPagination(total, page, limit) {
  const pages = Math.ceil(total / limit);
  const pag = $('pagination');
  if (pages <= 1) { pag.innerHTML = ''; return; }
  pag.innerHTML = '';
  const prev = Object.assign(document.createElement('button'), { className: 'btn btn-ghost btn-sm', textContent: '← Anterior', disabled: page <= 1 });
  const next = Object.assign(document.createElement('button'), { className: 'btn btn-ghost btn-sm', textContent: 'Siguiente →', disabled: page >= pages });
  const info = Object.assign(document.createElement('span'), { textContent: `Página ${page} de ${pages}` });
  prev.addEventListener('click', () => { state.page--; loadList(); });
  next.addEventListener('click', () => { state.page++; loadList(); });
  pag.append(prev, info, next);
}

// ─── Form (create / edit) ──────────────────────────────────────────────────────
function openForm(entry) {
  $('form-title').textContent = entry ? 'Editar entrada' : 'Nueva entrada';
  $('f-id').value = entry ? entry.id : '';
  $('f-fecha').value = entry ? entry.fecha : new Date().toISOString().slice(0, 10);
  $('f-nivel').value = entry ? entry.nivel : 'Bajo';
  $('f-lugar').value = entry ? (entry.lugar || '') : '';
  $('f-categoria').value = entry ? (entry.categoria || '') : '';
  $('f-hecho').value = entry ? entry.hecho : '';
  $('f-como').value = entry ? (entry.como || '') : '';
  $('f-comentario').value = entry ? (entry.comentario || '') : '';
  const factores = entry && entry.factores ? entry.factores.split(',') : [];
  $('f-factores').querySelectorAll('.chip').forEach(c => c.classList.toggle('active', factores.includes(c.dataset.val)));
  $('f-notado').checked = entry ? !!entry.notado_otros : false;
  $('f-quien-wrap').style.display = $('f-notado').checked ? '' : 'none';
  $('f-quien').value = entry ? (entry.notado_quien || '') : '';
  $('modal-detail').classList.add('hidden');
  $('modal-form').classList.remove('hidden');
  $('f-fecha').focus();
}
function closeForm() { $('modal-form').classList.add('hidden'); }

async function submitForm(e) {
  e.preventDefault();
  const id = $('f-id').value;
  const payload = {
    fecha: $('f-fecha').value,
    nivel: $('f-nivel').value,
    lugar: $('f-lugar').value.trim(),
    categoria: $('f-categoria').value,
    hecho: $('f-hecho').value.trim(),
    como: $('f-como').value.trim(),
    comentario: $('f-comentario').value.trim(),
    factores: [...$('f-factores').querySelectorAll('.chip.active')].map(c => c.dataset.val).join(','),
    notado_otros: $('f-notado').checked,
    notado_quien: $('f-quien').value.trim(),
  };
  if (!payload.fecha) return toast('La fecha es obligatoria.', 'err');
  if (!payload.hecho) return toast('El hecho es obligatorio.', 'err');

  const btn = $('btn-submit'); btn.disabled = true;
  try {
    const url = id ? `${API}/entries/${id}` : `${API}/entries`;
    const method = id ? 'PUT' : 'POST';
    const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Error al guardar');
    closeForm();
    toast(id ? 'Entrada actualizada.' : 'Entrada registrada.', 'ok');
    loadList(); loadStats();
  } catch (err) {
    toast(err.message, 'err');
  } finally {
    btn.disabled = false;
  }
}

// ─── Detail ─────────────────────────────────────────────────────────────────────
let detailEntry = null;
async function openDetail(id) {
  try {
    const r = await fetch(`${API}/entries/${id}`);
    const e = await r.json();
    if (!r.ok) throw new Error(e.error || 'No encontrada');
    detailEntry = e;
    renderDetail(e);
    $('modal-detail').classList.remove('hidden');
  } catch (err) { toast(err.message, 'err'); }
}

function renderDetail(e) {
  const factores = e.factores ? e.factores.split(',').filter(Boolean) : [];
  const field = (label, value) => value
    ? `<div class="detail-field"><span class="dl">${label}</span><span class="dv">${esc(value)}</span></div>` : '';
  $('detail-body').innerHTML = `
    <div class="detail-top">
      <span class="nivel-badge nivel-${esc(e.nivel)}">${esc(e.nivel)}</span>
      <span class="cell-fecha">${esc(e.fecha)}</span>
      ${e.categoria ? `<span class="cat-tag">${esc(e.categoria)}</span>` : ''}
      ${e.lugar ? `<span class="cell-muted">· ${esc(e.lugar)}</span>` : ''}
    </div>
    <div class="detail-field"><span class="dl">Hecho</span><span class="dv">${esc(e.hecho)}</span></div>
    ${field('Cómo me di cuenta', e.como)}
    ${factores.length ? `<div class="detail-field"><span class="dl">Factores del momento</span><div class="detail-factores">${factores.map(f => `<span class="chip active">${esc(f)}</span>`).join('')}</div></div>` : ''}
    ${e.notado_otros ? `<div class="detail-field"><span class="dl">Lo notó otra persona</span><span class="dv">Sí${e.notado_quien ? ' — ' + esc(e.notado_quien) : ''}</span></div>` : ''}
    ${field('Comentario', e.comentario)}
    <div class="detail-field"><span class="dl">Registrado</span><span class="dv cell-muted">${esc((e.created_at || '').replace('T', ' ').slice(0, 16))}</span></div>
  `;
  const idx = currentIds.indexOf(e.id);
  $('btn-prev').disabled = idx <= 0;
  $('btn-next').disabled = idx < 0 || idx >= currentIds.length - 1;
  $('btn-prev').onclick = () => { if (idx > 0) openDetail(currentIds[idx - 1]); };
  $('btn-next').onclick = () => { if (idx < currentIds.length - 1) openDetail(currentIds[idx + 1]); };
  $('btn-edit').onclick = () => openForm(detailEntry);
  $('btn-delete').onclick = () => doDelete(e.id);
}

async function doDelete(id) {
  if (!confirm('¿Eliminar esta entrada? No se puede deshacer.')) return;
  try {
    const r = await fetch(`${API}/entries/${id}`, { method: 'DELETE' });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Error');
    $('modal-detail').classList.add('hidden');
    toast('Entrada eliminada.', 'ok');
    loadList(); loadStats();
  } catch (err) { toast(err.message, 'err'); }
}

// ─── Patterns panel ─────────────────────────────────────────────────────────────
const MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

async function togglePatterns() {
  const panel = $('patterns-panel');
  if (!panel.classList.contains('hidden')) { panel.classList.add('hidden'); return; }
  panel.classList.remove('hidden');
  try {
    const r = await fetch(`${API}/insights`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || 'Error');
    renderInsights(d);
  } catch (err) {
    toast(err.message, 'err');
  }
}

// Render a labelled horizontal bar chart into a container.
// data: [{label, value}]; widths are relative to the max value.
function renderBars(container, data) {
  if (!data.length) { container.innerHTML = '<p class="bars-empty">Sin datos.</p>'; return; }
  const max = Math.max(...data.map(d => d.value), 1);
  container.innerHTML = data.map(d => `
    <div class="bar-row">
      <span class="bar-label" title="${esc(d.label)}">${esc(d.label)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${Math.round(d.value / max * 100)}%"></span></span>
      <span class="bar-val">${d.value}</span>
    </div>`).join('');
}

function renderInsights(d) {
  const grid = $('patterns-grid');
  const empty = $('patterns-empty');
  if (!d.total) { grid.classList.add('hidden'); empty.classList.remove('hidden'); return; }
  grid.classList.remove('hidden'); empty.classList.add('hidden');

  // 1) Registros por año.
  renderBars($('chart-year'), d.byYear.map(r => ({ label: r.year, value: r.n })));
  // 2) Tipo de lapsus (categoría), ya viene ordenado por frecuencia desc.
  renderBars($('chart-categoria'), d.byCategoria.map(r => ({ label: r.categoria, value: r.n })));
  // 3a) Concentración por lugar (top 8 para no saturar).
  renderBars($('chart-lugar'), d.byLugar.slice(0, 8).map(r => ({ label: r.lugar, value: r.n })));
  // 3b) Concentración por mes (nombre de mes).
  renderBars($('chart-month'), d.byMonth.map(r => ({ label: MESES[r.month] || r.month, value: r.n })));
}

// ─── Export ─────────────────────────────────────────────────────────────────────
async function doExport() {
  const btn = $('btn-export'); btn.disabled = true;
  toast('Exportando a Dropbox…');
  try {
    const r = await fetch(`${API}/export/csv`);
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Error');
    toast(data.message || 'Exportado.', 'ok');
  } catch (err) {
    toast(`Error al exportar: ${err.message}`, 'err');
  } finally {
    btn.disabled = false;
  }
}

// ─── Printable report / PDF ──────────────────────────────────────────────────────
// Opens a self-contained printable document in a new window (the browser's
// "Save as PDF" turns it into a PDF). Respects the filters currently applied to
// the list, and builds the whole summary client-side from the returned rows so
// it always matches exactly what was filtered.
const NIVEL_COLOR = { Bajo: '#27AE60', Medio: '#C99A00', Alto: '#C0392B' };

// Human-readable description of the active filters, for the report header.
function describeFilters() {
  const f = state.filters;
  const parts = [];
  if (state.search) parts.push(`Búsqueda: “${state.search}”`);
  if (f.nivel.length) parts.push(`Importancia: ${f.nivel.join(', ')}`);
  if (f.categoria.length) parts.push(`Categoría: ${f.categoria.join(', ')}`);
  if (f.factores.length) parts.push(`Factores: ${f.factores.join(', ')}`);
  if (f.from || f.to) parts.push(`Fechas: ${f.from || '…'} – ${f.to || '…'}`);
  if (f.notado) parts.push('Solo los que notó otra persona');
  return parts;
}

// Tally a list of labels into a [{label, value}] array sorted by value desc.
function tally(labels) {
  const m = new Map();
  for (const l of labels) m.set(l, (m.get(l) || 0) + 1);
  return [...m.entries()].map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
}

// Simple inline-styled horizontal bars for the printed document.
function reportBars(data) {
  if (!data.length) return '<p style="color:#4F6B5C">Sin datos.</p>';
  const max = Math.max(...data.map(d => d.value), 1);
  return `<div class="r-bars">${data.map(d => `
    <div class="r-bar">
      <span class="r-bar-label">${esc(d.label)}</span>
      <span class="r-bar-track"><span class="r-bar-fill" style="width:${Math.round(d.value / max * 100)}%"></span></span>
      <span class="r-bar-val">${d.value}</span>
    </div>`).join('')}</div>`;
}

function reportEntryHtml(e) {
  const factores = e.factores ? e.factores.split(',').filter(Boolean) : [];
  const block = (label, value) => value
    ? `<div class="r-field"><span class="r-dl">${label}</span><span class="r-dv">${esc(value)}</span></div>` : '';
  const color = NIVEL_COLOR[e.nivel] || '#4F6B5C';
  return `<article class="r-entry">
    <div class="r-entry-head">
      <span class="r-fecha">${esc(e.fecha)}</span>
      <span class="r-nivel" style="background:${color}">${esc(e.nivel)}</span>
      ${e.categoria ? `<span class="r-cat">${esc(e.categoria)}</span>` : ''}
      ${e.lugar ? `<span class="r-lugar">· ${esc(e.lugar)}</span>` : ''}
    </div>
    <div class="r-field"><span class="r-dl">Hecho</span><span class="r-dv">${esc(e.hecho)}</span></div>
    ${block('Cómo me di cuenta', e.como)}
    ${factores.length ? `<div class="r-field"><span class="r-dl">Factores del momento</span><span class="r-dv">${factores.map(esc).join(' · ')}</span></div>` : ''}
    ${e.notado_otros ? `<div class="r-field"><span class="r-dl">Lo notó otra persona</span><span class="r-dv">Sí${e.notado_quien ? ' — ' + esc(e.notado_quien) : ''}</span></div>` : ''}
    ${block('Comentario', e.comentario)}
    <div class="r-reg">Registrado: ${esc((e.created_at || '').replace('T', ' ').slice(0, 16))}</div>
  </article>`;
}

function buildReportHtml(rows) {
  const total = rows.length;
  const byNivel = META.niveles.map(n => ({ label: n, value: rows.filter(r => r.nivel === n).length }));
  // rows arrive ordered by fecha DESC → first is most recent, last is oldest.
  const rango = total ? `${rows[total - 1].fecha} – ${rows[0].fecha}` : '—';

  const byYear = tally(rows.map(r => r.fecha.slice(0, 4))).sort((a, b) => a.label.localeCompare(b.label));
  const byCategoria = tally(rows.map(r => (r.categoria || '').trim() || 'Sin categoría'));
  const byLugar = tally(rows.map(r => (r.lugar || '').trim() || 'Sin lugar')).slice(0, 10);
  const byMonth = tally(rows.map(r => MESES[parseInt(r.fecha.slice(5, 7), 10)] || r.fecha.slice(5, 7)));

  const filtros = describeFilters();
  const generado = new Date().toLocaleDateString('es-ES', { day: '2-digit', month: 'long', year: 'numeric' });
  const backUrl = location.href;   // para regresar a la app conservando los filtros

  const card = (title, body) => `<section class="r-card"><h3>${title}</h3>${body}</section>`;

  return `<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8" />
<title>Bitácora — Informe (${generado})</title>
<style>
  * { box-sizing: border-box; }
  @page { margin: 18mm 16mm; }
  body { font-family: Georgia, 'Times New Roman', serif; color: #14241B; font-size: 12px; line-height: 1.55; margin: 0; }
  h1 { font-size: 22px; margin: 0; color: #157A4B; }
  h2 { font-size: 14px; margin: 22px 0 8px; color: #157A4B; border-bottom: 1.5px solid #C9E2D2; padding-bottom: 3px; }
  h3 { font-size: 12px; margin: 0 0 6px; color: #14241B; }
  .r-head { border-bottom: 2px solid #1F9D62; padding-bottom: 12px; margin-bottom: 6px; }
  .r-sub { color: #4F6B5C; font-size: 11px; margin-top: 2px; }
  .r-meta { color: #4F6B5C; font-size: 11px; margin-top: 8px; }
  .r-filtros { background: #EEF6F0; border: 1px solid #C9E2D2; border-radius: 6px; padding: 8px 10px; margin-top: 10px; font-size: 11px; }
  .r-filtros b { color: #157A4B; }
  .r-summary { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0 4px; }
  .r-stat { border: 1px solid #C9E2D2; border-radius: 6px; padding: 8px 14px; min-width: 90px; }
  .r-stat .n { font-size: 20px; font-weight: 700; }
  .r-stat .l { font-size: 10px; color: #4F6B5C; text-transform: uppercase; letter-spacing: .05em; }
  .r-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .r-card { border: 1px solid #C9E2D2; border-radius: 8px; padding: 10px 12px; break-inside: avoid; }
  .r-bars { display: flex; flex-direction: column; gap: 4px; }
  .r-bar { display: grid; grid-template-columns: 120px 1fr 28px; align-items: center; gap: 6px; font-size: 11px; }
  .r-bar-label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #4F6B5C; }
  .r-bar-track { background: #E0F0E6; border-radius: 4px; height: 11px; overflow: hidden; }
  .r-bar-fill { display: block; height: 100%; background: #1F9D62; }
  .r-bar-val { text-align: right; font-variant-numeric: tabular-nums; }
  .r-entry { border: 1px solid #C9E2D2; border-radius: 8px; padding: 10px 12px; margin-bottom: 9px; break-inside: avoid; }
  .r-entry-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 5px; }
  .r-fecha { font-weight: 700; }
  .r-nivel { color: #fff; font-size: 10px; font-weight: 700; padding: 1px 8px; border-radius: 10px; }
  .r-cat { background: #E0F0E6; color: #157A4B; font-size: 10px; padding: 1px 8px; border-radius: 10px; }
  .r-lugar { color: #4F6B5C; font-size: 11px; }
  .r-field { margin: 3px 0; }
  .r-dl { display: block; font-size: 9.5px; text-transform: uppercase; letter-spacing: .05em; color: #4F6B5C; }
  .r-dv { display: block; white-space: pre-wrap; }
  .r-reg { font-size: 9.5px; color: #9CB3A6; margin-top: 5px; }
  .r-foot { margin-top: 20px; padding-top: 8px; border-top: 1px solid #C9E2D2; font-size: 10px; color: #9CB3A6; text-align: center; }
  .r-toolbar { position: sticky; top: 0; z-index: 10; display: flex; gap: 8px; background: #157A4B; padding: 9px 14px; }
  .r-toolbar button { font-family: -apple-system, system-ui, sans-serif; font-size: 13px; font-weight: 700; cursor: pointer; border: 0; border-radius: 6px; padding: 8px 14px; background: #fff; color: #157A4B; }
  .r-toolbar button.ghost { background: rgba(255,255,255,.16); color: #fff; }
  @media screen { body { background: #fff; }
    .r-toolbar { margin-bottom: 16px; }
    .r-body { max-width: 880px; margin: 0 auto; padding: 0 20px 24px; } }
  @media print { .r-toolbar { display: none !important; } }
</style>
</head><body>
  <div class="r-toolbar" role="toolbar">
    <button type="button" onclick="volverApp()">← Volver a la Bitácora</button>
    <button type="button" class="ghost" onclick="window.print()">Imprimir / PDF</button>
  </div>
  <div class="r-body">
  <header class="r-head">
    <h1>Bitácora — Informe</h1>
    <div class="r-sub">Registro personal de hechos</div>
    <div class="r-meta">Generado el ${generado} · ${total} ${total === 1 ? 'entrada' : 'entradas'} · Periodo: ${rango}</div>
    ${filtros.length ? `<div class="r-filtros"><b>Informe filtrado.</b> ${filtros.map(esc).join(' · ')}</div>` : ''}
  </header>

  ${total ? `
  <h2>Resumen</h2>
  <div class="r-summary">
    <div class="r-stat"><div class="n">${total}</div><div class="l">Total</div></div>
    ${byNivel.map(n => `<div class="r-stat"><div class="n" style="color:${NIVEL_COLOR[n.label] || '#14241B'}">${n.value}</div><div class="l">${esc(n.label)}</div></div>`).join('')}
  </div>

  <h2>Patrones</h2>
  <div class="r-grid">
    ${card('Registros por año', reportBars(byYear))}
    ${card('Tipo de lapsus', reportBars(byCategoria))}
    ${card('Concentración por lugar', reportBars(byLugar))}
    ${card('Concentración por mes', reportBars(byMonth))}
  </div>

  <h2>Detalle cronológico</h2>
  ${rows.map(reportEntryHtml).join('')}
  ` : '<p style="margin-top:24px;color:#4F6B5C">No hay entradas que coincidan con los filtros actuales.</p>'}

  <div class="r-foot">Bitácora · Jokin's Tools — documento generado automáticamente</div>
  </div>

  <script>
    var APP_URL = ${JSON.stringify(backUrl)};
    function volverApp() {
      // Si el informe se abrió como ventana/pestaña emergente, ciérrala.
      window.close();
      // Si sigue abierto (móvil/PWA lo abre en la misma vista), vuelve a la app.
      setTimeout(function () { if (!window.closed) location.href = APP_URL; }, 150);
    }
    window.addEventListener('load', function () {
      var go = function () { try { window.focus(); window.print(); } catch (e) {} };
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { setTimeout(go, 150); });
      else setTimeout(go, 300);
    });
  </script>
</body></html>`;
}

async function doReport() {
  const btn = $('btn-report'); btn.disabled = true;
  toast('Generando informe…');
  // Open the window synchronously inside the click handler so it isn't blocked.
  const win = window.open('', '_blank');
  if (!win) { toast('Permite las ventanas emergentes para generar el informe.', 'err'); btn.disabled = false; return; }
  win.document.write('<!DOCTYPE html><title>Generando informe…</title><body style="font-family:Georgia,serif;color:#4F6B5C;padding:40px">Generando informe…</body>');
  try {
    const q = buildQuery();          // report endpoint applies only the filter params
    const r = await fetch(`${API}/report?${q}`);
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Error');
    win.document.open();
    win.document.write(buildReportHtml(data.rows || []));
    win.document.close();
    toast('Informe listo. Usa “Imprimir → Guardar como PDF”.', 'ok');
  } catch (err) {
    win.close();
    toast(`Error al generar el informe: ${err.message}`, 'err');
  } finally {
    btn.disabled = false;
  }
}
