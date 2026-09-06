"""`empalme_sitios` se cierra con sus corridas. Una exclusión no puede gobernar dos ejes.

**EL CASO (2026-09-07).** Tras subir el resultado de SpliceAI —y guardarlo—,
`empalme_sitios` seguía en `NOT_RUN` en la tabla de candidatos. Por muchas corridas que se
guardaran. Su autor perdió **tres corridas de SpliceAI** llegando hasta aquí.

Y el mecanismo no era «se guarda y nadie lo lee» por descuido. Era peor y más difícil de
ver: `FRONTS_WITHOUT_COLUMN` se declaró para UNA cosa —«no cabe en una columna por
candidato, porque su unidad es el par»— y ese motivo está bien escrito y es correcto. Pero
el único camino que **cierra** un frente sale de `STORE_FOR_FRONT`, y quien no está en ella
no está en ninguna. Así que **no tener columna pasó a significar no poder cerrarse**, y eso
no lo decidió nadie.

Con las palabras del responsable del proyecto, que es quien lo nombró (principio nº 53):

    «Una lista de excepciones declarada para un propósito se convierte en la condición de
    todo lo que la consulta, y los usos posteriores heredan una decisión que no se tomó
    para ellos. Y no da error porque cada uso es coherente con la lista.»

Las dos decisiones van ahora separadas y **cada una declara lo suyo**: si tiene columna lo
dice `FRONTS_WITHOUT_COLUMN`; si puede cerrarse y con qué almacén lo dice
`PAIR_UNIT_FRONTS`.

Regla 5: escrito antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation  # noqa: E402
from shmir_design.coords import Frame  # noqa: E402
from shmir_design.filters import FilterResult, FilterState  # noqa: E402


class ParFalso:
    def __init__(self, inicio, intron):
        self.candidate_start, self.intron = inicio, intron
        self.candidate_frame = Frame.UTR3


class CorridaFalsa:
    def __init__(self, pares):
        self.scan = type("S", (), {"pairs": tuple(pares)})()
        self.candidate_frame = Frame.UTR3


class AlmacenFalso:
    """Lo mínimo que `_estado_por_par` le pide a un almacén de pares."""

    def __init__(self, pares, estado=FilterState.PASS):
        self.latest = CorridaFalsa(pares)
        self._estado = estado

    def verdict_for(self, inicio, intron, *, frame):
        return FilterResult(name="empalme_sitios", state=self._estado, reason="x")


class TestLasDosDECISIONES_van_separadas(unittest.TestCase):

    def test_hay_una_lista_para_la_COLUMNA_y_otra_para_el_CIERRE(self):
        self.assertIn("empalme_sitios", presentation.FRONTS_WITHOUT_COLUMN)
        self.assertIn("empalme_sitios", presentation.PAIR_UNIT_FRONTS)

    def test_y_cada_una_dice_lo_SUYO(self):
        columna = presentation.FRONTS_WITHOUT_COLUMN["empalme_sitios"]
        cierre = presentation.PAIR_UNIT_FRONTS["empalme_sitios"]
        self.assertIn("columna", columna)
        self.assertIn("almacen", cierre)
        self.assertGreater(len(cierre["por_que"]), 60)

    def test_el_almacen_declarado_EXISTE_entre_los_del_proyecto(self):
        """Si el nombre no fuera uno de los almacenes, no cerraría nunca y en silencio."""
        for frente, declarado in presentation.PAIR_UNIT_FRONTS.items():
            with self.subTest(frente):
                self.assertIn(declarado["almacen"], presentation.STORES)

    def test_un_frente_por_PAR_no_puede_estar_tambien_en_STORE_FOR_FRONT(self):
        """Dos caminos para cerrar el mismo frente son dos criterios que un día discrepan."""
        self.assertEqual(
            set(presentation.PAIR_UNIT_FRONTS) & set(presentation.STORE_FOR_FRONT), set()
        )


class TestConUnaCorridaGUARDADA_el_frente_contesta(unittest.TestCase):

    def test_los_candidatos_de_la_corrida_quedan_contestados(self):
        almacen = AlmacenFalso([ParFalso(959, "mvm_actual"), ParFalso(1149, "mvm_actual")])
        estados = presentation.store_states_by_front(
            {"splice": almacen}, species="raton", starts=[959, 1149, 2020],
        )
        self.assertIn("empalme_sitios", estados)
        self.assertEqual(estados["empalme_sitios"][959], FilterState.PASS.value)
        self.assertEqual(estados["empalme_sitios"][1149], FilterState.PASS.value)

    def test_y_el_que_NO_estaba_en_la_corrida_sigue_sin_contestar(self):
        """Cerrar el frente para quien no se consultó sería lo contrario del arreglo."""
        almacen = AlmacenFalso([ParFalso(959, "mvm_actual")])
        estados = presentation.store_states_by_front(
            {"splice": almacen}, species="raton", starts=[959, 2020],
        )
        self.assertNotIn(2020, estados["empalme_sitios"])

    def test_SIN_corrida_no_dice_nada_y_manda_el_NOT_RUN_de_siempre(self):
        estados = presentation.store_states_by_front(
            {"splice": None}, species="raton", starts=[959],
        )
        self.assertNotIn("empalme_sitios", estados)

    def test_y_sin_almacen_ninguno_tampoco_revienta(self):
        self.assertNotIn(
            "empalme_sitios",
            presentation.store_states_by_front({}, species="raton", starts=[959]),
        )

    def test_un_par_en_FAIL_manda_sobre_uno_en_PASS(self):
        """`_peor_de`: la laguna y el FAIL mandan. Nunca al revés."""
        almacen = AlmacenFalso(
            [ParFalso(959, "mvm_actual"), ParFalso(959, "mvm_sin_criptico")],
            estado=FilterState.NOT_RUN,
        )
        estados = presentation.store_states_by_front(
            {"splice": almacen}, species="raton", starts=[959],
        )
        self.assertEqual(estados["empalme_sitios"][959], FilterState.NOT_RUN.value)


class TestElControlADVERSARIO(unittest.TestCase):
    """Antes del arreglo esto daba `{}` para `empalme_sitios` con cualquier corrida."""

    def test_el_frente_LLEGA_a_store_states_by_front(self):
        almacen = AlmacenFalso([ParFalso(959, "mvm_actual")])
        estados = presentation.store_states_by_front(
            {"splice": almacen}, species="raton", starts=[959],
        )
        self.assertTrue(
            estados.get("empalme_sitios"),
            "el frente por par no llega a los estados: volvería a quedarse en NOT_RUN "
            "por muchas corridas que se guarden",
        )


if __name__ == "__main__":
    unittest.main()
