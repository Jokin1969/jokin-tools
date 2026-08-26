// El proxy hacia el proceso de Streamlit, y el agujero que hay que no dejar abierto.
//
// Streamlit no es una página: es una página MÁS un WebSocket (`/_stcore/stream`) por el
// que viaja todo. Y el evento `upgrade` de un servidor HTTP de Node **no pasa por los
// middlewares de Express**, así que `app.use('/shmir', requireApp(...))` NO lo protege.
// Si nadie comprueba la sesión ahí, la aplicación queda accesible sin login a través de
// su propio WebSocket, con la página de fuera pero los datos dentro.
//
// Por eso el guardián del upgrade tiene tests propios y separados del proxy.
const { test } = require('node:test');
const assert = require('node:assert');
const http = require('node:http');
const { useTempDb, makeUser } = require('./helpers');

useTempDb();
const store = require('../apps/auth/store');
const { upgradeAllowed, proxyRequest } = require('../apps/shmir/proxy');

// ── Un upstream de mentira: responde lo que se le diga y cuenta lo que recibe ──
function upstream(handler) {
  const server = http.createServer(handler);
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }));
  });
}

// ─────────────────────────── el guardián del upgrade ───────────────────────────

test('sin cookie de sesión el upgrade se DENIEGA', () => {
  const veredicto = upgradeAllowed({ headers: {} }, { store, appId: 'shmir-design' });
  assert.equal(veredicto.allowed, false);
  assert.match(veredicto.reason, /sesión/i);
});

test('con una cookie que no corresponde a ninguna sesión, DENEGADO', () => {
  const veredicto = upgradeAllowed(
    { headers: { cookie: 'jt_sid=inventada' } },
    { store, appId: 'shmir-design' }
  );
  assert.equal(veredicto.allowed, false);
});

test('con sesión válida y permiso sobre la app, PERMITIDO', () => {
  const u = makeUser(store);
  const sid = store.createSession(u.id).sid;
  const veredicto = upgradeAllowed(
    { headers: { cookie: `jt_sid=${sid}` } },
    { store, appId: 'shmir-design' }
  );
  assert.equal(veredicto.allowed, true);
  assert.equal(veredicto.user.email, u.email);
});

test('con sesión válida pero SIN permiso sobre la app, DENEGADO', () => {
  const u = makeUser(store);
  store.db.prepare('UPDATE users SET apps = ? WHERE id = ?').run('batchwork', u.id);
  const sid = store.createSession(u.id).sid;
  const veredicto = upgradeAllowed(
    { headers: { cookie: `jt_sid=${sid}` } },
    { store, appId: 'shmir-design' }
  );
  assert.equal(veredicto.allowed, false);
  assert.match(veredicto.reason, /permiso/i);
});

test('la cookie se lee entre otras y con espacios, como la manda un navegador', () => {
  const u = makeUser(store);
  const sid = store.createSession(u.id).sid;
  const veredicto = upgradeAllowed(
    { headers: { cookie: `otra=1; jt_sid=${sid}; tercera=x` } },
    { store, appId: 'shmir-design' }
  );
  assert.equal(veredicto.allowed, true);
});

// ─────────────────────────────── el proxy HTTP ───────────────────────────────

test('reenvía el método, la ruta y el cuerpo, y devuelve el estado del upstream', async () => {
  let visto = null;
  const { server, port } = await upstream((req, res) => {
    let cuerpo = '';
    req.on('data', d => { cuerpo += d; });
    req.on('end', () => {
      visto = { method: req.method, url: req.url, cuerpo };
      res.writeHead(201, { 'content-type': 'text/plain' });
      res.end('hecho');
    });
  });

  const respuesta = await new Promise((resolve, reject) => {
    const frente = http.createServer((req, res) => proxyRequest(req, res, { port }));
    frente.listen(0, '127.0.0.1', () => {
      const p = http.request(
        { port: frente.address().port, path: '/shmir/algo', method: 'POST' },
        r => {
          let texto = '';
          r.on('data', d => { texto += d; });
          r.on('end', () => { frente.close(); resolve({ status: r.statusCode, texto }); });
        }
      );
      p.on('error', reject);
      p.end('hola');
    });
  });

  server.close();
  assert.equal(respuesta.status, 201);
  assert.equal(respuesta.texto, 'hecho');
  assert.equal(visto.method, 'POST');
  assert.equal(visto.url, '/shmir/algo');
  assert.equal(visto.cuerpo, 'hola');
});

test('reenvía la ruta CON el prefijo del montaje, no la que Express recorta', async () => {
  // Express quita el prefijo del `app.use('/shmir', …)`: dentro del router, `/shmir/`
  // llega como `/`. Streamlit sirve bajo `--server.baseUrlPath=/shmir`, así que
  // reenviar la recortada da un 404 y la app no aparece — sin ningún error en ningún
  // log. Lo cazó una prueba de punta a punta, no un test unitario.
  let visto = null;
  const { server, port } = await upstream((req, res) => {
    visto = req.url;
    res.writeHead(200); res.end('ok');
  });
  const frente = http.createServer((req, res) => {
    req.originalUrl = '/shmir/algo?x=1';   // lo que hace Express al montar
    req.url = '/algo?x=1';                 // lo que ve el router
    proxyRequest(req, res, { port });
  });
  await new Promise((resolve, reject) => {
    frente.listen(0, '127.0.0.1', () => {
      const p = http.request({ port: frente.address().port, path: '/algo?x=1' }, r => {
        r.resume(); r.on('end', () => { frente.close(); resolve(); });
      });
      p.on('error', reject); p.end();
    });
  });
  server.close();
  assert.equal(visto, '/shmir/algo?x=1');
});

test('si el upstream no está, contesta 502 y NO deja la petición colgada', async () => {
  // Un puerto donde no escucha nadie. Sin esto, el navegador se queda esperando
  // para siempre y el usuario no sabe si tarda o si está roto.
  const frente = http.createServer((req, res) => proxyRequest(req, res, { port: 1 }));
  const respuesta = await new Promise((resolve, reject) => {
    frente.listen(0, '127.0.0.1', () => {
      const p = http.request({ port: frente.address().port, path: '/shmir/' }, r => {
        let texto = '';
        r.on('data', d => { texto += d; });
        r.on('end', () => { frente.close(); resolve({ status: r.statusCode, texto }); });
      });
      p.on('error', reject);
      p.end();
    });
  });
  assert.equal(respuesta.status, 502);
  assert.match(respuesta.texto, /shmir/i);
});
