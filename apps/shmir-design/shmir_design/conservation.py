"""Bloques de identidad exacta entre los 3'UTR de dos especies (paso 14).

Un tramo identico en modelo y en clinica es un candidato de altisimo valor: una sola
herramienta valida para los dos. Por eso este modulo es informativo y **nunca**
descarta: los bloques se reportan siempre, aunque ninguna de sus ventanas pase los
filtros duros. La decision de usarlos es del usuario, no del software.

Que hace:

- busca todos los bloques de identidad exacta de >= `min_length` nt (15 por defecto),
  ya extendidos al maximo por ambos lados — un bloque solo termina donde las dos
  secuencias dejan de coincidir;
- da longitud, posicion en cada especie, distancia al extremo 3' en cada especie y %GC;
- para cada bloque de >= 22 nt enumera TODAS las ventanas de 22 nt posibles y las
  evalua con los filtros duros, enseñando el motivo de cada filtro, no solo el fallo.

La `N` (base desconocida) nunca cuenta como identidad: dos posiciones desconocidas no
son un tramo conservado.

Coordenadas 1-based; `distance_to_3p` cuenta los nucleotidos entre el ultimo del bloque
y el extremo 3'. Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .filters import Verdict
from .hard_filters import (
    DEFAULT_THRESHOLDS,
    WINDOW_SIZE,
    AsymmetryModel,
    Thresholds,
    WindowEvaluation,
    evaluate_window,
    gc_fraction,
)
from .polya import normalize_sequence
from .thermo import turner_asymmetry

MIN_BLOCK_LENGTH = 15


@dataclass
class Utr3:
    """3'UTR de una especie, ya validado."""

    name: str
    sequence: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Cada 3'UTR necesita un nombre de especie identificable.")
        self.sequence = normalize_sequence(
            self.sequence, name=f"3'UTR de {self.name}"
        )

    @property
    def length(self) -> int:
        return len(self.sequence)


@dataclass(frozen=True)
class BlockHit:
    species: str
    start: int              # 1-based
    end: int                # 1-based, inclusive
    distance_to_3p: int

    def describe(self) -> str:
        return (
            f"{self.species} {self.start}-{self.end} "
            f"(a {self.distance_to_3p} nt del extremo 3')"
        )


@dataclass(frozen=True)
class ConservedBlock:
    sequence: str
    hits: tuple[BlockHit, ...]

    @property
    def length(self) -> int:
        return len(self.sequence)

    @property
    def gc_fraction(self) -> float:
        return gc_fraction(self.sequence)

    def hit(self, species: str) -> BlockHit:
        for hit in self.hits:
            if hit.species == species:
                return hit
        conocidas = ", ".join(h.species for h in self.hits)
        raise KeyError(
            f"El bloque no tiene posicion para {species!r}; especies del bloque: "
            f"{conocidas}."
        )

    def window_evaluations(
        self,
        *,
        window_size: int = WINDOW_SIZE,
        asymmetry_model: AsymmetryModel | None = turner_asymmetry,
        thresholds: Thresholds = DEFAULT_THRESHOLDS,
    ) -> list[WindowEvaluation]:
        """TODAS las ventanas posibles dentro del bloque, evaluadas una por una."""
        if self.length < window_size:
            return []
        return [
            evaluate_window(
                self.sequence[offset : offset + window_size],
                asymmetry_model=asymmetry_model,
                offset=offset,
                thresholds=thresholds,
            )
            for offset in range(self.length - window_size + 1)
        ]


