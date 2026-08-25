"""Tests de polyA como ANOTACION, no como veredicto (bloque 3).

Regla 5: escritos antes de implementarlo.

Lo que cambia: el umbral de ±10 nt no sale de ningun articulo, y debajo habia tres
preocupaciones distintas mezcladas en un solo PASS/FAIL. Ahora son cinco campos, y solo
uno de ellos es un veredicto.

La geometria, que es contraintuitiva: el corte NO ocurre en el hexamero, ocurre 10-30 nt
aguas abajo. El hexamero se queda DENTRO del ARNm maduro. Asi que una ventana que
contiene la señal terminal sigue existiendo en el transcrito; la que desaparece es la que
empieza despues del sitio de corte. La zona prohibida por esta razon es asimetrica y
esta desplazada aguas abajo, no centrada en el hexamero.

Dato real que se usa como regresion: la guia 1018 (TTTAGTACTGGATGGAACGGCC) tiene su seed
encima del ACTAAA de 1034. La ventana diana es 1018-1039; las posiciones 2-8 de la guia
emparejan con las posiciones 15-21 de la ventana, que en coordenadas de 3'UTR son
1032-1038; el ACTAAA ocupa 1034-1039. Se solapan.
"""

import unittest

from shmir_design.filters import FilterState
from shmir_design.polya import (
    CLEAVAGE_MAX,
    CLEAVAGE_MIN,
    PolyAMode,
    RelativePosition,
    SEED_TARGET_END,
    SEED_TARGET_START,
    SignalClass,
    Window,
    annotate_polya,
    classify_signal,
    seed_target_span,
)

UTR = 1242


def _señal(motif, position, clase=None, utr_length=UTR):
    s = classify_signal(motif, position, utr_length)
    if clase is None:
        return s
    return classify_signal(motif, position, utr_length).__class__(
        motif=s.motif,
        position=s.position,
        utr_length=s.utr_length,
        distance_to_3p=s.distance_to_3p,
        classification=clase,
        flank=s.flank,
    )


class TestGeometriaDeLaSeed(unittest.TestCase):
    """Las posiciones 2-8 de la guia emparejan con el extremo 3' de la ventana diana."""

    def test_la_seed_cae_en_las_posiciones_15_a_21_de_la_ventana(self):
        self.assertEqual((SEED_TARGET_START, SEED_TARGET_END), (15, 21))

    def test_el_tramo_absoluto_de_la_seed_de_la_guia_1018(self):
        self.assertEqual(seed_target_span(Window(1018, 22)), (1032, 1038))

    def test_para_una_ventana_cualquiera_el_tramo_va_al_final(self):
        inicio, fin = seed_target_span(Window(100, 22))
        self.assertEqual((inicio, fin), (114, 120))
        self.assertLess(fin, 100 + 22 - 1)

    def test_una_ventana_de_otro_tamaño_aborta(self):
        with self.assertRaises(ValueError):
            seed_target_span(Window(100, 19))


class TestSolapaSeed(unittest.TestCase):

    def test_el_ACTAAA_de_1034_pisa_la_seed_de_la_guia_1018(self):
        """El caso real que motivo este campo."""
        anotacion = annotate_polya(
            Window(1018, 22), [_señal("ACTAAA", 1034)], utr_length=UTR
        )
        self.assertTrue(anotacion.solapa_seed)

    def test_un_hexamero_al_principio_de_la_ventana_no_pisa_la_seed(self):
        anotacion = annotate_polya(
            Window(1018, 22), [_señal("AATAAA", 1018)], utr_length=UTR
        )
        self.assertFalse(anotacion.solapa_seed)

    def test_sin_ningun_hexamero_no_hay_solape(self):
        anotacion = annotate_polya(Window(1018, 22), [], utr_length=UTR)
        self.assertFalse(anotacion.solapa_seed)

    def test_solapar_la_seed_no_es_por_si_solo_un_FAIL(self):
        """Es informacion para decidir, no un veredicto."""
        anotacion = annotate_polya(
            Window(1018, 22), [_señal("ACTAAA", 1034)], utr_length=UTR
        )
        self.assertIsNot(anotacion.veredicto.state, FilterState.FAIL)


