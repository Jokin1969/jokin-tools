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
- **El filtro de poliadenilación es escalonado. DECIDIDO (2026-08-26)**, con la tabla de
  los seis candidatos delante y no antes: FAIL duro solo para la señal terminal y para
  `AATAAA`/`ATTAAA` en `APA_POSIBLE`; las variantes raras dejan bandera y penalización de
  ranking. 1018 entra con penalización. El informe saca las dos cifras de elegibles, y la
  tabla emite `polyA_estricto` y `polyA_escalonado` en columnas separadas para que la
  decisión siga siendo auditable.
- **Truncamiento y estérico son DOS riesgos, no uno** (`polya.polya_risk`). La regla de
  ±flanco los mezclaba:
  - **truncamiento** — la ventana está POR DETRÁS del corte que dirige un hexámero
    funcional (10–30 nt aguas abajo). Es un riesgo sobre la **existencia** de la diana.
  - **estérico** — la ventana **solapa** el hexámero y compite con CPSF/CstF. Es un
    riesgo sobre la **accesibilidad**, y solo existe si ese hexámero se usa.

  Un mismo hexámero nunca produce los dos en la misma ventana: o estás encima de la
  señal, o estás por detrás de su corte. Hay cinco estados y no dos (`RiskState`):
  `PENALIZADO` es obligatorio porque la banda de corte tiene 20 nt de ancho y colapsarla
  a PASS o FAIL inventa una precisión que no hay, y `TECHO` porque el APA no veta.

  **Y `truncamiento_propio` va aparte de `truncamiento` a propósito.** Una ventana que
  solapa un hexámero no tiene truncamiento *por ése*, pero puede tenerlo por otro que
  quede más arriba: 1018 solapa `ACTAAA` (sin truncamiento propio, estérico penalizado)
  y a la vez está por detrás del corte del `AATAAA` de 288, igual que los otros cuatro.
  Emitir solo «truncamiento NO_APLICA» lo dejaría como una excepción a su favor.
- **El truncamiento por APA es un `TECHO`, no un `FAIL`. DECIDIDO (2026-08-26).** El APA
  produce una **mezcla de isoformas**, no un corte binario: un candidato por detrás de un
  sitio proximal usado en una fracción f conserva su diana en el (1 − f) de isoforma
  larga. Lo que corre es un techo de knockdown de (1 − f), y eso no es un veto. `FAIL`
  queda reservado a la señal **terminal**, donde no hay isoforma que conserve la diana.
  (Con el 3'UTR murino esa rama no la alcanza ninguna ventana de 22 nt: una terminal está
  a ≤ 40 nt del extremo y su corte más tardío cae +30, así que detrás no cabe nada. Hay
  un test que fija ese hecho geométrico.)
  - `PolyARisk.fraccion_isoforma_larga` es **obligatorio y sin valor por defecto**:
    ningún camino puede omitirlo y dejar el techo mudo. `None` significa **no medida**,
    igual que `divergent_positions=None`, y **no es 0** (todo isoforma corta, techo cero)
    **ni 1** (todo larga, sin techo). La columna `polyA_fraccion_isoforma_larga` va
    **vacía**, nunca a cero, y el informe imprime «techo indeterminado» — no un veredicto.
  - Es el **mismo número** que `apa.ApaAssessment.knockdown_ceiling`, así que cuando hay
    tabla de sitios medidos (`--apa-medido`) el techo viaja a la anotación de polyA y las
    dos columnas dicen lo mismo. Se adjunta **solo** donde hay truncamiento por APA: dar
    un techo a una ventana inmune sería emitir un número que no se refiere a nada, y
    `PolyARisk.__post_init__` aborta si se intenta.
  - El experimento que lo convierte en un número está **en el informe**
    (`polya.rtqpcr_amplicons`): RT-qPCR de dos amplicones sobre el 3'UTR murino, uno
    entero por delante del hexámero y otro entero por detrás de la banda de corte,
    cuantificados contra una **curva estándar común**; la razón distal/proximal *es*
    `fraccion_isoforma_larga`. Con la señal de 288 salen 3'UTR **158-277** y **684-803**
    (120 nt cada uno, holgura de 10 nt y esquivando las dianas del panel). Se emiten
    **coordenadas**: no se emiten cebadores — eso necesita Tm, especificidad y horquillas,
    y no se improvisa. Se mide sobre tejido **sin tratar**: en muestras tratadas un
    amplicón que solape una diana mide corte por RNAi, no isoformas.
  - **Primero lo publicado, luego el banco**, y el informe lo imprime en ese orden:
    PolyA_DB / PolyASite y datos públicos de **3'-end seq de cerebro murino** sobre Prnp.
    Si la fracción está publicada, el experimento es **confirmación**, no descubrimiento.
  - **RT con hexámeros aleatorios, nunca oligo-dT**, y el sesgo tiene dirección conocida:
    el oligo-dT ceba en la cola y la RT avanza 3'→5', así que una RT incompleta pierde lo
    que está lejos de la cola. En la isoforma larga el proximal queda a **965 nt** de la
    cola y el distal a **439**, así que la larga se subrepresenta más en el proximal y la
    razón sale sesgada **hacia más isoforma larga** — justo el resultado que se busca.
    RNA con **RIN documentado**: la degradación produce el mismo sesgo por la misma razón.
  - **Control positivo de ensayo, obligatorio y hoy `NOT_RUN`**: un gen con APA
    caracterizado en cerebro murino, en las **mismas muestras** y con la **misma
    arquitectura de amplicones**. Sin él, un «casi todo isoforma larga» no se distingue de
    un ensayo **ciego** a las isoformas cortas: los dos dan la misma cifra. Ese gen se
    elige **con su cita**; el informe no propone ninguno, porque nombrarlo de memoria
    sería inventar la referencia, y emite `control_positivo_ensayo: NOT_RUN` hasta que
    alguien lo aporte con referencia.

