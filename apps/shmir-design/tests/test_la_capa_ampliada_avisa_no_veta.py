"""El frente de colision de seed CIERRA a nivel nucleo, sin fichero opcional.

**Contradiccion señalada por el responsable del proyecto (2026-09-02)**, y tenia razon:

> `seed_colision` no cierra sin `mirgenedb_cerebro.txt`, y ese fichero esta marcado
> OPCIONAL en el panel — «No bloquea nada: el filtro corre sin el y con el afina». Las
> dos cosas no pueden ser ciertas.

LA QUE CEDE ES EL FILTRO, y no por comodidad: lo dice la decision escrita de 2026-08-26.
Son DOS CAPAS y hacen cosas distintas —

  · NUCLEO: diez miARN abundantes de cerebro, `FAIL` duro, EN CODIGO, corre SIEMPRE y no
    necesita fichero;
  · AMPLIADA: el resto por encima de un umbral publicado, y su producto es un **AVISO**.

Un aviso que falta no puede convertir un `PASS` en `INCOMPLETE`, porque nunca habria
podido convertirlo en `FAIL`. Salir `NOT_RUN` bloqueaba el frente por una capa que no
emite veredicto — y ademas dejaba el fichero marcado OPCIONAL mintiendo.

LO QUE NO SE RELAJA: el `PASS` no se presenta como «limpio contra todo». Dice que el
nucleo corrio y esta limpio y que la capa de aviso NO se ejecuto, que es exactamente lo
que se sabe. Un PASS mudo aqui seria el «Alu 0 %».
"""

import unittest
from pathlib import Path

from shmir_design.filters import FilterState
from shmir_design.mirna import filter_seed_collision, load_mature_fa

MATURE = Path(__file__).resolve().parent.parent / "data" / "reference" / "mature.fa"
HAY = MATURE.is_file()

#: Una guia del panel murino REAL, la de `3utr:959`. Su seed no colisiona con el nucleo.
GUIA = "TAATGCGAAGGAACAAGCAGGA"


@unittest.skipUnless(HAY, "falta data/reference/mature.fa")
class TestElFrenteCIERRA_sinElFicheroOPCIONAL(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mature = load_mature_fa(MATURE, version="banco")

    def _sin_ampliada(self, guia=GUIA):
        return filter_seed_collision(guia, self.mature, None, species="mouse")

    def test_sin_lista_ampliada_el_veredicto_es_PASS(self):
        self.assertIs(self._sin_ampliada().state, FilterState.PASS)

    def test_y_el_motivo_dice_que_el_PASS_es_del_NUCLEO(self):
        motivo = self._sin_ampliada().reason
        self.assertIn("NÚCLEO", motivo)
        self.assertIn("AMPLIADA", motivo)

    def test_y_dice_expresamente_que_NO_es_limpio_contra_todo(self):
        # La frase que impide que una ausencia se lea como una comprobacion.
        self.assertIn("no dice «limpio contra todo»", self._sin_ampliada().reason.lower()
                      .replace("NO DICE", "no dice"))

    def test_y_lo_marca_como_CAMPO_para_no_tener_que_parsear_el_motivo(self):
        self.assertTrue(self._sin_ampliada().ampliada_sin_correr)


@unittest.skipUnless(HAY, "falta data/reference/mature.fa")
class TestLoQueELNUCLEO_sigueVETANDO(unittest.TestCase):
    """El control adversario: si todo saliera PASS, el filtro no mediria nada."""

    @classmethod
    def setUpClass(cls):
        cls.mature = load_mature_fa(MATURE, version="banco")

    def test_una_seed_del_NUCLEO_sigue_dando_FAIL_sin_fichero(self):
        # La seed de miR-124-3p, que esta en `CORE_ABUNDANT`. Se saca de `mature.fa`,
        # nunca escrita aqui (regla 1).
        semilla = next(
            s for nombre, s in _maduros(self.mature) if nombre == "mmu-miR-124-3p"
        )
        guia = "T" + semilla + "G" * (22 - 1 - len(semilla))
        resultado = filter_seed_collision(guia, self.mature, None, species="mouse")
        self.assertIs(resultado.state, FilterState.FAIL)


def _maduros(mature):
    """Los (nombre, seed) del fichero, PEDIDOS al objeto que los carga."""
    for nombre, seeds in getattr(mature, "seeds", {}).items():
        for seed in (seeds if isinstance(seeds, (list, tuple, set)) else [seeds]):
            yield seed, nombre
    # `seeds` va {seed: nombres}; se invierte arriba para poder buscar por nombre.


if __name__ == "__main__":
    unittest.main()
