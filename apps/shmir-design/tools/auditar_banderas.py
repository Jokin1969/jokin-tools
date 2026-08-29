#!/usr/bin/env python3
"""Inventario de banderas de los CLI: cuáles se recorren de PUNTA A PUNTA en algún test.

**De dónde sale.** De la errata nº 31: `tools/design.py` pasaba `thresholds=umbrales`, una
variable que no existe, así que TODA corrida con `--rmsk` moría con un `NameError` — y con
ella el bloque del triple motivo, que se había cableado precisamente porque «existía sólo
porque alguien lo corría a mano». Se cableó, y el cable no conducía.

**Y ninguna de las dos herramientas del proyecto podía verlo:**

- la **alcanzabilidad** busca símbolos sin llamador, y aquí había una llamada escrita;
- el **golden** lee la salida por defecto, y se genera SIN máscara.

Entre las dos hay un hueco, y ahí vive **el código llamado desde caminos que nadie
recorre**. Es el principio nº 17.

**Qué hace esto.** Deriva las banderas de cada CLI de su propio `add_argument`, deriva de
los tests qué banderas aparecen en una llamada a `main([...])` que NO se espera que aborte,
y cruza las dos listas. Lo que no aparece se lista como NO PROBADO.

**Y se ordena por CONSECUENCIA, que es lo único que hace útil la lista.** Una bandera que
cambia un VEREDICTO sin recorrido de punta a punta es urgente; una que cambia el formato de
la salida, no. Sin esa distinción, 120 filas planas no las lee nadie — que es el fallo que
esta herramienta viene a evitar, no a repetir.

**Lo que NO puede hacer**, y va declarado porque un análisis que se equivoca hacia el
silencio es peor que no tenerlo:

- no ve banderas construidas dinámicamente ni pasadas a `main()` desde una variable: sólo
  literales dentro de la llamada;
- no sabe si el test que la ejercita comprueba algo útil — sabe que el camino se recorrió
  sin abortar, que es exactamente el hueco de la errata nº 31 y ni un paso más;
- no dice que una bandera esté rota. Dice que **nadie la ha recorrido entera**.

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TABLA = RAIZ / "data" / "banderas.toml"

#: Los CLI que se auditan: los que tienen `main(argv)` y se invocan desde la consola.
#: Se derivan del directorio en vez de listarse, para que uno nuevo entre solo — y su
#: primera aparicion sea en el informe, no seis meses despues.
def clis() -> list[Path]:
    return sorted(
        p
        for p in (RAIZ / "tools").glob("*.py")
        if p.name != "__init__.py" and _tiene_main(p)
    )


def _tiene_main(ruta: Path) -> bool:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    return any(
        isinstance(n, ast.FunctionDef) and n.name == "main" for n in arbol.body
    )


#: Las CATEGORIAS de consecuencia, en orden de urgencia. El orden ES la priorizacion:
#: lo primero de la lista es lo que se arregla primero.
CONSECUENCIAS = (
    # Cambia QUE candidato pasa o cae, o el veredicto que lleva. Sin recorrido de punta
    # a punta, un fallo aqui manda a sintesis lo que no es.
    "VEREDICTO",
    # Mete o quita un DATO que mueve las cifras, sin cambiar por si mismo un veredicto.
    "DATO",
    # Cambia lo que se emite o como, no lo que se decide.
    "FORMATO",
    # Rutas, nombres y fontaneria. Un fallo aqui se ve en el acto.
    "FONTANERIA",
)


@dataclass(frozen=True)
class Bandera:
    cli: str
    nombre: str

    @property
    def clave(self) -> str:
        return f"{self.cli}:{self.nombre}"


def banderas_declaradas() -> list[Bandera]:
    """Las banderas de cada CLI, DERIVADAS de sus propias llamadas a `add_argument`.

    No se transcriben (principio nº 13): una bandera nueva aparece aqui sola, y una que
    se borre desaparece. Sólo se miran literales `"--x"`; una construida dinamicamente no
    se veria, y eso esta declarado arriba.
    """
    salida: list[Bandera] = []
    for ruta in clis():
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            if not (
                isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "add_argument"
            ):
                continue
            for arg in nodo.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if arg.value.startswith("--"):
                        salida.append(Bandera(cli=ruta.stem, nombre=arg.value))
    return sorted(set(salida), key=lambda b: (b.cli, b.nombre))


def banderas_ejercitadas() -> dict[str, set[str]]:
    """Que banderas recorre algun test SIN que se espere que la corrida aborte.

    LA DISTINCION NO ES COSMETICA. Un test que comprueba `main([...]) == 2` verifica que
    una entrada mala se rechaza: es util y NO recorre el camino. La errata nº 31 vivia
    justo ahi — la rama existia, tenia llamador, y ningun test la atravesaba entera.

    QUE CLI ES CADA `main` SE RESUELVE POR FICHERO, de sus propios `import`. La primera
    version llevaba una tabla de alias global y se equivoco EN LAS DOS DIRECCIONES: daba
    por probadas de `design` las banderas de `import_scores` —que tambien importa su main
    como `main`— y no veia las de `test_usar_manifiesto.py`, que llama por un ayudante.
    Un analisis que se equivoca hacia el silencio es peor que no tenerlo, asi que esto se
    contrasto contra un `grep` antes de darlo por bueno.
    """
    por_cli: dict[str, set[str]] = {}
    for ruta in sorted((RAIZ / "tests").glob("*.py")):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        nombres = _mains_importados(arbol)
        if not nombres:
            continue
        nombres.update(_ayudantes(arbol, nombres))
        abortadas = _llamadas_que_esperan_aborto(arbol)
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call) or nodo in abortadas:
                continue
            cli = _cli_de(nodo, nombres)
            if cli is None:
                continue
            por_cli.setdefault(cli, set()).update(_literales(nodo))
    return por_cli


def _mains_importados(arbol: ast.AST) -> dict[str, str]:
    """`from tools.design import main as design_main` → {design_main: design}.

    DERIVADO del import y no de una tabla: dos CLI no pueden llamarse los dos `main` en
    el mismo fichero, pero SI en ficheros distintos — y eso es lo que rompia la tabla
    global.
    """
    encontrados: dict[str, str] = {}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.ImportFrom) or not nodo.module:
            continue
        if not nodo.module.startswith("tools."):
            continue
        cli = nodo.module.split(".", 1)[1]
        for alias in nodo.names:
            if alias.name == "main":
                encontrados[alias.asname or alias.name] = cli
    return encontrados


def _ayudantes(arbol: ast.AST, mains: dict[str, str]) -> dict[str, str]:
    """Funciones del propio test que envuelven a un `main` y reciben la lista de flags.

    `test_usar_manifiesto.py` llama a `self._correr([...])`, asi que sus banderas no
    estan en ninguna llamada a `main` y salian como NO PROBADAS siendo falso. Se sigue
    UN nivel de indireccion, que es el que hay aqui; mas niveles no se persiguen y queda
    declarado, como todo lo que este analisis no puede hacer.
    """
    envoltorios: dict[str, str] = {}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for hijo in ast.walk(nodo):
            if isinstance(hijo, ast.Call) and _cli_de(hijo, mains) is not None:
                envoltorios[nodo.name] = _cli_de(hijo, mains)
                break
    return envoltorios


def _llamadas_que_esperan_aborto(arbol: ast.AST) -> set[ast.Call]:
    """`assertEqual(main([...]), 2)` — la corrida se rechaza, no se recorre."""
    fuera: set[ast.Call] = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call) or len(nodo.args) != 2:
            continue
        func = nodo.func
        if not (isinstance(func, ast.Attribute) and func.attr == "assertEqual"):
            continue
        primero, segundo = nodo.args
        if (
            isinstance(primero, ast.Call)
            and isinstance(segundo, ast.Constant)
            and segundo.value != 0
        ):
            fuera.add(primero)
    return fuera


def _cli_de(nodo: ast.Call, mains: dict[str, str]) -> str | None:
    if isinstance(nodo.func, ast.Name):
        return mains.get(nodo.func.id)
    if isinstance(nodo.func, ast.Attribute):
        return mains.get(nodo.func.attr)
    return None


def _literales(nodo: ast.Call) -> set[str]:
    """Las banderas que van escritas DENTRO de la llamada. Una que llegue por variable
    no se ve, y eso esta declarado: el analisis no se equivoca hacia el silencio sin
    decirlo."""
    encontradas: set[str] = set()
    for arg in nodo.args:
        for hijo in ast.walk(arg):
            if isinstance(hijo, ast.Constant) and isinstance(hijo.value, str):
                if hijo.value.startswith("--"):
                    encontradas.add(hijo.value)
    return encontradas


@dataclass
class Informe:
    filas: list[dict] = field(default_factory=list)
    combinaciones: list[dict] = field(default_factory=list)
    sin_clasificar: list[str] = field(default_factory=list)
    muertas: list[str] = field(default_factory=list)
    techo: int = 0

    @property
    def no_probadas(self) -> list[dict]:
        return [f for f in self.filas if not f["probada"] and not f["exento"]]

    @property
    def exentas(self) -> list[dict]:
        return [f for f in self.filas if f["exento"]]

    def por_consecuencia(self, nombre: str) -> list[dict]:
        return [f for f in self.no_probadas if f["consecuencia"] == nombre]


def auditar() -> Informe:
    tabla = tomllib.loads(TABLA.read_text(encoding="utf-8"))
    declarada = {e["bandera"]: e for e in tabla.get("bandera", [])}
    ejercitadas = banderas_ejercitadas()
    informe = Informe()

    vivas = set()
    for bandera in banderas_declaradas():
        vivas.add(bandera.clave)
        entrada = declarada.get(bandera.clave)
        if entrada is None:
            informe.sin_clasificar.append(bandera.clave)
            continue
        probada = bandera.nombre in ejercitadas.get(bandera.cli, set())
        informe.filas.append(
            {
                "clave": bandera.clave,
                "cli": bandera.cli,
                "bandera": bandera.nombre,
                "consecuencia": entrada["consecuencia"],
                "que_hace": entrada.get("que_hace", ""),
                # EXENTA: se declara por que NO se va a recorrer, con motivo. No es lo
                # mismo que no haberla mirado, asi que no cuenta para el trinquete pero
                # SIGUE SALIENDO — una exencion que desaparece de la lista deja de poder
                # caducar, y entonces el siguiente hallazgo se pierde dentro.
                "exento": entrada.get("exento", ""),
                "probada": probada,
            }
        )
    informe.muertas = sorted(set(declarada) - vivas)
    informe.techo = tabla.get("umbral", {}).get("veredicto_sin_recorrer", 0)

    # Las COMBINACIONES que sólo significan algo juntas: `--rmsk` sin su resumen ni su
    # especie aborta a proposito, asi que las tres por separado no dicen nada. Se
    # declaran porque argparse no las expresa, y el test comprueba que cada bandera
    # nombrada existe de verdad.
    for combinacion in tabla.get("combinacion", []):
        cli = combinacion["cli"]
        partes = combinacion["banderas"]
        vistas = ejercitadas.get(cli, set())
        informe.combinaciones.append(
            {
                **combinacion,
                "probada": all(p in vistas for p in partes),
            }
        )
    return informe


def render(informe: Informe) -> str:
    lineas = ["", "  Banderas de los CLI, por si algún test las recorre ENTERAS:"]
    total = len(informe.filas)
    probadas = sum(1 for f in informe.filas if f["probada"])
    lineas.append(f"    {probadas} de {total} banderas con recorrido de punta a punta")
    for consecuencia in CONSECUENCIAS:
        faltan = informe.por_consecuencia(consecuencia)
        if not faltan:
            continue
        marca = "⚠  " if consecuencia == "VEREDICTO" else "   "
        lineas.append(f"  {marca}{len(faltan):3}  {consecuencia} — sin recorrer")
        if consecuencia != "VEREDICTO":
            continue
        # Sólo las urgentes se detallan, y AGRUPADAS POR CLI. Las otras tres categorías
        # se cuentan y no se listan: una lista de 139 filas planas no la lee nadie, que
        # es el fallo que esta herramienta viene a evitar y no a repetir.
        por_cli: dict[str, list[dict]] = {}
        for fila in faltan:
            por_cli.setdefault(fila["cli"], []).append(fila)
        for cli in sorted(por_cli):
            lineas.append(f"       {cli}:")
            for fila in por_cli[cli]:
                lineas.append(f"         · {fila['bandera']} — {fila['que_hace']}")
    if informe.exentas:
        lineas.append(f"     {len(informe.exentas):3}  EXENTAS, con motivo escrito:")
        for fila in informe.exentas:
            lineas.append(f"         · {fila['clave']}")
    sin_combinar = [
        c for c in informe.combinaciones if not c["probada"] and not c.get("exento")
    ]
    if sin_combinar:
        lineas.append(f"  ⚠  {len(sin_combinar):3}  COMBINACIONES sin recorrer")
        for combinacion in sin_combinar:
            lineas.append(
                f"         · {combinacion['cli']}: "
                f"{' '.join(combinacion['banderas'])}"
            )
            lineas.append(f"           {combinacion['por_que']}")
    if informe.sin_clasificar:
        lineas.append("")
        lineas.append("  SIN CLASIFICAR: " + ", ".join(informe.sin_clasificar))
    lineas.append("")
    lineas.append(
        f"  Lo cubre una corrida de `main()` con esa bandera que termine en 0 y de la "
        f"que se LEA la"
    )
    lineas.append(
        "  salida. Que exista un test que la nombre no basta: la errata nº 31 tenía "
        "llamador."
    )
    lineas.append(
        f"  El techo declarado son {informe.techo} y hay {len(informe.por_consecuencia('VEREDICTO'))}. "
        f"Sólo puede bajar."
    )
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    informe = auditar()
    print(render(informe))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
