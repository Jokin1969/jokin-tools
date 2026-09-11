"""Ninguna funcion de la pagina lee un nombre que ahi dentro no existe.

**El caso, y llevaba dos dias vivo en produccion (errata nº 158).** El 2026-09-09, al
entrar el eje de transcriptoma, la linea de la huella del modal de off-targets se copio
tambien al de colision de seed:

    huella = run_fingerprint(tuple(starts), params, fondo)

`fondo` es la variable del OTRO modal —el catalogo elegido en su selector— y en
`_modal_seed` no existe. O sea que **abrir la casilla de colision de seed lanzaba un
`NameError`**, y como esa excepcion sube al `try` de `main()`, que pinta el motivo y hace
`return`, se llevaba por delante **todo lo que va por debajo**: los otros modales,
Descargas y el paso 5. El sintoma no es «el modal de seed falla»: es «la pagina se corta
por la mitad».

**Por que no lo vio nada de lo que hay.** No es un fallo de cobertura: `AppTest` no puede
rellenar un `file_uploader`, asi que la suite no llega al estado DISEÑADO y los once
estados que cuelgan de el estan declarados como BLOQUEADOS en `data/estados.toml` —los
ocho de los cuatro modales entre ellos—. El golden de la pagina se genera con el proyecto
vacio y tampoco los pinta. La alcanzabilidad mira simbolos sin llamador, y aqui habia
llamador; el golden lee lo que se emite, y esto no llegaba a emitirse nunca.

**Asi que el mecanismo no puede depender de ejecutar la pagina**: mira el FUENTE. Es la
comprobacion mas barata que cubre esta clase entera —un nombre leido y nunca escrito— y
no necesita Streamlit, ni fichero subido, ni proyecto.

**Guardia, no trinquete: el numero correcto es CERO.** Un nombre que no existe no es
deuda pendiente — es una rama que revienta la primera vez que alguien la recorre.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import ast
import builtins
import unittest
from pathlib import Path

PAGINA = Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"


def _globales(arbol: ast.Module) -> set[str]:
    """Lo que existe A NIVEL DE MODULO: importaciones, constantes y funciones."""
    nombres: set[str] = set()
    for nodo in arbol.body:
        if isinstance(nodo, (ast.Import, ast.ImportFrom)):
            for alias in nodo.names:
                nombres.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nombres.add(nodo.name)
        elif isinstance(nodo, ast.Assign):
            for destino in nodo.targets:
                nombres.update(
                    n.id for n in ast.walk(destino)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                )
        elif isinstance(nodo, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(nodo.target, ast.Name):
                nombres.add(nodo.target.id)
        elif isinstance(nodo, (ast.If, ast.Try, ast.With)):
            # Un `try: import X / except ImportError: X = None` define `X` igual.
            for hijo in ast.walk(nodo):
                if isinstance(hijo, (ast.Import, ast.ImportFrom)):
                    for alias in hijo.names:
                        nombres.add(alias.asname or alias.name.split(".")[0])
                elif isinstance(hijo, ast.Name) and isinstance(hijo.ctx, ast.Store):
                    nombres.add(hijo.id)
    return nombres


def _definidos_dentro(funcion) -> set[str]:
    """Todo lo que esa funcion ATA a un nombre: argumentos, asignaciones, `with`, `for`…

    Se es deliberadamente GENEROSO —cualquier `Store`, venga de donde venga, y sin mirar
    el orden ni las ramas—: lo que se busca es un nombre que **no se escribe en ninguna
    parte**, que es la forma del fallo. Un guardia mas fino diria cosas ciertas sobre
    codigo correcto —una variable asignada dentro de un `if`— y un guardia con falsos
    positivos se acaba apagando (principio nº 34).
    """
    nombres: set[str] = set()
    for argumentos in (funcion.args,):
        for arg in (
            *argumentos.posonlyargs, *argumentos.args, *argumentos.kwonlyargs,
        ):
            nombres.add(arg.arg)
        if argumentos.vararg:
            nombres.add(argumentos.vararg.arg)
        if argumentos.kwarg:
            nombres.add(argumentos.kwarg.arg)
    for nodo in ast.walk(funcion):
        if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, (ast.Store, ast.Del)):
            nombres.add(nodo.id)
        elif isinstance(nodo, (ast.Import, ast.ImportFrom)):
            for alias in nodo.names:
                nombres.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(nodo, ast.ExceptHandler) and nodo.name:
            nombres.add(nodo.name)
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if not isinstance(nodo, ast.Lambda):
                nombres.add(nodo.name)
            # Una anidada aporta SUS argumentos al cuerpo que la contiene sólo dentro de
            # ella; como el barrido es por función y `ast.walk` entra, se añaden aquí.
            for arg in (
                *nodo.args.posonlyargs, *nodo.args.args, *nodo.args.kwonlyargs,
            ):
                nombres.add(arg.arg)
            if nodo.args.vararg:
                nombres.add(nodo.args.vararg.arg)
            if nodo.args.kwarg:
                nombres.add(nodo.args.kwarg.arg)
    return nombres


def nombres_sin_definir(fuente: str) -> list[tuple[str, str, int]]:
    """`(funcion, nombre, linea)` de cada lectura de un nombre que no existe ahi."""
    arbol = ast.parse(fuente)
    conocidos = _globales(arbol) | set(dir(builtins)) | {"__file__", "__name__"}
    fallos: list[tuple[str, str, int]] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        dentro = _definidos_dentro(nodo)
        for hijo in ast.walk(nodo):
            if isinstance(hijo, ast.Name) and isinstance(hijo.ctx, ast.Load):
                if hijo.id not in dentro and hijo.id not in conocidos:
                    fallos.append((nodo.name, hijo.id, hijo.lineno))
    return fallos


class TestLaPaginaNoLeeNombresQueNoExisten(unittest.TestCase):

    def test_cero_nombres_sin_definir(self):
        fallos = nombres_sin_definir(PAGINA.read_text(encoding="utf-8"))
        self.assertEqual(
            fallos, [],
            "la página lee nombres que ahí dentro no existen; cada uno es un "
            "`NameError` que se lleva por delante todo lo que va por debajo: "
            + ", ".join(f"{f}:{n} (línea {l})" for f, n, l in fallos),
        )

    def test_Y_EL_DETECTOR_MUERDE_sobre_el_codigo_que_habia(self):
        """CONTROL ADVERSARIO, con la forma REAL del fallo (principio nº 18).

        No es una función inventada: es la línea tal cual estaba en `_modal_seed`, con
        `fondo` —la variable del OTRO modal— dentro. Sin esto, «cero sin definir» y «el
        detector no mira nada» darían el mismo verde (errata nº 29).
        """
        antes = (
            "import streamlit as st\n"
            "def _modal_seed(seleccion, nombre, maduros, proyecto=None):\n"
            "    starts = (1, 2)\n"
            "    params = None\n"
            "    huella = run_fingerprint(tuple(starts), params, fondo)\n"
            "    return huella\n"
        )
        fallos = nombres_sin_definir(antes)
        self.assertIn(
            ("_modal_seed", "fondo", 5), fallos,
            f"el detector no ve el fallo que lo motiva; lo que ve es {fallos}",
        )

    def test_y_NO_muerde_sobre_codigo_correcto(self):
        """La otra mitad: un guardia con falsos positivos se acaba apagando.

        Las tres formas que mas aparecen en esta página y que un barrido ingenuo marca:
        una variable atada dentro de un `if`, el objetivo de un `for`, y un nombre que
        entra por un `import` local.
        """
        bueno = (
            "def _panel(x):\n"
            "    if x:\n"
            "        y = 1\n"
            "    for fila in x:\n"
            "        pass\n"
            "    from shmir_design import presentation\n"
            "    return y, fila, presentation\n"
        )
        self.assertEqual(nombres_sin_definir(bueno), [])

    def test_el_detector_HA_MIRADO_de_verdad(self):
        """Prueba de vida (principio nº 51): que el barrido encuentre funciones.

        Si la página cambiara de forma —o el parser dejara de reconocerla— «cero
        fallos» sería el mismo verde que da un fichero vacío.
        """
        arbol = ast.parse(PAGINA.read_text(encoding="utf-8"))
        funciones = [
            n for n in ast.walk(arbol)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.assertGreater(len(funciones), 30, "el barrido no ve la página")
        self.assertTrue(
            any(f.name == "_modal_seed" for f in funciones),
            "no se encuentra `_modal_seed`, que es la función donde vivía el fallo",
        )


if __name__ == "__main__":
    unittest.main()
