// ─── El proceso de Streamlit, supervisado ───────────────────────────────────────
//
// shmir-design tiene su interfaz en Streamlit, que es un servidor propio. El hub la
// arranca como proceso hijo en 127.0.0.1 y la sirve por el proxy: desde fuera es una
// ruta más del hub, con el mismo login y los mismos permisos que las demás apps.
//
// Tres decisiones, y ninguna es un detalle:
//
//   1. **Arranque perezoso.** No se lanza al bootear. Streamlit tarda segundos y ocupa
//      memoria, y la mayoría de quien entra al hub no abre esta app.
//   2. **Escucha SÓLO en 127.0.0.1.** En 0.0.0.0 quedaría accesible por el puerto
//      directo, saltándose el login del hub. La única puerta es el proxy.
//   3. **Si no arranca, se dice por qué**, con lo que el proceso haya escrito. Un «no
//      disponible» a secas no distingue «falta Streamlit» de «el puerto está cogido».
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const SHMIR_ROOT = path.resolve(__dirname, '../shmir-design');
const APP_FILE = path.join(SHMIR_ROOT, 'ui', 'streamlit_app.py');
const REPO_ROOT = path.resolve(__dirname, '../..');
const VENV_PY = path.join(REPO_ROOT, '.venv', 'bin', 'python');
const PYTHON_LIBS = path.join(REPO_ROOT, 'python_libs');

const PYTHON_BIN = process.env.PYTHON_BIN
  || (fs.existsSync(VENV_PY) ? VENV_PY : 'python3');

const PORT = Number(process.env.SHMIR_PORT || 8501);
const BASE_PATH = '/shmir';
// Cuánto se espera a que conteste tras lanzarlo. Streamlit importa pandas y pyarrow,
// así que el primer arranque no es instantáneo ni en una máquina rápida.
const READY_TIMEOUT_MS = Number(process.env.SHMIR_READY_TIMEOUT_MS || 60000);
const POLL_MS = 300;
// Tope de reintentos. Sin tope, un fallo permanente —falta Streamlit— daría un bucle de
// arranques que llenaría los logs y no arreglaría nada.
const MAX_RESTARTS = 3;

let child = null;
let startedAt = null;
let starting = null;
let restarts = 0;
let lastError = '';
let lastOutput = '';

function buildArgs({ port = PORT, basePath = BASE_PATH } = {}) {
  return [
    // Como MÓDULO: `pip install --target=/app/python_libs` deja el ejecutable en un bin
    // que no está en el PATH, y `python3 -m streamlit` funciona sólo con PYTHONPATH,
    // que es lo que el build ya configura para las demás dependencias.
    '-m', 'streamlit', 'run', APP_FILE,
    '--server.address=127.0.0.1',
    `--server.port=${port}`,
    `--server.baseUrlPath=${basePath}`,
    '--server.headless=true',
    '--server.fileWatcherType=none',
    '--browser.gatherUsageStats=false',
    // OBLIGATORIO aquí, y sólo se ve en el despliegue. Streamlit decide si está en modo
    // desarrollo con `"site-packages" not in __file__`, y `pip install --target=` deja
    // la ruta SIN `site-packages` — que es justo como lo instala el build del hub. En
    // modo desarrollo, `--server.port` es un conflicto y el proceso ABORTA con
    // `RuntimeError: server.port does not work when global.developmentMode is true`.
    // En local Streamlit vive en site-packages, así que esto pasaba en desarrollo y
    // reventaba en producción.
    '--global.developmentMode=false',
    // Subidas: el transcriptoma de 3'UTR y un RefSeq son grandes. El límite de Streamlit
    // por defecto (200 MB) se deja como está; lo que se quita es el recolector de
    // estadísticas y el vigilante de ficheros, que en un servidor no pintan nada.
  ];
}

