'use strict';

// ── QR rendering core ─────────────────────────────────────────────────────────
// Builds styled QR codes as SVG (custom module/eye shapes, gradient, centre logo
// with a white backing, and an optional labelled frame), then rasterises to
// PNG/JPEG/WEBP via sharp and to PDF via pdfkit. Pure & deterministic: the
// routes layer handles HTTP, persistence and email.

const QRCode = require('qrcode');

// ── URL validation / normalisation ─────────────────────────────────────────────
// Flexible on input — accepts "example.com", "www.example.com", "http://…",
// "https://…" — but every stored/encoded URL ends up with an explicit scheme.
// A missing scheme defaults to https:// (modern default).
function normalizeUrl(raw) {
  let s = String(raw || '').trim();
  if (!s) return null;
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(s)) s = 'https://' + s.replace(/^\/+/, '');
  let u;
  try { u = new URL(s); } catch { return null; }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
  const host = u.hostname;
  if (!host || !/^[a-z0-9.-]+$/i.test(host)) return null;
  const isIp = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
  if (!isIp && host !== 'localhost' && !/\.[a-z]{2,}$/i.test(host)) return null;
  return u.toString();
}

// ── Style presets ──────────────────────────────────────────────────────────────
// Each preset sets the module shape, the corner radii of the three finder "eyes",
// and whether a gradient is on by default. fg/bg/gradient remain user-overridable.
const STYLES = {
  classic:      { label: 'Clásico',   module: 'square',  eyeR: 0,   eyeInnerR: 0,   gradient: false },
  rounded:      { label: 'Redondeado', module: 'rounded', eyeR: 1.8, eyeInnerR: 0.8, gradient: false },
  dots:         { label: 'Puntos',    module: 'dot',     eyeR: 3.5, eyeInnerR: 1.5, gradient: false },
  mosaic:       { label: 'Mosaico',   module: 'rounded', eyeR: 2.4, eyeInnerR: 1.2, gradient: false },
  diamond:      { label: 'Diamante',  module: 'diamond', eyeR: 0,   eyeInnerR: 0,   gradient: false },
  gradientDots: { label: 'Degradado', module: 'dot',     eyeR: 3.5, eyeInnerR: 1.5, gradient: true },
};
const STYLE_IDS = Object.keys(STYLES);

const ECC_LEVELS = ['L', 'M', 'Q', 'H'];

// ── Helpers ─────────────────────────────────────────────────────────────────────
const HEX_RE = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;
function color(value, fallback) {
  return (typeof value === 'string' && HEX_RE.test(value.trim())) ? value.trim() : fallback;
}
// Trim floats to 3 decimals, drop trailing zeros — keeps the SVG compact.
const n = (x) => {
  const r = Math.round(x * 1000) / 1000;
  return Number.isInteger(r) ? String(r) : String(r);
};
function escapeXml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Rounded-rect subpath (starts with M, ends with z). r is clamped to half-size.
function rr(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  if (r <= 0) return `M${n(x)} ${n(y)}h${n(w)}v${n(h)}h${n(-w)}z`;
  return `M${n(x + r)} ${n(y)}`
    + `h${n(w - 2 * r)}a${n(r)} ${n(r)} 0 0 1 ${n(r)} ${n(r)}`
    + `v${n(h - 2 * r)}a${n(r)} ${n(r)} 0 0 1 ${n(-r)} ${n(r)}`
    + `h${n(-(w - 2 * r))}a${n(r)} ${n(r)} 0 0 1 ${n(-r)} ${n(-r)}`
    + `v${n(-(h - 2 * r))}a${n(r)} ${n(r)} 0 0 1 ${n(r)} ${n(-r)}z`;
}
function circleSub(cx, cy, r) {
  return `M${n(cx - r)} ${n(cy)}a${n(r)} ${n(r)} 0 1 0 ${n(2 * r)} 0a${n(r)} ${n(r)} 0 1 0 ${n(-2 * r)} 0z`;
}
function diamondSub(cx, cy, h) {
  return `M${n(cx)} ${n(cy - h)}L${n(cx + h)} ${n(cy)}L${n(cx)} ${n(cy + h)}L${n(cx - h)} ${n(cy)}z`;
}

