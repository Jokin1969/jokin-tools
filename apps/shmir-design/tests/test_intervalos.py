"""Todo intervalo que sale del diseño cuadra con la secuencia que describe.

Regla 5: escrito antes de que hiciera falta, porque ya hizo falta dos veces.

La errata del desplazamiento de 3 nt y las ventanas `269-291`/`222-242` para guias de
22 nt son el mismo fallo: coordenadas transcritas a mano en vez de derivadas del match.
Este fichero comprueba el invariante sobre las salidas de verdad:

    fin - inicio + 1 == len(secuencia)

en las dos parejas de coordenadas —transcrito y 3'UTR— y en la tabla comparativa.
"""

import unittest
from pathlib import Path

from shmir_design.comparative import comparative_rows
from shmir_design.scaffold import SGEP_SCAFFOLD
from shmir_design.selection import SelectionConfig, select_from_report
from shmir_design.tiling import tile_utr

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"
SONDA = "GCGTCAGTACGATCGAATTACT" * 30


def _piezas(secuencia=SONDA, **kwargs):
    report = tile_utr(secuencia, **kwargs)
    return report, select_from_report(report, SelectionConfig(n_candidates=6))


class TestVentanasDelTiling(unittest.TestCase):

    def test_cada_ventana_abarca_lo_que_mide_su_diana(self):
        report, _ = _piezas()
        for ventana in report.windows:
            with self.subTest(ventana.window.start):
                self.assertEqual(
                    ventana.window.end - ventana.window.start + 1,
                    len(ventana.evaluation.sequence),
                )

    def test_y_lo_mismo_en_coordenadas_del_3utr(self):
        report, _ = _piezas()
        for ventana in report.windows:
            if ventana.inicio_3utr is None:
                continue
            with self.subTest(ventana.inicio_3utr):
                self.assertEqual(
                    ventana.fin_3utr - ventana.inicio_3utr + 1,
                    len(ventana.evaluation.sequence),
                )

    def test_la_guia_mide_lo_mismo_que_la_diana(self):
        report, _ = _piezas()
        for ventana in report.windows:
            with self.subTest(ventana.window.start):
                self.assertEqual(
                    len(ventana.evaluation.guide),
                    len(ventana.evaluation.sequence),
                )


class TestTablaComparativa(unittest.TestCase):

    def test_las_dos_parejas_cuadran_con_la_diana(self):
        _, seleccion = _piezas()
        filas = comparative_rows(seleccion, SGEP_SCAFFOLD)
        cabecera = filas[0]

        def valor(fila, nombre):
            return fila[cabecera.index(nombre)]

        for fila in filas[1:]:
            diana = valor(fila, "diana")
            with self.subTest(valor(fila, "inicio_transcrito")):
                self.assertEqual(
                    int(valor(fila, "fin_transcrito"))
                    - int(valor(fila, "inicio_transcrito")) + 1,
                    len(diana),
                )
                self.assertEqual(
                    int(valor(fila, "fin_3utr")) - int(valor(fila, "inicio_3utr")) + 1,
                    len(diana),
                )


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestSobreElTranscritoReal(unittest.TestCase):
    """Con anatomia de verdad, donde las dos parejas SI son distintas."""

    def _raton(self):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.polya import normalize_sequence

        _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
        secuencia = normalize_sequence(bruta, name="NM_011170.3")
        anatomia = Anatomy.from_cds(
            cds=(185, 949), length=len(secuencia),
            source=RegionSource.ANOTACION_GENBANK,
        )
        return _piezas(secuencia, anatomy=anatomia)

    def test_el_offset_entre_las_dos_parejas_es_constante_y_es_949(self):
        report, _ = self._raton()
        offsets = {
            w.window.start - w.inicio_3utr
            for w in report.windows
            if w.inicio_3utr is not None
        }
        self.assertEqual(offsets, {949})

    def test_y_cada_ventana_sigue_cuadrando(self):
        report, _ = self._raton()
        for ventana in report.windows:
            with self.subTest(ventana.window.start):
                self.assertEqual(
                    ventana.window.end - ventana.window.start + 1,
                    len(ventana.evaluation.sequence),
                )


if __name__ == "__main__":
    unittest.main()
