const { test } = require('node:test');
const assert = require('node:assert');

// Set the env before requiring the config module (it reads lazily, but be safe).
process.env.IMPRIMIR_ENABLED = 'true';
process.env.IMPRIMIR_IMAP_USER = 'imprimir@joaquincastilla.com';
process.env.IMPRIMIR_IMAP_PASS = 'app-password-secreta';
process.env.IMPRIMIR_ALLOWLIST = 'castilla@joaquincastilla.com, otro@x.com';
process.env.IMPRIMIR_DEFAULT_PRINTER = '\\\\cicpri042\\Color';
process.env.IMPRIMIR_AGENT_KEY = 'clave-agente';
process.env.SMTP_USER = 'envio@x.com';
process.env.SMTP_PASS = 'smtp-secreta';
process.env.EMAIL_FROM = 'Imprimir <envio@x.com>';

const { maskedConfig, readiness } = require('../apps/imprimir/config');

test('maskedConfig expone lo visible y oculta los secretos', () => {
  const mc = maskedConfig();
  assert.equal(mc.enabled, true);
  assert.equal(mc.imap.user, 'imprimir@joaquincastilla.com');
  assert.equal(mc.imap.hasPass, true);
  assert.ok(!('pass' in mc.imap), 'no expone la contraseña IMAP');
  assert.equal(mc.hasAgentKey, true);
  assert.ok(!('agentKey' in mc), 'no expone la API key del agente');
  assert.deepEqual(mc.allowlist, ['castilla@joaquincastilla.com', 'otro@x.com']);
  assert.equal(mc.defaultPrinter, '\\\\cicpri042\\Color');
  assert.equal(mc.smtp.from, 'Imprimir <envio@x.com>');
  assert.equal(mc.smtp.hasPass, true);
});

test('IMAP host: hereda de SMTP_HOST si no se define IMPRIMIR_IMAP_HOST', () => {
  const savedImap = process.env.IMPRIMIR_IMAP_HOST;
  const savedSmtp = process.env.SMTP_HOST;
  try {
    delete process.env.IMPRIMIR_IMAP_HOST;
    process.env.SMTP_HOST = 'mail.joaquincastilla.com';
    let mc = maskedConfig();
    assert.equal(mc.imap.host, 'mail.joaquincastilla.com');
    assert.equal(mc.imap.hostFrom, 'SMTP_HOST');
    assert.equal(mc.imap.port, 993, 'el puerto IMAP sigue siendo 993, no el de SMTP');

    process.env.IMPRIMIR_IMAP_HOST = 'imap.otro.com';
    mc = maskedConfig();
    assert.equal(mc.imap.host, 'imap.otro.com');
    assert.equal(mc.imap.hostFrom, 'IMPRIMIR_IMAP_HOST');
  } finally {
    if (savedImap === undefined) delete process.env.IMPRIMIR_IMAP_HOST; else process.env.IMPRIMIR_IMAP_HOST = savedImap;
    if (savedSmtp === undefined) delete process.env.SMTP_HOST; else process.env.SMTP_HOST = savedSmtp;
  }
});

test('readiness: todo configurado + sondeo OK + agente visto → todo ok', () => {
  const items = readiness(maskedConfig(), {
    lastPollAt: '2026-07-02T09:00:00Z', lastPollOk: true, lastAgentPullAt: '2026-07-02T09:01:00Z',
  });
  const by = Object.fromEntries(items.map(i => [i.label, i]));
  assert.equal(by['Servicio activado'].ok, true);
  assert.equal(by['Credenciales del buzón (IMAP)'].ok, true);
  assert.equal(by['Remitentes autorizados'].ok, true);
  assert.equal(by['Clave del agente (API key)'].ok, true);
  assert.equal(by['Impresora por defecto'].ok, true);
  assert.equal(by['SMTP para avisos por email'].ok, true);
  assert.equal(by['Último sondeo del buzón'].level, 'ok');
  assert.equal(by['Agente de impresión visto'].ok, true);
});

test('readiness: detecta lo que falta con el nivel correcto', () => {
  const bad = {
    enabled: false,
    imap: { host: 'imap.gmail.com', port: 993, user: '', hasPass: false, mailbox: 'INBOX', secure: true },
    allowlist: [], allowAll: false, defaultPrinter: '', hasAgentKey: false,
    smtp: { user: '', from: '', hasPass: false },
    retentionDays: 14, maxMB: 25, pollCron: '* * * * *', notifyReceived: true, notifySenderNoPdf: true,
  };
  const by = Object.fromEntries(readiness(bad, {}).map(i => [i.label, i]));
  assert.equal(by['Servicio activado'].ok, false);
  assert.equal(by['Servicio activado'].level, 'error');
  assert.equal(by['Credenciales del buzón (IMAP)'].ok, false);
  assert.equal(by['Remitentes autorizados'].ok, false); // lista vacía y sin allowAll → nadie imprime
  assert.equal(by['Clave del agente (API key)'].ok, false);
  assert.equal(by['Impresora por defecto'].level, 'warn');
  assert.equal(by['SMTP para avisos por email'].level, 'warn');
  assert.equal(by['Agente de impresión visto'].ok, false);
});
