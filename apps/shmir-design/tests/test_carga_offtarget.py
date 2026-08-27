"""Carga de off-targets mediada por seed: el TERCER modal.

Regla 5: escritos antes.

Es el frente `offtarget_seed`, el que estuvo invisible hasta que se contaron los frentes
uno a uno. Se cierra con `transcriptoma_3utr.fa`, que HOY NO ESTA: mientras falte, el
frente sale NOT_RUN con el nombre del fichero, nunca PASS y nunca cero.

Lo que se comprueba aqui es que el numero no se pueda leer mal:

  - son CUATRO clases y NO se suman: la represion esperada de un 8mer y la de un 6mer no
    se parecen, y un total las mezcla;
  - un conteo a secas no es interpretable, asi que va con PERCENTIL contra una nula de
    composicion equivalente, con CONTROLES biologicos y con AUTOCONTEO sobre la diana;
  - las tres limitaciones van EN EL RESULTADO, no al pie, porque las tres empujan en la
    misma direccion: el numero es un LIMITE SUPERIOR;
  - es DESEMPATE, nunca filtro: ningun camino puede devolver FAIL.
"""

import unittest
from pathlib import Path

from shmir_design import offtarget
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"
MATURE = DATOS / "mature.fa"
RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]
HAY_RATON = fixture_available(RATON)
HAY_DOS = HAY_RATON and fixture_available(HUMANO)
HAY_MATURE = MATURE.is_file()


def _procedencia_de_prueba() -> "offtarget.Provenance":
    """Procedencia del catalogo de PRUEBA, declarada como lo que es.

    NO es el transcriptoma: son los dos 3'UTR de referencia del proyecto, que si estan
    verificados por md5. Se declara asi para que ninguna salida de un test pueda
    confundirse con una corrida de verdad.
    """
    return offtarget.Provenance(
        source="fixtures del proyecto (NO es el transcriptoma)",
        assembly="n/a — dos 3'UTR de referencia, no un ensamblaje",
        table="data/reference/NM_011170.3.fa + NM_000311.5.fa",
        table_date="2026-08-26",
        representative="uno por gen porque solo hay dos genes",
        version="fixtures-2026-08-26",
        md5="0" * 32,
    )


def _catalogo_de_prueba() -> "offtarget.Catalog":
    registros = [("NM_011170.3_utr3", load_3utr(RATON))]
    if fixture_available(HUMANO):
        registros.append(("NM_000311.5_utr3", load_3utr(HUMANO)))
    return offtarget.build_catalog(registros, provenance=_procedencia_de_prueba())


def _piezas():
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(RATON)
    informe = tile_utr(utr3)
    seleccion = select_from_report(informe, SelectionConfig(n_candidates=10))
    return utr3, informe, seleccion


class TestLasCuatroClases(unittest.TestCase):

    def test_son_CUATRO_y_en_orden_de_especificidad(self):
        self.assertEqual(
            offtarget.SITE_CLASSES, ("8mer", "7mer-m8", "7mer-A1", "6mer")
        )

    def test_cada_una_lleva_su_geometria_escrita(self):
        for clase in offtarget.SITE_CLASSES:
            self.assertIn(clase, offtarget.CLASS_GEOMETRY)
            self.assertTrue(offtarget.CLASS_GEOMETRY[clase].strip())

    def test_la_geometria_dice_donde_va_la_A_y_donde_la_posicion_8(self):
        self.assertIn("A", offtarget.CLASS_GEOMETRY["8mer"])
        self.assertIn("2-8", offtarget.CLASS_GEOMETRY["7mer-m8"])
        self.assertIn("2-7", offtarget.CLASS_GEOMETRY["7mer-A1"])
        self.assertIn("2-7", offtarget.CLASS_GEOMETRY["6mer"])

    def test_NUNCA_se_suman_y_el_motivo_va_escrito(self):
        texto = offtarget.WHY_NOT_SUMMED.lower()
        self.assertIn("represion", texto)
        self.assertIn("no se suman", texto)

    def test_Counts_no_tiene_total_ni_suma(self):
        cuentas = offtarget.Counts(
            sites={c: 1 for c in offtarget.SITE_CLASSES},
            transcripts={c: 1 for c in offtarget.SITE_CLASSES},
        )
        for prohibido in ("total", "suma", "sum", "todos"):
            self.assertFalse(
                hasattr(cuentas, prohibido),
                f"`Counts.{prohibido}` NO puede existir: sumar las cuatro clases mezcla "
                f"señal con ruido, y si el atributo existe alguien lo imprimira.",
            )

    def test_una_clase_desconocida_ABORTA(self):
        with self.assertRaises(ValueError):
            offtarget.Counts(sites={"5mer": 3}, transcripts={"5mer": 1})


