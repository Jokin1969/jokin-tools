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
    },
    {
      id: 'plddt-kde',
      label: 'Distribución pLDDT (KDE)',
      desc: 'Parsea valores pLDDT en formato bruto, calcula una distribución KDE normalizada y genera una gráfica exportable en Excel, PNG y TIFF a 300 DPI.',
      clientSide: true,
      params: [],
    },
    {
      id: 'mutagen-tree',
      label: 'Árbol de mutagénesis',
      desc: 'Compara secuencias derivadas frente a una original y calcula la ruta de síntesis más barata. Las mutaciones que caen dentro de una misma ventana de N nucleótidos cuentan como un único cambio (lo que la empresa factura como un cambio), de modo que algunas secuencias se sintetizan a partir de otras para abaratar el pedido.',
      clientSide: true,
      params: [],
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
  const prevPlddt = $('plddt-results');
  if (prevPlddt) prevPlddt.remove();
  const prevMutagen = $('mutagen-results');
  if (prevMutagen) prevMutagen.remove();
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

  if (op.id === 'plddt-kde') { renderPlddtGroupsUI(); return; }
  if (op.id === 'mutagen-tree') { renderMutagenUI(); return; }

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
    if (op.id === 'plddt-kde') {
      ready = plddtGroups.some(g => g.raw.trim().length > 0);
      if (!ready) setStatus('Introduce datos en al menos un grupo', '');
      else setStatus('', '');
    } else if (op.id === 'mutagen-tree') {
      const hasOrig = mutagenInput.original.trim().length > 0;
      const hasList = mutagenInput.list.trim().length > 0;
      ready = hasOrig && hasList;
      if (!hasOrig && !hasList) setStatus('Introduce la secuencia original y el listado de derivadas', '');
      else if (!hasOrig)        setStatus('Falta: la secuencia original', '');
      else if (!hasList)        setStatus('Falta: el listado de secuencias derivadas', '');
      else setStatus('', '');
    } else {
      const mainParam = op.params.find(p => p.type === 'textarea');
      const val = mainParam ? (getParam(op.id, mainParam.id) || '').trim() : '';
      ready = val.length > 0;
      if (!ready) setStatus('Introduce los datos para continuar', '');
      else setStatus('', '');
    }
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

// ── AA biochemical properties ────────────────────────────────────────────────
const AA_PROPS = {
  A:'hydrophobic',V:'hydrophobic',L:'hydrophobic',I:'hydrophobic',
  P:'hydrophobic',F:'hydrophobic',M:'hydrophobic',W:'hydrophobic',
  S:'polar',T:'polar',C:'polar',Y:'polar',N:'polar',Q:'polar',
  K:'positive',R:'positive',H:'positive',
  D:'negative',E:'negative',G:'special',
};
const PROP_COLORS = {
  hydrophobic:'#D4820A', polar:'#2A9D8F',
  positive:'#3A70C8',   negative:'#C83A3A', special:'#8B5CF6',
};
const PROP_LABELS = {
  hydrophobic:'Hidrofóbico', polar:'Polar',
  positive:'Básico',        negative:'Ácido',  special:'Glicina',
};
const AA_ORDER = ['A','V','L','I','P','F','M','W','S','T','C','Y','N','Q','K','R','H','D','E','G'];
function aaProp(aa) { return AA_PROPS[(aa || '').toUpperCase()] || 'special'; }

// ── Degen viz modal ──────────────────────────────────────────────────────────
function openDegenViz(title, renderFn) {
  const prev = document.getElementById('degen-viz-modal');
  if (prev) prev.remove();
  const modal = document.createElement('div');
  modal.id = 'degen-viz-modal'; modal.className = 'degen-viz-modal';
  const inner = document.createElement('div'); inner.className = 'degen-viz-inner';
  const hdr = document.createElement('div'); hdr.className = 'degen-viz-hdr';
  const titleEl = document.createElement('div'); titleEl.className = 'degen-viz-title';
  titleEl.textContent = title;
  const closeBtn = document.createElement('button'); closeBtn.className = 'degen-viz-close';
  closeBtn.textContent = '✕';
  closeBtn.addEventListener('click', () => modal.remove());
  hdr.appendChild(titleEl); hdr.appendChild(closeBtn);
  const body = document.createElement('div'); body.className = 'degen-viz-body';
  inner.appendChild(hdr); inner.appendChild(body);
  modal.appendChild(inner); document.body.appendChild(modal);
  modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  const esc = e => { if (e.key === 'Escape') { modal.remove(); document.removeEventListener('keydown', esc); } };
  document.addEventListener('keydown', esc);
  renderFn(body);
}

// ── Viz 1: Retrato de Secuencia (SVG puro) ───────────────────────────────────
function renderDegenSeqMap(container, positions, startPos) {
  const CELL = 24, GAP = 3, COLS = 40;
  const TICK_H = 14, ALT_H = 12;
  const ROW_H = TICK_H + CELL + ALT_H + GAP;
  const nRows = Math.ceil(positions.length / COLS);
  const nCols = Math.min(positions.length, COLS);
  const PL = 14, PT = 52, PR = 14, PB = 58;
  const W = PL + nCols * (CELL + GAP) - GAP + PR;
  const H = PT + nRows * ROW_H + PB;
  const NS = 'http://www.w3.org/2000/svg';

  const svgEl = (tag, attrs, parent) => {
    const el = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    if (parent) parent.appendChild(el);
    return el;
  };
  const svgTxt = (x, y, txt, attrs, parent) => {
    const el = svgEl('text', { x, y, 'font-family':'IBM Plex Mono,monospace', ...attrs }, parent);
    el.textContent = txt; return el;
  };

  const svg = svgEl('svg', { viewBox:`0 0 ${W} ${H}`, width:W, height:H }, null);
  svg.style.cssText = 'max-width:100%;display:block;margin:0 auto;';
  svgEl('rect', { width:W, height:H, fill:'#F2F7FE', rx:10 }, svg);
  svgTxt(W/2, 28, 'RETRATO DE SECUENCIA', {
    'text-anchor':'middle','font-size':'11.5','font-weight':'700','fill':'#1E5FB8',
  }, svg);
  svgTxt(W/2, 43, `${positions.length} posiciones · pos ${startPos}–${startPos+positions.length-1}`, {
    'text-anchor':'middle','font-size':'8.5','fill':'#6A90B8',
  }, svg);

  for (let i = 0; i < positions.length; i++) {
    const col = i % COLS, row = Math.floor(i / COLS);
    const isDegen = positions[i].length > 1;
    const aa = positions[i][0];
    const color = PROP_COLORS[aaProp(aa)];
    const posNum = startPos + i;
    const x = PL + col * (CELL + GAP);
    const y = PT + row * ROW_H + TICK_H;

    if (col % 10 === 0) {
      svgTxt(x + CELL/2, y - 3, String(posNum), {
        'text-anchor':'middle','font-size':'7.5','fill': isDegen ? color : '#9AB8D4',
      }, svg);
    }

    svgEl('rect', { x, y, width:CELL, height:CELL, rx: isDegen ? 6 : 3,
      fill:color, opacity: isDegen ? 0.82 : 0.22 }, svg);

    if (isDegen) {
      svgEl('rect', { x:x-1.5, y:y-1.5, width:CELL+3, height:CELL+3, rx:7.5,
        fill:'none', stroke:color, 'stroke-width':2 }, svg);
    }

    svgTxt(x + CELL/2, y + CELL/2 + 5, aa, {
      'text-anchor':'middle',
      'font-size': isDegen ? '13' : '11',
      'font-weight': isDegen ? '800' : '600',
      'fill': isDegen ? '#fff' : color,
    }, svg);

    if (isDegen) {
      svgTxt(x + CELL/2, y + CELL + 10, positions[i].slice(1).join('/'), {
        'text-anchor':'middle','font-size':'8','font-weight':'700','fill':color,
      }, svg);
    }
  }

  const legY = H - PB + 14;
  const legEntries = Object.keys(PROP_COLORS);
  const legItemW = Math.floor((W - PL - PR - 8) / legEntries.length);
  legEntries.forEach((prop, i) => {
    const lx = PL + i * legItemW;
    svgEl('rect', { x:lx, y:legY, width:11, height:11, rx:3, fill:PROP_COLORS[prop] }, svg);
    svgTxt(lx + 14, legY + 9.5, PROP_LABELS[prop], { 'font-size':'8.5','fill':'#2B4F7A' }, svg);
  });

  const wrap = document.createElement('div');
  wrap.style.cssText = 'overflow-x:auto;padding:4px 0;';
  wrap.appendChild(svg);
  const dlRow = document.createElement('div');
  dlRow.style.cssText = 'display:flex;gap:8px;margin-top:12px;justify-content:center;';
  const btnSvg = mk('button', 'bw-btn');
  btnSvg.style.cssText = 'font-size:0.78rem;padding:6px 16px;';
  btnSvg.textContent = 'Descargar SVG';
  btnSvg.addEventListener('click', () => {
    const s = new XMLSerializer().serializeToString(svg);
    const b = new Blob([s], { type:'image/svg+xml' });
    const u = URL.createObjectURL(b);
    Object.assign(document.createElement('a'), { href:u, download:'retrato-secuencia.svg' }).click();
    setTimeout(() => URL.revokeObjectURL(u), 1000);
  });
  dlRow.appendChild(btnSvg);
  container.appendChild(wrap);
  container.appendChild(dlRow);
}

// ── Viz 2: Perfil de Degeneración (D3) ───────────────────────────────────────
function renderDegenProfile(container, positions, startPos) {
  if (typeof d3 === 'undefined') {
    container.innerHTML = '<p style="color:var(--red);font-family:var(--mono);font-size:0.82rem;padding:20px;">D3.js no disponible.</p>';
    return;
  }
  const degenPos = positions.map((p, i) => ({
    pos: startPos + i, alts: p.length, primary: p[0],
  })).filter(d => d.alts > 1);
  if (!degenPos.length) {
    container.innerHTML = '<p style="color:var(--text-dim);font-family:var(--mono);font-size:0.85rem;padding:20px;text-align:center;">No hay posiciones degeneradas.</p>';
    return;
  }
  let cumLog = 0;
  const allPts = positions.map((p, i) => {
    cumLog += Math.log2(p.length);
    return { pos: startPos + i, log: cumLog };
  });
  const mono = 'IBM Plex Mono,monospace';
  const W = Math.min(window.innerWidth - 100, 860);
  const H = 340, M = { top:30, right:74, bottom:72, left:50 };
  const iW = W - M.left - M.right, iH = H - M.top - M.bottom;

  const svg = d3.select(container).append('svg')
    .attr('width', W).attr('height', H)
    .style('max-width','100%').style('display','block').style('margin','0 auto');
  svg.append('rect').attr('width',W).attr('height',H).attr('fill','#F2F7FE').attr('rx',10);

  // title
  svg.append('text').attr('x',W/2).attr('y',20).attr('text-anchor','middle')
    .attr('font-size','11.5').attr('font-weight','700').attr('fill','#0D1F3C')
    .attr('font-family',mono).text('PERFIL DE DEGENERACIÓN');

  const g = svg.append('g').attr('transform', `translate(${M.left},${M.top})`);
  const xSc = d3.scaleLinear().domain([startPos - 0.5, startPos + positions.length - 0.5]).range([0, iW]);
  const yL  = d3.scaleLinear().domain([0, 3.5]).range([iH, 0]);
  const yR  = d3.scaleLinear().domain([0, cumLog * 1.08]).range([iH, 0]);

  g.append('g').call(d3.axisLeft(yL).tickSize(-iW).tickFormat('').ticks(3))
    .selectAll('line').attr('stroke','rgba(30,95,184,0.08)').attr('stroke-dasharray','4,3');
  g.selectAll('.domain').remove();

  g.append('path').datum(allPts)
    .attr('fill','rgba(30,95,184,0.07)')
    .attr('d', d3.area().x(d=>xSc(d.pos)).y0(iH).y1(d=>yR(d.log)).curve(d3.curveStepAfter));
  g.append('path').datum(allPts)
    .attr('fill','none').attr('stroke','#1E5FB8').attr('stroke-width',2).attr('opacity',0.72)
    .attr('d', d3.line().x(d=>xSc(d.pos)).y(d=>yR(d.log)).curve(d3.curveStepAfter));

  const barW = Math.max(3, Math.min(16, iW / positions.length * 0.6));
  degenPos.forEach(d => {
    const col = PROP_COLORS[aaProp(d.primary)];
    g.append('rect')
      .attr('x', xSc(d.pos) - barW/2).attr('y', yL(d.alts))
      .attr('width', barW).attr('height', iH - yL(d.alts))
      .attr('fill', col).attr('opacity', 0.76).attr('rx', 3);
    if (barW >= 8) {
      g.append('text').attr('x', xSc(d.pos)).attr('y', yL(d.alts) - 3)
        .attr('text-anchor','middle').attr('font-size','9').attr('font-weight','700')
        .attr('font-family',mono).attr('fill', col).text(d.primary);
    }
  });

  const axStyle = sel => sel.selectAll('text').attr('font-family',mono).attr('font-size','9').attr('fill','#2B4F7A');
  const ticks = d3.range(startPos, startPos + positions.length, Math.max(1, Math.round(positions.length / 10)));
  axStyle(g.append('g').attr('transform',`translate(0,${iH})`).call(d3.axisBottom(xSc).tickValues(ticks)));
  axStyle(g.append('g').call(d3.axisLeft(yL).ticks(3).tickFormat(d => d > 0 ? d : '')));
  axStyle(g.append('g').attr('transform',`translate(${iW},0)`).call(d3.axisRight(yR).ticks(4).tickFormat(d => d.toFixed(1))));

  svg.append('text').attr('transform','rotate(-90)').attr('x',-(M.top+iH/2)).attr('y',14)
    .attr('text-anchor','middle').attr('font-size','9.5').attr('font-family',mono).attr('fill','#2B4F7A')
    .text('Alternativas');
  svg.append('text').attr('transform',`translate(${M.left+iW/2},${H-8})`)
    .attr('text-anchor','middle').attr('font-size','9.5').attr('font-family',mono).attr('fill','#2B4F7A')
    .text('Posición');
  svg.append('text').attr('transform',`translate(${W-8},${M.top+iH/2}) rotate(90)`)
    .attr('text-anchor','middle').attr('font-size','9.5').attr('font-family',mono).attr('fill','#1E5FB8')
    .text('log₂ comb. acumuladas');

  // legend (bottom, inside svg)
  const legY = M.top + iH + 48;
  const activeProps = [...new Set(degenPos.map(d => aaProp(d.primary)))];
  const totalLegW = activeProps.length * 88 + 100;
  const legX0 = Math.max(M.left, (W - totalLegW) / 2);
  activeProps.forEach((prop, i) => {
    const lx = legX0 + i * 88;
    svg.append('rect').attr('x',lx).attr('y',legY).attr('width',10).attr('height',10)
      .attr('fill',PROP_COLORS[prop]).attr('rx',2);
    svg.append('text').attr('x',lx+13).attr('y',legY+9).attr('font-size','8.5').attr('fill','#2B4F7A')
      .attr('font-family',mono).text(PROP_LABELS[prop]);
  });
  const lx2 = legX0 + activeProps.length * 88;
  svg.append('line').attr('x1',lx2).attr('x2',lx2+16).attr('y1',legY+5).attr('y2',legY+5)
    .attr('stroke','#1E5FB8').attr('stroke-width',2);
  svg.append('text').attr('x',lx2+20).attr('y',legY+9).attr('font-size','8.5').attr('fill','#1E5FB8')
    .attr('font-family',mono).text('Comb. acum.');
}

// ── Viz 3: Paisaje Aminoacídico (D3 heatmap) ─────────────────────────────────
function renderDegenLandscape(container, positions, startPos) {
  if (typeof d3 === 'undefined') {
    container.innerHTML = '<p style="color:var(--red);font-family:var(--mono);font-size:0.82rem;padding:20px;">D3.js no disponible.</p>';
    return;
  }
  const degenPos = positions.map((p, i) => ({ pos: startPos + i, aas: p })).filter(d => d.aas.length > 1);
  if (!degenPos.length) {
    container.innerHTML = '<p style="color:var(--text-dim);font-family:var(--mono);font-size:0.85rem;padding:20px;text-align:center;">No hay posiciones degeneradas.</p>';
    return;
  }
  const CELL = 22, nCols = degenPos.length, nRows = AA_ORDER.length;
  const M = { top:52, left:38, right:16, bottom:48 };
  const iW = nCols * CELL, iH = nRows * CELL;
  const W = M.left + iW + M.right, H = M.top + iH + M.bottom;
  const mono = 'IBM Plex Mono,monospace';

  const scrollWrap = document.createElement('div');
  scrollWrap.style.cssText = 'overflow-x:auto;padding:4px 0;';
  container.appendChild(scrollWrap);

  const svg = d3.select(scrollWrap).append('svg')
    .attr('width', W).attr('height', H)
    .style('display','block').style('margin','0 auto');
  svg.append('rect').attr('width',W).attr('height',H).attr('fill','#F2F7FE').attr('rx',10);

  svg.append('text').attr('x',W/2).attr('y',22).attr('text-anchor','middle')
    .attr('font-size','11.5').attr('font-weight','700').attr('fill','#0D1F3C')
    .attr('font-family',mono).text('PAISAJE AMINOACÍDICO');
  svg.append('text').attr('x',W/2).attr('y',36).attr('text-anchor','middle')
    .attr('font-size','8.5').attr('fill','#6A90B8').attr('font-family',mono)
    .text('sólido = posición primaria · tenue = alternativa');

  const g = svg.append('g').attr('transform',`translate(${M.left},${M.top})`);

  // property side bands
  const propBands = [
    { prop:'hydrophobic', aas:['A','V','L','I','P','F','M','W'] },
    { prop:'polar',       aas:['S','T','C','Y','N','Q'] },
    { prop:'positive',    aas:['K','R','H'] },
    { prop:'negative',    aas:['D','E'] },
    { prop:'special',     aas:['G'] },
  ];
  propBands.forEach(({ prop, aas }) => {
    const r0 = AA_ORDER.indexOf(aas[0]), r1 = AA_ORDER.indexOf(aas[aas.length-1]);
    if (r0 < 0) return;
    g.append('rect').attr('x',-6).attr('y',r0*CELL).attr('width',4)
      .attr('height',(r1-r0+1)*CELL).attr('fill',PROP_COLORS[prop]).attr('rx',2);
  });

  // row shading + AA labels
  AA_ORDER.forEach((aa, ri) => {
    if (ri % 2 === 0)
      g.append('rect').attr('x',0).attr('y',ri*CELL).attr('width',iW).attr('height',CELL)
        .attr('fill','rgba(30,95,184,0.04)');
    g.append('text').attr('x',-10).attr('y',ri*CELL+CELL/2+4)
      .attr('text-anchor','end').attr('font-size','10').attr('font-family',mono)
      .attr('font-weight','700').attr('fill',PROP_COLORS[aaProp(aa)]).text(aa);
  });

  // column labels
  degenPos.forEach((dp, ci) => {
    g.append('text')
      .attr('transform',`translate(${ci*CELL+CELL/2},${iH+5}) rotate(45)`)
      .attr('text-anchor','start').attr('font-size','8.5')
      .attr('font-family',mono).attr('fill','#2B4F7A').text(dp.pos);
  });

  // grid
  for (let ci = 0; ci <= nCols; ci++)
    g.append('line').attr('x1',ci*CELL).attr('x2',ci*CELL).attr('y1',0).attr('y2',iH)
      .attr('stroke','rgba(30,95,184,0.1)').attr('stroke-width',0.5);
  for (let ri = 0; ri <= nRows; ri++)
    g.append('line').attr('x1',0).attr('x2',iW).attr('y1',ri*CELL).attr('y2',ri*CELL)
      .attr('stroke','rgba(30,95,184,0.1)').attr('stroke-width',0.5);

  // circles
  const r = CELL * 0.38;
  degenPos.forEach((dp, ci) => {
    const cx = ci * CELL + CELL/2;
    AA_ORDER.forEach((aa, ri) => {
      const isPrimary = dp.aas[0] === aa;
      const isAlt = !isPrimary && dp.aas.slice(1).includes(aa);
      if (!isPrimary && !isAlt) return;
      const col = PROP_COLORS[aaProp(aa)];
      g.append('circle').attr('cx',cx).attr('cy',ri*CELL+CELL/2).attr('r',r)
        .attr('fill',col).attr('opacity', isPrimary ? 0.86 : 0.28);
      if (r >= 6) {
        g.append('text').attr('x',cx).attr('y',ri*CELL+CELL/2+3.5)
          .attr('text-anchor','middle')
          .attr('font-size', isPrimary ? '9' : '8')
          .attr('font-family',mono).attr('font-weight', isPrimary ? '800':'600')
          .attr('fill', isPrimary ? '#fff' : col).attr('opacity', isPrimary ? 1 : 0.9)
          .text(aa);
      }
    });
  });
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

  // Visualizaciones
  const vizSection = mk('div', 'degen-viz-btns-section');
  const vizLbl = mk('div', 'degen-section-label'); vizLbl.textContent = 'Visualizaciones';
  vizSection.appendChild(vizLbl);
  const vizBtns = mk('div', 'degen-viz-btns');
  const mkVizBtn = (lbl, cls, fn) => {
    const b = mk('button', `bw-btn-viz ${cls}`); b.textContent = lbl;
    b.addEventListener('click', () => openDegenViz(lbl, c => fn(c, positions, startPos)));
    return b;
  };
  vizBtns.appendChild(mkVizBtn('Retrato de Secuencia',   'bw-btn-viz--map',       renderDegenSeqMap));
  vizBtns.appendChild(mkVizBtn('Perfil de Degeneración', 'bw-btn-viz--profile',   renderDegenProfile));
  vizBtns.appendChild(mkVizBtn('Paisaje Aminoacídico',   'bw-btn-viz--landscape', renderDegenLandscape));
  vizSection.appendChild(vizBtns);
  root.appendChild(vizSection);

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
  const existingPlddt = $('plddt-results');
  if (existingPlddt) existingPlddt.remove();
  const existingMutagen = $('mutagen-results');
  if (existingMutagen) existingMutagen.remove();
  state.clientSideBlob = null;

  try {
    if (op.id === 'plddt-kde') {
      await runPlddtKde(op);
      return;
    }
    if (op.id === 'mutagen-tree') {
      await runMutagenTree(op);
      return;
    }

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


// ── pLDDT KDE Analyzer ───────────────────────────────────────────────────────

const PLDDT_PALETTE = [
  { line: '#c4807f', fill: 'rgba(196,128,127,0.25)' },
  { line: '#6a9fc4', fill: 'rgba(106,159,196,0.25)' },
  { line: '#72b472', fill: 'rgba(114,180,114,0.25)' },
  { line: '#c4a85c', fill: 'rgba(196,168,92,0.25)'  },
  { line: '#9d72b4', fill: 'rgba(157,114,180,0.25)' },
  { line: '#c47282', fill: 'rgba(196,114,130,0.25)' },
];
const PLDDT_FONT  = "'Arial','Helvetica Neue',sans-serif";
const PLDDT_SVG_W = 680;
const PLDDT_IH    = 307;
const PLDDT_MTOP  = 35;
const PLDDT_ML    = 68;
const PLDDT_MR    = 45;
const PLDDT_IW    = PLDDT_SVG_W - PLDDT_ML - PLDDT_MR;

let plddtGroups        = [{ id: 1, name: 'Grupo 1', raw: '' }];
let plddtNextId        = 2;
let plddtShowLegend    = true;
let plddtCurrentGroups = [];

function plddtSvgH(nLegRows) {
  // top + innerH + x-tick-space + x-label + gap + leg-rows + bottom-pad
  return PLDDT_MTOP + PLDDT_IH + 20 + 26 + 16 + 22 * Math.max(1, nLegRows) + 14;
}

function plddtParseRaw(raw) {
  const values = [], rejected = [];
  for (const line of raw.split('\n')) {
    const t = line.trim();
    if (!t) continue;
    const parts = t.split(/\s+/);
    const n = parseFloat(parts[parts.length - 1]);
    if (!isNaN(n) && n >= 0 && n <= 100) values.push(n);
    else if (!isNaN(n)) rejected.push(n);
  }
  return { values, rejected };
}

function plddtGaussianKernel(bw) {
  const k = 1 / (bw * Math.sqrt(2 * Math.PI));
  return u => k * Math.exp(-0.5 * (u / bw) ** 2);
}

function plddtSilvermanBw(data) {
  const n = data.length;
  if (n < 2) return 1;
  const mu  = data.reduce((a, b) => a + b, 0) / n;
  const std = Math.sqrt(data.reduce((a, v) => a + (v - mu) ** 2, 0) / n);
  if (std === 0) return 0.1;
  return 1.06 * std * Math.pow(n, -0.2);
}

function plddtComputeKDE(data, kernel, xs) {
  return xs.map(x => [x, data.reduce((s, v) => s + kernel(x - v), 0) / data.length]);
}

// groups = [{ name, values, palette:{line,fill} }], showLegend, transparent
function plddtDrawChart(groups, showLegend = true, transparent = false) {
  const svgEl = document.getElementById('plddt-chart');
  if (!svgEl || typeof d3 === 'undefined') return;

  const SVG_H = plddtSvgH(showLegend ? groups.length : 0);
  const svg = d3.select('#plddt-chart');
  svg.selectAll('*').remove();
  svg.attr('width', PLDDT_SVG_W).attr('height', SVG_H).attr('xmlns', 'http://www.w3.org/2000/svg');

  if (!transparent) {
    svg.append('rect').attr('width', PLDDT_SVG_W).attr('height', SVG_H).attr('fill', '#ffffff');
  }

  const g = svg.append('g').attr('transform', `translate(${PLDDT_ML},${PLDDT_MTOP})`);

  // Combined x domain across all groups
  const allVals = groups.flatMap(gr => gr.values);
  const bwMax   = Math.max(...groups.map(gr => plddtSilvermanBw(gr.values)));
  const pad     = Math.max(bwMax * 3.5, 0.4);
  const xMin    = Math.min(...allVals) - pad;
  const xMax    = Math.max(...allVals) + pad;
  const xs      = d3.range(xMin, xMax, (xMax - xMin) / 300);

  const xScale = d3.scaleLinear().domain([xMin, xMax]).range([0, PLDDT_IW]);
  const yScale = d3.scaleLinear().domain([0, 1.06]).range([PLDDT_IH, 0]);

  // Grid
  g.append('g')
    .call(d3.axisLeft(yScale).tickValues([0,.2,.4,.6,.8,1]).tickSize(-PLDDT_IW).tickFormat(''))
    .call(e => e.select('.domain').remove())
    .call(e => e.selectAll('.tick line').attr('stroke','#e4e4e4').attr('stroke-dasharray','4,4').attr('stroke-width',1));

  // Draw each group (areas first, then lines on top)
  groups.forEach(grp => {
    const { fill: fc } = grp.palette;
    const bw   = plddtSilvermanBw(grp.values);
    const kdeN = plddtComputeKDE(grp.values, plddtGaussianKernel(bw), xs);
    const maxD = Math.max(...kdeN.map(d => d[1]));
    const norm = kdeN.map(d => [d[0], d[1] / maxD]);
    g.append('path').datum(norm).attr('fill', fc)
      .attr('d', d3.area().x(d => xScale(d[0])).y0(PLDDT_IH).y1(d => yScale(d[1])).curve(d3.curveMonotoneX));
    grp._norm = norm; // cache for peak + line pass
  });
  groups.forEach(grp => {
    const { line: lc } = grp.palette;
    g.append('path').datum(grp._norm)
      .attr('fill','none').attr('stroke',lc).attr('stroke-width',2.2)
      .attr('d', d3.line().x(d => xScale(d[0])).y(d => yScale(d[1])).curve(d3.curveMonotoneX));

    const peak = grp._norm.reduce((a, b) => b[1] > a[1] ? b : a);
    const px = xScale(peak[0]), py = yScale(1);
    const lr = px < PLDDT_IW * 0.6;
    g.append('text')
      .attr('x', px + (lr ? 10 : -10)).attr('y', py - 10)
      .attr('text-anchor', lr ? 'start' : 'end')
      .attr('fill', lc).attr('font-family', PLDDT_FONT).attr('font-size','13px')
      .text(peak[0].toFixed(2));
    g.append('circle').attr('cx', px).attr('cy', py).attr('r', 5)
      .attr('fill', lc).attr('stroke','#fff').attr('stroke-width',1.5);
  });

  // Axes
  const ax = e => e.selectAll('text').attr('font-family', PLDDT_FONT).attr('font-size','11px').attr('fill','#444');
  g.append('g').attr('transform',`translate(0,${PLDDT_IH})`)
    .call(d3.axisBottom(xScale).ticks(7).tickFormat(d3.format('.1f')))
    .call(ax).call(e => e.select('.domain').attr('stroke','#bbb'))
    .call(e => e.selectAll('.tick line').attr('stroke','#bbb'));
  g.append('g')
    .call(d3.axisLeft(yScale).tickValues([0,.2,.4,.6,.8,1]).tickFormat(d => d===0?'0':d.toFixed(1)))
    .call(ax).call(e => e.select('.domain').attr('stroke','#bbb'))
    .call(e => e.selectAll('.tick line').attr('stroke','#bbb'));

  g.append('text').attr('x', PLDDT_IW/2).attr('y', PLDDT_IH+46)
    .attr('text-anchor','middle').attr('fill','#333')
    .attr('font-family',PLDDT_FONT).attr('font-size','13px').text('Average CA pLDDT');
  g.append('text').attr('transform','rotate(-90)').attr('x',-(PLDDT_IH/2)).attr('y',-52)
    .attr('text-anchor','middle').attr('fill','#333')
    .attr('font-family',PLDDT_FONT).attr('font-size','13px').text('Density');

  // Legend
  if (showLegend) {
    const legY0 = PLDDT_IH + 64;
    const legX  = PLDDT_IW / 2 - 60;
    groups.forEach((grp, i) => {
      const { line: lc } = grp.palette;
      const y = legY0 + i * 22;
      g.append('line').attr('x1',legX).attr('x2',legX+22).attr('y1',y).attr('y2',y)
        .attr('stroke',lc).attr('stroke-width',2.2);
      g.append('circle').attr('cx',legX+11).attr('cy',y).attr('r',4).attr('fill',lc);
      g.append('text').attr('x',legX+28).attr('y',y+4)
        .attr('text-anchor','start').attr('fill','#444')
        .attr('font-family',PLDDT_FONT).attr('font-size','12px').text(grp.name);
    });
  }
}

function plddtSvgToBlob(scale, transparent = false) {
  return new Promise((resolve, reject) => {
    const svgEl = document.getElementById('plddt-chart');
    if (!svgEl) return reject(new Error('SVG not found'));
    let root = svgEl;
    if (transparent) {
      root = svgEl.cloneNode(true);
      const bgRect = root.querySelector('rect[fill="#ffffff"]');
      if (bgRect) bgRect.remove();
    }
    const svgStr = new XMLSerializer().serializeToString(root);
    const blob   = new Blob([svgStr], { type: 'image/svg+xml' });
    const url    = URL.createObjectURL(blob);
    const img    = new Image();
    const w = parseInt(svgEl.getAttribute('width')  || PLDDT_SVG_W);
    const h = parseInt(svgEl.getAttribute('height') || 440);
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width  = w * scale;
      canvas.height = h * scale;
      const ctx = canvas.getContext('2d');
      if (!transparent) { ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, canvas.width, canvas.height); }
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      canvas.toBlob(b => resolve(b), 'image/png', 1.0);
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('SVG render failed')); };
    img.src = url;
  });
}

function plddtDownloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

async function plddtExportPng(btnEl, transparent = false) {
  btnEl.disabled = true;
  try {
    const pngBlob = await plddtSvgToBlob(3, transparent);
    const arrBuf  = await pngBlob.arrayBuffer();
    const resp = await fetch('/batchwork/api/export/png', {
      method: 'POST', headers: { 'Content-Type': 'image/png' }, body: arrBuf,
    });
    if (!resp.ok) throw new Error(await resp.text());
    plddtDownloadBlob(await resp.blob(), transparent ? 'plddt-distribution-transparent.png' : 'plddt-distribution.png');
  } catch (e) {
    setStatus('Error PNG: ' + e.message, 'err');
  } finally {
    btnEl.disabled = false;
  }
}

async function plddtExportTiff(btnEl) {
  btnEl.disabled = true;
  try {
    const pngBlob = await plddtSvgToBlob(3);
    const arrBuf  = await pngBlob.arrayBuffer();
    const resp = await fetch('/batchwork/api/export/tiff', {
      method: 'POST', headers: { 'Content-Type': 'image/png' }, body: arrBuf,
    });
    if (!resp.ok) throw new Error(await resp.text());
    plddtDownloadBlob(await resp.blob(), 'plddt-distribution.tiff');
  } catch (e) {
    setStatus('Error TIFF: ' + e.message, 'err');
  } finally {
    btnEl.disabled = false;
  }
}

