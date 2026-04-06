const nodemailer = require('nodemailer');
const crypto = require('crypto');
const path = require('path');
const fs = require('fs');

const DEACTIVATION_SECRET = process.env.DEACTIVATION_SECRET || 'change-this-secret';

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

function generateDeactivationToken(memoryId) {
  return crypto
    .createHmac('sha256', DEACTIVATION_SECRET)
    .update(String(memoryId))
    .digest('hex');
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
  const deactivateToken = generateDeactivationToken(memory.id);
  const deactivateUrl = `${baseUrl}/re-memory/api/deactivate/${memory.id}/${deactivateToken}`;
  const freqLabel = FREQUENCY_LABELS[memory.frequency] || memory.frequency;
  const createdAt = new Date(memory.created_at).toLocaleDateString('es-ES', {
    day: '2-digit', month: 'long', year: 'numeric'
  });

  // Image block (inline if exists)
  let imageBlock = '';
  if (memory.image_path) {
    const filename = path.basename(memory.image_path);
    const imageUrl = `${baseUrl}/uploads/${filename}`;
    console.log(`[email] Image URL for memory #${memory.id}: ${imageUrl}`);
    imageBlock = `
      <tr>
        <td style="padding: 0 40px 24px;">
          <img src="${imageUrl}" alt="Imagen de la memoria"
               style="max-width: 100%; height: auto; border-radius: 8px; border: 1px solid #ddd; display: block;" />
        </td>
      </tr>`;
  }

  // Source link block
  let sourceBlock = '';
  if (memory.source_url) {
    sourceBlock = `
      <tr>
        <td style="padding: 0 40px 16px;">
          <p style="margin:0; font-size:13px; color:#888;">
            Fuente: <a href="${memory.source_url}" target="_blank"
              style="color:#2D9CDB; text-decoration:none;">${memory.source_url}</a>
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
<body style="margin:0; padding:0; background-color:#0d1117; font-family: 'Segoe UI', Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0d1117; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%; background:#161b22; border-radius:12px; overflow:hidden; border: 1px solid #21262d;">

          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #0d1117 0%, #1a2332 100%); padding: 32px 40px; border-bottom: 2px solid ${bg};">
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
            <td style="padding: 16px 40px; background: #0d1117; border-bottom: 1px solid #21262d;">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding-right: 24px;">
                    <p style="margin:0; font-size:11px; color:#7d8590; text-transform:uppercase; letter-spacing:0.1em; font-family: 'Courier New', monospace;">Tema</p>
                    <p style="margin:4px 0 0; font-size:13px; color:#2D9CDB; font-weight:600;">${memory.topic}</p>
                  </td>
                  <td style="padding-right: 24px;">
                    <p style="margin:0; font-size:11px; color:#7d8590; text-transform:uppercase; letter-spacing:0.1em; font-family: 'Courier New', monospace;">Frecuencia</p>
                    <p style="margin:4px 0 0; font-size:13px; color:#e6edf3;">${freqLabel}</p>
                  </td>
                  <td>
                    <p style="margin:0; font-size:11px; color:#7d8590; text-transform:uppercase; letter-spacing:0.1em; font-family: 'Courier New', monospace;">Creada</p>
                    <p style="margin:4px 0 0; font-size:13px; color:#e6edf3;">${createdAt}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Description -->
          <tr>
            <td style="padding: 32px 40px 24px;">
              <div style="border-left: 3px solid ${bg}; padding-left: 20px;">
                <p style="margin:0; font-size:16px; line-height:1.7; color:#e6edf3; white-space: pre-wrap;">${escapeHtml(memory.description)}</p>
              </div>
            </td>
          </tr>

          ${imageBlock}
          ${sourceBlock}

          <!-- Footer -->
          <tr>
            <td style="padding: 24px 40px; background: #0d1117; border-top: 1px solid #21262d;">
              <p style="margin:0; font-size:12px; color:#7d8590; text-align:center;">
                Enviado por <strong style="color:#2D9CDB;">Re-memory · Jokin's Tools</strong>
                <br />
                <a href="${deactivateUrl}"
                   style="color:#7d8590; text-decoration:underline; font-size:11px; margin-top:8px; display:inline-block;">
                  Desactivar este recordatorio
                </a>
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

async function sendMemoryEmail(memory) {
  const transporter = createTransporter();
  const html = buildEmailHTML(memory);
  const subject = `[Re-memory] ${memory.topic}: ${memory.description.substring(0, 60)}${memory.description.length > 60 ? '…' : ''}`;

  const info = await transporter.sendMail({
    from: process.env.EMAIL_FROM || '"Re-memory" <noreply@example.com>',
    to: process.env.EMAIL_TO,
    subject,
    html
  });

  console.log(`[email] Sent memory #${memory.id} → ${info.messageId}`);
  return info;
}

module.exports = {
  sendMemoryEmail,
  generateDeactivationToken,
  getBadgeColor
};
