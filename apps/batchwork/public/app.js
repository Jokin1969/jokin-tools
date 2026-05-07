'use strict';

// ── Operations definition ─────────────────────────────────────────────────────
const OPERATIONS = [
  {
    group: 'Inventario',
    ops: [{
      id: 'inventory',
      label: 'Inventariar carpeta → Excel',
      desc: 'Genera un fichero Excel con el inventario del primer nivel de la carpeta seleccionada.',
      folderMode: true,
      params: [],
    }],
  },
  {
    group: 'Renombrado',
    ops: [{
      id: 'rename',
      label: 'Renombrar desde lista de nombres',
      desc: 'Renombra un lote de ficheros según el orden de líneas de un fichero .txt.',
      uploadPaired: true,
      params: [
        { id: 'keepExtension', type: 'checkbox', label: 'Conservar extensión original', default: true },
      ],
    }],
  },
  {
    group: 'Imágenes',
    ops: [
      {
        id: 'transparent-png',
        label: 'Transparentar PNG (conservando negro)',
        desc: 'Convierte el fondo claro a transparente, preservando los píxeles oscuros.',
        params: [
          { id: 'threshold', type: 'range', label: 'Umbral de negro (0–255)', min: 0, max: 255, default: 60 },
        ],
      },
      {
        id: 'resize-tiff',
        label: 'Ajustar TIFF a 300 ppp / tamaño máximo',
        desc: 'Fija los TIFF a 300 ppp y reduce dimensiones si superan el tamaño máximo indicado.',
        params: [
          { id: 'maxMB', type: 'number', label: 'Tamaño máximo (MB)', default: 12, min: 1 },
        ],
      },
    ],
  },
  {
    group: 'PDF y documentos',
    ops: [
      {
        id: 'docx-to-pdf',
        label: 'DOCX → PDF',
        desc: 'Convierte ficheros .docx a .pdf usando LibreOffice headless.',
        params: [],
      },
      {
        id: 'images-to-pdf',
        label: 'Imágenes → PDF',
        desc: 'Convierte imágenes (PNG, JPG, SVG, TIFF) a PDF. Puedes generar un PDF independiente por imagen, o unirlas todas en un único PDF en orden alfabético del nombre. Los TIFF multipágina se conservan como un único PDF con varias páginas.',
        params: [
          {
            id: 'mode', type: 'select', label: '¿Cómo quieres el resultado?', default: 'independent',
            options: [
              { value: 'independent', label: 'Un PDF independiente por imagen' },
              { value: 'merged',      label: 'Un único PDF con todas (orden alfabético)' },
            ],
          },
          { id: 'mergedName', type: 'text', label: 'Nombre del PDF unificado', default: 'imagenes.pdf', conditional: 'mode=merged' },
          { id: 'resolution', type: 'number', label: 'Resolución para ráster (DPI)', default: 150, min: 72 },
        ],
      },
      {
        id: 'pdf-to-docx',
        label: 'PDF → DOCX',
        desc: 'Convierte ficheros .pdf a .docx usando pdf2docx.',
        params: [],
      },
      {
        id: 'normalize-dni',
        label: 'Unificar carpeta a PDF (normalización DNI)',
        desc: 'Detecta el identificador (DNI) en el nombre del fichero, lo convierte a PDF y lo renombra como {ID}.pdf.',
        params: [
          { id: 'pattern', type: 'text', label: 'Patrón regex del identificador', default: '\\d{8}[A-Za-z]', advanced: true },
        ],
      },
      {
        id: 'merge-pdfs',
        label: 'Unir PDFs en uno solo',
        desc: 'Concatena todos los PDFs del lote en un único fichero, ordenados alfabéticamente.',
        params: [
          { id: 'outputName', type: 'text', label: 'Nombre del PDF resultante', default: 'unificado.pdf' },
        ],
      },
      {
        id: 'split-pdfs',
        label: 'Dividir PDFs',
        desc: 'Divide cada PDF en páginas sueltas, pares/impares, o bloques de N páginas.',
        params: [
          { id: 'expectedPages', type: 'number', label: 'Nº de páginas esperado (deja vacío para omitir validación)', default: '', min: 1 },
          {
            id: 'splitMode', type: 'select', label: 'Modo de división', default: 'pages',
            options: [
              { value: 'pages',   label: 'Páginas sueltas' },
              { value: 'even-odd', label: 'Pares / impares' },
              { value: 'blocks2', label: 'Bloques de 2 páginas' },
              { value: 'blocks3', label: 'Bloques de 3 páginas' },
              { value: 'blocksN', label: 'Bloques de N páginas (personalizable)' },
            ],
          },
          { id: 'blockSize', type: 'number', label: 'N (tamaño del bloque)', default: 4, min: 1, conditional: 'splitMode=blocksN' },
        ],
      },
    ],
  },
  {
    group: 'Bioinformática',
    ops: [{
      id: 'degen-aa',
      label: 'Secuencia AA degenerada',
      desc: 'Analiza una secuencia proteica con posiciones degeneradas, calcula todas las combinaciones posibles y genera un fichero FASTA con todas las variantes.',
      clientSide: true,
      params: [
        {
          id: 'sequence',
          type: 'textarea',
          label: 'Secuencia (pega en cualquier formato)',
          placeholder: "Con comillas:   'W','N',('N','S'),('M','I','L')\nSin comillas:    W,N,(N,S),(M,I,L)\nCompacto:        WN(NS)(MIL)K",
          rows: 5,
          default: '',
        },
        { id: 'startPos', type: 'number', label: 'Número de la posición inicial', default: 99, min: 1 },
        { id: 'maxSeqs',  type: 'number', label: 'Límite de secuencias en el FASTA', default: 10000, min: 1, max: 1000000 },
      ],
    }],
  },
];

// Flat map for quick lookup
const OPS_MAP = {};
for (const group of OPERATIONS) {
  for (const op of group.ops) OPS_MAP[op.id] = op;
}

const MAX_BYTES = 500 * 1024 * 1024; // 500 MB client-side guard

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  selectedOp: null,
  sessionId: null,
  files: [],          // File objects
  namelistFile: null, // File for op 'rename'
  fileList: [],       // Metadata for op 'inventory'
  paramValues: {},    // { [opId]: { [paramId]: value } }
  appStatus: 'idle',  // idle | uploading | running | done | error
  pollTimer: null,
  generatedVariants: null,
  clientSideBlob: null, // { blob, filename } for client-side ops
};