function plddtExportExcel(groups) {
  if (typeof XLSX === 'undefined') { setStatus('xlsx.js no disponible', 'err'); return; }
  const wb = XLSX.utils.book_new();
  for (const grp of groups) {
    const ws = XLSX.utils.aoa_to_sheet([['pLDDT'], ...grp.values.map(v => [v])]);
    ws['!cols'] = [{ wch: 12 }];
    XLSX.utils.book_append_sheet(wb, ws, (grp.name || 'Grupo').slice(0, 31));
  }
  XLSX.writeFile(wb, 'plddt-values.xlsx');
}

function renderPlddtGroupsUI() {
  const zone = $('params-zone');
  zone.innerHTML = '';
  const container = document.createElement('div');
  container.className = 'bw-params';

  function rebuildUI() {
    container.innerHTML = '';
    plddtGroups.forEach((grp, i) => {
      const { line: lc } = PLDDT_PALETTE[i % PLDDT_PALETTE.length];
      const block = document.createElement('div');
      block.style.cssText = 'border:1px solid #e0ddd8;border-radius:8px;padding:12px 14px;margin-bottom:10px;background:#fafaf8;';

      const hdr = document.createElement('div');
      hdr.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:8px;';

      const dot = document.createElement('span');
      dot.style.cssText = `width:12px;height:12px;border-radius:50%;background:${lc};flex-shrink:0;display:inline-block;`;
      hdr.appendChild(dot);

      const nameIn = document.createElement('input');
      nameIn.type = 'text'; nameIn.value = grp.name; nameIn.placeholder = `Grupo ${i + 1}`;
      nameIn.style.cssText = `flex:1;font-size:0.82rem;padding:4px 8px;border:1px solid #d0ccc8;border-radius:5px;font-family:${PLDDT_FONT};`;
      nameIn.addEventListener('input', () => { plddtGroups[i].name = nameIn.value || `Grupo ${i + 1}`; });
      hdr.appendChild(nameIn);

      if (plddtGroups.length > 1) {
        const rmBtn = document.createElement('button');
        rmBtn.textContent = '✕'; rmBtn.title = 'Eliminar grupo';
        rmBtn.style.cssText = 'background:none;border:none;cursor:pointer;color:#aaa;font-size:1rem;padding:2px 6px;border-radius:4px;line-height:1;';
        rmBtn.addEventListener('mouseover', () => { rmBtn.style.color = '#c44'; });
        rmBtn.addEventListener('mouseout',  () => { rmBtn.style.color = '#aaa'; });
        rmBtn.addEventListener('click', () => { plddtGroups.splice(i, 1); rebuildUI(); updateExecuteBtn(); });
        hdr.appendChild(rmBtn);
      }
      block.appendChild(hdr);

      const ta = document.createElement('textarea');
      ta.value = grp.raw; ta.rows = 6; ta.spellcheck = false;
      ta.placeholder = '5500Myodes_glareolus 92.5\n5501Myodes_glareolus 92.1\n...';
      ta.style.cssText = `width:100%;resize:vertical;font-family:${PLDDT_FONT};font-size:0.78rem;padding:8px 10px;border:1px solid #d0ccc8;border-radius:5px;color:#333;box-sizing:border-box;`;
      ta.addEventListener('input', () => { plddtGroups[i].raw = ta.value; updateExecuteBtn(); });
      block.appendChild(ta);
      container.appendChild(block);
    });

    if (plddtGroups.length < PLDDT_PALETTE.length) {
      const addBtn = document.createElement('button');
      addBtn.style.cssText = 'font-size:0.82rem;padding:7px 14px;border:1px dashed #b0a0a0;color:#7a5050;background:transparent;border-radius:6px;cursor:pointer;width:100%;';
      addBtn.textContent = '＋ Añadir grupo';
      addBtn.addEventListener('click', () => {
        plddtGroups.push({ id: plddtNextId++, name: `Grupo ${plddtGroups.length + 1}`, raw: '' });
        rebuildUI(); updateExecuteBtn();
      });
      container.appendChild(addBtn);
    }
  }

  rebuildUI();
  zone.appendChild(container);
}

