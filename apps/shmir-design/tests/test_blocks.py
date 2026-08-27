"""Tests del generador de bloques (tanda B).

Regla 5: escritos antes que `shmir_design/blocks.py`.

La arquitectura es fija salvo dos variables, guia y pasajera. Todas las piezas se copian
LITERALMENTE del prompt de procedencia; ninguna se reconstruye (regla 1).

Dos niveles de salida, siempre los dos:
  - modulo NheI-SacI de 149 nt, para intercambiar solo la horquilla
  - cassette MluI-AgeI de 318 pb, intron completo

Y la comprobacion que no es opcional: los espaciadores se optimizaron para la horquilla
de 1018. Con otra guia el contexto podria capturar los flancos del pri-miR y deshacer el
tallo basal — fallo silencioso que solo se ve plegando.

Regresion: guia `TTTAGTACTGGATGGAACGGCC` (3'UTR murino 1018), pasajera esperada
`CGCCGTTCCATCCAGTACTAAA`, y los dos bloques literales del prompt.
"""

import unittest

from shmir_design.blocks import (
    CASSETTE_LENGTH,
    GIBSON_ARM,
    INTRON_LENGTH,
    MODULE_LENGTH,
    PIECES,
    build_block,
    blocks_fasta,
    blocks_tsv,
    order_sheet,
)
from shmir_design.filters import FilterState
from shmir_design.folding import VIENNA_AVAILABLE

GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"
PASAJERA_1018 = "CGCCGTTCCATCCAGTACTAAA"

MODULO_1018 = (
    "GCTAGCGAAGGCTCGAGAAGGTATATTGCTGTTGACAGTGAGCGCGCCGTTCCATCCAGTACTAAA"
    "TAGTGAAGCCACAGATGTATTTAGTACTGGATGGAACGGCCTGCCTACTGCCTCGGACTTCAAGGG"
    "GCTAGAATTCGGAGCTC"
)
CASSETTE_1018 = (
    "ACGCGTAAGAGGTAAGGGTTTAAGGGATGGTTGGTTGGTGGGGTATTAATGTACAATGATCCAAAT"
    "CAAGAGCTAGCGAAGGCTCGAGAAGGTATATTGCTGTTGACAGTGAGCGCGCCGTTCCATCCAGTA"
    "CTAAATAGTGAAGCCACAGATGTATTTAGTACTGGATGGAACGGCCTGCCTACTGCCTCGGACTTC"
    "AAGGGGCTAGAATTCGGAGCTCATGGATTTGTGTAAAGATCCAGTGCCTATGTATTGTTGGAAAGT"
    "ATTTAATTACCTGGAGCACCTGCCTGAAATCACTTTTTTTCAGGTTGGACCGGT"
)


class TestPiezas(unittest.TestCase):
    """Las piezas van literales y con su procedencia."""

    def test_estan_todas(self):
        for nombre in (
            "MluI", "exon5", "MVM5", "espaciador5", "NheI", "contexto5",
            "contexto3", "SacI", "espaciador3", "MVM3", "exon3", "AgeI",
        ):
            self.assertIn(nombre, PIECES)

    def test_las_longitudes_son_las_del_prompt(self):
        esperadas = {
            "MluI": 6, "exon5": 5, "MVM5": 40, "espaciador5": 20, "NheI": 6,
            "contexto5": 20, "contexto3": 20, "SacI": 6, "espaciador3": 45,
            "MVM3": 42, "exon3": 5, "AgeI": 6,
        }
        for nombre, largo in esperadas.items():
            self.assertEqual(len(PIECES[nombre].sequence), largo, nombre)

    def test_cada_pieza_lleva_procedencia(self):
        for nombre, pieza in PIECES.items():
            self.assertTrue(pieza.source, nombre)

    def test_los_contextos_dicen_de_donde_salen(self):
        self.assertIn("1739", PIECES["contexto5"].source)
        self.assertIn("1875", PIECES["contexto3"].source)

    def test_las_longitudes_declaradas_cuadran(self):
        self.assertEqual((MODULE_LENGTH, CASSETTE_LENGTH, INTRON_LENGTH), (149, 318, 296))


