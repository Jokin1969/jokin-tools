"""El informe como documento: parcial o completo, en docx y pdf.

Regla 5: escritos antes.

Tiene que poder leerse SIN la app delante y SIN haber estado en las conversaciones. Lo
que se comprueba aqui son las tres reglas de redaccion, que es lo que hace que eso sea
verdad y no una intencion:

  - ningun umbral sin justificar, y los que no tienen base medida lo dicen;
  - toda cifra comparativa con su referencia;
  - `NOT_RUN` visible en el CUERPO, nunca solo en un anexo.

Y el documento entero entra en el golden, con la misma disciplina que el informe de
texto y la ficha: se compara ENTERO, no por presencia de fragmentos.
"""

import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from shmir_design import informe_doc, justificacion
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)
GOLDEN = Path(__file__).resolve().parent / "golden" / "informe_documento.md"

FECHA = "2026-08-26"


def _documento():
    from shmir_design.apa import resolve_measured
    from shmir_design.selection import default_config, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(RATON)
    informe = tile_utr(utr3)
    # `default_config()`, la MISMA que usa `tools/regenerar_golden.py`. Estaba escrito a
    # mano con `n_candidates=10` y coincidia por casualidad: el dia que el panel del
    # proyecto paso a once, el golden y su regenerador construyeron dos documentos
    # distintos. Dos formas de montar lo mismo divergen (principio nº 24).
    seleccion = select_from_report(informe, default_config())
    return informe_doc.build_document(
        species="mouse", tiling=informe, selection=seleccion, generated=FECHA,
        anatomy_source="lo tilado ES el 3'UTR (fixture verificado por md5)",
        # `target` igual que en `tools/regenerar_golden.py`: el documento se construye
        # AQUI exactamente como se genera el golden, o el golden deja de comparar lo
        # que se entrega.
        dossier_starts=(200,), target=utr3,
    )


class TestNingunUmbralSinJustificar(unittest.TestCase):

    def test_los_origenes_son_TRES_y_estan_cerrados(self):
        self.assertEqual(
            justificacion.ORIGINS, ("literatura", "convencion", "nuestro")
        )

    def test_TODO_campo_de_Thresholds_tiene_su_procedencia(self):
        from dataclasses import fields

        from shmir_design.hard_filters import Thresholds

        declarados = {u.key for u in justificacion.THRESHOLDS}
        faltan = sorted({f.name for f in fields(Thresholds)} - declarados)
        self.assertEqual(
            faltan, [],
            f"Umbral(es) sin justificar: {faltan}. Un número en un informe sin decir de "
            f"donde sale se lee como una medida; añadelo a `justificacion.THRESHOLDS`.",
        )

    def test_un_origen_inventado_ABORTA(self):
        with self.assertRaises(ValueError):
            justificacion.ThresholdSource(
                key="x", label="x", value="1", origin="intuicion", rationale="porque si",
            )

    def test_un_umbral_sin_racional_ABORTA(self):
        with self.assertRaises(ValueError):
            justificacion.ThresholdSource(
                key="x", label="x", value="1", origin="nuestro", rationale="  ",
            )

    def test_el_flanco_de_10_nt_dice_EXPRESAMENTE_que_no_tiene_base_medida(self):
        flanco = justificacion.threshold("polya_flank")
        self.assertFalse(flanco.measured)
        texto = flanco.no_measured_basis.lower()
        self.assertIn("no tiene base medida", texto)
        self.assertIn("cpsf", texto)
        self.assertIn("gradiente", texto)

    def test_los_que_SI_tienen_base_no_llevan_ese_aviso(self):
        self.assertTrue(justificacion.threshold("gc_min").measured)
        self.assertTrue(justificacion.threshold("cleavage_band").measured)

    def test_un_umbral_que_no_existe_ABORTA_nombrando_los_que_hay(self):
        with self.assertRaises(ShmirDesignError) as caja:
            justificacion.threshold("inventado")
        self.assertIn("gc_min", str(caja.exception))


