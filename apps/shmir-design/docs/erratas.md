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

---

## 11 — «6 de 12» cuando eran «4 de 10»

**El fallo**: el semáforo decía *«Corrieron 6 de 12 filtros por candidato»*. Al retirar
G4 pasó a decir *«4 de 10»*. **Bajaron los dos números, no sólo el total.**

La cuenta estaba mal por los dos lados a la vez. `G4_diana` y `G4_guia` estaban en
`UNDECIDED_FILTERS`, así que se **excluían de los pendientes** —correctamente: su criterio
no estaba decidido y no debían bloquear la aprobación—, pero seguían **contando en el
total**. Y como los corridos se derivaban de `total − pendientes`, los dos acababan
sumando como **CORRIDOS**. Dos filtros que no habían corrido, que ni siquiera emitían
veredicto, inflaban la cuenta de los que sí.

**Sólo se vio al quitarlos.** No lo cazó ningún test —los tests comprobaban que G4 no
bloqueaba, que es lo que sí hacía bien—, ni el golden, que llevaba «6 de 12» congelado
como si fuera correcto desde el día que se escribió. Lo que lo destapó fue que al
eliminar el filtro los dos números bajaran, cuando sólo debía bajar el total.

**Tercera instancia del patrón de la errata nº 9**, y la más incómoda de las tres: **un
elemento que nunca dice que no puede pasar años inflando una cuenta sin que nadie lo
note.** No genera ninguna queja —no tumba candidatos—, no aparece en ningún informe de
fallo, y el número que altera es precisamente el que la gente usa para decidir si el
análisis está completo. Las tres instancias:

| | qué pasaba | por qué sobrevivió |
|---|---|---|
| nº 9 | G4 emitía veredictos sin procedencia | nunca excluyó a nadie |
| — | la cuenta del semáforo inflada en 2 | el filtro que la inflaba nunca fallaba |
| — | `DONORS_FORBIDDEN_IN_SPACERS` contiene donantes legítimos | sólo se aplicaba a espaciadores |

**Contramedida**: la del tercer caso, que es la única que se puede automatizar hoy —
`spacer_rejections` **aborta** si lo que recibe no es un espaciador, y la lista se llama
por su alcance. Para la cuenta, la única defensa real es la que ya funcionó aquí: **al
retirar algo, mirar qué números se mueven y comprobar que se mueven los que deben.**

---

## 12 — La comprobación a la que le faltaba una pieza

**El fallo**: `intron_folding` medía la accesibilidad de **donante, punto de ramificación
y ACEPTOR**. El **tracto de polipirimidinas no estaba**.

Los tres elementos frágiles son **donante, punto y TRACTO**; el aceptor es la frontera,
no lo que el espliceosoma lee para decidir. Así que cuando se pidió como criterio de
aceptación de los espaciadores «que los tres sigan desapareados», ese criterio **no se
podía evaluar** — y lo que había medido hasta entonces era otra cosa, con tres números,
con nombres correctos y con toda la pinta de estar completa.

**Nadie lo vio porque nadie había enumerado las piezas.** El test se llamaba
`test_corre_y_da_los_TRES_elementos` y pasaba: comprobaba que salieran tres, y salían
tres. Comprobaba la cantidad, no la identidad. Una comprobación compuesta parece completa
cuando sus componentes no están declarados en ningún sitio, porque no hay contra qué
contrastarla.

**Misma familia que el `.out` sin `.tbl`**: allí un frente parecía cerrado con un fichero
de dos porque nadie había listado los dos. Aquí una medida parecía completa con tres de
cuatro por la misma razón.

**Corolario**: **toda comprobación compuesta declara sus componentes en UN SOLO SITIO, y
lleva un test de que los evalúa todos.** No basta con contar cuántos salen — hay que
comprobar cuáles. La declaración es lo que convierte «faltó una pieza» en un fallo de
test en vez de en un descubrimiento a los meses.

**Contramedida aplicada**: `intron_folding.ELEMENTS` es la declaración, ahora con los
cuatro, y el test contrasta contra ella por identidad y no por cantidad. `barrido.FRAGILE`
declara aparte cuáles de esos cuatro son los frágiles, que es una pregunta distinta y por
eso es otra lista.

---

## 13 — La función citada como si existiera

**El fallo**: el registro de intrones decía, en el `why_missing` de `mvm_sin_criptico`,
que la variante «se genera con `intron_design.design_variant()`». **Esa función no
existía.**

