"""Auditoria de un fichero de scores externo contra el 3'UTR de referencia.

Existe porque este analisis se hizo tres veces a mano y a mano se cometen justo los
errores que persigue: en una pasada salieron las ventanas `269-291` (23 nt) y `222-242`
(21 nt) para guias de 22 nt, y en otra la misma ventana como `270-291`. Coordenadas
transcritas en vez de derivadas — la errata del desplazamiento de 3 nt otra vez.

Aqui **ningun intervalo se escribe a mano**: `Span.of()` lo deriva de la secuencia que
describe y `Span.check()` aborta si la longitud no cuadra. Un intervalo que no cuadre
no se imprime con una nota al pie: para el proceso.

Lo que mira, por fila:

- longitud, y la tabla de longitudes del fichero entero;
- si la guia mapea sobre el 3'UTR, y donde;
- si no mapea, si se restaura con UNA insercion o UNA delecion, y en que carrera cae;
- si la fila es prefijo o sufijo de otra fila del mismo fichero (la misma prediccion
  con un caracter menos);
- si lleva un sitio de restriccion que NO esta en el 3'UTR — señal de que se ha colado
  contexto de clonaje o de interfaz donde deberia haber guia.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType

from .errors import ShmirDesignError
from .hard_filters import reverse_complement_rna

#: Los siete que se pidieron mirar. Un sitio presente en la guia y ausente del 3'UTR no
#: puede venir de la diana: o es casualidad, o es contexto de clonaje colado.
RESTRICTION_SITES = MappingProxyType(
    {
        "XbaI": "TCTAGA",
        "EcoRI": "GAATTC",
        "XhoI": "CTCGAG",
        "NheI": "GCTAGC",
        "SacI": "GAGCTC",
        "MluI": "ACGCGT",
        "AgeI": "ACCGGT",
    }
)


@dataclass(frozen=True)
class Span:
    """Un intervalo 1-based e inclusivo que SIEMPRE se deriva de su secuencia."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ShmirDesignError(
                f"Intervalo del reves: {self.start}-{self.end}. Se aborta en vez de "
                f"imprimir unas coordenadas que no describen nada."
            )

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    @classmethod
    def of(cls, start: int, sequence: str) -> Span:
        """El final se calcula; no se teclea."""
        return cls(start, start + len(sequence) - 1)

    def check(self, sequence: str, *, name: str) -> None:
        if self.length != len(sequence):
            raise ShmirDesignError(
                f"El intervalo {self} de {name} abarca {self.length} nt y la secuencia "
                f"mide {len(sequence)}. Se aborta: unas coordenadas que no cuadran con "
                f"su secuencia son exactamente el fallo que hay que cazar, no una nota "
                f"al pie."
            )

    def __str__(self) -> str:
        return f"{self.start}-{self.end}"


def _rc(sequence: str) -> str:
    return reverse_complement_rna(sequence).replace("U", "T")


def _find(guide: str, utr3: str) -> tuple[int, str, bool] | None:
    """Donde cae la guia sobre el 3'UTR, probando sin su posicion 1 de convenio."""
    for descartada, candidata in ((False, guide), (True, guide[1:])):
        if not candidata:
            continue
        diana = _rc(candidata)
        posicion = utr3.find(diana)
        if posicion >= 0:
            return posicion + 1, diana, descartada
    return None


@dataclass(frozen=True)
class GuideAudit:
    guide: str
    maps: bool
    span: Span | None = None
    mapped_sequence: str = ""
    operation: str = ""
    restored: str = ""
    restored_span: Span | None = None
    #: La diana que de verdad se emparejo. Mide lo que mide `restored_span`, que puede
    #: ser un nt MENOS que la guia restaurada: si el match salio de `guia[1:]`, la
    #: posicion 1 es la T de convenio y no forma parte de la ventana.
    restored_sequence: str = ""
    #: True cuando el match necesito descartar la posicion 1 de convenio.
    dropped_convention_base: bool = False
    ambiguity: Span | None = None
    run_base: str = ""
    run_length: int = 0
    prefix_of: str = ""
    sites: tuple[str, ...] = ()
    foreign_prefix: str = ""
    native_suffix: str = ""

    @property
    def length(self) -> int:
        return len(self.guide)


