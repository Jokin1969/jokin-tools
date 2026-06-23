const { spawnPython } = require('../spawn-python');
const { createZip } = require('../utils');
const { waitForResolution } = require('../session');
const path = require('path');
const fs = require('fs');

async function run(session, params) {
  const {
    splitMode = 'pages',
    expectedPages,
    blockSize = 4,
    pattern = '',
  } = params;

  const inputFiles = fs.readdirSync(session.inputDir)
    .filter(f => /\.pdf$/i.test(f))
    .sort((a, b) => a.localeCompare(b, 'es'));

  if (inputFiles.length === 0) throw new Error('No se encontraron ficheros PDF en el lote');

  // Validate page count if expectedPages is specified
  if (expectedPages && parseInt(expectedPages) > 0) {
    const expected = parseInt(expectedPages);
    const invalid = [];

    for (const f of inputFiles) {
      try {
        const count = await spawnPythonCount(path.join(session.inputDir, f));
        if (count !== expected) invalid.push({ file: f, pages: count });
      } catch (e) {
        session.log.push({ type: 'warn', file: f, message: 'No se pudo leer el número de páginas' });
      }
    }

    if (invalid.length > 0) {
      const decision = await waitForResolution(session, {
        type: 'page_mismatch',
        expected,
        invalid,
      });
      if (decision === 'cancel') {
        session.log.push({ type: 'info', file: '', message: 'Operación cancelada' });
        session.status = 'cancelled';
        return;
      }
      // decision === 'continue': skip invalid files
      const invalidNames = new Set(invalid.map(i => i.file));
      inputFiles.forEach((f, idx) => {
        if (invalidNames.has(f)) inputFiles.splice(idx, 1);
      });
    }
  }

  const resolvedBlockSize = (splitMode === 'blocksN') ? (parseInt(blockSize) || 4) : 2;

  // Custom pattern: a comma-separated list of block sizes, e.g. "3,2,2,1".
  // Each PDF is cut sequentially into those block sizes; any leftover pages
  // (when the pattern sums to fewer than the page count) go into a final block.
  let patternArg = '';
  if (splitMode === 'pattern') {
    const sizes = String(pattern)
      .split(/[\s,]+/)
      .map(s => parseInt(s, 10))
      .filter(nn => Number.isInteger(nn) && nn > 0 && nn <= 10000)
      .slice(0, 2000);
    if (sizes.length === 0) {
      throw new Error('Introduce un patrón de bloques válido, por ejemplo: 3,2,2,1');
    }
    patternArg = sizes.join(',');
  }

  const modeArg = splitMode === 'pattern' ? `pattern:${patternArg}`
    : splitMode === 'blocksN' ? `blocks:${resolvedBlockSize}`
    : splitMode === 'blocks2' ? 'blocks:2'
    : splitMode === 'blocks3' ? 'blocks:3'
    : splitMode;

  await spawnPython('split_pdfs.py', [
    '--input', session.inputDir,
    '--output', session.outputDir,
    '--mode', modeArg,
  ], session);

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);

  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'pdfs_divididos.zip';
  session.status = 'done';
}

// Count pages of a single PDF via Python
function spawnPythonCount(pdfPath) {
  const { spawn } = require('child_process');
  const PYTHON_BIN = process.env.PYTHON_BIN || 'python3';
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_BIN, ['-c',
      `from pypdf import PdfReader; r=PdfReader(r"${pdfPath}"); print(len(r.pages))`
    ]);
    let out = '';
    proc.stdout.on('data', d => { out += d.toString(); });
    proc.on('close', code => {
      if (code === 0) resolve(parseInt(out.trim()));
      else reject(new Error('pypdf error'));
    });
    proc.on('error', reject);
  });
}

module.exports = { run };
