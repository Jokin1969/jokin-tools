// ─── Auth routes (mounted at /auth) ─────────────────────────────────────────────
const express = require('express');
const path = require('path');
const router = express.Router();

const store = require('./store');
const { appsForUser, appsMeta, APP_IDS } = require('./apps-registry');
const { requireAuth, requireAdmin, setSessionCookie, clearSessionCookie } = require('./middleware');

const PUBLIC_DIR = path.join(__dirname, 'public');

// ─── Pages ───────────────────────────────────────────────────────────────────
router.get('/login', (req, res) => {
  if (req.user) return res.redirect(safeNext(req.query.next));
  res.sendFile(path.join(PUBLIC_DIR, 'login.html'));
});

router.get('/admin', requireAdmin, (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'admin.html'));
});

// Only allow same-origin relative redirects (no open redirect).
function safeNext(next) {
  if (typeof next === 'string' && next.startsWith('/') && !next.startsWith('//')) return next;
  return '/';
}

// ─── Login / logout ──────────────────────────────────────────────────────────
router.post('/login', (req, res) => {
  const { email, password } = req.body || {};
  const user = store.getUserByEmail(email);
  if (!user || !user.active || !store.verifyPassword(password, user.password_hash)) {
    return res.status(401).json({ error: 'Email o contraseña incorrectos.' });
  }
  const { sid, maxAgeMs } = store.createSession(user.id);
  setSessionCookie(res, sid, maxAgeMs);
  res.json({ ok: true, redirect: safeNext(req.body.next) });
});

router.post('/logout', (req, res) => {
  store.destroySession(req.sessionId);
  clearSessionCookie(res);
  res.json({ ok: true });
});
// Convenience GET logout (e.g. a plain link) → clears and bounces to login.
router.get('/logout', (req, res) => {
  store.destroySession(req.sessionId);
  clearSessionCookie(res);
  res.redirect('/auth/login');
});

// ─── Current user + their apps ─────────────────────────────────────────────────
router.get('/api/me', requireAuth, (req, res) => {
  res.json({ user: req.user, apps: appsForUser(req.user) });
});

// Change own password.
router.post('/api/me/password', requireAuth, (req, res) => {
  const { current, password } = req.body || {};
  const full = store.getUserById(req.user.id);
  if (!full || !store.verifyPassword(current, full.password_hash)) {
    return res.status(400).json({ error: 'La contraseña actual no es correcta.' });
  }
  try {
    store.setPassword(req.user.id, password);
  } catch (e) {
    return res.status(400).json({ error: e.message });
  }
  // setPassword wipes sessions; re-issue one so the user stays logged in.
  const { sid, maxAgeMs } = store.createSession(req.user.id);
  setSessionCookie(res, sid, maxAgeMs);
  res.json({ ok: true });
});

// ─── Admin: app registry + user management ─────────────────────────────────────
router.get('/api/apps', requireAdmin, (req, res) => {
  res.json({ apps: appsMeta() });
});

router.get('/api/users', requireAdmin, (req, res) => {
  res.json({ users: store.listUsers() });
});

router.post('/api/users', requireAdmin, (req, res) => {
  try {
    const { email, name, password, role, apps } = req.body || {};
    const user = store.createUser({ email, name, password, role, apps: sanitizeApps(apps) });
    res.status(201).json({ user });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

router.patch('/api/users/:id', requireAdmin, (req, res) => {
  const id = Number(req.params.id);
  const target = store.getUserById(id);
  if (!target) return res.status(404).json({ error: 'Usuario no encontrado.' });
  const fields = {};
  if (req.body.name !== undefined) fields.name = req.body.name;
  if (req.body.role !== undefined) fields.role = req.body.role;
  if (req.body.apps !== undefined) fields.apps = sanitizeApps(req.body.apps);
  if (req.body.active !== undefined) fields.active = req.body.active;

  // Guards: don't let an admin lock themselves out or demote the last admin.
  const demotingOrDisabling =
    (fields.role !== undefined && fields.role !== 'admin' && target.role === 'admin') ||
    (fields.active === false && target.role === 'admin');
  if (demotingOrDisabling && store.countAdmins() <= 1) {
    return res.status(400).json({ error: 'No puedes quitar el último administrador.' });
  }
  if (id === req.user.id && fields.active === false) {
    return res.status(400).json({ error: 'No puedes desactivar tu propia cuenta.' });
  }
  try {
    res.json({ user: store.updateUser(id, fields) });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

router.post('/api/users/:id/password', requireAdmin, (req, res) => {
  const id = Number(req.params.id);
  if (!store.getUserById(id)) return res.status(404).json({ error: 'Usuario no encontrado.' });
  try {
    store.setPassword(id, (req.body || {}).password);
    res.json({ ok: true });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

router.delete('/api/users/:id', requireAdmin, (req, res) => {
  const id = Number(req.params.id);
  const target = store.getUserById(id);
  if (!target) return res.status(404).json({ error: 'Usuario no encontrado.' });
  if (id === req.user.id) return res.status(400).json({ error: 'No puedes eliminar tu propia cuenta.' });
  if (target.role === 'admin' && store.countAdmins() <= 1) {
    return res.status(400).json({ error: 'No puedes eliminar el último administrador.' });
  }
  store.deleteUser(id);
  res.json({ ok: true });
});

// Keep only known app ids (defends against typos / stale clients).
function sanitizeApps(apps) {
  if (apps === '*') return '*';
  const list = Array.isArray(apps) ? apps : String(apps || '').split(',');
  return list.map(s => String(s).trim()).filter(a => APP_IDS.includes(a));
}

module.exports = router;
