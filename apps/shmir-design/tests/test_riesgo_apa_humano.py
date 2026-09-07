"""El barrido humano trae sus DOS señales de APA desde el principio.

Regla 5: escritos antes.

El 3'UTR humano no tiene `AATAAA` ni una vez, pero si dos `ATTAAA` clasificadas
`APA_POSIBLE` en `3utr:955` y `3utr:1167`. Entran con la MISMA maquinaria que la murina
—`TECHO`, `fraccion_isoforma_larga = None`— porque son exactamente el mismo tipo de
riesgo: candidato, no medido.

Importa porque condicionan la mitad DISTAL, que es donde cae el bloque conservado de
`3utr:1507-1532`.

Datos reales: NM_000311.5, 1606 nt, md5 f7fdb4a8…
"""

import unittest

from shmir_design.polya import (
    CLEAVAGE_MAX,
    RiskState,
    SignalClass,
    Window,
    find_polya_signals,
    polya_risk,
)
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.selection import apa_ceiling_table, is_eligible
from shmir_design.tiling import tile_utr

HUMANO = REFERENCES["NM_000311.5"]


@unittest.skipUnless(fixture_available(HUMANO), "NOT_RUN: falta el fixture humano")
class TestLasDosATTAAAHumanas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3 = load_3utr(HUMANO)
        cls.signals = find_polya_signals(cls.utr3)
        cls.tiling = tile_utr(cls.utr3)
        cls.tabla = apa_ceiling_table(cls.tiling)

    def test_son_las_dos_y_estan_donde_estan(self):
        apa = [
            s for s in self.signals
            if s.classification is SignalClass.APA_POSSIBLE
        ]
        self.assertEqual([(s.motif, s.position) for s in apa],
                         [("ATTAAA", 955), ("ATTAAA", 1167)])

    def test_una_ventana_por_detras_sale_TECHO_no_FAIL(self):
        señal = [s for s in self.signals if s.position == 955][0]
        riesgo = polya_risk(
            Window(start=señal.end + CLEAVAGE_MAX + 5, length=22),
            [señal],
            utr_length=len(self.utr3),
        )
        self.assertIs(riesgo.truncamiento, RiskState.TECHO)

    def test_y_su_techo_esta_SIN_MEDIR(self):
        señal = [s for s in self.signals if s.position == 1167][0]
        riesgo = polya_risk(
            Window(start=señal.end + CLEAVAGE_MAX + 5, length=22),
            [señal],
            utr_length=len(self.utr3),
        )
        self.assertIsNone(riesgo.fraccion_isoforma_larga)

    # ── las cifras que hay que emitir ya ──────────────────────────────────────
    def test_la_tabla_trae_una_fila_por_señal(self):
        self.assertEqual([f.signal.position for f in self.tabla], [955, 1167])

    def test_hay_293_ventanas_elegibles(self):
        # 293 desde el 2026-09-07: el homopolímero pasa a medirse sobre la guía y la
        # pasajera (errata nº 144) y eso también muerde en el humano — eran 309.
        self.assertEqual(self.tabla[0].eligible_total, 293)

    def test_la_de_955_deja_95_por_detras(self):
        fila = self.tabla[0]
        self.assertEqual(fila.behind, 95)
        self.assertAlmostEqual(fila.fraction, 95 / 293, places=4)

    def test_la_de_1167_deja_71(self):
        self.assertEqual(self.tabla[1].behind, 71)

    def test_y_las_de_la_banda_de_cada_una(self):
        # Eran 6 y 6; la segunda baja a 5 con el filtro de la molécula.
        self.assertEqual([f.in_band for f in self.tabla], [6, 5])

    def test_la_segunda_es_subconjunto_de_la_primera(self):
        # Estar por detras del corte de 1167 implica estarlo del de 955.
        self.assertLess(self.tabla[1].behind, self.tabla[0].behind)

    def test_la_fila_se_describe_con_las_dos_cifras(self):
        texto = self.tabla[0].describe()
        self.assertIn("95", texto)
        self.assertIn("293", texto)
        self.assertIn("32.4", texto)


@unittest.skipUnless(fixture_available(HUMANO), "NOT_RUN: falta el fixture humano")
class TestElBloqueConservado(unittest.TestCase):
    """3utr:1507-1532 cae por detras de las DOS, y ademas no aporta ningun candidato."""

    @classmethod
    def setUpClass(cls):
        cls.utr3 = load_3utr(HUMANO)
        cls.tiling = tile_utr(cls.utr3)

    def test_esta_por_detras_de_los_dos_cortes(self):
        cortes = [
            s.end + CLEAVAGE_MAX
            for s in find_polya_signals(self.utr3)
            if s.classification is SignalClass.APA_POSSIBLE
        ]
        self.assertTrue(all(1507 > c for c in cortes))

    def test_pero_hoy_no_aporta_NI_UN_candidato(self):
        # 47 ventanas lo solapan y ninguna supera los filtros biofisicos, asi que la
        # pregunta del APA sobre ese bloque es hoy academica.
        solapan = [
            w for w in self.tiling.windows
            if w.window.start <= 1532 and w.window.end >= 1507
        ]
        self.assertEqual(len(solapan), 47)
        self.assertEqual([w for w in solapan if is_eligible(w)], [])

    def test_y_el_motivo_no_es_el_APA(self):
        from shmir_design.filters import FilterState

        solapan = [
            w for w in self.tiling.windows
            if w.window.start <= 1532 and w.window.end >= 1507
        ]
        motivos = {
            r.name for w in solapan for r in w.filters
            if r.state is FilterState.FAIL
        }
        self.assertEqual(motivos, {"GC", "homopolimero", "asimetria"})
        self.assertNotIn("zona_prohibida_polyA", motivos)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(fixture_available(HUMANO), "NOT_RUN: falta el fixture humano")
class TestElInformeHumanoLasSacaLasDOS(unittest.TestCase):
    """El bloque de polyA no puede enseñar solo la dominante cuando hay dos."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report

        tiling = tile_utr(load_3utr(HUMANO))
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=6))
        cls.texto = text_report(
            species="humano", tiling=tiling, selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
        )
        cls.bloque = cls.texto.split("── Riesgo de polyA")[1].split("── Que se ha")[0]

    def test_salen_las_dos_señales_con_su_posicion(self):
        self.assertIn("3utr:955", self.bloque)
        self.assertIn("3utr:1167", self.bloque)

    def test_con_la_fraccion_de_elegibles_que_condiciona_cada_una(self):
        self.assertIn("95 de 293", self.bloque)
        self.assertIn("71 de 293", self.bloque)

    def test_y_los_porcentajes(self):
        self.assertIn("32.4%", self.bloque)
        self.assertIn("24.2%", self.bloque)

    def test_dice_que_el_techo_de_las_dos_esta_sin_medir(self):
        self.assertIn("INDETERMINADO", self.bloque)

    def test_la_banda_de_corte_va_aparte_de_lo_que_esta_detras(self):
        # 6 en la banda de cada una: PENALIZADO, no TECHO. Sumarlas seria inventar.
        self.assertIn("6 en la banda", self.bloque)
