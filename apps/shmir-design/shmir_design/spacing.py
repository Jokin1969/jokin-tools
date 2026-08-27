"""Cuando dos candidatos son EL MISMO SITIO del panel.

221 y 223 son dos ventanas corridas 2 nt. Bajo la regla de espaciado del proyecto son el
mismo sitio, aunque las guias sean distintas y una fuente externa las liste como dos
entradas. Presentar la segunda como un candidato nuevo cuenta dos veces la misma plaza.

El aviso NO descarta nada: puede interesar cambiar una por otra, y para eso hay que ver
que compiten y con que numeros. Descartarla en silencio quitaria esa decision.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from .coords import Frame, label
from .selection import DEFAULT_MIN_SPACING, respects_spacing

#: El espaciado minimo entre posiciones de inicio, el mismo que usa la seleccion.
SITE_SPACING = DEFAULT_MIN_SPACING


def same_site(a: int, b: int, *, spacing: int = SITE_SPACING) -> bool:
    """¿Dos posiciones de inicio caen dentro del mismo sitio?

    Es la NEGACION EXACTA del criterio con el que la seleccion acepta un candidato
    (`selection._respects_spacing`: `abs(a - b) >= min_spacing`), y se define asi a
    proposito. Tenerlas por separado ya produjo una discrepancia: este modulo contaba
    como MISMO SITIO un par a exactamente 50 nt que la seleccion habia elegido como DOS.
    `spacing` es el minimo EXIGIDO, asi que a exactamente esa distancia si se cumple.
    """
    return not respects_spacing(a, b, spacing=spacing)


@dataclass(frozen=True)
class ReferenceSet:
    """Contra QUE se mide si una plaza es nueva. La etiqueta es obligatoria.

    Sin ella, «4 plazas nuevas» no es un resultado: el mismo cruce da 7 plazas contra
    los 6 candidatos elegidos y ninguna contra los 90 sitios elegibles, porque seis
    posiciones no cubren 1242 nt. La cifra sin la referencia es una cifra suelta, igual
    que una longitud sin su md5.
    """

    label: str
    starts: dict[int, str]
    frame: Frame

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise ValueError(
                "Un conjunto de referencia necesita etiqueta: la cuenta de plazas "
                "nuevas depende de contra que se mida, y sin decirlo el número no "
                "significa nada. Se aborta."
            )
        if not isinstance(self.frame, Frame):
            raise ValueError(
                f"Espacio de coordenadas {self.frame!r} desconocido en el conjunto de "
                f"referencia {self.label!r}; se aborta."
            )

    @property
    def size(self) -> int:
        return len(self.starts)


@dataclass(frozen=True)
class SiteConflict:
    candidate_start: int
    candidate_guide: str
    reference_start: int
    reference_guide: str
    distance: int
    reference_label: str
    frame: Frame = Frame.UTR3

    @property
    def message(self) -> str:
        return (
            f"El candidato de {label(self.candidate_start, self.frame)} está a "
            f"{self.distance} nt del de {label(self.reference_start, self.frame)}, que "
            f"ya está en {self.reference_label}: bajo el espaciado del proyecto son EL "
            f"MISMO SITIO, así que no es una plaza nueva del panel.\n"
            f"    nuevo       {label(self.candidate_start, self.frame):>10}  "
            f"{self.candidate_guide}\n"
            f"    referencia  {label(self.reference_start, self.frame):>10}  "
            f"{self.reference_guide}\n"
            f"    No se descarta: puede interesar cambiar uno por otro. Lo que no se "
            f"puede es contarlos como dos."
        )


@dataclass(frozen=True)
class SiteComparison:
    """El resultado, con la referencia DENTRO. No se puede leer sin ella."""

    reference: ReferenceSet
    conflicts: tuple[SiteConflict, ...]
    new_plazas: tuple[int, ...]
    identical: tuple[int, ...]
    spacing: int
    candidates: int
    #: Las posiciones de los candidatos comparados, para poder responder despues sin
    #: volver a pasarlas por parametro.
    candidates_starts: tuple[int, ...] = ()
    #: Plaza nueva -> otros candidatos externos que caen en ELLA. Dos externos a menos
    #: del espaciado son una plaza, no dos.
    merged: dict[int, tuple[int, ...]] = None

    def describe(self) -> str:
        lineas = [
            f"Espaciado de sitios ({self.spacing} nt) de {self.candidates} candidato(s) "
            f"externo(s) CONTRA {self.reference.label} ({self.reference.size} "
            f"posicion(es)).",
            "  La cifra de plazas nuevas depende de esta referencia y solo de ella: "
            "contra un",
            "  subconjunto seleccionado casi todo parece nuevo. Cambiar la referencia "
            "cambia el número.",
        ]
        if self.identical:
            lineas.append(
                "  IDÉNTICAS a una ventana de la referencia (misma posición de inicio): "
                + ", ".join(label(p, self.reference.frame) for p in self.identical)
            )
        lineas.append(
            f"  plazas NUEVAS: "
            + (
                ", ".join(label(p, self.reference.frame) for p in self.new_plazas)
                if self.new_plazas
                else "ninguna"
            )
        )
        for plaza, otras in (self.merged or {}).items():
            lineas.append(
                f"  {label(plaza, self.reference.frame)} absorbe a "
                + ", ".join(label(p, self.reference.frame) for p in otras)
                + f": entre ellas también hay menos de {self.spacing} nt, así que son "
                f"UNA plaza."
            )
        lineas.extend(f"  · {c.message}" for c in self.conflicts)
        return "\n".join(lineas)


def compare_sites(
    *,
    candidates: dict[int, str],
    reference: ReferenceSet,
    spacing: int = SITE_SPACING,
) -> SiteComparison:
    """Que candidatos externos son plaza nueva CONTRA `reference`, y cuales no.

    `reference` es obligatoria y lleva su etiqueta: es el conjunto completo de
    candidatos, no el subconjunto que la seleccion haya elegido. Medir contra los
    elegidos infla la cuenta de plazas nuevas — es lo que hizo salir «7 plazas» donde
    contra la tabla completa no queda ninguna.
    """
    conflictos = tuple(
        SiteConflict(
            candidate_start=inicio,
            candidate_guide=guia,
            reference_start=otro,
            reference_guide=reference.starts[otro],
            distance=abs(inicio - otro),
            reference_label=reference.label,
            frame=reference.frame,
        )
        for inicio, guia in sorted(candidates.items())
        for otro in sorted(reference.starts)
        if inicio != otro and same_site(inicio, otro, spacing=spacing)
    )
    con_conflicto = {c.candidate_start for c in conflictos}
    identicas = tuple(p for p in sorted(candidates) if p in reference.starts)
    sobreviven = [
        p for p in sorted(candidates)
        if p not in con_conflicto and p not in reference.starts
    ]
    # Y los supervivientes se agrupan ENTRE ELLOS: dos candidatos externos a menos del
    # espaciado son una plaza nueva, no dos. Contarlos por separado es el mismo error de
    # doble cuenta, un nivel mas abajo.
    nuevas: list[int] = []
    agrupadas: dict[int, tuple[int, ...]] = {}
    for inicio in sobreviven:
        if nuevas and same_site(nuevas[-1], inicio, spacing=spacing):
            agrupadas[nuevas[-1]] = agrupadas.get(nuevas[-1], ()) + (inicio,)
            continue
        nuevas.append(inicio)
    return SiteComparison(
        reference=reference,
        conflicts=conflictos,
        new_plazas=tuple(nuevas),
        identical=identicas,
        spacing=spacing,
        candidates=len(candidates),
        candidates_starts=tuple(sorted(candidates)),
        merged=agrupadas,
    )


def site_conflicts(
    *,
    candidates: dict[int, str],
    reference: ReferenceSet,
    spacing: int = SITE_SPACING,
) -> tuple[SiteConflict, ...]:
    """Solo los choques. `compare_sites` da ademas las plazas nuevas y la referencia."""
    return compare_sites(
        candidates=candidates, reference=reference, spacing=spacing
    ).conflicts


# ─── El resultado, como HALLAZGO ─────────────────────────────────────────────
#
# Cero sitios exclusivos de la fuente externa no es un parametro de configuracion ni una
# nota de proceso: es un resultado sobre el 3'UTR, y se declara como tal. Dos metodos
# independientes, con criterios distintos, sobre la misma secuencia, no encuentran ni un
# sitio que el otro no tenga.
#
# La lectura NO es «los dos metodos se validan»: donde solo cabe coincidir, coincidir no
# demuestra nada. Es que el espacio de ventanas viables esta SATURADO bajo los filtros
# duros, y entonces la convergencia externa no discrimina entre candidatos — no se puede
# usar para elegir. Sirve para calibrar nuestra propia cascada, y va al suplementario.

NEAR = 1  # nt; «coincidencia a 1 nt» es la misma ventana corrida una base


@dataclass(frozen=True)
class Convergence:
    comparison: SiteComparison
    method_a: str
    method_b: str
    #: Posiciones externas que caen EXACTAMENTE sobre un sitio de la referencia.
    exact: tuple[int, ...]
    #: Pares (externo, nuestro) a 1 nt: la misma ventana corrida una base.
    within_1nt: tuple[tuple[int, int], ...]
    #: Externos sin ningun sitio de la referencia dentro del espaciado.
    exclusive: tuple[int, ...]
    #: De esos, los que ADEMAS superan nuestros filtros duros. Es la cifra del hallazgo:
    #: un sitio exclusivo que nosotros mismos descartamos no es una plaza que la fuente
    #: externa aporte.
    exclusive_usable: tuple[int, ...]

    def window_of(self, start: int, sequence: str, length: int = 22) -> str:
        """La ventana de la secuencia en esa posicion, para poder comparar base a base."""
        if start < 1 or start + length - 1 > len(sequence):
            raise ValueError(
                f"La ventana de {label(start, self.comparison.reference.frame)} no cabe "
                f"en una secuencia de {len(sequence)} nt; se aborta."
            )
        return sequence[start - 1 : start - 1 + length]

    def describe(self, *, offset: int = 0) -> list[str]:
        """`offset` = primera posicion del 3'UTR menos 1, para dar las dos parejas."""
        marco = self.comparison.reference.frame

        def pos(valor: int) -> str:
            etiqueta = label(valor, marco)
            if offset and valor - offset >= 1:
                etiqueta += f" ({label(valor - offset, Frame.UTR3)})"
            return etiqueta

        lineas = [
            "HALLAZGO — el espacio de ventanas viables está SATURADO",
            f"  Dos metodos independientes con criterios distintos sobre el MISMO "
            f"3'UTR: {self.method_a}",
            f"  y {self.method_b}. {self.comparison.candidates} sitio(s) de la fuente "
            f"externa contra {self.comparison.reference.label}",
            f"  ({self.comparison.reference.size} posiciones), espaciado "
            f"{self.comparison.spacing} nt:",
            f"    · {len(self.exclusive_usable)} sitios exclusivos de la fuente externa "
            f"que superen nuestros filtros duros.",
        ]
        if self.exclusive:
            lineas.append(
                "      ("
                + ", ".join(pos(p) for p in self.exclusive)
                + " no choca con ningún sitio nuestro, pero no pasa nuestros filtros "
                "duros:"
            )
            lineas.append(
                "      por eso no hay ninguna ventana elegible cerca, y por eso no es "
                "una plaza que nadie aporte.)"
            )
        lineas.append(
            f"    · {len(self.exact)} coincidencia(s) EXACTA(S), misma posición de "
            f"inicio y misma ventana base a base: "
            + ", ".join(pos(p) for p in self.exact)
        )
        if self.within_1nt:
            lineas.append(
                f"    · {len(self.within_1nt)} a 1 nt (la misma ventana corrida una "
                f"base): "
                + ", ".join(
                    f"{pos(a)}↔{pos(b)}" for a, b in self.within_1nt
                )
            )
        lineas.extend(
            [
                "  LECTURA. Esto NO ES UNA VALIDACIÓN cruzada: donde solo cabe "
                "coincidir, coincidir no",
                "  demuestra nada. Lo que dice es que bajo los filtros duros quedan tan "
                "pocas ventanas",
                "  viables que dos criterios distintos aterrizan en las mismas. La "
                "convergencia externa",
                "  NO DISCRIMINA entre candidatos y NO PUEDE USARSE PARA ELEGIR: no "
                "ordena, no desempata",
                "  y no aporta plazas.",
                "  Es un dato de CALIBRACION de nuestra propia cascada — cuanto margen "
                "de elección deja —,",
                "  y como tal va al SUPLEMENTARIO, no al ranking.",
            ]
        )
        return lineas


