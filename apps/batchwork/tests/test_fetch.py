"""Tests de la descarga (paso 0). Regla 5: escritos antes que `batchwork/fetch.py`.

Nada de esto toca la red: se prueba la construccion de la peticion y el parseo de la
respuesta. La URL base NUNCA la pone el codigo — la pasa quien la haya verificado
(regla 4) — asi que aqui se usa un host inexistente a proposito.

Los payloads son fixtures de parseo etiquetados como tales, no registros reales.
"""

import unittest

from batchwork.errors import FetchError
from batchwork.fetch import build_efetch_url, parse_fasta_payload

BASE = "https://example.invalid/entrez/eutils/efetch.fcgi"

FASTA_OK = ">TEST-PARSER fixture, no es un registro real\nACGTACGTAC\nGTNNGT\n"
XML_ERROR = (
    '<?xml version="1.0"?>\n'
    "<eFetchResult><ERROR>ID list is empty</ERROR></eFetchResult>\n"
)


class TestConstruccionDeLaPeticion(unittest.TestCase):

    def test_incluye_los_parametros_verificados(self):
        url = build_efetch_url(BASE, "NM_011170.3")
        self.assertTrue(url.startswith(BASE + "?"))
        for esperado in ("db=nuccore", "id=NM_011170.3", "rettype=fasta", "retmode=text"):
            self.assertIn(esperado, url)

    def test_api_key_y_cortesia_se_anaden_si_se_dan(self):
        url = build_efetch_url(BASE, "NM_011170.3", api_key="K", tool="batchwork")
        self.assertIn("api_key=K", url)
        self.assertIn("tool=batchwork", url)

    def test_sin_api_key_no_aparece_el_parametro(self):
        self.assertNotIn("api_key", build_efetch_url(BASE, "NM_011170.3"))

    def test_rechaza_url_no_https(self):
        with self.assertRaises(ValueError):
            build_efetch_url("http://example.invalid/efetch.fcgi", "NM_011170.3")

    def test_rechaza_url_vacia(self):
        with self.assertRaises(ValueError) as ctx:
            build_efetch_url("", "NM_011170.3")
        self.assertIn("verificad", str(ctx.exception).lower())

    def test_rechaza_accession_vacio(self):
        with self.assertRaises(ValueError):
            build_efetch_url(BASE, "  ")


class TestParseoDeLaRespuesta(unittest.TestCase):

    def test_extrae_cabecera_y_secuencia(self):
        header, sequence = parse_fasta_payload(FASTA_OK, source=BASE)
        self.assertTrue(header.startswith("TEST-PARSER"))
        self.assertEqual(sequence, "ACGTACGTACGTNNGT")

    def test_respuesta_xml_con_200_no_se_parsea(self):
        """NCBI devuelve su XML de error con codigo 200: hay que detectarlo."""
        with self.assertRaises(FetchError) as ctx:
            parse_fasta_payload(XML_ERROR, source=BASE)
        mensaje = str(ctx.exception)
        self.assertIn(">", mensaje)
        self.assertIn("ID list is empty", mensaje)

    def test_respuesta_vacia_aborta(self):
        with self.assertRaises(FetchError):
            parse_fasta_payload("", source=BASE)

    def test_cabecera_sin_secuencia_aborta(self):
        with self.assertRaises(FetchError) as ctx:
            parse_fasta_payload(">solo cabecera\n", source=BASE)
        self.assertIn("sin secuencia", str(ctx.exception).lower())

    def test_varios_registros_abortan(self):
        payload = FASTA_OK + ">TEST-PARSER segundo registro\nACGT\n"
        with self.assertRaises(FetchError) as ctx:
            parse_fasta_payload(payload, source=BASE)
        self.assertIn("2", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
