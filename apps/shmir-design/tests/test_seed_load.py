"""Tests de la carga de off-targets mediados por seed (bloque 1b).

Regla 5: escritos antes que `shmir_design/seed_load.py`.

Es una pregunta distinta de la colision (1a). Alli se pregunta si la guia comparte seed
con un miARN endogeno; aqui, dando por bueno que no colisiona con nadie, cuantos
transcritos quedaran reprimidos por complementariedad de seed sola. El sitio
complementario de un 7-mero aparece por azar cada ~16 kb: hay miles, y ningun alineador
los devuelve, asi que la especificidad del bloque 12 no los ve.

El resultado NO es PASS/FAIL. Es un numero comparativo entre candidatos, para desempatar
en la tabla del bloque 6 — que es justo lo que falta ahora, porque la asimetria no dice
nada sobre esto.

Geometria de los tres tipos, sobre la DIANA:
  7mer-m8  complemento inverso de las posiciones 2-8 de la guia
  7mer-A1  complemento inverso de las posiciones 2-7, seguido de una A
  8mer     complemento inverso de las posiciones 2-8, seguido de una A
"""

import unittest

from shmir_design.filters import FilterState
from shmir_design.seed_load import (
    Utr3Set,
    seed_load,
    site_patterns,
)

#: Guia de prueba de 22 nt. Posiciones 2-8 = AAGGCAC (seed real de miR-124-3p).
GUIA = "TAAGGCACGGGGGGGGGGGGG"
#: complemento inverso de AAGGCAC
SITIO_M8 = "GTGCCTT"
#: complemento inverso de AAGGCA (posiciones 2-7) + A
SITIO_A1 = "TGCCTTA"


def _utrs(**secuencias) -> Utr3Set:
    return Utr3Set(
        records=dict(secuencias),
        source="sonda",
        version="sonda",
        checksum="0" * 32,
    )


class TestPatrones(unittest.TestCase):

    def test_el_7mer_m8_es_el_complemento_inverso_de_las_2_8(self):
        self.assertEqual(site_patterns(GUIA)["7mer-m8"], SITIO_M8)

    def test_el_8mer_es_el_7mer_m8_mas_una_A(self):
        p = site_patterns(GUIA)
        self.assertEqual(p["8mer"], p["7mer-m8"] + "A")

    def test_el_7mer_A1_es_el_de_las_2_7_mas_una_A(self):
        self.assertEqual(site_patterns(GUIA)["7mer-A1"], SITIO_A1)

    def test_los_tres_patrones_estan(self):
        self.assertEqual(
            set(site_patterns(GUIA)), {"7mer-m8", "7mer-A1", "8mer"}
        )

    def test_una_guia_corta_aborta(self):
        with self.assertRaises(ValueError):
            site_patterns("TAAG")

    def test_una_guia_con_N_en_la_seed_aborta(self):
        with self.assertRaises(ValueError):
            site_patterns("TAAGGNACGGGGGGGGGGGGG")


class TestRecuento(unittest.TestCase):

    def test_cuenta_un_sitio_7mer_m8(self):
        carga = seed_load(GUIA, _utrs(t1="CCCC" + SITIO_M8 + "CCCC"))
        self.assertEqual(carga.counts["7mer-m8"], 1)

    def test_un_8mer_no_se_cuenta_ademas_como_7mer_m8(self):
        """Los tipos son excluyentes: un 8mer es un 8mer, no dos sitios."""
        carga = seed_load(GUIA, _utrs(t1="CCCC" + SITIO_M8 + "ACCC"))
        self.assertEqual(carga.counts["8mer"], 1)
        self.assertEqual(carga.counts["7mer-m8"], 0)

    def test_cuenta_un_7mer_A1(self):
        carga = seed_load(GUIA, _utrs(t1="CCCC" + SITIO_A1 + "CCCC"))
        self.assertEqual(carga.counts["7mer-A1"], 1)

    def test_cuenta_en_todos_los_transcritos(self):
        carga = seed_load(
            GUIA,
            _utrs(t1="CCCC" + SITIO_M8 + "CCCC", t2="GGGG" + SITIO_M8 + "GGGG"),
        )
        self.assertEqual(carga.counts["7mer-m8"], 2)

    def test_cuenta_varios_sitios_en_el_mismo_transcrito(self):
        carga = seed_load(
            GUIA, _utrs(t1="CC" + SITIO_M8 + "CC" + SITIO_M8 + "CC")
        )
        self.assertEqual(carga.counts["7mer-m8"], 2)

    def test_sin_ningun_sitio_el_total_es_cero(self):
        carga = seed_load(GUIA, _utrs(t1="CCCCCCCCCCCCCCCCCCCC"))
        self.assertEqual(carga.total, 0)

    def test_el_total_suma_los_tres_tipos(self):
        carga = seed_load(
            GUIA,
            _utrs(t1=SITIO_M8 + "CCC" + SITIO_A1 + "CCC" + SITIO_M8 + "A"),
        )
        self.assertEqual(carga.total, sum(carga.counts.values()))
        self.assertEqual(carga.total, 3)

    def test_cuenta_tambien_los_transcritos_tocados(self):
        carga = seed_load(
            GUIA, _utrs(t1=SITIO_M8 + "CC" + SITIO_M8, t2="CCCCCCCC")
        )
        self.assertEqual(carga.transcripts_hit, 1)


