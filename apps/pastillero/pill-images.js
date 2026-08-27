'use strict';

// ── Pill images — one PNG per Código Nacional, hand-curated ──────────────────────
// Not the CIMA cache (raw AEMPS photos, mixed quality/background): this is a
// separate, deliberately-prepared repository — transparent PNG, same visual
// treatment for every medication — shared by Pastillero, Data Matrix and
// Asignación. Files are placed directly on disk by whoever curates them; there's
// no upload endpoint (Fase 1 scope). Named "<CN>.png", exactly the Código
// Nacional as stored (digits only, no check/prefix).
//
// Lives on a VOLUME, not in the image: same reasoning as SHMIR_REFERENCE_DIR in
// apps/shmir (see root CLAUDE.md) — the container filesystem is ephemeral, so a
// file dropped into the image's local path would vanish on the next redeploy.

const fs = require('fs');
const path = require('path');

const DIR = process.env.PASTILLERO_PILL_IMAGES_DIR || '/data/pastillero/pills';
if (!fs.existsSync(DIR)) fs.mkdirSync(DIR, { recursive: true });

const CN_RE = /^[0-9]{4,8}$/;

function pillImagePath(cn) {
  if (!CN_RE.test(String(cn || ''))) return null;
  return path.join(DIR, `${cn}.png`);
}
function hasPillImage(cn) {
  const p = pillImagePath(cn);
  return !!(p && fs.existsSync(p));
}

module.exports = { DIR, CN_RE, pillImagePath, hasPillImage };
