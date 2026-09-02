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

from dataclasses import dataclass
from pathlib import Path

from .errors import ShmirDesignError
from .identidad import file_fingerprint
from .manifest import MANIFEST_NAME, ROLES, ManifestEntry, Role, register_entry
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


def _v_plasmido_andamio(path, contexto):
    """El plásmido del andamio: se valida ANCLÁNDOLO, que es para lo que sirve.

    No basta con que sea un GenBank legible. Lo que hace útil a este fichero es que sus
    contextos sean los del módulo que se manda a sintetizar, así que la validación de la
    subida es exactamente la comprobación que luego va a correr: si el fichero no lleva la
    anotación del loop, o el andamio no está, o los contextos no coinciden, **no entra**.
    Un fichero que pasara aquí y fallara al emitir el módulo sería peor que no validarlo.
    """
    from .gblock import verify_contexts_against_plasmid

    verify_contexts_against_plasmid(
        Path(path).read_text(encoding="utf-8", errors="replace")
    )
    return None


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
    "plasmido_andamio": _v_plasmido_andamio,
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


# ─────────────────── la procedencia de una TABLA, pedida al SUBIR ───────────────────
#
# **Es la procedencia de un FICHERO, no la de una corrida**, y esa distincion es la que
# ordena todo lo de abajo. La del fichero —de que ensamblaje, de que tabla, de que fecha
# y con que criterio de representante— pertenece al DEPOSITO y se pide UNA VEZ, al
# entrar; la de la corrida es fecha, quien y parametros, y esa si va con cada corrida.
#
# El modal de carga de off-targets pedia los seis campos de `offtarget.Provenance` EN
# CADA CORRIDA, siendo cuatro de ellos un dato del fichero que el deposito ya tenia
# delante. Dos copias del mismo dato acaban divergiendo y nadie sabe cual manda.
#
# **Y por eso son OBLIGATORIAS AQUI y no opcionales con casilla vacia**: si
# `offtarget.Provenance` las exige para dar veredicto, un fichero sin ellas entraria al
# deposito, figuraria como PRESENTE, y bloquearia el frente tres pantallas despues sin
# decir por que. El rechazo va donde entra el fichero, con el motivo.

#: Los cuatro campos. NO se eligen aqui: son los de `offtarget.Provenance` que el
#: manifiesto no tenia ya. Los otros tres de esa clase los tiene desde siempre —`source`
#: es el origen, `version` sale de la fecha y `md5` se calcula del fichero—, y hay un
#: test que lo cruza: si esa lista creciera, esta se quedaria corta y el modal tendria
#: que seguir preguntando.
PROVENANCE_FIELDS = ("assembly", "table", "table_date", "representative")

#: Como se llama cada uno en el manifiesto. La columna es castellano porque el
#: manifiesto se lee con `cat`; el campo es el de `Provenance`, para poder cruzarlos.
MANIFEST_COLUMN_FOR = {
    "assembly": "ensamblaje",
    "table": "tabla",
    "table_date": "fecha_tabla",
    "representative": "representante",
}

#: Que se le pide a quien sube, con la ayuda que necesita para contestarlo. La ETIQUETA
#: y la AYUDA viven aqui y no en la pagina: son texto que decide si alguien pone el dato
#: bueno o el de otra especie (regla 6).
PROVENANCE_LABELS = {
    "assembly": (
        "Ensamblaje",
        "El de la especie que se está analizando, tal como lo nombra el navegador de "
        "genomas (mm39, hg38…). El de otra especie da un conteo con la forma correcta "
        "sobre el genoma equivocado.",
    ),
    "table": (
        "Tabla",
        "El grupo y la tabla exactos del Table Browser, por su nombre — «NCBI RefSeq» y "
        "la región «3' UTR Exons». Una tabla curada y una con predichos NO dan el mismo "
        "conteo.",
    ),
    "table_date": (
        "Fecha de la tabla",
        "Cuando se descargo (AAAA-MM-DD). Las tablas se actualizan, así que sin fecha el "
        "conteo no se puede repetir.",
    ),
    "representative": (
        "Criterio de representante",
        "Que se hizo con las varias isoformas de un mismo gen. Si no se filtro nada "
        "—que es lo que la ficha manda—, se escribe eso: el conteo sale inflado y hay "
        "que poder saberlo.",
    ),
}

