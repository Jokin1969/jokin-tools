const { test, before, after } = require('node:test');
const assert = require('node:assert');
const os = require('os');
const path = require('path');
const fs = require('fs');

// Isolate all four databases in a temp dir BEFORE requiring the modules.
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pastillero-test-'));
process.env.QR_TIS_DB_PATH = path.join(dir, 'qr.db');
process.env.DM_DB_PATH = path.join(dir, 'dm.db');
process.env.ASIG_DB_PATH = path.join(dir, 'asig.db');
process.env.PASTILLERO_DB_PATH = path.join(dir, 'pastillero.db');
process.env.DB_PATH = path.join(dir, 'auth.db');

const express = require('express');
const qrDb = require('../apps/qr-tis/db');
const asigDb = require('../apps/asignacion/db');
const ptDb = require('../apps/pastillero/db');
const router = require('../apps/pastillero/routes');

// A tiny app that injects an admin (for the /admin* routes) and mounts the router,
// same pattern as the other app test files.
const app = express();
app.use((req, res, next) => { req.user = { id: 1, email: 'a@e', name: 'A', role: 'admin', apps: '*' }; next(); });
app.use('/pastillero', router);

let server, base;
before(async () => { server = await new Promise(r => { const s = app.listen(0, () => r(s)); }); base = `http://127.0.0.1:${server.address().port}/pastillero/api`; });
after(() => { try { server.close(); } catch { } });

// Extracts "name=value" from a Set-Cookie header so we can replay it manually
// (undici's fetch doesn't keep a cookie jar across separate calls).
function cookieFrom(res) {
  const sc = res.headers.get('set-cookie');
  if (!sc) return null;
  return sc.split(';')[0];
}
async function call(method, p, body, cookie) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (cookie) headers['Cookie'] = cookie;
  const r = await fetch(base + p, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  const data = await r.json().catch(() => ({}));
  return { status: r.status, data, res: r };
}

test('db: rotateCode genera un código único y reutilizable; desactivar invalida el login', () => {
  const r1 = ptDb.rotateCode('Residencia Alfa');
  assert.ok(r1.access_code && r1.access_code.length >= 4);
  assert.equal(ptDb.getResidenciaByCode(r1.access_code).group_name, 'Residencia Alfa');

  const before = r1.access_code;
  const r2 = ptDb.rotateCode('Residencia Alfa');
  assert.notEqual(r2.access_code, before, 'rotar cambia el código');
  assert.equal(ptDb.getResidenciaByCode(before), null, 'el código viejo deja de servir');

  ptDb.setResidenciaActive('Residencia Alfa', false);
  assert.equal(ptDb.getResidenciaByCode(r2.access_code), null, 'desactivada: el código ya no resuelve sesión');
  ptDb.setResidenciaActive('Residencia Alfa', true);
  assert.ok(ptDb.getResidenciaByCode(r2.access_code));
});

test('login por código: rechaza vacío/incorrecto, acepta el válido y GET /me lo refleja', async () => {
  const bad1 = await call('POST', '/login', { code: '' });
  assert.equal(bad1.status, 400);
  const bad2 = await call('POST', '/login', { code: 'NOEXISTE1' });
  assert.equal(bad2.status, 400);

  const r = ptDb.rotateCode('Residencia Login');
  const ok = await call('POST', '/login', { code: r.access_code });
  assert.equal(ok.status, 200);
  assert.equal(ok.data.residencia.group_name, 'Residencia Login');
  const cookie = cookieFrom(ok.res);
  assert.ok(cookie && cookie.startsWith('pt_sid='));

  const me = await call('GET', '/me', undefined, cookie);
  assert.equal(me.data.residencia.group_name, 'Residencia Login');

  // Logout clears the session server-side (a fresh request without the cookie sees none).
  await call('POST', '/logout', undefined, cookie);
  const meAfter = await call('GET', '/me', undefined, cookie);
  assert.equal(meAfter.data.residencia, null);
});

