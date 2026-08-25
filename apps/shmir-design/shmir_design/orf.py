"""Proponedor de marco abierto de lectura (bloque 7, via 3).

**Este modulo propone y no decide.** No exporta ninguna funcion que fije la frontera
del 3'UTR, y a proposito no importa nada del modulo de anatomia: un ORF calculado es
una prediccion, y una prediccion no puede fijar en silencio la coordenada de la que
cuelgan los tercios, las etiquetas de region y toda comparacion con las tablas del
proyecto. Elegir la isoforma equivocada, o un inicio no-AUG, corre todas las
coordenadas sin que nada avise.

Lo que hace es util igualmente: cuando llega un transcrito sin anotacion, calcula el
marco mas largo, lo enseña, e imprime el `--cds INICIO FIN` exacto para que una persona
lo pegue si esta de acuerdo. Mientras nadie lo pegue, la anatomia sigue SIN RESOLVER y
los filtros que dependen de ella salen NOT_RUN.

Solo la hebra directa: un mRNA es de una sola hebra y buscar en la complementaria solo
produce ruido.

Regla 1: aqui no se genera ni una base. Se lee la secuencia que se da y se devuelven
coordenadas sobre ella.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

START_CODON = "ATG"
STOP_CODONS = frozenset({"TAA", "TAG", "TGA"})

#: Por debajo de esto casi todo son marcos por azar. 50 codones = 150 nt.
DEFAULT_MIN_CODONS = 50


@dataclass(frozen=True)
class Orf:
    """Marco abierto de lectura, 1-based e inclusivo, con el codon de parada dentro."""

    start: int
    end: int
    frame: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    @property
    def codons(self) -> int:
        """Codones traducidos, sin contar el de parada."""
        return self.length // 3 - 1

    def describe(self) -> str:
        return (
            f"{self.start}..{self.end} ({self.length} nt, {self.codons} codones, "
            f"marco {self.frame})"
        )


def find_orfs(sequence: str, *, min_codons: int = DEFAULT_MIN_CODONS) -> tuple[Orf, ...]:
    """Todos los marcos ATG..parada de la hebra directa, en los tres marcos.

    Devuelve tambien los anidados (un ATG interno da su propio marco): filtrarlos aqui
    seria decidir, y decidir no es cosa de este modulo.
    """
    if min_codons < 1:
        raise ValueError(
            f"min_codons={min_codons} no tiene sentido; se aborta en vez de devolver "
            f"marcos de longitud cero."
        )
    upper = sequence.upper()
    encontrados: list[Orf] = []

    for frame in range(3):
        posiciones = range(frame, len(upper) - 2, 3)
        for i in posiciones:
            if upper[i : i + 3] != START_CODON:
                continue
            for j in range(i + 3, len(upper) - 2, 3):
                codon = upper[j : j + 3]
                if codon not in STOP_CODONS:
                    continue
                tramo = upper[i : j + 3]
                if "N" in tramo:
                    break  # marco no evaluable: no se propone lo que no se puede leer
                orf = Orf(start=i + 1, end=j + 3, frame=frame + 1)
                if orf.codons >= min_codons:
                    encontrados.append(orf)
                break

    return tuple(sorted(encontrados, key=lambda o: (-o.length, o.start)))


def propose_cds(
    sequence: str, *, min_codons: int = DEFAULT_MIN_CODONS
) -> Orf | None:
    """El marco mas largo, o None si no hay ninguno. NUNCA fija la frontera."""
    orfs = find_orfs(sequence, min_codons=min_codons)
    return orfs[0] if orfs else None


def format_cds_suggestion(orf: Orf | None, *, alternatives: int | None = None) -> str:
    """Texto para el informe y la consola. Sugiere el comando; no lo ejecuta."""
    if orf is None:
        return (
            "No se encontro ningun marco abierto de lectura suficientemente largo, asi "
            "que no hay ni siquiera una propuesta que enseñar. La anatomia sigue SIN "
            "RESOLVER: declara --cds, o pasa el GenBank, o declara que la secuencia ya "
            "es el 3'UTR."
        )

    lineas = [
        f"PROPUESTA NO CONFIRMADA: el marco mas largo es {orf.describe()}.",
        "",
        "Esto es una prediccion, no una anotacion. NO se ha usado para nada: la",
        "anatomia sigue sin resolver y los filtros que dependen de la region estan en",
        "NOT_RUN. Si la das por buena, vuelve a lanzar el diseño añadiendo:",
        "",
        f"    --cds {orf.start} {orf.end}",
        "",
        "Antes de pegarlo, comprueba que la isoforma es la que quieres: el registro",
        "GenBank del RefSeq lleva el CDS anotado y se lee con --genbank, que es mas",
        "fiable que cualquier prediccion de este modulo.",
    ]
    if alternatives:
        lineas.insert(
            1,
            f"Hay {alternatives} marco(s) alternativo(s) mas: si la eleccion no es "
            f"obvia, no la haga el codigo.",
        )
    return "\n".join(lineas)
