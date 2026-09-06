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

from .anatomy import Anatomy
from .coords import Frame, bound_of, label, tiled_frame
from .external_score import (
    FEATURE_COLUMNS,
    MIRARCH_COLUMNS,
    ExternalScore,
    splashrna_features,
)
from .gblock import build_gblock
from .offtarget import SITE_CLASSES
from .polya import POLYA_COLUMNS
from .seed_load import LOAD_COLUMNS
from .scaffold import ScaffoldSpec, build_hairpin
from .selection import ReportSelection

#: LAS CUATRO COLUMNAS DEL FRENTE, derivadas de sus clases y no escritas: si mañana entra
#: una quinta clase, entra aqui sola. Llevan percentil pegado y las pone la CORRIDA
#: guardada, no el tilado — por eso su prefijo es distinto del de `LOAD_COLUMNS`.
OFFTARGET_COLUMNS = tuple(f"carga_{clase}" for clase in SITE_CLASSES)

#: Columnas fijas, en el orden en que se leen. Las de `filtro:<nombre>` se añaden
#: detras, una por filtro, y las tres columnas que esperan un dato de fuera
#: —`score_externo`, `fuente_score` y `knockdown_medido`— van SIEMPRE las ultimas.
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
    "penalizacion",
    "asimetria_penalizada",
    *POLYA_COLUMNS,
    "riesgo_APA",
    "APA_medido",
    "especificidad_0mm",
    "especificidad_1mm",
    "especificidad_2mm",
    "transgen",
    "seed_colision",
    # LOS SUMANDOS, NO LA SUMA. `carga_seed` era el total de las tres clases y salia sin
    # ellas; ver `seed_load.WHERE_THE_TOTAL_WENT`. Y las cuatro `carga_<clase>` —con
    # percentil y con el 6mer— venian saliendo en la tabla de la pagina y NO aqui: la
    # errata nº 70 llego a `candidate_rows` y no al TSV, que es el artefacto que se
    # descarga y se discute (septima vez del patron de `page_run`).
    *LOAD_COLUMNS,
    *OFFTARGET_COLUMNS,
    "accesibilidad",
    "accesibilidad_seed",
    *FEATURE_COLUMNS,
    "veredicto",
    "score_externo",
    "fuente_score",
    *MIRARCH_COLUMNS,
    "knockdown_medido",
)

#: Las que se rellenan desde fuera y por eso van al final, juntas y vacias.
PENDIENTES = ("score_externo", "fuente_score", *MIRARCH_COLUMNS, "knockdown_medido")

CABECERA = (
    "# Tabla comparativa de shmir-design. Las columnas knockdown_medido y "
    "score_externo van\n"
    "# VACÍAS a propósito: la primera se rellena en el laboratorio, la segunda con "
    "miRarchitect\n"
    "# (ver el bloque de instrucciones del informe, o tools/import_scores.py). Un "
    "campo vacio\n"
    "# significa 'no se midio', NUNCA cero.\n"
    "# El score externo es INFORMATIVO: no es un filtro, no da PASS y no da FAIL. Las\n"
    "# columnas feat_* son las features de SplashRNA calculadas aquí, SIN combinar: "
    "una\n"
    "# feature no es un score, y aquí no se entrena ningún modelo.\n"
)


#: Las dos posiciones que NO son dato. Van en el informe y en la cabecera del TSV.
CONVENTION_NOTE = (
    "Posiciones de CONVENIO, excluidas de toda comparación de identidad:\n"
    "  · posición 1 de la guía: se fuerza una T/U para que AGO2 cargue la hebra; no "
    "viene de la diana.\n"
    "  · posición 1 de la pasajera: desapareamiento deliberado que mantiene el bulge "
    "basal; tampoco viene de la diana."
)