function renderPlddtResults(resolvedGroups) {
  const existing = $('plddt-results');
  if (existing) existing.remove();
  plddtCurrentGroups = resolvedGroups;

  const root = document.createElement('div');
  root.id = 'plddt-results';
  root.style.cssText = 'margin-top:20px;display:flex;flex-direction:column;gap:14px;';

  // Per-group info bars
  resolvedGroups.forEach(grp => {
    const { line: lc } = grp.palette;
    const minV = Math.min(...grp.values).toFixed(2);
    const maxV = Math.max(...grp.values).toFixed(2);
    const mean = (grp.values.reduce((a,b)=>a+b,0)/grp.values.length).toFixed(2);
    const info = document.createElement('div');
    info.className = 'degen-summary';
    info.style.borderLeft = `4px solid ${lc}`;
    info.style.paddingLeft = '10px';
    info.innerHTML = `<strong style="color:${lc}">${grp.name}</strong> &nbsp;·&nbsp; <strong>${grp.values.length}</strong> val. &nbsp;·&nbsp; min <code>${minV}</code> · max <code>${maxV}</code> · media <code>${mean}</code>` +
      (grp.rejected.length ? ` · <span style="color:#b07030">${grp.rejected.length} descartados</span>` : '');
    root.appendChild(info);
  });

  // Chart
  const chartWrap = document.createElement('div');
  chartWrap.style.cssText = 'overflow-x:auto;background:#fff;border:1px solid #e0ddd8;border-radius:8px;padding:12px;';
  const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svgEl.id = 'plddt-chart';
  chartWrap.appendChild(svgEl);
  root.appendChild(chartWrap);

  // Controls: legend toggle + exports
  const ctrlRow = document.createElement('div');
  ctrlRow.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;';

  const legBtn = document.createElement('button');
  legBtn.style.cssText = 'font-size:0.82rem;padding:7px 14px;border:1px solid #bbb;color:#555;background:#fff;border-radius:6px;cursor:pointer;';
  const refreshLegBtn = () => { legBtn.textContent = plddtShowLegend ? '👁 Ocultar leyenda' : '👁 Mostrar leyenda'; };
  refreshLegBtn();
  legBtn.addEventListener('click', () => { plddtShowLegend = !plddtShowLegend; refreshLegBtn(); plddtDrawChart(plddtCurrentGroups, plddtShowLegend); });
  ctrlRow.appendChild(legBtn);

  const mkEx = (label, title) => {
    const b = document.createElement('button');
    b.style.cssText = 'font-size:0.82rem;padding:7px 14px;border:1px solid #a08070;color:#7a4040;background:#fff;border-radius:6px;cursor:pointer;';
    b.textContent = '⬇ ' + label; b.title = title;
    return b;
  };

  const btnExcel = mkEx('Excel',              'Una hoja por grupo con los valores curados');
  const btnPng   = mkEx('PNG 300 dpi',        'PNG fondo blanco a 300 DPI');
  const btnPngT  = mkEx('PNG Transp. 300 dpi','PNG fondo transparente a 300 DPI');
  const btnTiff  = mkEx('TIFF 300 dpi',       'TIFF fondo blanco a 300 DPI');

  btnExcel.addEventListener('click', () => plddtExportExcel(resolvedGroups));
  btnPng.addEventListener('click',   () => plddtExportPng(btnPng,  false));
  btnPngT.addEventListener('click',  () => plddtExportPng(btnPngT, true));
  btnTiff.addEventListener('click',  () => plddtExportTiff(btnTiff));

  [btnExcel, btnPng, btnPngT, btnTiff].forEach(b => ctrlRow.appendChild(b));
  root.appendChild(ctrlRow);

  const paramsZone = $('params-zone');
  paramsZone.parentNode.insertBefore(root, paramsZone.nextSibling);
  requestAnimationFrame(() => plddtDrawChart(plddtCurrentGroups, plddtShowLegend));
}