// One filled subpath for a data module of the given shape, at grid offset (ox,oy).
function modulePath(shape, ox, oy) {
  switch (shape) {
    case 'dot':     return circleSub(ox + 0.5, oy + 0.5, 0.46);
    case 'rounded': return rr(ox + 0.04, oy + 0.04, 0.92, 0.92, 0.34);
    case 'diamond': return diamondSub(ox + 0.5, oy + 0.5, 0.62);
    default:        return `M${n(ox)} ${n(oy)}h1v1h-1z`; // square (seamless)
  }
}

// ── Config sanitiser ────────────────────────────────────────────────────────────
function sanitizeConfig(input = {}) {
  const url = normalizeUrl(input.url);
  if (!url) { const e = new Error('La URL no es válida.'); e.status = 400; throw e; }

  const style = STYLE_IDS.includes(input.style) ? input.style : 'classic';
  const preset = STYLES[style];

  const hasLogo = typeof input.logo === 'string' && /^data:image\//i.test(input.logo);
  // A centre logo punches a hole in the code; force high error correction so it
  // still scans. Otherwise honour the requested level (default M).
  let ecc = ECC_LEVELS.includes(input.ecc) ? input.ecc : 'M';
  if (hasLogo && (ecc === 'L' || ecc === 'M')) ecc = 'H';

  const gradient = input.gradient != null ? !!input.gradient : preset.gradient;

  return {
    url,
    style,
    fg: color(input.fg, '#111111'),
    bg: input.bg === 'transparent' ? 'transparent' : color(input.bg, '#ffffff'),
    gradient,
    grad2: color(input.grad2, '#1B6CB0'),
    ecc,
    logo: hasLogo ? input.logo : null,
    logoScale: Math.min(34, Math.max(12, Number(input.logoScale) || 22)), // recuadro: % del ancho
    logoShape: input.logoShape === 'square' ? 'square' : 'circle',
    logoInner: Math.min(250, Math.max(50, Number(input.logoInner) || 90)), // zoom del logo: % del recuadro
    frame: !!input.frame,
    frameText: String(input.frameText || 'Escanéame').slice(0, 28),
  };
}

// ── SVG builder ─────────────────────────────────────────────────────────────────
const QUIET = 4; // quiet zone, in modules

