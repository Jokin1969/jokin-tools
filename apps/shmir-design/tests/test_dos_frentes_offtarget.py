"""Especificidad y off-target por seed son DOS frentes, nunca uno.

Regla 5: escritos antes.

El BLAST busca COMPLEMENTARIEDAD EXTENSA. El off-target mediado por seed no se busca con
BLAST y no se puede: **7 nt contiguos no dan un alineamiento puntuable**. Es coincidencia
EXACTA del heptamero 2-8 sobre los 3'UTR del transcriptoma murino — busqueda de
subcadena, no alineamiento — y necesita `transcriptoma_3utr.fa`.

Fundirlos en un «especificidad: PASS» daria por cubierto **el modo de off-target mas
frecuente de RNAi** con una herramienta que no lo detecta. Por eso son dos frentes y el
informe los cuenta aparte.
"""

import unittest

from shmir_design import seed_load as seed_mod
from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]


class TestSonDosCosasDistintas(unittest.TestCase):

    def test_el_motivo_de_la_separacion_va_escrito(self):
        texto = seed_mod.WHY_NOT_BLAST
        self.assertIn("7 nt", texto)
        self.assertIn("alineamiento", texto.lower())

    def test_dice_que_es_busqueda_de_SUBCADENA(self):
        self.assertIn("subcadena", seed_mod.WHY_NOT_BLAST.lower())

    def test_y_que_es_el_modo_MAS_FRECUENTE(self):
        self.assertIn("mas frecuente", seed_mod.WHY_NOT_BLAST.lower())

    def test_nombra_el_fichero_que_hace_falta(self):
        self.assertIn("transcriptoma_3utr.fa", seed_mod.WHY_NOT_BLAST)

    def test_el_frente_tiene_nombre_propio(self):
        self.assertEqual(seed_mod.FRONT_NAME, "offtarget_seed")
        self.assertNotEqual(seed_mod.FRONT_NAME, "especificidad")


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestElFrenteEntraEnLaLista(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.selection import (
            SelectionConfig, blocking_fronts, select_from_report,
        )
        from shmir_design.tiling import tile_utr

        informe = tile_utr(load_3utr(RATON))
        cls.frentes = blocking_fronts(
            informe, select_from_report(informe, SelectionConfig(n_candidates=10))
        )

    def _nombres(self):
        return [f.name for f in self.frentes]

    def test_estan_LOS_DOS(self):
        self.assertIn("especificidad", self._nombres())
        self.assertIn("offtarget_seed", self._nombres())

    def test_y_son_frentes_DISTINTOS(self):
        self.assertNotEqual(
            next(f for f in self.frentes if f.name == "especificidad").reason,
            next(f for f in self.frentes if f.name == "offtarget_seed").reason,
        )

    def test_el_de_seed_dice_que_el_BLAST_no_lo_ve(self):
        motivo = next(f for f in self.frentes if f.name == "offtarget_seed").reason
        self.assertIn("7 nt", motivo)
        self.assertIn("subcadena", motivo.lower())

    def test_y_el_de_especificidad_avisa_de_que_NO_cubre_al_otro(self):
        motivo = next(f for f in self.frentes if f.name == "especificidad").reason
        self.assertIn("seed", motivo.lower())

    def test_los_dos_BLOQUEAN(self):
        for nombre in ("especificidad", "offtarget_seed"):
            self.assertTrue(next(f for f in self.frentes if f.name == nombre).blocking)


@unittest.skipUnless(fixture_available(RATON), "falta data/reference/NM_011170.3.fa")
class TestElInformeNoLosFUNDE(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        informe = tile_utr(load_3utr(RATON))
        cls.texto = text_report(
            species="raton", tiling=informe,
            selection=select_from_report(informe, SelectionConfig(n_candidates=10)),
            scaffold=SGEP_SCAFFOLD,
        )

    def test_los_dos_nombres_salen(self):
        self.assertIn("offtarget_seed", self.texto)
        self.assertIn("especificidad", self.texto)

    def test_el_motivo_de_no_fundirlos_esta_en_el_informe(self):
        self.assertIn("7 nt", self.texto)


class TestLaBusquedaSIGUE_siendo_de_subcadena(unittest.TestCase):
    """No se cambia el algoritmo: ya era coincidencia exacta y asi se queda."""

    def test_los_patrones_son_los_tres_de_siempre(self):
        patrones = seed_mod.site_patterns("TTATATTCTTATTGGCCCGGTG")
        self.assertEqual(sorted(patrones), ["7mer-A1", "7mer-m8", "8mer"])

    def test_el_7mer_m8_mide_SIETE(self):
        self.assertEqual(len(seed_mod.site_patterns("TTATATTCTTATTGGCCCGGTG")["7mer-m8"]), 7)

    def test_y_es_el_complementario_inverso_de_las_posiciones_2_8(self):
        guia = "TTATATTCTTATTGGCCCGGTG"
        seed = guia[1:8]
        esperado = seed.translate(str.maketrans("ACGT", "TGCA"))[::-1]
        self.assertEqual(seed_mod.site_patterns(guia)["7mer-m8"], esperado)


if __name__ == "__main__":
    unittest.main()
