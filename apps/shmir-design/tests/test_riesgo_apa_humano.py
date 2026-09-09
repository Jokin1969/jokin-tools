"""El barrido humano trae sus señales de APA desde el principio.

Regla 5: escritos antes.

El 3'UTR humano no tiene `AATAAA` ni una vez, pero si dos `ATTAAA` clasificadas
`APA_POSIBLE` en `3utr:955` y `3utr:1167`. Entran con la MISMA maquinaria que la murina
porque son exactamente el mismo tipo de riesgo.

**ERAN DOS Y SON TRES DESDE EL 2026-09-09**, y la prosa se mueve con el dato (principio
nº 11): con `polya_db_human.tsv` en el depósito, el `AGTAAA` de `3utr:233` entra
**PROMOVIDO por uso medido** —el caso inverso al de una canónica sin dato, y el mismo del
`AATATA` murino de `3utr:236`—, y las dos `ATTAAA` dejan de ser «candidatas, no medidas»
para quedar CONFIRMADAS por medida. `fraccion_isoforma_larga` ya no es `None` en el
tilado del depósito.

**Los DOS números conviven a propósito y no se reconcilian**: `find_polya_signals` sobre
el 3'UTR pelado sigue viendo DOS —es la cascada de PREDICCIÓN, y ahí `AGTAAA` es una
variante rara que sale `OTRA`— y la tabla de techos ve TRES, porque la medida SUSTITUYE a
la predicción. **La diferencia entre esos dos números ES el efecto de la medida**, así que
los tests de cada vía dicen lo suyo y ninguno se «arregla» para que coincidan.

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
    #
    # SON TRES DESDE EL 2026-09-09, y la tercera no la da la predicción: con
    # `polya_db_human.tsv` en el depósito entra el `AGTAAA` de `3utr:233`, PROMOVIDO por
    # uso medido. `find_polya_signals` sobre el 3'UTR pelado sigue viendo DOS —es la
    # cascada de predicción, y ahí `AGTAAA` es una variante rara que sale `OTRA`— así que
    # los dos primeros tests de esta clase siguen diciendo «dos» y NO se tocan: miden otra
    # cosa. La diferencia entre esos dos números ES el efecto de la medida.
    def test_la_tabla_trae_una_fila_por_señal_y_ahora_son_TRES(self):
        self.assertEqual([f.signal.position for f in self.tabla], [233, 955, 1167])

    def test_hay_282_ventanas_elegibles(self):
        # 282 desde el 2026-09-09: la promoción del `AGTAAA` de 3utr:233 tumba por solape
        # ESTERICO 11 ventanas que superaban todo lo demás — eran 293. Antes de eso fueron
        # 309, hasta que el homopolímero pasó a medirse sobre la molécula (errata nº 144).
        self.assertEqual(self.tabla[0].eligible_total, 282)

    def test_la_de_233_deja_250_por_detras(self):
        fila = self.tabla[0]
        self.assertEqual(fila.behind, 250)
        self.assertAlmostEqual(fila.fraction, 250 / 282, places=4)

    def test_la_de_955_deja_95_por_detras(self):
        fila = self.tabla[1]
        self.assertEqual(fila.behind, 95)
        self.assertAlmostEqual(fila.fraction, 95 / 282, places=4)

    def test_la_de_1167_deja_71(self):
        self.assertEqual(self.tabla[2].behind, 71)

    def test_y_las_de_la_banda_de_cada_una(self):
        self.assertEqual([f.in_band for f in self.tabla], [4, 6, 5])

    def test_cada_una_es_subconjunto_de_la_anterior(self):
        # Estar por detras del corte de 1167 implica estarlo de los otros dos.
        detras = [f.behind for f in self.tabla]
        self.assertEqual(detras, sorted(detras, reverse=True))

    def test_la_fila_se_describe_con_las_dos_cifras(self):
        texto = self.tabla[1].describe()
        self.assertIn("95", texto)
        self.assertIn("282", texto)
        self.assertIn("33.7", texto)


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
class TestElInformeHumanoLasSacaTODAS(unittest.TestCase):
    """El bloque de polyA no puede enseñar solo la dominante cuando hay varias.

    **Eran DOS y son TRES desde el 2026-09-09**, y el test se mueve con la decisión en
    vez de bloquearla (principio nº 56): con `polya_db_human.tsv` en el depósito, el
    `AGTAAA` de `3utr:233` entra **promovido por medida de uso**, que es exactamente el
    caso del `AATATA` murino de `3utr:236`. Lo que este fichero fija no es cuántas hay
    —eso lo mueve el dato— sino que salgan **todas** con su fracción de elegibles.
    """

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

    def test_salen_las_TRES_señales_con_su_posicion(self):
        for posicion in ("3utr:233", "3utr:955", "3utr:1167"):
            with self.subTest(posicion):
                self.assertIn(posicion, self.bloque)

    def test_y_dice_que_son_TRES(self):
        # El recuento va en el encabezado del bloque: con una sola cifra que se quede
        # atrás, el lector cuenta dos y hay tres.
        self.assertIn("SEÑALES DE APA POSIBLE: 3", self.bloque)

    def test_con_la_fraccion_de_elegibles_que_condiciona_cada_una(self):
        # 282 y no 293: la promoción del AGTAAA tumba 11 ventanas por solape ESTERICO,
        # que es la factura que el propio bloque emite («LO QUE CUESTA LA PROMOCION»).
        for fila in ("250 de 282", "95 de 282", "71 de 282"):
            with self.subTest(fila):
                self.assertIn(fila, self.bloque)

    def test_y_los_porcentajes(self):
        for porcentaje in ("88.7%", "33.7%", "25.2%"):
            with self.subTest(porcentaje):
                self.assertIn(porcentaje, self.bloque)

    def test_el_techo_de_las_bandas_de_corte_sigue_INDETERMINADO(self):
        # Lo que la medida NO resuelve: dentro de la banda de 20 nt no se sabe de que
        # lado cae la ventana, y eso es PENALIZADO, no TECHO. Colapsarlo a un número
        # inventaria una precisión que no hay.
        self.assertIn("INDETERMINADO", self.bloque)

    def test_la_banda_de_corte_va_aparte_de_lo_que_esta_detras(self):
        # 6 en la banda de cada una: PENALIZADO, no TECHO. Sumarlas seria inventar.
        self.assertIn("6 en la banda", self.bloque)
