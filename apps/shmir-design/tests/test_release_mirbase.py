"""Los precursores y los maduros TIENEN que ser de la misma release. Regla 5.

`hairpin.fa` (precursores) y `mature.fa` (maduros) son dos ficheros de miRBase y ninguno
lleva la versión dentro: se declara. **De versiones distintas no son consistentes** —entre
releases se añaden, se retiran y se RENOMBRAN entradas, y un maduro que se busca dentro de
un precursor de otra versión puede no estar, o estar en otro sitio—. Así que no se avisa:
se aborta.
"""

import unittest

from shmir_design.errors import ShmirDesignError
from shmir_design.mirbase_release import RELEASE_DECLARADA, comprobar_release


class TestMismaRelease(unittest.TestCase):

    def test_iguales_deja_pasar(self):
        self.assertEqual(comprobar_release(mature="23", hairpin="23"), "23")

    def test_distintas_ABORTAN(self):
        with self.assertRaises(ShmirDesignError) as caja:
            comprobar_release(mature="23", hairpin="22")
        mensaje = str(caja.exception)
        self.assertIn("23", mensaje)
        self.assertIn("22", mensaje)
        # El aborto DICE por qué, no sólo que no.
        self.assertIn("renombr", mensaje.lower())

    def test_una_sin_declarar_ABORTA(self):
        """Sin declararla no se puede comparar, y «no se pudo comparar» no es «coinciden»."""
        for mature, hairpin in (("23", ""), ("", "23"), ("", "")):
            with self.subTest(mature=mature, hairpin=hairpin):
                with self.assertRaises(ShmirDesignError):
                    comprobar_release(mature=mature, hairpin=hairpin)

    def test_se_normaliza_el_formato(self):
        """«23» y «v23» y « 23 » son la misma release; que no aborte por el prefijo."""
        self.assertEqual(comprobar_release(mature="v23", hairpin=" 23 "), "23")

    def test_la_release_del_proyecto_esta_DECLARADA(self):
        self.assertEqual(RELEASE_DECLARADA, "23")


class TestElManifiestoESlaFuente(unittest.TestCase):
    """La release no se teclea en el código: sale del manifiesto, que es donde vive la
    procedencia de cada fichero del gestor."""

    def test_la_de_mature_sale_del_manifiesto_del_repositorio(self):
        from pathlib import Path

        from shmir_design.mirbase_release import release_del_manifiesto

        raiz = Path(__file__).resolve().parent.parent
        manifiesto = raiz / "data" / "reference" / "manifest.tsv"
        self.assertEqual(release_del_manifiesto("mature.fa", manifiesto), "23")

    def test_un_fichero_que_no_esta_devuelve_VACIO_no_una_suposicion(self):
        from pathlib import Path

        from shmir_design.mirbase_release import release_del_manifiesto

        raiz = Path(__file__).resolve().parent.parent
        manifiesto = raiz / "data" / "reference" / "manifest.tsv"
        self.assertEqual(release_del_manifiesto("hairpin.fa", manifiesto), "")
