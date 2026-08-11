'use strict';

// ── FEEP section router ─────────────────────────────────────────────────────────
// The Fundación Española de Enfermedades Priónicas section: its own landing page
// (a mini-hub listing the foundation's apps) plus each sub-app mounted underneath.
//
// PORTABILITY: this whole folder (apps/feep/) is self-contained — its own router,
// its own SQLite file (apps/feep/db.js → feep.db) and its own static assets. It
// does not import anything from the sibling apps. To migrate the section to the
// foundation's own repository: copy apps/feep/, copy feep.db, mount this router
// behind that repo's auth, and add its dependencies. See apps/feep/MIGRATION.md.

const express = require('express');
const path = require('path');

const router = express.Router();
const PUB = path.join(__dirname, 'public');

// Section landing (mini-hub).
router.get('/', (req, res) => res.sendFile(path.join(PUB, 'index.html')));

// Shared static assets for the section and its apps.
router.use('/assets', express.static(PUB));

// The section's apps live under their own sub-paths. Add new FEEP apps here.
router.use('/certificados', require('./certificados/routes'));

module.exports = router;
