#!/usr/bin/env python3
"""El PREFIJO del espacio de coordenadas no se teclea fuera de `coords`.

**De donde sale.** De la errata nº 121, y de que arreglarla cinco veces no la arreglo.
`coords.Position` ya impedia imprimir un entero desnudo, y con eso bastaba para el fallo
que se habia visto: un `1018` a solas no identifica ningun sitio. Lo que NO impedia era
teclear el prefijo: `f"3utr:{start}"` se escribe igual de facil, se lee igual de bien y
sobre un tilado del transcrito etiqueta como 3'UTR una posicion que no lo es.

Y eso paso **cinco veces en cinco modulos distintos**, cada una arreglada por su cuenta
—`outputs`, `presentation`, `dossier`, `offtarget`, `informe_doc`— mientras el sexto
seguia escribiendolo. Un arreglo que hay que acordarse de repetir no es un arreglo: es
una costumbre. Este guardia convierte la costumbre en imposibilidad. **Si el literal no
se puede teclear, no puede haber un sexto sitio.**

**Que se busca, exactamente.** Una cadena literal —no un comentario, no un docstring—
que TERMINE en `3utr:` o `tx:`. Terminar es la señal de que lo que viene detras llega de
fuera: una interpolacion de f-string (`f"3utr:{x}"`), un `.join`, una concatenacion.
Eso es fabricar una etiqueta, y fabricarla es lo unico que hace `coords`.

Una mencion con el numero DENTRO —`«3utr:221 era uno de los cuatro inmunes»`— es prosa:
nombra un caso concreto, no etiqueta nada. Va aparte, y tambien declarada: si aparece un
literal de prosa que la tabla no conoce, el guardia falla igual. La diferencia no es que
una se perdone: es que una se arregla y la otra se explica.

**Lo que NO cubre, declarado:**

- los **comentarios**, que no son literales y no salen por ninguna parte;
- los **docstrings**, por lo mismo: no llegan a ninguna salida del proyecto;
- los **tests**, que es donde el literal SI tiene que poder escribirse — un test que
  comprueba que sale `3utr:449` es el control adversario de esta misma regla, y
  prohibirselo dejaria la regla sin quien la verifique;
- `coords.py`, que es quien lo emite;
- un `3utr` **sin dos puntos** —el `mvm_actual__3utr959` de un nombre de construccion—,
  que es un identificador y no una etiqueta de posicion. No lo mira: cambiarlo romperia
  claves ya guardadas, y como no lleva numero pegado con prefijo no se lee como una
  coordenada.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TABLA = RAIZ / "data" / "marcos_en_prosa.toml"

#: El unico modulo que puede teclear el prefijo: es el que lo define.
DUEÑO = "shmir_design/coords.py"

#: Directorios que no se miran, con su motivo en el docstring de arriba.
FUERA = ("tests", "build")

WHY_NOT_THE_TESTS = (
    "Los tests SI pueden escribir el literal: un test que exige `3utr:449` en la salida "
    "es el control adversario de esta regla. Prohibirselo dejaria la regla sin quien la "
    "verifique."
)


@dataclass
class Informe:
    #: Literales que FABRICAN una etiqueta. El numero correcto es cero, sin excepciones.
    fabrican: list[dict] = field(default_factory=list)
    #: Menciones en prosa declaradas en la tabla, con su motivo.
    prosa: list[dict] = field(default_factory=list)
    #: Menciones en prosa que NADIE ha declarado.
    sin_declarar: list[dict] = field(default_factory=list)
    #: Entradas de la tabla que ya no corresponden a ningun literal.
    muertas: list[dict] = field(default_factory=list)


def _prefijos() -> tuple[str, ...]:
    """Los prefijos, PEDIDOS a `coords`. No se teclean aqui tampoco.

    Escribirlos en este fichero seria la misma enfermedad que persigue: si mañana entra
    un tercer espacio, el guardia dejaria de verlo sin dar ningun error.
    """
    sys.path.insert(0, str(RAIZ))
    from shmir_design.coords import SEPARATOR, Frame

    return tuple(f"{f.value}{SEPARATOR}" for f in Frame)


def _docstrings(arbol: ast.AST) -> set[int]:
    encontrados = set()
    for nodo in ast.walk(arbol):
        if isinstance(
            nodo, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            cuerpo = nodo.body
            if (
                cuerpo
                and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant)
                and isinstance(cuerpo[0].value.value, str)
            ):
                encontrados.add(id(cuerpo[0].value))
    return encontrados


def _simbolo(arbol: ast.AST, linea: int) -> str:
    """Como se llama lo que contiene esa linea: la funcion, la clase o la CONSTANTE.

    La constante importa tanto como las otras dos. Buena parte de la prosa de este
    proyecto vive en constantes de modulo —`WHY_NOT_SUMMED`, `LOS_DOS_NO_SE_SUSTITUYEN`—
    y con `<modulo>` como clave, una declaracion cubriria el fichero ENTERO: una mencion
    nueva en otra constante del mismo modulo entraria sin que nadie la mirase. Eso es un
    guardia calibrado sobre un caso, que es la forma que tiene de dejar de servir.
    """
    dentro = [
        (n.lineno, n.name)
        for n in ast.walk(arbol)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and n.lineno <= linea <= (n.end_lineno or n.lineno)
    ]
    if dentro:
        return max(dentro)[1]
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            continue
        if not nodo.lineno <= linea <= (nodo.end_lineno or nodo.lineno):
            continue
        objetivos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
        nombres = [t.id for t in objetivos if isinstance(t, ast.Name)]
        if nombres:
            return nombres[0]
    return "<modulo>"


def analizar_fuentes(fuentes: dict[str, str], declaradas: list[dict]) -> Informe:
    prefijos = _prefijos()
    informe = Informe()
    vistas: set[tuple[str, str]] = set()
    for nombre, texto in sorted(fuentes.items()):
        arbol = ast.parse(texto, filename=nombre)
        docs = _docstrings(arbol)
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Constant) or not isinstance(nodo.value, str):
                continue
            if id(nodo) in docs:
                continue
            for prefijo in prefijos:
                desde = 0
                while (donde := nodo.value.find(prefijo, desde)) != -1:
                    desde = donde + len(prefijo)
                    fila = {
                        "fichero": nombre,
                        "linea": nodo.lineno,
                        "simbolo": _simbolo(arbol, nodo.lineno),
                        "prefijo": prefijo,
                    }
                    if desde == len(nodo.value):
                        informe.fabrican.append(fila)
                        continue
                    clave = (nombre, fila["simbolo"])
                    vistas.add(clave)
                    motivo = next(
                        (
                            d["por_que"]
                            for d in declaradas
                            if d["fichero"] == nombre and d["simbolo"] == fila["simbolo"]
                        ),
                        "",
                    )
                    if motivo:
                        informe.prosa.append({**fila, "por_que": motivo})
                    else:
                        informe.sin_declarar.append(fila)
    informe.muertas = [
        d for d in declaradas if (d["fichero"], d["simbolo"]) not in vistas
    ]
    return informe


def _fuentes() -> dict[str, str]:
    salida = {}
    for ruta in sorted(RAIZ.rglob("*.py")):
        rel = ruta.relative_to(RAIZ)
        if rel.parts[0] in FUERA or str(rel) == DUEÑO:
            continue
        salida[str(rel)] = ruta.read_text(encoding="utf-8")
    return salida


def declaraciones() -> list[dict]:
    if not TABLA.exists():
        return []
    with TABLA.open("rb") as f:
        return list(tomllib.load(f).get("mencion", ()))


def auditar() -> Informe:
    return analizar_fuentes(_fuentes(), declaraciones())


def render(informe: Informe) -> str:
    lineas = ["", "  El prefijo del marco, fuera de `coords`:"]
    lineas.append(
        f"    {len(informe.prosa):3}  MENCIÓN en prosa — nombra un caso, no etiqueta"
    )
    if informe.fabrican:
        lineas.append(f"    {len(informe.fabrican):3}  ⚠  FABRICAN una etiqueta:")
        for fila in informe.fabrican:
            lineas.append(
                f"         · {fila['fichero']}:{fila['linea']}  "
                f"{fila['simbolo']}  «{fila['prefijo']}»"
            )
    else:
        lineas.append("      0  FABRICAN una etiqueta")
    if informe.sin_declarar:
        lineas.append(f"    {len(informe.sin_declarar):3}  ⚠  PROSA sin declarar:")
        for fila in informe.sin_declarar:
            lineas.append(
                f"         · {fila['fichero']}:{fila['linea']}  {fila['simbolo']}"
            )
    if informe.muertas:
        lineas.append(f"    {len(informe.muertas):3}  ⚠  DECLARACIONES muertas:")
        for fila in informe.muertas:
            lineas.append(f"         · {fila['fichero']}  {fila['simbolo']}")
    lineas.append("")
    lineas.append(
        "  El prefijo lo pone `coords.label`/`span`, que además comprueba el rango. Un"
    )
    lineas.append(
        "  literal tecleado se salta el invariante y ya lo hizo cinco veces (errata 121)."
    )
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    informe = auditar()
    print(render(informe))
    fallos = (
        len(informe.fabrican) + len(informe.sin_declarar) + len(informe.muertas)
    )
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
