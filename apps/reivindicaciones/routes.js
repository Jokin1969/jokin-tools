const express = require('express');
const path = require('path');
const router = express.Router();
const db = require('./db');

// Validar DNI
function validarDNI(dni) {
  const cleaned = dni.replace(/[^0-9XYZ]/gi, '').toUpperCase();
  if (!/^[0-9]{8}[XYZ]?$/.test(cleaned)) {
    return { valido: false, error: 'DNI inválido' };
  }
  return { valido: true, dni: cleaned };
}

// Middleware: verificar token de acceso público
function verifyPublicToken(req, res, next) {
  const token = req.params.token || req.query.token;
  if (!token) {
    return res.status(403).json({ error: 'Token requerido' });
  }
  const reivindicacionId = db.verifyAccessToken(token);
  if (!reivindicacionId) {
    return res.status(403).json({ error: 'Token inválido o expirado' });
  }
  req.reivindicacionId = reivindicacionId;
  next();
}

// ========== ADMIN (con login) ==========

// Servir HTML principal
router.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Servir assets estáticos
router.use('/public', express.static(path.join(__dirname, 'public')));
router.use('/assets', express.static(path.join(__dirname, 'public')));

// API Admin: listar reivindicaciones
router.get('/api/reivindicaciones', (req, res) => {
  if (!req.user) return res.status(403).json({ error: 'Sin login' });
  const reivindicaciones = db.getReivindicaciones(req.user.id);
  res.json(reivindicaciones);
});

// API Admin: crear reivindicación
router.post('/api/reivindicaciones', express.json({ limit: '256kb' }), (req, res) => {
  if (!req.user) return res.status(403).json({ error: 'Sin login' });
  const { titulo, contenido, fecha_inicio, fecha_fin, objetivo_firmas } = req.body;
  if (!titulo || !fecha_inicio) {
    return res.status(400).json({ error: 'Faltan campos requeridos' });
  }
  const reivindicacion = db.createReivindicacion({
    titulo,
    contenido: contenido || [],
    fecha_inicio,
    fecha_fin,
    objetivo_firmas: objetivo_firmas || 0,
  }, req.user.id);
  // Generar token de acceso
  const token = db.generateAccessToken(reivindicacion.id);
  res.json({ ...reivindicacion, token });
});

// API Admin: obtener reivindicación por ID
router.get('/api/reivindicaciones/:id', (req, res) => {
  if (!req.user) return res.status(403).json({ error: 'Sin login' });
  const reivindicacion = db.getReivindicacionById(req.params.id, req.user.id);
  if (!reivindicacion) return res.status(404).json({ error: 'No encontrada' });
  res.json(reivindicacion);
});

// API Admin: actualizar reivindicación
router.put('/api/reivindicaciones/:id', express.json({ limit: '256kb' }), (req, res) => {
  if (!req.user) return res.status(403).json({ error: 'Sin login' });
  const { titulo, contenido, estado, fecha_inicio, fecha_fin, objetivo_firmas } = req.body;
  const reivindicacion = db.updateReivindicacion(req.params.id, {
    titulo,
    contenido,
    estado,
    fecha_inicio,
    fecha_fin,
    objetivo_firmas,
  }, req.user.id);
  res.json(reivindicacion);
});

// API Admin: eliminar reivindicación
router.delete('/api/reivindicaciones/:id', (req, res) => {
  if (!req.user) return res.status(403).json({ error: 'Sin login' });
  db.deleteReivindicacion(req.params.id, req.user.id);
  res.json({ exito: true });
});

// API Admin: obtener firmas de una reivindicación
router.get('/api/reivindicaciones/:id/firmas', (req, res) => {
  if (!req.user) return res.status(403).json({ error: 'Sin login' });
  const reivindicacion = db.getReivindicacionById(req.params.id, req.user.id);
  if (!reivindicacion) return res.status(404).json({ error: 'No encontrada' });
  const firmas = db.getFirmas(req.params.id);
  res.json(firmas);
});

