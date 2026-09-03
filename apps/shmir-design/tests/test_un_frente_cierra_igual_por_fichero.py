"""Un frente que cierra el FICHERO del depósito llega igual que uno que cierra una corrida.

**Reportado con el export delante (2026-09-03).** El contador decía «2 de 7
comprobaciones hechas» y sólo una tarjeta estaba en verde, mientras los diez candidatos
del panel salían con `transgen: PASS` y `seed_colision: PASS` en el export — con
`aav_casete.fa` y `mature.fa` cargados. La única tarjeta verde era `especificidad`, que
es el único frente con corrida guardada.

**La causa, y es la misma de la errata nº 54 un consumidor más allá.** `blocking_fronts`
decide qué frentes están abiertos con `selection.not_run_filters`, que cuenta los
`NOT_RUN` sobre **las 2170 ventanas tiladas** — y 1790 de ellas ni siquiera llegan a los
filtros con recurso porque ya cayeron antes. Un `NOT_RUN` de una ventana descartada no es
una laguna de nada: nadie iba a preguntarle. La unidad de la pregunta «¿está cerrado este
frente?» es **el panel**, exactamente como ya lo era para las corridas guardadas.

O sea: había DOS reglas para la misma pregunta. Un frente cerrado por corrida se decidía
sobre el panel (`run_coverage`) y uno cerrado por fichero sobre las 2170 ventanas. Por eso
la tarjeta y la columna podían discrepar, y por eso la contramedida no es arreglar la
tarjeta: es que **las dos salgan del mismo sitio**.

Y al escribirlo salió un segundo fallo que nadie había visto todavía: `store_states_by_front`
**no contestaba nada de los frentes POR HEBRA**, así que una corrida de seed o de
off-targets no habría cerrado su frente nunca — sólo la de BLAST podía. Coincide con lo
observado («la de especificidad es la única verde») y no era esa la causa; es un fallo
LATENTE que el mismo reporte destapó.

Regla 5: escritos antes.
"""

import unittest

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import REFERENCES, fixture_available, load_reference

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

#: Los dos frentes del reporte: los cierra un fichero que YA está en el depósito, sin
#: ninguna corrida. Se nombran aquí para que el test diga de qué habla.
CERRADOS_POR_FICHERO = ("transgen", "seed_colision")


def _corrida_con_el_deposito():
    from shmir_design import resources as RES
    from shmir_design.species import resolve
    from shmir_design.trabajo import reference_dir

    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )
    recursos = RES.load_from_manifest(reference_dir(), species=resolve("raton"))
    return presentation.page_run(
        species="raton", sequence=secuencia, anatomy=anatomia, resources=recursos,
    ), recursos


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLaTarjetaYLaColumnaNOpuedenDiscrepar(unittest.TestCase):
    """El criterio de aceptación, tal cual se pidió, sobre la corrida de verdad."""

    @classmethod
    def setUpClass(cls):
        cls.corrida, cls.recursos = _corrida_con_el_deposito()
        cls.filas = presentation.candidate_rows(cls.corrida.selection, species="raton")
        cls.tarjetas = {
            t["frente"]: t
            for t in presentation.front_card_rows(
                cls.corrida, species="raton", stores=None
            )
        }

    def test_el_deposito_de_la_prueba_TRAE_los_dos_ficheros(self):
        # CONTROL: sin `aav_casete.fa` y `mature.fa` conectados, los dos frentes estarían
        # abiertos con toda la razón y el resto de esta clase pasaría sin probar nada.
        conectados = set(self.recursos.connected)
        self.assertIn("aav_casete.fa", conectados)
        self.assertIn("mature.fa", conectados)

    def test_los_diez_del_panel_tienen_respuesta_en_esos_dos_frentes(self):
        for frente in CERRADOS_POR_FICHERO:
            estados = {fila[frente] for fila in self.filas}
            self.assertTrue(
                estados <= set(presentation.ESTADOS_QUE_RESPONDEN),
                f"{frente}: el panel trae {sorted(estados)}, y este test da por hecho "
                f"que los diez tienen veredicto.",
            )

    def test_y_por_eso_su_tarjeta_esta_HECHA(self):
        for frente in CERRADOS_POR_FICHERO:
            self.assertEqual(
                self.tarjetas[frente]["estado"], "HECHO",
                f"{frente}: los diez candidatos del panel tienen veredicto en la "
                f"columna y la tarjeta sigue gris. Es el desacuerdo reportado.",
            )

    def test_la_tarjeta_dice_que_lo_cerro_el_FICHERO_y_no_una_corrida(self):
        # Dos causas, dos textos: «cerrado por corrida guardada» sobre un frente que
        # nadie ha corrido manda a buscar en el registro del proyecto, donde no hay nada.
        for frente in CERRADOS_POR_FICHERO:
            self.assertIn("depósito", self.tarjetas[frente]["avance"])

    def test_NINGUN_frente_con_columna_puede_estar_abierto_con_el_panel_contestado(self):
        """La invariante entera, no sólo los dos del reporte."""
        # Sólo los frentes que SON una columna de la tabla: `empalme_intron` y
        # `empalme_sitios` no lo son —lo declara `FRONTS_WITHOUT_COLUMN`— así que de
        # ellos no hay columna con la que comparar.
        for frente, tarjeta in self.tarjetas.items():
            if frente not in self.filas[0]:
                continue
            estados = {fila[frente] for fila in self.filas}
            contestado = estados <= set(presentation.ESTADOS_QUE_RESPONDEN)
            self.assertEqual(
                contestado, tarjeta["estado"] == "HECHO",
                f"{frente}: la columna dice {sorted(estados)} y la tarjeta "
                f"{tarjeta['estado']}. No pueden discrepar.",
            )

    def test_ESPECIFICIDAD_sigue_abierta_sin_su_fichero(self):
        # CONTROL ADVERSARIO: si todo saliera HECHO, esta prueba no distinguiría un
        # frente cerrado de una comprobación que no comprueba. `refseq_rna.fa` no está.
        self.assertEqual(self.tarjetas["especificidad"]["estado"], "SIN_HACER")