function getParam(opId, paramId) {
  return state.paramValues[opId]?.[paramId];
}
function setParam(opId, paramId, value) {
  if (!state.paramValues[opId]) state.paramValues[opId] = {};
  state.paramValues[opId][paramId] = value;
}

// ── DOM helpers ───────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const mk = (tag, cls, html) => {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (html !== undefined) el.innerHTML = html;
  return el;
};
function fmtSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

// ── Sidebar render ────────────────────────────────────────────────────────────
function renderSidebar() {
  const sb = $('sidebar');
  sb.innerHTML = '';
  for (const group of OPERATIONS) {
    const groupEl = mk('div', 'bw-sidebar-group');
    const label = mk('div', 'bw-sidebar-group-label', group.group);
    groupEl.appendChild(label);
    for (const op of group.ops) {
      const btn = mk('button', 'bw-op-btn' + (state.selectedOp === op.id ? ' active' : ''), op.label);
      btn.dataset.opId = op.id;
      btn.addEventListener('click', () => selectOp(op.id));
      groupEl.appendChild(btn);
    }
    sb.appendChild(groupEl);
  }
}

// ── Select operation ──────────────────────────────────────────────────────────
function selectOp(opId) {
  if (state.appStatus === 'running' || state.appStatus === 'uploading') return;

  state.selectedOp = opId;
  state.files = [];
  state.namelistFile = null;
  state.fileList = [];
  state.clientSideBlob = null;
  const prevResults = $('degen-results');
  if (prevResults) prevResults.remove();
  resetExecuteBar();

  renderSidebar();

  $('placeholder').style.display = 'none';
  const content = $('op-content');
  content.style.display = 'flex';

  const op = OPS_MAP[opId];
  $('op-title').textContent = op.label;
  $('op-desc').textContent = op.desc;

  renderUploadArea(op);
  renderParams(op);
  updateFileList();
  updateExecuteBtn();
}

// ── Upload area render ────────────────────────────────────────────────────────
function renderUploadArea(op) {
  const area = $('upload-area');
  area.innerHTML = '';

  if (op.clientSide) {
    area.style.display = 'none';
    $('file-list-wrap').style.display = 'none';
    return;
  }

  area.style.display = '';

  if (op.id === 'inventory') {
    // Single folder picker
    const drop = makeDropZone({
      label: 'Seleccionar carpeta',
      sub: 'El inventario se genera del primer nivel',
      accept: '',
      multiple: true,
      folder: true,
      onFiles: handleInventoryFiles,
    });
    area.appendChild(drop);
    $('file-list-wrap').style.display = 'none';

  } else if (op.uploadPaired) {
    // Two zones: files + namelist
    const pair = mk('div', 'bw-upload-pair');

    const dropFiles = makeDropZone({
      label: 'Ficheros a renombrar',
      sub: 'Drag & drop o clic',
      multiple: true,
      onFiles: (files) => {
        state.files = [...state.files, ...files].slice(0, 5000);
        state.files.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));
        updateFileList();
        updateExecuteBtn();
      },
    });

    const dropNames = makeDropZone({
      label: 'Lista de nombres (.txt)',
      sub: 'Un nombre por línea',
      accept: '.txt',
      multiple: false,
      onFiles: (files) => {
        if (files[0]) {
          state.namelistFile = files[0];
          const badge = dropNames.querySelector('.bw-drop-text');
          if (badge) badge.textContent = `✓ ${files[0].name}`;
        }
        updateExecuteBtn();
      },
    });

    pair.appendChild(dropFiles);
    pair.appendChild(dropNames);
    area.appendChild(pair);
    $('file-list-wrap').style.display = '';

  } else {
    // Standard single drop zone
    const drop = makeDropZone({
      label: 'Arrastrar ficheros aquí',
      sub: 'o clic para seleccionar · máx. 500 MB por lote',
      multiple: true,
      onFiles: (files) => {
        state.files = [...state.files, ...files].slice(0, 5000);
        state.files.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));
        updateFileList();
        updateExecuteBtn();
      },
    });
    area.appendChild(drop);
    $('file-list-wrap').style.display = '';
  }
}

// Traverse a FileSystemEntry tree and return plain file-metadata objects
// with a `webkitRelativePath`-equivalent `relativePath` set correctly.
async function readDroppedEntries(dataTransferItems) {
  const results = [];

  async function traverse(entry, pathPrefix) {
    if (entry.isFile) {
      await new Promise(resolve => {
        entry.file(f => {
          results.push({ name: f.name, size: f.size, type: f.type,
                         webkitRelativePath: pathPrefix + f.name });
          resolve();
        }, () => resolve());
      });
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      let batch;
      do {
        batch = await new Promise(resolve => reader.readEntries(resolve, () => resolve([])));
        for (const child of batch) await traverse(child, pathPrefix + entry.name + '/');
      } while (batch.length > 0);
    }
  }

  const entries = [...dataTransferItems]
    .map(i => i.webkitGetAsEntry && i.webkitGetAsEntry())
    .filter(Boolean);
  for (const entry of entries) await traverse(entry, '');
  return results;
}

function makeDropZone({ label, sub, accept = '', multiple = true, folder = false, onFiles }) {
  const wrap = mk('div', 'bw-drop-area');
  wrap.innerHTML = `
    <div class="bw-drop-icon">📂</div>
    <div class="bw-drop-text">${label}</div>
    <div class="bw-drop-sub">${sub}</div>
  `;

  const input = document.createElement('input');
  input.type = 'file';
  input.multiple = multiple;
  if (accept) input.accept = accept;
  if (folder) {
    input.setAttribute('webkitdirectory', '');
    input.setAttribute('mozdirectory', '');
  }
  input.addEventListener('change', () => {
    if (input.files && input.files.length > 0) onFiles([...input.files]);
    input.value = '';
  });
  wrap.appendChild(input);

  wrap.addEventListener('dragover', e => { e.preventDefault(); wrap.classList.add('drag-over'); });
  wrap.addEventListener('dragleave', () => wrap.classList.remove('drag-over'));
  wrap.addEventListener('drop', e => {
    e.preventDefault();
    wrap.classList.remove('drag-over');
    // For folder drop zones: use FileSystem Entry API to preserve folder structure
    if (folder && e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      readDroppedEntries(e.dataTransfer.items).then(entries => {
        if (entries.length > 0) onFiles(entries);
        else {
          const files = [...(e.dataTransfer.files || [])];
          if (files.length > 0) onFiles(files);
        }
      });
      return;
    }
    const files = [...(e.dataTransfer.files || [])];
    if (files.length > 0) onFiles(files);
  });

  return wrap;
}

