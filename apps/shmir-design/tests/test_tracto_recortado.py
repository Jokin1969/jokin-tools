"""El tracto que TOCA el borde de su ventana sale marcado como sospechoso.

Regla 5: escrito antes.

`_ppt_span` busca la racha de pirimidinas más larga en los 40 nt de delante del aceptor
(`PPT_WINDOW`). Si la racha EMPIEZA justo en el borde de esa ventana y la base anterior
también es pirimidina, lo que se emite no es la racha: es la parte de la racha que cabía.
El número sale más pequeño que el real y no lo dice.

Ninguno de los dos intrones de hoy lo toca —MVM 9 pirimidinas, quimérico 11, las dos muy
dentro—, y ése es exactamente el motivo de declararlo en vez de arreglarlo por si acaso:
la auditoría de geometría existe para vigilar lo que hoy no muerde. Un tercer intrón con
un tracto largo lo tocaría, y entonces el aviso ya estaría escrito.

Es hermano del principio nº 7: el invariante caza lo imposible; esto es un valor
PERFECTAMENTE POSIBLE y equivocado, así que no hay invariante que lo cubra — sólo
decirlo.
"""

import unittest

from shmir_design import introns


class TestLosDosIntronesDeHoyNoLoTocan(unittest.TestCase):
    def test_el_MVM(self):
        elementos = introns.INTRONS["mvm_actual"].elements()
        self.assertFalse(elementos.ppt.clipped_by_window)

    def test_el_quimerico(self):
        elementos = introns.INTRONS["intron_quimerico"].elements()
        self.assertFalse(elementos.ppt.clipped_by_window)

    def test_y_sus_tractos_son_los_declarados(self):
        self.assertEqual(len(introns.INTRONS["mvm_actual"].elements().ppt.sequence), 9)
        self.assertEqual(
            len(introns.INTRONS["intron_quimerico"].elements().ppt.sequence), 11
        )


class TestUnoQueSILoToca(unittest.TestCase):
    """Construido a mano sobre pirimidinas, no una secuencia biológica inventada.

    No viola la regla 1: no es un intrón que se vaya a pedir ni a plegar — es la entrada
    de una función de conteo, hecha de una sola base repetida para que la geometría sea
    evidente al leerla.
    """

    def _span(self, largo_tracto: int, relleno: int):
        # Ventana de 40 nt delante del AG. Con un tracto mas largo que la ventana, la
        # racha empieza FUERA y lo que se mide es el trozo que cabe.
        secuencia = "GT" + "A" * 20 + "C" * largo_tracto + "A" * relleno + "AG"
        return introns._ppt_span(secuencia, len(secuencia) - 1), secuencia

    def test_un_tracto_mas_largo_que_la_ventana_se_recorta(self):
        (ini, fin), secuencia = self._span(60, 0)
        self.assertEqual(fin - ini + 1, introns.PPT_WINDOW)

    def test_y_la_base_de_delante_del_borde_SIGUE_siendo_pirimidina(self):
        (ini, _), secuencia = self._span(60, 0)
        self.assertIn(secuencia[ini - 2], "CT")

    def test_uno_que_cabe_entero_no_se_recorta(self):
        (ini, fin), _ = self._span(10, 5)
        self.assertEqual(fin - ini + 1, 10)


class TestElInformeLoDICE(unittest.TestCase):
    def test_la_regla_esta_declarada(self):
        self.assertTrue(introns.WHY_THE_WINDOW_CAN_CLIP.strip())

    def test_el_informe_de_geometria_la_nombra(self):
        from shmir_design.presentation import intron_geometry_text

        texto = intron_geometry_text()
        self.assertIn("ventana", texto.lower())
        self.assertIn("40", texto)

    def test_y_dice_que_HOY_no_muerde(self):
        from shmir_design.presentation import intron_geometry_text

        self.assertIn("ninguno", intron_geometry_text().lower())


if __name__ == "__main__":
    unittest.main()
