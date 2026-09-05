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

---

## 29 — `verify()`: la única de la serie que producía CONFIANZA INFUNDADA

Es la cuarta vez que aparece el patrón —código escrito, probado y sin ningún llamador— y
la peor, por una razón que conviene escribir porque no es de grado:

**Las tres anteriores producían AUSENCIA DE INFORMACIÓN. Ésta producía CONFIANZA
INFUNDADA.**

- `masking.triple_motive_rows` — un detalle por ventana que se calculaba y no salía en
  ninguna salida. Faltaba información.
- `intron_folding` — lo mismo, un eje que no llegaba a la pantalla. Faltaba información.
- `store.save_*` — los cuatro modales calculaban y al cerrar la pestaña no quedaba nada.
  Faltaba información, y era mucha.
- **`store.ProjectStore.verify`** — no faltaba nada. Estaba **toda la disciplina de la
  cadena de md5**: cada línea del log lleva el md5 de la anterior, editar o borrar una
  vieja rompe la cadena, `verify()` lo dice con el número de línea, y hay un texto
  (`WHAT_THE_CHAIN_DOES_NOT_DO`) que explica con cuidado que no impide editar el fichero
  sino que lo vuelve **visible**.

  Todo eso existía **nominalmente**. Nadie llamaba a `verify()` fuera de sus tests, así
  que la cadena no se recalculaba nunca en la app y **nada era visible**. Un log editado
  se habría leído igual que uno íntegro.

La diferencia importa: de un hueco de información uno se entera al buscar el dato y no
encontrarlo. De una comprobación que no comprueba **no se entera nadie**, porque su
producto normal es el silencio — y el silencio es exactamente lo que se ve cuando todo
está bien.

### Cómo apareció, que es lo que más enseña

**No lo cazó la alcanzabilidad**, y no por descuido: **no podía**. Ese análisis mira
funciones de nivel de módulo, y `verify` es un **método**. La exclusión estaba declarada
y justificada con esta frase: *«no se pierde nada del modo de fallo que motiva esto — los
tres casos reales son funciones»*. Era cierta cuando se escribió, y **el cuarto caso la
refuta**.

Lo cazó **tener que rellenar una columna**: «cuándo se ejecuta». No hay respuesta posible
para `verify()` salvo *nunca*.

Y ésa es la lección, que va a principios como la nº 15: **la alcanzabilidad y la tabla de
guardias tienen la misma información y hacen dos preguntas distintas.**

| | |
|---|---|
| «nadie la llama» | se lee como **pendiente** — una fila más de una lista que obliga a decidir algún día |
| «cuándo protege» → *nunca* | no se puede leer de ninguna otra forma |

**Sólo una de las dos obliga a actuar.**

### Qué se ha hecho

- `presentation.project_open` llama a `verify()` en cada apertura, con regresión escrita.
  Su momento natural era evidente en cuanto se preguntó por él: el log se edita **entre
  sesiones**, así que comprobarlo sólo al escribirlo no protege de nada.
- La alcanzabilidad entra en los **métodos declarados como guardias** en
  `data/guardias.toml` — pocos, enumerados a mano, y de ellos ya se sabe que protegen
  algo. El resto de los métodos siguen fuera por la razón de siempre (215 filas de ruido).
- **Y las dos listas se cruzan**: un guardia sin quien lo invoque **sube de informe a
  fallo**, sin excepción posible. Ya cazó otro — ver abajo.

### Lo que el cruce encontró al estrenarse

`mirarchitect.Export.check_scaffold` — «el andamio se decide por SECUENCIA, no por
etiqueta», que es una regla escrita de este proyecto — **no lo llama nadie**. Y no es un
cableado olvidado: el único camino que existe (`tools/import_scores.py`) recibe un TSV de
dos columnas donde **no hay loop que comparar**, así que lo que decide es el `--andamio`
que teclea quien importa. La regla dice «fiarse de la etiqueta es lo que se deja de hacer
aquí» y el camino vivo se fía de la etiqueta.

Se ha hecho lo honesto y no lo cómodo: el veredicto **dice** que el andamio se comprobó
por etiqueta (`external_score.SCAFFOLD_BY_LABEL`), y el guardia por secuencia queda
declarado en `[sin_camino]` con **qué haría falta** para que corriera —que el CLI acepte
el export entero—. Es una decisión de interfaz, no un cableado, y no se toma de paso.

---

## 30 — Un frente cerrado que decía FALTA, con el `False` escrito a mano

**Fecha:** 2026-08-27. **Estado:** cerrada.

`species.fixture_report` construía la fila del frente del APA con **`available=False`
literal**. No era un valor calculado que diera falso: era un falso **tecleado**, de
cuando la tabla de PolyA_DB vivía en el código (`apa.POLYA_DB_PRNP`) y no había ningún
fichero que pudiera cerrar ese frente. Cuando el dato se mudó al gestor
—`data/reference/polya_db_mouse.tsv`, con su md5 en el manifiesto— **esa línea no se
enteró**.

### Qué se veía

Dos cosas a la vez, y las dos con pinta de medida:

- **el contador decía «4 de 7» y eran 5.** El frente estaba cerrado con un fichero que
  está en el depósito y que la corrida SÍ usa: es el que promociona el `AATATA` de
  `3utr:236` y saca a `3utr:221` del panel. O sea que la pantalla contradecía al
  resultado que ella misma acababa de imprimir;
- **`apa_medido.tsv` salía en ámbar, como algo que falta.** Mandaba a conseguir un
  fichero que no hacía falta, y encima uno cuya ficha de obtención explica cómo bajar
  PolyA_DB — que es exactamente lo que ya estaba dentro.

### Por qué no lo cazó nada

Porque un booleano escrito a mano no se puede desincronizar «con error»: se
desincroniza en silencio y sigue teniendo la forma correcta. Es el **principio nº 13**
—una constante que cita un fichero se deriva de él, nunca se transcribe— aplicado a
algo que ni siquiera parece un dato: un `False`. Y es la tercera capa del mismo montón
de la errata nº 28: la ficha, el listado, los nombres… y la **disponibilidad**.

### Qué se ha hecho

- `available` se **DERIVA** de los ficheros presentes, y son **DOS** los que cierran ese
  frente: `polya_db_<especie>.tsv` o `apa_medido_<especie>.tsv`. Cualquiera basta.
- El panel gana un estado propio, **`NO USADO`**, para una alternativa cuyo frente ya
  cierra otro fichero. No es trabajo pendiente y no puede compartir color con lo que sí
  falta: la fila dice **qué fichero** lo cierra, por su nombre.
- `tests/test_dos_momentos.py` fija las dos direcciones: con la tabla dentro,
  `apa_medido.tsv` es `NO USADO`; sin ella, vuelve a ser `FALTA`.

### Y la pregunta que abrió: ¿sobra uno de los dos roles?

No. Se ha mirado qué carga cada uno (`apa.APA_ARE_TWO_FILES`) y no son dos formatos del
mismo fichero: `polya_db_<especie>.tsv` es PolyA_DB **en crudo** —coordenadas genómicas,
PSE y AvgRPM, anclado por los cuatro puntos— y de él sale la **promoción por medida**;
`apa_medido_<especie>.tsv` son posiciones **ya convertidas** a coordenadas de 3'UTR con
su fracción, y alimenta `apa_assessment`. El caso del segundo es justo el fichero que
este proyecto tiene pendiente: **3'-end seq de cerebro murino**, la medida *en nuestro
tejido*, que PolyA_DB no puede dar porque su 0,86 es de **todos** los tejidos.

**Lo que sí hay que decir, y queda declarado en vez de callado:** hoy los dos producen
un techo de knockdown por caminos **independientes** —`apa_assessment` no mira la tabla
de PolyA_DB y `resolve_measured` no mira los sitios convertidos— y **nada obliga a que
coincidan**. Es el patrón de los dos contadores del mismo suceso, el mismo que ata un
test entre `seed_load.seed_load` y `offtarget`. Ese test aquí **no se puede escribir
todavía**: el segundo fichero no existe, y fabricarlo sería inventarse la medida
(regla 5). El día que llegue el 3'-end seq, lo primero es cruzar los dos techos, no
enchufarlo.

### RECTIFICACIÓN DE JOAQUÍN CASTILLA, 2026-08-27 — anotada con su nombre a petición suya

> «Rectifico lo de `apa_medido.tsv`: **no era un residuo**. Tienes razón en que son dos
> preguntas —PolyA_DB en crudo frente a posiciones ya convertidas— y en que el segundo
> tiene un uso real pendiente.»

Va con su nombre por la misma razón que la predicción refutada de la carrera de A
(errata nº 7): **si sólo se anotan las rectificaciones ajenas, el registro deja de ser un
registro y pasa a ser un argumento.** La sospecha inicial era razonable —dos roles vivos
para la misma pregunta huele a residuo— y comprobarla es lo que la deshizo.

### Y LA DIRECCIÓN DE LA DISCREPANCIA, que es la parte que hay que retener

Añadido por el mismo responsable, y es lo que convierte «cruzar los dos números» en algo
accionable (`apa.EXPECTED_DIRECTION`, emitido en el informe):

**Si los dos techos discrepan, no es un fallo: es el dato.** PolyA_DB promedia **todos**
los tejidos y las neuronas **alargan** los 3'UTR, así que lo esperable es que el techo de
cerebro sea **mayor** que 0,86:

| resultado | lectura |
|---|---|
| cerebro **>** PolyA_DB | **CONFIRMA el modelo.** El 0,86 se declaró como límite inferior y el dato del tejido lo mejora, que es justo lo que se anticipó. |
| cerebro **<** PolyA_DB | **PARAR.** Contradice la dirección conocida del sesgo. Antes de mover ningún veredicto hay que buscar la causa: el anclaje, el md5 del 3'UTR, o que una de las dos tablas no sea del gen que dice. |

**Y no se promedian.** Sin esta dirección escrita, quien reciba el 3'-end seq y vea un
número distinto de 0,86 lo tratará como un error a reconciliar y hará la media — que es
perder exactamente la información que la discrepancia lleva dentro. Es la misma clase de
frase que «rebaja, no descarta»: las dos ramas van juntas o ninguna sirve.

---

## 31 — `--rmsk` abortaba con un `NameError`, y con él el bloque que se cableó para no correrlo a mano

**Fecha:** 2026-08-27. **Estado:** cerrada. **Cómo apareció:** escribiendo el test que
corre el CLI **con máscara** para comprobar otra cosa.

`tools/design.py` pasaba `thresholds=umbrales`. **`umbrales` no existe en ese módulo** —
la variable se llama `thresholds`, y está definida tres llamadas más arriba en la misma
función. Así que **toda** corrida del CLI con `--rmsk` moría con un `NameError`, y con
ella todo lo que cuelga de esa rama:

- el **triple motivo por ventana** (`masking.triple_motive_rows`), que se cableó
  precisamente porque *«existía sólo porque alguien lo corría a mano»*;
- y, desde hoy, la **mordida de la máscara**.

### Por qué ningún test lo vio

Porque **ningún test corría el CLI con máscara**. Los del triple motivo llaman a
`triple_motive_rows` ellos mismos, así que la función estaba verde y **el llamador de
verdad no lo ejecutaba nadie**. Es la ceguera que describe la alcanzabilidad, un piso
más arriba: ahí el símbolo no tiene llamador; aquí lo tiene, y el llamador está roto.
El análisis de alcanzabilidad **no puede** verlo —hay una llamada escrita, y él no
ejecuta nada— y el golden tampoco, porque se genera **sin máscara**.

### Lo que enseña, y por qué no es un despiste

Es la **quinta** vez que aparece la misma familia: `triple_motive_rows`,
`intron_folding`, `store.save_*`, `page_run`, y ahora esto. Las cuatro anteriores eran
código sin llamador; ésta es un **llamador que no se ejecuta jamás**, que produce el
mismo resultado —trabajo escrito que no llega a ninguna salida— por una vía que ninguna
de las herramientas del proyecto cubría.

**Y hay una regla operativa que sale de aquí**: una rama del CLI que ningún test recorre
**de punta a punta** no está probada, por muchos tests que tengan sus piezas. La
contramedida no es otro análisis estático: es correr `main()` con esa combinación de
flags y leer lo que escribe. Eso está ahora en
`tests/test_mordida_de_la_mascara.py::TestSaleEnElInformeDEVERDAD`, que ejecuta el CLI
con `--rmsk` y comprueba **los dos** bloques que la rama emite.

### Un detalle que no se pasa por alto

El fallo era un `NameError` —ruidoso, inmediato, imposible de confundir con otra cosa—.
Sobrevivió igual, porque **nadie recorría ese camino**. Un fallo ruidoso en una rama que
nadie ejecuta es exactamente tan invisible como uno silencioso. Va como **principio
nº 17**, con su corolario: la alcanzabilidad ve símbolos sin llamador, el golden ve la
salida por defecto, y entre los dos hay un hueco donde vive el código llamado desde
caminos que nadie recorre.

### Y LA IRONÍA, que es lo que lo hace memorable

**La rama muerta era la del bloque que se cableó precisamente porque sólo existía si
alguien lo corría a mano.** `masking.triple_motive_rows` fue uno de los tres hallazgos
que dieron origen al análisis de alcanzabilidad: código con tests en verde y sin ningún
llamador, un análisis que se corría a mano aunque estuviera en la librería. Se le puso
llamador, se documentó como resuelto, y se dio por cerrado.

**Se cableó, y el cable no conducía.** El caso que motivó una herramienta entera del
proyecto volvió por la única puerta que esa herramienta no vigila — porque desde el día
que se cableó, la alcanzabilidad lo veía vivo: hay una llamada, escrita, apuntando a él.
Sólo que nadie la ejecutaba.

De ahí sale la contramedida que cubre el hueco: `tools/auditar_banderas.py`, el
inventario de qué banderas de los CLI recorre algún test **de punta a punta**.

---

## 32 — El CLI y la página daban paneles distintos, y llevaba así desde que se arregló la página

**Fecha:** 2026-08-27. **Estado:** cerrada. **Cómo apareció:** clasificando las 50
banderas VEREDICTO sin recorrido de punta a punta.

`tools/design.py` construía un `SelectionConfig(...)` pelado con
`apa_immune_quota=args.inmunes`, y **`--inmunes` valía `0` por defecto**. La decisión del
proyecto son **cuatro** (`DEFAULT_IMMUNE_QUOTA`), y vive en `selection.default_config()`,
que es lo que llama `presentation.page_run`.

Como **nadie pasa nunca esa bandera**, el CLI corría siempre con la cuota apagada:

| | panel |
|---|---|
| página | `3utr:` 10, 60, 143, **200**, 449, 553, 652, 735, 819, 1018 |
| CLI | `3utr:` 10, 60, 143, **359**, 449, 553, 652, 735, 819, 1018 |

`3utr:359` (+4,82) desplaza a `3utr:200` (+3,80) por asimetría, así que el panel del CLI
llevaba **tres inmunes en vez de cuatro** — y no lo decía nadie, porque los dos son del
tercio proximal y la cuota de tercios se cumple igual.

**Es literalmente el fallo que `default_config()` existe para cerrar**, arreglado en la
página y no en el CLI. La sexta divergencia entre los dos frontales, y la primera que es
el mismo fallo corregido sólo en un lado.

### Por qué nadie lo vio, y es lo que enseña

El golden pasaba **`--inmunes 4` tecleado a mano** en `regenerar_golden.py`. O sea que la
única corrida del CLI que alguien miraba llevaba la cuota puesta **desde fuera**, y por
eso coincidía con la página. El defecto del CLI no lo ejercitaba nadie.

Es el principio nº 17 otra vez, con una vuelta más: no es que la rama no se recorriera
—se recorría, en el golden—, es que **se recorría con la bandera puesta**, que es
justamente el camino que ningún usuario toma.

### Lo que se ha hecho

- `tools/design.py` monta su configuración con `config_de_seleccion(args)`, que parte de
  `default_config()`. La regresión compara los dos frontales y **falla si vuelven a
  separarse**.
- `--inmunes` y `--inmunes-antes` se **RETIRAN**. La cuota es una decisión del proyecto,
  no un parámetro de corrida; y la frontera **se deriva** del informe desde que un sitio
  medido la adelantó de `3utr:303` a `3utr:251` —una cifra tecleada no se entera, y no da
  ningún error—.
- El golden deja de pasar `--inmunes 4`: ahora sale solo. **Y no cambió ni una línea**,
  que es la comprobación de que el arreglo es el correcto.

### Y una decisión que hubo que tomar por el camino

Con la cuota aplicándose siempre, `select_from_report` **abortaba** en toda corrida cuya
secuencia no tuviera ninguna señal `APA_POSIBLE`: «no hay corte al que ser inmune». Sobre
el ratón no pasa nunca; sobre una entrada cualquiera, siempre.

La distinción que faltaba es la que `default_config` ya aplicaba al tamaño del panel
—«abortar por un defecto que quien llama no ha pedido sería peor que no tenerlo»—:

- cuota **PEDIDA** y sin corte → **ABORTA**. Se pidieron inmunes a algo que no existe.
- cuota **POR DEFECTO** y sin corte → **`NO_APLICA`, y se dice**. No hay pregunta de
  inmunidad que contestar. Pero la nota va en la selección, porque *«el panel no lleva
  reserva porque aquí no hay truncamiento que temer»* y *«no lleva reserva porque se
  renunció a ella»* son cosas distintas, y una cuota que desaparece en silencio es lo
  mismo que no haberla tenido nunca.

---

## 33 — `--usar-manifiesto` abortaba con un `KeyError` contra el manifiesto de verdad

**Fecha:** 2026-08-27. **Estado:** cerrada. **Cómo apareció:** escribiendo el golden
variante que fija «la forma normal de correr».

`manifest.ROLES` ganó el rol **`polyadb`** cuando la tabla de PolyA_DB se mudó del código
al gestor. `tools/design.py` tiene su propio diccionario, `DESTINOS`, que dice a qué
bandera va cada rol — y **no se enteró**. Resultado:

```
python3 tools/design.py --usar-manifiesto ...   →   KeyError: 'polyadb'
```

O sea que **«la forma normal de correr» estaba rota** desde entonces.

### Por qué ningún test lo vio, y es lo que enseña

`tests/test_usar_manifiesto.py` existe, pasa, y recorre la bandera de punta a punta. Pero
monta un manifiesto **PARCIAL** en un directorio temporal, con los roles que ese test
necesita. Ninguno incluía `polyadb`.

Así que la bandera figuraba como **cubierta** en el inventario —y lo estaba— sobre una
entrada que no se parece a la de producción. Es el principio nº 17 con la forma del
nº 18: el camino se recorre, pero **con una entrada que ningún usuario tiene**. De ahí
sale el corolario: al clasificar hay que mirar quién llama **y con qué entrada**.

### Lo que se ha hecho

- `DESTINOS["polyadb"] = None`, con el motivo: la tabla la resuelve `tile_utr` por su
  cuenta (`find_polyadb`), así que no hay bandera que rellenar. `None` es una **decisión
  declarada**, no un hueco.
- `tests/test_roles_del_manifiesto.py` cruza `manifest.ROLES` contra `DESTINOS` **en las
  dos direcciones**, y corre `main(["--usar-manifiesto"])` contra el manifiesto **del
  repositorio**, no contra uno de temporal.
- Y queda un golden que lee esa corrida entera:
  `raton_informe__con_usar_manifiesto__una_especie.txt`.

### Un límite que el aborto dejó a la vista, y no es un fallo

Con **dos** especies, `--usar-manifiesto` sigue abortando — y correctamente: el
manifiesto conecta `rmsk_mouse.out` **por su rol**, sin mirar qué se está diseñando, y
`RepeatMask.query_length` se niega a aplicar una máscara de 2191 nt a un transcrito de
2435. El guardia hace exactamente su trabajo. Lo que dice el aborto es que
**`--usar-manifiesto` con dos especies no es una combinación viable hoy**, y eso es
información que no estaba escrita en ninguna parte.

---

## 34 — La fila colapsada y ausente: un error rojo al abrir, y «Ver» tiraba la página

**Fecha:** 2026-08-29. **Estado:** cerrada. **Cómo apareció:** abriendo la primera de las
dos vías bloqueadas del inventario de estados — apuntar la página a un depósito de
prueba. Al pintar los nueve roles se vio, de paso, lo que hacía el depósito **real**.

`apa_medido.tsv` está en el estado **NO USADO**: su frente ya lo cierra
`polya_db_mouse.tsv`, así que no es trabajo pendiente y su fila sale **colapsada**. Pero
el fichero **no está**. La página elegía qué pintar así:

```python
if fila["acciones"]:
    _fila_presente(fila, directorio)
```

y `acciones` **nunca está vacía**: una fila ausente lleva `["subir"]`, que es verdadera.
Así que la fila salía con las cuatro acciones de un fichero presente. Al abrir la app, hoy,
en producción:

- un **recuadro rojo** —«`apa_medido.tsv` no está, así que no hay nada que descargar»—
  sobre una fila que la propia página acaba de describir como algo que **no hace falta
  conseguir**;
- y al pulsar «Ver», **la página entera se cae** con una excepción sin capturar.

### Lo que enseña

Tres cosas, y ninguna es «faltaba un test».

**Una: la página decidía.** Es la regla 6 — lo que decide vive en `presentation.py` — y
se saltó de la forma más barata que hay, una comprobación de verdad sobre una lista. No
había dónde escribir un test que lo cazara porque la decisión no existía como dato.
Ahora la fila **dice** si está: `"presente": fila["nombre"] in presentes`.

**Dos: el truco de la lista siempre verdadera.** `acciones` era `["ver", …]` o
`["subir"]`: dos cosas distintas, las dos verdaderas. Un `if` sobre eso no lee lo que
parece que lee. Hay un test que fija ese hecho —`acciones` nunca está vacía— para que
nadie vuelva a apoyarse en él.

**Tres, y es la que importa: el inventario acertó.** `data/estados.toml` decía que nadie
había pintado la página con los ficheros en el otro estado, y decía por qué no se podía.
Se abrió esa vía y el fallo apareció **en la primera corrida**. Diecinueve estados sin
pintar no eran diecinueve tareas: eran **dos causas**, y abrir una tiró nueve estados y
un fallo de producción con ella. Es el principio nº 15 cobrando: el informe obligaba
porque el trinquete lo contaba.

### La ironía

La fila estaba colapsada precisamente porque el panel **sabía** que ese fichero no hacía
falta —lo dice con su propio texto, «es una ALTERNATIVA que no hace falta conseguir»— y
dos líneas después le ofrecía descargarlo y se caía al intentarlo. El estado estaba bien
calculado en el núcleo y mal leído en la página.


---

## 35 — Donante→punto salía 405 en vez de 256: dos errores que sumaban uno plausible

**Fecha:** 2026-08-30. **Estado:** cerrada. **Cómo apareció:** leyendo la primera matriz
intrón × andamio. El número había sido 256 durante todo el proyecto y de pronto era 405,
sin que nadie hubiera tocado el intrón — y **405 − 256 = 149, la longitud del módulo**.

`donor_to_branch(elements, *, name, inserted)` tiene un contrato explícito:
`assembled = empty + inserted`. La celda de la matriz lo llamaba así:

```python
elementos = entrada.elements(modulo)          # elementos del intrón YA MONTADO
salto = donor_to_branch(elementos, name=intron, inserted=len(modulo))
```

**Dos errores, y ninguno de los dos por separado daba 405:**

1. los elementos eran los del intrón **montado**, cuyo campo `empty` vale ya la distancia
   montada (256), y la función le sumaba la inserción **otra vez**;
2. `inserted` no es la longitud del módulo: es **todo lo insertado**, el módulo **más los
   dos espaciadores** — 149 + 20 + 45 = **214**.

Con (1) y el 214 correcto habrían salido 470. Con (2) sobre el intrón vacío, 191. La
combinación dio 405, que es **el número con mejor pinta de los tres**.

### Lo que enseña

**Un valor plausible puede ser la suma de dos equivocaciones**, y entonces ninguna de las
dos se ve por separado: 470 y 191 habrían chirriado, 405 no. Lo que lo delató no fue una
comprobación sino que alguien recordara el número anterior y notara que la diferencia era
**exactamente la longitud de una pieza**. Una diferencia que coincide con una constante
del proyecto casi nunca es una coincidencia.

### La contramedida

No es «arreglarlo»: es que el número salga por **dos derivaciones independientes que
tienen que coincidir**. Ahora la matriz lo **mide** sobre la secuencia del intrón montado,
y el test lo cruza contra la ruta aritmética —`donor_to_branch(vacío, inserted=214)`— y
exige que den lo mismo. Una sola ruta no habría cazado esto, porque el fallo estaba en la
ruta.

Y queda fijado por escrito lo que se malentendió: **`inserted` incluye los espaciadores**.


---

## 36 — `NameError: _modal_blast`: la llamada a `main()` estaba a mitad del fichero

**Fecha:** 2026-08-30. **Estado:** cerrada. **Cómo apareció:** pulsando **Diseñar** en la
app desplegada. No lo encontró ningún test.

`ui/streamlit_app.py` tenía el bloque de entrada en la línea 1165:

```python
if __name__ == "__main__":
    main()
```

y **siete funciones definidas por debajo** — `_guardar_corrida`, `_guardar_seleccion`,
`_casete_de` y **los cuatro modales**. Streamlit ejecuta el fichero como `__main__`, así
que `main()` corre **en el sitio donde está esa línea**: cuando llega a
`_modal_blast(...)` en la línea 481, ese nombre todavía no existe.

La app arrancaba, pintaba los pasos 1 a 4 y sólo reventaba al llegar al único camino que
llama a un modal: **después de diseñar y con un candidato seleccionado**.

**Es antiguo.** Al menos quince commits con las mismas siete definiciones por debajo del
punto de entrada. No es una regresión reciente: es un defecto latente desde que se
añadieron los modales, y sólo dispara en el camino que ningún test podía recorrer.

### Por qué la suite no lo veía — y por qué eso no es la lección

`AppTest` no puede rellenar un `file_uploader`, así que la página nunca llega a DISEÑADO
y nunca ejecuta la línea 481. Es **exactamente** el estado que `data/estados.toml`
declaraba sin pintar, con su bloqueo escrito. **El inventario acertó**: dijo dónde estaba
el agujero y ahí estaba `_modal_blast`, con nombre y apellidos, desde el primer día.

**Pero pintar el estado no hacía falta.** Este fallo es **ESTÁTICO**: «hay un `def`
después del punto de entrada» se ve leyendo el fichero con `ast`, sin ejecutar nada, sin
Streamlit y sin ViennaRNA. Existía una comprobación **mucho más barata** que la que
estábamos esperando a poder hacer.

### La lección, que es sobre los bloqueos

**Un bloqueo declarado invita a dejar de buscar por otro lado.** El estado tenía una causa
escrita —`AppTest` no rellena un `file_uploader`— y esa causa era cierta; el trinquete lo
contaba, así que tampoco se leía como «pendiente» (principio nº 15 funcionando). Lo que
pasó es más fino: **con una explicación buena de por qué no se puede hacer LO CARO, nadie
preguntó si había algo BARATO que cazara el mismo fallo**. La explicación correcta ocupó
el sitio de la pregunta.

Así que a `bloqueado_por` le falta una pregunta al lado: *¿y hay alguna manera más barata
de cazar lo que vive detrás de este bloqueo?* Aquí la había, era un `ast.parse` de veinte
líneas, y habría cazado el fallo meses antes que la vía del `file_uploader`.

### Lo que se ha hecho

- La llamada a `main()` va **al final del módulo**, con el motivo escrito al lado.
- `tests/test_orden_del_modulo.py` lo impide: nada —función, clase o asignación— se define
  después del punto de entrada. Y de paso comprueba que ninguna llamada a un ayudante
  privado apunte a un nombre que no existe, que cazaría un `_modal_*` renombrado a medias.

---

## 37 — La columna `asimetria` era el número y era el estado, y el estado se comía el número

**Qué pasó.** La fila de un control (`controles.Control.row`) llevaba una columna
`asimetria` con el valor en kcal/mol —el que se compara contra el del original para saber
si el control se procesa igual— y luego un bucle escribía una columna por filtro con su
estado. Uno de los filtros se llama `asimetria`. La segunda escritura pisaba a la primera,
así que la fila salía con `PASS` donde tenía que ir el número.

**Ningún error.** El diccionario se dejó actualizar, la tabla salió con todas sus columnas
y el valor que decide si el control vale desapareció sin dejar rastro.

### Lo que lo hace anotable no es el fallo: es que la lección estaba escrita DOS LÍNEAS más arriba

`presentation.candidate_rows` tiene, desde el bloque 3, este comentario exacto:

> El VALOR de la asimetria y el ESTADO de su filtro son dos columnas: si comparten
> nombre, el diccionario fusionado pierde el numero.

Y por eso esa tabla usa `asimetria_kcal`. La tabla nueva repitió el fallo **en el mismo
eje y con el mismo par de magnitudes**. Es la misma forma que «la ironía de los dos
generadores» (principio nº 18): la regla estaba redactada, se aplicaba en un sitio, y no
existía nada que la aplicara en el siguiente.

### La diferencia entre un comentario y un mecanismo

Un comentario protege la tabla donde está escrito. Lo que faltaba es que la tabla
**se negara** a pisarse a sí misma. Ahora `row()` aborta si un filtro tiene el nombre de
una columna de métrica, con el motivo: *una columna que cambia de significado a mitad de
tabla es peor que una columna que falta*. Es la misma disciplina que
`informe_doc.Block.__post_init__` con las filas descuadradas, un nivel más abajo.

**Regla que queda:** cuando una lección se escribe como comentario en el sitio donde
apareció, hay que preguntarse si el sitio siguiente la va a heredar. Si la respuesta es
que no, el comentario es media contramedida.

---

## 38 — `_casete_de` indexaba un diccionario por `0`, y esperaba a que alguien subiera el casete

**Qué pasó.** La página tenía este ayudante:

```python
def _casete_de(tiling):
    base = getattr(tiling, "transgene_db", None)
    registros = getattr(base, "records", None) if base is not None else None
    return registros[0].sequence if registros else None
```

`specificity.load_database` devuelve `records: dict[str, str]`. Así que `registros[0]` es
un `KeyError: 0` y `.sequence` sobre una cadena es otro error detrás. **Dos fallos en una
línea de cuatro.**

**Por qué nadie se enteró.** `aav_casete.fa` no se ha conectado nunca desde la página, así
que `transgene_db` siempre ha sido `None` y el `if registros else None` de delante tapaba
la rama entera. El día que alguien subiera el casete, el CUARTO MODAL —el de empalme, que
recibe justo esto como contexto— moriría al abrirse.

Es la errata nº 31 otra vez con otra ropa: **una combinación que ningún test recorre de
punta a punta no está probada**, por muchos tests que tengan sus piezas. Allí era
`--rmsk`; aquí es «la página con el casete conectado».

### Lo que se ha hecho

- La función se va a `presentation.cassette_sequence`, porque **decidir cuál registro es
  el casete es decidir** (regla 6) y en la página no tenía test posible.
- Con **más de un registro ABORTA** en vez de elegir por orden de aparición: el contexto
  de empalme tiene que salir de UNA molécula, y concatenar dos inventa una juntura que no
  existe en ninguna. Es el mismo criterio por el que los bloques conservados se miran
  CONTENIDOS y no solapando.
- Tres tests con el casete de verdad: la secuencia sale, sin casete devuelve `None` sin
  reventar, y con dos registros aborta.

---

## 39 — El texto explicaba lo que se EVITÓ y se leía como lo que pasa

**Qué pasó.** El panel de «Guardados» decía:

> La biblioteca vive en el volumen y no en la imagen. **Dentro de la imagen, todo lo
> guardado desaparecería en el siguiente redespliegue** y el único síntoma sería una
> biblioteca vacía sin ninguna explicación.

Las dos frases son **ciertas**. La primera dice dónde vive; la segunda explica el
contrafactual — qué habría pasado en el sitio donde NO está. Leídas en pantalla, la
segunda es la que se queda, porque es la concreta y la que habla de consecuencias.

El responsable del proyecto lo leyó así y preguntó por qué no se podía hacer que lo
subido aguantara el despliegue. **Ya aguantaba.** La misma frase estaba en
`trabajo.WHY_A_WORKING_DIR`, para los ficheros de referencia.

### Es el principio nº 11 con los papeles cambiados

Allí la prosa **se había quedado atrás** y contradecía al código. Aquí la prosa es
correcta **como explicación** y falsa **como descripción**, que es un fallo distinto y
más difícil de ver: no hay nada que corregir en ella, hay que cambiar de qué habla.

**Y el mecanismo que la deja pasar es el mismo.** La regla operativa del principio nº 11
—«la frase la emite el generador, o un test la contrasta contra lo que el código
emite»— estaba aplicada a los amplicones y no a esto: eran **cadenas fijas**, y una
cadena fija no puede decir lo que pasa cuando lo que pasa depende del estado.

### Lo que se ha hecho

- **La frase se DERIVA** (`presentation.library_note(env)`): con el directorio de trabajo
  declarado dice «Lo guardado aquí SOBREVIVE a los redespliegues» y da la ruta; sin
  declarar dice «Estás en LOCAL» y qué significa. Cuál de las dos es verdad lo sabe
  `trabajo.is_declared()`, así que lo decide él.
- `WHY_A_WORKING_DIR` se reescribe igual: **afirma primero** —sólo se pinta cuando el
  directorio está declarado— y deja la razón detrás, en pasado.
