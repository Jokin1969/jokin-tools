"""Tests de la accesibilidad de la diana (bloque 4, paso 13).

Regla 5: escritos antes de implementarla.

Es el peor predicho de todos los criterios, y por eso va de DESEMPATE, nunca de filtro.
Con diez candidatos se quiere el numero para poder correlacionarlo despues contra el
knockdown medido: si resulta que no predice nada, se sabra; si predice, tambien.

Que se calcula: plegado local de una ventana de contexto alrededor de la diana, y la
fraccion de las 22 bases que queda sin aparear, mas el desglose de las posiciones que
emparejan con la seed de la guia. La eleccion de la ventana de contexto IMPORTA, asi que
se calculan dos (+/-80 y +/-150) y las dos salen en el informe.

ViennaRNA es una dependencia OPCIONAL: sin ella todo esto es NOT_RUN, que no es cero.
"""

import unittest

from shmir_design.accessibility import (
    CONTEXT_WINDOWS,
    Accessibility,
    accessibility_of,
    context_slice,
)
from shmir_design.filters import FilterState
from shmir_design.folding import VIENNA_AVAILABLE

SONDA = "GCGTCAGTACGATCGAATTACT" * 20   # 440 nt


class TestVentanaDeContexto(unittest.TestCase):

    def test_las_dos_ventanas_por_defecto_son_80_y_150(self):
        self.assertEqual(CONTEXT_WINDOWS, (80, 150))

    def test_el_contexto_rodea_la_diana(self):
        tramo, offset = context_slice(SONDA, start=200, length=22, flank=80)
        self.assertEqual(len(tramo), 22 + 160)
        self.assertEqual(offset, 80)

    def test_cerca_del_principio_el_contexto_se_recorta_y_el_offset_lo_dice(self):
        tramo, offset = context_slice(SONDA, start=10, length=22, flank=80)
        self.assertEqual(offset, 9)
        self.assertEqual(tramo[offset : offset + 22], SONDA[9:31])

    def test_cerca_del_final_tambien(self):
        tramo, offset = context_slice(SONDA, start=len(SONDA) - 21, length=22, flank=80)
        self.assertEqual(tramo[offset : offset + 22], SONDA[-22:])

    def test_el_tramo_contiene_siempre_la_diana_entera(self):
        for inicio in (1, 5, 200, len(SONDA) - 21):
            tramo, offset = context_slice(SONDA, start=inicio, length=22, flank=150)
            self.assertEqual(
                tramo[offset : offset + 22], SONDA[inicio - 1 : inicio + 21]
            )

    def test_una_diana_que_no_cabe_aborta(self):
        with self.assertRaises(ValueError):
            context_slice(SONDA, start=len(SONDA), length=22, flank=80)


@unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no está instalado")
class TestCalculo(unittest.TestCase):

    def test_devuelve_una_fraccion_entre_0_y_1(self):
        a = accessibility_of(SONDA, start=200, length=22)
        for flanco in CONTEXT_WINDOWS:
            self.assertGreaterEqual(a.unpaired_fraction[flanco], 0.0)
            self.assertLessEqual(a.unpaired_fraction[flanco], 1.0)

    def test_calcula_las_dos_ventanas(self):
        a = accessibility_of(SONDA, start=200, length=22)
        self.assertEqual(set(a.unpaired_fraction), set(CONTEXT_WINDOWS))

    def test_desglosa_la_seed(self):
        a = accessibility_of(SONDA, start=200, length=22)
        for flanco in CONTEXT_WINDOWS:
            self.assertGreaterEqual(a.seed_unpaired_fraction[flanco], 0.0)
            self.assertLessEqual(a.seed_unpaired_fraction[flanco], 1.0)

    def test_guarda_la_estructura_para_poder_mirarla(self):
        a = accessibility_of(SONDA, start=200, length=22)
        for flanco in CONTEXT_WINDOWS:
            self.assertEqual(len(a.structure[flanco]), 22)
            self.assertTrue(set(a.structure[flanco]) <= set(".()"))

    def test_una_diana_toda_apareada_da_fraccion_baja(self):
        """Una horquilla perfecta deja la diana emparejada."""
        tallo = "GGGGGGGGGGGGGGGGGGGGGG"
        secuencia = "A" * 50 + tallo + "AAAA" + "CCCCCCCCCCCCCCCCCCCCCC" + "A" * 50
        a = accessibility_of(secuencia, start=51, length=22)
        self.assertLess(a.unpaired_fraction[80], 0.5)

    def test_una_diana_en_medio_de_poli_A_da_fraccion_alta(self):
        secuencia = "A" * 200
        a = accessibility_of(secuencia, start=90, length=22)
        self.assertGreater(a.unpaired_fraction[80], 0.9)

    def test_el_estado_es_PASS_nunca_FAIL(self):
        """Es un numero de desempate: no descarta a nadie, jamas."""
        a = accessibility_of(SONDA, start=200, length=22)
        self.assertIs(a.state, FilterState.PASS)

    def test_la_energia_del_contexto_se_guarda(self):
        a = accessibility_of(SONDA, start=200, length=22)
        for flanco in CONTEXT_WINDOWS:
            self.assertIsInstance(a.energy[flanco], float)


