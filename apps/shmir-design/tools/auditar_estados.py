#!/usr/bin/env python3
"""Inventario de ESTADOS de la interfaz: en cuáles se ha pintado la página alguna vez.

**De dónde sale.** El inventario de banderas cubre los CLI. La página tiene su propia
superficie —y es donde vive lo que el usuario toca— y nada la inventariaba. El eje que
importa NO son los widgets: son las **combinaciones de estado que pintan cosas
distintas**. Un `st.toggle` más no añade un camino; una corrida guardada en un modal, sí.

**Los ejes**, y los tres se DERIVAN del código, no se transcriben:

- `corrida` — SIN_DISEÑAR · DISEÑADO_SIN_SELECCION · DISEÑADO_CON_SELECCION. Es la
  estructura de la página: el paso 5 sólo aparece después de diseñar, y la ficha y los
  modales necesitan un panel elegido.
- `fichero:<rol>` — CON y SIN, uno por rol de `species.required_files`. Con el fichero
  el frente corre; sin él sale NOT_RUN. Son dos pantallas distintas.
- `modal:<corrida>` — CON_CORRIDA y SIN_CORRIDA, uno por cada `corrida_*` de
  `store.RECORD_KINDS`. Con corrida guardada el modal enseña un veredicto; sin ella,
  un NOT_RUN visible. **Ésos son los caminos donde vivía `_modal_blast`.**

**DOS NIVELES DE COBERTURA, y la distinción es el punto entero:**

- `PINTADO` — algún test **renderiza la página** (`AppTest`) con ese estado. Es el único
  nivel que habría cazado un fallo de la página, porque es el único que la ejecuta.
- `CONSTRUIDO` — algún test monta ese estado en `presentation` o en `store`, pero no
  pinta. Vale para el núcleo y **no** para la juntura con la página.
- `NADA` — nadie.

Un `CONSTRUIDO` es exactamente la trampa del principio nº 17 en esta superficie: el
estado existe en un test, y el camino que lo pinta no lo recorre nadie.

**Lo que NO puede hacer**, declarado porque un análisis que se equivoca hacia el silencio
es peor que no tenerlo:

- reconoce un estado por sus MARCADORES en el fuente de los tests —el nombre del fichero
  del rol, la llamada que guarda la corrida— y no por ejecutarlos. Un marcador es prueba
  de que el estado se monta, no de que se compruebe nada útil con él;
- no enumera COMBINACIONES de ejes. El espacio es 3 × 2⁹ × 2⁴ y recorrerlo entero no es
  el objetivo: el objetivo es que ningún eje se quede sin pintar nunca;
- no dice que un estado esté roto. Dice que **nadie ha pintado la página en él**.

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TABLA = RAIZ / "data" / "estados.toml"

#: Los tres valores del eje de la corrida. Es estructura de la pagina, no dato: van
#: declarados aqui y el test comprueba que la tabla los cubre.
CORRIDA = ("SIN_DISEÑAR", "DISEÑADO_SIN_SELECCION", "DISEÑADO_CON_SELECCION")

#: Como se reconoce cada estado en el fuente de un test. La clave es el marcador; que
#: sea PINTADO o solo CONSTRUIDO lo decide el fichero donde aparece.
NIVELES = ("PINTADO", "CONSTRUIDO", "NADA")


@dataclass(frozen=True)
class Estado:
    eje: str
    valor: str
    #: Literales que, en el fuente de un test, delatan que ese estado se monta. Vacio
    #: cuando el estado no se reconoce por un marcador sino por un HECHO del repositorio.
    marcadores: tuple[str, ...]
    #: Para los estados de fichero: ¿es ESTE el estado en el que esta el deposito hoy?
    #: `None` = no aplica (el estado se reconoce por marcador).
    presente: bool | None = None

    @property
    def clave(self) -> str:
        return f"{self.eje}:{self.valor}"


def espacio_de_estados() -> list[Estado]:
    """Los ejes, DERIVADOS. Un rol nuevo o un modal nuevo aparecen solos."""
    sys.path.insert(0, str(RAIZ))
    from shmir_design.species import required_files, resolve  # noqa: PLC0415
    from shmir_design.store import RECORD_KINDS  # noqa: PLC0415

    estados: list[Estado] = [
        # Tambien es un HECHO y no un marcador: `AppTest` no puede subir un fichero, asi
        # que toda corrida de la pagina en un test se queda en SIN_DISEÑAR. Los otros dos
        # estados no los pinta nadie, y ese es el hallazgo — con ellos se van los cuatro
        # modales, que solo existen despues de diseñar.
        Estado("corrida", "SIN_DISEÑAR", (), presente=True),
        Estado("corrida", "DISEÑADO_SIN_SELECCION", (), presente=False),
        Estado("corrida", "DISEÑADO_CON_SELECCION", (), presente=False),
    ]
    # UN ROL, DOS ESTADOS. Y NO se reconocen por el nombre del fichero en el fuente: ese
    # nombre aparece IGUAL en un test que lo pone y en uno que comprueba que falta
    # («Subir transcriptoma_3utr.fa»). La primera version lo hacia asi y daba PINTADO a
    # cuatro ficheros que no estan en el repositorio.
    #
    # Se deriva de la PRESENCIA REAL: durante una corrida de `AppTest` el directorio de
    # referencia es el del paquete, asi que el estado de cada rol lo decide si su fichero
    # esta ahi o no. Eso no es un marcador, es el hecho.
    for fila in required_files(resolve("raton")):
        presentes = all(
            (RAIZ / "data" / "reference" / n).is_file() for n in fila.filenames
        )
        estados.append(Estado(f"fichero:{fila.role}", "CON", (), presente=presentes))
        estados.append(Estado(f"fichero:{fila.role}", "SIN", (), presente=not presentes))
    # UN MODAL, DOS ESTADOS. La corrida guardada se reconoce por la llamada que la
    # guarda, que es la unica forma de llegar a «este modal tiene veredicto».
    for tipo in sorted(k for k in RECORD_KINDS if k.startswith("corrida_")):
        corto = tipo.removeprefix("corrida_")
        # Los cuatro modales SOLO se pintan despues de diseñar, asi que arrastran el
        # mismo bloqueo: hoy no hay forma de que un test los pinte en ningun estado.
        estados.append(Estado(f"modal:{corto}", "CON_CORRIDA", (), presente=False))
        estados.append(Estado(f"modal:{corto}", "SIN_CORRIDA", (), presente=False))
    return estados


def _fuentes() -> dict[str, str]:
    return {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted((RAIZ / "tests").glob("*.py"))
    }


def _pinta(fuente: str) -> bool:
    """¿Ese test RENDERIZA la pagina? Es lo unico que ejecuta la juntura."""
    return "AppTest" in fuente


def cobertura() -> dict[str, str]:
    """El nivel de cada estado: PINTADO, CONSTRUIDO o NADA."""
    fuentes = _fuentes()
    salida: dict[str, str] = {}
    hay_apptest = any(_pinta(f) for f in fuentes.values())
    for estado in espacio_de_estados():
        if estado.presente is not None:
            # El estado del deposito durante una corrida de la pagina es un HECHO, no un
            # marcador: si el fichero esta, toda corrida de `AppTest` pinta ese rol en
            # CON; si no esta, en SIN. El otro estado no lo pinta nadie.
            salida[estado.clave] = "PINTADO" if (hay_apptest and estado.presente) else "NADA"
            continue
        # OJO: el nivel NO se compara con `max()` de cadenas. Se hizo asi en la primera
        # version y `max("NADA", "CONSTRUIDO")` da "NADA" —la N va despues de la C—, o
        # sea que TODO salia sin tocar. Un auditor que se equivoca hacia el silencio es
        # peor que no tenerlo, y este se equivocaba hacia el ruido: marcaba como no
        # cubierto lo que si estaba. Se ordena por indice declarado.
        nivel = "NADA"
        for fuente in fuentes.values():
            if not any(m in fuente for m in estado.marcadores):
                continue
            candidato = "PINTADO" if _pinta(fuente) else "CONSTRUIDO"
            if NIVELES.index(candidato) < NIVELES.index(nivel):
                nivel = candidato
            if nivel == "PINTADO":
                break
        salida[estado.clave] = nivel
    return salida


@dataclass
class Informe:
    filas: list[dict] = field(default_factory=list)
    sin_clasificar: list[str] = field(default_factory=list)
    muertos: list[str] = field(default_factory=list)
    techo: int = 0

    @property
    def sin_pintar(self) -> list[dict]:
        """Todos los que deciden algo y nadie ha pintado, BLOQUEADOS INCLUIDOS.

        Excluir los bloqueados dejaba el trinquete en CERO con diecinueve estados sin
        pintar, que es exactamente un informe que se lee como «pendiente» y no obliga a
        nada (principio nº 15). `bloqueado_por` documenta POR QUE no se puede hoy; no
        exime. El numero sólo baja abriendo el bloqueo o cubriendo el estado.
        """
        return [
            f for f in self.filas
            if f["nivel"] != "PINTADO" and f["destino"] == "CUBRIR"
        ]


def auditar() -> Informe:
    tabla = tomllib.loads(TABLA.read_text(encoding="utf-8"))
    declarado = {e["estado"]: e for e in tabla.get("estado", [])}
    niveles = cobertura()
    informe = Informe(techo=tabla.get("umbral", {}).get("sin_pintar", 0))

    vivos = set()
    for estado in espacio_de_estados():
        vivos.add(estado.clave)
        entrada = declarado.get(estado.clave)
        if entrada is None:
            informe.sin_clasificar.append(estado.clave)
            continue
        informe.filas.append(
            {
                "clave": estado.clave,
                "eje": estado.eje,
                "valor": estado.valor,
                "nivel": niveles[estado.clave],
                "destino": entrada["destino"],
                "que_pinta": entrada.get("que_pinta", ""),
                "bloqueado_por": entrada.get("bloqueado_por", ""),
            }
        )
    informe.muertos = sorted(set(declarado) - vivos)
    return informe


def _envolver(texto: str, ancho: int) -> list[str]:
    import textwrap  # noqa: PLC0415

    return textwrap.wrap(texto, ancho) or [""]


def render(informe: Informe) -> str:
    total = len(informe.filas)
    pintados = sum(1 for f in informe.filas if f["nivel"] == "PINTADO")
    construidos = sum(1 for f in informe.filas if f["nivel"] == "CONSTRUIDO")
    lineas = ["", "  Estados de la interfaz, por si algún test PINTA la página en ellos:"]
    lineas.append(
        f"    {pintados} de {total} pintados · {construidos} sólo construidos · "
        f"{total - pintados - construidos} sin tocar"
    )
    faltan = informe.sin_pintar
    if faltan:
        lineas.append(f"  ⚠  {len(faltan):3}  deciden qué se pinta y NADIE pinta en ellos:")
        for fila in faltan:
            if not fila["bloqueado_por"]:
                lineas.append(f"       · {fila['clave']} — {fila['que_pinta']}")
        # Los bloqueados van agrupados POR MOTIVO: son diecinueve entradas y dos causas,
        # asi que repetir la causa en cada linea la volveria invisible. Y lo que hay que
        # leer es la CAUSA: abrirla desbloquea todas las suyas de una vez.
        causas: dict[str, list[str]] = {}
        for fila in faltan:
            if fila["bloqueado_por"]:
                causas.setdefault(fila["bloqueado_por"], []).append(fila["clave"])
        for causa, claves in causas.items():
            lineas.append(f"     {len(claves):3}  bloqueados por lo mismo:")
            lineas.extend(f"           {l}" for l in _envolver(causa, 78))
            lineas.append(f"           {', '.join(claves)}")
    for destino in ("CONSTANTE", "BORRAR"):
        cuantos = [f for f in informe.filas if f["destino"] == destino]
        if cuantos:
            lineas.append(f"     {len(cuantos):3}  {destino}")
            for fila in cuantos:
                lineas.append(f"       · {fila['clave']} — {fila['que_pinta']}")
    if informe.sin_clasificar:
        lineas.append("")
        lineas.append("  SIN CLASIFICAR: " + ", ".join(informe.sin_clasificar))
    lineas.append("")
    lineas.append(
        "  CONSTRUIDO no basta: monta el estado en el núcleo y NO ejecuta la página, que"
    )
    lineas.append(
        "  es la juntura donde vive lo que el usuario toca. Sólo PINTADO cuenta."
    )
    lineas.append(
        f"  El techo declarado son {informe.techo} y hay {len(faltan)}. Sólo puede bajar."
    )
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    print(render(auditar()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
