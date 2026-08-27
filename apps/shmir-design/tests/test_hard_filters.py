"""Tests de los filtros duros sobre ventanas de 22 nt (pasos 4-8).

Regla 5: escritos antes que `shmir_design/hard_filters.py`.

Datos reales: el bloque conservado raton/humano de 26 nt y sus 5 ventanas de 22 nt,
verificados por el responsable del proyecto. Todas las secuencias de nucleotidos que
aparecen aqui salen de ese bloque; no hay ninguna inventada.

La asimetria se calcula sobre la GUIA ya transformada (U forzada en la posicion 1) con
el proxy de `thermo.py`; sus valores propios se prueban en `test_thermo.py`. Aqui se
comprueba que el filtro la usa, con que umbral y que sigue habiendo camino a NOT_RUN
cuando no hay modelo (regla 3).
"""

import unittest

from shmir_design.filters import FilterState, Verdict
from shmir_design.hard_filters import (
    DEFAULT_THRESHOLDS,
    GC_MAX,
    GC_MIN,
    MAX_HOMOPOLYMER,
    evaluate_window,
    filter_g4,
    filter_gc,
    filter_homopolymer,
    gc_fraction,
    Thresholds,
    guide_from_target,
    reverse_complement_rna,
)

BLOCK = "TTTTCTATATTTGTAACTTTGCATGT"          # bloque conservado real, 26 nt
W0 = "TTTTCTATATTTGTAACTTTGC"                 # offset 0
W1 = "TTTCTATATTTGTAACTTTGCA"                 # offset 1
W2 = "TTCTATATTTGTAACTTTGCAT"                 # offset 2
W3 = "TCTATATTTGTAACTTTGCATG"                 # offset 3, el mejor del bloque


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
    """G4 NO EMITE VEREDICTO mientras su criterio no se decida por escrito.

    Sigue buscando y sigue diciendo lo que encuentra —dejar de mirar seria perder el
    dato— pero sale `NOT_RUN` y NO cuenta para el veredicto del candidato. Ver
    `hard_filters.G4_PENDING` y `hard_filters.G4_PROVENANCE`.
    """

    def test_las_ventanas_del_bloque_no_tienen_motivo_g4(self):
        for window in (W0, W1, W2):
            with self.subTest(window):
                resultado = filter_g4(window)
                self.assertIs(resultado.state, FilterState.NOT_RUN)
                self.assertIn("Sin motivo G-cuadruplex", resultado.reason)

    def test_un_motivo_g4_canonico_SE_DICE_pero_no_excluye(self):
        resultado = filter_g4("GGGTGGGTGGGTGGGTAAAAAA")
        self.assertIs(resultado.state, FilterState.NOT_RUN)
        self.assertIsNot(resultado.state, FilterState.FAIL)
        self.assertIn("GGGTGGGTGGGTGGG", resultado.reason)

    def test_tres_tetradas_no_bastan_y_tambien_se_dice(self):
        resultado = filter_g4("GGGTGGGTGGGTAAAAAAAAAA")
        self.assertIn("Sin motivo G-cuadruplex", resultado.reason)


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

    def test_el_offset_3_falla_unicamente_por_GC(self):
        """El mejor del bloque: asimetria +0.77, homopolimero y G4 limpios."""
        evaluacion = evaluate_window(W3)
        self.assertEqual(failures(evaluacion), {"GC"})
        self.assertIs(states(evaluacion)["homopolimero"], FilterState.PASS)
        # G4 no emite veredicto: sale NOT_RUN y no cuenta para el del candidato.
        self.assertIs(states(evaluacion)["G4_diana"], FilterState.NOT_RUN)
        self.assertIs(states(evaluacion)["G4_guia"], FilterState.NOT_RUN)
        self.assertIs(states(evaluacion)["asimetria"], FilterState.PASS)

    def test_el_offset_1_falla_por_GC_y_por_asimetria(self):
        self.assertEqual(failures(evaluate_window(W1)), {"GC", "asimetria"})

    def test_la_asimetria_se_calcula_sobre_la_guia(self):
        evaluacion = evaluate_window(W1)
        asimetria = next(r for r in evaluacion.filters if r.name == "asimetria")
        self.assertIn("-2.98", asimetria.reason)
        self.assertIn(guide_from_target(W1), asimetria.reason)

    def test_sin_modelo_la_asimetria_queda_en_not_run(self):
        evaluacion = evaluate_window(W3, asymmetry_model=None)
        self.assertIs(states(evaluacion)["asimetria"], FilterState.NOT_RUN)
        self.assertIs(evaluacion.verdict, Verdict.FAIL)  # sigue fallando por GC

    def test_el_offset_0_falla_por_GC_homopolimero_y_asimetria(self):
        self.assertEqual(
            failures(evaluate_window(W0)), {"GC", "homopolimero", "asimetria"}
        )

    def test_un_fail_manda_sobre_el_not_run(self):
        self.assertIs(evaluate_window(W1).verdict, Verdict.FAIL)

    def test_una_ventana_limpia_pasa_entera(self):
        # Sonda: extremo 5' GC-rico y 3' AT-rico, que da una guia con la asimetria
        # en el sentido bueno.
        limpia = "GCGTCAGTACGATCGAATTACT"
        evaluacion = evaluate_window(limpia)
        self.assertEqual(failures(evaluacion), set())
        self.assertIs(evaluacion.verdict, Verdict.PASS)

    def test_sin_modelo_ninguna_ventana_puede_declararse_apta(self):
        """Regla 3: con un filtro duro en NOT_RUN, lo mejor posible es INCOMPLETE."""
        evaluacion = evaluate_window("GCGTCAGTACGATCGAATTACT", asymmetry_model=None)
        self.assertEqual(failures(evaluacion), set())
        self.assertIs(evaluacion.verdict, Verdict.INCOMPLETE)

    def test_el_G4_se_comprueba_tambien_sobre_la_guia(self):
        """Una diana con tramos de C da una guia con tramos de G.

        Los dos salen `NOT_RUN` —no emiten veredicto— pero el HALLAZGO sigue estando: la
        guia tiene motivo y la diana no, y eso se lee en el motivo de cada uno.
        """
        diana = "CCCACCCACCCACCCATTTTTT"
        evaluacion = evaluate_window(diana)
        motivos = {r.name: r.reason for r in evaluacion.filters}
        self.assertIs(states(evaluacion)["G4_diana"], FilterState.NOT_RUN)
        self.assertIs(states(evaluacion)["G4_guia"], FilterState.NOT_RUN)
        self.assertIn("Sin motivo G-cuadruplex", motivos["G4_diana"])
        self.assertIn("Motivo G-cuadruplex canónico", motivos["G4_guia"])

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

    def test_la_evaluacion_guarda_el_valor_de_la_asimetria(self):
        """El numero, no solo el texto: la seleccion ordena por el."""
        self.assertAlmostEqual(evaluate_window(W1).asymmetry, -2.98, places=2)
        self.assertIsNone(evaluate_window(W1, asymmetry_model=None).asymmetry)

    def test_una_ventana_con_N_no_es_evaluable(self):
        """Base desconocida: los filtros no corren, y NOT_RUN no es PASS (regla 3)."""
        con_n = "GCGTCAGTACGATCGAATTNCT"
        evaluacion = evaluate_window(con_n)
        self.assertTrue(
            all(r.state is FilterState.NOT_RUN for r in evaluacion.filters)
        )
        self.assertIn("20", evaluacion.filters[0].reason)
        self.assertIs(evaluacion.verdict, Verdict.INCOMPLETE)

    def test_una_ventana_de_longitud_distinta_es_error_explicito(self):
        with self.assertRaises(ValueError):
            evaluate_window(BLOCK)


