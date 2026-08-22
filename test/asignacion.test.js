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
process.env.DB_PATH = path.join(dir, 'auth.db');   // isolate the auth store too

const express = require('express');
const qrDb = require('../apps/qr-tis/db');
const dmDb = require('../apps/datamatrix/db');
const gs1 = require('../apps/datamatrix/gs1');
const authStore = require('../apps/auth/store');
// Seed the auth users the router keys off: 1 & 2 can access Asignación, 3 cannot.
authStore.createUser({ email: 'u1@example.com', name: 'Uno',  password: 'password1', apps: ['asignacion'] });          // id 1
authStore.createUser({ email: 'u2@example.com', name: 'Dos',  password: 'password1', apps: ['asignacion'] });          // id 2
authStore.createUser({ email: 'u3@example.com', name: 'Tres', password: 'password1', apps: ['qr-tis'] });              // id 3 (sin Asignación)
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

test('CIMA lookup endpoint is wired and validates the Código Nacional', async () => {
  // Too-short CN → 400 without touching the network (route regex requires digits).
  const r = await call('GET', '/cima/cn/1');
  assert.equal(r.status, 400);
  assert.equal(r.data.offline, false);
});

test('add a medication to the plan (must exist in DM)', async () => {
  const bad = await call('POST', `/person/${personId}/plan`, { gtin: '09999999999999', qty: 1 });
  assert.equal(bad.status, 400, 'unknown medication rejected');
  const ok = await call('POST', `/person/${personId}/plan`, { gtin: GTIN, qty: 2 });
  assert.equal(ok.status, 200);
  assert.equal(ok.data.plan.length, 1);
  assert.equal(ok.data.plan[0].qty, 2);
});

test('plan CN-only: add a medication by Código Nacional before any Data Matrix, then link a box', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '80001', nombre: 'Noa', apellidos: 'Cea', tis: '00080001' }, 1).id;
  // Adding by CN requires a name.
  assert.equal((await call('POST', `/person/${pid}/plan`, { cn: '715000' })).status, 400);
  // Add the medication with only its national code (no GTIN / no box yet).
  const added = (await call('POST', `/person/${pid}/plan`, { cn: '715000', nombre: 'Ibuprofeno 600', barcode: '8470007150008', qty: 2 })).data.plan;
  const med = added.find(m => m.cn === '715000');
  assert.ok(med, 'CN-only med is in the plan');
  assert.equal(med.cn_only, true);
  assert.equal(med.gtin, null);
  assert.equal(med.nombre, 'Ibuprofeno 600');
  assert.equal(med.available, 0, 'no compatible box yet');

  // A real box with that CN appears in stock → the plan med now has a compatible box.
  const cnBox = dmDb.createItem({ raw: 'R-CN715', box_key: 'CN715', gtin: '08470007150009', serial: 'C1', cn: '715000' }, 1).id;
  const planNow = (await call('GET', `/person/${pid}/plan`)).data.plan;
  assert.equal(planNow.find(m => m.cn === '715000').available, 1, 'available-by-CN finds it');

  // Link that box to the plan med → it becomes pre-asignada AND the med graduates to a GTIN.
  const ficha = (await call('POST', `/person/${pid}/preassign`, { item_id: cnBox, plan_id: med.id, ym: '2026-08' })).data;
  assert.ok(ficha.lines.some(l => l.item_id === cnBox && l.state === 'preasignada'), 'box pre-assigned');
  const graduated = ficha.plan.find(m => m.id === med.id);
  assert.equal(graduated.cn_only, false, 'CN-only med reconciled to a GTIN once linked');
  assert.equal(graduated.gtin, '08470007150009');
});

test('edit a CN-only plan medication (name / CN / barcode) without deleting', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '80060', nombre: 'Edi', apellidos: 'Tar', tis: '00080060' }, 1).id;
  const med = (await call('POST', `/person/${pid}/plan`, { cn: '885442', nombre: 'Ixia mal', barcode: '8470008854424' })).data.plan.find(m => m.cn === '885442');
  // Fix the name and change the code to another valid CN + its barcode.
  const up = (await call('PATCH', `/plan/${med.id}`, { nombre: 'Ixia 10 mg', cn: '715000', barcode: '8470007150008' })).data.plan.find(m => m.id === med.id);
  assert.equal(up.nombre, 'Ixia 10 mg');
  assert.equal(up.cn, '715000');
  // An inconsistent CN/barcode edit is rejected.
  assert.equal((await call('PATCH', `/plan/${med.id}`, { cn: '65498', barcode: '8470008854424' })).status, 400);
  // Duplicate CN in the same person's plan is rejected.
  const other = (await call('POST', `/person/${pid}/plan`, { cn: '999001', nombre: 'Otro' })).data.plan.find(m => m.cn === '999001');
  assert.equal((await call('PATCH', `/plan/${other.id}`, { cn: '715000' })).status, 400);
});

test('plan CN/barcode cross-check: rejects an inconsistent pair, derives CN from barcode', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '80050', nombre: 'Cruz', apellidos: 'Check', tis: '00080050' }, 1).id;
  // CN 65498 with the barcode of CN 885442 → inconsistent → rejected.
  const bad = await call('POST', `/person/${pid}/plan`, { cn: '65498', nombre: 'Ixia', barcode: '8470008854424' });
  assert.equal(bad.status, 400);
  assert.match(bad.data.error, /885442/);   // tells you the barcode's real CN
  // A 14-digit GTIN pasted as barcode is normalised, and matches CN 885442.
  const ok = (await call('POST', `/person/${pid}/plan`, { cn: '885442', nombre: 'Ixia 10 mg', barcode: '08470008854424' })).data.plan;
  assert.ok(ok.find(m => m.cn === '885442'));
  // Barcode only (no CN) → the CN is derived from it.
  const pid2 = qrDb.createPerson({ pharmacy_no: '80051', nombre: 'Der', apellidos: 'Iva', tis: '00080051' }, 1).id;
  const derived = (await call('POST', `/person/${pid2}/plan`, { nombre: 'Ixia 10 mg', barcode: '8470008854424' })).data.plan;
  assert.ok(derived.find(m => m.cn === '885442'), 'CN derived from the barcode');
});

