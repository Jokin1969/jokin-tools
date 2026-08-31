"""El informe como DOCUMENTO: parcial o completo, y en un solo modelo.

No son dos productos. Es el mismo documento en distintos grados de completitud: si hay
frentes sin cerrar sale marcado `PARCIAL` con esos frentes señalados, y cuando esten
todos cerrados sale `COMPLETO`. El boton esta disponible en cualquier momento — un
informe que solo se puede sacar al final no sirve para trabajar.

**Tiene que leerse sin la app delante y sin haber estado en las conversaciones.** De ahi
las siete secciones y las tres reglas de redaccion, que son las que se comprueban con
tests:

1. **Ningun umbral sin justificar.** Cada uno dice si viene de literatura, de convencion
   declarada o de una decision nuestra (`justificacion.py`), y los que no tienen base
   medida —el flanco de ±10 nt del eje esterico— lo dicen expresamente.
2. **Toda cifra comparativa lleva su referencia.** La tasa base junto a las colisiones de
   seed; el percentil junto a la carga de off-targets. Un numero sin referencia no es
   interpretable.
3. **`NOT_RUN` visible en el CUERPO**, nunca solo en un anexo.

Un solo modelo y tres salidas: markdown (fuente unica y lo que entra en el golden),
`.docx` y `.pdf`. Los dos formatos son entregables; el markdown es de donde salen.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ShmirDesignError

#: Los dos grados de completitud. No son dos documentos.
STATES = ("PARCIAL", "COMPLETO")

BLOCK_KINDS = ("heading", "para", "bullets", "table", "warning", "pre")

WHAT_PARTIAL_MEANS = (
    "ESTE INFORME ES PARCIAL. No es un borrador ni una versión reducida: es el mismo "
    "documento con frentes todavia abiertos, y cada uno sale marcado con lo que le falta "
    "y donde conseguirlo. Un candidato con cualquier frente en NOT_RUN es INCOMPLETE, "
    "nunca aprobado — no haber comprobado algo no es haberlo comprobado y que salga bien."
)

WHAT_COMPLETE_MEANS = (
    "Todos los frentes tienen veredicto. Eso NO quiere decir que todos hayan salido "
    "bien: quiere decir que ninguno se quedo sin correr."
)

READING_NOTE = (
    "COMO SE LEE ESTO. Cada filtro emite uno de cuatro estados: PASS (corrió y el "
    "candidato lo supera), FAIL (corrió y no lo supera), NOT_RUN (NO LLEGO A CORRER — es "
    "una laguna, no un aprobado) y NO_APLICA (esa pregunta no se le hace a ese "
    "candidato). Un número comparativo que no se calculo va VACÍO, nunca a cero: no "
    "haber contado y contar cero son cosas distintas."
)


@dataclass(frozen=True)
class Block:
    kind: str
    text: str = ""
    level: int = 2
    items: tuple[str, ...] = ()
    headers: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in BLOCK_KINDS:
            raise ValueError(
                f"Bloque de tipo {self.kind!r} desconocido; los que hay son "
                f"{', '.join(BLOCK_KINDS)}. Se aborta."
            )
        if self.kind == "table":
            anchos = {len(f) for f in self.rows}
            if anchos and anchos != {len(self.headers)}:
                raise ValueError(
                    f"Tabla con {len(self.headers)} cabecera(s) y filas de "
                    f"{sorted(anchos)} celda(s). Se aborta: una fila descuadrada "
                    f"desplaza los valores a la columna de al lado y eso no da ningún "
                    f"error, solo un informe equivocado."
                )


def heading(text: str, level: int = 2) -> Block:
    return Block(kind="heading", text=text, level=level)


def para(text: str) -> Block:
    return Block(kind="para", text=text)


def bullets(items) -> Block:
    return Block(kind="bullets", items=tuple(items))


def table(headers, rows) -> Block:
    return Block(
        kind="table",
        headers=tuple(headers),
        rows=tuple(tuple(str(c) for c in fila) for fila in rows),
    )


def warning(text: str) -> Block:
    return Block(kind="warning", text=text)


def pre(text: str) -> Block:
    return Block(kind="pre", text=text)


@dataclass(frozen=True)
class Section:
    number: int
    title: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class Document:
    title: str
    state: str
    generated: str
    sections: tuple[Section, ...]
    open_fronts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError(
                f"Estado {self.state!r} desconocido; los que hay son "
                f"{', '.join(STATES)}. Se aborta."
            )
        if self.state == "PARCIAL" and not self.open_fronts:
            raise ValueError(
                "Un informe PARCIAL sin ningún frente abierto no tiene sentido: o esta "
                "completo o hay que decir cual falta. Se aborta."
            )
        if self.state == "COMPLETO" and self.open_fronts:
            raise ValueError(
                f"Un informe COMPLETO no puede tener frentes abiertos y trae "
                f"{', '.join(self.open_fronts)}. Se aborta: presentarlo como completo "
                f"sería decir que se comprobo algo que no se comprobo."
            )

    def section(self, number: int) -> Section:
        for seccion in self.sections:
            if seccion.number == number:
                return seccion
        raise ShmirDesignError(
            f"El informe no tiene seccion {number}; tiene "
            f"{', '.join(str(s.number) for s in self.sections)}."
        )

    def markdown(self) -> str:
        lineas = [
            f"# {self.title}",
            "",
            f"**Estado del informe: {self.state}** · generado {self.generated}",
            "",
            WHAT_PARTIAL_MEANS if self.state == "PARCIAL" else WHAT_COMPLETE_MEANS,
            "",
        ]
        if self.open_fronts:
            lineas.extend([
                "Frentes abiertos: " + ", ".join(self.open_fronts) + ".",
                "",
            ])
        lineas.extend([READING_NOTE, ""])
        for seccion in self.sections:
            lineas.append(f"## {seccion.number}. {seccion.title}")
            lineas.append("")
            for bloque in seccion.blocks:
                lineas.extend(_markdown_block(bloque))
        return "\n".join(lineas).rstrip() + "\n"


def _markdown_block(block: Block) -> list[str]:
    if block.kind == "heading":
        return [f"{'#' * min(block.level, 6)} {block.text}", ""]
    if block.kind == "para":
        return [block.text, ""]
    if block.kind == "warning":
        return [f"> **{block.text}**", ""]
    if block.kind == "bullets":
        return [f"- {i}" for i in block.items] + [""]
    if block.kind == "pre":
        return ["```", *block.text.rstrip("\n").splitlines(), "```", ""]
    cabecera = "| " + " | ".join(block.headers) + " |"
    separador = "|" + "|".join("---" for _ in block.headers) + "|"
    filas = ["| " + " | ".join(c.replace("|", "/") for c in f) + " |" for f in block.rows]
    return [cabecera, separador, *filas, ""]


# ────────────────────────────── construccion del documento ─────────────────────────

#: Que umbrales se imprimen con cada frente. Un frente que no lleve ninguno lo dice:
#: «no tiene umbral» es informacion, y dejar la fila vacia parecia un olvido.
_FRONT_THRESHOLDS = {
    "especificidad": (),
    "transgen": ("transgene_mismatches",),
    "repeticiones": (),
    "repeticion_polimorfica": (),
    "seed": ("seed_window",),
    "seed_colision": ("seed_window",),
    "offtarget_seed": ("seed_window", "null_draws"),
    "fraccion_isoforma_larga": ("cleavage_band", "polya_flank"),
    "empalme_intron": ("kozak", "splice_acceptor"),
    "empalme_sitios": (),
}

#: Frentes cuyo criterio es RELATIVO y no absoluto. Decir de ellos que «no tienen
#: umbral numerico» seria otra media verdad: lo tienen, y lo que no existe es el
#: absoluto — que en el cuarto modal es justo el punto.
RELATIVE_CRITERION = {
    "empalme_sitios": (
        "Este frente NO tiene umbral ABSOLUTO, y no se puede inventar uno: SpliceAI se "
        "entreno sobre secuencia genomica humana con ventana de 10.000 nt para predecir "
        "el efecto de variantes, y un cassette de AAV no se le parece. Lo que si tiene es "
        "un umbral RELATIVO declarado: solo se listan los sitios que llegan al 5 % de la "
        "puntuación del DONANTE LEGÍTIMO del mismo intrón en la MISMA corrida. Ese "
        "referente interno es lo único que hace interpretable el número — el mismo "
        "criterio con el que ya se descartaron los aceptores crípticos, comparando su "
        "tracto de pirimidinas contra las nueve del legítimo."
    ),
}

#: Frentes que NO se contestan con un fichero: se contestan en el banco.
BENCH_FRONTS = frozenset({"empalme_intron"})

#: Frentes cuyo dato se SUBE en su modal en vez de venir del informe de tilado.
UPLOADED_FRONTS = {
    "empalme_sitios": (
        "el resultado de SpliceAI sobre las construcciones, subido por su modal. No sale "
        "del informe de tilado porque la unidad de ese frente es el par candidato x "
        "intrón, no la ventana"
    ),
}

#: De donde sale el dato de cada frente, dentro del informe de tilado.
_FRONT_SOURCE_ATTR = {
    "especificidad": "specificity_db",
    "transgen": "transgene_db",
    "repeticiones": "mask",
    "repeticion_polimorfica": "mask",
    "seed": "seeds",
    "seed_colision": "mature",
    "offtarget_seed": "utr3_set",
    "fraccion_isoforma_larga": "measured_apa",
    "empalme_intron": None,
}

BIOPHYSICAL_NOTE = (
    "Los seis filtros biofísicos de ventana NO dependen de ningún fichero ni de ninguna "
    "especie: corren siempre. Por eso no son un «frente» — no hay nada que conseguir "
    "para cerrarlos. Sus umbrales si necesitan justificarse igual que los demas."
)


def _describe_source(objeto) -> str:
    if objeto is None:
        return (
            "NINGUNA CARGADA. El frente queda NOT_RUN — que no es PASS y no es cero."
        )
    for atributo in ("provenance",):
        valor = getattr(objeto, atributo, None)
        if isinstance(valor, str) and valor.strip():
            return valor
    describe = getattr(objeto, "describe", None)
    if callable(describe):
        salida = describe()
        return salida if isinstance(salida, str) else " · ".join(salida)
    fuente = getattr(objeto, "source", "")
    return str(fuente) if fuente else "cargada (sin procedencia declarada)"


def _threshold_rows(claves):
    from .justificacion import threshold

    filas = []
    for clave in claves:
        umbral = threshold(clave)
        filas.append(
            (
                umbral.label,
                umbral.value,
                umbral.origin,
                umbral.rationale
                + (
                    f"  ⚠ SIN BASE MEDIDA: {umbral.no_measured_basis}"
                    if umbral.no_measured_basis else ""
                ),
            )
        )
    return filas


_THRESHOLD_HEADERS = ("umbral", "valor", "origen", "de donde sale")


def _section_1(*, species, tiling, generated, anatomy_source) -> Section:
    filas = [
        (
            "secuencia analizada",
            f"{tiling.sequence_length} nt / {tiling.sequence_md5}",
        ),
        ("especie declarada", species),
        ("anatomia", anatomy_source),
        ("ventanas tiladas", str(len(tiling.windows))),
        ("tamaño de ventana", f"{tiling.window_size} nt"),
        ("fecha del informe", generated),
    ]
    return Section(
        number=1,
        title="Que se analizo",
        blocks=(
            para(
                "Longitud y md5 van JUNTOS a propósito: «referencia 1246 nt» parece "
                "razonable a solas, y pegado al md5 no hay forma de leerlo sin ver que "
                "lo que se llama referencia no es lo que se cree. Es la contramedida de "
                "una errata real."
            ),
            table(("campo", "valor"), filas),
        ),
    )


def _section_2(fronts, *, species) -> Section:
    from .obtencion import resolve_ficha
    from .species import resolve

    especie = resolve(species)
    filas = []
    for frente in fronts:
        ficha = resolve_ficha(frente.name, species=especie)
        if ficha.no_file:
            falta = "no se cierra con ningún fichero (banco)"
        else:
            falta = ", ".join(f.name for f in ficha.files if f.required)
        filas.append(
            (
                frente.name,
                "NOT_RUN" if frente.blocking else "CERRADO",
                falta if frente.blocking else "—",
                f"{ficha.source} ({ficha.url})" if frente.blocking else "—",
            )
        )
    abiertos = [f for f in fronts if f.blocking]
    bloques = [
        para(
            "Un frente es una pregunta que hay que contestar antes de pedir oligo. Los "
            "cerrados NO desaparecen del informe: sin ellos, el siguiente lector no "
            "sabria si se resolvieron o si nadie los miro."
        ),
        table(("frente", "estado", "que falta", "donde se consigue"), filas),
    ]
    if abiertos:
        bloques.append(
            warning(
                f"{len(abiertos)} frente(s) en NOT_RUN. No se pide oligo hasta que "
                f"todos tengan veredicto. Que uno se arregle con un fichero de "
                f"kilobytes y otro necesite ir al banco no cambia nada: los dos "
                f"bloquean igual."
            )
        )
    sin_fichero = [
        f for f in abiertos
        if resolve_ficha(f.name, species=especie).no_file
    ]
    if sin_fichero:
        bloques.append(
            para(
                "Y hay una categoría aparte: "
                + ", ".join(f.name for f in sin_fichero)
                + " NO se cierra con ningún fichero. Conseguir más datos no lo resuelve;"
                " hay que ir al laboratorio. Se dice aparte para que no parezca que "
                "basta con descargar algo."
            )
        )
    return Section(number=2, title="Estado de los frentes", blocks=tuple(bloques))


def _section_3(fronts, *, species, tiling) -> Section:
    from .justificacion import THRESHOLDS
    from .obtencion import resolve_ficha
    from .species import resolve

    especie = resolve(species)
    bloques = [
        para(
            "Por cada frente: que mide, por que importa, con que criterio se decide y de "
            "donde sale cada umbral, con que datos se ha contestado, y el resultado."
        ),
        heading("Filtros biofísicos de ventana (no son un frente)", level=3),
        para(BIOPHYSICAL_NOTE),
        table(
            _THRESHOLD_HEADERS,
            _threshold_rows(tuple(u.key for u in THRESHOLDS if u.key != "polya_flank")),
        ),
    ]
    for frente in fronts:
        ficha = resolve_ficha(frente.name, species=especie)
        estado = "NOT_RUN" if frente.blocking else "CERRADO"
        # OJO: `.get()` devolvia `None` para un frente DESCONOCIDO, y `None` ya
        # significaba «de banco». Asi que un frente nuevo heredaba en silencio el texto
        # «no se contesta con datos, sino en el banco» — plausible y FALSO. Lo cazo el
        # diff del golden al añadir el cuarto modal. Ahora un frente sin declarar ABORTA.
        if frente.name in BENCH_FRONTS:
            fuente = "ninguna: este frente no se contesta con datos, sino en el banco"
        elif frente.name in UPLOADED_FRONTS:
            fuente = UPLOADED_FRONTS[frente.name]
        elif frente.name in _FRONT_SOURCE_ATTR:
            fuente = _describe_source(
                getattr(tiling, _FRONT_SOURCE_ATTR[frente.name], None)
            )
        else:
            raise ShmirDesignError(
                f"El frente {frente.name!r} no está declarado en `informe_doc`: no se "
                f"sabe de donde sale su dato. Se aborta en vez de escribir el texto de "
                f"otro frente — un «no se contesta con datos, sino en el banco» sobre un "
                f"frente que SI se cierra con un fichero es plausible y falso, y eso "
                f"cuesta más que no decir nada. Añadelo a `BENCH_FRONTS`, a "
                f"`UPLOADED_FRONTS` o a `_FRONT_SOURCE_ATTR`."
            )
        claves = _FRONT_THRESHOLDS.get(frente.name, ())
        bloques.extend([
            heading(f"{frente.name} — {estado}", level=3),
            para(f"**Que mide.** {ficha.question}"),
            para(f"**Por que importa / resultado.** {frente.reason}"),
            para(f"**Fuente de datos.** {fuente}"),
        ])
        if claves:
            bloques.append(table(_THRESHOLD_HEADERS, _threshold_rows(claves)))
        elif frente.name in RELATIVE_CRITERION:
            # Decir «no tiene umbral numerico» de un frente que SI tiene uno, solo que
            # relativo, es otra media verdad. Y en este caso la distincion es todo el
            # frente: lo que NO existe es el umbral ABSOLUTO.
            bloques.append(para(f"**Criterio.** {RELATIVE_CRITERION[frente.name]}"))
        else:
            bloques.append(
                para(
                    "**Criterio.** Este frente no tiene umbral numérico: su veredicto es "
                    "una comprobación, no una comparación contra un corte."
                )
            )
        if frente.blocking:
            bloques.append(
                para("**Como se cierra.** (ficha de obtencion, integra)")
            )
            bloques.append(pre(ficha.render()))
    return Section(number=3, title="Frente por frente", blocks=tuple(bloques))


def _section_4(selection) -> Section:
    from .presentation import candidate_rows

    filas = candidate_rows(selection)
    if not filas:
        return Section(
            number=4,
            title="Tabla de candidatos",
            blocks=(
                warning(
                    "Ningún candidato con estos umbrales. No es un error del informe: "
                    "es el resultado."
                ),
            ),
        )
    from .offtarget import MULTIPLEX_NOTE, core_conflicts

    cabeceras = tuple(filas[0])
    bloques = [
        para(
            "Todas las columnas, con un estado POR FILTRO. No se colapsan ni se "
            "omiten los que no corrieron: un filtro ausente de la tabla es "
            "indistinguible de uno superado."
        ),
        table(cabeceras, [tuple(str(f[c]) for c in cabeceras) for f in filas]),
    ]
    from .coords import Frame, frame_of, label as etiqueta

    marco = frame_of(selection.anatomy) if selection.anatomy is not None else Frame.UTR3
    conflictos = core_conflicts(selection)
    if conflictos:
        bloques.append(warning("MULTIPLEXADO: hay candidatos que comparten núcleo."))
        bloques.append(
            bullets([
                c.describe(
                    label_a=etiqueta(c.a, marco), label_b=etiqueta(c.b, marco)
                )
                for c in conflictos
            ])
        )
        bloques.append(para(MULTIPLEX_NOTE))
    else:
        bloques.append(
            para(
                "MULTIPLEXADO: ninguna pareja del panel comparte el núcleo de seed de "
                "6 nt. Se dice aunque salga limpio — su ausencia se leeria como que "
                "nadie lo miro."
            )
        )
    return Section(number=4, title="Tabla de candidatos", blocks=tuple(bloques))


def _section_5(*, species, tiling, selection, starts, target=None) -> Section:
    from .dossier import build_dossier

    bloques = [
        para(
            "Una ficha por candidato seleccionado, con el veredicto de CADA frente, su "
            "procedencia y su fecha."
        )
    ]
    for inicio in starts:
        ficha = build_dossier(
            species=species, tiling=tiling, selection=selection, start=inicio,
            target=target,
        )
        bloques.append(heading(f"3utr:{inicio}", level=3))
        bloques.append(pre(ficha.render()))
    return Section(number=5, title="Fichas de los seleccionados", blocks=tuple(bloques))


def _section_6() -> Section:
    from .justificacion import unmeasured
    from .offtarget import LIMITATIONS, UPPER_BOUND_NOTE
    from .seed_load import WHY_NOT_BLAST

    bloques = [
        para(
            "Seccion propia y no un pie: una limitacion al pie se lee después de haber "
            "creido el número."
        ),
        heading("Umbrales SIN base medida", level=3),
        para(
            "Estos no salen de ninguna medida. Se declaran como convenio o como decisión "
            "de este proyecto, y presentarlos junto a los que si tienen base sin "
            "distinguirlos les atribuiria una precisión que no tienen."
        ),
        table(
            ("umbral", "valor", "por que no tiene base medida"),
            [(u.label, u.value, u.no_measured_basis) for u in unmeasured()],
        ),
        heading("La carga de off-targets es un LÍMITE SUPERIOR", level=3),
        table(
            ("limitacion", "direccion", "detalle"),
            [(l.title, l.direction, l.text) for l in LIMITATIONS],
        ),
        warning(UPPER_BOUND_NOTE),
        heading("La especificidad no cubre los off-targets por seed", level=3),
        para(WHY_NOT_BLAST),
        heading("La accesibilidad es DESEMPATE, nunca filtro", level=3),
        para(
            "Es el criterio peor predicho del pipeline. Se calculan dos ventanas de "
            "contexto (±80 y ±150) y si discrepan, el número no sirve ni para desempatar."
        ),
        heading("La asimetría usa un PROXY, no una energía libre de duplex", level=3),
        para(
            "Ordena candidatos entre si; no es una magnitud fisica y no se debe leer "
            "como tal. Su especificación tuvo un error de signo que ningún test de "
            "consistencia interna habría detectado, así que hay dos tests de cordura "
            "biologica que fijan los signos."
        ),
        heading("Un frente que no se cierra con ningún fichero", level=3),
        para(
            "El empalme del intrón es BINARIO y solo se contesta en el banco. Y la "
            "lectura que se hace por defecto NO lo coge: un small RNA-seq puede salir "
            "perfecto con el empalme fallando, porque Drosha procesa el pri-miR "
            "cotranscripcionalmente — o sea ANTES del splicing. Un shmiR correcto no es "
            "evidencia de que haya proteina."
        ),
    ]
    return Section(number=6, title="Limitaciones", blocks=tuple(bloques))


def _section_7(tiling, *, extra=()) -> Section:
    filas = []
    for etiqueta, atributo in (
        ("máscara de repetitivos", "mask"),
        ("maduros de miRBase", "mature"),
        ("tabla de seeds", "seeds"),
        ("base de especificidad", "specificity_db"),
        ("casete del transgén", "transgene_db"),
        ("3'UTR del transcriptoma", "utr3_set"),
        ("APA medido", "measured_apa"),
        ("lista ampliada de abundancia", "abundance"),
    ):
        filas.append((etiqueta, _describe_source(getattr(tiling, atributo, None))))
    filas.extend(tuple(extra))
    return Section(
        number=7,
        title="Procedencia",
        blocks=(
            para(
                "Todos los ficheros que entraron, con versión y md5. Sin esto un "
                "veredicto no es auditable dentro de un año — que es la razón por la que "
                "el manifiesto se versiona en texto."
            ),
            table(("recurso", "procedencia"), filas),
        ),
    )


def _seccion_anatomia(anatomy) -> Section:
    """La anatomía del transcrito, la MISMA tabla que pinta la página.

    Sale de `presentation.anatomy_rows`, no de una copia: si la página gana una columna,
    el informe la gana con ella. Dos tablas para lo mismo divergen — y aquí el que
    diverge es el que acaba en una libreta de laboratorio.
    """
    from .presentation import anatomy_rows  # noqa: PLC0415

    filas = anatomy_rows(None, utr3_length=anatomy.utr3_length, anatomy=anatomy)
    return Section(
        number=0,   # lo asigna `build_document` por POSICION; ver `_numerar`.
        title="Anatomía del transcrito",
        blocks=(
            para(
                "De dónde sale cada frontera. La procedencia de la anotación importa "
                "tanto como el número: una frontera declarada y una anotada no "
                "sostienen lo mismo."
            ),
            table(tuple(filas[0]), tuple(tuple(str(f[c]) for c in filas[0]) for f in filas)),
        ),
    )


def _seccion_mapa(tiling, selection) -> Section:
    """El mapa del 3'UTR. En el PDF va su RESUMEN, no el SVG.

    El PDF es monoespaciado: mil coordenadas con decimales no se leen. Lo que entra es
    el conteo por tipo y la leyenda —lo mismo que se fija en el golden—, que es lo que
    permite ver que un mapa se quedó sin candidatos o dibuja el triple de señales.
    """
    from .presentation import _mapa_resumen, map_svg  # noqa: PLC0415

    lineas = _mapa_resumen(map_svg(tiling, selection))
    return Section(
        number=0,
        title="Mapa del 3'UTR",
        blocks=(
            para(
                "Resumen del mapa: cuántos elementos dibuja por tipo, y su leyenda. El "
                "dibujo entero se ve en la página; aquí va lo que se puede leer en "
                "monoespaciado y comparar entre dos corridas."
            ),
            pre("\n".join(lineas)),
        ),
    )


def _seccion_elegibles(tiling, selection, *, species: str) -> Section:
    """Todos los sitios elegibles, con UNA COLUMNA POR FRENTE.

    Es la vista que impide que vuelva a pasar lo de `offtarget_seed`: un frente sin
    columna no se ve, y lo que no se ve no existe. Las columnas se derivan de los frentes
    que el informe conoce, así que uno nuevo aparece solo — también aquí.
    """
    from .presentation import site_table_rows  # noqa: PLC0415

    filas = site_table_rows(tiling, selection, species=species)
    if not filas:
        return Section(
            number=0,
            title="Todos los sitios elegibles",
            blocks=(para("Ningún sitio elegible con estos umbrales."),),
        )
    return Section(
        number=0,
        title=f"Todos los sitios elegibles, con una columna por frente — {species}",
        blocks=(
            para(
                "Todos, no sólo los seleccionados: la selección es una propuesta y esta "
                "tabla es el conjunto sobre el que se hizo. Una columna por frente, "
                "derivada de los frentes que el informe conoce."
            ),
            table(tuple(filas[0]), tuple(tuple(str(f[c]) for c in filas[0]) for f in filas)),
        ),
    )


def _numerar(secciones: tuple[Section, ...]) -> tuple[Section, ...]:
    """Numera las secciones POR POSICION, no por lo que cada una traiga escrito.

    Estaban numeradas a mano, una a una, y eso hace que insertar una en medio obligue a
    tocar todas las de detras — y el dia que alguien no las toque, el informe tiene dos
    secciones «4». El numero es una CONSECUENCIA del orden, asi que se deriva de el.
    """
    from dataclasses import replace  # noqa: PLC0415

    return tuple(
        replace(seccion, number=indice)
        for indice, seccion in enumerate(secciones, start=1)
    )


def build_document(
    *, species: str, tiling, selection, generated: str,
    anatomy_source: str = "no declarada en esta corrida",
    dossier_starts=None, extra_provenance=(), title: str | None = None,
    target: str | None = None, anatomy=None,
) -> Document:
    """El informe entero. Parcial o completo segun los frentes, nunca dos documentos."""
    from .selection import blocking_fronts

    frentes = blocking_fronts(tiling, selection)
    abiertos = tuple(f.name for f in frentes if f.blocking)
    if dossier_starts is None:
        dossier_starts = tuple(c.start for c in selection.selection.chosen)
    return Document(
        title=title or f"Diseño de shmiR — {species}",
        state="PARCIAL" if abiertos else "COMPLETO",
        generated=generated,
        open_fronts=abiertos,
        sections=_numerar((
            _section_1(
                species=species, tiling=tiling, generated=generated,
                anatomy_source=anatomy_source,
            ),
            _section_2(frentes, species=species),
            _section_3(frentes, species=species, tiling=tiling),
            *((_seccion_anatomia(anatomy),) if anatomy is not None else ()),
            _seccion_mapa(tiling, selection),
            _section_4(selection),
            _seccion_elegibles(tiling, selection, species=species),
            _section_5(
                species=species, tiling=tiling, selection=selection,
                starts=tuple(dossier_starts), target=target,
            ),
            _section_6(),
            _section_7(tiling, extra=extra_provenance),
        )),
    )
