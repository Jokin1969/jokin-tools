# Principios del proyecto

Reglas que no son de estilo ni de código: son cosas que aprendimos al equivocarnos y que
aplican a **todo** lo que se escriba aquí. Van en `docs/` y no dentro de un módulo
concreto precisamente porque no son de ningún módulo.

El registro de los errores concretos está en [`erratas.md`](erratas.md). Esto es lo que
se sacó de ellos.

---

## 1 — El invariante caza lo imposible, no lo equivocado

> **Un invariante de rango sólo detecta valores que no pueden existir. Un valor
> equivocado pero dentro de rango pasa limpio, y lo único que lee la salida entera es el
> golden.**

Sale de tres apariciones del mismo fallo en una semana, todas con `Frame.UTR3` puesto a
mano donde el marco tenía que recibirse:

| Caso | Qué se imprimió | ¿Lo caza un invariante de rango? |
|---|---|---|
| `apa_ceiling_table` sobre el humano | `3utr:1784` en un 3'UTR de 1606 nt | **Sí** — no cabe en ningún 3'UTR conocido |
| tramos de techo sobre el ratón | `3utr:1273-2191` en un 3'UTR de 1242 nt | **Sí** — 2191 tampoco cabe |
| bloque de holguras | `3utr:1185` en un 3'UTR de 1242 nt | **No** — 1185 es una posición perfectamente válida |

Los dos primeros los caza `coords.check_utr3_range`. El tercero **no**, y no por un fallo
del invariante: `3utr:1185` existe, sólo que era de otra señal. La ventana venía
convertida al 3'UTR y la señal no, así que el número era plausible, estaba en rango, y se
leía sin sospechar nada.

Lo cazó el **golden**, al regenerarlo y leer el diff. Ese es el punto: los tests de
presencia comprueban que aparezca lo que cada uno espera y **no ven lo que sobra ni lo
que está mal escrito**; el golden compara la salida completa contra una referencia
versionada, así que un número cambiado salta aunque nadie supiera que había que mirarlo.

### Corolario operativo

**Para toda magnitud derivada nueva —una coordenada convertida, una fracción, un recuento,
un tamaño de banda— hazte esta pregunta antes de emitirla:**

> ¿Puede salir un valor **equivocado pero dentro de rango**?

- **Si la respuesta es no** (el valor imposible es el único modo de fallo), un invariante
  lo cubre. Escríbelo y sigue.
- **Si la respuesta es sí**, asume que **no hay invariante que lo cubra** y que el golden
  es la única red. Entonces:
  1. el bloque nuevo entra en el golden **antes** de darlo por bueno;
  2. se regenera y **se lee el diff**, no se acepta a ciegas;
  3. y se añade un test que fije el valor **con su procedencia**, no sólo su forma
     (`self.assertIn("3utr:236", texto)`, no `assertRegex(texto, r"3utr:\d+")`).

Casi siempre la respuesta es **sí**. Una conversión de marco, una resta de desfase, un
índice 0-based colado en una salida 1-based y un porcentaje con el denominador cambiado
producen todos números que caben.

### Y una consecuencia sobre el golden

El golden **no es un test más**. Es el único que ve la salida entera, así que:

- no se regenera automáticamente en CI ni en un hook;
- se regenera **a mano** y el diff entra en la revisión;
- si el diff es grande, se lee igual: un diff largo es exactamente donde se esconde la
  línea que nadie esperaba.

### Y el hueco que el golden NO puede cubrir

El golden lee **lo que se emite**. Por construcción no puede ver lo que **nunca llega a
emitirse**, y eso es un modo de fallo propio de este proyecto: ha aparecido **tres
veces**, siempre igual — código escrito, con tests en verde, y sin ningún llamador.

| caso | qué se calculaba | quién lo llamaba |
|---|---|---|
| `masking.triple_motive_rows` | el detalle por ventana del triple motivo | nadie |
| `intron_folding` | la accesibilidad estructural del intrón | nadie |
| `store.save_*` | la capa de persistencia **entera** | nadie |

El tercero es el que lo convierte en principio: los cuatro modales calculaban, pintaban,
y al cerrar la pestaña no quedaba nada. La capa estaba construida, testada y documentada.

**Los dos análisis son complementarios y ninguno sustituye al otro:**

> **el golden lee lo que se emite; la alcanzabilidad detecta lo que nunca llega a
> emitirse.**

Los tests tampoco lo cubren, y no por descuido: un test comprueba que la función hace lo
que dice, y para eso la llama él. Un test verde de una función que nadie más invoca **no
prueba que la app haga eso**.

`tools/check_alcance.py` lista toda función pública sin llamador fuera de su propio
módulo y de sus tests, y corre dentro de `npm run check:shmir`. Con dos reglas:

- **no es un fallo automático.** Hay casos legítimos —una API que se usa desde la
  consola, un símbolo alcanzado por nombre dinámico, una función que invoca el hub por
  `python3 -c`—. Lo que hace es **obligar a decidir**: o se cablea, o se justifica por
  escrito en `data/alcanzabilidad.toml`, o se borra;
- **una excepción que ya no hace falta SÍ aborta.** Una lista de excepciones con
  entradas muertas deja de leerse, y entonces el siguiente hallazgo se pierde dentro de
  ella. Es la misma razón por la que un frente CERRADO sigue saliendo en el informe en
  vez de desaparecer.

Y el análisis declara **lo que no puede hacer**, porque un análisis que no declara sus
límites se lee como si no los tuviera: no sigue `getattr` ni despachos por cadena, no
distingue una referencia de una llamada, y **no dice que el código sobre** — dice que
nadie lo llama, que es un hecho y no un veredicto.

---

## 2 — Un umbral en nucleótidos no convierte un gradiente en una frontera

El eje **estérico** del riesgo de poliadenilación tiene un umbral operativo de ±10 nt
(`polya.SIGNAL_FLANK`) que **no tiene base medida**, y la huella real de CPSF/CstF sobre
el pre-mRNA es mayor. Un `PASS` a 14 nt del hexámero no dice «fuera de la zona de
competencia»: dice «fuera del umbral que hemos escrito».

Por eso, siempre que se emite un veredicto sobre un eje así:

- **nunca sale la palabra sola.** `3utr:200` se emite como
  `inmune_truncamiento = SI | esterico = PENALIZADO`, jamás como «inmune»;
- **la sensibilidad al umbral va pegada al veredicto**, no en una nota al pie: «con un
  flanco de 15 en vez de 10 también caería» es parte del resultado;
- y se distingue el eje **geométrico** —por delante del corte, la diana se conserva; eso
  no depende de ninguna convención— del eje de **gradiente**.

`polya.STERIC_IS_A_GRADIENT` lleva el texto y se imprime con la tabla.

---

## 3 — Un mensaje que explica una causa tiene que haberla comprobado

Y si no la ha comprobado, **describe el síntoma y calla la causa**.

Es la **cuarta** vez que el mismo fallo sale en esta app, siempre igual: un dato plausible
—un texto o un número— que se lee como una causa que nadie ha mirado.

| mensaje o dato | lo que decía | lo que era |
|---|---|---|
| `/shmir` no arranca | «comprueba que Streamlit está instalado» | Streamlit estaba instalado y corriendo: era un conflicto de configuración |
| máscara de RepeatMasker | «Alu 0 %» | 0 % obtenido **sin buscar Alu**: la corrida era contra otra biblioteca |
| 1773 ventanas descartadas | «bases desconocidas o enmascaradas» | ninguna tenía `N` ni estaba enmascarada: fallaban GC y homopolímero |
| posiciones de inserción válidas en `intron_quimerico` | **«cero»**, que se lee como «ninguna vale» | se comparaba la estructura del MÓDULO entero en vez de la de la HORQUILLA. Con el criterio bueno son **15 de 97** |

**El cuarto es un CERO, no una frase, y por eso vale la pena tenerlo aquí**: un cero no
parece un diagnóstico, parece una medida. Pero «cero encontrados» dice una causa —«no
hay»— y esa causa hay que haberla comprobado igual que cualquier otra. Aquí la verdadera
era «se midió otra cosa».

Y el arreglo enseña dónde estaba la grieta: el criterio se **deducía** —la función recibía
el módulo y decidía por su cuenta qué comparar—. Ahora `hairpin` va **explícito en la
firma**. **Un criterio no se deduce, se pasa**: deducido, el día que se deduzca mal no hay
error, hay un número.

**Un diagnóstico plausible y falso cuesta más que ninguno.** Manda a mirar al sitio
equivocado, y quien lo lee gasta el tiempo ahí antes de sospechar del mensaje — que es
justo lo último de lo que se sospecha. Sin diagnóstico, se mira el dato; con uno
equivocado, se mira lo que dice el diagnóstico.

En la práctica, para cualquier texto que acompañe a un número o a un fallo:

- **el síntoma siempre**: qué se observó, con sus cifras y su procedencia. Eso es un
  hecho y no depende de ninguna hipótesis;
- **la causa sólo si el código la ha comprobado en ESA ejecución.** No vale «suele ser
  esto», ni «esto lo explicaría»: si la comprobación no está en el camino que produjo el
  mensaje, la causa no se nombra;
- **una pista condicionada a evidencia sí vale**, y así está hecho `process.diagnose`:
  sólo sugiere «falta Streamlit» cuando la salida del proceso trae un
  `ModuleNotFoundError`. La condición es que la evidencia esté delante, no que el caso
  sea frecuente;
- y cuando el número admite descomposición, **se emite entera** en vez de resumirla en
  una causa. «De las 2170 tiladas, 949 caen fuera del 3'UTR y 1221 dentro; pasan los
  biofísicos 407» no explica nada y no se equivoca; «1773 enmascaradas» explicaba y era
  falso.

El corolario incómodo: **un mensaje más corto y menos servicial suele ser mejor mensaje.**
La tentación de ayudar es la que escribe la causa.

---

## 4 — Una predicción refutada se anota igual que un acierto

Si sólo se registran las predicciones que salen bien, el registro deja de medir nada. Ver
las entradas nº 7 (la carrera de A) y nº 8 (las 1773 «enmascaradas») de
[`erratas.md`](erratas.md).

---

## 5 — Dos implementaciones del mismo número se CRUZAN, no se borra una

Cuando aparecen dos formas de calcular lo mismo y una no tiene llamador, el reflejo es
borrar la que sobra. Es el movimiento equivocado, y por una razón concreta: **la que no
se usa es la única que puede contradecir a la que sí**, y esa contradicción es
información que no se consigue de ninguna otra manera. Un test que exija que coinciden
sobre casos reales —los diez del panel, no un ejemplo de juguete— tiene dos salidas y
las dos valen:

- **coinciden** → verificación cruzada gratis, sobre un número del que antes sólo había
  una opinión;
- **no coinciden** → un fallo que nadie habría visto, porque el camino vivo no tiene con
  qué compararse.

Borrar primero cierra las dos puertas y deja la impresión de haber limpiado algo.

**Y el cruce hay que hacerlo antes de clasificar.** Al cruzar los tres pares que sacó la
alcanzabilidad, los tres resultaron ser cosas distintas de lo que parecían: uno era un
par de verdad y **no coincidía** (`spliceai.verdict_state` mira la corrida entera y el
almacén mira el par candidato × intrón: para un candidato que nadie consultó, la primera
dice `PASS` donde la segunda dice `NOT_RUN` — la que no tenía llamador no era redundante,
era la equivocada); otro era un **alias** de una línea, que no puede discrepar consigo
mismo; y el tercero eran **dos generaciones con reglas deliberadamente distintas**, donde
exigir que coincidan habría sido exigir que la corrección nunca hubiera pasado. Lo que se
cruza ahí es lo que de verdad comparten, no lo que se parece.

El cruce además **encuentra pares que la alcanzabilidad no ve**: si los dos lados tienen
llamador, no salen en el informe. `blocks.py` y `gblock.py` montan el mismo módulo de 149
nt desde dos juegos de constantes, y hoy coinciden — pero nada lo obligaba, y lo que
divergiría es ADN que se manda a sintetizar.

---

## 6 — Una comprobación que existe y no corre no es una comprobación

