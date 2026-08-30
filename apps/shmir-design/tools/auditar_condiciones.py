#!/usr/bin/env python3
"""Condiciones que NO PUEDEN SER FALSAS: una rama muerta con forma de decisión.

**De dónde sale.** Del principio nº 19. Tres fallos con la misma forma —`x or defecto`
con la cadena vacía (errata nº 18), `Path.is_file()` sobre un fichero de 0 bytes
(errata nº 15) y `if fila["acciones"]` sobre una lista que nunca está vacía
(errata nº 34)— y en los tres **un valor legítimo tiene la forma de otra cosa**, con la
comprobación mirando el CONTENEDOR cuando la pregunta era por el CONTENIDO.

**Por qué este detector y no el ancho.** El barrido general —cualquier verdad sobre una
colección, un `Path` o un `or` con defecto— da 187 posiciones en este paquete y **casi
todas son correctas**: en `if not filas` la vacuidad ES la pregunta. Un auditor así se
apaga el primer día, y un auditor apagado es peor que ninguno. Lo que sí se decide sin
discusión es el caso extremo: una condición **que no puede ser falsa nunca**. Eso no es
un criterio opinable, es código muerto — y era exactamente `fila["acciones"]`, que valía
`["ver", …]` o `["subir"]`: dos cosas distintas, las dos verdaderas.

Por eso **no es un trinquete, es un guardia**: el número correcto es CERO y sube a fallo.

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

#: NO hay lista de ficheros excluidos, y no es un olvido. La primera version excluia
#: `check_tildes.py` —lleva el vocabulario del castellano en un diccionario de cientos de
#: entradas— y dejo de hacer falta en cuanto el detector distinguio TABLA de REGISTRO:
#: ese vocabulario es una tabla de modulo, asi que ya no entra. Dos mecanismos para el
#: mismo trabajo es uno de mas, y el que se queda es el que explica POR QUE.
#: Constructores que conservan la vacuidad de su argumento.
ENVOLTORIOS = ("list", "tuple", "set", "sorted", "frozenset")

LO_QUE_NO_VE = (
    "Sólo mira claves de DICCIONARIO cuyo valor se construye con literales en todos los "
    "sitios donde aparece esa clave. NO ve una variable local que nunca esté vacía, ni "
    "un valor que venga de un fichero o de una llamada, ni un atributo de dataclass. Es "
    "el precio de no tener falsos positivos: un CERO aquí significa «ninguna de las que "
    "sé mirar», no «ninguna». El barrido ancho existe y da 187 posiciones legítimas; "
    "está en el principio nº 19 por qué no se convirtió en regla."
)


@dataclass
class Informe:
    hallazgos: list[dict] = field(default_factory=list)
    #: Claves cuyo valor nunca esta vacio. Intermedio, util para depurar el detector.
    siempre: list[str] = field(default_factory=list)


def _mapas_y_valores(arboles: dict[str, ast.Module]):
    """Los diccionarios de módulo (para resolver `TABLA[clave]`) y clave → valores."""
    mapas: dict[str, list] = {}
    valores: dict[str, list] = defaultdict(list)
    tablas: set[int] = set()   # id() de los Dict que son TABLA, no REGISTRO
    for arbol in arboles.values():
        for n in ast.walk(arbol):
            if (isinstance(n, ast.Assign) and len(n.targets) == 1
                    and isinstance(n.targets[0], ast.Name)):
                v = n.value
                if (isinstance(v, ast.Call)
                        and getattr(v.func, "id", "") == "MappingProxyType" and v.args):
                    v = v.args[0]
                if isinstance(v, ast.Dict):
                    mapas[n.targets[0].id] = list(v.values)
                    tablas.add(id(v))
    for arbol in arboles.values():
        for n in ast.walk(arbol):
            # DOS ESPACIOS DE NOMBRES DISTINTOS, y confundirlos da un falso positivo.
            # `ACTIONS = {"presente": (...), "ausente": (...)}` es una TABLA: sus claves
            # son valores del dominio, no campos de un registro. Un registro que tuviera
            # un campo `presente` heredaba la «no vacuidad» de la tabla y salia marcado.
            # Lo cazó el propio test de este detector, con el fixture del fallo real.
            if isinstance(n, ast.Dict) and id(n) not in tablas:
                for clave, valor in zip(n.keys, n.values, strict=True):
                    if isinstance(clave, ast.Constant) and isinstance(clave.value, str):
                        valores[clave.value].append(valor)
    return mapas, valores


def _no_vacio(v, mapas) -> bool | None:
    """`True` = seguro no vacio. `None` = NO SE SABE, que aqui es lo mismo que «no»."""
    if isinstance(v, (ast.List, ast.Tuple, ast.Set)):
        return True if v.elts else None
    if isinstance(v, ast.Dict):
        return True if v.keys else None
    if isinstance(v, ast.Constant) and isinstance(v.value, str):
        return True if v.value else None
    if isinstance(v, ast.Call) and getattr(v.func, "id", "") in ENVOLTORIOS:
        return _no_vacio(v.args[0], mapas) if v.args else None
    if isinstance(v, ast.Subscript) and isinstance(v.value, ast.Name):
        opciones = mapas.get(v.value.id)
        if opciones:
            return True if all(_no_vacio(o, mapas) is True for o in opciones) else None
    return None


def _pruebas(n) -> list:
    if isinstance(n, (ast.If, ast.While, ast.IfExp, ast.Assert)):
        return [n.test]
    if isinstance(n, ast.comprehension):
        return list(n.ifs)
    return []


def analizar_fuentes(fuentes: dict[str, str]) -> list[dict]:
    """El análisis, sobre fuentes en memoria. Así se le puede dar el código DE ANTES."""
    arboles = {nombre: ast.parse(texto) for nombre, texto in fuentes.items()}
    mapas, valores = _mapas_y_valores(arboles)
    siempre = {
        clave for clave, vs in valores.items()
        if vs and all(_no_vacio(v, mapas) is True for v in vs)
    }
    hallazgos: list[dict] = []
    for nombre, arbol in arboles.items():
        for n in ast.walk(arbol):
            for prueba in _pruebas(n):
                partes = prueba.values if isinstance(prueba, ast.BoolOp) else [prueba]
                for sub in partes:
                    if isinstance(sub, ast.UnaryOp) and isinstance(sub.op, ast.Not):
                        sub = sub.operand
                    if (isinstance(sub, ast.Subscript)
                            and isinstance(sub.slice, ast.Constant)
                            and sub.slice.value in siempre):
                        hallazgos.append({
                            "fichero": nombre,
                            "linea": sub.lineno,
                            "clave": sub.slice.value,
                            "fuente": ast.unparse(prueba)[:100],
                        })
    return hallazgos


def _fuentes() -> dict[str, str]:
    salida = {}
    for ruta in sorted(RAIZ.rglob("*.py")):
        rel = ruta.relative_to(RAIZ)
        if rel.parts[0] in {"tests", "build"}:
            continue
        salida[str(rel)] = ruta.read_text(encoding="utf-8")
    return salida


def auditar() -> Informe:
    fuentes = _fuentes()
    return Informe(hallazgos=analizar_fuentes(fuentes))


def render(informe: Informe) -> str:
    lineas = ["", "  Condiciones que NO PUEDEN ser falsas:"]
    if not informe.hallazgos:
        lineas.append("    0 — el número correcto. No es un trinquete: es un guardia.")
    for h in informe.hallazgos:
        lineas.append(f"    ⚠  {h['fichero']}:{h['linea']}  {h['fuente']}")
    lineas.append("")
    lineas.append(
        "  Una rama que no puede ejecutarse no es una decisión (principio nº 19)."
    )
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    informe = auditar()
    print(render(informe))
    return 1 if informe.hallazgos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
