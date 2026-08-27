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

    def test_y_los_espaciadores_SOLO_si_el_corte_quedo_resuelto(self):
        # Con el corte sin decidir NO se pasa al segundo paso, y eso es correcto: unos
        # espaciadores elegidos sobre un andamio que aún no está decidido no valen para
        # el andamio que salga. Lo que no vale es callarlo.
        if self.variante.break_choice.chosen is None:
            self.assertIsNone(self.variante.spacer_search)
            self.assertIn("no se pasa al segundo", self.variante.reason)
        else:
            self.assertIsNotNone(self.variante.spacer_search)

    def test_el_estado_es_PASS_solo_si_las_DOS_se_resolvieron(self):
        resuelta = (
            self.variante.break_choice.chosen is not None
            and self.variante.spacer_search.choice is not None
        )
        self.assertIs(
            self.variante.state,
            FilterState.PASS if resuelta else FilterState.NOT_RUN,
        )

    def test_si_el_corte_EMPATA_no_se_elige_y_SALEN_TODAS(self):
        if self.variante.break_choice.tied:
            self.assertIsNone(self.variante.break_choice.chosen)
            texto = self.variante.describe_text()
            self.assertIn("EMPATAN", texto)
            for candidato in self.variante.break_choice.tied:
                self.assertIn(candidato.replacement, texto)
                self.assertIn(str(candidato.position), texto)
                # Y el motivo resultante, que es lo que hay que mirar para decidir.
                self.assertIn(candidato.motif, texto)

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