class TestUmbralesAjustables(unittest.TestCase):
    """Los umbrales se pueden mover sin tocar la logica; los de por defecto no cambian."""

    def test_los_valores_por_defecto_son_los_de_siempre(self):
        self.assertEqual(DEFAULT_THRESHOLDS.gc_min, GC_MIN)
        self.assertEqual(DEFAULT_THRESHOLDS.gc_max, GC_MAX)
        self.assertEqual(DEFAULT_THRESHOLDS.max_homopolymer, MAX_HOMOPOLYMER)
        self.assertEqual(DEFAULT_THRESHOLDS.min_asymmetry, 0.5)
        self.assertEqual(DEFAULT_THRESHOLDS.polya_flank, 10)

    def test_un_rango_de_GC_invertido_aborta(self):
        with self.assertRaises(ValueError):
            Thresholds(gc_min=0.6, gc_max=0.4)

    def test_un_GC_fuera_de_0_1_aborta(self):
        with self.assertRaises(ValueError):
            Thresholds(gc_max=1.5)

    def test_un_homopolimero_menor_que_1_aborta(self):
        with self.assertRaises(ValueError):
            Thresholds(max_homopolymer=0)

    def test_un_flanco_negativo_aborta(self):
        with self.assertRaises(ValueError):
            Thresholds(polya_flank=-1)

    def test_bajar_el_GC_minimo_deja_pasar_el_offset_1(self):
        umbrales = Thresholds(gc_min=0.20)
        self.assertIs(filter_gc(W1, umbrales).state, FilterState.PASS)
        self.assertIn("0.20", filter_gc(W1, umbrales).reason)

    def test_subir_el_homopolimero_deja_pasar_el_offset_0(self):
        self.assertIs(
            filter_homopolymer(W0, Thresholds(max_homopolymer=4)).state,
            FilterState.PASS,
        )

    def test_bajar_el_umbral_de_asimetria_deja_pasar_una_negativa(self):
        evaluacion = evaluate_window(W1, thresholds=Thresholds(min_asymmetry=-3.0))
        self.assertEqual(failures(evaluacion), {"GC"})

    def test_los_umbrales_llegan_a_la_evaluacion_entera(self):
        evaluacion = evaluate_window(W1, thresholds=Thresholds(gc_min=0.20, min_asymmetry=-3.0))
        self.assertEqual(failures(evaluacion), set())


if __name__ == "__main__":
    unittest.main()
