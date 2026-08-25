# Estado del proyecto — resumen para quien continúe

Documento de traspaso. Dice **qué está hecho, qué está verificado con datos reales, qué
está bloqueado y qué no se puede romper**. Si vas a tocar código, lee además
[`CLAUDE.md`](./CLAUDE.md), que es vinculante.

Última actualización: 2026-08-25 (tanda de diez bloques). Todo lo descrito aquí
está en `main`.

---

## 1. Qué es y cómo se abre

Diseñador de shmiRs: de uno o dos 3'UTR a una lista corta de candidatos y sus oligos de
97 nt listos para pedir. Python 3.11+, **stdlib pura** en todo el núcleo y los CLI. La
única dependencia externa es Streamlit, y solo para la interfaz web.

Tres puertas de entrada, el mismo núcleo detrás:

```bash
# 1. Desde el hub: Batchwork → Laboratory tools → «Diseñar shmiRs (3′UTR → oligos)»
#    Subes uno o dos FASTA, ajustas umbrales, descargas un ZIP con las seis salidas.

# 2. CLI
python3 apps/shmir-design/tools/design.py --fasta a.fa --name raton \
    --fasta-b b.fa --name-b humano --out salida/

# 3. Interfaz web (opcional)
pip install -r apps/shmir-design/requirements-ui.txt
streamlit run apps/shmir-design/ui/streamlit_app.py
```

Comprobaciones:

```bash
npm run test:shmir     # 882 tests, 15 saltados (los saltados esperan fixtures)
npm run check:shmir    # verificador de la regla 2 sobre el AST, 74 ficheros
npm test               # suite del hub Node, 257 tests (no la rompe nada de aquí)
```

No confundir el proyecto con `apps/batchwork/`, que es la app de operaciones por lotes
del hub: aquí solo la usamos como puerta de entrada, mediante un puente de 30 líneas
(`apps/batchwork/python/shmir_design_run.py`) que llama al CLI y no contiene lógica.

---

## 2. Estado por paso del pipeline

El orden de operaciones es **no negociable** y está en [`docs/pipeline.md`](./docs/pipeline.md).

| # | Paso | Estado | Dónde |
|---:|---|---|---|
| 0 | Carga de referencias + verificación de checksum | **hecho** | `reference.py`, `tools/reference_data.py` |
| 1 | Anatomía del transcrito (ORF, UTRs) | **hecho**: tres vías (`--genbank`, `--cds`, `--region 3utr`), procedencia impresa, y **no hay fallback silencioso** | `anatomy.py`, `genbank.py`, `orf.py` |
| 2 | Enmascarado de repeticiones → RETILAR | **hecho**, lee `.out` de RepeatMasker y tabla rmsk de UCSC; falta el fichero | `masking.py` |
| 3 | Tiling de 22-meros | **hecho** | `tiling.py` |
| 4 | GC 0.30–0.52 | **hecho** | `hard_filters.py` |
| 5 | Sin homopolímeros ≥4 | **hecho** | `hard_filters.py` |
| 6 | U forzada en la posición 1 de la guía | **hecho** | `hard_filters.guide_from_target` |
| 7 | Asimetría ≥ +0.5 kcal/mol | **hecho** (proxy heurístico, ver §5) | `thermo.py` |
| 9b | Filtro de poliadenilación escalonado + sensibilidad de la penalización | **hecho** | `polya.py`, `selection.penalty_sensitivity` |
| — | Anatomía declarada: región y dobles coordenadas | **hecho** | `anatomy.py` |
| — | Plegado del 97-mero (ViennaRNA, opcional) | **hecho** | `folding.py` |
| — | Módulo NheI–SacI de 149 nt | **hecho** | `gblock.py` |
| 8 | Sin motivo G-cuádruplex | **hecho**, sobre diana **y** guía | `hard_filters.py` |
| 9 | polyA como **anotación** de cinco campos + tres modos | **hecho** | `polya.py` |
| 10a | Colisión de seed con miARN endógeno (dos niveles) | **hecho**; falta `mature.fa` y la lista de MirGeneDB | `mirna.py` |
| 10b | Carga de off-targets por seed (número comparativo) | **hecho**; falta el FASTA de 3'UTR del transcriptoma | `seed_load.py` |
| 11 | Variantes con AF > 0.001 (gnomAD) | **no empezado** | — |
| 12 | Especificidad (escaneo exhaustivo local + BLAST de inspección) | **hecho**; falta el fixture de RefSeq RNA | `specificity.py` |
| 12b | Transgén AAV como segunda base de especificidad | **hecho**; falta el FASTA del casete | `specificity.filter_transgene` |
| 13 | Accesibilidad de la diana (desempate, nunca filtro) | **hecho** con ViennaRNA 2.7.2; `--accesibilidad` | `accessibility.py` |
| — | APA con sitios medidos (PolyA_DB / PolyASite) | **hecho**; falta la tabla | `apa.py` |
| — | Ventana de tilado explícita | **hecho** | `anatomy.TileRange` |
| — | Cuota por región y estado `NO_APLICA` | **hecho** | `selection.py`, `filters.py` |
| — | Tabla comparativa + `knockdown_medido` + reparto por rango | **hecho** | `comparative.py`, `selection.coverage_report` |
| 14 | Bloques conservados | **hecho** | `conservation.py` |
| 15 | Sitios + selección voraz (50 nt, cuota por tercio, N=6) | **hecho** | `selection.py` |
| — | Horquilla miR-E de 97 nt | **hecho** | `scaffold.py`, `tools/oligo.py` |
| — | Seis salidas | **hecho** | `outputs.py`, `comparative.py`, `tools/design.py` |
| — | Interfaz Streamlit | **hecho** | `presentation.py` + `ui/streamlit_app.py` |
| — | Operación en el sidebar de Batchwork | **hecho** | `apps/batchwork/server/operations/shmir-design.js` |

