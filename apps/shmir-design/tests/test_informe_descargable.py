"""El botón de Informe: un PDF con todo lo que la corrida ha producido. Regla 5.

**Una sola fuente, dos consumidores.** El PDF NO es un documento nuevo: es
`informe_doc.build_document()` —el mismo que emite el CLI— pasado por `pdf_writer`. Dos
documentos para lo mismo es exactamente la divergencia CLI/página que costó la errata
nº 32, y aquí sería peor: el que se descarga es el que va a una libreta de laboratorio.

Lo que faltaba en el documento y entra ahora, porque estaba en la página y no en el
informe: la **anatomía del transcrito** como tabla, el **mapa del 3'UTR** y **todos los
sitios elegibles con una columna por frente**. Los tres salen de las MISMAS funciones que
pinta la página —`anatomy_rows`, `map_svg`, `site_table_rows`—, no de una copia.
"""

import unittest

from shmir_design.informe_doc import build_document
from shmir_design.pdf_writer import to_pdf


def _corrida():
    from shmir_design.anatomy import Anatomy, RegionSource
    from shmir_design.reference import REFERENCES, load_reference
    from shmir_design.selection import default_config, select_from_report
    from shmir_design.tiling import tile_utr

    referencia = REFERENCES["NM_011170.3"]
    secuencia = load_reference(referencia)
    anatomia = Anatomy.from_cds(
        cds=referencia.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )
    inicio, fin = anatomia.utr3
    utr3 = secuencia[inicio - 1 : fin]
    informe = tile_utr(utr3)
    return informe, select_from_report(informe, default_config()), anatomia


class TestElDocumentoLLEVAloQuePINTAlaPAGINA(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tiling, seleccion, anatomia = _corrida()
        cls.doc = build_document(
            species="raton", tiling=tiling, selection=seleccion,
            generated="2026-08-30", anatomy=anatomia,
        )
        cls.titulos = [s.title for s in cls.doc.sections]

    def test_esta_la_ANATOMIA_del_transcrito(self):
        self.assertTrue(
            any("Anatom" in t for t in self.titulos), self.titulos
        )

    def test_esta_el_MAPA_del_3utr(self):
        self.assertTrue(any("Mapa" in t for t in self.titulos), self.titulos)

    def test_estan_los_CANDIDATOS_con_un_estado_por_filtro(self):
        self.assertTrue(any("candidatos" in t.lower() for t in self.titulos))

    def test_y_TODOS_los_sitios_elegibles_con_columna_por_frente(self):
        self.assertTrue(
            any("elegibles" in t.lower() for t in self.titulos), self.titulos
        )

    def test_y_sigue_estando_la_PROCEDENCIA_del_material(self):
        self.assertTrue(any("rocedencia" in t for t in self.titulos), self.titulos)


class TestLasTablasSALENdeLasMISMASfunciones(unittest.TestCase):
    """No son copias: si la página cambia una columna, el informe cambia con ella."""

    @classmethod
    def setUpClass(cls):
        cls.tiling, cls.seleccion, cls.anatomia = _corrida()
        cls.doc = build_document(
            species="raton", tiling=cls.tiling, selection=cls.seleccion,
            generated="2026-08-30", anatomy=cls.anatomia,
        )

    def _tabla(self, fragmento):
        for seccion in self.doc.sections:
            if fragmento.lower() in seccion.title.lower():
                for bloque in seccion.blocks:
                    if bloque.kind == "table":
                        return bloque
        raise AssertionError(f"sin tabla en la sección {fragmento!r}")

    def test_la_de_anatomia_tiene_las_columnas_de_anatomy_rows(self):
        from shmir_design.presentation import anatomy_rows

        filas = anatomy_rows(
            None, utr3_length=self.anatomia.utr3_length, anatomy=self.anatomia
        )
        self.assertEqual(list(self._tabla("Anatom").headers), list(filas[0]))

    def test_la_de_sitios_elegibles_tiene_UNA_COLUMNA_POR_FRENTE(self):
        from shmir_design.presentation import site_table_rows

        filas = site_table_rows(self.tiling, self.seleccion, species="raton")
        tabla = self._tabla("elegibles")
        self.assertEqual(list(tabla.headers), list(filas[0]))
        self.assertEqual(len(tabla.rows), len(filas))

    def test_y_la_de_candidatos_la_de_candidate_rows(self):
        from shmir_design.presentation import candidate_rows

        filas = candidate_rows(self.seleccion)
        self.assertEqual(list(self._tabla("candidatos").headers), list(filas[0]))


class TestElPDF(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tiling, seleccion, anatomia = _corrida()
        cls.doc = build_document(
            species="raton", tiling=tiling, selection=seleccion,
            generated="2026-08-30", anatomy=anatomia,
        )
        cls.pdf = to_pdf(cls.doc)

    def test_es_un_pdf_de_verdad(self):
        self.assertTrue(self.pdf.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", self.pdf[-32:])

    def test_y_no_sale_vacio(self):
        self.assertGreater(len(self.pdf), 20_000)


class TestNoHayDOSinformes(unittest.TestCase):
    """La descarga YA EXISTÍA. Lo que faltaba era su contenido y su sitio.

    Estuve a punto de añadir un segundo botón de PDF, que es exactamente la duplicación
    que este proyecto persigue: `informe_files` ya emitía markdown, `.docx` y PDF del
    MISMO documento. Lo que se hizo es (1) que ese documento lleve la anatomía, el mapa y
    los sitios elegibles, y (2) moverlo a debajo de «Frentes», que es donde se pide.
    """

    def test_informe_documento_ACEPTA_la_anatomia_y_la_pasa(self):
        from shmir_design.presentation import informe_documento

        tiling, seleccion, anatomia = _corrida()
        con = informe_documento(
            seleccion, tiling, species="raton", generated="2026-08-30",
            anatomy=anatomia,
        )
        sin = informe_documento(
            seleccion, tiling, species="raton", generated="2026-08-30",
        )
        titulos_con = [s.title for s in con.sections]
        titulos_sin = [s.title for s in sin.sections]
        self.assertIn("Anatomía del transcrito", titulos_con)
        self.assertNotIn("Anatomía del transcrito", titulos_sin)

    def test_y_los_TRES_entregables_salen_del_MISMO_documento(self):
        from shmir_design.presentation import informe_documento, informe_files

        tiling, seleccion, anatomia = _corrida()
        documento = informe_documento(
            seleccion, tiling, species="raton", generated="2026-08-30",
            anatomy=anatomia,
        )
        entregables = informe_files(documento, stem="raton")
        tipos = {e["mime"] for e in entregables}
        self.assertIn("application/pdf", tipos)
        pdf = next(e for e in entregables if e["mime"] == "application/pdf")
        self.assertTrue(pdf["datos"].startswith(b"%PDF-"))

    def test_NO_hay_una_segunda_funcion_que_haga_un_PDF(self):
        """Un `informe_pdf` aparte volvería a partir el documento en dos."""
        from shmir_design import presentation

        self.assertFalse(hasattr(presentation, "informe_pdf"))
