// Shared "Manual / Ayuda → PDF" renderer for the pharmacy apps (QR·TIS, Data
// Matrix, Asignación). The help content lives in each app's frontend as a list of
// sections { icon, title, html }; the client posts those sections here and this
// module turns them into one elegant, branded PDF with pdfkit.
//
// The HTML uses a small, known vocabulary: <p>, <ul>/<ol> with <li>, inline
// <b>/<strong>, <code>, <em>/<i>, <span class="qt-chip-inline"> and note boxes
// <div class="qt-note tip|warn">. We parse exactly that. Emoji/symbols that the
// core PDF fonts cannot draw are stripped so nothing renders as a "tofu" box; the
// meaning survives because button names are also spelled out in words.

const PDFDocument = require('pdfkit');

// ── Palette (matches the app's help hero: #12406e → #1273b8) ────────────────────
const BRAND = '#1273b8';
const BRAND_DK = '#12406e';
const INK = '#0f172a';
const MUTED = '#64748b';
const LINE = '#e2e8f0';

// ── Text cleaning ───────────────────────────────────────────────────────────────
// Strip pictographic/symbol code points the standard PDF fonts (Helvetica/Courier)
// can't render. Keeps normal Latin-1 punctuation, bullets (•) and guillemets (« »).
// Ranges of code points the standard PDF fonts can't draw (arrows, dingbats,
// geometric shapes, enclosed alphanumerics, misc symbols, variation selectors,
// ZWJ and the whole emoji plane). Built from escapes so no literal glyph appears.
const SYMBOLS = new RegExp(
  '[' +
  '\\u2190-\\u21FF' +   // arrows
  '\\u2300-\\u23FF' +   // misc technical
  '\\u2460-\\u24FF' +   // enclosed alphanumerics
  '\\u2500-\\u27BF' +   // box drawing, geometric shapes, misc symbols, dingbats
  '\\u2B00-\\u2BFF' +   // misc symbols and arrows
  '\\uFE00-\\uFE0F' +   // variation selectors
  '\\u200D' +           // zero-width joiner
  '\\u{1F000}-\\u{1FAFF}' + // emoji / pictographs
  ']', 'gu');
