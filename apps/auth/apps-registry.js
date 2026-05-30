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
];

const APP_IDS = APPS.map(a => a.id);

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
// already has them, but it's handy for the admin checkboxes).
const appsMeta = () => APPS.map(({ id, name, path, desc, tags }) => ({ id, name, path, desc, tags }));

module.exports = { APPS, APP_IDS, appsForUser, canAccess, appsMeta };