---

## 3. Las seis salidas

Por especie, con el mismo contenido en las tres puertas de entrada:

| Fichero | Qué |
|---|---|
| `{especie}_ventanas.tsv` | TODAS las ventanas, una columna por filtro, con `PASS`/`FAIL`/`NOT_RUN` por separado — nunca un booleano agregado |
| `{especie}_seleccionados.tsv` | los candidatos, con rango por asimetría, tercio, veredicto y filtros sin correr |
| `{especie}_guias.fasta` | las guías en ADN, para BLAST (paso 12, manual en la v1) |
| `{especie}_oligos.tsv` | la horquilla de 97 nt de cada candidato, **con sus avisos en cada fila** |
| `{especie}_comparativa.tsv` | **la tabla del bloque 6**: los N elegidos con todos los parámetros lado a lado y una columna `knockdown_medido` VACÍA para que vuelva rellena del laboratorio |
| `{especie}_informe.txt` | anatomía y su procedencia, rango tilado, polyA bajo los tres modos, repeticiones, seed, especificidad, transgén, APA, accesibilidad, rango cubierto por la selección y **qué filtros no se ejecutaron** |

---

## 4. Los dos contadores, que no son lo mismo

- **`biofisicos_ok`** — ventanas que superan los seis filtros que solo dependen de la
  secuencia: GC, homopolímero, asimetría, G4 diana, G4 guía y zona prohibida de
  poliadenilación. Es el contador de referencia: comprobable sin red y sin fixtures.
- **`aptas`** — ventanas con veredicto `PASS`, que además superan los filtros externos.
  **Hoy es 0**, y debe serlo: con miRBase, gnomAD, RefSeq, el casete del transgén y
  `rmsk` ausentes, esos filtros están en `NOT_RUN`, y `NOT_RUN` no es `PASS`.

Un tercer valor que **no** es ninguno de los dos: `NO_APLICA`. Marca las preguntas que
no van con ese candidato (polyA sobre una ventana del ORF). No es una laguna, así que no
impide aprobar — pero si TODO sale `NO_APLICA`, el veredicto es `INCOMPLETE`.

Mezclarlos es exactamente el fallo que hace que un candidato incompleto parezca
aprobado. Son dos métodos, dos columnas del TSV y dos líneas del informe.

---

## 5. Qué está verificado con datos reales y qué no

**Verificado** (hay test con el dato real):

- Anatomía y checksums de `NM_011170.3` (ratón, 2191 nt) y `NM_000311.5` (humano, 2435 nt).
- Señales de poliadenilación: `AATAAA` en 288 del ratón → APA posible; `ATTAAA` en 1214
  y en 1582 → señal terminal; ventana humana 1581 excluida por solape.
- Bloque conservado de 26 nt `TTTTCTATATTTGTAACTTTGCATGT`, GC 23.1%, humano 1507–1532,
  ratón 1138–1163, y sus 5 ventanas de 22 nt.
- Asimetría: los cinco valores del bloque (−2.60, −2.98, −1.55, **+0.77**, −0.60) y dos
  guías de cordura biológica que detectarían una inversión de signo.
- Ventana humana 1237: guía `UAAAGUGCAAGCCAAUAAUAAC`, GC 0.364, asimetría +1.76, seed
  `AAAGTGC` → familia miR-17/20/93/106.
