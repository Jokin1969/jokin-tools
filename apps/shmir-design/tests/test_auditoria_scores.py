"""Auditoria de un fichero de scores externo contra el 3'UTR de referencia.

Regla 5: escritos antes que `shmir_design/audit.py`.

Existe porque el analisis de la corrupcion se hizo tres veces a mano, y a mano se
cometen justo los errores que persigue: en la segunda pasada emiti la ventana `269-291`
(23 nt) y `222-242` (21 nt) para guias de 22, y en el informe anterior la misma ventana
como `270-291`. Coordenadas transcritas en vez de derivadas: la errata del
desplazamiento de 3 nt otra vez.

Aqui NINGUN intervalo se escribe a mano. `Span.of()` lo deriva del match y comprueba
que su longitud es la de la secuencia; un intervalo que no cuadre aborta.

Datos reales: el 3'UTR de NM_011170.3 y el fichero de la corrida manual.
"""

import unittest
from pathlib import Path

from shmir_design.audit import (
    RESTRICTION_SITES,
    Span,
    audit_scores,
)
from shmir_design.errors import ShmirDesignError

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON, SCORES = DIR / "NM_011170.3.fa", DIR / "mirarchitect_prnp_raton.tsv"


def _utr3() -> str:
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.polya import normalize_sequence

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    return normalize_sequence(bruta, name="NM_011170.3")[949:]


class TestSpan(unittest.TestCase):
    """Un intervalo se DERIVA de la secuencia que describe, nunca se transcribe."""

    def test_la_longitud_sale_de_los_extremos(self):
        self.assertEqual(Span(10, 31).length, 22)

    def test_of_deriva_el_final_de_la_secuencia(self):
        self.assertEqual(Span.of(10, "A" * 22), Span(10, 31))

    def test_un_intervalo_que_no_cuadra_con_su_secuencia_aborta(self):
        with self.assertRaises(ShmirDesignError) as caja:
            Span(10, 31).check("A" * 21, name="guia")
        self.assertIn("22", str(caja.exception))
        self.assertIn("21", str(caja.exception))

    def test_uno_que_cuadra_no_aborta(self):
        Span(10, 31).check("A" * 22, name="guia")

    def test_no_existe_intervalo_al_reves(self):
        with self.assertRaises(ShmirDesignError):
            Span(31, 10)

    def test_se_imprime_1_based_inclusivo(self):
        self.assertEqual(str(Span(10, 31)), "10-31")


@unittest.skipUnless(
    RATON.is_file() and SCORES.is_file(), "NOT_RUN: faltan los fixtures del raton"
)
class TestSobreLaCorridaReal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        filas = [
            (l.split("\t")[0], float(l.split("\t")[1]))
            for l in SCORES.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("guia_dna")
        ]
        cls.auditoria = audit_scores(filas, _utr3())

    def test_las_longitudes_no_son_fijas(self):
        # 20 de 22 nt, 4 de 21 y 1 de 23. La herramienta NO emite longitud fija, asi
        # que de la longitud sola no se puede concluir donde se perdio la base.
        self.assertEqual(self.auditoria.lengths, {21: 4, 22: 20, 23: 1})

    def test_pero_toda_fila_que_no_mide_22_es_anomala(self):
        # Las cinco: tres no mapean, una no mapea y otra mapea pero es PREFIJO de otra
        # fila del mismo fichero, o sea la misma prediccion con un caracter menos.
        raras = [e for e in self.auditoria.entries if e.length != 22]
        self.assertEqual(len(raras), 5)
        for entrada in raras:
            with self.subTest(entrada.guide):
                self.assertTrue(not entrada.maps or entrada.prefix_of)

    def test_la_unica_de_21_que_mapea_es_prefijo_de_otra(self):
        entrada = next(
            e for e in self.auditoria.entries if e.length == 21 and e.maps
        )
        self.assertEqual(entrada.prefix_of, "TTTTTTTTCCTGTTGCCTTCAA")

    def test_ocho_no_mapean(self):
        self.assertEqual(sum(1 for e in self.auditoria.entries if not e.maps), 8)

    def test_toda_ventana_emitida_cuadra_con_su_secuencia(self):
        # La comprobacion que faltaba. Si un intervalo no cuadra, `Span.check` aborta
        # dentro de `audit_scores` y este test no llega a correr.
        for entrada in self.auditoria.entries:
            if entrada.span is not None:
                with self.subTest(entrada.guide):
                    self.assertEqual(entrada.span.length, len(entrada.mapped_sequence))

    def test_la_ventana_restaurada_cuadra_con_la_diana_que_emparejo(self):
        # Ojo: NO con la guia restaurada. Cuando el match sale de `guia[1:]`, la
        # ventana mide un nt menos porque la posicion 1 es la T de convenio. Este test
        # lo cazo la primera vez que se escribio al reves.
        for entrada in self.auditoria.entries:
            if entrada.restored_span is not None:
                with self.subTest(entrada.guide):
                    self.assertEqual(
                        entrada.restored_span.length, len(entrada.restored_sequence)
                    )

    def test_y_esa_diferencia_de_1_nt_esta_marcada(self):
        for entrada in self.auditoria.entries:
            if entrada.restored_span is None:
                continue
            with self.subTest(entrada.guide):
                esperado = len(entrada.restored) - (
                    1 if entrada.dropped_convention_base else 0
                )
                self.assertEqual(entrada.restored_span.length, esperado)

    def test_XbaI_aparece_en_una_guia_y_en_ninguna_parte_del_3utr(self):
        ajenos = dict(self.auditoria.sites_absent_from_reference)
        self.assertIn("XbaI", ajenos)
        self.assertEqual(ajenos["XbaI"], ("TCTAGATTCCCAGGTGGGAGGC",))

    def test_EcoRI_aparece_pero_SI_esta_en_el_3utr(self):
        # Esa es secuencia real, no contaminacion: no puede salir en la misma lista.
        self.assertNotIn("EcoRI", dict(self.auditoria.sites_absent_from_reference))

    def test_el_prefijo_ajeno_de_la_huerfana_es_XbaI_mas_una_T(self):
        entrada = next(
            e for e in self.auditoria.entries if e.guide.startswith("TCTAGA")
        )
        self.assertEqual(entrada.foreign_prefix, "TCTAGAT")
        self.assertEqual(entrada.native_suffix, "TCCCAGGTGGGAGGC")

    def test_una_sola_fila_con_sitio_ajeno_no_es_un_patron(self):
        ajenos = self.auditoria.sites_absent_from_reference
        self.assertEqual(sum(len(g) for _, g in ajenos), 1)

    def test_el_informe_dice_las_longitudes(self):
        self.assertIn("21", self.auditoria.format_text())
        self.assertIn("22", self.auditoria.format_text())


class TestSitios(unittest.TestCase):

    def test_estan_los_siete_que_se_pidieron(self):
        for nombre in ("XbaI", "EcoRI", "XhoI", "NheI", "SacI", "MluI", "AgeI"):
            with self.subTest(nombre):
                self.assertIn(nombre, RESTRICTION_SITES)


if __name__ == "__main__":
    unittest.main()
