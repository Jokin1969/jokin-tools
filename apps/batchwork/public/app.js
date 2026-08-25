'use strict';

// ── Operations definition ─────────────────────────────────────────────────────
const OPERATIONS = [
  {
    group: 'Folder tools',
    key: 'folder',
    ops: [
      {
        id: 'inventory',
        label: 'Inventariar carpetas',
        desc: 'Genera un fichero Excel con el inventario del primer nivel de la carpeta seleccionada.',
        folderMode: true,
        params: [],
      },
      {
        id: 'rename',
        label: 'Renombrar por orden de lista',
        desc: 'Renombra un lote de ficheros según el ORDEN: el fichero N (por orden de nombre) toma el nombre N de la lista (un nombre por línea, .txt).',
        uploadPaired: true,
        params: [
          { id: 'keepExtension', type: 'checkbox', label: 'Conservar extensión original', default: true },
        ],
      },
      {
        id: 'rename-pairs',
        label: 'Renombrar por parejas (nombre → nombre)',
        desc: 'Renombra emparejando cada fichero con un listado de parejas «nombre actual → nombre nuevo». Solo se renombran los ficheros cuyo nombre coincida con una pareja (sin distinguir mayúsculas); los demás se omiten. No hace falta que haya tantas parejas como ficheros.',
        uploadPairs: true,
        params: [],
      },
    ],
  },
  {
    group: 'Image tools',
    key: 'image',
    ops: [
      {
        id: 'transparent-png',
        label: 'Transparentar PNG',
        desc: 'Convierte el fondo claro a transparente, preservando los píxeles oscuros.',
        params: [
          { id: 'threshold', type: 'range', label: 'Umbral de negro (0–255)', min: 0, max: 255, default: 60 },
        ],
      },
      {
        id: 'resize-tiff',
        label: 'Ajustar TIFF a 300 ppp',
        desc: 'Fija los TIFF a 300 ppp y reduce dimensiones si superan el tamaño máximo indicado.',
        params: [
          { id: 'maxMB', type: 'number', label: 'Tamaño máximo (MB)', default: 12, min: 1 },
        ],
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
    ],
  },
  {
    group: 'Document tools',
    key: 'document',
    ops: [
      {
        id: 'docx-to-pdf',
        label: 'DOCX → PDF',
        desc: 'Convierte ficheros .docx a .pdf usando LibreOffice headless.',
        params: [],
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
        label: 'Unir documentos en un PDF',
        desc: 'Une en un único PDF cualquier mezcla de PDFs, documentos de Office (.docx, .doc, .odt, .rtf, .txt, .pptx, .ppt, .odp, .xlsx, .xls, .ods) e imágenes (JPG, PNG, WEBP, TIFF, GIF, BMP). Cada documento no-PDF se convierte a PDF automáticamente. Se unen en orden alfabético del nombre: para controlar el orden, numera los ficheros (01_, 02_, 03_…).',
        params: [
          { id: 'outputName', type: 'text', label: 'Nombre del PDF resultante', default: 'unificado.pdf' },
          { id: 'resolution', type: 'number', label: 'Resolución de las imágenes (ppp)', default: 150, min: 72, max: 600 },
        ],
      },
      {
        id: 'split-pdfs',
        label: 'Dividir PDFs',
        desc: 'Divide cada PDF en páginas sueltas, pares/impares, bloques de N páginas, o un patrón personalizado de tamaños (ej. 3,2,2,1).',
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
              { value: 'pattern', label: 'Patrón personalizado (ej. 3,2,2,1)' },
            ],
          },
          { id: 'blockSize', type: 'number', label: 'N (tamaño del bloque)', default: 4, min: 1, conditional: 'splitMode=blocksN' },
          { id: 'pattern', type: 'text', label: 'Patrón de bloques — páginas por bloque, separadas por comas', default: '', placeholder: 'ej. 3,2,2,1 (para un PDF de 8 páginas)', conditional: 'splitMode=pattern' },
          {
            id: 'grouping', type: 'select', label: 'Organización de los archivos de salida', default: 'byFile',
            options: [
              { value: 'byFile',  label: 'Una carpeta por fichero (con sus bloques dentro)' },
              { value: 'byBlock', label: 'Una carpeta por bloque (con todos los ficheros dentro, mismo nombre)' },
            ],
          },
        ],
      },
    ],
  },
  {
    group: 'Laboratory tools',
    key: 'lab',
    ops: [
      {
        id: 'degen-aa',
        label: 'Generar secuencia de AA degenerada',
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
        label: 'Árbol para solicitar mutagénesis',
        desc: 'Compara secuencias derivadas frente a una original y calcula la ruta de síntesis más barata. Las mutaciones que caen dentro de una misma ventana de N nucleótidos cuentan como un único cambio (lo que la empresa factura como un cambio), de modo que algunas secuencias se sintetizan a partir de otras para abaratar el pedido.',
        clientSide: true,
        params: [],
      },
      {
        id: 'dna-replace',
        label: 'Generar plásmidos .dna (SnapGene)',
        desc: 'Carga un fichero .dna de SnapGene, sustituye una región de nucleótidos por otra y descarga un nuevo .dna. Opcionalmente añade una feature para la secuencia entrante, borra la feature solapada, reajusta las coordenadas de las features posteriores y cambia el nombre interno del documento. En «Varias (bulk)» puedes pegar tú las secuencias o, dada una posición del ORF, generar automáticamente sus 19 variantes aminoacídicas (codón óptimo humano).',
        clientSide: true,
        params: [],
      },
      {
        id: 'shmir-design',
        label: 'Diseñar shmiRs (3′UTR → oligos)',
        desc: 'Sube el 3′UTR de una especie, o el de dos para compararlas (el nombre de cada '
            + 'fichero da el nombre de la especie). Trocea en ventanas de 22 nt, aplica los '
            + 'filtros biofísicos, excluye las zonas de poliadenilación, busca bloques '
            + 'idénticos entre las dos especies y selecciona candidatos con espaciado mínimo '
            + 'y cuota por tercio. Devuelve un ZIP con: TSV de todas las ventanas (un estado '
            + 'por filtro), TSV de seleccionados, FASTA de guías para BLAST, TSV de oligos de '
            + '97 nt con el andamio miR-E, e informe de texto. Mientras falten miRBase, '
            + 'gnomAD, BLAST y rmsk, los candidatos salen como INCOMPLETE: el informe dice '
            + 'qué filtros no se ejecutaron.',
        params: [
          { id: 'candidates', type: 'number', label: 'Candidatos por especie (por defecto: 6)', default: 6, min: 1, max: 100 },
          { id: 'minSpacing', type: 'number', label: 'Espaciado mínimo entre sitios, nt (por defecto: 50)', default: 50, min: 0 },
          { id: 'minBlock', type: 'number', label: 'Longitud mínima de bloque conservado, nt (por defecto: 15)', default: 15, min: 4 },
          { id: 'gcMin', type: 'number', label: 'GC mínimo (por defecto: 0.30)', default: 0.30, min: 0, max: 1, step: 0.01 },
          { id: 'gcMax', type: 'number', label: 'GC máximo (por defecto: 0.52)', default: 0.52, min: 0, max: 1, step: 0.01 },
          { id: 'maxHomopolymer', type: 'number', label: 'Homopolímero máximo (por defecto: 3)', default: 3, min: 1, max: 22 },
          { id: 'minAsymmetry', type: 'number', label: 'Asimetría mínima, kcal/mol (por defecto: 0.5)', default: 0.5, step: 0.1 },
          { id: 'polyaFlank', type: 'number', label: 'Flanco prohibido junto a la señal polyA, nt (por defecto: 10)', default: 10, min: 0, max: 200 },
          { id: 'cdsInicio', type: 'number', label: 'CDS: inicio en el transcrito (vacío = la secuencia ya es el 3′UTR)', default: '', min: 1 },
          { id: 'cdsFin', type: 'number', label: 'CDS: fin en el transcrito', default: '', min: 1 },
          { id: 'bootstrapSeeds', type: 'checkbox', label: 'Filtrar seeds con la lista de arranque de 12 miRNAs (mecánica, NO filtro real)', default: false },
          { id: 'bloques', type: 'checkbox', label: 'Generar los bloques listos para pedir (módulo NheI–SacI de 149 nt y cassette MluI–AgeI de 318 pb, con hoja de pedido)', default: false },
        ],
      },
      {
        id: 'dna-gb-compare',
        label: 'Comparar secuencias .dna vs .gb (verificar proveedor)',
        desc: 'Verifica que el plásmido que te fabrica el proveedor (GenScript, .gb) coincide exactamente con el que diseñaste en SnapGene (.dna), nucleótido a nucleótido. Dos modos: emparejar por nombre muchos ficheros a la vez, o comparar una sola pareja (un .dna y un .gb) aunque tengan nombres distintos.',
        fullCustom: 'dnacompare',
      },
    ],
  },
  {
    group: 'Miscelánea',
    key: 'misc',
    ops: [
      {
        id: 'watermark',
        label: 'Marca de agua (PDF e imágenes)',
        desc: 'Añade una marca de agua a PDFs (todas las páginas) e imágenes (JPG/PNG/WEBP/TIFF/GIF). Usa texto (deja uno estándar o escribe el tuyo) o sube una imagen/logo. Elige posición, tamaño, color e intensidad. Devuelve cada fichero en su mismo formato y calidad, con el nombre acabado en «_watermarked_».',
        uploadImageMark: true,
        params: [
          { id: 'text', type: 'text', label: 'Texto (si no subes logo)', default: 'CONFIDENCIAL', placeholder: 'CONFIDENCIAL' },
          {
            id: 'layout', type: 'select', label: 'Posición / repetición', default: 'diagonal',
            options: [
              { value: 'diagonal', label: 'Diagonal (una grande)' },
              { value: 'diagonal-rep', label: 'Diagonal repetida' },
              { value: 'mosaico', label: 'Mosaico (rejilla)' },
              { value: 'centro', label: 'Centro' },
              { value: 'pie', label: 'Pie de página' },
              { value: 'esquina', label: 'Esquina inferior' },
            ],
          },
          {
            id: 'size', type: 'select', label: 'Tamaño', default: 'mediana',
            options: [
              { value: 'pequeña', label: 'Pequeña' },
              { value: 'mediana', label: 'Mediana' },
              { value: 'grande', label: 'Grande' },
            ],
          },
          {
            id: 'color', type: 'select', label: 'Color (solo texto)', default: 'gris',
            options: [
              { value: 'gris', label: 'Gris' },
              { value: 'rojo', label: 'Rojo' },
              { value: 'azul', label: 'Azul' },
              { value: 'negro', label: 'Negro' },
            ],
          },
          { id: 'intensity', type: 'range', label: 'Intensidad (%)', min: 5, max: 60, default: 25 },
          { id: 'rotation', type: 'range', label: 'Rotación (° · 0 = automática)', min: -90, max: 90, default: 0 },
        ],
        presets: [
          { label: '🔴 CONFIDENCIAL', values: { text: 'CONFIDENCIAL', layout: 'diagonal', size: 'grande', color: 'rojo', intensity: 35, rotation: 0 } },
          { label: 'BORRADOR', values: { text: 'BORRADOR', layout: 'diagonal', size: 'mediana', color: 'gris', intensity: 30, rotation: 0 } },
          { label: 'COPIA (mosaico)', values: { text: 'COPIA', layout: 'mosaico', size: 'pequeña', color: 'gris', intensity: 20, rotation: 0 } },
        ],
      },
      {
        id: 'qr',
        label: 'QRs',
        desc: 'Genera códigos QR personalizados a partir de una URL: estilos, color, logo central y marco con etiqueta. Expórtalos en PNG, JPEG, WEBP, SVG o PDF, cópialos, envíalos por email y guárdalos en tu repositorio.',
        // Bespoke UI mounted from qr.js — bypasses the generic upload/execute flow.
        fullCustom: 'qr',
      },
      {
        id: 'sello',
        label: 'Generar sellos',
        desc: 'Diseña sellos digitales tipo imprenta: redondos, ovalados o rectangulares, con texto que bordea el emblema (arriba y abajo), texto o logo central, color de tinta y texturas realistas (como un sello físico escaneado). Expórtalos con fondo transparente en PNG, JPEG, WEBP, SVG o PDF, cópialos, envíalos por email y guárdalos en tu repositorio.',
        // Bespoke UI mounted from stamp.js — bypasses the generic upload/execute flow.
        fullCustom: 'stamp',
      },
      {
        id: 'pdfqa',
        label: 'Preguntar a un PDF (IA)',
        desc: 'Sube un PDF grande (incluso de miles de páginas, texto real — no escaneado) y «digiérelo» una vez: se extrae el texto de cada página, se trocea y se indexa con IA. Después pregunta en lenguaje natural y la IA te responde citando las páginas exactas. Los documentos digeridos quedan guardados para volver a preguntar cuando quieras.',
        // Bespoke UI — bypasses the generic upload/execute flow.
        fullCustom: 'pdfqa',
      },
    ],
  },
];

// Flat map for quick lookup
const OPS_MAP = {};
for (const group of OPERATIONS) {
  for (const op of group.ops) OPS_MAP[op.id] = op;
}

// ── Sub-feature access ──────────────────────────────────────────────────────────
// The admin can restrict a user to a subset of tools. The server tells us which
// features are allowed (loadConfig); we hide the rest. Each tool maps to one
// access-feature. `null` = not loaded yet / full access → show everything.
const OP_FEATURE = {
  inventory: 'folder', rename: 'folder', 'rename-pairs': 'folder',
  'transparent-png': 'image', 'resize-tiff': 'image', 'images-to-pdf': 'image',
  'docx-to-pdf': 'document', 'pdf-to-docx': 'document', 'normalize-dni': 'document',
  'merge-pdfs': 'document', 'split-pdfs': 'document',
  'degen-aa': 'lab', 'plddt-kde': 'lab', 'mutagen-tree': 'lab', 'dna-replace': 'lab', 'dna-gb-compare': 'lab',
  watermark: 'watermark', qr: 'qr', sello: 'stamp', pdfqa: 'pdfqa',
};
let ALLOWED_FEATURES = null;   // Set of allowed feature ids, or null = show all
function opAllowed(opId) {
  if (!ALLOWED_FEATURES) return true;
  const f = OP_FEATURE[opId];
  return !f || ALLOWED_FEATURES.has(f);
}

// Upload limit — the server is the single source of truth (BATCHWORK_MAX_UPLOAD_MB).
// These defaults are replaced by loadConfig() on startup so client and server
// never drift.
let MAX_MB = 500;
let MAX_BYTES = MAX_MB * 1024 * 1024;

async function loadConfig() {
  try {
    const r = await fetch('/batchwork/api/config');
    if (!r.ok) return;
    const c = await r.json();
    if (c.maxUploadMb) { MAX_MB = c.maxUploadMb; MAX_BYTES = MAX_MB * 1024 * 1024; }
    if (Array.isArray(c.features)) { ALLOWED_FEATURES = new Set(c.features); renderSidebar(); }
  } catch { /* keep defaults */ }
}

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  selectedOp: null,
  sessionId: null,
  files: [],          // File objects
  namelistFile: null, // File for op 'rename'
  pairsText: '',      // pasted/loaded pairs list for op 'rename-pairs'
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
// Collapsed-group state persists in localStorage so the user's layout sticks
// between visits. Default (no stored value) = every group expanded.
const SIDEBAR_STATE_KEY = 'bw:sidebar:collapsed';

