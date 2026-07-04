const nodemailer = require('nodemailer');
const crypto = require('crypto');
const path = require('path');
const fs = require('fs');

const DEACTIVATION_SECRET = process.env.DEACTIVATION_SECRET || 'change-this-secret';

// Uploaded images live next to the DB, in /data/uploads. They are now served
// behind login (see server.js), so emails can no longer link to a public URL —
// instead we attach the file inline via a Content-ID (cid:).
const UPLOADS_DIR = path.join(path.dirname(process.env.DB_PATH || '/data/jokin_tools.db'), 'uploads');
const EMAIL_IMAGE_CID = 'memory-image';

// Returns the absolute path to a memory's uploaded image, or null if there is
// none or the file is missing on disk.
function resolveImageFile(memory) {
  if (!memory.image_path) return null;
  const file = path.join(UPLOADS_DIR, path.basename(memory.image_path));
  return fs.existsSync(file) ? file : null;
}

// Lee BASE_URL en cada llamada, nunca cacheada, para que Railway la recoja
// correctamente tras añadir/cambiar la variable de entorno + redeploy.
function getBaseUrl() {
  const url = (process.env.BASE_URL || '').replace(/\/$/, '');
  if (!url || url.includes('localhost') || url.includes('127.0.0.1')) {
    console.warn('[email] WARNING: BASE_URL no definida o apunta a localhost. ' +
      'Las imágenes y links de desactivación no funcionarán en los emails. ' +
      'Configura BASE_URL=https://jokins-tools-production.up.railway.app en Railway y redespliega.');
  }
  return url || 'http://localhost:3000';
}

// ─── Transporter ─────────────────────────────────────────────────────────────

function createTransporter() {
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;

  if (!user || !pass) {
    throw new Error(
      'Credenciales SMTP no configuradas. ' +
      'Define SMTP_USER y SMTP_PASS en las variables de entorno de Railway.'
    );
  }

  return nodemailer.createTransport({
    host: process.env.SMTP_HOST || 'smtp.gmail.com',
    port: Number(process.env.SMTP_PORT) || 587,
    secure: process.env.SMTP_SECURE === 'true',
    auth: { user, pass }
  });
}

// ─── Deactivation token ───────────────────────────────────────────────────────

// Token binds to BOTH the memory id and its owner so a token forged/replayed for
// one memory can't target another user's memory. Older links (id-only) are no
// longer honoured — the recipient just toggles it off in the UI instead.
function generateDeactivationToken(memoryId, userId) {
  return crypto
    .createHmac('sha256', DEACTIVATION_SECRET)
    .update(`${memoryId}:${userId}`)
    .digest('hex');
}

// In production we must NOT run with the public default secret, otherwise anyone
// can forge deactivation links. The route uses this to fail closed.
function isDeactivationSecretConfigured() {
  return !!process.env.DEACTIVATION_SECRET;
}

