# Procedencia de los datos de test

Regla 5: los tests usan datos reales. Todo fichero de este directorio se anota aquí con
su origen. Regla 1: lo que no se pueda descargar y verificar **no se sustituye por nada**.

## Estado: los FASTA no están

La política de red del entorno remoto bloquea `eutils.ncbi.nlm.nih.gov` (403 al
CONNECT, ver `docs/endpoints-verificados.md`), así que no se han podido descargar. Los
tests que los necesitan están escritos y se saltan de forma visible (`skipped=3` en la
salida de unittest), no se dan por buenos.

## Cómo obtenerlos

Desde una máquina con salida a internet, o tras ampliar la política de red del entorno:

```bash
python3 apps/batchwork/tools/fetch_data.py \
    --efetch-url https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi \
    --email tu@correo
```

El script descarga, comprueba longitud, extremos y md5 contra `batchwork/reference.py`,
extrae los 3'UTR, vuelve a comprobar su md5 y escribe los ficheros. Si algún md5 no
coincide, **para y no escribe nada**.

## Ficheros esperados

| Fichero | Fuente | Identificador | Longitud | md5 |
|---|---|---|---:|---|
| `NM_011170.3.fa` | NCBI Nucleotide (efetch) | `NM_011170.3` — Prnp, *Mus musculus* | 2191 | `44fb8cd80883844cde5e53bbc367b176` |
| `NM_000311.5.fa` | NCBI Nucleotide (efetch) | `NM_000311.5` — PRNP, *Homo sapiens* | 2435 | `e28a945d24ce53e0d1d93ba5b55a532a` |
| `mouse_3utr.fasta` | extraído de `NM_011170.3` (950–2191) | — | 1242 | `19f5fa2a77a87892770e2affdc90e0e4` |
| `human_3utr.fasta` | extraído de `NM_000311.5` (830–2435) | — | 1606 | `f7fdb4a88d4834dbbf9a23edf9ec85dc` |

md5 calculado sobre la secuencia en MAYÚSCULAS, sin cabecera y sin saltos de línea.
Los checksums los verificó el responsable del proyecto y están fijados en
`batchwork/reference.py`, con un test que falla si alguien los cambia.

## Fragmentos usados en línea en los tests

| Fragmento | Coordenadas | Fuente |
|---|---|---|
| `AATTAAACGAGCGAAGATGAGC` (22 nt) | 3'UTR humano, 1581–1602 | proporcionado y verificado por el responsable, 2026-08-25 |

Es el único fragmento de secuencia real que aparece en el repositorio. Las sondas de
`test_reference.py` (`PROBE-NOT-A-SEQUENCE-…`) no son nucleótidos a propósito, para que
no puedan confundirse con un dato.
