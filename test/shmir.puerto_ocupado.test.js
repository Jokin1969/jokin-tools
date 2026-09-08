// EL CASO DE PRODUCCIÓN, DE PUNTA A PUNTA: el puerto ocupado por OTRO.
//
// Es el que costó los tres días de «está fusionado pero no lo veo». Un despliegue nuevo
// levanta su Streamlit, el puerto lo tiene todavía un proceso de la ejecución anterior,
// el hijo muere con `EADDRINUSE`... y el arranque se daba por bueno porque el sondeo
// encontraba contestando al viejo. Lo que se sirve entonces es la interfaz del
// despliegue VIEJO, sin un solo error en ningún log.
//
// Este fichero corre en SU PROPIO PUERTO —`SHMIR_PORT` se pone antes de cargar el
// módulo, que lo lee al importarse—, y eso no es higiene: `test/shmir.smoke.test.js`
// levanta la interfaz de verdad en el puerto por defecto, y dos ficheros de test
// peleándose por un puerto es exactamente el fallo que este arreglo cierra, cometido
// dentro de la suite que lo comprueba.
//
// Y el puerto se DERIVA del que use esta corrida, no se escribe: el hijo del calendario
// corre con `SHMIR_PORT` desplazado, así que un número fijo aquí volvería a poner a
// padre e hijo en el mismo sitio — el mismo choque, un puerto más allá.
process.env.SHMIR_PORT = String(Number(process.env.SHMIR_PORT || 8501) + 96);

const { test, after } = require('node:test');
const assert = require('node:assert');
const http = require('node:http');
const { execFileSync } = require('node:child_process');

const proceso = require('../apps/shmir/process');

function hayStreamlit() {
  try {
    execFileSync(process.env.PYTHON_BIN || 'python3', ['-c', 'import streamlit'], {
      stdio: 'ignore',
    });
    return true;
  } catch {
    // rule2-ok (equivalente en el hub): dependencia OPCIONAL ausente, y el motivo sale
    // en el mensaje del skip.
    return false;
  }
}

const SALTAR = {
  skip: hayStreamlit() ? false : 'NOT_RUN: Streamlit no está instalado',
};

let okupa = null;

after(() => {
  if (okupa) okupa.close();
  proceso.stop();
});

test('con el puerto cogido por otro, el arranque FALLA en vez de darse por bueno',
  { ...SALTAR, timeout: 120000 }, async () => {
    okupa = http.createServer((q, r) => {
      // Contesta a la ruta de salud igual que Streamlit: el sondeo, por sí solo, no
      // puede distinguirlo. Ése es el punto entero.
      r.writeHead(200, { 'content-type': 'text/plain' });
      r.end('ok');
    });
    await new Promise(r => okupa.listen(proceso.PORT, '127.0.0.1', r));

    // El sondeo dice que sí — y no basta.
    assert.equal(await proceso.probe(proceso.PORT), true);

    const arranque = await proceso.ensureRunning({ referenceDir: '' });
    assert.equal(arranque.ok, false, JSON.stringify(arranque));
    // Y el motivo manda a mirar donde toca: el puerto, no «falta Streamlit».
    assert.match(arranque.reason, new RegExp(String(proceso.PORT)));
    assert.ok(
      /Address already in use|EADDRINUSE|no es el que se acaba de lanzar/i
        .test(arranque.reason),
      arranque.reason,
    );
    // La identidad queda registrada y NO es PROPIO.
    assert.notEqual(proceso.status().identidad, proceso.IDENTIDAD.PROPIO);
  });
