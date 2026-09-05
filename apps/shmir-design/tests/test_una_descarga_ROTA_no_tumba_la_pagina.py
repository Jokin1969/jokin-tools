"""Un botón de descarga que falla se queda en su sitio; la página sigue.

**Reportado (2026-09-04)**, con el mensaje entero delante:

    PARA — La fecha del zip tiene que ser AAAA-MM-DD y llegó «sin fecha declarada»

**Son DOS fallos, y el segundo es el que convierte una molestia en un bloqueo.**

1. **La fecha del informe salía de una clave que NADIE escribe.** `fecha_informe` se
   leía en dos sitios de la página **con dos valores por defecto distintos**: en el
   informe con el literal `"sin fecha declarada"`, y en el zip de resultados con
   `"" or today_text()`. La primera llega a `Document.generated`, de ahí al `.docx`
   —que es un zip— y `deterministic_zip` la rechaza, con razón. O sea: el arreglo de la
   errata nº 76 hizo la fecha obligatoria y **no había dónde declararla**, así que el
   `.docx` pasó de corromperse a ser imposible. Es la errata nº 47 otra vez —una
   comparación que preguntaba por una clave que no existe— con el signo cambiado: aquí
   no devuelve un veredicto falso, aborta siempre.

2. **Y el aborto se llevaba por delante media página.** El bloque del informe no tenía
   guardia propio, así que la excepción subía hasta el `try` de `main()`, que pinta el
   motivo y **hace `return`**. Todo lo que va debajo —los cuatro modales, «Descargas»,
   el paso 5— dejaba de pintarse. Por eso el error salía «en la sección del informe»:
   ahí es donde el script se paró.

**La regla que queda: un entregable que falla NO puede tumbar a los otros dos ni al
resto de la página.** Los tres formatos se construyen por separado y cada uno lleva su
resultado o su motivo; la página pinta el botón o el error EN SU SITIO.

Regla 5: escritos antes.
"""

import re
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation  # noqa: E402
from shmir_design.gestor import deterministic_zip  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402

FUENTE = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """Un comentario que EXPLICA el fallo no es el fallo.

    Sin esto, el comentario que cuenta de donde venia `fecha_informe` haria fallar
    el guardia — y la salida facil seria borrar la explicacion. Es la errata nº 54
    (un ancla dentro de un comentario) con el signo cambiado.
    """
    return "\n".join(l for l in texto.split("\n") if not l.lstrip().startswith("#"))


def _claves_de_sesion(texto: str) -> tuple[set[str], set[str]]:
    """Las claves de `session_state` que se LEEN y las que se ESCRIBEN."""
    texto = _sin_comentarios(texto)
    leidas = set(re.findall(r'session_state\.get\(\s*["\']([^"\']+)["\']', texto))
    leidas |= set(
        re.findall(r'session_state\[\s*["\']([^"\']+)["\']\s*\](?!\s*=)', texto)
    )
    escritas = set(re.findall(r'session_state\[\s*["\']([^"\']+)["\']\s*\]\s*=', texto))
    escritas |= set(
        re.findall(r'session_state\.setdefault\(\s*["\']([^"\']+)["\']', texto)
    )
    # Una clave de widget la escribe Streamlit al pintarlo, no la página.
    escritas |= set(re.findall(r'key=["\']([^"\']+)["\']', texto))
    return leidas, escritas


class TestNingunaClaveSeLeeSinEscribirse(unittest.TestCase):
    """El guardia general, no el parche de `fecha_informe`.

    Una clave que se lee y nadie escribe **siempre** devuelve su valor por defecto, así
    que lo que decide de verdad es ese literal — y aquí había dos distintos para la
    misma clave. Es la familia de la errata nº 47: preguntar por una clave que no puede
    existir da una respuesta con la forma correcta.
    """

    def test_no_hay_ninguna(self):
        leidas, escritas = _claves_de_sesion(FUENTE)
        huerfanas = sorted(leidas - escritas)
        self.assertEqual(
            huerfanas, [],
            f"Estas claves de sesión se leen y no las escribe nadie, así que su valor "
            f"es SIEMPRE el literal por defecto: {huerfanas}",
        )

    def test_el_detector_ENCUENTRA_claves(self):
        """Control adversario: si dejara de encontrarlas, el test de arriba daría verde.

        «Ninguna huérfana» y «no he mirado» son el mismo verde, que es la errata nº 29.
        """
        leidas, escritas = _claves_de_sesion(FUENTE)
        self.assertGreaterEqual(len(leidas), 2)
        self.assertGreaterEqual(len(escritas), 2)

    def test_MUERDE_sobre_el_codigo_de_antes(self):
        antes = 'x = st.session_state.get("fecha_informe", "sin fecha declarada")\n'
        leidas, escritas = _claves_de_sesion(antes)
        self.assertEqual(sorted(leidas - escritas), ["fecha_informe"])


