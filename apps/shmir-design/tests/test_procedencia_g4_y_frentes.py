"""Frentes que no lo son, las dos reglas de la selección, y el marco de las columnas.

(La parte de G4 vivió aquí; el filtro se retiró el 2026-08-27 — ver `test_g4_fuera.py`,
`docs/procedencia-g4.md` y la errata nº 9.)

Regla 5: escritos antes.

**Cuatro cosas que salieron de la segunda ejecución real de la página**, y las cuatro
son de la misma familia: algo que emite un veredicto sin que nadie haya decidido que
debe emitirlo, o que dice una causa que no ha comprobado.

  1. `G4_diana` **emitía FAIL con un criterio sin justificar**. No es un filtro nuevo
     —es el paso 8 de `docs/pipeline.md` desde el commit fundacional— pero su criterio
     es una expresión regular escrita a mano y **no tiene entrada en `justificacion.py`**,
     porque el test que exige justificación recorre los campos de `Thresholds` y G4 no
     es un umbral. Un filtro duro que puede excluir a un candidato con un criterio que
     nadie ha discutido es un problema de PROCEDENCIA.
  2. Un **filtro biofísico se convertía en FRENTE**. Con la máscara puesta, 66 ventanas
     quedan con `N` y sus filtros de secuencia salen `NOT_RUN` — correcto, regla 3. Pero
     `blocking_fronts` construía un frente por cada `NOT_RUN`, así que `GC` y `G4_diana`
     aparecían como frentes abiertos y la app pedía su ficha de obtención. Una ventana
     enmascarada NO es un frente, y GC no necesita ningún fichero.
  3. Y el motivo de ese frente decía **«falta el recurso»** de un filtro que no tiene
     recurso. Tercera de esa familia, después del «comprueba que Streamlit está
     instalado» y del «Alu 0 %».
  4. La página **no aplicaba la tabla de APA medido** y el CLI sí. Es la cuarta
     divergencia entre los dos frontales, la misma clase de fallo que obligó a crear
     `resolve.py`.
"""

import unittest

from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_reference

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _entrada():
    secuencia = load_reference(RATON)
    return secuencia, Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )


