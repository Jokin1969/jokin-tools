"""Tests del estado NO_APLICA (bloque 9).

Regla 5: escritos antes de tocar `filters.py`.

La distincion que introduce: hay filtros que sobre una ventana del CDS no significan
nada. polyA, APA y los tercios son heuristicas del 3'UTR; aplicarlas a un tramo del ORF
no da un PASS ni un FAIL, da una pregunta mal hecha. Y tampoco es NOT_RUN: NOT_RUN
significa "no pude comprobarlo", que es una laguna; NO_APLICA significa "esa pregunta no
va con este candidato", que no lo es.

Consecuencia en la agregacion, que es lo que hay que tener claro:
  - NOT_RUN  -> INCOMPLETE (hay una laguna, el candidato no esta aprobado)
  - NO_APLICA -> no estorba (no hay laguna que tapar)
"""

import unittest

from shmir_design.filters import (
    BIOPHYSICAL_FILTERS,
    FilterResult,
    FilterState,
    Verdict,
    biophysical_ok,
    overall_verdict,
)


def _r(name, state, reason="motivo de prueba"):
    return FilterResult(name=name, state=state, reason=reason)


def _todos(state=FilterState.PASS):
    return [_r(n, state) for n in sorted(BIOPHYSICAL_FILTERS)]


class TestElEstadoExiste(unittest.TestCase):

    def test_NO_APLICA_es_un_estado(self):
        self.assertEqual(FilterState.NO_APLICA.value, "NO_APLICA")

    def test_no_se_confunde_con_NOT_RUN(self):
        self.assertIsNot(FilterState.NO_APLICA, FilterState.NOT_RUN)

    def test_sigue_exigiendo_motivo(self):
        with self.assertRaises(ValueError):
            FilterResult(name="polyA", state=FilterState.NO_APLICA, reason="")


class TestAgregacion(unittest.TestCase):

    def test_un_NO_APLICA_no_impide_el_PASS(self):
        resultados = [_r("GC", FilterState.PASS), _r("polyA", FilterState.NO_APLICA)]
        self.assertIs(overall_verdict(resultados), Verdict.PASS)

    def test_un_NOT_RUN_sigue_dando_INCOMPLETE(self):
        resultados = [_r("GC", FilterState.PASS), _r("polyA", FilterState.NOT_RUN)]
        self.assertIs(overall_verdict(resultados), Verdict.INCOMPLETE)

    def test_un_FAIL_manda_sobre_un_NO_APLICA(self):
        resultados = [_r("GC", FilterState.FAIL), _r("polyA", FilterState.NO_APLICA)]
        self.assertIs(overall_verdict(resultados), Verdict.FAIL)

    def test_un_NOT_RUN_manda_sobre_un_NO_APLICA(self):
        resultados = [
            _r("GC", FilterState.PASS),
            _r("polyA", FilterState.NO_APLICA),
            _r("especificidad", FilterState.NOT_RUN),
        ]
        self.assertIs(overall_verdict(resultados), Verdict.INCOMPLETE)

    def test_todo_NO_APLICA_no_es_un_candidato_aprobado(self):
        """Si NADA se pudo preguntar, no hay nada que aprobar."""
        resultados = [_r("GC", FilterState.NO_APLICA), _r("polyA", FilterState.NO_APLICA)]
        self.assertIs(overall_verdict(resultados), Verdict.INCOMPLETE)


class TestContadorBiofisico(unittest.TestCase):
    """`biofisicos_ok` no puede romperse: es el contador de referencia del proyecto."""

    def test_los_seis_en_PASS_siguen_contando(self):
        self.assertTrue(biophysical_ok(_todos()))

    def test_un_FAIL_sigue_descontando(self):
        resultados = _todos()
        resultados[0] = _r(resultados[0].name, FilterState.FAIL)
        self.assertFalse(biophysical_ok(resultados))

    def test_un_NOT_RUN_sigue_descontando(self):
        resultados = _todos()
        resultados[0] = _r(resultados[0].name, FilterState.NOT_RUN)
        self.assertFalse(biophysical_ok(resultados))

    def test_un_filtro_ausente_sigue_descontando(self):
        self.assertFalse(biophysical_ok(_todos()[:-1]))

    def test_el_polyA_en_NO_APLICA_no_descuenta(self):
        """Una ventana del CDS no puede quedar fuera por una heuristica del 3'UTR."""
        resultados = [
            _r(n, FilterState.NO_APLICA if n == "zona_prohibida_polyA" else FilterState.PASS)
            for n in sorted(BIOPHYSICAL_FILTERS)
        ]
        self.assertTrue(biophysical_ok(resultados))

    def test_sobre_un_3utr_puro_nada_cambia(self):
        """Regresion: en una corrida solo-3'UTR no aparece ni un NO_APLICA."""
        self.assertTrue(biophysical_ok(_todos()))
        self.assertFalse(biophysical_ok(_todos(FilterState.FAIL)))


if __name__ == "__main__":
    unittest.main()
