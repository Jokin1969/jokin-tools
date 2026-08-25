"""Tests del comando de bloques (tanda B).

Regla 5: escritos antes que `tools/blocks.py`.

Lo que pide el enunciado: sobre la tabla de candidatos YA calculada, seleccionar N y
devolver el bloque completo listo para pedir. Asi que el comando lee el TSV comparativo
y toma la seleccion por numero de fila o por guia.
"""

import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from tools.blocks import main

GUIA_1018 = "TTTAGTACTGGATGGAACGGCC"
GUIA_SGEP = "TAGATAAGCATTATAATTCCTA"


def _correr(args):
    salida = StringIO()
    with redirect_stdout(salida), redirect_stderr(salida):
        codigo = main(args)
    return codigo, salida.getvalue()


def _tabla(directorio: Path) -> Path:
    ruta = directorio / "comparativa.tsv"
    ruta.write_text(
        "# cabecera de comentario\n"
        "inicio_transcrito\tguia\tveredicto\n"
        f"1018\t{GUIA_1018}\tINCOMPLETE\n"
        f"2000\t{GUIA_SGEP}\tINCOMPLETE\n",
        encoding="utf-8",
    )
    return ruta


class TestArgumentos(unittest.TestCase):

    def test_sin_salida_es_error(self):
        self.assertEqual(_correr(["--guia", GUIA_1018])[0], 2)

    def test_sin_guias_ni_tabla_es_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            codigo, salida = _correr(["--out", tmp])
        self.assertEqual(codigo, 2)
        self.assertIn("--guia", salida)

    def test_una_tabla_que_no_existe_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            codigo, _ = _correr(["--out", tmp, "--tabla", "/no/existe.tsv"])
        self.assertEqual(codigo, 2)


class TestDesdeGuiasSueltas(unittest.TestCase):

    def test_una_guia_produce_las_tres_salidas(self):
        with tempfile.TemporaryDirectory() as tmp:
            codigo, salida = _correr(["--out", tmp, "--guia", GUIA_1018])
            self.assertEqual(codigo, 0, salida)
            nombres = {p.name for p in Path(tmp).iterdir()}
        self.assertIn("bloques.fasta", nombres)
        self.assertIn("bloques.tsv", nombres)
        self.assertIn("hoja_de_pedido.txt", nombres)

    def test_el_modulo_de_1018_es_el_esperado(self):
        from tests.test_blocks import MODULO_1018

        with tempfile.TemporaryDirectory() as tmp:
            _correr(["--out", tmp, "--guia", GUIA_1018])
            fasta = (Path(tmp) / "bloques.fasta").read_text(encoding="utf-8")
        self.assertIn(MODULO_1018, fasta.replace("\n", ""))

    def test_varias_guias_dan_varias_filas(self):
        with tempfile.TemporaryDirectory() as tmp:
            _correr(["--out", tmp, "--guia", GUIA_1018, "--guia", GUIA_SGEP])
            filas = (Path(tmp) / "bloques.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(filas) - 1, 2)

    def test_una_guia_repetida_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            codigo, salida = _correr(
                ["--out", tmp, "--guia", GUIA_1018, "--guia", GUIA_1018]
            )
        self.assertEqual(codigo, 2)
        self.assertIn("repetida", salida)


class TestDesdeLaTabla(unittest.TestCase):

    def test_sin_seleccion_se_toman_todas(self):
        tmp = Path(tempfile.mkdtemp())
        codigo, salida = _correr(["--out", str(tmp), "--tabla", str(_tabla(tmp))])
        self.assertEqual(codigo, 0, salida)
        filas = (tmp / "bloques.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(filas) - 1, 2)

    def test_se_puede_elegir_por_numero_de_fila(self):
        tmp = Path(tempfile.mkdtemp())
        codigo, salida = _correr(
            ["--out", str(tmp), "--tabla", str(_tabla(tmp)), "--elegir", "2"]
        )
        self.assertEqual(codigo, 0, salida)
        texto = (tmp / "bloques.tsv").read_text(encoding="utf-8")
        self.assertIn(GUIA_SGEP, texto)
        self.assertNotIn(GUIA_1018, texto)

    def test_se_pueden_elegir_varias(self):
        tmp = Path(tempfile.mkdtemp())
        _correr(["--out", str(tmp), "--tabla", str(_tabla(tmp)), "--elegir", "1,2"])
        filas = (tmp / "bloques.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(filas) - 1, 2)

    def test_un_numero_fuera_de_rango_aborta(self):
        tmp = Path(tempfile.mkdtemp())
        codigo, salida = _correr(
            ["--out", str(tmp), "--tabla", str(_tabla(tmp)), "--elegir", "9"]
        )
        self.assertEqual(codigo, 2)
        self.assertIn("9", salida)

    def test_una_tabla_sin_columna_guia_aborta(self):
        tmp = Path(tempfile.mkdtemp())
        mala = tmp / "mala.tsv"
        mala.write_text("inicio\tveredicto\n1\tPASS\n", encoding="utf-8")
        codigo, salida = _correr(["--out", str(tmp), "--tabla", str(mala)])
        self.assertEqual(codigo, 2)
        self.assertIn("guia", salida)

    def test_una_tabla_vacia_aborta(self):
        tmp = Path(tempfile.mkdtemp())
        vacia = tmp / "vacia.tsv"
        vacia.write_text("inicio_transcrito\tguia\n", encoding="utf-8")
        codigo, salida = _correr(["--out", str(tmp), "--tabla", str(vacia)])
        self.assertEqual(codigo, 2)


class TestSalidaEnPantalla(unittest.TestCase):

    def test_la_hoja_de_pedido_se_imprime(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, salida = _correr(["--out", tmp, "--guia", GUIA_1018])
        self.assertIn("Hoja de pedido", salida)

    def test_avisa_de_XhoI_y_EcoRI(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, salida = _correr(["--out", tmp, "--guia", GUIA_1018])
        self.assertIn("XhoI", salida)

    def test_un_bloque_con_una_comprobacion_en_FAIL_sale_con_codigo_1(self):
        """Se escriben las salidas igual, pero el codigo de salida lo dice."""
        with tempfile.TemporaryDirectory() as tmp:
            codigo, salida = _correr(
                ["--out", tmp, "--guia", "TGCTAGCTGGATGGAACGGCCA"]
            )
        self.assertEqual(codigo, 1)
        self.assertIn("sitios_unicos", salida)


if __name__ == "__main__":
    unittest.main()
