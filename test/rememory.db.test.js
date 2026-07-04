const { test } = require('node:test');
const assert = require('node:assert');
const { useTempDb, makeUser } = require('./helpers');

useTempDb();
const store = require('../apps/auth/store');
const rm = require('../apps/re-memory/db');

const A = makeUser(store, 'a@test.com');
const B = makeUser(store, 'b@test.com');

test('createMemory + getMemoryById scoped to owner', () => {
  const m = rm.createMemory({ description: 'capital de Francia', frequency: '1m', topic: 'Geografía', user_id: A.id });
  assert.ok(m.id);
  assert.ok(rm.getMemoryById(m.id, A.id), 'owner can read');
  assert.equal(rm.getMemoryById(m.id, B.id), null, 'non-owner cannot read');
});

test('listMemories is per-user', () => {
  // A already has 1 from previous test; add one for B
  rm.createMemory({ description: 'B memory', frequency: '1w', topic: 'Ciencia', user_id: B.id });
  assert.equal(rm.listMemories({}, A.id).total, 1);
  assert.equal(rm.listMemories({}, B.id).total, 1);
});

test('updateMemory cannot set image_path (only setMemoryImage can)', () => {
  const m = rm.createMemory({ description: 'with image attempt', frequency: '1m', topic: 'Historia', user_id: A.id });
  const updated = rm.updateMemory(m.id, { description: 'edited', image_path: 'memory-of-someone-else.png' }, A.id);
  assert.equal(updated.description, 'edited');
  assert.equal(updated.image_path, null, 'image_path must NOT be settable via generic update');

  rm.setMemoryImage(m.id, 'memory-legit.png', A.id);
  assert.equal(rm.getMemoryById(m.id, A.id).image_path, 'memory-legit.png');
});

test('getImageOwner resolves the owning user', () => {
  const m = rm.createMemory({ description: 'owns an image', frequency: '1m', topic: 'Arte', user_id: A.id });
  rm.setMemoryImage(m.id, 'memory-unique-xyz.png', A.id);
  assert.equal(rm.getImageOwner('memory-unique-xyz.png'), A.id);
  assert.equal(rm.getImageOwner('does-not-exist.png'), null);
});

test('deleteMemory and toggle are owner-scoped', () => {
  const m = rm.createMemory({ description: 'to delete', frequency: '1m', topic: 'Otro', user_id: A.id });
  rm.deleteMemory(m.id, B.id);                 // B tries — should not delete
  assert.ok(rm.getMemoryById(m.id, A.id), 'still there after B delete attempt');
  rm.deleteMemory(m.id, A.id);                 // owner deletes
  assert.equal(rm.getMemoryById(m.id, A.id), null);
});

test('calcNextSendDate returns a valid future ISO date', () => {
  const iso = rm.calcNextSendDate('1m');
  assert.ok(!Number.isNaN(Date.parse(iso)), 'parseable ISO');
  assert.throws(() => rm.calcNextSendDate('bogus'), /frequency/i);
});

// ─── Activity history ─────────────────────────────────────────────────────────
test('historial: createMemory registra "created"', () => {
  const m = rm.createMemory({ description: 'hist', frequency: '1w', topic: 'T', user_id: A.id });
  assert.ok(rm.listHistory(m.id, A.id).some(e => e.type === 'created'));
});

test('historial: cambio de frecuencia registra antes → después', () => {
  const m = rm.createMemory({ description: 'freq', frequency: '1w', topic: 'T', user_id: A.id });
  rm.updateMemory(m.id, { frequency: '2m' }, A.id);
  const fc = rm.listHistory(m.id, A.id).find(e => e.type === 'freq_changed');
  assert.ok(fc);
  assert.equal(fc.detail, '1 semana → 2 meses');
});

test('historial: toggle registra desactivada/reactivada; reset registra reset', () => {
  const m = rm.createMemory({ description: 'tg', frequency: '1w', topic: 'T', user_id: A.id });
  rm.toggleMemory(m.id, A.id);
  rm.toggleMemory(m.id, A.id);
  rm.resetCounter(m.id, A.id);
  const types = rm.listHistory(m.id, A.id).map(e => e.type);
  assert.ok(types.includes('deactivated'));
  assert.ok(types.includes('reactivated'));
  assert.ok(types.includes('reset'));
});

test('historial: markSent aparece como envío', () => {
  const m = rm.createMemory({ description: 'sent', frequency: '1w', topic: 'T', user_id: A.id });
  rm.markSent(m.id, '1w');
  assert.ok(rm.listHistory(m.id, A.id).some(e => e.type === 'sent'));
});

test('historial: es por dueño (otro usuario no lo ve)', () => {
  const m = rm.createMemory({ description: 'scoped', frequency: '1w', topic: 'T', user_id: A.id });
  assert.ok(rm.listHistory(m.id, A.id).length > 0);
  assert.equal(rm.listHistory(m.id, B.id).length, 0);
});

test('backfillCreatedEvents repone "created" faltantes', () => {
  const m = rm.createMemory({ description: 'bf', frequency: '1w', topic: 'T', user_id: A.id });
  rm.db.prepare('DELETE FROM memory_events WHERE memory_id = ?').run(m.id);
  assert.equal(rm.listHistory(m.id, A.id).length, 0);
  assert.ok(rm.backfillCreatedEvents() >= 1);
  assert.ok(rm.listHistory(m.id, A.id).some(e => e.type === 'created'));
});
