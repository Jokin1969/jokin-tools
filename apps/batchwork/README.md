# Batchwork

Proyecto Python del hub. Vive dentro de `jokin-tools` pero es independiente del backend
Node/Express: Python 3.11+, solo librería estándar, sin frameworks web, interfaz CLI
(regla 6). No se acopla a nada del hub.

Las reglas del proyecto están en [`CLAUDE.md`](./CLAUDE.md) y son vinculantes.

## Qué hay implementado

| Paso | Qué | Dónde |
|---|---|---|
| 0 | Descarga + verificación de checksum (longitud, extremos, md5) y extracción de los 3'UTR | `batchwork/fetch.py`, `batchwork/reference.py`, `tools/fetch_data.py` |
| 4, 5, 6, 8 | Filtros duros de ventana: GC, homopolímeros, motivo G4, guía con U forzada | `batchwork/hard_filters.py` |
| 7 | Asimetría — **`NOT_RUN`**: falta su definición verificada ([`docs/preguntas-abiertas.md`](./docs/preguntas-abiertas.md)) | `batchwork/hard_filters.py` |
| 9 | Guardarrailes de poliadenilación: señales, zonas prohibidas ±10 nt, aviso de APA, tercios | `batchwork/polya.py` |
| 14 | Bloques conservados entre dos 3'UTR, con todas sus ventanas evaluadas | `batchwork/conservation.py`, `tools/conservation_report.py` |
| — | Estados de filtro `PASS`/`FAIL`/`NOT_RUN` y su agregación | `batchwork/filters.py` |
| — | Verificador de la regla 2 sobre el AST | `tools/check_rules.py` |

El pipeline completo, con el orden no negociable y qué queda pendiente, está en
[`docs/pipeline.md`](./docs/pipeline.md). Los valores esperados verificados (tiling,
conteos PASS, bloque conservado) están en
[`docs/valores-esperados.md`](./docs/valores-esperados.md).

## Guardarrailes de poliadenilación

```python
from batchwork.polya import Window, analyze_3utr

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

## Bloques conservados

```bash
python3 apps/batchwork/tools/conservation_report.py \
    tests/data/mouse_3utr.fasta tests/data/human_3utr.fasta \
    --name-a raton --name-b humano
```

Busca todos los bloques de identidad exacta ≥15 nt ya extendidos al máximo por ambos
lados, da longitud, posición y distancia al extremo 3' en cada especie y %GC, y para
cada bloque ≥22 nt enumera **todas** sus ventanas de 22 nt con el estado y el motivo de
cada filtro, no solo el fallo. La `N` nunca cuenta como identidad.

Los bloques se reportan **siempre**, aunque ninguna ventana pase: la decisión de usarlos
es del usuario, no del software.

## Estado: dos bloqueantes

- **Sin secuencias.** La política de red del entorno bloquea NCBI, Ensembl, UCSC y
  miRBase (403 al CONNECT). `tests/data/` está vacío y los tests de extremo a extremo
  se saltan de forma visible. Ver [`tests/data/PROCEDENCIA.md`](./tests/data/PROCEDENCIA.md).
- **Sin endpoints verificados.** Por eso `batchwork/fetch.py` no contiene ninguna URL y
  `tools/fetch_data.py` exige `--efetch-url`. Ver
  [`docs/endpoints-verificados.md`](./docs/endpoints-verificados.md).

## Comprobaciones

```bash
npm run check:batchwork   # regla 2 sobre el AST
npm run test:batchwork    # tests

# Paso 0, desde una máquina con salida a internet:
python3 apps/batchwork/tools/fetch_data.py --efetch-url <base verificada> --email tu@correo
```

`check_rules.py` sale con 0 si está limpio, 1 si hay violaciones y 2 si algún fichero no
se pudo analizar. `fetch_data.py` sale con 2 y no escribe nada si un md5 no coincide.
