"""Cuando el código y la prosa discrepan sobre un hecho, la prosa es la que se quedó atrás.

Regla 5: escrito antes.

Sale de la errata nº 26. El `CLAUDE.md` afirmaba que los amplicones de la RT-qPCR iban
«esquivando las dianas del panel». **El código emitía `⚠ solapa`** en esa misma línea, y
la prosa decía lo contrario. El que estaba mal era **el texto que lee una persona**.

La contramedida no es revisar mejor: es que las frases que afirman un hecho calculable o
las **emita el generador**, o las **contraste un test**. Este test hace lo segundo con
las que ya están escritas.

No cubre toda la prosa del registro y no pretende: cubre las afirmaciones que el código
puede desmentir. Cada una va con el hecho que la contradice, para que quien la lea sepa
qué comprobar.
"""

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
REGISTRO = RAIZ / "CLAUDE.md"


class TestLoQueElRegistroAFIRMAYElCodigoPuedeDESMENTIR(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.texto = REGISTRO.read_text(encoding="utf-8")

    FRASE = "esquivando las dianas del panel"

    def test_no_AFIRMA_que_los_amplicones_esquiven_las_dianas(self):
        # NO LO CONSIGUEN, y el codigo lo dice con `⚠ solapa`. Es la errata nº 26.
        # La frase puede seguir apareciendo ENTRECOMILLADA —el registro la cita para
        # decir que era falsa—, pero no como afirmacion. Es la misma distincion que
        # necesitaron el guardia de las tildes y el de los simbolos citados.
        afirmaciones = [
            f"CLAUDE.md:{n}  {l.strip()}"
            for n, l in enumerate(self.texto.splitlines(), 1)
            if self.FRASE in l and "«" not in l
        ]
        self.assertEqual(afirmaciones, [], "\n".join(afirmaciones))

    def test_pero_SIGUE_citada_como_errata(self):
        # Borrarla del todo perderia la memoria de que se llego a afirmar.
        self.assertIn(f"«{self.FRASE}»", self.texto)

    def test_y_si_hablan_de_solape_es_para_decir_que_LO_HAY(self):
        if "solapa" not in self.texto:
            self.skipTest("NOT_RUN: el registro ya no habla de solape")
        self.assertIn("⚠ solapa", self.texto)

    def test_los_amplicones_que_el_registro_da_son_los_que_EMITE_el_codigo(self):
        """La afirmación más cara del fichero: alguien la copia a un cuaderno."""
        from shmir_design.polya import SignalClass
        from shmir_design.reference import REFERENCES, fixture_available, load_3utr
        from shmir_design.tiling import tile_utr

        if not fixture_available(REFERENCES["NM_011170.3"]):
            self.skipTest("NOT_RUN: falta el fixture del ratón")
        from shmir_design.polya import rtqpcr_amplicons

        informe = tile_utr(load_3utr(REFERENCES["NM_011170.3"]))
        señales = [
            s for s in informe.signals
            if s.classification is SignalClass.APA_POSSIBLE
        ]
        plan = rtqpcr_amplicons(
            señales[0], utr_length=informe.utr_length, others=tuple(señales[1:])
        )
        for amp in (plan.proximal, plan.distal):
            with self.subTest(f"3utr:{amp.start}-{amp.end}"):
                self.assertIn(f"`3utr:{amp.start}-{amp.end}`", self.texto)

    def test_y_los_VIEJOS_salen_marcados_como_que_no_valen(self):
        # Tacharlos no basta si el que los tiene en un cuaderno no ve por que.
        self.assertIn("~~", self.texto)
        self.assertIn("NO VALEN", self.texto)


class TestLasCIFRASDelRegistroQueElCodigoCALCULA(unittest.TestCase):
    """Números que el registro afirma y que salen de una corrida."""

    @classmethod
    def setUpClass(cls):
        cls.texto = REGISTRO.read_text(encoding="utf-8")
        from shmir_design.reference import REFERENCES, fixture_available

        cls.hay = fixture_available(REFERENCES["NM_011170.3"])

    def _informe(self):
        from shmir_design.reference import REFERENCES, load_3utr
        from shmir_design.tiling import tile_utr

        return tile_utr(load_3utr(REFERENCES["NM_011170.3"]))

    def test_el_panel_de_diez_que_afirma_es_el_que_sale(self):
        if not self.hay:
            self.skipTest("NOT_RUN: falta el fixture del ratón")
        from shmir_design.selection import default_config, select_from_report

        panel = sorted(
            c.start
            for c in select_from_report(self._informe(), default_config()).selection.chosen
        )
        declarado = re.search(
            r"corrida real por defecto da `3utr:` \*\*([0-9,\s]+?)\*\*", self.texto,
            re.S,
        )
        self.assertIsNotNone(declarado, "el registro ya no declara el panel")
        self.assertEqual(
            [int(x) for x in declarado.group(1).replace(",", " ").split()], panel
        )


if __name__ == "__main__":
    unittest.main()
