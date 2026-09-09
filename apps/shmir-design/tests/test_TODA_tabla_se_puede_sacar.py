"""Toda tabla que la página pinta tiene una vía de salida QUE FUNCIONA.

Regla 5: escrito con el fallo delante.

**EL CASO (2026-09-09).** Reportado así: *«la app muestra muchas tablas y todas tienen
unos botones arriba a la derecha… en muchas el botón de descarga no descarga»*.

Ese icono **no es nuestro**: lo pinta Streamlit en la esquina de cada `st.dataframe` y
genera el CSV **en el navegador**. Medido en el `bundle` de 1.62.0, acaba en
`showSaveFilePicker` y, si falla, en `Blob` + `<a download>` sintético — o sea, en la
misma maquinaria de descarga del navegador que la errata nº 130 dejó **sin causa
asignada**. No podemos arreglarlo: es código de terceros. Es el principio nº 59 —**no lo
escribimos nosotros, pero lo servimos nosotros**— y su consecuencia, que es lo que
faltaba: si el único camino para llevarse una tabla es ese icono, no hay camino.

**Y el guardia que ya existía no podía verlo.**
`test_una_DESCARGA_no_puede_ser_la_UNICA_via.py` cubre `st.download_button`, o sea
NUESTRAS descargas. Las tablas no tienen `download_button`: tienen el icono ajeno, que
ningún barrido del fuente ve porque no lo escribimos. Medido antes de arreglar nada:
**26 tablas** en 6 funciones y `_segunda_via` llamado **5 veces**, y esas cinco son para
FICHEROS enteros —el FASTA, el export—, no para las tablas.

**El arreglo no es tabla por tabla** (principio nº 31: un comentario protege su línea, un
mecanismo protege la siguiente): la página pinta las tablas por UN solo sitio, `_tabla`,
que publica además la segunda vía. Así una tabla nueva la trae por construcción, y lo que
este fichero fija es que no se pueda pintar ninguna por fuera.
"""

import ast
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation  # noqa: E402

PAGINA = RAIZ / "ui" / "streamlit_app.py"
FUENTE = PAGINA.read_text(encoding="utf-8")
ARBOL = ast.parse(FUENTE)

#: El ÚNICO sitio de la página que puede pintar una tabla.
PINTOR = "_tabla"


def _funcion(nombre):
    for n in ast.walk(ARBOL):
        if isinstance(n, ast.FunctionDef) and n.name == nombre:
            return n
    return None


def _llamadas_a_dataframe():
    """Dónde se llama a `st.dataframe`, por la función que lo hace."""
    sitios = []
    for f in ast.walk(ARBOL):
        if not isinstance(f, ast.FunctionDef):
            continue
        for n in ast.walk(f):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "dataframe"
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == "st"):
                sitios.append((f.name, n.lineno))
    return sitios


class TestLaPaginaPintaLasTablasPorUNsitio(unittest.TestCase):

    def test_existe_el_pintor(self):
        self.assertIsNotNone(_funcion(PINTOR), f"falta `{PINTOR}`")

    def test_y_es_el_UNICO_que_llama_a_st_dataframe(self):
        # Sin esto, una tabla nueva se pinta suelta y se queda con el icono ajeno como
        # unica salida — que es exactamente el caso reportado.
        fuera = [(f, ln) for f, ln in _llamadas_a_dataframe() if f != PINTOR]
        self.assertEqual(
            fuera, [],
            "estas tablas se pintan por fuera de `_tabla`, así que su única salida es el "
            "icono de Streamlit, que no es nuestro y no podemos arreglar:\n  "
            + "\n  ".join(f"{f} (línea {ln})" for f, ln in fuera),
        )

    def test_el_pintor_PUBLICA_la_segunda_via(self):
        cuerpo = _funcion(PINTOR)
        llama = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "_segunda_via"
            for n in ast.walk(cuerpo)
        )
        self.assertTrue(llama, "`_tabla` pinta y no ofrece salida: es media función")

    def test_CONTROL_el_detector_encuentra_tablas(self):
        # Si dejara de encontrarlas, «ninguna se pinta por fuera» y «no miré» darían el
        # mismo verde (principio nº 51).
        self.assertGreater(len(_llamadas_a_dataframe()), 0)


class TestElTSVdeUnaTabla(unittest.TestCase):
    """La conversión vive en `presentation` y no en la página (regla 6)."""

    def test_cabecera_y_filas_separadas_por_tabulador(self):
        texto = presentation.table_tsv([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])
        self.assertEqual(
            texto.splitlines(), ["a\tb", "1\tx", "2\ty"]
        )

    def test_NINGUNA_columna_se_pierde_aunque_las_filas_difieran(self):
        # Derivar la cabecera de la PRIMERA fila tiraría columnas de las siguientes sin
        # dar ningún error: es la familia del truncamiento silencioso.
        texto = presentation.table_tsv([{"a": 1}, {"a": 2, "b": "nuevo"}])
        self.assertEqual(texto.splitlines()[0], "a\tb")
        self.assertEqual(texto.splitlines()[2], "2\tnuevo")

    def test_una_celda_AUSENTE_va_vacia_y_no_a_cero(self):
        texto = presentation.table_tsv([{"a": 1, "b": "x"}, {"a": 2}])
        self.assertEqual(texto.splitlines()[2], "2\t")

    def test_un_tabulador_o_un_salto_DENTRO_de_una_celda_no_descuadra_la_fila(self):
        # Una celda con un tabulador dentro corre los valores a la columna de al lado, y
        # eso no da ningún error — es la tabla descuadrada de `Block.__post_init__`.
        texto = presentation.table_tsv([{"a": "con\ttab", "b": "con\nsalto"}])
        self.assertEqual(len(texto.splitlines()), 2)
        self.assertEqual(len(texto.splitlines()[1].split("\t")), 2)

    def test_una_tabla_VACIA_no_da_una_cadena_que_parezca_una_tabla(self):
        self.assertEqual(presentation.table_tsv([]), "")


if __name__ == "__main__":
    unittest.main()
