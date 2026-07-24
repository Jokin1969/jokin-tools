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

// Persistent store for the original PDFs (on the /data volume) so we can open the
// exact page a citation points to. Survives redeploys like the SQLite repo.
const FILES_DIR = path.join(process.env.BATCHWORK_DATA_DIR || '/data/batchwork', 'pdfqa-files');
try { fs.mkdirSync(FILES_DIR, { recursive: true }); } catch { /* created lazily on first save */ }
const pdfPathFor = id => path.join(FILES_DIR, `${id}.pdf`);
const hasPdf = id => { try { return fs.existsSync(pdfPathFor(id)); } catch { return false; } };

const MAX_MB = parseInt(process.env.PDFQA_MAX_UPLOAD_MB) || 120;
const RETRIEVE_K = parseInt(process.env.PDFQA_TOP_K) || 10;
// How many candidates to gather from each retrieval arm before final ranking.
const SEM_POOL = parseInt(process.env.PDFQA_SEM_POOL) || 30;
const LEX_POOL = parseInt(process.env.PDFQA_LEX_POOL) || 40;

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
async function digest(docId, pdfPath, model) {
  // Keep the extracted-text scratch file in TMP; the PDF itself stays in FILES_DIR.
  const jsonlPath = path.join(TMP_DIR, `${docId}.jsonl`);
  let ok = false;
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
    const vectors = await ai.embedTexts(chunks.map(c => c.text), model, (done, total) => {
      store.updateProgress(docId, { phase: 'embedding', current: done, total, message: `Indexando fragmentos (${done}/${total})` });
    });

    // Persist in batches to keep each transaction small on very large docs.
    const withVecs = chunks.map((c, i) => ({ ...c, embedding: vectors[i] }));
    const BATCH = 500;
    for (let i = 0; i < withVecs.length; i += BATCH) {
      store.insertChunks(docId, withVecs.slice(i, i + BATCH));
    }
    store.markReady(docId, { chunks: chunks.length });
    ok = true;
    console.log(`[batchwork/pdfqa] doc ${docId} listo: ${ex.pages} págs, ${chunks.length} fragmentos (${model})`);
  } catch (err) {
    console.error(`[batchwork/pdfqa] doc ${docId} falló:`, err.message);
    store.markError(docId, err.message);
  } finally {
    try { fs.rmSync(jsonlPath, { force: true }); } catch { /* ignore */ }
    // On success keep the PDF (so citations can open the page); on failure drop it.
    if (!ok) { try { fs.rmSync(pdfPathFor(docId), { force: true }); } catch { /* ignore */ } }
  }
}

// ── Routes ──────────────────────────────────────────────────────────────────────

// Whether the AI back-ends are configured (surfaced in the UI up front).
router.get('/meta', (req, res) => {
  const voyage = ai.voyageEnabled();
  res.json({
    openai: !!process.env.OPENAI_API_KEY,
    voyage,
    embedReady: voyage || !!process.env.OPENAI_API_KEY,
    anthropic: !!process.env.ANTHROPIC_API_KEY,
    embedModel: ai.defaultEmbedModel(),
    embedProvider: voyage ? 'voyage' : 'openai',
    rerank: ai.rerankAvailable(),
    answerModel: ai.ANSWER_MODEL,
    maxUploadMB: MAX_MB,
  });
});

