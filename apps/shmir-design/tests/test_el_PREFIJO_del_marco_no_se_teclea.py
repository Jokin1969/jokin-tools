"""El prefijo `3utr:` / `tx:` no se escribe a mano fuera de `coords`.

La errata nº 121 se arregló **cinco veces**, en cinco módulos, y seguía entrando por el
sexto. `coords.Position` ya impedía imprimir un entero desnudo; lo que faltaba era
impedir **teclear el prefijo**, que es la otra mitad de la etiqueta y la que se salta el
invariante de rango. Este test comprueba que el guardia existe, que está a cero y —lo que
más importa— que **detectaría el sexto sitio**: un guardia que no se prueba contra el
caso que persigue es una lista de deseos.

Regla 5: escrito con el caso real que lo motivó delante.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design.coords import SEPARATOR, Frame  # noqa: E402
from tools import auditar_marcos  # noqa: E402


class TestElGuardiaDemuestraQueHaMirado(unittest.TestCase):
    """Principio nº 51: «no falló» y «no miró» dan el mismo verde.

    Sin esto, un barrido que no encuentre ningún fichero —una ruta mal puesta, un filtro
    de más— diría «cero literales que fabrican etiquetas» y sería indistinguible de un
    paquete limpio. El caso que lo puso por escrito es el del guardia del calendario del
    hub: verde en 175 ms porque el hijo salía con 0 sin haber descubierto la suite.
    """

    def test_ha_leido_TODOS_los_ficheros_del_paquete_menos_los_exentos(self):
        # La cifra se DERIVA del disco. Escrita a mano se quedaría corta el día que
        # alguien añada un módulo, y entonces el guardia fallaría por su cuenta — la
        # otra forma de dejar de servir (principio nº 48).
        esperados = sum(
            1 for r in RAIZ.rglob("*.py")
            if r.relative_to(RAIZ).parts[0] not in auditar_marcos.FUERA
            and str(r.relative_to(RAIZ)) != auditar_marcos.DUEÑO
        )
        self.assertEqual(auditar_marcos.auditar().ficheros, esperados)
        self.assertGreater(esperados, 50, "el paquete no puede tener cuatro ficheros")

    def test_y_ha_ENCONTRADO_las_menciones_declaradas(self):
        """La exención hace de sonda: lo que no encuentre se lo reclama la tabla.

        Se comparan SÍMBOLOS, no ocurrencias: un símbolo puede nombrar dos posiciones en
        la misma frase —`MULTIPLEX_NOTE` dice que `3utr:449` y `3utr:1018` comparten
        núcleo— y eso es una declaración con dos menciones, no dos declaraciones.
        """
        informe = auditar_marcos.auditar()
        encontrados = {(f["fichero"], f["simbolo"]) for f in informe.prosa}
        declarados = {
            (d["fichero"], d["simbolo"]) for d in auditar_marcos.declaraciones()
        }
        self.assertEqual(encontrados, declarados)
        self.assertGreater(len(encontrados), 0, "no ha encontrado NINGUNA: no ha mirado")


class TestElGuardiaEstaACero(unittest.TestCase):

    def test_ningun_literal_FABRICA_una_etiqueta(self):
        informe = auditar_marcos.auditar()
        self.assertEqual(
            [f"{f['fichero']}:{f['linea']}" for f in informe.fabrican], []
        )

    def test_toda_MENCION_en_prosa_esta_declarada(self):
        informe = auditar_marcos.auditar()
        self.assertEqual(
            [f"{f['fichero']}:{f['linea']}" for f in informe.sin_declarar], []
        )

    def test_y_ninguna_declaracion_se_ha_quedado_sin_literal(self):
        """Una lista con entradas muertas deja de leerse y tapa el siguiente hallazgo."""
        informe = auditar_marcos.auditar()
        self.assertEqual(
            [f"{d['fichero']} {d['simbolo']}" for d in informe.muertas], []
        )

    def test_toda_declaracion_dice_POR_QUE(self):
        for entrada in auditar_marcos.declaraciones():
            with self.subTest(entrada["fichero"], simbolo=entrada["simbolo"]):
                self.assertTrue(entrada["por_que"].strip())
                self.assertGreater(len(entrada["por_que"]), 60)


class TestCazariaElSextoSitio(unittest.TestCase):
    """El control adversario: código que hace lo que la regla prohíbe."""

    def _analizar(self, fuente: str):
        return auditar_marcos.analizar_fuentes({"modulo_falso.py": fuente}, [])

    def test_una_f_string_con_el_prefijo_es_un_FALLO(self):
        informe = self._analizar('def f(x):\n    return f"3utr:{x}"\n')
        self.assertEqual(len(informe.fabrican), 1)
        self.assertEqual(informe.fabrican[0]["simbolo"], "f")

    def test_tambien_por_CONCATENACION_que_no_es_f_string(self):
        """Así entraba en `seed_scan`: `+ ", 3utr:".join(...)`, sin ninguna f-string."""
        informe = self._analizar(
            'def f(xs):\n    return "comparte con 3utr:" + ", 3utr:".join(xs)\n'
        )
        self.assertEqual(len(informe.fabrican), 2)

    def test_y_con_el_OTRO_marco_igual(self):
        """Si sólo mirara `3utr:`, un `tx:` tecleado pasaría — y hay dos espacios."""
        informe = self._analizar('def f(x):\n    return f"tx:{x}"\n')
        self.assertEqual(len(informe.fabrican), 1)

    def test_los_PREFIJOS_salen_de_coords_y_no_de_este_guardia(self):
        """Si mañana entra un tercer espacio, el guardia lo ve sin tocarlo.

        Tecleados aquí, un `Frame` nuevo quedaría fuera del barrido sin dar ningún
        error: el guardia diría cero porque no lo está buscando. Es el «Alu 0 %»
        obtenido sin buscar Alu.
        """
        self.assertEqual(
            set(auditar_marcos._prefijos()),
            {f"{f.value}{SEPARATOR}" for f in Frame},
        )

    def test_una_MENCION_en_prosa_NO_es_una_fabricacion(self):
        informe = self._analizar('AVISO = "3utr:221 era uno de los cuatro inmunes"\n')
        self.assertEqual(informe.fabrican, [])
        self.assertEqual(len(informe.sin_declarar), 1)
        self.assertEqual(informe.sin_declarar[0]["simbolo"], "AVISO")

    def test_y_declarada_deja_de_serlo(self):
        informe = auditar_marcos.analizar_fuentes(
            {"modulo_falso.py": 'AVISO = "3utr:221 era uno de los inmunes"\n'},
            [{"fichero": "modulo_falso.py", "simbolo": "AVISO", "por_que": "el caso"}],
        )
        self.assertEqual(informe.sin_declarar, [])
        self.assertEqual(len(informe.prosa), 1)

    def test_un_DOCSTRING_no_cuenta(self):
        """No llega a ninguna salida, y prohibirlo dejaría la regla sin explicar."""
        informe = self._analizar('"""Las posiciones van como 3utr:449."""\n')
        self.assertEqual(informe.fabrican, [])
        self.assertEqual(informe.sin_declarar, [])

    def test_la_DECLARACION_es_por_simbolo_y_no_por_fichero(self):
        """Una declaración no puede amparar a la constante de al lado.

        Con el fichero como clave, una mención nueva en OTRA constante del mismo módulo
        entraría sin que nadie la mirase: el guardia calibrado sobre un caso.
        """
        informe = auditar_marcos.analizar_fuentes(
            {
                "modulo_falso.py": (
                    'UNO = "3utr:221 era inmune"\n'
                    'OTRO = "y 3utr:1018 no lo era"\n'
                ),
            },
            [{"fichero": "modulo_falso.py", "simbolo": "UNO", "por_que": "el caso"}],
        )
        self.assertEqual(len(informe.prosa), 1)
        self.assertEqual(len(informe.sin_declarar), 1)
        self.assertEqual(informe.sin_declarar[0]["simbolo"], "OTRO")


class TestLosTestsSiPuedenEscribirlo(unittest.TestCase):

    def test_el_barrido_deja_fuera_tests_y_lo_dice(self):
        self.assertIn("tests", auditar_marcos.FUERA)
        self.assertIn("adversario", auditar_marcos.WHY_NOT_THE_TESTS)

    def test_y_ESTE_fichero_escribe_el_literal_a_proposito(self):
        """La prueba de que la exención hace falta: este test no existiría sin ella."""
        fuente = Path(__file__).read_text(encoding="utf-8")
        self.assertIn('f"3utr:{x}"', fuente)


class TestCoordsSigueSiendoElUnicoDueño(unittest.TestCase):

    def test_coords_esta_fuera_del_barrido_por_su_NOMBRE(self):
        self.assertEqual(auditar_marcos.DUEÑO, "shmir_design/coords.py")
        self.assertTrue((RAIZ / auditar_marcos.DUEÑO).exists())

    def test_y_es_el_que_de_verdad_lo_emite(self):
        """Si `coords` dejara de emitirlo, la exención sobraría y habría que quitarla.

        No se lee el fuente buscando la cadena: se PIDE la etiqueta y se mira que salga
        pegada. Un test sobre el texto del módulo pasaría con el emisor comentado.
        """
        from shmir_design.coords import Position

        self.assertEqual(str(Position(449, Frame.UTR3)), f"3utr{SEPARATOR}449")
        self.assertEqual(str(Position(1398, Frame.TX)), f"tx{SEPARATOR}1398")


if __name__ == "__main__":
    unittest.main()
