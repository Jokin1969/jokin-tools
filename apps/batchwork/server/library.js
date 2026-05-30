// Persistent .dna document repository.
//
// Stores SnapGene .dna files on a directory that is meant to live on a mounted
// volume so it survives deployments (the session /tmp area does NOT). Point the
// env var BATCHWORK_LIBRARY_DIR at that volume; the default below assumes a
// volume mounted at /data.
//
// The repository is PER USER: each owner's documents live in their own
// subdirectory (LIBRARY_DIR/<ownerId>/) and every function requires the owner
// id, so one user can never list/read/overwrite/delete another user's files.

const fs = require('fs');
const path = require('path');

const LIBRARY_DIR = process.env.BATCHWORK_LIBRARY_DIR
  || path.join(process.env.BATCHWORK_DATA_DIR || '/data/batchwork', 'dna-library');

// Guard rails against filling the volume (applied per user).
const MAX_FILE_BYTES = (parseInt(process.env.BATCHWORK_LIBRARY_MAX_FILE_MB) || 50) * 1024 * 1024;
const MAX_TOTAL_BYTES = (parseInt(process.env.BATCHWORK_LIBRARY_MAX_TOTAL_MB) || 1024) * 1024 * 1024;
const MAX_FILES = parseInt(process.env.BATCHWORK_LIBRARY_MAX_FILES) || 1000;

// Per-user directory. ownerId comes from req.user.id (an integer); coerce to a
// safe basename so it can never escape LIBRARY_DIR.
function userDir(ownerId) {
  const safe = path.basename(String(ownerId));
  if (!safe || safe === '.' || safe === '..') throw new Error('Usuario no válido.');
  return path.join(LIBRARY_DIR, safe);
}

function ensureDir(ownerId) {
  const dir = userDir(ownerId);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

// Turn an arbitrary display name into a safe .dna filename used both on disk and
// as the canonical key shown to the user.
function safeName(name) {
  let base = path.basename(String(name || '').trim());
  base = base.replace(/\.dna$/i, '');
  base = base.replace(/[^\p{L}\p{N}.\- ()\[\]]+/gu, '_').replace(/_{2,}/g, '_').replace(/^[_.\s]+|[_.\s]+$/g, '');
  if (!base) base = 'documento';
  if (base.length > 120) base = base.slice(0, 120);
  return base + '.dna';
}

// Resolve a name to an absolute path that is guaranteed to stay inside the
// owner's library dir (path-traversal guard).
function resolveInside(ownerId, name) {
  const dir = userDir(ownerId);
  const file = safeName(name);
  const full = path.resolve(dir, file);
  if (path.dirname(full) !== path.resolve(dir)) {
    throw new Error('Nombre de documento no válido.');
  }
  return { file, full };
}

// Light sanity check that the bytes look like a SnapGene .dna (cookie packet:
// type 9, then ASCII "SnapGene").
function looksLikeDna(buf) {
  if (!buf || buf.length < 14) return false;
  if (buf[0] !== 0x09) return false;
  return buf.slice(5, 13).toString('latin1') === 'SnapGene';
}

function list(ownerId) {
  const dir = ensureDir(ownerId);
  const out = [];
  for (const f of fs.readdirSync(dir)) {
    if (!f.toLowerCase().endsWith('.dna')) continue;
    try {
      const st = fs.statSync(path.join(dir, f));
      if (st.isFile()) out.push({ name: f, size: st.size, savedAt: st.mtimeMs });
    } catch { /* skip unreadable */ }
  }
  out.sort((a, b) => b.savedAt - a.savedAt);
  return out;
}

function stats(ownerId) {
  return list(ownerId).reduce((acc, d) => ({ count: acc.count + 1, bytes: acc.bytes + d.size }), { count: 0, bytes: 0 });
}

function save(ownerId, name, buf) {
  ensureDir(ownerId);
  if (!Buffer.isBuffer(buf) || buf.length === 0) throw Object.assign(new Error('Documento vacío.'), { status: 400 });
  if (buf.length > MAX_FILE_BYTES) {
    throw Object.assign(new Error(`El documento supera el límite de ${Math.round(MAX_FILE_BYTES / 1024 / 1024)} MB.`), { status: 413 });
  }
  if (!looksLikeDna(buf)) throw Object.assign(new Error('El fichero no parece un .dna de SnapGene.'), { status: 400 });

  const { file, full } = resolveInside(ownerId, name);
  const existed = fs.existsSync(full);
  if (!existed) {
    const s = stats(ownerId);
    if (s.count >= MAX_FILES) throw Object.assign(new Error('El repositorio ha alcanzado el número máximo de documentos.'), { status: 507 });
    if (s.bytes + buf.length > MAX_TOTAL_BYTES) throw Object.assign(new Error('El repositorio ha alcanzado su capacidad máxima.'), { status: 507 });
  }
  fs.writeFileSync(full, buf);
  const st = fs.statSync(full);
  return { name: file, size: st.size, savedAt: st.mtimeMs, replaced: existed };
}

function read(ownerId, name) {
  ensureDir(ownerId);
  const { file, full } = resolveInside(ownerId, name);
  if (!fs.existsSync(full)) throw Object.assign(new Error('Documento no encontrado.'), { status: 404 });
  return { name: file, buffer: fs.readFileSync(full) };
}

function remove(ownerId, name) {
  ensureDir(ownerId);
  const { full } = resolveInside(ownerId, name);
  if (!fs.existsSync(full)) throw Object.assign(new Error('Documento no encontrado.'), { status: 404 });
  fs.unlinkSync(full);
}

// One-off migration: move pre-existing flat .dna files (saved before the
// per-user split, when they lived directly in LIBRARY_DIR) into the given
// owner's subdirectory. Returns the number moved.
function migrateFlatFiles(ownerId) {
  if (!ownerId || !fs.existsSync(LIBRARY_DIR)) return 0;
  const dest = ensureDir(ownerId);
  let moved = 0;
  for (const f of fs.readdirSync(LIBRARY_DIR)) {
    if (!f.toLowerCase().endsWith('.dna')) continue;
    const from = path.join(LIBRARY_DIR, f);
    try {
      if (!fs.statSync(from).isFile()) continue;
      const to = path.join(dest, f);
      if (!fs.existsSync(to)) { fs.renameSync(from, to); moved++; }
    } catch { /* skip */ }
  }
  if (moved) console.log(`[batchwork] Migrated ${moved} flat library file(s) to owner ${ownerId}`);
  return moved;
}

module.exports = { LIBRARY_DIR, list, stats, save, read, remove, safeName, migrateFlatFiles };
