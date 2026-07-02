const { test, before, after } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { useTempDb } = require('./helpers');

const tmp = useTempDb();
process.env.IMPRIMIR_AGENT_KEY = 'testkey123';
process.env.IMPRIMIR_SUBMIT_KEY = 'submitkey456';
process.env.IMPRIMIR_DEFAULT_PRINTER = '\\\\cicpri042\\Color';
process.env.IMPRIMIR_DIR = path.join(tmp.dir, 'impr');
process.env.IMPRIMIR_ENABLED = 'false'; // no IMAP poll during tests

const app = require('../server');           // require.main !== module ⇒ no listen/cron
const db = require('../apps/imprimir/db');
const store = require('../apps/auth/store');
const { makeUser } = require('./helpers');

let base, server, seq = 0, adminCookie = '';
before(async () => {
  await new Promise((r) => { server = app.listen(0, r); });
  base = `http://127.0.0.1:${server.address().port}`;
  const admin = makeUser(store, 'admin@test.com', 'admin');
  const { sid } = store.createSession(admin.id);
  adminCookie = `jt_sid=${sid}`;
});
after(() => { try { server.close(); } catch { /* ignore */ } });

function enqueueSample() {
  seq++;
  const dir = process.env.IMPRIMIR_DIR;
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `sample${seq}.pdf`);
  fs.writeFileSync(file, Buffer.from('%PDF-1.4 sample ' + seq));
  return db.enqueueJob({
    message_id: `<rt${seq}@x>`, part_idx: 0,
    sender: 'castilla@joaquincastilla.com', subject: 'Hola',
    filename: `sample${seq}.pdf`, mime: 'application/pdf',
    printer: '\\\\cicpri042\\Color', size_bytes: 16, file_path: file,
  });
}

test('health responde sin API key', async () => {
  const r = await fetch(base + '/imprimir/api/health');
  const j = await r.json();
  assert.equal(r.status, 200);
  assert.equal(j.ok, true);
});

test('jobs/next sin API key → 401', async () => {
  const r = await fetch(base + '/imprimir/api/jobs/next');
  assert.equal(r.status, 401);
});

test('jobs/next con API key incorrecta → 401', async () => {
  const r = await fetch(base + '/imprimir/api/jobs/next', { headers: { 'X-Api-Key': 'mala' } });
  assert.equal(r.status, 401);
});

test('flujo del agente: next (con PDF) → done', async () => {
  const job = enqueueSample();
  const r = await fetch(base + '/imprimir/api/jobs/next', { headers: { 'X-Api-Key': 'testkey123' } });
  assert.equal(r.status, 200);
  const { job: got } = await r.json();
  assert.equal(got.id, job.id);
  assert.equal(got.printer, '\\\\cicpri042\\Color');
  assert.equal(Buffer.from(got.pdf_base64, 'base64').toString(), '%PDF-1.4 sample ' + seq);
  assert.equal(db.getJob(job.id).status, 'printing');

  const d = await fetch(base + `/imprimir/api/jobs/${job.id}/done`, {
    method: 'POST', headers: { 'X-Api-Key': 'testkey123' },
  });
  assert.equal(d.status, 200);
  assert.equal(db.getJob(job.id).status, 'done');

  const r2 = await fetch(base + '/imprimir/api/jobs/next', { headers: { 'X-Api-Key': 'testkey123' } });
  assert.equal((await r2.json()).job, null, 'cola vacía tras imprimir');
});

test('flujo del agente: failed marca error', async () => {
  const job = enqueueSample();
  await fetch(base + '/imprimir/api/jobs/next', { headers: { 'X-Api-Key': 'testkey123' } });
  const f = await fetch(base + `/imprimir/api/jobs/${job.id}/failed`, {
    method: 'POST', headers: { 'X-Api-Key': 'testkey123', 'Content-Type': 'application/json' },
    body: JSON.stringify({ error: 'impresora sin papel' }),
  });
  assert.equal(f.status, 200);
  const row = db.getJob(job.id);
  assert.equal(row.status, 'failed');
  assert.equal(row.error, 'impresora sin papel');
});