@dataclass(frozen=True)
class ScoreAudit:
    entries: tuple[GuideAudit, ...]
    lengths: dict[int, int]
    sites_absent_from_reference: tuple[tuple[str, tuple[str, ...]], ...]

    def format_text(self) -> str:
        lineas = [
            "── Auditoria del fichero de scores ──",
            f"  filas: {len(self.entries)}",
            "  longitudes: "
            + ", ".join(f"{n} nt × {c}" for n, c in sorted(self.lengths.items())),
        ]
        if len(self.lengths) > 1:
            lineas.append(
                "  La longitud NO es fija, así que de ella sola no se puede concluir "
                "donde se"
            )
            lineas.append(
                "  perdio una base: un 21-mero puede ser una predicción o una "
                "predicción mutilada."
            )
        sin_mapear = [e for e in self.entries if not e.maps]
        lineas.append(f"  no mapean sobre el 3'UTR: {len(sin_mapear)}")
        for entrada in sin_mapear:
            detalle = (
                f"restaura con una {entrada.operation} en {entrada.restored_span}"
                if entrada.operation
                else "NO se restaura con una sola inserción ni delecion"
            )
            lineas.append(f"    · {entrada.guide} ({entrada.length} nt) — {detalle}")
            if entrada.ambiguity is not None:
                lineas.append(
                    f"        zona ambigua {entrada.ambiguity}, carrera "
                    f"{entrada.run_base * entrada.run_length} "
                    f"({entrada.run_length} nt)"
                )
            if entrada.foreign_prefix:
                lineas.append(
                    f"        prefijo ajeno {entrada.foreign_prefix} + "
                    f"{len(entrada.native_suffix)} nt reales "
                    f"({entrada.native_suffix})"
                )
        duplicadas = [e for e in self.entries if e.prefix_of]
        if duplicadas:
            lineas.append("  filas que son prefijo o sufijo de otra fila:")
            for entrada in duplicadas:
                lineas.append(f"    · {entrada.guide} ⊂ {entrada.prefix_of}")
        if self.sites_absent_from_reference:
            lineas.append("  sitios de restricción presentes en la guía y AUSENTES del 3'UTR:")
            for nombre, guias in self.sites_absent_from_reference:
                lineas.append(f"    · {nombre} ({RESTRICTION_SITES[nombre]}) en:")
                lineas.extend(f"        {g}" for g in guias)
            lineas.append(
                "    Una sola fila no es un patron. Si aparecen mas, hay que mirar si "
                "la fuente"
            )
            lineas.append(
                "    añade contexto de clonaje que estamos leyendo como guía."
            )
        else:
            lineas.append("  ningún sitio de restricción ajeno al 3'UTR.")
        return "\n".join(lineas)


def _restaura(guide: str, utr3: str) -> tuple[str, str, Span, str, bool] | None:
    """Una insercion o una delecion que devuelva un match exacto. Nunca dos."""
    for posicion in range(len(guide) + 1):
        for base in "ACGT":
            candidata = guide[:posicion] + base + guide[posicion:]
            hallazgo = _find(candidata, utr3)
            if hallazgo:
                inicio, diana, descartada = hallazgo
                return "insercion", candidata, Span.of(inicio, diana), diana, descartada
    for posicion in range(len(guide)):
        candidata = guide[:posicion] + guide[posicion + 1 :]
        hallazgo = _find(candidata, utr3)
        if hallazgo:
            inicio, diana, descartada = hallazgo
            return "delecion", candidata, Span.of(inicio, diana), diana, descartada
    return None


def _zona_ambigua(implicada: str, referencia: str, ventana: Span) -> Span | None:
    """Donde cae la base que sobra o falta, derivado del prefijo y sufijo comunes."""
    comun = 0
    while comun < min(len(implicada), len(referencia)) and implicada[comun] == referencia[comun]:
        comun += 1
    sufijo = 0
    while (
        sufijo < min(len(implicada), len(referencia)) - comun
        and implicada[-1 - sufijo] == referencia[-1 - sufijo]
    ):
        sufijo += 1
    inicio, fin = ventana.start + comun, ventana.end - sufijo
    if fin < inicio:
        return None
    return Span(inicio, fin)