- **Y se MIDIÓ antes de contestar**, porque el registro decía «COMPROBADO que lo subido
  aguanta un redespliegue» y esa medida era sobre los **ficheros de referencia**, que
  están en la raíz del directorio. La biblioteca vive en un **subdirectorio** y nada
  comprobaba que la siembra no lo tocara. Se simuló el redespliegue: 27 copiados la
  primera vez, **0 copiados y 27 respetados** la segunda, y el `.gb` guardado sigue ahí
  byte a byte. Ahora lo fija `TestLaBibliotecaSOBREVIVEalRedespliegue`, con su control
  adversario —que el directorio esté de verdad fuera del paquete—, porque si viviera
  dentro los otros dos tests pasarían igual.

## 40 — La orden llevaba `-entrez_query` y la ficha mandaba correrla en LOCAL

**Qué pasó.** El modal de especificidad emitía siempre esta orden:

```
blastn -task blastn-short -db refseq_rna -word_size 7 -evalue 1000 -dust no \
       -outfmt 6 -entrez_query "txid10090[ORGN]" -query consulta.fasta
```

Y dos pantallas más allá, el paso 4 de `data/obtencion/especificidad.toml` decía:
«Ejecútalo contra una base **LOCAL**… Sólo una base local con md5 cierra el frente.»

**`-entrez_query` es un filtro del SERVICIO de Entrez, no de `blastn`.** Es una consulta
al índice de NCBI, así que sólo tiene a quién preguntársela con `-remote`; contra una
base local no hay Entrez al que consultar. BLAST+ lo declara en su propia ayuda
(`-entrez_query … * Requires: remote`).

### Las dos instrucciones se contradecían, y la contradicción se cobraba tarde

Quien siguiera la ficha se llevaba **varios GB de base** primero y descubría el conflicto
**después**, al lanzar la única orden que la app le había dado. El coste no es el error:
es *cuándo* llega.

### Y no depende de que `blastn` aborte

Este entorno no tiene BLAST+ instalado, así que **no se ha ejecutado la orden para
verlo** — y da igual, porque las dos salidas posibles son malas y una es peor:

- si **aborta**, se pierde la descarga y hay que averiguar por qué;
- si lo **ignorase**, la corrida saldría contra `refseq_rna` **entera** con el veredicto
  presentándose como restringido a la especie. Eso es exactamente el `.out` sin resumen:
  un resultado con la forma correcta obtenido contra otra cosa.

Lo que hace falso el par no es el comportamiento del binario: es que **la orden decía
filtrar por organismo y el destino que la ficha manda no puede filtrar así**.

### Lo que se ha hecho

- **La orden sale coherente con su destino** (`BlastParams.command`): `-entrez_query`
  entra **sólo** cuando `remote=True`, junto a `-remote`. Lo demás no se toca.
- **El organismo se sigue exigiendo SIEMPRE**, también en local: es la **identidad** de la
  corrida y viaja con ella al almacén (`describe()`). Lo exigía de rebote
  `entrez_expression()`, así que al dejar de llamarse en local el guardia se habría caído
  con el filtro: ahora se llama explícitamente al principio de `command()`, con el motivo
  escrito al lado.
- **Adónde se fue el filtro se DICE, no se calla** (`BlastParams.organism_note`, emitido
  por `presentation.blast_warnings` como aviso **que no bloquea**). En local la
  restricción pasa a ser una propiedad de la **BASE**: o se construye una sólo con
  transcritos de la especie (`makeblastdb`), o se corre contra la completa **leyendo que
  los aciertos de otros organismos están dentro del resultado**. Los dos son defendibles;
  creer que la orden filtra cuando no filtra, no.
- **El paso 4 de la ficha era una línea para una instalación y una descarga de varios GB.**
  Ahora son cuatro pasos: instalar BLAST+, bajar la base **ya formateada**
  (`update_blastdb.pl --decompress refseq_rna`, que llega en volúmenes numerados que son
  una sola base), **comprobar que se lee antes de lanzar nada**
  (`blastdbcmd -db refseq_rna -info`, que además da dos de los tres metadatos que hay que
  anotar) y ejecutar desde el directorio de la base o con `-db` completo.

### La regla que deja

**Una orden que se copia y una instrucción que se lee son la misma instrucción**, y nadie
las pone una al lado de otra: la orden la genera el código y el paso lo escribe una
persona. Es la errata nº 28 —ficha, listado y nombres desincronizados— sobre la
superficie que el usuario ejecuta en vez de la que prepara. `TestLaOrdenTIENEqueCORRERdondeSeDICE`
lo fija por los dos lados: que la orden local no lleve `-entrez_query` ni `-remote`, que
la remota lleve los dos, y que la nota del organismo llegue **a la pantalla** —no basta
con que exista— sin bloquear.

## 41 — La ficha mandaba al FTP del NCBI y punto: 80 GB para consultar veinte guías

**Qué pasó.** El frente de especificidad necesita una base de transcritos, y la ficha
escribía **una sola vía**: el FTP de BLAST del NCBI. Se siguió, y la descarga real fueron
**80 GB** — el RefSeq RNA completo, de **todos los organismos**, para consultar veinte
guías de **una**.

**La vía barata existía y estaba a la vista.** El mismo Table Browser de UCSC del que ya
sale `transcriptoma_3utr.fa` da los transcritos de la especie del diseño en **decenas de
MB**, y sale de la **misma sesión**: allí se pide la región «3' UTR Exons» y aquí el
transcrito entero. Dos descargas, una navegación.

### No es que la vía cara estuviera mal: es que era la ÚNICA escrita

La del NCBI sigue siendo legítima y por eso **no se borra**: es la exhaustiva, y la única
que trae los transcritos **predichos** (`XM_`/`XR_`). Lo que estaba mal es que la ficha no
ofrecía elegir, y una ficha que sólo escribe un camino **no está recomendando: está
decidiendo**, y decide sin decir lo que cuesta.

**Es la errata nº 30 con otro disfraz.** Allí una fila decía FALTA de un frente que ya
cerraba otro fichero; aquí la ficha manda conseguir lo caro cuando lo barato ya vale.
Las dos veces el usuario hace trabajo que no hacía falta y **nada da ningún error**.

### Y faltaba un paso sin el cual ninguna de las dos vías funciona: `makeblastdb`

**Un FASTA no es una base de BLAST.** No aparecía en ninguna parte de la ficha, así que
por la vía de UCSC —que entrega un FASTA— la orden que da la app no puede correr, y eso
se descubre **después** de la descarga. Por la del NCBI la base viene preformateada, así
que el paso parecía innecesario… y no lo es, por dos razones que se suman:

- **`-entrez_query` no funciona en local** (errata nº 40), así que sin filtrar, la corrida
  no queda restringida a la especie por ningún sitio;
- **la base preformateada no deja ningún FASTA que registrar**, y el manifiesto se
  quedaría sin el md5 que es toda la procedencia del veredicto.

Así que las dos vías acaban en `blastdbcmd`/`makeblastdb` y **en el mismo artefacto
declarable** —`refseq_rna.fa`—, que es lo que hace que el md5 signifique lo mismo por las
dos. Hay test de esa convergencia.

### Un cero que no significa lo que parece

«RefSeq Curated» **no trae los predichos**, así que por la vía A **cero aciertos contra
`XM_`/`XR_` no es «no hay off-targets contra predichos»**: es que no había ninguno en la
base contra el que acertar. Es el **«Alu 0 %» obtenido sin buscar Alu**, y va como aviso
con la consecuencia escrita, no sólo con el hecho.

### Lo que se ha hecho

- **Dos vías declaradas** en `data/obtencion/especificidad.toml`, cada paso etiquetado
  `[VÍA A · UCSC]` / `[VÍA B · NCBI]`, con lo que pesa cada una **en la propia ficha**
  —los 80 GB incluidos, porque el número medido convence y «decenas de GB» se lee en
  diagonal—. La URL de cabecera pasa a ser la de UCSC: la que se lee primero es la que se
  sigue.
- **`makeblastdb` en LAS DOS**, y **en los pasos, no en un aviso**: un aviso se lee en
  diagonal, un paso se ejecuta. Hay test de las dos mitades.
- **`blastdbcmd -db <base> -info` antes de lanzar nada**, para que un fallo salga antes de
  la corrida y no después de horas.
- **El `-db` cambiado se declara en el modal**, y que se marque como ajuste modificado es
  **correcto**: la base no es la estándar y el veredicto no puede parecer que sí.

### Y una nota de método que no se calla

**Ninguno de esos comandos se ha podido ejecutar desde este proyecto**: aquí no hay
BLAST+ instalado ni red saliente —las dos URL dan 403 en el CONNECT del proxy, que es una
denegación de política y no una respuesta del servicio—. Va **escrito en la ficha**: son
la ruta, no una corrida comprobada. Por eso el paso de comprobación no se apoya en que
los menús se sigan llamando igual, sino en el **resultado**: con «RefSeq Curated» las
cabeceras empiezan por `NM_`/`NR_` y no puede haber ni un `XM_`.

### Y de paso, la errata nº 40 un piso más abajo

El comando de filtrado se escribió primero como `-taxids <el número de {taxid}, sin el
prefijo txid>`: un comando que la ficha da **para copiar** y que hay que **editar antes de
pegarlo**. `{taxid_numero}` se **deriva** del taxid declarado (principio nº 13) y sale
`-taxids 10090`. Al derivarlo aparecieron **dos avisos idénticos** para una especie sin
taxid —dos marcadores del mismo dato son un solo agujero—, y ahora se emite uno.

## 42 — El proyecto se perdía en cada rerun, y el FASTA emitía identificadores inservibles

Dos fallos en el mismo camino, los dos detrás de una descarga de decenas de GB y una
corrida de BLAST de horas, y **ninguno de los dos daba un error**.

### 1. El formulario de guardar era imposible de completar

Reproducción exacta: abrir proyecto → subir el `.tsv` → rellenar md5, base y versión →
aparecen «Fecha», «Quién la corrió» y el botón → **escribir en «Fecha»** → los dos campos
y el botón desaparecen y vuelve «Sin proyecto abierto esta corrida NO se guarda».

La causa es de una línea: `_panel_proyecto` creaba el proyecto **dentro de un
`if st.sidebar.button(...)`**, y un botón de Streamlit vale `True` **un solo rerun**. Al
siguiente repintado el botón ya no está pulsado, el panel devuelve `None`, y con `None`
llega `_guardar_corrida`, que pinta el aviso gris.

**Y en Streamlit cada tecla que el usuario escribe ES un rerun.** O sea: para rellenar el
formulario hay que escribir, y escribir lo borraba. No es un caso raro — es el único
camino que hay.

**Afecta a los CUATRO modales**, y no por coincidencia: `_guardar_corrida` es la misma
función para los cuatro y recibe el mismo `proyecto` del mismo panel. Un solo fallo, cuatro
síntomas.

**El arreglo.** La decisión sale de la página (regla 6): `presentation.project_target`
recibe el estado de los widgets y dice qué hacer —`ninguna` / `crear` / `abrir`— y **qué
recordar**. La página guarda el **slug** en `session_state` y vuelve a abrir el proyecto
en cada rerun.

**Se recuerda el slug y no el almacén**, y eso no es un detalle de implementación: el md5
de la secuencia y la cadena del log **se comprueban al abrir**, así que un `ProjectStore`
guardado en `session_state` se quedaría con la comprobación del primer repintado para
siempre. Es el principio nº 14 —haber comprobado una vez no es seguir comprobando— en la
persistencia de la interfaz.

### 2. Sin proyecto, el modal aceptaba el fichero igualmente

Y avisaba **en gris** de que no se iba a guardar nada. Detrás de ese fichero hay una
descarga y una corrida que no se repiten gratis: un sitio donde se puede soltar algo que
no se guarda no informa, **es una trampa**. Es el mismo criterio con el que se quitó la
casilla «Usar los de `data/reference/`», cuyo único efecto posible al desmarcarla era
dejarlo todo en `NOT_RUN`.

Ahora `presentation.upload_allowed` decide y **los tres modales que aceptan un fichero**
—BLAST, SpliceAI y off-targets— no pintan el `file_uploader` sin proyecto: sale un error
rojo que dice dónde se abre.

### 3. `>Mus musculus_pos959_guia`: veinte consultas que llegan como una

El FASTA de consulta construía el identificador con el nombre que se **pinta**
(`Mus musculus`) en vez del **slug**. **BLAST corta `qseqid` en el primer espacio**, así
que las veinte consultas salen en el `-outfmt 6` como `Mus`, todas iguales.

**El fichero de resultados no es recuperable, y no por culpa de la interfaz**: no contiene
de qué consulta viene cada fila. Ni la app ni un CLI ni nadie puede repartir esas filas
entre los candidatos, porque la información no está. **Y no vale reconstruirlo por el
orden**: `-outfmt 6` agrupa por consulta en el orden de entrada, pero **una consulta sin
ningún hit no emite ninguna fila**, así que no se puede saber cuál falta. Eso es
reconstruir un dato ausente, que es la regla 1 por otra puerta.

Lo caro —la base— está intacto; lo que hay que repetir es el `blastn`.

**Dos arreglos, no uno.** `presentation.query_name` usa el slug (y de paso **normaliza**:
`mouse`, `raton` y `Mus musculus` son la misma especie, así que un nombre por alias haría
incomparables dos corridas de lo mismo). Y el **mecanismo** va en
`QueryFasta.from_records`, que ya abortaba con nombres repetidos y ahora aborta con
cualquier blanco: es la lección de la errata nº 37 —un comentario protege su tabla, un
mecanismo protege la siguiente— aplicada donde el guardia hermano ya vivía.

### Lo que enseña sobre el INVENTARIO DE ESTADOS, que es lo que generaliza

El responsable preguntó si este estado —diseñado, con selección, proyecto abierto,
fichero subido, campo de texto modificado— estaba en `data/estados.toml` y si se había
pintado alguna vez. **No estaba, y no podía estar**: de sus cinco componentes, el
inventario sólo modelaba dos.

- **No había eje de PROYECTO.** El estado del que cuelga si un modal puede guardar no
  aparecía en ningún eje.
- **Y no había eje de RERUN.** Los 29 estados describían **todos** la página *recién
  pintada*. Ninguno decía nada de volver a pintarla — que en Streamlit no es un caso raro
  sino **el normal**, uno por tecla.

Los dos ejes entran ahora (33 estados). `rerun:SEGUNDA` **se pinta hoy**
(`tests/test_segundo_rerun.py`: pinta, toca un widget, vuelve a pintar) y
`proyecto:ABIERTO` queda bloqueado **por la misma causa que los otros diez** —`AppTest` no
rellena un `file_uploader`, así que la página no llega a DISEÑADO—, declarada como tal y
no como un bloqueo nuevo.

**El trinquete SUBE de 10 a 11, y eso es correcto.** No es que se haya perdido cobertura:
es que **el espacio era demasiado pequeño**, y un inventario que no puede expresar un
estado no puede echarlo de menos. Es la contrapartida del principio nº 15: una lista que
sólo baja es útil mientras la lista sea la lista completa.

## 43 — La imagen no tenía ViennaRNA, así que la app degradó a la regla que ya había descartado

**Qué pasó.** `nixpacks.toml` instalaba Streamlit y el stack de PDF. **ViennaRNA no.** El
núcleo está escrito para eso —`check_fold` sale `NOT_RUN` y nunca `PASS`, y el diseño
sigue— y hasta ahí todo correcto: es una limitación declarada, con la que se convive.

**Lo que no degrada igual es la regla de la hebra PASAJERA.** `passenger_from_guide`
elige la base de la posición 1 **plegando** el 97-mero y comparándolo con la estructura de
SGEP. Sin plegado no hay criterio que aplicar, así que cae a la **tabla por terminación**
— y esa tabla es **la primera errata de este proyecto**: le falta el apareamiento
tambaleante `G:U`, así que con una guía acabada en G elige una base que deja un bulge de
2 nt en vez de 1. Está descartada **por escrito** y sustituida por el criterio estructural.

### Por qué no es «un `NOT_RUN` más»

Esa pasajera **va dentro del módulo de 149 nt**, que es lo que se manda a sintetizar. La
app desplegada emitía el módulo y la hoja de pedido con `structural_check = NOT_RUN` al
lado, más la advertencia de los contextos de SGEP — **que habla de otra cosa**. O sea:

> **Un `NOT_RUN` que produce ADN sintetizable no es un `NOT_RUN`: es un `PASS` con letra
> pequeña.**

Un gBlock pedido desde la app desplegada habría llevado la base equivocada, y el único
síntoma habría sido una horquilla que procesa peor — indistinguible de un mal candidato.

### Cómo se descubrió, y eso también cuenta

No lo cazó ningún test: lo cazó una **discrepancia de md5**. Al reconstruir el FASTA de
consulta del usuario salía `f4d304d7…` y el suyo era `148f946e…`, con los **mismos 1038
bytes** y las mismas cabeceras. En vez de dar una cifra plausible se buscó la causa, y
resultó ser que **este entorno tiene ViennaRNA y la imagen no**. Simulando la imagen
—bloqueando el `import RNA`— el md5 salió **exacto**. Los bytes coincidían porque la
pasajera cambia de base, no de longitud: la diferencia era invisible por tamaño.

### Lo que se ha hecho, y son tres cosas distintas

1. **La causa raíz**: la imagen instala ViennaRNA, con la comprobación de `import` **en el
   build**, igual que Streamlit y por la misma razón. Aquí pesa más: si no entra, la app
   **no falla a gritos** — sigue funcionando y deja de poder emitir oligos.
2. **El guardia, que se queda aunque esté instalado**: `presentation.check_can_emit_dna()`
   aborta la emisión del módulo y de la hoja de pedido sin plegado. Acotado a la
   **emisión** a propósito: el núcleo y los CLI tienen que seguir corriendo sin ViennaRNA
   —está en `docs/dependencias-autorizadas.md`— y abortar el pipeline entero dejaría la
   app sin hacer lo único que hoy hace bien. Se prohíbe lo que no se puede deshacer.
3. **Visible, no deducible**: `folding_capability()` lo dice en la **cabecera**. Es una
   **capacidad ausente del entorno**, no un fichero que falte — y confundirlos manda al
   usuario a buscar un fichero que no existe.

### La regla que deja

**Un entorno sin una dependencia no falla: DEGRADA** — y aquí degradó, en silencio, a la
regla que el proyecto ya había descartado por escrito. La familia es la del principio
nº 14 (haber comprobado una vez no es seguir comprobando) con el eje cambiado: aquí la
comprobación **sí corre**, y lo que cambia debajo es de qué se alimenta.

Lo operativo, y aplica a las dos dependencias opcionales y a las que vengan: **no basta
con que la ausencia esté declarada. Hay que preguntarse a QUÉ cae cada cosa cuando falta,
y si alguna cae a algo que ya se descartó, la ausencia tiene que IMPEDIR — no anotar.**
Comprobar que la dependencia está es la mitad; la otra mitad es comprobar que su ausencia
bloquea lo que sin ella no se puede hacer, y eso es lo que fija
`tests/test_sin_plegado_no_hay_ADN.py`, simulando la imagen de producción.

## 44 — Cinco copias de la misma clave, y dos tests que preguntaban por la suya

**Qué pasó.** Investigando por qué una corrida de BLAST guardada no cambiaba ningún
veredicto —cuya causa real es otra: **nadie consulta el almacén en el camino del
veredicto**— apareció un fallo distinto y latente. El identificador de una consulta se
construía **a mano en cinco sitios**:

| dónde | para qué |
|---|---|
| `presentation.query_name` | el FASTA que se descarga |
| `dossier.build_dossier` | la búsqueda en el almacén de BLAST |
| `dossier` (×2) | las búsquedas por hebra, seed y off-target |
| `seed_scan.run_scan` | las consultas que **emite** el scan |
| `offtarget` | lo mismo para la carga de off-targets |
| `presentation.seed_preview_rows` | los ids que el usuario **marca** |

Al pasar el FASTA al slug (errata nº 42) **las demás se quedaron atrás**: una decía
`Mus musculus_pos959_guia` y otra `mouse_pos959_guia`.

### Por qué es más valioso que el bug que se estaba buscando

**Habría producido el mismo síntoma que el problema real.** Se habría cableado el
almacén, `verdict_for` no habría encontrado nada, la tabla habría seguido diciendo
`NOT_RUN` — y la conclusión natural habría sido *«el cableado no funciona»*, buscando en
el sitio equivocado con la evidencia apuntando ahí. Un fallo que imita al que estás
arreglando es peor que uno ruidoso: no se descubre, se **confunde**.

### Y lo que lo escondía

> **Dos tests transcribían el formato — preguntaban por la clave que ellos mismos habían
> escrito.**

`test_seed_store` y `test_ficha_candidato` construían `"raton_pos10_guia"` a mano, metían
la corrida en el almacén con esa clave y luego la buscaban con esa misma clave. Verde
siempre, porque el test era **su propio universo**: nunca tocaba al productor real. Es la
tercera copia del mismo dato haciendo de aval de las otras dos, igual que en la errata
nº 27 —la constante, la tabla y el ancla, tres orígenes y ninguno correcto— y en la nº 28,
donde eran tres capas encima del mismo dato.

### Lo que se ha hecho

Las seis derivan de `query_name`. **Y los fixtures también**: `tests/test_seed_store.py`
llama a un ayudante `CLAVE(inicio, hebra)` que la deriva, así que si el productor cambia
de formato el test se entera en vez de acompañarlo. Es el principio nº 13 —una constante
que cita algo se deriva, nunca se transcribe— **sobre una CLAVE en vez de sobre un dato**,
y el corolario que añade: *un fixture que transcribe un formato es una copia más, y es la
que hace parecer que todo cuadra.*

## 45 — DECISIÓN: qué corrida manda cuando hay dos del mismo frente

No es una errata: es una **decisión tomada antes de que el fallo ocurriera**, y se anota
aquí porque el registro sirve para eso — el caso lo planteó el responsable del proyecto al
leer el criterio de aceptación, viendo que iba a probar exactamente la secuencia que lo
rompía.

**El caso.** Se sube una corrida buena y después, por probar, una marcada `-remote`.
«Nada se sobrescribe» y la ficha enseñaba **la última**, así que una corrida mala posterior
habría degradado un frente ya cerrado.

### Las tres salidas obvias, y por qué ninguna vale

- **«Manda la última»** — una exploración de treinta segundos tumba un veredicto ganado con
  una base local de decenas de GB.
- **«Manda la mejor»** — esconde una `FAIL` posterior, que es justo la que hay que ver: si
  se repite contra una base mejor y ahora falla, **el candidato falla**. Sería un `PASS`
  con letra pequeña, que es lo que este proyecto acaba de escribir que no hace (errata
  nº 43).
- **«Se borra la anterior»** — rompe el log append-only, que es la única memoria de por qué
  se volvió a correr.

### La regla, y de dónde sale

Sale de una distinción que ya estaba escrita: **`NO_CIERRA` no es un veredicto peor, es
NINGÚN veredicto.** Una corrida que no puede cerrar el frente no es evidencia sobre ese
candidato — no lo empeora ni lo mejora, **no habla de él**. Así que:

1. manda **la última corrida que PUEDE dar veredicto**, aunque después haya exploraciones;
2. entre las que pueden, **la última siempre**, sea mejor o peor: repetir contra una base
   mejor y sacar `FAIL` tiene que degradar;
3. si **ninguna** puede, se enseña la última con su `NO_CIERRA` y su motivo;
4. y si hay exploraciones **posteriores** a la que manda, **se dicen** — callarlas dejaría
   a quien acaba de subir la última creyendo que es la que cuenta.

`BlastStore.deciding_run` la implementa y **no borra nada**: decide cuál manda, no cuál se
guarda. Las dos siguen en el historial, que es donde se ve que alguien volvió a correr.

## 46 — «Predichos: sí» en una corrida que no puede filtrarlos

**Qué pasó.** `include_predicted` vale `True` por defecto y **sólo actúa dentro de
`-entrez_query`**. Desde la errata nº 40 ese filtro va **únicamente con `-remote`**, así
que en una corrida local el ajuste **no aparece en la orden**: no filtra nada, ni a favor
ni en contra. Y aun así viajaba con el resultado al almacén como «predichos: sí».

**El riesgo, planteado por el responsable del proyecto**: dos corridas —una remota y otra
local— registradas las dos igual, y comparadas **dentro de un año** como si fueran
equivalentes. Es un `PASS` falso de la misma familia que un `provided=True` con secuencia
vacía: el campo afirma algo que la corrida no puede cumplir.

### Se eligió la opción fuerte, y por qué no bastaba una nota

Una nota derivada —del estilo de `organism_note`— habría dicho la verdad **al lado** del
campo, dejando el campo mintiendo. Y aquí el campo **es** el registro: es lo que queda en
el log y lo que alguien leerá dentro de un año sin la nota delante. En local sale
**`NOT_RUN` con el motivo**, y el motivo dice que **no es un fichero que falte** sino que
el ajuste **no aplica**: lo que decide si hay modelos predichos en el resultado es **la
base**.

No bloquea la corrida. Una base curada de una especie es perfectamente válida — lo que no
lo es es registrarla como si hubiera comprobado los predichos.

### Y el veredicto declara el universo

`blast.UNIVERSE_NOTE`, pegado a cada veredicto de especificidad:

> El universo de esta comprobación es la BASE que se declara arriba, y nada más. Si esa
> base no incluye modelos predichos (`XM_`/`XR_`), cero aciertos contra ellos NO significa
> que no los haya: significa que no estaban.

Es lo que hace **interpretable un cero**, y cierra el caso que abrió la errata nº 41: la
vía de UCSC entrega un catálogo curado, y sin esta frase su cero se lee como «no hay
off-targets contra predichos» — el **«Alu 0 %» por quinta vez**.

### Nota de método sobre esta misma entrada

Esta errata **se escribió dos veces**: la primera se perdió porque un `cd` falló en mitad
de una cadena de comandos y la escritura se saltó, mientras el commit y el merge siguieron
adelante. El código entró, el registro no. Es la misma familia que todo lo demás de este
documento —algo que se da por hecho y no se comprueba— y se anota aquí porque el registro
sirve para eso también.

## 47 — La comparación de md5 no estaba congelada: NO PODÍA DARSE NUNCA

**Reportado por el responsable del proyecto (2026-09-02)**, con la secuencia entera y el
diagnóstico apuntando al sitio correcto: subió el `.tsv` sin `refseq_rna.fa` en el
depósito, la corrida se guardó y salió `NOT_RUN` con el motivo «no hay md5 de hoy con el
que comparar»; después subió `refseq_rna.fa`, cuyo md5 (`ade3c2e4…`) es **el mismo que la
corrida registró**; y tras refrescar, nada cambió.

Su lectura fue que el resultado de la comparación se quedaba **congelado** y que debía
recalcularse en cada consulta, «exactamente la lógica de OBSOLETO».

**No estaba congelado.** `insumos.obsoleta` se recalcula en cada consulta desde el primer
día: recibe los md5 de hoy, leídos del directorio en esa misma llamada
(`presentation.reference_md5s`), y no guarda nada. Lo que pasaba es peor:

> **la comparación preguntaba por una clave que no existe en el diccionario, y no podía
> existir.**

`insumos.CONSUMIDOS` nombraba el insumo de BLAST **en prosa** —`"base de datos de
BLAST"`— y `actuales` viene indexado por el **nombre del fichero en el depósito**, que es
`refseq_rna.fa`. Así que `actuales.get("base de datos de BLAST")` devolvía `None` con el
fichero delante, con el md5 correcto y con el usuario mirando. **Toda** corrida de BLAST
salía «no se ha podido comprobar», siempre, desde que existe la tabla.

### Los otros dos acertaban por casualidad, y sólo en ratón

`corrida_seed` y `corrida_offtarget` escribían `mature.fa` y `transcriptoma_3utr.fa`, que
**sí** son nombres de fichero. Pero son los nombres **murinos**: `species.required_files`
sufija por especie, así que en humano el catálogo se llama `transcriptoma_3utr_human.fa` y
esas dos entradas fallaban igual. No era un nombre mal escrito de tres: era **el mismo
fallo tres veces**, tapado dos de ellas por que la especie de trabajo es el ratón.

### Lo que lo dejó pasar es la errata nº 44, un piso más abajo

Los tests de `obsoleta` **construían `actuales` con la clave que ellos mismos habían
escrito**:

```python
insumos.obsoleta("corrida_blast", PAYLOAD, actuales={"base de datos de BLAST": "d" * 32})
```

Un test así pregunta por su propia respuesta. Coincide siempre, no puede discrepar del
depósito, y por eso once tests en verde convivían con una comparación que no se daba
nunca. Es literalmente la frase que quedó escrita en la errata nº 44 —*dos tests
transcribían el formato; preguntaban por la clave que ellos mismos habían escrito*—
aplicada a otra clave, tres días después.

### El arreglo es derivar, no corregir el nombre

Cambiar `"base de datos de BLAST"` por `"refseq_rna.fa"` habría arreglado **este** caso y
dejado el mecanismo entero en pie: seguiría habiendo dos sitios escribiendo el nombre del
mismo fichero, y seguirían envejeciendo por separado (principio nº 13, y la lección de la
errata nº 28). Así que el insumo declara su **ROL** —`refseq`, `mirbase`,
`transcriptoma`— y el nombre lo pone `insumos.fichero_de` contra `species.required_files`,
que es **la única fuente de los nombres del depósito**. Un rol que el gestor no declare
**aborta**, con el motivo escrito: un nombre inventado no da un error, deja la corrida en
«no se ha podido comprobar» para siempre.

Con eso la discrepancia no es que esté arreglada: **es que no se puede escribir**.

### Y el aviso que el responsable pidió DOS veces, ahora sí

«El modal debería avisar antes de subir, no después de guardar.»
`presentation.blast_readiness` sale **arriba del modal**, antes del comando y antes del
`file_uploader`, y dice las **tres** cosas medidas, no la que se suponía:

- la corrida **sí** sirve — su celda de la tabla pasa a tener veredicto;
- el **frente** se queda abierto, porque eso lo cierra el filtro de la ventana contra el
  catálogo cargado, no la corrida;
- y la corrida **no se podrá revalidar** mientras el fichero no esté.

La primera cláusula es la que hace que el aviso no sea un diagnóstico equivocado: la
premisa original —«cualquier corrida de BLAST va a salir `NOT_RUN` haga lo que haga el
usuario»— **era cierta cuando se planteó y dejó de serlo** en cuanto la tabla empezó a
leer los almacenes. Se midió antes de escribirla. Un aviso que afirma una causa sin
comprobarla es el principio nº 3, y este proyecto lleva cinco.

### La regresión

`tests/test_la_corrida_se_reevalua.py` reproduce la secuencia del usuario de punta a
punta —guardar la corrida, depósito vacío, depositar el fichero, quitarlo— y exige que el
estado cambie en cada paso, con la mitad adversaria (si el fichero cambia, `OBSOLETO`).
Y cierra lo que lo escondía: ningún test de esta familia puede volver a escribir a mano la
clave de `actuales`.

## 48 — El `run_id` no admitía dos corridas el mismo día, y repetir es lo normal

**Reportado tres veces en un solo día (2026-09-02)**, la tercera con la frase que lo
resume: *«no te lo he pedido dos veces por gusto»*. `Mus musculus-blast-02/09/2026` ya
existía y la subida abortaba.

El id era `especie + tipo + fecha`. Repetir una corrida el mismo día **es lo normal**
cuando algo falla — ese día hubo **cuatro**, todas por fallos de la app, no por capricho —
y el único identificador que la app sabía construir no lo admitía.

### El daño no era el aborto: era la salida que dejaba

Con un id que no admite el segundo intento, las salidas que quedan son **inventarse una
fecha** o **abrir un proyecto nuevo**. La segunda parte el historial en dos, y el
historial de por qué se volvió a correr **es exactamente lo que el log existe para
conservar**. O sea: el identificador estaba destruyendo el registro que protege.

### La pieza que faltaba, y la nombró quien lo reportó: el `result_md5`

Tiene la propiedad correcta y no hace falta ninguna otra:

- dos resultados **distintos** no chocan → se puede repetir cuantas veces haga falta;
- dos resultados **idénticos** sí → y ahí abortar es lo correcto, porque eso no es
  repetir una corrida, es subir dos veces el mismo fichero.

`identidad.run_id` emite `blast-2026-09-02-<md5 del resultado>`. **La especie sale del
id**: el log es de un proyecto y el proyecto ya declara su especie en `proyecto.json`.

### Y el md5 se calcula en UN solo sitio

Los cuatro almacenes tenían su propio `hashlib.md5(raw)` — cuatro definiciones del mismo
número, el patrón de las cinco copias de la clave de consulta. Aquí además el id
**termina** en ese md5: calculados por separado, una corrida podría acabar con dos
identidades y nada obligaría a que coincidieran. Ahora es `identidad.result_fingerprint`,
con test de que ningún almacén vuelve a llamar a `hashlib`.

### El id lo montaba la PÁGINA, y eso era regla 6

Los cuatro modales lo construían con una f-string en `ui/streamlit_app.py`. El id decide
si una corrida entra o se rechaza: eso no es pintar, es decidir. Ahora lo derivan los
cuatro `*_run_from_*` de `presentation.py` y hay un test de que la página no vuelve a
escribir ninguno. (El del cuarto modal ni siquiera llevaba el tipo — `especie-fecha` a
secas — así que además de no admitir dos al día habría chocado con cualquier otro modal
que usara ese formato.)

