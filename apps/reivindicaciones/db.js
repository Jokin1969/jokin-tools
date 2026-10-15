const Database = require('better-sqlite3');
const path = require('path');

const dataDir = process.env.DB_PATH || '/data';
const dbPath = path.join(dataDir, 'reivindicaciones.db');
const db = new Database(dbPath);

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

  CREATE TABLE IF NOT EXISTS votaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reivindicacion_id INTEGER NOT NULL,
    pregunta TEXT NOT NULL,
    opciones TEXT NOT NULL DEFAULT '[]',
    activa INTEGER DEFAULT 1,
    creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reivindicacion_id) REFERENCES reivindicaciones(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS votos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    votacion_id INTEGER NOT NULL,
    firma_id INTEGER NOT NULL,
    opcion TEXT NOT NULL,
    creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (votacion_id) REFERENCES votaciones(id) ON DELETE CASCADE,
    FOREIGN KEY (firma_id) REFERENCES firmas(id) ON DELETE CASCADE,
    UNIQUE(votacion_id, firma_id)
  );

  CREATE INDEX IF NOT EXISTS idx_firmas_reivindicacion ON firmas(reivindicacion_id);
  CREATE INDEX IF NOT EXISTS idx_access_tokens_reivindicacion ON access_tokens(reivindicacion_id);
  CREATE INDEX IF NOT EXISTS idx_access_tokens_token ON access_tokens(token);
  CREATE INDEX IF NOT EXISTS idx_votaciones_reivindicacion ON votaciones(reivindicacion_id);
  CREATE INDEX IF NOT EXISTS idx_votos_votacion ON votos(votacion_id);
`);

// Crear reivindicación de ejemplo al inicializar
try {
  const { crearReivindicacionEjemplo } = require('./init-ejemplo');
  crearReivindicacionEjemplo();
} catch (e) {
  console.error('[reivindicaciones] Error inicializando ejemplo:', e.message);
}

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
    SELECT id, titulo, descripcion, contenido, estado, fecha_inicio, fecha_fin, objetivo_firmas,
           (SELECT COUNT(*) FROM firmas WHERE reivindicacion_id = ?) as contador_firmas
    FROM reivindicaciones
    WHERE id = ?
  `);
  const row = stmt.get(reivindicacionId, reivindicacionId);
  if (row && typeof row.contenido === 'string') {
    try {
      row.contenido = JSON.parse(row.contenido);
    } catch (e) {
      row.contenido = [];
    }
  }
  return row;
}

// Votaciones
function createVotacion(reivindicacionId, votacion) {
  const stmt = db.prepare(`
    INSERT INTO votaciones (reivindicacion_id, pregunta, opciones)
    VALUES (?, ?, ?)
  `);
  const result = stmt.run(
    reivindicacionId,
    votacion.pregunta,
    JSON.stringify(votacion.opciones || [])
  );
  return { id: result.lastInsertRowid, ...votacion };
}

function getVotacionesPorReivindicacion(reivindicacionId) {
  const stmt = db.prepare(`
    SELECT * FROM votaciones WHERE reivindicacion_id = ? AND activa = 1
  `);
  return stmt.all(reivindicacionId).map(v => ({
    ...v,
    opciones: JSON.parse(v.opciones || '[]'),
  }));
}

function addVoto(votacionId, firmaId, opcion) {
  const stmt = db.prepare(`
    INSERT INTO votos (votacion_id, firma_id, opcion)
    VALUES (?, ?, ?)
  `);
  try {
    stmt.run(votacionId, firmaId, opcion);
    return { exito: true };
  } catch (e) {
    if (e.message.includes('UNIQUE constraint failed')) {
      return { exito: false, error: 'Ya has votado en esta encuesta' };
    }
    throw e;
  }
}

function getResultadosVotacion(votacionId) {
  const stmt = db.prepare(`
    SELECT opcion, COUNT(*) as count FROM votos WHERE votacion_id = ? GROUP BY opcion
  `);
  return stmt.all(votacionId);
}

module.exports = {
  db, // Exportar instancia de BD para acceso directo si es necesario
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
  createVotacion,
  getVotacionesPorReivindicacion,
  addVoto,
  getResultadosVotacion,
};
