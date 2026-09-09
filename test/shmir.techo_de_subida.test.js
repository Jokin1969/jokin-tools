// EL TECHO DE SUBIDA SE DECLARA, Y SALE EN LA PANTALLA ANTES DE ELEGIR FICHERO
//
// Reportado con la captura: el gestor pide `refseq_rna_human.fa`, se suelta el fichero
// de 320,9 MB y sale una X roja. Sin número, sin motivo y sin salida.
//
// La X la pone Streamlit: `server.maxUploadSize` NO estaba declarado, así que valía su
// defecto —200 MB— y el widget rechaza en el navegador cualquier cosa por encima. Un
// limite que rechaza sin decir cuál es no se distingue de una app rota, y el que lo
// sufre no tiene forma de saber si el fichero es demasiado grande o está corrupto.
//
// Se declara por DOS razones y ninguna es cosmética:
//
//   · un defecto no escrito es una decisión que nadie tomó, y esta decide qué ficheros
//     entran en el depósito — el catálogo del transcriptoma humano son ~160 MB y queda
//     a un pelo de los 200;
//   · y sin declararlo no hay número que enseñar en la pantalla.
'use strict';

const test = require('node:test');
const assert = require('node:assert');

const proceso = require('../apps/shmir/process');

test('maxUploadSize va DECLARADO en los argumentos', () => {
  const args = proceso.buildArgs();
  const flag = args.find(a => String(a).startsWith('--server.maxUploadSize='));
  assert.ok(flag, 'sin declararlo vale el defecto de Streamlit y nadie sabe cuál es');
});

test('y el valor sale de UNA constante, no escrito dos veces', () => {
  const args = proceso.buildArgs();
  const flag = args.find(a => String(a).startsWith('--server.maxUploadSize='));
  assert.equal(flag, `--server.maxUploadSize=${proceso.MAX_UPLOAD_MB}`);
  assert.equal(typeof proceso.MAX_UPLOAD_MB, 'number');
});

test('cubre el fichero legitimo mas GRANDE que el gestor pide', () => {
  // El catálogo de 3'UTR del transcriptoma humano son ~160 MB. Un techo por debajo
  // dejaría fuera un fichero que la propia app pide, y eso es peor que no tener techo:
  // la pantalla pediría algo que el widget rechaza.
  assert.ok(proceso.MAX_UPLOAD_MB >= 200,
    'el techo tiene que cubrir el transcriptoma, que es el mayor de los que se suben');
});

test('el hijo LO RECIBE, no solo el proceso padre', () => {
  const args = proceso.buildArgs({ port: 9999, basePath: '/x' });
  assert.ok(args.some(a => String(a).startsWith('--server.maxUploadSize=')),
    'con otro puerto o otra ruta el techo tiene que seguir yendo: es del servidor, no '
    + 'de una configuración concreta');
});