async function runPlddtKde(op) {
  const resolvedGroups = [];
  plddtGroups.forEach((grp, i) => {
    const { values, rejected } = plddtParseRaw(grp.raw);
    if (values.length >= 2) {
      resolvedGroups.push({
        name:    grp.name || `Grupo ${i + 1}`,
        values,
        rejected,
        palette: PLDDT_PALETTE[i % PLDDT_PALETTE.length],
      });
    }
  });

  if (resolvedGroups.length === 0) {
    throw new Error('Ningún grupo tiene al menos 2 valores válidos (0–100).');
  }

  renderPlddtResults(resolvedGroups);

  const total     = resolvedGroups.reduce((s, g) => s + g.values.length, 0);
  const discarded = resolvedGroups.reduce((s, g) => s + g.rejected.length, 0);
  state.appStatus = 'done';
  setStatus(`✓ ${resolvedGroups.length} grupo${resolvedGroups.length !== 1 ? 's' : ''} · ${total} valores` + (discarded ? ` · ${discarded} descartados` : ''), 'ok');
  $('btn-execute').style.display = 'none';
}

// ── Mutagenesis synthesis tree ────────────────────────────────────────────────
//
// Compara secuencias derivadas frente a una original (sólo substituciones, misma
// longitud) y calcula la ruta de síntesis más barata. La empresa de síntesis
// factura UN cambio por cada grupo de mutaciones que quepa en una ventana de N
// nucleótidos (por defecto 30). El coste entre dos secuencias = nº mínimo de
// ventanas de N nt que cubren todas sus diferencias. Con un coste simétrico, la
// arborescencia de coste mínimo enraizada en la original coincide con el árbol de
// recubrimiento mínimo (MST), que calculamos con Prim. El resultado indica el
// orden de mutagénesis (qué secuencia se sintetiza a partir de cuál) que minimiza
// el número total de cambios facturados.

let mutagenInput = { original: '', list: '', blockSize: 30, allowSynthesis: true, synthCost: 3 };

const MUT_MONO = 'IBM Plex Mono,monospace';
const MUT_SYNTH_COLOR = '#8B5CF6';

// Default starting sequence: bank vole (Myodes glareolus) PrP, label 92.
const MUT_BANKVOLE_FASTA = `>92
ATGAAGAAGCGGCCAAAGCCTGGAGGGTGGAACACTGGTGGAAGCCGATACCCTGGGCAGGGCAGCCCTGGAGGCAACCGGTACCCACCTCAGGGTGGTGGTACCTGGGGACAGCCCCATGGCGGTGGCTGGGGACAGCCTCACGGTGGTGGTTGGGGTCAGCCTCACGGTGGCGGTTGGGGTCAACCCCATGGCGGCGGCTGGGGTCAAGGAGGTGGCACCCACAATCAGTGGAACAAGCCCAGTAAGCCAAAAACCAACATTAAGCATGTGGCAGGCGCTGCCGCGGCTGGGGCAGTGGTGGGGGGCCTGGGTGGCTACATGCTGGGGAGCGCCATGAGCAGGCCCATGATCCATTTCGGCAATGACTGGGAGGACCGCTACTACCGTGAAAACATGAACCGGTACCCTAACCAAGTGTACTACCGGCCGGTGGACCAGTACAACAACCAGAACAACTTCGTGCACGATTGCGTCAACATCACCATCAAGCAGCATACAGTCACCACTACCACCAAGGGGGAGAACTTCACGGAGACCGACGTCAAGATGATGGAGCGCGTGGTGGAGCAGATGTGCGTCACCCAGTATCAGAAGGAGTCCCAGGCCTACTACGAAGGGAGAAGTTCCTAA`;

// Parse the original sequence: FASTA (first record) or plain text (all lines joined).
function mutagenParseOriginal(text) {
  const t = (text || '').trim();
  if (!t) return null;
  if (t.includes('>')) {
    const arr = parseFASTA(t);
    return arr.length ? { id: arr[0].id || 'Original', seq: arr[0].seq } : null;
  }
  const clean = t.split('\n').map(l => l.trim()).join('').toUpperCase().replace(/[^A-Z*]/g, '');
  return clean ? { id: 'Original', seq: clean } : null;
}

// Parse the derived list: FASTA (by headers) or plain text (one sequence per line,
// auto-named Seq001, Seq002…).
function mutagenParseList(text) {
  const t = (text || '').trim();
  if (!t) return [];
  if (t.includes('>')) {
    return parseFASTA(t).map((s, i) => ({
      id: s.id && s.id.trim() ? s.id.trim() : `Seq${String(i + 1).padStart(3, '0')}`,
      seq: s.seq,
    }));
  }
  const seqs = [];
  for (const line of t.split('\n')) {
    const clean = line.trim().toUpperCase().replace(/[^A-Z*]/g, '');
    if (!clean) continue;
    seqs.push({ id: `Seq${String(seqs.length + 1).padStart(3, '0')}`, seq: clean });
  }
  return seqs;
}

// 0-based positions where a and b differ (compares over the shared length).
function mutagenDiffPositions(a, b) {
  const positions = [];
  const len = Math.min(a.length, b.length);
  for (let i = 0; i < len; i++) if (a[i] !== b[i]) positions.push(i);
  return positions;
}

// Greedy minimal packing of differing positions into windows of `block` nt.
// Returns [{ start, end, positions:[...] }] (0-based). Each window spans ≤ block nt.
function mutagenBlocks(positions, block) {
  const blocks = [];
  let i = 0;
  while (i < positions.length) {
    const winStart = positions[i];
    const winEnd = winStart + block - 1;
    const grp = [];
    while (i < positions.length && positions[i] <= winEnd) { grp.push(positions[i]); i++; }
    blocks.push({ start: winStart, end: grp[grp.length - 1], positions: grp });
  }
  return blocks;
}

// Cost = number of windows, computed in O(L) without allocating the position list.
function mutagenCostDirect(a, b, block) {
  let windows = 0, winEnd = -1;
  const len = Math.min(a.length, b.length);
  for (let p = 0; p < len; p++) {
    if (a[p] !== b[p] && p > winEnd) { windows++; winEnd = p + block - 1; }
  }
  return windows;
}

// Minimum spanning arborescence rooted at a virtual synthesis source S (Prim).
// nodes[0] is the original (already exists → reached from S at cost 0). Each
// derived node is obtained either by de novo synthesis (edge from S at synthCost,
// when allowed) or by mutation from another node (edge cost = block distance).
// Returns { parent[], cost[], synthCost, allowSynth } indexed by node:
//   parent[i] === -1  → attached to the virtual source S
//       · i === 0      → the original (free, pre-existing base)
//       · i  >  0      → synthesized de novo (cost = synthCost)
//   parent[i] >= 0    → mutated from node parent[i] (cost = block distance)
function mutagenBuildTree(nodes, block, opts = {}) {
  const allowSynth = opts.allowSynthesis !== false;
  const synthCost = Math.max(1, opts.synthCost || 3);
  const n = nodes.length;
  const inTree = new Array(n).fill(false);
  const bestCost = new Array(n).fill(Infinity);
  const parent = new Array(n).fill(-1);

  // Seed with the edges from the virtual source S (already in the tree).
  bestCost[0] = 0; // the original exists for free
  if (allowSynth) for (let i = 1; i < n; i++) bestCost[i] = synthCost; // synthesize de novo

  for (let it = 0; it < n; it++) {
    let u = -1, min = Infinity;
    for (let v = 0; v < n; v++) if (!inTree[v] && bestCost[v] < min) { min = bestCost[v]; u = v; }
    if (u === -1) break;
    inTree[u] = true;
    for (let v = 0; v < n; v++) {
      if (inTree[v]) continue;
      const c = mutagenCostDirect(nodes[u].seq, nodes[v].seq, block);
      if (c < bestCost[v]) { bestCost[v] = c; parent[v] = u; }
    }
  }
  return { parent, cost: bestCost, synthCost, allowSynth };
}

