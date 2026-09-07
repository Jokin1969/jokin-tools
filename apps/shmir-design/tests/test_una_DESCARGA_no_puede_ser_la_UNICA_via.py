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

#: LOS MECANISMOS que pueden ser una segunda vía, y `DESCARGA` NO está entre ellos.
#:
#: Es la forma mecánica del corolario de la errata nº 124 —*una vía y su alternativa no
#: pueden compartir el mecanismo que falla*—. Antes esto era prosa libre, y dos exenciones
#: alegaban «va también en el ZIP» sobre un ZIP que es otro `st.download_button`: la regla
#: incumplida POR ESCRITO dentro del test que la hace cumplir (errata nº 140). Prohibir esa
#: frase concreta fue una lista negra de redacciones; lo que cierra la forma es obligar a
#: DECLARAR el mecanismo, de un conjunto cerrado que no lo contiene.
MECANISMOS = {
    "ORIGEN_EXTERNO": "el fichero se vuelve a obtener de donde salió, fuera de esta app",
    "TEXTO_EN_PANTALLA": "el mismo contenido se pinta en la página y se puede copiar",
    "OTRO_FICHERO_COPIABLE": "lo que empaqueta tiene su propio bloque copiable al lado",
}

#: Descargas que NO necesitan bloque copiable PROPIO, con su mecanismo y su motivo. Van
#: por la función que las pinta: una descarga nueva en otra función tendrá que entrar aquí
#: y declarar por cuál de los tres mecanismos se saca su fichero si el botón falla.
SIN_ALTERNATIVA = {
    "_descargar_todo": (
        "ORIGEN_EXTERNO",
        "es un ZIP de hasta 84 MB — copiar y pegar binario no es una vía. Los ficheros "
        "del depósito están en su origen, y los registros de proyecto salen por el botón "
        "de «Gestionar proyectos», que sí tiene bloque copiable",
    ),
    "_fila_presente": (
        "ORIGEN_EXTERNO",
        "devuelve el fichero de referencia TAL CUAL, que puede ser `mature.fa` (5,6 MB) o "
        "un `.gb`; el original está donde se bajó y el gestor dice su md5 para poder "
        "comprobarlo",
    ),
    # OJO: esta función tiene DOS descargas de naturaleza distinta —los informes y el
    # export de candidatos— y la tabla se indexa por FUNCIÓN, así que esta entrada exime
    # SÓLO a los informes. El export tiene su propio `_tambien_para_copiar`, y por eso
    # `bloque_especie` sale a la vez aquí y en `_alternativas()`. No es una exención
    # caducada: es que la granularidad de esta tabla no llega a distinguir dos botones
    # dentro de una función, y decirlo aquí es más honesto que fingir que sí.
    "bloque_especie": (
        "TEXTO_EN_PANTALLA",
        "exime SÓLO a los informes (.docx/.pdf), que son binarios maquetados: copiar y "
        "pegar no es una vía para ellos, y su contenido íntegro está en el .md que se "
        "descarga al lado y en el informe de la propia pantalla. El export de candidatos "
        "de esta misma función NO va por aquí: tiene bloque copiable propio",
    ),
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
        for funcion, (_, motivo) in SIN_ALTERNATIVA.items():
            with self.subTest(funcion):
                self.assertGreater(len(motivo), 40)

    def test_cada_exencion_DECLARA_su_mecanismo(self):
        """Y el mecanismo sale de un conjunto CERRADO que no contiene `DESCARGA`.

        Es lo que convierte el corolario de la errata nº 124 en algo mecánico: una
        exención no puede alegar otra descarga como alternativa porque no hay forma de
        escribirlo. Prohibir la frase «va también en el ZIP» sólo prohibía esa redacción.
        """
        for funcion, (mecanismo, _) in SIN_ALTERNATIVA.items():
            with self.subTest(funcion):
                self.assertIn(mecanismo, MECANISMOS)

    def test_DESCARGA_no_es_un_mecanismo_declarable(self):
        """El control adversario de la regla: si lo fuera, la regla no diría nada."""
        for prohibido in ("DESCARGA", "ZIP", "BOTON", "OTRA_DESCARGA"):
            with self.subTest(prohibido):
                self.assertNotIn(prohibido, MECANISMOS)

    def test_el_EXPORT_de_candidatos_tiene_bloque_copiable(self):
        """Es el fichero que VIAJA, y su única vía era un botón que se cuelga.

        Por AST y no por `find`: la primera aparición del nombre en el fuente es el
        IMPORT, y buscar desde ahí medía la distancia desde la cabecera del fichero.
        Un detector que mira al sitio equivocado da el mismo rojo que uno que funciona,
        y el mismo verde (principio nº 51).
        """
        llamadas = [
            n.lineno for n in ast.walk(ARBOL)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "selected_export_file"
        ]
        self.assertEqual(len(llamadas), 1, "se esperaba UNA llamada al export")
        export = llamadas[0]

        copiables = [
            n.lineno for n in ast.walk(ARBOL)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == ALTERNATIVA
            and _funcion_de(n.lineno) == _funcion_de(export)
        ]
        self.assertTrue(
            copiables,
            f"el export no tiene `{ALTERNATIVA}` en su misma función: si la descarga se "
            f"cuelga no queda ninguna vía para el fichero que VIAJA.",
        )
        # Y ANTES de LA TABLA DEL PANEL — la que lleva el icono de Streamlit encima—,
        # no de la primera `st.dataframe` de la función, que es la de la anatomía y está
        # mucho más arriba. Un ancla al elemento equivocado da un rojo que no señala nada.
        tabla = min(
            n.lineno for n in ast.walk(ARBOL)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "site_table_rows"
        )
        self.assertLess(min(copiables), tabla, "el bloque copiable va DESPUÉS de la tabla")

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
