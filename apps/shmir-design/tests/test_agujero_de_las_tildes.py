"""El guardia de las tildes no puede eximir prosa castellana.

Regla 5: escrito antes.

`_es_ingles` eximía un literal si TODAS sus palabras estaban en un vocabulario inglés, y
en ese vocabulario entraron `intron` y `primer` para poder eximir `"chimeric intron"`
—el `label` con el que se busca la feature en el GenBank del plásmido—. Las dos existen
en los dos idiomas, así que «primer intron», que es castellano con dos faltas, salía
eximido entero.

Un guardia que deja pasar justo lo que tenía que cazar es peor que no tenerlo: además
tranquiliza. La excepción pasa a ser POR CONTEXTO —una lista de literales EXACTOS que se
usan como etiqueta de un fichero ajeno— en vez de por vocabulario.
"""

import importlib.util
import unittest
from pathlib import Path

_RUTA = Path(__file__).resolve().parents[1] / "tools" / "check_tildes.py"
_spec = importlib.util.spec_from_file_location("check_tildes", _RUTA)
check_tildes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_tildes)


class TestElAgujero(unittest.TestCase):
    def test_primer_intron_YA_NO_se_exime(self):
        self.assertFalse(check_tildes._es_etiqueta_ajena("el primer intron"))

    def test_y_se_corrige(self):
        arreglado, cambios = check_tildes.corregir("el primer intron del casete")
        self.assertIn("intrón", arreglado)
        self.assertIn("intron → intrón", cambios)


class TestLoQueSIsigueEximido(unittest.TestCase):
    def test_la_etiqueta_del_GenBank(self):
        self.assertTrue(check_tildes._es_etiqueta_ajena("chimeric intron"))

    def test_con_espacios_alrededor_tambien(self):
        self.assertTrue(check_tildes._es_etiqueta_ajena("  chimeric intron  "))

    def test_y_CON_LAS_COMILLAS_PEGADAS(self):
        # El barrido del fichero pasa el TOKEN, no el valor: llega con sus comillas.
        # Sin esto la excepción valía desde `corregir()` y no desde `revisar()`, o sea
        # que el guardia acentuaba la etiqueta del GenBank igual.
        self.assertTrue(check_tildes._es_etiqueta_ajena('"chimeric intron"'))
        self.assertTrue(check_tildes._es_etiqueta_ajena("'chimeric intron'"))

    def test_pero_dentro_de_una_frase_NO_exime(self):
        self.assertFalse(
            check_tildes._es_etiqueta_ajena("busca el chimeric intron del plasmido")
        )

    def test_y_esa_etiqueta_NO_se_toca(self):
        arreglado, cambios = check_tildes.corregir("chimeric intron")
        self.assertEqual(arreglado, "chimeric intron")
        self.assertEqual(cambios, [])


class TestLaExcepcionEsCERRADA(unittest.TestCase):
    def test_es_una_lista_de_literales_completos_no_de_palabras(self):
        for entrada in check_tildes.ETIQUETAS_AJENAS:
            with self.subTest(entrada):
                self.assertIn(" ", entrada, "una palabra suelta no necesita excepción")

    def test_la_etiqueta_que_la_motiva_sigue_siendo_la_que_usa_el_codigo(self):
        from shmir_design import introns

        self.assertIn(introns.QUIMERICO_FEATURE[1], check_tildes.ETIQUETAS_AJENAS)


if __name__ == "__main__":
    unittest.main()
