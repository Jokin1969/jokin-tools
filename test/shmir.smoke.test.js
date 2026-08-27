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
