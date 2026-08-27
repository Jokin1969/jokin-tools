"""El TERCER modal: carga de off-targets por seed. Lo que la pagina NO decide.

Regla 5: escritos antes. Regla 6: la pagina pinta, `presentation.py` decide.

Este modal tiene una pieza que los otros dos no tienen: el fichero **no lo tenemos**, asi
que hay que poder subirlo desde la interfaz — y con el, su procedencia. Un fichero sin
ensamblaje y sin fecha de la tabla no es reproducible, asi que la subida los EXIGE.
"""

import unittest
from pathlib import Path

from shmir_design import offtarget, presentation
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"
MATURE = DATOS / "mature.fa"
RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]
HAY = MATURE.is_file() and fixture_available(RATON) and fixture_available(HUMANO)

FORMULARIO = {
    "source": "UCSC Table Browser",
    "assembly": "mm39",
    "table": "NCBI RefSeq / RefSeq All",
    "table_date": "2026-08-26",
    "representative": "el transcrito más largo por gen",
    "version": "2026-08-26",
}


class TestElHuecoMientrasFaltaElFichero(unittest.TestCase):

    def test_sin_catalogo_el_frente_sale_NOT_RUN_VISIBLE(self):
        hueco = presentation.offtarget_placeholder(None)
        self.assertIs(hueco["state"], FilterState.NOT_RUN)
        self.assertIn(offtarget.MISSING_FILE, hueco["texto"])

    def test_y_dice_que_NOT_RUN_no_es_cero(self):
        texto = presentation.offtarget_placeholder(None)["texto"].lower()
        self.assertIn("no es cero", texto)

    def test_la_ruta_de_descarga_esta_EN_LA_INTERFAZ(self):
        texto = presentation.offtarget_route_text()
        self.assertIn("Table Browser", texto)
        self.assertIn("mm39", texto)
        self.assertIn("3' UTR Exons", texto)
        self.assertIn("git", texto)


class TestLaSubidaDelFichero(unittest.TestCase):

    def test_la_procedencia_se_construye_FUERA_de_la_pagina(self):
        procedencia = presentation.offtarget_provenance_from_form(
            dict(FORMULARIO), md5="0" * 32
        )
        self.assertEqual(procedencia.assembly, "mm39")
        self.assertEqual(procedencia.table_date, "2026-08-26")

    def test_un_campo_de_procedencia_vacio_ABORTA_al_construirla(self):
        with self.assertRaises(ValueError):
            presentation.offtarget_provenance_from_form(
                dict(FORMULARIO, assembly=""), md5="0" * 32
            )

    def test_la_validacion_devuelve_filas_para_pintar_sin_decidir_nada(self):
        filas = presentation.offtarget_upload_rows(">a\nACGTACGTAC\n>b\nGGGGTTTTAA\n")
        campos = {f["campo"]: f["valor"] for f in filas}
        self.assertEqual(campos["secuencias"], "2")
        self.assertEqual(campos["longitud total"], "20 nt")
        self.assertIn("md5", campos)

    def test_las_filas_marcan_lo_que_NO_cuadra(self):
        filas = presentation.offtarget_upload_rows(
            ">NM_1\nACGTACGTAC\n>NM_1\nGGGGTTTTAA\n"
        )
        avisos = [f for f in filas if f["avisa"]]
        self.assertTrue(avisos)

    def test_un_fichero_que_no_es_FASTA_se_RECHAZA_al_subirlo(self):
        with self.assertRaises(ShmirDesignError):
            presentation.offtarget_upload_rows("no soy un fasta\n")

    def test_el_catalogo_se_construye_con_la_procedencia_del_formulario(self):
        catalogo = presentation.offtarget_catalog_from_upload(
            ">a\nACGTACGTACGTACGTACGT\n>b\nGGGGTTTTAAGGGGTTTTAA\n",
            form=dict(FORMULARIO),
        )
        self.assertEqual(catalogo.provenance.assembly, "mm39")
        self.assertEqual(len(catalogo.records), 2)
        # El md5 sale del fichero, no del formulario.
        self.assertNotEqual(catalogo.provenance.md5, "")