class TestUnFiltroBIOFISICO_NO_ES_UN_FRENTE(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.masking import RepeatMask
        from shmir_design import presentation
        from shmir_design.selection import SelectionConfig

        secuencia, anatomia = _entrada()
        # La máscara real del ratón: `(CTC)n` en tx:892-936, dentro del CDS. Enmascarar
        # deja ventanas con `N`, y sus filtros de secuencia salen NOT_RUN.
        mascara = RepeatMask(intervals=((892, 936),), source="rmsk_mouse.out")
        cls.corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
            config=SelectionConfig(n_candidates=10), mask=mascara,
        )

    def test_hay_ventanas_con_filtros_biofisicos_en_NOT_RUN(self):
        # Si esto deja de ser cierto, el resto de la clase no prueba nada.
        self.assertGreater(self.corrida.selection.not_run_filters.get("GC", 0), 0)

    def test_pero_GC_NO_sale_como_frente(self):
        from shmir_design.selection import blocking_fronts

        nombres = {
            f.name
            for f in blocking_fronts(self.corrida.tiling, self.corrida.selection)
        }
        self.assertNotIn("GC", nombres)
        self.assertNotIn("homopolimero", nombres)
        self.assertNotIn("asimetria", nombres)

    def test_ni_G4(self):
        from shmir_design.selection import blocking_fronts

        nombres = {
            f.name
            for f in blocking_fronts(self.corrida.tiling, self.corrida.selection)
        }
        self.assertNotIn("G4_diana", nombres)
        self.assertNotIn("G4_guia", nombres)

    def test_y_la_pagina_ya_no_ABORTA_pidiendo_su_ficha(self):
        from shmir_design import presentation

        filas = presentation.front_help_rows(
            self.corrida.tiling, self.corrida.selection, species="raton"
        )
        self.assertTrue(filas)

    def test_TODO_frente_que_salga_tiene_ficha(self):
        """El test bidireccional de las fichas, ahora sobre una corrida de verdad."""
        from shmir_design.obtencion import load_all
        from shmir_design.selection import blocking_fronts

        conocidas = set(load_all())
        for frente in blocking_fronts(self.corrida.tiling, self.corrida.selection):
            with self.subTest(frente.name):
                self.assertIn(frente.name, conocidas)

    def test_las_ventanas_enmascaradas_se_SIGUEN_contando_aparte(self):
        """Quitarlas de los frentes no es esconderlas: van en el semáforo."""
        from shmir_design import presentation

        luz = presentation.status_light(self.corrida.selection)
        self.assertIn(f"{luz.tiled} ventanas tiladas", luz.detail)

    def test_y_el_motivo_de_un_frente_NO_afirma_un_recurso_que_no_existe(self):
        from shmir_design.selection import blocking_fronts

        for frente in blocking_fronts(self.corrida.tiling, self.corrida.selection):
            with self.subTest(frente.name):
                if "falta el recurso" in frente.reason:
                    # Solo lo puede decir un frente que de verdad se cierra con un
                    # fichero. Es la regla del diagnóstico comprobado.
                    from shmir_design.obtencion import resolve_ficha
                    from shmir_design.species import resolve

                    ficha = resolve_ficha(frente.name, species=resolve("raton"))
                    self.assertFalse(
                        ficha.no_file,
                        f"{frente.name} dice «falta el recurso» y su ficha dice que no "
                        f"se cierra con ningún fichero",
                    )


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLaPaginaAPLICA_EL_APA_MEDIDO(unittest.TestCase):
    """Cuarta divergencia entre los dos frontales. La lección de `resolve.py`."""

    def test_page_run_coloca_la_tabla_como_el_CLI(self):
        from shmir_design import presentation
        from shmir_design.selection import SelectionConfig

        secuencia, anatomia = _entrada()
        corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
            config=SelectionConfig(n_candidates=10),
        )
        self.assertIsNotNone(
            corrida.tiling.measured_apa,
            "El CLI aplica `resolve_measured` y la página no lo hacía: sin la tabla, el "
            "tercer sitio de corte no promociona y la frontera de inmunidad se queda "
            "donde no es.",
        )

    def test_y_por_eso_el_tercer_sitio_de_corte_PROMOCIONA(self):
        from shmir_design import presentation
        from shmir_design.polya import SignalClass
        from shmir_design.selection import SelectionConfig

        secuencia, anatomia = _entrada()
        corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
            config=SelectionConfig(n_candidates=10),
        )
        # `AATATA` en 3utr:236 = tx:1185. Es variante RARA: por predicción saldría OTRA,
        # y entra como APA_POSIBLE por MEDIDA. Las dos vías no se confunden nunca.
        promovida = [
            s
            for s in corrida.tiling.signals
            if s.classification is SignalClass.APA_POSSIBLE
            and s.motif == "AATATA"
        ]
        self.assertTrue(promovida, "el AATATA de 3utr:236 no promocionó")


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLasDosREGLAS_DE_LA_SELECCION(unittest.TestCase):
    """Cuota por tercio a secas contra cuota por tercio + inmunes."""

    def test_la_cuota_de_INMUNES_existe_y_ya_no_vale_cero_por_defecto(self):
        from shmir_design.selection import DEFAULT_IMMUNE_QUOTA, default_config

        # La cuota va en `default_config()`, no en el dataclass: la pareja
        # (cuota, frontera) tiene que resolverse junta, y un `SelectionConfig()` a mano
        # no tiene informe del que sacar la frontera.
        self.assertGreater(DEFAULT_IMMUNE_QUOTA, 0)
        self.assertEqual(default_config().apa_immune_quota, DEFAULT_IMMUNE_QUOTA)
        self.assertEqual(default_config(n_candidates=2).apa_immune_quota, 2)

    def test_el_panel_por_defecto_son_DIEZ_como_el_del_proyecto(self):
        from shmir_design.selection import DEFAULT_CANDIDATES

        self.assertEqual(DEFAULT_CANDIDATES, 10)

    def test_sin_cuota_de_inmunes_el_panel_pierde_uno(self):
        """El hecho que motiva la cuota, medido y fijado."""
        from shmir_design import presentation
        from shmir_design.selection import SelectionConfig, default_config

        secuencia, anatomia = _entrada()
        sin = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
            config=SelectionConfig(n_candidates=10, apa_immune_quota=0),
        )
        con = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
            config=default_config(n_candidates=10),
        )
        inmunes_sin = presentation.immune_count(sin.tiling, sin.selection)
        inmunes_con = presentation.immune_count(con.tiling, con.selection)
        self.assertLess(inmunes_sin, inmunes_con)
        self.assertGreaterEqual(inmunes_con, 4)
        # El hecho concreto: sin cuota entra `3utr:359` (+4,82) y con ella `3utr:200`
        # (+3,80). Los dos son proximales, así que la cuota de tercios se cumple igual y
        # nada delataba el cambio.
        def _utr3(corrida):
            return {corrida.anatomy.utr3_position(c.start)
                    for c in corrida.selection.selection.chosen}
        self.assertIn(359, _utr3(sin))
        self.assertIn(200, _utr3(con))

    def test_y_las_dos_reglas_se_pueden_COMPARAR_lado_a_lado(self):
        from shmir_design import presentation

        secuencia, anatomia = _entrada()
        texto = presentation.selection_rules_report(
            species="raton", sequence=secuencia, anatomy=anatomia
        )
        self.assertIn("solo cuota por tercio", texto)
        self.assertIn("cuota de inmunes", texto)
        # Y dice cuántos inmunes deja cada una, que es la cifra que decide.
        self.assertIn("inmunes", texto.lower())


