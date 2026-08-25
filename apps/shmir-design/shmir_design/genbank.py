"""Lector de la feature CDS de un fichero GenBank (bloque 7, via 1).

Por que existe: la frontera del 3'UTR es el dato del que cuelgan los tercios, las
etiquetas de region y toda comparacion con las tablas del proyecto. Declararla a mano
funciona, pero se corre un nucleotido con una facilidad pasmosa. El registro GenBank del
RefSeq ya la trae anotada, asi que leerla de ahi no es reconstruir nada: es leer un dato
que aporta el usuario, con la misma disciplina que los FASTA (fichero en disco, md5
registrado, y si no cuadra se aborta).

Regla 4: aqui no hay ninguna URL. El .gb se descarga fuera y se deja en disco; este
modulo solo parsea lo que ya esta.

Regla 1: de este fichero NO sale ninguna secuencia. Solo coordenadas y metadatos. Las
bases siguen viniendo del FASTA verificado, y si el .gb y el FASTA no miden lo mismo se
aborta en vez de recortar por nuestra cuenta.

Regla 2: cualquier forma de CDS que no sea un tramo unico, completo y en la hebra
directa aborta diciendo que se encontro y que queda sin ejecutar. Un CDS parcial
(`<185..949`) o troceado (`join(...)`) en un registro de mRNA significa que el registro
no es lo que esperabamos, y adivinar cual de los tramos vale seria justo el tipo de
reconstruccion que este proyecto prohibe.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import ChecksumMismatchError, ShmirDesignError

#: `LOCUS       NM_011170               2191 bp    mRNA    linear   ROD 25-MAY-2024`
_LOCUS = re.compile(r"^LOCUS\s+(?P<name>\S+)\s+(?P<length>\d+)\s+bp\b")
#: `VERSION     NM_011170.3`
_VERSION = re.compile(r"^VERSION\s+(?P<accession>\S+)")
#: `ACCESSION   NM_011170`
_ACCESSION = re.compile(r"^ACCESSION\s+(?P<accession>\S+)")
#: `185..949`, ya sin adornos.
_SPAN = re.compile(r"^(?P<start>\d+)\.\.(?P<end>\d+)$")
#: `/gene="Prnp"`
_QUALIFIER = re.compile(r'^/(?P<key>\w+)=(?P<value>.*)$')


@dataclass(frozen=True)
class GenBankCds:
    """Lo que se saca de un GenBank: coordenadas y procedencia, nunca secuencia."""

    accession: str
    length: int
    cds: tuple[int, int]
    gene: str | None = None
    organism: str | None = None
    source: str = "?"
    md5: str | None = None

    def check_against_sequence_length(self, length: int) -> None:
        """El .gb y el FASTA tienen que hablar del mismo transcrito."""
        if length != self.length:
            raise ShmirDesignError(
                f"{self.source}: el GenBank de {self.accession} declara {self.length} "
                f"nt y la secuencia suministrada mide {length} nt. No son el mismo "
                f"transcrito (o una de las dos esta recortada); se aborta antes de "
                f"aplicar el CDS {self.cds[0]}..{self.cds[1]} a una secuencia que no le "
                f"corresponde."
            )

    def check_accession(self, expected: str) -> None:
        if self.accession != expected:
            raise ShmirDesignError(
                f"{self.source}: se esperaba el GenBank de {expected} y el fichero es "
                f"de {self.accession}. Se aborta: aplicar el CDS de un transcrito a "
                f"otro corre todas las coordenadas."
            )

    def describe(self) -> str:
        partes = [f"{self.accession} ({self.length} nt)"]
        if self.gene:
            partes.append(f"gen {self.gene}")
        if self.organism:
            partes.append(self.organism)
        partes.append(f"CDS {self.cds[0]}..{self.cds[1]}")
        if self.md5:
            partes.append(f"md5 {self.md5}")
        return ", ".join(partes)


def _parse_location(raw: str, *, source: str) -> tuple[int, int]:
    """Acepta un unico tramo completo en la hebra directa. Cualquier otra cosa aborta."""
    location = "".join(raw.split())

    if location.startswith("complement("):
        raise ShmirDesignError(
            f"{source}: el CDS esta en complement({location[11:-1]}). En un registro de "
            f"mRNA el CDS va en la hebra directa, asi que este registro no es lo que "
            f"esperabamos; se aborta sin leer coordenadas."
        )
    if location.startswith(("join(", "order(")):
        raise ShmirDesignError(
            f"{source}: el CDS viene troceado ({location}). Elegir uno de los tramos, o "
            f"tomar sus extremos, seria inventarse la frontera del 3'UTR; se aborta y "
            f"la anatomia queda sin resolver."
        )
    if "<" in location or ">" in location:
        raise ShmirDesignError(
            f"{source}: el CDS esta anotado como parcial ({location}). Una frontera "
            f"parcial no sirve para fijar el 3'UTR; se aborta y la anatomia queda sin "
            f"resolver."
        )

    match = _SPAN.match(location)
    if match is None:
        raise ShmirDesignError(
            f"{source}: no se entiende la localizacion del CDS ({location!r}). Se "
            f"esperaba `inicio..fin`; se aborta sin adivinar."
        )
    start, end = int(match["start"]), int(match["end"])
    if start < 1 or end < start:
        raise ShmirDesignError(
            f"{source}: el CDS {start}..{end} tiene coordenadas imposibles; se aborta."
        )
    return start, end


def _features(text: str) -> list[tuple[str, str, dict[str, str]]]:
    """Trocea el bloque FEATURES en (clave, localizacion, cualificadores)."""
    features: list[tuple[str, str, dict[str, str]]] = []
    dentro = False
    clave: str | None = None
    localizacion = ""
    cualificadores: dict[str, str] = {}
    pendiente: str | None = None

    def cerrar() -> None:
        nonlocal clave, localizacion, cualificadores
        if clave is not None:
            features.append((clave, localizacion, cualificadores))
        clave, localizacion, cualificadores = None, "", {}

    for linea in text.splitlines():
        if linea.startswith("FEATURES"):
            dentro = True
            continue
        if not dentro:
            continue
        if linea and not linea.startswith(" "):
            break  # ORIGIN, CONTIG, // o cualquier otra seccion de primer nivel
        if linea.startswith("     ") and linea[5:6] not in (" ", ""):
            cerrar()
            pendiente = None
            clave = linea[5:21].strip()
            localizacion = linea[21:].strip()
            continue
        if clave is None:
            continue
        resto = linea.strip()
        if resto.startswith("/"):
            match = _QUALIFIER.match(resto)
            if match is not None:
                pendiente = match["key"]
                cualificadores[pendiente] = match["value"].strip('"')
            else:
                pendiente = None
                cualificadores[resto.lstrip("/")] = ""
        elif pendiente is not None:
            cualificadores[pendiente] = (cualificadores[pendiente] + " " + resto).strip('"')
        else:
            localizacion += resto
    cerrar()
    return features


def parse_genbank_cds(text: str, *, source: str = "GenBank") -> GenBankCds:
    """Saca el CDS de un registro GenBank. Aborta ante cualquier ambiguedad."""
    if not text.strip():
        raise ShmirDesignError(
            f"{source}: el fichero GenBank esta vacio; no hay CDS que leer y la "
            f"anatomia queda sin resolver."
        )

    locus = next(
        (m for m in (_LOCUS.match(l) for l in text.splitlines()) if m), None
    )
    if locus is None:
        raise ShmirDesignError(
            f"{source}: no hay linea LOCUS, asi que esto no es un fichero GenBank "
            f"(¿es el FASTA?). Se aborta sin leer coordenadas."
        )
    length = int(locus["length"])

    accession = None
    for linea in text.splitlines():
        match = _VERSION.match(linea)
        if match is not None:
            accession = match["accession"]
            break
    if accession is None:
        for linea in text.splitlines():
            match = _ACCESSION.match(linea)
            if match is not None:
                accession = match["accession"]
                break
    if accession is None:
        accession = locus["name"]

    features = _features(text)
    cds_features = [f for f in features if f[0] == "CDS"]
    if not cds_features:
        claves = sorted({f[0] for f in features}) or ["ninguna"]
        raise ShmirDesignError(
            f"{source}: el registro de {accession} no tiene ninguna feature CDS "
            f"(las que hay: {', '.join(claves)}). Sin CDS no hay frontera del 3'UTR; "
            f"se aborta y la anatomia queda sin resolver."
        )
    if len(cds_features) > 1:
        localizaciones = ", ".join(f[1] for f in cds_features)
        raise ShmirDesignError(
            f"{source}: el registro de {accession} tiene {len(cds_features)} features "
            f"CDS ({localizaciones}). Elegir una seria elegir isoforma por nuestra "
            f"cuenta; se aborta y la anatomia queda sin resolver."
        )

    _, localizacion, cualificadores = cds_features[0]
    start, end = _parse_location(localizacion, source=source)
    if end > length:
        raise ShmirDesignError(
            f"{source}: el CDS {start}..{end} de {accession} se sale del transcrito, "
            f"que mide {length} nt segun su linea LOCUS. Se aborta en vez de recortar."
        )

    organismo = next(
        (f[2].get("organism") for f in features if f[0] == "source" and f[2].get("organism")),
        None,
    )
    return GenBankCds(
        accession=accession,
        length=length,
        cds=(start, end),
        gene=cualificadores.get("gene"),
        organism=organismo,
        source=source,
    )


def load_genbank_cds(path: Path | str, *, expected_md5: str | None = None) -> GenBankCds:
    """Lee el .gb de disco, comprueba su md5 si se dio, y devuelve el CDS."""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer el GenBank {path} ({exc}); la anatomia queda sin resolver "
            f"y el diseño no continua."
        ) from exc

    md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    if expected_md5 is not None and md5 != expected_md5:
        raise ChecksumMismatchError(
            f"{path}: md5 {md5} y se esperaba {expected_md5}. El fichero GenBank NO es "
            f"el que dice ser; se aborta antes de leer ninguna coordenada de el."
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ShmirDesignError(
            f"{path}: el GenBank no es UTF-8 ({exc}); se aborta."
        ) from exc

    cds = parse_genbank_cds(text, source=str(path))
    return GenBankCds(
        accession=cds.accession,
        length=cds.length,
        cds=cds.cds,
        gene=cds.gene,
        organism=cds.organism,
        source=str(path),
        md5=md5,
    )
