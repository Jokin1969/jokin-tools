"""El SEGUNDO rerun: el eje que el inventario de estados no tenia.

**Por que existe este fichero.** Los 29 estados del inventario describian la pagina
recien pintada, y ninguno decia nada de lo que pasa AL VOLVER A PINTARLA. El fallo de la
errata nº 42 vivia justo ahi: el panel de proyecto se pintaba bien la primera vez y
devolvia `None` en la segunda, porque el boton de crear vale `True` UN SOLO rerun. Un
inventario que solo mira el primer render no puede ver esa clase de fallo — y en
Streamlit **cada tecla que el usuario escribe es un rerun**, asi que el segundo render es
el caso NORMAL, no un caso raro.

**Lo que este test SI cubre y lo que NO.** Cubre que la pagina sobrevive a un rerun
provocado por tocar un widget, en el estado al que `AppTest` puede llegar hoy
(`SIN_DISEÑAR`). NO cubre el panel de proyecto ni los modales: viven detras del boton de
diseñar, que necesita un `file_uploader`, y eso `AppTest` no lo rellena. Esa mitad sigue
declarada como bloqueada en `data/estados.toml`, con lo que la cerraria.
"""

import sys
import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest

    STREAMLIT = True
except ImportError:  # rule2-ok: ausencia de una dependencia OPCIONAL de la interfaz.
    STREAMLIT = False

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "ui" / "streamlit_app.py"
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def segundo_rerun():
    """Pinta la pagina, TOCA un widget y la vuelve a pintar.

    El ayudante existe para que el auditor de estados lo reconozca por su nombre, igual
    que `deposito_completo()` y `deposito_vacio()`: la causa es una sola y el marcador
    tambien.
    """
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    if app.text_input:
        app.text_input[0].set_value("lo que sea")
    elif app.checkbox:
        app.checkbox[0].set_value(True)
    return app.run()


@unittest.skipUnless(STREAMLIT, "Streamlit no instalado: la interfaz es opcional")
class TestLaPaginaSOBREVIVEalSegundoRENDER(unittest.TestCase):

    def test_el_segundo_rerun_no_revienta(self):
        app = segundo_rerun()
        self.assertFalse(
            app.exception,
            f"La pagina falla al repintarse: {[e.value for e in app.exception]}",
        )

    def test_y_sigue_habiendo_pagina_despues(self):
        # Un rerun que no revienta pero deja la pantalla vacia es el mismo fallo con otra
        # cara: el panel desaparecia sin dar ningun error.
        app = segundo_rerun()
        # El titulo y los pasos, que es el esqueleto: si el rerun se hubiera quedado a
        # medias estarian vacios. (`markdown` sale a cero incluso en el primer render —
        # esta pagina escribe con `title`, `header` y `caption`—, asi que mirarlo habria
        # dado un fallo que no es del rerun.)
        self.assertTrue(app.title)
        self.assertTrue(app.header)


if __name__ == "__main__":
    unittest.main()
