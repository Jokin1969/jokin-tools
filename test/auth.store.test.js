const { test } = require('node:test');
const assert = require('node:assert');
const crypto = require('crypto');
const { useTempDb } = require('./helpers');

useTempDb();
const store = require('../apps/auth/store');

test('hashPassword → verifyPassword round-trip', () => {
  const h = store.hashPassword('correct horse battery');
  assert.ok(h.startsWith('scrypt$'));
  assert.equal(store.verifyPassword('correct horse battery', h), true);
  assert.equal(store.verifyPassword('wrong', h), false);
});

test('new hashes embed cost params and do not need rehash', () => {
  const h = store.hashPassword('whatever-long-pass');
  assert.equal(h.split('$').length, 6, 'format scrypt$N$r$p$salt$hash');
  assert.equal(store.needsRehash(h), false);
});

test('legacy hash verifies and is flagged for rehash', () => {
  // Legacy format: scrypt$salt$hash with Node defaults.
  const salt = crypto.randomBytes(16);
  const legacy = `scrypt$${salt.toString('hex')}$${crypto.scryptSync('legacypass123', salt, 64).toString('hex')}`;
  assert.equal(store.verifyPassword('legacypass123', legacy), true);
  assert.equal(store.verifyPassword('nope', legacy), false);
  assert.equal(store.needsRehash(legacy), true);
});

test('verifyPassword rejects malformed input safely', () => {
  assert.equal(store.verifyPassword('x', null), false);
  assert.equal(store.verifyPassword('x', ''), false);
  assert.equal(store.verifyPassword('x', 'not-a-hash'), false);
  assert.equal(store.verifyPassword('x', 'scrypt$onlyonepart'), false);
});

test('createUser validates email and password length', () => {
  assert.throws(() => store.createUser({ email: 'bad', password: 'longenough12' }), /Email/);
  assert.throws(() => store.createUser({ email: 'a@b.com', password: 'short' }), /8/);
  const u = store.createUser({ email: 'Valid@Test.com', password: 'longenough12', role: 'user', apps: 'bitacora' });
  assert.equal(u.email, 'valid@test.com', 'email normalised to lowercase');
  assert.equal(u.role, 'user');
});

test('duplicate email is rejected', () => {
  store.createUser({ email: 'dup@test.com', password: 'longenough12' });
  assert.throws(() => store.createUser({ email: 'dup@test.com', password: 'longenough12' }), /existe/i);
});

test('session lifecycle: create, fetch, destroy', () => {
  const u = store.createUser({ email: 'sess@test.com', password: 'longenough12' });
  const { sid } = store.createSession(u.id);
  assert.ok(sid && sid.length >= 32);
  const fetched = store.getSessionUser(sid);
  assert.equal(fetched.email, 'sess@test.com');
  store.destroySession(sid);
  assert.equal(store.getSessionUser(sid), null, 'destroyed session no longer resolves');
});

test('setPassword wipes existing sessions', () => {
  const u = store.createUser({ email: 'pw@test.com', password: 'longenough12' });
  const { sid } = store.createSession(u.id);
  assert.ok(store.getSessionUser(sid));
  store.setPassword(u.id, 'anotherlongpass');
  assert.equal(store.getSessionUser(sid), null, 'old session killed after password change');
});

test('countAdmins counts only active admins', () => {
  const before = store.countAdmins();
  store.createUser({ email: 'admin2@test.com', password: 'longenough12', role: 'admin' });
  assert.equal(store.countAdmins(), before + 1);
});
