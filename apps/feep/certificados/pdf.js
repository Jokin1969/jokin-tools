'use strict';

// ── Elegant attendance certificate (pdfkit, no browser needed) ──────────────────
// A4 landscape. Ivory ground, double navy/gold frame with corner flourishes, a
// wax-style seal on the left and a signature block on the right. Everything is
// drawn with vectors + the built-in Times family so there are no external font or
// asset files to ship — it renders identically on Railway.

const PDFDocument = require('pdfkit');

const THEMES = {
  clasico: { primary: '#1b2a4a', gold: '#b5893c' },
  burdeos: { primary: '#6e1e2a', gold: '#b0863a' },
  verde:   { primary: '#1f4636', gold: '#b5893c' },
  grafito: { primary: '#2f3336', gold: '#a9852f' },
};
const CREAM = '#fbf9f3';
const INK = '#33322e';
const MUTED = '#8a8578';

function theme(key) { return THEMES[key] || THEMES.clasico; }

// data URL → Buffer (or null if not a usable image).
function imgBuffer(dataUrl) {
  if (!dataUrl || typeof dataUrl !== 'string') return null;
  const m = dataUrl.match(/^data:image\/[a-zA-Z0-9.+-]+;base64,(.+)$/);
  if (!m) return null;
  try { return Buffer.from(m[1], 'base64'); } catch { return null; }
}

function esc(s) { return String(s == null ? '' : s).trim(); }

const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
  'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
// ISO (YYYY-MM-DD) → "11 de noviembre de 2018", optionally +N days. Null if invalid.
function longFromISO(iso, addDays) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
  if (!m) return null;
  const dt = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  if (isNaN(dt)) return null;
  if (addDays) dt.setUTCDate(dt.getUTCDate() + addDays);
  return `${dt.getUTCDate()} de ${MONTHS[dt.getUTCMonth()]} de ${dt.getUTCFullYear()}`;
}

// Two flavours of the same certificate, chosen at output time:
//   'ponencia'   → certifies the person spoke (default; needs a role of "ponente")
//   'asistencia' → certifies plain attendance, with the on-site schedule
// The type falls back from the role for records saved before the distinction existed.
function certType(d) {
  if (d.cert_type === 'asistencia' || d.cert_type === 'ponencia') return d.cert_type;
  return String(d.role || '').trim().toLowerCase() === 'ponente' ? 'ponencia' : 'asistencia';
}

// Build the certificate body sentence from the fields, per type.
function bodyText(d) {
  if (certType(d) === 'asistencia') {
    let s = 'asistió';
    if (esc(d.event)) s += ` a ${esc(d.event)}`;
    if (esc(d.date_text)) s += `, celebrada el ${esc(d.date_text)}`;
    if (esc(d.place)) s += ` en ${esc(d.place)}`;
    if (esc(d.hora_inicio) && esc(d.hora_fin)) s += `, entre las ${esc(d.hora_inicio)} y las ${esc(d.hora_fin)} horas`;
    if (esc(d.horas_presenciales)) s += ` (${esc(d.horas_presenciales)}h presenciales)`;
    return s.replace(/\s+/g, ' ').trim() + '.';
  }
  const role = esc(d.role) || 'ponente';
  let s = `actuó como ${role}`;
  if (esc(d.event)) s += ` en ${esc(d.event)}`;
  if (esc(d.talk_title)) s += `, con la ponencia titulada «${esc(d.talk_title)}»`;
  if (esc(d.date_text)) s += `, celebrada el ${esc(d.date_text)}`;
  if (esc(d.place)) s += ` en ${esc(d.place)}`;
  return s.replace(/\s+/g, ' ').trim() + '.';
}

function drawCorner(doc, x, y, dx, dy, gold) {
  // A small right-angle flourish with a diamond, oriented by (dx,dy).
  doc.save().lineWidth(1).strokeColor(gold);
  doc.moveTo(x, y + dy * 16).lineTo(x, y).lineTo(x + dx * 16, y).stroke();
  doc.moveTo(x + dx * 5, y + dy * 5)
    .lineTo(x + dx * 9, y + dy * 5).lineTo(x + dx * 9, y + dy * 9)
    .lineTo(x + dx * 5, y + dy * 9).closePath().fillColor(gold).fill();
  doc.restore();
}

function drawDivider(doc, cx, y, w, gold, primary) {
  const half = w / 2;
  doc.save().lineWidth(1).strokeColor(gold);
  doc.moveTo(cx - half, y).lineTo(cx - 10, y).stroke();
  doc.moveTo(cx + 10, y).lineTo(cx + half, y).stroke();
  // centre diamond
  doc.fillColor(primary);
  doc.moveTo(cx, y - 5).lineTo(cx + 5, y).lineTo(cx, y + 5).lineTo(cx - 5, y).closePath().fill();
  doc.fillColor(gold);
  doc.moveTo(cx, y - 2.5).lineTo(cx + 2.5, y).lineTo(cx, y + 2.5).lineTo(cx - 2.5, y).closePath().fill();
  doc.restore();
}