def coordinate_note(anatomy: Anatomy | None) -> str:
    """En que marco va cada pareja de coordenadas, y de donde salio la anatomia.

    Cuando lo que se tilo YA era un 3'UTR no hay offset, asi que `inicio_transcrito`
    sale igual que `inicio_3utr`. Los numeros estan bien; lo que no puede pasar es que
    dentro de seis meses alguien lea `inicio_transcrito = 21` y entienda que es la
    posicion 21 de un RefSeq. Aqui se dice.
    """
    lineas = [
        "inicio_3utr/fin_3utr van sobre el 3'UTR y empiezan en 1; "
        "inicio_transcrito/fin_transcrito,",
        "sobre la secuencia que se tilo.",
        "Las TRES columnas de asimetría son cantidades distintas y no se mezclan: "
        "`asimetria` es la CRUDA,",
        "`penalizacion` lo que resta la variante rara de poliadenilación (0.00 si no la "
        "hay), y",
        "`asimetria_penalizada` la NETA con la que se ordena. Darlas en una sola columna "
        "hizo que 3utr:221",
        "saliera +4.15 al lado de candidatos sin penalizar, y pareciera una discrepancia "
        "de calculo.",
        "polyA_hexamero_pos y polyA_dist_extremo3 van en el marco de LO TILADO, igual "
        "que",
        "inicio_transcrito: un hexámero en 1983 con el CDS declarado es el 1034 del "
        "3'UTR.",
    ]
    if anatomy is None:
        lineas.append(
            "La anatomía no se declaro al escribir esta tabla, así que no se puede "
            "decir que marco"
        )
        lineas.append("es el de las columnas de transcrito. Trata los dos con cuidado.")
        return "\n".join(lineas)
    lineas.append(f"Anatomia: {anatomy.source.describe()}.")
    if anatomy.cds is None:
        lineas.append(
            "AQUÍ NO HAY MARCO DE TRANSCRITO: la secuencia tilada era el 3'UTR entero, "
            "así que las"
        )
        lineas.append(
            "dos parejas coinciden y **no son coordenadas de ningún transcrito**. Para "
            "tenerlas hay"
        )
        lineas.append(
            "que resolver la anatomía con el GenBank o con las coordenadas del CDS."
        )
    return "\n".join(lineas)


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
    selection: ReportSelection,
    scaffold: ScaffoldSpec,
    *,
    anatomy: Anatomy | None = None,
    stores=None,
    species: str = "",
) -> list[list[str]]:
    """Cabecera y una fila por candidato elegido.

    Toda coordenada sale ETIQUETADA con su espacio (`3utr:449`, `tx:1398`). En la
    cabecera de la columna no basta: quien copia una celda a un correo se lleva el
    numero sin la cabecera, y `1018` en dos espacios son dos sitios distintos.

    **`stores` ENTRA POR AQUI Y NO POR CADA CONSUMIDOR** (principio nº 23). Las cuatro
    columnas del frente de off-targets —conteo por clase con su percentil— se cablearon
    a `presentation.candidate_rows` y no llegaron nunca a este TSV, que es el artefacto
    que se descarga y se discute. Se pide la referencia al MISMO sitio que la tabla de
    la pagina: dos calculos del mismo numero acaban discrepando.
    """
    # Import perezoso: `presentation` importa este modulo, asi que al reves solo puede
    # ser aqui dentro. Lo que NO se hace es reimplementar `seed_load_columns` — seria la
    # segunda definicion del mismo numero, que es el fallo que esto viene a cerrar.
    from .presentation import seed_load_columns, seed_load_reference  # noqa: PLC0415

    anatomy = anatomy or selection.anatomy
    referencia = seed_load_reference(
        stores=stores, species=species,
        starts=[c.start for c in selection.selection.chosen],
    )
    marco = tiled_frame(anatomy)
    # Cada fila convierte a 3'UTR restando el desfase. Con el tope real,
    # una resta mal hecha aborta en la fila en vez de salir en el TSV.
    tope_utr3 = bound_of(anatomy)
    elegidos = list(selection.selection.chosen)
    filtros: list[str] = []
    if elegidos:
        filtros = [r.name for r in selection.window_of(elegidos[0]).filters]

    columnas = [
        *COMPARATIVE_COLUMNS[: -len(PENDIENTES)],
        *(f"filtro:{n}" for n in filtros),
        *PENDIENTES,
    ]
    rows = [columnas]

    for choice in elegidos:
        window = selection.window_of(choice)
        hairpin = build_hairpin(window.evaluation.guide, scaffold=scaffold)
        gblock = build_gblock(hairpin)
        # `as_columns` YA etiqueta la posicion del hexamero con el marco de lo tilado.
        # Aqui habia una tercera copia de esa etiqueta —TSV, tabla comparativa y nadie en
        # la tabla de la pagina—, y las dos que existian volvian a parsear el entero con
        # `int()`. Tres sitios haciendo lo mismo: uno se olvidaba y los otros dos se
        # rompen en cuanto el primero deja de emitir un entero desnudo, que es
        # exactamente lo que paso.
        polya = window.polya.as_columns() if window.polya else dict.fromkeys(POLYA_COLUMNS, "")
        especificidad = _mismatch_counts(window.especificidad_detalle)

        fila = {
            "inicio_3utr": label(window.inicio_3utr, Frame.UTR3, limit=tope_utr3),
            "fin_3utr": label(window.fin_3utr, Frame.UTR3, limit=tope_utr3),
            "inicio_transcrito": label(window.window.start, marco),
            "fin_transcrito": label(window.window.end, marco),
            "region": window.region.value,
            "tercio": window.tercio.value if window.tercio else "",
            "diana": window.evaluation.sequence,
            "guia": window.evaluation.guide,
            "pasajera": hairpin.passenger.sequence,
            "gblock_149": gblock.sequence,
            "GC": f"{_gc(window.evaluation.sequence):.3f}",
            "asimetria": (
                "" if choice.asymmetry_raw is None else f"{choice.asymmetry_raw:+.2f}"
            ),
            "penalizacion": f"{choice.penalty:.2f}",
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
            **(
                window.carga_seed.as_columns() if window.carga_seed is not None
                else dict.fromkeys(LOAD_COLUMNS, "")
            ),
            **seed_load_columns(
                stores=stores, species=species, start=choice.start,
                reference=referencia,
            ),
            "accesibilidad": (
                window.accesibilidad.as_column()
                if window.accesibilidad is not None
                else ""
            ),
            "accesibilidad_seed": _seed_access(window),
            **splashrna_features(window.evaluation.guide),
            "veredicto": window.verdict.value,
            # Vacias las dos: nadie ha puntuado esta guia. `ExternalScore()` sin
            # argumentos es la forma de decirlo, y no hay ninguna rama que rellene
            # esto con una cuenta local (ver `external_score.py`).
            **ExternalScore().as_columns(),
            # Vacias hasta que `tools/import_scores.py` cruce una fuente externa. Aqui
            # no se calcula ninguna: no hay forma de saber que dice miRarchitect sin
            # preguntarselo a miRarchitect.
            **dict.fromkeys(MIRARCH_COLUMNS, ""),
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
    selection: ReportSelection,
    scaffold: ScaffoldSpec,
    *,
    with_header: bool = False,
    anatomy: Anatomy | None = None,
    stores=None,
    species: str = "",
) -> str:
    """La tabla en TSV. `with_header` añade los comentarios que la explican.

    **`anatomy` NO se reenviaba**, y los dos llamadores la pasan: se caia siempre a la
    anatomia que trae la propia seleccion. Hoy son la misma, asi que no habia sintoma — pero era un
    argumento inerte, que es lo que hace que nadie vuelva a mirarlo (errata nº 32).
    """
    cuerpo = "\n".join(
        "\t".join(fila)
        for fila in comparative_rows(
            selection, scaffold, anatomy=anatomy, stores=stores, species=species,
        )
    )
    if not with_header:
        return cuerpo
    nota = "".join(
        f"# {l}\n"
        for l in (coordinate_note(anatomy) + "\n" + CONVENTION_NOTE).splitlines()
    )
    return CABECERA + nota + cuerpo


