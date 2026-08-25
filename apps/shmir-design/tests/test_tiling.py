"""Tests del tiling y del contador de referencia (pasos 3 y 15).

Regla 5: escritos antes que `shmir_design/tiling.py`.

`biofisicos_ok` cuenta las ventanas que superan TODOS los filtros biofisicos —GC,
homopolimero, asimetria, G4 diana, G4 guia y zona prohibida de poliadenilacion— y solo
esos. No incluye la seed ni ningun filtro que dependa de un recurso externo, asi que es
comprobable sin miRBase y sin red. Es distinto del veredicto final: una ventana con
`biofisicos_ok=True` y la seed en NOT_RUN sigue siendo INCOMPLETE, nunca apta.

Los conteos sobre los 3'UTR reales estan al final y se saltan hasta que existan los
fixtures. Lo que si se comprueba hoy: la aritmetica del tiling, la agrupacion en sitios
y la ventana humana en 1237, que es un dato real verificado.
"""

import unittest

from shmir_design.filters import FilterState, Verdict
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.seeds import BOOTSTRAP_SEEDS
from shmir_design.tiling import (
    independent_sites,
    tile_positions,
    tile_utr,
)

MOUSE_UTR_LENGTH, HUMAN_UTR_LENGTH = 1242, 1606
DIANA_1237 = "GTTATTATTGGCTTGCACTTTG"


class TestAritmeticaDelTiling(unittest.TestCase):

    def test_un_3utr_de_1242_da_1221_ventanas(self):
        self.assertEqual(len(tile_positions(MOUSE_UTR_LENGTH)), 1221)

    def test_un_3utr_de_1606_da_1585_ventanas(self):
        self.assertEqual(len(tile_positions(HUMAN_UTR_LENGTH)), 1585)

    def test_las_posiciones_van_de_1_al_final(self):
        posiciones = tile_positions(MOUSE_UTR_LENGTH)
        self.assertEqual(posiciones[0], 1)
        self.assertEqual(posiciones[-1], MOUSE_UTR_LENGTH - 21)

    def test_un_3utr_mas_corto_que_la_ventana_no_da_ninguna(self):
        self.assertEqual(tile_positions(21), [])

    def test_longitud_invalida_es_error(self):
        with self.assertRaises(ValueError):
            tile_positions(0)


class TestSitiosIndependientes(unittest.TestCase):
    """Sitios = bloques de posiciones contiguas entre las que pasan."""

    def test_posiciones_contiguas_son_un_solo_sitio(self):
        self.assertEqual(independent_sites([10, 11, 12]), [(10, 12)])

    def test_un_hueco_separa_dos_sitios(self):
        self.assertEqual(independent_sites([10, 11, 20, 21]), [(10, 11), (20, 21)])

    def test_posiciones_sueltas(self):
        self.assertEqual(len(independent_sites([1, 5, 9])), 3)

    def test_sin_posiciones_no_hay_sitios(self):
        self.assertEqual(independent_sites([]), [])

    def test_el_orden_de_entrada_da_igual(self):
        self.assertEqual(independent_sites([21, 10, 20, 11]), [(10, 11), (20, 21)])

    def test_las_repetidas_no_inflan_el_conteo(self):
        self.assertEqual(independent_sites([10, 10, 11]), [(10, 11)])


class TestVentanaHumana1237(unittest.TestCase):
    """Dato real: pasa todos los biofisicos y solo cae por la seed."""

    def tiled(self, seeds=None):
        # Andamio de N con la diana real en su posicion real: la N no aporta GC ni
        # homopolimero, y ninguna ventana de N puede pasar los filtros.
        secuencia = "N" * 1236 + DIANA_1237 + "N" * (HUMAN_UTR_LENGTH - 1236 - 22)
        report = tile_utr(secuencia, seeds=seeds)
        return next(w for w in report.windows if w.window.start == 1237)

    def test_pasa_todos_los_biofisicos(self):
        self.assertTrue(self.tiled().biofisicos_ok)

    def test_sin_seeds_el_veredicto_es_incompleto_no_apto(self):
        ventana = self.tiled()
        self.assertIs(ventana.filter("seed").state, FilterState.NOT_RUN)
        self.assertIs(ventana.verdict, Verdict.INCOMPLETE)

    def test_con_la_lista_de_arranque_cae_por_la_seed(self):
        ventana = self.tiled(seeds=BOOTSTRAP_SEEDS)
        seed = ventana.filter("seed")
        self.assertIs(seed.state, FilterState.FAIL)
        self.assertIn("AAAGTGC", seed.reason)
        self.assertIn("miR-17/20/93/106", seed.reason)

    def test_la_seed_no_cuenta_como_biofisico(self):
        """Cae por la seed pero los biofisicos siguen en verde: son contadores distintos."""
        ventana = self.tiled(seeds=BOOTSTRAP_SEEDS)
        self.assertTrue(ventana.biofisicos_ok)
        self.assertIs(ventana.verdict, Verdict.FAIL)


