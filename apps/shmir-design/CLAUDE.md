# shmir-design — reglas del proyecto

> **Ámbito.** Este fichero es vinculante para todo lo que hay bajo `apps/shmir-design/`.
> El resto del hub (`server.js`, `apps/re-memory/`, `src/`) es Node/Express y NO se rige
> por estas reglas. shmir-design es un proyecto Python independiente que vive dentro del
> mismo repositorio.
>
> Si una petición choca con una de estas reglas, la regla gana. No se negocian, no se
> relajan "solo para esta vez" y no se saltan porque el resultado parezca razonable.

---

## Reglas innegociables

**1. NUNCA generes, completes ni "reconstruyas" secuencias biológicas.** Si falta una
secuencia, aborta con un error explícito. Una secuencia inventada que parece plausible
es el peor resultado posible de este software.

**2. PROHIBIDO `except: pass` y `except Exception: return None`.** Todo fallo de red,
de parseo o de fichero debe propagarse con un mensaje que diga QUÉ falló y QUÉ paso
queda sin ejecutar.

**3. Todo filtro que dependa de un recurso externo debe registrar en la salida si se
ejecutó, si se saltó, y por qué.** Un candidato nunca puede aparecer como "PASS" si un
filtro no llegó a correr. Usa tres estados: `PASS` / `FAIL` / `NOT_RUN`.

**4. Antes de usar cualquier endpoint o URL externa, verifica que responde y que el
formato es el esperado.** Si no lo has verificado, no lo escribas: pregunta. No inventes
URLs de API a partir de patrones.

**5. Escribe los tests ANTES de la funcionalidad.** Los tests usan datos reales
proporcionados, no datos sintéticos.

**6. Python 3.11+, solo librería estándar** salvo donde se autorice explícitamente una
dependencia. Sin frameworks web en la v1.

---

## Cómo se aplica cada regla

### Regla 1 — Secuencias

Queda prohibido, sin excepción:

- rellenar huecos/gaps con cualquier base o residuo;
- retro-traducir proteína a nucleótido para "recuperar" una secuencia ausente;
- reconstruir una secuencia por consenso, por homología o por el modelo;
- sustituir una secuencia ausente por una placeholder (`"NNNN..."`, `""`, cadena de
  ejemplo) que luego pueda circular como si fuera dato;
- usar secuencias inventadas en tests, fixtures, docstrings o ejemplos del README.

Si falta una secuencia, el flujo aborta:

```python
raise MissingSequenceError(
    f"No hay secuencia para {accession!r} en {source}; "
    f"se aborta el paso 'alineamiento de candidatos' (0 de {n} candidatos procesados)."
)
```

El error debe nombrar el identificador, de dónde se esperaba obtenerlo y qué paso queda
sin ejecutar. Nunca se degrada a warning.

### Regla 2 — Errores

- Prohibidos: `except:`, `except Exception: pass`, `except Exception: return None`,
  `contextlib.suppress(Exception)` y cualquier variante que borre el fallo.
- Capturar solo excepciones concretas y solo para **añadir contexto y relanzar**:

```python
try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    raise ParseError(
        f"Respuesta de {url} no es JSON válido ({exc}); "
        f"se aborta el filtro 'conservación' para {accession}."
    ) from exc
```

- `raise ... from exc` siempre: la causa original no se pierde.
- Un `except` con `pass` solo es admisible si la excepción es concreta, el caso está
  documentado en el propio bloque y no oculta ningún fallo de red, parseo o fichero.
  Ante la duda: propagar.

### Regla 3 — Estado de los filtros

Todo filtro devuelve uno de tres estados, nunca un booleano:

| Estado | Significado |
|---|---|
| `PASS` | El filtro corrió con todos sus recursos y el candidato lo supera. |
| `FAIL` | El filtro corrió con todos sus recursos y el candidato no lo supera. |
| `NOT_RUN` | El filtro no llegó a ejecutarse (recurso externo caído, dato ausente, sin autorización). |
| `NO_APLICA` | La pregunta no va con ese candidato (p. ej. polyA sobre una ventana del ORF). |

Reglas de agregación:

- Un candidato con **cualquier** filtro en `NOT_RUN` no puede reportarse como aprobado.
  Su veredicto global es `INCOMPLETE`, nunca `PASS`.
