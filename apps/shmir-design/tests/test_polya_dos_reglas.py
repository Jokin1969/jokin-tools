"""El polyA de cada candidato bajo las DOS reglas, en columnas separadas.

Regla 5: escritos antes.

Ninguna se aplica todavia: se emiten las dos y la decision se toma con la tabla delante.
Hoy el pipeline corre en `escalonado` y eso deja 1018 suspendido por un `ACTAAA`; para
cerrar ese debate hace falta ver, candidato a candidato, que dice cada regla y con que
hexamero — no un recuento agregado.

Los campos que se añaden a los cinco que ya habia:

- `polyA_hexamero_pos`   posicion del hexamero sobre el 3'UTR
- `polyA_dist_extremo3`  cuantos nt hay de el al extremo 3'
- `polyA_estricto`       veredicto bajo la regla estricta
- `polyA_escalonado`     veredicto bajo la escalonada

Datos reales: el 3'UTR verificado de NM_011170.3.
"""

import unittest
from pathlib import Path

from shmir_design.filters import FilterState
from shmir_design.polya import (
    POLYA_COLUMNS,
    PolyAMode,
    Window,
    annotate_polya,
    find_polya_signals,
)

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"


def _utr3() -> str:
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.polya import normalize_sequence

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    return normalize_sequence(bruta, name="NM_011170.3")[949:]


class TestColumnas(unittest.TestCase):

    def test_estan_los_cuatro_campos_nuevos(self):
        for columna in (
            "polyA_hexamero_pos", "polyA_dist_extremo3",
            "polyA_estricto", "polyA_escalonado",
        ):
            with self.subTest(columna):
                self.assertIn(columna, POLYA_COLUMNS)

    def test_y_siguen_los_cinco_de_antes(self):
        for columna in (
            "polyA_hexamero", "polyA_clase", "polyA_posicion_rel",
            "polyA_solapa_seed", "polyA_veredicto",
        ):
            with self.subTest(columna):
                self.assertIn(columna, POLYA_COLUMNS)

    def test_el_veredicto_aplicado_sigue_siendo_uno_de_los_dos(self):
        # `polyA_veredicto` es el del modo con el que se corrio; las dos columnas
        # nuevas son las dos reglas SIEMPRE, se haya corrido con la que se haya corrido.
        self.assertIn("polyA_veredicto", POLYA_COLUMNS)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestSobreElTranscritoReal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3 = _utr3()
        cls.signals = find_polya_signals(cls.utr3)

    def _anotar(self, inicio, modo=PolyAMode.ESCALONADO):
        return annotate_polya(
            Window(start=inicio, length=22),
            list(self.signals),
            utr_length=len(self.utr3),
            sequence=self.utr3,
            mode=modo,
        )

    def test_las_dos_columnas_salen_pase_lo_que_pase(self):
        columnas = self._anotar(1018).as_columns()
        self.assertIn(columnas["polyA_estricto"], {e.value for e in FilterState})
        self.assertIn(columnas["polyA_escalonado"], {e.value for e in FilterState})

    def test_no_dependen_del_modo_con_el_que_se_corra(self):
        # Es el punto: emitir las dos, no la que este puesta.
        una = self._anotar(1018, PolyAMode.ESCALONADO).as_columns()
        otra = self._anotar(1018, PolyAMode.ESTRICTO).as_columns()
        self.assertEqual(una["polyA_estricto"], otra["polyA_estricto"])
        self.assertEqual(una["polyA_escalonado"], otra["polyA_escalonado"])

    def test_el_veredicto_aplicado_SI_depende_del_modo(self):
        una = self._anotar(1018, PolyAMode.ESCALONADO).as_columns()
        otra = self._anotar(1018, PolyAMode.ESTRICTO).as_columns()
        self.assertEqual(una["polyA_veredicto"], una["polyA_escalonado"])
        self.assertEqual(otra["polyA_veredicto"], otra["polyA_estricto"])

    def test_la_posicion_del_hexamero_es_la_del_3utr(self):
        anotacion = self._anotar(1018)
        if anotacion.signal is not None:
            self.assertEqual(
                anotacion.as_columns()["polyA_hexamero_pos"],
                str(anotacion.signal.position),
            )

    def test_la_distancia_al_extremo_3_cuadra_con_la_longitud(self):
        anotacion = self._anotar(1018)
        if anotacion.signal is not None:
            esperada = len(self.utr3) - anotacion.signal.end
            self.assertEqual(
                anotacion.as_columns()["polyA_dist_extremo3"], str(esperada)
            )

    def test_sin_hexamero_cerca_los_dos_campos_van_VACIOS(self):
        # Vacio, no cero: no haber encontrado hexamero y encontrarlo en la posicion 0
        # son cosas distintas.
        anotacion = self._anotar(1)
        if anotacion.signal is None:
            columnas = anotacion.as_columns()
            self.assertEqual(columnas["polyA_hexamero_pos"], "")
            self.assertEqual(columnas["polyA_dist_extremo3"], "")

    def test_el_candidato_1018_es_el_caso_que_hay_que_decidir(self):
        # Suspendido por el pipeline en modo escalonado. Aqui se ve con que hexamero.
        columnas = self._anotar(1018).as_columns()
        self.assertTrue(columnas["polyA_hexamero"])
        self.assertIn(columnas["polyA_estricto"], {e.value for e in FilterState})


if __name__ == "__main__":
    unittest.main()
