// EL SONDEO NO DISTINGUÍA «MI PROCESO ESTÁ LISTO» DE «ALGUIEN CONTESTA EN ESE PUERTO».
//
// Tests primero. El fallo, con las palabras con que se pidió arreglarlo: *«que un
// arranque se dé por bueno porque conteste el proceso de otro es el Alu 0 % en su forma
// más pura»* — se afirma una cosa («ha arrancado») a partir de una comprobación que no
// la mira.
//
// CÓMO SE VIO. `test/calendario.test.js` corre la suite entera otra vez, así que su hijo
// levantaba Streamlit en el MISMO puerto fijo que el padre. El segundo muere con
// `EADDRINUSE`, `waitUntilReady` sondea el puerto, encuentra contestando al proceso del
// OTRO y da el arranque por bueno: dos pruebas del test de humo pasan y las dos
// siguientes sacan 502 en cuanto el otro para el suyo.
//
// Y EN PRODUCCIÓN ES PEOR QUE UN ROJO DE LA SUITE: un despliegue nuevo cuyo proceso no
// arranca —porque queda vivo el de la ejecución anterior, que es un caso que el propio
// `process.diagnose` ya contempla— se daría por arrancado, y lo que se sirve es la
// interfaz del despliegue VIEJO. El síntoma es «está fusionado pero no lo veo».
//
// DOS COMPROBACIONES Y NINGUNA SUSTITUYE A LA OTRA:
//
//   1. **el hijo propio sigue vivo**, mirado ANTES de sondear. El orden importa: estaba
//      escrito y sondeaba primero, así que el sondeo ganaba a la comprobación;
//   2. **quien escucha en el puerto es ESE hijo**, por el pid dueño del socket. Lo
//      primero no basta: un hijo vivo que todavía no escucha, con otro contestando, da
//      el mismo verde.
//
// Y TRES ESTADOS, no dos: donde no se puede mirar (sin `/proc`), la respuesta es
// `NO_COMPROBABLE` — que **no es «es el mío»**. Es la regla del `.out` sin resumen.
const { test } = require('node:test');
const assert = require('node:assert');
const http = require('node:http');
const { spawn } = require('node:child_process');

const proceso = require('../apps/shmir/process');

function servidor() {
  return new Promise(resolve => {
    const s = http.createServer((q, r) => r.end('ok'));
    s.listen(0, '127.0.0.1', () => resolve({ s, port: s.address().port }));
  });
}

// Otro proceso escuchando: es la forma EXACTA del fallo — alguien contesta en el puerto
// y no somos nosotros.
function ajeno() {
  return new Promise((resolve, reject) => {
    const hijo = spawn(process.execPath, ['-e', `
      const s = require('http').createServer((q, r) => r.end('ok'));
      s.listen(0, '127.0.0.1', () => console.log(s.address().port));
    `]);
    let salida = '';
    hijo.stdout.on('data', d => {
      salida += d.toString();
      const puerto = Number(salida.trim());
      if (puerto) resolve({ hijo, port: puerto });
    });
    hijo.on('error', reject);
  });
}

test('un socket NUESTRO sale PROPIO', async () => {
  const { s, port } = await servidor();
  try {
    const r = proceso.portOwner(process.pid, port);
    assert.equal(r.estado, proceso.IDENTIDAD.PROPIO, r.motivo);
  } finally {
    s.close();
  }
});

test('un socket de OTRO proceso sale AJENO — es la forma exacta del fallo', async () => {
  const { hijo, port } = await ajeno();
  try {
    const r = proceso.portOwner(process.pid, port);
    assert.equal(r.estado, proceso.IDENTIDAD.AJENO, r.motivo);
    // Y el motivo NOMBRA el puerto: un «no es tuyo» sin decir cuál no se investiga.
    assert.match(r.motivo, new RegExp(String(port)));
  } finally {
    hijo.kill();
  }
});

test('y preguntando por el pid del dueño de verdad, el MISMO puerto sale PROPIO', async () => {
  // Control adversario del anterior: sin esto, «AJENO» y «este detector dice AJENO a
  // todo» darían el mismo verde.
  const { hijo, port } = await ajeno();
  try {
    const r = proceso.portOwner(hijo.pid, port);
    assert.equal(r.estado, proceso.IDENTIDAD.PROPIO, r.motivo);
  } finally {
    hijo.kill();
  }
});

test('sin nadie escuchando NO es PROPIO: es NO_COMPROBABLE', () => {
  // No haber podido comprobar de quién es no es «es el mío». Misma regla que el `.out`
  // sin resumen.
  const { s, port } = { s: null, port: 0 };
  void s; void port;
  const r = proceso.portOwner(process.pid, 1);   // puerto reservado, nadie escucha
  assert.equal(r.estado, proceso.IDENTIDAD.NO_COMPROBABLE, r.motivo);
});

test('sin /proc tampoco se inventa nada: NO_COMPROBABLE con el motivo', async () => {
  const { s, port } = await servidor();
  try {
    const r = proceso.portOwner(process.pid, port, { procRoot: '/proc-que-no-existe' });
    assert.equal(r.estado, proceso.IDENTIDAD.NO_COMPROBABLE, r.motivo);
    assert.match(r.motivo, /proc/);
  } finally {
    s.close();
  }
});

test('EL HIJO MUERTO SE MIRA ANTES DE SONDEAR, aunque el puerto conteste', async () => {
  // LA REGRESIÓN. Con un hijo muerto y OTRO contestando en el puerto, `waitUntilReady`
  // decía que sí. La comprobación existía y estaba DESPUÉS del sondeo, así que el
  // sondeo la ganaba siempre.
  const { hijo, port } = await ajeno();
  try {
    const r = await proceso.waitUntilReady({
      port, timeoutMs: 2000, child: { exitCode: 1, pid: 999999 },
    });
    assert.equal(r.ok, false, JSON.stringify(r));
    assert.match(r.reason, /murió|termin/i);
  } finally {
    hijo.kill();
  }
});

test('un hijo VIVO que no es el que escucha tampoco vale', async () => {
  // La segunda mitad: la vida del hijo no basta. Aquí el hijo «vive» —nunca murió— y
  // quien contesta es otro; eso es exactamente lo que servía la app del despliegue
  // viejo.
  const { hijo, port } = await ajeno();
  try {
    const r = await proceso.waitUntilReady({
      port, timeoutMs: 2000, child: { exitCode: null, pid: process.pid },
    });
    assert.equal(r.ok, false, JSON.stringify(r));
    assert.match(r.reason, /no es el que se acaba de lanzar|AJENO|otro proceso/i);
  } finally {
    hijo.kill();
  }
});

test('el estado EXPONE la identidad, o la comprobación no se ve', () => {
  // Una comprobación que corre y no llega a ninguna pantalla es la mitad del arreglo.
  const s = proceso.status();
  assert.ok('identidad' in s, JSON.stringify(Object.keys(s)));
  assert.ok('pid' in s, JSON.stringify(Object.keys(s)));
});
