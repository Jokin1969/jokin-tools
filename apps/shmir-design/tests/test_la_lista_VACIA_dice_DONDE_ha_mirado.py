"""Cero proyectos NO es «no hay»: es «no hay AHÍ», y hay que decir dónde es ahí.

**Reportado (2026-09-08), con la captura delante**: el paso 0 —«¿Retomas un proyecto
guardado?»— **no aparece**, y la página sigue viva y pinta el paso 1. O sea que no es el
aborto de la errata nº 150: es que `project_options` devolvió CERO proyectos y
`_paso_cero_proyecto` hacía `return None` **sin decir nada**.

**Y cero se lee como «no tengo ninguno guardado» cuando lo que ha pasado es «he mirado en
otro sitio».** Es el «Alu 0 %» sobre el directorio de proyectos: un cero obtenido sin
decir dónde se buscó.

El sitio lo decide `SHMIR_PROJECT_DIR`. **Sin declarar, los proyectos van junto al
paquete** —o sea DENTRO de la imagen— y este proyecto ya tenía escrito lo que eso
significa: *«en producción se pierde en el siguiente redespliegue, sin ningún síntoma
hasta que alguien busca lo que guardó ayer»*. Esto es exactamente ese día, y el síntoma
que faltaba.

**La regla: la pantalla que lista dice DÓNDE ha mirado, y si ese sitio es el del paquete
lo dice con esas palabras.** Es la misma que ya se aplicaba al directorio de referencia
—«cuando el de trabajo NO es el del paquete, la interfaz lo dice con la ruta delante»—,
que aquí faltaba y que aquí pesa más: la referencia se vuelve a bajar, un registro de
decisiones no.

Regla 5: escritos antes.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.trabajo import PROJECT_ENV_VAR


class TestDiceDondeHaMirado(unittest.TestCase):
    def test_la_ruta_SIEMPRE_sale(self):
        with tempfile.TemporaryDirectory() as tmp:
            sitio = presentation.projects_location({PROJECT_ENV_VAR: tmp})
            self.assertEqual(sitio["ruta"], str(Path(tmp)))
            self.assertIn(tmp, sitio["texto"])

    def test_declarado_y_vacio_NO_es_lo_mismo_que_sin_declarar(self):
        with tempfile.TemporaryDirectory() as tmp:
            declarado = presentation.projects_location({PROJECT_ENV_VAR: tmp})
        sin = presentation.projects_location({})
        self.assertTrue(declarado["declarado"])
        self.assertFalse(sin["declarado"])
        self.assertNotEqual(declarado["texto"], sin["texto"])

    def test_sin_declarar_el_texto_dice_que_es_el_del_PAQUETE(self):
        texto = presentation.projects_location({})["texto"]
        self.assertIn("SHMIR_PROJECT_DIR", texto)
        self.assertIn("paquete", texto.lower())

    def test_y_dice_la_CONSECUENCIA_no_solo_el_hecho(self):
        # «Va junto al paquete» no significa nada para quien busca su proyecto. Lo que
        # hay que saber es que ahí, en un despliegue, no sobrevive.
        texto = presentation.projects_location({})["texto"]
        self.assertIn("redespliegue", texto)

    def test_un_directorio_declarado_que_NO_existe_se_dice(self):
        sitio = presentation.projects_location({PROJECT_ENV_VAR: "/no/existe/aqui"})
        self.assertFalse(sitio["existe"])
        self.assertIn("no existe", sitio["texto"])

    def test_cuenta_las_CARPETAS_y_los_proyectos_por_separado(self):
        # Una carpeta sin `proyecto.json` se salta EN SILENCIO en `project_list`. Con las
        # dos cifras, «no hay ninguno» y «hay tres y ninguno se puede listar» dejan de
        # dar la misma pantalla.
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "una").mkdir()
            (Path(tmp) / "otra").mkdir()
            sitio = presentation.projects_location({PROJECT_ENV_VAR: tmp})
            self.assertEqual(sitio["carpetas"], 2)
            self.assertEqual(sitio["proyectos"], 0)
            self.assertIn("2", sitio["texto"])

    def test_con_proyectos_de_verdad_las_dos_cifras_cuadran(self):
        with tempfile.TemporaryDirectory() as tmp:
            from shmir_design.store import PROJECT_FILE

            hecho = Path(tmp) / "Bueno"
            hecho.mkdir()
            (hecho / PROJECT_FILE).write_text("{}", encoding="utf-8")
            sitio = presentation.projects_location({PROJECT_ENV_VAR: tmp})
            self.assertEqual((sitio["carpetas"], sitio["proyectos"]), (1, 1))


class TestLaPaginaNoSeQuedaMUDA(unittest.TestCase):
    """Con cero proyectos, el paso 0 tiene que DECIR dónde ha mirado."""

    @classmethod
    def setUpClass(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:  # pragma: no cover
            # rule2-ok: Streamlit es dependencia SÓLO de la interfaz.
            raise unittest.SkipTest("Streamlit no instalado: la interfaz es opcional")

    def test_sin_ningun_proyecto_la_pagina_dice_el_sitio(self):
        import os
        import sys

        from streamlit.testing.v1 import AppTest

        raiz = Path(__file__).resolve().parent.parent
        if str(raiz) not in sys.path:
            sys.path.insert(0, str(raiz))
        from tests.pagina import ENV_PROYECTOS

        with tempfile.TemporaryDirectory() as tmp:
            antes = os.environ.get(ENV_PROYECTOS)
            os.environ[ENV_PROYECTOS] = tmp
            try:
                app = AppTest.from_file(
                    str(raiz / "ui" / "streamlit_app.py"), default_timeout=300
                ).run()
                self.assertFalse([str(e.value) for e in app.exception])
                pintado = " ".join(
                    [str(c.value) for c in app.caption]
                    + [str(w.value) for w in app.warning]
                    + [str(e.value) for e in app.error]
                )
                self.assertIn(
                    tmp, pintado,
                    "con cero proyectos la página no dice dónde ha mirado: un cero así "
                    "se lee como «no tengo ninguno» y puede ser «he mirado en otro sitio»",
                )
            finally:
                if antes is None:
                    os.environ.pop(ENV_PROYECTOS, None)
                else:
                    os.environ[ENV_PROYECTOS] = antes


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
