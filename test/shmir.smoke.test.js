// TEST DE HUMO: levantar la interfaz de verdad y comprobar que RESPONDE.
//
// Por qué existe: hubo 2.767 tests en verde y la app no abría. Toda la superficie de
// «arranca y sirve» estaba sin cubrir — los tests miraban los argumentos y las funciones
// del proxy, no el resultado.
//
// Y una lección que va dentro del propio test: **el WebSocket se abre CON cabecera
// `Origin`**. Mi comprobación anterior usaba una petición cruda, que NO manda `Origin`, y
// por eso pasó mientras el navegador recibía un 403 y la página se quedaba con el
// esqueleto sin rellenar. Un cliente que no se parece al real no prueba nada.
//
// Lo que este test NO cubre, y hay que decirlo: el fallo de `global.developmentMode` sólo
// aparece cuando Streamlit está instalado con `pip install --target=`, porque lo decide
// por si su ruta lleva `site-packages`. Aquí vive en site-packages, así que este test no
// lo habría cazado. Eso lo cubren el test de que la bandera está en los argumentos y la
// comprobación de importación del build.
const { test, before, after } = require('node:test');
const assert = require('node:assert');
const http = require('node:http');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');

const proceso = require('../apps/shmir/process');
const { proxyRequest, proxyUpgrade } = require('../apps/shmir/proxy');

function hayStreamlit() {
  try {
    execFileSync(process.env.PYTHON_BIN || 'python3', ['-c', 'import streamlit'], {
      stdio: 'ignore',
    });
    return true;
  } catch {
    // rule2-ok (equivalente en el hub): ausencia de una dependencia OPCIONAL. No se
    // esconde ningún fallo — el motivo sale en el mensaje del skip.
    return false;
  }
}

const HAY = hayStreamlit();
const SALTAR = { skip: HAY ? false : 'NOT_RUN: Streamlit no está instalado (pip install -r apps/shmir-design/requirements-ui.txt)' };

let frente = null;

before(async () => {
  if (!HAY) return;
  const arranque = await proceso.ensureRunning({ referenceDir: '' });
  assert.ok(arranque.ok, `el proceso no arrancó:\n${arranque.reason || ''}`);
  frente = http.createServer((req, res) => proxyRequest(req, res, { port: proceso.PORT }));
  frente.on('upgrade', (req, socket, head) =>
    proxyUpgrade(req, socket, head, { port: proceso.PORT }));
  await new Promise(r => frente.listen(0, '127.0.0.1', r));
}, { timeout: 120000 });

after(() => {
  if (frente) frente.close();
  proceso.stop();
});

function pedir(ruta, headers = {}) {
  return new Promise((resolve, reject) => {
    const r = http.get(
      { host: '127.0.0.1', port: frente.address().port, path: ruta, headers },
      res => {
        let cuerpo = '';
        res.on('data', d => { cuerpo += d; });
        res.on('end', () => resolve({ status: res.statusCode, cuerpo, headers: res.headers }));
      }
    );
    r.on('error', reject);
  });
}

test('el proceso arranca y contesta a su ruta de salud', SALTAR, async () => {
  const r = await pedir('/shmir/_stcore/health');
  assert.equal(r.status, 200);
  assert.equal(r.cuerpo.trim(), 'ok');
});

test('la SEGUNDA VÍA de las descargas se sirve de verdad, y como TEXTO', SALTAR, async () => {
  // Errata nº 130. Lo que este test mide no es que el fichero exista: es que sale
  // **sin `Content-Disposition`** y con `text/plain`, que es lo único que hace que el
  // navegador lo PINTE en vez de entregárselo a su gestor de descargas — el mecanismo
  // en el que se quedan colgados el botón y el icono de la tabla.
  //
  // Se pide POR EL PROXY, como la página: comprobarlo contra el proceso hijo no
  // probaría que la ruta llega hasta aquí. Un cliente que no se parece al real no
  // prueba nada.
  const fs = require('node:fs');
  const path = require('node:path');
  const dir = path.resolve(__dirname, '../apps/shmir-design/ui/static');
  const nombre = `humo_${crypto.randomUUID()}.tsv.txt`;
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, nombre), 'a\tb\n1\t2\n');
  try {
    const r = await pedir(`/shmir/app/static/${nombre}`);
    assert.equal(r.status, 200, `la ruta estática no contestó: ${r.status}`);
    assert.equal(r.cuerpo, 'a\tb\n1\t2\n');
    assert.match(r.headers['content-type'] || '', /text\/plain/);
    assert.equal(r.headers['content-disposition'], undefined,
      'con Content-Disposition el navegador vuelve a la descarga, que es lo que falla');
  } finally {
    fs.unlinkSync(path.join(dir, nombre));
  }
});

