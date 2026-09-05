"""Lo anunciado y lo emitido se reconcilian, y el fichero parcial lo dice en su nombre.

**Reportado (2026-09-05)**: el selector de alcance anuncia «el panel — 10 candidatos,
**20 pares**», el FASTA trae **10 registros**, y *«la propia app anunciaba 20 pares y ha
emitido 10, sin avisar de que faltaba la mitad»*.

**El núcleo hace lo correcto**: `build_panel` con los dos intrones devuelve **10
construcciones y 10 fallidas** con su motivo —`intron_quimerico` llega entero y no declara
dónde va el módulo—. Lo que fallaba es lo que la página hace con esas dos mitades.

Cuatro defectos, y el peor es el último:

1. **La cuenta MENTÍA.** `len(construcciones) // len(elegidos)` da `10 // 2 = 5`, así que
   la página decía «10 consulta(s) = **5 candidato(s)** × 2 intrón(es)». Ese 5 no existe:
   son 10 candidatos por 1 intrón que se pudo montar. Un número derivado que mezcla lo
   pedido con lo obtenido.
2. **Nada reconciliaba lo anunciado con lo emitido.** Dos contadores del mismo suceso —el
   del selector de alcance y el del resultado— sin nada que los ate.
3. **Diez avisos idénticos.** El fallo es del INTRÓN, no de cada candidato: repetir el
   mismo motivo diez veces es la razón de que se lea como ruido en vez de como «falta la
   mitad».
4. **Y el FASTA no decía que fuera parcial.** Ése es el que viaja: quien lo descarga y lo
   corre no tiene forma de saber que falta media corrida. El estado va **en el nombre**,
   como en el informe parcial.

Regla 5: escritos antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation, spliceai  # noqa: E402
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_reference,
)
from shmir_design.scaffold import SGEP_SCAFFOLD  # noqa: E402

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

DOS = ("mvm_actual", "intron_quimerico")


def _panel():
    tx = load_reference(RATON)
    anat = Anatomy.from_cds(
        cds=RATON.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
    )
    corrida = presentation.page_run(species="raton", sequence=tx, anatomy=anat)
    return spliceai.build_panel(
        corrida.selection, intron_names=DOS, scaffold=SGEP_SCAFFOLD,
    )


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLaReconciliacion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.panel = _panel()
        cls.resumen = presentation.splice_panel_summary(
            cls.panel, introns=DOS, candidates=10,
        )

    def test_el_nucleo_ya_devolvia_las_dos_mitades(self):
        self.assertEqual(len(self.panel.constructions), 10)
        self.assertEqual(len(self.panel.failed), 10)

    def test_dice_lo_ANUNCIADO_lo_EMITIDO_y_lo_que_FALTA(self):
        self.assertEqual(self.resumen["anunciadas"], 20)
        self.assertEqual(self.resumen["emitidas"], 10)
        self.assertEqual(self.resumen["faltan"], 10)

    def test_la_cuenta_YA_NO_inventa_un_recuento_de_candidatos(self):
        """`10 // 2 = 5` decía «5 candidatos», y ese 5 no existió nunca."""
        self.assertNotIn("5 candidato", self.resumen["texto"])
        self.assertIn("10", self.resumen["texto"])

    def test_el_desglose_es_POR_INTRON_y_no_diez_avisos_iguales(self):
        # El fallo es del intrón: repetirlo por candidato es lo que lo hace ilegible.
        por_intron = {f["intron"]: f for f in self.resumen["por_intron"]}
        self.assertEqual(por_intron["mvm_actual"]["emitidas"], 10)
        self.assertEqual(por_intron["intron_quimerico"]["emitidas"], 0)
        self.assertEqual(len(self.resumen["por_intron"]), 2)

    def test_y_el_motivo_sale_UNA_vez_con_su_intron(self):
        quimerico = next(
            f for f in self.resumen["por_intron"] if f["intron"] == "intron_quimerico"
        )
        self.assertIn("módulo", quimerico["motivo"])
        self.assertEqual(quimerico["motivos_distintos"], 1)

    def test_es_PARCIAL(self):
        self.assertTrue(self.resumen["parcial"])


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElFicheroLoDiceEnSuNOMBRE(unittest.TestCase):
    """El que viaja es el fichero: quien lo corre tiene que saber que falta media corrida."""

    @classmethod
    def setUpClass(cls):
        cls.panel = _panel()

    def test_parcial_lo_lleva_en_el_nombre(self):
        nombre = presentation.splice_fasta_name(
            self.panel, species="Mus musculus", introns=DOS, candidates=10,
        )
        self.assertIn("PARCIAL", nombre)
        self.assertIn("10", nombre)
        self.assertIn("20", nombre)
        self.assertTrue(nombre.endswith(".fa"))

    def test_completo_NO_lo_lleva(self):
        entero = spliceai.build_panel(
            _corrida_selection(), intron_names=("mvm_actual",), scaffold=SGEP_SCAFFOLD,
        )
        nombre = presentation.splice_fasta_name(
            entero, species="Mus musculus", introns=("mvm_actual",), candidates=10,
        )
        self.assertNotIn("PARCIAL", nombre)


def _corrida_selection():
    tx = load_reference(RATON)
    anat = Anatomy.from_cds(
        cds=RATON.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
    )
    return presentation.page_run(species="raton", sequence=tx, anatomy=anat).selection


class TestLaPaginaNoCalculaLaCuenta(unittest.TestCase):

    def test_no_queda_la_division_que_mentia(self):
        fuente = (RAIZ / "ui" / "streamlit_app.py").read_text("utf-8")
        limpia = "\n".join(
            l for l in fuente.split("\n") if not l.lstrip().startswith("#")
        )
        self.assertNotIn("len(construcciones) // len(elegidos)", limpia)


if __name__ == "__main__":
    unittest.main()
