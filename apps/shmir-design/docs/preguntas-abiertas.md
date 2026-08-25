# Preguntas abiertas

Regla 4, aplicada más allá de las URLs: lo que no está verificado no se escribe, se
pregunta. Cada entrada dice qué está bloqueado y qué se necesita para desbloquearlo.

## Abiertas

### 1. Endpoints

Ninguno verificado desde este proyecto: la política de red del entorno rechaza el
CONNECT a NCBI, Ensembl, UCSC y miRBase. Ver `endpoints-verificados.md`.

Desde que los datos de referencia son fixtures versionados
([`fixtures.md`](./fixtures.md)), esto ha dejado de ser un bloqueante del análisis: solo
limita el camino opcional `--fetch`.

### 2. Regla del desapareamiento de la pasajera — **no confirmada**

La pasajera del andamio miR-E lleva un desapareamiento en su posición 1: C donde el
complementario reverso daría T. La regla implementada es la transición T↔C, y está
derivada de **un solo ejemplo** (SGEP #111170).

Para fijarla hace falta: la secuencia de un segundo plásmido miR-E con una guía distinta
—LT3GEPIR (Addgene #111177) sirve— y comprobar que su pasajera cumple la misma
transición. Si el complementario reverso de esa guía empieza por A o por G, mejor: ese
es justamente el caso que hoy no está cubierto.

Hasta entonces `scaffold.py` la marca como `REGLA_NO_CONFIRMADA` y el aviso sale en cada
salida de oligos. Con A o G no se aplica ninguna transición y se avisa.

### 3. Flancos extendidos del pri-miR — sin decidir

Necesarios para el cassette AAV, no para el clonaje en SGEP. `extended_cassette()`
aborta en vez de inventarlos. Lo verificado es el 97-mero y solo el 97-mero.

### 4. Fixtures que faltan

- `data/reference/NM_011170.3.fa` y `NM_000311.5.fa`: 7 tests saltados hasta que estén.
- miRBase `mature.fa` (paso 10), export de gnomAD (paso 11), track `rmsk` (paso 2):
  cada uno necesita fichero **y** checksum registrado antes de usarse.

## Resueltas

### Definición de la asimetría — resuelta 2026-08-25

Especificación confirmada: ΔG(4 pb terminales del extremo 5' de la guía) − ΔG(4 pb
terminales del extremo 3' de la guía); positivo = extremo 5' menos estable = bueno;
umbral +0.5 kcal/mol; Turner 2004 ARN 37 °C sin término de iniciación; penalización
terminal AU de +0.45 en los dos extremos de cada tetrámero; calculado sobre la guía **ya
transformada** (U forzada en la posición 1), porque dentro de la horquilla la pasajera se
recalcula como complementario reverso de la guía modificada y ese par existe de verdad.

Implementado en `thermo.py`. Reproduce los cinco valores del bloque conservado.

**La especificación original tenía el signo invertido.** Se detectó porque el filtro
estaba en `NOT_RUN` esperando definición, no porque ningún test lo cazara: un error de
signo es un fallo de especificación y ningún test de consistencia interna lo ve. Por eso
`test_thermo.TestCorduraBiologica` comprueba ahora los dos signos contra dos guías de
composición conocida. Si se invierten, el pipeline seleccionaría sistemáticamente las
guías que cargan la hebra pasajera.

Advertencia que va en el código y que hay que mantener: aplicar la penalización terminal
en el límite **interno** del tetrámero no es rigurosamente correcto — ahí no hay fin de
hélice real. Es una simplificación operativa. Solo sirve para **ordenar** candidatos: es
un proxy heurístico, no una energía libre de dúplex, y no debe publicarse como tal.

### Motivo G-cuádruplex — resuelto 2026-08-25

Patrón canónico sobre la diana, confirmado, y **además** sobre la guía: una diana con
tramos de C produce una guía con tramos de G, y la guía es la molécula que se sintetiza.
Dos filtros separados: `G4_diana` y `G4_guia`.

### U forzada en la posición 1 — resuelto 2026-08-25

Afecta al oligo, no al sitio diana que se reporta. Confirmado.

### La N no cuenta como identidad — confirmado 2026-08-25

Sin eso, dos secuencias enmascaradas producirían bloques conservados fantasma.
