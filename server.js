require('dotenv').config();
const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const isProd = process.env.NODE_ENV === 'production';

// Behind Railway's TLS-terminating proxy: trust X-Forwarded-* so secure cookies
// and req.ip (used for rate limiting) work correctly.
app.set('trust proxy', 1);

// ─── Ensure /data directories exist ─────────────────────────────────────────
const dbPath = process.env.DB_PATH || '/data/jokin_tools.db';
const dataDir = path.dirname(dbPath);
const uploadsDir = path.join(dataDir, 'uploads');
[dataDir, uploadsDir].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`[server] Created directory: ${dir}`);
  }
});

// Persistence safeguard: in production the SQLite file MUST live on the mounted
// Railway volume (/data). If DB_PATH points elsewhere, every redeploy silently
// starts from an empty DB on ephemeral disk — users would be asked to change
// their password again and again, saved data would vanish, etc. Warn loudly so
// this is obvious in the logs.
if (process.env.NODE_ENV === 'production' && !path.resolve(dbPath).startsWith('/data')) {
  console.warn('[server] ⚠️  DB_PATH no está bajo /data (' + dbPath + '). '
    + 'En Railway la base de datos debe vivir en el volumen montado en /data o se '
    + 'perderá en cada despliegue. Configura DB_PATH=/data/jokin_tools.db y el volumen.');
}

// ─── Security headers (hand-rolled; no helmet dependency) ────────────────────
app.use((req, res, next) => {
  res.set('X-Content-Type-Options', 'nosniff');
  res.set('X-Frame-Options', 'SAMEORIGIN');
  res.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.set('X-XSS-Protection', '0');
  // Permissive CSP: allows the existing inline styles/scripts and Google Fonts
  // the hub uses, while blocking plugins, framing by others, and base-tag
  // hijacking. Tighten script-src once inline scripts are removed.
  res.set('Content-Security-Policy', [
    "default-src 'self'",
    "img-src 'self' data: blob: https:",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "script-src 'self' 'unsafe-inline'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'self'",
  ].join('; '));
  if (isProd) res.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  next();
});

// ─── Middleware ───────────────────────────────────────────────────────────────
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: false, limit: '1mb' }));

// ─── Auth: identify the user on every request ───────────────────────────────────
const authStore = require('./apps/auth/store');
const authRouter = require('./apps/auth/routes');
const { attachUser, csrfGuard, requireAuth, requireApp } = require('./apps/auth/middleware');
app.use(attachUser);
// Reject cross-site state-changing requests (CSRF) before any route runs.
app.use(csrfGuard);

// Serve uploaded files from /data/uploads — per-user. You must be logged in AND
// own the memory that references the image. Emails don't rely on this route;
// they embed images inline (cid:). Unknown files → 404, someone else's → 403.
const reMemoryDb = require('./apps/re-memory/db');
app.use('/uploads', requireAuth, (req, res, next) => {
  const filename = path.basename(decodeURIComponent(req.path));
  const ownerId = reMemoryDb.getImageOwner(filename);
  if (ownerId == null) return res.status(404).json({ error: 'Not found' });
  if (ownerId !== req.user.id) return res.status(403).json({ error: 'No tienes acceso a esta imagen.' });
  next();
}, express.static(uploadsDir));

// Serve shared public assets (favicons, logos)
app.use('/public', express.static(path.join(__dirname, 'public')));

// ─── Hub frontend assets (CSS, etc. — public so the login page can style itself) ─
app.use('/src', express.static(path.join(__dirname, 'src')));

// ─── Auth (login / logout / user management) ────────────────────────────────────
app.use('/auth', authRouter);

// ─── Re-memory micro-app (requires access to 're-memory') ───────────────────────
const reMemoryRouter = require('./apps/re-memory/routes');
app.use('/re-memory', requireApp('re-memory'), reMemoryRouter);

// ─── Batchwork micro-app (requires access to 'batchwork') ───────────────────────
const batchworkRouter = require('./apps/batchwork/server/routes');
app.use('/batchwork', requireApp('batchwork'), batchworkRouter);

// shmir-design: su interfaz es un proceso de Streamlit propio que corre en 127.0.0.1;
// esto lo sirve como una ruta mas del hub, con el mismo login y los mismos permisos.
// El proceso se arranca la PRIMERA vez que alguien entra, no al bootear: tarda segundos,
// ocupa memoria, y la mayoria de quien entra al hub no abre esta app.
const shmirRouter = require('./apps/shmir/routes');
app.use('/shmir', requireApp('shmir-design'), shmirRouter);

