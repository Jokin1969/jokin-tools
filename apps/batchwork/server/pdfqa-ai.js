'use strict';

// ── RAG engine for "Preguntar a un PDF" ─────────────────────────────────────────
// Pure-ish helpers (chunking, cosine search) plus the two external-API calls:
// OpenAI embeddings (text-embedding-3-small) to index the document and to embed
// the question, and Claude to write the final answer grounded in the retrieved
// fragments with page citations.
//
// The chunking and cosine helpers are exported separately so they can be unit
// tested without any network access.

// Embeddings provider. Two backends are supported and auto-selected: Voyage AI
// (Anthropic's embeddings, better for retrieval — especially rare scientific
// terms and cross-lingual questions) when VOYAGE_API_KEY is set, otherwise
// OpenAI. Each document records the exact model it was indexed with, so old
// OpenAI-indexed docs keep working after Voyage is enabled — only NEW digests use
// the new provider. The provider is derived from the model name at query time.
const OPENAI_EMBED_MODEL = process.env.PDFQA_OPENAI_MODEL || process.env.PDFQA_EMBED_MODEL || 'text-embedding-3-small';
const VOYAGE_EMBED_MODEL = process.env.PDFQA_VOYAGE_MODEL || 'voyage-3.5';
const RERANK_MODEL = process.env.PDFQA_RERANK_MODEL || 'rerank-2.5';
const ANSWER_MODEL = process.env.PDFQA_ANSWER_MODEL || 'claude-opus-4-7';

function voyageEnabled() {
  return !!process.env.VOYAGE_API_KEY && process.env.PDFQA_EMBED_PROVIDER !== 'openai';
}

// The embedding model a NEW digest will use (docs remember their own model).
function defaultEmbedModel() {
  return voyageEnabled() ? VOYAGE_EMBED_MODEL : OPENAI_EMBED_MODEL;
}

function providerForModel(model) {
  return /^voyage/i.test(String(model || '')) ? 'voyage' : 'openai';
}
// Backwards-compat export name used elsewhere.
const EMBED_MODEL = OPENAI_EMBED_MODEL;

// Target size of a chunk in characters (~750 tokens) and how much of the previous
// chunk to repeat at the start of the next so answers near a boundary keep their
// context. A single paragraph longer than HARD_MAX is hard-split.
const TARGET_CHARS = parseInt(process.env.PDFQA_CHUNK_CHARS) || 3000;
const OVERLAP_CHARS = parseInt(process.env.PDFQA_CHUNK_OVERLAP) || 350;
const HARD_MAX = 6000;

// ── Chunking ────────────────────────────────────────────────────────────────────
// Break each page into paragraph-sized segments tagged with their page number,
// hard-splitting any paragraph that is too long to embed on its own.
function splitIntoSegments(pages) {
  const segs = [];
  for (const p of pages) {
    const page = p.page;
    const raw = (p.text || '').trim();
    if (!raw) continue;
    const paras = raw.split(/\n\s*\n+/).map(s => s.replace(/[ \t]+\n/g, '\n').trim()).filter(Boolean);
    const list = paras.length ? paras : [raw];
    for (const para of list) {
      if (para.length <= HARD_MAX) {
        segs.push({ page, text: para });
      } else {
        for (let i = 0; i < para.length; i += HARD_MAX) {
          segs.push({ page, text: para.slice(i, i + HARD_MAX) });
        }
      }
    }
  }
  return segs;
}

