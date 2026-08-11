'use strict';

// ── Certificado de asistencia — frontend ────────────────────────────────────────
const API = '/feep/certificados/api';
const $ = id => document.getElementById(id);

const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
  'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const THEME_COLORS = {
  clasico: '#1b2a4a', burdeos: '#6e1e2a', verde: '#1f4636', grafito: '#2f3336',
};

const state = { logo: null, signature: null, accent: 'clasico', orientation: 'horizontal', meta: null, previewUrl: null };

function longDateToday() {
  const d = new Date();
  return `${d.getDate()} de ${MONTHS[d.getMonth()]} de ${d.getFullYear()}`;
}
// ISO (YYYY-MM-DD) → "10 de noviembre de 2018"
function isoToLong(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
  return m ? `${+m[3]} de ${MONTHS[+m[2] - 1]} de ${m[1]}` : '';
}

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json().catch(() => ({})) : {};
  if (!r.ok) throw new Error(data.error || `Error ${r.status}`);
  return data;
}
async function apiPdfBlob(path, body) {
  const r = await fetch(API + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || `Error ${r.status}`);
  }
  return r.blob();
}

// Process an image file on the SERVER (sharp) → normalised data URL. This works
// for any format, including iPhone HEIC which the browser can't decode client-side.
async function uploadImage(file, kind) {
  const fd = new FormData();
  fd.append('image', file);
  const r = await fetch(`${API}/image?kind=${encodeURIComponent(kind)}`, { method: 'POST', body: fd });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || 'No se pudo procesar la imagen.');
  return data.dataUrl;
}

function collectData() {
  return {
    recipient_name: $('f-name').value,
    role: $('f-role').value,
    event: $('f-event').value,
    talk_title: $('f-talk').value,
    date_text: $('f-date').value,
    event_date: $('f-event-date').value || null,
    place: $('f-place').value,
    signer_name: $('f-signer').value,
    signer_role: $('f-signer-role').value,
    foundation: state.meta ? state.meta.foundation : undefined,
    logo_data: state.logo,
    signature_data: state.signature,
    accent: state.accent,
    orientation: state.orientation,
  };
}

// Orientation toggle
function setOrient(o, skipPreview) {
  state.orientation = o === 'vertical' ? 'vertical' : 'horizontal';
  document.querySelectorAll('#orient .seg-btn').forEach(b => b.classList.toggle('sel', b.dataset.orient === state.orientation));
  if (!skipPreview) schedulePreview();
}
function wireOrient() {
  document.querySelectorAll('#orient .seg-btn').forEach(b => b.addEventListener('click', () => setOrient(b.dataset.orient)));
}

// ── Live preview (debounced) ────────────────────────────────────────────────────
let previewTimer = null;
function schedulePreview() {
  if (previewTimer) clearTimeout(previewTimer);
  previewTimer = setTimeout(runPreview, 650);
}
async function runPreview() {
  $('preview-note').textContent = 'Generando…';
  try {
    const blob = await apiPdfBlob('/preview', collectData());
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = URL.createObjectURL(blob);
    $('preview').src = state.previewUrl + '#toolbar=0&view=FitH';
    $('preview-note').textContent = '';
  } catch (err) {
    $('preview-note').textContent = err.message;
  }
}

// ── Uploaders ───────────────────────────────────────────────────────────────────
function wireUploader(kind, maxDim) {
  const drop = $(kind + '-drop'), input = $(kind + '-input'), thumb = $(kind + '-thumb'), clear = $(kind + '-clear');
  const canonical = kind === 'logo' ? 'logo' : 'signature';
  const idle = canonical === 'logo' ? 'Subir logo (cualquier formato, incl. HEIC del iPhone)' : 'Subir firma (PNG con fondo transparente recomendado)';
  const setImg = (dataUrl) => {
    state[canonical] = dataUrl;
    if (dataUrl) { thumb.src = dataUrl; thumb.style.display = 'block'; clear.style.display = 'inline'; drop.textContent = '✓ Imagen cargada — cambiar'; }
    else { thumb.style.display = 'none'; clear.style.display = 'none'; drop.textContent = idle; }
    schedulePreview();
  };
  drop.addEventListener('click', () => input.click());
  input.addEventListener('change', async () => {
    if (!input.files[0]) return;
    drop.textContent = 'Procesando imagen…';
    try { setImg(await uploadImage(input.files[0], canonical)); }
    catch (e) { setMsg('form-msg', e.message, true); drop.textContent = idle; }
    input.value = '';
  });
  clear.addEventListener('click', () => setImg(null));
  // expose the setter under the CANONICAL name ('logo' | 'signature') so recovery
  // and defaults-prefill callers match, regardless of the DOM element ids.
  wireUploader['set_' + canonical] = setImg;
}

