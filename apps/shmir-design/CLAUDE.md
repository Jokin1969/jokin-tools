# shmir-design — reglas del proyecto

> **Ámbito.** Este fichero es vinculante para todo lo que hay bajo `apps/shmir-design/`.
> El resto del hub (`server.js`, `apps/re-memory/`, `src/`) es Node/Express y NO se rige
> por estas reglas. shmir-design es un proyecto Python independiente que vive dentro del
> mismo repositorio.
>
> Si una petición choca con una de estas reglas, la regla gana. No se negocian, no se
> relajan "solo para esta vez" y no se saltan porque el resultado parezca razonable.

---

## ⚠ SI VAS AL BANCO: los amplicones de la RT-qPCR son ÉSTOS

Va arriba del todo porque es lo único de este fichero que puede llegar tarde: un
cuaderno con las coordenadas viejas ya está escrito.

| | 3'UTR | transcrito |
|---|---|---|
| **proximal** | **`3utr:106-225`** | `tx:1055-1174` |
| **distal** | **`3utr:282-401`** | `tx:1231-1350` |

120 nt cada uno, holgura de 10 nt. Emitidos por `polya.rtqpcr_amplicons` sobre el corte
más temprano, que es el del `AATATA` de `3utr:236`.

### ~~Los viejos: `3utr:158-277` y `3utr:684-803`~~ — NO VALEN

Se diseñaron contra `3utr:288`, cuyo corte cae en `3utr:303-323`. Eso era el corte más
temprano **antes** de que la promoción por medida subiera el `AATATA` de `3utr:236` a
`APA_POSIBLE`. Con ese sitio dentro, el corte más temprano pasa a `3utr:251-271` — y ese
tramo cae **entero dentro del amplicón proximal viejo**.

No queda a caballo: queda **partido en dos por el propio suceso que se quería medir**. Un
amplicón partido por un corte no da producto en la isoforma cortada, así que el proximal
dejaría de medir «el total» y **la razón distal/proximal no mediría nada**. El distal
viejo sí estaba bien colocado; el que invalida el par es el proximal.

### Lo que este par SÍ mide y lo que NO

El amplicón distal nuevo (`3utr:282-401`) queda entero detrás de `251-271` **y atraviesa
`303-323`**, la banda del `AATAAA` de 288. Así que la razón **no** mide la fracción que
sobrevive al corte de 236: mide **la que sobrevive a los dos**.

**Para el panel eso es justo lo que hace falta** —sus seis candidatos con techo están
detrás de las dos bandas, o sea el tramo de 0,86—. Lo que **no** se puede confirmar con
este par es el **0,91 del tramo intermedio**.

**Y no se arregla moviéndolo**: entre las dos bandas, con la misma holgura, quedan
`3utr:282-292` — **11 nt** para un amplicón de 120. Es geométricamente imposible aislar
el evento de 236 con esta arquitectura. El informe lo emite pegado al plan
(`AmpliconPlan.distal_crosses`, `gap_between`), no en una nota.

**EL ENSAYO NO SE REDISEÑA: se queda con ALCANCE DECLARADO. DECIDIDO (2026-08-27).**
Mide lo que el panel necesita —el **0,86** que hay detrás de las dos bandas—, y el plan
lo dice con **dos frases y no con una limitación al pie** (`_lineas_de_cruce`):

> **QUÉ MIDE** — la fracción de transcritos que sobrevive a las dos bandas de corte, o
> sea el techo de los candidatos que quedan por detrás de todas ellas.
> **QUÉ NO MIDE** — no separa una señal de la otra y no confirma el techo del tramo
> **intermedio**.

Van las dos o ninguna: sólo la segunda deja el ensayo pareciendo defectuoso, y sólo la
primera lo deja pareciendo completo.

**Y la salida, por si algún día hace falta** (`polya.WAY_OUT_IF_EVER_NEEDED`): el tramo
intermedio **no se alcanza moviendo amplicones** —eso ya está demostrado imposible— sino
con **3'RACE o secuenciación de extremos**, donde la resolución no depende de que quepa
un amplicón entre dos cortes. Es **línea abierta, no tarea**: hoy no hay ningún candidato
ahí, así que no confirmarlo no cuesta nada.

### Y una frase que era falsa, también de los viejos

Aquí ponía «esquivando las dianas del panel». **Ni los nuevos ni los viejos lo
consiguen**: el proximal solapa `3utr:143-164` y `3utr:200-221` (los viejos solapaban
`143-164` y `221-242`). El código sí lo decía —lo marca con `⚠ solapa`— y era la prosa de
este fichero la que no. Por eso se mide sobre **tejido sin tratar**: en muestras tratadas
un amplicón que solape una diana mide corte por RNAi, no isoformas.

Va al registro como **errata propia nº 26**, y deja **principio nº 11**: *cuando el
código y la prosa discrepan sobre el mismo hecho, la que se ha quedado atrás es la
prosa, y es la que alguien va a leer.* No basta con corregir la frase — el mecanismo
sigue ahí. La regla operativa es que **la frase la emita el generador**, o que **un test
la contraste** contra lo que el código emite: `tests/test_prosa_contra_codigo.py`
comprueba que este fichero no vuelve a **afirmar** esa frase (puede citarla entre «» como
lo que fue), que los amplicones que declara son los que emite `rtqpcr_amplicons`, y que
el panel declarado es el de una corrida real.

### Por qué esto está en el registro y no sólo en un commit

