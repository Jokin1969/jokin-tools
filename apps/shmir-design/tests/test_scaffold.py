"""Tests del andamio miR-E (montaje de la horquilla de 97 nt).

Regla 5: escritos antes que `shmir_design/scaffold.py`.

Datos reales: el andamio SGEP (Addgene #111170), verificado por el responsable contra el
fichero SnapGene de la secuencia depositada y coincidente con tres fuentes. La horquilla
de referencia y sus 97 nt son dato verificado.

La regla de la pasajera (transicion en la posicion 1) esta derivada de UN SOLO ejemplo:
`scaffold.py` la marca como REGLA_NO_CONFIRMADA y estos tests fijan que el aviso salga
siempre, tambien en la salida de oligos.
"""

import inspect
import tempfile
import unittest
from pathlib import Path

from shmir_design.errors import InvalidSequenceError
from shmir_design.scaffold import (
    EXTENDED_FLANKS_STATUS,
    SGEP_SCAFFOLD,
    UNVERIFIED_TAG,
    ScaffoldSpec,
    load_scaffold,
    PASSENGER_RULE_CONFIRMED,
    PASSENGER_RULE_TAG,
    SCAFFOLD,
    Hairpin,
    build_hairpin,
    extended_cassette,
    passenger_from_guide,
)

GUIA_REF = "TAGATAAGCATTATAATTCCTA"
PASAJERA_REF = "CAGGAATTATAATGCTTATCTA"
HORQUILLA_REF = (
    "TGCTGTTGACAGTGAGCG"
    "CAGGAATTATAATGCTTATCTA"
    "TAGTGAAGCCACAGATGTA"
    "TAGATAAGCATTATAATTCCTA"
    "TGCCTACTGCCTCGGA"
)


class TestAndamio(unittest.TestCase):

    def test_las_tres_piezas_verificadas(self):
        self.assertEqual(SCAFFOLD["flank5"], "TGCTGTTGACAGTGAGCG")
        self.assertEqual(SCAFFOLD["loop"], "TAGTGAAGCCACAGATGTA")
        self.assertEqual(SCAFFOLD["flank3"], "TGCCTACTGCCTCGGA")

    def test_longitudes(self):
        self.assertEqual(len(SCAFFOLD["flank5"]), 18)
        self.assertEqual(len(SCAFFOLD["loop"]), 19)
        self.assertEqual(len(SCAFFOLD["flank3"]), 16)
        self.assertEqual(SCAFFOLD["length"], 97)

    def test_la_guia_va_en_el_brazo_3p(self):
        self.assertEqual(SCAFFOLD["guide_arm"], "3p")

    def test_el_97_mero_esta_verificado(self):
        self.assertIs(SCAFFOLD["verified"], True)
        self.assertIn("111170", SCAFFOLD["source"])

    def test_el_andamio_no_se_puede_modificar_por_accidente(self):
        with self.assertRaises(TypeError):
            SCAFFOLD["loop"] = "otra cosa"


