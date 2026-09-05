"""Tests de `--usar-manifiesto` (mejora de operatividad 1).

Colapsa las 31 flags de fontaneria en una: por cada fichero de `data/reference/` que
este en OK, se conecta al filtro que su rol declara, con la version y el md5 del propio
manifiesto. Deja de poderse teclear una version que no corresponde al fichero.
"""

import hashlib
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from shmir_design.manifest import LEGACY_COLUMNS, MANIFEST_NAME
from tools.design import main

SONDA = "GCGTCAGTACGATCGAATTACT" * 20
CASETE = "GGCCATACTAGCATCGGATCAG" * 8


def _correr(args):
    salida = StringIO()
    with redirect_stdout(salida), redirect_stderr(salida):
        codigo = main(args)
    return codigo, salida.getvalue()


class _Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.datos = self.raiz / "datos"
        self.datos.mkdir()
        self.fa = self.raiz / "sonda.fa"
        self.fa.write_text(">sonda\n" + SONDA + "\n")

    def _poner(self, nombre: str, contenido: str, filtro: str) -> str:
        ruta = self.datos / nombre
        ruta.write_text(contenido, encoding="utf-8")
        datos = ruta.read_bytes()
        return (
            f"{nombre}\t{filtro}\t{len(datos)}\t"
            f"{hashlib.md5(datos, usedforsecurity=False).hexdigest()}\t2026-08-25\t"
            f"puesto por el test\n"
        )

    def _manifiesto(self, *filas: str) -> None:
        (self.datos / MANIFEST_NAME).write_text(
            "\t".join(LEGACY_COLUMNS) + "\n" + "".join(filas), encoding="utf-8"
        )

    def _correr(self, extra=None):
        return _correr(
            [
                "--fasta", str(self.fa), "--out", str(self.raiz / "out"),
                "--region", "3utr", "--datos", str(self.datos),
            ]
            + (extra or [])
        )

    def _informe(self) -> str:
        return list((self.raiz / "out").glob("*informe*.txt"))[0].read_text(
            encoding="utf-8"
        )


class TestConecta(_Base):

    def _seccion_transgen(self) -> str:
        return self._informe().split("── Transgén")[1][:400]

    def test_el_casete_del_transgen_se_conecta_solo(self):
        self._manifiesto(self._poner("aav_casete.fa", ">c\n" + CASETE + "\n", "transgen"))
        codigo, salida = self._correr(["--usar-manifiesto"])
        self.assertEqual(codigo, 0, salida)
        seccion = self._seccion_transgen()
        self.assertNotIn("NOT_RUN", seccion)
        self.assertIn("Casete:", seccion)

    def test_la_version_del_informe_es_la_del_manifiesto_no_una_tecleada(self):
        """El fallo que este atajo cierra: version y fichero dejan de ir por separado."""
        self._manifiesto(self._poner("aav_casete.fa", ">c\n" + CASETE + "\n", "transgen"))
        self._correr(["--usar-manifiesto"])
        self.assertIn("versión 2026-08-25", self._seccion_transgen())

    def test_sin_el_flag_no_se_conecta_nada(self):
        self._manifiesto(self._poner("aav_casete.fa", ">c\n" + CASETE + "\n", "transgen"))
        codigo, salida = self._correr()
        self.assertEqual(codigo, 0, salida)
        self.assertIn("NOT_RUN", self._informe().split("── Transgén")[1][:400])

    def test_la_consola_dice_que_conecto_y_con_que_version(self):
        self._manifiesto(self._poner("aav_casete.fa", ">c\n" + CASETE + "\n", "transgen"))
        _, salida = self._correr(["--usar-manifiesto"])
        self.assertIn("aav_casete.fa", salida)
        self.assertIn("2026-08-25", salida)

    def test_un_fichero_sin_md5_no_se_conecta_y_se_dice(self):
        ruta = self.datos / "aav_casete.fa"
        ruta.write_text(">c\n" + CASETE + "\n", encoding="utf-8")
        self._manifiesto("aav_casete.fa\ttransgen\t\t\t\tsin registrar\n")
        codigo, salida = self._correr(["--usar-manifiesto"])
        self.assertEqual(codigo, 0, salida)
        self.assertIn("SIN_REGISTRAR", salida)
        self.assertIn("NOT_RUN", self._informe().split("── Transgén")[1][:400])

    def test_la_procedencia_del_informe_sale_del_manifiesto(self):
        self._manifiesto(self._poner("aav_casete.fa", ">c\n" + CASETE + "\n", "transgen"))
        self._correr(["--usar-manifiesto"])
        texto = self._informe()
        self.assertIn("Procedencia de los ficheros", texto)
        self.assertIn("aav_casete.fa", texto)


class TestElFlagExplicitoManda(_Base):

    def test_una_flag_explicita_gana_al_manifiesto(self):
        self._manifiesto(self._poner("aav_casete.fa", ">c\n" + CASETE + "\n", "transgen"))
        otro = self.raiz / "otro_casete.fa"
        otro.write_text(">otro\n" + CASETE + "\n")
        codigo, salida = self._correr(
            ["--usar-manifiesto", "--transgen", str(otro), "--transgen-version", "a mano"]
        )
        self.assertEqual(codigo, 0, salida)
        self.assertIn("otro_casete.fa", self._informe())

    def test_y_se_dice_que_ha_ganado_en_vez_de_hacerlo_callando(self):
        self._manifiesto(self._poner("aav_casete.fa", ">c\n" + CASETE + "\n", "transgen"))
        otro = self.raiz / "otro_casete.fa"
        otro.write_text(">otro\n" + CASETE + "\n")
        _, salida = self._correr(
            ["--usar-manifiesto", "--transgen", str(otro), "--transgen-version", "a mano"]
        )
        self.assertIn("--transgen", salida)
        self.assertIn("manda", salida.lower())


class TestLaDianaYANOsePideAparte(_Base):
    """Era lo único del manifiesto que además había que teclear. Ya no.

    `--target` existía porque la diana es un accession y el manifiesto lista ficheros. Y
    era cierto — pero la diana ya estaba declarada en `data/diana/variantes.toml`, con
    todas sus variantes y con procedencia, y ésa es la que usa el veredicto de BLAST. Eran
    dos respuestas a la misma pregunta y ganaba la peor.
    """

    def test_el_refseq_CORRE_sin_teclear_nada(self):
        self._manifiesto(
            self._poner("refseq_rna.fa", ">diana\n" + SONDA + "\n", "especificidad")
        )
        codigo, salida = self._correr(["--usar-manifiesto"])
        self.assertEqual(codigo, 0, salida)

    def test_y_la_bandera_ya_no_existe(self):
        # `argparse` sale con `SystemExit(2)` ante una bandera que no conoce, y eso es
        # lo que se comprueba: que no quede una segunda forma de contestar la pregunta.
        with self.assertRaises(SystemExit):
            self._correr(["--usar-manifiesto", "--target", "loquesea"])


class TestSinManifiesto(_Base):

    def test_usar_manifiesto_sin_manifiesto_aborta(self):
        codigo, salida = self._correr(["--usar-manifiesto"])
        self.assertEqual(codigo, 2)
        self.assertIn(MANIFEST_NAME, salida)


if __name__ == "__main__":
    unittest.main()