test('assign-precinto: marca asignada en Salud sin caja, cuenta y se revierte', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '80070', nombre: 'Pre', apellidos: 'Cinto', tis: '00080070' }, 1).id;
  const med = (await call('POST', `/person/${pid}/plan`, { cn: '715000', nombre: 'Ibuprofeno 600', barcode: '8470007150008', qty: 2 })).data.plan.find(m => m.cn === '715000');
  // Manual assign by precinto, capturing the next release date.
  const r = await call('POST', `/person/${pid}/assign-precinto`, { plan_id: med.id, ym: '2026-08', next_release_at: '2026-09-15' });
  assert.equal(r.status, 200);
  const pm = r.data.plan.find(m => m.id === med.id);
  assert.equal(pm.boxes, 0, 'no real box in the ficha');
  assert.equal(pm.precinto, 1);
  assert.equal(pm.asignada, 1, 'precinto counts as assigned');
  assert.equal(pm.release_at, '2026-09-15', 'next release captured on the medication');
  assert.equal(r.data.progress.asignada_total, 1, 'period progress includes the precinto');
  assert.equal(r.data.precintos.length, 1);
  assert.equal(r.data.precintos[0].plan_id, med.id);
  // A second unit → 2 assigned.
  const r2 = await call('POST', `/person/${pid}/assign-precinto`, { plan_id: med.id, ym: '2026-08' });
  assert.equal(r2.data.plan.find(m => m.id === med.id).precinto, 2);
  // Revert the first one.
  const rev = await call('DELETE', `/precinto/${r.data.precintos[0].id}`);
  assert.equal(rev.status, 200);
  assert.equal(rev.data.plan.find(m => m.id === med.id).precinto, 1);
});

test('scan: precinto (código de barras) marca asignada y avanza la fecha', async () => {
  const asigDb = require('../apps/asignacion/db');
  const pid = qrDb.createPerson({ pharmacy_no: '80071', nombre: 'Esc', apellidos: 'Aner', tis: '00080071' }, 1).id;
  const med = (await call('POST', `/person/${pid}/plan`, { cn: '715000', nombre: 'Ibuprofeno 600', barcode: '8470007150008', qty: 2 })).data.plan.find(m => m.cn === '715000');
  await call('PUT', `/plan/${med.id}/release`, { date: '2026-08-20', advance_days: 15 });
  // Scanner types the EAN-13 precinto + Enter.
  const r = await call('POST', `/person/${pid}/scan`, { code: '8470007150008', ym: '2026-08' });
  assert.equal(r.status, 200);
  assert.equal(r.data.mode, 'precinto');
  assert.equal(r.data.med.cn, '715000');
  assert.equal(r.data.next_release_at, asigDb.nextMonthSameDay('2026-08-20'));
  assert.equal(r.data.next_release_at, '2026-09-20');
  const pm = r.data.ficha.plan.find(m => m.id === med.id);
  assert.equal(pm.precinto, 1);
  assert.equal(pm.asignada, 1);
  assert.equal(pm.release_at, '2026-09-20', 'recurring date advanced to same day next month');
});

test('scan: Data Matrix asocia y asigna la caja directamente', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '80072', nombre: 'Dema', apellidos: 'Trix', tis: '00080072' }, 1).id;
  await call('POST', `/person/${pid}/plan`, { gtin: GTIN, qty: 1 });
  const raw = '01' + '08470006991545' + '21SCAN-DM1' + gs1.GS + '17261130';
  const r = await call('POST', `/person/${pid}/scan`, { code: raw, ym: '2026-08' });
  assert.equal(r.status, 200);
  assert.equal(r.data.mode, 'dm');
  const created = dmDb.findByKey('08470006991545|SCAN-DM1');
  assert.ok(created && created.assignee_id === pid, 'box created and reserved for the person');
  assert.equal(created.status, 'utilizado', 'box marked used (assigned)');
  const line = r.data.ficha.lines.find(l => l.item_id === created.id);
  assert.ok(line && line.state === 'asignada', 'line is asignada');
  const pm = r.data.ficha.plan.find(m => m.gtin === GTIN);
  assert.equal(pm.boxes, 1);
  assert.equal(pm.asignada, 1);
});

test('scan: un código que no está en el plan responde 409 nomatch', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '80073', nombre: 'Sin', apellidos: 'Plan', tis: '00080073' }, 1).id;
  // Person has no plan → scanning a valid precinto barcode → 409 nomatch.
  const r = await call('POST', `/person/${pid}/scan`, { code: '8470007150008', ym: '2026-08' });
  assert.equal(r.status, 409);
  assert.equal(r.data.nomatch, true);
});

test('CIMA foto: ETag revalida y refresca la imagen (thumbnail → full)', async () => {
  const thumb = Buffer.from('THUMB-small');
  dmDb.cimaCachePut('991234', { nombre: 'Foto Test', foto_caja: thumb, foto_caja_url: 'http://x/thumbnails/a.jpg' });
  const r1 = await fetch(base + '/cima/foto/991234/caja');
  assert.equal(r1.status, 200);
  const etag1 = r1.headers.get('etag');
  assert.ok(etag1, 'envía un ETag');
  assert.match(r1.headers.get('cache-control') || '', /no-cache/);
  // Conditional GET con el mismo ETag → 304.
  const r304 = await fetch(base + '/cima/foto/991234/caja', { headers: { 'If-None-Match': etag1 } });
  assert.equal(r304.status, 304);
  // Reemplazar por una imagen más grande (full) → el validador antiguo ya no vale.
  dmDb.cimaCachePut('991234', { foto_caja: Buffer.from('FULL-image-much-larger-payload-bytes') });
  const r2 = await fetch(base + '/cima/foto/991234/caja', { headers: { 'If-None-Match': etag1 } });
  assert.equal(r2.status, 200, 'validador obsoleto → se envía la nueva imagen');
  assert.notEqual(r2.headers.get('etag'), etag1, 'el ETag cambia con la nueva imagen');
});

