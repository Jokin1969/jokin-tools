"""El texto no se atenúa mientras la app trabaja; sale un aviso que lo dice.

Regla 5: escritos antes.

**Reportado así** (2026-09-10): *«cada vez que le doy a un botón o un clic en alguna
casilla o relleno algo que luego guarda, se baja la intensidad del texto como dejando ver
que está pensando»*. Y lo que se pide en su lugar: *«una nota, ventana o similar diciendo
lo que está haciendo, pero sin bajar la intensidad del texto»*.

**MEDIDO en Chromium por el proxy del hub, no supuesto.** Al repintarse, Streamlit marca
el contenedor de cada elemento con `data-stale="true"`, le cambia la clase de emotion y le
pone `transition: opacity 1s ease-in 0.5s`. Ese medio segundo de retardo es lo que hacía
que pareciera intermitente: en un repintado corto no llega a verse; en una corrida larga
se ve entero.

**Lo que hace ese atenuado es avisar QUITANDO**: apaga justo lo que se estaba leyendo, y
no dice qué pasa ni cuánto queda. Se sustituye por lo contrario — un aviso que AÑADE.

**El gancho del aviso es `stStatusWidget`**, que existe SÓLO mientras el script corre
(medido: 0 apariciones en reposo, 7 durante). Así que se enciende y se apaga solo,
derivado del estado real y no de un temporizador nuestro.
"""

import ast
import pathlib
import re
import unittest

from shmir_design import presentation

PAGINA = pathlib.Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
FUENTE = PAGINA.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    # La lección de la errata nº 54: un ancla dentro del comentario que explica la regla
    # da verde sin comprobar nada.
    fuera = "\n".join(
        l for l in texto.split("\n") if not l.lstrip().startswith("#")
    )
    return re.sub(r"/\*.*?\*/", "", fuera, flags=re.S)


class TestElTextoNoSeAtenua(unittest.TestCase):

    def setUp(self):
        self.css = _sin_comentarios(presentation.page_stylesheet())

    def test_la_hoja_neutraliza_el_atenuado_de_lo_PENDIENTE(self):
        regla = re.search(r'\[data-stale="true"\]\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(
            regla, "la hoja no dice nada de `data-stale`, que es el gancho medido"
        )
        cuerpo = regla.group(1)
        self.assertIn("opacity: 1", cuerpo)
        self.assertIn("!important", cuerpo)

    def test_y_TAMBIEN_la_transicion(self):
        """Sin esto el navegador sigue animando hacia la opacidad nueva.

        Es la mitad que no se ve al leer la regla: `opacity: 1` gana el valor final y la
        `transition` sigue declarada, así que el desvanecido se ejecuta igual hasta que
        el estilo nuevo se aplica. Lo medido es `transition: opacity 1s ease-in 0.5s`.
        """
        regla = re.search(r'\[data-stale="true"\]\s*\{([^}]*)\}', self.css)
        self.assertIn("transition: none", regla.group(1))

    def test_esta_escrito_POR_QUE(self):
        for clave in ("data-stale", "avisa", "atenú"):
            with self.subTest(clave):
                self.assertIn(clave.lower(), presentation.WHY_NO_DIMMING.lower())


class TestElAvisoDeQueLaAppTrabaja(unittest.TestCase):

    def setUp(self):
        self.css = _sin_comentarios(presentation.page_stylesheet())

    def test_el_aviso_cuelga_del_ESTADO_REAL_de_ejecucion(self):
        # `stStatusWidget` existe sólo mientras el script corre, así que el aviso no
        # necesita ningún temporizador nuestro — y no puede quedarse encendido.
        self.assertIn('[data-testid="stStatusWidget"]', self.css)

    def test_y_LLEVA_TEXTO(self):
        self.assertIn(presentation.BUSY_NOTICE, self.css)
        self.assertIn("content:", self.css)

    def test_el_aviso_se_VE(self):
        # Un aviso que hereda la opacidad del indicador original vuelve a ser invisible:
        # medido, `stStatusWidget` aparece con opacidad 0 y se desvanece hacia dentro.
        bloque = re.search(
            r'\[data-testid="stStatusWidget"\]\s*\{([^}]*)\}', self.css
        )
        self.assertIsNotNone(bloque)
        cuerpo = bloque.group(1)
        self.assertIn("opacity: 1", cuerpo)
        self.assertIn("position: fixed", cuerpo)

    def test_el_texto_del_aviso_esta_en_CASTELLANO_correcto(self):
        # `check:tildes` mira los literales de prosa, y éste vive en `presentation`
        # justamente para que lo mire.
        self.assertIn("está", presentation.BUSY_NOTICE)


class TestLaPaginaNoMONTAlaHoja(unittest.TestCase):
    """Regla 6: la hoja lleva dos reglas que son mecanismo, así que necesitan test."""

    def test_la_pagina_pide_la_hoja_y_no_la_escribe(self):
        arbol = ast.parse(FUENTE)
        estilo = next(
            (n for n in ast.walk(arbol)
             if isinstance(n, ast.FunctionDef) and n.name == "_estilo"), None,
        )
        self.assertIsNotNone(estilo)
        cuerpo = _sin_comentarios(ast.get_source_segment(FUENTE, estilo) or "")
        self.assertIn("page_stylesheet()", cuerpo)
        for prohibido in ("data-stale", "stStatusWidget", "max-width"):
            with self.subTest(prohibido):
                self.assertNotIn(prohibido, cuerpo)


if __name__ == "__main__":
    unittest.main()