test('cuidador: solo ve personas de SU residencia, y la ficha respeta ese límite', async () => {
  const rA = ptDb.rotateCode('Ala Norte');
  const rB = ptDb.rotateCode('Ala Sur');
  const alice = qrDb.createPerson({ pharmacy_no: '90001', nombre: 'Alicia', apellidos: 'Norte', tis: '00090001', group_name: 'Ala Norte' }, 1);
  const bruno = qrDb.createPerson({ pharmacy_no: '90002', nombre: 'Bruno', apellidos: 'Sur', tis: '00090002', group_name: 'Ala Sur' }, 1);

  const loginA = await call('POST', '/login', { code: rA.access_code });
  const cookieA = cookieFrom(loginA.res);

  const list = await call('GET', '/people?q=', undefined, cookieA);
  assert.ok(list.data.items.some(p => p.id === alice.id), 've a su propia residencia');
  assert.ok(!list.data.items.some(p => p.id === bruno.id), 'NO ve a la otra residencia');

  const forbidden = await call('GET', `/person/${bruno.id}/pastillero`, undefined, cookieA);
  assert.equal(forbidden.status, 403);

  const withoutCookie = await call('GET', '/people?q=');
  assert.equal(withoutCookie.status, 401, 'sin código, no hay acceso al listado');
});

test('ficha del pastillero: agrega la pauta por franja vigente en la fecha pedida', async () => {
  const r = ptDb.rotateCode('Residencia Pauta');
  const person = qrDb.createPerson({ pharmacy_no: '90010', nombre: 'Elena', apellidos: 'Pauta', tis: '00090010', group_name: 'Residencia Pauta' }, 1);
  const med = asigDb.addPlanMed(person.id, { cn: '715000', nombre: 'Ibuprofeno 600', barcode: '8470007150008', qty: 1 });
  asigDb.setDoseSchedule(med.id, '2026-08-01', { desayuno: 1, comida: 0, cena: 1, noche: 0 }, 1);

  const login = await call('POST', '/login', { code: r.access_code });
  const cookie = cookieFrom(login.res);

  const ficha = await call('GET', `/person/${person.id}/pastillero?date=2026-08-15`, undefined, cookie);
  assert.equal(ficha.status, 200);
  assert.equal(ficha.data.empty, false);
  assert.equal(ficha.data.slots.desayuno.length, 1);
  assert.equal(ficha.data.slots.desayuno[0].nombre, 'Ibuprofeno 600');
  assert.equal(ficha.data.slots.comida.length, 0);
  assert.equal(ficha.data.slots.cena.length, 1);

  // A person with no schedule at all comes back "empty" (not an error).
  const other = qrDb.createPerson({ pharmacy_no: '90011', nombre: 'Sin', apellidos: 'Pauta', tis: '00090011', group_name: 'Residencia Pauta' }, 1);
  const ficha2 = await call('GET', `/person/${other.id}/pastillero`, undefined, cookie);
  assert.equal(ficha2.data.empty, true);
});

test('admin: requiere acceso a la app "pastillero" y gestiona el código por residencia', async () => {
  qrDb.createPerson({ pharmacy_no: '90020', nombre: 'Zzz', apellidos: 'Admin', tis: '00090020', group_name: 'Residencia Admin' }, 1);
  const list = await call('GET', '/admin/residencias');
  assert.equal(list.status, 200);
  const row = list.data.items.find(x => x.group_name === 'Residencia Admin');
  assert.ok(row && row.has_code === false);

  const rot = await call('POST', '/admin/residencias/rotate', { group_name: 'Residencia Admin' });
  assert.equal(rot.status, 200);
  assert.ok(rot.data.item.access_code);

  const list2 = await call('GET', '/admin/residencias');
  const row2 = list2.data.items.find(x => x.group_name === 'Residencia Admin');
  assert.equal(row2.has_code, true);

  const off = await call('POST', '/admin/residencias/active', { group_name: 'Residencia Admin', active: false });
  assert.equal(off.data.item.active, 0);
});

test('admin sin permiso de "pastillero" recibe 403', async () => {
  const app2 = express();
  app2.use((req, res, next) => { req.user = { id: 2, email: 'b@e', name: 'B', role: 'user', apps: 'qr-tis' }; next(); });
  app2.use('/pastillero', router);
  const s2 = await new Promise(r => { const srv = app2.listen(0, () => r(srv)); });
  try {
    const r = await fetch(`http://127.0.0.1:${s2.address().port}/pastillero/api/admin/residencias`);
    assert.equal(r.status, 403);
  } finally { s2.close(); }
});
