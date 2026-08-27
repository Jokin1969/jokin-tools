"""El almacen de corridas de colision de seed. Mismo patron que `blast_store.py`.

Una corrida es un registro, no un estado: se añade, no se pisa. Y el veredicto va **por
hebra**, nunca por candidato: guia y pasajera son dos consultas y fundirlas en un solo
`seed_colision: PASS` esconderia la mitad.

La TASA BASE viaja en todos los veredictos, tambien en los `LIMPIO`: sin ella un `AVISO`
parece mas grave de lo que es, y un `LIMPIO` mas tranquilizador.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .errors import ShmirDesignError
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
            result_md5=hashlib.md5(scan.raw.encode("utf-8")).hexdigest(),
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
        motivo = (
            f"[{resultado.strand}] ventana {resultado.window}, heptamero "
            f"{resultado.heptamer}: {resultado.level}. Colisiones: {nombres}. "
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

    def add(self, run: SeedRun) -> None:
        if any(r.run_id == run.run_id for r in self.runs):
            raise ShmirDesignError(
                f"Ya hay una corrida de seed con id {run.run_id!r}. Nada se sobrescribe: "
                f"una corrida nueva se AÑADE con su propio id. Se aborta."
            )
        self.runs.append(run)

    def history(self, query_name: str) -> tuple[SeedRun, ...]:
        return tuple(
            sorted(
                (r for r in self.runs if query_name in r.query_names),
                key=lambda r: (r.date, r.run_id),
            )
        )

    def latest(self, query_name: str) -> SeedRun | None:
        historial = self.history(query_name)
        return historial[-1] if historial else None

    def verdict_for(self, query_name: str) -> FilterResult:
        """Por HEBRA. No hay `verdict_for_candidate` a proposito."""
        ultima = self.latest(query_name)
        if ultima is None:
            return FilterResult(
                name=FILTER_NAME, state=FilterState.NOT_RUN,
                reason=(
                    f"No hay ninguna corrida de colisión de seed para {query_name}. "
                    f"NOT_RUN no es PASS."
                ),
            )
        return ultima.verdict(query_name)
