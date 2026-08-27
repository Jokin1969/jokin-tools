#!/usr/bin/env python3
"""Alcanzabilidad: qué función pública NO tiene ningún llamador.

POR QUÉ EXISTE
--------------

Es la tercera vez que aparece código con tests en verde y sin ningún llamador:

  1. `masking.triple_motive_rows` — el detalle por ventana del triple motivo, calculado
     y sin emitir en ninguna salida;
  2. `intron_folding` — la accesibilidad estructural del intrón, medida y sin pintar;
  3. `store.save_*` — la capa de persistencia entera, construida y testada, y ninguna de
     sus funciones llamada desde ningún sitio. Los cuatro modales calculaban, pintaban, y
     al cerrar la pestaña no quedaba nada.

Tres veces no es casualidad: es un modo de fallo del proyecto. Y **ni los tests ni el
golden lo cazan**, porque son ciegos a él por construcción — los tests comprueban que la
función hace lo que dice, y el golden lee lo que se emite; lo que nunca llega a emitirse
no aparece en ninguno de los dos.

Los dos análisis son complementarios y así están escritos en `docs/principios.md`:
**el golden lee lo que se emite; la alcanzabilidad detecta lo que nunca llega a
emitirse.**

QUÉ MIRA
--------

Toda función y clase **pública** definida bajo `shmir_design/` que no aparezca
referenciada desde **otro módulo** que no sea un test. Un test NO cuenta como llamador:
es todo el punto — `store.save_*` tenía tests.

Lo que este análisis NO puede hacer, y va escrito porque un análisis que no declara sus
límites se lee como si no los tuviera:

  - **no sigue `getattr` ni despachos por cadena.** Un símbolo alcanzado sólo por nombre
    dinámico saldrá aquí como inalcanzable y hay que justificarlo por escrito;
  - **no distingue una referencia de una llamada.** Aparecer en un `import` ya cuenta,
    y eso es deliberado: importar algo que no se usa es otro problema y lo caza el
    linter, no éste;
  - **no dice que el código sobre.** Dice que nadie lo llama, que es un hecho, no un
    veredicto. Lo que sigue es una decisión de una persona.

Uso:

    python3 tools/check_alcance.py            # informe
    python3 tools/check_alcance.py --estricto # y falla si hay hallazgos nuevos

Python 3.11+, solo librería estándar (regla 6).
"""

from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

#: Dónde se declaran las excepciones. Texto y versionado, como el manifiesto: se lee con
#: `cat`, se diffea, y añadir una excepción se ve en la revisión.
EXCEPCIONES = Path("data") / "alcanzabilidad.toml"

#: Por qué esto informa en vez de fallar.
WHY_NOT_A_FAILURE = (
    "Esto NO ES UN FALLO automático: hay casos legítimos —una API que se usa desde la "
    "consola, un símbolo que se alcanza por nombre dinámico, una constante que existe "
    "para documentar—. Lo que hace es OBLIGAR A DECIDIR: o se cablea, o se justifica "
    "por escrito en data/alcanzabilidad.toml, o se borra. Lo que no vale es dejarlo sin "
    "mirar, que es como llegamos tres veces al mismo sitio."
)

#: Lo que sí falla, y por qué. Una lista de excepciones se pudre: en cuanto tiene
#: entradas muertas, quien la lee deja de leerla y el siguiente hallazgo se pierde
#: dentro. Misma razón por la que un frente CERRADO sigue saliendo en el informe.
WHY_STALE_FAILS = (
    "Una excepción declarada para un símbolo que YA tiene llamador, o que ya no existe, "
    "deja de justificar nada y pasa a ser ruido que tapa el siguiente hallazgo. Eso sí "
    "se aborta."
)


@dataclass(frozen=True)
class Symbol:
    """Un símbolo público, con dónde está definido."""

    name: str
    module: str
    line: int
    kind: str

    def describe(self, width: int = 34) -> str:
        return f"{self.name:<{width}} {self.kind:<8} {self.module}:{self.line}"


@dataclass(frozen=True)
class Report:
    unreachable: tuple[Symbol, ...]
    stale: tuple[str, ...]
    scanned: int
    exempted: int

    def render(self) -> str:
        lineas = [
            "── Alcanzabilidad: funciones públicas sin ningún llamador ──",
            "",
            f"  módulos analizados      {self.scanned}",
            f"  sin llamador            {len(self.unreachable)}",
            f"  justificados por escrito {self.exempted}",
            "",
        ]
        if self.unreachable:
            ancho = max([len("símbolo")] + [len(s.name) for s in self.unreachable])
            lineas.append(f"  {'símbolo':<{ancho}} {'tipo':<8} dónde")
            lineas.extend(f"  {s.describe(ancho)}" for s in self.unreachable)
            lineas.append("")
            lineas.append(
                "  Para cada uno: o se CABLEA desde donde se use, o se JUSTIFICA por "
                "escrito"
            )
            lineas.append(
                f"  en {EXCEPCIONES} con el motivo, o se BORRA. {WHY_NOT_A_FAILURE}"
            )
        else:
            lineas.append("  Ninguno. Todo lo público tiene llamador o justificación.")
        if self.stale:
            lineas.extend(
                [
                    "",
                    "  ── EXCEPCIONES QUE YA NO HACEN FALTA (esto sí aborta) ──",
                    *[f"    · {n}" for n in self.stale],
                    f"    {WHY_STALE_FAILS}",
                ]
            )
        return "\n".join(lineas)


