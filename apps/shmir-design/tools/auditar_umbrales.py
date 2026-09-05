#!/usr/bin/env python3
"""Umbrales cuya lectura correcta depende de un supuesto sobre los datos.

Categoria PROPIA, y distinta de la que ya habia. `justificacion.py` cubre los umbrales
**sin base medida** —numeros sin respaldo—. Estos son numeros **con** respaldo aparente
que **significan otra cosa de la que parecen**, porque llevan dentro un supuesto que no
esta escrito.

El caso que abre la categoria (errata nº 56): `FAIL if len(fuera) > 1` codificaba «uno es
tuyo», y fallaba en las dos direcciones — con dos variantes del gen contaba la segunda
como off-target, y con una guia que no acierta a su diana daba PASS. Ninguna de las dos
se ve.

QUE MIRA, y por que ese recorte: comparaciones contra un literal numerico **dentro de una
funcion que emite veredicto** (nombra `FilterState`, `FilterResult` o `Verdict`). El
barrido ancho da **123** comparaciones en el paquete y casi todas son aritmetica de
formato o guardias de entrada; un auditor asi se apaga el primer dia. Acotado a lo que
DECIDE, son ocho y se revisan una a una.

QUE NO PUEDE HACER: no sabe si un supuesto es cierto. Obliga a escribirlo, que es lo que
faltaba — el `> 1` llevaba meses y nadie lo habia mirado porque parecia un umbral flojo.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TABLA = RAIZ / "data" / "umbrales_con_supuesto.toml"
COMPARACIONES = {"Gt", "Lt", "GtE", "LtE"}
EMITEN_VEREDICTO = {"FilterState", "FilterResult", "Verdict"}


def umbrales_de_fuentes(fuentes: dict[str, str]) -> list[str]:
    """Lo mismo sobre fuentes dadas — `{modulo: codigo}`.

    Va separado de leer el paquete por la razon de siempre: un guardia que solo se puede
    correr sobre el codigo YA arreglado no demuestra que muerda. El control adversario
    (`tests/test_umbrales_con_supuesto.py`) le da el fuente de ANTES de la errata nº 56.
    """
    salida = []
    for modulo, codigo in sorted(fuentes.items()):
        arbol = ast.parse(codigo, modulo)
        for fn in ast.walk(arbol):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            nombres = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
            nombres |= {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
            if not (EMITEN_VEREDICTO & nombres):
                continue
            for nodo in ast.walk(fn):
                if not isinstance(nodo, ast.Compare) or len(nodo.ops) != 1:
                    continue
                if type(nodo.ops[0]).__name__ not in COMPARACIONES:
                    continue
                derecha = nodo.comparators[0]
                if not isinstance(derecha, ast.Constant):
                    continue
                if isinstance(derecha.value, bool) or not isinstance(
                    derecha.value, (int, float)
                ):
                    continue
                salida.append(f"{modulo}.{fn.name}:{ast.unparse(nodo)}")
    return sorted(set(salida))


def umbrales() -> list[str]:
    """`modulo.funcion:expresion` de cada umbral dentro de algo que emite veredicto."""
    fuentes: dict[str, str] = {}
    for fichero in sorted((RAIZ / "shmir_design").rglob("*.py")):
        if fichero.stem in fuentes:
            # ABORTA en vez de pisar. Hoy no hay dos modulos con el mismo nombre, pero
            # un subpaquete con un `blast.py` propio dejaria uno de los dos SIN AUDITAR
            # y el informe seguiria saliendo a cero — un fallo hacia el silencio, que es
            # el que no avisa y ademas tranquiliza (errata nº 29).
            raise SystemExit(
                f"Dos módulos se llaman {fichero.stem!r}: la clave de este informe es el "
                f"nombre del módulo y uno taparia al otro. Hay que cualificarla antes de "
                f"seguir."
            )
        fuentes[fichero.stem] = fichero.read_text(encoding="utf-8")
    return umbrales_de_fuentes(fuentes)


def auditar(ruta: Path = TABLA) -> dict:
    with ruta.open("rb") as f:
        tabla = tomllib.load(f)
    vivos = umbrales()
    return {
        "umbrales": vivos,
        "sin_declarar": [u for u in vivos if u not in tabla],
        "muertos": [u for u in tabla if u not in vivos],
        "con_supuesto": [
            u for u in vivos
            if u in tabla and not tabla[u]["supuesto"].lower().startswith("ninguno")
        ],
    }


def render(informe: dict) -> str:
    lineas = ["\n── Umbrales cuya lectura depende de un supuesto ──\n"]
    lineas.append(f"  {len(informe['umbrales'])} umbral(es) dentro de algo que emite")
    lineas.append("  veredicto. Los que LLEVAN un supuesto sobre los datos:")
    for u in informe["con_supuesto"]:
        lineas.append(f"    · {u}")
    if not informe["con_supuesto"]:
        lineas.append("    (ninguno: todos son criterios declarados o formato)")
    lineas.append("")
    for u in informe["sin_declarar"]:
        lineas.append(f"  · SIN DECLARAR: {u}")
    for u in informe["muertos"]:
        lineas.append(f"  · DECLARACIÓN CADUCADA: {u} ya no existe")
    lineas.append(
        "\n  Un umbral que decide declara de QUÉ supuesto depende su lectura y dónde"
        "\n  está declarado ese supuesto. Si no se puede escribir, el umbral está mal"
        "\n  planteado — es lo que pasó con el `> 1` (errata nº 56).\n"
    )
    return "\n".join(lineas)


def main() -> int:
    informe = auditar()
    print(render(informe))
    fallos = len(informe["sin_declarar"]) + len(informe["muertos"])
    if fallos:
        print(f"\ncheck_rules: {fallos} umbral(es) sin declarar.", file=sys.stderr)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
