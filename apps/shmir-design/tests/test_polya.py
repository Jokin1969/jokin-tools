"""Tests de los guardarrailes de poliadenilacion sobre el 3'UTR.

Regla 5: escritos antes que `shmir_design/polya.py`.

Datos reales usados aqui (ver `data/reference/PROCEDENCIA.md`):

- Raton, 3'UTR de 1242 nt: AATAAA en 288 (a 949 nt del extremo) y ATTAAA en 1214
  (a 23 nt del extremo). Coordenadas verificadas por el responsable del proyecto.
- Humano, 3'UTR de 1606 nt: ninguna AATAAA canonica; ATTAAA en 1582 (a 19 nt del
  extremo). La ventana que empieza en 1581 es `AATTAAACGAGCGAAGATGAGC`, 22 nt.

El unico fragmento de secuencia real que aparece en estos tests es esa ventana humana
de 22 nt. Los casos de raton se prueban por
coordenadas, no con secuencia: regla 1, no se fabrica un 3'UTR de 1242 nt para que un
test tenga algo que leer. Los tests de extremo a extremo sobre los 3'UTR completos
estan al final y se SALTAN de forma visible mientras falten los fixtures.
"""

import unittest

from shmir_design.errors import InvalidSequenceError, MissingSequenceError
from shmir_design.filters import FilterState, Verdict
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.polya import (
    APA_MIN_DISTANCE,
    SIGNAL_FLANK,
    TERMINAL_MAX_DISTANCE,
    TERMINAL_MIN_DISTANCE,
    SignalClass,
    Tercio,
    Window,
    analyze_3utr,
    annotate_3utr,
    classify_signal,
    find_polya_signals,
)

# ─── Datos reales ────────────────────────────────────────────────────────────
HUMAN_UTR_LENGTH = 1606
HUMAN_WINDOW_START = 1581
HUMAN_WINDOW_SEQ = "AATTAAACGAGCGAAGATGAGC"
MOUSE_UTR_LENGTH = 1242


class TestFragmentoRealHumano(unittest.TestCase):
    """Busqueda sobre la ventana humana real de 22 nt que empieza en 1581."""

    def signals(self):
        return find_polya_signals(
            HUMAN_WINDOW_SEQ,
            first_position=HUMAN_WINDOW_START,
            utr_length=HUMAN_UTR_LENGTH,
        )

    def test_encuentra_attaaa_en_1582(self):
        signals = self.signals()
        self.assertEqual([(s.motif, s.position) for s in signals], [("ATTAAA", 1582)])

    def test_no_hay_aataaa_canonica_en_el_fragmento(self):
        self.assertEqual([s for s in self.signals() if s.is_canonical], [])

    def test_distancia_al_extremo_es_19(self):
        self.assertEqual(self.signals()[0].distance_to_3p, 19)

    def test_es_senal_terminal_probable(self):
        self.assertIs(self.signals()[0].classification, SignalClass.TERMINAL_PROBABLE)

    def test_solapamientos_no_se_pierden(self):
        """`AATAAA` y `ATTAAA` solapados deben reportarse los dos."""
        signals = find_polya_signals("CCAATAAATTAAACC", first_position=1)
        self.assertEqual(
            [(s.motif, s.position) for s in signals],
            [("AATAAA", 3), ("ATTAAA", 8)],
        )


