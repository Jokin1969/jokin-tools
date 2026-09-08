"""`apa_medido.tsv` se aplica por md5 del 3'UTR, igual que la tabla de PolyA_DB.

Regla 5: escrito antes.

**Los dos ficheros de APA no estaban igual de protegidos**, y son el mismo dato por dos
caminos:

  · `polya_db_<especie>.tsv` EXIGE `utr3_md5` en su cabecera y `resolve_measured`
    devuelve `None` si no cuadra, asi que sobre otra secuencia no promueve nada;
  · `apa_medido_<especie>.tsv` no llevaba NINGUN campo de identidad —`ApaSites` tenia
    `source`, `version` y `checksum` DEL FICHERO— y `apa_assessment` aplica sus
    posiciones, YA CONVERTIDAS a coordenadas de 3'UTR, a lo que se le de.

Unas posiciones murinas sobre el 3'UTR humano **caben**: 1242 contra 1606, asi que no se
salen de rango y no salta ninguna alarma. El techo de knockdown sale con la forma
correcta y referido a otra secuencia.

Hoy el fichero no existe para ninguna especie, o sea que esto es LATENTE — y es
exactamente el que la campaña humana necesita (`apa_medido_human.tsv` esta en la lista de
lo que falta). La primera vez que se use seria la primera vez que se prueba.
"""

import unittest

from shmir_design.apa import (
    APA_SITES_FORMAT,
    apply_measured_sites,
    parse_apa_sites,
)
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_3utr, sequence_md5

RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]
HAY = fixture_available(RATON) and fixture_available(HUMANO)


def _tabla(md5: str) -> str:
    return (
        f"# utr3_md5\t{md5}\n"
        f"# fuente\t3'-end seq de cerebro murino (test)\n"
        f"288\t0.86\tAATAAA proximal\n"
    )


@unittest.skipUnless(HAY, "NOT_RUN: faltan los fixtures")
class TestLaTablaDiceDeQueSecuenciaEs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raton = load_3utr(RATON)
        cls.humano = load_3utr(HUMANO)
        cls.md5_raton = sequence_md5(cls.raton)

    def test_sin_utr3_md5_la_cabecera_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as caso:
            parse_apa_sites(
                "288\t0.86\tAATAAA\n", source="t.tsv", version="v", checksum="c",
            )
        self.assertIn("utr3_md5", str(caso.exception))

    def test_y_el_mensaje_lleva_el_FORMATO_para_poder_arreglarlo(self):
        with self.assertRaises(ShmirDesignError) as caso:
            parse_apa_sites(
                "288\t0.86\tAATAAA\n", source="t.tsv", version="v", checksum="c",
            )
        self.assertIn(APA_SITES_FORMAT.splitlines()[0], str(caso.exception))

    def test_sobre_SU_secuencia_se_aplica(self):
        tabla = parse_apa_sites(
            _tabla(self.md5_raton), source="t.tsv", version="v", checksum="c",
        )
        self.assertIsNotNone(apply_measured_sites(tabla, self.raton))

    def test_sobre_OTRA_secuencia_devuelve_None_y_NO_aplica_nada(self):
        # El control que importa: las posiciones murinas CABEN en el 3'UTR humano
        # —1242 contra 1606— asi que sin este guardia no salta ninguna alarma.
        tabla = parse_apa_sites(
            _tabla(self.md5_raton), source="t.tsv", version="v", checksum="c",
        )
        self.assertGreater(len(self.humano), len(self.raton))
        self.assertIsNone(apply_measured_sites(tabla, self.humano))

    def test_y_el_MOTIVO_dice_de_que_secuencia_ES(self):
        tabla = parse_apa_sites(
            _tabla(self.md5_raton), source="t.tsv", version="v", checksum="c",
        )
        self.assertEqual(tabla.utr3_md5, self.md5_raton)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
