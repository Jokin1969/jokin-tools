const express = require('express');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const router = express.Router();

const db = require('./db');
const mailer = require('./mailer');
const { config } = require('./config');
const { requireAdmin } = require('../auth/middleware');

// ─── API-key guard for the local print agent ────────────────────────────────────
// The agent is not a browser session; it authenticates with a shared secret
// (IMPRIMIR_AGENT_KEY). Constant-time compare avoids leaking the key by timing.
function timingEqual(a, b) {
  const ba = Buffer.from(String(a || ''));
  const bb = Buffer.from(String(b || ''));
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
}

function apiKeyGuard(req, res, next) {
  const cfg = config();
  if (!cfg.agentKey) return res.status(503).json({ error: 'Servicio de impresión no configurado (falta IMPRIMIR_AGENT_KEY).' });
  const provided = req.get('x-api-key') || (req.get('authorization') || '').replace(/^Bearer\s+/i, '');
  if (!timingEqual(provided, cfg.agentKey)) return res.status(401).json({ error: 'API key inválida.' });
  next();
}

// ─── Health / reachability (no key: lets the agent verify the URL) ──────────────
// Intentionally minimal — no queue counts here to avoid leaking activity to
// unauthenticated callers (use GET /api/jobs with the key for that).
router.get('/api/health', (req, res) => {
  res.json({ ok: true, enabled: config().enabled });
});

// ─── Agent: claim the next queued job (returns the PDF as base64) ───────────────
router.get('/api/jobs/next', apiKeyGuard, (req, res) => {
  const job = db.claimNextJob();
  if (!job) return res.json({ job: null });
  let pdf_base64;
  try {
    pdf_base64 = fs.readFileSync(job.file_path).toString('base64');
  } catch (e) {
    db.markFailed(job.id, 'PDF no disponible en el servidor: ' + e.message);
    return res.status(500).json({ error: 'El PDF del trabajo no está disponible.' });
  }
  res.json({
    job: {
      id: job.id,
      filename: job.filename,
      printer: job.printer,
      mime: job.mime,
      size_bytes: job.size_bytes,
      pdf_base64,
    },
  });
});

// ─── Agent: report a job printed OK ─────────────────────────────────────────────
router.post('/api/jobs/:id/done', apiKeyGuard, (req, res) => {
  const id = Number(req.params.id);
  const job = db.getJob(id);
  if (!job) return res.status(404).json({ error: 'Trabajo no encontrado.' });
  db.markDone(id);
  res.json({ ok: true });
  // Confirmation email is best-effort and must not block/So we fire-and-forget.
  mailer.sendPrinted(db.getJob(id)).catch(e => console.error('[imprimir] confirmación falló:', e.message));
});

// ─── Agent: report a job failed ─────────────────────────────────────────────────
router.post('/api/jobs/:id/failed', apiKeyGuard, (req, res) => {
  const id = Number(req.params.id);
  const job = db.getJob(id);
  if (!job) return res.status(404).json({ error: 'Trabajo no encontrado.' });
  const err = (req.body && req.body.error) ? String(req.body.error).slice(0, 500) : 'Error en el agente de impresión.';
  db.markFailed(id, err);
  res.json({ ok: true });
  mailer.sendFailed(db.getJob(id), err).catch(e => console.error('[imprimir] aviso de fallo falló:', e.message));
});

// ─── Debug/list (key-protected) ─────────────────────────────────────────────────
router.get('/api/jobs', apiKeyGuard, (req, res) => {
  res.json({ jobs: db.listJobs({ status: req.query.status, limit: req.query.limit }) });
});

// ─── Status page (admins only) ──────────────────────────────────────────────────
// A small dashboard to watch the queue and reprint finished jobs. Cookie-auth
// (admin), separate from the agent's API-key routes.
router.get('/status', requireAdmin, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'status.html'));
});

router.get('/api/status', requireAdmin, (req, res) => {
  res.json({
    enabled: config().enabled,
    printer: config().defaultPrinter || null,
    counts: db.counts(),
    jobs: db.listJobs({ limit: 50 }),
  });
});

// Reprint a finished job (re-queues it so the agent picks it up again).
router.post('/api/jobs/:id/reprint', requireAdmin, (req, res) => {
  const id = Number(req.params.id);
  const job = db.getJob(id);
  if (!job) return res.status(404).json({ error: 'Trabajo no encontrado.' });
  if (!job.file_path || !fs.existsSync(job.file_path)) {
    return res.status(410).json({ error: 'El PDF ya no está disponible (se limpió por antigüedad).' });
  }
  db.requeueJob(id);
  res.json({ ok: true });
});

module.exports = router;
