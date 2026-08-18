// ── Batchwork · bio helpers (pure, browser + Node) ───────────────────────────────
// Genetic code, ORF analysis, position parsing and codon-optimised variant
// building for the saturation-mutagenesis sub-mode of the .dna plasmid generator.
// Kept free of DOM so it can be unit-tested under node --test.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;   // Node / tests
  if (typeof window !== 'undefined') window.BWBio = api;                     // browser
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Standard genetic code (DNA codons, T-based). '*' = stop.
  const GENETIC_CODE = (() => {
    const bases = ['T', 'C', 'A', 'G'];
    const aa = 'FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG';
    const code = {};
    let k = 0;
    for (const b1 of bases) for (const b2 of bases) for (const b3 of bases) code[b1 + b2 + b3] = aa[k++];
    return code;
  })();

  // Human (mammalian) preferred codon — the most frequent codon per amino acid
  // in Homo sapiens (Kazusa codon usage). Used to encode each new amino acid.
  const HUMAN_CODON = {
    A: 'GCC', R: 'CGG', N: 'AAC', D: 'GAC', C: 'TGC', Q: 'CAG', E: 'GAG', G: 'GGC',
    H: 'CAC', I: 'ATC', L: 'CTG', K: 'AAG', M: 'ATG', F: 'TTC', P: 'CCC', S: 'AGC',
    T: 'ACC', W: 'TGG', Y: 'TAC', V: 'GTG',
  };

  const AA_NAMES = {
    A: 'Ala', R: 'Arg', N: 'Asn', D: 'Asp', C: 'Cys', Q: 'Gln', E: 'Glu', G: 'Gly',
    H: 'His', I: 'Ile', L: 'Leu', K: 'Lys', M: 'Met', F: 'Phe', P: 'Pro', S: 'Ser',
    T: 'Thr', W: 'Trp', Y: 'Tyr', V: 'Val', '*': 'Stop',
  };

  // Display order for the toggle grid, grouped by property.
  const AA_ORDER = ['G', 'A', 'V', 'L', 'I', 'M', 'P', 'F', 'Y', 'W', 'S', 'T', 'C', 'N', 'Q', 'K', 'R', 'H', 'D', 'E'];

  const AA_GROUP = {
    G: 'Apolar', A: 'Apolar', V: 'Apolar', L: 'Apolar', I: 'Apolar', M: 'Apolar', P: 'Apolar',
    F: 'Aromático', Y: 'Aromático', W: 'Aromático',
    S: 'Polar', T: 'Polar', C: 'Polar', N: 'Polar', Q: 'Polar',
    K: 'Básico', R: 'Básico', H: 'Básico',
    D: 'Ácido', E: 'Ácido',
  };

  // Normalise a nucleotide string to uppercase ACGT (RNA U → T).
  function cleanNt(s) { return String(s == null ? '' : s).toUpperCase().replace(/U/g, 'T').replace(/[^ACGT]/g, ''); }

  function translateCodon(codon) { return GENETIC_CODE[String(codon).toUpperCase().replace(/U/g, 'T')] || 'X'; }

  // Analyse a nucleotide sequence as an ORF. Returns residues (one per codon,
  // 1-based pos), the amino-acid string, and human-readable warnings. `fatal` is
  // set only when the input can't be analysed at all.
  function analyzeOrf(ntRaw) {
    const nt = cleanNt(ntRaw);
    const out = { nt, len: nt.length, residues: [], aaString: '', warnings: [] };
    if (nt.length < 3) { out.fatal = 'La secuencia es demasiado corta para ser un ORF (hace falta al menos un codón de 3 nucleótidos).'; return out; }
    const nCodons = Math.floor(nt.length / 3);
    const residues = [];
    for (let i = 0; i < nCodons; i++) {
      const codon = nt.substr(i * 3, 3);
      residues.push({ pos: i + 1, aa: GENETIC_CODE[codon] || 'X', codon });
    }
    out.residues = residues;
    out.nCodons = nCodons;
    out.aaString = residues.map(r => r.aa).join('');
    out.multipleOf3 = (nt.length % 3 === 0);
    out.startsWithM = residues[0].aa === 'M';
    out.endsWithStop = residues[residues.length - 1].aa === '*';
    out.hasInternalStop = residues.some((r, idx) => r.aa === '*' && idx !== residues.length - 1);
    out.codingCount = residues.filter(r => r.aa !== '*').length;
    if (!out.multipleOf3) out.warnings.push('La longitud no es múltiplo de 3: puede que no sea un ORF completo o que el marco de lectura no empiece en el primer nucleótido.');
    if (!out.startsWithM) out.warnings.push('El primer codón no es ATG (Met): comprueba que has pegado el ORF desde su inicio.');
    if (out.hasInternalStop) out.warnings.push('Hay codón(es) de STOP internos: probablemente el marco de lectura no es el correcto.');
    if (!out.endsWithStop) out.warnings.push('El último codón no es un STOP: puede faltar el final del ORF (no afecta a la mutación puntual).');
    return out;
  }

  // Parse a position input ("168" or "G168") against a residues array. Validates
  // range, that it isn't a stop codon, and — if a letter is given — that the
  // original amino acid matches (a safety check against typos).
  //
  // `offset` maps the typed (wild-type) number to the real codon index in the ORF:
  // codonPos = typed + offset. It is 0 when the sequence matches the wild-type
  // numbering, and (1 - signalLength) when the plasmid's gene has NO signal
  // peptide but we still number as the wild-type (so G223 with a 23-aa signal
  // peptide targets codon 223 - 23 + 1 = 201). The returned `pos` is the typed
  // number (used for names/labels); `codonPos` is where the change is made.
  function parsePosition(input, residues, offset) {
    offset = offset || 0;
    const s = String(input == null ? '' : input).trim().toUpperCase();
    if (!s) return { error: 'Escribe la posición del aminoácido (por ejemplo 168 o G168).' };
    const m = s.match(/^([A-Z*]?)0*(\d+)$/);
    if (!m) return { error: 'Formato de posición no válido. Usa por ejemplo 168 o G168.' };
    const letter = m[1];
    const pos = parseInt(m[2], 10);
    if (!pos || pos < 1) return { error: 'La posición debe ser 1 o mayor.' };
    const codonPos = pos + offset;
    const where = offset ? ` (codón ${codonPos} del ORF)` : '';
    const r = (residues || []).find(x => x.pos === codonPos);
    if (!r) {
      if (codonPos < 1) return { error: `La posición ${pos} queda antes del inicio de la proteína en este plásmido (¿cae dentro del péptido señal?).` };
      return { error: `La posición ${pos}${where} está fuera del ORF (tiene ${(residues || []).length} codones).` };
    }
    if (r.aa === '*') return { error: `La posición ${pos}${where} es un codón STOP; no se puede mutar como aminoácido.` };
    if (r.aa === 'X') return { error: `La posición ${pos}${where} tiene un codón no reconocido (${r.codon}).` };
    if (letter && letter !== '*' && letter !== r.aa) {
      return { error: `En la posición ${pos}${where} el aminoácido es ${r.aa} (${AA_NAMES[r.aa] || '?'}), no ${letter}. Corrige la posición o el péptido señal.` };
    }
    return { pos, codonPos, orig: r.aa, origCodon: r.codon };
  }

  // Codon that will be used to encode `aa` (human-optimised). Preserves the RNA
  // alphabet if the template sequence uses U instead of T.
  function variantCodon(aa, likeSeq) {
    let codon = HUMAN_CODON[aa];
    if (!codon) return null;
    if (likeSeq && /U/i.test(likeSeq) && !/T/i.test(likeSeq)) codon = codon.replace(/T/g, 'U');
    return codon;
  }

  // Count nucleotide differences between two equal-length codons.
  function codonDistance(a, b) {
    a = String(a || '').toUpperCase().replace(/U/g, 'T'); b = String(b || '').toUpperCase().replace(/U/g, 'T');
    let n = 0; for (let i = 0; i < 3; i++) if (a[i] !== b[i]) n++;
    return n;
  }

  // Build the full variant ORF: the original sequence with the codon at 1-based
  // residue `pos` swapped for the human-optimised codon of `newAA`. Keeps the
  // template's own alphabet (T or U) and length. `origSeq` is the sequence exactly
  // as it will be matched in the .dna (NOT stripped of U), so we clean a copy for
  // indexing but splice into the original.
  function buildVariantNt(origSeq, pos, newAA) {
    const seq = String(origSeq == null ? '' : origSeq).toUpperCase();
    const i0 = (pos - 1) * 3;
    if (i0 + 3 > seq.length) throw new Error(`La posición ${pos} queda fuera de la secuencia.`);
    const codon = variantCodon(newAA, seq);
    if (!codon) throw new Error(`Aminoácido no válido: ${newAA}.`);
    return seq.slice(0, i0) + codon + seq.slice(i0 + 3);
  }

  return {
    GENETIC_CODE, HUMAN_CODON, AA_NAMES, AA_ORDER, AA_GROUP,
    cleanNt, translateCodon, analyzeOrf, parsePosition, variantCodon, codonDistance, buildVariantNt,
  };
});
