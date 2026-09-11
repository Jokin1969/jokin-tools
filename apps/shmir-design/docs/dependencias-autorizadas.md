# Dependencias externas autorizadas

Regla 6: Python 3.11+ y solo librería estándar. Cada dependencia fuera de la stdlib
necesita autorización explícita del responsable del proyecto, anotada aquí antes de
usarse.

| Paquete | Versión | Para qué | Autorizado por | Fecha |
|---|---|---|---|---|
| `streamlit` | >= 1.30 (probado con 1.62.0) | Interfaz web, **solo** `ui/streamlit_app.py` | responsable del proyecto, por escrito | 2026-08-25 |
| `ViennaRNA` | >= 2.6 (probado con 2.7.2) | Plegado del 97-mero: comprobar que la horquilla mantiene la estructura de SGEP | responsable del proyecto, por escrito | 2026-08-25 |
| `pandas` | la que trae Streamlit (probado con 3.0.5) | **Sólo `Int64Dtype()`**, y sólo en `_tabla` de `ui/streamlit_app.py`: tipar como entero-con-huecos las columnas numéricas de una tabla. Ver abajo | responsable del proyecto, por escrito | 2026-09-11 |

## `pandas`: qué cubre esta autorización y qué NO

**Autorizada el 2026-09-11**, con estas palabras: *«Autorizo `pandas.Int64Dtype()` para
la columna rango. Cambia el tipo a Int64 nullable para que el puesto se muestre como
entero (1, 2, 3) y no como float (1.0, 2.0)»*.

**Qué cubre**: declarar el dtype de una columna de tabla en el pintor único
(`ui/streamlit_app.py::_tabla`). Nada más. Ni cálculo, ni filtrado, ni ordenación, ni un
`read_csv`, ni pandas en `shmir_design/`.

**Por qué hacía falta.** Una columna numérica con huecos —el puesto en el panel lo tienen
11 de 284 sitios— se infiere `float64`, y entonces el puesto 1 se pinta `1.0`. El dtype
nullable `Int64` es la única forma de tener a la vez **entero** y **hueco**: sin él hay
que elegir entre `1.0` (float con nulos) y `"1"` (texto, que ordena el 11 entre el 1 y el
2 — la errata nº 164).

**QUÉ COLUMNAS, y por qué NO va escrito «rango».** La autorización nombra esa columna
porque es la que se vio; lo que se aplica es la **propiedad derivada** que la hace
aplicable —una columna cuyos valores presentes son **todos enteros** y que tiene algún
hueco—, y la decide `presentation.integer_columns` con tests. Escribir `"rango"` en la
página sería un dato transcrito (principio nº 13): la tabla 27 con una columna entera
volvería a pintar `1.0` y nadie se enteraría. **Se ensancha a propósito y queda dicho
aquí para que se pueda discutir.**

**El núcleo no se entera.** `presentation` decide QUÉ columnas son enteras y devuelve
nombres; el `astype` vive en la página. `shmir_design/` sigue sin importar pandas, y hay
test de ello.

## El núcleo sigue siendo stdlib pura

`streamlit` es dependencia **de la interfaz**, no del proyecto:

- `shmir_design/` no importa Streamlit en ningún módulo, `presentation.py` incluido.
- Los CLI (`design.py`, `tiling_report.py`, `oligo.py`, `conservation_report.py`,
  `reference_data.py`, `check_rules.py`) funcionan sin ella.
- Los tests del núcleo corren sin ella; solo `test_streamlit_app.py` se salta de forma
  visible si no está instalada.

Se instalan aparte y por separado:

```bash
pip install -r apps/shmir-design/requirements-ui.txt        # interfaz
pip install -r apps/shmir-design/requirements-folding.txt   # plegado (ViennaRNA)
```

Sin ViennaRNA, `check_fold` devuelve `NOT_RUN` —nunca `PASS`— y el resto del pipeline
funciona igual.

## Sobre "sin frameworks web en la v1"

La regla 6 decía literalmente *"sin frameworks web en la v1"*. Esa parte queda enmendada
por el responsable del proyecto al pedir la interfaz Streamlit, con la condición que ya
estaba implícita y ahora es explícita: **la interfaz no contiene lógica**. Todo lo que
decide algo vive en el núcleo y tiene tests (`presentation.py`), y la UI solo llama.

Si mañana la interfaz empieza a decidir cosas —ordenar, filtrar, elegir un color según
un umbral— eso es una violación de esta condición, no una mejora de la UI.

## Pendiente de autorización

| Paquete | Para qué | Estado |
|---|---|---|
| `ViennaRNA` para el paso 13 (accesibilidad, RNAplfold) | ranking | ya instalable; el paso 13 sigue **sin integrar** |
