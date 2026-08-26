"""Cuando una puntuacion externa es TRANSFERIBLE de una entrada a otra.

Regla 5: escritos antes.

    Una puntuacion externa es transferible entre entradas si y solo si la ventana no
    solapa ninguna diferencia entre ellas — y esa condicion SE COMPRUEBA, no se supone.

El caso de referencia son las dos corridas de miRarchitect sobre Prnp murino: misma
herramienta, mismo andamio, mismo gen, dos entradas que difieren en 18 sucesos sobre
1242 nt. Los 21 sitios que las dos corridas vieron con la MISMA ventana tienen score
identico, luego el score es funcion local de la ventana y la transferencia es legitima
donde la ventana coincide.

Lo que NO se transfiere es el PUESTO: 20 de esos 21 cambian de puesto teniendo el score
identico, porque el puesto depende del tamaño de la lista y no del sitio.
"""

import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.transfer import (
    TRANSFER_RULE,
    Transferability,
    can_transfer,
)

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"


class TestLaRegla(unittest.TestCase):

    def test_una_ventana_que_no_toca_ninguna_diferencia_es_transferible(self):
        veredicto = can_transfer(start=100, window=22, divergent_positions=frozenset({50}))
        self.assertIs(veredicto.state, Transferability.TRANSFERIBLE)

    def test_una_que_solapa_una_diferencia_no_lo_es(self):
        veredicto = can_transfer(start=100, window=22, divergent_positions=frozenset({110}))
        self.assertIs(veredicto.state, Transferability.NO_TRANSFERIBLE)
        self.assertIn("110", veredicto.reason)

    def test_el_borde_de_la_ventana_cuenta(self):
        for posicion in (100, 121):
            with self.subTest(posicion):
                self.assertIs(
                    can_transfer(
                        start=100, window=22, divergent_positions=frozenset({posicion})
                    ).state,
                    Transferability.NO_TRANSFERIBLE,
                )

    def test_justo_fuera_no_cuenta(self):
        for posicion in (99, 122):
            with self.subTest(posicion):
                self.assertIs(
                    can_transfer(
                        start=100, window=22, divergent_positions=frozenset({posicion})
                    ).state,
                    Transferability.TRANSFERIBLE,
                )

    def test_sin_saber_las_diferencias_NO_se_supone_que_no_las_hay(self):
        # El corolario de "se comprueba, no se supone": si nadie ha dicho en que
        # difieren las dos entradas, la condicion no se ha comprobado y no se transfiere.
        veredicto = can_transfer(start=100, window=22, divergent_positions=None)
        self.assertIs(veredicto.state, Transferability.SIN_COMPROBAR)
        self.assertIn("no se ha comprobado", veredicto.reason.lower())

    def test_un_conjunto_vacio_SI_es_una_comprobacion(self):
        # Vacio significa "se alinearon y no habia diferencias", que es distinto de
        # "nadie miro". Por eso `None` y `frozenset()` no son lo mismo.
        self.assertIs(
            can_transfer(start=100, window=22, divergent_positions=frozenset()).state,
            Transferability.TRANSFERIBLE,
        )

    def test_una_ventana_de_longitud_absurda_aborta(self):
        with self.assertRaises(ShmirDesignError):
            can_transfer(start=100, window=0, divergent_positions=frozenset())


class TestElPuestoNoSeTransfiere(unittest.TestCase):

    def test_la_regla_lo_dice(self):
        self.assertIn("puesto", TRANSFER_RULE.lower())
        self.assertIn("no", TRANSFER_RULE.lower())

    def test_y_dice_que_se_comprueba_no_se_supone(self):
        self.assertIn("se comprueba", TRANSFER_RULE.lower())
        self.assertIn("no se supone", TRANSFER_RULE.lower())


@unittest.skipUnless(
    (DIR / "mirarchitect_prnp_export.csv").is_file()
    and (DIR / "mirarchitect_prnp_export_buena.csv").is_file()
    and (DIR / "prnp_3utr_fabricado_1246nt.txt").is_file()
    and (DIR / "NM_011170.3.fa").is_file(),
    "NOT_RUN: faltan los fixtures de las dos corridas",
)
class TestSobreElCasoDeReferencia(unittest.TestCase):
    """La comprobacion sobre los dos ficheros de verdad."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.alignment import align
        from shmir_design.fetch import parse_fasta_payload
        from shmir_design.mirarchitect import parse_export
        from shmir_design.polya import normalize_sequence

        _, bruta = parse_fasta_payload(
            (DIR / "NM_011170.3.fa").read_text(encoding="utf-8"), source="fa"
        )
        cls.utr3 = normalize_sequence(bruta, name="NM_011170.3")[949:]
        cls.divergentes = align(
            cls.utr3,
            (DIR / "prnp_3utr_fabricado_1246nt.txt").read_text(encoding="ascii").strip(),
        ).ref_positions
        cls.fabricada = parse_export(
            (DIR / "mirarchitect_prnp_export.csv").read_text(encoding="utf-8-sig")
        )

    def test_veinte_de_las_21_guias_del_grupo_2_son_transferibles(self):
        # La 221 no lo es por el criterio posicional, aunque la diana diga que la
        # ventana fue la misma. La regla es la regla: se comprueba lo que se puede
        # comprobar a priori, y a priori esa ventana esta tocada.
        transferibles = sum(
            1
            for fila in self.fabricada.rows
            if self.utr3.find(fila.target) >= 0
            and can_transfer(
                start=self.utr3.find(fila.target) + 1,
                window=22,
                divergent_positions=self.divergentes,
            ).state
            is Transferability.TRANSFERIBLE
        )
        self.assertEqual(transferibles, 20)

    def test_las_5_sin_sitio_no_llegan_ni_a_preguntarse(self):
        sin_sitio = sum(
            1 for fila in self.fabricada.rows if self.utr3.find(fila.target) < 0
        )
        self.assertEqual(sin_sitio, 5)

    def test_sin_las_posiciones_divergentes_no_se_transfiere_ninguna(self):
        transferibles = sum(
            1
            for fila in self.fabricada.rows
            if self.utr3.find(fila.target) >= 0
            and can_transfer(
                start=self.utr3.find(fila.target) + 1, window=22,
                divergent_positions=None,
            ).state
            is Transferability.TRANSFERIBLE
        )
        self.assertEqual(transferibles, 0)


if __name__ == "__main__":
    unittest.main()
