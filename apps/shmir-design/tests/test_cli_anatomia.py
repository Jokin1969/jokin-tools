"""Tests del CLI en lo que toca a la anatomia (bloques 7 y 8).

Regla 5: escritos antes de tocar `tools/design.py`.

El agujero que cierran: `--fasta` sin `--cds` caia en `whole_is_utr3()` y tilaba el
transcrito entero como 3'UTR, en silencio.

Las secuencias de este fichero son SONDAS de mecanismo, no datos biologicos.
"""

import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from tools.design import main

UTR5 = "GCGTCAGTACGATCGAATTACT" * 2           # 44 nt   -> 1..44
CDS = "ATG" + "GCTAACGGGACT" * 8 + "TAA"        # 102 nt  -> 45..146
UTR3 = "GCGTCAGTACGATCGAATTACT" * 20            # 440 nt  -> 147..586
SONDA = UTR5 + CDS + UTR3                       # 586 nt
CDS_COORDS = ("45", "146")
CDS_CORRIDO = ("44", "145")                     # un nucleotido a la izquierda
ORF_LARGO = "GG" + "ATG" + "GCTAACGGGACT" * 20 + "TAA" + "GG" * 40  # 81 codones


def _fasta(directorio: Path, nombre: str = "sonda.fa", secuencia: str = SONDA) -> Path:
    ruta = directorio / nombre
    ruta.write_text(f">sonda de mecanismo, no es un dato biologico\n{secuencia}\n")
    return ruta


def _correr(args: list[str]) -> tuple[int, str]:
    salida = StringIO()
    with redirect_stdout(salida), redirect_stderr(salida):
        codigo = main(args)
    return codigo, salida.getvalue()


