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
                f"transcrito (o una de las dos está recortada); se aborta antes de "
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
            f"{source}: el CDS está en complement({location[11:-1]}). En un registro de "
            f"mRNA el CDS va en la hebra directa, así que este registro no es lo que "
            f"esperabamos; se aborta sin leer coordenadas."
        )
    if location.startswith(("join(", "order(")):
        raise ShmirDesignError(
            f"{source}: el CDS viene troceado ({location}). Elegir uno de los tramos, o "
            f"tomar sus extremos, sería inventarse la frontera del 3'UTR; se aborta y "
            f"la anatomía queda sin resolver."
        )
    if "<" in location or ">" in location:
        raise ShmirDesignError(
            f"{source}: el CDS está anotado como parcial ({location}). Una frontera "
            f"parcial no sirve para fijar el 3'UTR; se aborta y la anatomía queda sin "
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


@dataclass(frozen=True)
class PlasmidFeature:
    """Una feature anotada de un plasmido, con el plasmido entero detras.

    El plasmido entero viaja con ella A PROPOSITO: los contextos exonicos se DERIVAN de
    las coordenadas, no se piden aparte. Pedirlos aparte es abrir una segunda fuente
    para el mismo dato, y la segunda fuente es la que acaba estando mal.
    """

    plasmid: str
    key: str
    label: str
    start: int
    end: int
    qualifiers: dict[str, str]

    @property
    def sequence(self) -> str:
        return self.plasmid[self.start - 1:self.end]

    def context_5(self, nt: int) -> str:
        """Los `nt` de delante. Aborta si no caben: no se rellena con nada."""
        if nt > self.start - 1:
            raise ShmirDesignError(
                f"Se piden {nt} nt de contexto 5' y la feature empieza en "
                f"{self.start}: no caben. Se aborta en vez de devolver menos sin "
                f"decirlo. (El plásmido es circular, pero dar la vuelta cambiaría el "
                f"contexto por uno de otra parte del vector sin avisar.)"
            )
        return self.plasmid[self.start - 1 - nt:self.start - 1]

    def context_3(self, nt: int) -> str:
        """Los `nt` de detras. Aborta si no caben."""
        if self.end + nt > len(self.plasmid):
            raise ShmirDesignError(
                f"Se piden {nt} nt de contexto 3' y la feature acaba en {self.end} de "
                f"{len(self.plasmid)}: no caben. Se aborta en vez de devolver menos."
            )
        return self.plasmid[self.end:self.end + nt]

    def describe(self) -> list[str]:
        return [
            f"{self.key} «{self.label}» — plásmido {self.start}-{self.end} "
            f"({len(self.sequence)} pb de {len(self.plasmid)})",
            f"  md5 del fragmento: {sequence_md5(self.sequence)}",
        ]


def sequence_md5(sequence: str) -> str:
    """md5 de una secuencia. DELEGA en `reference.sequence_md5` (2026-09-02).

    Habia DOS funciones con este nombre y este proposito —aqui y en `reference`— y no
    daban lo mismo: aquella CANONIZA antes (sin blancos, en mayusculas) y esta hasheaba
    la cadena tal cual. Con una secuencia ya normalizada coinciden, que es por lo que
    nadie lo vio; con un salto de linea dentro, no. Y de ese numero depende que un
    fichero BUENO se acepte o se rechace.

    Lo destapo la auditoria de magnitudes: la misma cantidad calculada en dos sitios.
    """
    from .reference import sequence_md5 as canonico  # noqa: PLC0415

    return canonico(sequence)


def parse_plasmid_feature(
    text: str, *, key: str, label: str | None = None, source: str = "GenBank",
    expected_md5: str | None = None,
) -> PlasmidFeature:
    """Saca UNA feature anotada de un registro GenBank de plasmido. Aborta si hay duda.

    Es la puerta de entrada para un PLASMIDO, distinta de `parse_genbank_cds`, que es
    para un TRANSCRITO y exige un unico CDS: un plasmido lleva AmpR, el transgen y lo
    que haga falta, asi que por alli no entra — y hace bien en no entrar.

    Nada se teclea: la secuencia sale de las coordenadas de la anotacion. `expected_md5`
    es la contramedida de la errata nº 5 — una feature mal anotada por un nucleotido
    corre todas las coordenadas y no da ningun error.
    """
    features = _features(text)
    if not features:
        raise ShmirDesignError(
            f"{source}: el registro no tiene bloque FEATURES, así que no hay ninguna "
            f"anotación de la que extraer nada; se aborta en vez de buscar por secuencia."
        )
    candidatas = [f for f in features if f[0] == key]
    if label is not None:
        candidatas = [f for f in candidatas if f[2].get("label", "") == label]
    if not candidatas:
        etiquetas = sorted(
            {f"{k} «{q.get('label', '')}»" for k, _, q in features if k == key}
        )
        raise ShmirDesignError(
            f"{source}: no hay ninguna feature {key!r}"
            + (f" con label {label!r}" if label else "")
            + f". Las de esa clave: {', '.join(etiquetas) or 'ninguna'}. Se aborta en "
            f"vez de coger otra."
        )
    if len(candidatas) > 1:
        donde = ", ".join(f[1] for f in candidatas)
        raise ShmirDesignError(
            f"{source}: hay {len(candidatas)} features {key!r}"
            + (f" con label {label!r}" if label else "")
            + f" ({donde}). Elegir una por nuestra cuenta sería inventarse cuál; se "
            f"aborta y se pide la que vale."
        )

    clave, localizacion, cualificadores = candidatas[0]
    inicio, fin = _parse_location(localizacion, source=source)

    origen = text.split("ORIGIN", 1)
    if len(origen) < 2:
        raise ShmirDesignError(
            f"{source}: el registro no tiene bloque ORIGIN, así que trae anotaciones y "
            f"no trae secuencia; se aborta en vez de devolver coordenadas sobre nada."
        )
    plasmido = "".join(
        re.findall(r"[acgtnACGTN]", origen[1].split("//", 1)[0])
    ).upper()

    locus = next(
        (m for m in (_LOCUS.match(l) for l in text.splitlines()) if m), None
    )
    if locus is not None and int(locus["length"]) != len(plasmido):
        raise ShmirDesignError(
            f"{source}: la línea LOCUS dice {locus['length']} bp y el bloque ORIGIN "
            f"trae {len(plasmido)}. Se aborta: una de las dos está mal y no se sabe "
            f"cuál."
        )
    if fin > len(plasmido):
        raise ShmirDesignError(
            f"{source}: la feature {key!r} va de {inicio} a {fin} y el plásmido mide "
            f"{len(plasmido)}. Se aborta en vez de recortar."
        )

    feature = PlasmidFeature(
        plasmid=plasmido, key=clave,
        label=cualificadores.get("label", ""),
        start=inicio, end=fin, qualifiers=dict(cualificadores),
    )
    if expected_md5 is not None:
        md5 = sequence_md5(feature.sequence)
        if md5 != expected_md5:
            raise ShmirDesignError(
                f"{source}: la feature {key!r} «{feature.label}» en {inicio}-{fin} "
                f"({len(feature.sequence)} pb) tiene md5 {md5} y se esperaba "
                f"{expected_md5}. NO es lo que dice ser; se aborta antes de usarla."
            )
    return feature


def load_plasmid_feature(
    path: Path | str, *, key: str, label: str | None = None,
    expected_md5: str | None = None,
) -> PlasmidFeature:
    """`parse_plasmid_feature` sobre un fichero."""
    ruta = Path(path)
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer {ruta} ({exc}); la feature {key!r} queda sin extraer."
        ) from exc
    return parse_plasmid_feature(
        texto, key=key, label=label, source=str(ruta), expected_md5=expected_md5
    )


