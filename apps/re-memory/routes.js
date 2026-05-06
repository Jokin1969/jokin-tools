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
const { createBackup, listBackups, restoreBackup } = require('./backup');
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

// ─── Wikipedia image lookup ──────────────────────────────────────────────────
async function getWikipediaImage(query, lang = 'es') {
  try {
    const searchRes = await fetch(
      `https://${lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch=${encodeURIComponent(query)}&format=json&srlimit=1&origin=*`,
      { headers: { 'User-Agent': 'JokinTools/1.0 (jokin-tools)' } }
    );
    if (!searchRes.ok) return lang === 'es' ? getWikipediaImage(query, 'en') : null;
    const searchData = await searchRes.json();
    const hit = searchData.query?.search?.[0];
    if (!hit) return lang === 'es' ? getWikipediaImage(query, 'en') : null;

    const imgRes = await fetch(
      `https://${lang}.wikipedia.org/w/api.php?action=query&titles=${encodeURIComponent(hit.title)}&prop=pageimages&format=json&pithumbsize=500&origin=*`,
      { headers: { 'User-Agent': 'JokinTools/1.0 (jokin-tools)' } }
    );
    if (!imgRes.ok) return lang === 'es' ? getWikipediaImage(query, 'en') : null;
    const imgData = await imgRes.json();
    const thumbnail = Object.values(imgData.query?.pages || {})[0]?.thumbnail?.source || null;
    if (!thumbnail && lang === 'es') return getWikipediaImage(query, 'en');
    return thumbnail;
  } catch (_) {
    return lang === 'es' ? getWikipediaImage(query, 'en') : null;
  }
}

// ─── API: Claude AI assist ────────────────────────────────────────────────────
const CLAUDE_SYSTEM_PROMPT = `Eres un asistente que responde EXCLUSIVAMENTE con JSON puro. Sin texto antes ni después. Sin bloques de código markdown. Sin explicaciones.

Cuando recibas un tema o texto, devuelve SOLO este objeto JSON (nada más):
{"description":"descripción en prosa concisa sin bullet points, priorizando los detalles más memorables. Para palabras entre comillas: definición RAE y etimología. Para refranes: significado y origen. Si solo recibes un nombre o tema, búscalo","url":"URL más relevante o null","imageQuery":"término de búsqueda en Wikipedia que mejor represente visualmente el tema, o null","topic":"el tema que mejor encaja de esta lista exacta: Cultura general, Refranes, Ciencia, Historia, Geografía, Cinematografía, Naturaleza, Tecnología, Definiciones, Miscelánea"}

Reglas estrictas:
- SOLO JSON, sin texto adicional
- description: prosa continua, sin guiones ni viñetas
- url: la fuente más relevante o null (no una cadena vacía)
- imageQuery: término concreto (ej: "fotosíntesis", "Torre Eiffel", "Nikola Tesla") o null
- topic: elige EXACTAMENTE uno de los 10 valores de la lista, sin variaciones`;

function extractJSON(text) {
  // Strategy 1: fenced code block ```json { ... } ```
  const fenced = text.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/);
  if (fenced) {
    try { return JSON.parse(fenced[1]); } catch (_) {}
  }
  // Strategy 2: first complete top-level JSON object
  const start = text.indexOf('{');
  if (start !== -1) {
    let depth = 0;
    for (let i = start; i < text.length; i++) {
      if (text[i] === '{') depth++;
      else if (text[i] === '}') {
        depth--;
        if (depth === 0) {
          try { return JSON.parse(text.slice(start, i + 1)); } catch (_) {}
        }
      }
    }
  }
  return null;
}