class TestElFallbackEstaCerrado(unittest.TestCase):

    def test_un_fasta_sin_cds_y_sin_region_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = _fasta(Path(tmp))
            codigo, salida = _correr(["--fasta", str(fa), "--out", tmp])
        self.assertEqual(codigo, 2)
        self.assertIn("anatomia", salida.lower())

    def test_el_error_enumera_las_tres_vias(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = _fasta(Path(tmp))
            _, salida = _correr(["--fasta", str(fa), "--out", tmp])
        for via in ("--cds", "--genbank", "--region 3utr"):
            self.assertIn(via, salida)

    def test_declarar_que_ya_es_3utr_deja_correr(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = _fasta(Path(tmp))
            codigo, _ = _correr(
                ["--fasta", str(fa), "--out", tmp, "--region", "3utr"]
            )
        self.assertEqual(codigo, 0)

    def test_declarar_el_cds_deja_correr(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = _fasta(Path(tmp))
            codigo, _ = _correr(
                ["--fasta", str(fa), "--out", tmp, "--cds", *CDS_COORDS]
            )
        self.assertEqual(codigo, 0)


class TestLaProcedenciaSaleEnElInforme(unittest.TestCase):

    def _informe(self, extra: list[str]) -> str:
        tmp = Path(tempfile.mkdtemp())
        fa = _fasta(tmp)
        codigo, salida = _correr(["--fasta", str(fa), "--out", str(tmp)] + extra)
        self.assertEqual(codigo, 0, salida)
        informes = list(tmp.glob("*informe*.txt"))
        self.assertEqual(len(informes), 1, [p.name for p in tmp.iterdir()])
        return informes[0].read_text(encoding="utf-8")

    def test_con_cds_dice_que_se_declaro_a_mano(self):
        texto = self._informe(["--cds", *CDS_COORDS])
        self.assertIn("declaradas a mano", texto)

    def test_con_region_3utr_dice_que_se_declaro_asi(self):
        texto = self._informe(["--region", "3utr"])
        self.assertIn("ya es el 3'UTR", texto)

    def test_el_informe_nombra_la_procedencia_siempre(self):
        for extra in (["--cds", *CDS_COORDS], ["--region", "3utr"]):
            self.assertIn("Procedencia de la anatomia", self._informe(extra))


class TestCodonDeParada(unittest.TestCase):

    def test_un_cds_sin_codon_de_parada_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = _fasta(Path(tmp))
            codigo, salida = _correr(
                ["--fasta", str(fa), "--out", tmp, "--cds", *CDS_CORRIDO]
            )
        self.assertEqual(codigo, 2)
        self.assertIn("codon de parada", salida)

    def test_se_puede_seguir_adelante_a_proposito(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = _fasta(Path(tmp))
            codigo, salida = _correr(
                [
                    "--fasta", str(fa), "--out", tmp, "--cds", *CDS_CORRIDO,
                    "--permitir-cds-sin-codon-parada",
                ]
            )
        self.assertEqual(codigo, 0)

    def test_al_seguir_adelante_el_aviso_queda_en_el_informe(self):
        tmp = Path(tempfile.mkdtemp())
        fa = _fasta(tmp)
        codigo, _ = _correr(
            [
                "--fasta", str(fa), "--out", str(tmp), "--cds", *CDS_CORRIDO,
                "--permitir-cds-sin-codon-parada",
            ]
        )
        self.assertEqual(codigo, 0)
        texto = list(tmp.glob("*informe*.txt"))[0].read_text(encoding="utf-8")
        self.assertIn("codon de parada", texto)


class TestProponerCds(unittest.TestCase):

    def test_proponer_no_ejecuta_el_diseño(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = _fasta(Path(tmp), secuencia=ORF_LARGO)
            codigo, salida = _correr(
                ["--fasta", str(fa), "--out", tmp, "--proponer-cds"]
            )
            self.assertEqual(codigo, 0)
            self.assertEqual(list(Path(tmp).glob("*informe*.txt")), [])
        self.assertIn("PROPUESTA NO CONFIRMADA", salida)
        self.assertIn("--cds ", salida)

    def test_sin_ningun_marco_lo_dice_y_no_sugiere_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = _fasta(Path(tmp), secuencia="G" * 400)
            codigo, salida = _correr(
                ["--fasta", str(fa), "--out", tmp, "--proponer-cds"]
            )
        self.assertEqual(codigo, 0)
        self.assertNotIn("--cds ", salida)


class TestGenBank(unittest.TestCase):

    GB = """\
LOCUS       SONDA                    586 bp    mRNA    linear   ROD 01-JAN-2026
ACCESSION   SONDA
VERSION     SONDA.1
FEATURES             Location/Qualifiers
     source          1..586
                     /organism="sonda de mecanismo"
     CDS             45..146
                     /gene="sonda"
//
"""

    def test_el_genbank_fija_la_anatomia(self):
        tmp = Path(tempfile.mkdtemp())
        fa = _fasta(tmp)
        gb = tmp / "sonda.gb"
        gb.write_text(self.GB, encoding="utf-8")
        codigo, salida = _correr(
            [
                "--fasta", str(fa), "--out", str(tmp), "--genbank", str(gb),
                "--permitir-cds-sin-codon-parada",
            ]
        )
        self.assertEqual(codigo, 0, salida)
        texto = list(tmp.glob("*informe*.txt"))[0].read_text(encoding="utf-8")
        self.assertIn("feature CDS", texto)

    def test_genbank_y_cds_a_la_vez_abortan(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = _fasta(Path(tmp))
            gb = Path(tmp) / "sonda.gb"
            gb.write_text(self.GB, encoding="utf-8")
            codigo, salida = _correr(
                [
                    "--fasta", str(fa), "--out", tmp,
                    "--genbank", str(gb), "--cds", *CDS_COORDS,
                ]
            )
        self.assertEqual(codigo, 2)
        self.assertIn("--genbank", salida)

    def test_un_genbank_de_otra_longitud_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            fa = _fasta(Path(tmp))
            gb = Path(tmp) / "sonda.gb"
            gb.write_text(self.GB.replace("586 bp", "999 bp"), encoding="utf-8")
            codigo, salida = _correr(
                ["--fasta", str(fa), "--out", tmp, "--genbank", str(gb)]
            )
        self.assertEqual(codigo, 2)
        self.assertIn("999", salida)


if __name__ == "__main__":
    unittest.main()