// ─── Bitácora micro-app (requires access to 'bitacora') ─────────────────────────
const bitacoraDb = require('./apps/bitacora/db');
const bitacoraRouter = require('./apps/bitacora/routes');
app.use('/bitacora', requireApp('bitacora'), bitacoraRouter);

// ─── Imprimir (email-to-print): agent API, no login — the local print agent ─────
// authenticates with IMPRIMIR_AGENT_KEY. No browser UI. Requiring the module
// creates its DB table.
const imprimirDb = require('./apps/imprimir/db');
const imprimirRouter = require('./apps/imprimir/routes');
app.use('/imprimir', imprimirRouter);

// ─── FEEP · Fundación Española de Enfermedades Priónicas (requires access) ──────
// Self-contained section: its own router + its own SQLite file (apps/feep/db.js →
// feep.db). Nothing here couples to the other apps, so it can be lifted out to the
// foundation's own repository by copying apps/feep/ + feep.db. See MIGRATION.md.
const feepDb = require('./apps/feep/db');
const feepRouter = require('./apps/feep');
app.use('/feep', requireApp('feep'), feepRouter);

// ─── Gestión de QR (TIS) micro-app (requires access to 'qr-tis') ────────────────
// Self-contained: its own router + its own SQLite file (apps/qr-tis/db.js →
// qr_tis.db). People + their TIS code, rendered as scannable QR codes.
const qrTisDb = require('./apps/qr-tis/db');
const qrTisRouter = require('./apps/qr-tis/routes');
app.use('/qr-tis', requireApp('qr-tis'), qrTisRouter);

// ─── Gestor de códigos Data Matrix (requires access to 'datamatrix') ────────────
// Self-contained: its own router + its own SQLite file (apps/datamatrix/db.js →
// datamatrix.db). Medication boxes by their GS1 Data Matrix codes.
const dmDb = require('./apps/datamatrix/db');
const dmRouter = require('./apps/datamatrix/routes');
app.use('/datamatrix', requireApp('datamatrix'), dmRouter);

// ─── Asignación de medicación (requires access to 'asignacion') ─────────────────
// Bridges qr-tis (people) and datamatrix (boxes). Its own SQLite file
// (apps/asignacion/db.js → asignacion.db) holds only the assignment layer; the
// people/boxes stay in their own apps' databases.
const asigDb = require('./apps/asignacion/db');
const asigRouter = require('./apps/asignacion/routes');
app.use('/asignacion', requireApp('asignacion'), asigRouter);

// ─── Pastillero (residencias) ────────────────────────────────────────────────────
// NOT gated at the top level: caregivers have no farmacia account, they log in
// with a shared per-residencia code (their own session, see apps/pastillero/db.js).
// The router gates its own /admin* (farmacia staff, requireApp('pastillero')) and
// its caregiver API (requireResidencia) internally.
const pastilleroRouter = require('./apps/pastillero/routes');
app.use('/pastillero', pastilleroRouter);

// ─── Galénica (catálogo de medicamentos: nombre, forma, color, foto) ────────────
const galenicaRouter = require('./apps/galenica/routes');
app.use('/galenica', requireApp('galenica'), galenicaRouter);

// ─── Hub root (requires login) ──────────────────────────────────────────────────
app.get('/', requireAuth, (req, res) => {
  res.sendFile(path.join(__dirname, 'src', 'index.html'));
});

// Mini-hub for the pharmacy suite (QR·TIS · Data Matrix · Asignación).
app.get('/farmacia', requireAuth, (req, res) => {
  res.sendFile(path.join(__dirname, 'src', 'pharma.html'));
});
// Live counters for the pharmacy hub cards.
app.get('/farmacia/api/counts', requireAuth, (req, res) => {
  try {
    res.json({
      people: qrTisDb.listPeople().length,            // personas en QR (TIS)
      dmActive: dmDb.counts().activo,                 // DM sin utilizar (en stock)
      cnCount: asigDb.distinctCnCount(),              // medicamentos distintos (CN) en Asignación
    });
  } catch { res.json({}); }
});

// Favicon hub principal
app.get('/favicon.ico', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'favicon-jk.svg'), {
    headers: { 'Content-Type': 'image/svg+xml' }
  }, (err) => {
    if (err) res.status(204).end();
  });
});

