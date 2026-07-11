const { test, before, after } = require('node:test');
const assert = require('node:assert');
const { useTempDb, makeUser } = require('./helpers');

useTempDb();
process.env.DEACTIVATION_SECRET = 'test-secret-rememory';
const store = require('../apps/auth/store');
const rm = require('../apps/re-memory/db');
const { generateDeactivationToken } = require('../apps/re-memory/email');
const app = require('../server');

let base, server, cookie, mem, user;
before(async () => {
  await new Promise(r => { server = app.listen(0, r); });
  base = `http://127.0.0.1:${server.address().port}`;
  user = makeUser(store, 'u@test.com');
  const { sid } = store.createSession(user.id);
  cookie = `jt_sid=${sid}`;
  mem = rm.createMemory({ description: 'capital de Francia', frequency: '1m', topic: 'Geo', user_id: user.id });
});
after(() => { try { server.close(); } catch { /* ignore */ } });

test('cambiar frecuencia (token válido, con sesión) → cambia y recalcula', async () => {
  const token = generateDeactivationToken(mem.id, user.id);
  const before = rm.getMemoryById(mem.id, user.id).next_send_date;
  const r = await fetch(`${base}/re-memory/accion/frecuencia/${mem.id}/2m/${token}`, { headers: { Cookie: cookie } });
  assert.equal(r.status, 200);
  const after = rm.getMemoryById(mem.id, user.id);
  assert.equal(after.frequency, '2m');
  assert.notEqual(after.next_send_date, before, 'reprograma el próximo envío');
});

test('frecuencia no válida → 400', async () => {
  const token = generateDeactivationToken(mem.id, user.id);
  const r = await fetch(`${base}/re-memory/accion/frecuencia/${mem.id}/9z/${token}`, { headers: { Cookie: cookie } });
  assert.equal(r.status, 400);
});

test('token inválido → 403 (no cambia)', async () => {
  const r = await fetch(`${base}/re-memory/accion/frecuencia/${mem.id}/6m/malote`, { headers: { Cookie: cookie } });
  assert.equal(r.status, 403);
  assert.notEqual(rm.getMemoryById(mem.id, user.id).frequency, '6m');
});

test('sin sesión → 401 (no cambia, protege de prefetch)', async () => {
  const token = generateDeactivationToken(mem.id, user.id);
  const r = await fetch(`${base}/re-memory/accion/frecuencia/${mem.id}/3m/${token}`, { redirect: 'manual' });
  assert.ok(r.status === 401 || r.status === 302);
  assert.notEqual(rm.getMemoryById(mem.id, user.id).frequency, '3m');
});

test('historial vía API devuelve eventos (created + cambios)', async () => {
  const r = await fetch(`${base}/re-memory/api/memories/${mem.id}/history`, { headers: { Cookie: cookie } });
  assert.equal(r.status, 200);
  const events = await r.json();
  assert.ok(Array.isArray(events) && events.length > 0);
  assert.ok(events.some(e => e.type === 'created'));
});

test('posponer +2 días mueve la fecha del próximo envío', async () => {
  const token = generateDeactivationToken(mem.id, user.id);
  const before = new Date(rm.getMemoryById(mem.id, user.id).next_send_date).getTime();
  const r = await fetch(`${base}/re-memory/accion/posponer/${mem.id}/2/${token}`, { headers: { Cookie: cookie } });
  assert.equal(r.status, 200);
  const after = new Date(rm.getMemoryById(mem.id, user.id).next_send_date).getTime();
  const diffDays = Math.round((after - before) / 86400000);
  assert.equal(diffDays, 2, 'suma 2 días');
});

test('posponer con días no válidos → 400', async () => {
  const token = generateDeactivationToken(mem.id, user.id);
  const r = await fetch(`${base}/re-memory/accion/posponer/${mem.id}/9/${token}`, { headers: { Cookie: cookie } });
  assert.equal(r.status, 400);
});

test('acción del email sin sesión → redirige a login (no 401 JSON)', async () => {
  const token = generateDeactivationToken(mem.id, user.id);
  const r = await fetch(`${base}/re-memory/accion/frecuencia/${mem.id}/1w/${token}`, { redirect: 'manual' });
  assert.equal(r.status, 302, 'redirige (no JSON 401)');
  assert.ok((r.headers.get('location') || '').includes('/auth/login'), 'va al login con next');
});