def _carrera(utr3: str, posicion: int) -> tuple[str, int]:
    """La carrera de bases iguales que contiene esa posicion 1-based."""
    indice = posicion - 1
    base = utr3[indice]
    inicio = indice
    while inicio > 0 and utr3[inicio - 1] == base:
        inicio -= 1
    fin = indice
    while fin + 1 < len(utr3) and utr3[fin + 1] == base:
        fin += 1
    return base, fin - inicio + 1


def audit_scores(
    scores: list[tuple[str, float]], utr3: str
) -> ScoreAudit:
    """Audita cada guia del fichero contra el 3'UTR. No corrige nada: informa."""
    if not scores:
        raise ShmirDesignError(
            "El fichero de scores no trae ninguna fila; no hay nada que auditar."
        )
    guias = [g.upper().replace("U", "T") for g, _ in scores]
    entradas: list[GuideAudit] = []
    for guia in guias:
        contenida = next(
            (
                otra
                for otra in guias
                if otra != guia
                and len(otra) > len(guia)
                and (otra.startswith(guia) or otra.endswith(guia))
            ),
            "",
        )
        sitios = tuple(n for n, m in RESTRICTION_SITES.items() if m in guia)
        hallazgo = _find(guia, utr3)
        if hallazgo:
            inicio, diana, descartada = hallazgo
            ventana = Span.of(inicio, diana)
            ventana.check(diana, name=f"la guía {guia}")
            entradas.append(
                GuideAudit(
                    guide=guia, maps=True, span=ventana, mapped_sequence=diana,
                    prefix_of=contenida, sites=sitios,
                    dropped_convention_base=descartada,
                )
            )
            continue

        restaurada = _restaura(guia, utr3)
        if restaurada is None:
            ajeno, nativo = _parte_ajena(guia, utr3)
            entradas.append(
                GuideAudit(
                    guide=guia, maps=False, prefix_of=contenida, sites=sitios,
                    foreign_prefix=ajeno, native_suffix=nativo,
                )
            )
            continue

        operacion, candidata, ventana, diana, descartada = restaurada
        ventana.check(diana, name=f"la guía restaurada {candidata}")
        referencia = utr3[ventana.start - 1 : ventana.end]
        implicada = _rc(guia) if len(_rc(guia)) == len(referencia) - 1 else _rc(guia[1:])
        ambigua = _zona_ambigua(implicada, referencia, ventana)
        base, carrera = ("", 0)
        if ambigua is not None:
            base, carrera = _carrera(utr3, ambigua.start)
        entradas.append(
            GuideAudit(
                guide=guia, maps=False, operation=operacion, restored=candidata,
                restored_span=ventana, restored_sequence=diana,
                dropped_convention_base=descartada, ambiguity=ambigua, run_base=base,
                run_length=carrera, prefix_of=contenida, sites=sitios,
            )
        )

    ajenos: list[tuple[str, tuple[str, ...]]] = []
    for nombre, motivo in RESTRICTION_SITES.items():
        if motivo in utr3:
            continue
        con_sitio = tuple(e.guide for e in entradas if nombre in e.sites)
        if con_sitio:
            ajenos.append((nombre, con_sitio))

    return ScoreAudit(
        entries=tuple(entradas),
        lengths=dict(Counter(len(g) for g in guias)),
        sites_absent_from_reference=tuple(ajenos),
    )


def _parte_ajena(guide: str, utr3: str) -> tuple[str, str]:
    """El trozo mas largo de la DERECHA de la guia que si esta en el 3'UTR.

    La guia es el complementario reverso de la diana, asi que un trozo pegado por la
    izquierda de la guia sale por la DERECHA de la diana. Confundir los dos espacios es
    lo que produce descripciones al reves.
    """
    for largo in range(len(guide), 7, -1):
        cola = guide[len(guide) - largo :]
        if _rc(cola) in utr3:
            return guide[: len(guide) - largo], cola
    return "", ""


