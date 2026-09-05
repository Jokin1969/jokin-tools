"""Comprobar el plásmido montado a mano. NO se genera: se verifica.

## Por qué no se generan los `.dna` completos

Un plásmido de 5.400 pb ensamblado por código es demasiada superficie para un error
silencioso, y el módulo, el casete y el fragmento ya se emiten. Lo que faltaba era el
otro extremo: **entre lo que la app emite y lo que acaba en el vector no había ninguna
comprobación**. Es el último eslabón sin red, y es exactamente el criterio de
`gblock.verify_contexts_against_plasmid` con SGEP — se comprueba lo que se construyó, no
se construye.

## Por SECUENCIA, no por coordenadas

Un número escrito no puede validar el fichero del que salió (principio nº 13). Esto busca
el fragmento DENTRO del plásmido y compara secuencia con secuencia; no mira la posición
3129 de nada. Una feature corrida un nucleótido no lo engaña, y un plásmido con el intrón
en otro sitio pasa igual — que es lo correcto: la pregunta es «¿está dentro lo que
emitimos?», no «¿está donde yo creía?».

## Lo que NO hace, y va dicho

No dice si el plásmido «funciona», ni comprueba el resto del vector: comprueba el
fragmento. Y cuando algo falla, dice **qué encontró**, no por qué — un diagnóstico
equivocado cuesta más que ninguno (principio nº 3, y la lección del «Alu 0 %» obtenido
sin buscar Alu).

Python 3.11+, solo biblioteca estándar (regla 6).
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass

from .errors import ShmirDesignError
from .filters import FilterResult, FilterState
from .reference import sequence_md5

#: Lo que se admite como base en un plásmido. IUPAC completo: un `.dna` de laboratorio
#: puede traer ambigüedades, y rechazarlas sería confundir «no es ADN» con «no es ADN
#: sin ambigüedad».
DNA_ALPHABET = frozenset("ACGTUNRYSWKMBDHV")

#: Cabecera del `.dna` de SnapGene: byte de tipo 0x09 y la palabra `SnapGene` dentro del
#: primer segmento.
SNAPGENE_MAGIC = b"\x09"
SNAPGENE_COOKIE = b"SnapGene"
#: El segmento que lleva la secuencia de ADN.
SNAPGENE_DNA_SEGMENT = 0

SNAPGENE_FORMAT_DECLARED = (
    "El formato `.dna` de SnapGene está DECLARADO aquí a partir de su descripción "
    "pública —cabecera con la palabra «SnapGene», y segmentos de tipo (1 byte) más "
    "longitud (4 bytes, big-endian), con el segmento 0 llevando un byte de banderas y la "
    "secuencia en ASCII— y NO está verificado contra ningún `.dna` real de este "
    "repositorio: aquí no hay ninguno. Por eso el lector no se fía de la descripción, la "
    "INTERROGA: comprueba la cabecera, comprueba que la longitud declarada de cada "
    "segmento cabe en el fichero y comprueba que lo que lee es ADN. Si algo no cuadra "
    "ABORTA diciendo qué, en vez de devolver una secuencia plausible — que es el peor "
    "resultado posible de este software (regla 1). El día que llegue un `.dna` real, ese "
    "fichero es la prueba y esta nota se sustituye por la medida."
)


#: Mismo criterio que en `fragmento`: el md5 lo calcula `reference.sequence_md5` y no
#: este módulo. Los dos lados de esta comprobación —el número que viaja en la cabecera
#: del FASTA y el que se recalcula aquí— tienen que salir de la MISMA definición, o el
#: cruce dejaría de significar nada (principio nº 24).
_md5 = sequence_md5


# ─── Leer el plásmido, venga como venga ──────────────────────────────────────


def snapgene_sequence(data: bytes) -> str:
    """La secuencia de un `.dna` de SnapGene, comprobando lo que lee.

    Ver `SNAPGENE_FORMAT_DECLARED`: el formato está descrito, no medido, así que cada
    afirmación del fichero se comprueba antes de usarla.
    """
    if not data.startswith(SNAPGENE_MAGIC):
        raise ShmirDesignError(
            f"No parece un `.dna` de SnapGene: el primer byte es {data[:1]!r} y se "
            f"esperaba {SNAPGENE_MAGIC!r}. Se aborta en vez de interpretar bytes a ver "
            f"qué sale."
        )
    if SNAPGENE_COOKIE not in data[:64]:
        raise ShmirDesignError(
            f"No parece un `.dna` de SnapGene: no aparece {SNAPGENE_COOKIE!r} en la "
            f"cabecera. Se aborta. {SNAPGENE_FORMAT_DECLARED}"
        )
    posicion = 0
    total = len(data)
    while posicion + 5 <= total:
        tipo = data[posicion]
        (longitud,) = struct.unpack(">I", data[posicion + 1 : posicion + 5])
        inicio = posicion + 5
        if inicio + longitud > total:
            raise ShmirDesignError(
                f"El `.dna` declara un segmento de tipo {tipo} y {longitud} bytes en la "
                f"posición {posicion}, y el fichero sólo tiene {total}. La longitud "
                f"declarada no cabe: se aborta en vez de leer lo que haya."
            )
        if tipo == SNAPGENE_DNA_SEGMENT:
            if longitud < 2:
                raise ShmirDesignError(
                    f"El segmento de ADN del `.dna` declara {longitud} bytes y hacen "
                    f"falta al menos dos (banderas + secuencia). Se aborta."
                )
            crudo = data[inicio + 1 : inicio + longitud]
            try:
                secuencia = crudo.decode("ascii").upper()
            except UnicodeDecodeError as error:
                raise ShmirDesignError(
                    f"El segmento de ADN del `.dna` no es ASCII: {error}. Se aborta."
                ) from error
            malas = sorted(set(secuencia) - DNA_ALPHABET)
            if malas:
                raise ShmirDesignError(
                    f"El segmento de ADN del `.dna` trae caracteres fuera del alfabeto "
                    f"del ADN ({', '.join(repr(c) for c in malas[:5])}). O el fichero no "
                    f"es lo que dice o el formato no es el descrito; se aborta. "
                    f"{SNAPGENE_FORMAT_DECLARED}"
                )
            return secuencia
        posicion = inicio + longitud
    raise ShmirDesignError(
        "El `.dna` no trae ningún segmento de ADN (tipo "
        f"{SNAPGENE_DNA_SEGMENT}). Se aborta en vez de devolver una secuencia vacía, "
        "que se leería como «el plásmido no lleva el fragmento»."
    )


_ORIGIN = re.compile(r"^ORIGIN", re.MULTILINE)


def plasmid_sequence(source: str | bytes) -> str:
    """La secuencia del plásmido, venga en GenBank, FASTA, pelada o en `.dna`.

    El formato se DERIVA de lo que hay dentro, no de la extensión: un `.gb` renombrado a
    `.dna` es exactamente el caso en el que una extensión miente.
    """
    if isinstance(source, (bytes, bytearray)):
        if bytes(source[:1]) == SNAPGENE_MAGIC:
            return snapgene_sequence(bytes(source))
        try:
            source = bytes(source).decode("utf-8")
        except UnicodeDecodeError as error:
            raise ShmirDesignError(
                f"El fichero no es texto y tampoco es un `.dna` de SnapGene "
                f"(empieza por {bytes(source[:1])!r}): {error}. Se aborta."
            ) from error

    texto = str(source)
    if _ORIGIN.search(texto):
        cuerpo = texto[_ORIGIN.search(texto).end() :]
        letras = [c for c in cuerpo.split("//", 1)[0] if c.isalpha()]
        return "".join(letras).upper()
    lineas = [
        l.strip() for l in texto.splitlines() if l.strip() and not l.startswith(">")
    ]
    secuencia = "".join(lineas).upper()
    malas = sorted(set(secuencia) - DNA_ALPHABET)
    if malas:
        raise ShmirDesignError(
            f"Lo que se ha dado no se lee como una secuencia de ADN: trae "
            f"{', '.join(repr(c) for c in malas[:5])}. Se admite GenBank, FASTA, "
            f"secuencia pelada o un `.dna` de SnapGene; se aborta en vez de comparar "
            f"contra un texto que no es ADN."
        )
    return secuencia


# ─── Leer lo que la app emitió ───────────────────────────────────────────────


@dataclass(frozen=True)
class EmittedFragment:
    """Un fragmento del FASTA que emitió la app, con lo que su cabecera DECLARA."""

    name: str
    sequence: str
    declared: dict[str, str]

    @property
    def md5(self) -> str:
        return _md5(self.sequence)

    @property
    def growth(self) -> int | None:
        crudo = self.declared.get("crece", "")
        return int(crudo) if crudo.lstrip("-").isdigit() else None


def parse_fragments_fasta(text: str) -> tuple[EmittedFragment, ...]:
    """Relee el FASTA de fragmentos y CRUZA cada md5 con su secuencia.

    Un fichero que viaja solo tiene que poder validarse solo: si alguien retocó una base
    por el camino, el md5 de la cabecera deja de cuadrar y esto aborta AQUÍ, antes de
    comparar nada con el plásmido. Sin este cruce, un FASTA editado a mano compararía
    mal contra un montaje correcto y el diagnóstico saldría del lado equivocado.
    """
    registros: list[EmittedFragment] = []
    nombre, campos, piezas = "", {}, []

    def cerrar() -> None:
        if not nombre:
            return
        secuencia = "".join(piezas).upper()
        if not secuencia:
            raise ShmirDesignError(
                f"El registro {nombre!r} del FASTA de fragmentos no trae secuencia. "
                f"Se aborta."
            )
        declarado = campos.get("md5", "")
        if declarado and declarado != _md5(secuencia):
            raise ShmirDesignError(
                f"El registro {nombre!r} declara md5 {declarado} y su secuencia da "
                f"{_md5(secuencia)}: el FASTA no es el que emitió la app. Se aborta "
                f"antes de compararlo con ningún plásmido — comparar con un fragmento "
                f"retocado echaría la culpa al montaje."
            )
        registros.append(
            EmittedFragment(name=nombre, sequence=secuencia, declared=dict(campos))
        )

    for linea in str(text).splitlines():
        if linea.startswith(">"):
            cerrar()
            cabecera = linea[1:].split()
            nombre = cabecera[0] if cabecera else ""
            campos = {}
            for trozo in cabecera[1:]:
                if "=" in trozo:
                    clave, valor = trozo.split("=", 1)
                    campos[clave] = valor
            piezas = []
        elif linea.strip():
            piezas.append(linea.strip())
    cerrar()
    if not registros:
        raise ShmirDesignError(
            "El FASTA de fragmentos no trae ningún registro. Se aborta en vez de "
            "devolver «todo correcto» sobre cero comprobaciones."
        )
    return tuple(registros)


# ─── La comprobación ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AssemblyReport:
    """Lo que se ha podido comprobar del plásmido montado, y lo que no."""

    plasmid_name: str
    plasmid_length: int
    plasmid_md5: str
    checks: tuple[FilterResult, ...]

    @property
    def verdict_state(self) -> FilterState:
        if any(r.state is FilterState.FAIL for r in self.checks):
            return FilterState.FAIL
        if any(r.state is FilterState.NOT_RUN for r in self.checks):
            return FilterState.NOT_RUN
        return FilterState.PASS

    def check(self, name: str) -> FilterResult:
        for resultado in self.checks:
            if resultado.name == name:
                return resultado
        disponibles = ", ".join(r.name for r in self.checks)
        raise KeyError(f"No hay comprobación {name!r}; las que hay: {disponibles}.")

    def render(self) -> str:
        lineas = [
            f"═══ El plásmido montado contra lo que emitió la app ═══",
            "",
            f"  Plásmido : {self.plasmid_name}, {self.plasmid_length} pb, "
            f"md5 {self.plasmid_md5}",
            "",
        ]
        for resultado in self.checks:
            lineas.append(f"  [{resultado.state.value}] {resultado.name}")
            lineas.append(f"      {resultado.reason}")
        lineas.extend(["", f"  Veredicto: {self.verdict_state.value}"])
        return "\n".join(lineas)


#: Cuánto contexto se enseña alrededor de lo que se encontró. No sirve para juzgar: es
#: para que quien lea el fallo pueda mirarlo en su propio fichero.
CONTEXT_SHOWN = 20


def verify_assembly(
    plasmid: str | bytes,
    fragments_fasta_text: str,
    *,
    name: str = "el plásmido montado",
    previous_intron: str = "",
) -> AssemblyReport:
    """¿Lleva el plásmido montado EXACTAMENTE el fragmento que emitió la app?

    `previous_intron` es el intrón que había ANTES (vacío = se deriva del registro, el
    del casete parental). Encontrarlo todavía dentro es el fallo real que esto caza: se
    pegó al lado en vez de encima, y el plásmido lleva los dos.
    """
    secuencia = plasmid_sequence(plasmid)
    emitidos = parse_fragments_fasta(fragments_fasta_text)

    if not previous_intron:
        from .introns import get  # noqa: PLC0415

        previous_intron = get("mvm_actual").empty_sequence

    presentes = [f for f in emitidos if f.sequence in secuencia]
    ausentes = [f for f in emitidos if f.sequence not in secuencia]

    if ausentes:
        detalle = "; ".join(
            f"{f.name} ({len(f.sequence)} nt, md5 {f.md5}) no aparece"
            for f in ausentes
        )
        presencia = FilterResult(
            name="fragmento_presente",
            state=FilterState.FAIL,
            reason=(
                f"De los {len(emitidos)} fragmento(s) emitidos, {len(ausentes)} NO "
                f"están en {name} ({len(secuencia)} pb): {detalle}. Se dice lo que se "
                f"ha encontrado y no por qué: la comprobación busca la secuencia "
                f"exacta y no puede distinguir una base cambiada de un fragmento "
                f"distinto ni de un plásmido equivocado."
            ),
        )
    else:
        presencia = FilterResult(
            name="fragmento_presente",
            state=FilterState.PASS,
            reason=(
                f"{len(emitidos)} fragmento(s) emitido(s) están en {name} "
                f"({len(secuencia)} pb), letra por letra: "
                + "; ".join(f"{f.name} md5 {f.md5}" for f in emitidos)
                + ". Buscados POR SECUENCIA: ninguna coordenada interviene."
            ),
        )

    repetidos = {
        f.name: secuencia.count(f.sequence) for f in presentes
        if secuencia.count(f.sequence) > 1
    }
    if repetidos:
        unicidad = FilterResult(
            name="fragmento_unico",
            state=FilterState.FAIL,
            reason=(
                f"Hay fragmento(s) que aparecen más de una vez en {name}: "
                + ", ".join(f"{n} × {c}" for n, c in sorted(repetidos.items()))
                + ". Un plásmido con dos copias no es el que se diseñó."
            ),
        )
    elif presentes:
        unicidad = FilterResult(
            name="fragmento_unico",
            state=FilterState.PASS,
            reason=f"Cada fragmento aparece UNA sola vez en {name}.",
        )
    else:
        unicidad = FilterResult(
            name="fragmento_unico",
            state=FilterState.NOT_RUN,
            reason="No se ha encontrado ningún fragmento, así que no hay nada que contar.",
        )

    cuantos_viejo = secuencia.count(previous_intron)
    if cuantos_viejo:
        i = secuencia.index(previous_intron)
        contexto = secuencia[max(0, i - CONTEXT_SHOWN) : i + CONTEXT_SHOWN]
        previo = FilterResult(
            name="sin_intron_previo",
            state=FilterState.FAIL,
            reason=(
                f"El intrón ANTERIOR ({len(previous_intron)} nt, md5 "
                f"{_md5(previous_intron)}) sigue en {name}, {cuantos_viejo} vez(ces). "
                f"Contexto de la primera: …{contexto}… Si el fragmento también está, el "
                f"plásmido lleva LOS DOS: se pegó al lado en vez de encima. Se dice lo "
                f"que hay; la causa la decide quien mire el fichero."
            ),
        )
    else:
        previo = FilterResult(
            name="sin_intron_previo",
            state=FilterState.PASS,
            reason=(
                f"El intrón anterior ({len(previous_intron)} nt) no está en {name}: la "
                f"sustitución lo reemplazó en vez de añadirse al lado."
            ),
        )

    declarados = [f for f in presentes if f.growth is not None]
    if not declarados:
        crecimiento = FilterResult(
            name="crecimiento",
            state=FilterState.NOT_RUN,
            reason=(
                "Ningún fragmento presente declara cuánto crece el plásmido, así que "
                "no se ha podido cruzar la longitud. NOT_RUN no es PASS."
            ),
        )
    else:
        crecimiento = FilterResult(
            name="crecimiento",
            state=FilterState.PASS,
            reason=(
                f"{name} mide {len(secuencia)} pb. Los fragmentos presentes declaran un "
                f"crecimiento de "
                + ", ".join(f"{f.name} +{f.growth}" for f in declarados)
                + " sobre el casete de referencia: la longitud del montaje se compara "
                "con la del casete DEL QUE SE PARTIÓ, que esta comprobación no tiene "
                "delante — por eso el número se emite y no se juzga."
            ),
        )

    return AssemblyReport(
        plasmid_name=name,
        plasmid_length=len(secuencia),
        plasmid_md5=_md5(secuencia),
        checks=(presencia, unicidad, previo, crecimiento),
    )
