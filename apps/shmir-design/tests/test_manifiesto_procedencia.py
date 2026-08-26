"""El manifiesto tiene que decir QUE fichero era, no solo que existia.

Regla 5: escritos antes de ampliar el esquema.

Es la contramedida directa a la errata del 3'UTR fabricado: aquella se detecto por
LONGITUD contra las coordenadas declaradas. Un manifiesto que registre accession con
version, longitud y md5 permite hacer esa comprobacion sin abrir el fichero.

Los dos invariantes del transcrito murino, que este test fija contra el dato real:

    NM_011170.3      2191 nt   md5 canonico 44fb8cd80883844cde5e53bbc367b176
    3'UTR 950-2191   1242 nt   md5 canonico 19f5fa2a77a87892770e2affdc90e0e4
"""

import unittest
from pathlib import Path

from shmir_design.manifest import MANIFEST_COLUMNS, parse_manifest
from shmir_design.reference import REFERENCES, extract_3utr, load_3utr, sequence_md5

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
MANIFIESTO = DIR / "manifest.tsv"
RATON = DIR / "NM_011170.3.fa"


class TestEsquema(unittest.TestCase):

    def test_el_manifiesto_registra_accession_longitud_y_url(self):
        for columna in ("accession", "longitud", "url"):
            with self.subTest(columna):
                self.assertIn(columna, MANIFEST_COLUMNS)

    def test_el_manifiesto_del_repositorio_se_parsea(self):
        manifiesto = parse_manifest(
            MANIFIESTO.read_text(encoding="utf-8"), source=str(MANIFIESTO)
        )
        self.assertTrue(manifiesto.entries)

    def test_la_entrada_del_raton_declara_su_accession_con_version(self):
        manifiesto = parse_manifest(
            MANIFIESTO.read_text(encoding="utf-8"), source=str(MANIFIESTO)
        )
        entrada = manifiesto.find("NM_011170.3.fa")
        self.assertEqual(entrada.accession, "NM_011170.3")
        self.assertEqual(entrada.length, 2191)

    def test_toda_entrada_con_accession_declara_tambien_longitud(self):
        # Un accession sin longitud no permite la comprobacion que pilla la errata.
        manifiesto = parse_manifest(
            MANIFIESTO.read_text(encoding="utf-8"), source=str(MANIFIESTO)
        )
        for entrada in manifiesto.entries:
            if entrada.accession:
                with self.subTest(entrada.name):
                    self.assertIsNotNone(entrada.length)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestInvariantesDelRaton(unittest.TestCase):
    """Los dos pares longitud/md5, contra el fichero de verdad."""

    def test_el_transcrito_mide_2191_nt(self):
        self.assertEqual(REFERENCES["NM_011170.3"].length, 2191)

    def test_y_su_md5_canonico_es_el_registrado(self):
        secuencia = load_3utr.__wrapped__ if hasattr(load_3utr, "__wrapped__") else None
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.polya import normalize_sequence

        _, bruta = parse_fasta_payload(
            RATON.read_text(encoding="utf-8"), source=str(RATON)
        )
        limpia = normalize_sequence(bruta, name="NM_011170.3")
        self.assertEqual(len(limpia), 2191)
        self.assertEqual(sequence_md5(limpia), "44fb8cd80883844cde5e53bbc367b176")

    def test_el_3utr_va_de_950_a_2191_y_mide_1242(self):
        referencia = REFERENCES["NM_011170.3"]
        self.assertEqual(referencia.utr3, (950, 2191))
        self.assertEqual(referencia.utr3[1] - referencia.utr3[0] + 1, 1242)

    def test_y_su_md5_canonico_es_el_registrado(self):
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.polya import normalize_sequence

        _, bruta = parse_fasta_payload(
            RATON.read_text(encoding="utf-8"), source=str(RATON)
        )
        limpia = normalize_sequence(bruta, name="NM_011170.3")
        utr3 = extract_3utr(limpia, REFERENCES["NM_011170.3"])
        self.assertEqual(len(utr3), 1242)
        self.assertEqual(sequence_md5(utr3), "19f5fa2a77a87892770e2affdc90e0e4")

    def test_la_longitud_del_manifiesto_coincide_con_la_del_codigo(self):
        # Si alguien cambia una de las dos, esto salta. Es la comprobacion que la
        # errata del 3'UTR fabricado habria pasado.
        manifiesto = parse_manifest(
            MANIFIESTO.read_text(encoding="utf-8"), source=str(MANIFIESTO)
        )
        entrada = manifiesto.find("NM_011170.3.fa")
        self.assertEqual(entrada.length, REFERENCES["NM_011170.3"].length)


if __name__ == "__main__":
    unittest.main()
