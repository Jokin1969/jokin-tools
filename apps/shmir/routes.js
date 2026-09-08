// ─── shmir-design dentro del hub ────────────────────────────────────────────────
//
// Todo lo que llegue a `/shmir` se reenvía al proceso de Streamlit, que corre en
// 127.0.0.1. Este router no pinta nada: la única página que hay es la de Streamlit.
//
// Lo que sí hace, y es lo que justifica que exista: **arrancar el proceso la primera
// vez** y, si no arranca, contestar con el motivo en vez de con un 502 mudo.
const express = require('express');
const fs = require('node:fs');
const path = require('node:path');

const proceso = require('./process');
const { proxyRequest } = require('./proxy');

const router = express.Router();

// EL ANCLA ES EL VOLUMEN, NO `NODE_ENV` (errata nº 153).
//
// Esto colgaba de `process.env.NODE_ENV === 'production'`, y el 2026-09-08 los proyectos
// dejaron de aparecer después de más de treinta despliegues buenos. Medido sobre la
// derivación anterior:
//
//   production + DB_PATH        -> /data/shmir/proyectos
//   production SIN DB_PATH      -> /data/shmir/proyectos   (el defecto ya lo cubría)
//   SIN NODE_ENV, con DB_PATH   -> ''                      <- el hijo se queda sin nada
//   NODE_ENV mal escrito        -> ''
//
// O sea que **que falte `DB_PATH` no vacía nada**, y el ÚNICO interruptor capaz de dejar
// esto vacío era `NODE_ENV` — una bandera que este repositorio **no declara, no prueba y
// no ve**: la pone el constructor de la plataforma. De ella colgaba el registro de lo que
// se decidió, y su fallo es silencioso: la app arranca, funciona, y escribe donde no
// sobrevive.
//
// El ancla pasa a ser **el directorio de la base de datos del hub**, que es lo que de
// verdad significa «aquí está el volumen» — y es la MISMA cuenta que hace `server.js`
// para crear `/data`. Si ese directorio EXISTE, existe el volumen; si no, estamos en
// local y el vacío es la verdad. Es una medida del mundo, no una bandera.
const DB_PATH = process.env.DB_PATH || '/data/jokin_tools.db';
const DATA_DIR = path.dirname(DB_PATH);

function enElVolumen(nombre) {
  // `existsSync` y no `NODE_ENV`: la pregunta es si hay dónde escribir. Y se pregunta al
  // cargar el módulo, igual que antes, para que el valor sea uno solo en todo el proceso.
  return fs.existsSync(DATA_DIR) ? path.join(DATA_DIR, 'shmir', nombre) : '';
}

// El directorio de referencia de TRABAJO. En un despliegue tiene que estar en el volumen
// o lo que se suba desaparece en el siguiente redespliegue, y el único síntoma sería un
// frente que vuelve a salir NOT_RUN. En local, vacío = el del paquete.
const REFERENCE_DIR = process.env.SHMIR_REFERENCE_DIR || enElVolumen('reference');

// Los PROYECTOS. Mismo motivo que la referencia y más fuerte: ahí va el registro de lo
// que se decidió, y un veredicto tiene que sobrevivir a la app que lo escribió. Va a un
// directorio distinto del de referencia porque la referencia se siembra y esto no.
const PROJECT_DIR = process.env.SHMIR_PROJECT_DIR || enElVolumen('proyectos');

// Y SE DICE EN EL ARRANQUE. La pregunta «¿en qué directorio está guardando?» sólo se
// podía contestar abriendo la app; tiene que estar en el log del despliegue, que es donde
// se mira cuando algo dejó de funcionar hace tres días.
function describeDirs() {
  const donde = (v, cual) => (
    v ? `${cual}=${v}` : `${cual}=(el del paquete: no hay volumen en ${DATA_DIR})`
  );
  return `[shmir] ${donde(REFERENCE_DIR, 'reference')} ${donde(PROJECT_DIR, 'proyectos')}`;
}

function referenceDir() {
  return REFERENCE_DIR;
}

function projectDir() {
  return PROJECT_DIR;
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

// La CSP del hub es global y estricta, y Streamlit no cabe en ella: su fuente de iconos
// viaja como `data:` y sus trabajadores se crean desde `blob:`. Se le pone una politica
// PROPIA a esta ruta en vez de relajar la del hub entero — el resto de las apps no tiene
// por que pagar lo que necesita esta.
//
// Lo que se añade sobre la del hub, y por que cada cosa:
//   font-src   data:   la fuente de iconos de Streamlit va incrustada
//   img-src    blob:   los graficos se pintan a un blob antes de mostrarse
//   worker-src blob:   Streamlit crea sus workers desde un blob
//   connect-src ws: wss:  el WebSocket del estado; en produccion va por TLS
// `script-src` NO se relaja con 'unsafe-eval': se comprobo con un navegador de verdad
// que la app renderiza sin el, y añadirlo «por si acaso» seria abrir un agujero para
// nada.
const CSP_SHMIR = [
  "default-src 'self'",
  "img-src 'self' data: blob:",
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "script-src 'self' 'unsafe-inline'",
  "connect-src 'self' ws: wss:",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "frame-ancestors 'self'",
].join('; ');

router.use(async (req, res) => {
  res.set('Content-Security-Policy', CSP_SHMIR);
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
  const arranque = await proceso.ensureRunning({
    referenceDir: REFERENCE_DIR, projectDir: PROJECT_DIR,
  });
  if (!arranque.ok) {
    res.status(503).type('text/plain; charset=utf-8');
    return res.send(
      // `arranque.reason` YA trae la salida del proceso sin interpretar, y una pista
      // sólo si la propia salida la nombra (`process.failureText`). Aquí no se añade
      // ningún diagnóstico más: un texto plausible pero incorrecto en un mensaje de
      // error hace perder más tiempo que no tener mensaje.
      'shmir-design no está disponible ahora mismo.\n\n'
      + `${arranque.reason}\n\n`
      + 'El resto del hub no se ve afectado.'
    );
  }
  return proxyRequest(req, res, { port: proceso.PORT });
});

module.exports = router;
module.exports.referenceDir = referenceDir;
module.exports.projectDir = projectDir;
module.exports.describeDirs = describeDirs;
