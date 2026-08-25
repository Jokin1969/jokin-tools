"""Tests del registro de referencias y de la verificacion de checksum (paso 0).

Regla 5: escritos antes que `batchwork/reference.py`.

Los datos reales aqui son los metadatos verificados por el responsable del proyecto:
accession, longitudes, anatomia del transcrito y md5. NO hay secuencias: las de
NM_011170.3 y NM_000311.5 no se han podido descargar (ver `docs/endpoints-verificados.md`)
y no se sustituyen por nada (regla 1).

Las pruebas del comparador usan una sonda que NO es una secuencia de nucleotidos
(`PROBE-NOT-A-SEQUENCE`), justamente para que no pueda confundirse con un dato real.
"""

import unittest

from batchwork.errors import ChecksumMismatchError
from batchwork.reference import (
    REFERENCES,
    ReferenceTranscript,
    extract_3utr,
    sequence_md5,
    verify_transcript,
)

PROBE = "PROBE-NOT-A-SEQUENCE-0123456789"


def probe_reference(**overrides) -> ReferenceTranscript:
    """Referencia de juguete sobre la sonda, para probar el comparador."""
    defaults = dict(
        accession="PROBE.1",
        slug="probe",
        organism="sonda",
        gene="—",
        length=len(PROBE),
        md5=sequence_md5(PROBE),
        starts_with=PROBE[:10],
        ends_with=PROBE[-10:],
        utr5=(1, 10),
        cds=(11, 22),
        utr3=(23, len(PROBE)),
        utr3_md5=sequence_md5(PROBE[22:]),
    )
    defaults.update(overrides)
    return ReferenceTranscript(**defaults)


class TestRegistroInalterado(unittest.TestCase):
    """Los checksums son el guardarrail: tocarlos rompe el test, no el guardarrail."""

    def test_raton(self):
        ref = REFERENCES["NM_011170.3"]
        self.assertEqual(ref.gene, "Prnp")
        self.assertEqual(ref.organism, "Mus musculus")
        self.assertEqual(ref.length, 2191)
        self.assertEqual(ref.md5, "44fb8cd80883844cde5e53bbc367b176")
        self.assertEqual(ref.utr3, (950, 2191))
        self.assertEqual(ref.utr3_length, 1242)
        self.assertEqual(ref.utr3_md5, "19f5fa2a77a87892770e2affdc90e0e4")
        self.assertEqual(ref.starts_with, "CCCCTTTCCACTCCCGGCTCCCCCGCGTTG")
        self.assertEqual(ref.ends_with, "CATTAAATAGAAGCTATGATGAACACCTGG")

    def test_humano(self):
        ref = REFERENCES["NM_000311.5"]
        self.assertEqual(ref.gene, "PRNP")
        self.assertEqual(ref.organism, "Homo sapiens")
        self.assertEqual(ref.length, 2435)
        self.assertEqual(ref.md5, "e28a945d24ce53e0d1d93ba5b55a532a")
        self.assertEqual(ref.utr3, (830, 2435))
        self.assertEqual(ref.utr3_length, 1606)
        self.assertEqual(ref.utr3_md5, "f7fdb4a88d4834dbbf9a23edf9ec85dc")
        self.assertEqual(ref.starts_with, "GCCAGTCGCTGACAGCCGCGGCGCCGCGAG")
        self.assertEqual(ref.ends_with, "CTGAAATTAAACGAGCGAAGATGAGCACCA")


class TestAnatomiaCoherente(unittest.TestCase):
    """La aritmetia del transcrito se comprueba sin necesidad de la secuencia."""

    def test_los_tres_tramos_cubren_el_transcrito(self):
        for ref in REFERENCES.values():
            with self.subTest(ref.accession):
                self.assertEqual(ref.utr5[0], 1)
                self.assertEqual(ref.cds[0], ref.utr5[1] + 1)
                self.assertEqual(ref.utr3[0], ref.cds[1] + 1)
                self.assertEqual(ref.utr3[1], ref.length)

    def test_el_cds_es_multiplo_de_tres_y_cuadra_con_la_proteina(self):
        for ref in REFERENCES.values():
            with self.subTest(ref.accession):
                self.assertEqual(ref.cds_length % 3, 0)
                self.assertEqual(ref.protein_length, ref.cds_length // 3 - 1)

    def test_longitudes_declaradas(self):
        raton = REFERENCES["NM_011170.3"]
        humano = REFERENCES["NM_000311.5"]
        self.assertEqual((raton.utr5_length, raton.cds_length), (184, 765))
        self.assertEqual((humano.utr5_length, humano.cds_length), (67, 762))
        self.assertEqual((raton.protein_length, humano.protein_length), (254, 253))

    def test_una_anatomia_incoherente_se_rechaza_al_construirla(self):
        with self.assertRaises(ValueError):
            probe_reference(utr3=(23, len(PROBE) + 5))


class TestVerificacion(unittest.TestCase):

    def test_secuencia_correcta_pasa(self):
        verify_transcript(PROBE, probe_reference())

    def test_md5_distinto_aborta(self):
        ref = probe_reference(md5="0" * 32)
        with self.assertRaises(ChecksumMismatchError) as ctx:
            verify_transcript(PROBE, ref)
        mensaje = str(ctx.exception)
        self.assertIn("md5", mensaje.lower())
        self.assertIn("PARA", mensaje)

    def test_longitud_distinta_aborta_nombrando_la_longitud(self):
        # La referencia describe un transcrito coherente de 1 nt mas: lo que falla es
        # la secuencia que llega, no la anatomia declarada.
        ref = probe_reference(length=len(PROBE) + 1, utr3=(23, len(PROBE) + 1))
        with self.assertRaises(ChecksumMismatchError) as ctx:
            verify_transcript(PROBE, ref)
        self.assertIn(str(len(PROBE)), str(ctx.exception))

    def test_extremo_distinto_aborta(self):
        ref = probe_reference(ends_with="XXXXXXXXXX")
        with self.assertRaises(ChecksumMismatchError) as ctx:
            verify_transcript(PROBE, ref)
        self.assertIn("extremo", str(ctx.exception).lower())

    def test_saltos_de_linea_y_minusculas_no_cambian_el_md5(self):
        troceada = "\n".join([PROBE[:10].lower(), PROBE[10:20], PROBE[20:]])
        verify_transcript(troceada, probe_reference())

    def test_md5_es_el_de_la_secuencia_en_mayusculas_sin_saltos(self):
        self.assertEqual(sequence_md5("ac\ngt"), sequence_md5("ACGT"))


class TestExtraccion3UTR(unittest.TestCase):

    def test_extrae_el_tramo_declarado(self):
        self.assertEqual(extract_3utr(PROBE, probe_reference()), PROBE[22:])

    def test_md5_del_3utr_que_no_cuadra_aborta(self):
        ref = probe_reference(utr3_md5="0" * 32)
        with self.assertRaises(ChecksumMismatchError) as ctx:
            extract_3utr(PROBE, ref)
        self.assertIn("3'UTR", str(ctx.exception))

    def test_no_extrae_de_una_secuencia_que_no_verifica(self):
        """Si el transcrito no pasa el checksum, no se extrae nada de el."""
        with self.assertRaises(ChecksumMismatchError):
            extract_3utr(PROBE + "X", probe_reference())


if __name__ == "__main__":
    unittest.main()
