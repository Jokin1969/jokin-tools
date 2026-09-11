"""El almacen de corridas de colision de seed. Mismo patron que `blast_store.py`.

Una corrida es un registro, no un estado: se añade, no se pisa. Y el veredicto va **por
hebra**, nunca por candidato: guia y pasajera son dos consultas y fundirlas en un solo
`seed_colision: PASS` esconderia la mitad.

La TASA BASE viaja en todos los veredictos, tambien en los `LIMPIO`: sin ella un `AVISO`
parece mas grave de lo que es, y un `LIMPIO` mas tranquilizador.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ShmirDesignError
from .identidad import (
    mensaje_de_id_repetido, registrar_del_log, result_fingerprint,
)
from .filters import FilterResult, FilterState
from .seed_scan import MIR30_NOTE, SeedScan

FILTER_NAME = "seed_colision"


@dataclass(frozen=True)
class SeedRun:
    run_id: str
    date: str
    ran_by: str
    source: str
    result_md5: str
    scan: SeedScan

    @classmethod
    def create(cls, *, run_id: str, date: str, ran_by: str, scan: SeedScan) -> "SeedRun":
        for campo, valor in (
            ("run_id", run_id), ("date", date), ("ran_by", ran_by),
        ):
            if not str(valor).strip():
                raise ValueError(
                    f"Una corrida necesita {campo}: sin el el registro no es auditable. "
                    f"Se aborta."
                )
        return cls(
            run_id=str(run_id), date=str(date), ran_by=str(ran_by),
            source=scan.source,
            result_md5=result_fingerprint(scan.raw),
            scan=scan,
        )

    @property
    def params(self):
        return self.scan.params

    @property
    def results(self):
        return self.scan.results

    @property
    def raw(self) -> str:
        return self.scan.raw

    @property
    def query_names(self) -> tuple[str, ...]:
        return tuple(r.query for r in self.scan.results)

    @property
    def organism(self) -> str:
        """El organismo del eje de esta corrida. Vacio = anterior al eje (2026-09-11)."""
        return getattr(self.scan, "organism", "") or ""

    def result_for(self, query_name: str):
        return next((r for r in self.scan.results if r.query == query_name), None)

    def verdict(self, query_name: str) -> FilterResult:
        resultado = self.result_for(query_name)
        if resultado is None:
            return FilterResult(
                name=FILTER_NAME, state=FilterState.NOT_RUN,
                reason=(
                    f"La corrida {self.run_id} no incluye {query_name}: esa hebra no se "
                    f"marco. NOT_RUN no es PASS."
                ),
            )
        estado = {
            "FAIL": FilterState.FAIL,
            "AVISO": FilterState.PASS,
            "LIMPIO": FilterState.PASS,
        }[resultado.level]
        nombres = ", ".join(c.name for c in resultado.collisions) or "ninguna"
        # EL EJE VA EN EL VEREDICTO, no sólo en la cabecera de la corrida. Es el mismo
        # criterio que puso ahí la ventana y la tasa base: la cabecera se lee una vez y
        # el veredicto se lee siempre — y además se descarga. Un `LIMPIO` sin decir
        # contra qué conjunto se leería como limpio contra los dos.
        motivo = (
            f"[{resultado.strand}] ventana {resultado.window}, heptamero "
            f"{resultado.heptamer}: {resultado.level}. Colisiones: {nombres}. "
            f"{self.scan.axis_line()} "
            f"Corrida {self.run_id} ({self.date}, {self.ran_by}) sobre {self.source}. "
            f"{self.scan.base_rate.describe()}"
        )
        if resultado.mir30:
            motivo += f" {MIR30_NOTE}"
        if not self.params.is_standard:
            motivo += (
                f" AJUSTES MODIFICADOS ({', '.join(self.params.modified())}): esta "
                f"corrida NO es la estándar y no puede leerse como tal."
            )
        return FilterResult(name=FILTER_NAME, state=estado, reason=motivo)

    def describe(self) -> list[str]:
        lineas = [
            f"CORRIDA {self.run_id} — {self.date} — corrida por {self.ran_by}",
            f"  fuente: {self.source}",
            f"  resultado md5 {self.result_md5} · {len(self.results)} consulta(s)",
        ]
        lineas.extend(f"  {l}" for l in self.params.describe())
        return lineas


@dataclass
class SeedStore:
    runs: list[SeedRun] = field(default_factory=list)
    #: Los `run_id` que el LOG traia repetidos. Se apuntan al releer y no abortan: esa
    #: linea ya esta escrita y el log es append-only (errata nº 137).
    repetidas: list[str] = field(default_factory=list)

    def add(self, run: SeedRun) -> None:
        ya = next((r for r in self.runs if r.run_id == run.run_id), None)
        if ya is not None:
            raise ShmirDesignError(mensaje_de_id_repetido(
                run_id=ya.run_id, date=ya.date, by=ya.ran_by,
                que_es="corrida de colisión de seed",
                como_repetir=(
                    "Este modal calcula, así que volver a pulsar con el mismo panel "
                    "y los mismos ajustes da el mismo resultado. Cambia lo que "
                    "quieras comparar y el id ya no choca."
                ),
            ))
        self.runs.append(run)

    def add_recorded(self, run: SeedRun) -> None:
        """La via del CARGADOR: una repetida del log se omite y se apunta, no aborta."""
        registrar_del_log(self, run)

    def history(self, query_name: str) -> tuple[SeedRun, ...]:
        return tuple(
            sorted(
                (r for r in self.runs if query_name in r.query_names),
                key=lambda r: (r.date, r.run_id),
            )
        )

    def latest(self, query_name: str, *, background: str | None = None
               ) -> SeedRun | None:
        """La ultima corrida de esa consulta, y —si se pide— CONTRA ESE ORGANISMO.

        `background=None` es «cualquiera», y lo usan las vistas que solo quieren la mas
        reciente. El VEREDICTO nunca pregunta asi: ver `verdict_for`.
        """
        historial = self.history(query_name)
        if background is not None:
            historial = tuple(
                r for r in historial if r.organism == str(background)
            )
        return historial[-1] if historial else None

    def verdict_for(self, query_name: str, *, background: str) -> FilterResult:
        """Por HEBRA **y POR ORGANISMO**. No hay `verdict_for_candidate` a proposito.

        `background` es el SLUG del organismo del eje y va SIN valor por defecto
        (principio nº 58): con uno, la corrida contra los maduros `mmu-` contestaria a la
        pregunta del paciente —y al reves— sin que nadie lo decidiera. Es el mismo
        colapso que fundir guia y pasajera, un eje mas alla. Ver
        `species.WHY_TWO_MIRNA_SETS`.

        Se llama `background` y no `organism` porque es el nombre por el que
        `presentation._store_verdict` DESPACHA —mira la firma del almacen—, y dos
        nombres para el mismo eje serian dos caminos donde hoy hay uno. Lo que nombra es
        el organismo del eje, tambien cuando ese organismo es la propia diana.
        """
        from .eje_organismo import (  # noqa: PLC0415
            exige_organismo, motivo_corridas_sin_organismo,
        )

        QUE_ES = "la colisión de seed"
        organismo = exige_organismo(background, frente=FILTER_NAME, que_es=QUE_ES)
        sin_declarar = [r for r in self.history(query_name) if not r.organism]
        ultima = self.latest(query_name, background=organismo)
        if ultima is None and sin_declarar:
            return FilterResult(
                name=FILTER_NAME, state=FilterState.NOT_RUN,
                reason=motivo_corridas_sin_organismo(
                    query_name, organismo, que_es=QUE_ES,
                ),
            )
        if ultima is None:
            return FilterResult(
                name=FILTER_NAME, state=FilterState.NOT_RUN,
                reason=(
                    f"No hay ninguna corrida de colisión de seed para {query_name} "
                    f"contra los maduros de {organismo!r}. NOT_RUN no es PASS, y no es "
                    f"LIMPIO: no haber comparado no es no haber chocado."
                ),
            )
        return ultima.verdict(query_name)
