const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile } = require('child_process');
const PDFDocument = require('pdfkit');
const sharp = require('sharp');

// Turns a supported attachment into a print-ready PDF, so the local agent only
// ever deals with PDFs. Supported: PDF (passthrough), PNG/JPEG (embedded in an
// A4 page) and DOCX (via LibreOffice headless — the same engine Batchwork uses).

// Map a filename/mime to a printable kind, or null if unsupported.
function kindOf(filename, mime) {
  const type = String(mime || '').toLowerCase();
  const name = String(filename || '').toLowerCase();
  if (type === 'application/pdf' || name.endsWith('.pdf')) return 'pdf';
  if (type === 'image/png' || name.endsWith('.png')) return 'png';
  if (type === 'image/jpeg' || name.endsWith('.jpg') || name.endsWith('.jpeg')) return 'jpg';
  if (name.endsWith('.docx') || type.includes('wordprocessingml')) return 'docx';
  return null;
}

// Render an image (any orientation/format) onto a single A4 PDF page, centered
// and scaled to fit. sharp normalises EXIF rotation and re-encodes to PNG so
// pdfkit always accepts it (progressive/CMYK JPEGs included).
async function imageToPdf(buffer) {
  const png = await sharp(buffer).rotate().png().toBuffer();
  return new Promise((resolve, reject) => {
    try {
      const doc = new PDFDocument({ size: 'A4', margin: 24 });
      const chunks = [];
      doc.on('data', (c) => chunks.push(c));
      doc.on('end', () => resolve(Buffer.concat(chunks)));
      doc.on('error', reject);
      const w = doc.page.width - 48;
      const h = doc.page.height - 48;
      doc.image(png, 24, 24, { fit: [w, h], align: 'center', valign: 'center' });
      doc.end();
    } catch (e) { reject(e); }
  });
}

function rmrf(dir) {
  try { fs.rmSync(dir, { recursive: true, force: true }); } catch { /* ignore */ }
}

// DOCX → PDF via LibreOffice headless. A per-call UserInstallation profile keeps
// concurrent conversions (e.g. Batchwork running at the same time) from clashing
// on the shared profile lock.
function libreConvertDocx(buffer /*, filename */) {
  return new Promise((resolve, reject) => {
    const work = fs.mkdtempSync(path.join(os.tmpdir(), 'impr-docx-'));
    const inFile = path.join(work, 'in.docx');
    const outFile = path.join(work, 'in.pdf');
    const profile = path.join(work, 'profile');
    fs.writeFileSync(inFile, buffer);
    const bin = process.env.LIBREOFFICE_BIN || 'libreoffice';
    execFile(
      bin,
      ['--headless', `-env:UserInstallation=file://${profile}`, '--convert-to', 'pdf', '--outdir', work, inFile],
      { timeout: 120000 },
      (err, stdout, stderr) => {
        if (fs.existsSync(outFile)) {
          const buf = fs.readFileSync(outFile);
          rmrf(work);
          return resolve(buf);
        }
        rmrf(work);
        const detail = String((stderr || (err && err.message) || 'sin salida')).slice(0, 200);
        reject(new Error('LibreOffice no pudo convertir el DOCX: ' + detail));
      },
    );
  });
}

// Normalise one attachment to a PDF buffer. `deps.convertDocx` is injectable so
// the DOCX branch can be unit-tested without LibreOffice.
async function toPdf(doc, deps = {}) {
  const convertDocx = deps.convertDocx || libreConvertDocx;
  const kind = doc.kind || kindOf(doc.filename, doc.mime);
  if (!doc.content || !doc.content.length) throw new Error('Adjunto vacío');
  switch (kind) {
    case 'pdf':
      return { buffer: doc.content, kind };
    case 'png':
    case 'jpg':
      return { buffer: await imageToPdf(doc.content), kind };
    case 'docx':
      return { buffer: await convertDocx(doc.content, doc.filename), kind };
    default:
      throw new Error(`Tipo no soportado para impresión: ${doc.filename}`);
  }
}

module.exports = { kindOf, toPdf, imageToPdf, libreConvertDocx };
