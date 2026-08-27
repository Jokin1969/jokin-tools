"""Fichas de obtencion: como se resuelve cada `NOT_RUN`.

La app decia QUE fichero falta. No decia DE DONDE sale, asi que quien lo necesitaba lo
preguntaba **fuera de la app**. Esa es la dependencia que esto rompe: alguien que no haya
estado en las conversaciones tiene que poder conseguir el fichero, subirlo y entender el
resultado.

Cada ficha es **un fichero de datos versionado** (`data/obtencion/<frente>.toml`), no
texto en el codigo, por la misma razon por la que el manifiesto es texto: se lee con
`cat`, se diffea y no hace falta la app para consultarla.

**Y se adapta a la especie.** No vale decir «miRBase» cuando quien la lee ha cargado
conejo y necesita saber que prefijo le toca. Los marcadores `{…}` se resuelven contra
`species.Species`; y lo que esa especie **no tiene declarado** sale diciendo que no esta
declarado —nunca deducido del nombre— y ademas como AVISO, no enterrado en un paso.

Python 3.11+, solo libreria estandar (regla 6): `tomllib` desde 3.11.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .errors import ShmirDesignError

#: Donde viven. Junto a `data/reference/`, y versionadas.
FICHA_DIR = Path(__file__).resolve().parent.parent / "data" / "obtencion"

#: Para un frente que no se cierra descargando nada.
NO_URL = "—"

#: Campos obligatorios de toda ficha. Que falte uno ABORTA al cargarla: una ficha a
#: medias es peor que ninguna, porque parece que la pregunta esta contestada.
REQUIRED = ("frente", "pregunta", "fuente", "url", "tamano", "validacion", "pasos")

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


@dataclass(frozen=True)
class FichaFile:
    name: str
    why: str
    required: bool = True


@dataclass(frozen=True)
class Metadato:
    name: str
    why: str


@dataclass(frozen=True)
class Ficha:
    """La ficha de UN frente. `resolved` dice si ya se ha atado a una especie."""

    front: str
    question: str
    source: str
    url: str
    size: str
    validation: str
    steps: tuple[str, ...]
    files: tuple[FichaFile, ...] = ()
    metadata: tuple[Metadato, ...] = ()
    warnings: tuple[str, ...] = ()
    no_file: bool = False
    why_no_file: str = ""
    resolved: bool = False
    #: Que valores pedia esta ficha y la especie no tiene declarados.
    undeclared: tuple[str, ...] = ()

    def render(self) -> str:
        """El texto de la ficha. Sin resolver contra una especie, ABORTA."""
        if not self.resolved:
            raise ShmirDesignError(
                f"La ficha de {self.front!r} no se ha resuelto contra ninguna especie, "
                f"así que todavia lleva marcadores dentro. Renderizarla así daria un "
                f"texto que miente a medias —«rmsk_{{slug}}.out» no es un nombre de "
                f"fichero— y esos textos se copian. Usa `resolve_ficha(frente, "
                f"species=…)`."
            )
        lineas = [
            f"COMO CERRAR EL FRENTE «{self.front}»",
            "",
            f"  QUE PREGUNTA RESPONDE: {self.question}",
            "",
        ]
        if self.no_file:
            lineas.extend([
                "  NO SE CIERRA CON NINGÚN FICHERO.",
                f"  {self.why_no_file}",
                "",
            ])
        else:
            lineas.append("  FICHERO(S) QUE HACEN FALTA:")
            for fichero in self.files:
                marca = "OBLIGATORIO" if fichero.required else "opcional"
                lineas.append(f"    · {fichero.name}  [{marca}]")
                lineas.append(f"      {fichero.why}")
            lineas.append("")
        lineas.extend([f"  FUENTE: {self.source}", f"  URL: {self.url}", ""])
        lineas.append("  PASOS:")
        lineas.extend(f"    {i}. {paso}" for i, paso in enumerate(self.steps, start=1))
        lineas.append("")
        if self.metadata:
            lineas.append("  QUE ANOTAR AL DESCARGARLO (sin esto no es reproducible):")
            for metadato in self.metadata:
                lineas.append(f"    · {metadato.name}")
                lineas.append(f"      {metadato.why}")
            lineas.append("")
        lineas.extend([
            f"  TAMAÑO APROXIMADO: {self.size}",
            "",
            f"  COMO SE VALIDA AL SUBIRLO: {self.validation}",
        ])
        if self.warnings:
            lineas.append("")
            lineas.append("  AVISOS:")
            lineas.extend(f"    ⚠ {aviso}" for aviso in self.warnings)
        return "\n".join(lineas) + "\n"


#: Los ficheros de datos van en castellano, como el resto del proyecto; los dataclasses
#: en ingles, como el resto del codigo. La correspondencia va AQUI y explicita: con
#: `**fila` a pelo, un campo mal escrito en el TOML seria un TypeError sin contexto.
_FILE_KEYS = {"nombre": "name", "por_que": "why", "obligatorio": "required"}
_META_KEYS = {"nombre": "name", "por_que": "why"}


def _rows(datos, clave, constructor, claves, *, source):
    filas = []
    for fila in datos.get(clave, ()):
        ajenas = sorted(set(fila) - set(claves))
        if ajenas:
            raise ShmirDesignError(
                f"{source}: en [[{clave}]] hay campo(s) que no existen: "
                f"{', '.join(ajenas)}. Los que hay son {', '.join(claves)}. Se aborta "
                f"en vez de ignorarlos en silencio."
            )
        filas.append(constructor(**{claves[k]: v for k, v in fila.items()}))
    return tuple(filas)


def load_ficha(path: Path | str) -> Ficha:
    """Lee una ficha del disco. Sin ningun campo obligatorio, aborta."""
    path = Path(path)
    try:
        crudo = path.read_bytes()
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer la ficha de obtencion {path} ({exc}); el frente se quedaria "
            f"sin decir como resolverse."
        ) from exc
    try:
        datos = tomllib.loads(crudo.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ShmirDesignError(
            f"{path}: no es TOML válido ({exc}); se aborta en vez de cargar media ficha."
        ) from exc

    faltan = [c for c in REQUIRED if not str(datos.get(c, "")).strip()]
    if faltan:
        raise ShmirDesignError(
            f"{path}: a la ficha le falta(n) {', '.join(faltan)}. Una ficha a medias es "
            f"peor que ninguna: parece que la pregunta está contestada. Se aborta."
        )
    if datos["frente"] != path.stem:
        raise ShmirDesignError(
            f"{path}: la ficha dice ser del frente {datos['frente']!r} y el fichero se "
            f"llama {path.stem!r}. Se aborta: con los dos nombres sueltos, renombrar un "
            f"fichero desconectaria la ficha de su frente sin que nadie lo viera."
        )

    sin_fichero = bool(datos.get("sin_fichero", False))
    ficheros = _rows(datos, "ficheros", FichaFile, _FILE_KEYS, source=str(path))
    if sin_fichero and ficheros:
        raise ShmirDesignError(
            f"{path}: dice `sin_fichero` y además lista ficheros. Una de las dos cosas "
            f"es mentira; se aborta."
        )
    if not sin_fichero and not ficheros:
        raise ShmirDesignError(
            f"{path}: no lista ningún fichero y no dice `sin_fichero = true`. Si el "
            f"frente no se cierra descargando nada hay que decirlo con esas palabras."
        )
    if sin_fichero and not str(datos.get("por_que_sin_fichero", "")).strip():
        raise ShmirDesignError(
            f"{path}: dice `sin_fichero` y no explica por que. «No hay fichero» sin "
            f"motivo se lee como «nadie lo ha buscado»."
        )

    return Ficha(
        front=datos["frente"],
        question=datos["pregunta"],
        source=datos["fuente"],
        url=datos["url"],
        size=datos["tamano"],
        validation=datos["validacion"],
        steps=tuple(datos["pasos"]),
        files=ficheros,
        metadata=_rows(datos, "metadatos", Metadato, _META_KEYS, source=str(path)),
        warnings=tuple(datos.get("avisos", ())),
        no_file=sin_fichero,
        why_no_file=str(datos.get("por_que_sin_fichero", "")),
    )


def load_all(directory: Path | str = FICHA_DIR) -> dict[str, Ficha]:
    """Todas las fichas, por frente. Sin resolver: llevan marcadores dentro."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ShmirDesignError(
            f"No existe {directory}: sin las fichas de obtencion, cada NOT_RUN vuelve a "
            f"mandar al usuario a preguntar fuera de la app."
        )
    fichas = {}
    for ruta in sorted(directory.glob("*.toml")):
        ficha = load_ficha(ruta)
        fichas[ficha.front] = ficha
    if not fichas:
        raise ShmirDesignError(f"{directory} no tiene ninguna ficha; se aborta.")
    return fichas