#: EN QUE ROLES son obligatorias, con el motivo escrito. Es una tabla y no una regla
#: general porque la mayoria de los ficheros no salen de ninguna tabla: un casete de AAV
#: no tiene ensamblaje, y ahi la columna vacia es la VERDAD, no un hueco.
PROVENANCE_REQUIRED = {
    "transcriptoma": (
        "El catalogo de 3'UTR es el ÚNICO fichero de hoy del que se cuenta algo: la "
        "carga de off-targets por seed sale de barrerlo entero, y `offtarget.Provenance` "
        "EXIGE los cuatro para poder emitir veredicto."
    ),
}


def _exigir_procedencia(rol: str, valores: dict[str, str]) -> None:
    """Aborta si al rol le falta alguno de los cuatro. ANTES de escribir nada."""
    motivo = PROVENANCE_REQUIRED.get(rol)
    if motivo is None:
        return
    faltan = [c for c in PROVENANCE_FIELDS if not str(valores.get(c, "")).strip()]
    if not faltan:
        return
    nombres = ", ".join(MANIFEST_COLUMN_FOR[c] for c in faltan)
    raise ShmirDesignError(
        f"Falta la procedencia de la tabla: {nombres}. {motivo} Sin ensamblaje, tabla, "
        f"fecha y criterio de representante el conteo NO es reproducible — la misma "
        f"regla que la versión de miRBase y la biblioteca de Dfam. Se rechaza AQUÍ, en "
        f"la subida, y no al pedir el veredicto: un fichero sin procedencia entraria al "
        f"deposito, figuraria como presente, y dejaria el frente bloqueado tres "
        f"pantallas después sin decir por que. Una casilla en blanco cuenta como no "
        f"puesta."
    )


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
    assembly: str = "",
    table: str = "",
    table_date: str = "",
    representative: str = "",
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

    # ANTES de escribir nada: un fichero sin la procedencia que su frente exige no
    # entra. Va aqui y no tras la validacion porque no depende del contenido —es lo que
    # el usuario declara— y porque rechazar despues de escribir el provisional seria
    # trabajo tirado.
    _exigir_procedencia(
        rol.role,
        {
            "assembly": assembly, "table": table,
            "table_date": table_date, "representative": representative,
        },
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

    md5 = file_fingerprint(payload)
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
        assembly=assembly,
        table=table,
        table_date=table_date,
        representative=representative,
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


# ══════════════════ EL LECTOR DEL DEPOSITO: UN SOLO SITIO ══════════════════
#
# **El fallo que cierra.** El modal de carga de off-targets NO VEIA EL DEPOSITO: pedia
# soltar `transcriptoma_3utr.fa` aunque ya estuviera dentro, y ademas pedia los SEIS
# campos de `offtarget.Provenance` —fuente, ensamblaje, tabla, fecha, representante y
# version— que ya se habian declarado al subirlo. El de BLAST hacia lo mismo con la
# base: nombre, version y md5 tecleados a mano teniendo la linea del manifiesto delante.
#
# Eso es DOS COPIAS DEL MISMO DATO. La del deposito la escribio quien subio el fichero;
# la del modal la teclea quien corre, sin nada que las ate — y cuando divergen, ninguna
# de las dos dice cual manda. O peor: quien no se acuerda del ensamblaje se lo inventa,
# y el conteo sale con la forma correcta sobre el genoma equivocado.
#
# **La lectura sale de UN SOLO SITIO**, como `_filter_columns` con el estado por filtro.
# Los cuatro modales preguntan aqui; ninguno abre el manifiesto por su cuenta. Si cada
# uno lo abriera, el quinto se quedaria fuera sin que nadie lo note — la leccion de
# `offtarget_seed`.


@dataclass(frozen=True)
class DepositFile:
    """Lo que el deposito sabe de UN fichero: si esta, su md5 y su procedencia."""

    role: str
    filename: str
    present: bool
    size: int = 0
    md5: str = ""
    entry: ManifestEntry | None = None

    @property
    def registered(self) -> bool:
        """¿Tiene linea en el manifiesto? Estar y estar registrado son cosas distintas."""
        return self.entry is not None

    @property
    def stale_md5(self) -> bool:
        """El fichero de disco NO es el que el manifiesto registra.

        No es un detalle de presentacion: el md5 del manifiesto es el que viaja con el
        veredicto, asi que si no coincide lo que se guardaria seria la procedencia de
        OTRO fichero.
        """
        return bool(self.entry) and bool(self.md5) and self.entry.md5 != self.md5

    @property
    def missing_provenance(self) -> tuple[str, ...]:
        """Los campos de procedencia de tabla que este rol exige y no tiene.

        Sale VACIO en dos casos que no se confunden: el rol no las exige (un casete no
        sale de ninguna tabla), o las tiene todas. Lo que lo distingue es
        `PROVENANCE_REQUIRED`, no esta lista.
        """
        if self.role not in PROVENANCE_REQUIRED or self.entry is None:
            return ()
        return tuple(
            MANIFEST_COLUMN_FOR[c]
            for c in PROVENANCE_FIELDS
            if not str(getattr(self.entry, c, "")).strip()
        )

    def provenance_fields(self) -> dict[str, str]:
        """Los SIETE de `offtarget.Provenance`, sacados de la linea del manifiesto.

        Cuatro son las columnas nuevas; los otros tres los tenia desde siempre —`source`
        es el origen, `version` sale de la fecha (o del md5 si no la hay, igual que
        `resources`) y `md5` es el del fichero—. Se derivan aqui para que nadie los
        vuelva a teclear.
        """
        if self.entry is None:
            return {}
        return {
            "source": self.entry.origin,
            "assembly": self.entry.assembly,
            "table": self.entry.table,
            "table_date": self.entry.table_date,
            "representative": self.entry.representative,
            "version": self.entry.date or self.entry.md5,
            "md5": self.entry.md5,
        }

    def describe(self) -> str:
        if not self.present:
            return (
                f"{self.filename} NO está en el depósito. Mientras falte, el frente que "
                f"depende de él se queda en NOT_RUN — y NOT_RUN no es PASS."
            )
        lineas = [f"{self.filename} — {self.size} B — md5 {self.md5}"]
        if not self.registered:
            lineas.append(
                "Está en el directorio y NO tiene línea en el manifiesto, así que no "
                "hay procedencia que adjuntar al veredicto. Vuelve a subirlo por el "
                "gestor para registrarlo."
            )
            return " ".join(lineas)
        if self.stale_md5:
            lineas.append(
                f"OJO: el manifiesto registra md5 {self.entry.md5}, que NO es el del "
                f"fichero que hay. La procedencia registrada es la de OTRO fichero."
            )
        if self.entry.origin:
            lineas.append(f"Origen: {self.entry.origin}.")
        if self.entry.date:
            lineas.append(f"Registrado el {self.entry.date}.")
        procedencia = [
            f"{MANIFEST_COLUMN_FOR[c]}: {getattr(self.entry, c)}"
            for c in PROVENANCE_FIELDS
            if str(getattr(self.entry, c, "")).strip()
        ]
        if procedencia:
            lineas.append(" · ".join(procedencia) + ".")
        if self.missing_provenance:
            lineas.append(
                f"Le falta procedencia de tabla ({', '.join(self.missing_provenance)}): "
                f"se registró antes de que se pidiera. Reemplázalo por el gestor para "
                f"declararla."
            )
        return " ".join(lineas)


def read_deposit(role: str, *, species: Species, directory: Path | str) -> DepositFile:
    """QUE HAY en el depósito para ese rol, con su procedencia. Un solo sitio.

    El NOMBRE lo pone `species.required_files` —la única fuente de los nombres del
    depósito— y no se escribe: escribirlo aquí sería la tercera copia, y ya se sabe cómo
    acaban (errata nº 47, la comparación de md5 que no podía darse nunca).
    """
    from .manifest import load_manifest
    from .presencia import hay_fichero
    from .species import required_files

    directory = Path(directory)
    fila = next((f for f in required_files(species) if f.role == role), None)
    if fila is None:
        raise ShmirDesignError(
            f"El rol {role!r} no está entre los ficheros que "
            f"{species.scientific} necesita, así que no hay nada que leer del depósito. "
            f"Se aborta en vez de devolver «no está», que se leería como que el fichero "
            f"existe y falta."
        )
    nombre = fila.filename
    ruta = directory / nombre
    presente = hay_fichero(ruta)

    entrada = None
    manifiesto = directory / MANIFEST_NAME
    if manifiesto.is_file():
        try:
            entrada = load_manifest(manifiesto).entry(nombre)
        except ShmirDesignError:
            # rule2-ok: que el fichero no tenga linea es un HECHO sobre el deposito, no
            # un fallo del paso — `Manifest.entry` aborta con el que no esta. La lectura
            # sigue: `registered` lo dice, y `describe()` lo escribe.
            entrada = None

    return DepositFile(
        role=role,
        filename=nombre,
        present=presente,
        size=ruta.stat().st_size if presente else 0,
        md5=file_fingerprint(ruta.read_bytes()) if presente else "",
        entry=entrada,
    )
