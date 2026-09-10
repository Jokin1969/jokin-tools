"""Bajo CADA tabla, dos botones nuestros: descargar y copiar.

Regla 5: escritos antes.

**Por qué** (pedido el 2026-09-10): el icono de descarga que Streamlit pinta en la
esquina de cada tabla **no es nuestro** y no baja nada — acaba en la maquinaria de
descarga que la errata nº 130 dejó SIN CAUSA ASIGNADA. Es el principio nº 59: no lo
escribimos nosotros, pero lo servimos nosotros, así que quien lo ve espera que funcione.

Lo que se puede hacer no es arreglarlo: es poner al lado dos salidas que SÍ son nuestras.
Y **no tabla por tabla** —son 26 en 6 funciones— sino en el pintor único, para que una
tabla nueva las traiga por construcción (principio nº 31: un comentario protege su línea,
un mecanismo protege la siguiente).

**Son DOS porque entregan cosas distintas**: una da un FICHERO y la otra deja la tabla en
el portapapeles para pegarla en una hoja de cálculo. Ninguna sustituye a la otra.
"""

import ast
import pathlib
import unittest

from shmir_design import presentation

PAGINA = pathlib.Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
FUENTE = PAGINA.read_text(encoding="utf-8")
ARBOL = ast.parse(FUENTE)
PINTOR = "_tabla"
BOTONES = "_botones_de_tabla"


def _funcion(nombre):
    for n in ast.walk(ARBOL):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nombre:
            return n
    return None


class TestElPintorOFRECE_LOS_DOS(unittest.TestCase):

    def test_el_pintor_llama_al_bloque_de_botones(self):
        cuerpo = _funcion(PINTOR)
        self.assertIsNotNone(cuerpo, f"falta `{PINTOR}`")
        llama = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == BOTONES
            for n in ast.walk(cuerpo)
        )
        self.assertTrue(
            llama,
            "`_tabla` pinta la tabla y no ofrece los dos botones: la única salida "
            "volvería a ser el icono ajeno, que es el caso reportado.",
        )

    def test_y_los_botones_van_FUERA_de_un_desplegable(self):
        """Detrás de un clic no es «debajo de la tabla».

        Es el principio nº 46 en su forma más barata: un estado o un gesto de más entre
        el usuario y la salida se lee como que la salida no está.
        """
        cuerpo = _funcion(PINTOR)
        dentro = []
        for n in ast.walk(cuerpo):
            if isinstance(n, ast.With):
                for hijo in ast.walk(n):
                    if (isinstance(hijo, ast.Call) and isinstance(hijo.func, ast.Name)
                            and hijo.func.id == BOTONES):
                        dentro.append(hijo.lineno)
        self.assertEqual(
            dentro, [],
            "los dos botones se pintan dentro de un `with` (un expander): quedan "
            "detrás de un gesto y no debajo de la tabla.",
        )


class TestLoQueDECIDE_presentation_y_NO_la_pagina(unittest.TestCase):
    """Regla 6. Los rótulos y los colores se pidieron POR SU COLOR, así que son parte de
    lo que se pidió — elegidos en la vista serían una decisión sin test."""

    def test_los_dos_botones_estan_declarados(self):
        self.assertEqual(
            sorted(presentation.TABLE_BUTTONS), ["copiar", "descargar"]
        )
        for clave, datos in presentation.TABLE_BUTTONS.items():
            with self.subTest(clave):
                self.assertTrue(datos["rotulo"].strip())
                self.assertRegex(str(datos["color"]), r"^#[0-9a-fA-F]{6}$")
                self.assertGreater(len(datos["que_hace"].strip()), 60)

    def test_los_rotulos_son_los_PEDIDOS(self):
        self.assertEqual(
            presentation.TABLE_BUTTONS["descargar"]["rotulo"], "Descargar tabla"
        )
        self.assertEqual(
            presentation.TABLE_BUTTONS["copiar"]["rotulo"], "Copiar tabla"
        )

    def test_la_pagina_no_escribe_NINGUN_color(self):
        # Un color escrito en la vista es una decisión sin test, y además el día que
        # cambie el de `presentation` los dos dejarían de decir lo mismo.
        import re

        cuerpo = ast.get_source_segment(FUENTE, _funcion(BOTONES)) or ""
        sueltos = re.findall(r"#[0-9a-fA-F]{6}\b", cuerpo)
        declarados = {str(v).lower() for v in presentation.PAGE_COLORS.values()}
        self.assertEqual(
            [c for c in sueltos if c.lower() in declarados], [],
            "el bloque de botones escribe un color que `PAGE_COLORS` ya declara: se "
            "pide, no se copia.",
        )

    def test_una_tabla_VACIA_no_ofrece_nada(self):
        # Un botón que baja un fichero vacío se lee como una descarga hecha.
        accion = presentation.table_actions([], nombre="x.tsv")
        self.assertTrue(accion["vacia"])
        self.assertEqual(accion["tsv"], "")

    def test_y_una_con_filas_trae_el_TSV_y_sus_cifras(self):
        accion = presentation.table_actions(
            [{"a": 1, "b": 2}, {"a": 3, "b": 4}], nombre="x.tsv"
        )
        self.assertFalse(accion["vacia"])
        self.assertEqual(accion["filas"], 2)
        self.assertEqual(accion["tsv"].splitlines()[0], "a\tb")
        self.assertEqual(accion["bytes"], len(accion["tsv"].encode("utf-8")))


