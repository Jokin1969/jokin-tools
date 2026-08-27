"""Código con tests en verde y sin ningún llamador: la tercera vez.

Regla 5: escritos antes.

**El modo de fallo que esto cubre.** Ha pasado tres veces en este proyecto:

  1. `masking.triple_motive_rows` — el detalle por ventana del triple motivo, calculado
     y sin emitir en ninguna salida;
  2. `intron_folding` — la accesibilidad estructural del intrón, medida y sin pintar;
  3. `store.save_*` — la capa de persistencia ENTERA, construida y testada, y ninguna
     de sus funciones llamada desde ningún sitio. Los cuatro modales calculaban y al
     cerrar la pestaña no quedaba nada.

No es casualidad: es un modo de fallo del proyecto. Y **ni los tests ni el golden lo
cazan**, porque son ciegos a él por construcción: los tests comprueban que la función
hace lo que dice, y el golden lee lo que se emite — lo que nunca llega a emitirse no
aparece en ninguno de los dos. Son complementarios y entre los dos queda este hueco.

Lo que hace el análisis: listar toda función pública sin llamador fuera de su propio
módulo y de sus tests. **No falla automáticamente** — hay casos legítimos (una API que
se usa desde la consola, una constante de documentación). Lo que hace es OBLIGAR A
DECIDIR: o se cablea, o se justifica por escrito en `data/alcanzabilidad.toml`, o se
borra.

Y la lista de excepciones tiene su propia trampa, que es la razón de que esa parte SÍ
falle: una excepción que ya no hace falta —porque el símbolo se cableó, o se borró—
deja de ser una justificación y pasa a ser ruido que tapa el siguiente hallazgo.
"""

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FIXTURE = RAIZ / "tests" / "datos_alcance"


class TestElAnalisisEncuentraLoQueNadieLLAMA(unittest.TestCase):

    def test_una_funcion_publica_sin_llamador_SALE_en_el_informe(self):
        from tools.check_alcance import analizar

        informe = analizar(RAIZ, fuentes=(FIXTURE,), excepciones=FIXTURE / "alcanzabilidad.toml")
        nombres = {h.name for h in informe.unreachable}
        self.assertIn("nadie_me_llama", nombres)

    def test_y_una_que_SI_se_llama_desde_otro_modulo_NO_sale(self):
        from tools.check_alcance import analizar

        informe = analizar(RAIZ, fuentes=(FIXTURE,), excepciones=FIXTURE / "alcanzabilidad.toml")
        nombres = {h.name for h in informe.unreachable}
        self.assertNotIn("si_me_llaman", nombres)

    def test_llamarse_a_si_misma_dentro_de_su_modulo_NO_cuenta(self):
        """Un módulo que solo se usa a sí mismo sigue estando muerto por fuera."""
        from tools.check_alcance import analizar

        informe = analizar(RAIZ, fuentes=(FIXTURE,), excepciones=FIXTURE / "alcanzabilidad.toml")
        nombres = {h.name for h in informe.unreachable}
        self.assertIn("solo_me_llamo_yo", nombres)

    def test_los_privados_NO_entran(self):
        from tools.check_alcance import analizar

        informe = analizar(RAIZ, fuentes=(FIXTURE,), excepciones=FIXTURE / "alcanzabilidad.toml")
        nombres = {h.name for h in informe.unreachable}
        self.assertNotIn("_privada", nombres)

    def test_un_TEST_no_cuenta_como_llamador(self):
        """Es todo el punto: `store.save_*` tenía tests y ningún caller."""
        from tools.check_alcance import analizar

        informe = analizar(RAIZ, fuentes=(FIXTURE,), excepciones=FIXTURE / "alcanzabilidad.toml")
        nombres = {h.name for h in informe.unreachable}
        self.assertIn("solo_me_llama_un_test", nombres)


class TestLasExcepcionesSE_DECLARAN_Y_SE_JUSTIFICAN(unittest.TestCase):

    def test_hay_un_fichero_de_excepciones_y_es_TEXTO(self):
        # Misma disciplina que el manifiesto: se lee con `cat`, se diffea, y añadir una
        # excepción se ve en la revisión.
        self.assertTrue((RAIZ / "data" / "alcanzabilidad.toml").is_file())

    def test_toda_excepcion_lleva_MOTIVO_escrito(self):
        from tools.check_alcance import cargar_excepciones

        declaradas = cargar_excepciones(RAIZ)
        self.assertTrue(declaradas or True)
        for nombre, motivo in declaradas.items():
            with self.subTest(nombre):
                self.assertTrue(motivo.strip(), nombre)
                self.assertGreater(len(motivo.strip()), 20, nombre)

    def test_una_excepcion_declarada_NO_sale_en_el_informe(self):
        from tools.check_alcance import analizar

        informe = analizar(RAIZ, fuentes=(FIXTURE,), excepciones=FIXTURE / "alcanzabilidad.toml")
        nombres = {h.name for h in informe.unreachable}
        self.assertNotIn("estoy_justificada", nombres)

    def test_una_excepcion_que_YA_NO_HACE_FALTA_se_denuncia(self):
        """Es la trampa de toda lista de excepciones, y por eso esta parte SI falla.

        Una excepción que sobra deja de justificar nada y pasa a ser ruido: la próxima
        vez que alguien lea el informe, lo que vea será una lista con entradas muertas y
        dejará de leerla. Es la misma razón por la que un frente CERRADO sigue saliendo
        en el informe en vez de desaparecer.
        """
        from tools.check_alcance import analizar

        informe = analizar(RAIZ, fuentes=(FIXTURE,), excepciones=FIXTURE / "alcanzabilidad.toml")
        self.assertIn("excepcion_que_sobra", informe.stale)

    def test_el_informe_de_VERDAD_no_tiene_excepciones_muertas(self):
        """Sobre el proyecto entero, no sobre el fixture."""
        from tools.check_alcance import analizar

        informe = analizar(RAIZ)
        self.assertEqual(informe.stale, (), informe.stale)


class TestElInformeSE_LEE(unittest.TestCase):

    def test_cada_hallazgo_dice_DONDE_esta(self):
        from tools.check_alcance import analizar

        informe = analizar(RAIZ, fuentes=(FIXTURE,), excepciones=FIXTURE / "alcanzabilidad.toml")
        for hallazgo in informe.unreachable:
            with self.subTest(hallazgo.name):
                self.assertTrue(hallazgo.module)
                self.assertGreater(hallazgo.line, 0)

    def test_el_texto_dice_QUE_HACER_con_cada_uno(self):
        from tools.check_alcance import analizar

        texto = analizar(RAIZ, fuentes=(FIXTURE,), excepciones=FIXTURE / "alcanzabilidad.toml").render()
        self.assertIn("cablea", texto.lower())
        self.assertIn("justifica", texto.lower())
        self.assertIn("borra", texto.lower())

    def test_y_NO_es_un_fallo_automatico(self):
        # Lo dice el propio informe, para que nadie lo lea como una violación.
        from tools.check_alcance import WHY_NOT_A_FAILURE

        self.assertIn("no es un fallo", WHY_NOT_A_FAILURE.lower())


if __name__ == "__main__":
    unittest.main()
