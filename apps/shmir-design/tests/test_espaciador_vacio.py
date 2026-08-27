"""Un espaciador de longitud 0 es CERO nucleotidos, no el estandar.

Encontrado en la revision del PR #21. `Intron.with_module` resolvia el espaciador con
`spacer5 or PIECES["espaciador5"].sequence`: una cadena vacia es falsa, asi que pedir
«sin espaciador» devolvia silenciosamente los 20 nt estandar. El barrido de
`barrido.py` empieza la curva en 0, de modo que su punto 0 no media lo que decia medir
—media el estandar— y salia indistinguible del de referencia SIN que nada fallara.

La cadena vacia y «no me lo digas» son dos peticiones distintas y ahora se escriben
distinto: `""` es ninguno, `None` es el estandar.
"""

import unittest

from shmir_design import barrido, blocks, introns


class TestVacioNoEsEstandar(unittest.TestCase):
    def setUp(self):
        self.mvm = introns.INTRONS["mvm_actual"]
        self.modulo = "A" * blocks.MODULE_LENGTH

    def test_None_pone_el_estandar(self):
        montado = self.mvm.with_module(self.modulo)
        self.assertIn(blocks.PIECES["espaciador5"].sequence, montado)
        self.assertIn(blocks.PIECES["espaciador3"].sequence, montado)

    def test_cadena_vacia_no_pone_nada(self):
        montado = self.mvm.with_module(self.modulo, spacer5="", spacer3="")
        self.assertNotIn(blocks.PIECES["espaciador5"].sequence, montado)
        self.assertNotIn(blocks.PIECES["espaciador3"].sequence, montado)

    def test_y_la_diferencia_de_longitud_es_exactamente_los_dos_estandar(self):
        con = self.mvm.with_module(self.modulo)
        sin = self.mvm.with_module(self.modulo, spacer5="", spacer3="")
        self.assertEqual(
            len(con) - len(sin),
            len(blocks.PIECES["espaciador5"].sequence)
            + len(blocks.PIECES["espaciador3"].sequence),
        )


class TestElPuntoCeroDelBarrido(unittest.TestCase):
    def test_el_espaciador_de_longitud_cero_es_la_cadena_vacia(self):
        self.assertEqual(barrido._spacer(0), "")

    def test_y_el_punto_0_de_la_curva_inserta_0_nt_de_ese_lado(self):
        modulo = "A" * blocks.MODULE_LENGTH

        def medir(entrada, module, spacer5, spacer3):
            return dict.fromkeys(barrido.FRAGILE, 0.5)

        curva = barrido.sweep_side(
            "mvm_actual", side="5", lengths=(0,), other=45,
            module=modulo, medir=medir, replicas=1,
        )
        punto = curva.points[0]
        self.assertEqual(punto.total_inserted, len(modulo) + 0 + 45)


if __name__ == "__main__":
    unittest.main()
