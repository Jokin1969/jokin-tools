"""El casete del transgen: parental sin modulo, o terapeutico con el.

Regla 5: escritos antes.

Si el casete que se pasa YA lleva el modulo del shmiR y se pasa el GENOMA (con el intron
dentro), toda guia da impacto contra su propia horquilla: el filtro del transgen tumba el
panel entero por un artefacto, y el fallo parece un resultado. Lo que hay que dar en ese
caso es el TRANSCRITO MADURO, sin el intron.

Se detecta por SECUENCIA, no por el nombre del fichero: si el casete contiene el loop de
un andamio conocido, lleva un modulo dentro. El parental que hay hoy
(pAAV_G130E_W144Y_mouse_PrP_4xmiR-183T) no lo lleva, y el aviso lo dice tambien — para
que quede escrito por que el filtro se puede leer tal cual.
"""

import unittest
from pathlib import Path

from shmir_design.scaffold import SGEP_SCAFFOLD
from shmir_design.specificity import SpecificityDatabase
from shmir_design.transgene import carries_scaffold_module

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
CASETE = DIR / "aav_casete.fa"


def _db(secuencia: str) -> SpecificityDatabase:
    return SpecificityDatabase(
        name="casete", version="sonda", checksum="0" * 32,
        records={"casete": secuencia},
    )


class TestDeteccionPorSecuencia(unittest.TestCase):

    def test_un_casete_con_el_loop_del_andamio_se_detecta(self):
        loop = SGEP_SCAFFOLD.loop.replace("U", "T")
        aviso = carries_scaffold_module(_db("ACGT" * 20 + loop + "ACGT" * 20))
        self.assertTrue(aviso.carries)

    def test_y_el_aviso_pide_el_transcrito_MADURO(self):
        loop = SGEP_SCAFFOLD.loop.replace("U", "T")
        texto = carries_scaffold_module(_db("ACGT" * 20 + loop)).describe().lower()
        self.assertIn("maduro", texto)
        self.assertIn("intrón", texto)
        self.assertIn("su propia horquilla", texto)

    def test_tambien_detecta_el_loop_de_miR_30a(self):
        aviso = carries_scaffold_module(_db("ACGT" * 10 + "CTGTGAAGCCACAGATGGG"))
        self.assertTrue(aviso.carries)

    def test_sin_modulo_no_avisa_pero_lo_DICE(self):
        aviso = carries_scaffold_module(_db("ACGT" * 40))
        self.assertFalse(aviso.carries)
        self.assertIn("parental", aviso.describe().lower())

    def test_dice_que_loop_ha_encontrado(self):
        loop = SGEP_SCAFFOLD.loop.replace("U", "T")
        self.assertIn(loop, carries_scaffold_module(_db(loop)).describe())


@unittest.skipUnless(CASETE.is_file(), "NOT_RUN: falta data/reference/aav_casete.fa")
class TestElCaseteQueHayHoy(unittest.TestCase):
    """El parental aportado el 2026-08-26: 5282 pb, sin modulo."""

    def _casete(self):
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.polya import normalize_sequence

        _, bruta = parse_fasta_payload(CASETE.read_text(encoding="utf-8"), source="fa")
        return normalize_sequence(bruta, name="casete AAV")

    def test_mide_5282_pb(self):
        self.assertEqual(len(self._casete()), 5282)

    def test_no_lleva_modulo_de_shmiR(self):
        aviso = carries_scaffold_module(_db(self._casete()))
        self.assertFalse(aviso.carries)