- **El `AATAAA` de 3'UTR 288 es el riesgo de truncamiento dominante del panel** y el
  informe lo declara así, con qué candidatos quedan con techo por detrás de su corte y
  cuáles son inmunes por ser proximales. Si ninguno lo es, lo dice: un panel entero por
  detrás del mismo corte comparte un único modo de fallo.
  - Está clasificada `APA_POSIBLE` **por ser canónica** y estar a más de 100 nt del
    extremo 3', **no por evidencia de uso**: aquí no hay ni un dato de uso de ese sitio.
    Es un **supuesto**, y el informe lo dice con esa palabra. Con PolyA_DB o PolyASite
    (`--apa-medido`) dejaría de serlo.
  - **No está conservada en humano — COMPROBADO (2026-08-26)**, ya no declarado. Llegó
    `NM_000311.5.fa` y `polya.signal_conservation` lo mide: el 3'UTR humano (1606 nt) no
    contiene `AATAAA` **ni una sola vez** en sus 1606 nt, así que la señal murina no tiene
    homólogo posible. No hace falta alinear para decirlo — y **no se alinea**: `alignment.py`
    es difflib sobre dos versiones casi idénticas de la MISMA secuencia, y entre especies
    daría un alineamiento sin sentido con pinta de resultado. Consecuencia: el techo es un
    problema del **modelo murino**, no del candidato.
    **Matiz que no se omite**: eso no significa que el 3'UTR humano esté libre de APA.
    Tiene dos `ATTAAA` en `3utr:955` y `3utr:1167` clasificadas `APA_POSIBLE`. El riesgo no
    está conservado **como ese hexámero**, que es otra cosa.
    Sin `--fasta-b` la pregunta sale **`NOT_RUN`**, nunca «no está conservada».
  - **Y el dato humano SUBE a la evaluación del riesgo murino**, pegado al `TECHO` de los
    distales y no en una sección aparte (`SignalConservation.prior_note`). No es solo
    ausencia de homólogo: el gen humano ha **prescindido del hexámero canónico por
    completo**. Un APA proximal funcional es un elemento regulador, y los elementos
    reguladores tienden a conservarse, así que eso **REBAJA la probabilidad a priori** de
    que la murina se use. **NO LA DESCARTA**: puede ser diferencia real de especie. Las
    dos cláusulas van juntas y ninguna sobra — el informe termina con «rebaja, no
    descarta».
  - **Inmunes: 60, 143 y 200**, no solo 60. 60 es el único que salía por asimetría, pero
    la piscina de elegibles tiene 15 sitios más por delante del corte y el informe saca los
    mejores — `3utr:143` (+5,08) y `3utr:200` (+3,80) entre ellos. Con un solo inmune el
    panel entero depende de un supuesto; con tres, no.
    **`3utr:221` era el tercero y ya no está**: el `AATATA` de `3utr:236` pasó a
    `APA_POSIBLE` por medida y la ventana `221-242` lo **solapa**, así que cae por riesgo
    ESTÉRICO. Su inmunidad al TRUNCAMIENTO no se ha tocado — empieza por delante del corte.
- **El 3'UTR humano trae sus DOS señales de APA desde el principio**, con la misma
  maquinaria: `ATTAAA` en `3utr:955` y `3utr:1167`, las dos `APA_POSIBLE`, `TECHO` y
  `fraccion_isoforma_larga = None`. Condicionan la mitad distal, y `apa_ceiling_table`
  emite cuánto panel condiciona cada una sobre las **311 ventanas elegibles**:
  - `3utr:955` (corte `3utr:970-990`): **100 de 311 = 32,2 %** con techo, 6 en la banda.
  - `3utr:1167` (corte `3utr:1182-1202`): **74 de 311 = 23,8 %**, 6 en la banda. Es
    subconjunto de la anterior: 74 candidatos llevarían **dos** techos.
  - El informe saca **todas** las señales `APA_POSIBLE`, no solo la dominante: con dos,
    enseñar una esconde justo la que condiciona la mitad distal. La banda de corte va
    aparte de lo que está detrás — `PENALIZADO` no es `TECHO`, y sumarlas sería inventar.
  - **El bloque conservado queda por detrás de las DOS.** Es el único de ≥22 nt entre los
    dos 3'UTR: 26 nt, `TTTTCTATATTTGTAACTTTGCATGT`, en ratón `3utr:1138-1163` y humano
    `3utr:1507-1532`. De las **5 ventanas de 22 nt que caben DENTRO, ninguna** supera los
    filtros de secuencia, y con los **mismos motivos en las dos especies** porque la diana
    es la misma: GC en las cinco, asimetría en cuatro, homopolímero en una.
    - **Se miran las CONTENIDAS, no las que SOLAPAN.** Una ventana que solapa el bloque se
      sale de él, y fuera del bloque las dos especies difieren: son ventanas distintas con
      dianas distintas. Contarlas dio un «sí hay ventanas elegibles» **falso** en el
      informe del ratón mientras el del humano decía lo contrario.
    - **CONSECUENCIA, y va escrita así en el informe: NO EXISTE un shmiR único válido para
      ratón, Tg650 y clínica por la vía del 3'UTR.** Eso cambia la **arquitectura del
      programa**, no dos plazas del panel (`conservation.single_shmir_verdict`).
- **La otra vía: el ORF conservado** (`orf_sweep.py`, en el informe cuando hay dos
  especies con CDS). Identidad exacta ≥22 nt entre los dos ORF: **4 bloques**, 16 ventanas
  que caben dentro, y **2 superan los filtros de secuencia** — ORF ratón 523/524
  (`tx:707`/`tx:708`), ORF humano 526/527, misma diana `GTGCACGACTGCGTCAATATCA`.
  - Aplican GC, homopolímeros, asimetría, G4, **seed, repetitivos y especificidad**. NO
    aplican polyA, APA ni tercios: son heurísticas del 3'UTR y salen `NO_APLICA`, nunca
    `PASS`.
  - Esas dos ventanas **no están aprobadas, están preseleccionadas**: seed, repetitivos y
    especificidad siguen en `NOT_RUN`.
  - **El obstáculo clásico de la vía ORF no existe en este backbone**: el ORF del casete
    AAV está **codón-optimizado**, así que ya es resistente a una guía contra el ORF nativo
    **sin recodificar nada**. No se da por supuesto — el filtro del transgén corre igual.
  - **Propiedad clave de alcance, y va escrita en el informe**: una guía contra esa ventana
    **alcanza PRNP humano** —y por tanto Tg650 y las líneas humanizadas— y **no alcanza el
    transgén** del casete. Es exactamente el reparto que hace falta.
  - **VERIFICADO traduciendo los ORF del repositorio** (`orf_sweep.translate`): la ventana
    empieza en el **codón 175** (ratón) / **176** (humano), en marco, y codifica
    **`VHDCVNIT`** — el mismo péptido en las dos especies. Su **posición 4 es una
    cisteína**: **C178** (ratón) / **C179** (humano).
    - **PrP tiene UN solo puente disulfuro** —C178-C213 en ratón, C179-C214 en humano—, y
      eso también se sostiene aquí **sin estructura**: en el ORF murino solo hay tres
      cisteínas (22, 178, 213) y la 22 está en el péptido señal, así que **no hay un
      segundo par posible**. En humano, 6/22/179/214.
    - La numeración «codón 143» de la primera anotación era **contaminación con el W144Y
      del plásmido**, y el «segundo puente disulfuro» no existe. Las dos quedan
      corregidas; el registro de por qué, aquí.
    - Lo único que sigue **DECLARADO por el responsable y sin comprobar aquí**: la hélice
      B (H2) va de ~173 a 194, así que la ventana cae en su **extremo N-terminal**.
  - **«Región conservada» NO exime de mirar variación.** La selección purificadora
    restringe los **no sinónimos**, no los **sinónimos** — y son los sinónimos los que
    rompen el apareamiento sin tocar la proteína. **gnomAD sobre esa ventana es
    obligatorio**, y hoy está en `NOT_RUN`.
