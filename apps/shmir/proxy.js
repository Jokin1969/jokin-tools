// ─── Proxy inverso hacia el proceso de Streamlit ────────────────────────────────
//
// Streamlit no es una página: es una página MÁS un WebSocket (`/_stcore/stream`) por el
// que viaja todo el estado. Así que hay que reenviar las dos cosas.
//
// **El agujero que esto cierra, y es el motivo de que el guardián viva en su propia
// función con sus propios tests**: el evento `upgrade` de un servidor HTTP de Node NO
// pasa por los middlewares de Express. `app.use('/shmir', requireApp(...), router)`
// protege la página y no protege el WebSocket. Sin `upgradeAllowed`, cualquiera que
// conozca la ruta abre el socket sin sesión y habla con la app.
//
// Sin dependencias nuevas: hay un único upstream, es nuestro, y está en 127.0.0.1.
const http = require('node:http');
const { canAccess } = require('../auth/apps-registry');

const COOKIE_NAME = 'jt_sid';
const HOST = '127.0.0.1';

// Mismo parser mínimo que `auth/middleware.js`. Se repite —ocho líneas— en vez de
// exportarlo desde allí porque allí es un detalle interno del middleware, y aquí la
// entrada es un `req` crudo del evento `upgrade`, que no tiene nada de Express.
function parseCookies(header) {
  const out = {};
  if (!header) return out;
  for (const part of String(header).split(';')) {
    const i = part.indexOf('=');
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    if (k) out[k] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

// ¿Puede este upgrade pasar? Devuelve el veredicto CON motivo: un socket que se cierra
// sin decir por qué es indistinguible de uno que falla por red.
function upgradeAllowed(req, { store, appId }) {
  const sid = parseCookies(req && req.headers ? req.headers.cookie : '')[COOKIE_NAME];
  if (!sid) {
    return { allowed: false, reason: 'sin cookie de sesión' };
  }
  const user = store.getSessionUser(sid);
  if (!user) {
    return { allowed: false, reason: 'la sesión no existe o ha caducado' };
  }
  if (!canAccess(user, appId)) {
    return { allowed: false, reason: `sin permiso sobre la app ${appId}` };
  }
  return { allowed: true, user };
}

// Una redirección del upstream apunta a SU dirección, que es interna.
//
// Fallo real: `/shmir` sin barra final hace que Streamlit conteste 307 con
// `Location: http://127.0.0.1:8501/shmir/`. El navegador la sigue, fuera del contenedor
// no hay nada escuchando ahí, y lo que ve el usuario es que «no hace nada» — sin ningún
// error en ningún log, que es el peor tipo de fallo.
//
// Se reescribe SOLO lo que apunta al upstream: una redirección a otro sitio es legítima
// y reescribirla la rompería.
// El `Origin` que manda el navegador es el del HUB, y Streamlit solo admite localhost y
// las IPs de su propia maquina (`server.enableCORS`). Detras de un proxy eso rechaza el
// WebSocket con un 403 — y el sintoma es de los peores: el HTML y los estaticos cargan,
// asi que se ve el ESQUELETO de la pagina, pero como todo el estado viaja por
// `/_stcore/stream` no se rellena nunca. Ningun error visible.
//
// Se reescribe el Origin al del propio upstream en vez de apagarle el CORS a Streamlit.
// Es mas estrecho y conserva la propiedad: lo unico que llega a Streamlit con un Origin
// aceptable es lo que pasa por ESTE proxy, que ya comprueba sesion y permiso en
// `upgradeAllowed`. Si algun dia el puerto quedara expuesto, la comprobacion de Streamlit
// seguiria ahi; con `--server.enableCORS=false` no quedaria ninguna.
function rewriteOrigin(headers, { port }) {
  if (!headers.origin) return headers;
  return { ...headers, origin: `http://${HOST}:${port}` };
}

// Las cabeceras «salto a salto» describen la conexión de ESE salto, no la respuesta, y
// un proxy no las reenvía (RFC 9110 §7.6.1). Se copiaban enteras con `{...upRes.headers}`.
//
// La que muerde es `transfer-encoding`: dice cómo va troceado el cuerpo en la conexión
// que ACABA aquí. Reenviarla anuncia un troceado que la conexión de salida no usa —Node
// pone el suyo— y en HTTP/2, que es lo que habla el borde de cualquier despliegue
// moderno, está PROHIBIDA: una respuesta que la lleva se rechaza o se queda colgada.
// Síntoma: una descarga que el navegador da por iniciada y que nunca recibe un byte.
const SALTO_A_SALTO = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailer', 'transfer-encoding', 'upgrade',
]);