### La segunda mitad, y pesa igual: el mensaje dice CÓMO SALIR

*«Hoy dice que aborta y nada más; el usuario acaba inventándose una fecha falsa o creando
proyectos que no necesita.»* Con el md5 dentro del id, un choque significa **una sola
cosa**, así que el mensaje puede decirla sin adivinar (principio nº 3):

> ESTE RESULTADO YA ESTÁ GUARDADO. No es una corrida nueva: el fichero que acabas de
> soltar es **byte a byte** el de la corrida `blast-2026-09-02-…`, del …, subida por … El
> id lleva el md5 del resultado, así que dos corridas DISTINTAS del mismo día entran las
> dos sin problema — sólo choca subir dos veces lo mismo.
>
> QUÉ HACER: si querías guardar ESTA corrida, ya está guardada — míra la en el historial y
> en la ficha, su veredicto ya cuenta. Si querías registrar OTRA, el resultado es idéntico
> al anterior, así que casi seguro has cogido el fichero viejo.
>
> LO QUE NO HAY QUE HACER: NO cambies la fecha y NO abras un proyecto nuevo. Y no hay nada
> que borrar: el log es **append-only** a propósito.

Las dos salidas falsas se nombran **por su nombre**, y la tercera —«borra la anterior»—
se dice que no existe. Un mensaje que sólo dice que aborta deja al usuario buscando una
salida, y la que encuentra es la que rompe el historial.

## 49 — La auditoría de los tests que no pueden fallar, y lo que encontró

**Pedida por el responsable del proyecto (2026-09-02)** después de tres erratas seguidas
con la misma anatomía —la clave del dossier, las cinco copias del formato de consulta
(las dos en la nº 44) y la clave de insumos (nº 47)—:

> *No basta con arreglarlas de una en una. Busca todos los sitios donde un test construya
> un diccionario o un fixture cuya clave sea también la que el código bajo prueba usa para
> buscar. Ésos son los tests que no pueden fallar, y cada uno tapa un fallo estructural.*

`tools/auditar_claves.py` + `data/claves_derivadas.toml`, dentro de `npm run check:shmir`.
**Guardia, no trinquete**: el número correcto es cero.

### Cómo se hace aplicable, que es la mitad del trabajo

El barrido ancho da **294** literales de test que nombran un fichero del depósito, y casi
todos son correctos: abrir `data/reference/mature.fa` por su nombre **es** usar el fichero
real. Un auditor con 294 hallazgos se apaga el primer día. La distinción que lo hace útil:

- **VALORES** — sólo cuenta el valor exacto usado como **clave de un diccionario o
  elemento de un conjunto que el test pasa a una llamada**. Ahí el test está construyendo
  el índice por el que el código va a buscar. Un literal suelto no cuenta.
- **FORMATO** — la **forma** de una familia de claves (`_pos\d+_(guia|pasajera)`,
  `blast-AAAA-MM-DD-<md5>`), en cualquier literal o f-string, sin los docstrings: citar el
  formato en prosa es documentarlo, no transcribirlo.

Con eso: **12 hallazgos**, todos reales. Los 294 quedaron en 10 + 4 ficheros.

### Lo que encontró, y no era sólo lo esperado

- **6 sitios en `test_recursos.py`** construían el directorio del manifiesto con
  `{"aav_casete.fa": …}` y `{"refseq_rna.fa": …}`, y luego pedían a `load_from_manifest`
  que los conectara **por rol**. Es el agujero de `rmsk_mouse.out` conectado por rol,
  dentro del test que debía cazarlo.
- **`test_corrida_de_la_pagina.py`** y **`test_empalme_intron.py`**: lo mismo con el par
  `.out`/`.tbl` y con el casete.
- **4 ficheros transcribían el nombre de consulta** — y ahí salió el hallazgo de verdad:
  escribían **`raton_pos200_guia`**, que es un formato que **la app ya no produce**. El
  slug de la especie es `mouse`. Los tests coincidían consigo mismos, así que el desfase
  entre lo que probaban y lo que la app emite llevaba ahí desde que `query_name` normaliza
  por slug, **sin que nada lo dijera**.

### Y un fallo del NÚCLEO, destapado por lo anterior

Al pedirle el nombre a `query_name` en vez de escribirlo salió que
`presentation.query_name(resolve("raton"), 200, "guia")` —con un `Species` ya resuelto en
vez del nombre— devolvía:

```
species_scientific_mus_musculus_slug_mouse_mirbase_prefix_mmu_taxid_txid10090_ucsc_assembly_mm39_pos200_guia
```

`species.resolve` terminaba en `Species(scientific=str(name), slug=_slugify(str(name)))`,
así que con **cualquier objeto** fabricaba una especie a partir de su `repr` — con la
forma correcta y sin ningún error. Es la regla 4 aplicada a algo que no es una URL:
inventar una identidad en vez de abortar. Ahora `resolve` es **idempotente** con un
`Species` y **aborta** con cualquier otro tipo.

Ese fallo no lo podía ver ningún test que escribiera el nombre a mano: sólo aparece
cuando alguien **pide** la clave. Que sea lo primero que salió al aplicar la auditoría es
el argumento de que la auditoría hacía falta.

## 50 — Un constructor permisivo convierte un error de tipo en un dato con forma correcta

**Salió de la auditoría de claves (2026-09-02)**, al pedirle el nombre de consulta a
`query_name` en vez de escribirlo:

```python
>>> query_name(resolve("raton"), 200, "guia")
'species_scientific_mus_musculus_slug_mouse_mirbase_prefix_mmu_taxid_txid10090_ucsc_assembly_mm39_pos200_guia'
```

`species.resolve` terminaba en `Species(scientific=str(name), slug=_slugify(str(name)))`,
así que con **cualquier objeto** fabricaba una especie a partir de su `repr`. La
anotación decía `name: str` y nadie la comprueba en tiempo de ejecución.

**La lección, y es lo que generaliza**: no produjo una excepción, produjo **un dato con
la forma correcta**. Una excepción se ve; un nombre de consulta plausible viaja al FASTA,
al `-outfmt 6` y al almacén. Es la regla 4 —no se deduce, se comprueba o se aborta—
aplicada al **tipo** en vez de a un endpoint, y la familia del `.out` sin resumen: lo que
sale tiene forma de resultado.

`resolve` es ahora **idempotente** con un `Species` y **aborta** con cualquier otro tipo.

### Y se buscaron los demás, que era la mitad del encargo

`tools/auditar_claves.py` gana la regla: **`str(argumento)` que acaba construyendo un
objeto o un digesto sin un `isinstance` sobre ese mismo argumento**. Se sigue **un nivel
de asignación** (`limpio = str(name).strip()` y luego `Species(..., limpio)`), y eso no es
un detalle: sin esa vuelta, el fuente de antes del arreglo **salía limpio**. Está
comprobado contra él.

Salieron **10**. Uno era real y ya está cerrado — `identidad.result_fingerprint` hacía
`str(raw)` antes de hashear, así que un `Path` o una lista habrían dado un md5 válido de
su `repr`, **y ese md5 entra en el `run_id`**. Los otros nueve son `str(fecha)` a un campo
de texto, `str(ruta)` a una etiqueta de procedencia o `str(algo)` dentro del mensaje de un
aborto: quedan declarados con su motivo en `data/magnitudes.toml`, y una declaración que
deje de corresponder caduca.

**No se mira la anotación de tipo**, y ésa es la decisión de método: la de `resolve` decía
`str` y era justo la que mentía.

## 51 — La corrida daba PASS y no llegaba ni a la tabla ni al semáforo

**Reportado con el proyecto delante (2026-09-02)**: proyecto `Intento_10`, corrida
`blast-…-da94fcf3…`. La sección «¿Siguen valiendo las corridas guardadas?» decía **PASS**
—o sea que la comparación de md5 contra `refseq_rna.fa` funcionaba— y a la vez el semáforo
decía «Hechas 6 de 10», las tarjetas «1 de 8», los diez candidatos salían `INCOMPLETE` y
el informe seguía listando `especificidad` entre los frentes abiertos.

Y quien lo reportó pidió **distinguir cuál de los dos fallos era**, porque son distintos:
si la celda cambió y el semáforo no, falta un consumidor; si la celda tampoco cambió,
`stores` no llega a `site_table_rows`. **Eran los dos.**

### Fallo 1 — el argumento que faltaba en la única llamada que se ejecuta

```python
site_table_rows(tiling, seleccion, species=nombre, selected=marcados)
```

Sin `stores=`. La función lo acepta desde la tanda anterior y sus tests pasan; la página
—el único camino que se ejecuta— no lo usaba. Es la **quinta** vez de esta familia
—`triple_motive_rows`, `intron_folding`, `store.save_*`, `page_run`— y la primera en que
la capacidad estaba **cableada y probada**: lo que faltaba era un argumento.

### Fallo 2 — y además faltaban TRES consumidores

Aunque `stores` hubiera llegado a la tabla, sólo habría cambiado la celda:

- **el veredicto de cada candidato** salía de `ventana.verdict`, del informe de tilado. La
  fila podía decir `especificidad: PASS` y `veredicto: INCOMPLETE`, **una al lado de la
  otra y las dos con pinta de medida** — dos contadores del mismo suceso;
- **las tarjetas y el semáforo** se derivan de `blocking_fronts`, que no mira los
  almacenes;
- **el bloque de frentes del informe**, por lo mismo.

Ahora `presentation.store_states_by_front` resuelve una sola vez lo que dicen los
almacenes y lo usan los cuatro. El veredicto lo agrega `filters.overall_verdict` con los
estados **efectivos** — no se reimplementa, que es como `NO_CIERRA` seguiría contando mal.

### La regla que impide un cierre falso, y no se puede omitir

**Un frente sólo se cierra si lo cubre TODO el panel.** Con seis candidatos consultados de
diez, decir «frente cerrado» daría por comprobados cuatro que nadie miró — es la regla 3
un piso más arriba. Y **un `FAIL` cierra el frente igual que un `PASS`**: un frente se
cierra consiguiendo *la respuesta*, no consiguiendo una buena. Lo que no cierra es
`NOT_RUN` ni `NO_CIERRA`, porque ahí no hay respuesta que leer.

## 52 — Dos auditorías con reglas opuestas sobre la misma evidencia

Pasó dentro de la tanda anterior y lo señaló el responsable del proyecto:
`auditar_fixtures` reconocía que un test fabrica un artefacto **por el nombre del fichero
escrito en el test**, y `auditar_claves` —estrenada el mismo día— **prohíbe escribirlo**.
Dos guardias con reglas opuestas sobre la misma evidencia.

Al derivar el nombre, la fabricación **siguió existiendo** y su justificación, viva, pasó
a leerse como **caducada**. El guardia dejó de ver lo que sí estaba: el fallo hacia el
silencio, que es el peor de los dos sentidos.

Y la contramedida **no es coordinarlas a mano**: con once auditorías conviviendo, eso es
una condición que alguien tiene que recordar. Ver el principio nº 26 y
`data/auditorias.toml`.

**El cruce encontró dos cosas nada más estrenarse**, que es el argumento de que hacía
falta: dos auditorías del repositorio (`auditar_geometria`, `auditar_navegacion`) que **no
estaban declaradas en ninguna parte**, y que `guardias.toml` y `magnitudes.toml` opinan
las dos sobre quién calcula un digesto — con lo que hay que actualizar **las dos** al
añadir un sitio que hashea. Eso ya se había olvidado dos veces en un solo día
(`result_fingerprint` y `file_fingerprint`), y las dos se cazaron por casualidad al correr
la suite.

## 53 — «Banda larga = retenido» era falso, y estaba escrito sobre el único frente binario

**Corregido por Joaquín Castilla (2026-09-02)**, y va con su nombre por la misma razón que
la predicción refutada de la carrera de A y la rectificación del rol de APA: si sólo se
anotan las correcciones ajenas, el registro deja de ser un registro.

La ficha del frente de empalme y `splicing.splicing_readouts` decían, con esas palabras:

> Banda **CORTA** = empalmado, banda **LARGA** = retenido, y la **proporción** es la
> eficiencia.

**Y es falso.** El pre-mRNA sin empalmar **existe siempre**: el splicing es
cotranscripcional pero **no instantáneo**, así que en cualquier población de transcritos
hay nacientes a medio procesar. La banda larga sale **con el empalme perfecto**. Presencia
de banda larga no es evidencia de retención — es evidencia de que la célula estaba
transcribiendo.

### Por qué esto es grave y no un matiz

Es el **único frente binario** del proyecto: si el intrón no se escinde no hay proteína DN
en absoluto. Un ensayo mal especificado ahí no da un número peor, da un **veredicto
invertido** — y el modo de fallo es el peor de todos: la banda larga aparece, se lee como
retención, y se descarta una arquitectura que funciona. Al revés también: sin las
condiciones, una retención real queda enterrada en el naciente.

Y es la familia del **«Alu 0 %» al revés**. Allí se afirmaba una **ausencia** sin haber
buscado; aquí una **presencia** sin haber separado las dos causas que la producen. En los
dos casos el resultado sale, tiene la forma correcta, y no dice lo que se cree.

### Las cuatro condiciones, y ninguna es opcional

Tres quitan del medio lo que **no** es retención; la cuarta cambia **lo que se lee**:

1. **RNA CITOPLÁSMICO, no total.** El pre-mRNA sin empalmar es nuclear. Lo que sí es un
   fallo de empalme es encontrar el intrón retenido **en el citoplasma**, que es donde se
   traduce.
2. **Selección por polyA**, que excluye la mayor parte del naciente.
3. **DNasa y control SIN retrotranscriptasa.** El **genoma del AAV lleva el intrón
   dentro**, así que una traza de ADN del vector amplifica y da una banda larga
   **indistinguible** de la retención. El −RT tiene que salir vacío; si sale banda, lo que
   se está midiendo es ADN.
4. **La lectura es la PROPORCIÓN corta/larga, NO la presencia**, y no se lee sola:
   **dos referencias en la misma tanda** — el control sin intrón, que es el **100 % corta**
   y fija dónde está el cero, y el terapéutico.

La cuarta se apoya en algo que el proyecto ya tenía: el control sin intrón está
**especificado** (`splicing.intronless_control`, 82 pb, md5 `d72c574d…`) y sale en la hoja
de pedido. Lo que no estaba dicho es que **es la referencia de esta lectura**, no sólo el
techo de expresión del Western.

### Y la frase falsa no se borra: se marca

Vive citada entre comillas como lo que fue —el registro es para eso— y
`tests/test_rtpcr_no_confunde_naciente.py` comprueba que **no se vuelve a afirmar**, ni en
el código ni en la ficha, y que las cuatro condiciones están **en los dos sitios**. Es el
principio nº 11 aplicado por adelantado: la prosa que se queda atrás es la que alguien va a
leer, y ésta se iba a leer en una libreta de laboratorio.

## 54 — «6 de 10» era la corrida cubriendo 6 de 10, y la app no lo decía

**Reportado tres veces con los mismos números (2026-09-02)** y con el argumento que
resolvió el caso, que no era mío:

> Son tres caminos distintos —el semáforo, las tarjetas y el bloque de frentes del
> informe— y los tres siguen sin cambiar, **así que el fallo es común y anterior a los
> tres**.

Y era exactamente eso. Mi diagnóstico anterior (errata nº 51) explicaba **un** camino —el
argumento `stores=` que faltaba en la tabla— y arreglaba **un** consumidor. `blocking_fronts`
tiene **SEIS llamadores** (`presentation` ×3, `informe_doc`, `dossier`, `outputs`), y yo
estaba metiendo los almacenes **por el consumidor**: se arregla uno y los otros cinco
siguen igual. Ahora entran por `blocking_fronts` y todos se enteran a la vez.

Los dos que quedaban vivos y que nunca los leyeron:

- **`status_light`** — el semáforo de arriba. Cuenta los filtros de la ventana, que no
  saben nada del registro del proyecto. Decía «6 de 10» con una corrida válida encima.
- **el bloque de frentes de `informe_doc`** — el documento leía los almacenes para la
  **ficha** de cada candidato y no para la lista de frentes, así que podía decir
  `especificidad: PASS` en la ficha y listarla entre los frentes abiertos tres secciones
  más arriba. El principio nº 23 **dentro de un solo documento**.

### Y lo que había debajo, que es lo que más costaba ver

Reproducido el flujo real con el fixture murino: con una corrida que cubre **6 de los 10**
candidatos del panel, el semáforo dice exactamente **«6 de 10»**. Es el número del informe
del usuario, clavado.

El estado era **correcto** —un frente no se cierra con 6 de 10, porque daría por
comprobados cuatro que nadie miró— y **la app no lo decía**. Una corrida que cubre parte
del panel salía **idéntica** a no tener ninguna: tarjeta gris, «sin hacer», nada. Quien
acaba de subir una corrida de horas ve la pantalla sin cambiar y concluye que no se ha
recogido — que es lo que pasó tres veces.

Es la distinción de siempre —«no comprobado» y «comprobado a medias» no son lo mismo—
aplicada al **progreso** en vez de al veredicto, y con la misma consecuencia: el silencio
se lee como el estado peor. `presentation.run_coverage` la emite y la tarjeta la pinta:

> **HAY CORRIDA, PERO NO CUBRE EL PANEL:** 6 de 10 candidatos tienen veredicto de este
> frente y 4 no. El frente NO se cierra con eso —darlo por cerrado daría por comprobados
> los que nadie miró—, y **la corrida que hay no se pierde**: su veredicto está en la
> celda de cada candidato cubierto. Faltan: …

### Nota de método, y va al registro

**Probar las funciones por separado no lo enseñaba.** Llamando a `site_table_rows` y a
`front_card_rows` con un almacén salían `PASS` y `HECHO`, y eso es lo que yo medí y
respondí. El fallo vivía en la **juntura**: qué consumidores existen, cuál se quedó fuera,
y qué pasa cuando el panel está cubierto a medias. Lo dijo el principio nº 17 y lo repitió
quien lo reportó — *reproduce el flujo real, no llames a las funciones*—, y hasta que no lo
hice con el panel entero y una cobertura parcial no salió.

Los almacenes se cargan ahora **una sola vez** en `bloque_especie` y los usan los cuatro
consumidores, con test de que no vuelve a haber dos cargas: cuatro copias del mismo estado
son cuatro cosas que pueden discrepar.

### La última pieza, encontrada revisando antes de prometer nada

Los cuatro consumidores pueden estar perfectos y **el usuario ver exactamente lo mismo que
si estuvieran rotos**: la tabla, el semáforo y las tarjetas se pintan **arriba** del
formulario de guardado, o sea **antes** en el mismo script de Streamlit. En el rerun que
guarda la corrida siguen enseñando el estado de **antes** de guardarla.

Así que el usuario lee «Guardada, 10 veredictos actualizados» y ve la página sin cambiar.
Y concluye, con razón, que no se ha recogido. Es el fallo que habría reproducido el
informe de las tres veces anteriores **con todo lo demás ya arreglado**.

`_guardar_corrida` hace ahora `st.rerun()` tras guardar, y la confirmación viaja en
`session_state` para sobrevivir al repintado — sin eso habría que elegir entre enseñar el
mensaje y refrescar, y hacen falta las dos cosas.

**Y el test de eso se ancló mal a la primera**: buscaba `st.rerun()` en el cuerpo de la
función y lo encontraba **dentro del comentario que lo explica**, así que medía el orden
contra la prosa. Corregido —se quitan los comentarios antes de mirar— y anotado aquí
porque es la misma familia que un guardia que muerde donde no hay lógica: **un ancla falsa
da verde sin comprobar nada**.

## 55 — Eran TRES tablas, y «no se consultó» decía lo mismo que «falta el fichero»

**Reportado con dos capturas (2026-09-02)**, y el diagnóstico volvió a ser de quien lo
reportaba, no mío. La tarjeta decía **«CERRADO por corrida guardada: los 10 candidatos del
panel tienen veredicto»** y la tabla de esos mismos diez, tres centímetros más arriba,
decía `NOT_RUN` en las diez filas.

Mi respuesta anterior fue que la tabla «no estaba mal, estaba ilegible»: 270 filas y sólo
10 con veredicto. **Era otra tabla.** Lo dijo el título de la propia captura —«Candidatos
— un estado por filtro»— y lo confirmó **por el dato interno**:

> la última fila lleva marcada `bandera_polyA_debil`. Ése es `3utr:1018`, el único del
> panel con `ACTAAA` solapando la ventana. Son los diez del panel, no diez de los otros
> 260.

Comprobado: `tx:1967` = `3utr:1018`, y es la única del panel con esa bandera. **Una
identificación por un dato interno vale más que una captura**, y era la única forma de
distinguir las dos tablas desde fuera.

### Eran TRES, y las arreglé de una en una

`site_table_rows` (todos los sitios elegibles), **`candidate_rows`** (la de la captura) y
**`window_rows`** (todas las ventanas, en su propio desplegable). Las tres las pinta la
página, las tres emiten estado por filtro, y el `stores=` había ido a **una**.

El guardia que faltaba es mecánico y lo encontró sola la tercera: `_filter_columns` es el
**único** sitio que emite el estado por filtro de una fila, así que **todo el que lo llame
tiene que pasar por `_with_stores`**. Escrito el test, saltó `window_rows` de inmediato.

### Y la segunda mitad, que no es presentación

> Si sólo diez de 270 pueden tener veredicto y las 260 restantes salen `NOT_RUN` para
> siempre, esa tabla necesita distinguir «no se consultó» de «se consultó y no cerró». Hoy
> las dos dicen lo mismo, y eso es lo que hace la tabla ilegible.

Tiene razón y mi «es de presentación» era falso: son **dos causas distintas y se arreglan
con cosas distintas** —una lanzando una corrida que incluya ese candidato, la otra
consiguiendo un fichero—. Entra `SIN_CONSULTAR`, y sólo aparece cuando el proyecto **ya
tiene corridas de ese frente**: sin ninguna, el estado honesto sigue siendo `NOT_RUN`,
porque entonces no es que ese candidato se haya quedado fuera. Con la corrida del panel
guardada, la tabla pasa de 270 `NOT_RUN` a **10 `PASS` + 260 `SIN_CONSULTAR`**.

Para el veredicto agregado **bloquea igual que `NOT_RUN`**: lo que cambia es qué hay que
hacer, no si impide aprobar.

Y arrastró un contador: la primera corrida decía «**270 cambios**» porque las 260 filas
cambiaban de etiqueta. `verdicts_changed` trata ahora `SIN_CONSULTAR` y `NOT_RUN` como lo
mismo — era el contador engañoso que ese contador existe para no ser.

### Lo que esta errata deja como método

Tres veces seguidas he dado un diagnóstico que explicaba **una parte** de lo observado y
he ido a arreglar esa parte: primero un consumidor de seis, luego una tabla de tres. Las
tres veces la corrección vino de fuera y las tres veces el argumento fue el mismo —
**varios síntomas a la vez significan una causa arriba, no varios arreglos abajo**. El
guardia de `_filter_columns` es la primera contramedida de esta serie que no depende de
que yo mire en el sitio correcto.

## 56 — Un `> 1` que codificaba «uno es tuyo», y el frente tenía DOS implementaciones

**Reportado con la hipótesis ya construida (2026-09-02)**, y era la correcta:

> sale FAIL en los diez, y diez de diez apunta a criterio mal aplicado, no a diez guías
> malas. […] el `.tsv` tiene dos aciertos al 100 % por guía, y los dos son Prnp:
> `NM_011170.3` y `NM_001278256.1`. […] La exención tiene que ser por gen, no por
> accession.

**Confirmada midiendo, no leyendo.** `BlastRun.verdict` no miraba el sujeto en ninguna
parte —comprobado sobre `co_names`, no de vista—: contaba los aciertos a ≤1
desapareamiento y emitía

```python
estado = FilterState.FAIL if len(fuera) > 1 else FilterState.PASS
```

Con dos variantes de transcrito de la propia diana eso son dos, así que **cada candidato
fallaba contra su propio blanco**. Diez de diez.

### El `> 1` no era un umbral flojo: era un supuesto escondido en un número

Ese `1` no es una tolerancia. Es la afirmación **«la diana produce exactamente un
acierto»**, que nadie escribió y que no es cierta para ningún gen con más de una variante
anotada. Y falla en **las dos direcciones, las dos invisibles**:

- **hacia el FAIL** — el caso de arriba;
- **hacia el PASS** — una guía que **no acierta a su propia diana** sale `PASS`, porque
  cero aciertos también es «no más de uno». Un candidato que quizá no reconoce su blanco
  aprueba el frente por no tener con qué compararse.

Eso es **categoría propia** y no lo cubría nada: `justificacion.py` vigila los umbrales
**sin base medida** —números sin respaldo, declarados como tales— y éste tenía respaldo
aparente y **significaba otra cosa de la que parecía**. Entran
`data/umbrales_con_supuesto.toml` y `tools/auditar_umbrales.py`, GUARDIA con cero: un
umbral dentro de una función que emite veredicto declara **de qué supuesto depende su
lectura** y **dónde está declarado ese supuesto**. Si no se puede escribir, el umbral está
mal planteado — que es exactamente lo que le pasaba a éste.

- El recorte es lo que lo hace aplicable: el barrido ancho da **123** comparaciones contra
  literales en el paquete y casi todas son formato o guardias de entrada. Acotado a lo que
  **decide**, son **ocho**, y se revisan una a una.
- Y lleva **control adversario**: el test le da el fuente de **antes** y exige que señale
  el `> 1`. Salir a cero sobre el código ya arreglado no demuestra que muerda — errata
  nº 29.

### Había DOS implementaciones del mismo frente, y no coincidían en nada

`specificity.filter_specificity` y `BlastRun.verdict` contestan la misma pregunta y
diferían en **tres** cosas a la vez:

| | `filter_specificity` | `verdict` (antes) |
|---|---|---|
| hits en **sentido** | los descarta | los contaba |
| exención de la diana | por `target`, exacto | ninguna |
| criterio | ningún acierto grave fuera | `> 1` en total |

Lo del sentido no es un detalle: `-outfmt 6` **no tiene columna de hebra**, la orientación
es el signo de `sstart`→`send`, y un acierto en sentido contra un mRNA **no es un
off-target de una guía** — es la otra hebra. `verdict` los contaba.

**No se arreglan por separado**, que es lo que pedía el encargo: las dos llaman ahora a
`specificity.judge_hits`, que es el único sitio donde vive el criterio, y hay un test que
les da los mismos hits y exige el mismo estado. Un criterio en dos sitios es la errata
nº 52 con otro traje.

### La lista de la diana es DATO, y sin ella NO hay veredicto

Se eligió la segunda de las dos opciones planteadas —lista declarada de accessions, en
`data/diana/variantes.toml`, no un mapa transcrito→gen— y **la condición es la que decide**:
sin declaración **no hay veredicto**, nunca un `PASS` desde una lista vacía. Una exención
vacía convertiría «no sé cuáles son las variantes» en «ninguna es tuya», que es el error de
antes con el signo cambiado.

- El fichero lleva **procedencia y verificación** por especie, como todo lo demás.
- El **humano está deliberadamente ausente**: si todas las especies estuvieran declaradas,
  la condición no se ejercitaría nunca y sería una frase. Sobre humano, el veredicto sale
  `NO_CIERRA` con el motivo, que es lo honesto — hay corrida y no puede cerrar.

### Y el motivo dice contra qué acertó

Iba en el mismo cambio porque es lo que convierte esta errata en cinco segundos la próxima
vez: el `FAIL` nombra los accessions de fuera, el `PASS` nombra **los eximidos por ser la
propia diana**, y hay nota aparte para los 2 desapareamientos, para los hits en sentido
descartados y para el caso «ningún acierto contra la propia diana», que **no** es una buena
noticia. Antes decía `FAIL` y un recuento: un fallo contra el propio blanco era
indistinguible de uno real, y por eso costó un intercambio en vez de una mirada.

## 57 — Un parcial de 13 nt no es un off-target, y la orientación no era un filtro

**Reportado con el `.tsv` contado a mano (2026-09-02)**, un día después de la nº 56 y
sobre el arreglo de la nº 56. Son **dos fallos independientes** en el mismo criterio, y
cada uno tumba una hebra distinta.

> De las 20 consultas, ninguna tiene un solo acierto fuerte fuera de Prnp. Los únicos
> hits con ≥21 nt alineados y ≤1 desapareamiento son, en las 20, `NM_011170.3` y
> `NM_001278256.1`. Todo lo demás son parciales de 10-16 nt.

### 1. El `FAIL` de la tabla: `mismatches` no dice que el acierto sea perfecto

Dice que es perfecto **en el segmento que alineó**. Con `blastn-short`, `word_size 7` y
`evalue 1000` la corrida viene llena de parciales de 10-16 nt clavados, y **todos traen
`mismatches = 0`**. El criterio miraba `mismatches` y **no miraba la longitud**, así que
cada uno de esos entraba como acierto grave.

Medido sobre la misma corrida, cambiando **sólo** la orientación del ruido:

| parciales de 10-16 nt | veredicto |
|---|---|
| en sentido | `PASS` |
| antisentido | `FAIL` |

Un veredicto que depende de la orientación de un ruido que no debía contar en ningún
caso. Ésa es la causa del `FAIL` de las diez filas de la tabla, que lee la consulta
`…_guia`.

**Por qué `filter_specificity` no lo tenía, compartiendo el criterio**: su escáner
(`_scan_one`) casa ventanas de **exactamente `len(pattern)`**, así que todos sus hits son
de longitud completa y la condición se cumplía sola. BLAST devuelve alineamientos
**locales**. **Al mover el criterio de un sitio al otro no viajó el supuesto que lo
sostenía** — que es la nº 56 otra vez, un piso más abajo, y por eso el mínimo ahora se
**deriva de la sonda de cada consulta** en vez de escribirse: un `21` llevaría dentro «la
sonda mide 22».

### 2. La orientación: dos cantidades distintas con el mismo nombre

> La orientación no es un filtro, es la firma de qué hebra es.

Correcto, y el diagnóstico es más fino que «estaba mal»: **`ANTISENSE` no significa lo
mismo en los dos sitios**.

- En **`filter_specificity`** lo pone nuestro escáner: `ANTISENSE` = casó el complemento
  inverso de la sonda, o sea **la sonda puede aparearse con ese transcrito**. Un hit
  `SENSE` es un transcrito que contiene la sonda **tal cual**, con el que no puede
  aparearse. Descartarlos ahí es **correcto**, está medido y no se toca.
- En **`-outfmt 6`** el signo de `sstart`→`send` es la **hebra del sujeto tal como está
  depositado**. Para una guía coincide con lo anterior; **para la pasajera, no**: la
  pasajera lleva la misma secuencia que su blanco, así que acierta **en sentido**.

Al copiar el descarte de un sitio al otro se tiraba **el acierto legítimo de la pasajera
contra su propia diana**, y con él la exención de variantes. Medido sobre el código
desplegado, con las cuentas del `.tsv`:

| consulta | estado | ¿eximió la diana? | ¿dispara «ningún acierto contra su propia diana»? |
|---|---|---|---|
| guía | FAIL | **sí** | no |
| pasajera | FAIL | **no** | **sí** |

O sea: la predicción de que las diez estarían disparando esa nota es **cierta en las
pasajeras y falsa en las guías** — y la tabla sólo pide la consulta `…_guia`
(`presentation._store_state`), que es por lo que no se veía. Las dos mitades del
diagnóstico eran correctas y apuntaban a filas distintas.

### Lo que la orientación sí compra, que es más que descartar

Un **invariante de montaje** (`specificity.EXPECTED_ORIENTATION`): guía → antisentido,
pasajera → sentido, contra su **propia** diana. Un acierto con la orientación que esa
hebra no puede dar no es un off-target: es que **guía y pasajera están intercambiadas**, o
el FASTA de consulta se montó al revés. **No cambia el veredicto** —mezclarlo sería
confundir «esta guía tiene off-targets» con «esta construcción está mal montada»— y no lo
detecta ningún otro guardia.

### Y el criterio ya no mira la orientación

Cada llamador declara **qué puede probar** y le somete ese conjunto: `filter_specificity`
sólo los apareables, porque en su escáner eso está medido; `BlastRun.verdict` **todos**,
porque allí el signo del intervalo no es esa cantidad. El criterio en sí —longitud,
desapareamientos, fuera de la diana declarada— vive en un solo sitio. Contar de más en la
corrida de BLAST es la dirección segura: sobra por arriba, nunca por abajo.

### Una consecuencia en el registro, no sólo en el código

La longitud de cada sonda **viaja ahora con la corrida** (`BlastRun.query_lengths`, y en
el `registro.jsonl`): un veredicto tiene que poder rederivarse de lo que el log guarda, y
sin ese dato no se puede decir qué cuenta como alineamiento completo. Las corridas ya
escritas no se quedan sin veredicto — se acota con el propio resultado, porque `qend`
nunca pasa de la sonda, **y el motivo lo dice**, con la dirección del error posible.

### Coda: la generalización, y una tercera cosa que salió al buscarla

`ANTISENSE` no era el único. Al derivar del AST **qué magnitudes se calculan con el mismo
nombre en más de un módulo** —principio nº 27, `tools/auditar_homonimos.py`— salieron
siete cantidades distintas compartiendo nombre: además de `antisense` y `aligned`,
`usable` («este dato se puede usar» en tres clases, «esta ventana es única en el
plásmido» en la cuarta), `md5` (el del texto frente al de la secuencia: la trampa de los
tres checksums, dentro del código), `conclusive`, `ambiguous` y `fraction`.

