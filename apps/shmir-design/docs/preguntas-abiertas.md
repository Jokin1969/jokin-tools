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

### 2. NO DETERMINADO: de dónde salió el casete de 5.170 nt (2026-09-06)

**Qué se sabe, medido.** Un FASTA de producción se emitió sobre un casete de **5.170 nt**,
md5 `a9f6ac140d33f504313dc03ba7805b1f`, mientras el del depósito —`aav_casete.fa`— mide
**5.282** (md5 `74f3fd79…`, el mismo que declara haber subido su autor). Montando el panel
murino de verdad con las tres posibilidades:

| casete | contexto5 | contexto3 | construcción |
|---|---|---|---|
| el del depósito, entero (5282) | 3133 | 2067 | 5496 nt |
| ese mismo cortado 112 nt por el 3' (5170) | 3133 | **1955** | **5384** nt |
| ese mismo cortado 112 nt por el 5' (5170) | 3021 | 2067 | 5384 nt |

La geometría del FASTA de producción —**3133 / 1955 / 5384**— la reproduce **exactamente**
la segunda fila. Pero el md5 de ese casete cortado sería `0bfe9ea6…` y el de producción es
`a9f6ac14…`.

**Qué queda NO DETERMINADO, y se deja así a propósito.** La geometría cuadra y el md5 no,
así que **es otra molécula**: no es el fichero del depósito mal leído ni truncado al
cargarlo. De dónde salió, no se sabe. No está en el repositorio —barridos todos los
`.fa`, `.gb`, `.tsv`, `.seq` y `.txt`: ni un fichero de 5.170 nt ni una sola aparición de
ese md5—, así que vive únicamente en el volumen de producción, que desde el repositorio no
se ve.

**No se le asigna causa** (principio nº 3). Un diagnóstico equivocado cuesta más que
ninguno, y lo que hay son dos hechos —la geometría encaja, el md5 no— que juntos dicen
«otra versión del plásmido» y nada más.

**Qué lo desbloquearía**: el md5 que el panel de ficheros muestre para `aav_casete.fa` en
producción, y el que declare `contexto_origen` en el siguiente FASTA. Con el arreglo de la
errata nº 129 los dos salen a la vista sin gastar ninguna corrida, y la comparación
depósito ↔ versionado (`deposit_vs_versioned`) dice además si el casete era el único
fichero divergente.

### (resuelta 2026-08-25) Regla del desapareamiento de la pasajera

**Regla: la posición 1 de la pasajera nunca puede ser el complemento Watson-Crick de la
posición 22 de la guía.** Si aparea, el tallo se cierra y desaparece el bulge basal.

Evidencia: SGEP #111170 y LT3GEPIR #111177 llevan la misma horquilla shRen.713 con la
misma pasajera —lo que confirma que el desapareamiento es deliberado pero no discrimina
entre lecturas—, y el plegado del 97-mero completo lo resuelve. Comprobado aquí con
ViennaRNA: A, C y G dan la misma notación punto-paréntesis y el mismo ΔG (−44.50); la T
—la WC— cierra el tallo (−49.10).

Convención para elegir entre las tres válidas: **C, y A cuando la C es justo la
prohibida** (guía acabada en G). **Superada**: esa tabla fallaba con guías acabadas en
G, porque le faltaba el apareamiento tambaleante G:U. La regla vigente es estructural —
se pliegan las cuatro bases y se elige una que reproduzca la notación punto-paréntesis
de SGEP, con preferencia C > A > G > T sólo para desempatar.

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

No hay que fijarlo a ciegas: cada informe trae ahora un barrido de 0.5 a 2.0 kcal/mol
(`selection.penalty_sensitivity`) que dice si cambia **quién entra**. Si no cambia, el
valor es irrelevante para ese 3'UTR y queda documentado como insensible; si cambia, es
una decisión con consecuencias y hay que tomarla a propósito.

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

### El casete de la corrida del 2026-09-05 no es el versionado — 112 nt

**Medido, sin causa asignada.** Las construcciones de aquella corrida miden **5.384 nt**
con un contexto 3' de **1.955**; montadas hoy con el `aav_casete.fa` que hay en
`data/reference/` miden **5.496** con contexto 3' de **2.067**. La diferencia son 112 nt
y está **sólo en el flanco 3'**: el contexto 5' (3.133), el donante (3134) y el aceptor
(3428) coinciden exactamente.

Consecuencia práctica: los `md5` de aquel resultado **no validan** contra un panel montado
hoy, que es el guardia funcionando — un resultado de otra corrida no puede entrar.

Lo que NO se ha podido comprobar desde aquí, y por eso no se declara:

- si el casete que sirvió aquella corrida es otro fichero (el panel permite subirlo, y lo
  subido al volumen **se respeta** y no se pisa con lo versionado);
- si `/shmir` estaba sirviendo un commit distinto del actual;
- si el fichero de `data/reference/` cambió después. **No se versiona en git** (material
  de laboratorio, así declarado en el manifiesto), así que no hay historia que mirar.

Lo que sí queda hecho para que la próxima vez no haya que preguntarlo: el FASTA declara
ahora su convención y el estado del panel dentro del propio fichero. **Falta** que declare
también la procedencia del casete (md5 y longitud) y la versión de lo que lo produjo —
que es lo que habría contestado esto sin medir nada.

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
