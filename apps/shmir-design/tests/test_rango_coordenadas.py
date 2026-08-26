"""El marco correcto no se puede garantizar; el IMPOSIBLE si se puede detectar.

Regla 5: escritos antes.

`coords.Position` impide construir una posicion SIN marco. Lo que no impedia es declarar
el marco EQUIVOCADO, y eso ha vuelto a pasar tres veces en una semana:

  - `apa_ceiling_table` imprimio `3utr:1784` sobre un 3'UTR humano de 1606 nt, y salio en
    un informe que ya se estaba entregando;
  - los tramos de techo salieron como `3utr:1-1200` … `3utr:1273-2191` sobre un 3'UTR
    murino de 1242 nt;
  - los dos por lo mismo: `Frame.UTR3` puesto a pelo donde el marco tenia que RECIBIRSE.

Ninguno dio error. Los dos son coordenadas del TRANSCRITO etiquetadas como 3'UTR, y las
dos se leen sin sospechar nada.

El invariante que si los caza: una posicion en `3utr` no puede pasarse de la longitud del
3'UTR mas largo que conoce el proyecto. No prueba que el marco sea el bueno —eso necesita
contexto que la clase no tiene— pero convierte el fallo silencioso en un aborto.
"""

import unittest

from shmir_design import coords
from shmir_design.coords import Frame, Position
from shmir_design.reference import REFERENCES


class TestElTechoSaleDeLasReferencias(unittest.TestCase):

    def test_no_esta_TECLEADO_sale_de_REFERENCES(self):
        self.assertEqual(
            coords.max_utr3(),
            max(r.utr3_length for r in REFERENCES.values()),
        )

    def test_hoy_lo_pone_el_humano(self):
        self.assertEqual(coords.max_utr3(), 1606)

    def test_el_raton_cabe_de_sobra(self):
        self.assertLess(REFERENCES["NM_011170.3"].utr3_length, coords.max_utr3())


class TestLosDosCasosQueAcabanDeAparecer(unittest.TestCase):

    def test_3utr_1784_sobre_un_3UTR_humano_de_1606_ABORTA(self):
        with self.assertRaises(ValueError) as ctx:
            Position(1784, Frame.UTR3)
        self.assertIn("1784", str(ctx.exception))
        self.assertIn("1606", str(ctx.exception))

    def test_y_el_mensaje_dice_que_probablemente_sea_del_TRANSCRITO(self):
        with self.assertRaises(ValueError) as ctx:
            Position(1784, Frame.UTR3)
        self.assertIn("tx", str(ctx.exception))

    def test_el_tramo_3utr_1273_2191_ABORTA_por_su_extremo(self):
        with self.assertRaises(ValueError):
            coords.span(1273, 2191, Frame.UTR3)

    def test_pero_en_su_marco_de_verdad_NO_aborta(self):
        self.assertEqual(coords.span(1273, 2191, Frame.TX), "tx:1273-2191")

    def test_un_tx_grande_NO_se_toca(self):
        # El marco del transcrito no tiene techo conocido: comprobarlo seria inventarse
        # un limite. Lo que se caza es lo IMPOSIBLE, no lo sospechoso.
        self.assertEqual(str(Position(2191, Frame.TX)), "tx:2191")

    def test_label_tambien_lo_caza(self):
        with self.assertRaises(ValueError):
            coords.label(1784, Frame.UTR3)

    def test_parse_tambien(self):
        with self.assertRaises(ValueError):
            coords.parse("3utr:1784")


class TestElLimitePorESPECIE(unittest.TestCase):
    """El techo global caza lo imposible; con la longitud de VERDAD se afina."""

    def test_1500_es_valido_para_el_humano(self):
        humano = REFERENCES["NM_000311.5"]
        self.assertEqual(
            coords.label(1500, Frame.UTR3, limit=humano.utr3_length), "3utr:1500"
        )

    def test_y_NO_lo_es_para_el_raton(self):
        raton = REFERENCES["NM_011170.3"]
        with self.assertRaises(ValueError) as ctx:
            coords.label(1500, Frame.UTR3, limit=raton.utr3_length)
        self.assertIn("1242", str(ctx.exception))

    def test_span_acepta_el_limite_igual(self):
        with self.assertRaises(ValueError):
            coords.span(1, 1300, Frame.UTR3, limit=1242)

    def test_bound_of_saca_la_longitud_de_la_anatomia(self):
        from shmir_design.anatomy import Anatomy, RegionSource

        raton = REFERENCES["NM_011170.3"]
        anatomy = Anatomy(
            length=raton.length, utr5=raton.utr5, cds=raton.cds, utr3=raton.utr3,
            source=RegionSource.ANOTACION_GENBANK,
        )
        self.assertEqual(coords.bound_of(anatomy), 1242)

    def test_sin_anatomia_no_hay_limite_y_se_dice_asi(self):
        self.assertIsNone(coords.bound_of(None))

    def test_un_limite_mayor_que_el_techo_global_NO_lo_relaja(self):
        # Pasar un limite no puede servir para colarse por encima de lo imposible.
        with self.assertRaises(ValueError):
            coords.label(9999, Frame.UTR3, limit=99999)


class TestLoQueSIGUE_valiendo(unittest.TestCase):
    """El invariante nuevo no puede romper lo que ya estaba bien."""

    def test_una_posicion_normal_del_raton(self):
        self.assertEqual(str(Position(1018, Frame.UTR3)), "3utr:1018")

    def test_el_borde_del_3UTR_mas_largo_ENTRA(self):
        self.assertEqual(Position(coords.max_utr3(), Frame.UTR3).value, 1606)

    def test_uno_mas_ya_no(self):
        with self.assertRaises(ValueError):
            Position(coords.max_utr3() + 1, Frame.UTR3)

    def test_el_0_sigue_abortando_por_1_based(self):
        with self.assertRaises(ValueError):
            Position(0, Frame.UTR3)


if __name__ == "__main__":
    unittest.main()