**Y ésa es la peor de la familia**, que ya lleva tres esta semana:

| | qué es | cómo se lee |
|---|---|---|
| una función que falta y **se dice** | un `NOT_RUN` | «no está, y sé qué me falta» |
| una función **citada como existente** | un **`PASS` falso** | «hay un camino» — y no lo hay |

Un `NOT_RUN` manda a buscar algo. Un `PASS` falso manda a usar algo que no está, y el
descubrimiento llega cuando ya se contaba con ello. La diferencia no es de grado.

**Contramedida**: `tests/test_simbolos_citados.py` recorre **todos los literales de
cadena del paquete** —los `why_missing`, las fichas de obtención, los mensajes de error—
y comprueba que todo `modulo.simbolo` que citen exista de verdad. Un texto que nombra algo
inexistente hace fallar la suite.

Y el guardia tuvo que afinarse en su primera corrida, que dio **tres falsos positivos**:
`store.save_*` y `polya.CLEAVAGE_*` son FAMILIAS —el `*` se refiere a varios y ninguno se
llama así— y `mirarchitect.cs.put.poznan.pl` es un DOMINIO. Un guardia con falsos
positivos se acaba apagando; es la misma lección que el de la regla 6 y la del `GT…AG`.

---

## 14 — El test que comprobaba la forma y no el contenido

**El fallo**: `test_con_especie_sale_un_HUECO_DE_SUBIDA_por_fichero` exigía un hueco de
subida para `rmsk_mouse.out`, `mature.fa` y `aav_casete.fa` — **tres ficheros que ESTÁN**
en el directorio de referencia del paquete.

Pasaba porque el panel de entonces **pintaba el hueco estuviera el fichero o no**. El test
comprobaba que el panel tuviera la forma esperada, no que dijera la verdad sobre lo que
había. Sólo saltó al convertir el panel en gestor, cuando un fichero presente pasó a salir
con sus cuatro acciones en vez de con un hueco de subida.

**Misma familia que el del tracto** (errata nº 12), que se llamaba «da los TRES elementos»
y contaba en vez de identificar: salían tres y faltaba uno de los que importaban.

**Corolario, y va al principio nº 7**: **un test de estructura pasa cuando el contenido
está mal.** El valor esperado tiene que ser **lo que se dice**, no cuántas cosas se dicen
ni con qué forma. Contar widgets, contar elementos o contar filas no distingue una salida
correcta de una que tiene el mismo tamaño y dice otra cosa.

## 15 — El intrón que decía PASS con la secuencia vacía

**El fallo**: `intron_quimerico` declaraba `provided=True` en el registro y sacaba su
secuencia del plásmido de Addgene #198131. Ese fichero lo dejaba fuera de git el `*` del
`.gitignore` de `data/reference/`. Para cualquiera que clonara el repositorio:

```
provided=True   state=PASS   len(raw_sequence)=0
```

Y el guardia que existe justo para esto **no saltaba**: `require_sequence()` no llegaba
a su `ShmirDesignError` de la regla 1 porque `empty_sequence` caía primero en
`PIECES[""]` y moría con un `KeyError('')` — un error que ningún `except
ShmirDesignError` recoge y que ningún mensaje explica.

**Por qué era el peor de los tres**: no es una función que falta ni un texto equivocado.
Es un **PASS falso sobre una secuencia**, que es el principio central del proyecto. Un
intrón vacío anunciado como disponible es exactamente lo que la regla 1 existe para
impedir.

**Cómo se cierra**: no con un test que compruebe que `provided` y la secuencia coinciden
—eso comprueba que no ha pasado—, sino quitando la posibilidad de que diverjan.
`provided` **deja de ser un campo y pasa a ser una propiedad derivada**: hay secuencia si
hay piezas versionadas, o si llegó entera, y nunca si el intrón es `derived`. Es el mismo
cierre que se le dio al cuarto par duplicado, y por la misma razón.

Y el fichero entra en git: 22 kB de un depósito **público** no son «una base de datos»,
que es el criterio que ese `.gitignore` ya tenía escrito para las otras cinco
excepciones. Sin él dentro el intrón queda en NOT_RUN —correcto y **visible**— pero
nadie que clone puede reproducir la corrida.

## 16 — El punto 0 que medía el estándar

