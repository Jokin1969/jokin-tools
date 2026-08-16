const { test, before, after } = require('node:test');
const assert = require('node:assert');
const os = require('os');
const path = require('path');
const fs = require('fs');
const http = require('http');

// Isolate all three databases in a temp dir BEFORE requiring the modules.
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'asig-test-'));
process.env.QR_TIS_DB_PATH = path.join(dir, 'qr.db');
process.env.DM_DB_PATH = path.join(dir, 'dm.db');
process.env.ASIG_DB_PATH = path.join(dir, 'asig.db');

const express = require('express');
const qrDb = require('../apps/qr-tis/db');
const dmDb = require('../apps/datamatrix/db');
const gs1 = require('../apps/datamatrix/gs1');
const router = require('../apps/asignacion/routes');

// A tiny app that injects a logged-in user and mounts the real router.
const app = express();
app.use((req, res, next) => { req.user = { id: 1, email: 't@e', name: 'Tester' }; next(); });
app.use('/asignacion', router);

let server, base;
before(async () => {
  await new Promise(res => { server = app.listen(0, res); });
  base = `http://127.0.0.1:${server.address().port}/asignacion/api`;
});
after(() => { try { server.close(); } catch { } });

async function call(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const r = await fetch(base + path, opts);
  const data = await r.json().catch(() => ({}));
  return { status: r.status, data };
}

const GTIN = '08470006991545';
let personId, otherId, box1, box2;

test('setup: seed a person and two boxes', () => {
  personId = qrDb.createPerson({ pharmacy_no: '11111', nombre: 'Ana', apellidos: 'Pérez', tis: '00011111' }, 1).id;
  otherId = qrDb.createPerson({ pharmacy_no: '22222', nombre: 'Luis', apellidos: 'Gómez', tis: '00022222' }, 1).id;
  box1 = dmDb.createItem({ raw: 'R-BOX1', box_key: 'BK1', gtin: GTIN, serial: 'S1' }, 1).id;
  box2 = dmDb.createItem({ raw: 'R-BOX2', box_key: 'BK2', gtin: GTIN, serial: 'S2' }, 1).id;
  dmDb.upsertProduct(GTIN, { nombre: 'Ibuprofeno 600' });
});

test('people search finds the person (from qr-tis)', async () => {
  const { status, data } = await call('GET', '/people?q=' + encodeURIComponent('Ana'));
  assert.equal(status, 200);
  assert.ok(data.items.some(p => p.id === personId));
});

test('medications list comes from datamatrix', async () => {
  const { data } = await call('GET', '/medications?q=Ibupro');
  assert.ok(data.items.some(m => m.gtin === GTIN && m.nombre === 'Ibuprofeno 600'));
});

test('add a medication to the plan (must exist in DM)', async () => {
  const bad = await call('POST', `/person/${personId}/plan`, { gtin: '09999999999999', qty: 1 });
  assert.equal(bad.status, 400, 'unknown medication rejected');
  const ok = await call('POST', `/person/${personId}/plan`, { gtin: GTIN, qty: 2 });
  assert.equal(ok.status, 200);
  assert.equal(ok.data.plan.length, 1);
  assert.equal(ok.data.plan[0].qty, 2);
});

test('preassign a box → reserved, box stays in stock (pre-asignada)', async () => {
  const { status, data } = await call('POST', `/person/${personId}/preassign`, { item_id: box1, ym: '2026-08' });
  assert.equal(status, 200);
  assert.equal(data.lines.length, 1);
  assert.equal(data.lines[0].state, 'preasignada');
  assert.equal(data.lines[0].box.asig_state, 'preasignada');
  assert.equal(data.progress.pre_total, 1);
  // Reflected in the DM database, still activo.
  const it = dmDb.getItem(box1);
  assert.equal(it.status, 'activo');
  assert.equal(it.assignee_id, personId);
});

test('a reserved box cannot be pre-assigned to another person', async () => {
  const { status, data } = await call('POST', `/person/${otherId}/preassign`, { item_id: box1, ym: '2026-08' });
  assert.equal(status, 400);
  assert.match(data.error, /pre-asignada/i);
});

test('assign for real → box utilizado, line asignada, greyed out', async () => {
  const ficha = (await call('GET', `/person/${personId}/ficha?ym=2026-08`)).data;
  const lineId = ficha.lines[0].id;
  const { status, data } = await call('POST', `/line/${lineId}/assign`);
  assert.equal(status, 200);
  assert.equal(data.lines[0].state, 'asignada');
  assert.equal(data.progress.asignada_total, 1);
  assert.equal(dmDb.getItem(box1).status, 'utilizado');
  assert.equal(dmDb.getItem(box1).assignee_id, personId, 'assignee kept');
});

test('unassign reverts box to stock but keeps it pre-asignada', async () => {
  const ficha = (await call('GET', `/person/${personId}/ficha?ym=2026-08`)).data;
  const lineId = ficha.lines[0].id;
  const { data } = await call('POST', `/line/${lineId}/unassign`);
  assert.equal(data.lines[0].state, 'preasignada');
  assert.equal(dmDb.getItem(box1).status, 'activo');
  assert.equal(dmDb.getItem(box1).assignee_id, personId);
});

