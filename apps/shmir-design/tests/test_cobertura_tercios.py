"""Los tercios: con QUE definicion se etiqueta, y cuantos sitios hay en cada uno.

Regla 5: escritos antes.

`Tercio` etiqueta por el PUNTO MEDIO de la ventana; la particion simple del 3'UTR
(1-414 / 415-828 / 829-1242 en el raton) va por la POSICION DE INICIO. No coinciden, y
la ventana 3utr:819-840 es el caso: empieza en el segundo tercio y su punto medio
(829,5) cae en el tercero. Etiquetada «distal», por inicio es «medio».

Ninguna de las dos definiciones es incorrecta — lo que no vale es no decir cual se usa,
porque el reparto del panel se lee sobre una y se decide sobre la otra.

Y para pedir una plaza en un tramo concreto hay `start_window_quota`, que va por INICIO
y en coordenadas explicitas: «una plaza mas en 3utr:829-1242» no depende de ninguna
definicion de tercio.
"""

import unittest
from pathlib import Path

from shmir_design.polya import Tercio
from shmir_design.selection import (
    SelectionConfig,
    is_eligible,
    select_from_report,
    tercio_counts,
)

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"


def _tiling():
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.tiling import tile_utr

    return tile_utr(load_3utr(REFERENCES["NM_011170.3"]))


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLasDosDefinicionesNoCoinciden(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling = _tiling()
        cls.cuenta = tercio_counts(cls.tiling)

    def test_la_particion_simple_del_raton(self):
        self.assertEqual(
            self.cuenta.bounds,
            ((1, 414), (415, 828), (829, 1242)),
        )

    def test_por_punto_medio_que_es_como_se_etiqueta_hoy(self):
        self.assertEqual(self.cuenta.by_midpoint, {"proximal": 88, "medio": 128, "distal": 54})

    def test_por_posicion_de_inicio(self):
        self.assertEqual(self.cuenta.by_start, {"proximal": 88, "medio": 137, "distal": 45})

    def test_y_los_SITIOS_por_inicio(self):
        self.assertEqual(self.cuenta.sites_by_start, {"proximal": 28, "medio": 42, "distal": 16})

    def test_819_es_el_caso_que_las_separa(self):
        ventana = [w for w in self.tiling.windows if w.window.start == 819][0]
        self.assertIs(ventana.tercio, Tercio.DISTAL)      # por punto medio
        self.assertLessEqual(ventana.window.start, 828)   # por inicio, medio

    def test_la_salida_DICE_con_cual_etiqueta(self):
        texto = "\n".join(self.cuenta.describe())
        self.assertIn("PUNTO MEDIO", texto)
        self.assertIn("3utr:829-1242", texto)
        self.assertIn("88", texto)
        self.assertIn("45", texto)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaPlazaExtraEnElTramoDistal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling = _tiling()
        cls.seleccion = select_from_report(
            cls.tiling,
            SelectionConfig(
                n_candidates=11,
                apa_immune_quota=4,
                apa_immune_before=303,
                tercio_quota=((Tercio.PROXIMAL, 4), (Tercio.MEDIO, 3), (Tercio.DISTAL, 2)),
                start_window_quota=((829, 1242, 2),),
            ),
        )
        cls.inicios = sorted(c.start for c in cls.seleccion.selection.chosen)

    def test_hay_DOS_candidatos_que_empiezan_en_829_1242(self):
        self.assertGreaterEqual(len([p for p in self.inicios if 829 <= p <= 1242]), 2)

    def test_y_el_nuevo_respeta_el_espaciado_con_1018(self):
        distales = [p for p in self.inicios if 829 <= p <= 1242]
        for a, b in zip(distales, distales[1:]):
            with self.subTest((a, b)):
                self.assertGreaterEqual(b - a, 50)

    def test_los_cuatro_inmunes_siguen(self):
        self.assertEqual(sorted(p for p in self.inicios if p <= 303), [10, 60, 143, 200])

    def test_una_cuota_de_tramo_invertida_aborta(self):
        with self.assertRaises(ValueError):
            SelectionConfig(n_candidates=11, start_window_quota=((1242, 829, 1),))

    def test_una_cuota_de_tramo_mayor_que_el_panel_aborta(self):
        with self.assertRaises(ValueError):
            SelectionConfig(n_candidates=6, start_window_quota=((829, 1242, 7),))

    def test_si_no_cabe_se_DECLARA(self):
        seleccion = select_from_report(
            self.tiling,
            SelectionConfig(n_candidates=4, start_window_quota=((1200, 1242, 3),)),
        )
        avisos = " ".join(seleccion.selection.quota_unfilled)
        self.assertIn("1200", avisos)
        self.assertIn("3", avisos)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestSitiosPorTramoQueQuedanConTecho(unittest.TestCase):
    """¿Se puede rebalancear el panel hacia proximales si el APA resulta funcional?

    Esa pregunta se contesta con una cuenta y no con una impresion: cuantos sitios
    elegibles hay por tramo POR DELANTE del corte de 3utr:288 —que son los que
    sobrevivirian— y cuantos por detras.
    """

    @classmethod
    def setUpClass(cls):
        cls.cuenta = tercio_counts(_tiling())

    def test_da_la_cuenta_por_tramo(self):
        self.assertEqual(
            set(self.cuenta.sites_immune), {"proximal", "medio", "distal"}
        )

    def test_todos_los_inmunes_estan_en_el_tercio_proximal(self):
        # El corte de 3utr:288 cae dentro del primer tercio (1-414), asi que ni el medio
        # ni el distal tienen ni un sitio inmune. El rebalanceo solo puede ir hacia el
        # proximal, y ademas solo hasta donde deje el espaciado.
        self.assertEqual(self.cuenta.sites_immune["medio"], 0)
        self.assertEqual(self.cuenta.sites_immune["distal"], 0)
        self.assertGreater(self.cuenta.sites_immune["proximal"], 0)

    def test_la_cifra_proximal_cuadra_con_los_16_sitios_conocidos(self):
        self.assertEqual(self.cuenta.sites_immune["proximal"], 16)

    def test_y_la_salida_lo_dice_con_el_corte_nombrado(self):
        texto = "\n".join(self.cuenta.describe())
        self.assertIn("3utr:251", texto)
        self.assertIn("16", texto)
        self.assertIn("rebalancear", texto.lower())
