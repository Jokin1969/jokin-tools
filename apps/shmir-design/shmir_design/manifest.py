"""Manifiesto de `data/reference/`: que fichero se uso, con que checksum y de donde.

Para que existe: sin un registro versionado, una corrida de hace tres meses no es
reproducible y un veredicto no es auditable dentro de un año. No basta con que el
programa diga "especificidad: PASS"; hay que poder decir **con que version de RefSeq**.

Reparto: **el manifiesto se versiona en git, los ficheros NO**. Un RefSeq RNA completo o
un `mature.fa` no tienen por que entrar en el repositorio; lo que tiene que entrar es la
linea que dice cual era y como comprobarlo.

Una linea por fichero: `nombre`, `filtro`, `tamaño`, `md5`, `fecha`, `origen`.

## Lo que este manifiesto NO es

No es la fuente de verdad de los checksums de los dos transcritos de referencia. Esos
viven en `reference.py`, en codigo y con test, por el invariante 4 del proyecto: un
checksum que solo vive en un fichero de datos se puede editar para que un fichero pase.
El manifiesto tiene esa misma debilidad, y por eso hay un test que exige que coincida
con el codigo. Para el resto de ficheros —RefSeq, miRBase, rmsk— el manifiesto es el
registro, y su garantia es que va versionado: cambiarlo se ve en el diff.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .errors import ShmirDesignError

MANIFEST_NAME = "manifest.tsv"
MANIFEST_COLUMNS = ("nombre", "filtro", "tamaño", "md5", "fecha", "origen")

#: Ficheros del directorio que no son datos y no cuentan como sobrantes.
_NO_SON_DATOS = frozenset({MANIFEST_NAME, ".gitignore"})

_MD5 = re.compile(r"^[0-9a-f]{32}$")


class EntryStatus(StrEnum):
    OK = "OK"
    AUSENTE = "AUSENTE"
    NO_COINCIDE = "NO_COINCIDE"
    SIN_REGISTRAR = "SIN_REGISTRAR"


@dataclass(frozen=True)
class ManifestEntry:
    name: str
    filter_name: str
    size: int | None
    md5: str
    date: str
    origin: str

    def usable(self, status: EntryStatus) -> bool:
        """¿Se puede correr el filtro que depende de este fichero?

        `SIN_REGISTRAR` cuenta como usable —el fichero esta— pero no es auditable: el
        informe lo dira, porque dentro de un año nadie podra comprobar cual era.
        """
        return status in (EntryStatus.OK, EntryStatus.SIN_REGISTRAR)

    def as_line(self) -> str:
        tamaño = "?" if self.size is None else f"{self.size} B"
        md5 = self.md5 or "SIN REGISTRAR"
        fecha = self.date or "sin fecha"
        return (
            f"{self.name} — {self.filter_name} — {tamaño} — md5 {md5} — {fecha} — "
            f"{self.origin}"
        )


@dataclass(frozen=True)
class Manifest:
    entries: tuple[ManifestEntry, ...]
    source: str

    def find(self, name: str) -> ManifestEntry | None:
        """La entrada, o `None` si no esta. No lanza: quien pregunta ya sabe que puede
        no estar, y usar una excepcion para eso obligaria a capturarla (regla 2)."""
        for entrada in self.entries:
            if entrada.name == name:
                return entrada
        return None

    def entry(self, name: str) -> ManifestEntry:
        entrada = self.find(name)
        if entrada is None:
            disponibles = ", ".join(e.name for e in self.entries)
            raise KeyError(
                f"{self.source}: no hay ninguna entrada para {name!r}; las que hay: "
                f"{disponibles}."
            )
        return entrada

    def provenance_lines(self, used: list[str]) -> tuple[str, ...]:
        """Las lineas del manifiesto de los ficheros que se USARON, para el informe."""
        if not used:
            return (
                "No se uso ningun fichero de referencia: todos los filtros que dependen "
                "de uno quedaron en NOT_RUN.",
            )
        lineas: list[str] = []
        for nombre in used:
            entrada = self.find(nombre)
            lineas.append(
                entrada.as_line()
                if entrada is not None
                else (
                    f"{nombre} — NO ESTA EN EL MANIFIESTO: se uso un fichero sin "
                    f"registrar, asi que esta corrida no es reproducible. Añadelo a "
                    f"{MANIFEST_NAME}."
                )
            )
        return tuple(lineas)


def parse_manifest(text: str, *, source: str) -> Manifest:
    filas = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    if not filas:
        raise ShmirDesignError(
            f"{source}: el manifiesto no tiene ninguna fila; se aborta en vez de dar "
            f"por vacio el directorio de referencias."
        )
    cabecera = tuple(filas[0].split("\t"))
    if cabecera != MANIFEST_COLUMNS:
        raise ShmirDesignError(
            f"{source}: la cabecera del manifiesto es {cabecera} y se esperaba "
            f"{MANIFEST_COLUMNS}; se aborta en vez de leer las columnas por posicion."
        )
    if len(filas) == 1:
        raise ShmirDesignError(
            f"{source}: el manifiesto solo tiene cabecera. Se aborta: un manifiesto "
            f"vacio no distingue 'no hay ficheros' de 'nadie los ha registrado'."
        )

    entradas: list[ManifestEntry] = []
    vistos: set[str] = set()
    for numero, fila in enumerate(filas[1:], start=2):
        campos = fila.split("\t")
        if len(campos) != len(MANIFEST_COLUMNS):
            raise ShmirDesignError(
                f"{source}, fila {numero}: tiene {len(campos)} campo(s) y hacen falta "
                f"{len(MANIFEST_COLUMNS)}; se aborta en vez de saltarse la fila."
            )
        nombre, filtro, tamaño, md5, fecha, origen = (c.strip() for c in campos)
        if not nombre:
            raise ShmirDesignError(f"{source}, fila {numero}: sin nombre de fichero.")
        if nombre in vistos:
            raise ShmirDesignError(
                f"{source}, fila {numero}: {nombre} aparece dos veces; se aborta en vez "
                f"de quedarse con una de las dos lineas."
            )
        vistos.add(nombre)
        if md5 and not _MD5.match(md5):
            raise ShmirDesignError(
                f"{source}, fila {numero}: {md5!r} no es un md5 hexadecimal de 32 "
                f"caracteres; se aborta."
            )
        talla: int | None = None
        if tamaño:
            try:
                talla = int(tamaño)
            except ValueError as exc:
                raise ShmirDesignError(
                    f"{source}, fila {numero}: el tamaño {tamaño!r} no es un numero "
                    f"({exc}); se aborta."
                ) from exc
        entradas.append(
            ManifestEntry(
                name=nombre, filter_name=filtro, size=talla, md5=md5,
                date=fecha, origin=origen,
            )
        )
    return Manifest(entries=tuple(entradas), source=source)


def load_manifest(path: Path | str) -> Manifest:
    path = Path(path)
    try:
        texto = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer el manifiesto {path} ({exc}); sin el no se sabe que "
            f"ficheros de referencia deberia haber ni con que checksum."
        ) from exc
    return parse_manifest(texto, source=str(path))


@dataclass(frozen=True)
class EntryResult:
    entry: ManifestEntry
    status: EntryStatus
    computed_md5: str = ""
    computed_size: int | None = None

    @property
    def usable(self) -> bool:
        return self.entry.usable(self.status)

    @property
    def detail(self) -> str:
        if self.status is EntryStatus.OK:
            return f"md5 {self.entry.md5} — {self.entry.date} — {self.entry.origin}"
        if self.status is EntryStatus.AUSENTE:
            return f"falta el fichero — {self.entry.origin}"
        if self.status is EntryStatus.SIN_REGISTRAR:
            return (
                f"el fichero esta pero el manifiesto no trae su md5. Apunta "
                f"{self.computed_md5} ({self.computed_size} B) en {MANIFEST_NAME}: "
                f"hasta entonces la corrida no es auditable."
            )
        return (
            f"md5 {self.computed_md5} y el manifiesto dice {self.entry.md5}. El fichero "
            f"NO es el que dice ser; no se usa."
        )


@dataclass(frozen=True)
class DirectoryStatus:
    results: tuple[EntryResult, ...]
    unlisted: tuple[str, ...]
    directory: str

    def result_of(self, name: str) -> EntryResult:
        for resultado in self.results:
            if resultado.entry.name == name:
                return resultado
        raise KeyError(f"No hay resultado para {name!r}.")

    def status_of(self, name: str) -> EntryStatus:
        return self.result_of(name).status

    @property
    def runnable(self) -> tuple[EntryResult, ...]:
        return tuple(r for r in self.results if r.usable)

    @property
    def not_run(self) -> tuple[EntryResult, ...]:
        return tuple(r for r in self.results if not r.usable)

    @property
    def mismatched(self) -> tuple[EntryResult, ...]:
        return tuple(r for r in self.results if r.status is EntryStatus.NO_COINCIDE)

    def used_names(self) -> tuple[str, ...]:
        return tuple(r.entry.name for r in self.runnable)

    def format_text(self) -> str:
        lineas = [f"── Ficheros de referencia — {self.directory} ──"]
        ancho = max((len(r.entry.name) for r in self.results), default=10)
        for resultado in sorted(self.results, key=lambda r: r.entry.name):
            lineas.append(
                f"  {resultado.entry.name:<{ancho}}  "
                f"{resultado.status.value:<14} {resultado.entry.filter_name}"
            )
            lineas.append(f"  {' ' * ancho}  {resultado.detail}")
        lineas.append("")
        if self.runnable:
            lineas.append(
                "  Pueden correr: "
                + ", ".join(sorted(r.entry.filter_name for r in self.runnable))
            )
        else:
            lineas.append("  Ningun filtro que dependa de un fichero puede correr.")
        if self.not_run:
            lineas.append(
                "  Quedaran en NOT_RUN: "
                + ", ".join(sorted(r.entry.filter_name for r in self.not_run))
            )
            lineas.append(
                "  NOT_RUN no es PASS: los candidatos saldran INCOMPLETE mientras falte "
                "cualquiera de esos ficheros."
            )
        if self.mismatched:
            lineas.append(
                "  ⚠  HAY FICHEROS QUE NO SON LOS QUE DICEN SER: "
                + ", ".join(r.entry.name for r in self.mismatched)
                + ". No se usan."
            )
        if self.unlisted:
            lineas.append(
                "  Sin registrar en el manifiesto (no se usan): "
                + ", ".join(self.unlisted)
            )
        return "\n".join(lineas)


def check_directory(directory: Path | str) -> DirectoryStatus:
    """Valida el directorio contra su manifiesto. No lanza ningun diseño."""
    directory = Path(directory)
    manifiesto = load_manifest(directory / MANIFEST_NAME)

    resultados: list[EntryResult] = []
    for entrada in manifiesto.entries:
        ruta = directory / entrada.name
        if not ruta.is_file():
            resultados.append(EntryResult(entry=entrada, status=EntryStatus.AUSENTE))
            continue
        datos = ruta.read_bytes()
        md5 = hashlib.md5(datos, usedforsecurity=False).hexdigest()
        if not entrada.md5:
            estado = EntryStatus.SIN_REGISTRAR
        elif md5 == entrada.md5:
            estado = EntryStatus.OK
        else:
            estado = EntryStatus.NO_COINCIDE
        resultados.append(
            EntryResult(
                entry=entrada, status=estado, computed_md5=md5,
                computed_size=len(datos),
            )
        )

    listados = {e.name for e in manifiesto.entries}
    sobrantes = tuple(
        sorted(
            p.name
            for p in directory.iterdir()
            if p.is_file()
            and p.name not in listados
            and p.name not in _NO_SON_DATOS
            and p.suffix.lower() != ".md"
        )
    )
    return DirectoryStatus(
        results=tuple(resultados), unlisted=sobrantes, directory=str(directory)
    )
