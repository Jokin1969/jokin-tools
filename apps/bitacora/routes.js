const express = require('express');
const path = require('path');
const router = express.Router();

const {
  NIVELES, CATEGORIAS, FACTORES,
  createEntry, getEntryById, updateEntry, deleteEntry,
  listEntries, getAllIds, getStats, getInsights, getAllForExport,
} = require('./db');
const { exportToDropbox } = require('./dropbox');

// ─── Frontend ───────────────────────────────────────────────────────────────────
router.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});
router.use('/public', express.static(path.join(__dirname, 'public')));

// ─── Reference data for the form (niveles, categorías, factores) ───────────────
router.get('/api/meta', (req, res) => {
  res.json({ niveles: NIVELES, categorias: CATEGORIAS, factores: FACTORES });
});

// ─── List / search ──────────────────────────────────────────────────────────────
router.get('/api/entries', (req, res) => {
  try {
    res.json(listEntries(req.query, req.user.id));
  } catch (err) {
    console.error('[bitacora] list error:', err);
    res.status(500).json({ error: err.message });
  }
});

router.get('/api/ids', (req, res) => {
  try {
    res.json(getAllIds(req.query.sort, req.query.order, req.user.id));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.get('/api/stats', (req, res) => {
  try {
    res.json(getStats(req.user.id));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Aggregations for the patterns panel (per year / categoría / lugar / month).
router.get('/api/insights', (req, res) => {
  try {
    res.json(getInsights(req.user.id));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Get one ────────────────────────────────────────────────────────────────────
router.get('/api/entries/:id', (req, res) => {
  const entry = getEntryById(Number(req.params.id), req.user.id);
  if (!entry) return res.status(404).json({ error: 'Entrada no encontrada' });
  res.json(entry);
});

// ─── Create ─────────────────────────────────────────────────────────────────────
router.post('/api/entries', (req, res) => {
  try {
    const { fecha, hecho } = req.body;
    if (!fecha || !/^\d{4}-\d{2}-\d{2}$/.test(fecha)) {
      return res.status(400).json({ error: 'La fecha es obligatoria (formato YYYY-MM-DD).' });
    }
    if (!hecho || !hecho.trim()) {
      return res.status(400).json({ error: 'El hecho es obligatorio.' });
    }
    const entry = createEntry(req.body, req.user.id);
    res.status(201).json(entry);
  } catch (err) {
    console.error('[bitacora] create error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── Update ─────────────────────────────────────────────────────────────────────
router.put('/api/entries/:id', (req, res) => {
  try {
    const id = Number(req.params.id);
    if (!getEntryById(id, req.user.id)) return res.status(404).json({ error: 'Entrada no encontrada' });
    if (req.body.fecha !== undefined && !/^\d{4}-\d{2}-\d{2}$/.test(req.body.fecha)) {
      return res.status(400).json({ error: 'Fecha inválida (formato YYYY-MM-DD).' });
    }
    res.json(updateEntry(id, req.body, req.user.id));
  } catch (err) {
    console.error('[bitacora] update error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── Delete ─────────────────────────────────────────────────────────────────────
router.delete('/api/entries/:id', (req, res) => {
  const id = Number(req.params.id);
  if (!getEntryById(id, req.user.id)) return res.status(404).json({ error: 'Entrada no encontrada' });
  deleteEntry(id, req.user.id);
  res.json({ success: true });
});

// ─── Export CSV to Dropbox (per user) ──────────────────────────────────────────
router.get('/api/export/csv', async (req, res) => {
  try {
    const result = await exportToDropbox(req.user.id);
    res.json({ success: true, ...result, message: `Exportadas ${result.rows} entradas a Dropbox: ${result.path}` });
  } catch (err) {
    console.error('[bitacora] export error:', err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
