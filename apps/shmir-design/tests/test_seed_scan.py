"""El modal de colision de seed: este SI ejecuta.

Regla 5: escritos antes.

A diferencia del de BLAST, aqui no hay red ni orden que copiar: el calculo es busqueda de
SUBCADENA contra `mature.fa`, que ya esta cargado y verificado. Boton → resultado.

Lo que se comprueba aqui es que el resultado no se pueda leer mal:

  - una corrida con ventana 2-7 NO puede presentarse como 2-8;
  - guia y pasajera NUNCA se funden en un veredicto;
  - la TASA BASE va siempre junto a los avisos, porque sin ella un AVISO parece mas
    grave de lo que es;
  - la normalizacion U↔T va DECLARADA: un desajuste de alfabeto daria cero colisiones y
    parece una buena noticia.
"""

import unittest
from pathlib import Path

from shmir_design import seed_scan

#: Los parametros del raton. `seed_scan.DEFAULTS` ya NO trae `mmu-`: el prefijo sale de
#: `species`, y sin declarar especie va `None` — que no es lo mismo que `""` (todas).
PARAMS_RATON = seed_scan.SeedParams.for_species("raton")
from shmir_design.errors import ShmirDesignError
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
    seleccion = select_from_report(informe, SelectionConfig(n_candidates=10))
    return maduros, informe, seleccion