test('precintos (pegado): agrega DM+precinto, marca/escanea/revierte, foto y PDF', async () => {
  const cima = require('../apps/datamatrix/cima');
  const ym = '2026-07';
  const pid = qrDb.createPerson({ pharmacy_no: '80090', nombre: 'Peg', apellidos: 'Ado', tis: '00080090' }, 1).id;
  // A catalogued med + a box, assigned through the normal flow (→ one physical precinto).
  await call('POST', `/person/${pid}/plan`, { gtin: GTIN, qty: 1 });
  const boxX = dmDb.createItem({ raw: 'R-PEG1', box_key: 'PEG1', gtin: GTIN, serial: 'PG1', cn: '699154' }, 1).id;
  await call('POST', `/person/${pid}/preassign`, { item_id: boxX, ym });
  const ficha = (await call('GET', `/person/${pid}/ficha?ym=${ym}`)).data;
  const lineX = ficha.lines.find(l => l.item_id === boxX);
  await call('POST', `/line/${lineX.id}/assign`, { next_release_at: '' });
  // A precinto med (no box) → another physical precinto.
  const med = (await call('POST', `/person/${pid}/plan`, { cn: '715000', nombre: 'Ibuprofeno 600', barcode: '8470007150008', qty: 1 })).data.plan.find(m => m.cn === '715000');
  await call('POST', `/person/${pid}/assign-precinto`, { plan_id: med.id, ym });

  // Sticker view: 2 assigned, both pending, grouped by medication.
  let stk = (await call('GET', `/stickers?ym=${ym}`)).data;
  assert.equal(stk.totals.total, 2);
  assert.equal(stk.totals.por_pegar, 2);
  assert.equal(stk.totals.pegados, 0);
  assert.equal(stk.groups.length, 2, 'agrupados por medicamento');

  // Mark the Ibuprofeno group as stuck (manual/bulk).
  const grpIbu = stk.groups.find(g => g.cn === '715000');
  stk = (await call('POST', '/stickers/mark-med', { ym, key: grpIbu.key })).data;
  assert.equal(stk.marked, 1);
  assert.equal(stk.totals.pegados, 1);
  assert.equal(stk.totals.por_pegar, 1);

  // Scan the box precinto's barcode → cotejo marks it stuck.
  const bcBox = cima.barcodeFromCn('699154');
  const scan = await call('POST', '/stickers/scan', { ym, code: bcBox });
  assert.equal(scan.status, 200);
  assert.equal(scan.data.ok, true);
  assert.equal(scan.data.totals.por_pegar, 0);
  // Nothing left of that med → 409 nomatch.
  assert.equal((await call('POST', '/stickers/scan', { ym, code: bcBox })).status, 409);

  // Photo evidence → stored and retrievable.
  const png = 'data:image/png;base64,' + Buffer.from('FAKE-PNG-BYTES').toString('base64');
  const ev = await call('POST', '/stickers/evidencia', { ym, photo: png });
  assert.equal(ev.status, 200);
  assert.ok(ev.data.evidencia_id);
  const evImg = await fetch(base + '/stickers/evidencia/' + ev.data.evidencia_id);
  assert.equal(evImg.status, 200);

  // Revert one precinto → back to pending.
  const revItem = grpIbu.items[0];
  stk = (await call('POST', '/stickers/unmark', { ym, items: [{ source: revItem.source, id: revItem.id }] })).data;
  assert.equal(stk.totals.por_pegar, 1);

  // PDF endpoint returns a real PDF.
  const pdf = await fetch(base + '/stickers/pdf?ym=' + ym);
  assert.equal(pdf.status, 200);
  assert.equal(pdf.headers.get('content-type'), 'application/pdf');
  const bytes = Buffer.from(await pdf.arrayBuffer());
  assert.ok(bytes.length > 500 && bytes.slice(0, 4).toString() === '%PDF', 'es un PDF');

  // The month shows up in the selector.
  assert.ok(stk.months.some(m => m.ym === ym));
});

test('precintos: residencia (grupo QR·TIS) + opciones de impresión del PDF', async () => {
  const ym = '2026-06';
  const g1 = qrDb.createPerson({ pharmacy_no: '80095', nombre: 'Rosa', apellidos: 'Uno', tis: '00080095', group_name: 'Residencia Sol' }, 1).id;
  const g2 = qrDb.createPerson({ pharmacy_no: '80096', nombre: 'Tere', apellidos: 'Dos', tis: '00080096', group_name: 'Residencia Luna' }, 1).id;
  for (const pid of [g1, g2]) {
    const med = (await call('POST', `/person/${pid}/plan`, { cn: '715000', nombre: 'Ibuprofeno 600', barcode: '8470007150008', qty: 1 })).data.plan.find(m => m.cn === '715000');
    await call('POST', `/person/${pid}/assign-precinto`, { plan_id: med.id, ym });
  }
  const stk = (await call('GET', `/stickers?ym=${ym}`)).data;
  // Items carry the residence (from the person's QR·TIS group).
  const items = stk.groups.flatMap(g => g.items);
  assert.ok(items.some(i => i.residencia === 'Residencia Sol'));
  assert.ok(items.some(i => i.residencia === 'Residencia Luna'));
  // PDF ordered by residence, one page per group, restricted to one residence.
  const pdf = await fetch(base + `/stickers/pdf?ym=${ym}&filter=all&order=residencia&sub=person&pagebreak=1&groups=${encodeURIComponent(JSON.stringify(['Residencia Sol']))}`);
  assert.equal(pdf.status, 200);
  assert.equal(pdf.headers.get('content-type'), 'application/pdf');
  const bytes = Buffer.from(await pdf.arrayBuffer());
  assert.ok(bytes.length > 500 && bytes.slice(0, 4).toString() === '%PDF');
});

test('notas: persona y precinto (upsert + borrar) aparecen en overview y stickers', async () => {
  const ym = '2026-05';
  const pid = qrDb.createPerson({ pharmacy_no: '80097', nombre: 'Nota', apellidos: 'Test', tis: '00080097' }, 1).id;
  const med = (await call('POST', `/person/${pid}/plan`, { cn: '715000', nombre: 'Ibuprofeno 600', barcode: '8470007150008', qty: 1 })).data.plan.find(m => m.cn === '715000');
  await call('POST', `/person/${pid}/assign-precinto`, { plan_id: med.id, ym });
  // Person note.
  const pn = await call('PUT', `/note/person/${pid}`, { text: 'Alérgica a X', color: '#FBCFE8' });
  assert.equal(pn.status, 200);
  assert.equal(pn.data.note.text, 'Alérgica a X');
  const ov = (await call('GET', '/overview')).data.items.find(r => r.person.id === pid);
  assert.ok(ov && ov.note && ov.note.text === 'Alérgica a X', 'person note in overview');
  // Sticker note (on the precinto row).
  const stk = (await call('GET', `/stickers?ym=${ym}`)).data;
  const item = stk.groups.flatMap(g => g.items)[0];
  const sn = await call('PUT', `/note/sticker/${item.source}/${item.id}`, { text: 'Precinto dudoso' });
  assert.equal(sn.status, 200);
  const stk2 = (await call('GET', `/stickers?ym=${ym}`)).data;
  const item2 = stk2.groups.flatMap(g => g.items).find(i => i.source === item.source && i.id === item.id);
  assert.ok(item2.note && item2.note.text === 'Precinto dudoso', 'sticker note in payload');
  // Empty text clears the note.
  await call('PUT', `/note/person/${pid}`, { text: '' });
  const ov2 = (await call('GET', '/overview')).data.items.find(r => r.person.id === pid);
  assert.equal(ov2.note, null, 'empty text clears the person note');
});