router.post('/api/claude-assist', async (req, res) => {
  const { topic } = req.body;
  if (!topic || !topic.trim()) return res.status(400).json({ error: 'El campo topic es obligatorio' });
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return res.status(503).json({ error: 'ANTHROPIC_API_KEY no configurada' });
  try {
    const data = await callClaude(topic.trim());
    res.json(data);
  } catch (err) {
    console.error('[claude-assist] error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Unified AI assist (Claude / OpenAI / Gemini) ───────────────────────
const AI_SYSTEM_PROMPT = CLAUDE_SYSTEM_PROMPT; // same prompt for all providers

const VALID_TOPICS = ['Cultura general','Refranes','Ciencia','Historia','Geografía',
  'Cinematografía','Naturaleza','Tecnología','Definiciones','Miscelánea'];

async function aiResultWithImage(data) {
  const imageUrl = data.imageQuery ? await getWikipediaImage(data.imageQuery) : null;
  const topic = VALID_TOPICS.includes(data.topic) ? data.topic : null;
  return { description: data.description || null, url: data.url || null, imageUrl, topic };
}

async function callClaude(topic) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY no configurada');
  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic({ apiKey });
  const message = await client.messages.create({
    model: 'claude-opus-4-7',
    max_tokens: 2048,
    system: [{ type: 'text', text: AI_SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
    messages: [{ role: 'user', content: topic }]
  });
  const textBlock = message.content.find(b => b.type === 'text');
  if (!textBlock) {
    console.error('[claude] no text block. stop_reason=%s types=%s', message.stop_reason, message.content.map(b => b.type).join(','));
    throw new Error(`Claude no devolvió texto (stop_reason: ${message.stop_reason})`);
  }
  const data = extractJSON(textBlock.text);
  if (!data) { console.error('[claude] JSON parse failed. raw:\n%s', textBlock.text); throw new Error('No se pudo parsear la respuesta de Claude'); }
  return aiResultWithImage(data);
}

async function callOpenAI(topic) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('OPENAI_API_KEY no configurada');
  const { default: OpenAI } = require('openai');
  const client = new OpenAI({ apiKey });
  const response = await client.chat.completions.create({
    model: 'gpt-4o',
    max_tokens: 2048,
    response_format: { type: 'json_object' },
    messages: [
      { role: 'system', content: AI_SYSTEM_PROMPT },
      { role: 'user',   content: topic }
    ]
  });
  const text = response.choices[0]?.message?.content || '';
  const data = extractJSON(text);
  if (!data) { console.error('[openai] JSON parse failed. raw:\n%s', text); throw new Error('No se pudo parsear la respuesta de OpenAI'); }
  return aiResultWithImage(data);
}

async function callGemini(topic) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) throw new Error('GEMINI_API_KEY no configurada');
  const { GoogleGenerativeAI } = require('@google/generative-ai');
  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({
    model: 'gemini-2.0-flash',
    systemInstruction: AI_SYSTEM_PROMPT,
    generationConfig: { responseMimeType: 'application/json', maxOutputTokens: 2048 }
  });
  const result = await model.generateContent(topic);
  const text = result.response.text();
  const data = extractJSON(text);
  if (!data) { console.error('[gemini] JSON parse failed. raw:\n%s', text); throw new Error('No se pudo parsear la respuesta de Gemini'); }
  return aiResultWithImage(data);
}

router.post('/api/ai-assist', async (req, res) => {
  const { topic, provider = 'claude' } = req.body;
  if (!topic || !topic.trim()) return res.status(400).json({ error: 'El campo topic es obligatorio' });
  try {
    let data;
    if      (provider === 'claude') data = await callClaude(topic.trim());
    else if (provider === 'openai') data = await callOpenAI(topic.trim());
    else if (provider === 'gemini') data = await callGemini(topic.trim());
    else return res.status(400).json({ error: `Proveedor desconocido: ${provider}` });
    res.json(data);
  } catch (err) {
    console.error(`[ai-assist:${provider}] error:`, err.message);
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

// ─── API: Backup — crear ──────────────────────────────────────────────────────
router.post('/api/backup/create', async (req, res) => {
  try {
    const result = await createBackup();
    res.json({
      success: true,
      ...result,
      message: `Backup creado: ${result.filename}`
    });
  } catch (err) {
    console.error('[api] createBackup error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Backup — listar ─────────────────────────────────────────────────────
router.get('/api/backup/list', async (req, res) => {
  try {
    const backups = await listBackups();
    res.json({
      backups,
      count: backups.length,
      max: parseInt(process.env.BACKUP_MAX_COUNT || '100', 10)
    });
  } catch (err) {
    console.error('[api] listBackups error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ─── API: Backup — restaurar ──────────────────────────────────────────────────
router.post('/api/backup/restore/:filename', async (req, res) => {
  try {
    const { filename } = req.params;
    if (!filename.endsWith('.db') || /[/\\]/.test(filename) || filename.includes('..')) {
      return res.status(400).json({ error: 'Nombre de fichero inválido' });
    }
    const result = await restoreBackup(filename);
    res.json({
      success: true,
      ...result,
      message: `Backup restaurado correctamente: ${result.filename}`
    });
  } catch (err) {
    console.error('[api] restoreBackup error:', err);
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