Y una que no llegó a la tabla porque se arregló al encontrarla: **`selection.Site.end`
devolvía el inicio de la última ventana del bloque**, mientras en todo el resto del
paquete `end` es un final de intervalo inclusivo. Leído como final, el sitio salía 21 nt
más corto.

**Lo que enseña es lo que pasó al renombrarla.** Dije que no la leía nadie: es cierto de
la producción —el número equivocado nunca llegó a una pantalla— y **falso de los tests**.
Había uno que la afirmaba como final de intervalo, `(10, 12)` para tres ventanas de 22
nt. Código y test compartían la confusión, así que **ninguno de los dos podía delatarla**
— es el principio nº 22 en su forma más limpia, y la razón de que un homónimo así
sobreviva años: no hay nada que falle.

## 58 — El fichero que la propia app manda descargar no podía entrar

**Reportado el 2026-09-02** con el mensaje literal de la app:

> RECHAZADO — `/data/shmir/reference/.transcriptoma_3utr.fa.subiendo`: el identificador
> `'mm39_ncbiRefSeqCurated_NR_189043.1_0'` aparece dos veces; se aborta en vez de quedarse
> con una de las dos secuencias.

**No era el tamaño.** Los 84 MB suben bien: lo que rechaza el fichero es el validador, y
lo rechaza por tener **exactamente la forma que la ficha de obtención manda conseguir**.

La ruta que la propia app escribe es UCSC Table Browser → **«3' UTR Exons»**, que da **un
registro por exón**: un 3'UTR troceado sale varias veces con el mismo accession y un
sufijo `_0`, `_1`. Y la ficha dice además, con esas palabras, que **no** se filtren las
isoformas a mano.

### Estaba decidido, y arreglado en el lado que no corre

`offtarget.parse_fasta_pairs` lleva la decisión escrita en su propio docstring:

> No se reutiliza `seed_load.parse_fasta_records` a propósito: aquel ABORTA con un
> identificador repetido, y aquí repetirse es un caso legítimo y esperado […] Abortar
> escondería justo lo que hay que auditar.

El camino vivo —el panel de subida (`deposito._v_transcriptoma`) y `resources`— usaba
**el otro**. Es la familia de las erratas nº 56 y nº 57 por tercera vez en dos días: dos
implementaciones de lo mismo, y la del camino que se ejecuta es la equivocada.

**Y `parse_fasta_records` tenía UN SOLO llamador**: precisamente el fichero cuya forma
documentada lo viola. El guardia estricto no protegía a nadie más.

### No bastaba con arreglar el panel

`resources._transcriptoma` conecta el fichero con el **mismo** cargador. Aceptarlo sólo en
la subida habría movido el fallo al diseño — y ahí es peor, porque el fichero ya figuraría
como **presente** mientras su frente revienta al conectarlo. Los dos cuelgan ahora de un
único parser.

### Lo que el arreglo NO relaja

El motivo del parser estricto era bueno: un diccionario se habría quedado con **una** de
las dos secuencias y el conteo saldría corto **sin avisar**. Lo que estaba mal era la
salida elegida. `Utr3Set.records` pasa a ser una secuencia de pares —no se pierde nada— y
la procedencia **dice** cuántos identificadores se repiten y que por tanto hay **menos
transcritos que entradas**, con el conteo por transcrito inflado. Un fichero sin
repetidos no avisa de nada: hay control adversario de las dos mitades. Y cero entradas
sigue abortando: un fichero vacío y un transcriptoma sin sitios dan el mismo cero y no
son lo mismo.

### Lo que queda ABIERTO, y va escrito porque no está comprobado

En la misma sesión se reportó que **`aav_casete.fa` tampoco «entra»**. Eso **no está
reproducido** y no se le pone causa. Lo que sí está medido, y descartado: su validador
pasa contra el fichero real; `accept_upload` entero funciona con la fecha vacía tal como
lo deja el formulario; la corrida de la página tarda **0,33 s**, así que no es que se
rediseñe en cada rerun; y el límite de subida de Streamlit (200 MB) no se toca. La
sospecha pendiente de confirmar es de interfaz: el widget se **llama** «Subir
aav_casete.fa» y soltar el fichero ahí no sube nada — hay que rellenar dos campos y pulsar
un segundo botón más abajo. Si se confirma, la etiqueta promete una acción que no hace.

## 59 — Cuatro minutos por clic: la carga de seed barría 84 MB por cada una de 407 ventanas

**Reportado el 2026-09-02**, con la pregunta bien planteada: *«¿esto es achacable a la
aplicación o al servidor?»*. **A la aplicación**, y medido antes de tocar nada.

Apareció justo cuando el transcriptoma por fin entró (errata nº 58). Desde ese momento
`tile_utr` llamaba a `seed_load` **una vez por cada ventana escaneable** —407 en la
corrida murina— y **cada una barría el fichero entero**:

| | medido |
|---|---|
| barrido puro | 226 M nt/s |
| una ventana contra 84 MB | 0,4 s; 0,7 s troceado en registros pequeños, que es la forma real |
| × 407 ventanas | **3–4 minutos** |
| y eso | **en cada rerun**: cada tecla, cada botón, cada subida |

**Sin el transcriptoma la corrida entera tarda 0,33 s.** Ése es el dato que descarta el
servidor: no se ha vuelto lento, es que se conectó un trabajo que crece con el tamaño del
fichero y se repetía por ventana.

### Por qué se puede acotar, y no es una excusa

`carga_seed` **no alimenta ninguna selección ni ningún veredicto**. Lo dice `selection.py`
en su propio comentario —«es un número comparativo y por eso nunca estuvo en
`not_run_filters`»— y se comprobó: sus únicos consumidores son la columna del TSV
comparativo y la de la tabla de la página.

**Y el precedente está en la misma función, tres líneas más arriba**: la colisión de seed
ya se acota «por coste» a las ventanas que superan los biofísicos, con su `NOT_RUN` y su
motivo escrito. Esto es ese mismo escalón una vez más.

### Dos pasadas, y por qué son exactas

`page_run` tila **sin contar ninguna** —la selección no la mira—, selecciona, y vuelve a
tilar contando **sólo en el panel**. Dos tilados cuestan 0,33 s cada uno, la función es
determinista y las entradas son las mismas, así que el segundo informe es idéntico salvo
esa columna. Y `frozenset()` («en ninguna») **no es** `None` («en todas»): son dos valores
porque son dos cosas — el CLI sigue contándolas todas, que para una corrida por lotes está
bien.

Medido después: de **~200 s a ~9 s** extrapolado a 84 MB, con el número en las **10** del
panel y en ninguna más.

### El fallo que cometí al arreglarlo, y lo cazó medir otra vez

La primera versión acotaba **sólo la segunda pasada** y dejaba la primera contándolas
todas: seguía tardando 200 s. Un arreglo que no se mide es una hipótesis — y aquí la
medida posterior es lo único que lo distinguió de estar arreglado.

### Lo que no se relaja

Donde no se cuenta sale **`NOT_RUN` con el motivo**, nunca un cero ni una celda vacía que
se lea como cero: no haber contado y contar cero son cosas distintas, y ésa es la regla 3
desde el primer día. Donde sí se cuenta, **el número es el mismo** — misma función, mismas
entradas—, y hay test de que coincide con el de la pasada sin acotar.

## 60 — `NO_APLICA` escondía cuál de los tres era, y la tabla de almacenes tenía una fila

**Reportado el 2026-09-02** con cuatro cosas a la vez. Las tres que se cierran aquí
comparten forma: **una declaración incompleta que no se lee como incompleta**.

### `seed` salía `NO_APLICA`, y la pregunta se perdía entre dos columnas

`NO_APLICA` es «esta pregunta no se le hace a este candidato», y a una guía de 22 nt con
`mature.fa` cargado **sí se le hace** — la contesta `seed_colision`. El retiro del filtro
de arranque era deliberado y estaba escrito; el **estado** era el equivocado.

Entra `FilterState.SUSTITUIDO`, con las dos condiciones que lo hacen honesto:

1. **el motivo NOMBRA al sustituto** — «sustituido» a secas manda a buscar a ciegas;
2. **un `SUSTITUIDO` cuyo sustituto esté en `NOT_RUN` no puede existir**: se degrada a
   `NOT_RUN` con el motivo. Sin eso, la pregunta se pierde en el hueco entre las dos
   columnas y **las dos parecen resueltas**.

**Y ese hueco no era hipotético: era el estado real.** `seed_colision` sale `NOT_RUN`
mientras falte la lista ampliada de abundancia, así que la pareja era
`seed: NO_APLICA` + `seed_colision: NOT_RUN` — nada bloqueaba y nadie había contestado.
El diff del golden lo enseña entero: `seed` **aparece** ahora entre los filtros sin
ejecutar y los frentes provisionales pasan de **6 a 7**.

Lo aplica `filters.check_substitution`, nunca se anota a mano.

### `offtarget_seed` no tenía columna: la tabla de almacenes tenía UNA fila

`load_stores` reconstruye **cuatro** almacenes y `STORE_FOR_FRONT` declaraba **uno**. Con
el transcriptoma ya en el depósito, su frente no llegaba a ninguna de las cuatro tablas —
y `verdicts_changed` decía 0 en tres de los cuatro modales porque no había columna a la
que llevar el veredicto.

> Una tabla de declaración con una sola fila parece configurada. Es el mismo disfraz que
> `UNDECIDED_FILTERS` con un miembro.

`tests/test_almacenes_declarados.py` lo cierra por el modo de fallo y no por el caso:
**todo almacén llega a una columna o declara por qué no**, con el conjunto de almacenes
**pedido** a `presentation.STORES` en vez de escrito en el test — que sería preguntar por
la clave que uno mismo ha puesto (principio nº 25). El único sin columna es el de
`empalme_sitios`, y su motivo está declarado: su unidad es el par candidato × intrón, así
que una columna por candidato colapsaría justo la comparación entre intrones para la que
existe.

### Dos columnas por hebra, y no es formato

`offtarget_seed` y `seed_colision` dan ahora `<frente>:guia` y `<frente>:pasajera`. La
ficha ya las partía y la tabla no: **la pasajera es el eje donde menos datos hay**, y
fundirla con la guía la hace invisible — el estado de la guía pasaría por el de las dos.

### La tasa base, en la fila

Estaba sólo en el aviso de encima de la tabla. Ése se lee una vez; **la fila se lee
siempre**, y quien se lleva el CSV se lleva las filas y no el aviso. Sin ella no se sabe
si un `LIMPIO` es notable o es lo que predice el azar — que es lo que este proyecto tiene
decidido que no puede faltar «también en los LIMPIO, para no dar una falsa calma».

### Lo que NO se reproduce, y no se le pone causa

El heptámero de **6 nt** del CSV. Los **tres** productores de esa columna —el resultado
guardado, la fila de la tabla y el bloque exportable— dan **7 nt**, medido sobre el panel
real con `mature.fa`: `AATGCGA`, `TTAGTAA`, `TTTCCCA`, `AGAAGTA`. La comparación es 2-8
sobre un espacio de 16.384 con tasa base del 10 %, así que **los `LIMPIO` valen** — es la
mitad que no invalida el resultado. Dónde se pierde el carácter queda **abierto**.

## 61 — El fichero decía OPCIONAL y el filtro no cerraba sin él

**Contradicción señalada por el responsable del proyecto (2026-09-02)**, sobre el hallazgo
de la errata anterior:

> `seed_colision` no cierra sin `mirgenedb_cerebro.txt`, y ese fichero está marcado
> OPCIONAL en el panel — «No bloquea nada: el filtro corre sin él y con él afina». Las dos
> cosas no pueden ser ciertas.

**La que cede es el filtro**, y no por comodidad: lo dice la decisión escrita de
2026-08-26. Son **dos capas y hacen cosas distintas** — el **núcleo** son diez miARN
abundantes de cerebro, va en código, corre **siempre** sin fichero y es el que da `FAIL`;
la **ampliada** es de fichero y su producto es un **AVISO**.

Un aviso que falta **no puede convertir un `PASS` en `INCOMPLETE`**, porque nunca habría
podido convertirlo en `FAIL`. Salir `NOT_RUN` bloqueaba el frente por una capa que no
emite veredicto — y dejaba al panel mintiendo sobre el fichero.

Medido en el golden: `seed_colision` pasa de `NOT_RUN` en **2167** ventanas a **1790**,
que son exactamente las no escaneables. Las 377 que sí lo son cierran ahora a nivel
núcleo.

### Lo que no se relaja, y es la mitad que importa

El `PASS` **no se presenta como «limpio contra todo»**. Dice que el núcleo corrió y está
limpio y que la capa de aviso **no se ejecutó**, así que de las colisiones restantes no se
sabe cuáles superan el umbral. Y va además como **campo** (`ampliada_sin_correr`), no sólo
como una frase: quien lee el estado puede saberlo sin parsear el motivo. Un `PASS` mudo
aquí sería el «Alu 0 %».

### Y el par que lo destapó

Esta contradicción llevaba puesta desde que existen las dos capas, y sólo se vio al
cerrar la errata nº 60: mientras `seed` decía `NO_APLICA` y `seed_colision` decía
`NOT_RUN`, **nada bloqueaba y nadie contestaba**, así que el `NOT_RUN` de más no tenía
consecuencia visible. Arreglar el estado de una columna hizo visible el error de la otra
— que es el argumento entero de por qué un estado tiene que decir la verdad aunque «no
cambie nada».

---

## 62 — El modal pedía la procedencia de un FICHERO en cada corrida, y el depósito la tenía delante

**Reportado el 2026-09-02 con el modal abierto**, y con las dos mitades separadas:

> El modal de carga de off-targets no ve el depósito… Y además pide los seis campos de
> procedencia —source, assembly, table, table_date, representative, version— que ya
> declaré al subir el fichero.

Las dos mitades son el mismo fallo visto desde dos sitios, y la frase que lo ordena vino
después:

> está pidiendo procedencia de un fichero, no de una corrida. La procedencia del fichero
> pertenece al depósito; la de la corrida es fecha, quién y parámetros.

### Qué hacía

`_modal_offtarget` pintaba seis `text_input` y un `file_uploader` **sin mirar el
directorio de referencia**. Así que con `transcriptoma_3utr.fa` ya dentro:

- pedía volver a soltarlo, y
- pedía volver a teclear su ensamblaje, su tabla, su fecha y su criterio de
  representante.

El de BLAST hacía lo mismo con la base: **Base**, **Versión** y **md5 de la base**, tres
campos tecleados a mano con la línea del manifiesto delante. Y ese md5 no es decorativo:
es el que `insumos.obsoleta` compara para marcar una corrida OBSOLETA cuando el fichero
se reemplaza. Tecleado, no ata nada.

### Por qué es peor que teclear de más

**Son dos copias del mismo dato.** La del depósito la escribió quien subió el fichero; la
del modal la teclea quien corre. Nada las ata, así que cuando divergen ninguna de las dos
dice cuál manda — y el veredicto se guarda con la que se tecleó. Es la errata nº 28 otra
vez: *un dato transcrito en lugar de derivado no se desincroniza en un sitio, se
desincroniza en todos los que lo copiaron*.

Y hay un modo peor, que es el que lo hace urgente: **quien no se acuerda del ensamblaje se
lo inventa**. `mm39` es plausible, `mm10` también, y el conteo sale con la **forma
correcta** sobre el genoma equivocado. Sin ningún error.

### Lo que se ha hecho

**1. La procedencia de la tabla es del FICHERO y va al manifiesto**, cuatro columnas
nuevas —`ensamblaje`, `tabla`, `fecha_tabla`, `representante`—. Los otros tres campos de
`offtarget.Provenance` ya los tenía: `source` es el origen, `version` sale de la fecha
—la misma regla que usa `resources`, no otra— y `md5` se calcula del fichero.

**2. Se piden UNA VEZ, al subir, y son OBLIGATORIAS**, con la condición escrita con la
que se pidieron: *si `Provenance` las exige para dar veredicto, un fichero sin ellas no
puede entrar al depósito y bloquear el frente tres pantallas después sin decir por qué*.
`deposito.PROVENANCE_REQUIRED` declara en qué roles hacen falta —hoy uno, el catálogo de
3'UTR— y el rechazo va **donde entra el fichero**, antes de escribir nada, nombrando los
campos que faltan. Una casilla en blanco cuenta como no puesta.

Y **no son obligatorias en todos**: un casete de AAV no sale de ninguna tabla, así que
ahí la columna vacía es la VERDAD y pedirla sería inventarse un hueco.

**3. La lectura del depósito sale de UN SOLO SITIO**, como se pidió. `deposito.read_deposit`
es el único que abre el manifiesto para esto, `presentation.deposit_file` monta la fila y
`deposit_for_run` la repite por cada insumo de esa corrida. **Qué ficheros consume cada
corrida ya estaba declarado por ROL en `insumos.CONSUMIDOS`** —la tabla que existe para
que un quinto modal no se quede fuera—, así que esto la usa en vez de repetirla.

**4. Los cuatro modales**, que es lo que se pidió comprobar. Los tres que consumen un
fichero lo enseñan en vez de pedirlo; el de empalme sale **vacío y diciendo por qué**
(`insumos.POR_QUE_EMPALME_NO_TIENE`: monta el cassette con piezas del paquete). Vacío es
una decisión tomada; ausente sería una que nadie miró.

**5. La subida sólo se ofrece si el fichero NO está**, y lo decide `presentation`, no la
página (regla 6). Cuando falta, el modal la ofrece **con sus casillas de procedencia** —
las mismas del gestor, sacadas de la misma declaración— y el fichero queda registrado
para que la corrida siguiente ya no pregunte nada.

### Lo que salió al escribirlo, y no estaba en el reporte

`DepositFile.stale_md5`: el fichero que hay en el directorio puede no ser el que su línea
del manifiesto registra. No aborta —quien aborta es el cargador, en cada corrida— pero
**se dice**, porque la procedencia que se adjuntaría al veredicto sería la de OTRO
fichero, con la forma correcta. Queda declarado en `data/guardias.toml`, en
`[solo_informan]`, al lado de `manifest.check_directory`, que es el mismo criterio un piso
más abajo.

---

## 63 — El guardia del truncamiento: la clase de fallo tiene mecanismo aunque el caso no se reprodujera

**Reportado el 2026-09-02**: un heptámero de **seis** caracteres en la columna
`heptamero` del CSV descargable, con la petición de decir si compara 2-7 y lo etiqueta
2-8, o compara 2-8 y enseña seis. Se midieron **los tres productores** del heptámero y
los tres dan siete. **El caso no se reprodujo y no se le asigna causa**: decir «era esto»
sin haberlo comprobado es el principio nº 3, que este proyecto ya ha pagado cuatro veces.

Lo que sí se decidió —y es la parte que vale— es que **la clase de fallo tenga guardia**,
con el argumento con el que se pidió:

> un heptámero truncado a seis es una seed válida y distinta. Es la familia del Alu 0 %.

Ese es exactamente el motivo: **no da ningún error**. El conteo que sale al lado de un
heptámero truncado es un número correcto **para otra pregunta**, así que la tabla se lee
igual y lo que describe es otra cosa.

### Qué comprueba, y por qué se corren las tablas en vez de leer el fuente

`tools/auditar_truncamiento.py`, dentro de `npm run check:shmir`. **Guardia, no
trinquete**: el número correcto es cero.

Un barrido de AST buscando rebanadas no distingue `guia[:8]` de una etiqueta cortada, y
lo que importa no es el código sino **lo que sale**. Así que el auditor tila el 3'UTR
murino de verdad, monta las cinco tablas que se exportan —incluida la comparativa que se
descarga— y las mira. La sexta, la del modal de colisión de seed, la cubre
`tests/test_ninguna_tabla_TRUNCA_una_secuencia.py` con el mismo criterio: necesita barrer
`mature.fa` y no se le pone eso a cada `check:shmir`.

### Las dos decisiones que lo hacen aplicable

**La columna de secuencia NO se declara por su nombre: se DERIVA del contenido** —todas
sus celdas no vacías con alfabeto de ácidos nucleicos y al menos 6 nt—, así que una
columna nueva entra sola. Declararlas a mano habría reproducido el fallo original un
nivel más arriba: la tabla sólo cubriría las columnas de las que alguien se acordó.

**Y lo que sí hay que declarar es de dónde sale su longitud esperada**: una columna de
secuencia sin esa declaración **aborta**. La longitud se deriva del objeto que produjo la
tabla —la ventana de la corrida, la longitud de la guía, el hexámero de polyA— y **nunca
se escribe**: poner un `7` para el heptámero sería afirmar que la ventana es 2-8, que es
justo lo que hay que comprobar (principio nº 13). Con `2-7` mide seis **y eso es
correcto**, y el guardia lo sabe porque compara contra lo que esa corrida declara.

### Lo que encontró al estrenarse

**Ninguna tabla trunca nada** — que confirma la medida de los tres productores, ahora con
mecanismo detrás. Lo que sí apareció son **dos columnas de secuencia que no miraba nadie**:
`feat_seed` (la feature de SplashRNA, la misma ventana 2-8) y `polyA_hexamero`, las dos en
la tabla comparativa que se descarga. No estaban mal; estaban sin nadie mirándolas, que es
la situación en la que este fallo aparece.

Y lleva **control adversario**: sin él, «ninguna tabla trunca» y «el guardia no mira nada»
darían el mismo verde — la lección del `verify()` de la errata nº 29.

---

## 64 — Los proyectos no se podían ni renombrar ni borrar, y la fecha se tecleaba

**Pedido el 2026-09-02**: «mejorar un poco el sistema para guardar proyectos. En especial
para ir borrando los antiguos y que me permita editar el nombre y añademe un calendario
(con Hoy) para añadir la fecha».

No es una errata de cálculo: es una capa que se construyó para que un veredicto
sobreviviera a la app y **no se podía mantener**. Un proyecto entraba y ya no salía.

### Lo que había

Un desplegable con los slugs, un `text_input` para la fecha, y nada más. Sin forma de
borrar, sin forma de renombrar, y sin ver cuál estaba muerto: la etiqueta era el slug
pelado, así que `prueba`, `prueba2` y `prueba_bueno` se distinguían de memoria.

### Las tres, y por qué ninguna es trivial

**BORRAR es lo único de la app que DESTRUYE un registro**, y no se parece a borrar un
fichero de referencia: aquél se vuelve a bajar de UCSC, y una corrida de BLAST son horas
de cómputo **fuera de esta app** que nadie va a repetir. Así que:

- va con el **plan delante** (`project_delete_plan`), que cuenta los registros por tipo y
  su rango de fechas, y dice con esas palabras que **no se puede deshacer y no se puede
  volver a calcular aquí**;
- un proyecto **vacío** y uno con doce corridas **no suenan igual**: el primero no pierde
  nada y decirlo con el mismo aviso rojo convierte el aviso en ruido;
- y lleva la **descarga al lado** (`project_export`), que es el mismo criterio de
  `gestor.download`: lo que hace que el registro sea tuyo y no de la app. Salen las **dos
  piezas** —`proyecto.json` y `registro.jsonl`—, porque un log de veredictos sin saber
  sobre qué secuencia son no dice nada.

**Y el panel de gestión va ANTES de abrir el proyecto, no dentro.** No es colocación:
`project_open` comprueba el md5 de la secuencia cargada, así que **un proyecto de otra
entrada NO se puede abrir** — y si borrar colgara de tenerlo abierto, ese proyecto sería
imposible de quitar. Que es justo el que sobra. Por la misma razón, ni el plan ni el
borrado pasan por `verify()`: **un log con la cadena rota tiene que poder descargarse y
borrarse**; lo que exige la cadena sana es escribir en él.

**RENOMBRAR cambia el nombre VISIBLE y no el slug.** El slug nombra la carpeta, viaja en
los mensajes y es lo que se teclea para reabrir: cambiarlo dejaría sin abrir cualquier
referencia anterior. `Project.title` es un campo nuevo con valor por defecto, así que un
`proyecto.json` de antes se sigue abriendo y enseña el slug.

Y **el cambio se APUNTA en el log**, como un `nota` fechado. No es un ajuste: un proyecto
que ayer se llamaba otra cosa es justo lo que hace irreconocible un registro de hace un
año, que es para lo que este log existe. Renombrar al mismo nombre **no escribe nada** —
un `nota` por clic ensucia lo que se lee para saber qué pasó.

**LA FECHA sale de un calendario, con hoy puesto.** Una fecha tecleada se equivoca en
silencio —`2026-09-02` y `2026-09-20` se parecen— y ya produjo una salida falsa: ante el
`run_id` repetido de la errata nº 48, la tentación era cambiar la fecha para que entrara.

Con una distinción que **no se colapsa**: las fechas de algo que pasa AHORA —crear el
proyecto, guardar una corrida, guardar la selección— vienen con **hoy** puesto, porque
ésa es la verdad; las de un fichero que se **descargó otro día** —los dos huecos del
gestor y el del modal de off-targets— vienen **vacías**, porque poner hoy sería
inventarse el dato. Es la misma regla por la que `date_text(None)` devuelve vacío y no
la fecha de hoy.

El formato lo pone `presentation.date_text` y no la página (regla 6), y **una tupla
aborta**: `st.date_input` devuelve dos fechas en modo rango, y un rango convertido a texto
entra en el log con la forma correcta y sin significar nada.

### Lo que salió al hacerlo

`_hoy()` vivía **en la página** —formato en la página, regla 6— y su docstring decía que
las fechas de procedencia «se teclean, y ahí no hay ningún valor por defecto a propósito».
Era cierto cuando se escribió y dejó de serlo con este cambio: el **principio nº 11**, la
prosa que se queda atrás. Se ha ido con la función, y lo que queda es una comprobación
mecánica — la página no puede convertir ninguna fecha por su cuenta, y hay test de que no
queda ni un `isoformat()`, ni un `strftime(`, ni un `text_input` de fecha.

---

## 65 — El plásmido de SGEP no tenía hueco, y su comprobación leía coordenadas escritas

**Pedido el 2026-09-02**: «El plásmido de SGEP #111170 no tiene hueco en el panel de
referencia… Hazlo fichero de primera clase, como los demás: rol propio, hueco en el
gestor, ficha de obtención, validación al subir y md5 en el manifiesto. Formato .gb o
.dna, **y que extraiga los contextos por la anotación, no por las coordenadas
declaradas**… Y de paso: audita si queda algún dato más en esa situación».

### Lo segundo es lo que pesa

`gblock.verify_contexts_against_plasmid` leía el plásmido en `1739-1758` y `1856-1875`
—números **escritos**— y comparaba lo que hubiera ahí con los contextos del módulo. Eso
comprueba mucho menos de lo que parece:

- con las coordenadas corridas, **la comprobación fallaría contra un plásmido correcto**,
  y el arreglo obvio —moverlas hasta que cuadren— la dejaría **pasando siempre**;
- y un número escrito **no puede validar el fichero del que salió** (principio nº 13).

Ahora hay **dos vías y tienen que coincidir**. El ancla es la **anotación del propio
fichero** —`ncRNA` «miR-30a loop», que el registro de andamios ya declaraba en
`loop_feature`— y el andamio se localiza **por secuencia** a su alrededor, exigiendo que
aparezca **una sola vez** y que la anotación caiga **dentro** de lo localizado. Los
contextos son lo que flanquea al 97-mero, con la longitud del contexto del módulo — que
es la pregunta de verdad: *¿lo que llevamos es lo nativo de SGEP?*

**Y el resultado confirma lo que estaba escrito, ahora como consecuencia**: el andamio cae
en `1759-1855` —**97 nt exactos**, que es el 97-mero— y los contextos en `1739-1758` y
`1856-1875`. Los mismos números. La diferencia es que ya no son una entrada: si mañana
llega otro export, se derivan otra vez.

**Con sus dos controles adversarios**, porque sin ellos «pasa» y «no mira nada» dan el
mismo verde: se cambia **una base** del contexto sobre el fichero real y aborta; se
**mueve la anotación** del loop y aborta diciendo que no cae dentro. Lo segundo es lo que
impide que el ancla sea decorativa.

### Y el fixture que había era el problema descrito en el propio registro

Los tests de esa comprobación montaban **un plásmido de relleno de A's (o de N's) con los
dos contextos metidos en sus coordenadas declaradas**. El CLAUDE.md ya lo decía con esas
palabras —«el test los probaba contra un plásmido sintético: **el comprobador, no las
coordenadas**»— y seguía ahí. Con la derivación ni siquiera es construible: un relleno no
tiene bloque FEATURES del que anclarse. Los tres ficheros que lo copiaban usan ahora el
plásmido de verdad, desde `tests/plasmido_sgep.py`, que es **un solo sitio**.

### Fichero de primera clase

Rol propio `plasmido_andamio`, hueco en el gestor, ficha de obtención, validación al subir
—que es **la comprobación entera**, no una validación ligera: un fichero que pasara aquí y
fallara al pedir el gBlock sería peor que no validarlo— y su md5 en el manifiesto.

**No lleva sufijo de especie, y no es un descuido**: SGEP es el vector del **ANDAMIO**, no
de ningún organismo. Es el único fichero del depósito del que eso es cierto — justo al
revés que `aav_casete.fa`, que es pAAV con PrP **murino** y por eso sí lo lleva. Se ve en
el contador: con conejo, los frentes cerrables pasan de 1 a 2, y el segundo es éste.

El contador de frentes pasa de **7 a 8**.

### La auditoría que se pidió de paso, y lo que encontró

De las 12 piezas de `blocks.PIECES`, sólo las dos de SGEP declaraban coordenadas. Lo que
apareció al mirar las otras diez es de otra clase: **diez dicen de dónde vienen y nadie lo
estaba comprobando**, teniendo el fichero en el depósito. `audit_pieces_against_plasmids`
lo mide, y sale en `npm run check:shmir` como INFORME — aquí el número correcto **no es
cero**:

| pieza | estado |
|---|---|
| `MluI`, `MVM5`, `MVM3`, `AgeI` | **CONFIRMADA**: únicas en `aav_casete.fa` |
| `exon5`, `exon3` | **CONFIRMADA_EN_POSICIÓN**: miden 5 nt y salen 3 y 8 veces, así que a solas no identifican nada; se exige que estén pegadas a su MVM |
| `NheI`, `SacI` | **NO ESTÁN** en el receptor depositado |
| `espaciador5`, `espaciador3` | `NO_APLICA`: son de novo |
| `contexto5`, `contexto3` | **CONFIRMADA** contra SGEP, ahora por derivación |

**El hallazgo son `NheI` y `SacI`**: su procedencia decía «plásmido receptor» y el
receptor que hay **no las contiene**. Y es coherente —el parental lleva el intrón vacío,
sin sitio de clonaje—, así que lo que estaba mal no eran las secuencias, que son las
dianas canónicas de las dos enzimas: era **la frase**, que afirmaba un origen que ningún
fichero sostiene. Corregida. Y se las **sigue buscando** aunque ya no lo afirmen: si al
corregir la frase dejaran de mirarse, el informe perdería justo la medida que lo motivó —
mismo criterio que un frente CERRADO que sigue saliendo en el informe.

### Sobre la sospecha del andamio

Era razonable y la respuesta es que **no es el mismo caso**. El andamio de miR-E tiene una
**publicación** detrás, así que no se DERIVA del plásmido —eso sería elegir coordenadas
por nuestra cuenta, que es exactamente lo que `mir30_original` se niega a hacer— sino que
se **CONTRASTA** con él, y eso es lo que ahora corre: sus tres piezas se localizan por
secuencia en el fichero cada vez que se comprueba un contexto.

### Un fallo del corrector de tildes, encontrado al escribir esto

`check_tildes` marcó «esta medida es lo que lo corrigió» —demostrativo + sustantivo— como
si fuera el verbo. `"medida"` estaba en `_TRAS_ESTA`, la lista cerrada de palabras tras
las que `esta` es verbo… **y el comentario tres líneas más arriba la nombra como ejemplo
de lo que NO hay que meter ahí**: «esta corrida», «esta medida», «esta entrada» tienen
forma de participio y aquí son sustantivos.

Medido antes de quitarla: en literales de prosa **no había ni un solo «esta medida» como
verbo**, así que la entrada nunca acertó y sólo podía fallar. `"medido"` se queda —«el APA
esta medido» sí aparece— y no es incoherencia: son dos palabras con dos repartos distintos
en este corpus, que es justo lo que una lista **cerrada y leída** puede decir y una regla
de participios no.

---

## 66 — La copia de seguridad existía como posibilidad, no como acción

**Pedido el 2026-09-02**, con el motivo delante y mejor formulado de lo que estaba en el
código:

> El volumen es la única copia de todo lo que pone un frente en verde, y con él se iría la
> procedencia. **Que la copia de seguridad sea un botón, no una tarea de disciplina.**

Y es exacto. Los ficheros que cierran frentes —`mature.fa`, `aav_casete.fa`,
`addgene_111170.gb`, `transcriptoma_3utr.fa`, `refseq_rna.fa`— **no van en git**: no
entran en un repositorio, así que viven **sólo** en el volumen. Con ellos se iría el
`manifest.tsv` de trabajo, que es donde están su md5, su fecha, su origen y —desde ayer—
su ensamblaje y su tabla. O sea **la procedencia**, que es lo único que hace auditable un
veredicto dentro de un año.

