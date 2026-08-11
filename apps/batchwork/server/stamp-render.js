'use strict';

// ── Rubber-stamp rendering core ─────────────────────────────────────────────────
// Builds a print-shop-style stamp as SVG — round / oval / rectangular, an outer
// border (single or double), curved "arc" text that borders the emblem (top &
// bottom), centre text lines and/or a central logo, and inner divider lines — then
// applies a procedural INK TEXTURE (feTurbulence) so it looks like a real rubber
// stamp pressed on paper and scanned. Rasterises to PNG/JPEG/WEBP via sharp and to
// PDF via pdfkit. Pure & deterministic (the texture seed derives from the text, so
// a saved stamp always re-renders identically).

// ── Shapes / textures ────────────────────────────────────────────────────────────
const SHAPES = {
  circle:       { label: 'Círculo',        round: true },
  doubleCircle: { label: 'Círculo doble',  round: true, double: true },
  oval:         { label: 'Óvalo',          round: true, oval: true },
  rounded:      { label: 'Rectángulo redondeado', round: false, rx: 26 },
  rect:         { label: 'Rectángulo',     round: false, rx: 0 },
};
const SHAPE_IDS = Object.keys(SHAPES);

// Each texture is a distress recipe for the feTurbulence filter. `cover` is the
// alpha-threshold slope: lower removes more ink. rough displaces the edges.
const TEXTURES = {
  limpio:     { label: 'Limpio',      freq: 0,    cover: 0,    rough: 0,   blur: 0 },
  entintado:  { label: 'Entintado',   freq: 0.75, cover: 0.55, rough: 0.4, blur: 0.15 },
  desgastado: { label: 'Desgastado',  freq: 0.9,  cover: 1.0,  rough: 0.8, blur: 0.2 },
  escaneado:  { label: 'Escaneado',   freq: 1.15, cover: 0.75, rough: 1.1, blur: 0.35 },
};
const TEXTURE_IDS = Object.keys(TEXTURES);

const INK_PRESETS = ['#1B3A8C', '#B0201F', '#1A1A1A', '#1F6B3B', '#5B2A86'];

// ── Helpers ─────────────────────────────────────────────────────────────────────
const HEX_RE = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;
function color(value, fallback) {
  return (typeof value === 'string' && HEX_RE.test(value.trim())) ? value.trim() : fallback;
}
const n = (x) => { const r = Math.round(x * 1000) / 1000; return String(r); };
function escapeXml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
// Small stable seed from a string (so texture + arc are deterministic per stamp).
function seedFrom(s) {
  let h = 2166136261;
  const str = String(s || 'sello');
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return Math.abs(h) % 1000;
}

// ── Config sanitiser ────────────────────────────────────────────────────────────
function sanitizeConfig(input = {}) {
  const shape = SHAPE_IDS.includes(input.shape) ? input.shape : 'circle';
  const texture = TEXTURE_IDS.includes(input.texture) ? input.texture : 'entintado';
  const hasLogo = typeof input.logo === 'string' && /^data:image\//i.test(input.logo);
  return {
    shape,
    ink: color(input.ink || input.fg, '#1B3A8C'),
    bg: input.bg === 'transparent' || input.bg == null ? 'transparent' : color(input.bg, '#ffffff'),
    border: input.border != null ? !!input.border : true,
    borderWidth: Math.min(3, Math.max(0.6, Number(input.borderWidth) || 1.6)),
    innerLines: !!input.innerLines,
    topText: String(input.topText || '').slice(0, 60),
    bottomText: String(input.bottomText || '').slice(0, 60),
    centerText: String(input.centerText || '').slice(0, 120),
    arcSize: Math.min(2, Math.max(0.6, Number(input.arcSize) || 1)),
    centerSize: Math.min(2.2, Math.max(0.5, Number(input.centerSize) || 1)),
    separator: ['star', 'dot', 'none'].includes(input.separator) ? input.separator : 'star',
    logo: hasLogo ? input.logo : null,
    logoScale: Math.min(70, Math.max(15, Number(input.logoScale) || 40)),
    texture,
    intensity: Math.min(100, Math.max(0, input.intensity == null ? 55 : Number(input.intensity))),
    rotation: Math.min(20, Math.max(-20, Number(input.rotation) || 0)),
  };
}