- Horquilla miR-E de SGEP (#111170): el 97-mero se reconstruye byte a byte.

**No verificado, y marcado como tal en el código:**

- **La asimetría es un proxy heurístico, no una energía libre de dúplex.** La
  penalización terminal AU se aplica también en el límite interno del tetrámero, donde
  no hay fin de hélice real. Sirve para **ordenar**, no para publicar.
- **La regla del desapareamiento de la pasajera** (transición T↔C en la posición 1) está
  derivada de un solo ejemplo. Marcada `REGLA_NO_CONFIRMADA`; el aviso sale en cada
  salida de oligos. Si el complementario reverso empieza por A o G, el caso **no** está
  cubierto: no se toca la base y se avisa. Para cerrarlo hace falta un segundo plásmido
  miR-E con otra guía (LT3GEPIR #111177).
- **Los flancos extendidos del pri-miR** (cassette AAV) siguen sin decidir.
  `extended_cassette()` aborta en vez de inventarlos.
- **Los conteos 302/96 (ratón) y 323/97 (humano)**: el test está escrito y **saltado**
  hasta que existan los fixtures. Nadie los ha visto pasar todavía.

---

## 6. Bloqueantes

1. **Faltan los dos FASTA** en `data/reference/`: `NM_011170.3.fa` y `NM_000311.5.fa`.
   Sin ellos, 15 tests se saltan de forma visible. Con ellos, se ponen en verde solos.
   No se sustituyen por secuencia sintética (regla 1). **Esto es lo que impide tilar el
   3'UTR humano**, que estaba pedido en esta tanda: el código lo soporta entero, pero no
   hay secuencia que tilar.
2. **La política de red del entorno de desarrollo bloquea** NCBI, Ensembl, UCSC, gnomAD
   y miRBase (403 al CONNECT). Por eso ninguna URL está escrita en el código y `--fetch`
   exige `--efetch-url`. `pypi.org` sí es accesible.
3. **Faltan los ficheros externos.** Todos tienen ya su lector, su checksum y su flag; lo
   único que falta es el fichero. Mientras falten, su filtro está en `NOT_RUN`:

   | Fichero | Desbloquea | Flag |
   |---|---|---|
   | RefSeq RNA versionado | especificidad (paso 12) | `--refseq` |
   | `mature.fa` de miRBase | colisión de seed, nivel aviso | `--mirbase` |
   | lista de MirGeneDB | colisión de seed, nivel FAIL | `--abundancia` |
   | 3'UTR del transcriptoma | carga de off-targets por seed | `--transcriptoma-3utr` |
   | `.out` de RepeatMasker o tabla rmsk | elementos repetitivos (paso 2) | `--rmsk` |
   | FASTA del casete AAV completo | filtro del transgén | `--transgen` |
   | PolyA_DB / PolyASite | APA medido en vez de predicho | `--apa-medido` |
   | tabla de expresión cerebral | ponderar la carga de seed | `--expresion` |
   | export de gnomAD | paso 11, **sin implementar** | — |

   El patrón está en [`docs/fixtures.md`](./docs/fixtures.md): descarga manual, checksum
   registrado, carga por una función que aborta si no cuadra.
4. **El importador de PolyA_DB / PolyASite lee un formato propio**
   (`posicion<TAB>fraccion<TAB>nombre`), no el volcado original. No se adivinó el reparto
   de columnas de un fichero que nadie ha visto (regla 4). Con un volcado real de
   ejemplo, el importador se escribe.

---

## 7. Decisiones tomadas que conviene confirmar

Están en [`docs/preguntas-abiertas.md`](./docs/preguntas-abiertas.md). Las que más pesan:

- **El espaciado de 50 nt se mide entre posiciones de inicio** de los candidatos: 50
  exactos valen, 49 no. La alternativa (hueco entre ventanas) daría 28 nt de separación
  real para el mismo umbral.
- **El límite del riesgo de APA es la señal, no el sitio de corte** (que cae 10–30 nt
  aguas abajo). Sobre-marca unas 25 ventanas, a propósito. No es una predicción del
  extremo de la isoforma corta.
- **Una ventana con `N` no es evaluable**: sus filtros de secuencia salen `NOT_RUN`,
  nunca `PASS` ni `FAIL`. La seed es más fina: solo `NOT_RUN` si la `N` cae en las
  posiciones 2–8, porque el resto de la guía no la determina.
- **El semáforo de la interfaz mira los candidatos seleccionados**, no todas las
  ventanas. Con la definición literal el verde era inalcanzable en cuanto se enmascara
  algo, porque una ventana enmascarada tiene `N` y nunca se evalúa.
- **En Batchwork, el nombre de la especie sale del nombre del fichero**, para no tener
  que adivinar cuál es el modelo y cuál la diana.

---

## 8. Invariantes que no se pueden romper

1. **Nunca generar, completar ni reconstruir una secuencia.** Si falta, se aborta. Los
   únicos tramos de secuencia real del repositorio son los listados en
   `data/reference/PROCEDENCIA.md`; lo demás son sondas etiquetadas
   (`PROBE-NOT-A-SEQUENCE`, andamios de `N`, sondas de umbral).
2. **Ningún `except` se traga un fallo.** `npm run check:shmir` lo comprueba sobre el
   AST. Un `except` que no relanza necesita un comentario `# rule2-ok: <motivo>` y solo
   vale para excepciones concretas.
3. **`NOT_RUN` no es `PASS`.** Un filtro ausente no es un filtro superado. Y `NO_APLICA`
   no es una cuarta forma de `NOT_RUN`: significa que la pregunta no va con ese
   candidato, no que no se pudiera responder. Nunca se usa para esquivar un filtro que
   sí aplicaba.
4. **Los checksums viven en código con test** (`test_reference.py`), no solo en un `.md`:
   uno que solo vive en documentación se puede ajustar para que un fichero pase.
5. **Los avisos de oligo no se pueden silenciar.** No hay parámetro para ello en ninguna
   función ni CLI, y hay un test que lo comprueba por firma.
6. **La interfaz no tiene lógica.** Lo que decide algo vive en `presentation.py` con
   tests. Si la UI empieza a decidir, se mueve al núcleo.
7. **El orden de operaciones del paso 15 no se cambia**: enmascarar y RETILAR, filtros
   duros, ordenar por asimetría, agrupar en sitios, selección voraz.
8. **Los tests van antes que la funcionalidad**, y con datos reales.
9. **La anatomía no se adivina.** No existe ningún camino que convierta un "no sé" en un
   "todo es 3'UTR": `Anatomy.whole_is_utr3` exige declarar la procedencia por nombre, y
   `orf.py` no importa el módulo de anatomía (hay un test sobre el propio fuente).
10. **Un número comparativo que no se calculó va vacío, nunca a cero.** Cero sitios de
    seed y no haber contado son cosas distintas, y la tabla no las confunde.
11. **La columna `knockdown_medido` se queda vacía.** Es el instrumento con el que se
    sabrá qué parámetros predicen potencia; rellenarla desde el código la inutiliza.
12. **La accesibilidad nunca filtra.** Es el criterio peor predicho del pipeline y va
    solo de desempate.

---

## 9. Erratas ya corregidas — no las resucites

| Valor viejo | Por qué estaba mal | Valor bueno |
|---|---|---|
| 181 / 231 PASS | especificación de la asimetría con el signo invertido | — |
| 302 / **322** | mezclaban un filtro de seeds que solo afectaba al humano | **302 / 96** y **323 / 97**, solo biofísicos |
| «el mejor del bloque es el offset 1» | mismo error de signo | el mejor es el **offset 3** (+0.77) |
| «pasajera = revcomp exacto» | lleva un desapareamiento deliberado en la posición 1 | **resuelto**: la posición 1 nunca es el complemento Watson-Crick de la posición 22 de la guía |
| «transición T↔C» / «por defecto A» | regla trasplantada del diseño de miR-451, que es otra geometría; se generalizó desde una sola guía acabada en C sin volver a mirar el ejemplo de referencia | superada por la siguiente |
| «C por defecto, A cuando la C está prohibida» | tabla por terminación a la que le faltaba el apareamiento **tambaleante G:U**: con guía acabada en G también está prohibida la T, y la A —que no aparea con nada— deja un bulge de **2 nt** en vez de 1. Falla en 2 de 5 guías acabadas en G | **criterio estructural**: se pliegan las cuatro y se elige una que reproduzca la notación punto-paréntesis de SGEP; C > A > G > T sólo desempata |
| `--fasta` sin `--cds` tilaba el transcrito entero como 3'UTR | fallback silencioso a `whole_is_utr3`. En la corrida real sobre `NM_011170.3` metió las 744 ventanas del CDS y las 163 del 5'UTR en el mismo saco que las 1221 del 3'UTR, con 71 y 41 marcadas elegibles | **aborta** enumerando las tres vías; la procedencia sale en el informe |
| «la zona prohibida de polyA es simétrica ±10 nt» | el corte ocurre 10–30 nt **aguas abajo** del hexámero, que se queda dentro del ARNm maduro | la zona prohibida es **asimétrica y desplazada aguas abajo**; FAIL solo pasado el corte máximo |
| `seed` y `seed_colision` como dos columnas a la vez | responden a la misma pregunta con distinta profundidad, y la peor parecía igual de autorizada | con miRBase cargado, `seed` sale `NO_APLICA` remitiendo a la otra |

---

## 10. Qué falta, por orden de valor

1. Los dos `.fa` en `data/reference/` → desbloquea 12 tests y la primera ejecución real.
2. `mature.fa` de miRBase → cierra el paso 10 (la mecánica ya está). Pide un `head -8`
   del fichero real antes de escribir su parser: el formato no se supone.
3. Fixture de `rmsk` → cierra el paso 2 (el lector ya está).
3b. Fixture de RefSeq RNA de cada especie → cierra el paso 12 (el motor ya está).
    **El hueco más importante que quedará abierto aun así son los off-targets mediados
    por seed**: ningún alineador los devuelve, hacen falta 7mer-m8/8mer ponderados por
    expresión o siSPOTR/POTS.
4. Paso 11 (gnomAD): es el único paso del pipeline sin empezar.
5. Segundo plásmido miR-E (#111177) → confirma o corrige la regla de la pasajera.
6. Importador del volcado original de PolyA_DB / PolyASite, cuando haya un fichero de
   ejemplo que mirar.
7. Pantalla a medida dentro de Batchwork (semáforo, mapa, tabla) si se quiere la
   experiencia de la Streamlit dentro del hub: el backend ya es el mismo, cambiaría
   devolver JSON en vez de un ZIP.
8. Correlacionar la columna `knockdown_medido` cuando vuelva del laboratorio. Ese
   análisis es el que dirá qué parámetros predicen potencia; hasta entonces el orden por
   asimetría es una convención, no un resultado.

---

## 11. Mapa de ficheros

| Ruta | Qué |
|---|---|
| `shmir_design/errors.py` | Excepciones; ninguna se captura para silenciarla |
| `shmir_design/filters.py` | `PASS`/`FAIL`/`NOT_RUN`, agregación, conjunto biofísico |
| `shmir_design/reference.py` | Registro verificado, checksums, carga de fixtures |
| `shmir_design/fetch.py` | Descarga opcional; **sin ninguna URL** |
| `shmir_design/anatomy.py` | Regiones, `RegionSource`, dobles coordenadas, `TileRange` |
| `shmir_design/genbank.py` | CDS anotado de un `.gb` suministrado; de aquí no sale secuencia |
| `shmir_design/orf.py` | Propone un marco e imprime el `--cds`; **nunca decide** |
| `shmir_design/polya.py` | Señales, anotación de cinco campos, tres modos, tercios, TSV |
| `shmir_design/apa.py` | APA con sitios medidos y techo de knockdown |
| `shmir_design/thermo.py` | Proxy de asimetría (Turner 2004) |
| `shmir_design/hard_filters.py` | Filtros de ventana y `Thresholds` ajustables |
| `shmir_design/seeds.py` | Seed 2–8 y lista de arranque (se retira si hay miRBase) |
| `shmir_design/mirna.py` | Colisión de seed con miARN endógeno, en dos niveles |
| `shmir_design/seed_load.py` | Carga de off-targets por seed: 7mer-m8, 7mer-A1, 8mer |
| `shmir_design/specificity.py` | Especificidad y transgén, mismo motor |
| `shmir_design/accessibility.py` | Accesibilidad de la diana; desempate, nunca filtro |
| `shmir_design/comparative.py` | Tabla comparativa y columna `knockdown_medido` |
| `shmir_design/masking.py` | Enmascarado de repeticiones |
| `shmir_design/tiling.py` | Tiling, contadores, sitios |
| `shmir_design/conservation.py` | Bloques idénticos entre dos 3'UTR |
| `shmir_design/selection.py` | Selección voraz con espaciado y cuota |
| `shmir_design/scaffold.py` | Andamio miR-E parametrizable y horquilla |
| `shmir_design/outputs.py` | Las seis salidas |
| `shmir_design/presentation.py` | Semáforo, tablas, mapa SVG, descargas |
| `tools/` | CLIs: `design`, `tiling_report`, `conservation_report`, `oligo`, `reference_data`, `check_rules` |
| `ui/streamlit_app.py` | Interfaz, sin lógica |
| `config/andamio.example.toml` | Andamio parametrizable, `verificado = false` por defecto |
| `docs/` | pipeline, fixtures, valores esperados, preguntas abiertas, endpoints, dependencias |
| `apps/batchwork/python/shmir_design_run.py` | Puente Batchwork → CLI, sin lógica |
| `apps/batchwork/server/operations/shmir-design.js` | Operación del sidebar |
