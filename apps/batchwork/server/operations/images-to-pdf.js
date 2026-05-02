const { spawnPython } = require('../spawn-python');
const { createZip } = require('../utils');
const path = require('path');

async function run(session, params) {
  const resolution = parseInt(params.resolution, 10) || 150;

  await spawnPython('images_to_pdf.py', [
    '--input', session.inputDir,
    '--output', session.outputDir,
    '--resolution', String(resolution),
  ], session);

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);

  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'pdfs_desde_imagenes.zip';
  session.status = 'done';
}

module.exports = { run };
