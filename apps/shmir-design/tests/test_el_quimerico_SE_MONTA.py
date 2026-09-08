"""El intrón quimérico se monta: la decisión de dónde va el módulo ya estaba tomada.

**El único frente entre la corrida de 10 y la de 20.** `intron_quimerico` llega ENTERO de
su plásmido —133 pb extraídos por su anotación de Addgene #198131— y por eso
`with_module` abortaba: *«llegó entero, así que no se sabe DÓNDE va el módulo dentro»*. No
faltaba un fichero ni un cálculo: faltaba **aplicar** una decisión que ya está registrada
desde el 2026-08-30.

**La decisión, con su criterio** (`intron_design.INSERTION_RATIONALE`): posición **49** de
la ventana admisible **3-99**, por máxima separación al punto de ramificación y al tracto
entre las quince que conservan la horquilla, con la **69 registrada como descartada** —
mejor ΔG (−109,20 frente a −106,50) y peor en lo que discrimina: deja el punto a 34 nt en
vez de 54.

**Y con las dos arquitecturas montadas se puede comparar de verdad**: el quimérico tiene
donante de consenso `GTAAGT` y **11 pirimidinas** contiguas de tracto, frente a las 9 del
MVM, y no lleva `GTGAGCG`.

Regla 5: escritos antes. Los valores salen de MEDIR sobre el plásmido versionado, no de
recordarlos.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import blocks, introns, presentation, spliceai  # noqa: E402
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_reference,
)
from shmir_design.scaffold import SGEP_SCAFFOLD  # noqa: E402

RATON = REFERENCES["NM_011170.3"]
HAY_RATON = fixture_available(RATON)
HAY_QUIMERICO = introns.get("intron_quimerico").provided

#: Una guía REAL del panel murino (`3utr:735`), no una inventada (regla 1).
GUIA = "GCCCTATGTTTCTGTACTTCTA"

DOS = ("mvm_actual", "intron_quimerico")


def _modulo() -> str:
    return blocks.build_block(GUIA, scaffold=SGEP_SCAFFOLD).module


@unittest.skipUnless(HAY_QUIMERICO, "falta data/reference/addgene_198131.gb")
class TestLaDecisionVIVE_EN_UN_SITIO(unittest.TestCase):
    """El registro del intrón la declara; `intron_design` la DERIVA de ahí."""

    def test_el_intron_declara_DONDE_va_el_modulo(self):
        self.assertEqual(introns.get("intron_quimerico").insertion_point, 49)

    def test_y_intron_design_NO_la_repite(self):
        from shmir_design import intron_design

        self.assertEqual(
            intron_design.INSERTION_POSITION,
            introns.get("intron_quimerico").insertion_point,
        )

    def test_los_que_se_ensamblan_de_piezas_NO_declaran_ninguna(self):
        """El MVM pone el módulo entre sus dos mitades: no hay posición que elegir."""
        self.assertEqual(introns.get("mvm_actual").insertion_point, 0)

    def test_la_posicion_cae_en_la_ventana_ADMISIBLE_derivada_del_intron(self):
        """Los dos límites se DERIVAN del propio intrón, no se transcriben.

        Por abajo, después del donante; por arriba, el inicio del MOTIVO del primer
        candidato a punto de ramificación —invadirlo lo rompe— o el tracto, lo que
        llegue antes. Sin ViennaRNA: esto no mide la horquilla, mide la geometría.
        """
        from shmir_design.introns import BRANCH_A_OFFSET

        quimerico = introns.get("intron_quimerico")
        elementos = quimerico.elements()
        ramas = [
            c.branch_a for c in elementos.branch_candidates if c.branch_a is not None
        ]
        tope = min(min(ramas) - BRANCH_A_OFFSET, elementos.ppt.start) - 1
        self.assertGreater(quimerico.insertion_point, elementos.donor.end)
        self.assertLessEqual(quimerico.insertion_point, tope)
        # La ventana medida el 2026-08-30 fue 3-99: se comprueba que sigue siéndolo.
        self.assertEqual((elementos.donor.end + 1, tope), (3, 99))


@unittest.skipUnless(HAY_QUIMERICO, "falta data/reference/addgene_198131.gb")
class TestSeMONTA_y_los_cuatro_elementos_siguen(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.quimerico = introns.get("intron_quimerico")
        cls.modulo = _modulo()
        cls.montado = cls.quimerico.with_module(cls.modulo)

    def test_ya_NO_aborta(self):
        self.assertTrue(self.montado)

    def test_mide_lo_que_suman_las_dos_piezas(self):
        # 133 del intrón + 149 del módulo. Sin espaciadores: ver el test de abajo.
        self.assertEqual(len(self.montado), 133 + 149)

    def test_el_modulo_esta_EN_LA_POSICION_DECLARADA(self):
        inicio = self.quimerico.insertion_point
        self.assertEqual(self.montado[inicio:inicio + len(self.modulo)], self.modulo)

    def test_y_el_intron_queda_INTACTO_a_los_dos_lados(self):
        inicio = self.quimerico.insertion_point
        vacio = self.quimerico.empty_sequence
        self.assertEqual(self.montado[:inicio], vacio[:inicio])
        self.assertEqual(self.montado[inicio + len(self.modulo):], vacio[inicio:])

    def test_los_CUATRO_elementos_se_localizan_despues(self):
        elementos = introns.locate_elements(self.montado, name="intron_quimerico")
        self.assertEqual((elementos.donor.start, elementos.donor.end), (1, 2))
        self.assertEqual((elementos.acceptor.start, elementos.acceptor.end), (281, 282))
        self.assertEqual((elementos.ppt.start, elementos.ppt.end), (268, 278))
        self.assertEqual(
            [c.branch_a for c in elementos.branch_candidates], [252, 256]
        )

    def test_el_donante_sigue_siendo_el_CONSENSO(self):
        self.assertEqual(self.montado[:6], "GTAAGT")

    def test_y_el_tracto_son_ONCE_pirimidinas_frente_a_las_NUEVE_del_MVM(self):
        elementos = introns.locate_elements(self.montado, name="intron_quimerico")
        largo = elementos.ppt.end - elementos.ppt.start + 1
        self.assertEqual(largo, 11)
        mvm = introns.get("mvm_actual")
        suyos = mvm.elements(self.modulo)
        self.assertEqual(suyos.ppt.end - suyos.ppt.start + 1, 9)


@unittest.skipUnless(HAY_QUIMERICO, "falta data/reference/addgene_198131.gb")
class TestLosESPACIADORES_no_se_cuelan(unittest.TestCase):
    """La posición se eligió midiendo `secuencia[:p] + módulo + secuencia[p:]`."""

    def test_pedir_un_espaciador_ABORTA_en_un_intron_entero(self):
        quimerico = introns.get("intron_quimerico")
        with self.assertRaises(ShmirDesignError) as caja:
            quimerico.with_module(_modulo(), spacer5="AAAAA")
        self.assertIn("posición", str(caja.exception).lower())

    def test_y_el_MVM_los_sigue_poniendo(self):
        montado = introns.get("mvm_actual").with_module(_modulo())
        self.assertEqual(len(montado), 296)


class TestUnINTRON_ENTERO_SIN_posicion_sigue_abortando(unittest.TestCase):
    """No es que ahora valga cualquier intrón entero: vale el que la DECLARA."""

    def test_sin_declararla_no_se_pega_en_un_sitio_cualquiera(self):
        from dataclasses import replace

        sin = replace(introns.get("intron_quimerico"), insertion_point=0)
        with self.assertRaises(ShmirDesignError) as caja:
            sin.with_module("A" * 149)
        self.assertIn("DONDE", str(caja.exception))


@unittest.skipUnless(
    HAY_RATON and HAY_QUIMERICO, "faltan la referencia murina o el plásmido"
)
class TestLaCorridaPASA_DE_10_A_20(unittest.TestCase):
    """Es lo único que separaba las dos corridas."""

    @classmethod
    def setUpClass(cls):
        tx = load_reference(RATON)
        anat = Anatomy.from_cds(
            cds=RATON.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.corrida = presentation.page_run(
            species="raton", sequence=tx, anatomy=anat,
        )
        cls.panel = spliceai.build_panel(
            cls.corrida.selection, intron_names=DOS, scaffold=SGEP_SCAFFOLD,
        )

    def test_salen_las_VEINTE(self):
        self.assertEqual(len(self.panel.constructions), 22)

    def test_y_NINGUNA_falla(self):
        self.assertEqual(self.panel.failed, ())
        self.assertFalse(self.panel.partial)

    def test_UNO_DE_CADA_del_panel_por_intron(self):
        from collections import Counter

        cuenta = Counter(c.intron for c in self.panel.constructions)
        # ONCE por intron desde el 2026-09-06: el panel gano el segundo distal.
        self.assertEqual(cuenta["mvm_actual"], 11)
        self.assertEqual(cuenta["intron_quimerico"], 11)

    def test_el_resumen_ya_no_dice_que_falte_la_mitad(self):
        resumen = presentation.splice_panel_summary(
            self.panel, introns=DOS, candidates=11,
        )
        self.assertEqual(resumen["anunciadas"], 22)
        self.assertEqual(resumen["emitidas"], 22)
        self.assertFalse(resumen["parcial"])

    def test_y_el_FASTA_sale_COMPLETO(self):
        nombre = presentation.splice_fasta_name(
            self.panel, species="Mus musculus", introns=DOS, candidates=11,
        )
        self.assertNotIn("PARCIAL", nombre)
        fasta = presentation.splice_query_text(
            self.panel, introns=DOS, candidates=11,
        )
        self.assertEqual(fasta.count(">"), 22)
        for cabecera in (l for l in fasta.splitlines() if l.startswith(">")):
            self.assertIn("estado=COMPLETO", cabecera)
            self.assertIn("panel=22de22", cabecera)

    def test_las_DOS_arquitecturas_declaran_sus_posiciones(self):
        """Cada una con su geometría, y las dos con la convención pegada."""
        por_intron = {}
        for c in self.panel.constructions:
            por_intron.setdefault(c.intron, c)
        self.assertNotEqual(
            por_intron["mvm_actual"].donor_position,
            por_intron["intron_quimerico"].acceptor_position,
        )
        for construccion in por_intron.values():
            self.assertGreater(construccion.acceptor_position,
                               construccion.donor_position)


if __name__ == "__main__":
    unittest.main()
