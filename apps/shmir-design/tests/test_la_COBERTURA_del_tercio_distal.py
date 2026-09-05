"""Cuántos sitios elegibles hay por tercio, y cuál sería el siguiente.

Regla 5: escritos antes que `selection.tercio_coverage`.

## De qué va

El tercio distal del 3'UTR murino son 414 nt y el panel pone ahí UN candidato —
`3utr:1018`, que además es el penalizado por ACTAAA. Ese tramo depende de uno, y la
cuota se decidió POR TERCIOS: hay que poder ver si se cumple y con cuánto margen.

## Las dos definiciones no coinciden, y aquí muerde

`Tercio` etiqueta por el PUNTO MEDIO de la ventana; la partición del 3'UTR va por la
POSICIÓN DE INICIO. `3utr:819-840` empieza en el tercio medio (819 <= 828) y su punto
medio (829,5) cae en el distal. Con la definición que usa la CUOTA el panel tiene DOS
distales; con la otra, uno.

Ninguna de las dos es incorrecta y las dos se emiten, pero el «dos» es un artefacto del
borde: 819-840 se acaba en el nucleótido 840 de un tercio que llega al 1242. Contarlo
como cobertura distal sin decir dónde está es lo que hace que un tramo vacío parezca
cubierto.
"""

import unittest
from pathlib import Path

from shmir_design.selection import (
    DEFAULT_MIN_SPACING,
    select_from_report,
    tercio_coverage,
)

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"


def _tiling():
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.tiling import tile_utr

    return tile_utr(load_3utr(REFERENCES["NM_011170.3"]))


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaCoberturaPorTercios(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling = _tiling()
        cls.seleccion = select_from_report(cls.tiling)
        cls.cobertura = tercio_coverage(cls.tiling, cls.seleccion)
        cls.por_nombre = {c.tercio: c for c in cls.cobertura}

    def test_los_tres_tercios_salen_siempre(self):
        self.assertEqual(
            [c.tercio for c in self.cobertura], ["proximal", "medio", "distal"]
        )

    def test_los_limites_son_los_del_3utr(self):
        self.assertEqual(
            [c.bounds for c in self.cobertura], [(1, 414), (415, 828), (829, 1242)]
        )

    def test_sitios_elegibles_por_tercio_MEDIDOS(self):
        self.assertEqual(
            {c.tercio: c.sites_by_start for c in self.cobertura},
            {"proximal": 28, "medio": 42, "distal": 16},
        )

    def test_el_distal_tiene_UN_candidato_por_inicio_y_DOS_por_punto_medio(self):
        distal = self.por_nombre["distal"]
        self.assertEqual(distal.panel_by_start, (1018,))
        self.assertEqual(distal.panel_by_midpoint, (819, 1018))

    def test_la_cuota_se_cumple_y_se_dice_con_que_definicion(self):
        distal = self.por_nombre["distal"]
        self.assertEqual(distal.quota, 1)
        self.assertTrue(distal.quota_met)
        texto = "\n".join(distal.describe())
        self.assertIn("punto medio", texto)

    def test_el_dos_del_borde_se_marca_como_borde(self):
        """819-840 acaba en el nt 840 de un tercio que llega al 1242."""
        distal = self.por_nombre["distal"]
        self.assertEqual(distal.borderline, (819,))
        self.assertIn("819", "\n".join(distal.describe()))

    def test_el_siguiente_distal_con_espaciado(self):
        distal = self.por_nombre["distal"]
        self.assertEqual(distal.spacing, DEFAULT_MIN_SPACING)
        self.assertTrue(distal.next_free)
        self.assertEqual(distal.next_free[0].start, 1071)
        self.assertEqual(distal.next_free[0].end, 1092)
        # Todos los que se ofrecen respetan el espaciado con TODO el panel.
        elegidos = [c.start for c in self.seleccion.selection.chosen]
        for siguiente in distal.next_free:
            for start in elegidos:
                self.assertGreaterEqual(abs(siguiente.start - start), 50)

    def test_se_distingue_libre_de_1018_de_libre_del_panel_entero(self):
        distal = self.por_nombre["distal"]
        self.assertEqual(distal.free_of_reference, 13)
        self.assertEqual(distal.free_of_panel, 9)
        texto = "\n".join(distal.describe())
        self.assertIn("13", texto)
        self.assertIn("9", texto)

    def test_el_tercio_MEDIO_esta_saturado_y_tambien_se_dice(self):
        """MEDIDO: 41 sitios elegibles y CERO caben — todos a menos de 50 nt.

        Los cinco elegidos del tramo (449, 553, 652, 735, 819) dejan una franja de
        +/-50 nt que cubre casi los 414. No es lo mismo que el distal, donde quedan
        nueve: un tramo se lee lleno y el otro depende de uno. Los dos números salen del
        mismo sitio y por eso se pueden comparar.
        """
        medio = self.por_nombre["medio"]
        self.assertEqual(medio.sites_by_midpoint, 41)
        self.assertEqual(medio.free_of_panel, 0)
        self.assertTrue(medio.quota_met)
        self.assertEqual(medio.next_free, ())
        self.assertIn("No queda ninguno", "\n".join(medio.describe()))


if __name__ == "__main__":
    unittest.main()
