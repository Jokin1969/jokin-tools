#!/usr/bin/env python3
"""El mismo nombre para dos cantidades distintas.

**La generalizacion de los cuatro pares duplicados y de la errata nº 57.** No es codigo
repetido —eso se ve en un `grep`— sino una CANTIDAD QUE SE MUEVE DE CONTEXTO SIN EL
SUPUESTO QUE LA SOSTENIA, con el nombre igual haciendo que parezca la misma.

El caso: `antisense` en `blast.BlastHit` es la HEBRA DEL SUJETO y en `specificity.Hit` es
«la sonda PUEDE APAREARSE con este transcrito». Y en el mismo par, `aligned` vale siempre
`len(sonda)` en un lado —el escaner casa ventanas exactas— y es un alineamiento LOCAL en
el otro: por eso la condicion de longitud no hacia falta escribirla alli y si aqui.

QUE MIRA, y por que ese recorte: **magnitudes DERIVADAS** —`@property`, algo que se
CALCULA— con el mismo nombre en mas de un modulo. El barrido ancho de «cualquier nombre
en mas de un modulo» da 207 y son casi todas etiquetas (`name`, `date`, `reason`); un
auditor asi se apaga el primer dia. Un campo guardado es una etiqueta; una derivacion
lleva supuestos dentro, que es justo lo que se queda atras al moverla.

QUE NO PUEDE HACER: no sabe si dos derivaciones calculan lo mismo. Obliga a DECIRLO, que
es lo que faltaba — `antisense` llevaba desde siempre significando dos cosas y el nombre
las tapaba.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TABLA = RAIZ / "data" / "homonimos.toml"
RELACIONES = {"MISMA_MAGNITUD", "DISTINTA"}


def derivadas_de_fuentes(fuentes: dict[str, str]) -> dict[str, list[str]]:
    """`{nombre: [modulo.Clase, ...]}` de cada `@property` definida en las fuentes.

    Separado de leer el paquete por la razon de siempre: un guardia que solo corre sobre
    el codigo ya arreglado no demuestra que muerda.
    """
    salida: dict[str, set[str]] = {}
    for modulo, codigo in sorted(fuentes.items()):
        for nodo in ast.walk(ast.parse(codigo, modulo)):
            if not isinstance(nodo, ast.ClassDef):
                continue
            for cuerpo in nodo.body:
                if not isinstance(cuerpo, ast.FunctionDef):
                    continue
                if any(
                    isinstance(d, ast.Name) and d.id == "property"
                    for d in cuerpo.decorator_list
                ):
                    salida.setdefault(cuerpo.name, set()).add(f"{modulo}.{nodo.name}")
    return {n: sorted(v) for n, v in salida.items()}


def homonimos_de_fuentes(fuentes: dict[str, str]) -> dict[str, list[str]]:
    """Solo las que se derivan en MAS DE UN modulo."""
    return {
        nombre: donde
        for nombre, donde in derivadas_de_fuentes(fuentes).items()
        if len({d.split(".")[0] for d in donde}) > 1
    }


def _fuentes() -> dict[str, str]:
    fuentes: dict[str, str] = {}
    for fichero in sorted((RAIZ / "shmir_design").rglob("*.py")):
        if fichero.stem in fuentes:
            raise SystemExit(
                f"Dos módulos se llaman {fichero.stem!r}: la clave de este informe es el "
                f"nombre del módulo y uno taparia al otro."
            )
        fuentes[fichero.stem] = fichero.read_text(encoding="utf-8")
    return fuentes


def auditar(ruta: Path = TABLA) -> dict:
    with ruta.open("rb") as f:
        tabla = tomllib.load(f)
    vivos = homonimos_de_fuentes(_fuentes())
    movidos = {
        nombre: {"declarado": tabla[nombre]["donde"], "real": donde}
        for nombre, donde in vivos.items()
        if nombre in tabla and sorted(tabla[nombre]["donde"]) != sorted(donde)
    }
    return {
        "homonimos": vivos,
        "sin_declarar": sorted(n for n in vivos if n not in tabla),
        "muertos": sorted(n for n in tabla if n not in vivos),
        "movidos": movidos,
        "distintas": sorted(
            n for n in vivos if n in tabla and tabla[n]["relacion"] == "DISTINTA"
        ),
        "tabla": tabla,
    }


def render(informe: dict) -> str:
    lineas = ["\n── El mismo nombre para dos cantidades distintas ──\n"]
    lineas.append(
        f"  {len(informe['homonimos'])} magnitud(es) derivada(s) con el mismo nombre en "
        f"más de un módulo."
    )
    lineas.append(
        f"  De ésas, {len(informe['distintas'])} son CANTIDADES DISTINTAS y lo declaran:"
    )
    for nombre in informe["distintas"]:
        donde = ", ".join(informe["homonimos"][nombre])
        lineas.append(f"    · {nombre}  ({donde})")
    lineas.append("")
    for nombre in informe["sin_declarar"]:
        donde = ", ".join(informe["homonimos"][nombre])
        lineas.append(f"  · SIN DECLARAR: {nombre} se deriva en {donde}")
    for nombre in informe["muertos"]:
        lineas.append(f"  · DECLARACIÓN CADUCADA: {nombre} ya no es homónimo")
    for nombre, datos in informe["movidos"].items():
        lineas.append(
            f"  · {nombre} se deriva ahora en {datos['real']} y la tabla dice "
            f"{datos['declarado']}"
        )
    lineas.append(
        "\n  Un criterio que se copia entre módulos lleva sus supuestos ESCRITOS, y si"
        "\n  no se pueden escribir es que no se puede copiar (principio nº 27).\n"
    )
    return "\n".join(lineas)


def main() -> int:
    informe = auditar()
    print(render(informe))
    fallos = (
        len(informe["sin_declarar"]) + len(informe["muertos"]) + len(informe["movidos"])
    )
    if fallos:
        print(f"\ncheck_rules: {fallos} homónimo(s) sin declarar o mal declarado(s).",
              file=sys.stderr)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
