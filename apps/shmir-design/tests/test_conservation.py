"""Tests de la busqueda de bloques conservados entre dos 3'UTR (paso 14).

Regla 5: escritos antes que `shmir_design/conservation.py`.

Dato real (verificado por el responsable): entre el 3'UTR de NM_011170.3 y el de
NM_000311.5 existe exactamente un bloque identico de 26 nt,

    TTTTCTATATTTGTAACTTTGCATGT
    humano 1507-1532 (a 74 nt del extremo 3'), raton 1138-1163 (a 79 nt), GC 23.1%

Las secuencias completas no estan disponibles (la politica de red del entorno bloquea
NCBI, ver docs/endpoints-verificados.md) y NO se fabrican. Para probar el algoritmo con
las coordenadas reales se usa un andamio de N — base desconocida, que nunca cuenta como
identidad — con el bloque real colocado en su posicion real. El unico tramo de
nucleotidos de estos tests es el bloque verificado; lo demas es explicitamente
"desconocido". Los tests sobre los 3'UTR completos estan al final y se saltan.
"""

import unittest

from shmir_design.errors import InvalidSequenceError, MissingSequenceError
from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.conservation import (
    Utr3,
    build_conservation_report,
    find_conserved_blocks,
)

BLOCK = "TTTTCTATATTTGTAACTTTGCATGT"
MOUSE_LENGTH, HUMAN_LENGTH = 1242, 1606
MOUSE_START, HUMAN_START = 1138, 1507

MOUSE_PROBE = "N" * (MOUSE_START - 1) + BLOCK + "N" * (MOUSE_LENGTH - MOUSE_START - 25)
HUMAN_PROBE = "N" * (HUMAN_START - 1) + BLOCK + "N" * (HUMAN_LENGTH - HUMAN_START - 25)


def probes():
    return Utr3("raton", MOUSE_PROBE), Utr3("humano", HUMAN_PROBE)


class TestAndamio(unittest.TestCase):
    """El andamio reproduce las longitudes reales; si no, el resto no vale nada."""

    def test_longitudes(self):
        self.assertEqual(len(MOUSE_PROBE), MOUSE_LENGTH)
        self.assertEqual(len(HUMAN_PROBE), HUMAN_LENGTH)

    def test_el_bloque_esta_en_su_posicion_real(self):
        self.assertEqual(MOUSE_PROBE[MOUSE_START - 1 : MOUSE_START - 1 + 26], BLOCK)
        self.assertEqual(HUMAN_PROBE[HUMAN_START - 1 : HUMAN_START - 1 + 26], BLOCK)


class TestBusquedaDeBloques(unittest.TestCase):

    def test_encuentra_exactamente_un_bloque(self):
        blocks = find_conserved_blocks(*probes())
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].sequence, BLOCK)
        self.assertEqual(blocks[0].length, 26)

    def test_coordenadas_y_distancias_en_cada_especie(self):
        block = find_conserved_blocks(*probes())[0]
        raton = block.hit("raton")
        humano = block.hit("humano")
        self.assertEqual((raton.start, raton.end), (1138, 1163))
        self.assertEqual(raton.distance_to_3p, 79)
        self.assertEqual((humano.start, humano.end), (1507, 1532))
        self.assertEqual(humano.distance_to_3p, 74)

    def test_gc_del_bloque(self):
        self.assertAlmostEqual(find_conserved_blocks(*probes())[0].gc_fraction, 6 / 26)

    def test_la_N_nunca_cuenta_como_identidad(self):
        """Sin esto, dos andamios de N darian un 'bloque conservado' de mil nt."""
        self.assertEqual(find_conserved_blocks(Utr3("a", "N" * 60), Utr3("b", "N" * 60)), [])

    def test_el_bloque_se_extiende_al_maximo(self):
        """No se reportan subcadenas del bloque: solo el maximal."""
        blocks = find_conserved_blocks(*probes(), min_length=15)
        self.assertEqual([b.length for b in blocks], [26])

    def test_por_debajo_del_minimo_no_se_reporta(self):
        corto = BLOCK[:14]
        a = Utr3("a", "N" * 10 + corto + "N" * 10)
        b = Utr3("b", "N" * 20 + corto + "N" * 5)
        self.assertEqual(find_conserved_blocks(a, b), [])
        self.assertEqual(len(find_conserved_blocks(a, b, min_length=14)), 1)

    def test_el_minimo_por_defecto_es_15(self):
        corto = BLOCK[:15]
        a = Utr3("a", "N" * 10 + corto + "N" * 10)
        b = Utr3("b", "N" * 20 + corto + "N" * 5)
        self.assertEqual(len(find_conserved_blocks(a, b)), 1)

    def test_dos_bloques_se_reportan_los_dos(self):
        primero, segundo = BLOCK[:16], BLOCK[6:22]
        a = Utr3("a", "N" * 5 + primero + "N" * 30 + segundo + "N" * 5)
        b = Utr3("b", "N" * 40 + primero + "N" * 10 + segundo + "N" * 20)
        blocks = find_conserved_blocks(a, b)
        self.assertEqual({b_.sequence for b_ in blocks}, {primero, segundo})

    def test_secuencia_invalida_aborta(self):
        with self.assertRaises(InvalidSequenceError):
            Utr3("a", "ACGTX")

    def test_secuencia_ausente_aborta(self):
        with self.assertRaises(MissingSequenceError):
            Utr3("a", None)

    def test_dos_especies_con_el_mismo_nombre_es_error(self):
        with self.assertRaises(ValueError):
            find_conserved_blocks(Utr3("x", BLOCK), Utr3("x", BLOCK))