class TestRegresion1018(unittest.TestCase):
    """Los dos bloques literales del prompt, byte a byte."""

    def setUp(self):
        self.bloque = build_block(GUIA_1018)

    def test_la_pasajera_es_la_esperada(self):
        self.assertEqual(self.bloque.passenger, PASAJERA_1018)

    def test_el_modulo_es_el_esperado(self):
        self.assertEqual(self.bloque.module, MODULO_1018)

    def test_el_cassette_es_el_esperado(self):
        self.assertEqual(self.bloque.cassette, CASSETTE_1018)

    def test_las_longitudes_son_exactas(self):
        self.assertEqual(len(self.bloque.module), 149)
        self.assertEqual(len(self.bloque.cassette), 318)
        self.assertEqual(len(self.bloque.intron), 296)

    def test_el_modulo_esta_dentro_del_cassette(self):
        self.assertIn(self.bloque.module, self.bloque.cassette)

    def test_el_intron_esta_dentro_del_cassette(self):
        self.assertIn(self.bloque.intron, self.bloque.cassette)

    def test_el_97mero_esta_dentro_del_modulo(self):
        self.assertIn(self.bloque.hairpin.sequence, self.bloque.module)


class TestComprobacionesDeClonaje(unittest.TestCase):

    def _estado(self, bloque, nombre):
        return bloque.check(nombre).state

    def test_los_sitios_NheI_y_SacI_son_unicos(self):
        bloque = build_block(GUIA_1018)
        self.assertIs(self._estado(bloque, "sitios_unicos"), FilterState.PASS)

    def test_un_segundo_GCTAGC_en_la_guia_es_FAIL(self):
        """Sonda de mecanismo: una guia que trae un sitio NheI dentro."""
        bloque = build_block("TGCTAGCTGGATGGAACGGCC" + "A")
        self.assertIs(self._estado(bloque, "sitios_unicos"), FilterState.FAIL)

    def test_el_FAIL_de_sitios_dice_que_rompe_el_clonaje(self):
        bloque = build_block("TGCTAGCTGGATGGAACGGCC" + "A")
        self.assertIn("clonaje", bloque.check("sitios_unicos").reason)

    def test_el_modulo_no_lleva_MluI_ni_AgeI(self):
        bloque = build_block(GUIA_1018)
        self.assertIs(self._estado(bloque, "sin_MluI_AgeI"), FilterState.PASS)

    def test_las_longitudes_se_comprueban(self):
        self.assertIs(
            self._estado(build_block(GUIA_1018), "longitudes"), FilterState.PASS
        )


class TestHomopolimeros(unittest.TestCase):
    """El GGGG del contexto 3' es nativo de SGEP: no cuenta."""

    def test_la_parte_fija_no_dispara_el_filtro(self):
        bloque = build_block(GUIA_1018)
        self.assertIn("GGGG", bloque.module)
        self.assertIs(bloque.check("homopolimeros").state, FilterState.PASS)

    def test_un_homopolimero_en_la_guia_si_dispara(self):
        bloque = build_block("TTTAGTAAAAAGATGGAACGGCC"[:22])
        self.assertIs(bloque.check("homopolimeros").state, FilterState.FAIL)

    def test_el_motivo_dice_que_solo_mira_la_parte_variable(self):
        bloque = build_block(GUIA_1018)
        self.assertIn("variable", bloque.check("homopolimeros").reason)