test('importar medicación por CN: resuelve por TIS, añade al plan y avisa de no encontrados', async () => {
  const a = qrDb.createPerson({ pharmacy_no: '80200', nombre: 'Imp', apellidos: 'Ort', tis: '00080200' }, 1).id;
  const b = qrDb.createPerson({ pharmacy_no: '80201', nombre: 'Dos', apellidos: 'Imp', tis: '00080201' }, 1).id;
  const rows = [
    { person: '00080200', cns: ['715000', '885442'] },
    { person: '00080201', cns: ['659432'] },
    { person: '00089999', cns: ['715000'] },   // TIS inexistente → error
    { person: '00080200', cns: ['xx'] },        // sin CN válido → error
  ];
  const r = (await call('POST', '/plan/import', { by: 'tis', qty: 2, rows })).data;
  assert.equal(r.ok, true);
  assert.equal(r.people, 2, 'dos personas válidas');
  assert.equal(r.added, 3, 'tres medicamentos añadidos');
  assert.ok(r.errors.some(e => /no encontrada/i.test(e.error)), 'avisa de la persona inexistente');
  assert.ok(r.errors.some(e => /Códigos Nacionales/i.test(e.error)), 'avisa de la fila sin CN válido');
  // Detalle de los CN sin datos de CIMA (aquí CIMA está offline → todos figuran).
  assert.ok(Array.isArray(r.cima.missingCns), 'cima.missingCns es una lista');
  const m715 = r.cima.missingCns.find(m => m.cn === '715000');
  assert.ok(m715, 'lista los CN sin datos de CIMA (con su código)');
  assert.ok(m715.people >= 1, 'indica en cuántas personas está cada CN sin datos');
  assert.ok(m715.barcode === null || typeof m715.barcode === 'string', 'incluye el código de barras derivado (o null)');
  // El plan de la persona A tiene los dos CN, con qty 2.
  const planA = (await call('GET', `/person/${a}/plan`)).data.plan;
  const ibu = planA.find(m => m.cn === '715000');
  assert.ok(ibu, 'CN 715000 en el plan de A');
  assert.equal(ibu.qty, 2);
  assert.ok(planA.some(m => m.cn === '885442'));
  // Reimportar el mismo CN lo actualiza (no duplica).
  const r2 = (await call('POST', '/plan/import', { by: 'tis', qty: 3, rows: [{ person: '00080200', cns: ['715000'] }] })).data;
  assert.equal(r2.updated, 1);
  assert.equal(r2.added, 0);
  const planA2 = (await call('GET', `/person/${a}/plan`)).data.plan;
  assert.equal(planA2.filter(m => m.cn === '715000').length, 1, 'no se duplica');
  assert.equal(planA2.find(m => m.cn === '715000').qty, 3, 'qty actualizada');
  // Persona B por TIS.
  assert.ok((await call('GET', `/person/${b}/plan`)).data.plan.some(m => m.cn === '659432'));

  // Sin ceros a la izquierda: el TIS 00080200 debe resolver aunque se pase "80200".
  const rz = (await call('POST', '/plan/import', { by: 'tis', qty: 1, rows: [{ person: '80200', cns: ['998001'] }] })).data;
  assert.equal(rz.people, 1, 'resuelve el TIS sin ceros a la izquierda');
  assert.equal(rz.added, 1);
  assert.ok((await call('GET', `/person/${a}/plan`)).data.plan.some(m => m.cn === '998001'));
  // Y por Nº de farmacia sin ceros: "80200" ~ pharmacy "80200" (5 cifras) para otra persona.
  const c = qrDb.createPerson({ pharmacy_no: '07001', nombre: 'Far', apellidos: 'Zero', tis: '00070001' }, 1).id;
  const rp = (await call('POST', '/plan/import', { by: 'pharmacy', qty: 1, rows: [{ person: '7001', cns: ['715000'] }] })).data;
  assert.equal(rp.people, 1, 'resuelve el Nº de farmacia 07001 pasando "7001"');
  assert.ok((await call('GET', `/person/${c}/plan`)).data.plan.some(m => m.cn === '715000'));
});

test('importar: CN no reconocido por CIMA deja una nota en la persona', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '80500', nombre: 'Note', apellidos: 'Cima', tis: '00080500' }, 1).id;
  // CIMA está offline en el sandbox → 715000 se añade como "Medicamento CN 715000".
  const r = (await call('POST', '/plan/import', { by: 'tis', qty: 1, rows: [{ person: '00080500', cns: ['715000'] }] })).data;
  assert.ok(r.noted >= 1, 'informa de las notas añadidas');
  const note = asigDb.getEntNote('person', pid);
  assert.ok(note && /no ha sido reconocido/i.test(note.text), 'la persona tiene una nota de CN no reconocido');
  assert.ok(note.text.includes('715000'), 'la nota indica el CN concreto');
});

test('overview: incluye med_search para poder filtrar por medicamento (CN/nombre/barcode)', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '80600', nombre: 'Med', apellidos: 'Search', tis: '00080600' }, 1).id;
  await call('POST', `/person/${pid}/plan`, { cn: '123456', nombre: 'IBUPROFENO MARCA X', qty: 1 });
  const row = (await call('GET', '/overview')).data.items.find(x => x.person.id === pid);
  assert.ok(row && typeof row.med_search === 'string', 'cada fila trae med_search');
  assert.ok(/123456/.test(row.med_search) && /IBUPROFENO/i.test(row.med_search), 'med_search contiene CN y nombre');
});

