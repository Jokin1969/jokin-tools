"""El 3'UTR fabricado, archivado como FIXTURE NEGATIVO.

Regla 5: escritos antes de archivarlo.

No se destruye: se guarda. Una errata sin un test que la reproduzca se olvida, y esta
—un 3'UTR de 1246 nt anunciado como 1242— dejo inservible una corrida entera de
miRarchitect y costo varias tandas de hipotesis equivocadas. Es la nº 5 del registro.

Este fichero NO ENTRA AL PIPELINE. Su unico uso es demostrar que la comprobacion que
faltaba lo para. Si algun dia alguien lo pasa por un diseño, hay un test que lo impide.
"""

import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.reference import check_declared_length, sequence_md5

FABRICADO = (
    Path(__file__).resolve().parent.parent
    / "data" / "reference" / "prnp_3utr_fabricado_1246nt.txt"
)
MD5 = "328cfa074a9b002f9614fcce3f19e21f"
LONGITUD = 1246
#: Lo que se anuncio que era. La diferencia es de 4 nt sobre 1242: un 0,3 %.
ANUNCIADA = 1242


def _contenido() -> str:
    return "".join(FABRICADO.read_text(encoding="ascii").split()).upper()


@unittest.skipUnless(FABRICADO.is_file(), f"NOT_RUN: falta {FABRICADO.name}")
class TestElFixtureEsElQueFue(unittest.TestCase):
    """Si el fichero cambia, este test deja de reproducir la errata y lo dice."""

    def test_mide_1246_nt(self):
        self.assertEqual(len(_contenido()), LONGITUD)

    def test_su_md5_es_el_registrado(self):
        self.assertEqual(sequence_md5(_contenido()), MD5)

    def test_y_no_es_el_3utr_de_referencia(self):
        # Obvio, pero conviene que este escrito: son 4 nt de diferencia, no 400.
        self.assertNotEqual(sequence_md5(_contenido()), "19f5fa2a77a87892770e2affdc90e0e4")


@unittest.skipUnless(FABRICADO.is_file(), f"NOT_RUN: falta {FABRICADO.name}")
class TestLaComprobacionQueFaltaba(unittest.TestCase):
    """La reproduccion de la errata nº 5, sobre el dato de verdad."""

    def test_anunciarlo_como_1242_lo_rechaza(self):
        with self.assertRaises(ShmirDesignError) as caja:
            check_declared_length(
                _contenido(), ANUNCIADA, name="3'UTR de Prnp (fabricado)"
            )
        self.assertIn("1246", str(caja.exception))
        self.assertIn("1242", str(caja.exception))

    def test_el_mensaje_dice_que_se_cuenta_lo_entregado(self):
        with self.assertRaises(ShmirDesignError) as caja:
            check_declared_length(_contenido(), ANUNCIADA, name="fabricado")
        self.assertIn("entregada", str(caja.exception).lower())

    def test_anunciarlo_por_su_longitud_de_verdad_pasa(self):
        # La comprobacion no es un veto al fichero: es un veto a la MENTIRA sobre el
        # fichero. Declarado como lo que es, pasa.
        check_declared_length(_contenido(), LONGITUD, name="fabricado")

    def test_un_solo_nucleotido_de_diferencia_ya_lo_para(self):
        with self.assertRaises(ShmirDesignError):
            check_declared_length(_contenido(), LONGITUD - 1, name="fabricado")


@unittest.skipUnless(FABRICADO.is_file(), f"NOT_RUN: falta {FABRICADO.name}")
class TestNoEntraAlPipeline(unittest.TestCase):

    def test_no_esta_registrado_como_transcrito_de_referencia(self):
        from shmir_design.reference import REFERENCES

        self.assertNotIn(MD5, {r.md5 for r in REFERENCES.values()})
        self.assertNotIn(MD5, {r.utr3_md5 for r in REFERENCES.values()})

    def test_el_manifiesto_lo_marca_como_fixture_negativo(self):
        from shmir_design.manifest import parse_manifest

        ruta = FABRICADO.parent / "manifest.tsv"
        manifiesto = parse_manifest(ruta.read_text(encoding="utf-8"), source=str(ruta))
        entrada = manifiesto.find(FABRICADO.name)
        self.assertIsNotNone(entrada)
        self.assertIn("NEGATIVO", entrada.origin.upper())
        self.assertEqual(entrada.length, LONGITUD)


if __name__ == "__main__":
    unittest.main()