Lo que había: un botón «Descargar» **por fichero**, y el manifiesto **sin ninguno**. Ocho
descargas de una en una y la pieza que las explica sin forma de bajarla. Eso no es una
copia de seguridad: es la posibilidad de hacerla, que es otra cosa — y depende de que
alguien se acuerde, que es justo lo que la frase del reporte nombra.

### Lo que entra

`gestor.export_all` monta un zip con **todo lo que el volumen tiene y git no puede
llevar**: los ficheros del depósito con su `manifest.tsv`, los logs de cada proyecto —las
**dos** piezas, `proyecto.json` y `registro.jsonl`— y la biblioteca del paso 2, que estaba
en la misma situación y no se pidió: incluirla es lo coherente con el motivo, y dejarla
fuera en silencio habría sido entregar una «copia de todo» que no lo es.

**Con un LEEME dentro**, y no es adorno: un zip sin nada que lo explique es un montón de
ficheros dentro de un año. Lleva de dónde salió cada cosa —las rutas reales—, el
**inventario con md5** para poder comprobarlo **sin la app**, cómo se restaura (que
importa, porque el directorio de trabajo se declara por variable de entorno) y lo que esta
copia **no** es: una foto del día, que **no se actualiza sola**.

### Las dos decisiones que no son obvias

**Si un fichero no se puede leer, ABORTA.** Media copia que parece completa es peor que
ninguna, y aquí nadie va a abrir el zip hasta el día que lo necesite. Mismo criterio que
`trabajo.seed_reference_dir`, que aborta antes que dejar un directorio incompleto con
pinta de completo. Lo mismo con un proyecto al que le falte su log: una entrada sin
registro no dice nada, y guardar sólo una mitad sería peor que no guardar.

**El zip se monta al PULSAR, no al pintar.** `st.download_button` necesita los datos ya
hechos, así que ponerlo directo significaría comprimir en **cada repintado** de la página
— con el transcriptoma dentro, 84 MB por clic. Es la lección de la errata nº 59. Va detrás
de un botón que lo prepara, y el inventario —cuántos ficheros, cuánto pesan— se calcula
con `stat`, sin comprimir nada, para que se sepa **antes** de pulsar.

Medido sobre el depósito real: 27 ficheros, 5,5 MB sin comprimir → **1,1 MB** en el zip,
28 entradas, integridad comprobada.

### Y un control adversario que no corría

El primero que escribí hacía `chmod 000` sobre un fichero para probar que la copia aborta…
y **como root eso no impide leer**, así que el test se **saltaba**. Un control que no corre
en el entorno donde se corren los tests es exactamente lo que este proyecto no acepta —es
la familia del `verify()` de la errata nº 29—. Sustituido por dos deterministas: la pieza
que decide contra una ruta que de verdad no existe, y un proyecto al que se le borra el
log.

También cayó ahí un **rojo falso por anclar un guardia a la prosa**: el test que comprueba
que el botón de preparar va antes del de descargar encontraba `st.download_button` **dentro
del docstring** que explica precisamente por qué va detrás. Es la errata nº 54 con el signo
cambiado, y el arreglo es el mismo: se mira el código, no el texto que lo explica.

---

## 67 — El alcance de una corrida no era elegible, y `n_candidates` mentía

**Pedido el 2026-09-02**: cómo analizar todos los candidatos en vez de diez. La pregunta
destapó tres cosas, y la más importante es la distinción que puso quien la hizo:

> El panel sigue en 10 con sus cuotas. **Lo que cambia es a cuántos se pregunta, no
> cuántos se eligen.** Bajar el espaciado es otra decisión, con su coste en independencia
> entre apuestas, y merece discutirse aparte y por escrito.

### 1. `n_candidates` no era la palanca, y encima mentía

Medido: pides 20 y salen **14**; pides 50 y salen **14**; pides 500 y salen **14**. No es
un límite del código — es el **espaciado de 50 nt**, que sólo deja catorce sitios que lo
respeten en 1242 nt. Con 22 nt salen 25; con 1 nt salen los 86.

Y lo peor no es el tope: es que **la página no lo decía**. El núcleo lo apuntaba desde
siempre en `Selection.notes` —«se pedían 50 candidatos y sólo salen 14: no hay más sitios
elegibles que respeten el espaciado de 50 nt»— y **sólo lo emitía el informe de texto del
CLI**. Quien sube el número en la barra lateral veía la misma tabla y concluía, con razón,
que la app no le hace caso. Es el **principio nº 23**: dos artefactos leen el mismo estado
y sólo uno lo cuenta. La nota se pinta ahora junto al control que la produce.

### 2. El alcance, por modal, y en SITIOS

`presentation.scope_rows` / `scope_starts`: dos opciones —el panel (10) o **todos los
sitios elegibles (86)**— por modal y no globales, porque el coste no se parece.

**Sitios, no ventanas**, y el motivo lo dio quien lo pidió: ventanas solapadas de la misma
región comparten casi toda su secuencia, así que preguntar por las 270 daría el mismo
resultado repetido y **ensuciaría cualquier recuento**. El representante de cada sitio es
`Site.best`, que es el criterio con el que la selección ya ordena — elegir otro sería una
segunda definición de «el mejor».

**Y no toca la selección**: el panel sigue siendo de 10 con sus cuotas, y hay test de que
pedir el alcance grande no lo cambia. El panel es además **subconjunto** del alcance
grande, así que cambiar de alcance no pierde candidatos ya consultados.

### 3. El coste, con lo NO medido dicho

`COSTE_POR_ALCANCE`, una entrada por tipo de corrida, cruzada contra `insumos.CONSUMIDOS`
para que un quinto modal sin coste declarado falle en la suite:

- **BLAST** — no cuesta nada aquí: la corrida es fuera, y mandar 172 secuencias en un solo
  BLAST cuesta lo mismo que mandar 20. Lo único que crece es el FASTA.
- **Seed** — medido y barato: subcadena contra `mature.fa`, ya cargado.
- **Off-targets** — **NO medido**, y la etiqueta lo dice: el índice se construye una vez,
  pero la nula son 10.000 sorteos **por consulta**.
- **Empalme** — **NO medido**: cada par candidato × intrón se **pliega**, y el plegado es
  lo caro del pipeline.

Un número inventado es peor que «no lo sé», porque quien lo lee lo trata como una medida.
Con la lección de los cuatro minutos por clic delante (errata nº 59).

**Y el empalme no puede derivar su recuento**: su unidad es el par candidato × intrón, y
cuántos intrones se consultan lo elige quien corre, en ese mismo modal. Derivarlo de «los
que tienen secuencia» anunciaría 172 consultas cuando se van a hacer 86, así que
`scope_rows` **exige** que se le digan y aborta sin ellos. Por eso el selector va, en ese
modal, **después** del multiselect de intrones.

### La casilla inerte de BLAST

El modal tenía **«Todos»** y **«Sólo los del panel»**. La segunda **no filtraba nada**: las
filas salían ya sólo del panel y cada una llevaba `"panel": True` **escrito**, así que la
condición nunca descartaba ninguna. El propio comentario lo decía —«existe para cuando se
listen más»—: se dejó preparada la mitad de arriba y nunca llegó la de abajo.

Es la **errata nº 32** otra vez: un control que no se distingue de uno que funciona. Se ha
ido, y lo que hacía falta de verdad —preguntar por más candidatos— es el alcance. `panel`
pasa a **derivarse** (`choice.start in del_panel`), que es lo que lo hace significar algo:
con el alcance grande hay filas que no son del panel, y esa marca es lo único que las
distingue en pantalla.

### Un detalle que salió al escribirlo

La primera versión de la etiqueta pegaba una «s» al nombre de la unidad y salía **«par
candidato × intróns»** y «consulta de seeds». Derivar un plural pegando una letra es
derivar algo que no es derivable: cada unidad declara su singular y su plural.

## 68 — Un frente que cierra un FICHERO se decidía sobre 2170 ventanas y uno que cierra una CORRIDA sobre el panel

**Reportado con el export delante (2026-09-03).** El contador decía «2 de 7
comprobaciones hechas» y sólo una tarjeta estaba en verde, mientras los diez candidatos
del panel salían en el export con:

```
especificidad   PASS
transgen        PASS
seed_colision   PASS
seed            SUSTITUIDO
```

En gris, con su fichero cargado y su columna en `PASS`: «¿Apagaría también el propio
tratamiento?» (`transgen`, con `aav_casete.fa`) y «¿Se confunde con un microARN de la
propia célula?» (`seed_colision`, con `mature.fa`).

Y quien lo reportó dio además el diagnóstico, que era el correcto: es el desacuerdo de
`candidate_rows` un consumidor más allá; los frentes que cierran SIN corrida no llegan a
las tarjetas, y los que cierran por corrida sí.

### La causa: DOS reglas para la misma pregunta

`blocking_fronts` decide qué frentes están abiertos con `ReportSelection.not_run_filters`,
que cuenta los `NOT_RUN` sobre **las 2170 ventanas tiladas**. Medido sobre la corrida real
del ratón con el depósito conectado:

```
not_run_filters: {'especificidad': 2170, 'seed': 1790, 'seed_colision': 1790,
                  'transgen': 1790, 'GC': 66, 'asimetria': 66, 'homopolimero': 66}
```

**1790 de esas ventanas ni llegan a los filtros con recurso porque ya cayeron antes.** Un
`NOT_RUN` de una ventana descartada no es una laguna de nada: nadie iba a preguntarle.

Un frente cerrado por CORRIDA, en cambio, ya se decidía **sobre el panel** —
`run_coverage`, con la regla de que sólo cierra si lo cubre entero. O sea que la misma
pregunta tenía dos unidades según de dónde viniera la respuesta, y por eso la tarjeta y
la columna podían discrepar.

### El arreglo no es la tarjeta: es que las dos salgan del mismo sitio

`presentation.panel_states_by_front` es ahora **el único sitio donde se decide si un
frente está contestado**. Junta las dos mitades para cada candidato del panel:

1. lo que dice la celda de la tabla, **letra por letra** — `_filter_columns` pasado por
   `_with_stores`, la misma expresión que pinta `candidate_rows`, así que no pueden
   discrepar por construcción y no por coincidencia;
2. lo que dicen los almacenes, que además **marca el origen**.

Y entra por `blocking_fronts`, que tiene seis llamadores: es la lección de la errata
nº 54, que se cobró dos tandas arreglando consumidores de uno en uno.

Con eso, las tarjetas del ratón pasan de **2 de 7** a **4 de 8**, y `especificidad` sigue
en gris —`refseq_rna.fa` no está— que es el control adversario: si todo saliera HECHO,
esto no distinguiría un frente cerrado de una comprobación que no comprueba.

### Tres cosas más que salieron al escribirlo

- **`SUSTITUIDO` y `NO_APLICA` contaban como laguna.** `ESTADOS_QUE_RESPONDEN` era
  `("PASS", "FAIL")` escrito a mano. El filtro `seed` sale `SUSTITUIDO` en todo el panel
  con `mature.fa` cargado —y `check_substitution` impide que exista con su sustituto en
  `NOT_RUN`—, así que contarlo como hueco dejaba abierto un frente ya contestado. Ahora se
  declara **lo que es una laguna** y lo demás se DERIVA de `FilterState` (principio nº 13):
  una lista de «los que responden» escrita a mano deja fuera al estado número siete.
- **Y UN FALLO LATENTE que este reporte destapó sin ser su causa**:
  `store_states_by_front` **no contestaba nada de los frentes POR HEBRA**. Preguntaba al
  almacén con el nombre pelado del frente, y `_store_state` devuelve `None` para un frente
  por hebra sin hebra —a propósito: fundir las dos daría por buena la de la pasajera con
  el estado de la guía—. O sea que una corrida de seed o de off-targets que cubriera el
  panel entero **no cerraba su frente nunca**; sólo la de BLAST podía. Coincide
  exactamente con lo observado —«la de especificidad es la única verde»— y **no era eso**.
  Un frente por hebra se contesta con las dos, o no se contesta.
- **Dos causas, dos textos.** «CERRADO por corrida guardada» sobre un frente que nadie ha
  corrido manda a buscar en el registro del proyecto, donde no hay nada. El motivo se
  deriva del ORIGEN: «CERRADO con lo que hay en el depósito» / «por corrida guardada» /
  las dos. Y la cobertura parcial también: «EL FICHERO ESTÁ Y NO ALCANZA A TODO EL PANEL»
  no es «HAY CORRIDA, PERO NO CUBRE EL PANEL».

### Y dos nombres que dejaron de ser ciertos

`fronts_closed_by_runs` pasa a `fronts_closed_over_panel` y `blocking_fronts(closed_by_runs=)`
a `closed_by_panel=`. Los dos eran ciertos mientras sólo llegaban corridas y dejaron de
serlo en cuanto entraron los frentes que cierra un fichero. Se renombran en vez de
ampliarles el significado: principio nº 27.

### Los dos guardias del proyecto lo cazaron mientras se escribía

- el que exige que **todo llamador de `_filter_columns` pase por `_with_stores`** señaló
  la primera versión de `panel_states_by_front`. Tenía razón, y al hacerle caso los
  estados quedaron **idénticos a los de la celda por construcción**, que es mejor que lo
  que yo había escrito;
- el de **símbolos citados** rechazó dos docstrings nuevos que nombraban
  `not_run_filters` como si fuera un símbolo del módulo `selection`: es un atributo de
  `ReportSelection`.

## 69 — Los tres botones del informe se llamaban como el fichero, así que la sección no se leía como una descarga

**Reportado (2026-09-03)**: «No encuentro dónde se descarga el informe. Existe la sección
"Informe — parcial o completo, en cualquier momento" y un bloque "Descargas", pero no veo
el botón que baja el .docx o el .pdf.»

**Los botones estaban**, los tres, en su sitio y funcionando. Lo que fallaba es que su
etiqueta era el **nombre del fichero** —`raton_informe_parcial.docx`— así que la sección se
leía como una lista de ficheros sueltos y no como «aquí se descarga el informe». Es la
misma lección que ya estaba escrita para `BUTTON_DESIGN` («Diseñar» pasó a «Buscar
candidatos»): **un botón se llama por lo que HACE**, y estaba aplicada a un botón y no a
los otros tres.

Ahora las etiquetas las pone `presentation.INFORME_LABELS` (regla 6): «Descargar el
informe en Word (.docx)», «Descargar el informe en PDF», «Descargar el texto sin maquetar
(.md)». El nombre del fichero **no se pierde** —va debajo, en la ayuda—, porque es lo que
luego hay que buscar en la carpeta de Descargas.

Y el **orden pasa a ser deliberado**: Word, PDF y el markdown el último. Los dos primeros
son los que se mandan y se imprimen; el markdown es la FUENTE, para discutir una frase sin
maquetar. El orden anterior era el de escritura y dejaba el `.pdf` al final sin ninguna
razón. El test que lo fijaba **transcribía** la lista, así que sólo comprobaba que nadie
la tocara; ahora comprueba además la invariante que importa: **la etiqueta de un botón no
puede ser el nombre de su fichero**.

## 70 — `carga_seed` salía desnuda: la nula y los controles se calculaban en el modal y no llegaban al export

**Reportado (2026-09-03)**, y con la observación que lo motiva: «carga_seed es la primera
columna que discrimina de verdad — de 1.054 a 19.020, factor 18 entre el mejor y el peor.
Pero le falta el percentil contra la nula por permutación y los controles de miR-124,
miR-9 y let-7: sin ellos, 19.020 no se puede interpretar. Estaba en el diseño del modal y
no aparece en el export.»

Es la regla de redacción del propio proyecto —**toda cifra comparativa con su
referencia**— y era la única columna que seguía saliendo sin ella. Y el principio nº 23
otra vez: la nula por permutación y los controles **se calculan** en el modal de carga de
off-targets y se guardan en el registro del proyecto; lo que faltaba es que llegaran al
artefacto que se lee.

### La decisión que hay que dejar escrita: NO hay percentil de `carga_seed`

`carga_seed` es un **total** —la suma de tres clases de sitio— y `offtarget.WHY_NOT_SUMMED`
prohíbe sumar las clases, porque la represión esperada de un 8mer y la de un 6mer no se
parecen en nada. Así que el percentil que se pidió **no se puede calcular sobre 19.020**:
sería el percentil de una cantidad que este proyecto tiene decidido que no se refiere a
nada. Emitirlo habría sido dar por bueno el total por la puerta de atrás.

Lo que sí se emite, y es lo que hace el trabajo que se pedía: **cada clase con su
percentil pegado**, en columnas `carga_8mer`, `carga_7mer-m8`, `carga_7mer-A1` y
`carga_6mer`, con la forma `12 (p97.5)`. Es la misma forma que `describe_sequence`
(«longitud y md5 JUNTOS»): una cifra comparativa no se separa nunca de su referencia,
porque quien copia una celda a un correo se lleva el número sin la cabecera.

### Y son DOS referencias, no una

- el **percentil contra la nula por permutación** dice si el número es raro *para esa
  composición de heptámero* — una nula uniforme declararía «cargada» a cualquier seed rica
  en A/T por pura composición;
- los **controles biológicos** (`miR-124-3p`, `miR-9-5p`, `let-7a-5p`) dan la **magnitud**:
  qué es «muchos sitios» en un cerebro de verdad.

Ninguna sustituye a la otra, y va escrito (`WHY_BOTH_REFERENCES`). Los controles **no
llevan percentil** a propósito: se calcularía contra la nula de su propia composición, así
que no sería comparable con el nuestro. Aportan magnitud, no posición.

### Nada se recalcula: se LEE de la corrida guardada

La nula son ≥10.000 sorteos por consulta sobre un índice de 8-meros construido en una
pasada por un fichero de 84 MB. Hacerlo en cada repintado de la página es exactamente la
errata nº 59. `presentation.seed_load_reference` lee lo que la corrida ya guardó — que
además es lo que garantiza que la tabla y el modal digan **el mismo número**: dos cálculos
del mismo suceso acaban discrepando.

Sin corrida guardada, las cuatro columnas van **vacías** —nunca a cero: no haber contado y
contar cero son cosas distintas— y el texto dice qué falta, dónde se consigue y por qué el
total solo no se puede leer. Sale en la página, y **entra en el informe descargable**, que
es el documento que defiende la selección.

### Un detalle que salió al escribirlo

`candidate_rows` se puede llamar **sin especie** —es el camino del CLI— y al derivar la
clave de consulta eso abortaba. Sin almacén no hay registro que consultar, así que tampoco
hay clave que derivar: el corte es explícito y no un `try`. Y el guardia de colisión de
columnas **transcribía** la lista de nombres; ahora la pide, para que la quinta clase de
sitio que se añada quede cubierta sin que nadie se acuerde.

## 71 — Los frentes POR HEBRA no contestaban nada: una dimensión entera del modelo, sin respuesta

Salió al arreglar la errata nº 68 y **no era su causa**: es un fallo aparte, latente, que
ese reporte destapó. Va con entrada propia a petición de quien lo reportó, y por lo que lo
distingue de las cinco veces anteriores del mismo patrón.

### Qué pasaba

`presentation.store_states_by_front` le preguntaba a cada almacén con el **nombre pelado
del frente**. Para `seed_colision` y `offtarget_seed` el veredicto es **por hebra**, y
`_store_state` devuelve `None` cuando se le pregunta por un frente por hebra **sin
decirle la hebra**. O sea:

> una corrida de colisión de seed o de carga de off-targets **no cerraba su frente nunca**,
> cubriera lo que cubriera el panel. Sólo BLAST podía — el único frente que no va por hebra.

Coincide exactamente con lo observado en el reporte —«la de especificidad es la única
verde, y es la única con corrida guardada»— y por eso pasó desapercibido: la explicación
que se veía era cierta y no era ésta.

### Las dos mitades eran correctas por separado

Ninguna de las dos piezas está mal mirada de cerca:

- que `_store_state` devuelva `None` sin hebra es **deliberado y sigue siendo lo
  correcto**: fundir las dos daría por buena la de la pasajera con el estado de la guía,
  que es justo lo que la ficha parte en dos filas para no hacer;
- que `store_states_by_front` pregunte por el nombre del frente es su clave natural.

Lo que estaba mal es la **junta**, y su producto era `None` — «los almacenes no dicen nada
de esto»—, indistinguible de «no hay corrida». Un valor que significa *no sé* leído como
*no hay*: la misma forma que la comparación de md5 de la errata nº 47, donde la salida
honesta de una comprobación que no podía ser cierta era exactamente la de una que sale
que no.

### La sexta vez del patrón, y la primera sobre una DIMENSIÓN

Trabajo escrito, probado y que no llega a donde tenía que llegar:

1. `masking.triple_motive_rows` — calculado y sin emitir en ninguna salida;
2. `intron_folding` — igual;
3. `store.save_*` — la capa de persistencia entera, sin llamador;
4. `page_run` — escrita para que la página no divergiera, y la página no la llamaba;
5. `site_table_rows` — la capacidad cableada y probada, y faltaba el `stores=` en la única
   llamada que se ejecuta (errata nº 51);
6. **ésta.**

Las cinco primeras dejaban **un artefacto** sin actualizar: un detalle que no salía, un eje
que no llegaba a la pantalla, cuatro modales que no guardaban. Ésta deja **un eje entero
del modelo sin contestar**, para todos sus frentes y para todos los candidatos a la vez. Y
por eso ninguna de las herramientas que ya hay podía verlo: la alcanzabilidad mira
símbolos sin llamador y aquí **las dos funciones tienen llamadores**; el golden lee lo que
se emite y aquí lo que se emitía era un `NOT_RUN` con la forma correcta.

### El mecanismo, y está medido que muerde

`tests/test_TODO_frente_con_almacen_se_puede_cerrar.py` comprueba la propiedad **para
todos los frentes declarados en `STORE_FOR_FRONT`**, no para el que se probó: si una
corrida contesta a todas las columnas de un frente en todo el panel, ese frente se cierra.
Las columnas se **derivan** de `por_hebra`, así que un cuarto almacén por hebra queda
cubierto sin que nadie se acuerde.

Con sus tres mitades adversarias, porque sin ellas «cierra» y «no mira nada» dan el mismo
verde: quitando **una columna** no se cierra, dejando **un candidato** sin cubrir tampoco,
y un frente por hebra preguntado **sin hebra** tiene que seguir devolviendo `None` — si
alguien lo «arreglara» ahí, la pasajera desaparecería de la tabla sin dar ningún error,
que es peor que el fallo que esto cerró.

**Comprobado que falla con el código de antes**: devolviendo `store_states_by_front` a
preguntar con el nombre pelado, el test rompe en los **dos** frentes por hebra
(`seed_colision` y `offtarget_seed`) y pasa con el arreglo. Un guardia sin prueba de que
muerde es la errata nº 29 otra vez.

### Y hay un caso hermano que SÍ estaba protegido

`empalme_sitios` también tiene una dimensión propia —su unidad es el par candidato ×
intrón— y **está declarado** en `FRONTS_WITHOUT_COLUMN` con el motivo escrito, para que
nadie le dé una columna por candidato y colapse justo lo que ese frente existe para
comparar. O sea: el proyecto ya tenía una dimensión declarada **y protegida**, y otra
declarada (`por_hebra`) **y no protegida**. Declararla no basta; hay que derivar de la
declaración cada consulta que la atraviesa. Eso es el principio nº 29.

## 72 — El proyecto guardaba el md5 de su entrada y no la entrada, así que reabrirlo obligaba a repetir el principio

**Pedido (2026-09-04)**: «si yo esto ya lo he hecho antes y lo tengo grabado en un
proyecto, por qué no me pregunta antes de nada, al principio... si digo que sí, elijo cuál
quiero abrir e inmediatamente me mostraría el resultado de la búsqueda de candidatos que
se guardó en el proyecto.»

**El orden estaba al revés y era lo de menos.** El panel de proyecto vivía en la barra
lateral y **después** de diseñar, así que para volver a ver lo de ayer había que repetir
hoy los tres pasos de la entrada. Pero al ir a moverlo salió que **no se podía**: el
proyecto no guardaba la secuencia.

### Lo que guardaba y lo que eso permite

`proyecto.json` tenía `sequence_md5` y `sequence_length`. Los dos sirven para **comprobar
una secuencia que ya tengas delante** —y de hecho para eso están, y bien: abrir un
proyecto con otra entrada se rechaza por ahí— pero **no** para recuperarla. O sea que
reabrir exigía volver a subir el mismo fichero, y el md5 sólo servía para decirte que te
habías equivocado de fichero.

Dicho de otra manera: la regla escrita de este proyecto —**«un veredicto tiene que
sobrevivir a la app que lo escribió»**— estaba a medias. Sobrevivía el veredicto y **no la
entrada sobre la que se emitió**. Un log de decisiones sobre una secuencia que no está no
se puede releer; a lo sumo se puede comprobar.

### Lo que se hace, y lo que NO

- La entrada se guarda **verbatim**, dentro de `proyecto.json`. **No** en un fichero
  hermano: así viaja con todo lo que ya trata el proyecto —la copia de seguridad, el
  listado, la apertura— y no hay un artefacto más del que alguien tenga que acordarse. Las
  dos piezas del proyecto siguen siendo dos.
- **El tilado NO se guarda.** Se vuelve a calcular al abrir, porque es determinista y
  cuesta 0,33 s. Guardar lo derivado daría dos definiciones del panel y ninguna que mande,
  que es lo que obligó a escribir `resolve.py`.
- **No se reconstruye nada.** Guardar una secuencia verbatim es lo contrario de
  reconstruirla: es la regla 1 por su lado bueno. Y del md5 de un proyecto viejo no sale
  la secuencia, así que ahí se dice qué falta y se pide como siempre
  (`PROJECT_WITHOUT_ENTRY`).

### Con guardia, porque `proyecto.json` es un fichero

Al abrir se recalcula el md5 de la secuencia guardada y se compara con el que el propio
fichero declara. Vive en un volumen y se edita entre sesiones; con la entrada cambiada a
mano, el panel saldría **con la forma correcta sobre otra secuencia** y no habría nada que
lo dijera. Es la misma disciplina que la cadena de md5 del log, sobre el otro fichero del
par, y está declarado en `guardias.toml`.

**Y el md5 lo calcula `reference.sequence_md5`.** `store.create` tenía su propio
`hashlib`, y `magnitudes.toml` ya lo anotaba con una condición: «si algún día se moviera,
delegaría». Hoy son dos los sitios que necesitan ese número —crear y abrir— así que el día
llegó: se delega y **se quita** el `hashlib` de `store`, en vez de añadir un tercero. Lo
señalaron los tres auditores del propio proyecto en cuanto entró el guardia nuevo.

### El paso 0, y cuándo NO se pinta

**Sin ningún proyecto guardado no pinta nada.** Una pregunta sin ninguna respuesta posible
es ruido delante de quien entra por primera vez, que es exactamente a quien esta pantalla
tiene que guiar.

Al retomar, los pasos 1 y 2 no se vuelven a preguntar —la especie y la secuencia las
contesta el proyecto, y volver a preguntarlas dejaría abierto contestar otra cosa que la
que el proyecto guarda— y **el paso 3 tampoco se pinta**: sus candidatos ya están abajo, y
un «Nada más, dale al botón» encima de una tabla ya hecha es la casilla inerte de BLAST
otra vez.

**Comprobado con un navegador de verdad**, no sólo con tests: se creó un proyecto con el
Prnp murino, se abrió desde el paso 0, y la página cae directamente en la tabla de
candidatos sin subir nada.

## 73 — La entrada se pedía en dos columnas de tres, el aviso accionable estaba dentro de un desplegable colapsado, y las explicaciones eran grises

Tres cosas de la misma pantalla, pedidas juntas (2026-09-04).

**La rejilla.** El paso 2 ponía a la izquierda la especie del diseño y su GenBank y a la
derecha la segunda especie entera, así que los dos ficheros de una misma especie caían en
columnas distintas y los de especies distintas quedaban pegados. Ahora la **columna es la
especie** y la **fila es el tipo de fichero**: arriba lo del diseño, abajo lo de la
segunda; a la izquierda la secuencia, a la derecha su anotación.

Las cuatro tarjetas llevan el **mismo contenido** —título, subida y biblioteca— para que
el alto lo iguale el navegador solo, y el desplegable de la segunda especie va **fuera**,
encima de su fila: dentro de una tarjeta la hacía más alta que su pareja. **No se clava
ninguna altura a ojo**, que aguanta hasta el primer cambio de tipografía.

**Y el primer intento no valía**: envolver las cuatro con un `<div class="sd-caja">` de
`st.markdown` **no envuelve nada** — Streamlit mete cada markdown en su propio contenedor
y el div se cierra solo, así que el CSS no llegaba. Se vio midiendo en el navegador (el
selector devolvía cero elementos), no leyendo el código; y se quitó, en vez de dejarlo ahí
pareciendo que hacía algo.

**El color.** Las explicaciones eran gris claro y pasan a **azul marino**
(`presentation.PAGE_COLORS`, medido `rgb(18,48,92)` en el navegador). El color se declara
en `presentation` y no en la página: uno elegido en la vista es una decisión sin test —es
la razón por la que `REFINEMENT_STATES` ya los traía— y además estaban repartidos en tres
sitios del CSS con tres grises distintos y ninguna regla. No es sólo gusto: las
explicaciones son la mitad del producto de esta app —la frase que dice por qué un frente
sigue abierto pesa tanto como la tabla— y en gris se leen como letra pequeña.

**El aviso.** «Ficheros de referencia conectados (N)» **sí** es pertinente: es la
procedencia de lo que va a correr, y es donde se ve la regla del `.tbl` obligatorio. Lo
que estaba mal es que mezclaba dos cosas. La lista es procedencia y se consulta —ahí un
desplegable está bien—; un aviso es una **tarea pendiente**. Y ese desplegable está
**colapsado** cuando hay algo conectado, así que la única línea accionable de la pantalla
—«falta el gen diana, y sin él todo sitio parece un off-target»— quedaba escondida detrás
de un clic, debajo de la lista de lo que sí funcionó. Ahora el aviso va **fuera y arriba**
(`presentation.connected_panel`) y la lista se queda dentro.

## 74 — Retomar un proyecto y la barra lateral preguntando por él: dos respuestas para la misma pregunta

**Reportado con dos capturas (2026-09-04).** Se abre `Intento_17` desde el paso 0 —«3
registro(s) · última 2026-09-02»— y la barra lateral sigue enseñando «Guardar esta corrida
en un proyecto» **sin marcar**, con el aviso «Sin proyecto, lo que calculen los modales se
pierde al cerrar la pestaña». Y encima la app decía que ese proyecto no tenía la corrida
guardada, **que sí la tenía**.

Con una pregunta al lado que es la que hay que contestar, no la que hay que arreglar:
*«¿tengo que darle a guardar esta corrida en un proyecto, o viniendo de uno abierto asumo
que los cambios que haga se irán guardando?»* **Que esa pregunta se pueda hacer ya es el
fallo.**

### Dos síntomas y una causa

La casilla nunca se marcaba, así que el almacén **no se abría**; sin almacén, `stores`
llega `None` a la tabla, a las tarjetas y al semáforo, y todas las corridas guardadas
desaparecen. O sea que el segundo síntoma —«no tenía la corrida»— **es el primero**, tres
consumidores más allá. Es el principio nº 23 otra vez, y esta vez la pista la dio quien lo
reportó al poner las dos capturas juntas.

### Y el mecanismo que elegí estaba mal

Al añadir el paso 0 sembré el estado de la casilla con
`st.session_state.setdefault(f"pr_activo_{especie}", True)`. **`setdefault` no escribe nada
si la clave ya existe**, y la de un widget existe desde que se pinta por primera vez — o
sea desde el primer repintado, antes de que hubiera nada que retomar. Sembrar un valor por
defecto no sirve cuando el valor ya está puesto.

### Pero el arreglo no es sembrarlo bien: es no preguntar dos veces

La pregunta «¿en qué proyecto guardo esto?» ya la contestó el paso 0. Volver a hacerla
abajo permite dar **dos respuestas distintas a la misma pregunta**, y cuál manda no lo
elige nadie. Es la misma razón por la que se quitó la casilla global «Usar los de
`data/reference/`»: una opción cuyo único efecto posible es dejarlo todo en NOT_RUN sin
decir por qué no es una opción, es una trampa.

Con un proyecto retomado, la barra lateral **enseña el proyecto abierto** —su historial,
sus corridas y si siguen valiendo— y no ofrece elegir otro ni crear uno. Y la respuesta a
la pregunta va donde estaba la pregunta (`PROJECT_RESUMED_NOTE`): **todo lo que hagas a
partir de aquí se guarda solo, no hay nada que marcar.**

Comprobado en el navegador: tras retomar, la barra lateral no trae ni la casilla ni el
aviso de «Sin proyecto», y el banner dice el proyecto y cuántos registros tiene.

## 75 — La suite dependía de que la máquina no tuviera proyectos guardados

Salió al comprobar lo anterior, y es una rotura que **introduje yo** en la tanda del paso
0. Se corrió la suite con un proyecto de prueba en `data/proyectos/` y saltaron **24 tests
en error**, todos de ficheros que no tenían nada que ver.

**La causa**: desde que la primera pregunta de la app es «¿retomas un proyecto guardado?»,
lo que se pinta arriba del todo **depende de si hay proyectos**, y sin declarar el
directorio ése es el del paquete — el de la máquina donde corre la suite. Con uno dentro,
`app.selectbox[0]` deja de ser el de la especie y pasa a ser el del proyecto.

