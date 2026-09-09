// EL MOTIVO DEL FALLO NO SE PIERDE, Y EL SIGTERM ES NUESTRO
//
// Reportado con la app caída y el mensaje entero delante:
//
//   El proceso de shmir-design ha fallado 3 veces seguidas […]
//   ÚLTIMAS LÍNEAS DE LA SALIDA DEL PROCESO, SIN INTERPRETAR:
//   el proceso terminó con código null (señal SIGTERM). Últimas líneas:
//
// y nada más. Ese mensaje no dice NADA de lo que pasó, y lo que dice es engañoso: el
// SIGTERM lo mandamos NOSOTROS, en `ensureRunning`, justo después de que
// `waitUntilReady` diera el arranque por fallido. O sea que el mensaje presenta
// nuestra REACCIÓN como si fuera la causa — la familia de la errata nº 136.
//
// La secuencia, leída del código:
//
//   1. `waitUntilReady` devuelve `{ok:false, reason}` — y ese `reason` es lo ÚNICO que
//      distingue las tres cosas que pueden pasar: se murió, contesta OTRO en el puerto,
//      o no contestó a tiempo;
//   2. `ensureRunning` hace `child.kill('SIGTERM')`;
//   3. el manejador de `exit` del hijo salta DESPUÉS y llama a `_recordFailure` con «el
//      proceso terminó … (señal SIGTERM)», que PISA `lastError`;
//   4. el cuarto intento entra por la rama de MAX_RESTARTS, que reporta `lastError` —
//      o sea el texto pisado.
//
// El motivo real se calculó, viajó al encabezado del intento que falló, y se perdió
// para el mensaje que el usuario acaba viendo. Principio nº 23 dentro de un módulo.
'use strict';

const test = require('node:test');
const assert = require('node:assert');

const proceso = require('../apps/shmir/process');

test('el motivo del ultimo fallo SOBREVIVE al SIGTERM que mandamos nosotros', () => {
  proceso._resetSupervision();
  proceso._recordReason('no contestó en 60000 ms');
  // Lo que hace el manejador de `exit` tras nuestro propio kill.
  proceso._recordFailure('el proceso terminó con código null (señal SIGTERM). '
    + 'Últimas líneas:\n');

  const estado = proceso.status();
  assert.equal(estado.lastReason, 'no contestó en 60000 ms',
    'el motivo se pierde en cuanto el hijo sale: es justo lo que paso en produccion');
});

test('y el mensaje de MAX_RESTARTS lo NOMBRA', () => {
  proceso._resetSupervision();
  proceso._recordReason('no contestó en 60000 ms');
  proceso._recordFailure('el proceso terminó con código null (señal SIGTERM). '
    + 'Últimas líneas:\n');

  const texto = proceso.exhaustedText();
  assert.match(texto, /no contestó en 60000 ms/,
    'sin el motivo, el mensaje no distingue «se murió» de «no contestó a tiempo» de '
    + '«contesta otro en el puerto», que son tres problemas distintos');
});

test('DICE que el SIGTERM es NUESTRO, en vez de darlo como causa', () => {
  proceso._resetSupervision();
  proceso._recordReason('no contestó en 60000 ms');
  proceso._recordFailure('el proceso terminó con código null (señal SIGTERM). '
    + 'Últimas líneas:\n');

  const texto = proceso.exhaustedText();
  assert.match(texto, /SIGTERM/);
  assert.match(texto, /lo mand[óo] el hub/i,
    'un SIGTERM sin dueño se lee como una causa externa y manda a mirar la plataforma');
});

test('sin salida del proceso lo DICE, y eso es informacion', () => {
  proceso._resetSupervision();
  proceso._recordReason('no contestó en 60000 ms');
  const texto = proceso.exhaustedText();
  assert.match(texto, /no escribió nada/,
    'que el hijo no escriba NI UNA LINEA en 60 s descarta cosas —un fallo de import '
    + 'deja traza— asi que no puede quedar como un hueco en blanco');
});

test('CONTROL: sin ningun motivo registrado NO se inventa uno', () => {
  proceso._resetSupervision();
  const texto = proceso.exhaustedText();
  assert.doesNotMatch(texto, /no contestó en/);
  assert.match(texto, /no se lleg[óo] a registrar/i,
    'no haber podido registrar el motivo y que no lo haya son cosas distintas');
});

test('el contador de reintentos se puede REARMAR sin redesplegar', () => {
  proceso._resetSupervision();
  proceso._recordReason('lo que sea');
  assert.equal(proceso.status().restarts, 0);
  // Y el mensaje dice como: un bloqueo permanente sin salida escrita deja la app caida
  // hasta que alguien adivine que hay que reiniciar el hub.
  proceso._recordFailure('algo');
  assert.match(proceso.exhaustedText(), /reintentar/i);
});