// API Admin: descargar firma en imagen
router.get('/api/firmas/:id/imagen', (req, res) => {
  if (!req.user) return res.status(403).json({ error: 'Sin login' });
  const firma = db.getFirmaWithImage(req.params.id);
  if (!firma) return res.status(404).json({ error: 'No encontrada' });
  if (!firma.firma_imagen) return res.status(404).json({ error: 'Sin imagen' });
  res.setHeader('Content-Type', 'image/png');
  res.send(firma.firma_imagen);
});

// API Admin: generar token de acceso
router.post('/api/reivindicaciones/:id/token', (req, res) => {
  if (!req.user) return res.status(403).json({ error: 'Sin login' });
  const reivindicacion = db.getReivindicacionById(req.params.id, req.user.id);
  if (!reivindicacion) return res.status(404).json({ error: 'No encontrada' });
  const token = db.generateAccessToken(reivindicacion.id);
  res.json({ token });
});

// ========== PÚBLICO (sin login, con token) ==========

// Página pública de firma (acceso con token en URL)
router.get('/firma/:token', (req, res) => {
  const reivindicacionId = db.verifyAccessToken(req.params.token);
  if (!reivindicacionId) {
    return res.status(403).send(`
      <!DOCTYPE html>
      <html lang="es">
      <head>
        <meta charset="UTF-8">
        <title>Enlace inválido</title>
        <style>
          body { font-family: Inter, sans-serif; text-align: center; padding: 50px; }
          .error { color: #d32f2f; }
        </style>
      </head>
      <body>
        <div class="error">
          <h1>Enlace inválido o expirado</h1>
          <p>Este enlace de firma ya no es válido.</p>
        </div>
      </body>
      </html>
    `);
  }
  // Servir página de firma (será un HTML especial sin la barra de navegación)
  res.sendFile(path.join(__dirname, 'public', 'firma.html'));
});

// API Público: obtener datos de reivindicación para firma
router.get('/api/firma/:token/reivindicacion', (req, res) => {
  const reivindicacionId = db.verifyAccessToken(req.params.token);
  if (!reivindicacionId) {
    return res.status(403).json({ error: 'Token inválido' });
  }
  const reivindicacion = db.getReivindicacionPublico(reivindicacionId);
  if (!reivindicacion) return res.status(404).json({ error: 'No encontrada' });
  res.json(reivindicacion);
});

// API Público: enviar firma
router.post('/api/firma/:token/firmar', express.json({ limit: '10mb' }), (req, res) => {
  const reivindicacionId = db.verifyAccessToken(req.params.token);
  if (!reivindicacionId) {
    return res.status(403).json({ error: 'Token inválido' });
  }

  const { nombre, dni, firma_imagen, acepta_terminos } = req.body;

  if (!nombre || !dni || !firma_imagen || !acepta_terminos) {
    return res.status(400).json({ error: 'Faltan campos requeridos' });
  }

  const dniValidacion = validarDNI(dni);
  if (!dniValidacion.valido) {
    return res.status(400).json({ error: dniValidacion.error });
  }

  // Convertir base64 a Buffer
  let firmaBuffer = null;
  try {
    const base64Data = firma_imagen.replace(/^data:image\/\w+;base64,/, '');
    firmaBuffer = Buffer.from(base64Data, 'base64');
  } catch (e) {
    return res.status(400).json({ error: 'Firma inválida' });
  }

  const ipAddress = req.ip || req.connection.remoteAddress;
  const userAgent = req.get('user-agent');

  const resultado = db.addFirma(
    reivindicacionId,
    { nombre, dni: dniValidacion.dni, firma_imagen: firmaBuffer },
    ipAddress,
    userAgent
  );

  if (!resultado.exito) {
    return res.status(409).json({ error: resultado.error });
  }

  res.json({ exito: true, mensaje: '¡Gracias por tu firma!' });
});

module.exports = router;
