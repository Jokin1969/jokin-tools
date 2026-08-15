const { test } = require('node:test');
const assert = require('node:assert');
const os = require('os');
const path = require('path');
const fs = require('fs');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dm-test-'));
process.env.DM_DB_PATH = path.join(dir, 'datamatrix.db');

const gs1 = require('../apps/datamatrix/gs1');
const visual = require('../apps/datamatrix/visual');
const db = require('../apps/datamatrix/db');

const GS = gs1.GS;

test('gs1.parse extracts GTIN, serial, lote, caducidad, CN (with ]d2 and DD=00)', () => {
  const raw = ']d2' + '0108470006991545' + '21SN-0001' + GS + '17250800' + '10LOTE9' + GS + '710123456789';
  const f = gs1.parse(raw);
  assert.equal(f.gtin, '08470006991545');
  assert.equal(f.serial, 'SN-0001');
  assert.equal(f.lote, 'LOTE9');
  assert.equal(f.caducidad, '250800');
  assert.equal(f.cn, '123456789');
  assert.equal(gs1.expiryToIso('250800'), '2025-08-31'); // DD=00 → end of month
  assert.equal(gs1.expiryToIso('261130'), '2026-11-30');
});

test('gs1.boxKey uses GTIN|serial (identity of a box)', () => {
  const f = gs1.parse('0108470006991545' + '21SN0001' + GS + '17261130');
  assert.equal(gs1.boxKey(f, 'x'), '08470006991545|SN0001');
});

test('visual: deterministic colour/shape per GTIN, override wins', () => {
  const c1 = visual.autoColor('08470006991545'), c2 = visual.autoColor('08470006991545');
  assert.equal(c1, c2, 'deterministic');
  assert.match(c1, /^#[0-9a-f]{6}$/i);
  assert.equal(visual.resolveColor('x', '#abcdef'), '#abcdef');
  assert.equal(visual.resolveColor('x', 'bad'), visual.autoColor('x'));
  assert.ok(visual.SHAPES.includes(visual.autoShape('123')));
});

test('createItem + findByKey dedup; product name resolved via join', () => {
  const f = gs1.parse('0108470006991545' + '21AAA1' + GS + '17261130' + '10L1');
  const data = { raw: 'r1', box_key: gs1.boxKey(f, 'r1'), gtin: f.gtin, serial: f.serial, lote: f.lote, caducidad: gs1.expiryToIso(f.caducidad), cn: f.cn };
  const it = db.createItem(data, 1);
  assert.equal(it.status, 'activo');
  assert.ok(db.findByKey(data.box_key), 'found by key');
  assert.equal(db.findByKey('nope'), null);
  // name comes from the product catalog
  db.upsertProduct('08470006991545', { nombre: 'Ibuprofeno 600' });
  assert.equal(db.getItem(it.id).nombre, 'Ibuprofeno 600');
});

test('normGtin canonicalises; EAN-13 catalogue matches GTIN-14 boxes', () => {
  assert.equal(gs1.normGtin('8470006991545'), '08470006991545'); // EAN-13 → GTIN-14
  assert.equal(gs1.normGtin('08470006991545'), '08470006991545'); // already 14
  assert.equal(gs1.normGtin('  847 000 699 1545 '), '08470006991545');
  const it = db.createItem({ raw: 'e1', box_key: 'ek1', gtin: '08470006991545', serial: 'E1' }, 1);
  db.upsertProduct(gs1.normGtin('8470006991545'), { nombre: 'Ibuprofeno EAN' }); // catalogue lists EAN-13
  assert.equal(db.getItem(it.id).nombre, 'Ibuprofeno EAN');
});

test('CN fallback resolves the name when the GTIN is not catalogued', () => {
  const it = db.createItem({ raw: 'cnr', box_key: 'cnk', gtin: '09999999999999', serial: 'C1', cn: '654321' }, 1);
  db.upsertProduct('05555555555555', { cn: '654321', nombre: 'Resuelto por CN' });
  assert.equal(db.getItem(it.id).nombre, 'Resuelto por CN');
});

test('setUsed archives; listItems by status; counts', () => {
  const before = db.counts();
  const it = db.createItem({ raw: 'r2', box_key: 'k2', gtin: '05000000000031', serial: 'S2' }, 1);
  assert.equal(db.counts().activo, before.activo + 1);
  db.setUsed(it.id, true);
  assert.equal(db.getItem(it.id).status, 'utilizado');
  assert.ok(!db.listItems('activo').some(x => x.id === it.id));
  assert.ok(db.listItems('utilizado').some(x => x.id === it.id));
  db.setUsed(it.id, false);
  assert.equal(db.getItem(it.id).status, 'activo');
});

test('createManyItems bulk + product import', () => {
  const rows = [
    { raw: 'b1', box_key: 'bk1', gtin: '05000000000048', serial: 'X1' },
    { raw: 'b2', box_key: 'bk2', gtin: '05000000000048', serial: 'X2' },
  ];
  const created = db.createManyItems(rows, 1);
  assert.equal(created.length, 2);
  const n = db.importProducts([{ gtin: '05000000000048', nombre: 'Paracetamol 1g' }]);
  assert.equal(n, 1);
  assert.equal(db.getItem(created[0].id).nombre, 'Paracetamol 1g', 'both boxes share the medication name');
});

test('settings defaults + persistence; cart per user', () => {
  const s = db.getSettings();
  assert.equal(s.list_dm_size, 100);
  assert.equal(s.card_dm_size, 200);
  const s2 = db.saveSettings({ card_dm_size: 180 }, 1);
  assert.equal(s2.card_dm_size, 180);
  const it = db.createItem({ raw: 'c1', box_key: 'ck1', gtin: 'g', serial: 's' }, 1);
  db.cartAdd(9, it.id);
  assert.deepEqual(db.cartIds(9), [it.id]);
  assert.equal(db.cartIds(8).length, 0, 'per-user');
  db.deleteItem(it.id);
  assert.ok(!db.cartIds(9).includes(it.id), 'delete detaches from cart');
});
