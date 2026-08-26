// ─── App registry ───────────────────────────────────────────────────────────────
// Single source of truth for the apps that live in the hub. Both the landing
// page and the admin panel render from this list, and access control keys off
// the `id`. To add a new app: register its router in server.js, gate it with
// requireApp('<id>'), and add an entry here.
const APPS = [
  {
    id: 're-memory',
    name: 'Re-memory',
    path: '/re-memory',
    desc: 'Sistema de aprendizaje espaciado con recordatorios por email. Organiza y refuerza tu conocimiento de forma progresiva.',
    tags: ['Spaced Repetition', 'Email', 'SQLite'],
    icon: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="card-icon" aria-hidden="true">
      <path d="M32 12C22 12 14 19 14 28c0 4 1.5 7.5 4 10.2V44h28v-5.8c2.5-2.7 4-6.2 4-10.2C50 19 42 12 32 12z" stroke="#1B6CB0" stroke-width="2" fill="none"/>
      <path d="M24 28c0-2.2 1.8-4 4-4" stroke="#009B8D" stroke-width="2" stroke-linecap="round"/>
      <path d="M32 24c2.2 0 4 1.8 4 4" stroke="#009B8D" stroke-width="2" stroke-linecap="round"/>
      <path d="M32 32c0 0 4-4 4-8" stroke="#00B8D4" stroke-width="1.5" stroke-linecap="round" opacity="0.7"/>
      <circle cx="32" cy="50" r="8" stroke="#1B6CB0" stroke-width="2" fill="none"/>
      <path d="M32 46v4l3 2" stroke="#00B8D4" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`,
  },
  {
    id: 'shmir-design',
    name: 'shmiR Design',
    path: '/shmir',
    desc: 'Diseñador de shmiRs sobre un 3\u2032UTR: trocea en ventanas de 22 nt, aplica los filtros biofísicos y de poliadenilación, cruza colisión de seed, carga de off-targets, repetitivos y especificidad, y emite el panel de candidatos con su informe en docx y pdf. Cada frente sin cerrar sale como NOT_RUN y dice qué fichero falta y de dónde se saca.',
    tags: ['ARNi', 'shmiR', 'Streamlit'],
    icon: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="card-icon" aria-hidden="true">
      <path d="M22 10c0 10 20 12 20 22s-20 12-20 22" stroke="#1B6CB0" stroke-width="2" fill="none" stroke-linecap="round"/>
      <path d="M42 10c0 10-20 12-20 22s20 12 20 22" stroke="#009B8D" stroke-width="2" fill="none" stroke-linecap="round"/>
      <path d="M25 18h14M23 26h18M23 38h18M25 46h14" stroke="#00B8D4" stroke-width="1.5" stroke-linecap="round" opacity="0.6"/>
    </svg>`,
  },
  {
    id: 'batchwork',
    name: 'Batchwork',
    path: '/batchwork',
    desc: 'Operaciones por lotes sobre ficheros. Inventario, renombrado, conversión de documentos, manipulación de PDFs e imágenes.',
    tags: ['Lotes', 'PDF', 'Imágenes'],
    icon: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="card-icon" aria-hidden="true">
      <rect x="10" y="38" width="36" height="9" rx="2" stroke="#0097B2" stroke-width="2" fill="none" opacity="0.5"/>
      <rect x="13" y="28" width="36" height="9" rx="2" stroke="#0097B2" stroke-width="2" fill="none" opacity="0.7"/>
      <rect x="16" y="18" width="36" height="9" rx="2" stroke="#0097B2" stroke-width="2" fill="none"/>
    </svg>`,
  },
  {
    id: 'imprimir',
    name: 'Imprimir',
    path: '/imprimir/status',
    desc: 'Cola de impresión por email: envía un PDF, imagen o documento a la dirección de impresión y sale en la impresora. Panel de estado y diagnóstico.',
    tags: ['Email', 'Impresión', 'Diagnóstico'],
    icon: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="card-icon" aria-hidden="true">
      <path d="M20 26V12h24v14" stroke="#1B6CB0" stroke-width="2" fill="none" stroke-linejoin="round"/>
      <rect x="12" y="26" width="40" height="20" rx="2" stroke="#0097B2" stroke-width="2" fill="none"/>
      <path d="M20 40h24v12H20z" stroke="#009B8D" stroke-width="2" fill="none" stroke-linejoin="round"/>
      <circle cx="45" cy="33" r="2" fill="#00B8D4"/>
    </svg>`,
  },
  {
    id: 'bitacora',
    name: 'Bitácora',
    path: '/bitacora',
    desc: 'Registro personal de hechos y circunstancias para revisar con perspectiva a lo largo del tiempo. Formulario sencillo y búsqueda potente.',
    tags: ['Registro', 'Personal', 'SQLite'],
    icon: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="card-icon" aria-hidden="true">
      <path d="M18 10h20l10 10v32a2 2 0 0 1-2 2H18a2 2 0 0 1-2-2V12a2 2 0 0 1 2-2z" stroke="#1F9D62" stroke-width="2" fill="none"/>
      <path d="M38 10v10h10" stroke="#1F9D62" stroke-width="2" fill="none" stroke-linejoin="round"/>
      <path d="M24 32h16M24 39h16M24 46h10" stroke="#27AE60" stroke-width="2" stroke-linecap="round"/>
    </svg>`,
  },
  {
    id: 'qr-tis',
    group: 'farmacia',
    name: 'Gestión de QR (TIS)',
    path: '/qr-tis',
    desc: 'Base de datos de personas y su código TIS con generación de códigos QR escaneables. Introducir, visualizar y utilizar el QR del TIS para la gestión de la medicación.',
    tags: ['QR', 'TIS', 'SQLite'],
    icon: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="card-icon" aria-hidden="true">
      <rect x="12" y="12" width="16" height="16" rx="2" stroke="#1B6CB0" stroke-width="2"/>
      <rect x="17" y="17" width="6" height="6" rx="1" fill="#0097B2"/>
      <rect x="36" y="12" width="16" height="16" rx="2" stroke="#1B6CB0" stroke-width="2"/>
      <rect x="41" y="17" width="6" height="6" rx="1" fill="#0097B2"/>
      <rect x="12" y="36" width="16" height="16" rx="2" stroke="#1B6CB0" stroke-width="2"/>
      <rect x="17" y="41" width="6" height="6" rx="1" fill="#0097B2"/>
      <path d="M36 36h5v5M52 36v5h-5M36 52h5M47 47v5h5" stroke="#00B8D4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`,
  },
  {
    id: 'datamatrix',
    group: 'farmacia',
    name: 'Gestor de códigos Data Matrix',
    path: '/datamatrix',
    desc: 'Inventario de cajas de medicación por sus códigos Data Matrix (GS1). Escanea para dar entrada, marca como utilizada la salida, agrupa por medicamento y genera Data Matrix escaneables.',
    tags: ['Data Matrix', 'GS1', 'Inventario'],
    icon: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="card-icon" aria-hidden="true">
      <path d="M14 14v36M14 50h36" stroke="#1B6CB0" stroke-width="3" stroke-linecap="round"/>
      <rect x="20" y="16" width="6" height="6" fill="#0097B2"/>
      <rect x="32" y="16" width="6" height="6" fill="#00B8D4"/>
      <rect x="44" y="16" width="6" height="6" fill="#0097B2"/>
      <rect x="20" y="28" width="6" height="6" fill="#00B8D4"/>
      <rect x="44" y="28" width="6" height="6" fill="#00B8D4"/>
      <rect x="32" y="40" width="6" height="6" fill="#0097B2"/>
      <rect x="44" y="40" width="6" height="6" fill="#00B8D4"/>
      <path d="M50 14h2M14 12v2" stroke="#1B6CB0" stroke-width="3" stroke-linecap="round"/>
    </svg>`,
  },
  {
    id: 'asignacion',
    group: 'farmacia',
    name: 'Asignación de medicación',
    path: '/asignacion',
    desc: 'Une personas (QR·TIS) y cajas (Data Matrix): prepara el plan mensual de cada persona, pre-asigna cajas reales y márcalas como asignadas al dispensarlas en la aplicación de Salud.',
    tags: ['Asignación', 'TIS', 'Data Matrix'],
    icon: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="card-icon" aria-hidden="true">
      <circle cx="24" cy="22" r="8" stroke="#1B6CB0" stroke-width="2"/>
      <path d="M12 50c0-8 5-13 12-13s12 5 12 13" stroke="#009B8D" stroke-width="2" stroke-linecap="round"/>
      <rect x="40" y="30" width="16" height="16" rx="3" stroke="#0097B2" stroke-width="2"/>
      <path d="M44 38h8M48 34v8" stroke="#00B8D4" stroke-width="2" stroke-linecap="round"/>
    </svg>`,
  },
  {
    id: 'feep',
    name: 'FEEP',
    path: '/feep',
    desc: 'Sección de la Fundación Española de Enfermedades Priónicas. Herramientas propias de la fundación, empezando por los certificados de asistencia.',
    tags: ['Fundación', 'Certificados', 'PDF'],
    icon: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="card-icon" aria-hidden="true">
      <circle cx="32" cy="32" r="21" stroke="#1b2a4a" stroke-width="2"/>
      <circle cx="32" cy="32" r="15" stroke="#b5893c" stroke-width="1.5"/>
      <path d="M25 30h14M25 35h9" stroke="#b5893c" stroke-width="2" stroke-linecap="round"/>
      <path d="M28 44l-1.5 6 5.5-3 5.5 3L36 44" stroke="#1b2a4a" stroke-width="1.6" stroke-linejoin="round"/>
    </svg>`,
  },
];

const APP_IDS = APPS.map(a => a.id);

// ─── Sub-app features (fine-grained access WITHIN an app) ───────────────────────
// Some apps bundle many independent tools. An admin can restrict a user to a
// subset. We model each grant as a scoped id in the user's `apps` CSV, of the
// form "<appId>/<featureId>". Backwards-compatible rule: a user who has the base
// app id but NO scoped ids for it keeps FULL access (so nothing changes for the
// users created before this existed). As soon as one "<appId>/<featureId>" is
// present, access is restricted to the listed features.
const APP_FEATURES = {
  batchwork: [
    { id: 'folder',    name: 'Herramientas de carpetas' },
    { id: 'image',     name: 'Herramientas de imagen' },
    { id: 'document',  name: 'Herramientas de documentos' },
    { id: 'lab',       name: 'Herramientas de laboratorio' },
    { id: 'watermark', name: 'Marca de agua' },
    { id: 'qr',        name: 'QRs' },
    { id: 'stamp',     name: 'Sellos' },
    { id: 'pdfqa',     name: 'Preguntar a un PDF (IA)' },
  ],
};

function featureIds(appId) { return (APP_FEATURES[appId] || []).map(f => f.id); }
function appHasFeatures(appId) { return !!(APP_FEATURES[appId] && APP_FEATURES[appId].length); }
// A valid scoped id is "<knownApp>/<knownFeature>".
function isFeatureId(scoped) {
  const [app, feat] = String(scoped || '').split('/');
  return !!feat && featureIds(app).includes(feat);
}
function userAppList(user) {
  if (!user) return [];
  if (user.apps === '*') return ['*'];
  return Array.isArray(user.apps) ? user.apps : String(user.apps || '').split(',').map(s => s.trim()).filter(Boolean);
}

// Which features of an app a user may use. Returns the full list when the user
// has the app without any scoped ids (legacy/full), or the explicit subset.
function featuresForUser(user, appId) {
  const all = featureIds(appId);
  if (!all.length) return [];
  if (!user) return [];
  if (user.role === 'admin' || user.apps === '*') return all.slice();
  const list = userAppList(user);
  if (!list.includes(appId)) return [];
  const scoped = list.filter(x => x.startsWith(appId + '/')).map(x => x.split('/')[1]).filter(f => all.includes(f));
  return scoped.length ? scoped : all.slice();      // no scopes → full (legacy)
}

function canAccessFeature(user, appId, featureId) {
  if (!appHasFeatures(appId)) return canAccess(user, appId);
  if (!canAccess(user, appId)) return false;
  return featuresForUser(user, appId).includes(featureId);
}

// Apps a given user may access. role 'admin' (or apps '*') → everything.
function appsForUser(user) {
  if (!user) return [];
  if (user.role === 'admin' || user.apps === '*') return APPS.slice();
  const allowed = Array.isArray(user.apps) ? user.apps : String(user.apps || '').split(',').map(s => s.trim());
  const set = new Set(allowed);
  return APPS.filter(a => set.has(a.id));
}

function canAccess(user, appId) {
  if (!user) return false;
  if (user.role === 'admin' || user.apps === '*') return true;
  const allowed = Array.isArray(user.apps) ? user.apps : String(user.apps || '').split(',').map(s => s.trim());
  return allowed.includes(appId);
}

// Public-facing card metadata (no need to ship icons over the API; the hub
// already has them, but it's handy for the admin checkboxes). Each app also
// carries its `features` (empty for apps without fine-grained control).
const appsMeta = () => APPS.map(({ id, name, path, desc, tags, group }) => ({ id, name, path, desc, tags, group: group || null, features: APP_FEATURES[id] || [] }));

// App groups: a set of related apps shown in the main hub as ONE card that leads
// to a mini-hub. Currently just the pharmacy suite.
const GROUPS = {
  farmacia: {
    id: 'farmacia', name: 'Farmacia', path: '/farmacia',
    desc: 'Suite de farmacia: personas y su QR (TIS), inventario de cajas (Data Matrix) y la asignación mensual de medicación. Entra al mini-hub para elegir.',
    tags: ['QR (TIS)', 'Data Matrix', 'Asignación'],
    icon: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="card-icon" aria-hidden="true">
      <rect x="14" y="10" width="36" height="44" rx="6" stroke="#1B6CB0" stroke-width="2"/>
      <path d="M32 22v16M24 30h16" stroke="#009B8D" stroke-width="3" stroke-linecap="round"/>
      <path d="M22 10v6h20v-6" stroke="#0097B2" stroke-width="2"/>
    </svg>`,
  },
};
const GROUP_IDS = Object.keys(GROUPS);
// The groups a user can reach (they have access to ≥1 member app).
function groupsForUser(user) {
  const ids = new Set(appsForUser(user).map(a => a.id));
  return GROUP_IDS
    .filter(g => APPS.some(a => a.group === g && ids.has(a.id)))
    .map(g => GROUPS[g]);
}
// Member apps of a group that the user can access (for the mini-hub).
function groupAppsForUser(user, groupId) { return appsForUser(user).filter(a => a.group === groupId); }

module.exports = {
  APPS, APP_IDS, appsForUser, canAccess, appsMeta,
  APP_FEATURES, featureIds, appHasFeatures, isFeatureId, featuresForUser, canAccessFeature,
  GROUPS, GROUP_IDS, groupsForUser, groupAppsForUser,
};
