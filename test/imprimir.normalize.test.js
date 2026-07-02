const { test } = require('node:test');
const assert = require('node:assert');
const sharp = require('sharp');
const { kindOf, toPdf, imageToPdf } = require('../apps/imprimir/normalize');

const isPdf = (buf) => Buffer.isBuffer(buf) && buf.slice(0, 5).toString() === '%PDF-';

test('kindOf detecta pdf / png / jpg / docx y descarta el resto', () => {
  assert.equal(kindOf('a.pdf', 'application/pdf'), 'pdf');
  assert.equal(kindOf('a.PNG', ''), 'png');
  assert.equal(kindOf('foto.jpg', ''), 'jpg');
  assert.equal(kindOf('x', 'image/jpeg'), 'jpg');
  assert.equal(kindOf('carta.docx', 'application/octet-stream'), 'docx');
  assert.equal(kindOf('nota.txt', 'text/plain'), null);
});

test('PDF pasa tal cual', async () => {
  const pdf = Buffer.from('%PDF-1.4 real\n%%EOF');
  const out = await toPdf({ filename: 'x.pdf', mime: 'application/pdf', content: pdf });
  assert.deepEqual(out.buffer, pdf);
  assert.equal(out.kind, 'pdf');
});

test('PNG → PDF (una página, empieza por %PDF)', async () => {
  const png = await sharp({ create: { width: 40, height: 30, channels: 3, background: { r: 200, g: 100, b: 50 } } }).png().toBuffer();
  const out = await toPdf({ filename: 'foto.png', mime: 'image/png', content: png });
  assert.ok(isPdf(out.buffer), 'genera un PDF válido');
  assert.ok(out.buffer.length > 100);
});

test('JPG → PDF', async () => {
  const jpg = await sharp({ create: { width: 50, height: 20, channels: 3, background: { r: 10, g: 20, b: 30 } } }).jpeg().toBuffer();
  const out = await toPdf({ filename: 'foto.jpg', mime: 'image/jpeg', content: jpg });
  assert.ok(isPdf(out.buffer));
});

test('imageToPdf directo también produce PDF', async () => {
  const png = await sharp({ create: { width: 10, height: 10, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 1 } } }).png().toBuffer();
  assert.ok(isPdf(await imageToPdf(png)));
});

test('DOCX usa el convertidor (inyectado) y devuelve su PDF', async () => {
  const fakePdf = Buffer.from('%PDF-1.4 convertido por libreoffice');
  let called = null;
  const out = await toPdf(
    { filename: 'carta.docx', mime: 'application/octet-stream', content: Buffer.from('PKfakedocx') },
    { convertDocx: async (buf, name) => { called = name; return fakePdf; } },
  );
  assert.equal(called, 'carta.docx', 'se llama al convertidor con el nombre');
  assert.deepEqual(out.buffer, fakePdf);
  assert.equal(out.kind, 'docx');
});

test('tipo no soportado lanza error', async () => {
  await assert.rejects(
    () => toPdf({ filename: 'nota.txt', mime: 'text/plain', content: Buffer.from('hi') }),
    /no soportado/i,
  );
});

test('adjunto vacío lanza error', async () => {
  await assert.rejects(
    () => toPdf({ filename: 'x.pdf', mime: 'application/pdf', content: Buffer.alloc(0) }),
    /vac/i,
  );
});