**El fallo**: `Intron.with_module` resolvía los espaciadores con
`spacer5 or PIECES["espaciador5"].sequence`. Una cadena vacía es falsa, así que pedir
**cero espaciador** devolvía silenciosamente los **20 nt estándar**.

El barrido de `barrido.py` empieza su curva en 0. Su punto 0, el que responde «¿y si no
hubiera espaciador?», montaba el intrón con los 65 nt estándar dentro y salía —
lógicamente — indistinguible del de referencia. Nada falló, nada avisó, y la curva
publicada tenía un punto que no medía lo que su etiqueta decía.

**CORREGIDO por el responsable (2026-08-27)**, y la corrección es suya: *«el barrido sí
discrimina en el lado 3', mi frase era de la corrida mal medida»*. Al medir el 0 de
verdad, el lado 3' **sí** discrimina en dos de los tres elementos (donante 0,58 contra
0,54; punto de ramificación 0,40 contra 0,36). La decisión no cambia —en los dos lados
el único largo admisible sigue siendo el punto de partida— pero el motivo sí, y ya no
puede decirse «el barrido no discriminó» a secas.

**Y el corolario queda MEDIDO, no estimado**, también por corrección suya: quitando los
**65 nt** de espaciador enteros, donante→punto baja de 256 a **191 nt** — sigue fuera del
rango típico (18-100). O sea que recortar espaciadores no alcanza, y **la palanca es el
módulo**: 149 de los 214 nt intercalados.

**La lección**: `""` y «no me lo digas» son **dos peticiones distintas** y se escribían
igual. Un centinela que se confunde con un dato legítimo no es un centinela. Ahora
`None` es el estándar y `""` es ninguno.

Suerte en la forma de descubrirlo: el resultado del barrido fue **negativo** —el criterio
no discrimina— y por eso su punto 0 no se usó para decidir nada. Con un resultado
positivo, esa habría sido la primera fila de la tabla.

## 17 — La página navegando el modelo

**El fallo**: el modal de empalme hacía
`variant_proposal_text(seleccion.selection.chosen[0].guide)`, y `selection.Choice` **no
tiene** `guide`. La guía se alcanza por `window_of(choice).evaluation.guide`, que es como
lo hace `block_bundle`. Resultado: `AttributeError` en cuanto alguien abriera el modal
con un candidato elegido.

Son dos fallos, y el segundo explica el primero: la página estaba **encadenando
atributos del modelo**, que es justo lo que prohíbe la regla 6. La navegación no se
equivocó por descuido — se equivocó porque estaba en el sitio donde nadie la prueba.
Movida a `presentation.variant_proposal_for()`, la cubre un test como todo lo demás.

**Corolario**: la regla 6 no es de estilo. Cada `a.b.c` en la página es una suposición
sobre el modelo que ningún test comprueba.

## 18 — `or` borra el valor que significaba algo

**El fallo, en tres sitios y con la misma forma**: `x or defecto` trata la cadena vacía,
el cero y el `None` como si fueran la misma cosa. Cuando el valor falso **significa
algo**, el `or` lo borra.

De los 73 usos de `x or defecto` del paquete, la mayoría son correctos —rellenar un md5
vacío con «SIN REGISTRAR» es exactamente lo que se quiere—. Los tres que muerden:

1. **`inicio_3utr or window.start`**, en `outputs.py` y en `selection.py`. `None` no es
   una posición que falte: es que la ventana **no cae en el 3'UTR** —una del ORF entra
   con `--cuota-region`— y el `or` la sustituía por la coordenada de **lo tilado**, que
   dos caracteres después se etiquetaba `Frame.UTR3`. Es la familia que este proyecto ya
   había cazado cuatro veces, por quinta vez, y esta vez **entrando por la puerta del
   `or`** en vez de por un `Frame.UTR3` escrito a mano.
2. **`species_prefix or 'de todas las especies del fichero'`**, en la **tasa base**.
   `None` es «nadie declaró la especie» y `""` es «todas, a propósito». Está escrito en
   `CLAUDE.md` que son dos cosas. Salían las dos como la segunda — en el número que el
   proyecto obliga a imprimir al lado de cada AVISO.
3. Lo mismo en los controles de la carga de off-targets.

