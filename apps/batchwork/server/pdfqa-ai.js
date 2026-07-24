'use strict';

// ── RAG engine for "Preguntar a un PDF" ─────────────────────────────────────────
// Pure-ish helpers (chunking, cosine search) plus the two external-API calls:
// OpenAI embeddings (text-embedding-3-small) to index the document and to embed
// the question, and Claude to write the final answer grounded in the retrieved
// fragments with page citations.
//
// The chunking and cosine helpers are exported separately so they can be unit
// tested without any network access.

const EMBED_MODEL = process.env.PDFQA_EMBED_MODEL || 'text-embedding-3-small';
const ANSWER_MODEL = process.env.PDFQA_ANSWER_MODEL || 'claude-opus-4-7';

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

// ── OpenAI embeddings ───────────────────────────────────────────────────────────
function openaiClient() {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) { const e = new Error('OPENAI_API_KEY no configurada.'); e.status = 503; throw e; }
  const { default: OpenAI } = require('openai');
  return new OpenAI({ apiKey });
}

// Embed an array of strings, batching by count and total characters to respect the
// API's per-request limits. Calls onProgress(done, total) after each batch.
async function embedTexts(texts, onProgress) {
  const client = openaiClient();
  const MAX_BATCH = 96;
  const MAX_CHARS = 90000;
  const CAP = 8000; // hard cap per input string (well under the token limit)
  const out = new Array(texts.length);
  let i = 0;
  let done = 0;
  while (i < texts.length) {
    let j = i;
    let chars = 0;
    while (j < texts.length && (j - i) < MAX_BATCH && (chars === 0 || chars + Math.min(texts[j].length, CAP) <= MAX_CHARS)) {
      chars += Math.min(texts[j].length, CAP);
      j++;
    }
    const batch = texts.slice(i, j).map(t => (t.length > CAP ? t.slice(0, CAP) : t) || ' ');
    const resp = await client.embeddings.create({ model: EMBED_MODEL, input: batch });
    for (let k = 0; k < batch.length; k++) out[i + k] = resp.data[k].embedding;
    done += batch.length;
    if (onProgress) onProgress(done, texts.length);
    i = j;
  }
  return out;
}

async function embedQuery(question) {
  const client = openaiClient();
  const resp = await client.embeddings.create({ model: EMBED_MODEL, input: [String(question).slice(0, 8000)] });
  return resp.data[0].embedding;
}

// ── Claude answer ───────────────────────────────────────────────────────────────
// contexts: [{pageStart, pageEnd, text, score}] already sorted best-first.
async function answerQuestion(question, contexts) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) { const e = new Error('ANTHROPIC_API_KEY no configurada.'); e.status = 503; throw e; }
  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic({ apiKey });

  const pageRef = c => (c.pageStart === c.pageEnd ? `pág. ${c.pageStart}` : `págs. ${c.pageStart}–${c.pageEnd}`);
  const contextBlock = contexts
    .map((c, i) => `[Fragmento ${i + 1} · ${pageRef(c)}]\n${c.text}`)
    .join('\n\n────────\n\n');

  const system =
    'Eres un asistente experto que responde preguntas sobre un documento PDF a partir de ' +
    'fragmentos recuperados de él. Reglas:\n' +
    '1) Responde en español, de forma clara y bien estructurada.\n' +
    '2) Usa ÚNICAMENTE la información de los fragmentos proporcionados. No inventes datos.\n' +
    '3) Cita siempre las páginas en las que te apoyas, entre paréntesis, p. ej. (pág. 12) o (págs. 12–14).\n' +
    '4) Si la respuesta no está en los fragmentos, dilo con claridad («No encuentro esa información en las páginas recuperadas») y, si procede, sugiere reformular la pregunta.\n' +
    '5) Sé conciso pero completo; usa listas cuando ayuden.';

  const userContent =
    `FRAGMENTOS DEL DOCUMENTO:\n\n${contextBlock}\n\n` +
    `────────\n\nPREGUNTA DEL USUARIO:\n${question}`;

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
  EMBED_MODEL, ANSWER_MODEL, TARGET_CHARS, OVERLAP_CHARS,
  splitIntoSegments, chunkPages, cosineTopK,
  embedTexts, embedQuery, answerQuestion,
};
