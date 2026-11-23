const { test } = require('node:test');
const assert = require('node:assert');
const Database = require('better-sqlite3');
const { useTempDb, makeUser } = require('./helpers');

// Una base de datos creada con el esquema defectuoso (FK a memories(user_id), que no
// es UNIQUE): así quedó la de producción. Toda inserción en quizzes fallaba.
const { dbPath } = useTempDb();
const old = new Database(dbPath);
old.pragma('foreign_keys = OFF');
old.exec(`
  CREATE TABLE quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL, status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'completed')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP, completed_at DATETIME, score INTEGER,
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES memories(user_id)
  );
  CREATE TABLE quiz_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, topic TEXT NOT NULL,
    total_quizzes INTEGER DEFAULT 0, total_score INTEGER DEFAULT 0, average_score REAL DEFAULT 0,
    best_score INTEGER DEFAULT 0, worst_score INTEGER DEFAULT 0, last_quiz_date DATETIME,
    FOREIGN KEY (user_id) REFERENCES memories(user_id),
    UNIQUE(user_id, topic)
  );
  INSERT INTO quiz_stats (user_id, topic, total_quizzes) VALUES (99, 'Historia', 3);
`);
old.close();

const store = require('../apps/auth/store');
const rm = require('../apps/re-memory/db');

test('la migración quita la FK a memories(user_id) de quizzes y quiz_stats', () => {
  for (const t of ['quizzes', 'quiz_stats']) {
    const { sql } = rm.db.prepare("SELECT sql FROM sqlite_master WHERE type='table' AND name=?").get(t);
    assert.ok(!/REFERENCES\s+memories\s*\(\s*user_id\s*\)/i.test(sql), `${t}: ${sql}`);
  }
});

test('la migración conserva las filas', () => {
  const row = rm.db.prepare("SELECT total_quizzes FROM quiz_stats WHERE user_id = 99 AND topic = 'Historia'").get();
  assert.equal(row.total_quizzes, 3);
});

test('tras migrar, createQuiz y updateQuizStats insertan', () => {
  const U = makeUser(store, 'mig@test.com');
  const m = rm.createMemory({ description: 'x', frequency: '1w', topic: 'Ciencia', user_id: U.id });
  assert.ok(rm.createQuiz(m.id, U.id).id);
  rm.updateQuizStats(U.id, 'Ciencia', 80);
  assert.equal(rm.getQuizStats(U.id, 'Ciencia').total_quizzes, 1);
});

test('tras migrar, borrar una ficha arrastra sus cuestionarios (la FK buena sigue)', () => {
  const U = makeUser(store, 'mig2@test.com');
  const m = rm.createMemory({ description: 'y', frequency: '1w', topic: 'Ciencia', user_id: U.id });
  rm.createQuiz(m.id, U.id);
  rm.deleteMemory(m.id, U.id);
  assert.equal(rm.db.prepare('SELECT COUNT(*) n FROM quizzes WHERE memory_id = ?').get(m.id).n, 0);
});
