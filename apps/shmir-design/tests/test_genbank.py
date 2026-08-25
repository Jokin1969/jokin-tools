"""Tests del lector de CDS de GenBank (bloque 7, via 1).

Regla 5: escritos antes que `shmir_design/genbank.py`.

Regla 4: no se inventa ningun endpoint. El fichero .gb lo aporta el usuario, igual que
los FASTA; aqui solo se parsea lo que ya esta en disco.

Regla 1: los registros de prueba llevan la cabecera y las features REALES de
NM_011170.3 (2191 nt, CDS 185..949) y NO llevan bloque ORIGIN. No se fabrica ni una
base: las coordenadas son metadatos, y la secuencia sigue viniendo del FASTA verificado.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design.errors import ChecksumMismatchError, ShmirDesignError
from shmir_design.genbank import GenBankCds, parse_genbank_cds, load_genbank_cds

RATON = """\
LOCUS       NM_011170               2191 bp    mRNA    linear   ROD 25-MAY-2024
DEFINITION  Mus musculus prion protein (Prnp), transcript variant 1, mRNA.
ACCESSION   NM_011170
VERSION     NM_011170.3
FEATURES             Location/Qualifiers
     source          1..2191
                     /organism="Mus musculus"
                     /mol_type="mRNA"
     gene            1..2191
                     /gene="Prnp"
     CDS             185..949
                     /gene="Prnp"
                     /codon_start=1
                     /product="major prion protein preproprotein"
                     /protein_id="NP_035300.1"
//
"""


def _sin_cds(texto: str) -> str:
    fuera, saltando = [], False
    for linea in texto.splitlines(keepends=True):
        if linea.startswith("     CDS "):
            saltando = True
            continue
        if saltando:
            if linea.startswith("     ") and linea[21:22] == "/":
                continue
            saltando = False
        fuera.append(linea)
    return "".join(fuera)


class TestParseo(unittest.TestCase):

    def test_saca_las_coordenadas_del_CDS(self):
        cds = parse_genbank_cds(RATON, source="RATON")
        self.assertEqual(cds.cds, (185, 949))

    def test_saca_la_version_y_la_longitud(self):
        cds = parse_genbank_cds(RATON, source="RATON")
        self.assertEqual(cds.accession, "NM_011170.3")
        self.assertEqual(cds.length, 2191)

    def test_saca_el_gen_y_el_organismo_para_la_procedencia(self):
        cds = parse_genbank_cds(RATON, source="RATON")
        self.assertEqual(cds.gene, "Prnp")
        self.assertEqual(cds.organism, "Mus musculus")

    def test_el_CDS_leido_es_multiplo_de_3(self):
        cds = parse_genbank_cds(RATON, source="RATON")
        self.assertEqual((cds.cds[1] - cds.cds[0] + 1) % 3, 0)

    def test_es_un_GenBankCds(self):
        self.assertIsInstance(parse_genbank_cds(RATON, source="RATON"), GenBankCds)


class TestLoQueDebeAbortar(unittest.TestCase):
    """Regla 2: cada fallo dice QUE fallo y QUE queda sin ejecutar."""

    def test_sin_feature_CDS_aborta(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_genbank_cds(_sin_cds(RATON), source="sin_cds")
        self.assertIn("CDS", str(ctx.exception))

    def test_un_CDS_parcial_aborta_en_vez_de_redondear(self):
        for parcial in ("<185..949", "185..>949", "<185..>949"):
            texto = RATON.replace("185..949", parcial)
            with self.assertRaises(ShmirDesignError) as ctx:
                parse_genbank_cds(texto, source="parcial")
            self.assertIn("parcial", str(ctx.exception).lower())

    def test_un_CDS_en_join_aborta(self):
        texto = RATON.replace("185..949", "join(185..500,600..949)")
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_genbank_cds(texto, source="join")
        self.assertIn("join", str(ctx.exception).lower())

    def test_un_CDS_en_complement_aborta(self):
        texto = RATON.replace("185..949", "complement(185..949)")
        with self.assertRaises(ShmirDesignError):
            parse_genbank_cds(texto, source="complement")

    def test_dos_features_CDS_abortan_en_vez_de_elegir_una(self):
        texto = RATON.replace(
            "     CDS             185..949\n",
            "     CDS             185..949\n     CDS             200..949\n",
        )
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_genbank_cds(texto, source="dos")
        self.assertIn("2", str(ctx.exception))

    def test_un_CDS_que_se_sale_del_LOCUS_aborta(self):
        texto = RATON.replace("185..949", "185..9490")
        with self.assertRaises(ShmirDesignError):
            parse_genbank_cds(texto, source="fuera")

    def test_un_fichero_vacio_aborta(self):
        with self.assertRaises(ShmirDesignError):
            parse_genbank_cds("", source="vacio")

    def test_un_fichero_que_no_es_GenBank_aborta(self):
        with self.assertRaises(ShmirDesignError):
            parse_genbank_cds(">NM_011170.3\nACGT\n", source="fasta")


class TestCoherenciaConLaSecuencia(unittest.TestCase):

    def test_una_longitud_distinta_a_la_del_FASTA_aborta(self):
        cds = parse_genbank_cds(RATON, source="RATON")
        with self.assertRaises(ShmirDesignError) as ctx:
            cds.check_against_sequence_length(2000)
        self.assertIn("2191", str(ctx.exception))

    def test_la_longitud_correcta_pasa(self):
        cds = parse_genbank_cds(RATON, source="RATON")
        cds.check_against_sequence_length(2191)

    def test_un_accession_distinto_al_esperado_aborta(self):
        cds = parse_genbank_cds(RATON, source="RATON")
        with self.assertRaises(ShmirDesignError) as ctx:
            cds.check_accession("NM_000311.5")
        self.assertIn("NM_000311.5", str(ctx.exception))


class TestCargaDesdeDisco(unittest.TestCase):

    def test_lee_el_fichero_y_devuelve_el_CDS(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "raton.gb"
            p.write_text(RATON, encoding="utf-8")
            self.assertEqual(load_genbank_cds(p).cds, (185, 949))

    def test_un_md5_que_no_cuadra_aborta(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "raton.gb"
            p.write_text(RATON, encoding="utf-8")
            with self.assertRaises(ChecksumMismatchError):
                load_genbank_cds(p, expected_md5="0" * 32)

    def test_el_md5_correcto_pasa_y_queda_registrado(self):
        import hashlib

        with TemporaryDirectory() as d:
            p = Path(d) / "raton.gb"
            p.write_text(RATON, encoding="utf-8")
            md5 = hashlib.md5(p.read_bytes(), usedforsecurity=False).hexdigest()
            cds = load_genbank_cds(p, expected_md5=md5)
            self.assertEqual(cds.md5, md5)

    def test_un_fichero_ausente_aborta_diciendo_cual(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            load_genbank_cds(Path("/no/existe/raton.gb"))
        self.assertIn("raton.gb", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