class TestLaFechaDelInformeSeDeriva(unittest.TestCase):
    """Generar un informe pasa AHORA, así que su fecha es hoy y se deriva.

    Es el criterio ya escrito para el resto de la app (errata nº 64): lo que ocurre
    ahora lleva hoy porque ésa es la verdad; lo que se descargó otro día viene vacío
    porque poner hoy sería inventarse el dato. Un informe se genera al pulsar.
    """

    def test_la_pagina_NO_lee_ninguna_fecha_de_sesion(self):
        self.assertNotIn("fecha_informe", _sin_comentarios(FUENTE))

    def test_today_text_vale_para_el_zip(self):
        # La condición que el `.docx` necesita: `AAAA-MM-DD` y nada más.
        self.assertRegex(presentation.today_text(), r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(
            deterministic_zip({"a.txt": "x"}, date=presentation.today_text())
        )

    def test_y_el_literal_de_antes_ABORTABA(self):
        # Fijado para que se vea que el aborto era correcto: lo que estaba mal era el
        # llamador, no el guardia.
        with self.assertRaises(ShmirDesignError):
            deterministic_zip({"a.txt": "x"}, date="sin fecha declarada")


def _documento_con_fecha_mala():
    """UN `Document` DE VERDAD con la fecha que rompia el `.docx`.

    No es un doble: es la clase real, con su `__post_init__` y sus bloques, y lo unico
    anomalo es exactamente lo que se reporto — una `generated` que no es `AAAA-MM-DD`.
    Un doble con los atributos justos probaria el comparador y no el caso (principio
    nº 18): `to_docx` mira el titulo, las secciones y los bloques, asi que un objeto con
    tres campos habria fallado por otra cosa y el test habria pasado por el motivo
    equivocado.
    """
    from shmir_design.informe_doc import Document, Section, para

    return Document(
        title="Informe de prueba",
        state="PARCIAL",
        generated="no es una fecha",
        open_fronts=("especificidad",),
        sections=(
            Section(number=1, title="Qué se analizó", blocks=(para("Nada."),)),
        ),
    )


class TestUnFormatoRotoNoSeLlevaALosOtros(unittest.TestCase):
    def setUp(self):
        self.entregables = presentation.informe_files(
            _documento_con_fecha_mala(), stem="raton"
        )

    def test_siguen_saliendo_los_TRES(self):
        # No se omite el roto: se omitiría la única señal de que algo falla.
        self.assertEqual(len(self.entregables), 3)

    def test_el_roto_trae_MOTIVO_y_no_datos(self):
        roto = [e for e in self.entregables if e["nombre"].endswith(".docx")][0]
        self.assertIsNone(roto["datos"])
        self.assertIn("AAAA-MM-DD", roto["error"])

    def test_los_otros_dos_traen_DATOS_y_sin_motivo(self):
        sanos = [e for e in self.entregables if not e["nombre"].endswith(".docx")]
        self.assertEqual(len(sanos), 2)
        for entregable in sanos:
            self.assertTrue(entregable["datos"])
            self.assertEqual(entregable["error"], "")


class TestLaPaginaPintaElErrorEnSuSITIO(unittest.TestCase):
    def test_el_bloque_del_informe_mira_el_motivo(self):
        bloque = FUENTE[FUENTE.index("entregables = informe_files"):]
        bloque = bloque[:bloque.index("# LO GUARDADO SE RELEE")]
        self.assertIn('entregable["error"]', bloque)

    def test_y_no_construye_los_tres_de_golpe_fuera_del_guardia(self):
        """`informe_files` ya no puede reventar: cada formato trae su resultado."""
        self.assertIn("DOWNLOAD_FAILED_NOTE", FUENTE)


if __name__ == "__main__":
    unittest.main()
