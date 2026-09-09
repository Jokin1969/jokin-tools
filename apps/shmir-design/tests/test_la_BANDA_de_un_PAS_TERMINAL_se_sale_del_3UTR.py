"""La banda de corte de un PAS terminal se sale del 3'UTR, y eso NO es un error.

El corte cae 10-30 nt aguas abajo de un hexamero que en un sitio terminal ya esta
pegado al final, asi que la banda desborda el extremo anotado. La regla del proyecto
para esto ya estaba escrita —«se recorta a lo que hay y se CUENTA lo que se sale, en
vez de abortar la conversion con una posicion que no existe»— y protegia UNA linea, la
del mapa. `AnchoredSite.describe` no la tenia.

Y NO SE VEIA POR UNA COINCIDENCIA: `coords.max_utr3()` deriva su techo del 3'UTR mas
largo del proyecto, que es el HUMANO (1606 nt). La banda murina llega a 3utr:1249 sobre
un 3'UTR de 1242 —o sea que YA se salia— y pasaba porque 1249 < 1606. La humana llega a
1617 y aborta la corrida entera. El invariante caza lo IMPOSIBLE, no lo equivocado.
"""

from __future__ import annotations

import unittest

from shmir_design import apa, reference
from shmir_design.reference import REFERENCES, load_3utr
from tests.tabla_medida import TABLA


def _anclado(accession: str, anclas):
    utr3 = reference.canonical_form(load_3utr(REFERENCES[accession]), name="3'UTR")
    return utr3, apa.anchor_polyadb(utr3, anclas)


#: Las cuatro del 3'UTR humano con clase declarada. Las cifras son de las tablas de
#: PolyA_DB v4 aportadas el 2026-09-09; aqui no se calcula ninguna.
HUMANAS = (
    apa.PasAnchor("chr20:+:4700235", 4700235, "Other", pse=0.041, avgrpm=0.26),
    apa.PasAnchor("chr20:+:4700961", 4700961, "AUUAAA", pse=0.418, avgrpm=0.67),
    apa.PasAnchor("chr20:+:4701170", 4701170, "AUUAAA", pse=0.008, avgrpm=0.19),
    apa.PasAnchor("chr20:+:4701587", 4701587, "AUUAAA", pse=0.937, avgrpm=156.20),
)


class TestLaBandaSeRecortaYSeDice(unittest.TestCase):

    def setUp(self):
        self.utr3, self.anclaje = _anclado("NM_000311.5", HUMANAS)
        self.terminal = self.anclaje.by_locus("chr20:+:4701587")

    def test_el_anclaje_SIGUE_cerrando(self):
        # El recorte es de EMISION: no puede mover el anclaje.
        self.assertIs(self.anclaje.hypothesis, apa.MappingHypothesis.CORTE)
        self.assertEqual(self.anclaje.cleavage_anchored, 4)

    def test_la_banda_NO_pasa_del_final_del_3UTR(self):
        self.assertEqual(self.terminal.cleavage_band[1], len(self.utr3))

    def test_el_inicio_de_la_banda_NO_se_toca(self):
        # Solo desborda el extremo. Recortar el inicio seria inventarse otra cosa.
        sin_recortar = self.terminal.hexamer_end + apa.polya.CLEAVAGE_MIN
        self.assertEqual(self.terminal.cleavage_band[0], sin_recortar)

    def test_y_SE_DICE_que_esta_recortada(self):
        # Callarlo dejaria una banda de 10 nt donde el modelo pone 20, con la forma
        # correcta: el lector no puede distinguir «acaba ahi» de «no cabe».
        self.assertTrue(self.terminal.band_clipped)
        self.assertIn("recortada", self.terminal.describe().lower())
        self.assertIn(str(len(self.utr3)), self.terminal.describe())

    def test_describe_NO_ABORTA_sobre_el_3UTR_humano(self):
        # Es la regresion: antes reventaba con «3utr:1617 no cabe en ningun 3'UTR».
        texto = "\n".join(self.anclaje.describe())
        for ancla in HUMANAS:
            self.assertIn(ancla.locus, texto)

    def test_los_que_NO_desbordan_no_dicen_nada(self):
        # Un aviso que sale siempre deja de leerse.
        for locus in ("chr20:+:4700235", "chr20:+:4700961", "chr20:+:4701170"):
            sitio = self.anclaje.by_locus(locus)
            self.assertFalse(sitio.band_clipped)
            self.assertNotIn("recortada", sitio.describe().lower())


class TestElMurinoTambienSeSalia(unittest.TestCase):
    """No es un caso humano: el terminal murino desbordaba desde el primer dia."""

    def setUp(self):
        self.utr3, self.anclaje = _anclado(
            "NM_011170.3", TABLA.anchors
        )
        self.terminal = self.anclaje.by_locus("chr2:+:131938427")

    def test_su_banda_llegaba_a_1249_sobre_un_3UTR_de_1242(self):
        sin_recortar = self.terminal.hexamer_end + apa.polya.CLEAVAGE_MAX
        self.assertEqual(len(self.utr3), 1242)
        self.assertEqual(sin_recortar, 1249)

    def test_y_ahora_se_recorta_igual(self):
        self.assertTrue(self.terminal.band_clipped)
        self.assertEqual(self.terminal.cleavage_band, (1229, 1242))

    def test_NINGUN_valor_de_la_fraccion_se_mueve(self):
        # El recorte es de emision. Si moviera una cifra, seria otra cosa.
        t = TABLA
        self.assertAlmostEqual(t.working_value, 0.855834, places=6)
        self.assertAlmostEqual(t.unweighted_value, 0.649606, places=6)


class TestLosTRAMOSdeTECHOnoDependenDelRecorte(unittest.TestCase):
    """Los tramos se construyen con los PROXIMALES, y ninguno desborda."""

    def test_las_fronteras_no_se_mueven(self):
        utr3 = reference.canonical_form(
            load_3utr(REFERENCES["NM_011170.3"]), name="3'UTR"
        )
        medido = apa.resolve_measured(utr3, TABLA)
        self.assertEqual(medido.earliest_cut, 251)
        self.assertEqual(medido.layers[0].start_range, (1, 251))
        self.assertEqual(medido.layers[-1].start_range[1], len(utr3))


if __name__ == "__main__":
    unittest.main()
