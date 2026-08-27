"""Deposito de ficheros de referencia: subir, validar, registrar.

**El problema que cierra.** Unos ficheros se subian por la interfaz y otros habia que
DEPOSITAR a mano en `data/reference/`, que es un directorio del repositorio. Alguien que
no conoce el arbol del repositorio —que es exactamente el usuario para el que se escribe
esta app— no podia usarla. Aqui todos entran por el mismo sitio.

**Y desaparece la casilla global.** «Usar los de `data/reference/`» era una trampa: su
unico efecto posible al desmarcarla era dejarlo todo en NOT_RUN sin decir por que. Si un
fichero esta y es valido, se usa. Ignorar uno a proposito sigue siendo posible, pero
**por fichero y con el motivo escrito**, y ese motivo viaja al veredicto.

Lo que NO cambia, y es lo que hace que esto sea aceptable:

  - **la validacion la hace el cargador de verdad**, el mismo que usa el filtro. Un
    fichero que pasa aqui y falla despues seria peor que no validarlo;
  - **el md5 se calcula del fichero**, nunca se declara;
  - **nada entra sin quedar en el manifiesto**, que sigue siendo texto y sigue
    versionado: subir por la interfaz se ve en el `git diff` igual que editarlo a mano;
  - **si la validacion falla no se escribe nada**: ni el fichero ni la linea.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .errors import ShmirDesignError
from .manifest import ROLES, ManifestEntry, Role, register_entry
from .species import RequiredFile, Species, file_for, fixture_report, required_files

#: Por que no hay una casilla global. Va en la interfaz, no en un comentario.
WHY_NO_GLOBAL_TOGGLE = (
    "No hay ninguna casilla de «usar los ficheros de referencia». Su único efecto "
    "posible al desmarcarla era dejar todos los filtros con fichero en NOT_RUN sin decir "
    "por que, y eso no es una opción: es una trampa. Si un fichero está y es válido, se "
    "usa. Ignorar uno a propósito se hace POR FICHERO y con el motivo escrito, que viaja "
    "al veredicto."
)


@dataclass(frozen=True)
class Ignored:
    """Ignorar un fichero que ESTA y es valido. El motivo es obligatorio."""

    filename: str
    reason: str

    def __post_init__(self) -> None:
        if not str(self.filename).strip():
            raise ShmirDesignError("Ignorar un fichero exige decir cual.")
        if not str(self.reason).strip():
            raise ShmirDesignError(
                f"Ignorar {self.filename!r} exige un motivo ESCRITO: viaja al veredicto, "
                f"que es lo único que distingue «se decidio no usarlo» de «no estaba». "
                f"Sin motivo se aborta en vez de dejar un NOT_RUN mudo."
            )

    @property
    def note(self) -> str:
        return (
            f"{self.filename} NO se ha usado por decisión explicita: {self.reason}. El "
            f"filtro que dependia de el queda en NOT_RUN, y NOT_RUN no es PASS."
        )


# ───────────────────────────── validacion por rol ─────────────────────────────
#
# Cada rol se valida con el cargador que usa su filtro. No hay una validacion «ligera»
# propia de la subida: un fichero que pasara aqui y fallara al correr el filtro seria
# peor que no validarlo, porque la barra lateral diria «presente» y el frente saldria
# NOT_RUN sin motivo visible.


def _fasta(path: Path, *, what: str):
    from .specificity import load_database

    return load_database(path, name=what, version="subido por la interfaz")


def _v_refseq(path, contexto):
    return _fasta(path, what="RefSeq RNA")


def _v_transgen(path, contexto):
    return _fasta(path, what="casete del transgén")


def _v_mirbase(path, contexto):
    from .mirna import load_mature_fa

    return load_mature_fa(path, version="subido por la interfaz")


def _v_abundancia(path, contexto):
    from .mirna import load_abundance_list

    return load_abundance_list(path, version="subido por la interfaz")


def _v_transcriptoma(path, contexto):
    from .seed_load import load_utr3_set

    return load_utr3_set(path, version="subido por la interfaz")


def _v_expresion(path, contexto):
    from .seed_load import load_expression_table

    return load_expression_table(path)


def _v_apa(path, contexto):
    from .apa import load_apa_sites

    return load_apa_sites(path, version="subido por la interfaz")


def _v_rmsk(path, contexto):
    """El `.out` y el `.tbl`. Del todo, solo se pueden validar JUNTOS.

    Los dos ficheros de una corrida llegan de uno en uno, asi que hay que poder aceptar
    el primero. Lo que se comprueba de cada uno a solas va escrito en
    `masking.check_out_shape` y `masking.check_summary`: del `.out` solo la FORMA —la
    especie de la biblioteca no esta ahi y esta demostrado con md5 que una corrida buena
    y una contra la biblioteca equivocada dan `.out` identicos byte a byte—; del `.tbl`,
    la especie y la longitud de la consulta, que es para lo que existe.

    En cuanto estan los dos se valida la corrida entera con el cargador de verdad. Y
    mientras falte uno el frente NO se abre, que es lo que `fixture_report` ya exige.
    """
    from .masking import check_out_shape, check_summary, load_rmsk

    ruta = Path(path)
    especie = contexto["species"].scientific.lower()
    nombre = contexto["filename"]
    es_resumen = nombre.lower().endswith(".tbl")
    pareja = (
        ruta.parent / nombre.lower().replace(".tbl", ".out")
        if es_resumen
        else ruta.parent / nombre.lower().replace(".out", ".tbl")
    )
    if es_resumen:
        check_summary(
            ruta.read_text(encoding="utf-8", errors="replace"),
            source=nombre,
            expected_species=especie,
        )
        if not pareja.is_file():
            return None
        return load_rmsk(
            pareja,
            version="subido por la interfaz",
            expected_species=especie,
            summary_path=ruta,
        )
    check_out_shape(
        ruta.read_text(encoding="utf-8", errors="replace"), source=nombre
    )
    if not pareja.is_file():
        return None
    return load_rmsk(
        ruta,
        version="subido por la interfaz",
        expected_species=especie,
        summary_path=pareja,
    )


#: Un validador por rol. Hay test de que cubre EXACTAMENTE los roles del manifiesto.
VALIDATORS = {
    "refseq": _v_refseq,
    "mirbase": _v_mirbase,
    "abundancia": _v_abundancia,
    "transcriptoma": _v_transcriptoma,
    "expresion": _v_expresion,
    "rmsk": _v_rmsk,
    "transgen": _v_transgen,
    "apa": _v_apa,
}


def role_for(species: Species, filename: str) -> Role | None:
    """El rol de un fichero PARA ESTA ESPECIE. No se busca por el nombre a secas.

    `manifest.role_of` compara contra `manifest.ROLES`, que trae `rmsk_mouse.out`
    ESCRITO: con otra especie no encontraba nada y no habia forma de subir su mascara.
    El nombre lo pone `species.required_files`; el rol viene con el.
    """
    fila = file_for(species, filename)
    if fila is None:
        return None
    for rol in ROLES:
        if rol.role == fila.role:
            return rol
    return None


@dataclass(frozen=True)
class UploadResult:
    """Lo que paso al subir un fichero. Se devuelve entero para poder pintarlo."""

    filename: str
    role: str
    md5: str
    size: int
    #: Frentes que este fichero podia cerrar y que AHORA quedan cerrados.
    fronts_opened: tuple[str, ...]
    #: Lo que sigue faltando para esos frentes (el hermano, el otro fichero…).
    still_missing: tuple[str, ...]
    #: `True` si la linea del manifiesto ya existia y se ha sustituido.
    replaced: bool
    what: str

    def render(self) -> str:
        lineas = [
            f"{self.filename} — {self.size} B — md5 {self.md5}",
            f"  Desbloquea: {self.what}",
            (
                "  Registrado en el manifiesto (línea sustituida)."
                if self.replaced
                else "  Registrado en el manifiesto (línea nueva)."
            ),
        ]
        if self.fronts_opened:
            lineas.append("  Frentes que quedan CERRADOS: " + ", ".join(self.fronts_opened))
        if self.still_missing:
            lineas.append(
                "  Sigue faltando, así que el frente NO se abre todavia: "
                + ", ".join(self.still_missing)
            )
        return "\n".join(lineas)


def _presentes(directory: Path) -> set[str]:
    return {p.name for p in directory.iterdir() if p.is_file()}


def _cerrados(species: Species, presentes) -> set[str]:
    """Los frentes que `fixture_report` da por cerrables con esos ficheros.

    Se pregunta a `fixture_report` en vez de contarlo aqui: dos contadores del mismo
    suceso que discrepen es un fallo silencioso, y este proyecto ya lo ha tenido.
    """
    informe = fixture_report(species, have=tuple(presentes))
    return {k for f in informe.rows if f.available for k in f.keys}


def accept_upload(
    directory: Path | str,
    *,
    filename: str,
    payload: bytes,
    species: Species,
    origin: str,
    date: str,
    accession: str = "",
    length: int | None = None,
    url: str = "",
    library: str = "",
) -> UploadResult:
    """Recibe un fichero de referencia por la interfaz: valida, escribe y registra.

    El orden importa y es el unico correcto: se valida ANTES de escribir nada. Un
    fichero que se escribe y luego se rechaza deja el directorio con algo que la
    siguiente comprobacion contara como presente.
    """
    directory = Path(directory)
    fila = file_for(species, filename)
    if fila is None:
        esperados = ", ".join(
            n for f in required_files(species) for n in f.filenames
        )
        raise ShmirDesignError(
            f"{filename!r} no es un fichero que {species.scientific} necesite. Los que "
            f"necesita se llaman: {esperados}. El nombre no es cosmetico: el manifiesto "
            f"conecta cada fichero con su filtro POR EL NOMBRE, así que un fichero de "
            f"otra especie depositado con este nombre correria contra la secuencia "
            f"equivocada sin dar ningún error — es exactamente lo que paso con "
            f"`rmsk_mouse.out` sobre el transcrito humano."
        )

    rol = role_for(species, filename)
    if rol is None:  # pragma: no cover - lo fija el test de que ROLES los cubre todos
        raise ShmirDesignError(
            f"El rol {fila.role!r} no está en `manifest.ROLES`, así que no habría filtro "
            f"al que conectar {filename!r}. Se aborta."
        )

    antes = _cerrados(species, _presentes(directory))

    # Se escribe a un temporal AL LADO: el validador necesita una ruta, y el directorio
    # definitivo no puede tener el fichero hasta que la validacion pase.
    provisional = directory / f".{filename}.subiendo"
    try:
        provisional.write_bytes(payload)
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo escribir {filename!r} en {directory} ({exc}); no se registra "
            f"nada."
        ) from exc

    try:
        VALIDATORS[rol.role](provisional, {"species": species, "filename": filename})
    except BaseException:
        # rule2-ok: no se traga nada. Se borra el provisional para no dejar basura y se
        # RELANZA el fallo entero: el mensaje del cargador es la validacion.
        provisional.unlink(missing_ok=True)
        raise

    md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    destino = directory / filename
    provisional.replace(destino)

    entrada = ManifestEntry(
        name=filename,
        filter_name=rol.what,
        size=len(payload),
        md5=md5,
        date=date,
        origin=origin,
        accession=accession,
        length=length,
        url=url,
        library=library,
    )
    actualizacion = register_entry(directory, entrada)

    presentes = _presentes(directory)
    despues = _cerrados(species, presentes)
    faltan = tuple(n for n in fila.filenames if n not in presentes)
    return UploadResult(
        filename=filename,
        role=rol.role,
        md5=md5,
        size=len(payload),
        fronts_opened=tuple(sorted(despues - antes)),
        still_missing=faltan,
        replaced=actualizacion.replaced,
        what=fila.what,
    )