// Only http(s) URLs are safe to render as links in an email.
function isSafeHttpUrl(value) {
  if (!value) return false;
  try {
    const u = new URL(String(value));
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

// ─── Color logic ──────────────────────────────────────────────────────────────

function getBadgeColor(timesRecalled) {
  if (timesRecalled <= 3)  return { bg: '#27AE60', label: 'Nuevo' };
  if (timesRecalled <= 5)  return { bg: '#F2C94C', label: 'Aprendiendo' };
  if (timesRecalled <= 8)  return { bg: '#F2994A', label: 'Progresando' };
  if (timesRecalled <= 11) return { bg: '#EB5757', label: 'Avanzado' };
  return { bg: '#C0392B', label: 'Experto' };
}

const FREQUENCY_LABELS = {
  '1w': '1 semana', '2w': '2 semanas', '3w': '3 semanas',
  '1m': '1 mes', '2m': '2 meses', '3m': '3 meses',
  '6m': '6 meses', '1y': '1 año'
};

// ─── Email HTML builder ───────────────────────────────────────────────────────

function buildEmailHTML(memory) {
  const baseUrl = getBaseUrl();
  const { bg, label } = getBadgeColor(memory.times_recalled);
  const deactivateToken = generateDeactivationToken(memory.id, memory.user_id);
  const deactivateUrl = `${baseUrl}/re-memory/api/deactivate/${memory.id}/${deactivateToken}`;
  const freqLabel = FREQUENCY_LABELS[memory.frequency] || memory.frequency;

  // Quick "change frequency" pills for the email footer (the current one is
  // marked, the rest link to the signed set-frequency route).
  const FREQ_ORDER = ['1w', '2w', '3w', '1m', '2m', '3m', '6m', '1y'];
  const freqPills = FREQ_ORDER.map(f => {
    const lbl = FREQUENCY_LABELS[f] || f;
    if (f === memory.frequency) {
      return `<span style="display:inline-block;margin:3px 4px 3px 0;padding:6px 11px;border-radius:16px;background:#1B6CB0;color:#fff;font-size:12px;font-family:'Courier New',monospace;">${lbl} ✓</span>`;
    }
    const url = `${baseUrl}/re-memory/api/set-frequency/${memory.id}/${f}/${deactivateToken}`;
    return `<a href="${url}" style="display:inline-block;margin:3px 4px 3px 0;padding:6px 11px;border-radius:16px;background:#eef2f7;color:#1B6CB0;font-size:12px;font-family:'Courier New',monospace;text-decoration:none;border:1px solid #d0d9e6;">${lbl}</a>`;
  }).join('');
  const createdAt = new Date(memory.created_at).toLocaleDateString('es-ES', {
    day: '2-digit', month: 'long', year: 'numeric'
  });

  // Image block — attached inline via cid: (file resolved in sendMemoryEmail)
  let imageBlock = '';
  if (resolveImageFile(memory)) {
    imageBlock = `
      <tr>
        <td style="padding: 0 40px 24px;">
          <img src="cid:${EMAIL_IMAGE_CID}" alt="Imagen de la memoria"
               style="max-width: 100%; height: auto; border-radius: 8px; border: 1px solid #ddd; display: block;" />
        </td>
      </tr>`;
  }

  // Source link block — only render http(s) URLs, and escape into the markup so
  // a crafted source_url can't inject HTML or a javascript:/data: scheme.
  let sourceBlock = '';
  const safeSourceUrl = isSafeHttpUrl(memory.source_url) ? memory.source_url : null;
  if (safeSourceUrl) {
    const shown = escapeHtml(safeSourceUrl);
    sourceBlock = `
      <tr>
        <td style="padding: 0 40px 16px;">
          <p style="margin:0; font-size:13px; color:#888;">
            Fuente: <a href="${shown}" target="_blank"
              style="color:#2D9CDB; text-decoration:none;">${shown}</a>
          </p>
        </td>
      </tr>`;
  }

  return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Re-memory — Es hora de recordar</title>
</head>
<body style="margin:0; padding:0; background-color:#f0f0f0; font-family: 'Segoe UI', Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f0f0; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%; background:#ffffff; border-radius:12px; overflow:hidden; border: 1px solid #d0d0d0; box-shadow:0 2px 12px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #2c2c3a 0%, #1a2332 100%); padding: 32px 40px; border-bottom: 2px solid ${bg};">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <p style="margin:0; font-family: 'Courier New', monospace; font-size:11px; letter-spacing:0.15em; text-transform:uppercase; color:#7d8590;">Re-memory · Jokin's Tools</p>
                    <h1 style="margin:8px 0 0; font-size:22px; font-weight:700; color:#e6edf3; font-family: 'Courier New', monospace;">Es hora de recordar</h1>
                  </td>
                  <td align="right" style="vertical-align:top;">
                    <div style="display:inline-block; background:${bg}; color:#fff; font-size:13px; font-weight:700; padding:6px 14px; border-radius:20px; font-family: 'Courier New', monospace; white-space:nowrap;">
                      × ${memory.times_recalled} &nbsp;${label}
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Metadata strip -->
          <tr>
            <td style="padding: 16px 40px; background: #f7f7f7; border-bottom: 1px solid #e0e0e0;">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding-right: 24px;">
                    <p style="margin:0; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.1em; font-family: 'Courier New', monospace;">Tema</p>
                    <p style="margin:4px 0 0; font-size:13px; color:#1B6CB0; font-weight:600;">${memory.topic}</p>
                  </td>
                  <td style="padding-right: 24px;">
                    <p style="margin:0; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.1em; font-family: 'Courier New', monospace;">Frecuencia</p>
                    <p style="margin:4px 0 0; font-size:13px; color:#333;">${freqLabel}</p>
                  </td>
                  <td>
                    <p style="margin:0; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.1em; font-family: 'Courier New', monospace;">Creada</p>
                    <p style="margin:4px 0 0; font-size:13px; color:#333;">${createdAt}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Description -->
          <tr>
            <td style="padding: 32px 40px 24px;">
              <div style="border-left: 3px solid ${bg}; padding-left: 20px;">
                <p style="margin:0; font-size:16px; line-height:1.7; color:#1a1a1a; white-space: pre-wrap;">${escapeHtml(memory.description)}</p>
              </div>
            </td>
          </tr>

          ${imageBlock}
          ${sourceBlock}

          <!-- Actions: change frequency -->
          <tr>
            <td style="padding: 20px 40px 6px; background: #f7f7f7; border-top: 1px solid #e0e0e0;">
              <p style="margin:0 0 8px; font-size:12px; color:#555; font-family:'Courier New',monospace;">🔁 Cambiar frecuencia del recordatorio:</p>
              <div>${freqPills}</div>
            </td>
          </tr>
          <!-- Actions: deactivate -->
          <tr>
            <td style="padding: 10px 40px 8px; background: #f7f7f7; text-align:center;">
              <a href="${deactivateUrl}"
                 style="display:inline-block; padding:9px 18px; border-radius:8px; background:#ffffff; color:#C0392B; border:1px solid #e0b4b0; font-size:12px; font-family:'Courier New',monospace; text-decoration:none;">
                ⏸ Desactivar hasta nueva orden
              </a>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 8px 40px 20px; background: #f7f7f7;">
              <p style="margin:0; font-size:11px; color:#999; text-align:center;">
                Enviado por <strong style="color:#1B6CB0;">Re-memory · Jokin's Tools</strong>
                <br /><span style="color:#aaa;">Al pulsar puede pedirte iniciar sesión.</span>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>`;
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── Send email ───────────────────────────────────────────────────────────────

async function sendMemoryEmail(memory, toEmail) {
  const recipient = toEmail || process.env.EMAIL_TO;
  if (!recipient) throw new Error('No recipient: el usuario no tiene email y EMAIL_TO no está definido');
  const transporter = createTransporter();
  const html = buildEmailHTML(memory);
  const subject = `[Re-memory] ${memory.topic}: ${memory.description.substring(0, 60)}${memory.description.length > 60 ? '…' : ''}`;

  // Attach the uploaded image inline so it renders without a public /uploads URL.
  const imageFile = resolveImageFile(memory);
  const attachments = imageFile
    ? [{ filename: path.basename(imageFile), path: imageFile, cid: EMAIL_IMAGE_CID }]
    : [];

  const info = await transporter.sendMail({
    from: process.env.EMAIL_FROM || '"Re-memory" <noreply@example.com>',
    to: recipient,
    subject,
    html,
    attachments
  });

  console.log(`[email] Sent memory #${memory.id} → ${info.messageId}`);
  return info;
}

module.exports = {
  sendMemoryEmail,
  generateDeactivationToken,
  isDeactivationSecretConfigured,
  getBadgeColor,
  buildEmailHTML
};