function loadCollapsedGroups() {
  try {
    const raw = localStorage.getItem(SIDEBAR_STATE_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch { return new Set(); }
}
let collapsedGroups = loadCollapsedGroups();

function saveCollapsedGroups() {
  try { localStorage.setItem(SIDEBAR_STATE_KEY, JSON.stringify([...collapsedGroups])); } catch { /* ignore */ }
}

function toggleGroup(key) {
  if (collapsedGroups.has(key)) collapsedGroups.delete(key);
  else collapsedGroups.add(key);
  saveCollapsedGroups();
  renderSidebar();
}

function renderSidebar() {
  const sb = $('sidebar');
  sb.innerHTML = '';
  for (const group of OPERATIONS) {
    const ops = group.ops.filter(op => opAllowed(op.id));
    if (!ops.length) continue;                       // hide groups with no allowed tools
    const collapsed = collapsedGroups.has(group.key);
    const groupEl = mk('div', 'bw-sidebar-group' + (collapsed ? ' collapsed' : ''));

    const header = mk('button', 'bw-sidebar-group-label');
    header.type = 'button';
    header.setAttribute('aria-expanded', String(!collapsed));
    header.innerHTML = `<span class="bw-group-chevron" aria-hidden="true"></span><span class="bw-group-name">${group.group}</span>`;
    header.addEventListener('click', () => toggleGroup(group.key));
    groupEl.appendChild(header);

    const itemsEl = mk('div', 'bw-sidebar-group-items');
    for (const op of ops) {
      const btn = mk('button', 'bw-op-btn' + (state.selectedOp === op.id ? ' active' : ''), op.label);
      btn.dataset.opId = op.id;
      btn.addEventListener('click', () => selectOp(op.id));
      itemsEl.appendChild(btn);
    }
    groupEl.appendChild(itemsEl);
    sb.appendChild(groupEl);
  }
}

// ── Select operation ──────────────────────────────────────────────────────────
function selectOp(opId) {
  if (state.appStatus === 'running' || state.appStatus === 'uploading') return;
  if (!opAllowed(opId)) return;                      // not permitted for this user

  state.selectedOp = opId;
  state.files = [];
  state.namelistFile = null;
  state.pairsText = '';
  state.fileList = [];
  state.clientSideBlob = null;
  const prevResults = $('degen-results');
  if (prevResults) prevResults.remove();
  const prevPlddt = $('plddt-results');
  if (prevPlddt) prevPlddt.remove();
  const prevMutagen = $('mutagen-results');
  if (prevMutagen) prevMutagen.remove();
  const prevDnaRep = $('dna-replace-results');
  if (prevDnaRep) prevDnaRep.remove();
  resetExecuteBar();

  renderSidebar();

  $('placeholder').style.display = 'none';
  const content = $('op-content');
  content.style.display = 'flex';

  const op = OPS_MAP[opId];
  $('op-title').textContent = op.label;
  $('op-desc').textContent = op.desc;

  // Restore the execute bar (a previous fullCustom op may have hidden it).
  $('execute-bar').style.display = '';

  // Fully custom ops render their own panel and own controls — skip the generic
  // upload / params / execute machinery entirely.
  if (op.fullCustom) {
    $('upload-area').style.display = 'none';
    $('file-list-wrap').style.display = 'none';
    $('execute-bar').style.display = 'none';
    const zone = $('params-zone');
    zone.innerHTML = '';
    if (op.fullCustom === 'qr') {
      if (window.QRTool) window.QRTool.mount(zone);
      else zone.innerHTML = '<p style="color:#B83232">No se pudo cargar la herramienta de QRs.</p>';
    } else if (op.fullCustom === 'stamp') {
      if (window.StampTool) window.StampTool.mount(zone);
      else zone.innerHTML = '<p style="color:#B83232">No se pudo cargar la herramienta de sellos.</p>';
    } else if (op.fullCustom === 'dnacompare') {
      renderDnaCompareUI(zone);
    } else if (op.fullCustom === 'pdfqa') {
      renderPdfQaUI(zone);
    }
    return;
  }

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

  } else if (op.uploadPairs) {
    // Files + a pairs list (paste into a textarea or load a .txt)
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

    const panel = mk('div', 'bw-pairs-panel');
    panel.appendChild(mk('div', 'bw-pairs-label', 'Listado de parejas — pega el texto o carga un .txt'));
    const ta = document.createElement('textarea');
    ta.className = 'bw-input bw-textarea';
    ta.rows = 8;
    ta.placeholder = 'Una pareja por línea «nombre actual → nombre nuevo». Separador: tabulador, ->, ; o ,\nEl nombre va SIN extensión; los espacios valen y las comillas son opcionales.\nUna misma línea renombra todas las extensiones de ese nombre (.dna, .gb…).\n\npAAV 7OR I109I W145Y vole PrP\t6666\nIMG_002 -> luna_de_miel\nIMG_003;cena';
    ta.value = state.pairsText || '';
    ta.addEventListener('input', () => { state.pairsText = ta.value; updateExecuteBtn(); });
    panel.appendChild(ta);

    const loadRow = mk('div', 'bw-pairs-load');
    const loadBtn = mk('button', 'bw-btn-clear', 'Cargar .txt…');
    loadBtn.type = 'button';
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.txt,text/plain';
    fileInput.style.display = 'none';
    loadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
      const f = fileInput.files[0];
      if (!f) return;
      const reader = new FileReader();
      reader.onload = () => { ta.value = reader.result; state.pairsText = String(reader.result); updateExecuteBtn(); };
      reader.readAsText(f);
    });
    loadRow.appendChild(loadBtn);
    loadRow.appendChild(fileInput);
    panel.appendChild(loadRow);

    pair.appendChild(dropFiles);
    pair.appendChild(panel);
    area.appendChild(pair);
    $('file-list-wrap').style.display = '';

  } else if (op.uploadImageMark) {
    // Files to watermark + an optional logo/image mark.
    const pair = mk('div', 'bw-upload-pair');
    const dropFiles = makeDropZone({
      label: 'PDFs e imágenes a marcar',
      sub: 'Drag & drop o clic · varios a la vez',
      multiple: true,
      onFiles: (files) => {
        state.files = [...state.files, ...files].slice(0, 5000);
        state.files.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));
        updateFileList();
        updateExecuteBtn();
      },
    });
    const dropLogo = makeDropZone({
      label: 'Imagen/logo de marca (opcional)',
      sub: 'PNG con transparencia recomendado · si no, se usa el texto',
      accept: 'image/*',
      multiple: false,
      onFiles: (files) => {
        if (files[0]) {
          state.namelistFile = files[0];
          const badge = dropLogo.querySelector('.bw-drop-text');
          if (badge) badge.textContent = `✓ ${files[0].name}`;
        }
        updateExecuteBtn();
      },
    });
    pair.appendChild(dropFiles);
    pair.appendChild(dropLogo);
    area.appendChild(pair);
    $('file-list-wrap').style.display = '';

  } else {
    // Standard single drop zone
    const drop = makeDropZone({
      label: 'Arrastrar ficheros aquí',
      sub: `o clic para seleccionar · máx. ${MAX_MB} MB por lote`,
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
  if (op.id === 'dna-replace') { renderDnaReplaceUI(); return; }

  if (!op.params || op.params.length === 0) return;

  // Init defaults
  for (const p of op.params) {
    if (getParam(op.id, p.id) === undefined) {
      setParam(op.id, p.id, p.default ?? '');
    }
  }

  // One-click presets (rendered above the params).
  if (op.presets && op.presets.length) {
    const row = mk('div', 'bw-preset-row');
    row.appendChild(mk('span', 'bw-preset-label', 'Preajustes:'));
    for (const preset of op.presets) {
      const b = mk('button', 'bw-preset-btn', preset.label);
      b.type = 'button';
      b.addEventListener('click', () => {
        for (const [k, v] of Object.entries(preset.values)) setParam(op.id, k, v);
        renderParams(op);
        updateExecuteBtn();
      });
      row.appendChild(b);
    }
    zone.appendChild(row);
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
    if (p.max !== undefined) input.max = p.max;
    if (p.step !== undefined) input.step = p.step;
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
    if (p.placeholder) input.placeholder = p.placeholder;
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
    } else if (op.id === 'dna-replace') {
      const hasFile = !!dnaReplaceInput.file;
      const hasOld = dnaReplaceInput.oldSeq.trim().length > 0;
      if (dnaReplaceInput.bulkMode && dnaReplaceInput.bulkSubmode === 'saturate') {
        const st = dnaSatState();
        const n = st.constructs ? st.constructs.length : 0;
        ready = hasFile && !st.error && n > 0;
        if (!hasFile)        setStatus('Carga un fichero .dna de SnapGene', '');
        else if (st.error)   setStatus(st.error, '');
        else if (!n)         setStatus('Selecciona al menos una variante', '');
        else if (st.mode === 'list') setStatus(`${n} sustitución(es) lista(s) para generar`, '');
        else setStatus(`${n} variante(s) de ${st.parsed.orig}${String(st.parsed.pos).padStart(3, '0')} lista(s) para generar`, '');
      } else if (dnaReplaceInput.bulkMode) {
        const validRows = dnaParseBulk(dnaReplaceInput.bulkText, dnaReplaceInput.bulkHeader).filter(r => r.valid).length;
        ready = hasFile && hasOld && validRows > 0;
        if (!hasFile)         setStatus('Carga un fichero .dna de SnapGene', '');
        else if (!hasOld)     setStatus('Falta: la secuencia a sustituir (común a todas)', '');
        else if (!validRows)  setStatus('Pega al menos una fila con secuencia nueva en el cuadro de bulk', '');
        else setStatus(`${validRows} secuencia(s) lista(s) para procesar en bulk`, '');
      } else {
        const hasNew = dnaReplaceInput.newSeq.trim().length > 0;
        const needsName = dnaReplaceInput.renameDoc && !dnaReplaceInput.docName.trim();
        ready = hasFile && hasOld && hasNew && !needsName;
        if (!hasFile)       setStatus('Carga un fichero .dna de SnapGene', '');
        else if (!hasOld)   setStatus('Falta: la secuencia de nucleótidos a sustituir', '');
        else if (!hasNew)   setStatus('Falta: la secuencia nueva con la que sustituir', '');
        else if (needsName) setStatus('Falta: el nombre interno del documento (o desmarca «Cambiar el nombre interno»)', '');
        else setStatus('', '');
      }
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
  } else if (op.uploadPairs) {
    const hasFiles = state.files.length > 0;
    const hasPairs = (state.pairsText || '').trim().length > 0;
    ready = hasFiles && hasPairs;
    if (!hasFiles && !hasPairs) setStatus('Carga los ficheros y pega/carga el listado de parejas', '');
    else if (!hasFiles)         setStatus('Falta: arrastra los ficheros a renombrar', '');
    else if (!hasPairs)         setStatus('Falta: el listado de parejas (pega el texto o carga un .txt)', '');
    else                        setStatus('', '');
  } else if (op.uploadImageMark) {
    ready = state.files.length > 0; // el logo es opcional
    if (!ready) setStatus('Arrastra los PDFs/imágenes a marcar', '');
    else setStatus(state.namelistFile ? 'Marca con imagen/logo' : 'Marca con texto', '');
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
  // The pairs list rides the same 'nameList' channel (server renames it to
  // _namelist_.txt); we turn the pasted/loaded text into a file here.
  if (op.uploadPairs && (state.pairsText || '').trim()) {
    formData.append('nameList', new Blob([state.pairsText], { type: 'text/plain' }), '_pairs_.txt');
  }
  // The optional logo/image mark rides the same 'nameList' channel.
  if (op.uploadImageMark && state.namelistFile) {
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

    } else if (data.status === 'cancelled') {
      // Cancelled by the user mid-operation: no result to download, just reset
      // so they can run again.
      clearPoll();
      state.appStatus = 'idle';
      setStatus('Operación cancelada', 'err');
      $('btn-execute').style.display = '';
      $('btn-download').style.display = 'none';
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

    try {
      const r = await fetch(`/batchwork/api/session/${sessionId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(decision),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.error || `Error ${r.status}`);
      }
      startPoll(sessionId);
    } catch (err) {
      // Don't leave the UI stuck on "Reanudando…" if the request fails.
      state.appStatus = 'error';
      setStatus(`No se pudo reanudar: ${err.message}`, 'err');
      $('btn-execute').disabled = false;
    }
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
  const existingDnaRep = $('dna-replace-results');
  if (existingDnaRep) existingDnaRep.remove();
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
    if (op.id === 'dna-replace') {
      await runDnaReplace(op);
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

// ── SnapGene .dna sequence replacer ───────────────────────────────────────────
//
// A SnapGene .dna file is a sequence of TLV packets: [1 byte type][4 bytes
// big-endian length][payload]. Relevant packets:
//   type 9  — cookie: payload starts with ASCII "SnapGene"
//   type 0  — DNA: 1 flags byte (bit 0 = circular) + ASCII bases
//   type 10 — features: XML <Features><Feature><Segment range="a-b"/></Feature>…
//             (coordinates are 1-based, inclusive)
//   type 6  — notes: XML <Notes>…; the displayed name is the "custom map label"
// We edit the DNA packet (the swap), the features XML (delete/shift/add) and the
// notes XML (name), keep every other packet byte-for-byte, and re-serialise.

let dnaReplaceInput = {
  file: null,        // { name, bytes: Uint8Array, info }
  oldSeq: '',
  newSeq: '',
  addFeature: true,
  featName: '',
  featType: 'CDS',
  featColor: '#a6acb3',
  deleteOverlap: true,
  shiftCoords: true,
  renameDoc: true,
  docName: '',
  bulkMode: false,
  bulkText: '',
  bulkHeader: false,
  // Saturation sub-mode (auto-generate amino-acid variants at one ORF position).
  bulkSubmode: 'manual',   // 'manual' | 'saturate'
  satPos: '',              // e.g. "168" or "G168"
  satAAs: null,            // array of selected AA letters (null = all 19 by default)
  satKey: '',              // position identity the current satAAs belong to
  satPrefix: '',           // optional file-name prefix (e.g. "pAAV_")
  satSuffix: '',           // optional text after the mutation (e.g. " vole PrP")
  satAddFeat: true,        // rename the CDS feature (name it per variant)
  satFeatPrefix: '',       // optional feature-name prefix
  satFeatSuffix: '',       // optional feature-name suffix
  satHasSignal: true,      // does the gene include its signal peptide?
  satSignalLen: '',        // signal-peptide length (aa) when it's absent
  satVariantMode: 'position', // 'position' (19 AAs at one pos) | 'list' (specific changes)
  satList: '',             // comma-separated substitutions (e.g. "G223A, D45V")
  satListSel: null,        // selected substitution names (null = all valid)
  satListKey: '',          // identity of the current valid list (to reset selection)
};

const DNA_FEATURE_TYPES = [
  'misc_feature', 'CDS', 'gene', 'promoter', 'terminator', 'RBS',
  'primer_bind', 'protein_bind', 'rep_origin', 'misc_RNA', 'mat_peptide', 'sig_peptide',
];

const dnaCleanSeq = s => (s || '').toUpperCase().replace(/[^ACGTUNRYSWKMBDHV]/g, '');

// Download filename for the resulting .dna. Keeps spaces and accented letters
// intact; only strips characters that are illegal in filenames.
function dnaSafeDownloadName(name) {
  let base = String(name || '').trim().replace(/\.dna$/i, '');
  base = base.replace(/[\\/:*?"<>|\x00-\x1f]/g, '').replace(/\s+/g, ' ').trim();
  if (!base) base = 'documento';
  return base + '.dna';
}

// ── Binary layer (pure, no DOM) ───────────────────────────────────────────────
function dnaParsePackets(bytes) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const packets = [];
  let off = 0;
  while (off + 5 <= bytes.length) {
    const type = dv.getUint8(off);
    const len = dv.getUint32(off + 1, false);
    const start = off + 5;
    const end = start + len;
    if (end > bytes.length) throw new Error('Fichero .dna corrupto o incompleto (paquete fuera de rango).');
    packets.push({ type, data: bytes.slice(start, end) });
    off = end;
  }
  if (off !== bytes.length) throw new Error('Fichero .dna con bytes sobrantes; ¿formato no reconocido?');
  return packets;
}

function dnaValidateCookie(packets) {
  const c = packets[0];
  if (!c || c.type !== 9 || c.data.length < 8) {
    throw new Error('No parece un .dna de SnapGene (falta la cabecera "cookie").');
  }
  const tag = String.fromCharCode(...c.data.slice(0, 8));
  if (tag !== 'SnapGene') throw new Error('Cabecera SnapGene no encontrada; ¿es un .dna válido?');
}

function dnaSerialize(packets) {
  let total = 0;
  for (const p of packets) total += 5 + p.data.length;
  const out = new Uint8Array(total);
  const dv = new DataView(out.buffer);
  let off = 0;
  for (const p of packets) {
    dv.setUint8(off, p.type); off += 1;
    dv.setUint32(off, p.data.length, false); off += 4;
    out.set(p.data, off); off += p.data.length;
  }
  return out;
}

function dnaBytesToAscii(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i += 8192) {
    s += String.fromCharCode(...bytes.subarray(i, i + 8192));
  }
  return s;
}
function dnaAsciiToBytes(s) {
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i) & 0xff;
  return out;
}

// ── XML helpers (browser DOM) ─────────────────────────────────────────────────
function dnaReserializeXml(originalStr, doc) {
  let out = new XMLSerializer().serializeToString(doc);
  const decl = (originalStr.match(/^\s*<\?xml[^>]*\?>/i) || [])[0];
  if (decl && !/^\s*<\?xml/i.test(out)) out = decl + out;
  return out;
}

// Edit the features XML: delete features overlapping the replaced region, shift
// the coordinates of features located after it, and append a feature for the new
// sequence. Returns { xml, removed, shifted, added }.
function dnaEditFeaturesXml(xmlStr, opts) {
  const { rStart, rEnd, delta, deleteOverlap, shiftCoords, addFeature, featName, featType, featColor, newStart, newEnd, renameCdsName } = opts;
  const doc = new DOMParser().parseFromString(xmlStr, 'application/xml');
  if (doc.getElementsByTagName('parsererror').length) return { xml: xmlStr, removed: 0, shifted: 0, added: false, renamed: false };
  const root = doc.documentElement;
  if (!root || root.nodeName !== 'Features') return { xml: xmlStr, removed: 0, shifted: 0, added: false, renamed: false };

  let removed = 0, shifted = 0;
  for (const f of Array.from(root.getElementsByTagName('Feature'))) {
    const segs = Array.from(f.getElementsByTagName('Segment'))
      .map(s => {
        const m = (s.getAttribute('range') || '').match(/^(\d+)\s*-\s*(\d+)$/);
        return m ? { el: s, a: +m[1], b: +m[2] } : null;
      })
      .filter(Boolean);
    if (!segs.length) continue;

    const fmin = Math.min(...segs.map(s => s.a));
    const fmax = Math.max(...segs.map(s => s.b));
    const overlaps = !(fmax < rStart || fmin > rEnd);

    if (overlaps && deleteOverlap) { f.parentNode.removeChild(f); removed++; continue; }

    if (shiftCoords && delta !== 0) {
      let did = false;
      for (const s of segs) {
        if (s.a > rEnd) { s.el.setAttribute('range', `${s.a + delta}-${s.b + delta}`); did = true; }
      }
      if (did) shifted++;
    }
  }

  let added = false, renamed = false;

  // Rename mode: instead of adding a feature, rename the existing CDS that covers
  // the region (so no two features stack on the same span). If there is no such
  // CDS, fall back to adding one.
  if (renameCdsName) {
    let target = null;
    for (const f of Array.from(root.getElementsByTagName('Feature'))) {
      if ((f.getAttribute('type') || '').toLowerCase() !== 'cds') continue;
      const segs = Array.from(f.getElementsByTagName('Segment'))
        .map(s => { const m = (s.getAttribute('range') || '').match(/^(\d+)\s*-\s*(\d+)$/); return m ? { a: +m[1], b: +m[2] } : null; })
        .filter(Boolean);
      if (!segs.length) continue;
      const fmin = Math.min(...segs.map(s => s.a)), fmax = Math.max(...segs.map(s => s.b));
      if (!(fmax < newStart || fmin > newEnd)) { target = f; break; }
    }
    if (target) { target.setAttribute('name', renameCdsName); renamed = true; }
    else if (newEnd >= newStart) {
      const f = doc.createElement('Feature');
      f.setAttribute('name', renameCdsName); f.setAttribute('type', 'CDS'); f.setAttribute('directionality', '1');
      const seg = doc.createElement('Segment');
      seg.setAttribute('range', `${newStart}-${newEnd}`); seg.setAttribute('type', 'standard'); seg.setAttribute('color', featColor || '#a6acb3');
      f.appendChild(seg); root.appendChild(f); added = true;
    }
  } else if (addFeature && newEnd >= newStart) {
    const f = doc.createElement('Feature');
    f.setAttribute('name', featName || 'secuencia_nueva');
    f.setAttribute('type', featType || 'misc_feature');
    f.setAttribute('directionality', '1');
    const seg = doc.createElement('Segment');
    seg.setAttribute('range', `${newStart}-${newEnd}`);
    seg.setAttribute('type', 'standard');
    seg.setAttribute('color', featColor || '#a6acb3');
    f.appendChild(seg);
    root.appendChild(f);
    added = true;
  }

  return { xml: dnaReserializeXml(xmlStr, doc), removed, shifted, added, renamed };
}

function dnaSetNotesName(xmlStr, name) {
  const doc = new DOMParser().parseFromString(xmlStr, 'application/xml');
  if (doc.getElementsByTagName('parsererror').length) return xmlStr;
  const root = doc.documentElement;
  if (!root || root.nodeName !== 'Notes') return xmlStr;
  const setEl = (tag, val) => {
    let el = root.getElementsByTagName(tag)[0];
    if (!el) { el = doc.createElement(tag); root.appendChild(el); }
    el.textContent = val;
  };
  setEl('CustomMapLabel', name);
  setEl('UseCustomMapLabel', '1');
  return dnaReserializeXml(xmlStr, doc);
}

function dnaBuildNotesPacket(name) {
  const xml = `<?xml version="1.0" encoding="UTF-8"?><Notes><UseCustomMapLabel>1</UseCustomMapLabel><CustomMapLabel>${name.replace(/[<&>]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]))}</CustomMapLabel></Notes>`;
  return { type: 6, data: new TextEncoder().encode(xml) };
}

// ── Document repository (server-side, persistent volume) ──────────────────────
let dnaLibCache = null; // last fetched list, for "already saved?" checks

async function dnaLibList() {
  const res = await fetch('/batchwork/api/library/dna');
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || 'No se pudo leer el repositorio.');
  const data = await res.json();
  dnaLibCache = data.documents || [];
  return dnaLibCache;
}
async function dnaLibSave(name, bytes) {
  const fd = new FormData();
  fd.append('name', name);
  fd.append('file', new Blob([bytes], { type: 'application/octet-stream' }), name);
  const res = await fetch('/batchwork/api/library/dna', { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'No se pudo guardar el documento.');
  return data.document;
}
async function dnaLibDelete(name) {
  const res = await fetch('/batchwork/api/library/dna/' + encodeURIComponent(name), { method: 'DELETE' });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || 'No se pudo borrar el documento.');
}
async function dnaLibFetchBytes(name) {
  const res = await fetch('/batchwork/api/library/dna/' + encodeURIComponent(name), { headers: { Accept: 'application/octet-stream' } });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); if (j && j.error) msg = `${j.error} (HTTP ${res.status})`; } catch { /* not JSON */ }
    if (res.status === 401) msg = 'Sesión caducada: recarga la página e inicia sesión de nuevo.';
    throw new Error(msg);
  }
  const buf = await res.arrayBuffer();
  if (!buf || buf.byteLength === 0) throw new Error('el servidor devolvió una respuesta vacía');
  return new Uint8Array(buf);
}
// Mirror of the server name sanitiser, to know if a freshly loaded file already
// matches a stored document (and skip the "save?" prompt).
function dnaSafeName(name) {
  let base = (String(name || '').split(/[\\/]/).pop() || '').trim().replace(/\.dna$/i, '');
  base = base.replace(/[^\p{L}\p{N}.\- ()\[\]]+/gu, '_').replace(/_{2,}/g, '_').replace(/^[_.\s]+|[_.\s]+$/g, '');
  if (!base) base = 'documento';
  return base.slice(0, 120) + '.dna';
}

// Parse loaded .dna bytes; returns { info, error } without touching state.
function dnaParseLoaded(bytes) {
  try {
    const packets = dnaParsePackets(bytes);
    dnaValidateCookie(packets);
    const dnaPkt = packets.find(p => p.type === 0);
    if (!dnaPkt) throw new Error('El fichero no contiene secuencia de ADN (paquete tipo 0).');
    const seq = dnaBytesToAscii(dnaPkt.data.slice(1));
    const featPkt = packets.find(p => p.type === 10);
    let nFeatures = 0;
    if (featPkt) nFeatures = (dnaBytesToAscii(featPkt.data).match(/<Feature\b/g) || []).length;
    return { info: { length: seq.length, circular: (dnaPkt.data[0] & 1) === 1, nFeatures }, error: null };
  } catch (e) { return { info: null, error: e.message }; }
}

// ── Input UI ──────────────────────────────────────────────────────────────────

function renderDnaReplaceUI() {
  const zone = $('params-zone');
  zone.innerHTML = '';
  const container = mk('div', 'bw-params');

  // File loader
  const fileField = mk('div', 'bw-field');
  fileField.appendChild(mk('label', null, 'Fichero .dna de SnapGene (original)'));
  const info = mk('div');
  info.style.cssText = `font-family:${MUT_MONO};font-size:0.74rem;color:var(--text-muted);margin-top:8px;line-height:1.6;`;
  const savePrompt = mk('div');   // "¿Guardar en el repositorio?" banner
  savePrompt.style.marginTop = '8px';
  const repoPanel = mk('div');    // list of stored documents

  // Apply a freshly loaded document (from disk or from the repository).
  function applyLoaded(name, bytes, fromRepo) {
    const { info: fi, error } = dnaParseLoaded(bytes);
    dnaReplaceInput.file = { name, bytes, fromRepo: !!fromRepo };
    const txt = drop.querySelector('.bw-drop-text');
    if (txt) txt.textContent = `✓ ${name}`;
    if (error) {
      info.innerHTML = `<span style="color:var(--red)">⚠ ${error}</span>`;
      savePrompt.innerHTML = '';
    } else {
      info.innerHTML = `<strong>${fi.length.toLocaleString('es-ES')} nt</strong> · ${fi.circular ? 'circular' : 'lineal'} · ${fi.nFeatures} feature${fi.nFeatures !== 1 ? 's' : ''}${fromRepo ? ' · <span style="color:var(--green)">📂 del repositorio</span>' : ''}`;
      renderSavePrompt(name, bytes, fromRepo);
    }
    updateExecuteBtn();
  }

  // Ask whether to keep a disk-loaded document in the repository.
  function renderSavePrompt(name, bytes, fromRepo) {
    savePrompt.innerHTML = '';
    const safe = dnaSafeName(name);
    const alreadyStored = (dnaLibCache || []).some(d => d.name === safe);
    if (fromRepo || alreadyStored) {
      if (alreadyStored && !fromRepo) {
        const ok = mk('div', null, '✓ Ya está guardado en el repositorio.');
        ok.style.cssText = 'font-size:0.78rem;color:var(--green);';
        savePrompt.appendChild(ok);
      }
      return;
    }
    const banner = mk('div');
    banner.style.cssText = 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:rgba(13,122,85,0.06);';
    const q = mk('div', null, `💾 ¿Guardar «${safe}» en el repositorio para reutilizarlo otras veces?`);
    q.style.cssText = 'font-size:0.8rem;flex:1;min-width:200px;';
    banner.appendChild(q);
    const yes = mk('button', 'bw-btn bw-btn-primary');
    yes.type = 'button';
    yes.style.cssText = 'font-size:0.76rem;padding:6px 14px;';
    yes.textContent = 'Guardar';
    const no = mk('button', 'bw-btn bw-btn-cancel');
    no.type = 'button';
    no.style.cssText = 'font-size:0.76rem;padding:6px 14px;';
    no.textContent = 'Ahora no';
    yes.addEventListener('click', async () => {
      yes.disabled = true; yes.textContent = 'Guardando…';
      try {
        await dnaLibSave(name, bytes);
        await dnaLibList();
        savePrompt.innerHTML = '<div style="font-size:0.78rem;color:var(--green)">✓ Guardado en el repositorio.</div>';
        refreshRepo();
      } catch (e) {
        yes.disabled = false; yes.textContent = 'Guardar';
        const err = mk('div', null, '⚠ ' + e.message);
        err.style.cssText = 'font-size:0.76rem;color:var(--red);flex-basis:100%;';
        banner.appendChild(err);
      }
    });
    no.addEventListener('click', () => { savePrompt.innerHTML = ''; });
    banner.appendChild(yes);
    banner.appendChild(no);
    savePrompt.appendChild(banner);
  }

  const drop = makeDropZone({
    label: dnaReplaceInput.file ? `✓ ${dnaReplaceInput.file.name}` : 'Arrastra o haz clic para elegir un .dna',
    sub: 'SnapGene · se procesa en tu navegador',
    accept: '.dna',
    multiple: false,
    onFiles: files => {
      if (!files[0]) return;
      info.textContent = 'Leyendo…';
      savePrompt.innerHTML = '';
      files[0].arrayBuffer().then(buf => applyLoaded(files[0].name, new Uint8Array(buf), false));
    },
  });
  fileField.appendChild(drop);
  fileField.appendChild(info);
  fileField.appendChild(savePrompt);
  if (dnaReplaceInput.file) {
    info.textContent = dnaReplaceInput.file.name;
  }

  // ── Repository panel ──────────────────────────────────────────────
  function refreshRepo() {
    repoPanel.innerHTML = '';
    const head = mk('div');
    head.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px;';
    const title = mk('label', null, '📂 Repositorio de documentos guardados');
    title.style.margin = '0';
    head.appendChild(title);
    repoPanel.appendChild(head);

    const listBox = mk('div');
    listBox.style.cssText = 'border:1px solid var(--border);border-radius:8px;overflow:hidden;';
    repoPanel.appendChild(listBox);

    const setMsg = (html, color) => {
      listBox.innerHTML = `<div style="padding:12px 14px;font-family:${MUT_MONO};font-size:0.76rem;color:${color || 'var(--text-muted)'}">${html}</div>`;
    };
    setMsg('Cargando…');

    dnaLibList().then(docs => {
      listBox.innerHTML = '';
      if (!docs.length) {
        setMsg('Aún no has guardado ningún documento. Cuando cargues un .dna te preguntaré si quieres guardarlo aquí.');
        return;
      }
      docs.forEach((d, i) => {
        const row = mk('div');
        row.style.cssText = `display:flex;align-items:center;gap:10px;padding:9px 12px;${i ? 'border-top:1px solid var(--border);' : ''}`;
        const meta = mk('div');
        meta.style.cssText = 'flex:1;min-width:0;';
        const kb = d.size >= 1024 ? `${(d.size / 1024).toFixed(0)} KB` : `${d.size} B`;
        const date = new Date(d.savedAt).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' });
        meta.innerHTML = `<div style="font-size:0.82rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${d.name}</div><div style="font-family:${MUT_MONO};font-size:0.7rem;color:var(--text-dim);">${kb} · ${date}</div>`;
        row.appendChild(meta);

        const load = mk('button', 'bw-btn bw-btn-cancel');
        load.type = 'button';
        load.style.cssText = 'font-size:0.74rem;padding:5px 12px;white-space:nowrap;';
        load.textContent = 'Cargar';
        load.addEventListener('click', async () => {
          load.disabled = true; load.textContent = 'Cargando…';
          info.innerHTML = `<span style="color:var(--text-muted)">Cargando «${d.name}» del repositorio…</span>`;
          try {
            const bytes = await dnaLibFetchBytes(d.name);
            applyLoaded(d.name, bytes, true);
          } catch (e) {
            console.error('[dna repo] Cargar falló:', e);
            info.innerHTML = `<span style="color:var(--red)">⚠ No se pudo cargar «${d.name}»: ${e.message}</span>`;
          } finally { load.disabled = false; load.textContent = 'Cargar'; }
        });
        row.appendChild(load);

        const del = mk('button', 'bw-btn bw-btn-cancel');
        del.type = 'button';
        del.style.cssText = 'font-size:0.74rem;padding:5px 10px;';
        del.title = 'Borrar del repositorio';
        del.textContent = '🗑';
        del.addEventListener('click', async () => {
          if (!confirm(`¿Borrar «${d.name}» del repositorio? Esta acción no se puede deshacer.`)) return;
          del.disabled = true;
          try { await dnaLibDelete(d.name); await dnaLibList(); refreshRepo(); }
          catch (e) { del.disabled = false; alert('No se pudo borrar: ' + e.message); }
        });
        row.appendChild(del);
        listBox.appendChild(row);
      });
    }).catch(e => setMsg('⚠ ' + e.message, 'var(--red)'));
  }
  fileField.appendChild(repoPanel);
  refreshRepo();

  container.appendChild(fileField);

  // Mode switch: single sequence vs bulk.
  const bulk = dnaReplaceInput.bulkMode;
  const satMode = bulk && dnaReplaceInput.bulkSubmode === 'saturate';
  const modeField = mk('div', 'bw-field');
  modeField.appendChild(mk('label', null, 'Modo'));
  const seg = mk('div');
  seg.style.cssText = 'display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-top:4px;';
  const mkSeg = (label, active) => {
    const b = mk('button', null, label);
    b.type = 'button';
    b.style.cssText = `font-size:0.78rem;padding:7px 16px;border:none;cursor:pointer;background:${active ? 'var(--accent,#1E5FB8)' : 'var(--bg-card)'};color:${active ? '#fff' : 'var(--text-muted)'};font-weight:${active ? '600' : '400'};`;
    return b;
  };
  const segSingle = mkSeg('Una secuencia', !bulk);
  const segBulk = mkSeg('Varias (bulk)', bulk);
  segSingle.addEventListener('click', () => { if (dnaReplaceInput.bulkMode) { dnaReplaceInput.bulkMode = false; renderDnaReplaceUI(); } });
  segBulk.addEventListener('click', () => { if (!dnaReplaceInput.bulkMode) { dnaReplaceInput.bulkMode = true; renderDnaReplaceUI(); } });
  seg.appendChild(segSingle); seg.appendChild(segBulk);
  modeField.appendChild(seg);
  container.appendChild(modeField);

  // Sequence to replace (common in both modes).
  const mkSeqField = (label, hint, key) => {
    const f = mk('div', 'bw-field');
    f.appendChild(mk('label', null, label));
    const h = mk('div', null, hint);
    h.style.cssText = `font-family:${MUT_MONO};font-size:0.7rem;color:var(--text-dim);margin:2px 0 6px;line-height:1.5;`;
    f.appendChild(h);
    const ta = document.createElement('textarea');
    ta.className = 'bw-input bw-textarea';
    ta.id = 'dna-seqfield-' + key;
    ta.rows = 3;
    ta.spellcheck = false;
    ta.value = dnaReplaceInput[key];
    ta.placeholder = 'ATGC…';
    ta.addEventListener('input', () => { dnaReplaceInput[key] = ta.value; updateExecuteBtn(); });
    f.appendChild(ta);
    return f;
  };
  const oldSeqField = mkSeqField(
    bulk ? 'Secuencia a sustituir (común a todas, la que está ahora en el .dna)' : 'Secuencia a sustituir (la que está ahora en el .dna)',
    'Nucleótidos. Debe aparecer exactamente una vez en la secuencia.', 'oldSeq');
  container.appendChild(oldSeqField);

  if (!bulk) {
    container.appendChild(mkSeqField('Secuencia nueva (con la que sustituir)', 'Nucleótidos. Puede tener longitud distinta a la anterior.', 'newSeq'));
  } else {
    // Bulk sub-mode: paste-your-own table vs. auto-generate amino-acid variants.
    const subField = mk('div', 'bw-field');
    subField.appendChild(mk('label', null, '¿Qué secuencias nuevas?'));
    const subSeg = mk('div');
    subSeg.style.cssText = 'display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-top:4px;flex-wrap:wrap;';
    const mkSub = (label, active) => {
      const b = mk('button', null, label); b.type = 'button';
      b.style.cssText = `font-size:0.78rem;padding:7px 16px;border:none;cursor:pointer;background:${active ? 'var(--accent,#1E5FB8)' : 'var(--bg-card)'};color:${active ? '#fff' : 'var(--text-muted)'};font-weight:${active ? '600' : '400'};`;
      return b;
    };
    const subManual = mkSub('Ya sé las secuencias', !satMode);
    const subSat = mkSub('Generar variantes de un aminoácido', satMode);
    subManual.addEventListener('click', () => { if (dnaReplaceInput.bulkSubmode !== 'manual') { dnaReplaceInput.bulkSubmode = 'manual'; renderDnaReplaceUI(); updateExecuteBtn(); } });
    subSat.addEventListener('click', () => { if (dnaReplaceInput.bulkSubmode !== 'saturate') { dnaReplaceInput.bulkSubmode = 'saturate'; renderDnaReplaceUI(); updateExecuteBtn(); } });
    subSeg.appendChild(subManual); subSeg.appendChild(subSat);
    subField.appendChild(subSeg);
    const subHint = mk('div', null, satMode
      ? 'La app analiza el ORF de arriba, y para una posición que indiques genera las 19 variantes aminoacídicas (codón óptimo humano).'
      : 'Pega tú mismo la tabla de secuencias nuevas (una por documento).');
    subHint.style.cssText = `font-family:${MUT_MONO};font-size:0.7rem;color:var(--text-dim);margin-top:6px;line-height:1.5;`;
    subField.appendChild(subHint);
    container.appendChild(subField);
  }

  if (satMode) {
    renderDnaSatPanel(container, oldSeqField.querySelector('textarea'));
  } else if (bulk) {
    // Bulk table input.
    const f = mk('div', 'bw-field');
    f.appendChild(mk('label', null, 'Secuencias en bulk'));
    const h = mk('div');
    h.style.cssText = `font-family:${MUT_MONO};font-size:0.7rem;color:var(--text-dim);margin:2px 0 6px;line-height:1.6;`;
    h.innerHTML = 'Una fila por documento. Columnas (en este orden), separadas por coma, punto y coma o tabulador (puedes pegar directamente desde Excel):<br><strong>nombre interno&nbsp;,&nbsp;secuencia nueva&nbsp;,&nbsp;nombre del feature</strong><br>Si dejas un campo vacío, ese aspecto se queda como estaba. El color y el resto de opciones de abajo se aplican a todas.';
    f.appendChild(h);
    const ta = document.createElement('textarea');
    ta.className = 'bw-input bw-textarea';
    ta.rows = 8;
    ta.spellcheck = false;
    ta.value = dnaReplaceInput.bulkText;
    ta.placeholder = 'pET28a-GFP, ATGAGCAAGGGC..., GFP\npET28a-RFP, ATGGCCTCCTCC..., RFP';
    ta.style.cssText = `font-family:${MUT_MONO};`;
    const counter = mk('div');
    counter.style.cssText = `font-family:${MUT_MONO};font-size:0.7rem;color:var(--text-dim);margin-top:6px;`;
    const updCounter = () => {
      const rows = dnaParseBulk(dnaReplaceInput.bulkText, dnaReplaceInput.bulkHeader);
      const valid = rows.filter(r => r.valid).length;
      const skip = rows.length - valid;
      counter.textContent = rows.length
        ? `${valid} fila(s) con secuencia válida${skip ? ` · ${skip} sin secuencia (se omitirán)` : ''}.`
        : '';
    };
    ta.addEventListener('input', () => { dnaReplaceInput.bulkText = ta.value; updCounter(); updateExecuteBtn(); });
    f.appendChild(ta);
    // header checkbox
    const hdr = mk('label', 'bw-checkbox-wrap');
    hdr.style.marginTop = '6px';
    const hc = document.createElement('input'); hc.type = 'checkbox'; hc.checked = dnaReplaceInput.bulkHeader === true;
    hc.addEventListener('change', () => { dnaReplaceInput.bulkHeader = hc.checked; updCounter(); updateExecuteBtn(); });
    hdr.appendChild(hc); hdr.appendChild(mk('span', null, 'La primera fila son encabezados (ignorarla)'));
    f.appendChild(hdr);
    f.appendChild(counter);
    updCounter();
    container.appendChild(f);
  }

  // Options box (feature/coord/rename). Hidden in saturation mode, where the swap
  // is a single codon (non-destructive: every feature is kept, doc auto-renamed).
  if (!satMode) {
  const box = mk('div');
  box.style.cssText = 'border:1px solid var(--border);border-radius:8px;padding:12px 14px;background:var(--bg-card);display:flex;flex-direction:column;gap:10px;';

  const mkCheck = (key, label) => {
    const w = mk('label', 'bw-checkbox-wrap');
    const c = document.createElement('input');
    c.type = 'checkbox';
    c.checked = dnaReplaceInput[key] !== false;
    w.appendChild(c);
    w.appendChild(mk('span', null, label));
    return { w, c };
  };

  // add feature + name/type
  const addChk = mkCheck('addFeature', 'Añadir una feature para la secuencia nueva');
  box.appendChild(addChk.w);
  const featRow = mk('div');
  featRow.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;padding-left:24px;';
  const nameIn = document.createElement('input');
  nameIn.type = 'text'; nameIn.className = 'bw-input'; nameIn.placeholder = 'Nombre de la feature';
  nameIn.style.cssText = 'flex:1;min-width:160px;';
  nameIn.value = dnaReplaceInput.featName;
  nameIn.addEventListener('input', () => { dnaReplaceInput.featName = nameIn.value; });
  const typeSel = document.createElement('select');
  typeSel.className = 'bw-select';
  for (const t of DNA_FEATURE_TYPES) {
    const o = document.createElement('option'); o.value = t; o.textContent = t;
    if (t === dnaReplaceInput.featType) o.selected = true;
    typeSel.appendChild(o);
  }
  typeSel.addEventListener('change', () => { dnaReplaceInput.featType = typeSel.value; });
  if (!bulk) featRow.appendChild(nameIn);   // in bulk, the feature name comes from the table
  featRow.appendChild(typeSel);
  if (bulk) {
    const fh = mk('span', null, 'El nombre de cada feature se toma de la 3ª columna de la tabla.');
    fh.style.cssText = `font-family:${MUT_MONO};font-size:0.7rem;color:var(--text-dim);align-self:center;`;
    featRow.appendChild(fh);
  }
  box.appendChild(featRow);

  // feature colour: native picker + quick presets
  const colorRow = mk('div');
  colorRow.style.cssText = 'display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding-left:24px;';
  const colorLbl = mk('span', null, 'Color:');
  colorLbl.style.cssText = `font-family:${MUT_MONO};font-size:0.72rem;color:var(--text-dim);`;
  colorRow.appendChild(colorLbl);
  const colorIn = document.createElement('input');
  colorIn.type = 'color';
  colorIn.value = dnaReplaceInput.featColor || '#a6acb3';
  colorIn.title = 'Color de la feature';
  colorIn.style.cssText = 'width:40px;height:30px;padding:2px;border:1px solid var(--border);border-radius:6px;background:var(--bg-card);cursor:pointer;';
  colorIn.addEventListener('input', () => { dnaReplaceInput.featColor = colorIn.value; });
  colorRow.appendChild(colorIn);
  const DNA_FEATURE_PRESETS = ['#f5524b', '#f7a83e', '#f4d03f', '#5fb878', '#3fb6c6', '#4a78c8', '#9b6bd6', '#a6acb3'];
  for (const col of DNA_FEATURE_PRESETS) {
    const sw = mk('button');
    sw.type = 'button';
    sw.title = col;
    sw.style.cssText = `width:20px;height:20px;border-radius:5px;border:1px solid var(--border);background:${col};cursor:pointer;padding:0;`;
    sw.addEventListener('click', () => { dnaReplaceInput.featColor = col; colorIn.value = col; });
    colorRow.appendChild(sw);
  }
  if (!bulk) box.appendChild(colorRow);   // no per-row colours in bulk mode

  const syncFeat = () => { const show = addChk.c.checked ? 'flex' : 'none'; featRow.style.display = show; if (!bulk) colorRow.style.display = show; };
  addChk.c.addEventListener('change', () => { dnaReplaceInput.addFeature = addChk.c.checked; syncFeat(); });
  syncFeat();

  const delChk = mkCheck('deleteOverlap', 'Borrar la(s) feature(s) que solapan la región sustituida');
  delChk.c.addEventListener('change', () => { dnaReplaceInput.deleteOverlap = delChk.c.checked; });
  box.appendChild(delChk.w);

  const shiftChk = mkCheck('shiftCoords', 'Reajustar coordenadas de las features posteriores (si cambia la longitud)');
  shiftChk.c.addEventListener('change', () => { dnaReplaceInput.shiftCoords = shiftChk.c.checked; });
  box.appendChild(shiftChk.w);

  // rename (single mode only — in bulk the internal name comes from the table)
  if (!bulk) {
    const renChk = mkCheck('renameDoc', 'Cambiar el nombre interno del documento');
    renChk.c.checked = dnaReplaceInput.renameDoc === true;
    box.appendChild(renChk.w);
    const renField = mk('div');
    renField.style.cssText = 'padding-left:24px;';
    const renIn = document.createElement('input');
    renIn.type = 'text'; renIn.className = 'bw-input'; renIn.placeholder = 'Nombre interno (custom map label)';
    renIn.style.maxWidth = '320px';
    renIn.value = dnaReplaceInput.docName;
    renIn.addEventListener('input', () => { dnaReplaceInput.docName = renIn.value; updateExecuteBtn(); });
    renField.appendChild(renIn);
    const renHint = mk('div', null, 'El nombre del fichero descargado conserva tal cual los espacios y las tildes.');
    renHint.style.cssText = `font-family:${MUT_MONO};font-size:0.68rem;color:var(--text-dim);margin-top:4px;`;
    renField.appendChild(renHint);
    box.appendChild(renField);
    const syncRen = () => { renField.style.display = renChk.c.checked ? '' : 'none'; };
    renChk.c.addEventListener('change', () => { dnaReplaceInput.renameDoc = renChk.c.checked; syncRen(); updateExecuteBtn(); });
    syncRen();
  } else {
    const bh = mk('div', null, 'El nombre interno de cada documento (y el del fichero) se toma de la 1ª columna de la tabla, conservando espacios y tildes.');
    bh.style.cssText = `font-family:${MUT_MONO};font-size:0.7rem;color:var(--text-dim);`;
    box.appendChild(bh);
  }

  container.appendChild(box);
  } // end if(!satMode) options box

  // Bottom row: clear + FASTA export (all modified sequences, nt or aa)
  const bottomRow = mk('div');
  bottomRow.style.cssText = 'display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:4px;';
  const clearBtn = mk('button', 'bw-btn bw-btn-cancel');
  clearBtn.type = 'button';
  clearBtn.style.cssText = 'font-size:0.8rem;padding:7px 16px;';
  clearBtn.textContent = '↺ Limpiar y empezar de nuevo';
  clearBtn.addEventListener('click', () => {
    if (state.appStatus === 'running' || state.appStatus === 'uploading') return;
    dnaReplaceInput = { file: null, oldSeq: '', newSeq: '', addFeature: true, featName: '', featType: 'CDS', featColor: '#a6acb3', deleteOverlap: true, shiftCoords: true, renameDoc: true, docName: '', bulkMode: false, bulkText: '', bulkHeader: false, bulkSubmode: 'manual', satPos: '', satAAs: null, satKey: '', satPrefix: '', satSuffix: '', satAddFeat: true, satFeatPrefix: '', satFeatSuffix: '', satHasSignal: true, satSignalLen: '', satVariantMode: 'position', satList: '', satListSel: null, satListKey: '' };
    const res = $('dna-replace-results');
    if (res) res.remove();
    resetExecuteBar();
    renderDnaReplaceUI();
    updateExecuteBtn();
  });
  bottomRow.appendChild(clearBtn);

  const fastaLbl = mk('span', null, '⤓ FASTA de las secuencias modificadas:');
  fastaLbl.style.cssText = `font-family:${MUT_MONO};font-size:0.76rem;color:var(--text-muted);margin-left:6px;`;
  bottomRow.appendChild(fastaLbl);
  const fastaNt = mk('button', 'bw-btn bw-btn-cancel'); fastaNt.type = 'button'; fastaNt.textContent = 'nt'; fastaNt.title = 'Descargar un FASTA con las secuencias de nucleótidos'; fastaNt.style.cssText = 'font-size:0.8rem;padding:7px 16px;';
  const fastaAa = mk('button', 'bw-btn bw-btn-cancel'); fastaAa.type = 'button'; fastaAa.textContent = 'aa'; fastaAa.title = 'Descargar un FASTA con las secuencias traducidas a aminoácidos'; fastaAa.style.cssText = 'font-size:0.8rem;padding:7px 16px;';
  fastaNt.addEventListener('click', () => exportDnaFasta('nt'));
  fastaAa.addEventListener('click', () => exportDnaFasta('aa'));
  bottomRow.appendChild(fastaNt); bottomRow.appendChild(fastaAa);
  container.appendChild(bottomRow);

  zone.appendChild(container);
  updateExecuteBtn();
}

