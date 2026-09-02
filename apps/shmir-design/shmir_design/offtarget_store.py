"""El almacen de corridas de carga de off-targets. Mismo patron que los otros dos.

Una corrida es un registro, no un estado: se añade, no se pisa. El veredicto va **por
hebra**, nunca por candidato — igual que en la colision de seed, y por la misma razon.

Y una diferencia que no tienen los otros dos: **este frente no puede devolver FAIL**.
Es DESEMPATE, no filtro. Un percentil alto es motivo para preferir a otro entre dos que
empatan, jamas para excluir a nadie, asi que el veredicto solo tiene dos formas posibles:
NOT_RUN (no se ha contado) o PASS (se ha contado, y aqui esta el numero). Hay un test que
lo fija.

Con el numero viajan siempre tres cosas, porque sin ellas no es interpretable: el
PERCENTIL contra la nula, el aviso de LIMITE SUPERIOR y el estado de la auditoria de
isoformas del fichero.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ShmirDesignError
from .identidad import mensaje_de_id_repetido, result_fingerprint
from .filters import FilterResult, FilterState
from .offtarget import (
    MISSING_FILE,
    SITE_CLASSES,
    UPPER_BOUND_NOTE,
    USE_NOTE,
    OfftargetScan,
)

FILTER_NAME = "offtarget_seed"


@dataclass(frozen=True)
class OfftargetRun:
    run_id: str
    date: str
    ran_by: str
    source: str
    result_md5: str
    scan: OfftargetScan

    @classmethod
    def create(cls, *, run_id: str, date: str, ran_by: str,
               scan: OfftargetScan) -> "OfftargetRun":
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

    def result_for(self, query_name: str):
        return next((r for r in self.scan.results if r.query == query_name), None)

    def verdict(self, query_name: str) -> FilterResult:
        resultado = self.result_for(query_name)
        if resultado is None:
            return FilterResult(
                name=FILTER_NAME, state=FilterState.NOT_RUN,
                reason=(
                    f"La corrida {self.run_id} no incluye {query_name}: esa hebra no se "
                    f"conto. NOT_RUN no es PASS y NO ES CERO."
                ),
            )
        cifras = "  ".join(
            f"{clase}={resultado.counts.sites[clase]} "
            f"(p{resultado.percentiles[clase]:.1f}, "
            f"{resultado.counts.transcripts[clase]} transcrito(s))"
            for clase in SITE_CLASSES
        )
        autoconteo = self.scan.self_counts.get(query_name)
        motivo = (
            f"[{resultado.strand}] seed {resultado.patterns.heptamer}: {cifras}. "
            f"Las cuatro clases van SEPARADAS y no se suman. "
            f"Corrida {self.run_id} ({self.date}, {self.ran_by}) sobre {self.source}, "
            f"ensamblaje {self.scan.provenance.assembly}, tabla "
            f"{self.scan.provenance.table} ({self.scan.provenance.table_date}). "
            f"{self.scan.audit.warning()} "
            f"{UPPER_BOUND_NOTE} {USE_NOTE}"
        )
        if autoconteo is not None and autoconteo.anomalous:
            motivo += f" AUTOCONTEO: {autoconteo.describe()}"
        if not self.params.is_standard:
            motivo += (
                f" AJUSTES MODIFICADOS ({', '.join(self.params.modified())}): esta "
                f"corrida NO es la estándar y su percentil no es comparable con el de "
                f"una que si lo sea."
            )
        # PASS, nunca FAIL: este frente no excluye a nadie. Ver el docstring del modulo.
        return FilterResult(name=FILTER_NAME, state=FilterState.PASS, reason=motivo)

    def describe(self) -> list[str]:
        lineas = [
            f"CORRIDA {self.run_id} — {self.date} — corrida por {self.ran_by}",
            f"  fuente: {self.source}",
            f"  resultado md5 {self.result_md5} · {len(self.results)} consulta(s)",
        ]
        lineas.extend(f"  {l}" for l in self.scan.provenance.describe())
        lineas.extend(f"  {l}" for l in self.params.describe())
        return lineas


@dataclass
class OfftargetStore:
    """Historial por consulta. Nada se sobrescribe."""

    runs: list[OfftargetRun] = field(default_factory=list)

    def add(self, run: OfftargetRun) -> None:
        ya = next((r for r in self.runs if r.run_id == run.run_id), None)
        if ya is not None:
            raise ShmirDesignError(mensaje_de_id_repetido(
                run_id=ya.run_id, date=ya.date, by=ya.ran_by,
                que_es="corrida de carga de off-targets",
                como_repetir=(
                    "Este modal calcula, así que con el mismo panel, los mismos "
                    "ajustes y la misma semilla sale lo mismo. Cambia lo que quieras "
                    "comparar y el id ya no choca."
                ),
            ))
        self.runs.append(run)

    def history(self, query_name: str) -> tuple[OfftargetRun, ...]:
        return tuple(
            sorted(
                (r for r in self.runs if query_name in r.query_names),
                key=lambda r: (r.date, r.run_id),
            )
        )

    def latest(self, query_name: str) -> OfftargetRun | None:
        historial = self.history(query_name)
        return historial[-1] if historial else None

    def verdict_for(self, query_name: str) -> FilterResult:
        """Por HEBRA. No hay `verdict_for_candidate`, igual que en la colision."""
        ultima = self.latest(query_name)
        if ultima is None:
            return FilterResult(
                name=FILTER_NAME, state=FilterState.NOT_RUN,
                reason=(
                    f"No hay ninguna corrida de carga de off-targets para {query_name}. "
                    f"Falta `{MISSING_FILE}`. NOT_RUN no es PASS, y sobre todo NO ES "
                    f"CERO: no haber contado cuántos mensajeros llevan esta seed no es "
                    f"lo mismo que no llevarla ninguno."
                ),
            )
        return ultima.verdict(query_name)
