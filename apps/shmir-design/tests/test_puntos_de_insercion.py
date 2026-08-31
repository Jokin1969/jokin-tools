"""Dónde va el módulo dentro de `intron_quimerico`. Regla 5.

Ese intrón sale de la anotación de su plásmido y **no declara sus puntos de inserción**,
así que no se puede montar con ningún andamio — y eso NO es un fichero que falte: es una
decisión con criterio, y el criterio es computable.

**Dos criterios que no coinciden**, y por eso se emiten las dos medidas:

- la SEPARACIÓN de los elementos —lejos del punto de ramificación y del tracto, sin
  pegarse al donante—, que es maximizar la separación MÍNIMA de los dos extremos, no la
  suma: una suma alta puede esconder un extremo pegado;
- la conservación de la HORQUILLA dentro del intrón, que es el criterio estructural que
  el proyecto ya aplica al MVM.

Medido: de las 97 posiciones admisibles, sólo **15** conservan la horquilla — y las que
ganarían por separación pura (52 y 53) **no están entre ellas**. Los dos criterios
discrepan de verdad.
"""

import unittest

from shmir_design.folding import VIENNA_AVAILABLE
from shmir_design.intron_design import VENTANA_ADMISIBLE, insertion_candidates
from shmir_design.introns import get


def _piezas():
    from shmir_design.blocks import build_block
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.selection import default_config, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(REFERENCES["NM_011170.3"])
    elegido = select_from_report(tile_utr(utr3), default_config()).selection.chosen[0]
    bloque = build_block(guide=utr3[elegido.start - 1 : elegido.end], available=False)
    return bloque.module, bloque.hairpin.sequence


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: falta ViennaRNA")
class TestLaVentanaSeDERIVA(unittest.TestCase):

    def setUp(self):
        modulo, horquilla = _piezas()
        self.c = insertion_candidates(
            get("intron_quimerico"), modulo, hairpin=horquilla
        )

    def test_va_de_3_a_99(self):
        """Los dos límites salen de los elementos del intrón: después del donante (1-2) y
        antes del motivo del primer candidato a punto, que empieza en 100."""
        self.assertEqual((self.c[0].position, self.c[-1].position), (3, 99))
        self.assertEqual(len(self.c), 97)

    def test_el_limite_superior_respeta_el_MOTIVO_no_solo_la_A(self):
        """La A de ramificación está en 103, pero el motivo YTNAY empieza en 100.
        Invadirlo lo rompe, así que el tope es el inicio del motivo."""
        elementos = get("intron_quimerico").elements()
        primera = min(
            c.branch_a for c in elementos.branch_candidates if c.branch_a is not None
        )
        self.assertEqual(primera, 103)
        self.assertLess(self.c[-1].position, primera - 3)


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: falta ViennaRNA")
class TestLosDosCriteriosDISCREPAN(unittest.TestCase):
    """Y por eso no se colapsan en un número."""

    def setUp(self):
        modulo, horquilla = _piezas()
        self.c = insertion_candidates(
            get("intron_quimerico"), modulo, hairpin=horquilla
        )
        self.intactas = [x for x in self.c if x.hairpin_intact]

    def test_solo_15_de_97_conservan_la_horquilla(self):
        self.assertEqual(len(self.intactas), 15)

    def test_la_ganadora_por_SEPARACION_PURA_no_conserva_la_horquilla(self):
        """52 y 53 empatan en separación sobre la ventana entera, y ninguna sobrevive al
        criterio estructural. Si sólo se hubiera mirado la separación, se habría elegido
        una posición que rompe la horquilla."""
        pura = max(self.c, key=lambda x: x.min_separation).min_separation
        empatan = [x.position for x in self.c if x.min_separation == pura]
        self.assertEqual(empatan, [52, 53])
        for posicion in empatan:
            with self.subTest(posicion):
                self.assertFalse(
                    next(x for x in self.c if x.position == posicion).hairpin_intact
                )

    def test_entre_las_que_SI_conservan_gana_la_49_y_NO_hay_empate(self):
        tope = max(x.min_separation for x in self.intactas)
        ganan = [x.position for x in self.intactas if x.min_separation == tope]
        self.assertEqual(ganan, [49])
        self.assertEqual(tope, 47)

    def test_pero_el_mejor_DELTA_G_es_otro(self):
        """69. Los dos criterios no dan la misma respuesta, y elegir cuál pesa más es una
        decisión de diseño — no la toma el programa."""
        self.assertEqual(min(self.intactas, key=lambda x: x.dg).position, 69)

    def test_la_separacion_MINIMA_no_es_la_suma(self):
        for x in self.c:
            with self.subTest(x.position):
                self.assertEqual(x.min_separation, min(x.to_donor, x.to_branch))


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: falta ViennaRNA")
class TestElCriterioESTRUCTURALmideLaHORQUILLA(unittest.TestCase):
    """La primera versión comparaba el MÓDULO entero y daba CERO posiciones válidas.

    Un cero que se lee como «ninguna vale» cuando lo que pasa es que se medía otra cosa.
    El módulo lleva sitios de restricción y contextos a los dos lados que replegan con el
    intrón; lo que tiene que sobrevivir son los 97 nt de la horquilla.
    """

    def test_el_modulo_NO_conserva_su_estructura_en_ninguna_posicion(self):
        from shmir_design.folding import dot_bracket

        modulo, _ = _piezas()
        secuencia = get("intron_quimerico").raw_sequence
        sola = dot_bracket(modulo)[0]
        conservan = [
            p for p in range(3, 100)
            if dot_bracket(secuencia[:p] + modulo + secuencia[p:])[0][p : p + len(modulo)]
            == sola
        ]
        self.assertEqual(conservan, [])

    def test_y_la_HORQUILLA_si_lo_hace_en_15(self):
        modulo, horquilla = _piezas()
        candidatos = insertion_candidates(
            get("intron_quimerico"), modulo, hairpin=horquilla
        )
        self.assertEqual(len([x for x in candidatos if x.hairpin_intact]), 15)


class TestNoSeElige(unittest.TestCase):

    def test_la_funcion_NO_devuelve_ninguna_elegida(self):
        """Devuelve la tabla entera. Igual que con la base del crítico: si el criterio
        empata, la app no elige."""
        import inspect

        from shmir_design import intron_design

        fuente = inspect.getsource(intron_design.insertion_candidates)
        self.assertNotIn("return max(", fuente)
        self.assertNotIn("chosen", fuente)

    def test_la_ventana_admisible_esta_EXPLICADA(self):
        self.assertIn("NO coinciden", VENTANA_ADMISIBLE)
        self.assertGreater(len(VENTANA_ADMISIBLE), 200)
