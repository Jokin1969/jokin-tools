const { test } = require('node:test');
const assert = require('node:assert');
const os = require('os');
const path = require('path');
const fs = require('fs');

// FEEP uses its OWN database file (FEEP_DB_PATH), separate from the shared DB.
// Point it at a temp file before requiring the module.
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'feep-test-'));
process.env.FEEP_DB_PATH = path.join(dir, 'feep.db');

const db = require('../apps/feep/db');
const pdf = require('../apps/feep/certificados/pdf');

test('nextRef: sequential per year, zero-padded', () => {
  assert.match(db.nextRef(2026), /^FEEP-2026-0001$/);
});

test('certificate lifecycle: create → list → get → delete, scoped per user', () => {
  const c = db.createCert({
    recipient_name: 'Ana Pérez', role: 'ponente',
    event: 'la IX Convención de Familiares', date_text: '1 de junio de 2026',
    signer_name: 'El Secretario', accent: 'burdeos',
  }, 5);
  assert.match(c.ref, /^FEEP-\d{4}-0001$/);
  assert.equal(c.recipient_name, 'Ana Pérez');
  assert.equal(c.foundation, db.FOUNDATION);

  // Second certificate → next reference.
  const c2 = db.createCert({ recipient_name: 'Luis Gómez' }, 5);
  assert.match(c2.ref, /-0002$/);

  // list is per-user and lightweight (no image blobs).
  const list5 = db.listCerts(5);
  assert.equal(list5.length, 2);
  assert.ok(!('logo_data' in list5[0]), 'list omits image blobs');
  assert.equal(db.listCerts(9).length, 0, 'per-user isolation');

  // full get includes everything; wrong user gets null.
  assert.equal(db.getCert(c.id, 5).accent, 'burdeos');
  assert.equal(db.getCert(c.id, 9), null);

  assert.equal(db.removeCert(c.id, 5), true);
  assert.equal(db.listCerts(5).length, 1);
});

test('defaults: save + reload per user', () => {
  const saved = db.saveDefaults(7, { signer_name: 'Secretario FEEP', signer_role: 'Secretario', accent: 'verde' });
  assert.equal(saved.signer_name, 'Secretario FEEP');
  const again = db.getDefaults(7);
  assert.equal(again.signer_name, 'Secretario FEEP');
  assert.equal(again.accent, 'verde');
  // upsert overwrites.
  db.saveDefaults(7, { signer_name: 'Otro', accent: 'clasico' });
  assert.equal(db.getDefaults(7).signer_name, 'Otro');
});

test('pdf.render produces a valid PDF for every theme', async () => {
  for (const accent of Object.keys(pdf.THEMES)) {
    const buf = await pdf.render({
      ref: 'FEEP-2026-0001', recipient_name: 'María Fernández', role: 'ponente',
      event: 'la IX Convención de Familiares', talk_title: 'Diagnóstico precoz',
      date_text: '15 de marzo de 2026', place: 'Madrid',
      signer_name: 'Joaquín Castilla', signer_role: 'Secretario', accent,
    });
    assert.ok(Buffer.isBuffer(buf) && buf.length > 1000, `PDF generated (${accent})`);
    assert.equal(buf.slice(0, 5).toString('latin1'), '%PDF-', `valid PDF header (${accent})`);
  }
});

test('pdf.render tolerates missing fields and bad image data', async () => {
  const buf = await pdf.render({ recipient_name: 'Solo Nombre', logo_data: 'not-an-image', signature_data: 'data:image/png;base64,@@@' });
  assert.equal(buf.slice(0, 5).toString('latin1'), '%PDF-');
});
