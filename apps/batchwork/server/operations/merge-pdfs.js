const { spawnPython } = require('../spawn-python');
const { createZip } = require('../utils');
const path = require('path');
const fs = require('fs');

async function run(session, params) {
  const outputName = (params.outputName || 'unificado.pdf').replace(/[^a-zA-Z0-9._\-ñÑáéíóúÁÉÍÓÚüÜ ]/g, '_');
  const outFile = path.join(session.outputDir, outputName.endsWith('.pdf') ? outputName : outputName + '.pdf');

  await spawnPython('merge_pdfs.py', [
    '--input', session.inputDir,
    '--output', outFile,
  ], session);

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);

  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'pdfs_unidos.zip';
  session.status = 'done';
}

module.exports = { run };
