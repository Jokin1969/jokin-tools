"""Un amplicón distal que cruza OTRO corte no mide lo que su etiqueta dice.

Regla 5: escrito antes.

Sale de comprobar la corrección del responsable sobre los amplicones viejos, y de
encontrar que la misma clase de fallo seguía viva en los nuevos.

**Lo que él vio, confirmado y peor de lo que dijo.** Los amplicones se habían diseñado
contra el `AATAAA` de `3utr:288`, cuyo corte cae en `3utr:303-323`. Con la promoción por
medida, el corte más temprano pasó a ser el del `AATATA` de `3utr:236`, en
`3utr:251-271` — y ese tramo cae **entero dentro** del amplicón proximal viejo
(`3utr:158-277`). No queda a caballo: queda **partido en dos por el propio suceso que se
quería medir**, así que en la isoforma corta no amplifica y la razón distal/proximal no
mide nada.

**Y la segunda mitad, que es contra la propuesta nueva.** `rtqpcr_amplicons` recibe UNA
señal y coloca el distal justo detrás de SU banda de corte. No sabe que hay otra. El
distal nuevo (`3utr:282-401`) queda entero detrás de `251-271` — correcto para esa señal
— pero **atraviesa `303-323`**, la banda del `AATAAA` de 288. En la isoforma cortada ahí
tampoco amplifica.

**Y no se arregla moviéndolo**: entre las dos bandas, con 10 nt de holgura, quedan
`3utr:282-292` — **11 nt** para un amplicón de 120. Es geométricamente imposible aislar
el evento de 236 con esta arquitectura.

**Eso NO invalida el experimento, y por qué importa decirlo bien**: la pregunta del panel
es el techo de sus seis candidatos con truncamiento, y los seis están detrás de LAS DOS
bandas — o sea el tramo de 0,86. La razón distal/proximal mide exactamente eso. Lo que
NO puede hacer es confirmar el 0,91 del tramo intermedio, y quien lea el plan tiene que
saberlo antes de pedir cebadores.
"""

import unittest

from shmir_design.polya import CLEAVAGE_MAX, CLEAVAGE_MIN, find_polya_signals, SignalClass
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

#: Los amplicones que estaban en el registro, diseñados contra `3utr:288`.
VIEJOS = {"proximal": (158, 277), "distal": (684, 803)}


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del ratón")
class TestLosDosCortesMedIDOS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.señales = [
            s for s in tile_utr(load_3utr(RATON)).signals
            if s.classification is SignalClass.APA_POSSIBLE
        ]

    def test_hay_DOS_y_no_una(self):
        self.assertEqual([s.position for s in self.señales], [236, 288])

    def test_sus_bandas_de_corte(self):
        bandas = [(s.end + CLEAVAGE_MIN, s.end + CLEAVAGE_MAX) for s in self.señales]
        self.assertEqual(bandas, [(251, 271), (303, 323)])


class TestElAmpliconVIEJOQuedaPARTIDO(unittest.TestCase):
    """La corrección del responsable, comprobada con aritmética y no aceptada de palabra."""

    CORTE_236 = (251, 271)

    def test_el_corte_nuevo_cae_ENTERO_dentro_del_proximal_viejo(self):
        ini, fin = VIEJOS["proximal"]
        self.assertLess(ini, self.CORTE_236[0])
        self.assertLess(self.CORTE_236[1], fin)

    def test_asi_que_en_la_isoforma_corta_NO_amplifica(self):
        # Un amplicon partido por el corte no da producto en la isoforma cortada: el
        # proximal dejaria de medir «el total» y la razon no significaria nada.
        ini, fin = VIEJOS["proximal"]
        self.assertTrue(ini <= self.CORTE_236[0] <= fin)

    def test_el_distal_viejo_si_estaba_bien_colocado(self):
        # No todo estaba mal, y decirlo importa: el distal seguia entero por detras.
        ini, _ = VIEJOS["distal"]
        self.assertGreater(ini, self.CORTE_236[1])


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del ratón")
class TestElPlanDECLARAQueCortesCruza(unittest.TestCase):
    """Lo que hay que añadir: el plan dice qué otras bandas atraviesa cada amplicón."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.polya import rtqpcr_amplicons

        informe = tile_utr(load_3utr(RATON))
        señales = [
            s for s in informe.signals
            if s.classification is SignalClass.APA_POSSIBLE
        ]
        cls.plan = rtqpcr_amplicons(
            señales[0], utr_length=informe.utr_length, others=tuple(señales[1:])
        )

    def test_el_distal_cruza_la_banda_de_la_OTRA_señal(self):
        self.assertTrue(self.plan.distal_crosses)
        self.assertIn(288, [s.position for s in self.plan.distal_crosses])

    def test_y_el_proximal_no_cruza_ninguna(self):
        self.assertEqual(self.plan.proximal_crosses, ())

    def test_el_texto_DICE_lo_que_la_razon_mide_de_verdad(self):
        texto = "\n".join(self.plan.describe())
        self.assertIn("LAS DOS", texto.upper())

    def test_y_dice_que_el_tramo_intermedio_NO_se_puede_aislar(self):
        texto = "\n".join(self.plan.describe()).lower()
        self.assertIn("no cabe", texto)

    def test_sin_otras_señales_no_se_inventa_ningun_aviso(self):
        from shmir_design.polya import rtqpcr_amplicons

        informe = tile_utr(load_3utr(RATON))
        señal = next(s for s in informe.signals if s.position == 236)
        plan = rtqpcr_amplicons(señal, utr_length=informe.utr_length)
        self.assertEqual(plan.distal_crosses, ())
        self.assertNotIn("no cabe", "\n".join(plan.describe()).lower())


if __name__ == "__main__":
    unittest.main()
