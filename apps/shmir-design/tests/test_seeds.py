"""Tests del filtro de seeds (paso 10). Regla 5: escritos antes que `seeds.py`.

La lista de 12 seeds es un ARRANQUE para probar la mecanica, no un filtro real: el
filtro real necesita `mature.fa` de miRBase completo. Los tests fijan que el codigo lo
diga y que la lista se marque como tal.

Dato real: la ventana humana en 1237 (diana GTTATTATTGGCTTGCACTTTG, guia
UAAAGUGCAAGCCAAUAAUAAC) lleva la seed AAAGTGC de la familia miR-17/20/93/106.
"""

import unittest

from shmir_design.errors import InvalidSequenceError
from shmir_design.filters import FilterState
from shmir_design.seeds import (
    BOOTSTRAP_SEEDS,
    filter_seed,
    BOOTSTRAP_SEED_TABLE,
    SEED_END,
    SEED_START,
    SeedSet,
    parse_seed_table,
    seed_of,
)

GUIA_1237 = "UAAAGUGCAAGCCAAUAAUAAC"


class TestSeedDeLaGuia(unittest.TestCase):

    def test_posiciones_2_a_8(self):
        self.assertEqual((SEED_START, SEED_END), (2, 8))

    def test_seed_de_la_ventana_humana_1237(self):
        self.assertEqual(seed_of(GUIA_1237), "AAAGTGC")

    def test_la_seed_sale_en_notacion_ADN(self):
        self.assertNotIn("U", seed_of(GUIA_1237))

    def test_una_guia_demasiado_corta_es_error(self):
        with self.assertRaises(ValueError):
            seed_of("UAAAG")

    def test_una_guia_de_ADN_se_rechaza(self):
        with self.assertRaises(InvalidSequenceError):
            seed_of("TAAAGTGCAAGCCAATAATAAC")


class TestListaDeArranque(unittest.TestCase):

    def test_son_doce(self):
        self.assertEqual(len(BOOTSTRAP_SEEDS.seeds), 12)

    def test_contiene_las_familias_declaradas(self):
        self.assertEqual(BOOTSTRAP_SEEDS.seeds["AAAGTGC"], "miR-17/20/93/106")
        self.assertEqual(BOOTSTRAP_SEEDS.seeds["GAGGTAG"], "let-7")
        self.assertEqual(BOOTSTRAP_SEEDS.seeds["AAGGCAC"], "miR-124-3p")

    def test_esta_marcada_como_arranque_y_no_como_filtro_real(self):
        self.assertTrue(BOOTSTRAP_SEEDS.is_bootstrap)
        fuente = BOOTSTRAP_SEEDS.source.lower()
        self.assertIn("arranque", fuente)
        self.assertIn("mature.fa", fuente)

    def test_se_carga_como_si_viniera_de_un_fichero(self):
        cargada = parse_seed_table(BOOTSTRAP_SEED_TABLE, source="fichero de prueba")
        self.assertEqual(cargada.seeds, BOOTSTRAP_SEEDS.seeds)


class TestParseo(unittest.TestCase):

    def test_lineas_en_blanco_y_comentarios_se_ignoran(self):
        texto = "# comentario\n\nAAAGTGC miR-17/20/93/106\n"
        self.assertEqual(parse_seed_table(texto, source="x").seeds, {"AAAGTGC": "miR-17/20/93/106"})

    def test_una_linea_sin_familia_aborta(self):
        with self.assertRaises(ValueError) as ctx:
            parse_seed_table("AAAGTGC\n", source="x")
        self.assertIn("2", str(ctx.exception))

    def test_una_seed_que_no_mide_7_aborta(self):
        with self.assertRaises(ValueError):
            parse_seed_table("AAAGTG miR-x\n", source="x")

    def test_una_seed_con_bases_invalidas_aborta(self):
        with self.assertRaises(InvalidSequenceError):
            parse_seed_table("AAAGTGZ miR-x\n", source="x")

    def test_una_seed_repetida_con_otra_familia_aborta(self):
        texto = "AAAGTGC miR-17\nAAAGTGC otra-cosa\n"
        with self.assertRaises(ValueError) as ctx:
            parse_seed_table(texto, source="x")
        self.assertIn("AAAGTGC", str(ctx.exception))

    def test_un_fichero_vacio_aborta(self):
        with self.assertRaises(ValueError):
            parse_seed_table("\n\n", source="x")

    def test_una_seed_en_ARN_se_normaliza_a_ADN(self):
        self.assertIn("AAAGTGC", parse_seed_table("AAAGUGC miR-17\n", source="x").seeds)


class TestFiltroDeSeed(unittest.TestCase):

    def test_sin_lista_queda_en_not_run(self):
        self.assertIs(filter_seed(GUIA_1237).state, FilterState.NOT_RUN)

    def test_con_la_lista_de_arranque_la_1237_falla(self):
        resultado = filter_seed(GUIA_1237, BOOTSTRAP_SEEDS)
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("AAAGTGC", resultado.reason)
        self.assertIn("miR-17/20/93/106", resultado.reason)

    def test_el_motivo_avisa_de_que_la_lista_es_de_arranque(self):
        for guia in (GUIA_1237, "UAAAAAAAAAGCCAAUAAUAAC"):
            with self.subTest(guia):
                self.assertIn("arranque", filter_seed(guia, BOOTSTRAP_SEEDS).reason)

    def test_una_seed_que_no_esta_pasa(self):
        self.assertIs(
            filter_seed("UAAAAAAAAAGCCAAUAAUAAC", BOOTSTRAP_SEEDS).state,
            FilterState.PASS,
        )

    def test_una_N_dentro_de_la_seed_impide_compararla(self):
        resultado = filter_seed("UAANGUGCAAGCCAAUAAUAAC", BOOTSTRAP_SEEDS)
        self.assertIs(resultado.state, FilterState.NOT_RUN)
        self.assertIn("N", resultado.reason)

    def test_una_N_fuera_de_la_seed_no_impide_compararla(self):
        """La seed son las posiciones 2-8: lo de fuera no la determina."""
        resultado = filter_seed("UAAAGUGCAAGCCAAUAAUAAN", BOOTSTRAP_SEEDS)
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("AAAGTGC", resultado.reason)


class TestSeedSet(unittest.TestCase):

    def test_family_of_devuelve_la_familia_o_none(self):
        self.assertEqual(BOOTSTRAP_SEEDS.family_of("AAAGTGC"), "miR-17/20/93/106")
        self.assertIsNone(BOOTSTRAP_SEEDS.family_of("AAAAAAA"))

    def test_un_seedset_vacio_es_error(self):
        with self.assertRaises(ValueError):
            SeedSet(seeds={}, source="x", is_bootstrap=True)


if __name__ == "__main__":
    unittest.main()
