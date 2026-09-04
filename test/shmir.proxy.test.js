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
const { upgradeAllowed, proxyRequest, forwardableHeaders } = require('../apps/shmir/proxy');

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

test('reescribe el Location del upstream: si no, el navegador se va a 127.0.0.1', async () => {
  // Fallo real. `/shmir` SIN barra final hace que Streamlit conteste 307 con
  // `Location: http://127.0.0.1:8501/shmir/` — una URL ABSOLUTA a la dirección interna.
  // El navegador la sigue, no hay nada escuchando ahí fuera del contenedor, y lo que ve
  // el usuario es que «no hace nada». No sale ningún error en ningún log.
  const { server, port } = await upstream((req, res) => {
    res.writeHead(307, { location: `http://127.0.0.1:${port}/shmir/` });
    res.end();
  });
  const frente = http.createServer((req, res) => proxyRequest(req, res, { port }));
  const location = await new Promise((resolve, reject) => {
    frente.listen(0, '127.0.0.1', () => {
      const p = http.request({ port: frente.address().port, path: '/shmir' }, r => {
        r.resume();
        r.on('end', () => { frente.close(); resolve(r.headers.location); });
      });
      p.on('error', reject); p.end();
    });
  });
  server.close();
  assert.equal(location, '/shmir/');
});

test('y un Location que NO apunta al upstream se deja como está', () => {
  // No se reescribe todo por si acaso: una redirección a otro sitio es legítima y
  // reescribirla la rompería.
  const { rewriteLocation } = require('../apps/shmir/proxy');
  assert.equal(
    rewriteLocation('https://ejemplo.org/x', { port: 8501 }), 'https://ejemplo.org/x'
  );
  assert.equal(rewriteLocation('/shmir/otra', { port: 8501 }), '/shmir/otra');
  assert.equal(rewriteLocation(undefined, { port: 8501 }), undefined);
});

test('reescribe el Origin, o Streamlit rechaza el WebSocket con un 403', async () => {
  // Fallo real, y el síntoma es de los peores: el HTML y los estáticos cargan, así que
  // se ve el ESQUELETO de la página, pero como todo el estado viaja por
  // `/_stcore/stream` no se rellena nunca. Ningún error visible en ningún sitio.
  //
  // La causa: el navegador manda el Origin del HUB, y Streamlit sólo admite localhost y
  // las IPs de su propia máquina (`server.enableCORS`). Reproducido contra un Streamlit
  // de verdad: con el Origin del hub devuelve 403; con el Origin reescrito, 101.
  const { rewriteOrigin } = require('../apps/shmir/proxy');
  const salida = rewriteOrigin(
    { origin: 'https://jokins-tools-production.up.railway.app', host: 'x' },
    { port: 8501 }
  );
  assert.equal(salida.origin, 'http://127.0.0.1:8501');
});

test('y una petición SIN Origin se deja como está: no se inventa uno', () => {
  const { rewriteOrigin } = require('../apps/shmir/proxy');
  const salida = rewriteOrigin({ host: 'x' }, { port: 8501 });
  assert.ok(!('origin' in salida), JSON.stringify(salida));
});