class TestClasificacionPorCoordenadas(unittest.TestCase):
    """Clasificacion con las coordenadas reales, sin secuencia (regla 1)."""

    def test_aataaa_raton_288_es_apa_posible(self):
        signal = classify_signal("AATAAA", 288, MOUSE_UTR_LENGTH)
        self.assertEqual(signal.distance_to_3p, 949)
        self.assertIs(signal.classification, SignalClass.APA_POSSIBLE)
        self.assertTrue(signal.is_canonical)

    def test_attaaa_raton_1214_es_senal_terminal(self):
        signal = classify_signal("ATTAAA", 1214, MOUSE_UTR_LENGTH)
        self.assertEqual(signal.distance_to_3p, 23)
        self.assertIs(signal.classification, SignalClass.TERMINAL_PROBABLE)
        self.assertFalse(signal.is_canonical)

    def test_attaaa_humano_1582_es_senal_terminal(self):
        signal = classify_signal("ATTAAA", 1582, HUMAN_UTR_LENGTH)
        self.assertEqual(signal.distance_to_3p, 19)
        self.assertIs(signal.classification, SignalClass.TERMINAL_PROBABLE)

    def test_variante_no_canonica_lejos_del_extremo_no_es_apa(self):
        """Solo la AATAAA canonica a >100 nt cuenta como APA posible."""
        signal = classify_signal("ATTAAA", 288, MOUSE_UTR_LENGTH)
        self.assertIs(signal.classification, SignalClass.OTHER)

    def test_limites_de_la_ventana_terminal(self):
        length = 1000
        dentro_min = classify_signal("AATAAA", length - 5 - TERMINAL_MAX_DISTANCE, length)
        dentro_max = classify_signal("AATAAA", length - 5 - TERMINAL_MIN_DISTANCE, length)
        fuera = classify_signal("AATAAA", length - 5 - (TERMINAL_MIN_DISTANCE - 1), length)
        self.assertIs(dentro_min.classification, SignalClass.TERMINAL_PROBABLE)
        self.assertIs(dentro_max.classification, SignalClass.TERMINAL_PROBABLE)
        self.assertIs(fuera.classification, SignalClass.OTHER)

    def test_canonica_justo_en_100_no_es_apa(self):
        """'a mas de 100 nt' es estricto."""
        length = 1000
        justo = classify_signal("AATAAA", length - 5 - APA_MIN_DISTANCE, length)
        pasado = classify_signal("AATAAA", length - 5 - (APA_MIN_DISTANCE + 1), length)
        self.assertIs(justo.classification, SignalClass.OTHER)
        self.assertIs(pasado.classification, SignalClass.APA_POSSIBLE)

    def test_motivo_desconocido_se_rechaza(self):
        with self.assertRaises(ValueError):
            classify_signal("GGGGGG", 100, 1000)


class TestZonasProhibidas(unittest.TestCase):
    """Ninguna ventana puede solapar una señal de poliadenilacion ±10 nt."""

    def human_signals(self):
        return find_polya_signals(
            HUMAN_WINDOW_SEQ,
            first_position=HUMAN_WINDOW_START,
            utr_length=HUMAN_UTR_LENGTH,
        )

    def annotate(self, windows):
        return annotate_3utr(windows, self.human_signals(), HUMAN_UTR_LENGTH)

    def test_ventana_1581_humana_queda_excluida(self):
        report = self.annotate([Window(HUMAN_WINDOW_START, 22, label="w1581")])
        window = report.windows[0]
        self.assertIs(window.zona_prohibida.state, FilterState.FAIL)
        self.assertIn("1582", window.zona_prohibida.reason)

    def test_la_zona_prohibida_llega_hasta_el_flanco(self):
        signal = self.human_signals()[0]
        limite = signal.forbidden_start  # 1572
        self.assertEqual(limite, signal.position - SIGNAL_FLANK)
        justo_fuera = Window(limite - 22, 22, label="fuera")   # termina en limite - 1
        justo_dentro = Window(limite - 21, 22, label="dentro")  # termina en limite
        report = self.annotate([justo_fuera, justo_dentro])
        self.assertIs(report.windows[0].zona_prohibida.state, FilterState.PASS)
        self.assertIs(report.windows[1].zona_prohibida.state, FilterState.FAIL)

    def test_ventana_lejana_pasa(self):
        report = self.annotate([Window(1000, 22, label="lejana")])
        self.assertIs(report.windows[0].zona_prohibida.state, FilterState.PASS)

    def test_ninguna_ventana_desaparece_del_informe(self):
        windows = [Window(100, 22), Window(HUMAN_WINDOW_START, 22), Window(1000, 22)]
        report = self.annotate(windows)
        self.assertEqual(len(report.windows), 3)
        self.assertTrue(all(w.zona_prohibida.state is not None for w in report.windows))

    def test_ventana_fuera_del_utr_es_error_explicito(self):
        with self.assertRaises(ValueError) as ctx:
            self.annotate([Window(HUMAN_UTR_LENGTH - 5, 22, label="desbordada")])
        self.assertIn("desbordada", str(ctx.exception))


