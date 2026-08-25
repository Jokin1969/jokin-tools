"""Andamio miR-E: montaje de la horquilla de 97 nt (salida de oligos).

Andamio SGEP (Addgene #111170), verificado contra el fichero SnapGene de la secuencia
depositada y coincidente con tres fuentes:

    flanco5 + PASAJERA(22) + loop + GUIA(22) + flanco3  = 97 nt

La guia va en el brazo 3p. `SCAFFOLD["verified"] = True` se refiere **solo** al 97-mero:
los flancos extendidos del pri-miR que hacen falta para el cassette AAV siguen sin
decidir y este modulo se niega a inventarlos.

## La regla de la pasajera (resuelta)

La pasajera no es el complementario reverso exacto de la guia: lleva un desapareamiento
deliberado en su posicion 1, que es la que aparearia con la posicion 22 de la guia.

**Regla: la posicion 1 de la pasajera nunca puede ser el complemento Watson-Crick de la
posicion 22 de la guia.** Si lo es, el tallo se cierra y desaparece el bulge basal.
Cualquiera de las otras tres bases da una estructura identica base a base a la de SGEP,
con el mismo ΔG, asi que la eleccion entre ellas es una convencion: se usa C, y A cuando
la C es justo la prohibida (guia acabada en G).

Evidencia: dos vectores publicados independientes (SGEP #111170 y LT3GEPIR #111177)
llevan la misma horquilla shRen.713 con la misma pasajera, lo que confirma que el
desapareamiento es deliberado pero no discrimina entre lecturas; lo resuelve el plegado
del 97-mero completo, comprobado con ViennaRNA.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from .errors import InvalidSequenceError

ARM_LENGTH = 22
DNA_BASES = frozenset("ACGT")
COMPLEMENT = str.maketrans("ACGT", "TGCA")

UNVERIFIED_TAG = "ANDAMIO_NO_VERIFICADO"
UNVERIFIED_WARNING = (
    f"{UNVERIFIED_TAG}: las secuencias flanqueantes de este andamio NO han sido "
    f"contrastadas contra la publicacion original. Un flanco equivocado da una "
    f"horquilla que se sintetiza igual de bien y no procesa. Contrastalas antes de "
    f"pedir nada."
)

REQUIRED_KEYS = ("nombre", "flanco5", "loop", "flanco3")
OPTIONAL_KEYS = ("guide_arm", "verificado", "fuente", "notas")


@dataclass(frozen=True)
class ScaffoldSpec:
    """Andamio parametrizable.

    `verified` es False por defecto **a proposito**: un andamio que nadie ha
    contrastado contra su publicacion no puede pasar por verificado por omision. Con
    False, toda salida de oligos lleva el aviso `ANDAMIO_NO_VERIFICADO`, y no hay forma
    de silenciarlo: no existe parametro para ello en ninguna funcion de este modulo.
    """

    name: str
    flank5: str
    loop: str
    flank3: str
    guide_arm: str = "3p"
    verified: bool = False
    source: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        for nombre, pieza in (
            ("flanco5", self.flank5),
            ("loop", self.loop),
            ("flanco3", self.flank3),
        ):
            if not pieza:
                raise ValueError(
                    f"El andamio {self.name!r} no tiene {nombre}; se aborta el montaje."
                )
            for index, base in enumerate(pieza.upper(), start=1):
                if base not in DNA_BASES:
                    raise InvalidSequenceError(
                        f"Andamio {self.name!r}, {nombre}: caracter {base!r} no valido "
                        f"en la posicion {index}; se aborta el montaje."
                    )
        if self.guide_arm not in ("3p", "5p"):
            raise ValueError(
                f"Andamio {self.name!r}: guide_arm={self.guide_arm!r}; solo 3p o 5p."
            )

    @property
    def length(self) -> int:
        return len(self.flank5) + len(self.loop) + len(self.flank3) + 2 * ARM_LENGTH

    @property
    def warnings(self) -> tuple[str, ...]:
        return () if self.verified else (UNVERIFIED_WARNING,)


def load_scaffold(path: Path | str) -> ScaffoldSpec:
    """Lee un andamio de un fichero TOML. `verificado` es False si no se declara."""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"No existe el fichero de andamio {path}; se aborta el montaje de oligos."
        ) from exc
    except OSError as exc:
        raise OSError(
            f"No se pudo leer el fichero de andamio {path} ({exc}); se aborta el "
            f"montaje de oligos."
        ) from exc

    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"{path} no es TOML valido ({exc}); se aborta el montaje de oligos."
        ) from exc

    faltan = [key for key in REQUIRED_KEYS if key not in data]
    if faltan:
        raise ValueError(
            f"{path}: faltan las claves {', '.join(faltan)}; se aborta el montaje en "
            f"vez de completar el andamio con nada."
        )
    sobran = [key for key in data if key not in REQUIRED_KEYS + OPTIONAL_KEYS]
    if sobran:
        raise ValueError(
            f"{path}: claves desconocidas {', '.join(sobran)}. Se aborta: una clave mal "
            f"escrita que se ignora en silencio es un andamio equivocado."
        )

    return ScaffoldSpec(
        name=str(data["nombre"]),
        flank5=str(data["flanco5"]).upper(),
        loop=str(data["loop"]).upper(),
        flank3=str(data["flanco3"]).upper(),
        guide_arm=str(data.get("guide_arm", "3p")),
        verified=bool(data.get("verificado", False)),
        source=str(data.get("fuente", f"fichero {path}")),
        notes=str(data.get("notas", "")),
    )


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

PASSENGER_RULE_CONFIRMED = True
PASSENGER_RULE_SOURCE = (
    "SGEP #111170 y LT3GEPIR #111177 llevan la misma horquilla shRen.713 con la misma "
    "pasajera; el plegado del 97-mero completo (ViennaRNA) confirma que aparear la "
    "posicion 1 en Watson-Crick cierra el tallo y borra el bulge basal, y que las otras "
    "tres bases dan una estructura identica base a base"
)

#: Base preferida para el desapareamiento, y la alternativa cuando esa es la prohibida.
DEFAULT_MISMATCH_BASE = "C"
FALLBACK_MISMATCH_BASE = "A"

#: 97-mero real de SGEP con la guia shRen.713. Es la estructura de referencia contra la
#: que se compara el plegado de cualquier horquilla nueva.
REFERENCE_GUIDE = "TAGATAAGCATTATAATTCCTA"
REFERENCE_HAIRPIN = (
    "TGCTGTTGACAGTGAGCGCAGGAATTATAATGCTTATCTATAGTGAAGCCACAGATGTA"
    "TAGATAAGCATTATAATTCCTATGCCTACTGCCTCGGA"
)

EXTENDED_FLANKS_STATUS = (
    "sin decidir: los flancos extendidos del pri-miR (necesarios para el cassette AAV, "
    "no para el clonaje en SGEP) todavia no estan verificados"
)



#: Andamio verificado contra SGEP #111170. Es el unico con `verified=True`.
SGEP_SCAFFOLD = ScaffoldSpec(
    name=SCAFFOLD["name"],
    flank5=SCAFFOLD["flank5"],
    loop=SCAFFOLD["loop"],
    flank3=SCAFFOLD["flank3"],
    guide_arm=SCAFFOLD["guide_arm"],
    verified=True,
    source=SCAFFOLD["source"],
    notes="Verificado el 97-mero. NO los flancos extendidos del pri-miR.",
)


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
    #: La base que apareceria en el complementario reverso: el complemento Watson-Crick
    #: de la posicion 22 de la guia. Es justo la que NO puede ir en la posicion 1.
    forbidden_base: str
    chosen_base: str
    mismatch_applied: bool
    warnings: tuple[str, ...] = field(default=())


def passenger_from_guide(guide: str) -> Passenger:
    """Pasajera del andamio: revcomp de la guia con la posicion 1 desapareada.

    La posicion 1 nunca es el complemento Watson-Crick de la posicion 22 de la guia.
    """
    cleaned = _validate_arm(guide)
    revcomp = reverse_complement(cleaned)
    forbidden = revcomp[0]
    chosen = (
        FALLBACK_MISMATCH_BASE
        if DEFAULT_MISMATCH_BASE == forbidden
        else DEFAULT_MISMATCH_BASE
    )
    if chosen == forbidden:  # imposible por construccion; si pasa, es un fallo nuestro
        raise ValueError(
            f"La base elegida para la posicion 1 de la pasajera ({chosen}) es la "
            f"prohibida: aparearia en Watson-Crick con la posicion 22 de la guia y "
            f"cerraria el tallo. Se aborta el montaje."
        )

    return Passenger(
        sequence=chosen + revcomp[1:],
        reverse_complement=revcomp,
        forbidden_base=forbidden,
        chosen_base=chosen,
        mismatch_applied=True,
    )


@dataclass(frozen=True)
class Hairpin:
    sequence: str
    guide: str
    passenger: Passenger
    scaffold: ScaffoldSpec

    @property
    def scaffold_name(self) -> str:
        return self.scaffold.name

    @property
    def warnings(self) -> tuple[str, ...]:
        """Avisos del oligo. No hay forma de silenciarlos: no es un parametro."""
        return self.scaffold.warnings + self.passenger.warnings

    @property
    def _sello(self) -> str:
        return "verificado" if self.scaffold.verified else "SIN VERIFICAR"

    def format_text(self) -> str:
        lines = [
            f"Horquilla miR-E ({self.scaffold_name}) — {len(self.sequence)} nt",
            "",
            f"  {self.sequence}",
            "",
            "  Piezas (5'→3'):",
            f"    flanco 5'  {self.scaffold.flank5}  "
            f"({len(self.scaffold.flank5)} nt, {self._sello})",
            f"    pasajera   {self.passenger.sequence}  ({ARM_LENGTH} nt)",
            f"    loop       {self.scaffold.loop}  "
            f"({len(self.scaffold.loop)} nt, {self._sello})",
            f"    guia       {self.guide}  ({ARM_LENGTH} nt, brazo "
            f"{self.scaffold.guide_arm})",
            f"    flanco 3'  {self.scaffold.flank3}  "
            f"({len(self.scaffold.flank3)} nt, {self._sello})",
            "",
            f"  Pasajera: complementario reverso {self.passenger.reverse_complement}",
        ]
        lines.append(
            f"            con la posicion 1 en {self.passenger.chosen_base} y no en "
            f"{self.passenger.forbidden_base}: apareada en Watson-Crick con la posicion "
            f"22 de la guia, el tallo se cierra y desaparece el bulge basal"
        )

        lines.append("")
        for warning in self.warnings:
            lines.append(f"  ⚠  {warning}")
        return "\n".join(lines)


def build_hairpin(guide: str, scaffold: ScaffoldSpec = SGEP_SCAFFOLD) -> Hairpin:
    """Monta la horquilla lista para pedir. La guia va en el brazo indicado.

    No hay parametro para silenciar los avisos, y no lo habra: el aviso de andamio sin
    contrastar y el de la regla no confirmada viajan con el oligo.
    """
    cleaned = _validate_arm(guide)
    passenger = passenger_from_guide(cleaned)
    brazos = (
        (passenger.sequence, cleaned)
        if scaffold.guide_arm == "3p"
        else (cleaned, passenger.sequence)
    )
    sequence = (
        scaffold.flank5 + brazos[0] + scaffold.loop + brazos[1] + scaffold.flank3
    )
    if len(sequence) != scaffold.length:
        raise ValueError(
            f"La horquilla montada mide {len(sequence)} nt y el andamio "
            f"{scaffold.name!r} declara {scaffold.length}; se aborta en vez de entregar "
            f"un oligo que no corresponde al andamio."
        )
    return Hairpin(
        sequence=sequence,
        guide=cleaned,
        passenger=passenger,
        scaffold=scaffold,
    )


def extended_cassette(guide: str) -> str:
    """Horquilla con los flancos extendidos del pri-miR. No disponible."""
    raise NotImplementedError(
        f"Los flancos extendidos del pri-miR estan {EXTENDED_FLANKS_STATUS}. "
        f"Lo verificado es el 97-mero de SGEP y solo eso; no se inventan flancos para "
        f"completar un cassette AAV."
    )
