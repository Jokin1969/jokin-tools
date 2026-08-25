"""Tabla comparativa unica de los candidatos seleccionados (bloque 6).

Es lo que permite discutir descartes sobre DATOS. Una sola tabla con los N elegidos y
todos los parametros lado a lado: posicion en las dos coordenadas, tercio, region,
diana, guia, pasajera, el modulo NheI-SacI de 149 nt listo para pedir, GC, asimetria,
los cinco campos de polyA, riesgo de APA, especificidad con sus recuentos por numero de
desapareamientos, transgen, colision de seed, carga de seed, accesibilidad, y el
veredicto de cada filtro en su columna.

**Y una columna `knockdown_medido` vacia.** La idea es que este TSV vuelva del
laboratorio relleno y se pueda correlacionar cada parametro contra la potencia real.
Ahora mismo se ordena por asimetria, que predice SELECCION DE HEBRA y no potencia; con
diez medidas se sabra que parametros predicen algo y cuales son decoracion. Ese es el
motivo de llevar diez candidatos a sintesis y no dos.

Regla 3 llevada hasta el final: un campo sin dato va VACIO, nunca a cero. Sin base de
especificidad la columna de hits no es `0`, esta vacia — porque cero hits y no haber
contado son cosas distintas y confundirlas es exactamente lo que este proyecto prohibe.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from .gblock import build_gblock
from .polya import POLYA_COLUMNS
from .scaffold import ScaffoldSpec, build_hairpin
from .selection import ReportSelection

#: Columnas fijas, en el orden en que se leen. Las de `filtro:<nombre>` se añaden
#: detras, una por filtro, y `knockdown_medido` va SIEMPRE la ultima.
COMPARATIVE_COLUMNS = (
    "inicio_3utr",
    "fin_3utr",
    "inicio_transcrito",
    "fin_transcrito",
    "region",
    "tercio",
    "diana",
    "guia",
    "pasajera",
    "gblock_149",
    "GC",
    "asimetria",
    "asimetria_penalizada",
    *POLYA_COLUMNS,
    "riesgo_APA",
    "APA_medido",
    "especificidad_0mm",
    "especificidad_1mm",
    "especificidad_2mm",
    "transgen",
    "seed_colision",
    "carga_seed",
    "accesibilidad",
    "accesibilidad_seed",
    "veredicto",
    "knockdown_medido",
)

CABECERA = (
    "# Tabla comparativa de shmir-design. La columna knockdown_medido va VACIA a "
    "proposito:\n"
    "# rellenala en el laboratorio y devuelve el fichero para poder correlacionar cada\n"
    "# parametro contra la potencia real. Un campo vacio significa 'no se midio', "
    "NUNCA cero.\n"
)


def _mismatch_counts(detalle) -> dict[int, str]:
    """Hits antisentido por numero de desapareamientos. Vacio si no se conto."""
    if detalle is None:
        return {0: "", 1: "", 2: ""}
    conteo = {0: 0, 1: 0, 2: 0}
    for hit in detalle.hits:
        if hit.mismatches in conteo:
            conteo[hit.mismatches] += 1
    return {k: str(v) for k, v in conteo.items()}


def comparative_rows(
    selection: ReportSelection, scaffold: ScaffoldSpec
) -> list[list[str]]:
    """Cabecera y una fila por candidato elegido."""
    elegidos = list(selection.selection.chosen)
    filtros: list[str] = []
    if elegidos:
        filtros = [r.name for r in selection.window_of(elegidos[0]).filters]

    columnas = [
        *COMPARATIVE_COLUMNS[:-1],
        *(f"filtro:{n}" for n in filtros),
        "knockdown_medido",
    ]
    rows = [columnas]

    for choice in elegidos:
        window = selection.window_of(choice)
        hairpin = build_hairpin(window.evaluation.guide, scaffold=scaffold)
        gblock = build_gblock(hairpin)
        polya = window.polya.as_columns() if window.polya else dict.fromkeys(POLYA_COLUMNS, "")
        especificidad = _mismatch_counts(window.especificidad_detalle)

        fila = {
            "inicio_3utr": "" if window.inicio_3utr is None else str(window.inicio_3utr),
            "fin_3utr": "" if window.fin_3utr is None else str(window.fin_3utr),
            "inicio_transcrito": str(window.window.start),
            "fin_transcrito": str(window.window.end),
            "region": window.region.value,
            "tercio": window.tercio.value if window.tercio else "",
            "diana": window.evaluation.sequence,
            "guia": window.evaluation.guide,
            "pasajera": hairpin.passenger,
            "gblock_149": gblock.sequence,
            "GC": f"{_gc(window.evaluation.sequence):.3f}",
            "asimetria": (
                "" if choice.asymmetry_raw is None else f"{choice.asymmetry_raw:+.2f}"
            ),
            "asimetria_penalizada": f"{choice.asymmetry:+.2f}",
            **polya,
            "riesgo_APA": (
                window.apa.as_column()
                if window.apa is not None
                else ("NO_APLICA" if not window.apa_aplica else "")
            ),
            "APA_medido": (
                "si" if window.apa is not None and window.apa.measured else "no"
            ),
            "especificidad_0mm": especificidad[0],
            "especificidad_1mm": especificidad[1],
            "especificidad_2mm": especificidad[2],
            "transgen": window.filter("transgen").state.value,
            "seed_colision": window.filter("seed_colision").state.value,
            "carga_seed": (
                window.carga_seed.as_column() if window.carga_seed is not None else ""
            ),
            "accesibilidad": (
                window.accesibilidad.as_column()
                if window.accesibilidad is not None
                else ""
            ),
            "accesibilidad_seed": _seed_access(window),
            "veredicto": window.verdict.value,
            "knockdown_medido": "",
        }
        for resultado in window.filters:
            fila[f"filtro:{resultado.name}"] = resultado.state.value
        rows.append([_limpio(fila.get(c, "")) for c in columnas])

    return rows


def _gc(sequence: str) -> float:
    from .hard_filters import gc_fraction  # noqa: PLC0415

    return gc_fraction(sequence)


def _seed_access(window) -> str:
    acceso = window.accesibilidad
    if acceso is None or not acceso.seed_unpaired_fraction:
        return ""
    from .accessibility import CONTEXT_WINDOWS  # noqa: PLC0415

    return f"{acceso.seed_unpaired_fraction[CONTEXT_WINDOWS[0]]:.2f}"


def _limpio(campo: str) -> str:
    return str(campo).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def comparative_tsv(
    selection: ReportSelection, scaffold: ScaffoldSpec, *, with_header: bool = False
) -> str:
    """La tabla en TSV. `with_header` añade el comentario que explica la columna vacia."""
    cuerpo = "\n".join(
        "\t".join(fila) for fila in comparative_rows(selection, scaffold)
    )
    return (CABECERA + cuerpo) if with_header else cuerpo


#: Columnas que se enseñan en el bloque legible del informe. La tabla entera no cabe en
#: una consola, asi que el informe da las que sirven para decidir y el TSV lo trae todo.
RESUMEN_COLUMNS = (
    "inicio_3utr",
    "tercio",
    "GC",
    "asimetria",
    "polyA_solapa_seed",
    "riesgo_APA",
    "carga_seed",
    "accesibilidad",
    "veredicto",
)


def comparative_text(selection: ReportSelection, scaffold: ScaffoldSpec) -> str:
    """Bloque legible: las columnas que sirven para decidir, alineadas."""
    filas = comparative_rows(selection, scaffold)
    if len(filas) < 2:
        return "  (no hay candidatos seleccionados)"
    indices = [filas[0].index(c) for c in RESUMEN_COLUMNS]
    anchos = [
        max(len(RESUMEN_COLUMNS[i]), *(len(f[indice]) for f in filas[1:]))
        for i, indice in enumerate(indices)
    ]
    lineas = [
        "  " + "  ".join(c.ljust(a) for c, a in zip(RESUMEN_COLUMNS, anchos))
    ]
    for fila in filas[1:]:
        lineas.append(
            "  "
            + "  ".join(fila[i].ljust(a) for i, a in zip(indices, anchos))
        )
    lineas.append(
        "  La tabla COMPLETA —con la pasajera, el modulo de 149 nt, los cinco campos de"
    )
    lineas.append(
        "  polyA, los recuentos de especificidad y una columna por filtro— esta en el "
        "TSV comparativo,"
    )
    lineas.append(
        "  con la columna knockdown_medido vacia para que vuelva rellena del "
        "laboratorio."
    )
    return "\n".join(lineas)
