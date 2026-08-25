"""Proxy de asimetria termodinamica de la guia (paso 7).

    asimetria = ΔG(4 pb terminales del extremo 5' de la GUIA)
              − ΔG(4 pb terminales del extremo 3' de la GUIA)

Positivo = el extremo 5' de la guia esta MENOS establemente apareado, que es lo que se
busca: asi se carga la guia y no la pasajera. Umbral de paso: >= +0.5 kcal/mol.

No compara guia contra pasajera: son los dos extremos de la MISMA guia. Y se calcula
sobre la guia YA TRANSFORMADA (con la U forzada en la posicion 1), porque dentro de la
horquilla la pasajera se recalcula como complementario reverso de la guia modificada:
ese par existe de verdad en la molecula. El desapareamiento es contra la DIANA, no
dentro del duplex.

Parametros: Turner 2004, ARN, 37 C. Sin termino de iniciacion, que se cancela en la
resta. Penalizacion terminal AU de +0.45 aplicada a los dos extremos de cada tetramero.

**Esto es un proxy heuristico, no una energia libre de duplex.** Aplicar la
penalizacion terminal en el limite INTERNO del tetramero no es rigurosamente correcto:
ahi no hay fin de helice real. Es una simplificacion operativa deliberada. Como el
valor solo se usa para ORDENAR candidatos, importa mas la consistencia entre ventanas
que la exactitud absoluta. No lo publiques como ΔG de un duplex, porque no lo es.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from .errors import InvalidSequenceError

#: Paso de vecino mas proximo (5'→3') → kcal/mol. Turner 2004, ARN, 37 C.
NN_STEPS: dict[str, float] = {
    "AA": -0.93, "UU": -0.93,
    "AU": -1.10, "UA": -1.33,
    "CU": -2.08, "AG": -2.08,
    "CA": -2.11, "UG": -2.11,
    "GU": -2.24, "AC": -2.24,
    "GA": -2.35, "UC": -2.35,
    "CG": -2.36,
    "GG": -3.26, "CC": -3.26,
    "GC": -3.42,
}

AU_END_PENALTY = 0.45
TERMINAL_LENGTH = 4
RNA_BASES = frozenset("ACGU")


def _validate_rna(sequence: str, *, name: str = "guia") -> str:
    cleaned = "".join(str(sequence).split()).upper()
    if not cleaned:
        raise InvalidSequenceError(
            f"La {name} esta vacia; se aborta el calculo de la asimetria."
        )
    for index, base in enumerate(cleaned, start=1):
        if base not in RNA_BASES:
            extra = (
                " La guia va en notacion ARN: una T significa que llego ADN sin "
                "transformar."
                if base == "T"
                else ""
            )
            raise InvalidSequenceError(
                f"{name}: caracter {base!r} no valido en la posicion {index} "
                f"(se esperaba A, C, G o U); se aborta el calculo de la asimetria."
                f"{extra}"
            )
    return cleaned


def tetramer_dg(tetramer: str) -> float:
    """ΔG del tetramero: 3 pasos de vecino mas proximo + penalizacion AU terminal."""
    cleaned = _validate_rna(tetramer, name="tetramero")
    if len(cleaned) != TERMINAL_LENGTH:
        raise ValueError(
            f"El tetramero mide {len(cleaned)} nt y deben ser {TERMINAL_LENGTH}; "
            f"se aborta el calculo de la asimetria."
        )

    total = 0.0
    for index in range(TERMINAL_LENGTH - 1):
        step = cleaned[index : index + 2]
        if step not in NN_STEPS:
            raise InvalidSequenceError(
                f"Paso {step!r} sin parametro en la tabla de Turner; se aborta el "
                f"calculo de la asimetria en vez de tratarlo como 0."
            )
        total += NN_STEPS[step]

    for extremo in (cleaned[0], cleaned[-1]):
        if extremo in "AU":
            total += AU_END_PENALTY
    return total


def turner_asymmetry(guide: str) -> float:
    """Asimetria de la guia en kcal/mol. Positivo = extremo 5' menos estable = bueno."""
    cleaned = _validate_rna(guide)
    if len(cleaned) < 2 * TERMINAL_LENGTH:
        raise ValueError(
            f"La guia mide {len(cleaned)} nt y hacen falta al menos "
            f"{2 * TERMINAL_LENGTH} para que los dos tetrameros terminales no se "
            f"solapen; se aborta el calculo de la asimetria."
        )
    return tetramer_dg(cleaned[:TERMINAL_LENGTH]) - tetramer_dg(
        cleaned[-TERMINAL_LENGTH:]
    )