// Greedily pack segments into chunks up to TARGET_CHARS, backing up by ~OVERLAP
// characters between consecutive chunks. Every chunk records the span of pages it
// covers so the answer can cite them. Guarantees forward progress (never loops).
function chunkPages(pages, opts = {}) {
  const target = opts.targetChars || TARGET_CHARS;
  const overlap = opts.overlapChars != null ? opts.overlapChars : OVERLAP_CHARS;
  const segs = splitIntoSegments(pages);
  const chunks = [];
  let i = 0;
  while (i < segs.length) {
    let j = i;
    let len = 0;
    while (j < segs.length && (len === 0 || len + segs[j].text.length + 2 <= target)) {
      len += segs[j].text.length + 2;
      j++;
    }
    const group = segs.slice(i, j);
    chunks.push({
      idx: chunks.length,
      pageStart: group[0].page,
      pageEnd: group[group.length - 1].page,
      text: group.map(s => s.text).join('\n\n'),
    });
    if (j >= segs.length) break;
    // Back up from j to create overlap, but always advance past i.
    let k = j;
    let back = 0;
    while (k > i + 1 && back < overlap) { k--; back += segs[k].text.length; }
    i = Math.max(k, i + 1);
  }
  return chunks;
}

// ── Cosine similarity search ────────────────────────────────────────────────────
// items: [{id, idx, pageStart, pageEnd, embedding:Float32Array|number[]}].
// Returns the top-k by cosine similarity, each with a `score` field.
function cosineTopK(queryVec, items, k = 10) {
  const q = queryVec;
  let qn = 0;
  for (let i = 0; i < q.length; i++) qn += q[i] * q[i];
  qn = Math.sqrt(qn) || 1;

  const scored = [];
  for (const it of items) {
    const e = it.embedding;
    if (!e || e.length !== q.length) continue;
    let dot = 0;
    let en = 0;
    for (let i = 0; i < e.length; i++) { dot += q[i] * e[i]; en += e[i] * e[i]; }
    en = Math.sqrt(en) || 1;
    scored.push({ id: it.id, idx: it.idx, pageStart: it.pageStart, pageEnd: it.pageEnd, score: dot / (qn * en) });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, k);
}

// ── Embeddings: OpenAI + Voyage ───────────────────────────────────────────────
function openaiClient() {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) { const e = new Error('OPENAI_API_KEY no configurada.'); e.status = 503; throw e; }
  const { default: OpenAI } = require('openai');
  return new OpenAI({ apiKey });
}

const EMBED_CAP = 8000; // hard cap per input string (chars), well under token limits

// Embed a single batch (already size-bounded) with the given model/provider.
// inputType is 'document' (chunks) or 'query' (the question) — Voyage uses it to
// tune the vectors; OpenAI ignores it.
async function embedBatch(batch, model, inputType) {
  if (providerForModel(model) === 'voyage') {
    const apiKey = process.env.VOYAGE_API_KEY;
    if (!apiKey) { const e = new Error('VOYAGE_API_KEY no configurada.'); e.status = 503; throw e; }
    const resp = await fetch('https://api.voyageai.com/v1/embeddings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({ model, input: batch, input_type: inputType }),
    });
    if (!resp.ok) {
      const t = await resp.text().catch(() => '');
      const e = new Error(`Voyage embeddings ${resp.status}: ${t.slice(0, 200)}`);
      e.status = resp.status >= 500 ? 502 : 400; throw e;
    }
    const data = await resp.json();
    // Voyage may return data out of order — sort by index to be safe.
    return (data.data || []).slice().sort((a, b) => a.index - b.index).map(d => d.embedding);
  }
  const resp = await openaiClient().embeddings.create({ model, input: batch });
  return resp.data.map(d => d.embedding);
}

// Embed an array of strings, batching by count and total characters. Calls
// onProgress(done, total) after each batch.
async function embedTexts(texts, model, onProgress) {
  const m = model || defaultEmbedModel();
  const MAX_BATCH = providerForModel(m) === 'voyage' ? 128 : 96;
  const MAX_CHARS = providerForModel(m) === 'voyage' ? 110000 : 90000;
  const out = new Array(texts.length);
  let i = 0;
  let done = 0;
  while (i < texts.length) {
    let j = i;
    let chars = 0;
    while (j < texts.length && (j - i) < MAX_BATCH && (chars === 0 || chars + Math.min(texts[j].length, EMBED_CAP) <= MAX_CHARS)) {
      chars += Math.min(texts[j].length, EMBED_CAP);
      j++;
    }
    const batch = texts.slice(i, j).map(t => (t.length > EMBED_CAP ? t.slice(0, EMBED_CAP) : t) || ' ');
    const vecs = await embedBatch(batch, m, 'document');
    for (let k = 0; k < batch.length; k++) out[i + k] = vecs[k];
    done += batch.length;
    if (onProgress) onProgress(done, texts.length);
    i = j;
  }
  return out;
}

