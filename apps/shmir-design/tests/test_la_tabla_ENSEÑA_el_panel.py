"""La tabla de sitios pone el PANEL ARRIBA, o el veredicto no se ve.

**Reportado con captura (2026-09-02)**, y con la tarjeta ya en verde al lado: la tarjeta
decía «CERRADO por corrida guardada: los 10 candidatos del panel tienen veredicto» y la
columna `especificidad` de la tabla, justo debajo, salía `NOT_RUN` fila tras fila.

**La tabla no estaba mal: estaba ilegible.** Tiene **270 filas** —todos los sitios
elegibles, que es deliberado: un sitio fuera del panel sigue teniendo veredictos y
esconderlo deja al lector sin poder discutir la selección— y sólo **10** llevan la
corrida. Las otras 260 dicen `NOT_RUN` porque nadie las consultó, que es la verdad. Con
las diez repartidas entre las 260, lo que se ve al abrir la tabla es `NOT_RUN`.

Es la forma más incómoda de este fallo: **la salida es correcta y la conclusión que
produce es falsa**. No lo arregla ningún estado nuevo — lo arregla el ORDEN.

Regla 5: escrito antes.
"""

import unittest

from shmir_design import presentation


class TestElOrden(unittest.TestCase):

    FILAS = [
        {"elegido": False, "inicio": 100, "rango": ""},
        {"elegido": True, "inicio": 200, "rango": 2},
        {"elegido": False, "inicio": 300, "rango": ""},
        {"elegido": True, "inicio": 400, "rango": 1},
    ]

    def test_los_del_panel_van_PRIMERO(self):
        ordenadas = presentation.panel_first(self.FILAS)
        self.assertEqual([f["elegido"] for f in ordenadas], [True, True, False, False])

    def test_y_entre_ellos_por_RANGO_no_por_posicion(self):
        # El rango es el orden en que la app los eligió: es la información, y ordenarlos
        # por coordenada la perdería.
        ordenadas = presentation.panel_first(self.FILAS)
        self.assertEqual([f["rango"] for f in ordenadas[:2]], [1, 2])

    def test_el_resto_conserva_su_orden_por_POSICION(self):
        ordenadas = presentation.panel_first(self.FILAS)
        self.assertEqual([f["inicio"] for f in ordenadas[2:]], [100, 300])

    def test_no_se_pierde_ni_se_duplica_ninguna_fila(self):
        # La tabla enseña TODOS los sitios elegibles a propósito. Ordenar no es filtrar.
        ordenadas = presentation.panel_first(self.FILAS)
        self.assertEqual(len(ordenadas), len(self.FILAS))
        self.assertEqual(
            sorted(f["inicio"] for f in ordenadas),
            sorted(f["inicio"] for f in self.FILAS),
        )


class TestLaTablaLoAPLICA(unittest.TestCase):

    def test_site_table_rows_devuelve_el_panel_arriba(self):
        import inspect

        fuente = inspect.getsource(presentation.site_table_rows)
        self.assertIn("panel_first", fuente)


class TestLaPaginaDICEloQueHAY(unittest.TestCase):
    """Un `NOT_RUN` en una fila que nadie consultó no es lo mismo que uno sin corrida."""

    def test_hay_un_texto_que_explica_las_filas(self):
        texto = presentation.TABLE_SCOPE_NOTE
        self.assertIn("panel", texto.lower())
        self.assertIn("NOT_RUN", texto)

    def test_y_la_pagina_lo_pinta(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("TABLE_SCOPE_NOTE", fuente)


if __name__ == "__main__":
    unittest.main()


class TestNINGUNAtablaSEQUEDAfuera(unittest.TestCase):
    """El guardia que faltaba: son DOS tablas y las arreglé de una en una.

    `site_table_rows` (todos los sitios elegibles) y `candidate_rows` («Candidatos, un
    estado por filtro»). El `stores=` fue a la primera; la segunda se quedó fuera, y la
    página pinta las dos. Resultado: la tarjeta decía «CERRADO por corrida guardada: los
    10 candidatos» y la tabla de esos mismos diez decía `NOT_RUN` tres centímetros más
    arriba.

    `_filter_columns` es el ÚNICO sitio que emite el estado por filtro de una fila. La
    regla, que es mecánica y no una intención: **todo el que lo llame tiene que pasar por
    `_with_stores`**. Una tercera tabla que lo llame sin envolver falla aquí, no el día
    que alguien la mire con una corrida guardada.
    """

    def test_todo_llamador_de_filter_columns_pasa_por_with_stores(self):
        import ast
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent
            / "shmir_design" / "presentation.py"
        ).read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        sueltos = []
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            envuelto = (
                isinstance(nodo.func, ast.Name) and nodo.func.id == "_with_stores"
            )
            if not envuelto:
                continue
            # marcamos las líneas donde SÍ va envuelto
        envueltas = {
            n.lineno
            for n in ast.walk(arbol)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "_with_stores"
        }
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Name)
                and nodo.func.id == "_filter_columns"
            ):
                if not any(abs(nodo.lineno - l) <= 3 for l in envueltas):
                    sueltos.append(nodo.lineno)
        self.assertEqual(
            sueltos, [],
            f"hay una tabla que emite estados por filtro sin mirar los almacenes "
            f"(líneas {sueltos}). Son dos y las arreglé de una en una; una tercera "
            f"repetiría el desacuerdo entre la tarjeta y la tabla.",
        )

    def test_las_dos_tablas_aceptan_stores(self):
        import inspect

        for funcion in (presentation.candidate_rows, presentation.site_table_rows):
            with self.subTest(funcion.__name__):
                self.assertIn("stores", inspect.signature(funcion).parameters)

    def test_la_pagina_se_las_pasa_a_LAS_DOS(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("candidate_rows(seleccion, species=nombre, stores=", fuente)


class TestSINCONSULTARnoEsNOTRUN(unittest.TestCase):
    """«No se le ha preguntado» y «falta el fichero» no son lo mismo.

    Lo señaló el responsable del proyecto: si de 270 filas sólo diez pueden tener
    veredicto y las 260 restantes salen `NOT_RUN` para siempre, esa tabla **necesita
    distinguir** las dos causas. No es presentación — se arreglan con cosas distintas: una
    lanzando una corrida que las incluya, la otra consiguiendo un fichero.
    """

    def test_sin_ninguna_corrida_el_estado_sigue_siendo_NOT_RUN(self):
        # Control adversario: si `SIN_CONSULTAR` saliera siempre, no distinguiría nada.
        class AlmacenVacio:
            runs = []

            def history(self, _):
                return ()

        estado = presentation._store_state(
            {"blast": AlmacenVacio()}, "especificidad", "mouse", 10
        )
        self.assertIsNone(estado)

    def test_con_corridas_pero_ninguna_de_ESTE_candidato_dice_SIN_CONSULTAR(self):
        class AlmacenConOtras:
            runs = ["algo"]

            def history(self, _):
                return ()

        self.assertEqual(
            presentation._store_state(
                {"blast": AlmacenConOtras()}, "especificidad", "mouse", 10
            ),
            presentation.SIN_CONSULTAR,
        )

    def test_y_bloquea_el_veredicto_igual_que_NOT_RUN(self):
        self.assertEqual(
            presentation.verdict_with_stores(
                {"especificidad": presentation.SIN_CONSULTAR, "GC": "PASS"}
            ),
            "INCOMPLETE",
        )
