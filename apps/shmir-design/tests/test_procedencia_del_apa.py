"""`APA_POSIBLE (medido)` y `APA_POSIBLE (canónico, asumido)` son dos cosas.

Regla 5: escrito antes.

Hoy se llaman igual, y no lo son:

  · el `AATATA` de `3utr:236` del ratón lo es por **uso medido** (PolyA_DB v4.1, PSE
    21,1 %) y no por canonicidad;
  · las dos `ATTAAA` del 3'UTR **humano** —`3utr:955` y `3utr:1167`— lo son por
    canonicidad y **sin un solo dato de uso**: la tabla medida es de Prnp murino y no
    habla de esa secuencia. Son un SUPUESTO, y el informe ya usa esa palabra.

Con el ratón las dos señales `APA_POSIBLE` están medidas —el `AATAAA` de `3utr:288` es
uno de los tres sitios anclados—, así que el caso «canónico, asumido» hay que buscarlo
en el humano. Ésa es la razón de que este test use los dos fixtures y no uno.

El campo `evidence` ya distinguía las dos vías. Lo que faltaba es que la distinción
VIAJE PEGADA a la clasificación, que es lo que alguien copia a un correo. Es la misma
regla que la del md5 junto a la longitud: separadas en dos campos, la de al lado no se
lee.
"""

import unittest

from shmir_design.polya import SignalClass
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]
HAY = fixture_available(RATON)
HAY_HUMANO = fixture_available(HUMANO)


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del ratón")
class TestLaEtiquetaLLEVALaVia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raton = {s.position: s for s in tile_utr(load_3utr(RATON)).signals}
        cls.humano = (
            {s.position: s for s in tile_utr(load_3utr(HUMANO)).signals}
            if HAY_HUMANO else {}
        )

    def test_la_medida_dice_MEDIDO_y_NOMBRA_la_fuente(self):
        etiqueta = self.raton[236].classification_label
        self.assertIn("APA_POSIBLE", etiqueta)
        self.assertIn("medido", etiqueta)
        self.assertIn("PolyA_DB", etiqueta)

    def test_con_el_raton_las_DOS_estan_medidas(self):
        # No es un detalle del test: el `AATAAA` de 288 tambien es uno de los tres
        # sitios anclados, asi que en esta especie no hay ninguna «canonica asumida».
        for posicion in (236, 288):
            with self.subTest(posicion):
                self.assertEqual(self.raton[posicion].evidence, "medida")

    def test_la_canonica_sin_dato_dice_ASUMIDO_y_esa_es_HUMANA(self):
        if not HAY_HUMANO:
            self.skipTest("NOT_RUN: falta el fixture humano")
        etiqueta = self.humano[955].classification_label
        self.assertIn("APA_POSIBLE", etiqueta)
        self.assertIn("canónico", etiqueta)
        self.assertIn("asumido", etiqueta)

    def test_y_las_dos_etiquetas_NO_son_la_misma(self):
        if not HAY_HUMANO:
            self.skipTest("NOT_RUN: falta el fixture humano")
        self.assertNotEqual(
            self.raton[236].classification_label,
            self.humano[955].classification_label,
        )

    def test_las_dos_son_la_MISMA_clase(self):
        # Que es justo el problema: la clase no distingue, así que la etiqueta tiene que.
        if not HAY_HUMANO:
            self.skipTest("NOT_RUN: falta el fixture humano")
        self.assertIs(self.raton[236].classification, SignalClass.APA_POSSIBLE)
        self.assertIs(self.humano[955].classification, SignalClass.APA_POSSIBLE)


class TestLaEtiquetaSinNadaEspecial(unittest.TestCase):
    def _señal(self, motivo, medida=""):
        from shmir_design.polya import PolyASignal

        return PolyASignal(
            motif=motivo, position=100, utr_length=1242, distance_to_3p=500,
            classification=SignalClass.APA_POSSIBLE, measured_use=medida,
        )

    def test_una_clase_que_no_es_APA_POSIBLE_no_lleva_coletilla(self):
        from shmir_design.polya import PolyASignal

        señal = PolyASignal(
            motif="AATAAA", position=100, utr_length=1242, distance_to_3p=20,
            classification=SignalClass.TERMINAL_PROBABLE,
        )
        self.assertEqual(
            señal.classification_label, SignalClass.TERMINAL_PROBABLE.value
        )

    def test_una_variante_rara_sin_medida_tampoco_es_APA_POSIBLE(self):
        # No se puede fabricar el caso «rara y APA_POSIBLE sin medida»: la cascada no
        # deja llegar ahi a una variante rara. Se comprueba que la etiqueta lo dice.
        self.assertIn("asumido", self._señal("AATAAA").classification_label)

    def test_y_con_medida_lo_dice_aunque_el_hexamero_sea_canonico(self):
        etiqueta = self._señal("AATAAA", medida="PolyA_DB v4.1: uso medido").classification_label
        self.assertIn("medido", etiqueta)
        self.assertNotIn("asumido", etiqueta)


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del ratón")
class TestLLEGAALaSALIDA(unittest.TestCase):
    """Una distinción que se calcula y no se imprime es media distinción. Errata nº 17."""

    def _tabla(self, referencia):
        from shmir_design.selection import apa_ceiling_table

        return "\n".join(
            f.describe() for f in apa_ceiling_table(tile_utr(load_3utr(referencia)))
        )

    def test_el_bloque_de_TECHOS_del_raton_dice_MEDIDO(self):
        texto = self._tabla(RATON)
        self.assertIn("APA_POSIBLE (medido, PolyA_DB v4.1)", texto)

    def test_y_el_del_humano_dice_ASUMIDO(self):
        if not HAY_HUMANO:
            self.skipTest("NOT_RUN: falta el fixture humano")
        texto = self._tabla(HUMANO)
        self.assertIn("APA_POSIBLE (canónico, asumido)", texto)
        self.assertNotIn("medido", texto)


if __name__ == "__main__":
    unittest.main()
