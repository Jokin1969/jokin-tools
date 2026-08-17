const { test } = require('node:test');
const assert = require('node:assert');
const bio = require('../apps/batchwork/public/bio.js');

test('genetic code translates the classic codons', () => {
  assert.equal(bio.translateCodon('ATG'), 'M');
  assert.equal(bio.translateCodon('TGG'), 'W');
  assert.equal(bio.translateCodon('TAA'), '*');
  assert.equal(bio.translateCodon('TAG'), '*');
  assert.equal(bio.translateCodon('TGA'), '*');
  assert.equal(bio.translateCodon('GGT'), 'G');
  assert.equal(bio.translateCodon('AUG'), 'M'); // RNA accepted
});

test('analyzeOrf: clean ORF starting with M, ending in stop', () => {
  // M A G * : ATG GCC GGT TAA
  const a = bio.analyzeOrf('ATGGCCGGTTAA');
  assert.equal(a.fatal, undefined);
  assert.equal(a.nCodons, 4);
  assert.equal(a.aaString, 'MAG*');
  assert.equal(a.startsWithM, true);
  assert.equal(a.endsWithStop, true);
  assert.equal(a.hasInternalStop, false);
  assert.equal(a.multipleOf3, true);
  assert.equal(a.codingCount, 3);
  assert.deepEqual(a.residues[0], { pos: 1, aa: 'M', codon: 'ATG' });
});

test('analyzeOrf warns on frame problems', () => {
  const notMult3 = bio.analyzeOrf('ATGGCCGG');
  assert.ok(notMult3.warnings.some(w => /múltiplo de 3/.test(w)));
  const noMet = bio.analyzeOrf('GCCGGTTAA');
  assert.ok(noMet.warnings.some(w => /ATG/.test(w)));
  const internalStop = bio.analyzeOrf('ATGTAAGGT'); // M * G
  assert.equal(internalStop.hasInternalStop, true);
});

test('parsePosition accepts 168 and G168, validates the original residue', () => {
  // Build an ORF where residue 2 is Gly (GGT). ATG GGT GCC TAA
  const res = bio.analyzeOrf('ATGGGTGCCTAA').residues;
  const p = bio.parsePosition('2', res);
  assert.equal(p.pos, 2); assert.equal(p.orig, 'G'); assert.equal(p.origCodon, 'GGT');
  const pLetter = bio.parsePosition('G2', res);
  assert.equal(pLetter.orig, 'G');
  const padded = bio.parsePosition('G002', res);
  assert.equal(padded.pos, 2);
  // wrong letter caught
  const wrong = bio.parsePosition('A2', res);
  assert.match(wrong.error, /original es G/);
  // out of range
  assert.match(bio.parsePosition('99', res).error, /fuera del ORF/);
  // stop codon position rejected (pos 4 = TAA)
  assert.match(bio.parsePosition('4', res).error, /STOP/);
  // garbage
  assert.match(bio.parsePosition('abc', res).error, /no válido/);
});

test('buildVariantNt swaps exactly one codon using the human-optimised codon', () => {
  const orf = 'ATGGGTGCCTAA';            // M G A *
  // Mutate position 2 (Gly) → Val. Human Val codon = GTG.
  const v = bio.buildVariantNt(orf, 2, 'V');
  assert.equal(v, 'ATGGTGGCCTAA');
  assert.equal(v.length, orf.length);      // same length (delta 0)
  // Only the second codon differs.
  assert.equal(bio.analyzeOrf(v).aaString, 'MVA*');
  // Mutate position 3 (Ala) → Trp (TGG).
  assert.equal(bio.buildVariantNt(orf, 3, 'W'), 'ATGGGTTGGTAA');
});

test('variantCodon preserves RNA alphabet and codonDistance counts nt changes', () => {
  assert.equal(bio.variantCodon('V'), 'GTG');
  assert.equal(bio.variantCodon('V', 'AUGGGU'), 'GUG'); // RNA template → U
  assert.equal(bio.codonDistance('GGT', 'GTG'), 2);
  assert.equal(bio.codonDistance('GCC', 'GCC'), 0);
});

test('the 19 variants exclude the original amino acid', () => {
  const orig = 'G';
  const variants = bio.AA_ORDER.filter(a => a !== orig);
  assert.equal(variants.length, 19);
  assert.ok(!variants.includes('G'));
  assert.equal(new Set(bio.AA_ORDER).size, 20);
});
