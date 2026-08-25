# Pipeline de filtros

Orden de ejecución **no negociable**. Invertirlo produce un ranking contaminado que
parece correcto.

| # | Filtro | Tipo | Recurso externo | Si falla el recurso | Estado |
|---:|---|---|---|---|---|
| 0 | Carga + verificación de checksum | previo | ninguno: fixture versionado | **ABORTAR** | **implementado** (`reference.py`, `tools/reference_data.py`); descarga opcional con `--fetch` |
| 1 | Extracción de anatomía (ORF, UTRs) | duro | ninguno | — | parcial: coordenadas verificadas en `reference.py`; sin detección de ORF |
| 2 | Enmascarado de repeticiones → **RETILAR** | duro | fixture `rmsk` (descarga manual) | `NOT_RUN` | **implementado** (`masking.py`); falta el fichero de intervalos |
| 3 | Tiling de 22-meros | — | ninguno | — | **implementado** (`tiling.py`, `tools/tiling_report.py`) |
| 4 | GC 0.30–0.52 | duro | ninguno | — | **implementado** (`hard_filters.filter_gc`) |
| 5 | Sin homopolímeros ≥4 | duro | ninguno | — | **implementado** (`hard_filters.filter_homopolymer`) |
| 6 | Forzar U en posición 1 de la guía | transformación | ninguno | — | **implementado** (`hard_filters.guide_from_target`) |
| 7 | Asimetría ≥ +0.5 kcal/mol | duro | ninguno | — | **implementado** (`thermo.py`), sobre la guía transformada |
| 8 | Sin motivo G-cuádruplex | duro | ninguno | — | **implementado** sobre la diana **y** sobre la guía (`G4_diana`, `G4_guia`) |
| 9 | Exclusión de señales de poliadenilación ±10 nt | duro | ninguno | — | **implementado** (`polya.py`) |
| 10 | Seed sin colisión con miRNA | duro | fixture `mature.fa` (descarga manual) | `NOT_RUN` | mecánica **implementada** (`seeds.py`); falta `mature.fa`: la lista de 12 es un arranque, no un filtro |
| 11 | Sin variante con AF > 0.001 (solo humano) | duro | fixture del export de gnomAD | `NOT_RUN` | pendiente |
| 12 | Especificidad (BLAST) | duro | **manual en la v1** | `NOT_RUN` | pendiente |
| 13 | Accesibilidad (RNAplfold) | **ranking** | ViennaRNA (pip) | omitir, sin penalización | pendiente; la dependencia necesita autorización escrita (regla 6) |
| 14 | Detección de bloques conservados | informativo | ninguno | — | **implementado** (`conservation.py`, `tools/conservation_report.py`) |
| 15 | Agrupación en sitios + selección voraz | selección | ninguno | — | **implementado** (`selection.py`, `tools/design.py`) |

## Los datos de referencia son fixtures, no descargas

Ningún paso depende de la red en tiempo de ejecución. Descarga manual una vez,
checksum, fichero versionado; la verificación es idéntica de duro leyendo de disco. El
detalle y lo que hace falta para añadir un fixture nuevo, en [`fixtures.md`](./fixtures.md).

## Dos contadores, nunca uno

- **`biofisicos_ok`**: ventanas que superan los seis filtros biofísicos (GC,
  homopolímero, asimetría, G4 diana, G4 guía, zona prohibida de poliadenilación). No
  depende de ningún recurso externo, así que es el contador de referencia comprobable
  sin red.
- **`aptas`**: ventanas con veredicto `PASS`, que además superan los filtros externos.
  Con miRBase, gnomAD y BLAST ausentes esto es 0, y debe serlo.

Mezclarlos es exactamente el fallo que hace que un candidato incompleto parezca
aprobado. Son dos métodos y dos columnas del TSV.

## Una ventana con N no es evaluable

Si una ventana contiene una base desconocida (`N`), sus filtros de secuencia salen en
`NOT_RUN` con el motivo, nunca en `PASS` ni en `FAIL`: no se puede calcular GC ni
asimetría sobre una base que no se sabe cuál es. Así el enmascarado del paso 2 no podrá
inflar ningún conteo cuando entre.

## Reglas transversales

- **`NOT_RUN` no es `PASS`.** Un candidato con cualquier filtro duro en `NOT_RUN` no
  puede aparecer como apto: sale en categoría propia (`INCOMPLETE`, ver
  `filters.overall_verdict`).
- El paso 2 **retila desde cero** tras enmascarar. No se tachan candidatos a posteriori:
  una ventana parcialmente solapada con un elemento repetitivo hay que reevaluarla, no
  eliminarla.
- El paso 13 es **desempate**, nunca filtro.
- Selección voraz del paso 15: espaciado mínimo **50 nt** entre sitios elegidos, más
  cuota de al menos un candidato por cada tercio del 3'UTR. El tercio ya lo anota
  `polya.annotate_3utr` (`proximal` / `medio` / `distal`).
- El paso 12 es manual en la v1: entra como resultado importado, y mientras no se
  importe queda en `NOT_RUN`, nunca en `PASS`.

## Aviso de APA (apartado B del guardarrail)

Un APA proximal no excluye candidatos: los de corriente abajo se anotan con
`riesgo_APA=True` y el informe emite un `AVISO [APA_PROXIMAL]` que dice cuántos son. La
decisión de usarlos es del responsable, no del software.

