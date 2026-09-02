"""A cuántos candidatos se PREGUNTA, que no es lo mismo que cuántos se ELIGEN.

**Pedido el 2026-09-02**, y la distinción la puso quien lo pidió:

    El panel sigue en 10 con sus cuotas. Lo que cambia es a cuántos se pregunta, no
    cuántos se eligen. Bajar el espaciado es otra decisión, con su coste en independencia
    entre apuestas, y merece discutirse aparte y por escrito.

Así que el alcance es de la CORRIDA, no de la selección. Y la unidad son los **86 sitios**,
no las 270 ventanas: ventanas solapadas de la misma región comparten casi toda su
secuencia, así que preguntar por las tres daría el mismo resultado repetido y ensuciaría
cualquier recuento. «Cada región una vez» es la unidad correcta para especificidad, seed y
off-targets.

Y el coste va POR MODAL, con una condición: **donde no está medido, la etiqueta lo dice**
en vez de dar un número inventado. Con la lección de los cuatro minutos por clic delante
(errata nº 59).

Regla 5: escritos antes.
"""

import unittest
from dataclasses import replace
from pathlib import Path

from shmir_design import insumos, presentation
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.selection import default_config, select_from_report
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _seleccion(**cambios):
    informe = tile_utr(load_3utr(RATON))
    return select_from_report(informe, replace(default_config(), **cambios))