class TestTercios(unittest.TestCase):
    """Cada ventana se anota con el tercio del 3'UTR en que cae."""

    def tercio(self, start, length, utr_length):
        report = annotate_3utr([Window(start, length)], [], utr_length)
        return report.windows[0].tercio

    def test_ventana_raton_en_288_es_proximal(self):
        self.assertIs(self.tercio(288, 22, MOUSE_UTR_LENGTH), Tercio.PROXIMAL)

    def test_ventana_raton_en_1214_es_distal(self):
        self.assertIs(self.tercio(1214, 22, MOUSE_UTR_LENGTH), Tercio.DISTAL)

    def test_ventana_raton_intermedia_es_media(self):
        self.assertIs(self.tercio(600, 22, MOUSE_UTR_LENGTH), Tercio.MEDIO)

    def test_ventana_humana_en_1581_es_distal(self):
        self.assertIs(self.tercio(HUMAN_WINDOW_START, 22, HUMAN_UTR_LENGTH), Tercio.DISTAL)

    def test_primera_y_ultima_posicion(self):
        self.assertIs(self.tercio(1, 1, 999), Tercio.PROXIMAL)
        self.assertIs(self.tercio(999, 1, 999), Tercio.DISTAL)


class TestRiesgoAPA(unittest.TestCase):
    """APA proximal: aviso destacado y anotacion, nunca exclusion automatica."""

    def mouse_report(self, windows):
        signals = [
            classify_signal("AATAAA", 288, MOUSE_UTR_LENGTH),
            classify_signal("ATTAAA", 1214, MOUSE_UTR_LENGTH),
        ]
        return annotate_3utr(windows, signals, MOUSE_UTR_LENGTH)

    def test_ventana_corriente_abajo_del_apa_lleva_riesgo(self):
        report = self.mouse_report([Window(500, 22, label="abajo")])
        window = report.windows[0]
        self.assertTrue(window.riesgo_APA)
        self.assertIn(288, [s.position for s in window.apa_upstream])

    def test_ventana_corriente_abajo_no_se_excluye(self):
        report = self.mouse_report([Window(500, 22, label="abajo")])
        self.assertIs(report.windows[0].zona_prohibida.state, FilterState.PASS)

    def test_ventana_corriente_arriba_no_lleva_riesgo(self):
        report = self.mouse_report([Window(100, 22, label="arriba")])
        self.assertFalse(report.windows[0].riesgo_APA)

    def test_ventana_que_solapa_el_apa_se_excluye_por_zona_prohibida(self):
        report = self.mouse_report([Window(285, 22, label="sobre_apa")])
        self.assertIs(report.windows[0].zona_prohibida.state, FilterState.FAIL)

    def test_se_emite_aviso_destacado(self):
        report = self.mouse_report([Window(500, 22, label="abajo")])
        avisos = [a for a in report.avisos if a.code == "APA_PROXIMAL"]
        self.assertEqual(len(avisos), 1)
        self.assertIn("288", avisos[0].message)
        self.assertIn("abajo", avisos[0].affected)

    def test_sin_apa_no_hay_aviso(self):
        signals = [classify_signal("ATTAAA", 1582, HUMAN_UTR_LENGTH)]
        report = annotate_3utr([Window(1000, 22)], signals, HUMAN_UTR_LENGTH)
        self.assertEqual([a for a in report.avisos if a.code == "APA_PROXIMAL"], [])

    def test_el_aviso_aparece_en_la_salida_de_texto(self):
        report = self.mouse_report([Window(500, 22, label="abajo")])
        texto = report.format_text()
        self.assertIn("AVISO", texto)
        self.assertIn("APA", texto)

    def test_el_aviso_resume_y_no_enumera_las_ventanas(self):
        """Con el APA de raton en 288 son casi todas: enumerarlas es ruido."""
        windows = [
            Window(500, 22, label="abajo_1"),
            Window(600, 22, label="abajo_2"),
            Window(100, 22, label="arriba"),
        ]
        aviso = self.mouse_report(windows).avisos[0]
        self.assertNotIn("abajo_1", aviso.message)
        self.assertNotIn("abajo_2", aviso.message)
        self.assertIn("2 de 3", aviso.message)
        self.assertIn("66.7%", aviso.message)
        self.assertIn("500-621", aviso.message)
        self.assertIn("TSV", aviso.message)

    def test_el_aviso_conserva_la_lista_completa_como_dato(self):
        windows = [Window(500, 22, label="abajo_1"), Window(600, 22, label="abajo_2")]
        aviso = self.mouse_report(windows).avisos[0]
        self.assertEqual(aviso.affected, ("abajo_1", "abajo_2"))
        self.assertEqual(aviso.affected_count, 2)
        self.assertEqual(aviso.position_range, (500, 621))
        self.assertAlmostEqual(aviso.affected_pct, 100.0)

    def test_sin_ventanas_afectadas_el_aviso_lo_dice_sin_rango(self):
        aviso = self.mouse_report([Window(100, 22, label="arriba")]).avisos[0]
        self.assertEqual(aviso.affected_count, 0)
        self.assertIsNone(aviso.position_range)
        self.assertIn("0 de 1", aviso.message)