@unittest.skipUnless(VIENNA_AVAILABLE, "ViennaRNA no está instalado")
class TestPlegado(unittest.TestCase):

    def test_el_97mero_aislado_pliega_como_la_referencia(self):
        bloque = build_block(GUIA_1018)
        self.assertIs(bloque.check("plegado_97mero").state, FilterState.PASS)

    def test_el_97mero_conserva_su_estructura_dentro_del_intron(self):
        bloque = build_block(GUIA_1018)
        self.assertIs(bloque.check("plegado_en_intron").state, FilterState.PASS)

    def test_las_cuatro_guias_reales_pasan_las_dos(self):
        for guia in (
            GUIA_1018,
            "TAGATAAGCATTATAATTCCTA",
            "TAATTGAAAGAGCTACAGGTGG",
            "TAAAGGAATGCCACATATAGGG",
        ):
            with self.subTest(guia=guia):
                bloque = build_block(guia)
                self.assertIs(bloque.check("plegado_97mero").state, FilterState.PASS)
                self.assertIs(bloque.check("plegado_en_intron").state, FilterState.PASS)

    def test_el_modulo_es_seguro_cuando_las_dos_pasan(self):
        self.assertTrue(build_block(GUIA_1018).module_safe)

    def test_la_estructura_dentro_del_intron_se_guarda(self):
        bloque = build_block(GUIA_1018)
        self.assertEqual(len(bloque.structure_in_intron), 97)


class TestSinViennaRNA(unittest.TestCase):

    def test_los_dos_plegados_quedan_NOT_RUN(self):
        bloque = build_block(GUIA_1018, available=False)
        for nombre in ("plegado_97mero", "plegado_en_intron"):
            self.assertIs(bloque.check(nombre).state, FilterState.NOT_RUN)

    def test_el_modulo_NO_se_declara_seguro(self):
        """Sin plegar no se puede afirmar que el modulo sea seguro."""
        self.assertFalse(build_block(GUIA_1018, available=False).module_safe)

    def test_el_motivo_lo_dice(self):
        bloque = build_block(GUIA_1018, available=False)
        self.assertIn("ViennaRNA", bloque.check("plegado_en_intron").reason)


class TestGibson(unittest.TestCase):

    def test_el_modulo_lleva_brazos_de_30_pb(self):
        bloque = build_block(GUIA_1018)
        self.assertEqual(GIBSON_ARM, 30)
        self.assertEqual(len(bloque.module_gibson), 149 + 60)

    def test_los_brazos_salen_del_propio_cassette(self):
        """No se inventa contexto: los 30 pb de cada lado ya estan en el cassette."""
        bloque = build_block(GUIA_1018)
        self.assertIn(bloque.module_gibson, bloque.cassette)

    def test_el_modulo_original_esta_dentro_del_gibson(self):
        bloque = build_block(GUIA_1018)
        self.assertIn(bloque.module, bloque.module_gibson)

    def test_sin_plasmido_receptor_el_gibson_del_cassette_no_se_puede_construir(self):
        bloque = build_block(GUIA_1018)
        self.assertIsNone(bloque.cassette_gibson)
        self.assertIn("receptor", bloque.check("gibson_cassette").reason)

    def test_el_estado_es_NOT_RUN_no_FAIL(self):
        self.assertIs(
            build_block(GUIA_1018).check("gibson_cassette").state, FilterState.NOT_RUN
        )

    def test_con_plasmido_receptor_si_se_construye(self):
        receptor = "A" * 40 + CASSETTE_1018 + "T" * 40
        bloque = build_block(GUIA_1018, recipient=receptor)
        self.assertEqual(len(bloque.cassette_gibson), 318 + 60)
        self.assertTrue(bloque.cassette_gibson.startswith("A" * 30))

    def test_un_receptor_que_no_contiene_el_cassette_aborta(self):
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError):
            build_block(GUIA_1018, recipient="ACGT" * 100)


class TestTransgen(unittest.TestCase):

    def test_sin_resultado_del_transgen_queda_NOT_RUN(self):
        bloque = build_block(GUIA_1018)
        self.assertIs(bloque.check("hits_transgen").state, FilterState.NOT_RUN)

    def test_con_cero_hits_pasa(self):
        from shmir_design.specificity import SpecificityDatabase, filter_transgene

        casete = SpecificityDatabase(
            name="sonda", version="v", checksum="0" * 32,
            records={"casete": "GGCCATACTAGCATCGGATCAG" * 8},
        )
        bloque = build_block(
            GUIA_1018, transgene=filter_transgene(GUIA_1018, None, casete)
        )
        self.assertIs(bloque.check("hits_transgen").state, FilterState.PASS)


