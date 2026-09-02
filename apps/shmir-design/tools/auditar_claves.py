"""Una magnitud, un sitio que la calcula — en los tests y en el codigo.

DOS MITADES, y son el mismo principio (nº 24) por sus dos caras:

  1. **Claves que un test ESCRIBE y alguien PRODUCE.** Un test que construye el
     diccionario de entrada con el mismo nombre que el codigo va a buscar no puede
     fallar: coincide por construccion.
  2. **Magnitudes calculadas en mas de un sitio.** Un digesto, un identificador o una
     formula que decide algo y que se calcula por duplicado: nada obliga a que las dos
     copias coincidan, asi que se separan sin dar ningun error. Cuarto par del mismo tipo
     en pocos dias.

--- 1. Que tests ESCRIBEN la clave por la que luego preguntan ---

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
MAGNITUDES = RAIZ / "data" / "magnitudes.toml"
TESTS = RAIZ / "tests"
#: Donde vive el codigo de produccion. `tests/` no entra: ahi duplicar una formula no
#: decide nada, y la mitad de arriba ya cubre lo que si.
PRODUCCION = ("shmir_design", "tools", "ui")


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


# ─── 2. Magnitudes calculadas en mas de un sitio ─────────────────────────────
#
# Tres reglas, y cada una tiene su instrumento:
#
#   DIGESTOS       cada `hashlib.*` declara QUE magnitud calcula. Dos sitios con la misma
#                  magnitud es un FALLO: o uno delega, o son numeros distintos y hay que
#                  decir por que. Guardia, cero.
#   IDENTIFICADORES un `*_id` construido a mano con una f-string o una concatenacion.
#                  Guardia, cero: es la regresion de la errata nº 48 — el id lo produce
#                  `identidad.run_id` y nadie mas.
#   FORMULAS       una expresion aritmetica que aparece literal en mas de un modulo. Aqui
#                  cero no se puede exigir —`fin - inicio + 1` esta en seis sitios y
#                  ninguno es sospechoso por si mismo— asi que es TRINQUETE: el techo se
#                  declara y solo puede bajar.


def _funcion_contenedora(arbol: ast.AST) -> dict[int, str]:
    dentro: dict[int, str] = {}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for hijo in ast.walk(nodo):
                dentro[id(hijo)] = nodo.name
    return dentro


def _ficheros_de_produccion():
    for raiz in PRODUCCION:
        yield from sorted((RAIZ / raiz).rglob("*.py"))


def digestos() -> list[str]:
    """`modulo.funcion` de cada sitio que calcula un digesto."""
    salida = []
    for fichero in _ficheros_de_produccion():
        arbol = ast.parse(fichero.read_text(encoding="utf-8"), str(fichero))
        dentro = _funcion_contenedora(arbol)
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and isinstance(nodo.func.value, ast.Name)
                and nodo.func.value.id == "hashlib"
            ):
                salida.append(f"{fichero.stem}.{dentro.get(id(nodo), '<modulo>')}")
    return sorted(set(salida))


def identificadores_a_mano() -> list[str]:
    """Un `*_id` construido con una f-string o una concatenacion, fuera del productor.

    Se mira el NOMBRE del destino —`run_id=`, `algo_id =`— y no el valor: lo que delata
    la construccion a mano es que alguien este montando la identidad de un registro con
    trozos. Las claves de widget de Streamlit (`key=`) no cuentan y por eso no se miran:
    son 69, todas correctas, y meterlas apagaria el guardia.
    """
    salida = []
    for fichero in _ficheros_de_produccion():
        arbol = ast.parse(fichero.read_text(encoding="utf-8"), str(fichero))
        for nodo in ast.walk(arbol):
            objetivos = []
            if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1:
                destino = nodo.targets[0]
                nombre = getattr(destino, "id", None) or getattr(destino, "attr", None)
                if nombre and nombre.endswith("_id"):
                    objetivos.append(nodo.value)
            elif isinstance(nodo, ast.Call):
                objetivos.extend(
                    kw.value for kw in nodo.keywords
                    if kw.arg and kw.arg.endswith("_id")
                )
            for valor in objetivos:
                if isinstance(valor, ast.JoinedStr) or (
                    isinstance(valor, ast.BinOp) and isinstance(valor.op, ast.Add)
                ):
                    salida.append(f"{fichero.name}:{nodo.lineno}")
    return sorted(set(salida))


def formulas_repetidas() -> dict[str, list[str]]:
    """Expresiones aritmeticas que aparecen literalmente en mas de un modulo.

    Se descartan las que llevan un literal de texto —son formato, no aritmetica—, las de
    menos de dos operadores y las anotaciones de tipo (`Path | str | None` es una union,
    no una cuenta).
    """
    sitios: dict[str, list[str]] = {}
    for fichero in _ficheros_de_produccion():
        arbol = ast.parse(fichero.read_text(encoding="utf-8"), str(fichero))
        anotaciones = {
            id(n.annotation)
            for n in ast.walk(arbol)
            if isinstance(n, (ast.AnnAssign, ast.arg)) and getattr(n, "annotation", None)
        }
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.BinOp, ast.Compare)):
                continue
            if id(nodo) in anotaciones:
                continue
            partes = [
                n for n in ast.walk(nodo) if isinstance(n, (ast.BinOp, ast.Compare))
            ]
            if len(partes) < 2:
                continue
            if any(
                isinstance(n, ast.Constant) and isinstance(n.value, str)
                for n in ast.walk(nodo)
            ):
                continue
            fuente = ast.unparse(nodo)
            if len(fuente) < 12:
                continue
            sitios.setdefault(fuente, []).append(fichero.name)
    return {
        f: sorted(set(m)) for f, m in sitios.items() if len(set(m)) > 1
    }


def revisar_magnitudes(ruta: Path = MAGNITUDES) -> dict:
    """Los tres hallazgos, ya resueltos contra la tabla."""
    with ruta.open("rb") as f:
        tabla = tomllib.load(f)
    declarados = tabla.get("digestos", {})
    vivos = digestos()

    por_magnitud: dict[str, list[str]] = {}
    for sitio in vivos:
        entrada = declarados.get(sitio)
        if entrada:
            por_magnitud.setdefault(entrada["magnitud"], []).append(sitio)

    permisivos = constructores_permisivos()
    declarados_ctor = tabla.get("constructores", {})
    formulas = formulas_repetidas()
    techo = tabla.get("formulas", {}).get("techo")
    return {
        "sin_declarar": [s for s in vivos if s not in declarados],
        "muertas": [s for s in declarados if s not in vivos],
        "repetidas": {m: s for m, s in por_magnitud.items() if len(s) > 1},
        "identificadores": identificadores_a_mano(),
        "permisivos": [c for c in permisivos if c not in declarados_ctor],
        "permisivos_muertos": [c for c in declarados_ctor if c not in permisivos],
        "formulas": formulas,
        "techo": techo,
        "techo_roto": techo is not None and len(formulas) != techo,
    }


def constructores_permisivos() -> list[str]:
    """`str(argumento)` que construye un objeto o un digesto SIN comprobar antes el tipo.

    Es la forma de la errata nº 50: `species.resolve` terminaba en
    `Species(scientific=str(name))` y con cualquier objeto fabricaba una especie de su
    `repr`, con la forma correcta y sin ningun error. Un constructor permisivo convierte
    un error de tipo en un DATO, que es peor que una excepcion porque no se ve.

    Se sigue UN nivel de asignacion —`limpio = str(name).strip()` y despues
    `Species(..., limpio)`— porque sin eso el caso original no se detecta: lo comprobe
    contra el fuente de antes del arreglo, y sin esa vuelta salia limpio.

    Se da por comprobado cuando la funcion tiene un `isinstance` sobre ESE argumento. No
    se mira la anotacion: la de `resolve` decia `name: str` y era justamente la que
    mentia — una anotacion no la comprueba nadie en tiempo de ejecucion.
    """
    salida = []
    for fichero in _ficheros_de_produccion():
        arbol = ast.parse(fichero.read_text(encoding="utf-8"), str(fichero))
        for fn in ast.walk(arbol):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = fn.args
            params = {
                x.arg for x in
                list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
            }
            comprobados = {
                n.args[0].id for n in ast.walk(fn)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "isinstance" and n.args
                and isinstance(n.args[0], ast.Name)
            }

            def raiz(nodo):
                while isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute):
                    nodo = nodo.func.value
                if (
                    isinstance(nodo, ast.Call)
                    and isinstance(nodo.func, ast.Name)
                    and nodo.func.id == "str"
                    and len(nodo.args) == 1
                    and isinstance(nodo.args[0], ast.Name)
                    and nodo.args[0].id in params
                    and nodo.args[0].id not in comprobados
                ):
                    return nodo.args[0].id
                return None

            contagiados = {}
            for nodo in ast.walk(fn):
                if (
                    isinstance(nodo, ast.Assign)
                    and len(nodo.targets) == 1
                    and isinstance(nodo.targets[0], ast.Name)
                ):
                    quien = raiz(nodo.value)
                    if quien:
                        contagiados[nodo.targets[0].id] = quien
            for nodo in ast.walk(fn):
                if not isinstance(nodo, ast.Call):
                    continue
                destino = None
                if isinstance(nodo.func, ast.Name) and nodo.func.id[:1].isupper():
                    destino = nodo.func.id
                elif (
                    isinstance(nodo.func, ast.Attribute)
                    and isinstance(nodo.func.value, ast.Name)
                    and nodo.func.value.id == "hashlib"
                ):
                    destino = "hashlib." + nodo.func.attr
                if not destino:
                    continue
                for sub in ast.walk(nodo):
                    quien = raiz(sub) or (
                        contagiados.get(sub.id) if isinstance(sub, ast.Name) else None
                    )
                    if quien:
                        salida.append(f"{fichero.name}:{fn.name}")
                        break
    return sorted(set(salida))
