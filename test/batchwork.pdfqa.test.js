const { test } = require('node:test');
const assert = require('node:assert');
const { useTempDb } = require('./helpers');

useTempDb();
const ai = require('../apps/batchwork/server/pdfqa-ai');
const store = require('../apps/batchwork/server/pdfqa-store');

// ── Chunking ─────────────────────────────────────────────────────────────────
test('chunkPages: sequential idx, valid page spans, non-empty text', () => {
  const pages = [];
  for (let p = 1; p <= 8; p++) {
    let t = '';
    for (let par = 0; par < 4; par++) t += ('Página ' + p + ' párrafo ' + par + '. ').repeat(25) + '\n\n';
    pages.push({ page: p, text: t });
  }
  const chunks = ai.chunkPages(pages, { targetChars: 3000, overlapChars: 350 });
  assert.ok(chunks.length >= 8, 'produces multiple chunks');
  chunks.forEach((c, i) => {
    assert.equal(c.idx, i, 'idx sequential');
    assert.ok(c.text.trim().length > 0, 'chunk has text');
    assert.ok(c.pageStart >= 1 && c.pageEnd <= 8, 'page span within document');
    assert.ok(c.pageStart <= c.pageEnd, 'pageStart <= pageEnd');
  });
});

test('chunkPages: skips empty/whitespace pages, keeps page numbers', () => {
  const chunks = ai.chunkPages([
    { page: 1, text: '' },
    { page: 2, text: '   \n  ' },
    { page: 3, text: 'Hola mundo.' },
  ]);
  assert.equal(chunks.length, 1);
  assert.equal(chunks[0].pageStart, 3);
  assert.equal(chunks[0].text, 'Hola mundo.');
});

test('chunkPages: hard-splits a paragraph larger than the cap', () => {
  const big = 'x'.repeat(20000);
  const chunks = ai.chunkPages([{ page: 1, text: big }]);
  assert.ok(chunks.length > 1, 'splits the giant paragraph');
  assert.ok(chunks.every(c => c.text.length <= 6000), 'each piece under HARD_MAX');
});

test('chunkPages: always makes forward progress (no infinite loop) with tiny target', () => {
  const pages = [{ page: 1, text: Array.from({ length: 40 }, (_, i) => 'Frase ' + i + '.').join('\n\n') }];
  const chunks = ai.chunkPages(pages, { targetChars: 10, overlapChars: 50 });
  assert.ok(chunks.length > 0 && chunks.length < 200, 'terminates with a sane chunk count');
});

// ── Cosine search ────────────────────────────────────────────────────────────
test('cosineTopK: ranks by similarity and respects k', () => {
  const items = [
    { id: 1, idx: 0, pageStart: 1, pageEnd: 1, embedding: new Float32Array([1, 0, 0]) },
    { id: 2, idx: 1, pageStart: 2, pageEnd: 2, embedding: new Float32Array([0, 1, 0]) },
    { id: 3, idx: 2, pageStart: 3, pageEnd: 3, embedding: new Float32Array([0.7, 0.7, 0]) },
  ];
  const top = ai.cosineTopK([1, 0, 0], items, 2);
  assert.equal(top.length, 2);
  assert.equal(top[0].id, 1, 'exact match first');
  assert.equal(top[1].id, 3, 'partial match second');
  assert.ok(top[0].score > top[1].score);
});

test('cosineTopK: skips vectors of the wrong dimension', () => {
  const items = [{ id: 1, idx: 0, pageStart: 1, pageEnd: 1, embedding: new Float32Array([1, 0, 0]) }];
  assert.equal(ai.cosineTopK([1, 0], items, 5).length, 0);
});

// ── Store round-trip ─────────────────────────────────────────────────────────
test('store: doc lifecycle, embedding BLOB round-trip, retrieval, isolation, cascade', () => {
  const doc = store.createDoc({ name: 'libro.pdf', bytes: 999, model: 'text-embedding-3-small' }, 7);
  assert.equal(doc.status, 'processing');

  const chunks = [
    { idx: 0, pageStart: 1, pageEnd: 2, text: 'El gato duerme.', embedding: [1, 0, 0, 0] },
    { idx: 1, pageStart: 3, pageEnd: 3, text: 'El perro corre.', embedding: [0, 1, 0, 0] },
    { idx: 2, pageStart: 4, pageEnd: 5, text: 'El pájaro vuela.', embedding: [0, 0, 1, 0] },
  ];
  store.insertChunks(doc.id, chunks);
  store.markReady(doc.id, { chunks: chunks.length });

  const d2 = store.getDoc(doc.id, 7);
  assert.equal(d2.status, 'ready');
  assert.equal(d2.chunks, 3);

  const items = store.loadEmbeddings(doc.id);
  assert.equal(items.length, 3);
  assert.equal(items[0].embedding.length, 4);
  assert.deepEqual(Array.from(items[0].embedding), [1, 0, 0, 0]);

  const top = ai.cosineTopK([1, 0, 0, 0], items, 1);
  const texts = store.getChunkTexts(top.map(t => t.id));
  assert.equal(texts[top[0].id].text, 'El gato duerme.');

  // Per-user isolation.
  assert.equal(store.listDocs(7).length, 1);
  assert.equal(store.listDocs(9).length, 0);
  assert.equal(store.getDoc(doc.id, 9), null);

  // Delete cascades to chunks.
  assert.equal(store.removeDoc(doc.id, 7), true);
  assert.equal(store.listDocs(7).length, 0);
  assert.equal(store.countChunks(doc.id), 0);
});

