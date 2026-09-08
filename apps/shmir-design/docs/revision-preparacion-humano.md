# Revisión antes de empezar con el humano

**Qué es esto.** Una revisión del código con una pregunta concreta —*¿qué se rompe al
cambiar de especie?*— hecha **corriendo el camino humano de verdad**, no leyéndolo. Cada
hallazgo trae la medida que lo sostiene; los que no se han podido medir se dicen como
tales.

**Línea base, comprobada antes de tocar nada** `[DERIVADO 2026-09-08]`:

| | resultado |
|---|---|
| suite de `apps/shmir-design/` | **5201 tests, OK**, 8 saltados |
| suite del hub (`npm test`) | **368 tests, 0 fallos** |
| `npm run check:shmir` | verde |
| `npm run check:tildes` | verde |

O sea: **nada de lo que sigue lo caza la suite hoy**. Todo son huecos que sólo aparecen
con el humano como **especie de diseño**, y ésa es la razón de que ninguno haya salido
en cuatro meses de ratón.

---

## Resumen: dónde está el riesgo

El pipeline humano **funciona**. Lo que no está listo es la **capa que elige qué fichero
alimenta a qué filtro**, y ahí hay un fallo que produce veredictos con la forma correcta
y el significado equivocado — la definición que este proyecto usa para «el peor
resultado posible».

| # | hallazgo | gravedad | dónde |
|---|---|---|---|
| **A1** | El CLI conecta los ficheros **murinos** a un diseño humano | **bloqueante** | `tools/design.py` |
| **A2** | El casete no tiene guardia de especie | **bloqueante** | `specificity` / `resources` |
| **A3** | `apa_medido.tsv` no lleva `utr3_md5`: se aplica a cualquier secuencia | alta (latente) | `apa.ApaSites` |
| **B1** | Seis mensajes nombran el fichero murino | media | `offtarget`, `selection` |
| **B2** | `cassette_deposit_check` pide el nombre a la tabla ciega a la especie | media | `presentation` |
| **B3** | Tres fichas de obtención nombran ficheros murinos en su prosa | media | `data/obtencion/` |
| **C1** | El modal de seed no dice que el núcleo es una **lista prestada** | media | `seed_scan` |
| **D1** | Ningún golden tiene al humano como especie de diseño | estructural | `tests/golden/` |
| **D2** | El inventario de estados no tiene eje de **especie** | estructural | `data/estados.toml` |

### ESTADO (2026-09-08) — los NUEVE cerrados

Va aquí y el hallazgo se queda entero abajo, con la misma disciplina que un frente
CERRADO que no desaparece del informe: borrar lo que se encontró dejaría al siguiente
lector sin saber si se resolvió o si nadie lo miró (principio nº 15).

| # | estado | dónde queda escrito |
|---|---|---|
| **A1** | **CERRADO** | errata nº 155 · `--usar-manifiesto` conecta por especie |
| **A2** | **CERRADO** | errata nº 156 · `check_cassette_species` en la ingesta |
| **A3** | **CERRADO** | errata nº 156 · `ApaSites.utr3_md5` obligatorio |
| **B1** | **CERRADO** | errata nº 157 · `offtarget.missing_file(species)` |
| **B2** | **CERRADO** | errata nº 157 · el nombre sale de `species.required_files` |
| **B3** | **CERRADO** | errata nº 157 · las fichas nombran el ROL |
| **C1** | **CERRADO** | errata nº 157 · `mirna.core_list_note` |
| **D1** | **CERRADO** | `humano_informe__con_usar_manifiesto__una_especie.txt` |
| **D2** | **CERRADO** | eje `especie` en `data/estados.toml`, con sus cuatro valores PINTADOS |

**Y el guardia que queda de los tres de la letra B no es el arreglo: es
`tests/test_NINGUN_MENSAJE_nombra_el_fichero_de_OTRA_ESPECIE.py`**, que mide lo que la app
EMITE en una corrida humana — los mensajes se pueden volver a escribir, y lo que no puede
volver a pasar es que salgan.

---

## A1 — El CLI conecta los ficheros MURINOS a un diseño humano

**Es la quinta divergencia entre los dos frontales**, la misma clase que obligó a
escribir `resolve.py`.

- La **página** conecta por especie: `load_from_manifest(dir, species=resolve(nombre))`.
- El **CLI** conecta por rol y **sin especie**: `conectar_desde_manifiesto` usa
  `manifest.roles_available`, que empareja por el **nombre del fichero** contra
  `manifest.ROLES` — una tabla que trae los nombres **murinos** escritos.

### Medido, corriendo el CLI con el humano y una sola especie

```
python3 tools/design.py --fasta data/reference/NM_000311.5.fa --name humano \
        --genbank data/reference/NM_000311.5.gb --usar-manifiesto --out …
```