**Lo que hace este caso distinto de un descuido**: el proyecto ya había hecho bien esa
distinción dos veces, con `divergent_positions=None` frente a `frozenset()` y con
`species_prefix` frente a `""`. No falló el concepto — la distinción está hecha **en el
dato** y se deshace **al imprimirlo**. Un dato que distingue y una salida que no, es una
salida que no distingue.

**La regla**: un centinela que se confunde con un dato legítimo no es un centinela.
`None` para «no hay valor», y el valor falso —`""`, `0`, `frozenset()`— reservado para
lo que de verdad significa. Al escribir `or`, la pregunta es: ¿puede el lado izquierdo
ser legítimamente vacío o cero? Si puede, hace falta `is None`.

## 19 — El tracto medido dentro de una ventana, y el borde

**No es un fallo de hoy: es una sospecha declarada.** `_ppt_span` busca la racha de
pirimidinas más larga en los 40 nt de delante del aceptor. Si la racha **empieza en el
borde** de esa ventana y la base anterior sigue siendo pirimidina, lo que se emite no es
la racha: es el trozo que cabía.

Ninguno de los dos intrones del registro lo toca —9 y 11 pirimidinas, muy dentro—, y ése
es justamente el motivo de **declararlo en vez de subir la ventana por si acaso**: la
auditoría de geometría existe para vigilar lo que hoy no muerde. Un tercer intrón con un
tracto largo lo tocaría, y el aviso ya está escrito.

Importa porque el tracto es la **referencia interna** contra la que se compara todo
sitio críptico: un tracto más corto de lo que es hace parecer más débil al aceptor
legítimo, y con él más fuerte a cualquier críptico.

**Del tipo que ningún invariante caza**: el valor es perfectamente posible y equivocado
—principio nº 7—, así que lo único que se puede hacer es decirlo, y sale en el informe
de geometría con o sin recorte.

## 20 — El guardia de las tildes con un agujero del tamaño de «intron»

**El fallo**: `_es_ingles` eximía un literal si **todas** sus palabras estaban en un
vocabulario inglés. Ese vocabulario existía por `"chimeric intron"` —el `label` con el
que se busca la feature en el GenBank del plásmido, que tildado deja de encontrarse—, y
para eximirlo entraron `intron` y `primer`. Las dos existen en los dos idiomas.

Resultado: **«primer intron»**, que es castellano con dos faltas, salía eximido entero.

**Un guardia que deja pasar justo lo que tenía que cazar es peor que no tenerlo**,
porque además tranquiliza: el contador decía «90 ficheros sin prosa sin tildes» y la
prosa estaba sin tildes.

**El arreglo es de clase, no de lista**: la excepción pasa a ser **por contexto** —una
lista de literales **exactos** que se usan como etiqueta de un fichero ajeno— en vez de
por vocabulario. Una etiqueta lo es por **dónde se usa**, no por cómo está escrita, y
cualquier heurística sobre las palabras vuelve a abrir el agujero.

**Y la segunda mitad, que casi se escapa**: la excepción funcionaba desde `corregir()`,
que recibe el **valor** de la cadena, y no desde el barrido del fichero, que pasa el
**token** con las comillas pegadas. O sea que la etiqueta salía exenta al probarla a
mano y acentuada al pasar el guardia sobre el fichero. Media excepción es peor que
ninguna: la prueba a mano decía que estaba cerrada.

## 21 — Cuatro corridas, dos sin el md5 de lo que consumieron

**El fallo**: `SeedScan` guardaba la procedencia del fichero de maduros como **prosa**
—`mature.provenance`, con el md5 en medio de una frase— mientras BLAST guardaba
`database.md5` y off-target `provenance.md5` como **campo**. Un md5 dentro de una frase
se lee; no se compara. Y OBSOLETO se deriva **comparando**.

**Y al mirarlo salió lo que el primer vistazo tapaba**: off-target consume **dos**
ficheros —el catálogo de 3'UTR y el de maduros— y sólo llevaba el md5 del primero. No
era «un campo que falta en uno de cuatro»: faltaba en **dos**, y en el segundo lo
escondía que el primero sí estuviera. Misma forma que la errata nº 12, la comprobación
que se llamaba «los TRES elementos» y contaba en vez de identificar.

**Se cierra con una tabla y no con cuatro `if`** (`insumos.CONSUMIDOS`): qué consume
cada tipo de corrida y en qué campo del registro vive su md5. Un quinto modal que no
declare sus insumos falla en la suite, no el día que alguien busque por qué su corrida
no se marcó obsoleta. Y la entrada de `corrida_empalme` está **vacía a propósito**, que
dice «se miró y no hay» — ausente diría «nadie lo miró».