function setMsg(id, text, isErr) {
  const el = $(id); el.textContent = text || ''; el.className = 'msg ' + (isErr ? 'err' : 'ok');
  if (text && !isErr) setTimeout(() => { if (el.textContent === text) el.textContent = ''; }, 4000);
}

// ── Themes ───────────────────────────────────────────────────────────────────────
function renderThemes(themes) {
  const box = $('themes'); box.innerHTML = '';
  themes.forEach(key => {
    const dot = document.createElement('div');
    dot.className = 'theme-dot' + (key === state.accent ? ' sel' : '');
    dot.style.background = THEME_COLORS[key] || '#1b2a4a';
    dot.title = key;
    dot.addEventListener('click', () => {
      state.accent = key;
      box.querySelectorAll('.theme-dot').forEach(d => d.classList.remove('sel'));
      dot.classList.add('sel');
      schedulePreview();
    });
    box.appendChild(dot);
  });
}

// ── Repository ───────────────────────────────────────────────────────────────────
async function refreshRepo() {
  const wrap = $('repo-list');
  try {
    const { items } = await api('/list');
    if (!items.length) { wrap.innerHTML = '<p class="empty">Aún no hay certificados guardados.</p>'; return; }
    wrap.innerHTML = '';
    for (const it of items) {
      const row = document.createElement('div');
      row.className = 'repo-item';
      const when = fmtDate(it.created_at);
      row.innerHTML =
        `<div class="main">
           <div class="name">${esc(it.recipient_name)}</div>
           <div class="meta">${esc(it.ref || '')}${it.role ? ' · ' + esc(it.role) : ''}${it.event ? ' · ' + esc(clip(it.event, 70)) : ''}</div>
           <div class="meta">${esc(it.date_text || '')}${it.date_text ? ' · ' : ''}creado ${when}</div>
           <div class="row-actions">
             <button class="btn btn-ghost" data-act="load">Recuperar</button>
             <button class="btn btn-gold" data-act="download">⬇ PDF</button>
             <button class="btn btn-ghost" data-act="email">✉ Email</button>
             <button class="btn btn-danger" data-act="delete">Eliminar</button>
           </div>
         </div>`;
      row.querySelector('[data-act=load]').addEventListener('click', () => loadCert(it.id));
      row.querySelector('[data-act=download]').addEventListener('click', () => { window.location.href = `${API}/cert/${it.id}/pdf`; });
      row.querySelector('[data-act=email]').addEventListener('click', () => emailCert(it));
      row.querySelector('[data-act=delete]').addEventListener('click', () => deleteCert(it));
      wrap.appendChild(row);
    }
  } catch (err) { wrap.innerHTML = `<p class="empty">${esc(err.message)}</p>`; }
}

async function loadCert(id) {
  try {
    const { item } = await api('/cert/' + id);
    $('f-name').value = item.recipient_name || '';
    $('f-role').value = item.role || '';
    $('f-event').value = item.event || '';
    $('f-talk').value = item.talk_title || '';
    $('f-event-date').value = item.event_date || '';
    $('f-date').value = item.date_text || '';
    $('f-place').value = item.place || '';
    $('f-signer').value = item.signer_name || '';
    $('f-signer-role').value = item.signer_role || '';
    state.accent = item.accent || 'clasico';
    renderThemes(state.meta.themes);
    setOrient(item.orientation || 'horizontal', true);
    wireUploader['set_logo'](item.logo_data || null);
    wireUploader['set_signature'](item.signature_data || null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    setMsg('action-msg', `Recuperado ${item.ref || ''}. Puedes editarlo y volver a guardarlo.`, false);
    runPreview();
  } catch (err) { setMsg('action-msg', err.message, true); }
}

async function emailCert(it) {
  if (!state.meta.emailConfigured) { setMsg('action-msg', 'El envío por email no está configurado en el servidor.', true); return; }
  const to = prompt('Enviar el certificado a:', state.meta.defaultEmail || '');
  if (!to) return;
  try {
    await api(`/cert/${it.id}/email`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ to: to.trim() }) });
    setMsg('action-msg', `Enviado a ${to.trim()}.`, false);
  } catch (err) { setMsg('action-msg', err.message, true); }
}

