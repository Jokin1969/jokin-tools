'use strict';

// ── Asignación — notification email (HTML with embedded QR + Data Matrix) ────────
// Builds a pretty digest of the people whose medication is released in Salud, with
// each person's TIS QR and the releasing boxes' Data Matrix embedded (inline, via
// Content-ID), plus deep links back into the app (one person / the whole group).

const nodemailer = require('nodemailer');
const qrcode = require('qrcode');
const bwipjs = require('bwip-js');
const release = require('./release');

function smtpConfigured() { return !!(process.env.SMTP_USER && process.env.SMTP_PASS); }
function createTransporter() {
  const user = process.env.SMTP_USER, pass = process.env.SMTP_PASS;
  if (!user || !pass) throw new Error('SMTP no configurado (faltan SMTP_USER / SMTP_PASS).');
  return nodemailer.createTransport({
    host: process.env.SMTP_HOST || 'smtp.gmail.com',
    port: Number(process.env.SMTP_PORT) || 587,
    secure: process.env.SMTP_SECURE === 'true',
    auth: { user, pass },
  });
}
function getBaseUrl() { return (process.env.BASE_URL || 'http://localhost:3000').replace(/\/$/, ''); }
function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
const CLR = /^#[0-9a-fA-F]{6}$/;
function fmtDateEs(iso) { if (!iso) return ''; const d = new Date(iso + 'T00:00:00'); if (isNaN(d)) return iso; return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' }); }
function fmtTis(t) { return String(t || '').replace(/(\d{4})(\d{4})/, '$1 $2'); }
function parseRecipients(csv) {
  return String(csv || '').split(/[,;\n]+/).map(s => s.trim()).filter(s => /.@.+\..+/.test(s));
}
const TYPE_LABEL = { any: 'Al menos un medicamento', all: 'Toda la medicación' };
const CRIT_LABEL = { exact: 'novedades del día', lte: 'acumulado a la fecha' };

async function renderQrPng(tis, person) {
  const dark = CLR.test(person.qr_dark || '') ? person.qr_dark : '#0f172a';
  const light = CLR.test(person.qr_light || '') ? person.qr_light : '#ffffff';
  return qrcode.toBuffer(String(tis), { type: 'png', errorCorrectionLevel: 'M', margin: 1, width: 220, color: { dark, light } });
}
async function renderDmPng(raw, color) {
  return bwipjs.toBuffer({ bcid: 'datamatrix', text: String(raw || ''), scale: 3, padding: 2, barcolor: (CLR.test(color || '') ? color : '#0f172a').replace('#', '') }).catch(() => null);
}

// Build { subject, html, images:[{cid, buffer, filename}], count, people }.
async function buildParts(notif, refDate) {
  const dmVisual = require('../datamatrix/visual');
  const data = release.peopleForNotif({ ntype: notif.ntype, criterion: notif.criterion }, refDate);
  const base = getBaseUrl();
  const images = [];
  const ids = data.people.map(p => p.person.id);
  const groupLink = `${base}/asignacion?people=${ids.join(',')}`;

  // Pre-render all images (QR per person + DM per releasing box).
  const cards = [];
  for (const pp of data.people) {
    const p = pp.person;
    const qrCid = `qr-${p.id}`;
    try { images.push({ cid: qrCid, buffer: await renderQrPng(p.tis, p), filename: `qr-${p.tis}.png` }); } catch { /* skip */ }
    const meds = [];
    for (const b of pp.satisfying) {
      const it = b.item;
      const color = it ? dmVisual.resolveColor(it.gtin, it.color) : '#0f172a';
      const dmCid = `dm-${b.line_id}`;
      const png = it ? await renderDmPng(it.raw, color) : null;
      if (png) images.push({ cid: dmCid, buffer: png, filename: `dm-${b.line_id}.png` });
      meds.push({ it, color, dmCid: png ? dmCid : null, release_at: b.release_at, effective_at: b.effective_at, advance_days: b.advance_days });
    }
    cards.push({ p, pp, qrCid, meds, personLink: `${base}/asignacion?person=${p.id}` });
  }

  const typeLabel = TYPE_LABEL[notif.ntype] || notif.ntype;
  const critLabel = CRIT_LABEL[notif.criterion] || notif.criterion;
  const subject = `Asignación — ${data.people.length} persona(s) · ${typeLabel} (${fmtDateEs(refDate)})`;

  const cardHtml = cards.map(c => {
    const p = c.p;
    const groups = String(p.group_name || '').split('\n').map(s => s.trim()).filter(Boolean).join(' · ');
    const badge = c.pp.allOut
      ? `<span style="background:#e2f5ec;color:#128a5b;font-size:12px;font-weight:700;padding:3px 9px;border-radius:999px;">✓ toda la medicación</span>`
      : `<span style="background:#fff3d6;color:#8a5a00;font-size:12px;font-weight:700;padding:3px 9px;border-radius:999px;">${c.pp.satisfiedCount} de ${c.pp.total}</span>`;
    const medRows = c.meds.map(m => {
      const it = m.it || {};
      const dm = m.dmCid ? `<img src="cid:${m.dmCid}" width="66" height="66" alt="Data Matrix" style="display:block;border:1px solid #e6ebf1;border-radius:6px;">` : '';
      return `<tr>
        <td style="padding:6px 10px 6px 0;vertical-align:middle;">${dm}</td>
        <td style="padding:6px 0;vertical-align:middle;font-size:13px;color:#1a2332;">
          <b>${esc(it.nombre || 'Medicamento')}</b><br>
          <span style="color:#5c7086;font-size:12px;">${it.serial ? 'Nº ' + esc(it.serial) + ' · ' : ''}${it.caducidad ? 'Cad ' + esc(fmtDateEs(it.caducidad)) + ' · ' : ''}Disponible desde ${esc(fmtDateEs(m.effective_at || m.release_at))}${m.effective_at && m.effective_at !== m.release_at ? ' <span style="color:#93a1b3;">(oficial ' + esc(fmtDateEs(m.release_at)) + ')</span>' : ''}</span>
        </td></tr>`;
    }).join('');
    return `<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 14px;border:1px solid #e6ebf1;border-radius:12px;">
      <tr>
        <td width="150" style="padding:16px;text-align:center;vertical-align:top;background:#f7fafc;border-right:1px solid #eef2f6;border-radius:12px 0 0 12px;">
          <img src="cid:${c.qrCid}" width="120" height="120" alt="QR TIS" style="display:block;margin:0 auto 6px;">
          <div style="font-family:'Courier New',monospace;font-size:14px;font-weight:700;letter-spacing:.06em;color:#1273b8;">${esc(fmtTis(p.tis))}</div>
          <a href="${c.personLink}" style="display:inline-block;margin-top:10px;background:#1273b8;color:#fff;text-decoration:none;font-size:12px;font-weight:700;padding:8px 12px;border-radius:8px;">Abrir ficha →</a>
        </td>
        <td style="padding:16px;vertical-align:top;">
          <div style="font-size:16px;font-weight:800;color:#0f2233;">${esc(p.apellidos)}, ${esc(p.nombre)} ${badge}</div>
          <div style="font-size:12px;color:#5c7086;margin:3px 0 10px;">${p.pharmacy_no ? 'Farmacia ' + esc(p.pharmacy_no) : ''}${groups ? (p.pharmacy_no ? ' · ' : '') + esc(groups) : ''}</div>
          <table width="100%" cellpadding="0" cellspacing="0">${medRows}</table>
        </td>
      </tr>
    </table>`;
  }).join('');

  const empty = `<p style="font-size:14px;color:#5c7086;">Hoy no hay ninguna persona que cumpla el criterio.</p>`;
  const html = `<!DOCTYPE html><html lang="es"><body style="margin:0;background:#eef3f8;font-family:'Segoe UI',Arial,sans-serif;padding:28px 14px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
      <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#fff;border:1px solid #dbe4ee;border-radius:14px;overflow:hidden;">
        <tr><td style="background:linear-gradient(135deg,#12224b 0%,#0f2233 100%);padding:26px 32px;">
          <p style="margin:0;font-family:'Courier New',monospace;font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:#8fb3d8;">Jokin's Tools · Asignación de medicación</p>
          <h1 style="margin:8px 0 0;font-size:21px;color:#eaf2ff;">🔔 ${esc(typeLabel)}</h1>
          <p style="margin:6px 0 0;font-size:13px;color:#b9cbe6;">${esc(fmtDateEs(refDate))} · ${esc(critLabel)} · <b>${data.people.length}</b> persona(s)</p>
        </td></tr>
        <tr><td style="padding:24px 28px;color:#1a2332;">
          ${data.people.length ? `<p style="margin:0 0 16px;text-align:center;"><a href="${groupLink}" style="display:inline-block;background:#0a9d8e;color:#fff;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:9px;">Ver estas ${data.people.length} personas en la app →</a></p>${cardHtml}` : empty}
        </td></tr>
        <tr><td style="padding:16px 28px;background:#f7fafc;border-top:1px solid #e6ebf1;text-align:center;">
          <p style="margin:0;font-size:12px;color:#8a97a8;">El QR abre el TIS para la app de Salud. Los Data Matrix identifican cada caja. Enviado por <b style="color:#1273b8;">Jokin's Tools</b>.</p>
        </td></tr>
      </table>
    </td></tr></table></body></html>`;

  return { subject, html, images, count: data.people.length, people: data.people };
}

// Send the notification email now (for a reference date). Returns a summary.
async function sendNotif(notif, refDate, opts = {}) {
  const recipients = parseRecipients(notif.recipients);
  if (!recipients.length) throw new Error('La notificación no tiene destinatarios válidos.');
  const parts = await buildParts(notif, refDate);
  if (!parts.count && !opts.force) return { sent: false, skipped: true, count: 0, recipients };
  if (!smtpConfigured()) throw new Error('SMTP no configurado (SMTP_USER / SMTP_PASS).');
  const transporter = createTransporter();
  await transporter.sendMail({
    from: process.env.EMAIL_FROM || `"Jokin's Tools" <${process.env.SMTP_USER}>`,
    to: recipients.join(', '),
    subject: parts.subject,
    html: parts.html,
    attachments: parts.images.map(im => ({ filename: im.filename, content: im.buffer, cid: im.cid, contentDisposition: 'inline' })),
  });
  return { sent: true, count: parts.count, recipients };
}

// HTML preview (images inlined as data URIs so it renders outside an email client).
async function previewHtml(notif, refDate) {
  const parts = await buildParts(notif, refDate);
  let html = parts.html;
  for (const im of parts.images) html = html.split(`cid:${im.cid}`).join(`data:image/png;base64,${im.buffer.toString('base64')}`);
  return { html, count: parts.count, subject: parts.subject };
}

module.exports = { smtpConfigured, sendNotif, previewHtml, parseRecipients, buildParts };
