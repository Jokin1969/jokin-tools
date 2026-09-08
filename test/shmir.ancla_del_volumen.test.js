// EL ANCLA DE LA PERSISTENCIA ES EL VOLUMEN, NO `NODE_ENV`.
//
// Reportado el 2026-09-08: los proyectos dejaron de aparecer después de más de treinta
// despliegues buenos, y el aviso nuevo de la página lo dijo en una línea —
// `SHMIR_PROJECT_DIR NO está declarado`—, o sea que el proceso hijo no recibía la
// variable.
//
// MEDIDO sobre la derivación anterior, y esto es lo que la condena:
//
//   production + DB_PATH              -> /data/shmir/proyectos
//   production SIN DB_PATH            -> /data/shmir/proyectos   <- el defecto ya cubría
//   SIN NODE_ENV, con DB_PATH         -> ''                      <- AQUÍ
//   NODE_ENV mal escrito              -> ''                      <- Y AQUÍ
//
// O sea: **que falte `DB_PATH` NO vacía nada** —el propio defecto lo cubre—, y el único
// interruptor capaz de dejarlo vacío es `NODE_ENV`. Y `NODE_ENV` **no lo pone nadie de
// este repositorio**: viene del constructor de la plataforma. La persistencia de un
// registro de decisiones colgaba de una bandera de build que nosotros no declaramos, no
// probamos y no vemos.
//
// Arqueología, para no acusar al cambio equivocado: la derivación no la ha tocado ningún
// commit desde `17b25ac` (2026-08-27), `railway.toml` no cambia desde el commit inicial y
// el bloque `[variables]` de `nixpacks.toml` lleva ahí desde el 2026-05-02. Nada del
// repositorio explica el cambio.
//
// EL ANCLA PASA A SER EL DIRECTORIO DE LA BASE DE DATOS DEL HUB, que es lo que de verdad
// significa «aquí está el volumen» — y que es además la MISMA cuenta que hace `server.js`
// para crear `/data` y avisar si la base se sale de ahí. Si ese directorio existe, existe
// el volumen; si no existe, estamos en local. Eso es una MEDIDA del mundo, no una
// bandera: `NODE_ENV` desaparece de esta decisión.
const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

function cargar(entorno) {
  const antes = { ...process.env };
  for (const clave of ['SHMIR_REFERENCE_DIR', 'SHMIR_PROJECT_DIR', 'DB_PATH', 'NODE_ENV']) {
    delete process.env[clave];
  }
  Object.assign(process.env, entorno);
  delete require.cache[require.resolve('../apps/shmir/routes')];
  const routes = require('../apps/shmir/routes');
  for (const clave of Object.keys(process.env)) delete process.env[clave];
  Object.assign(process.env, antes);
  return routes;
}

test('con el volumen montado, los dos directorios salen de él SIN NODE_ENV', () => {
  const volumen = fs.mkdtempSync(path.join(os.tmpdir(), 'vol-'));
  try {
    const routes = cargar({ DB_PATH: path.join(volumen, 'jokin_tools.db') });
    assert.equal(routes.referenceDir(), path.join(volumen, 'shmir', 'reference'));
    assert.equal(routes.projectDir(), path.join(volumen, 'shmir', 'proyectos'));
  } finally {
    fs.rmSync(volumen, { recursive: true, force: true });
  }
});

test('y NODE_ENV ya no puede vaciarlos: era el único interruptor que lo hacía', () => {
  const volumen = fs.mkdtempSync(path.join(os.tmpdir(), 'vol-'));
  try {
    for (const nodeEnv of [undefined, 'development', 'produccion']) {
      const routes = cargar({
        DB_PATH: path.join(volumen, 'jokin_tools.db'),
        ...(nodeEnv === undefined ? {} : { NODE_ENV: nodeEnv }),
      });
      assert.equal(
        routes.projectDir(), path.join(volumen, 'shmir', 'proyectos'),
        `con NODE_ENV=${nodeEnv} el directorio de proyectos se ha vaciado`
      );
    }
  } finally {
    fs.rmSync(volumen, { recursive: true, force: true });
  }
});

test('sin volumen montado sigue siendo el del paquete, que es lo correcto en local', () => {
  // El caso local: `/data` no existe, así que no hay nada que declarar y la app usa el
  // directorio del paquete. Vacío aquí es la VERDAD, no un defecto que engaña.
  const routes = cargar({ DB_PATH: path.join(os.tmpdir(), 'no-existe-' + Date.now(), 'x.db') });
  assert.equal(routes.projectDir(), '');
  assert.equal(routes.referenceDir(), '');
});

test('una variable declarada a mano sigue mandando sobre todo lo demás', () => {
  const routes = cargar({
    SHMIR_PROJECT_DIR: '/declarado/proyectos',
    SHMIR_REFERENCE_DIR: '/declarado/reference',
    DB_PATH: '/data/jokin_tools.db',
  });
  assert.equal(routes.projectDir(), '/declarado/proyectos');
  assert.equal(routes.referenceDir(), '/declarado/reference');
});

test('el defecto de DB_PATH es el MISMO que usa server.js', () => {
  // Dos definiciones del mismo camino se desincronizan, y ésta decide dónde vive lo que
  // se guarda. Se comprueba contra el fuente de `server.js`, que es quien crea `/data`.
  const servidor = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
  const rutas = fs.readFileSync(
    path.join(__dirname, '..', 'apps', 'shmir', 'routes.js'), 'utf8'
  );
  assert.match(servidor, /DB_PATH \|\| '\/data\/jokin_tools\.db'/);
  assert.match(rutas, /DB_PATH \|\| '\/data\/jokin_tools\.db'/);
});

test('los dos directorios se DICEN en el arranque, con su origen', () => {
  // Sin esto, la pregunta «¿en qué directorio está guardando?» sólo se contesta abriendo
  // la app. La respuesta tiene que estar en el log del despliegue, que es donde se mira
  // cuando algo dejó de funcionar hace tres días.
  const routes = cargar({ DB_PATH: '/data/jokin_tools.db' });
  const linea = routes.describeDirs();
  assert.match(linea, /reference/);
  assert.match(linea, /proyectos/);
});
