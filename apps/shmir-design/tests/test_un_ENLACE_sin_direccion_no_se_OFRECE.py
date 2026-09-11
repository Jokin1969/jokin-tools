"""Un boton de enlace con `href` vacio no se ofrece: abre la PROPIA pagina.

**De donde sale.** Salio MIDIENDO, no leyendo. Al reproducir con Chromium por el proxy
del hub lo reportado sobre los dos botones del FASTA de consulta, el volcado del DOM de la
pagina real trajo esto:

    {"texto": "↗ siDirect",              "atributo": "", "resuelto": ".../shmir/"}
    {"texto": "↗ BLOCK-iT RNAi Designer", "atributo": "", "resuelto": ".../shmir/"}

O sea: `st.link_button(label, "")` pinta `<a href="" target="_blank">`, y un `href` vacio
**resuelve a la URL de la propia pagina**. El boton se ve activo, se pulsa, y abre una
pestaña con la app otra vez — indistinguible de uno roto, y con el agravante de que el
usuario cree haber ido a la herramienta externa.

Son las dos herramientas cuya direccion **nadie ha aportado**
(`external_score.URL_NOT_PROVIDED`): la regla 4 prohibe inventarles una URL, asi que la
salida no es escribir una — es **no ofrecer el enlace y decir por que**.

**La decision estaba escrita en UNO de los dos sitios** que pintan enlaces: la tarjeta de
un frente ya hacia `disabled=not tarjeta["url"].startswith("http")` **en la pagina**
(regla 6), y el panel de herramientas externas no hacia nada. Un criterio copiado a medias
entre dos sitios es el principio nº 27; ahora lo decide `presentation.link_usable` y lo
leen los dos.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import pathlib
import re
import unittest

from shmir_design.external_score import EXTERNAL_TOOLS, URL_NOT_PROVIDED
from shmir_design.presentation import link_usable

PAGINA = pathlib.Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"


def sin_comentarios(texto: str) -> str:
    """El fuente SIN comentarios ni docstrings.

    El comentario que explica este fallo nombra `link_usable` y `startswith`, asi que sin
    podar, el guardia pasaria por su propia documentacion — el ancla falsa de la errata
    nº 54.
    """
    fuera = re.sub(r'"""[\s\S]*?"""', "", texto)
    return "\n".join(l.split("#", 1)[0] for l in fuera.splitlines())


class TestLinkUsable(unittest.TestCase):

    def test_una_cadena_vacia_NO_es_utilizable(self):
        """Es la forma exacta del fallo medido."""
        self.assertFalse(link_usable(""))

    def test_ni_None_ni_los_blancos(self):
        for valor in (None, "   ", "\n"):
            with self.subTest(valor=valor):
                self.assertFalse(link_usable(valor))

    def test_una_direccion_http_SI(self):
        self.assertTrue(link_usable("https://portals.broadinstitute.org/gpp/public/"))

    def test_y_una_ruta_RELATIVA_tambien(self):
        """La segunda via de las descargas sirve `/shmir/app/static/…`: es legitima."""
        self.assertTrue(link_usable("/shmir/app/static/x.fasta.txt"))

    def test_el_MOTIVO_no_es_una_direccion(self):
        """`url_note` devuelve la explicacion cuando no hay URL, y eso no se enlaza."""
        self.assertFalse(link_usable(URL_NOT_PROVIDED))


class TestLasHerramientasSinDireccion(unittest.TestCase):

    def test_las_hay_HOY_y_por_eso_el_guardia_sirve(self):
        """Prueba de vida (principio nº 51).

        Si algun dia se aportan las cinco direcciones, este test falla y hay que decidir:
        el guardia se queda —protege a la siguiente— pero deja de estar EJERCITADO, y eso
        tiene que verse en vez de pasar en silencio.
        """
        sin_url = [h.name for h in EXTERNAL_TOOLS if not link_usable(h.url)]
        self.assertTrue(
            sin_url,
            "ninguna herramienta esta sin direccion: este guardia ya no se ejercita "
            "sobre ningun caso real y hay que decidir si se conserva.",
        )

    def test_y_las_que_SI_la_tienen_se_siguen_ofreciendo(self):
        """La otra mitad: desactivarlas todas pasaria el guardia igual de bien."""
        con_url = [h.name for h in EXTERNAL_TOOLS if link_usable(h.url)]
        self.assertTrue(con_url, "ninguna herramienta se ofrece: el panel no sirve")


class TestLaPaginaNoDecideElEnlace(unittest.TestCase):

    def setUp(self):
        self.fuente = sin_comentarios(PAGINA.read_text(encoding="utf-8"))

    def test_ningun_link_button_se_pinta_sin_preguntar(self):
        """TODO `st.link_button` de la pagina pasa por `link_usable`.

        Se mira por VECINDARIO y no por fichero: con un solo `link_usable` en cualquier
        parte, un tercer boton entraria sin comprobar nada.

        **Y la ventana mira a los DOS lados**, que es una calibracion y no un detalle: la
        primera version solo miraba hacia delante y dio un falso positivo sobre el panel
        de herramientas externas, donde la decision se calcula en la linea de ARRIBA
        (`utilizable = link_usable(...)`) porque ademas elige el tooltip. Un guardia con
        falsos positivos se acaba apagando — y el arreglo obvio habria sido mover codigo
        correcto para contentarlo.
        """
        trozos = self.fuente.split("st.link_button(")
        for i, trozo in enumerate(trozos[1:], start=1):
            vecindario = trozos[i - 1][-300:] + trozo[:400]
            self.assertIn(
                "link_usable", vecindario,
                "un st.link_button se pinta sin comprobar su direccion: "
                f"{trozo[:160]!r}",
            )

    def test_y_la_pagina_NO_decide_por_su_cuenta(self):
        """Regla 6: el criterio vive en `presentation`, no en la vista.

        Estaba escrito como `.startswith("http")` dentro de la pagina — correcto y en el
        sitio equivocado, que es como se acaba teniendo dos criterios para lo mismo.
        """
        self.assertNotIn('startswith("http', self.fuente)

    def test_hay_al_menos_DOS_botones_de_enlace(self):
        """Prueba de vida del detector: si dejara de encontrarlos, todo pasaria."""
        self.assertGreaterEqual(self.fuente.count("st.link_button("), 2)

    def test_Y_LA_VENTANA_SIGUE_MORDIENDO_despues_de_ensancharla(self):
        """Control adversario de la calibracion, y por eso va pegado a ella.

        Ensanchar una ventana para quitar un falso positivo es exactamente como se llega
        a un guardia que aprueba cualquier cosa: con 300 caracteres por detras, un
        `link_usable` de OTRO bloque podria amparar al de al lado. Se le da un boton
        rodeado de codigo que no pregunta nada y tiene que verlo.
        """
        falso = (
            "def _panel():\n"
            + "    st.caption('x')\n" * 40
            + "    st.link_button('↗ una herramienta', herramienta.url)\n"
            + "    st.caption('y')\n" * 40
        )
        trozos = falso.split("st.link_button(")
        vecindario = trozos[0][-300:] + trozos[1][:400]
        self.assertNotIn("link_usable", vecindario)


if __name__ == "__main__":
    unittest.main()