@unittest.skipUnless(HAY, "falta el fixture del 3'UTR murino")
class TestLosDosALCANCES(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sel = _seleccion()

    def test_son_DOS_y_el_panel_es_el_primero(self):
        # El panel va primero porque es el defecto: preguntar por 86 es la excepción.
        filas = presentation.scope_rows(self.sel, kind="corrida_seed")
        self.assertEqual([f["clave"] for f in filas], ["panel", "elegibles"])

    def test_el_panel_son_los_10_de_siempre(self):
        starts = presentation.scope_starts(self.sel, "panel")
        self.assertEqual(list(starts), presentation.chosen_starts(self.sel))
        self.assertEqual(len(starts), 10)

    def test_y_TODOS_son_los_SITIOS_no_las_ventanas(self):
        # 86 sitios, no las ~270 ventanas elegibles: tres ventanas solapadas de la misma
        # región dan el mismo resultado tres veces.
        starts = presentation.scope_starts(self.sel, "elegibles")
        self.assertEqual(len(starts), len(self.sel.selection.sites))
        self.assertGreater(len(starts), 50)

    def test_uno_POR_sitio_y_es_el_MEJOR_del_sitio(self):
        # El representante no se elige aquí: es `Site.best`, el mismo criterio con el que
        # la selección ya ordena. Otro criterio sería una segunda definición de «el mejor».
        starts = set(presentation.scope_starts(self.sel, "elegibles"))
        self.assertEqual(starts, {s.best.start for s in self.sel.selection.sites})

    def test_el_panel_es_SUBCONJUNTO_de_todos(self):
        # Si no lo fuera, cambiar de alcance PERDERIA candidatos ya consultados.
        self.assertTrue(
            set(presentation.scope_starts(self.sel, "panel"))
            <= set(presentation.scope_starts(self.sel, "elegibles"))
        )

    def test_un_alcance_que_no_existe_ABORTA(self):
        # Devolver el panel por defecto ante un valor desconocido daria una corrida de 10
        # etiquetada como de 86.
        with self.assertRaises(ShmirDesignError):
            presentation.scope_starts(self.sel, "todos_los_que_sean")


@unittest.skipUnless(HAY, "falta el fixture del 3'UTR murino")
class TestLoQueDICE_la_etiqueta(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sel = _seleccion()

    def test_cada_fila_dice_CUANTOS_candidatos_y_CUANTAS_consultas(self):
        for fila in presentation.scope_rows(self.sel, kind="corrida_seed"):
            with self.subTest(fila["clave"]):
                self.assertIn(str(fila["candidatos"]), fila["etiqueta"])
                self.assertIn(str(fila["consultas"]), fila["etiqueta"])

    def test_las_consultas_se_DERIVAN_de_las_hebras(self):
        # Dos por candidato porque hay dos hebras, y esa cifra sale de `STRANDS`: escribir
        # un 2 aqui seria afirmar que son dos, que es lo que el nucleo ya declara.
        fila = presentation.scope_rows(self.sel, kind="corrida_seed")[0]
        self.assertEqual(
            fila["consultas"], fila["candidatos"] * len(presentation.STRANDS)
        )

    def test_donde_el_coste_NO_esta_medido_la_etiqueta_LO_DICE(self):
        # Es la condicion con la que se pidio: mejor «no medido» que un numero inventado.
        for tipo, unidades in (
            ("corrida_offtarget", None), ("corrida_empalme", ("mvm_actual",)),
        ):
            with self.subTest(tipo):
                fila = presentation.scope_rows(self.sel, kind=tipo, units=unidades)[1]
                self.assertFalse(fila["coste_medido"])
                self.assertIn("NO está medido", fila["coste"])

    def test_y_donde_SI_lo_esta_no_dice_que_no(self):
        # Control adversario: si todo dijera «no medido», la distincion no distinguiria.
        for tipo in ("corrida_blast", "corrida_seed"):
            with self.subTest(tipo):
                fila = presentation.scope_rows(self.sel, kind=tipo)[1]
                self.assertTrue(fila["coste_medido"])
                self.assertNotIn("NO está medido", fila["coste"])

    def test_el_coste_esta_declarado_para_los_CUATRO_modales(self):
        # Se cruza contra `insumos.CONSUMIDOS`, que es la tabla que ya declara los tipos
        # de corrida: un quinto modal sin coste declarado falla aqui, no el dia que
        # alguien pulse y se quede esperando.
        self.assertEqual(
            set(presentation.COSTE_POR_ALCANCE), set(insumos.CONSUMIDOS)
        )

    def test_un_tipo_de_corrida_desconocido_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            presentation.scope_rows(self.sel, kind="corrida_inventada")

    def test_el_EMPALME_exige_decir_QUE_intrones_se_consultan(self):
        # Su unidad es el par candidato x intron, y cuantos intrones se consultan lo
        # elige quien corre. Derivarlo de «los que tienen secuencia» anunciaria 172
        # consultas cuando se van a hacer 86.
        with self.assertRaises(ShmirDesignError):
            presentation.scope_rows(self.sel, kind="corrida_empalme")
        fila = presentation.scope_rows(
            self.sel, kind="corrida_empalme", units=("mvm_actual", "quimerico")
        )[0]
        self.assertEqual(fila["consultas"], fila["candidatos"] * 2)


@unittest.skipUnless(HAY, "falta el fixture del 3'UTR murino")
class TestElPANEL_no_se_toca(unittest.TestCase):
    """Lo que cambia es a cuántos se pregunta, no cuántos se eligen."""

    def test_pedir_el_alcance_grande_NO_cambia_la_seleccion(self):
        sel = _seleccion()
        antes = presentation.chosen_starts(sel)
        presentation.scope_starts(sel, "elegibles")
        self.assertEqual(presentation.chosen_starts(sel), antes)

    def test_el_panel_sigue_siendo_de_10_con_sus_cuotas(self):
        sel = _seleccion()
        self.assertEqual(len(sel.selection.chosen), 10)
        self.assertEqual(sel.selection.quota_unfilled, ())


@unittest.skipUnless(HAY, "falta el fixture del 3'UTR murino")
class TestElPARAMETRO_que_MENTIA(unittest.TestCase):
    """«Pediste 50, el espaciado de 50 nt deja 14» — y hasta hoy no se decía EN LA PÁGINA.

    El núcleo ya lo apuntaba en `Selection.notes` desde siempre, y sólo lo emitía el
    informe de texto del CLI. Quien sube el número en la barra lateral ve la MISMA tabla y
    concluye, con razón, que la app no le hace caso. Es el principio nº 23: dos artefactos
    leen el mismo estado y sólo uno lo cuenta.
    """

    def test_el_nucleo_lo_apunta(self):
        sel = _seleccion(n_candidates=50)
        self.assertEqual(len(sel.selection.chosen), 14)
        self.assertTrue(sel.selection.notes)

    def test_y_presentation_lo_saca_en_una_FILA_que_avisa(self):
        filas = presentation.selection_notes(_seleccion(n_candidates=50))
        self.assertTrue(filas)
        self.assertTrue(filas[0]["avisa"])
        texto = filas[0]["texto"]
        self.assertIn("50", texto)
        self.assertIn("14", texto)

    def test_cuando_SI_caben_no_avisa_de_nada(self):
        # Control adversario: un aviso que sale siempre deja de leerse.
        self.assertEqual(presentation.selection_notes(_seleccion()), [])


class TestLaPAGINA(unittest.TestCase):

    def setUp(self):
        import re

        crudo = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        sin_doc = re.sub(r'"""[\s\S]*?"""', "", crudo)
        self.fuente = "\n".join(
            l for l in sin_doc.splitlines() if not l.strip().startswith("#")
        )

    def _modal(self, nombre: str) -> str:
        import re

        return re.split(r"\ndef ", self.fuente.split(f"def {nombre}(", 1)[1])[0]

    def test_los_CUATRO_modales_ofrecen_el_alcance(self):
        for modal in (
            "_modal_blast", "_modal_seed", "_modal_offtarget", "_modal_empalme",
        ):
            with self.subTest(modal):
                self.assertIn("_selector_de_alcance", self._modal(modal))

    def test_y_ninguno_sigue_pidiendo_solo_el_panel(self):
        # `chosen_starts` es «el panel y punto». Con alcance, los starts salen del
        # selector: si quedara alguna llamada directa, ese modal ignoraria la eleccion.
        for modal in (
            "_modal_blast", "_modal_seed", "_modal_offtarget", "_modal_empalme",
        ):
            with self.subTest(modal):
                self.assertNotIn("chosen_starts(", self._modal(modal))

    def test_la_casilla_INERTE_de_blast_ya_no_esta(self):
        # «Sólo los del panel» no filtraba nada: las filas salian ya sólo del panel y
        # todas llevaban `panel: True` escrito. Un control que no se distingue de uno que
        # funciona es la errata nº 32 otra vez.
        self.assertNotIn("Sólo los del panel", self.fuente)

    def test_la_pagina_PINTA_las_notas_de_la_seleccion(self):
        self.assertIn("selection_notes", self.fuente)

    def test_y_no_decide_ella_el_alcance(self):
        panel = self._modal("_selector_de_alcance")
        for prohibido in ("len(", "sorted(", "sites", "* 2"):
            with self.subTest(prohibido):
                self.assertNotIn(prohibido, panel)


if __name__ == "__main__":
    unittest.main()
