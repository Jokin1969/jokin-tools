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

NHEI_SITE = "GCTAGC"
CONTEXT_5 = "GAAGGCTCGAGAAGGTATAT"
CONTEXT_3 = "CTTCAAGGGGCTAGAATTCG"
SACI_SITE = "GAGCTC"

MLUI_SITE = "ACGCGT"
AGEI_SITE = "ACCGGT"

GBLOCK_LENGTH = 149
MAX_HOMOPOLYMER = 3
HOMOPOLYMER = re.compile(r"(.)\1{" + str(MAX_HOMOPOLYMER) + r",}")

#: Posiciones de los contextos en el plasmido SGEP depositado (1-based, inclusivas).
CONTEXT_POSITIONS = MappingProxyType(
    {"contexto_5": (1739, 1758), "contexto_3": (1856, 1875)}
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


def build_gblock(hairpin: Hairpin) -> GBlock:
    """Monta el modulo NheI–SacI y lo comprueba. No silencia ningun fallo."""
    sequence = NHEI_SITE + CONTEXT_5 + hairpin.sequence + CONTEXT_3 + SACI_SITE
    return GBlock(
        sequence=sequence,
        hairpin=hairpin,
        checks=(
            _check_length(sequence),
            _check_unique_sites(sequence),
            _check_intron_sites(sequence),
            _check_homopolymer(hairpin.sequence),
        ),
    )


def verify_contexts_against_plasmid(plasmid: str) -> None:
    """Contrasta los contextos con el plasmido depositado. Aborta si no coinciden."""
    cleaned = "".join(str(plasmid).split()).upper()
    for nombre, (inicio, fin) in CONTEXT_POSITIONS.items():
        esperado = CONTEXT_5 if nombre == "contexto_5" else CONTEXT_3
        if len(cleaned) < fin:
            raise ShmirDesignError(
                f"El plásmido mide {len(cleaned)} nt y {nombre} deberia estar en "
                f"{inicio}-{fin}; se aborta la verificación en vez de darla por buena."
            )
        encontrado = cleaned[inicio - 1 : fin]
        if encontrado != esperado:
            raise ShmirDesignError(
                f"{nombre}: en {inicio}-{fin} del plásmido hay {encontrado!r} y el "
                f"módulo usa {esperado!r}. PARA: no pidas el gBlock hasta aclararlo."
            )