class TestLosAjustes(unittest.TestCase):

    def test_se_pintan_todos_con_su_valor_por_defecto(self):
        filas = presentation.offtarget_setting_rows(offtarget.DEFAULTS)
        campos = {f["ajuste"] for f in filas}
        self.assertEqual(
            campos, {"null_draws", "null_seed", "species_prefix", "normalize_u_t"}
        )
        self.assertFalse(any(f["modificado"] for f in filas))

    def test_la_normalizacion_es_FIJA_y_se_enseña_no_se_ofrece(self):
        filas = {f["ajuste"]: f for f in presentation.offtarget_setting_rows(
            offtarget.DEFAULTS
        )}
        self.assertTrue(filas["normalize_u_t"]["fijo"])

    def test_uno_cambiado_se_marca_y_solo_ese(self):
        params = offtarget.DEFAULTS.with_changes(null_seed=99)
        marcados = [
            f["ajuste"] for f in presentation.offtarget_setting_rows(params)
            if f["modificado"]
        ]
        self.assertEqual(marcados, ["null_seed"])

    def test_la_conversion_a_entero_la_hace_presentation_no_la_pagina(self):
        params = presentation.offtarget_params_from_form(
            {"null_draws": "20000", "null_seed": "3", "species_prefix": "mmu-"}
        )
        self.assertEqual(params.null_draws, 20_000)
        self.assertEqual(params.null_seed, 3)

    def test_y_el_minimo_lo_sigue_haciendo_cumplir_el_dataclass(self):
        with self.assertRaises(ValueError):
            presentation.offtarget_params_from_form(
                {"null_draws": "10", "null_seed": "0", "species_prefix": "mmu-"}
            )


class TestLasLimitacionesEnLaInterfaz(unittest.TestCase):

    def test_salen_las_TRES_con_su_direccion(self):
        filas = presentation.offtarget_limitation_rows()
        self.assertEqual(len(filas), 3)
        for fila in filas:
            self.assertEqual(fila["direccion"], "sobrestima")
            self.assertTrue(fila["texto"].strip())

    def test_y_la_conclusion_de_LIMITE_SUPERIOR_va_aparte_y_activa(self):
        bloque = presentation.offtarget_upper_bound()
        self.assertTrue(bloque["activo"])
        self.assertIn("límite superior", bloque["texto"].lower())


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o alguno de los dos fixtures")
class TestElResultado(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.mirna import load_mature_fa
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        cls.utr3 = load_3utr(RATON)
        cls.seleccion = select_from_report(
            tile_utr(cls.utr3), SelectionConfig(n_candidates=10)
        )
        cls.catalogo = offtarget.build_catalog(
            [("uno", cls.utr3), ("dos", load_3utr(HUMANO))],
            provenance=presentation.offtarget_provenance_from_form(
                dict(FORMULARIO, source="fixtures del proyecto (NO es el transcriptoma)"),
                md5="0" * 32,
            ),
        )
        cls.scan = presentation.offtarget_run(
            cls.seleccion,
            catalog=cls.catalogo,
            mature=load_mature_fa(MATURE, version="23"),
            params=offtarget.DEFAULTS,
            species="raton",
            starts=(cls.seleccion.selection.chosen[0].start,),
            guides=True,
            passengers=True,
            target=cls.utr3,
            target_label="3'UTR de Prnp (raton)",
        )

    def test_una_columna_POR_CLASE_y_ningun_total(self):
        filas = presentation.offtarget_result_rows(self.scan)
        for clase in offtarget.SITE_CLASSES:
            self.assertIn(clase, filas[0])
            self.assertIn(f"{clase} percentil", filas[0])
        self.assertNotIn("total", filas[0])

    def test_la_hebra_va_en_su_columna_y_no_se_funde(self):
        filas = presentation.offtarget_result_rows(self.scan)
        self.assertEqual({f["hebra"] for f in filas}, {"guia", "pasajera"})

    def test_los_controles_salen_en_su_tabla(self):
        filas = presentation.offtarget_control_rows(self.scan)
        self.assertEqual(len(filas), 3)
        for fila in filas:
            self.assertIn("mmu-", fila["control"])

    def test_el_autoconteo_marca_lo_ANOMALO(self):
        filas = presentation.offtarget_self_count_rows(self.scan)
        self.assertTrue(all("anomalo" in f for f in filas))

    def test_los_destacados_traen_la_nula_el_limite_y_el_uso(self):
        destacados = presentation.offtarget_highlights(self.scan)
        for clave in ("limite_superior", "uso", "nula", "isoformas", "autoconteo"):
            self.assertIn(clave, destacados)
            self.assertIn("texto", destacados[clave])

    def test_el_bloque_de_isoformas_esta_ACTIVO_si_no_se_pudo_comprobar(self):
        destacados = presentation.offtarget_highlights(self.scan)
        self.assertTrue(destacados["isoformas"]["activo"])


class TestLaPaginaSigueSinLOGICA(unittest.TestCase):

    def test_el_modal_no_convierte_ni_ordena_datos(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        inicio = fuente.index("def _modal_offtarget(")
        modal = fuente[inicio:]
        for prohibido in ("int(", "float(", ".upper()", ".lower()", "sorted("):
            self.assertNotIn(prohibido, modal, prohibido)

    def test_el_modal_existe_y_se_llama_desde_la_pagina(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _modal_offtarget(", fuente)
        self.assertIn("_modal_offtarget(", fuente.split("def _modal_offtarget(")[0])


if __name__ == "__main__":
    unittest.main()
