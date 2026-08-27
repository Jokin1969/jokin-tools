"""`mvm_sin_criptico`: la variante que la app DISEÑA, con las dos decisiones juntas.

Es el tercer intrón del registro y el único que no viene de ningún sitio: se DERIVA del
`mvm_actual` con dos criterios computables y por eso es una PROPUESTA, no una
construcción aprobada.

  1. **Romper `GTGAGCG`** con la base que más baje el sitio críptico SIN alterar el
     plegado del 97-mero contra SGEP. Las dos métricas juntas, y si empatan NO se elige:
     salen todas. Elegir «por lo que baja el críptico» sin mirar el plegado es el fallo
     que este proyecto ya cometió con la pasajera.
  2. **Espaciadores por PLEGADO**, con las longitudes FIJAS en 20/45. El barrido de
     longitudes se hizo y no discriminó, así que aquí sólo se elige la SECUENCIA — que es
     donde la accesibilidad sí distingue. Ver `spacers.WHY_FIXED_LENGTHS`.

Y NO genera secuencia biológica por su cuenta (regla 1): cambia UNA base de un andamio
versionado y rellena espaciadores, que es lo que ya estaba autorizado para la variante.
"""

import unittest

from shmir_design import intron_design
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.scaffold import SGEP_SCAFFOLD

GUIA = "TATTTAATGTCAGTCTGATAGC"


class TestLaFUNCION_EXISTE_Y_LA_LLAMAN(unittest.TestCase):

    def test_design_variant_existe(self):
        # El registro la nombraba en `why_missing` y NO existía: una función citada como
        # si estuviera es peor que una que falta y se dice.
        self.assertTrue(hasattr(intron_design, "design_variant"))

    def test_y_el_registro_la_nombra_bien(self):
        from shmir_design.introns import INTRONS

        motivo = INTRONS["mvm_sin_criptico"].why_missing
        self.assertIn("design_variant", motivo)


