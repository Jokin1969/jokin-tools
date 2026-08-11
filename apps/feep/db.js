'use strict';

// ── FEEP database (SEPARATE, portable) ──────────────────────────────────────────
// Everything the Fundación Española de Enfermedades Priónicas section stores lives
// in its OWN SQLite file — NOT the shared jokin_tools.db. This keeps the
// foundation's data a single portable file: to migrate the whole FEEP section to
// its own repository you copy the `apps/feep/` folder and this one .db file.
//
// Images (logos, signatures) are stored inline as data URLs so the database is
// fully self-contained (no loose files to move alongside it).

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.FEEP_DB_PATH || '/data/feep.db';
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS feep_certificates (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ref            TEXT UNIQUE,
    user_id        INTEGER,
    recipient_name TEXT NOT NULL,
    role           TEXT,                 -- ponente, asistente, moderador…
    event          TEXT,                 -- "IX Convención de Familiares…"
    talk_title     TEXT,                 -- optional
    date_text      TEXT,                 -- free text: "15 de marzo de 2026"
    place          TEXT,                 -- optional
    signer_name    TEXT,
    signer_role    TEXT,
    foundation     TEXT,
    logo_data      TEXT,                 -- data URL (image) or null
    signature_data TEXT,                 -- data URL (image) or null
    accent         TEXT,                 -- theme colour key
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE INDEX IF NOT EXISTS idx_feep_cert_user ON feep_certificates(user_id);

  -- Reusable defaults per user so the logo / signature / signer don't have to be
  -- re-entered for every certificate.
  CREATE TABLE IF NOT EXISTS feep_cert_defaults (
    user_id        INTEGER PRIMARY KEY,
    logo_data      TEXT,
    signature_data TEXT,
    signer_name    TEXT,
    signer_role    TEXT,
    foundation     TEXT,
    accent         TEXT,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

console.log('[feep] Database ready at:', DB_PATH);

const FOUNDATION = 'Fundación Española de Enfermedades Priónicas';

// ── Certificates ────────────────────────────────────────────────────────────────
// A human-friendly reference: FEEP-<year>-<NNNN>.
function nextRef(year) {
  const y = year || new Date().getFullYear();
  const n = db.prepare("SELECT COUNT(*) AS c FROM feep_certificates WHERE ref LIKE ?").get(`FEEP-${y}-%`).c;
  return `FEEP-${y}-${String(n + 1).padStart(4, '0')}`;
}

const CERT_FIELDS = ['recipient_name', 'role', 'event', 'talk_title', 'date_text',
  'place', 'signer_name', 'signer_role', 'foundation', 'logo_data', 'signature_data', 'accent'];

function createCert(data, userId, refYear) {
  const row = {
    ref: nextRef(refYear),
    user_id: userId != null ? userId : null,
    foundation: FOUNDATION,
  };
  for (const f of CERT_FIELDS) row[f] = data[f] != null ? data[f] : (row[f] != null ? row[f] : null);
  row.foundation = data.foundation || FOUNDATION;
  const info = db.prepare(
    `INSERT INTO feep_certificates
       (ref, user_id, recipient_name, role, event, talk_title, date_text, place,
        signer_name, signer_role, foundation, logo_data, signature_data, accent)
     VALUES
       (@ref, @user_id, @recipient_name, @role, @event, @talk_title, @date_text, @place,
        @signer_name, @signer_role, @foundation, @logo_data, @signature_data, @accent)`
  ).run(row);
  return getCert(info.lastInsertRowid, userId);
}

// Full record (includes images) — for recovery / PDF / email.
function getCert(id, userId) {
  const row = userId != null
    ? db.prepare('SELECT * FROM feep_certificates WHERE id = ? AND user_id = ?').get(id, userId)
    : db.prepare('SELECT * FROM feep_certificates WHERE id = ?').get(id);
  return row || null;
}

// List (lightweight — no image blobs) for the repository view.
function listCerts(userId) {
  const where = userId != null ? 'WHERE user_id = ?' : '';
  const args = userId != null ? [userId] : [];
  return db.prepare(
    `SELECT id, ref, recipient_name, role, event, talk_title, date_text, place,
            signer_name, created_at,
            (logo_data IS NOT NULL) AS has_logo, (signature_data IS NOT NULL) AS has_signature
       FROM feep_certificates ${where} ORDER BY created_at DESC, id DESC`
  ).all(...args);
}

function removeCert(id, userId) {
  const where = userId != null ? 'id = ? AND user_id = ?' : 'id = ?';
  const args = userId != null ? [id, userId] : [id];
  return db.prepare(`DELETE FROM feep_certificates WHERE ${where}`).run(...args).changes > 0;
}

// ── Per-user defaults ─────────────────────────────────────────────────────────
function getDefaults(userId) {
  const row = db.prepare('SELECT * FROM feep_cert_defaults WHERE user_id = ?').get(userId);
  return row || { user_id: userId, logo_data: null, signature_data: null, signer_name: null, signer_role: null, foundation: FOUNDATION, accent: null };
}

function saveDefaults(userId, d) {
  db.prepare(
    `INSERT INTO feep_cert_defaults (user_id, logo_data, signature_data, signer_name, signer_role, foundation, accent, updated_at)
     VALUES (@user_id, @logo_data, @signature_data, @signer_name, @signer_role, @foundation, @accent, CURRENT_TIMESTAMP)
     ON CONFLICT(user_id) DO UPDATE SET
       logo_data = excluded.logo_data,
       signature_data = excluded.signature_data,
       signer_name = excluded.signer_name,
       signer_role = excluded.signer_role,
       foundation = excluded.foundation,
       accent = excluded.accent,
       updated_at = CURRENT_TIMESTAMP`
  ).run({
    user_id: userId,
    logo_data: d.logo_data || null,
    signature_data: d.signature_data || null,
    signer_name: d.signer_name || null,
    signer_role: d.signer_role || null,
    foundation: d.foundation || FOUNDATION,
    accent: d.accent || null,
  });
  return getDefaults(userId);
}

module.exports = {
  db, FOUNDATION,
  nextRef, createCert, getCert, listCerts, removeCert,
  getDefaults, saveDefaults,
};
