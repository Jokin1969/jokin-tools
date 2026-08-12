'use strict';

// ── Sellos — Miscelánea section of Batchwork ──────────────────────────────────
// Design digital rubber stamps (round / oval / rectangular), curved border text,
// centre text / logo, ink colours and realistic distress textures. Export to
// PNG/JPEG/WEBP/SVG/PDF, e-mail them, and keep a persistent per-user repository.
// Mounted under /batchwork/api/stamp. Mirrors qr-routes.

const express = require('express');
const nodemailer = require('nodemailer');
const render = require('./stamp-render');
const store = require('./stamp-store');

const router = express.Router();
const json = express.json({ limit: '2mb' }); // central logo data URLs

const FORMATS = ['png', 'jpeg', 'webp', 'svg', 'pdf'];
const EXT_MIME = {
  png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg',
  webp: 'image/webp', svg: 'image/svg+xml', pdf: 'application/pdf',
};

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[batchwork/stamp] error:', err);
  res.status(status).json({ error: err.message || 'Error generando el sello.' });
}

function safeStem(name) {
  return String(name || 'sello').replace(/[^\w.\- áéíóúñ]/gi, '_').trim().slice(0, 80) || 'sello';
}
function setDownload(res, filename, mime) {
  const ascii = filename.replace(/[^\x20-\x7E]/g, '_').replace(/["\\]/g, '_');
  res.setHeader('Content-Type', mime);
  res.setHeader('Content-Disposition',
    `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(filename)}`);
}
function subtitleOf(cfg) {
  return [cfg.topText, cfg.centerText && String(cfg.centerText).replace(/\n/g, ' '), cfg.bottomText]
    .map((s) => String(s || '').trim()).filter(Boolean).join(' · ').slice(0, 160);
}

// ── Meta: shape/texture previews, ink presets, defaults ─────────────────────────
router.get('/meta', (req, res) => {
  try {
    res.json({
      shapes: render.shapePreviews(),
      textures: render.texturePreviews(),
      inks: render.INK_PRESETS,
      formats: FORMATS,
      defaultEmail: req.user && req.user.email ? req.user.email : '',
    });
  } catch (err) { fail(res, err); }
});

// ── Live preview: returns the SVG for the given config ──────────────────────────
router.post('/render', json, async (req, res) => {
  try {
    const { svg } = await render.buildSvgAsync(req.body || {});
    res.json({ svg });
  } catch (err) { fail(res, err); }
});

// ── Export to a downloadable file ───────────────────────────────────────────────
router.post('/export', json, async (req, res) => {
  try {
    const { config = {}, format = 'png', name } = req.body || {};
    const fmt = FORMATS.includes(format) ? format : 'png';
    const { buffer, mime, ext } = await render.exportConfig(config, fmt, { name });
    setDownload(res, `${safeStem(name)}.${ext}`, mime || EXT_MIME[ext]);
    res.send(buffer);
  } catch (err) { fail(res, err); }
});

// ── E-mail the stamp in the chosen format (reuses the hub's SMTP config) ─────────
router.post('/email', json, async (req, res) => {
  try {
    const { config = {}, format = 'png', name, to } = req.body || {};
    const fmt = FORMATS.includes(format) ? format : 'png';

    const user = process.env.SMTP_USER, pass = process.env.SMTP_PASS;
    if (!user || !pass) { const e = new Error('El envío por email no está configurado (faltan SMTP_USER / SMTP_PASS).'); e.status = 503; throw e; }
    const recipient = (to && String(to).trim()) || (req.user && req.user.email) || process.env.EMAIL_TO;
    if (!recipient || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(recipient)) { const e = new Error('Destinatario de email no válido.'); e.status = 400; throw e; }

    const { buffer, mime, ext } = await render.exportConfig(config, fmt, { name });
    const stem = safeStem(name);
    const { buffer: previewPng } = await render.exportConfig(config, 'png', { name, width: 360 });
    const cid = 'stamp-preview';

    const transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || 'smtp.gmail.com',
      port: Number(process.env.SMTP_PORT) || 587,
      secure: process.env.SMTP_SECURE === 'true',
      auth: { user, pass },
    });

    const html = `<!DOCTYPE html><html lang="es"><body style="margin:0;background:#f0f0f0;font-family:Arial,sans-serif;padding:28px 16px;">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
        <table width="520" cellpadding="0" cellspacing="0" style="max-width:520px;width:100%;background:#fff;border:1px solid #d8d8d8;border-radius:12px;overflow:hidden;">
          <tr><td style="background:#0f1b2d;padding:22px 28px;">
            <p style="margin:0;font-family:'Courier New',monospace;font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:#7d8590;">Batchwork · Jokin's Tools</p>
            <h1 style="margin:6px 0 0;font-size:20px;color:#e6edf3;">Tu sello</h1>
          </td></tr>
          <tr><td align="center" style="padding:28px;background:#f7f7f4;">
            <img src="cid:${cid}" alt="Sello" style="width:240px;height:auto;"/>
            <p style="margin:16px 0 4px;font-size:16px;font-weight:700;color:#111;">${escapeHtml(name || stem)}</p>
            <p style="margin:14px 0 0;font-size:12px;color:#888;">Adjunto en formato ${ext.toUpperCase()}.</p>
          </td></tr>
        </table>
      </td></tr></table></body></html>`;

    await transporter.sendMail({
      from: process.env.EMAIL_FROM || `"Batchwork" <${user}>`,
      to: recipient,
      subject: `[Sellos] ${name || stem}`,
      html,
      attachments: [
        { filename: `${stem}.${ext}`, content: buffer, contentType: mime || EXT_MIME[ext] },
        { filename: 'preview.png', content: previewPng, cid },
      ],
    });
    res.json({ ok: true, to: recipient });
  } catch (err) { fail(res, err); }
});

// ── Repository: list / save / get / delete ─────────────────────────────────────
router.get('/list', (req, res) => {
  try { res.json({ items: store.list(req.user.id) }); } catch (err) { fail(res, err); }
});

router.post('/save', json, async (req, res) => {
  try {
    const { name, config = {} } = req.body || {};
    const cfg = render.sanitizeConfig(config);
    const { svg } = await render.buildSvgAsync(config); // thumbnail with the logo inked
    const saved = store.create({ name, subtitle: subtitleOf(cfg), config, thumb: svg }, req.user.id);
    res.status(201).json({ item: saved });
  } catch (err) { fail(res, err); }
});

router.get('/:id(\\d+)', (req, res) => {
  try {
    const item = store.get(Number(req.params.id), req.user.id);
    if (!item) return res.status(404).json({ error: 'No encontrado' });
    res.json({ item });
  } catch (err) { fail(res, err); }
});

router.delete('/:id(\\d+)', (req, res) => {
  try {
    const ok = store.remove(Number(req.params.id), req.user.id);
    if (!ok) return res.status(404).json({ error: 'No encontrado' });
    res.json({ ok: true });
  } catch (err) { fail(res, err); }
});

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

module.exports = router;
