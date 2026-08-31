"""Nada se define DESPUÉS de la llamada a `main()`. Regla 5.

**El fallo, en producción.** `NameError: name '_modal_blast' is not defined`, al pulsar
Diseñar. Los cuatro modales existen —están definidos— pero **después** de la línea que
invoca `main()`. Streamlit ejecuta el script como `__main__`, así que `main()` corre a
mitad del módulo y los nombres de más abajo todavía no existen. Cualquier camino que
llegue a ellos revienta.

**Por qué la suite no lo veía**, y es lo que enseña: `AppTest` no puede rellenar un
`file_uploader`, así que la página nunca llega a DISEÑADO y `bloque_especie` nunca ejecuta
la línea que llama al modal. Es exactamente el estado que `data/estados.toml` declaraba
sin pintar — el inventario acertó otra vez.

**Pero pintarlo no hacía falta.** Este fallo es ESTÁTICO: «hay un `def` después del punto
de entrada» se ve leyendo el fichero, sin ejecutar nada y sin ViennaRNA y sin Streamlit.
Había una comprobación mucho más barata que la que estábamos esperando, y nadie la buscó
porque el estado ya tenía una causa escrita para no estar cubierto. **Un bloqueo declarado
invita a dejar de buscar por otro lado.**
"""

import ast
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"


def _arbol():
    return ast.parse(APP.read_text(encoding="utf-8"))


def _linea_de_la_entrada(arbol) -> int:
    """La línea del `if __name__ == "__main__":`. Aborta si no está: sin punto de
    entrada la comprobación no puede decir nada, y callarse sería un falso verde."""
    for nodo in arbol.body:
        if isinstance(nodo, ast.If) and "__main__" in ast.unparse(nodo.test):
            return nodo.lineno
    raise AssertionError("no hay bloque `if __name__ == '__main__'` en la página")


class TestNadaSeDefineDespuesDeLaENTRADA(unittest.TestCase):

    def test_la_llamada_a_main_es_lo_ULTIMO_del_modulo(self):
        arbol = _arbol()
        entrada = _linea_de_la_entrada(arbol)
        despues = [
            f"{type(n).__name__} {getattr(n, 'name', '')} (línea {n.lineno})"
            for n in arbol.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and n.lineno > entrada
        ]
        self.assertEqual(
            despues, [],
            f"Se define esto DESPUÉS de invocar `main()` en la línea {entrada}: "
            f"{despues}. Streamlit ejecuta el script como `__main__`, así que esos "
            f"nombres no existen cuando `main()` corre.",
        )

    def test_tampoco_una_asignacion_de_modulo(self):
        """Mismo fallo con otra forma: una constante definida después tampoco existe."""
        arbol = _arbol()
        entrada = _linea_de_la_entrada(arbol)
        despues = [
            ast.unparse(n)[:60]
            for n in arbol.body
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.lineno > entrada
        ]
        self.assertEqual(despues, [], f"asignaciones después de `main()`: {despues}")


class TestTodoLoQueLaPAGINAllamaEXISTE(unittest.TestCase):
    """El otro lado, y no depende del orden: que ningún nombre llamado dentro de una
    función de la página falte del módulo. Cazaría un `_modal_*` renombrado a medias."""

    def test_ninguna_llamada_a_un_ayudante_privado_apunta_a_la_nada(self):
        arbol = _arbol()
        definidos = {
            n.name for n in ast.walk(arbol)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        locales = {
            objetivo.id
            for n in ast.walk(arbol)
            if isinstance(n, ast.Assign)
            for objetivo in n.targets
            if isinstance(objetivo, ast.Name)
        }
        faltan = sorted({
            n.func.id
            for n in ast.walk(arbol)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id.startswith("_")
            and n.func.id not in definidos
            and n.func.id not in locales
        })
        self.assertEqual(faltan, [], f"llamadas a ayudantes que no existen: {faltan}")


class TestElCasoREAL(unittest.TestCase):
    """Anclado: los cuatro modales, que son los que reventaron."""

    def test_los_cuatro_modales_se_definen_ANTES_de_la_entrada(self):
        arbol = _arbol()
        entrada = _linea_de_la_entrada(arbol)
        por_nombre = {
            n.name: n.lineno for n in arbol.body
            if isinstance(n, ast.FunctionDef)
        }
        for modal in ("_modal_blast", "_modal_seed", "_modal_empalme", "_modal_offtarget"):
            with self.subTest(modal):
                self.assertIn(modal, por_nombre)
                self.assertLess(por_nombre[modal], entrada)

    def test_y_tambien_los_ayudantes_que_usan(self):
        arbol = _arbol()
        entrada = _linea_de_la_entrada(arbol)
        por_nombre = {
            n.name: n.lineno for n in arbol.body if isinstance(n, ast.FunctionDef)
        }
        for ayudante in ("_guardar_corrida", "_guardar_seleccion", "_casete_de"):
            with self.subTest(ayudante):
                self.assertLess(por_nombre[ayudante], entrada)