class TestVentanasDelBloque(unittest.TestCase):

    def block(self):
        return find_conserved_blocks(*probes())[0]

    def test_un_bloque_de_26_nt_da_5_ventanas_de_22(self):
        evaluaciones = self.block().window_evaluations()
        self.assertEqual([e.offset for e in evaluaciones], [0, 1, 2, 3, 4])
        self.assertEqual(evaluaciones[1].sequence, "TTTCTATATTTGTAACTTTGCA")

    def test_la_ventana_del_offset_3_falla_solo_por_GC(self):
        """Con el signo corregido, el mejor del bloque es el offset 3 (asim +0.77)."""
        evaluacion = self.block().window_evaluations()[3]
        fallos = {r.name for r in evaluacion.filters if r.state is FilterState.FAIL}
        self.assertEqual(fallos, {"GC"})

    def test_la_ventana_del_offset_1_falla_por_GC_y_asimetria(self):
        evaluacion = self.block().window_evaluations()[1]
        fallos = {r.name for r in evaluacion.filters if r.state is FilterState.FAIL}
        self.assertEqual(fallos, {"GC", "asimetria"})

    def test_todas_las_ventanas_traen_el_motivo_de_cada_filtro(self):
        for evaluacion in self.block().window_evaluations():
            with self.subTest(evaluacion.offset):
                for resultado in evaluacion.filters:
                    self.assertTrue(resultado.reason.strip())

    def test_un_bloque_corto_no_tiene_ventanas(self):
        corto = BLOCK[:16]
        a = Utr3("a", "N" * 5 + corto + "N" * 5)
        b = Utr3("b", "N" * 9 + corto + "N" * 3)
        self.assertEqual(find_conserved_blocks(a, b)[0].window_evaluations(), [])


class TestInforme(unittest.TestCase):

    def report(self):
        return build_conservation_report(*probes())

    def test_el_bloque_se_reporta_aunque_ninguna_ventana_pase(self):
        report = self.report()
        self.assertEqual(len(report.blocks), 1)
        self.assertEqual(report.passing_windows(), 0)
        texto = report.format_text()
        self.assertIn(BLOCK, texto)
        self.assertIn("decision", texto.lower())

    def test_el_informe_da_posiciones_distancias_y_gc(self):
        texto = self.report().format_text()
        for esperado in ("1138-1163", "1507-1532", "79", "74", "23.1", "26 nt"):
            with self.subTest(esperado):
                self.assertIn(esperado, texto)

    def test_el_informe_enseña_los_motivos_de_fallo(self):
        texto = self.report().format_text()
        self.assertIn("0.227", texto)      # el GC que falla
        self.assertIn("TTTT", texto)       # el homopolimero del offset 0
        self.assertIn("-2.98", texto)      # la asimetria del offset 1
        self.assertIn("+0.77", texto)      # la del offset 3, la unica positiva

    def test_sin_bloques_el_informe_lo_dice(self):
        report = build_conservation_report(Utr3("a", "N" * 40), Utr3("b", "N" * 40))
        self.assertEqual(report.blocks, ())
        self.assertIn("ningun bloque", report.format_text().lower())


@unittest.skipUnless(
    all(fixture_available(ref) for ref in REFERENCES.values()),
    "NOT_RUN: faltan los fixtures de data/reference/; añadelos al repositorio o "
    "descargalos con tools/reference_data.py --fetch. No se sustituyen por secuencia "
    "sintetica (regla 1)",
)
class TestUtrCompletos(unittest.TestCase):
    """Sobre los 3'UTR reales, extraidos y verificados desde los fixtures."""

    def utrs(self):
        return (
            Utr3("raton", load_3utr(REFERENCES["NM_011170.3"])),
            Utr3("humano", load_3utr(REFERENCES["NM_000311.5"])),
        )

    def test_existe_exactamente_un_bloque_de_22_o_mas(self):
        blocks = [b for b in find_conserved_blocks(*self.utrs()) if b.length >= 22]
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertEqual(block.sequence, BLOCK)
        self.assertEqual((block.hit("raton").start, block.hit("raton").end), (1138, 1163))
        self.assertEqual(
            (block.hit("humano").start, block.hit("humano").end), (1507, 1532)
        )

    def test_las_distancias_al_extremo_coinciden(self):
        block = [b for b in find_conserved_blocks(*self.utrs()) if b.length >= 22][0]
        self.assertEqual(block.hit("raton").distance_to_3p, 79)
        self.assertEqual(block.hit("humano").distance_to_3p, 74)


if __name__ == "__main__":
    unittest.main()
