"""Tests de los tres estados de filtro (regla 3)."""

import unittest

from shmir_design.filters import (
    BIOPHYSICAL_FILTERS,
    FilterResult,
    FilterState,
    Verdict,
    biophysical_ok,
    overall_verdict,
)


def result(state, name="filtro", reason="motivo"):
    return FilterResult(name=name, state=state, reason=reason)


class TestFilterResult(unittest.TestCase):

    def test_un_estado_sin_motivo_es_error(self):
        with self.assertRaises(ValueError):
            FilterResult(name="conservacion", state=FilterState.NOT_RUN, reason="")

    def test_pass_tambien_exige_motivo(self):
        with self.assertRaises(ValueError):
            FilterResult(name="conservacion", state=FilterState.PASS, reason="")


class TestAgregacion(unittest.TestCase):

    def test_todos_pass(self):
        self.assertIs(
            overall_verdict([result(FilterState.PASS), result(FilterState.PASS)]),
            Verdict.PASS,
        )

    def test_un_not_run_impide_aprobar(self):
        self.assertIs(
            overall_verdict([result(FilterState.PASS), result(FilterState.NOT_RUN)]),
            Verdict.INCOMPLETE,
        )

    def test_fail_manda_sobre_not_run(self):
        self.assertIs(
            overall_verdict([result(FilterState.FAIL), result(FilterState.NOT_RUN)]),
            Verdict.FAIL,
        )

    def test_sin_filtros_no_hay_veredicto(self):
        with self.assertRaises(ValueError):
            overall_verdict([])


class TestBiofisicos(unittest.TestCase):
    """El contador biofisico es distinto del veredicto: no incluye filtros externos."""

    def todos(self, state=FilterState.PASS):
        return [result(state, name=name) for name in sorted(BIOPHYSICAL_FILTERS)]

    def test_son_CUATRO_y_no_incluyen_la_seed_ni_los_G4(self):
        # CUATRO desde que los dos G4 dejaron de emitir veredicto: su criterio está
        # pendiente de decisión escrita, así que no pueden decidir si una ventana es
        # elegible. (G4 se retiró; ver `hard_filters.G4_WITHDRAWN`.)
        self.assertEqual(len(BIOPHYSICAL_FILTERS), 4)
        self.assertNotIn("seed", BIOPHYSICAL_FILTERS)
        self.assertIn("zona_prohibida_polyA", BIOPHYSICAL_FILTERS)

    def test_todos_en_pass(self):
        self.assertTrue(biophysical_ok(self.todos()))

    def test_un_filtro_externo_no_cuenta(self):
        self.assertTrue(biophysical_ok(self.todos() + [result(FilterState.NOT_RUN, name="seed")]))

    def test_un_biofisico_en_fail_lo_tumba(self):
        resultados = self.todos()
        resultados[0] = result(FilterState.FAIL, name=resultados[0].name)
        self.assertFalse(biophysical_ok(resultados))

    def test_un_biofisico_en_not_run_lo_tumba(self):
        resultados = self.todos()
        resultados[0] = result(FilterState.NOT_RUN, name=resultados[0].name)
        self.assertFalse(biophysical_ok(resultados))

    def test_un_biofisico_ausente_lo_tumba(self):
        """Un filtro que no aparece no es un filtro superado."""
        self.assertFalse(biophysical_ok(self.todos()[:-1]))


if __name__ == "__main__":
    unittest.main()
