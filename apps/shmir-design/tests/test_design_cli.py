"""Tests del CLI de diseño (orden de operaciones completo).

Regla 5: escritos antes que `tools/design.py`.
"""

import tempfile
import unittest
from pathlib import Path

from shmir_design.reference import REFERENCES, fixture_available
from tools.design import main

SONDA = ">sonda de prueba, no es un dato biologico\n" + "GCGTCAGTACGATCGAATTACT" * 30


class TestArgumentos(unittest.TestCase):

    def test_sin_directorio_de_salida_es_error(self):
        self.assertEqual(main(["--fasta", "/x.fa"]), 2)

    def test_un_fasta_que_no_existe_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["--fasta", "/no/existe.fa", "--out", tmp]), 2)

    def test_sin_fixtures_y_sin_fasta_aborta(self):
        if all(fixture_available(ref) for ref in REFERENCES.values()):
            self.skipTest("los fixtures estan disponibles; este caso ya no aplica")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["--out", tmp]), 2)

    def test_un_andamio_inexistente_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                main(["--fasta", "/x.fa", "--out", tmp, "--scaffold", "/no/hay.toml"]), 2
            )


class TestEjecucionCompleta(unittest.TestCase):

    def correr(self, extra=None):
        directorio = tempfile.mkdtemp()
        fasta = Path(directorio) / "sonda.fa"
        fasta.write_text(SONDA, encoding="utf-8")
        salida = Path(directorio) / "salida"
        codigo = main(
            ["--fasta", str(fasta), "--name", "sonda", "--out", str(salida)]
            + (extra or [])
        )
        return codigo, salida

    def test_escribe_las_cinco_salidas(self):
        codigo, salida = self.correr()
        self.assertEqual(codigo, 0)
        for nombre in (
            "sonda_ventanas.tsv",
            "sonda_seleccionados.tsv",
            "sonda_guias.fasta",
            "sonda_oligos.tsv",
            "sonda_informe.txt",
        ):
            with self.subTest(nombre):
                self.assertTrue((salida / nombre).is_file())

    def test_el_informe_dice_que_filtros_no_corrieron(self):
        _, salida = self.correr()
        informe = (salida / "sonda_informe.txt").read_text(encoding="utf-8")
        self.assertIn("NO SE EJECUTARON", informe.upper())
        self.assertIn("provisional", informe.lower())

    def test_el_numero_de_candidatos_es_configurable(self):
        _, salida = self.correr(["--candidates", "2"])
        lineas = (salida / "sonda_seleccionados.tsv").read_text().splitlines()
        self.assertLessEqual(len(lineas) - 1, 2)

    def test_los_oligos_llevan_el_aviso_del_andamio(self):
        _, salida = self.correr()
        oligos = (salida / "sonda_oligos.tsv").read_text(encoding="utf-8")
        self.assertIn("REGLA_NO_CONFIRMADA", oligos)

    def test_con_un_andamio_sin_verificar_el_aviso_va_en_cada_fila(self):
        directorio = tempfile.mkdtemp()
        andamio = Path(directorio) / "andamio.toml"
        andamio.write_text(
            'nombre = "propio"\n'
            'flanco5 = "TGCTGTTGACAGTGAGCG"\n'
            'loop = "TAGTGAAGCCACAGATGTA"\n'
            'flanco3 = "TGCCTACTGCCTCGGA"\n',
            encoding="utf-8",
        )
        codigo, salida = self.correr(["--scaffold", str(andamio)])
        self.assertEqual(codigo, 0)
        for linea in (salida / "sonda_oligos.tsv").read_text().splitlines()[1:]:
            with self.subTest(linea[:20]):
                self.assertIn("ANDAMIO_NO_VERIFICADO", linea)


if __name__ == "__main__":
    unittest.main()