function decodeEntities(t) {
  return t
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&hellip;/g, '…')
    .replace(/&amp;/g, '&');
}
function clean(t) {
  return decodeEntities(String(t || ''))
    .replace(SYMBOLS, '')
    .replace(/\s+/g, ' ')
    // Tidy the orphan spaces a stripped emoji leaves next to delimiters/punctuation
    // (e.g. «🔎 CIMA» → «CIMA», "botón 📝." → "botón.").
    .replace(/([«(])\s*,\s*/g, '$1')   // "(🔗, solo" → "(solo"
    .replace(/([«("¡¿])\s+/g, '$1')
    .replace(/\s+([»).,:;!?])/g, '$1');
}

// ── Inline HTML → styled runs ───────────────────────────────────────────────────
// Returns [{ text, style }] where style ∈ plain|bold|code|italic|chip|link.
function inlineToRuns(html) {
  const runs = [];
  const stack = ['plain'];
  const cur = () => stack[stack.length - 1];
  const push = (text, style) => { if (text) runs.push({ text, style }); };
  const re = /<(\/?)([a-z0-9]+)([^>]*)>/gi;
  let last = 0, m;
  while ((m = re.exec(html))) {
    push(html.slice(last, m.index), cur());
    last = re.lastIndex;
    const closing = m[1] === '/', tag = m[2].toLowerCase(), attrs = m[3] || '';
    if (tag === 'br') { push('\n', cur()); continue; }
    if (closing) { if (stack.length > 1) stack.pop(); continue; }
    let style = cur();
    if (tag === 'b' || tag === 'strong') style = 'bold';
    else if (tag === 'code') style = 'code';
    else if (tag === 'em' || tag === 'i') style = 'italic';
    else if (tag === 'span') style = /qt-chip-inline/.test(attrs) ? 'chip' : cur();
    else if (tag === 'a') style = 'link';
    stack.push(style);
  }
  push(html.slice(last), cur());
  return runs;
}
// Clean each run; wrap chips in « »; drop the ones that became empty.
function normRuns(rawRuns) {
  const out = [];
  for (const r of rawRuns) {
    let t = clean(r.text);
    if (r.style === 'chip') { t = t.trim(); if (t) t = '«' + t + '»'; }
    if (t) out.push({ text: t, style: r.style });
  }
  // A stripped emoji that lived in its own tag (e.g. <b>💊</b>) leaves two runs each
  // ending/starting with a space; drop the doubled space across the boundary.
  for (let i = 1; i < out.length; i++) {
    if (/\s$/.test(out[i - 1].text) && /^\s/.test(out[i].text)) out[i].text = out[i].text.replace(/^\s+/, '');
  }
  return out.filter(r => r.text);
}

// ── Flow parsing (paragraphs + lists, with the inline text between them) ─────────
function parseFlow(html) {
  const items = [];
  const pushInline = frag => { const runs = normRuns(inlineToRuns(frag)); if (runs.length) items.push({ type: 'para', runs }); };
  const re = /<(ul|ol|p)\b([^>]*)>([\s\S]*?)<\/\1>/gi;
  let last = 0, m;
  while ((m = re.exec(html))) {
    pushInline(html.slice(last, m.index));
    last = re.lastIndex;
    const tag = m[1].toLowerCase();
    if (tag === 'p') { pushInline(m[3]); continue; }
    const ordered = tag === 'ol';
    const li = /<li\b[^>]*>([\s\S]*?)<\/li>/gi;
    let lm, idx = 0;
    while ((lm = li.exec(m[3]))) { const runs = normRuns(inlineToRuns(lm[1])); if (runs.length) items.push({ type: 'li', runs, ordered, index: ++idx }); }
  }
  pushInline(html.slice(last));
  return items;
}

// ── pdfkit helpers ──────────────────────────────────────────────────────────────
function styleFont(doc, style, base) {
  switch (style) {
    case 'bold': return doc.font('Helvetica-Bold').fillColor(base);
    case 'code': return doc.font('Courier').fillColor('#0f5f9a');
    case 'italic': return doc.font('Helvetica-Oblique').fillColor(base);
    case 'chip': return doc.font('Helvetica-Bold').fillColor(BRAND);
    case 'link': return doc.font('Helvetica').fillColor(BRAND);
    default: return doc.font('Helvetica').fillColor(base);
  }
}
// Render styled runs as one wrapping paragraph starting at x, with hanging indent.
function renderRuns(doc, runs, o) {
  doc.fontSize(o.size);
  runs.forEach((r, i) => {
    const last = i === runs.length - 1;
    styleFont(doc, r.style, o.base);
    const opts = { width: o.width, continued: !last };
    if (i === 0) doc.text(r.text, o.x, doc.y, opts); else doc.text(r.text, opts);
  });
}
function renderFlow(doc, items, o) {
  const x0 = o.x, size = o.size, base = o.base;
  items.forEach(it => {
    if (it.type === 'para') {
      // Keep the first line from being orphaned at the very bottom of a page.
      if (o.ensure) o.ensure(size * 2.2);
      renderRuns(doc, it.runs, { x: x0, width: o.width, size, base });
      doc.moveDown(0.5);
    } else {
      // Reserve room for the marker + first line together, THEN capture y — otherwise a
      // marker drawn at the page bottom paginates and the stale y strands a lone bullet
      // on an otherwise-blank page.
      if (o.ensure) o.ensure(size * 2.4);
      const marker = it.ordered ? it.index + '.' : '•';
      const y0 = doc.y;
      doc.font('Helvetica-Bold').fontSize(size).fillColor(BRAND).text(marker, x0, y0, { width: 15 });
      doc.y = y0;
      renderRuns(doc, it.runs, { x: x0 + 18, width: o.width - 18, size, base });
      doc.moveDown(0.32);
    }
  });
}
// Overestimate a flow's height (bold font = widest) so a note box is never too short.
function measureFlow(doc, items, width, size) {
  let h = 0;
  items.forEach(it => {
    doc.font('Helvetica-Bold').fontSize(size);
    const plain = it.runs.map(r => r.text).join('');
    const w = it.type === 'li' ? width - 18 : width;
    h += doc.heightOfString(plain, { width: w }) + (it.type === 'li' ? size * 0.5 : size * 0.7);
  });
  return h;
}

function renderNote(doc, inner, attrs, ctx) {
  const items = parseFlow(inner);
  if (!items.length) return;
  const variant = /warn/.test(attrs) ? 'warn' : (/tip/.test(attrs) ? 'tip' : 'note');
  const accent = variant === 'warn' ? '#c2410c' : (variant === 'tip' ? '#0e7490' : '#475569');
  const bg = variant === 'warn' ? '#fdf1e7' : (variant === 'tip' ? '#e8f4f8' : '#f1f5f9');
  const label = variant === 'warn' ? 'IMPORTANTE' : (variant === 'tip' ? 'CONSEJO' : 'NOTA');
  const { M, CW } = ctx;
  const padX = 14, padY = 11, barW = 4, labelH = 14;
  const textX = M + padX + barW, textW = CW - padX * 2 - barW;
  const bodyH = measureFlow(doc, items, textW, 9.5);
  const boxH = padY + labelH + bodyH + padY;
  ctx.ensure(boxH + 8);
  const y = doc.y;
  doc.roundedRect(M, y, CW, boxH, 8).fill(bg);
  doc.rect(M, y, barW, boxH).fill(accent);
  doc.fillColor(accent).font('Helvetica-Bold').fontSize(8.5).text(label, textX, y + padY, { characterSpacing: 1.2 });
  doc.y = y + padY + labelH;
  renderFlow(doc, items, { x: textX, width: textW, size: 9.5, base: '#334155' });
  doc.y = y + boxH + 10;
}

// Render a whole section body: note boxes are pulled out, everything else flows.
function renderSectionBody(doc, html, ctx) {
  const noteRe = /<div\b([^>]*qt-note[^>]*)>([\s\S]*?)<\/div>/gi;
  let last = 0, m;
  while ((m = noteRe.exec(html))) {
    renderFlow(doc, parseFlow(html.slice(last, m.index)), { x: ctx.M, width: ctx.CW, size: 10, base: INK, ensure: ctx.ensure });
    last = noteRe.lastIndex;
    renderNote(doc, m[2], m[1], ctx);
  }
  renderFlow(doc, parseFlow(html.slice(last)), { x: ctx.M, width: ctx.CW, size: 10, base: INK, ensure: ctx.ensure });
}

// ── Public API ──────────────────────────────────────────────────────────────────
// buildHelpPdf({ title, subtitle, appLabel, sections, dateLabel }) → Promise<Buffer>
function buildHelpPdf({ title, subtitle, appLabel, sections, dateLabel }) {
  return new Promise((resolve, reject) => {
    const doc = new PDFDocument({ size: 'A4', margin: 50, bufferPages: true, info: { Title: clean(title) } });
    const chunks = [];
    doc.on('data', c => chunks.push(c));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    const M = doc.page.margins.left;
    const CW = doc.page.width - doc.page.margins.left - doc.page.margins.right;
    const bottom = () => doc.page.height - doc.page.margins.bottom;
    const ctx = { M, CW, ensure: h => { if (doc.y + h > bottom()) doc.addPage(); } };
    const secs = (Array.isArray(sections) ? sections : []).filter(s => s && s.title);

    // Cover band.
    const bandH = 104, top = doc.y;
    const grad = doc.linearGradient(M, top, M + CW, top + bandH);
    grad.stop(0, BRAND_DK).stop(1, BRAND);
    doc.roundedRect(M, top, CW, bandH, 16).fill(grad);
    doc.fillColor('#bcd7ef').font('Helvetica-Bold').fontSize(9)
      .text(clean(appLabel).toUpperCase(), M + 24, top + 20, { characterSpacing: 1.6, width: CW - 200 });
    if (dateLabel) doc.fillColor('#bcd7ef').font('Helvetica').fontSize(9)
      .text(clean(dateLabel), M + CW - 210, top + 20, { width: 186, align: 'right' });
    doc.fillColor('#ffffff').font('Helvetica-Bold').fontSize(22).text(clean(title), M + 24, top + 38, { width: CW - 48 });
    doc.fillColor('#e0edf8').font('Helvetica').fontSize(10.5).text(clean(subtitle), M + 24, doc.y + 3, { width: CW - 48 });
    doc.y = top + bandH + 22;

    // Contents index.
    doc.fillColor(BRAND_DK).font('Helvetica-Bold').fontSize(13).text('Contenido', M, doc.y);
    doc.moveDown(0.5);
    secs.forEach((s, i) => {
      ctx.ensure(17);
      const y = doc.y;
      doc.fillColor(BRAND).font('Helvetica-Bold').fontSize(10).text((i + 1) + '.', M, y, { width: 22 });
      doc.fillColor('#334155').font('Helvetica').fontSize(10).text(clean(s.title), M + 24, y, { width: CW - 24 });
    });
    doc.moveDown(0.4);
    let ry = doc.y; doc.moveTo(M, ry).lineTo(M + CW, ry).lineWidth(1).strokeColor(LINE).stroke();
    doc.y = ry + 16;

    // Sections.
    secs.forEach((s, i) => {
      ctx.ensure(56);
      const y = doc.y, bw = 24, bh = 20;
      doc.roundedRect(M, y, bw, bh, 6).fill(BRAND);
      doc.fillColor('#ffffff').font('Helvetica-Bold').fontSize(11).text(String(i + 1), M, y + 5, { width: bw, align: 'center' });
      doc.fillColor(BRAND_DK).font('Helvetica-Bold').fontSize(14).text(clean(s.title), M + bw + 12, y + 3, { width: CW - bw - 12 });
      doc.y = Math.max(doc.y, y + bh);
      const hy = doc.y + 4; doc.moveTo(M, hy).lineTo(M + CW, hy).lineWidth(0.8).strokeColor(LINE).stroke();
      doc.y = hy + 10;
      renderSectionBody(doc, String(s.html || ''), ctx);
      doc.moveDown(0.9);
    });

    // Footers (page numbers) across all buffered pages.
    const range = doc.bufferedPageRange();
    for (let i = 0; i < range.count; i++) {
      doc.switchToPage(range.start + i);
      doc.page.margins.bottom = 0;
      const fy = doc.page.height - 34;
      doc.font('Helvetica').fontSize(8).fillColor('#94a3b8');
      doc.text(clean(appLabel) + " · Jokin's Tools", M, fy, { width: CW / 2, align: 'left', lineBreak: false });
      doc.text('Página ' + (i + 1) + ' de ' + range.count, M + CW / 2, fy, { width: CW / 2, align: 'right', lineBreak: false });
    }

    doc.end();
  });
}

// Express handler shared by the three apps' `POST /api/help/pdf` routes. The client
// posts the help sections it renders on screen (single source of truth); we validate,
// cap sizes and stream back the PDF as a download.
async function handleHelpPdf(req, res, opts) {
  try {
    const b = req.body || {};
    const raw = Array.isArray(b.sections) ? b.sections : [];
    if (!raw.length) return res.status(400).json({ error: 'No hay contenido de ayuda que exportar.' });
    if (raw.length > 80) return res.status(400).json({ error: 'Demasiadas secciones para el PDF.' });
    const sections = raw.map(s => ({
      icon: s && typeof s.icon === 'string' ? s.icon.slice(0, 8) : '',
      title: String((s && s.title) || '').slice(0, 300),
      html: String((s && s.html) || '').slice(0, 60000),
    })).filter(s => s.title);
    if (!sections.length) return res.status(400).json({ error: 'No hay contenido de ayuda que exportar.' });
    const title = (b.title ? String(b.title) : opts.defaultTitle).slice(0, 200);
    const subtitle = (b.subtitle != null ? String(b.subtitle) : opts.defaultSubtitle).slice(0, 400);
    let dateLabel = '';
    try { dateLabel = new Date().toLocaleDateString('es-ES', { day: '2-digit', month: 'long', year: 'numeric' }); } catch { dateLabel = ''; }
    const buf = await buildHelpPdf({ title, subtitle, appLabel: opts.appLabel, sections, dateLabel });
    const fname = opts.filename || ('Manual_' + String(opts.appLabel).replace(/[^\w]+/g, '_') + '.pdf');
    const ascii = fname.replace(/[^\x20-\x7E]/g, '_').replace(/["\\]/g, '_');
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(fname)}`);
    res.send(buf);
  } catch (err) {
    console.error('[help-pdf] error:', err);
    res.status(500).json({ error: 'No se pudo generar el PDF del manual.' });
  }
}

module.exports = { buildHelpPdf, handleHelpPdf };