function buildEnv({ referenceDir = '', projectDir = '', base = process.env } = {}) {
  const env = { ...base };
  const libs = [];
  if (fs.existsSync(PYTHON_LIBS)) libs.push(PYTHON_LIBS);
  if (env.PYTHONPATH) libs.push(...env.PYTHONPATH.split(':').filter(Boolean));
  const unicos = [...new Set(libs)];
  if (unicos.length) env.PYTHONPATH = unicos.join(':');
  // Vacío significa «el del paquete», y esa decisión vive en `trabajo.py`, en el lado
  // Python y con tests. Poner aquí un valor por defecto sería una segunda fuente de la
  // misma decisión, que es como se acaba con dos contadores que discrepan.
  if (String(referenceDir).trim()) {
    env.SHMIR_REFERENCE_DIR = String(referenceDir).trim();
  } else {
    delete env.SHMIR_REFERENCE_DIR;
  }
  // Y lo mismo para los PROYECTOS, que es donde vive el registro de lo que se decidió.
  // Va en su propia variable y en su propio directorio: la referencia se SIEMBRA desde
  // lo versionado y los proyectos no tienen semilla ninguna, así que mezclarlos
  // obligaría a la siembra a distinguir qué pisa y qué no. Si esta variable no viaja, la
  // persistencia funciona en local y en producción se pierde en el siguiente
  // redespliegue — con el mismo síntoma de siempre: nada, hasta que alguien busca lo que
  // guardó ayer.
  if (String(projectDir).trim()) {
    env.SHMIR_PROJECT_DIR = String(projectDir).trim();
  } else {
    delete env.SHMIR_PROJECT_DIR;
  }
  return env;
}

// ─── Diagnóstico: sólo cuando la evidencia lo señala ─────────────────────────
//
// Aquí había un fallo caro. Se pegaba una pista de instalación a TODOS los fallos
// —«comprueba que Streamlit está instalado»— y el primer fallo real de producción fue un
// conflicto de configuración con Streamlit ya importado y corriendo: la traza llegaba
// hasta `streamlit/config.py`, así que un `ModuleNotFoundError` habría fallado mucho
// antes. La página mandaba a mirar el sitio equivocado.
//
// Un diagnóstico EQUIVOCADO en un mensaje de error hace perder más tiempo que no tener
// mensaje. Es la misma lección que el «Alu 0 %» obtenido sin buscar Alu: un texto
// plausible pero incorrecto es peor que ninguno. Así que lo que se enseña es la SALIDA
// TAL CUAL, y una interpretación sólo cuando la propia salida la nombra.

//: Fallo → pista. Sólo se añade la pista cuya huella aparece en la salida del proceso.
const PISTAS = [
  {
    huella: /ModuleNotFoundError|No module named|ImportError/i,
    texto:
      'La salida dice que falta un módulo de Python. Streamlit es la única dependencia '
      + `de la interfaz (${path.join('apps', 'shmir-design', 'requirements-ui.txt')}, `
      + '`streamlit>=1.30`) y se instala con `pip3 install --target=/app/python_libs '
      + 'streamlit`. El núcleo y los CLI de shmir-design NO la necesitan.',
  },
  {
    huella: /developmentMode/i,
    texto:
      'La salida nombra `global.developmentMode`. Streamlit lo infiere de si su propia '
      + 'ruta lleva `site-packages`, y `pip install --target=` la deja sin él; en modo '
      + 'desarrollo, `--server.port` es un conflicto. Se fija con '
      + '`--global.developmentMode=false`, que este arranque ya pasa: si sigue saliendo, '
      + 'algo lo está sobreescribiendo (variable de entorno o `config.toml`).',
  },
  {
    huella: /Address already in use|EADDRINUSE/i,
    texto:
      `La salida dice que el puerto ${PORT} está cogido. Puede quedar un proceso de una `
      + 'ejecución anterior; el hub lo para al apagarse, pero un cierre a la brava no.',
  },
];

// Devuelve la pista que corresponda a esta salida, o cadena vacía. NUNCA adivina.
function diagnose(output) {
  const texto = String(output || '');
  if (!texto.trim()) return '';
  for (const pista of PISTAS) {
    if (pista.huella.test(texto)) return pista.texto;
  }
  return '';
}

