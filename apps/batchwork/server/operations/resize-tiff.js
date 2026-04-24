const { spawnPython } = require('../spawn-python');
const { createZip } = require('../utils');
const path = require('path');

async function run(session, params) {
  const maxMB = parseFloat(params.maxMB ?? 12);

  await spawnPython('resize_tiff.py', [
    '--input', session.inputDir,
    '--output', session.outputDir,
    '--max-mb', String(maxMB),
  ], session);

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);

  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'tiff_300dpi.zip';
  session.status = 'done';
}

module.exports = { run };