- **Un candidato «nuevo» de una fuente externa puede ser un sitio ya cogido**
  (`spacing.compare_sites`). 223 y 221 son dos ventanas corridas 2 nt: bajo el espaciado
  de 50 nt son el mismo sitio del panel. Se **avisa**, no se descarta — puede interesar
  cambiar uno por otro, y para eso hay que ver que compiten.
- **La referencia del espaciado es LOS 90 SITIOS ELEGIBLES. DECIDIDO (2026-08-26)** y no
  se cambia: el top 10 del plan es un subconjunto, no el conjunto. `ReferenceSet` es
  obligatorio, lleva **etiqueta**, y `SiteComparison.describe()` nombra el conjunto y su
  tamaño. Con los mismos 24 sitios de miRarchitect:
  - contra **los 6 elegidos** → 9 filas sin choque, que agrupadas entre ellas son
    **7 plazas** (337, 394, 735, 765, 930, 1075, 1200). Es la cifra que di, y estaba
    medida contra seis posiciones sobre 1242 nt: casi todo parece nuevo.
  - contra **los 90 sitios elegibles** (la tabla completa) → **ninguna**, salvo 1200. Y
    1200 no es utilizable: falla nuestro propio filtro duro de polyA, que es justo por lo
    que no hay ninguna ventana elegible cerca.
  - **735 no está cerca de una ventana nuestra: ES nuestra ventana 735**, base a base
    (`GCCCTATGTTTCTGTACTTCTA`). 337 choca con 329 a 8 nt y 765 con 735 a 30 nt.
  Los supervivientes se agrupan **entre ellos** además de contra la referencia: dos
  externos a menos del espaciado son una plaza, no dos. Y «plaza nueva» no es «plaza
  utilizable»: son dos preguntas, y el espaciado solo contesta la primera.
- **`same_site` y el criterio de la selección son la MISMA regla**, negada
  (`selection.respects_spacing`). Estaban por separado y discrepaban en el borde: un par
  a exactamente 50 nt era «dos candidatos» para la selección y «el mismo sitio» para el
  análisis de espaciado. El espaciado es el mínimo **exigido**, así que 50 lo cumple. Hay
  un test que barre 0-120 nt y ata las dos definiciones.
- **HALLAZGO: el espacio de ventanas viables está SATURADO** (`spacing.convergence`, en el
  informe con `--convergencia`). Dos métodos independientes con criterios distintos sobre
  el mismo 3'UTR verificado — nuestra cascada de filtros duros y miRarchitect —, 24 sitios
  externos contra los 90 elegibles: **0 sitios exclusivos de la fuente externa** que
  superen nuestros filtros duros, **4 coincidencias exactas** (`3utr:221`, `735`, `810`,
  `1018`; la de 735 es la misma ventana base a base) y **6 a 1 nt** (`337↔338`,
  `516↔517`, `552↔553`, `1017↔1018`, `1024↔1025`, `1075↔1076`). El único externo sin
  choque es `3utr:1200`, y falla nuestro propio filtro de polyA.
  **Lectura, y va escrita con esas palabras: NO es una validación cruzada** — donde solo
  cabe coincidir, coincidir no demuestra nada. La convergencia externa **no discrimina
  entre candidatos y no puede usarse para elegir**: no ordena, no desempata y no aporta
  plazas. Es un dato de **calibración de nuestra propia cascada**, y va al
  **suplementario**.
- **Las 3 plazas del bloque «solo de fuente externa» se reasignan a COBERTURA.** El bloque
  desapareció por vacío. Dos cuotas duras nuevas (`SelectionConfig.min_per_tercio`,
  `apa_immune_quota` + `apa_immune_before`), y el informe escribe la justificación: las
  causas de fallo son **regionales, no puntuales** —un APA, un repetitivo, un tramo
  estructurado afectan a una región entera—, así que con la predicción **saturada** la
  única variable que sigue comprando **independencia entre apuestas** es el espaciado.
  - **Inmune tiene dos definiciones y solo una vale**: por delante del corte más
    **temprano** (hoy `3utr:251`, el del tercer sitio medido; era `3utr:303`) la ventana se
    conserva en las dos isoformas; por delante del más tardío admite ventanas **de dentro
    de la banda de 20 nt**, que `polya_risk` clasifica `PENALIZADO`, no `NO_APLICA`. Llamar
    inmune a una de la banda es inventarse una precisión que no hay. El corte **se deriva**
    del informe (`selection.derive_immune_cut`), no se teclea.
  - **Con el criterio estricto y 50 nt de espaciado caben CUATRO inmunes, no cinco.
    DECIDIDO (2026-08-26)**: `3utr:10`, `60`, `143` y `200` (era `221` hasta que la medida
    subió el `AATATA` de 236). Es un hecho geométrico del 3'UTR —los sitios elegibles por
    delante del corte se apelotonan—, no una limitación del código, y hay un test que lo
    fija. La cuota de cuatro se cumple igual: lo que cambia es quién la ocupa.
  - **El espaciado NO se baja para meter un quinto inmune.** El espaciado compra
    **independencia entre apuestas, no número de apuestas**: las causas de fallo son
    regionales y dos candidatos a 30 nt fallan juntos, así que un quinto inmune pegado a
    otro no compraría nada.
  - **La quinta plaza va al TERCIO MEDIO** (`SelectionConfig.tercio_quota`), que es donde
    el panel queda más flojo, y el informe escribe la razón: **si el APA resulta funcional
    se pierde un candidato; si no, se gana cobertura donde hace falta.** El panel de 10
    queda proximal 4 / medio 4 / distal 2 — la cuota pide 3 en el medio y la asimetría
    pone el cuarto.
