"""Tests de la seleccion voraz de candidatos (paso 15).

Regla 5: escritos antes que `shmir_design/selection.py`.

El nucleo de la seleccion trabaja sobre datos minimos (posicion, tercio, asimetria), sin
secuencias: asi se puede probar el espaciado, la cuota por tercio y el desempate sin
inventar ni un nucleotido.
"""

import unittest

from shmir_design.filters import FilterState, Verdict
from shmir_design.polya import Tercio
from shmir_design.selection import (
    DEFAULT_CANDIDATES,
    DEFAULT_MIN_SPACING,
    Choice,
    SelectionConfig,
    choose,
    eligible_choices,
    group_choices,
    select_from_report,
)
from shmir_design.tiling import tile_utr


def choice(start, asymmetry, tercio=Tercio.PROXIMAL, label=None):
    return Choice(
        start=start,
        end=start + 21,
        tercio=tercio,
        asymmetry=asymmetry,
        label=label or f"w{start}",
    )


class TestValoresPorDefecto(unittest.TestCase):

    def test_seis_candidatos_y_50_nt(self):
        self.assertEqual(DEFAULT_CANDIDATES, 6)
        self.assertEqual(DEFAULT_MIN_SPACING, 50)
        config = SelectionConfig()
        self.assertEqual(config.n_candidates, 6)
        self.assertEqual(config.min_spacing, 50)
        self.assertTrue(config.require_one_per_tercio)

    def test_configuracion_invalida_aborta(self):
        with self.assertRaises(ValueError):
            SelectionConfig(n_candidates=0)
        with self.assertRaises(ValueError):
            SelectionConfig(min_spacing=-1)


class TestAgrupacionEnSitios(unittest.TestCase):

    def test_ventanas_contiguas_son_un_sitio(self):
        sites = group_choices([choice(10, 1.0), choice(11, 2.0), choice(12, 0.5)])
        self.assertEqual(len(sites), 1)
        self.assertEqual((sites[0].start, sites[0].end), (10, 12))

    def test_un_hueco_separa_sitios(self):
        sites = group_choices([choice(10, 1.0), choice(40, 2.0)])
        self.assertEqual(len(sites), 2)

    def test_el_mejor_del_sitio_es_el_de_mayor_asimetria(self):
        sites = group_choices([choice(10, 1.0), choice(11, 2.5), choice(12, 0.5)])
        self.assertEqual(sites[0].best.start, 11)

    def test_empate_gana_la_posicion_mas_baja(self):
        sites = group_choices([choice(10, 2.0), choice(11, 2.0)])
        self.assertEqual(sites[0].best.start, 10)


class TestEspaciado(unittest.TestCase):
    """La regla que convierte N apuestas correlacionadas en N independientes."""

    def test_dos_sitios_demasiado_juntos_solo_dan_uno(self):
        sites = group_choices([choice(100, 3.0), choice(140, 2.9)])
        resultado = choose(sites, SelectionConfig(n_candidates=2, require_one_per_tercio=False))
        self.assertEqual([c.start for c in resultado.chosen], [100])

    def test_exactamente_50_nt_vale(self):
        sites = group_choices([choice(100, 3.0), choice(150, 2.9)])
        resultado = choose(sites, SelectionConfig(n_candidates=2, require_one_per_tercio=False))
        self.assertEqual([c.start for c in resultado.chosen], [100, 150])

    def test_49_nt_no_vale(self):
        sites = group_choices([choice(100, 3.0), choice(149, 2.9)])
        resultado = choose(sites, SelectionConfig(n_candidates=2, require_one_per_tercio=False))
        self.assertEqual(len(resultado.chosen), 1)

    def test_el_espaciado_se_mide_contra_todos_los_elegidos(self):
        sites = group_choices([choice(100, 3.0), choice(200, 2.9), choice(160, 2.8)])
        resultado = choose(sites, SelectionConfig(n_candidates=3, require_one_per_tercio=False))
        self.assertEqual([c.start for c in resultado.chosen], [100, 200])

    def test_se_avisa_de_que_no_se_llego_al_numero_pedido(self):
        sites = group_choices([choice(100, 3.0), choice(120, 2.0)])
        resultado = choose(sites, SelectionConfig(n_candidates=6, require_one_per_tercio=False))
        self.assertEqual(len(resultado.chosen), 1)
        self.assertTrue(any("6" in nota for nota in resultado.notes))