test('preassign by scanning a NEW raw code creates the box in DM as pre-asignada', async () => {
  const raw = '01' + '08470006991545' + '21NEW-999' + gs1.GS + '17261130';
  const before = dmDb.counts().activo;
  const { status, data } = await call('POST', `/person/${personId}/preassign`, { raw, ym: '2026-08' });
  assert.equal(status, 200);
  assert.equal(data.lines.length, 2, 'second box attached');
  assert.equal(dmDb.counts().activo, before + 1, 'a new box was created in DM');
  const created = dmDb.findByKey('08470006991545|NEW-999');
  assert.ok(created && created.assignee_id === personId, 'new box reserved for the person');
});

test('remove a line releases the reservation (and returns a used box to stock)', async () => {
  // Assign box1 again, then remove its line → should return to activo + no assignee.
  let ficha = (await call('GET', `/person/${personId}/ficha?ym=2026-08`)).data;
  const line1 = ficha.lines.find(l => l.item_id === box1);
  await call('POST', `/line/${line1.id}/assign`);
  assert.equal(dmDb.getItem(box1).status, 'utilizado');
  const { data } = await call('DELETE', `/line/${line1.id}`);
  assert.ok(!data.lines.some(l => l.item_id === box1), 'line removed');
  const it = dmDb.getItem(box1);
  assert.equal(it.status, 'activo', 'returned to inventory');
  assert.equal(it.assignee_id, null, 'reservation cleared');
});

test('overview lists the person with their plan and month status', async () => {
  const { data } = await call('GET', '/overview');
  const row = data.items.find(r => r.person.id === personId);
  assert.ok(row, 'person present in overview');
  assert.equal(row.plan_count, 1);
  assert.equal(row.planned_total, 2);
  assert.equal(row.has_month_period, true);
});

test('release date: schedule, bucket due vs upcoming, and clear on assign', async () => {
  const bPast = dmDb.createItem({ raw: 'R-PAST', box_key: 'BKP', gtin: GTIN, serial: 'P1' }, 1).id;
  const bFut = dmDb.createItem({ raw: 'R-FUT', box_key: 'BKF', gtin: GTIN, serial: 'F1' }, 1).id;
  await call('POST', `/person/${otherId}/preassign`, { item_id: bPast, ym: '2026-09' });
  await call('POST', `/person/${otherId}/preassign`, { item_id: bFut, ym: '2026-09' });
  let ficha = (await call('GET', `/person/${otherId}/ficha?ym=2026-09`)).data;
  const lPast = ficha.lines.find(l => l.item_id === bPast).id;
  const lFut = ficha.lines.find(l => l.item_id === bFut).id;

  // Past date → ready ("lista"); far-future date → scheduled ("programada").
  let r = await call('PUT', `/line/${lPast}/release`, { date: '2020-01-01' });
  assert.equal(r.status, 200);
  assert.equal(r.data.lines.find(l => l.item_id === bPast).release_state, 'lista');
  r = await call('PUT', `/line/${lFut}/release`, { date: '2999-12-31' });
  const lf = r.data.lines.find(l => l.item_id === bFut);
  assert.equal(lf.release_state, 'programada');
  assert.ok(lf.release_days > 0);

  // Notifications bucket them correctly.
  let nt = (await call('GET', '/notifications')).data;
  assert.ok(nt.due.some(e => e.line_id === lPast), 'past date is due');
  assert.ok(nt.upcoming.some(e => e.line_id === lFut), 'future date is upcoming');

  // Overview surfaces the ready count for that person.
  const ov = (await call('GET', '/overview')).data;
  assert.ok((ov.items.find(x => x.person.id === otherId) || {}).ready_count >= 1);

  // Assigning the ready box removes it from the notifications.
  await call('POST', `/line/${lPast}/assign`);
  nt = (await call('GET', '/notifications')).data;
  assert.ok(!nt.due.some(e => e.line_id === lPast), 'assigned box no longer notified');
});

test('invalid release date rejected; clearing resets the state', async () => {
  const b = dmDb.createItem({ raw: 'R-CLR', box_key: 'BKC', gtin: GTIN, serial: 'C9' }, 1).id;
  await call('POST', `/person/${otherId}/preassign`, { item_id: b, ym: '2026-09' });
  const ficha = (await call('GET', `/person/${otherId}/ficha?ym=2026-09`)).data;
  const lid = ficha.lines.find(l => l.item_id === b).id;
  const bad = await call('PUT', `/line/${lid}/release`, { date: '2026/09/01' });
  assert.equal(bad.status, 400, 'wrong format rejected');
  await call('PUT', `/line/${lid}/release`, { date: '2027-01-15' });
  const cleared = (await call('PUT', `/line/${lid}/release`, { date: '' })).data;
  const l = cleared.lines.find(x => x.item_id === b);
  assert.equal(l.release_at, null);
  assert.equal(l.release_state, null);
});

test('period close / reopen toggles status', async () => {
  const ficha = (await call('GET', `/person/${personId}/ficha?ym=2026-08`)).data;
  const perId = ficha.period.id;
  assert.ok(perId, 'period exists');
  const closed = (await call('POST', `/period/${perId}/close`)).data;
  assert.equal(closed.period.status, 'cerrado');
  const reopened = (await call('POST', `/period/${perId}/reopen`)).data;
  assert.equal(reopened.period.status, 'abierto');
});