// Kick off digestion. Returns immediately with the new doc (status 'processing').
router.post('/digest', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) { const e = new Error('No se recibió ningún PDF.'); e.status = 400; throw e; }
    if (!ai.voyageEnabled() && !process.env.OPENAI_API_KEY) {
      try { fs.rmSync(req.file.path, { force: true }); } catch { /* ignore */ }
      const e = new Error('El indexado por IA no está configurado (falta OPENAI_API_KEY o VOYAGE_API_KEY).'); e.status = 503; throw e;
    }
    const model = ai.defaultEmbedModel();
    const origName = Buffer.from(req.file.originalname, 'latin1').toString('utf8');
    const doc = store.createDoc(
      { name: origName, bytes: req.file.size, model },
      req.user.id
    );
    // Move the upload to its persistent home (keyed by doc id) so citations can
    // reopen the exact page later. rename() can cross devices → fall back to copy.
    try {
      fs.mkdirSync(FILES_DIR, { recursive: true });
      try { fs.renameSync(req.file.path, pdfPathFor(doc.id)); }
      catch { fs.copyFileSync(req.file.path, pdfPathFor(doc.id)); fs.rmSync(req.file.path, { force: true }); }
    } catch (e) {
      console.error('[batchwork/pdfqa] no se pudo guardar el PDF:', e.message);
      store.markError(doc.id, 'No se pudo guardar el PDF en el servidor.');
      const err = new Error('No se pudo guardar el PDF en el servidor.'); err.status = 500; throw err;
    }
    // Fire-and-forget; the client polls for progress.
    digest(doc.id, pdfPathFor(doc.id), model);
    res.status(202).json({ doc: { ...doc, hasPdf: true } });
  } catch (err) { fail(res, err); }
});

router.get('/docs', (req, res) => {
  try {
    const items = store.listDocs(req.user.id).map(d => ({ ...d, hasPdf: hasPdf(d.id) }));
    res.json({ items });
  } catch (err) { fail(res, err); }
});

router.get('/docs/:id(\\d+)', (req, res) => {
  try {
    const doc = store.getDoc(Number(req.params.id), req.user.id);
    if (!doc) return res.status(404).json({ error: 'No encontrado' });
    res.json({ doc: { ...doc, hasPdf: hasPdf(doc.id) } });
  } catch (err) { fail(res, err); }
});

