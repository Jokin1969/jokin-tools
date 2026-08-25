"""Tests del puente entre la interfaz y la estimacion de coste.

Regla 5: escritos antes que `presentation.cost_text`.

El boton «Estimar» de la pagina no puede decidir nada: ni que anatomia se declara, ni
que recursos entran en la cuenta, ni que avisos hacen falta cuando algo se queda fuera.
Todo eso vive aqui y se prueba aqui, sin Streamlit de por medio.
"""

import unittest

from shmir_design.masking import RepeatMask
from shmir_design.presentation import cost_text
from shmir_design.resources import ResourceSet
from shmir_design.seed_load import Utr3Set
from shmir_design.specificity import SpecificityDatabase

SONDA = "GCGTCAGTACGATCGAATTACT" * 12


def _utrs():
    return Utr3Set(
        records={"t1": SONDA}, source="sonda", version="v", checksum="0" * 32
    )


def _base():
    return SpecificityDatabase(
        name="sonda", version="v", checksum="0" * 32, records={"diana": SONDA}
    )


class TestCostText(unittest.TestCase):

    def test_dice_que_no_ha_diseñado_nada(self):
        self.assertIn("no se ha diseñado nada", cost_text(SONDA))

    def test_cuenta_las_ventanas_del_3utr_que_se_le_pasa(self):
        texto = cost_text(SONDA)
        self.assertIn(f"ventanas a tilar:        {len(SONDA) - 22 + 1}", texto)

    def test_sin_recursos_no_aparece_ninguna_partida_cara(self):
        texto = cost_text(SONDA)
        for partida in ("especificidad", "transgen", "seed_colision", "carga_seed"):
            with self.subTest(partida):
                self.assertNotIn(partida, texto)

    def test_la_accesibilidad_se_puede_pedir_sin_ningun_fichero(self):
        self.assertIn("accesibilidad", cost_text(SONDA, accessibility=True))

    def test_los_recursos_del_manifiesto_entran_en_la_cuenta(self):
        texto = cost_text(SONDA, resources=ResourceSet(utr3_set=_utrs()))
        self.assertIn("carga_seed", texto)

    def test_la_especificidad_necesita_diana_y_base(self):
        conjunto = ResourceSet(specificity_db=_base(), specificity_target="diana")
        self.assertIn("especificidad", cost_text(SONDA, resources=conjunto))

    def test_una_base_sin_diana_no_estima_especificidad(self):
        # Es el mismo criterio que aplica `tile_utr`: sin diana el filtro no corre, asi
        # que estimar su coste seria presupuestar un trabajo que no se va a hacer.
        self.assertNotIn(
            "especificidad", cost_text(SONDA, resources=ResourceSet(specificity_db=_base()))
        )

    def test_avisa_de_que_la_mascara_no_esta_contada(self):
        # La mascara reduce las ventanas elegibles y la estimacion no la aplica: el
        # numero sale POR ENCIMA. Eso hay que decirlo, no dejarlo implicito.
        conjunto = ResourceSet(
            utr3_set=_utrs(),
            mask=RepeatMask(intervals=((1, 40),), source="sonda"),
        )
        texto = cost_text(SONDA, resources=conjunto)
        self.assertIn("mascara", texto.lower())

    def test_sin_mascara_no_aparece_el_aviso_de_la_mascara(self):
        self.assertNotIn("mascara", cost_text(SONDA, resources=ResourceSet()).lower())

    def test_no_le_pasa_a_estimate_cost_parametros_que_no_entiende(self):
        # `ResourceSet.as_kwargs()` trae `mask`, `expression` y `apa_sites`, que
        # `estimate_cost` no acepta. Splatearlo entero reventaria con TypeError.
        conjunto = ResourceSet(
            utr3_set=_utrs(),
            expression={"t1": 1.0},
            mask=RepeatMask(intervals=((1, 2),), source="sonda"),
        )
        self.assertIn("carga_seed", cost_text(SONDA, resources=conjunto))


if __name__ == "__main__":
    unittest.main()
