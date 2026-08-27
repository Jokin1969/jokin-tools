"""Tests de la procedencia de la anatomia (bloque 7).

Regla 5: escritos antes de tocar `anatomy.py`, `genbank.py` y `orf.py`.

El agujero que cierran: hasta ahora `tools/design.py` caia en `whole_is_utr3()` cuando
no se pasaba `--cds`, asi que un transcrito completo se tilaba entero como si fuera
3'UTR. La corrida real sobre NM_011170.3 sin `--cds` tilo las 744 ventanas del CDS y
las 163 del 5'UTR junto con las 1221 del 3'UTR, y 71 ventanas del CDS y 41 del 5'UTR
salieron como elegibles. Que ninguna entrara en la seleccion de seis fue casualidad.

Datos reales: NM_011170.3 (raton, Prnp) — 2191 nt, 5'UTR 1-184, CDS 185-949,
3'UTR 950-2191.
"""

import unittest

from shmir_design.anatomy import Anatomy, Region, RegionSource

RATON = dict(length=2191, cds=(185, 949))
WINDOW = 22


def _region_counts(anatomy: Anatomy, window: int = WINDOW) -> dict[str, int]:
    """Cuenta ventanas por region, separando las que pisan dos tramos."""
    counts = {"5'UTR": 0, "CDS": 0, "3'UTR": 0, "frontera": 0}
    for start in range(1, anatomy.length - window + 2):
        end = start + window - 1
        if anatomy.crosses_boundary(start, end):
            counts["frontera"] += 1
        else:
            counts[str(anatomy.region_of(start))] += 1
    return counts


class TestRecuentoDeLaCorridaReal(unittest.TestCase):
    """Reproduce los recuentos medidos en la corrida sin --cds."""

    def test_las_ventanas_por_region_son_las_medidas(self):
        a = Anatomy.from_cds(cds=RATON["cds"], length=RATON["length"])
        counts = _region_counts(a)
        self.assertEqual(counts["3'UTR"], 1221)
        self.assertEqual(counts["CDS"], 744)
        self.assertEqual(counts["5'UTR"], 163)

    def test_las_ventanas_de_frontera_son_21_por_cada_union(self):
        a = Anatomy.from_cds(cds=RATON["cds"], length=RATON["length"])
        counts = _region_counts(a)
        self.assertEqual(counts["frontera"], 42)

    def test_el_total_cuadra_con_el_transcrito_entero(self):
        a = Anatomy.from_cds(cds=RATON["cds"], length=RATON["length"])
        counts = _region_counts(a)
        self.assertEqual(sum(counts.values()), RATON["length"] - WINDOW + 1)

    def test_sin_CDS_declarado_todas_esas_ventanas_se_llamarian_3utr(self):
        """El error que se esta cerrando, escrito como test para que no vuelva."""
        mentira = Anatomy.whole_is_utr3(
            RATON["length"], source=RegionSource.TODO_3UTR_DECLARADO
        )
        counts = _region_counts(mentira)
        self.assertEqual(counts["3'UTR"], RATON["length"] - WINDOW + 1)
        self.assertEqual(counts["CDS"], 0)
        # Y ademas los tercios salen corridos: la posicion 300 es CDS de verdad.
        self.assertIs(mentira.region_of(300), Region.UTR3)
        real = Anatomy.from_cds(cds=RATON["cds"], length=RATON["length"])
        self.assertIs(real.region_of(300), Region.CDS)


class TestProcedencia(unittest.TestCase):

    def test_from_cds_marca_la_procedencia_por_defecto(self):
        a = Anatomy.from_cds(cds=RATON["cds"], length=RATON["length"])
        self.assertIs(a.source, RegionSource.CDS_DECLARADA)

    def test_from_cds_acepta_declarar_otra_procedencia(self):
        a = Anatomy.from_cds(
            cds=RATON["cds"],
            length=RATON["length"],
            source=RegionSource.ANOTACION_GENBANK,
        )
        self.assertIs(a.source, RegionSource.ANOTACION_GENBANK)

    def test_whole_is_utr3_exige_declarar_por_que(self):
        """No se puede afirmar 'todo es 3'UTR' sin decir de donde sale."""
        with self.assertRaises(TypeError):
            Anatomy.whole_is_utr3(1606)

    def test_la_procedencia_tiene_texto_legible_para_el_informe(self):
        for source in RegionSource:
            self.assertTrue(source.describe())
            self.assertNotEqual(source.describe(), source.value)

    def test_sin_resolver_no_es_una_anatomia_valida(self):
        """SIN_RESOLVER existe para el informe, no para construir una Anatomy."""
        with self.assertRaises(ValueError):
            Anatomy.whole_is_utr3(1606, source=RegionSource.SIN_RESOLVER)


class TestCodonDeParada(unittest.TestCase):
    """El chequeo que pilla los off-by-one y el lio 0-based/1-based."""

    # CDS minimo real: ATG + 3 codones + TAA, y 30 nt de 3'UTR detras.
    SEC = "AAAA" + "ATGGCTAACGGGTAA" + "G" * 30
    CDS = (5, 19)

    def test_un_CDS_bien_declarado_no_produce_avisos(self):
        from shmir_design.anatomy import check_cds_boundaries

        a = Anatomy.from_cds(cds=self.CDS, length=len(self.SEC))
        self.assertEqual(check_cds_boundaries(self.SEC, a), ())

    def test_un_CDS_corrido_un_nucleotido_se_detecta(self):
        from shmir_design.anatomy import check_cds_boundaries

        a = Anatomy.from_cds(cds=(6, 20), length=len(self.SEC))
        avisos = check_cds_boundaries(self.SEC, a)
        self.assertTrue(any("codón de parada" in x for x in avisos))

    def test_un_CDS_que_no_empieza_por_ATG_se_detecta(self):
        from shmir_design.anatomy import check_cds_boundaries

        a = Anatomy.from_cds(cds=(4, 18), length=len(self.SEC))
        avisos = check_cds_boundaries(self.SEC, a)
        self.assertTrue(any("ATG" in x for x in avisos))

    def test_acepta_los_tres_codones_de_parada(self):
        from shmir_design.anatomy import check_cds_boundaries

        for stop in ("TAA", "TAG", "TGA"):
            sec = "AAAA" + "ATGGCTAACGGG" + stop + "G" * 30
            a = Anatomy.from_cds(cds=(5, 19), length=len(sec))
            self.assertEqual(check_cds_boundaries(sec, a), (), stop)

    def test_sin_CDS_declarado_el_chequeo_no_aplica(self):
        from shmir_design.anatomy import check_cds_boundaries

        a = Anatomy.whole_is_utr3(100, source=RegionSource.TODO_3UTR_DECLARADO)
        avisos = check_cds_boundaries("A" * 100, a)
        self.assertTrue(any("no hay cds" in x.lower() for x in avisos))

    def test_una_secuencia_de_otra_longitud_aborta(self):
        from shmir_design.anatomy import check_cds_boundaries

        a = Anatomy.from_cds(cds=self.CDS, length=len(self.SEC))
        with self.assertRaises(ValueError):
            check_cds_boundaries(self.SEC + "AAAA", a)


if __name__ == "__main__":
    unittest.main()
