"""Tests del enmascarado de repeticiones (paso 1 del orden de operaciones).

Regla 5: escritos antes que `shmir_design/masking.py`.

Sin fixture de `rmsk` el paso NO se ejecuta: el filtro `repeticiones` queda en NOT_RUN
para todas las ventanas y ninguna puede declararse apta (regla 3). Con mascara, las
posiciones enmascaradas pasan a N, y el tiling se rehace sobre la secuencia enmascarada
— nunca se tachan candidatos a posteriori.
"""

import tempfile
import unittest
from pathlib import Path

from shmir_design.filters import FilterState
from shmir_design.masking import RepeatMask, apply_mask, filter_repeats, load_mask_file

SECUENCIA = "ACGT" * 10  # sonda de 40 nt, no es un dato biologico


class TestMascara(unittest.TestCase):

    def test_una_mascara_sin_intervalos_es_error(self):
        with self.assertRaises(ValueError):
            RepeatMask(intervals=(), source="rmsk de prueba")

    def test_un_intervalo_invertido_es_error(self):
        with self.assertRaises(ValueError):
            RepeatMask(intervals=((20, 10),), source="x")

    def test_coordenadas_1_based(self):
        mask = RepeatMask(intervals=((5, 8),), source="x")
        self.assertTrue(mask.covers(5))
        self.assertTrue(mask.covers(8))
        self.assertFalse(mask.covers(4))
        self.assertFalse(mask.covers(9))


class TestAplicarMascara(unittest.TestCase):

    def test_enmascara_el_tramo_indicado(self):
        mask = RepeatMask(intervals=((5, 8),), source="x")
        enmascarada = apply_mask(SECUENCIA, mask)
        self.assertEqual(enmascarada[4:8], "NNNN")
        self.assertEqual(enmascarada[:4], SECUENCIA[:4])
        self.assertEqual(len(enmascarada), len(SECUENCIA))

    def test_varios_intervalos(self):
        mask = RepeatMask(intervals=((1, 2), (39, 40)), source="x")
        enmascarada = apply_mask(SECUENCIA, mask)
        self.assertTrue(enmascarada.startswith("NN"))
        self.assertTrue(enmascarada.endswith("NN"))

    def test_un_intervalo_fuera_de_la_secuencia_aborta(self):
        mask = RepeatMask(intervals=((38, 45),), source="x")
        with self.assertRaises(ValueError) as ctx:
            apply_mask(SECUENCIA, mask)
        self.assertIn("45", str(ctx.exception))

    def test_sin_mascara_la_secuencia_no_cambia(self):
        self.assertEqual(apply_mask(SECUENCIA, None), SECUENCIA)


class TestFiltroDeRepeticiones(unittest.TestCase):

    def test_sin_mascara_queda_en_not_run(self):
        resultado = filter_repeats(10, 31, None)
        self.assertIs(resultado.state, FilterState.NOT_RUN)
        self.assertIn("NOT_RUN no es PASS", resultado.reason)

    def test_una_ventana_que_solapa_una_repeticion_falla(self):
        mask = RepeatMask(intervals=((25, 40),), source="rmsk de prueba")
        resultado = filter_repeats(10, 31, mask)
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("25-40", resultado.reason)

    def test_una_ventana_limpia_pasa(self):
        mask = RepeatMask(intervals=((100, 140),), source="rmsk de prueba")
        resultado = filter_repeats(10, 31, mask)
        self.assertIs(resultado.state, FilterState.PASS)
        self.assertIn("rmsk de prueba", resultado.reason)

    def test_el_solape_de_una_sola_base_cuenta(self):
        mask = RepeatMask(intervals=((31, 60),), source="x")
        self.assertIs(filter_repeats(10, 31, mask).state, FilterState.FAIL)


class TestCargaDeMascara(unittest.TestCase):

    def escribir(self, texto):
        ruta = Path(tempfile.mkdtemp()) / "rmsk.tsv"
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    def test_lee_intervalos(self):
        mask = load_mask_file(self.escribir("# inicio\tfin\n10\t20\n30\t40\n"))
        self.assertEqual(mask.intervals, ((10, 20), (30, 40)))
        self.assertIn("rmsk.tsv", mask.source)

    def test_una_linea_con_un_solo_campo_aborta(self):
        with self.assertRaises(ValueError) as ctx:
            load_mask_file(self.escribir("10\n"))
        self.assertIn("2", str(ctx.exception))

    def test_una_coordenada_no_numerica_aborta(self):
        with self.assertRaises(ValueError):
            load_mask_file(self.escribir("diez\tveinte\n"))

    def test_un_fichero_sin_intervalos_aborta(self):
        with self.assertRaises(ValueError):
            load_mask_file(self.escribir("# solo comentarios\n"))

    def test_un_fichero_que_no_existe_aborta(self):
        with self.assertRaises(FileNotFoundError):
            load_mask_file(Path("/no/existe/rmsk.tsv"))


if __name__ == "__main__":
    unittest.main()