class TestUnaVentanaSINveredictoDEJAelFrenteABIERTO(unittest.TestCase):
    """La otra mitad: cubrir el panel es la condición, y no se puede relajar."""

    def test_un_solo_NOT_RUN_del_panel_basta_para_no_cerrar(self):
        cerrados = presentation.fronts_closed_over_panel(
            {"transgen": {10: "PASS", 20: "NOT_RUN"}}, starts=(10, 20)
        )
        self.assertNotIn("transgen", cerrados)

    def test_SUSTITUIDO_y_NO_APLICA_SI_son_respuestas(self):
        # `SUSTITUIDO` nombra a su sustituto y `check_substitution` impide que exista con
        # el sustituto en NOT_RUN, así que no es una laguna. `NO_APLICA` tampoco: la
        # pregunta no se le hace a ese candidato.
        cerrados = presentation.fronts_closed_over_panel(
            {"seed": {10: "SUSTITUIDO", 20: "NO_APLICA"}}, starts=(10, 20)
        )
        self.assertIn("seed", cerrados)

    def test_SIN_CONSULTAR_no_es_una_respuesta(self):
        cerrados = presentation.fronts_closed_over_panel(
            {"seed_colision": {10: "PASS", 20: presentation.SIN_CONSULTAR}},
            starts=(10, 20),
        )
        self.assertNotIn("seed_colision", cerrados)


class TestUnFrentePORHEBRAtambienSeCierraPorCorrida(unittest.TestCase):
    """El fallo LATENTE que destapó el reporte, y no era su causa.

    `store_states_by_front` preguntaba a los almacenes con el nombre del frente PELADO.
    Para `seed_colision` y `offtarget_seed` el veredicto es por hebra, así que
    `_store_state` devolvía `None` — o sea, una corrida de seed que cubriera el panel
    entero **no cerraba su frente nunca**. Sólo BLAST podía, que es lo que se veía.
    """

    class _AlmacenFalso:
        runs = ("una",)

        def __init__(self, consultas):
            self._consultas = set(consultas)

        def history(self, consulta):
            return ("x",) if consulta in self._consultas else ()

        def verdict_for(self, consulta, **_):
            from shmir_design.filters import FilterResult, FilterState

            return FilterResult(
                name="seed_colision", state=FilterState.PASS,
                reason="corrida de prueba",
            )

    def _almacen(self, especie, starts, hebras):
        from shmir_design.presentation import query_name
        from shmir_design.species import resolve

        especie = resolve(especie)
        return {
            "seed": self._AlmacenFalso(
                query_name(especie, s, h) for s in starts for h in hebras
            )
        }

    def test_con_LAS_DOS_hebras_corridas_el_frente_contesta(self):
        estados = presentation.store_states_by_front(
            self._almacen("raton", (10, 20), ("guia", "pasajera")),
            species="raton", starts=(10, 20),
        )
        self.assertIn("seed_colision", estados)
        self.assertEqual(sorted(estados["seed_colision"]), [10, 20])

    def test_con_SOLO_LA_GUIA_el_frente_NO_se_cierra(self):
        # Fundir las dos daría por buena la de la pasajera con el estado de la guía, que
        # es justo lo que la ficha parte en dos filas para no hacer. La pasajera sale
        # `SIN_CONSULTAR` —hay corridas de este frente y ninguna la miró—, que se
        # RECOGE (dice más que el silencio) y NO cierra nada.
        almacen = self._almacen("raton", (10, 20), ("guia",))
        estados = presentation.store_states_by_front(
            almacen, species="raton", starts=(10, 20),
        )
        self.assertEqual(
            set(estados["seed_colision"].values()), {presentation.SIN_CONSULTAR}
        )
        self.assertNotIn(
            "seed_colision",
            presentation.fronts_closed_over_panel(estados, starts=(10, 20)),
        )


if __name__ == "__main__":
    unittest.main()