def cargar_excepciones(raiz: Path | str = RAIZ, *, ruta: Path | None = None) -> dict[str, str]:
    """Las excepciones declaradas, con su motivo. Sin fichero, ninguna."""
    ruta = Path(raiz) / EXCEPCIONES if ruta is None else Path(ruta)
    if not ruta.is_file():
        return {}
    datos = tomllib.loads(ruta.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in datos.get("justificados", {}).items()}


def _modulos(directorios) -> list[Path]:
    salida: list[Path] = []
    for directorio in directorios:
        camino = Path(directorio)
        if not camino.is_dir():
            continue
        for fichero in sorted(camino.rglob("*.py")):
            if "__pycache__" in str(fichero) or fichero.name == "__init__.py":
                continue
            salida.append(fichero)
    return salida


def _definiciones(fichero: Path) -> list[Symbol]:
    """Las FUNCIONES públicas de nivel superior de un módulo.

    Dos exclusiones, y las dos por la misma razón: un informe con falsos positivos deja
    de leerse, y entonces no sirve para nada — que es el fallo que esto viene a evitar.

      - **los métodos no entran**: se alcanzan por su instancia y este análisis no
        resuelve tipos;
      - **las clases tampoco**. Casi todas son `dataclass` que una función devuelve, así
        que se construyen DENTRO de su módulo y quien las usa nunca escribe su nombre.
        Medido sobre este proyecto: 121 clases sin referencia externa frente a 94
        funciones, y prácticamente todas las clases son ese caso. Con ellas dentro el
        informe tiene 215 filas y no se lee ninguna.

    Y no se pierde nada del modo de fallo que motiva esto: los tres casos reales
    —`triple_motive_rows`, `intron_folding`, `store.save_*`— son funciones. Lo que se
    busca es trabajo calculado que no llega a ninguna salida, y eso lo hace una función.
    """
    arbol = ast.parse(fichero.read_text(encoding="utf-8"), filename=str(fichero))
    salida: list[Symbol] = []
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if nodo.name.startswith("_"):
                continue
            salida.append(
                Symbol(
                    name=nodo.name,
                    module=fichero.stem,
                    line=nodo.lineno,
                    kind="función",
                )
            )
    return salida


def _referencias_por_funcion(fichero: Path) -> dict[str, set[str]]:
    """Qué nombra CADA función de nivel superior de un módulo.

    Hace falta para el cierre TRANSITIVO: `filter_gc` no la llama nadie de fuera de
    `hard_filters`, pero la llama `evaluate_window`, que sí se llama desde `tiling`. No
    está muerta — es una pieza de algo vivo.
    """
    arbol = ast.parse(fichero.read_text(encoding="utf-8"), filename=str(fichero))
    salida: dict[str, set[str]] = {}
    for nodo in arbol.body:
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        nombres: set[str] = set()
        for hijo in ast.walk(nodo):
            if isinstance(hijo, ast.Name):
                nombres.add(hijo.id)
            elif isinstance(hijo, ast.Attribute):
                nombres.add(hijo.attr)
            elif isinstance(hijo, (ast.Import, ast.ImportFrom)):
                for alias in hijo.names:
                    nombres.add(alias.name.split(".")[-1])
        salida[nodo.name] = nombres
    return salida


def _referencias(fichero: Path) -> set[str]:
    """Todo nombre referenciado en un módulo: `Name`, atributos e imports."""
    arbol = ast.parse(fichero.read_text(encoding="utf-8"), filename=str(fichero))
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name):
            nombres.add(nodo.id)
        elif isinstance(nodo, ast.Attribute):
            nombres.add(nodo.attr)
        elif isinstance(nodo, (ast.Import, ast.ImportFrom)):
            for alias in nodo.names:
                nombres.add(alias.name.split(".")[-1])
                if alias.asname:
                    nombres.add(alias.asname)
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            # Un `__all__` o un despacho por cadena. No es una llamada, pero nombrar el
            # símbolo cuenta: preferimos NO denunciar a denunciar de más.
            nombres.add(nodo.value)
    return nombres


