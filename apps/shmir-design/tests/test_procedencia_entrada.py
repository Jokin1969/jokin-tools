"""Lo que se analizo queda registrado: longitud y md5 de la secuencia de entrada.

Regla 5: escritos antes.

Sin esto no hay forma de saber QUE se analizo. La errata del 3'UTR fabricado se detecto
por longitud contra las coordenadas declaradas; si el informe no dice la longitud ni el
md5 de lo que se le paso, esa comprobacion no se puede hacer a posteriori.

Y las dos posiciones de CONVENIO —la 1 de la guia y la 1 de la pasajera— salen marcadas
como tales: ninguna de las dos viene de la diana, y compararlas como si fueran dato es
lo que dejaba dos ventanas iguales sin cruzar.
"""

import unittest

from shmir_design.comparative import CONVENTION_NOTE
from shmir_design.outputs import text_report
from shmir_design.reference import sequence_md5
from shmir_design.scaffold import SGEP_SCAFFOLD
from shmir_design.selection import SelectionConfig, select_from_report
from shmir_design.tiling import tile_utr

SONDA = "GCGTCAGTACGATCGAATTACT" * 30


def piezas():
    report = tile_utr(SONDA)
    return report, select_from_report(report, SelectionConfig(n_candidates=3))


class TestProcedenciaDeLaEntrada(unittest.TestCase):

    def test_el_informe_lleva_la_longitud_de_lo_analizado(self):
        report, seleccion = piezas()
        texto = text_report(
            species="sonda", tiling=report, selection=seleccion, scaffold=SGEP_SCAFFOLD
        )
        self.assertIn(f"{len(SONDA)} nt", texto)

    def test_el_informe_lleva_el_md5_de_lo_analizado(self):
        report, seleccion = piezas()
        texto = text_report(
            species="sonda", tiling=report, selection=seleccion, scaffold=SGEP_SCAFFOLD
        )
        self.assertIn(sequence_md5(SONDA), texto)

    def test_el_md5_es_el_de_la_secuencia_canonica(self):
        report, _ = piezas()
        self.assertEqual(report.sequence_md5, sequence_md5(SONDA))

    def test_y_la_longitud_tambien(self):
        report, _ = piezas()
        self.assertEqual(report.sequence_length, len(SONDA))


class TestPosicionesDeConvenio(unittest.TestCase):

    def test_la_nota_nombra_las_dos(self):
        self.assertIn("guía", CONVENTION_NOTE.lower())
        self.assertIn("pasajera", CONVENTION_NOTE.lower())

    def test_dice_que_no_vienen_de_la_diana(self):
        self.assertIn("no viene", CONVENTION_NOTE.lower())

    def test_viaja_en_el_informe(self):
        report, seleccion = piezas()
        texto = text_report(
            species="sonda", tiling=report, selection=seleccion, scaffold=SGEP_SCAFFOLD
        )
        self.assertIn(CONVENTION_NOTE.splitlines()[0], texto)


if __name__ == "__main__":
    unittest.main()
