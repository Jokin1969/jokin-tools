#!/usr/bin/env python3
"""Tests que FABRICAN un artefacto que YA EXISTE de verdad en el repositorio.

**De dónde sale.** De la segunda mitad del principio nº 18. Un parámetro tecleado y un
fixture sintético son **la misma enfermedad**: los dos validan un camino que nadie
recorre. `tests/test_usar_manifiesto.py` pasaba de punta a punta sobre un manifiesto
PARCIAL montado en un temporal — y el manifiesto real abortaba con un
`KeyError: 'polyadb'` (errata nº 33).

**Qué detecta.** Un test que ESCRIBE un fichero con el nombre de un artefacto que está en
`data/reference/`. Fabricar uno no está prohibido —hay motivos buenos: probar el caso
malo, la cabecera corta, el fichero corrupto— pero **hay que decir por qué no se usa el
real**, y la justificación va escrita en `data/fixtures_sinteticos.toml`.

**Lo que NO puede hacer**, declarado:

- no distingue un fixture legítimo de uno perezoso. Eso lo decide quien escribe el
  motivo; esto sólo obliga a escribirlo;
- reconoce el fabricado por el NOMBRE del fichero. Uno construido con otro nombre no se
  ve, y un test que lo mencione sin escribirlo tampoco cuenta.

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TABLA = RAIZ / "data" / "fixtures_sinteticos.toml"
REFERENCIA = RAIZ / "data" / "reference"

#: Como se reconoce que un test FABRICA un fichero. `shutil.copy` NO esta aqui a
#: proposito: copiar el real es USARLO, que es justo lo que se quiere. Meterlo daba 47
#: detecciones en 20 ficheros y la mayoria eran tests que hacen lo correcto — un auditor
#: con falsos positivos se acaba apagando.
ESCRITURA = re.compile(r"""write_text|write_bytes|open\([^)]*["']w""")

#: Cuantas lineas de distancia se admiten entre el nombre del artefacto y la escritura.
#: Un fichero de test menciona muchos nombres; lo que delata la fabricacion es que el
#: nombre y el `write_text` esten JUNTOS.
CERCA = 2


@dataclass
class Informe:
    filas: list[dict] = field(default_factory=list)
    sin_justificar: list[str] = field(default_factory=list)
    muertas: list[str] = field(default_factory=list)


def artefactos_reales() -> list[str]:
    """Lo que existe de verdad. Deriva del directorio, no de una lista."""
    return sorted(p.name for p in REFERENCIA.iterdir() if p.is_file())


def _alias_por_rol(texto: str) -> dict[str, set[str]]:
    """`CASETE_FA = _DEPOSITO["transgen"]` → {"CASETE_FA": {"aav_casete.fa", ...}}.

    El alias sale de un ROL y un rol tiene un nombre POR ESPECIE, asi que se devuelven
    todos: aqui no se sabe con que especie se construyo el diccionario del test, y quedarse
    con uno daria el de la ultima especie recorrida — que fue el fallo de la primera
    version (el humano pisaba al murino y la fabricacion volvia a no verse).

    Existe porque las dos auditorias se pisaban: `auditar_claves` PROHIBE escribir el
    nombre del fichero en un test —tiene que pedirselo a `species.required_files`— y esta
    reconocia la fabricacion justamente por ese nombre escrito. Con el nombre derivado, la
    fabricacion seguia ahi y la justificacion declarada pasaba a leerse como CADUCADA.
    Un auditor que deja de ver lo que existe es el fallo hacia el silencio.
    """
    import ast  # noqa: PLC0415
    import sys  # noqa: PLC0415

    sys.path.insert(0, str(RAIZ))
    from shmir_design import species  # noqa: PLC0415

    por_rol_todos: dict[str, set[str]] = {}
    for nombre in species.SPECIES:
        for fila in species.required_files(species.resolve(nombre)):
            por_rol_todos.setdefault(fila.role, set()).add(fila.filename)
    alias: dict[str, set[str]] = {}
    for nodo in ast.parse(texto).body:
        if not isinstance(nodo, ast.Assign) or len(nodo.targets) != 1:
            continue
        destino, valor = nodo.targets[0], nodo.value
        if not isinstance(destino, ast.Name):
            continue
        if (
            isinstance(valor, ast.Subscript)
            and isinstance(valor.slice, ast.Constant)
            and valor.slice.value in por_rol_todos
        ):
            alias[destino.id] = por_rol_todos[valor.slice.value]
    return alias


def fabricados() -> list[tuple[str, str]]:
    """(fichero de test, artefacto) de cada fabricacion detectada."""
    reales = artefactos_reales()
    salida: list[tuple[str, str]] = []
    for ruta in sorted((RAIZ / "tests").glob("*.py")):
        texto = ruta.read_text(encoding="utf-8")
        alias = _alias_por_rol(texto)
        lineas = texto.splitlines()
        escrituras = [i for i, l in enumerate(lineas) if ESCRITURA.search(l)]
        if not escrituras:
            continue
        for nombre in reales:
            # El nombre escrito, o el ALIAS que lo deriva del gestor.
            formas = [nombre] + [a for a, v in alias.items() if nombre in v]
            cerca = any(
                abs(i - j) <= CERCA
                for i, l in enumerate(lineas)
                if any(forma in l for forma in formas)
                for j in escrituras
            )
            if cerca:
                salida.append((ruta.name, nombre))
    return salida


def auditar() -> Informe:
    tabla = tomllib.loads(TABLA.read_text(encoding="utf-8"))
    declarado = {(e["test"], e["artefacto"]): e for e in tabla.get("fixture", [])}
    informe = Informe()
    vivos = set()
    for test, artefacto in fabricados():
        vivos.add((test, artefacto))
        entrada = declarado.get((test, artefacto))
        if entrada is None:
            informe.sin_justificar.append(f"{test} → {artefacto}")
            continue
        informe.filas.append(
            {
                "test": test,
                "artefacto": artefacto,
                "usa_el_real": entrada.get("usa_el_real", False),
                "por_que_no_el_real": entrada.get("por_que_no_el_real", ""),
            }
        )
    informe.muertas = sorted(
        f"{t} → {a}" for (t, a) in set(declarado) - vivos
    )
    return informe


def render(informe: Informe) -> str:
    fabrican = [f for f in informe.filas if not f["usa_el_real"]]
    lineas = ["", "  Tests que fabrican un artefacto que existe de verdad:"]
    lineas.append(
        f"    {len(fabrican)} fabricado(s) con motivo escrito · "
        f"{len(informe.filas) - len(fabrican)} usan el real"
    )
    for fila in fabrican:
        lineas.append(f"       · {fila['test']} → {fila['artefacto']}")
    if informe.sin_justificar:
        lineas.append("")
        lineas.append("  SIN JUSTIFICAR: " + ", ".join(informe.sin_justificar))
    lineas.append("")
    lineas.append(
        "  Fabricar no está prohibido: no decir POR QUÉ, sí. Un fixture sintético donde"
    )
    lineas.append(
        "  existe el real valida un camino que nadie recorre (principio nº 18)."
    )
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    print(render(auditar()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
