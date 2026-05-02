const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const sessionModule = require('./session');
const { resolveSession } = require('./session');

const router = express.Router();
const PUBLIC_DIR = path.join(__dirname, '../public');
const MAX_MB = parseInt(process.env.BATCHWORK_MAX_UPLOAD_MB) || 500;

// ── Static public assets ──────────────────────────────────────────────────────
router.use('/public', express.static(PUBLIC_DIR));

// Favicon shortcuts
router.get('/favicon.ico', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'favicon.svg'), { headers: { 'Content-Type': 'image/svg+xml' } },
    err => { if (err) res.status(204).end(); });
});
router.get('/favicon.png', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'favicon.svg'), { headers: { 'Content-Type': 'image/svg+xml' } },
    err => { if (err) res.status(204).end(); });
});

// ── SPA entry point ───────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'index.html'));
});
router.get('/styles.css', (req, res) => res.sendFile(path.join(PUBLIC_DIR, 'styles.css')));
router.get('/app.js', (req, res) => res.sendFile(path.join(PUBLIC_DIR, 'app.js')));
router.get('/favicon.svg', (req, res) => res.sendFile(path.join(PUBLIC_DIR, 'favicon.svg')));

// ── Multer setup ──────────────────────────────────────────────────────────────
function makeUpload() {
  return multer({
    storage: multer.diskStorage({
      destination: (req, file, cb) => {
        const session = sessionModule.getSession(req.params.id);
        if (!session) return cb(new Error('Session not found'));
        cb(null, session.inputDir);
      },
      filename: (req, file, cb) => {
        const decoded = Buffer.from(file.originalname, 'latin1').toString('utf8');
        cb(null, decoded);
      },
    }),
    limits: { fileSize: MAX_MB * 1024 * 1024 },
  });
}

// ── API: Diagnostic (Python env) ──────────────────────────────────────────────
router.get('/api/diag', (req, res) => {
  const { spawnSync } = require('child_process');
  const REPO_ROOT = path.resolve(__dirname, '../../..');
  const VENV_PY = path.join(REPO_ROOT, '.venv', 'bin', 'python');
  const PYTHON_LIBS = path.join(REPO_ROOT, 'python_libs');
  const PYTHON_BIN = process.env.PYTHON_BIN
    || (fs.existsSync(VENV_PY) ? VENV_PY : 'python3');

  const env = { ...process.env };
  if (fs.existsSync(PYTHON_LIBS)) {
    const existing = env.PYTHONPATH ? env.PYTHONPATH.split(':').filter(Boolean) : [];
    if (!existing.includes(PYTHON_LIBS)) existing.unshift(PYTHON_LIBS);
    env.PYTHONPATH = existing.join(':');
  }

  const out = {
    repoRoot: REPO_ROOT,
    cwd: process.cwd(),
    venvExists: fs.existsSync(VENV_PY),
    pythonLibsExists: fs.existsSync(PYTHON_LIBS),
    pythonBin: PYTHON_BIN,
    pythonpath: env.PYTHONPATH || null,
    envPythonBin: process.env.PYTHON_BIN || null,
  };
  try {
    out.appDirListing = fs.readdirSync(REPO_ROOT).slice(0, 50);
  } catch (e) {
    out.appDirListingError = e.message;
  }
  if (fs.existsSync(PYTHON_LIBS)) {
    try {
      out.pythonLibsListing = fs.readdirSync(PYTHON_LIBS).slice(0, 50);
    } catch (e) {
      out.pythonLibsListingError = e.message;
    }
  }
  try {
    const v = spawnSync(PYTHON_BIN, ['--version'], { encoding: 'utf8', env });
    out.pythonVersion = (v.stdout || v.stderr || '').trim();
  } catch (e) {
    out.pythonVersionError = e.message;
  }
  try {
    const r = spawnSync(PYTHON_BIN, ['-c',
      'import sys; print("EXE:", sys.executable);\n'
      + 'print("PATH:", sys.path);\n'
      + 'for m in ("PIL","pypdf","svglib","reportlab","pdf2docx"):\n'
      + '    try:\n'
      + '        mod = __import__(m); print(m, getattr(mod, "__version__", "ok"))\n'
      + '    except Exception as e:\n'
      + '        print(m, "FAIL:", e)\n'
    ], { encoding: 'utf8', env });
    out.pythonExitCode = r.status;
    out.pythonStdout = (r.stdout || '').slice(0, 1500);
    out.pythonStderr = (r.stderr || '').slice(0, 800);
  } catch (e) {
    out.pythonRunError = e.message;
  }
  res.json(out);
});