function drawSeal(doc, cx, cy, primary, gold, ref) {
  doc.save();
  doc.lineWidth(2).strokeColor(gold).circle(cx, cy, 46).stroke();
  doc.lineWidth(1).strokeColor(gold).circle(cx, cy, 39).stroke();
  doc.lineWidth(0.6).strokeColor(primary).circle(cx, cy, 33).stroke();
  // little ticks around the ring
  for (let i = 0; i < 24; i++) {
    const a = (i / 24) * Math.PI * 2;
    const x1 = cx + Math.cos(a) * 39; const y1 = cy + Math.sin(a) * 39;
    const x2 = cx + Math.cos(a) * 43; const y2 = cy + Math.sin(a) * 43;
    doc.moveTo(x1, y1).lineTo(x2, y2).strokeColor(gold).lineWidth(0.6).stroke();
  }
  doc.fillColor(primary).font('Times-Bold').fontSize(20)
    .text('FEEP', cx - 46, cy - 13, { width: 92, align: 'center', characterSpacing: 1 });
  doc.fillColor(gold).font('Times-Roman').fontSize(6.5)
    .text('· FUNDACIÓN ·', cx - 46, cy + 8, { width: 92, align: 'center', characterSpacing: 1 });
  doc.restore();
}

function render(data) {
  return new Promise((resolve, reject) => {
    const d = data || {};
    const t = theme(d.accent);
    const primary = t.primary;
    const gold = t.gold;
    const vertical = d.orientation === 'vertical';

    const doc = new PDFDocument({ size: 'A4', layout: vertical ? 'portrait' : 'landscape', margin: 0, info: {
      Title: `Certificado ${esc(d.ref) || ''}`.trim(),
      Author: esc(d.foundation) || 'Fundación Española de Enfermedades Priónicas',
    } });
    const chunks = [];
    doc.on('data', c => chunks.push(c));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    const W = doc.page.width;
    const H = doc.page.height;
    const cx = W / 2;
    const M = vertical ? 56 : 66;          // side margin for the content band
    const contentW = W - 2 * M;
    const foundation = esc(d.foundation) || 'Fundación Española de Enfermedades Priónicas';

    // Ground + double frame + corner flourishes
    doc.rect(0, 0, W, H).fill(CREAM);
    doc.lineWidth(2.5).strokeColor(primary).rect(22, 22, W - 44, H - 44).stroke();
    doc.lineWidth(0.8).strokeColor(gold).rect(31, 31, W - 62, H - 62).stroke();
    drawCorner(doc, 34, 34, 1, 1, gold);
    drawCorner(doc, W - 34, 34, -1, 1, gold);
    drawCorner(doc, 34, H - 34, 1, -1, gold);
    drawCorner(doc, W - 34, H - 34, -1, -1, gold);

    // Centred, self-advancing text within the content band. Returns its height.
    const draw = (str, y, font, size, color, opts = {}) => {
      const o = Object.assign({ width: contentW, align: 'center' }, opts);
      doc.font(font).fontSize(size).fillColor(color).text(str, M, y, o);
      return doc.heightOfString(str, o);
    };
    const fitSize = (str, start, min, spacing) => {
      let s = start; doc.fontSize(s);
      while (s > min && doc.widthOfString(str, spacing != null ? { characterSpacing: spacing } : undefined) > contentW) { s -= 1; doc.fontSize(s); }
      return s;
    };

    // ── Top section (flows from the top) ──────────────────────────────────────
    let y = vertical ? 62 : 50;
    const logo = imgBuffer(d.logo_data);
    if (logo) {
      const lw = Math.min(vertical ? 210 : 230, contentW * 0.62);
      const lh = vertical ? 96 : 70;
      try { doc.image(logo, cx - lw / 2, y, { fit: [lw, lh], align: 'center', valign: 'center' }); y += lh + 12; }
      catch { /* fall through to text header */ }
    }
    doc.font('Times-Bold'); fitSize(foundation.toUpperCase(), logo ? (vertical ? 11 : 12) : (vertical ? 15 : 17), 9, logo ? 2 : 2.5);
    y += draw(foundation.toUpperCase(), y, 'Times-Bold', doc._fontSize, primary, { characterSpacing: logo ? 2 : 2.5 });
    y += vertical ? 16 : 14;

    doc.font('Times-Bold');
    const title = certType(d) === 'asistencia' ? 'CERTIFICADO DE ASISTENCIA' : 'CERTIFICADO DE PONENCIA';
    const tSize = fitSize(title, vertical ? 24 : 30, 15, vertical ? 2.5 : 4);
    y += draw(title, y, 'Times-Bold', tSize, primary, { characterSpacing: vertical ? 2.5 : 4 });
    y += 12;
    drawDivider(doc, cx, y, Math.min(300, contentW * 0.8), gold, primary);
    y += 22;

    y += draw('Se certifica que', y, 'Times-Italic', 14, MUTED);
    y += 6;

    const name = esc(d.recipient_name) || '—';
    doc.font('Times-Bold');
    const nSize = fitSize(name, vertical ? 30 : 33, 17);
    y += draw(name, y, 'Times-Bold', nSize, primary) + 6;

    // flourish under the name
    doc.save().lineWidth(0.8).strokeColor(gold);
    doc.moveTo(cx - 120, y).lineTo(cx + 120, y).stroke();
    doc.fillColor(gold).moveTo(cx, y - 3).lineTo(cx + 4, y).lineTo(cx, y + 3).lineTo(cx - 4, y).closePath().fill();
    doc.restore();
    y += vertical ? 20 : 16;

    // ── Bottom section (anchored to the page bottom) ──────────────────────────
    const closingY = H - (vertical ? 210 : 150);
    const bodyW = contentW - (vertical ? 16 : 40);
    const bodyX = M + (contentW - bodyW) / 2;
    const body = bodyText(d);
    const avail = Math.max(40, closingY - y - 14);
    let bsize = vertical ? 14 : 15;
    doc.font('Times-Roman').fontSize(bsize);
    while (bsize > 10 && doc.heightOfString(body, { width: bodyW, align: 'center', lineGap: 3 }) > avail) { bsize -= 1; doc.fontSize(bsize); }
    doc.fillColor(INK).text(body, bodyX, y, { width: bodyW, align: 'center', lineGap: 3 });

    const issueDate = longFromISO(d.event_date, 1); // se expide el día siguiente al evento
    const closing = issueDate
      ? `Y para que así conste, se expide el presente certificado el ${issueDate}.`
      : 'Y para que así conste, se expide el presente certificado.';
    doc.font('Times-Italic').fontSize(11.5).fillColor(MUTED)
      .text(closing, bodyX, closingY, { width: bodyW, align: 'center' });

    // Seal (left): decorative FEEP emblem, a real uploaded seal image, or nothing.
    const sealMode = d.seal_mode || 'emblema';
    const sealCx = M + 80;
    const sealCy = H - 118;
    if (sealMode === 'imagen') {
      const sealImg = imgBuffer(d.seal_data);
      if (sealImg) {
        try { doc.image(sealImg, sealCx - 52, sealCy - 52, { fit: [104, 104], align: 'center', valign: 'center' }); }
        catch { /* ignore bad seal image */ }
      }
    } else if (sealMode !== 'ninguno') {
      drawSeal(doc, sealCx, sealCy, primary, gold, esc(d.ref));
    }

    const sigCx = W - M - 108;
    const sig = imgBuffer(d.signature_data);
    if (sig) {
      try { doc.image(sig, sigCx - 82, H - 168, { fit: [164, 54], align: 'center', valign: 'bottom' }); }
      catch { /* ignore bad image */ }
    }
    doc.save().lineWidth(0.8).strokeColor(primary).moveTo(sigCx - 100, H - 108).lineTo(sigCx + 100, H - 108).stroke().restore();
    doc.fillColor(primary).font('Times-Bold').fontSize(13)
      .text(esc(d.signer_name) || 'El Secretario', sigCx - 115, H - 102, { width: 230, align: 'center' });
    doc.fillColor(INK).font('Times-Roman').fontSize(10.5)
      .text(esc(d.signer_role) || 'Secretario de la Fundación Española de Enfermedades Priónicas', sigCx - 125, H - 86, { width: 250, align: 'center' });

    if (esc(d.ref)) {
      doc.fillColor(MUTED).font('Times-Roman').fontSize(9)
        .text(`Certificado nº ${esc(d.ref)}`, 40, H - 52, { width: W - 80, align: 'center', characterSpacing: 1 });
    }

    doc.end();
  });
}

// Rasterise the certificate PDF to a PNG buffer. Browsers (notably iOS Safari)
// refuse to display a PDF blob inside an <img>/<iframe>, so the live preview shows
// this PNG instead. Uses mupdf, a self-contained WebAssembly renderer — no system
// binary or extra fonts required, so it works identically on Railway.
let _mupdf = null;
async function getMupdf() {
  if (!_mupdf) _mupdf = await import('mupdf'); // ESM module, loaded lazily & cached
  return _mupdf;
}
async function renderPng(data, dpi) {
  const pdf = await render(data);
  const mupdf = await getMupdf();
  const doc = mupdf.Document.openDocument(pdf, 'application/pdf');
  const page = doc.loadPage(0);
  const scale = (dpi || 120) / 72;
  const pix = page.toPixmap(mupdf.Matrix.scale(scale, scale), mupdf.ColorSpace.DeviceRGB, false, true);
  const png = Buffer.from(pix.asPNG());
  pix.destroy(); page.destroy(); doc.destroy();
  return png;
}

module.exports = { render, renderPng, THEMES, longFromISO };
