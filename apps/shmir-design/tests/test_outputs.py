"""Tests de las salidas del diseño (TSV, FASTA, oligos e informe).

Regla 5: escritos antes que `shmir_design/outputs.py`.
"""

import unittest

from shmir_design.outputs import (
    fasta_guides,
    text_report,
    tsv_all_windows,
    tsv_oligos,
    tsv_selected,
)
from shmir_design.reference import REFERENCES
from shmir_design.scaffold import UNVERIFIED_TAG, ScaffoldSpec
from shmir_design.selection import SelectionConfig, select_from_report
from shmir_design.tiling import tile_utr

SONDA = "GCGTCAGTACGATCGAATTACT" * 30
ANDAMIO_SIN_VERIFICAR = ScaffoldSpec(
    name="andamio de prueba",
    flank5="TGCTGTTGACAGTGAGCG",
    loop="TAGTGAAGCCACAGATGTA",
    flank3="TGCCTACTGCCTCGGA",
)


def piezas():
    report = tile_utr(SONDA)
    return report, select_from_report(report, SelectionConfig(n_candidates=3))


class TestTsvCompleto(unittest.TestCase):

    def test_una_fila_por_ventana_y_una_columna_por_filtro(self):
        report, _ = piezas()
        lineas = tsv_all_windows(report).splitlines()
        self.assertEqual(len(lineas), len(report.windows) + 1)
        cabecera = lineas[0].split("\t")
        for filtro in ("GC", "homopolimero", "asimetria", "G4_diana", "G4_guia",
                       "zona_prohibida_polyA", "repeticiones", "seed"):
            with self.subTest(filtro):
                self.assertIn(filtro, cabecera)

    def test_los_estados_van_por_separado_no_agregados(self):
        report, _ = piezas()
        cuerpo = tsv_all_windows(report)
        self.assertIn("NOT_RUN", cuerpo)
        self.assertIn("PASS", cuerpo)


class TestTsvSeleccionados(unittest.TestCase):

    def test_una_fila_por_candidato(self):
        _, seleccion = piezas()
        lineas = tsv_selected(seleccion, species="sonda").splitlines()
        self.assertEqual(len(lineas), len(seleccion.selection.chosen) + 1)

    def test_lleva_una_columna_por_filtro(self):
        """Quien abra este TSV tiene que ver QUE filtro falta, no solo INCOMPLETE."""
        _, seleccion = piezas()
        cabecera = tsv_selected(seleccion, species="sonda").splitlines()[0].split("\t")
        for filtro in ("GC", "homopolimero", "asimetria", "G4_diana", "G4_guia",
                       "zona_prohibida_polyA", "repeticiones", "seed"):
            with self.subTest(filtro):
                self.assertIn(filtro, cabecera)

    def test_lleva_rango_tercio_asimetria_y_veredicto(self):
        _, seleccion = piezas()
        lineas = tsv_selected(seleccion, species="sonda").splitlines()
        fila = dict(zip(lineas[0].split("\t"), lineas[1].split("\t")))
        self.assertEqual(fila["especie"], "sonda")
        self.assertIn(fila["tercio"], ("proximal", "medio", "distal"))
        self.assertEqual(fila["veredicto"], "INCOMPLETE")
        self.assertTrue(fila["rango_asimetria"])
        self.assertTrue(fila["filtros_sin_correr"])


class TestFastaDeGuias(unittest.TestCase):

    def test_una_cabecera_y_una_secuencia_por_candidato(self):
        _, seleccion = piezas()
        lineas = fasta_guides(seleccion, species="sonda").splitlines()
        cabeceras = [l for l in lineas if l.startswith(">")]
        self.assertEqual(len(cabeceras), len(seleccion.selection.chosen))

    def test_la_guia_va_en_ADN_para_BLAST(self):
        _, seleccion = piezas()
        secuencias = [
            l for l in fasta_guides(seleccion, species="sonda").splitlines()
            if not l.startswith(">")
        ]
        self.assertTrue(secuencias)
        for secuencia in secuencias:
            with self.subTest(secuencia):
                self.assertNotIn("U", secuencia)

    def test_la_cabecera_identifica_especie_y_posicion(self):
        _, seleccion = piezas()
        primera = fasta_guides(seleccion, species="sonda").splitlines()[0]
        self.assertIn("sonda", primera)
        self.assertIn(str(seleccion.selection.chosen[0].start), primera)