Es el mismo modo de fallo que el código sin llamador, un escalón más arriba y más grave:
no es que sobre, es que **tranquiliza**. `verify_contexts_against_plasmid` llevaba desde
el generador de bloques abortando si los contextos del módulo no coinciden con el vector
real, escrita, probada, y sin correr nunca donde habría servido de algo.

Tres consecuencias, y hay que cumplir las tres:

1. **Corre donde se genera**, y si hay dos generadores, en los dos. Cablear sólo uno deja
   la comprobación fuera justo del camino que se lee.
2. **Sin su recurso sale `NOT_RUN`, no `PASS`.** Es la regla 3 en su forma literal, y
   aquí lo que se pide con un apto falso es ADN.
3. **Se ve.** Una comprobación que corre y cuyo resultado no llega a la pantalla es la
   mitad del arreglo. El diff del golden es la prueba de que llegó: si el golden no se
   mueve, no se ve.

---

## 7 — Una comprobación compuesta declara sus componentes en un solo sitio

Una comprobación con varias piezas parece completa cuando sus piezas no están enumeradas
en ningún sitio, porque **no hay contra qué contrastarla**. `intron_folding` medía
donante, punto de ramificación y aceptor, y el **tracto no estaba**: tres números, con
nombres correctos, con toda la pinta de estar completos. Y el test que lo cubría se
llamaba «da los TRES elementos» y pasaba — **comprobaba la cantidad, no la identidad**.

Dos consecuencias, y hay que cumplir las dos:

1. **Los componentes se declaran en una constante**, no se enumeran en cada sitio que
   los usa. `intron_folding.ELEMENTS` es esa declaración.
2. **El test contrasta por IDENTIDAD contra esa constante**, no por cantidad. Contar
   cuántos salen no distingue «están los cuatro» de «están tres y uno de más».

Y cuando un subconjunto responde a otra pregunta, **es otra lista**: `barrido.FRAGILE`
declara cuáles de los cuatro son los frágiles —donante, punto y tracto; el aceptor es la
frontera— porque «qué se mide» y «qué decide» no son la misma pregunta y meterlas en la
misma lista obliga a elegir cuál de las dos se rompe.

Es la misma familia que el `.out` sin su `.tbl`: allí un frente parecía cerrado con un
fichero de dos porque nadie había listado los dos. La diferencia entre «faltó una pieza»
como fallo de test y como descubrimiento a los meses es exactamente la declaración.

### Corolario A — qué se mide y qué decide son dos preguntas, y por tanto dos listas

`intron_folding.ELEMENTS` declara **qué se mide**: donante, punto de ramificación, tracto
y aceptor, los cuatro. `barrido.FRAGILE` declara **qué decide**: donante, punto y tracto —
el aceptor es la frontera, no lo que el espliceosoma lee.

Son **dos listas porque son dos preguntas**. Meterlas en una obliga a elegir cuál de las
dos se rompe: o se mide de menos para que la lista sirva de criterio, o se decide de más
porque el criterio arrastra todo lo que se mide. Las dos salidas son peores que tener dos
constantes.

### Corolario B — un test de estructura pasa cuando el contenido está mal

El valor esperado tiene que ser **lo que se dice**, no cuántas cosas se dicen ni con qué
forma. Dos casos reales, con meses de diferencia y el mismo mecanismo:

- «da los **TRES** elementos» pasaba mientras faltaba el tracto, porque salían tres
  (errata nº 12);
- «sale un hueco de subida por fichero» pasaba pidiendo hueco para tres ficheros que
  estaban, porque el panel pintaba el hueco a ciegas (errata nº 14).

Contar widgets, contar elementos o contar filas no distingue una salida correcta de una
que tiene el mismo tamaño y dice otra cosa. **Contar no es comprobar.**

## 8 — La página no accede a atributos del modelo. Ninguno.

La regla 6 dice que la interfaz no contiene lógica. Este principio dice algo más
concreto y más operativo, y sale de la errata nº 17:

> **Cada `a.b.c` que la página escribe sobre un objeto del modelo es una suposición
> sobre la forma de ese modelo que ningún test comprueba.**

El `AttributeError` del modal de empalme no fue mala suerte. `variant_proposal_text`
recibía `seleccion.selection.chosen[0].guide` y `Choice` no tiene `guide`: la guía se
alcanza por `window_of(choice).evaluation.guide`. El error estaba a un `.` de distancia
del código correcto, y sobrevivió a 3.169 tests en verde porque vivía en el único sitio
donde no lo mira nadie.

La contramedida no es revisar mejor: es que la página **pida funciones**, no atributos.
Una función de `presentation` tiene test; una cadena de atributos en la página, no.

### No todas cuestan lo mismo: primero las que están detrás de un clic

Un acceso dentro de `if st.button(...)` **no lo recorre ninguna suite**. No lo recorre el
golden de la corrida, que pinta la página sin pulsar nada. No lo recorre el test de humo,
que sólo comprueba que responde. Su primer lector es el usuario, y lo que ve es una traza.

Los que se pintan en cada rerun son otra cosa: el golden los cubre en parte, y un
`AttributeError` ahí lo encuentra el primero que abra la app en vez del primero que
pulse el botón que nadie pulsa.

`tools/auditar_navegacion.py` los cuenta y los separa en esas dos listas. Al escribirlo
había **nueve**, uno de ellos bajo clic; quedan **uno** y **cero**, y el que queda es
`upload.getvalue().decode`, que es la API de Streamlit para un fichero subido — contrato
de otra gente, no modelo nuestro. `tests/test_navegacion_de_la_pagina.py` mantiene la
segunda cifra en cero.

## 9 — Existir no es contener

> **Existir no es contener.** Un estado se deriva de que algo TENGA ALGO DENTRO, nunca
> de que la clave, la entrada o el fichero estén.

Sale de la errata nº 15 y aplica a todo. `provided` era `True` porque la **entrada
estaba en el registro**, no porque hubiera secuencia: fichero fuera de git,
`raw_sequence=""`, y aun así PASS — y el guardia de la regla 1 no llegaba a saltar
porque moría antes con un `KeyError('')`, que ningún `except` del proyecto recoge.

La forma general es ésta, y en este proyecto vive sobre todo en `Path.is_file()`:

> **Un fichero de 0 bytes existe.** Pasa `is_file()`. Y no contiene nada.

La descarga cortada a medias, el `touch` de una prueba, el volumen que se llenó a mitad
de escritura: los tres dejan exactamente eso, y los tres se leían como «lo tenemos» — en
el panel de ficheros, en `fixture_available` (de donde cuelga que ~80 ficheros de test se
salten de forma visible o corran contra nada) y en la cuenta de frentes cerrables del
paso 3.

`presencia.hay_fichero` es la única puerta, y el test que la exige es **de
comportamiento**, no de forma: comprueba que los tres sitios que deciden dicen AUSENTE
ante un fichero vacío, no que ninguno escriba `is_file()`. Buscar la llamada en el fuente
habría marcado además los sitios donde existir SÍ es la pregunta —abrir, borrar,
comprobar la pareja de un `.out`— que es el corolario B otra vez.

### Corolario — cerrar por derivación, no por test

Un test comprueba que no ha pasado; una **definición única** impide que pase. `provided`
dejó de ser un campo y pasó a ser una propiedad calculada, que es el mismo cierre que se
le dio al cuarto par duplicado. Cuando dos cosas tienen que coincidir y una se declara a
mano, la pregunta no es cómo comprobarlo: es cuál de las dos se deriva de la otra.

## 10 — Si el dato está y es válido, se usa

Un veredicto no puede depender de que alguien se acuerde de una bandera.

Este proyecto ya cerró esa puerta una vez, con la casilla «Usar los de
`data/reference/`»: una opción cuyo único efecto posible al desmarcarla era dejarlo todo
en `NOT_RUN` sin decir por qué no es una opción, es una trampa. La errata nº 22 es la
misma forma un nivel más adentro — la promoción por medida entraba sólo si el llamador
la resolvía y la pasaba, y **eso decidía un FAIL**.

### El modo sin el dato no es el modo neutro

Es la mitad que más cuesta ver. Omitir una medida no deja el análisis «sin opinión»:
le hace adoptar **la opinión contraria**. Sin la tabla de PolyA_DB, el `AATATA` de
`3utr:236` se trata como **no funcional** — que es la hipótesis **menos conservadora**, y
además la **falsa** según lo que está medido. El defecto favorecía al candidato
equivocado por omisión, y sin que nada lo dijera.

### Excluirlo es posible, pero es una decisión y se escribe

Hay que poder trabajar, así que la exclusión existe — **por fichero y con el motivo
escrito** (`deposito.Ignored`, `apa.ApaExcluded`), y el motivo **viaja al veredicto**.
Sin él, «se decidió no usarlo» y «nadie se acordó» son el mismo resultado mudo.

### El cierre es un centinela, no una nota

Que el valor por defecto haga lo correcto no basta: hay que quitar la forma de
equivocarse. `measured_apa=None` **aborta**, porque `None` era justo el salto
silencioso; para excluir hay que escribir el objeto con su motivo. La prueba de que
sobraba está en el diff: **doce ficheros de test** pasaban la tabla a mano y dejaron de
necesitarlo. Doce sitios acordándose de lo mismo son doce sitios donde uno puede
olvidarse.

---

## 11 — Cuando código y prosa discrepan, la prosa es la que se ha quedado atrás

Corolario del nº 3, y de la misma familia que el nº 5: **dos definiciones del mismo hecho
que nada obliga a coincidir acaban discrepando**, y aquí una de las dos no es código.

El caso: `CLAUDE.md` afirmaba que los amplicones de la RT-qPCR quedaban «esquivando las
dianas del panel». `polya.rtqpcr_amplicons` marcaba los solapes con `⚠ solapa` desde el
principio. **Los dos textos hablaban del mismo hecho y decían cosas contrarias**, y no
saltó nada: una frase no tiene invariante.

Y la asimetría es lo que lo hace un principio y no una anécdota:

- **el código se ejecuta**, así que un error suyo acaba dando un resultado raro;
- **la prosa se lee**, y un error suyo se cree — sobre todo el que va en el fichero que
  gobierna el proyecto, que es el que alguien abre para saber qué hacer;
- y la prosa **no se regenera**: sobrevive intacta al cambio que la deja falsa.

### La regla operativa: que la frase la EMITA el generador, o que un test la contraste

No basta con corregirla. Toda afirmación de prosa sobre un hecho que el código calcula
tiene que estar atada de una de estas dos formas:

1. **Que el generador la emita.** Es lo que ya se hace con las coordenadas de los
   amplicones, con el techo por tramos y con la descomposición del recuento: el texto
   sale de la magnitud, así que no puede contradecirla.
2. **Que un test la contraste.** Cuando la frase vive en un documento —`CLAUDE.md`,
   `docs/`— el test lee el documento y lo compara con lo que el código emite.
   `tests/test_prosa_contra_codigo.py` hace eso con los amplicones declarados y con el
   panel de diez.

Lo que **no** vale es corregir la frase y seguir. Eso deja el mismo mecanismo intacto, y
el mecanismo es lo que produjo las otras dos de esta misma familia: el «comprueba que
Streamlit está instalado» pegado a todo fallo, y el «Alu 0 %» obtenido sin buscar Alu.

### Y una prosa obsoleta que PIDE algo ya hecho es peor que una que describe mal

Formulado por el responsable del proyecto (2026-09-04) sobre el caso de
`introns.INTRONS["mvm_sin_criptico"].why_missing`, que decía:

> «el primer paso EMPATA entre dos alternativas y **la app no elige: hace falta una
> decisión**»

Cierto cuando se escribió. Falso desde que la decisión se registró en
`intron_design.TIEBREAK_MOTIF`, con su racional y su alternativa descartada.

**Las dos clases de texto obsoleto no cuestan lo mismo**:

- el que **describe mal** un hecho hace que alguien entienda algo equivocado, y se
  descubre al contrastarlo con lo que el código emite;
- el que **pide una decisión ya tomada GENERA TRABAJO**: manda a razonar otra vez lo que
  está razonado, a comparar alternativas que ya se compararon, y —lo peor— **a decidir de
  nuevo**, con el riesgo de decidir distinto y quedarse con dos decisiones. No se descubre
  contrastando nada, porque no afirma ningún hecho falso: afirma una *carencia* que ya no
  existe.

