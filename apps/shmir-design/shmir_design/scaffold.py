"""Andamio miR-E: montaje de la horquilla de 97 nt (salida de oligos).

Andamio SGEP (Addgene #111170), verificado contra el fichero SnapGene de la secuencia
depositada y coincidente con tres fuentes:

    flanco5 + PASAJERA(22) + loop + GUIA(22) + flanco3  = 97 nt

La guia va en el brazo 3p. `SCAFFOLD["verified"] = True` se refiere **solo** al 97-mero:
los flancos extendidos del pri-miR que hacen falta para el cassette AAV siguen sin
decidir y este modulo se niega a inventarlos.

## La regla de la pasajera NO esta confirmada

La pasajera no es el complementario reverso exacto de la guia: lleva un desapareamiento
deliberado en su posicion 1, que en el plasmido de referencia es C donde el
complementario reverso daria T. La regla implementada es la transicion T↔C.

**Esa regla esta derivada de UN SOLO ejemplo.** Hasta verificarla contra un segundo
plasmido miR-E con una guia distinta (LT3GEPIR, Addgene #111177), va marcada como
`REGLA_NO_CONFIRMADA` y el aviso sale en toda salida de oligos. Si el revcomp empieza
por A o por G, el caso no esta cubierto por el ejemplo: no se toca la base y se avisa,
en vez de inventar una transicion que nadie ha visto.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType

from .errors import InvalidSequenceError

ARM_LENGTH = 22
DNA_BASES = frozenset("ACGT")
COMPLEMENT = str.maketrans("ACGT", "TGCA")

SCAFFOLD = MappingProxyType(
    {
        "name": "miR-E / SGEP",
        "source": (
            "SGEP, Addgene #111170; fichero SnapGene de la secuencia depositada, "
            "coincidente con tres fuentes"
        ),
        "flank5": "TGCTGTTGACAGTGAGCG",
        "loop": "TAGTGAAGCCACAGATGTA",
        "flank3": "TGCCTACTGCCTCGGA",
        "guide_arm": "3p",
        "length": 97,
        #: Verificado el 97-mero. NO los flancos extendidos del pri-miR.
        "verified": True,
    }
)

PASSENGER_RULE_CONFIRMED = False
PASSENGER_RULE_TAG = "REGLA_NO_CONFIRMADA"
PASSENGER_RULE_WARNING = (
    f"{PASSENGER_RULE_TAG}: el desapareamiento de la posicion 1 de la pasajera "
    f"(transicion T↔C) esta derivado de UN SOLO ejemplo (SGEP #111170). Antes de "
    f"fijarlo hay que verificarlo contra un segundo plasmido miR-E con otra guia "
    f"(LT3GEPIR #111177). No pidas estos oligos dando la regla por buena."
)

EXTENDED_FLANKS_STATUS = (
    "sin decidir: los flancos extendidos del pri-miR (necesarios para el cassette AAV, "
    "no para el clonaje en SGEP) todavia no estan verificados"
)

#: Transicion observada. A y G no aparecen en el unico ejemplo disponible.
TRANSITION = MappingProxyType({"T": "C", "C": "T"})


def _validate_arm(sequence: str, *, name: str = "guia") -> str:
    """Normaliza a ADN y valida. Una N aqui es un oligo que no se puede pedir."""
    cleaned = "".join(str(sequence).split()).upper().replace("U", "T")
    if len(cleaned) != ARM_LENGTH:
        raise ValueError(
            f"La {name} mide {len(cleaned)} nt y el andamio miR-E lleva brazos de "
            f"{ARM_LENGTH} nt; se aborta el montaje de la horquilla."
        )
    for index, base in enumerate(cleaned, start=1):
        if base not in DNA_BASES:
            raise InvalidSequenceError(
                f"{name}: caracter {base!r} no valido en la posicion {index} "
                f"(se esperaba A, C, G o T/U). Un oligo no se puede sintetizar con una "
                f"base desconocida; se aborta el montaje de la horquilla."
            )
    return cleaned


def reverse_complement(sequence: str) -> str:
    return sequence.translate(COMPLEMENT)[::-1]


@dataclass(frozen=True)
class Passenger:
    sequence: str
    reverse_complement: str
    base_original: str
    base_final: str
    transition_applied: bool
    warnings: tuple[str, ...] = field(default=())


def passenger_from_guide(guide: str) -> Passenger:
    """Pasajera del andamio: revcomp de la guia con la transicion en la posicion 1."""
    cleaned = _validate_arm(guide)
    revcomp = reverse_complement(cleaned)
    original = revcomp[0]
    warnings = [PASSENGER_RULE_WARNING]

    final = TRANSITION.get(original)
    if final is None:
        warnings.append(
            f"La posicion 1 del complementario reverso es {original}: la transicion NO "
            f"se ha aplicado. El unico ejemplo verificado (SGEP #111170) tiene T→C, y "
            f"no hay ninguno con {original}. Decide tu que base va ahi antes de pedir "
            f"el oligo."
        )
        return Passenger(
            sequence=revcomp,
            reverse_complement=revcomp,
            base_original=original,
            base_final=original,
            transition_applied=False,
            warnings=tuple(warnings),
        )

    return Passenger(
        sequence=final + revcomp[1:],
        reverse_complement=revcomp,
        base_original=original,
        base_final=final,
        transition_applied=True,
        warnings=tuple(warnings),
    )


@dataclass(frozen=True)
class Hairpin:
    sequence: str
    guide: str
    passenger: Passenger
    scaffold_name: str

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.passenger.warnings

    def format_text(self) -> str:
        lines = [
            f"Horquilla miR-E ({self.scaffold_name}) — {len(self.sequence)} nt",
            "",
            f"  {self.sequence}",
            "",
            "  Piezas (5'→3'):",
            f"    flanco 5'  {SCAFFOLD['flank5']}  ({len(SCAFFOLD['flank5'])} nt, verificado)",
            f"    pasajera   {self.passenger.sequence}  ({ARM_LENGTH} nt)",
            f"    loop       {SCAFFOLD['loop']}  ({len(SCAFFOLD['loop'])} nt, verificado)",
            f"    guia       {self.guide}  ({ARM_LENGTH} nt, brazo {SCAFFOLD['guide_arm']})",
            f"    flanco 3'  {SCAFFOLD['flank3']}  ({len(SCAFFOLD['flank3'])} nt, verificado)",
            "",
            f"  Pasajera: complementario reverso {self.passenger.reverse_complement}",
        ]
        if self.passenger.transition_applied:
            lines.append(
                f"            con la posicion 1 cambiada "
                f"{self.passenger.base_original}→{self.passenger.base_final} "
                f"(desapareamiento deliberado del andamio)"
            )
        else:
            lines.append("            SIN cambiar la posicion 1 (ver aviso)")

        lines.append("")
        for warning in self.warnings:
            lines.append(f"  ⚠  {warning}")
        return "\n".join(lines)


def build_hairpin(guide: str) -> Hairpin:
    """Monta el 97-mero listo para pedir. La guia va en el brazo 3p."""
    cleaned = _validate_arm(guide)
    passenger = passenger_from_guide(cleaned)
    sequence = (
        SCAFFOLD["flank5"]
        + passenger.sequence
        + SCAFFOLD["loop"]
        + cleaned
        + SCAFFOLD["flank3"]
    )
    if len(sequence) != SCAFFOLD["length"]:
        raise ValueError(
            f"La horquilla montada mide {len(sequence)} nt y el andamio verificado son "
            f"{SCAFFOLD['length']}; se aborta en vez de entregar un oligo que no "
            f"corresponde al andamio."
        )
    return Hairpin(
        sequence=sequence,
        guide=cleaned,
        passenger=passenger,
        scaffold_name=SCAFFOLD["name"],
    )


def extended_cassette(guide: str) -> str:
    """Horquilla con los flancos extendidos del pri-miR. No disponible."""
    raise NotImplementedError(
        f"Los flancos extendidos del pri-miR estan {EXTENDED_FLANKS_STATUS}. "
        f"Lo verificado es el 97-mero de SGEP y solo eso; no se inventan flancos para "
        f"completar un cassette AAV."
    )
