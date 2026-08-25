"""Espaciadores del intron: los estandar, y generacion de novo cuando no valen.

## AUTORIZACION

La regla 1 prohibe generar secuencia. Aqui hay una excepcion **escrita y acotada**,
concedida explicitamente: cuando el 97-mero no conserva su estructura dentro del intron
con los espaciadores estandar, se pueden generar espaciadores nuevos PARA ESA GUIA.

La autorizacion cubre **solo los espaciadores**. No cubre guias, ni pasajeras, ni
contextos de SGEP, ni el andamio, ni ninguna otra pieza. Esas siguen copiandose literal o
derivandose de la entrada, y ninguna funcion de este modulo las toca.

Condiciones, las mismas que se usaron para los originales:

  - sin donantes cripticos GTRAGT (GTAAGT / GTGAGT), GTAAGG ni GTGAGG
  - sin señales de poliadenilacion AATAAA ni ATTAAA
  - sin homopolimeros de 4 o mas, y en particular sin GGGG ni CCCC
  - sin duplicar ninguno de los sitios del cassette
  - GC entre 0,28 y 0,45

Criterio de seleccion, **uno solo**: entre los que pasan los filtros, el que hace que el
97-mero dentro del intron pliegue identico a como pliega aislado. Si varios lo cumplen,
el de menor MFE del intron completo.

Longitudes FIJAS: 20 nt el espaciador 5' y 45 nt el 3'. No se tocan — son las que dejan
la horquilla a 86 nt del 5'SS y a 62 del punto de ramificacion.

## Como se busca, y por que asi

Los estandar son el **caso base**: se prueban primero y, si funcionan, se devuelven sin
buscar nada mas. Eso garantiza la propiedad que pide la autorizacion — para una guia
conocida el algoritmo elige exactamente los espaciadores que ya estan fijos — y hace que
el generador no pueda "mejorar" un diseño validado por su cuenta.

Cuando no funcionan, se busca por **desviacion creciente**: primero cambiando solo el 5',
luego solo el 3', y solo despues los dos. Asi el resultado se queda lo mas cerca posible
del diseño original.

La generacion es **determinista**: la semilla sale de la propia horquilla, asi que la
misma guia da siempre los mismos espaciadores. Sin eso, dos corridas del mismo diseño
pedirian bloques distintos.

Python 3.11+, solo libreria estandar; ViennaRNA es opcional pero sin el no hay criterio
que aplicar (regla 6).
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from dataclasses import dataclass

from .blocks import PIECES

SPACER5_LENGTH = 20
SPACER3_LENGTH = 45

STANDARD_5 = PIECES["espaciador5"].sequence
STANDARD_3 = PIECES["espaciador3"].sequence

#: GTRAGT son dos: R es A o G. Mas las dos variantes que se vigilan aparte.
CRYPTIC_DONORS = ("GTAAGT", "GTGAGT", "GTAAGG", "GTGAGG")
POLYA_SIGNALS = ("AATAAA", "ATTAAA")
CASSETTE_SITES = ("GCTAGC", "GAGCTC", "ACGCGT", "ACCGGT", "CTCGAG", "GAATTC")
FORBIDDEN_RUNS = ("GGGG", "CCCC")
MAX_HOMOPOLYMER = 3
GC_MIN = 0.28
GC_MAX = 0.45

#: Cuantos candidatos se llegan a plegar como mucho. Cada plegado del intron cuesta
#: ~14 ms, asi que 300 son unos 4 s. Es un tope, no un objetivo.
DEFAULT_BUDGET = 300

#: Composicion con la que se generan los candidatos. Uniforme daria GC ~0,50 y casi todo
#: caeria fuera de la ventana 0,28-0,45; con esto la mayoria entra a la primera. Es un
#: detalle de generacion, no un filtro: el filtro sigue siendo `spacer_rejections`.
_BASE_WEIGHTS = (("A", 32), ("T", 32), ("G", 18), ("C", 18))


def _homopolymer_run(sequence: str) -> tuple[str, int]:
    peor, actual, base, ganadora = 0, 0, "", ""
    for i, letra in enumerate(sequence):
        actual = actual + 1 if i and letra == base else 1
        base = letra
        if actual > peor:
            peor, ganadora = actual, letra
    return ganadora, peor


def gc_fraction(sequence: str) -> float:
    if not sequence:
        raise ValueError("No se puede calcular el GC de una secuencia vacia.")
    return sum(1 for b in sequence.upper() if b in "GC") / len(sequence)


def spacer_rejections(sequence: str) -> tuple[str, ...]:
    """Motivos por los que un espaciador NO vale. Vacio = pasa todos los filtros."""
    limpia = "".join(str(sequence).split()).upper()
    if not limpia:
        return ("El espaciador esta vacio.",)

    motivos: list[str] = []
    for donante in CRYPTIC_DONORS:
        if donante in limpia:
            motivos.append(
                f"Lleva el donante criptico de splicing {donante}: podria abrir un 5'SS "
                f"dentro del intron."
            )
    for señal in POLYA_SIGNALS:
        if señal in limpia:
            motivos.append(
                f"Lleva la señal de poliadenilacion {señal}: podria cortar el "
                f"transcrito antes de tiempo."
            )
    base, largo = _homopolymer_run(limpia)
    if largo > MAX_HOMOPOLYMER:
        motivos.append(
            f"Homopolimero de {largo} {base}: el limite es {MAX_HOMOPOLYMER}."
        )
    for tramo in FORBIDDEN_RUNS:
        if tramo in limpia:
            motivos.append(f"Lleva {tramo}.")
    for sitio in CASSETTE_SITES:
        if sitio in limpia:
            motivos.append(
                f"Lleva el sitio {sitio}, que ya esta en el cassette: duplicarlo "
                f"romperia el clonaje."
            )
    gc = gc_fraction(limpia)
    if not GC_MIN <= gc <= GC_MAX:
        motivos.append(
            f"GC {gc:.3f}, fuera de la ventana {GC_MIN:.2f}-{GC_MAX:.2f}."
        )
    return tuple(motivos)


def is_acceptable(sequence: str) -> bool:
    return not spacer_rejections(sequence)


@dataclass(frozen=True)
class SpacerChoice:
    spacer5: str
    spacer3: str
    standard: bool
    structure: str
    mfe: float

    def format_text(self) -> str:
        lineas = [
            "Espaciadores del intron:",
            f"  5' ({len(self.spacer5)} nt)  {self.spacer5}",
            f"  3' ({len(self.spacer3)} nt)  {self.spacer3}",
            "",
            f"  Plegado del intron completo ({len(self.structure)} nt), "
            f"MFE {self.mfe:+.2f} kcal/mol:",
        ]
        lineas.extend(
            f"    {self.structure[i : i + 60]}"
            for i in range(0, len(self.structure), 60)
        )
        lineas.append("")
        if self.standard:
            lineas.append(
                "  Son los espaciadores ESTANDAR del proyecto, sin tocar: el 97-mero "
                "conserva su estructura dentro del intron con ellos."
            )
        else:
            lineas.extend(
                [
                    "  ⚠  ESPACIADORES GENERADOS DE NOVO. Son ESPECIFICOS DE ESTA GUIA "
                    "y NO SON LOS ESTANDAR:",
                    "     con los estandar el 97-mero no conserva su estructura dentro "
                    "del intron.",
                    "  ⚠  Un cassette MluI-AgeI montado con estos espaciadores NO es "
                    "intercambiable con",
                    "     el modulo NheI-SacI estandar: el intron es otro. Si cambias la "
                    "horquilla de ese",
                    "     cassette por un modulo estandar, vuelves a tener el problema "
                    "que estos espaciadores",
                    "     resuelven — y al reves.",
                ]
            )
        return "\n".join(lineas)


@dataclass(frozen=True)
class SpacerSearch:
    choice: SpacerChoice | None
    evaluated: int
    #: Cuantos candidatos descarto el filtro duro ANTES de plegarlos.
    rejected: int
    note: str

    def format_text(self) -> str:
        if self.choice is None:
            return f"Espaciadores — NO HAY\n  {self.note}"
        return self.choice.format_text() + f"\n  {self.note}"


def _random_spacer(rng: random.Random, length: int) -> str:
    bases = [b for b, _ in _BASE_WEIGHTS]
    pesos = [w for _, w in _BASE_WEIGHTS]
    return "".join(rng.choices(bases, weights=pesos, k=length))


def _candidates(
    rng: random.Random, length: int, cuantos: int
) -> tuple[list[str], int]:
    """Candidatos que YA pasan los filtros duros. Los que no, ni se pliegan.

    Devuelve tambien cuantos se descartaron. Si se agotan los intentos y salen menos de
    los pedidos, quien llama tiene que poder decirlo: un presupuesto que no se gasta
    entero y no se menciona parece una busqueda completa.
    """
    salida: list[str] = []
    descartados = 0
    intentos = 0
    tope = cuantos * 200
    while len(salida) < cuantos and intentos < tope:
        intentos += 1
        sonda = _random_spacer(rng, length)
        if is_acceptable(sonda):
            salida.append(sonda)
        else:
            descartados += 1
    return salida, descartados


def choose_spacers(
    *,
    hairpin: str,
    structure_alone: str,
    assemble: Callable[[str, str], str],
    budget: int = DEFAULT_BUDGET,
) -> SpacerSearch:
    """Elige los espaciadores. Los estandar son el caso base y ganan si funcionan.

    `assemble(espaciador5, espaciador3)` devuelve el intron completo montado.
    """
    from .folding import VIENNA_AVAILABLE, dot_bracket  # noqa: PLC0415

    if not VIENNA_AVAILABLE:
        return SpacerSearch(
            choice=None,
            evaluated=0,
            rejected=0,
            note=(
                "ViennaRNA no esta instalado, asi que no hay criterio que aplicar: el "
                "unico criterio de seleccion es el plegado. No se generan espaciadores "
                "a ciegas. `pip install ViennaRNA`."
            ),
        )
    if budget < 1:
        raise ValueError(
            f"budget={budget}: hay que dejar evaluar al menos el caso base; se aborta."
        )

    evaluados = 0

    def evaluar(e5: str, e3: str) -> tuple[bool, str, float]:
        nonlocal evaluados
        evaluados += 1
        intron = assemble(e5, e3)
        estructura, mfe = dot_bracket(intron)
        inicio = intron.index(hairpin)
        dentro = estructura[inicio : inicio + len(hairpin)]
        return dentro == structure_alone, estructura, mfe

    # ── Caso base ────────────────────────────────────────────────────────────
    vale, estructura, mfe = evaluar(STANDARD_5, STANDARD_3)
    if vale:
        return SpacerSearch(
            choice=SpacerChoice(
                spacer5=STANDARD_5, spacer3=STANDARD_3, standard=True,
                structure=estructura, mfe=mfe,
            ),
            evaluated=evaluados,
            rejected=0,
            note=(
                "Los espaciadores estandar funcionan con esta guia; no se ha generado "
                "nada."
            ),
        )

    # ── Busqueda por desviacion creciente ────────────────────────────────────
    semilla = int(hashlib.md5(hairpin.encode("ascii"), usedforsecurity=False).hexdigest()[:8], 16)
    rng = random.Random(semilla)
    restante = budget - evaluados
    por_etapa = max(1, restante // 3)

    cinco, descartados5 = _candidates(rng, SPACER5_LENGTH, por_etapa)
    tres, descartados3 = _candidates(rng, SPACER3_LENGTH, por_etapa)
    descartados = descartados5 + descartados3
    corto = ""
    if len(cinco) < por_etapa or len(tres) < por_etapa:
        corto = (
            f" AVISO: no se pudieron generar todos los candidatos pedidos "
            f"({len(cinco)}/{por_etapa} de 5' y {len(tres)}/{por_etapa} de 3'): los "
            f"filtros duros dejan poco sitio. La busqueda es mas corta de lo que dice "
            f"el presupuesto."
        )

    parejas: list[tuple[str, str]] = []
    parejas.extend((c, STANDARD_3) for c in cinco)
    parejas.extend((STANDARD_5, t) for t in tres)
    parejas.extend(zip(cinco, tres))

    validos: list[SpacerChoice] = []
    for e5, e3 in parejas:
        if evaluados >= budget:
            break
        vale, estructura, mfe = evaluar(e5, e3)
        if vale:
            validos.append(
                SpacerChoice(
                    spacer5=e5, spacer3=e3, standard=False,
                    structure=estructura, mfe=mfe,
                )
            )

    if not validos:
        return SpacerSearch(
            choice=None,
            evaluated=evaluados,
            rejected=descartados,
            note=(
                f"No se encontro ningun par de espaciadores que conserve la estructura "
                f"del 97-mero dentro del intron, en {evaluados} candidato(s) plegados "
                f"(presupuesto {budget}; {descartados} descartado(s) por los filtros "
                f"duros antes de plegar). No se inventa uno peor: sube el presupuesto o "
                f"cambia de candidato.{corto}"
            ),
        )

    #: Criterio unico. A igualdad de MFE manda el orden de generacion, que es
    #: determinista, para que dos corridas no pidan bloques distintos.
    mejor = min(validos, key=lambda c: (c.mfe, c.spacer5, c.spacer3))
    return SpacerSearch(
        choice=mejor,
        evaluated=evaluados,
        rejected=descartados,
        note=(
            f"Los estandar NO conservan la estructura con esta guia. De "
            f"{evaluados} candidato(s) plegados, {len(validos)} la conservan; se ha "
            f"elegido el de menor MFE del intron completo.{corto}"
        ),
    )
