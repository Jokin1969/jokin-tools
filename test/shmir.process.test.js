// El proceso de Streamlit: cómo se arranca, cómo se espera y qué se dice si no arranca.
//
// Lo que se fija aquí, y son decisiones, no detalles:
//
//   - **arranque PEREZOSO**: no se lanza al bootear el hub. Streamlit tarda segundos y
//     se come memoria, y la mayoría de quien entra al hub no abre esta app;
//   - **los argumentos son los de estar detrás de un proxy**: escucha sólo en 127.0.0.1
//     —si escuchara en 0.0.0.0, en Railway quedaría accesible saltándose el login— y
//     sirve bajo `/shmir`, porque si no las rutas de sus propios recursos apuntan a la
//     raíz del hub;
//   - **el directorio de referencia de trabajo viaja en el entorno**, o lo subido se
//     escribiría dentro de la imagen y desaparecería en el siguiente despliegue;
//   - **si no arranca, se dice POR QUÉ** con lo que el proceso haya escrito. Un «no
//     disponible» a secas deja al usuario sin saber si falta Streamlit, si el puerto
//     está cogido o si el fichero tiene un error de sintaxis.
const { test } = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

const proceso = require('../apps/shmir/process');

test('los argumentos lo atan a 127.0.0.1 y a la ruta /shmir', () => {
  const args = proceso.buildArgs({ port: 8501, basePath: '/shmir' });
  const texto = args.join(' ');
  assert.match(texto, /--server\.address[= ]127\.0\.0\.1/);
  assert.match(texto, /--server\.port[= ]8501/);
  assert.match(texto, /--server\.baseUrlPath[= ]\/shmir/);
  assert.match(texto, /--server\.headless[= ]true/);
});

test('NO escucha en 0.0.0.0 — en Railway eso sería la app sin login', () => {
  const texto = proceso.buildArgs({ port: 8501, basePath: '/shmir' }).join(' ');
  assert.ok(!texto.includes('0.0.0.0'), texto);
});

test('se invoca como módulo, no por el ejecutable de la consola', () => {
  // `pip install --target=/app/python_libs` deja `streamlit` en un bin que no está en
  // el PATH. `python3 -m streamlit` funciona con sólo PYTHONPATH, que es lo que el
  // build ya configura para las demás dependencias de Python.
  const args = proceso.buildArgs({ port: 8501, basePath: '/shmir' });
  assert.equal(args[0], '-m');
  assert.equal(args[1], 'streamlit');
  assert.equal(args[2], 'run');
  assert.ok(args[3].endsWith(path.join('ui', 'streamlit_app.py')), args[3]);
});

test('el modo desarrollo se apaga EXPLÍCITAMENTE, o el proceso no arranca', () => {
  // Fallo real del primer despliegue, y sólo puede pasar ahí. Streamlit decide si está
  // en modo desarrollo con `"site-packages" not in __file__`, y
  // `pip install --target=/app/python_libs` deja la ruta SIN `site-packages`. En local
  // está en site-packages, así que esto pasaba en desarrollo y reventaba en producción
  // con `RuntimeError: server.port does not work when global.developmentMode is true`.
  const texto = proceso.buildArgs({ port: 8501, basePath: '/shmir' }).join(' ');
  assert.match(texto, /--global\.developmentMode[= ]false/);
});

test('la telemetría de Streamlit se apaga explícitamente', () => {
  const texto = proceso.buildArgs({ port: 8501, basePath: '/shmir' }).join(' ');
  assert.match(texto, /gatherUsageStats[= ]false/);
});

test('el entorno lleva el directorio de referencia de TRABAJO', () => {
  const env = proceso.buildEnv({ referenceDir: '/data/shmir/reference' });
  assert.equal(env.SHMIR_REFERENCE_DIR, '/data/shmir/reference');
});

test('y conserva el PYTHONPATH de las dependencias instaladas con --target', () => {
  const env = proceso.buildEnv({
    referenceDir: '/data/shmir/reference',
    base: { PYTHONPATH: '/app/python_libs' },
  });
  assert.match(env.PYTHONPATH, /\/app\/python_libs/);
});

test('sin directorio de referencia declarado NO se inventa uno', () => {
  // Vacío significa «el del paquete», y eso lo decide `trabajo.py` en el lado Python.
  // Poner aquí un valor por defecto sería una segunda fuente de la misma decisión.
  const env = proceso.buildEnv({ referenceDir: '' });
  assert.ok(!('SHMIR_REFERENCE_DIR' in env), JSON.stringify(env.SHMIR_REFERENCE_DIR));
});

test('el entorno lleva TAMBIÉN el directorio de PROYECTOS', () => {
  // Lo que se guarda ahí es el registro de lo que se decidió, y dentro de la imagen se
  // pierde en el siguiente redespliegue. Si esta variable no viaja, la persistencia
  // entera funciona en local y no sirve de nada en producción.
  const env = proceso.buildEnv({ projectDir: '/data/shmir/proyectos' });
  assert.equal(env.SHMIR_PROJECT_DIR, '/data/shmir/proyectos');
});