// ── Inventory files handler ───────────────────────────────────────────────────
function handleInventoryFiles(files) {
  state.fileList = files.map(f => ({
    name: f.name,
    relativePath: f.webkitRelativePath || f.name,
    size: f.size,
    type: f.type,
  }));

  // Show a summary instead of file list
  const area = $('upload-area');
  const existing = area.querySelector('.bw-inventory-summary');
  if (existing) existing.remove();
  const summary = mk('div', 'bw-inventory-summary');
  summary.style.cssText = 'margin-top:10px;font-family:var(--mono);font-size:0.8rem;color:var(--text-muted)';
  const rootFolder = state.fileList[0]?.relativePath?.includes('/')
    ? state.fileList[0].relativePath.split('/')[0]
    : null;
  summary.textContent = rootFolder
    ? `✓ ${state.fileList.length} ficheros cargados de la carpeta "${rootFolder}"`
    : `✓ ${state.fileList.length} fichero${state.fileList.length !== 1 ? 's' : ''} cargado${state.fileList.length !== 1 ? 's' : ''}`;

  area.appendChild(summary);

  updateExecuteBtn();
}

// ── File list render ──────────────────────────────────────────────────────────
function updateFileList() {
  const files = state.files;
  const wrap = $('file-list-wrap');
  const list = $('file-list');
  const countLabel = $('file-count-label');

  if (files.length === 0) {
    list.innerHTML = '';
    countLabel.textContent = '0 ficheros';
    return;
  }

  countLabel.textContent = `${files.length} fichero${files.length !== 1 ? 's' : ''}`;

  list.innerHTML = '';
  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    const item = mk('div', 'bw-file-item');
    const name = mk('span', 'bw-file-name', f.name);
    const size = mk('span', 'bw-file-size', fmtSize(f.size));
    const rm = mk('button', 'bw-file-remove', '×');
    rm.title = 'Quitar';
    rm.dataset.idx = i;
    rm.addEventListener('click', () => {
      state.files.splice(parseInt(rm.dataset.idx), 1);
      updateFileList();
      updateExecuteBtn();
    });
    item.appendChild(name);
    item.appendChild(size);
    item.appendChild(rm);
    list.appendChild(item);
  }
}

// ── Params render ─────────────────────────────────────────────────────────────
function renderParams(op) {
  const zone = $('params-zone');
  zone.innerHTML = '';

  if (!op.params || op.params.length === 0) return;

  // Init defaults
  for (const p of op.params) {
    if (getParam(op.id, p.id) === undefined) {
      setParam(op.id, p.id, p.default ?? '');
    }
  }

  const normalParams = op.params.filter(p => !p.advanced && !p.conditional);
  const advancedParams = op.params.filter(p => p.advanced);

  const container = mk('div', 'bw-params');

  for (const p of normalParams) {
    container.appendChild(buildParamField(op.id, p));
  }

  // Conditional params (e.g. blockSize when splitMode=blocksN)
  const conditionalParams = op.params.filter(p => p.conditional && !p.advanced);
  for (const p of conditionalParams) {
    const field = buildParamField(op.id, p);
    field.dataset.conditional = p.conditional;
    container.appendChild(field);
  }

  if (advancedParams.length > 0) {
    const toggleBtn = mk('button', 'bw-advanced-toggle', 'Mostrar opciones avanzadas');
    const advWrap = mk('div', 'bw-advanced-fields');
    advWrap.style.display = 'none';
    toggleBtn.addEventListener('click', () => {
      const open = advWrap.style.display !== 'none';
      advWrap.style.display = open ? 'none' : '';
      toggleBtn.textContent = open ? 'Mostrar opciones avanzadas' : 'Ocultar opciones avanzadas';
    });
    for (const p of advancedParams) advWrap.appendChild(buildParamField(op.id, p));
    container.appendChild(toggleBtn);
    container.appendChild(advWrap);
  }

  zone.appendChild(container);
  refreshConditionalFields(op.id);
}

function buildParamField(opId, p) {
  const field = mk('div', 'bw-field');
  field.dataset.paramId = p.id;

  const label = mk('label', null, p.label);
  label.htmlFor = `param-${opId}-${p.id}`;
  field.appendChild(label);

  if (p.type === 'checkbox') {
    const wrap = mk('label', 'bw-checkbox-wrap');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.id = `param-${opId}-${p.id}`;
    input.checked = getParam(opId, p.id) !== false;
    input.addEventListener('change', () => {
      setParam(opId, p.id, input.checked);
      updateExecuteBtn();
    });
    wrap.appendChild(input);
    wrap.appendChild(mk('span', null, p.label));
    // Replace label + wrap structure
    field.innerHTML = '';
    field.appendChild(wrap);

  } else if (p.type === 'range') {
    const wrap = mk('div', 'bw-range-wrap');
    const input = document.createElement('input');
    input.type = 'range';
    input.className = 'bw-range';
    input.id = `param-${opId}-${p.id}`;
    input.min = p.min ?? 0;
    input.max = p.max ?? 100;
    input.value = getParam(opId, p.id) ?? p.default;
    const valueDisplay = mk('span', 'bw-range-value', input.value);
    input.addEventListener('input', () => {
      valueDisplay.textContent = input.value;
      setParam(opId, p.id, parseInt(input.value));
    });
    wrap.appendChild(input);
    wrap.appendChild(valueDisplay);
    field.appendChild(wrap);

  } else if (p.type === 'select') {
    const select = document.createElement('select');
    select.className = 'bw-select';
    select.id = `param-${opId}-${p.id}`;
    for (const opt of (p.options || [])) {
      const o = document.createElement('option');
      o.value = opt.value;
      o.textContent = opt.label;
      if ((getParam(opId, p.id) ?? p.default) === opt.value) o.selected = true;
      select.appendChild(o);
    }
    select.addEventListener('change', () => {
      setParam(opId, p.id, select.value);
      refreshConditionalFields(opId);
      updateExecuteBtn();
    });
    field.appendChild(select);

  } else if (p.type === 'number') {
    const input = document.createElement('input');
    input.type = 'number';
    input.className = 'bw-input';
    input.id = `param-${opId}-${p.id}`;
    input.value = getParam(opId, p.id) ?? p.default ?? '';
    if (p.min !== undefined) input.min = p.min;
    input.addEventListener('input', () => {
      setParam(opId, p.id, input.value === '' ? '' : parseFloat(input.value));
      updateExecuteBtn();
    });
    field.appendChild(input);

  } else if (p.type === 'textarea') {
    const ta = document.createElement('textarea');
    ta.className = 'bw-input bw-textarea';
    ta.id = `param-${opId}-${p.id}`;
    ta.value = getParam(opId, p.id) ?? p.default ?? '';
    if (p.placeholder) ta.placeholder = p.placeholder;
    if (p.rows) ta.rows = p.rows;
    ta.addEventListener('input', () => {
      setParam(opId, p.id, ta.value);
      updateExecuteBtn();
    });
    field.appendChild(ta);

  } else {
    // text
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'bw-input';
    input.id = `param-${opId}-${p.id}`;
    input.value = getParam(opId, p.id) ?? p.default ?? '';
    input.addEventListener('input', () => {
      setParam(opId, p.id, input.value);
      updateExecuteBtn();
    });
    field.appendChild(input);
  }

  return field;
}

