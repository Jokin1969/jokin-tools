# Pipeline de filtros

Orden de ejecución **no negociable**. Invertirlo produce un ranking contaminado que
parece correcto.

| # | Filtro | Tipo | Recurso externo | Si falla el recurso | Estado |
|---:|---|---|---|---|---|
| 0 | Carga + verificación de checksum | previo | ninguno: fixture versionado | **ABORTAR** | **implementado** (`reference.py`, `tools/reference_data.py`); descarga opcional con `--fetch` |
| 1 | Extracción de anatomía (ORF, UTRs) | duro | ninguno | — | parcial: coordenadas verificadas en `reference.py`; sin detección de ORF |
| 2 | Enmascarado de repeticiones → **RETILAR** | duro | fixture `rmsk` (descarga manual) | `NOT_RUN` | pendiente |
| 3 | Tiling de 22-meros | — | ninguno | — | pendiente (el tiling dentro de un bloque conservado sí está, en `conservation.py`) |
| 4 | GC 0.30–0.52 | duro | ninguno | — | **implementado** (`hard_filters.filter_gc`) |
| 5 | Sin homopolímeros ≥4 | duro | ninguno | — | **implementado** (`hard_filters.filter_homopolymer`) |
| 6 | Forzar U en posición 1 de la guía | transformación | ninguno | — | **implementado** (`hard_filters.guide_from_target`) |
| 7 | Asimetría ≥ +0.5 kcal/mol | duro | ninguno | — | **implementado** (`thermo.py`), sobre la guía transformada |
| 8 | Sin motivo G-cuádruplex | duro | ninguno | — | **implementado** sobre la diana **y** sobre la guía (`G4_diana`, `G4_guia`) |
| 9 | Exclusión de señales de poliadenilación ±10 nt | duro | ninguno | — | **implementado** (`polya.py`) |
| 10 | Seed sin colisión con miRNA | duro | fixture `mature.fa` (descarga manual) | `NOT_RUN` | pendiente |
| 11 | Sin variante con AF > 0.001 (solo humano) | duro | fixture del export de gnomAD | `NOT_RUN` | pendiente |
| 12 | Especificidad (BLAST) | duro | **manual en la v1** | `NOT_RUN` | pendiente |
| 13 | Accesibilidad (RNAplfold) | **ranking** | ViennaRNA (pip) | omitir, sin penalización | pendiente; la dependencia necesita autorización escrita (regla 6) |
| 14 | Detección de bloques conservados | informativo | ninguno | — | **implementado** (`conservation.py`, `tools/conservation_report.py`) |
| 15 | Agrupación en sitios + selección voraz | selección | ninguno | — | pendiente |

## Los datos de referencia son fixtures, no descargas

Ningún paso depende de la red en tiempo de ejecución. Descarga manual una vez,
checksum, fichero versionado; la verificación es idéntica de duro leyendo de disco. El
detalle y lo que hace falta para añadir un fixture nuevo, en [`fixtures.md`](./fixtures.md).

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
