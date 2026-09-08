"""Un proyecto que no se puede leer NO se lleva por delante a los demás.

**Reportado (2026-09-08)**: *«algo gordo ha pasado porque ahora no me deja abrir un
proyecto previamente guardado»*.

**REPRODUCIDO**, y el fallo no está en abrir: está en LISTAR. `project_list` recorre el
directorio de proyectos y abre cada uno **sin ninguna protección**, así que basta con que
UNO no se pueda leer para que:

1. `project_options` aborte;
2. `_paso_cero_proyecto` la llama fuera de todo `try`, así que la excepción sube;
3. y —esto es lo que lo convierte en «algo gordo»— `Project(**crudo)` lanza un
   **`TypeError`**, que el `except (ShmirDesignError, ValueError, OSError)` de `main()`
   **NO captura**: la página muere con la traza de Streamlit y **el paso 0 no llega a
   pintarse**. No hay lista, no hay motivo, y los proyectos BUENOS son inalcanzables.

Un `proyecto.json` con un campo de más o de menos basta, y eso pasa en cuanto un
proyecto se escribe con una versión y se lee con otra — que es exactamente lo que ocurre
en el volumen después de un despliegue.

Es la familia de la errata nº 89 —una descarga que falla no puede tumbar el resto de la
página— y de la nº 137 —un aborto que borra la salida del propio problema—, aplicada a la
única pantalla que no se puede saltar.

**La regla: un proyecto ilegible sale NOMBRADO y con su motivo, y los demás se abren.**

Regla 5: escritos antes.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.store import PROJECT_FILE, ProjectStore

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _roto(raiz: Path, slug: str, crudo: dict) -> None:
    """Un proyecto cuyo `proyecto.json` esta app no sabe leer."""
    directorio = raiz / slug
    directorio.mkdir()
    (directorio / PROJECT_FILE).write_text(json.dumps(crudo), encoding="utf-8")
    (directorio / "registro.jsonl").write_text("", encoding="utf-8")


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElBuenoSIGUEsaliendo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.secuencia = load_reference(RATON)
        cls.anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(cls.secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        payload, fuente = presentation.anatomy_payload(self.anatomia)
        presentation.project_create(
            self.raiz, slug="Bueno", date="2026-09-08", sequence=self.secuencia,
            species="raton", anatomy=payload, anatomy_source=fuente,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_con_un_campo_DE_MENOS_el_bueno_sigue_en_la_lista(self):
        _roto(self.raiz, "Roto", {"slug": "Roto"})
        catalogo = presentation.project_options(self.raiz)
        self.assertEqual(catalogo["slugs"], ["Bueno"])

    def test_con_un_campo_DE_MAS_tampoco_se_esconde(self):
        # El caso simétrico: un `proyecto.json` escrito por una versión POSTERIOR.
        _roto(self.raiz, "Futuro", {
            "slug": "Futuro", "created": "2026-09-08", "sequence_md5": "x",
            "sequence_length": 1, "species": "raton", "anatomy": None,
            "anatomy_source": "declarado", "campo_que_no_existe": 1,
        })
        catalogo = presentation.project_options(self.raiz)
        self.assertEqual(catalogo["slugs"], ["Bueno"])

    def test_el_ilegible_SALE_NOMBRADO_y_con_su_motivo(self):
        # Esconderlo sería peor que el aborto: quien lo busca no lo encuentra y no sabe
        # por qué. La lista de abribles y la de rotos son DOS, y las dos se enseñan.
        _roto(self.raiz, "Roto", {"slug": "Roto"})
        catalogo = presentation.project_options(self.raiz)
        ilegibles = {i["slug"]: i["motivo"] for i in catalogo["ilegibles"]}
        self.assertEqual(sorted(ilegibles), ["Roto"])
        self.assertIn("proyecto.json", ilegibles["Roto"])

    def test_el_motivo_NOMBRA_los_campos_que_no_cuadran(self):
        # «No se pudo leer» no se puede investigar. Los campos se DERIVAN de la clase,
        # no se transcriben: uno nuevo queda cubierto sin que nadie se acuerde.
        _roto(self.raiz, "Roto", {"slug": "Roto"})
        with self.assertRaises(ShmirDesignError) as cm:
            ProjectStore.open(self.raiz, "Roto")
        motivo = str(cm.exception)
        self.assertIn("created", motivo)
        self.assertIn("sequence_md5", motivo)

    def test_y_el_de_un_campo_de_MAS_nombra_ESE_campo(self):
        _roto(self.raiz, "Futuro", {
            "slug": "Futuro", "created": "2026-09-08", "sequence_md5": "x",
            "sequence_length": 1, "species": "raton", "anatomy": None,
            "anatomy_source": "declarado", "campo_que_no_existe": 1,
        })
        with self.assertRaises(ShmirDesignError) as cm:
            ProjectStore.open(self.raiz, "Futuro")
        self.assertIn("campo_que_no_existe", str(cm.exception))

    def test_un_ilegible_NO_cuenta_como_abrible_ni_por_error(self):
        # Si entrara en `slugs`, el desplegable lo ofrecería y abrirlo volvería a
        # abortar — la trampa de ofrecer lo que no se puede hacer.
        _roto(self.raiz, "Roto", {"slug": "Roto"})
        catalogo = presentation.project_options(self.raiz)
        self.assertNotIn("Roto", catalogo["slugs"])
        self.assertNotIn("Roto", catalogo["etiquetas"])

    def test_TODOS_rotos_sigue_diciendo_lo_que_pasa(self):
        # El caso que más importa y el que un `if not slugs: return` se come: sin
        # ninguno abrible, la pantalla no puede quedarse muda.
        import shutil

        shutil.rmtree(self.raiz / "Bueno")
        _roto(self.raiz, "Roto", {"slug": "Roto"})
        catalogo = presentation.project_options(self.raiz)
        self.assertEqual(catalogo["slugs"], [])
        self.assertEqual([i["slug"] for i in catalogo["ilegibles"]], ["Roto"])

    def test_sin_ningun_proyecto_no_hay_ni_lista_ni_rotos(self):
        # Y esto NO cambia: el primer día la pantalla no pinta nada.
        import shutil

        shutil.rmtree(self.raiz / "Bueno")
        catalogo = presentation.project_options(self.raiz)
        self.assertEqual(catalogo["slugs"], [])
        self.assertEqual(catalogo["ilegibles"], [])


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaPaginaNoMUERE(unittest.TestCase):
    """De punta a punta: con un roto delante, el paso 0 se PINTA y el bueno se abre."""

    @classmethod
    def setUpClass(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:  # pragma: no cover
            # rule2-ok: Streamlit es dependencia SÓLO de la interfaz.
            raise unittest.SkipTest("Streamlit no instalado: la interfaz es opcional")

    def test_el_paso_cero_se_pinta_y_el_bueno_es_elegible(self):
        import os

        from streamlit.testing.v1 import AppTest

        from tests.pagina import ENV_PROYECTOS

        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            payload, fuente = presentation.anatomy_payload(anatomia)
            presentation.project_create(
                raiz, slug="Bueno", date="2026-09-08", sequence=secuencia,
                species="raton", anatomy=payload, anatomy_source=fuente,
            )
            _roto(raiz, "Roto", {"slug": "Roto"})
            antes = os.environ.get(ENV_PROYECTOS)
            os.environ[ENV_PROYECTOS] = str(raiz)
            try:
                app = AppTest.from_file(
                    str(RAIZ / "ui" / "streamlit_app.py"), default_timeout=300
                ).run()
                self.assertFalse(
                    [str(e.value) for e in app.exception],
                    "la página ha muerto por un proyecto que no se puede leer",
                )
                self.assertIn(
                    "Bueno", " ".join(app.selectbox[0].options),
                    "el proyecto bueno no llega al desplegable",
                )
                self.assertTrue(
                    any("Roto" in str(e.value) for e in app.error),
                    "el proyecto ilegible no se nombra en ninguna parte",
                )
            finally:
                if antes is None:
                    os.environ.pop(ENV_PROYECTOS, None)
                else:
                    os.environ[ENV_PROYECTOS] = antes


class TestElPasoCeroNoPuedeMORIR(unittest.TestCase):
    """La única pantalla que no se puede saltar no puede tumbar la app.

    Es la segunda vez que un aborto mata la página entera (la primera, errata nº 137), y
    aquí el coste es mayor: pasa ANTES de pintar nada, así que se lleva por delante hasta
    la explicación de lo que ha fallado.
    """

    def test_listar_los_proyectos_esta_protegido_en_la_pagina(self):
        fuente = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
        inicio = fuente.index("def _paso_cero_proyecto")
        cuerpo = fuente[inicio : fuente.index("\ndef ", inicio + 10)]
        llamada = cuerpo.index("project_options(raiz)")
        self.assertIn(
            "try:", cuerpo[:llamada],
            "`project_options` se llama sin protección: un fallo ahí mata la página "
            "antes de pintar el motivo",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
