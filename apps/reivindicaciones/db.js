const Database = require('better-sqlite3');
const path = require('path');

const dbPath = process.env.DB_PATH || '/data';
const db = new Database(path.join(path.dirname(dbPath), 'reivindicaciones.db'));

db.exec(`
  CREATE TABLE IF NOT EXISTS reivindicaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    titulo TEXT NOT NULL,
    contenido TEXT NOT NULL DEFAULT '[]',
    estado TEXT DEFAULT 'activa',
    fecha_inicio TEXT NOT NULL,
    fecha_fin TEXT,
    objetivo_firmas INTEGER DEFAULT 0,
    email_notificacion TEXT,
    creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS firmas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reivindicacion_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    dni TEXT NOT NULL,
    firma_imagen BLOB,
    ip_address TEXT,
    user_agent TEXT,
    creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reivindicacion_id) REFERENCES reivindicaciones(id) ON DELETE CASCADE,
    UNIQUE(reivindicacion_id, dni)
  );

  CREATE TABLE IF NOT EXISTS access_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reivindicacion_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reivindicacion_id) REFERENCES reivindicaciones(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_firmas_reivindicacion ON firmas(reivindicacion_id);
  CREATE INDEX IF NOT EXISTS idx_access_tokens_reivindicacion ON access_tokens(reivindicacion_id);
  CREATE INDEX IF NOT EXISTS idx_access_tokens_token ON access_tokens(token);
`);

// Reivindicaciones
function createReivindicacion(reivindicacion, userId) {
  const stmt = db.prepare(`
    INSERT INTO reivindicaciones (user_id, titulo, contenido, fecha_inicio, fecha_fin, objetivo_firmas, email_notificacion)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);
  const result = stmt.run(
    userId,
    reivindicacion.titulo,
    JSON.stringify(reivindicacion.contenido || []),
    reivindicacion.fecha_inicio,
    reivindicacion.fecha_fin || null,
    reivindicacion.objetivo_firmas || 0,
    reivindicacion.email_notificacion || null
  );
  return { id: result.lastInsertRowid, ...reivindicacion };
}

function getReivindicaciones(userId) {
  const stmt = db.prepare(`
    SELECT r.*, COUNT(f.id) as contador_firmas
    FROM reivindicaciones r
    LEFT JOIN firmas f ON r.id = f.reivindicacion_id
    WHERE r.user_id = ?
    GROUP BY r.id
    ORDER BY r.creado_en DESC
  `);
  return stmt.all(userId);
}

function getReivindicacionById(id, userId) {
  const stmt = db.prepare(`
    SELECT r.*, COUNT(f.id) as contador_firmas
    FROM reivindicaciones r
    LEFT JOIN firmas f ON r.id = f.reivindicacion_id
    WHERE r.id = ? AND r.user_id = ?
    GROUP BY r.id
  `);
  return stmt.get(id, userId);
}

function updateReivindicacion(id, reivindicacion, userId) {
  const stmt = db.prepare(`
    UPDATE reivindicaciones
    SET titulo = ?, contenido = ?, estado = ?, fecha_inicio = ?, fecha_fin = ?, objetivo_firmas = ?, email_notificacion = ?, actualizado_en = CURRENT_TIMESTAMP
    WHERE id = ? AND user_id = ?
  `);
  stmt.run(
    reivindicacion.titulo,
    JSON.stringify(reivindicacion.contenido || []),
    reivindicacion.estado,
    reivindicacion.fecha_inicio,
    reivindicacion.fecha_fin || null,
    reivindicacion.objetivo_firmas || 0,
    reivindicacion.email_notificacion || null,
    id,
    userId
  );
  return getReivindicacionById(id, userId);
}

function deleteReivindicacion(id, userId) {
  const stmt = db.prepare('DELETE FROM reivindicaciones WHERE id = ? AND user_id = ?');
  return stmt.run(id, userId);
}

// Firmas
function addFirma(reivindicacionId, firma, ipAddress, userAgent) {
  const stmt = db.prepare(`
    INSERT INTO firmas (reivindicacion_id, nombre, dni, firma_imagen, ip_address, user_agent)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  try {
    const result = stmt.run(
      reivindicacionId,
      firma.nombre,
      firma.dni,
      firma.firma_imagen || null,
      ipAddress,
      userAgent
    );
    return { id: result.lastInsertRowid, exito: true };
  } catch (e) {
    if (e.message.includes('UNIQUE constraint failed')) {
      return { exito: false, error: 'Este DNI ya ha firmado esta reivindicación' };
    }
    throw e;
  }
}

function getFirmas(reivindicacionId) {
  const stmt = db.prepare(`
    SELECT id, nombre, dni, creado_en
    FROM firmas
    WHERE reivindicacion_id = ?
    ORDER BY creado_en DESC
  `);
  return stmt.all(reivindicacionId);
}

function getFirmasCount(reivindicacionId) {
  const stmt = db.prepare('SELECT COUNT(*) as count FROM firmas WHERE reivindicacion_id = ?');
  return stmt.get(reivindicacionId).count;
}

function getFirmaWithImage(id) {
  const stmt = db.prepare('SELECT * FROM firmas WHERE id = ?');
  return stmt.get(id);
}

// Access tokens
function generateAccessToken(reivindicacionId) {
  const token = require('crypto').randomBytes(32).toString('hex');
  const stmt = db.prepare('INSERT INTO access_tokens (reivindicacion_id, token) VALUES (?, ?)');
  stmt.run(reivindicacionId, token);
  return token;
}

function verifyAccessToken(token) {
  const stmt = db.prepare('SELECT reivindicacion_id FROM access_tokens WHERE token = ?');
  const result = stmt.get(token);
  return result ? result.reivindicacion_id : null;
}

function getReivindicacionPublico(reivindicacionId) {
  const stmt = db.prepare(`
    SELECT id, titulo, descripcion, estado, fecha_inicio, fecha_fin, objetivo_firmas,
           (SELECT COUNT(*) FROM firmas WHERE reivindicacion_id = ?) as contador_firmas
    FROM reivindicaciones
    WHERE id = ?
  `);
  return stmt.get(reivindicacionId, reivindicacionId);
}

module.exports = {
  createReivindicacion,
  getReivindicaciones,
  getReivindicacionById,
  updateReivindicacion,
  deleteReivindicacion,
  addFirma,
  getFirmas,
  getFirmasCount,
  getFirmaWithImage,
  generateAccessToken,
  verifyAccessToken,
  getReivindicacionPublico,
};