# ═════════════ EL GUARDIA DEL TRUNCAMIENTO EN LAS TABLAS QUE SE EXPORTAN ═════════════
#
# **De donde sale.** Se reporto un heptamero de SEIS caracteres en la columna
# `heptamero` del CSV descargable. Los tres productores del heptamero se midieron y los
# tres dan siete, asi que el caso concreto NO se reprodujo y no se le asigna causa. Lo
# que si se decidio es que la clase de fallo tenga guardia, porque es de las que no dan
# ningun error: un heptamero truncado a seis SIGUE SIENDO una seed valida y DISTINTA
# —la familia del «Alu 0 %»—, asi que el numero que sale al lado es correcto para otra
# pregunta.
#
# **Que comprueba.** Que ninguna celda de una columna de SECUENCIA mida menos de lo que
# su fuente declara. La columna no se declara por su nombre: se DERIVA del contenido —una
# columna cuyas celdas no vacias son todas alfabeto de acidos nucleicos y miden al menos
# `MIN_SEQUENCE`—, asi que una columna de secuencia NUEVA entra en el guardia sola.
#
# **Y por eso hay que declarar la longitud esperada**: una columna de secuencia sin
# longitud declarada ABORTA. La alternativa —ignorarla— convierte al guardia en una
# lista de las columnas de las que alguien se acordo, que es como no tenerlo.

#: El alfabeto. `U` entra porque las tablas de ARN existen; las minusculas se normalizan.
SEQUENCE_ALPHABET = frozenset("ACGTU")

#: Por debajo de esto, una celda no es una secuencia: `AT`, `GC` y `CG` son etiquetas.
#: Seis es el minimo con sentido biologico aqui —es el nucleo de seed— y ademas es
#: justo la longitud que se reporto, asi que el guardia lo cubre.
MIN_SEQUENCE = 6

WHY_TRUNCATION_IS_SILENT = (
    "Un heptámero truncado a seis sigue siendo una seed válida y DISTINTA, así que el "
    "conteo que sale a su lado es correcto para otra pregunta y no da ningún error. Lo "
    "mismo con una guía a la que le falte la última base: la tabla se lee igual y lo que "
    "describe es otra cosa."
)


def _es_secuencia(valor) -> bool:
    texto = str(valor).strip().upper()
    return len(texto) >= MIN_SEQUENCE and set(texto) <= SEQUENCE_ALPHABET


def sequence_columns(rows) -> tuple[str, ...]:
    """Las columnas de una tabla que llevan SECUENCIA. Se derivan del contenido.

    Una columna cuenta si TODAS sus celdas no vacias son secuencia: con «alguna» bastaria
    un md5 que por azar solo tuviera a/c/g/t para meter una columna de checksums.
    """
    if not rows:
        return ()
    columnas = []
    for clave in rows[0]:
        valores = [f[clave] for f in rows if str(f.get(clave, "")).strip()]
        if valores and all(_es_secuencia(v) for v in valores):
            columnas.append(clave)
    return tuple(columnas)


def check_no_truncation(rows, *, expected: dict[str, int], table: str) -> None:
    """Aborta si una columna de secuencia no mide lo que su fuente declara.

    `expected` es longitud POR COLUMNA, y quien llama la saca del objeto que produjo la
    tabla —la ventana de la corrida, la longitud de la guia—, nunca de un numero escrito:
    escribir un 7 aqui seria afirmar que la ventana es 2-8, que es justo lo que el
    guardia tiene que comprobar y no suponer (principio nº 13).
    """
    from .errors import ShmirDesignError

    columnas = sequence_columns(rows)
    sin_declarar = [c for c in columnas if c not in expected]
    if sin_declarar:
        raise ShmirDesignError(
            f"{table}: la(s) columna(s) {', '.join(sin_declarar)} llevan secuencia y no "
            f"declaran su longitud esperada, así que nada impide que salgan truncadas. "
            f"{WHY_TRUNCATION_IS_SILENT} Se declara de dónde sale su longitud, no un "
            f"número escrito."
        )
    for clave, largo in expected.items():
        for fila in rows:
            valor = str(fila.get(clave, "")).strip()
            if not valor:
                continue
            if len(valor) != largo:
                raise ShmirDesignError(
                    f"{table}, columna {clave}: {valor!r} mide {len(valor)} y su fuente "
                    f"declara {largo}. {WHY_TRUNCATION_IS_SILENT}"
                )
