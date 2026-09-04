"""El nombre de un proyecto se cambia DONDE SE ELIGE el proyecto.

**Pedido (2026-09-04)**: *«¿me podrías añadir algo para editar el nombre del
proyecto?»*.

Y lo que estaba mal no era que no se pudiera: `store.rename` existe desde la tanda de
mantenimiento y funciona. Lo que estaba mal es **dónde**: el único sitio para renombrar
era el desplegable «Gestionar proyectos» de la barra lateral, y esa barra sólo aparece
**después de haber diseñado** — o sea que para cambiarle el nombre a un proyecto había
que volver a subir la secuencia y correr el diseño entero.

El sitio donde se pide un nombre es el sitio donde se leen los nombres: el paso 0, con
el desplegable de proyectos delante. Es la misma regla que puso el paso 0 arriba del
todo.

Regla 5: escritos antes.
"""

import sys
import tempfile
import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest

    STREAMLIT = True
except ImportError:  # rule2-ok: ausencia de una dependencia OPCIONAL de la interfaz.
    STREAMLIT = False

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import REFERENCES, fixture_available, load_reference

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
from tests.pagina import con_proyectos  # noqa: E402

APP = RAIZ / "ui" / "streamlit_app.py"
FUENTE = APP.read_text(encoding="utf-8")

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _sin_comentarios(texto: str) -> str:
    """Un comentario NOMBRA el mecanismo: buscarlo ahí da verde sin código detrás."""
    return "\n".join(l for l in texto.split("\n") if not l.lstrip().startswith("#"))


def _cuerpo(nombre: str) -> str:
    limpia = _sin_comentarios(FUENTE)
    inicio = limpia.index(f"def {nombre}")
    return limpia[inicio : limpia.index("\ndef ", inicio + 10)]


class TestElPasoCeroRenombra(unittest.TestCase):
    """Se comprueba el CAMINO, no una línea: el paso 0 llega al renombrado.

    Va en dos mitades a propósito. Pedir que la llamada esté escrita DENTRO del paso 0
    ataría el test a que no se saque a un auxiliar —que es lo que se hizo, y no cambia
    nada de lo que este test protege—. Lo que tiene que seguir siendo cierto es que
    desde donde se elige el proyecto se llega a cambiarle el nombre.
    """

    def test_el_paso_cero_llega_al_renombrado(self):
        self.assertIn(
            "_renombrar(", _cuerpo("_paso_cero_proyecto"),
            "el paso 0 enseña los nombres de los proyectos y no deja cambiarlos; el "
            "único sitio para hacerlo estaba detrás de haber diseñado.",
        )

    def test_y_el_renombrado_es_el_de_presentation(self):
        cuerpo = _cuerpo("_renombrar")
        self.assertIn("project_rename(", cuerpo)
        # La fecha es HOY y se DERIVA: renombrar pasa ahora, así que un calendario con
        # otra fecha sería una vía para apuntar el suceso en un día en que no ocurrió.
        self.assertIn("today_text()", cuerpo)

    def test_y_la_pagina_NO_escribe_el_nombre_ella_misma(self):
        # Regla 6: quien toca el log es `presentation`, que además lo APUNTA como un
        # suceso fechado. Una escritura desde la página no dejaría rastro.
        cuerpo = _cuerpo("_paso_cero_proyecto") + _cuerpo("_renombrar")
        for prohibido in (".rename(", "write_text", "project.title"):
            with self.subTest(prohibido):
                self.assertNotIn(prohibido, cuerpo)