test('el Origin reescrito llega al upstream en una petición normal', async () => {
  let visto = null;
  const { server, port } = await upstream((req, res) => {
    visto = req.headers.origin;
    res.writeHead(200); res.end('ok');
  });
  const frente = http.createServer((req, res) => proxyRequest(req, res, { port }));
  await new Promise((resolve, reject) => {
    frente.listen(0, '127.0.0.1', () => {
      const p = http.request(
        { port: frente.address().port, path: '/shmir/', headers: { origin: 'https://otra.org' } },
        r => { r.resume(); r.on('end', () => { frente.close(); resolve(); }); }
      );
      p.on('error', reject); p.end();
    });
  });
  server.close();
  assert.equal(visto, `http://127.0.0.1:${port}`);
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

// ─── Cabeceras «salto a salto»: un proxy NO las reenvía ───────────────────────
//
// Reportado (2026-09-04): en producción NINGUNA descarga llega — ni el informe en PDF
// (70 KB) ni el zip. El navegador dice «iniciando» y se queda en 0 bytes. Localmente,
// con este mismo proxy delante, la misma descarga cae en 0,1 s.
//
// Lo que este test cierra NO es «la causa comprobada» —no se ha podido reproducir el
// entorno de producción desde aquí y no se le asigna causa (principio nº 3)— sino un
// fallo REAL del proxy que encaja con el síntoma: `{...upRes.headers}` copiaba las
// cabeceras del upstream ENTERAS, incluidas las de salto a salto. `connection`,
// `keep-alive` y sobre todo `transfer-encoding` describen la conexión de ESE salto, no
// la respuesta: reenviarlas hace que la longitud o el troceado que anuncia la respuesta
// no sea el que va a viajar por la conexión de salida. En HTTP/2 —que es lo que habla
// el borde de un despliegue moderno— `transfer-encoding` está PROHIBIDA, y una
// respuesta que la lleva se rechaza o se queda colgada: el navegador ve una descarga
// que empieza y no llega nunca.
//
// Node pone la suya cuando hace falta, así que quitarlas es lo correcto en cualquier
// caso: la lista es la del RFC 9110 §7.6.1.
test('`forwardableHeaders` quita las de salto a salto y deja las demás', () => {
  const salida = forwardableHeaders({
    'content-type': 'application/octet-stream',
    'content-disposition': 'attachment; filename="x.bin"',
    'content-encoding': 'gzip',
    Connection: 'keep-alive',
    'keep-alive': 'timeout=5',
    'Transfer-Encoding': 'chunked',
    'proxy-authenticate': 'Basic',
    te: 'trailers',
  });
  // Lo que hace que el navegador guarde el fichero SIGUE pasando.
  assert.equal(salida['content-type'], 'application/octet-stream');
  assert.match(salida['content-disposition'], /attachment/);
  assert.equal(salida['content-encoding'], 'gzip');
  // Y lo del salto anterior no. Se comprueba por nombre en MINÚSCULAS y en mayúsculas:
  // un upstream puede escribirlas como quiera y una comparación sensible a la caja
  // dejaría pasar justo la que rompe.
  for (const fuera of ['Connection', 'keep-alive', 'Transfer-Encoding',
    'proxy-authenticate', 'te']) {
    assert.equal(fuera in salida, false, `${fuera} no puede reenviarse`);
  }
});

test('y el cuerpo de una descarga troceada llega ENTERO', async () => {
  // La otra mitad: quitar cabeceras no puede romper lo que sí tiene que llegar. El
  // upstream trocea y no declara longitud —el caso real de una descarga de Streamlit—
  // y Node pone su propio troceado en la salida, que es lo correcto: el troceado es de
  // cada conexión, no de la respuesta.
  const { server, port } = await upstream((req, res) => {
    res.writeHead(200, {
      'content-type': 'application/octet-stream',
      'content-disposition': 'attachment; filename="x.bin"',
      connection: 'keep-alive',
      'transfer-encoding': 'chunked',
    });
    res.end('12345');
  });

  const respuesta = await new Promise((resolve, reject) => {
    const frente = http.createServer((req, res) => proxyRequest(req, res, { port }));
    frente.listen(0, '127.0.0.1', () => {
      http.get({ port: frente.address().port, path: '/shmir/media/x.bin' }, r => {
        let cuerpo = '';
        r.on('data', d => { cuerpo += d; });
        r.on('end', () => { frente.close(); resolve({ headers: r.headers, cuerpo }); });
      }).on('error', reject);
    });
  });

  server.close();
  assert.equal(respuesta.cuerpo, '12345');
  assert.match(respuesta.headers['content-disposition'], /attachment/);
  // NO se comprueba aquí que falten `transfer-encoding` ni `keep-alive`: las pone NODE
  // en la conexión de salida, y son suyas. Confundir «no la reenviamos» con «no
  // aparece» daría un test que falla por lo correcto — y el arreglo obvio sería
  // quitarle a Node su propio troceado, que es peor que el fallo. Lo que se reenvía o
  // no lo fija el test de `forwardableHeaders`.
});
