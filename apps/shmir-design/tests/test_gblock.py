"""Tests del modulo NheI–SacI de 149 nt (gBlock).

Regla 5: escritos antes que `shmir_design/gblock.py`.

El valor esperado es el modulo real que da el responsable del proyecto para la guia de
SGEP; las secuencias de contexto estan copiadas literalmente de su especificacion, no
reconstruidas.
"""

import unittest

from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.gblock import (
    AGEI_SITE,
    CONTEXT_3,
    CONTEXT_5,
    CONTEXT_POSITIONS,
    GBLOCK_LENGTH,
    MLUI_SITE,
    NHEI_SITE,
    SACI_SITE,
    build_gblock,
    verify_contexts_against_plasmid,
)
from shmir_design.scaffold import build_hairpin

GUIA_REF = "TAGATAAGCATTATAATTCCTA"
MODULO_REF = (
    "GCTAGCGAAGGCTCGAGAAGGTATATTGCTGTTGACAGTGAGCGCAGGAATTATAATGCTTATCTATAGTGAAGCC"
    "ACAGATGTATAGATAAGCATTATAATTCCTATGCCTACTGCCTCGGACTTCAAGGGGCTAGAATTCGGAGCTC"
)


class TestComposicion(unittest.TestCase):

    def test_el_modulo_de_referencia_sale_exacto(self):
        gblock = build_gblock(build_hairpin(GUIA_REF))
        self.assertEqual(gblock.sequence, MODULO_REF)
        self.assertEqual(len(gblock.sequence), 149)

    def test_las_piezas_son_las_declaradas(self):
        self.assertEqual(NHEI_SITE, "GCTAGC")
        self.assertEqual(CONTEXT_5, "GAAGGCTCGAGAAGGTATAT")
        self.assertEqual(CONTEXT_3, "CTTCAAGGGGCTAGAATTCG")
        self.assertEqual(SACI_SITE, "GAGCTC")
        self.assertEqual((len(CONTEXT_5), len(CONTEXT_3)), (20, 20))
        self.assertEqual(GBLOCK_LENGTH, 149)

    def test_el_orden_es_el_declarado(self):
        gblock = build_gblock(build_hairpin(GUIA_REF))
        self.assertTrue(gblock.sequence.startswith(NHEI_SITE + CONTEXT_5))
        self.assertTrue(gblock.sequence.endswith(CONTEXT_3 + SACI_SITE))
        self.assertIn(build_hairpin(GUIA_REF).sequence, gblock.sequence)


class TestComprobaciones(unittest.TestCase):

    def checks(self, guia):
        return {c.name: c for c in build_gblock(build_hairpin(guia)).checks}

    def test_los_cuatro_del_modulo_pasan(self):
        # Los CUATRO que se calculan sobre la secuencia. El quinto —contrastar los
        # contextos con el plásmido— depende de un fichero que no está, así que va en
        # su propio test y en `test_contextos_vs_plasmido.py`.
        gblock = build_gblock(build_hairpin(GUIA_REF))
        for check in gblock.checks:
            if check.name == "contextos_vs_plasmido":
                continue
            with self.subTest(check.name):
                self.assertIs(check.state, FilterState.PASS)

    def test_pero_el_modulo_NO_es_apto_sin_contrastar_los_contextos(self):
        # Antes esto era `assertTrue(gblock.ok)`. Cambia a propósito: un módulo cuyos
        # contextos nadie ha contrastado con el vector real no puede salir apto, y lo
        # que se pide con un apto falso es ADN. Con el plásmido delante, sí lo es.
        from tests.test_contextos_vs_plasmido import plasmido

        self.assertFalse(build_gblock(build_hairpin(GUIA_REF)).ok)
        self.assertTrue(build_gblock(build_hairpin(GUIA_REF), plasmid=plasmido()).ok)

    def test_longitud(self):
        self.assertIs(self.checks(GUIA_REF)["longitud"].state, FilterState.PASS)

    def test_un_segundo_sitio_NheI_en_la_guia_es_FAIL(self):
        """Rompería el clonaje: hay que avisar, no dejarlo pasar."""
        guia = "GCTAGCTAAGCATTATAATTC"  + "A"
        checks = self.checks(guia)
        self.assertIs(checks["sitios_unicos"].state, FilterState.FAIL)
        self.assertIn("GCTAGC", checks["sitios_unicos"].reason)
        self.assertFalse(build_gblock(build_hairpin(guia)).ok)

    def test_un_segundo_sitio_SacI_en_la_guia_es_FAIL(self):
        guia = "GAGCTCTAAGCATTATAATTC" + "A"
        self.assertIs(self.checks(guia)["sitios_unicos"].state, FilterState.FAIL)

    def test_MluI_en_la_guia_es_FAIL(self):
        guia = "ACGCGTAAGCATTATAATTCC" + "A"
        checks = self.checks(guia)
        self.assertIs(checks["sitios_intron"].state, FilterState.FAIL)
        self.assertIn(MLUI_SITE, checks["sitios_intron"].reason)

    def test_AgeI_en_la_guia_es_FAIL(self):
        guia = "ACCGGTAAGCATTATAATTCC" + "A"
        self.assertIs(self.checks(guia)["sitios_intron"].state, FilterState.FAIL)

    def test_homopolimero_en_la_parte_variable_es_FAIL(self):
        guia = "TAGATAAGCATTATAAAATCC" + "A"
        checks = self.checks(guia)
        self.assertIs(checks["homopolimero"].state, FilterState.FAIL)

    def test_el_GGGG_del_contexto_fijo_no_cuenta(self):
        """El contexto 3' de SGEP lleva GGGG por diseño: si contara, todo sería FAIL."""
        self.assertIn("GGGG", CONTEXT_3)
        self.assertIs(self.checks(GUIA_REF)["homopolimero"].state, FilterState.PASS)
        self.assertIn("contexto", self.checks(GUIA_REF)["homopolimero"].reason.lower())


class TestVerificacionContraElPlasmido(unittest.TestCase):

    def plasmido(self, ctx5=CONTEXT_5, ctx3=CONTEXT_3):
        inicio5, _ = CONTEXT_POSITIONS["contexto_5"]
        inicio3, fin3 = CONTEXT_POSITIONS["contexto_3"]
        bases = ["N"] * (fin3 + 100)
        for offset, base in enumerate(ctx5):
            bases[inicio5 - 1 + offset] = base
        for offset, base in enumerate(ctx3):
            bases[inicio3 - 1 + offset] = base
        return "".join(bases)

    def test_las_posiciones_declaradas(self):
        self.assertEqual(CONTEXT_POSITIONS["contexto_5"], (1739, 1758))
        self.assertEqual(CONTEXT_POSITIONS["contexto_3"], (1856, 1875))

    def test_un_plasmido_que_coincide_pasa(self):
        verify_contexts_against_plasmid(self.plasmido())

    def test_un_plasmido_que_no_coincide_aborta(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            verify_contexts_against_plasmid(self.plasmido(ctx5="A" * 20))
        self.assertIn("1739", str(ctx.exception))

    def test_un_plasmido_demasiado_corto_aborta(self):
        with self.assertRaises(ShmirDesignError):
            verify_contexts_against_plasmid("ACGT" * 100)


if __name__ == "__main__":
    unittest.main()