function buildSvg(cfgInput) {
  const cfg = cfgInput.__sanitized ? cfgInput : sanitizeConfig(cfgInput);
  const preset = STYLES[cfg.style];

  const qr = QRCode.create(cfg.url, { errorCorrectionLevel: cfg.ecc });
  const size = qr.modules.size;
  const data = qr.modules.data;
  const dark = (r, c) => data[r * size + c] === 1;

  // The three finder patterns sit in 7×7 blocks at TL, TR, BL — we draw them as
  // styled "eyes" and skip their modules in the data loop.
  const eyes = [[0, 0], [0, size - 7], [size - 7, 0]];
  const inEye = (r, c) => eyes.some(([er, ec]) => r >= er && r < er + 7 && c >= ec && c < ec + 7);

  // Data modules + the inner 3×3 of each eye → one solid path.
  let solid = '';
  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      if (dark(r, c) && !inEye(r, c)) solid += modulePath(preset.module, c + QUIET, r + QUIET);
    }
  }
  let frames = ''; // eye frames (rings), drawn with evenodd holes
  for (const [er, ec] of eyes) {
    const ox = ec + QUIET, oy = er + QUIET;
    frames += rr(ox, oy, 7, 7, preset.eyeR) + rr(ox + 1, oy + 1, 5, 5, Math.max(0, preset.eyeR - 0.6));
    // inner 3×3 dot
    if (preset.module === 'dot') solid += circleSub(ox + 3.5, oy + 3.5, 1.5);
    else solid += rr(ox + 2, oy + 2, 3, 3, preset.eyeInnerR);
  }

  const total = size + 2 * QUIET;

  // Frame adds an outer border + a label strip below the code.
  const pad = cfg.frame ? 2.5 : 0;
  const labelH = cfg.frame ? 6 : 0;
  const W = total + 2 * pad;
  const H = total + 2 * pad + labelH;

  // Unique id suffix: several QR SVGs can share a page (preview, repo thumbs),
  // so gradient/clip ids must not collide.
  const uid = Math.random().toString(36).slice(2, 8);

  // Centre-logo geometry (backing half-size in modules), needed by both the clip
  // path in <defs> and the drawing below.
  let logo = null;
  if (cfg.logo) {
    const c = pad + total / 2;
    logo = { cx: c, cy: c, backR: (cfg.logoScale / 100) * size / 2 + 0.6, cr: 0 };
    logo.cr = Math.min(1.4, logo.backR * 0.16);
  }

  let defsInner = '';
  if (cfg.gradient) {
    defsInner += `<linearGradient id="qrGrad-${uid}" x1="0" y1="0" x2="1" y2="1">`
      + `<stop offset="0" stop-color="${cfg.fg}"/><stop offset="1" stop-color="${cfg.grad2}"/>`
      + `</linearGradient>`;
  }
  if (logo) {
    const shape = cfg.logoShape === 'square'
      ? `<rect x="${n(logo.cx - logo.backR)}" y="${n(logo.cy - logo.backR)}" width="${n(2 * logo.backR)}" height="${n(2 * logo.backR)}" rx="${n(logo.cr)}"/>`
      : `<circle cx="${n(logo.cx)}" cy="${n(logo.cy)}" r="${n(logo.backR)}"/>`;
    defsInner += `<clipPath id="logoClip-${uid}">${shape}</clipPath>`;
  }
  const defs = defsInner ? `<defs>${defsInner}</defs>` : '';
  const fill = cfg.gradient ? `url(#qrGrad-${uid})` : cfg.fg;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${n(W)} ${n(H)}" shape-rendering="geometricPrecision">`;
  svg += defs;

  // Background (whole canvas). Skipped entirely when transparent.
  if (cfg.bg !== 'transparent') {
    svg += `<rect width="${n(W)}" height="${n(H)}" fill="${cfg.bg}" ${cfg.frame ? `rx="${n(2.5)}"` : ''}/>`;
  }
  // Frame border around the code area.
  if (cfg.frame) {
    svg += `<rect x="0.6" y="0.6" width="${n(W - 1.2)}" height="${n(H - 1.2)}" rx="2.2" fill="none" stroke="${cfg.fg}" stroke-width="0.9"/>`;
  }

  // The QR group, offset by the frame padding.
  svg += `<g transform="translate(${n(pad)} ${n(pad)})" fill="${fill}">`;
  svg += `<path d="${solid}"/>`;
  svg += `<path fill-rule="evenodd" d="${frames}"/>`;
  svg += `</g>`;

  // Centre logo: white backing (circle or rounded square) + the image clipped to
  // that shape. logoScale sizes the backing (% of width); logoInner is a zoom on
  // the image (% of the backing): <100% leaves a margin, 100% fills it, >100%
  // enlarges and the excess is cropped to the shape (never spills out). "slice"
  // covers the box without distortion, so a small subject can be zoomed to fit.
  if (logo) {
    const { cx, cy, backR, cr } = logo;
    if (cfg.logoShape === 'square') {
      svg += `<rect x="${n(cx - backR)}" y="${n(cy - backR)}" width="${n(2 * backR)}" height="${n(2 * backR)}" rx="${n(cr)}" fill="#ffffff"/>`;
    } else {
      svg += `<circle cx="${n(cx)}" cy="${n(cy)}" r="${n(backR)}" fill="#ffffff"/>`;
    }
    const imgR = backR * (cfg.logoInner / 100);
    svg += `<image x="${n(cx - imgR)}" y="${n(cy - imgR)}" width="${n(2 * imgR)}" height="${n(2 * imgR)}" `
      + `href="${cfg.logo}" preserveAspectRatio="xMidYMid slice" clip-path="url(#logoClip-${uid})"/>`;
  }

  // Frame label text.
  if (cfg.frame) {
    const ty = total + pad + labelH * 0.62;
    svg += `<text x="${n(W / 2)}" y="${n(ty)}" text-anchor="middle" `
      + `font-family="DejaVu Sans, Verdana, sans-serif" font-weight="700" `
      + `font-size="${n(labelH * 0.5)}" fill="${cfg.fg}">${escapeXml(cfg.frameText)}</text>`;
  }

  svg += `</svg>`;
  return { svg, modules: size, total: H, ecc: cfg.ecc };
}

