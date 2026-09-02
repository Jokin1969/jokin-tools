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
