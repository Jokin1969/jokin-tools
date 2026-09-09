"""Un off-target se cuenta CONTRA UN CATÁLOGO, y el catálogo va declarado.

Regla 5: escrito antes.

Segunda mitad de la decisión del 2026-09-08. La primera —`species.off_target_catalogues`—
dice CONTRA QUÉ hay que barrer; ésta hace que el resultado sepa **contra cuál se barrió**.

**Sin esto, las dos corridas son indistinguibles en el almacén.** La clave de consulta es
`query_name(species, start, hebra)` y no lleva catálogo, así que una corrida contra el
transcriptoma humano y otra contra el murino se pisan: la última gana y el veredicto sale
con la forma correcta refiriéndose a un catálogo que nadie eligió.

**Y no se funden nunca** (`species.WHY_TWO_CATALOGUES`): los conteos no son sumables —un
gen conservado aparece en los dos—, y el percentil se calcula contra una nula del MISMO
catálogo, así que agrupado no se refiere a nada.

**Una corrida de antes no declara catálogo**, y eso NO es «es del de la diana»: es que no
se sabe. Se dice, y no contesta a ninguna de las dos preguntas — inventar cuál era es
exactamente lo que este eje viene a impedir.
"""

import unittest

from shmir_design import species
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.offtarget_store import OfftargetStore, verdict_without_catalogue

from tests import corrida_offtarget as CORRIDA


class TestLaCorridaDECLARAsuCatalogo(unittest.TestCase):

    def test_run_scan_EXIGE_el_fondo_declarado(self):
        # Sin valor por defecto (principio nº 58): el que saldria decide contra que
        # catalogo se entiende contado el resultado.
        import inspect

        from shmir_design import offtarget

        firma = inspect.signature(offtarget.run_scan)
        self.assertIn("background", firma.parameters)
        self.assertIs(
            firma.parameters["background"].default, inspect.Parameter.empty,
            "`background` con defecto es una corrida que no dice contra que se contó",
        )

    def test_el_scan_lo_LLEVA(self):
        from shmir_design.offtarget import OfftargetScan

        self.assertIn("background", OfftargetScan.__dataclass_fields__)


@unittest.skipUnless(CORRIDA.HAY, "NOT_RUN: faltan los fixtures del raton y mature.fa")
class TestElAlmacenCONTESTAporCATALOGO(unittest.TestCase):
    """Sobre una corrida de VERDAD (`tests/corrida_offtarget.py`), no sobre un doble.

    El almacen se consulta por `query_name`, que NO lleva catalogo: con un doble que
    conteste que si a todo, este eje daria verde sin haber pasado por la clave real.
    """

    @classmethod
    def setUpClass(cls):
        cls.consulta = CORRIDA.consultas()[0]

    def test_verdict_for_EXIGE_el_catalogo(self):
        import inspect

        firma = inspect.signature(OfftargetStore.verdict_for)
        self.assertIn("background", firma.parameters)
        self.assertIs(
            firma.parameters["background"].default, inspect.Parameter.empty,
            "un veredicto con catalogo por defecto contesta por uno que nadie eligio",
        )

    def test_una_corrida_de_OTRO_catalogo_no_contesta_por_este(self):
        # Es el fallo que el eje cierra: sin el, la ultima corrida gana y el veredicto
        # sale refiriendose a un catalogo que nadie eligio.
        almacen = CORRIDA.almacen(background="human")
        self.assertIs(
            almacen.verdict_for(
                self.consulta, species="raton", background="human",
            ).state,
            FilterState.PASS,
        )
        self.assertIs(
            almacen.verdict_for(
                self.consulta, species="raton", background="mouse",
            ).state,
            FilterState.NOT_RUN,
        )

    def test_y_el_motivo_NOMBRA_el_catalogo_que_falta(self):
        almacen = CORRIDA.almacen(background="human")
        motivo = almacen.verdict_for(
            self.consulta, species="raton", background="mouse",
        ).reason
        self.assertIn("mouse", motivo)

    def test_una_corrida_SIN_catalogo_declarado_no_contesta_a_ninguno(self):
        # No haberlo declarado no es «es el de la diana». Se dice.
        almacen = CORRIDA.almacen(background="")
        for fondo in ("human", "mouse"):
            with self.subTest(fondo):
                veredicto = almacen.verdict_for(
                    self.consulta, species="raton", background=fondo,
                )
                self.assertIs(veredicto.state, FilterState.NOT_RUN)
                self.assertIn("NO DECLARAN", veredicto.reason)

    def test_y_el_veredicto_SIGUE_sin_poder_dar_FAIL(self):
        # El eje NO convierte este frente en un filtro: sigue siendo DESEMPATE. Un eje
        # que se leyera como un filtro nuevo seria el `especificidad: PASS` que da por
        # cubierto lo que no se miro.
        almacen = CORRIDA.almacen(background="mouse")
        for fondo in ("mouse", "human"):
            with self.subTest(fondo):
                estado = almacen.verdict_for(
                    self.consulta, species="raton", background=fondo,
                ).state
                self.assertIsNot(estado, FilterState.FAIL)


