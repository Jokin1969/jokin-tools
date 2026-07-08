const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile } = require('child_process');
const sharp = require('sharp');
const { PDFDocument, StandardFonts, rgb, degrees } = require('pdf-lib');
const { createZip } = require('../utils');

// Stamps a watermark (text OR an uploaded logo image) onto PDFs (every page) and
// images, in the original format/quality, with the name ending in "_watermarked_".
// Options: layout (position/repetition), size, colour (text), and intensity.

const COLORS = {
  gris:  { pdf: [0.50, 0.50, 0.50], svg: '#808080' },
  rojo:  { pdf: [0.80, 0.10, 0.10], svg: '#cc1a1a' },
  azul:  { pdf: [0.12, 0.20, 0.70], svg: '#1f33b3' },
  negro: { pdf: [0.00, 0.00, 0.00], svg: '#000000' },
};
const SIZE_SCALE = { 'pequeña': 0.65, pequena: 0.65, mediana: 1.0, grande: 1.5 };
const LAYOUTS = new Set(['diagonal', 'diagonal-rep', 'mosaico', 'centro', 'pie', 'esquina']);
const IMG_EXT = new Set(['.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.gif']);
const xmlEsc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]));

function outputName(name) {
  const ext = path.extname(name);
  const base = ext ? name.slice(0, -ext.length) : name;
  return `${base}_watermarked_${ext}`; // contrato.pdf → contrato_watermarked_.pdf
}

// Placements in screen coordinates (origin top-left, y down). Each item is placed
// by its CENTER (cx, cy) with a clockwise rotation `rot` (degrees). `iw`/`ih` are
// the mark's natural width/height (used for tiling spacing).
function placements(layout, W, H, iw, ih, rotOverride = null) {
  const cx = W / 2, cy = H / 2;
  // A non-zero override forces that exact angle on every placement.
  const ov = (rotOverride == null || rotOverride === 0) ? null : rotOverride;
  if (layout === 'centro') return [{ cx, cy, rot: ov ?? 0 }];
  if (layout === 'pie') return [{ cx, cy: H - ih * 0.75, rot: ov ?? 0 }];
  if (layout === 'esquina') return [{ cx: W - iw / 2 - Math.min(W, H) * 0.03, cy: H - ih / 2 - Math.min(W, H) * 0.03, rot: ov ?? 0 }];
  if (layout === 'diagonal') return [{ cx, cy, rot: ov ?? -(Math.atan2(H, W) * 180 / Math.PI) }];
  // repeated: mosaico (no rotation) or diagonal-rep (rotated); override wins
  const rot = ov ?? (layout === 'diagonal-rep' ? -30 : 0);
  const gapX = iw + Math.max(iw * 0.5, 20);
  const gapY = ih + Math.max(ih * 1.3, 24);
  const pts = [];
  let row = 0;
  for (let y = -gapY; y < H + gapY; y += gapY, row++) {
    const off = row % 2 ? gapX / 2 : 0;
    for (let x = -gapX; x < W + gapX; x += gapX) pts.push({ cx: x + off, cy: y, rot });
  }
  return pts;
}

// ── Images (SVG overlay composited by sharp) ───────────────────────────────────
async function buildOverlaySvg(W, H, opts) {
  const { kind, text, colorSvg, layout, sizeScale, opacity, logoBuf, rotation } = opts;
  const min = Math.min(W, H);
  let iw, ih, el; // natural width/height + a function (px,py,rot)→svg element

  if (kind === 'logo') {
    const meta = await sharp(logoBuf).metadata();
    const aspect = (meta.width || 1) / (meta.height || 1);
    const baseFrac = { diagonal: 0.55, centro: 0.5, 'diagonal-rep': 0.2, mosaico: 0.2, pie: 0.28, esquina: 0.22 }[layout] || 0.4;
    iw = Math.max(24, min * baseFrac * sizeScale);
    ih = iw / aspect;
    const href = `data:${meta.format === 'jpeg' ? 'image/jpeg' : 'image/png'};base64,${logoBuf.toString('base64')}`;
    el = (px, py, rot) => `<image href="${href}" x="${px - iw / 2}" y="${py - ih / 2}" width="${iw}" height="${ih}" opacity="${opacity}" transform="rotate(${rot} ${px} ${py})"/>`;
  } else {
    const baseFrac = { diagonal: null, centro: 0.11, 'diagonal-rep': 0.038, mosaico: 0.038, pie: 0.028, esquina: 0.032 }[layout];
    let fontSize;
    if (layout === 'diagonal') {
      const diag = Math.hypot(W, H);
      fontSize = Math.round(diag * 0.8 / (Math.max(text.length, 4) * 0.6));
      fontSize = Math.max(Math.round(min * 0.05), Math.min(fontSize, Math.round(min * 0.32)));
    } else {
      fontSize = Math.max(10, Math.round(min * baseFrac));
    }
    fontSize = Math.max(9, Math.round(fontSize * sizeScale));
    iw = Math.max(text.length * fontSize * 0.6, fontSize);
    ih = fontSize;
    const t = xmlEsc(text);
    el = (px, py, rot) => `<text x="${px}" y="${py + fontSize * 0.34}" text-anchor="middle" font-size="${fontSize}" font-family="DejaVu Sans, Arial, sans-serif" font-weight="bold" fill="${colorSvg}" fill-opacity="${opacity}" transform="rotate(${rot} ${px} ${py})">${t}</text>`;
  }

  const body = placements(layout, W, H, iw, ih, rotation).map(p => el(p.cx, p.cy, p.rot)).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}">${body}</svg>`;
}

