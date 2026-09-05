"""La configuración se registra con la selección, y la app avisa si ya no coincide.

**Pedido por el responsable del proyecto (2026-09-04)**, en dos pasos y el segundo es el
que importa:

  · *«¿los ajustes se guardan en el proyecto o son sólo de sesión?»* — son de sesión, y
    callarlo hace creer que se corrió con una configuración cuando se corrió con otra.
    Es el `--inmunes 4` del golden (principio nº 18) del lado del usuario;
  · *«la configuración tiene que quedar ATADA al panel, no sólo guardada al lado. Si
    alguien cambia un umbral y vuelve a diseñar sin guardar selección nueva, el panel en
    pantalla deja de corresponder a la configuración registrada, y nada lo dice.»*

Guardada al lado, la discrepancia es invisible. Atada por huella, **se deriva** — que es
exactamente lo que hace `OBSOLETO` con los ficheros de una corrida: se hizo, y ya no vale
con lo que hay ahora.

**Y NO se restaura al reabrir**, decidido: restaurar los controles desde el proyecto daría
DOS fuentes de verdad en la barra lateral —lo guardado y lo que el widget diga—, que es la
casilla global «Usar los de `data/reference/`» otra vez. Registrar sí; restaurar no.

Regla 5: escritos antes.
"""

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation  # noqa: E402
from shmir_design.hard_filters import Thresholds  # noqa: E402
from shmir_design.scaffold import SGEP_SCAFFOLD  # noqa: E402
from shmir_design.selection import SelectionConfig  # noqa: E402
from shmir_design.store import ProjectStore, selected_configuration  # noqa: E402

SONDA = "GCGTCAGTACGATCGAATTACT" * 6


def _configuracion(**cambios):
    base = {
        "config": SelectionConfig(),
        "thresholds": Thresholds(),
        "accessibility": False,
        "scaffold": SGEP_SCAFFOLD,
        "resources": {"mature.fa": "a" * 32},
    }
    base.update(cambios)
    return presentation.run_configuration(**base)


class TestLaConfiguracionEsSerializable(unittest.TestCase):

    def test_recoge_los_cuatro_ejes_que_mueven_un_panel(self):
        conf = _configuracion()
        for eje in ("seleccion", "umbrales", "accesibilidad", "andamio", "ficheros"):
            self.assertIn(eje, conf)

    def test_los_ficheros_van_CON_SU_md5(self):
        # Un fichero cambiado debajo mueve el resultado igual que un umbral.
        self.assertEqual(_configuracion()["ficheros"]["mature.fa"], "a" * 32)

    def test_la_huella_es_ESTABLE_entre_llamadas(self):
        from shmir_design.identidad import configuration_fingerprint

        self.assertEqual(
            configuration_fingerprint(_configuracion()),
            configuration_fingerprint(_configuracion()),
        )

    def test_y_CAMBIA_al_cambiar_un_umbral(self):
        from shmir_design.identidad import configuration_fingerprint

        otra = _configuracion(thresholds=Thresholds(gc_min=0.35))
        self.assertNotEqual(
            configuration_fingerprint(_configuracion()),
            configuration_fingerprint(otra),
        )

    def test_y_CAMBIA_al_marcar_la_accesibilidad(self):
        from shmir_design.identidad import configuration_fingerprint

        self.assertNotEqual(
            configuration_fingerprint(_configuracion()),
            configuration_fingerprint(_configuracion(accessibility=True)),
        )

    def test_un_valor_que_no_se_puede_serializar_ABORTA(self):
        """Nunca por `repr`: la huella dependería del código y no de la configuración."""
        from shmir_design.errors import ShmirDesignError
        from shmir_design.identidad import configuration_fingerprint

        with self.assertRaises(ShmirDesignError):
            configuration_fingerprint({"x": object()})


class TestVaATADA(unittest.TestCase):

    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="conf_"))
        self.store = ProjectStore.create(
            self.raiz, slug="P1", sequence=SONDA, species="raton",
            anatomy=None, anatomy_source="lo tilado ES el 3'UTR",
            created="2026-09-04",
        )

    def test_la_seleccion_guarda_la_configuracion_y_su_huella(self):
        presentation.save_selection(
            self.store, starts=(10, 60), date="2026-09-04", by="jc",
            configuration=_configuracion(),
        )
        guardada, huella = selected_configuration(self.store)
        self.assertEqual(guardada["accesibilidad"], False)
        self.assertTrue(huella)

    def test_con_la_MISMA_configuracion_no_avisa(self):
        presentation.save_selection(
            self.store, starts=(10,), date="2026-09-04", by="jc",
            configuration=_configuracion(),
        )
        estado = presentation.selection_configuration_state(
            self.store, actual=_configuracion()
        )
        self.assertTrue(estado["coincide"])
        self.assertEqual(estado["estado"], "")

    def test_con_OTRA_configuracion_AVISA_y_dice_que_hacer(self):
        presentation.save_selection(
            self.store, starts=(10,), date="2026-09-04", by="jc",
            configuration=_configuracion(),
        )
        estado = presentation.selection_configuration_state(
            self.store, actual=_configuracion(accessibility=True)
        )
        self.assertFalse(estado["coincide"])
        self.assertEqual(estado["estado"], "CAMBIADA")
        self.assertIn("selección nueva", estado["texto"])

    def test_una_seleccion_de_ANTES_dice_que_NO_SE_PUDO_COMPROBAR(self):
        """No haber podido comprobarlo no es que coincida — el `.out` sin resumen."""
        presentation.save_selection(
            self.store, starts=(10,), date="2026-09-04", by="jc",
        )
        estado = presentation.selection_configuration_state(
            self.store, actual=_configuracion()
        )
        self.assertIsNone(estado["coincide"])
        self.assertEqual(estado["estado"], "NO_REGISTRADA")

    def test_sin_ninguna_seleccion_solo_dice_que_los_ajustes_son_de_sesion(self):
        estado = presentation.selection_configuration_state(
            self.store, actual=_configuracion()
        )
        self.assertEqual(estado["estado"], "")
        self.assertIn("de esta sesión", estado["texto"])


class TestLoQueSeDICEyLoQueNOSeHACE(unittest.TestCase):

    def test_el_aviso_dice_que_los_ajustes_NO_se_restauran(self):
        self.assertIn("NO se restauran", presentation.SETTINGS_ARE_SESSION_ONLY)

    def test_la_pagina_NO_restaura_ningun_ajuste_desde_el_proyecto(self):
        """Restaurarlos daría dos fuentes de verdad: es la casilla global otra vez."""
        fuente = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
        limpia = "\n".join(
            l for l in fuente.split("\n") if not l.lstrip().startswith("#")
        )
        self.assertNotIn("selected_configuration", limpia)


if __name__ == "__main__":
    unittest.main()
