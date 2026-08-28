#!/usr/bin/env python3
"""Cada guardia del proyecto: qué protege, CUÁNDO corre, y si algo lo revalida.

Sale de la errata nº 27, y de la parte del contrafactual que más enseña. `EVIDENCE`
llevaba anclada a un fichero retirado, y de los dos guardias que podían haberlo cazado:

  · `lower_is_better()` habría **aprobado** — sólo mira si la fuente está registrada;
  · `file_order_direction()` sí habría saltado… **y sólo al importar un fichero**.

O sea: la contramedida existía y estaba en el sitio equivocado del flujo. Nada la
revalidaba después. **Un guardia que sólo corre en la ingesta no protege de nada que se
degrade más tarde**, y el caso de hoy demuestra que se degradan.

Es el complemento del principio nº 9. Allí: *existir no es contener*. Aquí:
**haber comprobado una vez no es seguir comprobando.**

Las cuatro columnas, y ninguna sobra:

  · **qué protege** — el invariante, no la función.
  · **cuándo se ejecuta** — `INGESTA` (al cargar o al subir), `CADA_CORRIDA` (cada vez
    que se diseña), `AL_EMITIR` (al escribir la salida), `AL_ABRIR` (al recuperar algo
    guardado), `AL_CONSTRUIR` (en el `__post_init__`, o sea siempre que exista el
    objeto).
  · **puede degradarse** — si lo protegido puede cambiar DESPUÉS de la comprobación.
  · **qué lo revalida** — o `NADA`.

**LA CLASE DE RIESGO ES LA INTERSECCIÓN**: `INGESTA` + puede degradarse + nada lo
revalida. Ésos son los siguientes en fallar, y el informe los saca aparte.

**Y HAY UNA SEGUNDA CLASE, que salió de rellenar la tabla**: guardias que corren en cada
corrida pero cuyo SUPUESTO sólo lo revalida la suite (`revalida = "SUITE …"`). Protegen
el repositorio y no protegen una corrida: en producción el directorio de referencia vive
en un volumen que la suite no mira.

No falla nunca: es un informe. Lo que falla es `tests/test_guardias.py`, si una entrada
nombra un símbolo que ya no existe o que no aborta, o si queda fuera de la tabla algo de
la clase que se deriva del código.

    python3 tools/auditar_guardias.py
"""

import ast
import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAQUETE = RAIZ / "shmir_design"
TABLA = RAIZ / "data" / "guardias.toml"

MOMENTOS = ("INGESTA", "CADA_CORRIDA", "AL_EMITIR", "AL_ABRIR", "AL_CONSTRUIR")

#: Como impide un guardia lo que impide. `RECHAZA` no es un guardia de segunda: es el
#: que retiene el resultado en vez de abortar, y vale donde abortar seria peor. Pero se
#: DECLARA, porque «no aborta» a secas es lo que separa un guardia de un aviso.
ACCIONES = ("ABORTA", "RECHAZA")

#: Los errores con los que este proyecto ABORTA. Un guardia que no aborte no es un
#: guardia: es un aviso, y un aviso no protege nada (regla 2).
ERRORES = frozenset({
    "ShmirDesignError", "ChecksumMismatchError", "MissingSequenceError",
    "InvalidSequenceError", "ParseError", "ValueError", "KeyError",
})

#: LA CLASE QUE SE DERIVA DEL CÓDIGO, para que no se pueda omitir nada en silencio:
#: todo lo que COMPARA una identidad declarada contra lo entregado. Es exactamente la
#: familia del caso que motivó esto —un dato que dice ser de un sitio y viene de otro—
#: y es la que se degrada, porque la identidad vive fuera del proceso.
COMPARA_IDENTIDAD = re.compile(
    r"expected_md5|expected_species|hexdigest\(\)|"
    r"md5\s*!=|!=\s*[\w.]*md5|checksum\s*!=|!=\s*[\w.]*checksum",
    re.I,
)


