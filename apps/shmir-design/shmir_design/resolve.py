"""Como se fija la anatomia de un transcrito, en un solo sitio.

Esto vivia dentro de `tools/design.py`, asi que la interfaz no podia usarlo — y acabo
teniendo su propia version, que volvia a hacer lo que el CLI habia dejado de hacer:
tratar en silencio todo el transcrito como 3'UTR cuando nadie habia dicho donde acaba el
CDS. El mismo mRNA daba una anatomia por consola y otra por navegador, y la del
navegador corria los tercios y colaba ventanas del ORF como si fueran del 3'UTR.

Aqui no hay ningun camino que convierta un "no se" en un "todo es 3'UTR". Las vias son
tres, se declaran, y la que se uso viaja en `Anatomy.source` hasta el informe.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from pathlib import Path

from .anatomy import Anatomy, RegionSource, check_cds_boundaries, cds_stop_codon_ok
from .errors import ShmirDesignError
from .genbank import load_genbank_cds

#: Por que se aborta. Cada frontal añade con `hint` como se resuelve EN EL: el CLI
#: nombra sus flags, la interfaz nombra sus controles. El motivo es el mismo.
SIN_ANATOMIA = (
    "no se ha resuelto donde acaba el CDS, así que no se sabe que tramo del "
    "transcrito es cada posición y la anatomía queda SIN RESOLVER. Tilar de todos "
    "modos trataria el 5'UTR y el CDS como si fueran 3'UTR: los tercios saldrian "
    "corridos y habría candidatos del ORF presentados como candidatos del 3'UTR. "
    "Hay tres formas de resolverlo, por orden de fiabilidad:\n"
    "  1. la anotación de un fichero GenBank (.gb) del RefSeq — lo más fiable\n"
    "  2. las coordenadas del CDS a mano\n"
    "  3. declarar que la secuencia YA es el 3'UTR"
)


def resolve_anatomy(
    *,
    name: str,
    sequence: str,
    cds: tuple[int, int] | None = None,
    genbank: Path | str | None = None,
    genbank_md5: str | None = None,
    whole_is_utr3: bool = False,
    from_fixture: bool = False,
    hint: str = "",
) -> Anatomy:
    """Fija la anatomia por una de las tres vias, o aborta. Nunca adivina.

    El orden es el de fiabilidad: un GenBank manda sobre unas coordenadas tecleadas,
    porque las coordenadas tecleadas son justamente lo que se equivoca.
    """
    if from_fixture:
        # Los fixtures de REFERENCES ya son 3'UTR extraidos y comprobados por md5.
        return Anatomy.whole_is_utr3(
            len(sequence), source=RegionSource.FIXTURE_VERIFICADO
        )
    if genbank is not None:
        anotacion = load_genbank_cds(genbank, expected_md5=genbank_md5)
        anotacion.check_against_sequence_length(len(sequence))
        return Anatomy.from_cds(
            cds=anotacion.cds,
            length=len(sequence),
            source=RegionSource.ANOTACION_GENBANK,
        )
    if cds:
        return Anatomy.from_cds(
            cds=(cds[0], cds[1]),
            length=len(sequence),
            source=RegionSource.CDS_DECLARADA,
        )
    if whole_is_utr3:
        return Anatomy.whole_is_utr3(
            len(sequence), source=RegionSource.TODO_3UTR_DECLARADO
        )
    raise ShmirDesignError(f"{name}: {SIN_ANATOMIA}{hint}")


def check_boundaries(
    sequence: str, anatomy: Anatomy, *, allow_no_stop: bool = False
) -> tuple[str, ...]:
    """Comprueba el CDS declarado contra las bases. El codón de parada es aviso duro.

    Es el chequeo que pilla el off-by-one y el lio 0-based/1-based, que corren el 3'UTR
    entero sin avisar.
    """
    if anatomy.cds is None:
        return tuple(anatomy.warnings)
    avisos = tuple(anatomy.warnings) + check_cds_boundaries(sequence, anatomy)
    if cds_stop_codon_ok(sequence, anatomy) is False and not allow_no_stop:
        detalle = next((a for a in avisos if "codón de parada" in a), "")
        raise ShmirDesignError(
            f"{detalle} Se aborta el diseño: un CDS corrido corre también el 3'UTR, y "
            f"con el todas las posiciones y los tercios. Comprueba las coordenadas, o "
            f"resuelve la anatomía con el GenBank, o repite diciendo a propósito que "
            f"este CDS no acaba en codón de parada."
        )
    return avisos
