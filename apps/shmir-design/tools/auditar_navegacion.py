#!/usr/bin/env python3
"""¿Cuántos accesos al modelo quedan en la página, y cuáles no toca ninguna suite?

Sale del corolario de la errata nº 17, extendido. La regla 6 dice que la página no
contiene lógica; la errata dice algo más fuerte y más útil: **cada `a.b.c` en la página
es una suposición sobre el modelo que ningún test comprueba**. `variant_proposal_text`
recibía `chosen[0].guide` y `Choice` no tiene `guide` — un `AttributeError` esperando a
que alguien abriera el modal.

Lo que este programa emite, y por qué en ese orden:

  · **cadenas de atributos de profundidad ≥ 2** sobre objetos del modelo (no sobre `st`,
    que es la librería de la interfaz y no es nuestro contrato);
  · separadas en **BAJO CLIC** y **SIEMPRE**. Las de arriba son las que importan: un
    camino que sólo se recorre al pulsar un botón no lo ejecuta ninguna suite y no lo
    ejecuta el test de humo, así que su primer lector es el usuario. Las de «siempre»
    las pinta el rerun de Streamlit en cuanto la página carga, y el golden de la corrida
    las cubre en parte.

No falla nunca: es un informe. Lo que se hace con cada fila es moverla a una función de
`presentation` con test, y eso se decide leyendo, no automáticamente.

    python3 tools/auditar_navegacion.py
"""

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAGINA = RAIZ / "ui" / "streamlit_app.py"

#: Raíces que NO son el modelo. `st` es Streamlit —su contrato lo mantiene otra gente— y
#: los módulos estándar tampoco son nuestros.
AJENAS = frozenset({"st", "os", "sys", "time", "json", "re", "Path", "datetime"})

#: Lo que marca un camino que sólo se recorre al pulsar algo. `st.button`, `st.form_submit_button`
#: y `st.download_button` devuelven `True` sólo en el rerun del clic.
DISPARADORES = ("button(", "form_submit_button(", "download_button(", "file_uploader(")


def _raiz_de(nodo: ast.Attribute) -> str:
    actual = nodo
    while isinstance(actual, (ast.Attribute, ast.Subscript, ast.Call)):
        actual = getattr(actual, "value", getattr(actual, "func", None))
        if actual is None:
            return ""
    return actual.id if isinstance(actual, ast.Name) else ""


def _profundidad(nodo: ast.Attribute) -> int:
    hondo, actual = 0, nodo
    while isinstance(actual, (ast.Attribute, ast.Subscript, ast.Call)):
        if isinstance(actual, ast.Attribute):
            hondo += 1
        actual = getattr(actual, "value", getattr(actual, "func", None))
        if actual is None:
            break
    return hondo


def _lineas_bajo_clic(arbol: ast.AST, fuente: str) -> set[int]:
    """Las líneas que viven dentro de un `if <algo que es un clic>:`."""
    dentro: set[int] = set()
    lineas = fuente.splitlines()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.If):
            continue
        prueba = ast.unparse(nodo.test)
        if not any(d in prueba for d in DISPARADORES):
            continue
        for hijo in ast.walk(nodo):
            fin = getattr(hijo, "end_lineno", None)
            if getattr(hijo, "lineno", None) and fin:
                dentro.update(range(hijo.lineno, fin + 1))
    del lineas
    return dentro


def auditar(ruta: Path = PAGINA) -> dict:
    fuente = ruta.read_text(encoding="utf-8")
    arbol = ast.parse(fuente, filename=str(ruta))
    clic = _lineas_bajo_clic(arbol, fuente)
    lineas = fuente.splitlines()
    bajo_clic, siempre = [], []
    vistos = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Attribute):
            continue
        if _profundidad(nodo) < 2:
            continue
        raiz = _raiz_de(nodo)
        if not raiz or raiz in AJENAS:
            continue
        clave = (nodo.lineno, ast.unparse(nodo))
        if clave in vistos:
            continue
        vistos.add(clave)
        fila = (nodo.lineno, ast.unparse(nodo), lineas[nodo.lineno - 1].strip())
        (bajo_clic if nodo.lineno in clic else siempre).append(fila)
    return {
        "bajo_clic": sorted(bajo_clic),
        "siempre": sorted(siempre),
        "total": len(bajo_clic) + len(siempre),
    }


def main() -> int:
    informe = auditar()
    print(__doc__)
    print("=" * 78)
    print(f"Accesos al modelo de profundidad ≥ 2 en la página: {informe['total']}")
    print(f"  BAJO CLIC (ninguna suite los recorre): {len(informe['bajo_clic'])}")
    print(f"  SIEMPRE   (el rerun los pinta):        {len(informe['siempre'])}")
    for titulo, filas in (
        ("BAJO CLIC — prioridad, su primer lector es el usuario", informe["bajo_clic"]),
        ("SIEMPRE — el golden de la corrida los cubre en parte", informe["siempre"]),
    ):
        print()
        print(f"── {titulo} ──")
        if not filas:
            print("  (ninguno)")
        for n, cadena, linea in filas:
            print(f"  streamlit_app.py:{n:<5} {cadena}")
    print()
    print(
        "Qué se hace con cada una: se mueve a una función de `presentation` con test, "
        "como `variant_proposal_for()`. No es automático — se decide leyendo."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
