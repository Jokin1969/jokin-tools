const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const { PDFDocument, StandardFonts, rgb, degrees } = require('pdf-lib');
const { createZip } = require('../utils');

// Adds a text watermark to PDFs (every page) and images, returning each file in
// its original format/quality with the name ending in "_watermarked_".

const COLORS = {
  gris:  { pdf: [0.50, 0.50, 0.50], svg: '#808080' },
  rojo:  { pdf: [0.80, 0.10, 0.10], svg: '#cc1a1a' },
  azul:  { pdf: [0.12, 0.20, 0.70], svg: '#1f33b3' },
  negro: { pdf: [0.00, 0.00, 0.00], svg: '#000000' },
};

const IMG_EXT = new Set(['.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.gif']);
const xmlEsc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]));

function outputName(name) {
  const ext = path.extname(name);
  const base = ext ? name.slice(0, -ext.length) : name;
  return `${base}_watermarked_${ext}`; // p. ej. contrato.pdf → contrato_watermarked_.pdf
}

// ── PDF ───────────────────────────────────────────────────────────────────────
function drawPdfWatermark(page, font, text, style, col, opacity, W, H) {
  if (style === 'footer') {
    const size = Math.max(8, Math.min(W, H) * 0.02);
    const tw = font.widthOfTextAtSize(text, size);
    page.drawText(text, { x: (W - tw) / 2, y: size * 0.9, size, font, color: col, opacity });
    return;
  }
  if (style === 'tiled') {
    const size = Math.max(10, Math.min(W, H) * 0.03);
    const tw = font.widthOfTextAtSize(text, size);
    const stepX = tw + size * 3;
    const stepY = size * 5;
    for (let y = -stepY; y < H + stepY; y += stepY) {
      for (let x = -tw; x < W + stepX; x += stepX) {
        page.drawText(text, { x, y, size, font, color: col, opacity, rotate: degrees(30) });
      }
    }
    return;
  }
  // diagonal: one big line across the page, centered
  const a = Math.atan2(H, W);
  const diag = Math.hypot(W, H);
  let size = Math.min(W, H) * 0.2;
  let tw = font.widthOfTextAtSize(text, size);
  const target = diag * 0.8;
  if (tw > target) { size *= target / tw; tw = font.widthOfTextAtSize(text, size); }
  const x = W / 2 - Math.cos(a) * tw / 2 + Math.sin(a) * size * 0.35;
  const y = H / 2 - Math.sin(a) * tw / 2 - Math.cos(a) * size * 0.35;
  page.drawText(text, { x, y, size, font, color: col, opacity, rotate: degrees(a * 180 / Math.PI) });
}

async function watermarkPdf(bytes, { text, style, colorPdf, opacity }) {
  const pdf = await PDFDocument.load(bytes, { ignoreEncryption: true, updateMetadata: false });
  const font = await pdf.embedFont(StandardFonts.HelveticaBold);
  // Standard fonts only encode WinAnsi; drop anything outside it so custom text
  // with odd glyphs/emoji can't crash the whole file.
  const safe = (text.replace(/[^\x20-\xFF]/g, '').trim()) || 'CONFIDENCIAL';
  const col = rgb(colorPdf[0], colorPdf[1], colorPdf[2]);
  for (const page of pdf.getPages()) {
    const { width, height } = page.getSize();
    drawPdfWatermark(page, font, safe, style, col, opacity, width, height);
  }
  return Buffer.from(await pdf.save());
}

