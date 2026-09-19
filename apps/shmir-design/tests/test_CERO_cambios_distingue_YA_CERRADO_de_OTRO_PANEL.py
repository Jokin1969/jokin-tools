"""Cero cambios al guardar tiene DOS causas opuestas, y el texto las distingue.

**Reportado (2026-09-16).** Tras desbloquear el guardado de la corrida `mmu-` del panel
humano —dos paneles distintos ya no colisionan en `result_md5`—, volver a guardar una
corrida cuyo frente YA estaba cerrado sacaba «0 veredictos actualizados… puede que sus
consultas no sean las de este panel». El frente estaba cerrado y las consultas eran las de
este panel: la corrida era redundante, no ajena. El texto describía sólo la segunda causa
y se leía como una alarma sobre la primera.

`verdicts_changed` cuenta CAMBIOS en la tabla. Cero cambios ocurre por dos razones que se
excluyen:

  · **el frente ya estaba cerrado** por una corrida equivalente —tiene veredicto
    decisivo—, así que no quedaba nada que actualizar: NO es un fallo;
  · **la corrida no tocó este panel** —sus consultas no son las de aquí—, así que ningún
    candidato tiene veredicto de ella.

Se distinguen mirando el frente GUARDADO en la tabla ya calculada: si tiene algún
veredicto decisivo, estaba cerrado; si no, la corrida no llegó —porque si sus consultas
fueran las de aquí habrían pasado a PASS/FAIL y esto no sería cero—.

Regla 5: escrito antes. Python 3.11+, solo biblioteca estandar (regla 6).
"""

import unittest

from shmir_design import presentation
from tests.test_la_tabla_lee_las_corridas import _almacen_con, _piezas


class TestCeroCambiosDistingueLaCausa(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling, cls.seleccion = _piezas()
        cls.primero = cls.seleccion.selection.chosen[0].start
        #: El mismo almacen ANTES y DESPUES: guardar no cambia la tabla (cero cambios),
        #: y `especificidad` ya tiene veredicto de la corrida de `primero`.
        cls.cerrado = {"blast": _almacen_con(cls.primero)}

    def _texto(self, *, front, before, after):
        return presentation.verdicts_changed(
            self.tiling, self.seleccion, species="raton",
            before=before, after=after, front=front,
        )["texto"].lower()

    def test_frente_YA_CERRADO_no_se_lee_como_consultas_de_otro_panel(self):
        texto = self._texto(
            front="especificidad", before=self.cerrado, after=self.cerrado
        )
        self.assertIn("ya estaba cerrado", texto)
        self.assertNotIn("no sean las de este panel", texto)

    def test_sin_veredicto_en_el_frente_SI_avisa_de_otro_panel(self):
        # Nada cerrado (ningun almacen): cero cambios porque la corrida no llegó.
        texto = self._texto(front="especificidad", before={}, after={})
        self.assertIn("no sean las de este panel", texto)
        self.assertNotIn("ya estaba cerrado", texto)

    def test_mira_EL_FRENTE_GUARDADO_y_no_otro(self):
        """Control adversario: con `especificidad` cerrado pero guardando OTRO frente,
        el texto NO puede dar por cerrado lo que ese otro frente no ha cerrado."""
        texto = self._texto(
            front="seed_colision", before=self.cerrado, after=self.cerrado
        )
        self.assertIn("no sean las de este panel", texto)
        self.assertNotIn("ya estaba cerrado", texto)

    def test_sin_front_declarado_se_mantiene_el_texto_de_siempre(self):
        # Retrocompatibilidad: un llamador que no pasa `front` conserva el mensaje
        # clasico, sin fabricar un «ya cerrado» que no puede comprobar.
        texto = self._texto(front=None, before=self.cerrado, after=self.cerrado)
        self.assertIn("no sean las de este panel", texto)
        self.assertNotIn("ya estaba cerrado", texto)


if __name__ == "__main__":
    unittest.main()