@unittest.skipUnless(HAY_RATON, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaGeometriaDeLosPatrones(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.informe, cls.seleccion = _piezas()
        cls.elegido = cls.seleccion.selection.chosen[0]
        cls.guia = cls.seleccion.window_of(cls.elegido).evaluation.guide

    def test_el_nucleo_de_6_nt_lo_comparten_las_cuatro(self):
        patrones = offtarget.site_patterns(self.guia)
        self.assertEqual(len(patrones.core), 6)
        self.assertEqual(patrones.sites["8mer"], patrones.m8_base + patrones.core + "A")
        self.assertEqual(patrones.sites["7mer-m8"], patrones.m8_base + patrones.core)
        self.assertEqual(patrones.sites["7mer-A1"], patrones.core + "A")
        self.assertEqual(patrones.sites["6mer"], patrones.core)

    def test_el_heptamero_son_las_posiciones_2_8_de_la_guia(self):
        patrones = offtarget.site_patterns(self.guia)
        self.assertEqual(patrones.heptamer, self.guia.replace("U", "T")[1:8])

    def test_una_hebra_mas_corta_que_la_seed_ABORTA(self):
        with self.assertRaises(ValueError):
            offtarget.site_patterns("ACGTA")

    def test_las_cuatro_clases_son_EXCLUYENTES(self):
        """Cada aparicion del nucleo cae en UNA clase y solo una."""
        patrones = offtarget.site_patterns(self.guia)
        cuentas = offtarget.count_in(self.utr3, patrones)
        apariciones = offtarget.core_occurrences(self.utr3, patrones)
        self.assertEqual(sum(cuentas.values()), apariciones)


@unittest.skipUnless(HAY_RATON, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElAutoconteoSobrePrnp(unittest.TestCase):
    """Cuantos sitios tiene la guia en su PROPIO 3'UTR diana. Deberia ser 1."""

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.informe, cls.seleccion = _piezas()

    def _autoconteos(self):
        return {
            elegido.start: offtarget.self_count(
                self.seleccion.window_of(elegido).evaluation.guide,
                target=self.utr3, target_label="3\'UTR de Prnp",
            )
            for elegido in self.seleccion.selection.chosen
        }

    def test_CUATRO_del_panel_del_raton_tienen_un_SEGUNDO_sitio(self):
        """HALLAZGO, no expectativa: el valor con su procedencia, no su forma.

        No es un fallo del panel ni de la cuenta: es informacion que hay que tener ANTES
        de leer una cinetica de knockdown, porque el efecto de esas cuatro guias sobre su
        propio mensajero no es el de un solo sitio.
        """
        raros = {
            inicio: propio.occurrences
            for inicio, propio in self._autoconteos().items()
            if propio.anomalous
        }
        self.assertEqual(raros, {449: 2, 553: 2, 819: 2, 1018: 2})

    def test_los_otros_seis_tienen_UNO_solo(self):
        limpios = {
            inicio for inicio, propio in self._autoconteos().items()
            if not propio.anomalous
        }
        self.assertEqual(limpios, {10, 60, 143, 359, 652, 735})

    def test_el_aviso_dice_que_son_MULTIPLES_DIANAS_en_el_mismo_mensajero(self):
        texto = self._autoconteos()[819].describe()
        self.assertIn("MULTIPLES DIANAS", texto)
        self.assertIn("cinetica", texto)

    def test_449_y_1018_comparten_el_NUCLEO_asi_que_no_son_independientes(self):
        """El segundo sitio de cada uno es la ventana del otro. Sale del mismo dato."""
        nucleos = {
            inicio: offtarget.site_patterns(
                self.seleccion.window_of(elegido).evaluation.guide
            ).core
            for inicio, elegido in (
                (c.start, c) for c in self.seleccion.selection.chosen
            )
        }
        self.assertEqual(nucleos[449], nucleos[1018])

    def test_el_valor_esperado_es_UNO_y_va_declarado(self):
        guia = self.seleccion.window_of(
            self.seleccion.selection.chosen[0]
        ).evaluation.guide
        propio = offtarget.self_count(guia, target=self.utr3, target_label="Prnp")
        self.assertEqual(propio.expected, 1)

    def test_cero_sitios_tambien_es_ANOMALO_y_lo_dice(self):
        """Cero significa que la guia NO sale de esa diana. Es otro fallo, no un exito."""
        otra = "T" + "ACGTACGTACGTACGTACGTA"[:21]
        propio = offtarget.self_count(otra, target="AAAA" * 20, target_label="x")
        if propio.occurrences == 0:
            self.assertTrue(propio.anomalous)
            self.assertIn("0", propio.describe())


@unittest.skipUnless(HAY_RATON, "NOT_RUN: falta el fixture del raton")
class TestLaDistribucionNula(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.informe, cls.seleccion = _piezas()
        cls.catalogo = _catalogo_de_prueba()
        cls.guia = cls.seleccion.window_of(
            cls.seleccion.selection.chosen[0]
        ).evaluation.guide
        cls.patrones = offtarget.site_patterns(cls.guia)

    def test_el_minimo_son_DIEZ_MIL_sorteos(self):
        self.assertGreaterEqual(offtarget.DEFAULTS.null_draws, 10_000)
        self.assertEqual(offtarget.MIN_NULL_DRAWS, 10_000)

    def test_pedir_menos_de_diez_mil_ABORTA(self):
        with self.assertRaises(ValueError):
            offtarget.OfftargetParams(null_draws=500)

    def test_el_criterio_de_la_nula_va_DECLARADO_no_citado(self):
        texto = offtarget.NULL_CRITERION.lower()
        self.assertIn("composición", texto)
        self.assertIn("permutaci", texto)

    def test_todos_los_sorteos_tienen_LA_MISMA_composicion(self):
        nula = offtarget.null_distribution(
            self.catalogo.index, self.patrones, draws=10_000, seed=0
        )
        esperada = sorted(self.patrones.heptamer)
        for hepta in nula.distinct_heptamers:
            self.assertEqual(sorted(hepta), esperada)

    def test_la_misma_semilla_da_LA_MISMA_nula(self):
        una = offtarget.null_distribution(
            self.catalogo.index, self.patrones, draws=10_000, seed=7
        )
        otra = offtarget.null_distribution(
            self.catalogo.index, self.patrones, draws=10_000, seed=7
        )
        self.assertEqual(una.by_class, otra.by_class)

    def test_la_semilla_VIAJA_con_el_resultado(self):
        nula = offtarget.null_distribution(
            self.catalogo.index, self.patrones, draws=10_000, seed=7
        )
        self.assertEqual(nula.seed, 7)
        self.assertEqual(nula.draws, 10_000)
        self.assertIn("7", " ".join(nula.describe()))

    def test_el_percentil_es_el_numero_ACCIONABLE_y_esta_entre_0_y_100(self):
        nula = offtarget.null_distribution(
            self.catalogo.index, self.patrones, draws=10_000, seed=0
        )
        for clase in offtarget.SITE_CLASSES:
            p = nula.percentile(clase, 0)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 100.0)

    def test_un_conteo_por_debajo_de_toda_la_nula_da_percentil_bajo(self):
        nula = offtarget.null_distribution(
            self.catalogo.index, self.patrones, draws=10_000, seed=0
        )
        self.assertLess(nula.percentile("6mer", -1), 1.0)

    def test_la_regla_del_percentil_va_escrita(self):
        self.assertIn("empate", offtarget.PERCENTILE_RULE.lower())

    def test_una_clase_que_no_existe_ABORTA(self):
        nula = offtarget.null_distribution(
            self.catalogo.index, self.patrones, draws=10_000, seed=0
        )
        with self.assertRaises(ValueError):
            nula.percentile("5mer", 3)


@unittest.skipUnless(HAY_MATURE and HAY_RATON, "NOT_RUN: falta mature.fa")
class TestLosControlesBiologicos(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.mirna import load_mature_fa

        cls.maduros = load_mature_fa(MATURE, version="23")
        cls.catalogo = _catalogo_de_prueba()

    def test_son_los_TRES_acordados(self):
        self.assertEqual(
            offtarget.CONTROL_NAMES, ("miR-124-3p", "miR-9-5p", "let-7a-5p")
        )

    def test_sus_seeds_SALEN_DEL_FICHERO_no_del_codigo(self):
        fuente = Path(offtarget.__file__).read_text(encoding="utf-8")
        import re

        sospechosas = [
            m for m in re.findall(r"\"[ACGT]{6,}\"", fuente)
        ]
        self.assertEqual(
            sospechosas, [],
            f"Hay secuencias literales en offtarget.py: {sospechosas}. Las seeds de los "
            f"controles salen de mature.fa, nunca escritas (regla 1).",
        )

    def test_se_resuelven_contra_mature_fa_con_el_prefijo_de_especie(self):
        controles = offtarget.controls_from_mature(
            self.maduros, self.catalogo.index, prefix="mmu-"
        )
        self.assertEqual(len(controles), 3)
        for control in controles:
            self.assertTrue(control.name.startswith("mmu-"))
            self.assertEqual(len(control.heptamer), 7)

    def test_un_control_que_no_esta_en_el_fichero_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            offtarget.controls_from_mature(
                self.maduros, self.catalogo.index, prefix="xxx-"
            )

    def test_su_conteo_es_la_REFERENCIA_de_que_significa_muchos_sitios(self):
        texto = offtarget.CONTROLS_NOTE.lower()
        self.assertIn("referencia", texto)
        self.assertIn("biolog", texto)


class TestLasTresLimitaciones(unittest.TestCase):

    def test_son_TRES(self):
        self.assertEqual(len(offtarget.LIMITATIONS), 3)

    def test_las_tres_empujan_en_la_MISMA_direccion(self):
        for limitacion in offtarget.LIMITATIONS:
            self.assertEqual(limitacion.direction, "sobrestima")

    def test_conservacion_nombra_a_TargetScan_y_dice_que_no_lo_tenemos(self):
        texto = offtarget.limitation("conservacion").text
        self.assertIn("TargetScan", texto)
        self.assertIn("multiespecie", texto)

    def test_APA_lo_sabemos_por_Prnp_y_aplica_a_los_demas_igual(self):
        texto = offtarget.limitation("apa").text
        self.assertIn("Prnp", texto)
        self.assertIn("distal", texto.lower())

    def test_expresion_nombra_el_fichero_que_lo_refinaria(self):
        texto = offtarget.limitation("expresion").text
        self.assertIn("expresion_cerebro.tsv", texto)

    def test_la_conclusion_es_LIMITE_SUPERIOR(self):
        self.assertIn("límite superior", offtarget.UPPER_BOUND_NOTE.lower())

    def test_una_limitacion_que_no_existe_ABORTA(self):
        with self.assertRaises(KeyError):
            offtarget.limitation("conservacion_de_verdad")


class TestElUso(unittest.TestCase):

    def test_es_DESEMPATE_y_NUNCA_filtro(self):
        texto = offtarget.USE_NOTE.lower()
        self.assertIn("desempate", texto)
        self.assertIn("nunca", texto)
        self.assertIn("filtro", texto)

    def test_dice_que_la_potencia_sobre_la_diana_sigue_mandando(self):
        self.assertIn("potencia", offtarget.USE_NOTE.lower())


class TestLaProcedenciaDelFichero(unittest.TestCase):

    def test_necesita_ensamblaje_y_fecha_de_la_tabla(self):
        for campo in ("assembly", "table_date", "representative", "md5", "version"):
            with self.assertRaises(ValueError, msg=f"{campo} vacío tenia que abortar"):
                offtarget.Provenance(
                    **{
                        **{
                            "source": "UCSC Table Browser",
                            "assembly": "mm39",
                            "table": "NCBI RefSeq / RefSeq All",
                            "table_date": "2026-08-26",
                            "representative": "el más largo por gen",
                            "version": "v1",
                            "md5": "0" * 32,
                        },
                        campo: "",
                    }
                )

    def test_la_ruta_de_descarga_va_escrita_en_la_interfaz(self):
        texto = offtarget.UCSC_ROUTE
        self.assertIn("Table Browser", texto)
        self.assertIn("mm39", texto)
        self.assertIn("3' UTR Exons", texto)

    def test_el_fichero_que_falta_se_nombra(self):
        self.assertEqual(offtarget.MISSING_FILE, "transcriptoma_3utr.fa")


class TestLaValidacionAlSubir(unittest.TestCase):

    def test_lo_que_no_es_FASTA_se_RECHAZA(self):
        with self.assertRaises(ShmirDesignError) as caja:
            offtarget.validate_upload("esto no es un fasta\nni lo pretende\n")
        self.assertIn("FASTA", str(caja.exception))

    def test_un_fichero_vacio_se_RECHAZA(self):
        with self.assertRaises(ShmirDesignError):
            offtarget.validate_upload("")

    def test_un_alfabeto_que_no_es_de_ADN_se_RECHAZA(self):
        with self.assertRaises(ShmirDesignError) as caja:
            offtarget.validate_upload(">uno\nMKVLLAWFVGCLLS\n")
        self.assertIn("A/C/G/T", str(caja.exception))

    def test_el_md5_declarado_que_no_cuadra_se_RECHAZA(self):
        with self.assertRaises(ShmirDesignError) as caja:
            offtarget.validate_upload(">uno\nACGTACGTACGT\n", declared_md5="f" * 32)
        self.assertIn("md5", str(caja.exception))

    def test_devuelve_numero_de_secuencias_longitud_total_y_md5(self):
        informe = offtarget.validate_upload(">a\nACGTACGTAC\n>b\nGGGGTTTTAA\n")
        self.assertEqual(informe.records, 2)
        self.assertEqual(informe.total_nt, 20)
        self.assertEqual(len(informe.md5), 32)

    def test_detecta_identificadores_REPETIDOS(self):
        informe = offtarget.validate_upload(
            ">NM_1\nACGTACGTAC\n>NM_1\nGGGGTTTTAA\n>NM_2\nTTTTTTTTTT\n"
        )
        self.assertTrue(informe.audit.inflated)
        self.assertEqual(informe.audit.repeated_ids, (("NM_1", 2),))
        self.assertIn("inflado", informe.audit.warning().lower())

    def test_detecta_secuencias_DUPLICADAS_que_es_el_caso_de_dos_isoformas(self):
        informe = offtarget.validate_upload(
            ">NM_1\nACGTACGTAC\n>NM_2\nACGTACGTAC\n>NM_3\nTTTTTTTTTT\n"
        )
        self.assertEqual(informe.audit.duplicate_sequence_groups, 1)
        self.assertEqual(informe.audit.records_in_duplicates, 2)
        self.assertTrue(informe.audit.inflated)

    def test_SIN_mapa_de_genes_no_se_puede_descartar_y_lo_DICE(self):
        informe = offtarget.validate_upload(">NM_1\nACGTACGTAC\n>NM_2\nTTTTTTTTTT\n")
        self.assertFalse(informe.audit.checked_by_gene)
        self.assertIsNone(informe.audit.genes)
        texto = informe.audit.warning().lower()
        self.assertIn("no se ha podido comprobar", texto)

    def test_CON_mapa_de_genes_se_agrupa_y_se_dice_cuanto_infla(self):
        informe = offtarget.validate_upload(
            ">NM_1\nACGTACGTAC\n>NM_2\nTTTTTTTTTT\n>NM_3\nGGGGGGGGGG\n",
            gene_map={"NM_1": "Prnp", "NM_2": "Prnp", "NM_3": "Sprn"},
        )
        self.assertTrue(informe.audit.checked_by_gene)
        self.assertEqual(informe.audit.genes, 2)
        self.assertEqual(informe.audit.multi_isoform_genes, (("Prnp", 2),))
        self.assertTrue(informe.audit.inflated)

    def test_un_transcrito_que_no_esta_en_el_mapa_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            offtarget.validate_upload(
                ">NM_1\nACGTACGTAC\n>NM_2\nTTTTTTTTTT\n",
                gene_map={"NM_1": "Prnp"},
            )

    def test_un_catalogo_limpio_no_avisa_de_inflado(self):
        informe = offtarget.validate_upload(
            ">NM_1\nACGTACGTAC\n>NM_2\nTTTTTTTTTT\n",
            gene_map={"NM_1": "Prnp", "NM_2": "Sprn"},
        )
        self.assertFalse(informe.audit.inflated)


@unittest.skipUnless(HAY_DOS, "NOT_RUN: faltan los dos fixtures de referencia")
class TestElIndiceYElConteo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.informe, cls.seleccion = _piezas()
        cls.catalogo = _catalogo_de_prueba()
        cls.guia = cls.seleccion.window_of(
            cls.seleccion.selection.chosen[0]
        ).evaluation.guide
        cls.patrones = offtarget.site_patterns(cls.guia)

    def test_el_indice_y_el_barrido_directo_dan_LO_MISMO(self):
        """El indice es un atajo para la nula; si no coincide, la nula no vale."""
        por_indice = self.catalogo.index.class_counts(self.patrones)
        directo = offtarget.count_over(self.catalogo.records, self.patrones)
        self.assertEqual(por_indice, directo.sites)

    def test_el_conteo_trae_ademas_cuantos_TRANSCRITOS_toca(self):
        cuentas = offtarget.count_over(self.catalogo.records, self.patrones)
        for clase in offtarget.SITE_CLASSES:
            self.assertLessEqual(
                cuentas.transcripts[clase], len(self.catalogo.records)
            )

    def test_un_sitio_al_principio_de_un_3utr_no_se_pierde(self):
        """El relleno de los bordes es lo que evita perder sitios entre registros."""
        patrones = offtarget.site_patterns("TACGTACGTACGTACGTACGTA")
        catalogo = offtarget.build_catalog(
            [("uno", patrones.core + "GGGGG"), ("dos", "GGGGG" + patrones.core)],
            provenance=_procedencia_de_prueba(),
        )
        self.assertEqual(catalogo.index.class_counts(patrones)["6mer"], 2)


@unittest.skipUnless(HAY_MATURE and HAY_DOS, "NOT_RUN: falta mature.fa o un fixture")
class TestLaCorridaEntera(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.mirna import load_mature_fa

        cls.utr3, cls.informe, cls.seleccion = _piezas()
        cls.maduros = load_mature_fa(MATURE, version="23")
        cls.catalogo = _catalogo_de_prueba()
        cls.corrida = offtarget.run_scan(
            cls.seleccion,
            catalog=cls.catalogo,
            mature=cls.maduros,
            species="raton",
            starts=tuple(c.start for c in cls.seleccion.selection.chosen[:3]),
            guides=True,
            passengers=True,
            target=cls.utr3,
            target_label="3'UTR de Prnp (raton)",
        )

    def test_guia_y_pasajera_van_SEPARADAS(self):
        hebras = {r.strand for r in self.corrida.results}
        self.assertEqual(hebras, {"guia", "pasajera"})
        self.assertEqual(len(self.corrida.results), 6)

    def test_cada_resultado_trae_LAS_CUATRO_clases_por_separado(self):
        for resultado in self.corrida.results:
            self.assertEqual(
                sorted(resultado.counts.sites), sorted(offtarget.SITE_CLASSES)
            )
            self.assertEqual(
                sorted(resultado.percentiles), sorted(offtarget.SITE_CLASSES)
            )

    def test_la_nula_los_controles_y_el_autoconteo_van_EN_LA_MISMA_corrida(self):
        self.assertTrue(self.corrida.nulls)
        self.assertEqual(len(self.corrida.controls), 3)
        self.assertEqual(len(self.corrida.self_counts), 6)

    def test_sin_catalogo_ABORTA_en_vez_de_devolver_ceros(self):
        with self.assertRaises(ShmirDesignError) as caja:
            offtarget.run_scan(
                self.seleccion, catalog=None, mature=self.maduros, species="raton",
                starts=(self.seleccion.selection.chosen[0].start,),
                guides=True, passengers=False,
                target=self.utr3, target_label="x",
            )
        self.assertIn(offtarget.MISSING_FILE, str(caja.exception))

    def test_el_bloque_exportable_se_lee_SIN_la_app_delante(self):
        texto = self.corrida.export_block()
        for clase in offtarget.SITE_CLASSES:
            self.assertIn(clase, texto)
        self.assertIn("percentil", texto.lower())
        self.assertIn("TargetScan", texto)
        self.assertIn("expresion_cerebro.tsv", texto)
        self.assertIn("desempate", texto.lower())
        self.assertIn(self.catalogo.provenance.assembly, texto)

    def test_el_bloque_NO_imprime_ningun_total_de_las_cuatro_clases(self):
        texto = self.corrida.export_block().lower()
        self.assertNotIn("total de sitios", texto)

    def test_las_limitaciones_salen_EN_el_resultado_no_al_pie(self):
        lineas = self.corrida.export_block().splitlines()
        primera_limitacion = next(
            i for i, l in enumerate(lineas) if "TargetScan" in l
        )
        ultima_fila = max(
            i for i, l in enumerate(lineas) if "3utr:" in l
        )
        self.assertLess(
            primera_limitacion, ultima_fila + 12,
            "Las limitaciones tienen que ir pegadas al resultado, no en un pie que "
            "nadie lee.",
        )


@unittest.skipUnless(HAY_RATON, "NOT_RUN: falta el fixture del raton")
class TestLaFichaDelCandidato(unittest.TestCase):
    """El frente tiene que VERSE en la ficha, que es el punto de todo esto."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.dossier import build_dossier

        cls.utr3, cls.informe, cls.seleccion = _piezas()
        cls.ficha = build_dossier(
            species="raton", tiling=cls.informe, selection=cls.seleccion,
            start=cls.seleccion.selection.chosen[0].start,
        )

    def test_sale_PARTIDO_en_guia_y_pasajera_como_la_colision(self):
        nombres = {f.name for f in self.ficha.fronts}
        self.assertIn("offtarget_seed:guia", nombres)
        self.assertIn("offtarget_seed:pasajera", nombres)

    def test_y_NO_sale_como_un_frente_unico_por_candidato(self):
        nombres = {f.name for f in self.ficha.fronts}
        self.assertNotIn("offtarget_seed", nombres)

    def test_sin_corrida_los_dos_estan_en_NOT_RUN_VISIBLE(self):
        from shmir_design.filters import FilterState

        for frente in self.ficha.fronts:
            if frente.name.startswith("offtarget_seed"):
                self.assertIs(frente.state, FilterState.NOT_RUN)
                self.assertIn(offtarget.MISSING_FILE, frente.reason)


@unittest.skipUnless(HAY_DOS, "NOT_RUN: faltan los dos fixtures de referencia")
class TestNoHayDosContadoresQueDISCREPEN(unittest.TestCase):
    """`seed_load` cuenta lo mismo con TRES clases: los dos numeros tienen que atarse.

    `seed_load.seed_load` es el numero comparativo de la TABLA (sin 6mer, sin percentil)
    y este modulo es el FRENTE. Que convivan es util —la tabla no quiere cuatro columnas
    mas— pero dos contadores del mismo suceso que discrepen serian un fallo silencioso:
    la ficha diria una cosa y la tabla otra, las dos con pinta de medida.
    """

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.informe, cls.seleccion = _piezas()
        cls.registros = _catalogo_de_prueba().records

    def test_las_TRES_clases_compartidas_dan_LO_MISMO_en_los_diez_del_panel(self):
        from shmir_design import seed_load as viejo

        for elegido in self.seleccion.selection.chosen:
            guia = self.seleccion.window_of(elegido).evaluation.guide
            nuevo = offtarget.count_over(
                self.registros, offtarget.site_patterns(guia)
            ).sites
            patrones = viejo.site_patterns(guia)
            anterior = {t: 0 for t in viejo.SITE_TYPES}
            for _, secuencia in self.registros:
                for tipo, n in viejo._count_in(secuencia, patrones).items():
                    anterior[tipo] += n
            self.assertEqual(
                {t: nuevo[t] for t in viejo.SITE_TYPES}, anterior,
                f"3utr:{elegido.start}: el contador de la tabla y el del frente "
                f"discrepan. Uno de los dos está mal y no se elige por nuestra cuenta.",
            )

    def test_y_el_6mer_es_lo_que_el_contador_viejo_NO_veia(self):
        from shmir_design import seed_load as viejo

        self.assertNotIn("6mer", viejo.SITE_TYPES)
        self.assertIn("6mer", offtarget.SITE_CLASSES)


if __name__ == "__main__":
    unittest.main()