class TestRenombrarNoCambiaLaIdENTIDAD(unittest.TestCase):
    """Lo que cambia es el nombre visible; el slug nombra la carpeta y se queda."""

    def setUp(self):
        if not HAY:
            self.skipTest("falta data/reference/NM_011170.3.fa")
        self.raiz = Path(tempfile.mkdtemp(prefix="proyectos_"))
        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        payload, fuente = presentation.anatomy_payload(anatomia)
        presentation.project_create(
            self.raiz, slug="Intento_17", date="2026-09-02", sequence=secuencia,
            species="raton", anatomy=payload, anatomy_source=fuente,
        )

    def test_el_desplegable_ENSEÑA_el_nombre_nuevo(self):
        almacen = presentation.project_open(self.raiz, "Intento_17")
        presentation.project_rename(almacen, "Prnp 3'UTR — tanda buena", date="2026-09-04")
        catalogo = presentation.project_options(self.raiz)
        self.assertIn("Prnp 3'UTR — tanda buena", catalogo["etiquetas"]["Intento_17"])
        self.assertIn("(Intento_17)", catalogo["etiquetas"]["Intento_17"])

    def test_y_se_sigue_abriendo_por_su_slug(self):
        almacen = presentation.project_open(self.raiz, "Intento_17")
        presentation.project_rename(almacen, "Otro nombre", date="2026-09-04")
        vuelta = presentation.project_open(self.raiz, "Intento_17")
        self.assertEqual(vuelta.project.slug, "Intento_17")
        self.assertEqual(vuelta.project.display_name, "Otro nombre")

    def test_el_cambio_queda_APUNTADO_con_su_fecha(self):
        almacen = presentation.project_open(self.raiz, "Intento_17")
        presentation.project_rename(almacen, "Otro nombre", date="2026-09-04")
        notas = presentation.project_open(self.raiz, "Intento_17").records("nota")
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0].date, "2026-09-04")
        self.assertIn("Intento_17", notas[0].payload["texto"])


class TestLaCuentaSeLEE(unittest.TestCase):
    """«3 registro(s)» no decía qué eran. Ahora lo dice, y en singular también."""

    def test_una_sola_va_en_singular(self):
        self.assertEqual(presentation.project_entry_count(1), "1 anotación")

    def test_y_varias_en_plural(self):
        self.assertEqual(presentation.project_entry_count(3), "3 anotaciones")

    def test_ninguna_no_se_calla(self):
        # Un proyecto sin nada guardado tiene que distinguirse de uno con tres: es lo
        # que dice si alguien lo ha tocado, y lo que decide si borrarlo cuesta algo.
        self.assertEqual(presentation.project_entry_count(0), "0 anotaciones")

    def test_y_se_explica_QUE_es_una(self):
        texto = presentation.PROJECT_ENTRY_HELP.lower()
        self.assertIn("historial", texto)
        # Lo que la pregunta pedía aclarar: no son proyectos distintos que se abran.
        self.assertIn("no es otro proyecto", texto)


@unittest.skipUnless(STREAMLIT, "Streamlit no instalado: la interfaz es opcional")
class TestSeRenombraDESDElaPagina(unittest.TestCase):
    """De punta a punta, con la página de verdad — no con las piezas por separado.

    Es la nota de método de la errata nº 54: las funciones sueltas pueden estar bien y el
    usuario ver lo mismo que si estuvieran rotas. Aquí lo que se comprueba es lo que se
    ve: que la ETIQUETA del desplegable enseña el nombre nuevo después de guardarlo.
    """

    def setUp(self):
        if not HAY:
            self.skipTest("falta data/reference/NM_011170.3.fa")
        self.secuencia = load_reference(RATON)
        self.anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(self.secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )

    def _pagina(self):
        return AppTest.from_file(str(APP), default_timeout=120).run()

    def test_el_desplegable_enseña_el_nombre_nuevo_al_guardarlo(self):
        with con_proyectos(
            ("Intento_17", self.secuencia, "raton", self.anatomia)
        ):
            app = self._pagina()
            app.selectbox[0].select("Intento_17").run()
            app.text_input[0].set_value("Prnp tanda buena").run()
            app.button[1].click().run()
            self.assertFalse(app.exception)
            # LO QUE SE VE, que es lo que este test existe para mirar.
            self.assertIn(
                "Prnp tanda buena", " ".join(app.selectbox[0].options)
            )
            # Y la confirmación SOBREVIVE al repintado: sin eso, el cartel que dice que
            # ha cambiado se iría con el `st.rerun()` que hace falta para que la
            # etiqueta se vuelva a montar.
            self.assertTrue(any("Ahora se llama" in s.value for s in app.success))

    def test_y_sin_ningun_proyecto_no_hay_nada_que_renombrar(self):
        # El control cuelga del paso 0, que no se pinta sin proyectos: no puede aparecer
        # un campo «Nombre visible» delante de quien entra por primera vez.
        with con_proyectos():
            app = self._pagina()
            self.assertNotIn(
                "Nombre visible", [i.label for i in app.text_input]
            )


if __name__ == "__main__":
    unittest.main()
