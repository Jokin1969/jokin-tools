'use strict';

const API = '/galenica/api';
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const norm = s => String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const main = () => $('qt-main');

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json().catch(() => ({})) : {};
  if (!r.ok) throw new Error(data.error || `Error ${r.status}`);
  return data;
}
function jbody(obj) { return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) }; }
function stamp() { const d = new Date(); const p = n => String(n).padStart(2, '0'); return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`; }

let toastTimer = null;
function toast(msg, kind) {
  const t = $('toast'); t.textContent = msg; t.className = 'qt-toast' + (kind ? ' ' + kind : ''); t.hidden = false;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}
function confirmBox(title, body, okLabel) {
  return new Promise(resolve => {
    $('confirm-title').textContent = title; $('confirm-body').textContent = body; $('confirm-yes').textContent = okLabel || 'Aceptar';
    const m = $('confirm-modal'); m.hidden = false;
    const done = v => { m.hidden = true; $('confirm-yes').onclick = null; $('confirm-no').onclick = null; resolve(v); };
    $('confirm-yes').onclick = () => done(true); $('confirm-no').onclick = () => done(false);
  });
}
function openModal(html, opts) {
  const box = $('tool-modal-box'); box.innerHTML = html;
  box.classList.toggle('qt-modal-wide', !!(opts && opts.wide));
  $('tool-modal').hidden = false;
  box.querySelectorAll('[data-close]').forEach(b => b.onclick = closeModal);
}
function closeModal() { $('tool-modal').hidden = true; const box = $('tool-modal-box'); box.innerHTML = ''; box.classList.remove('qt-modal-wide'); }

// Pill photo (curated, by CN) — same repository/URL as Pastillero and the rest
// of the suite. No generic-icon fallback here (unlike the other apps): the whole
// point of Galénica is the appearance, so a missing photo shows as an honest
// empty slot with a hint, not a colour standing in for it.
function pillPhotoHtml(cn, cls) {
  return `<div class="${cls}" data-photobox="${esc(cn || '')}">${cn ? `<img src="/pastillero/assets/pill/${esc(cn)}.png" alt="" onerror="this.closest('[data-photobox]').innerHTML='<span style=&quot;color:var(--muted);font-size:.72rem;text-align:center;padding:6px&quot;>Sin foto</span>'">` : '<span style="color:var(--muted);font-size:.72rem">Sin CN</span>'}</div>`;
}
function eanSvg(ean) {
  const s = String(ean || '').replace(/\D/g, '');
  if (s.length < 12) return '';
  try {
    const svg = bwipjs.toSVG({ bcid: 'ean13', text: s, includetext: true, textxalign: 'center', height: 16, paddingwidth: 2, paddingheight: 2 });
    return svg.replace(/<svg /, '<svg shape-rendering="crispEdges" ');
  } catch { return ''; }
}

const S = {
  meds: [], meta: { formas: [], colors: [] },
  query: '', andor: 'AND', listMode: 'cards',
  formaFilter: null, colorFilter: null,
  selected: new Set(), hidden: new Set(), selectedOnly: false,
};

(async function boot() {
  try {
    const [{ items }, meta] = await Promise.all([api('/meds'), api('/meta')]);
    S.meds = items; S.meta = meta;
  } catch (e) { toast(e.message, 'err'); }
  viewList();
  $('help-btn').onclick = viewHelp;
})();
async function reload() {
  const [{ items }, meta] = await Promise.all([api('/meds'), api('/meta')]);
  S.meds = items; S.meta = meta;
}

// ── List ──────────────────────────────────────────────────────────────────────
function viewList() {
  main().innerHTML = `
     <div class="qt-actions-bar">
       <button class="qt-action" id="a-add"><span class="em">➕</span><span class="lbl">Añadir medicamento<small>por Código Nacional</small></span></button>
       <button class="qt-action" id="a-import"><span class="em">📥</span><span class="lbl">Importar<small>lote por CN, Excel/CSV</small></span></button>
       <button class="qt-action" id="a-export"><span class="em">📊</span><span class="lbl">Exportar Excel<small>elige columnas</small></span></button>
     </div>
     <div class="qt-search-wrap">
       <div class="qt-search"><span class="ico">🔎</span><input id="q" placeholder="Buscar por nombre, principio activo, forma, color…" autocomplete="off" value="${esc(S.query)}"></div>
       <div class="qt-andor" id="andor" title="AND = todas las palabras · OR = cualquier palabra">
         <button data-v="AND" class="${S.andor === 'AND' ? 'sel' : ''}">AND</button>
         <button data-v="OR" class="${S.andor === 'OR' ? 'sel' : ''}">OR</button>
       </div>
     </div>
     ${chipBarHtml()}
     <div class="qt-toolbar">
       <span class="qt-count" id="list-count"></span>
       <div class="qt-seg" id="list-mode">
         <button data-m="cards" class="${S.listMode === 'cards' ? 'sel' : ''}">▦ Tarjetas</button>
         <button data-m="table" class="${S.listMode !== 'cards' ? 'sel' : ''}">▤ Listado</button>
       </div>
       <button class="qt-toggle ${S.selectedOnly ? 'on' : ''}" id="tg-selected">✔ Solo seleccionados</button>
       <button class="qt-toggle" id="clear-sel">✕ Quitar selección</button>
     </div>
     <div id="hidden-note"></div>
     <div id="list-body"></div>`;
  const q = $('q');
  q.addEventListener('input', () => { S.query = q.value; renderRows(); });
  $('andor').querySelectorAll('button').forEach(b => b.onclick = () => { S.andor = b.dataset.v; $('andor').querySelectorAll('button').forEach(x => x.classList.toggle('sel', x === b)); renderRows(); });
  $('list-mode').querySelectorAll('button').forEach(b => b.onclick = () => { S.listMode = b.dataset.m; viewList(); });
  $('tg-selected').onclick = () => { S.selectedOnly = !S.selectedOnly; viewList(); };
  $('clear-sel').onclick = () => { S.selected.clear(); renderRows(); };
  $('a-add').onclick = toolAdd;
  $('a-import').onclick = toolImport;
  $('a-export').onclick = toolExport;
  wireChipBar();
  renderRows();
}
function chipBarHtml() {
  if (!S.meta.formas.length && !S.meta.colors.length) return '';
  const chip = (val, active, key) => `<button type="button" class="gl-chip ${active ? 'sel' : ''}" data-chip="${key}" data-val="${esc(val)}">${esc(val)}</button>`;
  const formas = S.meta.formas.length ? `<div class="gl-chipgroup"><span class="gl-chipgroup-lbl">Forma</span>${S.meta.formas.map(f => chip(f, S.formaFilter === f, 'forma')).join('')}</div>` : '';
  const colors = S.meta.colors.length ? `<div class="gl-chipgroup"><span class="gl-chipgroup-lbl">Color</span>${S.meta.colors.map(c => chip(c, S.colorFilter === c, 'color')).join('')}</div>` : '';
  return `<div class="gl-chipbar">${formas}${colors}</div>`;
}
function wireChipBar() {
  main().querySelectorAll('[data-chip]').forEach(b => b.onclick = () => {
    const key = b.dataset.chip, val = b.dataset.val;
    if (key === 'forma') S.formaFilter = S.formaFilter === val ? null : val;
    else S.colorFilter = S.colorFilter === val ? null : val;
    viewList();
  });
}
function filteredMeds() {
  let rows = S.meds.filter(m => !S.hidden.has(m.id));
  if (S.selectedOnly) rows = rows.filter(m => S.selected.has(m.id));
  if (S.formaFilter) rows = rows.filter(m => m.forma === S.formaFilter);
  if (S.colorFilter) rows = rows.filter(m => m.color === S.colorFilter);
  const tokens = norm(S.query).split(/\s+/).filter(Boolean);
  if (tokens.length) {
    rows = rows.filter(m => {
      const hay = norm([m.nombre, m.pactivos, m.forma, m.color, m.cn, m.labtitular].join(' '));
      return S.andor === 'OR' ? tokens.some(t => hay.includes(t)) : tokens.every(t => hay.includes(t));
    });
  }
  return rows.slice().sort((a, b) => norm(a.nombre || a.cn).localeCompare(norm(b.nombre || b.cn), 'es', { numeric: true }));
}
function tagsHtml(m) {
  return `${m.forma ? `<span class="gl-tag">${esc(m.forma)}</span>` : ''}${m.color ? `<span class="gl-tag color">${esc(m.color)}</span>` : ''}`;
}
function medCardHtml(m) {
  const sel = S.selected.has(m.id);
  return `<div class="gl-card ${sel ? 'is-selected' : ''}" data-id="${m.id}">
    <input type="checkbox" class="qt-check gl-card-check" data-sel="${m.id}" ${sel ? 'checked' : ''}>
    ${pillPhotoHtml(m.cn, 'gl-card-photo')}
    <div class="gl-card-name" data-open="${m.id}">${esc(m.nombre || 'Sin nombre')}</div>
    <div class="gl-card-meta">CN ${esc(m.cn)}${m.pactivos ? ' · ' + esc(m.pactivos) : ''}</div>
    <div class="gl-card-tags">${tagsHtml(m)}</div>
  </div>`;
}
function medRowHtml(m) {
  const sel = S.selected.has(m.id);
  return `<tr class="${sel ? 'is-selected' : ''}" data-id="${m.id}">
    <td><input type="checkbox" class="qt-check" data-sel="${m.id}" ${sel ? 'checked' : ''}></td>
    <td class="gl-td-photo">${pillPhotoHtml(m.cn, 'gl-thumb')}</td>
    <td><span class="qt-cell-name" data-open="${m.id}">${esc(m.nombre || 'Sin nombre')}</span><br><span class="gl-cn-mono">CN ${esc(m.cn)}</span></td>
    <td>${esc(m.pactivos || '—')}</td>
    <td>${esc(m.forma || '—')}</td>
    <td>${esc(m.color || '—')}</td>
    <td class="qt-cell-actions">
      <button class="qt-iconbtn" data-open="${m.id}" title="Ver ficha">👁</button>
      <button class="qt-iconbtn" data-hide="${m.id}" title="Ocultar temporalmente">🚫</button>
      <button class="qt-iconbtn danger" data-del="${m.id}" title="Eliminar">🗑</button>
    </td>
  </tr>`;
}
function renderRows() {
  const rows = filteredMeds();
  $('list-count').textContent = `${rows.length} de ${S.meds.length}` +
    (S.selected.size ? ` · ${S.selected.size} seleccionado(s)` : '') + (S.hidden.size ? ` · ${S.hidden.size} oculto(s)` : '');
  $('hidden-note').innerHTML = S.hidden.size
    ? `<div class="qt-hidden-note">👁 Hay <strong>${S.hidden.size}</strong> medicamento(s) oculto(s) temporalmente. <a id="unhide">Mostrar todos</a></div>` : '';
  if (S.hidden.size) $('unhide').onclick = () => { S.hidden.clear(); renderRows(); };
  const body = $('list-body');
  if (!rows.length) { body.innerHTML = '<div class="qt-empty">No hay medicamentos que coincidan. Prueba a «➕ Añadir medicamento».</div>'; return; }
  if (S.listMode === 'cards') {
    body.innerHTML = `<div class="gl-cards">${rows.map(medCardHtml).join('')}</div>`;
  } else {
    body.innerHTML = `<div class="qt-table-wrap"><table class="qt-table"><thead><tr>
      <th class="no-sort"></th><th class="no-sort">Foto</th><th class="no-sort">Medicamento</th><th class="no-sort">Principio activo</th><th class="no-sort">Forma</th><th class="no-sort">Color</th><th class="no-sort"></th>
    </tr></thead><tbody>${rows.map(medRowHtml).join('')}</tbody></table></div>`;
  }
  body.querySelectorAll('[data-sel]').forEach(cb => cb.addEventListener('change', () => {
    const id = Number(cb.dataset.sel); cb.checked ? S.selected.add(id) : S.selected.delete(id);
    renderRows();
  }));
  body.querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', () => openDetail(Number(el.dataset.open))));
  body.querySelectorAll('[data-hide]').forEach(b => b.addEventListener('click', () => { S.hidden.add(Number(b.dataset.hide)); renderRows(); }));
  body.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', () => removeMed(Number(b.dataset.del))));
}
async function removeMed(id) {
  const m = S.meds.find(x => x.id === id); if (!m) return;
  if (!(await confirmBox('Eliminar de Galénica', `¿Eliminar «${m.nombre || m.cn}» del catálogo? Esto no afecta al inventario de Data Matrix ni a ningún plan.`, 'Eliminar'))) return;
  try { await api('/meds/' + id, { method: 'DELETE' }); S.meds = S.meds.filter(x => x.id !== id); S.selected.delete(id); renderRows(); toast('Eliminado', 'ok'); }
  catch (e) { toast(e.message, 'err'); }
}

// ── Add ───────────────────────────────────────────────────────────────────────
function toolAdd() {
  openModal(`<div class="qt-modal-h"><h3>➕ Añadir medicamento</h3><button class="qt-x" data-close>×</button></div>
    <p style="color:var(--muted);font-size:.88rem;margin:0 0 10px">Escribe el <b>Código Nacional</b>: se consulta CIMA (AEMPS) para traer nombre, principio activo, forma farmacéutica y laboratorio. El <b>color</b> no lo da CIMA — escríbelo tú (o añádelo luego).</p>
    <div class="qt-field"><label>Código Nacional</label><input class="qt-input" id="ad-cn" inputmode="numeric" placeholder="702983" maxlength="8" autofocus></div>
    <div class="qt-field"><label>Color (opcional)</label><input class="qt-input" id="ad-color" placeholder="blanco, blanco y rosa, ámbar…"></div>
    <div class="qt-modal-actions"><button class="qt-btn qt-btn-ghost" data-close>Cancelar</button><button class="qt-btn qt-btn-primary" id="ad-go">🔎 Buscar en CIMA y añadir</button></div>`);
  const go = async () => {
    const cn = $('ad-cn').value.replace(/\D/g, '');
    if (!/^\d{4,8}$/.test(cn)) { toast('Código Nacional no válido.', 'err'); return; }
    const btn = $('ad-go'); btn.disabled = true; const prev = btn.textContent; btn.textContent = 'Consultando…';
    try {
      const r = await api('/meds', jbody({ cn, color: $('ad-color').value }));
      await reload(); closeModal(); viewList();
      toast(r.cima_found ? '✓ Añadido con datos de CIMA' : '✓ Añadido (CIMA no encontró ese CN; puedes editarlo a mano)', r.cima_found ? 'ok' : undefined);
    } catch (e) { toast(e.message, 'err'); btn.disabled = false; btn.textContent = prev; }
  };
  $('ad-go').onclick = go;
  $('ad-cn').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
}

// ── Detail / edit ─────────────────────────────────────────────────────────────
function openDetail(id) {
  const m = S.meds.find(x => x.id === id); if (!m) return;
  const ean = eanSvg(m.barcode);
  openModal(`<div class="qt-modal-h"><h3>${esc(m.nombre || 'Medicamento')}</h3><button class="qt-x" data-close>×</button></div>
    <div class="gl-detail">
      <div>
        ${pillPhotoHtml(m.cn, 'gl-detail-photo')}
        <div class="gl-detail-codes">
          <span>CN ${esc(m.cn)}</span>
          <span>GTIN ${esc(m.gtin || '—')}</span>
          <span>CB ${esc(m.barcode || '—')}</span>
        </div>
        ${ean ? `<div class="gl-detail-barcode">${ean}</div>` : ''}
      </div>
      <div>
        <div class="qt-field"><label>Nombre</label><input class="qt-input" id="dt-nombre" value="${esc(m.nombre || '')}"></div>
        <div class="qt-field"><label>Principio activo</label><input class="qt-input" id="dt-pactivos" value="${esc(m.pactivos || '')}"></div>
        <div class="qt-field"><label>Forma farmacéutica</label><input class="qt-input" id="dt-forma" value="${esc(m.forma || '')}"></div>
        <div class="qt-field"><label>Color</label><input class="qt-input" id="dt-color" value="${esc(m.color || '')}" placeholder="blanco, blanco y rosa…"></div>
        <div class="qt-field"><label>Laboratorio</label><input class="qt-input" id="dt-lab" value="${esc(m.labtitular || '')}"></div>
        <div class="qt-field"><label>Notas</label><input class="qt-input" id="dt-notes" value="${esc(m.notes || '')}"></div>
      </div>
    </div>
    <div class="qt-modal-actions">
      <button class="qt-btn qt-btn-ghost" id="dt-cima" title="Volver a consultar CIMA (no toca el color ni las notas)">🔄 Actualizar desde CIMA</button>
      <button class="qt-btn qt-btn-ghost" data-close>Cerrar</button>
      <button class="qt-btn qt-btn-primary" id="dt-save">Guardar</button>
    </div>`, { wide: true });
  $('dt-save').onclick = async () => {
    try {
      const { item } = await api('/meds/' + m.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        nombre: $('dt-nombre').value, pactivos: $('dt-pactivos').value, forma: $('dt-forma').value, color: $('dt-color').value, labtitular: $('dt-lab').value, notes: $('dt-notes').value,
      }) });
      const i = S.meds.findIndex(x => x.id === m.id); if (i >= 0) S.meds[i] = item;
      await reload(); closeModal(); viewList(); toast('Guardado', 'ok');
    } catch (e) { toast(e.message, 'err'); }
  };
  $('dt-cima').onclick = async () => {
    const btn = $('dt-cima'); btn.disabled = true; const prev = btn.textContent; btn.textContent = 'Consultando…';
    try {
      const r = await api('/meds/' + m.id + '/cima', jbody({}));
      const i = S.meds.findIndex(x => x.id === m.id); if (i >= 0) S.meds[i] = r.item;
      closeModal(); openDetail(m.id);
      toast(r.cima_found ? '✓ Actualizado desde CIMA' : 'CIMA no tiene datos para este CN (o no está disponible ahora)', r.cima_found ? 'ok' : 'err');
    } catch (e) { toast(e.message, 'err'); btn.disabled = false; btn.textContent = prev; }
  };
}

// ── Bulk import ───────────────────────────────────────────────────────────────
function toolImport() {
  openModal(`<div class="qt-modal-h"><h3>📥 Importar en lote</h3><button class="qt-x" data-close>×</button></div>
    <div class="qt-tool-opt">
      <h4>1 · Plantilla</h4>
      <p>Un Excel con <b>Código Nacional</b> y, opcionalmente, <b>Color</b> (el resto lo trae CIMA). Reimportar un CN ya existente lo actualiza, no lo duplica.</p>
      <button class="qt-btn qt-btn-primary" id="im-tpl">⬇ Descargar plantilla .xlsx</button>
    </div>
    <div class="qt-tool-opt">
      <h4>2 · Importar</h4>
      <div class="qt-dropfile" id="im-drop">📥 Haz clic o arrastra aquí tu Excel (.xlsx / .csv)</div>
      <input type="file" id="im-file" accept=".xlsx,.xls,.csv" hidden>
      <div class="qt-import-report" id="im-report"></div>
    </div>`);
  $('im-tpl').onclick = () => {
    const aoa = [['Código Nacional', 'Color'], ['702983', 'blanco'], ['699154', '']];
    const ws = XLSX.utils.aoa_to_sheet(aoa);
    ws['!cols'] = [{ wch: 16 }, { wch: 20 }];
    for (let r = 1; r <= 2; r++) { const cell = ws[XLSX.utils.encode_cell({ r, c: 0 })]; if (cell) { cell.t = 's'; cell.z = '@'; } }
    const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Galénica');
    XLSX.writeFile(wb, 'Plantilla_Galenica.xlsx');
  };
  const drop = $('im-drop'), file = $('im-file');
  drop.onclick = () => file.click();
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('drag'); };
  drop.ondragleave = () => drop.classList.remove('drag');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('drag'); if (e.dataTransfer.files[0]) importFile(e.dataTransfer.files[0]); };
  file.onchange = () => { if (file.files[0]) importFile(file.files[0]); };
}
function parseWorkbook(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = e => {
      try { const wb = XLSX.read(new Uint8Array(e.target.result), { type: 'array' }); const ws = wb.Sheets[wb.SheetNames[0]]; resolve(XLSX.utils.sheet_to_json(ws, { header: 1, raw: false, defval: '' })); }
      catch { reject(new Error('No se pudo leer el Excel.')); }
    };
    fr.onerror = () => reject(new Error('No se pudo leer el fichero.'));
    fr.readAsArrayBuffer(file);
  });
}
async function importFile(file) {
  const report = $('im-report');
  report.innerHTML = 'Leyendo…';
  try {
    const aoa = await parseWorkbook(file);
    if (!aoa.length) throw new Error('El Excel está vacío.');
    const header = aoa[0].map(h => norm(String(h)));
    const find = (...names) => header.findIndex(h => names.some(n => h.includes(n)));
    const ci = { cn: find('codigo nacional', 'cn'), color: find('color') };
    if (ci.cn < 0) throw new Error('Falta la columna «Código Nacional».');
    const rows = [];
    for (let i = 1; i < aoa.length; i++) {
      const r = aoa[i];
      const cn = String(r[ci.cn] || '').replace(/\D/g, '');
      if (!cn) continue;
      rows.push({ cn, color: ci.color >= 0 ? String(r[ci.color] || '').trim() : undefined });
    }
    if (!rows.length) throw new Error('No hay filas con Código Nacional.');
    report.innerHTML = `Consultando CIMA para ${rows.length} medicamento(s)… puede tardar un poco.`;
    const res = await api('/import', jbody({ rows }));
    await reload(); viewList();
    let html = `<div class="ok">✓ ${res.created} creado(s), ${res.updated} actualizado(s)${res.missing.length ? `, ${res.missing.length} sin datos de CIMA` : ''}.</div>`;
    if (res.missing.length) html += `<div class="qt-import-errs"><div class="err">Sin datos de CIMA (añadidos solo con su CN): ${esc(res.missing.slice(0, 40).join(', '))}${res.missing.length > 40 ? `… (+${res.missing.length - 40})` : ''}</div></div>`;
    html += `<div style="margin-top:12px"><button class="qt-btn qt-btn-primary" id="im-done">Ver catálogo</button></div>`;
    report.innerHTML = html;
    $('im-done').onclick = closeModal;
    toast(`${res.created + res.updated} procesado(s)`, 'ok');
  } catch (e) { report.innerHTML = `<div class="err">✕ ${esc(e.message)}</div>`; }
}

// ── Export ────────────────────────────────────────────────────────────────────
function toolExport() {
  const rows = filteredMeds();
  const aoa = [['Código Nacional', 'GTIN', 'Código de barras', 'Nombre', 'Principio activo', 'Forma farmacéutica', 'Color', 'Laboratorio']];
  rows.forEach(m => aoa.push([m.cn, m.gtin || '', m.barcode || '', m.nombre || '', m.pactivos || '', m.forma || '', m.color || '', m.labtitular || '']));
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  ws['!cols'] = [{ wch: 14 }, { wch: 16 }, { wch: 16 }, { wch: 32 }, { wch: 24 }, { wch: 18 }, { wch: 14 }, { wch: 20 }];
  for (let r = 1; r <= rows.length; r++) for (const c of [0, 1, 2]) { const cell = ws[XLSX.utils.encode_cell({ r, c })]; if (cell) { cell.t = 's'; cell.z = '@'; } }
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Galénica');
  XLSX.writeFile(wb, `Galenica_${stamp()}.xlsx`);
  toast(`Excel generado · ${rows.length} medicamento(s)`, 'ok');
}

// ── Manual / Ayuda ─────────────────────────────────────────────────────────────
function viewHelp() {
  const SECS = [
    { id: 'inicio', icon: '🚀', title: 'Qué es', html: `<p>Un <b>catálogo de medicamentos</b> pensado para reconocer una pastilla o un envase de un vistazo: nombre, principio activo, forma farmacéutica y color, junto a su foto. No es un inventario de cajas (eso es <b>Data Matrix</b>) ni el plan de una persona (eso es <b>Asignación</b>): es información general del medicamento.</p>` },
    { id: 'anadir', icon: '➕', title: 'Añadir un medicamento', html: `<p>Con <span class="qt-chip-inline">➕ Añadir medicamento</span> escribes su <b>Código Nacional</b>: la app consulta <b>CIMA (AEMPS)</b> para traer el nombre, el principio activo, la forma farmacéutica y el laboratorio.</p>
      <div class="qt-note warn"><b>El color no lo da CIMA.</b> Es el único campo que se escribe siempre a mano — tú lo rellenas al añadir el medicamento o después, desde su ficha.</div>` },
    { id: 'foto', icon: '📷', title: 'La foto de la pastilla', html: `<p>Las fotos son el mismo repositorio que usan <b>Pastillero</b> y el resto de la suite: un PNG por Código Nacional. Si un medicamento no tiene foto todavía, se ve un hueco vacío con «Sin foto» — pídesela a quien gestione ese repositorio en GitHub.</p>` },
    { id: 'buscar', icon: '🔎', title: 'Buscar y filtrar', html: `<p>El buscador mira <b>nombre, principio activo, forma, color, Código Nacional y laboratorio</b> a la vez. <b>AND</b> exige todas las palabras que escribas; <b>OR</b>, cualquiera. Ejemplo: <code>comprimido blanco</code> con AND encuentra los comprimidos blancos.</p>
      <p>Debajo del buscador hay <b>chips de forma y color</b> — pulsa uno para filtrar por ese valor exacto (se combinan con la búsqueda de texto).</p>` },
    { id: 'listado', icon: '📋', title: 'Tarjetas o listado, seleccionar y ocultar', html: `<p>El conmutador <span class="qt-chip-inline">▦ Tarjetas | ▤ Listado</span> cambia la vista — tarjetas es la que mejor luce las fotos. En ambas puedes <b>seleccionar</b> con la casilla, filtrar por <span class="qt-chip-inline">✔ Solo seleccionados</span> y <b>ocultar</b> temporalmente (🚫) los que no quieras ver ahora — no se recuerda al salir.</p>` },
    { id: 'import', icon: '📥', title: 'Importar en lote y exportar', html: `<p><span class="qt-chip-inline">📥 Importar</span> acepta un Excel con una columna de <b>Código Nacional</b> (y opcionalmente <b>Color</b>): consulta CIMA por cada uno y los añade o actualiza. <span class="qt-chip-inline">📊 Exportar Excel</span> descarga lo que ves filtrado en ese momento.</p>` },
    { id: 'cima', icon: '🔄', title: 'Actualizar desde CIMA', html: `<p>En la ficha de un medicamento, <span class="qt-chip-inline">🔄 Actualizar desde CIMA</span> vuelve a consultar AEMPS por si algo cambió (nombre, principio activo, forma, laboratorio). <b>Nunca toca el color ni las notas</b> — esos son siempre tuyos.</p>` },
  ];
  const nav = SECS.map(s => `<a data-go="help-${s.id}">${s.icon} ${s.title}</a>`).join('');
  const secs = SECS.map(s => `<section class="qt-help-sec" id="help-${s.id}"><h2><span class="em">${s.icon}</span>${s.title}</h2>${s.html}</section>`).join('');
  main().innerHTML = `<button class="qt-back" id="back">← Volver</button>
    <div class="qt-help-hero"><div class="qt-help-hero-txt"><h1>Manual · Galénica</h1><p>Cómo reconocer un medicamento de un vistazo.</p></div></div>
    <div class="qt-help-wrap"><nav class="qt-help-nav">${nav}</nav><div class="qt-help-content">${secs}</div></div>`;
  $('back').onclick = viewList;
  main().querySelectorAll('.qt-help-nav [data-go]').forEach(a => a.addEventListener('click', () => { const el = document.getElementById(a.dataset.go); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }));
  window.scrollTo({ top: 0 });
}
