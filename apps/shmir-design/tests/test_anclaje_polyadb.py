"""El mapeo genomico↔transcrito, resuelto SIN coordenadas genomicas.

Regla 5: escritos antes.

El desempate lo aporta la propia leyenda de PolyA_DB: «A[A/U]UAAA motif within 40-nt
upstream from the PAS». El hexamero se busca AGUAS ARRIBA del PAS, luego la coordenada
que publica la base es el SITIO DE CORTE, no el hexamero. Las dos lecturas dan mapeos
distintos y hasta ahora no habia con que elegir; con esta, si.

Y la eleccion no se hace por una resta, que seria un solo punto de apoyo. Se hace
comprobando las CUATRO coordenadas de PolyA_DB a la vez contra la secuencia que ya
esta en el repositorio, exigiendo ademas que la CLASE de hexamero que declara la base
(AAUAAA / AUUAAA / Other) coincida con la del hexamero que encontramos:

    131937444  Other     131937504  AAUAAA     131938392  Other     131938427  AUUAAA

Bajo «PAS = corte» las cuatro cuadran con un mismo desfase. Bajo «PAS = hexamero» el
aterrizaje tiene que ser EXACTO —un hexamero es un punto, no una banda— y no hay ningun
desfase que haga aterrizar mas de UNA de las cuatro. Eso mata la hipotesis.
"""

import unittest

from shmir_design import polya
from shmir_design.apa import (
    MappingHypothesis,
    PasAnchor,
    anchor_polyadb,
    polyadb_class,
)
from shmir_design.reference import REFERENCES, load_3utr, fixture_available
from tests.tabla_medida import TABLA


def _utr3():
    return load_3utr(REFERENCES["NM_011170.3"])


class TestLaLeyendaDePolyADB(unittest.TestCase):
    """La semantica del PAS va escrita, con la cita de la leyenda."""

    def test_la_leyenda_va_citada_literal(self):
        self.assertIn("40-nt upstream", polya.PAS_IS_CLEAVAGE_SITE)

    def test_dice_que_el_PAS_es_el_CORTE_y_no_el_hexamero(self):
        texto = polya.PAS_IS_CLEAVAGE_SITE.upper()
        self.assertIn("CORTE", texto)
        self.assertIn("NO EL HEXÁMERO", texto)


class TestLaClaseDeHexamero(unittest.TestCase):
    """La base etiqueta en ARN; nosotros buscamos en ADN. Se traduce, no se supone."""

    def test_la_canonica_es_AAUAAA(self):
        self.assertEqual(polyadb_class("AATAAA"), "AAUAAA")

    def test_la_variante_fuerte_es_AUUAAA(self):
        self.assertEqual(polyadb_class("ATTAAA"), "AUUAAA")

    def test_las_raras_son_Other(self):
        for motivo in ("AATATA", "TATAAA", "ACTAAA", "CATAAA"):
            self.assertEqual(polyadb_class(motivo), "Other", motivo)

    def test_un_motivo_desconocido_ABORTA(self):
        with self.assertRaises(ValueError):
            polyadb_class("GGGGGG")


