const { test, beforeEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { useTempDb } = require('./helpers');

useTempDb();
const db = require('../apps/imprimir/db');

// Tests share one DB within this process; start each from an empty queue so
// FIFO/count assertions are deterministic.
beforeEach(() => { db.db.prepare('DELETE FROM print_jobs').run(); });

const STORAGE = fs.mkdtempSync(path.join(os.tmpdir(), 'impr-db-'));
let counter = 0;
function makeJob(over = {}) {
  counter++;
  const file = path.join(STORAGE, `job${counter}.pdf`);
  fs.writeFileSync(file, Buffer.from('%PDF-1.4 job ' + counter));
  return db.enqueueJob({
    message_id: over.message_id || `<m${counter}@x>`,
    part_idx: over.part_idx || 0,
    sender: 'castilla@joaquincastilla.com',
    subject: 'S' + counter,
    filename: `doc${counter}.pdf`,
    mime: 'application/pdf',
    printer: '\\\\cicpri042\\Color',
    size_bytes: 10,
    file_path: file,
    ...over,
  });
}

test('enqueue + counts + jobExists', () => {
  const j = makeJob();
  assert.equal(j.status, 'queued');
  assert.ok(db.jobExists(j.message_id, 0));
  assert.equal(db.jobExists('<no-existe@x>', 0), false);
  assert.equal(db.counts().queued, 1);
});

test('claimNextJob es FIFO, marca printing y suma attempts', () => {
  const a = makeJob();
  const b = makeJob();
  const first = db.claimNextJob();
  assert.equal(first.id, a.id, 'coge el más antiguo primero');
  assert.equal(first.status, 'printing');
  assert.equal(first.attempts, 1);
  const second = db.claimNextJob();
  assert.equal(second.id, b.id);
});

test('markDone y markFailed', () => {
  const j = makeJob();
  const claimed = db.claimNextJob();
  assert.ok(db.markDone(claimed.id));
  const done = db.getJob(claimed.id);
  assert.equal(done.status, 'done');
  assert.ok(done.printed_at, 'printed_at se rellena');

  const k = makeJob();
  const c2 = db.claimNextJob();
  assert.ok(db.markFailed(c2.id, 'impresora offline'));
  const failed = db.getJob(c2.id);
  assert.equal(failed.status, 'failed');
  assert.equal(failed.error, 'impresora offline');
});

test('requeueJob reencola un trabajo terminado (reimprimir)', () => {
  const j = makeJob();
  const claimed = db.claimNextJob();
  db.markFailed(claimed.id, 'sin papel');
  assert.equal(db.getJob(j.id).status, 'failed');
  assert.ok(db.requeueJob(j.id));
  const back = db.getJob(j.id);
  assert.equal(back.status, 'queued');
  assert.equal(back.error, null);
  assert.equal(back.attempts, 0);
});

test('requeueStale devuelve a la cola trabajos printing viejos', () => {
  const j = makeJob();
  db.claimNextJob();                       // → printing, attempts 1
  // Envejecer el created_at a hace 1 hora.
  db.db.prepare("UPDATE print_jobs SET created_at = datetime('now','-60 minutes') WHERE id = ?").run(j.id);
  const n = db.requeueStale(3, 10);        // attempts<3 y >10 min
  assert.ok(n >= 1);
  assert.equal(db.getJob(j.id).status, 'queued');
});

test('deleteJob borra el trabajo y su fichero', () => {
  const j = makeJob();
  const file = j.file_path;
  assert.ok(fs.existsSync(file));
  assert.ok(db.deleteJob(j.id));
  assert.equal(db.getJob(j.id), undefined);
  assert.equal(fs.existsSync(file), false);
  assert.equal(db.deleteJob(999999), false, 'id inexistente → false');
});

test('clearDone borra solo los done (deja queued/failed)', () => {
  const a = makeJob(); db.claimNextJob(); db.markDone(a.id);   // done
  const b = makeJob();                                          // queued
  const c = makeJob(); db.claimNextJob(); db.markFailed(c.id, 'x'); // failed
  const removed = db.clearDone();
  assert.ok(removed >= 1);
  assert.equal(db.getJob(a.id), undefined, 'el done se borró');
  assert.ok(db.getJob(b.id), 'el queued sigue');
  assert.ok(db.getJob(c.id), 'el failed sigue');
});

test('settings: impresora por defecto persiste hasta cambiarla', () => {
  db.db.prepare('DELETE FROM imprimir_settings').run();
  assert.equal(db.getDefaultPrinter(), null);
  db.setDefaultPrinter('\\\\cicpri042\\Color');
  assert.equal(db.getDefaultPrinter(), '\\\\cicpri042\\Color');
  db.setDefaultPrinter('');                     // vaciar → vuelve a null
  assert.equal(db.getDefaultPrinter(), null);
});

test('settings: impresoras reportadas (dedup + merge de reportes)', () => {
  db.db.prepare('DELETE FROM imprimir_settings').run();
  db.reportPrinters(['A', 'B', 'A'], '2026-07-02T10:00:00Z');
  assert.deepEqual(db.getKnownPrinters().map(p => p.name).sort(), ['A', 'B']);
  db.reportPrinters(['B', 'C'], '2026-07-02T11:00:00Z');
  assert.deepEqual(db.getKnownPrinters().map(p => p.name).sort(), ['A', 'B', 'C']); // A se conserva
});

test('purgeOld borra trabajos terminados y sus ficheros', () => {
  const j = makeJob();
  const claimed = db.claimNextJob();
  db.markDone(claimed.id);
  const file = db.getJob(j.id).file_path;
  assert.ok(fs.existsSync(file));
  // Envejecer para superar el umbral (en producción son días).
  db.db.prepare("UPDATE print_jobs SET created_at = datetime('now','-2 days') WHERE id = ?").run(j.id);
  const removed = db.purgeOld(0);          // umbral 0 → borra lo terminado
  assert.ok(removed >= 1);
  assert.equal(db.getJob(j.id), undefined, 'la fila se eliminó');
  assert.equal(fs.existsSync(file), false, 'el fichero se eliminó');
});