**La regla operativa**: un texto que pide algo —«hace falta X», «queda por decidir Y»,
«falta aportar Z»— es una **deuda declarada**, y una deuda saldada hay que darla de baja
igual que se da de baja una excepción de alcanzabilidad caducada o una entrada muerta de
una tabla de auditoría. Este proyecto ya lo hace con las tablas —una justificación
caducada hace fallar la suite— y la prosa que declara carencias está en la misma
situación sin la misma protección.

Y el corolario que lo hace revisable: **cuando algo se resuelve, se busca quién lo pedía**.
El commit que registra una decisión tiene que tocar también los textos que la reclamaban;
si no, la decisión existe y el proyecto sigue pidiéndola.

### Un aviso: no todo lo que parece discrepar lo es

La prosa dice además cosas que el código **no** calcula —por qué se decidió algo, qué
queda abierto, qué cuesta no resolverlo— y eso no tiene con qué contrastarse ni falta.
El corolario aplica a **afirmaciones sobre hechos que el código sabe**; lo demás es el
registro, y el registro se defiende leyéndolo, no con un test.

---

## 12 — La procedencia de una EVIDENCIA se audita igual que la de un dato

Este proyecto exige procedencia para todo lo que entra al pipeline: md5 en el manifiesto,
versión de la herramienta, biblioteca con la que se corrió, ensamblaje de las
coordenadas. Y no la exigía para lo que **justifica una regla**.

`external_score.EVIDENCE` no es un dato del análisis: es la **prueba** de que la escala
va en la dirección que se dice. Y estaba anclada a `mirarchitect_prnp_raton.tsv`, un
fichero que el manifiesto marca «NO USAR» — se puntuó sobre el 3'UTR fabricado de la
errata nº 5.

### Un fichero retirado no se retira solo de las constantes que lo citan

Ésa es la parte mecánica y es la que hay que cerrar con una comprobación, no con
cuidado. Retirar un fichero es un acto en el manifiesto; las constantes que se
derivaron de él siguen exactamente donde estaban, con el mismo aspecto de siempre, y
nada las vuelve a mirar.

La comprobación va sobre **todas** las constantes, no sobre la que falló:
`tests/test_procedencia_retirada.py` deriva la lista de retirados **del propio
manifiesto** —«NO USAR» o «FIXTURE NEGATIVO»— y barre `shmir_design/` y `tools/`
enteros. Si mañana se retira otro fichero, queda cubierto sin que nadie añada nada.

### Nombrar un retirado se puede; nombrarlo COMO SI FUERA una fuente viva, no

Los fixtures negativos existen a propósito y no se borran: son evidencia, y ya está
escrito que borrarlos sería perderla. Así que la regla no es «prohibido nombrarlos» —una
lista de módulos exentos habría dejado ciego justo al módulo que motivó esto—, sino:
**quien escribe el nombre escribe al lado por qué no se usa**, en el mismo texto. Se
cumple sola y se lee sola.

### Y lo que no se encuentra se dice CÓMO se buscó

Los otros dos fixtures retirados —el 3'UTR fabricado y el `.out` de biblioteca
equivocada— salieron limpios. Eso no se anota como «no hay nada»: se anota con el método,
porque «no hay nada» sin decir con qué se miró es la misma frase que el «Alu 0 %»
obtenido sin buscar Alu (principio nº 3).

- Contra el **fabricado** no sirve buscar números —comparte casi todos con las
  referencias buenas—: se busca por **subcadena de ADN**, y una que esté en él y en
  ninguna referencia verdadera sólo puede venir de ahí. Con su **control adversario**:
  el test comprueba además que existe al menos un tramo exclusivo, porque si no
  existiera, «cero culpables» y «la búsqueda no distingue nada» serían el mismo
  resultado.
- Contra el **`.out` equivocado** no hay cifra exclusiva que buscar, y la razón es la
  propia demostración del proyecto: **es el mismo fichero byte a byte** que el válido. Lo
  que lo distingue vive en el `.tbl`, y de ahí tampoco hay ninguna cifra en el código.

---

## 13 — Una constante que cita un fichero se DERIVA de él, nunca se transcribe

El corolario operativo del nº 12, y el que habría bastado por sí solo.

Cuando una constante dice «estos son los valores de tal fichero», hay dos definiciones
del mismo dato (principio nº 5) con un agravante: **una de las dos es un fichero que
nadie vuelve a abrir**. La copia de código es la que se lee, así que es la que se cree, y
puede envejecer o —como pasó— haber nacido apuntando a otro sitio.

**Tres sitios decían de dónde salían los pares de `EVIDENCE` y ninguno acertaba**: la
constante decía «corrida manual sobre el 3'UTR de Prnp murino», la tabla de auditoría
decía `mirarchitect_prnp_export.csv`, y el ancla real era el TSV retirado. Cada uno
parecía confirmar a los otros dos. Eso es lo que lo hizo invisible durante semanas.

### La regla

Lo que vive en código es **cuál** es el fichero —eso es una decisión, y reapuntarla tiene
que verse en el diff—. Los **valores** se leen de él. Si el fichero no está, se **aborta**
diciendo qué paso queda sin ejecutar; no se devuelve una lista vacía, que es el modo en
que una evidencia desaparece sin que nadie lo note.

Y no se muestrea: `EVIDENCE` emite **todas** las filas del export, no cinco. Elegir cinco
es transcribir otra vez, con el mismo mecanismo y menos aviso.

### Dónde más aplicaba lo mismo

- **La ficha de obtención** nombraba `apa_medido_{slug}.tsv` mientras el cargador buscaba
  `apa_medido.tsv`: el texto mandaba preparar una cosa y el código leía otra. Ahora la
  ficha nombra el **rol** (`{fichero_polyadb}`) y el nombre lo pone
  `species.required_files`, que es quien lo va a cargar.
- **La anatomía** vive en `reference.REFERENCES` y en el manifiesto, y ahí no se pudo
  derivar todavía — así que se cruzan con un test en las dos direcciones. Cuando no se
  puede derivar, se **ata**; lo que no vale es dejarlo suelto.

---

## 14 — Haber comprobado una vez no es seguir comprobando

El complemento del nº 9. Allí: *existir no es contener* — un fichero de 0 bytes pasa
`is_file()` y no tiene nada dentro. Aquí: **una comprobación que corrió en la ingesta no
sigue corriendo**, y lo que protege puede haber cambiado desde entonces.

Sale del contrafactual de la errata nº 27, que es la parte que más enseña. De los dos
guardias que podían haber cazado la evidencia anclada a un fichero retirado:

- `lower_is_better()` habría **aprobado**: sólo mira si la fuente está registrada;
- `file_order_direction()` sí habría saltado — **y sólo al importar un fichero**.

La contramedida existía y estaba en el **sitio equivocado del flujo**. Nada la
revalidaba después.

### La pregunta que hay que hacerle a cada guardia

No es «¿existe?» ni «¿está probado?». Es **cuándo corre**, y luego **qué lo vuelve a
correr**:

| | |
|---|---|
| **qué protege** | el invariante, no la función |
| **cuándo se ejecuta** | ingesta · cada corrida · al emitir · al abrir · al construir |
| **puede degradarse** | ¿lo protegido puede cambiar después de la comprobación? |
| **qué lo revalida** | …o `NADA` |

**La clase de riesgo es la intersección**: corre sólo en la ingesta, lo protegido puede
cambiar, y nada lo revalida. Ésos son los siguientes en fallar. Va emitido en
`tools/auditar_guardias.py`, dentro de `npm run check:shmir`, con su tabla versionada en
`data/guardias.toml` y atada al código por `tests/test_guardias.py` — igual que la
alcanzabilidad y los datos en código, y por la misma razón: un informe que hay que
acordarse de pedir es un informe que nadie pide.

### Tres distinciones que salieron de rellenar la tabla, no de escribirla

- **`SUITE` no es una revalidación.** Un guardia cuyo supuesto sólo lo comprueba la suite
  protege el **repositorio** y no protege una **corrida**: en producción el directorio de
  referencia vive en un volumen que la suite no mira. Es una segunda clase de riesgo y
  sale aparte.
- **Un guardia que no aborta puede ser un INFORME.** `manifest.check_directory` compara
  el md5 de cada fichero contra el manifiesto y devuelve `NO_COINCIDE` para que el panel
  lo pinte. Eso ayuda a decidir con la pantalla delante; no impide nada. Quien impide es
  el cargador, en cada corrida. La distinción se declara, porque «no aborta» a secas es
  justo lo que separa un guardia de un aviso.
- **Y a veces RECHAZAR es lo correcto y abortar no.** `cached_run` retiene un resultado
  cuya huella ya no cuadra y dice por qué; abortar habría tirado la página al cambiar un
  ajuste. Se declara como `RECHAZA` en vez de dejarlo pasar por «no aborta».

### Lo que la tabla encontró al llenarse

`store.ProjectStore.verify()` —la que recalcula la cadena de md5 del log— estaba escrita,
probada y **sin ningún llamador fuera de sus tests**. La cadena no se comprobaba nunca en
la app. Es el patrón de `store.save_*` y `page_run` por cuarta vez, pero sobre un
**guardia**, que es peor: no es trabajo calculado que no llega a una salida, es una
**comprobación que no comprueba**. Y su momento natural era evidente en cuanto se
preguntó por él: el log se edita **entre sesiones**, así que comprobarlo sólo al
escribirlo no protege de nada. Ahora corre en `presentation.project_open`.

La misma pregunta sacó que la comparación de la huella de corrida vivía **en la página**,
copiada en los dos modales — sin test y pudiendo divergir entre ellos.

---

## 15 — Un informe que se puede leer como «pendiente» no obliga a nada

La alcanzabilidad llevaba días listando lo que no tiene llamador. La tabla de guardias
pregunta cuándo protege cada uno. **Es la misma información**, y sólo una de las dos
formas de preguntarla obliga a actuar:

| pregunta | respuesta | cómo se lee |
|---|---|---|
| ¿quién la llama? | nadie | **pendiente** — una fila de una lista larga |
| ¿cuándo protege? | **nunca** | no se puede leer de otra forma |

«Nadie la llama» convive con una lista de trece. «Nunca protege» no convive con nada.

### La consecuencia operativa: cruzar las dos listas, y que el cruce sea un FALLO

Un símbolo que esté en las dos —sin quien lo invoque **y** declarado como guardia— deja
de ser un informe y pasa a ser un fallo de `npm run check:shmir`. Y **sin excepción
posible**: una justificación de alcanzabilidad vale para una función que nadie llama; para
un **guardia** que nadie llama, no. Si protege algo, alguien tiene que invocarlo; si no lo
invoca nadie, no protege nada, por bien escrito que esté.

Está en `tools/auditar_guardias.py`, y **al estrenarse cazó uno**:
`mirarchitect.Export.check_scaffold`.

### Dos cosas que hubo que afinar, y las dos por la misma razón

Un guardia con falsos positivos se acaba apagando, así que el criterio del cruce se
midió en vez de suponerse:

- **no vale una mención en prosa.** Con un criterio textual, `check_scaffold` salía
  «vivo» porque tres docstrings hablan de él. Un guardia explicado no es un guardia que
  corra.
- **pero sí vale nombrarlo sin llamarlo.** `resources._refseq` no se invoca por su
  nombre: entra en un diccionario y se despacha por rol. Exigir una llamada literal
  denunciaba los nueve cargadores, que corren en cada corrida.

El criterio que queda —**referencia de código, ni prosa ni llamada literal**— dio
exactamente tres candidatos, y **dos eran errores de la tabla**, no del código: un
cargador de fixtures de test y una API para otra especie estaban clasificados como
guardias de producción. Se corrigió la tabla. El tercero era el hallazgo.

### Una tercera categoría, que no es fallo ni código muerto

`[sin_camino]`: comprobaciones escritas para una entrada que la app **todavía no acepta**.
Se declaran porque la alternativa es peor —leerlas en el código y creer que corren— y cada
una dice **qué haría falta** para que corriera. Sin eso sería una lista de excusas en vez
de una lista de deudas. Y una entrada que deja de hacer falta **caduca**, como las de
alcanzabilidad.

---

