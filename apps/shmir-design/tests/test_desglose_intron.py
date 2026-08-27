"""El intrón terapéutico, pieza a pieza, con su origen. La aritmética tiene que cerrar.

Salió de una resta que no cuadraba: MVM vacío 82 nt + módulo 149 nt = 231, y el intrón
terapéutico son 296. Faltaban 65. La respuesta es que YA HAY ESPACIADORES —20 nt en 5' y
45 nt en 3', los dos `diseño de novo`— y no estaban a la vista en ningún sitio: el
desglose no se emitía, así que la única forma de encontrarlos era leer `PIECES`.

Un total que nadie puede descomponer es un total en el que no se puede confiar. Esto lo
descompone y comprueba que la suma cierra contra el ensamblado REAL, no contra otra suma.
"""

import unittest

from shmir_design import blocks
from shmir_design.introns import intron_breakdown

GUIA = "TATTTAATGTCAGTCTGATAGC"


class TestElDesgloseCIERRA(unittest.TestCase):

    def setUp(self):
        self.desglose = intron_breakdown("mvm_actual", module_length=149)

    def test_la_suma_de_las_piezas_es_el_total(self):
        self.assertEqual(
            sum(p.length for p in self.desglose.pieces), self.desglose.total
        )

    def test_y_el_total_es_el_del_ENSAMBLADO_DE_VERDAD(self):
        # Contra el intrón que monta `build_block`, no contra otra suma mía: dos sumas
        # equivocadas igual coinciden.
        real = blocks.build_block(GUIA, available=False).intron
        self.assertEqual(self.desglose.total, len(real))
        self.assertEqual(self.desglose.total, 296)

    def test_las_piezas_en_ORDEN_del_donante_al_aceptor(self):
        self.assertEqual(
            [p.name for p in self.desglose.pieces],
            ["MVM5", "espaciador5", "módulo", "espaciador3", "MVM3"],
        )

    def test_los_65_QUE_FALTABAN_son_los_espaciadores_y_se_nombran(self):
        espaciadores = [p for p in self.desglose.pieces if "espaciador" in p.name]
        self.assertEqual(sum(p.length for p in espaciadores), 65)
        self.assertEqual([p.length for p in espaciadores], [20, 45])

    def test_cada_pieza_dice_su_ORIGEN(self):
        for pieza in self.desglose.pieces:
            with self.subTest(pieza.name):
                self.assertTrue(pieza.origin.strip(), f"{pieza.name} sin origen")

    def test_los_espaciadores_salen_marcados_como_DE_NOVO(self):
        # Es lo que no se veía. Una pieza generada por nosotros y una que viene del
        # plásmido no valen lo mismo, y en el total pesan igual.
        for pieza in self.desglose.pieces:
            if "espaciador" in pieza.name:
                self.assertTrue(pieza.de_novo, f"{pieza.name} no está marcada")
            else:
                self.assertFalse(pieza.de_novo, f"{pieza.name} marcada de más")

    def test_el_resumen_enseña_la_resta_que_no_cuadraba(self):
        texto = "\n".join(self.desglose.describe())
        for trozo in ("82", "149", "231", "65", "296"):
            self.assertIn(trozo, texto)


class TestLaASIMETRIAQueNadieDeclaro(unittest.TestCase):
    """20 en 5' y 45 en 3'. No es un descuido de este desglose: es lo que hay."""

    def test_los_dos_espaciadores_NO_miden_lo_mismo(self):
        from shmir_design.spacers import SPACER3_LENGTH, SPACER5_LENGTH

        self.assertNotEqual(SPACER5_LENGTH, SPACER3_LENGTH)

    def test_y_el_de_3_se_sale_de_la_banda_20_30(self):
        # La opción 3 habla de «espaciadores de 20-30 nt». El generador hace 20 y 45, así
        # que hoy el de 3' no cumple esa banda. El test lo FIJA para que decidir una cosa
        # u otra tenga que pasar por aquí, en vez de quedarse en dos sitios distintos.
        from shmir_design.spacers import SPACER3_LENGTH

        self.assertGreater(SPACER3_LENGTH, 30)


if __name__ == "__main__":
    unittest.main()