async function embedQuery(question, model) {
  const m = model || defaultEmbedModel();
  const vecs = await embedBatch([String(question).slice(0, EMBED_CAP) || ' '], m, 'query');
  return vecs[0];
}

// ── Voyage reranker (optional) ────────────────────────────────────────────────
// Given a query and candidate passages, return the indices reordered by
// relevance. Only used when VOYAGE_API_KEY is set; callers fall back to the
// hybrid score otherwise.
function rerankAvailable() {
  return !!process.env.VOYAGE_API_KEY && process.env.PDFQA_RERANK !== 'off';
}

async function rerank(question, documents, topK) {
  const apiKey = process.env.VOYAGE_API_KEY;
  if (!apiKey) return null;
  const resp = await fetch('https://api.voyageai.com/v1/rerank', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model: RERANK_MODEL, query: String(question).slice(0, 4000),
      documents: documents.map(d => String(d).slice(0, 8000)),
      top_k: Math.min(topK, documents.length), return_documents: false,
    }),
  });
  if (!resp.ok) return null; // fail soft — caller keeps the hybrid order
  const data = await resp.json();
  return (data.data || []).map(r => ({ index: r.index, score: r.relevance_score }));
}

// ── Lexical term extraction (for hybrid keyword search) ────────────────────────
// Pull the "salient" terms out of a question so we can do an exact substring
// match in the chunk store. This is what rescues rare tokens like "AAV-F",
// "FVIII" or "ST-920" that pure semantic search often misses. Terms that carry a
// digit, hyphen or internal capital (i.e. codes/acronyms) are marked `rare` and
// weighted more heavily.
const STOPWORDS = new Set([
  // Spanish
  'el','la','los','las','un','una','unos','unas','de','del','al','a','en','y','o','u','que','qué','con','por','para','se','su','sus','lo','le','les','es','son','hay','algún','alguna','algun','alguno','alguna','sobre','como','cómo','cual','cuál','cuales','cuáles','muestra','muestre','estudio','estudios','tipo','algo','este','esta','esto','estos','estas',
  // English
  'the','a','an','of','to','in','on','and','or','is','are','was','were','with','for','by','that','this','these','those','any','some','study','studies','show','shows','about','which','what','there','it','as','from','has','have','into','using',
]);

function extractTerms(query) {
  const raw = String(query || '').match(/[\p{L}\p{N}][\p{L}\p{N}.\-]*[\p{L}\p{N}]|[\p{L}\p{N}]/gu) || [];
  const seen = new Set();
  const terms = [];
  for (const tok of raw) {
    const t = tok.replace(/^[.\-]+|[.\-]+$/g, '');
    if (t.length < 2) continue;
    const lower = t.toLowerCase();
    const rare = /[0-9]/.test(t) || /[-.]/.test(t) || /[a-z][A-Z]/.test(t) || (/^[A-Z0-9]{2,}$/.test(t));
    if (!rare && (t.length < 4 || STOPWORDS.has(lower))) continue;
    if (seen.has(lower)) continue;
    seen.add(lower);
    terms.push({ term: t, rare });
  }
  return terms;
}

