"""El guardia de la regla 6 tiene que saltar donde hay logica y callar donde no.

Existe porque la version anterior buscaba `"int("` como subcadena y saltaba sobre
`run_fingerprint(`, que no convierte nada. Un guardia con falsos positivos se acaba
apagando; uno sin este test se acaba quedando sin morder.
"""

import unittest

from tests.sin_logica import comprobar_sin_logica


class TestElGuardiaMuerde(unittest.TestCase):

    def test_salta_con_una_conversion_de_verdad(self):
        for region in (
            "candidatos = int(texto)\n",
            "umbral = float(valor)\n",
            "nombre = especie.upper()\n",
            "nombre = especie.lower()\n",
            "filas = sorted(filas)\n",
        ):
            with self.subTest(region=region):
                with self.assertRaises(AssertionError):
                    comprobar_sin_logica(self, region)

    def test_y_dice_DONDE(self):
        with self.assertRaises(AssertionError) as ctx:
            comprobar_sin_logica(self, "x = 1\ncandidatos = int(texto)\n")
        self.assertIn("int(texto)", str(ctx.exception))


class TestElGuardiaNoLADRA(unittest.TestCase):

    def test_calla_con_nombres_que_CONTIENEN_la_palabra(self):
        for region in (
            "huella = run_fingerprint(tuple(starts), params)\n",
            "print(algo)\n",
            "st.write(constraint(x))\n",
            "valores = fila['punto_upper()']\n".replace("upper()", "upperx"),
        ):
            with self.subTest(region=region):
                comprobar_sin_logica(self, region)


if __name__ == "__main__":
    unittest.main()
