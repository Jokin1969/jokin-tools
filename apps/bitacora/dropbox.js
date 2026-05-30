const fetch = require('node-fetch');
const { getAccessToken } = require('../re-memory/dropbox');
const { getAllForExport } = require('./db');

const DROPBOX_UPLOAD_URL = 'https://content.dropboxapi.com/2/files/upload';

// ─── CSV builder ─────────────────────────────────────────────────────────────
function buildCSV(rows) {
  const headers = [
    'id', 'fecha', 'lugar', 'hecho', 'nivel', 'categoria',
    'como', 'factores', 'notado_otros', 'notado_quien', 'comentario', 'created_at',
  ];
  const escape = (val) => {
    if (val === null || val === undefined) return '';
    const str = String(val);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };
  const lines = [headers.join(',')];
  for (const row of rows) lines.push(headers.map(h => escape(row[h])).join(','));
  return lines.join('\n');
}

function generateFilename() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const date = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}-${pad(now.getMinutes())}`;
  return `bitacora-export-${date}_${time}.csv`;
}

// ─── Upload to Dropbox ───────────────────────────────────────────────────────
async function exportToDropbox(userId) {
  const rows = getAllForExport(userId);
  const csvContent = buildCSV(rows);
  const filename = generateFilename();

  const folder = (process.env.DROPBOX_BITACORA_FOLDER || '/JokinTools/Bitacora/exports').replace(/\/$/, '');
  const dropboxPath = `${folder}/${filename}`;
  const accessToken = await getAccessToken();

  const response = await fetch(DROPBOX_UPLOAD_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/octet-stream',
      'Dropbox-API-Arg': JSON.stringify({ path: dropboxPath, mode: 'add', autorename: true, mute: false }),
    },
    body: Buffer.from(csvContent, 'utf-8'),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Dropbox upload failed: ${err}`);
  }

  const result = await response.json();
  console.log(`[bitacora] Uploaded ${rows.length} rows to ${result.path_display}`);
  return { path: result.path_display, filename, rows: rows.length, size: Buffer.byteLength(csvContent, 'utf-8') };
}

module.exports = { exportToDropbox, buildCSV };
