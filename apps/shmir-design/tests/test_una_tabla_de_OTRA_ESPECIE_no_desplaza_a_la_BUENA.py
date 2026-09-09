"""Con dos tablas de PolyA_DB en el deposito, la del md5 que cuadra es la que entra.

`find_polyadb` sin especie devolvia la PRIMERA que encontraba y paraba. Su docstring
decia que eso era seguro —«la tabla se aplica por md5 de todos modos, asi que una de
otra especie no puede colarse»— y esa frase es cierta a MEDIAS: una tabla ajena no se
puede APLICAR, pero DESPLAZA a la buena, porque la busqueda se detiene en ella y la que
si cuadraba no se llega a mirar. No es un numero equivocado: es la medida perdida.

Y el orden lo decidia el alfabeto (`human` antes que `mouse`), asi que el fallo aparece
el dia que hay una segunda especie y no antes. Es el mismo patron que `rmsk_mouse.out`
conectado por su rol: algo que funciona callado mientras solo hay una especie.

MEDIDO el 2026-09-09: con `polya_db_human.tsv` en el deposito, la estimacion de coste de
la PAGINA MURINA pasaba de 390 ventanas elegibles a 407 —justo las 17 de
`measured_promotion_cost`— porque `cost_text` tila sin especie. La estimacion y la
corrida dejaban de contar lo mismo, que es la errata que hizo obligatoria la anatomia.
"""

from __future__ import annotations

import unittest

from shmir_design import apa, reference, tiling
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]


class TestElMd5DecideYNoElAlfabeto(unittest.TestCase):

    def test_hay_las_DOS_tablas_en_el_deposito(self):
        # Sin esto el test no prueba nada: con una sola, cualquier orden acierta.
        todas = apa.find_polyadb_all()
        self.assertEqual(len(todas), 2)
        self.assertEqual({t.assembly for t in todas}, {"mm10", "hg38"})

    def test_el_ALFABETO_pone_la_humana_primero(self):
        # Es la condicion que hacia el fallo posible, y se fija para que no se lea
        # como casualidad si algun dia cambia el orden.
        self.assertEqual(apa._known_slugs()[0], "human")

    def test_sobre_el_3UTR_MURINO_entra_la_MURINA(self):
        utr3 = reference.canonical_form(load_3utr(RATON), name="3'UTR")
        aplicables = [
            t for t in apa.find_polyadb_all()
            if apa.resolve_measured(utr3, t) is not None
        ]
        self.assertEqual([t.assembly for t in aplicables], ["mm10"])

    def test_sobre_el_3UTR_HUMANO_entra_la_HUMANA(self):
        utr3 = reference.canonical_form(load_3utr(HUMANO), name="3'UTR")
        aplicables = [
            t for t in apa.find_polyadb_all()
            if apa.resolve_measured(utr3, t) is not None
        ]
        self.assertEqual([t.assembly for t in aplicables], ["hg38"])


@unittest.skipUnless(fixture_available(RATON), "falta el 3'UTR murino")
class TestTilarSINESPECIEsigueAplicandoLaBuena(unittest.TestCase):
    """Es el caso de `cost_text`, que no recibe especie. La medida NO se pierde."""

    def test_la_promocion_por_medida_ENTRA(self):
        utr3 = load_3utr(RATON)
        informe = tiling.tile_utr(utr3)
        self.assertIsNotNone(informe.measured_apa)
        self.assertEqual(informe.measured_apa.table.assembly, "mm10")
        self.assertEqual(informe.apa_missing_reason, "")

    def test_y_da_LO_MISMO_que_declarando_la_especie(self):
        # La estimacion y la corrida tienen que contar sobre el mismo conjunto.
        utr3 = load_3utr(RATON)
        sin = tiling.tile_utr(utr3)
        con = tiling.tile_utr(utr3, species="raton")
        elegibles = lambda inf: sum(
            1 for w in inf.windows if w.verdict.name != "FAIL"
        )
        self.assertEqual(elegibles(sin), elegibles(con))


if __name__ == "__main__":
    unittest.main()
