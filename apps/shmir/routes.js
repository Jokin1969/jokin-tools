// ─── shmir-design dentro del hub ────────────────────────────────────────────────
//
// Todo lo que llegue a `/shmir` se reenvía al proceso de Streamlit, que corre en
// 127.0.0.1. Este router no pinta nada: la única página que hay es la de Streamlit.
//
// Lo que sí hace, y es lo que justifica que exista: **arrancar el proceso la primera
// vez** y, si no arranca, contestar con el motivo en vez de con un 502 mudo.
const express = require('express');
const path = require('node:path');

const proceso = require('./process');
const { proxyRequest } = require('./proxy');

const router = express.Router();

// El directorio de referencia de TRABAJO. En un despliegue tiene que estar en el volumen
// (/data) o lo que se suba desaparece en el siguiente redespliegue, y el único síntoma
// sería un frente que vuelve a salir NOT_RUN. En local, vacío = el del paquete.
const REFERENCE_DIR = process.env.SHMIR_REFERENCE_DIR
  || (process.env.NODE_ENV === 'production'
    ? path.join(path.dirname(process.env.DB_PATH || '/data/jokin_tools.db'), 'shmir', 'reference')
    : '');

function referenceDir() {
  return REFERENCE_DIR;
}

// Siembra: lo versionado se copia al directorio de trabajo la PRIMERA vez y no se
// vuelve a pisar. Se hace desde Node —y no desde el arranque de Streamlit— para que un
// fallo de permisos sobre el volumen se vea en el log del despliegue y no en la cara del
// usuario. La lógica de qué se copia y qué se respeta vive en `shmir_design/trabajo.py`,
// con tests; aquí sólo se invoca.
let sembrado = false;
function sembrar() {
  if (sembrado || !REFERENCE_DIR) return { ok: true, skipped: true };
  const { spawnSync } = require('node:child_process');
  const r = spawnSync(
    proceso.PYTHON_BIN || 'python3',
    ['-c',
      'import sys; sys.path.insert(0, sys.argv[1]);'
      + ' from shmir_design.trabajo import seed_reference_dir;'
      + ' print(seed_reference_dir(sys.argv[2]).render())',
      proceso.SHMIR_ROOT, REFERENCE_DIR],
    { encoding: 'utf8', env: { ...process.env } }
  );
  if (r.status !== 0) {
    return { ok: false, reason: (r.stderr || r.stdout || '').trim() };
  }
  sembrado = true;
  console.log('[shmir] ' + (r.stdout || '').trim().split('\n').join('\n[shmir] '));
  return { ok: true, skipped: false };
}

router.use(async (req, res) => {
  const siembra = sembrar();
  if (!siembra.ok) {
    res.status(503).type('text/plain; charset=utf-8');
    return res.send(
      'shmir-design no está disponible: no se pudo preparar su directorio de ficheros '
      + `de referencia (${REFERENCE_DIR}).\n\n${siembra.reason}\n\n`
      + 'Sin él, todo lo que se suba desaparecería en el siguiente despliegue, así que '
      + 'se para aquí en vez de arrancar y perderlo después.'
    );
  }
  const arranque = await proceso.ensureRunning({ referenceDir: REFERENCE_DIR });
  if (!arranque.ok) {
    res.status(503).type('text/plain; charset=utf-8');
    return res.send(
      'shmir-design no está disponible ahora mismo.\n\n'
      + `${arranque.reason}\n\n`
      + 'El resto del hub no se ve afectado, y el núcleo de shmir-design sigue '
      + 'funcionando por línea de órdenes: la interfaz es la única parte que necesita '
      + 'Streamlit.'
    );
  }
  return proxyRequest(req, res, { port: proceso.PORT });
});

module.exports = router;
module.exports.referenceDir = referenceDir;
