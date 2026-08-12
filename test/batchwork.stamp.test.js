const { test } = require('node:test');
const assert = require('node:assert');
const { useTempDb } = require('./helpers');

useTempDb();
const render = require('../apps/batchwork/server/stamp-render');
const store = require('../apps/batchwork/server/stamp-store');

test('sanitizeConfig: defaults + clamping', () => {
  const c = render.sanitizeConfig({});
  assert.equal(c.shape, 'circle');
  assert.equal(c.texture, 'entintado');
  assert.equal(c.bg, 'transparent');
  assert.equal(c.ink, '#1B3A8C');
  // unknown shape/texture fall back; out-of-range clamps
  const c2 = render.sanitizeConfig({ shape: 'nope', texture: 'nope', intensity: 999, rotation: 90, borderWidth: 99 });
  assert.equal(c2.shape, 'circle');
  assert.equal(c2.texture, 'entintado');
  assert.equal(c2.intensity, 100);
  assert.equal(c2.rotation, 20);
  assert.equal(c2.borderWidth, 3);
});

test('buildSvg: valid SVG for every shape and texture', () => {
  for (const shape of render.SHAPE_IDS) {
    for (const texture of render.TEXTURE_IDS) {
      const { svg } = render.buildSvg({
        shape, texture, intensity: 60,
        topText: 'Fundación Española', bottomText: 'Enfermedades Priónicas', centerText: 'FEEP\n2026',
      });
      assert.ok(svg.startsWith('<svg'), `svg for ${shape}/${texture}`);
      assert.ok(svg.includes('</svg>'));
      // arc text is rendered glyph-by-glyph as <text> (librsvg has no textPath)
      assert.ok(svg.includes('<text'), `has text ${shape}/${texture}`);
    }
  }
});

test('buildSvg: deterministic for the same config', () => {
  const cfg = { shape: 'doubleCircle', topText: 'A', bottomText: 'B', centerText: 'C', texture: 'desgastado' };
  assert.equal(render.buildSvg(cfg).svg, render.buildSvg(cfg).svg);
});

test('previews: shapes and textures render', () => {
  assert.equal(render.shapePreviews().length, render.SHAPE_IDS.length);
  assert.equal(render.texturePreviews().length, render.TEXTURE_IDS.length);
  assert.ok(render.shapePreviews()[0].svg.startsWith('<svg'));
  assert.ok(Array.isArray(render.INK_PRESETS) && render.INK_PRESETS.length > 0);
});

test('export: PNG and SVG buffers', async () => {
  const cfg = { shape: 'circle', topText: 'SELLO', centerText: 'FEEP', texture: 'limpio' };
  const png = await render.exportConfig(cfg, 'png', {});
  assert.equal(png.ext, 'png');
  assert.equal(png.buffer.slice(1, 4).toString('latin1'), 'PNG');
  const svg = await render.exportConfig(cfg, 'svg', {});
  assert.equal(svg.mime, 'image/svg+xml');
  assert.ok(svg.buffer.toString('utf8').startsWith('<svg'));
});

test('inkifyLogo + buildSvgAsync: a central logo becomes an inked silhouette', async () => {
  const sharp = require('sharp');
  const logo = 'data:image/png;base64,' + (await sharp({
    create: { width: 24, height: 24, channels: 4, background: { r: 20, g: 20, b: 20, alpha: 1 } },
  }).png().toBuffer()).toString('base64');

  const inked = await render.inkifyLogo(logo, '#1B3A8C');
  assert.match(inked, /^data:image\/png;base64,/);
  assert.notEqual(inked, logo, 'logo is re-processed to ink');

  const { svg } = await render.buildSvgAsync({ shape: 'circle', topText: 'FEEP', logo, logoInk: true, ink: '#1B3A8C' });
  assert.ok(svg.includes('<image'), 'inked logo embedded');

  const { svg: svgOrig } = await render.buildSvgAsync({ shape: 'circle', logo, logoInk: false });
  assert.ok(svgOrig.includes('<image'), 'original logo embedded when not inked');
});

test('store: create/list/get/delete, scoped per user', () => {
  const cfg = { shape: 'doubleCircle', topText: 'FEEP', centerText: 'Oficial', texture: 'entintado' };
  const s = store.create({ name: 'Mi sello', subtitle: 'FEEP · Oficial', config: cfg, thumb: '<svg/>' }, 7);
  assert.equal(s.name, 'Mi sello');
  assert.deepEqual(s.config.shape, 'doubleCircle');

  const list7 = store.list(7);
  assert.equal(list7.length, 1);
  assert.equal(list7[0].subtitle, 'FEEP · Oficial');
  assert.equal(store.list(9).length, 0, 'per-user isolation');
  assert.equal(store.get(s.id, 9), null);

  assert.equal(store.remove(s.id, 7), true);
  assert.equal(store.list(7).length, 0);
});

test('store: systematic name when none given', () => {
  const s = store.create({ config: {} }, 4);
  assert.match(s.name, /^Sello-\d{8}-\d{3}$/);
});