- **El sesgo de baja complejidad está DESCARTADO** como explicación del score de
  miRarchitect: correlación carrera máxima / score `r = +0,154` sobre las 24, y
  homopolímeros de 4 o más repartidos 5/15 entre los mejores y 3/9 entre los peores — el
  mismo 33 %. Queda anotado porque era la hipótesis que había que descartar **antes** de
  acusar a su puntuación de nada, y descartarla es lo que permite usarla.
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
- **polyA es anotación, no veredicto**: los campos base son cinco (`polyA_hexamero`, `polyA_clase`,
  `polyA_posicion_rel`, `polyA_solapa_seed`, `polyA_veredicto`). El corte ocurre 10-30 nt
  **aguas abajo** del hexámero, así que la ventana que desaparece es la que empieza tras
  el corte, no la que contiene la señal: la zona prohibida es asimétrica. `--polyA-modo`
  tiene tres criterios y el informe saca el top-N bajo los tres; el defecto sigue siendo
  `escalonado`, así que ninguna corrida anterior cambia de resultado.
- **La seed son dos preguntas**: colisión con un miARN endógeno (`mirna.py`) y carga de
  off-targets por seed (`seed_load.py`, un número comparativo, nunca un veredicto).
- **La abundancia en cerebro son DOS CAPAS. DECIDIDO (2026-08-26)**:
  - **Núcleo, `FAIL` duro, EN CÓDIGO y sin cita** (`mirna.CORE_ABUNDANT`): miR-124-3p,
    miR-9-5p, familia let-7, miR-128-3p, miR-181a-5p, miR-125b-5p, familia miR-30,
    miR-26a-5p, miR-99a-5p, miR-138-5p. Motivo escrito en cada FAIL: compartir seed con
    uno de estos **no da off-targets dispersos, secuestra un programa regulador neuronal
    completo**. Corre **siempre**: no necesita fichero.
    **Esto REVIERTE la regla anterior** («no hay ninguna lista de miARN escrita en el
    código»), de forma acotada y con la autorización escrita en `CORE_AUTHORIZATION`, con
    fecha y motivo — consenso del campo. El test cambió de forma en consecuencia: ahora
    comprueba que la única lista es esa y que **sigue sin haber ninguna SECUENCIA** en el
    código (las seeds salen de `mature.fa`).
  - **Capa ampliada, `AVISO`, de fichero**: el resto de `mmu-` por encima de un umbral de
    un dataset publicado de small RNA-seq de cerebro murino. El fichero lleva en cabecera
    la **referencia** y el **umbral**; sin ellos la capa queda `NOT_RUN` y no avisa de
    nada — un aviso sin umbral parece un veredicto y no lo es.
  - **La familia miR-30 se señala APARTE**: el andamio es miR-E, derivado de miR-30a, así
    que una colisión ahí no es solo competencia por su red de dianas — la horquilla que se
    construye se parece a un miARN endógeno abundante del mismo tejido. Lectura distinta y
    peor.
  - **Guía y pasajera se resuelven por separado**, y el origen queda escrito en cada
    colisión. **U→T se normaliza en los dos lados antes de comparar** (`_seed_of` y
    `_seed_of_mature`): un desajuste de alfabeto daría cero colisiones y parecería una
    buena noticia. Hay un test que compara la misma tabla en ARN y en ADN y exige el mismo
    veredicto.
- **El `.out` de RepeatMasker declara la especie de la BIBLIOTECA, y se comprueba**
  (`masking.declared_species`, `expected_species` **obligatorio**). Fallo real del
  2026-08-26: un transcrito humano corrido contra la biblioteca murina dio un fichero con
  formato correcto, cifras plausibles y **Alu 0 %** —imposible en humano— y lo único que lo
  delataba era la línea «The query species was assumed to be mus musculus». **Un cero
  obtenido sin buscar no puede pasar como veredicto.** Si el fichero no declara especie,
  también aborta: no haber podido comprobar no es «coincide».
- **Un `.out` sin filas necesita el RESUMEN** (`.tbl`). Sin él, cero no distingue «no había
  repetitivos» de «la corrida no llegó a correr» — y esa diferencia es la de `PASS` contra
  `NOT_RUN`. Con resumen, una máscara vacía es un resultado legítimo; sin él, se aborta.
- **El manifiesto registra la BIBLIOTECA además de la versión del binario** (columna
  `biblioteca`): RepeatMasker 4.0.9 con Dfam_3.0 y con otra biblioteca dan resultados
  distintos, así que la versión a solas no identifica la corrida. La cabecera de 9 columnas
  se sigue aceptando (`PREVIOUS_COLUMNS`) y la columna sale vacía, que es la verdad.
- **El casete que se pasa tiene que ser lo que la célula MADURA** (`transgene.py`). Si el
  casete lleva el módulo del shmiR y se pasa el **genoma con el intrón dentro**, toda guía
  da impacto contra **su propia horquilla**: el filtro tumba el panel entero por un
  artefacto, con un motivo que además es literalmente cierto, así que no se ve. Se detecta
  **por secuencia** —el loop de los andamios conocidos— y se avisa en el informe. El
  casete de hoy (`aav_casete.fa`, pAAV_G130E_W144Y_mouse_PrP_4xmiR-183T, 5282 pb) es el
  **parental sin módulo**, comprobado, y el informe también lo dice: por eso su veredicto
  se puede leer tal cual.
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
- **Ninguna secuencia entra al pipeline sin su md5 en el manifiesto.** Ni pegada, ni
  transcrita, ni copiada de una conversación. Y una longitud que se anuncia se cuenta
  sobre la cadena **entregada**, no sobre la que se pretendía entregar
  (`reference.check_declared_length`). Es la errata nº 5 del registro: un 3'UTR
  anunciado como «1242 nt verificados» que traía 1246 dejó inservible una corrida entera
  de miRarchitect y varias tandas persiguiendo hipótesis falsas.
- **Un 3'UTR para una herramienta externa se escribe a FICHERO, nunca a stdout**
  (`tools/export_utr3.py`): el nombre lleva la longitud y el md5, y el programa **no
  imprime la secuencia**. Lo que se pierde al copiar de una pantalla son las carreras de
  homopolímero, y eso no se ve. Lo que se sube es el fichero.
- **Mapear exacto no demuestra estar intacta.** Una guía que sea prefijo o sufijo de otra
  fila del mismo fichero es la misma predicción mutilada, y puede mapear exacta si la
  pérdida cae en un homopolímero. Se comprueba y se avisa (`mirarchitect.Export.contained`,
  `audit`).
- **El andamio se decide por SECUENCIA, no por etiqueta** (`mirarchitect.Export.check_scaffold`):
  se compara el loop del fichero contra el del andamio. Y la pasajera de la fuente se
  **descarta con el motivo escrito** (`PASSENGER_REJECTED`): sigue la convención de
  miR-30a —dos nucleótidos borrados tras la posición 9 y `GC` terminal, verificado
  26/26— y la nuestra cambia solo la posición 1 y se elige plegando. De miRarchitect se
  toma la guía y nada más.