test('importar medicación: si el identificador elegido falla, busca en QR (TIS) por el otro y crea el plan', async () => {
  // Persona con TIS y Nº de farmacia que "strippean" a valores distintos.
  const d = qrDb.createPerson({ pharmacy_no: '55501', nombre: 'Cruz', apellidos: 'Ada', tis: '00061234' }, 1).id;
  // No tiene plan todavía.
  assert.equal(asigDb.personMedSummary(d).has_plan, false, 'sin plan al empezar');
  // Importando «por TIS», pero pasando su Nº de farmacia (55501): debe resolver por el otro identificador.
  const r1 = (await call('POST', '/plan/import', { by: 'tis', qty: 1, rows: [{ person: '55501', cns: ['715000'] }] })).data;
  assert.equal(r1.people, 1, 'resuelve por Nº de farmacia aunque el modo sea TIS');
  assert.equal(r1.added, 1);
  assert.equal(asigDb.personMedSummary(d).has_plan, true, 'ahora tiene plan');
  assert.ok((await call('GET', `/person/${d}/plan`)).data.plan.some(m => m.cn === '715000'));
  // Importando «por Nº de farmacia», pero pasando su TIS (61234 sin ceros): resuelve por el otro.
  const r2 = (await call('POST', '/plan/import', { by: 'pharmacy', qty: 1, rows: [{ person: '61234', cns: ['885442'] }] })).data;
  assert.equal(r2.people, 1, 'resuelve por TIS aunque el modo sea Nº de farmacia');
  assert.ok((await call('GET', `/person/${d}/plan`)).data.plan.some(m => m.cn === '885442'));
});

test('linking a mismatched box warns (409) but can be forced', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '80002', nombre: 'Iker', apellidos: 'Dao', tis: '00080002' }, 1).id;
  const med = (await call('POST', `/person/${pid}/plan`, { cn: '999999', nombre: 'Medicamento X', qty: 1 })).data.plan.find(m => m.cn === '999999');
  // A box whose CN/GTIN doesn't match the plan med.
  const wrong = dmDb.createItem({ raw: 'R-WRONG', box_key: 'WRONG', gtin: GTIN, serial: 'W1', cn: '715000' }, 1).id;
  const warn = await call('POST', `/person/${pid}/preassign`, { item_id: wrong, plan_id: med.id, ym: '2026-08' });
  assert.equal(warn.status, 409);
  assert.equal(warn.data.mismatch, true);
  assert.ok(warn.data.med && warn.data.box, 'warning carries both sides');
  // Forcing it through succeeds.
  const forced = await call('POST', `/person/${pid}/preassign`, { item_id: wrong, plan_id: med.id, ym: '2026-08', force: true });
  assert.equal(forced.status, 200);
  assert.ok(forced.data.lines.some(l => l.item_id === wrong));
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

test('liberación por medicamento: estado por fecha, campana por medicamento, y quitar fecha', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '30900', nombre: 'Rel', apellidos: 'Med', tis: '00030900' }, 1).id;
  const add = (cn, nombre) => call('POST', `/person/${pid}/plan`, { cn, nombre, qty: 1 });
  const m1 = (await add('700001', 'Med Pasado')).data.plan.find(m => m.cn === '700001');
  const m2 = (await add('700002', 'Med Futuro')).data.plan.find(m => m.cn === '700002');

  // advance_days:0 → effective == official. Past = disponible; far-future = programada.
  const p1 = (await call('PUT', `/plan/${m1.id}/release`, { date: '2020-01-01', advance_days: 0 })).data.plan.find(m => m.id === m1.id);
  assert.equal(p1.release_state, 'disponible');
  const p2 = (await call('PUT', `/plan/${m2.id}/release`, { date: '2999-12-31', advance_days: 0 })).data.plan.find(m => m.id === m2.id);
  assert.equal(p2.release_state, 'programada');

  // Bell (por medicamento): the available med is due, the future one is upcoming.
  const nt = (await call('GET', '/release?mode=box&criterion=lte')).data;
  assert.ok(nt.matched.some(e => e.plan_id === m1.id), 'available med is due');
  assert.ok(nt.pending.some(e => e.plan_id === m2.id), 'future med is upcoming');

  // Overview surfaces the ready count for that person.
  const ov = (await call('GET', '/overview')).data;
  assert.ok((ov.items.find(x => x.person.id === pid) || {}).ready_count >= 1);

  // Clearing the date → 'sin_fecha' (permanent pending) and off the bell.
  const cleared = (await call('PUT', `/plan/${m1.id}/release`, { date: '' })).data.plan.find(m => m.id === m1.id);
  assert.equal(cleared.release_at, null);
  assert.equal(cleared.release_state, 'sin_fecha');
  assert.ok(!(await call('GET', '/release?mode=box&criterion=lte')).data.matched.some(e => e.plan_id === m1.id), 'no date → not on the bell');
});

test('fecha del medicamento: validación de formato y de anticipación', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '34000', nombre: 'Val', apellidos: 'Ida', tis: '00034000' }, 1).id;
  const m = (await call('POST', `/person/${pid}/plan`, { cn: '701000', nombre: 'X', qty: 1 })).data.plan[0];
  assert.equal((await call('PUT', `/plan/${m.id}/release`, { date: '2026/09/01' })).status, 400, 'wrong format rejected');
  assert.equal((await call('PUT', `/plan/${m.id}/release`, { advance_days: 400 })).status, 400, 'advance out of range rejected');
  const okd = (await call('PUT', `/plan/${m.id}/release`, { date: '2027-01-15' })).data.plan[0];
  assert.equal(okd.release_at, '2027-01-15');
  const cleared = (await call('PUT', `/plan/${m.id}/release`, { date: '' })).data.plan[0];
  assert.equal(cleared.release_at, null);
  assert.equal(cleared.release_state, 'sin_fecha');
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