class TestPonderacionPorExpresion(unittest.TestCase):

    def test_sin_tabla_de_expresion_no_hay_numero_ponderado(self):
        carga = seed_load(GUIA, _utrs(t1=SITIO_M8))
        self.assertIsNone(carga.weighted)

    def test_con_tabla_pondera_por_transcrito(self):
        carga = seed_load(
            GUIA,
            _utrs(t1=SITIO_M8, t2=SITIO_M8),
            expression={"t1": 100.0, "t2": 1.0},
        )
        self.assertEqual(carga.weighted, 101.0)

    def test_un_transcrito_sin_dato_de_expresion_no_se_inventa(self):
        carga = seed_load(
            GUIA, _utrs(t1=SITIO_M8, t2=SITIO_M8), expression={"t1": 100.0}
        )
        self.assertEqual(carga.weighted, 100.0)
        self.assertIn("t2", carga.sin_expresion)

    def test_lo_que_falta_se_dice_en_el_texto(self):
        carga = seed_load(
            GUIA, _utrs(t1=SITIO_M8, t2=SITIO_M8), expression={"t1": 100.0}
        )
        self.assertIn("1 transcrito", carga.format_text())


class TestEstadoYSalida(unittest.TestCase):

    def test_sin_transcriptoma_el_estado_es_NOT_RUN(self):
        carga = seed_load(GUIA, None)
        self.assertIs(carga.state, FilterState.NOT_RUN)

    def test_sin_transcriptoma_no_hay_numero(self):
        self.assertIsNone(seed_load(GUIA, None).total)

    def test_con_transcriptoma_el_estado_es_PASS_nunca_FAIL(self):
        """Es un numero comparativo, no un veredicto: nunca descarta a nadie."""
        for secuencia in ("CCCC", SITIO_M8 * 50):
            carga = seed_load(GUIA, _utrs(t1=secuencia))
            self.assertIs(carga.state, FilterState.PASS)

    def test_el_campo_de_la_tabla_va_vacio_si_no_corrio(self):
        self.assertEqual(seed_load(GUIA, None).as_column(), "")

    def test_el_campo_de_la_tabla_es_el_numero(self):
        carga = seed_load(GUIA, _utrs(t1=SITIO_M8))
        self.assertEqual(carga.as_column(), "1")

    def test_el_texto_lleva_la_procedencia(self):
        self.assertIn("sonda", seed_load(GUIA, _utrs(t1="CC")).format_text())

    def test_el_texto_explica_que_esto_no_lo_ve_ningun_alineador(self):
        texto = seed_load(GUIA, _utrs(t1="CC")).format_text()
        self.assertIn("alineador", texto.lower())

    def test_el_desglose_por_tipo_sale_en_el_texto(self):
        texto = seed_load(GUIA, _utrs(t1=SITIO_M8)).format_text()
        for tipo in ("7mer-m8", "7mer-A1", "8mer"):
            self.assertIn(tipo, texto)


class TestProcedencia(unittest.TestCase):

    def test_el_conjunto_de_3utr_exige_procedencia(self):
        for campo in ("source", "version", "checksum"):
            kwargs = dict(
                records={"t1": "CC"}, source="s", version="v", checksum="0" * 32
            )
            kwargs[campo] = ""
            with self.assertRaises(ValueError):
                Utr3Set(**kwargs)

    def test_un_conjunto_vacio_aborta(self):
        with self.assertRaises(Exception):
            Utr3Set(records={}, source="s", version="v", checksum="0" * 32)


if __name__ == "__main__":
    unittest.main()