class TestSinCATALOGOqueNOMBRARnoSePREGUNTA(unittest.TestCase):
    """Una especie sin declarar no tiene eje, y eso no puede tumbar la ficha.

    `verdict_for` aborta sin catalogo, y hace bien. Lo que no puede pasar es que ese
    aborto se lleve por delante la tabla o la ficha: la respuesta honesta es un
    `NOT_RUN` que dice que el hueco esta en la DECLARACION de la especie, no en un
    fichero que conseguir.
    """

    def test_una_especie_sin_declarar_NO_tiene_catalogos(self):
        self.assertEqual(species.off_target_catalogue_slugs("Oryctolagus cuniculus"), ())
        self.assertEqual(species.off_target_catalogue_slugs(""), ())

    def test_y_las_declaradas_SI(self):
        # Control adversario: sin el, «no hay eje» y «esta funcion no mira nada» dan lo
        # mismo.
        self.assertEqual(species.off_target_catalogue_slugs("raton"), ("mouse",))
        self.assertEqual(
            species.off_target_catalogue_slugs("human"), ("human", "mouse"),
        )

    def test_pedir_un_veredicto_SIN_catalogo_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            OfftargetStore().verdict_for("q", species="human", background="")

    def test_pero_hay_un_NOT_RUN_que_lo_dice_en_vez_de_abortar(self):
        veredicto = verdict_without_catalogue("Oryctolagus cuniculus")
        self.assertIs(veredicto.state, FilterState.NOT_RUN)
        self.assertIn("model_backgrounds", veredicto.reason)
        self.assertIn("no es que falte un fichero", veredicto.reason.lower())


@unittest.skipUnless(CORRIDA.HAY, "NOT_RUN: faltan los fixtures del raton y mature.fa")
class TestElCATALOGOsobreviveALLOG(unittest.TestCase):
    """Guardar y releer una corrida no puede perder CONTRA QUÉ se contó.

    Es la lección de la errata nº 138 aplicada al eje nuevo: el marco se perdía al
    escribir el log y el defecto lo reponía en `3utr`, así que el arreglo vivía sólo
    mientras el objeto estuviera en memoria. Aquí el defecto sería peor —repondría el
    catálogo de la DIANA— así que lo que vuelve es `""`, que no contesta por ninguno.
    """

    def _ida_y_vuelta(self, background: str):
        import tempfile
        from pathlib import Path

        from shmir_design import presentation

        from shmir_design.coords import Frame
        from shmir_design.reference import load_3utr

        utr3 = load_3utr(CORRIDA.RATON)
        _, scan = CORRIDA.corrida(background=background)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # LO SUBIDO YA ES EL 3'UTR: la corrida del ayudante tila el 3'UTR pelado,
            # asi que la anatomia del proyecto tiene que ser esa o `project_open`
            # rechazaria la secuencia por md5.
            anatomia = Anatomy.whole_is_utr3(
                length=len(utr3), source=RegionSource.FIXTURE_VERIFICADO
            )
            payload, fuente = presentation.anatomy_payload(anatomia)
            almacen = presentation.project_create(
                base, slug="eje_de_catalogo", date="2026-09-09",
                sequence=utr3, species="raton",
                anatomy=payload, anatomy_source=fuente,
            )
            presentation.save_offtarget_run(
                almacen,
                presentation.offtarget_run_from_scan(
                    scan, date="2026-09-09", ran_by="la suite"
                ),
            )
            reabierto = presentation.project_open(base, slug="eje_de_catalogo")
            almacenes = presentation.load_stores(reabierto)
        corridas = almacenes["offtarget"].runs
        self.assertEqual(len(corridas), 1)
        return corridas[0].scan.background

    def test_el_catalogo_declarado_VUELVE_del_log(self):
        self.assertEqual(self._ida_y_vuelta("mouse"), "mouse")

    def test_y_una_corrida_SIN_catalogo_vuelve_VACIA_no_con_el_de_la_diana(self):
        # El defecto que saldría es el peor de los dos: repondría el catálogo de la
        # diana sobre una corrida que no dijo contra cuál contó.
        self.assertEqual(self._ida_y_vuelta(""), "")


class TestLasDOSCifrasNOseSUMAN(unittest.TestCase):

    def test_esta_escrito_POR_QUE_son_dos(self):
        texto = species.WHY_TWO_CATALOGUES
        for clave in ("no describe", "SUMABLES", "nula"):
            with self.subTest(clave):
                self.assertIn(clave.lower(), texto.lower())

    def test_no_hay_ninguna_funcion_que_los_SUME(self):
        # El guardia de `Counts` un piso mas abajo, aplicado al eje de arriba: si
        # existiera un total, alguien acabaria imprimiendolo.
        from shmir_design import offtarget

        for nombre in dir(offtarget):
            with self.subTest(nombre):
                self.assertNotIn("total_catalog", nombre.lower())


if __name__ == "__main__":
    unittest.main()
