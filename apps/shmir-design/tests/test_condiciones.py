"""Condiciones que NO PUEDEN SER FALSAS. Regla 5: escrito antes que el detector.

**De dónde sale.** Del principio nº 19, y de tres fallos con la misma forma:
`x or defecto` con la cadena vacía (errata nº 18), `Path.is_file()` sobre un fichero de
0 bytes (errata nº 15) y `if fila["acciones"]` sobre una lista que nunca está vacía
(errata nº 34). En los tres, **un valor legítimo tiene la forma de otra cosa** y la
comprobación mira el CONTENEDOR cuando la pregunta es por el CONTENIDO.

**Por qué este detector y no otro.** El barrido ancho —cualquier verdad sobre una
colección— da 187 posiciones en este paquete y **casi todas son correctas**: en
`if not filas` la vacuidad ES la pregunta. Un auditor así se apaga el primer día. Lo que
sí se puede decidir sin equivocarse es el caso extremo: **una condición cuyo valor no
puede ser falso nunca**. Ésa no es un criterio discutible, es código muerto disfrazado de
decisión — y es exactamente lo que era `fila["acciones"]`, que valía `["ver", …]` o
`["subir"]`: dos cosas distintas, las dos verdaderas.

Así que esto **no es un trinquete**: es un guardia. El número correcto es CERO.
"""

import ast
import unittest
from pathlib import Path

from tools import auditar_condiciones as auditoria

RAIZ = Path(__file__).resolve().parent.parent


class TestNoQuedaNinguna(unittest.TestCase):

    def test_cero_condiciones_que_no_pueden_ser_falsas(self):
        halladas = auditoria.auditar().hallazgos
        self.assertEqual(
            [f"{h['fichero']}:{h['linea']}  {h['fuente']}" for h in halladas],
            [],
            "Una condición que no puede ser falsa no es una decisión: es una rama "
            "muerta con forma de decisión.",
        )


class TestCazaELfalloQueLOoriginó(unittest.TestCase):
    """La prueba que de verdad vale: se le da el fuente **de antes del arreglo**.

    Un detector que sale a cero sobre el código ya arreglado no ha demostrado nada — es
    el `verify()` de la errata nº 29 otra vez, confianza sin información. Aquí se le pone
    delante la línea que estuvo en producción y se exige que la señale.
    """

    #: La línea tal cual estaba en `ui/streamlit_app.py` antes de la errata nº 34, con lo
    #: mínimo alrededor para que sea un módulo analizable.
    ANTES = '''
ACTIONS = {
    "presente": ("ver", "reemplazar", "borrar", "descargar"),
    "ausente": ("subir",),
}

def fila_de(estado):
    return {"acciones": list(ACTIONS[estado])}

def pintar(fila, directorio):
    if fila["acciones"]:
        _fila_presente(fila, directorio)
    else:
        _caption(fila["si_no_llega"])
'''

    def test_la_señala(self):
        halladas = auditoria.analizar_fuentes({"antes.py": self.ANTES})
        self.assertEqual(len(halladas), 1, halladas)
        self.assertIn("acciones", halladas[0]["fuente"])

    def test_y_NO_señala_la_version_arreglada(self):
        """El otro lado: si marcara las dos, no estaría midiendo nada."""
        arreglada = self.ANTES.replace('fila["acciones"]', 'fila["presente"]')
        self.assertEqual(auditoria.analizar_fuentes({"despues.py": arreglada}), [])

    def test_ni_marca_la_vacuidad_cuando_ES_la_pregunta(self):
        """`if not filas` es correcto y es el 99 % de lo que hay. Marcarlo sería el
        auditor con falsos positivos que se acaba apagando."""
        fuente = '''
def leer(ruta):
    filas = [l for l in ruta.read_text().splitlines() if l]
    if not filas:
        raise ValueError("vacío")
    return filas
'''
        self.assertEqual(auditoria.analizar_fuentes({"lector.py": fuente}), [])


