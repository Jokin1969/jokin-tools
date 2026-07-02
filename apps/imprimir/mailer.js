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

// Acknowledgement to the sender: their email arrived and is queued to print.
async function sendReceived(to, subject, jobs) {
  const list = jobs.map(j => `• ${j.filename}`).join('\n');
  const text =
    `Hemos recibido tu correo${subject ? ` «${subject}»` : ''} y lo hemos puesto en cola de impresión:\n\n` +
    `${list}\n\n` +
    `Recibirás otro aviso cuando termine de imprimirse.\n` +
    `— Servicio de impresión de Jokin's Tools`;
  const n = jobs.length;
  return send(to, `📥 Recibido: ${n} documento${n !== 1 ? 's' : ''} en cola de impresión`, text);
}

// Notice to an allowed sender whose email carried nothing printable.
async function sendNothing(to, subject, oversized) {
  const over = (oversized && oversized.length)
    ? `\nSe ignoró ${oversized.length} adjunto(s) por superar el tamaño máximo permitido.`
    : '';
  const text =
    `Recibimos tu correo${subject ? ` «${subject}»` : ''} pero no encontramos ningún documento imprimible.\n` +
    `Adjunta un PDF, una imagen (JPG/PNG) o un Word (DOCX) y vuelve a enviarlo.${over}\n\n` +
    `— Servicio de impresión de Jokin's Tools`;
  return send(to, 'ℹ️ No se encontró ningún documento que imprimir', text);
}

// Notice when an attachment could not be converted to PDF (e.g. a corrupt DOCX).
async function sendConversionFailed(to, failures) {
  const list = failures.map(f => `• ${f.filename}: ${f.error}`).join('\n');
  const text =
    `No pudimos preparar para impresión ${failures.length} adjunto(s):\n\n` +
    `${list}\n\n` +
    `Comprueba que el archivo no esté dañado y vuelve a enviarlo.\n` +
    `— Servicio de impresión de Jokin's Tools`;
  return send(to, '⚠️ No se pudo preparar algún documento para imprimir', text);
}

module.exports = { send, sendPrinted, sendFailed, sendReceived, sendNothing, sendConversionFailed, transporter };