Un fallo así **no dice lo que pasa**: dice que has roto media app, y el que lo lea irá a
buscar a un sitio equivocado. Es la familia del diagnóstico que manda al lugar erróneo.

**El arreglo es el de siempre en este proyecto: lo que decide lo que se ve se declara.**
`tests/pagina.py` da `sin_proyectos()` —y su contrario, `con_proyectos()`— y los tres
ficheros que pintan la página lo ponen en `setUpModule`. Va ahí y no como gestor de
contexto alrededor de la construcción porque tiene que estar puesto durante **todos** los
`.run()`: cada `set_value(...).run()` vuelve a ejecutar el script de la página.

**Medido que muerde**: con un proyecto guardado delante y el `setUpModule` desactivado,
`test_streamlit_app` rompe en **15 de 22**; con él, pasan las 44 de los tres ficheros. Un
blindaje sin prueba de que muerde es la errata nº 29 otra vez.

Y `data/proyectos/` pasa a estar en `.gitignore`: son datos de quien usa la app —su
secuencia y su registro de decisiones—, no del repositorio.

## 76 — Eran DOS botones con casi el mismo nombre, y diagnostiqué el que no era

**Reportado dos veces (2026-09-03 y 2026-09-04)**: «Descargar todo (zip) produce un
fichero vacío... baja `shmir-design (3).zip` y no contiene nada», y luego «empieza lo que
parece la descarga pero luego parece que no llega porque da un error de internet, cuando
no lo hay».

**Yo di por supuesto cuál era el botón.** Reproduje el de la copia de seguridad de punta a
punta, midiendo, y funcionaba — porque no era ése. `shmir-design (3).zip` sale de
`file_name="shmir-design.zip"`, que es el botón **«Descargar todo (zip)»** de la sección
*Descargas*: el que empaqueta los ficheros GENERADOS del diseño. El de la copia se llama
«Descargar todo (**.**zip)» y baja `shmir_copia_<fecha>.zip`. **Dos botones con el mismo
nombre a un punto de distancia**, y el principio nº 3 —no dar por buena una causa sin
comprobarla— cometido por mí, sobre el propio botón.

Lo que lo cerró fue el nombre del fichero: `shmir-design.zip` está escrito en una sola
línea del código y no hay otra.

### Y en ese botón había DOS fallos distintos

**1. El zip vacío.** `ficheros` está vacío hasta que se pulsa «Seguir: las comprobaciones
que faltan» —`bloque_especie` devuelve `{}` antes— y la sección *Descargas* pintaba el
botón igual. Un zip de cero entradas son **22 bytes** y se abre sin nada dentro. Medido.
Es la misma frase que se dijo de la copia de seguridad: **parece una descarga hecha cuando
no hay ninguna**, y eso es peor que no tener el botón.

**2. La descarga que empieza y no llega**, y el mecanismo está comprobado en el código de
Streamlit, no supuesto:

- `zipfile` estampa **la hora actual** en cada entrada, así que los mismos ficheros dan
  bytes distintos en cada construcción. **Medido**: dos llamadas seguidas, dos md5. Y le
  pasaba también a la copia de seguridad.
- `MemoryMediaFileStorage.load_and_get_id` deriva el id de un descargable **de su
  contenido** (`_calculate_file_id(file_data, ...)`): bytes distintos, id distinto.
- Pulsar un `download_button` provoca un rerun; al terminar, `clear_session_refs` +
  `remove_orphaned_files` **borran el id que ya no referencia nadie** — que es justo el que
  el navegador está descargando.

O sea: **el fichero desaparece del servidor a media descarga**. Cuanto más grande, más
rato para que se lo lleven por delante — por eso «empieza y no llega» en vez de fallar del
todo, y por eso mi prueba con 1,1 MB en local no lo vio.

### El arreglo

`gestor.deterministic_zip` es ahora el **único** constructor de zips y pone **fecha fija**
en cada entrada, derivada de la fecha declarada — no a cero: dos copias de días distintos
tienen que seguir siendo dos ficheros distintos. `export_all` pasa por él también, así que
la copia de seguridad deja de cambiar de bytes entre repintados.

Y el botón: no se ofrece si no hay nada (`presentation.downloads_zip` dice qué falta y
que se genera al pulsar «Seguir»), y el nombre lleva **especie y fecha** en vez de la
constante `shmir-design.zip` — que es por lo que el navegador los numeraba `(1)`, `(2)`,
`(3)` sin que ninguno dijera de qué corrida era.

## 77 — El punto de «no hace falta» era NEGRO, el que más grita de la columna

**Preguntado con la captura (2026-09-04)**: «¿por qué está en negro lo de
`apa_medido.tsv`? Parece como si faltara algo.»

La fila decía exactamente lo contrario que su marca: *«Su frente ya está cerrado por
`polya_db_mouse.tsv`. Es una ALTERNATIVA que no hace falta conseguir, no algo pendiente»*
— con un **⚫** delante.

`REFINEMENT_STATES` declaraba ese estado como **«gris claro»** y le había puesto un
círculo **negro**. En una columna de 🟢 y 🟠, el negro no se lee como «el más apagado»: se
lee como **el peor**, más grave incluso que el ámbar de lo que falta de verdad. La marca
contradecía a la vez al color declarado al lado y al texto de la propia fila.

Ahora es **➖**, que se lee como «no aplica» — que es lo que es — y no compite con el ⚪ de
`OPCIONAL`. Es la lección del principio nº 11 en la capa visual: cuando el código y lo que
se ve dicen cosas distintas del mismo hecho, lo que alguien va a leer es lo que se ve.

## 78 — Dos botones que bajan cosas distintas se llamaban igual menos un punto

De la errata nº 76, y va aparte porque la lección es de interfaz y no del zip.

«Descargar todo (zip)» y «Descargar todo (.zip)». **Un punto de diferencia**, y bajan
cosas distintas: uno los ficheros que acaba de generar el diseño, el otro la copia de
seguridad del volumen entero.

Con esos dos nombres, un reporte de «no me baja el zip» **no identifica cuál**, y por eso
reproduje el que no era de punta a punta antes de darme cuenta. Que dos botones sólo se
distingan por un signo de puntuación es **un problema de la interfaz antes que de quien
los confunde** — lo dijo quien lo reportó y es exactamente así.

Ahora cada uno se llama por **lo que baja**, no por «todo» — qué es «todo» depende de
dónde estés en la página:

- **«Descargar los resultados del diseño (.zip)»**
- **«Descargar la copia de seguridad del depósito (.zip)»**

Y con guardia mecánico (`tests/test_dos_botones_NO_se_llaman_igual.py`): **ninguna pareja
de etiquetas de descarga puede ser la misma tras quitar la puntuación**. No protege sólo a
estos dos — mide la distancia entre las etiquetas que encuentra, así que el día que entre
un tercer zip se entera. Con su control adversario: el par de antes tiene que chocar, y hay
un test de que el detector encuentra etiquetas (si dejara de encontrarlas, «ningún par
choca» y «no miré» darían el mismo verde).

## 79 — La diana se pedía a mano y ya estaba declarada: dos respuestas y ganaba la peor

**Decidido (2026-09-04)**, y arrancó de una pregunta: «explícame por qué pone
*refseq_rna.fa no se ha conectado: hace falta el gen diana*».

`refseq_rna.fa` **estaba en el depósito** —salía en verde en el panel de refinamiento— y
aun así `resources._refseq` se negaba a conectarlo mientras el campo «Gen diana
(accession)» de la barra lateral estuviera vacío. Al explicarlo salieron dos cosas peores
que el aviso.

### 1. Eran DOS definiciones de «cuál es mi diana», y la manual ganaba

- El veredicto de una corrida de BLAST usa `specificity.target_accessions(especie)`: la
  lista **completa** de variantes de transcrito, declarada en `data/diana/variantes.toml`
  con su procedencia (errata nº 56).
- `filter_specificity` exigía un `target` **tecleado**, **uno solo**, y abortaba sin él.

El patrón de siempre —un dato declarado que además se pide a mano— con el agravante de que
**la que se pedía era la peor de las dos**: una variante en vez de todas, escrita sin
procedencia y sin nada que la ate a la tabla.

Ahora el filtro recibe la **especie** y lee la tabla. `--target` se retira del CLI y el
campo se va de la barra lateral: **la única forma de declarar la diana es esa tabla**.

### 2. Sin declaración NO se aborta: `NO_CIERRA` con el motivo

Igual que en BLAST. Abortar dejaría sin diseñar a una especie por algo que no impide
proponer candidatos; un `PASS` sería el colador que `target_accessions` existe para
impedir. `NO_CIERRA` ya es el estado de «la corrida se hizo y no cierra el frente», y aquí
es literalmente eso.

### 3. La pantalla se contradecía, y eso es un fallo por sí solo

Abajo el fichero en verde —«está en el depósito»— y arriba «`refseq_rna.fa` no se ha
conectado». **Las dos ciertas**, contestando a preguntas distintas, y juntas se leen como
que la app se equivoca. Ahora cada pregunta se contesta donde toca: **el fichero**, en la
lista de conectados; **la diana**, en el veredicto del filtro, que dice qué falta —la
declaración, no el fichero— en vez de dejarlo deducir.

### Lo que salió al arreglarlo

Cuatro ficheros de test montaban su base de datos falsa con un único registro llamado
**`"diana"`**, que era el `--target` que le pasaban. Al derivar la diana de la tabla, esa
base pasó a no contener ninguna variante declarada — así que la sonda daba un off-target
**contra sí misma** y el semáforo se ponía ámbar. El nombre del registro se **pide** ahora
a `target_accessions("raton")` en vez de escribirse: un test que escribe la clave por la
que pregunta coincide por construcción (principio nº 25).

Y en `test_presentacion_coste.py` había **dos tests que construían el mismo `ResourceSet`
y afirmaban lo contrario** —«necesita diana y base» y «una base sin diana no estima»—
porque el segundo se escribió cuando la diana era un campo. Ninguno de los dos podía
delatar al otro mientras el campo existiera.

## 80 — El aviso fechaba la causa, no decía qué hacer, y encima no se arreglaba nunca

**Reportado con la captura (2026-09-04)**: se elige `Intento_17` —tres líneas de
historial, última actividad 2026-09-02— y sale «Este proyecto se creó **antes de que la
app guardara la secuencia de entrada**». Y la pregunta: *«no parece cierto que ese
proyecto se creara cuando dice el comentario»*.

### El mensaje era CIERTO y aun así estaba mal

Cierto porque el campo `sequence` entró en `proyecto.json` **el 2026-09-04** (errata
nº 72), así que cualquier proyecto anterior —incluido uno de anteayer— no lo tiene. Que
suene a «hace mucho» es cosa de la frase, no del hecho.

Y estaba mal por dos razones independientes:

1. **fecha la causa en vez de decir qué hacer.** «Se creó antes de que la app guardara X»
   invita a comprobar cuándo se creó, que es información que no sirve para nada: lo que
   hay que saber es que falta la entrada y que se arregla subiéndola. El mensaje mandaba
   a mirar el sitio equivocado — la misma familia que el «comprueba que Streamlit está
   instalado» pegado a un conflicto de configuración;
2. **y no se arreglaba.** Subir la secuencia abría el proyecto, sí, pero **no la
   guardaba**: al día siguiente salía el mismo aviso. Un mensaje que dice «súbela como
   siempre» y deja el proyecto igual que estaba es **una tarea de disciplina, no un
   arreglo**.

### Ahora se rellena sola, y lo que lo hace seguro es el md5

`ProjectStore.open(..., sequence=…)`: si el proyecto no tiene entrada y el md5 canónico
de la que se le pasa es **el que el proyecto declara**, se escribe. Esa comprobación es la
misma que ya impide abrir un proyecto con otra entrada, así que rellenar **no puede** meter
una secuencia que no sea la suya — y con una que no lo sea no se escribe nada y además se
rechaza la apertura.

Es una **migración de una vez**, no una escritura en cada apertura: un proyecto que ya la
tiene no se reescribe. `proyecto.json` es la mitad del par que el log encadena, y tocarlo
sin motivo es ruido en lo que se lee para saber qué pasó.

### Y el argumento que faltaba: la sexta vez de la familia

La capacidad no vale nada si no corre en el camino de verdad, y **hay un solo sitio de la
app donde coinciden un proyecto viejo y su entrada**: el `project_open` de la barra
lateral, después de subir la secuencia. Si el `sequence=` no viaja ahí, la migración no
corre nunca y el aviso sale otra vez mañana — exactamente el patrón de `page_run`,
`store.save_*` y el `stores=` que no se pasaba.

## 81 — «3 registro(s)»: el nombre hacía la pregunta imposible de no hacerse

**Preguntado (2026-09-04)**: *«me explicas el concepto de "registro(s)". De qué sirve
tener registros diferentes si solo se accede a uno. O quizás no entiendo su
significado»*.

**La pregunta es la prueba de que el nombre estaba mal**, y no había ningún malentendido
que deshacer: en el desplegable de proyectos, «registro» se lee como **otra cosa que se
puede abrir** —otro proyecto, otra corrida guardada aparte— y no lo es. Un proyecto tiene
**un** historial, y ese número cuenta sus **líneas**: una corrida guardada, una selección,
un cambio de nombre, una nota.

Se llaman **anotaciones**, y la cuenta la monta `presentation.project_entry_count` — con
su singular, que estaba escrito a mano en cuatro sitios (`registro(s)` en el desplegable,
el cartel del proyecto abierto, el plan de borrado y su confirmación). Y qué es una va
dicho **donde se elige el proyecto** (`PROJECT_ENTRY_HELP`), con la mitad que la pregunta
pedía: *no es otro proyecto ni algo que se abra por separado*.

## 82 — Renombrar un proyecto exigía volver a diseñarlo entero

**Pedido (2026-09-04)**: «¿me podrías añadir algo para editar el nombre del proyecto?».

Y la capacidad **existía**: `store.rename` cambia el nombre visible, deja el slug en paz y
apunta el cambio en el log con su fecha (errata nº 64). Lo que estaba mal era **dónde**:
el único control vivía en el desplegable «Gestionar proyectos» de la barra lateral, y esa
barra sólo se pinta **después de haber diseñado**. O sea que para cambiarle el nombre a un
proyecto había que subir otra vez la secuencia y correr el diseño entero.

**El sitio donde se pide un nombre es el sitio donde se leen los nombres**: el paso 0, con
el desplegable delante. Y se renombra el **elegido**, no el abierto — el nombre se cambia
justo cuando no se reconoce cuál es, o sea antes de abrirlo.

La fecha es **hoy y derivada** (`today_text()`), no un calendario: renombrar pasa ahora, y
ofrecer elegir la fecha sería una vía para apuntar el suceso en un día en que no ocurrió
— la misma razón por la que crear un proyecto y guardar una corrida vienen con hoy puesto.

## 83 — El aviso describía el 80 % del camino y se callaba el paso que lo cierra

**Reportado (2026-09-04)**, con el aviso entero pegado: se abre un proyecto guardado
—«Candidatos shmiR (mouse)»— y sale *«A este proyecto le falta guardada la secuencia de
entrada… súbela como siempre y el proyecto se abrirá igual… y esta vez se queda
guardada»*.

**El aviso es el correcto** —ese proyecto se creó antes de que existiera el campo, y la
errata nº 80 es justo esto— pero **la instrucción no lleva a donde dice**. Quien la lee
sube la secuencia y espera que el proyecto se abra **solo**, porque el mensaje habla en
futuro y no nombra ningún sitio. Y no se abre: subir la secuencia sólo contesta los pasos
1 y 2. El proyecto se abre **en la barra lateral**, marcando «Guardar esta corrida en un
proyecto» y eligiéndolo en el desplegable — y **ése es exactamente el momento** en que
`project_open` recibe la secuencia y la migración se escribe.

O sea: la única acción que cierra el problema era la que no estaba escrita. Es la familia
de la errata nº 28 —la ficha que describe un fichero y el cargador que lee otro—: un texto
que **se lee correcto de principio a fin** y termina en otro sitio que el que anuncia.

### Y el nombre de la casilla no se transcribe

`presentation.PROJECT_SAVE_TOGGLE`: lo pinta la barra lateral y lo nombra el aviso. Escrito
dos veces, el día que ese control cambie de nombre el aviso mandaría a buscar algo que no
existe — con la forma correcta y sin dar ningún error (principio nº 13). Hay test de que la
página usa la constante y no el literal.

## 84 — Derivar la diana encendió un filtro que barre una base de GB por cada ventana

**Reportado (2026-09-04)**: «va muy lento; le doy a Buscar candidatos y lleva 10 min y aún
no muestra nada… se queda con Mus musculus como epígrafe». **Es una regresión de esa misma
mañana, y la causa es mía**: la errata nº 79.

### La cadena, en dos pasos

1. hasta ese día, `resources._refseq` **se negaba a conectar** `refseq_rna.fa` sin un gen
   diana tecleado, así que `specificity_db` llegaba `None` y `filter_specificity` salía
   `NOT_RUN` **al instante**. El filtro estaba escrito, probado… y nunca corría;
2. al derivar la diana de su tabla, el fichero pasa a conectarse —que es lo correcto— y
   con él **se enciende un filtro que barre la base ENTERA por cada ventana elegible**.

O sea: el arreglo era correcto y **destapó un coste que llevaba oculto desde siempre**
porque la condición que lo tapaba era otro fallo. Familia del principio nº 14 al revés: no
es que la comprobación dejara de correr, es que **empezó** a correr y nadie había medido lo
que costaba.

### Lo MEDIDO (2026-09-04, en el contenedor)

Con secuencia real repetida como registros: **~37 Mnt/s por ventana** (guía y pasajera, las
dos hebras). Sobre las **407 ventanas elegibles** de la corrida murina por defecto:

| base | por corrida |
|---|---|
| 22 MB | 3,8 min |
| 100 MB | 17 min |
| 400 MB | 73 min |

Y la **carga** aparte: 25 MB/s y **~5× el fichero en memoria** (45 MB de fichero → 234 MB
de proceso). Con una base de varios GB el contenedor se queda sin memoria antes de que
nadie llegue a medir nada — y el síntoma es exactamente el reportado: una página que no
vuelve, sin ningún error.

### La conclusión no es «optimizar»: es que ese filtro NO es para esta base

A cualquier tamaño plausible de un RefSeq real —decenas o cientos de MB por la vía UCSC,
80 GB por la del NCBI— el escáner en proceso tarda de minutos a horas **por corrida y en
cada repintado**. **Eso es exactamente la razón por la que existe el modal de BLAST**: este
software no lanza el BLAST y no puede, así que prepara la orden, se corre fuera contra una
base local y se recoge el `-outfmt 6`. Y desde la errata nº 68 **una corrida guardada
cierra el frente igual que un fichero**, así que no conectar la base no deja el frente sin
forma de cerrarse.

### El techo se DERIVA de un presupuesto declarado

`specificity.SCAN_BUDGET_SECONDS` (60 s por corrida) × la velocidad **medida** ÷ las
ventanas elegibles de la corrida de referencia → `MAX_SCANNABLE_NT`. No es un número
escrito: si mañana el escáner es diez veces más rápido, el techo sube solo. Y el motivo que
sale a pantalla lleva **los tres números** —cuánto pesa, sobre cuántas ventanas, cuántos
minutos— en vez de una queja.

### Y dice que el fichero SIGUE valiendo

Es la mitad que impide repetir la contradicción de la nº 79 con el signo cambiado: el
fichero **está en el depósito**, es de donde sale la **procedencia** de una corrida de
BLAST, y el frente se cierra con el modal. Lo único que no se hace es meterlo en un filtro
que no puede con él.

### Una frase que se quedó atrás, corregida en el mismo cambio

`blast_readiness` decía que el frente «lo cierra el filtro de la ventana contra el catálogo
cargado, no la corrida». Dejó de ser cierto con la errata nº 68 —una corrida que cubre el
panel lo cierra— y con esta errata es además **el consejo justo al revés**: el catálogo
cargado no puede cerrarlo. Principio nº 11.

## 85 — El `.docx` del informe cambiaba de bytes en cada generación

**Medido (2026-09-04)** al investigar «no se me descarga nada»: se genera el mismo informe
dos veces seguidas y

| | bytes | md5 |
|---|---|---|
| `.docx` | 50.766 | **dos distintos** |
| `.pdf` | 70.191 | el mismo |
| `.md` | 165.428 | el mismo |

**Un `.docx` es un zip**, así que tenía el problema de los zips (errata nº 76):
`zipfile.writestr(nombre, datos)` estampa la **hora actual** en cada entrada. Y Streamlit
deriva el id de su fichero de medios **del contenido**: bytes nuevos → id nuevo → el que
el navegador está descargando se queda huérfano y lo borra `remove_orphaned_files`.

Se empaqueta ahora con `gestor.deterministic_zip`, que pasa a ser el **único constructor
de zips del proyecto**. Y el orden va **declarado** (`order=`) porque aquí lo exige el
formato —`[Content_Types].xml` primero, OPC—: hoy el alfabético coincide por casualidad
(`[` va antes que `_` y que `w` en ASCII) y eso no es una garantía, es una coincidencia
que se rompe al renombrar cualquier pieza.

**Lo que esto NO explica, y se dice**: el `.pdf` y el `.md` **ya eran deterministas** y
tampoco se descargan. Así que esto es un fallo real y no es la causa de lo reportado.

## 86 — El proxy reenviaba las cabeceras de salto a salto del upstream

**No es una causa comprobada, y se declara como lo que es**: no se ha podido reproducir el
entorno de producción desde aquí, así que **no se le asigna causa** a «ninguna descarga
llega» (principio nº 3). Lo que sí es un fallo real del proxy, encontrado al buscarla:

`proxyRequest` copiaba `{...upRes.headers}` **enteras**. Las cabeceras de **salto a
salto** (RFC 9110 §7.6.1) describen la conexión que ACABA en el proxy, no la respuesta, y
un proxy no las reenvía. La que muerde es **`transfer-encoding`**: anuncia un troceado que
la conexión de salida no usa —Node pone el suyo— y en **HTTP/2**, que es lo que habla el
borde de cualquier despliegue moderno, **está prohibida**: una respuesta que la lleva se
rechaza o se queda colgada. El síntoma sería exactamente el reportado — una descarga que el
navegador da por iniciada y que nunca recibe un byte, mientras la misma descarga cae en
0,1 s en local, donde no hay HTTP/2 de por medio.

### Lo que se midió y quedó REFUTADO por el camino

Dos hipótesis plausibles, las dos descartadas con una medida en vez de con un argumento:

1. **«La URL del medio no lleva el prefijo del montaje»** — `MemoryMediaFileStorage` monta
   las URL sobre `/media` sin base. **Falso en la práctica**: con `--server.baseUrlPath`,
   el navegador pide `/shmir/media/<id>.bin` y la descarga cae. Comprobado con Chromium.
2. **«El proceso está ocupado y no atiende»** — con la base de 175 MB el escáner tiene el
   GIL casi todo el rato. **Falso**: con el script haciendo `find` sobre 160 Mnt durante
   30 s, el servidor contestó las 46 sondas de salud en **30-100 ms** y la descarga cayó
   en **0,1 s**. Streamlit corre el script en otro hilo y el servidor sigue sirviendo.

### Y un dato que sí acota el problema

La respuesta de `/media/` viene **`content-encoding: gzip`** —Streamlit comprime las
descargas de `application/octet-stream` a propósito— con `accept-ranges: bytes`. Queda
anotado porque es lo que hay que mirar primero si el arreglo de las cabeceras no basta:
una petición con `Range` sobre una respuesta comprimida es la otra forma conocida de que
una descarga empiece y no termine.

## 87 — La procedencia de un fichero que YA está exigía volver a subirlo

**Reportado (2026-09-04)** con el modal de carga de off-targets abortando en rojo:
`transcriptoma_3utr.fa` está en el depósito, es válido, tiene su md5 — y **PARA**, porque
a su línea le faltan las cuatro columnas de procedencia de tabla.

**El aviso decía la verdad.** Ese fichero entró el **2026-09-02**, y las cuatro columnas
entraron ese mismo día **más tarde** (errata nº 62). Así que no es un descuido de quien lo
subió: es una regla que llegó después que el fichero.

**Lo que estaba mal era la única salida que ofrecía**: «reemplázalo por el gestor para
declararla» — decenas de MB otra vez por cuatro metadatos. Lo que falta no es el fichero,
son cuatro campos de su **línea**. Así que se declaran sobre la línea y el fichero no se
toca (`deposito.declare_provenance`, con su control en la fila del gestor).

### Lo que lo hace seguro, y no un atajo

Se comprueba que **el fichero de disco siga siendo el que la fila registra** (md5). Con el
fichero cambiado debajo, declarar el ensamblaje se lo pegaría a **otra** tabla, con la
forma correcta y sin dar ningún error. Va declarado en `guardias.toml` — y la auditoría de
guardias **lo cazó sola al estrenarlo**: es de la clase «compara una identidad declarada
contra lo entregado» y no estaba en la tabla.

### Y lo que NO hace, a propósito

**No revalida el contenido.** El fichero pasó su validación al entrar, y volver a correrla
sobre decenas de MB para añadir metadatos es exactamente el coste que esto quita. Y sólo
se ofrece donde la procedencia hace falta (`PROVENANCE_REQUIRED`): un casete de AAV no sale
de ninguna tabla, así que ahí la columna vacía es la **verdad** y rellenarla sería
inventarse un dato — declararla en ese rol **aborta**.

---

## 88 — El proyecto elegido se olvidaba al avisar de que le faltaba la entrada

**Reportado (2026-09-04)**, con la secuencia entera: *«después de llegar donde llegué,
habiendo empezado desde cero, luego seleccionado el proyecto que tenía y metiendo el
tsv… sigue pidiéndote lo de la especie para avanzar. A pesar de que ya le he metido el
proyecto que tiene esa información»*. Y pegado: *«ahora no te sale eso en amarillo de que
le falta»*.

**Las dos observaciones son un solo fallo, y la segunda es la peor de las dos.**

En `_paso_cero_proyecto`, la rama de «este proyecto no se puede reabrir solo» pintaba el
aviso y **acto seguido hacía `session_state.pop("p0_retomado")`**. O sea, avisaba y se
olvidaba en el mismo gesto. De ahí salen los dos síntomas:

1. **El aviso duraba UN repintado.** En Streamlit cada tecla es un repintado, así que
   escribir cualquier cosa lo borraba — y la exigencia de contestar los pasos 1 y 2 se
   quedaba. **La app dejaba de explicar por qué seguía preguntando.** Un aviso que
   desaparece se lee como «ya está resuelto», así que esto es peor que no haber avisado:
   es lo que hace que la pregunta parezca un fallo de la app en vez de una consecuencia.
2. **El proyecto elegido no era el que se abría.** Al subir la secuencia había que ir a la
   barra lateral, marcar la casilla de guardar y **volver a elegir a mano el proyecto que
   ya se había elegido arriba**. Es la errata nº 83 con el signo cambiado: allí el texto
   no nombraba el paso que cierra el problema; aquí lo nombra y **la app no da ese paso**.

**Y es una consecuencia de haber modelado un estado con dos valores donde hacían falta
tres.** El paso 0 devolvía «un proyecto retomado» o `None`, y son **tres** cosas: no hay
proyecto elegido, hay uno **elegido y reabrible** —que contesta los pasos 1 y 2—, y hay
uno **elegido y sin entrada**, que no contesta nada y aun así es el proyecto en el que
hay que guardar. El tercero se estaba colapsando contra el primero, y colapsarlos es lo
que hacía que «elegido» y «no elegido» se comportaran igual.

Ahora se devuelve `pendiente` además de `reabrible`, y con eso:

- **olvidar el proyecto sólo puede ser una decisión de quien mira**, nunca automático:
  el `pop` vive dentro del botón «Elegir otro proyecto» y en ningún otro sitio. El aviso
  dura lo que dura el motivo;
- **la barra lateral no vuelve a preguntar por él** (`PROJECT_PENDING_NOTE`), igual que
  con uno retomado y por la misma razón que se quitó la casilla global de ficheros: dos
  respuestas posibles a la misma pregunta, sin nada que diga cuál manda;
- y al abrirlo con la secuencia delante, `project_open` la recibe y **la migración de la
  entrada se escribe sola** (errata nº 80). Ese es el paso que el aviso nombraba.

Hay tres tests, y el primero es el que fija la regla y no el síntoma:
`tests/test_un_proyecto_A_MEDIAS_no_se_olvida.py` exige que en esa rama no haya ningún
`pop` fuera de un botón, que la barra lateral tenga una rama para el pendiente, y que el
aviso nombre lo que pasa cuando se suba la secuencia.

---

## 89 — La fecha del informe salía de una clave que nadie escribe, y su aborto tumbaba media página

**Reportado (2026-09-04)** con el mensaje entero:

    PARA — La fecha del zip tiene que ser AAAA-MM-DD y llegó «sin fecha declarada»

**Son dos fallos independientes, y el segundo es el que convierte una molestia en un
bloqueo.**

### 1. El zip quedó imposible de generar

La errata nº 76 hizo la fecha del zip **obligatoria y derivada de la declarada**, que es
correcto. Lo que no se comprobó es de dónde salía la declarada en cada llamador. Salía de
`st.session_state.get("fecha_informe", …)`, y **`fecha_informe` no la escribe nadie**: se
lee en dos sitios de la página, con **dos valores por defecto distintos**:

| llamador | por defecto | qué pasa |
|---|---|---|
| el informe | `"sin fecha declarada"` | llega a `Document.generated` → `.docx` (que es un zip) → **aborta siempre** |
| el zip de resultados | `"" or today_text()` | cae en hoy y funciona |

O sea: **la misma clave, dos literales, y sólo uno válido.** Es la familia de la errata
nº 47 —una comparación que preguntaba por una clave que no existe— con el signo cambiado:
allí producía un veredicto falso, aquí un aborto seguro. Arreglé que el zip se corrompiera
y lo dejé imposible.

**El guardia estaba bien; el llamador, no.** No se toca `_fecha_del_zip`: una fecha
inventada ahí discreparía en silencio de la que va en el nombre del fichero. Lo que se
arregla es que la fecha **se derive**, que es lo que ya dice el criterio de la errata
nº 64: lo que ocurre AHORA lleva hoy porque ésa es la verdad, y generar un informe pasa
al pulsar. `fecha_informe` desaparece.

### 2. Y el aborto se llevaba por delante todo lo que hay debajo

El bloque del informe no tenía guardia propio, así que la excepción subía hasta el `try`
de `main()`, que pinta el motivo y **hace `return`**. Dejaban de pintarse los cuatro
modales, «Descargas» y el paso 5 entero. Por eso el error salía «en la sección del
informe»: ahí es donde el script se paraba, no donde está la causa.

**La regla que queda: un entregable que falla no puede tumbar a los otros dos ni al resto
de la página.** `informe_files` construye los tres formatos **por separado** y cada uno
trae sus `datos` o su `error`; la página pinta el botón o el motivo **en su columna**. El
botón roto **no se esconde** — sería quitar la única señal de que algo falla.

**Y en el CLI aborta, a propósito.** No es incoherencia: en la página cada entregable
tiene su sitio en pantalla, así que el motivo se ve y los otros dos siguen sirviendo; en
`tools/informe.py` no hay nadie mirando tres columnas, y escribir dos ficheros de tres
saliendo con 0 deja media entrega que parece completa.

### El guardia mecánico, que es lo que generaliza

`tests/test_una_descarga_ROTA_no_tumba_la_pagina.py` comprueba que **ninguna clave de
`session_state` se lee sin que alguien la escriba**. Una clave así devuelve **siempre** su
literal por defecto, así que lo que decide de verdad es ese literal — y aquí había dos
para la misma clave, en dos sitios, con resultados opuestos. Hoy sale a cero, y con su
control adversario: si el detector dejara de encontrar claves, «ninguna huérfana» y «no he
mirado» darían el mismo verde (errata nº 29).

**El detector quita los comentarios antes de mirar.** El comentario que explica de dónde
venía `fecha_informe` nombra la clave, y sin esa poda el guardia fallaría por su propia
documentación — con la salida fácil de borrar la explicación. Errata nº 54 con el signo
cambiado.

### Lo que NO estaba roto, medido antes de decirlo

**La copia de seguridad no pasa por aquí.** `build_backup` recibe `date=today_text()`,
que es una fecha derivada y válida, y su botón ya estaba envuelto en su propio
`try/except`. Comprobado: `deterministic_zip` con `today_text()` produce el zip sin
problema. De los dos botones que pasan por `deterministic_zip`, **sólo uno estaba roto**.

---

## 90 — El total prohibido era la única columna visible, y sus tres sumandos estaban calculados

**Reportado (2026-09-04)**, con la tabla delante: las cuatro `carga_<clase>` vacías y
`carga_seed` con valores de 1.054 a 19.020. *«No puede haber suma sin sumandos.»*

**Las dos hipótesis que se plantearon eran ciertas a la vez, en sitios distintos.**

### Son dos contadores, y no la misma cantidad ni en principio

| | de dónde sale | clases | percentil |
|---|---|---|---|
| `carga_seed` | de **tilar**, `seed_load.seed_load` | **tres** (8mer, 7mer-m8, 7mer-A1) | no |
| `carga_<clase>` | de la **corrida guardada**, `seed_load_reference` | **cuatro** (con `6mer`) | sí, pegado |

