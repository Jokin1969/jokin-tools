"""Lector del export de miRarchitect: valida el fichero antes de creerselo.

Regla 5: escritos antes que `shmir_design/mirarchitect.py`.

El export limpio trae mucho mas que guia y score, y cada columna de mas es una
comprobacion que antes no se podia hacer:

- `Target sequence` permite comprobar `guia == revcomp(diana)` — y ese chequeo NO sirve
  para distinguir de donde viene una corrupcion, porque la diana esta DERIVADA de la
  guia (26/26 sin excepciones). Se comprueba igual, como control de integridad del
  fichero, pero no como prueba de nada mas.
- `Start`/`End` permiten comprobar la longitud declarada contra la real.
- El loop y los flancos permiten comprobar el ANDAMIO por secuencia, no por etiqueta.
- La pasajera de la fuente sigue OTRA convencion (miR-30a) y se descarta a proposito.

Datos reales: el export de la corrida sobre Prnp murino.
"""

import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.mirarchitect import (
    PASSENGER_REJECTED,
    SOURCE_LOOP,
    parse_export,
    passenger_of,
)
from shmir_design.scaffold import SGEP_SCAFFOLD

CSV = Path(__file__).resolve().parent.parent / "data" / "reference" / "mirarchitect_prnp_export.csv"


@unittest.skipUnless(CSV.is_file(), "NOT_RUN: falta mirarchitect_prnp_export.csv")
class TestExportReal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))

    def test_trae_26_filas(self):
        self.assertEqual(len(self.export.rows), 26)

    def test_la_longitud_nominal_es_22_y_esta_confirmada(self):
        # Se acabo la dicotomia: el export lo enseña directamente en las tres columnas.
        self.assertEqual(self.export.guide_lengths, {22})
        self.assertEqual(self.export.target_lengths, {22})
        self.assertEqual(self.export.declared_lengths, {22})

    def test_la_diana_es_el_revcomp_de_la_guia_en_todas(self):
        self.assertTrue(all(f.target_is_revcomp for f in self.export.rows))

    def test_ese_chequeo_no_prueba_nada_sobre_el_origen(self):
        # La diana esta derivada de la guia: no es una lectura independiente del
        # transcrito, asi que no distingue corrupcion de entrada de corrupcion de
        # emision. El modulo lo dice para que nadie lo use como prueba.
        self.assertIn("derivada", self.export.integrity_note.lower())

    def test_el_andamio_se_lee_del_loop_no_de_la_etiqueta(self):
        self.assertEqual(self.export.loop, SOURCE_LOOP)
        self.assertNotEqual(self.export.loop, SGEP_SCAFFOLD.loop)

    def test_el_loop_del_fichero_es_el_de_miR_30a(self):
        self.assertEqual(self.export.loop, "CTGTGAAGCCACAGATGGG")

    def test_la_etiqueta_dice_lo_mismo_pero_no_se_usa(self):
        self.assertEqual(self.export.declared_scaffold, "hsa-mir-30a")

    def test_los_scores_van_en_orden_creciente(self):
        valores = [f.score for f in self.export.rows]
        self.assertEqual(valores, sorted(valores))

    def test_ninguna_guia_es_prefijo_ni_sufijo_de_otra(self):
        # En el fichero VIEJO si la habia, y mapeaba exacta: era una guia mutilada, no
        # una ventana mas corta. Aqui no hay ninguna, y por eso se comprueba.
        self.assertEqual(self.export.contained, ())


class TestReglaDeLaPasajeraDeLaFuente(unittest.TestCase):
    """`pasajera = revcomp(guia)[0:9] + revcomp(guia)[11:22] + "GC"`, 26/26."""

    def test_la_regla_reproduce_la_pasajera_de_la_fuente(self):
        self.assertEqual(
            passenger_of("TATTTAATGTCAGTCTGATAGC"), "GCTATCAGAGACATTAAATAGC"
        )

    def test_borra_dos_nucleotidos_tras_la_posicion_9(self):
        pasajera = passenger_of("TATTTAATGTCAGTCTGATAGC")
        self.assertEqual(len(pasajera), 22)
        self.assertTrue(pasajera.endswith("GC"))

    def test_no_es_la_nuestra(self):
        # La nuestra se elige plegando y solo cambia la posicion 1. Esta borra dos
        # nucleotidos del centro: son horquillas distintas.
        from shmir_design.scaffold import passenger_from_guide

        nuestra = passenger_from_guide("UAUUUAAUGUCAGUCUGAUAGC").sequence
        self.assertNotEqual(nuestra, passenger_of("TATTTAATGTCAGTCTGATAGC"))

    def test_el_motivo_del_descarte_esta_escrito(self):
        self.assertIn("miR-30a", PASSENGER_REJECTED)
        self.assertIn("plegando", PASSENGER_REJECTED)


@unittest.skipUnless(CSV.is_file(), "NOT_RUN: falta mirarchitect_prnp_export.csv")
class TestComprobacionDeAndamio(unittest.TestCase):

    def test_el_loop_del_fichero_contra_el_andamio_declarado_no_cuadra(self):
        export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        with self.assertRaises(ShmirDesignError) as caja:
            export.check_scaffold(SGEP_SCAFFOLD)
        texto = str(caja.exception)
        self.assertIn(SGEP_SCAFFOLD.loop, texto)
        self.assertIn(export.loop, texto)

    def test_el_mensaje_dice_que_la_etiqueta_no_es_la_prueba(self):
        export = parse_export(CSV.read_text(encoding="utf-8-sig"), source=str(CSV))
        with self.assertRaises(ShmirDesignError) as caja:
            export.check_scaffold(SGEP_SCAFFOLD)
        self.assertIn("etiqueta", str(caja.exception).lower())


if __name__ == "__main__":
    unittest.main()
