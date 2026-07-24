const { spawn, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const PYTHON_DIR = path.join(__dirname, '../python');
const REPO_ROOT = path.resolve(__dirname, '../../..');
const VENV_PY = path.join(REPO_ROOT, '.venv', 'bin', 'python');
const PYTHON_LIBS = path.join(REPO_ROOT, 'python_libs');
const PYTHON_BIN = process.env.PYTHON_BIN
  || (fs.existsSync(VENV_PY) ? VENV_PY : 'python3');

// PYTHONPATH para encontrar deps instaladas con `pip --target=/app/python_libs`
function buildPythonEnv() {
  const env = { ...process.env };
  if (fs.existsSync(PYTHON_LIBS)) {
    const existing = env.PYTHONPATH ? env.PYTHONPATH.split(':').filter(Boolean) : [];
    if (!existing.includes(PYTHON_LIBS)) existing.unshift(PYTHON_LIBS);
    env.PYTHONPATH = existing.join(':');
  }
  return env;
}

// ── Startup diagnostic (visible en logs de Railway) ──────────────────────────
(function diag() {
  console.log('[batchwork] REPO_ROOT =', REPO_ROOT);
  console.log('[batchwork] .venv/bin/python exists =', fs.existsSync(VENV_PY));
  console.log('[batchwork] python_libs exists =', fs.existsSync(PYTHON_LIBS));
  console.log('[batchwork] PYTHON_BIN =', PYTHON_BIN);
  const env = buildPythonEnv();
  console.log('[batchwork] PYTHONPATH =', env.PYTHONPATH || '(unset)');
  try {
    const v = spawnSync(PYTHON_BIN, ['--version'], { encoding: 'utf8', env });
    console.log('[batchwork] python --version:', (v.stdout || v.stderr || '').trim());
    const pil = spawnSync(PYTHON_BIN, ['-c',
      'import PIL, pypdf, svglib, reportlab; print(PIL.__version__, pypdf.__version__)'
    ], { encoding: 'utf8', env });
    if (pil.status === 0) {
      console.log('[batchwork] Python deps OK:', pil.stdout.trim());
    } else {
      console.log('[batchwork] Python deps FAILED:', (pil.stderr || '').trim().slice(0, 400));
    }
  } catch (e) {
    console.log('[batchwork] diag error:', e.message);
  }
})();

function spawnPython(script, args, session) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(PYTHON_DIR, script);
    const proc = spawn(PYTHON_BIN, [scriptPath, ...args], { env: buildPythonEnv() });

    let stderr = '';

    proc.stdout.on('data', (data) => {
      for (const line of data.toString().split('\n').map(l => l.trim()).filter(Boolean)) {
        if (line.startsWith('PROGRESS:')) {
          const parts = line.split(':');
          const current = parseInt(parts[1]) || 0;
          const total = parseInt(parts[2]) || 0;
          const message = parts.slice(3).join(':');
          session.progress = { current, total, message };
        } else if (line.startsWith('ERROR:')) {
          const parts = line.split(':');
          const file = parts[1] || '';
          const message = parts.slice(2).join(':');
          session.log.push({ type: 'error', file, message });
        } else if (line.startsWith('WARN:')) {
          const parts = line.split(':');
          const file = parts[1] || '';
          const message = parts.slice(2).join(':');
          session.log.push({ type: 'warn', file, message });
        }
      }
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Python (${script}) exit ${code}: ${stderr.slice(0, 500)}`));
      } else {
        resolve();
      }
    });

    proc.on('error', (err) => reject(new Error(`Failed to start ${script}: ${err.message}`)));
  });
}

module.exports = { spawnPython, PYTHON_BIN, PYTHON_DIR, buildPythonEnv };
