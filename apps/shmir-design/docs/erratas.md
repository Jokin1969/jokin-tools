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

**El fichero está archivado**, no destruido: `data/reference/prnp_3utr_fabricado_1246nt.txt`,
md5 `328cfa074a9b002f9614fcce3f19e21f`, con `tests/test_fixture_negativo.py` reproduciendo
la errata sobre el dato de verdad. No entra a ningún diseño; su único uso es ese test.

Alineamiento global contra el 3'UTR de referencia (`shmir_design/alignment.py`):
**1231 identidades, 18 sucesos** — 5 deleciones, 9 inserciones, 2 sustituciones y **2
transposiciones**; +4 nt netos.

> Son 20 operaciones crudas pero **18 sucesos**: cuatro de las seis sustituciones se
> agrupan de dos en dos en las transposiciones. Sumar «6 sustituciones + 2
> transposiciones» contaría cuatro cambios dos veces.

> **El recuento por clase depende del alineador.** No hay descomposición canónica: el
> reparto de huecos lo decide la penalización de gap. `difflib.SequenceMatcher` alinea
> las mismas dos cadenas y da **7 deleciones, 10 inserciones y 1 sustitución** — otras 18
> operaciones, también +4 nt netos, igual de válidas; renderiza las dos transposiciones
> como parejas inserción+deleción. Los dos repartos describen el mismo cambio.
>
> Por eso **la regla de lectura se apoya solo en las clases PRESENTES, no en las
> frecuencias**: bajo los dos repartos hay inserciones, luego bajo los dos la lectura es
> «se generó». Y por eso el test que fija estas cifras se llama *regresión del
> alineador*: si alguien toca `alignment.MATCH/MISMATCH/GAP` o el algoritmo, ese test
> falla y lo que significa es que ha cambiado el alineador, **no** que hayan cambiado los
> ficheros. Para eso están los md5.

| tipo | ref | fabricado | cambio |
|---|---|---|---|
| deleción | 56 | 55 | `T` → – |
| inserción | 240 | 240 | – → `A` |
| deleción | 275 | 274 | `T` → – |
| deleción | 431 | 429 | `T` → – |
| sustitución | 433 | 431 | `G` → `T` |
| deleción | 722 | 719 | `A` → – |
| inserción | 768 | 766 | – → `A` |
| inserción | 807 | 806 | – → `A` |
| deleción | 941 | 939 | `T` → – |
| inserción | 950 | 949 | – → `A` |
| inserción | 959–960 | 959–962 | – → `A`, `T`, `C` |
| inserción | 986 | 989 | – → `T` |
| **transposición** | **1142–1143** | **1145–1146** | **`CT` → `TC`** |
| **transposición** | **1169–1170** | **1172–1173** | **`GT` → `TG`** |
| inserción | 1189 | 1193 | – → `A` |
| sustitución | 1240 | 1244 | `T` → `A` |

La divergencia de 420–440 que introduce el `TCTAGA` inexistente en la referencia son la
deleción de 431 y la sustitución de 433 juntas. Y hay **dos** transposiciones, no una: la
`CT`↔`TC` de 1142 y una `GT`↔`TG` en 1169 que no se había previsto.

**Dónde caen las dos transposiciones.** La de 1142–1143 está **dentro** del bloque
conservado ratón/humano 1138–1163; la de 1169–1170, a 6 nt de su extremo. Ese bloque
tiene **GC 23,1 %** (comprobado: `TTTTCTATATTTGTAACTTTGCATGT`) frente al 43,2 % del 3'UTR
entero: es la región de menor complejidad del transcrito, y ahí es donde se equivocó lo
que fuera que generó el bloque. **Cuando se diseñen los dos candidatos de ese bloque,
verificación reforzada.**

## Regla de lectura del perfil

El perfil de diferencias **distingue dos investigaciones distintas**, y esa sola línea
habría acortado varias tandas:

| perfil | qué pasó | dónde investigar |
|---|---|---|
| solo deleciones | **trasvase** — copiar de una pantalla pierde caracteres, y lo que pierde son las carreras de homopolímero | por dónde pasó el texto |
| hay inserciones, sustituciones o transposiciones | **generación** — un trasvase no puede añadir ni cambiar caracteres | de dónde salió la secuencia |

`alignment.Alignment.reading` la emite sola, y viaja en `format_text()`, así que aparece
en cualquier sitio donde se imprima un perfil. Con la errata nº 5 la lectura correcta era
«se generó» desde el primer alineamiento.

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

## 6 — El marco equivocado dentro de rango

`3utr:1185` impreso sobre un 3'UTR murino de 1242 nt: la ventana venía convertida al
3'UTR y la señal no. El número **cabe**, así que ningún invariante de rango lo caza — ni
el techo global de `coords.max_utr3()` ni el límite por especie. Lo cazó el **golden**,
al leer el diff de la regeneración.

