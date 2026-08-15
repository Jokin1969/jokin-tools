'use strict';

// ── GS1 Data Matrix parser (pharmaceutical) ─────────────────────────────────────
// Spanish/EU medicine boxes carry a GS1 Data Matrix that encodes, via Application
// Identifiers (AIs):
//   01  GTIN            (14 digits, fixed)        → the product
//   21  Serial number   (variable)               → unique per box
//   17  Expiry date      (YYMMDD, 6 digits fixed)
//   10  Batch / lot      (variable)
//   710-714 National reimbursement number (variable) → "Código Nacional" (ES)
// Variable-length fields are separated by the FNC1/GS character (ASCII 29) which a
// scanner reports as \x1d. Some scanners also prefix a symbology id ("]d2"/"]C1").
//
// We keep the RAW verbatim (to re-encode an identical, scannable Data Matrix) and
// also segregate the useful fields for display/search.

const GS = '\x1d';

// AIs with a predefined (fixed) data length — they need no separator afterwards.
const FIXED = {
  '00': 18, '01': 14, '02': 14, '03': 14, '04': 16,
  '11': 6, '12': 6, '13': 6, '14': 6, '15': 6, '16': 6, '17': 6, '18': 6, '19': 6,
  '20': 2,
};

// Normalise the raw string a scanner produced.
function normalizeRaw(raw) {
  let s = String(raw == null ? '' : raw);
  s = s.replace(/^\][A-Za-z]\d/, ''); // strip symbology identifier (]d2, ]C1, ]e0…)
  s = s.replace(/^[\x1d]+/, '');        // strip a leading GS/FNC1
  return s;
}

// Parse into { gtin, serial, lote, caducidad(raw YYMMDD), cn }.
function parse(raw) {
  const s = normalizeRaw(raw);
  const out = { gtin: null, serial: null, lote: null, caducidad: null, cn: null };
  let i = 0;
  const readVar = () => {
    let j = s.indexOf(GS, i);
    if (j < 0) j = s.length;
    const v = s.slice(i, j);
    i = j < s.length ? j + 1 : j;
    return v;
  };
  let guard = 0;
  while (i < s.length && guard++ < 64) {
    const ai3 = s.substr(i, 3);
    if (/^71[0-4]$/.test(ai3)) { i += 3; const v = readVar(); if (!out.cn) out.cn = v; continue; }
    const ai2 = s.substr(i, 2);
    if (ai2 === '01') { i += 2; out.gtin = s.substr(i, 14); i += 14; continue; }
    if (ai2 === '17') { i += 2; out.caducidad = s.substr(i, 6); i += 6; continue; }
    if (ai2 === '10') { i += 2; out.lote = readVar() || null; continue; }
    if (ai2 === '21') { i += 2; out.serial = readVar() || null; continue; }
    if (FIXED[ai2] != null) { i += 2 + FIXED[ai2]; continue; } // skip other fixed AIs
    // Unknown → treat as a variable field and skip it (keeps parsing robust).
    if (/^\d{2}$/.test(ai2)) { i += 2; readVar(); continue; }
    break; // not GS1-shaped from here
  }
  return out;
}

// YYMMDD → ISO date (YYYY-MM-DD). DD == 00 means "end of month" (GS1 rule).
function expiryToIso(yymmdd) {
  const m = /^(\d{2})(\d{2})(\d{2})$/.exec(String(yymmdd || ''));
  if (!m) return null;
  const year = 2000 + (+m[1]);
  const month = +m[2];
  let day = +m[3];
  if (month < 1 || month > 12) return null;
  if (day === 0) day = new Date(Date.UTC(year, month, 0)).getUTCDate(); // last day of month
  if (day < 1 || day > 31) return null;
  const p = n => String(n).padStart(2, '0');
  return `${year}-${p(month)}-${p(day)}`;
}

// Canonical 14-digit GTIN. A box's Data Matrix carries a GTIN-14 (AI 01), but a
// pharmacy catalogue (Farmatic, Bot PLUS…) usually lists the barcode as an EAN-13.
// GTIN-14 = "0" + EAN-13, so we pad/trim everything to 14 digits to match reliably.
function normGtin(s) {
  const d = String(s == null ? '' : s).replace(/\D/g, '');
  if (!d) return null;
  return d.length >= 14 ? d.slice(-14) : d.padStart(14, '0');
}

// EAN-13 check digit for a 12-digit body.
function ean13Check(body12) {
  const d = String(body12); let sum = 0;
  for (let i = 0; i < 12; i++) sum += (i % 2 === 0 ? 1 : 3) * (+d[i] || 0);
  return String((10 - (sum % 10)) % 10);
}
// Reconstruct the canonical GTIN-14 from a Spanish Código Nacional so a catalogue
// that only has the CN (no barcode) can still match boxes by GTIN. CN6 →
// 847000+CN6, CN7 → 84700+CN7 (both give a 12-digit body → EAN-13 → GTIN-14).
// It only ever produces a match when the box's REAL GTIN equals this, so a wrong
// reconstruction just misses — it never mislabels.
function cnToGtin(cn) {
  const d = String(cn == null ? '' : cn).replace(/\D/g, '');
  if (!d) return null;
  let body12;
  if (d.length <= 6) body12 = '847000' + d.padStart(6, '0');
  else if (d.length === 7) body12 = '84700' + d;
  else return null;
  return '0' + body12 + ean13Check(body12);
}

// A stable identity for "the same physical box": GTIN + serial when present,
// otherwise the raw content (so codes without a serial are still de-duplicated).
function boxKey(fields, raw) {
  if (fields && fields.gtin && fields.serial) return fields.gtin + '|' + fields.serial;
  return 'raw:' + normalizeRaw(raw);
}

module.exports = { GS, parse, normalizeRaw, expiryToIso, boxKey, normGtin, cnToGtin, ean13Check };