```
  --usar-manifiesto conecta:
    mature.fa                → colisión de seed          (correcto: no lleva especie)
    aav_casete.fa            → filtro del transgén       ← MURINO
    rmsk_mouse.out           → elementos repetitivos     ← MURINO

PARA — rmsk_mouse.out se corrió sobre 2191 nt y se le está dando una secuencia
       de 2435 nt: no son la misma. Se aborta el enmascarado.
```

**El guardia de la máscara hace su trabajo y por eso aborta.** Lo que tapa es que, en la
misma corrida, **el casete murino ya se había conectado como filtro del transgén** — y
ahí no hay ningún guardia.

### Y la otra mitad: el CLI no reconoce NINGÚN fichero humano

`manifest.role_of` sobre los diez ficheros que `species.required_files` pide para humano:

| fichero que pide el gestor | rol que el CLI le asigna |
|---|---|
| `rmsk_human.out` | **NINGUNO** |
| `mirgenedb_cerebro_human.txt` | **NINGUNO** |
| `transcriptoma_3utr_human.fa` | **NINGUNO** |
| `expresion_cerebro_human.tsv` | **NINGUNO** |
| `refseq_rna_human.fa` | **NINGUNO** |
| `aav_casete_human.fa` | **NINGUNO** |
| `apa_medido_human.tsv` | **NINGUNO** |
| `polya_db_human.tsv` | **NINGUNO** |
| `mature.fa` | `mirbase` ✔ |
| `addgene_111170.gb` | `plasmido_andamio` ✔ |

**2 de 10.** Los ocho que llevan sufijo de especie son invisibles para el CLI, y en su
lugar se conectan los ocho murinos.

**Consecuencia práctica:** hoy no se puede correr una campaña humana por consola —y el
generador de goldens es el CLI, así que tampoco se puede fijar un artefacto humano
(ver D1).

**Arreglo:** `conectar_desde_manifiesto` recibe la especie y resuelve por
`species.required_files`, igual que la página. `manifest.ROLES` se queda como el caso
base del manifiesto que ya existe, que es lo que su propia documentación dice que es.

---

## A2 — El casete no tiene guardia de especie

`RepeatMask.query_length` protege la máscara: compara lo que el resumen declara haber
analizado contra lo que se le da, y aborta. **El casete no tiene nada equivalente.**

### Medido: el casete murino sobre el diseño humano

Reproduciendo lo que el CLI conecta, pero sin la máscara para que no aborte antes:

| corrida | `transgen` por ventana |
|---|---|
| humano, **sin** casete (correcto) | `sin: 2414` |
| humano, con el casete **murino** conectado | **`PASS: 415`**, **`FAIL: 4`**, `NOT_RUN: 1995` |

**415 ventanas humanas salen `PASS` contra una construcción que no es la suya, y 4 salen
`FAIL`.** Un `PASS` cuenta como frente contestado; un `FAIL` retira un candidato. Los
cuatro `FAIL` no cayeron en el panel de esta corrida — pero eso es suerte de esta
secuencia, no una propiedad del mecanismo.

**Arreglo:** el casete declara su especie —o su md5 se ata a la del diseño— y
`filter_transgene` aborta si no coinciden. Es el mismo patrón que `query_length`, un
rol más allá.

---

## A3 — `apa_medido.tsv` se aplicaría a cualquier secuencia

Los **dos** ficheros de APA no están igual de protegidos:

| rol | fichero | guardia de identidad |
|---|---|---|
| `polyadb` | `polya_db_<especie>.tsv` | **`utr3_md5` obligatorio** en la cabecera; `resolve_measured` compara y devuelve `None` si no cuadra |
| `apa` | `apa_medido_<especie>.tsv` | **ninguno** — `ApaSites` lleva `source`, `version` y `checksum` del fichero, y **no** el md5 del 3'UTR |

`apa_assessment(window_start, sites, predicted_risk)` aplica las posiciones **ya
convertidas a coordenadas de 3'UTR** a lo que se le dé. Unas posiciones murinas sobre el
3'UTR humano caen dentro de rango —1606 nt contra 1242— así que **no salta ninguna
alarma** y el techo de knockdown sale con la forma correcta.

Hoy es **latente**: el fichero no existe para ninguna especie. Pero es justo el que la
campaña humana necesita (`apa_medido_human.tsv` está en la lista de lo que falta), así
que la primera vez que se use será la primera vez que se pruebe.

**Arreglo:** `utr3_md5` obligatorio en la cabecera de ese formato también, con la misma
regla que ya tiene PolyA_DB.

---

## B — Mensajes que mandan al sitio equivocado en humano

