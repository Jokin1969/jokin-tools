const { ImapFlow } = require('imapflow');

// Connect to the print mailbox, iterate UNSEEN messages, and hand each raw
// message source to `handleSource`. Only messages the handler reports as
// definitively handled (returns true) are flagged \Seen, so a transient error
// (disk full, DB locked) leaves the email for the next poll. Enqueue itself is
// idempotent (message_id UNIQUE), so an occasional reprocess is harmless.
async function pollMailbox(cfg, handleSource) {
  const client = new ImapFlow({
    host: cfg.imap.host,
    port: cfg.imap.port,
    secure: cfg.imap.secure,
    auth: { user: cfg.imap.user, pass: cfg.imap.pass },
    logger: false,
    // Fail fast rather than hang a poll cycle forever.
    socketTimeout: 60000,
  });

  await client.connect();
  const lock = await client.getMailboxLock(cfg.imap.mailbox);
  let processed = 0;
  const toMark = [];
  try {
    for await (const msg of client.fetch({ seen: false }, { uid: true, source: true })) {
      processed++;
      let handled = false;
      try {
        handled = await handleSource(msg.source);
      } catch (e) {
        console.error('[imprimir] Error procesando mensaje uid', msg.uid, '—', e.message);
        handled = false; // leave unseen; retry next poll
      }
      if (handled) toMark.push(msg.uid);
    }
    if (toMark.length) {
      await client.messageFlagsAdd({ uid: toMark.join(',') }, ['\\Seen'], { uid: true });
    }
  } finally {
    lock.release();
  }
  await client.logout();
  return { processed, marked: toMark.length };
}

// Actively test the IMAP connection + credentials (used by the status page's
// "Probar conexión" button). Returns { ok, mailbox, unseen } or throws.
async function testConnection(cfg) {
  const client = new ImapFlow({
    host: cfg.imap.host,
    port: cfg.imap.port,
    secure: cfg.imap.secure,
    auth: { user: cfg.imap.user, pass: cfg.imap.pass },
    logger: false,
    socketTimeout: 20000,
  });
  await client.connect();
  const lock = await client.getMailboxLock(cfg.imap.mailbox);
  let unseen = 0;
  try {
    const found = await client.search({ seen: false }, { uid: true });
    unseen = Array.isArray(found) ? found.length : 0;
  } finally {
    lock.release();
  }
  await client.logout();
  return { ok: true, mailbox: cfg.imap.mailbox, unseen };
}

module.exports = { pollMailbox, testConnection };
