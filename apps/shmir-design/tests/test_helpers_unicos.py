"""Un solo sitio para cada propiedad de secuencia (mejora de la revision).

Habia TRES implementaciones del mismo concepto de homopolimero: una copiada literalmente
en `blocks.py` y en `spacers.py`, y una tercera por expresion regular en `hard_filters`.
Y dos de fraccion GC, una de ellas sin validar las bases.

Eran identicas el dia que se escribieron. El problema no es hoy: es el dia en que
alguien cambie el criterio en una y las otras dos sigan diciendo lo de siempre, sin que
nada falle. Estos tests fijan que hablen igual.
"""

import unittest

from shmir_design.hard_filters import (
    MAX_HOMOPOLYMER,
    gc_fraction,
    homopolymer_pattern,
    longest_homopolymer,
)

#: Sondas de mecanismo que recorren los casos que importan.
SONDAS = (
    "ACGT",
    "AAAA",
    "AAACGT",
    "ACGTTTT",
    "GGGGCCCC",
    "ACGACGACG",
    "A",
    "TTTAGTACTGGATGGAACGGCC",
    "GCGTCAGTACGATCGAATTACT",
    "TACAATGATCCAAATCAAGA",
    "ATGGATTTGTGTAAAGATCCAGTGCCTATGTATTGTTGGAAAGTA",
)


class TestHomopolimeroUnico(unittest.TestCase):

    def test_el_helper_y_la_regex_coinciden_siempre(self):
        patron = homopolymer_pattern(MAX_HOMOPOLYMER)
        for sonda in SONDAS:
            with self.subTest(sonda=sonda):
                _, largo = longest_homopolymer(sonda)
                self.assertEqual(
                    largo > MAX_HOMOPOLYMER,
                    bool(patron.search(sonda)),
                    f"{sonda}: el helper dice {largo} y la regex dice otra cosa",
                )

    def test_coinciden_para_cualquier_umbral(self):
        for umbral in range(1, 6):
            patron = homopolymer_pattern(umbral)
            for sonda in SONDAS:
                with self.subTest(umbral=umbral, sonda=sonda):
                    _, largo = longest_homopolymer(sonda)
                    self.assertEqual(largo > umbral, bool(patron.search(sonda)))

    def test_devuelve_la_base_y_la_longitud(self):
        self.assertEqual(longest_homopolymer("ACGGGGT"), ("G", 4))

    def test_una_secuencia_vacia_no_revienta(self):
        self.assertEqual(longest_homopolymer(""), ("", 0))

    def test_blocks_y_spacers_usan_EL_MISMO_helper(self):
        """Si alguien vuelve a copiarlo, este test lo caza."""
        from shmir_design import blocks, spacers

        self.assertIs(blocks._longest_homopolymer, longest_homopolymer)
        self.assertIs(spacers._longest_homopolymer, longest_homopolymer)


class TestGCUnico(unittest.TestCase):

    def test_spacers_usa_el_gc_de_hard_filters(self):
        from shmir_design import spacers

        self.assertIs(spacers.gc_fraction, gc_fraction)

    def test_el_GC_es_el_esperado(self):
        self.assertAlmostEqual(gc_fraction("GCAT"), 0.5)
        self.assertAlmostEqual(gc_fraction("AAAA"), 0.0)
        self.assertAlmostEqual(gc_fraction("GGCC"), 1.0)

    def test_valida_las_bases_en_vez_de_contar_lo_que_sea(self):
        """La version que habia en spacers no validaba: una X contaba como no-GC."""
        from shmir_design.errors import InvalidSequenceError

        with self.assertRaises(InvalidSequenceError):
            gc_fraction("GCXT")


if __name__ == "__main__":
    unittest.main()
