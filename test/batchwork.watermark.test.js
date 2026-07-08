const { test } = require('node:test');
const assert = require('node:assert');
const sharp = require('sharp');
const { PDFDocument } = require('pdf-lib');
const wm = require('../apps/batchwork/server/operations/watermark');

test('outputName: sufijo _watermarked_ conservando extensión', () => {
  assert.equal(wm.outputName('contrato.pdf'), 'contrato_watermarked_.pdf');
  assert.equal(wm.outputName('foto.JPG'), 'foto_watermarked_.JPG');
  assert.equal(wm.outputName('sin_ext'), 'sin_ext_watermarked_');
});

test('watermarkPdf: PDF válido, conserva páginas, más grande, en los 3 estilos', async () => {
  const doc = await PDFDocument.create();
  doc.addPage([595, 842]); doc.addPage([842, 595]);
  const src = Buffer.from(await doc.save());
  for (const style of ['diagonal', 'tiled', 'footer']) {
    const out = await wm.watermarkPdf(src, { text: 'CONFIDENCIAL', style, colorPdf: [0.8, 0.1, 0.1], opacity: 0.25 });
    assert.equal(out.slice(0, 5).toString(), '%PDF-');
    const reload = await PDFDocument.load(out);
    assert.equal(reload.getPageCount(), 2, `${style}: mantiene páginas`);
    assert.ok(out.length > src.length, `${style}: añade contenido`);
  }
});

test('watermarkPdf: texto con emoji/no-WinAnsi no rompe (se sanea)', async () => {
  const doc = await PDFDocument.create(); doc.addPage([400, 400]);
  const src = Buffer.from(await doc.save());
  const out = await wm.watermarkPdf(src, { text: 'COPIA 🔒 café', style: 'diagonal', colorPdf: [0, 0, 0], opacity: 0.3 });
  assert.equal(out.slice(0, 5).toString(), '%PDF-');
});

test('watermarkImage: el texto se renderiza (píxeles oscuros sobre blanco)', async () => {
  const fs = require('fs'), os = require('os'), path = require('path');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const inPng = path.join(dir, 'blanco.png');
  fs.writeFileSync(inPng, await sharp({ create: { width: 600, height: 400, channels: 3, background: { r: 255, g: 255, b: 255 } } }).png().toBuffer());
  const out = await wm.watermarkImage(inPng, { text: 'CONFIDENCIAL', style: 'diagonal', colorSvg: '#000000', opacity: 0.9 });
  const stats = await sharp(out).stats();
  const minCh = Math.min(...stats.channels.map(c => c.min));
  assert.ok(minCh < 60, `hay píxeles oscuros (texto): min=${minCh}`);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('watermarkImage: conserva formato y dimensiones (JPEG)', async () => {
  const fs = require('fs'), os = require('os'), path = require('path');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const inJpg = path.join(dir, 'foto.jpg');
  fs.writeFileSync(inJpg, await sharp({ create: { width: 500, height: 300, channels: 3, background: { r: 200, g: 220, b: 240 } } }).jpeg().toBuffer());
  const out = await wm.watermarkImage(inJpg, { text: 'BORRADOR', style: 'tiled', colorSvg: '#cc1a1a', opacity: 0.3 });
  const m = await sharp(out).metadata();
  assert.equal(m.format, 'jpeg');
  assert.equal(m.width, 500); assert.equal(m.height, 300);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('buildWatermarkSvg incluye el texto y es SVG', () => {
  const svg = wm.buildWatermarkSvg(400, 300, { text: 'PRUEBA', style: 'diagonal', color: '#808080', opacity: 0.25 });
  assert.ok(svg.startsWith('<svg') && svg.includes('PRUEBA'));
});
