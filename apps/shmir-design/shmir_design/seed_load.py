"""Carga de off-targets mediados por seed (bloque 1b).

Es una pregunta DISTINTA de la colision con un miARN endogeno (`mirna.py`). Alli se
pregunta si la guia comparte seed con un miARN que la neurona expresa. Aqui, dando por
bueno que no colisiona con nadie, se pregunta cuantos transcritos quedaran reprimidos
por complementariedad de seed sola.

Por que hace falta: el sitio complementario de un 7-mero aparece por azar cada ~16 kb.
Hay miles, y **ningun alineador los devuelve**: el filtro de especificidad del bloque 12
compara la guia entera, asi que estos sitios no aparecen en su salida. Un veredicto de
especificidad limpio no dice nada sobre esto.

El resultado NO es un veredicto. Es un numero comparativo entre candidatos, para
desempatar en la tabla comparativa — que es justo lo que falta, porque la asimetria
predice seleccion de hebra y no tiene nada que decir sobre carga de seed.

Geometria de los tres tipos, sobre la DIANA (leidos 5'→3'):

  7mer-m8   complemento inverso de las posiciones 2-8 de la guia
  7mer-A1   complemento inverso de las posiciones 2-7, seguido de una A
  8mer      complemento inverso de las posiciones 2-8, seguido de una A

Los tipos son excluyentes: un 8mer se cuenta como 8mer y no ademas como 7mer-m8.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ShmirDesignError
from .filters import FilterState

SEED_START = 2
SEED_END = 8
SITE_TYPES = ("8mer", "7mer-m8", "7mer-A1")

#: Cada cuantos nt aparece por azar el sitio complementario de un 7-mero.
AZAR_CADA_NT = 4 ** 7 // 1000 * 1000  # 16 kb, redondeado a la baja

_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def _revcomp(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)[::-1]


def site_patterns(guide: str) -> dict[str, str]:
    """Los tres patrones que hay que buscar en los 3'UTR, en coordenadas de diana."""
    limpia = "".join(str(guide).split()).upper().replace("U", "T")
    if len(limpia) < SEED_END:
        raise ValueError(
            f"La guia mide {len(limpia)} nt y la seed son las posiciones {SEED_START}-"
            f"{SEED_END}; se aborta en vez de buscar media seed."
        )
    seed_2_8 = limpia[SEED_START - 1 : SEED_END]
    seed_2_7 = limpia[SEED_START - 1 : SEED_END - 1]
    if set(seed_2_8) - set("ACGT"):
        raise ValueError(
            f"La seed {seed_2_8} tiene bases que no son A/C/G/T: no se puede construir "
            f"su sitio complementario. Se aborta."
        )
    m8 = _revcomp(seed_2_8)
    return {"7mer-m8": m8, "7mer-A1": _revcomp(seed_2_7) + "A", "8mer": m8 + "A"}


@dataclass(frozen=True)
class Utr3Set:
    """3'UTR del transcriptoma, con procedencia. Sin procedencia no vale."""

    records: dict[str, str]
    source: str
    version: str
    checksum: str

    def __post_init__(self) -> None:
        for campo, valor in (
            ("source", self.source),
            ("version", self.version),
            ("checksum", self.checksum),
        ):
            if not valor or not str(valor).strip():
                raise ValueError(
                    f"El conjunto de 3'UTR necesita {campo}: sin procedencia el numero "
                    f"no es auditable. Se aborta."
                )
        if not self.records:
            raise ShmirDesignError(
                f"{self.source}: el conjunto de 3'UTR esta vacio; se aborta en vez de "
                f"informar de una carga de seed de cero que pareceria una buena noticia."
            )

    @property
    def provenance(self) -> str:
        total = sum(len(s) for s in self.records.values())
        return (
            f"{self.source}, version {self.version}, checksum {self.checksum}, "
            f"{len(self.records)} 3'UTR ({total} nt)"
        )


def _count_in(sequence: str, patterns: dict[str, str]) -> dict[str, int]:
    """Cuenta los tres tipos sin contar dos veces el mismo sitio.

    Se ocupa la HUELLA entera de cada sitio contado, no solo su primera base: un 8mer
    contiene siempre un 7mer-A1 desplazado una posicion, y contar los dos convertiria
    un sitio en dos. Por eso el 8mer se busca primero — es el mas especifico — y lo que
    pisa su huella ya no se vuelve a contar.
    """
    upper = sequence.upper()
    conteo = {t: 0 for t in SITE_TYPES}
    ocupadas: set[int] = set()

    for tipo in SITE_TYPES:  # 8mer primero: es el mas especifico
        patron = patterns[tipo]
        inicio = 0
        while True:
            i = upper.find(patron, inicio)
            if i == -1:
                break
            huella = range(i, i + len(patron))
            if not any(p in ocupadas for p in huella):
                conteo[tipo] += 1
                ocupadas.update(huella)
            inicio = i + 1
    return conteo