## 22 — El veredicto que dependía de acordarse de una bandera

**El fallo**: la promoción por medida —el `AATATA` de `3utr:236` subiendo a
`APA_POSIBLE` porque PolyA_DB v4.1 mide su uso— sólo entraba si **el llamador se
acordaba** de resolverla y pasarla. `tile_utr(...)` a secas la omitía en silencio.

Los dos frentes de la app **sí** la resolvían, así que en la app el número estaba bien.
Lo que estaba mal es que **eso dependiera de tres sitios acordándose de lo mismo**, y ya
había fallado una vez: la cuarta divergencia entre la página y el CLI fue exactamente
ésta. Y hay una huella medible de que seguía costando: **doce ficheros de test** —y
cualquier análisis que alguien escribiera— corrían sin la promoción sin decirlo.

**No son dos ordenaciones, son dos veredictos**, y es lo que obliga a decidirlo así:

| | `3utr:221` |
|---|---|
| **sin** la medida | penalización de −1,00 por hexámero variante — **sigue en el panel** |
| **con** la medida | `AATATA` es `APA_POSIBLE` medido y 221 lo **solapa**: **FAIL duro** por riesgo estérico |

Y el dato existe: PSE 21,1 %, AvgRPM 0,55 — **el proximal más usado de los tres**. El
modo sin medida trata ese hexámero como no funcional, que es **la hipótesis menos
conservadora y además la falsa según lo medido**: el defecto favorecía al candidato
equivocado **por omisión**.

**Mismo criterio que el `.out` de RepeatMasker y que la casilla global que se quitó**: si
el dato está en el depósito y es válido, se usa. Una opción cuyo único efecto es
empeorar el veredicto en silencio no es una opción, es una trampa.

**El cierre no es una nota, es un centinela**: `tile_utr` resuelve la tabla por su cuenta,
`measured_apa=None` **aborta** —era el salto silencioso— y excluirla exige
`apa.ApaExcluded(reason=…)` con el motivo escrito, que **viaja al informe**. Sin él, «se
decidió no usarla» y «nadie se acordó» dan el mismo resultado mudo, que es la lección de
`deposito.Ignored`.

**Y la prueba de que sobraba**: los doce ficheros de test que pasaban la tabla a mano
dejaron de necesitar el argumento. Doce sitios acordándose de lo mismo son doce sitios
donde uno puede olvidarse.

## 23 — `APA_POSIBLE` decía lo mismo de dos cosas que no se parecen

**El fallo**: la clase no distingue **por qué** una señal es `APA_POSIBLE`, y las dos
vías son opuestas:

- el `AATAAA` de `3utr:288` lo es **por canonicidad** —y, cuando no hay tabla, **sin un
  solo dato de uso**: un supuesto, y el informe ya usaba esa palabra;
- el `AATATA` de `3utr:236` lo es **por uso medido** y **sin** canonicidad — por la
  cascada de predicción saldría `OTRA`.

El campo `evidence` ya las separaba. Lo que faltaba es que la distinción **viaje pegada a
la clase**: `evidence` quedaba cinco palabras más allá, donde no lo lee quien copia la
línea a un correo. Es la misma regla que el md5 junto a la longitud — separadas en dos
campos, la de al lado no se lee.

Ahora se emite `APA_POSIBLE (medido, PolyA_DB v4.1)` y `APA_POSIBLE (canónico, asumido)`,
y sólo en esa clase: ponerla en todas la haría invisible.

**Un detalle que corrigió el propio test**: con el ratón las **dos** señales están
medidas —288 también es uno de los tres sitios anclados—, así que el caso «canónico,
asumido» hay que buscarlo en el **humano**, donde la tabla no aplica por md5. La primera
versión del test daba por hecho que 288 era el caso asumido, y no lo es.

## 24 — El amplicón que el propio corte partía en dos

**Encontrado por el responsable del proyecto (2026-08-27)**, al leer el cambio de
coordenadas de la tanda anterior. Y es la primera vez que pasa esto en el proyecto, así
que va con esas palabras:

> **Un cambio de regla en el pipeline ha corregido un experimento de banco ANTES de
> hacerlo.**