// ── Images ────────────────────────────────────────────────────────────────────
function buildWatermarkSvg(W, H, { text, style, color, opacity }) {
  const t = xmlEsc(text);
  const common = `font-family="DejaVu Sans, Arial, sans-serif" font-weight="bold" fill="${color}" fill-opacity="${opacity}"`;
  if (style === 'footer') {
    const size = Math.max(10, Math.round(Math.min(W, H) * 0.025));
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}"><text x="${W / 2}" y="${H - size * 0.8}" text-anchor="middle" font-size="${size}" ${common}>${t}</text></svg>`;
  }
  if (style === 'tiled') {
    const size = Math.max(12, Math.round(Math.min(W, H) * 0.035));
    const pw = Math.round(Math.max(text.length * size * 0.6, size) + size * 2);
    const ph = Math.round(size * 3.2);
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}">` +
      `<defs><pattern id="wm" width="${pw}" height="${ph}" patternUnits="userSpaceOnUse" patternTransform="rotate(-30)">` +
      `<text x="0" y="${size}" font-size="${size}" ${common}>${t}</text></pattern></defs>` +
      `<rect width="${W}" height="${H}" fill="url(#wm)"/></svg>`;
  }
  // diagonal
  const diag = Math.hypot(W, H);
  let size = Math.round(diag * 0.8 / (Math.max(text.length, 4) * 0.6));
  size = Math.max(Math.round(Math.min(W, H) * 0.05), Math.min(size, Math.round(Math.min(W, H) * 0.3)));
  const cx = W / 2, cy = H / 2;
  const angle = -(Math.atan2(H, W) * 180 / Math.PI);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}"><text x="${cx}" y="${cy + size * 0.35}" text-anchor="middle" font-size="${size}" transform="rotate(${angle} ${cx} ${cy})" ${common}>${t}</text></svg>`;
}

async function watermarkImage(inPath, { text, style, colorSvg, opacity }) {
  const meta = await sharp(inPath, { failOn: 'none' }).metadata();
  const W = meta.width, H = meta.height;
  if (!W || !H) throw new Error('No se pudieron leer las dimensiones de la imagen.');
  const svg = buildWatermarkSvg(W, H, { text, style, color: colorSvg, opacity });
  let pipe = sharp(inPath, { failOn: 'none' }).composite([{ input: Buffer.from(svg), top: 0, left: 0 }]);
  switch (meta.format) {
    case 'jpeg': pipe = pipe.jpeg({ quality: 95, chromaSubsampling: '4:4:4' }); break;
    case 'png':  pipe = pipe.png(); break;
    case 'webp': pipe = pipe.webp({ quality: 95 }); break;
    case 'tiff': pipe = pipe.tiff(); break;
    case 'gif':  pipe = pipe.gif(); break;
    default: break; // keep input format
  }
  return pipe.toBuffer();
}

// ── Operation entry point ──────────────────────────────────────────────────────
async function run(session, params) {
  const text = (String(params.text ?? 'CONFIDENCIAL').trim()) || 'CONFIDENCIAL';
  const style = ['diagonal', 'tiled', 'footer'].includes(params.style) ? params.style : 'diagonal';
  const colorKey = COLORS[params.color] ? params.color : 'gris';
  const color = COLORS[colorKey];
  const opacity = Math.min(0.9, Math.max(0.03, (parseInt(params.intensity ?? 25, 10) || 25) / 100));

  const files = fs.readdirSync(session.inputDir)
    .filter(f => fs.statSync(path.join(session.inputDir, f)).isFile())
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));
  if (!files.length) throw new Error('No se han subido ficheros.');

  session.progress = { current: 0, total: files.length, message: 'Aplicando marca de agua...' };
  let done = 0;

  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    session.progress = { current: i + 1, total: files.length, message: f };
    const ext = path.extname(f).toLowerCase();
    const inPath = path.join(session.inputDir, f);
    const outPath = path.join(session.outputDir, outputName(f));
    try {
      if (ext === '.pdf') {
        const out = await watermarkPdf(fs.readFileSync(inPath), { text, style, colorPdf: color.pdf, opacity });
        fs.writeFileSync(outPath, out);
      } else if (IMG_EXT.has(ext)) {
        const out = await watermarkImage(inPath, { text, style, colorSvg: color.svg, opacity });
        fs.writeFileSync(outPath, out);
      } else {
        session.log.push({ type: 'warn', file: f, message: 'Formato no soportado (se omite): usa PDF o imagen.' });
        continue;
      }
      done++;
      session.log.push({ type: 'info', file: f, message: `→ ${outputName(f)}` });
    } catch (e) {
      session.log.push({ type: 'error', file: f, message: e.message });
    }
  }

  if (!done) throw new Error('No se pudo procesar ningún fichero (formatos no soportados o errores).');
  session.log.push({ type: 'info', file: '', message: `${done} fichero(s) con marca de agua.` });

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);
  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'con_marca_de_agua.zip';
  session.status = 'done';
}

module.exports = { run, outputName, buildWatermarkSvg, watermarkPdf, watermarkImage };
