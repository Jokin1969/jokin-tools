"""El autoconteo esperado depende de LA HEBRA, y valía 1 para las dos.

Reportado el 2026-09-06 con la corrida delante: **siete avisos de «0 sitios» sobre once
pasajeras**, todos falsos. El argumento, que es el que decide:

    «La guía es ANTISENTIDO a la diana: su seed encuentra su sitio por construcción, así
     que 1 es lo esperado. La pasajera es SENTIDO — tiene la misma secuencia que la
     diana, no la complementaria — así que su seed no tiene por qué encontrar nada ahí.
     Cero es el resultado ESPERADO para una pasajera. Y las tres que sí tienen sitio son
     las que merecen mirarse, no al revés.»

ES EL MISMO PATRÓN QUE `ANTISENSE` EN EL BLAST (errata nº 57): un criterio correcto
movido a la otra hebra sin el supuesto que lo sostenía. Allí el descarte por orientación
era correcto en nuestro escáner y tiraba el acierto legítimo de la pasajera contra su
propia diana; aquí el «esperado: 1» es correcto para la guía y convierte lo normal de la
pasajera en una anomalía.

Y SIETE DE ONCE ES LO QUE APAGA UN GUARDIA: con esa proporción de falsos positivos, la
próxima anomalía real de pasajera se lee como ruido.
"""

import unittest

from shmir_design.offtarget import SelfCount, expected_self_count, self_count

#: La guía de `3utr:1071` y su pasajera, del panel murino. La pasajera es la de verdad:
#: `passenger_from_guide` la eligió plegando, no se teclea aquí.
GUIA = "TAATCCTACGGAACTGAGTGCA"
PASAJERA = "CGCACTCAGTTCCGTAGGATTA"
#: Su diana, tal cual está en el 3'UTR: la pasajera es SENTIDO respecto de ella.
DIANA = "TGCACTCAGTTCCGTAGGATTC"


class TestElEsperadoDependeDeLaHebra(unittest.TestCase):
    def test_la_guia_espera_UNO(self):
        self.assertEqual(expected_self_count("guia"), 1)

    def test_la_pasajera_espera_CERO(self):
        self.assertEqual(expected_self_count("pasajera"), 0)

    def test_una_hebra_que_no_se_conoce_ABORTA(self):
        """No se elige un esperado por nuestra cuenta: son dos hebras con dos
        geometrías, y una tercera no tiene valor por defecto que valga."""
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError):
            expected_self_count("otra")


class TestSobreLaDianaDeVERDAD(unittest.TestCase):
    """Con la diana real de `3utr:1071`, medido y no supuesto."""

    def test_la_guia_encuentra_SU_sitio(self):
        conteo = self_count(GUIA, target=DIANA, target_label="su diana",
                            strand_name="guia")
        self.assertEqual(conteo.occurrences, 1)
        self.assertFalse(conteo.anomalous)

    def test_la_pasajera_NO_encuentra_ninguno_y_eso_es_lo_ESPERADO(self):
        conteo = self_count(PASAJERA, target=DIANA, target_label="su diana",
                            strand_name="pasajera")
        self.assertEqual(conteo.occurrences, 0)
        self.assertFalse(conteo.anomalous, "cero es lo normal en una pasajera")

    def test_y_una_pasajera_CON_sitio_SI_es_lo_que_hay_que_mirar(self):
        """Se invierte la lectura: lo anómalo es tenerlo. Se construye metiendo el
        núcleo de la pasajera en la propia diana — no es una secuencia biológica, es la
        diana real con su propio núcleo repetido."""
        from shmir_design.offtarget import site_patterns

        nucleo = site_patterns(PASAJERA).core
        conteo = self_count(
            PASAJERA, target=DIANA + nucleo + "AAAA", target_label="su diana",
            strand_name="pasajera",
        )
        self.assertGreaterEqual(conteo.occurrences, 1)
        self.assertTrue(conteo.anomalous)


class TestElTextoNoDiceLoContrario(unittest.TestCase):
    def test_un_cero_de_pasajera_NO_dice_que_no_salga_de_la_diana(self):
        texto = SelfCount(
            query="p", target_label="d", occurrences=0, sites={}, expected=0,
        ).describe()
        self.assertNotIn("NO sale de esa diana", texto)
        self.assertNotIn("ANOMALO", texto)

    def test_pero_un_cero_de_GUIA_lo_sigue_diciendo(self):
        texto = SelfCount(
            query="g", target_label="d", occurrences=0, sites={}, expected=1,
        ).describe()
        self.assertIn("NO sale de esa diana", texto)

    def test_y_una_pasajera_CON_sitio_dice_por_que_importa(self):
        texto = SelfCount(
            query="p", target_label="d", occurrences=1, sites={}, expected=0,
        ).describe()
        self.assertIn("sentido", texto.lower())


if __name__ == "__main__":
    unittest.main()
