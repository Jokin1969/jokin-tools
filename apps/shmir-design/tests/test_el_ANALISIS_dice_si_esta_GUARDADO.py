"""Un análisis que se ve entero y no está guardado es indistinguible de uno que sí.

**EL CASO (2026-09-07).** El resultado de SpliceAI se procesó, se pintó completo —tablas,
destacados, la comparación entre guías— y **no quedó en el registro**. Con las palabras de
quien lo sufrió:

    «No sé si llegué a pulsar "Guardar en el proyecto" — el formulario está al final del
    todo, después de la última tabla, y el análisis se pinta antes. Ahí hay un problema de
    forma aunque no lo haya de fondo: el resultado aparece completo y convincente arriba, y
    lo que lo hace permanente está tres pantallas más abajo. Es fácil darlo por hecho.»

Y el coste: **la tercera corrida de SpliceAI**.

**No se mueve el formulario: se dice el estado donde se mira.** Mover el botón arriba
dejaría el guardado antes de haber visto lo que se guarda. Lo que faltaba no era el botón:
era saber, mirando el resultado, si ese resultado existe fuera de la pantalla.

Regla 5: escrito antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation  # noqa: E402
from shmir_design.identidad import result_fingerprint  # noqa: E402

#: Un resultado cualquiera y SU huella, derivada — no tecleada: si se escribiera un md5
#: a mano, el test pasaria con una comparacion que no es la que hace el codigo.
CRUDO = "construccion\tmd5\tposicion\ttipo\tpuntuacion\nx\ty\t1\tdonante\t0.5\n"
HUELLA = result_fingerprint(CRUDO)


class CorridaFalsa:
    def __init__(self, md5):
        self.result_md5 = md5


class AlmacenFalso:
    def __init__(self, *md5s):
        self.runs = [CorridaFalsa(m) for m in md5s]


class TestLosTresESTADOS(unittest.TestCase):

    def test_una_corrida_que_ESTA_en_el_log_sale_GUARDADA(self):
        ficha = presentation.run_saved_state(
            {"splice": AlmacenFalso(HUELLA)},
            front="empalme_sitios", raw=CRUDO,
        )
        self.assertEqual(ficha["estado"], presentation.GUARDADA_SI)

    def test_una_que_NO_esta_lo_dice_y_dice_QUE_SE_PIERDE(self):
        ficha = presentation.run_saved_state(
            {"splice": AlmacenFalso("otra")},
            front="empalme_sitios", raw=CRUDO,
        )
        self.assertEqual(ficha["estado"], presentation.GUARDADA_NO)
        self.assertIn("pierde", ficha["texto"])
        self.assertIn("final", ficha["texto"])

    def test_sin_proyecto_NO_es_lo_mismo_que_sin_guardar(self):
        """No es que no esté guardada: es que no puede estarlo, y se arregla con otra cosa."""
        ficha = presentation.run_saved_state(
            None, front="empalme_sitios", raw=CRUDO,
        )
        self.assertEqual(ficha["estado"], presentation.GUARDADA_SIN_PROYECTO)
        self.assertIn("barra lateral", ficha["texto"])

    def test_los_tres_estados_son_DISTINTOS(self):
        self.assertEqual(
            len({presentation.GUARDADA_SI, presentation.GUARDADA_NO,
                 presentation.GUARDADA_SIN_PROYECTO}),
            3,
        )


class TestSeComparaPOR_LA_HUELLA_DEL_RESULTADO(unittest.TestCase):
    """La fecha y el nombre los teclea una persona: no atan nada."""

    def test_sin_almacen_del_frente_sale_SIN_GUARDAR_y_no_revienta(self):
        ficha = presentation.run_saved_state(
            {}, front="empalme_sitios", raw=CRUDO,
        )
        self.assertEqual(ficha["estado"], presentation.GUARDADA_NO)

    def test_el_ALMACEN_de_cada_frente_esta_declarado_y_no_deducido(self):
        """`empalme_sitios` se guarda en `splice`: deducirlo del nombre daría siempre no."""
        self.assertEqual(
            presentation.STORE_FOR_SAVED_STATE["empalme_sitios"], "splice"
        )
        for frente, almacen in presentation.STORE_FOR_SAVED_STATE.items():
            with self.subTest(frente):
                self.assertIn(almacen, presentation.STORES)

    def test_y_el_motivo_de_que_vaya_ARRIBA_esta_escrito(self):
        texto = presentation.WHY_THE_SAVE_STATE_GOES_ON_TOP
        self.assertIn("indistinguible", texto)
        self.assertIn("SpliceAI", texto)


class TestLaPaginaLO_PINTA_JUNTO_AL_RESULTADO(unittest.TestCase):

    def test_el_estado_sale_ANTES_que_las_tablas_del_analisis(self):
        fuente = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
        modal = fuente.split("def _modal_empalme", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("run_saved_state(", modal)
        self.assertLess(
            modal.index("run_saved_state("),
            modal.index("splice_result_rows("),
            "el estado de guardado tiene que verse ANTES del análisis, no después",
        )

    def test_y_el_formulario_de_guardar_SIGUE_al_final(self):
        """No se mueve: guardar antes de ver lo que se guarda sería peor."""
        fuente = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
        modal = fuente.split("def _modal_empalme", 1)[1].split("\ndef ", 1)[0]
        self.assertGreater(
            modal.index("_guardar_corrida("), modal.index("run_saved_state(")
        )


if __name__ == "__main__":
    unittest.main()
