const express = require('express');
const router = express.Router();

// Esta app no requiere persistencia ni autenticación especial
// Solo sirve archivos estáticos. Las rutas adicionales son opcionales.

// Health check
router.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

module.exports = router;
