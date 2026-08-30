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

// ── Medication button (QR·TIS → Asignación) ──────────────────────────────────────
test('med-summary endpoint + canAsignacion meta flag (with access gating)', async () => {
  const http = require('http');
  const express = require('express');
  process.env.ASIG_DB_PATH = path.join(dir, 'asig.db');
  const asigDb = require('../apps/asignacion/db');
  const router = require('../apps/qr-tis/routes');

  // Toggle the user's app access via a header: 'yes' → admin, 'no' → no apps.
  const app = express();
  app.use((req, res, next) => {
    req.user = req.headers['x-acc'] === 'no'
      ? { id: 2, email: 'no@e', name: 'NoAsig', role: 'user', apps: ['qr-tis'] }
      : { id: 1, email: 'ok@e', name: 'Admin', role: 'admin', apps: '*' };
    next();
  });
  app.use('/qr-tis', router);
  const server = await new Promise(res => { const s = app.listen(0, () => res(s)); });
  const base = `http://127.0.0.1:${server.address().port}/qr-tis/api`;
  const get = (p, acc) => fetch(base + p, { headers: acc ? { 'x-acc': acc } : {} }).then(async r => ({ status: r.status, data: await r.json().catch(() => ({})) }));

  try {
    const person = db.createPerson({ nombre: 'Med', apellidos: 'Link', tis: '7000001' }, 1);
    // No plan yet → has_plan false.
    const empty = await get(`/people/${person.id}/med-summary`);
    assert.equal(empty.status, 200);
    assert.equal(empty.data.summary.has_plan, false);
    assert.equal(empty.data.summary.plan_count, 0);
    // Add two medications → counts reflect it.
    asigDb.addPlanMed(person.id, { cn: '715000', nombre: 'Ibuprofeno 600' });
    asigDb.addPlanMed(person.id, { cn: '885442', nombre: 'Ixia 10 mg' });
    const full = await get(`/people/${person.id}/med-summary`);
    assert.equal(full.data.summary.has_plan, true);
    assert.equal(full.data.summary.plan_count, 2);
    assert.equal(full.data.summary.active_count, 2);
    // Meta advertises access for an admin, and hides it for a user without it.
    assert.equal((await get('/meta')).data.canAsignacion, true);
    assert.equal((await get('/meta', 'no')).data.canAsignacion, false);
    // A user without Asignación access is refused the summary.
    assert.equal((await get(`/people/${person.id}/med-summary`, 'no')).status, 403);
  } finally { server.close(); }
});

test('group_colors: se guardan, se filtran (color válido) y persisten en settings', () => {
  // Valid map is stored and returned parsed.
  let s = db.saveSettings({ group_colors: { 'Residencia Sol': '#1273b8', 'Residencia Luna': '#c23a3a' } }, 1);
  assert.deepEqual(s.group_colors, { 'Residencia Sol': '#1273b8', 'Residencia Luna': '#c23a3a' });
  s = db.getSettings();
  assert.equal(s.group_colors['Residencia Sol'], '#1273b8');
  // A normal settings save (no group_colors) must NOT wipe them.
  s = db.saveSettings({ qr_size: 300 }, 1);
  assert.equal(s.group_colors['Residencia Luna'], '#c23a3a');
  assert.equal(s.qr_size, 300);
  // Clearing to empty map removes them.
  s = db.saveSettings({ group_colors: {} }, 1);
  assert.deepEqual(s.group_colors, {});
});

test('person notes: upsert, borrar y aparecen en el payload de personas', async () => {
  const http = require('http'); const express = require('express');
  const router = require('../apps/qr-tis/routes');
  const app = express();
  app.use((req, res, next) => { req.user = { id: 1, email: 'a@e', name: 'A', role: 'admin', apps: '*' }; next(); });
  app.use('/qr-tis', router);
  const server = await new Promise(r => { const s = app.listen(0, () => r(s)); });
  const base = `http://127.0.0.1:${server.address().port}/qr-tis/api`;
  const call = (m, p, b) => fetch(base + p, { method: m, headers: b ? { 'Content-Type': 'application/json' } : {}, body: b ? JSON.stringify(b) : undefined }).then(async r => ({ status: r.status, data: await r.json().catch(() => ({})) }));
  try {
    const pid = db.createPerson({ pharmacy_no: '77001', nombre: 'Nota', apellidos: 'Uno', tis: '00770001' }, 1).id;
    // Set a note.
    const put = await call('PUT', `/people/${pid}/note`, { text: 'Silla de ruedas', color: '#BFDBFE' });
    assert.equal(put.status, 200); assert.equal(put.data.note.text, 'Silla de ruedas');
    // It shows in the list payload + single get.
    assert.ok((await call('GET', '/people')).data.items.find(x => x.id === pid).note.text === 'Silla de ruedas');
    assert.equal((await call('GET', `/people/${pid}`)).data.item.note.color, '#BFDBFE');
    // Empty text clears it.
    await call('PUT', `/people/${pid}/note`, { text: '' });
    assert.equal((await call('GET', `/people/${pid}`)).data.item.note, null);
  } finally { server.close(); }
});

