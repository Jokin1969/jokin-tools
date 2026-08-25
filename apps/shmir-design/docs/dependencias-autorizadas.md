# Dependencias externas autorizadas

Regla 6: Python 3.11+ y solo librería estándar. Cada dependencia fuera de la stdlib
necesita autorización explícita del responsable del proyecto, anotada aquí antes de
usarse.

| Paquete | Versión | Para qué | Autorizado por | Fecha |
|---|---|---|---|---|
| `streamlit` | >= 1.30 (probado con 1.62.0) | Interfaz web, **solo** `ui/streamlit_app.py` | responsable del proyecto, por escrito | 2026-08-25 |

## El núcleo sigue siendo stdlib pura

`streamlit` es dependencia **de la interfaz**, no del proyecto:

- `shmir_design/` no importa Streamlit en ningún módulo, `presentation.py` incluido.
- Los CLI (`design.py`, `tiling_report.py`, `oligo.py`, `conservation_report.py`,
  `reference_data.py`, `check_rules.py`) funcionan sin ella.
- Los tests del núcleo corren sin ella; solo `test_streamlit_app.py` se salta de forma
  visible si no está instalada.

Se instala aparte: `pip install -r apps/shmir-design/requirements-ui.txt`.

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
| `ViennaRNA` | Paso 13, accesibilidad (RNAplfold), solo ranking | autorizada de palabra, **sin integrar**: falta hacer la prueba y enseñarla |
