const fetch = require('node-fetch');
const fs = require('fs');
const path = require('path');

const { getAccessToken } = require('./dropbox');
const { db } = require('./db');

const DROPBOX_UPLOAD_URL   = 'https://content.dropboxapi.com/2/files/upload';
const DROPBOX_LIST_URL     = 'https://api.dropbox.com/2/files/list_folder';
const DROPBOX_DOWNLOAD_URL = 'https://content.dropboxapi.com/2/files/download';
const DROPBOX_DELETE_URL   = 'https://api.dropbox.com/2/files/delete_v2';

function getBackupFolder() {
  return (process.env.DROPBOX_BACKUP_FOLDER || '/JokinTools/ReMemory/backups').replace(/\/$/, '');
}

function getMaxCount() {
  return Math.max(1, parseInt(process.env.BACKUP_MAX_COUNT || '100', 10));
}

// ─── Change detection: track DB mtime after each backup ──────────────────────
let lastBackupMtime = null;

function hasDbChangedSinceLastBackup() {
  const dbPath = process.env.DB_PATH || '/data/jokin_tools.db';
  if (!fs.existsSync(dbPath)) return false;
  if (lastBackupMtime === null) return true;
  return fs.statSync(dbPath).mtimeMs > lastBackupMtime;
}

function generateBackupFilename() {
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const d = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const t = `${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}`;
  return `re-memory-backup-${d}_${t}.db`;
}

// ─── Create backup ────────────────────────────────────────────────────────────

async function createBackup() {
  const dbPath = process.env.DB_PATH || '/data/jokin_tools.db';
  const tempPath = path.join(path.dirname(dbPath), `_bkp_temp_${Date.now()}.db`);

  // SQLite hot backup (non-blocking)
  await db.backup(tempPath);
  const fileContent = fs.readFileSync(tempPath);
  fs.unlinkSync(tempPath);

  const filename     = generateBackupFilename();
  const folder       = getBackupFolder();
  const dropboxPath  = `${folder}/${filename}`;
  const accessToken  = await getAccessToken();

  const response = await fetch(DROPBOX_UPLOAD_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/octet-stream',
      'Dropbox-API-Arg': JSON.stringify({
        path: dropboxPath,
        mode: 'add',
        autorename: false,
        mute: true
      })
    },
    body: fileContent
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Dropbox upload failed: ${err}`);
  }

  const result = await response.json();

  // Mark DB mtime so we know when to backup next
  lastBackupMtime = fs.existsSync(dbPath) ? fs.statSync(dbPath).mtimeMs : Date.now();

  // Prune old backups asynchronously (non-blocking)
  enforceMaxCount(accessToken).catch(err =>
    console.error('[backup] enforceMaxCount error:', err.message)
  );

  const sizeKB = (fileContent.length / 1024).toFixed(1);
  console.log(`[backup] ✓ Created: ${filename} (${sizeKB} KB)`);

  return {
    filename,
    path: result.path_display,
    size: fileContent.length,
    created_at: new Date().toISOString()
  };
}

// ─── List backups ─────────────────────────────────────────────────────────────

async function listBackups() {
  const accessToken = await getAccessToken();
  const folder      = getBackupFolder();

  const response = await fetch(DROPBOX_LIST_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ path: folder, limit: 300 })
  });

  if (!response.ok) {
    const errText = await response.text();
    if (errText.includes('not_found') || errText.includes('path/not_found')) return [];
    throw new Error(`Dropbox list failed: ${errText}`);
  }

  const data = await response.json();
  return (data.entries || [])
    .filter(e => e['.tag'] === 'file' && e.name.endsWith('.db'))
    .sort((a, b) => new Date(b.client_modified) - new Date(a.client_modified))
    .map(f => ({
      filename:   f.name,
      path:       f.path_display,
      size:       f.size,
      created_at: f.client_modified
    }));
}

// ─── Restore backup ───────────────────────────────────────────────────────────

async function restoreBackup(filename) {
  const dbPath      = process.env.DB_PATH || '/data/jokin_tools.db';
  const folder      = getBackupFolder();
  const dropboxPath = `${folder}/${filename}`;
  const accessToken = await getAccessToken();

  const response = await fetch(DROPBOX_DOWNLOAD_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Dropbox-API-Arg': JSON.stringify({ path: dropboxPath })
    }
  });

  if (!response.ok) {
    throw new Error(`Dropbox download failed: ${await response.text()}`);
  }

  const buffer   = await response.buffer();
  const tempPath = path.join(path.dirname(dbPath), `_restore_temp_${Date.now()}.db`);
  fs.writeFileSync(tempPath, buffer);

  try {
    // ATTACH backup and atomically replace all data in live connection
    const safePath = tempPath.replace(/'/g, "''");
    db.exec(`ATTACH DATABASE '${safePath}' AS restore_src`);

    db.transaction(() => {
      db.exec('DELETE FROM recall_log');
      db.exec('DELETE FROM memories');
      db.exec('INSERT INTO memories  SELECT * FROM restore_src.memories');
      db.exec('INSERT INTO recall_log SELECT * FROM restore_src.recall_log');

      // Sync AUTOINCREMENT sequences
      db.exec(`UPDATE sqlite_sequence
               SET seq = (SELECT COALESCE(MAX(id),0) FROM memories)
               WHERE name = 'memories'`);
      db.exec(`UPDATE sqlite_sequence
               SET seq = (SELECT COALESCE(MAX(id),0) FROM recall_log)
               WHERE name = 'recall_log'`);
    })();

    db.exec('DETACH DATABASE restore_src');

    // Reset mtime tracker so auto-backup doesn't immediately re-backup
    lastBackupMtime = fs.existsSync(dbPath) ? fs.statSync(dbPath).mtimeMs : Date.now();

    console.log(`[backup] ✓ Restored from: ${filename} (${(buffer.length / 1024).toFixed(1)} KB)`);
  } finally {
    if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
  }

  return {
    filename,
    size: buffer.length,
    restored_at: new Date().toISOString()
  };
}

// ─── Enforce max backup count (delete oldest) ─────────────────────────────────

async function enforceMaxCount(accessToken) {
  const maxCount = getMaxCount();
  const folder   = getBackupFolder();

  const response = await fetch(DROPBOX_LIST_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ path: folder, limit: 500 })
  });

  if (!response.ok) return;

  const data  = await response.json();
  const files = (data.entries || [])
    .filter(e => e['.tag'] === 'file' && e.name.endsWith('.db'))
    .sort((a, b) => new Date(a.client_modified) - new Date(b.client_modified)); // oldest first

  if (files.length <= maxCount) return;

  const toDelete = files.slice(0, files.length - maxCount);
  for (const file of toDelete) {
    try {
      await fetch(DROPBOX_DELETE_URL, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ path: file.path_display })
      });
      console.log(`[backup] Pruned old backup: ${file.name}`);
    } catch (err) {
      console.error(`[backup] Failed to prune ${file.name}:`, err.message);
    }
  }
}

module.exports = { createBackup, listBackups, restoreBackup, hasDbChangedSinceLastBackup };
