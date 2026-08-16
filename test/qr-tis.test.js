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

test('createPerson preserves the TIS and pharmacy number exactly, leading zeros included', () => {
  const p = db.createPerson({ pharmacy_no: '01234', nombre: 'José', apellidos: 'Pérez García', tis: '00123456' }, 1);
  assert.equal(p.tis, '00123456');          // stored as text — zeros count
  assert.equal(p.tis.length, 8);
  assert.equal(p.pharmacy_no, '01234');     // 5-digit pharmacy number, zeros preserved
  assert.equal(p.active, 1);
  assert.equal(p.nombre, 'José');
  const back = db.getPerson(p.id);
  assert.equal(back.tis, '00123456');
  assert.equal(back.pharmacy_no, '01234');
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
  // multiple groups are stored newline-joined in the same column
  const u4 = db.updatePerson(p.id, { group_name: 'Planta 2\nUrgencias' });
  assert.equal(db.getPerson(p.id).group_name, 'Planta 2\nUrgencias');
});

test('setDeceased marks/reverts a person; deceased implies inactive; kept in listPeople', () => {
  const p = db.createPerson({ nombre: 'Luis', apellidos: 'Vega', tis: '5550001' }, 1);
  assert.equal(p.deceased, 0);
  // Mark deceased → deceased=1, timestamped, and inactive.
  const d = db.setDeceased(p.id, true);
  assert.equal(d.deceased, 1);
  assert.equal(d.active, 0, 'deceased implies inactive (QR inaccessible)');
  assert.ok(d.deceased_at, 'records when it was marked');
  // Still present in the directory (record is kept).
  assert.ok(db.listPeople().some(x => x.id === p.id));
  assert.ok('deceased' in db.listPeople().find(x => x.id === p.id));
  // Revert → deceased cleared and reactivated.
  const r = db.setDeceased(p.id, false);
  assert.equal(r.deceased, 0);
  assert.equal(r.deceased_at, null);
  assert.equal(r.active, 1, 'reverting restores active');
});

test('uniqueness: pharmacy (except 00000) and TIS', () => {
  const a = db.createPerson({ pharmacy_no: '55501', nombre: 'Uno', apellidos: 'X', tis: '55500001' }, 1);
  // pharmacy taken by another
  assert.equal(db.pharmacyTaken('55501'), true);
  assert.equal(db.pharmacyTaken('55501', a.id), false, 'excludes self');
  assert.equal(db.pharmacyTaken('55502'), false, 'free number');
  // 00000 never counts as taken (can repeat)
  db.createPerson({ pharmacy_no: '00000', nombre: 'Sin', apellidos: 'Num', tis: '55500002' }, 1);
  db.createPerson({ pharmacy_no: '00000', nombre: 'Sin2', apellidos: 'Num', tis: '55500003' }, 1);
  assert.equal(db.pharmacyTaken('00000'), false, '00000 may repeat');
  // TIS taken
  assert.equal(db.tisTaken('55500001'), true);
  assert.equal(db.tisTaken('55500001', a.id), false, 'excludes self');
  assert.equal(db.tisTaken('55599999'), false);
});

test('per-person QR overrides (colour/background/style) are stored and cleared', () => {
  const p = db.createPerson({ nombre: 'Color', apellidos: 'Test', tis: '00000011', qr_dark: '#c23a3a', qr_style: 'dots' }, 1);
  assert.equal(p.qr_dark, '#c23a3a');
  assert.equal(p.qr_style, 'dots');
  assert.equal(p.qr_light, null);          // not set → null (falls back to global)
  // change and then clear
  const u = db.updatePerson(p.id, { qr_dark: '#1f9d62', qr_light: '#fff8e1' });
  assert.equal(u.qr_dark, '#1f9d62');
  assert.equal(u.qr_light, '#fff8e1');
  assert.equal(u.qr_style, 'dots');        // untouched field kept
  const cleared = db.updatePerson(p.id, { qr_dark: null, qr_light: null, qr_style: null });
  assert.equal(cleared.qr_dark, null);
  assert.equal(cleared.qr_style, null);
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

test('global settings persist; separate list/card QR defaults (100/200)', () => {
  const s0 = db.getSettings();
  assert.equal(s0.qr_size, db.DEFAULT_SETTINGS.qr_size);
  assert.equal(s0.list_qr_size, 100);   // table QR default
  assert.equal(s0.card_qr_size, 200);   // cards QR default
  const s1 = db.saveSettings({ qr_size: 500, qr_dark: '#123456', qr_style: 'dots', card_qr_size: 180 }, 7);
  assert.equal(s1.qr_size, 500);
  assert.equal(s1.qr_dark, '#123456');
  assert.equal(s1.qr_style, 'dots');
  assert.equal(s1.card_qr_size, 180);
  assert.equal(s1.list_qr_size, 100, 'untouched size keeps its default');
  // reload reflects the shared row (persists until someone changes it)
  assert.equal(db.getSettings().qr_size, 500);
  // a NULL column (e.g. after a migration) falls back to the default, not null
  db.db.prepare('UPDATE tis_settings SET card_qr_size = NULL WHERE id = 1').run();
  assert.equal(db.getSettings().card_qr_size, 200);
});

test('createManyPeople (bulk import) inserts all in one go', () => {
  const before = db.listPeople().length;
  const rows = [
    { nombre: 'Imp Uno', apellidos: 'A', tis: '2000001' },
    { nombre: 'Imp Dos', apellidos: 'B', tis: '2000002', group_name: 'Lote X' },
  ];
  const created = db.createManyPeople(rows, 3);
  assert.equal(created.length, 2);
  assert.equal(db.listPeople().length, before + 2);
  assert.equal(created[1].group_name, 'Lote X');
});

test('touchPerson bumps last_used_at; recentPeople orders by it (limit respected)', () => {
  const a = db.createPerson({ nombre: 'Rec A', apellidos: 'X', tis: '3000001' }, 1);
  const b = db.createPerson({ nombre: 'Rec B', apellidos: 'X', tis: '3000002' }, 1);
  // touchPerson updates last_used_at
  const t0 = db.getPerson(a.id).last_used_at;
  db.touchPerson(a.id);
  assert.ok(db.getPerson(a.id).last_used_at >= t0);
  // Set distinct timestamps directly (CURRENT_TIMESTAMP is only 1s-resolution).
  db.db.prepare('UPDATE tis_people SET last_used_at = ? WHERE id = ?').run('2999-01-01 00:00:00', a.id);
  db.db.prepare('UPDATE tis_people SET last_used_at = ? WHERE id = ?').run('2999-01-01 00:00:01', b.id);
  const recent = db.recentPeople(10);
  const ia = recent.findIndex(p => p.id === a.id);
  const ib = recent.findIndex(p => p.id === b.id);
  assert.ok(ib >= 0 && ia >= 0 && ib < ia, 'B (later timestamp) comes before A');
  assert.ok('handled_at' in recent[0]);
  assert.ok(db.recentPeople(3).length <= 3, 'limit respected');
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
