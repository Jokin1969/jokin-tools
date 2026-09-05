"""Modulo NheI–SacI de 149 nt, listo para pedir como gBlock.

Composicion fija salvo el 97-mero:

    GCTAGC + GAAGGCTCGAGAAGGTATAT + [97-mero] + CTTCAAGGGGCTAGAATTCG + GAGCTC
     NheI      contexto 5' (20)                   contexto 3' (20)      SacI

Los dos contextos son secuencia nativa de SGEP (Addgene #111170) inmediatamente
adyacente al 97-mero: posiciones 1739-1758 y 1856-1875 del plasmido depositado. Estan
ahi porque el `CTTC` que queda en +15 respecto de la union basal es el motivo CNNC que
reconoce SRSF3, probablemente el elemento conservado 3' critico. **No se recortan ni se
sustituyen.**

Las dos cadenas de contexto estan copiadas literalmente de la especificacion, no
reconstruidas. `verify_contexts_against_plasmid()` las contrasta contra el `.dna` de
SGEP si algun dia se tiene a mano, y aborta si no coinciden.

Comprobaciones que se emiten con cada modulo:

  longitud        exactamente 149 nt
  sitios_unicos   GCTAGC y GAGCTC aparecen una sola vez cada uno; un segundo sitio
                  romperia el clonaje, asi que es FAIL y hay que avisarlo
  sitios_intron   sin ACGCGT (MluI) ni ACCGGT (AgeI), los sitios del intron externo
  homopolimero    sin tramos de >=4 nt iguales EN LA PARTE VARIABLE (el contexto 3'
                  nativo lleva un GGGG por diseño; si contara, todo modulo seria FAIL)

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType

from .errors import ShmirDesignError
from .filters import FilterResult, FilterState, Verdict, overall_verdict
from .scaffold import Hairpin


def _pieza(nombre: str) -> str:
    """La secuencia de una pieza de `blocks.PIECES`, que es su unico origen."""
    from .blocks import PIECES  # noqa: PLC0415  (ciclo: `blocks` importa `gblock`)

    return PIECES[nombre].sequence


def _span(nombre: str) -> tuple[int, int]:
    """Las posiciones de esa pieza en el plasmido. ABORTA si la pieza no las declara."""
    from .blocks import PIECES  # noqa: PLC0415

    pieza = PIECES[nombre]
    if pieza.span is None:
        raise ShmirDesignError(
            f"La pieza {nombre!r} no declara sus posiciones en el plásmido, así que no "
            f"se puede contrastar con él; se aborta en vez de inventarlas."
        )
    return pieza.span

# ORIGEN ÚNICO: estas secuencias VIVEN en `blocks.PIECES`, con su procedencia y sus
# posiciones en el plásmido. Aquí sólo se les pone nombre. Antes había dos juegos de
# constantes con llamador cada uno, coincidiendo sin que nada lo obligara: corregir un
# contexto en un sitio y no en el otro habría hecho que la ficha y los oligos
# describieran dos módulos distintos, y lo que divergiría es ADN que se manda a
# sintetizar. Un test comprueba que no ha pasado; esto impide que pase.
NHEI_SITE = _pieza("NheI")
CONTEXT_5 = _pieza("contexto5")
CONTEXT_3 = _pieza("contexto3")
SACI_SITE = _pieza("SacI")

MLUI_SITE = _pieza("MluI")
AGEI_SITE = _pieza("AgeI")

GBLOCK_LENGTH = 149
MAX_HOMOPOLYMER = 3
HOMOPOLYMER = re.compile(r"(.)\1{" + str(MAX_HOMOPOLYMER) + r",}")

#: Posiciones de los contextos en el plasmido SGEP depositado (1-based, inclusivas).
#: Tambien DERIVADAS: las lleva la pieza, que es donde vive su procedencia. Tenerlas
#: aqui a mano era la tercera copia del mismo dato.
CONTEXT_POSITIONS = MappingProxyType(
    {"contexto_5": _span("contexto5"), "contexto_3": _span("contexto3")}
)


@dataclass(frozen=True)
class GBlock:
    sequence: str
    hairpin: Hairpin
    checks: tuple[FilterResult, ...]

    @property
    def verdict(self) -> Verdict:
        return overall_verdict(list(self.checks))

    @property
    def ok(self) -> bool:
        return self.verdict is Verdict.PASS

    @property
    def failures(self) -> tuple[FilterResult, ...]:
        return tuple(c for c in self.checks if c.state is FilterState.FAIL)

    def format_text(self) -> str:
        lines = [
            f"Módulo NheI–SacI — {len(self.sequence)} nt",
            "",
            f"  {self.sequence}",
            "",
            "  Piezas (5'→3'):",
            f"    NheI        {NHEI_SITE}",
            f"    contexto 5' {CONTEXT_5}  (SGEP {CONTEXT_POSITIONS['contexto_5'][0]}-"
            f"{CONTEXT_POSITIONS['contexto_5'][1]}, nativo)",
            f"    97-mero     {self.hairpin.sequence}",
            f"    contexto 3' {CONTEXT_3}  (SGEP {CONTEXT_POSITIONS['contexto_3'][0]}-"
            f"{CONTEXT_POSITIONS['contexto_3'][1]}, nativo; lleva el CNNC de SRSF3)",
            f"    SacI        {SACI_SITE}",
            "",
            "  Comprobaciones:",
        ]
        lines.extend(
            f"    {c.name:<14} {c.state.value:<7} {c.reason}" for c in self.checks
        )
        for warning in self.hairpin.warnings:
            lines.append(f"  ⚠  {warning}")
        return "\n".join(lines)


def _check_length(sequence: str) -> FilterResult:
    if len(sequence) == GBLOCK_LENGTH:
        return FilterResult(
            name="longitud",
            state=FilterState.PASS,
            reason=f"{len(sequence)} nt, los {GBLOCK_LENGTH} esperados.",
        )
    return FilterResult(
        name="longitud",
        state=FilterState.FAIL,
        reason=(
            f"{len(sequence)} nt y se esperaban {GBLOCK_LENGTH}. El andamio o los brazos "
            f"no son los del módulo estándar; no lo pidas así."
        ),
    )


def _check_unique_sites(sequence: str) -> FilterResult:
    repetidos = [
        f"{sitio} aparece {sequence.count(sitio)} veces"
        for sitio, nombre in ((NHEI_SITE, "NheI"), (SACI_SITE, "SacI"))
        if sequence.count(sitio) != 1
    ]
    if not repetidos:
        return FilterResult(
            name="sitios_unicos",
            state=FilterState.PASS,
            reason=f"{NHEI_SITE} (NheI) y {SACI_SITE} (SacI) aparecen una sola vez.",
        )
    return FilterResult(
        name="sitios_unicos",
        state=FilterState.FAIL,
        reason=(
            f"{'; '.join(repetidos)}. Un segundo sitio rompe el clonaje NheI–SacI: "
            f"la guía o la pasajera han generado uno."
        ),
    )


def _check_intron_sites(sequence: str) -> FilterResult:
    presentes = [
        f"{sitio} ({nombre})"
        for sitio, nombre in ((MLUI_SITE, "MluI"), (AGEI_SITE, "AgeI"))
        if sitio in sequence
    ]
    if not presentes:
        return FilterResult(
            name="sitios_intron",
            state=FilterState.PASS,
            reason=f"Sin {MLUI_SITE} (MluI) ni {AGEI_SITE} (AgeI).",
        )
    return FilterResult(
        name="sitios_intron",
        state=FilterState.FAIL,
        reason=f"Contiene {', '.join(presentes)}, que son los sitios del intrón externo.",
    )


def _check_homopolymer(variable: str) -> FilterResult:
    match = HOMOPOLYMER.search(variable)
    if match is None:
        return FilterResult(
            name="homopolimero",
            state=FilterState.PASS,
            reason=(
                f"Sin tramos de más de {MAX_HOMOPOLYMER} nt iguales en la parte variable. "
                f"El GGGG del contexto 3' es nativo de SGEP y no cuenta: va por diseño."
            ),
        )
    return FilterResult(
        name="homopolimero",
        state=FilterState.FAIL,
        reason=(
            f"Homopolimero {match.group(0)} ({len(match.group(0))} nt) en la parte "
            f"variable, posición {match.start() + 1} del 97-mero."
        ),
    )


WHY_THE_PLASMID_IS_A_CHECK = (
    "Los contextos del módulo son CONSTANTES de este código, y lo que se pide a "
    "sintetizar tiene que encajar en el plásmido REAL. Contrastarlos es una "
    "comprobación como las otras cuatro, no un extra: por eso corre en cada "
    "generación de módulo y por eso su ausencia sale NOT_RUN y no PASS."
)

#: Lo que haría falta para que la comprobación corra de verdad. NO está en el
#: repositorio: `data/reference/aav_casete.fa` es pAAV con PrP murino, otro vector, y no
#: contiene ninguno de los dos contextos —comprobado, con test—.
SGEP_PLASMID_MISSING = (
    "No está el plásmido SGEP depositado, así que los contextos del módulo "
    f"(5' {CONTEXT_5} en {CONTEXT_POSITIONS['contexto_5'][0]}-"
    f"{CONTEXT_POSITIONS['contexto_5'][1]}, 3' {CONTEXT_3} en "
    f"{CONTEXT_POSITIONS['contexto_3'][0]}-{CONTEXT_POSITIONS['contexto_3'][1]}) NO se "
    "han contrastado con el vector real. NO pidas el gBlock con esto sin resolver."
)


def _check_contexts(plasmid: str | None) -> FilterResult:
    """La comprobación de los contextos, como quinto `FilterResult` del módulo.

    Un desajuste NO sale como FAIL de este candidato: `verify_contexts_against_plasmid`
    ABORTA, y está bien que aborte. Si los contextos no son los del vector, están mal
    TODOS los módulos y no éste — un veredicto por candidato lo disfrazaría de problema
    de la ventana, que es de lo que uno se fía para descartarla y seguir con la
    siguiente.
    """
    if plasmid is None:
        return FilterResult(
            name="contextos_vs_plasmido",
            state=FilterState.NOT_RUN,
            reason=SGEP_PLASMID_MISSING,
        )
    verify_contexts_against_plasmid(plasmid)
    return FilterResult(
        name="contextos_vs_plasmido",
        state=FilterState.PASS,
        reason=(
            f"Los dos contextos coinciden con el plásmido en las posiciones "
            f"declaradas ({CONTEXT_POSITIONS['contexto_5'][0]}-"
            f"{CONTEXT_POSITIONS['contexto_5'][1]} y "
            f"{CONTEXT_POSITIONS['contexto_3'][0]}-"
            f"{CONTEXT_POSITIONS['contexto_3'][1]})."
        ),
    )


def build_gblock(hairpin: Hairpin, *, plasmid: str | None = None) -> GBlock:
    """Monta el modulo NheI–SacI y lo comprueba. No silencia ningun fallo.

    `plasmid` es el vector depositado. Sin él la comprobación de contextos sale
    `NOT_RUN` y el módulo entero `INCOMPLETE`: ver `WHY_THE_PLASMID_IS_A_CHECK`.
    """
    sequence = NHEI_SITE + CONTEXT_5 + hairpin.sequence + CONTEXT_3 + SACI_SITE
    return GBlock(
        sequence=sequence,
        hairpin=hairpin,
        checks=(
            _check_length(sequence),
            _check_unique_sites(sequence),
            _check_intron_sites(sequence),
            _check_homopolymer(hairpin.sequence),
            _check_contexts(plasmid),
        ),
    )


def verify_contexts_against_plasmid(plasmid: str) -> None:
    """Contrasta los contextos con el plasmido depositado. Aborta si no coinciden.

    **YA NO LEE COORDENADAS.** Hasta 2026-09-02 miraba el plasmido en `1739-1758` y
    `1856-1875` —numeros ESCRITOS— y comparaba lo que hubiera ahi. Eso comprueba menos de
    lo que parece: con las coordenadas corridas fallaria contra un plasmido CORRECTO, y
    el arreglo obvio —moverlas hasta que cuadren— lo dejaria pasando siempre. Un numero
    escrito no puede validar el fichero del que salio (principio nº 13).

    Ahora el ancla es la ANOTACION del propio fichero y el andamio se localiza POR
    SECUENCIA a su alrededor (`scaffold_registry.anchor_scaffold`); los contextos son lo
    que flanquea al 97-mero, y la longitud que se pide es la del contexto del MODULO —que
    es la pregunta: ¿lo que llevamos es lo nativo de SGEP?

    Recibe el GenBank ENTERO, no la secuencia pelada: sin el bloque FEATURES no hay
    anotacion de la que anclarse, y anclarse solo por secuencia es la mitad que se acaba
    de quitar.
    """
    from .scaffold_registry import SCAFFOLDS, anchor_scaffold  # noqa: PLC0415

    ancla = anchor_scaffold(
        SCAFFOLDS["mir_e"], str(plasmid), context_length=len(CONTEXT_5)
    )
    for nombre, esperado, encontrado, span in (
        ("contexto_5", CONTEXT_5, ancla.context_5, ancla.context_5_span),
        ("contexto_3", CONTEXT_3, ancla.context_3, ancla.context_3_span),
    ):
        if encontrado != esperado:
            raise ShmirDesignError(
                f"{nombre}: pegado al andamio, en {span[0]}-{span[1]} del plásmido, hay "
                f"{encontrado!r} y el módulo usa {esperado!r}. PARA: no pidas el gBlock "
                f"hasta aclararlo."
            )