// ── Rasterisation ───────────────────────────────────────────────────────────────
// width = target pixel width of the output raster.
async function rasterize(svg, format, { width = 1024, bg = '#ffffff' } = {}) {
  const sharp = require('sharp');
  const buf = Buffer.from(svg);
  let img = sharp(buf, { density: 384 }).resize({ width: Math.round(width) });

  switch (format) {
    case 'jpeg':
    case 'jpg':
      // JPEG has no alpha — flatten onto a solid background.
      return { buffer: await img.flatten({ background: bg === 'transparent' ? '#ffffff' : bg }).jpeg({ quality: 92 }).toBuffer(), mime: 'image/jpeg', ext: 'jpg' };
    case 'webp':
      return { buffer: await img.webp({ quality: 92 }).toBuffer(), mime: 'image/webp', ext: 'webp' };
    case 'png':
    default:
      return { buffer: await img.png({ compressionLevel: 9 }).toBuffer(), mime: 'image/png', ext: 'png' };
  }
}

// PDF: an A4 page with the QR centred and a caption (name + URL).
async function toPdf(svg, { name = 'Código QR', url = '' } = {}) {
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
      const qrW = Math.min(360, usableW);
      const x = (pageW - qrW) / 2;
      const y = 130;

      doc.fontSize(20).fillColor('#111111').text(name, doc.page.margins.left, 70, { width: usableW, align: 'center' });
      doc.image(png, x, y, { width: qrW });
      if (url) {
        doc.fontSize(11).fillColor('#555555')
          .text(url, doc.page.margins.left, y + qrW + 24, { width: usableW, align: 'center', link: url });
      }
      doc.fontSize(8).fillColor('#9aa0a6')
        .text('Generado con Batchwork · Jokin’s Tools', doc.page.margins.left, doc.page.height - 60, { width: usableW, align: 'center' });
      doc.end();
    } catch (e) { reject(e); }
  });
}

// One-stop export to any supported format. Returns { buffer, mime, ext }.
async function exportConfig(cfgInput, format, meta = {}) {
  const cfg = sanitizeConfig(cfgInput);
  cfg.__sanitized = true;
  const { svg } = buildSvg(cfg);

  if (format === 'svg') return { buffer: Buffer.from(svg), mime: 'image/svg+xml', ext: 'svg' };
  if (format === 'pdf') return { buffer: await toPdf(svg, { name: meta.name, url: cfg.url }), mime: 'application/pdf', ext: 'pdf' };
  return rasterize(svg, format, { width: meta.width || 1024, bg: cfg.bg });
}

// Small style previews for the picker buttons (sample payload, fixed style).
function stylePreviews() {
  return STYLE_IDS.map((id) => {
    const { svg } = buildSvg({ url: 'https://jokin.tools', style: id });
    return { id, label: STYLES[id].label, gradient: STYLES[id].gradient, svg };
  });
}

module.exports = {
  normalizeUrl, sanitizeConfig, buildSvg, rasterize, toPdf, exportConfig,
  stylePreviews, STYLES, STYLE_IDS, ECC_LEVELS,
};
