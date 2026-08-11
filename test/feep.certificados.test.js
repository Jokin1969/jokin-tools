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
const seed = require('../apps/feep/seed-certificates');

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

test('pdf.render produces a valid PDF for every theme and orientation', async () => {
  for (const accent of Object.keys(pdf.THEMES)) {
    for (const orientation of ['horizontal', 'vertical']) {
      const buf = await pdf.render({
        ref: 'FEEP-2026-0001', recipient_name: 'María Fernández', role: 'ponente',
        event: 'la IX Convención de Familiares', talk_title: 'Diagnóstico precoz',
        date_text: '15 de marzo de 2026', place: 'Madrid',
        signer_name: 'Alberto Martínez', signer_role: 'Secretario', accent, orientation,
      });
      assert.ok(Buffer.isBuffer(buf) && buf.length > 1000, `PDF generated (${accent}/${orientation})`);
      assert.equal(buf.slice(0, 5).toString('latin1'), '%PDF-', `valid PDF header (${accent}/${orientation})`);
    }
  }
});

test('orientation is stored and returned on the certificate and defaults', () => {
  const c = db.createCert({ recipient_name: 'Vert Test', orientation: 'vertical' }, 3);
  assert.equal(db.getCert(c.id, 3).orientation, 'vertical');
  db.saveDefaults(3, { signer_name: 'Alberto Martínez', orientation: 'vertical' });
  assert.equal(db.getDefaults(3).orientation, 'vertical');
});

test('seal mode is stored on the certificate and defaults; PDF renders each mode', async () => {
  const c = db.createCert({ recipient_name: 'Sello Test', seal_mode: 'ninguno' }, 3);
  assert.equal(db.getCert(c.id, 3).seal_mode, 'ninguno');
  const c2 = db.createCert({ recipient_name: 'Sello Img', seal_mode: 'imagen', seal_data: 'data:image/png;base64,iVBORw0KGgo=' }, 3);
  assert.equal(db.getCert(c2.id, 3).seal_mode, 'imagen');

  db.saveDefaults(3, { signer_name: 'Alberto Martínez', seal_mode: 'ninguno' });
  assert.equal(db.getDefaults(3).seal_mode, 'ninguno');

  for (const seal_mode of ['emblema', 'ninguno', 'imagen']) {
    const buf = await pdf.render({ ref: 'FEEP-2026-0001', recipient_name: 'X', seal_mode, seal_data: seal_mode === 'imagen' ? null : null });
    assert.equal(buf.slice(0, 5).toString('latin1'), '%PDF-', `PDF for seal ${seal_mode}`);
  }
});

test('event_date is stored, and issue date = event + 1 day (with rollover)', () => {
  const c = db.createCert({ recipient_name: 'Fecha Test', event_date: '2018-11-30', date_text: '30 de noviembre de 2018' }, 3);
  assert.equal(db.getCert(c.id, 3).event_date, '2018-11-30');
  assert.equal(pdf.longFromISO('2018-11-10', 1), '11 de noviembre de 2018');
  assert.equal(pdf.longFromISO('2018-11-30', 1), '1 de diciembre de 2018');
  assert.equal(pdf.longFromISO('2025-12-31', 1), '1 de enero de 2026');
  assert.equal(pdf.longFromISO('', 1), null);
  assert.equal(pdf.longFromISO('texto libre', 1), null);
});

test('pdf.render tolerates missing fields and bad image data', async () => {
  const buf = await pdf.render({ recipient_name: 'Solo Nombre', logo_data: 'not-an-image', signature_data: 'data:image/png;base64,@@@' });
  assert.equal(buf.slice(0, 5).toString('latin1'), '%PDF-');
});

test('seed.longDate: ISO → Spanish long date (timezone-safe)', () => {
  assert.equal(seed.longDate('2018-11-10'), '10 de noviembre de 2018');
  assert.equal(seed.longDate('2025-11-15'), '15 de noviembre de 2025');
});

test('seed: imports the 11 known certificates and is idempotent', () => {
  const user = { id: 100, email: 'x@feep.es' };
  assert.equal(seed.seedFeepCertificates(user), 11, 'first run creates all 11');
  assert.equal(seed.seedFeepCertificates(user), 0, 'second run creates none');
  const list = db.listCerts(100);
  assert.equal(list.length, 11);
  const refs = list.map(c => c.ref);
  assert.equal(new Set(refs).size, refs.length, 'references are unique');
  assert.ok(list.every(c => c.event.startsWith('la ') && /de 20\d\d$/.test(c.date_text)));
});
