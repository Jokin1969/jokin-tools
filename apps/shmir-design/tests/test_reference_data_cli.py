"""Tests de `tools/reference_data.py` (paso 0 por CLI).

Regla 5: escritos antes de reescribir la herramienta. No tocan la red: comprueban que
sin fixture se aborta y que `--fetch` exige la URL verificada por parametro (regla 4).
"""

import tempfile
import unittest

from shmir_design.reference import REFERENCES, fixture_available
from tools.conservation_report import main as conservation_main
from tools.tiling_report import main as tiling_main
from tools.reference_data import main


class TestCli(unittest.TestCase):

    def test_fetch_sin_url_se_niega(self):
        self.assertEqual(main(["--fetch"]), 2)

    def test_sin_fixtures_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["--data-dir", tmp]), 2)

    def test_url_no_https_se_rechaza(self):
        self.assertEqual(main(["--fetch", "--efetch-url", "http://example.invalid/e"]), 2)


class TestConservationCli(unittest.TestCase):

    def test_sin_fixtures_aborta_en_vez_de_informar_a_medias(self):
        if all(fixture_available(ref) for ref in REFERENCES.values()):
            self.skipTest("los fixtures estan disponibles; este caso ya no aplica")
        self.assertEqual(conservation_main([]), 2)

    def test_un_fasta_suelto_sin_el_otro_es_error(self):
        self.assertEqual(conservation_main(["--fasta-a", "/no/existe.fa"]), 2)


class TestTilingCli(unittest.TestCase):

    def test_sin_fixtures_aborta(self):
        if all(fixture_available(ref) for ref in REFERENCES.values()):
            self.skipTest("los fixtures estan disponibles; este caso ya no aplica")
        self.assertEqual(tiling_main([]), 2)

    def test_un_fichero_de_seeds_inexistente_aborta(self):
        self.assertEqual(tiling_main(["--seeds", "/no/existe.txt"]), 2)

    def test_seeds_y_bootstrap_a_la_vez_es_error(self):
        self.assertEqual(tiling_main(["--seeds", "/x.txt", "--bootstrap-seeds"]), 2)


if __name__ == "__main__":
    unittest.main()
