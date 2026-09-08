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
- ~~un `3utr` **sin dos puntos** —el `mvm_actual__3utr959` de un nombre de
  construccion—, que es un identificador y no una etiqueta de posicion~~. **EXENCION
  RETIRADA (2026-09-07): la refuto el uso.** Ese nombre salio de la app en un FASTA, se
  leyo como `3utr:959` y se retiro un candidato del panel citandolo asi — cuando la
  construccion era la de `3utr:10`, que es `tx:959`. Una excepcion declarada es una
  HIPOTESIS; esta decia que un identificador no se lee como una coordenada, y se leyo
  como una coordenada la primera vez que salio. Ahora se mira: un literal de f-string
  que TERMINA en el valor del marco —sin los dos puntos— y va seguido de una
  interpolacion fabrica una etiqueta igual. Se exige el separador delante (`__3utr`,
  `_tx`) para no morder una palabra que acabe en `tx`, como `ctx`.

**LA PREGUNTA QUE HAY QUE HACERLE A CADA EXENCION NUEVA** (principio nº 54): ¿afirma
algo sobre como se va a LEER algo fuera del codigo? Si si, no la puede comprobar ningun
test —habla de una persona— y se declara como HIPOTESIS, no como hecho. La de arriba
decia que un identificador no se lee como una coordenada; se leyo como una coordenada la
primera vez que salio de la app.

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
    #: CUANTOS ficheros se leyeron. Va primero porque es lo que distingue «no hay
    #: literales» de «no he mirado»: las dos cosas dan cero hallazgos y sólo una es un
    #: resultado (principio nº 51). Un guardia declara lo que recorrió, no sólo su
    #: veredicto.
    ficheros: int = 0
    #: Literales que FABRICAN una etiqueta. El numero correcto es cero, sin excepciones.
    fabrican: list[dict] = field(default_factory=list)
    #: Menciones en prosa declaradas en la tabla, con su motivo.
    prosa: list[dict] = field(default_factory=list)
    #: Menciones en prosa que NADIE ha declarado.
    sin_declarar: list[dict] = field(default_factory=list)
    #: Entradas de la tabla que ya no corresponden a ningun literal.
    muertas: list[dict] = field(default_factory=list)
    #: Sitios donde el MARCO lo pone un valor POR DEFECTO. Cero, sin excepciones.
    por_defecto: list[dict] = field(default_factory=list)
    #: Funciones que reciben una posicion del panel (`start`/`starts`) y ESCRIBEN el
    #: marco en vez de recibirlo o derivarlo. Cero, sin excepciones.
    escrito_sobre_un_start: list[dict] = field(default_factory=list)


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


#: Lo que puede ir DELANTE del valor del marco para que sea un token y no el final de
#: una palabra. Sin esto, `f"ctx{n}"` saldria como fabricacion de `tx` — y un guardia con
#: falsos positivos se acaba apagando.
SEPARADORES = "_-/.:| ("


def _fabrica_sin_dos_puntos(arbol: ast.AST, valores: tuple[str, ...]) -> list[int]:
    """Lineas de un f-string cuyo literal ACABA en el marco y sigue una interpolacion.

    Es la forma exacta del fallo: `f"{intron}__3utr{start}"`. Se mira sobre el `JoinedStr`
    y no sobre el literal suelto porque lo que fabrica la etiqueta es la PAREJA —el
    trozo de texto y lo que se interpola justo detras—; un literal que acabe en `3utr` y
    no lleve nada pegado no etiqueta nada.

    LO QUE NO CUBRE, declarado: una concatenacion (`"3utr" + str(x)`) o un `.join`. La
    forma con dos puntos SI las cubre —ahi basta con que el literal termine en el
    prefijo—; aqui se acota a los f-strings porque es donde estan los casos reales y
    porque ensancharlo empieza a morder texto que no etiqueta nada.
    """
    lineas: list[int] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.JoinedStr):
            continue
        for anterior, siguiente in zip(nodo.values, nodo.values[1:]):
            if not isinstance(anterior, ast.Constant):
                continue
            if not isinstance(anterior.value, str):
                continue
            if not isinstance(siguiente, ast.FormattedValue):
                continue
            for valor in valores:
                if not anterior.value.endswith(valor):
                    continue
                delante = anterior.value[: -len(valor)]
                if delante and delante[-1] not in SEPARADORES:
                    continue
                lineas.append(nodo.lineno)
                break
    return lineas


#: Como se llaman las posiciones del PANEL cuando cruzan una frontera de funcion. Son
#: enteros pelados: el marco se queda al otro lado, y quien las imprime no tiene de donde
#: sacarlo — asi nacio `3utr:1768` por `tx:1768`. Donde llegue uno de estos, el marco se
#: recibe o se saca de la corrida; escribirlo es la forma que tiene este fallo de volver.
NOMBRES_DE_POSICION = ("start", "starts")


def _es_miembro_del_marco(nodo: ast.AST) -> bool:
    """`Frame.UTR3`, `coords.Frame.TX`… — un miembro del enum, escrito.

    No se listan los miembros: se acepta cualquier atributo de algo llamado `Frame`. Un
    tercer espacio de coordenadas entraria aqui solo, que es la diferencia entre un
    guardia y una lista que hay que acordarse de ampliar.
    """
    if not isinstance(nodo, ast.Attribute):
        return False
    duenno = nodo.value
    return (
        getattr(duenno, "id", None) == "Frame"
        or getattr(duenno, "attr", None) == "Frame"
    )


def _es_valor_del_marco(nodo: ast.AST) -> bool:
    """Lo mismo, pero pasado por `.value` — que es como se guarda en el log."""
    if _es_miembro_del_marco(nodo):
        return True
    return (
        isinstance(nodo, ast.Attribute)
        and nodo.attr == "value"
        and _es_miembro_del_marco(nodo.value)
    )


