'use strict';

// ── QRs — Miscelánea tool (Batchwork) ──────────────────────────────────────────
// Self-contained UI mounted by app.js when the "QRs" operation is selected.
// Talks to /batchwork/api/qr/* for rendering, export, email and the repository.
(function () {
  const API = '/batchwork/api/qr';
  const DEBOUNCE = 320;

  // Mirror of the server's URL normaliser, for instant client-side feedback.
  function normUrl(raw) {
    let s = String(raw || '').trim();
    if (!s) return null;
    if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(s)) s = 'https://' + s.replace(/^\/+/, '');
    let u;
    try { u = new URL(s); } catch { return null; }
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
    const host = u.hostname;
    if (!host || !/^[a-z0-9.-]+$/i.test(host)) return null;
    const isIp = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
    if (!isIp && host !== 'localhost' && !/\.[a-z]{2,}$/i.test(host)) return null;
    return u.toString();
  }

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let root = null;
  let state = null;
  let previewTimer = null;
  let metaLoaded = false;

  const q = (id) => root.querySelector('#' + id);

  function freshState() {
    return {
      url: '', name: '', style: 'classic',
      fg: '#111111', bg: '#ffffff', transparent: false,
      gradient: false, grad2: '#1B6CB0', ecc: 'M',
      logo: null, logoName: '', logoScale: 22, logoShape: 'circle', logoInner: 90,
      frame: false, frameText: 'Escáneame',
    };
  }

  function currentConfig() {
    return {
      url: state.url,
      style: state.style,
      fg: state.fg,
      bg: state.transparent ? 'transparent' : state.bg,
      gradient: state.gradient,
      grad2: state.grad2,
      ecc: state.ecc,
      logo: state.logo,
      logoScale: state.logoScale,
      logoShape: state.logoShape,
      logoInner: state.logoInner,
      frame: state.frame,
      frameText: state.frameText,
    };
  }

  const validUrl = () => normUrl(state.url);
  const stem = () => (state.name.trim() || 'qr').replace(/[^\w.\- áéíóúñ]/gi, '_').slice(0, 80) || 'qr';

  // ── Markup ────────────────────────────────────────────────────────────────────
  function template() {
    return `
    <div class="qr-tool">
      <div class="qr-grid">
        <div class="qr-controls">
          <div class="qr-field">
            <span class="qr-label">URL de destino</span>
            <div class="qr-url-row">
              <input id="qr-url" type="text" autocomplete="off" spellcheck="false"
                     placeholder="example.com · www.sitio.es · https://…" />
              <span class="qr-url-check" id="qr-url-check" aria-hidden="true"></span>
            </div>
            <span class="qr-hint" id="qr-url-hint">Acepta con o sin http(s):// y con o sin www.</span>
          </div>

          <div class="qr-field">
            <span class="qr-label">Nombre <span class="qr-opt">· opcional, para el repositorio</span></span>
            <input id="qr-name" type="text" maxlength="120"
                   placeholder="Si lo dejas vacío se asigna un nombre automático" />
          </div>

          <div class="qr-field">
            <span class="qr-label">Estilo</span>
            <div class="qr-styles" id="qr-styles"><span class="qr-hint">Cargando estilos…</span></div>
          </div>

          <div class="qr-field">
            <span class="qr-label">Color y corrección</span>
            <div class="qr-row">
              <label class="qr-color"><input type="color" id="qr-fg" value="#111111"><span>Módulos</span></label>
              <label class="qr-color"><input type="color" id="qr-bg" value="#ffffff"><span>Fondo</span></label>
              <label class="qr-check"><input type="checkbox" id="qr-transparent"> Transparente</label>
            </div>
            <div class="qr-row">
              <label class="qr-check"><input type="checkbox" id="qr-gradient"> Degradado</label>
              <label class="qr-color" id="qr-grad2-wrap" style="display:none"><input type="color" id="qr-grad2" value="#1B6CB0"><span>2.º color</span></label>
              <label class="qr-sel">Corrección
                <select id="qr-ecc">
                  <option value="L">L · baja</option>
                  <option value="M" selected>M · media</option>
                  <option value="Q">Q · alta</option>
                  <option value="H">H · máxima</option>
                </select>
              </label>
            </div>
          </div>

          <div class="qr-field">
            <span class="qr-label">Logo central <span class="qr-opt">· opcional</span></span>
            <div class="qr-logo-row">
              <button type="button" class="qr-btn qr-btn-soft" id="qr-logo-pick">Elegir imagen…</button>
              <input type="file" id="qr-logo-file" accept="image/png,image/jpeg,image/webp,image/svg+xml,image/*" hidden />
              <span class="qr-logo-name" id="qr-logo-name"></span>
              <button type="button" class="qr-btn-x" id="qr-logo-remove" style="display:none" title="Quitar logo">✕</button>
            </div>
            <div class="qr-logo-size" id="qr-logo-size" style="display:none">
              <div class="qr-logo-shape">
                <span class="qr-hint">Forma del recuadro</span>
                <label class="qr-check"><input type="radio" name="qr-logo-shape" value="circle" checked> Círculo</label>
                <label class="qr-check"><input type="radio" name="qr-logo-shape" value="square"> Cuadrado</label>
              </div>
              <label class="qr-slider"><span class="qr-hint">Tamaño del recuadro</span>
                <input type="range" id="qr-logo-scale" min="12" max="34" value="22" /></label>
              <label class="qr-slider"><span class="qr-hint">Tamaño del logo dentro</span>
                <input type="range" id="qr-logo-inner" min="40" max="100" value="90" /></label>
              <span class="qr-ecc-note">La corrección de errores sube a «H» automáticamente con logo.</span>
            </div>
          </div>

          <div class="qr-field">
            <label class="qr-check"><input type="checkbox" id="qr-frame"> Marco con etiqueta</label>
            <input id="qr-frame-text" type="text" maxlength="28" value="Escáneame"
                   placeholder="Texto del marco" style="display:none" />
          </div>
        </div>

        <div class="qr-preview-col">
          <div class="qr-preview" id="qr-preview">
            <div class="qr-preview-empty">Introduce una URL válida<br>para ver el código</div>
          </div>
          <div class="qr-export">
            <div class="qr-export-row">
              <select id="qr-format">
                <option value="png">PNG</option>
                <option value="jpeg">JPEG</option>
                <option value="webp">WEBP</option>
                <option value="svg">SVG (vectorial)</option>
                <option value="pdf">PDF</option>
              </select>
              <button class="qr-btn qr-btn-primary" id="qr-download">⬇ Descargar</button>
              <button class="qr-btn qr-btn-soft" id="qr-copy" title="Copiar como imagen">⧉ Copiar</button>
            </div>
            <div class="qr-export-row">
              <input id="qr-email" type="email" autocomplete="off" placeholder="destinatario@email.com" />
              <button class="qr-btn qr-btn-soft" id="qr-send">✉ Enviar</button>
            </div>
            <button class="qr-btn qr-btn-save" id="qr-save">★ Guardar en el repositorio</button>
            <div class="qr-status" id="qr-status"></div>
          </div>
        </div>
      </div>

      <div class="qr-repo">
        <div class="qr-repo-head">
          <span class="qr-label">Repositorio de QRs</span>
          <button class="qr-btn-link" id="qr-repo-refresh" type="button">Actualizar</button>
        </div>
        <div class="qr-repo-list" id="qr-repo-list"><span class="qr-hint">Cargando…</span></div>
      </div>
    </div>`;
  }

  // ── Preview ─────────────────────────────────────────────────────────────────────
  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(renderPreview, DEBOUNCE);
  }

  async function renderPreview() {
    const box = q('qr-preview');
    if (!validUrl()) {
      box.innerHTML = '<div class="qr-preview-empty">Introduce una URL válida<br>para ver el código</div>';
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
    } catch (err) {
      box.innerHTML = `<div class="qr-preview-empty">${esc(err.message)}</div>`;
    }
  }

  // ── URL field state ─────────────────────────────────────────────────────────────
  function refreshUrlState() {
    const ok = !!validUrl();
    const check = q('qr-url-check');
    const hint = q('qr-url-hint');
    if (!state.url.trim()) {
      check.textContent = ''; check.className = 'qr-url-check';
      hint.textContent = 'Acepta con o sin http(s):// y con o sin www.';
      hint.className = 'qr-hint';
    } else if (ok) {
      check.textContent = '✓'; check.className = 'qr-url-check ok';
      hint.textContent = 'URL válida → ' + validUrl();
      hint.className = 'qr-hint ok';
    } else {
      check.textContent = '✕'; check.className = 'qr-url-check err';
      hint.textContent = 'No parece una URL válida.';
      hint.className = 'qr-hint err';
    }
  }

  // ── Status toast (inline) ────────────────────────────────────────────────────────
  let statusTimer = null;
  function toast(msg, kind) {
    const el = q('qr-status');
    el.textContent = msg;
    el.className = 'qr-status' + (kind ? ' ' + kind : '');
    clearTimeout(statusTimer);
    if (kind === 'ok') statusTimer = setTimeout(() => { el.textContent = ''; el.className = 'qr-status'; }, 4000);
  }

  // ── Logo handling (downscale client-side to keep payloads small) ─────────────────
  function handleLogo(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const MAX = 300;
        const scale = Math.min(1, MAX / Math.max(img.width, img.height));
        const w = Math.max(1, Math.round(img.width * scale));
        const h = Math.max(1, Math.round(img.height * scale));
        const cv = document.createElement('canvas');
        cv.width = w; cv.height = h;
        cv.getContext('2d').drawImage(img, 0, 0, w, h);
        state.logo = cv.toDataURL('image/png');
        state.logoName = file.name;
        if (state.ecc === 'L' || state.ecc === 'M') { state.ecc = 'H'; q('qr-ecc').value = 'H'; }
        q('qr-logo-name').textContent = file.name;
        q('qr-logo-remove').style.display = '';
        q('qr-logo-size').style.display = '';
        schedulePreview();
      };
      img.onerror = () => toast('No se pudo leer la imagen.', 'err');
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  }

  function clearLogo() {
    state.logo = null; state.logoName = '';
    q('qr-logo-file').value = '';
    q('qr-logo-name').textContent = '';
    q('qr-logo-remove').style.display = 'none';
    q('qr-logo-size').style.display = 'none';
    schedulePreview();
  }

  // ── Download helper ──────────────────────────────────────────────────────────────
  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
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

  async function doDownload() {
    if (!validUrl()) return toast('Introduce una URL válida.', 'err');
    const fmt = q('qr-format').value;
    toast('Generando…');
    try {
      const blob = await exportBlob(fmt);
      const ext = fmt === 'jpeg' ? 'jpg' : fmt;
      downloadBlob(blob, `${stem()}.${ext}`);
      toast('Descargado ✓', 'ok');
    } catch (err) { toast(err.message, 'err'); }
  }

  async function doCopy() {
    if (!validUrl()) return toast('Introduce una URL válida.', 'err');
    toast('Copiando…');
    try {
      const blob = await exportBlob('png');
      if (navigator.clipboard && window.ClipboardItem) {
        await navigator.clipboard.write([new window.ClipboardItem({ 'image/png': blob })]);
        toast('Copiado al portapapeles ✓', 'ok');
      } else {
        downloadBlob(blob, `${stem()}.png`);
        toast('Portapapeles no disponible; se ha descargado.', 'ok');
      }
    } catch (err) { toast('No se pudo copiar: ' + err.message, 'err'); }
  }

  async function doSend() {
    if (!validUrl()) return toast('Introduce una URL válida.', 'err');
    const to = q('qr-email').value.trim();
    const fmt = q('qr-format').value;
    toast('Enviando…');
    try {
      const r = await fetch(API + '/email', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: currentConfig(), format: fmt, name: state.name, to }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Error al enviar');
      toast('Enviado a ' + data.to + ' ✓', 'ok');
    } catch (err) { toast(err.message, 'err'); }
  }

  async function doSave() {
    if (!validUrl()) return toast('Introduce una URL válida.', 'err');
    toast('Guardando…');
    try {
      const r = await fetch(API + '/save', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: state.name, config: currentConfig() }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Error al guardar');
      toast('Guardado como «' + data.item.name + '» ✓', 'ok');
      loadRepo();
    } catch (err) { toast(err.message, 'err'); }
  }

  // ── Repository ───────────────────────────────────────────────────────────────────
  async function loadRepo() {
    const list = q('qr-repo-list');
    try {
      const r = await fetch(API + '/list');
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Error');
      if (!data.items.length) {
        list.innerHTML = '<span class="qr-hint">Aún no has guardado ningún QR.</span>';
        return;
      }
      list.innerHTML = data.items.map((it) => `
        <div class="qr-repo-card" data-id="${it.id}">
          <div class="qr-repo-thumb">${it.thumb || ''}</div>
          <div class="qr-repo-info">
            <div class="qr-repo-name">${esc(it.name)}</div>
            <div class="qr-repo-url">${esc(it.url)}</div>
          </div>
          <div class="qr-repo-actions">
            <button type="button" class="qr-btn-link" data-act="load">Recuperar</button>
            <button type="button" class="qr-btn-x" data-act="del" title="Eliminar">✕</button>
          </div>
        </div>`).join('');
      list.querySelectorAll('.qr-repo-thumb svg').forEach((svg) => {
        svg.removeAttribute('width'); svg.removeAttribute('height');
      });
    } catch (err) {
      list.innerHTML = `<span class="qr-hint err">${esc(err.message)}</span>`;
    }
  }

  async function recover(id) {
    try {
      const r = await fetch(API + '/' + id);
      const data = await r.json();
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

  // Load a saved config back into the form.
  function applyConfig(cfg, name) {
    state = freshState();
    state.name = name || '';
    state.url = (cfg.url || '').replace(/\/$/, '') === '' ? '' : (cfg.url || '');
    state.style = cfg.style || 'classic';
    state.fg = cfg.fg || '#111111';
    state.transparent = cfg.bg === 'transparent';
    state.bg = state.transparent ? '#ffffff' : (cfg.bg || '#ffffff');
    state.gradient = !!cfg.gradient;
    state.grad2 = cfg.grad2 || '#1B6CB0';
    state.ecc = cfg.ecc || 'M';
    state.logo = cfg.logo || null;
    state.logoName = cfg.logo ? 'logo' : '';
    state.logoScale = cfg.logoScale || 22;
    state.logoShape = cfg.logoShape === 'square' ? 'square' : 'circle';
    state.logoInner = cfg.logoInner || 90;
    state.frame = !!cfg.frame;
    state.frameText = cfg.frameText || 'Escáneame';
    syncControls();
    schedulePreview();
  }

  // Push state → DOM controls.
  function syncControls() {
    q('qr-url').value = state.url;
    q('qr-name').value = state.name;
    q('qr-fg').value = state.fg;
    q('qr-bg').value = state.bg;
    q('qr-transparent').checked = state.transparent;
    q('qr-bg').disabled = state.transparent;
    q('qr-gradient').checked = state.gradient;
    q('qr-grad2').value = state.grad2;
    q('qr-grad2-wrap').style.display = state.gradient ? '' : 'none';
    q('qr-ecc').value = state.ecc;
    q('qr-logo-scale').value = state.logoScale;
    q('qr-logo-inner').value = state.logoInner;
    root.querySelectorAll('input[name="qr-logo-shape"]').forEach((r) => { r.checked = r.value === state.logoShape; });
    q('qr-logo-name').textContent = state.logoName;
    q('qr-logo-remove').style.display = state.logo ? '' : 'none';
    q('qr-logo-size').style.display = state.logo ? '' : 'none';
    q('qr-frame').checked = state.frame;
    q('qr-frame-text').value = state.frameText;
    q('qr-frame-text').style.display = state.frame ? '' : 'none';
    markActiveStyle();
    refreshUrlState();
  }

  function markActiveStyle() {
    root.querySelectorAll('.qr-style-btn').forEach((b) => {
      b.classList.toggle('active', b.dataset.style === state.style);
    });
  }

  // ── Style picker ─────────────────────────────────────────────────────────────────
  async function loadStyles() {
    const box = q('qr-styles');
    try {
      const r = await fetch(API + '/meta');
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Error');
      metaLoaded = true;
      if (data.defaultEmail && !q('qr-email').value) q('qr-email').value = data.defaultEmail;
      box.innerHTML = data.styles.map((s) => `
        <button type="button" class="qr-style-btn${s.id === state.style ? ' active' : ''}" data-style="${s.id}" title="${esc(s.label)}">
          <span class="qr-style-thumb">${s.svg}</span>
          <span class="qr-style-name">${esc(s.label)}</span>
        </button>`).join('');
      box.querySelectorAll('.qr-style-thumb svg').forEach((svg) => {
        svg.removeAttribute('width'); svg.removeAttribute('height');
      });
      box.querySelectorAll('.qr-style-btn').forEach((b) => {
        b.addEventListener('click', () => {
          state.style = b.dataset.style;
          // A style preset may turn the gradient on by default.
          const meta = data.styles.find((s) => s.id === b.dataset.style);
          if (meta) { state.gradient = !!meta.gradient; q('qr-gradient').checked = state.gradient; q('qr-grad2-wrap').style.display = state.gradient ? '' : 'none'; }
          markActiveStyle();
          schedulePreview();
        });
      });
    } catch (err) {
      box.innerHTML = `<span class="qr-hint err">No se pudieron cargar los estilos: ${esc(err.message)}</span>`;
    }
  }

  // ── Wiring ───────────────────────────────────────────────────────────────────────
  function wire() {
    q('qr-url').addEventListener('input', (e) => { state.url = e.target.value; refreshUrlState(); schedulePreview(); });
    q('qr-name').addEventListener('input', (e) => { state.name = e.target.value; });

    q('qr-fg').addEventListener('input', (e) => { state.fg = e.target.value; schedulePreview(); });
    q('qr-bg').addEventListener('input', (e) => { state.bg = e.target.value; schedulePreview(); });
    q('qr-transparent').addEventListener('change', (e) => {
      state.transparent = e.target.checked; q('qr-bg').disabled = e.target.checked; schedulePreview();
    });
    q('qr-gradient').addEventListener('change', (e) => {
      state.gradient = e.target.checked; q('qr-grad2-wrap').style.display = e.target.checked ? '' : 'none'; schedulePreview();
    });
    q('qr-grad2').addEventListener('input', (e) => { state.grad2 = e.target.value; schedulePreview(); });
    q('qr-ecc').addEventListener('change', (e) => { state.ecc = e.target.value; schedulePreview(); });

    q('qr-logo-pick').addEventListener('click', () => q('qr-logo-file').click());
    q('qr-logo-file').addEventListener('change', (e) => handleLogo(e.target.files[0]));
    q('qr-logo-remove').addEventListener('click', clearLogo);
    q('qr-logo-scale').addEventListener('input', (e) => { state.logoScale = Number(e.target.value); schedulePreview(); });
    q('qr-logo-inner').addEventListener('input', (e) => { state.logoInner = Number(e.target.value); schedulePreview(); });
    root.querySelectorAll('input[name="qr-logo-shape"]').forEach((rb) => {
      rb.addEventListener('change', (e) => { if (e.target.checked) { state.logoShape = e.target.value; schedulePreview(); } });
    });

    q('qr-frame').addEventListener('change', (e) => {
      state.frame = e.target.checked; q('qr-frame-text').style.display = e.target.checked ? '' : 'none'; schedulePreview();
    });
    q('qr-frame-text').addEventListener('input', (e) => { state.frameText = e.target.value; schedulePreview(); });

    q('qr-download').addEventListener('click', doDownload);
    q('qr-copy').addEventListener('click', doCopy);
    q('qr-send').addEventListener('click', doSend);
    q('qr-save').addEventListener('click', doSave);
    q('qr-email').addEventListener('input', (e) => { state.email = e.target.value; });

    q('qr-repo-refresh').addEventListener('click', loadRepo);
    q('qr-repo-list').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-act]');
      if (!btn) return;
      const card = btn.closest('.qr-repo-card');
      const id = card && card.dataset.id;
      if (!id) return;
      if (btn.dataset.act === 'load') recover(id);
      else if (btn.dataset.act === 'del') del(id);
    });
  }

  // ── Public mount ─────────────────────────────────────────────────────────────────
  function mount(container) {
    root = container;
    root.innerHTML = template();
    state = freshState();
    metaLoaded = false;
    wire();
    syncControls();
    loadStyles();
    loadRepo();
  }

  window.QRTool = { mount };
})();