function mutagenCostColor(c) {
  if (c <= 0) return '#9AA7B5';
  const palette = ['#0D7A55', '#1E5FB8', '#B85820', '#B83232'];
  return palette[Math.min(c - 1, palette.length - 1)];
}

// ── Input UI ──────────────────────────────────────────────────────────────────
// preset (optional): { label, value } adds a one-click button to fill the textarea.
function mutagenMakeInput({ label, hint, placeholder, rows, value, onChange, preset }) {
  const wrap = mk('div', 'bw-field');

  const top = mk('div');
  top.style.cssText = 'display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:4px;';
  const lbl = mk('label', null, label);
  lbl.style.margin = '0';
  top.appendChild(lbl);

  const btnGroup = mk('div');
  btnGroup.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;';

  const fileBtn = mk('button', 'bw-btn bw-btn-cancel');
  fileBtn.type = 'button';
  fileBtn.style.cssText = 'font-size:0.72rem;padding:4px 12px;';
  fileBtn.textContent = '📂 Cargar fichero';
  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.accept = '.txt,.fasta,.fa,.fas,.seq,.fna,.text';
  fileInput.style.display = 'none';
  fileBtn.addEventListener('click', () => fileInput.click());
  btnGroup.appendChild(fileBtn);
  top.appendChild(btnGroup);
  wrap.appendChild(top);

  if (hint) {
    const h = mk('div', null, hint);
    h.style.cssText = `font-family:${MUT_MONO};font-size:0.7rem;color:var(--text-dim);margin-bottom:6px;line-height:1.5;`;
    wrap.appendChild(h);
  }

  const ta = document.createElement('textarea');
  ta.className = 'bw-input bw-textarea';
  ta.rows = rows || 6;
  ta.spellcheck = false;
  ta.placeholder = placeholder || '';
  ta.value = value || '';
  ta.addEventListener('input', () => onChange(ta.value));
  wrap.appendChild(ta);
  wrap.appendChild(fileInput);

  const loadFile = (file) => {
    if (!file) return;
    const r = new FileReader();
    r.onload = () => { ta.value = r.result; onChange(ta.value); };
    r.readAsText(file);
  };
  fileInput.addEventListener('change', () => { loadFile(fileInput.files[0]); fileInput.value = ''; });

  if (preset) {
    const presetBtn = mk('button', 'bw-btn bw-btn-cancel');
    presetBtn.type = 'button';
    presetBtn.style.cssText = 'font-size:0.72rem;padding:4px 12px;';
    presetBtn.textContent = preset.label;
    presetBtn.title = 'Rellenar con esta secuencia predefinida';
    presetBtn.addEventListener('click', () => { ta.value = preset.value; onChange(ta.value); });
    btnGroup.insertBefore(presetBtn, fileBtn);
  }

  ta.addEventListener('dragover', e => { e.preventDefault(); ta.classList.add('drag-over'); });
  ta.addEventListener('dragleave', () => ta.classList.remove('drag-over'));
  ta.addEventListener('drop', e => {
    if (!e.dataTransfer.files || !e.dataTransfer.files.length) return;
    e.preventDefault();
    ta.classList.remove('drag-over');
    loadFile(e.dataTransfer.files[0]);
  });

  return wrap;
}

function renderMutagenUI() {
  const zone = $('params-zone');
  zone.innerHTML = '';
  const container = mk('div', 'bw-params');

  container.appendChild(mutagenMakeInput({
    label: 'Secuencia original (raíz del árbol)',
    hint: 'Texto plano o FASTA. Pega, carga un fichero, arrastra uno aquí o usa el botón de bank vole.',
    placeholder: '>WT\nATGCGTACGT...\n\n…o pega directamente los nucleótidos.',
    rows: 5,
    value: mutagenInput.original,
    onChange: v => { mutagenInput.original = v; updateExecuteBtn(); },
    preset: { label: '🐭 Bank vole (92)', value: MUT_BANKVOLE_FASTA },
  }));

  container.appendChild(mutagenMakeInput({
    label: 'Secuencias derivadas',
    hint: 'Una secuencia por línea (se autonombran Seq001, Seq002…) o formato FASTA con cabeceras «>nombre». Deben tener la misma longitud que la original (sólo substituciones).',
    placeholder: 'ATGCGTACGT...\nATGCATACGT...\nATGCGTACTT...\n\n…o FASTA:\n>mutante_A\nATGC...',
    rows: 9,
    value: mutagenInput.list,
    onChange: v => { mutagenInput.list = v; updateExecuteBtn(); },
  }));

  const bf = mk('div', 'bw-field');
  bf.appendChild(mk('label', null, 'Tamaño de bloque (nt) — las mutaciones dentro de esta ventana cuentan como 1 cambio'));
  const bi = document.createElement('input');
  bi.type = 'number';
  bi.className = 'bw-input';
  bi.min = '1';
  bi.value = mutagenInput.blockSize;
  bi.style.maxWidth = '180px';
  bi.addEventListener('input', () => { mutagenInput.blockSize = Math.max(1, parseInt(bi.value) || 30); });
  bf.appendChild(bi);
  container.appendChild(bf);

  // ── Synthesis options ──
  const synthBox = mk('div');
  synthBox.style.cssText = 'border:1px solid var(--border);border-radius:8px;padding:12px 14px;background:var(--bg-card);';

  const cbWrap = mk('label', 'bw-checkbox-wrap');
  const cb = document.createElement('input');
  cb.type = 'checkbox';
  cb.checked = mutagenInput.allowSynthesis !== false;
  cbWrap.appendChild(cb);
  cbWrap.appendChild(mk('span', null, 'Permitir síntesis de novo (la app decide cuántas salen a cuenta)'));
  synthBox.appendChild(cbWrap);

  const synthHint = mk('div', null, 'Algunas secuencias se sintetizan desde cero como «hub» y el resto se obtienen mutando desde ellas, cuando sale más barato que mutar todo desde la original.');
  synthHint.style.cssText = `font-family:${MUT_MONO};font-size:0.7rem;color:var(--text-dim);margin:6px 0 0;line-height:1.5;`;
  synthBox.appendChild(synthHint);

  const scField = mk('div', 'bw-field');
  scField.style.cssText = 'margin-top:10px;';
  scField.appendChild(mk('label', null, 'Coste de una síntesis (× el coste de una mutación)'));
  const sc = document.createElement('input');
  sc.type = 'number';
  sc.className = 'bw-input';
  sc.min = '1';
  sc.step = '0.5';
  sc.value = mutagenInput.synthCost;
  sc.style.maxWidth = '180px';
  sc.addEventListener('input', () => { mutagenInput.synthCost = Math.max(1, parseFloat(sc.value) || 3); });
  scField.appendChild(sc);
  synthBox.appendChild(scField);

  const syncSynthUI = () => { scField.style.display = cb.checked ? '' : 'none'; };
  cb.addEventListener('change', () => { mutagenInput.allowSynthesis = cb.checked; syncSynthUI(); });
  syncSynthUI();
  container.appendChild(synthBox);

  const clearBtn = mk('button', 'bw-btn bw-btn-cancel');
  clearBtn.type = 'button';
  clearBtn.style.cssText = 'font-size:0.8rem;padding:7px 16px;align-self:flex-start;margin-top:4px;';
  clearBtn.textContent = '↺ Limpiar y empezar de nuevo';
  clearBtn.addEventListener('click', () => {
    if (state.appStatus === 'running' || state.appStatus === 'uploading') return;
    mutagenInput = { original: '', list: '', blockSize: 30, allowSynthesis: true, synthCost: 3 };
    const res = $('mutagen-results');
    if (res) res.remove();
    resetExecuteBar();
    renderMutagenUI();
    updateExecuteBtn();
  });
  container.appendChild(clearBtn);

  zone.appendChild(container);
}

// ── Run + render ────────────────────────────────────────────────────────────
async function runMutagenTree() {
  const block = Math.max(1, parseInt(mutagenInput.blockSize) || 30);
  const allowSynthesis = mutagenInput.allowSynthesis !== false;
  const synthCost = Math.max(1, parseFloat(mutagenInput.synthCost) || 3);

  const original = mutagenParseOriginal(mutagenInput.original);
  if (!original || !original.seq) throw new Error('No se pudo leer la secuencia original.');

  let derived = mutagenParseList(mutagenInput.list);
  if (derived.length === 0) throw new Error('No se encontró ninguna secuencia en el listado de derivadas.');

  const L = original.seq.length;
  const excluded = [];
  derived = derived.filter(d => {
    if (d.seq.length !== L) { excluded.push({ id: d.id, len: d.seq.length }); return false; }
    return true;
  });
  if (derived.length === 0) {
    throw new Error(`Ninguna derivada coincide en longitud con la original (${L} nt). Esta herramienta sólo admite substituciones (misma longitud, sin inserciones ni deleciones).`);
  }

  // Disambiguate duplicate names so the tree stratify doesn't collide.
  const seen = new Map();
  for (const d of derived) {
    if (seen.has(d.id)) { const k = seen.get(d.id) + 1; seen.set(d.id, k); d.id = `${d.id}#${k}`; }
    else seen.set(d.id, 1);
  }

  const nodes = [original, ...derived];
  const tree = mutagenBuildTree(nodes, block, { allowSynthesis, synthCost });

  // Breakdown of the optimal plan.
  let nSynth = 0, mutBlocks = 0;
  for (let i = 1; i < nodes.length; i++) {
    if (tree.parent[i] === -1) nSynth++;
    else mutBlocks += tree.cost[i];
  }
  const totalCost = mutBlocks + nSynth * synthCost;

  // Reference: best plan WITHOUT any de novo synthesis (everything by mutation).
  const mutOnlyTree = mutagenBuildTree(nodes, block, { allowSynthesis: false, synthCost });
  let mutOnlyTotal = 0;
  for (let i = 1; i < nodes.length; i++) mutOnlyTotal += mutOnlyTree.cost[i];

  renderMutagenResults({
    nodes, tree, block, excluded, L,
    totalCost, nSynth, mutBlocks, synthCost, allowSynthesis, mutOnlyTotal,
  });

  state.appStatus = 'done';
  const saved = mutOnlyTotal - totalCost;
  const parts = [`${derived.length} derivada${derived.length !== 1 ? 's' : ''}`];
  if (allowSynthesis && nSynth > 0) parts.push(`${nSynth} síntesis + ${mutBlocks} bloque${mutBlocks !== 1 ? 's' : ''}`);
  parts.push(`coste óptimo ${mutagenFmt(totalCost)}`);
  if (saved > 0) parts.push(`ahorras ${mutagenFmt(saved)} vs. solo mutación`);
  if (excluded.length) parts.push(`${excluded.length} excluida${excluded.length !== 1 ? 's' : ''}`);
  setStatus('✓ ' + parts.join(' · '), 'ok');
  $('btn-execute').style.display = 'none';
}

