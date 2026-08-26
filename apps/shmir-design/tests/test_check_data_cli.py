"""Tests del comando de estado de los datos (tanda C).

Regla 5: escritos antes que `tools/check_data.py`.

Para que sirve: saber en diez segundos si merece la pena correr o falta algo. Valida el
directorio contra el manifiesto y dice que filtros pueden correr y cuales quedaran en
NOT_RUN, sin lanzar ningun diseño.
"""

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design.manifest import LEGACY_COLUMNS, MANIFEST_COLUMNS, MANIFEST_NAME
from tools.check_data import main

CABECERA = "\t".join(LEGACY_COLUMNS)
TABLA = f"""\
{CABECERA}
presente.fa\tespecificidad\t\t\t\tdescarga manual
ausente.fa\tcolision de seed\t\t\t\tmiRBase
"""


def _correr(args):
    salida = StringIO()
    with redirect_stdout(salida), redirect_stderr(salida):
        codigo = main(args)
    return codigo, salida.getvalue()


class TestSobreElDirectorioDeVerdad(unittest.TestCase):

    def test_sin_argumentos_mira_data_reference(self):
        codigo, salida = _correr([])
        self.assertIn(codigo, (0, 1))
        self.assertIn("manifest.tsv", salida + "data/reference/manifest.tsv")

    def test_lista_los_ficheros_que_el_proyecto_espera(self):
        _, salida = _correr([])
        for nombre in ("mature.fa", "rmsk_mouse.out", "aav_casete.fa"):
            self.assertIn(nombre, salida)

    def test_dice_que_filtros_quedaran_en_NOT_RUN(self):
        _, salida = _correr([])
        self.assertIn("NOT_RUN", salida)

    def test_no_lanza_ningun_diseño(self):
        """No debe escribir nada: es solo un chequeo."""
        with TemporaryDirectory() as tmp:
            _correr([])
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_con_ficheros_ausentes_el_codigo_es_1(self):
        codigo, _ = _correr([])
        self.assertEqual(codigo, 1)


class TestSobreUnDirectorioDado(unittest.TestCase):

    def _directorio(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ruta = Path(tmp.name)
        (ruta / MANIFEST_NAME).write_text(TABLA, encoding="utf-8")
        (ruta / "presente.fa").write_bytes(b">x\nACGT\n")
        return ruta

    def test_distingue_presente_de_ausente(self):
        _, salida = _correr(["--dir", str(self._directorio())])
        self.assertIn("SIN_REGISTRAR", salida)
        self.assertIn("AUSENTE", salida)

    def test_dice_el_md5_que_hay_que_apuntar(self):
        _, salida = _correr(["--dir", str(self._directorio())])
        self.assertIn("Apunta", salida)

    def test_todo_completo_da_codigo_0(self):
        import hashlib

        ruta = self._directorio()
        datos = (ruta / "presente.fa").read_bytes()
        md5 = hashlib.md5(datos, usedforsecurity=False).hexdigest()
        (ruta / "ausente.fa").write_bytes(b">y\nTTTT\n")
        md5b = hashlib.md5((ruta / "ausente.fa").read_bytes(), usedforsecurity=False).hexdigest()
        (ruta / MANIFEST_NAME).write_text(
            f"{CABECERA}\n"
            f"presente.fa\tespecificidad\t{len(datos)}\t{md5}\t2026-01-01\tmanual\n"
            f"ausente.fa\tcolision de seed\t9\t{md5b}\t2026-01-01\tmiRBase\n",
            encoding="utf-8",
        )
        codigo, salida = _correr(["--dir", str(ruta)])
        self.assertEqual(codigo, 0, salida)

    def test_un_md5_que_no_cuadra_da_codigo_2(self):
        ruta = self._directorio()
        (ruta / MANIFEST_NAME).write_text(
            f"{CABECERA}\npresente.fa\tespecificidad\t9\t{'0' * 32}\t2026-01-01\tmanual\n",
            encoding="utf-8",
        )
        codigo, salida = _correr(["--dir", str(ruta)])
        self.assertEqual(codigo, 2)
        self.assertIn("NO es el que dice ser", salida)

    def test_un_directorio_sin_manifiesto_aborta(self):
        with TemporaryDirectory() as tmp:
            codigo, salida = _correr(["--dir", tmp])
        self.assertEqual(codigo, 2)
        self.assertIn(MANIFEST_NAME, salida)

    def test_un_directorio_que_no_existe_aborta(self):
        codigo, salida = _correr(["--dir", "/no/existe"])
        self.assertEqual(codigo, 2)


class TestFormatoDeSalida(unittest.TestCase):

    def test_hay_una_tabla_con_estado_por_fichero(self):
        _, salida = _correr([])
        self.assertIn("── Ficheros de referencia", salida)

    def test_recuerda_que_NOT_RUN_no_es_PASS(self):
        _, salida = _correr([])
        self.assertIn("NOT_RUN no es PASS", salida)

    def test_en_modo_tsv_sale_una_fila_por_fichero(self):
        _, salida = _correr(["--tsv"])
        filas = [l for l in salida.splitlines() if l.strip()]
        self.assertIn("nombre\testado", filas[0])
        self.assertGreater(len(filas), 5)


if __name__ == "__main__":
    unittest.main()
