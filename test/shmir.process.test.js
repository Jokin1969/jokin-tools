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

test('el estado arranca en «parado» y no se ha lanzado nada', () => {
  const s = proceso.status();
  assert.equal(s.running, false);
  assert.equal(s.startedAt, null);
});

test('el motivo del último fallo se guarda para poder ENSEÑARLO', () => {
  proceso._recordFailure('ModuleNotFoundError: No module named \'streamlit\'');
  assert.match(proceso.status().lastError, /No module named/);
});

test('un fallo de arranque nombra qué instalar', () => {
  const texto = proceso.installHint();
  assert.match(texto, /streamlit/);
  assert.match(texto, /requirements-ui\.txt/);
});
