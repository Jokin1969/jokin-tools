const { test } = require('node:test');
const assert = require('node:assert');
const express = require('express');
const { buildHelpPdf, handleHelpPdf } = require('../lib/help-pdf');

const SECTIONS = [
  { icon: '🚀', title: 'Qué es', html: '<p>Guarda <strong>personas</strong> y su <code>TIS</code> 😀, y un <span class="qt-chip-inline">❔ Ayuda</span>.</p><ol><li><b>Uno</b>: hazlo.</li><li>Dos.</li></ol>' },
  { icon: '💊', title: 'Plan', html: '<p>Tiene un <b>plan</b>.</p><div class="qt-note tip"><b>Dos formas:</b><ul><li><b>Catálogo</b>: por nombre.</li><li><b>CN</b>: pendiente.</li></ul>Luego caja.</div><div class="qt-note warn"><b>Ojo:</b> compara <code>&lt;persona&gt;</code> &amp; guarda.</div>' },
];

test('buildHelpPdf produces a valid PDF buffer', async () => {
  const buf = await buildHelpPdf({ title: 'Manual de prueba', subtitle: 'Sub', appLabel: 'QR (TIS)', sections: SECTIONS, dateLabel: '23 de agosto de 2026' });
  assert.ok(Buffer.isBuffer(buf) && buf.length > 800, 'devuelve un buffer no trivial');
  assert.equal(buf.slice(0, 5).toString('latin1'), '%PDF-', 'empieza por la cabecera PDF');
  assert.ok(buf.slice(-1024).toString('latin1').includes('%%EOF'), 'termina correctamente');
});

test('buildHelpPdf tolerates empty / malformed input', async () => {
  const buf = await buildHelpPdf({ title: 'X', subtitle: '', appLabel: 'DM', sections: [] });
  assert.equal(buf.slice(0, 5).toString('latin1'), '%PDF-');
});

function mount() {
  const app = express();
  app.use(express.json({ limit: '6mb' }));
  app.post('/api/help/pdf', (req, res) => handleHelpPdf(req, res, {
    appLabel: 'QR (TIS)', filename: 'Manual_QR_TIS.pdf',
    defaultTitle: 'Manual', defaultSubtitle: 'Sub',
  }));
  return app;
}

test('POST /api/help/pdf streams a PDF download', async () => {
  const server = await new Promise(r => { const s = mount().listen(0, () => r(s)); });
  try {
    const url = `http://127.0.0.1:${server.address().port}/api/help/pdf`;
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: 'Manual de Gestión de QR (TIS)', subtitle: 'Sub', sections: SECTIONS }) });
    assert.equal(r.status, 200);
    assert.equal(r.headers.get('content-type'), 'application/pdf');
    assert.match(r.headers.get('content-disposition') || '', /Manual_QR_TIS\.pdf/);
    const buf = Buffer.from(await r.arrayBuffer());
    assert.equal(buf.slice(0, 5).toString('latin1'), '%PDF-');
  } finally { server.close(); }
});

test('POST /api/help/pdf rejects an empty section list', async () => {
  const server = await new Promise(r => { const s = mount().listen(0, () => r(s)); });
  try {
    const url = `http://127.0.0.1:${server.address().port}/api/help/pdf`;
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sections: [] }) });
    assert.equal(r.status, 400);
    const d = await r.json();
    assert.match(d.error, /ayuda/i);
  } finally { server.close(); }
});