- `NO_APLICA` **no** es una cuarta forma de `NOT_RUN`. `NOT_RUN` dice "no pude
  comprobarlo": es una laguna, y una laguna impide aprobar. `NO_APLICA` dice "esa
  pregunta no se le hace a este candidato". No estorba al veredicto — pero si TODO sale
  `NO_APLICA` el veredicto es `INCOMPLETE`, porque no se llegó a preguntar nada. Nunca
  se usa para esquivar un filtro que sí aplicaba.
- Un número comparativo (carga de seed, accesibilidad) que no se calculó va **vacío** en
  la tabla, nunca a cero: no haber contado y contar cero son cosas distintas.
- Todo `NOT_RUN` y todo `FAIL` llevan un `reason` legible que dice qué recurso faltó.
- La salida (CSV, JSON o texto) incluye una columna/campo por filtro con su estado. No
  se colapsan filtros ni se omiten los que no corrieron: un filtro ausente de la salida
  es indistinguible de un filtro superado, y eso es exactamente lo que la regla prohíbe.
- El resumen final indica cuántos candidatos son `INCOMPLETE` y por qué filtro.

### Regla 4 — Endpoints externos

- Ninguna URL externa se escribe en el código sin haber sido verificada antes
  (responde, y el formato es el esperado).
- Las URLs verificadas se registran en `docs/endpoints-verificados.md` con fecha,
  petición exacta y forma de la respuesta. **Ese registro está hoy vacío.** Y desde que
  los datos de referencia son fixtures, ningún paso del análisis depende de la red:
  si necesitas un recurso externo nuevo, se descarga a mano y se versiona con checksum,
  no se llama en tiempo de ejecución.
- Prohibido deducir una URL "por patrón" a partir de otra que sí existe, o de memoria
  sobre cómo suele ser la API de un servicio.
- Sin verificación no se escribe: se pregunta.

### Regla 5 — Tests primero, con datos reales

- El commit que añade funcionalidad llega con sus tests ya escritos y fallando antes.
- Los datos de referencia viven en `data/reference/` como fixtures versionados y cada
  uno lleva su procedencia y su md5 en `data/reference/PROCEDENCIA.md`. Se cargan
  siempre por una funcion que verifica el checksum y aborta si no cuadra; nunca se lee
  el fichero directamente desde un filtro. Ver `docs/fixtures.md`.
- Prohibido fabricar secuencias de ejemplo para un test (es la regla 1 por otra puerta).
  Si no hay dato real para cubrir un caso, el test no se inventa: se pide el dato.

### Regla 6 — Entorno

- Python 3.11+ (`match`, `tomllib`, `ExceptionGroup` disponibles), solo `stdlib` en
  **todo** `shmir_design/` y en los `tools/`.
- La interfaz Streamlit (`ui/streamlit_app.py`) es la única excepción autorizada, y con
  una condición: **no contiene lógica**. Lo que decide algo vive en
  `shmir_design/presentation.py`, con tests. Si la UI empieza a decidir —ordenar,
  filtrar, elegir un color según un umbral— eso se arregla moviéndolo al núcleo, no
  añadiendo más código a la página.
- El núcleo y los CLI tienen que seguir funcionando sin Streamlit instalado.
- Cada dependencia externa requiere autorización explícita y queda anotada en
  `docs/dependencias-autorizadas.md` con quién la autorizó y para qué. Hoy hay dos, las
  dos OPCIONALES y ninguna en el núcleo: `streamlit` (interfaz) y `ViennaRNA` (plegado).
  Sin ellas, el núcleo y los CLI funcionan igual.

---

## Verificación

`tools/check_rules.py` analiza el AST de los ficheros Python de `apps/shmir-design/` y
falla si encuentra manejo de errores prohibido por la regla 2:

```bash
npm run check:shmir   # o: python3 apps/shmir-design/tools/check_rules.py [ruta ...]
npm run test:shmir    # o: cd apps/shmir-design && python3 -m unittest discover -s tests -t .
```

Pásalos antes de cada commit que toque `apps/shmir-design/`.

---

## Antes de dar por terminado cualquier cambio aquí

1. ¿Alguna ruta del código puede producir una secuencia que no venga íntegra de la
   entrada? → arréglalo o aborta.
2. ¿Algún `except` se traga un fallo de red, parseo o fichero? → `check_rules.py`.
3. ¿Cada filtro emite `PASS`/`FAIL`/`NOT_RUN` con motivo, y ningún `NOT_RUN` acaba
   reportado como aprobado?
