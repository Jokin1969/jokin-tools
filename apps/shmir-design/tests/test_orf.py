"""Tests del proponedor de ORF (bloque 7, via 3).

Regla 5: escritos antes que `shmir_design/orf.py`.

La regla de este modulo: PROPONE y NUNCA DECIDE. No hay ninguna funcion que devuelva
una `Anatomy`; lo unico que sale de aqui es una propuesta y el texto del comando
`--cds INICIO FIN` para que lo pegue una persona. Elegir mal la isoforma corre todas
las coordenadas sin que nada avise, asi que la frontera la fija quien sabe, no el codigo.

Las sondas de este fichero son eso, SONDAS de mecanismo (marcos de lectura de juguete),
no secuencias biologicas presentadas como dato. La comprobacion contra biologia real es
`test_propone_el_CDS_real_del_raton`, que corre solo si esta el fixture verificado.
"""

import unittest

from shmir_design.orf import Orf, format_cds_suggestion, find_orfs, propose_cds
from shmir_design.reference import REFERENCES, fixture_available, load_reference

# Sonda: 4 nt, ORF de 15 nt (ATG + 3 codones + TAA), 11 nt detras.
SONDA = "AAAA" + "ATGGCTAACGGGTAA" + "GGGGGGGGGGG"


class TestBusqueda(unittest.TestCase):

    def test_encuentra_el_marco_de_la_sonda(self):
        orfs = find_orfs(SONDA, min_codons=2)
        self.assertIn((5, 19), [(o.start, o.end) for o in orfs])

    def test_el_ORF_incluye_el_codon_de_parada(self):
        orf = [o for o in find_orfs(SONDA, min_codons=2) if o.start == 5][0]
        self.assertEqual(SONDA[orf.start - 1 : orf.start + 2], "ATG")
        self.assertEqual(SONDA[orf.end - 3 : orf.end], "TAA")

    def test_la_longitud_de_todo_ORF_es_multiplo_de_3(self):
        for orf in find_orfs(SONDA, min_codons=2):
            self.assertEqual((orf.end - orf.start + 1) % 3, 0)

    def test_un_ORF_sin_parada_no_cuenta(self):
        self.assertEqual(find_orfs("ATGGCTAACGGG", min_codons=2), ())

    def test_min_codons_descarta_los_cortos(self):
        self.assertEqual(find_orfs(SONDA, min_codons=100), ())

    def test_busca_en_los_tres_marcos(self):
        orfs = find_orfs("G" + SONDA, min_codons=2)
        self.assertIn((6, 20), [(o.start, o.end) for o in orfs])

    def test_no_busca_en_la_hebra_complementaria(self):
        """Un mRNA es de una sola hebra: buscar en la otra solo produce ruido."""
        self.assertEqual(find_orfs("TTACCCGTTAGCCAT", min_codons=2), ())

    def test_una_secuencia_con_N_no_produce_un_ORF_que_la_pise(self):
        for orf in find_orfs("AAAAATGGCTNACGGGTAAGG", min_codons=2):
            self.assertNotIn("N", "AAAAATGGCTNACGGGTAAGG"[orf.start - 1 : orf.end])


class TestPropuesta(unittest.TestCase):

    def test_propone_el_ORF_mas_largo(self):
        propuesta = propose_cds(SONDA, min_codons=2)
        self.assertEqual((propuesta.start, propuesta.end), (5, 19))

    def test_es_un_Orf(self):
        self.assertIsInstance(propose_cds(SONDA, min_codons=2), Orf)

    def test_sin_ningun_ORF_devuelve_None_en_vez_de_inventarse_uno(self):
        self.assertIsNone(propose_cds("GGGGGGGGGGGG", min_codons=2))

    def test_la_propuesta_no_construye_una_anatomia(self):
        """Regla del modulo: no hay puente de orf.py a Anatomy."""
        import shmir_design.orf as orf_mod

        fuente = __import__("inspect").getsource(orf_mod)
        self.assertNotIn("Anatomy", fuente)
        self.assertNotIn("from .anatomy", fuente)

    def test_el_texto_sugiere_el_comando_para_pegar(self):
        texto = format_cds_suggestion(propose_cds(SONDA, min_codons=2))
        self.assertIn("--cds 5 19", texto)

    def test_el_texto_deja_claro_que_es_una_propuesta_sin_confirmar(self):
        texto = format_cds_suggestion(propose_cds(SONDA, min_codons=2)).lower()
        self.assertIn("propuesta", texto)
        self.assertIn("no confirmada", texto)

    def test_sin_propuesta_el_texto_lo_dice_y_no_sugiere_coordenadas(self):
        texto = format_cds_suggestion(None)
        self.assertNotIn("--cds ", texto)
        self.assertIn("no", texto.lower())

    def test_avisa_de_cuantos_marcos_alternativos_hay(self):
        texto = format_cds_suggestion(propose_cds(SONDA, min_codons=2), alternatives=3)
        self.assertIn("3", texto)


class TestContraBiologiaReal(unittest.TestCase):

    @unittest.skipUnless(
        fixture_available(REFERENCES["NM_011170.3"]),
        "falta el fixture de NM_011170.3; el chequeo contra el CDS real no corre",
    )
    def test_propone_el_CDS_real_del_raton(self):
        """El ORF mas largo de NM_011170.3 debe ser el CDS anotado, 185..949."""
        secuencia = load_reference(REFERENCES["NM_011170.3"])
        propuesta = propose_cds(secuencia)
        self.assertIsNotNone(propuesta)
        self.assertEqual((propuesta.start, propuesta.end), (185, 949))


if __name__ == "__main__":
    unittest.main()