class TestLosParametros(unittest.TestCase):

    def test_la_ventana_por_defecto_es_2_8(self):
        self.assertEqual(PARAMS_RATON.window, "2-8")

    def test_las_alternativas_son_2_7_y_2_8_y_nada_mas(self):
        self.assertEqual(sorted(seed_scan.SEED_WINDOWS), ["2-7", "2-8"])

    def test_una_ventana_desconocida_ABORTA(self):
        with self.assertRaises(ValueError):
            PARAMS_RATON.with_changes(window="2-9")

    def test_la_especie_NO_es_un_valor_por_defecto(self):
        """`mmu-` por defecto sobre una guia de conejo daba CERO colisiones."""
        self.assertIsNone(seed_scan.SeedParams().species_prefix)
        self.assertEqual(PARAMS_RATON.species_prefix, "mmu-")

    def test_sin_prefijo_declarado_la_corrida_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as caja:
            seed_scan.SeedParams().require_prefix()
        self.assertIn("species.mirbase_prefix", str(caja.exception))

    def test_y_VACIO_no_es_lo_mismo_que_SIN_DECLARAR(self):
        """`""` = todas las especies del fichero, elegido a proposito. Son dos valores."""
        self.assertEqual(seed_scan.SeedParams(species_prefix="").require_prefix(), "")

    def test_una_especie_sin_prefijo_declarado_ABORTA_al_pedirlo(self):
        with self.assertRaises(ShmirDesignError):
            seed_scan.SeedParams.for_species("Oryctolagus cuniculus")

    def test_el_nivel_por_defecto_son_LOS_DOS(self):
        self.assertEqual(PARAMS_RATON.level, "ambos")

    def test_un_nivel_desconocido_ABORTA(self):
        with self.assertRaises(ValueError):
            PARAMS_RATON.with_changes(level="solo_los_buenos")

    def test_cambiar_uno_lo_marca_y_solo_a_ese(self):
        self.assertEqual(
            PARAMS_RATON.with_changes(window="2-7").modified(), ("window",)
        )

    def test_la_normalizacion_U_T_es_SIEMPRE_y_va_declarada(self):
        self.assertTrue(PARAMS_RATON.normalize_u_t)
        texto = seed_scan.NORMALIZATION_NOTE
        self.assertIn("U", texto)
        self.assertIn("cero colisiones", texto.lower())

    def test_y_no_se_puede_apagar(self):
        with self.assertRaises(ValueError):
            PARAMS_RATON.with_changes(normalize_u_t=False)


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestLaTablaDeLoQueSeVaAComparar(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.maduros, cls.tiling, cls.seleccion = _piezas()
        cls.filas = seed_scan.preview_rows(
            cls.seleccion, species="raton", params=PARAMS_RATON
        )

    def test_hay_DOS_filas_por_candidato_guia_y_pasajera(self):
        self.assertEqual(len(self.filas), 2 * len(self.seleccion.selection.chosen))

    def test_cada_fila_trae_la_secuencia_COMPLETA_y_el_heptamero(self):
        fila = self.filas[0]
        self.assertEqual(len(fila.sequence), 22)
        self.assertEqual(len(fila.heptamer), 7)
        self.assertIn(fila.heptamer, fila.sequence)

    def test_el_heptamero_son_las_posiciones_2_8_de_la_hebra(self):
        fila = self.filas[0]
        self.assertEqual(fila.heptamer, fila.sequence[1:8])

    def test_las_dos_hebras_van_marcadas_por_defecto(self):
        self.assertTrue(all(f.checked for f in self.filas))

    def test_hay_filas_de_guia_y_de_pasajera(self):
        self.assertEqual({f.strand for f in self.filas}, {"guia", "pasajera"})

    def test_marca_las_filas_que_COMPARTEN_heptamero(self):
        # Dos candidatos con la misma seed no son dos apuestas independientes en este
        # eje, y eso se ve ANTES de correr nada.
        por_hepta = {}
        for fila in self.filas:
            por_hepta.setdefault(fila.heptamer, []).append(fila)
        for grupo in por_hepta.values():
            if len(grupo) > 1:
                for fila in grupo:
                    self.assertTrue(fila.shared_with)
            else:
                self.assertEqual(grupo[0].shared_with, ())

    def test_con_ventana_2_7_el_heptamero_mide_SEIS(self):
        filas = seed_scan.preview_rows(
            self.seleccion, species="raton",
            params=PARAMS_RATON.with_changes(window="2-7"),
        )
        self.assertEqual(len(filas[0].heptamer), 6)


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestLaTasaBaseSeDERIVA(unittest.TestCase):
    """No se teclea: sale del fichero cargado y del filtro de especie que se use."""

    def setUp(self):
        self.maduros, _, _ = _piezas()

    def test_con_mmu_solo_es_del_orden_del_10_por_ciento(self):
        tasa = seed_scan.base_rate(self.maduros, PARAMS_RATON)
        self.assertEqual(tasa.matures, 1988)
        self.assertEqual(tasa.distinct, 1593)
        self.assertAlmostEqual(tasa.fraction, 1593 / 16384, places=6)
        self.assertTrue(0.09 <= tasa.fraction <= 0.12)

    def test_el_espacio_es_4_elevado_a_7(self):
        self.assertEqual(seed_scan.base_rate(self.maduros, PARAMS_RATON).space, 16384)

    def test_con_2_7_la_tasa_SUBE_mucho_y_se_ve(self):
        tasa = seed_scan.base_rate(
            self.maduros, PARAMS_RATON.with_changes(window="2-7")
        )
        self.assertEqual(tasa.space, 4096)
        self.assertGreater(tasa.fraction, 0.25)

    def test_dejando_hsa_dentro_la_tasa_casi_se_DOBLA(self):
        # El filtro de especie no es cosmetico: cambia como se lee un AVISO.
        tasa = seed_scan.base_rate(
            self.maduros, PARAMS_RATON.with_changes(species_prefix="")
        )
        self.assertGreater(tasa.fraction, 0.18)

    def test_el_texto_dice_de_DONDE_sale(self):
        texto = seed_scan.base_rate(self.maduros, PARAMS_RATON).describe()
        self.assertIn("1988", texto)
        self.assertIn("16384", texto)
        self.assertIn("azar", texto.lower())


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestLaCorrida(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.maduros, cls.tiling, cls.seleccion = _piezas()
        cls.corrida = seed_scan.run_scan(
            cls.seleccion, mature=cls.maduros, params=PARAMS_RATON,
            species="raton",
            starts=tuple(c.start for c in cls.seleccion.selection.chosen),
            guides=True, passengers=True,
        )

    def test_hay_un_resultado_por_consulta(self):
        self.assertEqual(
            len(self.corrida.results), 2 * len(self.seleccion.selection.chosen)
        )

    def test_cada_resultado_clasifica_en_FAIL_AVISO_o_LIMPIO(self):
        for r in self.corrida.results:
            self.assertIn(r.level, ("FAIL", "AVISO", "LIMPIO"))

    def test_las_colisiones_traen_el_NOMBRE_COMPLETO_del_miARN(self):
        con = [r for r in self.corrida.results if r.collisions]
        for r in con:
            for c in r.collisions:
                self.assertTrue(c.name.startswith("mmu-"))

    def test_guia_y_pasajera_NO_se_funden(self):
        hebras = {r.strand for r in self.corrida.results}
        self.assertEqual(hebras, {"guia", "pasajera"})
        # y no hay ningun veredicto agregado por candidato
        self.assertFalse(hasattr(self.corrida, "verdict_per_candidate"))

    def test_la_familia_miR_30_se_marca_APARTE(self):
        for r in self.corrida.results:
            for c in r.collisions:
                if "miR-30" in c.name:
                    self.assertTrue(c.mir30)

    def test_y_con_su_razon_escrita(self):
        self.assertIn("miR-E", seed_scan.MIR30_NOTE)
        self.assertIn("peor", seed_scan.MIR30_NOTE.lower())

    def test_la_tasa_base_VIAJA_con_la_corrida(self):
        self.assertIsNotNone(self.corrida.base_rate)

    def test_los_parametros_efectivos_van_COMPLETOS(self):
        texto = "\n".join(self.corrida.params.describe())
        for trozo in ("window=", "especie=", "nivel=", "U↔T"):
            self.assertIn(trozo, texto)

    def test_la_procedencia_de_mature_fa_va_con_la_corrida(self):
        self.assertIn("mature.fa", self.corrida.source)
        self.assertIn("23", self.corrida.source)

    def test_sin_candidatos_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            seed_scan.run_scan(
                self.seleccion, mature=self.maduros, params=PARAMS_RATON,
                species="raton", starts=(), guides=True, passengers=True,
            )

    def test_sin_hebras_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            seed_scan.run_scan(
                self.seleccion, mature=self.maduros, params=PARAMS_RATON,
                species="raton", starts=(10,), guides=False, passengers=False,
            )


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestCriterio_2_7_NoEs_2_8(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.maduros, _, cls.seleccion = _piezas()

    def _corrida(self, ventana):
        return seed_scan.run_scan(
            cls_sel := self.seleccion, mature=self.maduros,
            params=PARAMS_RATON.with_changes(window=ventana),
            species="raton", starts=(10,), guides=True, passengers=False,
        )

    def test_la_ventana_VIAJA_en_cada_resultado(self):
        self.assertEqual(self._corrida("2-7").results[0].window, "2-7")

    def test_y_en_el_bloque_exportable(self):
        self.assertIn("2-7", self._corrida("2-7").export_block())

    def test_una_de_2_7_NO_es_estandar(self):
        self.assertFalse(self._corrida("2-7").params.is_standard)

    def test_y_el_bloque_lo_dice_con_esas_palabras(self):
        texto = self._corrida("2-7").export_block()
        self.assertIn("MODIFICADO", texto.upper())

    def test_los_heptameros_de_las_dos_ventanas_son_DISTINTOS(self):
        a = self._corrida("2-8").results[0].heptamer
        b = self._corrida("2-7").results[0].heptamer
        self.assertNotEqual(a, b)
        self.assertEqual(len(a), 7)
        self.assertEqual(len(b), 6)


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture del raton")
class TestElBloqueExportable(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.maduros, _, cls.seleccion = _piezas()
        cls.corrida = seed_scan.run_scan(
            cls.seleccion, mature=cls.maduros, params=PARAMS_RATON,
            species="raton", starts=(10, 60), guides=True, passengers=True,
        )

    def test_trae_la_PREGUNTA_que_contesta(self):
        self.assertIn("¿", self.corrida.export_block())

    def test_trae_fuente_y_version(self):
        texto = self.corrida.export_block()
        self.assertIn("mature.fa", texto)
        self.assertIn("23", texto)

    def test_trae_la_tasa_base(self):
        self.assertIn("azar", self.corrida.export_block().lower())

    def test_trae_una_linea_por_candidato_y_HEBRA(self):
        texto = self.corrida.export_block()
        self.assertIn("guia", texto)
        self.assertIn("pasajera", texto)

    def test_dice_lo_que_NO_contesta(self):
        texto = self.corrida.export_block()
        self.assertIn("transcriptoma_3utr.fa", texto)
        self.assertIn("cuantos mensajeros", texto.lower())

    def test_se_lee_sin_la_app_delante(self):
        # No hay referencias a widgets ni a «pincha aqui».
        self.assertNotIn("pincha", self.corrida.export_block().lower())


class TestLoQueEsteModalNoCierra(unittest.TestCase):

    def test_la_frase_esta_escrita_en_el_nucleo(self):
        texto = seed_scan.WHAT_THIS_DOES_NOT_ANSWER
        self.assertIn("mi seed es la de un miARN conocido", texto)
        self.assertIn("cuantos mensajeros", texto.lower())

    def test_nombra_el_fichero_que_falta(self):
        self.assertIn("transcriptoma_3utr.fa", seed_scan.WHAT_THIS_DOES_NOT_ANSWER)

    def test_y_dice_que_son_DOS_frentes(self):
        self.assertIn("dos frentes", seed_scan.WHAT_THIS_DOES_NOT_ANSWER.lower())


if __name__ == "__main__":
    unittest.main()
