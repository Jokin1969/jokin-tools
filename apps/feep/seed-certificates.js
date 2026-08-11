'use strict';

// ── FEEP · seed de certificados de asistencia (idempotente) ─────────────────────
// Importa un conjunto conocido de certificados en el repositorio del propietario
// (por su email). Se ejecuta al arrancar y es idempotente: no duplica un
// certificado ya existente (misma persona + evento + fecha). Los certificados se
// guardan SOLO con texto; el logo y la firma se toman de los predeterminados del
// usuario en el momento de generar el PDF (ver renderData en certificados/routes).

const fs = require('fs');
const path = require('path');
const feepDb = require('./db');

// Si existen ficheros de logo/firma en apps/feep/assets/, se cargan como
// predeterminados del propietario automáticamente (así no hay que subirlos a
// mano). Ficheros admitidos (el primero que exista):
const ASSETS_DIR = path.join(__dirname, 'assets');
const LOGO_FILES = ['logo.png', 'logo.jpg', 'logo.jpeg', 'logo.webp'];
const SIGNATURE_FILES = ['firma-secretario.png', 'firma.png', 'firma-secretario.jpg', 'firma.jpg'];

const SIGNER = 'Alberto Martínez';
const SIGNER_ROLE = 'Secretario de la Fundación Española de Enfermedades Priónicas';

// { name, talk, event, date (ISO) }
const CERTS = [
  { name: 'Izaro Kortazar', talk: 'El paciente de una enfermedad priónica', event: 'III Convención de afectados y profesionales de enfermedades priónicas', date: '2018-11-10' },
  { name: 'Izaro Kortazar', talk: 'Relación médico-paciente: una experiencia personal', event: 'IV Convención de afectados y profesionales de enfermedades priónicas', date: '2019-11-16' },
  { name: 'Guiomar Pérez de Nanclares', talk: 'Estudio genético: quién, cómo, cuándo y por qué', event: 'IV Convención de afectados y profesionales de enfermedades priónicas', date: '2019-11-16' },
  { name: 'Izaro Kortazar', talk: 'Organizando una red europea para la investigación de las enfermedades priónicas. El papel de investigadores y familias.', event: 'V Convención de afectados y profesionales de enfermedades priónicas', date: '2021-11-20' },
  { name: 'Guiomar Pérez de Nanclares', talk: '¿Para qué sirve un estudio genético?', event: 'V Convención de afectados y profesionales de enfermedades priónicas', date: '2021-11-20' },
  { name: 'Guiomar Pérez de Nanclares', talk: 'Cómo saber si no, sin saber si sí', event: 'VI Convención anual de afectados y profesionales de enfermedades priónicas', date: '2022-11-12' },
  { name: 'Izaro Kortazar', talk: 'Desentrañando el enigma: variabilidad en la edad de inicio de las enfermedades priónicas y sus implicaciones médicas', event: 'VII Convención anual de afectados y profesionales de enfermedades priónicas', date: '2023-11-18' },
  { name: 'Izaro Kortazar', talk: 'Adelantándonos al reloj: el poder predictivo de tu donación', event: 'VIII Convención anual de afectados y profesionales de enfermedades priónicas', date: '2024-11-16' },
  { name: 'Guiomar Pérez de Nanclares', talk: 'Diagnóstico genético preimplantacional: por un futuro seguro', event: 'VIII Convención anual de afectados y profesionales de enfermedades priónicas', date: '2024-11-16' },
  { name: 'Izaro Kortazar', talk: 'Historia natural y App: datos útiles para cuidar mejor hoy y tratar mejor mañana', event: 'IX Convención anual de afectados y profesionales de enfermedades priónicas', date: '2025-11-15' },
  { name: 'Guiomar Pérez de Nanclares', talk: 'Los guisantes de Mendel no cuadran', event: 'IX Convención anual de afectados y profesionales de enfermedades priónicas', date: '2025-11-15' },
];

const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
  'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

// ISO date (YYYY-MM-DD) → "10 de noviembre de 2018". Timezone-safe (no Date()).
function longDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
  if (!m) return String(iso || '');
  const y = m[1], mo = parseInt(m[2], 10), d = parseInt(m[3], 10);
  return `${d} de ${MONTHS[mo - 1] || ''} de ${y}`;
}

// Insert the known certificates for `user`, skipping any that already exist.
function seedFeepCertificates(user) {
  if (!user || user.id == null) return 0;
  const existsStmt = feepDb.db.prepare(
    'SELECT 1 FROM feep_certificates WHERE user_id = ? AND recipient_name = ? AND event = ? AND date_text = ? LIMIT 1'
  );
  let created = 0;
  for (const c of CERTS) {
    const event = `la ${c.event}`;
    const dateText = longDate(c.date);
    if (existsStmt.get(user.id, c.name, event, dateText)) continue;
    feepDb.createCert({
      recipient_name: c.name,
      role: 'ponente',
      event,
      talk_title: c.talk,
      date_text: dateText,
      event_date: c.date,
      signer_name: SIGNER,
      signer_role: SIGNER_ROLE,
      accent: 'clasico',
      orientation: 'horizontal',
    }, user.id);
    created++;
  }
  if (created) console.log(`[feep] Sembrados ${created} certificado(s) para ${user.email}`);
  return created;
}

// Read an image file (from the first existing candidate) into a data URL.
function fileToDataUrl(dir, candidates) {
  for (const name of candidates) {
    const p = path.join(dir, name);
    try {
      if (fs.existsSync(p)) {
        const ext = path.extname(p).toLowerCase().replace('.', '');
        const mime = ext === 'jpg' ? 'jpeg' : ext;
        return `data:image/${mime};base64,` + fs.readFileSync(p).toString('base64');
      }
    } catch { /* skip unreadable */ }
  }
  return null;
}

// If logo/signature files are present in apps/feep/assets/, activate them as the
// owner's default logo & signature — but never overwrite anything the user has
// already set from the app. No-op if the files aren't there.
function seedDefaultAssets(user) {
  if (!user || user.id == null) return false;
  const logo = fileToDataUrl(ASSETS_DIR, LOGO_FILES);
  const sig = fileToDataUrl(ASSETS_DIR, SIGNATURE_FILES);
  if (!logo && !sig) return false;

  const cur = feepDb.getDefaults(user.id) || {};
  const next = {
    logo_data: cur.logo_data || logo || null,
    signature_data: cur.signature_data || sig || null,
    signer_name: cur.signer_name || SIGNER,
    signer_role: cur.signer_role || SIGNER_ROLE,
    foundation: cur.foundation || undefined,
    accent: cur.accent || null,
    orientation: cur.orientation || null,
  };
  const changed = next.logo_data !== cur.logo_data || next.signature_data !== cur.signature_data
    || next.signer_name !== cur.signer_name || next.signer_role !== cur.signer_role;
  if (!changed) return false;
  feepDb.saveDefaults(user.id, next);
  console.log(`[feep] Predeterminados de logo/firma activados para ${user.email}`);
  return true;
}

module.exports = { seedFeepCertificates, seedDefaultAssets, CERTS, longDate };