test('y sin el sufijo .txt se sirve con su tipo real: es el MODO DESCARGA', SALTAR,
  async () => {
  // Dos cosas a la vez, y por eso el test es uno solo.
  //
  // (1) Es el CONTROL ADVERSARIO del sufijo: un `.tsv` sale como
  //     `text/tab-separated-values`, que el navegador NO pinta. Sin esto, «se sirve como
  //     texto» y «el servidor manda cualquier cosa como texto» dan el mismo verde.
  //
  // (2) Y desde el 2026-09-10 es además el modo que usa el botón MORADO «Descargar
  //     tabla» (`segunda_via.publish(..., inline=False)`). O sea que esta línea dejó de
  //     describir sólo una vía muerta: describe una viva. **No comparte mecanismo con
  //     los dos botones que no bajan nada** —aquéllos terminan en una pulsación
  //     SINTÉTICA sobre un `<a download>`; éste es una navegación de verdad, iniciada
  //     por una persona, a un fichero que ya está en disco—, y la errata nº 130 sigue
  //     SIN CAUSA ASIGNADA, así que esto la esquiva y no la arregla.
  const fs = require('node:fs');
  const path = require('node:path');
  const dir = path.resolve(__dirname, '../apps/shmir-design/ui/static');
  const nombre = `humo_${crypto.randomUUID()}.tsv`;
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, nombre), 'a\tb\n');
  try {
    const r = await pedir(`/shmir/app/static/${nombre}`);
    assert.equal(r.status, 200);
    assert.ok(!/text\/plain/.test(r.headers['content-type'] || ''),
      `sin sufijo salió como ${r.headers['content-type']}`);
  } finally {
    fs.unlinkSync(path.join(dir, nombre));
  }
});

test('y el que contesta es SU proceso, comprobado por el pid del socket', SALTAR, () => {
  // LA CALIBRACIÓN DEL GUARDIA, y sin ella no se puede poner. `portOwner` mira si el
  // inodo del socket en escucha está entre los descriptores del hijo: si Streamlit
  // bifurcara, el socket sería de un nieto y esto saldría AJENO sobre un arranque
  // CORRECTO — un guardia con falsos positivos se acaba apagando. Aquí se mide contra
  // el proceso de verdad, que es lo único que lo demuestra.
  const s = proceso.status();
  assert.equal(s.identidad, proceso.IDENTIDAD.PROPIO, JSON.stringify(s));
  assert.equal(
    proceso.portOwner(s.pid, s.port).estado, proceso.IDENTIDAD.PROPIO,
  );
});

test('la página se sirve POR EL PROXY y es la de Streamlit', SALTAR, async () => {
  const r = await pedir('/shmir/');
  assert.equal(r.status, 200);
  assert.match(r.cuerpo, /streamlit/i);
});

test('sin barra final redirige a una ruta RELATIVA, no a 127.0.0.1', SALTAR, async () => {
  const r = await pedir('/shmir');
  assert.ok([301, 302, 307, 308].includes(r.status), `status ${r.status}`);
  assert.ok(!String(r.headers.location).includes('127.0.0.1'), r.headers.location);
});

test('el WebSocket abre CON cabecera Origin, que es lo que manda un navegador', SALTAR,
  async () => {
    const resultado = await new Promise((resolve, reject) => {
      const req = http.request({
        host: '127.0.0.1',
        port: frente.address().port,
        path: '/shmir/_stcore/stream',
        headers: {
          connection: 'Upgrade',
          upgrade: 'websocket',
          origin: 'https://jokins-tools-production.up.railway.app',
          'sec-websocket-key': crypto.randomBytes(16).toString('base64'),
          'sec-websocket-version': '13',
        },
      });
      let hecho = false;
      req.on('upgrade', (res, socket) => { hecho = true; socket.destroy(); resolve('101'); });
      req.on('response', res => {
        hecho = true;
        resolve(`${res.statusCode}`);
        res.resume();
      });
      req.on('error', e => { if (!hecho) reject(e); });
      req.end();
      setTimeout(() => { if (!hecho) { req.destroy(); resolve('COLGADO'); } }, 15000);
    });
    assert.equal(
      resultado, '101',
      'Streamlit rechazó el WebSocket. Con un 403 la página carga el esqueleto y no lo '
      + 'rellena nunca: el Origin del hub no está en su lista blanca y hay que '
      + 'reescribirlo en el proxy.'
    );
  });
