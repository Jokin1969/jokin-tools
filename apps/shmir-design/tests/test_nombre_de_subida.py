"""El nombre de un fichero subido llega del NAVEGADOR, y se usa para escribir en disco.

`ui/streamlit_app.py` escribia `Path(tempfile.mkdtemp()) / subido.name` con el nombre
tal cual. `UploadedFile.name` lo pone el cliente, no el servidor: con `../` dentro, la
escritura sale del directorio temporal que se acababa de crear para contenerla. Que
Streamlit lo limpie o no es una suposicion sobre codigo ajeno, y la regla de la casa es
que una causa no comprobada no se da por buena: se comprueba aqui.

Es la misma familia que `check_project_slug`, un nivel mas abajo: alli el nombre lo
teclea el usuario, aqui lo manda el navegador.
"""

import tempfile
import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.errors import ShmirDesignError


class TestElNombreSeQuedaDENTRO(unittest.TestCase):

    def setUp(self):
        self.base = Path(tempfile.mkdtemp())

    def test_un_nombre_normal_pasa_entero(self):
        ruta = presentation.upload_path(self.base, "NM_011170.3.gb")
        self.assertEqual(ruta, self.base / "NM_011170.3.gb")

    def test_la_extension_SOBREVIVE(self):
        # No es cosmetica: `resolve_anatomy` y `load_scaffold` deciden el formato por
        # ella. Un saneado que se coma el `.gb` rompe la carga sin decir por que.
        for nombre in ("a.gb", "a.gbk", "a.fa", "a.fasta", "a.tsv"):
            with self.subTest(nombre=nombre):
                self.assertEqual(presentation.upload_path(self.base, nombre).suffix,
                                 Path(nombre).suffix)

    def test_una_ruta_con_directorios_se_queda_con_el_NOMBRE(self):
        ruta = presentation.upload_path(self.base, "sub/dir/NM_011170.3.gb")
        self.assertEqual(ruta.parent, self.base)
        self.assertEqual(ruta.name, "NM_011170.3.gb")

    def test_el_recorrido_hacia_arriba_se_CAE_con_el_resto_de_la_ruta(self):
        # La regla es UNA: sobrevive el nombre, se cae todo lo que hay delante. `..` no
        # es un caso especial, es ruta — y por eso no hay que acertar con una lista de
        # formas de escribirlo (`..%2f`, `....//`, `..\`): no se limpia la ruta, se
        # descarta entera.
        for nombre, esperado in (
            ("../fuera.gb", "fuera.gb"),
            ("../../../etc/passwd", "passwd"),
            ("..%2f..%2ffuera.gb", "..%2f..%2ffuera.gb"),
        ):
            with self.subTest(nombre=nombre):
                self.assertEqual(
                    presentation.upload_path(self.base, nombre), self.base / esperado
                )

    def test_lo_que_NO_deja_nombre_aborta(self):
        # `..`, `.` y el vacio no dejan nada con lo que escribir. No se inventa un
        # nombre: se para y se dice.
        for nombre in ("..", ".", "", "   ", "..///"):
            with self.subTest(nombre=nombre):
                with self.assertRaises(ShmirDesignError):
                    presentation.upload_path(self.base, nombre)

    def test_una_ruta_absoluta_pierde_la_ruta_como_cualquier_otra(self):
        # Misma regla que el caso de arriba, no una distinta: lo que sobrevive es el
        # NOMBRE. `/etc/passwd` acaba en `passwd` DENTRO del temporal — se escribe lo
        # que subio el usuario, en el sitio que le toca, y no se toca ningun `/etc`.
        for nombre, esperado in (("/etc/passwd", "passwd"), ("/tmp/otro.gb", "otro.gb")):
            with self.subTest(nombre=nombre):
                ruta = presentation.upload_path(self.base, nombre)
                self.assertEqual(ruta, self.base / esperado)

    def test_la_barra_invertida_tambien(self):
        # En Windows es separador y `PurePosixPath` no lo ve. No se depende del sistema
        # donde corra: se rechaza el caracter.
        with self.assertRaises(ShmirDesignError):
            presentation.upload_path(self.base, r"..\fuera.gb")

    def test_el_byte_NULO_aborta(self):
        with self.assertRaises(ShmirDesignError):
            presentation.upload_path(self.base, "a\x00.gb")

    def test_el_resultado_esta_DENTRO_de_la_base(self):
        # La comprobacion final, sobre la ruta resuelta: es la que vale, porque es la
        # que se le pasa a `write_bytes`.
        ruta = presentation.upload_path(self.base, "  espacios .gb  ")
        self.assertTrue(ruta.resolve().is_relative_to(self.base.resolve()))


class TestLaPaginaLoUSA(unittest.TestCase):

    def test_la_pagina_no_escribe_con_el_nombre_crudo(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("mkdtemp()) / ", fuente)
        self.assertIn("upload_path(", fuente)


if __name__ == "__main__":
    unittest.main()
