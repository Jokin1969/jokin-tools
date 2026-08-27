'use strict';

// ── Galénica — feed desde DM y Asignación ────────────────────────────────────────
// Relación DE UN SOLO SENTIDO: DM y Asignación llaman a ingestCn(cn) cuando ven un
// Código Nacional y siguen a lo suyo — no esperan respuesta, no la necesitan para su
// propio éxito, y Galénica nunca escribe de vuelta en sus bases de datos. "Que no se
// peleen entre ellas. Solo que miren."
//
// Un CN que YA está en Galénica no se vuelve a tocar desde aquí (aunque DM/Asignación
// lo sigan viendo): una vez que existe, Galénica es la única fuente de verdad de su
// propia ficha (p. ej. un color escrito a mano no se puede derivar de CIMA). Lo que
// CIMA no sepa se queda pendiente de completar a mano en la propia app — igual que
// en su alta manual o su importación masiva.

const db = require('./db');
const cimaCache = require('../datamatrix/cima-cache');
const cima = require('../datamatrix/cima');
const gs1 = require('../datamatrix/gs1');

const cleanCn = v => String(v == null ? '' : v).replace(/\D/g, '');

async function ingestOne(cn) {
  if (db.getByCn(cn)) return false;   // ya está — no tocar
  let it = null;
  try { it = await cimaCache.lookupByCnCached(cn); } catch { /* CIMA offline: entra igual, pendiente */ }
  db.upsertFromCima(cn, {
    gtin: (it && it.gtin) || gs1.cnToGtin(cn),
    barcode: (it && it.barcode) || cima.barcodeFromCn(cn),
    nombre: (it && it.nombre) || null,
    pactivos: it && it.pactivos, forma: it && it.forma, labtitular: it && it.labtitular,
  }, null);
  return true;
}

// Llamado desde DM/Asignación justo cuando ven un CN (una caja escaneada, un
// medicamento añadido a un plan…). Fire-and-forget a propósito: nunca se espera
// desde el llamador y nunca le puede hacer fallar su propia petición.
function ingestCn(cn) {
  const clean = cleanCn(cn);
  if (!/^\d{4,8}$/.test(clean)) return;
  if (db.getByCn(clean)) return;   // salida rápida sin tocar CIMA para el caso normal (CN repetido)
  ingestOne(clean).catch(err => console.error('[galenica/ingest] CN', clean, ':', err.message));
}

// Catch-up de arranque: recorre lo que YA había en Asignación y en DM antes de que
// este feed existiera. Asignación primero (tiene más medicamentos con CN). Idempotente
// — un CN ya presente en Galénica se salta al instante sin tocar CIMA — así que
// reiniciar el servidor no repite trabajo por nada ya resuelto.
async function backfillFrom(label, cns) {
  let added = 0, skipped = 0;
  for (const cn of cns) {
    const clean = cleanCn(cn);
    if (!/^\d{4,8}$/.test(clean)) continue;
    if (db.getByCn(clean)) { skipped++; continue; }
    try { if (await ingestOne(clean)) added++; }
    catch (e) { console.error(`[galenica/ingest] backfill (${label}) CN ${clean}:`, e.message); }
  }
  if (added) console.log(`[galenica/ingest] ${label}: ${added} CN nuevo(s) incorporado(s) (${skipped} ya estaban).`);
}

// El caller (arranque del servidor) NO espera esta promesa — fire-and-forget, nunca
// bloquea el arranque. Se devuelve igualmente para que los tests puedan esperarla.
// Asignación antes que DM, tal y como se pidió (tiene más medicamentos dados de alta).
async function backfillAll() {
  try {
    const asigDb = require('../asignacion/db');
    await backfillFrom('Asignación', asigDb.allCns());
  } catch (e) { console.error('[galenica/ingest] backfill Asignación falló:', e.message); }
  try {
    const dmDb = require('../datamatrix/db');
    await backfillFrom('Data Matrix', dmDb.allCns());
  } catch (e) { console.error('[galenica/ingest] backfill Data Matrix falló:', e.message); }
}

module.exports = { ingestCn, ingestOne, backfillFrom, backfillAll };
