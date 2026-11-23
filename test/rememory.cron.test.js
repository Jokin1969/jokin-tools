const { test } = require('node:test');
const assert = require('node:assert');
const { useTempDb, makeUser } = require('./helpers');

useTempDb();
const store = require('../apps/auth/store');
const rm = require('../apps/re-memory/db');
const { runSendJob } = require('../apps/re-memory/cron');

const U = makeUser(store, 'cron@test.com');

function dueMemory(description) {
  const m = rm.createMemory({ description, frequency: '1w', topic: 'Ciencia', user_id: U.id });
  rm.db.prepare("UPDATE memories SET next_send_date = datetime('now', '-1 day') WHERE id = ?").run(m.id);
  return m.id;
}

function isScheduledInFuture(id) {
  return rm.db.prepare("SELECT next_send_date > datetime('now') AS f FROM memories WHERE id = ?").get(id).f === 1;
}

function fakeMail() {
  const calls = { memory: [], quiz: [] };
  return {
    calls,
    sendMemoryEmail: async (m) => { calls.memory.push(m.id); },
    sendQuizEmail: async (m, to, token) => { calls.quiz.push({ id: m.id, token }); },
  };
}

test('createQuiz inserta: la clave foránea de quizzes no puede romper la inserción', () => {
  const id = dueMemory('quiz insert');
  const q = rm.createQuiz(id, U.id);
  assert.ok(q.id);
  rm.markSent(id, '1w');
});

test('si el cuestionario falla, el recordatorio normal SALE y la ficha se marca como enviada', async () => {
  const id = dueMemory('quiz falla');
  const mail = fakeMail();
  const r = await runSendJob({
    maxPerRun: 10,
    deps: { ...mail, generateQuizQuestions: async () => { throw new Error('IA caída'); } },
  });
  assert.deepEqual(mail.calls.memory, [id]);
  assert.equal(r.sent, 1);
  assert.equal(r.failed, 0);
  assert.match(r.details[0].quiz_error, /IA caída/);
  assert.ok(isScheduledInFuture(id), 'next_send_date debe avanzar');
});

test('con el cuestionario funcionando, sale el email de cuestionario', async () => {
  const id = dueMemory('quiz ok');
  const mail = fakeMail();
  const r = await runSendJob({ maxPerRun: 10, deps: { ...mail, generateQuizQuestions: async () => {} } });
  assert.equal(mail.calls.quiz.length, 1);
  assert.equal(mail.calls.quiz[0].id, id);
  assert.equal(mail.calls.memory.length, 0);
  assert.equal(r.details[0].type, 'quiz');
  assert.ok(isScheduledInFuture(id));
});

test('si el SMTP falla, la ficha NO se marca y la ejecución queda registrada con el motivo', async () => {
  const id = dueMemory('smtp falla');
  const boom = async () => { throw new Error('SMTP rechazado'); };
  const r = await runSendJob({
    maxPerRun: 10, trigger: 'manual',
    deps: { sendMemoryEmail: boom, sendQuizEmail: boom, generateQuizQuestions: async () => {} },
  });
  assert.equal(r.sent, 0);
  assert.equal(r.failed, 1);
  assert.ok(!isScheduledInFuture(id), 'sigue pendiente para el siguiente turno');

  const [last] = rm.listCronRuns(1);
  assert.equal(last.trigger, 'manual');
  assert.equal(last.failed, 1);
  assert.match(last.details[0].error, /SMTP rechazado/);
  rm.markSent(id, '1w');
});
