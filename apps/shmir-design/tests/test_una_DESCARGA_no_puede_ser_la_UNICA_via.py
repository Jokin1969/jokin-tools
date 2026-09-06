"""Todo fichero de texto que la página entrega tiene DOS vías, y no comparten mecanismo.

**EL CASO (2026-09-06).** La descarga del FASTA de construcciones se quedó colgada en
producción y el frente de empalme quedó bloqueado: sin ese fichero no se puede correr
SpliceAI. Antes había pasado con el bloque de off-targets y con el de colisión de seed.

**La causa NO está determinada** (errata nº 130). Medido: el contenido es determinista
—tres repintados, los mismos 66.893 bytes y el mismo md5—, así que el mecanismo de la
errata nº 76 (bytes distintos → id distinto → fichero huérfano a media descarga) **no
aplica**. Y reproducido con un navegador de verdad, un botón de 130 kB regenerado en cada
repintado, por el proxy real del hub: **baja entero**, 130.004 bytes.

**Lo que sí se puede afirmar**, y es lo que este test fija: había **una sola vía** para
sacar cada fichero, y cuando esa vía falla no queda ninguna. Es el principio nº 47 —la
salida va donde está el bloqueo— y su corolario, el que costó tres días en la errata
nº 124: *una vía y su alternativa no pueden compartir el mecanismo que falla*.

El bloque copiable no comparte nada con `st.download_button`: es texto en la página.

Regla 5: escrito con el fallo delante.
"""

import ast
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

PAGINA = RAIZ / "ui" / "streamlit_app.py"
FUENTE = PAGINA.read_text(encoding="utf-8")
ARBOL = ast.parse(FUENTE)

#: El ayudante que pinta la vía alternativa.
ALTERNATIVA = "_tambien_para_copiar"

#: Descargas que NO necesitan bloque copiable, con el motivo. Van por la función que las
#: pinta: una descarga nueva en otra función tendrá que entrar aquí y decir por qué.
SIN_ALTERNATIVA = {
    "_descargar_todo": "es un ZIP de hasta 84 MB — copiar y pegar binario no es una vía, "
                       "y su contenido son los ficheros del depósito, que están en su "
                       "origen",
    "_fila_presente": "devuelve el fichero de referencia TAL CUAL, que puede ser "
                      "`mature.fa` (5,6 MB) o un `.gb`; el original está donde se bajó y "
                      "el gestor dice su md5 para poder comprobarlo",
    "_gestionar_proyectos": "el registro de un proyecto se lleva entero por el ZIP de la "
                            "copia de seguridad, que es la vía alternativa y ya existe",
    "bloque_especie": "son los entregables del diseño, que van TAMBIÉN en el ZIP de "
                      "resultados de la sección Descargas: ésa es la segunda vía",
    "main": "las dos de `main` son el ZIP de resultados y los ficheros que ese mismo ZIP "
            "empaqueta, así que cada una es la alternativa de la otra",
}


def _funcion_de(linea: int) -> str:
    dentro = [
        (n.lineno, n.name) for n in ast.walk(ARBOL)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.lineno <= linea <= (n.end_lineno or n.lineno)
    ]
    return max(dentro)[1] if dentro else "<modulo>"


def _descargas() -> list[tuple[int, str]]:
    """`(linea, funcion)` de cada `st.download_button` de la página."""
    salida = []
    for nodo in ast.walk(ARBOL):
        if (
            isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Attribute)
            and nodo.func.attr == "download_button"
        ):
            salida.append((nodo.lineno, _funcion_de(nodo.lineno)))
    return sorted(salida)


def _alternativas() -> set[str]:
    return {
        _funcion_de(n.lineno)
        for n in ast.walk(ARBOL)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == ALTERNATIVA
    }


class TestElDetectorHaMirado(unittest.TestCase):
    """Principio nº 51: «no falló» y «no miró» dan el mismo verde."""

    def test_encuentra_las_descargas_de_la_pagina(self):
        descargas = _descargas()
        self.assertGreater(len(descargas), 5, "no ha encontrado los botones: no ha mirado")

    def test_y_encuentra_las_alternativas(self):
        self.assertGreater(len(_alternativas()), 0)

    def test_el_ayudante_EXISTE(self):
        self.assertIn(f"def {ALTERNATIVA}(", FUENTE)