4. ¿Toda URL nueva está en `docs/endpoints-verificados.md` con su verificación?
5. ¿Los tests se escribieron antes y usan datos reales con procedencia registrada?
6. ¿Sigue siendo stdlib pura, o hay una autorización escrita para la dependencia nueva?

## Estado actual (bloqueantes)

- **`--usar-manifiesto` es la forma normal de correr.** Conecta cada fichero de
  `data/reference/` que esté en `OK` con el filtro que su rol declara, tomando la
  versión y el md5 del propio manifiesto. Sustituye a 31 flags de fontanería, y cierra
  un fallo real: antes se podía teclear `--refseq-version 2024` apuntando a un fichero
  de 2026 y nadie se enteraba, porque el fichero y su versión iban por separado. La
  correspondencia fichero→filtro vive en `manifest.ROLES`, **en código**: como séptima
  columna del manifiesto se podría reasignar un fichero a otro filtro sin que se viera
  en el diff. Una flag explícita sigue mandando, pero se dice en la consola.
- **La interfaz llega a los mismos ficheros que el CLI.** La casilla «Usar los de
  `data/reference/`» llama a `resources.load_from_manifest`, que devuelve los objetos ya
  cargados con la version y el md5 del manifiesto. Antes la pagina pasaba tres de los
  catorce parametros de `tile_utr`, asi que **el semaforo verde era estructuralmente
  inalcanzable desde el navegador**: todos los filtros con fichero salian NOT_RUN
  pasara lo que pasara. El gen diana va aparte porque es un accession, no un fichero, y
  el manifiesto no lo sabe.
- **La pagina no lanza nada sola**: hay dos botones, «Estimar coste» y «Diseñar». La
  estimacion (`presentation.cost_text`) no diseña nada y no aplica la mascara, asi que
  su total es un techo y lo dice. Antes el diseño arrancaba al subir el FASTA, asi que
  una corrida de minutos empezaba sin avisar y la estimacion habria llegado tarde.
- **`data/reference/manifest.tsv` se versiona en git; los ficheros de datos NO.** Un
  RefSeq RNA completo no entra en el repositorio; lo que entra es la línea que dice cuál
  era y cómo comprobarlo. Cada informe copia las líneas de los ficheros que usó: sin eso
  un veredicto no es auditable dentro de un año. `tools/check_data.py` valida el
  directorio y dice qué filtros pueden correr, sin lanzar ningún diseño.
- **Ojo con los dos checksums**: el md5 del manifiesto es el del FICHERO en disco; el que
  `reference.py` verifica es el de la SECUENCIA canónica (mayúsculas, sin cabecera, sin
  saltos). Son cantidades distintas y copiar una en la otra haría que el fichero bueno se
  rechazara. Hay un test que comprueba que no se confunden.
- **Un eje que la selección no cubre puede significar dos cosas** y el informe las
  distingue: que la piscina de elegibles sí tenía los dos extremos y la selección no los
  cogió (se arregla con `--reparto-rango`), o que la piscina entera está apretada. Lo
  segundo **no es un fallo**: es información, y el informe dice con esas palabras que ese
  eje no se puede estudiar con ese 3'UTR y hay que dejar de tratarlo como variable. Para
  los ejes continuos no basta con tocar dos bins: hace falta recorrido (`MIN_SPAN`).
- **Los datos de referencia son fixtures versionados**, no descargas: `data/reference/`,
  verificados por checksum en cada carga (`docs/fixtures.md`). Nada del análisis depende
  de la red. Los dos `.fa` todavía no están en el repositorio, así que 7 tests se saltan
  de forma visible; no se rellenan con secuencia sintética.
- **No hay endpoints verificados desde este proyecto.** Por eso `shmir_design/fetch.py`
  no contiene ninguna URL y `tools/reference_data.py --fetch` exige `--efetch-url`. Eso
  solo afecta al camino opcional de descarga.
- La asimetría (paso 7) usa un **proxy heurístico**, no una energía libre de dúplex: ver
  la advertencia en `thermo.py` y mantenerla. Su especificación tuvo un error de signo
  que ningún test de consistencia interna habría detectado; por eso hay dos tests de
  cordura biológica que fijan los signos. No los borres ni los "arregles" para que pase
  un valor nuevo: si fallan, la especificación es lo que hay que revisar.
- **Dos contadores, nunca uno**: `biofisicos_ok` (los seis filtros biofísicos, sin
  recursos externos) y `aptas` (veredicto `PASS`). Mezclarlos es lo que hace que un
  candidato incompleto parezca aprobado. Ver `docs/pipeline.md`.