def _maximal_matches(
    seq_a: str, seq_b: str, min_length: int
) -> set[tuple[int, int, int]]:
    """(inicio en A, inicio en B, longitud) de cada bloque identico maximal, 0-based.

    Indexa los k-meros de A y extiende cada semilla por los dos lados hasta que las
    secuencias dejan de coincidir, que es exactamente "extenderlo al maximo".
    """
    seeds: dict[str, list[int]] = {}
    for i in range(len(seq_a) - min_length + 1):
        kmer = seq_a[i : i + min_length]
        if "N" in kmer:
            continue
        seeds.setdefault(kmer, []).append(i)

    found: set[tuple[int, int, int]] = set()
    for j in range(len(seq_b) - min_length + 1):
        kmer = seq_b[j : j + min_length]
        if "N" in kmer:
            continue
        for i in seeds.get(kmer, ()):
            start_a, start_b = i, j
            while (
                start_a > 0
                and start_b > 0
                and seq_a[start_a - 1] == seq_b[start_b - 1] != "N"
            ):
                start_a -= 1
                start_b -= 1
            end_a, end_b = i + min_length - 1, j + min_length - 1
            while (
                end_a < len(seq_a) - 1
                and end_b < len(seq_b) - 1
                and seq_a[end_a + 1] == seq_b[end_b + 1] != "N"
            ):
                end_a += 1
                end_b += 1
            found.add((start_a, start_b, end_a - start_a + 1))
    return found


def find_conserved_blocks(
    utr_a: Utr3,
    utr_b: Utr3,
    *,
    min_length: int = MIN_BLOCK_LENGTH,
) -> list[ConservedBlock]:
    """Bloques identicos maximales de >= `min_length` nt entre los dos 3'UTR."""
    if min_length < 1:
        raise ValueError(
            f"min_length={min_length} invalido; se aborta la busqueda de bloques."
        )
    if utr_a.name == utr_b.name:
        raise ValueError(
            f"Las dos especies se llaman igual ({utr_a.name!r}); se aborta la busqueda "
            f"para no reportar coordenadas indistinguibles."
        )

    blocks = [
        ConservedBlock(
            sequence=utr_a.sequence[start_a : start_a + length],
            hits=(
                BlockHit(
                    species=utr_a.name,
                    start=start_a + 1,
                    end=start_a + length,
                    distance_to_3p=utr_a.length - (start_a + length),
                ),
                BlockHit(
                    species=utr_b.name,
                    start=start_b + 1,
                    end=start_b + length,
                    distance_to_3p=utr_b.length - (start_b + length),
                ),
            ),
        )
        for start_a, start_b, length in _maximal_matches(
            utr_a.sequence, utr_b.sequence, min_length
        )
    ]
    blocks.sort(key=lambda b: (-b.length, b.hits[0].start))
    return blocks


@dataclass(frozen=True)
class ConservationReport:
    species: tuple[str, str]
    blocks: tuple[ConservedBlock, ...]
    min_length: int
    window_size: int
    evaluations: dict[int, list[WindowEvaluation]] = field(default_factory=dict)

    def passing_windows(self) -> int:
        return sum(
            1
            for windows in self.evaluations.values()
            for window in windows
            if window.verdict is Verdict.PASS
        )

    def format_text(self) -> str:
        a, b = self.species
        lines = [
            f"Bloques conservados {a}/{b} — identidad exacta >= {self.min_length} nt",
        ]
        if not self.blocks:
            lines.append("")
            lines.append(
                f"No se encontro ningun bloque conservado de >= {self.min_length} nt."
            )
            return "\n".join(lines)

        lines.append(f"{len(self.blocks)} bloque(s).")
        for index, block in enumerate(self.blocks):
            lines.append("")
            lines.append(f"── Bloque {index + 1}: {block.length} nt ──")
            lines.append(f"  {block.sequence}")
            lines.append(f"  GC {block.gc_fraction * 100:.1f}%")
            lines.extend(f"  {hit.describe()}" for hit in block.hits)

            windows = self.evaluations.get(index, [])
            if not windows:
                lines.append(
                    f"  Bloque de {block.length} nt: no caben ventanas de "
                    f"{self.window_size} nt. Se reporta igualmente."
                )
                continue

            aptas = sum(1 for w in windows if w.verdict is Verdict.PASS)
            lines.append(
                f"  Ventanas de {self.window_size} nt: {len(windows)}, aptas: {aptas}"
            )
            lines.extend(window.format_text(indent="    ") for window in windows)
            if aptas == 0:
                lines.append(
                    "    Ninguna ventana pasa los filtros. El bloque se reporta "
                    "igualmente: la decision de usarlo es del usuario, no del software."
                )
        return "\n".join(lines)