test('submit: sin clave → 401', async () => {
  const fd = new FormData();
  fd.append('file', new Blob([Buffer.from('%PDF-1.4 x')], { type: 'application/pdf' }), 'x.pdf');
  const r = await fetch(base + '/imprimir/api/submit', { method: 'POST', body: fd });
  assert.equal(r.status, 401);
});

test('submit: otra app envía un PDF y entra en la cola', async () => {
  const fd = new FormData();
  fd.append('file', new Blob([Buffer.from('%PDF-1.4 hola cola')], { type: 'application/pdf' }), 'desde_otra_app.pdf');
  fd.append('source', 'research-tools');
  fd.append('printer', 'OtraImpresora');
  const r = await fetch(base + '/imprimir/api/submit', { method: 'POST', headers: { 'X-Api-Key': 'submitkey456' }, body: fd });
  assert.equal(r.status, 200);
  const d = await r.json();
  assert.ok(d.ok && d.id);
  const job = db.getJob(d.id);
  assert.equal(job.status, 'queued');
  assert.equal(job.filename, 'desde_otra_app.pdf');
  assert.equal(job.sender, 'research-tools');
  assert.equal(job.printer, 'OtraImpresora', 'respeta la impresora indicada por la app');
  assert.equal(fs.readFileSync(job.file_path).slice(0, 5).toString(), '%PDF-');
});

test('submit: tipo no soportado → 400', async () => {
  const fd = new FormData();
  fd.append('file', new Blob([Buffer.from('hola')], { type: 'text/plain' }), 'nota.txt');
  const r = await fetch(base + '/imprimir/api/submit', { method: 'POST', headers: { 'X-Api-Key': 'submitkey456' }, body: fd });
  assert.equal(r.status, 400);
});

test('impresoras: el agente reporta y la app las lista', async () => {
  const rep = await fetch(base + '/imprimir/api/agent/printers', {
    method: 'POST', headers: { 'X-Api-Key': 'testkey123', 'Content-Type': 'application/json' },
    body: JSON.stringify({ printers: ['Color en cicpri042', 'Microsoft Print to PDF'] }),
  });
  assert.equal(rep.status, 200);
  const r = await fetch(base + '/imprimir/api/printers', { headers: { 'X-Api-Key': 'submitkey456' } });
  assert.equal(r.status, 200);
  const d = await r.json();
  assert.ok(d.known.includes('Microsoft Print to PDF'));
});

test('impresoras: fijar default es admin (401 sin sesión, ok con admin)', async () => {
  const no = await fetch(base + '/imprimir/api/printers/default', {
    method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ printer: 'Microsoft Print to PDF' }),
  });
  assert.equal(no.status, 401);
  const ok = await fetch(base + '/imprimir/api/printers/default', {
    method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json', Cookie: adminCookie },
    body: JSON.stringify({ printer: 'Microsoft Print to PDF' }),
  });
  assert.equal(ok.status, 200);
  assert.equal((await ok.json()).default, 'Microsoft Print to PDF');
});

test('submit sin printer usa el default persistente', async () => {
  db.setDefaultPrinter('MiDefault');
  const fd = new FormData();
  fd.append('file', new Blob([Buffer.from('%PDF-1.4 z')], { type: 'application/pdf' }), 'a.pdf');
  const r = await fetch(base + '/imprimir/api/submit', { method: 'POST', headers: { 'X-Api-Key': 'submitkey456' }, body: fd });
  const d = await r.json();
  assert.equal(db.getJob(d.id).printer, 'MiDefault');
  db.setDefaultPrinter('');
});

test('página de estado (admin): sin sesión → 401', async () => {
  const r = await fetch(base + '/imprimir/api/status', { headers: { Accept: 'application/json' } });
  assert.equal(r.status, 401);
});

