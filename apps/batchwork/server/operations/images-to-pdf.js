const { spawnPython } = require('../spawn-python');
const { createZip } = require('../utils');
const path = require('path');
const fs = require('fs');

async function run(session, params) {
  const resolution = parseInt(params.resolution, 10) || 150;
  const mode = params.mode === 'merged' ? 'merged' : 'independent';
  const mergedName = (params.mergedName || 'imagenes.pdf').trim() || 'imagenes.pdf';

  await spawnPython('images_to_pdf.py', [
    '--input', session.inputDir,
    '--output', session.outputDir,
    '--resolution', String(resolution),
    '--mode', mode,
    '--merged-name', mergedName,
  ], session);

  if (mode === 'merged') {
    const finalName = mergedName.toLowerCase().endsWith('.pdf') ? mergedName : `${mergedName}.pdf`;
    const pdfPath = path.join(session.outputDir, finalName);
    if (!fs.existsSync(pdfPath)) {
      throw new Error('No se generó el PDF unificado');
    }
    session.resultFile = pdfPath;
    session.resultMime = 'application/pdf';
    session.resultFilename = finalName;
  } else {
    const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
    await createZip(session.outputDir, zipPath);
    session.resultFile = zipPath;
    session.resultMime = 'application/zip';
    session.resultFilename = 'pdfs_desde_imagenes.zip';
  }
  session.status = 'done';
}

module.exports = { run };
