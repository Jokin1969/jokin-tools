"""La ficha se compara ENTERA, igual que el informe.

Regla 5 y el principio de `docs/principios.md`: el invariante caza lo imposible, no lo
equivocado, y el golden es lo unico que lee la salida entera. Una ficha a la que le falte
un frente entero pasa cualquier test de presencia — es literalmente lo que pasó con las
127 lineas borradas del informe.
"""

import unittest
from pathlib import Path

from shmir_design.reference import REFERENCES, fixture_available

GOLDEN = Path(__file__).resolve().parent / "golden" / "ficha_raton_200.txt"
RATON = REFERENCES["NM_011170.3"]


@unittest.skipUnless(
    GOLDEN.is_file() and fixture_available(RATON),
    "NOT_RUN: falta la ficha de referencia o el fixture del raton",
)
class TestLaFichaEntera(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from tools.regenerar_golden import generar_ficha

        cls.actual = generar_ficha()
        cls.esperado = GOLDEN.read_text(encoding="utf-8")

    def test_la_ficha_es_IGUAL_a_la_de_referencia(self):
        if self.actual != self.esperado:
            import difflib

            diff = "\n".join(
                difflib.unified_diff(
                    self.esperado.splitlines(), self.actual.splitlines(),
                    fromfile="ficha_raton_200.txt (referencia)",
                    tofile="ficha generada ahora", lineterm="",
                )
            )
            self.fail(
                "La ficha ha cambiado. Si el cambio es a proposito, regenerala con "
                "`python3 tools/regenerar_golden.py` y que el diff entre en la "
                f"revision:\n{diff}"
            )

    def test_la_referencia_no_es_un_muñon(self):
        self.assertGreater(len(self.esperado.splitlines()), 30)
        for bloque in (
            "── Frentes", "── Asimetria", "── Techo de APA", "── Hexameros cercanos",
            "── Bloques ──", "── Historial de BLAST ──",
        ):
            with self.subTest(bloque):
                self.assertIn(bloque, self.esperado)

    def test_borrar_un_frente_HACE_FALLAR_la_comparacion(self):
        # El criterio de aceptacion del golden: que un borrado entero se vea.
        mutilada = "\n".join(
            l for l in self.esperado.splitlines() if "offtarget_seed" not in l
        )
        self.assertNotEqual(mutilada, self.actual)


if __name__ == "__main__":
    unittest.main()