## 16 — La disposición de una pantalla AFIRMA algo, y eso también se deriva

Un formulario no es neutro. Poner cuatro cosas en el mismo paso, antes de un botón, dice
**«hacen falta las cuatro para pulsarlo»** — y lo dice con más fuerza que cualquier texto,
porque nadie lee un texto para saber en qué orden se hacen las cosas: lo lee del orden.

El paso 3 de la interfaz pedía **los siete frentes** antes de diseñar. Ninguna frase
afirmaba que hicieran falta; la **disposición** sí. Y era falso: para obtener candidatos
no hace falta ninguno —la anatomía sale del `.gb`, los filtros biofísicos corren solos—.
Lo que esos ficheros deciden es **cuáles caen**, no cuáles salen. Presentarlos juntos
producía una espera que no tenía que existir: *no puedo empezar hasta reunirlo todo*.

### La regla

Una afirmación implícita en la disposición se **deriva** y se **comprueba**, igual que un
número. Aquí:

- «para diseñar hoy no hace falta ningún fichero» **no se escribe**: la lista del paso 3
  se filtra de `species.required_files`, y hay un test que **corre el diseño con el
  directorio de referencia vacío** y comprueba que salen candidatos. El día que algo pase
  a hacer falta para tilar, el test lo dice y el paso 3 lo enseña solo;
- «estos ficheros no cambian cuáles son, cambian cuáles sobreviven» **está medida**: el
  conjunto de elegibles con cualquier fichero de referencia es un **subconjunto** del que
  sale sin ninguno —ninguno inventa un candidato— y lo que quita cada uno está contado
  (PolyA_DB 17, `mature.fa` 2, la máscara murina 0, y ese 0 es un hecho del 3'UTR del
  ratón, no una propiedad del fichero).

Es el principio nº 11 —cuando código y prosa discrepan, la prosa es la que se ha quedado
atrás— aplicado a algo que **no es prosa**: la maquetación envejece igual, y encima sin
una frase que alguien pueda ir a corregir.

### El corolario del color

Cuatro estados que decir algo distinto tienen que **verse** distintos, siempre igual, con
la leyenda al principio y no detrás de un tooltip. Y al revés: dos cosas que no son lo
mismo no pueden compartir color. `apa_medido.tsv` salía en el mismo ámbar que
`refseq_rna.fa` —uno no hace falta y el otro sí— y eso manda a buscar un fichero que ya
sobra (errata nº 30). Por eso `NO USADO` es un estado propio, y por eso el color lo pone
`presentation.py` con tests y no la página: un color elegido en la página es una decisión
sin test, y las decisiones sin test es donde reaparece todo esto.

---

## 17 — Un fallo ruidoso en una rama que nadie ejecuta es tan invisible como uno silencioso

`tools/design.py` pasaba `thresholds=umbrales`, y esa variable no existe en el módulo. Un
`NameError`: el fallo más ruidoso que hay, inmediato, imposible de confundir con otra
cosa. **Sobrevivió igual**, porque toda corrida con `--rmsk` moría antes de que nadie la
viera — y nadie la veía porque **ningún test recorría ese camino**.

La intuición que esto rompe es que los fallos se ordenan por lo escandalosos que son. No:
se ordenan por **si alguien pasa por ahí**. Un `NameError` en una rama muerta y un valor
mal calculado en una rama muerta cuestan exactamente lo mismo — cero, hasta el día que
alguien la ejecuta, y entonces cuestan lo que costaba desde el principio.

### El corolario: dónde está el hueco

**La alcanzabilidad ve símbolos sin llamador. El golden ve la salida por defecto. Y entre
los dos hay un hueco donde vive el código llamado desde caminos que nadie recorre.**

Ninguna de las dos podía cazarlo, y no por descuido:

| herramienta | qué mira | por qué se le escapó |
|---|---|---|
| alcanzabilidad | símbolos que nadie nombra | **había una llamada escrita** — sólo que nunca se ejecutaba |
| golden | la salida entera de una corrida | esa corrida se genera **sin máscara** |
| los tests de la pieza | que la función haga lo que dice | la llaman **ellos**, no el camino de verdad |

Las tres son necesarias y ninguna cubre esto. Lo que lo cubre es **recorrer el camino
entero y leer lo que sale**: correr `main()` con esa combinación de banderas, comprobar
que termina en 0, y mirar el resultado.

### La contramedida: el inventario de banderas

`tools/auditar_banderas.py` deriva las banderas de cada CLI de sus propios
`add_argument`, deriva de los tests cuáles aparecen en una llamada que **no** se espera
que aborte, y cruza las dos listas. Tres decisiones de diseño y las tres tienen motivo:

- **Se ordena por CONSECUENCIA**, no alfabéticamente. Una bandera que cambia un
  **veredicto** sin recorrido es urgente; una que cambia el **formato** de la salida, no.
  Sin esa distinción, 139 filas planas no las lee nadie — que es el fallo que la
  herramienta viene a evitar, no a repetir.
- **Un test que espera un `2` NO cuenta como recorrido.** Comprobar que una entrada mala
  se rechaza es útil y no atraviesa el camino. Ahí vivía exactamente la errata nº 31.
- **Y lleva un TRINQUETE**, porque una lista larga se lee como «pendiente» y no obliga a
  nada (principio nº 15): el número de banderas VEREDICTO sin recorrer va **declarado**, y
  la suite falla **en las dos direcciones** — si sube, alguien añadió algo que decide y no
  lo recorrió; si baja, el techo está caducado. Sólo puede ir hacia abajo. No hace falta
  cubrirlas todas de golpe: hace falta que bajarlo sea la única forma de cerrar la suite.

### Y el detector se equivocó en las dos direcciones antes de valer

Su primera versión resolvía «de qué CLI es este `main`» con una tabla de alias global.
Daba por recorridas de `design` las banderas de `import_scores` —que también importa su
main como `main`— y no veía las de `test_usar_manifiesto.py`, que llama por un ayudante.
Se contrastó contra un `grep` en las dos direcciones antes de darlo por bueno, y ahora el
CLI se resuelve **por fichero, de sus propios `import`**. Un análisis que se equivoca
hacia el silencio es peor que no tenerlo: no avisa y además tranquiliza.

---

## 18 — Un artefacto de verificación se genera con la CONFIGURACIÓN DE USO y con los DATOS DE USO

Tenía dos mitades y al principio sólo se escribió una. **Un parámetro tecleado y un
fixture sintético son la misma enfermedad:** los dos validan un camino que nadie recorre.
El golden llevaba `--inmunes 4` a mano y validaba un panel que ningún usuario ve;
`test_usar_manifiesto.py` pasaba de punta a punta sobre un manifiesto **parcial** montado
en un temporal, y el manifiesto **real** abortaba con un `KeyError: 'polyadb'`
(errata nº 33). Una configuración fantasma y una entrada fantasma, y el mismo agujero.

### La mitad de la configuración


El golden del informe se generaba con `--inmunes 4` **tecleado a mano** en
`regenerar_golden.py`. Así que la única corrida del CLI que alguien miraba llevaba una
configuración que **ningún usuario usa** — y coincidía con la página mientras el CLI por
defecto daba otro panel, con tres inmunes en vez de cuatro (errata nº 32).

Es grave por dónde falló: **el golden es la contramedida principal de este proyecto.** Se
escribió porque los tests de presencia miran lo que cada uno espera y nadie mira el
conjunto; lee la salida entera; se regenera a mano y su diff entra en la revisión. Todo
eso siguió funcionando — sobre una configuración que no existe fuera del generador.

### La contramedida

**El artefacto de verificación se genera con la configuración por defecto, sin
excepciones.** Si hace falta una variante, se genera un artefacto **adicional** cuyo
**nombre declara** qué configuración lleva. Nunca uno solo con parámetros puestos a mano.

Está comprobado sobre el propio generador: un test recorre su `ARGV` y **falla si aparece
cualquier bandera que no sea de entrada** —la secuencia y su anatomía—. Todo lo demás es
configuración, y una configuración en el golden por defecto es una configuración
fantasma.

### Lo que salió al aplicarla, que es media lección más

De los cuatro parámetros tecleados, **tres eran INERTES**: `--candidates 10` es el
defecto, `--min-block 22` da lo mismo que 15 sobre este par, y `--sin-manifiesto` no
cambia nada habiendo manifiesto. Llevaban ahí sin hacer nada y sin que nadie lo supiera.
El único con efecto era el que rompió.

Un parámetro puesto a mano en un artefacto de verificación **no se revisa nunca más**: se
lee como parte del decorado. Por eso la regla no es «revisa que los parámetros sigan
teniendo sentido» sino «**no los pongas**».

### Y los tres artefactos que no eran el golden

`ficha_raton_200.txt`, `informe_documento.md` y `pagina_raton.txt` construían
`SelectionConfig(n_candidates=10, apa_immune_quota=4)` a mano — `--inmunes 4` con otra
forma. Los tres pasan ahora por `default_config()`. **No cambió ni una línea de los tres**,
que es lo que se espera: hoy los valores coinciden. Lo que cambia es que mañana, si
alguien mueve la constante del proyecto, los goldens se enteran.

La ironía: dos de ellos ya llevaban escrito, dos líneas más arriba, que la tabla de
PolyA_DB **no se pasa a mano** porque «era lo que hacía que el golden se generara con la
constante mientras la app leía el fichero — dos caminos, y el golden dejaba de comprobar
el de verdad». La misma lección, aplicada al dato y no a la configuración, en el mismo
bloque de código.

### La mitad de los DATOS, y su corolario accionable

**Todo test que monte un fixture donde exista el artefacto real debe justificar por qué
no usa el real, y esa justificación va ESCRITA.** No es una prohibición: fabricar tiene
motivos buenos —probar el fichero corrupto, la cabecera corta, un md5 que no cuadra, un
manifiesto al que le falta un rol a propósito— y ninguno de ellos se puede montar con el
real. Lo que no vale es no decirlo.

Se revisó cuántos había, y el del manifiesto no era el único: **doce fabricaciones en
nueve ficheros**. Están en `data/fixtures_sinteticos.toml`, cada una con su motivo, y
`tools/auditar_fixtures.py` cruza la tabla con el código en las dos direcciones: una
fabricación sin entrada falla, y una entrada que ya no corresponde a ningún test también
—una justificación caducada es peor que ninguna, porque se lee como vigente.

Y lo que faltaba en el caso del manifiesto **no era dejar de fabricarlo**: era que
ADEMÁS hubiera una corrida contra el real. Las dos cosas, no una en lugar de la otra.

### La regla de los INERTES

**No se ponen parámetros en un artefacto de verificación, ni siquiera los que coinciden
con el defecto.** De los cuatro que llevaba el golden, tres no hacían nada — y ése es
exactamente el problema: **un parámetro que no hace nada no se distingue de uno que sí**,
así que nadie los volvió a mirar y el que rompía viajó de polizón entre los otros tres.

Lo comprueba un test sobre **todos** los generadores, no sólo sobre el del CLI:
`default_config()` se llama sin nada, `tile_utr` recibe la secuencia y nada más, no se
construye ningún `SelectionConfig` a mano, y **ningún campo de `SelectionConfig` aparece
como argumento** en el fichero — esa última lista se deriva de la propia clase, así que un
ajuste nuevo queda cubierto sin que nadie se acuerde de añadirlo. Lo permitido en una
variante tampoco es una lista escrita: sale de su propio nombre.

### La ironía de los dos generadores

Dos de ellos llevaban escrito, **dos líneas más arriba**, que la tabla de PolyA_DB no se
pasa a mano porque eso hacía que el golden se generara con la constante mientras la app
leía el fichero. Tenían la regla delante, redactada, para el **dato** — y no la vieron
para la **configuración**, en el mismo bloque de código.

**Saber la regla no basta si no se aplica al eje que toca.** Una regla escrita para un eje
no se transfiere sola al de al lado; hay que ir a buscarla.

### El corolario de la clasificación

**Al clasificar una bandera —o un estado— hay que mirar QUIÉN LA LLAMA, no sólo qué
hace.** El puente de Batchwork pasa 18 banderas en cada corrida desplegada, cuatro de
ellas sin recorrido de punta a punta; eso no se ve mirando la bandera. Y al revés:
`--usar-manifiesto` figuraba como recorrida porque sus tests montan un manifiesto
**parcial** en un temporal — contra el manifiesto de verdad abortaba con un
`KeyError: 'polyadb'`. Quién llama, y **con qué entrada**.