class TestLosCincoCampos(unittest.TestCase):

    def test_estan_los_cinco(self):
        a = annotate_polya(Window(1018, 22), [_señal("ACTAAA", 1034)], utr_length=UTR)
        for campo in (
            "polyA_hexamero", "polyA_clase", "polyA_posicion_rel",
            "polyA_solapa_seed", "polyA_veredicto",
        ):
            self.assertIn(campo, a.as_columns())

    def test_el_hexamero_sale_tal_cual(self):
        a = annotate_polya(Window(1018, 22), [_señal("ACTAAA", 1034)], utr_length=UTR)
        self.assertEqual(a.as_columns()["polyA_hexamero"], "ACTAAA")

    def test_sin_hexamero_el_campo_va_vacio(self):
        a = annotate_polya(Window(500, 22), [], utr_length=UTR)
        self.assertEqual(a.as_columns()["polyA_hexamero"], "")

    def test_la_clase_es_la_del_hexamero(self):
        a = annotate_polya(Window(1018, 22), [_señal("ACTAAA", 1034)], utr_length=UTR)
        self.assertEqual(a.as_columns()["polyA_clase"], SignalClass.OTHER.value)

    def test_con_varios_hexameros_manda_el_mas_grave(self):
        señales = [_señal("ACTAAA", 1034), _señal("AATAAA", 1030)]
        a = annotate_polya(Window(1018, 22), señales, utr_length=UTR)
        self.assertEqual(a.as_columns()["polyA_hexamero"], "AATAAA")


class TestPosicionRelativa(unittest.TestCase):

    def test_una_señal_antes_de_la_ventana_esta_aguas_arriba(self):
        a = annotate_polya(Window(1000, 22), [_señal("AATAAA", 900)], utr_length=UTR)
        self.assertIs(a.posicion_rel, RelativePosition.AGUAS_ARRIBA)

    def test_dice_a_cuantos_nt(self):
        a = annotate_polya(Window(1000, 22), [_señal("AATAAA", 900)], utr_length=UTR)
        self.assertIn("94 nt", a.as_columns()["polyA_posicion_rel"])

    def test_una_señal_dentro_de_la_ventana_esta_dentro(self):
        a = annotate_polya(Window(1000, 22), [_señal("AATAAA", 1005)], utr_length=UTR)
        self.assertIs(a.posicion_rel, RelativePosition.DENTRO)

    def test_una_señal_a_caballo_esta_solapando(self):
        a = annotate_polya(Window(1000, 22), [_señal("AATAAA", 1019)], utr_length=UTR)
        self.assertIs(a.posicion_rel, RelativePosition.SOLAPANDO)

    def test_una_señal_despues_de_la_ventana_esta_aguas_abajo(self):
        a = annotate_polya(Window(1000, 22), [_señal("AATAAA", 1100)], utr_length=UTR)
        self.assertIs(a.posicion_rel, RelativePosition.AGUAS_ABAJO)


