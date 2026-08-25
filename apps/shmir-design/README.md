# shmir-design

Proyecto Python del hub. Vive dentro de `jokin-tools` pero es independiente del backend
Node/Express: Python 3.11+, solo librería estándar, sin frameworks web, interfaz CLI
(regla 6). No se acopla a nada del hub.

Las reglas del proyecto están en [`CLAUDE.md`](./CLAUDE.md) y son vinculantes.

## Qué hay implementado

| Paso | Qué | Dónde |
|---|---|---|
| 0 | Carga de fixtures + verificación de checksum (longitud, extremos, md5) y extracción de los 3'UTR | `shmir_design/reference.py`, `tools/reference_data.py` |
| 4, 5, 6, 8 | Filtros duros de ventana: GC, homopolímeros, motivo G4, guía con U forzada | `shmir_design/hard_filters.py` |
| 7 | Asimetría de la guía (Turner 2004, proxy heurístico) | `shmir_design/thermo.py` |
| 3, 15 | Tiling de 22-meros, contadores `biofisicos_ok` / `aptas` y agrupación en sitios | `shmir_design/tiling.py`, `tools/tiling_report.py` |
| 9 | Guardarrailes de poliadenilación: señales, zonas prohibidas ±10 nt, aviso de APA, tercios | `shmir_design/polya.py` |
| 10 | Seed de la guía (posiciones 2–8) contra familias de miRNA — **mecánica**, falta `mature.fa` | `shmir_design/seeds.py` |
| 14 | Bloques conservados entre dos 3'UTR, con todas sus ventanas evaluadas | `shmir_design/conservation.py`, `tools/conservation_report.py` |
| — | Estados de filtro `PASS`/`FAIL`/`NOT_RUN` y su agregación | `shmir_design/filters.py` |
| — | Verificador de la regla 2 sobre el AST | `tools/check_rules.py` |

El pipeline completo, con el orden no negociable y qué queda pendiente, está en
[`docs/pipeline.md`](./docs/pipeline.md). Los valores esperados verificados (tiling,
conteos PASS, bloque conservado) están en
[`docs/valores-esperados.md`](./docs/valores-esperados.md).

## Guardarrailes de poliadenilación

```python
from shmir_design.polya import Window, analyze_3utr

report = analyze_3utr(secuencia_3utr, [Window(start=1581, length=22, label="w1581")])
print(report.format_text())
```

- **A.** Localiza `AATAAA` y las nueve variantes principales, con posición y distancia
  al extremo 3'. Marca *señal terminal probable* a 10–40 nt del final y *APA posible*
  toda `AATAAA` canónica a más de 100 nt. Toda ventana que solape una señal ±10 nt sale
  con `zona_prohibida = FAIL`.
- **B.** Si hay un APA proximal, el informe emite `⚠ AVISO [APA_PROXIMAL]`. Los
  candidatos corriente abajo **no se excluyen**: se anotan con `riesgo_APA=True`.
- **C.** Cada ventana se anota con su tercio (`proximal` / `medio` / `distal`), para las
  cuotas de selección del paso 15.

Coordenadas 1-based; `distance_to_3p` cuenta los nucleótidos entre el último del motivo
y el extremo 3'.

## Los dos contadores

```bash
python3 apps/shmir-design/tools/tiling_report.py --tsv /tmp/salida
```

- **`biofisicos_ok`** — ventanas que superan los seis filtros biofísicos: GC,
  homopolímero, asimetría, G4 diana, G4 guía y zona prohibida de poliadenilación. No
  depende de ningún recurso externo: es el contador comprobable sin red.
- **`aptas`** — ventanas con veredicto `PASS`, que además superan los externos. Con
  miRBase ausente esto es **0**, porque la seed queda en `NOT_RUN` y `NOT_RUN` no es
  `PASS`. Debe ser así.

`--bootstrap-seeds` carga una lista de 12 seeds que sirve para probar la mecánica y
**no** para cribar candidatos; el informe lo dice en cada ejecución. Una ventana con una
`N` no es evaluable: sus filtros salen en `NOT_RUN` con el motivo, nunca en `PASS`.

## Bloques conservados

```bash
# Compara los dos 3'UTR de referencia (fixtures verificados)
python3 apps/shmir-design/tools/conservation_report.py
```

Busca todos los bloques de identidad exacta ≥15 nt ya extendidos al máximo por ambos
lados, da longitud, posición y distancia al extremo 3' en cada especie y %GC, y para
cada bloque ≥22 nt enumera **todas** sus ventanas de 22 nt con el estado y el motivo de
cada filtro, no solo el fallo. La `N` nunca cuenta como identidad.

Los bloques se reportan **siempre**, aunque ninguna ventana pase: la decisión de usarlos
es del usuario, no del software.

## Datos de referencia

Fixtures versionados en `data/reference/`, verificados por checksum en cada carga. **No
se descarga nada en tiempo de ejecución**; el análisis no depende de la red. El patrón
—y lo que hace falta para añadir miRBase, gnomAD o `rmsk`— está en
[`docs/fixtures.md`](./docs/fixtures.md), y la procedencia en
[`data/reference/PROCEDENCIA.md`](./data/reference/PROCEDENCIA.md).

Estado: los dos `.fa` todavía no están en el repositorio, así que 7 tests se saltan de
forma visible. En cuanto estén, se ponen en verde solos.

## Comprobaciones

```bash
npm run check:shmir   # regla 2 sobre el AST
npm run test:shmir    # tests

# Paso 0: verificar los fixtures (sin red)
python3 apps/shmir-design/tools/reference_data.py

# Paso 0, camino opcional, desde una máquina con salida a internet:
python3 apps/shmir-design/tools/reference_data.py --fetch \
    --efetch-url <base verificada> --email tu@correo
```

`check_rules.py` sale con 0 si está limpio, 1 si hay violaciones y 2 si algún fichero no
se pudo analizar. `reference_data.py` sale con 2 y no escribe nada si un md5 no coincide.