test('extractTerms: keeps rare codes/acronyms, drops stopwords, flags rare', () => {
  const t = ai.extractTerms('Hay algún abstract que muestre algún estudio con el AAV-F?');
  const terms = t.map(x => x.term);
  assert.ok(terms.includes('AAV-F'), 'keeps the hyphenated code');
  assert.ok(t.find(x => x.term === 'AAV-F').rare, 'AAV-F flagged rare');
  assert.ok(!terms.includes('que') && !terms.includes('con') && !terms.includes('estudio'), 'stopwords dropped');

  const t2 = ai.extractTerms('AAV-F8 hemophilia FVIII ST-920');
  const rare = t2.filter(x => x.rare).map(x => x.term);
  assert.ok(rare.includes('AAV-F8') && rare.includes('FVIII') && rare.includes('ST-920'), 'codes flagged rare');
});

test('detectLang: forces answer language from the question, not the document', () => {
  assert.equal(ai.detectLang('Any study with AAV-F?'), 'en');
  assert.equal(ai.detectLang('Is there any abstract about AAV-F?'), 'en');
  assert.equal(ai.detectLang('Hay algún abstract que muestre estudio con AAV-F?'), 'es');
  assert.equal(ai.detectLang('¿Cuál es el límite de temperatura?'), 'es');
  assert.equal(ai.detectLang('Que estudios hay sobre AAV-F'), 'es'); // no accents
  assert.equal(ai.detectLang(''), 'es'); // default to Spanish
});

test('store: lexical search finds exact term matches and ranks by coverage', () => {
  const doc = store.createDoc({ name: 'aav.pdf', bytes: 1, model: 'text-embedding-3-small' }, 8);
  store.insertChunks(doc.id, [
    { idx: 0, pageStart: 10, pageEnd: 10, text: 'Overview of AAV2 and AAV8 serotypes.', embedding: [1, 0] },
    { idx: 1, pageStart: 2719, pageEnd: 2722, text: 'AAV-F is a CNS-tropic engineered capsid in this abstract.', embedding: [0, 1] },
  ]);
  store.markReady(doc.id, { chunks: 2 });

  const terms = ai.extractTerms('algún abstract con AAV-F');
  const hits = store.searchChunksByTerms(doc.id, terms, 40);
  assert.equal(hits.length, 1, 'only the AAV-F chunk matches');
  assert.equal(hits[0].pageStart, 2719);
  assert.ok(hits[0].matched >= 1);

  // A term that appears nowhere returns nothing; LIKE wildcards are escaped.
  assert.equal(store.searchChunksByTerms(doc.id, [{ term: 'AAV-Z9', rare: true }], 40).length, 0);
  assert.equal(store.searchChunksByTerms(doc.id, [{ term: '100%_x', rare: true }], 40).length, 0);
});

test('store: markError records the failure on the doc', () => {
  const doc = store.createDoc({ name: 'roto.pdf', bytes: 1 }, 3);
  store.markError(doc.id, 'PDF escaneado');
  const d = store.getDoc(doc.id, 3);
  assert.equal(d.status, 'error');
  assert.match(d.error, /escaneado/);
});

test('store: shared Q&A repository is visible to all users and deletable by anyone', () => {
  const a = store.saveQA({
    docId: 10, docName: 'A.pdf', userId: 1, userEmail: 'ana@lab.com',
    question: '¿Qué es X?', answer: 'X es Y (pág. 3).', sources: [{ pageStart: 3, pageEnd: 3 }],
  });
  const b = store.saveQA({
    docId: 11, docName: 'B.pdf', userId: 2, userEmail: 'beto@lab.com',
    question: '¿Cómo funciona Z?', answer: 'Z hace W (págs. 5–6).', sources: [{ pageStart: 5, pageEnd: 6 }],
  });

  // Not scoped: listQA takes no user id and returns everyone's, newest first.
  const all = store.listQA();
  assert.ok(all.length >= 2);
  assert.equal(all[0].id, b.id, 'newest first');
  const seen = all.find(x => x.id === a.id);
  assert.equal(seen.userEmail, 'ana@lab.com');
  assert.equal(seen.docName, 'A.pdf');
  assert.deepEqual(seen.sources, [{ pageStart: 3, pageEnd: 3 }]);

  // Any user can delete (shared lab resource).
  assert.equal(store.removeQA(a.id), true);
  assert.equal(store.listQA().some(x => x.id === a.id), false);
});

test('store: Q&A survives deletion of its source document', () => {
  const doc = store.createDoc({ name: 'fuente.pdf', bytes: 5 }, 4);
  store.insertChunks(doc.id, [{ idx: 0, pageStart: 1, pageEnd: 1, text: 'hola', embedding: [1, 0] }]);
  store.markReady(doc.id, { chunks: 1 });
  const qa = store.saveQA({
    docId: doc.id, docName: doc.name, userId: 4, userEmail: 'c@lab.com',
    question: 'p', answer: 'r (pág. 1).', sources: [{ pageStart: 1, pageEnd: 1 }],
  });
  store.removeDoc(doc.id, 4);
  const still = store.listQA().find(x => x.id === qa.id);
  assert.ok(still, 'Q&A entry is kept');
  assert.equal(still.docName, 'fuente.pdf', 'document name preserved for reference');
});
