"""La propuesta de variante en el modal, pedida ENTERA a `presentation`.

Encontrado en la revision del PR #21. La pagina hacia:

    variant_proposal_text(seleccion.selection.chosen[0].guide ...)

y `selection.Choice` NO tiene `guide` — solo `start`, `end`, `label` y los parametros.
La guia se alcanza por `selection.window_of(choice).evaluation.guide`, que es como lo
hace `block_bundle`. Resultado: `AttributeError` en cuanto alguien abriera el modal de
empalme con un candidato elegido. Dos fallos en uno, y el segundo explica el primero:
la pagina estaba NAVEGANDO el modelo, que es justo lo que la regla 6 prohibe. Se le
pide el texto a `presentation` y se acabo la navegacion.
"""

import unittest

from shmir_design.presentation import variant_proposal_for, variant_proposal_text
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.selection import Choice

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


class TestChoiceNoTieneGuia(unittest.TestCase):
    def test_el_campo_que_la_pagina_leia_no_existe(self):
        self.assertNotIn("guide", Choice.__dataclass_fields__)


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del raton")
class TestSeLePideAPresentation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        cls.seleccion = select_from_report(
            tile_utr(load_3utr(RATON)), SelectionConfig(n_candidates=3)
        )

    def test_devuelve_texto_y_no_revienta(self):
        texto = variant_proposal_for(self.seleccion)
        self.assertIsInstance(texto, str)
        self.assertTrue(texto.strip())

    def test_es_el_mismo_texto_que_da_la_guia_a_mano(self):
        elegido = self.seleccion.selection.chosen[0]
        guia = self.seleccion.window_of(elegido).evaluation.guide.replace("U", "T")
        self.assertEqual(
            variant_proposal_for(self.seleccion), variant_proposal_text(guia)
        )


class TestSinCandidatos(unittest.TestCase):
    def test_sin_elegidos_lo_dice_y_no_aborta(self):
        class _Vacia:
            class selection:  # noqa: N801
                chosen = ()

        texto = variant_proposal_for(_Vacia())
        self.assertIn("Sin guía", texto)


class TestLaPaginaNoNavegaElModelo(unittest.TestCase):
    def test_la_pagina_no_encadena_chosen_con_un_atributo(self):
        from pathlib import Path

        pagina = Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py"
        texto = pagina.read_text(encoding="utf-8")
        self.assertNotIn("chosen[0].", texto)


if __name__ == "__main__":
    unittest.main()