// ── Run + render ────────────────────────────────────────────────────────────
// Core: apply one substitution to a template .dna, returning new bytes + stats.
// oldSeq/newSeq must already be cleaned. renameName '' means "leave the internal
// name untouched". Throws on errors (sequence not found, etc.).
function dnaPerformReplacement(templateBytes, opts) {
  const { oldSeq, newSeq, deleteOverlap, shiftCoords, addFeature, featName, featType, featColor, renameName, renameCdsName } = opts;
  if (!oldSeq) throw new Error('La secuencia a sustituir no contiene nucleótidos válidos.');
  if (!newSeq) throw new Error('La secuencia nueva no contiene nucleótidos válidos.');

  const packets = dnaParsePackets(templateBytes);
  dnaValidateCookie(packets);

  const dnaPkt = packets.find(p => p.type === 0);
  if (!dnaPkt) throw new Error('El fichero no contiene secuencia de ADN.');
  const flags = dnaPkt.data[0];
  const seq = dnaBytesToAscii(dnaPkt.data.slice(1));
  const up = seq.toUpperCase();

  const pos = up.indexOf(oldSeq);
  if (pos < 0) throw new Error('La secuencia a sustituir no se encontró en el documento.');
  let occurrences = 1, scan = up.indexOf(oldSeq, pos + 1);
  while (scan >= 0) { occurrences++; scan = up.indexOf(oldSeq, scan + 1); }

  const newFullSeq = seq.slice(0, pos) + newSeq + seq.slice(pos + oldSeq.length);
  const delta = newSeq.length - oldSeq.length;

  // nt-to-nt comparison: only meaningful when the final length matches the original.
  let ntCompare;
  if (newFullSeq.length === seq.length) {
    const b = newFullSeq.toUpperCase();
    let changes = 0;
    for (let i = 0; i < up.length; i++) if (up[i] !== b[i]) changes++;
    ntCompare = { applicable: true, changes, total: up.length };
  } else {
    ntCompare = { applicable: false, total: seq.length, newTotal: newFullSeq.length };
  }

  // 1) DNA packet
  const newData = new Uint8Array(1 + newFullSeq.length);
  newData[0] = flags;
  newData.set(dnaAsciiToBytes(newFullSeq), 1);
  dnaPkt.data = newData;

  // 2) Features packet
  const rStart = pos + 1, rEnd = pos + oldSeq.length;          // 1-based, region replaced
  const newStart = pos + 1, newEnd = pos + newSeq.length;      // 1-based, new region
  let featResult = { removed: 0, shifted: 0, added: false, renamed: false };
  const featPkt = packets.find(p => p.type === 10);
  if (featPkt) {
    const xml = dnaBytesToAscii(featPkt.data);
    featResult = dnaEditFeaturesXml(xml, { rStart, rEnd, delta, deleteOverlap, shiftCoords, addFeature, featName, featType, featColor, newStart, newEnd, renameCdsName });
    featPkt.data = new TextEncoder().encode(featResult.xml);
  } else if (addFeature || renameCdsName) {
    // No features packet: create a minimal one with the (renamed) CDS feature.
    const nm = String(renameCdsName || featName || 'secuencia_nueva').replace(/[<&>]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
    const col = featColor || '#a6acb3';
    const type = renameCdsName ? 'CDS' : featType;
    const xml = `<?xml version="1.0" encoding="UTF-8"?><Features><Feature name="${nm}" type="${type}" directionality="1"><Segment range="${newStart}-${newEnd}" type="standard" color="${col}"/></Feature></Features>`;
    packets.push({ type: 10, data: new TextEncoder().encode(xml) });
    featResult.added = true;
  }

  // 3) Notes name
  let nameApplied = false;
  const renm = (renameName || '').trim();
  if (renm) {
    const notesPkt = packets.find(p => p.type === 6);
    if (notesPkt) notesPkt.data = new TextEncoder().encode(dnaSetNotesName(dnaBytesToAscii(notesPkt.data), renm));
    else packets.push(dnaBuildNotesPacket(renm));
    nameApplied = true;
  }

  // 4) Serialise
  const outBytes = dnaSerialize(packets);
  return {
    outBytes, pos, occurrences, oldLen: oldSeq.length, newLen: newSeq.length, delta,
    oldTotal: seq.length, newTotal: newFullSeq.length, featResult, nameApplied, ntCompare,
    circular: (flags & 1) === 1,
  };
}

async function runDnaReplace() {
  if (!dnaReplaceInput.file) throw new Error('Carga un fichero .dna.');
  if (dnaReplaceInput.bulkMode) {
    if (dnaReplaceInput.bulkSubmode === 'saturate') { await runDnaSaturate(); return; }
    await runDnaReplaceBulk(); return;
  }

  const oldSeq = dnaCleanSeq(dnaReplaceInput.oldSeq);
  const newSeq = dnaCleanSeq(dnaReplaceInput.newSeq);
  if (!oldSeq) throw new Error('La secuencia a sustituir no contiene nucleótidos válidos.');
  if (!newSeq) throw new Error('La secuencia nueva no contiene nucleótidos válidos.');

  const renameName = (dnaReplaceInput.renameDoc && dnaReplaceInput.docName.trim()) ? dnaReplaceInput.docName.trim() : '';
  const r = dnaPerformReplacement(dnaReplaceInput.file.bytes, {
    oldSeq, newSeq,
    deleteOverlap: dnaReplaceInput.deleteOverlap,
    shiftCoords: dnaReplaceInput.shiftCoords,
    addFeature: dnaReplaceInput.addFeature,
    featName: dnaReplaceInput.featName,
    featType: dnaReplaceInput.featType,
    featColor: dnaReplaceInput.featColor,
    renameName,
  });

  const baseName = dnaReplaceInput.file.name.replace(/\.dna$/i, '');
  const outName = renameName ? dnaSafeDownloadName(renameName) : `${baseName}_modificado.dna`;
  state.clientSideBlob = { blob: new Blob([r.outBytes], { type: 'application/octet-stream' }), filename: outName };

  renderDnaReplaceResults({ ...r, outName });

  state.appStatus = 'done';
  const parts = [`sustituido en pos ${r.pos + 1}`, `${r.oldTotal.toLocaleString('es-ES')}→${r.newTotal.toLocaleString('es-ES')} nt`];
  if (r.featResult.added) parts.push('feature añadida');
  if (r.featResult.removed) parts.push(`${r.featResult.removed} feature(s) borrada(s)`);
  if (r.featResult.shifted) parts.push(`${r.featResult.shifted} reajustada(s)`);
  setStatus('✓ ' + parts.join(' · '), 'ok');
  $('btn-execute').style.display = 'none';
  $('btn-download').style.display = '';
}

// ── Bulk mode ───────────────────────────────────────────────────────────────
// Parse the pasted table. Columns (in order): internal name, new sequence,
// feature name. Field separators: comma, semicolon or tab; rows: newlines.
function dnaParseBulk(text, skipHeader) {
  const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n');
  const rows = [];
  let started = false;
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    if (!raw.trim()) continue;
    if (skipHeader && !started) { started = true; continue; }
    started = true;
    const fields = raw.split(/[,;\t]/).map(s => s.trim());
    const name = fields[0] || '';
    const seqRaw = fields[1] || '';
    const feat = fields[2] || '';
    const seq = dnaCleanSeq(seqRaw);
    rows.push({ lineNo: i + 1, name, seqRaw, seq, feat, valid: seq.length > 0 });
  }
  return rows;
}