async function deleteCert(it) {
  if (!confirm(`¿Eliminar el certificado de «${it.recipient_name}» (${it.ref})?`)) return;
  try { await api('/cert/' + it.id, { method: 'DELETE' }); refreshRepo(); }
  catch (err) { setMsg('action-msg', err.message, true); }
}

// ── Actions ───────────────────────────────────────────────────────────────────────
function wireActions() {
  $('btn-refresh').addEventListener('click', runPreview);

  $('btn-download').addEventListener('click', async () => {
    if (!$('f-name').value.trim()) { setMsg('action-msg', 'Indica el nombre y apellidos.', true); return; }
    try {
      const blob = await apiPdfBlob('/preview', collectData());
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `Certificado_${($('f-name').value.trim() || 'certificado').replace(/[^\w.\- áéíóúñÁÉÍÓÚÑ]/gi, '_')}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    } catch (err) { setMsg('action-msg', err.message, true); }
  });

  $('btn-save').addEventListener('click', async () => {
    if (!$('f-name').value.trim()) { setMsg('action-msg', 'Indica el nombre y apellidos.', true); return; }
    try {
      const { item } = await api('/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(collectData()) });
      setMsg('action-msg', `Guardado como ${item.ref}.`, false);
      refreshRepo();
    } catch (err) { setMsg('action-msg', err.message, true); }
  });

  $('btn-save-defaults').addEventListener('click', async () => {
    try {
      await api('/defaults', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          logo_data: state.logo, signature_data: state.signature,
          signer_name: $('f-signer').value, signer_role: $('f-signer-role').value,
          accent: state.accent, orientation: state.orientation,
        }),
      });
      setMsg('form-msg', 'Guardado como predeterminado. Se rellenará automáticamente la próxima vez.', false);
    } catch (err) { setMsg('form-msg', err.message, true); }
  });

  // Picking the event date auto-fills the display text and recomputes the preview
  // (the certificate is expedited the day after — computed server-side).
  $('f-event-date').addEventListener('change', () => {
    const iso = $('f-event-date').value;
    if (iso) $('f-date').value = isoToLong(iso);
    schedulePreview();
  });

  // Re-preview on edits
  ['f-name', 'f-role', 'f-event', 'f-talk', 'f-date', 'f-place', 'f-signer', 'f-signer-role']
    .forEach(id => $(id).addEventListener('input', schedulePreview));
}

// ── Helpers ───────────────────────────────────────────────────────────────────────
function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function clip(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; }
function fmtDate(s) {
  if (!s) return '';
  const d = new Date(s.replace(' ', 'T') + 'Z');
  if (isNaN(d)) return s;
  return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' });
}

// ── Boot ────────────────────────────────────────────────────────────────────────
(async () => {
  wireUploader('logo', 800);
  wireUploader('sig', 900);
  wireOrient();
  wireActions();
  setOrient('horizontal', true);
  $('f-date').value = longDateToday();
  try {
    const meta = await api('/meta');
    state.meta = meta;
    const d = meta.defaults || {};
    if (d.signer_name) $('f-signer').value = d.signer_name;
    if (d.signer_role) $('f-signer-role').value = d.signer_role;
    if (d.accent) state.accent = d.accent;
    if (d.orientation) setOrient(d.orientation, true);
    if (d.logo_data) wireUploader['set_logo'](d.logo_data);
    if (d.signature_data) wireUploader['set_signature'](d.signature_data);
    renderThemes(meta.themes);
  } catch (err) { setMsg('form-msg', err.message, true); }
  runPreview();
  refreshRepo();
})();
