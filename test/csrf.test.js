const { test } = require('node:test');
const assert = require('node:assert');
const { useTempDb } = require('./helpers');

useTempDb();
const { csrfGuard } = require('../apps/auth/middleware');

// Build a fake req/res. headers keyed lowercase; get() mimics Express.
function run({ method = 'POST', origin, referer, host = 'app.example.com', proto = 'https' }) {
  const headers = { host };
  if (origin !== undefined) headers.origin = origin;
  if (referer !== undefined) headers.referer = referer;
  let status = 200, body = null, nexted = false;
  const req = {
    method, protocol: proto,
    get: (h) => headers[h.toLowerCase()],
  };
  const res = { status(c) { status = c; return this; }, json(b) { body = b; return this; } };
  csrfGuard(req, res, () => { nexted = true; });
  return { status, nexted };
}

test('GET is never blocked', () => {
  assert.equal(run({ method: 'GET', origin: 'https://evil.example' }).nexted, true);
});

test('same-origin POST passes', () => {
  assert.equal(run({ origin: 'https://app.example.com' }).nexted, true);
});

test('cross-origin POST is blocked (403)', () => {
  const r = run({ origin: 'https://evil.example' });
  assert.equal(r.nexted, false);
  assert.equal(r.status, 403);
});

test('POST with no Origin/Referer passes (non-browser client)', () => {
  assert.equal(run({}).nexted, true);
});

test('Referer fallback is honoured', () => {
  assert.equal(run({ referer: 'https://app.example.com/page' }).nexted, true);
  assert.equal(run({ referer: 'https://evil.example/page' }).nexted, false);
});
