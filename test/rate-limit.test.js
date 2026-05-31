const { test } = require('node:test');
const assert = require('node:assert');
const { rateLimit } = require('../apps/auth/rate-limit');

// Minimal fake req/res to drive the middleware.
function run(mw, ip) {
  let status = 200, body = null, nexted = false;
  const req = { ip, get: () => undefined, connection: {} };
  const res = {
    set() { return this; },
    status(c) { status = c; return this; },
    json(b) { body = b; return this; },
  };
  mw(req, res, () => { nexted = true; });
  return { status, body, nexted };
}

test('allows up to max, then blocks with 429', () => {
  const mw = rateLimit({ windowMs: 60000, max: 3 });
  assert.equal(run(mw, '1.1.1.1').nexted, true);
  assert.equal(run(mw, '1.1.1.1').nexted, true);
  assert.equal(run(mw, '1.1.1.1').nexted, true);
  const fourth = run(mw, '1.1.1.1');
  assert.equal(fourth.nexted, false);
  assert.equal(fourth.status, 429);
});

test('limits are per-key (per IP)', () => {
  const mw = rateLimit({ windowMs: 60000, max: 1 });
  assert.equal(run(mw, '2.2.2.2').nexted, true);
  assert.equal(run(mw, '2.2.2.2').nexted, false, 'second from same IP blocked');
  assert.equal(run(mw, '3.3.3.3').nexted, true, 'different IP unaffected');
});