- **Una puntuación externa es transferible entre entradas si y solo si la ventana no
  solapa ninguna diferencia entre ellas, y eso se COMPRUEBA, no se supone**
  (`transfer.py`). Sale del caso de referencia: dos corridas de miRarchitect sobre Prnp,
  misma herramienta y mismo andamio, entradas que difieren en 18 sucesos sobre 1242 nt —
  los **21 sitios con ventana idéntica salieron con score idéntico**, luego el score es
  función local de la ventana de 22 nt. `divergent_positions=None` significa «nadie lo
  ha mirado» y **no** se transfiere; un `frozenset()` vacío sí es una comprobación hecha.
  **El puesto NO se transfiere**: 20 de esos 21 cambiaron de puesto con el score
  idéntico, porque el puesto depende del tamaño de la lista y no del sitio.
- **Toda posición impresa lleva su ESPACIO DE COORDENADAS pegado** (`coords.py`):
  `3utr:1018`, `tx:1967`. En cualquier salida —informe, avisos, motivos de filtro y
  celdas del TSV—, **no en la cabecera de la columna**: quien copia una celda a un correo,
  o lee una línea suelta, se lleva el número sin la cabecera. Es la contramedida del md5
  generalizada, y el fallo que la motiva **no dio ningún error**: la línea de inmunes
  elegibles imprimió un `1018` que era el 69 del 3'UTR, justo al lado de un candidato
  elegido que se llama 1018. Habría dado una conversación equivocada, no una excepción.
  - `Position` no se puede construir sin `Frame`, y `str()`/`format()` devuelven siempre
    la etiqueta: no hay forma de imprimir el entero desnudo por descuido.
  - El marco **sale de la anatomía** (`coords.frame_of`), no se elige: si el 3'UTR empieza
    en la posición 1 de lo tilado, lo tilado ES el 3'UTR. Y viaja con la selección
    (`ReportSelection.anatomy`) para que todos los escritores usen el mismo.
  - `coords.parse` lee de vuelta una celda etiquetada y **rechaza el entero desnudo**, así
    que la etiqueta no es decoración: los tests del invariante de intervalos pasan por ahí.
  - **El fallo REAPARECE cada vez que se escribe un bloque nuevo**, y ha vuelto dos veces
    más: `apa_ceiling_table` imprimía `3utr:1784` para una coordenada del transcrito humano
    —en el informe que ya se estaba entregando— y los tramos de techo salían como
    `3utr:1-1200` sobre un 3'UTR de 1242 nt. Los dos llevaban `Frame.UTR3` a pelo. La regla
    para un bloque nuevo es: el marco **se recibe**, sacado de la anatomía, y nunca se pone
    a `UTR3` porque «suele serlo».
- **Toda salida que nombre una referencia imprime longitud y md5 JUNTOS**
  (`reference.describe_sequence`): `referencia 1242 nt / 19f5fa2a`. Contramedida a un
  fallo que fue invisible porque «referencia 1246 nt» parece razonable; pegado al md5 no
  hay forma de leerlo sin ver que lo que se llama referencia es el bloque fabricado.
  Separarlas en dos campos no vale: el fallo consiste justo en que la longitud sola no
  identifica nada.
- **El polyA sale bajo las DOS reglas, en columnas separadas** (`polyA_estricto`,
  `polyA_escalonado`), con el hexámero, su posición, su distancia al extremo 3' y su
  clase. No se aplica ninguna al emitirlas: la decisión se toma con la tabla delante.
  `polyA_veredicto` sigue siendo el del modo con el que se corrió. Ojo con el marco:
  `polyA_hexamero_pos` va en coordenadas de LO TILADO, como `inicio_transcrito`, y la
  cabecera lo dice.
- **El informe ENTERO está fijado contra un golden versionado**
  (`tests/golden/raton_informe.txt`, `tools/regenerar_golden.py`,
  `tests/test_informe_golden.py`). Los tests de presencia comprueban que aparezca lo que
  cada uno espera; **no detectan lo que falta**. En esta sesión se borraron 127 líneas del
  informe —el bloque del `TECHO` y los inmunes enteros— al reordenar un bloque, y los 1700
  tests siguieron en verde. El golden compara la salida completa y ese borrado lo hace
  fallar: está comprobado a propósito. Se regenera **a mano** y el diff entra en la
  revisión.
- **Los tercios tienen DOS definiciones y hay que decir cuál** (`selection.tercio_counts`,
  bloque «Cobertura por tercios»). `Tercio` etiqueta por el **punto medio** de la ventana;
  la partición simple (`3utr:1-414 / 415-828 / 829-1242`) va por **inicio**. Discrepan en
  el borde: `3utr:819-840` empieza en el segundo tercio y su punto medio (829,5) cae en el
  tercero. Con el tercer sitio de APA medido dentro: elegibles por punto medio 88/128/54;
  por inicio 88/137/45; **sitios** por inicio 28/42/16. (Sin él eran 105/128/54,
  105/137/45 y 32/42/16.) Para pedir una plaza en un tramo concreto está
  `SelectionConfig.start_window_quota`, en coordenadas explícitas y por inicio, que no
  depende de ninguna definición de tercio.
  - Y la cuenta que dice si el panel **se puede rebalancear**: sitios elegibles por tramo
    que quedan **por delante del corte más temprano**, que con el tercer sitio medido es
    `3utr:251` y no `3utr:303`. Son **16, todos en el tercio proximal**; medio y distal
    tienen **cero**. Si el APA resulta funcional, el rebalanceo solo puede ir hacia el
    proximal — y solo hasta donde deje el espaciado (cuatro). El corte **se deriva**
    (`selection.derive_immune_cut`); antes iba tecleado y no se enteró de que se adelantara.
- **La asimetría sale con las DOS cifras cuando hay penalización**: cruda, penalización
  y neta (`+5,15 − 1,00 penal. = +4,15`). Una sola columna con la neta, al lado de
  candidatos sin penalizar, mezcla dos magnitudes distintas sin decirlo: el 221 salía
  `+4,15` frente a un `+5,15` de la tabla y parecía una discrepancia de cálculo cuando era
  la penalización por solapar el `AATATA` de 236 (variante rara, clase `OTRA`). Ese
  `AATATA` es hoy `APA_POSIBLE` por medida, así que `3utr:221` ya no llega a la tabla: la
  penalización se convirtió en FAIL. El caso sigue anotado porque el fallo que enseña —una
  columna que mezcla cruda y neta— es el mismo con cualquier candidato penalizado.
