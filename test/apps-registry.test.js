const { test } = require('node:test');
const assert = require('node:assert');
const { useTempDb } = require('./helpers');

useTempDb();
const store = require('../apps/auth/store');
const reg = require('../apps/auth/apps-registry');

// ── Feature helpers ─────────────────────────────────────────────────────────────
test('isFeatureId only accepts known app/feature pairs', () => {
  assert.equal(reg.isFeatureId('batchwork/qr'), true);
  assert.equal(reg.isFeatureId('batchwork/lab'), true);
  assert.equal(reg.isFeatureId('batchwork/nope'), false);
  assert.equal(reg.isFeatureId('asignacion/qr'), false);   // app has no features
  assert.equal(reg.isFeatureId('batchwork'), false);       // not scoped
  assert.equal(reg.isFeatureId('foo/qr'), false);
});

test('featuresForUser: admin and full users get every feature', () => {
  const all = reg.featureIds('batchwork');
  assert.deepEqual(reg.featuresForUser({ role: 'admin', apps: '*' }, 'batchwork').sort(), all.slice().sort());
  // base app, no scopes → legacy full access
  assert.deepEqual(reg.featuresForUser({ role: 'user', apps: ['batchwork'] }, 'batchwork').sort(), all.slice().sort());
});

test('featuresForUser: scoped ids restrict to the listed subset', () => {
  const u = { role: 'user', apps: ['batchwork', 'batchwork/qr', 'batchwork/lab'] };
  assert.deepEqual(reg.featuresForUser(u, 'batchwork').sort(), ['lab', 'qr']);
});

test('featuresForUser: no app access → no features', () => {
  assert.deepEqual(reg.featuresForUser({ role: 'user', apps: ['asignacion'] }, 'batchwork'), []);
});

test('canAccessFeature honours scopes and base access', () => {
  const restricted = { role: 'user', apps: ['batchwork', 'batchwork/qr'] };
  assert.equal(reg.canAccessFeature(restricted, 'batchwork', 'qr'), true);
  assert.equal(reg.canAccessFeature(restricted, 'batchwork', 'lab'), false);

  const full = { role: 'user', apps: ['batchwork'] };
  assert.equal(reg.canAccessFeature(full, 'batchwork', 'lab'), true);

  const none = { role: 'user', apps: ['asignacion'] };
  assert.equal(reg.canAccessFeature(none, 'batchwork', 'qr'), false);

  // An app without features falls back to plain app access.
  assert.equal(reg.canAccessFeature({ role: 'user', apps: ['asignacion'] }, 'asignacion', 'x'), true);
  assert.equal(reg.canAccessFeature({ role: 'user', apps: ['batchwork'] }, 'asignacion', 'x'), false);
});

test('appsMeta exposes features for batchwork and none for the rest', () => {
  const meta = reg.appsMeta();
  const bw = meta.find(a => a.id === 'batchwork');
  assert.ok(bw.features.length >= 8, 'batchwork carries its feature groups');
  const asig = meta.find(a => a.id === 'asignacion');
  assert.deepEqual(asig.features, []);
});

// ── Persistence: scoped ids survive the store round-trip ────────────────────────
test('store keeps scoped app ids and canAccessFeature reads them back', () => {
  const u = store.createUser({
    email: 'restricted@example.com', name: 'R', password: 'password1',
    apps: ['batchwork', 'batchwork/document', 'batchwork/stamp'],
  });
  assert.ok(u.apps.includes('batchwork'));
  assert.ok(u.apps.includes('batchwork/document'));
  assert.equal(reg.canAccessFeature(u, 'batchwork', 'document'), true);
  assert.equal(reg.canAccessFeature(u, 'batchwork', 'qr'), false);

  // Widening back to full (drop all scopes) restores every tool.
  const u2 = store.updateUser(u.id, { apps: ['batchwork'] });
  assert.equal(reg.canAccessFeature(u2, 'batchwork', 'qr'), true);
});