// Detect the language of the QUESTION so we can force the answer language
// explicitly. "Same language as the question" is too soft when the whole
// retrieved context is in English — the model drifts to English. A hard,
// single-language directive fixes it. Returns 'es' or 'en'.
function detectLang(text) {
  const t = String(text || '').toLowerCase();
  if (/[áéíóúñ¿¡]/.test(t)) return 'es';
  const pad = ' ' + t.replace(/[^\p{L}\s]/gu, ' ').replace(/\s+/g, ' ') + ' ';
  const ES = [' el ', ' la ', ' los ', ' las ', ' un ', ' una ', ' de ', ' del ', ' que ', ' con ', ' por ', ' para ', ' hay ', ' algún ', ' alguna ', ' cual ', ' que ', ' como ', ' esta ', ' es ', ' se ', ' en ', ' y ', ' o ', ' muestra ', ' estudio ', ' sobre ', ' cuales '];
  const EN = [' the ', ' a ', ' an ', ' of ', ' that ', ' with ', ' for ', ' is ', ' are ', ' any ', ' study ', ' show ', ' what ', ' which ', ' how ', ' does ', ' this ', ' in ', ' and ', ' or ', ' about ', ' there ', ' can ', ' do '];
  let es = 0;
  let en = 0;
  for (const w of ES) if (pad.includes(w)) es++;
  for (const w of EN) if (pad.includes(w)) en++;
  return en > es ? 'en' : 'es'; // ties → Spanish (the user's primary language)
}

// ── Claude answer ───────────────────────────────────────────────────────────────
// contexts: [{pageStart, pageEnd, text, score}] already sorted best-first.
async function answerQuestion(question, contexts) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) { const e = new Error('ANTHROPIC_API_KEY no configurada.'); e.status = 503; throw e; }
  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic({ apiKey });

  const lang = detectLang(question);
  const langName = lang === 'es' ? 'ESPAÑOL' : 'INGLÉS (English)';

  const pageRef = c => (c.pageStart === c.pageEnd ? `pág. ${c.pageStart}` : `págs. ${c.pageStart}–${c.pageEnd}`);
  const contextBlock = contexts
    .map((c, i) => `[Fragmento ${i + 1} · ${pageRef(c)}]\n${c.text}`)
    .join('\n\n────────\n\n');

  const system =
    'Eres un asistente experto que responde preguntas sobre un documento PDF a partir de ' +
    'fragmentos recuperados de él. Reglas:\n' +
    `1) Escribe TODA tu respuesta EXCLUSIVAMENTE en ${langName}, aunque los fragmentos del ` +
    'documento estén en otro idioma. No cambies de idioma bajo ninguna circunstancia; si el ' +
    'documento está en inglés y debes responder en español, traduce lo necesario.\n' +
    '2) Usa ÚNICAMENTE la información de los fragmentos proporcionados. No inventes datos. ' +
    'Puedes citar entre comillas alguna frase clave del documento en su idioma original cuando ' +
    'aporte precisión, pero el resto de la respuesta va en el idioma indicado.\n' +
    '3) Cita siempre las páginas en las que te apoyas, entre paréntesis, p. ej. (pág. 12) / (págs. 12–14) ' +
    'o (p. 12) / (pp. 12–14) según el idioma de tu respuesta.\n' +
    '4) Si la respuesta no está en los fragmentos, dilo con claridad y, si procede, sugiere reformular.\n' +
    '5) Sé conciso pero completo; usa listas cuando ayuden.';

  const userContent =
    `FRAGMENTOS DEL DOCUMENTO:\n\n${contextBlock}\n\n` +
    `────────\n\nPREGUNTA DEL USUARIO:\n${question}\n\n` +
    `[RECUERDA: redacta toda la respuesta en ${langName}.]`;

  const msg = await client.messages.create({
    model: ANSWER_MODEL,
    max_tokens: 1800,
    system: [{ type: 'text', text: system }],
    messages: [{ role: 'user', content: userContent }],
  });
  const block = (msg.content || []).find(b => b.type === 'text');
  if (!block) throw new Error(`El modelo no devolvió texto (stop_reason: ${msg.stop_reason}).`);
  return block.text.trim();
}

module.exports = {
  EMBED_MODEL, OPENAI_EMBED_MODEL, VOYAGE_EMBED_MODEL, RERANK_MODEL, ANSWER_MODEL,
  TARGET_CHARS, OVERLAP_CHARS,
  voyageEnabled, defaultEmbedModel, providerForModel, rerankAvailable, detectLang,
  splitIntoSegments, chunkPages, cosineTopK, extractTerms,
  embedTexts, embedQuery, rerank, answerQuestion,
};