class TestCuotaPorTercio(unittest.TestCase):

    def sitios_con_medio_peor(self):
        return group_choices(
            [
                choice(100, 5.0, Tercio.PROXIMAL),
                choice(200, 4.5, Tercio.PROXIMAL),
                choice(300, 4.0, Tercio.PROXIMAL),
                choice(600, 0.6, Tercio.MEDIO),
                choice(1000, 3.0, Tercio.DISTAL),
            ]
        )

    def test_el_tercio_medio_entra_aunque_puntue_peor(self):
        resultado = choose(self.sitios_con_medio_peor(), SelectionConfig(n_candidates=3))
        tercios = {c.tercio for c in resultado.chosen}
        self.assertEqual(tercios, {Tercio.PROXIMAL, Tercio.MEDIO, Tercio.DISTAL})

    def test_sin_cuota_el_medio_se_queda_fuera(self):
        resultado = choose(
            self.sitios_con_medio_peor(),
            SelectionConfig(n_candidates=3, require_one_per_tercio=False),
        )
        self.assertNotIn(Tercio.MEDIO, {c.tercio for c in resultado.chosen})

    def test_el_resto_de_plazas_va_por_asimetria(self):
        resultado = choose(self.sitios_con_medio_peor(), SelectionConfig(n_candidates=4))
        self.assertEqual(
            sorted(c.start for c in resultado.chosen), [100, 200, 600, 1000]
        )

    def test_un_tercio_sin_candidatos_se_reporta(self):
        sites = group_choices(
            [choice(100, 5.0, Tercio.PROXIMAL), choice(1000, 3.0, Tercio.DISTAL)]
        )
        resultado = choose(sites, SelectionConfig(n_candidates=3))
        self.assertEqual(len(resultado.chosen), 2)
        self.assertTrue(any("medio" in q.lower() for q in resultado.quota_unfilled))

    def test_un_tercio_que_no_cabe_por_espaciado_se_reporta(self):
        sites = group_choices(
            [choice(100, 5.0, Tercio.PROXIMAL), choice(130, 4.0, Tercio.MEDIO)]
        )
        resultado = choose(sites, SelectionConfig(n_candidates=2))
        self.assertEqual(len(resultado.chosen), 1)
        self.assertTrue(
            any("espaciado" in q.lower() for q in resultado.quota_unfilled)
        )

    def test_con_menos_de_tres_plazas_la_cuota_no_cabe_y_se_avisa(self):
        resultado = choose(self.sitios_con_medio_peor(), SelectionConfig(n_candidates=2))
        self.assertEqual(len(resultado.chosen), 2)
        self.assertTrue(any("3" in nota for nota in resultado.notes))


class TestOrdenYDeterminismo(unittest.TestCase):

    def test_los_elegidos_salen_ordenados_por_posicion(self):
        sites = group_choices(
            [choice(1000, 5.0, Tercio.DISTAL), choice(100, 4.0, Tercio.PROXIMAL)]
        )
        resultado = choose(sites, SelectionConfig(n_candidates=2, require_one_per_tercio=False))
        self.assertEqual([c.start for c in resultado.chosen], [100, 1000])

    def test_el_rango_por_asimetria_se_conserva(self):
        sites = group_choices(
            [choice(1000, 5.0, Tercio.DISTAL), choice(100, 4.0, Tercio.PROXIMAL)]
        )
        resultado = choose(sites, SelectionConfig(n_candidates=2, require_one_per_tercio=False))
        self.assertEqual(resultado.rank_of(1000), 1)
        self.assertEqual(resultado.rank_of(100), 2)

    def test_dos_ejecuciones_dan_lo_mismo(self):
        sites = group_choices([choice(100 + 60 * i, 3.0, Tercio.PROXIMAL) for i in range(6)])
        config = SelectionConfig(n_candidates=4, require_one_per_tercio=False)
        primera = [c.start for c in choose(sites, config).chosen]
        segunda = [c.start for c in choose(sites, config).chosen]
        self.assertEqual(primera, segunda)

    def test_sin_sitios_no_hay_candidatos_pero_si_aviso(self):
        resultado = choose([], SelectionConfig())
        self.assertEqual(resultado.chosen, ())
        self.assertTrue(resultado.notes)


class TestSeleccionSobreUnInforme(unittest.TestCase):
    """Integracion: del informe de tiling a los candidatos elegidos."""

    def report(self):
        # Sonda: un 22-mero limpio repetido. No es un dato biologico, es un andamio
        # para que haya ventanas elegibles que seleccionar.
        return tile_utr("GCGTCAGTACGATCGAATTACT" * 30)

    def test_hay_ventanas_elegibles(self):
        seleccion = select_from_report(self.report(), SelectionConfig())
        self.assertGreater(seleccion.eligible, 0)

    def test_no_se_piden_mas_de_los_configurados(self):
        seleccion = select_from_report(self.report(), SelectionConfig(n_candidates=4))
        self.assertLessEqual(len(seleccion.selection.chosen), 4)

    def test_todos_los_elegidos_respetan_el_espaciado(self):
        seleccion = select_from_report(self.report(), SelectionConfig())
        posiciones = sorted(c.start for c in seleccion.selection.chosen)
        for anterior, siguiente in zip(posiciones, posiciones[1:]):
            self.assertGreaterEqual(siguiente - anterior, DEFAULT_MIN_SPACING)

    def test_todos_los_elegidos_eran_elegibles(self):
        seleccion = select_from_report(self.report(), SelectionConfig())
        for elegido in seleccion.selection.chosen:
            ventana = seleccion.window_of(elegido)
            self.assertTrue(ventana.biofisicos_ok)

    def test_los_candidatos_son_provisionales_mientras_falten_filtros(self):
        """Con seed y repeticiones en NOT_RUN, ninguno puede salir como apto."""
        seleccion = select_from_report(self.report(), SelectionConfig())
        for elegido in seleccion.selection.chosen:
            self.assertIs(seleccion.window_of(elegido).verdict, Verdict.INCOMPLETE)
        self.assertIn("seed", seleccion.not_run_filters)
        self.assertIn("repeticiones", seleccion.not_run_filters)

    def test_una_ventana_con_un_filtro_en_fail_no_es_elegible(self):
        report = self.report()
        elegibles = {c.label for c in eligible_choices(report)}
        con_fallo = [
            w.window.name for w in report.windows
            if any(r.state is FilterState.FAIL for r in w.filters)
        ]
        self.assertTrue(con_fallo)
        self.assertTrue(elegibles.isdisjoint(con_fallo))


if __name__ == "__main__":
    unittest.main()