# ─────────────────────────── resolucion contra la especie ─────────────────────────


def _values(species) -> dict[str, str]:
    """Que sabe el proyecto de esta especie. Lo que no sabe, VACIO — no se deduce."""
    return {
        "slug": species.slug,
        "cientifico": species.scientific,
        "prefijo": species.mirbase_prefix,
        "taxid": species.taxid,
        "ensamblaje": getattr(species, "ucsc_assembly", ""),
    }


#: Como se lee un hueco. Cada uno dice DONDE se declara, para que quien lo lea pueda
#: cerrarlo en vez de quedarse mirando.
_UNDECLARED = {
    "prefijo": (
        "el prefijo de miRBase de {cientifico} NO ESTÁ DECLARADO en este proyecto. Se "
        "mira en mirbase.org (la especie viene en el nombre de cada maduro) y se añade a "
        "`species.SPECIES`. NO se deduce del nombre: `ocu-`, `oc-` y `ory-` son todos "
        "plausibles y solo uno existe."
    ),
    "taxid": (
        "el taxid de {cientifico} NO ESTÁ DECLARADO en este proyecto. Se mira en el "
        "Taxonomy Browser del NCBI y se añade a `species.SPECIES`."
    ),
    "ensamblaje": (
        "el ensamblaje de UCSC de {cientifico} NO ESTÁ DECLARADO en este proyecto. Se "
        "elige en el propio Table Browser y se añade a `species.SPECIES` — anotandolo, "
        "porque dos ensamblajes distintos dan coordenadas distintas."
    ),
}


