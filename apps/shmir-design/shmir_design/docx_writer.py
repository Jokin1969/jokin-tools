"""`Document` → `.docx`, con la libreria estandar y nada mas.

**Por que a mano y no con `python-docx`.** La regla 6 de este proyecto dice stdlib pura
en `shmir_design/` salvo autorizacion escrita, y un informe no justifica una dependencia
nueva: un `.docx` es un ZIP con cuatro XML dentro, y `zipfile` es stdlib. Lo que se gana
es que el informe se puede generar en cualquier sitio donde corra el nucleo, sin instalar
nada — que es justo lo que hace falta para que la app sea autosuficiente.

Lo que este escritor cubre: titulos de tres niveles, parrafos, listas, TABLAS DE VERDAD
—con bordes, no texto tabulado— , avisos en negrita y bloques preformateados en
monoespaciada. No cubre imagenes, encabezados de pagina ni indices automaticos, y no
hacen falta.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.sax.saxutils import escape

from .informe_doc import Document

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _style(style_id: str, name: str, size_half_points: int, *, bold: bool,
           mono: bool = False, outline: int | None = None) -> str:
    piezas = [
        f'<w:style {_W} w:type="paragraph" w:styleId="{style_id}">',
        f'<w:name w:val="{name}"/>',
    ]
    if outline is not None:
        piezas.append(f'<w:pPr><w:outlineLvl w:val="{outline}"/></w:pPr>')
    piezas.append("<w:rPr>")
    if mono:
        piezas.append('<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/>')
    if bold:
        piezas.append("<w:b/>")
    piezas.append(f'<w:sz w:val="{size_half_points}"/>')
    piezas.append("</w:rPr></w:style>")
    return "".join(piezas)


def _styles_xml() -> str:
    estilos = "".join([
        _style("Normal", "Normal", 20, bold=False),
        _style("Title", "Title", 40, bold=True),
        _style("Heading1", "heading 1", 32, bold=True, outline=0),
        _style("Heading2", "heading 2", 26, bold=True, outline=1),
        _style("Heading3", "heading 3", 22, bold=True, outline=2),
        _style("Aviso", "Aviso", 20, bold=True),
        _style("Preformateado", "Preformateado", 16, bold=False, mono=True),
    ])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:styles {_W}>{estilos}</w:styles>"
    )


def _p(text: str, style: str = "Normal") -> str:
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
        f"<w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def _cell(text: str, *, bold: bool) -> str:
    negrita = "<w:b/>" if bold else ""
    return (
        "<w:tc><w:tcPr><w:tcW w:w=\"0\" w:type=\"auto\"/></w:tcPr>"
        f'<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:rPr>{negrita}'
        f'<w:sz w:val="16"/></w:rPr><w:t xml:space="preserve">{escape(text)}</w:t>'
        "</w:r></w:p></w:tc>"
    )


def _table(headers, rows) -> str:
    bordes = "".join(
        f'<w:{lado} w:val="single" w:sz="4" w:color="999999"/>'
        for lado in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    piezas = [
        "<w:tbl><w:tblPr><w:tblW w:w=\"5000\" w:type=\"pct\"/>"
        f"<w:tblBorders>{bordes}</w:tblBorders></w:tblPr>",
        "<w:tr>" + "".join(_cell(h, bold=True) for h in headers) + "</w:tr>",
    ]
    for fila in rows:
        piezas.append(
            "<w:tr>" + "".join(_cell(c, bold=False) for c in fila) + "</w:tr>"
        )
    piezas.append("</w:tbl>")
    # Un parrafo vacio detras: Word junta dos tablas seguidas en una sola si no lo hay,
    # y entonces las cabeceras de la segunda parecen filas de la primera.
    piezas.append(_p(""))
    return "".join(piezas)


_HEADING_STYLES = {2: "Heading1", 3: "Heading2", 4: "Heading3"}


def _blocks_xml(document: Document) -> str:
    from .informe_doc import READING_NOTE, WHAT_COMPLETE_MEANS, WHAT_PARTIAL_MEANS

    piezas = [
        _p(document.title, "Title"),
        _p(f"Estado del informe: {document.state} · generado {document.generated}",
           "Aviso"),
        _p(
            WHAT_PARTIAL_MEANS if document.state == "PARCIAL" else WHAT_COMPLETE_MEANS
        ),
    ]
    if document.open_fronts:
        piezas.append(
            _p("Frentes abiertos: " + ", ".join(document.open_fronts) + ".", "Aviso")
        )
    piezas.append(_p(READING_NOTE))
    for seccion in document.sections:
        piezas.append(_p(f"{seccion.number}. {seccion.title}", "Heading1"))
        for bloque in seccion.blocks:
            if bloque.kind == "heading":
                piezas.append(
                    _p(bloque.text, _HEADING_STYLES.get(bloque.level, "Heading3"))
                )
            elif bloque.kind == "para":
                piezas.append(_p(bloque.text))
            elif bloque.kind == "warning":
                piezas.append(_p(bloque.text, "Aviso"))
            elif bloque.kind == "bullets":
                piezas.extend(_p(f"· {i}") for i in bloque.items)
            elif bloque.kind == "pre":
                piezas.extend(
                    _p(linea, "Preformateado")
                    for linea in bloque.text.rstrip("\n").splitlines()
                )
            else:
                piezas.append(_table(bloque.headers, bloque.rows))
    return "".join(piezas)


def to_docx(document: Document) -> bytes:
    """El documento como `.docx`. Devuelve BYTES: quien los escribe decide donde."""
    cuerpo = _blocks_xml(document)
    documento = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {_W}><w:body>{cuerpo}"
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>'
        "</w:sectPr></w:body></w:document>"
    )
    # UN `.docx` ES UN ZIP, ASI QUE TIENE EL PROBLEMA DE LOS ZIPS (errata nº 84, la
    # segunda mitad de la nº 76). `zipfile.writestr` con un nombre estampa la HORA
    # ACTUAL en cada entrada, asi que el mismo informe generado dos veces daba dos
    # ficheros distintos —medido: 50.766 bytes, dos md5— y Streamlit deriva el id de su
    # fichero de medios DEL CONTENIDO: bytes nuevos, id nuevo, y el que el navegador
    # esta descargando se queda huerfano y lo borra `remove_orphaned_files`.
    #
    # Se empaqueta con el UNICO constructor de zips del proyecto, y el orden va
    # DECLARADO porque aqui lo exige el formato: `[Content_Types].xml` primero (OPC).
    from .gestor import deterministic_zip  # noqa: PLC0415

    piezas = {
        "[Content_Types].xml": _CONTENT_TYPES,
        "_rels/.rels": _RELS,
        "word/_rels/document.xml.rels": _DOC_RELS,
        "word/styles.xml": _styles_xml(),
        "word/document.xml": documento,
    }
    return deterministic_zip(piezas, date=document.generated, order=list(piezas))
