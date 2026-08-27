'use strict';

// ── Pill images — one PNG per Código Nacional, hand-curated ──────────────────────
// Not the CIMA cache (raw AEMPS photos, mixed quality/background): this is a
// separate, deliberately-prepared repository — transparent PNG, same visual
// treatment for every medication — shared by Pastillero, Data Matrix, Asignación
// and Galénica. Named "<CN>.png", exactly the Código Nacional as stored (digits
// only, no check digit/prefix).
//
// Two different places, on purpose:
//   SOURCE_DIR — apps/pastillero/pill-images/, INSIDE THE REPO. This is the
//                delivery mechanism: add/replace a PNG via GitHub (see its
//                README.md), no server/SSH access needed.
//   DIR        — the volume (PASTILLERO_PILL_IMAGES_DIR, default
//                /data/pastillero/pills). This is what actually gets SERVED.
// syncFromRepo() copies SOURCE_DIR → DIR at boot (called once from
// runStartupMigrations() in server.js) — same reasoning as SHMIR_REFERENCE_DIR
// in apps/shmir (root CLAUDE.md): the container filesystem is ephemeral, so
// serving straight from the repo checkout would still work today but ties the
// photo path to wherever THIS build happened to unpack, and — unlike the repo
// checkout — the volume is the one place a future upload feature could also
// write to without fighting the next git deploy. Git is the only writer for
// now, so the sync is a full mirror: a CN removed from the repo also
// disappears from the server, not just new/changed files copied over.

const fs = require('fs');
const path = require('path');

const SOURCE_DIR = path.join(__dirname, 'pill-images');
const DIR = process.env.PASTILLERO_PILL_IMAGES_DIR || '/data/pastillero/pills';
if (!fs.existsSync(DIR)) fs.mkdirSync(DIR, { recursive: true });

const CN_RE = /^[0-9]{4,8}$/;
const FILE_RE = /^[0-9]{4,8}\.png$/;

function pillImagePath(cn) {
  if (!CN_RE.test(String(cn || ''))) return null;
  return path.join(DIR, `${cn}.png`);
}
function hasPillImage(cn) {
  const p = pillImagePath(cn);
  return !!(p && fs.existsSync(p));
}

// Mirror SOURCE_DIR (repo, delivered via GitHub) onto DIR (volume, actually
// served). Copies new/changed files, removes from DIR anything no longer in
// SOURCE_DIR. Safe to call on every boot — it's a no-op once both sides match.
// `srcOverride` is test-only; production always mirrors the real SOURCE_DIR.
function syncFromRepo(srcOverride) {
  const source = srcOverride || SOURCE_DIR;
  let copied = 0, removed = 0;
  const wanted = fs.existsSync(source) ? fs.readdirSync(source).filter(f => FILE_RE.test(f)) : [];
  const wantedSet = new Set(wanted);
  for (const f of wanted) {
    const src = path.join(source, f), dst = path.join(DIR, f);
    let needsCopy = true;
    try { const [ss, ds] = [fs.statSync(src), fs.statSync(dst)]; needsCopy = ss.size !== ds.size || ss.mtimeMs > ds.mtimeMs; }
    catch { /* dst doesn't exist yet → copy */ }
    if (needsCopy) { fs.copyFileSync(src, dst); copied++; }
  }
  if (fs.existsSync(DIR)) {
    for (const f of fs.readdirSync(DIR)) {
      if (FILE_RE.test(f) && !wantedSet.has(f)) { fs.unlinkSync(path.join(DIR, f)); removed++; }
    }
  }
  return { copied, removed, total: wanted.length };
}

module.exports = { SOURCE_DIR, DIR, CN_RE, pillImagePath, hasPillImage, syncFromRepo };
