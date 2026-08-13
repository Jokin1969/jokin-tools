const { test } = require('node:test');
const assert = require('node:assert');
const os = require('os');
const path = require('path');
const fs = require('fs');

// qr-tis uses its OWN database file (QR_TIS_DB_PATH). Point it at a temp file
// before requiring the module.
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'qrtis-test-'));
process.env.QR_TIS_DB_PATH = path.join(dir, 'qr_tis.db');

const db = require('../apps/qr-tis/db');

test('createPerson preserves the TIS exactly, leading zeros included', () => {
  const p = db.createPerson({ nombre: 'José', apellidos: 'Pérez García', tis: '0012345' }, 1);
  assert.equal(p.tis, '0012345');           // stored as text — zeros count
  assert.equal(p.tis.length, 7);
  assert.equal(p.active, 1);
  assert.equal(p.nombre, 'José');
  const back = db.getPerson(p.id);
  assert.equal(back.tis, '0012345');
});

test('update, active toggle and group membership', () => {
  const p = db.createPerson({ nombre: 'Ana', apellidos: 'López', tis: '9999999' }, 1);
  const u = db.updatePerson(p.id, { group_name: 'Planta 2', active: 0 });
  assert.equal(u.group_name, 'Planta 2');
  assert.equal(u.active, 0);
  // partial update keeps the rest
  const u2 = db.updatePerson(p.id, { nombre: 'Ana María' });
  assert.equal(u2.nombre, 'Ana María');
  assert.equal(u2.group_name, 'Planta 2');
  assert.equal(u2.active, 0);
  // clearing the group
  const u3 = db.updatePerson(p.id, { group_name: '' });
  assert.equal(u3.group_name, null);
});

test('listPeople returns everyone; delete removes and detaches from carts', () => {
  const before = db.listPeople().length;
  const p = db.createPerson({ nombre: 'Borrar', apellidos: 'Test', tis: '0000001' }, 1);
  db.cartAdd(5, p.id);
  assert.ok(db.cartIds(5).includes(p.id));
  assert.equal(db.deletePerson(p.id), true);
  assert.equal(db.listPeople().length, before);
  assert.ok(!db.cartIds(5).includes(p.id), 'deleting a person clears it from carts');
});

test('global settings persist and clamp is applied by the caller shape', () => {
  const s0 = db.getSettings();
  assert.equal(s0.qr_size, db.DEFAULT_SETTINGS.qr_size);
  const s1 = db.saveSettings({ qr_size: 500, qr_dark: '#123456', qr_style: 'dots' }, 7);
  assert.equal(s1.qr_size, 500);
  assert.equal(s1.qr_dark, '#123456');
  assert.equal(s1.qr_style, 'dots');
  // reload reflects the shared row (persists until someone changes it)
  assert.equal(db.getSettings().qr_size, 500);
});

test('cart is per-user and isolated', () => {
  const p1 = db.createPerson({ nombre: 'C1', apellidos: 'X', tis: '1000001' }, 1);
  const p2 = db.createPerson({ nombre: 'C2', apellidos: 'X', tis: '1000002' }, 1);
  db.cartAdd(10, p1.id); db.cartAdd(10, p2.id);
  db.cartAdd(11, p1.id);
  assert.deepEqual(db.cartIds(10).sort(), [p1.id, p2.id].sort());
  assert.deepEqual(db.cartIds(11), [p1.id]);
  db.cartAdd(10, p1.id); // idempotent
  assert.equal(db.cartIds(10).length, 2);
  db.cartRemove(10, p1.id);
  assert.deepEqual(db.cartIds(10), [p2.id]);
  db.cartClear(10);
  assert.equal(db.cartIds(10).length, 0);
  assert.equal(db.cartIds(11).length, 1, 'clearing one user leaves others intact');
});
