# Registro de erratas

Errores que ya pasaron una vez y la comprobación que existe hoy para que no vuelvan a
pasar. No se borran: una errata borrada vuelve.

## 1 — Signo invertido en la asimetría

Los conteos de referencia 181/231 salieron de una especificación con el signo de la
asimetría al revés. Ningún test de consistencia interna lo habría detectado, porque el
código era coherente consigo mismo.

**Contramedida:** dos tests de cordura biológica en `thermo.py` que fijan los signos.
No se "arreglan" para que pase un valor nuevo: si fallan, lo que se revisa es la
especificación.

## 2 — Dos contadores mezclados

Los conteos 302/**322** mezclaban un filtro de seeds que solo afectaba al humano, así
que las dos columnas no eran comparables.

**Contramedida:** `biofisicos_ok` y `aptas` son dos nombres, dos métodos y dos columnas.
Ver `docs/pipeline.md`.

## 3 — Coordenadas transcritas a mano

Un desplazamiento de 3 nt en unas coordenadas escritas a mano en lugar de derivadas del
match. Reapareció en esta misma sesión: ventanas `269-291` (23 nt) y `222-242` (21 nt)
emitidas para guías de 22, y la misma ventana dada como `270-291` en un sitio y
`269-291` en otro.

**Contramedida:** `audit.Span` se deriva de la secuencia que describe y `Span.check()`
aborta si `fin - inicio + 1 != len(secuencia)`. `tests/test_intervalos.py` comprueba el
invariante sobre las salidas reales. El invariante cazó a la primera un caso legítimo
que yo había asertado mal: cuando el emparejamiento sale de `guia[1:]`, la ventana mide
un nt menos porque la posición 1 es de convenio (`dropped_convention_base`).

## 4 — El 3'UTR fabricado

Un 3'UTR anunciado como «1242 nt verificados» que en la cadena entregada traía **1246**.
Se detectó por longitud contra las coordenadas declaradas.

**Contramedida:** `reference.check_declared_length()` — cuenta la cadena **entregada**,
no la que se pretendía entregar. Y `manifest.tsv` registra `accession` con versión,
`longitud` y `url`, con un test que ata las dos parejas de cada transcrito de
referencia.

## 5 — La misma errata, con el agente equivocado (2026-08-26)

El 3'UTR que se pegó en miRarchitect se generó en conversación y se anunció como 1242 nt
verificados. El bloque entregado tenía **1246 nt**, md5 `328cfa074a9b002f9614fcce3f19e21f`.
Es la errata nº 4 otra vez, en otra mano.

Lo que costó: la corrida entera de miRarchitect quedó inservible, y varias tandas
persiguiendo hipótesis equivocadas — corrupción de la herramienta, corrupción del
trasvase, contaminación con adaptadores de clonaje. Ninguna era cierta. Todas las
discrepancias venían de comparar contra una referencia fabricada.

Dos hallazgos de esas tandas eran artefactos de la referencia equivocada y quedan
retirados como línea de investigación:

- el `TCTAGA` (XbaI) «ajeno»: es una ventana legítima del `.txt` fabricado, en su
  posición 431, diana en 415. El escaneo de sitios de restricción **se queda en el
  código** (`audit.RESTRICTION_SITES`), porque la comprobación sirve; lo que se retira
  es la conclusión;
- las anomalías de longitud (cuatro 21-meros y un 23-mero) eran daño de trasvase, no de
  la herramienta: el export limpio trae guía de 22 nt, diana de 22 y `End−Start+1 = 22`
  en las 26 filas. Longitud nominal 22, confirmada, dicotomía cerrada.

**Contramedidas nuevas:**

1. Ninguna secuencia entra al pipeline sin su md5 en el manifiesto. Ni pegada, ni
   transcrita, ni copiada de una conversación.
2. `check_declared_length()` en todo camino que anuncie una longitud.
3. `tools/export_utr3.py` escribe el 3'UTR a **fichero** con la longitud y el md5 en el
   nombre, y **no imprime la secuencia**. Lo que se sube a una herramienta externa es
   ese fichero. Lo que se pierde al copiar de una pantalla son las carreras de
   homopolímero, y eso no se ve.
4. Una guía que sea prefijo o sufijo de otra fila del mismo fichero se avisa: es la
   misma predicción mutilada, no una ventana más corta. En el fichero viejo la había y
   **mapeaba exacta**, porque el homopolímero se lo permitía — mapear exacto no
   demuestra estar intacta.
