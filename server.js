require('dotenv').config();
const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// ─── Ensure /data directories exist ─────────────────────────────────────────
const dataDir = path.dirname(process.env.DB_PATH || '/data/jokin_tools.db');
const uploadsDir = path.join(dataDir, 'uploads');
[dataDir, uploadsDir].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`[server] Created directory: ${dir}`);
  }
});

// ─── Middleware ───────────────────────────────────────────────────────────────
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve uploaded files from /data/uploads
app.use('/uploads', express.static(uploadsDir));

// Serve shared public assets (favicons, logos)
app.use('/public', express.static(path.join(__dirname, 'public')));

// ─── Hub frontend ─────────────────────────────────────────────────────────────
app.use('/src', express.static(path.join(__dirname, 'src')));

// ─── Re-memory micro-app ─────────────────────────────────────────────────────
const reMemoryRouter = require('./apps/re-memory/routes');
app.use('/re-memory', reMemoryRouter);

// ─── Hub root ─────────────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'src', 'index.html'));
});

// Favicon hub principal
app.get('/favicon.ico', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'favicon-jk.svg'), {
    headers: { 'Content-Type': 'image/svg+xml' }
  }, (err) => {
    if (err) res.status(204).end();
  });
});

// ─── 404 handler ─────────────────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// ─── Global error handler ─────────────────────────────────────────────────────
app.use((err, req, res, next) => {
  console.error('[server] Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error', message: err.message });
});

// ─── Start ────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`[server] Jokin's Tools running on port ${PORT}`);
  console.log(`[server] DB path: ${process.env.DB_PATH || '/data/jokin_tools.db'}`);
  console.log(`[server] NODE_ENV: ${process.env.NODE_ENV || 'development'}`);
});

module.exports = app;