- La lista de 12 seeds de `seeds.py` es un **arranque para probar la mecánica**, no un
  filtro real: el filtro real necesita `mature.fa` de miRBase completo. El aviso va en
  el código y en cada informe; no lo quites.
- Una ventana con `N` no es evaluable: sus filtros de secuencia salen en `NOT_RUN`, no
  en `PASS` ni en `FAIL`.
- El límite del riesgo de APA es la **señal**, no el sitio de corte (10-30 nt aguas
  abajo): sobre-marca a propósito y no es una predicción del extremo de la isoforma
  corta.
- El andamio miR-E (`scaffold.py`) está verificado en el 97-mero y **solo** ahí; los
  flancos extendidos del pri-miR siguen sin decidir.
- **La regla de la pasajera es ESTRUCTURAL, no una tabla.** Se pliegan las cuatro bases
  posibles para la posición 1 y se elige una cuyo 97-mero reproduzca la notación
  punto-paréntesis de SGEP; `C > A > G > T` sólo desempata cuando hay varias, y si no
  hay ninguna se aborta enseñando las cuatro estructuras. **No la sustituyas por una
  tabla por terminación**: eso es lo que había antes y falló — le faltaba el
  apareamiento tambaleante `G:U`, así que con guía acabada en G la T también está
  prohibida y la A, que no aparea con nada, deja un bulge de 2 nt en vez de 1. Sin
  ViennaRNA el criterio no se puede aplicar: la pasajera sale con `structural_check =
  NOT_RUN` y un aviso que dice que esa elección está comprobada como incorrecta.
- **El filtro de poliadenilación es escalonado**: FAIL duro solo para la señal terminal
  y para `AATAAA`/`ATTAAA` en `APA_POSIBLE`; las variantes raras dejan bandera y
  penalización de ranking. El informe saca las dos cifras de elegibles.