def _aborta(nodo: ast.AST) -> bool:
    for hijo in ast.walk(nodo):
        if not (isinstance(hijo, ast.Raise) and hijo.exc is not None):
            continue
        objetivo = hijo.exc.func if isinstance(hijo.exc, ast.Call) else hijo.exc
        nombre = getattr(objetivo, "id", None) or getattr(objetivo, "attr", None)
        if nombre in ERRORES:
            return True
    return False


def _funciones() -> dict[str, tuple[int, bool, str]]:
    """Toda función del paquete → (línea, ¿aborta?, fuente). Métodos incluidos."""
    encontradas: dict[str, tuple[int, bool, str]] = {}
    for ruta in sorted(PAQUETE.glob("*.py")):
        texto = ruta.read_text(encoding="utf-8")
        lineas = texto.splitlines()
        arbol = ast.parse(texto, filename=str(ruta))

        def registra(nodo, prefijo=""):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return
            fuente = "\n".join(lineas[nodo.lineno - 1 : nodo.end_lineno])
            encontradas[f"{ruta.stem}.{prefijo}{nodo.name}"] = (
                nodo.lineno, _aborta(nodo), fuente
            )

        for nodo in arbol.body:
            if isinstance(nodo, ast.ClassDef):
                for miembro in nodo.body:
                    registra(miembro, prefijo=f"{nodo.name}.")
            else:
                registra(nodo)
    return encontradas


def auditar() -> dict:
    datos = tomllib.loads(TABLA.read_text(encoding="utf-8"))
    guardias = list(datos.get("guardia", ()))
    solo_calculan = dict(datos.get("solo_calculan", {}))
    # Comparan de verdad y NO abortan: son informes. La distincion es el punto de esta
    # auditoria — un guardia que no aborta es un aviso, y un aviso no protege nada.
    solo_informan = dict(datos.get("solo_informan", {}))
    funciones = _funciones()

    implementados: set[str] = set()
    for guardia in guardias:
        implementados.update(guardia["implementa"])

    # Las que COMPARAN una identidad y no las cubre ninguna entrada ni estan declaradas
    # como meros calculadores del resumen.
    comparan = {
        nombre for nombre, (_, _, fuente) in funciones.items()
        if COMPARA_IDENTIDAD.search(fuente)
    }
    sin_cubrir = sorted(
        comparan - implementados - set(solo_calculan) - set(solo_informan)
    )

    # Entradas que nombran algo que ya no existe, o que ha dejado de abortar.
    fantasmas = sorted(s for s in implementados if s not in funciones)
    # MUDOS va por ENTRADA, no por símbolo. Un guardia se implementa con más de una
    # pieza y no todas abortan: `resources._refseq` PASA el md5 esperado y quien aborta
    # es `specificity.load_database`. Exigirlo símbolo a símbolo habría marcado como
    # rotas las piezas de fontanería —falsos positivos— y un guardia con falsos
    # positivos se acaba apagando, que es una lección ya escrita de este proyecto.
    # Lo que sí no puede pasar es que NINGUNA pieza de una entrada aborte.
    mudos = sorted(
        g["guardia"] for g in guardias
        if g.get("como_actua", "ABORTA") == "ABORTA"
        and not any(funciones.get(s, (0, False, ""))[1] for s in g["implementa"])
    )
    calculadores_muertos = sorted(
        s for s in (*solo_calculan, *solo_informan) if s not in funciones
    )
    # Un INFORME que empieza a abortar ha dejado de ser un informe: o pasa a la tabla
    # como guardia, o alguien le ha cambiado el contrato sin decirlo.
    informes_que_abortan = sorted(
        s for s in solo_informan if s in funciones and funciones[s][1]
    )

    riesgo = [
        g for g in guardias
        if g["momento"] == "INGESTA"
        and g.get("puede_degradar", False)
        and g.get("revalida", "NADA").upper() == "NADA"
    ]
    # SEGUNDA CLASE, y salió de rellenar la tabla: un guardia que corre en cada corrida
    # pero cuyo SUPUESTO sólo lo revalida la suite. Protege el repositorio y no protege
    # una corrida — en producción el directorio de referencia vive en un volumen que la
    # suite no mira. La primera clase la señaló el responsable; ésta la enseñó la tabla.
    solo_suite = [
        g for g in guardias
        if g not in riesgo and g.get("revalida", "").upper().startswith("SUITE")
    ]
    return {
        "guardias": guardias,
        "solo_calculan": solo_calculan,
        "solo_informan": solo_informan,
        "informes_que_abortan": informes_que_abortan,
        "sin_cubrir": sin_cubrir,
        "fantasmas": fantasmas,
        "mudos": mudos,
        "calculadores_muertos": calculadores_muertos,
        "riesgo": riesgo,
        "solo_suite": solo_suite,
        "momentos": {
            m: [g for g in guardias if g["momento"] == m] for m in MOMENTOS
        },
    }


