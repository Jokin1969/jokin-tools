"""El modal de colision de seed: la logica fuera de la pagina, y la ficha por hebra.

Regla 5: escritos antes. Regla 6: la pagina no decide nada.
"""

import unittest
from pathlib import Path

from shmir_design import presentation, seed_scan
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

MATURE = Path(__file__).resolve().parent.parent / "data" / "reference" / "mature.fa"
RATON = REFERENCES["NM_011170.3"]
HAY = MATURE.is_file() and fixture_available(RATON)


def _piezas():
    from shmir_design.mirna import load_mature_fa
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    maduros = load_mature_fa(MATURE, version="23")
    informe = tile_utr(load_3utr(RATON), mature=maduros)
    return maduros, informe, select_from_report(
        informe, SelectionConfig(n_candidates=10)
    )


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestLaTablaPrevia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.maduros, cls.tiling, cls.seleccion = _piezas()
        cls.filas = presentation.seed_preview_rows(
            cls.seleccion, species="raton", params=seed_scan.DEFAULTS
        )

    def test_trae_las_cuatro_columnas_que_se_piden(self):
        fila = self.filas[0]
        for clave in ("candidato", "hebra", "secuencia", "heptamero"):
            self.assertIn(clave, fila)

    def test_el_candidato_va_ETIQUETADO(self):
        self.assertTrue(self.filas[0]["candidato"].startswith("3utr:"))

    def test_marca_el_heptamero_COMPARTIDO_antes_de_correr(self):
        for fila in self.filas:
            self.assertIn("comparte", fila)

    def test_y_dice_CON_QUIEN(self):
        compartidas = [f for f in self.filas if f["comparte"]]
        for fila in compartidas:
            self.assertIn("3utr:", fila["comparte"])

    def test_las_dos_hebras_arrancan_marcadas(self):
        self.assertTrue(all(f["marcada"] for f in self.filas))


