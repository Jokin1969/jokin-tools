"""Tests del andamio miR-E (montaje de la horquilla de 97 nt).

Regla 5: escritos antes que `shmir_design/scaffold.py`.

Datos reales: el andamio SGEP (Addgene #111170), verificado por el responsable contra el
fichero SnapGene de la secuencia depositada y coincidente con tres fuentes. La horquilla
de referencia y sus 97 nt son dato verificado.

La regla de la pasajera (transicion en la posicion 1) esta derivada de UN SOLO ejemplo:
`scaffold.py` la marca como REGLA_NO_CONFIRMADA y estos tests fijan que el aviso salga
siempre, tambien en la salida de oligos.
"""

import unittest

from shmir_design.errors import InvalidSequenceError
from shmir_design.scaffold import (
    EXTENDED_FLANKS_STATUS,
    PASSENGER_RULE_CONFIRMED,
    PASSENGER_RULE_TAG,
    SCAFFOLD,
    build_hairpin,
    extended_cassette,
    passenger_from_guide,
)

GUIA_REF = "TAGATAAGCATTATAATTCCTA"
PASAJERA_REF = "CAGGAATTATAATGCTTATCTA"
HORQUILLA_REF = (
    "TGCTGTTGACAGTGAGCG"
    "CAGGAATTATAATGCTTATCTA"
    "TAGTGAAGCCACAGATGTA"
    "TAGATAAGCATTATAATTCCTA"
    "TGCCTACTGCCTCGGA"
)


class TestAndamio(unittest.TestCase):

    def test_las_tres_piezas_verificadas(self):
        self.assertEqual(SCAFFOLD["flank5"], "TGCTGTTGACAGTGAGCG")
        self.assertEqual(SCAFFOLD["loop"], "TAGTGAAGCCACAGATGTA")
        self.assertEqual(SCAFFOLD["flank3"], "TGCCTACTGCCTCGGA")

    def test_longitudes(self):
        self.assertEqual(len(SCAFFOLD["flank5"]), 18)
        self.assertEqual(len(SCAFFOLD["loop"]), 19)
        self.assertEqual(len(SCAFFOLD["flank3"]), 16)
        self.assertEqual(SCAFFOLD["length"], 97)

    def test_la_guia_va_en_el_brazo_3p(self):
        self.assertEqual(SCAFFOLD["guide_arm"], "3p")

    def test_el_97_mero_esta_verificado(self):
        self.assertIs(SCAFFOLD["verified"], True)
        self.assertIn("111170", SCAFFOLD["source"])

    def test_el_andamio_no_se_puede_modificar_por_accidente(self):
        with self.assertRaises(TypeError):
            SCAFFOLD["loop"] = "otra cosa"


