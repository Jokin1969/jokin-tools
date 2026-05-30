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
  return `<tr data-id="${e.id}">
    <td class="cell-fecha">${esc(e.fecha)}</td>
    <td><span class="nivel-badge nivel-${esc(e.nivel)}">${esc(e.nivel)}</span></td>
    <td>${e.categoria ? `<span class="cat-tag">${esc(e.categoria)}</span>` : '<span class="cell-muted">—</span>'}</td>
    <td class="cell-hecho">${esc(hecho)}</td>
    <td class="cell-muted">${esc(e.lugar || '—')}</td>
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
