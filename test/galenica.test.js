const { test, before, after } = require('node:test');
const assert = require('node:assert');
const os = require('os');
const path = require('path');
const fs = require('fs');

// Isolate the databases BEFORE requiring the modules. Galénica reuses the same
// CIMA cache as Data Matrix (apps/datamatrix/cima-cache.js → dm.db), so both
// DB paths need isolating for this test to seed the cache directly.
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'galenica-test-'));
process.env.GALENICA_DB_PATH = path.join(dir, 'galenica.db');
process.env.DM_DB_PATH = path.join(dir, 'dm.db');
process.env.CIMA_ENABLED = 'false';   // offline in the sandbox → tests seed the cache directly

const express = require('express');
const dmDb = require('../apps/datamatrix/db');
const glDb = require('../apps/galenica/db');
const router = require('../apps/galenica/routes');

const app = express();
app.use((req, res, next) => { req.user = { id: 1, email: 'a@e', name: 'A', role: 'admin', apps: '*' }; next(); });
app.use('/galenica', router);

let server, base;
before(async () => { server = await new Promise(r => { const s = app.listen(0, () => r(s)); }); base = `http://127.0.0.1:${server.address().port}/galenica/api`; });
after(() => { try { server.close(); } catch { } });

async function call(method, p, body) {
  const opts = { method };
  if (body !== undefined) { opts.headers = { 'Content-Type': 'application/json' }; opts.body = JSON.stringify(body); }
  const r = await fetch(base + p, opts);
  const data = await r.json().catch(() => ({}));
  return { status: r.status, data };
}

test('añadir por CN sin CIMA (offline): crea el registro solo con el CN', async () => {
  const r = await call('POST', '/meds', { cn: '900001', color: 'blanco' });
  assert.equal(r.status, 200);
  assert.equal(r.data.cima_found, false);
  assert.equal(r.data.item.cn, '900001');
  assert.equal(r.data.item.color, 'blanco', 'el color manual se aplica aunque CIMA no responda');
  assert.ok(r.data.item.gtin, 'el GTIN se deriva matemáticamente del CN, sin depender de CIMA');
  assert.ok(r.data.item.barcode, 'el código de barras también se deriva matemáticamente, sin depender de CIMA');
});

test('añadir por CN con la caché de CIMA sembrada: trae nombre/principio activo/forma', async () => {
  dmDb.cimaCachePut('900002', { nombre: 'IBUPROFENO PRUEBA 600 mg', pactivos: 'IBUPROFENO', forma: 'Comprimido recubierto con película', labtitular: 'Lab Pruebas SA' });
  const r = await call('POST', '/meds', { cn: '900002' });
  assert.equal(r.status, 200);
  assert.equal(r.data.cima_found, true);
  assert.equal(r.data.item.nombre, 'IBUPROFENO PRUEBA 600 mg');
  assert.equal(r.data.item.pactivos, 'IBUPROFENO');
  assert.equal(r.data.item.forma, 'Comprimido recubierto con película');
  assert.equal(r.data.item.color, null, 'sin color porque no se dio ninguno — CIMA no lo provee');
});

test('un CN duplicado se rechaza (400)', async () => {
  const r = await call('POST', '/meds', { cn: '900002' });
  assert.equal(r.status, 400);
});

test('CN no válido se rechaza', async () => {
  const r = await call('POST', '/meds', { cn: 'abc' });
  assert.equal(r.status, 400);
});

test('GET /api/meds y /api/meta reflejan lo añadido', async () => {
  const list = await call('GET', '/meds');
  assert.equal(list.status, 200);
  assert.ok(list.data.items.find(m => m.cn === '900001'));
  assert.ok(list.data.items.find(m => m.cn === '900002'));
  const meta = await call('GET', '/meta');
  assert.ok(meta.data.formas.includes('Comprimido recubierto con película'));
  assert.ok(meta.data.colors.includes('blanco'));
});

test('editar (color/notas) y luego actualizar desde CIMA no borra lo editado a mano', async () => {
  const created = (await call('POST', '/meds', { cn: '900003' })).data.item;
  const edited = await call('PUT', `/meds/${created.id}`, { color: 'rosa', notes: 'ranurada por la mitad' });
  assert.equal(edited.status, 200);
  assert.equal(edited.data.item.color, 'rosa');

  dmDb.cimaCachePut('900003', { nombre: 'NUEVO NOMBRE TRAS ACTUALIZAR', pactivos: 'PARACETAMOL' });
  const refreshed = await call('POST', `/meds/${created.id}/cima`);
  assert.equal(refreshed.status, 200);
  assert.equal(refreshed.data.cima_found, true);
  assert.equal(refreshed.data.item.nombre, 'NUEVO NOMBRE TRAS ACTUALIZAR', 'el nombre sí se refresca desde CIMA');
  assert.equal(refreshed.data.item.color, 'rosa', 'el color manual sobrevive a la actualización desde CIMA');
  assert.equal(refreshed.data.item.notes, 'ranurada por la mitad', 'las notas también sobreviven');
});

test('eliminar quita el medicamento del catálogo', async () => {
  const created = (await call('POST', '/meds', { cn: '900004' })).data.item;
  const del = await call('DELETE', `/meds/${created.id}`);
  assert.equal(del.status, 200);
  const list = await call('GET', '/meds');
  assert.ok(!list.data.items.find(m => m.cn === '900004'));
});

test('importación en lote: crea, actualiza y reporta lo que CIMA no resolvió', async () => {
  dmDb.cimaCachePut('900005', { nombre: 'PARACETAMOL PRUEBA 1g' });
  const r = await call('POST', '/import', { rows: [
    { cn: '900005', color: 'blanco' },   // CIMA sí lo tiene
    { cn: '900006' },                     // CIMA no lo tiene → "missing" pero se guarda igual
    { cn: '900002', color: 'amarillo' },  // ya existía → se actualiza, no se duplica
  ] });
  assert.equal(r.status, 200);
  assert.equal(r.data.created, 2);
  assert.equal(r.data.updated, 1);
  assert.deepEqual(r.data.missing, ['900006']);

  const list = (await call('GET', '/meds')).data.items;
  assert.equal(list.find(m => m.cn === '900005').nombre, 'PARACETAMOL PRUEBA 1g');
  assert.ok(list.find(m => m.cn === '900006'), 'se guarda por CN aunque CIMA no responda, nada se pierde');
  assert.equal(list.find(m => m.cn === '900002').color, 'amarillo', 'la reimportación actualiza el color');
});