class TestLoQueELdetectorNOpuedeHacer(unittest.TestCase):
    """Declarado, porque un análisis que se equivoca hacia el silencio es peor que no
    tenerlo — y éste se equivoca hacia el silencio a propósito."""

    def test_solo_ve_claves_de_DICCIONARIO_construidas_con_literales(self):
        """No ve una variable local que nunca esté vacía, ni un valor que venga de fuera.
        Es el precio de no tener falsos positivos, y va escrito para que nadie lea el
        cero como «no hay ninguna»."""
        self.assertIn("NO ve", auditoria.LO_QUE_NO_VE)
        self.assertGreater(len(auditoria.LO_QUE_NO_VE), 200)

    def test_una_clave_con_UN_solo_valor_vacio_ya_no_cuenta(self):
        """Basta un sitio donde pueda estar vacía para que la condición sea legítima."""
        fuente = '''
def a(): return {"cosas": ["x"]}
def b(): return {"cosas": []}
def c(fila):
    if fila["cosas"]:
        pass
'''
        self.assertEqual(auditoria.analizar_fuentes({"m.py": fuente}), [])


class TestUnSoloMECANISMO(unittest.TestCase):
    """La distinción tabla/registro dejó sin trabajo a la lista de exclusiones.

    Se quedó el mecanismo que explica por qué, no el que enumera excepciones. Este test
    existe para que la lista no vuelva por la puerta de atrás la próxima vez que algo
    ensucie el conjunto intermedio: si hace falta excluir, hará falta un motivo.
    """

    def test_no_hay_lista_de_ficheros_excluidos(self):
        self.assertFalse(hasattr(auditoria, "EXCLUIDOS"))

    def test_una_TABLA_de_modulo_no_aporta_claves_de_registro(self):
        fuente = '''
VOCABULARIO = {"funcion": "función", "razon": "razón"}
def usar(fila):
    if fila["funcion"]:
        pass
'''
        self.assertEqual(auditoria.analizar_fuentes({"v.py": fuente}), [])


class TestElOTROdisfrazDeLaMISMAforma(unittest.TestCase):
    """`zip` sobre un campo con defecto vacío: la vacuidad legítima produce SILENCIO.

    Apareció en el mismo barrido, y no lo caza el detector de arriba porque no es una
    condición: `BreakChoice.folding_ok` tiene `= ()` por defecto y `rows()` hace
    `zip(self.candidates, self.folding_ok)`. **`zip` trunca al más corto sin decir
    nada**, así que una construcción que rellenara `candidates` y olvidara `folding_ok`
    daría un informe VACÍO —ni una fila, ni un error—, que se lee como «no hay
    alternativas» cuando lo que pasa es que no se midió ninguna.

    Hoy los dos sitios que la construyen rellenan los dos campos, así que no hay fallo.
    Lo que faltaba es que la invariante estuviera ESCRITA y se hiciera cumplir: un tercer
    sitio no puede volver a quedarse a medias en silencio.
    """

    def test_construir_con_los_dos_campos_DESCUADRADOS_aborta(self):
        from shmir_design.errors import ShmirDesignError
        from shmir_design.filters import FilterState
        from shmir_design.intron_design import BreakChoice, break_candidates
        from shmir_design.scaffold import SGEP_SCAFFOLD

        candidatos = break_candidates(SGEP_SCAFFOLD)
        self.assertTrue(candidatos, "sin candidatos este test no comprueba nada")
        with self.assertRaises(ShmirDesignError) as caja:
            BreakChoice(state=FilterState.PASS, candidates=candidatos)
        self.assertIn("folding_ok", str(caja.exception))

    def test_y_los_dos_sitios_REALES_siguen_construyendo(self):
        """El otro lado: el guardia no puede romper lo que ya funciona."""
        from shmir_design.folding import VIENNA_AVAILABLE
        from shmir_design.intron_design import choose_break
        from shmir_design.scaffold import SGEP_SCAFFOLD

        # `available=True` sin ViennaRNA no se puede: pide el plegado de verdad.
        modos = (False, True) if VIENNA_AVAILABLE else (False,)
        for disponible in modos:
            with self.subTest(vienna=disponible):
                eleccion = choose_break(
                    SGEP_SCAFFOLD, guide="TAGATAAGCATTATAATTCCTA",
                    available=disponible,
                )
                self.assertEqual(
                    len(eleccion.candidates), len(eleccion.folding_ok)
                )