### Y LA MITAD QUE MÁS CUESTA VER: esto aplica al PROPIO COMPROBADOR

Un control adversario que no reproduce la **forma real** del fallo valida el comprobador,
no el caso. Es este mismo principio un piso más arriba, y es donde menos se nota — porque
el test pasa, señala, y parece que ha demostrado algo.

**El caso (2026-09-04, errata nº 90).** Al escribir el guardia que prohíbe que una clase
de conteos por clase tenga un atributo que los sume, su control adversario probaba con:

```python
class SeedLoad:
    counts: dict[str, int]
    def total(self):
        return sum(self.counts.values())
```

Señalaba, y el guardia salía a cero sobre el código arreglado. **Pero el `total` real no
era eso.** Era un **campo** —`total: int | None = None`— y la suma vivía en el
**constructor**, `SeedLoad(..., total=sum(totales.values()))`. Un guardia que sólo mirara
cuerpos de métodos habría pasado ese control adversario **y no habría cazado el fallo que
de verdad hubo**.

**La comprobación no es «¿el control adversario falla?», es «¿falla sobre el código que
existía?».** Se le da el fuente de ANTES, tal y como era, no una reconstrucción de memoria
de cómo era. Escribirlo de memoria es el mismo error que transcribir un dato en vez de
derivarlo (principio nº 13), aplicado a la evidencia de que un guardia sirve.

**Cómo se hace en la práctica**: el control adversario se saca de `git show` del commit
anterior, o se copia del cuerpo real que se acaba de borrar — nunca se teclea desde el
recuerdo de lo que hacía.

---

## 19 — Un valor legítimo puede tener la FORMA de la ausencia, y la comprobación mira el continente

Van **cuatro** fallos con la misma anatomía, en años de código distinto:

1. **`x or defecto` con la cadena vacía** (errata nº 18). `""` es un valor —«todas las
   especies, a propósito»— y `None` es «nadie lo declaró». El `or` los hace uno.
2. **`Path.is_file()` sobre un fichero de 0 bytes** (errata nº 15). El fichero **existe**
   y no tiene nada dentro; el panel lo daba por presente y «Ver» enseñaba el vacío.
3. **`if fila["acciones"]` sobre una lista que nunca está vacía** (errata nº 34). Valía
   `["ver", …]` o `["subir"]`: dos cosas distintas, las dos verdaderas.
4. **`zip(candidates, folding_ok)` con el segundo vacío por defecto.** `zip` trunca al
   más corto **sin decir nada**, así que el informe habría salido **sin ninguna fila y
   sin ningún error** — «no hay alternativas» cuando lo que pasa es que no se midió
   ninguna.

En los cuatro, **la pregunta era por el contenido y la comprobación miró el continente**.
Y en los cuatro el resultado fue el peor posible: no un error, sino una respuesta
plausible.

**El cuarto no está de adorno, y es el que más enseña**: no lleva **ninguna condición**.
Los tres primeros se encuentran mirando los `if`; a éste ninguna búsqueda de `if` lo
habría encontrado nunca. Y donde los otros devuelven un valor equivocado, éste devuelve
**un informe vacío, que se lee como un resultado** — la forma más callada que hay de leer
el continente. Un barrido que sólo mire condiciones deja fuera media familia.

### La forma de la enfermedad

Python —y cualquier lenguaje con verdad implícita— colapsa cosas distintas en «falso»:
`None`, `""`, `0`, `[]`, `{}`. **El colapso es cómodo mientras ninguno de ellos signifique
algo**, y deja de serlo en cuanto uno significa. Y el caso 3 enseña que el colapso también
va al revés: dos valores distintos pueden ser los dos **verdaderos**, y entonces el `if`
no separa nada aunque lo parezca.

Así que la regla no es «no uses la verdad implícita» — sería inaplicable y falsa, porque
en `if not filas` la vacuidad **es** la pregunta. La regla es:

> **Antes de escribir `if x:`, di en voz alta qué pregunta estás haciendo. Si la pregunta
> no es literalmente «¿está vacío?», el `if` no es la comprobación que necesitas.**

«¿Me lo dieron?» es `x is None`. «¿Hay algo dentro?» es `hay_fichero(ruta)`. «¿Está
presente?» es `fila["presente"]` — un dato que alguien calculó y que se puede probar.

### La contramedida, y por qué es más estrecha de lo que parece

Se barrió el paquete entero por los tres ejes. **El barrido ancho no sirve**: da 187
posiciones sólo en el eje de las colecciones y casi todas son correctas. Un auditor así
se apaga el primer día, y un auditor apagado es peor que ninguno — es la lección de
`shutil.copy` en el de fixtures, con otra ropa.

Lo que sí se decide sin discusión es el caso extremo: **una condición que no puede ser
falsa nunca**. Eso no es un criterio opinable, es una rama muerta con forma de decisión.
`tools/auditar_condiciones.py` la busca derivando qué claves valen siempre algo no vacío,
y **no es un trinquete sino un guardia**: el número correcto es cero.

Está probado contra el fallo que lo originó — se le da el fuente **de antes** del arreglo
y se exige que lo señale. Un detector que sale a cero sobre el código ya arreglado no ha
demostrado nada; es el `verify()` de la errata nº 29 otra vez.

### La contramedida del cuarto: dos salidas y ninguna tercera

Se barrió el paquete entero por `zip`, por `map` de dos iterables y por las comprensiones
sobre dos secuencias: **catorce**, descontando las ventanas del tipo `zip(x, x[1:])`, que
recorren pares consecutivos de **una** lista y no emparejan nada.

Y la lectura de los catorce da la regla, porque son **dos cosas distintas** y sólo quien
escribe la línea sabe cuál:

- **van en paralelo** —una fila y su ancho, un candidato y su veredicto de plegado, un
  patrón y su ventana— y entonces que difieran es un fallo: **`strict=True`**, biblioteca
  estándar desde 3.10, que aborta en vez de acortar. **Diez.**
- **la truncación ES la intención** —cinco columnas de layout para tres herramientas, un
  motivo de 7 nt contra un consenso de 5 posiciones— y entonces se escribe
  **`# zip-ok: <motivo>`**, la misma convención que `# rule2-ok`. **Cuatro.**

Dejarlo implícito no es una tercera opción: es que el lector adivine. Lo hace cumplir
`tools/auditar_pares.py`, y es un **guardia**, no un trinquete.

Que la regla tenga dos salidas no es una concesión: es lo que la hace aplicable. «Pon
`strict` en todos» habría roto cuatro sitios correctos, y una regla que rompe lo correcto
se retira a la semana.

**Donde dos secuencias van en paralelo, que vayan en paralelo es una invariante y se hace
cumplir.** Y donde no van en paralelo, eso se dice.


---

## 20 — Dos errores independientes pueden cancelarse hacia un resultado CREÍBLE, y entonces la plausibilidad deja de ser señal

`donor_to_branch` empezó a dar **405** donde llevaba todo el proyecto dando **256**, sin
que nadie hubiera tocado el intrón. Eran **dos** errores en la misma llamada:

1. recibía los elementos del intrón **ya montado**, cuyo campo `empty` vale ya la
   distancia montada — y la función le sumaba la inserción otra vez;
2. y recibía `inserted = len(módulo)`, cuando `inserted` es **todo lo insertado**: el
   módulo **más los dos espaciadores**, 149 + 20 + 45 = 214.

Lo que hace este caso distinto de un descuido es la aritmética. Los tres resultados
posibles eran:

| errores | resultado | ¿habría chirriado? |
|---|---|---|
| sólo (1) | 470 | **sí** — casi el doble |
| sólo (2) | 191 | **sí** — por debajo del conocido |
| los dos | **405** | **no** |

**Cada error por separado producía un número inverosímil. Juntos produjeron el más
creíble de los tres.** Así que el filtro que normalmente salva —«esto no puede ser»— no
disparó, y no por descuido de quien lo leyó: porque el número no daba motivo.

### Lo que se pierde, y hay que decirlo

La plausibilidad es el detector barato que se usa todo el rato, y **contra errores
compuestos no funciona**. No es que falle a veces: es que la composición **tiende** a
llevar el resultado hacia el centro, porque los extremos se cancelan entre sí. Cuantos
más errores independientes, más creíble el resultado y menos fiable el olfato.

### El corolario operativo, y es el que lo cazó

**Cuando una magnitud cambia sin que nadie haya cambiado su entrada, la DIFERENCIA es el
diagnóstico.** Antes de buscar en otro sitio, comprobar si esa diferencia **coincide con
la longitud de alguna pieza conocida**. Aquí 405 − 256 = **149**, que es exactamente la
longitud del módulo — y una diferencia que coincide con una constante del proyecto casi
nunca es una coincidencia: es una suma de más, una resta de menos o una unidad confundida.

No lo cazó ninguna comprobación. Lo cazó alguien que recordaba el número anterior. Eso no
es un método, así que hace falta uno.

### La contramedida general

**Toda magnitud compuesta sale por DOS DERIVACIONES INDEPENDIENTES que se cruzan.** No
«se comprueba»: se calcula dos veces por caminos distintos y el test exige que coincidan.
Donante→punto se **mide** ahora sobre la secuencia del intrón montado y se cruza contra la
ruta aritmética `donor_to_branch(vacío, inserted=214)`.

Una sola ruta no podía cazar esto **porque el fallo estaba en la ruta**. Es el principio
nº 5 —dos implementaciones del mismo número se cruzan— aplicado donde más falta hace: no
a los números que dos módulos calculan por separado, sino a los que un módulo calcula
componiendo, que es donde los errores se suman en silencio.

---

## 21 — Pasar un umbral no es ser EQUIVALENTE, y un control necesita lo segundo

Un filtro del pipeline contesta *«¿sirve esto?»*. Un control contesta otra pregunta:
*«¿se comporta esto como aquello?»*. **La primera es un mínimo y la segunda es una
distancia**, y quien tiene la primera puesta cree que tiene las dos.

### De dónde sale

El scrambled de un shmiR se genera permutando la guía original para conservar su
composición. Las cinco primeras permutaciones que salieron pasaban **todos** los filtros
—GC, homopolímero, asimetría, sin diana, sin sitio de seed— y tenían una asimetría de
**+0,8 a +3,9 kcal/mol frente a los +7,65 del original**. El umbral del proyecto
(`MIN_ASYMMETRY`, 0,5) dice si una hebra se carga en AGO2; no dice si se carga **igual**.

Con esos controles, la diferencia entre el brazo tratado y el brazo control mezclaría dos
cosas —la diana y el procesamiento— y no separaría ninguna. O sea: el control mediría
justo lo que existe para descartar.

Medido sobre la guía de `3utr:1018`: las permutaciones tienen **mediana 0,67** y rango de
−6,45 a 8,05. **Casi todas pasan el filtro y casi ninguna es comparable.**

### La forma general

Cuando una construcción existe para ser **el mismo experimento menos una cosa**, sus
criterios de admisión no son los del objeto que imita:

- el objeto necesita **estar por encima de un mínimo**;
- su control necesita **estar cerca de él** en todo lo que no se quiso cambiar.

Los dos criterios se parecen lo bastante como para que el segundo parezca cubierto por el
primero, y no lo está. Un control admitido por el umbral del original es un control que
pasa todo y no controla nada.

### La contramedida

**Dos umbrales, dos nombres, dos frentes.** El del pipeline se queda donde está;
la equivalencia va en su propio filtro (`equivalencia_asimetria`) con la magnitud del
original **al lado**, para que un lector acostumbrado a que «más es mejor» vea que aquí
lo que se busca es **parecerse**. La tolerancia va declarada como parámetro, con la
distribución medida detrás —de 1380 permutaciones admisibles, 1 a ≤0,5, 4 a ≤1,0 y 17 a
≤1,5— para que el número no sea una elección de despacho, y con la nota de que no sale de
ningún artículo.

### Corolario: el criterio que no puede fallar tampoco es equivalencia

