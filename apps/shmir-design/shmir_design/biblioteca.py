"""Biblioteca por ranura: los ficheros del paso 2 que se guardan para la próxima vez.

**El problema que cierra.** Los cuatro huecos del paso 2 —mRNA y GenBank de la especie
del diseño y de la segunda— se suben de cero en cada sesión. Repetir la misma prueba
obliga a ir a buscar los mismos cuatro ficheros otra vez, y ese trasiego es donde se
cuela el fichero equivocado: el `.gb` de la especie que no era, la versión vieja del
FASTA. La errata nº 5 empezó exactamente así.

**Dónde vive y por qué.** En el VOLUMEN (`SHMIR_REFERENCE_DIR/biblioteca/`), NO en la
imagen. El sistema de ficheros del contenedor es efímero: dentro de él, todo lo guardado
desaparecería en el siguiente redespliegue y el único síntoma sería una biblioteca vacía
sin ninguna explicación. Misma razón que el directorio de referencia y que los proyectos.

**Qué NO hace.** No sustituye al depósito de `deposito.py`, que es otra cosa: aquel
registra los ficheros que CIERRAN FRENTES —con su rol, su validación y su línea en el
manifiesto versionado— y éste sólo guarda entradas del paso 2 para no volver a
buscarlas. Aquí no hay roles, no hay manifiesto y no se cierra ningún frente.

**Las reglas que sí se mantienen:**

  - el **md5 se calcula de los bytes** y nunca se declara. Es además el identificador:
    guardar dos veces el mismo fichero no duplica nada, aunque venga con otro nombre;
  - **se vuelve a comprobar AL LEER.** El volumen es un directorio de verdad y alguien
    puede tocarlo; un fichero que ya no es el que se guardó no se devuelve como si lo
    fuera, se aborta;
  - **el nombre lo pone el navegador**, así que pasa por `presentation.upload_path`;
  - **la extensión tiene que ser la de la ranura.** Guardar el `.gb` en el hueco del
    FASTA es justo el error que esto viene a evitar, no uno que pueda introducir;
  - **el índice es TEXTO** (`indice.tsv`), legible y `grep`-able como el manifiesto. Un
    índice binario obliga a la app para saber qué hay guardado.

Python 3.11+, sólo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .errors import ShmirDesignError


@dataclass(frozen=True)
class Slot:
    """Una ranura del paso 2: qué hueco es y qué admite."""

    key: str
    label: str
    extensions: tuple[str, ...]


#: Las CUATRO del paso 2, en el orden en que salen en la página. Las extensiones son las
#: mismas que declara cada `st.file_uploader`: si divergen, la biblioteca aceptaría algo
#: que el hueco rechaza y el usuario tendría un fichero guardado que no puede usar.
SLOTS = MappingProxyType(
    {
        "mrna_diseno": Slot(
            "mrna_diseno", "mRNA — especie del diseño", ("fa", "fasta", "txt")
        ),
        "genbank_diseno": Slot(
            "genbank_diseno",
            "GenBank de la especie del diseño",
            ("gb", "gbk", "genbank"),
        ),
        "mrna_segunda": Slot(
            "mrna_segunda", "mRNA — segunda especie", ("fa", "fasta", "txt")
        ),
        "genbank_segunda": Slot(
            "genbank_segunda",
            "GenBank de la segunda especie",
            ("gb", "gbk", "genbank"),
        ),
    }
)

WHY_THE_VOLUME = (
    "La biblioteca vive en el volumen y no en la imagen. Dentro de la imagen, todo lo "
    "guardado desaparecería en el siguiente redespliegue y el único síntoma sería una "
    "biblioteca vacía sin ninguna explicación."
)

_INDICE = "indice.tsv"
_CABECERA = ("id", "nombre", "guardado", "bytes")


@dataclass(frozen=True)
class Entrada:
    """Un fichero guardado. `id` es su md5, que es también su nombre en disco."""

    id: str
    name: str
    date: str
    size: int

    def describe(self) -> str:
        return f"{self.name}  ({self.size} bytes, guardado el {self.date}, md5 {self.id[:8]}…)"


def base_por_defecto() -> Path:
    """`SHMIR_REFERENCE_DIR/biblioteca`. Ver `WHY_THE_VOLUME`.

    Sale de `trabajo.reference_dir()`, que es el que LEE LA VARIABLE, y no de
    `reference.reference_dirs()`, que devuelve los directorios del paquete y del
    repositorio. La primera version usaba el segundo y la biblioteca habria acabado
    dentro de la imagen: en local no se nota nada y en produccion se pierde todo lo
    guardado en el siguiente redespliegue, con una biblioteca vacia como unico sintoma.
    Es EXACTAMENTE el fallo contra el que avisa el docstring de este modulo.
    """
    from .trabajo import reference_dir  # noqa: PLC0415

    return reference_dir() / "biblioteca"


def _slot(clave: str) -> Slot:
    ranura = SLOTS.get(str(clave))
    if ranura is None:
        raise ShmirDesignError(
            f"No hay ninguna ranura {clave!r} en la biblioteca; las que hay son "
            f"{', '.join(SLOTS)}. Se aborta en vez de guardar en un sitio inventado."
        )
    return ranura


def _dir(clave: str, base: Path | str | None) -> Path:
    raiz = Path(base) if base is not None else base_por_defecto()
    return raiz / _slot(clave).key


def ruta_de(clave: str, ident: str, *, base: Path | str | None = None) -> Path:
    """Dónde vive un fichero guardado. El nombre en disco es su md5: no colisiona."""
    return _dir(clave, base) / f"{ident}.bin"


def _leer_indice(directorio: Path) -> list[Entrada]:
    indice = directorio / _INDICE
    if not indice.is_file():
        return []
    entradas: list[Entrada] = []
    for numero, linea in enumerate(
        indice.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not linea.strip() or linea.startswith("#"):
            continue
        campos = linea.split("\t")
        if len(campos) != len(_CABECERA):
            raise ShmirDesignError(
                f"{indice}: la línea {numero} tiene {len(campos)} campos y la cabecera "
                f"declara {len(_CABECERA)} ({', '.join(_CABECERA)}). Se aborta en vez de "
                f"adivinar cuál falta."
            )
        ident, nombre, fecha, tamano = campos
        try:
            entradas.append(Entrada(ident, nombre, fecha, int(tamano)))
        except ValueError as exc:
            raise ShmirDesignError(
                f"{indice}: la línea {numero} trae {tamano!r} donde debería ir el "
                f"tamaño en bytes ({exc}); se aborta."
            ) from exc
    return entradas


def _escribir_indice(directorio: Path, entradas) -> None:
    lineas = ["#" + "\t".join(_CABECERA)]
    lineas.extend(
        "\t".join((e.id, e.name, e.date, str(e.size))) for e in entradas
    )
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / _INDICE).write_text("\n".join(lineas) + "\n", encoding="utf-8")


def listar(clave: str, *, base: Path | str | None = None) -> tuple[Entrada, ...]:
    """Lo guardado en esa ranura, más reciente primero. Vacía si no hay nada."""
    directorio = _dir(clave, base)
    if not directorio.is_dir():
        return ()
    return tuple(sorted(_leer_indice(directorio), key=lambda e: e.date, reverse=True))


def guardar(
    clave: str,
    *,
    nombre: str,
    data: bytes,
    date: str,
    base: Path | str | None = None,
) -> Entrada:
    """Guarda un fichero en la ranura y devuelve su entrada. Repetir no duplica."""
    ranura = _slot(clave)
    if not data:
        raise ShmirDesignError(
            f"El fichero que se quiere guardar en «{ranura.label}» está vacío; se "
            f"aborta en vez de dejar una entrada que no sirve para nada."
        )

    from .presentation import upload_path  # noqa: PLC0415

    directorio = _dir(clave, base)
    directorio.mkdir(parents=True, exist_ok=True)
    limpio = upload_path(directorio, nombre).name
    extension = limpio.rsplit(".", 1)[-1].lower() if "." in limpio else ""
    if extension not in ranura.extensions:
        raise ShmirDesignError(
            f"«{ranura.label}» admite {', '.join('.' + e for e in ranura.extensions)} y "
            f"el fichero es .{extension or '(sin extensión)'}. Se aborta: guardar un "
            f".gb en el hueco del FASTA es justo el error que esto evita."
        )

    ident = hashlib.md5(data, usedforsecurity=False).hexdigest()
    entrada = Entrada(ident, limpio, str(date), len(data))
    ruta_de(clave, ident, base=base).write_bytes(data)
    otras = [e for e in _leer_indice(directorio) if e.id != ident]
    _escribir_indice(directorio, [*otras, entrada])
    return entrada


def leer(clave: str, ident: str, *, base: Path | str | None = None) -> bytes:
    """Los bytes guardados, COMPROBANDO el md5 otra vez. Ver el docstring del módulo."""
    directorio = _dir(clave, base)
    entrada = next((e for e in _leer_indice(directorio) if e.id == ident), None)
    if entrada is None:
        raise ShmirDesignError(
            f"En «{_slot(clave).label}» no hay ningún fichero guardado con id {ident}; "
            f"hay {len(_leer_indice(directorio))}. Se aborta."
        )
    ruta = ruta_de(clave, ident, base=base)
    if not ruta.is_file():
        raise ShmirDesignError(
            f"{ruta} está en el índice y NO está en disco. La biblioteca vive en el "
            f"volumen: si esto pasa, o el volumen no se montó o alguien borró el "
            f"fichero a mano. Se aborta en vez de seguir sin él."
        )
    datos = ruta.read_bytes()
    real = hashlib.md5(datos, usedforsecurity=False).hexdigest()
    if real != ident:
        raise ShmirDesignError(
            f"{ruta}: el md5 del fichero es {real} y el índice dice {ident}. Ya NO es el "
            f"que se guardó, así que no se devuelve como si lo fuera."
        )
    return datos


def borrar(clave: str, ident: str, *, base: Path | str | None = None) -> Entrada:
    """Borra una entrada del índice y del disco. Devuelve la que se fue."""
    directorio = _dir(clave, base)
    entradas = _leer_indice(directorio)
    entrada = next((e for e in entradas if e.id == ident), None)
    if entrada is None:
        raise ShmirDesignError(
            f"En «{_slot(clave).label}» no hay ningún fichero guardado con id {ident}, "
            f"así que no hay nada que borrar. Se aborta en vez de callar."
        )
    ruta = ruta_de(clave, ident, base=base)
    if ruta.is_file():
        ruta.unlink()
    _escribir_indice(directorio, [e for e in entradas if e.id != ident])
    return entrada