class TestCadaDescargaTieneSuSegundaVia(unittest.TestCase):

    def test_o_bloque_copiable_o_motivo_escrito(self):
        con_alternativa = _alternativas()
        sin_cubrir = sorted({
            funcion for _, funcion in _descargas()
            if funcion not in con_alternativa and funcion not in SIN_ALTERNATIVA
        })
        self.assertEqual(
            sin_cubrir, [],
            "Estas descargas son la ÚNICA vía para sacar su fichero. Si falla la "
            "descarga no queda ninguna, y eso bloqueó un frente entero el 2026-09-06. "
            f"O se les pone `{ALTERNATIVA}`, o entran en SIN_ALTERNATIVA con el motivo.",
        )

    def test_y_ninguna_exencion_se_ha_quedado_sin_descarga(self):
        """Una lista con entradas muertas deja de leerse y tapa el siguiente hallazgo."""
        funciones = {funcion for _, funcion in _descargas()}
        self.assertEqual(sorted(set(SIN_ALTERNATIVA) - funciones), [])

    def test_cada_exencion_dice_POR_QUE(self):
        for funcion, motivo in SIN_ALTERNATIVA.items():
            with self.subTest(funcion):
                self.assertGreater(len(motivo), 40)

    def test_los_CUATRO_ficheros_que_desbloquean_un_frente_la_tienen(self):
        """Los que paran una corrida de horas si no llegan: BLAST, seed, off-target y
        empalme. Son los que van a un servicio externo y vuelven."""
        con_alternativa = _alternativas()
        for modal in ("_modal_blast", "_modal_seed", "_modal_offtarget", "_modal_empalme"):
            with self.subTest(modal):
                self.assertIn(modal, con_alternativa)


class TestLaAlternativaNO_COMPARTE_MECANISMO(unittest.TestCase):
    """Lo que la hace una alternativa de verdad y no un segundo botón igual."""

    def _llamadas(self) -> set[str]:
        """Los `st.<algo>()` que hace el ayudante, por AST y no por texto.

        Su docstring NOMBRA `download_button` a propósito —explica de qué NO depende— y
        un `assertNotIn` sobre el fuente no distingue la prosa del código. Es la errata
        nº 121 en un test: el detector miraba la cadena, no lo que hace.
        """
        nodo = next(
            n for n in ast.walk(ARBOL)
            if isinstance(n, ast.FunctionDef) and n.name == ALTERNATIVA
        )
        return {
            c.func.attr for c in ast.walk(nodo)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
        }

    def test_no_usa_download_button(self):
        self.assertNotIn("download_button", self._llamadas())

    def test_pinta_el_contenido_como_TEXTO_en_la_pagina(self):
        self.assertIn("code", self._llamadas())

    def test_y_dice_COMO_se_llama_el_fichero(self):
        """Copiar el contenido sin saber el nombre deja el trabajo a medias."""
        cuerpo = FUENTE.split(f"def {ALTERNATIVA}(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("nombre", cuerpo)


class TestElMISMO_CONTENIDO_POR_LAS_DOS_VIAS(unittest.TestCase):
    """Dos vías que entregan cosas distintas son peor que una sola."""

    def test_el_FASTA_de_construcciones_se_calcula_UNA_vez(self):
        bloque = FUENTE.split("def _modal_empalme", 1)[1].split("\ndef ", 1)[0]
        self.assertEqual(bloque.count("texto_fasta = splice_query_text("), 1)
        # y el botón usa la variable, no una segunda llamada
        self.assertEqual(bloque.count("splice_query_text("), 1)
        self.assertEqual(bloque.count("splice_fasta_name("), 1)

    def test_y_el_bloque_de_seed_tambien(self):
        bloque = FUENTE.split("def _modal_seed", 1)[1].split("\ndef ", 1)[0]
        self.assertEqual(bloque.count("scan.export_block()"), 1)


if __name__ == "__main__":
    unittest.main()
