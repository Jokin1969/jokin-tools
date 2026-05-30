const fetch = require('node-fetch');
const fs = require('fs');
const path = require('path');

const { getAccessToken } = require('./dropbox');
const { db, assignOrphansToConfiguredOwner } = require('./db');

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

  // Copy a table using only the columns present in BOTH schemas. This makes the
  // restore resilient to schema drift — e.g. a backup taken before the
  // memories.user_id migration simply leaves user_id NULL instead of failing or
  // (worse) shifting data into the wrong columns with INSERT ... SELECT *.
  const copyTable = (table) => {
    const live = db.prepare(`PRAGMA table_info(${table})`).all().map(c => c.name);
    const src  = db.prepare(`PRAGMA restore_src.table_info(${table})`).all().map(c => c.name);
    const cols = live.filter(c => src.includes(c));
    if (!cols.length) throw new Error(`Backup incompatible: la tabla ${table} no tiene columnas en común`);
    const colList = cols.map(c => `"${c}"`).join(', ');
    db.exec(`INSERT INTO ${table} (${colList}) SELECT ${colList} FROM restore_src.${table}`);
  };

  // Whether the backup we're restoring from contains a given table (older
  // backups predate some apps, e.g. bitacora).
  const srcHasTable = (table) =>
    !!db.prepare(`SELECT name FROM restore_src.sqlite_master WHERE type='table' AND name=?`).get(table);

  let attached = false;
  try {
    // ATTACH backup and atomically replace memories/recall_log in the live
    // connection (users/auth_sessions are intentionally left untouched).
    const safePath = tempPath.replace(/'/g, "''");
    db.exec(`ATTACH DATABASE '${safePath}' AS restore_src`);
    attached = true;

    const restoreBitacora = srcHasTable('bitacora');

    db.transaction(() => {
      db.exec('DELETE FROM recall_log');
      db.exec('DELETE FROM memories');
      copyTable('memories');
      copyTable('recall_log');

      // A restored owner id that doesn't exist in the live users table (older or
      // foreign backup) would hide those rows forever — treat them as ownerless
      // so they can be reassigned below.
      db.exec('UPDATE memories SET user_id = NULL WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)');

      // Bitácora (only if the backup contains it).
      if (restoreBitacora) {
        db.exec('DELETE FROM bitacora');
        copyTable('bitacora');
        db.exec('UPDATE bitacora SET user_id = NULL WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)');
      }

      // Sync AUTOINCREMENT sequences
      db.exec(`UPDATE sqlite_sequence
               SET seq = (SELECT COALESCE(MAX(id),0) FROM memories)
               WHERE name = 'memories'`);
      db.exec(`UPDATE sqlite_sequence
               SET seq = (SELECT COALESCE(MAX(id),0) FROM recall_log)
               WHERE name = 'recall_log'`);
      if (restoreBitacora) {
        db.exec(`UPDATE sqlite_sequence
                 SET seq = (SELECT COALESCE(MAX(id),0) FROM bitacora)
                 WHERE name = 'bitacora'`);
      }
    })();

    // Reattach orphaned/unknown-owner rows to the configured owner so restored
    // data stays visible (mirrors the boot-time orphan assignment).
    const reassigned = assignOrphansToConfiguredOwner();
    if (reassigned) console.log(`[backup] Reassigned ${reassigned} restored memories to the configured owner`);
    try {
      const nb = require('../bitacora/db').assignOrphansToConfiguredOwner();
      if (nb) console.log(`[backup] Reassigned ${nb} restored bitácora entries to the configured owner`);
    } catch (e) { console.error('[backup] bitacora reassign skipped:', e.message); }

    // Reset mtime tracker so auto-backup doesn't immediately re-backup
    lastBackupMtime = fs.existsSync(dbPath) ? fs.statSync(dbPath).mtimeMs : Date.now();

    console.log(`[backup] ✓ Restored from: ${filename} (${(buffer.length / 1024).toFixed(1)} KB)`);
  } finally {
    // Always detach, even if the transaction threw — otherwise the next restore
    // hits "database restore_src is already in use" until the process restarts.
    if (attached) {
      try { db.exec('DETACH DATABASE restore_src'); }
      catch (e) { console.error('[backup] detach failed:', e.message); }
    }
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
