const { spawn } = require('child_process');
const path = require('path');

const PYTHON_DIR = path.join(__dirname, '../python');
const PYTHON_BIN = process.env.PYTHON_BIN || 'python3';

function spawnPython(script, args, session) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(PYTHON_DIR, script);
    const proc = spawn(PYTHON_BIN, [scriptPath, ...args]);

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

module.exports = { spawnPython };
