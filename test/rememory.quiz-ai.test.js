const { test } = require('node:test');
const assert = require('node:assert');
const { useTempDb, makeUser } = require('./helpers');

useTempDb();
process.env.ANTHROPIC_API_KEY = 'test';

// SDK falso: devuelve como texto lo que haya en `reply`.
let reply = null;
const sdkPath = require.resolve('@anthropic-ai/sdk');
require.cache[sdkPath] = {
  id: sdkPath, filename: sdkPath, loaded: true,
  exports: class { constructor() { this.messages = { create: async () => ({ content: [{ type: 'text', text: JSON.stringify(reply) }] }) }; } },
};

const store = require('../apps/auth/store');
const rm = require('../apps/re-memory/db');
const { generateQuizQuestions } = require('../apps/re-memory/quiz-ai');

const U = makeUser(store, 'ai@test.com');
function newQuiz() {
  const m = rm.createMemory({ description: 'París es la capital de Francia', frequency: '1m', topic: 'Geografía', user_id: U.id });
  return rm.createQuiz(m.id, U.id);
}
const pregunta = (correct) => ({ question: '¿Capital de Francia?', options: ['Roma', 'París', 'Berlín', 'Lyon'], correct_answer: correct, explanation: 'x' });

test('una correcta escrita distinto («paris») se guarda con el texto de la opción («París»)', async () => {
  const q = newQuiz();
  reply = { questions: [pregunta('paris'), pregunta('París')] };
  await generateQuizQuestions(q.id, 'd', 't', 'mixed', 2);
  assert.deepEqual(rm.getQuizQuestions(q.id).map(x => x.correct_answer), ['París', 'París']);
});

test('si la correcta no es ninguna opción, falla y NO deja preguntas a medias', async () => {
  const q = newQuiz();
  reply = { questions: [pregunta('París'), pregunta('Madrid')] };
  await assert.rejects(generateQuizQuestions(q.id, 'd', 't', 'mixed', 2), /ninguna de las opciones/);
  assert.equal(rm.getQuizQuestions(q.id).length, 0);
});