def _envolver(texto: str, ancho: int) -> list[str]:
    palabras, linea, salida = texto.split(), "", []
    for palabra in palabras:
        if linea and len(linea) + 1 + len(palabra) > ancho:
            salida.append(linea)
            linea = palabra
        else:
            linea = f"{linea} {palabra}".strip()
    if linea:
        salida.append(linea)
    return salida


def main() -> int:
    informe = auditar()
    print(__doc__)
    print("=" * 78)

    print()
    print(f"── LOS SIGUIENTES EN FALLAR ({len(informe['riesgo'])}) ──")
    print("   INGESTA + lo protegido puede cambiar + NADA lo revalida.")
    if not informe["riesgo"]:
        print("   Ninguno. No es un logro permanente: se vuelve a mirar en cada tanda.")
    for guardia in informe["riesgo"]:
        print()
        print(f"  ⚠  {guardia['guardia']}")
        for linea in _envolver(f"PROTEGE: {guardia['protege']}", 72):
            print(f"      {linea}")
        for linea in _envolver(f"SE DEGRADA: {guardia['degrada_como']}", 72):
            print(f"      {linea}")

    print()
    print(f"── SÓLO LOS REVALIDA LA SUITE ({len(informe['solo_suite'])}) ──")
    print("   Protegen el repositorio. NO protegen una corrida sobre un volumen.")
    for guardia in informe["solo_suite"]:
        print()
        print(f"  ⚠  {guardia['guardia']}")
        for linea in _envolver(f"PROTEGE: {guardia['protege']}", 72):
            print(f"      {linea}")
        for linea in _envolver(f"REVALIDA: {guardia['revalida']}", 72):
            print(f"      {linea}")

    for momento in MOMENTOS:
        filas = informe["momentos"][momento]
        print()
        print(f"── {momento} ({len(filas)}) ──")
        for fila in filas:
            marca = ""
            if fila in informe["riesgo"]:
                marca = " ⚠"
            elif fila in informe["solo_suite"]:
                marca = " ⚠ (sólo la suite)"
            print(f"  {fila['guardia']}{marca}")
            print(f"      protege:  {fila['protege']}")
            revalida = fila.get("revalida", "NADA")
            degrada = "SÍ" if fila.get("puede_degradar", False) else "no"
            accion = fila.get("como_actua", "ABORTA")
            print(f"      actúa:    {accion}")
            print(f"      degrada:  {degrada}    revalida: {revalida}")
            print(f"      código:   {', '.join(fila['implementa'])}")

    for etiqueta, filas in (
        ("SIN CUBRIR — comparan una identidad y no están en la tabla",
         informe["sin_cubrir"]),
        ("FANTASMAS — la tabla los nombra y ya no existen", informe["fantasmas"]),
        ("MUDOS — ninguna de sus piezas aborta ya", informe["mudos"]),
        ("CALCULADORES MUERTOS — declarados y ya no existen",
         informe["calculadores_muertos"]),
        ("INFORMES QUE AHORA ABORTAN — o son guardias, o les han cambiado el contrato",
         informe["informes_que_abortan"]),
    ):
        if filas:
            print()
            print(f"{etiqueta} (hacen fallar el test):")
            for fila in filas:
                print(f"  {fila}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
