"""«Inmune» a secas no es un veredicto: hay DOS ejes y sólo uno es geométrico.

Regla 5: escritos antes.

`3utr:200` conserva la cuarta plaza, pero por el eje de TRUNCAMIENTO, que es geometrico
y no depende de ninguna convencion: empieza en 200 y el corte mas temprano esta en 251.
En el eje ESTERICO queda MARCADO, y con una nota que no se puede omitir: el flanco de
±10 nt NO TIENE BASE MEDIDA, y la huella real de CPSF/CstF sobre el pre-mRNA es mayor,
asi que 15 nt aguas arriba del hexamero esta probablemente DENTRO de la zona de
competencia.

Y el principio detras: **el eje esterico es un GRADIENTE, no una frontera.** Cualquier
umbral en nucleotidos le atribuye una precision que la biologia no tiene, asi que la
sensibilidad al flanco se reporta SIEMPRE junto al veredicto.
"""

import unittest

from shmir_design.apa import POLYA_DB_PRNP, resolve_measured
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]


class TestElPrincipio(unittest.TestCase):

    def test_el_esterico_va_declarado_como_GRADIENTE(self):
        from shmir_design import polya

        texto = polya.STERIC_IS_A_GRADIENT
        self.assertIn("GRADIENTE", texto.upper())
        self.assertIn("no una frontera", texto.lower())

    def test_dice_que_el_flanco_de_10_NO_tiene_base_medida(self):
        from shmir_design import polya

        self.assertIn("no tiene base medida", polya.STERIC_IS_A_GRADIENT.lower())

    def test_y_que_la_huella_real_es_MAYOR(self):
        from shmir_design import polya

        texto = polya.STERIC_IS_A_GRADIENT
        self.assertIn("CPSF", texto)
        self.assertIn("mayor", texto.lower())

    def test_y_que_la_sensibilidad_va_SIEMPRE_al_lado(self):
        from shmir_design import polya

        self.assertIn("siempre", polya.STERIC_IS_A_GRADIENT.lower())


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLosDosEjesDe3utr200(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.selection import (
            SelectionConfig, promotion_clearance, select_from_report,
        )
        from shmir_design.tiling import tile_utr

        utr3 = load_3utr(RATON)
        cls.informe = tile_utr(utr3, measured_apa=resolve_measured(utr3, POLYA_DB_PRNP))
        cls.seleccion = select_from_report(
            cls.informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
        )
        cls.holguras = promotion_clearance(cls.informe, cls.seleccion)

    def _fila(self):
        return next(f for f in self.holguras.rows if f.start == 200)

    def test_el_eje_de_TRUNCAMIENTO_es_inmune(self):
        self.assertTrue(self._fila().immune_truncation)

    def test_y_es_GEOMETRICO_sin_convencion_de_por_medio(self):
        fila = self._fila()
        self.assertEqual(fila.start, 200)
        self.assertEqual(fila.earliest_cut, 251)
        self.assertLess(fila.start, fila.earliest_cut)

    def test_el_eje_ESTERICO_queda_PENALIZADO_no_inmune(self):
        self.assertEqual(self._fila().steric, "PENALIZADO")

    def test_NUNCA_sale_como_inmune_a_secas(self):
        texto = self._fila().describe()
        self.assertIn("inmune_truncamiento", texto)
        self.assertIn("esterico", texto)
        self.assertNotIn("PASA.", texto)

    def test_y_la_nota_del_flanco_va_PEGADA_al_veredicto(self):
        texto = self._fila().describe()
        self.assertIn("15", texto)
        self.assertIn("no tiene base medida", texto.lower())

    def test_la_tabla_entera_lo_repite_para_que_no_se_lea_suelto(self):
        texto = self.holguras.describe()
        self.assertIn("GRADIENTE", texto.upper())


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestLaListaDeInmunesNoDiceInmuneASecas(unittest.TestCase):
    """En el informe, `3utr:200` no puede aparecer en la misma lista que 10, 60 y 143."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        utr3 = load_3utr(RATON)
        informe = tile_utr(utr3, measured_apa=resolve_measured(utr3, POLYA_DB_PRNP))
        cls.texto = text_report(
            species="raton", tiling=informe,
            selection=select_from_report(
                informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
            ),
            scaffold=SGEP_SCAFFOLD,
        )

    def test_el_200_sale_MARCADO_en_la_lista(self):
        linea = next(
            l for l in self.texto.splitlines() if "INMUNES al TRUNCAMIENTO" in l
        )
        self.assertIn("3utr:200", linea)
        self.assertIn("esterico", linea.lower())

    def test_los_otros_tres_NO_llevan_marca(self):
        linea = next(
            l for l in self.texto.splitlines() if "INMUNES al TRUNCAMIENTO" in l
        )
        # La marca va SOLO donde hay algo que marcar; ponerla en todos la haria invisible.
        self.assertEqual(linea.count("esterico"), 1)

    def test_el_informe_trae_el_principio_del_gradiente(self):
        self.assertIn("GRADIENTE", self.texto.upper())


if __name__ == "__main__":
    unittest.main()
