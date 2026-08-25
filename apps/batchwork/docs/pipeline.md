# Pipeline de filtros

Orden de ejecución **no negociable**. Invertirlo produce un ranking contaminado que
parece correcto.

| # | Filtro | Tipo | Recurso externo | Si falla el recurso | Estado |
|---:|---|---|---|---|---|
| 0 | Descarga + verificación de checksum | previo | NCBI efetch | **ABORTAR** | implementado (`fetch.py`, `reference.py`, `tools/fetch_data.py`) |
| 1 | Extracción de anatomía (ORF, UTRs) | duro | ninguno | — | parcial: coordenadas verificadas en `reference.py`; sin detección de ORF |
| 2 | Enmascarado de repeticiones → **RETILAR** | duro | UCSC `rmsk` + Ensembl (mapeo) | `NOT_RUN` | pendiente |
| 3 | Tiling de 22-meros | — | ninguno | — | pendiente |
| 4 | GC 0.30–0.52 | duro | ninguno | — | pendiente |
| 5 | Sin homopolímeros ≥4 | duro | ninguno | — | pendiente |
| 6 | Forzar U en posición 1 de la guía | transformación | ninguno | — | pendiente |
| 7 | Asimetría ≥ +0.5 kcal/mol | duro | ninguno | — | pendiente |
| 8 | Sin motivo G-cuádruplex | duro | ninguno | — | pendiente |
| 9 | Exclusión de señales de poliadenilación ±10 nt | duro | ninguno | — | **implementado** (`polya.py`) |
| 10 | Seed sin colisión con miRNA | duro | miRBase `mature.fa` local | `NOT_RUN` | pendiente |
| 11 | Sin variante con AF > 0.001 (solo humano) | duro | gnomAD + Ensembl | `NOT_RUN` | pendiente |
| 12 | Especificidad (BLAST) | duro | **manual en la v1** | `NOT_RUN` | pendiente |
| 13 | Accesibilidad (RNAplfold) | **ranking** | ViennaRNA (pip) | omitir, sin penalización | pendiente; la dependencia necesita autorización escrita (regla 6) |
| 14 | Detección de bloques conservados | informativo | ninguno | — | pendiente |
| 15 | Agrupación en sitios + selección voraz | selección | ninguno | — | pendiente |

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
