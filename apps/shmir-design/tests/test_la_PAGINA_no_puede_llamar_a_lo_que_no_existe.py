"""La pagina no puede llamar a lo que no existe: ni un NOMBRE, ni un ARGUMENTO.

Son dos comprobaciones y una sola causa: **`ui/streamlit_app.py` no se puede ejecutar en
la suite**, asi que nada de lo que hay mira lo que pasa cuando alguien pulsa. Las dos
clases de fallo que eso deja vivas han caido las dos en dos dias, y las dos en el mismo
modal:

  · `NameError: name 'fondo' is not defined` — un nombre que ahi dentro no existe;
  · `TypeError: seed_run() got an unexpected keyword argument 'organism'` — una llamada
    con un argumento que la funcion no acepta.

Ninguna de las dos necesita ejecutar nada para verse: las dos estan en el FUENTE.

**EL PRIMER CASO, y llevaba dos dias vivo en produccion (errata nº 158).** El 2026-09-09, al
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

**EL SEGUNDO, al dia siguiente y sobre el arreglo del primero (errata nº 159).**
`presentation.seed_run` es un atajo con nombre estable para la pagina que **transcribe
la firma** de `seed_scan.run_scan`. Al entrar el eje de organismo se actualizo la de
abajo, la del atajo se quedo atras, y la pagina —que llama por ahi— reventaba con un
`TypeError` **al pulsar el boton**. Es el principio nº 13 sobre una FIRMA: una lista de
parametros transcrita es una segunda definicion, y envejece por su cuenta.

Que este segundo fallo entrara en el mismo commit que arreglaba el primero es el
argumento entero: **quien acaba de mirar ese codigo es quien mas cree que no le hace
falta un guardia** (principio nº 26). El de nombres no podia verlo — `seed_run` SI
existe; lo que no existe es su parametro.

**Guardia, no trinquete: el numero correcto es CERO en las dos.** Una llamada imposible
no es deuda pendiente — es una rama que revienta la primera vez que alguien la recorre.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import ast
import builtins
import inspect
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


# ─── La SEGUNDA mitad: los ARGUMENTOS ────────────────────────────────────────


#: Un valor que no es nada, para `bind_partial`: lo unico que se comprueba es si los
#: nombres ENCAJAN en la firma, no que los valores sirvan.
CUALQUIERA = object()


def _importados(arbol: ast.Module) -> dict[str, str]:
    """`{nombre local: modulo}` de lo que la pagina trae de `shmir_design.*`.

    Solo de este paquete: de `streamlit` y de la libreria estandar no se comprueba nada
    —no son nuestros y su firma no la movemos nosotros—, y meterlos daria hallazgos
    ciertos sobre codigo correcto el dia que una version cambie un argumento opcional.
    """
    traidos: dict[str, str] = {}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.ImportFrom) or not nodo.module:
            continue
        if not nodo.module.startswith("shmir_design"):
            continue
        for alias in nodo.names:
            if alias.name != "*":
                traidos[alias.asname or alias.name] = nodo.module
    return traidos


def _resolver(modulo: str, nombre: str):
    import importlib

    try:
        return getattr(importlib.import_module(modulo), nombre)
    except AttributeError:
        # rule2-ok: un nombre que el modulo no exporta NO se pierde aqui — lo caza el
        # `import` de la propia pagina al arrancar, que es antes y con mejor mensaje.
        # Lo que este barrido contesta es «¿encaja la llamada en la firma?», y de algo
        # que no existe no hay firma que mirar: devolver `None` es decir «esta pregunta
        # no aplica», no tragarse un fallo.
        return None


def llamadas_imposibles(fuente: str) -> list[tuple[str, str, int]]:
    """`(funcion, motivo, linea)` de cada llamada que la firma NO admite.

    Se salta las llamadas con `*args`/`**kwargs` desempaquetados: ahi no se sabe que
    llega, y un hallazgo sobre eso seria adivinar. Lo que se comprueba es lo que si se
    puede: que los nombres de los argumentos escritos existan en la firma, y que no
    sobren posicionales.
    """
    arbol = ast.parse(fuente)
    traidos = _importados(arbol)
    fallos: list[tuple[str, str, int]] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Name):
            continue
        modulo = traidos.get(nodo.func.id)
        if modulo is None:
            continue
        objetivo = _resolver(modulo, nodo.func.id)
        if not callable(objetivo) or isinstance(objetivo, type):
            continue
        if any(isinstance(a, ast.Starred) for a in nodo.args):
            continue
        if any(k.arg is None for k in nodo.keywords):
            continue
        try:
            firma = inspect.signature(objetivo)
        except (TypeError, ValueError):
            # rule2-ok: hay callables SIN firma introspectable (algunos builtins y
            # objetos en C). No es un fallo del codigo mirado: es que de ese no se puede
            # decir nada, y decir algo seria adivinar. Se salta, y la cuenta de la
            # prueba de vida delata el dia que se salten demasiados.
            continue
        try:
            firma.bind_partial(
                *([CUALQUIERA] * len(nodo.args)),
                **{k.arg: CUALQUIERA for k in nodo.keywords},
            )
        except TypeError as exc:
            # rule2-ok: ESTE `except` ES EL RESULTADO, no un fallo tragado. `bind_partial`
            # lanza `TypeError` exactamente cuando la llamada no encaja en la firma, que
            # es lo que este barrido viene a encontrar; el mensaje se conserva entero y
            # sale en el aserto.
            fallos.append((nodo.func.id, str(exc), nodo.lineno))
    return fallos


class TestLaPaginaNoLlamaConArgumentosQueNoExisten(unittest.TestCase):

    def test_cero_llamadas_imposibles(self):
        fallos = llamadas_imposibles(PAGINA.read_text(encoding="utf-8"))
        self.assertEqual(
            fallos, [],
            "la página llama con argumentos que la firma no admite; cada uno es un "
            "`TypeError` al pulsar: "
            + "; ".join(f"{f} (línea {l}): {m}" for f, m, l in fallos),
        )

    def test_Y_EL_DETECTOR_MUERDE_sobre_el_codigo_que_habia(self):
        """CONTROL ADVERSARIO con la forma REAL del fallo (principio nº 18).

        Es la llamada tal cual estaba: `seed_run(..., organism=eje)` contra un
        `seed_run` que no lo aceptaba. Se construye pidiendo la firma ANTERIOR en vez de
        escribirla, que es lo que hace que el control pruebe el caso y no el comprobador.
        """
        antes = (
            "from shmir_design.presentation import seed_run\n"
            "def _modal_seed(seleccion, nombre, maduros, eje):\n"
            "    return seed_run(\n"
            "        seleccion, mature=maduros, params=None, species=nombre,\n"
            "        starts=(1,), guides=True, passengers=True, organism=eje,\n"
            "    )\n"
        )
        from shmir_design import presentation

        firma_de_antes = [
            p for p in inspect.signature(presentation.seed_run).parameters
            if p != "organism"
        ]

        def _sin_organismo(*a, **k):
            pass

        _sin_organismo.__signature__ = inspect.Signature(
            [
                inspect.Parameter(
                    nombre,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD if i == 0
                    else inspect.Parameter.KEYWORD_ONLY,
                )
                for i, nombre in enumerate(firma_de_antes)
            ]
        )
        original = presentation.seed_run
        presentation.seed_run = _sin_organismo
        try:
            fallos = llamadas_imposibles(antes)
        finally:
            presentation.seed_run = original
        self.assertTrue(
            any(f == "seed_run" and "organism" in m for f, m, _ in fallos),
            f"el detector no ve el fallo que lo motiva; lo que ve es {fallos}",
        )

    def test_y_NO_muerde_sobre_una_llamada_correcta(self):
        """La otra mitad. Un guardia con falsos positivos se acaba apagando."""
        bueno = (
            "from shmir_design.presentation import seed_run\n"
            "def _modal(seleccion, nombre, maduros, eje):\n"
            "    return seed_run(\n"
            "        seleccion, mature=maduros, params=None, species=nombre,\n"
            "        starts=(1,), guides=True, passengers=True, organism=eje,\n"
            "    )\n"
        )
        self.assertEqual(llamadas_imposibles(bueno), [])

    def test_el_detector_HA_MIRADO_de_verdad(self):
        """Prueba de vida (principio nº 51): que encuentre llamadas que comprobar.

        Si la página dejara de importar por nombre —o el resolvedor fallara en silencio—
        «cero imposibles» sería el mismo verde que da un fichero sin una sola llamada.
        """
        arbol = ast.parse(PAGINA.read_text(encoding="utf-8"))
        traidos = _importados(arbol)
        self.assertGreater(
            len(traidos), 50, "la página no trae nombres de `shmir_design`"
        )
        comprobables = [
            n for n in ast.walk(arbol)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in traidos
        ]
        self.assertGreater(
            len(comprobables), 50,
            "el barrido no encuentra llamadas que comprobar",
        )
        self.assertIn(
            "seed_run", {n.func.id for n in comprobables},
            "no se encuentra la llamada donde vivía el fallo",
        )


if __name__ == "__main__":
    unittest.main()
