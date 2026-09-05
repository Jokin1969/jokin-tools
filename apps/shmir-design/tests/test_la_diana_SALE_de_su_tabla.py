"""La diana se DECLARA en su tabla; no se teclea. Y sin declarar, NO_CIERRA.

**Decidido (2026-09-04)**, con el argumento de quien lo pidió: «`data/diana/variantes.toml`
ya declara las variantes por especie y el veredicto de BLAST las usa; que el filtro local
pida teclear una sola variante a mano es la peor de las dos definiciones».

Eran **dos respuestas a la misma pregunta** —«¿cuál es mi diana?»— y la manual ganaba:

- el veredicto de una corrida de BLAST usaba `specificity.target_accessions(especie)`, la
  lista **completa** de variantes de transcrito, declarada con su procedencia (errata
  nº 56);
- `filter_specificity` exigía un `target` **tecleado en la barra lateral**, uno solo, y
  abortaba sin él. Y `resources._refseq` se negaba a conectar `refseq_rna.fa` mientras ese
  campo estuviera vacío — con el fichero delante.

Es el patrón de siempre: un dato que ya está declarado y que además se pide a mano. Y la
manual es la peor de las dos —una variante en vez de todas, escrita sin procedencia—, así
que la que se va es ésa.

### Sin declaración NO se aborta: se dice que no cierra

Igual que en BLAST. Abortar dejaría sin diseñar a una especie por algo que no impide
proponer candidatos; dar `PASS` sería el colador que `target_accessions` existe para
impedir. `NO_CIERRA` es el estado que ya hay para «la corrida se hizo y no cierra el
frente», y aquí es literalmente eso.

Regla 5: escritos antes.
"""

import unittest

from shmir_design.filters import FilterState
from shmir_design.specificity import filter_specificity, target_accessions


class TestLaDianaSaleDeLaTabla(unittest.TestCase):
    def test_el_raton_la_tiene_declarada(self):
        # CONTROL: si la tabla dejara de declararla, el resto de esta clase estaría
        # comprobando el camino de «no declarada» creyendo que prueba el otro.
        self.assertTrue(target_accessions("raton"))

    def test_filter_specificity_YA_NO_acepta_un_target_tecleado(self):
        import inspect

        parametros = inspect.signature(filter_specificity).parameters
        self.assertNotIn("target", parametros)
        self.assertIn("species", parametros)

    def test_sin_base_sigue_siendo_NOT_RUN(self):
        # Lo que ya era: sin fichero no se ejecuta, y eso no cambia.
        resultado = filter_specificity("ACGT" * 6, None, None, species="raton")
        self.assertIs(resultado.state, FilterState.NOT_RUN)


class TestUnaEspecieSINdianaDeclaradaNOcierra(unittest.TestCase):
    """El caso que antes abortaba. Ahora dice qué falta y sigue."""

    class _BaseFalsa:
        provenance = "base de prueba"
        #: `scan_database` no llega a llamarse: se sale antes por falta de diana.
        records = ()

    def test_da_NO_CIERRA_y_no_PASS(self):
        resultado = filter_specificity(
            "ACGT" * 6, None, self._BaseFalsa(), species="conejo",
        )
        self.assertIs(resultado.state, FilterState.NO_CIERRA)

    def test_y_el_motivo_dice_QUE_falta_y_DONDE_se_declara(self):
        resultado = filter_specificity(
            "ACGT" * 6, None, self._BaseFalsa(), species="conejo",
        )
        self.assertIn("variantes.toml", resultado.reason)
        # Lo que NO puede decir es que falte el fichero: el fichero está.
        self.assertNotIn("no hay base", resultado.reason.lower())


class TestElCampoDeLaBarraLateralSeVA(unittest.TestCase):
    """Que no quede una segunda forma de contestar la misma pregunta."""

    def test_la_pagina_no_pide_ningun_gen_diana(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Gen diana", fuente)
        self.assertNotIn("gen_diana", fuente)

    def test_ni_el_CLI_tiene_bandera_para_ello(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "tools" / "design.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"--target"', fuente)


if __name__ == "__main__":
    unittest.main()