class TestSalidaTSV(unittest.TestCase):
    """La lista completa de ventanas vive en el TSV, no en el aviso."""

    def report(self, windows):
        signals = [classify_signal("AATAAA", 288, MOUSE_UTR_LENGTH)]
        return annotate_3utr(windows, signals, MOUSE_UTR_LENGTH)

    def windows(self):
        return [
            Window(100, 22, label="arriba"),
            Window(285, 22, label="sobre_apa"),
            Window(500, 22, label="abajo"),
        ]

    def test_una_fila_por_ventana_mas_cabecera(self):
        lineas = self.report(self.windows()).format_tsv().splitlines()
        self.assertEqual(len(lineas), 4)
        self.assertEqual(lineas[0].split("\t")[0], "ventana")

    def test_todas_las_filas_tienen_las_mismas_columnas(self):
        lineas = self.report(self.windows()).format_tsv().splitlines()
        anchos = {len(linea.split("\t")) for linea in lineas}
        self.assertEqual(len(anchos), 1)

    def test_la_fila_lleva_estado_tercio_riesgo_y_motivo(self):
        lineas = self.report(self.windows()).format_tsv().splitlines()
        cabecera = lineas[0].split("\t")
        fila = dict(zip(cabecera, lineas[3].split("\t")))
        self.assertEqual(fila["ventana"], "abajo")
        self.assertEqual(fila["inicio"], "500")
        self.assertEqual(fila["tercio"], "medio")
        self.assertEqual(fila["zona_prohibida_polyA"], "PASS")
        self.assertEqual(fila["riesgo_APA"], "True")
        self.assertEqual(fila["apa_upstream"], "288")
        self.assertTrue(fila["motivo"])

    def test_la_ventana_excluida_sale_con_su_motivo(self):
        lineas = self.report(self.windows()).format_tsv().splitlines()
        fila = dict(zip(lineas[0].split("\t"), lineas[2].split("\t")))
        self.assertEqual(fila["zona_prohibida_polyA"], "FAIL")
        self.assertIn("288", fila["motivo"])

    def test_ningun_campo_lleva_tabuladores(self):
        for linea in self.report(self.windows()).format_tsv().splitlines():
            for campo in linea.split("\t"):
                self.assertNotIn("\n", campo)

    def test_not_run_tambien_sale_en_el_tsv(self):
        report = annotate_3utr([Window(500, 22, label="w")], None, MOUSE_UTR_LENGTH)
        self.assertIn("NOT_RUN", report.format_tsv())


