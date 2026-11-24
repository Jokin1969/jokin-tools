const { test, before, after } = require('node:test');
const assert = require('node:assert');
const { useTempDb, makeUser } = require('./helpers');

useTempDb();
const store = require('../apps/auth/store');
const rm = require('../apps/re-memory/db');
const app = require('../server');

let base, server, cookie, user;
before(async () => {
  await new Promise(r => { server = app.listen(0, r); });
  base = `http://127.0.0.1:${server.address().port}`;
  user = makeUser(store, 'quiz@test.com');
  cookie = `jt_sid=${store.createSession(user.id).sid}`;
});
after(() => { try { server.close(); } catch { /* ignore */ } });

const get = (p) => fetch(base + p, { headers: { Cookie: cookie } });
const post = (p, body) => fetch(base + p, {
  method: 'POST', headers: { Cookie: cookie, 'Content-Type': 'application/json' }, body: JSON.stringify(body),
});

// Cuestionario como lo deja quiz-ai: preguntas con 4 opciones y la correcta guardada aparte.
function makeQuiz(topic, items) {
  const m = rm.createMemory({ description: `ficha de ${topic}`, frequency: '1m', topic, user_id: user.id });
  const quiz = rm.createQuiz(m.id, user.id);
  const ids = items.map((it, i) => {
    const qid = rm.addQuizQuestion(quiz.id, { question: it.q, order_num: i + 1, correct_answer: it.ok, explanation: `porque ${it.ok}` });
    it.opts.forEach((o, j) => rm.addQuizOption(qid, o, j + 1));
    return qid;
  });
  return { ...quiz, ids };
}

const DOS = [
  { q: '¿Capital de Francia?', ok: 'París', opts: ['Roma', 'París', 'Berlín', 'Lyon'] },
  { q: '¿Año de Lepanto?', ok: '1571', opts: ['1492', '1571', '1588', '1600'] },
];

test('la página del cuestionario carga su script (lo que pide el navegador, no lo que suponemos)', async () => {
  const html = await (await get('/re-memory/quiz?token=x')).text();
  const srcs = [...html.matchAll(/<script[^>]+src="([^"]+)"/g)].map(m => m[1]).filter(s => s.startsWith('/re-memory'));
  assert.ok(srcs.length, 'la página referencia un script propio');
  for (const src of srcs) {
    const r = await get(src);
    assert.equal(r.status, 200, `${src} debe existir`);
    assert.match(r.headers.get('content-type'), /javascript/);
  }
});

test('GET del cuestionario devuelve las preguntas SIN la respuesta correcta', async () => {
  const q = makeQuiz('Geografía', structuredClone(DOS));
  const r = await get(`/re-memory/api/quiz/${q.token}`);
  assert.equal(r.status, 200);
  const data = await r.json();
  assert.equal(data.status, 'pending');
  assert.equal(data.questions.length, 2);
  assert.deepEqual(data.questions[0].options.map(o => o.text), DOS[0].opts);
  assert.ok(!JSON.stringify(data).includes('porque'), 'no filtra explicaciones');
  assert.ok(!('correct_answer' in data.questions[0]));
});

test('enviar: puntúa sobre el TOTAL de preguntas, ignora preguntas ajenas y actualiza estadísticas', async () => {
  const otro = makeQuiz('Otro', structuredClone(DOS));
  const q = makeQuiz('Historia', structuredClone(DOS));
  const r = await post(`/re-memory/api/quiz/${q.token}/submit`, {
    answers: [
      { question_id: q.ids[0], answer: 'París' },
      { question_id: otro.ids[1], answer: '1571' },
    ],
  });
  assert.equal(r.status, 200);
  const res = await r.json();
  assert.equal(res.status, 'completed');
  assert.equal(res.score, 50, '1 de 2: la no contestada cuenta como fallo');
  assert.deepEqual(res.results.map(x => x.question), DOS.map(d => d.q), 'en el orden de las preguntas');
  assert.equal(res.results[1].user_answer, null);
  assert.equal(res.results[1].correct_answer, '1571');
  assert.equal(res.results[1].explanation, 'porque 1571');
  assert.equal(rm.getQuizStats(user.id, 'Historia').total_quizzes, 1);
});

test('reenviar o reabrir el enlace enseña la nota guardada y no cuenta dos veces', async () => {
  const q = makeQuiz('Ciencia', structuredClone(DOS));
  const all = { answers: [{ question_id: q.ids[0], answer: 'París' }, { question_id: q.ids[1], answer: '1571' }] };
  assert.equal((await (await post(`/re-memory/api/quiz/${q.token}/submit`, all)).json()).score, 100);
  const again = await (await post(`/re-memory/api/quiz/${q.token}/submit`, { answers: [] })).json();
  assert.equal(again.score, 100);
  const reopen = await (await get(`/re-memory/api/quiz/${q.token}`)).json();
  assert.equal(reopen.status, 'completed');
  assert.equal(reopen.score, 100);
  assert.equal(rm.getQuizStats(user.id, 'Ciencia').total_quizzes, 1);
});

test('token desconocido → 404', async () => {
  assert.equal((await get(`/re-memory/api/quiz/${'0'.repeat(64)}`)).status, 404);
});

test('ajustes, estadísticas e historial no quedan tapados por la ruta del token', async () => {
  for (const p of ['settings', 'stats', 'history']) {
    const r = await get(`/re-memory/api/quiz/${p}`);
    assert.notEqual(r.status, 404, p);
    const data = await r.json();
    assert.notEqual(data.error, 'Cuestionario no encontrado', p);
  }
});
