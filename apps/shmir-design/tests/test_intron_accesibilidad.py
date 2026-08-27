"""Accesibilidad estructural del intron. El analisis que SI corre entero.

Regla 5: escritos antes.

Es la otra mitad del cuarto modal, y es de otra naturaleza que la primera: **da un numero
propio en vez de uno prestado de un modelo entrenado para otra cosa**. Se pliega el intron
completo con el modulo dentro y se mira si el donante, el punto de ramificacion y el
aceptor quedan apareados. Un elemento secuestrado dentro de un tallo no esta disponible
para el espliceosoma.

Van juntos en el modal y SEPARADOS en el resultado: prediccion de sitios y accesibilidad
estructural son dos preguntas.
"""

import unittest

from shmir_design import blocks, intron_folding, introns
from shmir_design.filters import FilterState
from shmir_design.folding import VIENNA_AVAILABLE

MODULO = "A" * blocks.MODULE_LENGTH


class TestSinViennaRNA_NO_SE_INVENTA_NADA(unittest.TestCase):

    def test_sale_NOT_RUN_con_el_motivo(self):
        resultado = intron_folding.fold_intron(
            introns.INTRONS["mvm_actual"], module=MODULO, available=False
        )
        self.assertIs(resultado.state, FilterState.NOT_RUN)
        self.assertIn("ViennaRNA", resultado.reason)

    def test_y_las_probabilidades_van_VACIAS_no_a_cero(self):
        """No haber plegado y plegar y salir apareado son cosas distintas."""
        resultado = intron_folding.fold_intron(
            introns.INTRONS["mvm_actual"], module=MODULO, available=False
        )
        self.assertEqual(resultado.unpaired, {})
        self.assertIsNone(resultado.energy)


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: ViennaRNA no está instalado")
class TestElPlegadoDeVerdad(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.resultado = intron_folding.fold_intron(
            introns.INTRONS["mvm_actual"], module=MODULO
        )

    def test_corre_y_da_los_CUATRO_elementos(self):
        # Eran tres —donante, punto y ACEPTOR— y el tracto faltaba. Los TRES FRÁGILES
        # son donante, punto y tracto; el aceptor es la frontera. Sin el tracto no se
        # podía evaluar el criterio de aceptación de los espaciadores.
        self.assertIs(self.resultado.state, FilterState.PASS)
        # Por IDENTIDAD, no por cantidad. La version anterior comprobaba que salieran
        # TRES —y salian tres— mientras faltaba el tracto: contar no es comprobar. Ver
        # la errata nº 12.
        self.assertEqual(
            set(self.resultado.unpaired), set(intron_folding.ELEMENTS)
        )
        self.assertIn("tracto_polipirimidinas", self.resultado.unpaired)
        self.assertEqual(len(intron_folding.ELEMENTS), 4)

    def test_y_los_TRES_FRAGILES_estan_entre_ellos(self):
        # `barrido.FRAGILE` es OTRA lista y otra pregunta: cuales de los cuatro son los
        # que el criterio de aceptacion de los espaciadores mira. El aceptor no esta.
        from shmir_design.barrido import FRAGILE

        self.assertTrue(set(FRAGILE) <= set(intron_folding.ELEMENTS))
        self.assertNotIn("aceptor", FRAGILE)

    def test_cada_uno_es_una_FRACCION_entre_cero_y_uno(self):
        for nombre, valor in self.resultado.unpaired.items():
            self.assertGreaterEqual(valor, 0.0, nombre)
            self.assertLessEqual(valor, 1.0, nombre)

    def test_la_energia_sale_y_es_NEGATIVA(self):
        self.assertLess(self.resultado.energy, 0)

    def test_la_estructura_mide_lo_MISMO_que_el_intron(self):
        self.assertEqual(len(self.resultado.structure), self.resultado.length)

    def test_el_intron_montado_es_el_que_se_pliega_no_el_vacio(self):
        self.assertEqual(self.resultado.length, blocks.INTRON_LENGTH)

    def test_el_punto_de_ramificacion_sale_por_CANDIDATO_no_uno_solo(self):
        """Si caben varios YURAY no se elige: se informa de todos."""
        self.assertTrue(self.resultado.branch_detail)
        for fila in self.resultado.branch_detail:
            self.assertIn("posicion", fila)
            self.assertIn("desapareado", fila)

    def test_NO_hay_umbral_ni_veredicto(self):
        """Desempate y alerta, nunca filtro: no puede excluir a nadie."""
        self.assertNotIn("FAIL", self.resultado.describe())
        self.assertIn("desempate", self.resultado.describe().lower())

    def test_dos_modulos_distintos_dan_numeros_distintos(self):
        """Es lo que hace el analisis util: compara construcciones, no absolutos."""
        otro = intron_folding.fold_intron(
            introns.INTRONS["mvm_actual"], module="G" * blocks.MODULE_LENGTH
        )
        self.assertNotEqual(otro.energy, self.resultado.energy)


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: ViennaRNA no está instalado")
class TestLoQueMIDE_Y_LO_QUE_NO(unittest.TestCase):
    """Dos hechos medidos el 2026-08-26, y el segundo es el que da sentido al primero.

    Sobre el panel murino de referencia los seis candidatos dan **el mismo** perfil de
    accesibilidad —donante 0,89, ramificacion 0,29, aceptor 0,84— y solo cambia la
    energia. O sea: **en el intron MVM, la guia no mueve la accesibilidad de los tres
    elementos**; la deciden los extremos del propio intron. Este eje NO discrimina entre
    estos seis candidatos, y decir lo contrario seria vender como desempate algo que da
    el mismo numero a todos.

    Pero eso NO es que el analisis sea ciego, y hay que poder distinguirlo: un modulo
    COMPLEMENTARIO al extremo 5' del intron lo mueve de 0,89 a 0,00. O sea, el analisis
    cazaria una guia que secuestrara un elemento; lo que dice el primer hecho es que
    ninguna de estas seis lo hace. Sin el control adversario, «todos iguales» y «no mide
    nada» serian el mismo resultado.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design.reference import REFERENCES, fixture_available, load_3utr

        cls.raton = REFERENCES["NM_011170.3"]
        cls.hay = fixture_available(cls.raton)
        if cls.hay:
            cls.utr3 = load_3utr(cls.raton)

    def _perfil(self, modulo):
        return intron_folding.fold_intron(
            introns.INTRONS["mvm_actual"], module=modulo
        )

    def test_los_seis_del_panel_dan_el_MISMO_perfil(self):
        if not self.hay:
            self.skipTest("NOT_RUN: falta el fixture del raton")
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        seleccion = select_from_report(
            tile_utr(self.utr3), SelectionConfig(n_candidates=6)
        )
        perfiles = []
        for elegido in seleccion.selection.chosen:
            guia = self.utr3[elegido.start - 1:elegido.end]
            bloque = blocks.build_block(guia, scaffold=SGEP_SCAFFOLD)
            perfiles.append(self._perfil(bloque.module).unpaired)
        for nombre in intron_folding.ELEMENTS:
            valores = [round(p[nombre], 2) for p in perfiles]
            self.assertEqual(
                len(set(valores)), 1,
                f"{nombre}: {valores} — si esto deja de ser plano, algo cambio",
            )

    def test_y_los_valores_son_LOS_MEDIDOS(self):
        if not self.hay:
            self.skipTest("NOT_RUN: falta el fixture del raton")
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        seleccion = select_from_report(
            tile_utr(self.utr3), SelectionConfig(n_candidates=6)
        )
        primero = seleccion.selection.chosen[0]
        bloque = blocks.build_block(
            self.utr3[primero.start - 1:primero.end], scaffold=SGEP_SCAFFOLD
        )
        perfil = self._perfil(bloque.module).unpaired
        self.assertAlmostEqual(perfil["donante"], 0.89, places=2)
        # 0.26 y no 0.29: el punto de ramificación se movió un nucleótido al recalibrar
        # el motivo (`YURAY` leía TAATT en 43-47, `YTNAY` lee TTAAT en 42-46 — la MISMA
        # A, otro marco de lectura), y el perfil se mide sobre las posiciones del
        # elemento. El número no se ajustó a mano: es lo que sale ahora.
        self.assertAlmostEqual(perfil["punto_de_ramificacion"], 0.26, places=2)
        self.assertAlmostEqual(perfil["aceptor"], 0.84, places=2)

    def test_pero_un_modulo_ADVERSARIO_SI_lo_mueve(self):
        """Sin esto, «todos iguales» y «no mide nada» serian el mismo resultado."""
        vacio = introns.INTRONS["mvm_actual"].empty_sequence
        complemento = {"A": "T", "T": "A", "G": "C", "C": "G"}
        reverso = "".join(complemento[b] for b in reversed(vacio[:20]))
        adversario = (reverso * 8)[:blocks.MODULE_LENGTH]
        perfil = self._perfil(adversario).unpaired
        self.assertLess(perfil["donante"], 0.10)
        self.assertLess(perfil["aceptor"], 0.10)

    def test_el_intron_VACIO_tiene_los_elementos_MAS_accesibles(self):
        """El del parental, sin modulo: 0,96 y 0,96. Meter el modulo los baja algo, y
        eso es informacion sobre el modulo, no sobre la guia."""
        vacio = introns.INTRONS["mvm_actual"]
        from shmir_design.folding import unpaired_probabilities
        from shmir_design.introns import locate_elements

        secuencia = vacio.empty_sequence
        elementos = locate_elements(secuencia, name="vacio")
        p = unpaired_probabilities(secuencia)
        donante = sum(p[elementos.donor.start - 1:elementos.donor.end]) / 2
        self.assertGreater(donante, 0.90)


class TestElResultadoSE_PUEDE_LEER_SOLO(unittest.TestCase):

    def test_el_bloque_dice_QUE_significa_un_elemento_apareado(self):
        texto = intron_folding.WHY_IT_MATTERS
        self.assertIn("espliceosoma", texto)
        self.assertIn("tallo", texto.lower())

    def test_y_que_este_numero_es_PROPIO_no_prestado(self):
        self.assertIn("propio", intron_folding.WHY_ITS_OURS.lower())


if __name__ == "__main__":
    unittest.main()
