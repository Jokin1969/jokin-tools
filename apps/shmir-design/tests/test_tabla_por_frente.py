"""La tabla de sitios con UNA COLUMNA POR FRENTE, y el `.gb` contra el NO_FIABLE.

Regla 5: escritos antes.

Es la vista que impide que vuelva a pasar lo de `offtarget_seed`: un frente sin columna
no se ve, y lo que no se ve no existe. Por eso las columnas se DERIVAN de los frentes que
el informe conoce — un frente nuevo aparece solo — en vez de listarse a mano.

Y la frontera del 3'UTR: con `.gb` la declara una ANOTACION; con el CDS tecleado, una
persona. No es lo mismo y la salida no puede tratarlo igual, porque un off-by-one ahi
corre el 3'UTR entero y con el todos los tercios sin dar ningun error.
"""

import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _piezas(anatomy=None):
    from shmir_design.apa import resolve_measured
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(RATON)
    informe = tile_utr(
        utr3, anatomy=anatomy
    )
    seleccion = select_from_report(
        informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
    )
    return informe, seleccion


class TestLaFiabilidadDeLaFrontera(unittest.TestCase):

    def _anatomia(self, source):
        return Anatomy.from_cds(cds=(1, 3), length=1242, source=source)

    def test_con_GENBANK_es_fiable(self):
        info = presentation.anatomy_reliability(
            self._anatomia(RegionSource.ANOTACION_GENBANK)
        )
        self.assertTrue(info["fiable"])
        self.assertIs(info["estado"], FilterState.PASS)

    def test_con_un_fixture_verificado_tambien(self):
        self.assertTrue(
            presentation.anatomy_reliability(
                self._anatomia(RegionSource.FIXTURE_VERIFICADO)
            )["fiable"]
        )

    def test_con_el_CDS_TECLEADO_NO_es_fiable(self):
        info = presentation.anatomy_reliability(
            self._anatomia(RegionSource.CDS_DECLARADA)
        )
        self.assertFalse(info["fiable"])
        self.assertIs(info["estado"], FilterState.NOT_RUN)
        self.assertIn("NO_FIABLE", info["texto"])

    def test_ni_marcando_que_lo_subido_YA_es_el_3utr(self):
        self.assertFalse(
            presentation.anatomy_reliability(
                self._anatomia(RegionSource.TODO_3UTR_DECLARADO)
            )["fiable"]
        )

    def test_sin_anatomia_tampoco(self):
        info = presentation.anatomy_reliability(None)
        self.assertFalse(info["fiable"])
        self.assertIn("SIN ANATOMÍA", info["texto"])

    def test_lo_que_deja_de_valer_va_NOMBRADO_uno_a_uno(self):
        """«Algunas cosas» no sirve: hay que poder saber que columna no mirar."""
        info = presentation.anatomy_reliability(
            self._anatomia(RegionSource.CDS_DECLARADA)
        )
        self.assertEqual(len(info["afectados"]), 5)
        texto = " ".join(info["afectados"])
        for cosa in ("tercios", "región", "polyA", "TERMINALES"):
            self.assertIn(cosa, texto)

    def test_y_el_motivo_dice_QUE_pasa_con_un_off_by_one(self):
        info = presentation.anatomy_reliability(
            self._anatomia(RegionSource.CDS_DECLARADA)
        )
        self.assertIn("off-by-one", info["texto"])
        self.assertIn("ningún error", info["texto"])

    def test_se_ACEPTA_igual_no_se_bloquea(self):
        """Hay que poder trabajar. Lo que no se puede es no decirlo."""
        info = presentation.anatomy_reliability(
            self._anatomia(RegionSource.CDS_DECLARADA)
        )
        self.assertIn("Se acepta", info["texto"])


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaTablaDeSitios(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.informe, cls.seleccion = _piezas()

    def test_las_columnas_de_frente_se_DERIVAN_no_se_listan(self):
        from shmir_design.selection import blocking_fronts

        esperadas = sorted({f.name for f in blocking_fronts(self.informe, self.seleccion)})
        self.assertEqual(
            presentation.front_columns(self.informe, self.seleccion), esperadas
        )

    def test_hay_columna_para_offtarget_seed_que_es_el_que_estuvo_invisible(self):
        self.assertIn(
            "offtarget_seed",
            presentation.front_columns(self.informe, self.seleccion),
        )

    def test_salen_TODOS_los_elegibles_no_solo_los_elegidos(self):
        filas = presentation.site_table_rows(self.informe, self.seleccion)
        self.assertGreater(len(filas), 10)
        self.assertEqual(sum(1 for f in filas if f["elegido"]), 10)

    def test_cada_fila_trae_UNA_COLUMNA_POR_FRENTE(self):
        filas = presentation.site_table_rows(self.informe, self.seleccion)
        for columna in presentation.front_columns(self.informe, self.seleccion):
            self.assertIn(columna, filas[0], columna)

    def test_y_un_frente_sin_correr_sale_NOT_RUN_no_vacio(self):
        filas = presentation.site_table_rows(self.informe, self.seleccion)
        self.assertEqual(filas[0]["especificidad"], "NOT_RUN")

    def test_la_seleccion_a_mano_cambia_QUIEN_esta_marcado(self):
        filas = presentation.site_table_rows(
            self.informe, self.seleccion, selected=(10, 60)
        )
        marcados = {f["inicio"] for f in filas if f["elegido"]}
        self.assertEqual(marcados, {10, 60})

    def test_sin_frontera_fiable_el_TERCIO_sale_NO_FIABLE(self):
        filas = presentation.site_table_rows(self.informe, self.seleccion)
        self.assertEqual(filas[0]["tercio"], "NO_FIABLE")

    def test_con_GENBANK_el_tercio_sale_con_su_valor(self):
        informe, seleccion = _piezas(
            Anatomy.from_cds(
                cds=(1, 3), length=1242, source=RegionSource.ANOTACION_GENBANK
            )
        )
        filas = presentation.site_table_rows(informe, seleccion)
        self.assertNotEqual(filas[0]["tercio"], "NO_FIABLE")


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLosAvisosDeLaSeleccion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.informe, cls.seleccion = _piezas()

    def test_dos_marcados_a_menos_del_espaciado_dan_aviso_ROJO(self):
        avisos = presentation.selection_warnings(
            self.informe, self.seleccion, selected=(100, 120), min_spacing=50
        )
        self.assertTrue(avisos)
        self.assertTrue(avisos[0]["rojo"])
        self.assertIn("20 nt", avisos[0]["texto"])

    def test_y_el_motivo_dice_que_las_causas_son_REGIONALES(self):
        avisos = presentation.selection_warnings(
            self.informe, self.seleccion, selected=(100, 120), min_spacing=50
        )
        self.assertIn("REGIONALES", avisos[0]["texto"])

    def test_dos_lejos_NO_dan_aviso_de_espaciado(self):
        avisos = presentation.selection_warnings(
            self.informe, self.seleccion, selected=(10, 600), min_spacing=50
        )
        self.assertEqual(
            [a for a in avisos if "espaciado" in a["texto"]], []
        )

    def test_el_NUCLEO_compartido_da_su_PROPIO_aviso_rojo(self):
        """El espaciado no lo ve: mide nucleotidos, no parecido de seed."""
        avisos = presentation.selection_warnings(
            self.informe, self.seleccion, selected=(449, 1018), min_spacing=50
        )
        self.assertTrue(any("núcleo" in a["texto"] for a in avisos))
        self.assertTrue(all(a["rojo"] for a in avisos))

    def test_449_y_1018_estan_LEJOS_y_aun_asi_avisan(self):
        avisos = presentation.selection_warnings(
            self.informe, self.seleccion, selected=(449, 1018), min_spacing=50
        )
        self.assertFalse(any("espaciado mínimo" in a["texto"] for a in avisos))
        self.assertTrue(avisos)


class TestLaPaginaLaENSEÑA(unittest.TestCase):

    def test_la_tabla_y_los_avisos_estan_en_la_pagina(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("site_table_rows", fuente)
        self.assertIn("selection_warnings", fuente)
        self.assertIn("anatomy_reliability", fuente)


if __name__ == "__main__":
    unittest.main()
