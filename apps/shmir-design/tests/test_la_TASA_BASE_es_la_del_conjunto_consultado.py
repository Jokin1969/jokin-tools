"""La tasa base describe lo que el veredicto MIDE, y la ventana no estándar se ve.

Regla 5: escritos antes.

## Los dos defectos, reportados con la corrida delante (2026-09-06)

La corrida salió con `window=2-7` y `level=nucleo`, los dos marcados como ajustes
modificados. Y el resultado era **incoherente con su propia tasa base**: la cabecera
decía que el 31 % colisionaría por azar y salió 1 de 176.

> *«La tasa base se calcula sobre los 1.988 maduros mmu- y el veredicto se emite sólo
> contra los diez del núcleo. La cifra que acompaña al resultado no describe lo que el
> resultado mide, y engaña en la dirección tranquilizadora: hace parecer
> excepcionalmente limpio algo que sólo se comparó contra diez secuencias.»*

**Y engaña hacia el lado cómodo**, que es lo que lo hace grave: una tasa base inflada
convierte un `LIMPIO` trivial en un `LIMPIO` notable. Con `level=nucleo` la tasa
relevante es la de DIEZ seeds sobre el espacio, que es otra cifra y muy pequeña.

## Y la ventana 2-7 tiene que verse en el VEREDICTO

La seed es 2-8 por definición del bolsillo de Ago2. En 2-7 el espacio pasa de 16.384 a
4.096, así que la tasa base sube y **un LIMPIO significa mucho menos**. Estaba marcado
en la cabecera de los parámetros, que se lee una vez; el veredicto se lee siempre y
viaja en la descarga. Es la misma lección que puso la tasa base en la fila.
"""

import unittest

from shmir_design import seed_scan
from shmir_design.mirna import MatureSet


def _maduros() -> MatureSet:
    """Fixture SINTÉTICO: `mature.fa` son 5,6 MB y no se versiona.

    Se declara qué es cada entrada, que es lo que un fixture opaco no permite: dos del
    NÚCLEO (`miR-9-5p` y `miR-124-3p`, que están en `CORE_ABUNDANT`) y tres de fuera.
    Las seeds son de siete letras porque así las indexa `load_mature_fa`.
    """
    return MatureSet(
        seeds={
            "CTTTGGA": ("mmu-miR-9-5p",),
            "AAGGCAC": ("mmu-miR-124-3p",),
            "GGGGGGA": ("mmu-miR-0001-5p",),
            "GGGGGGT": ("mmu-miR-0002-5p",),
            # Dos maduros con la MISMA seed: `matures` y `distinct` no son el mismo
            # número, y la tasa se calcula sobre el segundo.
            "TTTTTTA": ("mmu-miR-0003-5p", "mmu-miR-0004-5p"),
        },
        source="fixture sintético declarado",
        version="0",
        checksum="0" * 32,
    )


class TestLaTasaBaseSigueAlNivel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.maduros = _maduros()

    def _tasa(self, **cambios):
        params = seed_scan.SeedParams(species_prefix="mmu-", **cambios)
        return seed_scan.base_rate(self.maduros, params)

    def test_con_AMBOS_cuenta_todo_el_fichero(self):
        tasa = self._tasa(level="ambos")
        self.assertEqual(tasa.matures, 6)   # TTTTTTA lleva dos
        self.assertEqual(tasa.distinct, 5)
        self.assertEqual(tasa.level, "ambos")

    def test_con_NUCLEO_cuenta_SOLO_los_del_nucleo(self):
        """Es el defecto reportado: se comparaba contra dos y se anunciaba cinco."""
        tasa = self._tasa(level="nucleo")
        self.assertEqual(tasa.matures, 2)
        self.assertEqual(tasa.distinct, 2)
        self.assertEqual(tasa.level, "nucleo")

    def test_con_AMPLIADO_cuenta_el_resto(self):
        tasa = self._tasa(level="ampliado")
        self.assertEqual(tasa.matures, 4)
        self.assertEqual(tasa.distinct, 3)
        self.assertEqual(tasa.distinct, 3)

    def test_la_diferencia_va_EN_LA_DIRECCION_tranquilizadora(self):
        """La cifra inflada hace parecer notable un LIMPIO trivial."""
        self.assertGreater(
            self._tasa(level="ambos").fraction, self._tasa(level="nucleo").fraction
        )

    def test_la_tasa_DICE_contra_que_conjunto_se_comparo(self):
        texto = self._tasa(level="nucleo").describe()
        self.assertIn("núcleo", texto.lower())
        self.assertIn(seed_scan.WHY_THE_RATE_FOLLOWS_THE_LEVEL[:30], texto)

    def test_y_tambien_en_la_CELDA_que_viaja_con_la_fila(self):
        self.assertIn("nucleo", self._tasa(level="nucleo").short)

    def test_con_la_ventana_de_seis_el_espacio_es_4096(self):
        tasa = self._tasa(level="nucleo", window="2-7")
        self.assertEqual(tasa.space, 4096)
        self.assertEqual(tasa.distinct, 2)


class TestLaVentanaNoEstandarVaEnElVeredicto(unittest.TestCase):

    def _resultado(self, window: str, level: str = "LIMPIO"):
        return seed_scan.SeedResult(
            start=1761, strand="guia", query="q", sequence="ACGTACGTACGTACGTACGTAC",
            heptamer="CTTTGG", window=window, collisions=(), level=level,
        )

    def test_con_2_8_el_veredicto_va_LIMPIO_a_secas(self):
        self.assertEqual(self._resultado("2-8").verdict, "LIMPIO")
        self.assertTrue(self._resultado("2-8").window_standard)

    def test_con_2_7_el_veredicto_LO_DICE(self):
        resultado = self._resultado("2-7")
        self.assertFalse(resultado.window_standard)
        self.assertIn("2-7", resultado.verdict)
        self.assertIn("NO ESTÁNDAR", resultado.verdict)

    def test_y_tambien_cuando_hay_colision(self):
        con = seed_scan.SeedResult(
            start=1761, strand="guia", query="q", sequence="ACGTACGTACGTACGTACGTAC",
            heptamer="CTTTGG", window="2-7", level="FAIL",
            collisions=(seed_scan.SeedCollision("mmu-miR-9-5p", True, False),),
        )
        self.assertIn("NO ESTÁNDAR", con.verdict)
        self.assertIn("NO ESTÁNDAR", con.describe())

    def test_el_motivo_esta_escrito_y_dice_LO_QUE_CAMBIA(self):
        self.assertIn("Ago2", seed_scan.WHY_2_8_IS_THE_SEED)
        self.assertIn("SIGNIFICA MUCHO MENOS", seed_scan.WHY_2_8_IS_THE_SEED)

    def test_la_ventana_estandar_se_DERIVA_y_no_se_declara(self):
        """Si se declarara, un día diría 2-8 sobre una corrida de 2-7."""
        self.assertEqual(seed_scan.STANDARD_WINDOW, "2-8")
        self.assertIs(
            seed_scan.SeedParams().window == seed_scan.STANDARD_WINDOW, True
        )


if __name__ == "__main__":
    unittest.main()
