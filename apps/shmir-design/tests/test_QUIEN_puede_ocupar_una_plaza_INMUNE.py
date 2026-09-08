"""Si se retira un inmune, ¿quién puede ocupar su plaza? Y qué pasa si no puede nadie.

Regla 5: escritos antes.

**De dónde sale.** Del 2026-09-07: se retira del panel el candidato `3utr:10` por el
frente de EMPALME —introduce crípticos que sus hermanas no tienen— y es uno de los CUATRO
inmunes al APA, así que la plaza no la puede ocupar «el siguiente de la lista»: tiene que
ocuparla otro inmune, o la cuota baja.

**Y la respuesta puede ser NINGUNO, que es un resultado y no un fallo.** Los sitios
elegibles por delante del corte se apelotonan en los primeros 200 nt del 3'UTR, así que
con `3utr:60`, `143` y `200` puestos no queda ninguno a 50 nt de todos ellos. Eso ya
estaba registrado como hecho geométrico —«caben CUATRO inmunes, no cinco»— y aquí se
emite en vez de deducirse.

**El control adversario es obligatorio**: sin él, «no hay ninguno» y «esta función nunca
devuelve nada» dan la misma lista vacía. Con un panel más pequeño SÍ salen candidatos.
"""

import unittest

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import (
    REFERENCES, fixture_available, load_reference,
)
from shmir_design.selection import SelectionConfig, derive_immune_cut, select_from_report
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElCasoReal(unittest.TestCase):
    """Retirar `3utr:10` del panel de once, con el 3'UTR murino de verdad."""

    @classmethod
    def setUpClass(cls):
        secuencia = load_reference(RATON)
        cls.anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=cls.anatomia
        )
        # `tx:959` es `3utr:10`: el nombre de la construcción lo dice desde el
        # arreglo del marco, y las dos formas del número conviven en este proyecto.
        cls.retirado = 959
        cls.plan = presentation.immune_replacements(
            cls.corrida.tiling, cls.corrida.selection, retire=cls.retirado,
        )

    def test_el_corte_y_el_espaciado_se_DERIVAN(self):
        corte = derive_immune_cut(self.corrida.tiling)
        self.assertEqual(self.plan["corte"], corte)
        self.assertEqual(
            self.plan["espaciado"], self.corrida.selection.selection.config.min_spacing
        )

    def test_el_retirado_sale_del_panel_y_los_demas_se_quedan(self):
        # Ya no está: la retirada está APLICADA desde el 2026-09-07, así que el panel de
        # esta corrida son los once que quedan y `tx:959` no es uno de ellos. La plaza
        # existe igual —la dejó él— y ese es el segundo camino que `immune_replacements`
        # acepta: la vacante es real, sólo que ya cobrada.
        self.assertNotIn(self.retirado, self.plan["panel"])
        self.assertEqual(len(self.plan["panel"]), 11)
        self.assertIn(
            self.retirado, self.corrida.selection.selection.config.retired_starts
        )

    def test_NO_HAY_NINGUNO_y_se_dice_POR_QUE(self):
        """La respuesta es un hecho geométrico del 3'UTR, no un fallo del código."""
        self.assertEqual(self.plan["disponibles"], [])
        self.assertIn("espaciado", self.plan["texto"])
        # Y dice cuántos inmunes hay, o «ninguno disponible» no se puede interpretar:
        # cero de cero y cero de dieciséis no son la misma noticia.
        self.assertEqual(self.plan["inmunes"], 16)
        self.assertIn("16", self.plan["texto"])

    def test_y_dice_CUANTOS_inmunes_QUEDAN_en_el_panel(self):
        """Lo que se perdió fue el cuarto inmune, y eso hay que verlo al decidir.

        La cuota se PIDE a la configuración de la corrida en vez de escribirse: bajó de
        cuatro a tres el mismo día, y un número transcrito aquí habría seguido diciendo
        cuatro sobre un panel que pide tres.
        """
        self.assertEqual(len(self.plan["inmunes_en_el_panel"]), 3)
        cuota = self.corrida.selection.selection.config.apa_immune_quota
        self.assertEqual(self.plan["cuota"], cuota)
        self.assertIn(f"3 inmunes frente a la cuota de {cuota}", self.plan["texto"])

    def test_las_posiciones_LLEVAN_SU_MARCO(self):
        for fila in self.plan["descartados"]:
            self.assertIn("tx:", fila["tx"])
            self.assertIn("3utr:", fila["utr3"])

    def test_los_descartados_salen_ORDENADOS_por_asimetria(self):
        valores = [f["asimetria"] for f in self.plan["descartados"]]
        self.assertEqual(valores, sorted(valores, reverse=True))


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElControlAdversario(unittest.TestCase):
    """Sin esto, «ninguno» y «esta función no encuentra nada» son lo mismo."""

    def test_con_un_panel_PEQUEÑO_si_hay_candidatos(self):
        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        informe = tile_utr(secuencia, anatomy=anatomia)
        seleccion = select_from_report(informe, SelectionConfig(n_candidates=2))
        plan = presentation.immune_replacements(
            informe, seleccion, retire=seleccion.selection.chosen[0].start,
        )
        self.assertTrue(plan["disponibles"], plan["texto"])

    def test_retirar_algo_que_NO_esta_en_el_panel_ABORTA(self):
        """Un plan para una plaza que nadie ha dejado no significa nada."""
        from shmir_design.errors import ShmirDesignError

        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia
        )
        with self.assertRaises(ShmirDesignError):
            presentation.immune_replacements(
                corrida.tiling, corrida.selection, retire=1,
            )


if __name__ == "__main__":
    unittest.main()
