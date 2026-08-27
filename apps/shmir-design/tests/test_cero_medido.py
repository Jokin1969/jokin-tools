"""El punto 0 del barrido, MEDIDO de verdad, y lo que cambia al medirlo.

Regla 5: escrito antes del arreglo, corrido después.

Hasta la errata nº 16 el punto 0 de la curva no medía la ausencia de espaciador: medía
los 20/45 ESTÁNDAR, porque `with_module` resolvía `spacer5 or PIECES[...]` y la cadena
vacía es falsa. O sea que la fila «0 nt» era una copia de la fila de referencia, y
entraba en el recorrido y en la dispersión como si fuera un punto más.

Con el centinela arreglado, el barrido se ha vuelto a correr entero (ViennaRNA presente,
5 réplicas por longitud) y **el resultado NO es el mismo en los dos lados**:

  · **lado 5' — sigue sin discriminar**, y limpiamente: recorridos 0,09 / 0,29 / 0,01
    contra dispersiones 0,21 / 0,46 / 0,02. Los tres elementos, por debajo.
  · **lado 3' — SÍ discrimina en dos de los tres**: donante 0,58 contra 0,54 y punto de
    ramificación 0,40 contra 0,36. Por poco —un 7 % y un 11 %— pero por encima.

Así que la frase «el barrido no discriminó» era cierta de la corrida vieja y **es falsa
de la nueva para el lado 3'**. Lo que NO cambia es la decisión: en los dos lados el
único largo admisible sigue siendo el punto de partida, o sea que ninguna longitud más
corta mejora nada. 20/45 se quedan, y ahora por dos razones distintas según el lado.

Los números de aquí son los de la corrida real y se fijan para que un cambio en el
plegado o en el módulo se vea como un diff, no como una frase que alguien recuerda.
"""

import unittest

from shmir_design import barrido, blocks, introns

#: La guia de referencia del proyecto, la misma que usa `tools/barrer_espaciadores.py`.
GUIA = "TATTTAATGTCAGTCTGATAGC"


class TestElCeroEsCeroDeVerdad(unittest.TestCase):
    """Lo primero: que la fila 0 mida la ausencia y no el estándar."""

    def setUp(self):
        self.mvm = introns.INTRONS["mvm_actual"]
        self.modulo = "A" * blocks.MODULE_LENGTH

    def test_el_intron_con_los_dos_espaciadores_a_cero_mide_65_nt_menos(self):
        con = self.mvm.with_module(self.modulo)
        sin = self.mvm.with_module(self.modulo, spacer5="", spacer3="")
        self.assertEqual(len(con) - len(sin), 65)

    def test_y_esos_65_son_exactamente_los_dos_estandar(self):
        self.assertEqual(len(blocks.PIECES["espaciador5"].sequence), 20)
        self.assertEqual(len(blocks.PIECES["espaciador3"].sequence), 45)


class TestLaGeometriaDelCero(unittest.TestCase):
    """donante→punto con cada espaciador a cero. Es aritmética, no plegado."""

    def _distancia(self, spacer5: str, spacer3: str) -> int:
        mvm = introns.INTRONS["mvm_actual"]
        modulo = blocks.build_block(GUIA, available=False).module
        montado = mvm.with_module(modulo, spacer5=spacer5, spacer3=spacer3)
        elementos = introns.locate_elements(montado, name="mvm_actual")
        return min(
            c.branch_a - elementos.donor.end - 1
            for c in elementos.branch_candidates
            if c.branch_a is not None
        )

    def test_con_los_de_hoy_son_256_nt(self):
        self.assertEqual(self._distancia("A" * 20, "A" * 45), 256)

    def test_quitar_el_5_entero_deja_236(self):
        self.assertEqual(self._distancia("", "A" * 45), 236)

    def test_quitar_el_3_entero_deja_211(self):
        self.assertEqual(self._distancia("A" * 20, ""), 211)

    def test_quitar_LOS_DOS_deja_191_y_ese_es_el_suelo_del_recorte(self):
        # 191 nt es TODO lo que se puede comprar recortando espaciadores, y sigue muy
        # por encima del rango tipico. Es la medida del corolario: la palanca no son
        # los espaciadores, es el modulo.
        self.assertEqual(self._distancia("", ""), 191)

    def test_el_rango_tipico_sigue_quedando_lejos(self):
        bajo, alto = introns.TYPICAL_DONOR_TO_BRANCH
        self.assertGreater(self._distancia("", ""), alto)


class TestLoQueLaFRASEPuedeDecir(unittest.TestCase):
    """El texto que justifica 20/45 no puede afirmar lo que la corrida no dice."""

    def test_no_afirma_que_NINGUN_elemento_discrimine(self):
        from shmir_design.spacers import WHY_FIXED_LENGTHS

        # «no discriminó» a secas era cierto de la corrida con el 0 mal medido.
        self.assertNotIn("no discriminó", WHY_FIXED_LENGTHS)

    def test_distingue_los_dos_lados(self):
        from shmir_design.spacers import WHY_FIXED_LENGTHS

        self.assertIn("5'", WHY_FIXED_LENGTHS)
        self.assertIn("3'", WHY_FIXED_LENGTHS)

    def test_y_dice_lo_que_SI_sostiene_la_medida(self):
        from shmir_design.spacers import WHY_FIXED_LENGTHS

        self.assertIn("admisible", WHY_FIXED_LENGTHS.lower())


class TestElBarridoSigueSiendoRELATIVO(unittest.TestCase):
    def test_el_punto_de_partida_no_se_movio(self):
        self.assertEqual(barrido.STARTING_POINT, {"5": 20, "3": 45})

    def test_y_el_rango_barrido_llega_a_cero(self):
        self.assertEqual(barrido.SWEEP_RANGE, (0, 45))


if __name__ == "__main__":
    unittest.main()