`carga_seed` era literalmente `total=sum(totales.values())`. Las cuatro estaban vacías
porque no había ninguna corrida de off-targets guardada. O sea: **la única columna
visible de este eje era la única que `offtarget.WHY_NOT_SUMMED` prohíbe usar.**

### Y el desglose estaba calculado y se tiraba

`SeedLoad.counts` lleva los tres sumandos, por ventana. `as_column()` devolvía
`str(self.total)`. **No hacía falta calcular nada: había que dejar de tirarlo.**

### El total se retira, no se sustituye

No hay ningún número que signifique lo que aquél parecía significar. Salen los tres
sumandos —`tilado_8mer`, `tilado_7mer-m8`, `tilado_7mer-A1`— con el prefijo diciendo de
dónde vienen, para que no se confundan con las cuatro del frente que están al lado. Y
queda la **frase de dirección** (`WHERE_THE_TOTAL_WENT`), como con `POLYA_DB_PRNP`: sin
ella, quien busque `carga_seed` y no la encuentre pensará que el dato se perdió.

**`weighted` era el mismo pecado y también se arregla**: multiplicaba la expresión por
`sum(conteo.values())`, o sea ponderaba el total. Ahora pondera **por clase**. Hoy no se
calcula nunca —`expresion_cerebro.tsv` no existe— y por eso importa que nazca bien.

### La séptima del patrón de `page_run`: el TSV nunca recibió el arreglo

Las cuatro `carga_<clase>` se cablearon a `presentation.candidate_rows` (errata nº 70) y
**no llegaron a `comparative.COLUMNS`**, que es el TSV que se descarga y se discute. Se
cierra por donde había que cerrarlo: `stores` entra por **`comparative_rows`**, y las
columnas se piden al **mismo** `seed_load_columns` que usa la página — reimplementarlo
sería la segunda definición del mismo número.

**Y al hacerlo salió un argumento inerte**: `comparative_tsv` acepta `anatomy` y llamaba
a `comparative_rows(selection, scaffold)` **sin pasarlo**. Los dos llamadores lo pasan.
No había síntoma porque hoy coincide con la de la selección, pero la cabecera se
construía con una anatomía y las filas con otra. Al dejar de tragárselo, un test que
pasaba una anatomía incompatible con lo tilado **empezó a abortar** — el guardia de
`coords` haciendo su trabajo: `3utr:306` no cabe en un 3'UTR de 294 nt. Ese test tilaba
sin la anatomía que declaraba en la cabecera.

### PRINCIPIO nº 31 — un comentario protege su clase; un mecanismo protege la siguiente

`offtarget.WHY_NOT_SUMMED` termina, escrito hace semanas:

> «`Counts` no tiene ningún atributo que las sume: **si existiera, alguien acabaría
> imprimiéndolo**.»

El guardia se puso sobre `offtarget.Counts`. **El atributo existía en
`seed_load.SeedLoad` y se estaba imprimiendo.** La profecía se cumplió al pie de la
letra, en la clase de al lado, mientras el comentario que la anunciaba seguía ahí.

`tests/test_ninguna_clase_de_conteos_SUMA.py` **descubre** qué clases del paquete llevan
conteos por clase y se lo exige a todas, así que un contador nuevo queda cubierto sin que
nadie se acuerde. Guardia, no trinquete: el número correcto es cero.

**Y su control adversario tuvo que corregirse.** La primera versión probaba con un
`def total(self): return sum(...)` — una forma **parecida** a la real. El `total` de
verdad era un **campo** (`total: int | None = None`) y la suma vivía en el constructor,
así que un guardia que sólo mirara cuerpos de métodos **no habría cazado el fallo que de
verdad hubo**. Es el principio nº 18 aplicado al propio comprobador: un control adversario
que no reproduce la forma real valida el comprobador, no el caso.

---

## PRINCIPIO nº 32 — una clave sin escritor no falla: su valor por defecto pasa a ser la configuración

Sale de la errata nº 89 y merece entrada propia porque **no se parece a los fallos de
clave anteriores**.

La errata nº 47 —la comparación de md5 que preguntaba por una clave que no existía—
producía una **respuesta falsa**: «no se ha podido comprobar» con el fichero delante.
Ésta no produce ninguna respuesta falsa: produce **siempre el valor por defecto**, y
entonces pasa algo distinto y peor.

**El literal por defecto deja de ser un plan B y se convierte en la configuración real.**
Y nadie lo revisa como tal: se escribe pensando «esto es lo que pasa si falta», se lee
como una precaución, y es lo único que se ejecuta. Un `"sin fecha declarada"` puesto para
ser honesto acabó siendo el valor con el que se generaba **todos** los informes.

**Dos llamadores con dos defaults distintos son dos configuraciones distintas para la
misma cosa** — y ninguna de las dos está declarada en ningún sitio, así que no hay dónde
mirarlas juntas. Aquí una funcionaba y la otra abortaba, y eso es lo que hizo que el
fallo pareciera del zip y no de la fecha.

**La contramedida es mecánica y va en `tests/test_una_descarga_ROTA_no_tumba_la_pagina.py`**:
ninguna clave de `session_state` puede leerse sin que alguien la escriba. A cero, con
control adversario, y **quitando los comentarios antes de mirar** — el comentario que
explica de dónde venía la clave la nombra, y sin la poda el guardia fallaría por su propia
documentación, con la salida fácil de borrar la explicación (errata nº 54 con el signo
cambiado).

---

## 91 — «No se pidió» y «no se pudo» daban la misma celda vacía

**Reportado (2026-09-04)**: *«la columna `accesibilidad` sale vacía en las diez»*.

**No era un fallo del cálculo: la casilla «Calcular accesibilidad (lento)» está apagada
por defecto**, así que `accessibility=False` → `acceso = None` → celda vacía. Y ViennaRNA
sí está instalado (2.7.2 aquí, y `nixpacks.toml` lo mete en la imagen con comprobación en
el build). Lo que estaba mal es que **esa celda vacía era indistinguible de la de un
cálculo que se pidió y no pudo correr** — y son dos cosas que se arreglan con cosas
distintas: una marcando una casilla, la otra consiguiendo algo. **Y la primera ni siquiera
es un problema.**

Es la lección de `SIN_CONSULTAR` (errata nº 55) aplicada a una familia que no la tenía:
**los números comparativos**. No tienen columna de estado, así que el estado va **dentro
de la celda**, porque no hay otro sitio.

`FilterState.NO_PEDIDO`. No es `NO_APLICA` —esa dice «a este candidato no se le hace esta
pregunta», y aquí sí se le hace— ni `NOT_RUN`, que anuncia una laguna donde no la hay:
nadie pidió que se llenara.

### Y al revisar la familia salió un segundo caso, del mismo tipo

`carga_seed` acotada por coste (errata nº 59) salía **`NOT_RUN`**, y `NOT_RUN` manda a
conseguir algo. Ahí no hay nada que conseguir: acotar el conteo al panel es una
**decisión**, tomada y escrita, no una laguna. Pasa a `NO_PEDIDO`.

Las tres celdas quedan distinguibles: **vacía** (no aplica / no hay dato de fuera),
**`NOT_RUN`** (se pidió y faltó un recurso), **`NO_PEDIDO`** (nadie lo pidió). Ninguna es
cero, que sigue siendo la regla de siempre.

---

## 92 — La configuración no viajaba con el panel, y nada avisaba cuando dejaban de corresponder

**Preguntado y luego acotado por el responsable del proyecto (2026-09-04)**: *«¿los
ajustes se guardan en el proyecto o son sólo de sesión?»* y, después, *«la configuración
tiene que quedar ATADA al panel, no sólo guardada al lado»*.

**Los ajustes eran sólo de sesión, y no se decía.** `Project` tiene slug, fecha, md5,
longitud, especie, anatomía, título y secuencia — **ningún campo de configuración**. Y
`save_selection` guardaba `{"starts": [...], "by": ...}` y nada más. Umbrales,
`SelectionConfig`, accesibilidad y andamio viven en widgets de Streamlit y vuelven a su
valor por defecto al recargar. Es el `--inmunes 4` del golden (principio nº 18) **del lado
del usuario**: una configuración que produce un número y que no viaja con él.

**Guardarla al lado no habría bastado**, y ése es el punto que lo cierra: si alguien cambia
un umbral y vuelve a diseñar sin guardar selección nueva, el panel de la pantalla deja de
corresponder a la configuración registrada **y nada lo dice**. Va **atada por huella**
(`identidad.configuration_fingerprint`), y la discrepancia **se deriva** — exactamente lo
que hace `OBSOLETO` con los ficheros de una corrida: se hizo, y ya no vale con lo que hay
ahora.

**Y NO se restaura al reabrir. DECIDIDO.** Restaurar los controles desde el proyecto daría
**dos fuentes de verdad** en la barra lateral —lo guardado y lo que el widget diga— sin
nada que dijera cuál manda: es la casilla global «Usar los de `data/reference/`» otra vez.
Registrar sí; restaurar no. Hay un test mecánico de que la página no lee la configuración
guardada.

**Tres estados y ninguno se colapsa**: coincide (sólo se recuerda que los ajustes son de
sesión), **`CAMBIADA`** (aviso, y dice qué hacer: volver a la configuración o guardar
selección nueva), y **`NO_REGISTRADA`** para una selección anterior a este campo — *no
haber podido comprobarlo no es que coincida*, que es el `.out` sin resumen otra vez.

**Y una aclaración que sí es buena noticia**: marcar la accesibilidad **no exige volver a
pulsar «Diseñar»**. `st.session_state["accion"]` es pegajoso, así que cada repintado vuelve
a correr `page_run` con lo que la barra lateral diga en ese momento. Tardará, pero se
rellena.

**Lo que la propia maquinaria del proyecto cazó al escribirlo**: el cruce de auditorías
(principio nº 26) rechazó el digesto nuevo hasta declararlo en **las dos** tablas,
`magnitudes.toml` y `guardias.toml`. Y `guardias.toml` lo rechazó como guardia porque **no
aborta**: va a `[solo_informan]`, con `manifest.check_directory` y `stale_md5`.

---

## 93 — Dos servicios más, y una premisa que había que corregir con la medida

**Pedido (2026-09-04)**: añadir **siDirect** y **BLOCK-iT RNAi Designer** a la fila que ya
tienen miRarchitect, SplashRNA y el GPP Web Portal, comprobar si el GPP ya es el del
Broad, y proteger el cruce porque siDirect diseña **19-mers**.

### El GPP ya era el del Broad: comprobado antes de añadir nada

`GPP_URL` es `portals.broadinstitute.org/gpp/public/` y su descripción dice «Genetic
Perturbation Platform del **Broad**» desde que se escribió. **No se duplica.** Añadirlo
como entrada aparte habría puesto la misma herramienta dos veces con dos nombres, que es
como se acaba comparando una lista consigo misma y llamándolo convergencia. Hay test.

### LA PREMISA DEL CRUCE ERA FALSA, y va corregida con el número

Se pidió esto dando por hecho que los 19-mers **no cruzarían** «por identidad de
secuencia» y darían cero coincidencias. **Medido sobre el panel murino real: no es así.**
`guide_shift` no compara cadenas iguales — busca el desplazamiento con solapamiento
exacto de al menos `MIN_OVERLAP` — así que un 19-mer contenido en una ventana de 22 **sí
cruza**. De los **120** 19-mers que solapan ≥15 nt con alguna de las diez ventanas del
panel, los cruza **los 120**. Cero fallos.

**Y aun así había un defecto real, de otra familia.** `guide_shift` devuelve un
**desplazamiento**, y con longitudes distintas ese número **mezcla** cuánto está corrida
la ventana con cuánto más corta es la guía: un 19-mer perfectamente contenido en nuestra
ventana sale con un `shift = 2` y se lee como «ventana desplazada 2 nt» cuando no está
desplazada en absoluto. Es el **principio nº 27** — dos cantidades bajo el mismo nombre —
y de ese número cuelgan `DISPLACED_SHIFT` y `MIN_OVERLAP`, los dos **derivados de 22
contra 22**.

Así que el cruce por **solapamiento sobre la referencia** (`window_overlap`) entra igual,
pero por el motivo correcto: no porque el otro no cruce, sino porque **el número que
devuelve significa otra cosa**. Emite el solapamiento —una cantidad que sí quiere decir lo
mismo con cualquier longitud— y aborta si la guía aparece dos veces en la referencia,
porque entonces no identifica ninguna posición.

### La longitud es de primera clase, y la que no se sabe NO se inventa

Cada servicio declara `guide_length`, porque es **lo que decide cómo se cruza**.
miRarchitect y SplashRNA, 22. siDirect, **19** —lo dijo quien lo pidió—. **BLOCK-iT sale
`SIN DECLARAR`**: nadie ha dicho qué longitud produce, y escribir un número de memoria no
daría ningún error — daría un cruce con la forma correcta sobre el candidato de al lado.
Es la regla 4 un nivel más abajo: no es una URL, pero es un dato de un servicio ajeno.

`check_guide_lengths` **aborta** si llegan longitudes distintas de las declaradas, y el
mensaje dice por qué importa: importarlas igual no daría error, daría **cero cruces**, y
cero cruces se lee como «no hay convergencia» — una conclusión sobre la biología sacada de
un desajuste de formato. Vive **dentro de `merge_scores`**, no en el CLI: allí la tendría
un solo llamador y el segundo que cruce se queda fuera (el patrón de `page_run`, ya siete
veces).

### Las direcciones que nadie ha aportado salen VACÍAS y diciéndolo

Las tres primeras las dio el responsable del proyecto. Para las dos nuevas no hay
dirección aportada, y **desde aquí no se puede verificar ninguna**: comprobado hoy, las
dos URL conocidas dan **403 en el CONNECT del proxy**, que es política de red y no una
respuesta del servicio. Regla 4: si no lo has comprobado, no lo escribas. Salen con
`URL_NOT_PROVIDED`, que dice qué falta y quién lo aporta — un hueco en blanco se lee como
un fallo de formato y no manda a nadie a ninguna parte.

### Y ninguna de las dos ORDENA nunca

`NEVER_ORDERS`, con el motivo escrito: diseñan siRNA —otra modalidad, otra longitud— así
que su número no puntúa el procesamiento de una horquilla miR-E. Entran como
**convergencia de sitio**, con la misma degradación que un score medido sobre otro
andamio, y la etiqueta los distingue: `_CONVERGENCIA_DE_SITIO_NO_ORDENA` frente a
`_andamio_..._NO_ORDENAR`. Uno podría ordenar el día que se puntúe con nuestro andamio; el
otro no va a ordenar nunca, y son dos cosas.

**No pasan por `lower_is_better`**, que abortaría — y no abortaría por un fallo: abortaría
porque su dirección no está registrada, y ahí **no falta ese registro, sobra la pregunta**.
Registrarla daría a entender que algún día ordenarían.

### La decisión de no usarlas como fuente principal, ESCRITA

`WHY_NOT_PRIMARY`, en la sección de Limitaciones del informe con la tabla de longitudes al
lado. Dos motivos: **no declaran qué no han comprobado** —un sitio que no sale no se
distingue de uno que no miraron, que es justo por lo que aquí todo filtro emite `NOT_RUN`
con su motivo— y **ninguna considera la poliadenilación alternativa**, que en este 3'UTR
condiciona a seis de los diez candidatos. Un servicio que nadie miró y uno que se miró y se
descartó se leen igual si lo único que hay es su ausencia.

---

## 94 — La guía se re-recortaba de una secuencia que pasaba la página, y el aborto era la mitad afortunada

**Reportado (2026-09-04)** con el panel guardado delante:

    PARA — La guía mide 0 nt y el andamio miR-E lleva brazos de 22 nt

**La causa.** `build_constructions` sacaba la guía con `target[start - 1:end]`, y la
página le pasaba el **3'UTR** (1242 nt) mientras los `start` del panel van en el marco de
**LO TILADO**, que es el transcrito (2191 nt). Medido sobre el panel murino real:

| start | `utr3[start-1:end]` | qué sale |
|---|---|---|
| 959, 1009, 1092, 1149 | **22 nt** | **la guía de OTRO SITIO**, con md5 correcto |
| 1398, 1502, 1601, 1684, 1768, 1967 | **0 nt** | aborta |

**El aborto era la mitad afortunada.** Cuatro de las diez construcciones se habrían
montado con la guía equivocada y habrían salido hacia SpliceAI sin que nada lo dijera;
sólo cayeron las seis que se salen del 3'UTR. **Con un panel entero dentro de los primeros
1242 nt, esto no habría dado ningún error nunca.**

### Por qué ningún test lo veía

Todos los del modal tilan el **3'UTR solo**, y ahí el marco de lo tilado ES el 3'UTR, así
que `target=utr3` coincidía con los `start`. La página tila el **transcrito entero** con su
anatomía, como el CLI. Es el principio nº 18 otra vez: los artefactos de verificación
corrían con una configuración que la app no usa.

### El arreglo es el principio nº 13, no un cambio de argumento

La guía **ya está calculada** en la ventana de la selección. Volver a recortarla de una
secuencia que pasa el llamador es una segunda definición del mismo dato — y con un `start`
que no lleva marco, **cualquier secuencia sirve de argumento y ninguna se puede
comprobar**. Ahora se pide a la ventana, y **`target` se retira**: un parámetro que sólo
podía traer la secuencia equivocada no se arregla documentándolo (principio nº 33).

### Y las otras dos cosas del reporte, las dos ciertas

**El mensaje describía el síntoma como si fuera la causa.** «La guía mide 0 nt» invita a
buscar una guía mal formada; lo que había era una guía **que no ha llegado**. Ahora nombra
**el candidato** y **de dónde se intentó leer** —su ventana en la selección, no el
andamio—, que es donde hay que mirar.

**Y un fallo en una construcción tumbaba las veinte.** El error salía antes del FASTA, así
que un candidato sin guía bloqueaba la corrida entera. `build_panel` devuelve **las dos
mitades**: lo que se pudo montar y lo que no, con su motivo por candidato × intrón, y la
página pinta el aviso sin dejar de emitir el resto. Lo que sí aborta es que no salga
**ninguna** — cero construcciones no es una entrega parcial: no hay nada que consultar.

### El contexto por defecto era el que la propia app desaconseja

Estaba en **0**, y con 0 el contexto son las dos piezas de 5 nt que `context_note` califica
de «esencialmente NINGÚN contexto para un modelo entrenado con ventana de 10.000». **Un
valor por defecto que la app avisa de que no sirve es una trampa, no un defecto.** Pasa al
tope del control (`SPLICE_CONTEXT_DEFAULT`): con el casete cargado el contexto sale de
secuencia real —hasta 3133/2067 nt, el plásmido entero— y pedir más del que hay **no lo
inventa** (regla 1). Sin casete se cae solo a las piezas, con su aviso, que es el mismo
sitio de antes pero por haberlo intentado.

---

## 95 — El barrido de la errata nº 94: había un segundo, vivo

**Pedido en el momento**: *«si `build_constructions` recortaba con el marco equivocado,
busca todos los sitios donde se recorte una secuencia con un start del panel»*.

**Lo había: `presentation.splice_module_of`.** Hacía
`target[construction.candidate_start - 1 : +22]` con `target` pasado por la página, o sea
el mismo fallo por un segundo camino — la tabla de **accesibilidad estructural** del modal
montaba el módulo con la guía de otro sitio, con la forma correcta y sin ningún error.
Arreglado igual: **pide la guía a la ventana** (`spliceai.guide_of`).

### El criterio del barrido, y por qué éste distingue

Recortes 1-based en el paquete: **50**, y casi todos correctos —la seed sobre su propia
guía, el 3'UTR sobre su propio transcrito, un plásmido sobre sus propias coordenadas—. Lo
que separa al fallo **no es la forma** `x[start - 1:end]` sino **de dónde vienen las dos
cosas**:

| criterio | hallazgos | de ésos, fallos |
|---|---|---|
| cualquier recorte indexado por un `.start` ajeno | **10** | 1 |
| **la secuencia y la posición son DOS PARÁMETROS distintos de la misma función** | **1** | **1** |

En los correctos la posición **se deriva** de la secuencia que se recorta: `Span.of` sobre
algo que se acaba de buscar ahí, o dos campos del mismo objeto (`self.plasmid` y
`self.start`). En el fallo llegan por separado, y entonces **nada obliga a que compartan
marco**. Cero falsos positivos con el criterio fino, así que es un guardia aplicable.

### Y los que se sospechaban están limpios

`blocks.py` y `gblock.py` —el generador de módulo y la hoja de pedido— **no recortan
nada**: reciben la guía ya hecha. No aparecen en el barrido por eso, y es la razón de que
no estuvieran afectados.

### El corolario, que es el que generaliza

**Un `start` sin marco declarado no puede indexar una secuencia que llega por otro lado.**
`coords.Position` ya impide **imprimir** un entero desnudo; esto impide **indexar** con uno.
Guardia, no trinquete: el número correcto es cero, con control adversario sobre la forma
**real** que tenían los dos fallos (principio nº 18 aplicado al comprobador).

### Y por qué esta familia es peor que las cuatro confusiones de marco anteriores

Las de `3utr:1784`, `3utr:1185`, `3utr:1398` y el mapa producían **una etiqueta mal
escrita**: un número en el sitio equivocado de una salida que alguien lee. Ésta produce
**ADN que se manda a analizar** — un módulo de 149 nt con la guía de otro sitio, con su md5
correcto, camino de SpliceAI. Y habría **validado al volver**, porque la validación
comprueba que el md5 del resultado cuadre con el de la construcción que se entregó: la
construcción equivocada es consistente consigo misma.

---

## 96 — La regla del desempate existía y el modal no la aplicaba: la NOVENA del patrón

**Pedido (2026-09-04)**: declarar el desempate de `mvm_sin_criptico` como regla y
**aplicarla por candidato**, emitiendo qué base salió y si hubo empate.

**Al ir a escribirla resultó que ya estaba.** `intron_design.TIEBREAK_MOTIF`,
`TIEBREAK_RATIONALE` con las palabras de quien la decidió, `TIEBREAK_REJECTED` con el
motivo de descartar `GTGCGCG`, y `apply_tiebreak` **abortando** si la decisión registrada
no está entre las que empatan — que es la salvaguarda de «para y pregunta», escrita hace
semanas. Lo que faltaba era **el consumidor**: `variant_proposal_for` resolvía **el primer
candidato** y el modal enseñaba ese texto y nada más.

**Es la NOVENA vez del mismo patrón** —`triple_motive_rows`, `intron_folding`,
`store.save_*`, `page_run`, el `stores=` de `site_table_rows`, las tres tablas de la
errata nº 55, la dimensión guía/pasajera, las cuatro `carga_<clase>` que no llegaron al
TSV— y a estas alturas **no es una serie de casos aislados: es la forma en que este
proyecto falla.** La capacidad se escribe, se prueba, se documenta, y el sitio donde
serviría no la llama. Ninguna de las herramientas la caza sola: la alcanzabilidad no la ve
si hay algún llamador (aquí lo había, `design_variant`), el golden lee lo que se emite, y
lo emitido tenía la forma correcta.

### La tabla, medida ANTES de aplicar nada

| candidatos | estado | alternativas que empatan |
|---|---|---|
| los **diez** (959, 1009, 1092, 1149, 1398, 1502, 1601, 1684, 1768, 1967) | **EMPATE (2)** | **`C@4`, `T@4`** |

Los diez empatan, y siempre entre **las mismas dos** — exactamente el par sobre el que se
decidió con la guía de `3utr:60`. Ninguno queda sin empate y ninguno empata entre
alternativas distintas de T/C, así que **ninguna de las dos salvaguardas llega a
dispararse**. La regla aplica limpia a los diez.

### Y la columna sale aunque el resultado repita

`empate` y `base` van en **cada fila** de `presentation.variant_rows`, con el criterio
pegado —la app **no lo mide**, y un valor que sale sin decirlo se lee como si lo hubiera
medido—. El resultado es idéntico en los diez, así que emitirlo parece redundante y es al
revés: **el día que entre un candidato que no empate, esa columna es lo único que lo
dirá.** Un valor constante que se calcula y no se enseña es indistinguible de uno que
nadie ha mirado.

### Y una prosa que se quedó atrás

`introns.INTRONS["mvm_sin_criptico"].why_missing` decía «el primer paso EMPATA … **y la
app no elige: hace falta una decisión**». Cierto cuando se escribió y **falso desde que la
decisión se registró**. Principio nº 11. Ahora dice lo que de verdad falta, que no es la
decisión: es que la variante **se monte como intrón de esta corrida**, que es el paso
siguiente y no está hecho — la corrida sigue en 20 pares, no en 30.

---

## 97 — La app anunció 20 pares, emitió 10, y no dijo que faltaba la mitad

**Reportado (2026-09-05)**: con los dos intrones marcados y alcance «el panel — 10
candidatos, **20 pares**», el FASTA trae **10 registros**. *«La propia app anunciaba 20
pares y ha emitido 10, sin avisar de que faltaba la mitad.»* Y la pregunta correcta: *«que
no aparezca ni montado ni fallido es peor que cualquiera de las dos cosas»*.

**El núcleo hacía lo correcto, comprobado**: `build_panel` con los dos devuelve **10
construcciones y 10 fallidas**, cada una con su motivo — `intron_quimerico` llega entero
de su plásmido y **no declara dónde va el módulo**, que es una carencia conocida y
declarada, no un fallo nuevo. Lo que estaba mal es lo que la página hacía con las dos
mitades.

### Cuatro defectos, y el peor es el que viaja

1. **La cuenta MENTÍA.** `len(construcciones) // len(elegidos)` da `10 // 2 = 5`, así que
   se imprimía «10 consulta(s) = **5 candidato(s)** × 2 intrón(es)». **Ese 5 no existió
   nunca**: son 10 candidatos por 1 intrón que se pudo montar. Un número derivado que
   mezcla lo pedido con lo obtenido y sale con la forma correcta.
2. **Nada reconciliaba lo anunciado con lo emitido.** El selector de alcance dice 20 —de
   `10 × 2`, calculado antes de montar nada— y el resultado dice 10. **Dos contadores del
   mismo suceso sin nada que los ate**, que es un patrón que este proyecto ya tiene
   escrito. Ahora los dos salen de `splice_panel_summary`, que es la única forma de que no
   puedan discrepar.
3. **Diez avisos idénticos.** El fallo es **del intrón**, no de cada candidato: repetir el
   mismo motivo diez veces es exactamente lo que hace que se lea como ruido en vez de como
   «falta media corrida». El desglose pasa a ser **por intrón**, una línea cada uno.
4. **Y el FASTA no decía que fuera parcial.** Es el que **viaja**: quien lo descarga y lo
   pasa por SpliceAI no tiene la pantalla delante. Media entrega con un nombre que no lo
   dice parece completa. El estado va **en el nombre** —
   `construcciones_mouse_PARCIAL_10de20.fa`— igual que en el informe.

### Lo que NO se ha podido determinar, y por eso no se le asigna causa

Por qué no vio ningún aviso. Con el código actual habría visto diez, y con el anterior a
la errata nº 94 no habría obtenido FASTA ninguno —el montaje del quimérico abortaba la
corrida entera—, así que **ninguna de las dos versiones produce exactamente lo descrito**.
Puede ser que los diez avisos idénticos pasaran por ruido, que es justo lo que el defecto
nº 3 produce. No se declara: los cuatro defectos de arriba son ciertos y están arreglados
con independencia de eso.

## 98 — `10 // 2 = 5`: un número derivado que mezcla lo PEDIDO con lo OBTENIDO

Es el defecto nº 1 de la errata nº 97, y se saca aparte porque **la lectura vale más que
el arreglo**: *«ese 5 no existió nunca: son 10 candidatos × 1 intrón montable. Un número
derivado que mezcla lo pedido con lo obtenido y sale con la forma correcta es la familia
del 405 — dos magnitudes distintas cuya composición da algo plausible.»*

### La cuenta

```python
f"{len(construcciones)} consulta(s) = {len(construcciones) // len(elegidos)} "
f"candidato(s) × {len(elegidos)} intrón(es)"
```

Con 10 construcciones y 2 intrones marcados: `10 // 2 = 5`, y la página imprimía **«5
candidatos × 2 intrones»**. Ninguna de las dos cifras describe nada real:

| lo que dice la línea | de dónde sale | qué es de verdad |
|---|---|---|
| 5 candidatos | `len(construcciones) // len(elegidos)` | **10** candidatos, y los diez estaban elegidos |
| 2 intrones | `len(elegidos)` — lo **pedido** | **1** intrón montable; el otro dio 0 de 10 |

`len(construcciones)` es lo **obtenido**; `len(elegidos)` es lo **pedido**. El cociente no
es ninguna de las dos cosas, y **el producto vuelve a cuadrar** —5 × 2 = 10— así que la
línea es internamente consistente y por eso no chirría.

### Por qué es la familia del 405

El 405 de este proyecto era el mismo mecanismo: dos magnitudes distintas cuya composición
da un número plausible. Aquí la composición es exacta y eso lo empeora — un número que
**no cuadra** se mira; uno que cuadra por construcción, no. La firma de la familia:

- **hay dos magnitudes**, una de la petición y otra del resultado;
- **se combinan con una operación que las hace conmensurables** —una división, una suma—
  cuando no lo son;
- **el resultado tiene la forma esperada** (un entero pequeño, un porcentaje, un total);
- **y nada compara la salida con ninguna de las dos entradas**, así que el error no tiene
  dónde aparecer.

Es la misma raíz que `carga_seed`, la suma prohibida (errata nº 90): una operación
aritmética entre cantidades que no son de la misma clase. Allí eran tres sumandos de
clases distintas; aquí son el numerador y el denominador.

### El arreglo, y lo que lo hace estructural

No es cambiar la fórmula: es que **la cuenta y el fichero salgan del mismo sitio**.
`splice_panel_summary` deriva lo anunciado (`candidatos × intrones`) y lo emitido
(`len(panel.constructions)`) **por separado y sin componerlos**, y los enseña uno al lado
del otro. Un número que mezcla las dos no puede existir porque ya no hay ninguna
operación que las junte.

Hay regresión escrita (`test_el_panel_dice_CUANTAS_faltan.py`) que además comprueba que la
división no ha vuelto a la página.

## 99 — Dos convenciones de posición para el mismo sitio, y `2e-07` no es cero

**Medido y reportado (2026-09-05)**, con la primera corrida real de SpliceAI sobre las diez
construcciones: *«la app declara `donante=3134` y el pico está en 3133; declara
`aceptor=3428` y el pico está en 3430»*.

```
donante   app → la G de GT      SpliceAI → última base exónica   → donante − 1
aceptor   app → la A de AG      SpliceAI → primera base exónica  → aceptor + 2
```

**Ninguno de los dos está mal.** Son dos convenciones, y hasta esa corrida sólo una de
ellas estaba escrita en alguna parte — la nuestra, y sólo como número, sin decir a qué
base apuntaba.

### Lo que lo convierte en errata: la salvaguarda no mordió

`scan_from_result` aborta si el donante legítimo *«no viene puntuado o vale cero»*. En la
posición equivocada la puntuación es **`2e-07`**. No es cero. Así que el guardia dejó
pasar un análisis entero —**107.680 filas**— normalizado contra un referente inexistente,
y todo lo que salió de ahí (fracciones, crípticos, avisos) era aritméticamente correcto
sobre el dato equivocado.

Es el principio nº 33 con otra cara: *el guardia estaba, y el número que le llegaba pasaba
por encima de su criterio*. Un `<= 0` sólo atrapa el caso en que el modelo no dice nada; no
atrapa el caso en que dice algo **sobre otra base**.

### El guardia nuevo, calibrado midiendo (principio nº 34)

No hay umbral que poner —en este módulo los absolutos están prohibidos y con razón—, así
que el criterio es **relativo y sin número**: *la base declarada tiene que ser el máximo de
su propio vecindario (±3)*. Medido sobre las diez:

| | posición declarada | mejor vecina en ±3 | relación |
|---|---|---|---|
| marco bueno (3133 = 3134 − 1) | **0,664 – 0,871** | ≤ 1,1e-05 | ≥ 6·10⁴ a favor |
| marco ajeno (3134) | **2,0e-07** | 0,664 | 3·10⁶ **en contra** |

Cuatro órdenes de margen por el lado bueno y seis por el malo: la separación es tan grande
que no hace falta elegir ningún corte, sólo preguntar cuál es el máximo. `FRAME_RADIUS = 3`
porque el desplazamiento mayor entre las dos convenciones es `+2`.

Y emite **estado**, no un booleano: `FAIL` aborta nombrando el desplazamiento hallado y,
si coincide con el de SpliceAI, cómo declararlo; `NOT_RUN` cuando el fichero no trae
vecinas que comparar —**que no es lo mismo que cuadrar**, y decirlo es literalmente el
principio nº 33.

### Lo que ahora viaja con los datos

1. **La cabecera del FASTA declara la convención, no sólo la posición**:
   `donante=3134(G de GT) aceptor=3428(A de AG) convencion=app spliceai_donante=3133
   spliceai_aceptor=3430`. Quien escriba el siguiente puente **no tiene que medirlo**, que
   es exactamente lo que costó esta corrida.
2. **El resultado puede declarar la suya** con una línea `# convencion: spliceai`, y
   entonces se traduce **en la frontera** (`parse_result`), de modo que dentro del módulo
   sólo existe una convención. Una convención desconocida **no se adivina**: aborta.

### La comprobación que no depende de ninguna puntuación

