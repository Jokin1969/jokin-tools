const { test } = require('node:test');
const assert = require('node:assert');
const os = require('os');
const path = require('path');
const fs = require('fs');

// Isolate the datamatrix DB before requiring the modules.
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cimacache-'));
process.env.DM_DB_PATH = path.join(dir, 'dm.db');
process.env.DB_PATH = path.join(dir, 'auth.db');

const db = require('../apps/datamatrix/db');
const cc = require('../apps/datamatrix/cima-cache');

const SAMPLE = {
  nregistro: '65498', nombre: 'IXIA 10 mg COMPRIMIDOS RECUBIERTOS', pactivos: 'OLMESARTAN MEDOXOMILO',
  labtitular: 'Menarini', comerc: true,
  presentaciones: [{ cn: '885442', nombre: 'IXIA 10 mg COMPRIMIDOS RECUBIERTOS , 28 comprimidos' }],
  fotos: [
    { tipo: 'materialas', url: 'https://cima.aemps.es/cima/fotos/thumbnails/materialas/65498/65498_materialas.jpg' },
    { tipo: 'formafarmac', url: 'https://cima.aemps.es/cima/fotos/thumbnails/formafarmac/65498/65498_formafarmac.jpg' },
  ],
};
// A fake fetch: medicamento JSON for the API, some bytes for image URLs.
const online = async (url) => {
  if (url.includes('/medicamento?cn=')) return { ok: true, json: async () => SAMPLE };
  if (/materialas|formafarmac/.test(url)) return { ok: true, arrayBuffer: async () => new Uint8Array([137, 80, 78, 71]).buffer };
  return { ok: false, status: 404 };
};

test('lookupByCnCached: stores data + images, falls back offline, and serves photos', async () => {
  const item = await cc.lookupByCnCached('885442', { fetchImpl: online });
  assert.equal(item.cached, false);
  assert.equal(item.cn, '885442');
  assert.equal(item.barcode, '8470008854424');

  // Persisted in the cache with both images.
  const row = db.cimaCacheGet('885442');
  assert.ok(row && row.nombre.startsWith('IXIA'));
  assert.equal(row.has_caja, 1);
  assert.equal(row.has_pastilla, 1);

  // CIMA down → served from cache.
  const offline = async () => { throw new Error('ENET'); };
  const cached = await cc.lookupByCnCached('885442', { fetchImpl: offline });
  assert.equal(cached.cached, true);
  assert.equal(cached.nombre, item.nombre);
  assert.ok(cached.fotos.caja, 'cached item still reports its photo');

  // Photo bytes come back from the cache.
  const buf = await cc.foto('885442', 'caja');
  assert.ok(Buffer.isBuffer(buf) && buf.length > 0);

  // Unknown CN while offline → rethrows the offline error.
  await assert.rejects(() => cc.lookupByCnCached('999999', { fetchImpl: offline }), (e) => e.offline === true);
});
