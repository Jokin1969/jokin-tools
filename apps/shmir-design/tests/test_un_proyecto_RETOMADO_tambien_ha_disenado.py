"""Con un proyecto retomado, el paso 5 tiene que aparecer.

Reportado el 2026-09-06: la caja del modal ya está —o sea que el despliegue es nuevo— y
«el paso 5 sigo sin verlo». Y es cierto, con una causa medida: había DOS definiciones de
«se ha diseñado» y la que decide si el paso 5 se pinta no conocía el camino del proyecto
retomado.

    linea 1871:  designed=st.session_state.get("accion") == "diseñar"
    linea 1987:  accion = "diseñar" if retomado is not None else session["accion"]

La segunda es la que decide si se corre el diseño y se pintan los resultados y los cuatro
modales. La primera decide si el paso 5 es visible. Con un proyecto retomado, la segunda
dice «diseñar» y la primera dice que no: se ven los modales y NO se ve el paso 5, que es
exactamente lo reportado.

Es el patrón de `resolve.py` una vez más —la misma pregunta contestada en dos sitios, y
uno se entera de un camino nuevo y el otro no— y aquí se cobra la ÚNICA vía alternativa
cuando el modal falla.
"""

import re
import unittest
from pathlib import Path

from shmir_design import presentation

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
CODIGO = "\n".join(
    l for l in PAGINA.splitlines() if not l.strip().startswith("#")
)


class TestLaAccionSeResuelveEnUnSitio(unittest.TestCase):
    def test_retomar_un_proyecto_ES_haber_disenado(self):
        self.assertEqual(
            presentation.design_action(None, resumed=True), "diseñar"
        )

    def test_sin_proyecto_retomado_manda_lo_que_se_pulso(self):
        self.assertEqual(
            presentation.design_action("estimar", resumed=False), "estimar"
        )
        self.assertIsNone(presentation.design_action(None, resumed=False))

    def test_y_un_proyecto_retomado_NO_pisa_una_estimacion_en_curso(self):
        """Retomar es ver el resultado; si además se pidió estimar, se estima."""
        self.assertEqual(
            presentation.design_action("estimar", resumed=True), "estimar"
        )


class TestLaPaginaNoLaCalculaDOS_VECES(unittest.TestCase):
    def test_la_pagina_no_compara_la_accion_a_mano(self):
        """El literal comparado a mano es lo que permitió que hubiera dos definiciones.
        Se quitan los comentarios antes de mirar: el que explica el fallo lo nombra."""
        self.assertNotIn('== "diseñar"', CODIGO)
        self.assertNotIn('"diseñar" if', CODIGO)

    def test_y_lo_resuelve_llamando_al_nucleo(self):
        self.assertIn("design_action(", CODIGO)

    def test_steps_rows_recibe_ESA_accion_y_no_otra_expresion(self):
        # Se recorta la llamada CONTANDO PARENTESIS: cortar en el primer `)` la partia
        # dentro de `reference_dir()` y el test pasaba mirando media llamada.
        resto = CODIGO[CODIGO.index("steps_rows(") + len("steps_rows"):]
        nivel, fin = 0, 0
        for i, c in enumerate(resto):
            nivel += (c == "(") - (c == ")")
            if nivel == 0:
                fin = i
                break
        llamada = resto[: fin + 1]
        self.assertIn("designed=", llamada)
        self.assertNotIn("session_state", llamada)


if __name__ == "__main__":
    unittest.main()
