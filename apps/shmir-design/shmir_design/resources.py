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
from .errors import ShmirDesignError


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
            "la tabla de expresión sin los 3'UTR del transcriptoma no tiene sitios que "
            "ponderar."
        )
    return load_expression_table(path)


def _rmsk(path, entry, contexto):
    """La mascara, con la especie y el resumen DERIVADOS del manifiesto.

    Nada de esto se teclea. La especie sale del organismo de la referencia que el
    manifiesto declara en `accession`; el resumen, del `.tbl` hermano. Si falta
    cualquiera de los dos se aborta: un `.out` a solas no se puede validar — los tres
    `.out` reales del 2026-08-26 ni siquiera declaran la especie, que vive en el `.tbl`.
    """
    from .reference import REFERENCES

    ruta = Path(path)
    if ruta.suffix.lower() == ".out":
        if not entry.accession:
            raise ShmirDesignError(
                f"{ruta.name}: el manifiesto no dice sobre que accession se corrió, así "
                f"que no se puede saber que especie esperar ni comprobar que la máscara "
                f"es de esta secuencia. Se aborta."
            )
        referencia = REFERENCES.get(entry.accession)
        if referencia is None:
            raise ShmirDesignError(
                f"{ruta.name}: el manifiesto declara accession {entry.accession!r}, que "
                f"no está en REFERENCES, así que no hay de donde sacar la especie "
                f"esperada. Se aborta en vez de saltarse la comprobación."
            )
        resumen = ruta.with_suffix(".tbl")
        if not resumen.is_file():
            raise ShmirDesignError(
                f"{ruta.name}: falta su resumen ({resumen.name}). Sin el no se sabe "
                f"contra que biblioteca se corrió —la línea de la especie vive ahi, no "
                f"en el .out— ni cuántos nt se analizaron. Se aborta."
            )
        return load_rmsk(
            path,
            version=entry.date or entry.md5,
            expected_md5=entry.md5,
            expected_species=referencia.organism.lower(),
            library=entry.library or None,
            summary_path=resumen,
        )
    return load_rmsk(path, version=entry.date or entry.md5, expected_md5=entry.md5)


def _transgen(path, entry, contexto):
    return load_database(
        path,
        name="casete del transgén",
        version=entry.date or entry.md5,
        expected_md5=entry.md5,
    )


def _apa(path, entry, contexto):
    return load_apa_sites(
        path, version=entry.date or entry.md5, expected_md5=entry.md5
    )


def _polyadb(path, entry, contexto):
    """La tabla de PolyA_DB. Su version y su ensamblaje van DENTRO del fichero, no en el
    manifiesto: son parte del dato, no de como se guardo."""
    from .apa import load_polyadb  # noqa: PLC0415

    return load_polyadb(path, expected_md5=entry.md5)


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
    "polyadb": _polyadb,
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
    ("polyadb", "polyadb"),
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
    #: La tabla de PolyA_DB, si esta. `tile_utr` la resuelve por su cuenta del
    #: directorio de referencia, asi que esto es para quien quiera pasarla explicita.
    polyadb: object | None = None
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
            lineas.append(describe_connected(self.connected, indent="  "))
        else:
            lineas.append(
                "No se ha conectado ningún fichero de referencia: los filtros que "
                "dependen de uno quedaran en NOT_RUN."
            )
        if self.notes:
            lineas.append("")
            lineas.extend(f"  ⚠  {n}" for n in self.notes)
        return "\n".join(lineas)


def roles_for_species(estado: DirectoryStatus, especie) -> dict:
    """Los roles conectables PARA ESTA ESPECIE: rol -> `species.RequiredFile`.

    `manifest.roles_available` empareja por el NOMBRE contra `manifest.ROLES`, que trae
    `rmsk_mouse.out` escrito. Con otra especie eso conectaba el fichero del raton por su
    rol sin mirar que se estaba diseñando — el intervalo murino tx:892-936 cabe de sobra
    en los 2435 nt del humano y no salta ninguna alarma. Aqui el nombre lo pone
    `species.required_files`, asi que un fichero de otra especie sencillamente no aparece.
    """
    from .manifest import EntryStatus
    from .species import required_files

    por_nombre = {f.filename: f for f in required_files(especie)}
    disponibles = {}
    for resultado in estado.results:
        if resultado.status is not EntryStatus.OK:
            continue
        fila = por_nombre.get(resultado.entry.name)
        if fila is not None:
            disponibles[fila.role] = fila
    return disponibles


