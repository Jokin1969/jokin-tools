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
      headers: { ...req.headers, host: `${HOST}:${port}` },
    },
    upRes => {
      const cabeceras = { ...upRes.headers };
      if (cabeceras.location) {
        cabeceras.location = rewriteLocation(cabeceras.location, { port });
      }
      res.writeHead(upRes.statusCode || 502, cabeceras);
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
    headers: { ...req.headers, host: `${HOST}:${port}` },
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
  upgradeAllowed, proxyRequest, proxyUpgrade, denySocket, rewriteLocation, COOKIE_NAME,
};
