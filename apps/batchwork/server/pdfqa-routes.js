'use strict';

// ── "Preguntar a un PDF (IA)" — Miscelánea section of Batchwork ─────────────────
// Digest a (text, non-scanned) PDF once — extract per-page text with pypdf, chunk
// it, embed the chunks with OpenAI and store them in the shared SQLite repo — then
// answer natural-language questions about it with Claude, grounded in the retrieved
// fragments and citing page numbers. Mounted under /batchwork/api/pdfqa.

const express = require('express');
const multer = require('multer');
const os = require('os');
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { spawn } = require('child_process');

const store = require('./pdfqa-store');
const ai = require('./pdfqa-ai');
const { PYTHON_BIN, PYTHON_DIR, buildPythonEnv } = require('./spawn-python');

const router = express.Router();
const json = express.json({ limit: '1mb' });

// Temp workspace for uploaded PDFs + extracted JSONL (deleted after digestion).
const TMP_DIR = path.join(os.tmpdir(), 'batchwork-pdfqa');
fs.mkdirSync(TMP_DIR, { recursive: true });

const MAX_MB = parseInt(process.env.PDFQA_MAX_UPLOAD_MB) || 120;
const RETRIEVE_K = parseInt(process.env.PDFQA_TOP_K) || 10;

const upload = multer({
  storage: multer.diskStorage({
    destination: (req, file, cb) => cb(null, TMP_DIR),
    filename: (req, file, cb) => {
      // Unique, opaque on-disk name; original name is kept separately.
      const stamp = `${process.pid}-${req.user.id}-${store.db.prepare("SELECT COUNT(*) n FROM pdfqa_docs").get().n}-${file.fieldname}`;
      cb(null, `${stamp}.pdf`);
    },
  }),
  limits: { fileSize: MAX_MB * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const ok = /pdf$/i.test(file.mimetype) || /\.pdf$/i.test(file.originalname);
    cb(ok ? null : Object.assign(new Error('Solo se admiten ficheros PDF.'), { status: 400 }), ok);
  },
});

function fail(res, err) {
  const status = err && err.status ? err.status : 500;
  if (status >= 500) console.error('[batchwork/pdfqa] error:', err);
  res.status(status).json({ error: err.message || 'Error en Preguntar a un PDF.' });
}

// ── Python text extraction with progress capture ───────────────────────────────
function runExtract(input, output, onProgress) {
  return new Promise((resolve, reject) => {
    const script = path.join(PYTHON_DIR, 'pdf_extract_text.py');
    const proc = spawn(PYTHON_BIN, [script, '--input', input, '--output', output], { env: buildPythonEnv() });
    let stderr = '';
    let result = null;
    let warning = null;
    proc.stdout.on('data', (data) => {
      for (const line of data.toString().split('\n').map(l => l.trim()).filter(Boolean)) {
        if (line.startsWith('PROGRESS:')) {
          const parts = line.split(':');
          const current = parseInt(parts[1]) || 0;
          const total = parseInt(parts[2]) || 0;
          const message = parts.slice(3).join(':');
          if (onProgress) onProgress(current, total, message);
        } else if (line.startsWith('WARN:')) {
          warning = line.split(':').slice(2).join(':');
        } else if (line.startsWith('RESULT:')) {
          try { result = JSON.parse(line.slice('RESULT:'.length)); } catch { /* ignore */ }
        } else if (line.startsWith('ERROR:')) {
          stderr += line.split(':').slice(2).join(':') + '\n';
        }
      }
    });
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => {
      if (code !== 0) return reject(new Error((stderr.trim() || `Python exit ${code}`).slice(0, 400)));
      resolve({ pages: (result && result.pages) || 0, emptyPages: (result && result.empty_pages) || 0, warning });
    });
    proc.on('error', (e) => reject(new Error(`No se pudo iniciar la extracción: ${e.message}`)));
  });
}

// Read the JSONL produced by the extractor back into [{page, text}], streaming so
// a huge document never has to sit fully in memory as one string.
function readPages(jsonlPath) {
  return new Promise((resolve, reject) => {
    const pages = [];
    const rl = readline.createInterface({ input: fs.createReadStream(jsonlPath, 'utf8'), crlfDelay: Infinity });
    rl.on('line', (line) => {
      const s = line.trim();
      if (!s) return;
      try { pages.push(JSON.parse(s)); } catch { /* skip corrupt line */ }
    });
    rl.on('close', () => resolve(pages));
    rl.on('error', reject);
  });
}

// The long-running digestion pipeline. Runs detached from the HTTP request; the
// client polls GET /docs/:id for progress. Never throws to the caller — failures
// are recorded on the doc row.
async function digest(docId, pdfPath) {
  const jsonlPath = `${pdfPath}.jsonl`;
  try {
    store.updateProgress(docId, { phase: 'extracting', current: 0, total: 0, message: 'Extrayendo texto…' });
    const ex = await runExtract(pdfPath, jsonlPath, (cur, total, message) => {
      store.updateProgress(docId, { phase: 'extracting', current: cur, total, message });
    });
    store.setPages(docId, ex.pages);
    if (ex.warning) store.setWarning(docId, ex.warning);
    if (ex.pages && ex.emptyPages >= ex.pages) {
      throw new Error('El PDF no contiene texto extraíble (parece escaneado; necesitaría OCR).');
    }

    const pages = await readPages(jsonlPath);
    const chunks = ai.chunkPages(pages);
    if (!chunks.length) throw new Error('No se pudo extraer texto del PDF.');

    store.updateProgress(docId, { phase: 'embedding', current: 0, total: chunks.length, message: 'Indexando fragmentos…' });
    const vectors = await ai.embedTexts(chunks.map(c => c.text), (done, total) => {
      store.updateProgress(docId, { phase: 'embedding', current: done, total, message: `Indexando fragmentos (${done}/${total})` });
    });

    // Persist in batches to keep each transaction small on very large docs.
    const withVecs = chunks.map((c, i) => ({ ...c, embedding: vectors[i] }));
    const BATCH = 500;
    for (let i = 0; i < withVecs.length; i += BATCH) {
      store.insertChunks(docId, withVecs.slice(i, i + BATCH));
    }
    store.markReady(docId, { chunks: chunks.length });
    console.log(`[batchwork/pdfqa] doc ${docId} listo: ${ex.pages} págs, ${chunks.length} fragmentos`);
  } catch (err) {
    console.error(`[batchwork/pdfqa] doc ${docId} falló:`, err.message);
    store.markError(docId, err.message);
  } finally {
    try { fs.rmSync(pdfPath, { force: true }); } catch { /* ignore */ }
    try { fs.rmSync(jsonlPath, { force: true }); } catch { /* ignore */ }
  }
}