Hay una verificación independiente y es la más fuerte de todas: **traducidas, las
posiciones caen sobre el dinucleótido**. `donante → GT`, `aceptor → AG`, las diez
construcciones y también los crípticos —el del contexto que SpliceAI da en 1516 es, en
nuestra convención, la `G` de un `GT` en **1517**—. Si el desplazamiento fuera otro,
caerían en cualquier sitio. Está escrito como test.

## 100 — El consenso posicional SOBRESTIMA: el `GTGAGCG` empataba 5-5 y puntúa cero

**Medido (2026-09-05)**. El criterio de secuencia de este proyecto decía que el donante
críptico del flanco 5' de miR-E, `GTGAGCG`, **empataba con el donante legítimo**: 5 sobre
5 contra el consenso `MAG|GTRAGT`. Un modelo entrenado sobre intrones reales **no lo
considera donante en absoluto**.

| | las diez construcciones |
|---|---|
| donante legítimo (nuestro 3134) | 0,664 – 0,871 |
| `GTGAGCG` (nuestro 3232) | **4,0e-08 – 3,1e-07** |

No es «bajo»: es cero a efectos prácticos, seis órdenes por debajo. Y en toda la zona del
intrón sólo hay **otra** posición que pase de 0,01: la 3352 en la convención de SpliceAI,
con **0,046** en el peor caso y 0,003 en el mejor.

### Que quede escrito

**El consenso posicional sobrestima porque cuenta coincidencias sin contexto.** Un
`GT` con las bases «buenas» en las posiciones «buenas» puntúa alto en una matriz que sólo
mira esas posiciones; el modelo mira miles de nucleótidos alrededor y decide otra cosa. Y
aquí **las dos herramientas discrepan de forma limpia** —no es un margen, es 5/5 frente a
1e-07—, así que no hay forma de leerlo como ruido.

Esto no jubila el criterio de secuencia: sigue siendo lo único que corre sin nada
instalado y sigue sirviendo para **enumerar candidatos a mirar**. Lo que no puede hacer es
**afirmar que un sitio es un donante**, que es como se estaba leyendo.

### La consecuencia de proyecto

`mvm_sin_criptico` **baja de prioridad**. Se diseñó para romper un `GTGAGCG` que, medido,
no compite con nada. **Se construye como CONTROL, no como arreglo**: sigue teniendo valor
—demuestra que romper el motivo no rompe el splicing— pero deja de ser una respuesta a un
riesgo, porque el riesgo no se ha podido medir en ninguna de las diez.

## 101 — El estado del panel iba sólo en el NOMBRE del fichero

La errata nº 97 puso el estado en el nombre: `construcciones_raton_PARCIAL_10de20.fa`.
Bien, e insuficiente: *«un nombre se pierde en el primer `mv` — a mí me pasó hoy mismo
renombrando el fichero para quitarle un espacio. Lo que viaja pegado a los datos
sobrevive; el nombre no.»*

El FASTA es lo que sale de la app y **viaja solo**: se renombra, se mueve, se mete en un
ZIP, se adjunta a un correo, se sube a otra máquina. En cada uno de esos pasos el nombre es
lo primero que se pierde, y el contenido no.

Ahora el estado va en **tres sitios a la vez**, y los tres a propósito:

| dónde | sobrevive a | lo tira |
|---|---|---|
| el nombre del fichero | nada | un `mv` |
| el bloque `#` de cabecera | renombrar, mover, comprimir | un lector de FASTA estricto |
| **cada línea `>`** | **todo lo anterior** | nada que siga leyendo FASTA |

Por eso se repite: el bloque de comentario es el que se lee cómodo, y la cabecera `>` es
la que no se puede perder. Y hay un límite explícito — **sin `summary` no se declara
ningún estado**: un fichero que no sabe de qué panel viene no puede decir «COMPLETO», que
sería inventar la mitad tranquilizadora.

## 102 — El frente que NO se cierra aquí estaba en la cuadrícula, y sumaba en el contador

**Reportado (2026-09-05)**: *«la tarjeta del empalme del intrón no se quita, pero no puede
parecerse a las otras siete. Es el único frente que no se cierra con ningún fichero y el
único binario: si el intrón no se escinde, no hay proteína DN, y ninguno de los otros ocho
lo detecta. Hoy está en la misma cuadrícula, con el mismo aspecto y el mismo "Cómo se
hace", así que se lee como una comprobación pendiente más — y alguien puede concluir que
sobra por no encajar con lo que hace la app»*.

### Dos cosas, y la segunda es aritmética

1. **Mismo aspecto.** Tarjeta idéntica, en la misma rejilla de dos columnas, con el mismo
   desplegable. Nada en pantalla decía que ese frente no se cierra aquí.
2. **Mismo contador.** `front_progress` contaba **todas** las tarjetas, y este frente
   **siempre bloquea** —`blocking_fronts` lo emite con `blocking=True` por construcción,
   porque no hay nada en la app que pueda cerrarlo—. Así que el máximo del contador era
   **INALCANZABLE**: «8 de 8» no podía salir nunca, y nadie podía saber por qué.
   **Eso tiene errata propia, la nº 105**: es otra familia —un contador bien calculado y
   mal acotado, que no se contradice con nada— y aquí se leía como una consecuencia de la
   presentación.

Un contador que no puede llegar a su máximo no mide progreso: mide una distancia a un
sitio al que no se va. Y mezclaba dos cosas que se resuelven de forma distinta —una
descarga y una tanda de laboratorio— en el mismo denominador.

### El arreglo, y por qué no es una lista en el código

Cada ficha declara **dónde se cierra su frente** (`se_cierra_en = "la app"` /
`"el banco"`), y de ahí sale todo: la bandera `cierra_aqui` de la tarjeta, el encabezado
propio, y qué entra en el contador. **La página no nombra ningún frente** y hay un test
mecánico de ello: el día que haya un segundo frente de banco, sale aparte sin tocar la
interfaz (principio nº 31).

### Y `sin_fichero` NO servía para derivarlo — significa dos cosas opuestas

Era la tentación evidente: `empalme_intron` ya declaraba `sin_fichero = true`. Pero
`intron_sin_criptico` **también**, y ahí quiere decir lo contrario: *«no se consigue: SE
DISEÑA — la app lo deriva de `mvm_actual`»*. Derivar el banco de esa clave habría sacado
de la cuadrícula un intrón que la app resuelve sola.

Es el principio nº 27 en un fichero de datos, donde ningún auditor lo mira: el de
homónimos recorre propiedades derivadas de Python, no claves de TOML. La clave nueva es
explícita, **de vocabulario cerrado**, y **sin valor por defecto** — un frente de banco al
que se le olvide la línea aborta al cargar la ficha, en vez de entrar en la cuadrícula sin
que nadie lo vea (principio nº 32).

### Lo que había en dos sitios

`informe_doc.BENCH_FRONTS = frozenset({"empalme_intron"})` estaba escrito a mano **y** la
prosa de la ficha decía lo mismo con otras palabras. Dos definiciones del mismo hecho, y
la que se usaba no era la versionada. Ahora `BENCH_FRONTS` se **deriva** de las fichas, con
test de que las dos coinciden.

## 103 — Un frente CERRADO seguía mandando a conseguir lo que ya tenía

**Reportado (2026-09-05)**: *«el de `fraccion_isoforma_larga` está en verde, con
`polya_db_mouse.tsv` cargado, y aun así muestra instrucciones para conseguir un fichero que
ya está — incluido `apa_medido.tsv`, que la propia app marca como "no hace falta
conseguir"»*. Y el diagnóstico, que es el que ordena el arreglo: **es el `why_missing` que
envejeció, en su versión de interfaz — un texto correcto cuando se escribió que hoy manda a
hacer algo ya hecho.**

### Era GENERAL, no de ese frente

El texto lo emite `Ficha.render()`, y empezaba **siempre** por `COMO CERRAR EL FRENTE
«x»`, con `FICHERO(S) QUE HACEN FALTA` y `PASOS:` detrás. Lo pinta la tarjeta de **todos**
los frentes, así que el defecto lo tenían los cuatro cerrados de la corrida murina, no uno.
Se comprobó como se pidió, y hay test de que ningún frente cerrado vuelve a decirlo.

### Tres estados, y ninguno puede enseñar lo del otro

| estado | encabezado | el desplegable se llama |
|---|---|---|
| abierto | `COMO CERRAR EL FRENTE «x»` | Cómo se consigue |
| **cerrado** | `CÓMO SE CONSIGUIÓ CERRAR EL FRENTE «x» (referencia)` | **Cómo se consiguió (referencia)** |
| de banco | `QUÉ HAY QUE MEDIR EN EL BANCO PARA CERRAR «x»` | Qué hay que medir en el banco |

Cambia el **tiempo verbal**, no el contenido: los pasos se quedan enteros porque son la
**procedencia** de lo que se cargó, y quitarlos dejaría un frente cerrado sin poder decir
con qué se cerró. De ahí «(referencia)».

### Y lo que va DELANTE cambia con el estado

Ése es el fondo del asunto, con las palabras del reporte: *«cuando el frente está cerrado,
lo que va delante es el resultado; la ficha de obtención se queda accesible pero plegada»*.
El motivo —«CERRADO. 6 de 10 candidatos quedan por detrás del corte…»— vivía **dentro** del
desplegable, junto a las instrucciones. Ahora sale fuera y en verde, y la ficha se pliega
detrás con su título en pasado.

### La causa de que nadie lo viera: había DOS fuentes

La tarjeta calculaba su estado con `closed_by_panel` y el motivo y la ficha llegaban por
`front_help_rows`, **calculada aparte y sin ese argumento**. O sea que una tarjeta podía
salir **en verde** con el motivo y la ficha del frente **abierto** al lado, y las dos con
pinta de dato. Ahora las trae la propia tarjeta —una sola fuente— y `_tarjetas_de_comprobacion`
ya no recibe el tilado ni la selección, que era lo que pedía la segunda.

## 104 — El hallazgo estaba en la corrida y salía como una nota

**Reportado (2026-09-05)**: *«el aceptor de 3263 es el hallazgo de la corrida y hay que
tratarlo como tal, no como una nota. Es el único sitio que depende de la guía en las diez
construcciones — literalmente lo que ese frente existe para encontrar»*.

No es una errata de cálculo: el número estaba bien y **estaba en el sitio equivocado de la
jerarquía**. Un dato que contesta la pregunta del frente no puede salir con el mismo peso
que el resto de la tabla.

### Lo medido, y por qué el `GTGAGCG` no era esto

Este modal existe por el donante críptico del andamio. Medido: puntúa **cero en las diez**
(4e-08 a 3e-07). El que sí depende de la guía es otro, y no lo había buscado nadie:

| sitio (nuestra convención) | región | máximo | del donante legítimo | listado en |
|---|---|---|---|---|
| **aceptor `construccion:3261`** | intrón, dentro del módulo | 0,0751 | **11 %** | 1 de 10 |
| donante `construccion:3353` | intrón | 0,0459 | 7 % | 1 de 10 |
| donante `construccion:1517` | contexto 5' | 0,766 | 112 % | 10 de 10 |

El tercero es el más fuerte de la molécula y **no es un hallazgo**: viene con el plásmido,
está en las diez y varía un 3 %. El primero es diez veces más débil y **es el hallazgo**,
porque cambia con el módulo.

### `exclusive_rows` no podía cazarlo

Aquella pregunta si un críptico está en una construcción y en **ninguna** de sus hermanas.
Este aparece en dos de diez sobre el dato crudo, así que no es exclusivo de nadie. La
pregunta correcta no es «¿es exclusivo?» sino **«¿cuánto se mueve?»** — la versión continua
de la misma idea. `guide_dependent_sites` la contesta, con un criterio que es una **razón
entre hermanas** (2×, declarado) y no un corte absoluto: un sitio que dobla dice algo
aunque los dos números sean pequeños, y uno que no se mueve no dice nada aunque sea el más
alto de la molécula.

### Y una celda vacía no es un cero

Un sitio por debajo del umbral relativo **no entra** en la lista de crípticos de esa
construcción, así que de ahí no hay medida. Poner `0,0000` afirmaría una que no se tiene:
va `None`, y el texto dice «listado en 1 de 10; en las demás por debajo del umbral
relativo, que NO es cero». Misma regla que un número comparativo sin calcular.

### El efecto general, que tampoco se esperaba

El **donante legítimo** —el mismo sitio en las diez— va de **0,664 a 0,871**: un **31 %**,
con el módulo a más de 100 nt. Sale como columna (`donante_vs_hermanas`), con su tabla por
intrón y ahora también destacado. El contraste es lo que le da sentido: el sitio del
contexto se mueve un 3 %.

## 105 — Un contador con el máximo INALCANZABLE no informa de nada, y parece que informa

**Reportado (2026-09-05)**: *«el contador con máximo inalcanzable merece errata propia.
"10 de 10" no podía salir nunca y nadie podía saber por qué — un número cuyo tope es
imposible no informa de progreso, informa de nada, y encima parece que informa. Es
distinto de un contador que miente: éste era correcto y estaba mal acotado»*.

Sale de la errata nº 102 y se separa a propósito: allí el hallazgo es que el frente del
banco se leía como una comprobación pendiente más. Esto es **otra cosa y otra familia**, y
mezclado con aquello se leía como una consecuencia de la presentación.

### La distinción, que es todo el punto

| | qué le pasa al número | cómo se ve | cómo se caza |
|---|---|---|---|
| un contador que **miente** | el numerador o el denominador están mal calculados | dice 5 donde hay 10 | cruzando con la otra cuenta del mismo suceso |
| un contador **mal acotado** | los dos números están **bien** | dice «4 de 8» y es verdad | **no se caza mirando el número** |

Aquí ninguna de las dos cifras era falsa. `front_progress` contaba las tarjetas que había
y las que estaban cerradas, y las dos eran ciertas. Lo que no existía era el **estado
final**: `empalme_intron` sale de `blocking_fronts` con `blocking=True` **por
construcción**, porque no hay nada en la app que pueda cerrarlo. Así que «8 de 8» no era
improbable ni difícil: era **imposible**, y nada lo decía.

### Por qué es peor que un contador que miente

Un contador que miente se contradice con algo: hay otra cuenta del mismo suceso, o una
tabla al lado, y en cuanto se ponen juntas salta —así se cazó la errata nº 97, y por eso
la contramedida de aquélla fue derivar las dos de lo mismo—. **Un contador bien calculado
y mal acotado no se contradice con nada.** Cada cifra es correcta por separado y la
propiedad rota —«el máximo se puede alcanzar»— no la comprueba nadie, porque nadie la
enuncia: se da por supuesta al escribir la barra.

Y produce el síntoma más caro que hay en este registro: **el silencio con forma de dato**.
Quien lo mira ve una barra que no llega al final, concluye que le faltan cosas por hacer,
y va a buscar la que falta. La familia del «Alu 0 %» y de la errata nº 24 — una salida que
parece una medida y no se refiere a nada.

### La regla que deja

**Todo contador declara qué hace falta para llegar a su máximo, y algo lo comprueba.** Si
el máximo depende de un estado que ninguna acción disponible produce, ese elemento no va en
ese denominador: va aparte, y se dice por qué. La comprobación es mecánica y no una
revisión —`test_el_frente_del_BANCO_va_aparte.py` exige que el total del contador sea
alcanzable, o sea que exista una combinación de estados que lo iguale—, porque una
propiedad que nadie enuncia es una propiedad que nadie mira.

### Y no se arregla subiendo el numerador

La salida cómoda era contar el frente del banco como cerrado —o darle un estado
«resuelto»—. Eso convierte un contador mal acotado en uno que **miente**, que es la
categoría de al lado y peor. Lo que se separa del denominador no desaparece de la pantalla:
sale con su encabezado propio, diciendo que no se cierra aquí.

## 106 — `inserted` era una constante global sobre dos intrones que insertan distinto

**Salió el 2026-09-05**, al comparar las dos arquitecturas: se dio como contrapeso del
quimérico que su donante→punto de ramificación es de **314-318 nt** frente a los 256 del
MVM, o sea 58-62 nt peor. **Medido sobre el intrón que de verdad se monta, son 249-253**:
el quimérico no es peor en ese eje — empata, y por unos pocos nucleótidos incluso queda por
debajo.

### RETIRADO POR JOAQUÍN CASTILLA, y va con su nombre a petición suya

*«El contrapeso lo retiro entero. Apliqué al quimérico los 214 nt del MVM sin comprobar que
el quimérico se monta sin espaciadores. La diferencia era exactamente 65 = 20 + 45 — la
errata 35, cometida por mí esta vez»*.

Va anotado con su nombre por la misma razón que la predicción refutada de la carrera de A y
que la rectificación del rol de `apa_medido.tsv`: **si sólo se anotan las rectificaciones
ajenas, el registro deja de ser un registro y pasa a ser un argumento.**

**Consecuencia, y está en el informe**: el quimérico **gana en todo lo medido, sin
contrapeso conocido**. Lo que sí se sostiene es que **los dos** quedan muy por encima del
rango típico de mamífero — y eso no lo arregla cambiar de intrón.

### De dónde salían los 314-318

`tools/auditar_geometria.py` tenía

```python
INSERTADO = 149 + spacers.SPACER5_LENGTH + spacers.SPACER3_LENGTH   # 214
```

y se lo pasaba **a los dos intrones**. Y no es lo que se intercala en los dos:

| intrón | cómo mete el módulo | se intercala |
|---|---|---|
| `mvm_actual` | entre sus dos mitades, con los dos espaciadores | **214** nt |
| `intron_quimerico` | en la posición 49 de su secuencia entera | **149** nt |

Los espaciadores del MVM separan la horquilla de los extremos del intrón; en el quimérico
esa separación **es lo que compra la posición 49**, y por eso `_insert_module` **aborta** si
se le piden. O sea: la constante describía a uno de los dos y se aplicaba a los dos.

### La firma, otra vez

318 − 253 = **65** = 20 + 45, los dos espaciadores exactos. Es el corolario operativo de la
errata nº 35: **cuando una magnitud sale distinta de lo esperado, mirar si la diferencia
coincide con la longitud de alguna pieza conocida antes de buscar en otro sitio.** Aquí
apuntaba directamente a la causa.

Y la plausibilidad no ayudaba: 314-318 nt es un número perfectamente creíble para un intrón
de 282 nt con un módulo dentro. Que estuviera **fuera del rango típico de mamífero** —donde
también está el número correcto— lo hacía encajar en la historia que se estaba contando.

### El arreglo es una derivación, no un segundo número

`Intron.inserted_length(module_length)` lo dice **el intrón**: módulo solo si llegó entero,
módulo más los dos espaciadores si se ensambla de piezas. El auditor pide el módulo —lo
único común— y pregunta. Poner un segundo `INSERTADO_QUIMERICO` al lado habría dejado dos
constantes que hay que acordarse de mantener, y el tercer intrón volvería a heredar la que
no le toca.

### Y arrastraba dos frases

`THE_THREE_ARE_BETTER_ON_DIFFERENT_AXES` y `OPEN_QUESTION_DONOR_TO_BRANCH` decían las dos
que el quimérico es **peor** en este eje. Eso es cierto **del intrón vacío** —100-104 nt
frente a 42— y **no sobrevive al montaje**, porque el MVM intercala 65 nt más. Las dos
quedan corregidas con los números medidos, y con lo que sí se sostiene: **este eje no
discrimina entre los dos**, los dos siguen muy por encima del rango típico, y lo que los
separa es el donante, el tracto y la ventana de inserción.

## 107 — El alcance de 86 nunca funcionó: una opción de la interfaz sin implementación detrás

**Reportado (2026-09-05)**, en dos partes y con el diagnóstico correcto desde la primera:
*«el selector de alcance ofrece "Todos los sitios elegibles — 86" y luego lo rechaza …
Son dos definiciones de qué candidatos valen en el mismo flujo, y gana la restrictiva»*; y
después, *«si es el mismo `panel` que se pasa aguas abajo sin mirar el alcance elegido,
están los cuatro»*. **Están los cuatro.**

### Los cuatro, por tres caminos

| modal | cómo resolvía un inicio | con uno de fuera del panel |
|---|---|---|
| especificidad | `{c.start: c for c in …chosen}` en `blast_query` | **aborta** |
| colisión de seed | lo mismo en `seed_scan._strands` | **aborta** |
| carga de off-targets | usa `_strands` del anterior | **aborta** |
| empalme | `[c for c in chosen if c.start in starts]` | **NO aborta: emite el panel** |

**El cuarto es el peor, y la razón es de grado invertido.** No rechazaba nada: el
selector anunciaba 172 consultas, la app montaba 20 y no decía una palabra. Dicho por quien
lo reportó: *«los tres que abortan te dejan sin resultado; ése te deja con un resultado que
parece completo»*. Un aborto es información —desagradable, inmediata y accionable—; **un
FASTA de 20 registros con la etiqueta de 172 detrás es un entregable que se pasa por
SpliceAI, se analiza y se archiva**, y el error sólo aparece si alguien vuelve a contar.
Es la errata nº 97 —lo anunciado y lo emitido sin nada que los ate— entrando por un eje
nuevo, tres días después de haberla cerrado por el otro; y es la misma familia que el
`verify()` de la nº 29 y el contador de la nº 105: **el fallo cuyo producto normal es el
silencio con forma de dato.**

### Por qué esta no es «otro consumidor sin cablear»

La lectura es de quien lo reportó y es la que la separa de las once anteriores: *«no es un
consumidor que no leía un almacén, es una opción de la interfaz que nunca tuvo
implementación detrás»*. Las otras eran capacidades que funcionaban y no llegaban a un
sitio; **ésta no funcionó nunca, en ningún modal, desde que se escribió** (errata nº 67).

Y lo que la hacía creíble es que **las cifras del selector estaban bien**: 86 candidatos,
172 secuencias en el FASTA. Un selector que contara mal se habría notado; uno que cuenta
bien y no se puede ejecutar parece una opción de verdad hasta que se pulsa. Es el silencio
con forma de dato de la errata nº 105, en un control en vez de en un contador.

### El arreglo es UN resolutor, no cuatro parches

Un inicio se resuelve a su candidato en **`ReportSelection.choices_for`**, que es el objeto
que tiene los dos conjuntos —el panel y los sitios elegibles—. Y la definición buena **ya
existía**: `presentation._choices_de` hacía exactamente eso, en la capa que el núcleo no
puede importar.

**Ésa es la causa estructural, y es lo que explica por qué eran cuatro y no uno**, con las
palabras de quien lo señaló: *«que la definición correcta viviera en `presentation`, en una
capa que el núcleo no puede importar, es la causa estructural: cada módulo escribió la suya
porque la buena estaba donde no se podía usar»*. No fueron cuatro descuidos independientes:
fue **una pieza colocada en el sitio equivocado de la jerarquía de capas**, y cada módulo
que la necesitó y no pudo llamarla resolvió lo mismo por su cuenta. Contarlo como cuatro
fallos lleva a arreglar cuatro sitios; contarlo como uno lleva a mover la pieza — que es lo
que se ha hecho, con `presentation` delegando en ella.

Y deja una pregunta que vale para el resto del paquete: **¿qué más vive en `presentation`
que el núcleo necesitaría?** Una utilidad correcta en la capa de arriba no da ningún error
— produce copias peores abajo.

Arreglar los cuatro por separado habría dejado el mismo hueco para el quinto. El guardia es
mecánico y está **calibrado midiendo** (principio nº 34), porque la forma del fallo y la
condición que lo hace posible no son la misma cosa:

| criterio | hallazgos | reales |
|---|---|---|
| «indexa el panel por inicio» | 2 | 1 |
| «recibe `starts` y construye algo sobre el panel» | 2 | 1 |
| **«recibe `starts` y construye un ÍNDICE inicio→candidato sobre el panel»** | **1** | **1** |

Las dos distinciones son de significado: **recibir el alcance** es lo que hace peligroso
resolverlo, y **un `dict` inicio→candidato resuelve mientras un `set` de inicios sólo
marca** — con el conjunto no se puede sacar la guía de nadie, así que no puede rechazar ni
mentir. Los dos falsos positivos son código correcto (`site_table_rows` marca filas que
vienen del tilado; `blast_candidate_rows` deriva la marca `panel` que la errata nº 32
obligó a derivar), y con cualquiera de los criterios anchos el guardia habría acabado
apagado.

### Y el mensaje culpaba a la entrada

*«"Una guía que no existe aquí" sugiere que pedí algo raro; lo que pasa es que la app me
ofreció un alcance que ella misma no acepta»*. El motivo nuevo habla de **ventanas
elegibles** —que es el conjunto de verdad— y dice cuántas hay y cuántas están en el panel.
Un inicio que no sea de ninguna ventana elegible sigue abortando, que es lo correcto.

### Comprobado con su criterio de aceptación

Con el alcance de 86 marcado: FASTA de consulta **172 registros**, modal de seed **172
filas**, y el de empalme **172 construcciones con 0 fallidas** en vez de las 20 que emitía.

## 108 — La tarjeta decía lo mismo dos veces, y en dos colores

**Reportado (2026-09-05)**, con la tarjeta delante: *«se repite el mensaje que dice que ya
está hecho. Uno en verde y otro en amarillo»*, y **«pasa en casi todas»** — que es cierto:
en todas las cerradas por corrida guardada, o sea casi todas en un proyecto trabajado.

```
CERRADO por corrida guardada: los 10 candidatos del panel tienen veredicto…   ← verde
CERRADO por corrida guardada: los 10 candidatos del panel tienen veredicto…   ← ámbar
```

### El texto se escribe UNA vez y lo leen DOS campos

`run_coverage` emite un `motivo` cuando una corrida cubre el panel, y ese mismo objeto
viajaba a los dos sitios:

- a `cerrados`, que `blocking_fronts` pone en `frente.reason` → `resultado` → `st.success`;
- a `avance`, que la tarjeta pinta → `st.warning`.

No es una copia que alguien escribió dos veces —eso se ve en un `grep`—: es **una cantidad
leída por dos campos que la pintan distinto**, que es el principio nº 27 en la capa visual.

### Y el segundo no es sólo redundante: es del color equivocado

`avance` existe por la **errata nº 54**, y su frase fundacional dice para qué: *«un frente
con corrida para 6 de 10 no puede pintarse igual que uno que nadie ha tocado»*. O sea,
**cobertura PARCIAL**. Sobre un frente cerrado no falta nada que avanzar, así que el ámbar
—que en esta app significa «pendiente»— quedaba **justo debajo de un verde que dice
«cerrado»**. Dos estados pintando lo mismo: el principio nº 36 dentro de una sola tarjeta.

Un lector que se fía del color ve un frente medio hecho; uno que se fía del texto ve el
mensaje repetido y deja de leer los dos. Las dos lecturas son peores que una sola línea.

### El arreglo es separar las preguntas, no esconder un campo

`run_coverage` emite **dos**: `motivo` (por qué se cierra, o cuánto falta) y `avance`
(**sólo** cuánto falta, vacío si está cerrado). Y en la tarjeta, `motivo` deja de duplicar
a `resultado`: cerrado, el motivo **es** el resultado y ya está pintado arriba.

Los tres estados quedan con **una** línea cada uno, medido:

| cobertura | verde (`resultado`) | ámbar (`avance`) |
|---|---|---|
| 10 de 10 | «CERRADO por corrida guardada…» | — |
| 6 de 10 | — | «HAY CORRIDA, PERO NO CUBRE…» |
| 0 de 10 | — | — |

### Lo que el arreglo estuvo a punto de llevarse por delante

La instantánea de la página imprime la tabla de frentes con **una** columna `motivo`, así
que al vaciarlo en los cerrados esa fila se quedaba **sin motivo** en el golden — el
arreglo tapando justo lo que ese golden existe para mirar. Lee ahora `resultado or motivo`,
que son **excluyentes por construcción**, y el golden vuelve a ser idéntico. Lo cazó leer
el diff, otra vez.

### El guardia

`tests/test_una_tarjeta_NO_dice_lo_mismo_dos_veces.py` recorre **todos** los campos de
texto que la tarjeta pinta uno debajo de otro y exige que ninguno repita a otro, sobre las
tarjetas de verdad y en los dos estados. Con su control adversario: una tarjeta con el
texto duplicado tiene que ser señalada, porque si no «ninguna repite» y «el detector no
mira nada» dan el mismo verde. Un campo nuevo entra en la comprobación con sólo añadirlo a
la lista de lo que se pinta.

## 109 — La pasajera «no acertaba contra su propia diana» en 75 de 88, y era nuestro umbral

**Salió el 2026-09-05**, verificando la corrida de 88 candidatos: la nota «OJO: esta
consulta no tiene NINGÚN acierto contra su propia diana — eso NO es una buena noticia»
saltaba en **75 de las 88 pasajeras**. No es una propiedad de esos candidatos.

### La pasajera pierde DOS posiciones contra su blanco, y las dos son CONVENIO

- su **posición 1** es el desapareamiento deliberado del bulge basal;
- su **posición 22** es el complemento de la posición 1 de la guía, que el pipeline
  **fuerza a T** para que AGO2 cargue la hebra — así que sólo casa con el genoma cuando
  el genoma ya tenía una T ahí.

Medido sobre las 88: la pasajera alinea **20 nt** contra su diana en **75** casos y 21 en
los **13** en que la T ya estaba. Con `ALLOWED_TRUNCATION = 1` para las dos hebras, esas
75 no encontraban su blanco y la app avisaba de que no lo tenían — **una alarma sobre una
construcción impecable, en el 85 % de las pasajeras**.

### Son DOS preguntas, no un umbral mal puesto

«¿Este acierto ajeno es lo bastante largo para contar?» y «¿este acierto es mi propia
diana?» no son la misma pregunta, y los convenios que aflojan la segunda **se definen
respecto de la diana pretendida: fuera de ella no existen**. Es el principio nº 27 y su
corolario — el criterio vive en un sitio y cada llamador declara qué puede probar.

`OWN_TARGET_TRUNCATION = {"guia": 1, "pasajera": 2}` se DERIVA de los dos convenios que
este proyecto ya tenía escritos, no es un número elegido; una hebra sin convenio declarado
**aborta**, porque deducirlo daría un umbral con la forma correcta y el convenio
equivocado, que es la errata nº 56 exacta.

**Y los veredictos no se mueven**, medido sobre las 176 consultas: 174 `PASS` / 2 `FAIL`
antes y después. Lo que cambia es que las falsas alarmas pasan de 75 a **0**.

### Por qué importa aunque no cambie ningún veredicto

Es la familia de la errata nº 24: una salida bien redactada que **parece una medida**. La
nota existe para un caso real —una hebra que no sale de su propia diana está mal montada—
y disparándose en el 85 % de las pasajeras deja de significar eso: se lee en diagonal, y
el día que sea verdad no la mira nadie. Un aviso que salta siempre es un aviso apagado.

## 110 — Un accession no dice qué gen es, y eso es lo que decide

**Reportado (2026-09-05)** sobre el primer candidato que cae por un motivo real: *«que sea
ADAR y no un gen cualquiera es lo que hay que escribir, no sólo el accession»*.

El motivo del `FAIL` nombraba los transcritos contra los que acertó —que es lo que la
errata nº 56 arregló— y ahí se paraba. Quien lo lee tiene que ir a buscar el accession
fuera de la app para saber si el candidato se descarta o se discute, y **la app tiene ese
hueco justo donde se toma la decisión**.

### La consecuencia se DECLARA, con autorización escrita

`CONSEQUENCE_DECLARED`, en código y no en un fichero, con el mismo criterio que
`mirna.CORE_ABUNDANT`: cambia la lectura de todos los informes a la vez, y en un fichero se
cambiaría **sin que se viera en el diff**. Un gen sin declarar sale por su accession y nada
más — deducir la consecuencia de un gen por su número es la regla 1 con otra cara.

Las **ocho variantes de transcrito de Adar** las identificó el responsable del proyecto:
desde aquí no hay red para resolver un accession, así que se declaran **con su
procedencia**. Y van al mismo motivo, agrupadas: ocho variantes del mismo gen son **un**
hallazgo, y repetir su texto ocho veces lo lee como ocho.

## 111 — «Descarta 1 de 88» y «atrapó un shmiR anti-ADAR» van juntas o mienten las dos

**Decidido (2026-09-05)**, con las palabras con que se pidió: *«separadas se leen mal:
"descarta 1 de 88" suena a filtro inútil, y "atrapó un shmiR anti-ADAR" suena a filtro
decisivo. Es las dos cosas»*.

Es la misma forma que **«rebaja, no descarta»** del dato humano de APA y que el **«QUÉ MIDE
/ QUÉ NO MIDE»** del ensayo de RT-qPCR: dos cláusulas que sólo dicen la verdad juntas, y
que por eso viven en una sola constante y no en dos frases que alguien podría separar.

`discrimination_reading` emite las dos: la **tasa** la deriva de la corrida guardada —no se
teclea— y la **consecuencia** de cada gen atrapado la declara `CONSEQUENCE_DECLARED`, que
es lo único que la app no puede derivar. Sin nada atrapado **no se emite la tasa sola**: se
dice que no ha caído ninguno, que es otra cosa — la mitad que suena a filtro inútil no sale
nunca por su cuenta.

### Y el juicio se extrae para que haya UNA definición

El informe necesita los aciertos **graves** para decir contra qué gen acertó, y
recalcularlos por su cuenta habría sido la segunda definición del mismo número: bastaría
con que uno derivara el mínimo de otra forma para que la celda y el informe dijeran cosas
distintas. `BlastRun._judge` es ese sitio único, y `verdict` y `judged_call` lo llaman los
dos.