def _defectos(arbol: ast.AST) -> list[tuple[int, str]]:
    """Los sitios donde el marco lo pone la AUSENCIA de una decision, con su forma.

    Tres formas, y las tres estaban en el codigo el 2026-09-07: el campo de una
    dataclass, el parametro de una firma y el segundo argumento de un `.get()` al releer
    el log. Un ARGUMENTO escrito —`label(w.inicio_3utr, Frame.UTR3)`— NO entra: eso
    afirma algo sobre ese valor, no rellena lo que nadie dijo.
    """
    salida: list[tuple[int, str]] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = nodo.args
            posicionales = a.posonlyargs + a.args
            defectos = [None] * (len(posicionales) - len(a.defaults)) + list(a.defaults)
            for defecto in defectos + list(a.kw_defaults):
                if defecto is not None and _es_valor_del_marco(defecto):
                    salida.append((defecto.lineno, "firma"))
        elif isinstance(nodo, ast.AnnAssign):
            if nodo.value is not None and _es_valor_del_marco(nodo.value):
                salida.append((nodo.lineno, "campo"))
        elif isinstance(nodo, ast.Call):
            nombre = nodo.func.attr if isinstance(nodo.func, ast.Attribute) else ""
            if nombre in ("get", "pop") and len(nodo.args) == 2:
                if _es_valor_del_marco(nodo.args[1]):
                    salida.append((nodo.args[1].lineno, "al releer"))
            elif getattr(nodo.func, "id", "") == "getattr" and len(nodo.args) == 3:
                if _es_valor_del_marco(nodo.args[2]):
                    salida.append((nodo.args[2].lineno, "al releer"))
    return salida


def _escritos_sobre_un_start(arbol: ast.AST) -> list[tuple[int, str]]:
    """Miembros del marco ESCRITOS dentro de una funcion que recibe `start`/`starts`."""
    salida: list[tuple[int, str]] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        a = nodo.args
        nombres = {
            arg.arg for arg in a.posonlyargs + a.args + a.kwonlyargs
        }
        if not nombres & set(NOMBRES_DE_POSICION):
            continue
        for dentro in ast.walk(nodo):
            if _es_miembro_del_marco(dentro):
                salida.append((dentro.lineno, nodo.name))
    return salida


def analizar_fuentes(fuentes: dict[str, str], declaradas: list[dict]) -> Informe:
    prefijos = _prefijos()
    valores = tuple(p.rstrip(":") for p in prefijos)
    informe = Informe(ficheros=len(fuentes))
    vistas: set[tuple[str, str]] = set()
    for nombre, texto in sorted(fuentes.items()):
        arbol = ast.parse(texto, filename=nombre)
        docs = _docstrings(arbol)
        for linea, donde in _defectos(arbol):
            informe.por_defecto.append({
                "fichero": nombre,
                "linea": linea,
                "simbolo": _simbolo(arbol, linea),
                "donde": donde,
            })
        for linea, funcion in _escritos_sobre_un_start(arbol):
            informe.escrito_sobre_un_start.append({
                "fichero": nombre, "linea": linea, "simbolo": funcion,
            })
        for linea in _fabrica_sin_dos_puntos(arbol, valores):
            informe.fabrican.append({
                "fichero": nombre,
                "linea": linea,
                "simbolo": _simbolo(arbol, linea),
                "prefijo": "sin dos puntos, pegado a una interpolación",
            })
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
    lineas = [
        "",
        f"  El prefijo del marco, fuera de `coords` ({informe.ficheros} fichero(s) "
        f"leído(s)):",
    ]
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
    if informe.por_defecto:
        lineas.append(
            f"    {len(informe.por_defecto):3}  ⚠  el MARCO viene POR DEFECTO:"
        )
        for fila in informe.por_defecto:
            lineas.append(
                f"         · {fila['fichero']}:{fila['linea']}  {fila['simbolo']}  "
                f"[{fila['donde']}]"
            )
    else:
        lineas.append("      0  el MARCO viene por defecto")
    if informe.escrito_sobre_un_start:
        lineas.append(
            f"    {len(informe.escrito_sobre_un_start):3}  ⚠  marco ESCRITO donde llega "
            f"una posición del panel:"
        )
        for fila in informe.escrito_sobre_un_start:
            lineas.append(
                f"         · {fila['fichero']}:{fila['linea']}  {fila['simbolo']}"
            )
    else:
        lineas.append("      0  marco escrito donde llega una posición del panel")
    lineas.append("")
    lineas.append(
        "  El prefijo lo pone `coords.label`/`span`, que además comprueba el rango. Un"
    )
    lineas.append(
        "  literal tecleado se salta el invariante y ya lo hizo cinco veces (errata 121)."
    )
    lineas.append(
        "  Y el MARCO no tiene valor por defecto: olvidarse de pasarlo es un TypeError,"
    )
    lineas.append(
        "  no una posición de otro sitio bien formada y callada (errata nº 138)."
    )
    return "\n".join(lineas)


def fallos(informe: Informe) -> int:
    """Los hallazgos que tienen que estar a CERO. En un solo sitio, no en dos.

    Estaba contado aqui y otra vez en `check_rules`, y al añadir una categoria nueva se
    actualiza uno y no el otro: un guardia que solo falla por la mitad de lo que mira.
    """
    return (
        len(informe.fabrican)
        + len(informe.sin_declarar)
        + len(informe.muertas)
        + len(informe.por_defecto)
        + len(informe.escrito_sobre_un_start)
    )


def main(argv: list[str]) -> int:
    informe = auditar()
    print(render(informe))
    return 1 if fallos(informe) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
