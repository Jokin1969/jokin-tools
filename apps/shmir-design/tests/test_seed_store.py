"""El almacen de corridas de seed: mismo patron que el de BLAST.

Regla 5: escritos antes.

CRITERIOS DE ACEPTACION:

  1. Una corrida con ventana 2-7 NO puede presentarse como 2-8.
  2. Guia y pasajera NUNCA se funden en un veredicto.
  3. Un candidato sin corrida sigue en `NOT_RUN` visible.
  4. La tasa base aparece SIEMPRE junto a los avisos.
"""

import unittest
from pathlib import Path

from shmir_design import seed_scan
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.seed_store import SeedRun, SeedStore

MATURE = Path(__file__).resolve().parent.parent / "data" / "reference" / "mature.fa"
RATON = REFERENCES["NM_011170.3"]
HAY = MATURE.is_file() and fixture_available(RATON)


def _corrida(ventana="2-8", **cambios):
    from shmir_design.mirna import load_mature_fa
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    maduros = load_mature_fa(MATURE, version="23")
    informe = tile_utr(load_3utr(RATON), mature=maduros)
    seleccion = select_from_report(informe, SelectionConfig(n_candidates=10))
    scan = seed_scan.run_scan(
        seleccion, mature=maduros,
        params=seed_scan.DEFAULTS.with_changes(window=ventana),
        species="raton", starts=(10, 60), guides=True, passengers=True,
    )
    base = dict(
        run_id="s1", date="2026-08-26", ran_by="responsable del proyecto", scan=scan
    )
    base.update(cambios)
    return SeedRun.create(**base)


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestElRegistroEsINMUTABLE(unittest.TestCase):

    def setUp(self):
        self.corrida = _corrida()

    def test_trae_todo_lo_que_hay_que_guardar(self):
        c = self.corrida
        self.assertEqual(c.run_id, "s1")
        self.assertEqual(c.date, "2026-08-26")
        self.assertTrue(c.ran_by)
        self.assertIn("mature.fa", c.source)
        self.assertIn("23", c.source)
        self.assertEqual(len(c.result_md5), 32)

    def test_guarda_el_crudo_ademas_del_parseado(self):
        self.assertTrue(self.corrida.raw)
        self.assertTrue(self.corrida.results)

    def test_los_parametros_van_COMPLETOS(self):
        texto = "\n".join(self.corrida.describe())
        for trozo in ("window=", "especie=", "nivel="):
            self.assertIn(trozo, texto)

    def test_no_se_puede_modificar(self):
        from dataclasses import FrozenInstanceError

        with self.assertRaises(FrozenInstanceError):
            self.corrida.run_id = "otro"

    def test_sin_quien_la_corrio_ABORTA(self):
        with self.assertRaises(ValueError):
            _corrida(ran_by="")


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestCriterio1_LaVentanaVIAJA(unittest.TestCase):

    def test_la_de_2_7_lo_dice_en_su_veredicto(self):
        corrida = _corrida("2-7")
        motivo = corrida.verdict("raton_pos10_guia").reason
        self.assertIn("2-7", motivo)

    def test_y_NO_puede_presentarse_como_estandar(self):
        self.assertFalse(_corrida("2-7").params.is_standard)

    def test_la_de_2_8_si(self):
        self.assertTrue(_corrida("2-8").params.is_standard)

    def test_las_dos_dan_heptameros_de_longitud_distinta(self):
        a = _corrida("2-8").results[0].heptamer
        b = _corrida("2-7").results[0].heptamer
        self.assertEqual((len(a), len(b)), (7, 6))


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestCriterio2_GuiaYPasajeraNoSeFunden(unittest.TestCase):

    def setUp(self):
        self.almacen = SeedStore()
        self.almacen.add(_corrida())

    def test_hay_veredicto_por_HEBRA_y_son_consultas_distintas(self):
        guia = self.almacen.verdict_for("raton_pos10_guia")
        pasajera = self.almacen.verdict_for("raton_pos10_pasajera")
        self.assertIsNot(guia.state, FilterState.NOT_RUN)
        self.assertIsNot(pasajera.state, FilterState.NOT_RUN)

    def test_el_almacen_NO_ofrece_un_veredicto_por_candidato(self):
        self.assertFalse(hasattr(self.almacen, "verdict_for_candidate"))

    def test_el_motivo_dice_de_QUE_hebra_es(self):
        self.assertIn("guia", self.almacen.verdict_for("raton_pos10_guia").reason)
        self.assertIn(
            "pasajera", self.almacen.verdict_for("raton_pos10_pasajera").reason
        )


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestCriterio3_SinCorridaSigueEnNOT_RUN(unittest.TestCase):

    def test_sin_corrida_es_NOT_RUN_visible(self):
        motivo = SeedStore().verdict_for("raton_pos999_guia")
        self.assertIs(motivo.state, FilterState.NOT_RUN)
        self.assertIn("ninguna corrida", motivo.reason.lower())
        self.assertIn("NOT_RUN no es PASS", motivo.reason)

    def test_una_corrida_de_OTRA_hebra_no_lo_cambia(self):
        almacen = SeedStore()
        almacen.add(_corrida())
        self.assertIs(
            almacen.verdict_for("raton_pos999_pasajera").state, FilterState.NOT_RUN
        )


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestCriterio4_LaTasaBaseVaSiempreConLosAvisos(unittest.TestCase):

    def setUp(self):
        self.almacen = SeedStore()
        self.almacen.add(_corrida())

    def test_todo_veredicto_de_AVISO_la_lleva(self):
        avisos = [
            self.almacen.verdict_for(r.query)
            for r in self.almacen.runs[0].results if r.level == "AVISO"
        ]
        if not avisos:
            self.skipTest("esta corrida no produjo ningun AVISO")
        for resultado in avisos:
            self.assertIn("azar", resultado.reason.lower())

    def test_y_tambien_los_LIMPIO_para_no_dar_una_falsa_calma(self):
        limpios = [
            self.almacen.verdict_for(r.query)
            for r in self.almacen.runs[0].results if r.level == "LIMPIO"
        ]
        for resultado in limpios:
            self.assertIn("azar", resultado.reason.lower())


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestNadaSeSOBRESCRIBE(unittest.TestCase):

    def test_dos_corridas_se_suman(self):
        almacen = SeedStore()
        almacen.add(_corrida(run_id="s1"))
        almacen.add(_corrida(run_id="s2", date="2026-08-27"))
        self.assertEqual(len(almacen.history("raton_pos10_guia")), 2)

    def test_la_ficha_enseña_la_ultima(self):
        almacen = SeedStore()
        almacen.add(_corrida(run_id="s1", date="2026-08-26"))
        almacen.add(_corrida(run_id="s2", date="2026-08-27"))
        self.assertEqual(almacen.latest("raton_pos10_guia").run_id, "s2")

    def test_repetir_un_run_id_ABORTA(self):
        almacen = SeedStore()
        almacen.add(_corrida(run_id="s1"))
        with self.assertRaises(ShmirDesignError):
            almacen.add(_corrida(run_id="s1"))


if __name__ == "__main__":
    unittest.main()
