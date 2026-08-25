const path = require('path');
const fs = require('fs');
const { spawnPython } = require('../spawn-python');
const { createZip } = require('../utils');

// Extensiones que aceptamos como FASTA de 3'UTR.
const FASTA_EXT = new Set(['.fa', '.fasta', '.fna', '.seq', '.txt']);

// El nombre de la especie sale del nombre del fichero: así no hay que adivinar
// cuál es el modelo y cuál la diana, y cada salida se llama como su fichero.
function speciesName(filename) {
  const stem = path.basename(filename, path.extname(filename));
  const clean = stem.replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^[_.]+|[_.]+$/g, '');
  return clean || 'especie';
}

function numeric(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

async function run(session, params) {
  const files = fs.readdirSync(session.inputDir)
    .filter(f => FASTA_EXT.has(path.extname(f).toLowerCase()))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));

  if (files.length === 0) {
    throw new Error('No hay ningún FASTA en la subida (.fa, .fasta, .fna, .seq o .txt).');
  }
  if (files.length > 2) {
    throw new Error(
      `Se han subido ${files.length} FASTA y esta operación admite uno o dos ` +
      `(una especie, o dos para comparar sus 3'UTR). Quita los que sobren.`
    );
  }

  const names = files.map(speciesName);
  if (names.length === 2 && names[0] === names[1]) {
    throw new Error(
      `Los dos ficheros dan el mismo nombre de especie ("${names[0]}"); ` +
      `renombra uno para no mezclar sus salidas.`
    );
  }

  const args = [
    '--fasta', path.join(session.inputDir, files[0]),
    '--name', names[0],
    '--out', session.outputDir,
    '--candidates',      String(numeric(params.candidates, 6)),
    '--min-spacing',     String(numeric(params.minSpacing, 50)),
    '--min-block',       String(numeric(params.minBlock, 15)),
    '--gc-min',          String(numeric(params.gcMin, 0.30)),
    '--gc-max',          String(numeric(params.gcMax, 0.52)),
    '--max-homopolymer', String(numeric(params.maxHomopolymer, 3)),
    '--min-asymmetry',   String(numeric(params.minAsymmetry, 0.5)),
    '--polya-flank',     String(numeric(params.polyaFlank, 10)),
  ];

  const cdsInicio = Number(params.cdsInicio);
  const cdsFin = Number(params.cdsFin);
  if (Number.isFinite(cdsInicio) && Number.isFinite(cdsFin) && cdsInicio > 0 && cdsFin > 0) {
    args.push('--cds', String(cdsInicio), String(cdsFin));
    if (files.length === 2) args.push('--cds-b', String(cdsInicio), String(cdsFin));
  } else if (params.cdsInicio || params.cdsFin) {
    throw new Error(
      'El CDS necesita inicio Y fin, los dos. Déjalos vacíos si la secuencia ya es el 3′UTR.'
    );
  }

  if (files.length === 2) {
    args.push('--fasta-b', path.join(session.inputDir, files[1]), '--name-b', names[1]);
  } else {
    session.log.push({
      type: 'warn',
      file: files[0],
      message: 'Solo un FASTA: no hay bloques conservados que buscar. Sube dos para compararlos.',
    });
  }

  if (params.bootstrapSeeds === true || params.bootstrapSeeds === 'true') {
    args.push('--bootstrap-seeds');
    session.log.push({
      type: 'warn',
      file: '',
      message: 'Filtro de seed con la lista de arranque de 12 miRNAs: sirve para probar '
             + 'la mecánica, NO para cribar candidatos (hace falta mature.fa de miRBase).',
    });
  }

  await spawnPython('shmir_design_run.py', args, session);

  const escritos = fs.readdirSync(session.outputDir);
  if (escritos.length === 0) {
    throw new Error('El diseño no generó ningún fichero; revisa el log.');
  }

  session.log.push({
    type: 'warn',
    file: '',
    message: 'Los candidatos salen como INCOMPLETE mientras haya filtros en NOT_RUN '
           + '(miRBase, gnomAD, BLAST, rmsk). El informe dice cuáles y por qué.',
  });

  const zipPath = path.join(path.dirname(session.outputDir), 'result.zip');
  await createZip(session.outputDir, zipPath);
  session.resultFile = zipPath;
  session.resultMime = 'application/zip';
  session.resultFilename = 'shmir-design.zip';
  session.status = 'done';
}

module.exports = { run };