async function watermarkImage(inPath, opts) {
  const meta = await sharp(inPath, { failOn: 'none' }).metadata();
  const W = meta.width, H = meta.height;
  if (!W || !H) throw new Error('No se pudieron leer las dimensiones de la imagen.');
  const svg = await buildOverlaySvg(W, H, opts);
  let pipe = sharp(inPath, { failOn: 'none' }).composite([{ input: Buffer.from(svg), top: 0, left: 0 }]);
  switch (meta.format) {
    case 'jpeg': pipe = pipe.jpeg({ quality: 95, chromaSubsampling: '4:4:4' }); break;
    case 'png':  pipe = pipe.png(); break;
    case 'webp': pipe = pipe.webp({ quality: 95 }); break;
    case 'tiff': pipe = pipe.tiff(); break;
    case 'gif':  pipe = pipe.gif(); break;
    default: break;
  }
  return pipe.toBuffer();
}

// ── PDF (pdf-lib) ──────────────────────────────────────────────────────────────
// pdf-lib uses a bottom-left origin (y up) and counter-clockwise rotation, so we
// convert from the screen-space placements above.
function drawItemPdf(page, W, H, place, iw, ih, drawAt) {
  for (const p of place) {
    drawAt(p.cx, H - p.cy, -p.rot); // flip y, invert rotation direction
  }
}

function rmrf(dir) { try { fs.rmSync(dir, { recursive: true, force: true }); } catch { /* ignore */ } }

// Best-effort decrypt with qpdf (removes owner-only encryption, no password
// needed). Returns decrypted bytes, or null if qpdf is missing/fails (e.g. the
// PDF has a real user password).
function qpdfDecrypt(bytes) {
  return new Promise((resolve) => {
    let work;
    try { work = fs.mkdtempSync(path.join(os.tmpdir(), 'wm-dec-')); } catch { return resolve(null); }
    const inF = path.join(work, 'in.pdf'), outF = path.join(work, 'out.pdf');
    try { fs.writeFileSync(inF, bytes); } catch { rmrf(work); return resolve(null); }
    execFile(process.env.QPDF_BIN || 'qpdf', ['--decrypt', '--password=', inF, outF], { timeout: 60000 }, () => {
      let buf = null;
      try { if (fs.existsSync(outF)) buf = fs.readFileSync(outF); } catch { /* ignore */ }
      rmrf(work);
      resolve(buf && buf.length ? buf : null);
    });
  });
}

// Load a PDF, transparently decrypting encrypted ones. Encrypted PDFs can't be
// edited by pdf-lib (it would emit a corrupt file), so we decrypt first or fail
// with a clear, actionable error.
async function loadPdf(bytes) {
  try {
    return await PDFDocument.load(bytes); // strict: throws if encrypted
  } catch (e) {
    if (!/encrypt/i.test(e.message || '')) throw e; // genuinely broken source
  }
  const dec = await qpdfDecrypt(bytes);
  if (dec) return PDFDocument.load(dec, { ignoreEncryption: true });
  throw new Error('PDF protegido/cifrado: no se puede marcar. Quítale la contraseña o la protección y vuelve a intentarlo.');
}