def load_from_manifest(
    directory: Path | str, *, target: str | None = None, ignore=(), species=None
) -> ResourceSet:
    """Carga todo lo que este en OK en ese directorio. Lo que no, se anota.

    `ignore` son `deposito.Ignored`: ficheros que ESTAN y son validos y que aun asi no
    se quieren usar. No hay ninguna casilla global para esto —su unico efecto posible al
    desmarcarla era dejarlo todo en NOT_RUN sin decir por que— asi que se hace por
    fichero y con el MOTIVO escrito, y ese motivo se anota en `notes` para que llegue al
    veredicto. Sin eso, «se decidio no usarlo» y «no estaba» serian el mismo NOT_RUN.
    """
    estado = check_directory(directory)
    disponibles = (
        {r.role: r for r in roles_available(estado)}
        if species is None
        else roles_for_species(estado, species)
    )

    ignorados = {i.filename: i for i in ignore}
    sobran = set(ignorados) - {r.filename for r in disponibles.values()}
    if sobran:
        raise ShmirDesignError(
            f"Se ha pedido ignorar {sorted(sobran)}, y esos ficheros no estaban "
            f"conectados de todas formas. Se aborta: un motivo escrito para un fichero "
            f"que no se iba a usar deja en el informe una decisión que nadie tomo."
        )

    cargado: dict[str, object] = {}
    conectados: list[str] = []
    notas: list[str] = []
    contexto: dict[str, object] = {"target": target}

    for role, destino in DESTINOS:
        rol = disponibles.get(role)
        if rol is None:
            continue
        ignorado = ignorados.get(rol.filename)
        if ignorado is not None:
            notas.append(ignorado.note)
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


# ─────────────── Los ficheros que NO tienen rol propio pero hacen falta ───────────────
#
# `connected` lista un fichero por ROL, y el resumen `.tbl` de RepeatMasker no es un rol:
# es el compañero obligatorio del `.out`. Resultado en pantalla: «Ficheros de referencia
# conectados (1) · rmsk_mouse.out» con el frente `repeticiones` cerrado — que se lee
# exactamente como «un `.out` a solas ha cerrado el frente», que es justo lo que este
# proyecto promete no hacer y NO estaba haciendo (sin el `.tbl`, `_rmsk` aborta; hay
# test). Lo que fallaba era la pantalla, y una pantalla que contradice al codigo cuesta
# lo mismo que el codigo equivocado: hay que ir a leer el fuente para saber cual manda.
COMPANION_NOTE = (
    "El `.tbl` es el resumen de la corrida y es OBLIGATORIO: la línea que declara contra "
    "que biblioteca se corrió vive ahi, no en el `.out`. Sin el no se conecta la máscara."
)

#: Que compañero obligatorio lleva cada fichero. Se DERIVA de `species.required_files`
#: cuando hay especie; el mapa de aqui es el mismo por extension, para los sitios que no
#: tienen especie a mano.
COMPANION_SUFFIX = {".out": ".tbl"}


def companions_of(names) -> dict[str, tuple[str, ...]]:
    """El compañero obligatorio de cada nombre, si lo tiene."""
    from pathlib import Path as _Path

    salida: dict[str, tuple[str, ...]] = {}
    for nombre in names:
        sufijo = COMPANION_SUFFIX.get(_Path(nombre).suffix.lower())
        if sufijo:
            salida[nombre] = (_Path(nombre).with_suffix(sufijo).name,)
    return salida


def describe_connected(names, *, companions=None, indent: str = "  ") -> str:
    """La lista de conectados NOMBRANDO el compañero obligatorio de cada uno.

    Ver `COMPANION_NOTE`: sin esto, la pantalla decia «1 fichero conectado» de algo que
    necesita dos, y el frente cerrado al lado se leia como una contradiccion.
    """
    mapa = companions_of(names) if companions is None else dict(companions)
    lineas = []
    for nombre in names:
        acompanantes = tuple(mapa.get(nombre, ()))
        if acompanantes:
            lineas.append(
                f"{indent}· {nombre}  (+ {', '.join(acompanantes)}, obligatorio)"
            )
        else:
            lineas.append(f"{indent}· {nombre}")
    if any(mapa.get(n) for n in names):
        lineas.append(f"{indent}  {COMPANION_NOTE}")
    return "\n".join(lineas)
