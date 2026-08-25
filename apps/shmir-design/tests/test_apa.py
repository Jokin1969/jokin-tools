"""Tests del APA con sitios medidos (bloque 5).

Regla 5: escritos antes de implementarlo.

No es lo mismo que la zona prohibida. La zona prohibida pregunta si la ventana TOCA una
señal; el APA pregunta si esta POR DETRAS de un sitio de corte, porque entonces la diana
no existe en la isoforma corta y hay un techo de knockdown duro e invisible.

Dato real que motiva el bloque: en el 3'UTR murino el riesgo de APA afecta a 928
ventanas (42,8 %), y si el AATAAA de 288 es funcional esas ventanas tienen ese techo.

Lo que la app no puede resolver sola: si ese sitio se usa o no. Lo que si puede hacer es
aceptar el dato medido y, cuando esta, sustituir la prediccion por el. Cuando no esta,
`riesgo_APA` sigue siendo una PREDICCION y el informe lo dice con esas palabras.

Geometria: un sitio medido ES el sitio de corte, no el hexamero. No hay que sumarle los
10-30 nt; esa correccion es para las señales predichas.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design.apa import (
    ApaSite,
    ApaSites,
    apa_assessment,
    load_apa_sites,
    parse_apa_sites,
)
from shmir_design.errors import ChecksumMismatchError, ShmirDesignError

TABLA = """\
# sitios de poliadenilacion medidos, coordenadas de 3'UTR
# posicion<TAB>fraccion<TAB>nombre
288\t0.35\tsitio_proximal
1242\t0.65\tsitio_distal
"""


def _sitios(*sitios: ApaSite) -> ApaSites:
    return ApaSites(
        sites=sitios or (ApaSite(288, 0.35, "proximal"), ApaSite(1242, 0.65, "distal")),
        source="sonda",
        version="sonda",
        checksum="0" * 32,
        coords="3utr",
    )


class TestLectura(unittest.TestCase):

    def test_lee_los_dos_sitios(self):
        s = parse_apa_sites(TABLA, source="s", version="v", checksum="0" * 32)
        self.assertEqual(len(s.sites), 2)

    def test_lee_posicion_y_fraccion(self):
        s = parse_apa_sites(TABLA, source="s", version="v", checksum="0" * 32)
        self.assertEqual(s.sites[0].position, 288)
        self.assertAlmostEqual(s.sites[0].fraction, 0.35)

    def test_el_nombre_es_opcional(self):
        s = parse_apa_sites("288\t0.35\n", source="s", version="v", checksum="0" * 32)
        self.assertEqual(len(s.sites), 1)

    def test_una_fraccion_fuera_de_0_1_aborta(self):
        with self.assertRaises(ShmirDesignError):
            parse_apa_sites("288\t1.5\n", source="s", version="v", checksum="0" * 32)

    def test_una_fraccion_no_numerica_aborta(self):
        with self.assertRaises(ShmirDesignError):
            parse_apa_sites("288\tmucho\n", source="s", version="v", checksum="0" * 32)

    def test_las_fracciones_que_suman_mas_de_1_abortan(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_apa_sites(
                "288\t0.7\n1242\t0.7\n", source="s", version="v", checksum="0" * 32
            )
        self.assertIn("1.4", str(ctx.exception))

    def test_un_fichero_sin_sitios_aborta(self):
        with self.assertRaises(ShmirDesignError):
            parse_apa_sites("# nada\n", source="s", version="v", checksum="0" * 32)

    def test_la_procedencia_es_obligatoria(self):
        with self.assertRaises(ValueError):
            parse_apa_sites(TABLA, source="s", version="", checksum="0" * 32)

    def test_las_coordenadas_se_declaran(self):
        s = parse_apa_sites(
            TABLA, source="s", version="v", checksum="0" * 32, coords="transcrito"
        )
        self.assertEqual(s.coords, "transcrito")

    def test_un_sistema_de_coordenadas_desconocido_aborta(self):
        with self.assertRaises(ValueError):
            parse_apa_sites(
                TABLA, source="s", version="v", checksum="0" * 32, coords="genomicas"
            )


class TestSinDatoMedido(unittest.TestCase):

    def test_sin_sitios_el_riesgo_sigue_siendo_prediccion(self):
        a = apa_assessment(window_start=500, sites=None, predicted_risk=True)
        self.assertFalse(a.measured)
        self.assertTrue(a.risk)

    def test_y_se_dice_con_esas_palabras(self):
        a = apa_assessment(window_start=500, sites=None, predicted_risk=True)
        self.assertIn("prediccion", a.reason.lower())

    def test_sin_sitios_no_hay_fraccion_perdida(self):
        a = apa_assessment(window_start=500, sites=None, predicted_risk=True)
        self.assertIsNone(a.lost_fraction)

    def test_sin_riesgo_predicho_tampoco_hay_riesgo(self):
        a = apa_assessment(window_start=100, sites=None, predicted_risk=False)
        self.assertFalse(a.risk)


class TestConDatoMedido(unittest.TestCase):

    def test_el_dato_sustituye_a_la_prediccion(self):
        a = apa_assessment(window_start=100, sites=_sitios(), predicted_risk=True)
        self.assertTrue(a.measured)
        self.assertFalse(a.risk)

    def test_una_ventana_por_detras_de_un_sitio_pierde_esa_fraccion(self):
        a = apa_assessment(window_start=500, sites=_sitios(), predicted_risk=False)
        self.assertTrue(a.risk)
        self.assertAlmostEqual(a.lost_fraction, 0.35)

    def test_una_ventana_delante_de_todos_los_sitios_no_pierde_nada(self):
        a = apa_assessment(window_start=100, sites=_sitios(), predicted_risk=True)
        self.assertAlmostEqual(a.lost_fraction, 0.0)

    def test_el_techo_de_knockdown_es_lo_que_queda(self):
        a = apa_assessment(window_start=500, sites=_sitios(), predicted_risk=False)
        self.assertAlmostEqual(a.knockdown_ceiling, 0.65)

    def test_varias_perdidas_se_suman(self):
        sitios = _sitios(
            ApaSite(100, 0.2, "a"), ApaSite(200, 0.3, "b"), ApaSite(1242, 0.5, "c")
        )
        a = apa_assessment(window_start=500, sites=sitios, predicted_risk=False)
        self.assertAlmostEqual(a.lost_fraction, 0.5)

    def test_una_ventana_justo_en_el_sitio_no_esta_por_detras(self):
        a = apa_assessment(window_start=288, sites=_sitios(), predicted_risk=False)
        self.assertAlmostEqual(a.lost_fraction, 0.0)

    def test_el_motivo_dice_que_es_dato_medido_no_prediccion(self):
        a = apa_assessment(window_start=500, sites=_sitios(), predicted_risk=False)
        self.assertIn("medido", a.reason.lower())
        self.assertNotIn("prediccion", a.reason.lower())

    def test_el_motivo_nombra_la_procedencia(self):
        a = apa_assessment(window_start=500, sites=_sitios(), predicted_risk=False)
        self.assertIn("sonda", a.reason)

    def test_la_columna_es_el_techo_cuando_hay_dato(self):
        a = apa_assessment(window_start=500, sites=_sitios(), predicted_risk=False)
        self.assertEqual(a.as_column(), "0.65")

    def test_la_columna_dice_prediccion_cuando_no_lo_hay(self):
        a = apa_assessment(window_start=500, sites=None, predicted_risk=True)
        self.assertEqual(a.as_column(), "prediccion:si")


class TestSinFraccionDeLecturas(unittest.TestCase):
    """PolyA_DB no siempre trae la fraccion. Sin ella hay sitio pero no techo."""

    SIN_FRACCION = ApaSites(
        sites=(ApaSite(288, None, "proximal"),),
        source="sonda",
        version="sonda",
        checksum="0" * 32,
        coords="3utr",
    )

    def test_hay_riesgo_pero_no_numero(self):
        a = apa_assessment(
            window_start=500, sites=self.SIN_FRACCION, predicted_risk=False
        )
        self.assertTrue(a.risk)
        self.assertIsNone(a.lost_fraction)

    def test_el_motivo_dice_que_falta_la_fraccion(self):
        a = apa_assessment(
            window_start=500, sites=self.SIN_FRACCION, predicted_risk=False
        )
        self.assertIn("fraccion", a.reason.lower())

    def test_no_se_inventa_un_techo(self):
        a = apa_assessment(
            window_start=500, sites=self.SIN_FRACCION, predicted_risk=False
        )
        self.assertIsNone(a.knockdown_ceiling)


class TestCargaDesdeDisco(unittest.TestCase):

    def test_lee_el_fichero(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "apa.tsv"
            p.write_text(TABLA, encoding="utf-8")
            self.assertEqual(len(load_apa_sites(p, version="v").sites), 2)

    def test_un_md5_que_no_cuadra_aborta(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "apa.tsv"
            p.write_text(TABLA, encoding="utf-8")
            with self.assertRaises(ChecksumMismatchError):
                load_apa_sites(p, version="v", expected_md5="0" * 32)

    def test_un_fichero_ausente_aborta_diciendo_cual(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            load_apa_sites(Path("/no/existe/apa.tsv"), version="v")
        self.assertIn("apa.tsv", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