class TestTodaColumnaDePosicionLLEVA_SU_MARCO(unittest.TestCase):
    """`polyA_hexamero_pos = 1185` es `tx:1185`, o sea `3utr:236`.

    Bien calculado y mal etiquetado. `inicio_3utr` lleva el marco en el nombre; éstas no
    lo llevaban ni en el nombre ni en el valor, que es la misma familia del `3utr:1185`
    que ya apareció.
    """

    def test_la_posicion_del_hexamero_sale_ETIQUETADA(self):
        from shmir_design.polya import PolyAAnnotation

        self.assertIn("polyA_hexamero_pos", PolyAAnnotation.__doc__ or "")

    @unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
    def test_sobre_la_corrida_de_verdad_ninguna_posicion_va_desnuda(self):
        from shmir_design import presentation
        from shmir_design.selection import SelectionConfig

        secuencia, anatomia = _entrada()
        corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
            config=SelectionConfig(n_candidates=10),
        )
        for fila in presentation.candidate_rows(corrida.selection):
            valor = str(fila.get("polyA_hexamero_pos", ""))
            if valor:
                with self.subTest(valor):
                    self.assertRegex(valor, r"^(tx|3utr):\d+$")

    @unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
    def test_y_la_distancia_al_extremo_3_dice_que_es_una_DISTANCIA(self):
        # Una distancia no es una posición y no lleva marco: lleva unidad. Mezclarlas en
        # columnas que se leen seguidas es lo que hace que un número se lea como el otro.
        from shmir_design import presentation
        from shmir_design.selection import SelectionConfig

        secuencia, anatomia = _entrada()
        corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
            config=SelectionConfig(n_candidates=10),
        )
        filas = presentation.candidate_rows(corrida.selection)
        con_dato = [f for f in filas if str(f.get("polyA_dist_extremo3", ""))]
        self.assertTrue(con_dato)
        for fila in con_dato:
            with self.subTest(fila["inicio"]):
                self.assertRegex(str(fila["polyA_dist_extremo3"]), r"^\d+ nt$")


if __name__ == "__main__":
    unittest.main()


class TestLaPaginaLLAMA_A_page_run(unittest.TestCase):
    """El tercer `store.save_*`, y lo cazó el análisis de alcanzabilidad.

    `page_run` se escribió justo para que la página no rehiciera el camino y pudiera
    divergir del CLI. Se documentó como «la página llama ahora a page_run». **Y la
    página no lo llamaba**: seguía tilando a mano, así que el APA medido que se cableó
    en `page_run` no llegaba a la pantalla.

    Ni los tests ni el golden lo veían: los tests llamaban a `page_run` ellos mismos y
    el golden se genera desde `page_snapshot`, que también lo llama. Lo que faltaba era
    justo lo que este análisis mira — quién lo llama en el camino de verdad.
    """

    def test_la_pagina_no_tila_por_su_cuenta(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("page_run(", fuente)
        # `tile_utr` y `select_from_report` son el camino que `page_run` encapsula: si
        # la página vuelve a llamarlos, vuelve a poder divergir.
        self.assertNotIn("tile_utr(", fuente)
        self.assertNotIn("select_from_report(", fuente)