test('búsqueda por fecha (por medicamento): modos box/all/any y criterios lte/exact', async () => {
  const pid = qrDb.createPerson({ pharmacy_no: '33333', nombre: 'Marta', apellidos: 'Ruiz', tis: '00033333' }, 1).id;
  const m1 = (await call('POST', `/person/${pid}/plan`, { cn: '702001', nombre: 'Uno', qty: 1 })).data.plan.find(m => m.cn === '702001');
  const m2 = (await call('POST', `/person/${pid}/plan`, { cn: '702002', nombre: 'Dos', qty: 1 })).data.plan.find(m => m.cn === '702002');
  // advance_days:0 → effective == official, so the exact-date assertions hold.
  await call('PUT', `/plan/${m1.id}/release`, { date: '2020-01-01', advance_days: 0 }); // available
  await call('PUT', `/plan/${m2.id}/release`, { date: '2999-12-31', advance_days: 0 }); // far future

  // Mode BOX (per medication), criterion lte, date today.
  const box = (await call('GET', '/release?mode=box&criterion=lte')).data;
  assert.equal(box.mode, 'box');
  assert.ok(box.matched.some(e => e.plan_id === m1.id));
  assert.ok(box.pending.some(e => e.plan_id === m2.id));

  // Mode ALL: person NOT ready (not all available); aggDate is the latest.
  const all = (await call('GET', '/release?mode=all&criterion=lte')).data;
  const inAllPending = all.pending.find(e => e.person.id === pid);
  assert.ok(inAllPending, 'ALL: person still pending');
  assert.equal(inAllPending.aggDate, '2999-12-31');
  assert.equal(inAllPending.total, 2);
  assert.equal(inAllPending.releasedByToday, 1);
  assert.ok(!all.matched.some(e => e.person.id === pid));

  // Mode ANY: person IS ready (one available); aggDate is the earliest.
  const any = (await call('GET', '/release?mode=any&criterion=lte')).data;
  const inAnyMatched = any.matched.find(e => e.person.id === pid);
  assert.ok(inAnyMatched, 'ANY: person ready');
  assert.equal(inAnyMatched.aggDate, '2020-01-01');

  // Criterion EXACT with the future date: only the future medication matches.
  const exact = (await call('GET', '/release?mode=box&criterion=exact&date=2999-12-31')).data;
  assert.ok(exact.matched.some(e => e.plan_id === m2.id));
  assert.ok(!exact.matched.some(e => e.plan_id === m1.id));
});

