"""La ficha de un candidato: todo lo que sabemos de un sitio, en un sitio.

Regla 5: escritos antes.

Reune el veredicto de CADA frente con su procedencia y fecha, la asimetria en sus tres
columnas, el techo de APA con el tramo del que sale, los hexameros cercanos con su clase
y su distancia, el modulo de 149 nt, el cassette de 318 y el historial de BLAST.

Y con la MISMA disciplina que el golden del informe: la ficha se compara **entera**
contra una de referencia, no por presencia de fragmentos. Los tests de presencia
comprueban lo que cada uno espera y no ven lo que falta.
"""

import unittest

from shmir_design.apa import POLYA_DB_PRNP, resolve_measured
from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]


def _piezas():
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(RATON)
    informe = tile_utr(utr3, measured_apa=resolve_measured(utr3, POLYA_DB_PRNP))
    seleccion = select_from_report(
        informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
    )
    return informe, seleccion


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLaFicha(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.dossier import build_dossier

        cls.tiling, cls.seleccion = _piezas()
        cls.ficha = build_dossier(
            species="raton", tiling=cls.tiling, selection=cls.seleccion, start=200,
        )

    def test_identifica_el_sitio(self):
        self.assertEqual(self.ficha.start, 200)
        self.assertEqual(self.ficha.end, 221)

    def test_trae_la_guia_y_la_pasajera(self):
        self.assertEqual(len(self.ficha.guide), 22)
        self.assertTrue(self.ficha.passenger)

    def test_un_sitio_que_NO_esta_en_el_panel_aborta(self):
        from shmir_design.dossier import build_dossier
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError):
            build_dossier(
                species="raton", tiling=self.tiling, selection=self.seleccion,
                start=99999,
            )

    # ── los frentes ──
    def test_trae_TODOS_los_frentes_no_una_seleccion(self):
        from shmir_design.selection import blocking_fronts

        esperados = {f.name for f in blocking_fronts(self.tiling, self.seleccion)}
        # `seed_colision` se PARTE en dos —guia y pasajera— porque son dos consultas y
        # fundirlas escondería la mitad. Los demas van uno a uno.
        esperados.discard("seed_colision")
        esperados |= {"seed_colision:guia", "seed_colision:pasajera"}
        # `offtarget_seed` se PARTE por lo mismo, y ademas es el frente que llego a
        # estar invisible: una sola fila por candidato volveria a esconder la mitad.
        esperados.discard("offtarget_seed")
        esperados |= {"offtarget_seed:guia", "offtarget_seed:pasajera"}
        self.assertEqual({f.name for f in self.ficha.fronts}, esperados)

    def test_cada_frente_lleva_estado_procedencia_y_fecha(self):
        for frente in self.ficha.fronts:
            self.assertIsInstance(frente.state, FilterState)
            self.assertTrue(frente.source, frente.name)
            self.assertTrue(frente.date, frente.name)

    def test_los_dos_frentes_de_off_target_van_SEPARADOS(self):
        nombres = [f.name for f in self.ficha.fronts]
        self.assertIn("especificidad", nombres)
        self.assertIn("offtarget_seed:guia", nombres)
        self.assertIn("offtarget_seed:pasajera", nombres)

    def test_sin_corrida_de_BLAST_la_especificidad_es_NOT_RUN_VISIBLE(self):
        frente = next(f for f in self.ficha.fronts if f.name == "especificidad")
        self.assertIs(frente.state, FilterState.NOT_RUN)
        self.assertIn("NOT_RUN", self.ficha.render())

    # ── asimetria ──
    def test_la_asimetria_va_en_las_TRES_columnas(self):
        self.assertIsNotNone(self.ficha.asymmetry_raw)
        self.assertIsNotNone(self.ficha.penalty)
        self.assertAlmostEqual(
            self.ficha.asymmetry_net,
            self.ficha.asymmetry_raw - self.ficha.penalty, places=6,
        )

    # ── techo ──
    def test_el_techo_dice_de_QUE_TRAMO_sale(self):
        texto = self.ficha.render()
        self.assertIn("3utr:1-251", texto)

    def test_3utr_200_no_lleva_techo_porque_es_inmune(self):
        self.assertIsNone(self.ficha.ceiling)

    # ── hexameros ──
    def test_los_hexameros_cercanos_traen_clase_y_distancia(self):
        self.assertTrue(self.ficha.hexamers)
        cercano = self.ficha.hexamers[0]
        self.assertTrue(cercano.motif)
        self.assertTrue(cercano.classification)
        self.assertIsInstance(cercano.distance, int)

    def test_el_AATATA_de_236_esta_entre_ellos(self):
        self.assertIn(236, [h.position for h in self.ficha.hexamers])

    # ── bloques ──
    def test_trae_el_modulo_de_149_y_el_cassette_de_318(self):
        self.assertEqual(len(self.ficha.module), 149)
        self.assertEqual(len(self.ficha.cassette), 318)

    # ── historial ──
    def test_sin_almacen_el_historial_esta_VACIO_y_se_dice(self):
        self.assertEqual(self.ficha.blast_history, ())
        self.assertIn("sin corridas", self.ficha.render().lower())


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLaFichaConCorridaDeBLAST(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design import blast
        from shmir_design.blast_store import BlastDatabase, BlastRun, BlastStore
        from shmir_design.dossier import build_dossier

        cls.tiling, cls.seleccion = _piezas()
        ventana = cls.seleccion.window_of(
            next(c for c in cls.seleccion.selection.chosen if c.start == 200)
        )
        guia = ventana.evaluation.guide.replace("U", "T")
        nombre = "raton_pos200_guia"
        consulta = blast.QueryFasta.from_records(((nombre, guia),))
        cls.almacen = BlastStore()
        cls.almacen.add(
            BlastRun.create(
                run_id="r1", date="2026-08-26", uploaded_by="responsable del proyecto",
                params=blast.DEFAULTS,
                database=BlastDatabase(
                    name="refseq_rna", version="2026-08-26", md5="a" * 32, remote=False,
                ),
                query=consulta,
                raw=(
                    f"{nombre}\tNM_011170.3\t100.000\t22\t0\t0\t1\t22\t1170\t1191"
                    f"\t1e-05\t44.1\n"
                ),
            )
        )
        cls.ficha = build_dossier(
            species="raton", tiling=cls.tiling, selection=cls.seleccion, start=200,
            store=cls.almacen,
        )

    def test_el_historial_trae_la_corrida(self):
        self.assertEqual(len(self.ficha.blast_history), 1)

    def test_y_la_especificidad_deja_de_ser_NOT_RUN(self):
        frente = next(f for f in self.ficha.fronts if f.name == "especificidad")
        self.assertIsNot(frente.state, FilterState.NOT_RUN)

    def test_la_procedencia_es_la_corrida_con_su_fecha(self):
        frente = next(f for f in self.ficha.fronts if f.name == "especificidad")
        self.assertIn("r1", frente.source)
        self.assertEqual(frente.date, "2026-08-26")

    def test_el_otro_frente_SIGUE_en_NOT_RUN(self):
        # Una corrida de BLAST no cubre el off-target por seed. Nunca.
        for hebra in ("guia", "pasajera"):
            frente = next(
                f for f in self.ficha.fronts if f.name == f"offtarget_seed:{hebra}"
            )
            self.assertIs(frente.state, FilterState.NOT_RUN)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestUnFrenteCERRADONoSaleComoNOT_RUN(unittest.TestCase):
    """Decir que falta algo resuelto engaña tanto como lo contrario."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.dossier import build_dossier

        tiling, seleccion = _piezas()
        cls.ficha = build_dossier(
            species="raton", tiling=tiling, selection=seleccion, start=200
        )

    def test_la_fraccion_de_isoforma_larga_esta_CERRADA(self):
        frente = next(
            f for f in self.ficha.fronts if f.name == "fraccion_isoforma_larga"
        )
        self.assertIsNot(frente.state, FilterState.NOT_RUN)

    def test_y_su_procedencia_lo_dice(self):
        frente = next(
            f for f in self.ficha.fronts if f.name == "fraccion_isoforma_larga"
        )
        self.assertIn("CERRADO", frente.source)

    def test_los_demas_siguen_abiertos(self):
        abiertos = [f.name for f in self.ficha.fronts if f.state is FilterState.NOT_RUN]
        self.assertIn("especificidad", abiertos)
        self.assertIn("offtarget_seed:guia", abiertos)
        self.assertIn("offtarget_seed:pasajera", abiertos)