def build_conservation_report(
    utr_a: Utr3,
    utr_b: Utr3,
    *,
    min_length: int = MIN_BLOCK_LENGTH,
    window_size: int = WINDOW_SIZE,
    asymmetry_model: AsymmetryModel | None = turner_asymmetry,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> ConservationReport:
    blocks = find_conserved_blocks(utr_a, utr_b, min_length=min_length)
    evaluations = {
        index: block.window_evaluations(
            window_size=window_size,
            asymmetry_model=asymmetry_model,
            thresholds=thresholds,
        )
        for index, block in enumerate(blocks)
    }
    return ConservationReport(
        species=(utr_a.name, utr_b.name),
        blocks=tuple(blocks),
        min_length=min_length,
        window_size=window_size,
        evaluations=evaluations,
    )


# ─── La consecuencia de que un bloque conservado no de candidatos ────────────
#
# Ojo con QUE ventanas se miran. Las que SOLAPAN un bloque conservado se salen de el, y
# fuera del bloque las dos especies difieren: son ventanas distintas con dianas
# distintas, y contarlas dio un «SI hay ventanas elegibles» falso. Las que valen son las
# CONTENIDAS en el bloque, que por construccion tienen la MISMA diana en las dos
# especies — y son exactamente las que `ConservationReport.evaluations` ya evalua.


@dataclass(frozen=True)
class SingleShmirVerdict:
    """¿Cabe UN shmiR que sirva para las tres cosas por la via del 3'UTR?

    `possible` es `None` cuando no se ha comparado: no haber mirado y haber mirado sin
    encontrar nada son cosas distintas, y aqui la diferencia decide un programa.
    """

    possible: bool | None
    passing: int
    windows: int
    blocks: int
    long_enough: int
    window_size: int

    def describe(self) -> str:
        if self.possible is None:
            return (
                "Un shmiR unico para raton, Tg650 y clinica por la via del 3'UTR: "
                "NOT_RUN. No se ha comparado con otra especie, asi que no hay bloques "
                "conservados que mirar. NOT_RUN no es «no existe»."
            )
        if self.possible:
            return (
                f"SI hay ventanas de {self.window_size} nt CONTENIDAS en un bloque "
                f"conservado que superan los filtros de secuencia: {self.passing} de "
                f"{self.windows}. Un shmiR unico para raton, Tg650 y clinica por la via "
                f"del 3'UTR es POSIBLE por ahi, y esas son las ventanas por las que "
                f"pasa. Falta comprobarlas con los filtros que dependen de recurso."
            )
        return (
            f"CONSECUENCIA: NO EXISTE un shmiR unico valido para raton, Tg650 y clinica "
            f"por la via del 3'UTR. De los {self.blocks} bloque(s) conservado(s), "
            f"{self.long_enough} son lo bastante largos para alojar una guia de "
            f"{self.window_size} nt, y de las {self.windows} ventanas que caben DENTRO "
            f"de ellos NINGUNA supera los filtros de secuencia — con los mismos motivos "
            f"en las dos especies, porque la diana es la misma. No hay donde poner una "
            f"guia que sirva para las tres cosas a la vez. Esto cambia la ARQUITECTURA "
            f"DEL PROGRAMA —haria falta otra via, por ejemplo el ORF conservado— y no "
            f"dos plazas del panel."
        )


def single_shmir_verdict(report: "ConservationReport | None") -> SingleShmirVerdict:
    """Deriva el veredicto del informe de conservacion. Sin informe, `None`."""
    if report is None or not report.blocks:
        return SingleShmirVerdict(
            possible=None, passing=0, windows=0, blocks=0, long_enough=0,
            window_size=report.window_size if report is not None else WINDOW_SIZE,
        )
    ventanas = [w for lista in report.evaluations.values() for w in lista]
    return SingleShmirVerdict(
        possible=bool(report.passing_windows()),
        passing=report.passing_windows(),
        windows=len(ventanas),
        blocks=len(report.blocks),
        long_enough=sum(1 for b in report.blocks if b.length >= report.window_size),
        window_size=report.window_size,
    )
