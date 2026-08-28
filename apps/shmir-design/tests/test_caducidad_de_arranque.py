"""La lista de ARRANQUE de seeds tiene fecha de caducidad, y la fecha es un FICHERO.

`seeds.BOOTSTRAP_SEED_TABLE` son doce seeds murinas escritas a mano. Que exista es
defendible —sin `mature.fa` no hay otra cosa— y ya sale avisada en el informe. Lo que no
era defendible es que el aviso fuera el MISMO con el fichero bueno delante y sin el:

  - sin `mature.fa`, correr con doce seeds es una limitacion que se declara;
  - con `mature.fa` en el deposito y sin conectar, es la tabla EQUIVOCADA.

Los dos daban el mismo texto, asi que el segundo era invisible. `bootstrap_expiry_note`
los separa, y estos tests fijan las dos mitades — que avisa cuando el fichero esta y que
calla cuando no—, que es la disciplina del control adversario: sin la segunda, «avisa
siempre» y «avisa cuando toca» serian el mismo resultado.
"""

import tempfile
import unittest
from pathlib import Path

from shmir_design.seeds import (
    BOOTSTRAP_COUNT,
    BOOTSTRAP_SEED_TABLE,
    REPLACED_BY,
    WHY_AN_EXPIRY,
    bootstrap_expiry_note,
)


class TestLaCaducidad(unittest.TestCase):

    def _carpeta(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def test_sin_el_fichero_de_verdad_NO_avisa(self):
        # La mitad que hace util a la otra: si avisara siempre, el aviso no diria nada.
        self.assertIsNone(bootstrap_expiry_note(self._carpeta()))

    def test_con_el_fichero_de_verdad_AVISA(self):
        d = self._carpeta()
        (d / REPLACED_BY).write_text(">mmu-let-7a-5p\nUGAGGUAGUAGGUUGUAUAGUU\n")
        aviso = bootstrap_expiry_note(d)
        self.assertIsNotNone(aviso)
        self.assertIn("CADUCADA", aviso)
        self.assertIn(REPLACED_BY, aviso)
        self.assertIn(str(d), aviso)

    def test_un_fichero_VACIO_no_es_tener_el_fichero(self):
        # Principio nº 9: existir no es contener. Un `mature.fa` de 0 bytes es la
        # descarga que se corto, no miRBase.
        d = self._carpeta()
        (d / REPLACED_BY).write_text("   \n\n")
        self.assertIsNone(bootstrap_expiry_note(d))

    def test_el_aviso_dice_QUE_HACER_y_no_solo_que_pasa(self):
        d = self._carpeta()
        (d / REPLACED_BY).write_text(">x\nACGU\n")
        self.assertIn("manifiesto", bootstrap_expiry_note(d))

    def test_el_numero_de_seeds_se_DERIVA_de_la_tabla(self):
        filas = [
            l for l in BOOTSTRAP_SEED_TABLE.splitlines()
            if l.strip() and not l.startswith("#")
        ]
        self.assertEqual(BOOTSTRAP_COUNT, len(filas))
        self.assertEqual(BOOTSTRAP_COUNT, 12)

    def test_el_motivo_de_que_haya_caducidad_esta_escrito(self):
        self.assertIn("no lo tenemos", WHY_AN_EXPIRY.lower())


class TestQuienLoEnseña(unittest.TestCase):
    """Un aviso que se calcula y no llega a ninguna salida es media medida."""

    def test_el_informe_de_tilado_lo_llama(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "shmir_design" / "tiling.py"
        ).read_text(encoding="utf-8")
        self.assertIn("bootstrap_expiry_note()", fuente)

    def test_el_bloque_de_avisos_del_informe_lo_llama(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "shmir_design" / "outputs.py"
        ).read_text(encoding="utf-8")
        self.assertIn("bootstrap_expiry_note()", fuente)


if __name__ == "__main__":
    unittest.main()
