"""`provided` se DERIVA de la secuencia; no se declara.

Existe por un PASS FALSO encontrado en la revision del PR #21. `intron_quimerico`
declaraba `provided=True` en el registro y sacaba su secuencia de un plasmido que el
`.gitignore` de `data/reference/` dejaba FUERA de git. Para cualquiera que clonara el
repositorio el resultado era:

    provided=True   state=PASS   len(raw_sequence)=0

y `require_sequence()` no abortaba con el mensaje de la regla 1 sino con un
`KeyError('')` al buscar una pieza vacia en `blocks.PIECES` — es decir, se saltaba
todos los guardias, incluido el que existe para esto.

Es el mismo patron que el cuarto par duplicado y se cierra igual: no con un test que
compruebe que las dos cosas coinciden, sino con UNA SOLA DEFINICION que impida que
diverjan. `provided` deja de ser un campo y pasa a ser una propiedad calculada.
"""

import unittest

from shmir_design import blocks, introns
from shmir_design.errors import ShmirDesignError


class TestProvistoSeDeriva(unittest.TestCase):
    def test_sin_secuencia_y_sin_piezas_NO_esta_provisto(self):
        huerfano = introns.Intron(
            name="huerfano", description="", source="", raw_sequence=""
        )
        self.assertFalse(huerfano.provided)

    def test_su_estado_es_NOT_RUN_y_no_PASS(self):
        huerfano = introns.Intron(name="huerfano", description="", source="")
        self.assertIs(huerfano.state, introns.FilterState.NOT_RUN)

    def test_require_sequence_aborta_con_el_error_del_proyecto_no_con_KeyError(self):
        huerfano = introns.Intron(name="huerfano", description="", source="")
        with self.assertRaises(ShmirDesignError) as caja:
            huerfano.require_sequence()
        self.assertIn("no se ha aportado", str(caja.exception))

    def test_with_module_tambien_aborta_en_vez_de_dar_KeyError(self):
        huerfano = introns.Intron(name="huerfano", description="", source="")
        with self.assertRaises(ShmirDesignError):
            huerfano.with_module("A" * blocks.MODULE_LENGTH)

    def test_con_secuencia_entera_si_esta_provisto(self):
        aportado = introns.Intron(
            name="aportado", description="", source="", raw_sequence="GTAAGTCTAG"
        )
        self.assertTrue(aportado.provided)

    def test_el_derivado_no_esta_provisto_aunque_tenga_piezas(self):
        self.assertFalse(introns.INTRONS["mvm_sin_criptico"].provided)
        self.assertTrue(introns.INTRONS["mvm_sin_criptico"].derived)

    def test_el_de_piezas_versionadas_si(self):
        self.assertTrue(introns.INTRONS["mvm_actual"].provided)


class TestElQuimericoNoPuedeSerUnPassFalso(unittest.TestCase):
    """Lo que hacia falsa la declaracion: fichero fuera de git."""

    def test_el_plasmido_esta_versionado(self):
        import subprocess

        from shmir_design import trabajo

        ruta = trabajo.reference_dir() / introns.QUIMERICO_PLASMID
        self.assertTrue(ruta.is_file(), f"no esta el plasmido en {ruta}")
        salida = subprocess.run(
            ["git", "check-ignore", "-q", str(ruta)],
            capture_output=True, check=False,
        )
        self.assertNotEqual(
            salida.returncode, 0,
            f"{introns.QUIMERICO_PLASMID} lo ignora git: quien clone el repositorio se "
            f"encuentra `intron_quimerico` sin secuencia",
        )

    def test_provisto_y_secuencia_no_pueden_divergir(self):
        quimerico = introns.INTRONS["intron_quimerico"]
        self.assertEqual(quimerico.provided, bool(quimerico.raw_sequence))

    def test_esta_provisto_y_mide_lo_declarado(self):
        quimerico = introns.INTRONS["intron_quimerico"]
        self.assertTrue(quimerico.provided)
        self.assertEqual(len(quimerico.empty_sequence), 133)


if __name__ == "__main__":
    unittest.main()