Es el tercero de la misma familia en una semana. Los otros dos —`3utr:1784` sobre 1606 nt
y `3utr:1273-2191` sobre 1242— sí eran imposibles y sí los caza `coords.check_utr3_range`.

**Contramedida:** el invariante de rango, que cubre los imposibles, más el principio y su
corolario operativo en [`principios.md`](principios.md#1--el-invariante-caza-lo-imposible-no-lo-equivocado):
para toda magnitud derivada nueva, decidir si un valor equivocado pero dentro de rango es
posible; si lo es, no hay invariante y sólo el golden lo detecta.

## 7 — La hipótesis de la carrera de A

**Predicción de Joaquín Castilla (2026-08-26)**, anotada con su nombre porque el acierto
se habría anotado igual: los 45 pb de repetición simple que RepeatMasker daba sobre el
transcrito murino serían la **carrera de A de `3utr:480-500`**, y de cumplirse habría sido
**convergencia de dos criterios independientes** —nuestro filtro de homopolímeros y
RepeatMasker— sobre el mismo tramo.

**Refutada por el dato.** Llegó el `.out` real y la repetición es un **`(CTC)n` en
`tx:892-936`**, dentro del **CDS** (185-949). No toca el 3'UTR. La carrera más larga del
3'UTR murino son **10 A que acaban en `3utr:507`** (`tx:1456`), y ahí RepeatMasker no marcó
nada. **No hay convergencia de dos criterios.**

**Contramedida:** ninguna, porque no hubo error de código — hubo una hipótesis razonable
que el dato tumbó. Queda en el registro para que el registro siga midiendo algo: si sólo
se anotan las predicciones que salen bien, deja de ser un registro y pasa a ser un
argumento. Ver [`principios.md`](principios.md#3--una-predicción-refutada-se-anota-igual-que-un-acierto).

---

## 8 — Las 1773 ventanas «enmascaradas» que no lo estaban

**Predicción de Joaquín Castilla, 2026-08-27**, anotada con su nombre a petición suya y
con el mismo criterio que la nº 7: si sólo se anotan las predicciones que salen bien, el
registro deja de ser un registro y pasa a ser un argumento.

**Lo que se dijo.** Al ver «ventanas a tilar: 1221» arriba y «1773 ventana(s) no
evaluable(s) (bases desconocidas o enmascaradas)» abajo:

> «Si el enmascarado de repetitivos se aplica en coordenadas de transcrito sobre un
> tilado de 3'UTR, es el mismo fallo de marco del punto 1 — y estaría enmascarando 1773
> ventanas por un (CTC)n de 45 pb que está en el CDS.»

La hipótesis era razonable: el fallo de marco acababa de aparecer por cuarta vez en la
misma corrida, y una máscara aplicada en el marco equivocado es exactamente la clase de
cosa que produce un número absurdo sin dar ningún error.

**Lo que había, medido.** **Ninguna** de las 1773 estaba enmascarada, y ninguna tenía una
`N`. La corrida ni siquiera llevaba máscara cargada. Las 1773 eran las ventanas que **no
pasan los filtros biofísicos** —fallaban GC y homopolímero— y el recuento las llamaba «no
evaluables (bases desconocidas o enmascaradas)» porque ese texto estaba escrito a mano
junto al número, sin comprobar nada.

O sea: **la hipótesis del marco queda REFUTADA**, y lo que había debajo era el mismo fallo
por otra puerta — un texto que explica una causa que nadie ha comprobado.

**Lo que sí era cierto del diagnóstico**: los dos números venían de conjuntos distintos.
Pero no por la máscara: la estimación tilaba el 3'UTR (1242 nt → 1221 ventanas) y la
corrida el transcrito entero (2191 → 2170).

**Y una comprobación que la hipótesis habría dejado en pie**: el `(CTC)n` murino de
`tx:892-936` **sí** está entero en el CDS, así que sobre un mapa del 3'UTR no tiene sitio.
Eso se arregló aparte —no se dibuja y se cuenta— y no tiene nada que ver con las 1773.

**Contramedida**: el principio nº 4 de [`principios.md`](principios.md), y la
descomposición del recuento se emite entera en vez de por diferencias.

---

## 9 — El filtro que nunca dijo que no

**Predicción, de Joaquín Castilla, 2026-08-27**: `G4_diana` «ha estado excluyendo
candidatos sin que nadie lo supiera y hay que ver a quién».

**Refutada, y por el lado que no se esperaba.** Medido antes de tocar nada, sobre las dos
especies del proyecto:

| | ventanas de 22 nt | `G4_diana` FAIL | `G4_guia` FAIL |
|---|---:|---:|---:|
| ratón `NM_011170.3` | 1221 | **0** | **0** |
| humano `NM_000311.5` | 1585 | **0** | **0** |

**No excluyó a nadie nunca.** Ninguna ventana pasa a elegible al quitarlo, y ninguno de
los diez del panel entra ni sale. Lo que hacía no era excluir: era emitir **veredictos
`PASS` que nadie había autorizado**.

**Y eso es PEOR, no mejor.** El filtro sobrevivió sin procedencia desde el 25 de agosto
—implementado en `b544dd2`, empaquetado con GC y homopolímero, sin una sola cita frente a
una asimetría que citaba Turner 2004 y reproducía cinco valores— **precisamente porque
nunca decía que no**. Un filtro que rechaza se audita solo: alguien pregunta por qué cayó
su candidato y hay que enseñarle el criterio. Uno que siempre aprueba no lo mira nadie: no
genera ninguna pregunta, no aparece en ninguna queja, y su justificación no se pide jamás.
La ausencia de rechazos no es evidencia de que un criterio sea bueno; es la condición que
lo protege de ser revisado.

**Corolario, y es el que cambia cómo se trabaja**: **la revisión de procedencia no puede
priorizarse por impacto observado.** Ordenar la cola de auditoría por «cuántos candidatos
ha tumbado esto» pone al final exactamente los criterios que llevan más tiempo sin que
nadie los mire. El orden tiene que salir de la calidad de la ficha —qué cita, qué umbral,
quién lo autorizó— y no de las consecuencias visibles.

**Y una asimetría de rigor que sí es señal**: un filtro cuya justificación no está a la
altura de la de sus vecinos **en el mismo fichero** es sospechoso por esa sola razón, sin
necesidad de mirar lo que hace. `justificacion.py` existe justo para esto y a G4 se le
escapó por una grieta concreta: **el test que exige justificación recorre los campos de
`Thresholds`**, y G4 nunca llegó a tener un umbral que justificar — su criterio era una
expresión regular escrita a mano. Cualquier criterio futuro que no sea un número entra por
el mismo agujero.

**Contramedida**: `docs/procedencia-g4.md` con la arqueología entera, y el filtro fuera.
Para volver a entrar hacen falta tres cosas y las tres por escrito: **predictor con cita**,
**umbral con justificación**, y **decisión explícita de si es duro o desempate** — con el
voto de partida del responsable en «desempate, nunca filtro».

---

## 10 — El tracto de una sola base

**El fallo**: el tracto de polipirimidinas se calculaba contando pirimidinas hacia atrás
**desde el `AG` del aceptor** y parando en la primera purina. Sobre el intrón quimérico
—que tiene **once** pirimidinas contiguas en 119-129— devolvía **1 nt**, porque entre el
tracto y el aceptor hay un `AC` en medio.

**Y no daba ningún error.** Un tracto de 1 nt es un intrón que no empalma, y la app lo
habría emitido como dato, con su posición y su longitud, exactamente igual que uno bueno.
Es la misma familia que el mapa que se dibujaba mudo sobre 2191 nt rotulados «3'UTR»: el
cálculo estaba mal, la salida tenía la forma correcta, y nada se quejó.

**Lo que lo cazó**: el segundo intrón. No un test, no una revisión, no leer el código —
**meter un caso más**. Con el MVM, donde el tracto sí pega con el `AG`, la regla acierta
y no hay forma de ver que acierta por casualidad.

**Corolario, y es el que importa**: **un cálculo sólo se puede validar sobre más de un
caso.** Con un solo ejemplo no se distingue una regla correcta de una que coincide con
ese ejemplo, y ninguna cantidad de tests sobre ese único caso resuelve la diferencia —
todos comparten la misma ceguera. Aplica a los intrones igual que a las guías, y de la
misma forma: el `mvm_actual` fue durante meses el único intrón del registro, así que
**cualquier** regla de geometría escrita en ese periodo está calibrada sobre un caso y
hay que volver a mirarla al llegar el segundo.

**La regla nueva**: la racha de pirimidinas contiguas **más larga** en los 40 nt de
delante de la A del aceptor, con el **hueco** al aceptor emitido — no tiene por qué ser
cero. Medida en los dos: MVM 72-80 (9 nt, hueco 0), quimérico 119-129 (11 nt, hueco 2).
Las dos coinciden con lo declarado.

**Y una segunda cosa que salió por el mismo sitio**: el motivo del punto de ramificación
estaba calibrado sobre un solo intrón también. `YURAY` funcionaba en el MVM y perdía
`CTGAC` —el canónico de mamífero— en el quimérico. Recalibrado contra los dos casos
conocidos en `tests/test_calibracion_ramificacion.py`, que **es** la justificación:
`YTNAY` es el único de los cuatro probados que recupera los dos sin dejar de discriminar.