// El texto que ve el usuario: la salida TAL CUAL y, sólo si procede, la pista.
function failureText(output, encabezado = '') {
  const crudo = String(output || '').trim() || '(el proceso no escribió nada)';
  const pista = diagnose(crudo);
  return [
    encabezado,
    'ÚLTIMAS LÍNEAS DE LA SALIDA DEL PROCESO, SIN INTERPRETAR:',
    '',
    crudo,
    ...(pista ? ['', `PISTA (sale porque la propia salida la nombra): ${pista}`] : []),
  ].filter(Boolean).join('\n');
}

function _recordFailure(message) {
  lastError = String(message || '').slice(0, 4000);
}

function status() {
  return {
    running: Boolean(child && child.exitCode === null),
    startedAt,
    port: PORT,
    restarts,
    lastError,
    lastOutput: lastOutput.slice(-2000),
  };
}

// ¿Contesta ya? Se pregunta al propio Streamlit por su ruta de salud.
function probe(port = PORT) {
  return new Promise(resolve => {
    const req = http.get(
      { host: '127.0.0.1', port, path: `${BASE_PATH}/_stcore/health`, timeout: 2000 },
      res => {
        res.resume();
        resolve(res.statusCode === 200);
      }
    );
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

function esperar(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function waitUntilReady({ port = PORT, timeoutMs = READY_TIMEOUT_MS } = {}) {
  const limite = Date.now() + timeoutMs;
  while (Date.now() < limite) {
    if (await probe(port)) return true;
    if (child && child.exitCode !== null) return false;   // se murió por el camino
    await esperar(POLL_MS);
  }
  return false;
}

function spawnChild({ referenceDir, projectDir }) {
  const proc = spawn(PYTHON_BIN, buildArgs(), {
    cwd: SHMIR_ROOT,
    env: buildEnv({ referenceDir, projectDir }),
  });
  proc.stdout.on('data', d => { lastOutput += d.toString(); });
  proc.stderr.on('data', d => {
    const texto = d.toString();
    lastOutput += texto;
    _recordFailure(texto);
  });
  proc.on('exit', (code, signal) => {
    if (code !== 0) {
      _recordFailure(
        `el proceso terminó con código ${code}${signal ? ` (señal ${signal})` : ''}. `
        + `Últimas líneas:\n${lastOutput.slice(-1500)}`
      );
    }
    child = null;
    startedAt = null;
  });
  return proc;
}

// Arranca si hace falta y espera a que conteste. Concurrente-seguro: varias peticiones
// a la vez comparten el mismo arranque en vez de lanzar tres procesos.
async function ensureRunning({ referenceDir = '', projectDir = '' } = {}) {
  if (child && child.exitCode === null && await probe()) {
    return { ok: true, alreadyRunning: true };
  }
  if (starting) return starting;

  starting = (async () => {
    if (restarts >= MAX_RESTARTS) {
      return {
        ok: false,
        reason: failureText(
          lastError,
          `El proceso de shmir-design ha fallado ${restarts} veces seguidas y no se `
          + `vuelve a intentar automáticamente: reintentar en bucle llenaría los logs y `
          + `no arreglaría nada.`
        ),
      };
    }
    lastOutput = '';
    try {
      child = spawnChild({ referenceDir, projectDir });
    } catch (err) {
      restarts += 1;
      _recordFailure(err.message);
      return {
        ok: false,
        reason: failureText(err.message, `No se pudo lanzar ${PYTHON_BIN}.`),
      };
    }
    startedAt = new Date().toISOString();
    const listo = await waitUntilReady();
    if (!listo) {
      restarts += 1;
      if (child) child.kill('SIGTERM');
      return {
        ok: false,
        reason: failureText(
          lastOutput || lastError,
          `El proceso de shmir-design no llegó a contestar en ${READY_TIMEOUT_MS} ms.`
        ),
      };
    }
    restarts = 0;
    return { ok: true, alreadyRunning: false };
  })();

  try {
    return await starting;
  } finally {
    starting = null;
  }
}

function stop() {
  if (child && child.exitCode === null) child.kill('SIGTERM');
  child = null;
  startedAt = null;
}

module.exports = {
  ensureRunning, stop, status, probe, waitUntilReady,
  buildArgs, buildEnv, diagnose, failureText, _recordFailure,
  PORT, BASE_PATH, SHMIR_ROOT, APP_FILE, PYTHON_BIN,
};
