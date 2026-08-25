"""Tests de los tres estados de filtro (regla 3)."""

import unittest

from batchwork.filters import FilterResult, FilterState, Verdict, overall_verdict


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


if __name__ == "__main__":
    unittest.main()
