// Inicialización de reivindicación de ejemplo: Actas

const db = require('./db');

function crearReivindicacionEjemplo() {
  // Verificar si ya existe una reivindicación con este título
  try {
    const existente = db.db.prepare(`
      SELECT id FROM reivindicaciones WHERE titulo = ?
    `).get('Permitir firmar las Actas digitalmente');

    if (existente) {
      console.log('[reivindicaciones] Reivindicación de ejemplo ya existe');
      return;
    }
  } catch (e) {
    console.error('[reivindicaciones] Error verificando reivindicación de ejemplo:', e.message);
    // Continuar de todas formas
  }

  // Crear reivindicación de ejemplo
  const contenido = [
    {
      tipo: 'titulo',
      texto: 'Solicitud: Permitir firmar las Actas digitalmente',
    },
    {
      tipo: 'parrafo',
      texto: 'Los estudiantes y docentes solicitan la posibilidad de firmar las Actas académicas (notas) utilizando firma digital, facilitando el proceso administrativo y adaptándose a los estándares modernos de documentación electrónica.',
    },
    {
      tipo: 'titulo',
      texto: 'Motivación',
    },
    {
      tipo: 'lista',
      items: [
        'Agilizar el proceso de firma de actas',
        'Reducir papel y mejorar sostenibilidad',
        'Facilitar el acceso remoto a firmas',
        'Cumplir con normativas de firma digital vigentes',
        'Mantener validez legal de documentos',
      ],
    },
    {
      tipo: 'titulo',
      texto: 'Beneficios',
    },
    {
      tipo: 'parrafo',
      texto: 'La firma digital de actas permitirá un flujo de trabajo más eficiente, reduciendo tiempos administrativos y facilitando el archivo y consulta de documentos. Esto es especialmente importante en contextos de educación híbrida o remota.',
    },
    {
      tipo: 'titulo',
      texto: 'Tu firma cuenta',
    },
    {
      tipo: 'parrafo',
      texto: 'Estamos recopilando firmas de apoyo. Si crees que esta reivindicación es importante, firma abajo para sumar tu voz a esta solicitud.',
    },
  ];

  const reivindicacion = db.createReivindicacion({
    titulo: 'Permitir firmar las Actas digitalmente',
    contenido,
    fecha_inicio: new Date().toISOString().split('T')[0],
    fecha_fin: null,
    objetivo_firmas: 50, // Objetivo inicial
    email_notificacion: null,
  }, 'SYSTEM');

  // Generar token de acceso
  const token = db.generateAccessToken(reivindicacion.id);

  console.log(`[reivindicaciones] Reivindicación de ejemplo creada:
  ID: ${reivindicacion.id}
  Título: ${reivindicacion.titulo}
  Token: ${token}
  URL: /reivindicaciones/firma/${token}`);

  return { reivindicacion, token };
}

module.exports = { crearReivindicacionEjemplo };
