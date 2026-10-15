const nodemailer = require('nodemailer');

function smtpConfigured() {
  return !!(process.env.SMTP_USER && process.env.SMTP_PASS);
}

function createTransporter() {
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;
  if (!user || !pass) throw new Error('SMTP no configurado');

  return nodemailer.createTransport({
    host: process.env.SMTP_HOST || 'smtp.gmail.com',
    port: Number(process.env.SMTP_PORT) || 587,
    secure: process.env.SMTP_SECURE === 'true',
    auth: { user, pass },
  });
}

function getBaseUrl() {
  return (process.env.BASE_URL || 'http://localhost:3000').replace(/\/$/, '');
}

async function enviarNotificacionFirma(reivindicacion, firma, email) {
  if (!smtpConfigured()) return; // Silent: no email configured

  try {
    const transporter = createTransporter();
    const fechaHumana = new Date(firma.creado_en).toLocaleDateString('es-ES', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

    const html = `
      <html lang="es">
      <head>
        <meta charset="UTF-8">
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; color: #333; }
          .container { max-width: 600px; margin: 0 auto; padding: 20px; }
          .header { background: #1B6CB0; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
          .header h1 { margin: 0; font-size: 24px; }
          .content { background: #f9f9f9; padding: 20px; border-radius: 8px; border-left: 4px solid #1B6CB0; }
          .firma-info { background: white; padding: 15px; border-radius: 4px; margin: 15px 0; border: 1px solid #ddd; }
          .label { font-weight: 600; color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 4px; }
          .value { font-size: 16px; color: #333; }
          .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
          .stat { text-align: center; padding: 15px; background: white; border-radius: 4px; }
          .stat-num { font-size: 28px; font-weight: 700; color: #1B6CB0; }
          .stat-label { font-size: 12px; color: #666; margin-top: 5px; }
          .footer { text-align: center; margin-top: 20px; color: #999; font-size: 12px; }
          a { color: #1B6CB0; text-decoration: none; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>✓ Nueva firma recibida</h1>
          </div>

          <div class="content">
            <div class="firma-info">
              <div class="label">Reivindicación</div>
              <div class="value">${escapeHtml(reivindicacion.titulo)}</div>
            </div>

            <div class="firma-info">
              <div class="label">Firmante</div>
              <div class="value">${escapeHtml(firma.nombre)}</div>
              <div style="font-size:12px;color:#999;margin-top:4px;">DNI: ${escapeHtml(firma.dni)}</div>
            </div>

            <div class="firma-info">
              <div class="label">Fecha y hora</div>
              <div class="value">${fechaHumana}</div>
            </div>

            <div class="stats">
              <div class="stat">
                <div class="stat-num">${reivindicacion.contador_firmas || 0}</div>
                <div class="stat-label">Firmas totales</div>
              </div>
              ${reivindicacion.objetivo_firmas ? `
                <div class="stat">
                  <div class="stat-num">${Math.round((reivindicacion.contador_firmas / reivindicacion.objetivo_firmas) * 100)}%</div>
                  <div class="stat-label">Progreso</div>
                </div>
              ` : ''}
            </div>

            <div style="margin-top:20px; text-align:center;">
              <a href="${getBaseUrl()}/reivindicaciones" style="display:inline-block; background:#1B6CB0; color:white; padding:10px 20px; border-radius:4px;">Ver reivindicación</a>
            </div>
          </div>

          <div class="footer">
            <p>Esta es una notificación automática de ${getBaseUrl().split('//')[1] || 'Jokin\'s Tools'}</p>
          </div>
        </div>
      </body>
      </html>
    `;

    await transporter.sendMail({
      from: process.env.SMTP_USER,
      to: email,
      subject: `Nueva firma: ${reivindicacion.titulo}`,
      html,
    });
  } catch (err) {
    console.error('[reivindicaciones:email] Error enviando notificación:', err.message);
  }
}

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return String(text || '').replace(/[&<>"']/g, m => map[m]);
}

module.exports = {
  smtpConfigured,
  enviarNotificacionFirma,
};
