const fetch = require('node-fetch');
const { getAllMemoriesForExport } = require('./db');

const DROPBOX_TOKEN_URL = 'https://api.dropbox.com/oauth2/token';
const DROPBOX_UPLOAD_URL = 'https://content.dropboxapi.com/2/files/upload';

// ─── Get temporary access token from refresh token ───────────────────────────

async function getAccessToken() {
  const { DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN } = process.env;

  if (!DROPBOX_APP_KEY || !DROPBOX_APP_SECRET || !DROPBOX_REFRESH_TOKEN) {
    throw new Error('Dropbox credentials not configured. Check DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN');
  }

  const params = new URLSearchParams({
    grant_type: 'refresh_token',
    refresh_token: DROPBOX_REFRESH_TOKEN,
    client_id: DROPBOX_APP_KEY,
    client_secret: DROPBOX_APP_SECRET
  });

  const response = await fetch(DROPBOX_TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params.toString()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Dropbox token refresh failed: ${err}`);
  }

  const data = await response.json();
  return data.access_token;
}

// ─── CSV builder ─────────────────────────────────────────────────────────────

function buildCSV(rows) {
  const headers = [
    'id', 'description', 'created_at', 'times_recalled',
    'frequency', 'topic', 'has_image', 'source_url',
    'active', 'next_send_date', 'last_sent_date'
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
  for (const row of rows) {
    lines.push(headers.map(h => escape(row[h])).join(','));
  }
  return lines.join('\n');
}

// ─── Generate filename ────────────────────────────────────────────────────────

function generateFilename() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const date = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}-${pad(now.getMinutes())}`;
  return `re-memory-export-${date}_${time}.csv`;
}

// ─── Upload to Dropbox ────────────────────────────────────────────────────────

async function exportToDropbox() {
  const rows = getAllMemoriesForExport();
  const csvContent = buildCSV(rows);
  const filename = generateFilename();

  const folder = (process.env.DROPBOX_FOLDER || '/JokinTools/ReMemory/exports').replace(/\/$/, '');
  const dropboxPath = `${folder}/${filename}`;

  const accessToken = await getAccessToken();

  const response = await fetch(DROPBOX_UPLOAD_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/octet-stream',
      'Dropbox-API-Arg': JSON.stringify({
        path: dropboxPath,
        mode: 'add',
        autorename: true,
        mute: false
      })
    },
    body: Buffer.from(csvContent, 'utf-8')
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Dropbox upload failed: ${err}`);
  }

  const result = await response.json();
  console.log(`[dropbox] Uploaded ${rows.length} rows to ${result.path_display}`);

  return {
    path: result.path_display,
    filename,
    rows: rows.length,
    size: Buffer.byteLength(csvContent, 'utf-8')
  };
}

// ─── Dropbox OAuth2 helper (first-time setup) ─────────────────────────────────

function getAuthorizationUrl() {
  const { DROPBOX_APP_KEY } = process.env;
  if (!DROPBOX_APP_KEY) throw new Error('DROPBOX_APP_KEY not set');
  const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
  const redirectUri = encodeURIComponent(`${BASE_URL}/re-memory/auth/dropbox/callback`);
  return `https://www.dropbox.com/oauth2/authorize?client_id=${DROPBOX_APP_KEY}&response_type=code&token_access_type=offline&redirect_uri=${redirectUri}`;
}

async function exchangeCodeForTokens(code) {
  const { DROPBOX_APP_KEY, DROPBOX_APP_SECRET } = process.env;
  const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
  const redirectUri = `${BASE_URL}/re-memory/auth/dropbox/callback`;

  const params = new URLSearchParams({
    code,
    grant_type: 'authorization_code',
    redirect_uri: redirectUri
  });

  const credentials = Buffer.from(`${DROPBOX_APP_KEY}:${DROPBOX_APP_SECRET}`).toString('base64');

  const response = await fetch(DROPBOX_TOKEN_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Basic ${credentials}`,
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: params.toString()
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Token exchange failed: ${err}`);
  }

  return response.json();
}

module.exports = {
  exportToDropbox,
  getAuthorizationUrl,
  exchangeCodeForTokens,
  getAccessToken
};