class TestTsvDeOligos(unittest.TestCase):

    def test_una_fila_por_candidato_con_el_97_mero(self):
        _, seleccion = piezas()
        lineas = tsv_oligos(seleccion, ANDAMIO_SIN_VERIFICAR, species="sonda").splitlines()
        self.assertEqual(len(lineas), len(seleccion.selection.chosen) + 1)
        fila = dict(zip(lineas[0].split("\t"), lineas[1].split("\t")))
        self.assertEqual(len(fila["oligo"]), 97)

    def test_cada_fila_lleva_el_aviso_del_andamio_sin_verificar(self):
        _, seleccion = piezas()
        lineas = tsv_oligos(seleccion, ANDAMIO_SIN_VERIFICAR, species="sonda").splitlines()
        for linea in lineas[1:]:
            with self.subTest(linea[:30]):
                self.assertIn(UNVERIFIED_TAG, linea)

    def test_con_el_andamio_verificado_no_hay_avisos_de_regla(self):
        """La regla de la pasajera esta resuelta: ya no se avisa de ella."""
        from shmir_design.scaffold import SGEP_SCAFFOLD

        _, seleccion = piezas()
        texto = tsv_oligos(seleccion, SGEP_SCAFFOLD, species="sonda")
        self.assertNotIn("REGLA_NO_CONFIRMADA", texto)


class TestColumnasNuevas(unittest.TestCase):

    def test_los_seleccionados_traen_region_y_doble_coordenada(self):
        from shmir_design.anatomy import Anatomy

        anatomia = Anatomy.from_cds(cds=(1, 240), length=len(SONDA))
        report = tile_utr(SONDA, anatomy=anatomia)
        seleccion = select_from_report(report, SelectionConfig(n_candidates=2))
        lineas = tsv_selected(seleccion, species="sonda").splitlines()
        cabecera = lineas[0].split("\t")
        for columna in ("region", "inicio_3utr", "fin_3utr", "bandera_polyA_debil"):
            with self.subTest(columna):
                self.assertIn(columna, cabecera)
        fila = dict(zip(cabecera, lineas[1].split("\t")))
        self.assertEqual(fila["region"], "3'UTR")
        self.assertEqual(int(fila["inicio_3utr"]), int(fila["inicio"]) - 240)

    def test_los_oligos_traen_el_modulo_de_149(self):
        _, seleccion = piezas()
        lineas = tsv_oligos(seleccion, ANDAMIO_SIN_VERIFICAR, species="sonda").splitlines()
        cabecera = lineas[0].split("\t")
        self.assertIn("gblock_149", cabecera)
        fila = dict(zip(cabecera, lineas[1].split("\t")))
        self.assertEqual(len(fila["gblock_149"]), 149)
        self.assertIn(fila["gblock_veredicto"], ("PASS", "FAIL", "INCOMPLETE"))


class TestInformeDeTexto(unittest.TestCase):

    def informe(self):
        report, seleccion = piezas()
        return text_report(
            species="raton",
            tiling=report,
            selection=seleccion,
            scaffold=ANDAMIO_SIN_VERIFICAR,
            transcript=REFERENCES["NM_011170.3"],
        )

    def test_lleva_la_anatomia_del_transcrito(self):
        texto = self.informe()
        self.assertIn("NM_011170.3", texto)
        self.assertIn("950-2191", texto)
        self.assertIn("184", texto)

    def test_lleva_las_señales_de_poliadenilacion(self):
        self.assertIn("poliadenilacion", self.informe().lower())

    def test_dice_que_filtros_no_se_ejecutaron(self):
        texto = self.informe()
        self.assertIn("NO SE EJECUTARON", texto.upper())
        self.assertIn("seed", texto)
        self.assertIn("repeticiones", texto)

    def test_enseña_las_dos_cifras_de_elegibles(self):
        texto = self.informe()
        self.assertIn("escalonado", texto.lower())
        self.assertIn("estricto", texto.lower())

    def test_saca_la_sensibilidad_de_la_penalizacion(self):
        texto = self.informe()
        self.assertIn("sensibilidad", texto.lower())
        self.assertIn("penalizacion", texto.lower())

    def test_avisa_de_que_la_seleccion_es_provisional(self):
        self.assertIn("provisional", self.informe().lower())

    def test_lleva_el_aviso_del_andamio_sin_verificar(self):
        self.assertIn(UNVERIFIED_TAG, self.informe())

    def test_sin_bloques_conservados_lo_dice(self):
        self.assertIn("bloques conservados", self.informe().lower())


if __name__ == "__main__":
    unittest.main()
