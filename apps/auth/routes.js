// ─── Auth routes (mounted at /auth) ─────────────────────────────────────────────
const express = require('express');
const path = require('path');
const router = express.Router();

const store = require('./store');
const mailer = require('./mailer');
const { appsForUser, appsMeta, APP_IDS } = require('./apps-registry');
const { requireAuth, requireAdmin, requireLogin, setSessionCookie, clearSessionCookie } = require('./middleware');
const { rateLimit } = require('./rate-limit');

const PUBLIC_DIR = path.join(__dirname, 'public');

// Throttle password-guessing on login and password-change.
const loginLimiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 10, message: 'Demasiados intentos de inicio de sesión. Espera unos minutos.' });
const pwdLimiter   = rateLimit({ windowMs: 15 * 60 * 1000, max: 10, message: 'Demasiados intentos. Espera unos minutos.' });
const resetLimiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 6,  message: 'Demasiadas solicitudes. Espera unos minutos.' });

// A valid-format hash for a random password. Verifying an incoming password
// against this when the account doesn't exist keeps login response time uniform
// (defeats user-enumeration by timing).
const DUMMY_HASH = store.hashPassword(require('crypto').randomBytes(16).toString('hex'));

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
router.post('/login', loginLimiter, (req, res) => {
  const { email, password } = req.body || {};
  const user = store.getUserByEmail(email);
  // Always run one scrypt verification (against a dummy hash when the user is
  // missing/inactive) so timing doesn't reveal whether an account exists.
  const usable = user && user.active;
  const hash = usable ? user.password_hash : DUMMY_HASH;
  const passwordOk = store.verifyPassword(password, hash);
  if (!usable || !passwordOk) {
    return res.status(401).json({ error: 'Email o contraseña incorrectos.' });
  }
  // Transparently upgrade old/weaker password hashes to the current scrypt cost.
  if (store.needsRehash(user.password_hash)) {
    try { store.upgradePasswordHash(user.id, password); } catch (e) { console.error('[auth] rehash failed:', e.message); }
  }
  const { sid, maxAgeMs } = store.createSession(user.id);
  setSessionCookie(res, sid, maxAgeMs);
  // First-login / temp passwords must be changed before going anywhere else.
  const redirect = user.must_change ? '/auth/change-password' : safeNext(req.body.next);
  res.json({ ok: true, redirect, must_change: !!user.must_change });
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
router.post('/api/me/password', pwdLimiter, requireAuth, (req, res) => {
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

// ─── Forced first-login change + self-service change ───────────────────────────
router.get('/change-password', requireLogin, (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'change-password.html'));
});

router.post('/api/change-password', pwdLimiter, requireLogin, (req, res) => {
  const { current, password } = req.body || {};
  const full = store.getUserById(req.user.id);
  if (!full) return res.status(401).json({ error: 'Sesión no válida.' });
  // A voluntary change (not forced) must prove the current password.
  if (!full.must_change && !store.verifyPassword(current, full.password_hash)) {
    return res.status(400).json({ error: 'La contraseña actual no es correcta.' });
  }
  const np = String(password || '');
  if (np.length < 8) return res.status(400).json({ error: 'La contraseña debe tener al menos 8 caracteres.' });
  if (np === '12345678') return res.status(400).json({ error: 'Elige una contraseña distinta de la inicial (12345678).' });
  try {
    store.setPassword(req.user.id, np);      // wipes sessions
    store.setMustChange(req.user.id, false);
  } catch (e) {
    return res.status(400).json({ error: e.message });
  }
  // Re-issue a session so the user stays logged in after the change.
  const { sid, maxAgeMs } = store.createSession(req.user.id);
  setSessionCookie(res, sid, maxAgeMs);
  res.json({ ok: true });
});

// ─── Forgot / reset password by email ──────────────────────────────────────────
router.get('/forgot-password', (req, res) => {
  if (req.user && !req.user.must_change) return res.redirect('/');
  res.sendFile(path.join(PUBLIC_DIR, 'forgot-password.html'));
});

router.post('/forgot-password', resetLimiter, async (req, res) => {
  try {
    const user = store.getUserByEmail((req.body || {}).email);
    if (user && user.active && mailer.smtpConfigured()) {
      const token = store.createResetToken(user.id);
      try { await mailer.sendResetEmail(user, token); }
      catch (e) { console.error('[auth] reset email failed:', e.message); }
    }
  } catch (e) {
    console.error('[auth] forgot-password error:', e.message);
  }
  // Always the same response — never reveal whether an email exists.
  res.json({ ok: true });
});

router.get('/reset-password/:token', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'reset-password.html'));
});

router.post('/reset-password', resetLimiter, (req, res) => {
  const { token, password } = req.body || {};
  const user = store.getUserByResetToken(token);
  if (!user) return res.status(400).json({ error: 'El enlace no es válido o ha caducado. Solicita uno nuevo.' });
  const np = String(password || '');
  if (np.length < 8) return res.status(400).json({ error: 'La contraseña debe tener al menos 8 caracteres.' });
  if (np === '12345678') return res.status(400).json({ error: 'Elige una contraseña distinta de la inicial (12345678).' });
  try {
    store.setPassword(user.id, np);          // also clears the reset token + sessions
    store.setMustChange(user.id, false);
  } catch (e) {
    return res.status(400).json({ error: e.message });
  }
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
    // Admin-created accounts get a temporary password the user must change on
    // first login (unless the admin explicitly opts out).
    const mustChange = req.body.mustChange !== false;
    const user = store.createUser({ email, name, password, role, apps: sanitizeApps(apps), mustChange });
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
    // Force a password change on next login, or clear that flag, on demand.
    if (req.body.must_change !== undefined) store.setMustChange(id, !!req.body.must_change);
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
    // An admin-set password is temporary → force the user to change it next time,
    // unless the admin explicitly opts out.
    store.setMustChange(id, (req.body || {}).mustChange !== false);
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