test('QR code: asociación por Nº de farmacia, PATCH, PUT y borrado (fallback al TIS)', async () => {
  const express = require('express');
  const router = require('../apps/qr-tis/routes');
  const app = express();
  app.use((req, res, next) => { req.user = { id: 1, email: 'a@e', name: 'A', role: 'admin', apps: '*' }; next(); });
  app.use('/qr-tis', router);
  const server = await new Promise(r => { const s = app.listen(0, () => r(s)); });
  const base = `http://127.0.0.1:${server.address().port}/qr-tis/api`;
  const call = (m, p, b) => fetch(base + p, { method: m, headers: b ? { 'Content-Type': 'application/json' } : {}, body: b ? JSON.stringify(b) : undefined }).then(async r => ({ status: r.status, data: await r.json().catch(() => ({})) }));
  try {
    const a = db.createPerson({ pharmacy_no: '88001', nombre: 'Qr', apellidos: 'Uno', tis: '00880001' }, 1).id;
    const b = db.createPerson({ pharmacy_no: '88002', nombre: 'Qr', apellidos: 'Dos', tis: '00880002' }, 1).id;
    // Import association by pharmacy number; one pharmacy doesn't exist.
    const imp = await call('POST', '/qr-codes/import', { rows: [
      { pharmacy_no: '88001', qr_code: 'LONG-CODE-AAA-1234567890' },
      { pharmacy_no: '88002', qr_code: 'LONG-CODE-BBB-0987654321' },
      { pharmacy_no: '99999', qr_code: 'X' },
    ] });
    assert.equal(imp.status, 200);
    assert.equal(imp.data.updated, 2, 'asocia 2 códigos');
    assert.deepEqual(imp.data.notFound, ['99999'], 'informa del Nº de farmacia inexistente');
    // The code reaches the payload (used to build the QR) but the TIS is untouched.
    const pa = (await call('GET', `/people/${a}`)).data.item;
    assert.equal(pa.qr_code, 'LONG-CODE-AAA-1234567890');
    assert.equal(pa.tis, '00880001', 'el TIS no cambia');
    // Import only touches qr_code — never other fields.
    assert.equal(pa.nombre, 'Qr');
    // PATCH can set it too.
    await call('PATCH', `/people/${a}`, { qr_code: 'EDIT-CODE-999' });
    assert.equal((await call('GET', `/people/${a}`)).data.item.qr_code, 'EDIT-CODE-999');
    // PUT (scanner path) sets one person's code.
    const put = await call('PUT', `/people/${b}/qr-code`, { qr_code: 'SCAN-CODE-777' });
    assert.equal(put.status, 200);
    assert.equal(put.data.item.qr_code, 'SCAN-CODE-777');
    // Empty clears it (QR falls back to the TIS).
    await call('PUT', `/people/${b}/qr-code`, { qr_code: '' });
    assert.equal((await call('GET', `/people/${b}`)).data.item.qr_code, null);

    // Real-world code: kept VERBATIM (%, ^, ?, / and inner/trailing spaces all matter).
    const real = '%0000000000930868^BBBBBBBBBN583421^02^CASTILLA/CASTRILLON/JOAQUIN            ? TDG';
    await call('PUT', `/people/${a}/qr-code`, { qr_code: real });
    assert.equal((await call('GET', `/people/${a}`)).data.item.qr_code, real, 'código guardado exactamente igual');
    // Same fidelity through the association import, and a trailing newline (scanner Enter) is dropped.
    await call('POST', '/qr-codes/import', { rows: [{ pharmacy_no: '88002', qr_code: real + '\r\n' }] });
    assert.equal((await call('GET', `/people/${b}`)).data.item.qr_code, real, 'import conserva el código y quita el salto de línea');
    // Whitespace-only clears it.
    await call('PUT', `/people/${a}/qr-code`, { qr_code: '   ' });
    assert.equal((await call('GET', `/people/${a}`)).data.item.qr_code, null);
  } finally { server.close(); }
});

test('POST /api/people (alta desde el formulario): admite grupo y Código QR desde la creación', async () => {
  const express = require('express');
  const router = require('../apps/qr-tis/routes');
  const app = express();
  app.use((req, res, next) => { req.user = { id: 1, email: 'a@e', name: 'A', role: 'admin', apps: '*' }; next(); });
  app.use('/qr-tis', router);
  const server = await new Promise(r => { const s = app.listen(0, () => r(s)); });
  const base = `http://127.0.0.1:${server.address().port}/qr-tis/api`;
  const call = (m, p, b) => fetch(base + p, { method: m, headers: b ? { 'Content-Type': 'application/json' } : {}, body: b ? JSON.stringify(b) : undefined }).then(async r => ({ status: r.status, data: await r.json().catch(() => ({})) }));
  try {
    const created = await call('POST', '/people', {
      pharmacy_no: '91001', nombre: 'Alta', apellidos: 'ConQR', tis: '00910011',
      group_name: 'Residencia San José', qr_code: 'CODIGO-QR-LARGO-123',
    });
    assert.equal(created.status, 201);
    assert.equal(created.data.item.group_name, 'Residencia San José', 'el grupo se guarda ya desde el alta');
    assert.equal(created.data.item.qr_code, 'CODIGO-QR-LARGO-123', 'el Código QR se guarda ya desde el alta (antes se perdía)');
    assert.equal(created.data.item.tis, '00910011', 'el TIS se conserva aparte, como texto legible');

    // Sin grupo ni Código QR: ambos quedan vacíos (el QR usará el TIS, como siempre).
    const plain = await call('POST', '/people', { pharmacy_no: '91002', nombre: 'Alta', apellidos: 'Simple', tis: '00910012' });
    assert.equal(plain.status, 201);
    assert.equal(plain.data.item.group_name, null);
    assert.equal(plain.data.item.qr_code, null);
  } finally { server.close(); }
});

