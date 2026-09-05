#!/usr/bin/env python3
"""`zip` y `map` sobre DOS secuencias: o van emparejadas, o la truncación es a propósito.

**De dónde sale.** Del principio nº 19, del lado que **no lleva ninguna condición**. Los
tres primeros casos de ese principio —`x or defecto`, `is_file()` sobre 0 bytes,
`if fila["acciones"]`— se pueden buscar mirando los `if`. Éste no: `zip` trunca al más
corto **en silencio**, y lo que produce no es un error sino un **informe más corto que se
lee como un resultado**. Ninguna búsqueda de condiciones lo habría encontrado.

**La regla, con dos salidas y ninguna tercera.** Un `zip` de dos secuencias distintas es
una de dos cosas, y sólo quien lo escribe sabe cuál:

- **van en paralelo** —una fila y su ancho, un candidato y su veredicto de plegado— y
  entonces distinta longitud es un fallo: `strict=True`, de la biblioteca estándar desde
  3.10, que aborta en vez de acortar;
- **la truncación ES la intención** —cinco columnas de layout para tres herramientas, un
  motivo de 7 nt contra un consenso de 5 posiciones— y entonces se escribe
  `# zip-ok: <motivo>`, la misma convención que `# rule2-ok`.

Dejarlo implícito no es una tercera opción: es que el lector adivine.

**Lo que NO puede hacer**, declarado:

- no sabe si las dos secuencias tienen de verdad la misma longitud. No lo comprueba: lo
  que exige es que alguien lo haya DECIDIDO y escrito;
- `zip(x, x[1:])` no es un par, es una VENTANA sobre una sola secuencia, y se excluye.
  Exigirle `strict` sería ruido y encima imposible: la segunda es más corta a propósito.

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

#: La marca que declara una truncacion deliberada, en la linea del `zip` o la de antes.
MARCA = re.compile(r"#\s*zip-ok:\s*(.+)$")


@dataclass
class Informe:
    #: Sin `strict=` y sin `# zip-ok:`: no dicen cual de las dos cosas son.
    mudos: list[dict] = field(default_factory=list)
    #: Con `strict=True`: declarados EMPAREJADOS.
    emparejados: list[dict] = field(default_factory=list)
    #: Con `# zip-ok:`: declarados TRUNCADOS a proposito, con su motivo.
    exentos: list[dict] = field(default_factory=list)


def _es_ventana(a: str, b: str) -> bool:
    """`zip(x, x[1:])`: la MISMA expresion con un corte. No empareja dos cosas."""
    return b.startswith(a) and "[" in b[len(a):]


def _marca_encima(lineas: list[str], indice: int) -> str:
    """`# zip-ok: ...` en esa linea o en el bloque de comentario contiguo de encima."""
    if 0 <= indice < len(lineas):
        encontrado = MARCA.search(lineas[indice])
        if encontrado:
            return encontrado.group(1).strip()
    indice -= 1
    while 0 <= indice < len(lineas) and lineas[indice].lstrip().startswith("#"):
        encontrado = MARCA.search(lineas[indice])
        if encontrado:
            return encontrado.group(1).strip()
        indice -= 1
    return ""


def _inicio_de_la_sentencia(arbol, linea: int) -> int:
    """La SENTENCIA que contiene esa linea, no la llamada.

    Segunda equivocacion del detector, y la misma familia que la primera: el `zip` de
    `_donor_score` vive dentro de un `return sum(...)` que empieza una linea antes, asi
    que encima de la llamada no hay comentario ninguno — hay codigo. Buscar el bloque a
    partir de la llamada dejaba fuera precisamente el caso mejor documentado.
    """
    # La MAS INTERNA de las que la contienen, no la mas externa. La primera version se
    # quedaba con el `def` de la funcion —tambien la contiene— y miraba el comentario de
    # encima de la firma, que no es el que documenta la linea.
    dentro = [
        n.lineno for n in ast.walk(arbol)
        if isinstance(n, ast.stmt) and n.lineno <= linea <= (n.end_lineno or n.lineno)
    ]
    return max(dentro) if dentro else linea


def analizar_fuentes(fuentes: dict[str, str]) -> Informe:
    informe = Informe()
    for nombre, texto in fuentes.items():
        lineas = texto.splitlines()
        arbol = ast.parse(texto)
        for n in ast.walk(arbol):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)):
                continue
            if n.func.id == "zip":
                secuencias = n.args
            elif n.func.id == "map":
                secuencias = n.args[1:]   # el primero es la funcion
            else:
                continue
            if len(secuencias) < 2:
                continue
            partes = [ast.unparse(a) for a in secuencias]
            if _es_ventana(partes[0], partes[1]):
                continue
            fila = {
                "fichero": nombre,
                "linea": n.lineno,
                "fuente": f"{n.func.id}({', '.join(p[:40] for p in partes)})",
            }
            if any(k.arg == "strict" for k in n.keywords):
                informe.emparejados.append(fila)
                continue
            # La marca vale en la linea del `zip` o en cualquier punto del BLOQUE DE
            # COMENTARIO contiguo de encima. La primera version miraba solo dos lineas
            # y no encontraba ninguna de las cuatro reales: un motivo que merece
            # escribirse ocupa varias lineas y `# zip-ok:` va en la primera, que queda
            # arriba del todo. Un detector que obliga a redactar en una linea obliga a
            # redactar mal.
            motivo = _marca_encima(lineas, n.lineno - 1)
            if not motivo:
                motivo = _marca_encima(
                    lineas, _inicio_de_la_sentencia(arbol, n.lineno) - 1
                )
            if motivo:
                informe.exentos.append({**fila, "motivo": motivo})
            else:
                informe.mudos.append(fila)
    return informe


def _fuentes() -> dict[str, str]:
    salida = {}
    for ruta in sorted(RAIZ.rglob("*.py")):
        rel = ruta.relative_to(RAIZ)
        if rel.parts[0] in {"tests", "build"}:
            continue
        salida[str(rel)] = ruta.read_text(encoding="utf-8")
    return salida


def auditar() -> Informe:
    return analizar_fuentes(_fuentes())


def render(informe: Informe) -> str:
    lineas = ["", "  Secuencias emparejadas (`zip` / `map` de dos):"]
    lineas.append(
        f"    {len(informe.emparejados):3}  EMPAREJADAS — `strict=True`, distinta "
        f"longitud aborta"
    )
    lineas.append(
        f"    {len(informe.exentos):3}  TRUNCAN a propósito — con su motivo escrito"
    )
    for fila in informe.exentos:
        lineas.append(f"         · {fila['fichero']}:{fila['linea']}  {fila['motivo'][:70]}")
    if informe.mudos:
        lineas.append(f"    {len(informe.mudos):3}  ⚠  SIN DECLARAR:")
        for fila in informe.mudos:
            lineas.append(f"         · {fila['fichero']}:{fila['linea']}  {fila['fuente']}")
    lineas.append("")
    lineas.append(
        "  `zip` trunca al más corto EN SILENCIO: no hay condición que buscar y lo que"
    )
    lineas.append(
        "  sale es un informe corto que se lee como un resultado (principio nº 19)."
    )
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    informe = auditar()
    print(render(informe))
    return 1 if informe.mudos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
