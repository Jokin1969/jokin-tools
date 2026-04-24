const { spawnPython } = require('../spawn-python');
const { createZip } = require('../utils');
const path = require('path');

async function run(session, params) {
  const threshold = parseInt(params.threshold ?? 60);

  await spawnPython('transparent_png.py', [
    '--input', session.inputDir,
    '--output', session.outputDir,
    '--threshold', String(threshold),
  ], session);

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);

  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'transparentes.zip';
  session.status = 'done';
}

module.exports = { run };
