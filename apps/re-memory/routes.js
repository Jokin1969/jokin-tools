const express = require('express');
const path = require('path');
const fs = require('fs');
const multer = require('multer');
const crypto = require('crypto');
const fetch = require('node-fetch');

const router = express.Router();

const {
  createMemory, getMemoryById, listMemories, updateMemory,
  deleteMemory, toggleMemory, resetCounter, getAllIds, getAllMemoriesForExport
} = require('./db');

const { sendMemoryEmail, generateDeactivationToken } = require('./email');
const { exportToDropbox, getAuthorizationUrl, exchangeCodeForTokens } = require('./dropbox');
const { startCron } = require('./cron');

// ─── Start cron when routes are loaded ───────────────────────────────────────
startCron();

// ─── Multer setup (images → /data/uploads/) ──────────────────────────────────
const uploadsDir = path.join(path.dirname(process.env.DB_PATH || '/data/jokin_tools.db'), 'uploads');
if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir, { recursive: true });

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadsDir),
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    cb(null, `memory-${Date.now()}-${Math.random().toString(36).slice(2)}${ext}`);
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10 MB
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('image/')) cb(null, true);
    else cb(new Error('Only image files are allowed'));
  }
});

// ─── Serve Re-memory frontend ─────────────────────────────────────────────────
router.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

router.use('/public', express.static(path.join(__dirname, 'public')));

// ─── API: Config diagnostic (muestra BASE_URL activa sin exponer secrets) ─────
router.get('/api/config-check', (req, res) => {
  const baseUrl = process.env.BASE_URL || '(no definida)';
  const smtpUser = process.env.SMTP_USER ? process.env.SMTP_USER.replace(/(.{3}).*(@.*)/, '$1***$2') : '(no definida)';
  const deactivationSecret = process.env.DEACTIVATION_SECRET ? '✓ definida' : '✗ usa valor por defecto (inseguro)';
  const dbPath = process.env.DB_PATH || '(no definida, usando /data/jokin_tools.db)';

  res.json({
    BASE_URL: baseUrl,
    BASE_URL_ok: baseUrl.startsWith('https://'),
    SMTP_USER: smtpUser,
    DEACTIVATION_SECRET: deactivationSecret,
    DB_PATH: dbPath,
    uploads_dir: uploadsDir,
    node_env: process.env.NODE_ENV || '(no definida)'
  });
});

