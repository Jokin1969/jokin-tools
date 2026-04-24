const fs = require('fs');
const path = require('path');
const { waitForResolution } = require('../session');
const { spawnPython } = require('../spawn-python');
const { createZip } = require('../utils');

async function run(session, params) {
  const pattern = params.pattern || '\\d{8}[A-Za-z]';
  let regex;
  try {
    regex = new RegExp(pattern);
  } catch (e) {
    throw new Error(`Expresión regular inválida: ${pattern}`);
  }

  const allFiles = fs.readdirSync(session.inputDir).filter(f => {
    return fs.statSync(path.join(session.inputDir, f)).isFile();
  });

  // Extract ID from each filename
  const withId = [];
  const noId = [];

  for (const file of allFiles) {
    const nameNoExt = path.parse(file).name;
    const match = regex.exec(nameNoExt) || regex.exec(file);
    if (match) {
      withId.push({ file, id: match[0] });
    } else {
      noId.push(file);
    }
  }

  // Group by ID to detect collisions
  const idMap = new Map();
  for (const entry of withId) {
    if (!idMap.has(entry.id)) idMap.set(entry.id, []);
    idMap.get(entry.id).push(entry.file);
  }

  const collisions = [...idMap.entries()].filter(([, files]) => files.length > 1);

  // Resolve collisions if any
  let resolvedEntries = []; // Array of {file, outputName}

  if (collisions.length > 0) {
    const decision = await waitForResolution(session, {
      type: 'collision',
      collisions: collisions.map(([id, files]) => ({ id, files })),
    });

    if (decision.action === 'cancel') {
      session.log.push({ type: 'info', file: '', message: 'Operación cancelada' });
      session.status = 'done';
      return;
    }

    for (const [id, files] of idMap) {
      if (files.length === 1) {
        resolvedEntries.push({ file: files[0], outputName: id + '.pdf' });
      } else {
        const sorted = [...files].sort((a, b) => a.localeCompare(b, 'es'));
        if (decision.action === 'first') {
          resolvedEntries.push({ file: sorted[0], outputName: id + '.pdf' });
        } else {
          // suffix
          for (let i = 0; i < sorted.length; i++) {
            resolvedEntries.push({
              file: sorted[i],
              outputName: i === 0 ? id + '.pdf' : `${id}_${i}.pdf`,
            });
          }
        }
      }
    }
  } else {
    for (const [id, files] of idMap) {
      resolvedEntries.push({ file: files[0], outputName: id + '.pdf' });
    }
  }

  const total = resolvedEntries.length;
  session.progress = { current: 0, total, message: 'Convirtiendo ficheros...' };

  let processed = 0;
  for (const { file, outputName } of resolvedEntries) {
    processed++;
    session.progress = { current: processed, total, message: `Procesando ${file}...` };
    const srcPath = path.join(session.inputDir, file);
    const dstPath = path.join(session.outputDir, outputName);
    const ext = path.extname(file).toLowerCase();

    try {
      if (ext === '.pdf') {
        fs.copyFileSync(srcPath, dstPath);
      } else {
        // Convert to PDF using Python (handles docx, images)
        await spawnPython('normalize_dni_convert.py', [
          '--input', srcPath,
          '--output', dstPath,
        ], session);
      }
    } catch (e) {
      session.log.push({ type: 'error', file, message: e.message });
    }
  }

  if (noId.length > 0) {
    const logContent = 'Ficheros sin identificador detectable:\n' + noId.join('\n');
    fs.writeFileSync(path.join(session.outputDir, 'sin_identificador.txt'), logContent, 'utf8');
    session.log.push({ type: 'warn', file: '', message: `${noId.length} fichero(s) sin ID detectado` });
  }

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);

  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'normalizacion_dni.zip';
  session.status = 'done';
}

module.exports = { run };
