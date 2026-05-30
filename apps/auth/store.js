// ─── Auth store ───────────────────────────────────────────────────────────────
// Users + sessions persisted in the same SQLite file the rest of the hub uses.
// Passwords are hashed with Node's built-in scrypt (no native deps, no bcrypt).
const Database = require('better-sqlite3');
const crypto = require('crypto');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.DB_PATH || '/data/jokin_tools.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE NOT NULL,
    name          TEXT,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user',   -- 'admin' | 'user'
    apps          TEXT NOT NULL DEFAULT '',        -- CSV of app ids, or '*' for all
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login    DATETIME
  );

  CREATE TABLE IF NOT EXISTS auth_sessions (
    sid        TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
  );
`);

console.log('[auth] Store initialized at:', DB_PATH);

// ─── Password hashing (scrypt) ──────────────────────────────────────────────────
function hashPassword(pw) {
  const salt = crypto.randomBytes(16);
  const hash = crypto.scryptSync(String(pw), salt, 64);
  return `scrypt$${salt.toString('hex')}$${hash.toString('hex')}`;
}

function verifyPassword(pw, stored) {
  if (!stored || typeof stored !== 'string') return false;
  const [scheme, saltHex, hashHex] = stored.split('$');
  if (scheme !== 'scrypt' || !saltHex || !hashHex) return false;
  const expected = Buffer.from(hashHex, 'hex');
  let test;
  try {
    test = crypto.scryptSync(String(pw), Buffer.from(saltHex, 'hex'), expected.length);
  } catch {
    return false;
  }
  return expected.length === test.length && crypto.timingSafeEqual(expected, test);
}

// ─── Normalisation ──────────────────────────────────────────────────────────────
const normEmail = e => String(e || '').trim().toLowerCase();
// Allowed app ids come from the registry; we keep apps as a clean CSV.
function normApps(apps) {
  if (apps === '*' || apps === 'all') return '*';
  const list = Array.isArray(apps) ? apps : String(apps || '').split(',');
  const clean = list.map(s => String(s).trim()).filter(Boolean);
  return [...new Set(clean)].join(',');
}

// ─── User CRUD ──────────────────────────────────────────────────────────────────
function publicUser(u) {
  if (!u) return null;
  return {
    id: u.id,
    email: u.email,
    name: u.name || '',
    role: u.role,
    apps: u.apps === '*' ? '*' : (u.apps ? u.apps.split(',') : []),
    active: !!u.active,
    created_at: u.created_at,
    last_login: u.last_login,
  };
}

function getUserByEmail(email) {
  return db.prepare('SELECT * FROM users WHERE email = ?').get(normEmail(email)) || null;
}
function getUserById(id) {
  return db.prepare('SELECT * FROM users WHERE id = ?').get(id) || null;
}
function listUsers() {
  return db.prepare('SELECT * FROM users ORDER BY role DESC, email ASC').all().map(publicUser);
}
function countUsers() {
  return db.prepare('SELECT COUNT(*) AS n FROM users').get().n;
}

function createUser({ email, name, password, role = 'user', apps = '' }) {
  const e = normEmail(email);
  if (!e || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e)) throw new Error('Email no válido.');
  if (!password || String(password).length < 8) throw new Error('La contraseña debe tener al menos 8 caracteres.');
  if (getUserByEmail(e)) throw new Error('Ya existe un usuario con ese email.');
  const r = role === 'admin' ? 'admin' : 'user';
  const appsCsv = r === 'admin' ? '*' : normApps(apps);
  const info = db.prepare(
    'INSERT INTO users (email, name, password_hash, role, apps, active) VALUES (?, ?, ?, ?, ?, 1)'
  ).run(e, name || '', hashPassword(password), r, appsCsv);
  return publicUser(getUserById(info.lastInsertRowid));
}

function updateUser(id, fields) {
  const u = getUserById(id);
  if (!u) throw new Error('Usuario no encontrado.');
  const updates = [], values = [];
  if (fields.name !== undefined) { updates.push('name = ?'); values.push(String(fields.name)); }
  let role = u.role;
  if (fields.role !== undefined) {
    role = fields.role === 'admin' ? 'admin' : 'user';
    updates.push('role = ?'); values.push(role);
  }
  if (fields.apps !== undefined || fields.role !== undefined) {
    // Admins always see everything; for regular users keep the explicit list.
    const appsCsv = role === 'admin' ? '*' : normApps(fields.apps !== undefined ? fields.apps : u.apps);
    updates.push('apps = ?'); values.push(appsCsv);
  }
  if (fields.active !== undefined) { updates.push('active = ?'); values.push(fields.active ? 1 : 0); }
  if (updates.length) {
    values.push(id);
    db.prepare(`UPDATE users SET ${updates.join(', ')} WHERE id = ?`).run(...values);
  }
  return publicUser(getUserById(id));
}

function setPassword(id, password) {
  if (!password || String(password).length < 8) throw new Error('La contraseña debe tener al menos 8 caracteres.');
  db.prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(hashPassword(password), id);
  // Changing the password kills every existing session for that user.
  db.prepare('DELETE FROM auth_sessions WHERE user_id = ?').run(id);
}

function deleteUser(id) {
  db.prepare('DELETE FROM auth_sessions WHERE user_id = ?').run(id);
  db.prepare('DELETE FROM users WHERE id = ?').run(id);
}

function countAdmins() {
  return db.prepare("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND active = 1").get().n;
}

// ─── Sessions ───────────────────────────────────────────────────────────────────
const SESSION_DAYS = parseInt(process.env.AUTH_SESSION_DAYS) || 7;

function createSession(userId) {
  const sid = crypto.randomBytes(32).toString('hex');
  const expires = new Date(Date.now() + SESSION_DAYS * 24 * 60 * 60 * 1000).toISOString();
  db.prepare('INSERT INTO auth_sessions (sid, user_id, expires_at) VALUES (?, ?, ?)').run(sid, userId, expires);
  db.prepare("UPDATE users SET last_login = datetime('now') WHERE id = ?").run(userId);
  return { sid, maxAgeMs: SESSION_DAYS * 24 * 60 * 60 * 1000 };
}

function getSessionUser(sid) {
  if (!sid) return null;
  const row = db.prepare('SELECT * FROM auth_sessions WHERE sid = ?').get(sid);
  if (!row) return null;
  if (new Date(row.expires_at).getTime() < Date.now()) {
    db.prepare('DELETE FROM auth_sessions WHERE sid = ?').run(sid);
    return null;
  }
  const u = getUserById(row.user_id);
  if (!u || !u.active) return null;
  return u;
}

function destroySession(sid) {
  if (sid) db.prepare('DELETE FROM auth_sessions WHERE sid = ?').run(sid);
}

function purgeExpiredSessions() {
  db.prepare("DELETE FROM auth_sessions WHERE expires_at < datetime('now')").run();
}
setInterval(purgeExpiredSessions, 60 * 60 * 1000).unref?.();

// ─── Seed the first admin from environment ──────────────────────────────────────
// On boot, ADMIN_EMAIL + ADMIN_PASSWORD guarantee there is a working admin:
// creates it if missing, and (re)sets its password/role if it already exists.
function seedAdminFromEnv() {
  const email = normEmail(process.env.ADMIN_EMAIL);
  const password = process.env.ADMIN_PASSWORD;
  if (!email || !password) {
    if (countAdmins() === 0) {
      console.warn('[auth] No admin exists and ADMIN_EMAIL/ADMIN_PASSWORD are not set — nobody can log in yet.');
    }
    return;
  }
  if (String(password).length < 8) {
    console.warn('[auth] ADMIN_PASSWORD is shorter than 8 characters — ignored.');
    return;
  }
  const existing = getUserByEmail(email);
  if (!existing) {
    db.prepare('INSERT INTO users (email, name, password_hash, role, apps, active) VALUES (?, ?, ?, ?, ?, 1)')
      .run(email, 'Admin', hashPassword(password), 'admin', '*');
    console.log(`[auth] Seeded admin account: ${email}`);
  } else {
    db.prepare("UPDATE users SET password_hash = ?, role = 'admin', apps = '*', active = 1 WHERE id = ?")
      .run(hashPassword(password), existing.id);
    console.log(`[auth] Admin account ensured/updated from env: ${email}`);
  }
}

module.exports = {
  db,
  hashPassword, verifyPassword,
  getUserByEmail, getUserById, listUsers, countUsers, countAdmins,
  createUser, updateUser, setPassword, deleteUser, publicUser,
  createSession, getSessionUser, destroySession,
  seedAdminFromEnv,
};
