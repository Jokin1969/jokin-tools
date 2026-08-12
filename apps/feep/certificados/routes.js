'use strict';

// ── Certificado de asistencia — API + UI ────────────────────────────────────────
// Mounted at /feep/certificados. Generates elegant attendance certificates as PDF,
// keeps a per-user repository (recover / re-download / email / delete) and stores
// reusable defaults (logo, signature, signer) so they need not be re-entered.

const express = require('express');
const path = require('path');
const multer = require('multer');
const sharp = require('sharp');
const nodemailer = require('nodemailer');
const db = require('../db');
const { render, renderPng, THEMES } = require('./pdf');

const router = express.Router();
const PUB = path.join(__dirname, '../public');

// Image data URLs make bodies larger than the hub-wide 1 MB default; the client
// sends already-processed (downscaled) data URLs so this stays comfortable.
const json = express.json({ limit: '8mb' });

// Raw image uploads (logo/signature) are processed server-side with sharp so ANY
// format works — including iPhone HEIC, which browsers can't decode client-side.
const uploadImage = multer({ storage: multer.memoryStorage(), limits: { fileSize: 30 * 1024 * 1024 } });

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[feep/certificados] error:', err);
  res.status(status).json({ error: err.message || 'Error en el certificado.' });
}

function safeStem(name) {
  return String(name || 'certificado').replace(/[^\w.\- áéíóúñÁÉÍÓÚÑ]/gi, '_').trim().slice(0, 80) || 'certificado';
}
function setDownload(res, filename, mime) {
  const ascii = filename.replace(/[^\x20-\x7E]/g, '_').replace(/["\\]/g, '_');
  res.setHeader('Content-Type', mime);
  res.setHeader('Content-Disposition',
    `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(filename)}`);
}

// Turn a signature's near-white background transparent. Luminance-based: bright
// pixels become fully transparent, dark ink stays opaque, mid-tones (anti-aliased
// edges) get partial alpha for a clean cut-out. Any existing transparency is kept.
async function whiteToTransparent(pipe) {
  const { data, info } = await pipe.ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const ch = info.channels; // 4 (RGBA)
  const WHITE = 236, INK = 120; // luminance thresholds
  for (let i = 0; i < data.length; i += ch) {
    const L = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    let a;
    if (L >= WHITE) a = 0;
    else if (L <= INK) a = 255;
    else a = Math.round(255 * (WHITE - L) / (WHITE - INK));
    if (a < data[i + 3]) data[i + 3] = a; // never increase existing transparency
  }
  return sharp(data, { raw: { width: info.width, height: info.height, channels: ch } })
    .png({ compressionLevel: 9 }).toBuffer();
}

// Validate + normalise the certificate fields coming from the client.
function cleanData(body) {
  const b = body || {};
  const str = (v, max) => (v == null ? null : String(v).trim().slice(0, max) || null);
  const img = (v) => {
    if (!v) return null;
    if (typeof v !== 'string' || !/^data:image\/[a-z0-9.+-]+;base64,/i.test(v)) {
      const e = new Error('Imagen no válida.'); e.status = 400; throw e;
    }
    if (v.length > 2_800_000) { const e = new Error('La imagen es demasiado grande (redúcela).'); e.status = 413; throw e; }
    return v;
  };
  const accent = THEMES[b.accent] ? b.accent : 'clasico';
  return {
    recipient_name: str(b.recipient_name, 160),
    role: str(b.role, 60),
    event: str(b.event, 400),
    talk_title: str(b.talk_title, 300),
    date_text: str(b.date_text, 120),
    event_date: /^\d{4}-\d{2}-\d{2}$/.test(String(b.event_date || '')) ? String(b.event_date) : null,
    place: str(b.place, 120),
    signer_name: str(b.signer_name, 160),
    signer_role: str(b.signer_role, 200),
    foundation: str(b.foundation, 200) || db.FOUNDATION,
    logo_data: img(b.logo_data),
    signature_data: img(b.signature_data),
    seal_mode: ['emblema', 'ninguno', 'imagen'].includes(b.seal_mode) ? b.seal_mode : 'emblema',
    seal_data: img(b.seal_data),
    accent,
    orientation: b.orientation === 'vertical' ? 'vertical' : 'horizontal',
  };
}

const certToRender = (c) => ({
  ref: c.ref, recipient_name: c.recipient_name, role: c.role, event: c.event,
  talk_title: c.talk_title, date_text: c.date_text, event_date: c.event_date, place: c.place,
  signer_name: c.signer_name, signer_role: c.signer_role, foundation: c.foundation,
  logo_data: c.logo_data, signature_data: c.signature_data,
  seal_mode: c.seal_mode, seal_data: c.seal_data, accent: c.accent,
  orientation: c.orientation,
});

// Render data for a SAVED certificate. If it has no logo/signature/seal of its
// own, fall back to the owner's current defaults — so setting them once (as
// defaults) makes every saved certificate render complete, including ones created
// in bulk before the images were uploaded.
function renderData(cert, userId) {
  const base = certToRender(cert);
  const def = db.getDefaults(userId) || {};
  if (!base.logo_data) base.logo_data = def.logo_data || null;
  if (!base.signature_data) base.signature_data = def.signature_data || null;
  if (!base.signer_name) base.signer_name = def.signer_name || base.signer_name;
  if (!base.signer_role) base.signer_role = def.signer_role || base.signer_role;
  if (!base.orientation) base.orientation = def.orientation || base.orientation;
  if (!base.seal_mode) base.seal_mode = def.seal_mode || 'emblema';
  if (base.seal_mode === 'imagen' && !base.seal_data) base.seal_data = def.seal_data || null;
  return base;
}

// ── UI ───────────────────────────────────────────────────────────────────────
router.get('/', (req, res) => res.sendFile(path.join(PUB, 'certificados.html')));

// ── Meta: defaults + capabilities ──────────────────────────────────────────────
router.get('/api/meta', (req, res) => {
  try {
    const d = db.getDefaults(req.user.id);
    res.json({
      foundation: db.FOUNDATION,
      themes: Object.keys(THEMES),
      emailConfigured: !!(process.env.SMTP_USER && process.env.SMTP_PASS),
      defaultEmail: (req.user && req.user.email) || '',
      defaults: d,
    });
  } catch (err) { fail(res, err); }
});

// ── Reusable defaults ──────────────────────────────────────────────────────────
router.post('/api/defaults', json, (req, res) => {
  try {
    const b = req.body || {};
    const img = (v) => {
      if (!v) return null;
      if (!/^data:image\//i.test(v)) { const e = new Error('Imagen no válida.'); e.status = 400; throw e; }
      if (v.length > 2_800_000) { const e = new Error('Imagen demasiado grande.'); e.status = 413; throw e; }
      return v;
    };
    const saved = db.saveDefaults(req.user.id, {
      logo_data: img(b.logo_data),
      signature_data: img(b.signature_data),
      seal_mode: ['emblema', 'ninguno', 'imagen'].includes(b.seal_mode) ? b.seal_mode : null,
      seal_data: img(b.seal_data),
      signer_name: b.signer_name ? String(b.signer_name).slice(0, 160) : null,
      signer_role: b.signer_role ? String(b.signer_role).slice(0, 200) : null,
      foundation: b.foundation ? String(b.foundation).slice(0, 200) : db.FOUNDATION,
      accent: THEMES[b.accent] ? b.accent : null,
      orientation: b.orientation === 'vertical' ? 'vertical' : (b.orientation === 'horizontal' ? 'horizontal' : null),
    });
    res.json({ defaults: saved });
  } catch (err) { fail(res, err); }
});

// ── Process an uploaded image (logo/signature) → normalised data URL ───────────
// Accepts any format sharp can read (PNG, JPEG, WEBP, TIFF, GIF, HEIC/HEIF…),
// auto-orients via EXIF, downscales, and returns a compact data URL: PNG when the
// image has transparency (signatures), JPEG otherwise (photos/logos).
router.post('/api/image', uploadImage.single('image'), async (req, res) => {
  try {
    if (!req.file || !req.file.buffer || !req.file.buffer.length) {
      const e = new Error('No se recibió ninguna imagen.'); e.status = 400; throw e;
    }
    const kind = ['logo', 'signature', 'seal'].includes(req.query.kind) ? req.query.kind : 'signature';
    const maxDim = kind === 'logo' ? 900 : (kind === 'seal' ? 700 : 1000);

    let meta;
    try { meta = await sharp(req.file.buffer, { failOn: 'none' }).metadata(); }
    catch { const e = new Error('No se pudo leer la imagen (formato no soportado).'); e.status = 400; throw e; }

    const pipe = sharp(req.file.buffer, { failOn: 'none' })
      .rotate() // auto-orient from EXIF (iPhone photos)
      .resize({ width: maxDim, height: maxDim, fit: 'inside', withoutEnlargement: true });

    let mime, out;
    if (kind === 'signature' || kind === 'seal') {
      // Remove the (near-white) background so the signature/seal sits cleanly on
      // the certificate: white → transparent, ink → opaque, edges → partial alpha.
      out = await whiteToTransparent(pipe);
      mime = 'image/png';
    } else if (meta.hasAlpha) {
      out = await pipe.png({ compressionLevel: 9 }).toBuffer(); mime = 'image/png';
    } else {
      out = await pipe.jpeg({ quality: 88, mozjpeg: true }).toBuffer(); mime = 'image/jpeg';
    }

    const dataUrl = `data:${mime};base64,${out.toString('base64')}`;
    if (dataUrl.length > 2_800_000) { const e = new Error('La imagen es demasiado grande incluso reducida.'); e.status = 413; throw e; }
    res.json({ dataUrl });
  } catch (err) { fail(res, err); }
});

// ── Live preview (render unsaved data) ─────────────────────────────────────────
router.post('/api/preview', json, async (req, res) => {
  try {
    const data = cleanData(req.body);
    if (!data.recipient_name) data.recipient_name = 'Nombre y apellidos';
    const payload = { ...data, ref: (req.body && req.body.ref) || '' };
    // The download button asks for the real PDF; the live preview wants a PNG.
    if (req.query.format === 'pdf') {
      const buf = await render(payload);
      res.setHeader('Content-Type', 'application/pdf');
      return res.send(buf);
    }
    // Serve a PNG so the preview shows on every device (iOS Safari won't render a
    // PDF blob in an <img>). Fall back to the PDF if pdftoppm isn't available.
    try {
      const png = await renderPng(payload);
      res.setHeader('Content-Type', 'image/png');
      res.send(png);
    } catch {
      const buf = await render(payload);
      res.setHeader('Content-Type', 'application/pdf');
      res.send(buf);
    }
  } catch (err) { fail(res, err); }
});

// ── Repository: list / create / get / delete ───────────────────────────────────
router.get('/api/list', (req, res) => {
  try { res.json({ items: db.listCerts(req.user.id) }); } catch (err) { fail(res, err); }
});

router.post('/api/create', json, (req, res) => {
  try {
    const data = cleanData(req.body);
    if (!data.recipient_name) { const e = new Error('Indica el nombre y apellidos de la persona.'); e.status = 400; throw e; }
    const cert = db.createCert(data, req.user.id);
    res.status(201).json({ item: cert });
  } catch (err) { fail(res, err); }
});

router.get('/api/cert/:id(\\d+)', (req, res) => {
  try {
    const c = db.getCert(Number(req.params.id), req.user.id);
    if (!c) return res.status(404).json({ error: 'No encontrado' });
    res.json({ item: c });
  } catch (err) { fail(res, err); }
});

router.delete('/api/cert/:id(\\d+)', (req, res) => {
  try {
    const ok = db.removeCert(Number(req.params.id), req.user.id);
    if (!ok) return res.status(404).json({ error: 'No encontrado' });
    res.json({ ok: true });
  } catch (err) { fail(res, err); }
});

// ── Download a saved certificate as PDF ────────────────────────────────────────
router.get('/api/cert/:id(\\d+)/pdf', async (req, res) => {
  try {
    const c = db.getCert(Number(req.params.id), req.user.id);
    if (!c) return res.status(404).json({ error: 'No encontrado' });
    const buf = await render(renderData(c, req.user.id));
    setDownload(res, `Certificado_${safeStem(c.recipient_name)}.pdf`, 'application/pdf');
    res.send(buf);
  } catch (err) { fail(res, err); }
});

// ── Email a saved certificate (reuses the hub's SMTP config) ───────────────────
router.post('/api/cert/:id(\\d+)/email', json, async (req, res) => {
  try {
    const c = db.getCert(Number(req.params.id), req.user.id);
    if (!c) { const e = new Error('Certificado no encontrado.'); e.status = 404; throw e; }
    const user = process.env.SMTP_USER, pass = process.env.SMTP_PASS;
    if (!user || !pass) { const e = new Error('El envío por email no está configurado (faltan SMTP_USER / SMTP_PASS).'); e.status = 503; throw e; }
    const to = ((req.body && req.body.to) || '').trim() || (req.user && req.user.email);
    if (!to || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(to)) { const e = new Error('Destinatario de email no válido.'); e.status = 400; throw e; }

    const buf = await render(renderData(c, req.user.id));
    const transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || 'smtp.gmail.com',
      port: Number(process.env.SMTP_PORT) || 587,
      secure: process.env.SMTP_SECURE === 'true',
      auth: { user, pass },
    });
    const html = `<!DOCTYPE html><html lang="es"><body style="margin:0;background:#f2efe7;font-family:Georgia,serif;padding:28px 16px;">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
        <table width="520" cellpadding="0" cellspacing="0" style="max-width:520px;width:100%;background:#fff;border:1px solid #e2ddd0;border-radius:12px;overflow:hidden;">
          <tr><td style="background:#1b2a4a;padding:22px 28px;">
            <p style="margin:0;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#c9b280;">Fundación Española de Enfermedades Priónicas</p>
            <h1 style="margin:6px 0 0;font-size:20px;color:#fbf9f3;">Certificado de asistencia</h1>
          </td></tr>
          <tr><td style="padding:26px 28px;color:#33322e;font-size:15px;line-height:1.6;">
            <p style="margin:0 0 10px;">Adjuntamos el certificado de asistencia a nombre de <strong>${escapeHtml(c.recipient_name)}</strong>.</p>
            <p style="margin:0;color:#8a8578;font-size:13px;">Referencia: ${escapeHtml(c.ref || '')}</p>
          </td></tr>
        </table>
      </td></tr></table></body></html>`;

    await transporter.sendMail({
      from: process.env.EMAIL_FROM || `"FEEP · Certificados" <${user}>`,
      to,
      subject: `Certificado de asistencia · ${c.recipient_name}`,
      html,
      attachments: [{ filename: `Certificado_${safeStem(c.recipient_name)}.pdf`, content: buf, contentType: 'application/pdf' }],
    });
    res.json({ ok: true, to });
  } catch (err) { fail(res, err); }
});

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

module.exports = router;