// ── Minimal ZIP writer (store, no compression) — keeps us dependency-free ─────
const DNA_CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    t[n] = c >>> 0;
  }
  return t;
})();
function dnaCrc32(bytes) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < bytes.length; i++) c = DNA_CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}
// files: [{ name, data: Uint8Array }] → Blob (application/zip)
function dnaMakeZip(files) {
  const enc = new TextEncoder();
  const chunks = [];
  const central = [];
  let offset = 0;
  const push = u8 => { chunks.push(u8); offset += u8.length; };
  const u16 = v => new Uint8Array([v & 0xFF, (v >>> 8) & 0xFF]);
  const u32 = v => new Uint8Array([v & 0xFF, (v >>> 8) & 0xFF, (v >>> 16) & 0xFF, (v >>> 24) & 0xFF]);

  for (const f of files) {
    const nameBytes = enc.encode(f.name);
    const data = f.data;
    const crc = dnaCrc32(data);
    const localOffset = offset;
    // Local file header. Bit 11 (0x0800) marks UTF-8 filenames.
    push(u32(0x04034b50));
    push(u16(20)); push(u16(0x0800)); push(u16(0));        // version, flags, method=store
    push(u16(0)); push(u16(0x21));                          // mod time, mod date (arbitrary)
    push(u32(crc)); push(u32(data.length)); push(u32(data.length));
    push(u16(nameBytes.length)); push(u16(0));
    push(nameBytes); push(data);
    // Central directory record (stored for later).
    central.push({ nameBytes, crc, size: data.length, localOffset });
  }

  const cdStart = offset;
  for (const c of central) {
    push(u32(0x02014b50));
    push(u16(20)); push(u16(20)); push(u16(0x0800)); push(u16(0));   // madeBy, needed, flags, method
    push(u16(0)); push(u16(0x21));                                    // time, date
    push(u32(c.crc)); push(u32(c.size)); push(u32(c.size));
    push(u16(c.nameBytes.length)); push(u16(0)); push(u16(0));        // name, extra, comment
    push(u16(0)); push(u16(0)); push(u32(0));                         // disk, intAttr, extAttr
    push(u32(c.localOffset));
    push(c.nameBytes);
  }
  const cdSize = offset - cdStart;
  push(u32(0x06054b50));
  push(u16(0)); push(u16(0));
  push(u16(central.length)); push(u16(central.length));
  push(u32(cdSize)); push(u32(cdStart)); push(u16(0));

  return new Blob(chunks, { type: 'application/zip' });
}

// Build the CSV report (Excel-friendly: ; separator + UTF-8 BOM).
function dnaBulkReportCsv(results, meta) {
  const esc = v => {
    const s = String(v == null ? '' : v);
    return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const header = ['#', 'Nombre interno', 'Fichero', 'Feature', 'Estado', 'Posición', 'Ocurrencias',
    'nt original', 'nt resultado', 'Δ longitud', 'Cambios nt-a-nt', 'Features borradas', 'Features reajustadas', 'Feature añadida', 'Observaciones'];
  const lines = [header.map(esc).join(';')];
  results.forEach((r, i) => {
    lines.push([
      i + 1, r.name || '', r.filename || '', r.feat || '',
      r.ok ? 'OK' : 'ERROR',
      r.ok ? r.pos + 1 : '',
      r.ok ? r.occurrences : '',
      r.ok ? r.oldTotal : '',
      r.ok ? r.newTotal : '',
      r.ok ? (r.delta >= 0 ? '+' + r.delta : r.delta) : '',
      r.ok ? (r.ntCompare.applicable ? r.ntCompare.changes : 'n/a (distinto tamaño)') : '',
      r.ok ? r.featResult.removed : '',
      r.ok ? r.featResult.shifted : '',
      r.ok ? (r.featResult.renamed ? 'CDS renombrada' : r.featResult.added ? 'añadida' : 'no') : '',
      r.ok ? (r.occurrences > 1 ? `secuencia común encontrada ${r.occurrences} veces; sustituida la 1ª` : '') : r.error,
    ].map(esc).join(';'));
  });
  const summary = [
    '', '',
    `Informe de sustitución en bulk — ${meta.date}`,
    ...(meta.extraLabel ? [meta.extraLabel] : []),
    `Plantilla: ${meta.template}`,
    `Secuencia a sustituir (común): ${meta.oldSeq}`,
    `Filas procesadas: ${meta.processed} · correctas: ${meta.ok} · con error: ${meta.failed} · omitidas (sin secuencia): ${meta.skipped}`,
  ];
  return '﻿' + lines.join('\n') + '\n' + summary.map(esc).join('\n') + '\n';
}

// Shared core for both bulk paths: given the common oldSeq and a list of rows
// ({ name, seq, feat }), replace oldSeq→row.seq in the template for each, zip the
// results + a CSV report, and render. `opts` carries the feature/coord behaviour.
async function dnaRunRows(oldSeq, rows, skipped, opts) {
  if (!rows.length) throw new Error('No hay ninguna construcción que generar.');
  const templateBase = dnaReplaceInput.file.name.replace(/\.dna$/i, '');
  const usedNames = new Map();   // ensure unique filenames inside the zip
  const uniqueName = base => {
    let name = base; let n = 1;
    while (usedNames.has(name.toLowerCase())) { n++; name = base.replace(/\.dna$/i, '') + ` (${n}).dna`; }
    usedNames.set(name.toLowerCase(), true);
    return name;
  };

  const results = [];
  const zipFiles = [];
  rows.forEach((row, idx) => {
    const filenameBase = row.name ? dnaSafeDownloadName(row.name) : `${templateBase}_${idx + 1}.dna`;
    try {
      const r = dnaPerformReplacement(dnaReplaceInput.file.bytes, {
        oldSeq, newSeq: row.seq,
        deleteOverlap: opts.deleteOverlap,
        shiftCoords: opts.shiftCoords,
        addFeature: opts.addFeature,
        featName: row.feat,                 // per-row feature name (empty → default)
        featType: opts.featType,
        featColor: opts.featColor || '#a6acb3',
        renameCdsName: opts.renameCds ? row.feat : null,   // rename the ORF's CDS
        renameName: row.name,               // empty → leave internal name
      });
      const filename = uniqueName(filenameBase);
      zipFiles.push({ name: filename, data: r.outBytes });
      results.push({ ok: true, name: row.name, feat: row.feat, filename, ...r });
    } catch (e) {
      results.push({ ok: false, name: row.name, feat: row.feat, filename: filenameBase, error: e.message });
    }
  });

  const okCount = results.filter(r => r.ok).length;
  const failCount = results.length - okCount;
  if (!zipFiles.length) throw new Error('Ninguna construcción se pudo generar. Revisa la secuencia a sustituir.');

  const meta = {
    date: new Date().toLocaleString('es-ES'),
    template: dnaReplaceInput.file.name,
    oldSeq,
    processed: rows.length, ok: okCount, failed: failCount, skipped: skipped.length,
    extraLabel: opts.reportLabel || '',
  };
  const csv = dnaBulkReportCsv(results, meta);
  zipFiles.push({ name: 'informe.csv', data: new TextEncoder().encode(csv) });

  const zipBlob = dnaMakeZip(zipFiles);
  const zipName = `${opts.zipPrefix || 'bulk'}-${templateBase}-${new Date().toISOString().slice(0, 10)}.zip`;
  state.clientSideBlob = { blob: zipBlob, filename: zipName };

  renderDnaReplaceBulkResults({ results, skipped, meta, zipName, csv });

  state.appStatus = 'done';
  setStatus(`✓ ${okCount} documento(s) generado(s)${failCount ? ` · ${failCount} con error` : ''}${skipped.length ? ` · ${skipped.length} omitida(s)` : ''}`, okCount ? 'ok' : 'err');
  $('btn-execute').style.display = 'none';
  $('btn-download').style.display = '';
}

async function runDnaReplaceBulk() {
  const oldSeq = dnaCleanSeq(dnaReplaceInput.oldSeq);
  if (!oldSeq) throw new Error('La secuencia a sustituir (común) no contiene nucleótidos válidos.');

  const allRows = dnaParseBulk(dnaReplaceInput.bulkText, dnaReplaceInput.bulkHeader);
  const rows = allRows.filter(r => r.valid);
  const skipped = allRows.filter(r => !r.valid);
  if (!rows.length) throw new Error('No hay ninguna fila con secuencia nueva válida en el cuadro de bulk.');

  await dnaRunRows(oldSeq, rows, skipped, {
    deleteOverlap: dnaReplaceInput.deleteOverlap,
    shiftCoords: dnaReplaceInput.shiftCoords,
    addFeature: dnaReplaceInput.addFeature,
    featType: dnaReplaceInput.featType,
    featColor: '#a6acb3',
    zipPrefix: 'bulk',
  });
}

// ── Saturation sub-mode: 19 amino-acid variants at one ORF position ────────────
// Pure state derived from the current inputs (used by the panel, the execute-bar
// validation and the runner). Never mutates state.
// Signal-peptide offset: keep wild-type numbering even when the gene lacks its
// signal peptide (codonPos = typed − signalLen + 1, i.e. offset = 1 − signalLen).
function dnaSatOffset() {
  if (dnaReplaceInput.satHasSignal === false) {
    const L = Math.round(Number(dnaReplaceInput.satSignalLen));
    if (!Number.isFinite(L) || L < 1) return { error: 'Indica de cuántos aminoácidos es el péptido señal (o marca que sí lo tiene).' };
    return { offset: 1 - L, signalLen: L };
  }
  return { offset: 0, signalLen: 0 };
}
function dnaSatState() {
  const oldSeq = dnaCleanSeq(dnaReplaceInput.oldSeq);
  if (!oldSeq) return { oldSeq: '', error: 'Introduce arriba la «Secuencia a sustituir» (el ORF) para analizarla.' };
  const analyze = BWBio.analyzeOrf(oldSeq);
  if (analyze.fatal) return { oldSeq, analyze, error: analyze.fatal };
  const off = dnaSatOffset();
  if (off.error) return { oldSeq, analyze, error: off.error };
  const { offset, signalLen } = off;
  const mode = dnaReplaceInput.satVariantMode === 'list' ? 'list' : 'position';
  const base = { oldSeq, analyze, offset, signalLen, mode };

  if (mode === 'list') {
    const subs = BWBio.parseSubList(dnaReplaceInput.satList, analyze.residues, offset);
    const valid = subs.filter(s => s.valid);
    if (!valid.length) return { ...base, subs, selected: [], constructs: [], error: dnaReplaceInput.satList.trim() ? 'Ninguna sustitución válida en la lista.' : 'Escribe las sustituciones (por ejemplo G223A, D45V).' };
    const key = valid.map(s => s.name).join(',');
    let selNames;
    if (Array.isArray(dnaReplaceInput.satListSel) && dnaReplaceInput.satListKey === key) selNames = dnaReplaceInput.satListSel.filter(n => valid.some(s => s.name === n));
    else selNames = valid.map(s => s.name);
    const constructs = valid.filter(s => selNames.includes(s.name)).map(s => ({ codonPos: s.codonPos, name: s.name, newAA: s.newAA }));
    return { ...base, subs, valid, key, selNames, constructs, selected: constructs };
  }

  // Position mode: all (selected) amino acids at one position.
  const parsed = BWBio.parsePosition(dnaReplaceInput.satPos, analyze.residues, offset);
  if (parsed.error) return { ...base, parsed, error: parsed.error };
  const key = parsed.codonPos + parsed.orig;
  const all19 = BWBio.AA_ORDER.filter(a => a !== parsed.orig);
  let selAAs;
  if (Array.isArray(dnaReplaceInput.satAAs) && dnaReplaceInput.satKey === key) selAAs = dnaReplaceInput.satAAs.filter(a => a !== parsed.orig && BWBio.AA_ORDER.includes(a));
  else selAAs = all19.slice();
  const posLabel = String(parsed.pos).padStart(3, '0');
  const constructs = selAAs.map(aa => ({ codonPos: parsed.codonPos, name: `${parsed.orig}${posLabel}${aa}`, newAA: aa }));
  return { ...base, parsed, orig: parsed.orig, all19, selAAs, key, constructs, selected: constructs };
}

async function runDnaSaturate() {
  const st = dnaSatState();
  if (st.error) throw new Error(st.error);
  if (!st.constructs.length) throw new Error('Selecciona al menos una variante para generar.');
  const { oldSeq, constructs, mode } = st;
  const prefix = dnaReplaceInput.satPrefix || '';
  const suffix = dnaReplaceInput.satSuffix || '';
  const featPrefix = dnaReplaceInput.satFeatPrefix || '';
  const featSuffix = dnaReplaceInput.satFeatSuffix || '';
  const addFeat = dnaReplaceInput.satAddFeat !== false;
  const rows = constructs.map(c => ({
    name: `${prefix}${c.name}${suffix}`,
    seq: BWBio.buildVariantNt(oldSeq, c.codonPos, c.newAA),   // real codon in the ORF
    feat: `${featPrefix}${c.name}${featSuffix}`,              // used only when renaming the CDS
  }));
  const sig = st.signalLen ? ` · sin péptido señal (${st.signalLen} aa)` : '';
  const label = mode === 'list'
    ? `Sustituciones concretas (${constructs.length}; codón óptimo humano)${sig}`
    : `Saturación de la posición ${st.parsed.orig}${String(st.parsed.pos).padStart(3, '0')} (codón óptimo humano)${sig}`;
  const zipPrefix = mode === 'list' ? 'sustituciones' : `saturacion-${st.parsed.orig}${String(st.parsed.pos).padStart(3, '0')}`;
  await dnaRunRows(oldSeq, rows, [], {
    // Change only the codon and rename the doc. Optionally rename the ORF's CDS
    // feature per variant (no duplicate features); keep every other feature.
    deleteOverlap: false, shiftCoords: false, addFeature: false, renameCds: addFeat,
    featType: 'CDS', featColor: '#a6acb3',
    zipPrefix, reportLabel: label,
  });
}

// ── FASTA export of the modified sequences (nt / aa), across all modes ──────────
// Gathers { name, nt } for every construction currently defined: the single new
// sequence, each bulk row, or each saturation variant.
function dnaCollectConstructions() {
  const out = [];
  const templateBase = (dnaReplaceInput.file && dnaReplaceInput.file.name.replace(/\.dna$/i, '')) || 'seq';
  if (dnaReplaceInput.bulkMode && dnaReplaceInput.bulkSubmode === 'saturate') {
    const st = dnaSatState();
    if (st.error) throw new Error(st.error);
    const prefix = dnaReplaceInput.satPrefix || '', suffix = dnaReplaceInput.satSuffix || '';
    for (const c of st.constructs) out.push({ name: `${prefix}${c.name}${suffix}`, nt: BWBio.buildVariantNt(st.oldSeq, c.codonPos, c.newAA) });
    return out;
  }
  if (dnaReplaceInput.bulkMode) {
    const rows = dnaParseBulk(dnaReplaceInput.bulkText, dnaReplaceInput.bulkHeader).filter(r => r.valid);
    rows.forEach((r, i) => out.push({ name: r.name || `${templateBase}_${i + 1}`, nt: r.seq }));
    return out;
  }
  const nt = dnaCleanSeq(dnaReplaceInput.newSeq);
  if (nt) out.push({ name: (dnaReplaceInput.renameDoc && dnaReplaceInput.docName.trim()) || `${templateBase}_modificado`, nt });
  return out;
}
// Frame-1 translation (T-based); '*' = stop, 'X' = unknown/incomplete handled by dropping the tail.
function dnaTranslateFrame1(nt) {
  const s = String(nt || '').toUpperCase().replace(/U/g, 'T').replace(/[^ACGT]/g, '');
  let aa = '';
  for (let i = 0; i + 3 <= s.length; i += 3) aa += (BWBio.GENETIC_CODE[s.substr(i, 3)] || 'X');
  return aa;
}
function dnaFastaWrap(s, n) { const out = []; for (let i = 0; i < s.length; i += n) out.push(s.slice(i, i + n)); return out.join('\n'); }
function exportDnaFasta(kind) {
  let items;
  try { items = dnaCollectConstructions(); } catch (e) { setStatus('No se pudo exportar: ' + e.message, 'err'); return; }
  if (!items.length) { setStatus('No hay secuencias modificadas que exportar (introduce la secuencia nueva, el bulk o las variantes).', 'err'); return; }
  const text = items.map(it => {
    const header = String(it.name || 'secuencia').replace(/[\r\n]+/g, ' ').trim() || 'secuencia';
    const seq = kind === 'aa' ? dnaTranslateFrame1(it.nt) : String(it.nt || '').toUpperCase();
    return '>' + header + '\n' + (dnaFastaWrap(seq, 70) || '');
  }).join('\n') + '\n';
  const templateBase = (dnaReplaceInput.file && dnaReplaceInput.file.name.replace(/\.dna$/i, '')) || 'secuencias';
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `${templateBase}_modificadas_${kind}.fasta` });
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  setStatus(`✓ FASTA (${kind}) generado — ${items.length} secuencia(s).`, 'ok');
}

