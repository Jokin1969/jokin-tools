const express = require('express');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const multer = require('multer');
const router = express.Router();

const db = require('./db');
const mailer = require('./mailer');
const { config, maskedConfig, readiness } = require('./config');
const { state, recordAgentPull } = require('./state');
const { requireAdmin } = require('../auth/middleware');

// In-memory upload for the submit API (files go straight into the queue).
const submitUpload = multer({ storage: multer.memoryStorage(), limits: { fileSize: config().maxBytes } });

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

// Guard for the submit API — other apps authenticate with the submit key
// (falls back to the agent key if a dedicated submit key isn't set).
function submitKeyGuard(req, res, next) {
  const cfg = config();
  const key = cfg.submitKey || cfg.agentKey;
  if (!key) return res.status(503).json({ error: 'Servicio de impresión no configurado (falta IMPRIMIR_SUBMIT_KEY).' });
  const provided = req.get('x-api-key') || (req.get('authorization') || '').replace(/^Bearer\s+/i, '');
  if (!timingEqual(provided, key)) return res.status(401).json({ error: 'Clave de envío inválida.' });
  next();
}

// ─── Health / reachability (no key: lets the agent verify the URL) ──────────────
// Intentionally minimal — no queue counts here to avoid leaking activity to
// unauthenticated callers (use GET /api/jobs with the key for that).
router.get('/api/health', (req, res) => {
  res.json({ ok: true, enabled: config().enabled });
});

// ─── Submit: any app (any repo/Railway project) pushes a job to the queue ───────
// Multipart: field `file` (PDF/image/office) + optional `filename`, `printer`,
// `source`, `subject`. Server-to-server with the submit key. The single local
// agent prints it — so a "Print" button anywhere ends up on the printer.
router.post('/api/submit', submitKeyGuard, submitUpload.single('file'), async (req, res) => {
  try {
    if (!req.file || !req.file.buffer || !req.file.buffer.length) {
      return res.status(400).json({ error: 'Falta el fichero (campo multipart "file").' });
    }
    const { kindOf, toPdf } = require('./normalize'); // lazy: only load pdfkit/sharp on first submit
    const { storeDoc } = require('./ingest');

    const filename = String(req.body.filename || req.file.originalname || 'documento.pdf');
    const mime = req.file.mimetype || '';
    const kind = kindOf(filename, mime);
    if (!kind) return res.status(400).json({ error: 'Tipo no soportado (usa PDF, imagen JPG/PNG o documento Office).' });

    let pdf;
    try {
      pdf = await toPdf({ filename, mime, content: req.file.buffer, kind });
    } catch (e) {
      return res.status(400).json({ error: 'No se pudo preparar para impresión: ' + e.message });
    }

    const cfg = config();
    const job = storeDoc(cfg, db, {
      messageId: 'submit:' + crypto.randomBytes(12).toString('hex'),
      part_idx: 0,
      sender: String(req.body.source || '') || '(envío por API)',
      subject: String(req.body.subject || filename),
      filename,
      printer: String(req.body.printer || '') || undefined,
    }, pdf.buffer);

    res.json({ ok: true, id: job.id, status: job.status, printer: job.printer });
  } catch (e) {
    console.error('[imprimir] submit error:', e.message);
    res.status(500).json({ error: 'Error al encolar el trabajo de impresión.' });
  }
});

// ─── Agent: claim the next queued job (returns the PDF as base64) ───────────────
router.get('/api/jobs/next', apiKeyGuard, (req, res) => {
  recordAgentPull(); // heartbeat: the agent is alive and talking to us
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
  const mc = maskedConfig();
  const jobs = db.listJobs({ limit: 50 });
  const diag = {
    ...state,
    now: new Date().toISOString(),
    lastEmailAt: jobs.length ? jobs[0].created_at : null,
  };
  res.json({
    config: mc,
    diag,
    checklist: readiness(mc, diag),
    counts: db.counts(),
    jobs,
    printers: { default: db.getDefaultPrinter(), envDefault: mc.defaultPrinter, known: db.getKnownPrinters() },
  });
});

// The local agent reports the printers installed on its PC (so the panel/apps
// can offer a real selector).
router.post('/api/agent/printers', apiKeyGuard, (req, res) => {
  const names = Array.isArray(req.body && req.body.printers) ? req.body.printers : [];
  const merged = db.reportPrinters(names, new Date().toISOString());
  res.json({ ok: true, count: merged.length });
});

// Printer list for other apps' selectors (submit key). Returns the persisted
// default and the printers reported by the agent.
router.get('/api/printers', submitKeyGuard, (req, res) => {
  res.json({
    default: db.getDefaultPrinter() || config().defaultPrinter || null,
    known: db.getKnownPrinters().map(p => p.name),
  });
});

// Set the persisted default printer (panel, admin). Empty ⇒ back to env default.
router.post('/api/printers/default', requireAdmin, (req, res) => {
  const printer = String((req.body && req.body.printer) || '').trim();
  const value = db.setDefaultPrinter(printer);
  res.json({ ok: true, default: value });
});

// Actively test the IMAP connection with the current credentials.
router.post('/api/diag/imap-test', requireAdmin, async (req, res) => {
  const cfg = config();
  if (!cfg.imap.user || !cfg.imap.pass) {
    return res.json({ ok: false, error: 'Faltan usuario/contraseña IMAP en la configuración.' });
  }
  try {
    const { testConnection } = require('./imap'); // lazy: only load imapflow on demand
    const result = await testConnection(cfg);
    res.json(result);
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
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
