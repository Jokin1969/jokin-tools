"""Tests de los filtros duros sobre ventanas de 22 nt (pasos 4-8).

Regla 5: escritos antes que `batchwork/hard_filters.py`.

Datos reales: el bloque conservado raton/humano de 26 nt y sus 5 ventanas de 22 nt,
verificados por el responsable del proyecto. Todas las secuencias de nucleotidos que
aparecen aqui salen de ese bloque; no hay ninguna inventada.

La asimetria NO esta implementada: falta la definicion verificada (que extremos, cuantos
pares de bases, que tabla de parametros). Mientras falte, el filtro devuelve NOT_RUN,
que no es PASS (regla 3). Los tests fijan ese comportamiento y el valor esperado
(2.98 kcal/mol para la ventana del offset 1) queda anotado en docs/valores-esperados.md.
"""

import unittest

from batchwork.filters import FilterState, Verdict
from batchwork.hard_filters import (
    GC_MAX,
    GC_MIN,
    MAX_HOMOPOLYMER,
    evaluate_window,
    filter_g4,
    filter_gc,
    filter_homopolymer,
    gc_fraction,
    guide_from_target,
    reverse_complement_rna,
)

BLOCK = "TTTTCTATATTTGTAACTTTGCATGT"          # bloque conservado real, 26 nt
W0 = "TTTTCTATATTTGTAACTTTGC"                 # offset 0
W1 = "TTTCTATATTTGTAACTTTGCA"                 # offset 1
W2 = "TTCTATATTTGTAACTTTGCAT"                 # offset 2


def states(evaluation):
    return {r.name: r.state for r in evaluation.filters}


def failures(evaluation):
    return {r.name for r in evaluation.filters if r.state is FilterState.FAIL}


class TestGC(unittest.TestCase):

    def test_gc_del_bloque_conservado(self):
        self.assertAlmostEqual(gc_fraction(BLOCK), 6 / 26, places=4)
        self.assertAlmostEqual(gc_fraction(BLOCK) * 100, 23.08, places=2)

    def test_gc_de_la_ventana_del_offset_1(self):
        self.assertAlmostEqual(gc_fraction(W1), 0.227, places=3)

    def test_por_debajo_del_minimo_falla_diciendo_el_valor(self):
        resultado = filter_gc(W1)
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("0.227", resultado.reason)
        self.assertIn(f"{GC_MIN:.2f}", resultado.reason)

    def test_los_limites_son_inclusivos(self):
        # 22 nt con exactamente 7 y 11 GC: 0.318 y 0.5, dentro del rango.
        self.assertIs(filter_gc("G" * 7 + "A" * 15).state, FilterState.PASS)
        self.assertIs(filter_gc("G" * 11 + "A" * 11).state, FilterState.PASS)
        self.assertLessEqual(11 / 22, GC_MAX)

    def test_por_encima_del_maximo_falla(self):
        self.assertIs(filter_gc("G" * 13 + "A" * 9).state, FilterState.FAIL)


class TestHomopolimero(unittest.TestCase):

    def test_la_ventana_del_offset_0_falla_por_las_cuatro_T(self):
        resultado = filter_homopolymer(W0)
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("TTTT", resultado.reason)

    def test_la_ventana_del_offset_1_pasa(self):
        self.assertIs(filter_homopolymer(W1).state, FilterState.PASS)

    def test_el_maximo_declarado_es_3(self):
        self.assertEqual(MAX_HOMOPOLYMER, 3)
        # Sondas de umbral: 3 A seguidas pasan, 4 fallan (el resto alterna).
        self.assertIs(filter_homopolymer("A" * 3 + "CG" * 9 + "C").state, FilterState.PASS)
        self.assertIs(filter_homopolymer("A" * 4 + "CG" * 9).state, FilterState.FAIL)