class TestPasajera(unittest.TestCase):

    def test_la_pasajera_de_referencia(self):
        pasajera = passenger_from_guide(GUIA_REF)
        self.assertEqual(pasajera.sequence, PASAJERA_REF)

    def test_solo_cambia_la_posicion_1(self):
        pasajera = passenger_from_guide(GUIA_REF)
        self.assertEqual(pasajera.sequence[1:], pasajera.reverse_complement[1:])
        self.assertNotEqual(pasajera.sequence[0], pasajera.reverse_complement[0])

    def test_transicion_T_a_C(self):
        pasajera = passenger_from_guide(GUIA_REF)
        self.assertEqual((pasajera.base_original, pasajera.base_final), ("T", "C"))
        self.assertTrue(pasajera.transition_applied)

    def test_transicion_C_a_T(self):
        """Una guia acabada en G da un revcomp que empieza por C."""
        guia = "TAGATAAGCATTATAATTCCTG"
        pasajera = passenger_from_guide(guia)
        self.assertEqual(pasajera.reverse_complement[0], "C")
        self.assertEqual(pasajera.sequence[0], "T")
        self.assertTrue(pasajera.transition_applied)

    def test_si_es_A_no_se_toca_pero_se_avisa(self):
        guia = "TAGATAAGCATTATAATTCCTT"   # revcomp empieza por A
        pasajera = passenger_from_guide(guia)
        self.assertEqual(pasajera.reverse_complement[0], "A")
        self.assertEqual(pasajera.sequence, pasajera.reverse_complement)
        self.assertFalse(pasajera.transition_applied)
        self.assertTrue(any("A" in w and "transicion" in w.lower() for w in pasajera.warnings))

    def test_si_es_G_no_se_toca_pero_se_avisa(self):
        guia = "TAGATAAGCATTATAATTCCTC"   # revcomp empieza por G
        pasajera = passenger_from_guide(guia)
        self.assertEqual(pasajera.reverse_complement[0], "G")
        self.assertFalse(pasajera.transition_applied)
        self.assertTrue(pasajera.warnings)

    def test_la_regla_va_marcada_como_no_confirmada(self):
        self.assertFalse(PASSENGER_RULE_CONFIRMED)
        self.assertEqual(PASSENGER_RULE_TAG, "REGLA_NO_CONFIRMADA")
        avisos = " ".join(passenger_from_guide(GUIA_REF).warnings)
        self.assertIn(PASSENGER_RULE_TAG, avisos)
        self.assertIn("111177", avisos)

    def test_acepta_la_guia_en_ARN(self):
        rna = GUIA_REF.replace("T", "U")
        self.assertEqual(passenger_from_guide(rna).sequence, PASAJERA_REF)

    def test_una_guia_de_otra_longitud_es_error(self):
        with self.assertRaises(ValueError):
            passenger_from_guide(GUIA_REF[:21])

    def test_una_guia_con_N_es_error(self):
        with self.assertRaises(InvalidSequenceError):
            passenger_from_guide("N" + GUIA_REF[1:])


class TestHorquilla(unittest.TestCase):

    def test_la_horquilla_de_referencia(self):
        hairpin = build_hairpin(GUIA_REF)
        self.assertEqual(hairpin.sequence, HORQUILLA_REF)
        self.assertEqual(len(hairpin.sequence), 97)

    def test_las_piezas_caen_donde_toca(self):
        hairpin = build_hairpin(GUIA_REF)
        self.assertTrue(hairpin.sequence.startswith(SCAFFOLD["flank5"]))
        self.assertTrue(hairpin.sequence.endswith(SCAFFOLD["flank3"]))
        self.assertEqual(hairpin.sequence[18:40], PASAJERA_REF)
        self.assertEqual(hairpin.sequence[40:59], SCAFFOLD["loop"])
        self.assertEqual(hairpin.sequence[59:81], GUIA_REF)

    def test_la_salida_de_oligos_lleva_el_aviso(self):
        texto = build_hairpin(GUIA_REF).format_text()
        self.assertIn(PASSENGER_RULE_TAG, texto)
        self.assertIn("111177", texto)
        self.assertIn(HORQUILLA_REF, texto)

    def test_la_salida_dice_que_pieza_es_cada_cosa(self):
        texto = build_hairpin(GUIA_REF).format_text()
        for pieza in ("flanco 5'", "pasajera", "loop", "guia", "flanco 3'"):
            with self.subTest(pieza):
                self.assertIn(pieza, texto)

    def test_una_guia_con_N_no_se_convierte_en_oligo(self):
        with self.assertRaises(InvalidSequenceError):
            build_hairpin("N" + GUIA_REF[1:])


class TestFlancosExtendidos(unittest.TestCase):
    """Los flancos del pri-miR para el cassette AAV siguen sin decidir."""

    def test_el_estado_lo_dice(self):
        self.assertIn("sin decidir", EXTENDED_FLANKS_STATUS.lower())

    def test_pedirlos_aborta_en_vez_de_inventarlos(self):
        with self.assertRaises(NotImplementedError) as ctx:
            extended_cassette(GUIA_REF)
        self.assertIn("sin decidir", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