### B1 · Seis emisores nombran el fichero murino

`offtarget.MISSING_FILE = "transcriptoma_3utr.fa"` es una constante con el nombre
**murino**, y la leen cinco mensajes (`offtarget_store`, `offtarget`, y tres de
`presentation`). Un sexto lo escribe inline `selection.py` en el motivo del frente:

```
offtarget_seed  NOT_RUN: falta `transcriptoma_3utr.fa`, así que los sitios de seed…
```

En humano el gestor pide `transcriptoma_3utr_human.fa`. **El mensaje manda a conseguir
un fichero que nadie pide.** Es la errata nº 83 —«un aviso que no nombra el paso que lo
cierra no es una instrucción»— con la especie como eje.

Y no es una sorpresa: el propio `insumos.py` lo dejó escrito al cerrar la errata nº 47
—*«`transcriptoma_3utr.fa` es el nombre murino, o sea que en humano fallaban igual»*—.
Se derivó **la comparación de md5** y se dejaron **los mensajes**.

**Arreglo:** el nombre se pide a `species.required_files` por su ROL, que es la única
fuente de los nombres del depósito. Y un guardia mecánico: ningún literal de nombre de
fichero del depósito fuera de `species.py` (con la prosa histórica declarada, como en
`auditar_marcos`).

### B2 · `cassette_deposit_check` es ciego a la especie

Su firma no tiene especie y su docstring dice —correctamente en espíritu— que el nombre
se le pide a `manifest.ROLES` «para no tener una segunda definición». El problema es que
`ROLES` **es la tabla murina**.

Medido, en un depósito que contiene el casete humano correcto:

```
   fichero que busca : aav_casete.fa          ← el murino
   estado            : SIN_COMPROBAR
```

Y en el caso **real** —el casete murino está versionado en git, así que **siempre** está
en el depósito— con un diseño humano:

```
   estado : NO_COINCIDE
   motivo : El casete con el que se iban a montar las construcciones NO es el de
            aav_casete.fa: en uso 5282 nt (md5 44aa551d…) y en el depósito 5282 nt
            (md5 74f3fd79…)…
```

**Una alarma roja en toda corrida humana correcta.** Un guardia con falsos positivos se
acaba apagando (principio nº 34), y éste los daría siempre.

### B3 · Tres fichas de obtención nombran ficheros murinos en su prosa

Resolviendo las trece fichas para humano, quedan tres con nombres murinos dentro:

| ficha | literal |
|---|---|
| `transgen` | «El casete que hay hoy en el proyecto (`aav_casete.fa`) es el PARENTAL…» |
| `empalme_intron` | «El casete que hay (`aav_casete.fa`) NO sirve como parental sin intrón…» |
| `offtarget_seed` | «…igual que con `refseq_rna.fa`» |

La **lista de ficheros** de cada ficha sí está derivada —hay test que la cruza contra el
gestor— y lo que se quedó atrás es la prosa de los pasos. Para quien cargue humano, la
primera frase afirma un hecho murino como si fuera del proyecto en curso. La regla ya
está escrita: *«la ficha SE ADAPTA A LA ESPECIE. No vale decir «miRBase» cuando quien lee
ha cargado conejo»*, y el sistema ya soporta marcadores `{fichero_<rol>}`.

---

## C1 — El modal de seed no dice que el núcleo es una lista PRESTADA

La decisión del 2026-08-26 (opción **a**) es explícita: fuera del ratón el veredicto sale
igual, **marcado**, porque *«excluir por una lista prestada es defendible; no decirlo,
no»*. `CoreHit` implementa los tres estados y `CoreHit.reason` añade
`BORROWED_LIST_WARNING`.

**Ese aviso llega al filtro del tilado y no llega al modal.** `mirna.py` pasa
`species=`; `seed_scan.run_scan` llama a `core_hits(nombres)` **sin especie**, y sólo usa
el booleano `core` — la razón con el aviso no se construye nunca. El modal es el camino
que **escribe en el almacén**, alimenta la ficha y produce el **bloque exportable**, que
es «material para defender la selección».

### Medido sobre el humano

Corriendo el modal sobre los 103 sitios elegibles humanos (206 consultas, `hsa-`,
ventana 2-8): **un FAIL de núcleo**, la pasajera de `3utr:671` contra `hsa-miR-128-3p`.
Su línea en el bloque exportable:

```
tx:1500   pasajera   CACAGTG   FAIL — 5: hsa-miR-11400-3p, hsa-miR-128-3p, …
```

Y buscando en todo lo que el modal emite —destacados incluidos— las palabras «otra
especie», «murino», «ratón», «mouse» y «autoriz»: **ninguna aparece**.

O sea: en humano se excluye un candidato por una lista autorizada para **cerebro
murino** y el artefacto que se lleva quien defiende la selección no lo dice.

