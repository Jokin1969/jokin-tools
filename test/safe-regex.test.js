const { test } = require('node:test');
const assert = require('node:assert');
const { matchFilenames, PATTERN_MAX_LEN } = require('../apps/batchwork/server/safe-regex');

test('normal pattern extracts ids and separates non-matches', async () => {
  const { withId, noId } = await matchFilenames('\\d{8}[A-Za-z]', ['12345678A_x.pdf', 'sindni.docx', '87654321Z.pdf']);
  assert.equal(withId.length, 2);
  assert.equal(noId.length, 1);
  assert.deepEqual(withId.map(w => w.id).sort(), ['12345678A', '87654321Z']);
});

test('invalid regex rejects with status 400', async () => {
  await assert.rejects(() => matchFilenames('(', ['a.pdf']), (e) => e.status === 400);
});

test('over-long pattern rejected before running', async () => {
  await assert.rejects(() => matchFilenames('a'.repeat(PATTERN_MAX_LEN + 1), ['a.pdf']), (e) => e.status === 400);
});

test('catastrophic-backtracking pattern is killed by timeout, not the event loop', async () => {
  let ticks = 0;
  const ticker = setInterval(() => { ticks++; }, 50);
  const t0 = Date.now();
  await assert.rejects(
    () => matchFilenames('(a+)+$', ['a'.repeat(40) + '!']),
    (e) => e.status === 400,
  );
  const dt = Date.now() - t0;
  clearInterval(ticker);
  assert.ok(dt < 5000, `aborted in ${dt}ms`);
  assert.ok(ticks >= 5, `event loop stayed alive (${ticks} ticks during ReDoS)`);
});
