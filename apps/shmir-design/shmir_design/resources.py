"""Carga de los ficheros de referencia a partir del manifiesto.

`--usar-manifiesto` ya hacia esto en el CLI, pero rellenando argumentos de linea de
comandos. La interfaz no tenia forma de llegar ahi: le pasaba tres de los catorce
parametros de `tile_utr`, asi que **el semaforo verde era estructuralmente inalcanzable
desde el navegador** y el generador de bloques nunca podia comprobar `hits_transgen`.

Aqui esta el mismo cableado devolviendo los objetos YA CARGADOS, para que quien llame
—la pagina, un script, lo que sea— no tenga que saber que cargador va con cada fichero.

Regla 3 hasta el final: lo que no se pudo cargar no desaparece, se anota en `notes` con
el motivo. Un recurso ausente y un recurso que fallo tienen que verse distintos.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .apa import load_apa_sites
from .manifest import ROLES, DirectoryStatus, check_directory, roles_available
from .masking import load_rmsk
from .mirna import load_abundance_list, load_mature_fa
from .seed_load import load_expression_table, load_utr3_set
from .specificity import load_database


def _refseq(path, entry, contexto):
    if not contexto.get("target"):
        raise _Omitir(
            "hace falta el gen diana (--target / el campo de la interfaz): es un "
            "accession, no un fichero, y el manifiesto no lo sabe. Sin el, todo sitio "
            "parece un off-target."
        )
    return load_database(
        path, name="RefSeq RNA", version=entry.date or entry.md5, expected_md5=entry.md5
    )


def _mirbase(path, entry, contexto):
    return load_mature_fa(
        path, version=entry.date or entry.md5, expected_md5=entry.md5
    )


def _abundancia(path, entry, contexto):
    if contexto.get("mature") is None:
        raise _Omitir(
            "la lista de abundancia sin la tabla de maduros no sirve de nada: decide "
            "cuales de las colisiones importan, y sin maduros no hay colisiones."
        )
    return load_abundance_list(
        path, version=entry.date or entry.md5, expected_md5=entry.md5
    )


def _transcriptoma(path, entry, contexto):
    return load_utr3_set(path, version=entry.date or entry.md5, expected_md5=entry.md5)


def _expresion(path, entry, contexto):
    if contexto.get("utr3_set") is None:
        raise _Omitir(
            "la tabla de expresion sin los 3'UTR del transcriptoma no tiene sitios que "
            "ponderar."
        )
    return load_expression_table(path)


def _rmsk(path, entry, contexto):
    return load_rmsk(path, version=entry.date or entry.md5, expected_md5=entry.md5)


def _transgen(path, entry, contexto):
    return load_database(
        path,
        name="casete del transgen",
        version=entry.date or entry.md5,
        expected_md5=entry.md5,
    )


def _apa(path, entry, contexto):
    return load_apa_sites(
        path, version=entry.date or entry.md5, expected_md5=entry.md5
    )


class _Omitir(Exception):
    """Este recurso no se puede cargar todavia, y el motivo no es un fallo."""


#: Un cargador por rol. Unico sitio donde vive esa correspondencia; hay test de que
#: cubre exactamente los roles declarados en `manifest.ROLES`, ni uno mas ni uno menos.
LOADERS = {
    "refseq": _refseq,
    "mirbase": _mirbase,
    "abundancia": _abundancia,
    "transcriptoma": _transcriptoma,
    "expresion": _expresion,
    "rmsk": _rmsk,
    "transgen": _transgen,
    "apa": _apa,
}

#: Donde acaba cada rol dentro de `ResourceSet`. El orden importa: la abundancia
#: necesita los maduros y la expresion necesita el transcriptoma, asi que se cargan
#: despues de ellos.
DESTINOS = (
    ("mirbase", "mature"),
    ("abundancia", "abundance"),
    ("transcriptoma", "utr3_set"),
    ("expresion", "expression"),
    ("refseq", "specificity_db"),
    ("transgen", "transgene_db"),
    ("rmsk", "mask"),
    ("apa", "apa_sites"),
)


@dataclass(frozen=True)
class ResourceSet:
    """Lo que se le puede pasar a `tile_utr`, mas de donde salio cada cosa."""

    specificity_db: object | None = None
    specificity_target: str | None = None
    transgene_db: object | None = None
    mature: object | None = None
    abundance: object | None = None
    utr3_set: object | None = None
    expression: object | None = None
    mask: object | None = None
    apa_sites: object | None = None
    connected: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())
    status: DirectoryStatus | None = None

    def as_kwargs(self) -> dict[str, object]:
        """Los campos que `tile_utr` entiende, y solo esos."""
        return {
            "specificity_db": self.specificity_db,
            "specificity_target": self.specificity_target,
            "transgene_db": self.transgene_db,
            "mature": self.mature,
            "abundance": self.abundance,
            "utr3_set": self.utr3_set,
            "expression": self.expression,
            "mask": self.mask,
            "apa_sites": self.apa_sites,
        }

    def format_text(self) -> str:
        lineas = []
        if self.connected:
            lineas.append("Conectados desde el manifiesto:")
            lineas.extend(f"  · {n}" for n in self.connected)
        else:
            lineas.append(
                "No se ha conectado ningun fichero de referencia: los filtros que "
                "dependen de uno quedaran en NOT_RUN."
            )
        if self.notes:
            lineas.append("")
            lineas.extend(f"  ⚠  {n}" for n in self.notes)
        return "\n".join(lineas)


def load_from_manifest(
    directory: Path | str, *, target: str | None = None
) -> ResourceSet:
    """Carga todo lo que este en OK en ese directorio. Lo que no, se anota."""
    estado = check_directory(directory)
    disponibles = {r.role: r for r in roles_available(estado)}

    cargado: dict[str, object] = {}
    conectados: list[str] = []
    notas: list[str] = []
    contexto: dict[str, object] = {"target": target}

    for role, destino in DESTINOS:
        rol = disponibles.get(role)
        if rol is None:
            continue
        entrada = estado.result_of(rol.filename).entry
        try:
            objeto = LOADERS[role](Path(directory) / rol.filename, entrada, contexto)
        except _Omitir as motivo:
            # rule2-ok: no es un fallo, es una dependencia que falta. Se anota con su
            # motivo y el recurso queda sin cargar, que es lo que hay que reportar.
            notas.append(f"{rol.filename} no se ha conectado: {motivo}")
            continue
        cargado[destino] = objeto
        contexto[destino] = objeto
        conectados.append(rol.filename)

    return ResourceSet(
        specificity_target=target if cargado.get("specificity_db") else None,
        connected=tuple(conectados),
        notes=tuple(notas),
        status=estado,
        **cargado,
    )
