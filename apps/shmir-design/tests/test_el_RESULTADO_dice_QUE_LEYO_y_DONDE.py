"""Un resultado rechazado tiene que decir qué leyó, en qué línea DEL FICHERO, y por qué.

**EL CASO (2026-09-06).** Un TSV de SpliceAI de 22 construcciones, todas correctas, se
rechazó con:

    RECHAZADO — fila 2: la posición -1 se sale de la construcción
    mvm_actual__3utr959 (5496 nt); se aborta.

Y su autor, razonablemente, concluyó que el parser estaba leyendo **la cabecera de
columnas como dato**: en su fichero la línea 2 ES la cabecera, porque la 1 es
`# convencion: spliceai`.

**No era eso.** Medido: la cabecera se salta bien. Lo que pasa son dos cosas distintas y
ninguna se veía en el mensaje:

1. **`fila 2` no era la línea 2 del fichero.** El número contaba filas YA FILTRADAS —sin
   comentarios—, así que con una línea `#` delante los dos números se separan. Es la
   errata nº 121 en otro espacio: un número impreso sin decir de qué espacio es. La
   «fila 2» era la línea **3**.
2. **El −1 sale de la CONVERSIÓN, no del fichero.** La fila declara `posicion=1` y
   `tipo=aceptor`; en la convención de SpliceAI el aceptor apunta dos bases más allá, así
   que traerla a la nuestra es `1 − 2 = −1`. El fichero no traía ningún −1.

**Y la tercera, que es la que bloqueaba de verdad**: una puntuación de SpliceAI en la
posición 1 es legítima —puntúa todas las posiciones, y ésa valía 1,57e-07, ruido— pero al
convertirla cae fuera de la construcción. Abortar el fichero entero por una fila de ruido
del borde no es defender nada.

Con las palabras de quien lo sufrió: *«el mensaje describe el síntoma como si fuera del
contenido; que diga qué texto encontró donde esperaba un número — con eso se ve en un
segundo»*.

Regla 5: escritos antes del arreglo, con el fichero real delante.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import spliceai  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402

CABECERA = "\t".join(spliceai.RESULT_COLUMNS)


class Construccion:
    """Lo mínimo que `parse_result` mira de una construcción."""

    def __init__(self, nombre="mvm_actual__3utr959", md5="72b7e346", nt=5496):
        self.name, self.md5, self.sequence = nombre, md5, "A" * nt


def _texto(*filas, convencion=True):
    cabeza = ["# convencion: spliceai"] if convencion else []
    return "\n".join([*cabeza, CABECERA, *filas]) + "\n"


class TestLaLineaQueDICE_ES_LA_DEL_FICHERO(unittest.TestCase):
    """Con una línea `#` delante, la fila filtrada y la línea del fichero se separan."""

    def test_el_numero_apunta_a_la_linea_del_FICHERO(self):
        texto = _texto("mvm_actual__3utr959\t72b7e346\tno_es_un_numero\tdonante\t0.5")
        with self.assertRaises(ShmirDesignError) as caso:
            spliceai.parse_result(texto, constructions=[Construccion()])
        # La fila mala es la línea 3 del fichero: 1 el comentario, 2 la cabecera.
        self.assertIn("línea 3", str(caso.exception))

    def test_y_sin_comentario_delante_tambien_cuadra(self):
        texto = _texto(
            "mvm_actual__3utr959\t72b7e346\tno_es_un_numero\tdonante\t0.5",
            convencion=False,
        )
        with self.assertRaises(ShmirDesignError) as caso:
            spliceai.parse_result(texto, constructions=[Construccion()])
        self.assertIn("línea 2", str(caso.exception))

    def test_con_DOS_comentarios_delante_sigue_cuadrando(self):
        texto = "# convencion: spliceai\n# otra nota\n" + CABECERA + "\n" + (
            "mvm_actual__3utr959\t72b7e346\tx\tdonante\t0.5\n"
        )
        with self.assertRaises(ShmirDesignError) as caso:
            spliceai.parse_result(texto, constructions=[Construccion()])
        self.assertIn("línea 4", str(caso.exception))


class TestElMensajeDICE_QUE_TEXTO_ENCONTRO(unittest.TestCase):

    def test_un_campo_no_numerico_se_NOMBRA(self):
        texto = _texto("mvm_actual__3utr959\t72b7e346\tposicion\tdonante\t0.5")
        with self.assertRaises(ShmirDesignError) as caso:
            spliceai.parse_result(texto, constructions=[Construccion()])
        mensaje = str(caso.exception)
        self.assertIn("'posicion'", mensaje)
        self.assertIn("posición", mensaje)

    def test_y_dice_QUE_COLUMNA_era(self):
        texto = _texto("mvm_actual__3utr959\t72b7e346\t100\tdonante\tno_numero")
        with self.assertRaises(ShmirDesignError) as caso:
            spliceai.parse_result(texto, constructions=[Construccion()])
        mensaje = str(caso.exception)
        self.assertIn("'no_numero'", mensaje)
        self.assertIn("puntuación", mensaje)


class TestElBordeDeLaCONVERSION_no_tumba_el_fichero(unittest.TestCase):
    """SpliceAI puntúa TODAS las posiciones. Las del borde se salen al convertirlas."""

    def test_un_aceptor_en_la_posicion_1_NO_rechaza_el_fichero(self):
        texto = _texto(
            "mvm_actual__3utr959\t72b7e346\t1\taceptor\t1.57e-07",
            "mvm_actual__3utr959\t72b7e346\t3300\tdonante\t0.71",
        )
        sitios = spliceai.parse_result(texto, constructions=[Construccion()])
        self.assertEqual(len(sitios), 1)
        self.assertEqual(sitios[0].position, 3301)

    def test_pero_lo_saltado_se_CUENTA_y_se_dice(self):
        """Saltarse filas en silencio sería peor que abortar."""
        texto = _texto(
            "mvm_actual__3utr959\t72b7e346\t1\taceptor\t1.57e-07",
            "mvm_actual__3utr959\t72b7e346\t3300\tdonante\t0.71",
        )
        aviso = spliceai.edge_note(texto, constructions=[Construccion()])
        self.assertIsNotNone(aviso)
        self.assertIn("1", aviso)
        self.assertIn("línea 3", aviso)

    def test_y_sin_ninguna_saltada_NO_hay_aviso(self):
        texto = _texto("mvm_actual__3utr959\t72b7e346\t3300\tdonante\t0.71")
        self.assertIsNone(
            spliceai.edge_note(texto, constructions=[Construccion()])
        )

    def test_una_posicion_fuera_de_rango_DE_VERDAD_sigue_abortando(self):
        """El guardia existe para cazar un fichero de OTRA corrida. Eso no se relaja."""
        texto = _texto("mvm_actual__3utr959\t72b7e346\t99999\tdonante\t0.71")
        with self.assertRaises(ShmirDesignError) as caso:
            spliceai.parse_result(texto, constructions=[Construccion()])
        self.assertIn("99999", str(caso.exception))

    def test_y_una_negativa_DECLARADA_tambien(self):
        texto = _texto("mvm_actual__3utr959\t72b7e346\t-5\tdonante\t0.71")
        with self.assertRaises(ShmirDesignError) as caso:
            spliceai.parse_result(texto, constructions=[Construccion()])
        self.assertIn("-5", str(caso.exception))

    def test_el_borde_es_COMO_MUCHO_el_desplazamiento_de_la_convencion(self):
        """Tolerar más sería tolerar un fichero equivocado, que es lo que se defiende."""
        self.assertEqual(
            spliceai.EDGE_TOLERANCE, max(abs(v) for v in spliceai.TO_SPLICEAI.values())
        )

    def test_y_en_NUESTRA_convencion_no_se_tolera_nada(self):
        """Sin conversión no hay efecto de borde: una fuera de rango es un error."""
        texto = "\n".join([CABECERA, "mvm_actual__3utr959\t72b7e346\t0\tdonante\t0.7"])
        with self.assertRaises(ShmirDesignError) as caso:
            spliceai.parse_result(texto + "\n", constructions=[Construccion()])
        self.assertIn("0", str(caso.exception))


class TestElMensajeDEL_RANGO_explica_la_CONVERSION(unittest.TestCase):

    def test_dice_la_posicion_DECLARADA_y_la_convertida(self):
        texto = _texto("mvm_actual__3utr959\t72b7e346\t99999\taceptor\t0.71")
        with self.assertRaises(ShmirDesignError) as caso:
            spliceai.parse_result(texto, constructions=[Construccion()])
        mensaje = str(caso.exception)
        self.assertIn("99999", mensaje)      # la que trae el fichero
        self.assertIn("99997", mensaje)      # la que sale de convertirla
        self.assertIn("spliceai", mensaje)   # de dónde sale la resta


if __name__ == "__main__":
    unittest.main()
