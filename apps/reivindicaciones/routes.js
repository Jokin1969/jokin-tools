const express = require('express');
const path = require('path');
const router = express.Router();
const db = require('./db');
const { enviarNotificacionFirma } = require('./email');

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
  const { titulo, contenido, fecha_inicio, fecha_fin, objetivo_firmas, email_notificacion } = req.body;
  if (!titulo || !fecha_inicio) {
    return res.status(400).json({ error: 'Faltan campos requeridos' });
  }
  const reivindicacion = db.createReivindicacion({
    titulo,
    contenido: contenido || [],
    fecha_inicio,
    fecha_fin,
    objetivo_firmas: objetivo_firmas || 0,
    email_notificacion: email_notificacion || null,
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
  const { titulo, contenido, estado, fecha_inicio, fecha_fin, objetivo_firmas, email_notificacion } = req.body;
  const reivindicacion = db.updateReivindicacion(req.params.id, {
    titulo,
    contenido,
    estado,
    fecha_inicio,
    fecha_fin,
    objetivo_firmas,
    email_notificacion,
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

// API Admin: obtener certificado de firma (para descargar)
router.get('/api/firmas/:id/certificado', (req, res) => {
  if (!req.user) return res.status(403).json({ error: 'Sin login' });
  const firma = db.getFirmaWithImage(req.params.id);
  if (!firma) return res.status(404).json({ error: 'No encontrada' });

  const htmlCert = `
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <title>Certificado de Firma Digital</title>
      <style>
        body { font-family: 'Georgia', serif; margin: 40px; color: #333; }
        .cert-container { border: 3px solid #1B6CB0; padding: 40px; max-width: 800px; margin: 0 auto; background: #f9f9f9; }
        .cert-header { text-align: center; border-bottom: 2px solid #1B6CB0; padding-bottom: 20px; margin-bottom: 30px; }
        .cert-header h1 { margin: 0; color: #1B6CB0; font-size: 28px; }
        .cert-header p { margin: 10px 0 0 0; color: #666; font-size: 14px; }
        .cert-body { line-height: 1.8; }
        .cert-field { margin: 20px 0; }
        .cert-label { font-weight: bold; color: #1B6CB0; }
        .cert-value { margin-top: 5px; padding: 8px; background: white; border-left: 3px solid #0097B2; padding-left: 15px; }
        .cert-firma-container { text-align: center; margin: 40px 0 20px 0; }
        .cert-firma-label { font-size: 12px; color: #999; margin-bottom: 10px; }
        .cert-firma-img { max-width: 200px; border: 1px solid #ddd; padding: 10px; background: white; }
        .cert-footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #999; font-size: 12px; }
        @media print {
          body { margin: 0; }
          .cert-container { border: 1px solid #ddd; box-shadow: none; }
        }
      </style>
    </head>
    <body>
      <div class="cert-container">
        <div class="cert-header">
          <h1>CERTIFICADO DE FIRMA DIGITAL</h1>
          <p>Documento de registro de firma electrónica</p>
        </div>

        <div class="cert-body">
          <div class="cert-field">
            <div class="cert-label">Identificación del Firmante</div>
            <div class="cert-value">${escapeHtml(firma.nombre)}</div>
          </div>

          <div class="cert-field">
            <div class="cert-label">Documento de Identidad (DNI/NIE)</div>
            <div class="cert-value">${escapeHtml(firma.dni)}</div>
          </div>

          <div class="cert-field">
            <div class="cert-label">Fecha y Hora de la Firma</div>
            <div class="cert-value">${new Date(firma.creado_en).toLocaleString('es-ES', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })}</div>
          </div>

          <div class="cert-field">
            <div class="cert-label">Dirección IP del Firmante</div>
            <div class="cert-value">${escapeHtml(firma.ip_address || 'No registrada')}</div>
          </div>

          <div class="cert-field">
            <div class="cert-label">Información del Navegador/Dispositivo</div>
            <div class="cert-value" style="font-size:12px;">${escapeHtml(firma.user_agent || 'No registrado')}</div>
          </div>

          <div class="cert-field">
            <div class="cert-label">Validez Legal</div>
            <div class="cert-value">Esta firma digital ha sido realizada mediante un sistema de firma electrónica seguro y tiene validez jurídica conforme a la legislación aplicable sobre firma electrónica. El firmante manifiesta su consentimiento expreso y acepta la responsabilidad de los datos proporcionados.</div>
          </div>

          ${firma.firma_imagen ? `
            <div class="cert-firma-container">
              <div class="cert-firma-label">Firma Digital del Documento</div>
              <img src="data:image/png;base64,${firma.firma_imagen.toString('base64')}" class="cert-firma-img" />
            </div>
          ` : ''}

          <div class="cert-footer">
            <p><strong>CERTIFICACIÓN DIGITAL</strong></p>
            <p>Este documento certifica la autenticidad de la firma digital realizada por el firmante identificado arriba. El registro de firma incluye pruebas de identidad, hora exacta, dirección IP y datos del dispositivo utilizado para garantizar la autenticidad e integridad de la firma.</p>
            <p>Documento generado automáticamente por sistema de firma digital seguro.</p>
          </div>
        </div>
      </div>
    </body>
    </html>
  `;

  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="certificado-firma-' + firma.id + '.html"');
  res.send(htmlCert);
});

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text || '').replace(/[&<>"']/g, m => map[m]);
}

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

  // Enviar notificación por email (async, no bloquea)
  const reivindicacion = db.getReivindicacionPublico(reivindicacionId);
  if (reivindicacion && reivindicacion.email_notificacion) {
    enviarNotificacionFirma(
      { ...reivindicacion, contador_firmas: (reivindicacion.contador_firmas || 0) + 1 },
      { nombre, dni: dniValidacion.dni, creado_en: new Date().toISOString() },
      reivindicacion.email_notificacion
    ).catch(() => {}); // Ignorar errores de email
  }

  res.json({ exito: true, mensaje: '¡Gracias por tu firma!' });
});

module.exports = router;
