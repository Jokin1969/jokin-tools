const { test } = require('node:test');
const assert = require('node:assert');
const cima = require('../apps/datamatrix/cima');

// ── Barcode / GTIN math ──────────────────────────────────────────────────────────
test('ean13CheckDigit matches a known EAN-13', () => {
  assert.equal(cima.ean13CheckDigit('400638133393'), 1);   // 4006381333931
  assert.equal(cima.ean13CheckDigit('847000654321'), 4);   // 8470006543214
  assert.equal(cima.ean13CheckDigit('bad'), null);
});

test('barcode / gtin derive from a 6-digit CN and round-trip back', () => {
  assert.equal(cima.barcodeFromCn('654321'), '8470006543214');
  assert.equal(cima.gtinFromCn('654321'), '08470006543214');
  assert.equal(cima.cnFromBarcode('8470006543214'), '654321');
  // 7-digit CNs use the 84700 prefix (handled by gs1).
  const b7 = cima.barcodeFromCn('6543210');
  assert.match(b7, /^84700\d{8}$/);
  assert.equal(cima.gtinFromCn('6543210').length, 14);
  // Empty / invalid → null.
  assert.equal(cima.barcodeFromCn(''), null);
  assert.equal(cima.cnFromBarcode('1234567890123'), null);
});

// ── Mapping a CIMA "medicamento" response ─────────────────────────────────────────
const SAMPLE = {
  nregistro: '65432',
  nombre: 'IBUPROFENO NORMON 600 mg COMPRIMIDOS EFG',
  pactivos: 'IBUPROFENO',
  labtitular: 'LABORATORIOS NORMON, S.A.',
  comerc: true,
  presentaciones: [
    { cn: '654321', nombre: 'IBUPROFENO NORMON 600 mg EFG, 40 comprimidos', comerc: true },
    { cn: '654999', nombre: 'IBUPROFENO NORMON 600 mg EFG, 500 comprimidos', comerc: true },
  ],
  fotos: [
    { tipo: 'materialas', url: 'https://cima.aemps.es/cima/fotos/thumbnails/materialas/65432/65432_materialas.jpg' },
    { tipo: 'formafarmac', url: 'https://cima.aemps.es/cima/fotos/thumbnails/formafarmac/65432/65432_formafarmac.jpg' },
  ],
};

test('mapMedicamento picks the exact presentation by CN and derives the barcode', () => {
  const m = cima.mapMedicamento(SAMPLE, '654321');
  assert.equal(m.cn, '654321');           // presentation CN, NOT the nregistro
  assert.notEqual(m.cn, m.nregistro);
  assert.match(m.nombre, /40 comprimidos/);
  assert.equal(m.barcode, '8470006543214');
  assert.equal(m.gtin, '08470006543214');
  assert.equal(m.pactivos, 'IBUPROFENO');
  assert.equal(m.labtitular, 'LABORATORIOS NORMON, S.A.');
  assert.equal(m.source, 'cima');
});

test('mapMedicamento extracts box and pill photos (thumb + full)', () => {
  const m = cima.mapMedicamento(SAMPLE, '654321');
  assert.ok(m.fotos.caja && m.fotos.pastilla, 'both photos present');
  assert.match(m.fotos.caja.thumb, /materialas/);
  assert.match(m.fotos.caja.full, /\/full\/materialas\//);   // full-size swaps the folder
  assert.match(m.fotos.pastilla.thumb, /formafarmac/);
});

// A fake fetch that returns a canned JSON (no network).
const fakeFetch = (payload, ok = true, status = 200) => async () => ({ ok, status, json: async () => payload });

test('lookupByCn maps a mocked CIMA response', async () => {
  const m = await cima.lookupByCn('654321', { fetchImpl: fakeFetch(SAMPLE) });
  assert.equal(m.cn, '654321');
  assert.equal(m.barcode, '8470006543214');
});

test('lookupByCn rejects an invalid Código Nacional (400)', async () => {
  await assert.rejects(() => cima.lookupByCn('abc', { fetchImpl: fakeFetch(SAMPLE) }), (e) => e.status === 400);
});

test('lookupByCn surfaces an offline error when CIMA is unreachable', async () => {
  const boom = async () => { throw new Error('ENOTFOUND'); };
  await assert.rejects(() => cima.lookupByCn('654321', { fetchImpl: boom }), (e) => e.offline === true && e.status === 502);
  const http500 = fakeFetch({}, false, 500);
  await assert.rejects(() => cima.lookupByCn('654321', { fetchImpl: http500 }), (e) => e.offline === true);
});

test('searchByName maps CIMA text-search results to presentations', async () => {
  const payload = { totalFilas: 1, resultados: [SAMPLE] };
  const items = await cima.searchByName('ibuprofeno normon', { fetchImpl: fakeFetch(payload) });
  assert.ok(items.length >= 2, 'one row per presentation');
  assert.equal(items[0].cn, '654321');
  assert.equal(items[0].barcode, '8470006543214');
  // Short queries are ignored (no network call).
  assert.deepEqual(await cima.searchByName('ib'), []);
});
