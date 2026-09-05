"""Todo frente con almacen tiene su fila en `STORE_FOR_FRONT`.

**Pedido por el responsable del proyecto (2026-09-02)** con la leccion delante:

> Una tabla de declaracion con una sola fila parece configurada. Es el mismo disfraz que
> `UNDECIDED_FILTERS` con un miembro.

Y no era teorico: `STORE_FOR_FRONT` tenia UNA fila —`especificidad`— mientras
`load_stores` cargaba CUATRO almacenes. Consecuencias medidas: `offtarget_seed` no tenia
columna con el transcriptoma ya en el deposito, y `verdicts_changed` decia 0 en tres de
los cuatro modales porque no habia a que columna llevar su veredicto.

Lo que este test impide es el modo de fallo, no el caso: una tabla incompleta no se lee
como incompleta.
"""

import unittest

from shmir_design.presentation import (
    FRONTS_WITHOUT_COLUMN, STORE_FOR_FRONT, STORES, STRANDS,
)

#: Se le PIDE al que los construye. Escribirlos aqui haria que este test coincidiera
#: consigo mismo: un quinto almacen entraria sin que nadie lo echara de menos, que es
#: exactamente el fallo que este fichero existe para impedir (principio nº 25).
ALMACENES = set(STORES)


class TestNingunAlmacenSeQuedaSinCOLUMNA(unittest.TestCase):

    def test_los_almacenes_declarados_existen(self):
        for frente, datos in STORE_FOR_FRONT.items():
            with self.subTest(frente):
                self.assertIn(datos["almacen"], ALMACENES)
                self.assertIn("por_hebra", datos)

    def test_todo_almacen_llega_a_una_columna_o_DECLARA_por_que_no(self):
        # El test que faltaba. Un almacen que se carga y no llega a ninguna columna es
        # trabajo que el usuario ve desaparecer: la corrida se guarda y la tabla sigue
        # igual — que es literalmente lo que paso con `offtarget_seed`.
        con_columna = {d["almacen"] for d in STORE_FOR_FRONT.values()}
        sin_columna = ALMACENES - con_columna
        declarados = {"splice"}  # el de `empalme_sitios`, con su motivo abajo
        self.assertEqual(
            sin_columna, declarados,
            "hay un almacen que se carga y no llega a ninguna columna, y no dice por qué. "
            "Un frente sin columna no se ve, y lo que no se ve no existe.",
        )

    def test_lo_que_NO_tiene_columna_dice_POR_QUE(self):
        self.assertTrue(FRONTS_WITHOUT_COLUMN)
        for frente, motivo in FRONTS_WITHOUT_COLUMN.items():
            with self.subTest(frente):
                self.assertGreater(len(motivo.strip()), 40)
                self.assertNotIn(frente, STORE_FOR_FRONT)

    def test_un_frente_por_HEBRA_da_DOS_columnas(self):
        # No es formato: la pasajera es el eje donde menos datos hay y fundirla con la
        # guia la hace invisible.
        self.assertEqual(STRANDS, ("guia", "pasajera"))
        por_hebra = [f for f, d in STORE_FOR_FRONT.items() if d["por_hebra"]]
        self.assertEqual(sorted(por_hebra), ["offtarget_seed", "seed_colision"])


class TestLasCOLUMNAS_de_la_tabla(unittest.TestCase):
    """Sobre la corrida real, que es donde se vio que faltaba."""

    @classmethod
    def setUpClass(cls):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_corrida_de_la_pagina import _entrada

        from shmir_design import presentation

        cls.presentation = presentation
        secuencia, anatomia = _entrada()
        cls.corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia
        )

    def test_offtarget_seed_tiene_sus_DOS_columnas(self):
        columnas = self.presentation.front_columns(
            self.corrida.tiling, self.corrida.selection
        )
        self.assertIn("offtarget_seed:guia", columnas)
        self.assertIn("offtarget_seed:pasajera", columnas)

    def test_y_seed_colision_tambien(self):
        columnas = self.presentation.front_columns(
            self.corrida.tiling, self.corrida.selection
        )
        self.assertIn("seed_colision:guia", columnas)
        self.assertIn("seed_colision:pasajera", columnas)

    def test_y_ninguna_columna_de_un_frente_por_hebra_va_SIN_hebra(self):
        # Si quedara la fundida, seria la que alguien lee — y estaria dando el estado de
        # la guia por el de las dos.
        columnas = self.presentation.front_columns(
            self.corrida.tiling, self.corrida.selection
        )
        for frente, datos in STORE_FOR_FRONT.items():
            if datos["por_hebra"]:
                with self.subTest(frente):
                    self.assertNotIn(frente, columnas)


if __name__ == "__main__":
    unittest.main()
