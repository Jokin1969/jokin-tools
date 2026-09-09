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
// TECHO DE SUBIDA, EN MB, DECLARADO. Sin declararlo vale el defecto de Streamlit —200—
// y el widget rechaza en el navegador con una X roja: sin numero, sin motivo y sin
// salida. Un limite que rechaza sin decir cual es no se distingue de una app rota.
//
// El valor lo fija el fichero legitimo MAS GRANDE que el gestor pide: el catalogo de
// 3'UTR del transcriptoma, que en humano son ~160 MB y queda a un pelo de los 200. Se
// deja holgura para que un catalogo de otra especie no vuelva a chocar.
//
// OJO: esto NO decide si un fichero SIRVE. Que quepa en la subida y que el filtro pueda
// con el son dos preguntas: el escaner por ventana tiene su propio techo medido
// (`specificity.MAX_SCANNABLE_NT`, 5,45 MB) y una base de RefSeq de verdad lo pasa por
// mucho aunque suba entera. Subir 320 MB para que el filtro los rechace despues es la
// errata nº 40 —la contradiccion cobrada DESPUES de la descarga— por la otra puerta.
const MAX_UPLOAD_MB = Number(process.env.SHMIR_MAX_UPLOAD_MB || 400);
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
// EL MOTIVO del ultimo arranque fallido —cual de las TRES cosas paso: se murio, contesta
// otro en el puerto, o no contesto a tiempo—. Va APARTE de `lastError` porque el
// manejador de `exit` del hijo salta DESPUES de nuestro propio `kill('SIGTERM')` y pisa
// `lastError` con «el proceso termino ... (señal SIGTERM)». Ese texto describe NUESTRA
// REACCION, no la causa, y era lo unico que llegaba al mensaje de MAX_RESTARTS.
let lastReason = '';
// ¿El ultimo SIGTERM lo mandamos nosotros? Un SIGTERM sin dueño se lee como una causa
// externa —la plataforma, un OOM— y manda a mirar donde no hay nada.
let killedByUs = false;
//: Qué dijo la última comprobación de identidad. Empieza sin comprobar, que es la
//: verdad mientras no se haya lanzado nada.
let lastIdentity = 'NO_COMPROBABLE';

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
    `--server.maxUploadSize=${MAX_UPLOAD_MB}`,
    '--browser.gatherUsageStats=false',
    // OBLIGATORIO aquí, y sólo se ve en el despliegue. Streamlit decide si está en modo
    // desarrollo con `"site-packages" not in __file__`, y `pip install --target=` deja
    // la ruta SIN `site-packages` — que es justo como lo instala el build del hub. En
    // modo desarrollo, `--server.port` es un conflicto y el proceso ABORTA con
    // `RuntimeError: server.port does not work when global.developmentMode is true`.
    // En local Streamlit vive en site-packages, así que esto pasaba en desarrollo y
    // reventaba en producción.
    '--global.developmentMode=false',
    // LA SEGUNDA VIA DE LAS DESCARGAS (errata nº 130). Sirve `ui/static/` en
    // `/shmir/app/static/…` con `FileResponse` y SIN `Content-Disposition`, así que un
    // `.txt` se PINTA en la pestaña en vez de irse al gestor de descargas del
    // navegador — que es el mecanismo en el que se quedan colgados el botón y el icono
    // de la tabla. No abre ninguna puerta: es una ruta más bajo `/shmir`, o sea detrás
    // de `requireApp`, igual que la página.
    '--server.enableStaticServing=true',
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
  // QUÉ COMMIT ESTÁ SIRVIENDO ESTO. El proceso hijo no puede saberlo: no hay `.git` en la
  // imagen y el paquete no lleva versión. El único que lo sabe es la plataforma, y lo
  // pone en `RAILWAY_GIT_COMMIT_SHA`. Se pasa TAL CUAL para que los ficheros que salen de
  // la app —el FASTA de construcciones, el informe— puedan decir de qué versión vienen.
  // El 2026-09-05 un FASTA descargado de producción no coincidía con lo que produce el
  // código de `main`, y no hubo forma de saber si era el despliegue o las entradas.
  // Si la plataforma no la da, NO se inventa ninguna: el lado Python dice «sin declarar»,
  // que es información, y un valor puesto aquí a mano no lo sería.
  const commit = String(base.RAILWAY_GIT_COMMIT_SHA || '').trim();
  if (commit) {
    env.SHMIR_BUILD = commit;
  } else {
    delete env.SHMIR_BUILD;
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

// EL MENSAJE QUE VE QUIEN ABRE LA APP CAIDA. Lleva las TRES cosas, y ninguna sobra:
//
//   · el MOTIVO —cual de los tres fallos fue—, que es lo que se perdia;
//   · la salida del proceso TAL CUAL, o que no escribio nada, que tambien informa: un
//     fallo de import deja traza, asi que cero lineas lo descarta;
//   · como se REARMA. Sin eso, el contador se queda en el tope —solo baja con un
//     arranque bueno— y la app se queda caida hasta que alguien adivine que hay que
//     reiniciar el hub.
function exhaustedText() {
  const motivo = lastReason
    ? `Motivo del último intento: ${lastReason}.`
    : 'El motivo del último intento NO se llegó a registrar, que no es lo mismo que no '
      + 'haberlo tenido.';
  // La aclaracion del SIGTERM sale SOLO si la propia salida lo nombra, que es la regla
  // de `diagnose`: una pista que no se apoya en la evidencia manda a mirar donde no hay
  // nada. Y aqui SI es nuestro: a esta rama solo se llega tras fallar `waitUntilReady`,
  // y ese camino siempre pasa por `killedByUs = true; child.kill('SIGTERM')`.
  const duenno = /SIGTERM/.test(lastError)
    ? ' El SIGTERM lo mandó el hub al dar el arranque por fallido, así que NO es la '
      + 'causa: es la reacción.'
    : '';
  return failureText(
    lastError,
    `El proceso de shmir-design ha fallado ${restarts} veces seguidas y no se vuelve a `
    + `intentar automáticamente: reintentar en bucle llenaría los logs y no arreglaría `
    + `nada. ${motivo}${duenno} El contador sólo baja con un arranque bueno, así que para volver `
    + `a intentarlo hay que reiniciar el hub.`
  );
}

function _recordFailure(message) {
  lastError = String(message || '').slice(0, 4000);
}

function _recordReason(reason) {
  lastReason = String(reason || '').slice(0, 500);
}

// Para los tests: deja la supervision como recien arrancada. No lo llama la app.
function _resetSupervision() {
  lastError = '';
  lastOutput = '';
  lastReason = '';
  killedByUs = false;
  restarts = 0;
}

function status() {
  return {
    running: Boolean(child && child.exitCode === null),
    startedAt,
    port: PORT,
    // EL PID Y LA IDENTIDAD SALEN, o la comprobación no se ve. Una comprobación que
    // corre y no llega a ninguna pantalla es la mitad del arreglo, y `identidad` es
    // además el sitio donde se lee un NO_COMPROBABLE — que no es «coincide».
    pid: child ? child.pid : null,
    identidad: lastIdentity,
    restarts,
    lastReason,
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

// ─── ¿Quién contesta en ese puerto? ─────────────────────────────────────────────
//
// UN SONDEO NO DISTINGUE «mi proceso está listo» de «alguien contesta en ese puerto», y
// eso es afirmar una cosa a partir de una comprobación que no la mira. Con el puerto
// fijo, un proceso de una ejecución anterior que quede vivo —caso que `diagnose` ya
// contempla— hace que un despliegue cuyo Streamlit NO arrancó se dé por arrancado, y lo
// que se sirve es la interfaz del despliegue viejo. El síntoma es «está fusionado pero
// no lo veo», y no hay ningún error en ningún log.
//
// Se comprueba por el PID DUEÑO DEL SOCKET EN ESCUCHA, que es lo comprobable sin añadir
// dependencias ni protocolo: el inodo del socket que escucha en ese puerto
// (`/proc/net/tcp`) tiene que estar entre los descriptores del hijo (`/proc/<pid>/fd`).
// MEDIDO sobre el proceso real: Streamlit no bifurca, el socket lo tiene el mismo
// proceso que se lanza — si bifurcara, este guardia daría falsos positivos y un guardia
// con falsos positivos se acaba apagando.
//
// TRES ESTADOS, y el tercero NO es «coincide»: donde no hay `/proc` —desarrollo fuera de
// Linux— la respuesta es NO_COMPROBABLE **con el motivo**, y no haber podido comprobarlo
// no es haberlo comprobado. Es la regla del `.out` sin resumen.
const IDENTIDAD = { PROPIO: 'PROPIO', AJENO: 'AJENO', NO_COMPROBABLE: 'NO_COMPROBABLE' };

//: Los inodos de los sockets EN ESCUCHA en ese puerto. `null` = no se pudo mirar.
function _inodosEnEscucha(port, procRoot) {
  const hex = Number(port).toString(16).toUpperCase().padStart(4, '0');
  const inodos = new Set();
  let leido = false;
  for (const nombre of ['net/tcp', 'net/tcp6']) {
    let texto = '';
    try {
      texto = fs.readFileSync(path.join(procRoot, nombre), 'utf8');
    } catch {
      // rule2-ok (equivalente en el hub): la ausencia de UNO de los dos ficheros es
      // normal —hay sistemas sin IPv6— y no se traga nada: si no se lee NINGUNO, el
      // llamador devuelve NO_COMPROBABLE con el motivo.
      continue;
    }
    leido = true;
    for (const linea of texto.split('\n').slice(1)) {
      const campos = linea.trim().split(/\s+/);
      if (campos.length < 10) continue;
      if (campos[3] !== '0A') continue;                 // 0A = LISTEN
      if (!campos[1].endsWith(':' + hex)) continue;     // dirección local:puerto
      inodos.add(campos[9]);                            // inodo del socket
    }
  }
  return leido ? inodos : null;
}

function _tieneElInodo(pid, inodos, procRoot) {
  let entradas = [];
  try {
    entradas = fs.readdirSync(path.join(procRoot, String(pid), 'fd'));
  } catch {
    // rule2-ok: el proceso puede haber muerto entre una cosa y otra. No se esconde
    // ningún fallo — el llamador lo traduce a AJENO, que es la respuesta conservadora.
    return false;
  }
  for (const fd of entradas) {
    let destino = '';
    try {
      destino = fs.readlinkSync(path.join(procRoot, String(pid), 'fd', fd));
    } catch {
      continue;   // rule2-ok: un descriptor cerrado mientras se recorre. Se sigue.
    }
    for (const inodo of inodos) {
      if (destino === `socket:[${inodo}]`) return true;
    }
  }
  return false;
}

// ¿El que escucha en `port` es el proceso `pid`? Devuelve `{ estado, motivo }`.
function portOwner(pid, port, { procRoot = '/proc' } = {}) {
  if (!pid) {
    return {
      estado: IDENTIDAD.NO_COMPROBABLE,
      motivo: 'No hay ningún pid con el que comparar, así que no se ha comprobado nada.',
    };
  }
  const inodos = _inodosEnEscucha(port, procRoot);
  if (inodos === null) {
    return {
      estado: IDENTIDAD.NO_COMPROBABLE,
      motivo:
        `No se ha podido leer ${path.join(procRoot, 'net/tcp')}, así que no se sabe de `
        + `quién es el puerto ${port}. NO se ha comprobado, que no es lo mismo que `
        + `haber comprobado que es el nuestro.`,
    };
  }
  if (inodos.size === 0) {
    return {
      estado: IDENTIDAD.NO_COMPROBABLE,
      motivo:
        `No aparece ningún socket en escucha en el puerto ${port}: no hay de quién `
        + `comprobar la identidad. NO se ha comprobado, que no es «es el nuestro».`,
    };
  }
  if (_tieneElInodo(pid, inodos, procRoot)) {
    return {
      estado: IDENTIDAD.PROPIO,
      motivo: `El socket en escucha en el puerto ${port} es del proceso ${pid}.`,
    };
  }
  return {
    estado: IDENTIDAD.AJENO,
    motivo:
      `Quien escucha en el puerto ${port} NO es el proceso ${pid}, que es el que se `
      + `acaba de lanzar. Puede quedar vivo un proceso de una ejecución anterior: `
      + `servirle a él sería servir OTRA versión de la interfaz sin ningún error.`,
  };
}

//: Motivos, en un sitio: los usa `waitUntilReady` y los leen sus tests.
const MOTIVO_MURIO = 'el proceso terminó antes de llegar a contestar';
const MOTIVO_AJENO = 'quien contesta no es el que se acaba de lanzar';

// Espera a que conteste EL HIJO PROPIO. Devuelve `{ ok, reason, identidad }`.
//
// EL ORDEN NO ES UN DETALLE. Esto sondeaba primero y miraba si el hijo se había muerto
// después, así que un hijo muerto con otro contestando en el puerto salía LISTO — el
// sondeo le ganaba siempre a la comprobación. Ahora se mira la vida del hijo ANTES, y
// además se comprueba de quién es el puerto: un hijo vivo que todavía no escucha, con
// otro contestando, da el mismo verde falso.
async function waitUntilReady(
  { port = PORT, timeoutMs = READY_TIMEOUT_MS, child: propio = undefined } = {}
) {
  const hijo = propio === undefined ? child : propio;
  const limite = Date.now() + timeoutMs;
  while (Date.now() < limite) {
    if (hijo && hijo.exitCode !== null) {
      return { ok: false, reason: MOTIVO_MURIO, identidad: IDENTIDAD.NO_COMPROBABLE };
    }
    if (await probe(port)) {
      const duenno = portOwner(hijo && hijo.pid, port);
      if (duenno.estado === IDENTIDAD.AJENO) {
        return { ok: false, reason: `${MOTIVO_AJENO}. ${duenno.motivo}`,
                 identidad: duenno.estado };
      }
      // NO_COMPROBABLE no bloquea el arranque —fuera de Linux no hay `/proc` y la app
      // tiene que poder correr—, pero VIAJA al estado y se dice. Callarlo lo convertiría
      // en un «comprobado» silencioso, que es el fallo que esto viene a cerrar.
      return { ok: true, reason: duenno.motivo, identidad: duenno.estado };
    }
    await esperar(POLL_MS);
  }
  return {
    ok: false,
    reason: `no contestó en ${timeoutMs} ms`,
    identidad: IDENTIDAD.NO_COMPROBABLE,
  };
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
      const duenno = (signal === 'SIGTERM' && killedByUs)
        ? ' — lo mandó el hub al dar el arranque por fallido, así que NO es la causa'
        : '';
      _recordFailure(
        `el proceso terminó con código ${code}`
        + `${signal ? ` (señal ${signal}${duenno})` : ''}. `
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
      return { ok: false, reason: exhaustedText() };
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
    lastIdentity = listo.identidad;
    if (!listo.ok) {
      restarts += 1;
      _recordReason(listo.reason);
      killedByUs = true;
      if (child) child.kill('SIGTERM');
      // EL ENCABEZADO DICE CUÁL DE LAS TRES COSAS PASÓ —se murió, contesta otro, o no
      // contestó a tiempo— en vez de las tres bajo el mismo texto. Un «no llegó a
      // contestar» sobre un puerto que SÍ contesta manda a mirar el sitio equivocado,
      // que es la lección de `diagnose`.
      return {
        ok: false,
        reason: failureText(
          lastOutput || lastError,
          `El proceso de shmir-design no arrancó: ${listo.reason}.`
        ),
      };
    }
    restarts = 0;
    return { ok: true, alreadyRunning: false, identidad: listo.identidad };
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
  ensureRunning, stop, status, probe, waitUntilReady, portOwner,
  buildArgs, buildEnv, diagnose, failureText, exhaustedText,
  _recordFailure, _recordReason, _resetSupervision,
  IDENTIDAD, MOTIVO_MURIO, MOTIVO_AJENO,
  PORT, BASE_PATH, SHMIR_ROOT, APP_FILE, PYTHON_BIN, MAX_UPLOAD_MB,
};
