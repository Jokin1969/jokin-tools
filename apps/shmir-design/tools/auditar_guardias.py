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

**Y HAY UN CRUCE QUE SÍ ES UN FALLO**: un guardia que el análisis de alcanzabilidad da
por SIN LLAMADOR. La alcanzabilidad dice «nadie la llama», que se lee como *pendiente*;
esta tabla pregunta *cuándo protege*, y para lo mismo la respuesta es *nunca*. Misma
información, dos preguntas, y sólo una obliga a actuar — así que se cruzan y el cruce no
admite excepción: si protege algo, alguien tiene que invocarlo.

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


def _nadie_lo_invoca(simbolos) -> list[str]:
    """De los simbolos dados, cuales NO se INVOCAN desde ningun sitio del paquete.

    **El criterio es mas grueso que el de la alcanzabilidad, y a proposito.** Aquella
    contesta «¿se llega a esto desde un punto de entrada?»; aqui la pregunta es otra y
    mas basica: «¿lo llama ALGO?». Tiene que serlo, porque este cruce **es un fallo** y
    un guardia con falsos positivos se acaba apagando — leccion ya escrita.

    Con el criterio fino salian cuatro y **tres eran falsos positivos**: `read_evidence_pairs`
    lo llama una PROPIEDAD de su propio modulo —que es justo lo que la alcanzabilidad
    declara no poder ver—, y `declare_utr3_length` y `load_guide_fixture` son APIs para
    otra especie y para los tests. Denunciar esos tres habria hecho que la siguiente
    denuncia no se leyera.

    Se miran REFERENCIAS DE CODIGO, y eso son dos cosas y no una:

      - **no vale una mencion en prosa.** Un guardia cuya unica aparicion es un docstring
        que habla de el NO lo llama nadie, por bien explicado que este — y ese es
        exactamente el caso que esto viene a cazar.
      - **pero SI vale nombrarlo sin llamarlo.** `resources._refseq` no se invoca por su
        nombre: se mete en el diccionario `LOADERS` y se despacha por rol. Exigir una
        llamada literal habria denunciado los nueve cargadores, que corren en cada
        corrida. Un guardia con falsos positivos se acaba apagando.

    Y los DUNDER quedan fuera: a `__post_init__` lo llama la maquinaria del dataclass,
    asi que corre siempre que el objeto exista y nadie escribe su nombre.
    """
    referidos: set[str] = set()
    for carpeta in ("shmir_design", "tools", "ui"):
        for ruta in sorted((RAIZ / carpeta).glob("*.py")):
            arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Load):
                    referidos.add(nodo.id)
                elif isinstance(nodo, ast.Attribute) and isinstance(nodo.ctx, ast.Load):
                    referidos.add(nodo.attr)
    return [
        s for s in simbolos
        if not s.split(".")[-1].startswith("__")
        and s.split(".")[-1] not in referidos
    ]


def auditar() -> dict:
    datos = tomllib.loads(TABLA.read_text(encoding="utf-8"))
    guardias = list(datos.get("guardia", ()))
    solo_calculan = dict(datos.get("solo_calculan", {}))
    # Comparan de verdad y NO abortan: son informes. La distincion es el punto de esta
    # auditoria — un guardia que no aborta es un aviso, y un aviso no protege nada.
    solo_informan = dict(datos.get("solo_informan", {}))
    # Existen y NO PUEDEN correr por ningun camino de hoy. No es lo mismo que un guardia
    # sin cablear —eso es un fallo— ni que codigo muerto: es una deuda declarada.
    sin_camino = dict(datos.get("sin_camino", {}))
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
        s for s in (*solo_calculan, *solo_informan, *sin_camino) if s not in funciones
    )
    # Un INFORME que empieza a abortar ha dejado de ser un informe: o pasa a la tabla
    # como guardia, o alguien le ha cambiado el contrato sin decirlo.
    informes_que_abortan = sorted(
        s for s in solo_informan if s in funciones and funciones[s][1]
    )

    # EL CRUCE, Y ES UN FALLO — NO UN INFORME. AÑADIDO 2026-08-27.
    #
    # La alcanzabilidad dice «nadie la llama», y eso se lee como PENDIENTE: una fila mas
    # de una lista que obliga a decidir algun dia. La tabla de guardias pregunta CUANDO
    # protege, y para lo mismo la respuesta es «nunca». Misma informacion, dos preguntas,
    # y solo una obliga a actuar.
    #
    # Asi que se cruzan: **un simbolo que este en las dos listas sube de informe a
    # fallo**, y aqui NO hay excepcion posible. Un guardia legitimamente sin llamador no
    # existe — si protege algo, alguien tiene que invocarlo; si no lo invoca nadie, no
    # protege nada, y da igual lo bien escrito que este.
    huerfanos = set(_nadie_lo_invoca(sorted(implementados)))
    # Un simbolo declarado SIN CAMINO tiene que seguir sin tenerlo: el dia que alguien
    # lo cablee, esta entrada sobra y hay que quitarla — igual que una excepcion de
    # alcanzabilidad caducada.
    con_camino_ya = sorted(set(sin_camino) - set(_nadie_lo_invoca(sorted(sin_camino))))
    guardias_sin_llamador = sorted(
        f"{g['guardia']} → {s}"
        for g in guardias
        for s in g["implementa"]
        if s in huerfanos
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
    # Un SUITE sin decir que lo revalidaria de verdad es una queja, no una tarea.
    suite_sin_salida = sorted(
        g["guardia"] for g in guardias
        if g.get("revalida", "").upper().startswith("SUITE")
        and not g.get("revalida_en_produccion", "").strip()
    )
    return {
        "guardias": guardias,
        "solo_calculan": solo_calculan,
        "solo_informan": solo_informan,
        "informes_que_abortan": informes_que_abortan,
        "sin_cubrir": sin_cubrir,
        "fantasmas": fantasmas,
        "mudos": mudos,
        "calculadores_muertos": calculadores_muertos,
        "guardias_sin_llamador": guardias_sin_llamador,
        "sin_camino": sin_camino,
        "con_camino_ya": con_camino_ya,
        "riesgo": riesgo,
        "solo_suite": solo_suite,
        "suite_sin_salida": suite_sin_salida,
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

    if informe["guardias_sin_llamador"]:
        print()
        print("── GUARDIAS QUE NO LOS LLAMA NADIE — ESTO ES UN FALLO, NO UN INFORME ──")
        for fila in informe["guardias_sin_llamador"]:
            print(f"  ✗  {fila}")
        print("   No hay excepción posible: si protege algo, alguien tiene que")
        print("   invocarlo; si no lo invoca nadie, no protege nada.")

    if informe["sin_camino"]:
        print()
        print(f"── EXISTEN Y NO PUEDEN CORRER ({len(informe['sin_camino'])}) ──")
        print("   No es un fallo ni código muerto: es una deuda declarada.")
        for simbolo, motivo in sorted(informe["sin_camino"].items()):
            print(f"  ·  {simbolo}")
            for linea in _envolver(motivo, 72):
                print(f"      {linea}")

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
        for linea in _envolver(
            f"EN PRODUCCIÓN LO CERRARÍA: {guardia.get('revalida_en_produccion', '')}", 72
        ):
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
        ("DECLARADOS SIN CAMINO Y YA LO TIENEN — sobra la entrada",
         informe["con_camino_ya"]),
        ("SUITE SIN DECIR QUÉ LO CERRARÍA EN PRODUCCIÓN",
         informe["suite_sin_salida"]),
    ):
        if filas:
            print()
            print(f"{etiqueta} (hacen fallar el test):")
            for fila in filas:
                print(f"  {fila}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