test('anticipación por medicamento: efectiva = oficial − anticipación; y se captura al asignar', async () => {
  const isoIn = (days) => { const d = new Date(); d.setDate(d.getDate() + days); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const pid = qrDb.createPerson({ pharmacy_no: '66666', nombre: 'Nel', apellidos: 'Antic', tis: '00066666' }, 1).id;
  const m = (await call('POST', `/person/${pid}/plan`, { gtin: GTIN, qty: 1 })).data.plan.find(x => x.gtin === GTIN);

  // Oficial dentro de 10 días, anticipación 15 (por defecto) → efectiva pasada → 'disponible'.
  let p = (await call('PUT', `/plan/${m.id}/release`, { date: isoIn(10) })).data.plan.find(x => x.id === m.id);
  assert.equal(p.advance_days, 15, 'por defecto 15 días de anticipación');
  assert.equal(p.effective_at, isoIn(-5), 'efectiva = oficial − 15');
  assert.equal(p.release_state, 'disponible');

  // Sin anticipación (0) → efectiva = oficial (dentro de 10 días) → 'programada'.
  p = (await call('PUT', `/plan/${m.id}/release`, { advance_days: 0 })).data.plan.find(x => x.id === m.id);
  assert.equal(p.effective_at, isoIn(10));
  assert.equal(p.release_state, 'programada');
  assert.equal((await call('PUT', `/plan/${m.id}/release`, { advance_days: 400 })).status, 400);

  // La PRÓXIMA fecha se captura al pulsar Asignar (clic de asignación).
  const bx = dmDb.createItem({ raw: 'R-ASGN', box_key: 'ASGN', gtin: GTIN, serial: 'AS1' }, 1).id;
  await call('POST', `/person/${pid}/preassign`, { item_id: bx, plan_id: m.id, ym: '2026-08' });
  const fic = (await call('GET', `/person/${pid}/ficha?ym=2026-08`)).data;
  const line = fic.lines.find(l => l.item_id === bx).id;
  const after = (await call('POST', `/line/${line}/assign`, { next_release_at: isoIn(30) })).data;
  const medAfter = after.plan.find(x => x.id === m.id);
  assert.equal(medAfter.release_at, isoIn(30), 'la próxima fecha de liberación se guarda en el medicamento al asignar');
});

test('notify_mode persists in settings', async () => {
  const s1 = (await call('PUT', '/settings', { notify_mode: 'any' })).data;
  assert.equal(s1.settings.notify_mode, 'any');
  // sizes untouched by a mode-only update
  const meta = (await call('GET', '/meta')).data;
  assert.equal(meta.settings.notify_mode, 'any');
  assert.ok(meta.settings.ficha_qr_size > 0);
  await call('PUT', '/settings', { notify_mode: 'all' });
});

test('búsqueda por fecha: orden alfabético por persona (apellidos, nombre)', async () => {
  const mk = (ph, nom, ape, tis) => qrDb.createPerson({ pharmacy_no: ph, nombre: nom, apellidos: ape, tis }, 1).id;
  const pA = mk('44444', 'Zoe', 'Álvarez', '00044444');
  const pZ = mk('55555', 'Ana', 'Zamora', '00055555');
  for (const [pid, cn] of [[pA, '703001'], [pZ, '703002']]) {
    const m = (await call('POST', `/person/${pid}/plan`, { cn, nombre: 'Med', qty: 1 })).data.plan.find(x => x.cn === cn);
    await call('PUT', `/plan/${m.id}/release`, { date: '2020-01-01', advance_days: 0 });
  }
  const data = (await call('GET', '/release?mode=any&criterion=lte')).data;
  const names = data.matched.map(e => e.person.apellidos);
  const iA = names.indexOf('Álvarez'), iZ = names.indexOf('Zamora');
  assert.ok(iA >= 0 && iZ >= 0 && iA < iZ, 'Álvarez comes before Zamora alphabetically');
});

const asigDb = require('../apps/asignacion/db');

test('notifications: CRUD, validation, toggle and preview', async () => {
  // create requires recipients (and a date for 'once')
  const badNoRcpt = await call('POST', '/notif', { ntype: 'any', criterion: 'exact', schedule_kind: 'once', once_date: '2026-09-01', send_time: '08:00', recipients: '' });
  assert.equal(badNoRcpt.status, 400);
  const badNoDate = await call('POST', '/notif', { ntype: 'any', schedule_kind: 'once', send_time: '08:00', recipients: 'a@b.com' });
  assert.equal(badNoDate.status, 400);

  const created = await call('POST', '/notif', { name: 'Diario', ntype: 'all', criterion: 'lte', schedule_kind: 'recurring', weekdays: '1,2,3,4,5', send_time: '08:30', recipients: 'a@b.com, mal, c@d.com' });
  assert.equal(created.status, 201);
  const id = created.data.item.id;
  assert.equal(created.data.item.recipients, 'a@b.com, c@d.com');  // invalid dropped
  assert.equal(created.data.item.weekdays, '1,2,3,4,5');

  const list = await call('GET', '/notif');
  assert.ok(list.data.items.some(n => n.id === id));
  assert.ok(list.data.userEmail);

  const tg = await call('POST', `/notif/${id}/toggle`);
  assert.equal(tg.data.item.enabled, 0);

  // preview returns HTML (0 people is fine)
  const pv = await call('POST', '/notif/preview', { ntype: 'any', criterion: 'exact', ref_date: '2999-01-01', recipients: 'a@b.com', schedule_kind: 'once', once_date: '2999-01-01' });
  assert.equal(pv.status, 200);
  assert.match(pv.data.html, /<html/i);
  assert.equal(typeof pv.data.count, 'number');

  const del = await call('DELETE', `/notif/${id}`);
  assert.equal(del.data.ok, true);
  assert.ok(!(await call('GET', '/notif')).data.items.some(n => n.id === id));
});

test('dueNotifs fires by time/day and only once per day; once disables after send', () => {
  const rec = asigDb.createNotif({ ntype: 'any', criterion: 'exact', schedule_kind: 'recurring', weekdays: '', send_time: '08:00', recipients: 'a@b.com', enabled: 1 }, 1);
  assert.equal(asigDb.dueNotifs('2030-01-01', '07:59', 3).length, 0, 'before time');
  assert.ok(asigDb.dueNotifs('2030-01-01', '08:00', 3).some(n => n.id === rec.id), 'at time');
  asigDb.markNotifSent(rec.id, '2030-01-01');
  assert.equal(asigDb.dueNotifs('2030-01-01', '09:00', 3).filter(n => n.id === rec.id).length, 0, 'not twice same day');
  assert.ok(asigDb.dueNotifs('2030-01-02', '09:00', 3).some(n => n.id === rec.id), 'fires next day');

  // weekday restriction
  const wk = asigDb.createNotif({ ntype: 'any', criterion: 'exact', schedule_kind: 'recurring', weekdays: '1', send_time: '08:00', recipients: 'a@b.com', enabled: 1 }, 1);
  assert.equal(asigDb.dueNotifs('2030-01-01', '09:00', 2).filter(n => n.id === wk.id).length, 0, 'wrong weekday');
  assert.ok(asigDb.dueNotifs('2030-01-01', '09:00', 1).some(n => n.id === wk.id), 'right weekday');

  // once disables after sending
  const once = asigDb.createNotif({ ntype: 'any', criterion: 'exact', schedule_kind: 'once', once_date: '2030-02-02', send_time: '08:00', recipients: 'a@b.com', enabled: 1 }, 1);
  assert.ok(asigDb.dueNotifs('2030-02-02', '09:00', 6).some(n => n.id === once.id));
  asigDb.markNotifSent(once.id, '2030-02-02');
  assert.equal(asigDb.getNotif(once.id).enabled, 0, 'one-time disabled after send');
});

// A second app instance acting as a different (non-admin) user, sharing the DBs.
const app2 = express();
app2.use((req, res, next) => { req.user = { id: 2, email: 'u2@e', name: 'Otro' }; next(); });
app2.use('/asignacion', router);
let server2, base2;
before(async () => { await new Promise(r => { server2 = app2.listen(0, r); }); base2 = `http://127.0.0.1:${server2.address().port}/asignacion/api`; });
after(() => { try { server2.close(); } catch { } });
async function call2(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const r = await fetch(base2 + path, opts);
  return { status: r.status, data: await r.json().catch(() => ({})) };
}

test('post-its: board CRUD, seed and last-board protection', async () => {
  const b0 = (await call('GET', '/boards')).data;            // ensures the seed board
  assert.ok(b0.items.length >= 1);
  const created = await call('POST', '/boards', { name: 'Turno mañana' });
  assert.equal(created.status, 201);
  const bid = created.data.item.id;
  const ren = await call('PUT', `/boards/${bid}`, { name: 'Mañana' });
  assert.equal(ren.data.item.name, 'Mañana');
  // delete down to one → the last one is protected
  let boards = (await call('GET', '/boards')).data.items;
  for (const b of boards.slice(1)) await call('DELETE', `/boards/${b.id}`);
  const remaining = (await call('GET', '/boards')).data.items;
  assert.equal(remaining.length, 1);
  const blocked = await call('DELETE', `/boards/${remaining[0].id}`);
  assert.equal(blocked.status, 400);
  assert.match(blocked.data.error, /último tablón/);
});

test('post-its: note create validates colour/size, partial updates persist', async () => {
  const board = (await call('GET', '/boards')).data.items[0].id;
  const c = await call('POST', '/notes', { board_id: board, content: 'Hola', color: 'no-existe', pos_x: 30, pos_y: 40, width: 5, height: -9, visibility: 'privada' });
  assert.equal(c.status, 201);
  assert.equal(c.data.item.color, '#FEF08A');      // invalid → yellow
  assert.equal(c.data.item.width, 160);            // clamped up to min
  assert.equal(c.data.item.height, 140);
  assert.equal(c.data.item.puede_gestionar, true);
  const id = c.data.item.id;
  // move (partial)
  await call('PUT', `/notes/${id}`, { pos_x: 111, pos_y: 222 });
  // colour (partial)
  await call('PUT', `/notes/${id}`, { color: '#BBF7D0' });
  const list = (await call('GET', `/notes?board_id=${board}`)).data.items.find(n => n.id === id);
  assert.equal(list.pos_x, 111); assert.equal(list.pos_y, 222); assert.equal(list.color, '#BBF7D0');
});

test('post-its: visibility — who sees / who edits / who manages', async () => {
  const board = (await call('GET', '/boards')).data.items[0].id;
  const n = (await call('POST', '/notes', { board_id: board, content: 'privada de u1', visibility: 'privada' })).data.item;
  // user 2 does NOT see u1's private note
  let u2 = (await call2('GET', `/notes?board_id=${board}`)).data.items;
  assert.ok(!u2.some(x => x.id === n.id), 'u2 no ve la privada');
  // user 2 cannot edit it (can't see)
  assert.equal((await call2('PUT', `/notes/${n.id}`, { content: 'hack' })).status, 403);
  // share with everyone → u2 sees it, and CAN edit it (ver = editar)…
  await call('PUT', `/notes/${n.id}`, { visibility: 'todos' });
  u2 = (await call2('GET', `/notes?board_id=${board}`)).data.items;
  const seen = u2.find(x => x.id === n.id);
  assert.ok(seen, 'u2 ve la de todos');
  assert.equal(seen.puede_gestionar, false, 'u2 no la gestiona');
  assert.equal((await call2('PUT', `/notes/${n.id}`, { content: 'respuesta de u2' })).status, 200, 'u2 puede editar el texto');
  // …but u2 cannot change its sharing or delete it
  assert.equal((await call2('PUT', `/notes/${n.id}`, { visibility: 'privada' })).status, 403);
  assert.equal((await call2('DELETE', `/notes/${n.id}`)).status, 403);
  // personalizada with viewer = 2
  await call('PUT', `/notes/${n.id}`, { visibility: 'personalizada', viewer_ids: [2] });
  const pers = (await call2('GET', `/notes?board_id=${board}`)).data.items.find(x => x.id === n.id);
  assert.ok(pers, 'u2 (viewer) ve la personalizada');
  await call('PUT', `/notes/${n.id}`, { visibility: 'personalizada', viewer_ids: [] });
  assert.ok(!(await call2('GET', `/notes?board_id=${board}`)).data.items.some(x => x.id === n.id), 'sin viewers u2 no la ve');
});

test('post-its: alertas — avisar a los destinatarios, ver, apagar y re-avisar', async () => {
  const board = (await call('GET', '/boards')).data.items[0].id;
  const n = (await call('POST', '/notes', { board_id: board, content: '  Revisa   el pedido \n de mañana ', visibility: 'privada' })).data.item;

  // Un no-gestor no puede activar el aviso.
  assert.equal((await call2('PUT', `/notes/${n.id}`, { alert: true })).status, 403);

  // Compartir con u2 y marcar el aviso (todo en el mismo PUT del autor).
  const shared = (await call('PUT', `/notes/${n.id}`, { visibility: 'personalizada', viewer_ids: [2], alert: true })).data.item;
  assert.equal(shared.alert, 1, 'la nota queda marcada con aviso');

  // u2 recibe la alerta pendiente, con autor, tablón y extracto limpio.
  let al = (await call2('GET', '/notes/alerts')).data.items;
  const mine = al.find(x => x.id === n.id);
  assert.ok(mine, 'u2 tiene la alerta pendiente');
  assert.equal(mine.board_id, board);
  assert.ok(mine.board_name, 'incluye el nombre del tablón');
  assert.equal(mine.excerpt, 'Revisa el pedido de mañana', 'extracto con espacios colapsados');
  assert.ok(typeof mine.author_name === 'string' && mine.author_name.length, 'incluye un nombre de autor');
  assert.ok((await call2('GET', '/notes/badge')).data.alerts >= 1, 'el badge de u2 cuenta la alerta');

  // El autor no se avisa a sí mismo.
  assert.ok(!(await call('GET', '/notes/alerts')).data.items.some(x => x.id === n.id), 'u1 (autor) no se auto-avisa');

  // Al abrir el tablón (marcar visto) la alerta se apaga para u2.
  await call2('POST', '/notes/seen', { board_id: board });
  assert.ok(!(await call2('GET', '/notes/alerts')).data.items.some(x => x.id === n.id), 'tras verla, ya no le avisa');

  // El autor vuelve a avisar → reaparece para u2.
  assert.equal((await call2('POST', `/notes/${n.id}/repoke`)).status, 403, 'u2 no puede re-avisar');
  const re = (await call('POST', `/notes/${n.id}/repoke`)).data.item;
  assert.equal(re.alert, 1);
  assert.ok((await call2('GET', '/notes/alerts')).data.items.some(x => x.id === n.id), 're-avisada: vuelve a aparecer');

  // Volver a privada apaga el aviso.
  const priv = (await call('PUT', `/notes/${n.id}`, { visibility: 'privada' })).data.item;
  assert.equal(priv.alert, 0, 'una nota privada no avisa');
  assert.ok(!(await call2('GET', '/notes/alerts')).data.items.some(x => x.id === n.id), 'sin acceso, sin alerta');
});

test('post-its: compartir se limita a usuarios con acceso a la app', async () => {
  // El selector de compartir solo lista usuarios con acceso a Asignación (1 y 2), no el 3.
  const users = (await call('GET', '/users')).data.items.map(u => u.id);
  assert.ok(users.includes(1) && users.includes(2), 'lista a los usuarios con acceso');
  assert.ok(!users.includes(3), 'NO lista a un usuario sin acceso a la app');

  const board = (await call('GET', '/boards')).data.items[0].id;
  const n = (await call('POST', '/notes', { board_id: board, content: 'para gente de la app', visibility: 'privada' })).data.item;
  // Intentar compartir con el 2 (con acceso) y el 3 (sin acceso): solo se guarda el 2.
  const up = (await call('PUT', `/notes/${n.id}`, { visibility: 'personalizada', viewer_ids: [2, 3] })).data.item;
  assert.deepEqual(up.viewer_ids.sort(), [2], 'el destinatario sin acceso se descarta');

  // Lo mismo al crear la nota directamente con viewers.
  const n2 = (await call('POST', '/notes', { board_id: board, content: 'otra', visibility: 'personalizada', viewer_ids: [2, 3] })).data.item;
  assert.deepEqual(n2.viewer_ids.sort(), [2], 'al crear también se filtra por acceso');
});

test('plan vacío: createEmptyPlan persiste y cuenta como "con plan"', async () => {
  const asigDb = require('../apps/asignacion/db');
  const pid = qrDb.createPerson({ pharmacy_no: '80300', nombre: 'Vac', apellidos: 'Io', tis: '00080300' }, 1).id;
  // Sin plan al principio.
  assert.equal(asigDb.personMedSummary(pid).has_plan, false);
  assert.equal(asigDb.personsWithPlanSet().has(pid), false);
  // Crear plan vacío → persiste y cuenta como con plan (sin medicamentos).
  asigDb.createEmptyPlan(pid, 1);
  const s = asigDb.personMedSummary(pid);
  assert.equal(s.has_plan, true);
  assert.equal(s.plan_count, 0);
  assert.equal(s.empty_plan, true);
  assert.equal(asigDb.personsWithPlanSet().has(pid), true);
  // Idempotente.
  asigDb.createEmptyPlan(pid, 1);
  assert.equal(asigDb.personMedSummary(pid).has_plan, true);
});
