"""Tests de la anatomia del transcrito (paso 1).

Regla 5: escritos antes que `shmir_design/anatomy.py`.

Datos reales: NM_000311.5 — 5'UTR 1-67, CDS 68-829, 3'UTR 830-2435 (2435 nt).
"""

import unittest

from shmir_design.anatomy import Anatomy, Region

HUMANO = dict(length=2435, cds=(68, 829))


class TestConstruccion(unittest.TestCase):

    def test_desde_el_CDS_salen_los_tres_tramos(self):
        a = Anatomy.from_cds(cds=(68, 829), length=2435)
        self.assertEqual(a.utr5, (1, 67))
        self.assertEqual(a.cds, (68, 829))
        self.assertEqual(a.utr3, (830, 2435))
        self.assertEqual(a.utr3_length, 1606)

    def test_todo_es_3utr(self):
        a = Anatomy.whole_is_utr3(1606)
        self.assertIsNone(a.utr5)
        self.assertIsNone(a.cds)
        self.assertEqual(a.utr3, (1, 1606))
        self.assertEqual(a.utr3_length, 1606)

    def test_un_CDS_que_no_es_multiplo_de_3_avisa_pero_no_aborta(self):
        a = Anatomy.from_cds(cds=(68, 830), length=2435)
        self.assertTrue(any("multiplo de 3" in w for w in a.warnings))

    def test_un_CDS_fuera_del_transcrito_aborta(self):
        with self.assertRaises(ValueError):
            Anatomy.from_cds(cds=(68, 3000), length=2435)

    def test_un_CDS_invertido_aborta(self):
        with self.assertRaises(ValueError):
            Anatomy.from_cds(cds=(829, 68), length=2435)

    def test_sin_3utr_aborta(self):
        with self.assertRaises(ValueError):
            Anatomy.from_cds(cds=(68, 2435), length=2435)


class TestRegiones(unittest.TestCase):

    def anatomia(self):
        return Anatomy.from_cds(**HUMANO)

    def test_cada_posicion_cae_donde_toca(self):
        a = self.anatomia()
        self.assertIs(a.region_of(1), Region.UTR5)
        self.assertIs(a.region_of(67), Region.UTR5)
        self.assertIs(a.region_of(68), Region.CDS)
        self.assertIs(a.region_of(829), Region.CDS)
        self.assertIs(a.region_of(830), Region.UTR3)
        self.assertIs(a.region_of(2435), Region.UTR3)

    def test_una_posicion_fuera_del_transcrito_aborta(self):
        with self.assertRaises(ValueError):
            self.anatomia().region_of(2436)

    def test_la_coordenada_en_el_3utr(self):
        a = self.anatomia()
        self.assertEqual(a.utr3_position(830), 1)
        self.assertEqual(a.utr3_position(2435), 1606)
        # La ventana 1237 del 3'UTR humano esta en 2066 del transcrito.
        self.assertEqual(a.utr3_position(2066), 1237)
        self.assertEqual(a.transcript_position(1237), 2066)

    def test_fuera_del_3utr_no_hay_coordenada_de_3utr(self):
        self.assertIsNone(self.anatomia().utr3_position(100))

    def test_una_ventana_a_caballo_se_marca(self):
        a = self.anatomia()
        self.assertTrue(a.crosses_boundary(820, 841))
        self.assertFalse(a.crosses_boundary(830, 851))


class TestTercios(unittest.TestCase):
    """Los tercios se calculan sobre el 3'UTR, no sobre el transcrito entero."""

    def test_los_limites_caen_dentro_del_3utr(self):
        a = Anatomy.from_cds(**HUMANO)
        self.assertIs(a.tercio_of(830, 851), None if False else a.tercio_of(830, 851))
        self.assertEqual(a.tercio_of(830, 851).value, "proximal")
        self.assertEqual(a.tercio_of(2414, 2435).value, "distal")

    def test_una_ventana_del_CDS_no_tiene_tercio(self):
        self.assertIsNone(Anatomy.from_cds(**HUMANO).tercio_of(100, 121))

    def test_con_todo_3utr_los_tercios_son_los_de_siempre(self):
        a = Anatomy.whole_is_utr3(1242)
        self.assertEqual(a.tercio_of(288, 309).value, "proximal")
        self.assertEqual(a.tercio_of(1214, 1235).value, "distal")


if __name__ == "__main__":
    unittest.main()
