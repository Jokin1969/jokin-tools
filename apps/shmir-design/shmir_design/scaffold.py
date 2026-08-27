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

**Regla: entre las cuatro bases, se elige una cuyo 97-mero pliegue con notacion
punto-parentesis IDENTICA a la del 97-mero de SGEP.** Si hay varias, manda el orden de
preferencia C > A > G > T para que la salida sea determinista. Si ninguna la reproduce,
se aborta enseñando las cuatro estructuras: no se elige por defecto.

### Por que un criterio estructural y NO una tabla por terminacion

Porque una tabla por terminacion es exactamente lo que fallo. La regla anterior era
"C por defecto, A cuando la C es la prohibida por Watson-Crick", y le faltaba el
apareamiento tambaleante: **G:U aparea en ARN**. Con guia acabada en G, la C esta
prohibida por Watson-Crick y la T tambien lo esta por wobble; la tabla elegia A, que no
aparea con nada — y aun asi la estructura sale distinta, con un bulge de 2 nt en vez de
1. Comprobado plegando las guias del proyecto: con `TAATTGAAAGAGCTACAGGTGG` y
`TAAAGGAATGCCACATATAGGG` solo la G reproduce la estructura de referencia.

El criterio estructural subsume Watson-Crick y wobble sin enumerarlos, y no depende de
que hayamos previsto todos los casos. **No lo sustituyas por una tabla, por rapida que
parezca**: la lista de restricciones que hay que prever es justo lo que no sabemos.

Evidencia: dos vectores publicados independientes (SGEP #111170 y LT3GEPIR #111177)
llevan la misma horquilla shRen.713 con la misma pasajera, lo que confirma que el
desapareamiento es deliberado pero no discrimina entre lecturas; lo resuelve el plegado
del 97-mero completo, comprobado con ViennaRNA.

**Otra lectura del mismo hecho, y es la mejor explicacion:** el flanco 5' del andamio
seria `TGCTGTTGACAGTGAGCGC` —19 nt, con una C fija de scaffold— y la pasajera 21 nt.
Eso explica SGEP y LT3GEPIR sin necesidad de regla ninguna, y monta exactamente el
mismo 97-mero que este modulo... **salvo cuando la guia acaba en G**. Ahi la C fija
seria justo el complemento Watson-Crick de la posicion 22, cerraria el tallo y borraria
el bulge (comprobado plegando). El criterio estructural resuelve ese caso solo, sin
excepciones escritas: pliega las cuatro y se queda con la que funciona, que ahi es la G.
Si alguien "simplifica" esto dejando la C siempre porque "es scaffold", rompe esas guias
en silencio.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from .errors import InvalidSequenceError, ShmirDesignError
from .filters import FilterState

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
                        f"Andamio {self.name!r}, {nombre}: carácter {base!r} no válido "
                        f"en la posición {index}; se aborta el montaje."
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
            f"{path} no es TOML válido ({exc}); se aborta el montaje de oligos."
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
    "posición 1 en Watson-Crick cierra el tallo y borra el bulge basal. Cuántas bases "
    "reproducen la estructura depende de la guía: con guía acabada en A o en C hay "
    "tres, y con guía acabada en G solo la G — la C aparea en Watson-Crick, la T por "
    "wobble G:U, y la A deja un bulge de 2 nt en vez de 1. Por eso la elección es "
    "estructural y no una tabla por terminacion"
)

#: Orden de preferencia entre las bases que SI reproducen la estructura de referencia.
#: Solo desempata; no decide. Quien decide es el plegado.
MISMATCH_PREFERENCE = ("C", "A", "G", "T")

#: Apareamientos tambaleantes que hay que tener en cuenta en la posicion 1. Estan aqui
#: solo para el camino SIN ViennaRNA y para poder explicarlo en los avisos: el criterio
#: de verdad es estructural y no consulta esta tabla.
WOBBLE_PAIRS = {"G": "T", "T": "G"}

#: 97-mero real de SGEP con la guia shRen.713. Es la estructura de referencia contra la
#: que se compara el plegado de cualquier horquilla nueva.
REFERENCE_GUIDE = "TAGATAAGCATTATAATTCCTA"
REFERENCE_HAIRPIN = (
    "TGCTGTTGACAGTGAGCGCAGGAATTATAATGCTTATCTATAGTGAAGCCACAGATGTA"
    "TAGATAAGCATTATAATTCCTATGCCTACTGCCTCGGA"
)