class TestReglasDeSecuencia(unittest.TestCase):
    """Regla 1 y regla 2: sin secuencia se aborta, nunca se devuelve None."""

    def test_secuencia_ausente(self):
        with self.assertRaises(MissingSequenceError):
            find_polya_signals(None)

    def test_secuencia_vacia(self):
        with self.assertRaises(MissingSequenceError):
            find_polya_signals("   \n  ")

    def test_caracter_invalido_aborta_con_posicion(self):
        with self.assertRaises(InvalidSequenceError) as ctx:
            find_polya_signals("AATZAA")
        self.assertIn("4", str(ctx.exception))

    def test_no_se_rellena_una_secuencia_corta(self):
        """Una secuencia mas corta que el motivo no se completa: devuelve vacio."""
        self.assertEqual(find_polya_signals("AATA"), [])

    def test_analyze_no_devuelve_none_nunca(self):
        report = analyze_3utr(
            HUMAN_WINDOW_SEQ,
            [Window(HUMAN_WINDOW_START, 22)],
            first_position=HUMAN_WINDOW_START,
            utr_length=HUMAN_UTR_LENGTH,
        )
        self.assertIsNotNone(report)
        self.assertEqual(len(report.windows), 1)


class TestEstadoNotRun(unittest.TestCase):
    """Regla 3: si la busqueda de señales no llego a correr, no se aprueba nada."""

    def test_sin_señales_calculadas_el_filtro_queda_en_not_run(self):
        report = annotate_3utr([Window(500, 22, label="w")], None, MOUSE_UTR_LENGTH)
        window = report.windows[0]
        self.assertIs(window.zona_prohibida.state, FilterState.NOT_RUN)
        self.assertIs(window.verdict, Verdict.INCOMPLETE)

    def test_lista_vacia_no_es_lo_mismo_que_no_haber_corrido(self):
        report = annotate_3utr([Window(500, 22, label="w")], [], MOUSE_UTR_LENGTH)
        self.assertIs(report.windows[0].zona_prohibida.state, FilterState.PASS)
        self.assertIs(report.windows[0].verdict, Verdict.PASS)

    def test_not_run_visible_en_la_salida_de_texto(self):
        report = annotate_3utr([Window(500, 22, label="w")], None, MOUSE_UTR_LENGTH)
        self.assertIn("NOT_RUN", report.format_text())


@unittest.skipUnless(
    all(fixture_available(ref) for ref in REFERENCES.values()),
    "NOT_RUN: faltan los fixtures de data/reference/; añadelos al repositorio o "
    "descargalos con tools/reference_data.py --fetch. No se sustituyen por secuencia "
    "sintetica (regla 1)",
)
class TestUtrCompletos(unittest.TestCase):
    """Sobre los 3'UTR reales, extraidos y verificados desde los fixtures."""

    def raton(self):
        return load_3utr(REFERENCES["NM_011170.3"])

    def humano(self):
        return load_3utr(REFERENCES["NM_000311.5"])

    def test_raton_longitud_y_senales(self):
        seq = self.raton()
        self.assertEqual(len(seq), MOUSE_UTR_LENGTH)
        by_pos = {(s.motif, s.position) for s in find_polya_signals(seq)}
        self.assertIn(("AATAAA", 288), by_pos)
        self.assertIn(("ATTAAA", 1214), by_pos)

    def test_el_aataaa_del_raton_es_el_unico_canonico(self):
        canonicas = [s for s in find_polya_signals(self.raton()) if s.is_canonical]
        self.assertEqual([s.position for s in canonicas], [288])
        self.assertIs(canonicas[0].classification, SignalClass.APA_POSSIBLE)

    def test_humano_no_tiene_aataaa_canonica(self):
        signals = find_polya_signals(self.humano())
        self.assertEqual([s for s in signals if s.is_canonical], [])
        self.assertIn(("ATTAAA", 1582), {(s.motif, s.position) for s in signals})

    def test_humano_ventana_1581_coincide_con_el_fragmento_verificado(self):
        seq = self.humano()
        self.assertEqual(len(seq), HUMAN_UTR_LENGTH)
        window = seq[HUMAN_WINDOW_START - 1 : HUMAN_WINDOW_START - 1 + 22]
        self.assertEqual(window, HUMAN_WINDOW_SEQ)

    def test_la_ventana_1581_queda_excluida_sobre_el_3utr_real(self):
        seq = self.humano()
        report = analyze_3utr(seq, [Window(HUMAN_WINDOW_START, 22, label="w1581")])
        self.assertIs(report.windows[0].zona_prohibida.state, FilterState.FAIL)


if __name__ == "__main__":
    unittest.main()
