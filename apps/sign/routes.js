const express = require('express');
const path = require('path');
const router = express.Router();

// Servir HTML principal
router.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Servir assets estáticos
router.use('/public', express.static(path.join(__dirname, 'public')));

// Health check
router.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

module.exports = router;