class TestPasajera(unittest.TestCase):

    def test_la_pasajera_de_referencia(self):
        pasajera = passenger_from_guide(GUIA_REF)
        self.assertEqual(pasajera.sequence, PASAJERA_REF)

    def test_solo_cambia_la_posicion_1(self):
        pasajera = passenger_from_guide(GUIA_REF)
        self.assertEqual(pasajera.sequence[1:], pasajera.reverse_complement[1:])
        self.assertNotEqual(pasajera.sequence[0], pasajera.reverse_complement[0])

    def test_transicion_T_a_C(self):
        pasajera = passenger_from_guide(GUIA_REF)
        self.assertEqual((pasajera.base_original, pasajera.base_final), ("T", "C"))
        self.assertTrue(pasajera.transition_applied)

    def test_transicion_C_a_T(self):
        """Una guia acabada en G da un revcomp que empieza por C."""
        guia = "TAGATAAGCATTATAATTCCTG"
        pasajera = passenger_from_guide(guia)
        self.assertEqual(pasajera.reverse_complement[0], "C")
        self.assertEqual(pasajera.sequence[0], "T")
        self.assertTrue(pasajera.transition_applied)

    def test_si_es_A_no_se_toca_pero_se_avisa(self):
        guia = "TAGATAAGCATTATAATTCCTT"   # revcomp empieza por A
        pasajera = passenger_from_guide(guia)
        self.assertEqual(pasajera.reverse_complement[0], "A")
        self.assertEqual(pasajera.sequence, pasajera.reverse_complement)
        self.assertFalse(pasajera.transition_applied)
        self.assertTrue(any("A" in w and "transicion" in w.lower() for w in pasajera.warnings))

    def test_si_es_G_no_se_toca_pero_se_avisa(self):
        guia = "TAGATAAGCATTATAATTCCTC"   # revcomp empieza por G
        pasajera = passenger_from_guide(guia)
        self.assertEqual(pasajera.reverse_complement[0], "G")
        self.assertFalse(pasajera.transition_applied)
        self.assertTrue(pasajera.warnings)

    def test_la_regla_va_marcada_como_no_confirmada(self):
        self.assertFalse(PASSENGER_RULE_CONFIRMED)
        self.assertEqual(PASSENGER_RULE_TAG, "REGLA_NO_CONFIRMADA")
        avisos = " ".join(passenger_from_guide(GUIA_REF).warnings)
        self.assertIn(PASSENGER_RULE_TAG, avisos)
        self.assertIn("111177", avisos)

    def test_acepta_la_guia_en_ARN(self):
        rna = GUIA_REF.replace("T", "U")
        self.assertEqual(passenger_from_guide(rna).sequence, PASAJERA_REF)

    def test_una_guia_de_otra_longitud_es_error(self):
        with self.assertRaises(ValueError):
            passenger_from_guide(GUIA_REF[:21])

    def test_una_guia_con_N_es_error(self):
        with self.assertRaises(InvalidSequenceError):
            passenger_from_guide("N" + GUIA_REF[1:])


class TestHorquilla(unittest.TestCase):

    def test_la_horquilla_de_referencia(self):
        hairpin = build_hairpin(GUIA_REF)
        self.assertEqual(hairpin.sequence, HORQUILLA_REF)
        self.assertEqual(len(hairpin.sequence), 97)

    def test_las_piezas_caen_donde_toca(self):
        hairpin = build_hairpin(GUIA_REF)
        self.assertTrue(hairpin.sequence.startswith(SCAFFOLD["flank5"]))
        self.assertTrue(hairpin.sequence.endswith(SCAFFOLD["flank3"]))
        self.assertEqual(hairpin.sequence[18:40], PASAJERA_REF)
        self.assertEqual(hairpin.sequence[40:59], SCAFFOLD["loop"])
        self.assertEqual(hairpin.sequence[59:81], GUIA_REF)

    def test_la_salida_de_oligos_lleva_el_aviso(self):
        texto = build_hairpin(GUIA_REF).format_text()
        self.assertIn(PASSENGER_RULE_TAG, texto)
        self.assertIn("111177", texto)
        self.assertIn(HORQUILLA_REF, texto)

    def test_la_salida_dice_que_pieza_es_cada_cosa(self):
        texto = build_hairpin(GUIA_REF).format_text()
        for pieza in ("flanco 5'", "pasajera", "loop", "guia", "flanco 3'"):
            with self.subTest(pieza):
                self.assertIn(pieza, texto)

    def test_una_guia_con_N_no_se_convierte_en_oligo(self):
        with self.assertRaises(InvalidSequenceError):
            build_hairpin("N" + GUIA_REF[1:])


class TestFlancosExtendidos(unittest.TestCase):
    """Los flancos del pri-miR para el cassette AAV siguen sin decidir."""

    def test_el_estado_lo_dice(self):
        self.assertIn("sin decidir", EXTENDED_FLANKS_STATUS.lower())

    def test_pedirlos_aborta_en_vez_de_inventarlos(self):
        with self.assertRaises(NotImplementedError) as ctx:
            extended_cassette(GUIA_REF)
        self.assertIn("sin decidir", str(ctx.exception).lower())


