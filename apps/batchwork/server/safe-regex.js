// Run a user-supplied regex against a list of filenames WITHOUT risking a ReDoS
// that blocks the whole server.
//
// The pattern comes from the client (normalize-dni's `pattern` param), so a
// catastrophic-backtracking expression could pin the single Node event loop and
// hang every other user. We run the matching inside a worker thread with a hard
// timeout: if the worker overruns it is terminated and the caller gets an error,
// while the main event loop stays responsive.

const { Worker } = require('worker_threads');
const path = require('path');

const PATTERN_MAX_LEN = parseInt(process.env.BATCHWORK_REGEX_MAX_LEN) || 200;
const MATCH_TIMEOUT_MS = parseInt(process.env.BATCHWORK_REGEX_TIMEOUT_MS) || 2000;

// Worker body: compile the pattern once, then for each filename try to match the
// base name (no extension) and fall back to the full name. Posts back the same
// { withId, noId } shape the operation expects.
const WORKER_SRC = `
const { parentPort, workerData } = require('worker_threads');
const path = require('path');
try {
  const re = new RegExp(workerData.pattern);
  const withId = [];
  const noId = [];
  for (const file of workerData.files) {
    const nameNoExt = path.parse(file).name;
    const match = re.exec(nameNoExt) || re.exec(file);
    if (match) withId.push({ file, id: match[0] });
    else noId.push(file);
  }
  parentPort.postMessage({ ok: true, withId, noId });
} catch (e) {
  parentPort.postMessage({ ok: false, error: e.message });
}
`;

// Returns a Promise resolving to { withId, noId }. Rejects on invalid pattern,
// oversize pattern, or timeout (likely ReDoS).
function matchFilenames(pattern, files) {
  if (typeof pattern !== 'string' || pattern.length > PATTERN_MAX_LEN) {
    return Promise.reject(Object.assign(
      new Error(`Patrón demasiado largo (máx. ${PATTERN_MAX_LEN} caracteres).`), { status: 400 }));
  }

  return new Promise((resolve, reject) => {
    const worker = new Worker(WORKER_SRC, { eval: true, workerData: { pattern, files } });
    let settled = false;
    const finish = (fn, arg) => { if (!settled) { settled = true; clearTimeout(timer); worker.terminate(); fn(arg); } };

    const timer = setTimeout(() => {
      finish(reject, Object.assign(
        new Error('El patrón tardó demasiado en evaluarse y fue cancelado (posible expresión peligrosa).'), { status: 400 }));
    }, MATCH_TIMEOUT_MS);

    worker.on('message', (msg) => {
      if (msg.ok) finish(resolve, { withId: msg.withId, noId: msg.noId });
      else finish(reject, Object.assign(new Error(`Expresión regular inválida: ${pattern}`), { status: 400 }));
    });
    worker.on('error', (err) => finish(reject, err));
    worker.on('exit', (code) => { if (code !== 0) finish(reject, new Error('El evaluador de patrones terminó inesperadamente.')); });
  });
}

module.exports = { matchFilenames, PATTERN_MAX_LEN, MATCH_TIMEOUT_MS };