// ─── 404 handler ─────────────────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// ─── Global error handler ─────────────────────────────────────────────────────
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  // Respect well-formed client errors (e.g. body-parser's 413/400) instead of
  // masking them all as 500.
  const status = err.status || err.statusCode || 500;
  if (status >= 500) console.error('[server] Unhandled error:', err);
  // Don't leak internal 5xx details (SQL, paths, API errors) to clients in
  // production; full detail still goes to the server log above. Client (4xx)
  // messages are safe to surface.
  const expose = status < 500 || !isProd;
  res.status(status).json({
    error: status >= 500 ? 'Internal server error' : (err.message || 'Error'),
    ...(expose && status >= 500 ? { message: err.message } : {}),
  });
});

// ─── Startup migrations ─────────────────────────────────────────────────────
function runStartupMigrations() {
  // Ensure there's a working admin (from ADMIN_EMAIL / ADMIN_PASSWORD).
  authStore.seedAdminFromEnv();

  // Pill images: mirror what's committed in the repo (delivered via GitHub) onto
  // the volume that's actually served — see apps/pastillero/pill-images.js.
  try {
    const r = require('./apps/pastillero/pill-images').syncFromRepo();
    if (r.copied || r.removed) console.log(`[pastillero] Pill images synced: ${r.copied} copiada(s), ${r.removed} eliminada(s) (${r.total} en el repo).`);
  } catch (e) {
    console.error('[pastillero] Pill image sync skipped:', e.message);
  }

  // Seed the team's accounts (idempotent): default password + forced change.
  try {
    require('./apps/auth/seed-users').seedInitialUsers();
  } catch (e) {
    console.error('[auth] initial user seeding skipped:', e.message);
  }

  const ownerEmail = (process.env.REMEMORY_OWNER_EMAIL || process.env.ADMIN_EMAIL || '').trim().toLowerCase();
  const owner = ownerEmail ? authStore.getUserByEmail(ownerEmail) : null;

  // Re-memory: assign any pre-existing (ownerless) memories to a single owner.
  try {
    if (owner) {
      const n = reMemoryDb.assignOrphanMemories(owner.id);
      if (n) console.log(`[re-memory] Assigned ${n} pre-existing memories to ${owner.email}`);
    } else {
      const orphans = reMemoryDb.db.prepare('SELECT COUNT(*) AS n FROM memories WHERE user_id IS NULL').get().n;
      if (orphans) console.warn(`[re-memory] ${orphans} memories have no owner and ADMIN_EMAIL/REMEMORY_OWNER_EMAIL is not set — hidden until assigned.`);
    }
  } catch (e) {
    console.error('[re-memory] Orphan assignment skipped:', e.message);
  }

  // Bitácora: assign any pre-existing (ownerless) entries to the same owner.
  try {
    if (owner) {
      const n = bitacoraDb.assignOrphans(owner.id);
      if (n) console.log(`[bitacora] Assigned ${n} pre-existing entries to ${owner.email}`);
    }
  } catch (e) {
    console.error('[bitacora] Orphan assignment skipped:', e.message);
  }

  // FEEP: seed the foundation's known attendance certificates (idempotent) into
  // the owner's repository so they can be recovered/downloaded/emailed later.
  try {
    const feepOwner = owner || authStore.getUserByEmail('castilla@joaquincastilla.com');
    const feepSeed = require('./apps/feep/seed-certificates');
    feepSeed.seedDefaultAssets(feepOwner);   // logo/firma desde apps/feep/assets/ (si existen)
    feepSeed.seedFeepCertificates(feepOwner);
  } catch (e) {
    console.error('[feep] certificate seeding skipped:', e.message);
  }

  // Batchwork: the .dna library is shared across users. Consolidate any
  // per-user subdirectories (from the earlier per-user split) back into the
  // shared repository.
  try {
    require('./apps/batchwork/server/library').consolidateToShared();
  } catch (e) {
    console.error('[batchwork] Library consolidation skipped:', e.message);
  }
}

