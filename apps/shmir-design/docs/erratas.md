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
