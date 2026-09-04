"""El panel de referencia como GESTOR: una tabla, y acciones sobre cada fichero.

**El problema que cierra.** Había dos sitios —una lista de conectados y otra de lo que
falta— y hacía falta mirar dos veces para saber en qué punto estabas. Y sobre lo que ya
estaba no se podía hacer nada: ni verlo, ni reemplazarlo, ni borrarlo, ni recuperarlo. El
fichero entraba y dejaba de ser tuyo.

**El criterio:** entrar al panel y saber exactamente qué hay, qué falta y qué se puede
hacer con cada cosa, sin leer documentación ni abrir una terminal.

Una fila por fichero, PRESENTES Y AUSENTES JUNTOS, ordenadas por frente. Sobre las
presentes cuatro acciones —ver, reemplazar, borrar, descargar—; sobre las ausentes,
subir, con su ficha de obtención al lado.

**REEMPLAZAR es la que de verdad importa.** Cambiar `mature.fa` invalida las corridas de
seed hechas con el anterior, y dejar que convivan en silencio es PEOR que no poder
reemplazarlo: el veredicto viejo se queda en pantalla, con la misma pinta de siempre,
calculado contra un fichero que ya no está. Por eso el plan se enseña ANTES de confirmar,
con el md5 viejo, el nuevo, y qué corridas dejan de valer.

**Y DESCARGAR es lo que hace que el depósito sea tuyo y no de la app**: recuperar el
fichero tal como se subió, sin volver a UCSC ni a miRBase.

Python 3.11+, sólo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from .errors import ShmirDesignError
from .identidad import file_fingerprint
from .presencia import hay_fichero

#: QUE CORRIDAS INVALIDA CAMBIAR CADA FICHERO. Declarado en UN SOLO SITIO y con test de
#: que estan TODOS los roles y de que cada corrida existe en `store.RECORD_KINDS`
#: (principio nº 7). Un rol que faltara aqui NO seria «no invalida nada»: seria un rol sin
#: decidir, y se leeria como lo primero.
#:
#: La tupla vacia es una DECISION, no un hueco: ese fichero alimenta un filtro que se
#: recalcula entero en cada corrida, asi que no hay ninguna corrida guardada que dependa
#: de el.
ROLE_INVALIDATES = MappingProxyType(
    {
        "mirbase": ("corrida_seed",),
        "abundancia": ("corrida_seed",),
        "transcriptoma": ("corrida_offtarget",),
        "expresion": ("corrida_offtarget",),
        "refseq": ("corrida_blast",),
        "transgen": ("corrida_blast",),
        # Se recalculan enteros en cada corrida: no hay corrida guardada que dependa.
        "rmsk": (),
        "apa": (),
        # Tampoco: la promocion por medida se recalcula al tilar, no queda guardada en
        # ninguna corrida del log. Lo que SI cambia al reemplazarla es el panel entero
        # —y eso se ve al volver a diseñar, no en una corrida vieja.
        "polyadb": (),
        # Tampoco: los contextos se contrastan al EMITIR el modulo, en cada corrida. Lo
        # que si cambia al reemplazarlo es si el modulo se puede emitir, y eso se ve al
        # volver a pedirlo — no en una corrida guardada.
        "plasmido_andamio": (),
    }
)

WHY_THE_PLAN_IS_SHOWN_FIRST = (
    "Reemplazar un fichero invalida las corridas hechas con el anterior. Dejar que "
    "convivan en silencio es peor que no poder reemplazarlo: el veredicto viejo se queda "
    "en pantalla, con la misma pinta, calculado contra un fichero que ya no está."
)

WHY_DOWNLOAD = (
    "Descargar devuelve el fichero tal como se subió. Es lo que evita volver a UCSC o a "
    "miRBase cuando hace falta en otro sitio, y lo que hace que el depósito sea tuyo y "
    "no de la app."
)

#: Cuantas lineas se enseñan por defecto. Con un `.out` o un `.tsv`, diez dicen mas que
#: cualquier metadato.
PREVIEW_LINES = 10


def _ruta(directory, name: str) -> Path:
    """La ruta dentro del directorio. El nombre no puede salirse."""
    from .presentation import upload_path  # noqa: PLC0415

    return upload_path(Path(directory), name)


def _md5(data: bytes) -> str:
    return file_fingerprint(data)


@dataclass(frozen=True)
class Preview:
    """Las primeras lineas de un fichero, para reconocerlo de un vistazo."""

    name: str
    text: str
    total_lines: int
    shown: int
    is_text: bool

    @property
    def truncated(self) -> bool:
        return self.shown < self.total_lines


def preview(name: str, *, directory, lines: int = PREVIEW_LINES) -> Preview:
    """Las primeras `lines` lineas. Un binario se DICE, no se pinta como texto."""
    ruta = _ruta(directory, name)
    if not ruta.is_file():
        raise ShmirDesignError(
            f"{ruta} no está, así que no hay nada que ver. Se aborta en vez de enseñar "
            f"una vista vacía, que se leería como «el fichero está y no dice nada»."
        )
    crudo = ruta.read_bytes()
    try:
        texto = crudo.decode("utf-8")
    except UnicodeDecodeError:
        # rule2-ok: NO se traga nada. Que un fichero no sea UTF-8 es un HECHO sobre el
        # fichero, no un fallo del paso: la vista lo DICE y sigue enseñando el md5 y el
        # tamaño, que es con lo que se reconoce. Tragarselo seria enseñar una vista
        # vacia, que se leeria como «esta y no dice nada».
        return Preview(
            name=name,
            text=(
                f"Fichero binario ({len(crudo)} bytes): no se puede enseñar como texto. "
                f"El md5 y el tamaño siguen valiendo para reconocerlo."
            ),
            total_lines=0, shown=0, is_text=False,
        )
    todas = texto.splitlines()
    primeras = todas[:lines]
    return Preview(
        name=name, text="\n".join(primeras),
        total_lines=len(todas), shown=len(primeras), is_text=True,
    )


def download(name: str, *, directory) -> bytes:
    """Los bytes TAL COMO SE SUBIERON. Ver `WHY_DOWNLOAD`."""
    ruta = _ruta(directory, name)
    if not ruta.is_file():
        raise ShmirDesignError(
            f"{ruta} no está, así que no hay nada que descargar. Se aborta."
        )
    return ruta.read_bytes()


@dataclass(frozen=True)
class ReplacePlan:
    """Lo que va a pasar si se confirma. Se enseña ANTES. Ver `WHY_THE_PLAN_IS_SHOWN_FIRST`."""

    name: str
    old_md5: str
    new_md5: str
    old_bytes: int
    new_bytes: int
    invalidates: tuple[str, ...] = ()
    fronts: tuple[str, ...] = ()

    @property
    def same_file(self) -> bool:
        return self.old_md5 == self.new_md5

    def describe(self) -> str:
        if self.same_file:
            return (
                f"{self.name}: el fichero nuevo es EL MISMO (md5 {self.old_md5}). No "
                f"cambia nada y no se invalida ninguna corrida."
            )
        lineas = [
            f"{self.name}: md5 {self.old_md5} ({self.old_bytes} bytes) → "
            f"{self.new_md5} ({self.new_bytes} bytes).",
        ]
        if self.invalidates:
            lineas.append(
                f"INVALIDA las corridas guardadas de tipo "
                f"{', '.join(self.invalidates)}: se hicieron con el fichero anterior y "
                f"su veredicto ya no vale. {WHY_THE_PLAN_IS_SHOWN_FIRST}"
            )
        else:
            lineas.append(
                "No hay ninguna corrida guardada que dependa de este fichero: alimenta "
                "un filtro que se recalcula entero en cada corrida."
            )
        if self.fronts:
            lineas.append(f"Frentes afectados: {', '.join(self.fronts)}.")
        return " ".join(lineas)


def _rol_de(name: str):
    from .manifest import role_of  # noqa: PLC0415

    return role_of(name)


def _frentes_de(name: str, species: str | None) -> tuple[str, ...]:
    if species is None:
        return ()
    from .species import required_files, resolve  # noqa: PLC0415

    for fila in required_files(resolve(species)):
        if name in fila.filenames:
            return tuple(fila.fronts)
    return ()


def plan_replace(
    name: str, *, directory, payload: bytes, species: str | None = None
) -> ReplacePlan:
    """Qué cambia y qué deja de valer. NO escribe nada: es el plan."""
    ruta = _ruta(directory, name)
    if not ruta.is_file():
        raise ShmirDesignError(
            f"{ruta} no está, así que no hay nada que reemplazar: lo que toca es SUBIRLO. "
            f"Se aborta en vez de tratar una subida como un reemplazo, que se registraría "
            f"con una procedencia que no le corresponde."
        )
    if not payload:
        raise ShmirDesignError(
            f"El fichero nuevo para {name} está vacío; se aborta en vez de dejar el "
            f"frente cerrado con nada dentro."
        )
    viejo = ruta.read_bytes()
    rol = _rol_de(name)
    nuevo_md5 = _md5(payload)
    mismo = _md5(viejo) == nuevo_md5
    return ReplacePlan(
        name=name,
        old_md5=_md5(viejo), new_md5=nuevo_md5,
        old_bytes=len(viejo), new_bytes=len(payload),
        invalidates=() if mismo else tuple(ROLE_INVALIDATES.get(rol.role if rol else "", ())),
        fronts=() if mismo else _frentes_de(name, species),
    )


@dataclass(frozen=True)
class DeletePlan:
    """Qué frente vuelve a NOT_RUN si se borra."""

    name: str
    md5: str
    fronts: tuple[str, ...] = field(default_factory=tuple)
    invalidates: tuple[str, ...] = ()

    def describe(self) -> str:
        frentes = ", ".join(self.fronts) if self.fronts else "ninguno declarado"
        texto = (
            f"Borrar {self.name} (md5 {self.md5}) devuelve a NOT_RUN: {frentes}. "
            f"NOT_RUN no es PASS: los candidatos volverán a salir INCOMPLETE."
        )
        if self.invalidates:
            texto += (
                f" Y las corridas guardadas de tipo {', '.join(self.invalidates)} quedan "
                f"sin el fichero contra el que se hicieron."
            )
        return texto


def plan_delete(name: str, *, directory, species: str | None = None) -> DeletePlan:
    """Lo que se pierde. NO borra: es el plan."""
    ruta = _ruta(directory, name)
    if not ruta.is_file():
        raise ShmirDesignError(f"{ruta} no está, así que no hay nada que borrar.")
    rol = _rol_de(name)
    return DeletePlan(
        name=name,
        md5=_md5(ruta.read_bytes()),
        fronts=_frentes_de(name, species),
        invalidates=tuple(ROLE_INVALIDATES.get(rol.role if rol else "", ())),
    )


def delete(name: str, *, directory) -> str:
    """Borra el fichero y devuelve su md5, para que quede en el registro de quien llame."""
    ruta = _ruta(directory, name)
    if not ruta.is_file():
        raise ShmirDesignError(f"{ruta} no está, así que no hay nada que borrar.")
    md5 = _md5(ruta.read_bytes())
    ruta.unlink()
    return md5


#: Las acciones de cada estado. Declaradas aqui y no en la pagina: si la pagina decide
#: que botones pinta, acaba habiendo un estado con acciones que no le tocan.
ACTIONS = MappingProxyType(
    {
        "presente": ("ver", "reemplazar", "borrar", "descargar"),
        "ausente": ("subir",),
    }
)


def _procedencia_pedida(role: str) -> list[dict[str, str]]:
    """Las casillas de procedencia de la TABLA que este rol exige, ya con su texto.

    Vacia en casi todos: la mayoria de los ficheros no salen de ninguna tabla y ahi la
    columna vacia del manifiesto es la VERDAD, no un hueco.
    """
    from .deposito import (  # noqa: PLC0415
        PROVENANCE_FIELDS, PROVENANCE_LABELS, PROVENANCE_REQUIRED,
    )

    if role not in PROVENANCE_REQUIRED:
        return []
    return [
        {
            "clave": campo,
            "etiqueta": PROVENANCE_LABELS[campo][0],
            "ayuda": PROVENANCE_LABELS[campo][1],
        }
        for campo in PROVENANCE_FIELDS
    ]


def manager_rows(species: str, *, directory) -> list[dict]:
    """Una fila por fichero, PRESENTES Y AUSENTES juntos, ordenadas por frente."""
    from .manifest import load_manifest  # noqa: PLC0415
    from .presentation import obtencion_rows  # noqa: PLC0415
    from .species import required_files, resolve  # noqa: PLC0415

    raiz = Path(directory)
    especie = resolve(species)

    registrado: dict[str, object] = {}
    manifiesto = raiz / "manifest.tsv"
    if manifiesto.is_file():
        try:
            for entrada in load_manifest(manifiesto).entries:
                registrado[entrada.name] = entrada
        except ShmirDesignError as exc:
            # rule2-ok: un manifiesto ilegible NO se traga. La tabla sale igual —los
            # ficheros estan y se ven— pero cada fila lo dice en vez de enseñar los
            # metadatos vacios como si el fichero no los tuviera.
            registrado["__error__"] = str(exc)

    aviso = registrado.pop("__error__", "")
    filas: list[dict] = []
    for fila in required_files(especie):
        ficha = obtencion_rows(fila.ficha, species=species)
        for nombre in fila.filenames:
            ruta = raiz / nombre
            # Presencia = hay algo dentro. Un fichero de 0 bytes saldria PRESENTE con
            # sus cuatro acciones y la de «Ver» enseñaria nada. Errata nº 15.
            presente = hay_fichero(ruta)
            estado = "presente" if presente else "ausente"
            entrada = registrado.get(nombre)
            filas.append(
                {
                    "nombre": nombre,
                    "role": fila.role,
                    "frente": fila.fronts[0] if fila.fronts else "",
                    "frentes": list(fila.fronts),
                    "estado": estado,
                    "obligatorio": fila.required,
                    "hermano": nombre != fila.filename,
                    "que_desbloquea": fila.what,
                    "extensiones": list(fila.extensions),
                    # Que casillas de PROCEDENCIA hay que rellenar para que este fichero
                    # pueda entrar. Sale de `deposito.PROVENANCE_REQUIRED`, que es quien
                    # las exige: la pagina las pinta y no decide cuales son (regla 6).
                    "procedencia": _procedencia_pedida(fila.role),
                    "acciones": list(ACTIONS[estado]),
                    "ficha": ficha,
                    "md5": _md5(ruta.read_bytes()) if presente else "",
                    "bytes": ruta.stat().st_size if presente else 0,
                    "fecha": getattr(entrada, "date", "") or "",
                    "origen": getattr(entrada, "origin", "") or "",
                    "invalida": list(ROLE_INVALIDATES.get(fila.role, ())),
                    "aviso_manifiesto": aviso,
                }
            )
    return sorted(filas, key=lambda f: (f["frente"], f["nombre"]))


# ═══════════════ «DESCARGAR TODO»: la copia de seguridad, en un botón ═══════════════
#
# **El motivo, con las palabras con que se pidio**: *el volumen es la unica copia de todo
# lo que pone un frente en verde, y con el se iria la procedencia. Que la copia de
# seguridad sea un boton, no una tarea de disciplina.*
#
# Y es exacto. Los ficheros que cierran frentes —`mature.fa`, el casete, el plasmido del
# andamio, el transcriptoma— NO van en git: no entran en un repositorio, asi que viven
# solo en el volumen. Con ellos se iria el `manifest.tsv` de TRABAJO, que es donde estan
# su md5, su fecha, su origen y su ensamblaje — o sea la PROCEDENCIA, que es lo unico que
# hace auditable un veredicto dentro de un año.
#
# Habia un boton por FICHERO y el manifiesto no tenia ninguno. Eso no es una copia de
# seguridad: es la posibilidad de hacerla, que es otra cosa.
#
# **Va con un LEEME dentro**, y no es adorno: un zip sin nada que lo explique es un monton
# de ficheros dentro de un año. Lleva de donde salio cada cosa, el inventario con md5 —para
# poder comprobarlo SIN la app— y como se restaura, que importa porque el directorio de
# trabajo se declara por variable de entorno.
#
# **Y si un fichero no se puede leer, ABORTA.** Media copia que parece completa es peor
# que ninguna, y aqui nadie va a mirar el zip hasta el dia que haga falta. Es el mismo
# criterio de `trabajo.seed_reference_dir`.

#: Como se llaman los dos directorios dentro del zip. En el zip y en el LEEME salen los
#: mismos nombres: si divergieran, las instrucciones de restauracion apuntarian a una
#: carpeta que no existe.
BACKUP_DIRS = MappingProxyType(
    {"referencia": "reference", "proyectos": "proyectos", "biblioteca": "biblioteca"}
)

WHY_A_BACKUP_BUTTON = (
    "El volumen es la única copia de todo lo que pone un frente en verde, y con él se "
    "iría la procedencia: el manifiesto de trabajo es donde están el md5, la fecha, el "
    "origen y el ensamblaje de cada fichero que subiste. Esta copia lo mete todo en un "
    "zip para que hacerla sea un botón y no una tarea de disciplina."
)


def _bytes_de(ruta: Path, *, que: str) -> bytes:
    """Los bytes, o ABORTA. Nunca se omite un fichero de la copia en silencio."""
    try:
        return ruta.read_bytes()
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer {que} ({ruta}): {exc}. Se ABORTA la copia entera en vez de "
            f"dejar fuera un fichero sin decirlo: media copia que parece completa es "
            f"peor que ninguna, y nadie mira un zip de seguridad hasta el día que lo "
            f"necesita."
        ) from exc


def _ficheros_del_deposito(directory: Path) -> list[Path]:
    """Todo lo que hay en la raíz del depósito, el manifiesto incluido.

    NO se filtra por rol: un fichero que esté ahí y no reconozcamos entra igual. Lo que
    esto copia es el VOLUMEN, no la lista de lo que la app sabe usar — y lo segundo es
    justo lo que dejaría fuera algo puesto a mano.
    """
    return sorted(p for p in directory.iterdir() if p.is_file())


def _proyectos_de(base: Path) -> list[Path]:
    from .store import PROJECT_FILE  # noqa: PLC0415

    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / PROJECT_FILE).is_file())


def backup_inventory(directory, *, projects=None) -> dict[str, object]:
    """Qué llevaría la copia y cuánto pesa. NO construye el zip.

    Se pinta en cada repintado de la página, así que aquí no se comprime nada: con el
    transcriptoma dentro —84 MB— montar el zip para enseñar un número costaría un minuto
    por clic. Es la lección de la errata nº 59.
    """
    from .store import LOG_FILE, PROJECT_FILE  # noqa: PLC0415

    raiz = Path(directory)
    if not raiz.is_dir():
        raise ShmirDesignError(
            f"No hay depósito en {raiz}, así que no hay nada que copiar. Se aborta en "
            f"vez de entregar un zip vacío, que se leería como «no había nada»."
        )
    ficheros = _ficheros_del_deposito(raiz)
    total = sum(p.stat().st_size for p in ficheros)

    proyectos = _proyectos_de(Path(projects)) if projects is not None else []
    for directorio in proyectos:
        for nombre in (PROJECT_FILE, LOG_FILE):
            ruta = directorio / nombre
            if ruta.is_file():
                total += ruta.stat().st_size

    biblioteca = raiz / "biblioteca"
    guardados = (
        sorted(p for p in biblioteca.rglob("*") if p.is_file())
        if biblioteca.is_dir() else []
    )
    total += sum(p.stat().st_size for p in guardados)
    return {
        "ficheros": len(ficheros),
        "proyectos": len(proyectos),
        "guardados": len(guardados),
        "bytes": total,
        "nombres": tuple(p.name for p in ficheros),
        "slugs": tuple(p.name for p in proyectos),
    }


#: POR QUE UN ZIP TIENE QUE SALIR IGUAL DOS VECES, y no es manía de reproducibilidad.
#:
#: `zipfile` estampa LA HORA ACTUAL en cada entrada, así que los mismos ficheros dan
#: bytes distintos en cada construcción. Y Streamlit deriva el id de un fichero
#: descargable **de su contenido** (`MemoryMediaFileStorage.load_and_get_id` →
#: `_calculate_file_id(file_data, ...)`), así que bytes distintos son un id distinto.
#:
#: Pulsar un `download_button` provoca un rerun; al terminar, `clear_session_refs` +
#: `remove_orphaned_files` borran el id que ya no referencia nadie — **el que el navegador
#: está descargando en ese momento**. El síntoma es exactamente el que se reportó: la
#: descarga empieza y no llega, «un error de internet cuando no lo hay». Y cuanto más
#: grande el zip, más probable, porque hay más rato para que se lo lleven por delante.
WHY_A_ZIP_MUST_NOT_CHANGE = (
    "Un zip que se reconstruye con bytes distintos cada vez desaparece del servidor a "
    "media descarga: Streamlit identifica lo descargable por su CONTENIDO y borra lo que "
    "deja de estar referenciado en el repintado siguiente. Con la fecha fija, el mismo "
    "contenido da el mismo identificador y no hay nada que quede huérfano."
)


def _fecha_del_zip(date: str) -> tuple[int, int, int, int, int, int]:
    """La marca de tiempo de las entradas, DERIVADA de la fecha declarada.

    Se deriva y no se pone a cero: dos copias de días distintos tienen que ser dos
    ficheros distintos —si no, no hay forma de saber cuál es cuál— y la fecha ya viaja
    dentro del zip y en su nombre. Lo que NO puede entrar es la hora del reloj, que
    cambia entre un repintado y el siguiente sin que nadie haya tocado nada.

    Un `date` que no sea `AAAA-MM-DD` no se adivina: se aborta. El zip lleva la fecha
    dentro y en el nombre, y una inventada aquí las haría discrepar en silencio.
    """
    try:
        anio, mes, dia = (int(x) for x in str(date).split("-"))
    except ValueError as exc:
        raise ShmirDesignError(
            f"La fecha del zip tiene que ser AAAA-MM-DD y llegó {date!r}: se aborta en "
            f"vez de poner una cualquiera. {WHY_A_ZIP_MUST_NOT_CHANGE}"
        ) from exc
    # `zipfile` no admite años anteriores a 1980 (el formato no los representa).
    return (max(anio, 1980), mes, dia, 0, 0, 0)


def deterministic_zip(entries, *, date: str, order=None) -> bytes:
    """Un zip que sale IGUAL con el mismo contenido. Ver `WHY_A_ZIP_MUST_NOT_CHANGE`.

    `entries` es `{nombre: texto o bytes}`. Las entradas van ordenadas por nombre —el
    orden también es contenido— y todas con la misma marca de tiempo.

    `order` es para los formatos donde el orden LO EXIGE la especificación y no lo elige
    quien empaqueta: un `.docx` es un zip OPC y `[Content_Types].xml` tiene que ir el
    primero. Se pasa explícito en vez de confiar en que el alfabético coincida — hoy
    coincide por casualidad (`[` va antes que `_` y que `w` en ASCII) y eso no es una
    garantía, es una coincidencia que se rompe al renombrar cualquier pieza.

    **Es el ÚNICO constructor de zips del proyecto**, y por eso lo usan la copia de
    seguridad, la descarga de resultados y el `.docx` del informe: un zip que cambia de
    bytes sin cambiar de contenido rompe todo lo que lo identifique por su contenido
    (errata nº 76).
    """
    import zipfile  # noqa: PLC0415

    marca = _fecha_del_zip(date)
    if order is not None:
        faltan = set(entries) ^ set(order)
        if faltan:
            raise ShmirDesignError(
                f"El orden declarado del zip no cuadra con lo que se le da: sobran o "
                f"faltan {sorted(faltan)}. Se aborta en vez de escribir un zip con "
                f"entradas de menos o en un orden que no es el declarado."
            )
        pares = [(nombre, entries[nombre]) for nombre in order]
    else:
        pares = sorted(entries.items())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in pares:
            info = zipfile.ZipInfo(nombre, date_time=marca)
            info.compress_type = zipfile.ZIP_DEFLATED
            # Permisos fijos también: el modo va dentro del zip, así que heredarlo del
            # fichero de disco volvería a hacer que el resultado dependa del entorno.
            info.external_attr = 0o644 << 16
            zf.writestr(
                info,
                contenido.encode("utf-8") if isinstance(contenido, str) else contenido,
            )
    return buffer.getvalue()


def export_all(directory, *, projects=None, date: str) -> bytes:
    """El depósito entero, los proyectos y la biblioteca en un zip. Con su LEEME.

    `date` es OBLIGATORIA y va dentro: una copia de seguridad sin fecha no se distingue
    de otra, y lo primero que hace falta saber de un zip encontrado dentro de un año es
    de cuándo es.
    """
    import zipfile  # noqa: PLC0415

    from .store import LOG_FILE, PROJECT_FILE  # noqa: PLC0415

    if not str(date).strip():
        raise ShmirDesignError(
            "Una copia de seguridad necesita fecha: sin ella no se distingue de otra, y "
            "es lo primero que hace falta saber de un zip encontrado dentro de un año. "
            "Se aborta."
        )
    raiz = Path(directory)
    inventario = backup_inventory(raiz, projects=projects)

    lineas = [
        f"Copia de seguridad de shmir-design — {date}",
        "",
        WHY_A_BACKUP_BUTTON,
        "",
        "DE DÓNDE SALIÓ",
        f"  ficheros de referencia: {raiz}",
    ]
    base_proyectos = Path(projects) if projects is not None else None
    lineas.append(
        f"  proyectos:              {base_proyectos}"
        if base_proyectos is not None
        else "  proyectos:              no se pidieron"
    )
    lineas += [
        "",
        "CÓMO SE RESTAURA",
        f"  El contenido de {BACKUP_DIRS['referencia']}/ va al directorio que declare la "
        f"variable SHMIR_REFERENCE_DIR",
        f"  (en un despliegue, dentro del volumen). El de "
        f"{BACKUP_DIRS['proyectos']}/ va al de SHMIR_PROJECT_DIR.",
        f"  {BACKUP_DIRS['biblioteca']}/ va DENTRO del de referencia, en un "
        f"subdirectorio con ese mismo nombre.",
        "  Los ficheros se copian tal cual: el manifiesto lleva su md5 y la app lo "
        "vuelve a comprobar al cargarlos.",
        "",
        "LO QUE ESTA COPIA NO ES",
        "  Es una FOTO del día que se descargó: no se actualiza sola. Lo que se suba "
        "después no está aquí.",
        "  Y no lleva el código: eso está en git. Lleva lo que git NO puede llevar.",
        "",
        f"INVENTARIO — {inventario['ficheros']} fichero(s) de referencia, "
        f"{inventario['proyectos']} proyecto(s), {inventario['guardados']} guardado(s) "
        f"de la biblioteca",
        "",
    ]

    # SE RECOGEN Y LUEGO SE EMPAQUETAN, con `deterministic_zip`: si esto escribiera
    # el zip por su cuenta volvería a haber dos constructores y sólo uno con la
    # fecha fija. Ver `WHY_A_ZIP_MUST_NOT_CHANGE`.
    entradas: dict[str, bytes] = {}
    for ruta in _ficheros_del_deposito(raiz):
        crudo = _bytes_de(ruta, que=f"el fichero de referencia {ruta.name!r}")
        entradas[f"{BACKUP_DIRS['referencia']}/{ruta.name}"] = crudo
        lineas.append(
            f"  {BACKUP_DIRS['referencia']}/{ruta.name:<38} {len(crudo):>12} B  "
            f"md5 {file_fingerprint(crudo)}"
        )

    biblioteca = raiz / "biblioteca"
    if biblioteca.is_dir():
        for ruta in sorted(p for p in biblioteca.rglob("*") if p.is_file()):
            crudo = _bytes_de(ruta, que=f"el guardado {ruta.name!r} de la biblioteca")
            relativa = ruta.relative_to(biblioteca).as_posix()
            entradas[f"{BACKUP_DIRS['biblioteca']}/{relativa}"] = crudo
            lineas.append(
                f"  {BACKUP_DIRS['biblioteca']}/{relativa:<38} {len(crudo):>12} B  "
                f"md5 {file_fingerprint(crudo)}"
            )

    proyectos = _proyectos_de(base_proyectos) if base_proyectos else []
    if not proyectos:
        lineas.append(
            "  (no había ningún proyecto: el primer día es lo normal, no un fallo)"
        )
    for directorio in proyectos:
        for nombre in (PROJECT_FILE, LOG_FILE):
            ruta = directorio / nombre
            if not ruta.is_file():
                raise ShmirDesignError(
                    f"Al proyecto {directorio.name!r} le falta {nombre}, así que su "
                    f"registro no se puede leer entero. Se aborta la copia en vez de "
                    f"guardar media: un log sin saber sobre qué secuencia es no dice "
                    f"nada, y una entrada sin su log tampoco."
                )
            crudo = _bytes_de(ruta, que=f"{nombre} del proyecto {directorio.name!r}")
            destino = f"{BACKUP_DIRS['proyectos']}/{directorio.name}/{nombre}"
            entradas[destino] = crudo
            lineas.append(
                f"  {destino:<50} {len(crudo):>12} B  md5 {file_fingerprint(crudo)}"
            )

    entradas["LEEME.txt"] = "\n".join(lineas) + "\n"
    return deterministic_zip(entradas, date=date)
