/* ─── Re-memory Frontend App ──────────────────────────────────────────────── */
'use strict';

const API = '/re-memory/api';

// ─── State ───────────────────────────────────────────────────────────────────
const state = {
  currentId: null,        // memory being edited
  currentTab: 'ficha',
  listSort: { col: 'created_at', order: 'desc' },
  listPage: 1,
  listTotal: 0,
  listLimit: 50,
  deleteTarget: null,
  existingImagePath: null,
  navList: [],            // all IDs in order for prev/next
  navIndex: -1           // current position in navList
};

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// ─── Toast ───────────────────────────────────────────────────────────────────
function toast(msg, type = 'info', duration = 3500) {
  const container = $('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  el.innerHTML = `<span>${icons[type] || ''}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add('removing');
    el.addEventListener('animationend', () => el.remove());
  }, duration);
}

// ─── Utilities ────────────────────────────────────────────────────────────────
function formatDate(isoStr) {
  if (!isoStr) return '—';
  return new Date(isoStr).toLocaleDateString('es-ES', {
    day: '2-digit', month: '2-digit', year: 'numeric'
  });
}

function formatDateTime(isoStr) {
  if (!isoStr) return '—';
  return new Date(isoStr).toLocaleString('es-ES', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

const FREQ_LABELS = {
  '1w': '1 semana', '2w': '2 semanas', '3w': '3 semanas',
  '1m': '1 mes', '2m': '2 meses', '3m': '3 meses',
  '6m': '6 meses', '1y': '1 año'
};

function getBadgeColor(n) {
  if (n <= 3)  return '#27AE60';
  if (n <= 5)  return '#F2C94C';
  if (n <= 8)  return '#F2994A';
  if (n <= 11) return '#EB5757';
  return '#C0392B';
}

// ─── Tab navigation ───────────────────────────────────────────────────────────
function switchTab(tab) {
  state.currentTab = tab;
  $$('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  $$('.view').forEach(v => v.classList.toggle('active', v.id === `view-${tab}`));
  if (tab === 'listado') loadList();
}

$$('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ─── Navigation list ──────────────────────────────────────────────────────────
async function refreshNavList() {
  try {
    const res = await fetch(`${API}/ids`);
    if (res.ok) state.navList = await res.json();
  } catch (_) { /* non-critical */ }
}

function updateNavButtons() {
  const idx = state.navList.indexOf(state.currentId);
  state.navIndex = idx;
  const btnPrev = $('btn-prev');
  const btnNext = $('btn-next');
  const navPos  = $('nav-pos');
  if (idx === -1 || state.navList.length === 0) {
    btnPrev.disabled = true;
    btnNext.disabled = true;
    navPos.textContent = '';
    return;
  }
  btnPrev.disabled = idx <= 0;
  btnNext.disabled = idx >= state.navList.length - 1;
  navPos.textContent = `${idx + 1} / ${state.navList.length}`;
}

async function navTo(id) {
  try {
    const res = await fetch(`${API}/memories/${id}`);
    if (!res.ok) throw new Error('No encontrado');
    const memory = await res.json();
    populateForm(memory);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
  }
}

$('btn-prev').addEventListener('click', () => {
  if (state.navIndex > 0) navTo(state.navList[state.navIndex - 1]);
});
$('btn-next').addEventListener('click', () => {
  if (state.navIndex < state.navList.length - 1) navTo(state.navList[state.navIndex + 1]);
});

// ─── Ficha: Form state management ────────────────────────────────────────────
function clearForm() {
  state.currentId = null;
  state.existingImagePath = null;
  $('field-id').value = '';
  $('field-id-display').value = '';
  $('field-created-at').value = '';
  $('field-times-recalled').value = '';
  $('field-description').value = '';
  $('field-frequency').value = '';
  $('field-topic').value = '';
  $('field-source-url').value = '';
  $('field-source-link').classList.add('hidden');
  $('field-active').checked = true;
  $('field-image').value = '';
  $('image-preview').src = '';
  $('image-preview-wrap').classList.add('hidden');
  $('image-field-container').classList.add('hidden');
  $('btn-show-image').textContent = '📷';
  $('next-send-wrap').style.display = 'none';
  $('btn-borrar').disabled = true;
  $('btn-reset-counter').disabled = true;
  $('btn-test-email').disabled = true;
  $('record-info').textContent = 'Nuevo registro';
  updateNavButtons();
}

function populateForm(memory) {
  state.currentId = memory.id;
  state.existingImagePath = memory.image_path || null;
  $('field-id').value = memory.id;
  $('field-id-display').value = `#${memory.id}`;
  $('field-created-at').value = formatDate(memory.created_at);
  $('field-times-recalled').value = memory.times_recalled ?? 0;
  $('field-description').value = memory.description || '';
  $('field-frequency').value = memory.frequency || '';
  $('field-topic').value = memory.topic || '';
  $('field-source-url').value = memory.source_url || '';
  $('field-active').checked = memory.active === 1 || memory.active === true;

  // Source link
  const sourceLink = $('field-source-link');
  if (memory.source_url) {
    sourceLink.href = memory.source_url;
    sourceLink.classList.remove('hidden');
  } else {
    sourceLink.classList.add('hidden');
  }

  // Image
  if (memory.image_path) {
    $('image-preview').src = `/uploads/${memory.image_path}`;
    $('image-preview-wrap').classList.remove('hidden');
    $('image-field-container').classList.remove('hidden');
  }

  // Next send
  if (memory.next_send_date) {
    $('field-next-send').value = formatDateTime(memory.next_send_date);
    $('next-send-wrap').style.display = '';
  }

  $('btn-borrar').disabled = false;
  $('btn-reset-counter').disabled = false;
  $('btn-test-email').disabled = false;
  $('record-info').textContent = `Registro #${memory.id}`;
  updateNavButtons();
}

// URL live preview
$('field-source-url').addEventListener('input', () => {
  const val = $('field-source-url').value.trim();
  const link = $('field-source-link');
  if (val) { link.href = val; link.classList.remove('hidden'); }
  else { link.classList.add('hidden'); }
});

// Image toggle
$('btn-show-image').addEventListener('click', () => {
  const container = $('image-field-container');
  container.classList.toggle('hidden');
  $('btn-show-image').textContent = container.classList.contains('hidden') ? '📷' : '✕';
});

// Image preview
$('field-image').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    $('image-preview').src = ev.target.result;
    $('image-preview-wrap').classList.remove('hidden');
  };
  reader.readAsDataURL(file);
});

// Remove image button
$('btn-remove-image').addEventListener('click', () => {
  $('field-image').value = '';
  $('image-preview').src = '';
  $('image-preview-wrap').classList.add('hidden');
  state.existingImagePath = null;
});

// ─── Nuevo ────────────────────────────────────────────────────────────────────
$('btn-nuevo').addEventListener('click', () => {
  clearForm();
  switchTab('ficha');
  $('field-description').focus();
});

// ─── Guardar ──────────────────────────────────────────────────────────────────
$('btn-guardar').addEventListener('click', async () => {
  const description = $('field-description').value.trim();
  const frequency   = $('field-frequency').value;
  const topic       = $('field-topic').value;
  const source_url  = $('field-source-url').value.trim();
  const active      = $('field-active').checked ? 1 : 0;

  if (!description) { toast('La descripción es obligatoria', 'error'); $('field-description').focus(); return; }
  if (!frequency)   { toast('Selecciona una frecuencia', 'error'); return; }
  if (!topic)       { toast('Selecciona un tema', 'error'); return; }

  const body = { description, frequency, topic, source_url: source_url || null, active };

  try {
    let memory;
    if (state.currentId) {
      const res = await fetch(`${API}/memories/${state.currentId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!res.ok) throw new Error((await res.json()).error);
      memory = await res.json();
      toast('Memoria actualizada', 'success');
    } else {
      const res = await fetch(`${API}/memories`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!res.ok) throw new Error((await res.json()).error);
      memory = await res.json();
      toast('Memoria creada', 'success');
    }

    // Upload image if selected
    const imageFile = $('field-image').files[0];
    if (imageFile) {
      const formData = new FormData();
      formData.append('image', imageFile);
      const imgRes = await fetch(`${API}/memories/${memory.id}/image`, {
        method: 'POST', body: formData
      });
      if (imgRes.ok) {
        const imgData = await imgRes.json();
        memory = imgData.memory;
        toast('Imagen subida', 'success');
      } else {
        toast('Error al subir imagen', 'error');
      }
    }

    populateForm(memory);
    await refreshNavList();
    updateNavButtons();
  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
  }
});

// ─── Borrar ───────────────────────────────────────────────────────────────────
$('btn-borrar').addEventListener('click', () => {
  if (!state.currentId) return;
  state.deleteTarget = state.currentId;
  $('modal-delete').classList.remove('hidden');
});

$('btn-cancel-delete').addEventListener('click', () => {
  $('modal-delete').classList.add('hidden');
  state.deleteTarget = null;
});

$('btn-confirm-delete').addEventListener('click', async () => {
  $('modal-delete').classList.add('hidden');
  if (!state.deleteTarget) return;
  try {
    const res = await fetch(`${API}/memories/${state.deleteTarget}`, { method: 'DELETE' });
    if (!res.ok) throw new Error((await res.json()).error);
    toast('Memoria eliminada', 'success');
    state.deleteTarget = null;
    clearForm();
    await refreshNavList();
    if (state.currentTab === 'listado') loadList();
  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
  }
});

// ─── Reset counter ────────────────────────────────────────────────────────────
$('btn-reset-counter').addEventListener('click', async () => {
  if (!state.currentId) return;
  if (!confirm('¿Reiniciar el contador a cero? Se borrarán todos los registros de envío de esta memoria.')) return;
  try {
    const res = await fetch(`${API}/memories/${state.currentId}/reset-counter`, { method: 'POST' });
    if (!res.ok) throw new Error((await res.json()).error);
    const memory = await res.json();
    $('field-times-recalled').value = memory.times_recalled;
    toast('Contador reiniciado a cero', 'success');
  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
  }
});

// ─── Test email ───────────────────────────────────────────────────────────────
$('btn-test-email').addEventListener('click', async () => {
  if (!state.currentId) return;
  const btn = $('btn-test-email');
  btn.disabled = true;
  btn.textContent = '✉ Enviando…';
  try {
    const res = await fetch(`${API}/test-email/${state.currentId}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    toast('Email de prueba enviado. Revisa tu bandeja de entrada.', 'success', 5000);
  } catch (err) {
    toast(`Error al enviar: ${err.message}`, 'error', 6000);
  } finally {
    btn.disabled = false;
    btn.textContent = '✉ Test email';
  }
});

// ─── Claude modal ─────────────────────────────────────────────────────────────
let claudeResult = null; // stores { description, url, imageUrl } from last call

function openClaudeModal(prefill) {
  claudeResult = null;
  $('claude-input').value = prefill || '';
  $('claude-results').classList.add('hidden');
  $('claude-input-area').style.display = '';
  $('claude-submit-label').textContent = 'Consultar';
  $('btn-claude-submit').disabled = false;
  $('modal-claude').classList.remove('hidden');
  setTimeout(() => $('claude-input').focus(), 50);
}

function closeClaudeModal() {
  $('modal-claude').classList.add('hidden');
  claudeResult = null;
}

async function submitClaudeQuery() {
  const topic = $('claude-input').value.trim();
  if (!topic) { toast('Escribe un tema o texto primero', 'error'); return; }

  const btn = $('btn-claude-submit');
  btn.disabled = true;
  $('claude-submit-label').innerHTML = '<span class="claude-spinner" style="display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,0.3);border-top-color:#fff;border-radius:50%;animation:spin 0.8s linear infinite;vertical-align:middle;margin-right:6px;"></span>Consultando…';

  $('claude-results').classList.add('hidden');

  try {
    const res = await fetch(`${API}/claude-assist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Error en la consulta');

    claudeResult = data;

    // Populate results
    $('claude-result-desc').textContent = data.description || '(sin descripción)';

    const urlWrap = $('claude-result-url-wrap');
    const urlEl   = $('claude-result-url');
    if (data.url) {
      urlEl.href = data.url;
      urlEl.textContent = data.url;
      urlWrap.style.display = '';
    } else {
      urlWrap.style.display = 'none';
    }

    const imgWrap = $('claude-result-image-wrap');
    const imgEl   = $('claude-result-image');
    if (data.imageUrl) {
      const proxyUrl = `${API}/proxy-image?url=${encodeURIComponent(data.imageUrl)}`;
      imgEl.src = proxyUrl;
      imgEl.onerror = () => { imgWrap.style.display = 'none'; };
      imgWrap.style.display = '';
    } else {
      imgWrap.style.display = 'none';
    }

    $('claude-input-area').style.display = 'none';
    $('claude-results').classList.remove('hidden');

  } catch (err) {
    toast(`Claude: ${err.message}`, 'error', 6000);
    btn.disabled = false;
    $('claude-submit-label').textContent = 'Consultar';
  }
}

async function acceptClaudeResult() {
  if (!claudeResult) return;

  if (claudeResult.description) {
    $('field-description').value = claudeResult.description;
  }

  if (claudeResult.url) {
    $('field-source-url').value = claudeResult.url;
    const link = $('field-source-link');
    link.href = claudeResult.url;
    link.classList.remove('hidden');
  }

  if (claudeResult.imageUrl) {
    try {
      const proxyUrl = `${API}/proxy-image?url=${encodeURIComponent(claudeResult.imageUrl)}`;
      const imgRes = await fetch(proxyUrl);
      if (imgRes.ok) {
        const blob = await imgRes.blob();
        const ext = blob.type.split('/')[1] || 'jpg';
        const file = new File([blob], `claude-image.${ext}`, { type: blob.type });
        const dt = new DataTransfer();
        dt.items.add(file);
        $('field-image').files = dt.files;
        $('field-image').dispatchEvent(new Event('change'));
        $('image-field-container').classList.remove('hidden');
        $('btn-show-image').textContent = '✕';
      }
    } catch (_) { /* image optional, skip silently */ }
  }

  closeClaudeModal();
  toast('Datos de Claude aplicados al formulario', 'success');
}

$('btn-claude').addEventListener('click', () => {
  openClaudeModal($('field-description').value);
});

$('btn-close-claude').addEventListener('click', closeClaudeModal);
$('modal-claude').addEventListener('click', e => {
  if (e.target === $('modal-claude')) closeClaudeModal();
});

$('btn-claude-submit').addEventListener('click', submitClaudeQuery);
$('claude-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submitClaudeQuery();
  if (e.key === 'Escape') closeClaudeModal();
});

$('btn-claude-accept').addEventListener('click', acceptClaudeResult);
$('btn-claude-retry').addEventListener('click', () => {
  claudeResult = null;
  $('claude-results').classList.add('hidden');
  $('claude-input-area').style.display = '';
  $('claude-submit-label').textContent = 'Consultar';
  $('btn-claude-submit').disabled = false;
  setTimeout(() => $('claude-input').focus(), 50);
});

// ─── Export CSV ───────────────────────────────────────────────────────────────
async function doExport() {
  toast('Exportando a Dropbox…', 'info');
  try {
    const res = await fetch(`${API}/export/csv`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    toast(`✓ ${data.message}`, 'success', 6000);
  } catch (err) {
    toast(`Error al exportar: ${err.message}`, 'error', 6000);
  }
}

$('btn-export-csv').addEventListener('click', doExport);
$('btn-export-csv-list').addEventListener('click', doExport);

// ─── List: Load ───────────────────────────────────────────────────────────────
async function loadList() {
  const tbody = $('table-body');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="10">Cargando…</td></tr>';

  const params = new URLSearchParams();
  params.set('sort', state.listSort.col);
  params.set('order', state.listSort.order);
  params.set('page', state.listPage);
  params.set('limit', state.listLimit);

  // Filters
  const topicChecked = [...$$('#filter-topic input:checked')].map(i => i.value);
  if (topicChecked.length) params.set('topic', topicChecked.join(','));

  const activeVal = $('filter-active').value;
  if (activeVal !== '') params.set('active', activeVal);

  const freqChecked = [...$$('#filter-frequency input:checked')].map(i => i.value);
  if (freqChecked.length) params.set('frequency', freqChecked.join(','));

  const dateFrom = $('filter-date-from').value;
  if (dateFrom) params.set('date_from', dateFrom);
  const dateTo = $('filter-date-to').value;
  if (dateTo) params.set('date_to', dateTo);

  const recMin = $('filter-recalled-min').value;
  if (recMin !== '') params.set('recalled_min', recMin);
  const recMax = $('filter-recalled-max').value;
  if (recMax !== '') params.set('recalled_max', recMax);

  try {
    const res = await fetch(`${API}/memories?${params}`);
    if (!res.ok) throw new Error('Error cargando datos');
    const { rows, total } = await res.json();
    state.listTotal = total;

    $('record-count').textContent = `${total} registro${total !== 1 ? 's' : ''}`;

    if (!rows.length) {
      tbody.innerHTML = '<tr class="empty-row"><td colspan="10">No hay memorias que mostrar</td></tr>';
      renderPagination(total);
      return;
    }

    tbody.innerHTML = rows.map(m => buildRow(m)).join('');
    attachRowEvents();
    renderPagination(total);
    updateSortIcons();
  } catch (err) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="10">Error: ${err.message}</td></tr>`;
    toast(err.message, 'error');
  }
}

function buildRow(m) {
  const color = getBadgeColor(m.times_recalled);
  const desc = m.description.length > 80
    ? m.description.substring(0, 80) + '…'
    : m.description;
  const fullDesc = m.description.replace(/"/g, '&quot;').replace(/</g, '&lt;');
  const nextSend = m.next_send_date ? formatDate(m.next_send_date) : '—';
  const createdAt = formatDate(m.created_at);
  const freqLabel = FREQ_LABELS[m.frequency] || m.frequency;
  const activeChecked = m.active ? 'checked' : '';
  const imageSrc = m.image_path ? `/uploads/${m.image_path}` : '';

  return `<tr data-id="${m.id}">
    <td><span class="tag-topic">${esc(m.topic)}</span></td>
    <td class="desc-cell" title="${fullDesc}">${esc(desc)}</td>
    <td style="white-space:nowrap;font-family:var(--mono);font-size:0.75rem;">${createdAt}</td>
    <td><span class="freq-badge">${freqLabel}</span></td>
    <td><span class="recalled-badge" style="background:${color}">${m.times_recalled}</span></td>
    <td style="white-space:nowrap;font-family:var(--mono);font-size:0.75rem;">${nextSend}</td>
    <td class="col-icon">${m.image_path
      ? `<button class="col-icon-btn btn-view-image" data-src="${imageSrc}" title="Ver imagen">📷</button>`
      : '<span style="color:var(--text-dim)">—</span>'}</td>
    <td class="col-icon">${m.source_url
      ? `<a href="${esc(m.source_url)}" target="_blank" class="col-icon-btn" title="${esc(m.source_url)}">🔗</a>`
      : '<span style="color:var(--text-dim)">—</span>'}</td>
    <td>
      <label class="toggle-switch" title="${m.active ? 'Desactivar' : 'Activar'}">
        <input type="checkbox" class="toggle-active" data-id="${m.id}" ${activeChecked} />
        <span class="toggle-slider"></span>
      </label>
    </td>
    <td>
      <div style="display:flex;gap:6px;align-items:center;">
        <button class="btn btn-ghost btn-sm btn-edit" data-id="${m.id}" title="Editar">✏️</button>
        <button class="btn btn-danger-outline btn-sm btn-delete-row" data-id="${m.id}" title="Eliminar">🗑️</button>
        <button class="btn btn-claude-orange btn-sm btn-claude-row" data-id="${m.id}" data-desc="${fullDesc}" title="Claude AI" style="padding:4px 8px;">
          <span class="claude-dot-orange" style="width:7px;height:7px;"></span>
        </button>
      </div>
    </td>
  </tr>`;
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function attachRowEvents() {
  // Edit
  $$('.btn-edit').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = Number(btn.dataset.id);
      try {
        const res = await fetch(`${API}/memories/${id}`);
        const memory = await res.json();
        populateForm(memory);
        switchTab('ficha');
      } catch (err) {
        toast(`Error: ${err.message}`, 'error');
      }
    });
  });

  // Delete from list
  $$('.btn-delete-row').forEach(btn => {
    btn.addEventListener('click', () => {
      state.deleteTarget = Number(btn.dataset.id);
      $('modal-delete').classList.remove('hidden');
    });
  });

  // Toggle active inline
  $$('.toggle-active').forEach(chk => {
    chk.addEventListener('change', async () => {
      const id = Number(chk.dataset.id);
      try {
        await fetch(`${API}/memories/${id}/toggle`, { method: 'PATCH' });
      } catch (err) {
        toast(`Error: ${err.message}`, 'error');
        chk.checked = !chk.checked; // revert
      }
    });
  });

  // Image modal
  $$('.btn-view-image').forEach(btn => {
    btn.addEventListener('click', () => {
      $('modal-image-src').src = btn.dataset.src;
      $('modal-image').classList.remove('hidden');
    });
  });

  // Claude from list
  $$('.btn-claude-row').forEach(btn => {
    btn.addEventListener('click', () => {
      const desc = btn.dataset.desc.replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
      openClaudeModal(desc);
    });
  });
}

// ─── Image modal close ────────────────────────────────────────────────────────
$('btn-close-image').addEventListener('click', () => $('modal-image').classList.add('hidden'));
$('modal-image').addEventListener('click', e => {
  if (e.target === $('modal-image')) $('modal-image').classList.add('hidden');
});

// ─── Modal delete from list (reuse same modal) ────────────────────────────────
$('btn-confirm-delete').addEventListener('click', async () => {
  // Already handled above (ficha) — handles list too since state.deleteTarget is set
}, { once: false });

// ─── Sorting ──────────────────────────────────────────────────────────────────
$$('.sortable').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.dataset.col;
    if (state.listSort.col === col) {
      state.listSort.order = state.listSort.order === 'desc' ? 'asc' : 'desc';
    } else {
      state.listSort.col = col;
      state.listSort.order = 'desc';
    }
    state.listPage = 1;
    loadList();
  });
});

