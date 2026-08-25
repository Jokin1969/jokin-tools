# Endpoints externos verificados

Regla 4: ninguna URL externa se escribe en el código de Batchwork sin estar en esta
tabla. Verificar significa **haber lanzado la petición desde este proyecto** y haber
comprobado que responde y que el formato es el esperado.

## Verificados desde este proyecto

| Endpoint | Petición verificada | Fecha | Formato observado | Verificado por |
|---|---|---|---|---|
| _(ninguno)_ | | | | |

**Ninguno.** Por eso `batchwork/fetch.py` no contiene ni una sola URL y
`tools/fetch_data.py` exige `--efetch-url`. En cuanto un endpoint se verifique desde
aquí, se anota arriba y entonces —y solo entonces— puede fijarse por defecto.

## Intentos de verificación (2026-08-25)

La política de red del entorno remoto rechaza el CONNECT a los cuatro hosts. No es un
fallo del endpoint: es el proxy del entorno negando la salida.

```
$ curl -sS -D - "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NM_011170.3&rettype=fasta&retmode=text"
curl: (56) CONNECT tunnel failed, response 403
HTTP/1.1 403 Forbidden
```

| Host | Resultado |
|---|---|
| `eutils.ncbi.nlm.nih.gov` | `connect_rejected` — 403 al CONNECT |
| `rest.ensembl.org` | `connect_rejected` — 403 al CONNECT |
| `api.genome.ucsc.edu` | `connect_rejected` — 403 al CONNECT |
| `www.mirbase.org` | `connect_rejected` — 403 al CONNECT |

El propio `tools/fetch_data.py`, lanzado contra la URL de NCBI, aborta como debe y no
escribe ningún fichero:

```
$ python3 apps/batchwork/tools/fetch_data.py --efetch-url https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi --accession NM_011170.3
GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&rettype=fasta&retmode=text&id=NM_011170.3&tool=batchwork
PARA — NM_011170.3: No se pudo conectar con [...] (Tunnel connection failed: 403 Forbidden);
se aborta el paso 0 (descarga + verificacion de checksum) y con el todo el pipeline.
(exit 2)
```

Para desbloquearlo: ampliar la política de red del entorno remoto
(https://code.claude.com/docs/en/claude-code-on-the-web) o ejecutar el script desde una
máquina con salida a internet.

## Lo que sabe el responsable del proyecto (NO verificado desde aquí)

Se anota como contexto, no como autorización. Ninguna de estas URLs está en el código.

| Recurso | URL base | Estado según el responsable |
|---|---|---|
| NCBI E-utilities `efetch` | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi` | Verificado funcionando con `db=nuccore&id=…&rettype=fasta&retmode=text`, también con `rettype=gb` y con recorte vía `seq_start`/`seq_stop`/`strand` |
| Ensembl REST | `https://rest.ensembl.org` | Host activo; devuelve 415 sin cabecera de contenido explícita. Requiere `Accept: text/x-fasta` o `application/json`; el `?content-type=` en la query NO basta |
| gnomAD GraphQL | `https://gnomad.broadinstitute.org/api` | Sin verificar. Verificar el esquema antes de escribir queries |
| UCSC REST (track `rmsk`) | `https://api.genome.ucsc.edu/getData/track` | Sin verificar |
| miRBase `mature.fa` | descarga estática de mirbase.org | Sin verificar. Fichero local, no API |
| PolyASite / PolyA_DB | descarga estática (BED) | Sin verificar. Son atlas, no predictores |
| NCBI BLAST URL API | `https://blast.ncbi.nlm.nih.gov/Blast.cgi` | **No implementar en la v1** |

Notas operativas que ya están reflejadas en el código:

- NCBI limita a 3 peticiones/segundo sin clave de API y 10 con clave, **por IP**. Si
  algo paraleliza, necesita un limitador compartido, no uno por worker
  (`fetch.min_interval_seconds`).
- `curl -s` no falla ante errores HTTP: NCBI devuelve su XML de error con código 200.
  Por eso `fetch.parse_fasta_payload` exige que la respuesta empiece por `>` y enseña
  los primeros 300 caracteres cuando no es así.
- Ensembl solo hace falta para mapear coordenadas de transcrito a genómicas, y eso solo
  lo necesitan gnomAD (paso 11) y UCSC (paso 2).