## Bloques conservados (paso 14)

Nunca descartan nada: se reportan siempre, aunque ninguna de sus ventanas pase los
filtros duros, porque un tramo idéntico en modelo y en clínica vale una sola
herramienta para los dos. La decisión de usarlos es del usuario.

Con los filtros 4–9 implementados, una ventana ya puede salir `PASS`. Los pasos 2, 10,
11 y 12 siguen pendientes: cuando entren, un candidato sin sus fixtures saldrá
`INCOMPLETE`, nunca `PASS`.

## Después del pipeline: la horquilla (salida de oligos)

`scaffold.py` monta el 97-mero miR-E que se pide al sintetizador:

```
flanco5(18) + PASAJERA(22) + loop(19) + GUIA(22) + flanco3(16) = 97 nt
```

Andamio SGEP (Addgene #111170), **verificado**: los flancos y el loop son dato, no
suposición. La guía va en el brazo 3p.

Lo que **no** está verificado, y sale avisado en cada oligo:

- **La regla de la pasajera.** No es el complementario reverso exacto: lleva un
  desapareamiento deliberado en la posición 1 (transición T↔C). Derivada de **un solo
  ejemplo**; hay que confirmarla contra un segundo plásmido miR-E (LT3GEPIR #111177).
  Si el complementario reverso empieza por A o por G, el caso no está cubierto: la base
  no se toca y se avisa, en vez de inventar una transición que nadie ha visto.
- **Los flancos extendidos del pri-miR** para el cassette AAV: sin decidir.
  `extended_cassette()` aborta en vez de rellenarlos.

`SCAFFOLD["verified"] = True` se refiere solo al 97-mero.

## Selección de los candidatos finales

Orden de operaciones, y no se cambia:

1. **enmascarar repeticiones y RETILAR** (`masking.apply_mask` + `tiling.tile_utr`). Se
   enmascara antes de trocear: una ventana parcialmente repetitiva se reevalúa entera,
   no se tacha de una lista ya hecha. Las posiciones enmascaradas pasan a `N`, y una
   ventana con `N` no es evaluable.
2. **todos los filtros duros** (`tiling.tile_utr`).
3. **ordenar los supervivientes por asimetría** — por el número guardado en
   `WindowEvaluation.asymmetry`, no por el texto del motivo.
4. **agrupar ventanas contiguas en sitios** (`selection.group_choices`).
5. **selección voraz** (`selection.choose`).

### Restricciones

- **Espaciado mínimo de 50 nt entre sitios elegidos.** Es la regla que convierte N
  apuestas correlacionadas en N apuestas independientes: las causas de fallo —estructura
  local, RBPs, repeticiones no anotadas, APA— son regionales, no puntuales. Se mide
  **entre las posiciones de inicio** de los candidatos elegidos: 50 nt exactos valen, 49
  no. Configurable con `--min-spacing`.
- **Cuota por tercio**: primero se cubre un candidato de cada tercio, aunque el medio
  puntúe peor; el resto de plazas van por asimetría. Si un tercio no se puede cubrir, el
  informe dice por qué (sin sitios elegibles, o todos demasiado cerca de uno ya
  elegido). No se rellena con nada ni se calla.
- **Número de candidatos** configurable, 6 por especie por defecto.

### Elegible no es aprobado

Elegible = supera los seis biofísicos y no falla ningún filtro conocido. Un filtro en
`NOT_RUN` no descarta la ventana, pero tampoco la aprueba: su veredicto sigue siendo
`INCOMPLETE` y **la selección entera es provisional**. El informe lo dice en su propia
sección, y el TSV de seleccionados lo lleva en una columna.

## Salidas

`tools/design.py --out DIR` escribe, por especie:

| Fichero | Qué |
|---|---|
| `{especie}_ventanas.tsv` | TODAS las ventanas, una columna por filtro con `PASS`/`FAIL`/`NOT_RUN` por separado |
| `{especie}_seleccionados.tsv` | los candidatos, con rango por asimetría, tercio, veredicto y filtros sin correr |
| `{especie}_guias.fasta` | las guías en ADN, para BLAST (paso 12, manual en la v1) |
| `{especie}_oligos.tsv` | la horquilla ensamblada de cada candidato, con sus avisos en cada fila |
| `{especie}_informe.txt` | anatomía, señales de poliadenilación, bloques conservados, avisos y **qué filtros no se ejecutaron** |

## Interfaz

`ui/streamlit_app.py` es una capa sobre lo anterior, sin lógica propia. Lo que decide
algo está en `shmir_design/presentation.py` y tiene tests: el color del semáforo, las
filas de las tablas, el mapa SVG del 3'UTR y el paquete de descargas.

El semáforo mira los **candidatos seleccionados**, no todas las ventanas: una ventana
enmascarada nunca se evalúa —tiene `N`— y eso no significa que un filtro no haya llegado
a correr. Lo que decide el color es si lo que vas a encargar está filtrado del todo. Las
ventanas no evaluables se cuentan aparte, en el detalle del semáforo.

Los umbrales ajustables son `hard_filters.Thresholds`: GC mínimo y máximo, homopolímero
máximo, asimetría mínima y flanco prohibido alrededor de la señal de poliadenilación;
más el número de candidatos, el espaciado mínimo y la longitud mínima de bloque
conservado. Los valores por defecto son los verificados y salen escritos en la etiqueta
de cada control.
