// Shared test helpers. Each test FILE runs in its own process (node --test), so
// every file points DB_PATH at a unique temp database before requiring any app
// module, giving full isolation with no cross-test contamination.
const os = require('os');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

// Must be called BEFORE requiring any module that opens the DB.
function useTempDb() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'jt-test-'));
  const dbPath = path.join(dir, 'test.db');
  process.env.DB_PATH = dbPath;
  process.env.BATCHWORK_DATA_DIR = path.join(dir, 'bw');
  process.env.BATCHWORK_TMP_DIR = path.join(dir, 'bwtmp');
  return { dir, dbPath };
}

// Insert a user directly into the shared users table (created by auth/store).
// Returns the new user id. Avoids going through HTTP for unit-level DB tests.
function makeUser(store, email = `u${crypto.randomBytes(4).toString('hex')}@test.com`, role = 'user') {
  const info = store.db.prepare(
    "INSERT INTO users (email, name, password_hash, role, apps, active) VALUES (?, '', ?, ?, '*', 1)"
  ).run(email.toLowerCase(), store.hashPassword('password1234'), role);
  return { id: info.lastInsertRowid, email: email.toLowerCase() };
}

module.exports = { useTempDb, makeUser };
