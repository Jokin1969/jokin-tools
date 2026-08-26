"""El control SIN INTRON: se especifica, no se pide.

Regla 5: escritos antes.

La lectura 3 del frente del empalme —parental sin intron como techo de expresion— no
existe sin la construccion. Aqui se emite su SECUENCIA EXACTA: el casete con el donante
y el aceptor eliminados y todo lo demas conservado.

No es generar secuencia (regla 1): es BORRAR dos piezas literales de una secuencia que
esta en el repositorio. Nada se rellena, nada se reconstruye, y el resultado se comprueba
contra el original base a base.
"""

import unittest
from pathlib import Path

from shmir_design import splicing
from shmir_design.blocks import PIECES
from shmir_design.errors import ShmirDesignError

CASETE = Path(__file__).resolve().parent.parent / "data" / "reference" / "aav_casete.fa"


def _plasmido() -> str:
    raw = CASETE.read_text(encoding="utf-8")
    return "".join(l.strip() for l in raw.splitlines() if not l.startswith(">")).upper()


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestElFragmento(unittest.TestCase):

    def setUp(self):
        self.control = splicing.intronless_control(_plasmido(), name="aav_casete.fa")

    def test_quita_EXACTAMENTE_el_intron_y_nada_mas(self):
        self.assertEqual(self.control.deleted, 82)
        self.assertEqual(
            self.control.deleted,
            len(PIECES["MVM5"].sequence) + len(PIECES["MVM3"].sequence),
        )

    def test_lo_borrado_son_las_DOS_piezas_literales(self):
        self.assertEqual(
            self.control.deleted_sequence,
            PIECES["MVM5"].sequence + PIECES["MVM3"].sequence,
        )

    def test_el_donante_y_el_aceptor_YA_NO_estan(self):
        self.assertNotIn(PIECES["MVM5"].sequence, self.control.sequence)
        self.assertNotIn(PIECES["MVM3"].sequence, self.control.sequence)

    def test_TODO_lo_demas_se_conserva_base_a_base(self):
        # El fragmento es exactamente el original con el intron cortado: se comprueba
        # reinsertando el trozo borrado y comparando con el plasmido.
        plasmido = _plasmido()
        corte = self.control.deletion_start - self.control.fragment_start
        rehecho = (
            self.control.sequence[:corte]
            + self.control.deleted_sequence
            + self.control.sequence[corte:]
        )
        original = plasmido[
            self.control.fragment_start - 1: self.control.fragment_end
        ]
        self.assertEqual(rehecho, original)

    def test_conserva_MluI_y_AgeI_para_la_digestion(self):
        self.assertEqual(self.control.sequence.count(PIECES["MluI"].sequence), 1)
        self.assertEqual(self.control.sequence.count(PIECES["AgeI"].sequence), 1)

    def test_conserva_los_DOS_exones(self):
        self.assertIn(
            PIECES["exon5"].sequence + PIECES["exon3"].sequence, self.control.sequence
        )

    def test_lleva_brazos_de_homologia_a_los_dos_lados(self):
        self.assertGreater(self.control.arm, 0)
        self.assertEqual(
            self.control.fragment_start,
            self.control.deletion_start - self.control.arm - len(PIECES["exon5"].sequence)
            - len(PIECES["MluI"].sequence),
        )

    def test_los_brazos_salen_del_PLASMIDO_no_de_ningun_sitio_mas(self):
        plasmido = _plasmido()
        self.assertIn(self.control.left_arm, plasmido)
        self.assertIn(self.control.right_arm, plasmido)

    def test_trae_longitud_y_md5_JUNTOS(self):
        texto = "\n".join(self.control.describe())
        self.assertIn(str(len(self.control.sequence)), texto)
        self.assertIn(self.control.md5[:8], texto)

    def test_dice_que_NO_lleva_donante_ni_aceptor_y_por_eso_es_el_TECHO(self):
        texto = "\n".join(self.control.describe()).lower()
        self.assertIn("techo", texto)
        self.assertIn("no hay empalme que medir", texto)

    def test_NO_se_emite_sobre_una_secuencia_sin_intron(self):
        with self.assertRaises(ShmirDesignError):
            splicing.intronless_control("ACGT" * 200, name="inventado")

    def test_el_donante_criptico_del_ANDAMIO_no_esta_aqui(self):
        # El parental no lleva modulo, asi que el GTGAGCG del flanco de miR-E tampoco.
        # Importa: el control tiene que ser un techo LIMPIO, sin ningun sitio de empalme.
        self.assertNotIn(splicing.CRYPTIC_DONOR, self.control.sequence)


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestSaleEnLaHojaDePedido(unittest.TestCase):

    def setUp(self):
        self.control = splicing.intronless_control(_plasmido(), name="aav_casete.fa")

    def test_la_hoja_lo_incluye_como_un_fragmento_mas(self):
        from shmir_design.blocks import order_sheet

        hoja = order_sheet([], species="raton", intronless=self.control)
        self.assertIn("SIN INTRON", hoja.upper())
        self.assertIn(self.control.sequence[:30], hoja)

    def test_y_avisa_de_para_que_es(self):
        from shmir_design.blocks import order_sheet

        hoja = order_sheet([], species="raton", intronless=self.control)
        self.assertIn("lectura 3", hoja.lower())

    def test_sin_control_la_hoja_sigue_saliendo_igual(self):
        from shmir_design.blocks import order_sheet

        self.assertNotIn("SIN INTRON", order_sheet([], species="raton").upper())


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestElAvisoDelCebadorVaEnNEGRITA(unittest.TestCase):
    """Es el error que arruinaria el ensayo sin dar ninguna señal."""

    def test_la_hoja_lo_lleva_destacado(self):
        from shmir_design.blocks import order_sheet

        plan = splicing.splice_rtpcr_plan(_plasmido(), name="aav_casete.fa")
        hoja = order_sheet([], species="raton", rtpcr=plan)
        self.assertIn("**", hoja)
        destacado = [l for l in hoja.splitlines() if "**" in l]
        self.assertTrue(destacado)
        junto = " ".join(destacado).lower()
        self.assertIn("aguas arriba", junto)
        self.assertIn("endogeno", junto)

    def test_dice_que_el_fallo_NO_da_señal(self):
        from shmir_design.blocks import order_sheet

        plan = splicing.splice_rtpcr_plan(_plasmido(), name="aav_casete.fa")
        hoja = order_sheet([], species="raton", rtpcr=plan)
        self.assertIn("sin dar ninguna señal", hoja.lower())


if __name__ == "__main__":
    unittest.main()