function refreshConditionalFields(opId) {
  const zone = $('params-zone');
  if (!zone) return;
  const fields = zone.querySelectorAll('[data-conditional]');
  fields.forEach(field => {
    const cond = field.dataset.conditional; // e.g. "splitMode=blocksN"
    const [condParamId, condValue] = cond.split('=');
    const currentVal = getParam(opId, condParamId);
    field.style.display = (currentVal === condValue) ? '' : 'none';
  });
}

// ── Execute bar state ─────────────────────────────────────────────────────────
function resetExecuteBar() {
  clearPoll();
  state.appStatus = 'idle';
  state.sessionId = null;
  $('btn-execute').disabled = true;
  $('btn-execute').style.display = '';
  $('btn-download').style.display = 'none';
  $('status-msg').textContent = '';
  $('status-msg').className = 'bw-status-msg';
  $('progress-wrap').classList.remove('visible');
  $('progress-fill').style.width = '0%';
  $('progress-label').textContent = '';
  $('log-panel').innerHTML = '';
  $('log-panel').classList.remove('visible');
}

function updateExecuteBtn() {
  if (!state.selectedOp) return;
  const op = OPS_MAP[state.selectedOp];
  let ready = false;

  if (op.clientSide) {
    const seq = (getParam(op.id, 'sequence') || '').trim();
    ready = seq.length > 0;
    if (!ready) setStatus('Introduce una secuencia para continuar', '');
    else setStatus('', '');
  } else if (op.id === 'inventory') {
    ready = state.fileList.length > 0;
    if (!ready) setStatus('Selecciona una carpeta para continuar', '');
    else setStatus('', '');
  } else if (op.uploadPaired) {
    const hasFiles = state.files.length > 0;
    const hasNames = state.namelistFile !== null;
    ready = hasFiles && hasNames;
    if (!hasFiles && !hasNames) setStatus('Carga los ficheros y el .txt con los nombres nuevos', '');
    else if (!hasFiles)         setStatus('Falta: arrastra los ficheros a renombrar', '');
    else if (!hasNames)         setStatus('Falta: arrastra el .txt con los nombres nuevos', '');
    else                        setStatus('', '');
  } else {
    ready = state.files.length > 0;
    if (!ready) setStatus('Arrastra los ficheros para continuar', '');
    else setStatus('', '');
  }

  // Check total size
  const totalBytes = state.files.reduce((s, f) => s + f.size, 0);
  if (totalBytes > MAX_BYTES) {
    setStatus(`El lote supera el límite de 500 MB (${fmtSize(totalBytes)})`, 'err');
    ready = false;
  }

  $('btn-execute').disabled = !ready || state.appStatus !== 'idle';
}

function setStatus(msg, cls = '') {
  const el = $('status-msg');
  el.textContent = msg;
  el.className = 'bw-status-msg' + (cls ? ' ' + cls : '');
}

function setProgress(current, total, message) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  $('progress-fill').style.width = pct + '%';
  $('progress-label').textContent = message || (total > 0 ? `${current} / ${total}` : '');
  $('progress-wrap').classList.add('visible');
}

