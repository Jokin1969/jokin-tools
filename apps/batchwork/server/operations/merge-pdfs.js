const { spawnPython } = require('../spawn-python');
const path = require('path');
const fs = require('fs');

async function run(session, params) {
  const outputName = (params.outputName || 'unificado.pdf').replace(/[^a-zA-Z0-9._\-ñÑáéíóúÁÉÍÓÚüÜ ]/g, '_');
  const outFile = path.join(session.outputDir, outputName.endsWith('.pdf') ? outputName : outputName + '.pdf');
  const resolution = parseInt(params.resolution, 10) || 150;

  await spawnPython('merge_documents.py', [
    '--input', session.inputDir,
    '--output', outFile,
    '--resolution', String(resolution),
  ], session);

  if (!fs.existsSync(outFile)) {
    throw new Error('No se pudo generar el PDF unificado (revisa que los ficheros sean PDF, Office o imágenes admitidas).');
  }

  session.resultFile = outFile;
  session.resultMime = 'application/pdf';
  session.resultFilename = path.basename(outFile);
  session.status = 'done';
}

module.exports = { run };