test('bulk import (/api/import) crea personas con su Código QR (real); vacío = QR usa el TIS', async () => {
  const express = require('express');
  const router = require('../apps/qr-tis/routes');
  const app = express();
  app.use((req, res, next) => { req.user = { id: 1, email: 'a@e', name: 'A', role: 'admin', apps: '*' }; next(); });
  app.use('/qr-tis', router);
  const server = await new Promise(r => { const s = app.listen(0, () => r(s)); });
  const base = `http://127.0.0.1:${server.address().port}/qr-tis/api`;
  const call = (m, p, b) => fetch(base + p, { method: m, headers: b ? { 'Content-Type': 'application/json' } : {}, body: b ? JSON.stringify(b) : undefined }).then(async r => ({ status: r.status, data: await r.json().catch(() => ({})) }));
  try {
    const real = '%0000000000930868^BBBBBBBBBN583421^02^IMPO/QR/UNO? TDG';
    const r = await call('POST', '/import', { rows: [
      { __row: 2, pharmacy_no: '71011', nombre: 'Impo', apellidos: 'ConQR', tis: '00710111', qr_code: real, group_name: 'Planta 9' },
      { __row: 3, pharmacy_no: '71012', nombre: 'Impo', apellidos: 'SinQR', tis: '00710112', qr_code: '' },
    ] });
    assert.equal(r.status, 200);
    assert.deepEqual(r.data.errors, [], 'sin errores de validación');
    const list = (await call('GET', '/people')).data.items;
    const withQr = list.find(x => x.tis === '00710111');
    const noQr = list.find(x => x.tis === '00710112');
    assert.ok(withQr && noQr, 'ambas personas importadas');
    assert.equal(withQr.qr_code, real, 'guarda el Código QR (real) tal cual');
    assert.equal(noQr.qr_code, null, 'sin Código QR → null (el QR usará el TIS)');
  } finally { server.close(); }
});

test('export/pdf: modo normal (QR primero) y modo "priorizar nombre" (QR en segundo plano)', async () => {
  const express = require('express');
  const router = require('../apps/qr-tis/routes');
  const app = express();
  app.use((req, res, next) => { req.user = { id: 1, email: 'a@e', name: 'A', role: 'admin', apps: '*' }; next(); });
  app.use('/qr-tis', router);
  const server = await new Promise(r => { const s = app.listen(0, () => r(s)); });
  const base = `http://127.0.0.1:${server.address().port}/qr-tis/api`;
  try {
    const p1 = db.createPerson({ pharmacy_no: '92001', nombre: 'Pdf', apellidos: 'UnoLargoApellidoParaProbarElAjuste', tis: '00920011' }, 1).id;
    db.createPerson({ pharmacy_no: '92002', nombre: 'Pdf', apellidos: 'Dos', tis: '00920012' }, 1);

    // Modo normal: sin name_priority, se comporta exactamente como antes.
    const normal = await fetch(base + '/export/pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: [p1], qr_size: 150, title: 'Prueba normal' }),
    });
    assert.equal(normal.status, 200);
    assert.equal(normal.headers.get('content-type'), 'application/pdf');
    const normalBytes = Buffer.from(await normal.arrayBuffer());
    assert.ok(normalBytes.length > 500 && normalBytes.slice(0, 4).toString() === '%PDF', 'es un PDF');

    // Modo "priorizar nombre": mismo endpoint, con name_priority + name_size.
    const prio = await fetch(base + '/export/pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: [p1], qr_size: 80, title: 'Prueba flexible', name_priority: true, name_size: 28 }),
    });
    assert.equal(prio.status, 200);
    assert.equal(prio.headers.get('content-type'), 'application/pdf');
    const prioBytes = Buffer.from(await prio.arrayBuffer());
    assert.ok(prioBytes.length > 500 && prioBytes.slice(0, 4).toString() === '%PDF', 'también es un PDF válido');

    // name_size fuera de rango no rompe nada — se acota en el servidor.
    const clamped = await fetch(base + '/export/pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: [p1], name_priority: true, name_size: 999 }),
    });
    assert.equal(clamped.status, 200, 'un name_size disparatado se acota, no rompe la exportación');
  } finally { server.close(); }
});