function addLog(entry) {
  const el = $('log-panel');
  el.classList.add('visible');
  const line = mk('div', `bw-log-entry ${entry.type}`,
    entry.file ? `[${entry.file}] ${entry.message}` : entry.message);
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

// ── Execute flow ──────────────────────────────────────────────────────────────
$('btn-execute').addEventListener('click', startExecution);
$('btn-clear-files').addEventListener('click', () => {
  state.files = [];
  updateFileList();
  updateExecuteBtn();
});
$('btn-download').addEventListener('click', downloadResult);

async function startExecution() {
  if (!state.selectedOp) return;
  const op = OPS_MAP[state.selectedOp];

  if (op.clientSide) {
    runClientSideOp(op);
    return;
  }

  $('btn-execute').disabled = true;
  $('btn-download').style.display = 'none';
  $('log-panel').innerHTML = '';
  $('log-panel').classList.remove('visible');
  state.appStatus = 'uploading';
  setStatus('Creando sesión...');
  setProgress(0, 1, 'Iniciando...');

  try {
    // 1. Create session
    const sessRes = await fetch('/batchwork/api/session', { method: 'POST' });
    if (!sessRes.ok) throw new Error('Error al crear sesión');
    const { id } = await sessRes.json();
    state.sessionId = id;

    // 2. Upload files (skip for inventory — send metadata inline)
    if (op.id !== 'inventory') {
      setStatus('Subiendo ficheros...');
      await uploadFiles(id, op);
    }

    // 3. Execute
    state.appStatus = 'running';
    setStatus('Ejecutando...');

    const execBody = {
      operation: op.id,
      params: buildParams(op),
    };

    // For inventory, include fileList in params
    if (op.id === 'inventory') {
      execBody.params.fileList = state.fileList;
    }

    const execRes = await fetch(`/batchwork/api/session/${id}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(execBody),
    });
    if (!execRes.ok) {
      const err = await execRes.json();
      throw new Error(err.error || 'Error al ejecutar la operación');
    }

    // 4. Poll status
    startPoll(id);

  } catch (err) {
    state.appStatus = 'error';
    setStatus(err.message, 'err');
    $('btn-execute').disabled = false;
    clearPoll();
  }
}

async function uploadFiles(sessionId, op) {
  const formData = new FormData();

  for (const f of state.files) formData.append('files', f, f.name);
  if (op.uploadPaired && state.namelistFile) {
    formData.append('nameList', state.namelistFile, state.namelistFile.name);
  }

  const res = await fetch(`/batchwork/api/session/${sessionId}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Error al subir ficheros (${res.status})`);
  }
  return res.json();
}

function buildParams(op) {
  const params = {};
  for (const p of (op.params || [])) {
    params[p.id] = getParam(op.id, p.id) ?? p.default ?? '';
  }
  return params;
}

// ── Status polling ────────────────────────────────────────────────────────────
function startPoll(sessionId) {
  clearPoll();
  state.pollTimer = setInterval(() => pollStatus(sessionId), 600);
}

function clearPoll() {
  if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
}

async function pollStatus(sessionId) {
  try {
    const res = await fetch(`/batchwork/api/session/${sessionId}/status`);
    if (!res.ok) return;
    const data = await res.json();

    // Update progress
    if (data.progress && (data.progress.total > 0 || data.progress.message)) {
      setProgress(data.progress.current, data.progress.total, data.progress.message);
    }

    // Update log (show new entries)
    const logEl = $('log-panel');
    const existingCount = logEl.querySelectorAll('.bw-log-entry').length;
    if (data.log && data.log.length > existingCount) {
      for (let i = existingCount; i < data.log.length; i++) addLog(data.log[i]);
    }

    if (data.status === 'done') {
      clearPoll();
      state.appStatus = 'done';
      setStatus(`✓ Completado: ${data.resultFilename || 'resultado listo'}`, 'ok');
      setProgress(data.progress?.total || 1, data.progress?.total || 1, 'Completado');
      $('btn-execute').style.display = 'none';
      $('btn-download').style.display = '';

    } else if (data.status === 'error') {
      clearPoll();
      state.appStatus = 'error';
      const errMsg = data.log?.find(l => l.type === 'error')?.message || 'Error desconocido';
      setStatus(`Error: ${errMsg}`, 'err');
      $('btn-execute').disabled = false;

    } else if (data.status === 'awaiting_user') {
      clearPoll();
      showAwaitingDialog(sessionId, data.awaitingData);
    }
  } catch (e) {
    // network glitch, keep polling
  }
}

// ── Download ──────────────────────────────────────────────────────────────────
async function downloadResult() {
  if (state.clientSideBlob) {
    const { blob, filename } = state.clientSideBlob;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    return;
  }

  if (!state.sessionId) return;
  window.location.href = `/batchwork/api/session/${state.sessionId}/download`;
  // Allow a fresh execution after download
  setTimeout(() => {
    state.appStatus = 'idle';
    state.sessionId = null;
    $('btn-execute').style.display = '';
    $('btn-download').style.display = 'none';
    $('btn-execute').disabled = false;
    updateExecuteBtn();
  }, 2000);
}

// ── Awaiting user dialogs ─────────────────────────────────────────────────────
function showAwaitingDialog(sessionId, awaitingData) {
  if (!awaitingData) return;

  const overlay = $('overlay');
  const title = $('dialog-title');
  const body = $('dialog-body');
  const detail = $('dialog-detail');
  const actions = $('dialog-actions');

  actions.innerHTML = '';
  detail.style.display = 'none';

  async function resolve(decision) {
    overlay.classList.remove('open');
    state.appStatus = 'running';
    setStatus('Reanudando...');

    await fetch(`/batchwork/api/session/${sessionId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(decision),
    });

    startPoll(sessionId);
  }

  function addBtn(label, cls, onClick) {
    const btn = mk('button', `bw-btn ${cls}`, label);
    btn.addEventListener('click', onClick);
    actions.appendChild(btn);
  }

  if (awaitingData.type === 'mismatch') {
    title.textContent = 'Desajuste entre ficheros y nombres';
    body.innerHTML = `Hay <strong>${awaitingData.fileCount}</strong> fichero(s) pero <strong>${awaitingData.nameCount}</strong> nombre(s) en la lista.<br>¿Qué deseas hacer?`;
    detail.style.display = '';
    detail.textContent = `Ficheros: ${awaitingData.files.slice(0, 10).join(', ')}${awaitingData.files.length > 10 ? '…' : ''}`;

    addBtn('Cancelar', 'bw-btn-cancel', () => resolve('cancel'));
    addBtn(`Renombrar los ${Math.min(awaitingData.fileCount, awaitingData.nameCount)} emparejables`, 'bw-btn-execute', () => resolve('partial'));

  } else if (awaitingData.type === 'collision') {
    title.textContent = 'Colisión de identificadores';
    body.textContent = 'Se han encontrado ficheros distintos con el mismo identificador:';
    detail.style.display = '';
    detail.innerHTML = awaitingData.collisions
      .map(c => `<b>${c.id}</b>: ${c.files.join(', ')}`)
      .join('<br>');

    addBtn('Cancelar', 'bw-btn-cancel', () => resolve({ action: 'cancel' }));
    addBtn('Quedarse con el primero (alfabético)', 'bw-btn-cancel', () => resolve({ action: 'first' }));
    addBtn('Añadir sufijo numérico', 'bw-btn-execute', () => resolve({ action: 'suffix' }));

  } else if (awaitingData.type === 'page_mismatch') {
    title.textContent = 'PDFs con número de páginas inesperado';
    body.innerHTML = `Se esperaban <strong>${awaitingData.expected}</strong> páginas, pero estos ficheros difieren:`;
    detail.style.display = '';
    detail.innerHTML = awaitingData.invalid
      .map(i => `${i.file} (${i.pages} pág.)`)
      .join('<br>');

    addBtn('Cancelar', 'bw-btn-cancel', () => resolve('cancel'));
    addBtn('Continuar solo con los válidos', 'bw-btn-execute', () => resolve('continue'));
  }

  overlay.classList.add('open');
}

// Close dialog on overlay click
$('overlay').addEventListener('click', e => {
  if (e.target === $('overlay')) $('overlay').classList.remove('open');
});

// ── Degenerate AA (client-side) ───────────────────────────────────────────────

function parseAASequence(rawInput) {
  const trimmed = rawInput.trim();

  // Python-style list-of-lists: [['W'], ['N', 'S'], ...]
  if (trimmed.startsWith('[')) {
    try {
      const jsonStr = trimmed.replace(/'/g, '"');
      const parsed = JSON.parse(jsonStr);
      if (Array.isArray(parsed) && parsed.every(p => Array.isArray(p))) {
        const positions = parsed
          .map(p => p.map(aa => String(aa).toUpperCase().trim()).filter(aa => aa.length > 0))
          .filter(p => p.length > 0);
        if (positions.length > 0) return positions;
      }
    } catch (e) {
      // fall through to character parser
    }
  }

  let clean = trimmed.replace(/['"`]/g, '');
  const positions = [];
  let i = 0;

  while (i < clean.length) {
    if (clean[i] === '(') {
      const close = clean.indexOf(')', i);
      if (close === -1) { i++; continue; }
      const inner = clean.slice(i + 1, close).replace(/\s/g, '');
      let aas;
      if (inner.includes(',')) {
        aas = inner.split(',').map(s => s.toUpperCase()).filter(s => s.length > 0);
      } else {
        aas = inner.toUpperCase().split('').filter(c => /[A-Z*]/.test(c));
      }
      if (aas.length > 0) positions.push(aas);
      i = close + 1;
      while (i < clean.length && /[,\s]/.test(clean[i])) i++;

    } else if (/[,\s]/.test(clean[i])) {
      i++;

    } else if (/[A-Za-z*]/.test(clean[i])) {
      let j = i;
      while (j < clean.length && /[A-Za-z*]/.test(clean[j])) j++;
      const chunk = clean.slice(i, j).toUpperCase();
      i = j;
      while (i < clean.length && /[,\s]/.test(clean[i])) i++;
      if (chunk.length === 1) {
        positions.push([chunk]);
      } else {
        for (const c of chunk) positions.push([c]);
      }

    } else {
      i++;
    }
  }

  return positions;
}

function countCombinations(positions) {
  return positions.reduce((acc, pos) => acc * pos.length, 1);
}

function generateAllVariants(positions, maxSeqs) {
  let results = [''];
  for (const pos of positions) {
    const next = [];
    outer: for (const seq of results) {
      for (const aa of pos) {
        next.push(seq + aa);
        if (next.length >= maxSeqs) break outer;
      }
    }
    results = next;
    if (results.length >= maxSeqs) break;
  }
  return results;
}

function buildFASTABlob(variants, startPos, seqLen) {
  const end = startPos + seqLen - 1;
  const lines = [];
  for (let i = 0; i < variants.length; i++) {
    lines.push(`>variant_${i + 1} pos${startPos}-${end}`);
    lines.push(variants[i]);
  }
  return new Blob([lines.join('\n') + '\n'], { type: 'text/plain' });
}

function renderDegenAnalysis(positions, startPos, degenCount, totalCombinations, maxSeqs) {
  const existing = $('degen-results');
  if (existing) existing.remove();

  const root = mk('div', 'degen-results');
  root.id = 'degen-results';

  // Summary
  const primarySeq = positions.map(p => p[0]).join('');
  const summary = mk('div', 'degen-summary');
  summary.innerHTML = `La secuencia <code class="degen-seq-code">${primarySeq}</code> presenta <strong>${degenCount} posición${degenCount !== 1 ? 'es' : ''} degenerada${degenCount !== 1 ? 's' : ''}</strong>`;
  root.appendChild(summary);

  // Sequence viewer
  const viewer = mk('div', 'degen-viewer');
  const numRow = mk('div', 'degen-row degen-row--nums');
  const aaRow  = mk('div', 'degen-row degen-row--aa');
  const altRow = mk('div', 'degen-row degen-row--alts');

  for (let i = 0; i < positions.length; i++) {
    const pos = positions[i];
    const isDegen = pos.length > 1;
    const posNum = startPos + i;
    const degenCls = isDegen ? ' degen-cell--degen' : '';

    numRow.appendChild(mk('div', 'degen-cell' + degenCls, String(posNum)));
    aaRow.appendChild(mk('div', 'degen-cell degen-cell--aa' + degenCls, pos[0]));
    altRow.appendChild(mk('div', 'degen-cell degen-cell--alt' + degenCls, isDegen ? pos.join('/') : ''));
  }

  viewer.appendChild(numRow);
  viewer.appendChild(aaRow);
  viewer.appendChild(altRow);
  root.appendChild(viewer);

  // Stats
  const stats = mk('div', 'degen-stats');
  const comboStr = totalCombinations > 1e9
    ? totalCombinations.toExponential(2)
    : totalCombinations.toLocaleString('es-ES');

  const mkStat = (val, lbl) => {
    const s = mk('div', 'degen-stat');
    s.innerHTML = `<span class="degen-stat-val">${val}</span><span class="degen-stat-lbl">${lbl}</span>`;
    return s;
  };
  stats.appendChild(mkStat(positions.length, 'posiciones<br>en total'));
  stats.appendChild(mkStat(degenCount, 'posiciones<br>degeneradas'));
  stats.appendChild(mkStat(comboStr, 'combinaciones<br>posibles'));
  root.appendChild(stats);

  if (totalCombinations > maxSeqs) {
    const warn = mk('div', 'degen-warn');
    warn.innerHTML = `⚠ El FASTA incluirá solo las primeras <strong>${maxSeqs.toLocaleString('es-ES')}</strong> de <strong>${comboStr}</strong> variantes. Aumenta el límite para obtener más.`;
    root.appendChild(warn);
  }

  renderClusterSection(root);

  const paramsZone = $('params-zone');
  paramsZone.parentNode.insertBefore(root, paramsZone.nextSibling);
}

async function runClientSideOp(op) {
  $('btn-execute').disabled = true;
  $('btn-download').style.display = 'none';
  $('log-panel').innerHTML = '';
  $('log-panel').classList.remove('visible');
  $('progress-wrap').classList.remove('visible');
  state.appStatus = 'running';
  setStatus('Procesando...');

  const existing = $('degen-results');
  if (existing) existing.remove();
  state.clientSideBlob = null;

  try {
    const rawSeq   = (getParam(op.id, 'sequence') || '').trim();
    const startPos = Math.max(1, parseInt(getParam(op.id, 'startPos') ?? 99) || 99);
    const maxSeqs  = Math.max(1, parseInt(getParam(op.id, 'maxSeqs')  ?? 10000) || 10000);

    const positions = parseAASequence(rawSeq);
    if (positions.length === 0) throw new Error('No se pudo parsear la secuencia. Comprueba el formato.');

    const degenCount        = positions.filter(p => p.length > 1).length;
    const totalCombinations = countCombinations(positions);

    const variants = generateAllVariants(positions, maxSeqs);
    state.generatedVariants = variants;

    state.clientSideBlob = {
      blob: buildFASTABlob(variants, startPos, positions.length),
      filename: `variantes-aa-${new Date().toISOString().slice(0, 10)}.fasta`,
    };

    renderDegenAnalysis(positions, startPos, degenCount, totalCombinations, maxSeqs);

    state.appStatus = 'done';
    const limitNote = totalCombinations > maxSeqs ? ` (FASTA: ${maxSeqs.toLocaleString('es-ES')} variantes)` : '';
    setStatus(`✓ ${degenCount} posición${degenCount !== 1 ? 'es' : ''} degenerada${degenCount !== 1 ? 's' : ''} · ${totalCombinations.toLocaleString('es-ES')} combinaciones${limitNote}`, 'ok');
    $('btn-execute').style.display = 'none';
    $('btn-download').style.display = '';

  } catch (err) {
    state.appStatus = 'error';
    setStatus(err.message, 'err');
    $('btn-execute').disabled = false;
  }
}

// ── Clustering helpers ────────────────────────────────────────────────────────

function parseFASTA(text) {
  const seqs = [];
  let id = null, seq = '';
  for (const line of text.split('\n')) {
    const l = line.trim();
    if (!l) continue;
    if (l.startsWith('>')) {
      if (id !== null && seq) seqs.push({ id, seq });
      id = l.slice(1).trim();
      seq = '';
    } else if (id !== null) {
      seq += l.toUpperCase().replace(/[^A-Z*]/g, '');
    }
  }
  if (id !== null && seq) seqs.push({ id, seq });
  return seqs;
}

function hammingDist(a, b) {
  let d = 0;
  const len = Math.min(a.length, b.length);
  for (let i = 0; i < len; i++) if (a[i] !== b[i]) d++;
  return d + Math.abs(a.length - b.length);
}

// Jalview PID distance: d_ij = 100 - PID_ij  (range 0–100)
function pidDist(a, b) {
  const compared = Math.max(a.length, b.length);
  if (compared === 0) return 0;
  let identical = 0;
  const len = Math.min(a.length, b.length);
  for (let i = 0; i < len; i++) if (a[i] === b[i]) identical++;
  return 100 - (identical / compared) * 100;
}

function filterByN(variants, prions, minN) {
  const passing = [];
  for (let i = 0; i < variants.length; i++) {
    let ok = true;
    for (const p of prions) {
      if (hammingDist(variants[i], p.seq) < minN) { ok = false; break; }
    }
    if (ok) passing.push({ idx: i, seq: variants[i] });
  }
  return passing;
}

const MAX_CLUSTER_SEQS = 800;

function upgmaCluster(seqs, nClusters) {
  const n = seqs.length;
  const k = Math.min(nClusters, n);
  if (n <= k) return seqs.map((_, i) => ({ medoid: i, members: [i] }));

  // Build distance matrix
  const D = Array.from({ length: n }, () => new Float32Array(n));
  for (let i = 0; i < n; i++)
    for (let j = i + 1; j < n; j++)
      D[i][j] = D[j][i] = pidDist(seqs[i], seqs[j]);

  // UPGMA with active set
  const avg = Array.from({ length: n }, (_, i) => Float32Array.from(D[i]));
  const size = new Int32Array(n).fill(1);
  const members = Array.from({ length: n }, (_, i) => [i]);
  const active = new Set(Array.from({ length: n }, (_, i) => i));

  for (let step = 0; step < n - k; step++) {
    let minVal = Infinity, minI = -1, minJ = -1;
    const arr = [...active];
    for (let a = 0; a < arr.length; a++) {
      for (let b = a + 1; b < arr.length; b++) {
        if (avg[arr[a]][arr[b]] < minVal) {
          minVal = avg[arr[a]][arr[b]]; minI = arr[a]; minJ = arr[b];
        }
      }
    }
    const sI = size[minI], sJ = size[minJ];
    for (const kk of active) {
      if (kk === minI || kk === minJ) continue;
      const d = (avg[minI][kk] * sI + avg[minJ][kk] * sJ) / (sI + sJ);
      avg[minI][kk] = avg[kk][minI] = d;
    }
    size[minI] = sI + sJ;
    members[minI] = [...members[minI], ...members[minJ]];
    active.delete(minJ);
  }

  const result = [];
  for (const rep of active) {
    const mems = members[rep];
    let bestMedoid = mems[0], bestAvg = Infinity;
    for (const m of mems) {
      let sum = 0;
      for (const other of mems) sum += D[m][other];
      const a = sum / mems.length;
      if (a < bestAvg) { bestAvg = a; bestMedoid = m; }
    }
    result.push({ medoid: bestMedoid, members: mems });
  }
  result.sort((a, b) => a.medoid - b.medoid);
  return result;
}

function renderClusterSection(root) {
  const section = mk('div', 'degen-cluster-section');

  const hdr = mk('div', 'degen-cluster-hdr');
  hdr.innerHTML = '<span class="degen-cluster-title">Filtro + Clusterización</span><span class="degen-cluster-sub">vs. priones naturales · UPGMA</span>';
  section.appendChild(hdr);

  const f1 = mk('div', 'bw-field');
  const l1 = mk('label', null, 'Priones naturales (FASTA)');
  const ta = document.createElement('textarea');
  ta.className = 'bw-input bw-textarea';
  ta.id = 'degen-prions-input';
  ta.rows = 5;
  ta.placeholder = '>natural_prion_1\nAMKLPS...\n>natural_prion_2\nWNKPS...';
  f1.appendChild(l1);
  f1.appendChild(ta);
  section.appendChild(f1);

  const row = mk('div', 'degen-cluster-row');

  const f2 = mk('div', 'bw-field');
  f2.appendChild(mk('label', null, 'N mínimo de mutaciones'));
  const nInput = document.createElement('input');
  nInput.type = 'number'; nInput.className = 'bw-input'; nInput.id = 'degen-min-n';
  nInput.value = '17'; nInput.min = '1'; nInput.max = '999';
  f2.appendChild(nInput);

  const f3 = mk('div', 'bw-field');
  f3.appendChild(mk('label', null, 'Número de clusters'));
  const cInput = document.createElement('input');
  cInput.type = 'number'; cInput.className = 'bw-input'; cInput.id = 'degen-num-clusters';
  cInput.value = '10'; cInput.min = '1'; cInput.max = '500';
  f3.appendChild(cInput);

  row.appendChild(f2);
  row.appendChild(f3);
  section.appendChild(row);

  const btn = mk('button', 'bw-btn bw-btn-cluster', 'Clusterizar');
  btn.addEventListener('click', () => runClustering(btn));
  section.appendChild(btn);

  const resultsDiv = mk('div', '');
  resultsDiv.id = 'degen-cluster-results';
  section.appendChild(resultsDiv);

  root.appendChild(section);
}

async function runClustering(btn) {
  const prionsText = ($('degen-prions-input')?.value || '').trim();
  const minN = Math.max(1, parseInt($('degen-min-n')?.value || '17') || 17);
  const numClusters = Math.max(1, parseInt($('degen-num-clusters')?.value || '10') || 10);
  const resultsDiv = $('degen-cluster-results');
  if (!resultsDiv) return;

  if (!state.generatedVariants || state.generatedVariants.length === 0) {
    resultsDiv.innerHTML = '<div class="degen-cerr">Primero genera las variantes con "Analizar".</div>';
    return;
  }
  if (!prionsText) {
    resultsDiv.innerHTML = '<div class="degen-cerr">Pega las secuencias de priones naturales en formato FASTA.</div>';
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Filtrando...';
  resultsDiv.innerHTML = '<div class="degen-cloading">⏳ Filtrando variantes vs. priones naturales…</div>';
  await new Promise(r => setTimeout(r, 15));

  try {
    const prions = parseFASTA(prionsText);
    if (prions.length === 0) throw new Error('No se encontraron secuencias FASTA válidas.');

    const filtered = filterByN(state.generatedVariants, prions, minN);

    if (filtered.length === 0) {
      resultsDiv.innerHTML = `<div class="degen-cempty">Ninguna variante supera N≥${minN} contra ${prions.length} prión${prions.length !== 1 ? 'es' : ''} natural${prions.length !== 1 ? 'es' : ''}.</div>`;
      return;
    }

    let clusterInput = filtered;
    let sampled = false;
    if (filtered.length > MAX_CLUSTER_SEQS) {
      const step = filtered.length / MAX_CLUSTER_SEQS;
      clusterInput = Array.from({ length: MAX_CLUSTER_SEQS }, (_, i) => filtered[Math.floor(i * step)]);
      sampled = true;
    }

    btn.textContent = 'Calculando distancias…';
    resultsDiv.innerHTML = '<div class="degen-cloading">⏳ Calculando matrix de distancias…</div>';
    await new Promise(r => setTimeout(r, 15));

    const clusters = upgmaCluster(clusterInput.map(v => v.seq), numClusters);

    renderClusterResults(resultsDiv, { prions, minN, filtered, clusterInput, sampled, clusters });

  } catch (err) {
    resultsDiv.innerHTML = `<div class="degen-cerr">Error: ${err.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Clusterizar';
  }
}

function renderClusterResults(container, { prions, minN, filtered, clusterInput, sampled, clusters }) {
  container.innerHTML = '';

  const banner = mk('div', 'degen-cbanner');
  banner.innerHTML = `<strong>${filtered.length.toLocaleString('es-ES')}</strong> variante${filtered.length !== 1 ? 's' : ''} pasan N≥${minN} de ${prions.length} prión${prions.length !== 1 ? 'es' : ''} natural${prions.length !== 1 ? 'es' : ''}`;
  container.appendChild(banner);

  if (sampled) {
    const w = mk('div', 'degen-cwarn');
    w.innerHTML = `⚠ Clustering sobre muestra de <strong>${clusterInput.length}</strong> de ${filtered.length.toLocaleString('es-ES')} variantes filtradas (límite del navegador).`;
    container.appendChild(w);
  }

  const lhdr = mk('div', 'degen-clist-hdr');
  lhdr.textContent = `${clusters.length} cluster${clusters.length !== 1 ? 's' : ''} — centroides (medoides):`;
  container.appendChild(lhdr);

  const list = mk('div', 'degen-clist');
  const ids = [];
  for (let i = 0; i < clusters.length; i++) {
    const c = clusters[i];
    const v = clusterInput[c.medoid];
    const variantId = `variant_${v.idx + 1}`;
    ids.push(variantId);

    const item = mk('div', 'degen-citem');
    item.innerHTML =
      `<span class="degen-citem-cluster">C${String(i + 1).padStart(2, '0')}</span>` +
      `<code class="degen-citem-seq">${v.seq}</code>` +
      `<span class="degen-citem-id">${variantId}</span>` +
      `<span class="degen-citem-size">${c.members.length} seq.</span>`;
    list.appendChild(item);
  }
  container.appendChild(list);

  const copyBtn = mk('button', 'bw-btn bw-btn-cancel degen-copy-btn', '📋 Copiar IDs de centroides');
  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(ids.join('\n')).then(() => {
      copyBtn.textContent = '✓ Copiado';
      setTimeout(() => { copyBtn.innerHTML = '📋 Copiar IDs de centroides'; }, 2000);
    });
  });
  container.appendChild(copyBtn);
}

// ── Init ──────────────────────────────────────────────────────────────────────
renderSidebar();