// The saturation panel: analyse the ORF, ask for a position, and show the 19
// amino-acid toggles (codón óptimo humano). Re-analyses live when the ORF changes.
function renderDnaSatPanel(container, oldTa) {
  const MONO = MUT_MONO;
  const panelRoot = mk('div');
  container.appendChild(panelRoot);

  const paint = () => {
    panelRoot.innerHTML = '';
    const oldSeq = dnaCleanSeq(dnaReplaceInput.oldSeq);
    if (!oldSeq) {
      const note = mk('div', null, 'Introduce arriba la «Secuencia a sustituir» (el ORF) para analizarla y elegir la posición a mutar.');
      note.style.cssText = 'font-size:0.8rem;color:var(--text-dim);padding:10px;border:1px dashed var(--border);border-radius:8px;';
      panelRoot.appendChild(note);
      return;
    }
    const analyze = BWBio.analyzeOrf(oldSeq);
    const sum = mk('div');
    sum.style.cssText = `border:1px solid var(--border);border-radius:8px;padding:10px 12px;background:var(--bg-card);font-family:${MONO};font-size:0.72rem;line-height:1.6;color:var(--text-muted);`;
    if (analyze.fatal) {
      sum.innerHTML = `<span style="color:var(--danger,#f5524b)">${analyze.fatal}</span>`;
      panelRoot.appendChild(sum);
      return;
    }
    const aaPrev = analyze.aaString.length > 90 ? analyze.aaString.slice(0, 90) + '…' : analyze.aaString;
    sum.innerHTML = `ORF: <b>${analyze.len} nt</b> · <b>${analyze.nCodons}</b> codones · <b>${analyze.codingCount}</b> aminoácidos.<br>` +
      `Traducción (M001…): <span style="word-break:break-all">${aaPrev}</span>` +
      (analyze.warnings.length ? '<br>' + analyze.warnings.map(w => `<span style="color:#f7a83e">⚠ ${w}</span>`).join('<br>') : '');
    panelRoot.appendChild(sum);

    // Signal peptide: keep wild-type numbering even when the gene lacks it.
    const sigField = mk('div', 'bw-field'); sigField.style.marginTop = '10px';
    const sigChkWrap = mk('label', 'bw-checkbox-wrap');
    const sigChk = document.createElement('input'); sigChk.type = 'checkbox'; sigChk.checked = dnaReplaceInput.satHasSignal !== false;
    sigChkWrap.appendChild(sigChk); sigChkWrap.appendChild(mk('span', null, 'El gen incluye su péptido señal (la numeración coincide con la wild-type)'));
    sigField.appendChild(sigChkWrap);
    const sigLenRow = mk('div');
    sigLenRow.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px;padding-left:24px;';
    const sigLenLbl = mk('span', null, 'Longitud del péptido señal (aa):');
    sigLenLbl.style.cssText = `font-family:${MONO};font-size:0.72rem;color:var(--text-dim);`;
    sigLenRow.appendChild(sigLenLbl);
    const sigLenIn = document.createElement('input');
    sigLenIn.type = 'number'; sigLenIn.min = '1'; sigLenIn.className = 'bw-input'; sigLenIn.style.maxWidth = '90px';
    sigLenIn.placeholder = 'p. ej. 23'; sigLenIn.value = dnaReplaceInput.satSignalLen;
    sigLenRow.appendChild(sigLenIn);
    sigField.appendChild(sigLenRow);
    const sigHint = mk('div', null, 'Si el gen NO tiene péptido señal, se numera igual que la wild-type: la posición que escribas se ajusta a «posición − longitud + 1» (por la Met que se conserva). Ej.: G223 con 23 aa → se cambia el codón 201, pero la variante se sigue llamando G223.');
    sigHint.style.cssText = `font-family:${MONO};font-size:0.68rem;color:var(--text-dim);margin-top:6px;line-height:1.5;`;
    sigField.appendChild(sigHint);
    const syncSig = () => { const has = sigChk.checked; sigLenRow.style.display = has ? 'none' : 'flex'; sigHint.style.display = has ? 'none' : 'block'; };
    sigChk.addEventListener('change', () => { dnaReplaceInput.satHasSignal = sigChk.checked; syncSig(); renderGrid(); updateExecuteBtn(); });
    sigLenIn.addEventListener('input', () => { dnaReplaceInput.satSignalLen = sigLenIn.value; renderGrid(); updateExecuteBtn(); });
    syncSig();
    panelRoot.appendChild(sigField);

    // Variant mode: all AAs at one position, or specific changes across positions.
    const listMode = dnaReplaceInput.satVariantMode === 'list';
    const vmField = mk('div', 'bw-field'); vmField.style.marginTop = '10px';
    vmField.appendChild(mk('label', null, '¿Qué cambios generar?'));
    const vmSeg = mk('div');
    vmSeg.style.cssText = 'display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-top:4px;flex-wrap:wrap;';
    const mkVm = (label, active) => { const b = mk('button', null, label); b.type = 'button'; b.style.cssText = `font-size:0.78rem;padding:7px 14px;border:none;cursor:pointer;background:${active ? 'var(--accent,#1E5FB8)' : 'var(--bg-card)'};color:${active ? '#fff' : 'var(--text-muted)'};font-weight:${active ? '600' : '400'};`; return b; };
    const vmPos = mkVm('Todas las variantes de una posición', !listMode);
    const vmList = mkVm('Cambios concretos (lista)', listMode);
    vmPos.addEventListener('click', () => { if (dnaReplaceInput.satVariantMode !== 'position') { dnaReplaceInput.satVariantMode = 'position'; paint(); updateExecuteBtn(); } });
    vmList.addEventListener('click', () => { if (dnaReplaceInput.satVariantMode !== 'list') { dnaReplaceInput.satVariantMode = 'list'; paint(); updateExecuteBtn(); } });
    vmSeg.appendChild(vmPos); vmSeg.appendChild(vmList);
    vmField.appendChild(vmSeg);
    panelRoot.appendChild(vmField);

    if (!listMode) {
      // Position input (all amino acids at that position).
      const posField = mk('div', 'bw-field'); posField.style.marginTop = '10px';
      posField.appendChild(mk('label', null, 'Posición del aminoácido a mutar (numeración wild-type)'));
      const posHint = mk('div', null, 'Escribe el número (p. ej. 168) o con su aminoácido (p. ej. G168 — se comprueba que coincide). La primera Met es M001.');
      posHint.style.cssText = `font-family:${MONO};font-size:0.7rem;color:var(--text-dim);margin:2px 0 6px;`;
      posField.appendChild(posHint);
      const posIn = document.createElement('input');
      posIn.type = 'text'; posIn.className = 'bw-input'; posIn.style.maxWidth = '200px';
      posIn.placeholder = 'p. ej. 168 o G168'; posIn.value = dnaReplaceInput.satPos;
      posIn.addEventListener('input', () => { dnaReplaceInput.satPos = posIn.value; renderGrid(); updateExecuteBtn(); });
      posField.appendChild(posIn);
      panelRoot.appendChild(posField);
    } else {
      // Substitution list (specific changes across positions).
      const listField = mk('div', 'bw-field'); listField.style.marginTop = '10px';
      listField.appendChild(mk('label', null, 'Sustituciones (numeración wild-type)'));
      const listHint = mk('div', null, 'Escríbelas separadas por comas, p. ej. «G223A, D45V, K102R». Se comprueba cada una (posición y aminoácido original) y podrás desmarcar las que no quieras. Puedes omitir el aminoácido original (p. ej. 223A).');
      listHint.style.cssText = `font-family:${MONO};font-size:0.7rem;color:var(--text-dim);margin:2px 0 6px;line-height:1.5;`;
      listField.appendChild(listHint);
      const listIn = document.createElement('textarea');
      listIn.className = 'bw-input bw-textarea'; listIn.rows = 2; listIn.spellcheck = false;
      listIn.style.cssText = `font-family:${MONO};`;
      listIn.placeholder = 'G223A, D45V, K102R'; listIn.value = dnaReplaceInput.satList;
      listIn.addEventListener('input', () => { dnaReplaceInput.satList = listIn.value; renderGrid(); updateExecuteBtn(); });
      listField.appendChild(listIn);
      panelRoot.appendChild(listField);
    }

    // Name: prefix + mutation + suffix
    const preField = mk('div', 'bw-field'); preField.style.marginTop = '8px';
    preField.appendChild(mk('label', null, 'Nombre del documento (opcional)'));
    const nameRow = mk('div');
    nameRow.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;';
    const preIn = document.createElement('input');
    preIn.type = 'text'; preIn.className = 'bw-input'; preIn.style.cssText = 'flex:1;min-width:130px;max-width:220px;';
    preIn.placeholder = 'Prefijo (p. ej. pAAV_)'; preIn.value = dnaReplaceInput.satPrefix;
    const midTag = mk('span', null, 'G123A');
    midTag.style.cssText = `font-family:${MONO};font-size:0.8rem;font-weight:700;color:var(--accent,#1E5FB8);padding:0 2px;`;
    const sufIn = document.createElement('input');
    sufIn.type = 'text'; sufIn.className = 'bw-input'; sufIn.style.cssText = 'flex:1;min-width:130px;max-width:220px;';
    sufIn.placeholder = 'Sufijo (p. ej. " vole PrP")'; sufIn.value = dnaReplaceInput.satSuffix;
    nameRow.appendChild(preIn); nameRow.appendChild(midTag); nameRow.appendChild(sufIn);
    preField.appendChild(nameRow);
    const preHint = mk('div', null, 'El nombre es «prefijo + mutación + sufijo». La mutación (Original + posición + Nuevo, p. ej. G123A) va en medio. Respeta los espacios que escribas (p. ej. sufijo « vole PrP» → pAAV_G123A vole PrP).');
    preHint.style.cssText = `font-family:${MONO};font-size:0.68rem;color:var(--text-dim);margin-top:6px;line-height:1.5;`;
    preField.appendChild(preHint);
    panelRoot.appendChild(preField);

    // Feature CDS name: prefix + mutation + suffix (same procedure, own fields)
    const featField = mk('div', 'bw-field'); featField.style.marginTop = '10px';
    const featChkWrap = mk('label', 'bw-checkbox-wrap');
    const featChk = document.createElement('input'); featChk.type = 'checkbox'; featChk.checked = dnaReplaceInput.satAddFeat !== false;
    featChkWrap.appendChild(featChk); featChkWrap.appendChild(mk('span', null, 'Renombrar el feature CDS del ORF con este nombre (no crea uno nuevo)'));
    featField.appendChild(featChkWrap);
    const featRow = mk('div');
    featRow.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px;padding-left:24px;';
    const fPreIn = document.createElement('input');
    fPreIn.type = 'text'; fPreIn.className = 'bw-input'; fPreIn.style.cssText = 'flex:1;min-width:130px;max-width:220px;';
    fPreIn.placeholder = 'Prefijo del feature'; fPreIn.value = dnaReplaceInput.satFeatPrefix;
    const fMid = mk('span', null, 'G123A');
    fMid.style.cssText = `font-family:${MONO};font-size:0.8rem;font-weight:700;color:var(--accent,#1E5FB8);padding:0 2px;`;
    const fSufIn = document.createElement('input');
    fSufIn.type = 'text'; fSufIn.className = 'bw-input'; fSufIn.style.cssText = 'flex:1;min-width:130px;max-width:220px;';
    fSufIn.placeholder = 'Sufijo del feature'; fSufIn.value = dnaReplaceInput.satFeatSuffix;
    featRow.appendChild(fPreIn); featRow.appendChild(fMid); featRow.appendChild(fSufIn);
    featField.appendChild(featRow);
    const featHint = mk('div', null, 'Se busca el feature de tipo CDS que cubre el ORF y se le pone este nombre (mismo procedimiento: «prefijo + mutación + sufijo»), sin crear un CDS duplicado. Si no hubiera ninguno, se añade uno. El resto de features se conservan.');
    featHint.style.cssText = `font-family:${MONO};font-size:0.68rem;color:var(--text-dim);margin-top:6px;padding-left:24px;line-height:1.5;`;
    featField.appendChild(featHint);
    const syncFeat = () => { const on = featChk.checked; featRow.style.opacity = on ? '1' : '0.5'; fPreIn.disabled = !on; fSufIn.disabled = !on; };
    featChk.addEventListener('change', () => { dnaReplaceInput.satAddFeat = featChk.checked; syncFeat(); });
    fPreIn.addEventListener('input', () => { dnaReplaceInput.satFeatPrefix = fPreIn.value; });
    fSufIn.addEventListener('input', () => { dnaReplaceInput.satFeatSuffix = fSufIn.value; });
    syncFeat();
    panelRoot.appendChild(featField);

    // Grid area
    const grid = mk('div'); grid.style.marginTop = '10px';
    panelRoot.appendChild(grid);

    const renderGrid = () => {
      grid.innerHTML = '';
      const off = dnaSatOffset();
      if (off.error) {
        const e = mk('div', null, off.error);
        e.style.cssText = 'font-size:0.78rem;color:var(--danger,#f5524b);padding:6px 0;';
        grid.appendChild(e);
        return;
      }

      // ── List mode: specific substitutions across positions ──────────────────
      if (dnaReplaceInput.satVariantMode === 'list') {
        const subs = BWBio.parseSubList(dnaReplaceInput.satList, analyze.residues, off.offset);
        if (!subs.length) {
          const e = mk('div', null, 'Escribe las sustituciones (por ejemplo G223A, D45V) para comprobarlas.');
          e.style.cssText = 'font-size:0.78rem;color:var(--text-dim);padding:6px 0;';
          grid.appendChild(e); return;
        }
        const valid = subs.filter(s => s.valid);
        const key = valid.map(s => s.name).join(',');
        if (dnaReplaceInput.satListKey !== key || !Array.isArray(dnaReplaceInput.satListSel)) {
          dnaReplaceInput.satListKey = key;
          dnaReplaceInput.satListSel = valid.map(s => s.name);
        }
        const sel = new Set(dnaReplaceInput.satListSel);
        const head = mk('div');
        head.style.cssText = 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px;';
        const info = mk('div'); info.style.cssText = `font-family:${MONO};font-size:0.76rem;color:var(--text-muted);`;
        info.innerHTML = `<b>${valid.length}</b> sustitución(es) válida(s)${subs.length - valid.length ? ` · <span style="color:#f5524b">${subs.length - valid.length} con error</span>` : ''}. Marca las que quieras generar:`;
        head.appendChild(info);
        const btnAll = mk('button', 'bw-btn bw-btn-cancel'); btnAll.type = 'button'; btnAll.textContent = 'Todas'; btnAll.style.cssText = 'font-size:0.72rem;padding:4px 10px;';
        const btnNone = mk('button', 'bw-btn bw-btn-cancel'); btnNone.type = 'button'; btnNone.textContent = 'Ninguna'; btnNone.style.cssText = 'font-size:0.72rem;padding:4px 10px;';
        btnAll.addEventListener('click', () => { dnaReplaceInput.satListSel = valid.map(s => s.name); renderGrid(); updateExecuteBtn(); });
        btnNone.addEventListener('click', () => { dnaReplaceInput.satListSel = []; renderGrid(); updateExecuteBtn(); });
        head.appendChild(btnAll); head.appendChild(btnNone);
        grid.appendChild(head);

        const cells = mk('div');
        cells.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:6px;';
        for (const s of subs) {
          if (!s.valid) {
            const bad = mk('div');
            bad.style.cssText = 'border:1px solid #e7c9c9;border-radius:7px;padding:5px 8px;background:#fbf2f2;';
            bad.innerHTML = `<span style="font-family:${MONO};font-size:0.72rem;color:#b3403a">✕ ${s.error}</span>`;
            cells.appendChild(bad); continue;
          }
          const codon = BWBio.variantCodon(s.newAA, oldSeq);
          const dist = BWBio.codonDistance(s.origCodon, codon);
          const on = sel.has(s.name);
          const lab = mk('label');
          lab.style.cssText = `display:flex;align-items:center;gap:7px;border:1px solid ${on ? 'var(--accent,#1E5FB8)' : 'var(--border)'};border-radius:7px;padding:5px 8px;cursor:pointer;background:${on ? 'rgba(30,95,184,0.08)' : 'var(--bg-card)'};`;
          const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = on;
          cb.addEventListener('change', () => { const set = new Set(dnaReplaceInput.satListSel); if (cb.checked) set.add(s.name); else set.delete(s.name); dnaReplaceInput.satListSel = valid.map(v => v.name).filter(n => set.has(n)); renderGrid(); updateExecuteBtn(); });
          const codonNote = off.offset ? ` · codón ${s.codonPos}` : '';
          const txt = mk('span'); txt.style.cssText = `font-family:${MONO};font-size:0.73rem;`;
          txt.innerHTML = `<b>${s.name}</b> · ${BWBio.AA_NAMES[s.orig]}→${BWBio.AA_NAMES[s.newAA]}${codonNote} · ${codon} <span style="color:var(--text-dim)">(${dist} nt)</span>`;
          lab.appendChild(cb); lab.appendChild(txt);
          cells.appendChild(lab);
        }
        grid.appendChild(cells);

        const count = mk('div'); count.style.cssText = `font-family:${MONO};font-size:0.74rem;color:var(--text-muted);margin-top:8px;`;
        const chosen = valid.filter(s => sel.has(s.name));
        const prefix = dnaReplaceInput.satPrefix || '', suffix = dnaReplaceInput.satSuffix || '';
        count.innerHTML = chosen.length
          ? `Se generarán <b>${chosen.length}</b> construcción(es): ${chosen.slice(0, 6).map(s => `${prefix}${s.name}${suffix}`).join(', ')}${chosen.length > 6 ? '…' : ''}`
          : 'No hay ninguna sustitución seleccionada.';
        grid.appendChild(count);
        return;
      }

      const parsed = BWBio.parsePosition(dnaReplaceInput.satPos, analyze.residues, off.offset);
      if (parsed.error) {
        const e = mk('div', null, dnaReplaceInput.satPos ? parsed.error : 'Escribe una posición para ver las 19 variantes.');
        e.style.cssText = `font-size:0.78rem;color:${dnaReplaceInput.satPos ? 'var(--danger,#f5524b)' : 'var(--text-dim)'};padding:6px 0;`;
        grid.appendChild(e);
        return;
      }
      const key = parsed.codonPos + parsed.orig;
      if (dnaReplaceInput.satKey !== key || !Array.isArray(dnaReplaceInput.satAAs)) {
        dnaReplaceInput.satKey = key;
        dnaReplaceInput.satAAs = BWBio.AA_ORDER.filter(a => a !== parsed.orig);
      }
      const sel = new Set(dnaReplaceInput.satAAs);
      const posLabel = String(parsed.pos).padStart(3, '0');

      const head = mk('div');
      head.style.cssText = 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px;';
      const info = mk('div');
      info.style.cssText = `font-family:${MONO};font-size:0.76rem;color:var(--text-muted);`;
      const mapNote = off.offset ? ` <span style="color:#f7a83e">(sin péptido señal: se cambia el codón ${parsed.codonPos} del ORF)</span>` : '';
      info.innerHTML = `Posición <b>${parsed.pos}</b>: original <b>${parsed.orig}</b> (${BWBio.AA_NAMES[parsed.orig] || '?'}) · codón <b>${parsed.origCodon}</b>${mapNote}. Marca las variantes a generar:`;
      head.appendChild(info);
      const btnAll = mk('button', 'bw-btn bw-btn-cancel'); btnAll.type = 'button'; btnAll.textContent = 'Todas (19)'; btnAll.style.cssText = 'font-size:0.72rem;padding:4px 10px;';
      const btnNone = mk('button', 'bw-btn bw-btn-cancel'); btnNone.type = 'button'; btnNone.textContent = 'Ninguna'; btnNone.style.cssText = 'font-size:0.72rem;padding:4px 10px;';
      btnAll.addEventListener('click', () => { dnaReplaceInput.satAAs = BWBio.AA_ORDER.filter(a => a !== parsed.orig); renderGrid(); updateExecuteBtn(); });
      btnNone.addEventListener('click', () => { dnaReplaceInput.satAAs = []; renderGrid(); updateExecuteBtn(); });
      head.appendChild(btnAll); head.appendChild(btnNone);
      grid.appendChild(head);

      const cells = mk('div');
      cells.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px;';
      for (const aa of BWBio.AA_ORDER) {
        if (aa === parsed.orig) continue;   // skip the original → 19 remain
        const codon = BWBio.variantCodon(aa, oldSeq);
        const dist = BWBio.codonDistance(parsed.origCodon, codon);
        const on = sel.has(aa);
        const lab = mk('label');
        lab.style.cssText = `display:flex;align-items:center;gap:7px;border:1px solid ${on ? 'var(--accent,#1E5FB8)' : 'var(--border)'};border-radius:7px;padding:5px 8px;cursor:pointer;background:${on ? 'rgba(30,95,184,0.08)' : 'var(--bg-card)'};`;
        const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = on;
        cb.addEventListener('change', () => {
          const s = new Set(dnaReplaceInput.satAAs);
          if (cb.checked) s.add(aa); else s.delete(aa);
          dnaReplaceInput.satAAs = BWBio.AA_ORDER.filter(a => s.has(a));
          renderGrid(); updateExecuteBtn();
        });
        const txt = mk('span');
        txt.style.cssText = `font-family:${MONO};font-size:0.74rem;`;
        txt.innerHTML = `<b>${parsed.orig}${posLabel}${aa}</b> · ${BWBio.AA_NAMES[aa]} · ${codon} <span style="color:var(--text-dim)">(${dist} nt)</span>`;
        lab.appendChild(cb); lab.appendChild(txt);
        cells.appendChild(lab);
      }
      grid.appendChild(cells);

      const count = mk('div');
      count.style.cssText = `font-family:${MONO};font-size:0.74rem;color:var(--text-muted);margin-top:8px;`;
      const n = dnaReplaceInput.satAAs.length;
      const prefix = dnaReplaceInput.satPrefix || '';
      const suffix = dnaReplaceInput.satSuffix || '';
      count.innerHTML = n
        ? `Se generarán <b>${n}</b> construcción(es): ${dnaReplaceInput.satAAs.slice(0, 6).map(a => `${prefix}${parsed.orig}${posLabel}${a}${suffix}`).join(', ')}${n > 6 ? '…' : ''}`
        : 'No hay ninguna variante seleccionada.';
      grid.appendChild(count);
    };

    preIn.addEventListener('input', () => { dnaReplaceInput.satPrefix = preIn.value; renderGrid(); updateExecuteBtn(); });
    sufIn.addEventListener('input', () => { dnaReplaceInput.satSuffix = sufIn.value; renderGrid(); updateExecuteBtn(); });
    renderGrid();
  };

  // Re-analyse live if the ORF (oldSeq) textarea above changes.
  if (oldTa) oldTa.addEventListener('input', paint);
  paint();
}