// Serve the original PDF inline so the browser viewer can jump to a page via the
// #page=N fragment the client appends. Scoped to the owner.
router.get('/docs/:id(\\d+)/pdf', (req, res) => {
  try {
    const doc = store.getDoc(Number(req.params.id), req.user.id);
    if (!doc) return res.status(404).json({ error: 'No encontrado' });
    const p = pdfPathFor(doc.id);
    if (!fs.existsSync(p)) return res.status(404).json({ error: 'El PDF original no está disponible para este documento.' });
    const ascii = String(doc.name || 'documento.pdf').replace(/[^\x20-\x7E]/g, '_').replace(/["\\]/g, '_');
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `inline; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(doc.name || 'documento.pdf')}`);
    fs.createReadStream(p).pipe(res);
  } catch (err) { fail(res, err); }
});

router.delete('/docs/:id(\\d+)', (req, res) => {
  try {
    const id = Number(req.params.id);
    const ok = store.removeDoc(id, req.user.id);
    if (!ok) return res.status(404).json({ error: 'No encontrado' });
    try { fs.rmSync(pdfPathFor(id), { force: true }); } catch { /* ignore */ }
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

    // ── Hybrid retrieval ──────────────────────────────────────────────────────
    // Two arms, then merge: (1) SEMANTIC — cosine over the doc's embeddings, using
    // the SAME model the doc was indexed with; (2) LEXICAL — exact keyword match,
    // which rescues rare codes/acronyms (e.g. "AAV-F", "FVIII") that semantic
    // search alone often misses. Optionally re-ranked by Voyage.
    const queryVec = await ai.embedQuery(q, doc.model);
    const items = store.loadEmbeddings(doc.id);
    if (!items.length) { const e = new Error('El documento no tiene fragmentos indexados.'); e.status = 409; throw e; }
    const sem = ai.cosineTopK(queryVec, items, SEM_POOL); // [{id,pageStart,pageEnd,score}]
    const terms = ai.extractTerms(q);
    const lex = store.searchChunksByTerms(doc.id, terms, LEX_POOL); // [{id,...,lexScore,matched}]

    // Merge into a candidate map keyed by chunk id. A chunk can come from either
    // arm (or both). `matched` = how many distinct query terms it contains.
    const cand = new Map();
    for (const s of sem) cand.set(s.id, { id: s.id, pageStart: s.pageStart, pageEnd: s.pageEnd, cos: s.score, lex: 0, matched: 0 });
    for (const l of lex) {
      const e = cand.get(l.id) || { id: l.id, pageStart: l.pageStart, pageEnd: l.pageEnd, cos: 0, lex: 0, matched: 0 };
      e.lex = l.lexScore; e.matched = l.matched;
      cand.set(l.id, e);
    }
    let pool = [...cand.values()];
    const texts = store.getChunkTexts(pool.map(c => c.id));
    for (const c of pool) c.text = (texts[c.id] && texts[c.id].text) || '';
    pool = pool.filter(c => c.text);
    if (!pool.length) { const e = new Error('No se encontraron fragmentos relevantes.'); e.status = 409; throw e; }
    const byId = new Map(pool.map(c => [c.id, c]));

    // Select the final RETRIEVE_K. Key insight from the reported bug: when a
    // fragment literally contains the term the user asked about (e.g. "AAV-F"),
    // it MUST reach the model — a near-1.0 cosine on an unrelated fragment should
    // not crowd it out. So we GUARANTEE slots for the strongest lexical hits,
    // then fill the rest with the best semantic matches.
    let ranked;
    if (ai.rerankAvailable() && pool.length > RETRIEVE_K) {
      // Voyage rerank scores query↔passage relevance directly (handles exact
      // matches well); trust it, but still guarantee the top lexical hit is in.
      try {
        const rr = await ai.rerank(q, pool.map(c => c.text), RETRIEVE_K);
        if (rr && rr.length) {
          ranked = rr.map(r => ({ ...pool[r.index], score: r.score })).filter(Boolean);
          const bestLex = lex.filter(l => byId.has(l.id)).sort((a, b) => b.lexScore - a.lexScore)[0];
          if (bestLex && !ranked.some(c => c.id === bestLex.id)) {
            ranked.pop();
            ranked.push({ ...byId.get(bestLex.id) });
          }
        }
      } catch (e) { console.error('[batchwork/pdfqa] rerank falló, uso híbrido:', e.message); }
    }
    if (!ranked) {
      ranked = [];
      const used = new Set();
      // 1) Guaranteed lexical slots (strongest term coverage first).
      const lexSorted = lex.filter(l => byId.has(l.id))
        .sort((a, b) => b.lexScore - a.lexScore || b.matched - a.matched);
      const guarantee = Math.min(lexSorted.length, Math.max(3, Math.floor(RETRIEVE_K / 2)));
      for (let i = 0; i < guarantee; i++) { used.add(lexSorted[i].id); ranked.push(byId.get(lexSorted[i].id)); }
      // 2) Fill the rest with the best semantic matches.
      const semSorted = pool.slice().sort((a, b) => (b.cos || 0) - (a.cos || 0));
      for (const c of semSorted) {
        if (ranked.length >= RETRIEVE_K) break;
        if (used.has(c.id)) continue;
        used.add(c.id); ranked.push(c);
      }
      // Order the chosen set: exact-term matches first, then by semantic score.
      ranked.sort((a, b) => (b.matched - a.matched) || ((b.cos || 0) - (a.cos || 0)));
    }
    ranked = ranked.slice(0, RETRIEVE_K);

    const contexts = ranked.map(c => ({ pageStart: c.pageStart, pageEnd: c.pageEnd, score: c.score != null ? c.score : c.cos, text: c.text }));

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
  try {
    const items = store.listQA().map(it => ({ ...it, hasPdf: it.docId != null && hasPdf(it.docId) }));
    res.json({ items });
  } catch (err) { fail(res, err); }
});

router.delete('/qa/:id(\\d+)', (req, res) => {
  try {
    const ok = store.removeQA(Number(req.params.id));
    if (!ok) return res.status(404).json({ error: 'No encontrado' });
    res.json({ ok: true });
  } catch (err) { fail(res, err); }
});

module.exports = router;