**Es el primer caso en el que el trabajo computacional corrige un experimento de banco
ANTES de hacerlo.** Hasta ahora el pipeline emitía veredictos sobre candidatos; aquí un
cambio de regla —la promoción por medida deja de depender de una bandera— ha invalidado
un diseño experimental que ya estaba escrito y ha emitido el que lo sustituye. El coste
evitado no es una plaza del panel: es una tanda de RT-qPCR cuya razón no habría
significado nada, y que habría parecido un resultado.

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
npm run check:shmir   # regla 2 sobre el AST + informe de ALCANZABILIDAD
npm run check:tildes  # el castellano de los mensajes que ve el usuario
npm run test:shmir    # o: cd apps/shmir-design && python3 -m unittest discover -s tests -t .
```

`check:shmir` imprime además el informe de alcanzabilidad —qué función pública no tiene
ningún llamador— y **aborta solo** si hay una excepción declarada que ya no hace falta.
`check:tildes --arreglar` corrige, y el diff se revisa: el vocabulario es cerrado, pero
el contexto no lo mira nadie.

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
    `fraccion_isoforma_larga`. **Las coordenadas están arriba del todo**, en «SI VAS AL
    BANCO», con las viejas tachadas y el motivo: se diseña contra el corte MÁS TEMPRANO,
    que con la medida aplicada siempre pasó a ser el `AATATA` de `3utr:236`. Se emiten
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
  - **PANEL CONFIRMADO (2026-08-27)**: con la promoción por medida aplicada siempre, la
    corrida real por defecto da `3utr:` **10, 60, 143, 200, 449, 553, 652, 735, 819,
    1018** — los diez, con los **cuatro inmunes**. Coincide con el panel del responsable,
    así que la app reproduce lo que se sabía antes de construirla y la validación queda
    **cerrada**. Fijado en `tests/test_promocion_por_defecto.py`.
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
- **La especie de la biblioteca vive en el `.tbl`, NO en el `.out`. COMPROBADO
  (2026-08-26)** (`masking.declared_species`, `expected_species` **obligatorio**).
  Llegaron las tres corridas reales —RepeatMasker open-4.0.9 · rmblastn 2.17.1+ ·
  Dfam_3.0— y **ninguno de los tres `.out` declara la especie**. Se busca primero en el
  resumen; sin resumen no hay nada que comprobar, y no haber podido comprobar no es
  «coincide».
  - **LA DEMOSTRACIÓN, y va al registro con sus md5 como evidencia**
    (`masking.INDISTINGUISHABLE_OUTS`):

    | fichero | md5 |
    |---|---|
    | `rmsk_human.out` | `bcc33dbc7a65e74690f5f9d1fb270035` |
    | `rmsk_human_WRONG_SPECIES_mouse_lib.out` | `bcc33dbc7a65e74690f5f9d1fb270035` |

    **Son el mismo fichero byte a byte.** Una corrida válida y una contra la biblioteca
    equivocada producen `.out` **indistinguibles**, porque lo único presente es un
    microsatélite `(TA)n` y las repeticiones simples se detectan por **composición**, no
    por biblioteca. La diferencia vive **sólo** en el `.tbl`: uno dice «homo sapiens» y
    lista ALUs/MIRs, el otro dice «mus musculus» y lista Alu/B1 y B2-B4 **sobre una
    consulta de 2435 bp que es humana**. Exigir el resumen no es una precaución: es un
    **requisito**, y esto lo demuestra con datos en vez de argumentarlo.
  - **Los dos ficheros de la corrida mala se quedan** como fixture negativo, igual que
    el 3'UTR fabricado, con un test que comprueba que el parser los rechaza. No se
    borran: son evidencia.
- **Una máscara no se puede aplicar a otra secuencia** (`RepeatMask.query_length`, de la
  línea `total length:` del resumen). Es la misma trampa un nivel más arriba:
  `--usar-manifiesto` carga `rmsk_mouse.out` **por su rol**, sin mirar qué especie se
  está diseñando, y el intervalo murino `tx:892-936` **cabe de sobra** en los 2435 nt del
  humano — no se sale de rango, así que no salta ninguna otra alarma y taparía un tramo
  que ahí no es repetitivo. Se compara lo que el resumen declara haber analizado con lo
  que se le da, y si no coinciden se aborta.
  - `resources._rmsk` y `--usar-manifiesto` **derivan** la especie (del organismo de la
    referencia que el manifiesto declara en `accession`) y el resumen (del `.tbl`
    hermano). No se teclean. Por la línea de órdenes son `--rmsk-especie` y
    `--rmsk-resumen`, las dos **obligatorias** con un `.out`.
- **Resultados de las dos corridas buenas, y una predicción que sale MAL.**
  - **Ratón**: una repetición, `(CTC)n` en `tx:892-936`, **dentro del CDS** (185-949).
    No toca el 3'UTR ni la ventana del ORF conservado (`tx:707-728`). O sea: **el 3'UTR
    murino no tiene ni un elemento repetitivo**, y el `.tbl` lo respalda con los ceros
    explícitos por familia (SINEs 0, Alu/B1 0, B2-B4 0, LINEs 0, LTR 0).
  - **Humano**: una repetición, `(TA)n` en `tx:2097-2130` = **`3utr:1268-1301`**, que
    **sí** cae en el 3'UTR y **solapa 5 ventanas elegibles**: `3utr:1247`, `1249`,
    `1250`, `1251`, `1252`. La conversión va por `coords.Position.to_utr3`, no por una
    resta.
  - **La hipótesis de la carrera de A queda REFUTADA — predicción de Joaquín Castilla,
    2026-08-26, anotada con su nombre a petición suya y porque el acierto se habría
    anotado igual.** Se predijo que los 45 pb serían la carrera de A de `3utr:480-500`, y
    que de cumplirse sería convergencia de dos criterios independientes sobre el mismo
    tramo. **No lo es**: es un `(CTC)n` en el **CDS**, y la carrera más larga del 3'UTR
    murino son 10 A que acaban en `3utr:507`, donde RepeatMasker no marcó nada. **No hay
    convergencia.** Registro completo en
    [`docs/erratas.md`](./docs/erratas.md) nº 7. Si sólo se anotan las predicciones que
    salen bien, el registro deja de ser un registro y pasa a ser un argumento.
- **`repeticion_polimorfica` es OTRO motivo, no una etiqueta del mismo** (`masking`,
  columna propia en la tabla). Salen del mismo hallazgo y apuntan a cosas distintas:
  - **`repeticiones`** → **estabilidad del genoma AAV** (un tramo repetitivo dentro del
    casete es sustrato de recombinación) y, sobre la diana, una guía con miles de sitios
    perfectos.
  - **`repeticion_polimorfica`** → **viabilidad clínica**, que es otra cosa. Un
    microsatélite varía en **número de repeticiones** entre individuos, así que una guía
    ahí tendría **respondedores y no respondedores por variación de LONGITUD**, no de
    secuencia.
  - **Y hay un hueco que no cubre nadie: gnomAD anota SUSTITUCIONES y capta mal la
    variación de longitud**, así que el filtro de variación **no** cubre este riesgo.
    Decirlo importa: un «gnomAD limpio» invita a creer que la ventana está comprobada.
  - El criterio de qué familias son polimórficas (`Simple_repeat`, `Satellite`,
    `Low_complexity`) va **declarado como parámetro y no citado**: un SINE es repetitivo
    pero **disperso**, no varía de longitud, así que no entra.
  - **El caso real, con TRIPLE motivo**: el `(TA)n` humano de `3utr:1268-1301` solapa
    **5 ventanas** (`3utr:1247`, `1249`, `1250`, `1251`, `1252`) que caen por los **tres**
    ejes a la vez — repetitivo, polimórfico, y con **TECHO** por quedar por detrás de las
    **dos** `ATTAAA` humanas (`3utr:955` y `3utr:1167`). Tres razones independientes: no
    se recuperan arreglando una.
  - **Dónde se ve y dónde no**: el paso 15 enmascara y **retila**, así que con la máscara
    puesta esas ventanas ya no están en la piscina y una lista por ventana saldría vacía.
    El informe emite los **dos ejes** con su motivo; el detalle por ventana es
    `masking.triple_motive_rows` sobre un informe tilado **sin** máscara.
- **CUÁNTO MUERDE LA MÁSCARA SALE EN EL INFORME, y es INFORMACIÓN (2026-08-27)**
  (`masking.mask_bite`, `WHY_THE_BITE_IS_A_PROPERTY`). Salió al medir qué cambia cada
  fichero de referencia: la máscara del ratón quita **0** ventanas elegibles y la del
  humano **5**. Eso **no es una propiedad del pipeline** —es la misma maquinaria en los
  dos— sino de los **TRANSCRITOS**, y por eso va en la salida y no en un test.
  - Un filtro que corre y no quita nada tiene que **distinguirse** de uno que no corrió.
    Un cero a secas se lee como «no hizo nada» o, peor, como que no llegó a mirar — y no
    haber quitado nada no es lo mismo que no haber mirado. Misma familia que el «Alu 0 %»
    obtenido sin buscar Alu.
  - **Tres cifras y ninguna sobra**: elementos en toda la consulta, cuántos **dentro** del
    3'UTR, y cuántas ventanas **elegibles** solapa. En el ratón son 1 / 0 / 0, y es la
    segunda la que hace legible el cero: la máscara **sí** encontró algo y está en el CDS.
  - **Se calcula sobre un tilado SIN máscara**, misma condición que `triple_motive_rows`:
    con ella puesta el paso 15 retila y la cuenta saldría cero — indistinguible del cero
    de verdad, que es justo el número que esto existe para poder leer. Y con los **dos**
    desfases por nombre, por lo mismo que allí.
  - **Las dos cifras de la frase NO están transcritas**:
    `tests/test_mordida_de_la_mascara.py` las recalcula de los ficheros de verdad y exige
    que la prosa las cite (principio nº 13).
  - **Y NO se comprueba con un `grep` sobre el fuente.** El golden del informe se genera
    **sin máscara**, así que este bloque no entra en él: un test que mirara `outputs.py`
    pasaría igual con la línea sin llegar nunca a una pantalla. Se corre el **CLI de
    verdad** con `--rmsk` y se lee el informe que escribe.
  - **Y ESE TEST CAZÓ UNA RAMA QUE NUNCA HABÍA CORRIDO** (errata nº 31): `design.py`
    pasaba `thresholds=umbrales` y esa variable **no existe** —se llama `thresholds`—,
    así que **toda** corrida con `--rmsk` moría con un `NameError`, y con ella el bloque
    del **triple motivo**, que se cableó justo porque «existía sólo porque alguien lo
    corría a mano». Ningún test lo veía porque **ninguno corría el CLI con máscara**: los
    del triple motivo llaman a `triple_motive_rows` ellos mismos. Es la **quinta** vez de
    esa familia, y la primera en que hay un llamador escrito y lo que falla es el
    llamador. **Un fallo ruidoso en una rama que nadie ejecuta es tan invisible como uno
    silencioso**, y ni la alcanzabilidad ni el golden pueden verlo: la regla que queda es
    que una combinación de flags que ningún test recorre de punta a punta **no está
    probada**, por muchos tests que tengan sus piezas.

- **El manifiesto registra la BIBLIOTECA además de la versión del binario** (columna
  `biblioteca`): RepeatMasker 4.0.9 con Dfam_3.0 y con otra biblioteca dan resultados
  distintos, así que la versión a solas no identifica la corrida. Las cabeceras cortas se
  siguen aceptando (`LEGACY_COLUMNS`, `PREVIOUS_COLUMNS`, `BEFORE_ANATOMY_COLUMNS`) y las
  columnas nuevas salen vacías, que es la verdad — nadie las registró.
- **Y REGISTRA LA ANATOMÍA, no sólo los ficheros. AÑADIDO (2026-08-27)**: tres columnas
  más, `cds` (en la notación `185..949` del propio GenBank, para poder cotejarla con el
  `.gb` sin traducir nada), `md5_secuencia` y `md5_utr3`. Hasta aquí registraba nombre,
  tamaño, md5, accession y longitud, y **la frontera del 3'UTR no tenía ninguna línea**:
  vivía sólo en `reference.REFERENCES`, así que añadir una especie era editar código y un
  veredicto de hace tres meses no se podía auditar sin la versión del código con la que
  salió. De esa frontera cuelgan los tercios, la región de cada ventana y la distancia de
  cada señal de polyA al extremo.
  - **Sigue habiendo DOS definiciones** —la del manifiesto y la de `REFERENCES`— y eso
    sólo es admisible porque algo obliga a que coincidan:
    `tests/test_anatomia_en_el_manifiesto.py` las cruza **en las dos direcciones**, así
    que una especie nueva sin su línea hace fallar la suite. Es el principio nº 5
    aplicado antes de que el par diverja, en vez de después.
  - **Vacío significa NO REGISTRADO**, nunca «todo es 3'UTR»: un `0..0` o un md5 de
    relleno serían un dato. Un CDS que no se puede leer **aborta** — leer mal esa
    frontera corre los tercios enteros sin dar ningún error.
  - **AHORA SON TRES CHECKSUMS EN LA MISMA FILA**, y son cantidades distintas: `md5` es
    el del FICHERO en disco, `md5_secuencia` el de la SECUENCIA canónica (mayúsculas, sin
    cabecera, sin saltos) y `md5_utr3` el del 3'UTR — que es el que decide si la tabla de
    APA medido se aplica. Copiar uno en el sitio de otro hace que el fichero **bueno** se
    rechace; hay test de que los tres son distintos.
  - **La fila la monta `entry_row` y su ancho se DERIVA de `MANIFEST_COLUMNS`**, con un
    aborto si no cuadra. No es teórico: al entrar estas tres columnas, un test que
    escribía la fila con tabuladores contados a mano se quedó en diez campos y el
    manifiesto dejó de parsearse. Una columna que no se escribe corre los valores a la de
    al lado, y eso no da ningún error — es la tabla descuadrada de `Block.__post_init__`
    un nivel más abajo.
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
- **`riesgo_APA` es una PREDICCIÓN mientras no haya medida**, y el informe lo dice con
  esa palabra. Con sitios medidos el dato sustituye a la predicción y sale el techo de
  knockdown.
- **LA MEDIDA ENTRA SIEMPRE QUE HAYA MEDIDA. DECIDIDO (2026-08-27)**
  (`apa.WHY_MEASURE_IS_NOT_A_FLAG`, `tiling.RESOLVER_MEDIDA`, `apa.ApaExcluded`). No es
  una preferencia de ordenación: **son dos veredictos**. Sin la medida `3utr:221` lleva
  una penalización de −1,00 por hexámero variante y **sigue en el panel**; con ella, el
  `AATATA` de `3utr:236` es `APA_POSIBLE` y `3utr:221` es **FAIL duro** por solape
  estérico. Y el dato existe: PSE 21,1 %, AvgRPM 0,55, el proximal **más usado** de los
  tres.
  - **`tile_utr` la resuelve por su cuenta**: nadie tiene que acordarse. Antes dependía de
    que el llamador llamara a `resolve_measured` y pasara el resultado — tres sitios
    acordándose de lo mismo, y ya había fallado una vez (la cuarta divergencia entre la
    página y el CLI). Doce ficheros de test la pasaban a mano y dejaron de necesitarlo.
  - **`measured_apa=None` ABORTA.** Era el salto silencioso. Para excluirla hay que
    escribir `apa.ApaExcluded(reason=…)`, el motivo es **obligatorio** y **viaja al
    informe** (`TilingReport.apa_excluded_reason`): sin él, «se decidió no usarla» y
    «nadie se acordó» dan el mismo resultado mudo. Mismo criterio que `deposito.Ignored`.
  - **El modo sin medida NO es el modo neutro**: trata el hexámero como **no funcional**,
    que es la hipótesis menos conservadora y la falsa según lo medido. El defecto
    favorecía al candidato equivocado **por omisión**. Principio nº 10.
  - `--apa-medido` deja de ser un interruptor y pasa a ser una tabla **adicional**; la
    exclusión deliberada es `--ignorar-apa-medido MOTIVO`.
- **`APA_POSIBLE` no dice lo mismo de dos cosas distintas**
  (`PolyASignal.classification_label`). Se emite `APA_POSIBLE (medido, PolyA_DB v4.1)` y
  `APA_POSIBLE (canónico, asumido)`, con la procedencia **pegada a la clase**: `evidence`
  ya las distinguía, pero quedaba cinco palabras más allá, donde no lo lee quien copia la
  línea a un correo. Misma regla que el md5 junto a la longitud. Sólo en esa clase:
  ponerla en todas la haría invisible. **Con el ratón las DOS están medidas** —288 es uno
  de los tres sitios anclados—, así que el caso «canónico, asumido» es el **humano**.
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
  - **INVARIANTE DE RANGO. AÑADIDO (2026-08-26)** (`coords.max_utr3`,
    `coords.check_utr3_range`). La clase impedía construir una posición **sin** marco,
    pero no impedía declarar el marco **equivocado**. Ahora una `Position` en `3utr` que
    no quepa en el 3'UTR más largo que conoce el proyecto **aborta**, y el mensaje dice
    que casi seguro es una coordenada del transcrito. El techo se **deriva** de
    `reference.REFERENCES` (hoy 1606, lo pone el humano): si entra una referencia con un
    3'UTR más largo, sube solo. `label` y `span` aceptan además `limit` —la longitud real
    de la especie que se está analizando— y `coords.bound_of(anatomy)` la saca; `tx` no
    se comprueba, porque ponerle un techo sería inventarse un límite.
  - **Y lo que este invariante NO puede hacer es un PRINCIPIO del proyecto, no una nota
    de `coords.py`**: está en [`docs/principios.md`](./docs/principios.md) porque aplica a
    todo. En corto: **el invariante caza lo imposible, no lo equivocado; el golden es lo
    único que lee la salida entera.** `3utr:1784` sobre 1606 nt y `3utr:1273-2191` sobre
    1242 los caza; `3utr:1185` sobre un 3'UTR murino de 1242 **no**, porque 1185 es una
    posición válida — sólo que de otra señal. Ese caso lo cazó el golden, al leer el diff.
    - **Corolario operativo, y va aplicado a toda magnitud derivada nueva**: pregúntate si
      puede salir un valor **equivocado pero dentro de rango**. Si puede —y casi siempre
      puede: una conversión de marco, una resta de desfase, un denominador cambiado—
      **no hay invariante que lo cubra**, el bloque entra en el golden antes de darlo por
      bueno, se lee el diff, y el test fija el **valor con su procedencia**, no su forma.
    - Ya ha vuelto a pasar dos veces desde que se escribió: el bloque de holguras y los
      **dos desfases** de `triple_motive_rows` (con uno solo, `3utr:1275` salía marcada
      por un elemento que está a 800 nt; posición válida, ningún error). Los dos los cazó
      leer la salida.
  - **El fallo REAPARECE cada vez que se escribe un bloque nuevo**, y ha vuelto tres veces
    más: `apa_ceiling_table` imprimía `3utr:1784` para una coordenada del transcrito humano
    —en el informe que ya se estaba entregando— y los tramos de techo salían como
    `3utr:1-1200` sobre un 3'UTR de 1242 nt, y el bloque de holguras imprimió `3utr:1185`
    para la señal mientras la ventana sí venía convertida. Los tres llevaban `Frame.UTR3`
    a pelo o una conversión a medias. La regla para un bloque nuevo es: el marco **se
    recibe**, sacado de la anatomía, las coordenadas se convierten **todas a la vez o
    ninguna**, y nunca se pone `UTR3` porque «suele serlo».
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
- **EL GOLDEN SE GENERA CON LA CONFIGURACIÓN POR DEFECTO. SIN EXCEPCIONES.
  DECIDIDO (2026-08-27)**, principio nº 18. Llevaba `--inmunes 4`, `--candidates 10`,
  `--min-block 22` y `--sin-manifiesto` **tecleados**, así que la única corrida del CLI
  que alguien miraba llevaba una configuración que ningún usuario usa — y validaba un
  panel que el CLI por defecto no producía (errata nº 32). **De los cuatro, TRES eran
  inertes**: llevaban ahí sin hacer nada y sin que nadie lo supiera.
  - Si hace falta otra configuración, va en un artefacto **adicional cuyo nombre la
    declara**: hoy `raton_informe__con_convergencia.txt` y
    `raton_informe__con_usar_manifiesto__una_especie.txt`. Hay test de que cada variante
    nombra en su fichero las banderas que la distinguen.
  - **La segunda variante existe porque `--usar-manifiesto` —«la forma normal de
    correr»— no la leía ningún golden**, y al escribirla apareció que **abortaba** con un
    `KeyError: 'polyadb'` contra el manifiesto de verdad: `manifest.ROLES` ganó ese rol y
    `design.py` no se enteró. Va **con una sola especie** a propósito: con dos, el
    manifiesto conecta `rmsk_mouse.out` por su rol y `RepeatMask.query_length` aborta —el
    guardia hace lo que debe, y lo que dice es que esa combinación no es viable hoy.
  - **Y los otros tres artefactos tenían el mismo vicio**: la ficha, el documento y la
    página construían `SelectionConfig(n_candidates=10, apa_immune_quota=4)` a mano.
    Ahora pasan por `default_config()` y **no cambió ni una línea**, que es lo que se
    espera: hoy los valores coinciden, y mañana los goldens se enteran si la constante se
    mueve.

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
- **La fracción de isoforma larga está MEDIDA y YA ENTRA**
  (`data/reference/polya_db_mouse.tsv`, cargada con `apa.find_polyadb`; estuvo
  cableada en `apa.POLYA_DB_PRNP` hasta 2026-08-27 y la constante ya no existe).
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
  - **CABO SUELTO, NO RESUELTO: `131938392`** (`apa.CLUSTER_READING`). Es el PAS con
    **más expresión** de los tres (PSE 70,5 %, AvgRPM 1,65) y es el **numerador** de la
    fracción larga, así que de su lectura depende lo que significa el 0,86. Hay dos:
    - **(a)** es el racimo del terminal `131938427` → 0,86 es exactamente lo que dice.
    - **(b)** es un corte **propio** en `3utr:1199-1207` → hay un tercer corte por
      delante del terminal. Y peor de lo que parece: por detrás de esa banda **ya no
      queda ningún PAS con expresión medida**, así que ahí la medida no acota nada — no
      es un techo bajo, es un techo del que esta tabla no sabe nada.
    El anclaje de cuatro puntos **estrecha** la banda a `3utr:1199-1207` pero **no
    desempata**: los dos `TATAAA` de su clase que caben ahí son `3utr:1178` y `3utr:1189`.
    - **No se cierra hacia (a) por conveniencia**, que es justo lo que sería cerrarlo
      porque es la lectura que sostiene el número que ya tenemos.
    - **Cuánto cuesta hoy no resolverlo**: el bloque conservado de `3utr:1138-1163` queda
      **por delante** de la banda; `3utr:1200` de la lista externa cae **dentro** (y ya
      fallaba nuestro propio filtro duro de polyA); **cero** ventanas elegibles por
      detrás y cero dentro.
    - **Por qué el frente sigue cerrado igual, y no por conveniencia**: bajo **las dos**
      lecturas el techo del panel es **≥ 0,86**. Bajo (a) es 0,86 exacto; bajo (b) los
      diez siguen por delante de la banda, así que conservan su diana en la isoforma de
      ese corte **y** en la terminal, cuya expresión no está medida — o sea 0,86 más lo
      que no se ha contado. La ambigüedad no mueve el número **del panel**; movería el de
      cualquier candidato que se pusiera por detrás de `3utr:1207`, y hoy no hay ninguno.
    - **Qué lo resolvería**: 3'-end seq de cerebro murino, o la regla de agrupamiento que
      use la propia base. Ninguna de las dos está aquí.
    - **RATIFICADO (2026-08-26)**: el razonamiento de por qué la ambigüedad no mueve el
      techo del panel queda aceptado tal cual, y **el cabo queda abierto**. No se cierra.
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
- **`3utr:200` conserva la plaza, pero NUNCA sale como «inmune» a secas. DECIDIDO
  (2026-08-26)** (`selection.promotion_clearance`, bloque «Lo que se salva, y por
  cuánto»). Se emite en **los dos ejes**, siempre:

  `inmune_truncamiento = SI` / `esterico = PENALIZADO`

  - **El eje de truncamiento es GEOMÉTRICO** y no depende de ninguna convención: empieza
    en `200` y el corte más temprano está en `251`. O empiezas antes o no.
  - **El eje estérico es un GRADIENTE, no una frontera** (`polya.STERIC_IS_A_GRADIENT`).
    El flanco de ±10 nt **no tiene base medida**: es un umbral operativo, y la huella real
    de CPSF/CstF sobre el pre-mRNA es **mayor**, así que los 14 nt que separan
    `3utr:200-221` del hexámero están **probablemente dentro de la zona de competencia**
    aunque el filtro lo deje pasar. Cualquier umbral en nucleótidos le atribuye a este eje
    una precisión que la biología no tiene.
  - **Por eso la sensibilidad al flanco va SIEMPRE pegada al veredicto**, no en una nota:
    la ventana queda **4 nt** por delante de la zona prohibida (`3utr:226-251`) y **con un
    flanco de 15 en vez de 10 también caería**. Sin esa cifra, un `PASS` parece una medida
    y es una convención. El flanco de cambio se **busca** con el mismo `classify_signal`
    que decide, no se calcula a mano.
  - En la lista de inmunes del informe, `3utr:200` sale con `[esterico PENALIZADO]` al
    lado; `3utr:10`, `60` y `143` no llevan marca porque no la necesitan. Poner la marca
    en todos la haría invisible.
- **REGISTRO DE DECISIONES: el criterio escalonado no es un colador, y hay evidencia.**
  El criterio se decidió con la tabla de los seis candidatos delante, y quien lo defendió
  tenía interés en el resultado. El 2026-08-26 ese mismo criterio **tumbó `3utr:221`**,
  que era uno de los cuatro inmunes del panel y uno de los mejores por asimetría. Un
  criterio que sólo aprueba nunca demuestra nada; éste ha quitado algo que su autor
  quería conservar, y por eso vale. Se anota la **decisión**, no sólo el resultado: si
  más adelante alguien propone relajarlo, este caso es el que hay que discutir.
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
  - **SON DOS MODOS DE FALLO, no uno con un detalle** (`splicing.RETENTION_MODES`). Si
    el intrón se retiene: **(a)** la horquilla se queda en el 5'UTR del mRNA maduro, y
    **(b)** el ribosoma escanea desde el extremo 5' y se encuentra varios AUG antes del
    legítimo. **El (b) actúa aunque la horquilla no estorbara nada**, así que van
    separados y contados aparte en el informe.
  - **Los uAUG, con posición, Kozak y marco** (`splicing.scan_upstream_atgs`). Con la
    horquilla de referencia son **ocho**, y el análisis da tres categorías, no una:
    - **`EXTENSION_N_TERMINAL`** — en marco **y** sin codón de parada antes del ATG
      legítimo. Es el caso **peor**: produce PrP con una cola por delante, o sea **algo
      que un Western podría confundir con la DN**. **Con este casete no hay ninguno, y
      se comprueba en vez de suponerse**: el único en marco es `+16` (MVM5,
      `TAAGGGATG`, Kozak **FUERTE**, a 318 nt) y **para a los 10 codones**.
    - **`uORF_SOLAPANTE`** — fuera de marco y **sin** parada antes del ATG legítimo:
      `+210` y `+237`. El ribosoma **sigue elongando** al pasar por el inicio, así que no
      puede reiniciar ahí. Es peor que un uORF que termina antes, y meterlo en el mismo
      saco lo escondía.
    - **`uORF`** — el resto.
    El criterio de Kozak (**−3** purina, **+4** G) va **declarado como parámetro de este
    análisis, no citado** (`splicing.KOZAK_CRITERION`). Y **la cuenta cambia por
    candidato**: tres de los ocho los aporta la horquilla.
  - **No se cierra con ningún fichero**, y el informe lo separa de los otros: sus
    **cuatro** lecturas son de banco, las cuatro `NOT_RUN`, y este software no corre
    ninguna.
    1. **RT-PCR de empalme** con cebadores en los exones que flanquean el intrón MVM.
       Banda **corta** = empalmado, banda **larga** = retenido, y la **proporción** es la
       eficiencia.
    2. **Western L42 normalizado por vg-qPCR.** Sin normalizar, «no hay proteína» no se
       distingue de «no llegó el vector»: los dos dan una membrana vacía y solo uno culpa
       al empalme.
    3. **Parental SIN INTRÓN en la misma tanda**, como techo de expresión. Sin techo, un
       western flojo no dice si el empalme va mal o si la construcción expresa poco.
    4. **SECUENCIAR la banda corta, y es LA QUE CIERRA el frente.** La lectura de éxito
       es la **secuencia de la unión exón-exón**, **no la altura de la banda**. Sin ella,
       ver una banda corta no descarta el donante críptico.
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
- **El donante críptico `GTGAGCG` del andamio: lo que la secuencia cierra y lo que NO**
  (`splicing.cryptic_donor_scan`). Está en el flanco 5' de miR-E, **dentro del andamio**,
  así que viaja con cualquier candidato: intrón `+98`.
  - **La pregunta que se podía contestar hoy, contestada**: entre ese donante y el aceptor
    legítimo (`+295`) hay **13 AG**, y **ninguno es un aceptor utilizable**. El legítimo
    tiene un tracto de **9 pirimidinas contiguas**; el mejor críptico llega a **3**. El
    criterio va **declarado como parámetro y no como cita** (`SPLICE_SITE_CRITERION`), y
    la comparación se hace **contra el aceptor legítimo del mismo intrón** — referencia
    interna, así que el veredicto no depende de ningún umbral traído de fuera.
  - **Eso cierra** la familia de productos que necesitaría un aceptor críptico ahí.
  - **PERO NO CIERRA el riesgo del donante críptico, y ese es el punto**: ese donante
    **no necesita** un aceptor críptico — el **legítimo** del MVM está aguas abajo y es
    perfectamente utilizable. Un empalme `+98 → +295` quita 198 nt y deja **97 nt** de
    intrón dentro: banda = **empalmada + 97 pb**, frente a +0 (correcta) y +296
    (retenida). Es la banda **intermedia**, exactamente la confundible en un gel. Los dos
    donantes compiten por el **mismo** aceptor y cuál gana no lo dice la secuencia — por
    eso la lectura 4 no es opcional.
- **El control SIN INTRÓN se ESPECIFICA, no se pide** (`splicing.intronless_control`, y
  sale en la hoja de pedido como un fragmento más). Es el casete con **donante y aceptor
  eliminados** y todo lo demás conservado base a base: 82 pb con 30 nt de homología a cada
  lado, `md5 d72c574d…`, y conserva MluI y AgeI para la digestión.
  - **No viola la regla 1**: no genera secuencia, **borra dos piezas literales** de una
    que está en el repositorio. Hay un test que reinserta lo borrado y comprueba que
    recupera el original **base a base**.
  - Se **niega** a construirlo sobre un casete cuyo intrón no sea el vacío: quitar donante
    y aceptor de un casete **con módulo** dejaría la horquilla dentro del mRNA, que es el
    modo de fallo que se quiere medir, no su control.
  - La longitud sale tal cual y **no se inventa un mínimo de síntesis**: si el proveedor
    pide más, `arm=N` alarga los brazos, y salen del propio plásmido.
- **El aviso del cebador va en NEGRITA en la hoja** (`blocks.PRIMER_WARNING`): **la
  especificidad de vector la da el cebador de aguas ARRIBA, y solo ese**. La ventana de
  aguas abajo entra en el ORF de PrP, así que un par con los dos cebadores ahí
  amplificaría también el **Prnp endógeno** del tejido — saldría banda, del tamaño
  esperado, y no sería del vector. **Es el error que arruinaría el ensayo sin dar ninguna
  señal**, y por eso no va en un párrafo cualquiera.
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
- **El frente de especificidad es FUNCIONALIDAD, no un script suelto**
  (`blast.py`, `blast_store.py`, el modal en `presentation.py` + la página).
  - **ARQUITECTURA, y es lo primero**: este software **no lanza el BLAST y no puede** —
    el navegador no puede llamar a NCBI (CORS) y el backend no tiene red saliente. El
    modal **prepara** (FASTA de consulta con md5 + la orden completa), se **entrega** para
    ejecutar fuera, y se **recoge** el `-outfmt 6`. No es una limitación escondida: es la
    arquitectura, y `Disabled.why` la dice.
  - **El ejecutor va detrás de una interfaz con TRES implementaciones** para que el día
    que haya red no haya que tocar la interfaz: `Disabled` (la de hoy), `LocalCommand`
    (da la orden, es la única vía que puede dar **veredicto** porque una base local tiene
    md5) y `RemoteApi`. **`RemoteApi` no trae ninguna URL escrita** (regla 4): se le pasa
    un endpoint verificado o aborta, y hay un test que lee el fuente del módulo y
    comprueba que no hay ni un `http`.
  - **Ajustes por defecto**: `-task blastn-short`, `-word_size 7`, `-evalue 1000`,
    `-dust no`, `-outfmt 6`, `refseq_rna`, `txid10090`, predichos `XM_`/`XR_` **sí**.
    Editables, y **cualquiera modificado se marca en rojo y VIAJA con el resultado**: un
    veredicto obtenido con parámetros no estándar no puede ser indistinguible de uno
    estándar. Es la misma lección del `.out` sin especie.
  - **`-remote` es EXPLORACIÓN, nunca veredicto**, con el motivo visible: la base de NCBI
    **cambia entre corridas**, así que no es reproducible. Sólo una base **local con md5**
    cierra el frente.
  - **`-outfmt` distinto de 6 aborta al ELEGIRLO**, no al subir el fichero: aceptar un
    formato que el almacén no sabe leer dejaría entrar algo que luego se rechaza sin poder
    decir por qué.
  - **Un `-outfmt 6` vacío ABORTA**: cero hits y «la corrida no llegó a correr» son cosas
    distintas y ese fichero no las distingue. Misma lección que el `.out` sin resumen.
- **El almacén de corridas es INMUTABLE y nada se sobrescribe** (`blast_store.py`). Cada
  corrida guarda id, fecha, quién la subió, **md5 de la consulta y del resultado**, los
  parámetros **completos** (no sólo los cambiados), la base con nombre/versión/md5 —o
  marcada `no reproducible` con esas palabras si fue `-remote`— y el **crudo sin tocar**
  además del parseado. Una corrida nueva se **añade**; la ficha enseña la última y enlaza
  el historial. Repetir un `run_id` aborta.
  - **Validación al subir, y las dos rechazan**: que el md5 del FASTA de consulta sea el
    que generó la app, y que toda `query` del resultado esté en el panel. **Es el fallo
    del CSV de miRarchitect** —un fichero de otra corrida pegado por error, que entra,
    cuadra de forma y produce un análisis entero sobre el dato equivocado— y el mensaje lo
    nombra.
  - **Un candidato sin corrida sigue en `NOT_RUN`, y visible.** El almacén **no relaja la
    regla 3**: no haber corrido y haber corrido limpio no se parecen en nada.
- **`offtarget_seed` es un frente PROPIO y no se funde con `especificidad`**
  (`seed_load.WHY_NOT_BLAST`). El BLAST busca **complementariedad extensa**; el
  off-target mediado por seed **no se busca con BLAST y no se puede**: **7 nt contiguos no
  dan un alineamiento puntuable**, así que un blastn no los devuelve por mucho que se le
  baje el `word_size`. Es coincidencia **exacta** del heptámero 2-8 sobre los 3'UTR del
  transcriptoma murino —**búsqueda de subcadena, no alineamiento**— y necesita
  `transcriptoma_3utr.fa`.
  - **Fundirlos en un «especificidad: PASS» daría por cubierto el modo de off-target más
    frecuente de RNAi con una herramienta que no lo detecta.** Por eso son dos frentes,
    el informe los cuenta aparte, y el motivo de `especificidad` avisa de que **no** cubre
    al otro.
  - Antes este frente era **invisible**: `carga_seed` es un número comparativo, así que
    nunca estuvo en `not_run_filters` y no salía en la lista de frentes. Se contaba
    «especificidad» y parecía que la pregunta estaba cubierta.
- **La ficha de un candidato reúne todo lo que se sabe de un sitio** (`dossier.py`), y se
  compara **ENTERA** contra `tests/golden/ficha_raton_200.txt`, con la misma disciplina
  que el informe: veredicto de **cada** frente con procedencia y fecha, asimetría en sus
  tres columnas, techo de APA **con el tramo del que sale**, hexámeros cercanos con clase
  y distancia, el módulo de 149 nt, el cassette de 318 y el historial de BLAST.
  - **Emite TODOS los frentes que el informe conoce, no un número fijo.** Hoy son nueve.
    Fijar «seis» en el código haría que el décimo entrara sin que la ficha lo enseñara.
  - **Un frente CERRADO no sale como `NOT_RUN`**: decir que falta algo resuelto engaña
    tanto como lo contrario. Sale con su estado y con «frente CERRADO» en la procedencia.
  - Un sitio que no está en el panel de esa corrida **aborta**: no se emite la ficha de
    un candidato que no existe ahí.
- **El modal no decide nada; `presentation.py` sí** (regla 6). La página recibe filas con
  un booleano `modificado` —para pintar en rojo— y avisos con un booleano `bloquea`.
  Hasta la conversión de «SI»/«no» a booleano vive fuera: si la hiciera la página no
  tendría test, y el día que alguien escriba «si» en minúsculas el ajuste se leería como
  `False` sin que nadie se enterara. Hay un test que lee el fuente del modal y comprueba
  que no hay ni un `int(`, `float(`, `.upper()` ni `sorted(`.
- **El segundo modal, colisión de seed, SÍ EJECUTA** (`seed_scan.py`, `seed_store.py`).
  Mismo patrón que el de BLAST y una diferencia que lo cambia todo: aquí no hay red ni
  orden que copiar — el cálculo es **búsqueda de subcadena** contra `mature.fa`, ya
  cargado y verificado por md5. Botón → resultado.
  - **La tabla previa es la mitad del valor**: antes de correr nada se enseña candidato,
    hebra, **secuencia completa** y heptámero, con casillas por candidato y por hebra
    (las dos marcadas por defecto). Y **marca las filas que comparten heptámero**: dos
    candidatos con la misma seed **no son dos apuestas independientes** en este eje, y eso
    tiene que verse antes de correr, no después.
  - **Ajustes**: ventana `2-8` (alternativa `2-7`), especie `mmu-`, nivel
    núcleo/ampliado/ambos. Cualquiera cambiado se marca y **viaja con el resultado**.
    - **La ventana viaja en CADA resultado** (`SeedResult.window`): una corrida de `2-7`
      no puede presentarse como una de `2-8`, y sus tasas base ni se parecen.
    - **`normalize_u_t` no es editable y se declara a la vista.** Apagarla daría **cero
      colisiones** en todas y eso parece una buena noticia: es un desajuste de alfabeto
      disfrazado de resultado limpio. Se enseña, no se ofrece.
  - **La TASA BASE se DERIVA del fichero cargado, no se teclea** (`seed_scan.base_rate`),
    y va **siempre** junto al resultado — también en los `LIMPIO`, para no dar una falsa
    calma. Comprobada contra el fichero real:

    | filtro | maduros | seeds distintas | espacio | tasa |
    |---|---|---|---|---|
    | `mmu-`, ventana 2-8 | 1988 | 1593 | 16384 | **9,7 %** |
    | `mmu-`, ventana 2-7 | 1988 | 1274 | 4096 | **31,1 %** |
    | `mmu-` + `hsa-`, 2-8 | 4777 | 3127 | 16384 | **19,1 %** |

    Las dos últimas filas son la razón de que la tasa base no se pueda teclear: con `2-7`
    un tercio de las guías colisiona por azar, y dejar `hsa-` dentro **casi dobla** la
    tasa. El filtro de especie y la ventana no son cosméticos — cambian cómo se lee un
    `AVISO`.
  - **Tres cosas van DESTACADAS, no enterradas en la tabla** (`presentation.seed_highlights`):
    la colisión con la familia **miR-30** con su razón escrita (el andamio es miR-E,
    derivado de miR-30a: lectura distinta y peor), las colisiones de **pasajera**
    separadas de las de guía, y la **tasa base**.
  - **Guía y pasajera NUNCA se funden**: `SeedStore.verdict_for` es por **hebra** y no
    existe un `verdict_for_candidate` — a propósito, y hay un test que lo comprueba. En la
    ficha son **dos filas**, `seed_colision:guia` y `seed_colision:pasajera`.
  - **El almacén es inmutable**, igual que el de BLAST: fecha, quién la corrió, parámetros
    completos, release y md5 de `mature.fa`, crudo y parseado. Nada se sobrescribe.
  - **Lo que este modal NO cierra, escrito en la propia interfaz**
    (`seed_scan.WHAT_THIS_DOES_NOT_ANSWER`): contesta «¿mi seed es la de un miARN
    conocido?»; **no** contesta «¿cuántos mensajeros llevan mi seed?», que es la carga de
    off-targets y necesita `transcriptoma_3utr.fa`. El hueco queda preparado en la misma
    página, en `NOT_RUN` **visible** (`presentation.seed_load_placeholder`).
  - **Bloque exportable** (`SeedScan.export_block`) con pregunta, fuente y versión,
    parámetros, resultado por candidato **y por hebra**, y la tasa base. Se lee sin la app
    delante: es material para defender la selección.
  - **Resultado de la corrida murina de referencia**: 20 consultas, **cero FAIL** de
    núcleo, **cero miR-30**, y **tres AVISO** —`3utr:143` (`mmu-miR-7653-3p`), `3utr:359`
    (`mmu-miR-5615-5p`) y la pasajera de `3utr:819` (`mmu-miR-136-5p`)—. Tres de veinte es
    el 15 % contra una tasa base del 10 %: **es lo que predice el azar**, y por eso la
    cifra va al lado.
- **PERSISTENCIA: JSONL append-only por proyecto, NO SQLite. DECIDIDO (2026-08-26)**
  (`store.py`). Se decide **antes** que nada de lo que guarda, para que los tres modales
  escriban en el mismo sitio y no cada uno en el suyo:

  ```
  data/proyectos/<slug>/proyecto.json    la entrada: md5, longitud, especie, anatomia
  data/proyectos/<slug>/registro.jsonl   el log APPEND-ONLY de todo lo demas
  ```

  - **Por qué no SQLite**, que también es stdlib y también sobrevive a la sesión: este
    proyecto ya decidió que el manifiesto va en **texto y versionado** porque «un
    veredicto no es auditable dentro de un año» si no se puede leer con `cat`. Un `.db`
    binario no se diffea, no se grepea y no se lee sin la app — y el registro de un
    veredicto tiene que sobrevivir **a la app que lo escribió**. Si algún día hacen falta
    consultas de verdad, SQLite se construye DESDE este log; al revés no.
  - **Un solo directorio y un solo log por proyecto.** Si cada modal abriera el suyo, la
    ficha tendría que buscar en tres sitios y el día que se añada un cuarto se quedaría
    fuera sin que nadie lo note. Es la misma lección de `offtarget_seed`: **un frente que
    no se ve no existe.**
  - **«Nada se sobrescribe» deja de ser una convención**: cada línea lleva el md5 de la
    anterior, así que editar o borrar una vieja rompe la cadena y `verify()` lo dice
    **con el número de línea**. Y lo que la cadena NO hace va escrito
    (`WHAT_THE_CHAIN_DOES_NOT_DO`): no impide editar el fichero —nada lo impide, es un
    fichero—, lo vuelve **visible**. Misma disciplina que el md5 del manifiesto.
  - `RECORD_KINDS` está **cerrado** (`corrida_blast`, `corrida_seed`,
    `corrida_offtarget`, `corrida_empalme`, `seleccion`, `descarte`, `veredicto`,
    `nota`): si cada modal se inventa su etiqueta, el log deja de poder leerse sin saber
    quién lo escribió. Cada modal nuevo añade **su** etiqueta aquí y su par
    `save_*`/`load_*`; hay un test que comprueba que no falta ninguno de los cuatro.
  - **La entrada preferente es el `.gb`, no la secuencia pelada.** Un FASTA se acepta,
    pero entonces `Project.reliable` es falso y `why_unreliable` dice qué deja de valer:
    **tercios, proximal/medio/distal y zonas de polyA** salen `NO_FIABLE`, porque todos
    cuelgan de dónde empieza el 3'UTR. No es un aviso decorativo — sin frontera, «tercio
    medio» no significa nada.
- **Los fixtures por especie se DECLARAN, nunca se suponen** (`species.py`). `resolve()`
  **no infiere** el prefijo de miRBase ni el taxid de un nombre: una especie que no está
  declarada aborta en vez de fabricar `ory-` o un `txid` por patrón (regla 4 aplicada a
  algo que no es una URL). `fixture_report(especie)` lista **frente por frente** si se
  puede cerrar y, si no, **nombra el fichero concreto** que falta.
  - **El fixture de una especie no vale para otra**, y eso ya está demostrado con datos:
    es exactamente el caso de `rmsk_human` con biblioteca de ratón. `_WRONG_SPECIES_NOTE`
    lo dice pegado al informe de disponibilidad, no en una nota aparte.
  - Con conejo, hoy: **1 de 7** frentes cerrable. Los seis restantes nombran
    `rmsk_oryctolagus_cuniculus.out`, `mature.fa` filtrado a su prefijo —**que no está
    declarado**—, `transcriptoma_3utr_oryctolagus_cuniculus.fa`, datos de PolyA_DB para
    esa especie y una base de RefSeq de *Oryctolagus cuniculus*.
- **Lo que hoy tiene la anatomía del RATÓN metida por dentro** (auditoría 2026-08-26).
  No son los ficheros —esos ya se sabe que faltan por especie— sino **constantes,
  supuestos y valores por defecto**. Es la lista de lo que hay que tocar para correr otra
  especie, y por tanto la lista de lo que aún no es una app:
  - `coords.max_utr3()` valía 1606 **derivado de `reference.REFERENCES`**, o sea de las
    dos especies que hay. Un 3'UTR de conejo de 1900 nt **abortaba**: el invariante de
    rango, que existe para cazar coordenadas de transcrito, tumbaba una coordenada
    legítima. Cerrado con `coords.declare_utr3_length(longitud, species=…)`: la longitud
    real **se declara**, no se adivina ni se sube el techo a ojo.
  - `manifest.ROLES` trae `rmsk_mouse.out` **escrito**: con otra especie el manifiesto
    conectaba el fichero equivocado por su rol. Es el mismo agujero que cierra
    `RepeatMask.query_length` un nivel más abajo. **CERRADO (2026-08-26)**: el nombre por
    especie lo pone `species.required_files` y el rol viaja con él
    (`resources.roles_for_species`, `deposito.role_for`). `ROLES` conserva el nombre
    murino como el caso base del manifiesto que ya existe, no como el único posible.
  - **Prefijos y taxids por defecto**: `mirna.DEFAULT_PREFIXES = ("mmu-", "hsa-")`,
    `seed_scan.SeedParams.species_prefix = "mmu-"`, `blast.BlastParams.entrez_query =
    "txid10090"`. Y `specificity.TAXIDS` solo conoce ratón y humano — **aborta** con
    cualquier otra, que es el comportamiento correcto, pero deja el frente cerrado a dos
    especies.
  - `mirna.CORE_ABUNDANT` son **diez miARN de cerebro murino**. Matiz que importa:
    `CoreMember.matches` **quita el prefijo** antes de comparar, así que casa igual con
    `ocu-let-7a-5p`. O sea, no está roto para otra especie — está **sin justificar**: la
    autorización escrita habla de consenso del campo en cerebro **murino**.
  - `blocks.PIECES` son **12 piezas literales** del plásmido de PrP murino
    (`MluI`, `exon5`, `MVM5`, `espaciador5`, `NheI`, `contexto5`, `contexto3`, `SacI`,
    `espaciador3`, `MVM3`, `exon3`, `AgeI`), y con ellas el módulo, el cassette, la hoja
    de pedido, el control sin intrón y `splicing.locate_intron`. **Esto no es un valor por
    defecto: es el vector concreto**, y para otra especie no se parametriza — se sustituye.
  - La tabla de PolyA_DB **no** está en esta lista, y por dos razones distintas: se
    aplica por md5 del 3'UTR (`resolve_measured`), así que sobre otra secuencia
    devuelve `None` y no promueve nada — y desde 2026-08-27 **ya no está en el
    código**: es `polya_db_mouse.tsv`, un fichero del gestor con su md5 en el
    manifiesto, así que otra especie es otro fichero y no otro commit.
  - **Y lo que NO está metido, para no tocarlo**: `polya.ALL_SIGNALS` (los diez
    hexámeros), `CLEAVAGE_MIN/MAX` (10-30 nt), `SIGNAL_FLANK` y los umbrales terminales
    son **mamífero**, no murino. Los números 949 / 1242 / 2191 aparecen solo en
    `reference.REFERENCES` —que es **dato**— y en docstrings; **en ninguna rama de código**.
- **Dónde vive cada análisis de estos días** (auditoría 2026-08-26): el cruce con
  miRarchitect (`spacing.compare_sites` + `convergence`), el anclaje de PolyA_DB
  (`apa.anchor_polyadb`, `resolve_measured`) y el enmascarado con las corridas reales de
  RepeatMasker (`masking.apply_mask` vía `tiling`) **están dentro**, con caller en
  `tools/design.py` y en el informe. **La excepción es `masking.triple_motive_rows`**, que
  hoy no tiene **ningún** caller fuera de sus tests: el detalle por ventana del triple
  motivo se calculó y no se emite en ninguna salida. Mientras siga así, es un análisis que
  se corre a mano aunque el código esté en la librería.
- **El TERCER modal, carga de off-targets por seed, cierra `offtarget_seed`**
  (`offtarget.py`, `offtarget_store.py`). Es el frente que estuvo **invisible**, y ahora
  se ve en la ficha partido en dos filas. Necesita `transcriptoma_3utr.fa`, que no está.
  - **CUATRO clases, y NUNCA un total** (`SITE_CLASSES`, `WHY_NOT_SUMMED`): `8mer`,
    `7mer-m8`, `7mer-A1`, `6mer`. La represión esperada de un 8mer y la de un 6mer no se
    parecen en nada, así que sumarlas **mezcla señal con ruido**. `Counts` **no tiene**
    ningún atributo que las sume y hay un test que lo comprueba: si existiera, alguien
    acabaría imprimiéndolo.
    - Las cuatro comparten un **núcleo de 6 nt**; lo que las separa es la base de delante
      (la que aparea con la posición 8) y la de detrás (la A de la posición 1 de la
      diana). Se busca el núcleo **una vez** y se mira el contexto, así que son
      **excluyentes por construcción** y no hay que descontar unas de otras. Test: la
      suma de las cuatro es exactamente el número de apariciones del núcleo.
  - **Un conteo a secas no es interpretable**, y por eso van con él tres cosas:
    - **PERCENTIL contra una nula de composición equivalente** (`null_distribution`),
      ≥10.000 sorteos —`MIN_NULL_DRAWS`, y pedir menos **aborta**—. La nula son
      **permutaciones del propio heptámero**, no heptámeros uniformes: una nula uniforme
      mide sobre todo el contenido de A/T y declararía «cargada» a cualquier seed rica en
      A/T por pura composición. El criterio va **declarado, no citado**, la **semilla
      viaja con el resultado**, y la regla del percentil (empates a medias) va escrita.
      - Se calcula contra un **índice de 8-meros** construido en una pasada. Hay un test
        que exige que el índice y el barrido directo den **lo mismo**: si discreparan, el
        percentil no sería comparable con el conteo.
    - **CONTROLES biológicos en la misma corrida**: `miR-124-3p`, `miR-9-5p`, `let-7a-5p`,
      con sus seeds sacadas de `mature.fa` y **nunca escritas en el código** (regla 1, con
      un test que barre el fuente buscando literales de ADN). Su conteo es la referencia
      de qué significa «muchos sitios» — el valor esperado viene de la biología.
      **No se les da percentil**, y el motivo va escrito: un percentil se calcula contra
      la nula de **su propia composición**, así que el de un control contra nuestra nula
      no querría decir nada. Aportan **magnitud**, no posición.
    - **AUTOCONTEO sobre la propia diana** (`self_count`), esperado **1**.
  - **HALLAZGO del autoconteo, y no es un detalle**: **4 de los 10** del panel murino
    tienen un **segundo sitio de seed en el propio 3'UTR de Prnp** — `3utr:449` (núcleo en
    `3utr:464` y `1033`), `553` (`460`, `568`), `819` (`148`, `834`) y `1018` (`464`,
    `1033`). No es un fallo: es información que hay que tener **antes** de leer una
    cinética, porque el efecto de esas cuatro sobre su mensajero no es el de un solo
    sitio. Y **`449` y `1018` comparten el núcleo**, así que en este eje no son dos
    apuestas independientes. Los otros seis tienen uno solo. Está fijado con un test.
    - Un autoconteo de **CERO** también es anómalo, y hacia el otro lado: significa que
      esa hebra **no sale de esa diana**. Se dice con esas palabras.
  - **LAS TRES LIMITACIONES VAN EN EL RESULTADO, no al pie** (`LIMITATIONS`), y las tres
    llevan `direction = "sobrestima"`: sin ponderación por **conservación** (no tenemos
    alineamientos multiespecie, TargetScan sí: contamos sitios, no sitios probablemente
    funcionales), sin ponderación por **APA** (un sitio distal no está en todos los
    mensajeros de ese gen — lo sabemos por Prnp, con la fracción larga en 0,86, y aplica a
    los demás igual), y sin ponderación por **expresión** (un sitio en un gen que la
    neurona no expresa no cuenta; `expresion_cerebro.tsv` lo refinaría y hoy no existe).
    **Empujan todas en la misma dirección**, así que la conclusión es una sola y va
    pegada: **el número es un LÍMITE SUPERIOR** (`UPPER_BOUND_NOTE`). No se corrige con
    un factor: se dice.
  - **USO: DESEMPATE, NUNCA FILTRO** (`USE_NOTE`). Un percentil alto es motivo para
    preferir a otro entre dos que empatan, jamás para excluir a nadie — la **potencia**
    sobre la diana sigue mandando y esto no la predice. `OfftargetStore.verdict_for`
    **no puede devolver FAIL**: solo NOT_RUN o PASS, con un test que lo fija.
  - **El fichero se SUBE por el modal, y con su procedencia** (`Provenance`,
    `validate_upload`). Los seis campos —fuente, ensamblaje, tabla, **fecha de la tabla**,
    criterio de representante y versión— son **obligatorios** y su ausencia aborta: sin
    ensamblaje y sin fecha el conteo no es reproducible, que es la misma regla de la
    versión de miRBase y de la biblioteca de Dfam. La ruta de descarga (Table Browser de
    UCSC, **el ensamblaje de la especie que se esté analizando**, NCBI RefSeq, «3' UTR
    Exons») va **en la interfaz** (`ucsc_route(especie)` sobre `UCSC_ROUTE_TEMPLATE`),
    no en una conversación. El ensamblaje **se resuelve** contra
    `species.ucsc_assembly` y no va escrito dentro del texto: con `mm39` dentro, quien
    cargara conejo leía una instrucción correcta de principio a fin con el ensamblaje
    del ratón, y **no daba ningún error**.
  - **Validación al recibirlo, y rechaza**: que sea FASTA, que el alfabeto sea de ADN, el
    md5 declarado si lo hay, más número de secuencias y longitud total. Y la **auditoría
    de isoformas** (`IsoformAudit`), que son tres preguntas y no una:
    - **identificadores repetidos** — la salida de «3' UTR Exons» da un registro **por
      exón**, así que un 3'UTR troceado aparece varias veces: el conteo está inflado y se
      dice. Por eso este módulo tiene su **propio** parser de FASTA en vez de reusar el de
      `seed_load`, que **aborta** con un identificador repetido: aquí repetirse es un caso
      legítimo y esperado, y abortar escondería justo lo que hay que auditar.
    - **secuencias idénticas** — dos isoformas que comparten 3'UTR aportan sus sitios dos
      veces.
    - **varios transcritos por gen**, que es la pregunta de verdad y que **no se puede
      contestar sin un mapa transcrito→gen**: de un accession no se deduce el gen y aquí
      no se adivina. Sin mapa queda **NO COMPROBADO**, con esas palabras — y no haber
      podido comprobarlo **no es «no las hay»**. Es la misma lección del `.out` sin
      resumen.
  - **Almacén inmutable y ficha**, como los otros dos: nada se sobrescribe, repetir un
    `run_id` aborta, y el veredicto va **por hebra** — `offtarget_seed:guia` y
    `offtarget_seed:pasajera` son **dos filas** de la ficha y no existe un
    `verdict_for_candidate`. Con el veredicto viajan el percentil de las cuatro clases,
    el ensamblaje y la fecha de la tabla, el estado de la auditoría de isoformas y el
    aviso de límite superior.
  - **Persiste en el mismo log que los otros dos** (`store.corrida_offtarget`). La nula se
    guarda como **histograma**, no como 40.000 enteros: es exacto —el percentil se
    recalcula igual— y deja el `registro.jsonl` legible con `cat`, que es la razón por la
    que se eligió JSONL.
  - **Y hay DOS contadores del mismo suceso, atados con un test.** `seed_load.seed_load`
    sigue siendo el número comparativo de la **tabla** (tres clases, sin 6mer y sin
    percentil) y `offtarget` es el **frente**. Que convivan es útil —la tabla no quiere
    cuatro columnas más— pero dos contadores que discrepasen serían un fallo silencioso:
    la ficha diría una cosa y la tabla otra, las dos con pinta de medida. Hay un test que
    exige que **las tres clases compartidas den lo mismo** en los diez del panel; el
    `6mer` es exactamente lo que el contador viejo no veía.
- **Cada `NOT_RUN` dice CÓMO SE RESUELVE** (`obtencion.py`, `data/obtencion/*.toml`).
  La app decía qué fichero falta y no de dónde sale, así que el usuario lo preguntaba
  **fuera de la app**. Esa es la dependencia que esto rompe.
  - **Una ficha por frente, y es un FICHERO DE DATOS versionado**, no texto en el código:
    misma razón que el manifiesto — se lee con `cat`, se diffea, y no hace falta la app
    para consultarla. Nueve fichas con: qué pregunta responde el frente, el fichero
    exacto con el nombre que se espera, la fuente con URL, los **pasos concretos** con la
    opción de cada menú, qué metadatos anotar **y por qué**, el tamaño aproximado y cómo
    se valida al subirlo.
  - **Dos tests, en las dos direcciones**: un frente sin ficha hace fallar la suite, y una
    ficha **huérfana** también — documentación de algo que ya no existe engaña igual que
    la ausencia.
  - **Y la ficha SE ADAPTA A LA ESPECIE.** No vale decir «miRBase» cuando quien lee ha
    cargado conejo. Los marcadores se resuelven contra `species.Species`, y lo que esa
    especie **no tiene declarado** sale diciendo que no está declarado **y dónde se
    declara** — nunca deducido del nombre: `ocu-`, `oc-` y `ory-` son todos plausibles y
    sólo uno existe. Ese hueco sale **además como AVISO**, no enterrado en un paso, porque
    un paso largo se lee en diagonal. `Species` gana `ucsc_assembly` (mm39 / hg38),
    declarado como todo lo demás.
  - **Una ficha sin resolver NO se puede renderizar** y aborta: con marcadores dentro el
    texto miente a medias —`rmsk_{slug}.out` no es un nombre de fichero— y esos textos se
    copian.
  - Contenido de hoy: RepeatMasker (`Services → RepeatMasking`, DNA source con la especie,
    `tar file`, `email`) con el **`.tbl` obligatorio** y la demostración de por qué;
    miRBase (`Downloads` → `mature.fa`) con el **release**, porque renumera entre
    versiones; UCSC Table Browser con «3' UTR Exons» y la orden de **no filtrar isoformas
    a mano**; el BLAST que corre el usuario con el FASTA y el comando que da la app;
    **PolyA_DB v4** con las tablas `PAS Summary` y `PAS Expression`, las columnas
    `PSE_3'READS` y `AvgRPM_3READS` por su nombre, y el aviso de que **las coordenadas son
    GENÓMICAS y no se convierten con una resta**. El empalme del intrón declara
    `sin_fichero = true`: sus cuatro lecturas son de banco y conseguir más datos no lo
    cierra.
- **El informe es un DOCUMENTO, parcial o completo, en markdown + docx + pdf**
  (`informe_doc.py`, `docx_writer.py`, `pdf_writer.py`, `tools/informe.py`, botón en la
  página). **No son dos productos**: es el mismo documento en distintos grados de
  completitud, con `state` `PARCIAL`/`COMPLETO` derivado de los frentes. `Document`
  **aborta** si se declara completo con frentes abiertos — presentarlo así sería decir
  que se comprobó algo que no se comprobó.
  - **Escritos a mano con stdlib, y es una decisión, no una limitación.** `python-docx` y
    `reportlab` habrían necesitado autorización escrita (regla 6) y un informe no justifica
    una dependencia: un `.docx` es un ZIP con cuatro XML (`zipfile`) y un PDF de texto con
    las base-14 no incrusta nada (`zlib`). Lo que se gana es que el informe se genera
    donde corra el núcleo, sin instalar nada — que es justo lo que pide «autosuficiente».
  - **Siete secciones**: qué se analizó (longitud y md5 **juntos**), estado de los frentes
    con **qué falta y dónde conseguirlo**, frente por frente (qué mide, por qué importa,
    criterio y umbrales con su origen, fuente de datos con versión y md5, resultado, **y
    la ficha de obtención íntegra si está abierto**), tabla de candidatos con todas las
    columnas, fichas de los seleccionados, **limitaciones en sección propia** y
    procedencia.
  - **Las tres reglas de redacción son TESTS, no intenciones**:
    - **Ningún umbral sin justificar** (`justificacion.py`): cada uno declara `literatura`
      / `convencion` / `nuestro`, y hay un test que exige que **todo campo de
      `hard_filters.Thresholds`** tenga entrada — un umbral nuevo sin justificar hace
      fallar la suite. Los que **no tienen base medida** lo dicen expresamente y salen
      **juntos** en Limitaciones. El caso que obliga a la distinción es el flanco de
      **±10 nt** del eje estérico: no tiene base medida, la huella de CPSF/CstF es mayor,
      y ponerlo al lado de un GC 30-55 % sin distinguirlo le atribuye una precisión que la
      biología no tiene.
    - **Toda cifra comparativa con su referencia**: la tasa base junto a las colisiones de
      seed, el percentil junto a la carga de off-targets.
    - **`NOT_RUN` visible en el CUERPO**: hay un test que comprueba que aparece **antes**
      de la sección de limitaciones. Un `NOT_RUN` que sólo sale en un anexo se lee después
      de haber creído la tabla.
  - **El documento entero entra en el golden** (`tests/golden/informe_documento.md`, 588
    líneas), con la misma disciplina que el informe de texto y la ficha: se compara
    **entero**. La fecha va **fijada** en el generador — con la de hoy, el golden cambiaría
    cada día y el diff dejaría de significar nada. Hoy el golden es el **PARCIAL**, y eso
    también lo fija: el día que se cierre un frente, el diff lo enseña.
  - **Una tabla descuadrada ABORTA** (`Block.__post_init__`): una fila con menos celdas
    que cabeceras desplaza los valores a la columna de al lado, y eso no da ningún error
    — sólo un informe equivocado. Es el mismo tipo de fallo que el invariante de rango.
  - **Detalles de los dos escritores que importan al leerlos**: en el `.docx` las tablas
    son **tablas de verdad con bordes**; en el `.pdf` salen en monoespaciada con las
    columnas recortadas para caber, **y el recorte se marca con `...`** —un valor cortado
    sin marca es peor que uno que no cabe—. Lo que WinAnsi no tiene se sustituye por su
    equivalente ASCII con una tabla **declarada**, y el markdown y el `.docx` conservan el
    texto original. Hay un test que recorre la **tabla xref** del PDF y comprueba que cada
    desplazamiento apunta a su objeto: si uno está mal, el lector abre un PDF vacío y **no
    da ningún error**.
  - La página y `tools/informe.py` llaman a **la misma** función: si divergieran, el
    informe que se entrega no sería el que se revisa. Y no hay opción para pedir «el
    completo»: el estado lo deciden los frentes, y viaja **en el nombre del fichero**
    además de dentro.
- **Fuera de ratón: los valores por defecto que nadie avisaba dejan de existir.
  DECIDIDO (2026-08-26)**. Era el mismo patrón que `rmsk_mouse.out` conectado por rol —
  un valor que funciona callado y que sobre otra especie produce un resultado con la
  **forma correcta**. Un `txid10090` sobre una secuencia de conejo tiene que ser
  **imposible**, no improbable.
  - **`species.resolve()` es el ÚNICO origen** de los tres, con `species.mirbase_prefix()`
    y `species.taxid()`. Una especie sin el valor declarado **aborta** diciendo dónde se
    declara y qué pasaría si se dedujera: para conejo, `ocu-`, `oc-` y `ory-` son todos
    plausibles y sólo uno existe — filtrar con el equivocado da **cero colisiones**, que
    parece una buena noticia.
  - `blast.BlastParams.entrez_query` ya no vale `txid10090`: vale **vacío**, y generar la
    orden sin organismo **aborta**. `BlastParams.for_species(nombre)` es la vía.
  - `seed_scan.SeedParams.species_prefix` ya no vale `mmu-`: vale `None`, y `None` **no
    es** `""` — el primero es «nadie lo ha dicho» y el segundo «todas las especies del
    fichero, elegido a propósito». Son dos valores porque son dos cosas. `run_scan`
    resuelve el prefijo con la especie de **la corrida**, que ya venía por parámetro.
  - **La especie NO cuenta como «ajuste modificado»** en ninguno de los dos: es la
    identidad de la corrida. Si contara, toda corrida que no fuera de ratón saldría en
    rojo y el rojo dejaría de significar «alguien tocó esto».
  - `mirna.DEFAULT_PREFIXES` pasa a `()` = **indexar todo el fichero**. `("mmu-","hsa-")`
    dejaba fuera del índice a cualquier otra especie **sin avisar**, así que una guía de
    conejo salía limpia por no haber contra qué compararla. El filtro por especie es de
    quien **pregunta**, no de quien carga. Las cifras murinas no se mueven (1988 maduros,
    1593 seeds, 9,7 %); `HISTORICAL_PREFIXES` conserva el par con el que se calculó el
    19,1 %. Y «TODAS» ahora significa de verdad todas: **75 %** sobre 69.020 maduros, que
    es la mejor demostración de por qué el filtro de especie no es cosmético.
  - **Los alias van DECLARADOS** (`species.ALIASES`): `raton`/`ratón`/`Mus musculus` →
    `mouse`, `humano`/`Homo sapiens` → `human`. Sin ellos, la corrida murina se habría
    marcado a sí misma como lista de otra especie.
- **`CORE_ABUNDANT` fuera de ratón: el veredicto SALE, marcado. DECIDIDO (2026-08-26),
  opción (a)**. `CoreMember.matches` quita el prefijo, así que la lista casa igual y el
  filtro corre — pero eso no la convierte en una lista de esa especie. **Excluir por una
  lista prestada es defendible; no decirlo, no.**
  - Tres estados, no dos: la especie del diseño **coincide** con la de la autorización
    (limpio), es **otra declarada** (`LISTA_DE_OTRA_ESPECIE`, con el aviso en el motivo
    del FAIL y diciendo que **puede acertar** — let-7, miR-124 y miR-9 son abundantes en
    cerebro de casi cualquier mamífero), o **no está declarada**
    (`ESPECIE_NO_DECLARADA`: no se ha podido comprobar, y eso no es que coincida).
  - `tile_utr` gana `species`, **vacía por defecto y no «raton»**: poner ratón por defecto
    es exactamente el patrón que se está quitando.
- **`specificity.TAXIDS` deja de ser una LISTA BLANCA** (`specificity.taxid_for`). La
  validación pasa a ser «esta especie tiene taxid **declarado**», no «está en una lista de
  dos» — que cerraba el frente a ratón y humano por una razón que no es del frente.
  Añadir una especie a `species.SPECIES` la habilita sin tocar `specificity`, y hay un
  test que lo comprueba añadiendo una y quitándola.
- **`blocks.PIECES` no se parametriza — y la app lo DICE** (`blocks.vector_applies_to`,
  `presentation.vector_note`). Las 12 piezas son el plásmido concreto de PrP murino, no
  un valor por defecto. Con otra especie, `block_rows` devuelve la lista **vacía** y la
  página saca en rojo qué NO se emite y por qué: **módulo NheI-SacI, cassette MluI-AgeI,
  hoja de pedido y control sin intrón**. Emitirlos con las piezas murinas daría fragmentos
  con la forma correcta y la secuencia equivocada, que es **peor** que no darlos. Para
  otra especie hace falta OTRO plásmido, y entonces se sustituye.
- **La tabla de sitios con UNA COLUMNA POR FRENTE** (`presentation.site_table_rows`,
  `front_columns`). Es la vista que impide que vuelva a pasar lo de `offtarget_seed`: un
  frente sin columna no se ve, y **lo que no se ve no existe**.
  - **Las columnas se DERIVAN de `blocking_fronts`, no se listan a mano**, así que un
    frente nuevo aparece solo. Listarlas habría reproducido el fallo original un nivel más
    arriba.
  - Salen **todos los sitios elegibles**, no sólo los diez del panel: un sitio que no está
    en la selección sigue teniendo veredictos, y esconderlo deja al lector sin poder
    discutir la selección.
  - Un frente sin correr sale **`NOT_RUN` en su celda**, nunca vacío.
  - La selección se puede cambiar a mano y los avisos se recalculan con lo marcado.
- **Dos avisos rojos, y son DOS EJES que no se cubren** (`presentation.selection_warnings`):
  la **distancia** en el 3'UTR (por debajo del espaciado mínimo) y el **parecido de seed**
  (núcleo de 6 nt compartido). El espaciado **no ve** el segundo — mide nucleótidos, no
  seeds — y por eso `3utr:449` y `3utr:1018`, que están en extremos opuestos del 3'UTR y
  pasan el espaciado holgadamente, avisan igual.
- **El `.gb` es la entrada preferente, y sin él lo que cuelga de la frontera sale
  `NO_FIABLE`** (`presentation.anatomy_reliability`). Con `.gb` —o con un fixture
  verificado por md5— la frontera la declara una **anotación**; con el CDS tecleado o con
  «lo que subo YA es el 3'UTR», la declara una **persona**. No es lo mismo:
  - **Se acepta igual** —hay que poder trabajar— pero lo que deja de ser fiable va
    **nombrado uno a uno**, no como «algunas cosas»: tercios, la etiqueta de región de
    cada ventana, las cuotas por tercio, la distancia de cada señal de polyA al extremo 3'
    y qué señales cuentan como terminales.
  - En la tabla, la columna `tercio` sale literalmente **`NO_FIABLE`** en vez de un valor
    que parece un dato. Sin frontera fiable, «tercio medio» no se refiere a nada.
  - El motivo dice **qué pasaría**: un off-by-one ahí corre el 3'UTR entero y con él todos
    los tercios, **sin dar ningún error**.
- Los umbrales ajustables viven en `hard_filters.Thresholds`, con los valores
  verificados como defecto. Añadir un umbral nuevo significa añadirlo ahí y pasarlo,
  nunca leerlo de la UI.
- Implementado: pasos 0 (fixtures + checksum), 1 (anatomía resuelta por tres vías),
  2 (enmascarado con rmsk real), 3 y 15 (tiling, sitios y selección), 4-8 (filtros de
  ventana, incluida la asimetría), 9 (polyA como anotación de cinco campos), 10 (seed en
  dos preguntas: colisión y carga), 12 (especificidad + transgén), 13 (accesibilidad) y
  14 (bloques conservados), más la horquilla, el módulo de 149 nt, el APA con dato
  medido y la tabla comparativa. El resto, en `docs/pipeline.md`.

- **LA PRIMERA PANTALLA GUIA, Y TODO SE SUBE POR ELLA. DECIDIDO (2026-08-26)**
  (`deposito.py`, `species.required_files`, `presentation.steps_rows`). El criterio de
  aceptacion es el de siempre: **alguien que no haya estado en estas conversaciones tiene
  que poder abrir la app y llegar a un informe sin abrir una terminal ni conocer el arbol
  de directorios.** Cuatro cosas lo rompian y las cuatro se arreglan en la interfaz.
  - **1. Desplegable de especies, y SIN valor por defecto** (`presentation.species_options`,
    `species_default` devuelve `None`). Solo las declaradas en `species.SPECIES`, con su
    nombre cientifico completo — «raton» es un alias del proyecto y no identifica nada
    fuera de el. `modelo` como valor inicial era **peor que vacio**: parecia configurado y
    dejaba la colision de seed y la especificidad rotas sin decir por que.
    - Hay una opcion **explicita** «otra especie (no declarada)», y explica **que frentes
      quedan cerrados y como se declara** (`HOW_TO_DECLARE`: los tres identificadores, en
      `species.SPECIES`, verificados y nunca deducidos del nombre). Se explica **al elegir
      la opcion**, antes de teclear ningun nombre: la pregunta que se contesta es «¿me
      sirve esta app para mi especie?», y contestarla despues es no contestarla.
  - **2. `species.required_files` es la vista POR FICHERO, y la UNICA fuente de los
    nombres.** `fixture_report` —la vista por FRENTE— se **deriva** de ella. Tenerlas
    como dos listas independientes seria el patron de los dos contadores que discrepan:
    la barra lateral diria que falta un fichero y la tabla de frentes diria que no, las
    dos con pinta de medida. Cada fila trae rol, nombre ya resuelto para la especie, que
    frentes cierra, el **hermano obligatorio** (el `.tbl` de un `.out`) y la ficha de
    obtencion que dice de donde sale.
    - **El nombre lleva la especie donde importa**, y el raton conserva los que ya estan
      en el manifiesto (`mature.fa`, `rmsk_mouse.out`, `aav_casete.fa`): el sufijo empieza
      donde empieza el problema, no antes, porque renombrarlos dejaria de detectar los que
      hay.
    - **`aav_casete.fa` pasa a llevar especie fuera del raton.** Es pAAV con PrP
      **murino**, y `blocks.vector_applies_to` ya decia que para otra especie no se
      parametriza — se SUSTITUYE. Sin sufijo, el casete murino contaba como presente para
      un conejo y su frente salia cerrado con el vector equivocado.
    - **Y el `.out` a solas deja de abrir el frente de repetitivos.** Esa tabla decia
      «disponible» con solo el `.out`, y `resources._rmsk` abortaba sin resumen: dos
      contadores que discrepaban. Manda el estricto, con la demostracion de md5 detras.
  - **3. Todos los ficheros se suben por la interfaz** (`deposito.accept_upload`, panel en
    la barra lateral). Antes unos se subian y otros habia que **depositar** en
    `data/reference/`, que es un directorio del repositorio: quien no conoce ese arbol
    —que es exactamente el usuario para el que se escribe esto— no podia usar la app. Los
    que ya esten ahi se **detectan solos** y salen como presentes; depositarlos deja de
    ser necesario.
    - **La validacion la hace el cargador de verdad**, el mismo que usa el filtro. Un
      fichero que pasara una validacion «ligera» y fallara despues seria peor que no
      validarlo: la barra lateral diria «presente» y el frente saldria NOT_RUN sin motivo.
    - **Si la validacion falla no se escribe nada**: ni el fichero ni la linea del
      manifiesto. Se escribe a un provisional al lado, se valida, y solo entonces se
      renombra — hay test de las dos cosas.
    - **El md5 se calcula del fichero, nunca se declara**, y la entrada va al manifiesto
      (`manifest.update_manifest_text` / `register_entry`). El manifiesto sigue siendo
      texto y sigue versionado: subir por la interfaz se ve en el `git diff` igual que
      editarlo a mano, y los **comentarios de cabecera sobreviven** —explican los dos
      checksums, y perderlos al subir un fichero borraria la unica advertencia que evita
      copiar un md5 en el sitio del otro—. Una cabecera corta se **ensancha** rellenando
      en vacio, que es la verdad; abortar dejaria sin subir ficheros justo a quien no
      puede editarlo.
    - **Un `.out` y su `.tbl` llegan de uno en uno**, asi que del `.out` a solas solo se
      comprueba la FORMA (`masking.check_out_shape`, que dice expresamente que **no**
      comprueba la especie de la biblioteca) y del `.tbl` la especie y la longitud de la
      consulta (`masking.check_summary`), que es para lo que existe. Con los dos delante
      se valida la corrida entera. Mientras falte uno, el frente **no se abre** y el
      resultado de la subida **nombra** lo que sigue faltando.
  - **4. La casilla «Usar los de `data/reference/`» DESAPARECE**
    (`deposito.WHY_NO_GLOBAL_TOGGLE`). Una opcion cuyo unico efecto posible al desmarcarla
    era dejarlo todo en NOT_RUN sin decir por que no es una opcion: es una trampa. Si un
    fichero esta y es valido, **se usa**.
    - Ignorar uno a proposito sigue siendo posible, pero **por fichero y con el motivo
      escrito** (`deposito.Ignored`, motivo obligatorio, y `load_from_manifest(ignore=…)`).
      El motivo **viaja al veredicto**: sin el, «se decidio no usarlo» y «no estaba» serian
      el mismo NOT_RUN mudo. Pedir ignorar un fichero que no se iba a usar **aborta** — un
      motivo escrito para una decision que nadie tomo ensucia el informe.
  - **5. La pantalla va en pasos numerados**, y desde 2026-08-27 son **CINCO**: los
    ficheros de referencia se partieron en sus **dos momentos** (bloque siguiente).
    **No bloquea**: un frente abierto deja los candidatos en `INCOMPLETE`, que es
    informacion, no un veto, y el paso 4 lo dice con esas palabras.
  - **El manifiesto se carga cuando se diseña, no al pintar la pantalla.** La presencia de
    un fichero es un listado de directorio y es barato; conectar `mature.fa` son 5,6 MB en
    cada rerun de Streamlit. La pantalla no promete nada que no vaya a cumplir: dice que
    frentes se pueden cerrar, no que ya esten cerrados.

- **LOS FICHEROS DE REFERENCIA SON DOS MOMENTOS, NO UNO. DECIDIDO (2026-08-27)**
  (`presentation.WHY_TWO_MOMENTS`, `design_files_rows`, `refinement_panel`,
  `_panel_refinamiento` en la página). El paso 3 pedía **los siete frentes** antes de
  diseñar, como si todos sirvieran para lo mismo. No sirven, y presentarlos juntos
  **afirmaba una dependencia que no existe**: *no puedo empezar hasta reunirlo todo*.
  - **Momento 1 — obtener candidatos** (paso 3). Le hace falta la secuencia y su
    anatomía, y nada más. **Hoy la lista está VACÍA**, y eso NO se declara: hay un test
    que **corre el diseño con el directorio de referencia vacío** y comprueba que salen
    candidatos (287 elegibles con el ratón). El día que algo pase a hacer falta para
    tilar, el test lo dice y el paso 3 lo enseña solo.
  - **Momento 2 — refinar y descartar** (paso 5, **después** del botón y **debajo de los
    resultados**). Estos ficheros no cambian QUÉ candidatos salen: cambian qué veredicto
    lleva cada uno y **cuáles acaban cayendo**. La frase que abre la sección va en la
    propia sección y no en un tooltip: «**Los candidatos ya están. Estos ficheros no
    cambian cuáles son, cambian cuáles sobreviven.**»
  - **Y esa frase está MEDIDA, no afirmada.** El conjunto de elegibles con cualquier
    fichero de referencia es un **SUBCONJUNTO** del que sale sin ninguno —**ninguno
    inventa un candidato**— y lo que quita cada uno está contado: PolyA_DB **17** (que
    es exactamente `measured_promotion_cost`), `mature.fa` **2**, la máscara murina
    **0** y el casete **0**. Ese cero de la máscara es un hecho **del 3'UTR del ratón**
    —su único repetitivo, el `(CTC)n`, está en el CDS— y no una propiedad del fichero:
    sobre el humano la misma máscara tumba cinco. Está en `tests/test_dos_momentos.py`.
  - **Cuatro estados, constantes, con leyenda al principio**: `CERRADO` (verde), `FALTA`
    (ámbar), `OPCIONAL` (gris) y `NO USADO` (gris claro). El color lo pone
    `presentation.REFINEMENT_STATES`, no la página: un color elegido en la página es una
    decisión sin test (regla 6).
    - **`NO USADO` es un estado propio y existe por un fallo real** (errata nº 30):
      `apa_medido.tsv` salía en el mismo ámbar que `refseq_rna.fa` con
      `polya_db_mouse.tsv` ya en el depósito. Uno no hace falta y el otro sí. La fila
      dice **qué fichero** cierra su frente, por su nombre.
    - **`OPCIONAL` no puede parecerse a `FALTA`**: `expresion_cerebro.tsv` refina una
      ponderación y **no bloquea nada**, así que va en otro grupo y con otro color.
  - **El orden es por IMPACTO, no alfabético**: primero lo que cierra un frente, luego lo
    opcional, y dentro de cada grupo **lo resuelto abajo**. Alfabético pone
    `aav_casete.fa` delante de `transcriptoma_3utr.fa` sin ninguna razón, y quien entra
    aquí entra a saber qué le falta. El frente **viaja en la fila** ahora que ya no se
    agrupa por frente: un fichero sin frente visible es un fichero del que no se sabe
    para qué sirve.
  - **Densidad**: lo resuelto se colapsa a **una línea CON SUS BOTONES** —colapsar es no
    ocupar sitio, no dejar de poder ver, reemplazar, borrar o descargar— y sólo se queda
    expandido lo que falta.
  - **Contador en el encabezado**, `N de 7 frentes cerrados`, con barra. Con el ratón y
    lo que hay son **5 de 7** (eran «4 de 7» y la cifra estaba mal: ver errata nº 30).
  - **Cada fila que falta dice QUÉ PASA si no llega**, con las palabras de siempre: su
    frente se queda en `NOT_RUN` y los candidatos en `INCOMPLETE`. Una opcional dice lo
    contrario —nada se queda sin correr— y una `NO USADO`, que conseguirla no cambiaría
    ningún veredicto. A un fichero que YA está no se le hace la pregunta: ahí el campo
    vacío es `NO_APLICA`, no un hueco.
  - **El depósito sigue siendo alcanzable ANTES de diseñar**, pero como acceso
    **secundario**: un expander **colapsado** y titulado «no hace falta ninguno para
    diseñar» (`_deposito_opcional`). El paso 5 sólo aparece después de haber diseñado, y
    ésa es la decisión; dejar el gestor *sólo* ahí dentro le quitaba la única vía de
    subir un fichero a quien acaba de abrir la app, y este proyecto tiene decidido que
    **todo se sube por la interfaz**.

- **EL FRENTE DEL APA LO CIERRAN DOS FICHEROS, Y NINGUNO DE LOS DOS ROLES SOBRA.
  REVISADO (2026-08-27)** (`apa.APA_ARE_TWO_FILES`). `species.fixture_report` tenía ese
  frente con **`available=False` escrito a mano**, de cuando la tabla vivía en el código:
  el contador decía 4 de 7 y eran 5, y `apa_medido.tsv` salía en ámbar con
  `polya_db_mouse.tsv` ya dentro. Errata nº 30; ahora se **deriva**.
  - **No son dos formatos del mismo fichero.** `polya_db_<especie>.tsv` es PolyA_DB **en
    crudo** —coordenadas GENÓMICAS, clase declarada, PSE y AvgRPM—, hay que anclarlo por
    los cuatro puntos y de él sale la **promoción por medida** y el techo **por tramos**.
    `apa_medido_<especie>.tsv` son posiciones **YA convertidas** a coordenadas de 3'UTR
    con su fracción; no ancla nada y no promueve ninguna señal: alimenta
    `apa_assessment`. Con cualquiera de los dos el frente está cerrado.
  - **Y el segundo SÍ se va a usar en ratón**: su caso es exactamente el fichero
    pendiente —**3'-end seq de cerebro murino**—, la medida *en nuestro tejido*, que
    PolyA_DB no puede dar porque su 0,86 es de **todos** los tejidos y por eso se declara
    como límite inferior.
  - **RECTIFICADO por Joaquín Castilla (2026-08-27), y anotado con su nombre a petición
    suya**: «no era un residuo... son dos preguntas, y el segundo tiene un uso real
    pendiente». Va con su nombre por la misma razón que la predicción refutada de la
    carrera de A: si sólo se anotan las rectificaciones ajenas, el registro deja de ser
    un registro y pasa a ser un argumento.
  - **LO QUE NO SE CALLA**: hoy los dos producen un techo de knockdown por caminos
    **independientes** —`apa_assessment` no mira la tabla de PolyA_DB y `resolve_measured`
    no mira los sitios convertidos— y **nada obliga a que coincidan**. Es el patrón de los
    dos contadores del mismo suceso, el que ata un test entre `seed_load.seed_load` y
    `offtarget`. Aquí ese test **no se puede escribir todavía**: el segundo fichero no
    existe y fabricarlo sería inventarse la medida (regla 5). **El día que llegue el
    3'-end seq, lo primero es cruzar los dos techos, no enchufarlo.**
  - **Y LA DIRECCIÓN ESPERADA VA ESCRITA** (`apa.EXPECTED_DIRECTION`, emitida en el
    informe). **Si discrepan, NO es un fallo a reconciliar: es el dato.** PolyA_DB
    promedia **todos** los tejidos y las neuronas **alargan** los 3'UTR, así que lo
    esperable es que el techo de cerebro sea **MAYOR** que 0,86:
    - **cerebro > PolyA_DB → CONFIRMA el modelo.** El 0,86 se declaró como límite
      inferior y el dato del tejido lo mejora, que es lo que se anticipó.
    - **cerebro < PolyA_DB → PARAR.** Contradice la dirección conocida del sesgo: antes
      de mover ningún veredicto hay que buscar la causa —anclaje, md5 del 3'UTR, o que
      una de las dos tablas no sea del gen que dice.
    **Y no se promedian.** Sin la dirección escrita, quien vea un número distinto de 0,86
    lo tratará como un error y hará la media, que es perder justo la información que la
    discrepancia lleva dentro. Misma clase de frase que «rebaja, no descarta».

- **LA INTERFAZ SE SIRVE DESDE EL HUB, EN `/shmir`. DECIDIDO (2026-08-26)**
  (`apps/shmir/` en el hub — proceso hijo + proxy inverso). Hasta ahora esta interfaz
  **no estaba montada en ningún sitio**: había que arrancarla a mano con `streamlit run`,
  y lo que sí estaba desplegado era la operación «Diseñar shmiRs» de Batchwork, que llama
  al **CLI** y es otra cosa —por lotes, sin ficheros de referencia y sin modales—.
  - **TODO VA EN shmir-design; BATCHWORK NO SE TOCA. DECIDIDO (2026-08-26).** Lo nuevo
    —el cuarto modal incluido— entra **sólo aquí**. La operación «Diseñar shmiRs» de
    Batchwork se queda como está y se **desmantelará** más adelante, cuando esta interfaz
    cubra de verdad lo que aquella hace; hasta entonces no se le añade nada ni se duplica
    nada en ella. Eso cierra la pregunta de si había que integrar el modal en los dos
    sitios: no.
  - **Los dos frentes conviven MIENTRAS TANTO, y no hacen lo mismo**: Batchwork es el
    atajo por lotes (subes FASTA, sale un ZIP); `/shmir` es el interactivo. Lo que NO se hace es
    duplicar la lógica en los dos: esa es la trampa que obligó a crear `resolve.py`, con
    la anatomía teniendo una versión en el CLI y otra en la interfaz que daban resultados
    distintos sobre el mismo mRNA.
  - **El mensaje de fallo NO interpreta.** Enseña las últimas líneas de la salida del
    proceso **tal cual**, y una pista sólo cuando la propia salida la nombra
    (`process.diagnose`). Antes se pegaba «comprueba que Streamlit está instalado» a TODO
    fallo, y el primero de producción fue un conflicto de configuración con Streamlit ya
    importado y corriendo: la página mandaba a mirar el sitio equivocado. Un diagnóstico
    **equivocado** cuesta más que ninguno — la misma lección que el «Alu 0 %» obtenido sin
    buscar Alu.
  - **Hay un TEST DE HUMO que levanta la interfaz de verdad**
    (`test/shmir.smoke.test.js`, en el hub): arranca el proceso, pide la página por el
    proxy y **abre el WebSocket CON cabecera `Origin`**. Existe porque hubo 2.767 tests en
    verde y la app no abría — se miraban los argumentos y las funciones del proxy, no el
    resultado. Y la cabecera no es un detalle: la comprobación anterior usaba una petición
    cruda, que NO manda `Origin`, así que pasaba mientras el navegador recibía un 403.
    **Un cliente que no se parece al real no prueba nada.** Comprobado que el test falla
    si se quita la reescritura del Origin.
  - **`SHMIR_REFERENCE_DIR`: el directorio de referencia de TRABAJO se declara**
    (`trabajo.py`). Son dos sitios que hasta ahora eran uno — el **origen versionado**,
    que llega con el código, y el **directorio de trabajo**, donde el panel escribe lo que
    se sube y el manifiesto se actualiza. En local coinciden y está bien. En un servidor
    no pueden: el sistema de ficheros de la imagen es efímero, así que todo lo subido
    desaparecería en el siguiente despliegue y el único síntoma sería un frente volviendo
    a salir NOT_RUN. Y `manifest.tsv` está versionado, así que escribirlo dentro de la
    imagen deja el árbol de trabajo sucio contra el siguiente despliegue.
    - Sin declarar, es **el del paquete**: en local no cambia nada, que es la condición
      para que esto sea aceptable. Una ruta **relativa aborta** — dependería de desde
      dónde se arranque el proceso.
    - **La siembra no pisa nada**, y va en los dos sentidos: un fichero subido manda sobre
      la copia que trae la imagen (al revés, un redespliegue borraría el bueno), y el
      `manifest.tsv` de trabajo lleva los md5 de lo subido, así que pisarlo con el
      versionado es perder justo la procedencia que el manifiesto existe para conservar.
    - Cuando el de trabajo NO es el del paquete, **la interfaz lo dice** con la ruta
      delante: quien sube un fichero tiene que saber dónde ha ido a parar.
  - **Streamlit sigue siendo una dependencia SOLO de la interfaz.** El núcleo y los CLI
    son stdlib pura y funcionan sin ella; lo que cambia es que ahora el hub la instala en
    su imagen porque sirve esa interfaz. La autorización escrita de `docs/dependencias-autorizadas.md`
    no se toca: sigue siendo opcional y sigue sin estar en el núcleo.

- **EL CUARTO MODAL: la unidad de analisis NO es el candidato** (`introns.py`,
  `intron_folding.py`). Los otros tres preguntan sobre una guia de 22 nt; este pregunta
  sobre el **cassette montado** —intron completo, con su modulo dentro, con la guia y la
  pasajera de ESE candidato, y con contexto exonico a los dos lados—. Asi que la unidad
  es el par **candidato x intron**: diez candidatos y tres intrones son **treinta
  consultas**, no una lista de diez.
  - **El registro de intrones es de primera clase**, y eso es una consecuencia de diseño
    de que este modal exista, no un adorno. Tres entradas con tres estados DISTINTOS:
    - `mvm_actual` — **disponible**. Se ensambla de `blocks.PIECES`; nadie lo teclea. El
      intron VACIO —el del parental— mide **82 nt**.
    - `quimerico_cmv_globina` — **no aportado**, `NOT_RUN` visible y con ficha. Se extrae
      de un plasmido comercial del laboratorio (familia pAAV-MCS), de un `.dna` o un
      `.gb`, y **no se reconstruye de memoria**: es la errata nº 5 esperando a repetirse.
      Al cargarlo, la app localiza los cuatro elementos POR SECUENCIA y los declara.
    - `mvm_sin_criptico` — lo **diseña la app**, derivado del primero. Es una **PROPUESTA**
      y pasa por el mismo modal que las demas antes de ir a sintesis.
  - **Los cuatro elementos se DERIVAN; el punto de ramificacion NO es un dato.** Donante
    (`GT`), aceptor (`AG`) y tracto de polipirimidinas **contiguas** salen de la secuencia
    sin ambiguedad y, si no estan, se aborta. El punto de ramificacion sale como
    `CANDIDATO`: `YURAY` es un criterio **declarado como parametro, no una cita**, y
    pueden caber varios — si caben, salen todos y no se elige por nuestra cuenta. Ninguno
    o varios NO es «no lo hay».
    - Sobre el MVM: donante `GT` en 1-2, aceptor `AG` al final, **9 pirimidinas
      contiguas** (`CTTTTTTTC`) y **UN solo** YURAY (`TAATT`). El punto de ramificacion
      vive dentro de `MVM3`, asi que viaja con el cuando se mete el modulo.
  - **El suelo de 80 nt aborta, y se dice DONDE MUERDE.** Con el modulo de 149 nt dentro
    ese limite es **inalcanzable**, asi que sobre el intron terapeutico no protege de
    nada: vale para el vacio (82, pasa por dos) y para los intrones que vengan, que
    pueden ser mucho mas cortos. Decir que protege algo que no puede pasar seria peor que
    no ponerlo.
  - **La accesibilidad estructural va por FUNCION DE PARTICION, no por la estructura de
    MFE** (`folding.unpaired_probabilities`). No es un detalle: la de MFE es **una**
    estructura, asi que cada posicion sale apareada o no y el resultado es un 0 o un 1
    **disfrazado de probabilidad**. Con MFE los seis candidatos del panel daban donante
    1,00 y aceptor 0,00 los seis — un numero que no distingue nada, que es exactamente lo
    contrario de lo que este analisis existe para hacer.
  - **HALLAZGO, y las dos mitades van juntas o ninguna** (medido 2026-08-26):
    - Sobre el panel murino, los **seis** candidatos dan **el mismo** perfil —donante
      **0,89**, ramificacion **0,29**, aceptor **0,84**— y solo cambia la energia. O sea:
      **en el intron MVM la guia NO mueve la accesibilidad de los tres elementos**; la
      deciden los extremos del propio intron. Este eje **no discrimina** entre estos seis,
      y venderlo como desempate seria dar por criterio algo que da el mismo numero a todos.
    - **Pero eso no es que sea ciego**, y hay que poder distinguirlo: un modulo
      COMPLEMENTARIO al extremo 5' del intron lleva el donante de **0,89 a 0,00**. El
      analisis cazaria una guia que secuestrara un elemento; lo que dice el primer hecho
      es que ninguna de estas seis lo hace.
    - Los dos estan fijados con test. **Sin el control adversario, «todos iguales» y «no
      mide nada» serian el mismo resultado**, y es la misma leccion que el `.out` sin
      resumen.
  - **`GTGAGCG` esta en el ANDAMIO, no en los contextos**: son los ultimos 7 nt de
    `SGEP_SCAFFOLD.flank5` (`TGCTGTTGACA|GTGAGCG`). Romperlo **no es tocar un espaciador**
    — muta el andamio verificado contra la publicacion — asi que toda construccion con
    `mvm_sin_criptico` deja de llevar miR-E verificado y sale MARCADA en toda la salida,
    igual que un cassette con espaciadores de novo.
  - **Las fichas de obtencion documentan DOS familias, no una**: los frentes y los
    intrones que faltan. Un intron que no tenemos es un `NOT_RUN` como cualquier otro y
    tiene que decir como se resuelve. Los dos tests —ninguno sin ficha, ninguna ficha
    huerfana— cubren las dos.

- **EL CUARTO MODAL: prediccion de sitios de splicing** (`spliceai.py`,
  `splice_store.py`, `intron_design.py`, modal en la pagina). Cierra el frente
  `empalme_sitios`, que ahora son **diez** frentes.
  - **SpliceAI NO fue entrenado para esto, y eso manda sobre todo lo demas.** Se entreno
    sobre secuencia genomica **humana** con ventana de **10.000 nt** para predecir el
    efecto de **variantes**; un cassette de AAV no se le parece. Consecuencias, y van
    **ANTES del boton**, no al pie:
    - las puntuaciones **absolutas no son interpretables** y **no hay umbral que
      aplicar**. Cualquier corte que se pusiera seria inventado;
    - solo vale la comparacion **RELATIVA contra un referente INTERNO**: el donante
      legitimo del mismo intron **en la misma corrida**. Es el mismo criterio con el que
      ya se descartaron los aceptores cripticos —su tracto de pirimidinas contra las
      nueve del legitimo— y funciona por la misma razon: el veredicto no depende de
      ningun umbral traido de fuera;
    - **un legitimo de cero ABORTA** en vez de dividir: sin referente no hay nada.
  - **El umbral relativo (5 %) va DECLARADO como parametro y no citado.** No decide
    nada: solo evita que la tabla se llene de ruido. El absoluto sigue sin existir.
  - **LA ORDEN DE SpliceAI NO SE INVENTA.** Este proyecto no ha verificado su
    invocacion, asi que `LocalCommand` la **recibe** y aborta sin ella — igual que
    `blast.RemoteApi` con su endpoint. Hay un test que lee el fuente y comprueba que no
    hay ni un `http`. Lo que si define este modulo es el **formato del resultado que
    acepta**, que es nuestro.
  - **Validacion al subir, POR md5 y por nombre**: cada construccion tiene que ser una de
    las que genero esta corrida y su md5 tiene que cuadrar. Un resultado de otra corrida
    NO entra aunque encaje de forma — es el fallo del CSV de miRarchitect. Un fichero con
    solo cabecera tambien se rechaza: cero sitios y «no llego a correr» son cosas
    distintas y ese fichero no las distingue.
  - **El `GTGAGCG` sale POR SU NOMBRE**, aunque no sea el mejor criptico: es el conocido
    y el motivo por el que existe este modal. Y si el resultado no trae ninguna fila para
    su posicion, se dice **«sin puntuar»** — que no es «no puntua».
  - **LA COLUMNA COMPARATIVA es lo accionable** (`exclusive_rows`): que guias introducen
    cripticos que las **otras no**. Si nueve dan un perfil limpio y una no, esa se
    cambia. Se compara **entre construcciones del mismo intron**: mezclar intrones daria
    «exclusivos» que solo dicen que los intrones son distintos, que ya se sabe.
  - **LA VENTANA DE CONTEXTO viaja con cada consulta, y si es poca SE DICE.** Sin casete
    lo unico que hay son las piezas `exon5`/`exon3`: **5 nt por lado**, que para un
    modelo entrenado con 10.000 es esencialmente ninguno — y `context_note()` lo dice con
    esas palabras. Con `aav_casete.fa` cargado el contexto sale de **secuencia real**
    (hasta 3178/2069 nt) y **pedir mas del que hay no lo inventa**: se da lo que hay
    (regla 1). Dos corridas con contextos distintos **no son comparables**, y
    `context_note` aborta si las construcciones de una misma corrida no lo comparten.
  - **`verdict_for` solo puede dar NOT_RUN o PASS**, como la carga de off-targets, y el
    veredicto va **por PAR candidato x intron** — colapsarlo por candidato perderia justo
    lo que se quiere comparar: el mismo modulo dentro de dos intrones distintos.
  - **`mvm_sin_criptico` lo DISEÑA la app** (`intron_design.py`), con **autorizacion
    escrita y acotada** que cubre **dos cosas**: una sola base del `GTGAGCG` y los
    espaciadores de 20-30 nt. Nada mas.
    - **OJO: `GTGAGCG` esta en el ANDAMIO.** Son los ultimos 7 nt de
      `SGEP_SCAFFOLD.flank5`, asi que romperlo **muta el andamio verificado contra la
      publicacion** — no es lo mismo que generar un espaciador. Toda construccion que
      salga de ahi sale **MARCADA** en toda la salida.
    - **Dos metricas y ninguna sola basta**: cuanto degrada el contexto de donante (un
      conteo **declarado**, y se dice expresamente que **NO es SpliceAI** — el numero de
      verdad sale del modal) y si el 97-mero **sigue plegando como en SGEP**.
    - **MEDIDO (2026-08-26)** sobre el andamio real y la guia de `3utr:60`: de las **21**
      alternativas, solo **4** conservan el plegado; de esas, **DOS EMPATAN**
      (`GTGCGCG` y `GTGTGCG`) y **la app NO elige** — lo decide quien lee, igual que la
      posicion 1 de la pasajera. Y `GTAAGCG` pliega bien y **aun asi no es elegible**
      porque hace el contexto **mas** canonico: romper el motivo no es degradarlo, y sin
      la primera metrica esa se colaria.
    - **Sin ViennaRNA no se propone ninguna** y sale `NOT_RUN`: elegir «por lo que baja
      el criptico» sin comprobar el plegado es exactamente el fallo de la tabla por
      terminacion que este proyecto ya cometio con la pasajera.
    - **Los filtros de los espaciadores son SATISFACIBLES**, y hay un test que lo mide:
      pasan cerca del **2 %** de 200.000 sorteos. Un filtro que no puede pasar nadie es
      PEOR que no tener filtro — parece que comprueba algo y lo que hace es vaciar la
      piscina. Los que mas rechazan son los propios de este intron (`GT` y `AG` en
      contexto utilizable), que es lo esperado.
  - **UN FALLO QUE CAZO EL DIFF DEL GOLDEN, y es del tipo peor**: `informe_doc` sacaba la
    fuente de cada frente con `.get(nombre)`, y `None` **ya significaba «de banco»**. Asi
    que el frente nuevo heredo en silencio el texto «este frente no se contesta con
    datos, sino en el banco» — **plausible y falso**, sobre un frente que si se cierra con
    un fichero. Ahora un frente sin declarar **ABORTA** diciendo donde añadirlo
    (`BENCH_FRONTS`, `UPLOADED_FRONTS` o `_FRONT_SOURCE_ATTR`). Y su criterio tambien
    mentia a medias: decia «no tiene umbral numerico» de un frente que si tiene uno,
    **relativo** — que es todo el punto. Los dos textos los cazo LEER EL DIFF, que es
    para lo que el golden existe.

- **LA PERSISTENCIA, CONECTADA (2026-08-27)** (`trabajo.projects_dir`, `store.py`,
  la sección de persistencia de `presentation.py`, `_panel_proyecto` en la página).
  - **El hueco era el mismo patrón que este proyecto ya ha tenido dos veces**
    (`triple_motive_rows`, `intron_folding`), un nivel más arriba: la capa entera —JSONL
    append-only, cadena de md5, `verify()`— estaba **construida y testada**, y
    **`store.save_*` no se llamaba desde ningún sitio**. Los cuatro modales calculaban,
    pintaban, y al cerrar la pestaña no quedaba nada. Un test verde de una función que
    nadie invoca no prueba que la app haga eso.
  - **`SHMIR_PROJECT_DIR`: los proyectos también salen de la imagen.** Misma indirección
    que `SHMIR_REFERENCE_DIR` y aquí el motivo pesa más: lo que se guarda es el registro
    de lo que se decidió, y el sistema de ficheros de la imagen es efímero. Sin declarar,
    van junto al paquete y en local no cambia nada. Una ruta **relativa ABORTA**: el log
    acabaría en un sitio distinto según desde dónde se lance el proceso, que es lo
    contrario de para lo que existe.
  - **Abrir un proyecto con OTRA SECUENCIA se RECHAZA** (`presentation.project_open`,
    `expect_md5`). Es el fallo del CSV de miRarchitect por la puerta de la persistencia:
    el log quedaría coherente de forma, la cadena de md5 **ni se enteraría**, y el
    proyecto mezclaría dos entradas sin que nada lo delate.
  - **Se guarda el CRUDO además de lo interpretado**, en los cuatro. Lo interpretado
    depende de cómo interprete **esta** versión del código; el crudo no. Si mañana cambia
    la forma de comparar contra el referente, del crudo se recalcula; al revés no.
  - **Una selección nueva no pisa la vieja: la SUCEDE.** `selected_starts` lee la última;
    las anteriores siguen en el log, que es donde se ve que alguien cambió de opinión.
  - **`presentation` expone los cuatro `save_*` y un solo `load_stores`.** La página no
    importa `store.py`: si cada panel abriera el almacén por su cuenta, el quinto modal
    se quedaría fuera del log sin que nadie lo note — la lección de `offtarget_seed`.
  - **Ciclo comprobado de punta a punta**, no por partes: crear → guardar selección y
    corrida de empalme → cerrar → reabrir → `verify()` → vuelven la selección
    `(60, 553, 819, 1018)` y el veredicto `PASS`, y el log se lee con `cat`.
  - **El ancho de la tabla de frentes sale del nombre más largo QUE HAY**, no de un
    número escrito a mano (`dossier.py`). Al partirse `empalme_sitios` por intrón, los
    nombres llegaron a 36 caracteres y el `<24` fijo se comía la columna de al lado: el
    estado dejaba de leerse en vertical, que es justo para lo que sirve la tabla. Lo cazó
    **leer el diff del golden**, otra vez.

- **LA PRIMERA EJECUCIÓN REAL DE LA PÁGINA (2026-08-27): tres fallos con 2.947 tests en
  verde.** `NM_011170.3.gb`, Mus musculus, sin subir nada. Los tres estaban en la
  **juntura** entre piezas que por separado estaban bien, y ninguno era sutil.
  - **1. El mapa PONÍA el marco en vez de recibirlo** (`presentation.map_svg`,
    `TilingReport.frame`). La página tila el TRANSCRITO ENTERO con su anatomía —igual que
    el CLI— y el mapa daba por hecho que toda posición era del 3'UTR. Dos consecuencias y
    **solo una daba error**:
    - `signal.describe()` etiquetaba `3utr:1856` sobre un 3'UTR de 1242 nt. Eso lo abortó
      `coords`: **la cuarta vez** que aparece esta familia, después de `3utr:1784`,
      `3utr:1185` y `3utr:1398`. El invariante hizo su trabajo;
    - y el eje, los tercios y la escala se dibujaban sobre los **2191 nt de lo tilado**
      con la etiqueta «3'UTR» encima. Eso **no daba ningún error**: un mapa mudo con las
      divisorias de los tercios donde no era. El aborto tapaba al fallo callado.
    Ahora el marco sale de `report.frame` y la frontera de `report.utr3_of()`, las dos
    derivadas de la anatomía; lo que no cae en el 3'UTR **no se dibuja y se dice cuántos
    son** —el `(CTC)n` murino de `tx:892-936` está entero en el CDS—, porque descartarlo
    en silencio deja un mapa que parece completo.
  - **2. Aritmética imposible: «ventanas a tilar: 1221» arriba y «1773 no evaluables»
    abajo.** No puede haber más descartadas que totales. Eran **dos conjuntos distintos
    con el mismo nombre**: `cost_text` recibía el 3'UTR (1242 nt → 1221 ventanas) y la
    corrida tilaba el transcrito entero (2191 → 2170). `cost_text` **exige ahora la
    anatomía** y aborta sin ella (`WHY_THE_ESTIMATE_NEEDS_ANATOMY`): fabricarse una para
    estimar es la misma suposición que `resolve.py` prohíbe.
  - **3. El recuento AFIRMABA UNA CAUSA QUE NO HABÍA COMPROBADO.** Las 1773 se
    anunciaban como «ventanas no evaluables (bases desconocidas o enmascaradas)» y **ni
    una** tenía una N ni estaba enmascarada: fallaban GC y homopolímero. Misma familia
    que el «comprueba que Streamlit está instalado» pegado a un fallo de configuración y
    que el «Alu 0 %» obtenido sin buscar Alu. Ahora la descomposición va **entera**: de
    las 2170 tiladas, 949 caen fuera del 3'UTR y 1221 dentro; pasan los biofísicos 407,
    de los que 287 son del 3'UTR y 120 de fuera. Y **no se resume en una causa**: por qué
    falla cada una está en su fila.
    - Escribiendo ese mismo texto salió una primera versión que decía «las otras 407 sí
      entran. De esas, 949 están fuera del 3'UTR» — 949 de 407. El fallo no es difícil de
      cometer, y por eso la cuenta se emite entera en vez de por diferencias.
  - **4. El `.tbl` era obligatorio y NO SE VEÍA** (`resources.describe_connected`,
    `COMPANION_NOTE`). `rmsk_mouse.out` a solas **no** cierra el frente —`_rmsk` aborta
    sin resumen, comprobado— pero la lista de conectados solo nombraba el `.out`, así que
    la pantalla se leía como «un frente cerrado con un `.out` a solas», que es justo lo
    que este proyecto promete no hacer. Una pantalla que contradice al código cuesta lo
    mismo que el código equivocado: hay que ir a leer el fuente para saber cuál manda.
  - **5. «2 de 7 frentes» y «8 de 12 filtros» en la misma pantalla, y ninguno decía cuál
    contaba qué** (`FRONT_COUNT_NAME`, `FILTER_COUNT_NAME`, `FRONTS_VS_FILTERS`). Son dos
    cuentas distintas: los 7 son frentes que cierra un FICHERO; los 12, filtros de UN
    candidato, cinco de ellos biofísicos que no necesitan fichero y corren siempre. Ahora
    cada número lleva su nombre y la relación va escrita.
  - **Y EL TEST QUE FALTABA, que es la consecuencia de método**
    (`tests/test_corrida_de_la_pagina.py`, `tests/golden/pagina_raton.txt`,
    `presentation.page_run` / `page_snapshot`). No fallaba la cobertura de las funciones:
    fallaba que **nadie recorría el camino de la página de punta a punta mirando la
    salida entera**. La página llama ahora a `page_run` en vez de rehacer el camino —si
    lo rehiciera, volvería a poder divergir— y `page_snapshot` lo pinta entero contra un
    golden, con la misma disciplina que el informe.
    - **Los tiempos MEDIDOS no entran en el golden** (`_sin_tiempos`): cambian en cada
      corrida y harían fallar el golden sin que nadie haya tocado nada. Falló en la
      primera corrida del propio test, 205 ms contra 221. Un golden que falla siempre
      deja de leerse, que es la única forma en que sirve para algo.
    - **El test pide la instantánea AL MISMO generador que escribe el golden.** Pedirla
      por separado ya se dio: el test usaba la configuración por defecto y el generador
      `n_candidates=10`, así que el golden decía 10 candidatos y el test veía 6. Un fallo
      que no era del código sino de tener la corrida definida dos veces — `resolve.py`
      otra vez.

- **LAS TILDES SON PARTE DEL PRODUCTO (2026-08-27)** (`tools/check_tildes.py`,
  `npm run check:tildes`). Los mensajes se escribieron sin tildes, y no es estilo: es
  texto que se copia a un correo y se pega en un informe que defiende una selección.
  «Ningun candidato esta aprobado y la seleccion es PROVISIONAL» está mal escrito.
  - **Qué se toca y qué no.** Solo literales de **prosa**, definida como «una sola línea
    y con al menos un espacio». `"seleccion"` a secas NO se toca: es una etiqueta de
    `RECORD_KINDS` o una cabecera de columna, y acentuarla rompe un fichero ya escrito en
    disco. Y lo de **una sola línea** no es cosmético — en la primera pasada convirtió
    `VERSION     NM_011170.3` en `VERSIÓN` dentro del fixture de GenBank y el parser dejó
    de encontrar la versión del transcrito. **Ortografía correcta, dato roto**: ese
    intercambio no se acepta.
  - **Tres cosas más quedan fuera, las tres por haber fallado**: lo que va detrás de un
    `-` (convirtió `--guia` en `--guía`, una opción que no existe: el texto quedaba bien
    escrito y las instrucciones que daba, mal), lo que va entre acentos graves (es código,
    no prosa) y el interior de `{...}` en una f-string (es una variable).
  - **`esta` y `mas` no los resuelve el diccionario.** «esta tabla» es demostrativo y
    «esta fuera» es el verbo: meter `esta → está` en la lista habría acentuado los 250
    casos, demostrativos incluidos — cambiar unas faltas por otras. La regla es
    **positiva y cerrada**, construida LEYENDO las 88 palabras que siguen a `esta` en
    este código: «esta corrida», «esta medida», «esta entrada» tienen forma de participio
    y aquí son **sustantivos**, así que una regla genérica de participios las habría
    acentuado todas.
  - El vocabulario es **cerrado y escrito a mano** (269 entradas): deducirlo con reglas
    de acentuación daría falsos positivos sobre `seed`, `pri-miR` y `Alu`, y un informe
    con falsos positivos deja de leerse.

- **ALCANZABILIDAD: lo que el golden NO puede ver (2026-08-27)**
  (`tools/check_alcance.py`, `data/alcanzabilidad.toml`, dentro de
  `npm run check:shmir`). Es la **tercera vez** que aparece código con tests en verde y
  sin ningún llamador: `triple_motive_rows`, `intron_folding` y `store.save_*` —la capa
  de persistencia entera—. Tres veces no es casualidad.
  - **Ni los tests ni el golden lo cazan, y no por descuido**: un test comprueba que la
    función hace lo que dice, y para eso la llama él; el golden lee lo que se emite. Lo
    que **nunca llega a emitirse** no aparece en ninguno de los dos. Son complementarios:
    **el golden lee lo que se emite; la alcanzabilidad detecta lo que nunca llega a
    emitirse.** Está escrito así en [`docs/principios.md`](./docs/principios.md).
  - **No es un fallo automático**, y el propio informe lo dice: hay casos legítimos.
    Aparecer ahí **obliga a decidir** — o se cablea, o se justifica por escrito, o se
    borra. Hoy salen **93** funciones; la primera justificación declarada es
    `seed_reference_dir`, que la invoca el hub con `python3 -c` desde `routes.js` y por
    eso este análisis no la ve.
  - **Lo que SÍ aborta es una excepción caducada**: declarada para algo que ya tiene
    llamador o que ya no existe. Una lista con entradas muertas deja de leerse, y
    entonces el siguiente hallazgo se pierde dentro — misma razón por la que un frente
    CERRADO sigue saliendo en el informe.
  - **Solo mira FUNCIONES.** Con las clases dentro salían 215 filas y casi todas eran
    `dataclass` que una función devuelve —se construyen en su propio módulo y quien las
    usa nunca escribe su nombre—. Un informe de 215 filas no lo lee nadie, y los tres
    casos reales son funciones: lo que se busca es **trabajo calculado que no llega a
    ninguna salida**.
  - Y declara **lo que no puede hacer**: no sigue `getattr` ni despachos por cadena, no
    distingue una referencia de una llamada, y **no dice que el código sobre** — dice que
    nadie lo llama, que es un hecho y no un veredicto.

- **LA SEGUNDA EJECUCIÓN REAL (2026-08-27): un problema de PROCEDENCIA y tres
  divergencias.** El mapa ya dibujaba; lo que salió esta vez es de otra familia — algo
  que emite un veredicto sin que nadie haya decidido que deba emitirlo.
  - **`G4_diana` emitía FAIL con un criterio SIN JUSTIFICAR** (`hard_filters.G4_PENDING`,
    `G4_PROVENANCE`). Lo que no tiene —y ese sí es el hueco— es entrada en
    `justificacion.py`, y no por descuido: **el test que exige justificación recorre los
    campos de `Thresholds`**, y el criterio de G4 es una **expresión regular escrita a
    mano**, no un umbral. Se coló por debajo de la comprobación.
    - **CORRECCIÓN (2026-08-27).** Aquí decía que G4 venía «del commit fundacional
      (`ccb344a`)». **Es falso y va corregido en `docs/procedencia-g4.md`**, con la
      arqueología entera. `ccb344a` es el commit del RENOMBRADO —batchwork a
      shmir-design— y su propio mensaje dice «G4 **se comprueba ahora** sobre la diana Y
      sobre la guía», o sea que ya existía y ese commit lo PARTIÓ en dos. Dar por buena
      la primera aparición que sale al buscar es exactamente el principio nº 3 —un
      diagnóstico plausible sin comprobar— aplicado a la respuesta que se dio sobre otro
      diagnóstico plausible sin comprobar.
    - **Qué mide**: el motivo G-cuadruplex canónico `G{3,}N{1-7}` × 4, sobre la diana
      (ADN) y sobre la guía (ARN). **No es un predictor de plegado**: no mide
      estabilidad, no distingue paralelo de antiparalelo y no mira el contexto.
    - **MEDIDO (2026-08-27)**: pasa **las 2170 ventanas** del 3'UTR murino, las dos
      variantes. **No ha excluido a nadie nunca**, que es por lo que nadie lo miró.
    - **Hasta que se decida por escrito NO EMITE VEREDICTO.** Sigue buscando y sigue
      diciendo lo que encuentra —dejar de mirar sería perder el dato— pero sale
      `NOT_RUN` y **no cuenta para el veredicto del candidato** (`UNDECIDED_FILTERS`,
      excluido en `overall_verdict` y en el semáforo). Dejarlo dentro habría hecho que
      TODA ventana saliera `INCOMPLETE` por un criterio que nadie autorizó — o sea `PASS`
      estructuralmente inalcanzable, que es el fallo que la interfaz ya tuvo. **Bloquear
      una aprobación también es decidir.** Y no se esconde: sale nombrado en el semáforo.
    - Lo que hay que decidir: **(1)** filtro duro o desempate, **(2)** qué predictor, y
      **(3)** con qué justificación de umbral, anotada en `justificacion.py`.
  - **UN FILTRO BIOFÍSICO NO PUEDE SER UN FRENTE** (`selection.blocking_fronts`). Con la
    máscara puesta, 66 ventanas quedan con `N` y sus filtros de secuencia salen
    `NOT_RUN` —correcto, regla 3— pero `blocking_fronts` construía un frente por cada
    `NOT_RUN`, así que `GC` y `G4_diana` salían como frentes y la app pedía su **ficha de
    obtención**: aborto. Una ventana enmascarada no es un frente.
    - Y el motivo decía **«falta el recurso»** de un filtro que no tiene recurso ninguno.
      **Tercera de esa familia**, y por eso hay ya un principio escrito sobre ella
      ([`docs/principios.md`](./docs/principios.md) nº 3): un mensaje que explica una
      causa tiene que haberla comprobado.
    - Un frente es un filtro que **se cierra consiguiendo algo**. Lo demás se cuenta en
      el semáforo, con las ventanas tiladas.
  - **LA PÁGINA NO APLICABA LA TABLA DE APA MEDIDO y el CLI sí.** Cuarta divergencia
    entre los dos frontales, la misma clase que obligó a crear `resolve.py`. Sin ella el
    tercer sitio de corte no promociona, la frontera de inmunidad se queda en `3utr:303`
    en vez de adelantarse a `3utr:251`, y **`3utr:221` volvía al panel** porque su riesgo
    estérico no llegaba a existir. Ahora `page_run` llama a `resolve_measured` como el
    CLI, y el diff del golden lo enseña entero: `AATATA` pasa de `OTRA` a `APA_POSIBLE`,
    entran 17 ventanas más a FAIL —exactamente `measured_promotion_cost`— y `3utr:221`
    sale del panel.
  - **CUOTA DE INMUNES EXPLÍCITA Y PANEL DE 10** (`selection.default_config`,
    `DEFAULT_CANDIDATES = 10`, `DEFAULT_IMMUNE_QUOTA = 4`). La página sólo tenía cuota
    **por tercio**, así que `3utr:359` (+4,82) desplazaba a `3utr:200` (+3,80) por
    asimetría y el panel quedaba con **tres** inmunes en vez de cuatro — sin que nada lo
    dijera, porque los dos son proximales y la cuota de tercios se cumplía igual.
    - **Por qué es una cuota y no una preferencia**: los inmunes son la ÚNICA reserva si
      el APA de `3utr:288` resulta funcional, y los sitios elegibles por delante del
      corte están **20/0/0** por tercio. Si se pierden, no hay de dónde rebalancear.
    - **La cuota NO va en `SelectionConfig`**, y eso lo enseñó el intento: la pareja
      (cuota, frontera) va junta por invariante —«pedir cinco inmunes sin decir inmunes A
      QUÉ no significa nada»— y `apa_immune_before` sólo se DERIVA de un informe. Ponerla
      en el dataclass hacía abortar a todo el que construyera un `SelectionConfig()` a
      mano, que es justo quien no tiene informe. Va en `default_config()`, **acotada al
      tamaño del panel**: pedir cuatro inmunes en un panel de tres es imposible y abortar
      por un defecto que nadie pidió sería peor que no tenerlo.
    - `presentation.selection_rules_report` emite el panel **bajo las dos reglas**, para
      poder compararlas. No elige: da las dos y dice cuántos inmunes deja cada una.
  - **TODA COLUMNA DE POSICIÓN LLEVA SU MARCO, y la etiqueta la pone UNA sola pieza**
    (`PolyAAnnotation.frame`). `polyA_hexamero_pos = 1185` es `tx:1185`, o sea
    `3utr:236` — bien calculado y mal etiquetado. Y había **TRES** sitios poniendo (o no)
    esa etiqueta: el TSV la ponía, la tabla comparativa la ponía **volviendo a parsear el
    entero con `int()`**, y la tabla de la página no la ponía. Ahora la pone
    `as_columns`, que es quien sabe de qué posición habla. Una **distancia** no lleva
    marco: lleva unidad (`949 nt`), y la lleva porque se lee pegada a una posición.

- **`page_run` ERA EL TERCER `store.save_*`, y lo cazó la ALCANZABILIDAD.** Se escribió
  justo para que la página no rehiciera el camino y pudiera divergir del CLI. Se
  documentó como «la página llama ahora a `page_run`». **Y la página no lo llamaba**:
  seguía tilando a mano, así que el APA medido recién cableado en `page_run` no llegaba a
  la pantalla. Ni los tests ni el golden lo veían —los tests llaman a `page_run` ellos
  mismos y el golden se genera desde `page_snapshot`, que también lo llama—: lo que
  faltaba era justo lo que este análisis mira, **quién lo llama en el camino de verdad**.
  Hay regresión escrita que comprueba que la página no vuelve a llamar a `tile_utr`.
  - **Y el análisis necesitó una vuelta más para verlo: el CIERRE TRANSITIVO.**
    `filter_gc` no la llama nadie de fuera de `hard_filters`, pero la llama
    `evaluate_window`, que sí: es una pieza de algo vivo, no código muerto. Sin esa
    vuelta el informe tenía **94** filas y ~78 eran ese caso; con ella son **23**, y `page_run`
    aparecía entre ellas. Un informe de 94 filas donde tres cuartas partes son ruido no lo
    lee nadie — que es exactamente el fallo que el análisis viene a evitar.
  - **Clasificadas en tres** (`data/alcanzabilidad.toml`): **útiles sin cablear** (lo
    urgente: `splice_variant_rows` —el cuarto modal calcula la propuesta de
    `mvm_sin_criptico` y no la enseña, cero llamadores y cero tests—, `describe_triple`,
    `ceiling_layers` —que además duplica `measured_apa.layer_for`—), **legítimas**
    (justificadas por escrito: `fixture_available`, que usan 80 ficheros de test como
    `skipUnless`; `declare_utr3_length`, API documentada) y **muertas**, que se borran en
    su propia tanda: borrar en la misma tanda que arregla otra cosa esconde el borrado
    dentro de un diff que se lee por otro motivo.

- **LA REVISIÓN DE CÓDIGO Y LA DE SEGURIDAD (2026-08-27).** Ocho hallazgos y uno más.
  Los que dejan regla:
  - **Un guardia con falsos positivos se acaba apagando.** El test de la regla 6 buscaba
    `"int("` como **subcadena**, así que saltaba sobre `run_fingerprint(` —que no
    convierte nada— y el arreglo obvio habría sido quitar la comprobación. Se busca la
    **llamada como token** (`\bint\(`). Estaba copiado en tres tests con el mismo fallo;
    ahora vive en `tests/sin_logica.py` **con un test propio de las dos mitades**: que
    muerde donde hay lógica y que calla donde sólo hay un nombre parecido. Un guardia sin
    test de que muerde se queda sin morder y nadie se entera.
  - **Una corrida vieja en pantalla es una PROCEDENCIA FALSA.** Los modales de seed y
    off-target guardaban el scan en `session_state` para sobrevivir al rerun, y al
    cambiar el panel o un ajuste seguían enseñando el resultado anterior **y
    ofreciéndolo para guardar**. Se guarda con la **huella** del panel y los ajustes
    (`run_fingerprint`, `WHY_A_RUN_FINGERPRINT`): si no coincide, no se enseña y se dice
    por qué. Un resultado que no es de la corrida que se ve es peor que no tener ninguno.
  - **Las claves de los widgets llevan la especie.** Sin ella, con dos especies abiertas
    el segundo panel reusaba el estado del primero: `key=f"pr_activo_{especie}"`.
  - **El nombre de un fichero subido lo pone el NAVEGADOR** (`presentation.upload_path`,
    `UPLOAD_NAME_RULE`). Se escribía `Path(tempfile.mkdtemp()) / subido.name` con el
    nombre tal cual, y con `../` dentro la escritura sale del directorio temporal que se
    acababa de crear para contenerla. Que Streamlit lo limpie o no es una **suposición
    sobre código ajeno**, y aquí una causa no comprobada no se da por buena. La regla es
    **una**: sobrevive el nombre, se cae toda la ruta —`..` no es un caso especial, es
    ruta—, así que **no hay que acertar con la lista de formas de escribirlo**
    (`..%2f`, `....//`, `..\`). La extensión sí sobrevive: `resolve_anatomy` y
    `load_scaffold` deciden el formato por ella. Y la comprobación final es sobre la ruta
    **resuelta**, que es la que llega a `write_bytes`: comprobar el texto y escribir otra
    cosa es media comprobación. Es la hermana pequeña de `check_project_slug`, un nivel
    más abajo: allí el nombre lo teclea el usuario, aquí lo manda el navegador.
  - **La alcanzabilidad se medía a sí misma mal.** La clave era el **nombre pelado**, así
    que un envoltorio homónimo vivo mantenía «vivo» al original: `presentation` envuelve
    `store.save_blast_run` y compañía, o sea que **la herramienta había dejado de ver
    exactamente el caso que la motivó**. Con clave `(módulo, nombre)` el informe pasó de
    23 a 17 — y las cuatro que salieron a la luz (`offset_of`,
    `verify_contexts_against_plasmid`, `load_guide_fixture`, `can_transfer_window`)
    estaban tapadas. Un análisis que se equivoca **hacia el silencio** es peor que no
    tenerlo: no avisa y además tranquiliza.
  - **Las 17, revisadas una a una** (`data/alcanzabilidad.toml`). Lo que aparece y no
    estaba: `verify_contexts_against_plasmid` **aborta si los contextos del módulo no
    coinciden con el plásmido depositado** y sólo lo corren sus tests —la comprobación
    existe y no corre cuando serviría—; `shared_network`, cuyo propio docstring exige
    decir «NO CALCULADO» con esas palabras y no hay nadie que lo diga. Y **tres casos de
    dos formas de calcular lo mismo** con una sin usar (`ceiling_layers` frente a
    `measured_apa.layer_for`, `verdict_state` frente a `splice_store`/`dossier`,
    `analyze_3utr` frente a `annotate_polya`): no es que sobre código, es que **hay dos
    definiciones de un número y nada garantiza que coincidan**.
  - **La revisión de seguridad no encontró nada** que emitiera veredicto. Lo único
    señalado —el nombre del fichero subido— es lo de arriba, y ya está cerrado.

- **LA COMPROBACIÓN DEL PLÁSMIDO, CABLEADA (2026-08-27).** `verify_contexts_against_plasmid`
  llevaba desde el generador de bloques abortando si los contextos del módulo no
  coinciden con el vector real — escrita, probada, y **sin correr nunca donde habría
  servido de algo**. Es el patrón de `store.save_*` sobre algo más grave: lo que no se
  contrastaba son secuencias que se van a PEDIR. Principio nº 6 de `docs/principios.md`,
  y sus tres mitades:
  - **Corre donde se genera, y hay DOS generadores.** `gblock.build_gblock` monta el
    módulo de 149 nt para los oligos y `blocks.build_block` monta ese mismo módulo más
    el cassette para la ficha. Cablear sólo el primero habría dejado la comprobación
    fuera justo del camino que se lee.
  - **Sin el plásmido sale `NOT_RUN`, no `PASS`,** y el módulo entero `INCOMPLETE`. El
    plásmido SGEP **no está en el repositorio** y no vale el que hay:
    `data/reference/aav_casete.fa` es pAAV con PrP murino, otro vector, y **no contiene
    ninguno de los dos contextos** —comprobado, con test, para que nadie apunte la
    comprobación ahí creyendo que sirve—.
  - **Se ve.** El motivo se pinta en la ficha y en el informe que se entrega. La primera
    versión corría y no salía en ningún golden: una comprobación que corre y no llega a
    la pantalla es la mitad del arreglo, y **el diff del golden es la prueba**.
- **LOS TRES PARES DUPLICADOS, CRUZADOS EN VEZ DE BORRADOS**
  (`tests/test_cruce_de_pares_duplicados.py`, principio nº 5). La que no se usa es la
  única que puede contradecir a la que sí. Y al cruzarlos, los tres resultaron ser cosas
  distintas de lo que parecían:
  - **`spliceai.verdict_state` vs `SpliceRun.verdict`: par de verdad, y NO COINCIDEN.**
    La primera mira la corrida ENTERA («¿tiene pares?»), el almacén mira **el par
    candidato × intrón**, que es la unidad que este frente tiene decidida. Para un
    candidato que nadie consultó, `verdict_state` dice `PASS` donde el almacén dice
    `NOT_RUN`. **La que no tenía llamador no era una copia redundante: era la
    equivocada** — y estaba ahí para que alguien la cableara. La discrepancia queda fija
    en un test.
  - **`ceiling_layers` vs `layer_for`: no son dos implementaciones.** `ceiling_layers(m)`
    es literalmente `return m.layers`. Lo que sí se puede exigir es lo que su docstring
    AFIRMA —tramos sin huecos ni solapes—, comprobado sobre posiciones reales del ratón.
  - **`analyze_3utr` vs `annotate_polya`: dos GENERACIONES con reglas deliberadamente
    distintas** (el umbral simétrico ±10 que «no sale de ningún artículo» frente a la
    ventana de corte asimétrica). Exigirles que coincidan sería exigir que el bloque 3 no
    hubiera pasado. Lo que sí comparten es `find_polya_signals`, y ése es el número que
    se cruza.
  - **Y UN CUARTO PAR que la alcanzabilidad NO PUEDE VER**, porque los dos lados tienen
    llamador: `blocks.py` monta el módulo con SUS piezas y `gblock.py` con SUS
    constantes. Hoy coinciden —comprobado sobre el módulo entero, no sobre los trozos—,
    pero nada lo obligaba, y lo que divergiría es **ADN que se manda a sintetizar**.
    Además la comprobación del plásmido usa las de `gblock`: sin este cruce, validaría un
    módulo que la ficha no monta.
- **LA PROCEDENCIA DE G4, HECHA DE VERDAD** (`docs/procedencia-g4.md`). Lo que se dijo
  aquí —que venía «del commit fundacional `ccb344a`»— **era falso**: `ccb344a` es el
  renombrado, y su mensaje dice «G4 se comprueba AHORA sobre la diana Y sobre la guía»,
  o sea que ya existía y ese commit lo partió en dos. Se dio por buena la primera
  aparición que salió al buscar. La cadena real son 33 minutos del 25 de agosto:
  `8211734` (sólo las reglas, sin pipeline) → `61741c4` (nace la tabla de 15 pasos, con
  el paso 8 «Sin motivo G-cuádruplex, duro, pendiente») → `b544dd2` (la implementación,
  empaquetada con GC y homopolímero y **sin ninguna cita**, al lado de una asimetría que
  sí cita Turner 2004) → `ccb344a` (se parte en dos). Quién lo pidió: `61741c4` separa
  «apartados A, B y C **del encargo**» de «**además**: docs/pipeline.md…», y G4 está en
  el además; pero `docs/valores-esperados.md`, del mismo commit, se titula «verificados
  por el responsable del proyecto» y lista «sin motivo G4» junto a un 181 PASS que este
  código no pudo calcular —los pasos 3-8 estaban «pendiente»—. **El repositorio no puede
  decidir cuál de las dos, así que no se decide.**

- **QUÉ DATOS DE UNA ESPECIE SIGUEN EN EL CÓDIGO (2026-08-27)**
  (`tools/auditar_datos.py`, `data/datos_en_codigo.toml`, dentro de
  `npm run check:shmir`). Es la generalización de lo que ya pasó tres veces —
  `rmsk_mouse.out` conectado por rol, `txid10090` por defecto, `mmu-` por defecto—: un
  dato de UNA especie escrito en el código **funciona callado** y sobre otra produce un
  resultado con la **forma correcta**. Tres categorías, y la distinción es lo único que
  hace útil el informe:
  - **DE LAS CINCO DE «DATO», TRES SE HAN MOVIDO. DECIDIDO (2026-08-27)**, con el
    criterio dicho en una frase por el responsable y que es lo que ordena la lista:
    **si cambiaría al cambiar de especie o de gen, es dato y va al gestor; si es una
    regla sobre cómo tratar el dato, va al código.**
    - ~~`apa.POLYA_DB_PRNP`~~ → **`data/reference/polya_db_mouse.tsv`**, con su línea en
      el manifiesto y su md5. Era la más importante: 15 PAS con PSE y AvgRPM, y de ella
      cuelgan el techo por tramos, la promoción del `AATATA` y el panel de diez. **La
      constante se quitó ENTERA**, no se dejó «por si acaso»: mientras existieran las
      dos habría dos definiciones del mismo dato sin nada que las atara — y ya habían
      empezado a separarse, con las notas de los anclajes diciendo `PSE 21,1 %` en el
      código y la lectura del racimo en el fichero. Los tests la cargan del fichero
      (`tests/tabla_medida.py`), que es el camino que corre la app.
      **No es el rol `apa_medido.tsv`**: ése ya existe y carga OTRO formato —posición,
      fracción, nombre—, así que se le dio rol propio (`polyadb`) en vez de fundir dos
      formatos vivos. La ficha de obtención de `apa_medido.tsv` describía PolyA_DB, que
      es lo que hacía parecer que era el mismo hueco.
    - ~~`external_score.EVIDENCE`~~ → los pares se **leen** de
      `mirarchitect_prnp_export_buena.csv` (`read_evidence_pairs`), y salen **todas** las
      filas: elegir cinco vuelve a ser transcribir. **Lo que salió al cruzarlo tiene
      entrada propia** — errata nº 27 y principios nº 12 y nº 13 — y se resume abajo,
      porque es lo más grave de esta tanda.
    - ~~`reference.REFERENCES`~~ → la **anatomía** entra en el manifiesto: tres columnas
      nuevas (`cds`, `md5_secuencia`, `md5_utr3`). Registraba los FICHEROS y no la
      frontera de la que cuelgan los tercios, la región de cada ventana y la distancia
      de cada señal de polyA al extremo. **Sigue habiendo dos definiciones**, y eso solo
      es admisible porque algo obliga a que coincidan:
      `tests/test_anatomia_en_el_manifiesto.py` las cruza **en las dos direcciones**.
      Queda pendiente el paso siguiente —que `REFERENCES` se **lea** del manifiesto—,
      que es un cambio de fuente única y no un registro.
    - **OJO CON LOS TRES CHECKSUMS**, que ahora conviven en la misma fila: `md5` es el
      del FICHERO en disco, `md5_secuencia` el de la SECUENCIA canónica y `md5_utr3` el
      del 3'UTR. Copiar uno en el sitio de otro hace que el fichero **bueno** se
      rechace. Hay test de que los tres son distintos.
  - **LAS DOS QUE SE QUEDAN, y por qué no es incoherencia**:
    - `offtarget.CONTROL_NAMES` **se reclasifica como DECLARACIÓN**
      (`WHY_THE_CONTROLS_STAY_IN_CODE`). Estaba como DATO con el motivo «su elección
      viene de la biología, no del código»: la frase es cierta y **no es el criterio**.
      Los tres nombres son el **patrón** de qué significa «muchos sitios», y cambiarlos
      cambia la lectura de todos los informes a la vez; en un fichero se cambiarían
      **sin que se viera en el diff**, que es exactamente la razón de `CORE_ABUNDANT`. Y
      con la misma consecuencia: fuera de cerebro murino la elección no está
      justificada, y eso se arregla **marcándola**, no sacándola a un fichero. Sus
      **secuencias** sí son dato y ya salen de `mature.fa`.
    - `seeds.BOOTSTRAP_SEED_TABLE` **se queda, con FECHA DE CADUCIDAD explícita**
      (`seeds.bootstrap_expiry_note`). El aviso de siempre salía **igual** con
      `mature.fa` en el depósito y sin él, así que no distinguía «no lo tenemos» —una
      limitación que se declara y con la que se convive— de «lo tenemos y no se está
      usando», que es la tabla equivocada. Ahora el segundo caso sale aparte y dice qué
      hacer. Se borra cuando el fichero de maduros sea obligatorio para correr.
  - **PROSA: la tarea pendiente está CERRADA.** `offtarget.UCSC_ROUTE` nombraba `mm39`
    **dentro del texto**; ahora es `UCSC_ROUTE_TEMPLATE` con marcador y `ucsc_route(especie)`
    lo resuelve contra `species.ucsc_assembly`. Si la especie no lo tiene declarado, el
    texto **lo dice y dice dónde se declara**, con la misma redacción que las fichas
    (`obtencion.undeclared_note`). Era el caso peligroso de siempre: la instrucción se
    leía correcta de principio a fin y mandaba a bajar el transcriptoma del organismo
    equivocado, **sin dar ningún error**.
  - **Y una constante que se muda deja DIRECCIÓN** (`apa.WHERE_THE_MOUSE_TABLE_LIVES`):
    sin una frase que diga a dónde se fue, el siguiente que busque `POLYA_DB_PRNP` y no
    la encuentre pensará que el dato se perdió o que nunca estuvo. Mismo criterio que un
    frente CERRADO que sigue saliendo en el informe.
  - La tabla la ata un test en las dos direcciones, como `alcanzabilidad.toml`: una
    constante sospechosa **sin clasificar** hace fallar la suite, y una entrada **muerta**
    también.

- **LA CONTRAMEDIDA CONTRA EL PEOR FALLO DEL PROYECTO ESTABA APOYADA EN EL DATO QUE ESE
  MISMO FALLO RETIRÓ (2026-08-27).** Errata nº 27, y es lo más grave que ha salido en
  esta tanda — no por lo que rompió, sino por lo que podría haber roto sin que nada lo
  dijera.
  - `external_score.EVIDENCE` registra la **dirección** de la escala de miRarchitect
    —si menor es mejor— **con los pares (puesto, score) de los que salió**. Estaban
    transcritos a mano. Al derivarlos del fichero versionado salió que **no eran de ese
    fichero**: cuadran, uno a uno, con `mirarchitect_prnp_raton.tsv`, el que el
    manifiesto marca **«NO USAR»** porque se puntuó sobre el **3'UTR FABRICADO de
    1246 nt** — la errata nº 5.
  - **`lower_is_better()` no es una función cualquiera**: existe exactamente para impedir
    que se ordene por un score de dirección desconocida y **se manden a síntesis los
    peores candidatos**. Es la contramedida escrita contra el modo de fallo más caro que
    este proyecto sabe nombrar, y estaba apoyada en el dato que ese fallo retiró.
  - **La dirección no cambió, y eso es SUERTE, no un atenuante.** Los tres ficheros
    vienen crecientes. Si la corrida retirada hubiera venido al revés, hoy tendríamos la
    dirección **invertida**, **cinco pares de aval** al lado, el test de `EVIDENCE` **en
    verde** —comprueba que la evidencia es monótona consigo misma, y una invertida lo
    es— y `lower_is_better()` **aprobando**. Sólo habría saltado `file_order_direction`,
    y sólo al importar un fichero.
  - **Tres sitios decían de dónde salía el dato y NINGUNO acertaba**: la constante decía
    «corrida manual sobre el 3'UTR de Prnp murino», `datos_en_codigo.toml` decía
    `mirarchitect_prnp_export.csv`, y el ancla real era el TSV retirado. Cada uno parecía
    confirmar a los otros dos: eso es lo que lo hizo invisible durante semanas.
  - **PRINCIPIO nº 12 — la procedencia de una EVIDENCIA se audita igual que la de un
    dato.** Un fichero retirado **no se retira solo** de las constantes que lo citan.
    `tests/test_procedencia_retirada.py` deriva la lista de retirados **del manifiesto**
    —«NO USAR» o «FIXTURE NEGATIVO»— y barre `shmir_design/` y `tools/` **enteros**, no
    sólo `EVIDENCE`. Si mañana se retira otro fichero, queda cubierto sin tocar el test.
    - **Nombrar un retirado se puede; nombrarlo como si fuera una fuente viva, no.** La
      regla no es una lista de módulos exentos —eso habría dejado ciego justo al módulo
      que lo motivó— sino: **quien escribe el nombre escribe al lado por qué no se usa**,
      en el mismo texto. Ya cazó uno: el ejemplo de uso de `tools/audit_scores.py`
      apuntaba al fichero retirado sin decirlo.
  - **PRINCIPIO nº 13 — una constante que cita un fichero se DERIVA de él, nunca se
    transcribe.** Lo que vive en código es **cuál** es el fichero; los valores se leen. Y
    si no está, se **aborta** — no se devuelve una lista vacía, que es como una evidencia
    desaparece sin que nadie lo note.
  - **LOS OTROS DOS FIXTURES RETIRADOS: LIMPIOS, y se dice CÓMO se buscó.** «No hay nada»
    sin decir con qué se miró es la misma frase que el «Alu 0 %» obtenido sin buscar Alu.
    - Contra el **3'UTR fabricado** no sirve buscar números —comparte casi todos con las
      referencias buenas—: se busca **por subcadena de ADN**, y una que esté en él y en
      ninguna referencia verdadera sólo puede venir de ahí. **Cero.** Con su **control
      adversario**: el test comprueba además que existe algún tramo exclusivo, porque si
      no existiera, «cero culpables» y «la búsqueda no distingue nada» darían lo mismo.
    - Contra el **`.out` de biblioteca equivocada** no hay cifra exclusiva que buscar, y
      la razón es la propia demostración del proyecto: **es el mismo fichero byte a
      byte** que el válido. Lo que lo distingue vive en el `.tbl`, y de ahí tampoco hay
      ninguna cifra en el código. **Cero.**

- **CADA GUARDIA, CON SU MOMENTO. AÑADIDO (2026-08-27)**
  (`tools/auditar_guardias.py`, `data/guardias.toml`, dentro de `npm run check:shmir`).
  Sale de la parte del contrafactual de la errata nº 27 que más enseña: de los dos
  guardias que podían haberlo cazado, `lower_is_better()` habría **aprobado** y
  `file_order_direction()` sólo salta **al importar un fichero**. **La contramedida
  existía y estaba en el sitio equivocado del flujo**, y nada la revalidaba después.
  - **Es el complemento del principio nº 9**, y va como principio nº 14: *existir no es
    contener, y **haber comprobado una vez no es seguir comprobando**.*
  - **Cuatro columnas por guardia, y ninguna sobra**: qué protege (el invariante, no la
    función), **cuándo se ejecuta** (`INGESTA` · `CADA_CORRIDA` · `AL_EMITIR` ·
    `AL_ABRIR` · `AL_CONSTRUIR`), si lo protegido **puede degradarse** después de la
    comprobación, y **qué lo revalida** — o `NADA`.
  - **LA CLASE DE RIESGO ES LA INTERSECCIÓN**: `INGESTA` + puede degradarse + nada lo
    revalida. Hoy sale **uno**, y es exactamente el de la errata: `file_order_direction`.
    Mientras nadie lo cablee sigue siendo el siguiente en fallar, y hay un test que lo
    fija — si alguien lo arregla, el test cambia con él.
  - **Y UNA SEGUNDA CLASE que salió de RELLENAR la tabla, no de escribirla:
    `revalida = SUITE`.** Un guardia cuyo supuesto sólo lo comprueba la suite protege el
    **repositorio** y no protege una **corrida**: en producción el directorio de
    referencia vive en un volumen que la suite no mira. Hoy sale uno — el ancla de
    `EVIDENCE`.
  - **Tres distinciones más, todas de llenar la tabla**:
    - **Un guardia que no aborta puede ser un INFORME.** `manifest.check_directory`
      compara el md5 de cada fichero contra el manifiesto y devuelve `NO_COINCIDE` para
      que el panel lo pinte: ayuda a decidir con la pantalla delante, **no impide nada**.
      Quien impide es el cargador, en cada corrida. Va en `[solo_informan]`, porque «no
      aborta» a secas es justo lo que separa un guardia de un aviso.
    - **A veces RECHAZAR es lo correcto y abortar no** (`como_actua = "RECHAZA"`).
      `cached_run` retiene un resultado cuya huella ya no cuadra; abortar habría tirado
      la página al cambiar un ajuste.
    - **«Mudo» va por ENTRADA, no por símbolo.** Un guardia se implementa con varias
      piezas y no todas abortan —`resources._refseq` PASA el md5 esperado y quien aborta
      es `specificity.load_database`—. Exigirlo pieza a pieza daba falsos positivos sobre
      la fontanería, y **un guardia con falsos positivos se acaba apagando**.
  - **LO QUE LA TABLA ENCONTRÓ AL LLENARSE, y es el hallazgo de la tanda**:
    `store.ProjectStore.verify()` —la que recalcula la cadena de md5 del log— estaba
    escrita, probada y **sin ningún llamador fuera de sus tests**. La cadena **no se
    comprobaba nunca en la app**. Es el patrón de `store.save_*` y `page_run` por cuarta
    vez, pero sobre un **guardia**: no es trabajo calculado que no llega a una salida, es
    una **comprobación que no comprueba**.
    - **Y es la peor de la serie por una razón que no es de grado** (errata nº 29): las
      tres anteriores producían **ausencia de información** —un detalle que no salía, un
      eje que no llegaba a la pantalla, cuatro modales que no guardaban nada—. Ésta
      producía **CONFIANZA INFUNDADA**. Estaba **toda la disciplina de la cadena de
      md5** —el eslabón por línea, el aborto con el número de línea, el texto que explica
      que no impide editar el fichero sino que lo vuelve visible— y existía
      **nominalmente**: nada era visible, y un log editado se habría leído igual que uno
      íntegro. De un hueco de información uno se entera al buscar el dato; de una
      comprobación que no comprueba **no se entera nadie**, porque su producto normal es
      el silencio, que es justo lo que se ve cuando todo está bien. Y su momento natural saltó en cuanto se
    preguntó por él — el log se edita **entre sesiones**, así que comprobarlo sólo al
    escribirlo no protege de nada. **CABLEADO** en `presentation.project_open`, con
    regresión.
    - La misma pregunta sacó que la comparación de la **huella de corrida** vivía **en la
      página** y copiada en los **dos** modales: sin test y pudiendo divergir entre ellos.
      Ahora decide `presentation.cached_run` (regla 6).
  - **EL CRUCE CON LA ALCANZABILIDAD SÍ ES UN FALLO. AÑADIDO (2026-08-27)**, y sale de
    cómo apareció lo de `verify()`. **No lo cazó la alcanzabilidad y no podía**: ese
    análisis mira funciones de módulo y `verify` es un **método**; la exclusión estaba
    declarada y justificada con «los tres casos reales son funciones», que era cierto
    cuando se escribió y que **el cuarto refuta**. Lo cazó tener que rellenar «cuándo se
    ejecuta».
    - **Es la misma información y son dos preguntas** (principio nº 15): «nadie la
      llama» se lee como **pendiente** —una fila más de una lista de trece— y «cuándo
      protege → nunca» no se puede leer de otra forma. **Sólo una obliga a actuar.**
    - Así que se cruzan, y **sin excepción posible**: una justificación de alcanzabilidad
      vale para una función que nadie llama; para un **guardia** que nadie llama, no.
    - La alcanzabilidad entra ahora en los **métodos declarados como guardias** —pocos,
      enumerados a mano— y el resto de los métodos siguen fuera por la razón de siempre.
    - **El criterio del cruce se MIDIÓ, no se supuso**, porque un guardia con falsos
      positivos se acaba apagando: **no vale una mención en prosa** —con un criterio
      textual `check_scaffold` salía «vivo» porque tres docstrings hablan de él— pero
      **sí vale nombrarlo sin llamarlo**, porque `resources._refseq` entra en un
      diccionario y se despacha por rol. Con el criterio fino salían cuatro y tres eran
      falsos positivos.
    - **Al estrenarse dio tres, y DOS eran errores de la tabla**, no del código: un
      cargador de fixtures de test y una API para otra especie estaban clasificados como
      guardias de producción. Se corrigió la tabla.
  - **EL TERCERO ERA REAL: `mirarchitect.Export.check_scaffold` no lo llama nadie.** «El
    andamio se decide por SECUENCIA, no por etiqueta» es una regla escrita de este
    proyecto, y **el camino vivo se fía de la etiqueta**: `tools/import_scores.py` recibe
    un TSV de dos columnas donde no hay loop que comparar, así que lo que decide es el
    `--andamio` que se teclea.
    - Se ha hecho lo honesto y no lo cómodo: el veredicto **dice** que se comprobó por
      etiqueta (`external_score.SCAFFOLD_BY_LABEL`) y el guardia por secuencia queda en
      **`[sin_camino]`** con **qué haría falta** —que el CLI acepte el export entero—.
      Aceptarlo es una decisión de interfaz y no se toma de paso.
    - **`[sin_camino]` es una tercera categoría**: ni fallo ni código muerto, sino una
      comprobación escrita para una entrada que la app todavía no acepta. Se declara
      porque la alternativa es peor —leerla en el código y creer que corre— y **caduca**
      en cuanto alguien la cablea, como las excepciones de alcanzabilidad.
  - **`revalida = SUITE` ES CATEGORÍA DE PRIMERA, y al preguntarlo en serio son TRES, no
    uno.** Obliga a rellenar `revalida_en_produccion`: sin eso la categoría es una queja
    y no una tarea. Los tres se apoyan en el **contenido de un volumen** que sólo cruza
    un test:
    - **la tabla de PolyA_DB** — el md5 del fichero cuadra contra el manifiesto de
      TRABAJO, que se escribe en el mismo volumen y se puede actualizar a la vez. Lo
      cerraría un md5 fijado en **código**, como ya se hace con la secuencia canónica de
      las referencias y por la misma razón: la constante no es editable y el manifiesto
      de trabajo sí;
    - **la anatomía del manifiesto contra `REFERENCES`** — `parse_manifest` sólo comprueba
      la FORMA. Lo cerraría que el cargador compare la fila contra `REFERENCES` cuando el
      accession esté declarado: es barato, ya se lee la fila;
    - **el ancla de `EVIDENCE`** — lo cerraría que `read_evidence_pairs` mire la línea del
      ancla en el manifiesto de trabajo y aborte si su origen la marca «NO USAR».
  - **No falla nunca: es un informe.** Lo que falla es `tests/test_guardias.py` — si una
    entrada nombra un símbolo que ya no existe, si de un guardia `ABORTA` no aborta
    ninguna pieza, si algo de la clase **derivada del código** —todo lo que compara una
    identidad declarada contra lo entregado— se queda fuera sin declararlo, si un guardia
    **no lo invoca nadie**, si un `SUITE` no dice qué lo cerraría en producción, o si una
    entrada de `[sin_camino]` ya tiene camino.

- **LA FICHA DE OBTENCIÓN DESCRIBÍA UN FICHERO Y EL CARGADOR LEÍA OTRO (2026-08-27).**
  Mismo principio nº 13, un piso más arriba, y es lo que hizo creer que la tabla de
  PolyA_DB ya tenía hueco en el gestor: tenía la **ficha**, no el cargador.
  - `fraccion_isoforma_larga.toml` describía PolyA_DB de arriba abajo —su URL, sus dos
    tablas, sus columnas por nombre, el aviso de las coordenadas genómicas— y el **único**
    fichero que listaba era `apa_medido_{slug}.tsv`, cuyo cargador lee **otro formato**:
    tres columnas `posicion/fraccion/nombre` con la posición ya convertida. **Lo que el
    texto mandaba preparar y lo que el cargador sabe leer eran cosas distintas.**
  - Ahora la ficha nombra **los dos**, con su formato cada uno y con un aviso que dice
    que son dos y por qué: `polya_db_{slug}.tsv` es la de PolyA_DB —la que producen sus
    pasos— y `apa_medido_{slug}.tsv` es la simple, **opcional**, para una medida que
    llega ya convertida (el caso sería un 3'-end seq de cerebro murino).
  - **Y los nombres los pone el GESTOR, no la ficha** (`{fichero_<rol>}`,
    `{hermano_<rol>}` resueltos contra `species.required_files`). La ficha escribía
    `apa_medido_{slug}.tsv` y el gestor pide `apa_medido.tsv` en ratón: la regla de
    sufijos por especie estaba en dos sitios. Ahora la ficha nombra el **rol** —que es lo
    estable— y el nombre lo pone quien lo va a cargar.
  - **`tests/test_ficha_contra_gestor.py` cruza las dos listas por especie**, en las dos
    direcciones: ningún fichero que el gestor pida puede faltar en su ficha, y ningún
    nombre de fichero de la ficha puede ser algo que nadie vaya a cargar. Al escribirlo
    salieron **tres huecos más**: la ficha de especificidad no nombraba la base de RefSeq
    como fichero, la de off-targets no nombraba `expresion_cerebro`, y la de colisión de
    seed no nombraba la capa ampliada de abundancia.
  - **ERAN TRES NIVELES, y cada uno mentía por su cuenta** (errata nº 28): la **ficha**
    describía un fichero y el rol cargaba otro; el **listado** no nombraba el fichero que
    la propia ficha describía; y los **nombres** estaban transcritos con otra regla de
    sufijos que la del gestor. Ninguno daba error — la ficha se lee, el cargador se
    ejecuta, y nadie los pone uno al lado del otro.
  - **La lección, y es la que generaliza**: **un dato transcrito en lugar de derivado no
    se desincroniza en un sitio, se desincroniza en TODOS los que lo copiaron.** Cada
    copia envejece por su cuenta y en su propia dirección, así que ninguna coincide con
    las otras y todas parecen plausibles por separado. Es lo mismo que con los pares de
    `EVIDENCE` —la constante, la tabla de auditoría y el ancla real, tres orígenes y
    ninguno correcto—, sólo que aquí las tres capas estaban una encima de otra sobre el
    mismo dato.

- **QUÉ BANDERAS DE LOS CLI SE RECORREN DE PUNTA A PUNTA (2026-08-27)**
  (`tools/auditar_banderas.py`, `data/banderas.toml`, dentro de `npm run check:shmir`).
  Sale de la errata nº 31, y cubre el **hueco entre las dos herramientas que ya había**:
  - **la alcanzabilidad ve símbolos sin llamador; el golden ve la salida POR DEFECTO; y
    entre los dos vive el código llamado desde caminos que nadie recorre.** Es el
    principio nº 17. Ninguna de las dos podía cazar el `NameError` de `--rmsk`: había una
    llamada escrita, y el golden se genera sin máscara.
  - **Todo se DERIVA**: las banderas, de los `add_argument` de cada CLI; el recorrido, de
    los tests. Aquí sólo se declara lo que no se puede derivar — **qué consecuencia tiene
    cada bandera**, que es lo que ordena la lista.
  - **CUATRO consecuencias, y el orden ES la priorización**: `VEREDICTO` (puede cambiar
    si un candidato pasa, cae o queda INCOMPLETE — conecta un filtro, mueve un umbral,
    resuelve la anatomía, o ABORTA cuando un md5 no cuadra), `DATO` (cifras y
    anotaciones que viajan con el veredicto sin decidirlo), `FORMATO` y `FONTANERIA`.
    Una `VEREDICTO` sin recorrido es **urgente**; una de `FORMATO`, no. Sin esa
    distinción, 139 filas planas no las lee nadie — el fallo que esto viene a evitar.
    - **Un `*-md5` es VEREDICTO y no DATO a propósito**: su trabajo es **abortar** cuando
      el fichero no es el que dice ser. Si ese camino no se recorre, el fichero
      equivocado entra en silencio.
  - **Un test que espera un `2` NO cuenta como recorrido.** Comprobar que una entrada
    mala se rechaza es útil y **no atraviesa el camino** — ahí vivía la errata nº 31.
  - **Y LLEVA TRINQUETE**, porque una lista larga se lee como «pendiente» y no obliga a
    nada (principio nº 15): el número de `VEREDICTO` sin recorrer va **declarado** y la
    suite falla **en las dos direcciones** —si sube, alguien añadió algo que decide y no
    lo recorrió; si baja, el techo está caducado—. **Sólo puede ir hacia abajo.** Hoy
    está en **50**. Cubrirlas todas de golpe no hace falta; lo que hace falta es que
    bajarlo sea la única forma de cerrar la suite.
  - **Las exenciones van DECLARADAS con motivo y siguen saliendo**: hoy dos,
    `reference_data --fetch` y `--efetch-url`, que salen a la RED — recorrerlas exigiría
    un endpoint verificado y el registro está vacío (regla 4). Una exención que
    desaparece de la lista deja de poder caducar; hay test de que una exenta que ya se
    recorre hace fallar la suite.
  - **Estado de partida: 47 de 139 banderas con recorrido entero**; hoy 47 de 130, tras
    retirar nueve (bloque siguiente). La primera que se
    cubrió al estrenarlo fue `--mirbase` —conecta `mature.fa` y con él el FAIL duro del
    núcleo de abundancia—, que era la `VEREDICTO` más consecuente de las alcanzables hoy:
    `--apa-medido` espera al 3'-end seq y `--accesibilidad` a ViennaRNA.
  - **El detector se equivocó EN LAS DOS DIRECCIONES antes de valer.** Resolvía el CLI
    con una tabla de alias global: daba por recorridas de `design` las banderas de
    `import_scores` —que también importa su main como `main`— y no veía las de
    `test_usar_manifiesto.py`, que llama por un ayudante. Se contrastó contra un `grep`
    en las dos direcciones y ahora el CLI se resuelve **por fichero, de sus propios
    `import`**, siguiendo **un** nivel de ayudante. Lo que no puede hacer va declarado:
    no ve banderas que lleguen por variable, y no dice que una bandera esté rota — dice
    que **nadie la ha recorrido entera**.

- **LAS 50 BANDERAS VEREDICTO, CLASIFICADAS — Y NUEVE RETIRADAS (2026-08-27)**
  (`destino` en `data/banderas.toml`). El techo de 50 no decía nada accionable, así que
  se clasificó con el mismo criterio que la alcanzabilidad: **CUBRIR** (se usa de
  verdad), **CONSTANTE** (reproduce una decisión ya tomada y debe dejar de ser bandera),
  **BORRAR** (muerta). Salieron **41 / 5 / 4**.
  - **La sospecha de «superficie de configuración crecida» sale CONFIRMADA en parte, y
    conviene decir en cuál**: la mayoría (41) son caminos reales, y **12 de ellos no se
    pueden recorrer hoy** porque el dato no existe (`--refseq`, `--transcriptoma-3utr`,
    `--apa-medido`…) o falta ViennaRNA. Lo que sí había era **nueve** banderas sin dueño.
  - **Un flujo real que nadie tenía en cuenta**: el puente de Batchwork
    (`apps/batchwork/server/operations/shmir-design.js`) pasa **18 banderas en cada
    corrida desplegada**, cuatro de ellas sin recorrido de punta a punta
    (`--bootstrap-seeds`, `--cds-b`, `--max-homopolymer`, `--min-spacing`). Al clasificar
    hay que mirar quién llama, no sólo qué hace la bandera.
  - **Las nueve retiradas**, y por qué:
    - `--inmunes` y `--inmunes-antes` — la cuota es la decisión del proyecto y la
      frontera **se deriva**. Su defecto (0) contradecía la constante (4): errata nº 32.
    - `--min-por-tercio` — repetía el valor que ya trae `SelectionConfig`.
    - `--mirbase-especies` — puerta de atrás a un prefijo tecleado, que es justo lo que
      da CERO colisiones y parece buena noticia. El prefijo sale de `species.resolve()`.
    - `--polyA-modo` — el criterio es ESCALONADO, decidido con la tabla delante, y el
      informe ya emite el top-N bajo los tres criterios.
    - `--seeds` (en `design` y en `tiling_report`) — tabla suelta **sin procedencia**,
      sustituida por `mature.fa` en el gestor.
    - `--repeats` — máscara por intervalos pelados, sin especie, sin resumen y sin md5.
      La sustituyó `--rmsk`, que valida la corrida entera.
    - `oligo --skip-filters` — saltaba los filtros duros y emitía un oligo **sin
      veredicto**, que es exactamente lo que este proyecto existe para impedir.
  - **Bajar eliminando es más barato que cubrir, y una bandera retirada no puede
    fallar.** El trinquete pasó de **50 a 41** sin escribir un solo test de punta a punta
    más — y la historia de cómo bajó va en la propia tabla, porque el camino importa
    tanto como el número.

- **EL INVENTARIO DE ESTADOS DE LA INTERFAZ (2026-08-27)**
  (`tools/auditar_estados.py`, `data/estados.toml`, dentro de `npm run check:shmir`).
  El de banderas cubre los CLI; **éste cubre la PÁGINA, que es donde vive lo que el
  usuario toca**. Y el eje no son los widgets: son las **combinaciones de estado que
  pintan cosas distintas**.
  - **Tres ejes, los tres DERIVADOS**: `corrida` (SIN_DISEÑAR · DISEÑADO_SIN_SELECCION ·
    DISEÑADO_CON_SELECCION), `fichero:<rol>` CON/SIN —uno por rol de
    `species.required_files`— y `modal:<corrida>` CON_CORRIDA/SIN_CORRIDA —uno por cada
    `corrida_*` de `store.RECORD_KINDS`—. **29 estados.**
  - **DOS NIVELES, y la distinción es el punto entero**: `PINTADO` (algún test
    **renderiza la página** con ese estado) y `CONSTRUIDO` (lo monta en el núcleo y no
    pinta). Un `CONSTRUIDO` es el principio nº 17 en esta superficie: el estado existe en
    un test y el camino que lo pinta no lo recorre nadie. **Sólo PINTADO cuenta.**
  - **Las causas eran DOS, no diecinueve**: `AppTest` no puede rellenar un
    `file_uploader` —18 estados, los ocho de los modales entre ellos— y la página no
    aceptaba un directorio de referencia de prueba —9 estados—. **Abrir cualquiera de las
    dos desbloquea todas las suyas de golpe**, así que lo que hay que hacer no es
    escribir tests sueltos: es abrir esas dos vías.
  - **LA SEGUNDA VÍA YA ESTÁ ABIERTA, y el trinquete pasó de 19 a 10.**
    `trabajo.reference_dir()` lee `os.environ` **en cada llamada** —la indirección ya
    estaba, la usaba el hub y no la usaba ningún test—, así que apuntando
    `SHMIR_REFERENCE_DIR` a un temporal la misma página pinta los nueve roles en el lado
    que se quiera. Los dos ayudantes son `deposito_vacio()` y `deposito_completo()`, en
    `tests/test_estados_de_fichero.py`, y **no hubo que tocar la página**.
    - Cinco de los diez ficheros no están en el repositorio, así que el depósito completo
      les pone un **marcador de presencia** con su motivo escrito uno a uno — y al
      escribirlos apareció que los motivos **no son el mismo**: cuatro son descargas de
      cientos de MB y `apa_medido.tsv` es que **todavía no existe**. Un motivo común
      habría tapado esa diferencia.
    - Con un marcador se pinta el estado CON **del panel**, que es lo que este eje cubre.
      No prueba que el frente corra: eso pide el fichero de verdad. Escrito donde está.
  - **Y al abrir esa vía apareció un fallo de producción a la primera corrida**
    (errata nº 34): una fila **colapsada y AUSENTE** —`apa_medido.tsv`, cuyo frente ya
    cierra PolyA_DB— salía con las cuatro acciones de un fichero presente, porque la
    página decidía con `if fila["acciones"]:` y esa lista **nunca está vacía**: una fila
    ausente lleva `["subir"]`. El panel enseñaba un error rojo al abrir la app y «Ver»
    tiraba la página entera. Ahora la fila **dice** si está (`"presente"`, en
    `presentation.py`: regla 6) y hay test de las dos cosas.
  - **LO QUE QUEDA son los diez de la MISMA causa**: `AppTest` no rellena un
    `file_uploader`, así que la página no llega a DISEÑADO y con ella se quedan fuera los
    ocho de los cuatro modales — donde vive `_modal_blast`. Es un límite de la
    herramienta, no de la app: cerrarlo pide una vía para inyectar la secuencia sin pasar
    por el widget.
  - **Los BLOQUEADOS CUENTAN para el trinquete.** Excluirlos lo dejaba en **cero** con
    diecinueve estados sin pintar — un informe que se lee como «pendiente» y no obliga a
    nada (principio nº 15). `bloqueado_por` dice **qué lo cerraría**; no exime.
  - **El detector se equivocó DOS veces antes de valer**, y las dos quedan fijadas con
    test: comparaba los niveles con `max()` de cadenas —y `max("NADA", "CONSTRUIDO")` es
    `"NADA"`, así que TODO salía sin tocar—, y reconocía los estados de fichero por el
    nombre del fichero en el fuente, **que aparece igual en un test que lo pone y en uno
    que comprueba que falta**. Ahora hay dos vías y ninguna es ésa: el **hecho** —está o
    no está en el depósito del paquete— y el **ayudante** que lleva el depósito ENTERO a
    un lado, que no nombra ningún fichero. Lo que sigue prohibido es lo de entonces, y
    hay test.

- **EL INVENTARIO DE FIXTURES SINTÉTICOS (2026-08-29)**
  (`tools/auditar_fixtures.py`, `data/fixtures_sinteticos.toml`, dentro de
  `npm run check:shmir`). Es la **segunda mitad del principio nº 18**: un parámetro
  tecleado y un fixture sintético son **la misma enfermedad**, los dos validan un camino
  que nadie recorre. `test_usar_manifiesto.py` pasaba de punta a punta sobre un
  manifiesto PARCIAL en un temporal, y el manifiesto real abortaba (errata nº 33).
  - **Fabricar NO está prohibido** —el fichero corrupto, la cabecera corta, el md5 que no
    cuadra, el manifiesto al que le falta un rol a propósito: ninguno se puede montar con
    el real—. Lo prohibido es **no decir por qué**, y el motivo va escrito en la tabla.
  - Se revisó cuántos había y el del manifiesto **no era el único**: **12 fabricaciones
    en 9 ficheros**. La tabla se cruza con el código **en las dos direcciones**: una
    fabricación sin entrada falla, y una entrada que ya no corresponde a ningún test
    también — una justificación caducada se lee como vigente, que es peor que ninguna.
  - **Lo que faltaba en el caso del manifiesto no era dejar de fabricarlo**: era que
    ADEMÁS hubiera una corrida contra el real. Las dos cosas.
  - Los artefactos salen del **directorio** `data/reference/`, no de una lista. El
    detector reconoce la fabricación por el NOMBRE cerca de una escritura, y `shutil.copy`
    **no cuenta** —copiar el real es usarlo—: meterlo daba 47 detecciones en 20 ficheros,
    casi todas tests haciendo lo correcto, y un auditor con falsos positivos se apaga.

- **LA REGLA DE LOS INERTES (2026-08-29)**, comprobada sobre **todos** los generadores de
  goldens, no sólo sobre el del CLI. **No se ponen parámetros en un artefacto de
  verificación, ni siquiera los que coinciden con el defecto.** De los cuatro que llevaba
  el golden, tres no hacían nada — y ése es el problema: **un parámetro que no hace nada
  no se distingue de uno que sí**, así que nadie los vuelve a mirar y el que rompía viajó
  de polizón entre los otros tres.
  - Lo fija `TestNingunGeneradorPONEunParametro`: `default_config()` se llama **sin
    nada**, `tile_utr` recibe la secuencia y nada más, no se construye ningún
    `SelectionConfig` a mano, y **ningún campo de `SelectionConfig` aparece como
    argumento** — esa lista se deriva de la propia clase, así que un ajuste nuevo queda
    cubierto sin que nadie se acuerde. Lo permitido en una variante tampoco es una lista
    escrita: sale de **su propio nombre**.
  - **La ironía, al registro**: dos de los generadores llevaban escrito **dos líneas más
    arriba** que la tabla de PolyA_DB no se pasa a mano, por este mismo motivo. Tenían la
    regla delante, redactada, **para el dato** — y no la vieron **para la configuración**,
    en el mismo bloque de código. Saber la regla no basta si no se aplica al eje que toca.

- **`--usar-manifiesto` VA CON UNA SOLA ESPECIE**, y no es un descuido ni un fallo. El
  manifiesto conecta `rmsk_mouse.out` **por su rol**, sin mirar qué se está diseñando, así
  que con `--fasta-b` la máscara murina acaba delante del transcrito humano y
  `RepeatMask.query_length` la rechaza —«se corrió sobre 2191 nt y se le está dando una de
  2435»—. **El guardia hace exactamente lo que debe.** Con dos especies, se conectan los
  ficheros con sus flags. Está escrito **en la ayuda de la bandera**, que es donde se mira
  antes de intentarlo, y no sólo en el mensaje del aborto.

- **EL GUARDIA DE LAS CONDICIONES QUE NO PUEDEN SER FALSAS (2026-08-29)**
  (`tools/auditar_condiciones.py`, dentro de `npm run check:shmir`). Principio nº 19, y
  sale de **tres fallos con la misma anatomía**: `x or defecto` con la cadena vacía
  (errata nº 18), `Path.is_file()` sobre un fichero de 0 bytes (errata nº 15) y
  `if fila["acciones"]` sobre una lista que nunca está vacía (errata nº 34). En los tres
  **la pregunta era por el CONTENIDO y la comprobación miró el CONTINENTE**, y el
  resultado no fue un error sino una respuesta plausible.
  - **NO es un trinquete: es un guardia.** El número correcto es CERO y cualquier
    hallazgo aborta — una rama que no puede ejecutarse no es una decisión.
  - **Es estrecho a propósito.** Se barrió el paquete por los tres ejes y el barrido
    ancho da **187 posiciones sólo en las colecciones, casi todas correctas**: en
    `if not filas` la vacuidad ES la pregunta. Un auditor así se apaga el primer día.
    Lo que sí se decide sin discusión es el caso extremo.
  - **Está probado contra el fallo que lo originó**: se le da el fuente de ANTES del
    arreglo y se exige que lo señale. Salir a cero sobre el código ya arreglado no
    demuestra nada — es el `verify()` de la errata nº 29 otra vez.
  - Distingue **TABLA de REGISTRO** (un diccionario de módulo frente a uno construido por
    fila), y eso lo cazó su propio test: sin esa distinción, un campo `presente` heredaba
    la «no vacuidad» de las claves de `ACTIONS`. La distinción dejó además sin trabajo a
    la lista de ficheros excluidos, que se retiró: dos mecanismos para lo mismo es uno de
    más.
  - **El cuarto caso NO LLEVA NINGUNA CONDICIÓN**, y es el que más enseña:
    `BreakChoice.folding_ok` tiene `= ()` por defecto y todo lo que lo lee hace
    `zip(candidates, folding_ok)`. **`zip` trunca al más corto sin decir nada**, así que
    olvidar ese campo daría un informe **sin ninguna fila y sin ningún error** — que se
    lee como un resultado. Ninguna búsqueda de `if` lo habría encontrado. Un barrido que
    sólo mire condiciones deja fuera media familia.

- **SECUENCIAS EMPAREJADAS (2026-08-30)** (`tools/auditar_pares.py`, dentro de
  `npm run check:shmir`). El barrido del otro lado: `zip`, `map` de dos iterables y las
  comprensiones sobre dos secuencias. **Catorce**, descontando las ventanas
  `zip(x, x[1:])`, que recorren pares consecutivos de UNA lista y no emparejan nada.
  - **Dos salidas y ninguna tercera**, porque son dos cosas distintas y sólo quien
    escribe la línea sabe cuál: **`strict=True`** cuando van en paralelo y diferir es un
    fallo (**diez**), o **`# zip-ok: <motivo>`** cuando la truncación es la intención
    (**cuatro**) — la misma convención que `# rule2-ok`. Dejarlo implícito no es una
    tercera opción: es que el lector adivine. Es un **guardia**, no un trinquete.
  - **Que tenga dos salidas es lo que la hace aplicable**: «pon `strict` en todos» habría
    roto cuatro sitios correctos, y una regla que rompe lo correcto se retira a la semana.
  - **Los cuatro exentos, medidos, no supuestos.** El más instructivo:
    `_donor_score` puntúa un motivo de **7 nt** contra un consenso de **5 posiciones**, y
    la consecuencia va escrita porque no es obvia — cambiar una base en la posición 6 o la
    7 **no baja la puntuación**, así que esas alternativas salen con el mismo número que
    el motivo intacto y nunca se eligen (gana el mínimo).
  - **Lo que ya estaba bien y sirvió de modelo**: `informe_doc.Block.__post_init__` lleva
    desde hace tiempo el guardia exacto para las tablas —«una fila descuadrada desplaza
    los valores a la columna de al lado y eso no da ningún error»— y protege aguas arriba
    a `pdf_writer._table_lines`, su único llamador.
  - **El detector se equivocó DOS veces, las dos HACIA EL SILENCIO**, y las dos quedan
    fijadas con test: buscaba la marca sólo dos líneas por encima —y un motivo que merece
    escribirse ocupa varias, con `# zip-ok:` en la primera— y luego la anclaba a la
    llamada en vez de a la SENTENCIA, con lo que se le escapaba el `zip` que vive dentro
    de un `return sum(...)`. Un exento no reconocido empuja a quitar el comentario y poner
    `strict` donde no toca.

- **EL REGISTRO DE ANDAMIOS (2026-08-30)** (`shmir_design/scaffold_registry.py`,
  `tests/test_registro_andamios.py`). **Cambiar de andamio NO es sustituir un flanco: es
  rediseñar el módulo entero.** Hasta hoy `blocks.PIECES` sólo tenía miR-E. El registro
  lleva cuatro cosas INDEPENDIENTES por andamio —secuencia verificada de fichero,
  contextos, regla de pasajera con su criterio, y plásmido con md5— y **la app se niega a
  montar** con uno incompleto (`require_verified`), en vez de montarlo con una regla
  prestada: saldría con la forma correcta, que es peor que no salir.
  - **La regla de la pasajera es PROPIEDAD DEL ANDAMIO, no constante global**, y está
    medido cuánto cambia: la de miR-E es revcomp con desapareamiento en la posición 1
    **elegido plegando contra SGEP**; la que miRarchitect emite para miR-30a es
    `revcomp(guía)[0:9] + revcomp(guía)[11:22] + "GC"` — dos nucleótidos borrados tras la
    posición 9 y un `GC` terminal. No se parecen en nada. Esa segunda está en
    `mirarchitect.passenger_of` **para poder descartarla**, no para diseñar.
  - **MONTAR y VERIFICAR LOS CONTEXTOS son dos ejes**, y fundirlos dejaría `mir_e` en
    NOT_RUN y la app dejaría de emitir lo único que hoy emite bien.
  - **Al montarlo salió que miR-E tampoco estaba completo** —faltaba el plásmido de SGEP,
    así que sus contextos eran coordenadas que ningún fichero confirmaba, y su test los
    probaba contra un plásmido sintético de N's: **el comprobador, no las coordenadas**
    (principio nº 18)—. **CERRADO el 2026-08-30**: llegó #111170 (8968 pb, md5
    `b15d8091…`) y `contexto5` en 1739-1758 y `contexto3` en 1856-1875 **coinciden
    exactamente**. miR-E está completo en los cuatro ejes y hay test contra el fichero.
  - **LOS DOS PLÁSMIDOS SE MIDIERON ANTES DE DESCARTARLOS**, con un CONTROL POSITIVO:
    SGEP anota su `miR-30a loop` con la misma etiqueta de 15 nt, así que centrarlo en una
    ventana de 71 nt y plegarla se puede probar donde la respuesta se conoce — y da una
    horquilla limpia (−35,10 kcal/mol, 82 % emparejada, **un** bucle terminal). Con el
    mismo método: **#20670 SÍ da horquilla** (−34,70; 73 %; un bucle; las 10 bases
    ambiguas empiezan en la 710, fuera de la ventana) → hay base para pedir la anotación.
    **#78126 NO**: su mejor ventana se queda en −26,00 y 65 %, y lo que lo decide no es
    el plegado sino que ese hueco tiene **15 dianas de restricción canónicas en 215 nt,
    una cada 12,6 y con densidad 105× la del resto del plásmido** — es un polilinker
    vacío. Descartado con motivo medido, no por ausencia de etiqueta.
  - **La ventana se DERIVA, y no era un detalle**: centrada da 126..196; el rango
    propuesto a ojo (112..183) da −20,50, 53 % y **dos** bucles. Catorce kcal/mol.
  - **Y el discriminante primero fue equivocado**: conté `)(` —tallos SECUENCIALES— y
    estas estructuras son ANIDADAS, así que ninguna tenía uno; el control positivo pasó
    **por casualidad**. Lo que separa una horquilla es cuántos BUCLES TERMINALES cierra.
    Con el criterio bueno, la mejor ventana de #78126 **sí** es una horquilla: lo que la
    descarta es la magnitud y la densidad de dianas, no la forma. Decir «ramificada»
    habría sido un diagnóstico equivocado, que cuesta más que ninguno.
  - **NINGUNO DE LOS DOS PLÁSMIDOS APORTADOS TRAE SU ANDAMIO COMO FEATURE**, y eso es el
    hallazgo, no un contratiempo: **#20670** anota únicamente el `miR-30a loop` —15 nt,
    154..168, y su propia nota dice que es el loop del precursor de 71 nt— y encima son
    771 pb **lineales** con 10 bases ambiguas desde la 710, o sea un fragmento;
    **#78126** está completo y verificado por md5 pero **no anota ninguna feature de
    miARN**: sus 34 features son el esqueleto de pcDNA3.1. Que el título diga «miR155 in
    pcDNA3.1» no es una anotación, es un texto. Buscar el andamio por secuencia contra
    una construida por nosotros es exactamente lo que prohíbe la regla 1.

- **LA MATRIZ INTRÓN × ANDAMIO (2026-08-30)** (`shmir_design/matriz_andamio_intron.py`).
  **Los dos registros NO son independientes**, y tratarlos como 12 combinaciones sueltas
  permite construir pares que no resuelven nada: `mvm_sin_criptico` existe **sólo** para
  romper el `GTGAGCG` del flanco 5' de miR-E, así que con un andamio que no lo lleve es
  la misma construcción con otro nombre.
  - **Los motivos se buscan en la SECUENCIA REAL del módulo montado**, nunca por familia
    ni por analogía, y el contexto de donante se puntúa **contra el donante legítimo del
    propio intrón** — referencia interna, el mismo criterio que cazó el `GTGAGCG`.
  - **Lo medido sobre `mvm_actual` × `mir_e`**, el único par evaluable hoy: **UN** donante
    críptico en los 149 nt del módulo, y es el conocido — `GTGAGCG` en +38, con score
    **5, el mismo que el donante legítimo** (`GTAAGGG`). Por eso compite, y por eso no
    hace falta ningún umbral de fuera para decirlo. Cae en el flanco 5' del andamio, así
    que **viaja con cualquier guía**.
  - **NINGÚN aceptor utilizable dentro del módulo**: el mejor tracto de cualquier `AG` son
    **2** pirimidinas contiguas contra las **9** del aceptor legítimo. Eso cierra **por
    secuencia** los empalmes que cortarían por dentro de la horquilla.
  - **Un YTNAY (`TTGAC` en +32) y NO define ningún intrón**: va **aguas arriba** del
    donante —el orden contrario al que haría falta— y no hay aceptor. El peor caso sería
    donante, punto y aceptor los tres dentro y en ese orden; se comprueba el ORDEN, no
    sólo la presencia.
  - **1 de 12 evaluable, y los `NOT_RUN` tienen DOS causas distintas** (9 + 2). Fundirlas
    diría «falta un fichero de andamio» sobre algo que ningún andamio arregla:
    `intron_quimerico` llega **entero** y no declara sus puntos de inserción, y
    `mvm_sin_criptico` se **diseña por candidato** y hoy el primer paso empata. El motivo
    lo da el propio intrón; no se transcribe en la matriz.
  - **La redundancia se MARCA, no se elimina**: la decisión de no sintetizar es de quien
    diseña. Y `aviso_de_par` lo dice **al montar**, como el aviso de núcleo de seed
    compartido — sin impedirlo.
  - **`None` no es `False`, y decide qué se hace**: «el andamio no lleva el motivo»
    descarta el par; «no se ha mirado» manda a conseguir el fichero. El aviso nunca
    declara redundancia sobre un andamio sin evaluar.
  - **El aviso pregunta por el ANDAMIO, no por el par**: el módulo se monta con el andamio
    y la guía, y el intrón lo envuelve. Atarlo al par hacía que dijera «no se puede
    comprobar» sobre miR-E —donde el motivo está y está medido— sólo porque la variante
    de intrón todavía no se ha diseñado.

## Ficheros que faltan (por eso hay filtros en NOT_RUN)

Ninguno se sustituye por una lista interna ni por nada reconstruido. Mientras falten, su
filtro queda en `NOT_RUN` y los candidatos salen `INCOMPLETE`:

| Fichero | Qué desbloquea | Flag |
|---|---|---|
| RefSeq RNA versionado | especificidad | `--refseq` |
| lista ampliada de abundancia (con referencia y umbral) | colisión de seed, nivel AVISO | `--abundancia` |
| 3'UTR del transcriptoma (UCSC Table Browser, mm39, NCBI RefSeq, «3' UTR Exons»; hay que apuntar ensamblaje, fecha de la tabla y criterio de representante) | carga de off-targets por seed — el TERCER modal, `offtarget_seed` | `--transcriptoma-3utr` o el modal |
| máscara rmsk de ratón | elementos repetitivos | `--rmsk` |
| 3'-end seq de cerebro murino — **es el caso del rol `apa_medido`** (`apa_medido.tsv`, posiciones ya convertidas a 3'UTR con su fracción) | fracción de isoforma larga en NUESTRO tejido (hoy hay la de todos los tejidos: 0,86, límite inferior). **Al llegar, lo primero es cruzar su techo con el de PolyA_DB**: hoy los dos se calculan por caminos independientes y nada obliga a que coincidan | se sube por el gestor |
| **`apa_medido_human.tsv`** — PolyA_DB v4 para **PRNP / hg38** | que el humano deje de estar en **MODO ASUMIDO**. La tabla murina se aplica por md5 del 3'UTR, así que sobre el humano devuelve `None` y sus dos `ATTAAA` (`3utr:955` y `3utr:1167`) siguen clasificadas por **canonicidad y sin un solo dato de uso**. Es exactamente donde estaba el ratón antes de mirar PolyA_DB — y allí el modo sin medida resultó ser el **equivocado**. **La entrada existe y quedó pendiente** desde que se miró la murina: es la misma consulta cambiando la especie en el selector | se sube por el gestor |
| parental SIN INTRÓN (donante y aceptor fuera) | techo de expresión para el empalme; `aav_casete.fa` NO vale, lleva el intrón vacío de 82 nt | — |
| tabla de expresión | ponderar la carga de seed | `--expresion` |
| **`hairpin.fa` de miRBase** (los PRECURSORES; el que hay es `mature.fa`, los maduros) | **los tres cálculos de miR-451**. El pre-miR-451 nativo es a la vez el andamio y la referencia contra la que se comparan los diez candidatos, y del maduro no se deriva: reconstruirlo es la regla 1. También localizaría el precursor de miR-155 dentro del hueco sin anotar de #78126 | se sube por el gestor |
| export de **Addgene #20670** con el precursor de miR-30a anotado, o sus coordenadas | el andamio **miR-30 original**. Plegando la ventana de 71 nt centrada en el loop anotado **sí sale horquilla** (−34,70; 73 %; un bucle) frente al control de SGEP (−35,10; 82 %; un bucle): hay base para pedir la anotación, pero anotado no está | se sube por el gestor |
| **otro plásmido de miR-155** | el andamio **miR-155**. #78126 queda **DESCARTADO con motivo medido**: su único hueco sin anotar es un polilinker vacío — 15 dianas de restricción canónicas en 215 nt, densidad **105×** la del resto — y su mejor ventana de 71 nt se queda en −26,00 y 65 % | se sube por el gestor |