// Format a cost: integer when whole, otherwise up to 1 decimal.
function mutagenFmt(x) {
  return Number.isInteger(x) ? String(x) : x.toFixed(1);
}

function renderMutagenResults({ nodes, tree, block, excluded, L, totalCost, nSynth, mutBlocks, synthCost, allowSynthesis, mutOnlyTotal }) {
  const existing = $('mutagen-results');
  if (existing) existing.remove();

  const root = mk('div', 'degen-results');
  root.id = 'mutagen-results';

  // Summary
  const summary = mk('div', 'degen-summary');
  summary.innerHTML = `Original <code class="degen-seq-code">${nodes[0].name || nodes[0].id}</code> · <strong>${L} nt</strong> · ventana de empaquetado <strong>${block} nt</strong>` +
    (allowSynthesis ? ` · síntesis = <strong>${mutagenFmt(synthCost)}×</strong> una mutación` : ' · sólo mutación (síntesis desactivada)');
  root.appendChild(summary);

  // Stats
  const saved = mutOnlyTotal - totalCost;
  const stats = mk('div', 'degen-stats');
  const mkStat = (val, lbl, color) => {
    const s = mk('div', 'degen-stat');
    s.innerHTML = `<span class="degen-stat-val"${color ? ` style="color:${color}"` : ''}>${val}</span><span class="degen-stat-lbl">${lbl}</span>`;
    return s;
  };
  stats.appendChild(mkStat(nodes.length - 1, 'secuencias<br>derivadas'));
  if (allowSynthesis) stats.appendChild(mkStat(nSynth, 'síntesis<br>de novo', MUT_SYNTH_COLOR));
  stats.appendChild(mkStat(mutBlocks, 'bloques de<br>mutación'));
  stats.appendChild(mkStat(mutagenFmt(totalCost), 'coste total<br>(ruta óptima)'));
  if (allowSynthesis) stats.appendChild(mkStat(saved > 0 ? `−${mutagenFmt(saved)}` : '0', 'ahorro vs.<br>solo mutación', saved > 0 ? 'var(--green)' : undefined));
  root.appendChild(stats);

  if (excluded.length) {
    const warn = mk('div', 'degen-warn');
    warn.innerHTML = `⚠ ${excluded.length} secuencia${excluded.length !== 1 ? 's' : ''} excluida${excluded.length !== 1 ? 's' : ''} por longitud distinta a ${L} nt (sólo se admiten substituciones): ` +
      excluded.map(e => `<strong>${e.id}</strong> (${e.len} nt)`).join(', ');
    root.appendChild(warn);
  }

  // ── Tree visualization ──
  const treeLbl = mk('div', 'degen-section-label');
  treeLbl.textContent = allowSynthesis
    ? 'Árbol de síntesis (⚙ = síntesis de novo · ramas = mutaciones facturadas)'
    : 'Árbol de síntesis (la etiqueta de cada rama = cambios facturados)';
  root.appendChild(treeLbl);

  const treeWrap = mk('div');
  treeWrap.style.cssText = 'overflow:auto;background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:10px;max-height:620px;';
  root.appendChild(treeWrap);
  const svgNode = renderMutagenTreeViz(treeWrap, nodes, tree);

  // ── Synthesis plan ──
  const planRows = mutagenBuildPlan(nodes, tree, block);

  const planLbl = mk('div', 'degen-section-label');
  planLbl.textContent = 'Plan de síntesis (orden de mutagénesis recomendado)';
  planLbl.style.marginTop = '18px';
  root.appendChild(planLbl);

  const plan = mk('div');
  plan.style.cssText = 'display:flex;flex-direction:column;gap:8px;';
  planRows.forEach((r, idx) => plan.appendChild(mutagenPlanRowEl(r, idx + 1)));
  root.appendChild(plan);

  // ── Exports ──
  const dlRow = mk('div');
  dlRow.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;margin-top:16px;';

  const mkBtn = (label) => {
    const b = mk('button', 'bw-btn bw-btn-cancel');
    b.style.cssText = 'font-size:0.78rem;padding:6px 14px;';
    b.textContent = label;
    return b;
  };

  const btnSvg = mkBtn('⬇ Árbol (SVG)');
  btnSvg.addEventListener('click', () => {
    if (!svgNode) return;
    const s = new XMLSerializer().serializeToString(svgNode);
    const b = new Blob([s], { type: 'image/svg+xml' });
    const u = URL.createObjectURL(b);
    Object.assign(document.createElement('a'), { href: u, download: 'arbol-mutagenesis.svg' }).click();
    setTimeout(() => URL.revokeObjectURL(u), 1000);
  });
  dlRow.appendChild(btnSvg);

  const btnXlsx = mkBtn('⬇ Plan (Excel)');
  btnXlsx.addEventListener('click', () => mutagenExportExcel(planRows));
  dlRow.appendChild(btnXlsx);

  const btnCopy = mkBtn('📋 Copiar plan');
  btnCopy.addEventListener('click', () => {
    navigator.clipboard.writeText(mutagenPlanToText(planRows)).then(() => {
      btnCopy.textContent = '✓ Copiado';
      setTimeout(() => { btnCopy.textContent = '📋 Copiar plan'; }, 2000);
    });
  });
  dlRow.appendChild(btnCopy);

  root.appendChild(dlRow);

  const paramsZone = $('params-zone');
  paramsZone.parentNode.insertBefore(root, paramsZone.nextSibling);
}

// Build the ordered plan (BFS from the virtual source). Each row is one step:
//   type 'synth' → synthesize the sequence de novo (cost = synthCost)
//   type 'mut'   → mutate it from an existing sequence (blocks of changes)
// The original is the pre-existing base and produces no step.
function mutagenBuildPlan(nodes, tree, block) {
  const name = i => nodes[i].name || nodes[i].id;
  const byName = (a, b) => name(a).localeCompare(name(b), undefined, { numeric: true });

  const children = Array.from({ length: nodes.length }, () => []);
  const roots = []; // nodes attached to the virtual source (original + synthesized)
  for (let i = 0; i < nodes.length; i++) {
    if (tree.parent[i] === -1) roots.push(i);
    else children[tree.parent[i]].push(i);
  }
  roots.sort(byName);
  for (const c of children) c.sort(byName);

  const rows = [];
  const queue = [...roots]; // BFS guarantees a parent is emitted before its children
  while (queue.length) {
    const u = queue.shift();
    if (u === 0) {
      // the original: pre-existing base, no step
    } else if (tree.parent[u] === -1) {
      rows.push({ type: 'synth', child: name(u), parent: null, cost: tree.synthCost, blocks: [] });
    } else {
      const p = tree.parent[u];
      const positions = mutagenDiffPositions(nodes[p].seq, nodes[u].seq);
      const blocks = mutagenBlocks(positions, block).map(b => ({
        from: b.start + 1,
        to: b.end + 1,
        muts: b.positions.map(pos => ({ pos: pos + 1, ref: nodes[p].seq[pos], alt: nodes[u].seq[pos] })),
      }));
      rows.push({ type: 'mut', child: name(u), parent: name(p), cost: tree.cost[u], blocks });
    }
    for (const c of children[u]) queue.push(c);
  }
  return rows;
}