class TestInforme(unittest.TestCase):

    def report(self):
        return tile_utr("N" * 1236 + DIANA_1237 + "N" * 348)

    def test_cuenta_todas_las_ventanas(self):
        self.assertEqual(len(self.report().windows), 1585)

    def test_el_contador_biofisico_es_distinto_del_de_aptas(self):
        report = self.report()
        self.assertEqual(report.biofisicos_ok(), 1)
        self.assertEqual(report.aptas(), 0)  # la seed en NOT_RUN lo impide

    def test_el_tsv_lleva_una_fila_por_ventana(self):
        lineas = self.report().format_tsv().splitlines()
        self.assertEqual(len(lineas), 1586)
        self.assertIn("biofisicos_ok", lineas[0])
        self.assertIn("seed", lineas[0])

    def test_el_texto_cuenta_en_cuantas_ventanas_no_corrio_cada_filtro(self):
        """El resumen mira todas las ventanas, no la primera."""
        texto = self.report().format_text()
        self.assertIn("seed: NOT_RUN en 1585/1585", texto)  # sin lista cargada
        self.assertIn("GC: NOT_RUN en 1584/1585", texto)

    def test_con_seeds_la_N_solo_bloquea_si_cae_dentro_de_la_seed(self):
        """La seed son las posiciones 2-8 de la guia, o sea 15-21 de la diana: hay 16
        ventanas cuyo tramo 15-21 cae entero dentro de la diana real, y en esas la seed
        SI se puede comparar aunque el resto de la ventana sea desconocido."""
        texto = tile_utr(
            "N" * 1236 + DIANA_1237 + "N" * 348, seeds=BOOTSTRAP_SEEDS
        ).format_text()
        self.assertIn("seed: NOT_RUN en 1569/1585", texto)

    def test_el_texto_avisa_de_que_la_lista_de_arranque_no_es_un_filtro_real(self):
        texto = tile_utr(
            "N" * 1236 + DIANA_1237 + "N" * 348, seeds=BOOTSTRAP_SEEDS
        ).format_text()
        self.assertIn("arranque", texto.lower())


@unittest.skipUnless(
    all(fixture_available(ref) for ref in REFERENCES.values()),
    "NOT_RUN: faltan los fixtures de data/reference/; sin ellos los conteos de "
    "referencia no se pueden comprobar y no se inventan (regla 1)",
)
class TestConteosDeReferencia(unittest.TestCase):
    """Contadores sobre los 3'UTR reales, verificados por el responsable."""

    def raton(self, seeds=None):
        return tile_utr(load_3utr(REFERENCES["NM_011170.3"]), seeds=seeds)

    def humano(self, seeds=None):
        return tile_utr(load_3utr(REFERENCES["NM_000311.5"]), seeds=seeds)

    def test_raton_solo_biofisicos(self):
        report = self.raton()
        self.assertEqual(len(report.windows), 1221)
        self.assertEqual(report.biofisicos_ok(), 302)
        self.assertEqual(len(report.sites_biofisicos()), 96)

    def test_humano_solo_biofisicos(self):
        report = self.humano()
        self.assertEqual(len(report.windows), 1585)
        self.assertEqual(report.biofisicos_ok(), 323)
        self.assertEqual(len(report.sites_biofisicos()), 97)

    def test_el_raton_no_cambia_con_la_lista_de_arranque(self):
        report = self.raton(seeds=BOOTSTRAP_SEEDS)
        self.assertEqual(report.aptas(), 302)
        self.assertEqual(len(report.sites_aptas()), 96)

    def test_el_humano_pierde_exactamente_una_ventana(self):
        sin_seeds = self.humano()
        con_seeds = self.humano(seeds=BOOTSTRAP_SEEDS)
        self.assertEqual(con_seeds.aptas(), 322)
        self.assertEqual(len(con_seeds.sites_aptas()), 96)
        self.assertEqual(sin_seeds.biofisicos_ok() - con_seeds.aptas(), 1)

    def test_la_ventana_que_cae_es_la_de_1237(self):
        report = self.humano(seeds=BOOTSTRAP_SEEDS)
        caidas = [
            w for w in report.windows
            if w.biofisicos_ok and w.filter("seed").state is FilterState.FAIL
        ]
        self.assertEqual([w.window.start for w in caidas], [1237])
        self.assertEqual(caidas[0].evaluation.sequence, DIANA_1237)


if __name__ == "__main__":
    unittest.main()
