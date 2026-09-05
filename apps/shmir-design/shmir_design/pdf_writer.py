"""`Document` → `.pdf`, con la libreria estandar y nada mas.

**Por que a mano y no con `reportlab`.** Mismo motivo que el `.docx`: la regla 6 pide
stdlib pura y un informe no justifica una dependencia. Un PDF de texto es un formato de
bytes con una tabla de referencias cruzadas al final, y con las fuentes base-14 —que todo
lector trae— no hay que incrustar nada.

Lo que este escritor NO hace, y va dicho porque importa al leerlo: las tablas salen en
monoespaciada con las columnas alineadas por relleno, no como tablas con bordes. Un PDF
con tablas de verdad necesita medir texto y dibujar lineas, y el `.docx` ya las trae. Las
columnas se RECORTAN para caber, y cuando se recorta se marca con `…` — un valor cortado
sin marca es peor que uno que no cabe.

Codificacion: WinAnsi, que es lo que entienden las base-14. Los caracteres que no
existen ahi se sustituyen por su equivalente ASCII a traves de `_TRANSLATION`, en vez de
petar o de salir como un cuadrito. La sustitucion es DECLARADA, no silenciosa: el
markdown y el `.docx` llevan el texto original.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

from .informe_doc import Document

#: A4 en puntos, y margenes generosos: esto se lee en pantalla y se imprime.
PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 45
LINE = 11.5

#: Lo que WinAnsi no tiene. Se sustituye por ASCII con el sentido intacto.
_TRANSLATION = {
    "⚠": "!", "≥": ">=", "≤": "<=", "→": "->", "↗": "->", "─": "-", "═": "=",
    "·": "-", "—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'",
    "…": "...", "«": '"', "»": '"', "±": "+/-", "×": "x", "→": "->",
    "🟢": "[verde]", "🟠": "[ambar]", "€": "EUR",
}


def _ascii(texto: str) -> str:
    salida = "".join(_TRANSLATION.get(c, c) for c in str(texto))
    return salida.encode("latin-1", "replace").decode("latin-1")


def _escape(texto: str) -> str:
    return (
        texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    )


@dataclass(frozen=True)
class _Line:
    text: str
    size: float
    bold: bool
    mono: bool
    gap: float = 0.0


#: Ancho medio por caracter, en fracciones del tamaño de fuente. Courier es exacto
#: (0,6); para Helvetica se usa 0,55, que sobreestima a proposito: pasarse al partir
#: lineas deja margen en blanco, quedarse corto saca texto por fuera de la pagina.
_WIDTH_HELVETICA = 0.55
_WIDTH_COURIER = 0.6


def _chars_per_line(size: float, mono: bool) -> int:
    ancho = size * (_WIDTH_COURIER if mono else _WIDTH_HELVETICA)
    return max(20, int((PAGE_WIDTH - 2 * MARGIN) / ancho))


def _wrap(texto: str, size: float, mono: bool) -> list[str]:
    limite = _chars_per_line(size, mono)
    if mono:
        # Una linea preformateada no se re-parte por palabras: se corta, porque su
        # alineacion es informacion.
        return [texto[i : i + limite] for i in range(0, max(len(texto), 1), limite)] or [""]
    palabras = texto.split()
    if not palabras:
        return [""]
    lineas, actual = [], palabras[0]
    for palabra in palabras[1:]:
        if len(actual) + 1 + len(palabra) <= limite:
            actual += " " + palabra
        else:
            lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    return lineas


def _table_lines(headers, rows) -> list[str]:
    """Tabla en monoespaciada, recortando columnas y MARCANDO el recorte."""
    columnas = len(headers)
    limite = _chars_per_line(7.5, mono=True)
    disponible = limite - (columnas - 1) * 2
    anchos = []
    for i in range(columnas):
        celdas = [str(headers[i])] + [str(f[i]) for f in rows]
        anchos.append(max(len(c) for c in celdas))
    total = sum(anchos)
    if total > disponible:
        # Se recorta proporcionalmente, con un minimo para que la columna siga siendo
        # legible. Lo que se recorta se marca.
        factor = disponible / total
        anchos = [max(6, int(a * factor)) for a in anchos]

    def fila(celdas):
        piezas = []
        # Una fila con MAS celdas que cabeceras perderia las de mas y el PDF
        # saldria con una columna menos, sin ningun error. `Block.__post_init__`
        # ya lo impide al construir la tabla; esto lo dice tambien aqui, que es
        # donde se lee.
        for ancho, celda in zip(anchos, celdas, strict=True):
            texto = str(celda)
            if len(texto) > ancho:
                texto = texto[: ancho - 1] + "..."
            piezas.append(texto.ljust(ancho))
        return "  ".join(piezas).rstrip()

    lineas = [fila(headers), "  ".join("-" * a for a in anchos)]
    lineas.extend(fila(f) for f in rows)
    return lineas


def _document_lines(document: Document) -> list[_Line]:
    from .informe_doc import READING_NOTE, WHAT_COMPLETE_MEANS, WHAT_PARTIAL_MEANS

    lineas: list[_Line] = []

    def añadir(texto: str, *, size=8.5, bold=False, mono=False, gap=0.0):
        for trozo in _wrap(_ascii(texto), size, mono):
            lineas.append(_Line(trozo, size, bold, mono))
        if gap:
            lineas.append(_Line("", size, False, False, gap=gap))

    añadir(document.title, size=17, bold=True, gap=4)
    añadir(
        f"Estado del informe: {document.state} - generado {document.generated}",
        size=10, bold=True, gap=3,
    )
    añadir(
        WHAT_PARTIAL_MEANS if document.state == "PARCIAL" else WHAT_COMPLETE_MEANS,
        gap=3,
    )
    if document.open_fronts:
        añadir(
            "Frentes abiertos: " + ", ".join(document.open_fronts) + ".",
            bold=True, gap=3,
        )
    añadir(READING_NOTE, gap=6)

    for seccion in document.sections:
        añadir(f"{seccion.number}. {seccion.title}", size=13, bold=True, gap=3)
        for bloque in seccion.blocks:
            if bloque.kind == "heading":
                añadir(bloque.text, size=10.5, bold=True, gap=2)
            elif bloque.kind == "para":
                añadir(bloque.text, gap=3)
            elif bloque.kind == "warning":
                añadir(bloque.text, bold=True, gap=3)
            elif bloque.kind == "bullets":
                for item in bloque.items:
                    añadir(f"- {item}")
                lineas.append(_Line("", 8.5, False, False, gap=3))
            elif bloque.kind == "pre":
                for linea in bloque.text.rstrip("\n").splitlines():
                    añadir(linea, size=7, mono=True)
                lineas.append(_Line("", 7, False, False, gap=3))
            else:
                for linea in _table_lines(bloque.headers, bloque.rows):
                    añadir(linea, size=7.5, mono=True)
                lineas.append(_Line("", 7.5, False, False, gap=3))
    return lineas


def _paginate(lineas: list[_Line]) -> list[list[tuple[float, _Line]]]:
    paginas, actual = [], []
    y = PAGE_HEIGHT - MARGIN
    for linea in lineas:
        alto = max(LINE, linea.size * 1.25) + linea.gap
        if y - alto < MARGIN:
            paginas.append(actual)
            actual, y = [], PAGE_HEIGHT - MARGIN
        y -= alto
        actual.append((y, linea))
    if actual:
        paginas.append(actual)
    return paginas or [[]]


_FONTS = {
    (False, False): "/F1",   # Helvetica
    (True, False): "/F2",    # Helvetica-Bold
    (False, True): "/F3",    # Courier
    (True, True): "/F3",
}


def _content(pagina) -> bytes:
    piezas = ["BT"]
    for y, linea in pagina:
        if not linea.text:
            continue
        fuente = _FONTS[(linea.bold, linea.mono)]
        piezas.append(f"{fuente} {linea.size:.1f} Tf")
        piezas.append(f"1 0 0 1 {MARGIN} {y:.1f} Tm")
        piezas.append(f"({_escape(linea.text)}) Tj")
    piezas.append("ET")
    return "\n".join(piezas).encode("latin-1", "replace")


def to_pdf(document: Document) -> bytes:
    """El documento como `.pdf`. Devuelve BYTES: quien los escribe decide donde."""
    paginas = _paginate(_document_lines(document))
    objetos: list[bytes] = []

    def add(cuerpo: bytes) -> int:
        objetos.append(cuerpo)
        return len(objetos)

    fuentes = {
        "/F1": b"/Helvetica", "/F2": b"/Helvetica-Bold", "/F3": b"/Courier",
    }
    ids_fuente = {
        clave: add(
            b"<< /Type /Font /Subtype /Type1 /BaseFont " + nombre
            + b" /Encoding /WinAnsiEncoding >>"
        )
        for clave, nombre in fuentes.items()
    }
    recursos = (
        b"<< /Font << "
        + b" ".join(
            f"{clave} {ids_fuente[clave]} 0 R".encode("ascii") for clave in fuentes
        )
        + b" >> >>"
    )

    id_paginas = add(b"")  # reservado: se rellena al final, cuando hay hijos
    hijos = []
    for pagina in paginas:
        datos = zlib.compress(_content(pagina))
        id_stream = add(
            b"<< /Length " + str(len(datos)).encode("ascii")
            + b" /Filter /FlateDecode >>\nstream\n" + datos + b"\nendstream"
        )
        id_pagina = add(
            b"<< /Type /Page /Parent " + str(id_paginas).encode("ascii")
            + b" 0 R /MediaBox [0 0 " + str(PAGE_WIDTH).encode("ascii") + b" "
            + str(PAGE_HEIGHT).encode("ascii") + b"] /Resources " + recursos
            + b" /Contents " + str(id_stream).encode("ascii") + b" 0 R >>"
        )
        hijos.append(id_pagina)
    objetos[id_paginas - 1] = (
        b"<< /Type /Pages /Count " + str(len(hijos)).encode("ascii") + b" /Kids ["
        + b" ".join(f"{h} 0 R".encode("ascii") for h in hijos) + b"] >>"
    )
    id_catalogo = add(
        b"<< /Type /Catalog /Pages " + str(id_paginas).encode("ascii") + b" 0 R >>"
    )

    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for numero, cuerpo in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{numero} 0 obj\n".encode("ascii") + cuerpo + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n".encode("ascii")
    salida += b"0000000000 65535 f \n"
    for posicion in posiciones:
        salida += f"{posicion:010d} 00000 n \n".encode("ascii")
    salida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root {id_catalogo} 0 R >>\n"
        f"startxref\n{inicio_xref}\n%%EOF\n"
    ).encode("ascii")
    return bytes(salida)
