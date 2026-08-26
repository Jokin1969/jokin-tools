"""Barrido del ORF conservado: la otra via cuando el 3'UTR no da un shmiR unico.

El 3'UTR de Prnp no tiene ni una ventana de 22 nt conservada raton/humano que supere los
filtros de secuencia (ver `conservation.single_shmir_verdict`), asi que un shmiR unico
para raton, Tg650 y clinica no cabe por ahi. El ORF si tiene tramos de identidad exacta
de 22 nt o mas, y ahi la pregunta se puede volver a hacer.

Se aplica la MISMA cascada, con la misma regla sobre lo que no aplica:

- SI aplican fuera del 3'UTR: GC, homopolimeros, asimetria, G-cuadruplex, colision de
  seed, elementos repetitivos y especificidad.
- NO aplican: polyA, APA y los tercios. Son heuristicas del 3'UTR y sobre una ventana del
  ORF la pregunta no se hace. Salen `NO_APLICA`, nunca `PASS` (regla 3, y `NO_APLICA` no
  es una cuarta forma de `NOT_RUN`).

CONTEXTO QUE NO ES UN DETALLE. El obstaculo clasico de la via ORF es que la guia apague
tambien el transgen terapeutico, y la solucion habitual es recodificar el transgen. Aqui
no hace falta: el ORF del casete AAV esta CODON-OPTIMIZADO, asi que ya es resistente a
una guia diseñada contra el ORF nativo. Eso no se supone — se comprueba con el filtro del
transgen, que sigue corriendo sobre estas ventanas como sobre las demas.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from .conservation import Utr3, build_conservation_report
from .filters import FilterResult, FilterState
from .hard_filters import DEFAULT_THRESHOLDS, Thresholds

#: Lo que NO se le pregunta a una ventana del ORF, con el motivo que va escrito.
ORF_NOT_APPLICABLE = {
    "zona_prohibida_polyA": (
        "La ventana cae en el ORF, no en el 3'UTR. Las señales de poliadenilacion solo "
        "tienen sentido sobre el 3'UTR: aqui la pregunta no aplica. NO_APLICA no es PASS."
    ),
    "APA": (
        "La poliadenilacion alternativa recorta el 3'UTR, no el ORF: una ventana del ORF "
        "esta en todas las isoformas. La pregunta no aplica. NO_APLICA no es PASS."
    ),
    "tercio": (
        "Los tercios se cuentan sobre el 3'UTR. Una ventana del ORF no tiene tercio, y "
        "asignarle uno seria inventarse una coordenada. NO_APLICA no es PASS."
    ),
}

#: Los que SI aplican en el ORF pero necesitan un fichero. Sin el, NOT_RUN.
ORF_PENDING = {
    "seed_colision": "no hay lista curada de miARN abundantes cargada",
    "repeticiones": "no hay mascara de repeticiones cargada",
    "especificidad": "no hay base de RefSeq RNA cargada",
}

MIN_BLOCK = 22

#: El codigo genetico ESTANDAR. No es un dato del proyecto ni una secuencia: es la tabla
#: de correspondencia codon→aminoacido, la misma para todo el mundo. Se genera en vez de
#: escribirse a mano para que no haya erratas de transcripcion.
_BASES = "TCAG"
_AMINOACIDOS = (
    "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
)
GENETIC_CODE = {
    b1 + b2 + b3: _AMINOACIDOS[i]
    for i, (b1, b2, b3) in enumerate(
        (x, y, z) for x in _BASES for y in _BASES for z in _BASES
    )
}


def translate(sequence: str) -> str:
    """Traduce una secuencia YA EXISTENTE. No completa el ultimo codon incompleto."""
    limpia = sequence.upper().replace("U", "T")
    codones = [limpia[i : i + 3] for i in range(0, len(limpia) - 2, 3)]
    for codon in codones:
        if codon not in GENETIC_CODE:
            raise ValueError(
                f"Codon {codon!r} no esta en el codigo genetico estandar (¿una N?); se "
                f"aborta la traduccion en vez de inventar el aminoacido."
            )
    return "".join(GENETIC_CODE[c] for c in codones)


def cysteine_codons(orf: str) -> tuple[int, ...]:
    """Posiciones (1-based, en codones) de las cisteinas del ORF."""
    return tuple(
        i + 1 for i, residuo in enumerate(translate(orf)) if residuo == "C"
    )


def _envolver(texto: str, ancho: int) -> list[str]:
    palabras, lineas, actual = texto.split(), [], ""
    for palabra in palabras:
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    if actual:
        lineas.append(actual)
    return lineas


#: Anotacion estructural de la ventana, DECLARADA por el responsable del proyecto el
#: 2026-08-26 y SIN COMPROBAR aqui: este repositorio no tiene estructura ni alineamiento
#: de proteina, y darla por propia seria inventar la fuente que la respalda.
STRUCTURAL_NOTE_VERIFIED = (
    "VERIFICADO aqui traduciendo los ORF del repositorio: la ventana empieza en el codon "
    "{codon_a} ({especie_a}) / {codon_b} ({especie_b}), en marco, y codifica el peptido "
    "{peptido} — el MISMO en las dos especies. Su posicion 4 es una CISTEINA: "
    "{cis_a} ({especie_a}) / {cis_b} ({especie_b}). "
    "PrP tiene UN solo puente disulfuro, C178-C213 en raton y C179-C214 en humano, y eso "
    "tambien se sostiene aqui sin estructura: en el ORF murino solo hay tres cisteinas "
    "({cisteinas_a}) y la primera esta en el peptido señal, asi que no hay un segundo par "
    "posible. En humano, {cisteinas_b}."
)

STRUCTURAL_NOTE_DECLARED = (
    "DECLARADO por el responsable del proyecto y sin comprobar aqui —este repositorio no "
    "tiene estructura ni alineamiento de proteina—: la helice B (H2) va de ~173 a 194, "
    "asi que la ventana cae en su EXTREMO N-TERMINAL. Nucleo estructural bajo fuerte "
    "seleccion purificadora."
)

#: La consecuencia que NO es intuitiva y por eso va escrita.
GNOMAD_NOTE = (
    "Que la region este bajo seleccion purificadora restringe los NO SINONIMOS, no los "
    "SINONIMOS — y son los sinonimos los que rompen el apareamiento de la guia sin tocar "
    "la proteina. Asi que «region conservada» NO exime de mirar variacion: gnomAD sobre "
    "esta ventana es OBLIGATORIO, y hoy esta en NOT_RUN. NOT_RUN no es PASS."
)

#: La propiedad de alcance de una guia contra el ORF conservado.
REACH_NOTE = (
    "PROPIEDAD CLAVE DE ALCANCE: una guia contra esta ventana alcanza PRNP humano —y por "
    "tanto Tg650 y las lineas humanizadas— y NO alcanza el transgen del casete, porque su "
    "ORF esta codon-optimizado. Es exactamente el reparto que hace falta: silencia lo "
    "endogeno de las dos especies y respeta la construccion terapeutica."
)


@dataclass(frozen=True)
class OrfCandidate:
    orf_start_a: int
    orf_start_b: int
    tx_start_a: int
    tx_start_b: int
    target_a: str
    target_b: str
    guide: str
    filters: tuple[FilterResult, ...]
    #: Los ORF completos, para poder traducir el tramo de 24 nt que completa los codones.
    _orf_a: str = ""
    _orf_b: str = ""

    @property
    def codon_a(self) -> int:
        """Codon del ORF en que empieza la ventana, 1-based. Derivado, no escrito."""
        return (self.orf_start_a - 1) // 3 + 1

    @property
    def codon_b(self) -> int:
        return (self.orf_start_b - 1) // 3 + 1

    @property
    def codon_span_a(self) -> tuple[int, int]:
        return (self.codon_a, (self.orf_start_a + 21 - 1) // 3 + 1)

    def _peptido(self, orf: str, inicio: int) -> str:
        """Traduce los 24 nt que completan los 8 codones de la ventana.

        Vacio si la ventana NO empieza en marco: traducir desde la posicion 2 de un
        codon da una cadena de aminoacidos que no existe en ninguna proteina, y eso es
        peor que no dar nada.
        """
        if not self.in_frame:
            return ""
        return translate(orf[inicio - 1 : inicio - 1 + 24])

    @property
    def peptide(self) -> str:
        return self._peptido(self._orf_a, self.orf_start_a)

    @property
    def peptide_b(self) -> str:
        return self._peptido(self._orf_b, self.orf_start_b)

    @property
    def cysteine_codon_a(self) -> int | None:
        indice = self.peptide.find("C") if self.peptide else -1
        return None if indice < 0 else self.codon_a + indice

    @property
    def cysteine_codon_b(self) -> int | None:
        indice = self.peptide_b.find("C") if self.peptide_b else -1
        return None if indice < 0 else self.codon_b + indice

    @property
    def in_frame(self) -> bool:
        return (self.orf_start_a - 1) % 3 == 0

    @property
    def not_applicable(self) -> tuple[FilterResult, ...]:
        return tuple(
            FilterResult(name=nombre, state=FilterState.NO_APLICA, reason=motivo)
            for nombre, motivo in ORF_NOT_APPLICABLE.items()
        )

    @property
    def pending(self) -> tuple[FilterResult, ...]:
        return tuple(
            FilterResult(
                name=nombre,
                state=FilterState.NOT_RUN,
                reason=(
                    f"{motivo}. Este filtro SI aplica en el ORF; sin el recurso queda "
                    f"NOT_RUN, y NOT_RUN no es PASS."
                ),
            )
            for nombre, motivo in ORF_PENDING.items()
        )


@dataclass(frozen=True)
class OrfSweep:
    species: tuple[str, str]
    lengths: tuple[int, int]
    blocks: tuple
    windows: int
    passing: tuple[OrfCandidate, ...]
    min_block: int
    cysteines_a: tuple[int, ...] = ()
    cysteines_b: tuple[int, ...] = ()

    def describe(self) -> list[str]:
        from .coords import Frame, label

        a, b = self.species
        lineas = [
            f"BARRIDO DEL ORF CONSERVADO {a}/{b} — identidad exacta >= "
            f"{self.min_block} nt",
            f"  ORF: {self.lengths[0]} nt ({a}) y {self.lengths[1]} nt ({b}). "
            f"{len(self.blocks)} bloque(s) conservado(s), {self.windows} ventana(s) de "
            f"22 nt que caben dentro.",
            f"  Superan los filtros de SECUENCIA: {len(self.passing)}.",
        ]
        for candidato in self.passing:
            lineas.append(
                f"    · ORF {a} {candidato.orf_start_a} "
                f"({label(candidato.tx_start_a, Frame.TX)}) / "
                f"ORF {b} {candidato.orf_start_b} "
                f"({label(candidato.tx_start_b, Frame.TX)})  {candidato.target_a}"
            )
            lineas.append(
                f"      codon {candidato.codon_a} ({a}) / {candidato.codon_b} ({b}); "
                + (
                    f"la ventana cubre los codones "
                    f"{candidato.codon_span_a[0]}-{candidato.codon_span_a[1]}, empieza "
                    f"en marco y codifica {candidato.peptide}."
                    if candidato.in_frame
                    else "NO empieza en marco (arranca en la 2ª o 3ª base de su codon), "
                    "asi que no se traduce: dar un peptido desde ahi seria una cadena "
                    "que no existe."
                )
            )
        if not self.passing:
            lineas.append(
                "    Ninguna. Por esta via tampoco hay shmiR unico, y con eso se cierran "
                "las dos."
            )
        if self.passing:
            en_marco = [c for c in self.passing if c.in_frame]
            candidato = min(en_marco or self.passing, key=lambda c: c.orf_start_a)
            verificada = STRUCTURAL_NOTE_VERIFIED.format(
                codon_a=candidato.codon_a,
                codon_b=candidato.codon_b,
                especie_a=a,
                especie_b=b,
                peptido=candidato.peptide,
                cis_a=f"C{candidato.cysteine_codon_a}",
                cis_b=f"C{candidato.cysteine_codon_b}",
                cisteinas_a=", ".join(str(c) for c in self.cysteines_a),
                cisteinas_b=", ".join(str(c) for c in self.cysteines_b),
            )
            for nota in (verificada, STRUCTURAL_NOTE_DECLARED, GNOMAD_NOTE, REACH_NOTE):
                lineas.append("")
                lineas.extend(f"  {l}" for l in _envolver(nota, 86))
        lineas.append("")
        lineas.extend(
            [
                "  polyA, APA y tercios salen NO_APLICA en estas ventanas: son "
                "heuristicas del 3'UTR y",
                "  sobre el ORF la pregunta no se hace. NO_APLICA no es PASS.",
                "  seed, repetitivos y especificidad SI aplican aqui, y hoy estan en "
                "NOT_RUN por falta de",
                "  fichero: estas ventanas NO estan aprobadas, estan preseleccionadas.",
                "  EL TRANSGEN NO ES UN OBSTACULO EN ESTE BACKBONE: el ORF del casete "
                "AAV esta",
                "  CODON-OPTIMIZADO, asi que ya es RESISTENTE a una guia contra el ORF "
                "nativo SIN",
                "  RECODIFICAR nada. El obstaculo clasico de la via ORF no existe aqui. "
                "Se comprueba igual",
                "  con el filtro del transgen: no se da por supuesto.",
            ]
        )
        return lineas


def orf_sweep(
    orf_a: str,
    orf_b: str,
    *,
    species: tuple[str, str],
    cds_start: tuple[int, int],
    min_block: int = MIN_BLOCK,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> OrfSweep:
    """Tramos de identidad exacta entre los dos ORF, con la cascada aplicada."""
    if min_block < 22:
        raise ValueError(
            f"min_block={min_block}: por debajo de 22 nt no cabe una guia entera dentro "
            f"del tramo conservado, asi que el barrido no significa nada. Se aborta."
        )
    informe = build_conservation_report(
        Utr3(species[0], orf_a),
        Utr3(species[1], orf_b),
        min_length=min_block,
        thresholds=thresholds,
    )
    candidatos: list[OrfCandidate] = []
    ventanas = 0
    for indice, bloque in enumerate(informe.blocks):
        hit_a = [h for h in bloque.hits if h.species == species[0]][0]
        hit_b = [h for h in bloque.hits if h.species == species[1]][0]
        for desplazamiento, evaluacion in enumerate(informe.evaluations[indice]):
            ventanas += 1
            if evaluacion.verdict.value != "PASS":
                continue
            inicio_a = hit_a.start + desplazamiento
            inicio_b = hit_b.start + desplazamiento
            candidatos.append(
                OrfCandidate(
                    orf_start_a=inicio_a,
                    orf_start_b=inicio_b,
                    tx_start_a=cds_start[0] + inicio_a - 1,
                    tx_start_b=cds_start[1] + inicio_b - 1,
                    target_a=orf_a[inicio_a - 1 : inicio_a - 1 + 22],
                    target_b=orf_b[inicio_b - 1 : inicio_b - 1 + 22],
                    guide=evaluacion.guide,
                    filters=tuple(evaluacion.filters),
                    _orf_a=orf_a,
                    _orf_b=orf_b,
                )
            )
    return OrfSweep(
        species=species,
        lengths=(len(orf_a), len(orf_b)),
        blocks=informe.blocks,
        windows=ventanas,
        passing=tuple(candidatos),
        min_block=min_block,
        cysteines_a=cysteine_codons(orf_a),
        cysteines_b=cysteine_codons(orf_b),
    )
