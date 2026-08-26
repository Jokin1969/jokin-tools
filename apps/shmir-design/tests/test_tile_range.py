"""Tests de la ventana de tilado explicita (bloque 8).

Regla 5: escritos antes de implementarla.

`--cds` fija la anatomia pero no dice DONDE buscar. Los casos reales que hay que poder
pedir: la cobertura proximal del 3'UTR (1-400, por si el APA murino resulta funcional),
el bloque conservado raton/humano, o un tramo concreto del ORF.

Datos reales: NM_011170.3 — 2191 nt, CDS 185-949, 3'UTR 950-2191 (1242 nt).
"""

import unittest

from shmir_design.anatomy import Anatomy, Region, RegionSource, TileRange

RATON = Anatomy.from_cds(cds=(185, 949), length=2191)
SOLO_UTR3 = Anatomy.whole_is_utr3(1242, source=RegionSource.TODO_3UTR_DECLARADO)


class TestCoordenadasDeTranscrito(unittest.TestCase):

    def test_un_rango_explicito_se_respeta(self):
        r = TileRange.resolve(RATON, start=950, end=1349)
        self.assertEqual((r.start, r.end), (950, 1349))

    def test_sin_rango_se_tila_el_transcrito_entero(self):
        r = TileRange.resolve(RATON)
        self.assertEqual((r.start, r.end), (1, 2191))

    def test_solo_el_inicio_llega_hasta_el_final(self):
        r = TileRange.resolve(RATON, start=950)
        self.assertEqual((r.start, r.end), (950, 2191))

    def test_solo_el_final_empieza_en_uno(self):
        r = TileRange.resolve(RATON, end=949)
        self.assertEqual((r.start, r.end), (1, 949))


class TestCoordenadasDe3UTR(unittest.TestCase):
    """La cobertura proximal se pide en coordenadas de 3'UTR, que es como se piensa."""

    def test_1_400_del_3utr_son_950_1349_del_transcrito(self):
        r = TileRange.resolve(RATON, start=1, end=400, coords="3utr")
        self.assertEqual((r.start, r.end), (950, 1349))

    def test_guarda_lo_que_se_declaro_para_poder_imprimirlo(self):
        r = TileRange.resolve(RATON, start=1, end=400, coords="3utr")
        self.assertEqual((r.declared_start, r.declared_end), (1, 400))
        self.assertEqual(r.declared_as, "3utr")

    def test_el_3utr_entero_en_sus_propias_coordenadas(self):
        r = TileRange.resolve(RATON, start=1, end=1242, coords="3utr")
        self.assertEqual((r.start, r.end), (950, 2191))

    def test_pasarse_del_3utr_aborta(self):
        with self.assertRaises(ValueError) as ctx:
            TileRange.resolve(RATON, start=1, end=1243, coords="3utr")
        self.assertIn("1242", str(ctx.exception))

    def test_sobre_una_secuencia_que_ya_es_3utr_las_dos_coinciden(self):
        a = TileRange.resolve(SOLO_UTR3, start=1, end=400, coords="3utr")
        b = TileRange.resolve(SOLO_UTR3, start=1, end=400)
        self.assertEqual((a.start, a.end), (b.start, b.end))


class TestLoQueAborta(unittest.TestCase):

    def test_un_rango_invertido_aborta(self):
        with self.assertRaises(ValueError):
            TileRange.resolve(RATON, start=1349, end=950)

    def test_salirse_del_transcrito_aborta(self):
        with self.assertRaises(ValueError) as ctx:
            TileRange.resolve(RATON, start=1, end=99999)
        self.assertIn("2191", str(ctx.exception))

    def test_una_posicion_cero_aborta(self):
        with self.assertRaises(ValueError):
            TileRange.resolve(RATON, start=0, end=100)

    def test_un_rango_mas_corto_que_la_ventana_aborta(self):
        with self.assertRaises(ValueError) as ctx:
            TileRange.resolve(RATON, start=950, end=960, window_size=22)
        self.assertIn("22", str(ctx.exception))

    def test_coordenadas_de_3utr_sin_3utr_declarado_no_es_un_problema(self):
        """Sobre `whole_is_utr3` la conversion es la identidad, no un error."""
        TileRange.resolve(SOLO_UTR3, start=1, end=100, coords="3utr")

    def test_un_sistema_de_coordenadas_desconocido_aborta(self):
        with self.assertRaises(ValueError):
            TileRange.resolve(RATON, start=1, end=100, coords="genomicas")


class TestQueVentanasEntran(unittest.TestCase):

    def test_una_ventana_entera_dentro_entra(self):
        r = TileRange.resolve(RATON, start=950, end=1349)
        self.assertTrue(r.contains_window(950, 971))
        self.assertTrue(r.contains_window(1328, 1349))

    def test_una_ventana_que_sobresale_no_entra(self):
        r = TileRange.resolve(RATON, start=950, end=1349)
        self.assertFalse(r.contains_window(949, 970))
        self.assertFalse(r.contains_window(1329, 1350))

    def test_el_numero_de_ventanas_del_3utr_proximal(self):
        r = TileRange.resolve(RATON, start=1, end=400, coords="3utr")
        cuantas = sum(
            1 for s in range(1, 2191 - 22 + 2) if r.contains_window(s, s + 21)
        )
        self.assertEqual(cuantas, 400 - 22 + 1)

    def test_el_transcrito_entero_da_el_recuento_de_siempre(self):
        r = TileRange.resolve(RATON)
        cuantas = sum(
            1 for s in range(1, 2191 - 22 + 2) if r.contains_window(s, s + 21)
        )
        self.assertEqual(cuantas, 2170)


class TestRegionesCubiertas(unittest.TestCase):
    """El informe tiene que decir siempre que tramos toca el rango tilado."""

    def test_el_3utr_proximal_solo_cubre_3utr(self):
        r = TileRange.resolve(RATON, start=1, end=400, coords="3utr")
        self.assertEqual(r.regions_covered(RATON), (Region.UTR3,))

    def test_un_tramo_del_ORF_solo_cubre_CDS(self):
        r = TileRange.resolve(RATON, start=300, end=600)
        self.assertEqual(r.regions_covered(RATON), (Region.CDS,))

    def test_el_transcrito_entero_cubre_los_tres(self):
        r = TileRange.resolve(RATON)
        self.assertEqual(
            r.regions_covered(RATON), (Region.UTR5, Region.CDS, Region.UTR3)
        )

    def test_un_rango_a_caballo_cubre_los_dos(self):
        r = TileRange.resolve(RATON, start=900, end=1000)
        self.assertEqual(r.regions_covered(RATON), (Region.CDS, Region.UTR3))

    def test_el_texto_del_informe_lleva_las_dos_coordenadas(self):
        texto = TileRange.resolve(RATON, start=1, end=400, coords="3utr").describe(RATON)
        self.assertIn("950", texto)
        self.assertIn("1349", texto)
        self.assertIn("1-400", texto)
        self.assertIn("3'UTR", texto)

    def test_el_texto_dice_cuando_se_tilo_todo(self):
        self.assertIn("completo", TileRange.resolve(RATON).describe(RATON))


if __name__ == "__main__":
    unittest.main()
