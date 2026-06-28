const fs = require('fs');
const path = require('path');
const { createZip } = require('../utils');

// Remove one layer of surrounding quotes (straight, typographic or angular), so
// the user can wrap names that contain spaces in quotes — or not; both work.
function stripQuotes(s) {
  s = s.trim();
  const quotes = [['"', '"'], ["'", "'"], ['“', '”'], ['‘', '’'], ['«', '»']];
  for (const [a, b] of quotes) {
    if (s.length >= 2 && s[0] === a && s[s.length - 1] === b) return s.slice(1, -1).trim();
  }
  return s;
}

// Split one line of the pairs list into [oldName, newName]. The separator is
// auto-detected per line, in priority order: TAB, arrow (-> => →), ';', ','.
// Surrounding quotes around each side are optional and stripped.
function splitPair(line) {
  const seps = ['\t', '->', '=>', '→', ';', ','];
  for (const sep of seps) {
    const i = line.indexOf(sep);
    if (i !== -1) {
      return [stripQuotes(line.slice(0, i)), stripQuotes(line.slice(i + sep.length))];
    }
  }
  return null;
}

async function run(session) {
  const allFiles = fs.readdirSync(session.inputDir)
    .filter(f => fs.statSync(path.join(session.inputDir, f)).isFile());

  // The pairs list is uploaded through the same channel as the name list.
  const listFile = allFiles.find(f => f === '_namelist_.txt');
  if (!listFile) throw new Error('No se recibió el listado de parejas.');

  const files = allFiles
    .filter(f => f !== '_namelist_.txt')
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));
  if (files.length === 0) throw new Error('No se han subido ficheros para renombrar');

  // Build a case-insensitive map from the left (current) name → right (new) name,
  // both kept verbatim (no extension stripping, so dotted names like
  // "plasmido.v2" survive intact).
  const raw = fs.readFileSync(path.join(session.inputDir, listFile), 'utf8');
  const map = new Map();
  let badLines = 0;
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const pair = splitPair(trimmed);
    if (!pair || !pair[0] || !pair[1]) { badLines++; continue; }
    map.set(pair[0].toLowerCase(), pair[1]);
  }
  if (map.size === 0) {
    throw new Error('El listado de parejas está vacío o no tiene un separador válido (tabulador, ->, ; o ,).');
  }
  if (badLines > 0) {
    session.log.push({ type: 'warn', file: '', message: `${badLines} línea(s) del listado ignoradas por no tener pareja válida.` });
  }

  session.progress = { current: 0, total: files.length, message: 'Renombrando por parejas...' };

  const usedOut = new Set();   // lowercased output names, to avoid collisions
  const skipped = [];
  let matched = 0;

  for (let i = 0; i < files.length; i++) {
    const srcFile = files[i];
    const ext = path.extname(srcFile);
    const stem = ext ? srcFile.slice(0, -ext.length) : srcFile;
    // Match the list entry against the name WITHOUT extension first (the normal
    // case), and fall back to the full filename (tolerates entries that include
    // the extension).
    const newVal = map.get(stem.toLowerCase()) ?? map.get(srcFile.toLowerCase());

    session.progress = { current: i + 1, total: files.length, message: srcFile };

    if (newVal === undefined) { skipped.push(srcFile); continue; }  // no pair → omit

    // Always keep the file's ORIGINAL extension; append it unless the new name
    // already ends with it (so 'plasmido'→'plasmido.dna', and 'x.dna' stays 'x.dna').
    let newName = (ext && !newVal.toLowerCase().endsWith(ext.toLowerCase())) ? newVal + ext : newVal;
    let n = 2;
    while (usedOut.has(newName.toLowerCase())) {
      const e2 = path.extname(newName);
      const b2 = e2 ? newName.slice(0, -e2.length) : newName;
      newName = `${b2} (${n++})${e2}`;
    }
    usedOut.add(newName.toLowerCase());

    try {
      fs.copyFileSync(path.join(session.inputDir, srcFile), path.join(session.outputDir, newName));
      matched++;
      session.log.push({ type: 'info', file: srcFile, message: `→ ${newName}` });
    } catch (e) {
      session.log.push({ type: 'error', file: srcFile, message: e.message });
    }
  }

  if (matched === 0) {
    throw new Error('Ningún fichero de la carpeta coincidió con el listado de parejas.');
  }
  if (skipped.length > 0) {
    session.log.push({ type: 'warn', file: '', message: `${skipped.length} fichero(s) sin pareja (omitidos): ${skipped.slice(0, 20).join(', ')}${skipped.length > 20 ? '…' : ''}` });
  }
  session.log.push({ type: 'info', file: '', message: `${matched} fichero(s) renombrado(s).` });

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);

  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'renombrados.zip';
  session.status = 'done';
}

module.exports = { run };
