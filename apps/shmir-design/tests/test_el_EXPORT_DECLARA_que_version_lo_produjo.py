"""El fichero que viaja dice QUÉ VERSIÓN lo produjo, y no hay que preguntárselo a nadie.

**Reportado el 2026-09-07**: *«`empalme_sitios` y `offtarget_seed` siguen sin columna en
el export de candidatos. Era lo que dijiste haber arreglado. Comprueba si está desplegado
o si el export que descargo es otro»*.

Y ésa es la pregunta que el fichero tenía que poder contestar solo. El sello existe desde
el 2026-09-05 —`identidad.build_stamp()`, que el hub pasa por `SHMIR_BUILD`— y **su único
consumidor era la cabecera del FASTA de empalme**: los dos TSV que se descargan, se mandan
por correo y se leen dentro de un año salían sin él. Es el principio nº 35 —*un nombre se
pierde en el primer `mv`*— sobre el dato que distingue «el arreglo no está» de «el
despliegue va por detrás», que son dos cosas y se arreglan con cosas distintas.

**Y las columnas se comprueban aquí también**, sobre el panel del TRANSCRITO: sin eso, un
export que las tenga y otro que no darían el mismo verde, y la pregunta volvería.

Regla 5: escrito antes.
"""

import unittest

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.identidad import BUILD_NOT_DECLARED, build_stamp
from shmir_design.outputs import tsv_selected
from shmir_design.comparative import comparative_tsv
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.scaffold import SGEP_SCAFFOLD

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

#: El prefijo con el que el sello viaja en un fichero de texto. Se declara aquí y en
#: `outputs`/`comparative` sale de la misma constante: escrito dos veces, un cambio de
#: formato dejaría el test pasando sobre un fichero que ya no lo lleva.
from shmir_design.identidad import BUILD_PREFIX  # noqa: E402


def _corrida():
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )
    return presentation.page_run(
        species="raton", sequence=secuencia, anatomy=anatomia
    )


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElSelloViajaEnLosDosTSV(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.seleccionados = tsv_selected(
            cls.corrida.selection, species="raton", tiling=cls.corrida.tiling,
        )
        cls.comparativa = comparative_tsv(
            cls.corrida.selection, SGEP_SCAFFOLD, with_header=True,
            anatomy=cls.corrida.tiling.anatomy,
        )

    def test_el_export_de_candidatos_lo_lleva(self):
        self.assertTrue(
            self.seleccionados.startswith(BUILD_PREFIX), self.seleccionados[:80]
        )

    def test_la_comparativa_tambien(self):
        self.assertIn(BUILD_PREFIX, self.comparativa.splitlines()[0])

    def test_y_dice_LO_QUE_EL_ENTORNO_DECLARA_o_que_no_lo_declara(self):
        # Sin `SHMIR_BUILD` el sello dice «sin declarar», que es información; inventarse
        # un commit sería peor que no ponerlo (principio nº 32).
        primera = self.seleccionados.splitlines()[0]
        self.assertIn(build_stamp(), primera)
        if build_stamp() == BUILD_NOT_DECLARED:
            self.assertIn(BUILD_NOT_DECLARED, primera)

    def test_la_cabecera_de_columnas_sigue_siendo_LEGIBLE(self):
        # El sello es un comentario `#`, así que quien lea el fichero salta esas líneas
        # y la primera de datos sigue siendo la cabecera de columnas.
        cabecera = presentation.tsv_header(self.seleccionados)
        self.assertEqual(cabecera[0], "especie")


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestYlasCOLUMNASdeLosDosFrentesEstan(unittest.TestCase):
    """Lo reportado: `empalme_sitios` y `offtarget_seed` no aparecían en el export."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.cabecera = presentation.tsv_header(
            tsv_selected(
                cls.corrida.selection, species="raton", tiling=cls.corrida.tiling,
            )
        )

    def test_empalme_sitios_tiene_columna(self):
        self.assertIn("empalme_sitios", self.cabecera)

    def test_y_offtarget_seed_tambien_POR_HEBRA(self):
        self.assertIn("offtarget_seed:guia", self.cabecera)
        self.assertIn("offtarget_seed:pasajera", self.cabecera)

    def test_y_no_se_quedan_en_los_filtros_de_la_VENTANA(self):
        # El control adversario del reporte: lo que se veía terminaba en los filtros de
        # ventana y saltaba a `bandera_polyA_debil`.
        ventana = self.corrida.selection.window_of(
            self.corrida.selection.selection.chosen[0]
        )
        de_ventana = set(presentation._filter_names(ventana))
        self.assertTrue(set(self.cabecera) - de_ventana >= {"empalme_sitios"})


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLaComparativaDESCARGADArecibeLosAlmacenes(unittest.TestCase):
    """`output_bundle` la montaba sin `stores` ni `species`.

    Así que las cuatro `carga_<clase>` salían vacías para TODOS los candidatos aunque el
    proyecto tuviera corrida — el mismo patrón por octava vez, y sobre el fichero que se
    descarga. Se comprueba sobre la LLAMADA porque es un argumento que falta, no una
    función que no exista (errata nº 51).
    """

    def test_output_bundle_se_los_pasa(self):
        import inspect

        fuente = inspect.getsource(presentation.output_bundle)
        llamada = fuente[fuente.index("comparative_tsv("):]
        llamada = llamada[: llamada.index("),")]
        self.assertIn("stores=", llamada)
        self.assertIn("species=", llamada)


if __name__ == "__main__":
    unittest.main()
