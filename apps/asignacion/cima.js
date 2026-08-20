'use strict';

// ── CIMA (AEMPS) lookup ──────────────────────────────────────────────────────────
// Public, keyless REST API of the Centro de Información de Medicamentos (AEMPS):
//   https://cima.aemps.es/cima/rest
// We use it to fill a medication's name (and derive its barcode/GTIN) from a
// Código Nacional, or to search by name. It's an OPTIONAL convenience: if CIMA is
// unreachable, the caller can still type the data by hand. All calls are made
// server-side (the browser can't reach CIMA under our CSP), with a short timeout.
//
// NOTE: the hosting environment must allow outbound HTTPS to cima.aemps.es.

const BASE = (process.env.CIMA_BASE_URL || 'https://cima.aemps.es/cima/rest').replace(/\/+$/, '');
const TIMEOUT_MS = Number(process.env.CIMA_TIMEOUT_MS) || 6000;
const ENABLED = String(process.env.CIMA_ENABLED || 'true').toLowerCase() !== 'false';

// ── Barcode / GTIN math (Spanish medication EAN-13, prefix 847000) ────────────────
// EAN-13 check digit for a 12-digit body (weights 1,3,1,3,… from the left).
function ean13CheckDigit(body12) {
  const d = String(body12);
  if (!/^\d{12}$/.test(d)) return null;
  let sum = 0;
  for (let i = 0; i < 12; i++) sum += Number(d[i]) * (i % 2 === 0 ? 1 : 3);
  return (10 - (sum % 10)) % 10;
}
// EAN-13 barcode for a 6-digit Código Nacional: 847000 + CN + check. Older/most
// medications. For other CN lengths we don't guess (the exact GTIN comes from the
// scanned Data Matrix), so we return null.
function barcodeFromCn(cn) {
  const c = String(cn == null ? '' : cn).trim();
  if (!/^\d{6}$/.test(c)) return null;
  const body = '847000' + c;                 // 12 digits
  const cd = ean13CheckDigit(body);
  return cd == null ? null : body + cd;       // 13 digits (EAN-13)
}
// GS1 GTIN-14 = '0' + EAN-13 (what the box's Data Matrix carries).
function gtinFromCn(cn) {
  const ean = barcodeFromCn(cn);
  return ean ? '0' + ean : null;
}
// Recover the Código Nacional from a Spanish EAN-13 (prefix 847000).
function cnFromBarcode(ean13) {
  const s = String(ean13 == null ? '' : ean13).trim();
  if (/^847000\d{7}$/.test(s)) return s.slice(6, 12);   // 847000 + CN(6) + check
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

// Normalise a CIMA "medicamento" (+ its presentaciones) into what our app stores.
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

// Look up a medication by Código Nacional. Returns the mapped object or null (not
// found). Throws an `offline` error if CIMA can't be reached.
async function lookupByCn(cn, opts = {}) {
  const c = String(cn == null ? '' : cn).trim();
  if (!/^\d{5,7}$/.test(c)) { const e = new Error('Código Nacional no válido.'); e.status = 400; throw e; }
  const med = await getJson(`/medicamento?cn=${encodeURIComponent(c)}`, opts.fetchImpl);
  return mapMedicamento(med, c);
}

// Search medications by free text (name / active ingredient). Returns up to `limit`
// mapped presentations. Throws an `offline` error if CIMA can't be reached.
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
  mapMedicamento, lookupByCn, searchByName,
};