test('y sin declararlo tampoco se inventa uno', () => {
  const env = proceso.buildEnv({ projectDir: '' });
  assert.ok(!('SHMIR_PROJECT_DIR' in env), JSON.stringify(env.SHMIR_PROJECT_DIR));
});

test('el commit desplegado VIAJA al proceso hijo', () => {
  // El hijo no puede saberlo: no hay `.git` en la imagen. Sin esto, un fichero que sale
  // de la app no puede decir de qué versión viene — y el 2026-09-05 hizo falta.
  const env = proceso.buildEnv({ base: { RAILWAY_GIT_COMMIT_SHA: 'a5fb5e0deadbeef' } });
  assert.equal(env.SHMIR_BUILD, 'a5fb5e0deadbeef');
});

test('y si la plataforma no lo da, NO se inventa ninguno', () => {
  // «sin declarar» es información; un valor puesto aquí a mano no lo sería.
  const env = proceso.buildEnv({ base: {} });
  assert.ok(!('SHMIR_BUILD' in env), JSON.stringify(env.SHMIR_BUILD));
});

test('los dos directorios son DISTINTOS: referencia se siembra, proyectos no', () => {
  // La referencia se siembra desde lo versionado; los proyectos no tienen semilla
  // ninguna. Mezclarlos en un solo directorio haría que la siembra tuviera que
  // distinguir qué pisa y qué no, que es justo lo que la siembra no sabe hacer.
  const env = proceso.buildEnv({
    referenceDir: '/data/shmir/reference',
    projectDir: '/data/shmir/proyectos',
  });
  assert.notEqual(env.SHMIR_REFERENCE_DIR, env.SHMIR_PROJECT_DIR);
});

test('el estado arranca en «parado» y no se ha lanzado nada', () => {
  const s = proceso.status();
  assert.equal(s.running, false);
  assert.equal(s.startedAt, null);
});

test('el motivo del último fallo se guarda para poder ENSEÑARLO', () => {
  proceso._recordFailure('ModuleNotFoundError: No module named \'streamlit\'');
  assert.match(proceso.status().lastError, /No module named/);
});

// ─── El mensaje de error NO diagnostica por su cuenta ────────────────────────
//
// Fallo real y caro. Al primer despliegue, la página dijo «comprueba que Streamlit está
// instalado» — y Streamlit estaba instalado, importado y corriendo: era un conflicto de
// configuración (`server.port` con `global.developmentMode`). La traza llegaba hasta
// `streamlit/config.py`, o sea que un `ModuleNotFoundError` habría fallado mucho antes.
//
// Un diagnóstico EQUIVOCADO en un mensaje de error hace perder más tiempo que no tener
// mensaje: es la misma lección que el «Alu 0 %» obtenido sin buscar Alu — un texto
// plausible pero incorrecto es peor que ninguno.

test('la pista de instalación solo sale cuando la salida nombra un módulo que falta', () => {
  const pista = proceso.diagnose('ModuleNotFoundError: No module named \'streamlit\'');
  assert.match(pista, /falta un módulo/i);
  assert.match(pista, /requirements-ui\.txt/);
});

test('y un fallo de CONFIGURACIÓN no manda a mirar la instalación', () => {
  // Es el fallo que costó una vuelta entera: la página decía «comprueba que Streamlit
  // está instalado» y Streamlit estaba importado y corriendo.
  const pista = proceso.diagnose(
    'RuntimeError: server.port does not work when global.developmentMode is true.'
  );
  assert.ok(!/instala|requirements-ui/i.test(pista), pista);
  // Sí puede haber una pista, PERO sólo porque la propia salida nombra el ajuste.
  assert.match(pista, /developmentMode/);
});

test('un fallo que no encaja con ninguna huella NO se interpreta', () => {
  assert.equal(proceso.diagnose('RuntimeError: algo que nadie ha visto antes'), '');
});

test('un fallo sin salida tampoco se diagnostica', () => {
  assert.equal(proceso.diagnose(''), '');
  assert.equal(proceso.diagnose(undefined), '');
});

test('el motivo que ve el usuario lleva la traza TAL CUAL', () => {
  const traza = 'File "/app/python_libs/streamlit/config.py", line 3073\n'
    + 'RuntimeError: server.port does not work when global.developmentMode is true.';
  const texto = proceso.failureText(traza);
  assert.ok(texto.includes(traza), 'la traza no viaja entera');
});

test('y no le pega ninguna interpretación cuando no la hay', () => {
  const texto = proceso.failureText('RuntimeError: lo que sea');
  assert.ok(!/instalad/i.test(texto), texto);
});
