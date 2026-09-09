"""`APA_POSIBLE (medido)` y `APA_POSIBLE (canónico, asumido)` son dos cosas.

Regla 5: escrito antes.

Hoy se llaman igual, y no lo son:

  · el `AATATA` de `3utr:236` del ratón lo es por **uso medido** (PolyA_DB v4.1, PSE
    21,1 %) y no por canonicidad;
  · las dos `ATTAAA` del 3'UTR **humano** —`3utr:955` y `3utr:1167`— lo eran por
    canonicidad y **sin un solo dato de uso**, porque la tabla medida era de Prnp murino
    y no hablaba de esa secuencia.

**ESO CAMBIO EL 2026-09-09**, y el test se mueve con la decisión en vez de bloquearla
(principio nº 56): con `polya_db_human.tsv` en el depósito, las dos `ATTAAA` humanas
están **CONFIRMADAS por medida** y el `AGTAAA` de `3utr:233` entra **promovido** por
uso. O sea que **el caso «canónico, asumido» ya no existe en ninguna especie con
fixture**: sobre los dos transcritos del repositorio, las cinco señales `APA_POSIBLE`
salen medidas.

Que no exista ningún caso vivo NO es que la distinción sobre. Es lo contrario: la
etiqueta sigue teniendo que saber decirlo, y quien lo comprueba son los tests de unidad
de abajo, que construyen la señal a mano. Un caso que sólo existe ahí es un caso que hay
que fijar ahí — si no, el día que entre una especie sin tabla nadie sabría qué se emite.

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

    def test_la_HUMANA_ya_NO_dice_asumido_porque_hay_medida(self):
        if not HAY_HUMANO:
            self.skipTest("NOT_RUN: falta el fixture humano")
        etiqueta = self.humano[955].classification_label
        self.assertIn("APA_POSIBLE", etiqueta)
        self.assertIn("medido", etiqueta)
        self.assertNotIn("asumido", etiqueta)

    def test_NINGUNA_señal_con_fixture_queda_ya_en_ASUMIDO(self):
        # Es el hecho que hace caducar la premisa de este fichero, y se fija para que
        # se vea: si mañana alguien retira una tabla, este test lo dice.
        if not HAY_HUMANO:
            self.skipTest("NOT_RUN: falta el fixture humano")
        for nombre, señales in (("raton", self.raton), ("humano", self.humano)):
            for pos, s in señales.items():
                if s.classification is SignalClass.APA_POSSIBLE:
                    with self.subTest(especie=nombre, pos=pos):
                        self.assertEqual(s.evidence, "medida")

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

    def test_y_el_del_humano_dice_MEDIDO_y_por_QUE_VIA(self):
        # Las dos vias siguen distinguiendose en el texto, que es todo el punto: una
        # señal SUBIDA por medida («por predicción saldria OTRA») no dice lo mismo que
        # una canonica que la medida CONFIRMA. Fundirlas en «medido» a secas perderia
        # cual de las dos cambio de veredicto al llegar el dato.
        if not HAY_HUMANO:
            self.skipTest("NOT_RUN: falta el fixture humano")
        texto = self._tabla(HUMANO)
        self.assertIn("APA_POSIBLE (medido, PolyA_DB v4.1)", texto)
        self.assertNotIn("asumido", texto)
        self.assertIn("SUBIDA aquí por MEDIDA de uso", texto)
        self.assertIn("por canonicidad, CONFIRMADA por medida de uso", texto)


if __name__ == "__main__":
    unittest.main()
