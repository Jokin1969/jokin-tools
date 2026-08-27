"""La elección de espaciador dice sobre CUÁNTOS candidatos válidos descansa.

Es el mismo fallo que el barrido de longitudes, un nivel más abajo. Allí cada longitud
llevaba UNA secuencia y longitud y secuencia quedaban confundidas. Aquí, si de 300
candidatos plegados sólo UNO conserva la estructura, «el mejor» es el único — y un caso
no distingue «esto funciona» de «esto acierta por suerte». El criterio no cambia; lo que
cambia es que el número se emite en vez de quedarse dentro.

No hay umbral inventado: la frontera es UNO frente a MÁS DE UNO, que es exactamente el
corolario de la errata nº 10.
"""

import unittest

from shmir_design import spacers


class TestCuantosVALIDOS(unittest.TestCase):

    def _buscar(self, cuantos_pasan):
        """Búsqueda con un `assemble` de mentira que deja pasar N candidatos."""
        vistos = {"n": 0}
        horquilla = "G" * 97

        def assemble(e5, e3):
            vistos["n"] += 1
            # Los `cuantos_pasan` primeros NO estándar conservan la estructura.
            conserva = 1 < vistos["n"] <= cuantos_pasan + 1
            relleno = "." if conserva else "("
            return e5 + horquilla + e3 if conserva else e5 + horquilla + e3

        return vistos, assemble, horquilla

    def test_la_busqueda_declara_cuantos_validos_encontro(self):
        resultado = spacers.choose_spacers(
            hairpin="G" * 97,
            structure_alone="." * 97,
            assemble=lambda e5, e3: e5 + "G" * 97 + e3,
            budget=30,
        )
        self.assertTrue(hasattr(resultado, "valid_count"))
        self.assertIsInstance(resultado.valid_count, int)

    def test_si_descansa_en_UNO_SOLO_se_dice(self):
        resultado = spacers.SpacerSearch(
            choice=None, evaluated=300, rejected=0, note="", valid_count=1
        )
        self.assertTrue(resultado.single_candidate)
        self.assertIn("UN solo candidato", resultado.thinness_warning)
        self.assertIn("suerte", resultado.thinness_warning.lower())

    def test_con_varios_NO_hay_aviso(self):
        resultado = spacers.SpacerSearch(
            choice=None, evaluated=300, rejected=0, note="", valid_count=7
        )
        self.assertFalse(resultado.single_candidate)
        self.assertEqual(resultado.thinness_warning, "")

    def test_el_caso_base_NO_cuenta_como_delgado(self):
        # Si los estándar funcionan no se ha buscado nada, y decir «descansa en uno»
        # sería confundir «no hizo falta buscar» con «apenas se encontró».
        resultado = spacers.choose_spacers(
            hairpin="G" * 97,
            structure_alone="." * 97,
            assemble=lambda e5, e3: e5 + "G" * 97 + e3,
            budget=30,
        )
        if resultado.choice is not None and resultado.choice.standard:
            self.assertFalse(resultado.single_candidate)


class TestLaLONGITUD_NO_SE_EXPLORA(unittest.TestCase):
    """20/45 fijos, y el motivo escrito donde se ve."""

    def test_las_longitudes_son_las_declaradas(self):
        self.assertEqual(spacers.SPACER5_LENGTH, 20)
        self.assertEqual(spacers.SPACER3_LENGTH, 45)

    def test_y_hay_una_entrada_de_JUSTIFICACION_que_dice_que_no_hay_numero(self):
        from shmir_design.justificacion import OTHER_THRESHOLDS

        entrada = next(x for x in OTHER_THRESHOLDS if x.key == "spacer_lengths")
        self.assertEqual(entrada.origin, "convencion")
        # ACTUALIZADO al medir el 0 de verdad (errata nº 16): decía «NO DISCRIMINÓ» a
        # secas, y eso era cierto de la corrida en la que el punto 0 devolvía los
        # espaciadores ESTÁNDAR. Con el 0 bien medido el lado 3' SÍ discrimina, por
        # poco. Lo que el barrido sigue sin dar es un NÚMERO que justifique 20 y 45.
        self.assertIn("NO da es un número", entrada.no_measured_basis)
        self.assertIn("comparable", entrada.rationale)

    def test_el_motivo_de_NO_explorar_esta_escrito(self):
        self.assertIn("comparable", spacers.WHY_FIXED_LENGTHS)
        # Y el motivo va POR LADO, no en una frase única: son dos resultados distintos
        # y colapsarlos es lo que hacía falsa la versión anterior. Ver errata nº 16.
        self.assertIn("único largo admisible", spacers.WHY_FIXED_LENGTHS)
        self.assertIn("5'", spacers.WHY_FIXED_LENGTHS)
        self.assertIn("3'", spacers.WHY_FIXED_LENGTHS)

    def test_y_la_PALANCA_de_donante_punto_queda_anotada(self):
        # No son los espaciadores: es el módulo, 149 de los 214 nt intercalados.
        self.assertIn("módulo", spacers.WHY_FIXED_LENGTHS)
        self.assertIn("149", spacers.WHY_FIXED_LENGTHS)


if __name__ == "__main__":
    unittest.main()
