"""La promoción por medida ENTRA SIEMPRE que haya medida. No es una bandera.

Regla 5: escrito antes.

Decisión del responsable (2026-08-27), y el motivo es que **son dos veredictos, no dos
ordenaciones**:

  · sin la medida, `3utr:221` lleva una PENALIZACIÓN de −1,00 por solapar un hexámero
    variante — sigue en el panel, sólo que peor colocada;
  · con la medida, el `AATATA` de `3utr:236` es `APA_POSIBLE` y `3utr:221` es **FAIL
    duro** por solape estérico.

Y el dato existe: PSE 21,1 %, AvgRPM 0,55 — el proximal MÁS usado de los tres. Sin
aplicarlo, la app trata ese hexámero como no funcional, que es la hipótesis **menos
conservadora** y además la falsa según lo medido: el defecto favorecía al candidato
equivocado por omisión.

Mismo criterio que el `.out` de RepeatMasker y que la casilla global que se quitó: si el
dato está y es válido, se usa. Que un veredicto dependa de acordarse de una bandera es
justo la trampa que este proyecto ya cerró una vez.

Excluirlo sigue siendo posible —hay que poder trabajar— pero con MOTIVO ESCRITO, igual
que `deposito.Ignored`, y el motivo viaja al veredicto: sin él, «se decidió no usarlo» y
«nadie se acordó» serían el mismo resultado mudo.
"""

import unittest

from shmir_design.apa import ApaExcluded
from shmir_design.errors import ShmirDesignError
from shmir_design.polya import SignalClass
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

#: El hexamero que la medida promueve, y el candidato que cae por su solape esterico.
HEXAMERO_MEDIDO = 236
CAE_POR_ESTERICO = 221


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del ratón")
class TestSeAplicaSinPedirlo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3 = load_3utr(RATON)

    def test_tile_utr_a_secas_YA_trae_la_medida(self):
        informe = tile_utr(self.utr3)
        self.assertIsNotNone(informe.measured_apa)

    def test_y_el_AATATA_de_236_sale_APA_POSIBLE(self):
        informe = tile_utr(self.utr3)
        señal = next(s for s in informe.signals if s.position == HEXAMERO_MEDIDO)
        self.assertEqual(señal.motif, "AATATA")
        self.assertIs(señal.classification, SignalClass.APA_POSSIBLE)

    def test_por_la_via_de_la_MEDIDA_no_por_canonicidad(self):
        informe = tile_utr(self.utr3)
        señal = next(s for s in informe.signals if s.position == HEXAMERO_MEDIDO)
        self.assertEqual(señal.evidence, "medida")


class TestExcluirlaEXIGEUnMotivo(unittest.TestCase):
    def test_pasar_None_ABORTA_en_vez_de_saltarsela_en_silencio(self):
        with self.assertRaises(ShmirDesignError) as caja:
            tile_utr("A" * 100, measured_apa=None)
        self.assertIn("ApaExcluded", str(caja.exception))

    def test_ApaExcluded_sin_motivo_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            ApaExcluded(reason="")

    def test_con_motivo_se_excluye_y_el_motivo_VIAJA(self):
        if not HAY:
            self.skipTest("NOT_RUN: falta el fixture del ratón")
        motivo = "prueba de regresión: se quiere el panel sin promoción"
        informe = tile_utr(load_3utr(RATON), measured_apa=ApaExcluded(reason=motivo))
        self.assertIsNone(informe.measured_apa)
        self.assertIn(motivo, informe.apa_excluded_reason)

    def test_y_sin_exclusion_ese_campo_esta_vacio(self):
        if not HAY:
            self.skipTest("NOT_RUN: falta el fixture del ratón")
        self.assertEqual(tile_utr(load_3utr(RATON)).apa_excluded_reason, "")


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del ratón")
class TestSonDosVEREDICTOSNoDosOrdenaciones(unittest.TestCase):
    """La diferencia que motiva la decisión, medida sobre el candidato concreto."""

    @classmethod
    def setUpClass(cls):
        utr3 = load_3utr(RATON)
        cls.con = tile_utr(utr3)
        cls.sin = tile_utr(
            utr3, measured_apa=ApaExcluded(reason="control de esta comparación")
        )

    def _elegible(self, informe, inicio):
        from shmir_design.selection import is_eligible

        ventana = next(v for v in informe.windows if v.window.start == inicio)
        return is_eligible(ventana)

    def test_SIN_la_medida_221_sigue_siendo_elegible(self):
        self.assertTrue(self._elegible(self.sin, CAE_POR_ESTERICO))

    def test_CON_la_medida_221_NO_lo_es(self):
        self.assertFalse(self._elegible(self.con, CAE_POR_ESTERICO))

    def test_y_la_piscina_se_encoge_en_lo_que_cuesta_la_promocion(self):
        from shmir_design.selection import is_eligible

        self.assertLess(
            sum(1 for v in self.con.windows if is_eligible(v)),
            sum(1 for v in self.sin.windows if is_eligible(v)),
        )


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del ratón")
class TestElPanelDeDIEZ(unittest.TestCase):
    """Lo que cierra la validación: los once, con los TRES inmunes que caben."""

    # ONCE desde el 2026-09-06: `3utr:1071` es el segundo distal, exigido por cuota.
    #
    # Y DESDE EL 2026-09-07 sin `3utr:10` y con `3utr:359`: el primero se retira POR EL
    # FRENTE DE EMPALME —es el único de los once que introduce crípticos que sus hermanas
    # no tienen— y su plaza NO la puede ocupar otro inmune, porque los 16 sitios inmunes
    # se apelotonan entre `3utr:10` y `3utr:200` y con `60`, `143` y `200` puestos ninguno
    # de los trece restantes cabe a 50 nt. La cuota baja a TRES por geometría, y la plaza
    # once se la lleva el mejor disponible.
    ESPERADO = [60, 143, 200, 359, 449, 553, 652, 735, 819, 1018, 1071]

    def test_el_panel_por_defecto_es_el_del_responsable(self):
        from shmir_design.selection import default_config, select_from_report

        informe = tile_utr(load_3utr(RATON))
        panel = sorted(
            c.start for c in select_from_report(informe, default_config()).selection.chosen
        )
        self.assertEqual(panel, self.ESPERADO)

    def test_y_los_TRES_inmunes_que_caben_estan(self):
        """TRES, no cuatro — y la diferencia es GEOMETRIA, no criterio.

        `3utr:10` era el cuarto y se retiró el 2026-09-07. Que no lo sustituya otro
        inmune no es una renuncia a la reserva: es que no cabe ninguno. Lo demuestra
        `tests/test_QUIEN_puede_ocupar_una_plaza_INMUNE.py`, que emite los dieciséis con
        el motivo de por qué cada uno choca.
        """
        from shmir_design.selection import (
            DEFAULT_IMMUNE_QUOTA, default_config, select_from_report,
        )

        informe = tile_utr(load_3utr(RATON))
        panel = sorted(
            c.start for c in select_from_report(informe, default_config()).selection.chosen
        )
        inmunes = [p for p in panel if p <= 251]
        self.assertEqual(inmunes, [60, 143, 200])
        # La cuota se CUMPLE: no es que falte uno, es que la cuota son tres.
        self.assertEqual(len(inmunes), DEFAULT_IMMUNE_QUOTA)


if __name__ == "__main__":
    unittest.main()
