const { test } = require('node:test');
const assert = require('node:assert');
const os = require('os');
const path = require('path');
const fs = require('fs');

// Isolate every DB this feed touches BEFORE requiring the modules: Galénica's own,
// the shared CIMA cache (lives in Data Matrix's db), and Asignación's (for the
// startup catch-up). CIMA itself stays disabled — same pattern as galenica.test.js —
// so lookups only succeed when the cache was seeded directly.
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'galenica-ingest-test-'));
process.env.GALENICA_DB_PATH = path.join(dir, 'galenica.db');
process.env.DM_DB_PATH = path.join(dir, 'dm.db');
process.env.ASIG_DB_PATH = path.join(dir, 'asig.db');
process.env.CIMA_ENABLED = 'false';

const glDb = require('../apps/galenica/db');
const dmDb = require('../apps/datamatrix/db');
const asigDb = require('../apps/asignacion/db');
const ingest = require('../apps/galenica/ingest');

test('ingestOne con la caché de CIMA sembrada: crea el registro con nombre/pactivos/forma', async () => {
  dmDb.cimaCachePut('910001', { nombre: 'MEDICAMENTO PRUEBA A', pactivos: 'PRINCIPIO A', forma: 'Comprimido' });
  const created = await ingest.ingestOne('910001');
  assert.equal(created, true);
  const med = glDb.getByCn('910001');
  assert.ok(med, 'el CN entra en Galénica');
  assert.equal(med.nombre, 'MEDICAMENTO PRUEBA A');
  assert.equal(med.pactivos, 'PRINCIPIO A');
  assert.equal(med.forma, 'Comprimido');
  assert.equal(med.color, null, 'el color queda pendiente de rellenar a mano — CIMA no lo da');
});

test('ingestOne sin datos de CIMA (offline / CN desconocido): entra igual, pendiente de completar', async () => {
  const created = await ingest.ingestOne('910002');
  assert.equal(created, true);
  const med = glDb.getByCn('910002');
  assert.ok(med, 'nada se pierde: el CN se guarda aunque CIMA no responda');
  assert.equal(med.nombre, null);
  assert.ok(med.gtin, 'el GTIN se deriva matemáticamente del CN, sin depender de CIMA');
  assert.ok(med.barcode, 'el código de barras también se deriva matemáticamente');
});

test('un CN que YA está en Galénica no se vuelve a tocar — "solo miran"', async () => {
  // Editado a mano (como haría un usuario en la propia app de Galénica).
  glDb.updateMed(glDb.getByCn('910001').id, { color: 'azul', notes: 'ranurada' });
  dmDb.cimaCachePut('910001', { nombre: 'NOMBRE DISTINTO SI SE REPITIERA', pactivos: 'OTRO' });
  const created = await ingest.ingestOne('910001');
  assert.equal(created, false, 'no crea (ya existía) ni lo toca');
  const med = glDb.getByCn('910001');
  assert.equal(med.color, 'azul', 'lo editado a mano sobrevive a que DM/Asignación vuelvan a ver el mismo CN');
  assert.equal(med.nombre, 'MEDICAMENTO PRUEBA A', 'tampoco se refresca el nombre — Galénica ya es dueña de su ficha');
});

test('ingestCn es fire-and-forget: no bloquea y valida el CN antes de tocar nada', async () => {
  const before = Date.now();
  const ret = ingest.ingestCn('abc');   // CN no numérico → no-op inmediato
  assert.equal(ret, undefined);
  assert.ok(Date.now() - before < 20, 'no debe esperar a ninguna llamada de red para un CN inválido');
  assert.equal(glDb.getByCn('abc'), null);

  dmDb.cimaCachePut('910003', { nombre: 'MEDICAMENTO PRUEBA C' });
  ingest.ingestCn('910003');   // no se espera — igual que lo llamarían las rutas de DM/Asignación
  await new Promise(r => setTimeout(r, 50));
  const med = glDb.getByCn('910003');
  assert.ok(med, 'el CN entra en Galénica aunque el llamador no haya esperado la promesa');
  assert.equal(med.nombre, 'MEDICAMENTO PRUEBA C');
});

test('backfillFrom: incorpora los CN que ya existían y no toca los que ya están', async () => {
  dmDb.cimaCachePut('910004', { nombre: 'MEDICAMENTO PRUEBA D' });
  await ingest.backfillFrom('test', ['910001', '910004', 'no-es-un-cn']);
  assert.ok(glDb.getByCn('910004'), 'el CN nuevo se incorpora');
  assert.equal(glDb.getByCn('910001').color, 'azul', 'el CN ya existente no se vuelve a tocar');
});

test('backfillAll: recorre Asignación y luego Data Matrix, sin duplicar lo que ya estaba', async () => {
  asigDb.addPlanMed(1, { cn: '910005', nombre: 'DESDE ASIGNACIÓN', qty: 1 });
  dmDb.upsertProduct('08470001234567', { cn: '910006' });
  dmDb.cimaCachePut('910005', { nombre: 'MEDICAMENTO PRUEBA E' });
  dmDb.cimaCachePut('910006', { nombre: 'MEDICAMENTO PRUEBA F' });

  await ingest.backfillAll();

  const fromAsig = glDb.getByCn('910005');
  const fromDm = glDb.getByCn('910006');
  assert.ok(fromAsig, 'el CN que solo estaba en el plan de Asignación se incorpora');
  assert.equal(fromAsig.nombre, 'MEDICAMENTO PRUEBA E');
  assert.ok(fromDm, 'el CN que solo estaba en el catálogo de Data Matrix se incorpora');
  assert.equal(fromDm.nombre, 'MEDICAMENTO PRUEBA F');
  // Segunda pasada: nada nuevo, nada tocado (idempotente).
  glDb.updateMed(fromAsig.id, { color: 'verde' });
  await ingest.backfillAll();
  assert.equal(glDb.getByCn('910005').color, 'verde', 'una segunda pasada no pisa lo ya resuelto');
});
