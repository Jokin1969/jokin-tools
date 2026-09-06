"""`locate_intron` deja de buscar las mitades del MVM y resuelve por el DECLARADO.

Regla 5: escritos antes.

## La asimetría que había que cerrar

Señalado por el responsable del proyecto (2026-09-06):

> *«La arquitectura que gana en todo lo medido es la única que no se puede verificar en
> el banco, y eso es una asimetría que hoy no se ve porque el NO_APLICA parece una
> carencia menor.»*

`splice_rtpcr_plan` deriva las ventanas de cebador con las que se mide la eficiencia de
empalme, y las derivaba de `locate_intron`, que buscaba **las dos piezas fijas del MVM**.
Con el intrón quimérico dentro no las encuentra: la construcción que gana en las cinco
métricas de SpliceAI se quedaba sin la única medida de banco de su propio frente — y el
frente del empalme es el ÚNICO binario del proyecto.

No era un fallo de un cálculo: era que el localizador tenía la arquitectura escrita
dentro. Ahora recibe el intrón DECLARADO en la construcción y resuelve por sus propios
extremos, que es lo que ya sabía hacer `montaje.intron_in_plasmid`.

## Y por qué los extremos y no las piezas

Un intrón que se ensambla de piezas versionadas (`mvm_actual`) tiene dos mitades que
buscar; uno que llega entero (`intron_quimerico`) no tiene piezas — llega como una sola
secuencia. Lo que los DOS tienen es extremos, y el módulo va por dentro sin tocarlos: por
eso el mismo criterio vale con el intrón vacío y con el montado.
"""

import pathlib
import unittest

from shmir_design import blocks, fragmento, introns, splicing
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.scaffold import build_hairpin

DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "reference"
CASETE = DIR / "aav_casete.fa"
QUIMERICO = DIR / introns.QUIMERICO_PLASMID
GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"


def _casete() -> str:
    crudo = CASETE.read_text(encoding="utf-8").splitlines()
    return "".join(l.strip() for l in crudo if not l.startswith(">")).upper()


@unittest.skipUnless(
    CASETE.is_file() and QUIMERICO.is_file(),
    "NOT_RUN: falta aav_casete.fa o el plásmido del quimérico",
)
class TestElLocalizadorConLosDosIntrones(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        feature = fragmento.locate_feature(cls.casete, name="aav_casete.fa")
        cls.feature = feature
        cls.p_qui = feature.paste(
            feature.exon5
            + introns.get("intron_quimerico").empty_sequence
            + feature.exon3
        )

    def test_el_parental_sigue_saliendo_IGUAL_que_antes(self):
        sitio = splicing.locate_intron(self.casete, name="aav_casete.fa")
        self.assertEqual((sitio.donor_start, sitio.acceptor_end), (3134, 3215))
        self.assertEqual(sitio.length, 82)
        self.assertTrue(sitio.empty)
        self.assertEqual(sitio.intron_name, "mvm_actual")

    def test_con_el_QUIMERICO_dentro_lo_encuentra_si_se_DECLARA(self):
        sitio = splicing.locate_intron(
            self.p_qui, name="casete con el quimérico", intron="intron_quimerico"
        )
        self.assertEqual(sitio.length, 133)
        self.assertEqual(sitio.donor, "GT")
        self.assertEqual(sitio.acceptor, "AG")
        self.assertTrue(sitio.empty)
        self.assertEqual(sitio.intron_name, "intron_quimerico")

    def test_y_con_el_intron_EQUIVOCADO_aborta_NOMBRANDOLO(self):
        with self.assertRaises(ShmirDesignError) as cm:
            splicing.locate_intron(
                self.p_qui, name="casete con el quimérico", intron="mvm_actual"
            )
        self.assertIn("mvm_actual", str(cm.exception))

    def test_con_el_MODULO_dentro_tambien_resuelve_los_dos(self):
        for nombre, montado in (
            ("mvm_actual", 284), ("intron_quimerico", 270),
        ):
            frag = fragmento.build_fragment(
                build_hairpin(GUIA_1018), cassette=self.casete, intron=nombre
            )
            sitio = splicing.locate_intron(
                frag.feature.paste(frag.sequence), name="pegado", intron=nombre
            )
            self.assertEqual(sitio.length, montado, nombre)
            self.assertFalse(sitio.empty, nombre)

    def test_los_extremos_que_se_buscan_son_UNICOS(self):
        for nombre, plasmido in (
            ("mvm_actual", self.casete), ("intron_quimerico", self.p_qui),
        ):
            cinco, tres = splicing.intron_boundaries(nombre)
            self.assertEqual(plasmido.count(cinco), 1, f"{nombre} 5'")
            self.assertEqual(plasmido.count(tres), 1, f"{nombre} 3'")

    def test_el_intron_sin_secuencia_ABORTA_con_su_motivo(self):
        with self.assertRaises(ShmirDesignError) as cm:
            splicing.intron_boundaries("mvm_sin_criptico")
        self.assertIn("mvm_sin_criptico", str(cm.exception))


@unittest.skipUnless(
    CASETE.is_file() and QUIMERICO.is_file(),
    "NOT_RUN: falta aav_casete.fa o el plásmido del quimérico",
)
class TestElQuimericoYA_TIENE_ventanas_de_cebador(unittest.TestCase):
    """Lo que cerraba la asimetría: la medida de banco del frente binario."""

    @classmethod
    def setUpClass(cls):
        cls.casete = _casete()
        feature = fragmento.locate_feature(cls.casete, name="aav_casete.fa")
        cls.p_qui = feature.paste(
            feature.exon5
            + introns.get("intron_quimerico").empty_sequence
            + feature.exon3
        )

    def test_el_plan_de_RT_qPCR_sale_para_el_quimerico(self):
        plan = splicing.splice_rtpcr_plan(
            self.p_qui, name="casete con el quimérico", intron="intron_quimerico"
        )
        self.assertTrue(plan.upstream.usable)
        self.assertTrue(plan.downstream.usable)

    def test_y_sus_ventanas_NO_son_las_del_MVM(self):
        """Distinta arquitectura, distinta unión: si salieran iguales no medirían ésta."""
        del_mvm = splicing.splice_rtpcr_plan(self.casete, name="parental")
        del_qui = splicing.splice_rtpcr_plan(
            self.p_qui, name="quimérico", intron="intron_quimerico"
        )
        self.assertNotEqual(
            (del_mvm.downstream.start, del_mvm.downstream.end),
            (del_qui.downstream.start, del_qui.downstream.end),
        )

    def test_el_fragmento_del_quimerico_YA_SALE_localizable(self):
        frag = fragmento.build_fragment(
            build_hairpin(GUIA_1018), cassette=self.casete,
            intron="intron_quimerico",
        )
        self.assertIs(frag.check("localizable").state, FilterState.PASS)

    def test_un_intron_que_NO_se_puede_localizar_DICE_la_consecuencia(self):
        """Mientras quede algún NO_APLICA, tiene que decir lo que cuesta."""
        self.assertIn("NO HAY CON QUÉ MEDIR SU EMPALME", fragmento.WHY_LOCATABLE_MATTERS)
        self.assertIn("empalme", fragmento.WHY_LOCATABLE_MATTERS.lower())


if __name__ == "__main__":
    unittest.main()