class TestElModelo(unittest.TestCase):

    def test_una_tabla_descuadrada_ABORTA(self):
        with self.assertRaises(ValueError):
            informe_doc.table(("a", "b"), [("uno",)])

    def test_un_bloque_de_tipo_desconocido_ABORTA(self):
        with self.assertRaises(ValueError):
            informe_doc.Block(kind="video")

    def test_un_informe_COMPLETO_con_frentes_abiertos_ABORTA(self):
        with self.assertRaises(ValueError) as caja:
            informe_doc.Document(
                title="x", state="COMPLETO", generated=FECHA, sections=(),
                open_fronts=("seed",),
            )
        self.assertIn("comprobo", str(caja.exception))

    def test_un_informe_PARCIAL_sin_frentes_abiertos_ABORTA(self):
        with self.assertRaises(ValueError):
            informe_doc.Document(
                title="x", state="PARCIAL", generated=FECHA, sections=(),
            )


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLasSieteSecciones(unittest.TestCase):
    """Cada sección es lo que dice ser, y se busca POR TÍTULO.

    Estaban buscadas por NÚMERO —`section(4)`, `section(6)`— y eso las ataba al orden:
    insertar una sección en medio las rompía todas, que es el mismo acoplamiento que
    tenían los propios números antes de derivarlos por posición. Ahora el número es una
    consecuencia del orden y el test no lo usa para nada.
    """

    @classmethod
    def setUpClass(cls):
        cls.doc = _documento()
        cls.md = cls.doc.markdown()

    def _seccion(self, fragmento):
        for seccion in self.doc.sections:
            if fragmento.lower() in seccion.title.lower():
                return seccion
        raise AssertionError(
            f"sin sección {fragmento!r}; las que hay: "
            f"{[s.title for s in self.doc.sections]}"
        )

    def test_los_numeros_son_CONSECUTIVOS_y_empiezan_en_uno(self):
        numeros = [s.number for s in self.doc.sections]
        self.assertEqual(numeros, list(range(1, len(numeros) + 1)))

    def test_ninguna_seccion_se_queda_con_el_CERO_del_constructor(self):
        """Las secciones nuevas se construyen con `number=0` y lo asigna el ensamblado.
        Un cero que llegara al documento sería una sección sin numerar."""
        self.assertNotIn(0, [s.number for s in self.doc.sections])

    def test_1_dice_QUE_se_analizo_con_longitud_y_md5_JUNTOS(self):
        texto = "\n".join(_markdown_of(self._seccion("Que se analizo")))
        self.assertIn("1242 nt / 19f5fa2a", texto)

    def test_2_dice_que_frentes_faltan_y_DONDE_conseguirlos(self):
        texto = "\n".join(_markdown_of(self._seccion("Estado de los frentes")))
        self.assertIn("NOT_RUN", texto)
        self.assertIn("mirbase.org", texto)
        self.assertIn("repeatmasker.org", texto)

    def test_3_trae_por_frente_que_mide_por_que_importa_y_el_criterio(self):
        texto = "\n".join(_markdown_of(self._seccion("Frente por frente")))
        self.assertIn("Que mide", texto)
        self.assertIn("Por que importa", texto)
        self.assertIn("Fuente de datos", texto)

    def test_3_trae_la_ficha_de_obtencion_de_cada_frente_ABIERTO(self):
        texto = "\n".join(_markdown_of(self._seccion("Frente por frente")))
        self.assertIn("COMO CERRAR EL FRENTE", texto)
        self.assertIn("3' UTR Exons", texto)

    def test_4_es_la_tabla_de_candidatos_CON_TODAS_las_columnas(self):
        tabla = next(
            b for b in self._seccion("Tabla de candidatos").blocks if b.kind == "table"
        )
        # `carga_seed` se retiro (2026-09-04): era la SUMA de tres clases y salia sin
        # sus sumandos. Ahora estan los tres, y las cuatro del frente al lado.
        for columna in ("inicio", "asimetria_kcal", "tilado_8mer", "carga_8mer",
                        "veredicto"):
            self.assertIn(columna, tabla.headers)
        self.assertNotIn("carga_seed", tabla.headers)

    def test_5_trae_la_ficha_entera_del_seleccionado(self):
        texto = "\n".join(_markdown_of(self._seccion("Fichas de los seleccionados")))
        self.assertIn("3utr:200", texto)
        self.assertIn("Frentes (", texto)

    def test_6_es_una_SECCION_propia_y_no_un_pie(self):
        limitaciones = self._seccion("Limitaciones")
        self.assertEqual(limitaciones.title, "Limitaciones")
        procedencia = self._seccion("Procedencia")
        self.assertLess(limitaciones.number, procedencia.number)

    def test_7_lista_la_procedencia_de_TODOS_los_recursos(self):
        texto = "\n".join(_markdown_of(self._seccion("Procedencia")))
        for recurso in ("máscara de repetitivos", "maduros de miRBase", "APA medido"):
            self.assertIn(recurso, texto)


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLasTresReglasDeRedaccion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.doc = _documento()
        cls.md = cls.doc.markdown()

    def test_todo_umbral_impreso_lleva_su_ORIGEN(self):
        for seccion in self.doc.sections:
            for bloque in seccion.blocks:
                if bloque.kind != "table" or "origen" not in bloque.headers:
                    continue
                indice = bloque.headers.index("origen")
                for fila in bloque.rows:
                    self.assertIn(fila[indice], justificacion.ORIGINS, fila)

    def test_los_umbrales_sin_base_medida_salen_JUNTOS_en_limitaciones(self):
        texto = "\n".join(_markdown_of(_por_titulo(self.doc, "Limitaciones")))
        for umbral in justificacion.unmeasured():
            self.assertIn(umbral.label, texto, umbral.key)

    def test_la_carga_de_offtargets_va_con_su_PERCENTIL(self):
        texto = "\n".join(_markdown_of(_por_titulo(self.doc, "Frente por frente")))
        self.assertIn("percentil", texto.lower())

    def test_la_colision_de_seed_va_con_su_TASA_BASE(self):
        texto = "\n".join(_markdown_of(_por_titulo(self.doc, "Frente por frente")))
        self.assertIn("tasa base", texto.lower())

    def test_NOT_RUN_esta_en_el_CUERPO_y_no_solo_al_final(self):
        primera = self.md.index("NOT_RUN")
        seccion_6 = self.md.index("## 6.")
        self.assertLess(
            primera, seccion_6,
            "Un NOT_RUN que solo aparece en un anexo se lee después de haber creido la "
            "tabla de candidatos.",
        )

    def test_y_el_estado_del_informe_esta_en_la_PRIMERA_pantalla(self):
        self.assertIn("Estado del informe: PARCIAL", self.md.splitlines()[2])


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestParcialYCompletoSonELMISMO(unittest.TestCase):

    def test_hoy_sale_PARCIAL_porque_hay_frentes_abiertos(self):
        doc = _documento()
        self.assertEqual(doc.state, "PARCIAL")
        self.assertIn("especificidad", doc.open_fronts)

    def test_y_el_documento_DICE_que_parcial_no_es_borrador(self):
        texto = informe_doc.WHAT_PARTIAL_MEANS.lower()
        self.assertIn("no es un borrador", texto)
        self.assertIn("incomplete", texto)

    #: El ESQUELETO: las secciones que salen siempre, con frentes abiertos o cerrados.
    #: Se comprueban por TITULO. Estaba escrito como `len(doc.sections) == 7`, que no es
    #: la invariante que el test dice comprobar —«el completo no gana ni pierde
    #: secciones»— sino un recuento: añadir una seccion lo rompia sin que hubiera pasado
    #: nada de lo que vigila.
    ESQUELETO = (
        "Que se analizo",
        "Estado de los frentes",
        "Frente por frente",
        "Mapa del 3'UTR",
        "Tabla de candidatos",
        "Todos los sitios elegibles",
        "Controles del experimento",
        # AÑADIDA (2026-09-05). Compara las dos arquitecturas de intrón eje a eje, y
        # entra porque eso DECIDE QUE SE SINTETIZA: vivía en un desplegable de la
        # interfaz, que es donde no lo lee quien recibe el documento.
        "Arquitecturas de intrón",
        "Fichas de los seleccionados",
        "Limitaciones",
        "Procedencia",
    )

    def test_las_secciones_son_LAS_MISMAS_en_los_dos_estados(self):
        """No son dos productos: el completo no gana ni pierde secciones.

        Hoy NO se puede construir un COMPLETO —ningun frente cierra sin ficheros— asi
        que lo que se puede afirmar es que las secciones no dependen del estado: el
        esqueleto sale entero con el documento en PARCIAL. El dia que uno cierre, este
        mismo test lo comprueba sobre el otro estado sin tocar nada.
        """
        doc = _documento()
        self.assertEqual(doc.state, "PARCIAL")
        titulos = [s.title for s in doc.sections]
        for esperado in self.ESQUELETO:
            with self.subTest(esperado):
                self.assertTrue(
                    any(esperado in t for t in titulos),
                    f"falta {esperado!r}; hay {titulos}",
                )
        self.assertEqual(len(titulos), len(self.ESQUELETO))


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElGolden(unittest.TestCase):
    """El informe ENTERO, como el de texto y como la ficha."""

    def test_el_documento_no_ha_cambiado(self):
        if not GOLDEN.is_file():
            self.fail(
                f"No existe {GOLDEN}. Genera el golden con "
                f"`python3 tools/regenerar_golden.py`."
            )
        import difflib

        # SE LE PIDE AL MISMO GENERADOR QUE ESCRIBE EL GOLDEN. Rehacer aqui la corrida
        # es tenerla definida dos veces, y ya se dio: el test usaba la configuracion por
        # defecto y el generador `n_candidates=10`, asi que el golden decia 10 y el test
        # veia 6. Ademas es lo que trae la cabecera que declara sobre que se genera.
        from tools.regenerar_golden import generar_documento

        esperado = GOLDEN.read_text(encoding="utf-8")
        actual = generar_documento()
        if esperado != actual:
            diff = "\n".join(
                difflib.unified_diff(
                    esperado.splitlines(), actual.splitlines(),
                    fromfile="informe_documento.md (referencia)",
                    tofile="documento generado ahora", lineterm="",
                )
            )
            self.fail(
                "El informe ha cambiado. Si el cambio es a propósito, regeneralo con "
                "`python3 tools/regenerar_golden.py` y que el diff entre en la "
                f"revision:\n{diff[:4000]}"
            )


    def test_lo_UNICO_fijado_es_la_FECHA_no_la_procedencia_de_la_entrada(self):
        """La fecha es ruido; el md5 de la entrada, no.

        El generador del golden fija la fecha para que el diff siga significando algo.
        Lo que NO se fija es la secuencia: su longitud y su md5 salen del informe, asi
        que un documento generado sobre OTRA secuencia hace fallar el golden. Se
        comprueba construyendolo sobre el 3'UTR humano.
        """
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        humano = REFERENCES["NM_000311.5"]
        if not fixture_available(humano):
            self.skipTest("NOT_RUN: falta el fixture humano")
        utr3 = load_3utr(humano)
        informe = tile_utr(utr3)
        otro = informe_doc.build_document(
            species="human", tiling=informe,
            selection=select_from_report(informe, SelectionConfig(n_candidates=10)),
            generated=FECHA,  # MISMA fecha: el unico campo que el golden fija
            anatomy_source="lo tilado ES el 3'UTR (fixture verificado por md5)",
            dossier_starts=(),
        ).markdown()
        golden = GOLDEN.read_text(encoding="utf-8")
        self.assertNotEqual(
            otro, golden,
            "Con la fecha igualada, el golden TIENE que seguir distinguiendo dos "
            "secuencias distintas: si no, no fija la procedencia de la entrada.",
        )
        self.assertIn("1242 nt / 19f5fa2a", golden)
        self.assertNotIn("1242 nt / 19f5fa2a", otro)

    def test_y_el_md5_del_documento_es_el_de_la_secuencia_ANALIZADA(self):
        from shmir_design.reference import sequence_md5

        doc = _documento()
        texto = "\n".join(_markdown_of(doc.section(1)))
        self.assertIn(sequence_md5(load_3utr(RATON)), texto)

    def test_el_golden_de_hoy_es_el_PARCIAL_y_lo_dice(self):
        self.assertIn("Estado del informe: PARCIAL", GOLDEN.read_text(encoding="utf-8"))


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElDocx(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.docx_writer import to_docx

        cls.datos = to_docx(_documento())

    def test_es_un_ZIP_valido_con_las_cuatro_partes(self):
        zf = zipfile.ZipFile(BytesIO(self.datos))
        self.assertIsNone(zf.testzip())
        for parte in (
            "[Content_Types].xml", "_rels/.rels", "word/document.xml",
            "word/styles.xml", "word/_rels/document.xml.rels",
        ):
            self.assertIn(parte, zf.namelist())

    def test_el_XML_del_documento_es_valido(self):
        import xml.dom.minidom

        zf = zipfile.ZipFile(BytesIO(self.datos))
        xml.dom.minidom.parseString(zf.read("word/document.xml"))

    def test_las_tablas_son_TABLAS_de_verdad_no_texto_tabulado(self):
        zf = zipfile.ZipFile(BytesIO(self.datos))
        cuerpo = zf.read("word/document.xml").decode("utf-8")
        self.assertIn("<w:tbl>", cuerpo)
        self.assertIn("w:tblBorders", cuerpo)

    def test_el_texto_llega_ENTERO_sin_sustituciones(self):
        zf = zipfile.ZipFile(BytesIO(self.datos))
        cuerpo = zf.read("word/document.xml").decode("utf-8")
        self.assertIn("NOT_RUN", cuerpo)
        self.assertIn("±10 nt", cuerpo)

    def test_y_los_caracteres_de_XML_van_ESCAPADOS(self):
        zf = zipfile.ZipFile(BytesIO(self.datos))
        cuerpo = zf.read("word/document.xml").decode("utf-8")
        self.assertNotIn("<w:t>3utr:200 <", cuerpo)


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElPdf(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.pdf_writer import to_pdf

        cls.datos = to_pdf(_documento())

    def test_empieza_y_acaba_como_un_PDF(self):
        self.assertTrue(self.datos.startswith(b"%PDF-1.4"))
        self.assertTrue(self.datos.rstrip().endswith(b"%%EOF"))

    def test_la_tabla_XREF_apunta_a_objetos_de_verdad(self):
        """Si un desplazamiento esta mal, el lector abre un PDF vacio y no da error."""
        cola = self.datos[self.datos.rindex(b"startxref"):]
        inicio = int(cola.split(b"\n")[1])
        cabecera = self.datos[inicio:].split(b"\n")[1].split()
        total = int(cabecera[1])
        cuerpo = self.datos[inicio:].split(b"\n")[2 : 2 + total]
        for numero, linea in enumerate(cuerpo[1:], start=1):
            desplazamiento = int(linea.split()[0])
            self.assertTrue(
                self.datos[desplazamiento:].startswith(f"{numero} 0 obj".encode()),
                f"El objeto {numero} no esta donde dice la xref.",
            )

    def test_tiene_mas_de_una_pagina_y_todas_cuelgan_del_arbol(self):
        paginas = self.datos.count(b"/Type /Page ")
        self.assertGreater(paginas, 1)
        self.assertIn(f"/Count {paginas}".encode(), self.datos)

    def test_usa_fuentes_base_14_asi_que_no_incrusta_nada(self):
        for fuente in (b"/Helvetica", b"/Helvetica-Bold", b"/Courier"):
            self.assertIn(fuente, self.datos)
        self.assertNotIn(b"/FontFile", self.datos)

    def test_los_parentesis_van_ESCAPADOS(self):
        """Un parentesis sin escapar cierra la cadena y rompe el resto de la pagina."""
        from shmir_design.pdf_writer import _escape

        self.assertEqual(_escape("(a)"), r"\(a\)")

    def test_lo_que_WinAnsi_no_tiene_se_SUSTITUYE_y_esta_declarado(self):
        from shmir_design.pdf_writer import _TRANSLATION, _ascii

        self.assertIn("⚠", _TRANSLATION)
        self.assertEqual(_ascii("⚠ x"), "! x")
        self.assertNotIn("⚠", _ascii("⚠"))

    def test_una_tabla_recortada_MARCA_el_recorte(self):
        from shmir_design.pdf_writer import _table_lines

        lineas = _table_lines(
            ("a", "b"), [("x" * 400, "y" * 400)]
        )
        self.assertIn("...", "\n".join(lineas))


class TestLaPaginaTieneElBoton(unittest.TestCase):

    def test_el_informe_se_puede_descargar_desde_la_pagina(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("informe_documento", fuente)
        self.assertIn("informe_files", fuente)

    def test_y_la_pagina_NO_arma_los_nombres_ni_los_formatos(self):
        """Regla 6: el nombre del fichero y el mime son decisiones, y viven fuera."""
        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        for prohibido in ('".docx"', '".pdf"', "vnd.openxmlformats"):
            self.assertNotIn(prohibido, fuente, prohibido)

    def test_presentation_da_los_TRES_entregables_con_su_mime(self):
        from shmir_design import presentation

        doc = _documento() if HAY else None
        if doc is None:
            self.skipTest("NOT_RUN: falta el fixture del raton")
        entregables = presentation.informe_files(doc, stem="raton")
        # EL ORDEN ES DELIBERADO: primero lo que se manda y se imprime, y el markdown
        # el ultimo porque es la FUENTE —para discutir una frase sin maquetar—, no el
        # entregable. Alfabetico dejaba el `.pdf` al final sin ninguna razon.
        self.assertEqual(
            [e["nombre"] for e in entregables],
            [
                "raton_informe_parcial.docx",
                "raton_informe_parcial.pdf",
                "raton_informe_parcial.md",
            ],
        )
        # Y LA ETIQUETA DEL BOTON NO ES EL NOMBRE DEL FICHERO. Lo era, y por eso la
        # seccion se leia como una lista de ficheros: se reporto como «no encuentro
        # donde se descarga el informe» con los tres botones en pantalla.
        for entregable in entregables:
            self.assertNotEqual(entregable["etiqueta"], entregable["nombre"])
            self.assertIn("Descargar", entregable["etiqueta"])
        for entregable in entregables:
            self.assertTrue(entregable["datos"])
            self.assertTrue(entregable["mime"])


def _por_titulo(documento, fragmento):
    """La sección POR TÍTULO. Buscarla por número la ata al orden, y el número es ahora
    una consecuencia del orden: insertar una sección en medio rompía todos estos tests
    sin que hubiera pasado nada de lo que vigilan."""
    for seccion in documento.sections:
        if fragmento.lower() in seccion.title.lower():
            return seccion
    raise AssertionError(
        f"sin sección {fragmento!r}; hay {[s.title for s in documento.sections]}"
    )


def _markdown_of(section) -> list[str]:
    from shmir_design.informe_doc import _markdown_block

    lineas = []
    for bloque in section.blocks:
        lineas.extend(_markdown_block(bloque))
    return lineas


if __name__ == "__main__":
    unittest.main()