def _substitute(texto: str, valores: dict[str, str], huecos: set[str]) -> str:
    def cambia(match: re.Match) -> str:
        clave = match.group(1)
        if clave not in valores:
            raise ShmirDesignError(
                f"La ficha usa el marcador {{{clave}}}, que no existe. Los que hay son "
                f"{', '.join(sorted(valores))}. Se aborta en vez de dejarlo escrito tal "
                f"cual."
            )
        valor = valores[clave]
        if valor:
            return valor
        huecos.add(clave)
        plantilla = _UNDECLARED.get(
            clave, f"{clave} no está declarado para esta especie"
        )
        return plantilla.format(cientifico=valores["cientifico"])

    return _PLACEHOLDER.sub(cambia, texto)


def resolve_ficha(front: str, *, species) -> Ficha:
    """La ficha de un frente, atada a una especie concreta."""
    fichas = load_all()
    ficha = fichas.get(front)
    if ficha is None:
        raise ShmirDesignError(
            f"No hay ficha de obtencion para el frente {front!r}. Las que hay son: "
            f"{', '.join(sorted(fichas))}. Un frente sin ficha deja al usuario "
            f"preguntando fuera de la app; añade data/obtencion/{front}.toml."
        )
    valores = _values(species)
    huecos: set[str] = set()

    def sub(texto: str) -> str:
        return _substitute(texto, valores, huecos)

    resuelta = Ficha(
        front=ficha.front,
        question=sub(ficha.question),
        source=sub(ficha.source),
        url=ficha.url,
        size=ficha.size,
        validation=sub(ficha.validation),
        steps=tuple(sub(p) for p in ficha.steps),
        files=tuple(
            FichaFile(name=sub(f.name), why=sub(f.why), required=f.required)
            for f in ficha.files
        ),
        metadata=tuple(
            Metadato(name=sub(m.name), why=sub(m.why)) for m in ficha.metadata
        ),
        warnings=tuple(sub(a) for a in ficha.warnings),
        no_file=ficha.no_file,
        why_no_file=sub(ficha.why_no_file),
        resolved=True,
        undeclared=tuple(sorted(huecos)),
    )
    if not huecos:
        return resuelta
    # Un hueco NO se queda solo dentro de un paso: sale ademas como aviso, porque un
    # paso largo se lee en diagonal y esto es lo que impide cerrar el frente.
    avisos = tuple(
        _UNDECLARED[clave].format(cientifico=valores["cientifico"])
        for clave in sorted(huecos)
        if clave in _UNDECLARED
    )
    return Ficha(**{**resuelta.__dict__, "warnings": avisos + resuelta.warnings})
