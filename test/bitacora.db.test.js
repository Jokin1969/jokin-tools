const { test } = require('node:test');
const assert = require('node:assert');
const { useTempDb, makeUser } = require('./helpers');

useTempDb();
const store = require('../apps/auth/store');
const bita = require('../apps/bitacora/db');

const A = makeUser(store, 'a@test.com');
const B = makeUser(store, 'b@test.com');

function seed() {
  bita.createEntry({ fecha: '2022-05-23', lugar: 'Lab', hecho: 'Pedí crear carpeta de Actas ya creada', nivel: 'Bajo', categoria: 'Repetición' }, A.id);
  bita.createEntry({ fecha: '2023-03-02', lugar: 'Garaje', hecho: 'No encontraba el mando del garaje', nivel: 'Bajo', categoria: 'Objeto extraviado', factores: 'Cansancio,Falta de sueño' }, A.id);
  bita.createEntry({ fecha: '2025-03-11', lugar: 'Lab', hecho: 'Creía que los compuestos eran P1-P4', nivel: 'Medio', categoria: 'Falso recuerdo', notado_otros: true, notado_quien: 'Hasier' }, A.id);
}

test('createEntry stores normalised fields', () => {
  const e = bita.createEntry({ fecha: '2024-01-01', hecho: 'x', nivel: 'PenpaBad', factores: 'Cansancio,Inventado', notado_otros: true, notado_quien: 'Ana' }, A.id);
  assert.equal(e.nivel, 'Bajo', 'invalid nivel falls back to Bajo');
  assert.equal(e.factores, 'Cansancio', 'unknown factor dropped, known kept');
  assert.equal(e.notado_otros, 1);
  assert.equal(e.notado_quien, 'Ana');
  bita.deleteEntry(e.id, A.id);
});

test('list + free-text search across fields', () => {
  seed();
  assert.equal(bita.listEntries({}, A.id).total, 3);
  assert.equal(bita.listEntries({ search: 'mando' }, A.id).total, 1);
  assert.equal(bita.listEntries({ search: 'compuestos' }, A.id).total, 1);
  assert.equal(bita.listEntries({ search: 'Hasier' }, A.id).total, 1, 'searches notado_quien too');
});

test('filters: nivel, categoria, factor, date range, notado', () => {
  assert.equal(bita.listEntries({ nivel: 'Medio' }, A.id).total, 1);
  assert.equal(bita.listEntries({ categoria: 'Objeto extraviado' }, A.id).total, 1);
  assert.equal(bita.listEntries({ factores: 'Cansancio' }, A.id).total, 1);
  assert.equal(bita.listEntries({ date_from: '2023-01-01', date_to: '2025-12-31' }, A.id).total, 2);
  assert.equal(bita.listEntries({ notado: '1' }, A.id).total, 1);
});

test('default sort is fecha desc', () => {
  const rows = bita.listEntries({}, A.id).rows;
  assert.equal(rows[0].fecha, '2025-03-11');
  assert.equal(rows[rows.length - 1].fecha, '2022-05-23');
});

test('stats reflect counts by nivel', () => {
  const s = bita.getStats(A.id);
  assert.equal(s.total, 3);
  assert.equal(s.byNivel.Bajo, 2);
  assert.equal(s.byNivel.Medio, 1);
  assert.equal(s.byNivel.Alto, 0);
});

test('per-user isolation: B sees nothing of A', () => {
  assert.equal(bita.listEntries({}, B.id).total, 0);
  const someAId = bita.listEntries({}, A.id).rows[0].id;
  assert.equal(bita.getEntryById(someAId, B.id), undefined, 'B cannot read A entry');
  assert.equal(bita.deleteEntry(someAId, B.id), false, 'B cannot delete A entry');
  // A still has all 3
  assert.equal(bita.listEntries({}, A.id).total, 3);
});

test('update is scoped to owner', () => {
  const id = bita.listEntries({}, A.id).rows[0].id;
  bita.updateEntry(id, { nivel: 'Alto' }, A.id);
  assert.equal(bita.getEntryById(id, A.id).nivel, 'Alto');
  // B's update is a no-op (row not theirs)
  bita.updateEntry(id, { nivel: 'Bajo' }, B.id);
  assert.equal(bita.getEntryById(id, A.id).nivel, 'Alto', 'B could not modify A row');
});

test('getInsights aggregates per year/categoria/lugar/month, scoped per user', () => {
  const ins = bita.getInsights(A.id);
  assert.equal(ins.total, 3);
  // Years: 2022, 2023, 2025 — one each.
  assert.deepEqual(ins.byYear.map(y => y.year), ['2022', '2023', '2025']);
  assert.ok(ins.byYear.every(y => y.n === 1));
  // Categorías ordered by frequency desc; here all distinct (1 each).
  assert.equal(ins.byCategoria.reduce((s, c) => s + c.n, 0), 3);
  assert.ok(ins.byCategoria.some(c => c.categoria === 'Falso recuerdo'));
  // Lugar: "Lab" appears twice → must be the top entry.
  assert.equal(ins.byLugar[0].lugar, 'Lab');
  assert.equal(ins.byLugar[0].n, 2);
  // Month: March (3) appears twice (2023-03, 2025-03).
  const march = ins.byMonth.find(m => m.month === 3);
  assert.equal(march.n, 2);
});

test('getInsights for a user with no entries is empty', () => {
  const ins = bita.getInsights(B.id);
  assert.equal(ins.total, 0);
  assert.deepEqual(ins.byYear, []);
  assert.deepEqual(ins.byCategoria, []);
});

test('getAllFiltered returns every matching row (unpaginated, fecha desc) for the report', () => {
  const all = bita.getAllFiltered({}, A.id);
  assert.equal(all.length, 3, 'all A entries, no pagination');
  // Always chronological, most recent first, regardless of any on-screen sort.
  assert.equal(all[0].fecha, '2025-03-11');
  assert.equal(all[all.length - 1].fecha, '2022-05-23');
  // Applies the same filters as the list.
  assert.equal(bita.getAllFiltered({ categoria: 'Objeto extraviado' }, A.id).length, 1);
  assert.equal(bita.getAllFiltered({ date_from: '2023-01-01' }, A.id).length, 2);
  assert.equal(bita.getAllFiltered({ search: 'mando' }, A.id).length, 1);
  // Scoped per user.
  assert.equal(bita.getAllFiltered({}, B.id).length, 0);
});
