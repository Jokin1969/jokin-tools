"""El CUARTO modal: prediccion de sitios de splicing sobre el cassette montado.

## En que se diferencia de los otros tres

**La unidad de analisis NO es el candidato.** Los otros tres preguntan sobre una guia de
22 nt; este pregunta sobre el **cassette montado**: intron completo, con su modulo dentro,
con la guia y la pasajera de ESE candidato, y con contexto exonico a los dos lados. Diez
candidatos y tres intrones son **treinta consultas**, no una lista de diez.

## SpliceAI NO fue entrenado para esto, y eso manda sobre todo lo demas

Se entreno sobre secuencia **genomica humana** con ventana de **10.000 nt** para predecir
el **efecto de variantes**. Un cassette de AAV no se le parece: no hay contexto genomico,
las longitudes son atipicas y la composicion tambien. Consecuencias, y van ANTES del
boton, no al pie:

  - las puntuaciones **absolutas no son interpretables**. No hay umbral que aplicar;
  - solo vale la comparacion **relativa** contra un referente **interno**: el donante
    legitimo del mismo intron, en la misma corrida. Es el mismo criterio que ya se uso
    para descartar los 13 aceptores cripticos comparandolos contra el tracto de 9
    pirimidinas del legitimo;
  - un modulo cuyo mejor criptico se **acerque** al legitimo es sospechoso; uno donde el
    legitimo **domine**, no. **Nada de esto es un veredicto.**

## Y sobre la orden: no se inventa

Este proyecto no ha verificado la invocacion de SpliceAI (regla 4 generalizada: si no lo
has comprobado, no lo escribas — pregunta). Asi que `LocalCommand` **recibe** la orden y
aborta sin ella, igual que `blast.RemoteApi` con su endpoint. Lo que si define este modulo
es el **formato del resultado que acepta**, que es nuestro.

Lo que SI hay desde el 2026-09-05 es la **procedencia de una corrida real**
(`VERIFIED_INVOCATION`): SpliceAI 1.3 en conda, llamado como **libreria desde Python** —no
el ejecutable `spliceai`, que anota variantes sobre un genoma y no aplica—, cinco modelos
promediados y ventana de 10.000 con relleno de N. **Eso no es una orden ejecutable y no se
usa como tal**: el script vive en la maquina de quien lo corrio y no esta aqui. Es lo que
permite comparar la siguiente corrida con esta, que es justo lo que faltaba.

## Dos convenciones de posicion, y la que nos costo un resultado

La app apunta a la **G de GT** y a la **A de AG**; SpliceAI apunta a la **ultima base
exonica** y a la **primera base exonica**. Ver el bloque `POSITION_CONVENTION_NOTE`: es la causa
entera de que un analisis de 107.680 filas se normalizara contra `2e-07`.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .blocks import PIECES, build_block
from .errors import ShmirDesignError
from .filters import FilterState
from .introns import get as get_intron
from .introns import locate_elements
from .splicing import CRYPTIC_DONOR

# ─────────────────────────── lo que se dice ANTES del boton ───────────────────────────

NOT_TRAINED_FOR_THIS = (
    "SpliceAI NO fue entrenado para esto. Se entreno sobre secuencia GENOMICA HUMANA con "
    "una ventana de 10.000 nt, para predecir el efecto de VARIANTES. Un cassette de AAV "
    "no se le parece: no hay contexto genomico, las longitudes son atipicas y la "
    "composición también. Lo que devuelve aquí no es «lo mismo peor»: es un número "
    "calculado sobre una entrada de otra clase."
)

NO_ABSOLUTE_THRESHOLD = (
    "LAS PUNTUACIONES ABSOLUTAS NO SON INTERPRETABLES, y no hay ningún umbral que "
    "aplicar. Un 0,8 aquí no significa lo que significa un 0,8 en el genoma humano, y no "
    "existe un valor por encima del cual algo sea «un sitio». Cualquier corte que se "
    "pusiera sería inventado."
)

RELATIVE_ONLY = (
    "Lo único que vale es la comparación RELATIVA contra un referente INTERNO: el donante "
    "legítimo del mismo intrón, en la misma corrida. Es el mismo criterio que ya se uso "
    "para descartar los aceptores crípticos —el tracto de pirimidinas de cada uno "
    "comparado contra las nueve del legítimo— y funciona por la misma razón: el veredicto "
    "no depende de ningún umbral traido de fuera. Un módulo cuyo mejor críptico se ACERQUE "
    "al legítimo es sospechoso; uno donde el legítimo DOMINE, no."
)

CONTEXT_MATTERS = (
    "LA VENTANA DE CONTEXTO CAMBIA EL RESULTADO, así que va declarada y viaja con cada "
    "consulta. SpliceAI mira miles de nucleótidos a cada lado; aquí hay lo que da el "
    "casete. Dos corridas con contextos distintos no son comparables, y sin registrarlo "
    "nadie podría saberlo."
)

USE_NOTE = (
    "USO: DESEMPATE Y ALERTA, NUNCA FILTRO. Ni esto ni la accesibilidad estructural "
    "pueden excluir un candidato — NO ES UN VEREDICTO. Lo que pueden hacer es señalar que "
    "una construcción concreta tiene un perfil peor que sus hermanas, y eso es motivo "
    "para preferir otra o para llevar las dos."
)

WHAT_IS_ACTIONABLE = (
    "LO ACCIONABLE es que guías introducen crípticos que las otras NO. Si nueve dan un "
    "perfil limpio y una no, esa una se CAMBIA. Es una comparación ENTRE CONSTRUCCIONES, "
    "no contra un umbral absoluto — que es justo lo que aquí no se puede usar."
)

#: Umbral RELATIVO por debajo del cual un sitio no se lista. DECLARADO como parametro de
#: este analisis, NO citado: no sale de ninguna publicacion. Existe para que la tabla no
#: se llene de ruido, no para decidir nada.
RELATIVE_THRESHOLD = 0.05

RELATIVE_THRESHOLD_NOTE = (
    f"Solo se listan los sitios cuya puntuación llega al {RELATIVE_THRESHOLD:.0%} de la "
    f"del donante legítimo. Es un umbral RELATIVO y va DECLARADO como parámetro de este "
    f"análisis, no citado: no sale de ninguna publicacion y no decide nada — solo evita "
    f"que la tabla se llene de ruido. El absoluto sigue sin existir."
)


# ─────────────────────────── la CONVENCION de posiciones ───────────────────────────
#
# SpliceAI y esta app apuntan a BASES DISTINTAS del mismo sitio. No es un error de
# ninguno de los dos: son dos convenciones, y hasta la corrida del 2026-09-05 sólo una
# de ellas estaba escrita.
#
#     donante   app → la G de GT       SpliceAI → última base exónica   → donante − 1
#     aceptor   app → la A de AG       SpliceAI → primera base exónica  → aceptor + 2
#
# MEDIDO sobre las diez construcciones de esa corrida: la app declara `donante=3134` y el
# pico está en 3133; declara `aceptor=3428` y el pico está en 3430. Y lo que convierte
# esto en errata es la magnitud del silencio: en la posición declarada la puntuación es
# **2e-07**, que NO es cero, así que la salvaguarda `legit_donor <= 0` no mordió y se
# normalizó un análisis entero contra un referente inexistente.

#: A qué base apunta cada posición de las que ESTA app declara.
DONOR_BASE = "G de GT"
ACCEPTOR_BASE = "A de AG"
BASE_OF_KIND = {"donante": DONOR_BASE, "aceptor": ACCEPTOR_BASE}

OUR_CONVENTION = "app"
SPLICEAI_CONVENTION = "spliceai"
CONVENTIONS = (OUR_CONVENTION, SPLICEAI_CONVENTION)

#: Lo que hay que SUMAR a nuestra posición para obtener la de SpliceAI. Medido, no
#: supuesto: ver el bloque de arriba.
TO_SPLICEAI = {"donante": -1, "aceptor": +2}

#: La línea que un resultado puede traer para declarar en qué convención vienen sus
#: posiciones. Va como comentario para que el fichero siga siendo un TSV de cinco
#: columnas.
CONVENTION_KEY = "convencion"

POSITION_CONVENTION_NOTE = (
    f"CONVENCIÓN DE POSICIONES. Las posiciones que declara esta app apuntan a la primera "
    f"base del intrón por el 5' (la {DONOR_BASE}) y a la primera base del AG por el 3' "
    f"(la {ACCEPTOR_BASE}). SpliceAI apunta a otras: la última base exónica para el "
    f"donante ({TO_SPLICEAI['donante']:+d}) y la primera base exónica para el aceptor "
    f"({TO_SPLICEAI['aceptor']:+d}). MEDIDO el 2026-09-05 sobre diez construcciones. Un "
    f"resultado en la convención de SpliceAI se declara con una línea "
    f"«# {CONVENTION_KEY}: {SPLICEAI_CONVENTION}» y se traduce al entrar; sin declararla "
    f"se comprueba contra el vecindario y se ABORTA si los marcos no cuadran."
)

#: La invocación que SÍ se ha verificado. NO es una orden ejecutable y no se usa como
#: tal: es la PROCEDENCIA del único resultado real que ha entrado en este proyecto, para
#: que la siguiente corrida se pueda comparar con ésta. La regla 4 sigue en pie —el
#: script concreto vive en la máquina de quien lo corrió y no está aquí—, así que
#: `LocalCommand` sigue exigiendo que la orden se le PASE.
VERIFIED_INVOCATION = {
    "fecha": "2026-09-05",
    "version": "SpliceAI 1.3",
    "entorno": "conda, entorno «spliceai», en WSL/Ubuntu",
    "forma": (
        "la LIBRERÍA desde Python, no el ejecutable `spliceai`: ése anota VARIANTES "
        "sobre un genoma con un VCF y no aplica a una construcción suelta"
    ),
    "modelos": "los cinco modelos del reparto, promediados",
    "ventana": (
        "10.000 nt, la del entrenamiento, con relleno de N hasta 5.000 por lado; el "
        "relleno NO cuenta como contexto declarado de la construcción"
    ),
    "salida": (
        "un TSV con las cinco columnas que declara `RESULT_COLUMNS`, una fila por "
        "POSICIÓN y CLASE — no sólo los máximos locales"
    ),
    "convencion": (
        f"posiciones en la convención de SpliceAI ({SPLICEAI_CONVENTION}): última base "
        f"exónica el donante, primera base exónica el aceptor"
    ),
}

VERIFIED_INVOCATION_NOTE = (
    "INVOCACIÓN VERIFICADA (2026-09-05): SpliceAI 1.3 en un entorno conda, llamado como "
    "LIBRERÍA desde Python —no el ejecutable `spliceai`, que anota variantes sobre un "
    "genoma—, con los cinco modelos promediados y ventana de 10.000 nt rellenada con N "
    "hasta 5.000 por lado. El relleno no es contexto: el contexto declarado es el de "
    "esta construcción y va en su cabecera."
)


def warning_blocks() -> list[dict[str, object]]:
    """Los avisos que van ANTES del boton. Todos activos: ninguno es opcional."""
    return [
        {"clave": "entrenamiento", "texto": NOT_TRAINED_FOR_THIS, "activo": True},
        {"clave": "sin_umbral", "texto": NO_ABSOLUTE_THRESHOLD, "activo": True},
        {"clave": "relativo", "texto": RELATIVE_ONLY, "activo": True},
        {"clave": "contexto", "texto": CONTEXT_MATTERS, "activo": True},
        {"clave": "uso", "texto": USE_NOTE, "activo": True},
    ]


# ─────────────────────────── la construccion: candidato x intron ───────────────────────


def _md5(texto: str) -> str:
    return hashlib.md5(texto.encode("ascii"), usedforsecurity=False).hexdigest()


@dataclass(frozen=True)
class Construction:
    """UN par candidato x intron, montado y listo para consultar."""

    name: str
    candidate_start: int
    intron: str
    sequence: str
    md5: str
    #: Contexto exonico a cada lado, en nt. DECLARADO: cambia el resultado.
    context_5: int
    context_3: int
    #: Posiciones 1-based DENTRO de la construccion.
    donor_position: int
    acceptor_position: int
    #: El donante criptico conocido del andamio, si esta.
    cryptic_position: int
    #: `True` si el andamio de esta construccion NO es el miR-E verificado.
    scaffold_modified: bool = False
    #: DE DONDE salio el contexto exonico: el casete con su md5 y su longitud, o las
    #: piezas del plasmido. Va en la cabecera del FASTA porque es lo unico que ata un
    #: resultado a las ENTRADAS con las que se monto — el md5 de la construccion dice
    #: que salio de aqui, no con que. Medido el 2026-09-05: dos casetes con 112 nt de
    #: diferencia dan construcciones distintas y nada lo decia.
    context_source: str = ""

    @property
    def intron_offset(self) -> int:
        """Donde empieza el intron dentro de la construccion (1-based)."""
        return self.context_5 + 1

    @property
    def intron_end(self) -> int:
        """La ULTIMA base del intron (1-based): la G del AG, o sea `aceptor + 1`."""
        return self.acceptor_position + 1

    def describe(self) -> str:
        lineas = [
            f"{self.name}  ({len(self.sequence)} nt, md5 {self.md5})",
            f"  candidato 3utr:{self.candidate_start} x intrón {self.intron}",
            f"  contexto exonico declarado: {self.context_5} nt por el 5' y "
            f"{self.context_3} nt por el 3'",
            f"  donante legítimo en construcción:{self.donor_position}, "
            f"aceptor en construcción:{self.acceptor_position}",
        ]
        if self.cryptic_position:
            lineas.append(
                f"  donante críptico conocido ({CRYPTIC_DONOR}) en "
                f"construccion:{self.cryptic_position}"
            )
        if self.scaffold_modified:
            lineas.append(
                "  ANDAMIO MODIFICADO: esta construcción NO lleva el miR-E verificado."
            )
        return "\n".join(lineas)


#: Las tres zonas de una construccion. NO son un adorno de la tabla: separan lo que
#: introduce la guia de lo que viene con el plasmido.
REGIONS = ("contexto5", "intron", "contexto3")

REGION_NOTE = (
    "LA REGIÓN DE CADA SITIO IMPORTA. Un sitio en el INTRÓN puede venir del módulo, así "
    "que cambia con la guía y es lo accionable de este frente. Uno en el CONTEXTO viene "
    "con el plásmido: está en las diez construcciones, no lo introduce ninguna guía y "
    "cambiar de candidato no lo quita. MEDIDO el 2026-09-05: el donante más fuerte de "
    "las diez —0,744 a 0,766 en construcción:1517, que es la 1516 en el marco de "
    "SpliceAI— cae en el contexto 5' y varía un 3 % entre hermanas, mientras el donante "
    "legítimo del intrón varía un 31 %."
)


def region_of(construction, position: int) -> str:
    """En qué zona de la construcción cae una posición 1-based."""
    if not 1 <= int(position) <= len(construction.sequence):
        raise ShmirDesignError(
            f"La posición {position} se sale de la construcción {construction.name} "
            f"({len(construction.sequence)} nt), así que no cae en ninguna región; se "
            f"aborta en vez de devolver una etiqueta inventada."
        )
    if position < construction.donor_position:
        return "contexto5"
    if position <= construction.intron_end:
        return "intron"
    return "contexto3"


def intron_report(names) -> list[dict[str, object]]:
    """Estado de cada intron pedido. Los que faltan salen VISIBLES, no se omiten."""
    filas = []
    for nombre in names:
        intron = get_intron(nombre)
        filas.append({
            "intron": nombre,
            "estado": intron.state,
            "descripcion": intron.description,
            "motivo": "" if intron.provided else intron.why_missing,
            "ficha": intron.ficha,
        })
    return filas


def context_note(constructions) -> str:
    """Que contexto exonico se ha dado, y si es poco lo DICE.

    Sin casete, lo unico que hay son las piezas `exon5`/`exon3` del plasmido: **5 nt por
    lado**, que para un modelo que mira miles es esencialmente NINGUN contexto. No se
    rellena con nada (regla 1) y no se esconde: se dice, y se dice como conseguir mas.
    """
    if not constructions:
        return "No hay construcciones."
    anchos = {(c.context_5, c.context_3) for c in constructions}
    if len(anchos) > 1:
        raise ShmirDesignError(
            f"Las construcciones de esta corrida no comparten la misma ventana de "
            f"contexto ({sorted(anchos)}), así que sus puntuaciones NO son comparables "
            f"entre si — y comparar entre construcciones es todo lo que este frente "
            f"puede hacer. Se aborta."
        )
    cinco, tres = anchos.pop()
    base = (
        f"Ventana de contexto exonico declarada: {cinco} nt por el 5' y {tres} nt por el "
        f"3'. {CONTEXT_MATTERS}"
    )
    if cinco <= len(PIECES["exon5"].sequence):
        base += (
            " AVISO: eso es lo que dan las piezas del plásmido y es esencialmente NINGÚN "
            "contexto para un modelo entrenado con ventana de 10.000 nt. Para dar más "
            "hace falta el CASETE (`aav_casete.fa`): entonces el contexto sale de "
            "secuencia real y no se rellena con nada."
        )
    return base


@dataclass(frozen=True)
class FailedConstruction:
    """Un par que NO se pudo montar, con de quien es y por que."""

    candidate_start: int
    intron: str
    reason: str


@dataclass(frozen=True)
class ConstructionPanel:
    """Lo que se pudo montar y lo que no. Las dos mitades, siempre."""

    constructions: tuple[Construction, ...]
    failed: tuple[FailedConstruction, ...] = ()

    @property
    def partial(self) -> bool:
        return bool(self.failed)


def guide_of(selection, elegido) -> str:
    """La guia de ESTE candidato, PEDIDA a su ventana.

    **Antes se recortaba de una secuencia que pasaba el llamador**
    —`target[start - 1:end]`— y esa es la causa entera de la errata nº 94: los `start`
    van en el marco de LO TILADO y la pagina pasaba el 3'UTR, asi que cuatro de las diez
    salian con la guia de OTRO SITIO —22 nt, md5 correcto, sin ningun error— y las seis
    que se salen del 3'UTR daban una cadena vacia. El aborto era la mitad afortunada.

    La guia ya esta calculada en la ventana. Volver a derivarla de una secuencia que
    puede ser cualquiera es una segunda definicion del mismo dato (principio nº 13), y
    con un `start` que no lleva marco no hay forma de comprobar cual es la buena.
    """
    ventana = selection.window_of(elegido)
    guia = "".join(str(ventana.evaluation.guide).split()).upper().replace("U", "T")
    if not guia:
        raise ShmirDesignError(
            f"El candidato 3utr:{elegido.start} llega SIN GUÍA: su ventana de la "
            f"selección trae la guía vacía, así que no hay "
            f"nada con lo que montar la horquilla. No es una guía mal formada — es una "
            f"guía que no ha llegado, y el sitio donde mirar es la ventana de ese "
            f"candidato en el tilado, no el andamio."
        )
    return guia


def build_panel(
    selection,
    *,
    intron_names=("mvm_actual",),
    scaffold=None,
    starts=None,
    cassette: str | None = None,
    context_nt: int = 0,
) -> ConstructionPanel:
    """Monta todos los pares y dice CUALES no pudo. No aborta por uno.

    **Un fallo en el montaje de UNA construccion no puede impedir las otras
    diecinueve**: el error salia antes del FASTA, asi que un candidato sin guia
    bloqueaba la corrida entera. Se emite lo que se puede y se dice lo que falta, que es
    la misma regla que rige los frentes.

    Lo que si aborta es que no salga NINGUNA: cero construcciones no es una entrega
    parcial — no hay nada que consultar, y un FASTA vacio no se podria validar despues.
    """
    hechas: list[Construction] = []
    fallidas: list[FailedConstruction] = []
    for nombre in intron_names:
        try:
            hechas.extend(build_constructions(
                selection, intron_names=(nombre,), scaffold=scaffold, starts=starts,
                cassette=cassette, context_nt=context_nt, _failures=fallidas,
            ))
        except ShmirDesignError as exc:
            # rule2-ok: no se traga — el motivo entero viaja en `failed` y la pagina lo
            # pinta. Lo que se evita es que un intron que no se puede montar impida los
            # demas. Si al final no queda ninguna construccion, se aborta abajo.
            for elegido in selection.selection.chosen:
                if starts is None or elegido.start in set(starts):
                    fallidas.append(FailedConstruction(
                        candidate_start=elegido.start, intron=nombre, reason=str(exc),
                    ))
    if not hechas:
        raise ShmirDesignError(
            "No se pudo montar NINGUNA construcción, así que no hay nada que consultar "
            "y no se emite ningún FASTA:\n"
            + "\n".join(f"  · 3utr:{f.candidate_start} × {f.intron}: {f.reason}"
                         for f in fallidas)
        )
    return ConstructionPanel(
        constructions=tuple(hechas), failed=tuple(fallidas),
    )


def build_constructions(
    selection,
    *,
    intron_names=("mvm_actual",),
    scaffold=None,
    starts=None,
    cassette: str | None = None,
    context_nt: int = 0,
    _failures: list | None = None,
) -> tuple[Construction, ...]:
    """Monta un cassette POR PAR candidato x intron. La unidad de este modal.

    `cassette` + `context_nt` sacan el contexto exonico de la SECUENCIA REAL del
    plasmido en vez de las dos piezas de 5 nt. Si se pide mas del que hay, se da lo que
    hay: nunca se rellena (regla 1).

    **La guia se PIDE a la ventana** (`_guia_de`), no se recorta de ninguna secuencia
    que pase el llamador: ver la errata nº 94.
    """
    elegidos = [
        c for c in selection.selection.chosen
        if starts is None or c.start in set(starts)
    ]
    if not elegidos:
        raise ShmirDesignError(
            "No hay ningún candidato seleccionado para consultar; se aborta en vez de "
            "emitir un FASTA vacío que luego no se podría validar."
        )

    construcciones: list[Construction] = []
    for nombre in intron_names:
        intron = get_intron(nombre)
        if not intron.provided:
            raise ShmirDesignError(
                f"El intrón {nombre!r} no está disponible, así que no hay cassette que "
                f"montar. {intron.why_missing} Se aborta en vez de emitir consultas de "
                f"un intrón que no tenemos."
            )
        contexto5, contexto3 = _flancos(
            intron, cassette=cassette, context_nt=context_nt
        )
        for elegido in elegidos:
            try:
                guia = guide_of(selection, elegido)
            except ShmirDesignError as exc:
                if _failures is None:
                    raise
                # rule2-ok: el motivo entero se conserva y viaja al panel; lo que se
                # evita es que un candidato tumbe a los otros diecinueve.
                _failures.append(FailedConstruction(
                    candidate_start=elegido.start, intron=nombre, reason=str(exc),
                ))
                continue
            bloque = build_block(guia, scaffold=scaffold)
            montado = intron.with_module(bloque.module)
            elementos = locate_elements(montado, name=nombre)
            secuencia = contexto5 + montado + contexto3
            desplazamiento = len(contexto5)
            criptico = montado.find(CRYPTIC_DONOR)
            construcciones.append(
                Construction(
                    name=f"{nombre}__3utr{elegido.start}",
                    candidate_start=elegido.start,
                    intron=nombre,
                    sequence=secuencia,
                    md5=_md5(secuencia),
                    context_5=len(contexto5),
                    context_3=len(contexto3),
                    donor_position=desplazamiento + elementos.donor.start,
                    acceptor_position=desplazamiento + elementos.acceptor.start,
                    cryptic_position=(
                        desplazamiento + criptico + 1 if criptico >= 0 else 0
                    ),
                    scaffold_modified=bool(
                        scaffold is not None and not getattr(scaffold, "verified", True)
                    ),
                    context_source=_context_source(
                        cassette if context_nt > 0 else None
                    ),
                )
            )
    return tuple(construcciones)


def _context_source(cassette) -> str:
    """La PROCEDENCIA del contexto, en una cadena que cabe en una cabecera de FASTA."""
    if not cassette:
        return "piezas"
    limpio = "".join(str(cassette).split()).upper()
    return f"casete:md5={_md5(limpio)}:{len(limpio)}nt"


def _flancos(intron, *, cassette, context_nt) -> tuple[str, str]:
    """El contexto exonico. Del casete si lo hay; si no, las piezas."""
    piezas = (
        PIECES[intron.exon5_piece].sequence if intron.exon5_piece else "",
        PIECES[intron.exon3_piece].sequence if intron.exon3_piece else "",
    )
    if not cassette or context_nt <= 0:
        return piezas

    from .splicing import locate_intron

    limpio = "".join(str(cassette).split()).upper()
    sitio = locate_intron(limpio, name="casete para el contexto de splicing")
    # `locate_intron` da posiciones 1-based: `donor_start` es el primer nt del intron y
    # `acceptor_end` el ultimo. El contexto es lo que hay FUERA de ese intervalo.
    inicio = sitio.donor_start - 1
    fin = sitio.acceptor_end
    # Se recorta a lo que el casete da. Pedir 100.000 no inventa 100.000.
    return (
        limpio[max(0, inicio - context_nt):inicio],
        limpio[fin:fin + context_nt],
    )


FASTA_WRAP = 60


def _fasta_comment_block(constructions, *, summary) -> list[str]:
    """Lo que el FICHERO tiene que decir de si mismo, en lineas de comentario.

    **Un nombre se pierde en el primer `mv`.** El estado de la corrida iba solo en el
    nombre del fichero (`construcciones_raton_PARCIAL_10de20.fa`) y eso dura hasta que
    alguien lo renombra —le quita un espacio, lo mueve, lo mete en un ZIP—. Lo que va
    pegado a los datos sobrevive a todo eso.

    Las lineas van ANTES del primer `>` y empiezan por `#`, que es lo que ignoran los
    lectores de FASTA. Aun asi **no son el unico sitio**: lo esencial se repite en cada
    cabecera `>`, que ningun lector tira.
    """
    from .identidad import build_stamp  # noqa: PLC0415

    lineas = [
        "# Construcciones para SpliceAI — shmiR design.",
        f"# {len(constructions)} registro(s) en este fichero.",
        f"# BUILD: {build_stamp()}",
    ]
    origenes = sorted({c.context_source for c in constructions if c.context_source})
    for origen in origenes:
        lineas.append(f"# CONTEXTO EXÓNICO tomado de: {origen}")
    if summary is not None:
        estado = "PARCIAL" if summary["parcial"] else "COMPLETO"
        lineas.append(
            f"# ESTADO: {estado} — {summary['emitidas']} de {summary['anunciadas']} "
            f"par(es) anunciado(s)."
        )
        if summary["parcial"]:
            lineas.append(
                f"#   FALTAN {summary['faltan']}. No se han montado y NO están aquí:"
            )
        for fila in summary["por_intron"]:
            if fila["fallidas"]:
                lineas.append(
                    f"#   · {fila['intron']} — 0 de "
                    f"{fila['emitidas'] + fila['fallidas']}: {fila['motivo']}"
                )
    for texto in (POSITION_CONVENTION_NOTE, REGION_NOTE, VERIFIED_INVOCATION_NOTE):
        lineas.append("#")
        lineas.extend(f"# {trozo}" for trozo in _wrap(texto, 88))
    return lineas


def _wrap(texto: str, ancho: int) -> list[str]:
    """Se DELEGA. Una copia mas de esta cuenta es una duplicacion que el auditor cuenta,
    y el techo de `data/magnitudes.toml` solo puede bajar."""
    from .outputs import _envolver  # noqa: PLC0415

    return _envolver(texto, ancho)


def constructions_fasta(constructions, *, summary=None) -> str:
    """El FASTA que se entrega. El md5 va EN LA CABECERA: es lo que ata el resultado.

    Y con el md5 van dos cosas mas, las dos porque **el fichero viaja solo**:

    - **la CONVENCION de cada posicion**, no solo la posicion: `donante=3134(G de GT)`.
      Quien escriba el siguiente puente tiene que poder saber a que base apunta sin
      medirlo — que es exactamente lo que costo la corrida del 2026-09-05. Y va tambien
      la misma posicion YA traducida a la convencion de SpliceAI, para no obligar a
      nadie a aplicar el desplazamiento a mano;
    - **el ESTADO del panel**, cuando se sabe (`summary`): si faltan pares, cada
      cabecera lo dice. Sin `summary` no se declara ninguno: un fichero que no sabe de
      que panel viene no puede decir «COMPLETO».
    """
    if not constructions:
        raise ShmirDesignError(
            "No hay construcciones que exportar; se aborta en vez de escribir un FASTA "
            "vacio."
        )
    estado = ""
    if summary is not None:
        estado = (
            f" panel={summary['emitidas']}de{summary['anunciadas']}"
            f" estado={'PARCIAL' if summary['parcial'] else 'COMPLETO'}"
        )
    lineas = _fasta_comment_block(constructions, summary=summary)
    for c in constructions:
        lineas.append(
            f">{c.name} md5={c.md5} longitud={len(c.sequence)} "
            f"contexto5={c.context_5} contexto3={c.context_3} "
            f"donante={c.donor_position}({DONOR_BASE}) "
            f"aceptor={c.acceptor_position}({ACCEPTOR_BASE}) "
            f"convencion={OUR_CONVENTION} "
            f"spliceai_donante={c.donor_position + TO_SPLICEAI['donante']} "
            f"spliceai_aceptor={c.acceptor_position + TO_SPLICEAI['aceptor']}"
            f"{' contexto_origen=' + c.context_source if c.context_source else ''}"
            f"{estado}"
        )
        for i in range(0, len(c.sequence), FASTA_WRAP):
            lineas.append(c.sequence[i:i + FASTA_WRAP])
    return "\n".join(lineas) + "\n"


# ─────────────────────────── el ejecutor ───────────────────────────


class Executor:
    """Interfaz. La de hoy es `Disabled`, igual que en el modal de especificidad."""

    name = "interfaz"
    runs_here = False
    why = ""

    def prepare(self, *, fasta_path: str) -> str:
        raise NotImplementedError

    def run(self, *, constructions):
        raise NotImplementedError


class Disabled(Executor):
    """La de HOY. No ejecuta y dice exactamente por que."""

    name = "deshabilitado"
    runs_here = False
    why = (
        "Este software no ejecuta SpliceAI y no puede: este backend no tiene red saliente "
        "y la invocación de SpliceAI no se ha verificado desde este proyecto, así que "
        "tampoco se escribe (regla 4). Lo que hace es PREPARAR el FASTA de las "
        "construcciones con su md5 y RECOGER el resultado. No es una limitacion "
        "escondida: es la arquitectura."
    )

    def prepare(self, *, fasta_path: str) -> str:
        return (
            f"Descarga {fasta_path}, pasalo por SpliceAI en tu máquina y sube el "
            f"resultado en el formato que describe la ficha. La orden concreta depende "
            f"de como lo tengas instalado y este proyecto NO la inventa. "
            f"{VERIFIED_INVOCATION_NOTE} {POSITION_CONVENTION_NOTE}"
        )

    def run(self, *, constructions):
        raise ShmirDesignError(
            f"El ejecutor «{self.name}» NO EJECUTA. {self.why}"
        )


class LocalCommand(Executor):
    """Da una orden para ejecutar EN LOCAL. La orden se le PASA: no se escribe aqui."""

    name = "orden_local"
    runs_here = False
    why = (
        "La orden se ejecuta en la máquina de quien la copia. Este módulo no trae ninguna "
        "escrita porque la invocación de SpliceAI no se ha verificado desde este proyecto "
        "(regla 4): se comprueba, se anota, y entonces se pasa."
    )

    def __init__(self, *, command: str | None):
        if not command or not str(command).strip():
            raise ValueError(
                "LocalCommand necesita una orden VERIFICADA. Aquí no hay ninguna escrita "
                "a propósito: la invocación de SpliceAI no se ha comprobado desde este "
                "proyecto, y escribirla de memoria es lo mismo que inventar una URL de "
                "API a partir de un patron. Se aborta."
            )
        self.command = str(command).strip()

    def prepare(self, *, fasta_path: str) -> str:
        return self.command.replace("{fasta}", fasta_path)

    def run(self, *, constructions):
        raise ShmirDesignError(
            f"El ejecutor «{self.name}» prepara la orden pero no la lanza desde aquí. "
            f"{self.why}"
        )


# ─────────────────────────── recoger el resultado ───────────────────────────

#: El formato que este modulo ACEPTA. Es nuestro, asi que si se define.
RESULT_COLUMNS = ("construccion", "md5", "posicion", "tipo", "puntuacion")
RESULT_HEADER = "\t".join(RESULT_COLUMNS)

SITE_KINDS = ("donante", "aceptor")


@dataclass(frozen=True)
class SiteScore:
    construction: str
    position: int
    kind: str
    score: float


def declared_convention(text: str) -> str:
    """La convencion que el fichero DECLARA, o la nuestra si no declara ninguna.

    Va en una linea de comentario —«# convencion: spliceai»— para que el TSV siga siendo
    de cinco columnas. Una convencion que no conocemos NO se adivina: se aborta.

    **El valor por defecto no cambia ningun dato** (principio nº 32): un fichero sin
    declaracion se lee tal cual, y lo que protege el caso es el guardia de marco, que
    compara con el vecindario en vez de creerse la etiqueta.
    """
    for linea in text.splitlines():
        if not linea.startswith("#"):
            continue
        cuerpo = linea.lstrip("#").strip()
        if ":" not in cuerpo:
            continue
        clave, valor = (t.strip() for t in cuerpo.split(":", 1))
        if clave.lower() != CONVENTION_KEY:
            continue
        if valor not in CONVENTIONS:
            raise ShmirDesignError(
                f"El resultado declara «{CONVENTION_KEY}: {valor}» y las que este "
                f"proyecto conoce son {CONVENTIONS}. NO se adivina cual es: se aborta. "
                f"{POSITION_CONVENTION_NOTE}"
            )
        return valor
    return OUR_CONVENTION


def to_our_frame(position: int, kind: str, *, convention: str) -> int:
    """Trae una posicion a NUESTRA convencion. Es la inversa de `TO_SPLICEAI`."""
    if convention == OUR_CONVENTION:
        return position
    return position - TO_SPLICEAI[kind]


def parse_result(text: str, *, constructions) -> tuple[SiteScore, ...]:
    """Lee el resultado y lo VALIDA contra lo que se entrego. Rechaza lo de otra corrida.

    Si el fichero declara la convencion de SpliceAI, las posiciones se TRADUCEN aqui, en
    la frontera, y todo lo de dentro habla una sola convencion — que es la unica forma de
    que no vuelvan a convivir dos marcos sin que nadie lo note.
    """
    convencion = declared_convention(text)
    por_nombre = {c.name: c for c in constructions}
    filas = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    if not filas:
        raise ShmirDesignError(
            "El resultado está vacío del todo: ni cabecera. Se aborta."
        )
    cabecera = tuple(filas[0].split("\t"))
    if cabecera != RESULT_COLUMNS:
        raise ShmirDesignError(
            f"La cabecera del resultado es {cabecera} y se esperaba {RESULT_COLUMNS}; se "
            f"aborta en vez de leer las columnas por posición."
        )
    if len(filas) == 1:
        raise ShmirDesignError(
            "El resultado solo trae cabecera. Se aborta: CERO SITIOS y «la corrida no "
            "llego a correr» son cosas distintas y este fichero NO DISTINGUE entre las "
            "dos. Es la misma razón por la que un `-outfmt 6` vacío también se rechaza."
        )

    sitios: list[SiteScore] = []
    for numero, fila in enumerate(filas[1:], start=2):
        campos = fila.split("\t")
        if len(campos) != len(RESULT_COLUMNS):
            raise ShmirDesignError(
                f"fila {numero}: tiene {len(campos)} campo(s) y la cabecera declara "
                f"{len(RESULT_COLUMNS)}; se aborta en vez de saltarse la fila."
            )
        nombre, md5, posicion, tipo, puntuacion = (c.strip() for c in campos)
        construccion = por_nombre.get(nombre)
        if construccion is None:
            raise ShmirDesignError(
                f"fila {numero}: la construcción {nombre!r} no es ninguna de las que "
                f"genero esta corrida ({', '.join(sorted(por_nombre))}). Se rechaza el "
                f"fichero entero: es el fallo del CSV de miRarchitect —un fichero de "
                f"OTRA CORRIDA pegado por error, que entra, cuadra de forma y produce un "
                f"análisis entero sobre el dato equivocado."
            )
        if md5 != construccion.md5:
            raise ShmirDesignError(
                f"fila {numero}: {nombre} declara md5 {md5!r} y la construcción que se "
                f"entrego tiene {construccion.md5!r}. Se rechaza: un resultado de OTRA "
                f"CORRIDA no puede entrar, aunque encaje de forma."
            )
        if tipo not in SITE_KINDS:
            raise ShmirDesignError(
                f"fila {numero}: tipo {tipo!r} desconocido; los que hay son "
                f"{SITE_KINDS}. Se aborta."
            )
        try:
            entero = int(posicion)
            valor = float(puntuacion)
        except ValueError as exc:
            raise ShmirDesignError(
                f"fila {numero}: posición o puntuación no numericas ({exc}); se aborta."
            ) from exc
        entero = to_our_frame(entero, tipo, convention=convencion)
        if not 1 <= entero <= len(construccion.sequence):
            raise ShmirDesignError(
                f"fila {numero}: la posición {entero} se sale de la construcción "
                f"{nombre} ({len(construccion.sequence)} nt); se aborta."
            )
        sitios.append(
            SiteScore(construction=nombre, position=entero, kind=tipo, score=valor)
        )
    return tuple(sitios)


# ─────────────────────────── el analisis ───────────────────────────


# ─────────────────────────── el guardia del MARCO ───────────────────────────

#: Cuantas bases a cada lado se miran para saber si el marco cuadra. Tres: el
#: desplazamiento mas grande que separa las dos convenciones es +2.
FRAME_RADIUS = 3

FRAME_NOTE = (
    "EL MARCO SE COMPRUEBA CONTRA EL VECINDARIO, no contra un umbral. La salvaguarda "
    "anterior era «el donante legítimo no puede valer cero» y no mordió: en la posición "
    "equivocada valía 2e-07, que no es cero. Lo que sí distingue los dos casos sin "
    "inventar ningún corte es que la base declarada sea el MÁXIMO de su vecindario: "
    "medido el 2026-09-05, con el marco bueno la declarada vale 0,66-0,87 y ninguna "
    "vecina pasa de 1,1e-05 —cuatro órdenes de margen—; con el marco ajeno la relación "
    "se invierte entera."
)


@dataclass(frozen=True)
class FrameCheck:
    """Si el marco del resultado y el de la app coinciden. Emite ESTADO, no un booleano."""

    state: FilterState
    reason: str = ""
    #: Desplazamiento hallado por clase, cuando se pudo medir.
    offsets: tuple[tuple[str, int], ...] = ()

    @property
    def matches_spliceai(self) -> bool:
        return bool(self.offsets) and all(
            TO_SPLICEAI[tipo] == desplazamiento for tipo, desplazamiento in self.offsets
        )


def check_frame(construction, sites) -> FrameCheck:
    """La base DECLARADA tiene que ser el máximo de su vecindario. Si no, hay dos marcos.

    Tres desenlaces, y ninguno es «pasar callando»:

    - `PASS`  — la declarada domina su vecindario en las dos clases;
    - `FAIL`  — alguna vecina la supera. Se dice **cuál** y **a cuántas bases**, y si el
      desplazamiento coincide con el de SpliceAI se dice también cómo declararlo;
    - `NOT_RUN` — el fichero no trae vecinas que mirar, así que la comprobación no se
      puede hacer. No se disfraza de PASS: el principio nº 33 es exactamente esto.
    """
    declaradas = {
        "donante": construction.donor_position,
        "aceptor": construction.acceptor_position,
    }
    por_clase: dict[str, dict[int, float]] = {"donante": {}, "aceptor": {}}
    for sitio in sites:
        declarada = declaradas[sitio.kind]
        if abs(sitio.position - declarada) <= FRAME_RADIUS:
            por_clase[sitio.kind][sitio.position] = sitio.score

    desplazamientos: list[tuple[str, int]] = []
    sin_vecindario = []
    problemas = []
    for tipo, declarada in declaradas.items():
        vecindario = por_clase[tipo]
        vecinas = {p: v for p, v in vecindario.items() if p != declarada}
        if not vecinas:
            sin_vecindario.append(tipo)
            continue
        mejor = max(vecindario, key=lambda p: vecindario[p])
        if mejor == declarada:
            continue
        desplazamiento = mejor - declarada
        desplazamientos.append((tipo, desplazamiento))
        problemas.append(
            f"{tipo}: la app declara construcción:{declarada} "
            f"({BASE_OF_KIND[tipo]}) con {vecindario.get(declarada, 0.0):.3e}, y el "
            f"máximo del vecindario está en construcción:{mejor} "
            f"({desplazamiento:+d}) con {vecindario[mejor]:.3e}"
        )

    if problemas:
        comprobacion = FrameCheck(
            state=FilterState.FAIL,
            reason="",
            offsets=tuple(desplazamientos),
        )
        pista = ""
        if comprobacion.matches_spliceai:
            pista = (
                f" ESE desplazamiento es EXACTAMENTE el que separa nuestra convención de "
                f"la de SpliceAI (donante {TO_SPLICEAI['donante']:+d}, aceptor "
                f"{TO_SPLICEAI['aceptor']:+d}). Si el resultado viene en la de SpliceAI, "
                f"declaralo con una línea «# {CONVENTION_KEY}: {SPLICEAI_CONVENTION}» al "
                f"principio del fichero y entra tal cual."
            )
        return FrameCheck(
            state=FilterState.FAIL,
            reason=(
                f"{construction.name}: el resultado y la app NO hablan del mismo marco. "
                + "; ".join(problemas) + "." + pista + f" {FRAME_NOTE}"
            ),
            offsets=tuple(desplazamientos),
        )

    if sin_vecindario:
        return FrameCheck(
            state=FilterState.NOT_RUN,
            reason=(
                f"{construction.name}: no se puede comprobar el marco de "
                f"{', '.join(sin_vecindario)} porque el fichero no trae ninguna posición "
                f"vecina (±{FRAME_RADIUS}) que comparar. NO es que cuadre: es que no hay "
                f"con qué comprobarlo. {FRAME_NOTE}"
            ),
        )
    return FrameCheck(state=FilterState.PASS)


def require_frame(construction, sites) -> FrameCheck:
    """El guardia: comprueba y ABORTA. `check_frame` calcula; ésta es la que impide.

    Van separadas a proposito. `check_frame` tiene que poder devolver `NOT_RUN` sin
    tumbar nada —el fichero puede no traer vecindario— y eso es un ESTADO que la pagina
    enseña (regla 3). Lo que no puede seguir es un marco que se ha medido y NO cuadra.
    """
    comprobacion = check_frame(construction, sites)
    if comprobacion.state is FilterState.FAIL:
        raise ShmirDesignError(comprobacion.reason)
    return comprobacion


@dataclass(frozen=True)
class Cryptic:
    position: int
    kind: str
    score: float
    fraction: float
    note: str = ""
    #: `contexto5`, `intron` o `contexto3`. Separa lo que introduce la guia de lo que
    #: viene con el plasmido y no se quita cambiando de candidato.
    region: str = ""


@dataclass(frozen=True)
class PairResult:
    """Un par candidato x intron, ya interpretado CONTRA SU PROPIO REFERENTE."""

    construction: str
    candidate_start: int
    intron: str
    legit_donor: float
    legit_acceptor: float
    cryptics: tuple[Cryptic, ...]
    known_cryptic: Cryptic | None
    context_5: int
    context_3: int
    #: Si el marco del resultado y el de la app coinciden. NUNCA es un booleano suelto.
    frame_check: FrameCheck = FrameCheck(state=FilterState.NOT_RUN, reason="sin comprobar")

    @property
    def best_cryptic(self) -> Cryptic | None:
        return self.cryptics[0] if self.cryptics else None

    def describe(self) -> list[str]:
        lineas = [
            f"{self.construction}  (3utr:{self.candidate_start} x {self.intron})",
            f"  REFERENTE INTERNO — donante legítimo {self.legit_donor:.3f}, "
            f"aceptor legítimo {self.legit_acceptor:.3f}",
            f"  contexto declarado: {self.context_5} nt / {self.context_3} nt",
        ]
        if self.best_cryptic is None:
            lineas.append(
                f"  Ningún sitio críptico llega al {RELATIVE_THRESHOLD:.0%} del legítimo."
            )
        else:
            mejor = self.best_cryptic
            lineas.append(
                f"  MEJOR CRÍPTICO — construcción:{mejor.position} ({mejor.kind}) "
                f"{mejor.score:.3f} = {mejor.fraction:.0%} del legítimo"
            )
            for otro in self.cryptics[1:]:
                lineas.append(
                    f"    construcción:{otro.position} ({otro.kind}) {otro.score:.3f} "
                    f"= {otro.fraction:.0%}"
                )
        if self.known_cryptic is not None:
            lineas.append(
                f"  {CRYPTIC_DONOR} (el críptico CONOCIDO del andamio, y el motivo por "
                f"el que existe este modal) — construcción:"
                f"{self.known_cryptic.position} {self.known_cryptic.score:.3f} "
                f"= {self.known_cryptic.fraction:.0%} del legítimo"
            )
        else:
            lineas.append(
                f"  {CRYPTIC_DONOR}: SIN PUNTUAR en este resultado. No es «no puntua»: "
                f"es que el fichero no trae ninguna fila para esa posición."
            )
        return lineas


@dataclass(frozen=True)
class SpliceScan:
    pairs: tuple[PairResult, ...]
    threshold: float = RELATIVE_THRESHOLD

    def for_candidate(self, start: int, intron: str) -> PairResult | None:
        for par in self.pairs:
            if par.candidate_start == start and par.intron == intron:
                return par
        return None


def scan_from_result(text: str, *, constructions) -> SpliceScan:
    """Del resultado crudo al analisis, siempre contra el referente INTERNO."""
    sitios = parse_result(text, constructions=constructions)
    por_construccion: dict[str, list[SiteScore]] = {}
    for sitio in sitios:
        por_construccion.setdefault(sitio.construction, []).append(sitio)

    pares: list[PairResult] = []
    for construccion in constructions:
        suyos = por_construccion.get(construccion.name, [])
        if not suyos:
            continue
        marco = require_frame(construccion, suyos)
        legitimo_donante = next(
            (s.score for s in suyos
             if s.position == construccion.donor_position and s.kind == "donante"),
            0.0,
        )
        legitimo_aceptor = next(
            (s.score for s in suyos
             if s.position == construccion.acceptor_position and s.kind == "aceptor"),
            0.0,
        )
        if legitimo_donante <= 0:
            raise ShmirDesignError(
                f"{construccion.name}: el donante legítimo "
                f"(construccion:{construccion.donor_position}) no viene puntuado o vale "
                f"cero, así que NO HAY REFERENTE interno contra el que comparar. Y sin "
                f"referente no hay nada: las puntuaciones absolutas de este modelo no "
                f"son interpretables sobre un cassette de AAV. Se aborta. "
                f"{RELATIVE_ONLY}"
            )

        cripticos = []
        conocido = None
        for sitio in suyos:
            legitimo = (
                sitio.position == construccion.donor_position and sitio.kind == "donante"
            ) or (
                sitio.position == construccion.acceptor_position
                and sitio.kind == "aceptor"
            )
            if legitimo:
                continue
            fraccion = sitio.score / legitimo_donante
            entrada = Cryptic(
                position=sitio.position, kind=sitio.kind, score=sitio.score,
                fraction=fraccion,
                region=region_of(construccion, sitio.position),
                note=(
                    f"{CRYPTIC_DONOR}: donante críptico del flanco 5' de miR-E. Viaja "
                    f"con CUALQUIER candidato porque está dentro del andamio, y compite "
                    f"por el aceptor legítimo del intrón."
                    if sitio.position == construccion.cryptic_position else ""
                ),
            )
            if sitio.position == construccion.cryptic_position and sitio.kind == "donante":
                conocido = entrada
            if fraccion >= RELATIVE_THRESHOLD:
                cripticos.append(entrada)

        cripticos.sort(key=lambda c: c.score, reverse=True)
        pares.append(
            PairResult(
                construction=construccion.name,
                candidate_start=construccion.candidate_start,
                intron=construccion.intron,
                legit_donor=legitimo_donante,
                legit_acceptor=legitimo_aceptor,
                cryptics=tuple(cripticos),
                known_cryptic=conocido,
                context_5=construccion.context_5,
                context_3=construccion.context_3,
                frame_check=marco,
            )
        )
    return SpliceScan(pairs=tuple(pares))


# ─────────────────────────── la guia MODULA el donante legitimo ───────────────────────

MODULATION_NOTE = (
    "LA GUÍA MODULA EL DONANTE LEGÍTIMO. No es sólo que una guía pueda meter un sitio "
    "críptico nuevo: el sitio legítimo del intrón, que es el MISMO en las diez "
    "construcciones, puntúa distinto según qué módulo lleve dentro. MEDIDO el "
    "2026-09-05 sobre las diez del panel murino: de 0,664 en 3utr:959 a 0,871 en "
    "3utr:1684, un 31 %, con el sitio a más de 100 nt del módulo. Ninguna baja hasta "
    "preocupar, pero el efecto existe y es medible, así que sale como COLUMNA y no como "
    "una nota. Y el contraste es lo que le da sentido: el donante más fuerte de todas "
    "—el del contexto 5', que no lo pone ninguna guía— varía sólo un 3 % entre las "
    "mismas diez."
)


@dataclass(frozen=True)
class DonorModulation:
    """Cuanto mueve la GUIA al donante legitimo, dentro de un mismo intron."""

    intron: str
    minimum: float
    maximum: float
    lowest: str
    highest: str
    pairs: int

    @property
    def spread(self) -> float:
        """Recorrido RELATIVO al minimo. Cero si no hay con que comparar."""
        if self.minimum <= 0 or self.pairs < 2:
            return 0.0
        return (self.maximum - self.minimum) / self.minimum


def donor_modulation(scan) -> tuple[DonorModulation, ...]:
    """Una fila POR INTRÓN: entre sus construcciones, cuánto se mueve el legítimo.

    Se compara sólo entre hermanas del MISMO intrón. Mezclar intrones daría un recorrido
    que sólo dice que los intrones son distintos, que ya se sabe — el mismo motivo por el
    que `exclusive_rows` tampoco los mezcla.
    """
    por_intron: dict[str, list] = {}
    for par in scan.pairs:
        por_intron.setdefault(par.intron, []).append(par)
    filas = []
    for nombre, pares in por_intron.items():
        ordenados = sorted(pares, key=lambda p: p.legit_donor)
        filas.append(DonorModulation(
            intron=nombre,
            minimum=ordenados[0].legit_donor,
            maximum=ordenados[-1].legit_donor,
            lowest=ordenados[0].construction,
            highest=ordenados[-1].construction,
            pairs=len(ordenados),
        ))
    return tuple(filas)


def donor_fraction(scan, pair) -> float:
    """El donante legitimo de un par, como fraccion del mayor de SUS HERMANAS."""
    hermanas = [p.legit_donor for p in scan.pairs if p.intron == pair.intron]
    mayor = max(hermanas) if hermanas else 0.0
    return pair.legit_donor / mayor if mayor > 0 else 0.0


def exclusive_rows(scan: SpliceScan) -> list[dict[str, object]]:
    """Que guias introducen cripticos que las OTRAS no. Es lo accionable.

    Se compara ENTRE CONSTRUCCIONES del mismo intron: mezclar intrones distintos aqui
    daria «exclusivos» que solo dicen que los intrones son distintos, que ya se sabe.
    """
    filas = []
    for par in scan.pairs:
        hermanas = [
            p for p in scan.pairs
            if p.intron == par.intron and p.construction != par.construction
        ]
        compartidas = set()
        for hermana in hermanas:
            compartidas |= {(c.position, c.kind) for c in hermana.cryptics}
        exclusivos = [
            c for c in par.cryptics if (c.position, c.kind) not in compartidas
        ]
        filas.append({
            "construccion": par.construction,
            "candidato": par.candidate_start,
            "intron": par.intron,
            "exclusivos": [
                {"posicion": c.position, "tipo": c.kind, "fraccion": c.fraction,
                 "region": c.region}
                for c in exclusivos
            ],
            "hermanas": len(hermanas),
        })
    return filas


def verdict_state(scan: SpliceScan | None) -> FilterState:
    """NUNCA FAIL. Desempate y alerta: no puede excluir a nadie."""
    return FilterState.PASS if scan and scan.pairs else FilterState.NOT_RUN
