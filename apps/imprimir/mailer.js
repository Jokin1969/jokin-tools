const nodemailer = require('nodemailer');

// Reuses the hub's SMTP configuration (same as Re-memory). Returns null if SMTP
// isn't configured, so callers can degrade gracefully (log instead of throw).
function transporter() {
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;
  if (!user || !pass) return null;
  return nodemailer.createTransport({
    host: process.env.SMTP_HOST || 'smtp.gmail.com',
    port: Number(process.env.SMTP_PORT) || 587,
    secure: process.env.SMTP_SECURE === 'true',
    auth: { user, pass },
  });
}

function from() {
  return process.env.EMAIL_FROM || process.env.SMTP_USER || 'imprimir@localhost';
}

async function send(to, subject, text) {
  if (!to) return false;
  const t = transporter();
  if (!t) { console.warn('[imprimir] SMTP no configurado — no se envía aviso a', to); return false; }
  await t.sendMail({ from: from(), to, subject, text });
  return true;
}

// Print confirmation (success) back to the sender.
async function sendPrinted(job) {
  const subject = `✅ Impreso: ${job.filename}`;
  const text =
    `Tu documento se ha enviado correctamente a la impresora.\n\n` +
    `• Documento: ${job.filename}\n` +
    `• Impresora: ${job.printer || '(por defecto del agente)'}\n` +
    (job.subject ? `• Asunto original: ${job.subject}\n` : '') +
    `\n— Servicio de impresión de Jokin's Tools`;
  return send(job.sender, subject, text);
}

// Print failure back to the sender.
async function sendFailed(job, error) {
  const subject = `⚠️ No se pudo imprimir: ${job.filename}`;
  const text =
    `Ha habido un problema al imprimir tu documento.\n\n` +
    `• Documento: ${job.filename}\n` +
    `• Impresora: ${job.printer || '(por defecto del agente)'}\n` +
    `• Error: ${error || 'desconocido'}\n\n` +
    `Vuelve a intentarlo o revisa que el agente de impresión esté encendido.\n` +
    `— Servicio de impresión de Jokin's Tools`;
  return send(job.sender, subject, text);
}

// Notice to an allowed sender whose email carried no printable PDF.
async function sendNoPdf(to, subject, oversized) {
  const over = (oversized && oversized.length)
    ? `\nSe ignoró ${oversized.length} adjunto(s) por superar el tamaño máximo permitido.`
    : '';
  const text =
    `Recibimos tu correo${subject ? ` «${subject}»` : ''} pero no encontramos ningún PDF que imprimir.\n` +
    `Adjunta el documento en formato PDF y vuelve a enviarlo.${over}\n\n` +
    `— Servicio de impresión de Jokin's Tools`;
  return send(to, 'ℹ️ No se encontró ningún PDF que imprimir', text);
}

module.exports = { send, sendPrinted, sendFailed, sendNoPdf, transporter };
