// Persistent .dna document repository (SHARED across all batchwork users).
//
// Stores SnapGene .dna files on a directory meant to live on a mounted volume so
// it survives deployments (the session /tmp area does NOT). Point the env var
// BATCHWORK_LIBRARY_DIR at that volume; the default below assumes a volume
// mounted at /data.
//
// Access model (decided with the user): the library is a shared team resource.
// Anyone with batchwork access can list, download, ADD, OVERWRITE and DELETE
// documents — it's a lab working library. It is intentionally NOT per-user and
// destructive actions are NOT admin-gated. The only hard guard is against path
// traversal (a malicious name can't escape LIBRARY_DIR).

const fs = require('fs');
const path = require('path');

const LIBRARY_DIR = process.env.BATCHWORK_LIBRARY_DIR
  || path.join(process.env.BATCHWORK_DATA_DIR || '/data/batchwork', 'dna-library');

// Guard rails against filling the volume (whole shared library).
const MAX_FILE_BYTES = (parseInt(process.env.BATCHWORK_LIBRARY_MAX_FILE_MB) || 50) * 1024 * 1024;
const MAX_TOTAL_BYTES = (parseInt(process.env.BATCHWORK_LIBRARY_MAX_TOTAL_MB) || 1024) * 1024 * 1024;
const MAX_FILES = parseInt(process.env.BATCHWORK_LIBRARY_MAX_FILES) || 1000;

function ensureDir() {
  fs.mkdirSync(LIBRARY_DIR, { recursive: true });
  return LIBRARY_DIR;
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

// Resolve a name to an absolute path guaranteed to stay inside LIBRARY_DIR
// (path-traversal guard).
function resolveInside(name) {
  const file = safeName(name);
  const full = path.resolve(LIBRARY_DIR, file);
  if (path.dirname(full) !== path.resolve(LIBRARY_DIR)) {
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

function list() {
  ensureDir();
  const out = [];
  for (const f of fs.readdirSync(LIBRARY_DIR)) {
    if (!f.toLowerCase().endsWith('.dna')) continue;
    try {
      const st = fs.statSync(path.join(LIBRARY_DIR, f));
      if (st.isFile()) out.push({ name: f, size: st.size, savedAt: st.mtimeMs });
    } catch { /* skip unreadable */ }
  }
  out.sort((a, b) => b.savedAt - a.savedAt);
  return out;
}

function stats() {
  return list().reduce((acc, d) => ({ count: acc.count + 1, bytes: acc.bytes + d.size }), { count: 0, bytes: 0 });
}

// Add or overwrite a document. Overwriting an existing name is allowed for any
// user (shared lab library).
function save(name, buf) {
  ensureDir();
  if (!Buffer.isBuffer(buf) || buf.length === 0) throw Object.assign(new Error('Documento vacío.'), { status: 400 });
  if (buf.length > MAX_FILE_BYTES) {
    throw Object.assign(new Error(`El documento supera el límite de ${Math.round(MAX_FILE_BYTES / 1024 / 1024)} MB.`), { status: 413 });
  }
  if (!looksLikeDna(buf)) throw Object.assign(new Error('El fichero no parece un .dna de SnapGene.'), { status: 400 });

  const { file, full } = resolveInside(name);
  const existed = fs.existsSync(full);
  if (!existed) {
    const s = stats();
    if (s.count >= MAX_FILES) throw Object.assign(new Error('El repositorio ha alcanzado el número máximo de documentos.'), { status: 507 });
    if (s.bytes + buf.length > MAX_TOTAL_BYTES) throw Object.assign(new Error('El repositorio ha alcanzado su capacidad máxima.'), { status: 507 });
  }
  fs.writeFileSync(full, buf);
  const st = fs.statSync(full);
  return { name: file, size: st.size, savedAt: st.mtimeMs, replaced: existed };
}

function read(name) {
  ensureDir();
  const { file, full } = resolveInside(name);
  if (!fs.existsSync(full)) throw Object.assign(new Error('Documento no encontrado.'), { status: 404 });
  return { name: file, buffer: fs.readFileSync(full) };
}

function remove(name) {
  ensureDir();
  const { full } = resolveInside(name);
  if (!fs.existsSync(full)) throw Object.assign(new Error('Documento no encontrado.'), { status: 404 });
  fs.unlinkSync(full);
}

// One-off migration: an earlier version split the library per user into numeric
// subdirectories (LIBRARY_DIR/<userId>/). Now that the library is shared again,
// move those files back up to LIBRARY_DIR and remove the empty subdirs. On a
// name collision the existing shared file wins (the subdir copy is left in place
// so nothing is silently lost). Returns the number consolidated.
function consolidateToShared() {
  if (!fs.existsSync(LIBRARY_DIR)) return 0;
  let moved = 0;
  for (const entry of fs.readdirSync(LIBRARY_DIR, { withFileTypes: true })) {
    if (!entry.isDirectory() || !/^\d+$/.test(entry.name)) continue;
    const subdir = path.join(LIBRARY_DIR, entry.name);
    for (const f of fs.readdirSync(subdir)) {
      if (!f.toLowerCase().endsWith('.dna')) continue;
      const from = path.join(subdir, f);
      const to = path.join(LIBRARY_DIR, f);
      try {
        if (!fs.statSync(from).isFile()) continue;
        if (!fs.existsSync(to)) { fs.renameSync(from, to); moved++; }
      } catch { /* skip */ }
    }
    try { fs.rmdirSync(subdir); } catch { /* not empty (collisions) — leave it */ }
  }
  if (moved) console.log(`[batchwork] Consolidated ${moved} per-user library file(s) into the shared repository`);
  return moved;
}

module.exports = { LIBRARY_DIR, list, stats, save, read, remove, safeName, consolidateToShared };
