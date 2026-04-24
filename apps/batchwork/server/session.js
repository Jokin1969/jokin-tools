const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const TMP_DIR = process.env.BATCHWORK_TMP_DIR || '/tmp/batchwork';
const SESSION_TTL_MS = (parseInt(process.env.BATCHWORK_SESSION_TTL_MIN) || 30) * 60 * 1000;

const sessions = new Map();

// Purge expired sessions every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [id, session] of sessions) {
    if (now - session.createdAt > SESSION_TTL_MS) cleanup(id);
  }
}, 5 * 60 * 1000).unref();

function createSession() {
  const id = crypto.randomUUID();
  const inputDir = path.join(TMP_DIR, id, 'input');
  const outputDir = path.join(TMP_DIR, id, 'output');
  fs.mkdirSync(inputDir, { recursive: true });
  fs.mkdirSync(outputDir, { recursive: true });

  const session = {
    id,
    status: 'idle',
    operation: null,
    params: null,
    inputDir,
    outputDir,
    progress: { current: 0, total: 0, message: '' },
    log: [],
    awaitingData: null,
    resolveDecision: null,
    resultFile: null,
    resultMime: null,
    resultFilename: null,
    createdAt: Date.now(),
    _timer: null,
  };

  session._timer = setTimeout(() => cleanup(id), SESSION_TTL_MS);
  sessions.set(id, session);
  return session;
}

function getSession(id) {
  const session = sessions.get(id);
  if (!session) return null;
  if (Date.now() - session.createdAt > SESSION_TTL_MS) {
    cleanup(id);
    return null;
  }
  return session;
}

function cleanup(id) {
  const session = sessions.get(id);
  if (!session) return;
  clearTimeout(session._timer);
  const sessionDir = path.join(TMP_DIR, id);
  fs.rm(sessionDir, { recursive: true, force: true }, () => {});
  sessions.delete(id);
}

function waitForResolution(session, awaitingData) {
  session.status = 'awaiting_user';
  session.awaitingData = awaitingData;
  return new Promise(resolve => {
    session.resolveDecision = resolve;
  });
}

function resolveSession(session, decision) {
  if (session.resolveDecision && session.status === 'awaiting_user') {
    const resolve = session.resolveDecision;
    session.resolveDecision = null;
    session.awaitingData = null;
    session.status = 'running';
    resolve(decision);
  }
}

module.exports = { createSession, getSession, cleanup, waitForResolution, resolveSession };