class TestGeometriaDelCorte(unittest.TestCase):
    """El corte va 10-30 nt aguas abajo del hexamero, no en el hexamero.

    Esta clase juzga la REGLA GEOMETRICA, que es la del modo permisivo. El modo
    escalonado sigue tumbando por solape porque es deliberadamente conservador; el
    reparto entre los dos criterios es justo lo que el top-N bajo los tres modos deja
    ver.
    """

    TERMINAL = _señal("AATAAA", 1200, SignalClass.TERMINAL_PROBABLE)

    def test_los_limites_del_corte_son_10_y_30(self):
        self.assertEqual((CLEAVAGE_MIN, CLEAVAGE_MAX), (10, 30))

    def test_una_ventana_que_contiene_la_señal_terminal_sobrevive(self):
        """El hexamero se queda dentro del ARNm maduro."""
        a = annotate_polya(
            Window(1198, 22), [self.TERMINAL], utr_length=UTR,
            mode=PolyAMode.PERMISIVO,
        )
        self.assertIsNot(a.veredicto.state, FilterState.FAIL)

    def test_una_ventana_justo_detras_del_hexamero_sobrevive(self):
        a = annotate_polya(
            Window(1206, 22), [self.TERMINAL], utr_length=UTR,
            mode=PolyAMode.PERMISIVO,
        )
        self.assertIsNot(a.veredicto.state, FilterState.FAIL)

    def test_una_ventana_pasado_el_corte_maximo_es_FAIL(self):
        # hexamero 1200-1205; corte como mucho en 1205+30 = 1235
        a = annotate_polya(Window(1236, 6), [self.TERMINAL], utr_length=UTR)
        self.assertIs(a.veredicto.state, FilterState.FAIL)

    def test_en_la_banda_incierta_no_es_FAIL_pero_queda_marcada(self):
        a = annotate_polya(Window(1220, 6), [self.TERMINAL], utr_length=UTR)
        self.assertIsNot(a.veredicto.state, FilterState.FAIL)
        self.assertTrue(a.tras_corte_posible)

    def test_la_zona_prohibida_es_asimetrica(self):
        """Aguas arriba del hexamero no se prohibe nada por esta razon."""
        a = annotate_polya(Window(1150, 22), [self.TERMINAL], utr_length=UTR)
        self.assertIsNot(a.veredicto.state, FilterState.FAIL)
        self.assertFalse(a.tras_corte_posible)

    def test_una_señal_que_no_es_terminal_no_produce_FAIL_por_corte(self):
        """Que un APA se use o no lo dice el dato medido, no la prediccion."""
        apa = _señal("AATAAA", 288, SignalClass.APA_POSSIBLE)
        a = annotate_polya(Window(400, 22), [apa], utr_length=UTR)
        self.assertIsNot(a.veredicto.state, FilterState.FAIL)


class TestContextoDelHexamero(unittest.TestCase):
    """Un hexamero solo casi nunca es un sitio funcional: hace falta el elemento GU/U."""

    def test_sin_secuencia_el_contexto_no_se_puede_mirar(self):
        a = annotate_polya(Window(1018, 22), [_señal("ACTAAA", 1034)], utr_length=UTR)
        self.assertIsNone(a.contexto_gu_rico)

    def test_con_un_tramo_GU_rico_detras_el_contexto_es_plausible(self):
        secuencia = "A" * 99 + "AATAAA" + "C" * 9 + "GTGTGTGTGTGTGTGTGTGTG" + "A" * 66
        a = annotate_polya(
            Window(80, 22), [_señal("AATAAA", 100, utr_length=len(secuencia))],
            utr_length=len(secuencia), sequence=secuencia,
        )
        self.assertTrue(a.contexto_gu_rico)

    def test_sin_tramo_GU_rico_detras_el_contexto_no_es_plausible(self):
        secuencia = "A" * 99 + "AATAAA" + "A" * 95
        a = annotate_polya(
            Window(80, 22), [_señal("AATAAA", 100, utr_length=len(secuencia))],
            utr_length=len(secuencia), sequence=secuencia,
        )
        self.assertFalse(a.contexto_gu_rico)

    def test_un_hexamero_al_final_sin_sitio_para_el_contexto_queda_en_None(self):
        secuencia = "A" * 99 + "AATAAA" + "A" * 5
        a = annotate_polya(
            Window(80, 22), [_señal("AATAAA", 100, utr_length=len(secuencia))],
            utr_length=len(secuencia), sequence=secuencia,
        )
        self.assertIsNone(a.contexto_gu_rico)