// ── Geometry ──────────────────────────────────────────────────────────────────────
const VB = 300;            // viewBox size
const C = VB / 2;          // centre

function polar(cx, cy, r, deg) {
  const a = (deg * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}
const FONT = 'DejaVu Sans, Verdana, Arial, sans-serif';

// Curved text, glyph by glyph (librsvg doesn't render <textPath>). `r` is the
// BASELINE radius. `side` is 'top' (letters point outward over the top, reading
// L→R) or 'bottom' (upright along the lower arc, reading L→R).
function arcTextSvg(str, cx, cy, r, side, fs, ink) {
  const chars = [...String(str).toUpperCase()];
  if (!chars.length) return '';
  const nch = chars.length;
  const ap = ((fs * 0.64) / r) * (180 / Math.PI);   // degrees per glyph
  const spread = (nch - 1) * ap;
  let out = '';
  for (let i = 0; i < nch; i++) {
    if (chars[i] === ' ') continue;
    // 90° = bottom, 270°/-90° = top (SVG y-down). Standard circular-text layout.
    const a = side === 'top'
      ? (-90 - spread / 2) + i * ap
      : (90 + spread / 2) - i * ap;
    const rad = (a * Math.PI) / 180;
    const x = cx + r * Math.cos(rad);
    const y = cy + r * Math.sin(rad);
    const rot = side === 'top' ? a + 90 : a - 90;
    out += `<text x="${n(x)}" y="${n(y)}" transform="rotate(${n(rot)} ${n(x)} ${n(y)})" `
      + `text-anchor="middle" font-family="${FONT}" font-weight="700" font-size="${n(fs)}" `
      + `fill="${ink}">${escapeXml(chars[i])}</text>`;
  }
  return out;
}

// ── SVG builder ─────────────────────────────────────────────────────────────────
function buildSvg(cfgInput) {
  const cfg = cfgInput.__sanitized ? cfgInput : sanitizeConfig(cfgInput);
  const sh = SHAPES[cfg.shape];
  const ink = cfg.ink;
  const uid = 's' + seedFrom(cfg.topText + '|' + cfg.bottomText + '|' + cfg.centerText + '|' + cfg.shape);
  const seed = seedFrom(cfg.topText + cfg.bottomText + cfg.texture + cfg.shape);

  // Radii / box
  const rx = sh.oval ? 142 : 138;
  const ry = sh.oval ? 108 : 138;
  const bw = cfg.borderWidth;

  let ink_svg = ''; // everything drawn in ink colour (gets the texture filter)

  // ── Border(s) ──
  if (cfg.border) {
    if (sh.round) {
      ink_svg += `<ellipse cx="${C}" cy="${C}" rx="${n(rx)}" ry="${n(ry)}" fill="none" stroke="${ink}" stroke-width="${n(bw * 2.4)}"/>`;
      if (sh.double) {
        ink_svg += `<ellipse cx="${C}" cy="${C}" rx="${n(rx - 10)}" ry="${n(ry - 10)}" fill="none" stroke="${ink}" stroke-width="${n(bw)}"/>`;
      }
    } else {
      const m = 14;
      ink_svg += `<rect x="${m}" y="${m}" width="${n(VB - 2 * m)}" height="${n(VB - 2 * m)}" rx="${n(sh.rx)}" fill="none" stroke="${ink}" stroke-width="${n(bw * 2.4)}"/>`;
    }
  }

  // ── Arc / straight border text ──
  const arcFs = 20 * cfg.arcSize;
  if (sh.round) {
    const ring = sh.double ? ry - 10 : ry;
    // Top letters extend outward from their baseline, bottom letters inward — so
    // the baselines sit at different radii to keep both bands the same distance
    // from the rim.
    if (cfg.topText) ink_svg += arcTextSvg(cfg.topText, C, C, ring - arcFs * 1.05, 'top', arcFs, ink);
    if (cfg.bottomText) ink_svg += arcTextSvg(cfg.bottomText, C, C, ring - arcFs * 0.2, 'bottom', arcFs, ink);
    // side separators (where the two arcs meet)
    if (cfg.separator !== 'none' && (cfg.topText || cfg.bottomText)) {
      const rSep = ring;
      for (const deg of [0, 180]) {
        const [sx, sy] = polar(C, C, rSep - arcFs * 0.55, deg);
        ink_svg += cfg.separator === 'star'
          ? starPath(sx, sy, arcFs * 0.42, ink)
          : `<circle cx="${n(sx)}" cy="${n(sy)}" r="${n(arcFs * 0.18)}" fill="${ink}"/>`;
      }
    }
  } else {
    // rectangle: straight text near top & bottom
    if (cfg.topText) ink_svg += `<text x="${C}" y="${n(38 + arcFs * 0.4)}" text-anchor="middle" font-family="${FONT}" font-weight="700" font-size="${n(arcFs)}" fill="${ink}" letter-spacing="1">${escapeXml(cfg.topText.toUpperCase())}</text>`;
    if (cfg.bottomText) ink_svg += `<text x="${C}" y="${n(VB - 30)}" text-anchor="middle" font-family="${FONT}" font-weight="700" font-size="${n(arcFs)}" fill="${ink}" letter-spacing="1">${escapeXml(cfg.bottomText.toUpperCase())}</text>`;
  }

  // ── Inner divider lines (classic) ──
  if (cfg.innerLines) {
    const half = sh.round ? Math.min(rx, ry) * 0.66 : (VB / 2 - 40);
    for (const dy of [-46, 46]) {
      ink_svg += `<line x1="${n(C - half)}" y1="${n(C + dy)}" x2="${n(C + half)}" y2="${n(C + dy)}" stroke="${ink}" stroke-width="${n(bw * 1.1)}"/>`;
    }
  }

  // ── Centre logo + centre text ──
  let logoBottom = C;
  if (cfg.logo) {
    const s = (cfg.logoScale / 100) * VB * 0.5;
    const cy = cfg.centerText ? C - (cfg.centerText.split('\n').length * 8) : C;
    ink_svg += `<image x="${n(C - s / 2)}" y="${n(cy - s / 2)}" width="${n(s)}" height="${n(s)}" href="${cfg.logo}" preserveAspectRatio="xMidYMid meet"/>`;
    logoBottom = cy + s / 2;
  }
  if (cfg.centerText) {
    const lines = cfg.centerText.split('\n').slice(0, 4);
    const fs = 22 * cfg.centerSize;
    const lh = fs * 1.12;
    const startY = cfg.logo ? logoBottom + fs : C - ((lines.length - 1) * lh) / 2 + fs * 0.34;
    lines.forEach((ln, i) => {
      ink_svg += `<text x="${C}" y="${n(startY + i * lh)}" text-anchor="middle" font-family="${FONT}" font-weight="800" font-size="${n(fs)}" fill="${ink}" letter-spacing="0.5">${escapeXml(ln)}</text>`;
    });
  }

  // ── Texture filter ──
  const tx = TEXTURES[cfg.texture];
  let filterDef = '';
  let filterAttr = '';
  if (tx.freq > 0 && cfg.intensity > 0) {
    const k = cfg.intensity / 100;                 // 0..1
    const slope = -(1.1 + tx.cover * 1.8 * k);     // steeper → more ink removed
    const inter = 1.05 + tx.cover * 0.9 * k;
    const scale = tx.rough * 6 * k;                // edge displacement
    filterDef = `<filter id="tex-${uid}" x="-8%" y="-8%" width="116%" height="116%">`
      + `<feTurbulence type="fractalNoise" baseFrequency="${n(tx.freq)}" numOctaves="2" seed="${seed}" result="noise"/>`
      + (scale > 0.2 ? `<feDisplacementMap in="SourceGraphic" in2="noise" scale="${n(scale)}" xChannelSelector="R" yChannelSelector="G" result="disp"/>` : '')
      + `<feColorMatrix in="noise" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 ${n(slope)} ${n(inter)}" result="mask"/>`
      + `<feComposite in="${scale > 0.2 ? 'disp' : 'SourceGraphic'}" in2="mask" operator="in" result="cut"/>`
      + (tx.blur > 0 ? `<feGaussianBlur in="cut" stdDeviation="${n(tx.blur)}"/>` : '')
      + `</filter>`;
    filterAttr = ` filter="url(#tex-${uid})"`;
  }

  // ── Assemble ──
  const rot = cfg.rotation ? ` transform="rotate(${n(cfg.rotation)} ${C} ${C})"` : '';
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${VB}" height="${VB}" viewBox="0 0 ${VB} ${VB}" shape-rendering="geometricPrecision">`;
  if (filterDef) svg += `<defs>${filterDef}</defs>`;
  if (cfg.bg !== 'transparent') svg += `<rect width="${VB}" height="${VB}" fill="${cfg.bg}"/>`;
  svg += `<g${rot}${filterAttr}>${ink_svg}</g>`;
  svg += `</svg>`;
  return { svg };
}

function starPath(cx, cy, r, fill) {
  let d = '';
  for (let i = 0; i < 10; i++) {
    const rr = i % 2 === 0 ? r : r * 0.42;
    const [x, y] = polar(cx, cy, rr, -90 + i * 36);
    d += (i === 0 ? 'M' : 'L') + n(x) + ' ' + n(y);
  }
  return `<path d="${d}z" fill="${fill}"/>`;
}

// ── Rasterisation / export (mirrors qr-render) ──────────────────────────────────
async function rasterize(svg, format, { width = 1024, bg = 'transparent' } = {}) {
  const sharp = require('sharp');
  let img = sharp(Buffer.from(svg), { density: 384 }).resize({ width: Math.round(width) });
  switch (format) {
    case 'jpeg':
    case 'jpg':
      return { buffer: await img.flatten({ background: bg === 'transparent' ? '#ffffff' : bg }).jpeg({ quality: 92 }).toBuffer(), mime: 'image/jpeg', ext: 'jpg' };
    case 'webp':
      return { buffer: await img.webp({ quality: 92 }).toBuffer(), mime: 'image/webp', ext: 'webp' };
    case 'png':
    default:
      return { buffer: await img.png({ compressionLevel: 9 }).toBuffer(), mime: 'image/png', ext: 'png' };
  }
}

async function toPdf(svg, { name = 'Sello' } = {}) {
  const PDFDocument = require('pdfkit');
  const { buffer: png } = await rasterize(svg, 'png', { width: 1200 });
  return await new Promise((resolve, reject) => {
    try {
      const doc = new PDFDocument({ size: 'A4', margin: 56 });
      const chunks = [];
      doc.on('data', (c) => chunks.push(c));
      doc.on('end', () => resolve(Buffer.concat(chunks)));
      doc.on('error', reject);
      const pageW = doc.page.width;
      const usableW = pageW - doc.page.margins.left - doc.page.margins.right;
      const w = Math.min(320, usableW);
      const x = (pageW - w) / 2;
      doc.fontSize(20).fillColor('#111111').text(name, doc.page.margins.left, 70, { width: usableW, align: 'center' });
      doc.image(png, x, 140, { width: w });
      doc.fontSize(8).fillColor('#9aa0a6')
        .text('Generado con Batchwork · Jokin’s Tools', doc.page.margins.left, doc.page.height - 60, { width: usableW, align: 'center' });
      doc.end();
    } catch (e) { reject(e); }
  });
}

async function exportConfig(cfgInput, format, meta = {}) {
  const cfg = sanitizeConfig(cfgInput);
  cfg.__sanitized = true;
  const { svg } = buildSvg(cfg);
  if (format === 'svg') return { buffer: Buffer.from(svg), mime: 'image/svg+xml', ext: 'svg' };
  if (format === 'pdf') return { buffer: await toPdf(svg, { name: meta.name }), mime: 'application/pdf', ext: 'pdf' };
  return rasterize(svg, format, { width: meta.width || 1024, bg: cfg.bg });
}

// Small previews for the shape / texture pickers.
function shapePreviews() {
  return SHAPE_IDS.map((id) => {
    const { svg } = buildSvg({ shape: id, topText: 'FUNDACIÓN', bottomText: 'ESPAÑOLA', centerText: 'FEEP', texture: 'limpio', border: true });
    return { id, label: SHAPES[id].label, svg };
  });
}
function texturePreviews() {
  return TEXTURE_IDS.map((id) => {
    const { svg } = buildSvg({ shape: 'circle', topText: 'SELLO', bottomText: 'MUESTRA', centerText: 'FEEP', texture: id, intensity: 60 });
    return { id, label: TEXTURES[id].label, svg };
  });
}

module.exports = {
  sanitizeConfig, buildSvg, rasterize, toPdf, exportConfig,
  shapePreviews, texturePreviews,
  SHAPES, SHAPE_IDS, TEXTURES, TEXTURE_IDS, INK_PRESETS,
};
