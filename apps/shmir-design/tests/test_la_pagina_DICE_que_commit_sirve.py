"""La página dice QUÉ COMMIT está sirviendo, siempre y sin abrir nada.

Reportado por tercera vez el 2026-09-06, y con esas palabras:

    «Con la app mostrando su commit o su fecha de construcción, estos tres días de "está
     fusionado pero no lo veo" se habrían resuelto en un vistazo. Es la tercera vez.»

EL DATO YA ESTABA. `identidad.build_stamp()` lee `SHMIR_BUILD`, que el hub pasa al proceso
hijo desde `RAILWAY_GIT_COMMIT_SHA` — escrito, probado, y con un único consumidor: la
cabecera del FASTA de consulta de SpliceAI. O sea que para saber qué versión servía la app
había que generar un artefacto y abrirlo. Es el patrón de `page_run` otra vez: la
capacidad cableada a un sitio y no al que la necesita.

Y aquí el coste no es de información sino de TIEMPO AJENO: sin el sello, «está fusionado»
y «lo estás viendo» son indistinguibles desde la pantalla, y la única forma de separarlos
es que alguien mire el despliegue por su cuenta.
"""

import os
import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.identidad import BUILD_ENV, BUILD_NOT_DECLARED

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")


class TestElSelloSeEmite(unittest.TestCase):
    def setUp(self):
        self.previo = os.environ.get(BUILD_ENV)

    def tearDown(self):
        if self.previo is None:
            os.environ.pop(BUILD_ENV, None)
        else:
            os.environ[BUILD_ENV] = self.previo

    def test_con_la_variable_declarada_sale_el_commit(self):
        os.environ[BUILD_ENV] = "0123456789abcdef0123456789abcdef01234567"
        texto = presentation.build_banner()["texto"]
        self.assertIn("0123456", texto)

    def test_sin_la_variable_dice_SIN_DECLARAR_y_no_se_inventa_nada(self):
        os.environ.pop(BUILD_ENV, None)
        fila = presentation.build_banner()
        self.assertIn(BUILD_NOT_DECLARED, fila["texto"])
        self.assertFalse(fila["declarado"])

    def test_y_dice_QUE_HACER_cuando_no_cuadra(self):
        """Un sello que sólo da un sha deja a quien lo lee sin saber qué compararlo con
        qué. La contramedida es del principio nº 47: la salida donde está el bloqueo."""
        os.environ[BUILD_ENV] = "0123456789abcdef0123456789abcdef01234567"
        self.assertTrue(presentation.build_banner()["ayuda"])

    def test_el_sha_NO_se_recorta_del_todo(self):
        """Se enseña corto para leerlo y ENTERO para compararlo: un sha de 7 puede ser
        ambiguo y el que compara necesita el completo."""
        largo = "0123456789abcdef0123456789abcdef01234567"
        os.environ[BUILD_ENV] = largo
        self.assertEqual(presentation.build_banner()["commit"], largo)


class TestLaPaginaLoPINTA(unittest.TestCase):
    def test_la_pagina_llama_al_sello(self):
        self.assertIn("build_banner(", PAGINA)

    def test_y_NO_lee_la_variable_por_su_cuenta(self):
        """Regla 6: el texto y el recorte los decide `presentation`, con tests.

        SE QUITAN LOS COMENTARIOS ANTES DE MIRAR. El comentario que explica por qué el
        sello está ahí nombra la variable, así que sin la poda este test fallaría por su
        propia documentación — el ancla falsa al revés, y ya nos pasó con `st.rerun()`.
        """
        codigo = "\n".join(
            l for l in PAGINA.splitlines() if not l.strip().startswith("#")
        )
        self.assertNotIn("SHMIR_BUILD", codigo)
        self.assertNotIn("os.environ", codigo)


if __name__ == "__main__":
    unittest.main()
