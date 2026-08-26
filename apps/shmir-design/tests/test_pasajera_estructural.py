"""Tests del criterio ESTRUCTURAL para la posicion 1 de la pasajera (tanda A).

Regla 5: escritos antes de sustituir la tabla.

Que estaba mal: la regla anterior era una tabla por terminacion (C por defecto, A cuando
la C era la prohibida por Watson-Crick). Le faltaba el apareamiento tambaleante — **G:U
aparea en ARN** — asi que con guia acabada en G la T tambien esta prohibida, y la A que
elegia la tabla no aparea con nada pero deja un bulge de 2 nt en vez de 1.

Comprobado plegando: con `TAATTGAAAGAGCTACAGGTGG` y `TAAAGGAATGCCACATATAGGG`, solo la G
reproduce la estructura de SGEP.

El criterio nuevo no enumera restricciones: pliega las cuatro y se queda con una que
reproduzca la notacion punto-parentesis de la referencia. Eso subsume Watson-Crick y
wobble sin haberlos previsto, que es justo lo que le faltaba a la tabla.

Datos reales: horquilla shRen.713 del plasmido SGEP (Addgene #111170) y cuatro guias del
proyecto.
"""

import unittest
from dataclasses import replace

from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.folding import (
    VIENNA_AVAILABLE,
    dot_bracket,
    reference_structure,
)
from shmir_design.scaffold import (
    MISMATCH_PREFERENCE,
    REFERENCE_GUIDE,
    REFERENCE_HAIRPIN,
    SGEP_SCAFFOLD,
    build_hairpin,
    passenger_from_guide,
)

#: Guia de SGEP y su pasajera REAL, la del plasmido.
PASAJERA_SGEP = "CAGGAATTATAATGCTTATCTA"

#: Guias del proyecto que acaban en G: el caso que la tabla fallaba.
GUIA_G1 = "TAATTGAAAGAGCTACAGGTGG"
GUIA_G2 = "TAAAGGAATGCCACATATAGGG"
#: Guia del 3'UTR murino 1018.
GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"

REALES = (REFERENCE_GUIDE, GUIA_G1, GUIA_G2, GUIA_1018)


class TestPreferencia(unittest.TestCase):

    def test_el_orden_es_C_A_G_T(self):
        self.assertEqual(MISMATCH_PREFERENCE, ("C", "A", "G", "T"))

    def test_no_queda_ninguna_tabla_por_terminacion(self):
        """La tabla es exactamente lo que fallo; no puede seguir en el modulo."""
        import inspect

        import shmir_design.scaffold as modulo

        fuente = inspect.getsource(modulo)
        self.assertNotIn("DEFAULT_MISMATCH_BASE", fuente)
        self.assertNotIn("FALLBACK_MISMATCH_BASE", fuente)


@unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no esta instalado")
class TestCriterioEstructural(unittest.TestCase):

    def test_la_guia_de_SGEP_da_la_pasajera_real_del_plasmido(self):
        self.assertEqual(passenger_from_guide(REFERENCE_GUIDE).sequence, PASAJERA_SGEP)

    def test_una_guia_acabada_en_G_empieza_por_G_no_por_A(self):
        for guia in (GUIA_G1, GUIA_G2):
            with self.subTest(guia=guia):
                self.assertEqual(passenger_from_guide(guia).chosen_base, "G")

    def test_la_regla_vieja_habria_elegido_A_en_esos_casos(self):
        """Deja constancia de la diferencia: no es un cambio cosmetico."""
        from shmir_design.scaffold import reverse_complement

        for guia in (GUIA_G1, GUIA_G2):
            self.assertEqual(reverse_complement(guia)[0], "C")  # C prohibida por WC
            self.assertNotEqual(passenger_from_guide(guia).chosen_base, "A")

    def test_una_guia_acabada_en_C_sigue_dando_C(self):
        self.assertEqual(passenger_from_guide(GUIA_1018).chosen_base, "C")

    def test_las_guias_reales_pliegan_identico_a_la_referencia(self):
        referencia = reference_structure(REFERENCE_HAIRPIN)
        for guia in REALES:
            with self.subTest(guia=guia):
                horquilla = build_hairpin(guia, scaffold=SGEP_SCAFFOLD)
                self.assertEqual(dot_bracket(horquilla.sequence)[0], referencia)

    def test_el_resto_de_la_pasajera_sigue_siendo_el_revcomp(self):
        from shmir_design.scaffold import reverse_complement

        for guia in REALES:
            pasajera = passenger_from_guide(guia)
            self.assertEqual(pasajera.sequence[1:], reverse_complement(guia)[1:])

    def test_la_base_elegida_nunca_es_la_prohibida_por_Watson_Crick(self):
        for guia in REALES:
            pasajera = passenger_from_guide(guia)
            self.assertNotEqual(pasajera.chosen_base, pasajera.forbidden_base)

    def test_la_base_elegida_nunca_es_la_prohibida_por_wobble(self):
        """G:U aparea. Si la guia acaba en G, la T esta prohibida; y al reves."""
        wobble = {"G": "T", "T": "G"}
        for guia in REALES:
            prohibida = wobble.get(guia[-1])
            if prohibida is not None:
                self.assertNotEqual(passenger_from_guide(guia).chosen_base, prohibida)

    def test_el_chequeo_estructural_queda_registrado_como_ejecutado(self):
        self.assertIs(
            passenger_from_guide(REFERENCE_GUIDE).structural_check, FilterState.PASS
        )

    def test_se_guardan_las_bases_que_tambien_valian(self):
        """La guia de SGEP admite C, A y G; el determinismo lo da la preferencia."""
        pasajera = passenger_from_guide(REFERENCE_GUIDE)
        self.assertEqual(set(pasajera.candidates), {"C", "A", "G"})

    def test_una_guia_acabada_en_G_solo_admite_la_G(self):
        self.assertEqual(passenger_from_guide(GUIA_G1).candidates, ("G",))


@unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no esta instalado")
class TestCuandoNingunaBaseVale(unittest.TestCase):

    #: Andamio con el loop alargado: ya no monta la arquitectura de SGEP.
    OTRO = replace(SGEP_SCAFFOLD, loop=SGEP_SCAFFOLD.loop + "GGGGGGGGG", verified=False)

    def test_si_ninguna_reproduce_la_estructura_no_se_elige_por_defecto(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            passenger_from_guide(REFERENCE_GUIDE, scaffold=self.OTRO)
        self.assertIn("ninguna", str(ctx.exception).lower())

    def test_el_error_enseña_las_cuatro_estructuras(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            passenger_from_guide(REFERENCE_GUIDE, scaffold=self.OTRO)
        mensaje = str(ctx.exception)
        for base in MISMATCH_PREFERENCE:
            self.assertIn(f"{base}:", mensaje)

    def test_el_error_enseña_tambien_la_de_referencia(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            passenger_from_guide(REFERENCE_GUIDE, scaffold=self.OTRO)
        self.assertIn("referencia", str(ctx.exception))

    def test_las_guias_del_proyecto_no_llegan_a_esta_rama(self):
        """Con el andamio de SGEP, las cuatro guias reales siempre tienen solucion."""
        for guia in REALES:
            self.assertTrue(passenger_from_guide(guia).candidates)


class TestSinViennaRNA(unittest.TestCase):
    """Sin plegado el criterio no se puede aplicar, y eso no se puede disimular."""

    def test_sin_ViennaRNA_el_chequeo_queda_NOT_RUN(self):
        pasajera = passenger_from_guide(REFERENCE_GUIDE, available=False)
        self.assertIs(pasajera.structural_check, FilterState.NOT_RUN)

    def test_se_elige_igual_pero_excluyendo_WC_y_wobble(self):
        pasajera = passenger_from_guide(GUIA_G1, available=False)
        self.assertNotIn(pasajera.chosen_base, ("C", "T"))

    def test_el_aviso_dice_que_esa_eleccion_esta_comprobada_como_incorrecta(self):
        pasajera = passenger_from_guide(GUIA_G1, available=False)
        self.assertTrue(pasajera.warnings)
        self.assertIn("ViennaRNA", " ".join(pasajera.warnings))

    def test_el_aviso_nombra_el_caso_que_falla(self):
        pasajera = passenger_from_guide(GUIA_G1, available=False)
        self.assertIn("G", " ".join(pasajera.warnings))

    def test_con_ViennaRNA_no_hay_aviso(self):
        if not VIENNA_AVAILABLE:
            self.skipTest("ViennaRNA no esta instalado")
        self.assertEqual(passenger_from_guide(REFERENCE_GUIDE).warnings, ())


if __name__ == "__main__":
    unittest.main()
