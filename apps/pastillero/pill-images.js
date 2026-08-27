'use strict';

// ── Pill images — one PNG per Código Nacional, hand-curated ──────────────────────
// Not the CIMA cache (raw AEMPS photos, mixed quality/background): this is a
// separate, deliberately-prepared repository — transparent PNG, same visual
// treatment for every medication — shared by Pastillero, Data Matrix and
// Asignación. Named "<CN>.png", exactly the Código Nacional as stored (digits
// only, no check digit/prefix). See apps/pastillero/pill-images/README.md for
// how to add one.
//
// Lives INSIDE THE REPO (apps/pastillero/pill-images/ by default), not on a
// volume: these files are added via GitHub, so they need to travel with a
// normal commit + deploy, not with server/SSH access to a Railway volume. The
// env var below is only an escape hatch (e.g. to point at a volume later if
// the collection ever grows large enough to warrant it); nothing depends on it.

const fs = require('fs');
const path = require('path');

const DIR = process.env.PASTILLERO_PILL_IMAGES_DIR || path.join(__dirname, 'pill-images');
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
