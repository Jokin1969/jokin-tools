"""La fraccion de isoforma larga, MEDIDA: PolyA_DB v4.1.

Regla 5: escritos antes.

Aportado el 2026-08-26: PolyA_DB v4.1 (15-sep-2025), mm10, Prnp (Gene ID 19122). 15 PAS
en el gen, 5 con datos de expresion; los otros 10 por debajo de deteccion en 3'READS+,
incluidos los intermedios del 3'UTR — no introducen techos.

Las DOS cifras, con su formula, porque no miden lo mismo:

  ponderada    Σ(AvgRPM × PSE) del distal / Σ de todos   = 0,86  ← valor de trabajo
  sin ponderar Σ(AvgRPM) del distal / Σ de todos         = 0,65

La ponderada es la correcta porque `AvgRPM` esta condicionado a muestras CON expresion.

Y hay tres cosas que NO se dan por buenas, ninguna resoluble con este repositorio:
la conversion genomico↔transcrito, el segundo PAS proximal y el racimo terminal.
"""

import unittest

from shmir_design.apa import (
    POLYA_DB_PRNP,
    MeasuredSite,
    long_isoform_fraction,
)


class TestLasDosCifras(unittest.TestCase):

    def test_la_ponderada_es_0_86(self):
        self.assertAlmostEqual(
            long_isoform_fraction(POLYA_DB_PRNP.sites, weighted=True), 0.8558, places=4
        )

    def test_la_sin_ponderar_es_0_65(self):
        self.assertAlmostEqual(
            long_isoform_fraction(POLYA_DB_PRNP.sites, weighted=False), 0.6496, places=4
        )

    def test_la_de_trabajo_es_la_PONDERADA_y_lo_dice(self):
        self.assertAlmostEqual(POLYA_DB_PRNP.working_value, 0.8558, places=4)
        self.assertIn("condicionado a muestras", POLYA_DB_PRNP.why_weighted)

    def test_las_dos_formulas_van_escritas(self):
        texto = "\n".join(POLYA_DB_PRNP.describe())
        self.assertIn("AvgRPM × PSE", texto)
        self.assertIn("0.86", texto)
        self.assertIn("0.65", texto)

    def test_la_procedencia_completa_esta(self):
        texto = "\n".join(POLYA_DB_PRNP.describe())
        for dato in ("PolyA_DB v4.1", "2025-09-15", "mm10", "19122", "NM_001278256.1"):
            with self.subTest(dato):
                self.assertIn(dato, texto)

    def test_los_15_PAS_y_los_5_con_expresion_se_declaran(self):
        texto = "\n".join(POLYA_DB_PRNP.describe())
        self.assertIn("15 PAS", texto)
        self.assertIn("5 con datos", texto)

    def test_una_lista_vacia_de_sitios_aborta(self):
        with self.assertRaises(ValueError):
            long_isoform_fraction((), weighted=True)

    def test_sin_ningun_sitio_distal_aborta(self):
        solo_proximales = tuple(s for s in POLYA_DB_PRNP.sites if not s.distal)
        with self.assertRaises(ValueError):
            long_isoform_fraction(solo_proximales, weighted=True)


class TestLoQueNoSeDaPorBueno(unittest.TestCase):

    def test_el_dato_NO_es_utilizable_todavia(self):
        self.assertFalse(POLYA_DB_PRNP.usable)

    def test_y_las_tres_comprobaciones_estan_listadas(self):
        pendientes = " ".join(POLYA_DB_PRNP.pending)
        self.assertIn("conversion", pendientes.lower())
        self.assertIn("131937444", pendientes)
        self.assertIn("131938427", pendientes)

    def test_la_conversion_NO_se_puede_hacer_aqui_y_se_dice_por_que(self):
        texto = "\n".join(POLYA_DB_PRNP.describe())
        # El .gb de NM_011170.3 no trae coordenadas genomicas: su bloque PRIMARY
        # referencia cDNA y EST, no un cromosoma.
        self.assertIn("no trae coordenadas genomicas", texto)
        self.assertIn("PRIMARY", texto)

    def test_las_DOS_hipotesis_de_mapeo_se_dan_y_no_se_elige(self):
        texto = "\n".join(POLYA_DB_PRNP.describe())
        self.assertIn("3utr:228", texto)   # si 131937504 es el hexamero
        self.assertIn("3utr:243", texto)   # si es el sitio de corte
        self.assertIn("no se elige", texto.lower())

    def test_dice_que_el_221_depende_de_esa_conversion(self):
        texto = "\n".join(POLYA_DB_PRNP.describe())
        self.assertIn("3utr:221", texto)
        self.assertIn("inmune", texto.lower())

    def test_el_racimo_terminal_no_se_fusiona_sin_comprobar(self):
        texto = "\n".join(POLYA_DB_PRNP.describe())
        self.assertIn("35 nt", texto)
        self.assertIn("no se fusionan", texto.lower())


class TestElTejido(unittest.TestCase):

    def test_el_dato_es_de_TODOS_los_tejidos_y_se_dice(self):
        texto = "\n".join(POLYA_DB_PRNP.describe())
        self.assertIn("todos los tejidos", texto.lower())
        self.assertNotIn("de cerebro murino,", texto)

    def test_se_declara_como_LIMITE_INFERIOR_para_cerebro(self):
        texto = "\n".join(POLYA_DB_PRNP.describe())
        self.assertIn("limite inferior", texto.lower())
        self.assertIn("alargan", texto.lower())

    def test_y_la_RT_qPCR_deja_de_ser_solo_confirmacion(self):
        texto = "\n".join(POLYA_DB_PRNP.describe())
        self.assertIn("puede MEJORAR", texto)