// ── Routes ──────────────────────────────────────────────────────────────────────

// Whether the AI back-ends are configured (surfaced in the UI up front).
router.get('/meta', (req, res) => {
  res.json({
    openai: !!process.env.OPENAI_API_KEY,
    anthropic: !!process.env.ANTHROPIC_API_KEY,
    embedModel: ai.EMBED_MODEL,
    answerModel: ai.ANSWER_MODEL,
    maxUploadMB: MAX_MB,
  });
});

// Kick off digestion. Returns immediately with the new doc (status 'processing').
router.post('/digest', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) { const e = new Error('No se recibió ningún PDF.'); e.status = 400; throw e; }
    if (!process.env.OPENAI_API_KEY) {
      try { fs.rmSync(req.file.path, { force: true }); } catch { /* ignore */ }
      const e = new Error('El indexado por IA no está configurado (falta OPENAI_API_KEY).'); e.status = 503; throw e;
    }
    const origName = Buffer.from(req.file.originalname, 'latin1').toString('utf8');
    const doc = store.createDoc(
      { name: origName, bytes: req.file.size, model: ai.EMBED_MODEL },
      req.user.id
    );
    // Fire-and-forget; the client polls for progress.
    digest(doc.id, req.file.path);
    res.status(202).json({ doc });
  } catch (err) { fail(res, err); }
});

router.get('/docs', (req, res) => {
  try { res.json({ items: store.listDocs(req.user.id) }); } catch (err) { fail(res, err); }
});

router.get('/docs/:id(\\d+)', (req, res) => {
  try {
    const doc = store.getDoc(Number(req.params.id), req.user.id);
    if (!doc) return res.status(404).json({ error: 'No encontrado' });
    res.json({ doc });
  } catch (err) { fail(res, err); }
});

router.delete('/docs/:id(\\d+)', (req, res) => {
  try {
    const ok = store.removeDoc(Number(req.params.id), req.user.id);
    if (!ok) return res.status(404).json({ error: 'No encontrado' });
    res.json({ ok: true });
  } catch (err) { fail(res, err); }
});

// Ask a question about a digested document.
router.post('/ask', json, async (req, res) => {
  try {
    const { docId, question } = req.body || {};
    const q = String(question || '').trim();
    if (!q) { const e = new Error('Escribe una pregunta.'); e.status = 400; throw e; }
    const doc = store.getDoc(Number(docId), req.user.id);
    if (!doc) { const e = new Error('Documento no encontrado.'); e.status = 404; throw e; }
    if (doc.status !== 'ready') { const e = new Error('El documento aún se está procesando.'); e.status = 409; throw e; }

    const queryVec = await ai.embedQuery(q);
    const items = store.loadEmbeddings(doc.id);
    const top = ai.cosineTopK(queryVec, items, RETRIEVE_K);
    if (!top.length) { const e = new Error('El documento no tiene fragmentos indexados.'); e.status = 409; throw e; }

    const texts = store.getChunkTexts(top.map(t => t.id));
    const contexts = top.map(t => ({
      pageStart: t.pageStart, pageEnd: t.pageEnd, score: t.score,
      text: (texts[t.id] && texts[t.id].text) || '',
    })).filter(c => c.text);

    const answer = await ai.answerQuestion(q, contexts);

    // Deduplicated, ordered list of source page ranges for the UI.
    const seen = new Set();
    const sources = [];
    for (const c of contexts) {
      const key = `${c.pageStart}-${c.pageEnd}`;
      if (seen.has(key)) continue;
      seen.add(key);
      sources.push({ pageStart: c.pageStart, pageEnd: c.pageEnd, score: Math.round(c.score * 1000) / 1000 });
    }

    // Save to the SHARED Q&A repository (visible to everyone). Best-effort: a
    // storage hiccup must not fail the answer the user already got.
    let saved = null;
    try {
      saved = store.saveQA({
        docId: doc.id, docName: doc.name,
        userId: req.user.id, userEmail: req.user.email || null,
        question: q, answer, sources: sources.map(s => ({ pageStart: s.pageStart, pageEnd: s.pageEnd })),
      });
    } catch (e) { console.error('[batchwork/pdfqa] no se pudo guardar la Q&A:', e.message); }

    res.json({ answer, sources, qa: saved });
  } catch (err) { fail(res, err); }
});

// ── Shared Q&A repository (visible to all users) ────────────────────────────────
router.get('/qa', (req, res) => {
  try { res.json({ items: store.listQA() }); } catch (err) { fail(res, err); }
});

router.delete('/qa/:id(\\d+)', (req, res) => {
  try {
    const ok = store.removeQA(Number(req.params.id));
    if (!ok) return res.status(404).json({ error: 'No encontrado' });
    res.json({ ok: true });
  } catch (err) { fail(res, err); }
});

module.exports = router;
