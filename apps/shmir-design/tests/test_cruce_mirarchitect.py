"""Cruce de los scores de miRarchitect con nuestros candidatos.

Regla 5: escritos antes de tocar el importador.

Datos REALES (regla 1): las guias son las del fixture `guias_pasajera.fa` y los scores
los de `mirarchitect_prnp_raton.tsv`, la corrida manual sobre el 3'UTR de Prnp murino.
No se fabrica ninguna secuencia ni ningun numero.

Lo que se prueba aqui es el cruce por SECUENCIA, no por coordenada. miRarchitect numera
sus ventanas con un convenio que no es el nuestro —para la misma guia da a veces una
posicion y a veces otra— asi que cruzar por numero pegaria un score en la fila de otro
candidato. Las secuencias no tienen ese problema.
"""

import unittest
from pathlib import Path

from shmir_design.external_score import (
    CONFIRMED_BELOW,
    DISPLACED_SHIFT,
    MAX_SHIFT,
    MIN_OVERLAP,
    MIRARCH_COLUMNS,
    ScoreSource,
    guide_shift,
    lower_is_better,
)

SCORES = Path(__file__).resolve().parent.parent / "data" / "reference" / "mirarchitect_prnp_raton.tsv"

#: Guias reales, del fixture. Los pares salen de la corrida murina con el GenBank.
NUESTRA_1018 = "TTTAGTACTGGATGGAACGGCC"     # 3'UTR 1018, candidato #1
SUYA_1018 = "TTTAGTACTGGATGGAACGGCC"       # la misma, exacta
NUESTRA_449 = "TTTAGTAAAGAAAGAATTCCAC"     # 3'UTR 449
SUYA_444 = "TAAAGAAAGAATTCCACGTGTG"        # la de miRarchitect, 5 nt corrida
NUESTRA_819 = "TTTTCCCACTTTGGAATGGAGC"     # 3'UTR 819
SUYA_822 = "TTTCTTTCCCACTTTGGAATGG"        # 3 nt corrida
LEJANA = "TATTTAATGTCAGTCTGATAGC"          # 3'UTR 1200, a cientos de nt


class TestDesplazamiento(unittest.TestCase):

    def test_la_misma_guia_esta_a_cero(self):
        self.assertEqual(guide_shift(NUESTRA_1018, SUYA_1018), 0)

    def test_una_ventana_corrida_da_su_distancia(self):
        self.assertEqual(abs(guide_shift(NUESTRA_449, SUYA_444)), 5)

    def test_otra_ventana_corrida_da_la_suya(self):
        self.assertEqual(abs(guide_shift(NUESTRA_819, SUYA_822)), 3)

    def test_dos_guias_de_sitios_distintos_no_se_emparejan(self):
        self.assertIsNone(guide_shift(NUESTRA_1018, LEJANA))

    def test_mas_alla_del_limite_no_se_empareja(self):
        # El limite lo puso quien encargo esto: mas de 15 nt de desplazamiento y no se
        # asigna. Un solapamiento de 7 nt sobre 22 ya no es la misma ventana.
        self.assertIsNone(guide_shift(NUESTRA_449, SUYA_444, max_shift=4))

    def test_un_trozo_corto_no_empareja_con_cualquier_cosa(self):
        # Sin minimo de solapamiento, tres bases emparejan con media tabla.
        self.assertIsNone(guide_shift(NUESTRA_1018, SUYA_1018[:4]))

    def test_la_posicion_1_no_se_compara(self):
        # Los dos lados fuerzan una T ahi. En la ventana 819 esa T era el UNICO
        # desapareamiento de un solapamiento de 19 nt: compararla dejaba sin cruzar dos
        # ventanas que son la misma.
        self.assertEqual(guide_shift("A" + NUESTRA_1018[1:], NUESTRA_1018), 0)

    def test_admite_guias_de_longitud_distinta(self):
        # miRarchitect devuelve ventanas de 21, 22 y 23 nt; las nuestras son de 22.
        self.assertIsNotNone(guide_shift(NUESTRA_1018, SUYA_1018[:-1]))

    def test_el_desplazamiento_lleva_signo(self):
        # Saber hacia que lado esta corrida importa para leerla contra el mapa.
        a, b = guide_shift(NUESTRA_449, SUYA_444), guide_shift(SUYA_444, NUESTRA_449)
        self.assertEqual(a, -b)


class TestEscalaInvertida(unittest.TestCase):
    """En miRarchitect MENOR es mejor. Si esto se pierde, el ranking se lee al reves."""

    def test_miRarchitect_es_de_escala_invertida(self):
        self.assertTrue(lower_is_better(ScoreSource.MANUAL_MIRARCHITECT))

    def test_el_umbral_de_confirmacion_es_por_debajo(self):
        self.assertEqual(CONFIRMED_BELOW, 20.0)

    def test_el_umbral_de_ventana_desplazada(self):
        self.assertEqual(DISPLACED_SHIFT, 5)

    def test_el_minimo_solapamiento_sale_del_limite(self):
        self.assertEqual(MIN_OVERLAP, 22 - MAX_SHIFT)


class TestColumnas(unittest.TestCase):

    def test_las_columnas_de_bandera(self):
        self.assertEqual(
            MIRARCH_COLUMNS,
            ("mirarch_confirmado", "mirarch_rank", "mirarch_shift_nt"),
        )


@unittest.skipUnless(SCORES.is_file(), f"NOT_RUN: falta {SCORES.name}")
class TestSobreElFicheroReal(unittest.TestCase):
    """Contra las 25 lineas que devolvio la corrida manual."""

    def scores(self):
        return [
            l.rstrip("\n").split("\t")
            for l in SCORES.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("guia_dna")
        ]

    def test_el_fichero_trae_25_guias(self):
        # El encargo hablaba de 26. Son 25: hay una linea menos, y eso explica que los
        # rangos de ranking no cuadren con los del encargo (23/26 aqui es 22/25).
        self.assertEqual(len(self.scores()), 25)

    def test_todas_las_guias_empiezan_por_T(self):
        # miRarchitect fuerza una T en la posicion 1, asi que la base 1 de sus guias no
        # es necesariamente la complementaria de la diana. El cruce lo tiene en cuenta.
        self.assertTrue(all(g.startswith("T") for g, _ in self.scores()))

    def test_nuestro_candidato_1018_encuentra_su_guia_exacta(self):
        guias = [g for g, _ in self.scores()]
        exactas = [g for g in guias if guide_shift(NUESTRA_1018, g) == 0]
        self.assertEqual(exactas, [SUYA_1018])

    def test_nuestro_candidato_449_encuentra_una_corrida_5_nt(self):
        mejor = min(
            ((g, guide_shift(NUESTRA_449, g)) for g, _ in self.scores()),
            key=lambda par: 99 if par[1] is None else abs(par[1]),
        )
        self.assertEqual(mejor[0], SUYA_444)
        self.assertEqual(abs(mejor[1]), 5)


if __name__ == "__main__":
    unittest.main()
