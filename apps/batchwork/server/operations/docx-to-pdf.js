const { spawnPython } = require('../spawn-python');
const { createZip } = require('../utils');
const path = require('path');

async function run(session, params) {
  await spawnPython('docx_to_pdf.py', [
    '--input', session.inputDir,
    '--output', session.outputDir,
  ], session);

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);

  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'pdfs_desde_docx.zip';
  session.status = 'done';
}

module.exports = { run };
