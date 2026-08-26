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

test('el proceso se para al apagar el hub', () => {
  const fuente = require('node:fs').readFileSync(
    require('node:path').join(__dirname, '..', 'server.js'), 'utf8'
  );
  assert.match(fuente, /shmir\/process'\)\.stop\(\)/);
});