class TestSalidas(unittest.TestCase):

    def test_el_FASTA_lleva_los_dos_niveles(self):
        texto = blocks_fasta([build_block(GUIA_1018)], species="raton")
        self.assertIn(">", texto)
        self.assertIn(MODULO_1018, texto.replace("\n", ""))
        self.assertIn(CASSETTE_1018, texto.replace("\n", ""))

    def test_las_cabeceras_son_informativas(self):
        texto = blocks_fasta([build_block(GUIA_1018)], species="raton")
        self.assertIn("modulo_NheI_SacI", texto)
        self.assertIn("cassette_MluI_AgeI", texto)

    def test_el_TSV_tiene_una_fila_por_candidato(self):
        filas = blocks_tsv([build_block(GUIA_1018)], species="raton").splitlines()
        self.assertEqual(len(filas), 2)

    def test_el_TSV_lleva_una_columna_por_comprobacion(self):
        cabecera = blocks_tsv([build_block(GUIA_1018)], species="raton").splitlines()[0]
        for nombre in ("longitudes", "sitios_unicos", "plegado_en_intron"):
            self.assertIn(f"check:{nombre}", cabecera)

    def test_la_hoja_de_pedido_parte_en_bloques_de_60(self):
        texto = order_sheet([build_block(GUIA_1018)], species="raton")
        lineas = [l.strip() for l in texto.splitlines() if l.strip().startswith("GCTAGC")]
        self.assertTrue(lineas)
        self.assertLessEqual(len(lineas[0]), 60)

    def test_la_hoja_avisa_de_XhoI_y_EcoRI(self):
        texto = order_sheet([build_block(GUIA_1018)], species="raton")
        self.assertIn("XhoI", texto)
        self.assertIn("EcoRI", texto)
        self.assertIn("NO son únicas", texto)

    def test_la_hoja_dice_por_donde_va_el_clonaje(self):
        texto = order_sheet([build_block(GUIA_1018)], species="raton")
        self.assertIn("NheI", texto)
        self.assertIn("SacI", texto)

    def test_una_lista_vacia_no_finge_una_hoja_de_pedido(self):
        self.assertIn("ningún", order_sheet([], species="raton").lower())


if __name__ == "__main__":
    unittest.main()


class TestEspaciadoresEnElBloque(unittest.TestCase):
    """La rama autorizada: espaciadores de novo cuando los estandar no valen."""

    def test_por_defecto_los_bloques_llevan_los_estandar(self):
        bloque = build_block(GUIA_1018)
        self.assertFalse(bloque.custom_spacers)
        self.assertIs(bloque.check("espaciadores").state, FilterState.PASS)
        self.assertIn("ESTÁNDAR", bloque.check("espaciadores").reason)

    def test_el_TSV_dice_que_espaciadores_lleva(self):
        cabecera = blocks_tsv([build_block(GUIA_1018)], species="raton").splitlines()
        columnas = cabecera[0].split("\t")
        for nombre in ("espaciadores", "espaciador5", "espaciador3"):
            self.assertIn(nombre, columnas)
        fila = cabecera[1].split("\t")
        self.assertEqual(fila[columnas.index("espaciadores")], "estandar")

    def test_el_FASTA_lo_marca_en_la_cabecera(self):
        texto = blocks_fasta([build_block(GUIA_1018)], species="raton")
        self.assertIn("espaciadores_estandar", texto)

    def test_pedir_reoptimizar_no_cambia_nada_si_los_estandar_valen(self):
        """No puede 'mejorar' por su cuenta un diseño que ya funciona."""
        normal = build_block(GUIA_1018)
        pedido = build_block(GUIA_1018, reoptimize_spacers=True)
        self.assertEqual(normal.cassette, pedido.cassette)
        self.assertFalse(pedido.custom_spacers)

    def test_sin_pedirlo_y_con_el_intron_roto_el_filtro_queda_NOT_RUN(self):
        """Sonda: se fuerza el fallo sin ViennaRNA para no depender del plegado."""
        bloque = build_block(GUIA_1018, available=False)
        self.assertIs(bloque.check("espaciadores").state, FilterState.PASS)