- **El PUESTO de una fuente externa no se usa en la selección.** Es propiedad de la
  LISTA, no del sitio: 20 de los 21 sitios compartidos entre las dos corridas de
  miRarchitect cambian de puesto con el score **idéntico**, solo porque una lista tiene
  26 filas y la otra 24. Se importa el score, y solo donde la ventana coincide.
- **El criterio posicional tiene TRES estados, no dos** (`transfer.WindowState`):
  `LIMPIA`, `TOCADA` e `INDETERMINADA`. El tercero es para un indel dentro de una carrera
  de bases iguales cuya carrera cruza el borde de la ventana: ahí el alineador coloca el
  indel en un punto cualquiera y la pregunta «¿cae dentro?» no tiene respuesta a priori.
  `LIMPIA` transfiere, `TOCADA` no, `INDETERMINADA` transfiere **solo** si existe la
  comprobación directa y las dos cadenas coinciden. Ojo con los dos vecindarios: una
  deleción borra una posición de la carrera, pero una inserción se mete en una JUNTURA, y
  la juntura de detrás de la carrera cae fuera de una ventana que acaba en ella. Tratar
  los dos igual marcaba TOCADA la ventana 221, que las dos corridas vieron idéntica.
- **Dos criterios de «misma ventana», y manda el directo.** El posicional —¿el intervalo
  de referencia contiene alguna posición divergente?— es conservador: cuando el indel cae
  dentro de una carrera de bases iguales, su posición exacta es ambigua y el alineamiento
  la coloca en un punto cualquiera, así que sobre-marca. El directo —¿las dos corridas
  emitieron la misma diana?— es exacto, pero solo se puede aplicar a sitios que las dos
  reportan. El informe da los dos y dice dónde discrepan y por qué.
- **El perfil de diferencias dice de QUÉ investigación se trata** (`alignment.py`). Un
  trasvase —copiar de una pantalla— solo puede PERDER caracteres: si el perfil trae
  inserciones, sustituciones o transposiciones, la secuencia no se copió mal, se generó.
  Son dos culpables y dos remedios. Las transposiciones se cuentan aparte de las
  sustituciones: `CT`→`TC` son dos bases pero UN suceso.
- **La comparación de dos corridas va ESTRATIFICADA, sin cifra agregada.** Un porcentaje
  global de solapamiento mezcla ventanas que las dos corridas vieron idénticas con
  ventanas que vieron distintas, y con eso no se decide nada. Los estratos son: (a)
  ventana sin ninguna diferencia dentro de sus 22 nt, (b) ventana que solapa al menos
  una. Para el estrato (a) la expectativa es **score idéntico**, y eso es un test
  binario, no un umbral. Si falla, el score no es función local de la ventana: arrastra
  contexto global, y entonces **ninguna** puntuación calculada sobre una entrada
  imperfecta sirve — tampoco las de ventanas intactas. El informe lo dice con esas
  palabras y no dice «robusto».
- **Dos corridas de miRarchitect se cruzan por SITIO sobre la referencia**
  (`mirarchitect.compare_exports`, `tools/compare_exports.py`), nunca por guía ni por la
  coordenada que declara el fichero: una ventana corrida da otra guía, y una entrada
  distinta corre las coordenadas. `axis` es **obligatorio** porque la misma aritmética
  contesta dos preguntas distintas — cuánto mueve la puntuación un cambio de la entrada
  (sensibilidad) y cuánto la mueve un cambio de andamio (la magnitud que convierte el
  `NO_ORDENAR` en un número). El programa da la cifra y **no** dice si es alta o baja:
  ese umbral lo pone quien lee, y el informe dice qué decisión cuelga de él. El bloque
  entra en el documento con `design.py --nota`, no se queda en el log.
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
- **La fracción de isoforma larga está MEDIDA y YA ENTRA** (`apa.POLYA_DB_PRNP`).
  PolyA_DB v4.1 (2025-09-15), mm10, Prnp (Gene ID 19122): 15 PAS, 5 con expresión. Las dos
  cifras con su fórmula, porque no miden lo mismo:
  - **ponderada** `Σ(AvgRPM × PSE) distal / Σ total` = **0,86** ← valor de trabajo
  - sin ponderar `Σ(AvgRPM) distal / Σ total` = **0,65**
  La ponderada manda porque `AvgRPM` está condicionado a muestras **con** expresión.
  - **El dato es de TODOS los tejidos, no de cerebro.** Las neuronas alargan los 3'UTR, así
    que 0,86 es un **límite inferior conservador** para el nuestro — y por eso la RT-qPCR de
    los dos amplicones deja de ser solo confirmación: **puede mejorar el número**.
  - **`pending` y `caveats` son cosas distintas y no se mezclan.** `pending` para lo que
    **bloquea** el uso del dato (hoy vacío); `caveats` para lo que se anota y no mueve el
    valor. Meter una reserva en `pending` haría parecer inutilizable un dato por algo que no
    cambia ninguna cifra, y eso engaña tanto como omitirla.
  - Reserva que se mantiene: el PAS terminal `131938427` y el que tiene expresión
    (`131938392`, 35 nt aguas arriba) **se anotan como dos y no se fusionan** sin
    comprobarlo. **No mueve el valor**: `131938427` no tiene expresión, así que no suma en
    ninguna de las dos fórmulas. El anclaje además los coloca sobre hexámeros **distintos**.
- **El mapeo genómico↔transcrito está RESUELTO, y sin coordenadas genómicas**
  (`apa.anchor_polyadb`, `polya.PAS_IS_CLEAVAGE_SITE`). El `.gb` de NM_011170.3 sigue sin
  traerlas —su bloque `PRIMARY` referencia cDNA y EST, no un cromosoma— y ya no hacen falta.
  - **El desempate lo da la propia leyenda de PolyA_DB**: «A[A/U]UAAA motif within 40-nt
    upstream from the PAS». Si el hexámero se **busca aguas arriba** del PAS, el PAS no puede
    ser el hexámero: **es el sitio de corte**. La otra lectura queda descartada.
  - **Y no se elige por una resta**, que es un solo punto de apoyo y siempre cuadra. Se
    exige que las **cuatro** coordenadas publicadas aterricen a la vez, con el **mismo
    desfase**, sobre un hexámero de la **clase que la propia base declara** para cada una
    (`AAUAAA` / `AUUAAA` / `Other`). Bajo «PAS = corte» aterrizan las cuatro; bajo «PAS =
    hexámero» —donde el aterrizaje tiene que ser **exacto**, porque un hexámero es un punto
    y no una banda— no hay ningún desfase que haga aterrizar **más de una**.
  - Resultado: `131937444` → corte `3utr:251-271`, hexámero **`AATATA` en `3utr:236`**;
    `131937504` → corte `3utr:303-323`, hexámero `AATAAA` en `3utr:288`; `131938427` →
    corte `3utr:1229-1249`, hexámero `ATTAAA` en `3utr:1214`. Desfase 3'UTR→mm10 acotado a
    **131937185-131937193**, y se deja como **intervalo**: la banda de corte mide 20 nt y
    fijarlo en un entero sería inventarse precisión.
  - **`131938392` sale AMBIGUO** —dos `TATAAA` de su clase caben en su banda, `3utr:1178` y
    `3utr:1189`— y eso **no invalida el anclaje**, pero ese sitio **no entra al modelo con
    banda propia**: no identifica un hexámero y no se elige por nuestra cuenta.
  - **La tabla se aplica por md5 del 3'UTR** (`MeasuredFraction.utr3_md5`,
    `apa.resolve_measured`), no por el nombre del gen. Sobre cualquier otra secuencia
    devuelve `None` y no se promueve nada: unas coordenadas de Prnp murino ancladas sobre
    otro 3'UTR anclarían ruido, y el ruido ancla si se le deja sitio.