function renderDnaReplaceBulkResults(data) {
  const existing = $('dna-replace-results');
  if (existing) existing.remove();
  const root = mk('div', 'degen-results');
  root.id = 'dna-replace-results';

  const { results, skipped, meta, zipName } = data;
  const okCount = results.filter(r => r.ok).length;

  const summary = mk('div', 'degen-summary');
  summary.innerHTML = `Transformación en bulk · <strong>${okCount}</strong> documento(s) generado(s)${meta.failed ? ` · <strong style="color:var(--red)">${meta.failed}</strong> con error` : ''}${skipped.length ? ` · ${skipped.length} fila(s) omitida(s) sin secuencia` : ''}`;
  root.appendChild(summary);

  // Per-row table with original/new sizes.
  const tableWrap = mk('div');
  tableWrap.style.cssText = 'overflow-x:auto;border:1px solid var(--border);border-radius:8px;margin-top:4px;';
  const table = mk('table');
  table.style.cssText = `width:100%;border-collapse:collapse;font-family:${MUT_MONO};font-size:0.74rem;`;
  const thStyle = 'text-align:left;padding:7px 10px;border-bottom:1px solid var(--border);color:var(--text-dim);white-space:nowrap;';
  table.innerHTML = `<thead><tr>
    <th style="${thStyle}">#</th>
    <th style="${thStyle}">Documento</th>
    <th style="${thStyle}">Feature</th>
    <th style="${thStyle}">nt original</th>
    <th style="${thStyle}">nt nuevo</th>
    <th style="${thStyle}">Δ</th>
    <th style="${thStyle}">Cambios nt-a-nt</th>
    <th style="${thStyle}">Estado</th>
  </tr></thead>`;
  const tbody = mk('tbody');
  results.forEach((r, i) => {
    const tr = mk('tr');
    const td = (html, color) => { const c = mk('td', null); c.style.cssText = `padding:6px 10px;border-bottom:1px solid var(--border);white-space:nowrap;${color ? 'color:' + color + ';' : ''}`; c.innerHTML = html; return c; };
    tr.appendChild(td(String(i + 1)));
    tr.appendChild(td(`${r.filename || ''}${r.name ? '' : ' <span style="color:var(--text-dim)">(sin nombre)</span>'}`));
    tr.appendChild(td(r.feat || '<span style="color:var(--text-dim)">—</span>'));
    if (r.ok) {
      tr.appendChild(td(r.oldTotal.toLocaleString('es-ES')));
      tr.appendChild(td(r.newTotal.toLocaleString('es-ES')));
      tr.appendChild(td((r.delta >= 0 ? '+' : '') + r.delta.toLocaleString('es-ES')));
      tr.appendChild(td(r.ntCompare.applicable ? `<strong>${r.ntCompare.changes.toLocaleString('es-ES')}</strong>` : '<span style="color:var(--text-dim)">n/a (distinto tamaño)</span>'));
      tr.appendChild(td('✓ OK', 'var(--green)'));
    } else {
      tr.appendChild(td('—')); tr.appendChild(td('—')); tr.appendChild(td('—')); tr.appendChild(td('—'));
      tr.appendChild(td('⚠ ' + r.error, 'var(--red)'));
    }
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  root.appendChild(tableWrap);

  if (skipped.length) {
    const sk = mk('div');
    sk.style.cssText = `font-family:${MUT_MONO};font-size:0.72rem;color:var(--text-dim);margin-top:8px;`;
    sk.textContent = `Filas omitidas por no tener secuencia nueva: ${skipped.map(s => 'línea ' + s.lineNo).join(', ')}.`;
    root.appendChild(sk);
  }

  const detail = mk('div');
  detail.style.cssText = `font-family:${MUT_MONO};font-size:0.78rem;color:var(--text-muted);line-height:1.8;margin-top:8px;`;
  detail.innerHTML = `📦 Todo se descarga en <strong>${zipName}</strong>, que incluye los .dna generados y un <strong>informe.csv</strong> con el detalle de cada transformación.`;
  root.appendChild(detail);

  const note = mk('div', 'degen-warn');
  note.style.cssText = 'background:rgba(30,95,184,0.06);border-color:var(--border);';
  note.innerHTML = '💡 La secuencia a sustituir y las opciones (borrado/reajuste de features, tipo de feature) son comunes a todas. Ábrelos en SnapGene para comprobarlos.';
  root.appendChild(note);

  const paramsZone = $('params-zone');
  paramsZone.parentNode.insertBefore(root, paramsZone.nextSibling);
}

function renderDnaReplaceResults(r) {
  const existing = $('dna-replace-results');
  if (existing) existing.remove();
  const root = mk('div', 'degen-results');
  root.id = 'dna-replace-results';

  const summary = mk('div', 'degen-summary');
  summary.innerHTML = `Sustitución aplicada en la posición <strong>${(r.pos + 1).toLocaleString('es-ES')}</strong> · documento ${r.circular ? 'circular' : 'lineal'}`;
  root.appendChild(summary);

  if (r.occurrences > 1) {
    const warn = mk('div', 'degen-warn');
    warn.innerHTML = `⚠ La secuencia a sustituir aparecía <strong>${r.occurrences} veces</strong>; se ha sustituido solo la <strong>primera</strong> (posición ${(r.pos + 1).toLocaleString('es-ES')}). Si querías otra, afina la secuencia para que sea única.`;
    root.appendChild(warn);
  }

  const stats = mk('div', 'degen-stats');
  const mkStat = (val, lbl) => {
    const s = mk('div', 'degen-stat');
    s.innerHTML = `<span class="degen-stat-val">${val}</span><span class="degen-stat-lbl">${lbl}</span>`;
    return s;
  };
  stats.appendChild(mkStat(r.oldLen.toLocaleString('es-ES'), 'nt<br>retirados'));
  stats.appendChild(mkStat(r.newLen.toLocaleString('es-ES'), 'nt<br>insertados'));
  stats.appendChild(mkStat((r.delta >= 0 ? '+' : '') + r.delta.toLocaleString('es-ES'), 'variación<br>de longitud'));
  stats.appendChild(mkStat(r.newTotal.toLocaleString('es-ES'), 'nt totales<br>(resultado)'));
  if (r.ntCompare && r.ntCompare.applicable) {
    stats.appendChild(mkStat(r.ntCompare.changes.toLocaleString('es-ES'), 'cambios<br>nt-a-nt'));
  }
  root.appendChild(stats);

  const detail = mk('div');
  detail.style.cssText = `font-family:${MUT_MONO};font-size:0.78rem;color:var(--text-muted);line-height:1.8;`;
  const line = (txt) => { const d = mk('div', null, txt); detail.appendChild(d); };
  line(`📄 Fichero de salida: <strong>${r.outName}</strong>`);
  if (r.ntCompare && r.ntCompare.applicable) {
    const pct = r.ntCompare.total ? (r.ntCompare.changes / r.ntCompare.total * 100) : 0;
    line(`🔬 Comparación nt-a-nt con el original: <strong>${r.ntCompare.changes.toLocaleString('es-ES')}</strong> cambio(s) sobre ${r.ntCompare.total.toLocaleString('es-ES')} nt (${pct.toFixed(2)} %).`);
  } else if (r.ntCompare) {
    line(`🔬 La secuencia final (${r.ntCompare.newTotal.toLocaleString('es-ES')} nt) tiene distinto tamaño que la original (${r.ntCompare.total.toLocaleString('es-ES')} nt); por eso no se calcula el número de cambios nt-a-nt.`);
  }
  if (r.featResult.added) line('🏷️ Feature nueva añadida para la secuencia entrante.');
  if (r.featResult.removed) line(`🗑️ Features borradas por solapar la región: <strong>${r.featResult.removed}</strong>.`);
  if (r.featResult.shifted) line(`↔️ Features con coordenadas reajustadas: <strong>${r.featResult.shifted}</strong>.`);
  if (r.nameApplied) line('✏️ Nombre interno (custom map label) actualizado.');
  line('Descarga el resultado con el botón «⬇ Descargar resultado».');
  root.appendChild(detail);

  const note = mk('div', 'degen-warn');
  note.style.cssText = 'background:rgba(30,95,184,0.06);border-color:var(--border);';
  note.innerHTML = '💡 Ábrelo en SnapGene para comprobarlo. Otros elementos que dependen de la posición (p. ej. sitios de unión de primers) no se recalculan aquí; SnapGene los reanaliza al abrir.';
  root.appendChild(note);

  const paramsZone = $('params-zone');
  paramsZone.parentNode.insertBefore(root, paramsZone.nextSibling);
}

// ── .dna vs .gb sequence comparison (verify provider) ─────────────────────────
//
// Compares the plasmid you designed in SnapGene (.dna, binary) against the one
// the provider (e.g. GenScript) sends back (.gb, GenBank text). Files are paired
// by name (extension ignored, case-insensitive); only complete pairs are
// compared, nt-by-nt. Because a circular plasmid can be linearised at any base
// and on either strand, a sequence that differs only by a circular rotation
// and/or reverse-complement IS the same molecule — we detect and label that
// instead of crying "mismatch".

function cmpSeqFromDna(bytes) {
  const packets = dnaParsePackets(bytes);
  dnaValidateCookie(packets);
  const dnaPkt = packets.find(p => p.type === 0);
  if (!dnaPkt) throw new Error('El .dna no contiene secuencia de ADN.');
  const seq = dnaBytesToAscii(dnaPkt.data.slice(1)).toUpperCase().replace(/[^A-Z]/g, '');
  return { seq, circular: (dnaPkt.data[0] & 1) === 1, topologyKnown: true };
}

function cmpSeqFromGb(text) {
  const locusLine = (text.match(/^LOCUS[^\n]*/m) || [''])[0];
  const circular = /\bcircular\b/i.test(locusLine);
  const linear = /\blinear\b/i.test(locusLine);
  let seq = '';
  const oi = text.search(/^ORIGIN/m);
  if (oi >= 0) {
    let after = text.slice(oi).replace(/^ORIGIN[^\n]*\n?/, '');
    const term = after.search(/^\/\//m);
    if (term >= 0) after = after.slice(0, term);
    seq = after.replace(/[^A-Za-z]/g, '').toUpperCase();
  }
  return { seq, circular, topologyKnown: circular || linear };
}

const CMP_COMP = { A:'T',T:'A',G:'C',C:'G',U:'A',N:'N',R:'Y',Y:'R',S:'S',W:'W',K:'M',M:'K',B:'V',V:'B',D:'H',H:'D' };
function cmpRevComp(s) {
  let out = '';
  for (let i = s.length - 1; i >= 0; i--) out += CMP_COMP[s[i]] || 'N';
  return out;
}

// Compare two sequences as (possibly circular) plasmids.
function cmpCompare(a, b) {
  if (a === b && a.length > 0) return { status: 'identical', len: a.length };
  if (a.length !== b.length) return { status: 'mismatch', reason: 'length', lenA: a.length, lenB: b.length };
  const aa = a + a;
  const idx = aa.indexOf(b);
  if (idx > 0) return { status: 'rotated', offset: idx, len: a.length };
  const rb = cmpRevComp(b);
  const idxR = aa.indexOf(rb);
  if (idxR >= 0) return { status: 'revcomp', offset: idxR, len: a.length };
  let diffs = 0, first = -1;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) { diffs++; if (first < 0) first = i; }
  return { status: 'mismatch', reason: 'content', diffs, first, len: a.length };
}

const cmpFmt = n => Number(n).toLocaleString('es-ES');

function renderDnaCompareUI(zone) {
  const cmp = { items: [], mode: 'byname' }; // { name, base, kind, seq, circular, topologyKnown, error }
  const root = mk('div', 'bw-params');

  // ── Explanation ─────────────────────────────────────────────────────────────
  const intro = mk('div', 'dnacmp-intro');
  intro.innerHTML = `
    <h3>¿Qué hace y por qué?</h3>
    <p>Cuando diseñas un plásmido en <strong>SnapGene</strong> obtienes un fichero <code>.dna</code>.
       El proveedor (p. ej. <strong>GenScript</strong>) te lo fabrica y te devuelve la secuencia en formato
       <strong>GenBank</strong> <code>.gb</code>. Esta herramienta confirma que lo que te van a fabricar
       <strong>coincide exactamente</strong> con lo que pediste: mismo número de nucleótidos y mismos nucleótidos.
       La comparación es <strong>nucleótido a nucleótido</strong> y, como un plásmido circular puede venir «cortado»
       en otro punto o en la hebra contraria, también detecta ese caso: sigue siendo <strong>la misma molécula</strong>.</p>`;
  root.appendChild(intro);

  // ── Mode selector: two clearly-differentiated ways to compare ────────────────
  const modes = mk('div', 'dnacmp-modes');
  modes.innerHTML = `
    <label class="dnacmp-mode is-sel" data-mode="byname">
      <input type="radio" name="dnacmp-mode" value="byname" checked>
      <div class="dnacmp-mode-body">
        <div class="dnacmp-mode-t">Varios ficheros · emparejar por nombre</div>
        <div class="dnacmp-mode-d">Suelta de golpe <strong>todos</strong> los <code>.dna</code> y <code>.gb</code>.
          Se emparejan por nombre (<strong>misma base = misma pareja</strong>, ignorando extensión y mayúsculas) y se
          comparan uno a uno. Ideal para verificar muchos plásmidos a la vez.</div>
      </div>
    </label>
    <label class="dnacmp-mode" data-mode="pair">
      <input type="radio" name="dnacmp-mode" value="pair">
      <div class="dnacmp-mode-body">
        <div class="dnacmp-mode-t">Una sola pareja · nombres distintos</div>
        <div class="dnacmp-mode-d">Compara <strong>exactamente un <code>.dna</code> con un <code>.gb</code></strong>,
          <strong>aunque se llamen distinto</strong>. Útil cuando el proveedor te devuelve el fichero con otro nombre.
          Solo se admite una pareja (un fichero de cada extensión).</div>
      </div>
    </label>`;
  root.appendChild(modes);

  // ── Drop zone ───────────────────────────────────────────────────────────────
  const drop = makeDropZone({
    label: 'Suelta aquí los .dna y los .gb',
    sub: 'Arrastra o haz clic · varios a la vez',
    accept: '.dna,.gb,.gbk,.gbff,.genbank',
    multiple: true,
    onFiles: handleFiles,
  });
  root.appendChild(drop);

  const listWrap = mk('div', 'dnacmp-loaded');
  root.appendChild(listWrap);

  const actions = mk('div', 'dnacmp-actions');
  const btnCompare = mk('button', 'bw-btn bw-btn-primary', 'Comparar');
  btnCompare.type = 'button'; btnCompare.disabled = true;
  const btnClear = mk('button', 'bw-btn bw-btn-cancel', 'Vaciar');
  btnClear.type = 'button';
  actions.appendChild(btnCompare); actions.appendChild(btnClear);
  root.appendChild(actions);

  const results = mk('div', 'dnacmp-results');
  root.appendChild(results);

  zone.appendChild(root);

  const kindOf = name =>
    /\.dna$/i.test(name) ? 'dna' :
    /\.(gb|gbk|gbff|genbank)$/i.test(name) ? 'gb' : null;
  const baseOf = name => name.replace(/\.[^.\\/]+$/, '').replace(/^.*[\\/]/, '');

  const dropLabel = () => cmp.mode === 'pair' ? 'Suelta un .dna y un .gb' : 'Suelta aquí los .dna y los .gb';

  // In single-pair mode only one valid file of each extension is kept (the last
  // dropped wins); error chips are kept so the user sees what failed.
  function enforcePairLimit() {
    if (cmp.mode !== 'pair') return;
    let dna = null, gb = null; const errs = [];
    for (const it of cmp.items) {
      if (it.error) { errs.push(it); continue; }
      if (it.kind === 'dna') dna = it;
      else if (it.kind === 'gb') gb = it;
    }
    cmp.items = [...(dna ? [dna] : []), ...(gb ? [gb] : []), ...errs];
  }

  function updateEnabled() {
    if (cmp.mode === 'pair') {
      const dna = cmp.items.find(it => it.kind === 'dna' && !it.error);
      const gb = cmp.items.find(it => it.kind === 'gb' && !it.error);
      btnCompare.disabled = !(dna && gb);
    } else {
      btnCompare.disabled = cmp.items.length === 0;
    }
  }

  function setMode(m) {
    cmp.mode = m === 'pair' ? 'pair' : 'byname';
    modes.querySelectorAll('.dnacmp-mode').forEach(el => el.classList.toggle('is-sel', el.dataset.mode === cmp.mode));
    enforcePairLimit();
    results.innerHTML = '';
    renderLoaded();
    updateEnabled();
    const txt = drop.querySelector('.bw-drop-text');
    if (txt) txt.textContent = dropLabel();
  }
  modes.querySelectorAll('input[name="dnacmp-mode"]').forEach(inp =>
    inp.addEventListener('change', () => setMode(inp.value)));

  async function handleFiles(files) {
    for (const f of files) {
      const kind = kindOf(f.name);
      const base = baseOf(f.name);
      if (!kind) { cmp.items.push({ name: f.name, base, kind: null, error: 'Extensión no reconocida (usa .dna o .gb).' }); continue; }
      try {
        if (kind === 'dna') {
          const buf = new Uint8Array(await f.arrayBuffer());
          const { seq, circular, topologyKnown } = cmpSeqFromDna(buf);
          if (!seq) throw new Error('Secuencia vacía.');
          cmp.items.push({ name: f.name, base, kind, seq, circular, topologyKnown });
        } else {
          const text = await f.text();
          const { seq, circular, topologyKnown } = cmpSeqFromGb(text);
          if (!seq) throw new Error('No se encontró la sección ORIGIN con secuencia.');
          cmp.items.push({ name: f.name, base, kind, seq, circular, topologyKnown });
        }
      } catch (e) {
        cmp.items.push({ name: f.name, base, kind, error: e.message });
      }
    }
    enforcePairLimit();
    renderLoaded();
    updateEnabled();
  }

  function renderLoaded() {
    listWrap.innerHTML = '';
    if (!cmp.items.length) return;
    const head = mk('div', 'dnacmp-loaded-head',
      cmp.mode === 'pair' ? 'Pareja a comparar (nombres distintos permitidos)' : `${cmp.items.length} fichero(s) cargado(s)`);
    listWrap.appendChild(head);
    const grid = mk('div', 'dnacmp-chips');
    cmp.items.forEach((it, i) => {
      const chip = mk('div', 'dnacmp-chip' + (it.error ? ' is-err' : ''));
      const badge = it.kind ? it.kind.toUpperCase() : '??';
      chip.innerHTML = `<span class="dnacmp-chip-badge dnacmp-${it.kind || 'bad'}">${badge}</span>` +
        `<span class="dnacmp-chip-name">${it.name}</span>` +
        (it.error ? `<span class="dnacmp-chip-err">⚠ ${it.error}</span>`
                  : `<span class="dnacmp-chip-meta">${cmpFmt(it.seq.length)} nt</span>`);
      const x = mk('button', 'dnacmp-chip-x', '×');
      x.type = 'button';
      x.addEventListener('click', () => { cmp.items.splice(i, 1); renderLoaded(); updateEnabled(); });
      chip.appendChild(x);
      grid.appendChild(chip);
    });
    listWrap.appendChild(grid);
  }

  btnClear.addEventListener('click', () => {
    cmp.items = [];
    renderLoaded();
    results.innerHTML = '';
    updateEnabled();
    const txt = drop.querySelector('.bw-drop-text');
    if (txt) txt.textContent = dropLabel();
  });

  btnCompare.addEventListener('click', () => runComparison(cmp.items, results, cmp.mode));
}

function runComparison(items, results, mode) {
  if (mode === 'pair') return runPairComparison(items, results);
  // Group by base name (case-insensitive). Keep the first valid item per side.
  const groups = new Map(); // key -> { base, dna, gb, dnaErr, gbErr }
  for (const it of items) {
    const key = it.base.toLowerCase();
    if (!groups.has(key)) groups.set(key, { base: it.base, dna: null, gb: null, dnaErr: null, gbErr: null });
    const g = groups.get(key);
    if (it.kind === 'dna') { if (it.error) g.dnaErr = g.dnaErr || it; else g.dna = g.dna || it; }
    else if (it.kind === 'gb') { if (it.error) g.gbErr = g.gbErr || it; else g.gb = g.gb || it; }
    else { g.gbErr = g.gbErr || it; } // unknown extension
  }

  const rows = [];
  for (const g of groups.values()) {
    if (g.dna && g.gb) {
      rows.push({ kind: 'pair', base: g.base, dna: g.dna, gb: g.gb, cmp: cmpCompare(g.dna.seq, g.gb.seq) });
    } else if (g.dna && !g.gb) {
      rows.push({ kind: 'lonely', base: g.base, have: 'dna', miss: 'gb', item: g.dna, err: g.gbErr });
    } else if (g.gb && !g.dna) {
      rows.push({ kind: 'lonely', base: g.base, have: 'gb', miss: 'dna', item: g.gb, err: g.dnaErr });
    } else {
      rows.push({ kind: 'error', base: g.base, item: g.dnaErr || g.gbErr });
    }
  }
  rows.sort((a, b) => a.base.localeCompare(b.base, undefined, { numeric: true, sensitivity: 'base' }));

  // Tally
  const isPass = r => r.kind === 'pair' && r.cmp.status !== 'mismatch';
  const identical = rows.filter(r => r.kind === 'pair' && r.cmp.status === 'identical').length;
  const sameMol = rows.filter(r => r.kind === 'pair' && (r.cmp.status === 'rotated' || r.cmp.status === 'revcomp')).length;
  const fail = rows.filter(r => r.kind === 'pair' && r.cmp.status === 'mismatch').length;
  const lonely = rows.filter(r => r.kind === 'lonely').length;
  const errs = rows.filter(r => r.kind === 'error').length;

  results.innerHTML = '';

  const summary = mk('div', 'dnacmp-summary');
  const pill = (cls, n, label) => `<div class="dnacmp-pill ${cls}"><span class="dnacmp-pill-n">${n}</span> ${label}</div>`;
  summary.innerHTML =
    pill('ok', identical, 'idénticas') +
    pill('ok2', sameMol, 'misma molécula<br><small>(rotada / hebra inversa)</small>') +
    pill('bad', fail, 'NO coinciden') +
    pill('warn', lonely, 'sin pareja') +
    (errs ? pill('warn', errs, 'con error') : '');
  results.appendChild(summary);

  if (!rows.length) {
    results.appendChild(mk('div', 'degen-cerr', 'No hay nada que comparar.'));
    return;
  }

  for (const r of rows) results.appendChild(buildCmpCard(r));
}

// Single-pair mode: compare one .dna against one .gb directly, ignoring names.
function runPairComparison(items, results) {
  const dna = items.find(it => it.kind === 'dna' && !it.error);
  const gb = items.find(it => it.kind === 'gb' && !it.error);
  results.innerHTML = '';
  if (!dna || !gb) {
    results.appendChild(mk('div', 'degen-cerr', 'Necesitas exactamente un .dna y un .gb para comparar la pareja.'));
    return;
  }
  const c = cmpCompare(dna.seq, gb.seq);
  // Show both filenames as the card title, since in this mode they can differ.
  const r = { kind: 'pair', base: `${dna.name}  ↔  ${gb.name}`, dna, gb, cmp: c };
  results.appendChild(buildCmpCard(r));
}

function buildCmpCard(r) {
  const card = mk('div', 'dnacmp-card');

  if (r.kind === 'pair') {
    const c = r.cmp;
    const pass = c.status !== 'mismatch';
    card.classList.add(pass ? (c.status === 'identical' ? 'is-ident' : 'is-same') : 'is-fail');

    const icon = pass ? (c.status === 'identical' ? '✓' : '↻') : '✗';
    let title, sub;
    if (c.status === 'identical') {
      title = 'Secuencia IDÉNTICA';
      sub = 'Mismo número de nucleótidos y mismos nucleótidos, en el mismo orden.';
    } else if (c.status === 'rotated') {
      title = 'Misma secuencia (mismo plásmido)';
      sub = `El <code>.gb</code> está «cortado» en otra posición: empieza en el nt <strong>${cmpFmt(c.offset + 1)}</strong> de tu <code>.dna</code>. En un plásmido circular es exactamente la misma molécula.`;
    } else if (c.status === 'revcomp') {
      title = 'Misma secuencia (hebra inversa)';
      sub = `El <code>.gb</code> es la <strong>hebra complementaria inversa</strong>${c.offset ? ` y empieza en otra posición (nt <strong>${cmpFmt(c.offset + 1)}</strong>)` : ''}. Es la misma molécula de doble cadena.`;
    } else if (c.reason === 'length') {
      title = 'NO COINCIDE — distinta longitud';
      sub = `Tu <code>.dna</code> tiene <strong>${cmpFmt(c.lenA)} nt</strong> y el <code>.gb</code> del proveedor <strong>${cmpFmt(c.lenB)} nt</strong> (diferencia de ${cmpFmt(Math.abs(c.lenA - c.lenB))} nt).`;
    } else {
      title = 'NO COINCIDE — mismos nt, secuencia distinta';
      sub = `Misma longitud (${cmpFmt(c.len)} nt) pero <strong>${cmpFmt(c.diffs)} nucleótido(s) distinto(s)</strong>; el primero en la posición <strong>${cmpFmt(c.first + 1)}</strong>.`;
    }

    card.innerHTML =
      `<div class="dnacmp-card-bar"><span class="dnacmp-ico">${icon}</span>` +
      `<div class="dnacmp-card-h"><div class="dnacmp-card-name">${r.base}</div>` +
      `<div class="dnacmp-card-title">${title}</div></div></div>` +
      `<div class="dnacmp-card-body">` +
        cmpLenRow(r.dna, r.gb, c) +
        `<p class="dnacmp-card-sub">${sub}</p>` +
      `</div>`;
    // Only when there ARE differences: a collapsed Clustal-style diff viewer.
    if (c.status === 'mismatch') {
      card.querySelector('.dnacmp-card-body').appendChild(buildDnaDiff(r.dna.seq, r.gb.seq));
    }
    return card;
  }

  if (r.kind === 'lonely') {
    card.classList.add('is-lonely');
    const haveDna = r.have === 'dna';
    card.innerHTML =
      `<div class="dnacmp-card-bar"><span class="dnacmp-ico">⚠</span>` +
      `<div class="dnacmp-card-h"><div class="dnacmp-card-name">${r.base}</div>` +
      `<div class="dnacmp-card-title">Sin pareja — no comparado</div></div></div>` +
      `<div class="dnacmp-card-body"><p class="dnacmp-card-sub">` +
      `Solo se ha encontrado el <code>.${haveDna ? 'dna' : 'gb'}</code> (${cmpFmt(r.item.seq.length)} nt). ` +
      `Falta el <code>.${r.miss}</code> con el mismo nombre, así que no se puede comparar.` +
      (r.err ? ` <span class="dnacmp-chip-err">Había un <code>.${r.miss}</code> con ese nombre pero falló: ${r.err.error}</span>` : '') +
      `</p></div>`;
    return card;
  }

  // error
  card.classList.add('is-fail');
  card.innerHTML =
    `<div class="dnacmp-card-bar"><span class="dnacmp-ico">✗</span>` +
    `<div class="dnacmp-card-h"><div class="dnacmp-card-name">${r.base}</div>` +
    `<div class="dnacmp-card-title">Error al leer el fichero</div></div></div>` +
    `<div class="dnacmp-card-body"><p class="dnacmp-card-sub">${r.item ? r.item.error : 'Error desconocido.'}</p></div>`;
  return card;
}

// Visual nt-count comparison: two bars + an equals/!= verdict.
function cmpLenRow(dna, gb, c) {
  const eq = c.status !== 'mismatch' || c.reason === 'content'; // same length
  const verdict = eq
    ? `<span class="dnacmp-eq ok">${cmpFmt(dna.seq.length)} nt = ${cmpFmt(gb.seq.length)} nt</span>`
    : `<span class="dnacmp-eq bad">${cmpFmt(dna.seq.length)} nt ≠ ${cmpFmt(gb.seq.length)} nt</span>`;
  const ntOk = (c.status === 'identical' || c.status === 'rotated' || c.status === 'revcomp');
  const top = (dna.circular || gb.circular) ? 'circular' : (dna.topologyKnown && gb.topologyKnown ? 'lineal' : '');
  return `<div class="dnacmp-lenrow">
      <div class="dnacmp-side"><span class="dnacmp-side-tag dnacmp-dna">.dna</span> ${cmpFmt(dna.seq.length)} nt</div>
      ${verdict}
      <div class="dnacmp-side"><span class="dnacmp-side-tag dnacmp-gb">.gb</span> ${cmpFmt(gb.seq.length)} nt</div>
    </div>
    <div class="dnacmp-checks">
      <span class="dnacmp-check ${eq ? 'ok' : 'bad'}">${eq ? '✓' : '✗'} mismo nº de nt</span>
      <span class="dnacmp-check ${ntOk ? 'ok' : 'bad'}">${ntOk ? '✓' : '✗'} mismos nucleótidos</span>
      ${top ? `<span class="dnacmp-check neutral">${top === 'circular' ? '◯ circular' : '— lineal'}</span>` : ''}
    </div>`;
}

// ── Clustal-style diff viewer (only for mismatching pairs) ────────────────────
//
// Cheap O(n) alignment: trim the common prefix and suffix, then the differing
// middle is padded with gaps «−» so both rows line up. This pinpoints a single
// insertion/deletion or a substitution block exactly, works for any plasmid size
// (no O(n·m) DP matrix), and for a run of substitutions degrades to a plain
// positional comparison. We render it Clustal-style: 60 columns per block, with
// the differing nucleotides highlighted.

function cmpAlign(a, b) {
  const la = a.length, lb = b.length;
  const maxP = Math.min(la, lb);
  let p = 0;
  while (p < maxP && a[p] === b[p]) p++;
  let s = 0;
  const maxS = maxP - p;
  while (s < maxS && a[la - 1 - s] === b[lb - 1 - s]) s++;
  const aMid = a.slice(p, la - s);
  const bMid = b.slice(p, lb - s);
  const width = Math.max(aMid.length, bMid.length);
  const pre = a.slice(0, p);
  const suf = a.slice(la - s);
  const aa = pre + aMid + '-'.repeat(width - aMid.length) + suf;
  const bb = pre + bMid + '-'.repeat(width - bMid.length) + suf;
  return { aa, bb };
}

function cmpMismatchCount(aln) {
  let m = 0;
  for (let i = 0; i < aln.aa.length; i++) if (aln.aa[i] !== aln.bb[i]) m++;
  return m;
}

// Align forward and against the reverse complement of b; keep whichever differs
// less. A revcomp-with-a-few-mutations would otherwise show as a sea of red.
function cmpBestAlign(a, b) {
  const fwd = cmpAlign(a, b);
  const mFwd = cmpMismatchCount(fwd);
  const rc = cmpAlign(a, cmpRevComp(b));
  const mRc = cmpMismatchCount(rc);
  return mRc < mFwd ? { ...rc, revcomp: true, mism: mRc } : { ...fwd, revcomp: false, mism: mFwd };
}

function buildDnaDiff(dnaSeq, gbSeq) {
  const details = document.createElement('details');
  details.className = 'dnacmp-diff';
  const summary = document.createElement('summary');
  summary.innerHTML = '🔍 Ver dónde están las diferencias <span class="dnacmp-diff-hint">(alineamiento tipo Clustal)</span>';
  details.appendChild(summary);
  const body = mk('div', 'dnacmp-diff-body');
  details.appendChild(body);
  let built = false;
  details.addEventListener('toggle', () => {
    if (details.open && !built) { built = true; body.appendChild(renderDnaAlignment(dnaSeq, gbSeq)); }
  });
  return details;
}

function renderDnaAlignment(a, b) {
  const wrap = mk('div', 'dnacmp-aln');
  const { aa, bb, revcomp, mism } = cmpBestAlign(a, b);
  const total = aa.length;
  const COLS = 60;
  const CAP = 60000;                // don't render absurdly long alignments
  const shown = Math.min(total, CAP);
  const coordW = String(Math.max(a.length, b.length)).length;

  const note = mk('div', 'dnacmp-aln-note');
  note.innerHTML =
    `Diferencias resaltadas en <span class="dnacmp-nt-diff">rojo</span>. ` +
    `«−» = hueco (inserción/deleción). ` +
    (revcomp ? 'El <code>.gb</code> se muestra como <strong>hebra complementaria inversa</strong> (así alinea mejor). ' : '') +
    `<strong>${cmpFmt(mism)}</strong> posición(es) con diferencias sobre ${cmpFmt(total)}.`;
  wrap.appendChild(note);

  const scroll = mk('div', 'dnacmp-aln-scroll');
  let posA = 0, posB = 0;
  for (let start = 0; start < shown; start += COLS) {
    const end = Math.min(start + COLS, shown);
    const segA = aa.slice(start, end), segB = bb.slice(start, end);
    const aStart = posA + 1, bStart = posB + 1;
    let rowA = '', rowB = '', mark = '';
    for (let i = 0; i < segA.length; i++) {
      const ca = segA[i], cb = segB[i];
      const diff = ca !== cb;
      rowA += diff ? `<span class="dnacmp-nt-diff">${ca}</span>` : ca;
      rowB += diff ? `<span class="dnacmp-nt-diff">${cb}</span>` : cb;
      mark += diff ? '^' : ' ';
      if (ca !== '-') posA++;
      if (cb !== '-') posB++;
    }
    const gut = (label, coord) => `<span class="dnacmp-aln-gut">${label.padEnd(5)}${String(coord).padStart(coordW)}</span> `;
    const block = mk('div', 'dnacmp-aln-block');
    block.innerHTML =
      `<div class="dnacmp-aln-row">${gut('.dna', aStart)}${rowA} <span class="dnacmp-aln-end">${posA}</span></div>` +
      `<div class="dnacmp-aln-row dnacmp-aln-mark">${gut('', '')}${mark}</div>` +
      `<div class="dnacmp-aln-row">${gut('.gb', bStart)}${rowB} <span class="dnacmp-aln-end">${posB}</span></div>`;
    scroll.appendChild(block);
  }
  wrap.appendChild(scroll);

  if (total > CAP) {
    wrap.appendChild(mk('div', 'dnacmp-aln-note', `… alineamiento recortado a ${cmpFmt(CAP)} columnas de ${cmpFmt(total)}.`));
  }
  return wrap;
}

// ════════════════════════════════════════════════════════════════════════════
// Preguntar a un PDF (IA) — RAG sobre un PDF grande
// ════════════════════════════════════════════════════════════════════════════
let pdfqaPollTimer = null;

function pdfqaEsc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Light markdown → HTML for the AI answer (bold, bullet lists, paragraphs).
function pdfqaFormatAnswer(text) {
  return String(text || '').split(/\n{2,}/).map(block => {
    const lines = block.split('\n');
    if (lines.length && lines.every(l => /^\s*[-*•]\s+/.test(l))) {
      return '<ul style="margin:6px 0 6px 18px;padding:0;">' +
        lines.map(l => '<li>' + pdfqaEsc(l.replace(/^\s*[-*•]\s+/, '')).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') + '</li>').join('') +
        '</ul>';
    }
    return '<p style="margin:0 0 10px;">' +
      lines.map(l => pdfqaEsc(l)).join('<br>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') +
      '</p>';
  }).join('');
}

function pdfqaPageRef(s, e) {
  return s === e ? `pág. ${s}` : `págs. ${s}–${e}`;
}

// Friendly label for an embedding model (so the user can see what each doc used).
function pdfqaModelLabel(m) {
  if (!m) return '';
  return /^voyage/i.test(m) ? `Voyage · ${m}` : `OpenAI · ${m}`;
}

// Render source page ranges as chips. When the original PDF is available, each
// chip is a BUTTON that opens an in-app viewer showing that page of the PDF.
function pdfqaSourceChips(sources, docId, hasPdf, docName) {
  const base = 'padding:2px 10px;margin:2px 4px 2px 0;border-radius:12px;background:#eef5fc;border:1px solid #cfe1f5;color:#1B6CB0;font-size:12px;';
  return (sources || []).map(s => {
    const label = pdfqaPageRef(s.pageStart, s.pageEnd);
    if (hasPdf && docId != null) {
      return `<button type="button" class="pdfqa-page-btn" data-doc="${docId}" data-page="${s.pageStart}" data-name="${pdfqaEsc(docName || '')}" ` +
        `title="Ver la página ${s.pageStart} del PDF" style="${base}cursor:pointer;font-family:inherit;">${label} 🔍</button>`;
    }
    return `<span style="display:inline-block;${base}">${label}</span>`;
  }).join('');
}

// ── In-app PDF page viewer (modal with the browser's native PDF viewer) ─────────
function pdfqaViewer() {
  let el = document.getElementById('pdfqa-viewer');
  if (el) return el;
  el = mk('div');
  el.id = 'pdfqa-viewer';
  el.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(15,27,45,.62);display:none;align-items:center;justify-content:center;padding:2vh 2vw;';
  el.innerHTML =
    '<div style="background:#fff;border-radius:12px;width:min(1000px,96vw);height:95vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,.35);">' +
      '<div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid #e2e2e2;background:#fafafa;">' +
        '<strong id="pdfqa-viewer-title" style="flex:1;font-size:14px;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">Página</strong>' +
        '<a id="pdfqa-viewer-tab" target="_blank" rel="noopener" class="bw-btn" style="font-size:12px;text-decoration:none;">Pestaña ↗</a>' +
        '<button id="pdfqa-viewer-close" class="bw-btn bw-btn-cancel" type="button" style="font-size:12px;">Cerrar ✕</button>' +
      '</div>' +
      '<iframe id="pdfqa-viewer-frame" title="Página del PDF" style="flex:1;width:100%;border:0;background:#525659;"></iframe>' +
    '</div>';
  document.body.appendChild(el);
  const hide = () => { el.style.display = 'none'; const f = el.querySelector('#pdfqa-viewer-frame'); if (f) f.src = 'about:blank'; };
  el.addEventListener('click', e => { if (e.target === el) hide(); });
  el.querySelector('#pdfqa-viewer-close').addEventListener('click', hide);
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && el.style.display !== 'none') hide(); });
  el._hide = hide;
  return el;
}

