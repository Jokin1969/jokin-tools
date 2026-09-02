"""Qué tests ESCRIBEN la clave por la que luego preguntan.

Un test que construye el diccionario de entrada con el mismo nombre que el codigo va a
buscar **no puede fallar**: coincide por construccion. Su verde no dice nada del
emparejamiento real y, mientras tanto, tapa un fallo estructural — tres veces en tres
dias (erratas nº 44, nº 47 y nº 48).

Es el principio nº 24 convertido en auditoria: *los dos lados de una comparacion salen de
la misma fuente, o la comparacion puede no darse nunca*. Aqui el «segundo lado» es el
test, y el productor esta declarado en `data/claves_derivadas.toml`.

QUE NO PUEDE HACER, dicho por delante:

  · no sigue la clave hasta el `dict.get` que la usa — no dice que el test ESTE mal, dice
    que **escribe una clave que alguien produce**, que es lo que hay que revisar;
  · en modo VALORES solo mira claves de diccionario y elementos de conjunto pasados a una
    llamada. Un literal suelto no cuenta a proposito: abrir `data/reference/mature.fa`
    por su nombre es usar el fichero real, que es lo correcto;
  · en modo FORMATO no distingue un uso de una cita, mas alla de saltarse los docstrings.

El numero correcto es CERO y cualquier hallazgo aborta. No es un trinquete: un test que
no puede fallar no es deuda pendiente, es una comprobacion que no comprueba.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TABLA = RAIZ / "data" / "claves_derivadas.toml"
TESTS = RAIZ / "tests"


def nombres_del_deposito() -> set[str]:
    """Los nombres que emite `species.required_files`, para TODAS las especies."""
    sys.path.insert(0, str(RAIZ))
    from shmir_design import species  # noqa: PLC0415

    salida: set[str] = set()
    for nombre in species.SPECIES:
        for fila in species.required_files(species.resolve(nombre)):
            salida.add(fila.filename)
            if fila.companion:
                salida.add(fila.companion)
    return salida


#: Los enumeradores que este modulo sabe resolver. Uno no declarado ABORTA: apuntar a una
#: funcion que no existe daria un conjunto vacio, o sea CERO hallazgos — un auditor que se
#: equivoca hacia el silencio es peor que no tenerlo (la leccion de la alcanzabilidad).
ENUMERADORES = {"nombres_del_deposito": nombres_del_deposito}


def cargar_tabla(ruta: Path = TABLA) -> dict:
    with ruta.open("rb") as f:
        datos = tomllib.load(f)
    for productor in datos.get("productor", []):
        modo = productor.get("modo")
        if modo == "VALORES":
            if productor.get("enumerador") not in ENUMERADORES:
                raise SystemExit(
                    f"El productor {productor.get('nombre')!r} declara el enumerador "
                    f"{productor.get('enumerador')!r} y este módulo no lo conoce; los "
                    f"que hay son {', '.join(sorted(ENUMERADORES))}. Se aborta: uno "
                    f"inexistente daria cero valores y cero hallazgos."
                )
        elif modo == "FORMATO":
            re.compile(productor["patron"])
        else:
            raise SystemExit(
                f"El productor {productor.get('nombre')!r} declara el modo {modo!r}; "
                f"los que hay son VALORES y FORMATO."
            )
    return datos


def _docstrings(arbol: ast.AST) -> set[str]:
    fuera = set()
    for nodo in ast.walk(arbol):
        if isinstance(
            nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            texto = ast.get_docstring(nodo, clean=False)
            if texto:
                fuera.add(texto)
    return fuera


def _claves_pasadas_a_una_llamada(arbol: ast.AST):
    """(linea, clave) de cada dict/set literal que va como argumento de una llamada."""
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        for arg in list(nodo.args) + [k.value for k in nodo.keywords]:
            if isinstance(arg, ast.Dict):
                elementos = arg.keys
            elif isinstance(arg, ast.Set):
                elementos = arg.elts
            else:
                continue
            for elem in elementos:
                if isinstance(elem, ast.Constant) and isinstance(elem.value, str):
                    yield nodo.lineno, elem.value


def _textos(arbol: ast.AST, fuera: set[str]):
    """(linea, texto) de literales y f-strings, sin los docstrings."""
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.JoinedStr):
            yield nodo.lineno, "".join(
                v.value if isinstance(v, ast.Constant) else "{}" for v in nodo.values
            )
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            if nodo.value not in fuera:
                yield nodo.lineno, nodo.value


def revisar_fuente(texto: str, nombre: str, tabla: dict) -> list[dict]:
    """Los hallazgos de UN fichero. Separado para poder probarlo con fuente sintetica."""
    arbol = ast.parse(texto, nombre)
    fuera = _docstrings(arbol)
    hallazgos = []
    for productor in tabla.get("productor", []):
        # Si el test LLAMA al productor, no lo esta transcribiendo. Se exige la forma de
        # LLAMADA y no la mencion: `corrida.run_id ==` LEE el id, no lo produce, y con
        # una busqueda por subcadena eso bastaba para eximir al fichero entero — un
        # auditor que se equivoca hacia el silencio.
        if any(
            re.search(rf"\b{re.escape(llamada)}\s*\(", texto)
            for llamada in productor.get("llamadas", [])
        ):
            continue
        if productor["modo"] == "VALORES":
            valores = ENUMERADORES[productor["enumerador"]]()
            for linea, clave in _claves_pasadas_a_una_llamada(arbol):
                if clave in valores:
                    hallazgos.append({
                        "fichero": nombre, "linea": linea,
                        "productor": productor["nombre"], "clave": clave,
                    })
        else:
            patron = re.compile(productor["patron"])
            visto = set()
            for linea, cadena in _textos(arbol, fuera):
                encaje = patron.search(cadena)
                if encaje and productor["nombre"] not in visto:
                    visto.add(productor["nombre"])
                    hallazgos.append({
                        "fichero": nombre, "linea": linea,
                        "productor": productor["nombre"], "clave": encaje.group(0),
                    })
    return hallazgos


def revisar(directorio: Path = TESTS, tabla: dict | None = None) -> list[dict]:
    tabla = tabla or cargar_tabla()
    exentos = tabla.get("exentos", {})
    hallazgos = []
    for fichero in sorted(directorio.glob("*.py")):
        for h in revisar_fuente(
            fichero.read_text(encoding="utf-8"), fichero.name, tabla
        ):
            if f"{h['fichero']}:{h['linea']}" in exentos:
                continue
            hallazgos.append(h)
    return hallazgos


def exenciones_caducadas(directorio: Path = TESTS, tabla: dict | None = None):
    """Exenciones que ya no corresponden a ningun hallazgo. Caducan igual que las otras."""
    tabla = tabla or cargar_tabla()
    sin_exentos = dict(tabla)
    sin_exentos["exentos"] = {}
    vivos = {f"{h['fichero']}:{h['linea']}" for h in revisar(directorio, sin_exentos)}
    return sorted(set(tabla.get("exentos", {})) - vivos)


def informe() -> int:
    tabla = cargar_tabla()
    hallazgos = revisar(tabla=tabla)
    caducadas = exenciones_caducadas(tabla=tabla)
    print("\n── Claves que un test ESCRIBE y alguien PRODUCE ──\n")
    for productor in tabla.get("productor", []):
        print(f"  {productor['nombre']}  [{productor['modo']}]")
    print()
    if not hallazgos and not caducadas:
        print("  0 — el número correcto. Ningún test pregunta por la clave que él mismo")
        print("      ha escrito. No es un trinquete: es un guardia (principio nº 24).\n")
        return 0
    for h in hallazgos:
        print(f"  · {h['fichero']}:{h['linea']}  {h['clave']!r}  → {h['productor']}")
    for e in caducadas:
        print(f"  · EXENCIÓN CADUCADA: {e} ya no corresponde a ningún hallazgo")
    print(
        "\n  Se le pide la clave al productor, o el sitio se declara en"
        "\n  data/claves_derivadas.toml con su motivo. Un test que escribe la clave por"
        "\n  la que pregunta no puede fallar.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(informe())
