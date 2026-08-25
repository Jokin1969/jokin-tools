# Datos de referencia — procedencia y verificación

Los datos de referencia son **fixtures versionados**, no descargas en tiempo de
ejecución. La red no es una dependencia del análisis: se descarga una vez, a mano, se
verifica por checksum y el fichero entra en el repositorio.

Que el origen sea el disco no relaja la verificación. `shmir_design/reference.py`
comprueba longitud, extremos y md5 en cada carga, y `extract_3utr` vuelve a comprobar el
md5 del 3'UTR extraído. Si algo no cuadra, se aborta: no hay camino que siga adelante
con "la secuencia que haya".

## Ficheros

| Fichero | Fuente | Identificador | Longitud | md5 |
|---|---|---|---:|---|
| `NM_011170.3.fa` | NCBI Nucleotide (efetch) | `NM_011170.3` — Prnp, *Mus musculus* | 2191 | `44fb8cd80883844cde5e53bbc367b176` |
| `NM_000311.5.fa` | NCBI Nucleotide (efetch) | `NM_000311.5` — PRNP, *Homo sapiens* | 2435 | `e28a945d24ce53e0d1d93ba5b55a532a` |

Los 3'UTR **no son ficheros**: se extraen del transcrito por sus coordenadas
(ratón 950–2191, humano 830–2435) y se verifican al vuelo contra su propio md5
(`19f5fa2a77a87892770e2affdc90e0e4` y `f7fdb4a88d4834dbbf9a23edf9ec85dc`). Un fichero
derivado menos es una copia menos que puede quedar desincronizada.

md5 calculado sobre la secuencia en MAYÚSCULAS, sin cabecera y sin saltos de línea. Los
valores están fijados en `shmir_design/reference.py`, con un test que falla si alguien
los cambia: el checksum no puede ajustarse para que un fichero pase.

## Estado

Los dos `.fa` todavía no están en el repositorio. Mientras falten, los tests que
dependen de ellos se saltan de forma visible (`skipped=7`) y nunca se dan por buenos.

## Cómo se comprueban

```bash
python3 apps/shmir-design/tools/reference_data.py            # verifica los fixtures, sin red
```

Y si alguna vez hay salida a internet, para regenerarlos:

```bash
python3 apps/shmir-design/tools/reference_data.py --fetch \
    --efetch-url https://<base verificada>/entrez/eutils/efetch.fcgi --email tu@correo
```

Lo descargado se verifica **antes** de escribirse: un fichero que no pasa el checksum no
llega al repositorio.

## Fragmentos usados en línea en los tests

| Fragmento | Coordenadas | Fuente |
|---|---|---|
| `AATTAAACGAGCGAAGATGAGC` (22 nt) | 3'UTR humano, 1581–1602 | proporcionado y verificado por el responsable |
| `GTTATTATTGGCTTGCACTTTG` (22 nt) | 3'UTR humano, 1237–1258 | proporcionado y verificado por el responsable |
| Andamio miR-E: flancos, loop y horquilla de 97 nt | plásmido SGEP | Addgene #111170, fichero SnapGene de la secuencia depositada, coincidente con tres fuentes |
| `TTTTCTATATTTGTAACTTTGCATGT` (26 nt) | bloque conservado; humano 1507–1532, ratón 1138–1163 | proporcionado y verificado por el responsable |

Son los únicos tramos de secuencia real que aparecen en el código. Las sondas de los
tests (`PROBE-NOT-A-SEQUENCE-…`, los andamios de `N`, las sondas de umbral) no son datos
biológicos y están etiquetadas como tales.
