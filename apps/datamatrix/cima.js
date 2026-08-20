'use strict';

// ── CIMA (AEMPS) lookup ──────────────────────────────────────────────────────────
// Public, keyless REST API of the Centro de Información de Medicamentos (AEMPS):
//   https://cima.aemps.es/cima/rest
// We use it to fill a medication's name (and derive its barcode/GTIN) from a
// Código Nacional, or to search by name. It's an OPTIONAL convenience: if CIMA is
// unreachable, the caller can still type the data by hand. All calls are made
// server-side (the browser can't reach CIMA under our CSP), with a short timeout.
//
// Lives in the Data Matrix app because it's about the medication catalogue; the
// Asignación app reuses it. NOTE: the hosting environment must allow outbound
// HTTPS to cima.aemps.es.

const gs1 = require('./gs1');

const BASE = (process.env.CIMA_BASE_URL || 'https://cima.aemps.es/cima/rest').replace(/\/+$/, '');
const TIMEOUT_MS = Number(process.env.CIMA_TIMEOUT_MS) || 6000;
const ENABLED = String(process.env.CIMA_ENABLED || 'true').toLowerCase() !== 'false';

// ── Barcode / GTIN math (Spanish medication codes; delegated to gs1) ──────────────
const ean13CheckDigit = (body12) => /^\d{12}$/.test(String(body12)) ? gs1.ean13Check(String(body12)) : null;
// GS1 GTIN-14 for a Código Nacional (847000+CN6, or 84700+CN7).
function gtinFromCn(cn) { return gs1.cnToGtin(cn); }
// EAN-13 barcode = GTIN-14 without its leading '0'.
function barcodeFromCn(cn) { const g = gs1.cnToGtin(cn); return g ? g.replace(/^0/, '') : null; }
// Recover a 6-digit Código Nacional from a Spanish EAN-13 (prefix 847000).
function cnFromBarcode(ean13) {
  const s = String(ean13 == null ? '' : ean13).trim();
  if (/^847000\d{7}$/.test(s)) return s.slice(6, 12);
  return null;
}

// ── HTTP helpers ──────────────────────────────────────────────────────────────────
function offline(msg) { const e = new Error(msg || 'No se pudo consultar CIMA (AEMPS).'); e.offline = true; e.status = 502; return e; }

async function getJson(path, fetchImpl) {
  if (!ENABLED) throw offline('La consulta a CIMA está desactivada (CIMA_ENABLED=false).');
  const doFetch = fetchImpl || globalThis.fetch;
  if (typeof doFetch !== 'function') throw offline('fetch no disponible en este entorno.');
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const r = await doFetch(BASE + path, { signal: ctrl.signal, headers: { Accept: 'application/json' } });
    if (!r.ok) throw offline(`CIMA respondió ${r.status}.`);
    return await r.json();
  } catch (e) {
    if (e.offline) throw e;
    throw offline('No se pudo contactar con CIMA: ' + (e.message || e));
  } finally {
    clearTimeout(timer);
  }
}

// Normalise a CIMA "medicamento" (+ its presentaciones) into what our apps store.
// `cn` (optional) picks the exact presentation's name when present.
function mapMedicamento(med, cn) {
  if (!med || (!med.nombre && !med.nregistro)) return null;
  const pres = Array.isArray(med.presentaciones) ? med.presentaciones : [];
  const exact = cn ? pres.find(p => String(p.cn) === String(cn)) : null;
  const theCn = (exact && exact.cn) || (pres[0] && pres[0].cn) || (cn ? String(cn) : null) || null;
  const nombre = (exact && exact.nombre) || med.nombre || (pres[0] && pres[0].nombre) || null;
  return {
    cn: theCn ? String(theCn) : null,
    nombre,
    nregistro: med.nregistro || null,
    pactivos: med.pactivos || null,
    labtitular: med.labtitular || null,
    comercializado: med.comerc === undefined ? null : !!med.comerc,
    barcode: barcodeFromCn(theCn),
    gtin: gtinFromCn(theCn),
    source: 'cima',
  };
}
const validCn = (cn) => /^\d{5,7}$/.test(String(cn == null ? '' : cn).trim());
function badCn() { const e = new Error('Código Nacional no válido.'); e.status = 400; return e; }

// Look up a medication by Código Nacional → mapped object (or null if not found).
async function lookupByCn(cn, opts = {}) {
  const c = String(cn == null ? '' : cn).trim();
  if (!validCn(c)) throw badCn();
  const med = await getJson(`/medicamento?cn=${encodeURIComponent(c)}`, opts.fetchImpl);
  return mapMedicamento(med, c);
}

// Diagnostic: return the raw CIMA response alongside the mapped result (for
// verifying field names in a real environment). ?debug=1 on the route uses this.
async function probeByCn(cn, opts = {}) {
  const c = String(cn == null ? '' : cn).trim();
  if (!validCn(c)) throw badCn();
  const raw = await getJson(`/medicamento?cn=${encodeURIComponent(c)}`, opts.fetchImpl);
  return { url: `${BASE}/medicamento?cn=${c}`, item: mapMedicamento(raw, c), raw };
}

// Search medications by free text (name / active ingredient) → mapped presentations.
async function searchByName(text, opts = {}) {
  const q = String(text == null ? '' : text).trim();
  if (q.length < 3) return [];
  const data = await getJson(`/medicamentos?nombre=${encodeURIComponent(q)}&pagina=1`, opts.fetchImpl);
  const rows = Array.isArray(data && data.resultados) ? data.resultados : [];
  const limit = Math.min(25, Math.max(1, opts.limit || 15));
  const out = [];
  for (const med of rows) {
    const pres = Array.isArray(med.presentaciones) && med.presentaciones.length ? med.presentaciones : [{ cn: null, nombre: med.nombre }];
    for (const p of pres) {
      const cn = p.cn ? String(p.cn) : null;
      out.push({
        cn, nombre: p.nombre || med.nombre || null,
        nregistro: med.nregistro || null, pactivos: med.pactivos || null, labtitular: med.labtitular || null,
        barcode: barcodeFromCn(cn), gtin: gtinFromCn(cn), source: 'cima',
      });
      if (out.length >= limit) return out;
    }
  }
  return out;
}

module.exports = {
  ENABLED, BASE,
  ean13CheckDigit, barcodeFromCn, gtinFromCn, cnFromBarcode,
  mapMedicamento, lookupByCn, probeByCn, searchByName,
};
