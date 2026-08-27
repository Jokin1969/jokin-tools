"""De donde sale cada umbral. Ninguno se imprime sin decirlo.

Un numero en un informe sin decir de donde sale se lee como si fuera una medida. Aqui
cada umbral declara su ORIGEN, que es una de tres cosas y solo tres:

  - `literatura`  — viene de trabajo publicado. Lleva **de que** trabajo, y si no se
                    puede citar aqui con seguridad, NO se marca como literatura.
  - `convencion`  — es un convenio de diseño declarado por este proyecto. No hay medida
                    detras y se dice.
  - `nuestro`     — es una decision de este proyecto, tomada con datos delante y con su
                    fecha. Se puede discutir; lo que no se puede es leerla como un hecho.

**La distincion no es cosmetica.** El flanco de ±10 nt del eje esterico es el caso que
obliga a tenerla: NO TIENE BASE MEDIDA, la huella real de CPSF/CstF sobre el pre-mRNA es
mayor, y presentarlo al lado de un GC del 30-55 % —que si sale de trabajo publicado—
sin distinguirlos le atribuye una precision que la biologia no tiene.

Hay un test que exige que TODO campo de `hard_filters.Thresholds` tenga su entrada aqui:
un umbral nuevo sin justificar hace fallar la suite.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ShmirDesignError

#: Los tres origenes posibles. CERRADO: un cuarto seria una forma de no elegir.
ORIGINS = ("literatura", "convencion", "nuestro")

ORIGIN_MEANING = {
    "literatura": (
        "viene de trabajo publicado. Si no se puede citar con seguridad, no se marca así"
    ),
    "convencion": (
        "es un convenio de diseño de este proyecto. NO hay medida detrás, y por eso se "
        "declara en vez de citarse"
    ),
    "nuestro": (
        "es una decisión de este proyecto, con datos delante y con fecha. Se puede "
        "discutir; lo que no se puede es leerla como un hecho"
    ),
}


@dataclass(frozen=True)
class ThresholdSource:
    """Un umbral con su procedencia. `note` es obligatoria si no hay base medida."""

    key: str
    label: str
    value: str
    origin: str
    rationale: str
    #: Vacio salvo que el umbral NO tenga base medida. Entonces lo dice expresamente.
    no_measured_basis: str = ""

    def __post_init__(self) -> None:
        if self.origin not in ORIGINS:
            raise ValueError(
                f"Origen {self.origin!r} desconocido para {self.key!r}; los que hay son "
                f"{', '.join(ORIGINS)}. Se aborta: un origen inventado deja el umbral "
                f"sin justificar sin que se note."
            )
        if not self.rationale.strip():
            raise ValueError(
                f"El umbral {self.key!r} no dice de donde sale. Un número sin "
                f"procedencia en un informe se lee como una medida; se aborta."
            )

    @property
    def measured(self) -> bool:
        return not self.no_measured_basis

    def describe(self) -> str:
        texto = f"{self.label} = {self.value}  [{self.origin}] — {self.rationale}"
        if self.no_measured_basis:
            texto += f"  ⚠ SIN BASE MEDIDA: {self.no_measured_basis}"
        return texto


THRESHOLDS: tuple[ThresholdSource, ...] = (
    ThresholdSource(
        key="gc_min",
        label="GC mínimo de la ventana",
        value="0,30",
        origin="literatura",
        rationale=(
            "el rango de GC de las guías funcionales de RNAi es un resultado repetido en "
            "los trabajos de diseño de shRNA/siRNA: por debajo el duplex es demasiado "
            "inestable para cargar bien"
        ),
    ),
    ThresholdSource(
        key="gc_max",
        label="GC máximo de la ventana",
        value="0,55",
        origin="literatura",
        rationale=(
            "por encima el duplex es demasiado estable y la hebra no se separa; mismo "
            "cuerpo de trabajo que el mínimo"
        ),
    ),
    ThresholdSource(
        key="max_homopolymer",
        label="homopolimero máximo",
        value="4 nt",
        origin="convencion",
        rationale=(
            "carreras más largas dan problemas de síntesis y de secuenciacion, y en el "
            "casete son sustrato de deslizamiento de la polimerasa"
        ),
        no_measured_basis=(
            "el corte en 4 es un redondeo operativo, no un punto medido: 5 no es "
            "cualitativamente distinto de 4"
        ),
    ),
    ThresholdSource(
        key="min_asymmetry",
        label="asimetría mínima (proxy)",
        value="+1,0 kcal/mol",
        origin="nuestro",
        rationale=(
            "la regla de asimetría termodinamica —el extremo 5' de la guía menos estable "
            "carga preferentemente— si viene de literatura; el UMBRAL en +1,0 sobre "
            "NUESTRO proxy es nuestro. Y el proxy NO es una energía libre de duplex: es "
            "una heurística, con su aviso en `thermo.py`"
        ),
        no_measured_basis=(
            "el proxy no está calibrado contra energias medidas, así que el número "
            "ordena candidatos entre si pero no es una magnitud fisica"
        ),
    ),
    ThresholdSource(
        key="polya_flank",
        label="flanco prohibido alrededor del hexámero (eje esterico)",
        value="±10 nt",
        origin="convencion",
        rationale=(
            "es un umbral OPERATIVO para marcar solapamiento con la señal de "
            "poliadenilacion"
        ),
        no_measured_basis=(
            "NO TIENE BASE MEDIDA, y es el caso que obliga a distinguir origenes. La "
            "huella real de CPSF/CstF sobre el pre-mRNA es MAYOR que 10 nt, así que una "
            "ventana que el filtro deja pasar por 4 nt está probablemente dentro de la "
            "zona de competencia. El eje esterico es un GRADIENTE, no una frontera: "
            "cualquier umbral en nucleótidos le atribuye una precisión que la biologia "
            "no tiene. Por eso el informe emite además la SENSIBILIDAD al flanco"
        ),
    ),
)

#: Umbrales que no viven en `Thresholds` pero se imprimen igual. Misma disciplina.
OTHER_THRESHOLDS: tuple[ThresholdSource, ...] = (
    ThresholdSource(
        key="spacer_lengths",
        label="longitud de los espaciadores del intrón (5' y 3')",
        value="20 nt en 5' y 45 nt en 3'",
        origin="convencion",
        rationale=(
            "son los que lleva la construcción de hoy, y se FIJAN a propósito: con "
            "espaciador constante e intrón variable, los tres intrones son comparables. "
            "Si cada uno llevara su longitud «óptima», la matriz dejaría de ser "
            "interpretable"
        ),
        no_measured_basis=(
            "NO HAY NÚMERO QUE JUSTIFICAR, y no por no haberlo buscado: el barrido se "
            "hizo (`tools/barrer_espaciadores.py`, 0-45 nt en los dos lados, con "
            "réplicas) y NO DISCRIMINÓ. En ningún elemento el recorrido entre longitudes "
            "supera la dispersión entre secuencias de la MISMA longitud: lo que mueve la "
            "accesibilidad es la secuencia del espaciador, no su longitud. Optimizar por "
            "un criterio que no discrimina es elegir ruido, y elegir el ruido favorable "
            "es peor que no elegir. Misma categoría que el flanco de ±10 nt: nuestro, "
            "sin base medida"
        ),
    ),
    ThresholdSource(
        key="cleavage_band",
        label="banda de corte por detrás del hexámero",
        value="10-30 nt aguas abajo",
        origin="literatura",
        rationale=(
            "el corte de poliadenilación ocurre a esa distancia del hexámero; es un "
            "resultado clasico del procesamiento del extremo 3'"
        ),
    ),
    ThresholdSource(
        key="min_spacing",
        label="espaciado mínimo entre candidatos elegidos",
        value="50 nt",
        origin="nuestro",
        rationale=(
            "el espaciado compra INDEPENDENCIA ENTRE APUESTAS, no número de apuestas: "
            "las causas de fallo son regionales —un APA, un repetitivo, un tramo "
            "estructurado afectan a una región entera— así que dos candidatos pegados "
            "fallan juntos. Decidido con la tabla delante"
        ),
        no_measured_basis=(
            "50 nt no sale de ninguna medida de correlación espacial de fallos: sale de "
            "que sea claramente mayor que una ventana de 22 nt y de que deje sitio para "
            "el panel"
        ),
    ),
    ThresholdSource(
        key="seed_window",
        label="ventana de seed",
        value="posiciones 2-8",
        origin="literatura",
        rationale=(
            "la seed 2-8 es la definicion estándar del emparejamiento que dirige la "
            "represion mediada por miARN; la alternativa 2-7 también está definida y la "
            "app la ofrece, pero cambia el espacio de seeds y la tasa base"
        ),
    ),
    ThresholdSource(
        key="kozak",
        label="criterio de Kozak fuerte",
        value="purina en -3 y G en +4",
        origin="convencion",
        rationale=(
            "es el criterio que este análisis aplica para clasificar los uATG, declarado "
            "como parámetro y no citado"
        ),
        no_measured_basis=(
            "no se pondera la fuerza del contexto ni se usa ninguna matriz: es un corte "
            "binario sobre dos posiciones"
        ),
    ),
    ThresholdSource(
        key="splice_acceptor",
        label="aceptor de empalme utilizable",
        value="tracto de pirimidinas comparado con el aceptor LEGÍTIMO del mismo intrón",
        origin="nuestro",
        rationale=(
            "la comparación es contra una referencia INTERNA —el aceptor que ya funciona "
            "en ese intrón— así que el veredicto no depende de ningún umbral traido de "
            "fuera. El legítimo tiene 9 pirimidinas contiguas; el mejor críptico, 3"
        ),
    ),
    ThresholdSource(
        key="transgene_mismatches",
        label="desapareamientos que hacen FAIL contra el transgén",
        value="0 o 1",
        origin="nuestro",
        rationale=(
            "una guía a un solo desapareamiento apaga la construcción terapeutica casi "
            "igual que a su diana, y eso sería un fallo silencioso: el experimento no "
            "distinguiria «el shmiR no funciona» de «el shmiR apago su propio vector»"
        ),
    ),
    ThresholdSource(
        key="null_draws",
        label="sorteos minimos de la distribución nula (carga de off-targets)",
        value="10.000",
        origin="nuestro",
        rationale=(
            "con menos, el percentil de la COLA —que es el único número accionable— no "
            "tiene resolución"
        ),
    ),
)


def all_thresholds() -> tuple[ThresholdSource, ...]:
    return THRESHOLDS + OTHER_THRESHOLDS


def threshold(key: str) -> ThresholdSource:
    for umbral in all_thresholds():
        if umbral.key == key:
            return umbral
    raise ShmirDesignError(
        f"No hay procedencia registrada para el umbral {key!r}. Los que hay son: "
        f"{', '.join(u.key for u in all_thresholds())}. Un umbral sin justificar no se "
        f"imprime: se justifica."
    )


def unmeasured() -> tuple[ThresholdSource, ...]:
    """Los que NO tienen base medida. Van juntos y se dicen expresamente."""
    return tuple(u for u in all_thresholds() if not u.measured)
