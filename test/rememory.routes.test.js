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
  const r = await fetch(`${base}/re-memory/api/set-frequency/${mem.id}/2m/${token}`, { headers: { Cookie: cookie } });
  assert.equal(r.status, 200);
  const after = rm.getMemoryById(mem.id, user.id);
  assert.equal(after.frequency, '2m');
  assert.notEqual(after.next_send_date, before, 'reprograma el próximo envío');
});

test('frecuencia no válida → 400', async () => {
  const token = generateDeactivationToken(mem.id, user.id);
  const r = await fetch(`${base}/re-memory/api/set-frequency/${mem.id}/9z/${token}`, { headers: { Cookie: cookie } });
  assert.equal(r.status, 400);
});

test('token inválido → 403 (no cambia)', async () => {
  const r = await fetch(`${base}/re-memory/api/set-frequency/${mem.id}/6m/malote`, { headers: { Cookie: cookie } });
  assert.equal(r.status, 403);
  assert.notEqual(rm.getMemoryById(mem.id, user.id).frequency, '6m');
});

test('sin sesión → 401 (no cambia, protege de prefetch)', async () => {
  const token = generateDeactivationToken(mem.id, user.id);
  const r = await fetch(`${base}/re-memory/api/set-frequency/${mem.id}/3m/${token}`, { redirect: 'manual' });
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
