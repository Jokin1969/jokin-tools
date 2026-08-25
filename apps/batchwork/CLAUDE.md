# Batchwork — reglas del proyecto

> **Ámbito.** Este fichero es vinculante para todo lo que hay bajo `apps/batchwork/`.
> El resto del hub (`server.js`, `apps/re-memory/`, `src/`) es Node/Express y NO se rige
> por estas reglas. Batchwork es un proyecto Python independiente que vive dentro del
> mismo repositorio.
>
> Si una petición choca con una de estas reglas, la regla gana. No se negocian, no se
> relajan "solo para esta vez" y no se saltan porque el resultado parezca razonable.

---

## Reglas innegociables

**1. NUNCA generes, completes ni "reconstruyas" secuencias biológicas.** Si falta una
secuencia, aborta con un error explícito. Una secuencia inventada que parece plausible
es el peor resultado posible de este software.

**2. PROHIBIDO `except: pass` y `except Exception: return None`.** Todo fallo de red,
de parseo o de fichero debe propagarse con un mensaje que diga QUÉ falló y QUÉ paso
queda sin ejecutar.

**3. Todo filtro que dependa de un recurso externo debe registrar en la salida si se
ejecutó, si se saltó, y por qué.** Un candidato nunca puede aparecer como "PASS" si un
filtro no llegó a correr. Usa tres estados: `PASS` / `FAIL` / `NOT_RUN`.

**4. Antes de usar cualquier endpoint o URL externa, verifica que responde y que el
formato es el esperado.** Si no lo has verificado, no lo escribas: pregunta. No inventes
URLs de API a partir de patrones.

**5. Escribe los tests ANTES de la funcionalidad.** Los tests usan datos reales
proporcionados, no datos sintéticos.

**6. Python 3.11+, solo librería estándar** salvo donde se autorice explícitamente una
dependencia. Sin frameworks web en la v1.

---

## Cómo se aplica cada regla

### Regla 1 — Secuencias

Queda prohibido, sin excepción:

- rellenar huecos/gaps con cualquier base o residuo;
- retro-traducir proteína a nucleótido para "recuperar" una secuencia ausente;
- reconstruir una secuencia por consenso, por homología o por el modelo;
- sustituir una secuencia ausente por una placeholder (`"NNNN..."`, `""`, cadena de
  ejemplo) que luego pueda circular como si fuera dato;
- usar secuencias inventadas en tests, fixtures, docstrings o ejemplos del README.

Si falta una secuencia, el flujo aborta:

```python
raise MissingSequenceError(
    f"No hay secuencia para {accession!r} en {source}; "
    f"se aborta el paso 'alineamiento de candidatos' (0 de {n} candidatos procesados)."
)
```

El error debe nombrar el identificador, de dónde se esperaba obtenerlo y qué paso queda
sin ejecutar. Nunca se degrada a warning.

### Regla 2 — Errores

- Prohibidos: `except:`, `except Exception: pass`, `except Exception: return None`,
  `contextlib.suppress(Exception)` y cualquier variante que borre el fallo.
- Capturar solo excepciones concretas y solo para **añadir contexto y relanzar**:

```python
try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    raise ParseError(
        f"Respuesta de {url} no es JSON válido ({exc}); "
        f"se aborta el filtro 'conservación' para {accession}."
    ) from exc
```

- `raise ... from exc` siempre: la causa original no se pierde.
- Un `except` con `pass` solo es admisible si la excepción es concreta, el caso está
  documentado en el propio bloque y no oculta ningún fallo de red, parseo o fichero.
  Ante la duda: propagar.

### Regla 3 — Estado de los filtros

Todo filtro devuelve uno de tres estados, nunca un booleano:

| Estado | Significado |
|---|---|
| `PASS` | El filtro corrió con todos sus recursos y el candidato lo supera. |
| `FAIL` | El filtro corrió con todos sus recursos y el candidato no lo supera. |
| `NOT_RUN` | El filtro no llegó a ejecutarse (recurso externo caído, dato ausente, sin autorización). |

Reglas de agregación:

- Un candidato con **cualquier** filtro en `NOT_RUN` no puede reportarse como aprobado.
  Su veredicto global es `INCOMPLETE`, nunca `PASS`.
