const fs = require('fs');
const path = require('path');
const { waitForResolution } = require('../session');
const { createZip } = require('../utils');

async function run(session, params) {
  const { keepExtension = true } = params;

  const allFiles = fs.readdirSync(session.inputDir).filter(f => {
    const stat = fs.statSync(path.join(session.inputDir, f));
    return stat.isFile();
  });

  // The name-list file is uploaded as _namelist_.txt
  const namelistFile = allFiles.find(f => f === '_namelist_.txt');
  if (!namelistFile) throw new Error('No se encontró el fichero de lista de nombres (_namelist_.txt)');

  const files = allFiles.filter(f => f !== '_namelist_.txt').sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));
  const namesRaw = fs.readFileSync(path.join(session.inputDir, namelistFile), 'utf8');
  const names = namesRaw.split('\n').map(l => l.trim()).filter(l => l.length > 0);

  if (files.length === 0) throw new Error('No se han subido ficheros para renombrar');

  if (files.length !== names.length) {
    const decision = await waitForResolution(session, {
      type: 'mismatch',
      fileCount: files.length,
      nameCount: names.length,
      files,
      names,
    });

    if (decision === 'cancel') {
      session.log.push({ type: 'info', file: '', message: 'Operación cancelada por el usuario' });
      session.status = 'done';
      return;
    }
    // decision === 'partial': continue with min(files, names) pairs
  }

  const pairs = Math.min(files.length, names.length);
  session.progress = { current: 0, total: pairs, message: 'Renombrando ficheros...' };

  for (let i = 0; i < pairs; i++) {
    const srcFile = files[i];
    let newName = names[i];

    if (keepExtension) {
      const srcExt = path.extname(srcFile);
      const newNameExt = path.extname(newName);
      if (newNameExt) newName = newName.slice(0, -newNameExt.length);
      newName = newName + srcExt;
    }

    try {
      fs.copyFileSync(
        path.join(session.inputDir, srcFile),
        path.join(session.outputDir, newName)
      );
    } catch (e) {
      session.log.push({ type: 'error', file: srcFile, message: e.message });
    }
    session.progress = { current: i + 1, total: pairs, message: `${srcFile} → ${newName}` };
  }

  if (files.length !== names.length) {
    const skipped = files.length > names.length
      ? files.slice(names.length)
      : [];
    if (skipped.length > 0) {
      session.log.push({ type: 'warn', file: '', message: `${skipped.length} fichero(s) sin nombre asignado: ${skipped.join(', ')}` });
    }
  }

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);

  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'renombrados.zip';
  session.status = 'done';
}

module.exports = { run };