**El fallo**: los amplicones de la RT-qPCR se habían diseñado contra el `AATAAA` de
`3utr:288`, cuyo corte cae en `3utr:303-323`. Ése era el corte **más temprano** —hasta
que la promoción por medida subió el `AATATA` de `3utr:236` a `APA_POSIBLE` y el corte
más temprano pasó a `3utr:251-271`.

Y ese tramo cae **entero dentro** del amplicón proximal viejo (`3utr:158-277`). No queda
a caballo: queda **partido en dos por el propio suceso que se quería medir**. Un amplicón
partido por un corte no da producto en la isoforma cortada, así que el proximal dejaría
de medir «el total» y **la razón distal/proximal no mediría nada**.

El distal viejo sí estaba bien colocado. Lo que invalida el par es el proximal.

**Lo que se evita no es una plaza del panel**: es una tanda de RT-qPCR cuya razón no
habría significado nada — y que habría parecido un resultado, porque saldría un número.

### La segunda mitad, que va contra la propuesta nueva

Al comprobar la corrección salió que la misma clase de fallo seguía viva en los
amplicones que este proyecto acababa de emitir. `rtqpcr_amplicons` recibe **una** señal y
coloca el distal justo detrás de **su** banda de corte: **no sabe que hay otra**.

El distal nuevo (`3utr:282-401`) queda entero detrás de `251-271` —correcto para esa
señal— y **atraviesa `303-323`**, la banda del `AATAAA` de 288. En la isoforma cortada
ahí tampoco amplifica.

**Y no se arregla moviéndolo**: entre las dos bandas, con 10 nt de holgura, quedan
`3utr:282-292` — **11 nt** para un amplicón de 120. Es **geométricamente imposible**
aislar el evento de 236 con esta arquitectura.

**Eso NO invalida el experimento**, y decirlo bien importa: la pregunta del panel es el
techo de sus seis candidatos con truncamiento, y los seis están detrás de **las dos**
bandas — el tramo de 0,86. La razón mide exactamente eso. Lo que **no** puede es
confirmar el **0,91 del tramo intermedio**, y quien lea el plan tiene que saberlo antes
de pedir cebadores. Ahora lo emite el propio plan (`AmpliconPlan.distal_crosses`,
`gap_between`), no una nota.

### Y una frase de este registro que era falsa

Aquí ponía que los amplicones iban «esquivando las dianas del panel». **Ni los nuevos ni
los viejos lo consiguen**: el proximal solapa `3utr:143-164` y `3utr:200-221` (los viejos
solapaban `143-164` y `221-242`). **El código sí lo decía** —lo marca con `⚠ solapa`— y
era la prosa de este fichero la que no. Por eso se mide sobre **tejido sin tratar**.

**La lección de método**: una función que diseña contra **una** señal en una secuencia
que tiene **dos** no está incompleta — está **equivocada**, y su salida tiene la forma
correcta. Es la familia del principio nº 7 aplicada a un diseño experimental.

## 25 — En humano seguimos en modo asumido, y no se veía

**No es un fallo de hoy: es una consecuencia del cambio de hoy que no era obvia.**

Con el ratón, las **dos** señales `APA_POSIBLE` están **medidas** —el `AATATA` de
`3utr:236` y el `AATAAA` de `3utr:288` son dos de los tres sitios anclados de PolyA_DB—.
Así que el caso «canónico, asumido» que la etiqueta nueva sabe emitir **no existe en esta
especie**.

Sólo existe en el **humano**, y por una razón exacta: la tabla se aplica **por md5 del
3'UTR**, así que sobre el humano devuelve `None` y sus dos `ATTAAA` (`3utr:955` y
`3utr:1167`) se quedan clasificadas por canonicidad y **sin un solo dato de uso**.

**Lo que eso significa cuando llegue el panel humano**: estaremos exactamente donde
estaba el ratón antes de mirar PolyA_DB. Y allí el modo sin medida resultó ser el
**equivocado** — al llegar la medida, una variante rara subió a `APA_POSIBLE`, tumbó a un
candidato del panel por solape estérico y adelantó la frontera de la inmunidad 52 nt.

**PolyA_DB v4 tiene entrada para PRNP en hg38** y quedó pendiente desde que se miró la
murina. No es un fichero que haya que ir a buscar: es la misma consulta cambiando la
especie en el selector. Ya está en la lista de ficheros que faltan y en la ficha de
obtención, **que ahora dice qué se pierde mientras no esté** en vez de listarlo como un
fichero más.