class TestG4(unittest.TestCase):

    def test_las_ventanas_del_bloque_no_tienen_motivo_g4(self):
        for window in (W0, W1, W2):
            with self.subTest(window):
                self.assertIs(filter_g4(window).state, FilterState.PASS)

    def test_un_motivo_g4_canonico_falla(self):
        self.assertIs(filter_g4("GGGTGGGTGGGTGGGTAAAAAA").state, FilterState.FAIL)

    def test_tres_tetradas_no_bastan(self):
        self.assertIs(filter_g4("GGGTGGGTGGGTAAAAAAAAAA").state, FilterState.PASS)


class TestGuia(unittest.TestCase):

    def test_complementario_inverso_en_ARN(self):
        self.assertEqual(reverse_complement_rna("ACGT"), "ACGU")

    def test_se_fuerza_U_en_la_posicion_1(self):
        """La guia de un diana acabado en C empezaria por G; se fuerza a U."""
        self.assertEqual(reverse_complement_rna("AAAAC"), "GUUUU")
        self.assertEqual(guide_from_target("AAAAC"), "UUUUU")

    def test_si_ya_empieza_por_U_no_cambia_nada(self):
        self.assertEqual(guide_from_target("AAAAA"), reverse_complement_rna("AAAAA"))

    def test_guia_de_la_ventana_del_offset_1(self):
        self.assertEqual(guide_from_target(W1), "UGCAAAGUUACAAAUAUAGAAA")


class TestEvaluacionDeVentana(unittest.TestCase):

    def test_el_offset_1_falla_unicamente_por_GC(self):
        evaluacion = evaluate_window(W1)
        self.assertEqual(failures(evaluacion), {"GC"})
        self.assertIs(states(evaluacion)["homopolimero"], FilterState.PASS)
        self.assertIs(states(evaluacion)["G4"], FilterState.PASS)

    def test_la_asimetria_queda_en_not_run_mientras_no_haya_modelo(self):
        evaluacion = evaluate_window(W1)
        asimetria = states(evaluacion)["asimetria"]
        self.assertIs(asimetria, FilterState.NOT_RUN)
        reason = next(r.reason for r in evaluacion.filters if r.name == "asimetria")
        self.assertIn("definicion", reason.lower())

    def test_el_offset_0_falla_por_GC_y_por_homopolimero(self):
        self.assertEqual(failures(evaluate_window(W0)), {"GC", "homopolimero"})

    def test_un_fail_manda_sobre_el_not_run(self):
        self.assertIs(evaluate_window(W1).verdict, Verdict.FAIL)

    def test_sin_ningun_fail_el_veredicto_es_incompleto_no_apto(self):
        """Con la asimetria en NOT_RUN, nada puede declararse apto (regla 3)."""
        limpia = "ACGTACGTAAGGTTCCAAGGTT"
        evaluacion = evaluate_window(limpia)
        self.assertEqual(failures(evaluacion), set())
        self.assertIs(evaluacion.verdict, Verdict.INCOMPLETE)

    def test_con_modelo_de_asimetria_el_filtro_corre(self):
        """Cuando llegue la definicion verificada, el filtro deja de ser NOT_RUN."""
        evaluacion = evaluate_window(W1, asymmetry_model=lambda seq: 2.98)
        asimetria = next(r for r in evaluacion.filters if r.name == "asimetria")
        self.assertIs(asimetria.state, FilterState.PASS)
        self.assertIn("2.98", asimetria.reason)

    def test_modelo_de_asimetria_negativa_falla(self):
        evaluacion = evaluate_window(W2, asymmetry_model=lambda seq: -1.2)
        asimetria = next(r for r in evaluacion.filters if r.name == "asimetria")
        self.assertIs(asimetria.state, FilterState.FAIL)
        self.assertIn("-1.2", asimetria.reason)

    def test_una_ventana_de_longitud_distinta_es_error_explicito(self):
        with self.assertRaises(ValueError):
            evaluate_window(BLOCK)


if __name__ == "__main__":
    unittest.main()