Al medirlo apareció el otro lado. El criterio estructural —«el 97-mero pliega igual que el
original»— **no rechaza nada y no puede**: `passenger_from_guide` ELIGE la base de la
posición 1 de la pasajera para que el 97-mero reproduzca la estructura de SGEP y ABORTA si
ninguna lo consigue, así que la comprobación posterior vuelve a preguntar lo que ya era
condición para haber montado la horquilla. **0 de 2000** permutaciones, **0 de 1134**
variantes de seed, y tampoco una guía derivada del propio andamio para competir con el
loop.

No se quita —sigue siendo el guardia del caso en que una guía no admita pasajera— pero
sale con esa frase pegada: **un PASS que no puede fallar no es evidencia, es la
definición**. Es la cuarta vez que este proyecto se encuentra un criterio que da el mismo
resultado a todo el mundo (el `donante 1,00 / aceptor 0,00` de MFE, el `)(` del
discriminante de horquillas, el GC de una permutación, y éste), y la regla que queda es la
misma: **antes de creerse un criterio, hay que enseñarle un caso que deba suspender.**

---

## 22 — Un informe que lee estado MUTABLE declara contra QUÉ estado se generó, no sólo cuándo

**Formulado por el responsable del proyecto (2026-09-01)**, al cablear los almacenes al
documento. En una frase: **la fecha no basta — dos corridas del mismo día son dos
documentos distintos.**

### De dónde sale

Mientras el informe se calculaba **sólo del tilado**, «generado el 1 de septiembre» lo
identificaba: la entrada era la misma y el resultado también. En cuanto empieza a leer los
almacenes del proyecto, la entrada deja de ser una — el mismo día, la misma secuencia y el
mismo panel dan **dos documentos distintos** según si se subió un BLAST entre uno y otro.

Y el que los compara no tiene forma de saberlo. «Este informe es de después de subir el
BLAST» pasa a ser **algo que alguien tiene que recordar**, que es exactamente la clase de
cosa que este proyecto no deja en la memoria de nadie.

### La contramedida, en dos piezas

- **La HUELLA, en la cabecera** (`presentation.log_fingerprint`): un md5 de la lista de
  `run_id` presentes al generar. **Dos informes con la misma huella son el mismo
  documento; con huellas distintas, la diferencia se explica sola.** Va **ordenada**,
  porque el orden de llegada no es estado: dos logs con las mismas corridas son el mismo
  estado, y si el orden contara, dos documentos idénticos saldrían con huellas distintas y
  la señal dejaría de servir para lo único que sirve. Hay test de eso.
- **La PROCEDENCIA de cada corrida** (`run_provenance_rows`), en la sección que ya lleva
  la de los ficheros: `run_id`, fecha, **md5 del fichero subido** y md5 de la base o
  catálogo. Es **lo mismo que se le exige a un fichero de referencia, aplicado a un
  resultado** — y sin ello un frente que sale cerrado en el documento no se puede cotejar
  con nada.

### El detalle que no es un detalle

De una corrida de BLAST hay **dos** md5 y sólo uno sirve aquí: `query_md5` es el del FASTA
que **generó la app** —regenerable, no prueba nada de fuera— y `result_md5` el del fichero
que **llegó**. La procedencia lleva el segundo. Confundirlos deja el documento apuntando a
lo que él mismo produjo.

### La forma general

Vale para cualquier artefacto que se entregue y lea algo que cambia debajo. **Fechar no es
identificar.** Si dos ejecuciones con la misma fecha pueden dar productos distintos, el
producto tiene que llevar **de qué estado salió** — y llevarlo donde se lee, no en un
anexo.

---

## 23 — Cuando dos artefactos leen el mismo estado y sólo uno se actualiza, el intermedio es PEOR que el punto de partida

**Formulado por el responsable del proyecto (2026-09-01)**, sobre una tanda propia. No es
una observación de gestión: es una regla técnica sobre cómo se reparte un cambio.

### El caso

El informe descargable pasó a leer los almacenes del proyecto. La tabla de la pantalla no,
todavía. Antes de la tanda los dos **callaban** —`NOT_RUN` los dos— y eran coherentes en su
ignorancia. Después, el documento puede decir `PASS` de un frente que la pantalla sigue
enseñando en `NOT_RUN`.

**Y el que se entrega es el documento.**

### Por qué el estado intermedio es peor que el inicial

Antes había **una laguna**: los dos artefactos decían menos de lo que se sabía, y quien los
leía sabía a qué atenerse. Ahora hay una **contradicción**: dos artefactos del mismo
proyecto afirman cosas distintas del mismo frente, y quien los ponga uno al lado del otro
**concluirá que uno está mal sin poder saber cuál**. Eso no es «media mejora»: es
información nueva y falsa sobre la fiabilidad de las dos.

Es la familia del principio nº 11 —código y prosa que discrepan— con los dos lados siendo
**salidas del código**, y con el agravante de que ninguna se ha quedado atrás por descuido:
el desfase lo introdujo una mejora.

### La regla operativa

Al repartir un cambio que toca varios artefactos que leen el mismo estado:

1. **Preferible: en la misma tanda.** Si los dos leen, no hay desfase que declarar.
2. **Si no cabe: el desfase se DECLARA en el artefacto que se ha quedado atrás**, diciendo
   quién sabe más y **a cuál creer** — un aviso que sólo siembra duda es peor que ninguno.
   Aquí es `presentation.TABLE_LAGS_REPORT`, pintado sobre la tabla.
3. **Y el aviso CADUCA con un test.** `tests/test_desacuerdo_declarado.py` falla el día que
   `site_table_rows` lea los almacenes, obligando a borrarlo: **un aviso que sobrevive a su
   causa manda a desconfiar de algo que ya es correcto**, que es el mismo daño al revés.

### El corolario que no es obvio

**«Está a medias» no describe este estado.** Una tanda a medias deja cosas sin hacer; ésta
deja algo **nuevo y roto** que antes no existía. La pregunta antes de partir un cambio no
es *¿qué parte entra?* sino *¿el estado intermedio afirma algo falso?* — y si lo afirma,
o entra entero, o entra con el desfase declarado.

## 24 — Los dos lados de una comparación salen de la MISMA fuente, o la comparación puede no darse nunca

**Sale de la errata nº 47 (2026-09-02)**, y generaliza algo que este proyecto ya había
tocado por dos puertas distintas sin nombrarlo: el principio nº 13 (derivar en vez de
transcribir) dice de dónde sale **un** dato; éste dice qué pasa cuando **dos** datos que
tienen que casar salen de sitios distintos.

### El caso

`insumos.obsoleta` compara el md5 que una corrida registró con el md5 del fichero que hay
hoy. Los dos lados se emparejan por un **nombre**: la tabla de insumos escribía «base de
datos de BLAST» y el diccionario de md5 de hoy venía indexado por `refseq_rna.fa`. La
comparación no fallaba: **no llegaba a hacerse**, y con el fichero delante y el md5
correcto la corrida salía «no se ha podido comprobar» para siempre.

### Por qué es invisible, y no un fallo más

Una comparación que no puede ser verdadera **produce exactamente la salida honesta de una
comparación que sale que no**: aquí, «no se ha podido comprobar». Ese estado existe, es
correcto en su caso, y está bien redactado — así que nadie lo lee como un fallo. Es la
familia de la errata nº 29 (`verify()` que no comprobaba nada) con otra forma: **el
producto normal del fallo es un mensaje que parece un resultado.**

Y no lo caza ningún guardia de los que hay: no es un `except` que se traga nada, ni una
condición que no puede ser falsa, ni una función sin llamador. Se ejecuta entera, cada
vez, y devuelve algo plausible.

### La regla

Cuando dos valores se emparejan por una clave —un nombre de fichero, un rol, un
identificador de consulta—, **esa clave la produce UNA sola función**, y los dos lados la
piden. No se escribe en ninguno de los dos. Si el emparejamiento no se puede resolver, se
**aborta** diciéndolo: devolver el estado de «no se sabe» hace indistinguible un fallo de
cableado de una laguna legítima.

### Y el test no puede escribir la clave

Es la mitad que dejó pasar el fallo, y ya había dejado pasar otro tres días antes (errata
nº 44). Un test que construye el diccionario de entrada con el nombre que él mismo ha
escrito **pregunta por su propia respuesta**: coincide siempre, por construcción, y su
verde no dice nada del emparejamiento real. La clave se le pide al productor —aquí
`insumos.fichero_de` o `presentation.reference_md5s`— o el test se escribe **de punta a
punta**, poniendo el fichero en un directorio y mirando qué sale.

## 25 — Un test que ESCRIBE la clave por la que pregunta no puede fallar, y hay que poder buscarlos todos

**Formulado por el responsable del proyecto (2026-09-02)**, después de tres erratas
seguidas con la misma anatomía y con la consecuencia dicha en una frase: *«no basta con
arreglarlas de una en una»*. Es el principio nº 24 —los dos lados de una comparación
salen de la misma fuente— **convertido en auditoría**, con el segundo lado siendo el test.

### El patrón

```python
insumos.obsoleta("corrida_blast", payload, actuales={"base de datos de BLAST": "d" * 32})
```

El test construye el diccionario de entrada con el mismo nombre por el que el código va a
buscar. Coincide **por construcción**: pase lo que pase con el productor real de esa clave
—que la sufije por especie, que la normalice, que cambie de formato—, este test sigue en
verde. Su verde no dice nada del emparejamiento real, y mientras tanto **tapa** el fallo
estructural que habría destapado.

### Por qué es peor que un test que falta

Un test que falta se ve: alguien pregunta por la cobertura y aparece. Éste **ocupa el
sitio** del test que haría falta y da la señal contraria — es la familia de la errata
nº 29, donde `verify()` producía confianza infundada en vez de ausencia de información.

### La regla

Una clave que **algo produce** —un nombre de fichero, un identificador de consulta, un id
de corrida— se le **pide al productor**, también en los tests. Escribirla es admisible
sólo con el motivo declarado, y ese motivo caduca.

### Y la auditoría, porque una regla que no se puede buscar no se aplica

`tools/auditar_claves.py` la busca de dos formas, y la distinción entre ellas es lo que
la hace aplicable en vez de ruidosa (el barrido ancho daba 294 hallazgos, casi todos
correctos, y un auditor así se apaga el primer día):

- **VALORES** — el valor exacto usado como **clave** de un diccionario o conjunto que el
  test pasa a una llamada. Un literal suelto no cuenta: abrir el fichero real por su
  nombre es lo correcto.
- **FORMATO** — la **forma** de la familia, en literales y f-strings, sin docstrings.

Es un **guardia**: el número correcto es cero. Un test que no puede fallar no es deuda
pendiente que se salda cuando se pueda; es una comprobación que no comprueba.

## 26 — Dos guardias que opinan sobre el mismo hecho tienen que estar atados, o se separan

**Formulado por el responsable del proyecto (2026-09-02)** sobre un caso propio y con la
predicción incluida: *«con tres auditorías ya conviviendo, esto va a volver a pasar»*.

### El caso

`auditar_fixtures` reconocía que un test fabrica un artefacto **por el nombre del fichero
escrito en el test**. `auditar_claves`, estrenada el mismo día, **prohíbe escribirlo**: hay
que pedírselo al gestor. Dos guardias con reglas **opuestas** sobre la misma evidencia.

Al derivar el nombre, la fabricación siguió existiendo y su justificación —viva y
correcta— pasó a leerse como **caducada**. Ninguno de los dos falló; uno **dejó de ver** lo
que sí estaba.

### Por qué no basta con arreglarlo

El arreglo evidente es enseñarle a la primera a reconocer el alias. Eso cierra este caso y
deja el mecanismo entero en pie: la próxima auditoría que mire una evidencia ya vigilada
volverá a separarse, y el síntoma volverá a ser una justificación que se lee como
caducada, o un guardia que calla. **Es una condición que alguien tiene que recordar, y las
que hay que recordar se olvidan** — el mismo argumento por el que aquí nada se coordina a
mano.

### La regla

Cada auditoría declara **sobre qué evidencia opina** (`data/auditorias.toml`), escrita
igual cuando es la misma, junto con **cómo la reconoce** — que es donde dos criterios se
separan sin que nadie lo note. Dos entradas que comparten evidencia **tienen que declarar
un cruce**, y el cruce es un test que comprueba que las dos siguen de acuerdo sobre el
mismo material. `tests/test_auditorias_no_se_pisan.py` falla si falta.

