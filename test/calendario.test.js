// LA SUITE ENTERA, CORRIDA COMO SI FUERA DENTRO DE UN AÑO.
//
// De dónde sale: el 1 de septiembre de 2026 se puso roja sola una prueba del overview
// de Asignación. No la rompió nadie — su valor esperado (`has_month_period === true`)
// era cierto mientras «el mes en curso» fuese agosto de 2026, el mes que la prueba
// tenía escrito. Se escribió correcta y caducó sola.
//
// Es el principio nº 11 aplicado a los tests: la prosa envejece, y los valores
// esperados también. Y lo que hizo que durase cinco días es peor que el fallo: estaba
// fuera de la zona de quien miraba la suite, así que se leyó como ruido de fondo. Un
// fallo persistente que nadie reclama deja de informar de nada — un guardia con falsos
// positivos, a escala de suite entera.
//
// Lo que hace: volver a correr TODA la suite con el reloj 400 días por delante. 400 y
// no 30 porque cruza los tres límites de golpe —día, mes y año— y además cae en otro
// día de la semana (400 = 57·7 + 1). Si una prueba depende del calendario, aquí falla
// hoy en vez de dentro de un año en la máquina de otro.
//
// Lo que NO hace: decir CUÁL es la prueba dependiente antes de que falle. Cuando falle,
// la salida del hijo trae su nombre y su fichero, que es lo que hace falta.
//
// Correrlo dentro de `npm test` y no como comando aparte es deliberado: una
// comprobación que hay que acordarse de pedir es una comprobación que nadie pide.

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const DIAS = 400;
const RAIZ = path.join(__dirname, '..');

test('la suite entera pasa con el reloj 400 días por delante', { timeout: 300000 }, () => {
  if (process.env.CALENDARIO_HIJO) return;   // el hijo no se vuelve a lanzar a sí mismo

  // Las variables `NODE_TEST_*` que el runner pone en ESTE proceso NO se heredan: con
  // ellas puestas el hijo se cree un fichero de test lanzado por un padre, no descubre
  // nada y sale con 0 en 40 ms. Verde sin haber corrido nada — el «Alu 0 %» obtenido
  // sin buscar Alu. Por eso además se comprueba abajo CUÁNTAS pruebas corrió.
  const entorno = { ...process.env, SALTO_DIAS: String(DIAS), CALENDARIO_HIJO: '1' };
  for (const k of Object.keys(entorno)) if (k.startsWith('NODE_TEST')) delete entorno[k];

  // EL HIJO NECESITA SU PROPIO PUERTO PARA STREAMLIT, y esto no es una precaución.
  // `apps/shmir/process.js` fija el puerto en 8501 y el test de humo levanta la interfaz
  // de verdad, así que el hijo corría `shmir.smoke.test.js` contra el MISMO puerto que
  // el padre estaba usando en ese momento. Lo que pasa entonces no es un choque limpio:
  // el segundo Streamlit muere con `EADDRINUSE`, `waitUntilReady` sondea el puerto,
  // encuentra contestando al proceso del PADRE y da el arranque por bueno — así que las
  // dos primeras pruebas pasan, y en cuanto el padre para el suyo las dos siguientes
  // sacan **502**. Sale rojo a veces y verde a veces, y el rojo no señala a nada de lo
  // que este test existe para vigilar: es ruido dentro del guardia del calendario, que
  // es justo lo que lo haría dejar de leerse.
  entorno.SHMIR_PORT = String(Number(process.env.SHMIR_PORT || 8501) + 1);

  const r = spawnSync(
    process.execPath,
    ['--require', path.join(__dirname, 'helpers', 'reloj-adelantado.js'),
     '--test', 'test/**/*.test.js'],
    { cwd: RAIZ, encoding: 'utf8', env: entorno, maxBuffer: 64 * 1024 * 1024 },
  );

  if (r.status !== 0) {
    // La salida del hijo ENTERA, no un resumen: el nombre del test que cae y su
    // aserción son justo lo que hay que leer, y un «falló algo» obligaría a repetir
    // el experimento a mano para saber qué.
    const fallos = (r.stdout || '').split('\n').filter(l => l.startsWith('not ok'));
    assert.fail(
      `Con el reloj +${DIAS} días la suite cae. Los valores esperados de estas pruebas ` +
      `dependen del calendario y caducarán solas:\n` +
      fallos.map(l => '  ' + l).join('\n') +
      `\n\nSalida del hijo:\n${r.stdout}\n${r.stderr}`,
    );
  }

  // Y que haya CORRIDO, no sólo que haya salido con 0. Un hijo que no descubre ningún
  // fichero también sale con 0, y entonces esta prueba diría «verde» sin haber mirado
  // nada. El número se compara con el del padre: así no hay ninguna cifra escrita a
  // mano que se quede corta cuando alguien añada un test.
  const corridas = Number((/^# tests (\d+)$/m.exec(r.stdout || '') || [])[1] || 0);
  const ficheros = fs.readdirSync(__dirname).filter(f => f.endsWith('.test.js')).length;
  assert.ok(
    corridas >= ficheros,
    `el hijo dice haber corrido ${corridas} pruebas y aquí hay ${ficheros} ficheros de ` +
    `test: no ha descubierto la suite, así que su verde no significa nada.\n` +
    `${r.stdout}\n${r.stderr}`,
  );
});

test('y el reloj adelantado adelanta de verdad', () => {
  // Sin esto, el test de arriba pasaría igual si el parche no hiciera nada: el control
  // adversario de su propio instrumento. Un cliente que no se parece al real no prueba
  // nada, y un reloj que no se mueve tampoco.
  const r = spawnSync(
    process.execPath,
    ['--require', path.join(__dirname, 'helpers', 'reloj-adelantado.js'),
     '-e', 'process.stdout.write(String(new Date().getFullYear()))'],
    { encoding: 'utf8', env: { ...process.env, SALTO_DIAS: '4000' } },
  );
  assert.equal(r.status, 0, r.stderr);
  assert.ok(
    Number(r.stdout) >= new Date().getFullYear() + 10,
    `el reloj adelantado devolvió ${r.stdout}, que no está 4000 días por delante`,
  );
});
