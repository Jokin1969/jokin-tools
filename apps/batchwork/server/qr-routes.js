'use strict';

// ── QRs — Miscelánea section of Batchwork ──────────────────────────────────────
// Generate styled QR codes from a URL, export to PNG/JPEG/WEBP/SVG/PDF, e-mail
// them, and keep a persistent per-user repository. Mounted under /batchwork/api/qr.

const express = require('express');
const nodemailer = require('nodemailer');
const render = require('./qr-render');
const store = require('./qr-store');

const router = express.Router();

// Logo dataURLs make these bodies larger than the default; the client downscales
// logos so the payload stays comfortably under the hub-wide 1 MB JSON limit.
const json = express.json({ limit: '1mb' });

const FORMATS = ['png', 'jpeg', 'webp', 'svg', 'pdf'];
const EXT_MIME = {
  png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg',
  webp: 'image/webp', svg: 'image/svg+xml', pdf: 'application/pdf',
};

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[batchwork/qr] error:', err);
  res.status(status).json({ error: err.message || 'Error generando el QR.' });
}

// Sanitise a filename stem so it's safe in a Content-Disposition header.
function safeStem(name) {
  const stem = String(name || 'qr').replace(/[^\w.\- áéíóúñ]/gi, '_').trim().slice(0, 80) || 'qr';
  return stem;
}
function setDownload(res, filename, mime) {
  const ascii = filename.replace(/[^\x20-\x7E]/g, '_').replace(/["\\]/g, '_');
  res.setHeader('Content-Type', mime);
  res.setHeader('Content-Disposition',
    `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(filename)}`);
}

// ── Meta: style previews, ECC levels, defaults ──────────────────────────────────
router.get('/meta', (req, res) => {
  try {
    res.json({
      styles: render.stylePreviews(),
      ecc: render.ECC_LEVELS,
      formats: FORMATS,
      defaultEmail: req.user && req.user.email ? req.user.email : '',
    });
  } catch (err) { fail(res, err); }
});

// ── Live preview: returns the SVG for the given config ──────────────────────────
router.post('/render', json, (req, res) => {
  try {
    const { svg, modules, ecc } = render.buildSvg(req.body || {});
    res.json({ svg, modules, ecc });
  } catch (err) { fail(res, err); }
});

// ── URL check (flexible validation → normalised form) ───────────────────────────
router.post('/validate', json, (req, res) => {
  const url = render.normalizeUrl((req.body || {}).url);
  res.json({ valid: !!url, url: url || null });
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

// ── E-mail the QR in the chosen format (reuses the hub's SMTP config) ────────────
router.post('/email', json, async (req, res) => {
  try {
    const { config = {}, format = 'png', name, to } = req.body || {};
    const fmt = FORMATS.includes(format) ? format : 'png';

    const user = process.env.SMTP_USER, pass = process.env.SMTP_PASS;
    if (!user || !pass) {
      const e = new Error('El envío por email no está configurado (faltan SMTP_USER / SMTP_PASS).');
      e.status = 503; throw e;
    }
    const recipient = (to && String(to).trim()) || (req.user && req.user.email) || process.env.EMAIL_TO;
    if (!recipient || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(recipient)) {
      const e = new Error('Destinatario de email no válido.'); e.status = 400; throw e;
    }

    const cfg = render.sanitizeConfig(config);
    const { buffer, mime, ext } = await render.exportConfig(config, fmt, { name });
    const stem = safeStem(name);

    const transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || 'smtp.gmail.com',
      port: Number(process.env.SMTP_PORT) || 587,
      secure: process.env.SMTP_SECURE === 'true',
      auth: { user, pass },
    });

    // Preview image inline (always a PNG, regardless of the attached format).
    const { buffer: previewPng } = await render.exportConfig(config, 'png', { name, width: 360 });
    const cid = 'qr-preview';

    const html = `<!DOCTYPE html><html lang="es"><body style="margin:0;background:#f0f0f0;font-family:Arial,sans-serif;padding:28px 16px;">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
        <table width="520" cellpadding="0" cellspacing="0" style="max-width:520px;width:100%;background:#fff;border:1px solid #d8d8d8;border-radius:12px;overflow:hidden;">
          <tr><td style="background:#0f1b2d;padding:22px 28px;">
            <p style="margin:0;font-family:'Courier New',monospace;font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:#7d8590;">Batchwork · Jokin's Tools</p>
            <h1 style="margin:6px 0 0;font-size:20px;color:#e6edf3;">Tu código QR</h1>
          </td></tr>
          <tr><td align="center" style="padding:28px;">
            <img src="cid:${cid}" alt="Código QR" style="width:240px;height:auto;border:1px solid #eee;border-radius:8px;"/>
            <p style="margin:18px 0 4px;font-size:16px;font-weight:700;color:#111;">${escapeHtml(name || stem)}</p>
            <p style="margin:0;font-size:13px;color:#1B6CB0;word-break:break-all;">${escapeHtml(cfg.url)}</p>
            <p style="margin:14px 0 0;font-size:12px;color:#888;">Adjunto en formato ${ext.toUpperCase()}.</p>
          </td></tr>
        </table>
      </td></tr></table></body></html>`;

    await transporter.sendMail({
      from: process.env.EMAIL_FROM || `"Batchwork" <${user}>`,
      to: recipient,
      subject: `[QRs] ${name || stem}`,
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

router.post('/save', json, (req, res) => {
  try {
    const { name, config = {} } = req.body || {};
    const cfg = render.sanitizeConfig(config); // validates URL etc.
    const { svg } = render.buildSvg(cfg);
    const saved = store.create({ name, url: cfg.url, config, thumb: svg }, req.user.id);
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

// ── Reusable logo library ───────────────────────────────────────────────────────
router.get('/logos', (req, res) => {
  try { res.json({ items: store.listLogos(req.user.id) }); } catch (err) { fail(res, err); }
});

router.post('/logos', json, (req, res) => {
  try {
    const { name, data } = req.body || {};
    if (!data || !/^data:image\//i.test(data)) { const e = new Error('Imagen no válida.'); e.status = 400; throw e; }
    if (data.length > 1200000) { const e = new Error('La imagen es demasiado grande para guardarla.'); e.status = 413; throw e; }
    res.status(201).json({ item: store.createLogo({ name, data }, req.user.id) });
  } catch (err) { fail(res, err); }
});

router.delete('/logos/:id(\\d+)', (req, res) => {
  try {
    const ok = store.removeLogo(Number(req.params.id), req.user.id);
    if (!ok) return res.status(404).json({ error: 'No encontrado' });
    res.json({ ok: true });
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
