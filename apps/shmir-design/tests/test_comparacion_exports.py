"""Cruce de dos exports de miRarchitect por SITIO sobre la referencia.

Regla 5: escritos antes que `mirarchitect.compare_exports`.

Sirve para dos preguntas distintas, y el eje que cambia se declara para que el informe
diga cual de las dos se esta contestando:

- **Sensibilidad a la entrada.** Mismo andamio, secuencia de entrada distinta: la
  fabricada de 1246 nt frente a la buena de 1242. Es una perturbacion del 0,3 % con el
  resto de variables identicas. Si el solapamiento de sitios es alto, la puntuacion es
  robusta; si es bajo, hay que degradar la confianza que se le da y decirlo.
- **Magnitud del andamio.** Misma entrada, andamio distinto (miR-30a frente a miR-E):
  mismo sitio, dos puntuaciones, y la diferencia atribuible al andamio. Con eso el
  `NO_ORDENAR` deja de ser una prohibicion a ciegas.

El cruce va por la coordenada del MATCH sobre la referencia, no por la guia ni por la
coordenada declarada: una ventana corrida da otra guia, y cruzar por guia perderia justo
los casos interesantes.
"""

import unittest
from pathlib import Path

from shmir_design.mirarchitect import compare_exports, parse_export

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
CSV, RATON = DIR / "mirarchitect_prnp_export.csv", DIR / "NM_011170.3.fa"


def _utr3() -> str:
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.polya import normalize_sequence

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    return normalize_sequence(bruta, name="NM_011170.3")[949:]


@unittest.skipUnless(CSV.is_file() and RATON.is_file(), "NOT_RUN: faltan los fixtures")
class TestConsigoMismo(unittest.TestCase):
    """El caso degenerado, que es el que fija el significado de las cifras."""

    @classmethod
    def setUpClass(cls):
        export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        cls.comparacion = compare_exports(
            export, export, _utr3(), axis="ninguno (control)"
        )

    def test_todos_los_sitios_reaparecen(self):
        self.assertEqual(len(self.comparacion.only_a), 0)
        self.assertEqual(len(self.comparacion.only_b), 0)

    def test_ninguno_cambia_de_puesto(self):
        self.assertEqual(self.comparacion.moved, ())

    def test_el_solapamiento_es_del_100_por_cien(self):
        self.assertEqual(self.comparacion.overlap, 1.0)

    def test_las_filas_sin_sitio_se_cuentan_aparte(self):
        # Las 5 que no existen en la referencia no tienen sitio con el que cruzar.
        self.assertEqual(self.comparacion.without_site_a, 5)
        self.assertEqual(self.comparacion.without_site_b, 5)

    def test_el_informe_nombra_el_eje(self):
        self.assertIn("ninguno (control)", self.comparacion.format_text())

    def test_el_informe_da_el_solapamiento(self):
        self.assertIn("100", self.comparacion.format_text())


@unittest.skipUnless(CSV.is_file() and RATON.is_file(), "NOT_RUN: faltan los fixtures")
class TestConUnaPerturbacion(unittest.TestCase):
    """Perturbaciones sobre el dato real: un intercambio de puestos y una baja."""

    @classmethod
    def setUpClass(cls):
        cls.export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        cls.utr3 = _utr3()

    def _con_filas(self, filas):
        from dataclasses import replace

        return replace(self.export, rows=tuple(filas))

    def test_intercambiar_dos_puestos_mueve_solo_esos_dos(self):
        filas = list(self.export.rows)
        filas[0], filas[2] = filas[2], filas[0]      # las dos tienen sitio
        comparacion = compare_exports(
            self.export, self._con_filas(filas), self.utr3, axis="prueba"
        )
        self.assertEqual(comparacion.overlap, 1.0)
        self.assertEqual(
            {m.guide for m in comparacion.moved},
            {self.export.rows[0].guide, self.export.rows[2].guide},
        )

    def test_y_el_desplazamiento_es_simetrico(self):
        filas = list(self.export.rows)
        filas[0], filas[2] = filas[2], filas[0]
        comparacion = compare_exports(
            self.export, self._con_filas(filas), self.utr3, axis="prueba"
        )
        saltos = sorted(m.rank_shift for m in comparacion.moved)
        self.assertEqual(saltos, [-2, 2])

    def test_quitar_una_fila_con_sitio_baja_el_solapamiento(self):
        # Y ademas corre el puesto de todas las de debajo: eso es lo que pasa de verdad
        # al comparar dos rankings de distinto tamaño, y el informe lo enseña.
        comparacion = compare_exports(
            self.export, self._con_filas(self.export.rows[1:]), self.utr3, axis="prueba"
        )
        self.assertEqual(len(comparacion.only_a), 1)
        self.assertEqual(len(comparacion.only_b), 0)
        self.assertLess(comparacion.overlap, 1.0)

    def test_quitar_una_fila_SIN_sitio_no_cambia_el_solapamiento(self):
        # Las 5 que no existen en la referencia no participan del cruce.
        sin_sitio = self.export.rows[1]
        filas = [f for f in self.export.rows if f is not sin_sitio]
        comparacion = compare_exports(
            self.export, self._con_filas(filas), self.utr3, axis="prueba"
        )
        self.assertEqual(comparacion.overlap, 1.0)
        self.assertEqual(comparacion.without_site_a, 5)
        self.assertEqual(comparacion.without_site_b, 4)

    def test_el_informe_lista_los_que_se_mueven(self):
        filas = list(self.export.rows)
        filas[0], filas[2] = filas[2], filas[0]
        texto = compare_exports(
            self.export, self._con_filas(filas), self.utr3, axis="prueba"
        ).format_text()
        self.assertIn("puesto", texto.lower())


@unittest.skipUnless(CSV.is_file() and RATON.is_file(), "NOT_RUN: faltan los fixtures")
class TestLoQueNoDecideLaHerramienta(unittest.TestCase):

    def test_hay_que_declarar_que_eje_cambia(self):
        export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        with self.assertRaises(TypeError):
            compare_exports(export, export, _utr3())

    def test_el_informe_no_dice_si_es_robusto_o_no(self):
        # El umbral de "alto" o "bajo" no lo pone el codigo: lo pone quien lee. El
        # informe da la cifra y dice que decision cuelga de ella.
        export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        texto = compare_exports(export, export, _utr3(), axis="x").format_text()
        self.assertNotIn("robusto", texto.lower())
        self.assertIn("degradar", texto.lower())


if __name__ == "__main__":
    unittest.main()