function forwardableHeaders(headers) {
  const salida = {};
  for (const [nombre, valor] of Object.entries(headers || {})) {
    if (!SALTO_A_SALTO.has(nombre.toLowerCase())) salida[nombre] = valor;
  }
  return salida;
}

function rewriteLocation(location, { port }) {
  if (!location) return location;
  const prefijos = [`http://${HOST}:${port}`, `https://${HOST}:${port}`];
  for (const prefijo of prefijos) {
    if (location.startsWith(prefijo)) return location.slice(prefijo.length) || '/';
  }
  return location;
}

// Reenvía una petición HTTP al upstream y devuelve su respuesta tal cual.
//
// OJO CON LA RUTA. Montado con `app.use('/shmir', …)`, Express le QUITA el prefijo a
// `req.url`: dentro del router, una petición a `/shmir/` llega como `/`. Reenviar eso
// le pide a Streamlit —que sirve bajo `--server.baseUrlPath=/shmir`— una ruta que no
// existe, y contesta 404. No da ningún error por ningún lado: la app simplemente no
// aparece. `req.originalUrl` es la que conserva el prefijo y la query.
function proxyRequest(req, res, { port, timeoutMs = 120000, path = null }) {
  const ruta = path || req.originalUrl || req.url;
  const upstream = http.request(
    {
      host: HOST,
      port,
      method: req.method,
      path: ruta,
      headers: rewriteOrigin({ ...req.headers, host: `${HOST}:${port}` }, { port }),
    },
    upRes => {
      const cabeceras = forwardableHeaders(upRes.headers);
      if (cabeceras.location) {
        cabeceras.location = rewriteLocation(cabeceras.location, { port });
      }
      res.writeHead(upRes.statusCode || 502, cabeceras);

      // EL FLUJO DE RESPUESTA TAMBIÉN FALLA, y hasta hoy no lo recogía nadie.
      //
      // `upstream.on('error')` de abajo cubre el fallo al PEDIR —no se abre la conexión,
      // el proceso no está— y contesta 502 con el motivo. Pero un fallo DESPUÉS de las
      // cabeceras —el upstream que corta a mitad de una descarga— llega a `upRes`, que
      // no tenía manejador. Sin él pasan dos cosas y las dos son malas: el `error` sin
      // escuchador es una excepción no capturada que se lleva por delante el HUB ENTERO,
      // y mientras tanto el cliente se queda COLGADO sin fin ni error. Medido: el test
      // de este caso no terminaba nunca.
      //
      // Con las palabras de quien lo sufrió: «un error en el flujo de respuesta se traga
      // y deja 0 bytes, que es indistinguible de una descarga vacía legítima». NO es una
      // causa comprobada del fallo de producción —no se ha reproducido, ver la errata
      // nº 130— pero convierte un silencio en un mensaje.
      upRes.on('error', err => {
        // rule2-ok (equivalente en el hub): no se traga nada. O sale como 502 con el
        // motivo, o —si ya no se puede cambiar el estado— se rompe la respuesta Y se
        // deja el motivo en el log del servidor.
        if (!res.headersSent) {
          res.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' });
          res.end(
            `Se cortó la respuesta de shmir-design en ${HOST}:${port}: ${err.message}`
          );
          return;
        }
        // Las cabeceras ya salieron, así que el estado no se puede cambiar y el
        // `content-length` ya prometió una longitud. Terminar limpio aquí entregaría un
        // fichero TRUNCADO que se lee como una descarga hecha — que es justo lo que no
        // se puede distinguir. Se ROMPE la conexión: el navegador dice que la descarga
        // falló, que es la verdad.
        console.error(
          `[shmir] la respuesta se cortó después de las cabeceras (${req.originalUrl
            || req.url}): ${err.message}`
        );
        res.destroy(err);
      });

      // Y EL OTRO LADO: si el cliente se va —cancela la descarga, cierra la pestaña—,
      // `pipe` deja de escribir pero NO cierra la petición al upstream, que se queda
      // leyendo contra un socket muerto. Es el mismo agujero por el otro extremo.
      res.on('close', () => {
        if (!res.writableFinished) upstream.destroy();
      });

      upRes.pipe(res);
    }
  );

  upstream.setTimeout(timeoutMs, () => {
    upstream.destroy(new Error(`el proceso de shmir-design no respondió en ${timeoutMs} ms`));
  });

  upstream.on('error', err => {
    // rule2-ok (equivalente en el hub): no se traga nada. Se contesta 502 CON el motivo.
    // Sin esto la petición se queda colgada y el navegador no distingue «tarda» de
    // «está roto».
    if (!res.headersSent) {
      res.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' });
    }
    res.end(
      `No se pudo hablar con el proceso de shmir-design en ${HOST}:${port}: ${err.message}`
    );
  });

  req.pipe(upstream);
}