Es el principio nº 33 exacto: *el guardia estaba, y la pregunta no le llegaba* —
`run_scan` **tiene** la especie en su firma.

---

## D — Lo estructural, que es lo que más ahorra

### D1 · Ningún golden tiene al humano como especie de DISEÑO

Los ocho goldens versionados son de ratón. El humano entra **sólo** como `--fasta-b`, es
decir como la segunda especie de la comparación de conservación — nunca como la que se
está diseñando.

Así que el camino humano-primario **no lo lee ningún artefacto**. Y merece recordarse
cuánto cazó el golden en la campaña del ratón: las 127 líneas borradas en silencio, el
`3utr:1149` de la cabecera de una ficha, los dos textos inventados de `informe_doc`, el
ancho de la tabla de frentes. Todo eso lo cazó **leer el diff**, no un test.

**Es la recomendación número uno de esta revisión**, y depende de A1: hoy el CLI no puede
producirlo.

### D2 · El inventario de estados no tiene eje de especie

`data/estados.toml` modela `corrida`, `fichero:<rol>`, `modal:<corrida>`, `proyecto` y
`rerun`. **No modela la especie.** Es la contrapartida del principio nº 15 que ya se
aprendió con el eje de proyecto: *un inventario que no puede expresar un estado no puede
echarlo de menos* — y los 33 estados de hoy describen todos una corrida de ratón.

---

## Lo que SÍ está listo, medido

Para que se pueda confiar en lo que no hay que tocar:

- **La página conecta por especie, correctamente.** Con humano conecta `mature.fa` y
  `rmsk_human.out`, y **no** conecta el casete murino ni la tabla de PolyA_DB murina.
- **El pipeline humano corre entero y sin abortos**: 2414 ventanas tiladas, 103 sitios
  elegibles (102 con la máscara puesta), panel de **11** —`3utr:` 110, 246, 387, 476,
  651, 710, 779, 857, 1111, 1246, 1421—, sin notas y sin cuotas sin cubrir.
- **La máscara humana entra y muerde**: `(TA)n` en `tx:2097-2130`.
- **La tasa base de seed se deriva por especie**: 2789 maduros `hsa-`, 2183 seeds
  distintas sobre 16384 (frente a 1988 / 1593 en ratón).
- **`resolve_measured` rechaza por md5**: el humano **no** hereda el techo de 0,86 del
  ratón.
- **`retirados` se aplica por md5**: la retirada de `3utr:10` no toca al humano.
- **`vector_applies_to("human")` es `False`**: el módulo NheI-SacI, el cassette, la hoja
  de pedido y el control sin intrón **no se emiten** con las piezas murinas, y la app
  dice cuáles y por qué.
- **`deposito.role_for` sí resuelve por especie** — el agujero de `ROLES` está cerrado
  ahí; lo que queda son los dos llamadores de B2 y A1.

---

## Y una cosa que no es un fallo del código, pero decide la campaña

**Para el humano no hay vector.** `blocks.PIECES` son las 12 piezas del plásmido de PrP
murino y el proyecto tiene decidido que **no se parametriza: se sustituye**. Sin otro
plásmido, una campaña humana puede llegar hasta el panel y sus filtros, y **no** puede
emitir el fragmento de síntesis, la hoja de pedido, las construcciones ni el frente de
empalme.

No es un descubrimiento de esta revisión —está escrito y la app lo dice en rojo— pero
conviene tenerlo delante **antes** de empezar, porque cambia qué se puede prometer.

Y en el mismo orden de cosas: el humano entra en **modo asumido** para el APA. Sus dos
`ATTAAA` (`3utr:955` y `3utr:1167`) están clasificadas por **canonicidad y sin un solo
dato de uso** — que es exactamente donde estaba el ratón antes de mirar PolyA_DB, y allí
el modo sin medida resultó ser **el equivocado**.

---

## Orden de trabajo propuesto

1. **A1** — la especie llega al CLI. Desbloquea todo lo demás, incluido poder generar
   un artefacto humano.
2. **D1** — golden humano-primario, con la configuración por defecto (principio nº 18).
   Antes de tocar nada más, para que los cambios siguientes se lean en un diff.
3. **A2** y **A3** — los dos guardias de identidad que faltan (casete y `apa_medido`).
4. **C1** — la especie llega a `core_hits` desde el modal.
5. **B1**, **B2**, **B3** — los nombres, derivados del rol, con un guardia mecánico que
   impida volver a escribirlos.
6. **D2** — eje de especie en el inventario de estados.

Los cinco primeros son la diferencia entre empezar el humano con la red puesta o
repetir, uno a uno, los fallos que costaron la campaña del ratón.