- Todo `NOT_RUN` y todo `FAIL` llevan un `reason` legible que dice qué recurso faltó.
- La salida (CSV, JSON o texto) incluye una columna/campo por filtro con su estado. No
  se colapsan filtros ni se omiten los que no corrieron: un filtro ausente de la salida
  es indistinguible de un filtro superado, y eso es exactamente lo que la regla prohíbe.
- El resumen final indica cuántos candidatos son `INCOMPLETE` y por qué filtro.

### Regla 4 — Endpoints externos

- Ninguna URL externa se escribe en el código sin haber sido verificada antes
  (responde, y el formato es el esperado).
- Las URLs verificadas se registran en `docs/endpoints-verificados.md` con fecha,
  petición exacta y forma de la respuesta. **Ese registro está hoy vacío.**
- Prohibido deducir una URL "por patrón" a partir de otra que sí existe, o de memoria
  sobre cómo suele ser la API de un servicio.
- Sin verificación no se escribe: se pregunta.

### Regla 5 — Tests primero, con datos reales

- El commit que añade funcionalidad llega con sus tests ya escritos y fallando antes.
- Los fixtures viven en `tests/data/` y cada uno lleva su procedencia (fuente,
  identificador, fecha de descarga) en `tests/data/PROCEDENCIA.md`.
- Prohibido fabricar secuencias de ejemplo para un test (es la regla 1 por otra puerta).
  Si no hay dato real para cubrir un caso, el test no se inventa: se pide el dato.

### Regla 6 — Entorno

- Python 3.11+ (`match`, `tomllib`, `ExceptionGroup` disponibles), solo `stdlib`.
- Sin frameworks web en la v1: la interfaz es CLI.
- Cada dependencia externa requiere autorización explícita y queda anotada en
  `docs/dependencias-autorizadas.md` con quién la autorizó y para qué.
  **Ese registro está hoy vacío: la v1 es stdlib pura.**

---

## Verificación

`tools/check_rules.py` analiza el AST de los ficheros Python de `apps/batchwork/` y
falla si encuentra manejo de errores prohibido por la regla 2:

```bash
npm run check:batchwork   # o: python3 apps/batchwork/tools/check_rules.py [ruta ...]
npm run test:batchwork    # o: cd apps/batchwork && python3 -m unittest discover -s tests -t .
```

Pásalos antes de cada commit que toque `apps/batchwork/`.

---

## Antes de dar por terminado cualquier cambio aquí

1. ¿Alguna ruta del código puede producir una secuencia que no venga íntegra de la
   entrada? → arréglalo o aborta.
2. ¿Algún `except` se traga un fallo de red, parseo o fichero? → `check_rules.py`.
3. ¿Cada filtro emite `PASS`/`FAIL`/`NOT_RUN` con motivo, y ningún `NOT_RUN` acaba
   reportado como aprobado?
4. ¿Toda URL nueva está en `docs/endpoints-verificados.md` con su verificación?
5. ¿Los tests se escribieron antes y usan datos reales con procedencia registrada?
6. ¿Sigue siendo stdlib pura, o hay una autorización escrita para la dependencia nueva?

## Estado actual (bloqueantes)

- **No hay secuencias.** La política de red del entorno rechaza el CONNECT a
  `eutils.ncbi.nlm.nih.gov`, `rest.ensembl.org`, `api.genome.ucsc.edu` y
  `www.mirbase.org` (403). `tests/data/` está vacío y los tests que necesitan los 3'UTR
  completos se saltan de forma visible. No se rellenan con secuencia sintética.
- **No hay endpoints verificados desde este proyecto.** Por eso `batchwork/fetch.py` no
  contiene ninguna URL y `tools/fetch_data.py` exige `--efetch-url`. Lo que el
  responsable ha verificado por su cuenta está anotado como contexto, no como
  autorización, en `docs/endpoints-verificados.md`.
- **La asimetría (paso 7) no está implementada**: falta su definición verificada, así
  que el filtro devuelve `NOT_RUN` y ninguna ventana puede salir `PASS`. Las cuatro
  preguntas que la desbloquean están en `docs/preguntas-abiertas.md`. No se deduce
  probando tablas de parámetros hasta que salga el número esperado.
- Implementado: pasos 0 (descarga + checksum), 4-6 y 8 (filtros duros de ventana),
  9 (guardarrailes de poliadenilación) y 14 (bloques conservados). El resto del
  pipeline, en `docs/pipeline.md`.