- **`131937444` es un TERCER sitio de corte y entra como `APA_POSIBLE` POR MEDIDA, no por
  canonicidad. DECIDIDO (2026-08-26)** (`polya.promote_by_measurement`). Es el caso
  **inverso** al del `AATAAA` de 288: allí hay canonicidad y ni un dato de uso; aquí hay uso
  medido —**el proximal más usado de los tres**, PSE 21,1 % y AvgRPM 0,55 frente a 23,5 % /
  0,34— y el hexámero es una **variante rara** (`AATATA`) que por la cascada de predicción
  saldría `OTRA`. La medida **sustituye** a la predicción, que es lo que dice `apa.py` desde
  su primera línea. `PolyASignal.evidence` dice por cuál de las dos vías entró cada señal y
  el informe lo imprime; las dos vías no se confunden nunca en la salida.
  - Su corte es **más temprano** (`3utr:251-271` frente a `3utr:303-323`), así que la
    frontera de la inmunidad se **adelanta de `3utr:303` a `3utr:251`**.
  - **`3utr:221` conserva su inmunidad al TRUNCAMIENTO** —empieza en 221, por delante de
    251— **y pierde la plaza por el otro riesgo, el ESTÉRICO**: `3utr:221-242` **contiene**
    el hexámero y compite con CPSF/CstF por un sitio del que ahora se sabe que se usa. Son
    dos ejes y el informe no los mezcla. Su plaza proximal la ocupa **`3utr:200`** (+3,80
    frente al +4,15 neto de 221): la cuota de cuatro inmunes se cumple igual.
  - **Lo que cuesta la promoción va NOMBRADO** (`selection.measured_promotion_cost`): 17
    ventanas que superaban todos los demás filtros pasan a FAIL, elegibles 287 → 270,
    sitios 90 → 86, sitios inmunes 20 → 16 (todos siguen en el proximal). Sin esa cuenta la
    única huella de la decisión sería una piscina más pequeña, que es exactamente la forma
    que tiene un candidato de desaparecer sin que nadie lo vea. **Solo se cobran las
    ventanas que caen POR ESTO**: una que ya fallaba GC no la tumba la promoción, y a la
    canónica de 288 no se le cobra nada porque ya era `APA_POSIBLE` por predicción.