// ── API: Create session ───────────────────────────────────────────────────────
router.post('/api/session', (req, res) => {
  const session = sessionModule.createSession();
  res.json({ id: session.id });
});

// ── API: Upload files ─────────────────────────────────────────────────────────
router.post('/api/session/:id/upload', (req, res, next) => {
  const session = sessionModule.getSession(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });

  makeUpload().fields([
    { name: 'files', maxCount: 10000 },
    { name: 'nameList', maxCount: 1 },
  ])(req, res, (err) => {
    if (err instanceof multer.MulterError && err.code === 'LIMIT_FILE_SIZE') {
      return res.status(413).json({ error: `Fichero demasiado grande. Límite: ${MAX_MB} MB por fichero.` });
    }
    if (err) return next(err);

    // Rename nameList to canonical name so operations can find it
    if (req.files?.nameList?.[0]) {
      const nl = req.files.nameList[0];
      const canonical = path.join(session.inputDir, '_namelist_.txt');
      try {
        fs.renameSync(nl.path, canonical);
      } catch (e) {
        // already at destination
      }
    }

    const uploaded = (req.files?.files || []).map(f => ({ name: f.originalname, size: f.size }));
    res.json({ uploaded });
  });
});

// ── API: Execute operation ────────────────────────────────────────────────────
router.post('/api/session/:id/execute', express.json(), async (req, res) => {
  const session = sessionModule.getSession(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  if (session.status === 'running') return res.status(409).json({ error: 'Already running' });

  const { operation, params = {} } = req.body;
  if (!operation) return res.status(400).json({ error: 'operation is required' });

  session.operation = operation;
  session.params = params;
  session.status = 'running';
  session.log = [];
  session.progress = { current: 0, total: 0, message: 'Iniciando...' };

  const OPERATIONS = {
    'inventory': () => require('./operations/inventory'),
    'rename': () => require('./operations/rename-from-list'),
    'transparent-png': () => require('./operations/transparent-png'),
    'resize-tiff': () => require('./operations/resize-tiff'),
    'docx-to-pdf': () => require('./operations/docx-to-pdf'),
    'images-to-pdf': () => require('./operations/images-to-pdf'),
    'pdf-to-docx': () => require('./operations/pdf-to-docx'),
    'normalize-dni': () => require('./operations/normalize-dni'),
    'merge-pdfs': () => require('./operations/merge-pdfs'),
    'split-pdfs': () => require('./operations/split-pdfs'),
  };

  const opFactory = OPERATIONS[operation];
  if (!opFactory) {
    session.status = 'error';
    return res.status(400).json({ error: `Unknown operation: ${operation}` });
  }

  // Run asynchronously
  opFactory().run(session, params).catch(err => {
    console.error(`[batchwork] operation ${operation} error:`, err.message);
    session.status = 'error';
    session.log.push({ type: 'error', file: '', message: err.message });
  });

  res.json({ status: 'running' });
});

// ── API: Status ───────────────────────────────────────────────────────────────
router.get('/api/session/:id/status', (req, res) => {
  const session = sessionModule.getSession(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });

  res.json({
    status: session.status,
    progress: session.progress,
    log: session.log,
    awaitingData: session.awaitingData,
    resultFilename: session.resultFilename,
  });
});

// ── API: Resolve awaiting_user ────────────────────────────────────────────────
router.post('/api/session/:id/resolve', express.json(), (req, res) => {
  const session = sessionModule.getSession(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  if (session.status !== 'awaiting_user') {
    return res.status(409).json({ error: 'Session is not awaiting user input' });
  }

  resolveSession(session, req.body);
  res.json({ ok: true });
});

// ── API: Download result ──────────────────────────────────────────────────────
router.get('/api/session/:id/download', (req, res) => {
  const session = sessionModule.getSession(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  if (session.status !== 'done') return res.status(409).json({ error: 'Result not ready' });
  if (!session.resultFile || !fs.existsSync(session.resultFile)) {
    return res.status(404).json({ error: 'Result file not found' });
  }

  res.setHeader('Content-Type', session.resultMime || 'application/octet-stream');
  res.setHeader('Content-Disposition', `attachment; filename="${session.resultFilename || 'result'}"`);
  res.sendFile(session.resultFile, (err) => {
    if (!err) {
      // Clean up session after successful download
      setTimeout(() => sessionModule.cleanup(session.id), 5000);
    }
  });
});

// ── API: Delete session ───────────────────────────────────────────────────────
router.delete('/api/session/:id', (req, res) => {
  const session = sessionModule.getSession(req.params.id);
  if (session) sessionModule.cleanup(session.id);
  res.json({ ok: true });
});

module.exports = router;