#: Columnas que se enseñan en el bloque legible del informe. La tabla entera no cabe en
#: una consola, asi que el informe da las que sirven para decidir y el TSV lo trae todo.
RESUMEN_COLUMNS = (
    "inicio_transcrito",
    "inicio_3utr",
    "region",
    "tercio",
    "GC",
    "asimetria",
    "penalizacion",
    "asimetria_penalizada",
    "polyA_solapa_seed",
    "riesgo_APA",
    # EN EL RESUMEN VA UNA SOLA CLASE, la que mas discrimina, y con su nombre completo:
    # meter las siete columnas de este eje en un bloque alineado lo haria ilegible, y
    # meter un total volveria a ser la suma prohibida.
    "carga_8mer",
    "accesibilidad",
    "veredicto",
)


def comparative_text(
    selection: ReportSelection,
    scaffold: ScaffoldSpec,
    *,
    anatomy: Anatomy | None = None,
    stores=None,
    species: str = "",
) -> str:
    """Bloque legible: las columnas que sirven para decidir, alineadas."""
    filas = comparative_rows(
        selection, scaffold, anatomy=anatomy, stores=stores, species=species,
    )
    if len(filas) < 2:
        return "  (no hay candidatos seleccionados)"
    indices = [filas[0].index(c) for c in RESUMEN_COLUMNS]
    anchos = [
        max(len(RESUMEN_COLUMNS[i]), *(len(f[indice]) for f in filas[1:]))
        for i, indice in enumerate(indices)
    ]
    lineas = [
        "  " + "  ".join(
            c.ljust(a) for c, a in zip(RESUMEN_COLUMNS, anchos, strict=True)
        )
    ]
    for fila in filas[1:]:
        lineas.append(
            "  "
            + "  ".join(
                fila[i].ljust(a) for i, a in zip(indices, anchos, strict=True)
            )
        )
    lineas.append(
        "  La tabla COMPLETA —con la pasajera, el módulo de 149 nt, los cinco campos de"
    )
    lineas.append(
        "  polyA, los recuentos de especificidad y una columna por filtro— está en el "
        "TSV comparativo,"
    )
    lineas.append(
        "  con la columna knockdown_medido vacía para que vuelva rellena del "
        "laboratorio."
    )
    lineas.extend(f"  {l}" for l in coordinate_note(anatomy).splitlines())
    return "\n".join(lineas)
