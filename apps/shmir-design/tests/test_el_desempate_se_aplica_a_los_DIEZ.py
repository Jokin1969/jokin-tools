"""El desempate se aplica POR CANDIDATO, y la columna sale aunque el resultado repita.

**Medido antes de aplicar nada (2026-09-04)**, que es como se pidió: sobre el panel
murino real los **diez** candidatos empatan, y siempre entre **las mismas dos**
alternativas —`C@4` y `T@4`—, que son exactamente el par sobre el que se tomó la decisión
con la guía de `3utr:60`. Ninguno queda sin empate y ninguno empata entre alternativas
distintas de T/C, así que ninguna de las dos salvaguardas llega a dispararse.

**Y la columna sale igual.** El resultado es idéntico en los diez, así que emitirlo parece
redundante — y es justo al revés: *el día que entre un candidato nuevo y NO empate, esa
columna es lo único que lo dirá*. Un valor constante que se calcula y no se enseña es
indistinguible de uno que nadie ha mirado.

Las dos salvaguardas, que ya estaban en `apply_tiebreak` y ahora se ejercitan por
candidato:

  · un candidato SIN empate **no usa la regla** — se queda con lo que salga;
  · un empate entre alternativas donde la decisión registrada **no está** ABORTA, en vez
    de imponer una elección sobre un conjunto que nadie ha comparado.

Regla 5: escritos antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation  # noqa: E402
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.folding import VIENNA_AVAILABLE  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_reference,
)

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _corrida():
    tx = load_reference(RATON)
    anat = Anatomy.from_cds(
        cds=RATON.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
    )
    return presentation.page_run(species="raton", sequence=tx, anatomy=anat)


@unittest.skipUnless(HAY and VIENNA_AVAILABLE, "falta el fixture o ViennaRNA")
class TestLaTablaDeLosDiez(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.filas = presentation.variant_rows(_corrida().selection)

    def test_hay_una_fila_POR_CANDIDATO(self):
        self.assertEqual(len(self.filas), 10)

    def test_cada_fila_dice_QUE_BASE_salio(self):
        for fila in self.filas:
            with self.subTest(fila["inicio"]):
                self.assertEqual(fila["base"], "T")

    def test_y_dice_SI_HUBO_EMPATE_aunque_el_resultado_repita(self):
        """La columna que sólo servirá el día que uno NO empate."""
        for fila in self.filas:
            with self.subTest(fila["inicio"]):
                self.assertTrue(fila["empate"])
                self.assertIn("C@4", fila["alternativas"])
                self.assertIn("T@4", fila["alternativas"])

    def test_los_diez_empatan_entre_LAS_MISMAS_dos(self):
        self.assertEqual({f["alternativas"] for f in self.filas}, {"C@4, T@4"})

    def test_el_motivo_del_desempate_VIAJA_con_cada_fila(self):
        # Un criterio que la app NO mide no puede salir como si lo hubiera medido.
        for fila in self.filas:
            self.assertIn("no mide", fila["motivo"].lower())


class TestLasDosSalvaguardas(unittest.TestCase):

    def test_sin_empate_NO_se_usa_la_regla(self):
        from shmir_design.intron_design import BreakCandidate, BreakChoice, apply_tiebreak

        from shmir_design.filters import FilterState

        unica = BreakCandidate(
            position=4, original="A", replacement="G", flank5="",
            motif="GTGGGCG", donor_score=1,
        )
        elegida = apply_tiebreak(
            BreakChoice(state=FilterState.PASS, candidates=(unica,),
                        folding_ok=(True,), chosen=unica, tied=())
        )
        self.assertIs(elegida, unica)

    def test_un_empate_SIN_la_decision_registrada_ABORTA(self):
        from shmir_design.errors import ShmirDesignError
        from shmir_design.intron_design import BreakCandidate, BreakChoice, apply_tiebreak

        from shmir_design.filters import FilterState

        otras = (
            BreakCandidate(position=2, original="T", replacement="G", flank5="",
                           motif="GGGAGCG", donor_score=1),
            BreakCandidate(position=6, original="C", replacement="A", flank5="",
                           motif="GTGAGAG", donor_score=1),
        )
        with self.assertRaises(ShmirDesignError) as caja:
            apply_tiebreak(
                BreakChoice(state=FilterState.PASS, candidates=otras,
                            folding_ok=(True, True), chosen=None, tied=otras)
            )
        self.assertIn("nadie ha comparado", str(caja.exception))


class TestLaProsaQueSeQuedoATRAS(unittest.TestCase):
    """`why_missing` decía que hacía falta una decisión. La decisión existe."""

    def test_ya_no_dice_que_falte_una_decision(self):
        from shmir_design.introns import INTRONS

        texto = INTRONS["mvm_sin_criptico"].why_missing.lower()
        self.assertNotIn("hace falta una decisión", texto)
        self.assertNotIn("la app no elige", texto)


if __name__ == "__main__":
    unittest.main()
