# Datos de referencia: fixtures versionados

**Regla operativa: nada de referencia se descarga en tiempo de ejecución.** Descarga
manual una vez, checksum, fichero versionado. La red no puede ser una dependencia del
análisis — ni por disponibilidad, ni por reproducibilidad, ni por límites de peticiones.

Aplica a todo lo que sea dato de referencia:

| Recurso | Fichero | Paso que lo usa | Estado |
|---|---|---|---|
| Transcritos NCBI | `data/reference/NM_*.fa` | 0, 1 | implementado; fixtures pendientes de añadir |
| miRBase `mature.fa` | `data/reference/mature.fa` | 10 (seed vs miRNA) | mecánica lista (`seeds.py`); falta el fichero y su checksum |
| Export de gnomAD | `data/reference/gnomad_*.tsv` | 11 (AF > 0.001) | pendiente |
| RefSeq RNA de la especie | `data/reference/refseq_rna_*.fa` | 12 (especificidad) | lector listo (`specificity.load_database`, con md5); falta el fichero |
| Track `rmsk` de UCSC | `data/reference/rmsk_*.tsv` | 2 (enmascarado) | lector listo (`masking.load_mask_file`, formato `inicio<TAB>fin`); falta el recorte y su checksum |

## Qué hace falta para añadir un fixture nuevo

1. **Descargarlo a mano**, una vez, desde una máquina con salida a internet.
2. **Anotar su checksum y su procedencia** en `data/reference/PROCEDENCIA.md`: fuente,
   versión o fecha de descarga, tamaño y md5.
3. **Registrar el checksum en el código**, como está `REFERENCES` en
   `shmir_design/reference.py`, con un test que lo fije. Un checksum que vive solo en un
   `.md` se puede ajustar sin que nadie se entere; uno con test, no.
4. **Cargarlo siempre por una función que verifique** antes de devolver nada, y que
   aborte si no cuadra. Nunca leer el fichero directamente desde el código del filtro.
5. Si el recurso no está, el filtro que dependía de él sale en `NOT_RUN` — nunca en
   `PASS`, y nunca en silencio (regla 3). El paso 0 es la excepción: sin transcrito
   verificado no hay análisis, así que aborta.

## Por qué el checksum no es opcional

El proyecto ya sufrió una vez la entrega de una secuencia fabricada con metadatos
correctos alrededor. Un fixture sin checksum reproduce exactamente esa situación: un
fichero plausible, con el nombre correcto, que nadie vuelve a mirar. El checksum es lo
único que distingue "el dato" de "un dato".

## Versionar datos en el repositorio

Los transcritos son 2,4 kb: se versionan sin discusión. Para ficheros grandes (miRBase
completo, exports de gnomAD), recorta primero a lo que el pipeline necesita, versiona el
recorte, y anota en `PROCEDENCIA.md` el comando exacto del recorte y el checksum del
fichero original. Un recorte sin trazabilidad es un dato huérfano.