Compartir evidencia no es un fallo: a menudo es lo correcto. Lo que no vale es compartirla
**sin nada que ate los dos criterios**.

### Y el cruce tiene que ser una comprobación, no una declaración

Un campo `cruce = "..."` que nadie ejecuta sería la errata nº 29 otra vez. Aquí el cruce
corre de verdad: da a los dos reconocedores el **mismo** material escrito de las dos
formas —el nombre literal y el derivado— y exige el **mismo veredicto**.

### Lo que encontró nada más estrenarse — y de quién era

Dos auditorías del repositorio sin declarar en ninguna parte
(`auditar_geometria`, `auditar_navegacion`), y que `guardias.toml` y `magnitudes.toml`
opinan **las dos** sobre quién calcula un digesto: hay que actualizar las dos al añadir un
sitio que hashea.

**Y eso último se me había olvidado dos veces en el mismo día**, con
`identidad.result_fingerprint` y con `identidad.file_fingerprint`. Las dos veces se cazó
**por casualidad**: la suite entera falló por otro motivo y la declaración que faltaba
apareció de paso. Sin eso habrían quedado dos sitios que hashean sin clasificar en una de
las dos tablas, y la siguiente duplicación habría entrado por ahí.

**Esto va al principio y no al mensaje del commit**, porque es el argumento entero:

> De las tres auditorías que se estrenaron ese día, **dos cazaron a la primera un
> descuido del mismo día de quien las estaba escribiendo**.

No es una anécdota simpática. Quien escribe un guardia es exactamente quien más cree que
no lo necesita —acaba de mirar ese código— y aun así falló dos veces en unas horas. **La
disciplina no sustituye al mecanismo, ni siquiera la de quien está escribiendo el
mecanismo.** Es la razón por la que aquí nada se coordina a mano, dicha con un caso propio
en vez de con un argumento.

## 27 — El mismo nombre para dos cantidades distintas es peor que el código repetido

**Pedido por el responsable del proyecto (2026-09-02)** como generalización de los cuatro
pares duplicados, con el diagnóstico ya hecho:

> No es código repetido, es peor — es una cantidad que se mueve de contexto sin el
> supuesto que la sostenía. Allí todos los hits son de longitud completa por
> construcción, así que la condición de longitud no hacía falta escribirla; al mover el
> criterio, el supuesto se quedó atrás.

**Código repetido se ve en un `grep`.** Esto no: los dos sitios se leen bien por separado,
el nombre es el mismo, y lo que difiere es **qué mide** — que no está escrito en ninguna
parte porque en su módulo de origen era obvio.

### El caso, con las dos mitades

`antisense` existe en `blast.BlastHit` y en `specificity.Hit`:

- en nuestro escáner significa **«la sonda puede aparearse con este transcrito»**, y por
  eso descartar los hits en sentido es correcto ahí;
- en `-outfmt 6` es **«la hebra del sujeto tal como está depositado»**. Coincide para una
  guía y **no** para la pasajera, que lleva la misma secuencia que su blanco.

Y en el mismo par, `aligned`, que es la mitad más instructiva porque **la unidad es la
misma y la propiedad estadística es opuesta**: en el escáner vale siempre `len(sonda)`
—casa ventanas de esa longitud exacta—, en BLAST es un alineamiento **local**. El
criterio no necesitaba mirarla en un lado, y por eso nadie la escribió; al moverlo, los
parciales de 13 nt entraron como aciertos graves.

### El corolario, que es la regla operativa

**Un criterio que se copia entre módulos tiene que llevar sus supuestos escritos, y si no
se pueden escribir es que no se puede copiar.** La forma que toma aquí: el criterio vive
en un solo sitio y **cada llamador declara qué puede probar** antes de someterle sus
datos, en vez de compartir además el descarte.

### El mecanismo, porque la disciplina no basta

`data/homonimos.toml` + `tools/auditar_homonimos.py`, guardia con cero. Se declaran las
**magnitudes derivadas** —`@property`, algo que se calcula— con el mismo nombre en más de
un módulo, y cada una dice si son la misma magnitud o **cantidades distintas**, con qué
es cada una.

El recorte es lo que lo hace aplicable, y está medido: el barrido ancho de «cualquier
nombre definido en más de un módulo» da **207**, casi todas etiquetas (`name`, `date`,
`reason`). Acotado a lo derivado son **23**, y **siete son cantidades distintas**. Un
campo guardado es una etiqueta; **una derivación lleva supuestos dentro**, que es
exactamente lo que se queda atrás al moverla.

### Lo que encontró al estrenarse

Además de `antisense` y `aligned`: `usable`, que en tres clases es «este dato se puede
usar» y en `splicing.PrimerWindow` es «esta ventana es única en el plásmido»; `md5`, que
es el del texto en un lado y el de la secuencia en el otro —la trampa de los tres
checksums, dentro del código—; `conclusive`, `ambiguous` y `fraction`. Y una que ya no
sale porque se arregló: **`selection.Site.end` devolvía el inicio de la última ventana
del bloque**, mientras en todo el resto del paquete `end` es un final de intervalo
inclusivo. Leída como final, dejaba el sitio 21 nt más corto. **Ninguna salida la leía**
—el número equivocado nunca llegó a una pantalla— **pero sí la leía un test**, que la
afirmaba como final de intervalo: `(10, 12)` para tres ventanas de 22 nt. Código y test
compartían la confusión, así que ninguno de los dos podía delatarla (principio nº 22), y
renombrarla salía gratis porque no había producción que romper.

---

## 28 — Un estado tiene que decir la verdad aunque no cambie nada, porque el día que cambie el de al lado empieza a decidir

Lo formuló quien reportó la errata nº 61, y es la generalización de aquel arreglo:

> un estado tiene que decir la verdad aunque no cambie nada, porque el día que cambie el
> de al lado ese estado empieza a decidir.

**El caso que lo enseña.** `seed` salía `NO_APLICA` en los diez candidatos cuando lo
honesto era `NOT_RUN` — faltaba el fichero, no es que la pregunta no fuera con ellos—.
Mientras `seed_colision` decía `NOT_RUN` a su lado, ese `NO_APLICA` **no cambiaba ningún
veredicto**: el candidato salía `INCOMPLETE` por la otra columna igual. Era un error sin
consecuencia visible, así que nadie lo miró. En cuanto `seed_colision` pasó a cerrar con
el núcleo de diez miARN —un cambio que no tocó `seed` ni de lejos—, aquel `NO_APLICA`
empezó a ser el que decidía, y decidía mal.

**Por qué no es «arreglar los errores aunque sean pequeños».** Es más concreto que eso:
un estado con la verdad cambiada NO ES un error latente que quizá algún día importe. Es
un error que **cambia de consecuencia** cuando cambia algo que no lo toca. Y el momento
en que empieza a decidir es exactamente el momento en que nadie está mirando esa columna:
se estaba mirando la de al lado, que es la que se acaba de arreglar.

**Corolario de método**: arreglar el estado de una columna es el mejor momento para
releer las de su misma agregación. No porque las haya roto —no las ha tocado— sino porque
acaba de cambiar **quién manda** entre ellas, y un error que estaba tapado por la anterior
sale a la superficie en la misma tanda. Fue así como se encontró el segundo estado
equivocado de la errata nº 61: no lo cazó ningún test, lo cazó preguntarse qué había
quedado debajo.

**En qué se aplica esto.** En un `PASS`/`FAIL`/`NOT_RUN`/`NO_APLICA` que no bloquea hoy,
en un contador que hoy nadie suma, en una fecha que hoy nadie compara. Todos son datos
que alguien va a leer después con otra regla de agregación. La regla es que el valor sea
el que corresponde al hecho, no el que produce la salida correcta con las reglas de hoy —
que es lo mismo que decir que un estado se decide mirando el hecho, no la consecuencia.

## 29 — Una consulta que omite una DIMENSIÓN del modelo no da error: contesta «no sé», y eso se lee como «no hay»

Sale de la errata nº 71, y generaliza un fallo que costó que **una corrida de colisión de
seed o de carga de off-targets no pudiera cerrar su frente nunca**.

Cuando el modelo declara que algo tiene partes —por hebra, por par candidato × intrón, por
clase de sitio— toda consulta que lo atraviese tiene **una dimensión más de la que se ve en
la firma**. Preguntar sin ella no es un error de tipo ni una excepción: la función devuelve
lo que devuelve cuando no sabe, y lo que no sabe es indistinguible de lo que no hay.

### Por qué es peor que el código repetido y que el símbolo sin llamador

Las dos mitades pueden ser **correctas por separado**, y en el caso que lo motiva lo eran:

- devolver `None` a un frente por hebra preguntado sin hebra es deliberado, y sigue
  siendo lo correcto — fundir las dos daría por buena la de la pasajera con el estado de
  la guía;
- preguntar por el nombre del frente es su clave natural.

El fallo vive en la **junta**, así que ninguna revisión de una de las dos piezas lo ve. Y
ninguna de las herramientas que este proyecto ya tiene puede cazarlo:

- **la alcanzabilidad** mira símbolos sin llamador, y aquí las dos funciones tienen
  llamadores;
- **el golden** lee lo que se emite, y lo que se emitía era un estado con la forma
  correcta;
- **el auditor de homónimos** mira magnitudes con el mismo nombre, y aquí el nombre es el
  mismo a propósito.

### La regla operativa

**Declarar la dimensión no basta: hay que DERIVAR de la declaración cada consulta que la
atraviesa, y el test tiene que iterar la declaración, no el caso.** Un test escrito para
`seed_colision` pasa igual el día que entre un cuarto almacén por hebra.

Y con su mitad adversaria, que aquí es doble: quitar **una** parte de la dimensión tiene
que impedir la respuesta, y preguntar **sin** la dimensión tiene que seguir sin contestar.
Sin la primera, «contesta» y «no mira nada» dan el mismo verde; sin la segunda, el arreglo
obvio —devolver la parte que haya— borraría la otra sin dar ningún error.

### Cómo se reconoce antes de que pase

La pregunta que hay que hacerse al escribir una consulta contra algo que tiene partes:
**¿qué devuelve esto si le falta una parte, y se distingue de «no hay nada»?** Si la
respuesta es `None`, `{}`, `0` o una lista vacía, y ese mismo valor es el que sale cuando
de verdad no hay nada, la consulta no está mal escrita — está **muda**, que es la forma que
tiene un fallo de durar semanas.

Es el mismo criterio que separa `NOT_RUN` de `NO_APLICA`, y que separa `None` de
`frozenset()` en el acotado de la carga de seed: **dos cosas distintas no pueden compartir
valor**. Aquí la que se colaba era una tercera —«no te he entendido la pregunta»—
compartiendo valor con «no hay corrida».

## 30 — Un fallo que depende del TAMAÑO no se reproduce con un fixture pequeño, y el determinismo no es estética

Sale de la errata nº 76, y son dos lecciones que van juntas porque el mismo fallo las
enseña por los dos lados.

### La primera: el fixture pequeño da un verde falso

Reproduje la descarga del zip **de punta a punta, con un navegador de verdad, midiendo**,
y salió perfecta: 1,19 MB, 28 entradas, nombre correcto. Y el fallo estaba ahí todo el
rato. Lo que separaba mi prueba del caso real no era el camino —era **el tamaño**: la
carrera entre la descarga en curso y el repintado que borra el fichero la gana la descarga
cuando dura 200 ms y la pierde cuando dura veinte segundos.

O sea: **una reproducción que sale bien con un fixture pequeño no descarta un fallo que
depende del tamaño**, y creer que sí es peor que no haber probado — porque cierra la
investigación. La contramedida es preguntarse siempre, antes de dar por bueno un verde:
*¿de qué magnitud depende esto, y la he variado?* Si la respuesta es que no, lo que se ha
comprobado es que el camino existe, no que funcione.

Es hermana del principio nº 3 —no dar por buena una causa sin comprobarla— aplicada al
otro lado: **tampoco se da por buena una AUSENCIA de causa** medida en un solo punto de un
eje que sí importa.

