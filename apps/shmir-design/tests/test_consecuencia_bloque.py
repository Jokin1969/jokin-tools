"""El bloque conservado: la CONSECUENCIA, no solo el dato.

Regla 5: escritos antes.

El unico bloque conservado de >= 22 nt entre los dos 3'UTR mide 26 nt
(`TTTTCTATATTTGTAACTTTGCATGT`, raton 3utr:1138-1163, humano 3utr:1507-1532). De las
cinco ventanas de 22 nt que caben DENTRO, ninguna supera los filtros de secuencia — y
con los mismos motivos en las dos especies, porque la diana es la misma: GC en las
cinco, asimetria en cuatro, homopolimero en una.

Consecuencia, y va escrita con esas palabras: **no existe un shmiR unico valido para
raton, Tg650 y clinica por la via del 3'UTR**. Eso cambia la arquitectura del programa,
no dos plazas del panel.

OJO con que ventanas se miran: las que SOLAPAN el bloque se salen de el, y fuera del
bloque las dos especies difieren. Contarlas daba un «si hay ventanas elegibles» falso.
"""

import unittest

from shmir_design.conservation import (
    Utr3,
    build_conservation_report,
    single_shmir_verdict,
)
from shmir_design.filters import Verdict
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON, HUMANO = REFERENCES["NM_011170.3"], REFERENCES["NM_000311.5"]


@unittest.skipUnless(
    fixture_available(RATON) and fixture_available(HUMANO),
    "NOT_RUN: faltan los fixtures de los dos 3'UTR",
)
class TestElVeredictoSaleDelDatoReal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.informe = build_conservation_report(
            Utr3("raton", load_3utr(RATON)),
            Utr3("humano", load_3utr(HUMANO)),
            min_length=22,
        )
        cls.veredicto = single_shmir_verdict(cls.informe)

    def test_hay_UN_bloque_de_26_nt(self):
        self.assertEqual([b.length for b in self.informe.blocks], [26])
        self.assertEqual(
            self.informe.blocks[0].sequence, "TTTTCTATATTTGTAACTTTGCATGT"
        )

    def test_esta_en_las_dos_coordenadas_conocidas(self):
        posiciones = {h.species: (h.start, h.end) for h in self.informe.blocks[0].hits}
        self.assertEqual(posiciones["raton"], (1138, 1163))
        self.assertEqual(posiciones["humano"], (1507, 1532))

    def test_caben_cinco_ventanas_dentro(self):
        self.assertEqual(self.veredicto.windows, 5)

    def test_y_ninguna_pasa(self):
        self.assertEqual(self.veredicto.passing, 0)
        self.assertFalse(self.veredicto.possible)

    def test_los_motivos_son_de_secuencia_no_de_posicion(self):
        # Por eso son los MISMOS en las dos especies: la diana es la misma.
        motivos = {
            r.name
            for lista in self.informe.evaluations.values()
            for w in lista
            for r in w.filters
            if r.state.value == "FAIL"
        }
        self.assertEqual(motivos, {"GC", "homopolimero", "asimetria"})

    def test_lo_dice_con_esas_palabras(self):
        texto = self.veredicto.describe()
        self.assertIn("NO EXISTE un shmiR único", texto)
        self.assertIn("raton, Tg650 y clinica", texto)
        self.assertIn("ARQUITECTURA DEL PROGRAMA", texto)
        self.assertIn("no dos plazas del panel", texto)

    def test_da_las_cifras_que_lo_sostienen(self):
        texto = self.veredicto.describe()
        self.assertIn("5 ventanas", texto)

    def test_un_control_con_la_MISMA_secuencia_da_lo_contrario(self):
        # Raton contra raton: el bloque es el 3'UTR entero y si hay ventanas que pasan.
        # Sirve para comprobar que el veredicto no esta clavado en «no existe».
        control = single_shmir_verdict(
            build_conservation_report(
                Utr3("raton", load_3utr(RATON)),
                Utr3("raton (control)", load_3utr(RATON)),
                min_length=22,
            )
        )
        self.assertTrue(control.possible)
        self.assertIn("SI hay ventanas", control.describe())

    def test_sin_comparacion_es_NOT_RUN_y_no_una_negacion(self):
        veredicto = single_shmir_verdict(None)
        self.assertIsNone(veredicto.possible)
        self.assertIn("NOT_RUN", veredicto.describe())
        self.assertIn("no es «no existe»", veredicto.describe())
