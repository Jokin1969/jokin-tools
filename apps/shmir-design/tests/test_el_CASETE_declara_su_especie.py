"""El casete del transgen NO puede ser el de otra especie. Regla 5: escrito antes.

**El agujero que cierra.** `RepeatMask.query_length` protege la mascara: compara lo que
el resumen declara haber analizado contra lo que se le da, y ABORTA. El casete no tenia
nada equivalente, asi que el filtro del transgen corria contra cualquier construccion
que llegara.

Medido antes de escribir esto (errata nº 155), con el casete MURINO sobre el diseño
humano — que es exactamente lo que conectaba el CLI:

    humano, SIN casete (correcto)     transgen por ventana: sin: 2414
    humano, con el casete MURINO      PASS: 415, FAIL: 4, NOT_RUN: 1995

**415 ventanas humanas con un PASS contra una construccion que no es la suya, y 4 con un
FAIL.** Un PASS cuenta como frente contestado y un FAIL retira un candidato: es el
resultado con la forma correcta y el significado equivocado.

**TRES estados y el tercero NO es «coincide»**: la especie del casete puede estar
declarada y coincidir, declarada y NO coincidir —aborta—, o NO estar declarada, y eso
sale DICHO. No haber podido comprobarlo no es que cuadre: es el `.out` sin resumen otra
vez.
"""

import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.resolve import resolve_anatomy
from shmir_design.specificity import (
    CASSETTE_SPECIES_UNDECLARED,
    check_cassette_species,
    load_database,
)
from shmir_design.tiling import tile_utr

DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"
CASETE = DATOS / "aav_casete.fa"
HUMANO = REFERENCES["NM_000311.5"]
RATON = REFERENCES["NM_011170.3"]
HAY = CASETE.is_file() and fixture_available(HUMANO) and fixture_available(RATON)


def _casete(especie: str):
    return load_database(
        CASETE, name="casete del transgén", version="test", species=especie,
    )


@unittest.skipUnless(HAY, "NOT_RUN: falta el casete o algun fixture")
class TestElCaseteDeOtraEspecieABORTA(unittest.TestCase):

    def test_el_casete_MURINO_sobre_un_diseño_humano_aborta(self):
        with self.assertRaises(ShmirDesignError) as caso:
            check_cassette_species(_casete("raton"), species="humano")
        mensaje = str(caso.exception)
        # El motivo nombra LAS DOS especies: «no coincide» a secas no se investiga.
        self.assertIn("Mus musculus", mensaje)
        self.assertIn("Homo sapiens", mensaje)

    def test_y_lo_hace_ANTES_de_emitir_ningun_veredicto(self):
        # El guardia va en la INGESTA, como `RepeatMask.query_length`: si mordiera por
        # ventana, las 415 ya se habrian emitido cuando alguien lo leyera.
        secuencia = load_reference(HUMANO)
        anatomia = resolve_anatomy(
            name="humano", sequence=secuencia, genbank=DATOS / "NM_000311.5.gb",
        )
        with self.assertRaises(ShmirDesignError):
            tile_utr(
                secuencia, anatomy=anatomia, species="humano",
                transgene_db=_casete("raton"),
            )

    def test_el_casete_de_SU_especie_corre(self):
        # Control adversario: abortar SIEMPRE tambien pasaria los dos de arriba.
        self.assertIsNone(check_cassette_species(_casete("raton"), species="raton"))

    def test_y_los_alias_no_lo_rompen(self):
        # `raton`, `ratón` y `Mus musculus` son el mismo `mouse`: la comparacion va por
        # la especie RESUELTA, no por el texto que alguien tecleo.
        self.assertIsNone(
            check_cassette_species(_casete("Mus musculus"), species="raton")
        )


@unittest.skipUnless(HAY, "NOT_RUN: falta el casete o algun fixture")
class TestSinDeclararSeDICE(unittest.TestCase):
    """El tercer estado. No bloquea, y NO se calla."""

    def test_no_aborta(self):
        self.assertIsNotNone(check_cassette_species(_casete(""), species="humano"))

    def test_pero_lo_DICE_y_dice_que_no_es_lo_mismo_que_cuadrar(self):
        aviso = check_cassette_species(_casete(""), species="humano")
        self.assertIn("NO DECLARADA", aviso)
        self.assertEqual(aviso, CASSETTE_SPECIES_UNDECLARED)

    def test_y_el_aviso_VIAJA_a_la_procedencia_del_casete(self):
        # Un aviso que se queda dentro del guardia no lo lee nadie: la procedencia del
        # casete es lo que sale en el informe y en el motivo de cada veredicto.
        self.assertIn("NO DECLARADA", _casete("").provenance)
        self.assertNotIn("NO DECLARADA", _casete("raton").provenance)

    def test_y_la_especie_declarada_sale_en_la_procedencia(self):
        self.assertIn("Mus musculus", _casete("raton").provenance)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
