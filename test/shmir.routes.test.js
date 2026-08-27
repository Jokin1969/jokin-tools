// El montaje en el hub: permisos, y que el WebSocket no se quede fuera del login.
const { test } = require('node:test');
const assert = require('node:assert');
const { useTempDb } = require('./helpers');

useTempDb();
const reg = require('../apps/auth/apps-registry');

test('la app está registrada, así que se puede conceder por usuario', () => {
  const ids = reg.appsMeta().map(a => a.id);
  assert.ok(ids.includes('shmir-design'), ids.join(', '));
});

test('su ruta es la que sirve el proxy', () => {
  const app = reg.appsMeta().find(a => a.id === 'shmir-design');
  assert.equal(app.path, '/shmir');
});

test('un usuario sin la app concedida NO la ve en el hub', () => {
  const suyas = reg.appsForUser({ role: 'user', apps: ['batchwork'] }).map(a => a.id);
  assert.ok(!suyas.includes('shmir-design'), suyas.join(', '));
});

test('y un admin sí', () => {
  const suyas = reg.appsForUser({ role: 'admin', apps: '*' }).map(a => a.id);
  assert.ok(suyas.includes('shmir-design'));
});

test('server.js monta /shmir detrás de requireApp y engancha el upgrade', () => {
  const fuente = require('node:fs').readFileSync(
    require('node:path').join(__dirname, '..', 'server.js'), 'utf8'
  );
  assert.match(fuente, /app\.use\('\/shmir', requireApp\('shmir-design'\)/);
  // Sin esto el WebSocket de Streamlit queda accesible sin sesión: el evento `upgrade`
  // no pasa por los middlewares de Express.
  assert.match(fuente, /server\.on\('upgrade'/);
  assert.match(fuente, /upgradeAllowed/);
});

test('un upgrade de OTRA app se cierra DICIENDO por qué', () => {
  // Este es el único handler de `upgrade` del hub, así que cierra todo lo que no sea
  // /shmir. Hoy ninguna otra app usa WebSocket. El día que una lo use, un socket que se
  // cierra sin motivo se lee como «no conecta» y cuesta horas; el mensaje dice dónde
  // está el reparto que hay que tocar.
  const fuente = require('node:fs').readFileSync(
    require('node:path').join(__dirname, '..', 'server.js'), 'utf8'
  );
  assert.match(fuente, /repartir por prefijo/);
  assert.ok(!/startsWith\('\/shmir'\)\) \{\s*socket\.destroy\(\)/.test(fuente),
    'sigue cerrando a la brava sin decir por qué');
});

test('el proceso se para al apagar el hub', () => {
  const fuente = require('node:fs').readFileSync(
    require('node:path').join(__dirname, '..', 'server.js'), 'utf8'
  );
  assert.match(fuente, /shmir\/process'\)\.stop\(\)/);
});

test('/shmir lleva su PROPIA CSP: la del hub no deja pasar a Streamlit', () => {
  // La del hub es global y estricta: `font-src 'self' https://fonts.gstatic.com` bloquea
  // la fuente de iconos de Streamlit, que viaja como `data:`. Se le da una política a
  // esta ruta en vez de relajar la del hub entero — las demás apps no tienen por qué
  // pagar lo que necesita ésta.
  const fuente = require('node:fs').readFileSync(
    require('node:path').join(__dirname, '..', 'apps', 'shmir', 'routes.js'), 'utf8'
  );
  assert.match(fuente, /Content-Security-Policy/);
  assert.match(fuente, /font-src 'self' data:/);
  assert.match(fuente, /worker-src 'self' blob:/);
  assert.match(fuente, /connect-src 'self' ws: wss:/);
});

test("y NO se relaja con 'unsafe-eval'", () => {
  // Se comprobó con un navegador de verdad que la app renderiza sin él. Añadirlo «por si
  // acaso» sería abrir un agujero para nada.
  const fuente = require('node:fs').readFileSync(
    require('node:path').join(__dirname, '..', 'apps', 'shmir', 'routes.js'), 'utf8'
  );
  assert.ok(!/'unsafe-eval'/.test(fuente.split('const CSP_SHMIR')[1].split(']')[0]),
    "la CSP de /shmir lleva 'unsafe-eval'");
});
