"""Barrido de longitudes de espaciador: la CURVA del compromiso, no un óptimo.

**Los dos lados no son simétricos**, y eso manda sobre todo lo demás:

  - el de **5' separa del DONANTE**. Recorte AGRESIVO: si el donante aguanta con 8 nt,
    vale con 8;
  - el de **3' separa del PUNTO DE RAMIFICACION y del TRACTO**, que son los elementos
    frágiles. Recorte CONSERVADOR: aquí quedarse corto cuesta el empalme entero.

**El suelo NO ES UN NUMERO: es la accesibilidad.** No hay una longitud mínima que se
declare y se defienda; hay un criterio de aceptación —que donante, punto de ramificación
y tracto sigan desapareados en el plegado del intrón completo CON el módulo dentro— y las
longitudes que lo cumplen salen de medirlo. Un espaciador de 8 nt en 5' que mantiene el
donante accesible vale; uno de 30 en 3' que no deja libre el punto, no.

**El CERO se prueba a propósito.** Si el plegado aguanta sin espaciador, el argumento
para tenerlo desaparece — y eso hay que poder verlo en la tabla en vez de darlo por
imposible sin mirar.

**Y no se colapsa a un par de valores.** Lo que se emite es la curva entera: cada
longitud con la accesibilidad de los tres elementos y el donante→punto resultante. Si
varias longitudes empatan, salen todas. Elegir una por nuestra cuenta escondería
exactamente el compromiso que esto existe para enseñar.

Python 3.11+, sólo biblioteca estándar más el ViennaRNA que ya usa `intron_folding`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from .errors import ShmirDesignError

#: El rango que se explora en los dos lados. El 45 no es un límite físico: es el punto de
#: partida del lado 3', y explorar por encima de lo que hay hoy no responde a la pregunta
#: —que es si SOBRA espaciador, no si falta—.
SWEEP_RANGE = (0, 45)

#: Lo que hay hoy, y la referencia contra la que se mide todo lo demás.
STARTING_POINT = {"5": 20, "3": 45}

#: Los TRES elementos frágiles. El aceptor no está: es la frontera, no lo que el
#: espliceosoma lee para decidir. El tracto entró en `intron_folding` para esto.
FRAGILE = ("donante", "punto_de_ramificacion", "tracto_polipirimidinas")

SIDES = {
    "5": "el DONANTE — recorte agresivo: separar de él cuesta poco",
    "3": (
        "el PUNTO DE RAMIFICACIÓN y el TRACTO de polipirimidinas — recorte conservador: "
        "son los elementos frágiles y quedarse corto cuesta el empalme entero"
    ),
}

#: POR QUE EL CRITERIO ES RELATIVO Y NO UN UMBRAL. Un número absoluto —«desapareado por
#: encima de 0,6»— no lo respalda nadie, y este proyecto ya sabe lo que cuesta un criterio
#: sin procedencia que emite veredictos (ver `docs/procedencia-g4.md`). La referencia es
#: lo que hay HOY funcionando: 20/45. Una longitud es admisible si los tres elementos
#: quedan NO PEOR que ahí. Eso no inventa nada y contesta la pregunta que se hace.
ADMISSIBILITY_RULE = (
    "El criterio es RELATIVO al punto de partida 20/45, no un umbral absoluto: una "
    "longitud es admisible si los TRES elementos frágiles quedan no peor que con los "
    "espaciadores de hoy. Un umbral absoluto no lo respalda nadie, y un criterio sin "
    "procedencia que emite veredictos es exactamente lo que se acaba de retirar."
)


@dataclass(frozen=True)
class SweepPoint:
    """Una longitud probada, con la DISTRIBUCION de lo que se midio en ella.

    `unpaired` es la mediana y `spread` el (minimo, maximo) entre replicas. Los dos
    juntos, siempre: la mediana sola esconde justo lo que hace falta ver — que la
    dispersion entre secuencias de la MISMA longitud es del orden del efecto de la
    longitud, y por tanto que la longitud sola no decide.
    """

    length: int
    unpaired: dict[str, float]
    spread: dict[str, tuple[float, float]]
    donor_to_branch: int
    total_inserted: int
    replicas: int

    def describe(self) -> str:
        medidas = "  ".join(
            f"{self.unpaired[n]:.2f} [{self.spread[n][0]:.2f}-{self.spread[n][1]:.2f}]"
            for n in FRAGILE
        )
        return f"  {self.length:>3} nt   {medidas}   {self.donor_to_branch:>4} nt"


@dataclass(frozen=True)
class Sweep:
    """La curva de un lado. No trae ningún «óptimo» a propósito."""

    intron: str
    side: str
    other: int
    points: tuple[SweepPoint, ...]
    baseline: dict[str, float] = field(default_factory=dict)

    @property
    def what_it_separates(self) -> str:
        return SIDES[self.side]

    @property
    def admissible(self) -> tuple[SweepPoint, ...]:
        """Las que dejan los tres elementos NO PEOR que el punto de partida.

        Si varias empatan salen TODAS: elegir una escondería el compromiso.
        """
        if not self.baseline:
            return ()
        return tuple(
            p for p in self.points
            if all(p.unpaired[n] >= self.baseline[n] for n in FRAGILE)
        )

    @property
    def discriminates(self) -> dict[str, bool]:
        """¿SE VE la longitud por encima del ruido de la secuencia, elemento a elemento?

        La comparacion honesta: el recorrido de las MEDIANAS entre longitudes frente a
        la dispersion TIPICA dentro de una longitud. Si la segunda se come al primero, la
        curva no distingue longitudes y decir «admisible: 20» seria presentar como
        respuesta lo que es un artefacto de exigir «no peor en los tres a la vez» sobre
        numeros que son ruido.
        """
        salida = {}
        for nombre in FRAGILE:
            medianas = [p.unpaired[nombre] for p in self.points]
            dispersiones = [p.spread[nombre][1] - p.spread[nombre][0] for p in self.points]
            if not medianas or not dispersiones:
                salida[nombre] = False
                continue
            recorrido = max(medianas) - min(medianas)
            tipica = median(sorted(dispersiones))
            salida[nombre] = recorrido > tipica
        return salida

    @property
    def conclusive(self) -> bool:
        return any(self.discriminates.values())

    def describe(self) -> list[str]:
        lineas = [
            f"Barrido del espaciador {self.side}' de «{self.intron}» "
            f"(el otro lado fijo en {self.other} nt)",
            f"  Separa: {self.what_it_separates}",
            f"  Punto de partida: {STARTING_POINT[self.side]} nt",
            "",
            f"  Réplicas por longitud: {self.points[0].replicas if self.points else 0}"
            f" — {WHY_REPLICAS}",
            "",
            "  long   " + "  ".join(f"{n[:11]:^18}" for n in FRAGILE)
            + "   donante→punto",
            "         " + "  ".join(f"{'mediana [min-max]':^18}" for n in FRAGILE),
        ]
        lineas.extend(p.describe() for p in self.points)
        lineas.extend(["", "  ¿La LONGITUD se ve por encima del ruido de la SECUENCIA?"])
        for nombre, si in self.discriminates.items():
            medianas = [p.unpaired[nombre] for p in self.points]
            dispersiones = [
                p.spread[nombre][1] - p.spread[nombre][0] for p in self.points
            ]
            recorrido = max(medianas) - min(medianas)
            tipica = median(sorted(dispersiones))
            lineas.append(
                f"    {nombre:<24} recorrido entre longitudes {recorrido:.2f}  ·  "
                f"dispersión típica dentro de una {tipica:.2f}  →  "
                f"{'SÍ' if si else 'NO'}"
            )
        admisibles = [p.length for p in self.admissible]
        lineas.extend(["", f"  Admisibles: {admisibles if admisibles else 'NINGUNA'}"])
        if not self.conclusive:
            lineas.extend(
                [
                    "",
                    "  ⚠ NO CONCLUYENTE, y ese es el resultado. En NINGÚN elemento el "
                    "recorrido entre",
                    "    longitudes supera la dispersión dentro de una sola longitud: lo "
                    "que mueve la",
                    "    accesibilidad es la SECUENCIA del espaciador, no su longitud. "
                    "Con este método el",
                    "    suelo NO se puede fijar por accesibilidad — no porque falte "
                    "medir, sino porque el",
                    "    criterio no distingue lo que se le pide distinguir.",
                    "",
                    "    Y la lista de admisibles de arriba es un ARTEFACTO: exigir «no "
                    "peor en los tres a",
                    "    la vez» sobre números que son ruido deja fuera todo menos el "
                    "punto de referencia,",
                    "    que se compara consigo mismo. NO se lee como «la respuesta es "
                    "ésa».",
                ]
            )
        lineas.extend(
            [
                "",
                f"  {ADMISSIBILITY_RULE}",
                "  No se elige una: si varias empatan, salen todas. El compromiso se ve.",
            ]
        )
        return lineas


#: Cuantas secuencias DISTINTAS se prueban por longitud. Ver `WHY_REPLICAS`.
DEFAULT_REPLICAS = 5

#: POR QUE HAY REPLICAS Y NO UNA SECUENCIA POR LONGITUD. La primera version usaba UNA, y
#: la curva que salio era inservible: los valores saltaban de 0,41 a 0,87 sin relacion con
#: la longitud, porque cada longitud llevaba una SECUENCIA distinta y el plegado se mueve
#: mucho mas con la secuencia que con la longitud. Longitud y secuencia quedaban
#: CONFUNDIDAS, asi que la curva no medía lo que decia medir.
#:
#: Con varias secuencias por longitud, la dispersion DENTRO de cada longitud es el efecto
#: de la secuencia y el desplazamiento ENTRE longitudes es el efecto de la longitud. Sin
#: eso no se pueden separar. Es el corolario de la errata nº 10 —un calculo solo se puede
#: validar sobre mas de un caso— aplicado a cada punto de la curva.
WHY_REPLICAS = (
    "Cada longitud se prueba con varias secuencias distintas. Con una sola, longitud y "
    "secuencia quedan confundidas: el plegado se mueve mucho más con la secuencia que "
    "con la longitud, y la curva no mide lo que dice medir. La dispersión dentro de cada "
    "longitud es el efecto de la secuencia; el desplazamiento entre longitudes, el de la "
    "longitud."
)

#: Motivos de relleno, de composicion parecida y sin GT canonico. NO es diseño de
#: secuencia: lo que se diseñe de verdad pasa por `spacers.choose_spacers`, que filtra
#: motivos. Aqui solo hacen falta secuencias DISTINTAS y comparables entre si.
_MOTIVOS = (
    "ATTACAATGA", "TAACATTAGA", "ATCAAGATTA", "CAATTAGATA", "TTAGACAATA",
)


def _spacer(length: int, replica: int = 0) -> str:
    """Un espaciador de esa longitud y esa replica. Deterministico: sin azar."""
    motivo = _MOTIVOS[replica % len(_MOTIVOS)]
    return (motivo * ((length // len(motivo)) + 1))[:length]


def sweep_side(
    intron: str,
    *,
    side: str,
    lengths,
    other: int,
    module: str,
    medir=None,
    replicas: int = DEFAULT_REPLICAS,
) -> Sweep:
    """Barre un lado y devuelve la curva entera. `medir` se inyecta para poder probarlo."""
    if side not in SIDES:
        raise ShmirDesignError(
            f"El lado {side!r} no existe; son {' y '.join(sorted(SIDES))}. Se aborta."
        )
    bajo, alto = SWEEP_RANGE
    for largo in lengths:
        if not bajo <= largo <= alto:
            raise ShmirDesignError(
                f"La longitud {largo} está fuera del rango declarado {bajo}-{alto}. "
                f"Explorar por encima de lo que hay hoy no responde a la pregunta, que "
                f"es si SOBRA espaciador. Se aborta."
            )
    if medir is None:
        medir = _medir_de_verdad

    from .introns import INTRONS, locate_elements  # noqa: PLC0415

    entrada = INTRONS.get(intron)
    if entrada is None:
        raise ShmirDesignError(
            f"No hay ningún intrón {intron!r}; los que hay son {', '.join(INTRONS)}."
        )

    def _medidas(largo: int, cuantas: int):
        salida = []
        for replica in range(cuantas):
            cinco = _spacer(largo if side == "5" else other, replica)
            tres = _spacer(other if side == "5" else largo, replica)
            salida.append((cinco, tres, medir(entrada, module, cinco, tres)))
        return salida

    def punto(largo: int) -> SweepPoint:
        medidas = _medidas(largo, replicas)
        cinco, tres, _ = medidas[0]
        montado = entrada.with_module(module, spacer5=cinco, spacer3=tres)
        elementos = locate_elements(montado, name=intron)
        distancias = [
            c.branch_a - elementos.donor.end - 1
            for c in elementos.branch_candidates
            if c.branch_a is not None
        ]
        por_elemento = {n: sorted(m[2][n] for m in medidas) for n in FRAGILE}
        return SweepPoint(
            length=largo,
            unpaired={n: median(v) for n, v in por_elemento.items()},
            spread={n: (v[0], v[-1]) for n, v in por_elemento.items()},
            donor_to_branch=min(distancias) if distancias else -1,
            total_inserted=len(module) + len(cinco) + len(tres),
            replicas=replicas,
        )

    # La referencia se mide con las MISMAS replicas: comparar una mediana contra un
    # valor suelto seria comparar dos cosas distintas.
    base = [
        medir(
            entrada, module,
            _spacer(STARTING_POINT["5"], r), _spacer(STARTING_POINT["3"], r),
        )
        for r in range(replicas)
    ]
    referencia = {n: median(sorted(m[n] for m in base)) for n in FRAGILE}
    return Sweep(
        intron=intron, side=side, other=int(other),
        points=tuple(punto(int(l)) for l in lengths),
        baseline=dict(referencia),
    )


def _medir_de_verdad(entrada, module, spacer5, spacer3) -> dict[str, float]:
    """Pliega el intrón entero con el módulo dentro y devuelve los tres elementos."""
    from .intron_folding import fold_intron  # noqa: PLC0415

    plegado = fold_intron(
        entrada, module=module, spacer5=spacer5, spacer3=spacer3
    )
    if not plegado.unpaired:
        raise ShmirDesignError(
            f"El plegado de «{entrada.name}» no devolvió ninguna probabilidad: "
            f"{plegado.reason} Sin ellas no hay criterio de aceptación que aplicar, y "
            f"no haber plegado NO es «los elementos están accesibles»."
        )
    return {n: float(plegado.unpaired[n]) for n in FRAGILE}