@dataclass(frozen=True)
class SeedLoad:
    """Numero comparativo, nunca veredicto."""

    state: FilterState
    counts: dict[str, int] = field(default_factory=dict)
    total: int | None = None
    transcripts_hit: int = 0
    weighted: float | None = None
    sin_expresion: tuple[str, ...] = ()
    utrs: Utr3Set | None = None
    reason: str = ""

    def as_column(self) -> str:
        return "" if self.total is None else str(self.total)

    def format_text(self) -> str:
        if self.utrs is None:
            return (
                "Carga de seed — NOT_RUN\n"
                f"  {self.reason}"
            )
        lines = [
            f"Carga de seed — {self.total} sitio(s) en "
            f"{self.transcripts_hit} transcrito(s)",
            "  Desglose: "
            + ", ".join(f"{t}={self.counts[t]}" for t in SITE_TYPES),
            f"  3'UTR: {self.utrs.provenance}",
        ]
        if self.weighted is not None:
            lines.append(f"  Ponderado por expresion: {self.weighted:.1f}")
        if self.sin_expresion:
            lines.append(
                f"  {len(self.sin_expresion)} transcrito(s) con sitios pero sin dato de "
                f"expresion: NO se les ha puesto un valor inventado, quedan fuera del "
                f"numero ponderado."
            )
        lines.append(
            "  Esto no lo ve ningun alineador: el filtro de especificidad compara la "
            "guia entera, asi que estos sitios no salen en su informe. No es un "
            "veredicto — es un numero para desempatar."
        )
        return "\n".join(lines)


def seed_load(
    guide: str,
    utrs: Utr3Set | None,
    expression: dict[str, float] | None = None,
) -> SeedLoad:
    """Cuenta los sitios de seed en los 3'UTR del transcriptoma. Sin base: NOT_RUN."""
    if utrs is None:
        return SeedLoad(
            state=FilterState.NOT_RUN,
            reason=(
                "No hay conjunto de 3'UTR del transcriptoma cargado, asi que la carga "
                "de off-targets por seed no se puede contar. NOT_RUN no es PASS, y "
                "sobre todo no es un cero: no saber cuantos hay no es lo mismo que no "
                "haber ninguno."
            ),
        )

    patterns = site_patterns(guide)
    totales = {t: 0 for t in SITE_TYPES}
    tocados = 0
    ponderado = 0.0
    sin_dato: list[str] = []

    for nombre, secuencia in utrs.records.items():
        conteo = _count_in(secuencia, patterns)
        sitios = sum(conteo.values())
        if not sitios:
            continue
        tocados += 1
        for tipo, n in conteo.items():
            totales[tipo] += n
        if expression is not None:
            valor = expression.get(nombre)
            if valor is None:
                sin_dato.append(nombre)
            else:
                ponderado += valor * sitios

    return SeedLoad(
        state=FilterState.PASS,
        counts=totales,
        total=sum(totales.values()),
        transcripts_hit=tocados,
        weighted=ponderado if expression is not None else None,
        sin_expresion=tuple(sin_dato),
        utrs=utrs,
        reason=(
            f"{sum(totales.values())} sitio(s) de seed en {tocados} transcrito(s). "
            f"Numero comparativo, no veredicto."
        ),
    )


def parse_fasta_records(text: str, *, source: str) -> dict[str, str]:
    """FASTA → {identificador: secuencia}. Aborta si no hay ninguna entrada."""
    records: dict[str, str] = {}
    nombre: str | None = None
    partes: list[str] = []

    def cerrar() -> None:
        nonlocal nombre, partes
        if nombre is not None:
            if nombre in records:
                raise ShmirDesignError(
                    f"{source}: el identificador {nombre!r} aparece dos veces; se "
                    f"aborta en vez de quedarse con una de las dos secuencias."
                )
            records[nombre] = "".join(partes).upper()
        nombre, partes = None, []

    for linea in text.splitlines():
        if linea.startswith(">"):
            cerrar()
            nombre = linea[1:].split()[0] if linea[1:].strip() else ""
            continue
        if nombre is not None:
            partes.append(linea.strip())
    cerrar()

    if not records:
        raise ShmirDesignError(
            f"{source}: no hay ninguna entrada FASTA; se aborta en vez de contar sobre "
            f"un conjunto vacio."
        )
    return records


def load_utr3_set(
    path, *, version: str, expected_md5: str | None = None
) -> Utr3Set:
    """Lee el FASTA de 3'UTR del transcriptoma y comprueba su md5."""
    import hashlib
    from pathlib import Path

    from .errors import ChecksumMismatchError

    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer el FASTA de 3'UTR {path} ({exc}); la carga de seed queda "
            f"sin contar."
        ) from exc
    md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    if expected_md5 is not None and md5 != expected_md5:
        raise ChecksumMismatchError(
            f"{path}: md5 {md5} y se esperaba {expected_md5}. El fichero NO es el que "
            f"dice ser; se aborta antes de contar nada con el."
        )
    try:
        texto = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ShmirDesignError(f"{path}: no es UTF-8 ({exc}); se aborta.") from exc
    return Utr3Set(
        records=parse_fasta_records(texto, source=str(path)),
        source=str(path),
        version=version,
        checksum=md5,
    )


def load_expression_table(path) -> dict[str, float]:
    """TSV `identificador<TAB>valor`. `#` es comentario. Un valor no numerico aborta."""
    from pathlib import Path

    path = Path(path)
    try:
        texto = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer la tabla de expresion {path} ({exc}); la carga de seed "
            f"quedaria sin ponderar y eso hay que decirlo, no suponerlo."
        ) from exc

    tabla: dict[str, float] = {}
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        campos = linea.split("\t") if "\t" in linea else linea.split()
        if len(campos) < 2:
            raise ShmirDesignError(
                f"{path}:{numero}: se esperaba `identificador<TAB>valor` y hay "
                f"{len(campos)} campo(s); se aborta."
            )
        try:
            tabla[campos[0]] = float(campos[1])
        except ValueError as exc:
            raise ShmirDesignError(
                f"{path}:{numero}: {campos[1]!r} no es un numero ({exc}); se aborta en "
                f"vez de tratarlo como cero."
            ) from exc
    if not tabla:
        raise ShmirDesignError(
            f"{path}: la tabla de expresion no tiene ninguna fila; se aborta."
        )
    return tabla