function mutagenPlanRowEl(r, step) {
  const isSynth = r.type === 'synth';
  const accent = isSynth ? MUT_SYNTH_COLOR : mutagenCostColor(r.cost);

  const el = mk('div');
  el.style.cssText = `border:1px solid var(--border);border-left:4px solid ${accent};border-radius:8px;padding:10px 12px;background:var(--bg-card);`;

  const head = mk('div');
  head.style.cssText = `display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-family:${MUT_MONO};font-size:0.82rem;color:var(--text);`;

  if (isSynth) {
    head.innerHTML =
      `<span style="font-weight:700;color:var(--text-dim);">${String(step).padStart(2, '0')}</span>` +
      `<span style="color:${MUT_SYNTH_COLOR};font-weight:700;">⚙ Sintetizar de novo</span>` +
      `<strong style="color:${MUT_SYNTH_COLOR};">${r.child}</strong>` +
      `<span style="margin-left:auto;font-weight:700;color:${MUT_SYNTH_COLOR};">coste ${mutagenFmt(r.cost)}</span>`;
  } else {
    const costTxt = r.cost === 0
      ? 'idéntica (sin coste)'
      : `${r.cost} cambio${r.cost !== 1 ? 's' : ''}`;
    head.innerHTML =
      `<span style="font-weight:700;color:var(--text-dim);">${String(step).padStart(2, '0')}</span>` +
      `<strong style="color:var(--blue);">${r.child}</strong>` +
      `<span style="color:var(--text-dim);">a partir de</span>` +
      `<strong>${r.parent}</strong>` +
      `<span style="margin-left:auto;font-weight:700;color:${accent};">${costTxt}</span>`;
  }
  el.appendChild(head);

  if (r.blocks.length) {
    const list = mk('div');
    list.style.cssText = 'display:flex;flex-direction:column;gap:4px;margin-top:8px;';
    r.blocks.forEach((b, i) => {
      const row = mk('div');
      row.style.cssText = `font-family:${MUT_MONO};font-size:0.72rem;color:var(--text-muted);line-height:1.5;`;
      const rangeTxt = b.from === b.to ? `pos ${b.from}` : `pos ${b.from}–${b.to}`;
      const mutTxt = b.muts.map(m => `${m.pos}:${m.ref}→${m.alt}`).join(', ');
      row.innerHTML =
        `<span style="display:inline-block;min-width:64px;color:${mutagenCostColor(r.cost)};font-weight:700;">Bloque ${i + 1}</span>` +
        `<span style="color:var(--text);">${rangeTxt}</span> ` +
        `<span style="color:var(--text-dim);">(${b.muts.length} mut.)</span> ` +
        `<span>· ${mutTxt}</span>`;
      list.appendChild(row);
    });
    el.appendChild(list);
  }

  return el;
}

function mutagenPlanToText(rows) {
  const lines = ['Plan de síntesis (orden recomendado)', ''];
  rows.forEach((r, i) => {
    const num = String(i + 1).padStart(2, '0');
    if (r.type === 'synth') {
      lines.push(`${num}. ${r.child} ← síntesis de novo  [coste ${mutagenFmt(r.cost)}]`);
      return;
    }
    const costTxt = r.cost === 0 ? 'idéntica (sin coste)' : `${r.cost} cambio(s)`;
    lines.push(`${num}. ${r.child} ← mutar desde ${r.parent}  [${costTxt}]`);
    r.blocks.forEach((b, j) => {
      const rangeTxt = b.from === b.to ? `pos ${b.from}` : `pos ${b.from}-${b.to}`;
      const mutTxt = b.muts.map(m => `${m.pos}:${m.ref}>${m.alt}`).join(', ');
      lines.push(`     Bloque ${j + 1}: ${rangeTxt} (${b.muts.length} mut.) ${mutTxt}`);
    });
  });
  return lines.join('\n') + '\n';
}

// Export the synthesis plan as a real .xlsx with one column per field.
// One row per mutation block; synthesis steps and block-less rows take a single row.
function mutagenExportExcel(rows) {
  if (typeof XLSX === 'undefined') { setStatus('xlsx.js no disponible', 'err'); return; }

  const header = ['Paso', 'Tipo', 'Secuencia', 'A partir de', 'Coste',
                  'Nº bloque', 'Desde (nt)', 'Hasta (nt)', 'Nº mutaciones', 'Mutaciones'];
  const aoa = [header];

  rows.forEach((r, i) => {
    if (r.type === 'synth') {
      aoa.push([i + 1, 'Síntesis de novo', r.child, '(desde cero)', r.cost, '', '', '', '', '']);
      return;
    }
    if (!r.blocks.length) {
      aoa.push([i + 1, 'Mutación', r.child, r.parent, r.cost, '', '', '', 0, 'idéntica (sin coste)']);
      return;
    }
    r.blocks.forEach((b, j) => {
      const mutTxt = b.muts.map(m => `${m.pos}:${m.ref}>${m.alt}`).join(', ');
      aoa.push([i + 1, 'Mutación', r.child, r.parent, r.cost, j + 1, b.from, b.to, b.muts.length, mutTxt]);
    });
  });

  const ws = XLSX.utils.aoa_to_sheet(aoa);
  ws['!cols'] = [
    { wch: 6 }, { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 8 },
    { wch: 10 }, { wch: 11 }, { wch: 11 }, { wch: 14 }, { wch: 60 },
  ];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Plan de síntesis');
  XLSX.writeFile(wb, 'plan-mutagenesis.xlsx');
}

// Horizontal d3 tree. Returns the <svg> DOM node (for export) or null.
// Node kinds: 'source' (virtual synthesizer), 'original', 'synth', 'mut'.
function renderMutagenTreeViz(container, nodes, tree) {
  if (typeof d3 === 'undefined') {
    container.innerHTML = '<p style="color:var(--red);font-family:var(--mono);font-size:0.82rem;padding:20px;">D3.js no disponible.</p>';
    return null;
  }

  // Any sequence (other than the original) attached to the virtual source = synthesized.
  const hasSynth = nodes.some((_, i) => i > 0 && tree.parent[i] === -1);

  const data = [];
  if (hasSynth) data.push({ id: 'S', parentId: '', name: '⚙ Síntesis', cost: null, kind: 'source' });
  nodes.forEach((nd, i) => {
    const fromSource = tree.parent[i] === -1;
    data.push({
      id: 'n' + i,
      parentId: fromSource ? (hasSynth ? 'S' : '') : 'n' + tree.parent[i],
      name: nd.name || nd.id,
      cost: tree.cost[i],
      kind: i === 0 ? 'original' : (fromSource ? 'synth' : 'mut'),
    });
  });

  let hierarchy;
  try {
    hierarchy = d3.stratify().id(d => d.id).parentId(d => d.parentId || null)(data);
  } catch (e) {
    container.innerHTML = `<p style="color:var(--red);font-family:var(--mono);font-size:0.82rem;padding:20px;">No se pudo construir el árbol: ${e.message}</p>`;
    return null;
  }

  const rowH = 38, colW = 210;
  d3.tree().nodeSize([rowH, colW])(hierarchy);

  let minX = Infinity, maxX = -Infinity, maxY = 0;
  hierarchy.each(d => { minX = Math.min(minX, d.x); maxX = Math.max(maxX, d.x); maxY = Math.max(maxY, d.y); });

  const M = { top: 22, right: 160, bottom: 22, left: 80 };
  const W = M.left + maxY + M.right;
  const H = M.top + (maxX - minX) + M.bottom;

  const svg = d3.select(container).append('svg')
    .attr('xmlns', 'http://www.w3.org/2000/svg')
    .attr('width', W).attr('height', H)
    .style('display', 'block');
  svg.append('rect').attr('width', W).attr('height', H).attr('fill', '#F2F7FE').attr('rx', 10);

  const g = svg.append('g').attr('transform', `translate(${M.left},${M.top - minX})`);

  const edgeColor = d => {
    const k = d.target.data.kind;
    if (k === 'original') return '#9AA7B5';
    if (k === 'synth') return MUT_SYNTH_COLOR;
    return mutagenCostColor(d.target.data.cost);
  };
  const edgeLabel = d => {
    const k = d.target.data.kind;
    if (k === 'original') return 'base';
    if (k === 'synth') return `síntesis (${mutagenFmt(tree.synthCost)})`;
    const c = d.target.data.cost;
    return c === 0 ? '0' : `${c} cambio${c !== 1 ? 's' : ''}`;
  };

  // Links
  g.selectAll('path.mut-link').data(hierarchy.links()).join('path')
    .attr('fill', 'none')
    .attr('stroke', edgeColor)
    .attr('stroke-width', 2)
    .attr('stroke-dasharray', d => d.target.data.kind === 'synth' ? '5,4' : null)
    .attr('opacity', 0.8)
    .attr('d', d3.linkHorizontal().x(d => d.y).y(d => d.x));

  // Edge labels
  g.selectAll('text.mut-elabel').data(hierarchy.links()).join('text')
    .attr('x', d => (d.source.y + d.target.y) / 2)
    .attr('y', d => (d.source.x + d.target.x) / 2 - 4)
    .attr('text-anchor', 'middle')
    .attr('font-family', MUT_MONO).attr('font-size', '9.5')
    .attr('font-weight', '700')
    .attr('fill', edgeColor)
    .text(edgeLabel);

  // Nodes
  const nodeFill = d => {
    if (d.data.kind === 'source') return MUT_SYNTH_COLOR;
    if (d.data.kind === 'original') return '#1E5FB8';
    if (d.data.kind === 'synth') return MUT_SYNTH_COLOR;
    return '#fff';
  };
  const nodeStroke = d => d.data.kind === 'synth' || d.data.kind === 'source' ? MUT_SYNTH_COLOR : '#1E5FB8';

  const node = g.selectAll('g.mut-node').data(hierarchy.descendants()).join('g')
    .attr('transform', d => `translate(${d.y},${d.x})`);
  node.append('circle')
    .attr('r', d => d.data.kind === 'source' ? 8 : 6)
    .attr('fill', nodeFill)
    .attr('stroke', nodeStroke).attr('stroke-width', 2);
  node.append('text')
    .attr('x', d => d.children ? -11 : 11)
    .attr('y', 4)
    .attr('text-anchor', d => d.children ? 'end' : 'start')
    .attr('font-family', MUT_MONO)
    .attr('font-size', d => d.data.kind === 'source' ? '11.5' : '11')
    .attr('font-weight', d => d.depth === 0 || d.data.kind === 'synth' ? '800' : '600')
    .attr('fill', d => {
      if (d.data.kind === 'source') return MUT_SYNTH_COLOR;
      if (d.data.kind === 'synth') return '#5B3FA8';
      if (d.data.kind === 'original') return '#1E5FB8';
      return '#0D1F3C';
    })
    .text(d => d.data.name);

  return svg.node();
}

// ── Init ──────────────────────────────────────────────────────────────────────
renderSidebar();
