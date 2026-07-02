const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { isAllowed } = require('./config');

// ─── Pure helpers (no I/O — unit tested) ──────────────────────────────────────

function senderOf(parsed) {
  const v = parsed && parsed.from && parsed.from.value && parsed.from.value[0];
  return v && v.address ? String(v.address).trim().toLowerCase() : '';
}

function isPdf(att) {
  const type = String(att.contentType || '').toLowerCase();
  const name = String(att.filename || '').toLowerCase();
  return type === 'application/pdf' || name.endsWith('.pdf');
}

function safeFilename(name) {
  let base = String(name || 'documento.pdf').split(/[\\/]/).pop();
  base = base.replace(/[^\p{L}\p{N}.\-_() ]+/gu, '_').replace(/_{2,}/g, '_').replace(/^[_.\s]+|[_.\s]+$/g, '');
  if (!base) base = 'documento';
  if (!/\.pdf$/i.test(base)) base += '.pdf';
  return base.slice(0, 120);
}

// A stable id for dedupe: prefer the email's Message-ID; otherwise derive one
// deterministically so re-fetching the same email won't enqueue it twice.
function messageIdOf(parsed) {
  if (parsed.messageId) return String(parsed.messageId);
  const h = crypto.createHash('sha256');
  h.update(senderOf(parsed));
  h.update('|' + (parsed.subject || ''));
  h.update('|' + (parsed.date ? new Date(parsed.date).toISOString() : ''));
  for (const a of (parsed.attachments || [])) h.update('|' + (a.filename || '') + ':' + (a.size || 0));
  return 'gen:' + h.digest('hex');
}

// Decide what to do with a parsed email. Returns one of:
//   { action: 'reject',  reason: 'sender', sender }
//   { action: 'no_pdf',  sender, messageId, subject }        (allowed but nothing to print)
//   { action: 'enqueue', sender, messageId, subject, pdfs: [...], oversized: [...] }
// Never throws; pure function of its inputs.
function classifyMessage(parsed, cfg) {
  const sender = senderOf(parsed);
  const messageId = messageIdOf(parsed);
  const subject = parsed.subject || '';

  if (!isAllowed(cfg, sender)) {
    return { action: 'reject', reason: 'sender', sender, messageId, subject };
  }

  const pdfs = [];
  const oversized = [];
  let idx = 0;
  for (const att of (parsed.attachments || [])) {
    if (!isPdf(att)) continue;
    const size = att.size || (att.content ? att.content.length : 0);
    const entry = {
      part_idx: idx++,
      filename: safeFilename(att.filename),
      mime: 'application/pdf',
      size,
      content: att.content || null,
    };
    if (cfg.maxBytes && size > cfg.maxBytes) oversized.push(entry);
    else pdfs.push(entry);
  }

  if (!pdfs.length) return { action: 'no_pdf', sender, messageId, subject, oversized };
  return { action: 'enqueue', sender, messageId, subject, pdfs, oversized };
}

// ─── Persistence (writes PDFs to disk + rows to the queue) ─────────────────────

// Persist an 'enqueue' classification. Skips attachments already stored (dedupe
// by message_id + part_idx). Returns the jobs actually created.
function persistEnqueue(result, cfg, db) {
  if (!fs.existsSync(cfg.storageDir)) fs.mkdirSync(cfg.storageDir, { recursive: true });
  const created = [];
  for (const pdf of result.pdfs) {
    if (db.jobExists(result.messageId, pdf.part_idx)) continue;
    if (!pdf.content || !pdf.content.length) continue;
    const token = crypto.randomBytes(8).toString('hex');
    const filePath = path.join(cfg.storageDir, `${token}-${pdf.filename}`);
    fs.writeFileSync(filePath, pdf.content);
    const job = db.enqueueJob({
      message_id: result.messageId,
      part_idx: pdf.part_idx,
      sender: result.sender,
      subject: result.subject,
      filename: pdf.filename,
      mime: pdf.mime,
      printer: cfg.defaultPrinter || null,
      size_bytes: pdf.size,
      file_path: filePath,
    });
    created.push(job);
  }
  return created;
}

module.exports = {
  senderOf, isPdf, safeFilename, messageIdOf, classifyMessage, persistEnqueue,
};