function updateSortIcons() {
  $$('.sortable').forEach(th => {
    const icon = th.querySelector('.sort-icon');
    if (th.dataset.col === state.listSort.col) {
      icon.textContent = state.listSort.order === 'desc' ? '↓' : '↑';
    } else {
      icon.textContent = '';
    }
  });
}

// ─── Pagination ───────────────────────────────────────────────────────────────
function renderPagination(total) {
  const container = $('pagination');
  const totalPages = Math.ceil(total / state.listLimit);
  if (totalPages <= 1) { container.innerHTML = ''; return; }

  let html = '';
  html += `<button class="page-btn" ${state.listPage <= 1 ? 'disabled' : ''} data-page="${state.listPage - 1}">‹</button>`;
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || Math.abs(i - state.listPage) <= 2) {
      html += `<button class="page-btn ${i === state.listPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
    } else if (Math.abs(i - state.listPage) === 3) {
      html += `<span style="color:var(--text-dim);padding:0 4px">…</span>`;
    }
  }
  html += `<button class="page-btn" ${state.listPage >= totalPages ? 'disabled' : ''} data-page="${state.listPage + 1}">›</button>`;
  container.innerHTML = html;

  container.querySelectorAll('.page-btn:not([disabled])').forEach(btn => {
    btn.addEventListener('click', () => {
      state.listPage = Number(btn.dataset.page);
      loadList();
    });
  });
}

// ─── Filters ──────────────────────────────────────────────────────────────────
$('btn-toggle-filters').addEventListener('click', () => {
  const panel = $('filters-panel');
  panel.classList.toggle('hidden');
  $('btn-toggle-filters').textContent = panel.classList.contains('hidden')
    ? '▼ Filtros'
    : '▲ Filtros';
});

$('btn-apply-filters').addEventListener('click', () => {
  state.listPage = 1;
  loadList();
});

$('btn-reset-filters').addEventListener('click', () => {
  $$('#filter-topic input, #filter-frequency input').forEach(i => i.checked = false);
  $('filter-active').value = '';
  $('filter-date-from').value = '';
  $('filter-date-to').value = '';
  $('filter-recalled-min').value = '';
  $('filter-recalled-max').value = '';
  state.listPage = 1;
  loadList();
});

// ─── Search modal ─────────────────────────────────────────────────────────────
let searchDebounce = null;

$('btn-buscar').addEventListener('click', () => {
  $('modal-search').classList.remove('hidden');
  $('search-input').value = '';
  $('search-results').innerHTML = '';
  setTimeout(() => $('search-input').focus(), 50);
});

$('btn-close-search').addEventListener('click', () => {
  $('modal-search').classList.add('hidden');
});

$('modal-search').addEventListener('click', e => {
  if (e.target === $('modal-search')) $('modal-search').classList.add('hidden');
});

// Keyboard: Escape closes, Enter selects first result
$('search-input').addEventListener('keydown', e => {
  if (e.key === 'Escape') $('modal-search').classList.add('hidden');
  if (e.key === 'Enter') {
    const first = $('search-results').querySelector('.search-result-item');
    if (first) first.click();
  }
});

$('search-input').addEventListener('input', () => {
  clearTimeout(searchDebounce);
  const q = $('search-input').value.trim();
  if (!q) { $('search-results').innerHTML = ''; return; }
  $('search-results').innerHTML = '<div class="search-loading">Buscando…</div>';
  searchDebounce = setTimeout(() => doSearch(q), 280);
});

async function doSearch(query) {
  try {
    const params = new URLSearchParams({ search: query, limit: 30, sort: 'created_at', order: 'desc' });
    const res = await fetch(`${API}/memories?${params}`);
    if (!res.ok) throw new Error('Error en búsqueda');
    const { rows } = await res.json();
    renderSearchResults(rows, query);
  } catch (err) {
    $('search-results').innerHTML = `<div class="search-empty">Error: ${err.message}</div>`;
  }
}

function renderSearchResults(rows, query) {
  const container = $('search-results');
  if (!rows.length) {
    container.innerHTML = '<div class="search-empty">Sin resultados</div>';
    return;
  }
  const hi = (str, q) => {
    if (!str) return '';
    const safe = String(str).replace(/</g, '&lt;');
    const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return safe.replace(re, '<mark>$1</mark>');
  };
  container.innerHTML = rows.map(m => {
    const desc = m.description.length > 120 ? m.description.substring(0, 120) + '…' : m.description;
    const freq = FREQ_LABELS[m.frequency] || m.frequency;
    return `<div class="search-result-item" data-id="${m.id}">
      <span class="sri-topic">${esc(m.topic)}</span>
      <span class="sri-desc">${hi(desc, query)}</span>
      <span class="sri-meta">#${m.id} · ${freq} · ${formatDate(m.created_at)}</span>
    </div>`;
  }).join('');

  container.querySelectorAll('.search-result-item').forEach(item => {
    item.addEventListener('click', async () => {
      const id = Number(item.dataset.id);
      $('modal-search').classList.add('hidden');
      try {
        const res = await fetch(`${API}/memories/${id}`);
        const memory = await res.json();
        populateForm(memory);
        switchTab('ficha');
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } catch (err) {
        toast(`Error: ${err.message}`, 'error');
      }
    });
  });
}

// Highlight style
const style = document.createElement('style');
style.textContent = 'mark { background: rgba(122,37,181,0.18); color: var(--purple,#7A25B5); border-radius:2px; padding:0 1px; }';
document.head.appendChild(style);

// ─── Init ─────────────────────────────────────────────────────────────────────
clearForm();
refreshNavList();
