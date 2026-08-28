"""Manifiesto de `data/reference/`: que fichero se uso, con que checksum y de donde.

Para que existe: sin un registro versionado, una corrida de hace tres meses no es
reproducible y un veredicto no es auditable dentro de un año. No basta con que el
programa diga "especificidad: PASS"; hay que poder decir **con que version de RefSeq**.

Reparto: **el manifiesto se versiona en git, los ficheros NO**. Un RefSeq RNA completo o
un `mature.fa` no tienen por que entrar en el repositorio; lo que tiene que entrar es la
linea que dice cual era y como comprobarlo.

Una linea por fichero: `nombre`, `filtro`, `tamaño`, `md5`, `fecha_descarga`,
`origen`.

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
MANIFEST_COLUMNS = (
    "nombre",
    "filtro",
    "tamaño",
    "md5",
    "fecha_descarga",
    "origen",
    # Las tres de abajo son la contramedida a la errata del 3'UTR fabricado: aquella se
    # detecto por LONGITUD contra las coordenadas declaradas. Con accession CON VERSION
    # y longitud registradas, esa comprobacion se puede hacer sin abrir el fichero, y
    # hay un test que la hace. Van vacias en las entradas que no son un transcrito.
    "accession",
    "longitud",
    "url",
    # La BIBLIOTECA con la que se corrio la herramienta, cuando el fichero es la salida
    # de una: RepeatMasker con Dfam_3.0 y con otra biblioteca dan resultados distintos
    # con la misma version del binario, asi que «RepeatMasker open-4.0.9» a solas NO
    # identifica la corrida. Vacia para los ficheros que no son salida de herramienta.
    "biblioteca",
    # LA ANATOMIA, añadida 2026-08-27. Hasta aqui el manifiesto registraba los FICHEROS
    # —nombre, tamaño, md5, accession, longitud— y la anatomia vivia SOLO en
    # `reference.REFERENCES`: donde empieza el CDS, donde el 3'UTR, y los dos md5
    # CANONICOS. O sea que añadir una especie era editar codigo, y que la frontera de
    # la que cuelgan los tercios, las regiones y las distancias de polyA no tenia linea
    # que la registrara.
    #
    # Van vacias en todo lo que no sea un transcrito, y vacio significa NO REGISTRADO.
    #
    # OJO CON LOS TRES CHECKSUMS, que ahora conviven en la misma fila y son cantidades
    # DISTINTAS: `md5` es el del FICHERO en disco (con cabecera y con saltos de linea),
    # `md5_secuencia` el de la SECUENCIA canonica (mayusculas, sin cabecera, sin saltos)
    # y `md5_utr3` el del 3'UTR canonico. Copiar uno en el sitio de otro hace que el
    # fichero BUENO se rechace.
    "cds",
    "md5_secuencia",
    "md5_utr3",
)

#: El ancho de antes de las columnas de procedencia. Se sigue leyendo.
LEGACY_COLUMNS = MANIFEST_COLUMNS[:6]
#: La cabecera de antes de que existiera `biblioteca` (2026-08-26). Se sigue aceptando:
#: un manifiesto viejo se lee igual y la columna nueva sale vacia, que es la verdad —
#: no se sabe con que biblioteca se corrio.
PREVIOUS_COLUMNS = MANIFEST_COLUMNS[:9]
#: La cabecera de antes de que la ANATOMIA entrara en el manifiesto (2026-08-27). Misma
#: regla: se sigue leyendo y las tres columnas nuevas salen vacias.
BEFORE_ANATOMY_COLUMNS = MANIFEST_COLUMNS[:10]

#: Ficheros del directorio que no son datos y no cuentan como sobrantes.
_NO_SON_DATOS = frozenset({MANIFEST_NAME, ".gitignore"})

_MD5 = re.compile(r"^[0-9a-f]{32}$")


class EntryStatus(StrEnum):
    OK = "OK"
    AUSENTE = "AUSENTE"
    NO_COINCIDE = "NO_COINCIDE"
    SIN_REGISTRAR = "SIN_REGISTRAR"


@dataclass(frozen=True)
class Role:
    """Que filtro desbloquea cada fichero, y que flags del CLI sustituye.

    Vive en CODIGO y no como septima columna del manifiesto por dos razones: el formato
    de seis columnas esta fijado, y una correspondencia editable desde un fichero de
    datos permitiria reasignar un fichero a otro filtro sin que se vea en el diff.
    """

    role: str
    filename: str
    what: str
    replaces: tuple[str, ...]


#: Unico sitio donde vive la correspondencia fichero → filtro. `--usar-manifiesto` la
#: recorre y conecta cada fichero que este en OK con lo que le toca.
ROLES: tuple[Role, ...] = (
    Role(
        role="refseq",
        filename="refseq_rna.fa",
        what="especificidad (paso 12)",
        replaces=("--refseq", "--refseq-name", "--refseq-version", "--refseq-md5"),
    ),
    Role(
        role="mirbase",
        filename="mature.fa",
        what="colisión de seed, nivel aviso (paso 10a)",
        replaces=("--mirbase", "--mirbase-version", "--mirbase-md5"),
    ),
    Role(
        role="abundancia",
        filename="mirgenedb_cerebro.txt",
        what="colisión de seed, nivel FAIL (paso 10a)",
        replaces=("--abundancia", "--abundancia-version", "--abundancia-md5"),
    ),
    Role(
        role="transcriptoma",
        filename="transcriptoma_3utr.fa",
        what="carga de off-targets por seed (paso 10b)",
        replaces=(
            "--transcriptoma-3utr",
            "--transcriptoma-version",
            "--transcriptoma-md5",
        ),
    ),
    Role(
        role="expresion",
        filename="expresion_cerebro.tsv",
        what="ponderación de la carga de seed",
        replaces=("--expresion",),
    ),
    Role(
        role="rmsk",
        filename="rmsk_mouse.out",
        what="elementos repetitivos (paso 2)",
        replaces=("--rmsk", "--rmsk-version", "--rmsk-md5"),
    ),
    Role(
        role="transgen",
        filename="aav_casete.fa",
        what="filtro del transgén (paso 12b)",
        replaces=("--transgen", "--transgen-name", "--transgen-version", "--transgen-md5"),
    ),
    Role(
        role="apa",
        filename="apa_medido.tsv",
        what="APA medido en vez de predicho (tabla simple posición/fracción/nombre)",
        replaces=("--apa-medido", "--apa-version", "--apa-md5"),
    ),
    # OTRA tabla, y por eso otro nombre. `apa_medido.tsv` es la simple —posicion,
    # fraccion, nombre— y esta es la de PolyA_DB, con clase, PSE y AvgRPM por PAS: es la
    # que promueve señales por MEDIDA y la que da el techo por tramos. Fundirlas en un
    # solo fichero seria el patron de los dos contadores que discrepan.
    Role(
        role="polyadb",
        filename="polya_db_mouse.tsv",
        what="tabla de PolyA_DB: los PAS con su clase, PSE y AvgRPM",
        replaces=(),
    ),
)


def role_of(filename: str) -> Role | None:
    """El rol de un fichero, o `None` si no tiene ninguno. No adivina."""
    for rol in ROLES:
        if rol.filename == filename:
            return rol
    return None


@dataclass(frozen=True)
class ManifestEntry:
    name: str
    filter_name: str
    size: int | None
    md5: str
    date: str
    origin: str
    #: Accession CON version (`NM_011170.3`), vacio si el fichero no es un transcrito.
    accession: str = ""
    #: Longitud declarada en nt. `None` si no aplica o no se registro.
    length: int | None = None
    #: De donde se descargo. No la llama ningun codigo: es procedencia, no un endpoint.
    url: str = ""
    #: Biblioteca de la herramienta que genero el fichero (p. ej. Dfam_3.0). Vacia si no
    #: aplica. El veredicto depende de ella tanto como de la version del binario.
    library: str = ""
    #: La ANATOMIA declarada, para un transcrito. `cds` es el par 1-based inclusivo
    #: (185, 949) en la notacion del propio GenBank; `None` si no se registro — y no
    #: registrarla NO es «todo es 3'UTR», que es justo lo que `Anatomy` prohibe.
    cds: tuple[int, int] | None = None
    #: md5 de la SECUENCIA canonica. NO es `md5`, que es el del fichero en disco.
    sequence_md5: str = ""
    #: md5 del 3'UTR canonico. Es el que decide si la tabla de APA medido se aplica.
    utr3_md5: str = ""

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
                "No se uso ningún fichero de referencia: todos los filtros que dependen "
                "de uno quedaron en NOT_RUN.",
            )
        lineas: list[str] = []
        for nombre in used:
            entrada = self.find(nombre)
            lineas.append(
                entrada.as_line()
                if entrada is not None
                else (
                    f"{nombre} — NO ESTÁ EN EL MANIFIESTO: se uso un fichero sin "
                    f"registrar, así que esta corrida no es reproducible. Añadelo a "
                    f"{MANIFEST_NAME}."
                )
            )
        return tuple(lineas)


def _longitud(bruto: str, *, source: str, fila: int) -> int | None:
    """La longitud declarada, o `None` si no se registro. Nunca 0 por defecto."""
    if not bruto:
        return None
    try:
        return int(bruto)
    except ValueError as exc:
        raise ShmirDesignError(
            f"{source}, fila {fila}: la longitud {bruto!r} no es un número. Se aborta: "
            f"esa columna existe para comprobar ficheros, y una que no se puede leer no "
            f"comprueba nada."
        ) from exc


def _cds(bruto: str, *, source: str, fila: int) -> tuple[int, int] | None:
    """`185..949` → `(185, 949)`, o `None` si no se registro.

    Se lee en la notacion del propio GenBank, que es de donde sale, para que la columna
    se pueda cotejar con el `.gb` sin traducir nada. Un par que no se puede leer ABORTA:
    la frontera del 3'UTR es de lo que cuelgan los tercios, las regiones y las
    distancias de polyA, y una anatomia mal leida corre todo eso sin dar ningun error.
    """
    if not bruto:
        return None
    partes = bruto.split("..")
    if len(partes) != 2 or not all(p.strip().isdigit() for p in partes):
        raise ShmirDesignError(
            f"{source}, fila {fila}: el CDS {bruto!r} no tiene la forma `inicio..fin` "
            f"(p. ej. `185..949`). Se aborta: de esa frontera cuelgan los tercios, la "
            f"región de cada ventana y la distancia de cada señal de polyA al extremo, "
            f"y leerla mal las corre TODAS sin dar ningún error."
        )
    inicio, fin = (int(p) for p in partes)
    if inicio < 1 or fin < inicio:
        raise ShmirDesignError(
            f"{source}, fila {fila}: el CDS {bruto!r} no es un intervalo 1-based "
            f"creciente. Se aborta."
        )
    return (inicio, fin)


def parse_manifest(text: str, *, source: str) -> Manifest:
    filas = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    if not filas:
        raise ShmirDesignError(
            f"{source}: el manifiesto no tiene ninguna fila; se aborta en vez de dar "
            f"por vacío el directorio de referencias."
        )
    cabecera = tuple(filas[0].split("\t"))
    # Se aceptan dos anchos: el completo y el corto, que es el de antes de que
    # existieran las columnas de procedencia. Un manifiesto corto NO es un error —los
    # ficheros que no son transcritos no tienen accession— pero deja esas columnas
    # vacias, y vacio significa "no registrado", nunca un valor por defecto.
    if cabecera not in (
        MANIFEST_COLUMNS, BEFORE_ANATOMY_COLUMNS, PREVIOUS_COLUMNS, LEGACY_COLUMNS,
    ):
        raise ShmirDesignError(
            f"{source}: la cabecera del manifiesto es {cabecera} y se esperaba "
            f"{MANIFEST_COLUMNS}; se aborta en vez de leer las columnas por posición."
        )
    ancho = len(cabecera)
    if len(filas) == 1:
        raise ShmirDesignError(
            f"{source}: el manifiesto solo tiene cabecera. Se aborta: un manifiesto "
            f"vacío no distingue 'no hay ficheros' de 'nadie los ha registrado'."
        )

    entradas: list[ManifestEntry] = []
    vistos: set[str] = set()
    for numero, fila in enumerate(filas[1:], start=2):
        campos = fila.split("\t")
        if len(campos) != ancho:
            raise ShmirDesignError(
                f"{source}, fila {numero}: tiene {len(campos)} campo(s) y la cabecera "
                f"declara {ancho}; se aborta en vez de saltarse la fila."
            )
        rellenos = [*(c.strip() for c in campos), *([""] * (len(MANIFEST_COLUMNS) - ancho))]
        (nombre, filtro, tamaño, md5, fecha, origen,
         accession, longitud, url, biblioteca,
         cds, md5_secuencia, md5_utr3) = rellenos
        if not nombre:
            raise ShmirDesignError(f"{source}, fila {numero}: sin nombre de fichero.")
        if nombre in vistos:
            raise ShmirDesignError(
                f"{source}, fila {numero}: {nombre} aparece dos veces; se aborta en vez "
                f"de quedarse con una de las dos líneas."
            )
        vistos.add(nombre)
        for etiqueta, valor in (
            ("md5", md5), ("md5_secuencia", md5_secuencia), ("md5_utr3", md5_utr3),
        ):
            if valor and not _MD5.match(valor):
                raise ShmirDesignError(
                    f"{source}, fila {numero}: {valor!r} en la columna {etiqueta} no es "
                    f"un md5 hexadecimal de 32 caracteres; se aborta."
                )
        talla: int | None = None
        if tamaño:
            try:
                talla = int(tamaño)
            except ValueError as exc:
                raise ShmirDesignError(
                    f"{source}, fila {numero}: el tamaño {tamaño!r} no es un número "
                    f"({exc}); se aborta."
                ) from exc
        entradas.append(
            ManifestEntry(
                name=nombre, filter_name=filtro, size=talla, md5=md5,
                date=fecha, origin=origen, accession=accession,
                length=_longitud(longitud, source=source, fila=numero), url=url,
                library=biblioteca,
                cds=_cds(cds, source=source, fila=numero),
                sequence_md5=md5_secuencia, utr3_md5=md5_utr3,
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
                f"el fichero está pero el manifiesto no trae su md5. Apunta "
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
            lineas.append("  Ningún filtro que dependa de un fichero puede correr.")
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


def roles_available(status: DirectoryStatus) -> tuple[Role, ...]:
    """Roles que se pueden conectar solos: fichero presente y comprobado.

    Solo `OK`. `SIN_REGISTRAR` no vale aunque el fichero este: sin md5 no hay version,
    y sin version no hay procedencia que poner en el informe — que es justo lo que este
    atajo tiene que preservar.
    """
    disponibles = []
    for resultado in status.results:
        if resultado.status is not EntryStatus.OK:
            continue
        rol = role_of(resultado.entry.name)
        if rol is not None:
            disponibles.append(rol)
    return tuple(disponibles)


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


# ─────────────────────── escribir en el manifiesto ───────────────────────
#
# Hasta ahora el manifiesto solo se LEIA: las lineas se escribian a mano, asi que subir
# un fichero de referencia obligaba a abrir una terminal y editar un `.tsv`. Eso es
# justo lo que rompe la autosuficiencia de la app — quien no conoce el arbol del
# repositorio no puede hacerlo, y quien lo conoce se equivoca al teclear un md5.
#
# Lo que NO cambia: el manifiesto sigue siendo texto y sigue versionado. Escribirlo
# desde la interfaz se ve en el `git diff` igual que escribirlo a mano.


def _campo(valor: object) -> str:
    """Un valor en su celda. Un tabulador dentro rompe el fichero, asi que ABORTA."""
    texto = "" if valor is None else str(valor)
    if "\t" in texto or "\n" in texto:
        raise ShmirDesignError(
            f"El valor {texto!r} lleva un tabulador o un salto de línea dentro, así que "
            f"partiria la fila en dos y el manifiesto pasaría a decir otra cosa. Se "
            f"aborta en vez de escribirlo."
        )
    return texto


def entry_row(entry: ManifestEntry) -> str:
    """La linea de una entrada, con TODAS las columnas en el orden de la cabecera.

    El numero no se escribe aqui: sale de `MANIFEST_COLUMNS`, y hay un test que exige
    que esta fila tenga tantos campos como columnas declara la cabecera. Una columna
    nueva que no se escribiera desplazaria en silencio a las de su derecha.
    """
    fila = "\t".join(
        _campo(v)
        for v in (
            entry.name, entry.filter_name, entry.size, entry.md5, entry.date,
            entry.origin, entry.accession, entry.length, entry.url, entry.library,
            _cds_texto(entry.cds), entry.sequence_md5, entry.utr3_md5,
        )
    )
    if len(fila.split("\t")) != len(MANIFEST_COLUMNS):
        raise ShmirDesignError(
            f"La fila de {entry.name!r} tiene {len(fila.split(chr(9)))} campo(s) y la "
            f"cabecera declara {len(MANIFEST_COLUMNS)}. Se aborta: escribirla así "
            f"correria los valores a la columna de al lado, que no da ningún error."
        )
    return fila


def _cds_texto(cds: tuple[int, int] | None) -> str:
    """`(185, 949)` → `185..949`. Vacio si no se registro, nunca `0..0`."""
    return "" if cds is None else f"{cds[0]}..{cds[1]}"


@dataclass(frozen=True)
class ManifestUpdate:
    """El texto nuevo, y que paso al escribirlo. Se devuelve para poder DECIRLO."""

    text: str
    #: `True` si la entrada ya estaba y se ha sustituido; `False` si se ha añadido.
    replaced: bool
    #: `True` si la cabecera era de las cortas y se ha ensanchado a las de hoy.
    widened: bool


def update_manifest_text(text: str, entry: ManifestEntry) -> ManifestUpdate:
    """Mete (o sustituye) una entrada en el texto del manifiesto.

    Funcion PURA: recibe texto y devuelve texto, para que la escritura en disco sea una
    sola linea sin logica. Los comentarios de cabecera se conservan tal cual — explican
    los dos checksums, y perderlos al subir un fichero seria borrar la unica advertencia
    que evita copiar un md5 en el sitio del otro.

    Una cabecera corta se ENSANCHA a las columnas de hoy rellenando las nuevas en vacio,
    que es la verdad: nadie las registro. Abortar seria dejar sin subir ficheros a quien
    tenga un manifiesto viejo, y esa persona es exactamente la que no puede editarlo.
    """
    # `parse_manifest` valida; si el manifiesto no se puede leer, no se escribe encima.
    parse_manifest(text, source="<manifiesto a actualizar>")

    lineas = text.splitlines()
    fila_cabecera = next(
        i for i, l in enumerate(lineas) if l.strip() and not l.startswith("#")
    )
    cabecera = tuple(lineas[fila_cabecera].split("\t"))
    ensanchada = cabecera != MANIFEST_COLUMNS
    if ensanchada:
        faltan = len(MANIFEST_COLUMNS) - len(cabecera)
        lineas[fila_cabecera] = "\t".join(MANIFEST_COLUMNS)
        for i in range(fila_cabecera + 1, len(lineas)):
            if lineas[i].strip() and not lineas[i].startswith("#"):
                lineas[i] = lineas[i] + "\t" * faltan

    nueva = entry_row(entry)
    sustituida = False
    for i in range(fila_cabecera + 1, len(lineas)):
        if not lineas[i].strip() or lineas[i].startswith("#"):
            continue
        if lineas[i].split("\t")[0].strip() == entry.name:
            lineas[i] = nueva
            sustituida = True
            break
    if not sustituida:
        lineas.append(nueva)
    return ManifestUpdate(
        text="\n".join(lineas) + "\n", replaced=sustituida, widened=ensanchada
    )


def register_entry(directory: Path | str, entry: ManifestEntry) -> ManifestUpdate:
    """Escribe la entrada en el manifiesto de ese directorio. No toca el fichero."""
    ruta = Path(directory) / MANIFEST_NAME
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer {ruta} para registrar {entry.name!r} ({exc}); sin "
            f"manifiesto el fichero no sería auditable y no se usa."
        ) from exc
    actualizado = update_manifest_text(texto, entry)
    try:
        ruta.write_text(actualizado.text, encoding="utf-8")
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo escribir {ruta} tras validar {entry.name!r} ({exc}); el fichero "
            f"queda SIN registrar y por tanto sin usar."
        ) from exc
    return actualizado