def analizar(raiz: Path | str = RAIZ, *, fuentes=None, excepciones=None) -> Report:
    """El informe. `fuentes` acota qué se analiza (los tests lo usan con un fixture).

    `excepciones` apunta a OTRO fichero de justificaciones. Existe porque las del
    fixture no valen para el proyecto y al revés: mezcladas, las del fixture salían como
    caducadas en la corrida de verdad — y una lista con entradas muertas es justo lo que
    esta comprobación aborta.
    """
    raiz = Path(raiz)
    directorios = (
        [raiz / "shmir_design"] if fuentes is None else [Path(f) for f in fuentes]
    )
    # Los llamadores válidos: el propio paquete, los CLI y la interfaz. NUNCA los tests.
    llamadores = _modulos(directorios + [raiz / "tools", raiz / "ui"])
    modulos = _modulos(directorios)

    definidos: list[Symbol] = []
    for fichero in modulos:
        definidos.extend(_definiciones(fichero))

    por_modulo = {f.stem: _referencias(f) for f in llamadores}
    declaradas = cargar_excepciones(raiz, ruta=excepciones)

    # PASO 1 — la SEMILLA: lo que se nombra desde OTRO módulo. Usarse a sí mismo no
    # saca nada del módulo, y el frente de la persistencia era exactamente eso.
    vivos = {
        s.name
        for s in definidos
        if any(
            s.name in nombres
            for modulo, nombres in por_modulo.items()
            if modulo != s.module
        )
    }

    # PASO 2 — el CIERRE TRANSITIVO. Lo que nombra una función viva, también vive.
    # `filter_gc` no la llama nadie de fuera de `hard_filters`, pero la llama
    # `evaluate_window`, que sí: es una pieza de algo vivo, no código muerto. Sin esta
    # vuelta el informe tenía 94 filas y casi todas eran ese caso — y un informe de 94
    # filas donde 78 son ruido no lo lee nadie, que es el fallo que esto viene a evitar.
    # La clave es (MODULO, nombre), no el nombre pelado. `presentation` tiene
    # envoltorios HOMONIMOS de `store.save_blast_run` y compañía: con el nombre a secas,
    # el envoltorio vivo mantenia «vivo» al original — o sea, la herramienta habria
    # dejado de ver EXACTAMENTE el caso que la motivo. Y `dict.update` con nombres
    # pelados machacaba ademas las funciones homonimas de otro modulo, asi que el cierre
    # propagaba referencias del modulo equivocado.
    dentro: dict[tuple[str, str], set[str]] = {}
    for fichero in modulos:
        for nombre, nombres in _referencias_por_funcion(fichero).items():
            dentro[(fichero.stem, nombre)] = nombres
    #: De un nombre a los modulos que lo definen. Una referencia sin cualificar puede
    #: apuntar a cualquiera de ellos y no se resuelve mas: se mantienen todos vivos, que
    #: es el lado conservador — preferimos NO denunciar a denunciar de mas.
    por_nombre: dict[str, list[str]] = {}
    for modulo, nombre in dentro:
        por_nombre.setdefault(nombre, []).append(modulo)

    vivos_clave = {
        (s.module, s.name) for s in definidos if s.name in vivos
    }
    pendientes = list(vivos_clave)
    while pendientes:
        modulo_actual, nombre_actual = pendientes.pop()
        for referido in dentro.get((modulo_actual, nombre_actual), ()):
            # Una referencia dentro de un modulo se resuelve PRIMERO en ese modulo.
            destinos = (
                [modulo_actual]
                if (modulo_actual, referido) in dentro
                else por_nombre.get(referido, [])
            )
            for destino in destinos:
                if (destino, referido) not in vivos_clave:
                    vivos_clave.add((destino, referido))
                    pendientes.append((destino, referido))

    sin_llamador = [s for s in definidos if (s.module, s.name) not in vivos_clave]

    muertos = {s.name for s in sin_llamador}
    definidos_todos = {s.name for s in definidos}
    caducadas = tuple(
        sorted(
            nombre
            for nombre in declaradas
            if nombre in definidos_todos and nombre not in muertos
        )
        + sorted(nombre for nombre in declaradas if nombre not in definidos_todos)
    )
    visibles = tuple(s for s in sin_llamador if s.name not in declaradas)
    return Report(
        unreachable=visibles,
        stale=caducadas,
        scanned=len(modulos),
        exempted=len(sin_llamador) - len(visibles),
    )


def main(argv: list[str]) -> int:
    informe = analizar(RAIZ)
    print(informe.render())
    if informe.stale:
        print(
            f"\ncheck_alcance: {len(informe.stale)} excepción(es) que ya no hacen falta. "
            f"{WHY_STALE_FAILS}",
            file=sys.stderr,
        )
        return 1
    if "--estricto" in argv and informe.unreachable:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