function pdfqaViewPage(docId, page, name) {
  const el = pdfqaViewer();
  const url = `/batchwork/api/pdfqa/docs/${docId}/pdf#page=${page}`;
  el.querySelector('#pdfqa-viewer-frame').src = url;
  el.querySelector('#pdfqa-viewer-tab').href = url;
  el.querySelector('#pdfqa-viewer-title').textContent = (name ? name + ' · ' : '') + 'página ' + page;
  el.style.display = 'flex';
}

// One delegated handler for every page button (they're injected via innerHTML).
if (!window.__pdfqaPageDelegated) {
  window.__pdfqaPageDelegated = true;
  document.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('.pdfqa-page-btn');
    if (!b) return;
    e.preventDefault();
    pdfqaViewPage(b.dataset.doc, b.dataset.page, b.dataset.name);
  });
}

async function pdfqaApi(path, opts) {
  const r = await fetch('/batchwork/api/pdfqa' + path, opts);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json().catch(() => ({})) : {};
  if (!r.ok) throw new Error(data.error || `Error ${r.status}`);
  return data;
}

function renderPdfQaUI(zone) {
  if (pdfqaPollTimer) { clearTimeout(pdfqaPollTimer); pdfqaPollTimer = null; }

  const ui = { docs: [], selectedId: null, meta: null, pendingFile: null, busy: false, qa: [], qaFilter: '' };
  const cardCss = 'margin:0 0 16px;padding:16px 18px;border:1px solid #e2e2e2;border-radius:12px;background:#fbfbfb;';

  const root = mk('div', 'bw-params');

  // ── Intro ─────────────────────────────────────────────────────────────────
  const intro = mk('div', 'dnacmp-intro');
  intro.innerHTML = `
    <h3>¿Qué hace y por qué?</h3>
    <p>Sube un PDF —aunque tenga <strong>miles de páginas</strong>— y «digiérelo» una sola vez. Se extrae el
       texto de cada página, se trocea en fragmentos y se <strong>indexa con IA</strong> (embeddings). A partir
       de ahí puedes <strong>preguntar en lenguaje natural</strong> y la IA responde apoyándose solo en el
       documento y <strong>citando las páginas exactas</strong>.</p>
    <ol>
      <li><strong>Digerir:</strong> suelta el PDF y pulsa «Digerir». Tarda un poco (extracción + indexado); verás el progreso.</li>
      <li><strong>Guardado:</strong> los documentos digeridos quedan almacenados; no hay que volver a subirlos.</li>
      <li><strong>Preguntar:</strong> elige un documento, escribe tu pregunta y obtén la respuesta con sus páginas de referencia.</li>
    </ol>
    <p style="font-size:12px;color:#777;margin-top:6px;">Requiere texto real en el PDF (no escaneado / sin OCR). Un documento escaneado no tendría texto que extraer.</p>`;
  root.appendChild(intro);

  const warnBox = mk('div');
  warnBox.style.cssText = 'display:none;margin:0 0 14px;padding:10px 12px;border-radius:8px;background:#fff4e5;border:1px solid #f0c27a;color:#8a5a00;font-size:13px;';
  root.appendChild(warnBox);

  // ── 1 · Digerir ─────────────────────────────────────────────────────────────
  const digestCard = mk('div'); digestCard.style.cssText = cardCss;
  digestCard.appendChild(mk('h3', null, '1 · Digerir un PDF nuevo'));
  const drop = makeDropZone({
    label: 'Suelta aquí un PDF', sub: 'texto real, no escaneado · uno cada vez',
    accept: '.pdf', multiple: false, onFiles: onPick,
  });
  digestCard.appendChild(drop);
  const digestRow = mk('div'); digestRow.style.cssText = 'display:flex;gap:10px;align-items:center;margin-top:10px;flex-wrap:wrap;';
  const btnDigest = mk('button', 'bw-btn bw-btn-primary', 'Digerir'); btnDigest.type = 'button'; btnDigest.disabled = true;
  const pickInfo = mk('span'); pickInfo.style.cssText = 'font-size:13px;color:#555;';
  digestRow.appendChild(btnDigest); digestRow.appendChild(pickInfo);
  digestCard.appendChild(digestRow);
  const digestMsg = mk('div'); digestMsg.style.cssText = 'margin-top:8px;font-size:13px;';
  digestCard.appendChild(digestMsg);
  root.appendChild(digestCard);

  // ── 2 · Documentos ──────────────────────────────────────────────────────────
  const listCard = mk('div'); listCard.style.cssText = cardCss;
  listCard.appendChild(mk('h3', null, '2 · Mis documentos digeridos'));
  const listWrap = mk('div');
  listCard.appendChild(listWrap);
  root.appendChild(listCard);

  // ── 3 · Preguntar ─────────────────────────────────────────────────────────────
  const askCard = mk('div'); askCard.style.cssText = cardCss;
  askCard.appendChild(mk('h3', null, '3 · Preguntar'));
  const askDocLabel = mk('div'); askDocLabel.style.cssText = 'font-size:13px;color:#555;margin-bottom:8px;';
  askCard.appendChild(askDocLabel);
  const ta = document.createElement('textarea');
  ta.className = 'bw-input bw-textarea'; ta.rows = 3;
  ta.placeholder = 'Escribe tu pregunta sobre el documento seleccionado…';
  askCard.appendChild(ta);
  const askRow = mk('div'); askRow.style.cssText = 'display:flex;gap:10px;margin-top:8px;align-items:center;';
  const btnAsk = mk('button', 'bw-btn bw-btn-primary', 'Preguntar'); btnAsk.type = 'button';
  askRow.appendChild(btnAsk);
  askCard.appendChild(askRow);
  const answerBox = mk('div'); answerBox.style.cssText = 'margin-top:14px;';
  askCard.appendChild(answerBox);
  root.appendChild(askCard);

  // ── 4 · Repositorio compartido de preguntas y respuestas ──────────────────────
  const qaCard = mk('div'); qaCard.style.cssText = cardCss;
  const qaHead = mk('div'); qaHead.style.cssText = 'display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;';
  qaHead.appendChild(mk('h3', null, '4 · Preguntas y respuestas guardadas'));
  const qaShared = mk('span', null, '· compartido con todos los usuarios');
  qaShared.style.cssText = 'font-size:12px;color:#888;';
  qaHead.appendChild(qaShared);
  qaCard.appendChild(qaHead);
  const qaSearch = document.createElement('input');
  qaSearch.className = 'bw-input'; qaSearch.type = 'search';
  qaSearch.placeholder = 'Buscar en preguntas, respuestas o documentos…';
  qaSearch.style.cssText = 'margin:10px 0;width:100%;';
  qaCard.appendChild(qaSearch);
  const qaWrap = mk('div');
  qaCard.appendChild(qaWrap);
  root.appendChild(qaCard);

  zone.appendChild(root);

  // ── Behaviour ───────────────────────────────────────────────────────────────
  function onPick(files) {
    const f = files && files[0];
    if (!f) return;
    if (!/\.pdf$/i.test(f.name)) { digestMsg.style.color = '#B83232'; digestMsg.textContent = 'Solo se admiten ficheros PDF.'; return; }
    ui.pendingFile = f;
    pickInfo.textContent = `${f.name} · ${fmtSize(f.size)}`;
    btnDigest.disabled = false;
    digestMsg.textContent = '';
  }

  btnDigest.addEventListener('click', async () => {
    if (!ui.pendingFile || ui.busy) return;
    ui.busy = true; btnDigest.disabled = true;
    digestMsg.style.color = '#555';
    digestMsg.textContent = `Subiendo «${ui.pendingFile.name}»…`;
    try {
      const fd = new FormData();
      fd.append('file', ui.pendingFile, ui.pendingFile.name);
      const { doc } = await pdfqaApi('/digest', { method: 'POST', body: fd });
      digestMsg.style.color = '#1a7f37';
      digestMsg.textContent = 'Recibido. Procesando en segundo plano (extracción + indexado)…';
      ui.pendingFile = null; pickInfo.textContent = '';
      const t = drop.querySelector('.bw-drop-text'); if (t) t.textContent = 'Suelta aquí un PDF';
      ui.selectedId = doc.id;
      await refreshDocs();
      schedulePoll();
    } catch (err) {
      digestMsg.style.color = '#B83232';
      digestMsg.textContent = err.message;
    } finally {
      ui.busy = false;
      btnDigest.disabled = !ui.pendingFile;
    }
  });

  async function refreshDocs() {
    try {
      const { items } = await pdfqaApi('/docs');
      ui.docs = items || [];
    } catch { /* keep previous */ }
    // Default selection: keep current if still present & ready, else first ready.
    const ready = ui.docs.filter(d => d.status === 'ready');
    if (!ui.docs.some(d => d.id === ui.selectedId)) ui.selectedId = null;
    if (ui.selectedId == null && ready.length) ui.selectedId = ready[0].id;
    renderDocs();
    renderAskLabel();
  }

  function renderDocs() {
    listWrap.innerHTML = '';
    if (!ui.docs.length) {
      listWrap.appendChild(mk('div', null, 'Todavía no has digerido ningún documento.'));
      listWrap.lastChild.style.cssText = 'color:#888;font-size:13px;';
      return;
    }
    for (const d of ui.docs) {
      const row = mk('div');
      const selectable = d.status === 'ready';
      const isSel = d.id === ui.selectedId && selectable;
      row.style.cssText = 'display:flex;align-items:flex-start;gap:10px;padding:10px 12px;margin-bottom:8px;border-radius:10px;border:1px solid ' +
        (isSel ? '#1B6CB0' : '#e2e2e2') + ';background:' + (isSel ? '#eef5fc' : '#fff') + ';';

      const main = mk('div'); main.style.cssText = 'flex:1;min-width:0;cursor:' + (selectable ? 'pointer' : 'default') + ';';
      let metaLine = '';
      if (d.status === 'ready') {
        metaLine = `${d.pages} págs · ${d.chunks} fragmentos · ${fmtSize(d.bytes)}`;
      } else if (d.status === 'error') {
        metaLine = `<span style="color:#B83232;">⚠ ${pdfqaEsc(d.error || 'Error al procesar')}</span>`;
      } else {
        metaLine = pdfqaProgressText(d.progress);
      }
      const modelLine = (d.status === 'ready' && d.model)
        ? `<div style="font-size:11.5px;color:#888;margin-top:2px;">🧠 Indexado con <strong>${pdfqaEsc(pdfqaModelLabel(d.model))}</strong></div>`
        : '';
      main.innerHTML =
        `<div style="font-weight:600;color:#111;word-break:break-word;">${isSel ? '✓ ' : ''}${pdfqaEsc(d.name)}</div>` +
        modelLine +
        `<div style="font-size:12.5px;color:#555;margin-top:2px;">${metaLine}</div>`;
      if (d.status === 'processing') main.appendChild(pdfqaProgressBar(d.progress));
      if (d.warning && d.status === 'ready') {
        const w = mk('div', null, '⚠ ' + pdfqaEsc(d.warning));
        w.style.cssText = 'font-size:12px;color:#8a5a00;margin-top:4px;';
        main.appendChild(w);
      }
      if (selectable) main.addEventListener('click', () => { ui.selectedId = d.id; renderDocs(); renderAskLabel(); });
      row.appendChild(main);

      const del = mk('button', 'bw-btn bw-btn-cancel', '🗑'); del.type = 'button';
      del.title = 'Eliminar documento'; del.style.cssText = 'flex:0 0 auto;';
      del.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!confirm(`¿Eliminar «${d.name}» y su índice? Esta acción no se puede deshacer.`)) return;
        try { await pdfqaApi('/docs/' + d.id, { method: 'DELETE' }); } catch (err) { alert(err.message); return; }
        if (ui.selectedId === d.id) ui.selectedId = null;
        await refreshDocs();
      });
      row.appendChild(del);
      listWrap.appendChild(row);
    }
  }

  function pdfqaProgressText(p) {
    if (!p) return 'En cola…';
    if (p.phase === 'extracting') return p.total ? `Extrayendo texto (${p.current}/${p.total} págs)` : 'Extrayendo texto…';
    if (p.phase === 'embedding') return p.total ? `Indexando fragmentos (${p.current}/${p.total})` : 'Indexando…';
    return p.message || 'Procesando…';
  }

  function pdfqaProgressBar(p) {
    const wrap = mk('div'); wrap.style.cssText = 'height:6px;border-radius:4px;background:#e6e6e6;overflow:hidden;margin-top:6px;';
    const bar = mk('div');
    const pct = p && p.total ? Math.max(4, Math.min(100, Math.round(p.current / p.total * 100))) : 12;
    bar.style.cssText = `height:100%;width:${pct}%;background:#1B6CB0;transition:width .3s;`;
    wrap.appendChild(bar);
    return wrap;
  }

  function schedulePoll() {
    if (pdfqaPollTimer) { clearTimeout(pdfqaPollTimer); pdfqaPollTimer = null; }
    const anyProcessing = ui.docs.some(d => d.status === 'processing');
    if (!anyProcessing) return;
    pdfqaPollTimer = setTimeout(async () => {
      // Stop if the user navigated away (this UI was replaced).
      if (!document.body.contains(zone)) { pdfqaPollTimer = null; return; }
      await refreshDocs();
      schedulePoll();
    }, 1600);
  }

  function renderAskLabel() {
    const d = ui.docs.find(x => x.id === ui.selectedId && x.status === 'ready');
    if (d) {
      askDocLabel.innerHTML = `Documento: <strong>${pdfqaEsc(d.name)}</strong> <span style="color:#888;">(${d.pages} págs)</span>`;
    } else {
      askDocLabel.innerHTML = '<span style="color:#888;">Selecciona arriba un documento ya digerido para preguntar.</span>';
    }
  }

  async function ask() {
    const d = ui.docs.find(x => x.id === ui.selectedId && x.status === 'ready');
    if (!d) { answerBox.innerHTML = '<div style="color:#B83232;font-size:13px;">Selecciona un documento digerido.</div>'; return; }
    const q = ta.value.trim();
    if (!q) { ta.focus(); return; }
    if (ui.busy) return;
    ui.busy = true; btnAsk.disabled = true;
    answerBox.innerHTML = '<div style="color:#555;font-size:13px;">Buscando en el documento y redactando la respuesta…</div>';
    try {
      const { answer, sources } = await pdfqaApi('/ask', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ docId: d.id, question: q }),
      });
      const src = pdfqaSourceChips(sources, d.id, d.hasPdf, d.name);
      answerBox.innerHTML =
        `<div style="background:#fff;border:1px solid #e2e2e2;border-radius:10px;padding:14px 16px;font-size:14px;line-height:1.55;color:#1a1a1a;">${pdfqaFormatAnswer(answer)}</div>` +
        (src ? `<div style="margin-top:10px;font-size:12px;color:#666;">Páginas consultadas: ${src}</div>` : '') +
        '<div style="margin-top:8px;font-size:12px;color:#1a7f37;">✓ Guardado en el repositorio compartido (sección 4).</div>';
      ta.value = '';
      await refreshQA();  // surface the new entry at the top of the shared repo
    } catch (err) {
      answerBox.innerHTML = `<div style="color:#B83232;font-size:13px;">${pdfqaEsc(err.message)}</div>`;
    } finally {
      ui.busy = false; btnAsk.disabled = false;
    }
  }
  btnAsk.addEventListener('click', ask);
  ta.addEventListener('keydown', (e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') ask(); });

  // ── Shared Q&A repository ─────────────────────────────────────────────────────
  qaSearch.addEventListener('input', () => { ui.qaFilter = qaSearch.value.trim().toLowerCase(); renderQA(); });

  async function refreshQA() {
    try { const { items } = await pdfqaApi('/qa'); ui.qa = items || []; } catch { /* keep previous */ }
    renderQA();
  }

  function pdfqaWhen(s) {
    // SQLite CURRENT_TIMESTAMP is UTC "YYYY-MM-DD HH:MM:SS"; show a friendly local date.
    if (!s) return '';
    const d = new Date(s.replace(' ', 'T') + 'Z');
    if (isNaN(d)) return s;
    return d.toLocaleString('es-ES', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  function renderQA() {
    qaWrap.innerHTML = '';
    const f = ui.qaFilter;
    const items = !f ? ui.qa : ui.qa.filter(it =>
      (it.question || '').toLowerCase().includes(f) ||
      (it.answer || '').toLowerCase().includes(f) ||
      (it.docName || '').toLowerCase().includes(f) ||
      (it.userEmail || '').toLowerCase().includes(f));

    if (!ui.qa.length) {
      const e = mk('div', null, 'Todavía no hay preguntas guardadas. Las que hagáis en la sección 3 aparecerán aquí para todos.');
      e.style.cssText = 'color:#888;font-size:13px;'; qaWrap.appendChild(e); return;
    }
    const count = mk('div', null, `${items.length} de ${ui.qa.length} pregunta(s)`);
    count.style.cssText = 'font-size:12px;color:#888;margin-bottom:8px;'; qaWrap.appendChild(count);
    if (!items.length) return;

    for (const it of items) {
      const box = mk('div');
      box.style.cssText = 'border:1px solid #e2e2e2;border-radius:10px;background:#fff;margin-bottom:10px;overflow:hidden;';

      const det = document.createElement('details');
      const sum = document.createElement('summary');
      sum.style.cssText = 'cursor:pointer;padding:12px 14px;list-style:none;';
      const who = it.userEmail ? pdfqaEsc(it.userEmail.split('@')[0]) : 'anónimo';
      sum.innerHTML =
        `<div style="font-weight:600;color:#111;">${pdfqaEsc(it.question)}</div>` +
        `<div style="font-size:12px;color:#777;margin-top:3px;">📄 ${pdfqaEsc(it.docName || '—')} · 👤 ${who} · 🕒 ${pdfqaWhen(it.created_at)}</div>`;
      det.appendChild(sum);

      const body = mk('div');
      body.style.cssText = 'padding:0 14px 14px;';
      const src = pdfqaSourceChips(it.sources, it.docId, it.hasPdf, it.docName);
      body.innerHTML =
        `<div style="border-top:1px solid #eee;padding-top:10px;font-size:14px;line-height:1.55;color:#1a1a1a;">${pdfqaFormatAnswer(it.answer)}</div>` +
        (src ? `<div style="margin-top:8px;font-size:12px;color:#666;">Páginas: ${src}</div>` : '');
      const del = mk('button', 'bw-btn bw-btn-cancel', 'Eliminar');
      del.type = 'button'; del.style.cssText = 'margin-top:10px;font-size:12px;padding:4px 10px;';
      del.addEventListener('click', async () => {
        if (!confirm('¿Eliminar esta pregunta del repositorio compartido? La verán (o dejarán de ver) todos los usuarios.')) return;
        try { await pdfqaApi('/qa/' + it.id, { method: 'DELETE' }); } catch (err) { alert(err.message); return; }
        await refreshQA();
      });
      body.appendChild(del);
      det.appendChild(body);
      box.appendChild(det);
      qaWrap.appendChild(box);
    }
  }

  // ── Boot ────────────────────────────────────────────────────────────────────
  (async () => {
    try {
      ui.meta = await pdfqaApi('/meta');
      const missing = [];
      if (!ui.meta.embedReady) missing.push('OPENAI_API_KEY o VOYAGE_API_KEY (indexado)');
      if (!ui.meta.anthropic) missing.push('ANTHROPIC_API_KEY (respuestas)');
      if (missing.length) {
        warnBox.style.display = '';
        warnBox.innerHTML = '⚠ Faltan claves de IA en el servidor: <strong>' + missing.join('</strong>, <strong>') +
          '</strong>. Configúralas en Railway para poder ' + (!ui.meta.embedReady ? 'digerir' : 'preguntar') + '.';
      } else if (ui.meta.embedModel) {
        // Small info note: which embedding model new digests use + rerank status.
        const rr = ui.meta.rerank ? ' · reranker activo' : '';
        const info = mk('div', null, `Indexado con <strong>${pdfqaEsc(ui.meta.embedModel)}</strong> (${pdfqaEsc(ui.meta.embedProvider)})${rr}. Búsqueda híbrida (semántica + palabras clave).`);
        info.style.cssText = 'font-size:12px;color:#777;margin:-6px 0 12px;';
        warnBox.insertAdjacentElement('afterend', info);
      }
    } catch { /* meta optional */ }
    await refreshDocs();
    await refreshQA();
    schedulePoll();
  })();
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadConfig();      // fetch server upload limit (async; defaults apply meanwhile)
renderSidebar();