**Y el gen sale de `reference.REFERENCES`, no de una regla de mayúsculas**: `Prnp` en
ratón y `PRNP` en humano son dato declarado. En otro organismo el símbolo puede no seguir
ninguna de las dos convenciones — el mismo criterio que impide deducir `ocu-` del nombre
de la especie.

---

## 26 — «Esquivando las dianas del panel», que era falso de los dos pares

**Errata propia, y del tipo que este proyecto tiene ya catalogado**: una frase de prosa
que afirma un hecho que el código nunca dijo.

En `CLAUDE.md`, junto a los amplicones de la RT-qPCR, ponía que el par quedaba
«esquivando las dianas del panel». **No lo consigue ninguno de los dos pares.** El
proximal nuevo (`3utr:106-225`) solapa `3utr:143-164` y `3utr:200-221`; el proximal viejo
(`3utr:158-277`) solapaba `3utr:143-164` y `3utr:221-242`. No es que la frase envejeciera
al cambiar los amplicones: era falsa de los viejos también.

**El código sí lo decía.** `polya.rtqpcr_amplicons` marca cada solape con `⚠ solapa` y lo
emite pegado al plan. Quien leyera el informe lo veía; quien leyera el fichero que
gobierna el proyecto, no.

### Por qué importa más que una errata de redacción

Las dos consecuencias reales van en direcciones distintas:

- **Sobre tejido sin tratar** —que es como se mide, y está escrito— un solape es
  inofensivo: no hay corte por RNAi que confundir con isoformas.
- **Sobre tejido tratado** el mismo amplicón mediría **corte por RNAi**, no isoformas. La
  frase falsa era justo la que hacía parecer innecesaria esa precaución.

### Qué se ha hecho

La frase se ha sustituido por lo que el código emite, con los solapes nombrados uno a
uno, y hay un test (`tests/test_prosa_contra_codigo.py`) que comprueba que el registro no
vuelve a **afirmar** «esquivando las dianas del panel» — puede citarla entre comillas
como lo que fue, que es distinto.

Ver el corolario del principio nº 3: **cuando el código y la prosa discrepan sobre el
mismo hecho, la que se ha quedado atrás es la prosa, y es la que alguien va a leer.**

---

## 27 — La contramedida contra el peor fallo del proyecto, apoyada en el dato que ese mismo fallo retiró

**Es la peor de la serie, y no por lo que rompió: por lo que podría haber roto sin que
nada lo dijera.**

`external_score.EVIDENCE` registra la **dirección** de la escala de miRarchitect —si
menor es mejor— **con los pares (puesto, score) de los que salió**. Esos cinco pares
estaban transcritos a mano en el código. Al derivarlos del fichero versionado salió que
**no eran de ese fichero**: cuadran, uno a uno, con `mirarchitect_prnp_raton.tsv`.

Ese fichero es el que el manifiesto marca **«NO USAR»**. Se puntuó sobre el **3'UTR
FABRICADO de 1246 nt** — la errata nº 5, la que dejó inservible una corrida entera de
miRarchitect y se llevó por delante varias tandas persiguiendo hipótesis falsas.

### Por qué esto es peor que un número mal copiado

`lower_is_better()` no es una función cualquiera. Existe **exactamente** para impedir que
se ordene por un score cuya dirección no se conoce y se manden a síntesis **los peores
candidatos**. Es la contramedida escrita contra el modo de fallo más caro que este
proyecto sabe nombrar.

Y estaba apoyada en el dato que el propio fallo retiró.

### La dirección no cambió, y eso es suerte — no un atenuante

Los tres ficheros vienen crecientes en el score, así que la conclusión —menor es mejor—
es la misma con cualquiera de ellos. Pero eso es una propiedad del dato, no del método.
**Si la corrida retirada hubiera venido al revés**, hoy tendríamos:

- la dirección **invertida**,
- **cinco pares de aval** escritos al lado,
- el test de `EVIDENCE` **en verde** —comprueba que la evidencia es monótona consigo
  misma, y una evidencia invertida lo es—,
- `file_order_direction()` derivando del fichero bueno la dirección **contraria** a la
  registrada… y ahí sí habría abortado. Pero sólo al importar un fichero: `lower_is_better()`
  a solas habría seguido **aprobando**.

