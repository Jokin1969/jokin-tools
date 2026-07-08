const { test } = require('node:test');
const assert = require('node:assert');
const sharp = require('sharp');
const { PDFDocument } = require('pdf-lib');
const wm = require('../apps/batchwork/server/operations/watermark');

const LAYOUTS = ['diagonal', 'diagonal-rep', 'mosaico', 'centro', 'pie', 'esquina'];
const textOpts = (o = {}) => ({ kind: 'text', text: 'CONFIDENCIAL', colorSvg: '#cc1a1a', colorPdf: [0.8, 0.1, 0.1], layout: 'diagonal', sizeScale: 1, opacity: 0.3, ...o });

async function pngLogo() {
  return sharp({ create: { width: 120, height: 70, channels: 4, background: { r: 220, g: 30, b: 30, alpha: 1 } } }).png().toBuffer();
}
function tmpImage(buf, name) {
  const fs = require('fs'), os = require('os'), path = require('path');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-'));
  const p = path.join(dir, name);
  fs.writeFileSync(p, buf);
  return { p, dir, rm: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

test('outputName: sufijo _watermarked_ conservando extensión', () => {
  assert.equal(wm.outputName('contrato.pdf'), 'contrato_watermarked_.pdf');
  assert.equal(wm.outputName('foto.JPG'), 'foto_watermarked_.JPG');
});

test('placements: centro=1, mosaico=varios', () => {
  assert.equal(wm.placements('centro', 600, 400, 100, 30).length, 1);
  assert.ok(wm.placements('mosaico', 600, 400, 100, 30).length > 5);
});

test('watermarkPdf (texto): válido y conserva páginas en los 6 layouts', async () => {
  const doc = await PDFDocument.create(); doc.addPage([595, 842]); doc.addPage([842, 595]);
  const src = Buffer.from(await doc.save());
  for (const layout of LAYOUTS) {
    const out = await wm.watermarkPdf(src, textOpts({ layout }));
    assert.equal(out.slice(0, 5).toString(), '%PDF-');
    assert.equal((await PDFDocument.load(out)).getPageCount(), 2, `${layout}`);
    assert.ok(out.length > src.length);
  }
});

test('watermarkPdf (texto): emoji/no-WinAnsi no rompe', async () => {
  const doc = await PDFDocument.create(); doc.addPage([400, 400]);
  const out = await wm.watermarkPdf(Buffer.from(await doc.save()), textOpts({ text: 'COPIA 🔒 café' }));
  assert.equal(out.slice(0, 5).toString(), '%PDF-');
});

test('watermarkImage (texto): el texto se renderiza (píxeles oscuros)', async () => {
  const { p, rm } = tmpImage(await sharp({ create: { width: 600, height: 400, channels: 3, background: { r: 255, g: 255, b: 255 } } }).png().toBuffer(), 'b.png');
  const out = await wm.watermarkImage(p, textOpts({ colorSvg: '#000000', opacity: 0.9, layout: 'diagonal' }));
  const stats = await sharp(out).stats();
  assert.ok(Math.min(...stats.channels.map(c => c.min)) < 60);
  rm();
});

test('watermarkImage (texto): conserva formato y dimensiones (JPEG)', async () => {
  const { p, rm } = tmpImage(await sharp({ create: { width: 500, height: 300, channels: 3, background: { r: 210, g: 225, b: 240 } } }).jpeg().toBuffer(), 'f.jpg');
  const m = await sharp(await wm.watermarkImage(p, textOpts({ layout: 'mosaico' }))).metadata();
  assert.equal(m.format, 'jpeg'); assert.equal(m.width, 500); assert.equal(m.height, 300);
  rm();
});

test('logo en imagen: se compone (cambia la imagen) y conserva dimensiones', async () => {
  const logoBuf = await pngLogo();
  const { p, rm } = tmpImage(await sharp({ create: { width: 500, height: 500, channels: 3, background: { r: 255, g: 255, b: 255 } } }).png().toBuffer(), 'w.png');
  const out = await wm.watermarkImage(p, { kind: 'logo', logoBuf, layout: 'centro', sizeScale: 1, opacity: 0.85 });
  const stats = await sharp(out).stats();
  const m = await sharp(out).metadata();
  assert.equal(m.width, 500); assert.equal(m.height, 500);
  assert.ok(stats.channels[0].mean > stats.channels[2].mean, 'el logo rojo tiñe de rojo (R>B)');
  rm();
});

test('logo en PDF: embed PNG, PDF válido y conserva páginas', async () => {
  const logoBuf = await pngLogo();
  const doc = await PDFDocument.create(); doc.addPage([500, 700]); doc.addPage([700, 500]);
  const out = await wm.watermarkPdf(Buffer.from(await doc.save()), { kind: 'logo', logoBuf, layout: 'mosaico', sizeScale: 1, opacity: 0.4 });
  assert.equal(out.slice(0, 5).toString(), '%PDF-');
  assert.equal((await PDFDocument.load(out)).getPageCount(), 2);
});

test('buildOverlaySvg: texto y logo', async () => {
  const t = await wm.buildOverlaySvg(400, 300, textOpts({ text: 'PRUEBA', layout: 'centro' }));
  assert.ok(t.startsWith('<svg') && t.includes('PRUEBA'));
  const l = await wm.buildOverlaySvg(400, 300, { kind: 'logo', logoBuf: await pngLogo(), layout: 'centro', sizeScale: 1, opacity: 0.5 });
  assert.ok(l.includes('<image') && l.includes('data:image/png;base64,'));
});