// ─── Graceful shutdown ───────────────────────────────────────────────────────
function shutdown(server, signal) {
  console.log(`[server] ${signal} received — shutting down…`);
  try { require('./apps/re-memory/cron').stopCron(); } catch { /* ignore */ }
  try { require('./apps/imprimir/poller').stopPolling(); } catch { /* ignore */ }
  try { require('./apps/asignacion/cron').stopCron(); } catch { /* ignore */ }
  // El proceso de Streamlit es hijo de este: sin esto sobrevive al apagado y se
  // queda con el puerto cogido, asi que el siguiente arranque no puede lanzarlo.
  try { require('./apps/shmir/process').stop(); } catch { /* ignore */ }
  server.close(() => {
    try { authStore.db.close(); } catch { /* ignore */ }
    try { reMemoryDb.db.close(); } catch { /* ignore */ }
    try { bitacoraDb.db.close(); } catch { /* ignore */ }
    try { imprimirDb.db.close(); } catch { /* ignore */ }
    try { qrTisDb.db.close(); } catch { /* ignore */ }
    try { dmDb.db.close(); } catch { /* ignore */ }
    try { asigDb.db.close(); } catch { /* ignore */ }
    console.log('[server] Closed cleanly.');
    process.exit(0);
  });
  // Don't hang forever if a connection won't drain.
  setTimeout(() => process.exit(0), 10000).unref?.();
}

// ─── Start (only when run directly, not when required for tests) ─────────────
if (require.main === module) {
  runStartupMigrations();

  // Start the re-memory cron jobs (daily email + periodic backup).
  try { require('./apps/re-memory/cron').startCron(); }
  catch (e) { console.error('[cron] failed to start:', e.message); }

  // Start the email-to-print poller (no-op unless IMPRIMIR_ENABLED=true).
  try { require('./apps/imprimir/poller').startPolling(); }
  catch (e) { console.error('[imprimir] poller failed to start:', e.message); }

  // Start the Asignación notification scheduler (sends the scheduled digests).
  try { require('./apps/asignacion/cron').startCron(); }
  catch (e) { console.error('[asignacion] cron failed to start:', e.message); }

  const server = app.listen(PORT, () => {
    console.log(`[server] Jokin's Tools running on port ${PORT}`);
    console.log(`[server] DB path: ${process.env.DB_PATH || '/data/jokin_tools.db'}`);
    console.log(`[server] NODE_ENV: ${process.env.NODE_ENV || 'development'}`);
  });

  // ── WebSocket de shmir-design ───────────────────────────────────────────────
  //
  // OJO: el evento `upgrade` NO pasa por los middlewares de Express, asi que el
  // `requireApp('shmir-design')` de arriba protege la pagina y NO protege este socket.
  // Streamlit hace TODO por el (`/_stcore/stream`), asi que sin comprobar aqui la sesion
  // la app quedaria accesible sin login. La comprobacion vive en `upgradeAllowed`, con
  // sus tests.
  const { upgradeAllowed, proxyUpgrade, denySocket } = require('./apps/shmir/proxy');
  const shmirProcess = require('./apps/shmir/process');
  //
  // Y OJO CON LO DE ABAJO SI AÑADES UN WEBSOCKET A OTRA APP: este handler es el UNICO
  // que hay, asi que todo upgrade que no sea de /shmir se cierra aqui. Hoy ninguna otra
  // app usa WebSocket, asi que no estorba a nadie; el dia que una lo use, esto tiene que
  // repartir por prefijo en vez de cerrar. Si no, su socket se cerraria sin motivo y sin
  // dar ningun error — solo «no conecta».
  server.on('upgrade', (req, socket, head) => {
    if (!req.url || !req.url.startsWith('/shmir')) {
      denySocket(socket, 404, 'Este hub solo sirve WebSocket en /shmir. Si acabas de '
        + 'añadir uno a otra app, el handler de `upgrade` de server.js tiene que '
        + 'repartir por prefijo en vez de cerrar todo lo que no sea /shmir.');
      return;
    }
    const veredicto = upgradeAllowed(req, { store: authStore, appId: 'shmir-design' });
    if (!veredicto.allowed) {
      denySocket(socket, 401, `shmir-design: ${veredicto.reason}`);
      return;
    }
    proxyUpgrade(req, socket, head, { port: shmirProcess.PORT });
  });

  process.on('SIGTERM', () => shutdown(server, 'SIGTERM'));
  process.on('SIGINT',  () => shutdown(server, 'SIGINT'));
  process.on('unhandledRejection', (reason) => console.error('[server] Unhandled promise rejection:', reason));
  process.on('uncaughtException',  (err)    => console.error('[server] Uncaught exception:', err));
}

module.exports = app;