def convergence(
    comparison: SiteComparison,
    *,
    eligible: set[int] | frozenset[int],
    method_a: str,
    method_b: str,
) -> Convergence:
    """Convierte una comparacion de sitios en el hallazgo, con sus cifras.

    `eligible` son las posiciones de inicio que superan NUESTROS filtros duros. Hace
    falta porque «sitio exclusivo» y «plaza utilizable» son dos preguntas distintas: un
    sitio que solo tiene la fuente externa y que nosotros descartamos no es una plaza
    que ella aporte.
    """
    if not method_a.strip() or not method_b.strip():
        raise ValueError(
            "Un hallazgo de convergencia nombra los DOS metodos que se comparan; sin "
            "eso la cifra no dice de que es. Se aborta."
        )
    referencia = comparison.reference.starts
    exactas = tuple(p for p in sorted(comparison.candidates_starts) if p in referencia)
    cercanas = tuple(
        (p, q)
        for p in sorted(comparison.candidates_starts)
        if p not in referencia
        for q in sorted(referencia)
        if abs(p - q) <= NEAR
    )
    return Convergence(
        comparison=comparison,
        method_a=method_a,
        method_b=method_b,
        exact=exactas,
        within_1nt=cercanas,
        exclusive=comparison.new_plazas,
        exclusive_usable=tuple(
            p for p in comparison.new_plazas if p in eligible
        ),
    )
