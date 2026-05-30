// ─── Auth middleware ────────────────────────────────────────────────────────────
const store = require('./store');
const { canAccess } = require('./apps-registry');

const COOKIE_NAME = 'jt_sid';
const isProd = process.env.NODE_ENV === 'production';

// Minimal cookie parser (avoids pulling in cookie-parser).
function parseCookies(header) {
  const out = {};
  if (!header) return out;
  for (const part of header.split(';')) {
    const i = part.indexOf('=');
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    const v = part.slice(i + 1).trim();
    if (k) out[k] = decodeURIComponent(v);
  }
  return out;
}

function setSessionCookie(res, sid, maxAgeMs) {
  res.cookie(COOKIE_NAME, sid, {
    httpOnly: true,
    sameSite: 'lax',
    secure: isProd,
    path: '/',
    maxAge: maxAgeMs,
  });
}

function clearSessionCookie(res) {
  res.clearCookie(COOKIE_NAME, { path: '/', httpOnly: true, sameSite: 'lax', secure: isProd });
}

// Attach req.user (or null) on every request based on the session cookie.
function attachUser(req, res, next) {
  const cookies = parseCookies(req.headers.cookie);
  req.sessionId = cookies[COOKIE_NAME] || null;
  req.user = req.sessionId ? store.publicUser(store.getSessionUser(req.sessionId)) : null;
  next();
}

// Is this request expecting JSON (API/XHR) rather than an HTML page?
function wantsJson(req) {
  if (req.path.includes('/api/')) return true;
  const accept = req.headers.accept || '';
  return req.xhr || (accept.includes('application/json') && !accept.includes('text/html'));
}

function denyOrRedirect(req, res, status, message) {
  if (wantsJson(req)) return res.status(status).json({ error: message });
  if (status === 401) {
    const next = encodeURIComponent(req.originalUrl || '/');
    return res.redirect(`/auth/login?next=${next}`);
  }
  return res.status(status).sendFile(require('path').join(__dirname, 'public', 'forbidden.html'));
}

// ─── CSRF guard (origin/referer based, no token plumbing in the frontend) ───────
// For state-changing methods we require that, when the browser sends an Origin
// (or Referer), it matches our own origin. Modern browsers always send Origin on
// cross-site POST/PUT/PATCH/DELETE, so a forged cross-site request is rejected.
// Requests with neither header are not cross-site browser requests (e.g. curl,
// health checks) and can't carry the victim's cookie via CSRF, so they pass.
function allowedOrigins(req) {
  const set = new Set();
  const host = req.get('host');
  if (host) set.add(`${req.protocol}://${host}`);
  if (process.env.BASE_URL) {
    try { set.add(new URL(process.env.BASE_URL).origin); } catch { /* ignore */ }
  }
  return set;
}

function csrfGuard(req, res, next) {
  if (req.method === 'GET' || req.method === 'HEAD' || req.method === 'OPTIONS') return next();
  const allowed = allowedOrigins(req);
  const origin = req.get('origin');
  if (origin) {
    return allowed.has(origin) ? next() : res.status(403).json({ error: 'Origen no permitido (CSRF).' });
  }
  const referer = req.get('referer');
  if (referer) {
    try { if (allowed.has(new URL(referer).origin)) return next(); } catch { /* fallthrough */ }
    return res.status(403).json({ error: 'Origen no permitido (CSRF).' });
  }
  return next(); // no Origin/Referer → not a cross-site browser request
}

function requireAuth(req, res, next) {
  if (!req.user) return denyOrRedirect(req, res, 401, 'Inicia sesión para continuar.');
  next();
}

function requireAdmin(req, res, next) {
  if (!req.user) return denyOrRedirect(req, res, 401, 'Inicia sesión para continuar.');
  if (req.user.role !== 'admin') return denyOrRedirect(req, res, 403, 'Necesitas permisos de administrador.');
  next();
}

// Gate an app router: must be logged in AND have access to that app id.
function requireApp(appId) {
  return (req, res, next) => {
    if (!req.user) return denyOrRedirect(req, res, 401, 'Inicia sesión para continuar.');
    if (!canAccess(req.user, appId)) return denyOrRedirect(req, res, 403, 'No tienes acceso a esta herramienta.');
    next();
  };
}

module.exports = {
  COOKIE_NAME, attachUser, csrfGuard, requireAuth, requireAdmin, requireApp,
  setSessionCookie, clearSessionCookie,
};
