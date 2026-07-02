const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { isAllowed } = require('./config');
const { kindOf } = require('./normalize');

// ─── Pure helpers (no I/O — unit tested) ──────────────────────────────────────

function senderOf(parsed) {
  const v = parsed && parsed.from && parsed.from.value && parsed.from.value[0];
  return v && v.address ? String(v.address).trim().toLowerCase() : '';
}

// Sanitise a filename for display/storage. Keeps the original extension unless
// `forceExt` (e.g. '.pdf') is given, in which case it replaces it.
function safeFilename(name, forceExt) {
  let base = String(name || 'documento').split(/[\\/]/).pop();
  base = base.replace(/[^\p{L}\p{N}.\-_() ]+/gu, '_').replace(/_{2,}/g, '_').replace(/^[_.\s]+|[_.\s]+$/g, '');
  if (!base) base = 'documento';
  if (forceExt) base = base.replace(/\.[^.]+$/, '') + forceExt;
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
//   { action: 'reject',  reason: 'sender', sender, ... }
//   { action: 'empty',   sender, messageId, subject, oversized }   (allowed, nothing to print)
//   { action: 'enqueue', sender, messageId, subject, docs: [...], oversized: [...] }
// `docs` are printable attachments (PDF/PNG/JPG/DOCX), each with its raw content.
// Never throws; pure function of its inputs.
function classifyMessage(parsed, cfg) {
  const sender = senderOf(parsed);
  const messageId = messageIdOf(parsed);
  const subject = parsed.subject || '';

  if (!isAllowed(cfg, sender)) {
    return { action: 'reject', reason: 'sender', sender, messageId, subject };
  }

  const docs = [];
  const oversized = [];
  let idx = 0;
  for (const att of (parsed.attachments || [])) {
    const kind = kindOf(att.filename, att.contentType);
    if (!kind) continue; // not a printable type
    const size = att.size || (att.content ? att.content.length : 0);
    const entry = {
      part_idx: idx++,
      filename: safeFilename(att.filename),
      mime: att.contentType || '',
      kind,
      size,
      content: att.content || null,
    };
    if (cfg.maxBytes && size > cfg.maxBytes) oversized.push(entry);
    else docs.push(entry);
  }

  if (!docs.length) return { action: 'empty', sender, messageId, subject, oversized };
  return { action: 'enqueue', sender, messageId, subject, docs, oversized };
}

// ─── Persistence (writes the normalised PDF to disk + a row to the queue) ──────

// Store one already-normalised PDF and enqueue it. `meta.filename` is the name
// shown to the user (original, e.g. carta.docx); the file on disk is a .pdf.
// Returns the created job. Caller must check db.jobExists first for dedupe.
function storeDoc(cfg, db, meta, pdfBuffer) {
  if (!fs.existsSync(cfg.storageDir)) fs.mkdirSync(cfg.storageDir, { recursive: true });
  const token = crypto.randomBytes(8).toString('hex');
  const filePath = path.join(cfg.storageDir, `${token}-${safeFilename(meta.filename, '.pdf')}`);
  fs.writeFileSync(filePath, pdfBuffer);
  return db.enqueueJob({
    message_id: meta.messageId,
    part_idx: meta.part_idx,
    sender: meta.sender,
    subject: meta.subject,
    filename: meta.filename,
    mime: 'application/pdf',
    printer: cfg.defaultPrinter || null,
    size_bytes: pdfBuffer.length,
    file_path: filePath,
  });
}

module.exports = {
  senderOf, safeFilename, messageIdOf, classifyMessage, storeDoc,
};