### La segunda: un artefacto que cambia de bytes sin cambiar de contenido rompe todo lo
que lo identifique por su contenido

Poner fecha fija en el zip parece una corrección estética —«que salga igual, queda más
limpio»— y no lo es. En cuanto **algo identifica ese artefacto por su contenido**, dos
construcciones del mismo contenido son dos artefactos distintos:

- Streamlit deriva el id de un descargable de su md5, así que el que se está bajando queda
  huérfano y lo borra el recolector;
- lo mismo le pasaría a cualquier caché, a cualquier deduplicación y a cualquier
  comprobación de integridad que alguien quiera hacer sobre el fichero entregado.

**La regla: si un artefacto se va a identificar, transportar o comprobar por su contenido,
tiene que ser función de su contenido y de nada más.** El reloj no es contenido.

### Y el corolario que salió al aplicarlo: fijar no es poner a cero

La marca de tiempo **no se pone a cero**: se deriva de la fecha declarada. Dos copias de
seguridad de días distintos tienen que seguir siendo **dos ficheros distintos** — si no,
no hay forma de saber cuál es cuál, y la que se conserva no dice de cuándo es. Lo que se
quita es la parte que cambia sin que nadie haya cambiado nada; lo que identifica de verdad
se queda.

---

## 31 — Un comentario protege su clase; un mecanismo protege la siguiente

**El caso, y es literal.** `offtarget.WHY_NOT_SUMMED` termina, escrito semanas antes:

> «`Counts` no tiene ningún atributo que las sume: **si existiera, alguien acabaría
> imprimiéndolo**.»

El guardia se puso sobre `offtarget.Counts`. **El atributo existía en
`seed_load.SeedLoad`** —`total = sum(counts.values())`— **y se estaba imprimiendo**, en la
única columna visible de ese eje. La profecía se cumplió al pie de la letra, en la clase de
al lado, mientras el comentario que la anunciaba seguía ahí sin que nadie lo relacionara.

### Por qué no es un descuido puntual

Un comentario es un aviso **a quien lee esa clase**. Nadie lee la clase de al lado buscando
un aviso que está en otro fichero, y menos aún el día que la escribe: quien la escribe cree
que ya conoce la regla. La disciplina se agota exactamente donde hace falta.

### La regla operativa

**Un guardia no nombra a quién protege: lo DESCUBRE.** El test que sustituyó al comentario
no pregunta por `Counts` ni por `SeedLoad` — barre el paquete, encuentra qué clases llevan
conteos por clase y se lo exige a todas. Un contador nuevo queda cubierto **sin que nadie se
acuerde**, que es la única forma en que un guardia sobrevive a su autor.

Es hermano del principio nº 26 —dos auditorías sobre la misma evidencia se atan— y del
nº 14: haber comprobado una vez no es seguir comprobando. Aquí: haberlo **escrito** una vez
no es que proteja.

---

## 32 — Una clave sin escritor no falla: su valor por defecto pasa a ser la configuración

**No se parece al principio nº 24.** Allí —la comparación de md5 que preguntaba por una
clave que no podía existir— el resultado era una **respuesta falsa**: «no se ha podido
comprobar» con el fichero delante. Aquí no hay ninguna respuesta falsa: hay **siempre el
valor por defecto**, y entonces pasa algo distinto y peor.

**El literal escrito como plan B se convierte en la configuración real, y nadie lo revisa
como tal.** Se escribe pensando «esto es lo que pasa si falta», se lee como una precaución,
y es lo único que se ejecuta nunca. Un `"sin fecha declarada"` puesto para ser honesto
acabó siendo el valor con el que se generaban **todos** los informes (errata nº 89).

### Y dos llamadores con dos defaults distintos son dos configuraciones distintas

Para la misma clave, y ninguna declarada en ningún sitio, así que **no hay dónde mirarlas
juntas**. En el caso real una funcionaba (`"" or today_text()`) y la otra abortaba, y eso
es justo lo que hizo que el fallo pareciera del zip y no de la fecha.

### La contramedida es mecánica

Ninguna clave de estado de sesión puede leerse sin que alguien la escriba. A cero, con
control adversario —si el detector dejara de encontrar claves, «ninguna huérfana» y «no he
mirado» darían el mismo verde (nº 24)— y **quitando los comentarios antes de mirar**: el
comentario que explica de dónde venía la clave la nombra, y sin la poda el guardia fallaría
por su propia documentación, con la salida fácil de borrar la explicación.

---

## 33 — El guardia estaba, y la pregunta no le llegaba

Variante del principio nº 29 —una consulta que omite una dimensión contesta «no sé» y se lee
como «no hay»— con el fallo un paso antes: aquí **la consulta no llega a hacerse**.

**El caso (2026-09-04, errata nº 90).** `comparative_tsv` aceptaba `anatomy`, los **dos**
llamadores se lo pasaban, y llamaba a `comparative_rows(selection, scaffold)` **sin
reenviarlo**. Consecuencia: la **cabecera** del TSV se construía con la anatomía que se le
daba y las **filas** con otra. Y el invariante de rango de `coords` —que existe justo para
cazar una coordenada en el marco equivocado y ya ha mordido cuatro veces— **no podía
morder**, porque el dato que lo habría activado nunca llegaba a su lado.

No hubo síntoma. Hoy las dos anatomías coinciden, así que el argumento inerte no producía
ningún número equivocado; producía **un guardia dormido**, esperando al día en que dejaran
de coincidir.

### Por qué es su propia categoría

Las herramientas del proyecto no lo ven, y ninguna por descuido:

- la **alcanzabilidad** mira símbolos sin llamador, y aquí hay llamador;
- el **golden** lee lo que se emite, y lo que se emitía tenía la forma correcta;
- el auditor de **banderas** cubre los CLI, no los argumentos entre funciones;
- y el propio invariante no puede quejarse de una pregunta que no recibe.

### Cómo se reconoce

**Un parámetro que se acepta y no se usa es un guardia apagado, no una firma de más.** La
señal está en la firma: si una función declara un argumento, hay que poder señalar la línea
donde lo consume. Si esa línea no existe, no sobra el argumento — falta el uso, y lo que
depende de él lleva dormido desde que se escribió.

### Y NO tiene mecanismo: se midió, y no sale

Este proyecto no escribe un auditor sin medir antes el ruido, porque **un guardia con
falsos positivos se acaba apagando**. Se probaron las dos formas obvias, sobre el paquete
entero (2026-09-04):

| detector | hallazgos | qué son |
|---|---|---|
| parámetro declarado y **nunca referenciado** | **35** | casi todos legítimos: implementaciones que comparten firma por interfaz (`Executor.run`), validadores con firma común (`deposito._v_*`) |
| F acepta `P`, llama a G que también acepta `P`, y no se lo pasa **por nombre** | **686** | dominado por el paso **posicional**, que es correcto |

**Y el primero no habría cazado el caso real**, que es lo que lo zanja: `anatomy` **sí se
usaba** dentro de `comparative_tsv` —construía la cabecera con ella— y lo que faltaba era
reenviarla a la función que monta las filas. Un detector de «argumento sin usar» lo habría
dado por bueno.

Así que este principio se queda como **regla de lectura**, no como guardia, y eso va
escrito para que nadie suponga que hay una red debajo. Lo que sí lo cazó fue **leer el
diff** de una firma al tocarla, que es donde aparece: la línea que consume el argumento se
busca a mano cuando se edita esa función. Es la misma categoría que el principio nº 3 —hay
comprobaciones que hoy sólo hace una persona— y se anota como tal en vez de fingir cobertura.

Y el corolario que lo cerró: **al dejar de tragárselo, un test empezó a abortar.** Ese test
declaraba en la cabecera una anatomía incompatible con lo tilado, y sólo pasaba porque el
argumento no llegaba. Cuando un guardia se despierta y algo falla, lo primero que hay que
preguntarse no es cómo callarlo: es qué llevaba pasando mientras dormía.

---

## 34 — Un guardia se CALIBRA midiendo, no eligiendo el criterio que suena bien

Sale del barrido de la errata nº 95, y el método importa más que el hallazgo.

### Los tres pasos, con sus números

Buscando «recortes de una secuencia con una posición ajena» sobre el paquete entero:

| criterio | hallazgos | de ésos, fallos | sirve |
|---|---|---|---|
| cualquier recorte 1-based, `x[start - 1:end]` | **50** | 1 | **no**: 49 correctos, se apaga el primer día |
| indexado por un `.start` de otro objeto | **10** | 1 | **no**: 9 correctos |
| **la secuencia y la posición son dos parámetros distintos de la misma función** | **1** | **1** | **sí**: cero falsos positivos |

El primero es el que «suena bien» —es literalmente la forma del fallo— y es inservible.
El tercero no describe la forma: describe **de dónde vienen las dos cosas**.

### La formulación que discrimina, y por qué

En los 49 correctos la posición **se deriva** de la secuencia que se recorta: un `Span.of`
sobre algo que se acaba de buscar ahí, o dos campos del mismo objeto (`self.plasmid` y
`self.start`). En el fallo **llegan como dos argumentos independientes**, y entonces nada
—ni un tipo, ni un invariante, ni el propio código— obliga a que compartan marco.

**La forma del fallo y la condición que lo hace posible no son la misma cosa**, y sólo la
segunda sirve para un guardia. Buscar la forma da todos los usos legítimos de esa forma;
buscar la condición da los sitios donde el fallo **puede** ocurrir.

### El método, que es lo que se conserva

1. **enunciar varios criterios**, del ancho al estrecho;
2. **medir cada uno sobre el código real**, contando hallazgos **y cuántos son fallos;**
3. **quedarse con el que discrimina**, no con el que describe mejor el síntoma;
4. y **escribir la formulación ganadora**, porque es lo que hay que reconocer la próxima
   vez — no el número.

Un guardia con falsos positivos se acaba apagando, así que **un criterio sin medir no se
publica**. Y el corolario: si ningún criterio discrimina, el resultado honesto es que **no
hay mecanismo** y se dice (principio nº 33), no un auditor ruidoso que nadie mirará.

## 35 — Lo que viaja pegado a los datos sobrevive; el nombre del fichero no

Sale de la errata nº 101, y de un `mv` real: *«un nombre se pierde en el primer `mv` — a
mí me pasó hoy mismo renombrando el fichero para quitarle un espacio»*.

Un artefacto que sale de la app **viaja solo**. Se descarga, se renombra, se mueve, se
comprime, se adjunta, se sube a otra máquina, y en algún punto llega a alguien que **no
tuvo la pantalla delante** cuando se generó. Todo lo que sepa de él, lo tiene que sacar del
propio fichero.

### La jerarquía, de lo más frágil a lo más resistente

| canal | sobrevive a | lo tira |
|---|---|---|
| el nombre del fichero | nada | cualquier `mv`, cualquier descarga que resuelva un choque de nombres |
| una carpeta, un ZIP, un correo alrededor | poco | descomprimir, reenviar |
| un bloque de comentario dentro | renombrar, mover, comprimir | un lector estricto del formato |
| **un campo del propio formato** | **todo lo anterior** | nada que siga leyendo ese formato |

**El nombre es documentación; el contenido es dato.** Un estado, una convención, una
procedencia o una versión que sólo viven en el nombre están escritos en el canal más
frágil de todos.

### La regla

Todo lo que haga falta para **interpretar** un artefacto va DENTRO del artefacto, en el
canal más resistente que el formato permita, y se repite en los más cómodos de leer. En un
FASTA: el bloque `#` para leerlo de un vistazo **y** la cabecera `>` de cada registro, que
es la que no se puede perder. En un TSV: una línea de comentario declarada **y** columnas
que no dependan de ella.

Qué entra en «hace falta para interpretarlo»: la **convención** de cualquier posición
(errata nº 99), el **estado** de la corrida —si está entera o falta la mitad—, la
**procedencia** de las entradas y la **versión** de lo que lo produjo.

### Y el límite, que es la otra mitad

**Lo que no se sabe no se declara.** Un FASTA construido sin saber de qué panel viene no
pone «COMPLETO» por defecto: no pone nada. Rellenar el hueco con la mitad tranquilizadora
es peor que dejarlo vacío, porque un campo presente se lee como comprobado — es el
principio nº 32 aplicado al artefacto en vez de a la configuración.