def parse_genbank_cds(text: str, *, source: str = "GenBank") -> GenBankCds:
    """Saca el CDS de un registro GenBank. Aborta ante cualquier ambiguedad."""
    if not text.strip():
        raise ShmirDesignError(
            f"{source}: el fichero GenBank está vacío; no hay CDS que leer y la "
            f"anatomía queda sin resolver."
        )

    locus = next(
        (m for m in (_LOCUS.match(l) for l in text.splitlines()) if m), None
    )
    if locus is None:
        raise ShmirDesignError(
            f"{source}: no hay línea LOCUS, así que esto no es un fichero GenBank "
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
            f"se aborta y la anatomía queda sin resolver."
        )
    if len(cds_features) > 1:
        localizaciones = ", ".join(f[1] for f in cds_features)
        raise ShmirDesignError(
            f"{source}: el registro de {accession} tiene {len(cds_features)} features "
            f"CDS ({localizaciones}). Elegir una sería elegir isoforma por nuestra "
            f"cuenta; se aborta y la anatomía queda sin resolver."
        )

    _, localizacion, cualificadores = cds_features[0]
    start, end = _parse_location(localizacion, source=source)
    if end > length:
        raise ShmirDesignError(
            f"{source}: el CDS {start}..{end} de {accession} se sale del transcrito, "
            f"que mide {length} nt segun su línea LOCUS. Se aborta en vez de recortar."
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
            f"No se pudo leer el GenBank {path} ({exc}); la anatomía queda sin resolver "
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
