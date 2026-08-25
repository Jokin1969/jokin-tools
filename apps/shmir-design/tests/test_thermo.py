"""Tests del proxy de asimetria termodinamica (paso 7).

Regla 5: escritos antes que `shmir_design/thermo.py`.

Datos reales: la tabla de Turner 2004 (ARN, 37 C) y los valores esperados de las 5
ventanas del bloque conservado, verificados por el responsable del proyecto despues de
corregir un error de signo en la especificacion original.
"""

import unittest

from shmir_design.errors import InvalidSequenceError
from shmir_design.hard_filters import guide_from_target
from shmir_design.thermo import AU_END_PENALTY, NN_STEPS, tetramer_dg, turner_asymmetry

BLOCK = "TTTTCTATATTTGTAACTTTGCATGT"
ESPERADO = {0: -2.60, 1: -2.98, 2: -1.55, 3: 0.77, 4: -0.60}


class TestTabla(unittest.TestCase):

    def test_los_16_pasos(self):
        self.assertEqual(len(NN_STEPS), 16)

    def test_pasos_complementarios_valen_lo_mismo(self):
        for paso, complementario in (
            ("AA", "UU"), ("CU", "AG"), ("CA", "UG"),
            ("GU", "AC"), ("GA", "UC"), ("GG", "CC"),
        ):
            with self.subTest(paso):
                self.assertEqual(NN_STEPS[paso], NN_STEPS[complementario])

    def test_la_penalizacion_terminal_AU(self):
        self.assertAlmostEqual(AU_END_PENALTY, 0.45)


class TestTetramero(unittest.TestCase):

    def test_extremo_5_de_la_guia_del_offset_1(self):
        # UGCA: UG + GC + CA = -7.64; U y A terminales: +0.45 cada una.
        self.assertAlmostEqual(tetramer_dg("UGCA"), -6.74, places=2)

    def test_extremo_3_de_la_guia_del_offset_1(self):
        # GAAA: GA + AA + AA = -4.21; solo la A final penaliza.
        self.assertAlmostEqual(tetramer_dg("GAAA"), -3.76, places=2)

    def test_la_penalizacion_se_aplica_a_los_dos_extremos(self):
        sin_penalizacion = tetramer_dg("GGCC")
        self.assertAlmostEqual(sin_penalizacion, -9.94, places=2)

    def test_longitud_distinta_de_4_es_error(self):
        with self.assertRaises(ValueError):
            tetramer_dg("UGC")

    def test_una_base_desconocida_no_se_ignora(self):
        with self.assertRaises(InvalidSequenceError):
            tetramer_dg("UGNA")


class TestAsimetria(unittest.TestCase):

    def test_las_cinco_ventanas_del_bloque_conservado(self):
        for offset, esperado in ESPERADO.items():
            with self.subTest(offset=offset):
                guia = guide_from_target(BLOCK[offset : offset + 22])
                self.assertAlmostEqual(turner_asymmetry(guia), esperado, places=2)

    def test_el_mejor_es_el_offset_3(self):
        valores = {
            offset: turner_asymmetry(guide_from_target(BLOCK[offset : offset + 22]))
            for offset in range(5)
        }
        self.assertEqual(max(valores, key=valores.get), 3)

    def test_una_guia_de_ADN_se_rechaza(self):
        with self.assertRaises(InvalidSequenceError):
            turner_asymmetry("TGCAAAGTTACAAATATAGAAA")

    def test_una_guia_demasiado_corta_es_error(self):
        with self.assertRaises(ValueError):
            turner_asymmetry("UGCAAAG")


class TestCorduraBiologica(unittest.TestCase):
    """Un error de signo es un fallo de ESPECIFICACION, no de implementacion:
    ningun test de consistencia interna lo detecta. Estos dos si.

    Si estos dos signos se invierten, el pipeline selecciona sistematicamente las
    guias que cargan la hebra pasajera.
    """

    def test_extremo_5_AU_rico_y_3_GC_rico_da_asimetria_positiva(self):
        self.assertGreater(turner_asymmetry("UUUAGUACUGGAUGGAACGGCC"), 0)

    def test_extremo_5_GC_rico_y_3_AU_rico_da_asimetria_negativa(self):
        self.assertAlmostEqual(turner_asymmetry("UGCAAAGUUACAAAUAUAGAAA"), -2.98, places=2)

    def test_positivo_significa_extremo_5_menos_estable(self):
        """El extremo 5' de la guia debe estar MENOS establemente apareado."""
        au_rico = "UUUAGUACUGGAUGGAACGGCC"
        self.assertGreater(tetramer_dg(au_rico[:4]), tetramer_dg(au_rico[-4:]))


if __name__ == "__main__":
    unittest.main()