class TestModos(unittest.TestCase):

    SEÑALES = [_señal("AATAAA", 1030, SignalClass.APA_POSSIBLE), _señal("ACTAAA", 1034)]

    def test_los_tres_modos_existen(self):
        self.assertEqual(
            {m.value for m in PolyAMode}, {"estricto", "escalonado", "permisivo"}
        )

    def test_estricto_tumba_la_ventana_que_solapa_cualquier_hexamero(self):
        a = annotate_polya(
            Window(1018, 22), self.SEÑALES, utr_length=UTR, mode=PolyAMode.ESTRICTO
        )
        self.assertIs(a.veredicto.state, FilterState.FAIL)

    def test_escalonado_tumba_solo_las_fuertes(self):
        a = annotate_polya(
            Window(1018, 22), self.SEÑALES, utr_length=UTR, mode=PolyAMode.ESCALONADO
        )
        self.assertIs(a.veredicto.state, FilterState.FAIL)

    def test_escalonado_no_tumba_una_variante_rara_sola(self):
        a = annotate_polya(
            Window(1018, 22), [_señal("ACTAAA", 1034)], utr_length=UTR,
            mode=PolyAMode.ESCALONADO,
        )
        self.assertIsNot(a.veredicto.state, FilterState.FAIL)

    def test_permisivo_no_tumba_nada_que_no_este_tras_el_corte(self):
        a = annotate_polya(
            Window(1018, 22), self.SEÑALES, utr_length=UTR, mode=PolyAMode.PERMISIVO
        )
        self.assertIsNot(a.veredicto.state, FilterState.FAIL)

    def test_el_motivo_dice_siempre_con_que_modo_se_juzgo(self):
        for modo in PolyAMode:
            a = annotate_polya(
                Window(1018, 22), self.SEÑALES, utr_length=UTR, mode=modo
            )
            self.assertIn(modo.value, a.veredicto.reason)


if __name__ == "__main__":
    unittest.main()


class TestIntegracion(unittest.TestCase):
    """Los cinco campos llegan a la tabla, y los tres modos al informe."""

    SONDA = "GCGTCAGTACGATCGAATTACT" * 12

    def _tiling(self, modo=PolyAMode.ESCALONADO):
        from shmir_design.tiling import tile_utr

        return tile_utr(self.SONDA, polya_mode=modo)

    def test_las_cinco_columnas_estan_en_el_TSV(self):
        cabecera = self._tiling().format_tsv().splitlines()[0].split("\t")
        for campo in (
            "polyA_hexamero", "polyA_clase", "polyA_posicion_rel",
            "polyA_solapa_seed", "polyA_veredicto",
        ):
            self.assertIn(campo, cabecera)

    def test_el_veredicto_de_la_columna_coincide_con_el_del_filtro(self):
        tiling = self._tiling()
        cabecera = tiling.format_tsv().splitlines()[0].split("\t")
        col = cabecera.index("polyA_veredicto")
        filtro = cabecera.index("zona_prohibida_polyA")
        for fila in tiling.format_tsv().splitlines()[1:]:
            campos = fila.split("\t")
            self.assertEqual(campos[col], campos[filtro])

    def test_el_modo_por_defecto_es_el_escalonado(self):
        """Regresion: cambiar el criterio por defecto en silencio esta prohibido."""
        self.assertIs(self._tiling().polya_mode, PolyAMode.ESCALONADO)

    def test_el_informe_saca_los_tres_modos(self):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report

        tiling = self._tiling()
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=3))
        texto = text_report(
            species="sonda", tiling=tiling, selection=seleccion, scaffold=SGEP_SCAFFOLD
        )
        for modo in PolyAMode:
            self.assertIn(modo.value, texto)

    def test_el_informe_explica_la_geometria_del_corte(self):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report

        tiling = self._tiling()
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=3))
        texto = text_report(
            species="sonda", tiling=tiling, selection=seleccion, scaffold=SGEP_SCAFFOLD
        )
        self.assertIn("10-30 nt aguas abajo", texto)

    def test_la_comparacion_dice_si_los_tres_modos_coinciden(self):
        from shmir_design.selection import SelectionConfig, polya_mode_comparison

        comparacion = polya_mode_comparison(self._tiling(), SelectionConfig())
        self.assertIsInstance(comparacion.stable, bool)
        self.assertEqual(set(comparacion.selections), {m.value for m in PolyAMode})
