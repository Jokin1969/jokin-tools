"""La primera línea de un TSV que se descarga es su CABECERA DE COLUMNAS.

**EL CASO (2026-09-07).** El sello `# BUILD:` se puso arriba del todo el mismo día, con
este motivo: «es lo primero que hace falta cuando el fichero no cuadra con lo que se
esperaba». El motivo sigue siendo cierto y el sitio era el equivocado: **Excel toma la
primera línea como fila de títulos**, así que la cabecera real baja una fila y todas las
columnas se leen corridas. Reportado contando columnas sobre un fichero desplazado — dos
rondas persiguiendo un `FAIL` en una columna que no era la que se estaba mirando.

**El sello no se quita: se mueve al final.** `presentation.tsv_header` y `tsv_rows` saltan
los comentarios **estén donde estén**, así que para nuestros lectores no cambia nada; para
Excel, la cabecera vuelve a la fila 1. Lo que se pierde es «arriba del todo», y a cambio el
fichero se abre bien en la herramienta con la que se lee de verdad.

**Y se aplica también al bloque de prosa de la comparativa**, por el mismo motivo y sin
excepción: media medida habría dejado ese fichero con el mismo defecto. La prosa sigue
entera y en el mismo orden, sólo que detrás de los datos.

Regla 5: escrito con el fallo delante.
"""

import unittest

from shmir_design import outputs, presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.identidad import BUILD_PREFIX
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.scaffold import SGEP_SCAFFOLD

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)
ESPECIE = "Mus musculus"


def _corrida():
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO,
    )
    return presentation.page_run(
        species=ESPECIE, sequence=secuencia, anatomy=anatomia,
    ), anatomia


@unittest.skipUnless(HAY, "falta el fixture del ratón")
class TestTodoTSVdelPaquete(unittest.TestCase):
    """DERIVADO del paquete, no de una lista: un TSV nuevo queda cubierto solo."""

    @classmethod
    def setUpClass(cls):
        cls.corrida, cls.anatomia = _corrida()
        cls.paquete = presentation.output_bundle(
            species=ESPECIE, tiling=cls.corrida.tiling,
            selection=cls.corrida.selection, scaffold=SGEP_SCAFFOLD,
        )

    def _tsv(self):
        return {n: t for n, t in self.paquete.items() if n.endswith(".tsv")}

    def test_el_detector_ha_encontrado_TSV(self):
        """Principio nº 51: «ninguno falla» y «no he mirado» dan el mismo verde."""
        self.assertGreaterEqual(len(self._tsv()), 3)

    def test_ninguno_empieza_por_un_comentario(self):
        for nombre, texto in self._tsv().items():
            with self.subTest(nombre):
                primera = texto.splitlines()[0]
                self.assertFalse(
                    primera.startswith(presentation.TSV_COMMENT),
                    f"{nombre} empieza por un comentario: Excel se comerá la cabecera",
                )

    def test_y_su_primera_linea_ES_la_cabecera_de_columnas(self):
        """No basta con que no empiece por `#`: tiene que ser la cabecera."""
        for nombre, texto in self._tsv().items():
            with self.subTest(nombre):
                self.assertEqual(
                    texto.splitlines()[0].split("\t"),
                    presentation.tsv_header(texto),
                )


@unittest.skipUnless(HAY, "falta el fixture del ratón")
class TestElSelloSIGUEestando(unittest.TestCase):
    """Mover no es quitar. Sin esto, «no empieza por comentario» se cumple borrándolo."""

    @classmethod
    def setUpClass(cls):
        cls.corrida, cls.anatomia = _corrida()

    def _seleccionados(self):
        return outputs.tsv_selected(
            self.corrida.selection, species=ESPECIE, tiling=self.corrida.tiling,
        )

    def _comparativa(self):
        from shmir_design.comparative import comparative_tsv

        return comparative_tsv(
            self.corrida.selection, SGEP_SCAFFOLD, with_header=True,
            anatomy=self.anatomia,
        )

    def test_el_export_lo_lleva_AL_FINAL(self):
        lineas = [l for l in self._seleccionados().splitlines() if l.strip()]
        self.assertTrue(lineas[-1].startswith(BUILD_PREFIX), lineas[-1])

    def test_la_comparativa_tambien(self):
        lineas = [l for l in self._comparativa().splitlines() if l.strip()]
        self.assertTrue(lineas[-1].startswith(BUILD_PREFIX), lineas[-1])

    def test_y_la_PROSA_de_la_comparativa_no_se_ha_perdido(self):
        """Se mueve entera; no se recorta. La columna vacía se sigue explicando."""
        comentarios = "\n".join(
            l for l in self._comparativa().splitlines()
            if l.startswith(presentation.TSV_COMMENT)
        )
        self.assertIn("knockdown_medido", comentarios)
        self.assertIn("score_externo", comentarios.lower())


@unittest.skipUnless(HAY, "falta el fixture del ratón")
class TestLosLectoresNOcambian(unittest.TestCase):
    """El contrato de `tsv_header` / `tsv_rows` es el mismo con el sello donde sea."""

    @classmethod
    def setUpClass(cls):
        cls.corrida, cls.anatomia = _corrida()
        cls.texto = outputs.tsv_selected(
            cls.corrida.selection, species=ESPECIE, tiling=cls.corrida.tiling,
        )

    def test_tsv_header_da_las_columnas(self):
        self.assertEqual(presentation.tsv_header(self.texto)[0], "especie")

    def test_tsv_rows_no_cuenta_el_sello_como_una_fila(self):
        filas = presentation.tsv_rows(self.texto)
        anchos = {len(f) for f in filas}
        self.assertEqual(len(anchos), 1, f"filas de anchos distintos: {anchos}")
        self.assertEqual(len(filas) - 1, len(self.corrida.selection.selection.chosen))


if __name__ == "__main__":
    unittest.main()
