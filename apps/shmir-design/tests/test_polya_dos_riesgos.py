"""Truncamiento y esterico son DOS riesgos, no uno.

Regla 5: escritos antes.

La regla de ±flanco los mezclaba, y son distintos:

- **Truncamiento.** Una ventana situada POR DETRAS del punto de corte que dirigiria un
  hexamero funcional. El corte cae 10-30 nt aguas abajo del hexamero. Una ventana que
  SOLAPA el hexamero esta aguas ARRIBA del corte y se conserva en las dos isoformas:
  no tiene riesgo de truncamiento. Es un riesgo sobre la EXISTENCIA de la diana.
- **Esterico.** Una ventana que solapa el hexamero compite con CPSF/CstF por el mismo
  tramo. Solo aplica si el hexamero se usa. Es un riesgo sobre la ACCESIBILIDAD.

Un mismo hexamero produce los dos en ventanas DISTINTAS, y nunca en la misma: o estas
encima de la señal, o estas por detras del corte.

Datos reales: el 3'UTR verificado de NM_011170.3.
"""

import unittest
from pathlib import Path

from shmir_design.polya import (
    CLEAVAGE_MAX,
    CLEAVAGE_MIN,
    RiskState,
    Window,
    find_polya_signals,
    polya_risk,
)

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"


def _utr3() -> str:
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.polya import normalize_sequence

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    return normalize_sequence(bruta, name="NM_011170.3")[949:]


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLosDosRiesgosSonDistintos(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3 = _utr3()
        cls.signals = find_polya_signals(cls.utr3)

    def _riesgo(self, inicio, señales=None):
        return polya_risk(
            Window(start=inicio, length=22),
            list(self.signals) if señales is None else list(señales),
            utr_length=len(self.utr3),
        )

    def _solo(self, posicion):
        """Una sola señal real, para poder aislar su efecto de las demas."""
        return [s for s in self.signals if s.position == posicion]

    def test_respecto_del_hexamero_que_SOLAPA_no_hay_truncamiento(self):
        # Esta aguas arriba de SU corte: se conserva en las dos isoformas.
        self.assertIs(self._riesgo(1018).truncamiento_propio, RiskState.NO_APLICA)

    def test_pero_1018_SI_tiene_truncamiento_por_el_AATAAA_de_288(self):
        # Y esto hay que decirlo, porque leer solo «truncamiento NO_APLICA» dejaria a
        # 1018 como una excepcion a su favor cuando corre el MISMO riesgo dominante que
        # los otros cuatro.
        riesgo = self._riesgo(1018)
        self.assertIs(riesgo.truncamiento, RiskState.FAIL)
        self.assertIn("288", riesgo.truncamiento_motivo)

    def test_aislando_su_propio_hexamero_el_truncamiento_es_NO_APLICA(self):
        riesgo = self._riesgo(1018, self._solo(1034))
        self.assertIs(riesgo.truncamiento, RiskState.NO_APLICA)

    def test_pero_SI_tiene_esterico(self):
        riesgo = self._riesgo(1018)
        self.assertIs(riesgo.esterico, RiskState.PENALIZADO)

    def test_el_esterico_de_1018_es_por_ACTAAA_clase_OTRA(self):
        riesgo = self._riesgo(1018)
        self.assertIn("ACTAAA", riesgo.esterico_motivo)
        self.assertIn("OTRA", riesgo.esterico_motivo)

    def test_el_motivo_del_propio_dice_que_esta_aguas_ARRIBA(self):
        motivo = self._riesgo(1018).truncamiento_propio_motivo.lower()
        self.assertIn("aguas arriba", motivo)

    def test_y_avisa_de_que_eso_no_dice_nada_de_otras_señales(self):
        self.assertIn("mas arriba", self._riesgo(1018).truncamiento_propio_motivo.lower())

    def test_los_dos_riesgos_nunca_son_el_mismo_hexamero_en_la_misma_ventana(self):
        # O estas encima de la señal, o estas por detras del corte. Las dos cosas a la
        # vez, con el MISMO hexamero, no puede ser.
        for inicio in range(1, len(self.utr3) - 21, 37):
            riesgo = self._riesgo(inicio)
            with self.subTest(inicio):
                if riesgo.esterico is not RiskState.NO_APLICA:
                    self.assertIsNot(
                        riesgo.truncamiento_signal, riesgo.esterico_signal
                    )

    def test_una_ventana_muy_por_detras_es_FAIL_de_truncamiento(self):
        señal = self._solo(288)[0]
        riesgo = self._riesgo(señal.end + CLEAVAGE_MAX + 5, self._solo(288))
        self.assertIs(riesgo.truncamiento, RiskState.FAIL)

    def test_en_la_banda_de_incertidumbre_es_PENALIZADO_no_FAIL(self):
        # Entre 10 y 30 nt aguas abajo no se sabe si el corte cae antes o despues. Se
        # aisla el AATAAA de 288 para que no lo tape ninguna otra señal.
        señal = self._solo(288)[0]
        riesgo = self._riesgo(señal.end + CLEAVAGE_MIN + 5, self._solo(288))
        self.assertIs(riesgo.truncamiento, RiskState.PENALIZADO)

    def test_la_distancia_al_corte_previsto_viene_con_el_veredicto(self):
        señal = self._solo(288)[0]
        inicio = señal.end + CLEAVAGE_MAX + 5
        riesgo = self._riesgo(inicio, self._solo(288))
        self.assertEqual(
            riesgo.distancia_corte, inicio - (señal.end + CLEAVAGE_MIN)
        )

    def test_sin_ninguna_señal_cerca_los_dos_son_NO_APLICA(self):
        riesgo = polya_risk(
            Window(start=100, length=22), [], utr_length=len(self.utr3)
        )
        self.assertIs(riesgo.truncamiento, RiskState.NO_APLICA)
        self.assertIs(riesgo.esterico, RiskState.NO_APLICA)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElAATAAADe288(unittest.TestCase):
    """El riesgo de truncamiento DOMINANTE del panel, y quien es inmune."""

    @classmethod
    def setUpClass(cls):
        cls.utr3 = _utr3()
        cls.signals = find_polya_signals(cls.utr3)

    def test_hay_un_AATAAA_canonico_en_288(self):
        canonicas = [s for s in self.signals if s.motif == "AATAAA"]
        self.assertTrue(any(s.position == 288 for s in canonicas))

    def test_los_cinco_candidatos_del_panel_estan_por_detras(self):
        for inicio in (449, 553, 652, 819, 1018):
            with self.subTest(inicio):
                riesgo = polya_risk(
                    Window(start=inicio, length=22), list(self.signals),
                    utr_length=len(self.utr3),
                )
                self.assertIsNot(riesgo.truncamiento, RiskState.NO_APLICA)

    def test_y_los_proximales_son_INMUNES(self):
        for inicio in (60, 143, 221):
            with self.subTest(inicio):
                riesgo = polya_risk(
                    Window(start=inicio, length=22), list(self.signals),
                    utr_length=len(self.utr3),
                )
                self.assertIs(riesgo.truncamiento, RiskState.NO_APLICA)


if __name__ == "__main__":
    unittest.main()
