"""Un frente cuya respuesta es del TRANSCRITO llega a la celda de cada candidato.

**EL CASO (2026-09-07).** `fraccion_isoforma_larga` sale `NOT_RUN` en los once del panel
—en la pantalla y en el export, los dos igual— mientras su tarjeta dice «CERRADO. 8 de 11
candidatos quedan por detrás del corte». El frente está cerrado desde que
`polya_db_mouse.tsv` está en el depósito.

**Por qué caía.** `front_columns` deriva una columna por frente, y quien la resuelve es
`_filter_columns` —los filtros de la VENTANA— o `STORE_FOR_FRONT` —los almacenes—. Este
frente no tiene ninguna de las dos cosas, y no por descuido: la tabla de APA medido se
aplica **por md5 del 3'UTR**, así que la pregunta «¿está medida la fracción de isoforma
larga?» es del TRANSCRITO y se contesta una vez para todos. Sin resolutor, la celda caía
al `NOT_RUN` por defecto.

Es la errata nº 68 en su tercera forma. Las dos primeras eran ejes POR CANDIDATO que se
resolvían mal —el fichero contra el panel, y el eje guía/pasajera—; ésta es un eje que
**no es por candidato** y al que se le pedía una respuesta por candidato.

**Y NO era «la pantalla y el export sin el mismo estado»**: los dos decían lo mismo. Lo
que discrepaba era el FRENTE con SU PROPIA COLUMNA, que es peor de leer — dos cifras del
mismo suceso, una al lado de la otra y las dos con pinta de medida (errata nº 51).

Regla 5: escrito con el fallo delante.
"""

import unittest

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.selection import blocking_fronts

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)
ESPECIE = "Mus musculus"


def _anatomia(secuencia):
    return Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO,
    )


def _corrida():
    """La corrida normal. La tabla de APA medido entra SOLA, y eso importa.

    `tile_utr` la resuelve por su cuenta y la aplica **por md5 del 3'UTR**, así que no
    depende de que haya recursos cargados: quitarlos no la quita. Medido al escribir el
    control adversario de abajo, que con `resources=None` seguía dando el frente cerrado.
    """
    secuencia = load_reference(RATON)
    return presentation.page_run(
        species=ESPECIE, sequence=secuencia, anatomy=_anatomia(secuencia),
    )


def _corrida_sin_la_tabla():
    """La MISMA corrida con la tabla EXCLUIDA a propósito, que es la palanca declarada.

    `measured_apa=None` aborta —era el salto silencioso—, así que la única forma de dejar
    el frente abierto es `apa.ApaExcluded` con su motivo. Es también la forma que tendrá
    cualquier especie sin tabla, que es el caso que este control representa.
    """
    from shmir_design.apa import ApaExcluded
    from shmir_design.selection import default_config, select_from_report
    from shmir_design.tiling import tile_utr

    secuencia = load_reference(RATON)
    anatomia = _anatomia(secuencia)
    informe = tile_utr(
        secuencia, anatomy=anatomia, species=ESPECIE,
        measured_apa=ApaExcluded(reason="control adversario: sin tabla medida"),
    )
    return informe, select_from_report(informe, default_config())


class TestLaListaEstaDeclarada(unittest.TestCase):

    def test_existe_y_no_esta_vacia(self):
        self.assertTrue(presentation.ESTADO_GLOBAL_NO_POR_CANDIDATO)

    def test_ninguno_tiene_ALMACEN_ni_pretende_tenerlo(self):
        """Si tuviera almacén, la respuesta sería por candidato y no global."""
        for frente in presentation.ESTADO_GLOBAL_NO_POR_CANDIDATO:
            with self.subTest(frente):
                self.assertNotIn(frente, presentation.STORE_FOR_FRONT)

    def test_y_NO_se_solapa_con_la_otra_lista(self):
        """`NO_CABE_COLUMNA_POR_CANDIDATO` dice otra cosa: que la unidad es un PAR.

        Las dos listas hablan de la forma de la respuesta y dicen cosas distintas; un
        frente en las dos sería una contradicción declarada (principio nº 53).
        """
        self.assertFalse(
            set(presentation.ESTADO_GLOBAL_NO_POR_CANDIDATO)
            & set(presentation.NO_CABE_COLUMNA_POR_CANDIDATO)
        )


@unittest.skipUnless(HAY, "falta el fixture del ratón")
class TestElFrenteYSuColumnaDicenLoMISMO(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()

    def _frente(self, nombre):
        for f in blocking_fronts(self.corrida.tiling, self.corrida.selection):
            if f.name == nombre:
                return f
        self.fail(f"no existe el frente {nombre}")

    def test_con_la_tabla_medida_el_frente_esta_CERRADO(self):
        """El control de la premisa: sin esto, lo de abajo no prueba nada."""
        self.assertFalse(self._frente("fraccion_isoforma_larga").blocking)

    def test_y_la_celda_de_los_ONCE_no_dice_NOT_RUN(self):
        filas = presentation.site_table_rows(
            self.corrida.tiling, self.corrida.selection, species=ESPECIE,
        )
        panel = [f for f in filas if f.get("elegido")]
        self.assertTrue(panel, "no se han encontrado los del panel")
        for fila in panel:
            with self.subTest(fila["inicio"]):
                self.assertNotEqual(fila["fraccion_isoforma_larga"], "NOT_RUN")

    def test_el_EXPORT_dice_lo_mismo_que_la_pantalla(self):
        from shmir_design import outputs

        crudo = presentation.tsv_rows(outputs.tsv_selected(
            self.corrida.selection, species=ESPECIE, tiling=self.corrida.tiling,
        ))
        cabecera = crudo[0]
        i = cabecera.index("fraccion_isoforma_larga")
        for fila in crudo[1:]:
            with self.subTest(fila[cabecera.index("inicio")]):
                self.assertNotEqual(fila[i], "NOT_RUN")


@unittest.skipUnless(HAY, "falta el fixture del ratón")
class TestControlAdversario(unittest.TestCase):
    """SIN la tabla medida el frente bloquea, y entonces la celda SÍ dice `NOT_RUN`.

    Sin esto, «no dice NOT_RUN» y «la columna no mira nada» dan el mismo verde: bastaría
    con escribir `PASS` a secas para pasar los tests de arriba.
    """

    @classmethod
    def setUpClass(cls):
        cls.informe, cls.seleccion = _corrida_sin_la_tabla()

    def test_sin_la_tabla_el_frente_BLOQUEA(self):
        frente = next(
            f for f in blocking_fronts(self.informe, self.seleccion)
            if f.name == "fraccion_isoforma_larga"
        )
        self.assertTrue(frente.blocking)

    def test_y_entonces_la_celda_SI_dice_NOT_RUN(self):
        filas = presentation.site_table_rows(
            self.informe, self.seleccion, species=ESPECIE,
        )
        panel = [f for f in filas if f.get("elegido")]
        self.assertTrue(panel)
        for fila in panel:
            with self.subTest(fila["inicio"]):
                self.assertEqual(fila["fraccion_isoforma_larga"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
