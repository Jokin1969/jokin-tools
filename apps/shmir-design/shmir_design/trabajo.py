"""Donde vive el directorio de referencia CUANDO SE TRABAJA. No donde se versiona.

Son dos sitios y hasta ahora eran uno. `data/reference/` es a la vez:

  - el **origen versionado**: los fixtures que si entran en git (los dos transcritos, las
    corridas de RepeatMasker, el manifiesto) y que llegan con el codigo;
  - el **directorio de trabajo**: donde el panel de la interfaz escribe lo que se sube y
    donde `manifest.tsv` se actualiza con su md5.

En local coinciden y esta bien. En un servidor no pueden coincidir: el sistema de
ficheros de la imagen es **efimero**, asi que cada redespliegue se llevaria por delante
todo lo subido —y la linea del manifiesto con ello— sin dar ningun error; simplemente un
frente volveria a salir NOT_RUN. Y `manifest.tsv` esta versionado, asi que escribirlo
dentro de la imagen deja el arbol de trabajo sucio contra el siguiente despliegue.

Asi que el de trabajo **se declara** (`SHMIR_REFERENCE_DIR`) y por defecto es el del
paquete: en local no cambia nada, que es la condicion para que esto sea aceptable.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .errors import ShmirDesignError
from .reference import PACKAGE_REFERENCE_DIR

#: La variable que declara el directorio de trabajo. Vacia = el del paquete.
ENV_VAR = "SHMIR_REFERENCE_DIR"

#: Lo mismo para los PROYECTOS. Y por el mismo motivo, que aqui pesa mas todavia: el
#: registro de un veredicto tiene que sobrevivir a la app que lo escribio, y dentro de la
#: imagen de un despliegue se pierde en el siguiente redespliegue.
PROJECT_ENV_VAR = "SHMIR_PROJECT_DIR"

#: Por que existe. Va a la interfaz cuando el de trabajo no es el del paquete, para que
#: quien sube un fichero sepa DONDE ha ido a parar.
#: LA FRASE DICE LO QUE PASA, no lo que se evitó. La versión anterior explicaba el
#: contrafactual —«dentro de la imagen desapareceria en el siguiente redespliegue»— y en
#: pantalla se leía como que lo subido se borra, que es lo contrario de lo que hace la
#: app. Este texto sólo se pinta cuando el directorio de trabajo ESTÁ declarado, así que
#: puede afirmarlo sin condicionales; la razón va detrás, en pasado, donde no se
#: confunde con el veredicto. Ver el mismo arreglo en `biblioteca.SURVIVES`.
WHY_A_WORKING_DIR = (
    "Lo que subas SOBREVIVE a los redespliegues: este directorio está fuera del código, "
    "en el volumen. Se hizo así porque el sistema de ficheros de un despliegue es "
    "efimero y, dentro de la imagen, lo subido se habría perdido en el siguiente "
    "redespliegue dejando un frente que vuelve a salir NOT_RUN. Lo versionado se copia "
    "aquí la primera vez y no se vuelve a pisar."
)


def reference_dir(env=None) -> Path:
    """El directorio de TRABAJO. Sin declarar, el del paquete."""
    entorno = os.environ if env is None else env
    declarado = str(entorno.get(ENV_VAR, "") or "").strip()
    if not declarado:
        return PACKAGE_REFERENCE_DIR
    ruta = Path(declarado)
    if not ruta.is_absolute():
        raise ShmirDesignError(
            f"{ENV_VAR}={declarado!r} no es una ruta absoluta. Se aborta: un directorio "
            f"de trabajo relativo depende de desde donde se arranque el proceso, así que "
            f"los ficheros acabarian en un sitio distinto segun quien lo lance y la "
            f"mitad de los frentes saldrian NOT_RUN sin motivo visible."
        )
    return ruta


def projects_dir(env=None) -> Path:
    """Donde viven los proyectos. Sin declarar, junto al paquete.

    Misma indireccion que `reference_dir`, y el motivo aqui es MAS fuerte: lo que se
    guarda es el registro de lo que se decidio, y ese registro tiene que sobrevivir a la
    app que lo escribio. Dentro de la imagen de un despliegue no sobrevive a nada.
    """
    entorno = os.environ if env is None else env
    declarado = str(entorno.get(PROJECT_ENV_VAR, "") or "").strip()
    if not declarado:
        return PACKAGE_REFERENCE_DIR.parent / "proyectos"
    ruta = Path(declarado)
    if not ruta.is_absolute():
        raise ShmirDesignError(
            f"{PROJECT_ENV_VAR}={declarado!r} no es una ruta absoluta. Se aborta: un "
            f"directorio de proyectos relativo depende de desde donde se arranque el "
            f"proceso, así que el log de un proyecto acabaria en un sitio distinto segun "
            f"quien lo lance — y entonces no sobrevive a nada, que es justo lo contrario "
            f"de para lo que existe."
        )
    return ruta


def is_declared(env=None) -> bool:
    """¿Se ha sacado el directorio de trabajo fuera del paquete?"""
    return reference_dir(env) != PACKAGE_REFERENCE_DIR


@dataclass(frozen=True)
class SeedReport:
    """Que se copio y que se respeto. Se devuelve para poder DECIRLO en el arranque."""

    directory: str
    copied: tuple[str, ...]
    kept: tuple[str, ...]

    def render(self) -> str:
        lineas = [f"Directorio de referencia de trabajo: {self.directory}"]
        if self.copied:
            lineas.append(f"  copiados desde lo versionado: {len(self.copied)}")
        if self.kept:
            lineas.append(
                f"  respetados (ya estaban, y mandan): {', '.join(sorted(self.kept))}"
            )
        if not self.copied and not self.kept:
            lineas.append("  sin cambios.")
        return "\n".join(lineas)


def seed_reference_dir(target: Path | str, *, source: Path | str | None = None) -> SeedReport:
    """Copia lo versionado al directorio de trabajo. **No pisa nada.**

    Que no pise es la parte importante y va en los dos sentidos:

      - un fichero subido por el usuario manda sobre la copia que trae la imagen. Al
        reves, un redespliegue borraria el fichero bueno y lo dejaria en NOT_RUN;
      - el `manifest.tsv` de trabajo lleva los md5 de lo subido, asi que pisarlo con el
        versionado es perder la procedencia — que es justo lo que el manifiesto existe
        para conservar.
    """
    origen = Path(PACKAGE_REFERENCE_DIR if source is None else source)
    destino = Path(target)
    if not origen.is_dir():
        raise ShmirDesignError(
            f"No hay de donde sembrar el directorio de referencia: {origen} no existe. "
            f"Se aborta en vez de arrancar con un directorio vacío, que se leeria como "
            f"«no hay ningún fichero» y no como «la instalación está rota»."
        )
    try:
        destino.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo crear el directorio de referencia de trabajo {destino} ({exc}); "
            f"sin el no se puede subir ningún fichero por la interfaz."
        ) from exc

    copiados: list[str] = []
    respetados: list[str] = []
    for fichero in sorted(origen.iterdir()):
        if not fichero.is_file():
            continue
        llegada = destino / fichero.name
        if llegada.exists():
            respetados.append(fichero.name)
            continue
        try:
            shutil.copy2(fichero, llegada)
        except OSError as exc:
            raise ShmirDesignError(
                f"No se pudo copiar {fichero.name} a {destino} ({exc}); se aborta la "
                f"siembra a medias en vez de dejar un directorio incompleto que parezca "
                f"completo."
            ) from exc
        copiados.append(fichero.name)
    return SeedReport(
        directory=str(destino), copied=tuple(copiados), kept=tuple(respetados)
    )
