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

### (resuelta 2026-08-25) Regla del desapareamiento de la pasajera

**Regla: la posición 1 de la pasajera nunca puede ser el complemento Watson-Crick de la
posición 22 de la guía.** Si aparea, el tallo se cierra y desaparece el bulge basal.

Evidencia: SGEP #111170 y LT3GEPIR #111177 llevan la misma horquilla shRen.713 con la
misma pasajera —lo que confirma que el desapareamiento es deliberado pero no discrimina
entre lecturas—, y el plegado del 97-mero completo lo resuelve. Comprobado aquí con
ViennaRNA: A, C y G dan la misma notación punto-paréntesis y el mismo ΔG (−44.50); la T
—la WC— cierra el tallo (−49.10).

Convención para elegir entre las tres válidas: **C, y A cuando la C es justo la
prohibida** (guía acabada en G). Elimina el caso de la G que antes quedaba sin decidir.

> **Discrepancia en la especificación, resuelta a favor del plásmido.** La instrucción
> decía «por defecto A; si la guía termina en T, entonces C», pero con «por defecto A»
> la guía de SGEP daría `AAGGAATT…` y la pasajera real del plásmido es `CAGGAATT…`. Se
> ha implementado la lectura que reproduce el plásmido y que satisface el resto de la
> instrucción. Si «por defecto A» era lo correcto, es un cambio de una línea — pero
> entonces el test de regresión contra SGEP falla.

### 3. Flancos extendidos del pri-miR — sin decidir

Necesarios para el cassette AAV, no para el clonaje en SGEP. `extended_cassette()`
aborta en vez de inventarlos. Lo verificado es el 97-mero y solo el 97-mero.

### 4. Fixtures que faltan

- `data/reference/NM_011170.3.fa` y `NM_000311.5.fa`: 7 tests saltados hasta que estén.
- miRBase `mature.fa` (paso 10), export de gnomAD (paso 11), track `rmsk` (paso 2):
  cada uno necesita fichero **y** checksum registrado antes de usarse.

### 3. Penalización por variante rara de poliadenilación — valor por confirmar

El filtro escalonado penaliza 1.0 kcal/mol a la ventana que solapa una variante `OTRA`,
en vez de excluirla. El mecanismo viene de la instrucción; **el valor es una convención
mía**, configurable en `SelectionConfig.weak_polya_penalty`.

### 4. El `GGGG` del contexto 3' del gBlock

La instrucción pide «sin homopolímeros ≥4» y el contexto 3' nativo de SGEP lleva un
`GGGG`. Aplicar la comprobación al módulo entero haría fallar todos los módulos,
incluido el de referencia, así que se aplica **solo a la parte variable**. Queda dicho
en el motivo del propio check.

### 5. Definición del espaciado de 50 nt — decisión tomada, confírmala

Implementado como distancia **entre las posiciones de inicio** de los candidatos
elegidos: dos candidatos a 50 nt exactos valen, a 49 no. La alternativa sería medir el
hueco entre las ventanas (que con ventanas de 22 nt daría 28 nt de separación real para
el mismo umbral). Si querías la segunda, es un cambio de una línea en
`selection._respects_spacing`.

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