class TestSinViennaRNA(unittest.TestCase):

    def test_sin_ViennaRNA_es_NOT_RUN(self):
        a = accessibility_of(SONDA, start=200, length=22, available=False)
        self.assertIs(a.state, FilterState.NOT_RUN)

    def test_NOT_RUN_no_es_cero_Y_LO_DICE(self):
        """Sigue sin ser cero, y ademas la celda dice cual de los dos casos es.

        Vacia se leia igual que «no se pidio», y son dos cosas: esta se arregla
        instalando ViennaRNA, la otra marcando una casilla. Ver `FilterState.NO_PEDIDO`.
        """
        a = accessibility_of(SONDA, start=200, length=22, available=False)
        self.assertEqual(a.unpaired_fraction, {})
        self.assertEqual(a.as_column(), "NOT_RUN")
        self.assertNotEqual(a.as_column(), "0")

    def test_y_NO_PEDIDO_es_OTRA_celda(self):
        from shmir_design.accessibility import NOT_ASKED, Accessibility

        sin_pedir = Accessibility(state=FilterState.NO_PEDIDO, reason=NOT_ASKED)
        self.assertEqual(sin_pedir.as_column(), "NO_PEDIDO")
        # La distincion entera: las dos celdas tienen que poder leerse aparte.
        pedida = accessibility_of(SONDA, start=200, length=22, available=False)
        self.assertNotEqual(sin_pedir.as_column(), pedida.as_column())

    def test_el_motivo_dice_como_arreglarlo(self):
        a = accessibility_of(SONDA, start=200, length=22, available=False)
        self.assertIn("ViennaRNA", a.reason)


class TestSalida(unittest.TestCase):

    def test_es_un_Accessibility(self):
        self.assertIsInstance(
            accessibility_of(SONDA, start=200, length=22, available=False), Accessibility
        )

    @unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no está instalado")
    def test_la_columna_es_la_fraccion_de_la_ventana_principal(self):
        a = accessibility_of(SONDA, start=200, length=22)
        self.assertEqual(a.as_column(), f"{a.unpaired_fraction[CONTEXT_WINDOWS[0]]:.2f}")

    @unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no está instalado")
    def test_el_texto_saca_las_dos_ventanas(self):
        texto = accessibility_of(SONDA, start=200, length=22).format_text()
        for flanco in CONTEXT_WINDOWS:
            self.assertIn(str(flanco), texto)

    @unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no está instalado")
    def test_el_texto_avisa_de_que_es_desempate_y_no_filtro(self):
        texto = accessibility_of(SONDA, start=200, length=22).format_text()
        self.assertIn("desempate", texto.lower())

    @unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no está instalado")
    def test_el_texto_dice_si_las_dos_ventanas_discrepan(self):
        texto = accessibility_of(SONDA, start=200, length=22).format_text()
        self.assertIn("ventana", texto.lower())


if __name__ == "__main__":
    unittest.main()
