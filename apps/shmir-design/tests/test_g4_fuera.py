"""G4 fuera. La decisión, con su motivo, y las consecuencias comprobadas.

Un regex de tres guaninas NO es un predictor de G4. La estructura es real y sí bloquea
el acceso de RISC, pero formarla depende de ESTABILIDAD, no de coincidencia de motivo, y
la mayoría de secuencias que casan el patrón no forman nada.

Se quita sin impacto medible: cero FAIL en las 1221 ventanas del ratón y las 1585 del
humano — ver la errata nº 9, que explica por qué eso es PEOR y no mejor. Lo que se
comprueba aquí es que la retirada está COMPLETA: quitar el veredicto y dejar el nombre en
una cabecera es lo que produce filas de 36 columnas bajo una cabecera de 38.

Para volver a entrar hacen falta tres cosas por escrito: predictor con cita, umbral con
justificación en `justificacion.py`, y decisión explícita de si es filtro duro o
desempate — con el voto de partida del responsable en «desempate, nunca filtro».
"""

import unittest

from shmir_design import hard_filters
from shmir_design.reference import REFERENCES, fixture_available, load_3utr


class TestNoQuedaNADA(unittest.TestCase):

    def test_no_hay_filter_g4(self):
        self.assertFalse(hasattr(hard_filters, "filter_g4"))

    def test_ni_el_patron_ni_sus_textos(self):
        for nombre in ("G4_PATTERN", "G4_PENDING", "G4_PROVENANCE"):
            with self.subTest(nombre):
                self.assertFalse(hasattr(hard_filters, nombre))

    def test_ninguna_ventana_emite_un_resultado_G4(self):
        resultado = hard_filters.evaluate_window("ACGTACGTACGTACGTACGTAC")
        nombres = {r.name for r in resultado.filters}
        self.assertFalse({n for n in nombres if n.startswith("G4")}, nombres)

    def test_y_tampoco_la_rama_de_las_N(self):
        # La rama de ventanas con N emite los nombres a mano, y es donde se rompió la
        # cabecera del TSV la vez anterior. Los dos caminos tienen que coincidir.
        con_n = hard_filters.evaluate_window("ACGTNACGTACGTACGTACGTA")
        sin_n = hard_filters.evaluate_window("ACGTAACGTACGTACGTACGTA")
        self.assertEqual(
            [r.name for r in con_n.filters], [r.name for r in sin_n.filters]
        )
        self.assertFalse(
            {r.name for r in con_n.filters if r.name.startswith("G4")}
        )


class TestLaMEDIDAQueJustificaLaRetirada(unittest.TestCase):
    """Cero exclusiones en las dos especies. Fijado para que el dato no se pierda."""

    @unittest.skipUnless(
        all(fixture_available(r) for r in REFERENCES.values()), "faltan fixtures"
    )
    def test_quitarlo_no_cambia_ninguna_ventana(self):
        import re

        # El patrón de entonces, reconstruido AQUÍ y sólo aquí: es el dato de la errata
        # nº 9 y tiene que poder recomprobarse sin resucitar el filtro.
        patron = re.compile(
            r"G{3,}[ACGUTN]{1,7}G{3,}[ACGUTN]{1,7}G{3,}[ACGUTN]{1,7}G{3,}"
        )
        for clave, referencia in REFERENCES.items():
            utr = load_3utr(referencia)
            ventanas = [utr[i:i + 22] for i in range(len(utr) - 21)]
            with self.subTest(clave, ventanas=len(ventanas)):
                self.assertEqual(
                    sum(1 for v in ventanas if patron.search(v)), 0,
                    "si esto deja de ser cero, la errata nº 9 hay que revisarla",
                )


if __name__ == "__main__":
    unittest.main()