- **El TECHO ya no es UNO: va POR TRAMOS** (`apa.CeilingLayer`, `MeasuredApa.layer_for`).
  Un solo número contesta «cuánta isoforma larga hay»; la pregunta de un candidato es otra,
  «qué fracción de transcritos conserva MI diana», y eso depende de por detrás de **cuántos**
  cortes está. Con los tres sitios medidos:

  | tramo (3'UTR) | techo | por qué |
  |---|---|---|
  | `1-251` | — | por delante de todos los cortes: inmune |
  | `252-271` | INDETERMINADO | dentro de la banda de `131937444` (PENALIZADO, no TECHO) |
  | `272-303` | **0,91** | por detrás de `131937444` |
  | `304-323` | INDETERMINADO | dentro de la banda de `131937504` |
  | `324-1242` | **0,86** | por detrás de los dos proximales |

  Colapsarlo a 0,86 para todos castigaría al tramo intermedio con un techo que no es el
  suyo; dejarlo en 1,00 por delante del corte de 288 —que es lo que había— se saltaba un
  sitio de corte entero. Los seis candidatos con techo del panel están todos en el último
  tramo: **0,86**.
- **El APA fue el cuarto FRENTE BLOQUEANTE y hoy está CERRADO. DECIDIDO (2026-08-26)**
  (`selection.blocking_fronts`, `BlockingFront.blocking`). La cuenta que lo abrió sigue
  siendo cierta —sitios inmunes por tramo 16/0/0, tope de cuatro por espaciado, seis de diez
  candidatos con el mismo modo de fallo—, pero **la razón por la que bloqueaba era que un
  techo alto y un shmiR malo dan la misma lectura en la placa**, y con el techo cuantificado
  en **0,86** eso deja de cumplirse: 0,86 no es indistinguible de una guía que no funciona.
  - **Un frente cerrado NO desaparece del informe**: sale como `FRENTE CERRADO` con el
    motivo. Borrarlo dejaría el informe sin memoria de por qué se cerró, y el siguiente
    lector no sabría si se resolvió o si nadie lo miró.
  - **La reserva del tejido se mantiene** y va escrita: el dato es de todos los tejidos, así
    que 0,86 es un límite inferior. La RT-qPCR de los dos amplicones sigue en pie y puede
    **mejorar** el número.
  - Sin tabla aplicable (p. ej. el 3'UTR humano) el frente **sigue bloqueando**, y el motivo
    dice que la tabla no entra en esa corrida **por md5**, no que no exista.
- **`--inmunes-antes` se DERIVA, no se teclea** (`selection.derive_immune_cut`). Estaba
  puesto a mano (`--inmunes-antes 1252`, o sea `3utr:303`) y cuando el tercer sitio medido
  adelantó la frontera a `3utr:251` la cifra tecleada siguió ahí **sin dar ningún error**.
  Ahora `apa_immune_before=None` con cuota significa «sácalo del informe»; lo que sigue
  abortando es llegar a `choose()` sin resolverlo, que es la garantía que importa.
- **Los tercios se cuentan sobre el 3'UTR, no sobre lo tilado.** Con un mRNA completo
  `report.utr_length` es la longitud tilada (2191) y los límites salían del transcrito: el
  reparto decía «medio 20» de unos sitios que están todos en el tercio **proximal** del
  3'UTR, y la frase del informe decía «proximal» al lado. Las posiciones se convierten
  antes de contar, y el tramo de la frase se **deriva** en vez de escribirse.
- **El EMPALME DEL INTRÓN es el quinto frente, y el ÚNICO BINARIO. AÑADIDO
  (2026-08-26)** (`splicing.py`). Los otros cuatro son graduales: una especificidad
  regular da off-targets, un techo de APA baja el knockdown, una colisión de seed
  secuestra una red. Se miden, se ordenan y se comparan. Este no: **si el intrón no se
  escinde, la horquilla se queda en el 5'UTR del mRNA maduro y no hay proteína DN en
  absoluto**. No hay «un poco de proteína» que optimizar, así que va como **frente y no
  como columna**, y lo que decide no es un candidato — decide si la **arquitectura
  intrónica** sigue viva.
  - **Por qué no estaba en la lista, y es la parte importante**: la lectura que se hace
    por defecto **no lo coge**. Un `small RNA-seq` puede salir **perfecto** con el
    empalme fallando, porque Drosha procesa el pri-miR **cotranscripcionalmente**, o sea
    **antes** del splicing: la horquilla se corta igual esté el intrón escindido o no.
    **Un shmiR correcto no es evidencia de que haya proteína.** Son dos sucesos en orden
    y esa lectura solo mide el primero.
  - **No se cierra con ningún fichero**, y el informe lo separa de los otros: sus tres
    lecturas son de banco, las tres `NOT_RUN`, y este software no corre ninguna.
    1. **RT-PCR de empalme** con cebadores en los exones que flanquean el intrón MVM.
       Banda **corta** = empalmado, banda **larga** = retenido, y la **proporción** es la
       eficiencia.
    2. **Western L42 normalizado por vg-qPCR.** Sin normalizar, «no hay proteína» no se
       distingue de «no llegó el vector»: los dos dan una membrana vacía y solo uno culpa
       al empalme.
    3. **Parental SIN INTRÓN en la misma tanda**, como techo de expresión. Sin techo, un
       western flojo no dice si el empalme va mal o si la construcción expresa poco.
  - **El casete que hay NO es el parental sin intrón, y confundirlos daría un techo que
    no lo es.** `aav_casete.fa` es el parental sin **módulo** pero **con el intrón vacío
    de 82 nt** (MVM5 40 + MVM3 42 pegadas, comprobado por secuencia), así que arrastra el
    mismo problema de empalme que se quiere medir. Hace falta la construcción **sin
    donante ni aceptor**. Y el intrón del terapéutico son **296 nt**, no 82: no son el
    mismo intrón y la eficiencia de uno no dice nada del otro.
  - **Las coordenadas se DERIVAN del casete, no se teclean** (`splicing.locate_intron`).
    Se buscan las piezas `MVM5`/`MVM3` de `blocks.PIECES` —una sola copia de cada una— y
    los dinucleótidos `GT`/`AG` se **leen** de la secuencia y se comprueban; si no cuadran,
    se aborta. Sobre `aav_casete.fa`: donante `casete:3134`, aceptor `casete:3215`.
    - Ventanas donde **buscar** los cebadores: `casete:3064-3123` (aguas arriba) y
      `casete:3226-3285` (aguas abajo), 60 nt cada una, a 10 nt de la unión, y se
      comprueba que sean **únicas** en el plásmido — un cebador que aparece dos veces no
      mide nada.
    - **No se emiten cebadores**, igual que en `polya.rtqpcr_amplicons`: Tm, especificidad
      y horquillas no se improvisan. Se emite dónde buscarlos.
    - **Ningún cebador puede cruzar la unión exón-exón**: uno que la cruce solo amplifica
      la forma empalmada, así que da presencia y **no proporción** — y la proporción es
      justo lo que se busca.
    - **La banda no se da como un número falso.** El extremo bajo del rango es solo los
      dos márgenes (20 pb); la banda real es `20 + F + R` con F y R las longitudes de los
      cebadores, que aquí no se fijan. Darlo tal cual emitía «banda corta ~22 pb», que es
      geométricamente imposible. **La cifra que no depende de nada de eso es la
      DIFERENCIA**: 296 pb en el terapéutico, 82 en el parental. Esa es la lectura.
    - **La especificidad del par la da el cebador de aguas ARRIBA.** La ventana de aguas
      abajo entra en el ORF de PrP, así que un par con los dos cebadores ahí amplificaría
      también el **Prnp endógeno** del tejido y la banda no sería del vector.
  - **Que el intrón cae en el 5'UTR se COMPRUEBA, no se declara**: el ATG se busca por
    detrás del aceptor y se traduce. Está en `casete:3253`, a **37 nt** del aceptor, y el
    ORF da **254 aa** que empiezan por `MANLGYWLLALFVTMW` con **G130E** y **W144Y** — o
    sea, es PrP y es el que anuncia el nombre del plásmido, **comprobado por traducción y
    no por el nombre del fichero**. Retenido, el intrón mete 296 nt por delante del codón
    de inicio, con al menos **5 uATG** en sus piezas fijas.
- **El informe cuenta los FRENTES abiertos, no «el bloqueante».** Con el casete y
  `mature.fa` cargados quedan **cuatro**: especificidad, repetitivos, colisión de seed a
  nivel FAIL y el **empalme del intrón**. Y lo dice con esas palabras: **no se pide oligo
  hasta que los cuatro tengan veredicto**. Que uno se arregle con un fichero de kilobytes
  y otro necesite una base entera no cambia nada — los dos bloquean igual, y llamar
  «único bloqueante» al pequeño es lo que hace que se pida oligo con dos filtros sin
  correr. Y hay una tercera categoría desde el empalme: **un frente que no se cierra con
  ningún fichero**, solo en el banco. El informe lo dice aparte para que no parezca que
  basta con conseguir datos.
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
| RefSeq RNA versionado | especificidad | `--refseq` |
| lista ampliada de abundancia (con referencia y umbral) | colisión de seed, nivel AVISO | `--abundancia` |
| 3'UTR del transcriptoma | carga de off-targets por seed | `--transcriptoma-3utr` |
| máscara rmsk de ratón | elementos repetitivos | `--rmsk` |
| 3'-end seq de cerebro murino | fracción de isoforma larga en NUESTRO tejido (hoy hay la de todos los tejidos: 0,86, límite inferior) | `--apa-medido` |
| parental SIN INTRÓN (donante y aceptor fuera) | techo de expresión para el empalme; `aav_casete.fa` NO vale, lleva el intrón vacío de 82 nt | — |
| tabla de expresión | ponderar la carga de seed | `--expresion` |