test('página de estado (admin): cuentas + trabajos + config enmascarada + checklist', async () => {
  enqueueSample();
  const r = await fetch(base + '/imprimir/api/status', { headers: { Accept: 'application/json', Cookie: adminCookie } });
  assert.equal(r.status, 200);
  const d = await r.json();
  assert.ok(d.counts && typeof d.counts.queued === 'number');
  assert.ok(Array.isArray(d.jobs));
  // config visible, secretos enmascarados
  assert.equal(d.config.hasAgentKey, true);
  assert.ok(!('agentKey' in d.config), 'no filtra la API key');
  assert.equal(d.config.defaultPrinter, '\\\\cicpri042\\Color');
  assert.ok(Array.isArray(d.checklist) && d.checklist.length > 0);
  assert.ok('lastPollAt' in d.diag && 'lastAgentPullAt' in d.diag);
});

test('imap-test: sin sesión admin → 401', async () => {
  const r = await fetch(base + '/imprimir/api/diag/imap-test', { method: 'POST', headers: { Accept: 'application/json' } });
  assert.equal(r.status, 401);
});

test('imap-test: admin sin credenciales IMAP → ok:false sin reventar', async () => {
  const r = await fetch(base + '/imprimir/api/diag/imap-test', { method: 'POST', headers: { Accept: 'application/json', Cookie: adminCookie } });
  assert.equal(r.status, 200);
  const d = await r.json();
  assert.equal(d.ok, false);
  assert.match(d.error, /credenciales|usuario|contrase/i);
});

test('el agente que pide trabajo actualiza el heartbeat (lastAgentPullAt)', async () => {
  await fetch(base + '/imprimir/api/jobs/next', { headers: { 'X-Api-Key': 'testkey123' } });
  const r = await fetch(base + '/imprimir/api/status', { headers: { Accept: 'application/json', Cookie: adminCookie } });
  const d = await r.json();
  assert.ok(d.diag.lastAgentPullAt, 'se registra la última consulta del agente');
});

test('reimprimir (admin): reencola un trabajo terminado', async () => {
  const job = enqueueSample();
  // Marcarlo done directamente (determinista; no depende del FIFO de la cola).
  db.markDone(job.id);
  assert.equal(db.getJob(job.id).status, 'done');

  const r = await fetch(base + `/imprimir/api/jobs/${job.id}/reprint`, {
    method: 'POST', headers: { Accept: 'application/json', Cookie: adminCookie },
  });
  assert.equal(r.status, 200);
  assert.equal(db.getJob(job.id).status, 'queued');
});

test('borrar un trabajo (admin): 401 sin sesión, ok con admin', async () => {
  const job = enqueueSample();
  const no = await fetch(base + `/imprimir/api/jobs/${job.id}/delete`, { method: 'POST', headers: { Accept: 'application/json' } });
  assert.equal(no.status, 401);
  assert.ok(db.getJob(job.id), 'sigue existiendo tras el intento sin sesión');
  const ok = await fetch(base + `/imprimir/api/jobs/${job.id}/delete`, { method: 'POST', headers: { Accept: 'application/json', Cookie: adminCookie } });
  assert.equal(ok.status, 200);
  assert.equal(db.getJob(job.id), undefined, 'se borró');
});

test('limpiar realizados (admin) borra solo los done', async () => {
  const a = enqueueSample(); db.markDone(a.id);
  const b = enqueueSample(); // queued
  const r = await fetch(base + '/imprimir/api/jobs/clear-done', { method: 'POST', headers: { Accept: 'application/json', Cookie: adminCookie } });
  assert.equal(r.status, 200);
  assert.ok((await r.json()).removed >= 1);
  assert.equal(db.getJob(a.id), undefined, 'done borrado');
  assert.ok(db.getJob(b.id), 'queued conservado');
});

test('reimprimir sin sesión admin → 401', async () => {
  const job = enqueueSample();
  const r = await fetch(base + `/imprimir/api/jobs/${job.id}/reprint`, { method: 'POST', headers: { Accept: 'application/json' } });
  assert.equal(r.status, 401);
});