async function watermarkPdf(bytes, opts) {
  const { kind, text, colorPdf, layout, sizeScale, opacity, logoBuf, rotation } = opts;
  const pdf = await loadPdf(bytes);

  let embedded = null;
  if (kind === 'logo') {
    const sig = logoBuf.slice(0, 4);
    embedded = (sig[0] === 0x89 && sig[1] === 0x50) ? await pdf.embedPng(logoBuf) : await pdf.embedJpg(logoBuf);
  }
  const font = kind === 'text' ? await pdf.embedFont(StandardFonts.HelveticaBold) : null;
  const safe = kind === 'text' ? ((text.replace(/[^\x20-\xFF]/g, '').trim()) || 'CONFIDENCIAL') : '';
  const col = kind === 'text' ? rgb(colorPdf[0], colorPdf[1], colorPdf[2]) : null;

  for (const page of pdf.getPages()) {
    const { width: W, height: H } = page.getSize();
    const min = Math.min(W, H);
    let iw, ih, drawAt;

    if (kind === 'logo') {
      const aspect = embedded.width / embedded.height;
      const baseFrac = { diagonal: 0.55, centro: 0.5, 'diagonal-rep': 0.2, mosaico: 0.2, pie: 0.28, esquina: 0.22 }[layout] || 0.4;
      iw = Math.max(24, min * baseFrac * sizeScale);
      ih = iw / aspect;
      drawAt = (cx, cyPdf, rotCcw) => {
        // place by center: shift origin to bottom-left of the (unrotated) image
        const x = cx - iw / 2, y = cyPdf - ih / 2;
        page.drawImage(embedded, { x, y, width: iw, height: ih, opacity, rotate: degrees(rotCcw) });
      };
    } else {
      let fontSize;
      if (layout === 'diagonal') {
        const diag = Math.hypot(W, H);
        fontSize = Math.min(min * 0.32, Math.max(min * 0.05, diag * 0.8 / (Math.max(safe.length, 4) * 0.6)));
      } else {
        const baseFrac = { 'diagonal-rep': 0.038, mosaico: 0.038, centro: 0.11, pie: 0.028, esquina: 0.032 }[layout] || 0.05;
        fontSize = Math.max(8, min * baseFrac);
      }
      fontSize = Math.max(7, fontSize * sizeScale);
      const tw = font.widthOfTextAtSize(safe, fontSize);
      iw = tw; ih = fontSize;
      drawAt = (cx, cyPdf, rotCcw) => {
        const x = cx - tw / 2, y = cyPdf - fontSize * 0.34;
        page.drawText(safe, { x, y, size: fontSize, font, color: col, opacity, rotate: degrees(rotCcw) });
      };
    }

    drawItemPdf(page, W, H, placements(layout, W, H, iw, ih, rotation), iw, ih, drawAt);
  }
  return Buffer.from(await pdf.save());
}

// ── Operation entry point ──────────────────────────────────────────────────────
async function run(session, params) {
  const text = (String(params.text ?? 'CONFIDENCIAL').trim()) || 'CONFIDENCIAL';
  const layout = LAYOUTS.has(params.layout) ? params.layout : 'diagonal';
  const sizeScale = SIZE_SCALE[params.size] || 1.0;
  const colorKey = COLORS[params.color] ? params.color : 'gris';
  const color = COLORS[colorKey];
  const opacity = Math.min(0.95, Math.max(0.03, (parseInt(params.intensity ?? 25, 10) || 25) / 100));
  const rotDeg = parseInt(params.rotation ?? 0, 10) || 0;
  const rotation = rotDeg !== 0 ? Math.max(-90, Math.min(90, rotDeg)) : null; // null = automática por layout

  // Optional logo image (uploaded through the nameList channel → _namelist_.txt).
  let logoBuf = null;
  const logoPath = path.join(session.inputDir, '_namelist_.txt');
  if (fs.existsSync(logoPath)) {
    try {
      const buf = fs.readFileSync(logoPath);
      await sharp(buf).metadata(); // validate it's a real image
      logoBuf = buf;
    } catch { throw new Error('La imagen de marca (logo) no es una imagen válida.'); }
  }
  const kind = logoBuf ? 'logo' : 'text';
  const common = { kind, text, colorSvg: color.svg, colorPdf: color.pdf, layout, sizeScale, opacity, logoBuf, rotation };

  const files = fs.readdirSync(session.inputDir)
    .filter(f => f !== '_namelist_.txt' && fs.statSync(path.join(session.inputDir, f)).isFile())
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));
  if (!files.length) throw new Error('No se han subido ficheros a los que poner la marca.');

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
        fs.writeFileSync(outPath, await watermarkPdf(fs.readFileSync(inPath), common));
      } else if (IMG_EXT.has(ext)) {
        fs.writeFileSync(outPath, await watermarkImage(inPath, common));
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
  session.log.push({ type: 'info', file: '', message: `${done} fichero(s) con marca de agua (${kind === 'logo' ? 'logo' : 'texto'}).` });

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);
  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'con_marca_de_agua.zip';
  session.status = 'done';
}

module.exports = { run, outputName, placements, buildOverlaySvg, watermarkPdf, watermarkImage };