EXTENDED_FLANKS_STATUS = (
    "sin decidir: los flancos extendidos del pri-miR (necesarios para el cassette AAV, "
    "no para el clonaje en SGEP) todavia no están verificados"
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
                f"{name}: carácter {base!r} no válido en la posición {index} "
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
    #: Todas las bases que reproducen la estructura de referencia. La elegida es la
    #: primera segun `MISMATCH_PREFERENCE`; el resto se guardan para poder auditarlo.
    candidates: tuple[str, ...] = ()
    #: ¿Se pudo aplicar el criterio estructural? Sin ViennaRNA, NOT_RUN — que no es PASS.
    structural_check: FilterState = FilterState.NOT_RUN
    warnings: tuple[str, ...] = field(default=())


def _hairpin_sequence(guide: str, passenger: str, scaffold: ScaffoldSpec) -> str:
    return scaffold.flank5 + passenger + scaffold.loop + guide + scaffold.flank3


@lru_cache(maxsize=8192)
def passenger_from_guide(
    guide: str,
    *,
    scaffold: ScaffoldSpec | None = None,
    available: bool | None = None,
) -> Passenger:
    """Pasajera del andamio: revcomp de la guia con la posicion 1 desapareada.

    La base de la posicion 1 se elige PLEGANDO las cuatro y quedandose con una que
    reproduzca la estructura de SGEP. Ver el docstring del modulo para por que no vale
    una tabla por terminacion.

    `available=False` fuerza el camino sin ViennaRNA (util para probarlo).
    """
    from .folding import VIENNA_AVAILABLE, dot_bracket  # noqa: PLC0415

    cleaned = _validate_arm(guide)
    revcomp = reverse_complement(cleaned)
    forbidden = revcomp[0]
    wobble = WOBBLE_PAIRS.get(cleaned[-1])
    andamio = scaffold or SGEP_SCAFFOLD

    usable = VIENNA_AVAILABLE if available is None else available
    if not usable:
        # Sin plegado no se puede aplicar el criterio. Se excluye lo que se sabe que
        # aparea (Watson-Crick y wobble) y se deja constancia de que NO esta verificado:
        # esa eleccion esta COMPROBADA como incorrecta para guias acabadas en G.
        posibles = [
            b for b in MISMATCH_PREFERENCE if b != forbidden and b != wobble
        ]
        if not posibles:
            raise ShmirDesignError(
                f"Sin ViennaRNA no queda ninguna base para la posición 1 de la pasajera "
                f"que no aparee con la posición 22 de la guía ({cleaned[-1]}); se "
                f"aborta el montaje."
            )
        elegida = posibles[0]
        return Passenger(
            sequence=elegida + revcomp[1:],
            reverse_complement=revcomp,
            forbidden_base=forbidden,
            chosen_base=elegida,
            mismatch_applied=True,
            candidates=tuple(posibles),
            structural_check=FilterState.NOT_RUN,
            warnings=(
                "ViennaRNA no está instalado, así que la posición 1 de la pasajera NO "
                "se ha elegido por el criterio estructural: solo se han excluido las "
                "bases que aparean en Watson-Crick y por wobble. Eso está COMPROBADO "
                "como insuficiente — con guía acabada en G la elección por exclusión "
                "da un bulge de 2 nt en vez de 1 y la horquilla no es la de SGEP. "
                "NOT_RUN no es PASS: no pidas este bloque sin instalar ViennaRNA.",
            ),
        )

    referencia = dot_bracket(REFERENCE_HAIRPIN)[0]
    estructuras: dict[str, str] = {}
    validas: list[str] = []
    for base in MISMATCH_PREFERENCE:
        estructura = dot_bracket(
            _hairpin_sequence(cleaned, base + revcomp[1:], andamio)
        )[0]
        estructuras[base] = estructura
        if estructura == referencia:
            validas.append(base)

    if not validas:
        detalle = "\n".join(f"    {b}: {estructuras[b]}" for b in MISMATCH_PREFERENCE)
        raise ShmirDesignError(
            f"Ninguna de las cuatro bases reproduce la estructura de la horquilla de "
            f"referencia para la guía {cleaned}. No se elige por defecto: una pasajera "
            f"que no pliega como SGEP monta otra horquilla.\n"
            f"  referencia:\n    {referencia}\n  obtenidas:\n{detalle}"
        )

    elegida = validas[0]
    return Passenger(
        sequence=elegida + revcomp[1:],
        reverse_complement=revcomp,
        forbidden_base=forbidden,
        chosen_base=elegida,
        mismatch_applied=True,
        candidates=tuple(validas),
        structural_check=FilterState.PASS,
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
            f"    guía       {self.guide}  ({ARM_LENGTH} nt, brazo "
            f"{self.scaffold.guide_arm})",
            f"    flanco 3'  {self.scaffold.flank3}  "
            f"({len(self.scaffold.flank3)} nt, {self._sello})",
            "",
            f"  Pasajera: complementario reverso {self.passenger.reverse_complement}",
        ]
        lines.append(
            f"            con la posición 1 en {self.passenger.chosen_base} y no en "
            f"{self.passenger.forbidden_base}: apareada en Watson-Crick con la posición "
            f"22 de la guía, el tallo se cierra y desaparece el bulge basal"
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
        f"Los flancos extendidos del pri-miR están {EXTENDED_FLANKS_STATUS}. "
        f"Lo verificado es el 97-mero de SGEP y solo eso; no se inventan flancos para "
        f"completar un cassette AAV."
    )
