"""Mientras el informe lea los almacenes y la tabla no, la pantalla LO DICE.

**El problema no es que la tanda este a medias: es una INCONSISTENCIA NUEVA.** Antes los
dos artefactos callaban —la tabla decia `NOT_RUN` y el documento tambien— y eran
coherentes en su ignorancia. Ahora el documento puede decir `PASS` de un frente que la
pantalla sigue enseñando en `NOT_RUN`, y **el que se entrega es el documento**.

Quien mire los dos concluira que uno de ellos esta mal, y no tiene forma de saber cual.
Un desacuerdo DECLARADO es manejable; uno silencioso, no.

El aviso se borra cuando la tabla lea los almacenes, y hay un test que lo obliga: una
excepcion que no caduca deja de ser una excepcion.
"""

import unittest

from shmir_design import presentation


class TestElDESACUERDOseDECLARA(unittest.TestCase):

    def test_hay_un_aviso_y_dice_QUIEN_dice_que(self):
        aviso = presentation.TABLE_LAGS_REPORT
        self.assertIn("informe", aviso.lower())
        self.assertIn("tabla", aviso.lower())

    def test_dice_CUAL_manda(self):
        # Sin esto el aviso solo siembra duda: quien lo lee tiene que saber a cual creer.
        self.assertIn("informe", presentation.TABLE_LAGS_REPORT.lower())

    def test_la_pagina_lo_pinta_cuando_HAY_proyecto_abierto(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("TABLE_LAGS_REPORT", fuente)


class TestElAVISO_CADUCA(unittest.TestCase):
    """Cuando la tabla lea los almacenes, este aviso miente. Que se entere la suite."""

    def test_mientras_la_tabla_NO_lea_los_almacenes_el_aviso_hace_falta(self):
        import inspect

        fuente = inspect.getsource(presentation.site_table_rows)
        lee = "store" in fuente or "almacen" in fuente
        self.assertFalse(
            lee,
            "`site_table_rows` ya lee los almacenes: el desacuerdo se acabo y "
            "`TABLE_LAGS_REPORT` hay que BORRARLO, junto con este test y la llamada de "
            "la pagina. Un aviso que sobrevive a su causa es peor que no haberlo puesto: "
            "manda a desconfiar de una tabla que ya es correcta.",
        )


if __name__ == "__main__":
    unittest.main()
