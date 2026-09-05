"""«Descarta 1 de 88» y «atrapó un shmiR anti-ADAR» van JUNTAS o se leen mal.

**Decidido (2026-09-05)**, con las palabras con que se pidió: *«que las dos frases vayan
juntas en el informe, porque separadas se leen mal: "descarta 1 de 88" suena a filtro
inútil, y "atrapó un shmiR anti-ADAR" suena a filtro decisivo. Es las dos cosas»*.

Es la misma forma que «rebaja, no descarta» y que el «QUÉ MIDE / QUÉ NO MIDE» del ensayo
de RT-qPCR: dos cláusulas que sólo dicen la verdad juntas.

**La TASA se deriva de la corrida**; lo que NO puede derivar la app es **por qué importa
ese gen**, y eso va declarado con su autorización escrita — mismo criterio que
`mirna.CORE_ABUNDANT`: en código y no en un fichero, porque cambiarlo cambia la lectura
de todos los informes a la vez y en un fichero se cambiaría sin verse en el diff.

Regla 5: escrito antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import specificity  # noqa: E402


class TestLaDECLARACION_de_consecuencia(unittest.TestCase):
    """Un accession no dice nada; lo que decide es qué gen es."""

    def test_ADAR_esta_declarado(self):
        self.assertIn("NM_019655.4", specificity.CONSEQUENCE_DECLARED)

    def test_y_su_motivo_trae_las_TRES_razones(self):
        texto = specificity.CONSEQUENCE_DECLARED["NM_019655.4"].lower()
        # maquinaria del propio sistema de ARN de doble cadena
        self.assertIn("doble cadena", texto)
        # esencial en neurona: edita GluA2 en Q/R
        self.assertIn("glua2", texto)
        # y cómo se leería el fallo
        self.assertIn("neurodegener", texto)

    def test_la_autorizacion_esta_ESCRITA(self):
        self.assertTrue(specificity.CONSEQUENCE_AUTHORIZATION.strip())
        self.assertIn("2026-09-05", specificity.CONSEQUENCE_AUTHORIZATION)

    def test_un_accession_no_declarado_NO_inventa_motivo(self):
        # Sin declaración se emite el accession y nada más: deducir la consecuencia de
        # un gen por su número sería exactamente lo que la regla 1 prohíbe con otra cara.
        self.assertEqual(specificity.consequence_of("NM_999999.1"), "")


class TestLasDosFrasesVANJUNTAS(unittest.TestCase):

    def test_la_lectura_trae_LA_TASA_y_LO_QUE_ATRAPA(self):
        texto = specificity.discrimination_reading(
            total=88, caidos=1,
            atrapados={"mouse_pos1746": ("NM_019655.4",)},
        )
        # La TASA, con sus dos cifras: cuántos caen y sobre cuántos.
        self.assertIn("1", texto)
        self.assertIn("88", texto)
        self.assertIn("ADAR", texto)

    def test_y_NINGUNA_puede_ir_sola(self):
        texto = specificity.discrimination_reading(
            total=88, caidos=1,
            atrapados={"mouse_pos1746": ("NM_019655.4",)},
        )
        # La frase de la tasa dice expresamente que no discrimina entre candidatos…
        self.assertIn("no es lo que discrimina", texto.lower())
        # …y la otra, que lo que atrapa lo justifica igual.
        self.assertIn("y aun así", texto.lower())

    def test_sin_nada_atrapado_la_tasa_NO_se_emite_sola(self):
        # «Muerde 1 de cada 88» sin decir qué atrapó es la mitad que suena a filtro
        # inútil. Sin capturas se dice que no ha caído ninguno, que es otra cosa.
        texto = specificity.discrimination_reading(total=88, caidos=0, atrapados={})
        self.assertIn("ninguno", texto.lower())
        self.assertNotIn("no es lo que discrimina", texto.lower())

    def test_el_gen_sin_declarar_sale_por_su_ACCESSION(self):
        texto = specificity.discrimination_reading(
            total=10, caidos=1, atrapados={"mouse_pos1": ("NM_999999.1",)},
        )
        self.assertIn("NM_999999.1", texto)


if __name__ == "__main__":
    unittest.main()
