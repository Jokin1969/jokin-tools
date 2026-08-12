'use strict';

// ── Sellos — Miscelánea tool (Batchwork) ───────────────────────────────────────
// Self-contained UI mounted by app.js when the "Generar sellos" operation is
// selected. Clone of the QR tool adapted to digital rubber stamps. Reuses the
// qr-* CSS classes. Talks to /batchwork/api/stamp/*.
(function () {
  const API = '/batchwork/api/stamp';
  const DEBOUNCE = 300;
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let root = null;
  let state = null;
  let previewTimer = null;
  const q = (id) => root.querySelector('#' + id);

  function freshState() {
    return {
      name: '', shape: 'doubleCircle', ink: '#1B3A8C', transparent: true, bg: '#ffffff',
      border: true, borderWidth: 1.6, innerLines: false, separator: 'star',
      topText: '', bottomText: '', centerText: '', arcSize: 1, centerSize: 1,
      logo: null, logoName: '', logoScale: 40, logoInk: true,
      texture: 'entintado', intensity: 55, rotation: 0,
    };
  }

  function currentConfig() {
    return {
      shape: state.shape, ink: state.ink,
      bg: state.transparent ? 'transparent' : state.bg,
      border: state.border, borderWidth: state.borderWidth,
      innerLines: state.innerLines, separator: state.separator,
      topText: state.topText, bottomText: state.bottomText, centerText: state.centerText,
      arcSize: state.arcSize, centerSize: state.centerSize,
      logo: state.logo, logoScale: state.logoScale, logoInk: state.logoInk,
      texture: state.texture, intensity: state.intensity, rotation: state.rotation,
    };
  }

  const stem = () => (state.name.trim() || 'sello').replace(/[^\w.\- áéíóúñ]/gi, '_').slice(0, 80) || 'sello';

  // ── Markup ────────────────────────────────────────────────────────────────────
  function template() {
    return `
    <div class="qr-tool">
      <div class="qr-grid">
        <div class="qr-controls">
          <div class="qr-field">
            <span class="qr-label">Textos del sello</span>
            <input id="st-top" type="text" maxlength="60" placeholder="Texto que bordea arriba (p. ej. Fundación Española)" />
            <input id="st-center" type="text" maxlength="120" placeholder="Texto central (usa una línea o varias con Intro)" style="margin-top:8px" />
            <input id="st-bottom" type="text" maxlength="60" placeholder="Texto que bordea abajo (p. ej. Enfermedades Priónicas)" style="margin-top:8px" />
          </div>

          <div class="qr-field">
            <span class="qr-label">Nombre <span class="qr-opt">· opcional, para el repositorio</span></span>
            <input id="st-name" type="text" maxlength="120" placeholder="Si lo dejas vacío se asigna un nombre automático" />
          </div>

          <div class="qr-field">
            <span class="qr-label">Forma</span>
            <div class="qr-styles" id="st-shapes"><span class="qr-hint">Cargando formas…</span></div>
          </div>

          <div class="qr-field">
            <span class="qr-label">Textura <span class="qr-opt">· realismo del sello</span></span>
            <div class="qr-styles" id="st-textures"><span class="qr-hint">Cargando texturas…</span></div>
            <label class="qr-slider"><span class="qr-hint">Intensidad del desgaste</span>
              <input type="range" id="st-intensity" min="0" max="100" value="55" /></label>
          </div>

          <div class="qr-field">
            <span class="qr-label">Color de tinta</span>
            <div class="qr-row">
              <label class="qr-color"><input type="color" id="st-ink" value="#1B3A8C"><span>Tinta</span></label>
              <div class="qr-inks" id="st-inks"></div>
            </div>
            <div class="qr-row">
              <label class="qr-check"><input type="checkbox" id="st-transparent" checked> Fondo transparente</label>
              <label class="qr-color" id="st-bg-wrap" style="display:none"><input type="color" id="st-bg" value="#ffffff"><span>Fondo</span></label>
            </div>
          </div>

          <div class="qr-field">
            <span class="qr-label">Disposición</span>
            <div class="qr-row">
              <label class="qr-check"><input type="checkbox" id="st-border" checked> Borde</label>
              <label class="qr-check"><input type="checkbox" id="st-inner"> Líneas interiores</label>
              <label class="qr-sel">Separador
                <select id="st-sep">
                  <option value="star">Estrella</option>
                  <option value="dot">Punto</option>
                  <option value="none">Ninguno</option>
                </select>
              </label>
            </div>
            <label class="qr-slider"><span class="qr-hint">Grosor del borde</span>
              <input type="range" id="st-bw" min="0.6" max="3" step="0.1" value="1.6" /></label>
            <label class="qr-slider"><span class="qr-hint">Tamaño del texto del borde</span>
              <input type="range" id="st-arc" min="0.6" max="2" step="0.05" value="1" /></label>
            <label class="qr-slider"><span class="qr-hint">Tamaño del texto central</span>
              <input type="range" id="st-cs" min="0.5" max="2.2" step="0.05" value="1" /></label>
            <label class="qr-slider"><span class="qr-hint">Rotación (° · como al estampar)</span>
              <input type="range" id="st-rot" min="-20" max="20" value="0" /></label>
          </div>

          <div class="qr-field">
            <span class="qr-label">Logo / emblema central <span class="qr-opt">· opcional</span></span>
            <div class="qr-logo-row">
              <button type="button" class="qr-btn qr-btn-soft" id="st-logo-pick">Elegir imagen…</button>
              <input type="file" id="st-logo-file" accept="image/*" hidden />
              <span class="qr-logo-name" id="st-logo-name"></span>
              <button type="button" class="qr-btn-x" id="st-logo-remove" style="display:none" title="Quitar logo">✕</button>
            </div>
            <div class="qr-logo-size" id="st-logo-size" style="display:none">
              <label class="qr-check"><input type="checkbox" id="st-logo-ink" checked> Convertir el logo a la tinta del sello (silueta)</label>
              <label class="qr-slider"><span class="qr-hint">Tamaño del logo</span>
                <input type="range" id="st-logo-scale" min="15" max="70" value="40" /></label>
            </div>
          </div>
        </div>

        <div class="qr-preview-col">
          <div class="qr-preview" id="st-preview" style="background:#f4f2ec">
            <div class="qr-preview-empty">Escribe los textos<br>para ver el sello</div>
          </div>
          <div class="qr-export">
            <div class="qr-export-row">
              <select id="st-format">
                <option value="png">PNG (fondo transparente)</option>
                <option value="jpeg">JPEG</option>
                <option value="webp">WEBP</option>
                <option value="svg">SVG (vectorial)</option>
                <option value="pdf">PDF</option>
              </select>
              <button class="qr-btn qr-btn-primary" id="st-download">⬇ Descargar</button>
              <button class="qr-btn qr-btn-soft" id="st-copy" title="Copiar como imagen">⧉ Copiar</button>
            </div>
            <div class="qr-export-row">
              <input id="st-email" type="email" autocomplete="off" placeholder="destinatario@email.com" />
              <button class="qr-btn qr-btn-soft" id="st-send">✉ Enviar</button>
            </div>
            <button class="qr-btn qr-btn-save" id="st-save">★ Guardar en el repositorio</button>
            <div class="qr-status" id="st-status"></div>
          </div>
        </div>
      </div>

      <div class="qr-repo">
        <div class="qr-repo-head">
          <span class="qr-label">Repositorio de sellos</span>
          <button class="qr-btn-link" id="st-repo-refresh" type="button">Actualizar</button>
        </div>
        <div class="qr-repo-list" id="st-repo-list"><span class="qr-hint">Cargando…</span></div>
      </div>
    </div>`;
  }

  // ── Preview ─────────────────────────────────────────────────────────────────────
  function schedulePreview() { clearTimeout(previewTimer); previewTimer = setTimeout(renderPreview, DEBOUNCE); }
  async function renderPreview() {
    const box = q('st-preview');
    if (!state.topText && !state.bottomText && !state.centerText && !state.logo) {
      box.innerHTML = '<div class="qr-preview-empty">Escribe los textos<br>para ver el sello</div>';
      return;
    }
    try {
      const r = await fetch(API + '/render', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentConfig()),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Error');
      box.innerHTML = data.svg;
      const svg = box.querySelector('svg');
      if (svg) { svg.removeAttribute('width'); svg.removeAttribute('height'); svg.classList.add('qr-svg'); }
    } catch (err) { box.innerHTML = `<div class="qr-preview-empty">${esc(err.message)}</div>`; }
  }

  // ── Status toast ────────────────────────────────────────────────────────────────
  let statusTimer = null;
  function toast(msg, kind) {
    const el = q('st-status');
    el.textContent = msg; el.className = 'qr-status' + (kind ? ' ' + kind : '');
    clearTimeout(statusTimer);
    if (kind === 'ok') statusTimer = setTimeout(() => { el.textContent = ''; el.className = 'qr-status'; }, 4000);
  }

  // ── Logo ──────────────────────────────────────────────────────────────────────
  function handleLogo(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const MAX = 320;
        const scale = Math.min(1, MAX / Math.max(img.width, img.height));
        const w = Math.max(1, Math.round(img.width * scale)), h = Math.max(1, Math.round(img.height * scale));
        const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
        cv.getContext('2d').drawImage(img, 0, 0, w, h);
        state.logo = cv.toDataURL('image/png'); state.logoName = file.name;
        q('st-logo-name').textContent = file.name;
        toggleLogoUI(); schedulePreview();
      };
      img.onerror = () => toast('No se pudo leer la imagen.', 'err');
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  }
  function toggleLogoUI() {
    const has = !!state.logo;
    q('st-logo-remove').style.display = has ? '' : 'none';
    q('st-logo-size').style.display = has ? '' : 'none';
  }
  function clearLogo() {
    state.logo = null; state.logoName = ''; q('st-logo-file').value = '';
    q('st-logo-name').textContent = ''; toggleLogoUI(); schedulePreview();
  }

  // ── Export / actions ─────────────────────────────────────────────────────────────
  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }
  async function exportBlob(format) {
    const r = await fetch(API + '/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config: currentConfig(), format, name: state.name }),
    });
    if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.error || 'Error al exportar'); }
    return r.blob();
  }
  const hasContent = () => !!(state.topText || state.bottomText || state.centerText || state.logo);
  async function doDownload() {
    if (!hasContent()) return toast('Escribe algún texto primero.', 'err');
    const fmt = q('st-format').value; toast('Generando…');
    try { const blob = await exportBlob(fmt); downloadBlob(blob, `${stem()}.${fmt === 'jpeg' ? 'jpg' : fmt}`); toast('Descargado ✓', 'ok'); }
    catch (err) { toast(err.message, 'err'); }
  }
  async function doCopy() {
    if (!hasContent()) return toast('Escribe algún texto primero.', 'err');
    toast('Copiando…');
    try {
      const blob = await exportBlob('png');
      if (navigator.clipboard && window.ClipboardItem) {
        await navigator.clipboard.write([new window.ClipboardItem({ 'image/png': blob })]);
        toast('Copiado al portapapeles ✓', 'ok');
      } else { downloadBlob(blob, `${stem()}.png`); toast('Portapapeles no disponible; se ha descargado.', 'ok'); }
    } catch (err) { toast('No se pudo copiar: ' + err.message, 'err'); }
  }
  async function doSend() {
    if (!hasContent()) return toast('Escribe algún texto primero.', 'err');
    const to = q('st-email').value.trim(); const fmt = q('st-format').value; toast('Enviando…');
    try {
      const r = await fetch(API + '/email', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: currentConfig(), format: fmt, name: state.name, to }),
      });
      const data = await r.json(); if (!r.ok) throw new Error(data.error || 'Error al enviar');
      toast('Enviado a ' + data.to + ' ✓', 'ok');
    } catch (err) { toast(err.message, 'err'); }
  }
  async function doSave() {
    if (!hasContent()) return toast('Escribe algún texto primero.', 'err');
    toast('Guardando…');
    try {
      const r = await fetch(API + '/save', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: state.name, config: currentConfig() }),
      });
      const data = await r.json(); if (!r.ok) throw new Error(data.error || 'Error al guardar');
      toast('Guardado como «' + data.item.name + '» ✓', 'ok'); loadRepo();
    } catch (err) { toast(err.message, 'err'); }
  }

  // ── Repository ───────────────────────────────────────────────────────────────────
  async function loadRepo() {
    const list = q('st-repo-list');
    try {
      const r = await fetch(API + '/list'); const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Error');
      if (!data.items.length) { list.innerHTML = '<span class="qr-hint">Aún no has guardado ningún sello.</span>'; return; }
      list.innerHTML = data.items.map((it) => `
        <div class="qr-repo-card" data-id="${it.id}">
          <div class="qr-repo-thumb">${it.thumb || ''}</div>
          <div class="qr-repo-info">
            <div class="qr-repo-name">${esc(it.name)}</div>
            <div class="qr-repo-url">${esc(it.subtitle || '')}</div>
          </div>
          <div class="qr-repo-actions">
            <button type="button" class="qr-btn-link" data-act="load">Recuperar</button>
            <button type="button" class="qr-btn-x" data-act="del" title="Eliminar">✕</button>
          </div>
        </div>`).join('');
      list.querySelectorAll('.qr-repo-thumb svg').forEach((svg) => { svg.removeAttribute('width'); svg.removeAttribute('height'); });
    } catch (err) { list.innerHTML = `<span class="qr-hint err">${esc(err.message)}</span>`; }
  }
  async function recover(id) {
    try {
      const r = await fetch(API + '/' + id); const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Error');
      applyConfig(data.item.config, data.item.name);
      toast('«' + data.item.name + '» recuperado. Puedes editarlo y regenerarlo.', 'ok');
      root.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) { toast(err.message, 'err'); }
  }
  async function del(id) {
    try {
      const r = await fetch(API + '/' + id, { method: 'DELETE' });
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.error || 'Error'); }
      loadRepo();
    } catch (err) { toast(err.message, 'err'); }
  }

  function applyConfig(cfg, name) {
    state = freshState();
    state.name = name || '';
    state.shape = cfg.shape || 'doubleCircle';
    state.ink = cfg.ink || cfg.fg || '#1B3A8C';
    state.transparent = cfg.bg === 'transparent' || cfg.bg == null;
    state.bg = state.transparent ? '#ffffff' : (cfg.bg || '#ffffff');
    state.border = cfg.border != null ? !!cfg.border : true;
    state.borderWidth = cfg.borderWidth || 1.6;
    state.innerLines = !!cfg.innerLines;
    state.separator = cfg.separator || 'star';
    state.topText = cfg.topText || ''; state.bottomText = cfg.bottomText || ''; state.centerText = cfg.centerText || '';
    state.arcSize = cfg.arcSize || 1; state.centerSize = cfg.centerSize || 1;
    state.logo = cfg.logo || null; state.logoName = cfg.logo ? 'logo' : ''; state.logoScale = cfg.logoScale || 40; state.logoInk = cfg.logoInk !== false;
    state.texture = cfg.texture || 'entintado'; state.intensity = cfg.intensity == null ? 55 : cfg.intensity;
    state.rotation = cfg.rotation || 0;
    syncControls(); schedulePreview();
  }

  function syncControls() {
    q('st-top').value = state.topText; q('st-center').value = state.centerText; q('st-bottom').value = state.bottomText;
    q('st-name').value = state.name;
    q('st-ink').value = state.ink;
    q('st-transparent').checked = state.transparent;
    q('st-bg').value = state.bg; q('st-bg-wrap').style.display = state.transparent ? 'none' : '';
    q('st-border').checked = state.border; q('st-inner').checked = state.innerLines; q('st-sep').value = state.separator;
    q('st-bw').value = state.borderWidth; q('st-arc').value = state.arcSize; q('st-cs').value = state.centerSize;
    q('st-rot').value = state.rotation; q('st-intensity').value = state.intensity;
    q('st-logo-scale').value = state.logoScale; q('st-logo-ink').checked = state.logoInk; q('st-logo-name').textContent = state.logoName;
    toggleLogoUI();
    markActive('st-shapes', state.shape); markActive('st-textures', state.texture);
  }
  function markActive(boxId, val) {
    root.querySelectorAll('#' + boxId + ' .qr-style-btn').forEach((b) => b.classList.toggle('active', b.dataset.val === val));
  }

  // ── Pickers ──────────────────────────────────────────────────────────────────────
  async function loadMeta() {
    try {
      const r = await fetch(API + '/meta'); const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Error');
      if (data.defaultEmail && !q('st-email').value) q('st-email').value = data.defaultEmail;
      renderPicker('st-shapes', data.shapes, 'shape');
      renderPicker('st-textures', data.textures, 'texture');
      // ink swatches
      q('st-inks').innerHTML = (data.inks || []).map((c) =>
        `<button type="button" class="st-ink-sw" data-ink="${c}" style="background:${c}" title="${c}"></button>`).join('');
      q('st-inks').querySelectorAll('.st-ink-sw').forEach((b) => b.addEventListener('click', () => {
        state.ink = b.dataset.ink; q('st-ink').value = b.dataset.ink; schedulePreview();
      }));
    } catch (err) {
      q('st-shapes').innerHTML = `<span class="qr-hint err">${esc(err.message)}</span>`;
    }
  }
  function renderPicker(boxId, items, key) {
    const box = q(boxId);
    box.innerHTML = items.map((s) => `
      <button type="button" class="qr-style-btn${s.id === state[key] ? ' active' : ''}" data-val="${s.id}" title="${esc(s.label)}">
        <span class="qr-style-thumb">${s.svg}</span>
        <span class="qr-style-name">${esc(s.label)}</span>
      </button>`).join('');
    box.querySelectorAll('.qr-style-thumb svg').forEach((svg) => { svg.removeAttribute('width'); svg.removeAttribute('height'); });
    box.querySelectorAll('.qr-style-btn').forEach((b) => b.addEventListener('click', () => {
      state[key] = b.dataset.val; markActive(boxId, b.dataset.val); schedulePreview();
    }));
  }

  // ── Wiring ───────────────────────────────────────────────────────────────────────
  function wire() {
    const on = (id, ev, fn) => q(id).addEventListener(ev, fn);
    on('st-top', 'input', (e) => { state.topText = e.target.value; schedulePreview(); });
    on('st-center', 'input', (e) => { state.centerText = e.target.value; schedulePreview(); });
    on('st-bottom', 'input', (e) => { state.bottomText = e.target.value; schedulePreview(); });
    on('st-name', 'input', (e) => { state.name = e.target.value; });
    on('st-ink', 'input', (e) => { state.ink = e.target.value; schedulePreview(); });
    on('st-transparent', 'change', (e) => { state.transparent = e.target.checked; q('st-bg-wrap').style.display = e.target.checked ? 'none' : ''; schedulePreview(); });
    on('st-bg', 'input', (e) => { state.bg = e.target.value; schedulePreview(); });
    on('st-border', 'change', (e) => { state.border = e.target.checked; schedulePreview(); });
    on('st-inner', 'change', (e) => { state.innerLines = e.target.checked; schedulePreview(); });
    on('st-sep', 'change', (e) => { state.separator = e.target.value; schedulePreview(); });
    on('st-bw', 'input', (e) => { state.borderWidth = Number(e.target.value); schedulePreview(); });
    on('st-arc', 'input', (e) => { state.arcSize = Number(e.target.value); schedulePreview(); });
    on('st-cs', 'input', (e) => { state.centerSize = Number(e.target.value); schedulePreview(); });
    on('st-rot', 'input', (e) => { state.rotation = Number(e.target.value); schedulePreview(); });
    on('st-intensity', 'input', (e) => { state.intensity = Number(e.target.value); schedulePreview(); });
    on('st-logo-pick', 'click', () => q('st-logo-file').click());
    on('st-logo-file', 'change', (e) => handleLogo(e.target.files[0]));
    on('st-logo-remove', 'click', clearLogo);
    on('st-logo-scale', 'input', (e) => { state.logoScale = Number(e.target.value); schedulePreview(); });
    on('st-logo-ink', 'change', (e) => { state.logoInk = e.target.checked; schedulePreview(); });
    on('st-download', 'click', doDownload);
    on('st-copy', 'click', doCopy);
    on('st-send', 'click', doSend);
    on('st-save', 'click', doSave);
    on('st-repo-refresh', 'click', loadRepo);
    q('st-repo-list').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-act]'); if (!btn) return;
      const card = btn.closest('.qr-repo-card'); const id = card && card.dataset.id; if (!id) return;
      if (btn.dataset.act === 'load') recover(id); else if (btn.dataset.act === 'del') del(id);
    });
  }

  function mount(container) {
    root = container;
    root.innerHTML = template();
    state = freshState();
    wire();
    syncControls();
    loadMeta();
    loadRepo();
  }

  window.StampTool = { mount };
})();
