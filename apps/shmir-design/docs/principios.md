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

Es la tercera vez que el mismo fallo sale en esta app, siempre igual: un texto plausible,
escrito a mano junto a un dato, que nombra una causa que nadie ha mirado.

| mensaje | lo que decía | lo que era |
|---|---|---|
| `/shmir` no arranca | «comprueba que Streamlit está instalado» | Streamlit estaba instalado y corriendo: era un conflicto de configuración |
| máscara de RepeatMasker | «Alu 0 %» | 0 % obtenido **sin buscar Alu**: la corrida era contra otra biblioteca |
| 1773 ventanas descartadas | «bases desconocidas o enmascaradas» | ninguna tenía `N` ni estaba enmascarada: fallaban GC y homopolímero |

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
