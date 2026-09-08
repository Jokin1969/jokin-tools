// Que el directorio de referencia CAIGA EN EL VOLUMEN en produccion.
//
// Por que hace falta este fichero: los tests que habia pasan `/data/shmir/reference`
// COMO ARGUMENTO a `buildEnv`, asi que comprueban que la variable llega al proceso hijo
// — y no que la ruta se DERIVE bien. Si alguien cambia la derivacion de `routes.js`, o
// si `DB_PATH` deja de apuntar al volumen, todo sigue en verde y lo subido por el panel
// desaparece en el siguiente redespliegue, con el unico sintoma de un frente que vuelve
// a salir NOT_RUN.
//
// Es el mismo patron del principio 18 de shmir-design: un artefacto de verificacion que
// prueba el comprobador y no el dato.

const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

function cargarRoutes({ nodeEnv, dbPath, referenceDir, projectDir }) {
  const previo = {
    NODE_ENV: process.env.NODE_ENV,
    DB_PATH: process.env.DB_PATH,
    SHMIR_REFERENCE_DIR: process.env.SHMIR_REFERENCE_DIR,
    SHMIR_PROJECT_DIR: process.env.SHMIR_PROJECT_DIR,
  };
  const poner = (clave, valor) => {
    if (valor === undefined) delete process.env[clave];
    else process.env[clave] = valor;
  };
  poner('NODE_ENV', nodeEnv);
  poner('DB_PATH', dbPath);
  poner('SHMIR_REFERENCE_DIR', referenceDir);
  poner('SHMIR_PROJECT_DIR', projectDir);
  // `REFERENCE_DIR` se calcula al cargar el modulo, asi que hay que recargarlo.
  const ruta = require.resolve('../apps/shmir/routes');
  delete require.cache[ruta];
  try {
    return require('../apps/shmir/routes');
  } finally {
    for (const [clave, valor] of Object.entries(previo)) poner(clave, valor);
    delete require.cache[ruta];
  }
}

test('en produccion el directorio de referencia cae en el VOLUMEN', () => {
  const routes = cargarRoutes({ nodeEnv: 'production', dbPath: '/data/jokin_tools.db' });
  assert.equal(routes.referenceDir(), path.join('/data', 'shmir', 'reference'));
  assert.equal(routes.projectDir(), path.join('/data', 'shmir', 'proyectos'));
});

test('y sale del MISMO sitio que la base de datos, no de una ruta escrita a mano', () => {
  // Si el volumen se montara en otro sitio, los ficheros lo siguen. Esto es lo que
  // convierte «/data» en una consecuencia de DB_PATH y no en una coincidencia.
  //
  // EL VOLUMEN SE CREA DE VERDAD (errata nº 153). Antes bastaba con nombrar una ruta
  // porque lo que decidia era `NODE_ENV`; ahora lo que decide es que el directorio
  // EXISTA, que es una medida del mundo y no una bandera. El invariante que este test
  // fija no ha cambiado — lo que cambio es el ancla, y el test se mueve con ella.
  const fs = require('node:fs');
  const os = require('node:os');
  const volumen = fs.mkdtempSync(path.join(os.tmpdir(), 'vol-otro-'));
  try {
    const routes = cargarRoutes({ nodeEnv: 'production', dbPath: path.join(volumen, 'hub.db') });
    assert.equal(routes.referenceDir(), path.join(volumen, 'shmir', 'reference'));
    assert.equal(routes.projectDir(), path.join(volumen, 'shmir', 'proyectos'));
  } finally {
    fs.rmSync(volumen, { recursive: true, force: true });
  }
});

test('sin DB_PATH sigue cayendo en el volumen por defecto', () => {
  const routes = cargarRoutes({ nodeEnv: 'production', dbPath: undefined });
  assert.equal(routes.referenceDir(), path.join('/data', 'shmir', 'reference'));
});

test('la variable explicita MANDA sobre la derivacion', () => {
  const routes = cargarRoutes({
    nodeEnv: 'production', dbPath: '/data/jokin_tools.db',
    referenceDir: '/otro/sitio', projectDir: '/otro/proyectos',
  });
  assert.equal(routes.referenceDir(), '/otro/sitio');
  assert.equal(routes.projectDir(), '/otro/proyectos');
});

test('en local, vacio: el directorio del paquete', () => {
  // «Local» ya no es «NODE_ENV no es production» —esa bandera es la que fallo— sino
  // «no hay volumen donde escribir». Se apunta a un sitio que NO existe, que es lo que
  // pasa en una maquina de desarrollo sin `/data` montado. Vacio aqui es la VERDAD.
  const os = require('node:os');
  const routes = cargarRoutes({
    nodeEnv: 'test',
    dbPath: path.join(os.tmpdir(), `sin-volumen-${Date.now()}`, 'hub.db'),
  });
  assert.equal(routes.referenceDir(), '');
  assert.equal(routes.projectDir(), '');
});

test('el de PROYECTOS es distinto del de referencia', () => {
  // No es cosmetico: la referencia SE SIEMBRA desde lo versionado y los proyectos no.
  // En un solo directorio, la siembra tendria que distinguir que pisa y que no.
  const routes = cargarRoutes({ nodeEnv: 'production', dbPath: '/data/jokin_tools.db' });
  assert.notEqual(routes.referenceDir(), routes.projectDir());
});
