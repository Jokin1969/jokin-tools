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
            self.skipTest("los fixtures están disponibles; este caso ya no aplica")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["--out", tmp]), 2)

    def test_un_andamio_inexistente_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                main(["--fasta", "/x.fa", "--out", tmp, "--scaffold", "/no/hay.toml"]), 2
            )


class TestDosEspecies(unittest.TestCase):
    """Dos FASTA en la misma ejecucion, con bloques conservados entre ellos."""

    def preparar(self):
        directorio = Path(tempfile.mkdtemp())
        bloque = "TTTTCTATATTTGTAACTTTGCATGT"
        a = directorio / "modelo.fa"
        b = directorio / "diana.fa"
        a.write_text(">modelo\n" + "GCGTCAGTACGATCGAATTACT" * 10 + bloque + "\n")
        b.write_text(">diana\n" + "ACGTCAGTACGATCGAATTAGT" * 8 + bloque + "\n")
        return directorio, a, b

    def correr(self, extra=None):
        directorio, a, b = self.preparar()
        salida = directorio / "salida"
        codigo = main(
            ["--fasta", str(a), "--name", "modelo",
             "--fasta-b", str(b), "--name-b", "diana",
             "--out", str(salida), "--region", "3utr"] + (extra or [])
        )
        return codigo, salida

    def test_escribe_las_cinco_salidas_de_cada_especie(self):
        codigo, salida = self.correr()
        self.assertEqual(codigo, 0)
        for especie in ("modelo", "diana"):
            for sufijo in ("ventanas.tsv", "seleccionados.tsv", "guias.fasta",
                           "oligos.tsv", "informe.txt"):
                with self.subTest(f"{especie}_{sufijo}"):
                    self.assertTrue((salida / f"{especie}_{sufijo}").is_file())

    def test_el_informe_trae_los_bloques_conservados(self):
        _, salida = self.correr()
        informe = (salida / "modelo_informe.txt").read_text(encoding="utf-8")
        self.assertIn("TTTTCTATATTTGTAACTTTGCATGT", informe)

    def test_fasta_b_sin_fasta_es_error(self):
        directorio, a, b = self.preparar()
        self.assertEqual(main(["--fasta-b", str(b), "--out", str(directorio / "x")]), 2)


class TestUmbralesPorLineaDeComandos(unittest.TestCase):

    def correr(self, extra, secuencia=None):
        directorio = Path(tempfile.mkdtemp())
        fasta = directorio / "sonda.fa"
        fasta.write_text(secuencia or SONDA)
        salida = directorio / "salida"
        codigo = main(
            ["--fasta", str(fasta), "--name", "sonda", "--out", str(salida),
             "--region", "3utr"] + extra
        )
        return codigo, salida

    def test_el_GC_minimo_se_puede_mover(self):
        """Bajando el minimo, las ventanas que fallaban por GC dejan de fallar."""
        # Sonda pobre en GC: el bloque conservado real, repetido.
        pobre = ">sonda\n" + "TTTTCTATATTTGTAACTTTGCATGT" * 20 + "\n"
        _, salida_defecto = self.correr([], secuencia=pobre)
        self.assertIn("GC=FAIL", (salida_defecto / "sonda_ventanas.tsv").read_text())

        codigo, salida = self.correr(["--gc-min", "0.10"], secuencia=pobre)
        self.assertEqual(codigo, 0)
        self.assertNotIn("GC=FAIL", (salida / "sonda_ventanas.tsv").read_text())

    def test_un_rango_de_GC_imposible_aborta(self):
        codigo, _ = self.correr(["--gc-min", "0.9", "--gc-max", "0.1"])
        self.assertEqual(codigo, 2)

    def test_el_flanco_de_polyA_se_puede_mover(self):
        # Sonda con una señal AATAAA en 81, para que la zona prohibida exista.
        # AATAAA TERMINAL (a 20 nt del extremo): el filtro escalonado solo hace FAIL
        # duro con las señales fuertes, asi que la señal tiene que serlo.
        con_senal = ">sonda\n" + "ACGT" * 20 + "AATAAA" + "ACGT" * 5 + "\n"
        codigo, salida = self.correr(["--polya-flank", "40"], secuencia=con_senal)
        self.assertEqual(codigo, 0)
        tsv = (salida / "sonda_ventanas.tsv").read_text()
        self.assertIn("±40 nt", tsv)

        _, salida_defecto = self.correr([], secuencia=con_senal)
        por_defecto = (salida_defecto / "sonda_ventanas.tsv").read_text()
        self.assertIn("±10 nt", por_defecto)
        self.assertGreater(tsv.count("zona_prohibida_polyA=FAIL"),
                           por_defecto.count("zona_prohibida_polyA=FAIL"))

    def test_el_numero_de_candidatos_llega_al_TSV(self):
        codigo, salida = self.correr(["--candidates", "2"])
        self.assertEqual(codigo, 0)
        lineas = (salida / "sonda_seleccionados.tsv").read_text().splitlines()
        self.assertLessEqual(len(lineas) - 1, 2)

    def test_el_umbral_de_asimetria_se_puede_mover(self):
        """Con el umbral por los suelos, ninguna ventana falla por asimetria."""
        por_defecto, salida_defecto = self.correr([])
        self.assertEqual(por_defecto, 0)
        self.assertIn("asimetria=FAIL", (salida_defecto / "sonda_ventanas.tsv").read_text())

        codigo, salida = self.correr(["--min-asymmetry", "-99"])
        self.assertEqual(codigo, 0)
        self.assertNotIn("asimetria=FAIL", (salida / "sonda_ventanas.tsv").read_text())


class TestEjecucionCompleta(unittest.TestCase):

    def correr(self, extra=None):
        directorio = tempfile.mkdtemp()
        fasta = Path(directorio) / "sonda.fa"
        fasta.write_text(SONDA, encoding="utf-8")
        salida = Path(directorio) / "salida"
        codigo = main(
            ["--fasta", str(fasta), "--name", "sonda", "--out", str(salida),
             "--region", "3utr"]
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

    def test_los_oligos_traen_la_horquilla_y_el_modulo(self):
        _, salida = self.correr()
        oligos = (salida / "sonda_oligos.tsv").read_text(encoding="utf-8")
        self.assertNotIn("REGLA_NO_CONFIRMADA", oligos)   # regla ya resuelta
        self.assertIn("oligo", oligos.splitlines()[0].split("\t"))

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
