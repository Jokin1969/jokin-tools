"""Indels de posicion ambigua, y el tercer estado que hacen falta.

Regla 5: escritos antes.

Un indel dentro de una carrera de bases identicas no tiene posicion. `AAA` → `AAAA` es
la misma pareja de cadenas se meta la A donde se meta, y el alineador la coloca en un
punto cualquiera de la carrera. Preguntar «¿esa diferencia cae dentro de esta ventana?»
no siempre tiene respuesta, y ahi hacen falta tres estados y no dos:

- `LIMPIA`         ninguna diferencia dentro de los 22 nt
- `TOCADA`         diferencia de posicion inequivoca dentro de la ventana; o una
                   ambigua cuya carrera cabe ENTERA dentro, que tambien esta dentro
                   se ponga donde se ponga
- `INDETERMINADA`  la carrera de una diferencia ambigua cruza el borde de la ventana:
                   no se puede afirmar si cae dentro o fuera

No es una excepcion para el sitio 221: es la forma correcta de preguntarlo.
"""

import unittest
from pathlib import Path

from shmir_design.alignment import align

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON, FABRICADO = DIR / "NM_011170.3.fa", DIR / "prnp_3utr_fabricado_1246nt.txt"


def _utr3() -> str:
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.polya import normalize_sequence

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    return normalize_sequence(bruta, name="NM_011170.3")[949:]


class TestDeteccionDeAmbiguedad(unittest.TestCase):

    def test_una_delecion_dentro_de_una_carrera_es_ambigua(self):
        diferencias = align("CCAAAATT", "CCAAATT").differences
        self.assertTrue(diferencias[0].ambiguous)

    def test_y_su_carrera_abarca_las_cuatro_A(self):
        diferencia = align("CCAAAATT", "CCAAATT").differences[0]
        self.assertEqual((diferencia.run_start, diferencia.run_end), (3, 6))

    def test_una_insercion_junto_a_una_carrera_tambien(self):
        diferencia = align("CCAAATT", "CCAAAATT").differences[0]
        self.assertTrue(diferencia.ambiguous)

    def test_un_indel_de_posicion_inequivoca_NO_es_ambiguo(self):
        # La G esta sola: quitarla de otro sitio daria otra cadena.
        diferencia = align("CCAGATT", "CCAATT").differences[0]
        self.assertFalse(diferencia.ambiguous)
        self.assertEqual((diferencia.run_start, diferencia.run_end), (4, 4))

    def test_una_sustitucion_nunca_es_ambigua(self):
        diferencia = align("CCAAAATT", "CCAAGATT").differences[0]
        self.assertFalse(diferencia.ambiguous)

    def test_una_carrera_de_dos_ya_hace_ambiguo_el_indel(self):
        self.assertTrue(align("CCAATT", "CCATT").differences[0].ambiguous)


class TestClasificacionDeVentana(unittest.TestCase):

    def _clasificar(self, ref, otra, inicio, ventana):
        from shmir_design.transfer import classify_window

        return classify_window(
            start=inicio, window=ventana, alignment=align(ref, otra)
        )

    def test_sin_diferencias_cerca_la_ventana_es_limpia(self):
        from shmir_design.transfer import WindowState

        estado = self._clasificar("CCAGATT" + "G" * 40, "CCAATT" + "G" * 40, 20, 22)
        self.assertIs(estado.state, WindowState.LIMPIA)

    def test_una_diferencia_inequivoca_dentro_la_deja_TOCADA(self):
        from shmir_design.transfer import WindowState

        estado = self._clasificar("CCAGATT" + "G" * 40, "CCAATT" + "G" * 40, 1, 22)
        self.assertIs(estado.state, WindowState.TOCADA)

    def test_una_carrera_que_cabe_ENTERA_dentro_tambien_la_deja_TOCADA(self):
        # Se ponga donde se ponga el indel, esta dentro.
        from shmir_design.transfer import WindowState

        ref = "G" * 10 + "AAAA" + "G" * 30
        estado = self._clasificar(ref, ref.replace("AAAA", "AAA", 1), 5, 22)
        self.assertIs(estado.state, WindowState.TOCADA)

    def test_una_carrera_que_CRUZA_el_borde_la_deja_INDETERMINADA(self):
        from shmir_design.transfer import WindowState

        ref = "G" * 20 + "AAAA" + "G" * 30
        # Ventana 1-22: la carrera va de 21 a 24, asi que cruza el borde.
        estado = self._clasificar(ref, ref.replace("AAAA", "AAA", 1), 1, 22)
        self.assertIs(estado.state, WindowState.INDETERMINADA)

    def test_el_motivo_explica_por_que_no_se_puede_afirmar(self):
        estado = self._clasificar(
            "G" * 20 + "AAAA" + "G" * 30,
            ("G" * 20 + "AAAA" + "G" * 30).replace("AAAA", "AAA", 1),
            1, 22,
        )
        self.assertIn("carrera", estado.reason.lower())
        self.assertIn("no se puede afirmar", estado.reason.lower())

    def test_lo_inequivoco_manda_sobre_lo_ambiguo(self):
        # Si hay las dos cosas, TOCADA gana: no hay duda de que algo cambio ahi.
        from shmir_design.transfer import WindowState

        ref = "G" * 5 + "C" + "G" * 14 + "AAAA" + "G" * 30
        otra = ref.replace("C", "T", 1).replace("AAAA", "AAA", 1)
        self.assertIs(self._clasificar(ref, otra, 1, 22).state, WindowState.TOCADA)


@unittest.skipUnless(
    RATON.is_file() and FABRICADO.is_file(), "NOT_RUN: faltan los fixtures"
)
class TestElSitio221(unittest.TestCase):
    """El caso que motivo el tercer estado, resuelto con su razon escrita."""

    @classmethod
    def setUpClass(cls):
        cls.alineamiento = align(
            _utr3(), FABRICADO.read_text(encoding="ascii").strip()
        )

    def _estado(self, inicio):
        from shmir_design.transfer import classify_window

        return classify_window(start=inicio, window=22, alignment=self.alineamiento)

    def test_el_221_sale_INDETERMINADO_no_TOCADO(self):
        from shmir_design.transfer import WindowState

        self.assertIs(self._estado(221).state, WindowState.INDETERMINADA)

    def test_y_su_motivo_nombra_la_carrera(self):
        self.assertIn("carrera", self._estado(221).reason.lower())

    def test_un_sitio_lejos_de_toda_diferencia_sigue_LIMPIO(self):
        from shmir_design.transfer import WindowState

        self.assertIs(self._estado(643).state, WindowState.LIMPIA)


if __name__ == "__main__":
    unittest.main()
