require('dotenv').config();
const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// ─── Ensure /data directories exist ─────────────────────────────────────────
const dataDir = path.dirname(process.env.DB_PATH || '/data/jokin_tools.db');
const uploadsDir = path.join(dataDir, 'uploads');
[dataDir, uploadsDir].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`[server] Created directory: ${dir}`);
  }
});

// ─── Middleware ───────────────────────────────────────────────────────────────
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// ─── Auth: identify the user on every request ───────────────────────────────────
const authStore = require('./apps/auth/store');
const authRouter = require('./apps/auth/routes');
const { attachUser, requireAuth, requireApp } = require('./apps/auth/middleware');
app.use(attachUser);

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

// ─── Hub root (requires login) ──────────────────────────────────────────────────
app.get('/', requireAuth, (req, res) => {
  res.sendFile(path.join(__dirname, 'src', 'index.html'));
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
app.use((err, req, res, next) => {
  console.error('[server] Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error', message: err.message });
});

// ─── Start ────────────────────────────────────────────────────────────────────
// Ensure there's a working admin (from ADMIN_EMAIL / ADMIN_PASSWORD) before listening.
authStore.seedAdminFromEnv();

// Re-memory is now per-user. Assign any pre-existing (ownerless) memories to a
// single owner — REMEMORY_OWNER_EMAIL if set, otherwise the seeded admin.
try {
  const ownerEmail = (process.env.REMEMORY_OWNER_EMAIL || process.env.ADMIN_EMAIL || '').trim().toLowerCase();
  const owner = ownerEmail ? authStore.getUserByEmail(ownerEmail) : null;
  if (owner) {
    const n = reMemoryDb.assignOrphanMemories(owner.id);
    if (n) console.log(`[re-memory] Assigned ${n} pre-existing memories to ${owner.email}`);
  } else {
    const { db } = reMemoryDb;
    const orphans = db.prepare('SELECT COUNT(*) AS n FROM memories WHERE user_id IS NULL').get().n;
    if (orphans) console.warn(`[re-memory] ${orphans} memories have no owner and ADMIN_EMAIL/REMEMORY_OWNER_EMAIL is not set — they will be hidden until assigned.`);
  }
} catch (e) {
  console.error('[re-memory] Orphan assignment skipped:', e.message);
}

app.listen(PORT, () => {
  console.log(`[server] Jokin's Tools running on port ${PORT}`);
  console.log(`[server] DB path: ${process.env.DB_PATH || '/data/jokin_tools.db'}`);
  console.log(`[server] NODE_ENV: ${process.env.NODE_ENV || 'development'}`);
});

module.exports = app;