- **Cada informe dice QUÉ se analizó**: longitud y md5 canónico de la secuencia de
  entrada (`TilingReport.sequence_length` / `.sequence_md5`). Sin esas dos cifras no hay
  forma de saber a posteriori qué se pasó — y la errata del 3'UTR fabricado se detectó
  precisamente por longitud contra las coordenadas declaradas. El manifiesto registra lo
  mismo por fichero: `accession` con versión, `longitud` y `url`, con un test que ata las
  dos parejas del ratón (2191 nt / `44fb8cd8…` y 3'UTR 1242 nt / `19f5fa2a…`).
- **Dos posiciones son CONVENIO y no dato** (`comparative.CONVENTION_NOTE`, en el informe
  y en la cabecera del TSV): la posición 1 de la guía, donde se fuerza una T/U para que
  AGO2 cargue la hebra, y la posición 1 de la pasajera, el desapareamiento deliberado del
  bulge basal. Ninguna viene de la diana, así que ninguna entra en una comparación de
  identidad.
- **Las coordenadas van siempre por partida doble**: transcrito y 3'UTR. Los tercios se
  calculan sobre el 3'UTR. Cuando lo que se tila YA es un 3'UTR no hay offset y las dos
  parejas coinciden; los números están bien, pero `inicio_transcrito = 21` leído dentro
  de un año parece la posición 21 de un RefSeq. Por eso la cabecera del TSV comparativo
  y el bloque del informe llevan `comparative.coordinate_note`, que dice en qué marco va
  cada pareja, de dónde salió la anatomía, y —si no hay marco de transcrito— que esas
  columnas **no son coordenadas de ningún transcrito**. Los nombres de las columnas no
  cambian: el esquema es estable, lo que cambia es lo que se explica de él.
- **La anatomía se resuelve en `resolve.py`, y la usan los DOS frontales.** Vivía dentro
  de `tools/design.py`, así que la interfaz no podía llamarla y acabó teniendo su propia
  versión — con el `else: todo es 3'UTR` que el CLI había cerrado, escondido en un
  `value=1 … value=len(secuencia)` por defecto. El mismo mRNA daba una anatomía por
  consola y otra por navegador, y la del navegador corría los tercios. La interfaz tiene
  ahora las tres vías (subir el `.gb`, declarar el CDS, o marcar que lo subido ya es el
  3'UTR), tila la secuencia ENTERA con su anatomía como el CLI, y pasa por
  `check_boundaries`. No añadas un valor por defecto a esos controles.
- **La anatomía nunca se adivina.** Hay tres vías (`--genbank`, `--cds`, `--region
  3utr`) y la que se usó sale impresa en el informe (`RegionSource`). No existe ningún
  camino que convierta un "no sé" en un "todo es 3'UTR": `Anatomy.whole_is_utr3` exige
  declarar la procedencia por nombre. `orf.py` puede PROPONER un marco e imprimir el
  `--cds` para pegar, pero no importa el módulo de anatomía y un test lo comprueba
  sobre el propio fuente.
- **El codón de parada es aviso duro**: un CDS declarado que no termina en TAA/TAG/TGA
  aborta el diseño salvo `--permitir-cds-sin-codon-parada`. Es el chequeo que pilla el
  off-by-one y el lío 0-based/1-based, que corren el 3'UTR entero sin avisar.
- **Fuera del 3'UTR no se cuela nadie por accidente**: una ventana del ORF solo entra si
  se pidió su región con `--cuota-region`. Y allí polyA, APA y los tercios salen
  `NO_APLICA`, no `PASS`.
- **polyA es anotación, no veredicto**: cinco campos (`polyA_hexamero`, `polyA_clase`,
  `polyA_posicion_rel`, `polyA_solapa_seed`, `polyA_veredicto`). El corte ocurre 10-30 nt
  **aguas abajo** del hexámero, así que la ventana que desaparece es la que empieza tras
  el corte, no la que contiene la señal: la zona prohibida es asimétrica. `--polyA-modo`
  tiene tres criterios y el informe saca el top-N bajo los tres; el defecto sigue siendo
  `escalonado`, así que ninguna corrida anterior cambia de resultado.
- **La seed son dos preguntas**: colisión con un miARN endógeno (`mirna.py`, dos niveles
  — FAIL solo contra la lista curada de abundantes, aviso contra el resto) y carga de
  off-targets por seed (`seed_load.py`, un número comparativo, nunca un veredicto). No
  hay ninguna lista de miARN escrita en el código y un test lo comprueba.
- **El transgén es una segunda base de especificidad**: `filter_transgene` con el casete
  AAV. FAIL con 0 o 1 desapareamiento, porque una guía a un solo desapareamiento apaga
  la construcción terapéutica casi igual que a su diana — y eso sería un fallo
  silencioso.
- **La accesibilidad es DESEMPATE, nunca filtro**: es el criterio peor predicho del
  pipeline. Se calculan dos ventanas de contexto (±80 y ±150) y si discrepan el informe
  dice que el número no sirve para desempatar.
- **`riesgo_APA` es una PREDICCIÓN mientras no haya `--apa-medido`**, y el informe lo
  dice con esa palabra. Con sitios medidos el dato sustituye a la predicción y sale el
  techo de knockdown.
- **El cruce con una fuente externa va por SECUENCIA, nunca por coordenada.**
  miRarchitect numera sus ventanas con un convenio que no es el nuestro —para la misma
  guía da a veces una posición y a veces otra— así que cruzar por número pega un score
  en la fila del candidato de al lado. Y **la posición 1 de la guía no se compara**: los
  dos lados fuerzan ahí una T (la U que quiere AGO2), así que esa base es un convenio y
  no un dato; comparándola, la ventana 3'UTR 819 quedaba sin cruzar por un único
  desapareamiento sobre 19 nt de solapamiento idéntico. Una ventana corrida hasta 15 nt
  se asigna al candidato más cercano con la distancia escrita en `mirarch_shift_nt`; más
  allá, no se asigna.
- **Ningún intervalo se escribe a mano**: `audit.Span` se deriva de la secuencia que
  describe y `Span.check()` **aborta** si `fin - inicio + 1 != len(secuencia)`. No es
  teórico: la errata del desplazamiento de 3 nt y unas ventanas `269-291`/`222-242`
  emitidas para guías de 22 nt son el mismo fallo, coordenadas transcritas en vez de
  derivadas. `tests/test_intervalos.py` comprueba el invariante sobre las salidas de
  verdad, en las dos parejas de coordenadas. Ese invariante ya cazó algo real: cuando el
  emparejamiento sale de `guia[1:]`, la ventana mide un nt MENOS que la guía, porque la
  posición 1 es la T de convenio y no forma parte de la ventana.
- **La auditoría de un fichero de scores es código, no un análisis a mano**
  (`shmir_design/audit.py`, `tools/audit_scores.py`). Tabula longitudes, dice qué guías
  no mapean y cómo se restauran, marca las filas que son prefijo de otra, y avisa de
  sitios de restricción presentes en la guía y **ausentes del 3'UTR** — señal de que se
  ha colado contexto de clonaje donde debería haber guía. En la corrida murina: 25 filas
  (no 26), longitudes 21×4 / 22×20 / 23×1, 8 sin mapear, y un `TCTAGA` (XbaI) que no
  está en ninguna parte del 3'UTR.
- **La dirección de la escala se DERIVA del dato, no se supone.** `EVIDENCE` registra
  la dirección de cada fuente **con los pares (puesto, score) de los que salió**, y
  `file_order_direction()` la vuelve a derivar en cada importación del orden de las filas
  del fichero: si ese orden no es monótono en el score, no es un ranking y se aborta.
  Si la derivada no coincide con la registrada, también se aborta — uno de los dos está
  mal y no se elige por nuestra cuenta. `lower_is_better()` sigue abortando para una
  fuente no registrada. Ojo: el fichero de la corrida manual **no trae columna de rank**;
  el puesto sale del ORDEN DE SUS FILAS, que es lo único no circular que hay. Y el
  alcance de esa prueba es limitado: que 25 filas salgan ordenadas demuestra que el
  fichero **está** ordenado, no en qué dirección. Que la primera sea la mejor sigue
  siendo un supuesto sobre el convenio de la fuente, anotado como tal en `EVIDENCE` y
  pendiente de confirmar leyendo el puesto en su interfaz.
- **Un score de otro andamio no ordena.** `check_orderable()` compara el andamio del
  fichero con el del diseño y, si no coinciden, el score se degrada a **convergencia de
  sitio**: sigue diciendo que otro método señaló la misma región, pero no ordena nada.
  Va escrito en cada fila (`fuente_score` acaba en `_NO_ORDENAR`) y el resumen empieza
  por ahí. `--andamio` es obligatorio en `tools/import_scores.py`: suponer que coincide
  es justo lo que no se puede hacer, porque miR-E existe porque procesa distinto de
  miR-30a y el sesgo cae sobre lo que el score dice medir.
- **`score_externo` va vacía y no se rellena aquí.** Se comprobó si miRarchitect
  (`mirarchitect.cs.put.poznan.pl`), SplashRNA (`splashrna.mskcc.org`) y el GPP Web
  Portal (`portals.broadinstitute.org`) responden: las tres dan 403 en el CONNECT del
  proxy de este entorno, que es una denegación de política de red y **no una respuesta
  del servicio** — o sea, no se ha podido comprobar, que no es lo mismo que no existir.
  Las tres viven en `external_score.EXTERNAL_TOOLS` como **enlaces**, en la cabecera de
  la interfaz y en el informe; ningún código las llama.
  Por eso `external_score.MIRARCHITECT_API` y `SPLASHRNA_API` valen `None` y ninguna URL
  se usa como endpoint. Las features de SplashRNA (asimetría, GC, posición 1, posiciones
  2-7, composición de la seed, GC del bucle) **sí** se calculan y salen en columnas
  `feat_*` separadas y sin combinar: una feature no es un score, y aquí no se entrena
  ningún modelo ni se etiqueta de miRarchitect un número calculado por nosotros. El
  informe imprime cómo puntuar a mano y `tools/import_scores.py` mete el resultado en la
  tabla, con `fuente_score = manual_mirarchitect`. El score es informativo: nunca FAIL,
  nunca PASS. El test de plausibilidad de la guía de SGEP está escrito y se salta de
  forma visible mientras no haya endpoint. Ver `docs/endpoints-verificados.md`.
- **La tabla comparativa lleva una columna `knockdown_medido` vacía** para que vuelva
  rellena del laboratorio. No la rellenes ni la quites: es el instrumento con el que se
  sabrá qué parámetros predicen potencia y cuáles son decoración.
- El módulo NheI–SacI de 149 nt (`gblock.py`, `blocks.py`) lleva contextos nativos de
  SGEP que **no se recortan ni se sustituyen**: llevan el CNNC de SRSF3. El `GGGG` del
  contexto 3' es nativo, por eso la comprobación de homopolímeros mira solo la parte
  variable.
- **El generador de bloques (`blocks.py`) pliega dos veces, y la segunda no es opcional**:
  el 97-mero aislado, y el 97-mero **dentro del intrón de 296 nt**. Los espaciadores se
  optimizaron para la horquilla de 1018; con otra guía el contexto puede capturar los
  flancos del pri-miR y deshacer el tallo basal, y eso solo se ve plegando. Si falla el
  segundo, el módulo NheI–SacI **no es seguro** para ese candidato y el cassette con los
  mismos espaciadores tampoco, porque lleva el mismo intrón dentro. Reoptimizar los
  espaciadores es generar secuencia de novo, y **hay autorización escrita y acotada para
  ello**: `shmir_design/spacers.py`, activado con `--reoptimizar-espaciadores`. Cubre
  SOLO los espaciadores — nunca guías, pasajeras, contextos ni andamio. Longitudes fijas
  (20 y 45 nt), filtros duros iguales a los originales, y un único criterio de selección:
  que el 97-mero dentro del intrón pliegue idéntico a aislado; a igualdad, menor MFE.
  **Los estándar son el caso base y ganan si funcionan**, así que el generador no puede
  "mejorar" por su cuenta un diseño validado. Lo que genera se marca en toda la salida:
  un cassette con espaciadores de novo NO es intercambiable con el módulo NheI–SacI
  estándar.
- **XhoI y EcoRI viajan dentro del módulo**, heredadas de los contextos de SGEP, y en el
  plásmido final no son únicas. La hoja de pedido lo dice siempre: el clonaje va por
  NheI/SacI o por síntesis.
- **La especificidad no cubre los off-targets por seed** y el informe lo dice en cada
  ejecución. No lo quites ni lo suavices: es el hueco más grande que queda, y un
  veredicto de especificidad "limpio" sin esa frase invita a creer que la guía está
  comprobada cuando lo que se ha comprobado son los alineamientos, no las seeds.
- El BLAST remoto es **inspección, nunca veredicto**, y solo para los supervivientes.
- **El orden de operaciones del paso 15 no se cambia**: enmascarar y RETILAR, filtros
  duros, ordenar por asimetría, agrupar en sitios, selección voraz. Enmascarar después
  de tilar produce un ranking contaminado que parece correcto.
- El aviso `ANDAMIO_NO_VERIFICADO` **no se puede silenciar**: no hay parámetro para ello
  en ninguna función ni en ningún CLI, y no lo añadas. `verificado` es false por defecto
  en todo andamio cargado de fichero.
- Elegible no es aprobado: mientras haya filtros en `NOT_RUN`, la selección es
  provisional y los candidatos salen `INCOMPLETE`.
- Los umbrales ajustables viven en `hard_filters.Thresholds`, con los valores
  verificados como defecto. Añadir un umbral nuevo significa añadirlo ahí y pasarlo,
  nunca leerlo de la UI.
- Implementado: pasos 0 (fixtures + checksum), 1 (anatomía resuelta por tres vías),
  2 (enmascarado con rmsk real), 3 y 15 (tiling, sitios y selección), 4-8 (filtros de
  ventana, incluida la asimetría), 9 (polyA como anotación de cinco campos), 10 (seed en
  dos preguntas: colisión y carga), 12 (especificidad + transgén), 13 (accesibilidad) y
  14 (bloques conservados), más la horquilla, el módulo de 149 nt, el APA con dato
  medido y la tabla comparativa. El resto, en `docs/pipeline.md`.

## Ficheros que faltan (por eso hay filtros en NOT_RUN)

Ninguno se sustituye por una lista interna ni por nada reconstruido. Mientras falten, su
filtro queda en `NOT_RUN` y los candidatos salen `INCOMPLETE`:

| Fichero | Qué desbloquea | Flag |
|---|---|---|
| `data/reference/*.fa` | los dos 3'UTR de referencia (15 tests saltados) | — |
| RefSeq RNA versionado | especificidad | `--refseq` |
| `mature.fa` de miRBase | colisión de seed, nivel aviso | `--mirbase` |
| lista de MirGeneDB | colisión de seed, nivel FAIL | `--abundancia` |
| 3'UTR del transcriptoma | carga de off-targets por seed | `--transcriptoma-3utr` |
| máscara rmsk de ratón | elementos repetitivos | `--rmsk` |
| casete AAV completo | filtro del transgén | `--transgen` |
| PolyA_DB / PolyASite | APA medido en vez de predicho | `--apa-medido` |
| tabla de expresión | ponderar la carga de seed | `--expresion` |
