// ─── Auth mailer ────────────────────────────────────────────────────────────────
// Sends the password-reset email, reusing the hub's SMTP configuration
// (SMTP_HOST/PORT/SECURE/USER/PASS, EMAIL_FROM) — the same variables Re-memory uses.
const nodemailer = require('nodemailer');

function smtpConfigured() {
  return !!(process.env.SMTP_USER && process.env.SMTP_PASS);
}

function createTransporter() {
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;
  if (!user || !pass) throw new Error('SMTP no configurado (faltan SMTP_USER / SMTP_PASS).');
  return nodemailer.createTransport({
    host: process.env.SMTP_HOST || 'smtp.gmail.com',
    port: Number(process.env.SMTP_PORT) || 587,
    secure: process.env.SMTP_SECURE === 'true',
    auth: { user, pass },
  });
}

// Read BASE_URL fresh each call so a Railway change is picked up after redeploy.
function getBaseUrl() {
  const url = (process.env.BASE_URL || '').replace(/\/$/, '');
  if (!url || url.includes('localhost') || url.includes('127.0.0.1')) {
    console.warn('[auth] BASE_URL no definida o apunta a localhost: los enlaces de recuperación no funcionarán bien. '
      + 'Configura BASE_URL=https://tu-dominio en Railway.');
  }
  return url || 'http://localhost:3000';
}

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function sendResetEmail(user, token) {
  const link = `${getBaseUrl()}/auth/reset-password/${token}`;
  const transporter = createTransporter();
  const name = user.name ? esc(user.name) : '';

  const html = `<!DOCTYPE html><html lang="es"><body style="margin:0;background:#f0f0f0;font-family:'Segoe UI',Arial,sans-serif;padding:32px 16px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#fff;border:1px solid #d0d0d0;border-radius:12px;overflow:hidden;">
        <tr><td style="background:linear-gradient(135deg,#1a2332 0%,#0f1b2d 100%);padding:28px 36px;">
          <p style="margin:0;font-family:'Courier New',monospace;font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:#7d8590;">Jokin's Tools</p>
          <h1 style="margin:8px 0 0;font-size:21px;color:#e6edf3;">Restablecer contraseña</h1>
        </td></tr>
        <tr><td style="padding:32px 36px;color:#1a1a1a;font-size:15px;line-height:1.6;">
          <p style="margin:0 0 16px;">${name ? `Hola ${name},` : 'Hola,'}</p>
          <p style="margin:0 0 22px;">Hemos recibido una solicitud para restablecer la contraseña de tu cuenta. Pulsa el botón para elegir una nueva. El enlace caduca en <strong>1 hora</strong>.</p>
          <p style="margin:0 0 26px;text-align:center;">
            <a href="${link}" style="display:inline-block;background:#1B6CB0;color:#fff;text-decoration:none;font-weight:700;padding:13px 26px;border-radius:8px;">Cambiar mi contraseña</a>
          </p>
          <p style="margin:0 0 8px;font-size:13px;color:#666;">Si el botón no funciona, copia este enlace en tu navegador:</p>
          <p style="margin:0 0 22px;font-size:12px;color:#1B6CB0;word-break:break-all;">${esc(link)}</p>
          <p style="margin:0;font-size:13px;color:#888;">Si no has solicitado este cambio, puedes ignorar este correo: tu contraseña no cambiará.</p>
        </td></tr>
        <tr><td style="padding:18px 36px;background:#f7f7f7;border-top:1px solid #e0e0e0;text-align:center;">
          <p style="margin:0;font-size:12px;color:#888;">Enviado por <strong style="color:#1B6CB0;">Jokin's Tools</strong></p>
        </td></tr>
      </table>
    </td></tr></table></body></html>`;

  await transporter.sendMail({
    from: process.env.EMAIL_FROM || `"Jokin's Tools" <${process.env.SMTP_USER}>`,
    to: user.email,
    subject: 'Jokin\'s Tools — Restablecer tu contraseña',
    html,
  });
}

module.exports = { smtpConfigured, sendResetEmail };
