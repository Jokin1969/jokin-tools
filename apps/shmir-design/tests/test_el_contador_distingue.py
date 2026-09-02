"""El contador distingue GANAR UN VEREDICTO de cambiar de motivo. Y el almacen no pisa.

**Lo que pasó.** Se subio una corrida que no cierra y la confirmacion dijo, en VERDE,
«10 veredictos actualizados». Los diez habian pasado de `NOT_RUN` a `NO_CIERRA`: de **no
comprobado a no comprobado por otro motivo**. El contador contaba cambios de VALOR, y el
verde hacia creer que se habia cerrado un frente.

**Y un segundo fallo, latente, del mismo cableado**: con un almacen presente pero SIN
corrida para ese candidato, el estado del almacen (`NOT_RUN`) PISABA al del filtro de la
ventana. Hoy no se nota porque sin base cargada ese filtro tambien dice `NOT_RUN` — pero
en cuanto alguien deposite `refseq_rna.fa`, un veredicto local de verdad quedaria
sustituido por un `NOT_RUN` del almacen. El almacen manda **donde tiene algo que decir**,
no por estar.
"""

import unittest

from shmir_design import presentation
from tests.test_la_tabla_lee_las_corridas import _almacen_con, _piezas


class TestElCONTADORdistingue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling, cls.seleccion = _piezas()
        cls.primero = cls.seleccion.selection.chosen[0].start

    def _resumen(self, after, before=None):
        return presentation.verdicts_changed(
            self.tiling, self.seleccion, species="raton", before=before, after=after,
        )

    def test_una_corrida_que_CIERRA_cuenta_como_veredicto_ganado(self):
        resumen = self._resumen({"blast": _almacen_con(self.primero)})
        self.assertEqual(resumen["con_veredicto"], 1)
        self.assertEqual(resumen["sin_veredicto"], 0)

    def test_una_que_NO_cierra_NO_cuenta_como_veredicto_ganado(self):
        """De `NOT_RUN` a `NO_CIERRA` es cambiar de motivo, no comprobar nada."""
        resumen = self._resumen({"blast": _almacen_con(self.primero, remota=True)})
        self.assertEqual(resumen["con_veredicto"], 0)
        self.assertEqual(resumen["sin_veredicto"], 1)

    def test_y_el_TEXTO_no_da_por_cerrado_lo_que_no_lo_esta(self):
        texto = self._resumen(
            {"blast": _almacen_con(self.primero, remota=True)}
        )["texto"].lower()
        self.assertIn("sin veredicto", texto)
        self.assertNotIn("actualizado(s) en la tabla", texto)

    def test_el_VERDE_se_reserva_a_los_veredictos_ganados(self):
        # La pagina pinta en verde si `con_veredicto`, y no si hubo cambios a secas.
        self.assertFalse(
            self._resumen({"blast": _almacen_con(self.primero, remota=True)})["verde"]
        )
        self.assertTrue(
            self._resumen({"blast": _almacen_con(self.primero)})["verde"]
        )


class TestElALMACENnoPISAloQueNOsabe(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling, cls.seleccion = _piezas()
        cls.primero = cls.seleccion.selection.chosen[0].start
        cls.otro = cls.seleccion.selection.chosen[1].start

    def test_sin_corrida_para_ESE_candidato_manda_el_filtro_de_la_ventana(self):
        from shmir_design.presentation import _store_state

        # `None` = «el almacen no dice nada de esto», que NO es `NOT_RUN`: quien decide
        # entonces es el filtro de la ventana, como siempre.
        estado = _store_state(
            {"blast": _almacen_con(self.primero)}, "especificidad", "raton", self.otro
        )
        self.assertIsNone(estado)

    def test_con_corrida_SI_manda_el_almacen(self):
        from shmir_design.presentation import _store_state

        estado = _store_state(
            {"blast": _almacen_con(self.primero)}, "especificidad", "raton", self.primero
        )
        self.assertEqual(estado, "PASS")


if __name__ == "__main__":
    unittest.main()
