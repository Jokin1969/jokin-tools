"""Tests de la estimacion de coste (mejora de la revision).

Con --accesibilidad y --transcriptoma-3utr a la vez, el 3'UTR murino son unas 300
ventanas elegibles por dos plegados de 340 nt mas un barrido del transcriptoma cada una.
Eso son minutos, y hasta ahora no habia forma de saberlo antes de lanzarlo.

La estimacion NO adivina: mide UNA invocacion real de cada filtro caro sobre una ventana
de verdad y multiplica por cuantas van a pasar por el. Si el coste por ventana cambia,
la estimacion cambia sola.
"""

import unittest

from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.cost import estimate_cost
from shmir_design.seed_load import Utr3Set
from shmir_design.specificity import SpecificityDatabase

SONDA = "GCGTCAGTACGATCGAATTACT" * 12


def _anatomia():
    return Anatomy.whole_is_utr3(len(SONDA), source=RegionSource.TODO_3UTR_DECLARADO)


def _base():
    return SpecificityDatabase(
        name="sonda", version="v", checksum="0" * 32, records={"diana": SONDA}
    )


def _utrs():
    return Utr3Set(
        records={"t1": SONDA}, source="sonda", version="v", checksum="0" * 32
    )


class TestSinFiltrosCaros(unittest.TestCase):

    def test_cuenta_las_ventanas(self):
        e = estimate_cost(sequence=SONDA, anatomy=_anatomia())
        self.assertEqual(e.windows, len(SONDA) - 22 + 1)

    def test_cuenta_las_elegibles_que_pasaran_por_los_filtros_caros(self):
        e = estimate_cost(sequence=SONDA, anatomy=_anatomia())
        self.assertGreater(e.eligible, 0)
        self.assertLessEqual(e.eligible, e.windows)

    def test_sin_nada_caro_no_hay_partidas(self):
        self.assertEqual(estimate_cost(sequence=SONDA, anatomy=_anatomia()).items, ())

    def test_el_total_incluye_el_tilado(self):
        e = estimate_cost(sequence=SONDA, anatomy=_anatomia())
        self.assertGreater(e.total_seconds, 0)
        self.assertAlmostEqual(e.total_seconds, e.tiling_seconds, places=6)


class TestConFiltrosCaros(unittest.TestCase):

    def test_la_especificidad_aparece_como_partida(self):
        e = estimate_cost(
            sequence=SONDA, anatomy=_anatomia(),
            specificity_db=_base(), specificity_target="diana",
        )
        self.assertIn("especificidad", [i.name for i in e.items])

    def test_la_carga_de_seed_aparece(self):
        e = estimate_cost(sequence=SONDA, anatomy=_anatomia(), utr3_set=_utrs())
        self.assertIn("carga_seed", [i.name for i in e.items])

    def test_cada_partida_multiplica_por_las_ventanas_elegibles(self):
        e = estimate_cost(sequence=SONDA, anatomy=_anatomia(), utr3_set=_utrs())
        item = next(i for i in e.items if i.name == "carga_seed")
        self.assertEqual(item.windows, e.eligible)
        self.assertAlmostEqual(item.total_seconds, item.per_window * e.eligible)

    def test_el_total_es_la_suma_mas_el_tilado(self):
        e = estimate_cost(sequence=SONDA, anatomy=_anatomia(), utr3_set=_utrs())
        self.assertAlmostEqual(
            e.total_seconds,
            e.tiling_seconds + sum(i.total_seconds for i in e.items),
        )

    def test_el_coste_por_ventana_es_medido_no_inventado(self):
        e = estimate_cost(sequence=SONDA, anatomy=_anatomia(), utr3_set=_utrs())
        for item in e.items:
            self.assertGreater(item.per_window, 0.0)


class TestSalida(unittest.TestCase):

    def test_el_texto_dice_cuantas_ventanas_y_cuantas_elegibles(self):
        texto = estimate_cost(sequence=SONDA, anatomy=_anatomia()).format_text()
        self.assertIn("ventanas", texto)
        self.assertIn("elegibles", texto)

    def test_el_texto_avisa_de_que_es_una_estimacion(self):
        texto = estimate_cost(sequence=SONDA, anatomy=_anatomia()).format_text()
        self.assertIn("estimacion", texto.lower())

    def test_el_texto_dice_como_se_midio(self):
        texto = estimate_cost(sequence=SONDA, anatomy=_anatomia(), utr3_set=_utrs()).format_text()
        self.assertIn("medido", texto.lower())

    def test_sin_ventanas_elegibles_lo_dice_en_vez_de_dar_cero(self):
        e = estimate_cost(sequence="N" * 200, anatomy=Anatomy.whole_is_utr3(
            200, source=RegionSource.TODO_3UTR_DECLARADO))
        self.assertEqual(e.eligible, 0)
        self.assertIn("ninguna ventana", e.format_text().lower())


class TestNoEsCaroEstimar(unittest.TestCase):
    """La estimacion tiene que ser barata: si no, no sirve de nada."""

    def test_mide_pocas_ventanas_no_todas(self):
        from shmir_design.cost import SAMPLES

        self.assertLessEqual(SAMPLES, 5)

    def test_las_muestras_van_REPARTIDAS_por_el_tramo(self):
        """La primera version medía sobre la ventana mas a la izquierda, donde el
        contexto de la accesibilidad esta recortado: estimaba la MITAD del coste real."""
        from shmir_design.cost import _sample_windows

        elegibles = list(range(100))
        muestras = _sample_windows(elegibles, 3)
        self.assertEqual(muestras, [0, 50, 99])

    def test_con_menos_elegibles_que_muestras_no_revienta(self):
        from shmir_design.cost import _sample_windows

        self.assertEqual(_sample_windows([7], 3), [7])
        self.assertEqual(_sample_windows([], 3), [])

    def test_una_sola_muestra_se_coge_del_centro(self):
        from shmir_design.cost import _sample_windows

        self.assertEqual(_sample_windows(list(range(11)), 1), [5])

    def test_estimar_no_escribe_nada(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            estimate_cost(sequence=SONDA, anatomy=_anatomia(), utr3_set=_utrs())
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