class TestElMECANISMOdelBloqueSIGUEexistiendo(unittest.TestCase):
    """Los dos botones cuelgan de `streamlit.components.v1.html`, que está DEPRECADO.

    Medido el 2026-09-10 sobre Streamlit 1.62.0: la llamada funciona y avisa por consola
    de que «will be removed after 2026-06-01» — una fecha que **ya pasó**. O sea que esto
    no es una precaución teórica: la próxima subida de Streamlit puede llevarse por
    delante los dos botones de todas las tablas.

    El guardia es barato y hace lo único que se puede hacer desde aquí: que el día que
    el símbolo desaparezca **falle la suite y no la página**. Es el principio nº 59 —no
    lo escribimos nosotros, pero lo servimos nosotros— con la contramedida que le
    corresponde.

    **Y el relevo está explorado, no supuesto**: `st.iframe` existe en 1.62.0 y recibe un
    `src`, no HTML en línea, así que sustituirlo NO es cambiar el nombre de la función —
    hay que publicar el bloque en `ui/static/` y apuntar ahí. Esa ruta ya está medida por
    el proxy (`test/shmir.smoke.test.js`), pero **el permiso de portapapeles del iframe
    no**, y de él depende el botón naranja. Se mide antes de cambiarlo.
    """

    def test_el_simbolo_del_que_cuelgan_los_dos_botones_existe(self):
        from streamlit.components.v1 import html  # noqa: PLC0415

        self.assertTrue(callable(html))

    def test_y_la_pagina_lo_pide_por_ese_nombre(self):
        cuerpo = ast.get_source_segment(FUENTE, _funcion(BOTONES)) or ""
        self.assertIn("from streamlit.components.v1 import html", cuerpo)


class TestElDeDESCARGARnoCOMPARTEmecanismo(unittest.TestCase):
    """El corolario que costó tres días (errata nº 124): una vía y su alternativa no
    pueden compartir el mecanismo que falla."""

    def test_el_boton_publica_en_modo_DESCARGA(self):
        cuerpo = ast.get_source_segment(FUENTE, _funcion(BOTONES)) or ""
        self.assertIn("inline=False", cuerpo)

    def test_y_la_via_PINTADA_sigue_existiendo_como_alternativa(self):
        # No se sustituye una por otra: la pintada es la que está MEDIDA desde el
        # 2026-09-08, y quitarla dejaría la nueva sin respaldo.
        cuerpo = ast.get_source_segment(FUENTE, _funcion("_segunda_via")) or ""
        self.assertIn("inline=True", cuerpo)

    def test_los_dos_modos_dan_NOMBRES_distintos(self):
        import tempfile

        from shmir_design import segunda_via

        with tempfile.TemporaryDirectory() as tmp:
            pintado = segunda_via.publish(
                "t.tsv", "a\tb\n", directory=tmp, base_path="/shmir", inline=True,
            )
            descarga = segunda_via.publish(
                "t.tsv", "a\tb\n", directory=tmp, base_path="/shmir", inline=False,
            )
        self.assertTrue(pintado["url"].endswith(".tsv.txt"))
        self.assertTrue(descarga["url"].endswith(".tsv"))
        self.assertFalse(descarga["url"].endswith(".txt"))
        self.assertEqual(pintado["modo"], "pinta")
        self.assertEqual(descarga["modo"], "descarga")

    def test_CONTROL_ADVERSARIO_el_modo_decide_el_tipo_que_sirve_el_servidor(self):
        # Si los dos dieran el mismo tipo, el modo no estaría haciendo nada y el botón
        # morado sería la vía pintada con otro rótulo.
        import mimetypes

        self.assertEqual(mimetypes.guess_type("t.tsv.txt")[0], "text/plain")
        self.assertNotEqual(mimetypes.guess_type("t.tsv")[0], "text/plain")

    def test_sin_declarar_el_modo_ABORTA(self):
        import tempfile

        from shmir_design import segunda_via

        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(TypeError):
            segunda_via.publish(  # type: ignore[call-arg]
                "t.tsv", "a", directory=tmp, base_path="/shmir",
            )


if __name__ == "__main__":
    unittest.main()
