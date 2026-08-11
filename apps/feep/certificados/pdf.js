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

// Build the certificate body sentence from the fields.
function bodyText(d) {
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

    const doc = new PDFDocument({ size: 'A4', layout: 'landscape', margin: 0, info: {
      Title: `Certificado ${esc(d.ref) || ''}`.trim(),
      Author: esc(d.foundation) || 'Fundación Española de Enfermedades Priónicas',
    } });
    const chunks = [];
    doc.on('data', c => chunks.push(c));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    const W = doc.page.width;   // 841.89
    const H = doc.page.height;  // 595.28
    const cx = W / 2;
    const foundation = esc(d.foundation) || 'Fundación Española de Enfermedades Priónicas';

    // Ground + double frame
    doc.rect(0, 0, W, H).fill(CREAM);
    doc.lineWidth(2.5).strokeColor(primary).rect(22, 22, W - 44, H - 44).stroke();
    doc.lineWidth(0.8).strokeColor(gold).rect(31, 31, W - 62, H - 62).stroke();
    drawCorner(doc, 34, 34, 1, 1, gold);
    drawCorner(doc, W - 34, 34, -1, 1, gold);
    drawCorner(doc, 34, H - 34, 1, -1, gold);
    drawCorner(doc, W - 34, H - 34, -1, -1, gold);

    // Header — logo (if any) then foundation name in small caps
    const logo = imgBuffer(d.logo_data);
    let headerBottom = 60;
    if (logo) {
      try { doc.image(logo, cx - 115, 50, { fit: [230, 66], align: 'center', valign: 'center' }); headerBottom = 120; }
      catch { /* fall through to text header */ }
    }
    doc.fillColor(primary).font('Times-Bold').fontSize(logo ? 12 : 17)
      .text(foundation.toUpperCase(), 70, logo ? 122 : 66, { width: W - 140, align: 'center', characterSpacing: logo ? 2 : 2.5 });
    headerBottom = logo ? 140 : 92;

    // Title
    doc.fillColor(primary).font('Times-Bold').fontSize(30)
      .text('CERTIFICADO DE ASISTENCIA', 70, headerBottom + 18, { width: W - 140, align: 'center', characterSpacing: 4 });
    drawDivider(doc, cx, headerBottom + 62, 300, gold, primary);

    // "Se certifica que"
    let y = headerBottom + 82;
    doc.fillColor(MUTED).font('Times-Italic').fontSize(14)
      .text('Se certifica que', 70, y, { width: W - 140, align: 'center' });

    // Recipient name (the star)
    y += 26;
    const name = esc(d.recipient_name) || '—';
    doc.fillColor(primary).font('Times-Bold').fontSize(33)
      .text(name, 70, y, { width: W - 140, align: 'center' });
    const nameH = doc.heightOfString(name, { width: W - 140, align: 'center' });
    y += nameH + 6;
    // underline flourish under the name
    doc.save().lineWidth(0.8).strokeColor(gold);
    doc.moveTo(cx - 120, y).lineTo(cx + 120, y).stroke();
    doc.fillColor(gold).moveTo(cx, y - 3).lineTo(cx + 4, y).lineTo(cx, y + 3).lineTo(cx - 4, y).closePath().fill();
    doc.restore();

    // Body sentence — adapt font size so it fits above the signature area
    y += 16;
    const body = bodyText(d);
    const bodyW = W - 220;
    let bsize = 15;
    doc.font('Times-Roman').fontSize(bsize);
    while (bsize > 11 && doc.heightOfString(body, { width: bodyW, align: 'center', lineGap: 3 }) > 96) {
      bsize -= 1; doc.fontSize(bsize);
    }
    doc.fillColor(INK).text(body, 110, y, { width: bodyW, align: 'center', lineGap: 3 });

    // Closing line
    doc.fillColor(MUTED).font('Times-Italic').fontSize(11.5)
      .text('Y para que así conste, se expide el presente certificado.', 110, H - 150, { width: bodyW, align: 'center' });

    // Seal (left) + signature block (right)
    drawSeal(doc, 200, H - 118, primary, gold, esc(d.ref));

    const sigCx = W - 235;
    const sig = imgBuffer(d.signature_data);
    if (sig) {
      try { doc.image(sig, sigCx - 80, H - 165, { fit: [160, 52], align: 'center', valign: 'bottom' }); }
      catch { /* ignore bad image */ }
    }
    doc.save().lineWidth(0.8).strokeColor(primary).moveTo(sigCx - 100, H - 108).lineTo(sigCx + 100, H - 108).stroke().restore();
    doc.fillColor(primary).font('Times-Bold').fontSize(13)
      .text(esc(d.signer_name) || 'El Secretario', sigCx - 110, H - 102, { width: 220, align: 'center' });
    doc.fillColor(INK).font('Times-Roman').fontSize(10.5)
      .text(esc(d.signer_role) || 'Secretario de la Fundación Española de Enfermedades Priónicas', sigCx - 120, H - 86, { width: 240, align: 'center' });

    // Reference (bottom-centre)
    if (esc(d.ref)) {
      doc.fillColor(MUTED).font('Times-Roman').fontSize(9)
        .text(`Certificado nº ${esc(d.ref)}`, 40, H - 52, { width: W - 80, align: 'center', characterSpacing: 1 });
    }

    doc.end();
  });
}

module.exports = { render, THEMES };