class TestAndamioConfigurable(unittest.TestCase):
    """El andamio se puede parametrizar; `verificado` es False por defecto."""

    TOML = (
        'nombre = "andamio de prueba"\n'
        'flanco5 = "TGCTGTTGACAGTGAGCG"\n'
        'loop = "TAGTGAAGCCACAGATGTA"\n'
        'flanco3 = "TGCCTACTGCCTCGGA"\n'
    )

    def escribir(self, texto, nombre="andamio.toml"):
        directorio = tempfile.mkdtemp()
        ruta = Path(directorio) / nombre
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    def test_verificado_es_False_por_defecto(self):
        andamio = load_scaffold(self.escribir(self.TOML))
        self.assertFalse(andamio.verified)

    def test_verificado_se_puede_declarar_en_el_fichero(self):
        andamio = load_scaffold(self.escribir(self.TOML + "verificado = true\n"))
        self.assertTrue(andamio.verified)

    def test_falta_una_pieza_y_aborta(self):
        sin_loop = 'nombre = "x"\nflanco5 = "ACGT"\nflanco3 = "ACGT"\n'
        with self.assertRaises(ValueError) as ctx:
            load_scaffold(self.escribir(sin_loop))
        self.assertIn("loop", str(ctx.exception))

    def test_una_clave_desconocida_aborta(self):
        with self.assertRaises(ValueError) as ctx:
            load_scaffold(self.escribir(self.TOML + 'flanco4 = "ACGT"\n'))
        self.assertIn("flanco4", str(ctx.exception))

    def test_una_base_invalida_aborta(self):
        malo = self.TOML.replace('loop = "TAGTGAAGCCACAGATGTA"', 'loop = "TAGTXAAGC"')
        with self.assertRaises(InvalidSequenceError):
            load_scaffold(self.escribir(malo))

    def test_un_fichero_que_no_existe_aborta(self):
        with self.assertRaises(FileNotFoundError):
            load_scaffold(Path("/no/existe/andamio.toml"))


class TestAvisoDeAndamioNoVerificado(unittest.TestCase):
    """Si `verificado` es False, el aviso sale en TODA salida de oligos."""

    def andamio(self):
        return ScaffoldSpec(
            name="andamio sin contrastar",
            flank5="TGCTGTTGACAGTGAGCG",
            loop="TAGTGAAGCCACAGATGTA",
            flank3="TGCCTACTGCCTCGGA",
        )

    def test_por_defecto_un_andamio_nuevo_no_esta_verificado(self):
        self.assertFalse(self.andamio().verified)

    def test_el_aviso_esta_en_los_warnings(self):
        hairpin = build_hairpin(GUIA_REF, scaffold=self.andamio())
        self.assertTrue(any(UNVERIFIED_TAG in w for w in hairpin.warnings))
        self.assertTrue(any("publicacion original" in w.lower() for w in hairpin.warnings))

    def test_el_aviso_sale_en_la_salida_de_texto(self):
        texto = build_hairpin(GUIA_REF, scaffold=self.andamio()).format_text()
        self.assertIn(UNVERIFIED_TAG, texto)

    def test_el_andamio_verificado_no_lleva_ese_aviso(self):
        hairpin = build_hairpin(GUIA_REF, scaffold=SGEP_SCAFFOLD)
        self.assertFalse(any(UNVERIFIED_TAG in w for w in hairpin.warnings))

    def test_no_hay_manera_de_silenciarlo(self):
        """Ni parametro para callarlo, ni formateador que lo omita."""
        parametros = set(inspect.signature(build_hairpin).parameters)
        self.assertEqual(parametros, {"guide", "scaffold"})
        parametros_texto = set(inspect.signature(Hairpin.format_text).parameters)
        self.assertEqual(parametros_texto, {"self"})

    def test_un_andamio_con_otras_piezas_da_otra_longitud(self):
        andamio = ScaffoldSpec(
            name="corto", flank5="ACGT", loop="TAGTGAAGCCACAGATGTA", flank3="ACGT"
        )
        hairpin = build_hairpin(GUIA_REF, scaffold=andamio)
        self.assertEqual(len(hairpin.sequence), 4 + 22 + 19 + 22 + 4)


if __name__ == "__main__":
    unittest.main()
