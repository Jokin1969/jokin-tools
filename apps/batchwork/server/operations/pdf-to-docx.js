const { spawnPython } = require('../spawn-python');
const { createZip } = require('../utils');
const path = require('path');

async function run(session, params) {
  await spawnPython('pdf_to_docx.py', [
    '--input', session.inputDir,
    '--output', session.outputDir,
  ], session);

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);

  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'docx_desde_pdf.zip';
  session.status = 'done';
}

module.exports = { run };