// ─── API: List memories ───────────────────────────────────────────────────────
router.get('/api/memories', (req, res) => {
  try {
    const result = listMemories(req.query);
    res.json(result);
  } catch (err) {
    console.error('[api] listMemories error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Get all IDs (for client-side prev/next navigation) ─────────────────
router.get('/api/ids', (req, res) => {
  try {
    const ids = getAllIds(req.query.sort, req.query.order);
    res.json(ids);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Get one memory ──────────────────────────────────────────────────────
router.get('/api/memories/:id', (req, res) => {
  try {
    const memory = getMemoryById(Number(req.params.id));
    if (!memory) return res.status(404).json({ error: 'Memory not found' });
    res.json(memory);
  } catch (err) {
    console.error('[api] getMemory error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Create memory ───────────────────────────────────────────────────────
router.post('/api/memories', (req, res) => {
  try {
    const { description, frequency, topic, source_url, active } = req.body;
    if (!description || !frequency || !topic) {
      return res.status(400).json({ error: 'description, frequency and topic are required' });
    }
    const memory = createMemory({ description, frequency, topic, source_url, active });
    res.status(201).json(memory);
  } catch (err) {
    console.error('[api] createMemory error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Update memory ───────────────────────────────────────────────────────
router.put('/api/memories/:id', (req, res) => {
  try {
    const id = Number(req.params.id);
    const existing = getMemoryById(id);
    if (!existing) return res.status(404).json({ error: 'Memory not found' });
    const memory = updateMemory(id, req.body);
    res.json(memory);
  } catch (err) {
    console.error('[api] updateMemory error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Delete memory ───────────────────────────────────────────────────────
router.delete('/api/memories/:id', (req, res) => {
  try {
    const id = Number(req.params.id);
    const existing = getMemoryById(id);
    if (!existing) return res.status(404).json({ error: 'Memory not found' });

    // Delete image file if exists
    if (existing.image_path) {
      const imgPath = path.join(uploadsDir, path.basename(existing.image_path));
      if (fs.existsSync(imgPath)) fs.unlinkSync(imgPath);
    }

    deleteMemory(id);
    res.json({ success: true });
  } catch (err) {
    console.error('[api] deleteMemory error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Toggle active/inactive ─────────────────────────────────────────────
router.patch('/api/memories/:id/toggle', (req, res) => {
  try {
    const memory = toggleMemory(Number(req.params.id));
    if (!memory) return res.status(404).json({ error: 'Memory not found' });
    res.json(memory);
  } catch (err) {
    console.error('[api] toggleMemory error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Reset counter ───────────────────────────────────────────────────────
router.post('/api/memories/:id/reset-counter', (req, res) => {
  try {
    const id = Number(req.params.id);
    const existing = getMemoryById(id);
    if (!existing) return res.status(404).json({ error: 'Memory not found' });
    const memory = resetCounter(id);
    res.json(memory);
  } catch (err) {
    console.error('[api] resetCounter error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Upload image ────────────────────────────────────────────────────────
router.post('/api/memories/:id/image', upload.single('image'), (req, res) => {
  try {
    const id = Number(req.params.id);
    const existing = getMemoryById(id);
    if (!existing) return res.status(404).json({ error: 'Memory not found' });
    if (!req.file) return res.status(400).json({ error: 'No image file provided' });

    // Remove old image if exists
    if (existing.image_path) {
      const oldPath = path.join(uploadsDir, path.basename(existing.image_path));
      if (fs.existsSync(oldPath)) fs.unlinkSync(oldPath);
    }

    const relativePath = req.file.filename;
    const memory = updateMemory(id, { image_path: relativePath });
    res.json({ image_path: relativePath, memory });
  } catch (err) {
    console.error('[api] uploadImage error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Test email ──────────────────────────────────────────────────────────
router.post('/api/test-email/:id', async (req, res) => {
  try {
    const memory = getMemoryById(Number(req.params.id));
    if (!memory) return res.status(404).json({ error: 'Memory not found' });
    await sendMemoryEmail(memory);
    res.json({ success: true, message: 'Test email sent' });
  } catch (err) {
    console.error('[api] testEmail error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Deactivate from email link ─────────────────────────────────────────
router.get('/api/deactivate/:id/:token', (req, res) => {
  try {
    const id = Number(req.params.id);
    const token = req.params.token;
    const expected = generateDeactivationToken(id);

    if (!crypto.timingSafeEqual(Buffer.from(token), Buffer.from(expected))) {
      return res.status(403).send('<h2>Token inválido</h2>');
    }

    const memory = getMemoryById(id);
    if (!memory) return res.status(404).send('<h2>Memoria no encontrada</h2>');

    if (memory.active) {
      updateMemory(id, { active: 0 });
    }

    res.send(`<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"/>
      <title>Re-memory — Desactivado</title>
      <style>body{background:#0d1117;color:#e6edf3;font-family:monospace;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center}
      .box{max-width:400px;padding:40px;background:#161b22;border:1px solid #21262d;border-radius:12px}
      h2{color:#27AE60;margin-bottom:12px}p{color:#7d8590;font-size:14px}
      a{color:#2D9CDB;text-decoration:none}</style>
    </head><body>
      <div class="box">
        <h2>✓ Recordatorio desactivado</h2>
        <p>La memoria "<strong>${memory.description.substring(0,80)}</strong>" ya no te enviará más correos.</p>
        <p style="margin-top:16px"><a href="/re-memory">Ir a Re-memory →</a></p>
      </div>
    </body></html>`);
  } catch (err) {
    console.error('[api] deactivate error:', err);
    res.status(500).send('<h2>Error al desactivar</h2>');
  }
});

// ─── API: Export CSV to Dropbox ───────────────────────────────────────────────
router.get('/api/export/csv', async (req, res) => {
  try {
    const result = await exportToDropbox();
    res.json({
      success: true,
      path: result.path,
      filename: result.filename,
      rows: result.rows,
      size: result.size,
      message: `Exportado ${result.rows} registros a Dropbox: ${result.path}`
    });
  } catch (err) {
    console.error('[api] exportCSV error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Claude AI assist ────────────────────────────────────────────────────
const CLAUDE_SYSTEM_PROMPT = `Cada vez que te mande información, resúmela en una descripción en prosa concisa, priorizando los detalles más importantes y memorables. Sin bullet points, sin campo de tema. Añade al final una URL relevante. Para palabras entre comillas: definición RAE y etimología. Para refranes: significado y origen. Si solo te doy un nombre o tema sin texto, búscalo tú.

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional antes ni después, con este formato exacto:
{
  "description": "prosa concisa sin bullet points",
  "url": "URL más relevante o null",
  "imageUrl": "URL directa a imagen representativa de Wikipedia Commons u otra fuente pública libre, o null"
}

Para imageUrl: busca una imagen representativa en Wikipedia Commons (URL directa al archivo, no a la página).`;

router.post('/api/claude-assist', async (req, res) => {
  const { topic } = req.body;
  if (!topic || !topic.trim()) {
    return res.status(400).json({ error: 'El campo topic es obligatorio' });
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return res.status(503).json({ error: 'ANTHROPIC_API_KEY no configurada' });
  }

  try {
    const Anthropic = require('@anthropic-ai/sdk');
    const client = new Anthropic({ apiKey });

    const stream = client.messages.stream({
      model: 'claude-opus-4-7',
      max_tokens: 2048,
      system: [{ type: 'text', text: CLAUDE_SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
      tools: [{ type: 'web_search_20260209', name: 'web_search' }],
      messages: [{ role: 'user', content: topic.trim() }]
    });

    const message = await stream.finalMessage();

    const textBlock = message.content.find(b => b.type === 'text');
    if (!textBlock) {
      return res.status(500).json({ error: 'Claude no devolvió texto' });
    }

    const jsonMatch = textBlock.text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return res.status(500).json({ error: 'No se pudo parsear la respuesta de Claude', raw: textBlock.text });
    }

    const data = JSON.parse(jsonMatch[0]);
    res.json({
      description: data.description || null,
      url: data.url || null,
      imageUrl: data.imageUrl || null
    });
  } catch (err) {
    console.error('[claude-assist] error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Proxy image (CORS-safe preview) ────────────────────────────────────
router.get('/api/proxy-image', async (req, res) => {
  const url = req.query.url;
  if (!url) return res.status(400).json({ error: 'url requerida' });

  try {
    const parsed = new URL(url);
    const allowedHosts = ['upload.wikimedia.org', 'commons.wikimedia.org', 'en.wikipedia.org',
      'es.wikipedia.org', 'upload.wikipedia.org', 'images.wikimedia.org'];
    if (!allowedHosts.some(h => parsed.hostname.endsWith(h))) {
      return res.status(403).json({ error: 'Dominio no permitido para proxy' });
    }

    const response = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; JokinTools/1.0)' }
    });

    if (!response.ok) {
      return res.status(response.status).json({ error: `Upstream ${response.status}` });
    }

    const ct = response.headers.get('content-type') || 'image/jpeg';
    if (!ct.startsWith('image/')) {
      return res.status(400).json({ error: 'URL no es una imagen' });
    }

    res.set('Content-Type', ct);
    res.set('Cache-Control', 'public, max-age=3600');
    response.body.pipe(res);
  } catch (err) {
    console.error('[proxy-image] error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ─── Dropbox OAuth2 setup (first deploy only) ─────────────────────────────────
router.get('/auth/dropbox', (req, res) => {
  try {
    const url = getAuthorizationUrl();
    res.redirect(url);
  } catch (err) {
    res.status(500).send(`<pre>Error: ${err.message}</pre>`);
  }
});

router.get('/auth/dropbox/callback', async (req, res) => {
  const { code, error } = req.query;
  if (error) return res.status(400).send(`<pre>Dropbox error: ${error}</pre>`);
  if (!code) return res.status(400).send('<pre>No code received</pre>');

  try {
    const tokens = await exchangeCodeForTokens(code);
    res.send(`<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"/>
      <title>Dropbox Auth</title>
      <style>body{background:#0d1117;color:#e6edf3;font-family:monospace;padding:40px;max-width:700px;margin:0 auto}
      pre{background:#161b22;padding:20px;border-radius:8px;border:1px solid #21262d;overflow-x:auto;color:#27AE60}
      h2{color:#2D9CDB}p{color:#7d8590}</style>
    </head><body>
      <h2>✓ Autorización completada</h2>
      <p>Copia el <code>refresh_token</code> y añádelo como variable de entorno <code>DROPBOX_REFRESH_TOKEN</code> en Railway:</p>
      <pre>${JSON.stringify(tokens, null, 2)}</pre>
      <p>Una vez configurado, elimina o protege este endpoint de tu código.</p>
    </body></html>`);
  } catch (err) {
    res.status(500).send(`<pre>Error: ${err.message}</pre>`);
  }
});

module.exports = router;