class TestLasDosDECISIONES(unittest.TestCase):

    def setUp(self):
        self.variante = intron_design.design_variant(
            guide=GUIA, scaffold=SGEP_SCAFFOLD
        )

    def test_trae_el_corte_SIEMPRE(self):
        self.assertIsNotNone(self.variante.break_choice)

    def test_y_los_espaciadores_se_eligen_sobre_el_andamio_YA_decidido(self):
        # El orden importa: unos espaciadores elegidos sobre un andamio sin decidir no
        # valen para el andamio que salga.
        self.assertIsNotNone(self.variante.spacer_search)
        self.assertIsNotNone(self.variante.scaffold)

    def test_el_estado_es_PASS_porque_las_DOS_se_resolvieron(self):
        # El corte EMPATA y lo resuelve el DESEMPATE del responsable, que la app no mide;
        # los espaciadores estándar conservan la estructura. Las dos decisiones cerradas.
        self.assertIs(self.variante.state, FilterState.PASS)
        self.assertIsNotNone(self.variante.spacer_search.choice)

    def test_el_corte_EMPATA_y_lo_resuelve_el_DESEMPATE__no_un_calculo(self):
        # La app sigue sin poder elegir: `chosen` es None y las dos siguen empatadas. Lo
        # que decide es una decisión REGISTRADA, y el texto lo dice — para que nadie lea
        # `GTGTGCG` como si lo hubiera calculado algo.
        from shmir_design.intron_design import (
            TIEBREAK_DECISION, TIEBREAK_MOTIF, TIEBREAK_POSITION, TIEBREAK_REJECTED,
        )

        self.assertIsNone(self.variante.break_choice.chosen)
        self.assertEqual(len(self.variante.break_choice.tied), 2)
        texto = self.variante.describe_text()
        self.assertIn(f"{TIEBREAK_DECISION} en la posición {TIEBREAK_POSITION}", texto)
        self.assertIn(TIEBREAK_MOTIF, texto)
        self.assertIn("no lo mide la app", texto)
        self.assertIn("responsable del proyecto", texto)

    def test_y_la_DESCARTADA_queda_registrada_con_su_motivo(self):
        # «Descartada, no eliminada»: si la elegida da problemas, la segunda está a un
        # gBlock de distancia y no hay que volver a razonarla.
        from shmir_design.intron_design import TIEBREAK_REJECTED

        texto = self.variante.describe_text()
        self.assertIn(TIEBREAK_REJECTED, texto)
        self.assertIn("DESCARTADA, no eliminada", texto)
        self.assertIn("gBlock de distancia", texto)

    def test_el_desempate_ABORTA_si_ya_no_aplica(self):
        # Si las que empatan cambian —otra guía, otro andamio— la decisión de hoy puede
        # no estar entre ellas. Aplicarla a ciegas sería imponerla sobre alternativas que
        # nadie ha comparado.
        from dataclasses import replace as _replace

        from shmir_design.intron_design import BreakChoice, apply_tiebreak

        otras = _replace(
            self.variante.break_choice,
            chosen=None,
            tied=tuple(
                c for c in self.variante.break_choice.tied if c.replacement != "T"
            ),
        )
        with self.assertRaises(ShmirDesignError) as ctx:
            apply_tiebreak(otras)
        self.assertIn("NO está entre", str(ctx.exception))

    def test_hoy_con_la_guia_de_referencia_EMPATAN_DOS(self):
        # El resultado real, fijado: de 21 alternativas, seis conservan el plegado, y de
        # ésas las dos que más bajan el donante empatan exactamente. La app NO elige, y
        # esto lo deja escrito para que cambiarlo tenga que pasar por aquí.
        empatan = {
            (c.position, c.replacement, c.motif)
            for c in self.variante.break_choice.tied
        }
        self.assertEqual(
            empatan, {(4, "C", "GTGCGCG"), (4, "T", "GTGTGCG")}
        )

    def test_las_longitudes_de_espaciador_son_las_FIJAS(self):
        from shmir_design.spacers import SPACER3_LENGTH, SPACER5_LENGTH

        if self.variante.spacer_search is None:
            self.skipTest("el corte no quedó resuelto, así que no se buscó espaciador")
        eleccion = self.variante.spacer_search.choice
        if eleccion is not None:
            self.assertEqual(len(eleccion.spacer5), SPACER5_LENGTH)
            self.assertEqual(len(eleccion.spacer3), SPACER3_LENGTH)

    def test_y_NO_se_explora_ninguna_otra_longitud(self):
        fuente = _fuente()
        self.assertNotIn("sweep_side", fuente)
        self.assertIn("WHY_FIXED_LENGTHS", fuente)


class TestEsUnaPROPUESTA(unittest.TestCase):

    def test_sale_marcada_como_propuesta_y_no_como_construccion(self):
        variante = intron_design.design_variant(guide=GUIA, scaffold=SGEP_SCAFFOLD)
        texto = variante.describe_text()
        self.assertIn("PROPUESTA, no una construcción aprobada", texto)

    def test_el_andamio_derivado_sale_con_verified_en_FALSO(self):
        # Un andamio con UNA base cambiada ya NO es el verificado, y decir que sí lo es
        # sería la regla 1 por la puerta de atrás.
        variante = intron_design.design_variant(guide=GUIA, scaffold=SGEP_SCAFFOLD)
        if variante.scaffold is not None:
            self.assertFalse(variante.scaffold.verified)

    def test_una_guia_vacia_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            intron_design.design_variant(guide="", scaffold=SGEP_SCAFFOLD)


class TestSinViennaNO_INVENTA(unittest.TestCase):

    def test_sale_NOT_RUN_entero_y_dice_por_que(self):
        variante = intron_design.design_variant(
            guide=GUIA, scaffold=SGEP_SCAFFOLD, available=False
        )
        self.assertIs(variante.state, FilterState.NOT_RUN)
        self.assertIn("ViennaRNA", variante.describe_text())
        self.assertIsNone(variante.scaffold)


def _fuente():
    from pathlib import Path

    return (
        Path(__file__).resolve().parent.parent / "shmir_design" / "intron_design.py"
    ).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
