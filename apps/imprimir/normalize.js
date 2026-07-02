const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile } = require('child_process');
const PDFDocument = require('pdfkit');
const sharp = require('sharp');

// Turns a supported attachment into a print-ready PDF, so the local agent only
// ever deals with PDFs. Supported: PDF (passthrough), PNG/JPEG (embedded in an
// A4 page) and office documents — DOCX/XLSX/PPTX (and their legacy/ODF cousins)
// via LibreOffice headless, the same engine Batchwork uses.

// Office formats LibreOffice can convert to PDF.
const OFFICE = new Set(['docx', 'xlsx', 'pptx', 'odt', 'ods', 'odp', 'doc', 'xls', 'ppt', 'rtf']);

// Map a filename/mime to a printable kind, or null if unsupported.
function kindOf(filename, mime) {
  const type = String(mime || '').toLowerCase();
  const name = String(filename || '').toLowerCase();
  if (type === 'application/pdf' || name.endsWith('.pdf')) return 'pdf';
  if (type === 'image/png' || name.endsWith('.png')) return 'png';
  if (type === 'image/jpeg' || name.endsWith('.jpg') || name.endsWith('.jpeg')) return 'jpg';
  const ext = (name.match(/\.([a-z0-9]+)$/) || [])[1];
  if (ext && OFFICE.has(ext)) return ext;
  // Fall back to MIME for office types sent as octet-stream with no extension.
  if (type.includes('wordprocessingml')) return 'docx';
  if (type.includes('spreadsheetml')) return 'xlsx';
  if (type.includes('presentationml')) return 'pptx';
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

// Office document → PDF via LibreOffice headless. Writes the source with its real
// extension so LibreOffice picks the right filter. A per-call UserInstallation
// profile keeps concurrent conversions (e.g. Batchwork at the same time) from
// clashing on the shared profile lock.
function libreConvert(buffer, ext) {
  return new Promise((resolve, reject) => {
    const work = fs.mkdtempSync(path.join(os.tmpdir(), 'impr-office-'));
    const safeExt = /^[a-z0-9]{1,5}$/i.test(ext) ? ext.toLowerCase() : 'bin';
    const inFile = path.join(work, 'in.' + safeExt);
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
        reject(new Error('LibreOffice no pudo convertir el documento: ' + detail));
      },
    );
  });
}

// Normalise one attachment to a PDF buffer. `deps.convertOffice` is injectable so
// the office branch can be unit-tested without LibreOffice.
async function toPdf(doc, deps = {}) {
  const convertOffice = deps.convertOffice || libreConvert;
  const kind = doc.kind || kindOf(doc.filename, doc.mime);
  if (!doc.content || !doc.content.length) throw new Error('Adjunto vacío');
  if (kind === 'pdf') return { buffer: doc.content, kind };
  if (kind === 'png' || kind === 'jpg') return { buffer: await imageToPdf(doc.content), kind };
  if (OFFICE.has(kind)) return { buffer: await convertOffice(doc.content, kind), kind };
  throw new Error(`Tipo no soportado para impresión: ${doc.filename}`);
}

module.exports = { kindOf, toPdf, imageToPdf, libreConvert, OFFICE };