O sea: la mitad de la contramedida habría funcionado, y la otra mitad habría firmado el
error con cinco pruebas debajo.

### Tres sitios decían de dónde salía el dato, y ninguno acertaba

- la constante decía «corrida manual sobre el 3'UTR de Prnp murino»;
- `data/datos_en_codigo.toml` decía `mirarchitect_prnp_export.csv`;
- el ancla real era `mirarchitect_prnp_raton.tsv`.

**Ninguno de los tres era el fichero bueno.** Eso es lo que lo hizo invisible durante
semanas: cada sitio parecía confirmar a los otros dos.

### Qué se ha hecho

Los pares se **leen** de `mirarchitect_prnp_export_buena.csv` —la corrida sobre el 3'UTR
verificado— con `read_evidence_pairs`, y salen **todas** las filas: elegir cinco vuelve a
ser transcribir. Lo único que queda en código es **cuál es el fichero ancla**, que es una
decisión y tiene que verse en el diff.

Y deja dos principios, el **nº 12** y el **nº 13**, porque el mecanismo no era de esta
constante: era del método.

---

## 28 — Tres niveles del mismo dato transcrito, cada uno mintiendo por su cuenta

De la errata nº 27 salió el mecanismo; de arreglarlo salió esto, que es el mismo
mecanismo **repetido en capas**. La tabla de PolyA_DB tenía tres sitios diciendo cuál era
su hueco en el gestor, y **los tres estaban mal, cada uno de una forma distinta**:

**Nivel 1 — la FICHA describía otro fichero.** `fraccion_isoforma_larga.toml` explicaba
PolyA_DB de arriba abajo: su URL, sus dos tablas, sus columnas `PSE_3'READS` y
`AvgRPM_3READS` por su nombre, el aviso de que las coordenadas son genómicas. Y el rol al
que iba enganchada carga **otro formato**: tres columnas, `posicion/fraccion/nombre`, con
la posición ya convertida. Lo que el texto mandaba preparar y lo que el cargador sabe
leer eran cosas distintas.

**Nivel 2 — el LISTADO no nombraba el fichero que la ficha describía.** El único
`[[ficheros]]` de esa ficha era el del otro formato. O sea que la ficha explicaba cómo
conseguir un fichero que **no aparecía en su propia lista**.

**Nivel 3 — los NOMBRES estaban transcritos.** La ficha escribía `apa_medido_{slug}.tsv`
y el gestor pide `apa_medido.tsv` en ratón: la regla de sufijos por especie vivía en dos
sitios y no coincidían.

### Lo que esto enseña, y es lo que lo convierte en errata y no en tres arreglos

**Un dato transcrito en lugar de derivado no se desincroniza en un sitio: se
desincroniza en todos los que lo copiaron.** Cada copia envejece por su cuenta y en su
propia dirección, así que ninguna coincide con las otras y todas parecen plausibles por
separado. Es lo mismo que ya había pasado con los pares de `EVIDENCE` —la constante, la
tabla de auditoría y el ancla real, tres orígenes distintos y ninguno correcto— sólo que
aquí las tres capas estaban una encima de otra sobre el mismo dato.

Y ninguna de las tres daba error: la ficha se **lee**, el cargador se **ejecuta**, y
nadie los pone uno al lado del otro.

### El tercer nivel destapó tres huecos más

Al escribir `tests/test_ficha_contra_gestor.py` —que cruza, por especie, los ficheros que
el gestor pide contra los que la ficha nombra— salieron otras tres fichas incompletas:
la de **especificidad** no nombraba la base de RefSeq como fichero, la de **off-targets**
no nombraba `expresion_cerebro.tsv`, y la de **colisión de seed** no nombraba la capa
ampliada de abundancia. Ninguna se buscaba: aparecieron porque el cruce las miró todas.

### Qué se ha hecho

La ficha nombra ahora **el rol** (`{fichero_polyadb}`, `{hermano_rmsk}`) y el nombre lo
pone `species.required_files`, que es quien lo va a cargar. El informe que se entrega ya
dice `transcriptoma_3utr.fa` —lo que el cargador busca— en vez de
`transcriptoma_3utr_mouse.fa`, y el diff del golden es la prueba.

Es el principio nº 13 aplicado un piso más arriba: **lo que se declara es cuál, y el
nombre lo pone quien lo usa.**
