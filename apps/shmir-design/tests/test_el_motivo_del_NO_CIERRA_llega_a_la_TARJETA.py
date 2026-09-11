"""Hay corrida y NO CIERRA: la tarjeta dice POR QUE, no «falta el recurso».

**Reportado con el panel humano delante (2026-09-11).** Los once candidatos salian
`especificidad: NO_CIERRA` en el CSV —la corrida guardada `blast-2026-09-09` estaba
registrada, se leia y daba veredicto— y la tarjeta de ese mismo frente decia:

    NOT_RUN en 2414 de 2414 ventanas: falta el recurso. NOT_RUN no es PASS.

**Las dos frases eran ciertas y contestaban a preguntas distintas.** La de la tarjeta es
del ESCANER DE VENTANA, que efectivamente no ha corrido porque falta `refseq_rna.fa`; la
de la celda es la de la CORRIDA GUARDADA, que si esta y lo que dice es que no puede dar
veredicto (alli, porque la diana de esa especie no estaba declarada). La que se pintaba
era la de la pregunta que nadie habia hecho, y manda a descargar una base de decenas de
GB que no habria desbloqueado nada.

**LA CAUSA, y es de la familia del principio nº 27 vista desde el otro lado.**
`run_coverage` cuenta como CUBIERTO solo lo que esta en `ESTADOS_QUE_RESPONDEN`, y
`NO_CIERRA` es una laguna — con razon: no da veredicto, asi que el frente no se cierra.
Pero entonces `cubiertos` sale 0 y el frente cae en la rama «nadie ha tocado esto», o sea
**indistinguible de un proyecto sin ninguna corrida**. Y el motivo que emite el almacen
—`FilterResult.reason`, que es lo unico que dice QUE hay que hacer— se calculaba y se
tiraba en `_store_state`.

Asi que son dos huecos y ninguno sustituye al otro: que el motivo SOBREVIVA hasta arriba
(`panel_states_by_front` → `motivos`) y que haya un estado para «se consulto y no cierra»
(`run_coverage` → `bloqueo`) distinto de «no se consulto».

**Y entra por `blocking_fronts`, no por la tarjeta**: ese motivo lo leen la tarjeta, el
informe descargable y la ficha, y metido por cada consumidor se arregla uno y los demas
siguen igual — que es exactamente lo que costo la errata nº 54.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import unittest

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.coords import Frame
from shmir_design.filters import FilterResult, FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.selection import blocking_fronts

RATON = REFERENCES["NM_011170.3"]

#: El texto que la tarjeta pintaba, y que es del OTRO escaner. Se cita por el trozo que
#: lo identifica sin atarse a la redaccion entera.
TEXTO_DEL_ESCANER = "falta el recurso"

#: El motivo que emite el almacen. Se escribe aqui porque es el doble quien lo pone; lo
#: que el test comprueba es que ESE llega a la tarjeta, no cual es.
MOTIVO_DE_LA_CORRIDA = (
    "NO_CIERRA: la corrida se leyó y no puede dar veredicto porque la especie no "
    "declara sus variantes de transcrito."
)


class _AlmacenQueNoCierra:
    """Un almacen con corrida que contesta `NO_CIERRA` CON MOTIVO a todo el panel.

    Es la forma REAL del caso: `history` devuelve algo —la corrida existe y cubre a ese
    candidato— y `verdict_for` da un estado que no responde. Un doble que devolviera
    `NOT_RUN` probaria otra cosa: ahi no hay corrida que leer.
    """

    def __init__(self, consultas, *, frente):
        self._consultas = frozenset(consultas)
        self._frente = frente
        self.runs = ("una corrida",)

    def history(self, consulta):
        return ("x",) if consulta in self._consultas else ()

    def verdict_for(self, consulta, **_):
        return FilterResult(
            name=self._frente,
            state=FilterState.NO_CIERRA,
            reason=MOTIVO_DE_LA_CORRIDA,
        )


def _almacenes_para(frente: str, *, starts, especie: str):
    declarado = presentation.STORE_FOR_FRONT[frente]
    hebras = presentation.STRANDS if declarado["por_hebra"] else ("guia",)
    consultas = [
        presentation.query_name(especie, inicio, hebra)
        for inicio in starts for hebra in hebras
    ]
    return {declarado["almacen"]: _AlmacenQueNoCierra(consultas, frente=frente)}


PANEL = (10, 60, 143)


class TestElMotivoSOBREVIVEhastaLaCobertura(unittest.TestCase):
    """La mecanica, para TODOS los frentes con almacen. No para el que se reporto."""

    def _vista(self, frente):
        almacenes = _almacenes_para(frente, starts=PANEL, especie="raton")
        return presentation.store_verdicts_by_front(
            almacenes, species="raton", starts=PANEL,
        )

    def test_el_almacen_devuelve_el_MOTIVO_ademas_del_estado(self):
        for frente in presentation.STORE_FOR_FRONT:
            with self.subTest(frente=frente):
                por_candidato = self._vista(frente).get(frente) or {}
                self.assertTrue(
                    por_candidato,
                    f"{frente}: la corrida cubre el panel y no contesta nada.",
                )
                for inicio, (estado, motivo) in por_candidato.items():
                    self.assertEqual(estado, FilterState.NO_CIERRA.value)
                    self.assertEqual(motivo, MOTIVO_DE_LA_CORRIDA, f"inicio {inicio}")

    def test_store_states_by_front_SIGUE_dando_solo_el_estado(self):
        """La proyeccion no cambia de forma: muchos llamadores dependen de ella."""
        for frente in presentation.STORE_FOR_FRONT:
            with self.subTest(frente=frente):
                estados = presentation.store_states_by_front(
                    _almacenes_para(frente, starts=PANEL, especie="raton"),
                    species="raton", starts=PANEL,
                )
                self.assertEqual(
                    estados[frente],
                    {i: FilterState.NO_CIERRA.value for i in PANEL},
                )

    def test_run_coverage_emite_BLOQUEO_con_el_motivo_de_la_corrida(self):
        for frente in presentation.STORE_FOR_FRONT:
            with self.subTest(frente=frente):
                vista = self._vista(frente)
                estados = {
                    f: {i: e for i, (e, _) in por.items()}
                    for f, por in vista.items()
                }
                motivos = {
                    f: {i: m for i, (_, m) in por.items() if m}
                    for f, por in vista.items()
                }
                fila = presentation.run_coverage(
                    estados, starts=PANEL, frame=Frame.UTR3, reasons=motivos,
                )[frente]
                self.assertFalse(fila["cerrado"])
                self.assertEqual(fila["cubiertos"], 0)
                self.assertIn(MOTIVO_DE_LA_CORRIDA, fila["bloqueo"])
                self.assertIn("HAY CORRIDA Y NO CIERRA", fila["bloqueo"])

    def test_Y_SIN_LOS_MOTIVOS_no_hay_bloqueo(self):
        """CONTROL ADVERSARIO: sin `reasons` esto se comporta como antes.

        Sin el, «emite el bloqueo» y «emite algo pase lo que pase» darian el mismo verde.
        """
        vista = self._vista("especificidad")
        estados = {f: {i: e for i, (e, _) in por.items()} for f, por in vista.items()}
        fila = presentation.run_coverage(
            estados, starts=PANEL, frame=Frame.UTR3,
        )["especificidad"]
        self.assertEqual(fila["bloqueo"], "")
        self.assertEqual(fila["motivo"], "")
        self.assertEqual(fila["avance"], "")

    def test_bloqueo_NO_repite_a_motivo_ni_a_avance(self):
        """Errata nº 108: un campo que repite a otro pinta lo mismo dos veces."""
        vista = self._vista("especificidad")
        estados = {f: {i: e for i, (e, _) in por.items()} for f, por in vista.items()}
        motivos = {f: {i: m for i, (_, m) in por.items()} for f, por in vista.items()}
        fila = presentation.run_coverage(
            estados, starts=PANEL, frame=Frame.UTR3, reasons=motivos,
        )["especificidad"]
        self.assertTrue(fila["bloqueo"].strip())
        self.assertNotEqual(fila["bloqueo"], fila["motivo"])
        self.assertNotEqual(fila["bloqueo"], fila["avance"])

    def test_y_los_que_NADIE_MIRO_se_dicen_APARTE(self):
        """Dos causas y dos salidas: una pide otra corrida, la otra no."""
        vista = self._vista("especificidad")
        estados = {f: {i: e for i, (e, _) in por.items()} for f, por in vista.items()}
        motivos = {f: {i: m for i, (_, m) in por.items()} for f, por in vista.items()}
        panel = (*PANEL, 200)
        fila = presentation.run_coverage(
            estados, starts=panel, frame=Frame.UTR3, reasons=motivos,
        )["especificidad"]
        self.assertIn("3utr:200", fila["bloqueo"])
        self.assertIn("no llegó a preguntar", fila["bloqueo"])


class TestBlockingFrontsAceptaElMotivo(unittest.TestCase):
    """Entra por `blocking_fronts` para que lo vean sus SEIS llamadores a la vez."""

    @classmethod
    def setUpClass(cls):
        if not fixture_available(RATON):
            raise unittest.SkipTest("NOT_RUN: falta data/reference/NM_011170.3.fa")
        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
        )

    def _frente(self, **kwargs):
        for frente in blocking_fronts(
            self.corrida.tiling, self.corrida.selection, **kwargs
        ):
            if frente.name == "especificidad":
                return frente
        self.fail("`especificidad` no sale de `blocking_fronts`")

    def test_SIN_el_motivo_sale_el_texto_del_ESCANER(self):
        """CONTROL: es el texto reportado, y sigue siendo el correcto sin corrida."""
        frente = self._frente()
        self.assertTrue(frente.blocking)
        self.assertIn(TEXTO_DEL_ESCANER, frente.reason)

    def test_CON_el_motivo_manda_el_de_la_corrida(self):
        frente = self._frente(blocked_by_panel={"especificidad": MOTIVO_DE_LA_CORRIDA})
        self.assertTrue(frente.blocking)
        self.assertEqual(frente.reason, MOTIVO_DE_LA_CORRIDA)
        self.assertNotIn(TEXTO_DEL_ESCANER, frente.reason)

    def test_y_un_frente_CERRADO_conserva_el_suyo(self):
        """`closed_by_panel` manda: de un frente cerrado no bloquea nada."""
        frente = self._frente(
            closed_by_panel={"especificidad": "CERRADO por corrida guardada: los 3."},
            blocked_by_panel={"especificidad": MOTIVO_DE_LA_CORRIDA},
        )
        self.assertFalse(frente.blocking)
        self.assertNotIn(MOTIVO_DE_LA_CORRIDA, frente.reason)


class TestLaTarjetaLoPINTA(unittest.TestCase):
    """El camino entero, que es donde vivia el fallo: corrida → tarjeta."""

    @classmethod
    def setUpClass(cls):
        if not fixture_available(RATON):
            raise unittest.SkipTest("NOT_RUN: falta data/reference/NM_011170.3.fa")
        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia,
        )
        cls.panel = presentation.chosen_starts(cls.corrida.selection)
        cls.almacenes = _almacenes_para(
            "especificidad", starts=cls.panel, especie="raton",
        )

    def _tarjeta(self, stores):
        for tarjeta in presentation.front_card_rows(
            self.corrida, species="raton", stores=stores
        ):
            if tarjeta["frente"] == "especificidad":
                return tarjeta
        self.fail("no hay tarjeta de `especificidad`")

    def test_SIN_corrida_la_tarjeta_dice_lo_del_escaner(self):
        # CONTROL: sin este caso, «la tarjeta dice el motivo de la corrida» y «la tarjeta
        # dice cualquier cosa» darian el mismo verde.
        tarjeta = self._tarjeta(None)
        self.assertEqual(tarjeta["estado"], "SIN_HACER")
        self.assertIn(TEXTO_DEL_ESCANER, tarjeta["motivo"])

    def test_CON_la_corrida_que_NO_CIERRA_dice_el_motivo_de_la_corrida(self):
        """El criterio de aceptacion, con las palabras con que se pidio: «el motivo
        correcto para mostrar es el que viene del NO_CIERRA, no el del NOT_RUN del
        escáner»."""
        tarjeta = self._tarjeta(self.almacenes)
        self.assertEqual(tarjeta["estado"], "SIN_HACER")
        self.assertIn(MOTIVO_DE_LA_CORRIDA, tarjeta["motivo"])
        self.assertNotIn(TEXTO_DEL_ESCANER, tarjeta["motivo"])

    def test_y_la_tarjeta_NO_dice_lo_mismo_dos_veces(self):
        tarjeta = self._tarjeta(self.almacenes)
        self.assertEqual(tarjeta["resultado"], "")
        # `avance` es «cuanto falta por consultar», y aqui no falta nadie por consultar:
        # se consulto a los once y la corrida no da veredicto. Ponerlo en ambar debajo
        # del motivo seria el «pendiente» debajo del «cerrado» de la errata nº 108.
        self.assertEqual(tarjeta["avance"], "")
        self.assertTrue(tarjeta["motivo"].strip())


if __name__ == "__main__":
    unittest.main()