// Reenvía un upgrade a WebSocket. Se llama SOLO después de `upgradeAllowed`.
function proxyUpgrade(req, socket, head, { port }) {
  const upstream = http.request({
    host: HOST,
    port,
    method: req.method,
    path: req.url,
    headers: rewriteOrigin({ ...req.headers, host: `${HOST}:${port}` }, { port }),
  });

  upstream.on('upgrade', (upRes, upSocket, upHead) => {
    const cabecera = Object.entries(upRes.headers)
      .map(([k, v]) => `${k}: ${v}`)
      .join('\r\n');
    socket.write(`HTTP/1.1 101 Switching Protocols\r\n${cabecera}\r\n\r\n`);
    if (upHead && upHead.length) socket.unshift(upHead);
    upSocket.pipe(socket);
    socket.pipe(upSocket);
    upSocket.on('error', () => socket.destroy());
    socket.on('error', () => upSocket.destroy());
  });

  upstream.on('response', () => {
    // El upstream contestó sin cambiar de protocolo: no hay WebSocket que montar.
    denySocket(socket, 502, 'el proceso de shmir-design rechazó el WebSocket');
  });

  upstream.on('error', err => {
    denySocket(socket, 502, `no se pudo abrir el WebSocket: ${err.message}`);
  });

  if (head && head.length) upstream.write(head);
  upstream.end();
}

// Cierra un socket de upgrade con una respuesta HTTP legible en vez de a la brava.
function denySocket(socket, status, reason) {
  const textos = { 401: 'Unauthorized', 403: 'Forbidden', 502: 'Bad Gateway' };
  try {
    socket.write(
      `HTTP/1.1 ${status} ${textos[status] || 'Error'}\r\n`
      + 'content-type: text/plain; charset=utf-8\r\n'
      + 'connection: close\r\n\r\n'
      + `${reason}\n`
    );
  } catch {
    // rule2-ok: el socket ya está roto por el otro lado; no hay nada que informar y no
    // se oculta ningún fallo — lo único que quedaba por hacer era cerrarlo.
  }
  socket.destroy();
}

module.exports = {
  upgradeAllowed, proxyRequest, proxyUpgrade, denySocket, rewriteLocation, rewriteOrigin,
  forwardableHeaders,
  COOKIE_NAME,
};