@unittest.skipUnless(
    fixture_available(REFERENCES["NM_011170.3"]),
    "falta data/reference/NM_011170.3.fa",
)
class TestElAnclaje(unittest.TestCase):

    def setUp(self):
        self.utr3 = _utr3()
        self.resultado = anchor_polyadb(self.utr3, TABLA.anchors)

    def test_gana_la_hipotesis_del_CORTE(self):
        self.assertIs(self.resultado.hypothesis, MappingHypothesis.CORTE)

    def test_la_del_HEXAMERO_no_aterriza_en_mas_de_UNA_de_las_cuatro(self):
        self.assertLessEqual(self.resultado.hexamer_best, 1)

    def test_la_del_CORTE_aterriza_en_las_CUATRO(self):
        self.assertEqual(self.resultado.cleavage_anchored, 4)

    def test_no_es_una_resta_sino_CUATRO_puntos_independientes(self):
        # Un solo punto de apoyo siempre "cuadra": lo que demuestra algo es que los
        # cuatro cuadren con el MISMO desfase.
        self.assertGreaterEqual(len(self.resultado.anchors), 4)
        self.assertTrue(self.resultado.offsets)

    def test_el_desfase_queda_ACOTADO_no_fijado(self):
        # La banda de corte tiene 20 nt de ancho, asi que el desfase sale como un
        # intervalo. Fijarlo en un entero seria inventarse precision.
        self.assertGreater(len(self.resultado.offsets), 1)
        self.assertLess(len(self.resultado.offsets), 25)

    def test_el_AATAAA_de_288_es_el_de_131937504(self):
        sitio = self.resultado.by_locus("chr2:+:131937504")
        self.assertEqual(sitio.motif, "AATAAA")
        self.assertEqual(sitio.hexamer_start, 288)

    def test_el_tercer_PAS_es_el_AATATA_de_236_y_NO_hay_nada_en_198_208(self):
        sitio = self.resultado.by_locus("chr2:+:131937444")
        self.assertEqual(sitio.motif, "AATATA")
        self.assertEqual(sitio.hexamer_start, 236)
        # Lo que se pidio buscar era 3utr:198-208. Ahi no hay ninguna señal conocida:
        # la ventana de busqueda estaba corrida, no el razonamiento.
        for pos in range(190, 236):
            self.assertNotIn(self.utr3[pos - 1:pos + 5], polya.ALL_SIGNALS, f"3utr:{pos}")

    def test_el_terminal_131938427_es_el_ATTAAA_de_1214(self):
        sitio = self.resultado.by_locus("chr2:+:131938427")
        self.assertEqual(sitio.motif, "ATTAAA")
        self.assertEqual(sitio.hexamer_start, 1214)

    def test_131938392_y_131938427_siguen_siendo_DOS_sitios(self):
        a = self.resultado.by_locus("chr2:+:131938392")
        b = self.resultado.by_locus("chr2:+:131938427")
        # Ninguno de los hexameros posibles de 392 es el de 427, asi que el anclaje
        # tampoco da motivo para fusionarlos.
        self.assertNotIn(b.hexamer_start, [pos for pos, _ in a.candidates])

    def test_131938392_es_AMBIGUO_y_por_eso_NO_entra_al_modelo(self):
        # Dos TATAAA de su clase caben en su banda. El anclaje se sostiene igual —el
        # desfase sigue acotado—, pero ese sitio no identifica UN hexamero, asi que no
        # se le da banda de corte propia. No se elige por nuestra cuenta.
        sitio = self.resultado.by_locus("chr2:+:131938392")
        self.assertTrue(sitio.ambiguous)
        self.assertEqual(len(sitio.candidates), 2)
        with self.assertRaises(ValueError):
            sitio.cleavage_band

    def test_los_TRES_que_importan_NO_son_ambiguos(self):
        for locus in ("chr2:+:131937444", "chr2:+:131937504", "chr2:+:131938427"):
            self.assertFalse(self.resultado.by_locus(locus).ambiguous, locus)

    def test_la_clase_declarada_por_la_base_coincide_en_los_CUATRO(self):
        for sitio in self.resultado.anchors:
            for _, motivo in sitio.candidates:
                self.assertEqual(
                    polyadb_class(motivo), sitio.declared_class, sitio.locus
                )

    def test_la_banda_de_corte_sale_de_NUESTRA_convencion(self):
        sitio = self.resultado.by_locus("chr2:+:131937444")
        self.assertEqual(
            sitio.cleavage_band,
            (236 + 5 + polya.CLEAVAGE_MIN, 236 + 5 + polya.CLEAVAGE_MAX),
        )

    def test_el_anclaje_se_NIEGA_sobre_otra_secuencia(self):
        # La tabla es de Prnp murino. Sobre el 3'UTR humano no se ancla nada: si
        # anclara, estaria anclando ruido.
        humano = REFERENCES["NM_000311.5"]
        if not fixture_available(humano):
            self.skipTest("falta data/reference/NM_000311.5.fa")
        otro = anchor_polyadb(load_3utr(humano), TABLA.anchors)
        self.assertIs(otro.hypothesis, MappingHypothesis.SIN_RESOLVER)
        self.assertLess(otro.cleavage_anchored, 4)

    def test_describe_dice_que_hipotesis_se_descarta_y_por_que(self):
        texto = "\n".join(self.resultado.describe())
        self.assertIn("CORTE", texto)
        self.assertIn("DESCARTADA", texto)
        self.assertIn("40-nt upstream", texto)


@unittest.skipUnless(
    fixture_available(REFERENCES["NM_011170.3"]),
    "falta data/reference/NM_011170.3.fa",
)
class TestLoQueDejaDeEstarPendiente(unittest.TestCase):

    def test_la_conversion_YA_NO_esta_pendiente(self):
        for p in TABLA.pending:
            self.assertNotIn("AQUÍ NO SE PUEDE HACER", p)

    def test_el_racimo_terminal_SIGUE_anotado_como_RESERVA(self):
        # Deja de ser una comprobacion BLOQUEANTE porque no mueve el valor, pero no
        # desaparece: una reserva que no bloquea sigue siendo una reserva.
        self.assertTrue(any("fusionan" in c for c in TABLA.caveats))

    def test_la_tabla_declara_a_QUE_secuencia_se_refiere(self):
        self.assertEqual(
            TABLA.utr3_md5, REFERENCES["NM_011170.3"].utr3_md5
        )


class TestElAnclajeEsAuditable(unittest.TestCase):

    def test_un_anclaje_necesita_locus_y_clase(self):
        with self.assertRaises(ValueError):
            PasAnchor(locus="", genomic=1, declared_class="Other")
        with self.assertRaises(ValueError):
            PasAnchor(locus="chr2:+:1", genomic=1, declared_class="AAUAAA_o_lo_que_sea")


if __name__ == "__main__":
    unittest.main()
