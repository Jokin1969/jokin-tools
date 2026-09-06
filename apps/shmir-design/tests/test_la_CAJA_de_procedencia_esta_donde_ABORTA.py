"""La caja para declarar la procedencia va DONDE aparece el problema, no sólo en el gestor.

Reportado dos veces por el responsable del proyecto (2026-09-04 y 2026-09-06), la segunda
con el texto YA arreglado delante: el aviso nombraba el paso correcto —la fila del gestor,
en «Ficheros de referencia»— y aun así seguía bloqueado. Y es que un aviso que nombra el
paso correcto **sigue siendo un aviso**: hay que ir a buscarlo, es otro paso de la página,
y quien está en el modal está bloqueado EN el modal.

Es la errata nº 83 llevada hasta el final: allí el texto no nombraba el paso que cierra el
problema; aquí lo nombra y la salida seguía estando en otro sitio.

LO QUE ESTE TEST PROTEGE no es que la caja se pinte —eso lo ve un ojo— sino que la FILA
del modal traiga todo lo que la caja necesita para escribir. Una caja pintada sobre una
fila incompleta se ve igual de bien y revienta al pulsar, que es peor que no tenerla.
"""

import re
import unittest
from pathlib import Path

from shmir_design import presentation

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")


def _cuerpo(nombre: str) -> str:
    inicio = PAGINA.index(f"def {nombre}(")
    resto = PAGINA[inicio:]
    return resto[: resto.index("\ndef ", 1)]


class TestLaCajaSeOfreceEnElModal(unittest.TestCase):
    def test_el_panel_del_modal_llama_a_la_MISMA_caja_del_gestor(self):
        """La misma función, no una segunda: dos formularios para lo mismo acabarían
        escribiendo cosas distintas."""
        self.assertIn("_declarar_procedencia(", _cuerpo("_panel_deposito"))

    def test_y_sigue_estando_en_el_gestor(self):
        """No se mueve: se ofrece en los dos sitios donde el problema se ve."""
        self.assertIn("_declarar_procedencia(", _cuerpo("_fila_presente"))


class TestLaFilaTraeLoQueLaCajaNECESITA(unittest.TestCase):
    """Las claves se DERIVAN del código de la caja, no se transcriben aquí: si mañana
    pide una más, este test la exige sin que nadie se acuerde (principio nº 13)."""

    @classmethod
    def setUpClass(cls):
        cuerpo = _cuerpo("_declarar_procedencia")
        cls.claves = set(re.findall(r"fila(?:\.get)?[\[(]\"([a-z_]+)\"", cuerpo))

    def test_el_test_encuentra_claves(self):
        """Sin esto, «no falta ninguna» y «no he mirado» dan el mismo verde."""
        self.assertTrue(self.claves)

    def test_la_fila_del_MODAL_las_trae_todas(self):
        fila = presentation.deposit_file(
            "transcriptoma", species="raton",
            directory=RAIZ / "data" / "reference",
        )
        faltan = sorted(self.claves - set(fila))
        self.assertEqual(faltan, [], f"la fila del modal no trae: {faltan}")

    def test_y_la_del_GESTOR_tambien(self):
        panel = presentation.refinement_panel(
            "raton", directory=RAIZ / "data" / "reference"
        )
        for fila in panel["filas"]:
            with self.subTest(fila["nombre"]):
                self.assertEqual(sorted(self.claves - set(fila)), [])


if __name__ == "__main__":
    unittest.main()
