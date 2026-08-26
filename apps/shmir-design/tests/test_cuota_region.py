"""Tests de la cuota por region (bloque 9).

Regla 5: escritos antes de tocar `selection.py`.

Si el tilado incluye CDS, pedir "uno por tercio" no significa nada para esas ventanas:
los tercios se calculan sobre el 3'UTR. La cuota que hace falta es por region, del tipo
"7 del 3'UTR y 3 del CDS".

Y una ventana del ORF no puede entrar por accidente: solo entra si se pidio
explicitamente una cuota para su region.
"""

import unittest

from shmir_design.anatomy import Region
from shmir_design.polya import Tercio
from shmir_design.selection import (
    Choice,
    SelectionConfig,
    Site,
    choose,
)


def _sitio(start, tercio, asimetria, region=Region.UTR3):
    return Site(
        choices=(
            Choice(
                start=start,
                end=start + 21,
                tercio=tercio,
                asymmetry=asimetria,
                label=f"w{start}",
                asymmetry_raw=asimetria,
                region=region,
            ),
        )
    )


#: Tres del 3'UTR bien repartidos y tres del CDS, todos separados >50 nt.
SITIOS = [
    _sitio(1000, Tercio.PROXIMAL, 1.0),
    _sitio(1400, Tercio.MEDIO, 0.9),
    _sitio(1900, Tercio.DISTAL, 0.8),
    _sitio(200, None, 2.0, Region.CDS),
    _sitio(400, None, 1.9, Region.CDS),
    _sitio(600, None, 1.8, Region.CDS),
]


class TestConfiguracion(unittest.TestCase):

    def test_la_cuota_por_defecto_no_existe(self):
        self.assertIsNone(SelectionConfig().region_quota)

    def test_una_cuota_que_no_suma_el_total_aborta(self):
        with self.assertRaises(ValueError) as ctx:
            SelectionConfig(
                n_candidates=10, region_quota=((Region.UTR3, 7), (Region.CDS, 2))
            )
        self.assertIn("10", str(ctx.exception))

    def test_una_cuota_que_suma_el_total_vale(self):
        config = SelectionConfig(
            n_candidates=10, region_quota=((Region.UTR3, 7), (Region.CDS, 3))
        )
        self.assertEqual(dict(config.region_quota)[Region.CDS], 3)

    def test_una_cuota_negativa_aborta(self):
        with self.assertRaises(ValueError):
            SelectionConfig(
                n_candidates=6, region_quota=((Region.UTR3, 7), (Region.CDS, -1))
            )

    def test_una_region_repetida_aborta(self):
        with self.assertRaises(ValueError):
            SelectionConfig(
                n_candidates=6, region_quota=((Region.UTR3, 3), (Region.UTR3, 3))
            )


class TestSeleccionConCuota(unittest.TestCase):

    def _elegidos(self, config):
        return choose(list(SITIOS), config)

    def test_sin_cuota_no_entra_ninguna_del_CDS(self):
        """Regresion: el comportamiento de siempre no cambia si no se pide nada."""
        seleccion = self._elegidos(SelectionConfig(n_candidates=6))
        self.assertEqual(
            [c.region for c in seleccion.chosen], [Region.UTR3] * 3
        )

    def test_con_cuota_entran_las_dos_regiones(self):
        seleccion = self._elegidos(
            SelectionConfig(
                n_candidates=5,
                region_quota=((Region.UTR3, 3), (Region.CDS, 2)),
                require_one_per_tercio=False,
            )
        )
        regiones = [c.region for c in seleccion.chosen]
        self.assertEqual(regiones.count(Region.UTR3), 3)
        self.assertEqual(regiones.count(Region.CDS), 2)

    def test_la_cuota_del_CDS_coge_las_de_mejor_asimetria(self):
        seleccion = self._elegidos(
            SelectionConfig(
                n_candidates=4,
                region_quota=((Region.UTR3, 3), (Region.CDS, 1)),
                require_one_per_tercio=False,
            )
        )
        del_cds = [c for c in seleccion.chosen if c.region is Region.CDS]
        self.assertEqual([c.start for c in del_cds], [200])

    def test_la_cuota_del_3utr_sigue_repartiendo_por_tercios(self):
        seleccion = self._elegidos(
            SelectionConfig(
                n_candidates=4,
                region_quota=((Region.UTR3, 3), (Region.CDS, 1)),
                require_one_per_tercio=True,
            )
        )
        tercios = {c.tercio for c in seleccion.chosen if c.region is Region.UTR3}
        self.assertEqual(tercios, {Tercio.PROXIMAL, Tercio.MEDIO, Tercio.DISTAL})

    def test_una_cuota_que_no_se_puede_llenar_lo_dice(self):
        seleccion = self._elegidos(
            SelectionConfig(
                n_candidates=9,
                region_quota=((Region.UTR3, 3), (Region.CDS, 6)),
                require_one_per_tercio=False,
            )
        )
        self.assertTrue(
            any("CDS" in x for x in seleccion.quota_unfilled), seleccion.quota_unfilled
        )

    def test_una_cuota_de_cero_deja_fuera_esa_region(self):
        seleccion = self._elegidos(
            SelectionConfig(
                n_candidates=3,
                region_quota=((Region.UTR3, 3), (Region.CDS, 0)),
                require_one_per_tercio=False,
            )
        )
        self.assertNotIn(Region.CDS, [c.region for c in seleccion.chosen])

    def test_el_espaciado_se_sigue_respetando_dentro_de_cada_region(self):
        juntos = [
            _sitio(200, None, 2.0, Region.CDS),
            _sitio(210, None, 1.9, Region.CDS),
        ]
        seleccion = choose(
            juntos,
            SelectionConfig(
                n_candidates=2,
                region_quota=((Region.CDS, 2),),
                require_one_per_tercio=False,
                min_spacing=50,
            ),
        )
        self.assertEqual(len(seleccion.chosen), 1)
        self.assertTrue(any("espaciado" in x for x in seleccion.quota_unfilled))


if __name__ == "__main__":
    unittest.main()
