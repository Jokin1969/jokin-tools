"""Tests del plegado (ViennaRNA) y del invariante de estructura del andamio.

Regla 5: escritos antes que `shmir_design/folding.py`.

El valor esperado sale de la biologia, no del propio codigo: la estructura de referencia
es la del 97-mero real de SGEP, y la regla de la pasajera se comprueba viendo que aparear
la posicion 1 en Watson-Crick CAMBIA esa estructura.

ViennaRNA es una dependencia OPCIONAL: sin ella estos tests se saltan de forma visible y
`check_fold` devuelve NOT_RUN, nunca PASS.
"""

import unittest

from shmir_design.filters import FilterState
from shmir_design.folding import VIENNA_AVAILABLE, check_fold, dot_bracket
from shmir_design.scaffold import build_hairpin, reverse_complement

GUIA_REF = "TAGATAAGCATTATAATTCCTA"
HORQUILLA_REF = (
    "TGCTGTTGACAGTGAGCGCAGGAATTATAATGCTTATCTATAGTGAAGCCACAGATGTA"
    "TAGATAAGCATTATAATTCCTATGCCTACTGCCTCGGA"
)


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: ViennaRNA no instalado (pip install ViennaRNA)")
class TestPlegado(unittest.TestCase):

    def test_la_estructura_de_referencia_es_la_de_SGEP(self):
        estructura, dg = dot_bracket(HORQUILLA_REF)
        self.assertEqual(len(estructura), 97)
        self.assertLess(dg, 0)

    def test_cualquier_guia_da_la_misma_notacion_que_SGEP(self):
        referencia, _ = dot_bracket(build_hairpin(GUIA_REF).sequence)
        guias = [
            GUIA_REF,
            GUIA_REF[:-1] + "C",
            GUIA_REF[:-1] + "G",
            GUIA_REF[:-1] + "T",
            "TAAATAAATTTATAAATTTAAA",   # extremo AT
            "GCCGCGGCACGGCCGCAGCGGC",   # extremo GC
            "TAAAGTGCAAGCCAATAATAAC",   # ventana humana 1237
        ]
        for guia in guias:
            with self.subTest(guia):
                estructura, _ = dot_bracket(build_hairpin(guia).sequence)
                self.assertEqual(estructura, referencia)

    def test_aparear_la_posicion_1_en_WC_cambia_la_estructura(self):
        """Es la razon de ser de la regla: si aparea, el tallo se cierra."""
        hairpin = build_hairpin(GUIA_REF)
        referencia, dg_ref = dot_bracket(hairpin.sequence)

        prohibida = reverse_complement(GUIA_REF)[0]
        cerrada = hairpin.sequence.replace(
            hairpin.passenger.sequence, prohibida + hairpin.passenger.sequence[1:], 1
        )
        estructura, dg = dot_bracket(cerrada)
        self.assertNotEqual(estructura, referencia)
        self.assertLess(dg, dg_ref)  # mas estable justamente porque cierra el tallo

    def test_check_fold_pasa_con_una_horquilla_bien_montada(self):
        resultado = check_fold(build_hairpin(GUIA_REF))
        self.assertIs(resultado.state, FilterState.PASS)
        self.assertIn("(", resultado.reason)

    def test_una_secuencia_no_ARN_aborta(self):
        from shmir_design.errors import InvalidSequenceError

        with self.assertRaises(InvalidSequenceError):
            dot_bracket("ACGTX")


class TestSinViennaRNA(unittest.TestCase):
    """El nucleo no depende de ViennaRNA: sin ella, NOT_RUN y se dice."""

    def test_check_fold_sin_modelo_es_not_run(self):
        resultado = check_fold(build_hairpin(GUIA_REF), available=False)
        self.assertIs(resultado.state, FilterState.NOT_RUN)
        self.assertIn("ViennaRNA", resultado.reason)
        self.assertIn("NOT_RUN no es PASS", resultado.reason)

    def test_dot_bracket_sin_vienna_aborta_con_instrucciones(self):
        from shmir_design.folding import FoldingUnavailableError, _fold_with

        with self.assertRaises(FoldingUnavailableError) as ctx:
            _fold_with(None, "ACGU")
        self.assertIn("pip install ViennaRNA", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