class TestLosAjustesDelModal(unittest.TestCase):

    def test_estan_TODOS_no_solo_los_cambiados(self):
        filas = presentation.seed_setting_rows(seed_scan.DEFAULTS)
        nombres = {f["ajuste"] for f in filas}
        for esperado in ("window", "species_prefix", "level", "normalize_u_t"):
            self.assertIn(esperado, nombres)

    def test_por_defecto_ninguno_va_marcado(self):
        self.assertTrue(
            all(not f["modificado"] for f in presentation.seed_setting_rows(seed_scan.DEFAULTS))
        )

    def test_cambiar_la_ventana_marca_SOLO_esa(self):
        filas = presentation.seed_setting_rows(
            seed_scan.DEFAULTS.with_changes(window="2-7")
        )
        self.assertEqual([f["ajuste"] for f in filas if f["modificado"]], ["window"])

    def test_la_normalizacion_sale_como_FIJA(self):
        fila = next(
            f for f in presentation.seed_setting_rows(seed_scan.DEFAULTS)
            if f["ajuste"] == "normalize_u_t"
        )
        self.assertTrue(fila["fijo"])

    def test_las_alternativas_de_ventana_se_ofrecen(self):
        fila = next(
            f for f in presentation.seed_setting_rows(seed_scan.DEFAULTS)
            if f["ajuste"] == "window"
        )
        self.assertEqual(sorted(fila["opciones"]), ["2-7", "2-8"])


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestLaFuenteSaleALaVISTA(unittest.TestCase):

    def test_release_y_md5_no_van_escondidos(self):
        maduros, _, _ = _piezas()
        texto = presentation.seed_source_text(maduros)
        self.assertIn("23", texto)
        self.assertIn("320a5a53", texto)

    def test_sin_maduros_lo_dice_y_no_deja_correr(self):
        texto = presentation.seed_source_text(None)
        self.assertIn("NOT_RUN", texto)


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestLoQueSeDESTACA(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        maduros, _, seleccion = _piezas()
        cls.scan = seed_scan.run_scan(
            seleccion, mature=maduros, params=seed_scan.DEFAULTS, species="raton",
            starts=tuple(c.start for c in seleccion.selection.chosen),
            guides=True, passengers=True,
        )
        cls.destacados = presentation.seed_highlights(cls.scan)

    def test_son_TRES_bloques(self):
        self.assertEqual(
            sorted(self.destacados), ["mir30", "pasajeras", "tasa_base"]
        )

    def test_la_tasa_base_esta_SIEMPRE(self):
        self.assertTrue(self.destacados["tasa_base"]["texto"])

    def test_las_pasajeras_van_SEPARADAS_de_las_guias(self):
        self.assertIn("pasajera", self.destacados["pasajeras"]["texto"].lower())
        self.assertIn("nunca", self.destacados["pasajeras"]["texto"].lower())

    def test_el_bloque_de_miR30_trae_su_razon(self):
        self.assertIn("miR-E", self.destacados["mir30"]["texto"])

    def test_cada_bloque_dice_si_hay_algo_que_enseñar(self):
        for bloque in self.destacados.values():
            self.assertIn("activo", bloque)


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestElHuecoDeLaCARGA(unittest.TestCase):
    """Lo que este modal NO cierra, preparado en la misma interfaz y en NOT_RUN."""

    def test_hay_un_bloque_para_el_otro_frente(self):
        hueco = presentation.seed_load_placeholder(None)
        self.assertIs(hueco["state"], FilterState.NOT_RUN)

    def test_nombra_el_fichero_que_falta(self):
        self.assertIn("transcriptoma_3utr.fa", presentation.seed_load_placeholder(None)["texto"])

    def test_dice_que_es_OTRA_pregunta(self):
        texto = presentation.seed_load_placeholder(None)["texto"].lower()
        self.assertIn("cuántos mensajeros", texto)

    def test_con_el_fichero_dejaria_de_ser_un_hueco(self):
        class _Falso:
            provenance = "transcriptoma_3utr.fa, versión x"

        hueco = presentation.seed_load_placeholder(_Falso())
        self.assertIsNot(hueco["state"], FilterState.NOT_RUN)


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestLaFichaSeparaLasDosHEBRAS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.apa import resolve_measured
        from shmir_design.dossier import build_dossier
        from shmir_design.mirna import load_mature_fa
        from shmir_design.seed_store import SeedRun, SeedStore
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        utr3 = load_3utr(RATON)
        maduros = load_mature_fa(MATURE, version="23")
        tiling = tile_utr(
            utr3, mature=maduros
        )
        seleccion = select_from_report(
            tiling, SelectionConfig(n_candidates=10, apa_immune_quota=4)
        )
        inicio = seleccion.selection.chosen[0].start
        scan = seed_scan.run_scan(
            seleccion, mature=maduros, params=seed_scan.DEFAULTS, species="raton",
            starts=(inicio,), guides=True, passengers=True,
        )
        cls.inicio = inicio
        cls.almacen = SeedStore()
        cls.almacen.add(
            SeedRun.create(
                run_id="s1", date="2026-08-26", ran_by="responsable", scan=scan
            )
        )
        cls.ficha = build_dossier(
            species="raton", tiling=tiling, selection=seleccion, start=inicio,
            seed_store=cls.almacen,
        )

    def test_hay_DOS_filas_de_seed_no_una(self):
        nombres = [f.name for f in self.ficha.fronts]
        self.assertIn("seed_colision:guia", nombres)
        self.assertIn("seed_colision:pasajera", nombres)

    def test_y_NO_queda_una_fila_fundida(self):
        self.assertNotIn("seed_colision", [f.name for f in self.ficha.fronts])

    def test_cada_una_trae_su_fecha_y_su_corrida(self):
        for nombre in ("seed_colision:guia", "seed_colision:pasajera"):
            frente = next(f for f in self.ficha.fronts if f.name == nombre)
            self.assertEqual(frente.date, "2026-08-26")
            self.assertIn("s1", frente.source)

    def test_sin_almacen_las_dos_siguen_en_NOT_RUN(self):
        from shmir_design.dossier import build_dossier

        ficha = build_dossier(
            species="raton", tiling=self.ficha_tiling(), selection=self.ficha_sel(),
            start=self.inicio,
        )
        for nombre in ("seed_colision:guia", "seed_colision:pasajera"):
            frente = next(f for f in ficha.fronts if f.name == nombre)
            self.assertIs(frente.state, FilterState.NOT_RUN)

    @classmethod
    def ficha_tiling(cls):
        from shmir_design.apa import resolve_measured
        from shmir_design.mirna import load_mature_fa
        from shmir_design.tiling import tile_utr

        utr3 = load_3utr(RATON)
        return tile_utr(
            utr3, mature=load_mature_fa(MATURE, version="23"),
        )

    @classmethod
    def ficha_sel(cls):
        from shmir_design.selection import SelectionConfig, select_from_report

        return select_from_report(
            cls.ficha_tiling(),
            SelectionConfig(n_candidates=10, apa_immune_quota=4),
        )


if __name__ == "__main__":
    unittest.main()
