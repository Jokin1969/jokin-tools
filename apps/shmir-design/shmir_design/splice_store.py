"""El almacen de corridas del cuarto modal. Mismo patron que los otros tres.

Una corrida es un registro, no un estado: se añade, no se pisa. Repetir un `run_id`
aborta.

Y comparte con la carga de off-targets la propiedad que mas importa: **este frente NO
PUEDE devolver FAIL.** Es DESEMPATE Y ALERTA, no filtro. Ninguno de los dos analisis del
modal —prediccion de sitios y accesibilidad estructural— puede excluir un candidato; lo
que pueden hacer es señalar que una construccion tiene un perfil peor que sus hermanas.
Asi que el veredicto solo tiene dos formas: `NOT_RUN` (no se ha consultado) o `PASS` (se
ha consultado, y aqui esta el numero). Hay un test que lo fija.

**El veredicto va por PAR candidato x intron**, no por candidato: la unidad de analisis de
este modal es el par, y colapsarlo perderia justo lo que se quiere comparar — el mismo
modulo dentro de dos intrones distintos.

Y con el numero viajan siempre: el REFERENTE interno (el legitimo del mismo intron en la
misma corrida), la VENTANA DE CONTEXTO declarada, y el aviso de que las puntuaciones
absolutas de este modelo no son interpretables sobre un cassette de AAV.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ShmirDesignError
from .identidad import mensaje_de_id_repetido, result_fingerprint
from .filters import FilterResult, FilterState
from .spliceai import (
    NO_ABSOLUTE_THRESHOLD,
    RELATIVE_ONLY,
    USE_NOTE,
    SpliceScan,
)

FILTER_NAME = "empalme_sitios"


@dataclass(frozen=True)
class SpliceRun:
    run_id: str
    date: str
    ran_by: str
    #: Con que se consulto, para poder repetirlo.
    executor: str
    result_md5: str
    scan: SpliceScan
    raw: str
    #: El plegado del intron, por par. Va JUNTO en la corrida y SEPARADO en el
    #: resultado: prediccion de sitios y accesibilidad estructural son dos preguntas.
    folding: dict = field(default_factory=dict)

    @classmethod
    def create(cls, *, run_id: str, date: str, ran_by: str, executor: str,
               scan: SpliceScan, raw: str, folding=None) -> "SpliceRun":
        for campo, valor in (
            ("run_id", run_id), ("date", date), ("ran_by", ran_by),
            ("executor", executor),
        ):
            if not str(valor).strip():
                raise ValueError(
                    f"Una corrida necesita {campo}: sin el el registro no es auditable. "
                    f"Se aborta."
                )
        return cls(
            run_id=str(run_id), date=str(date), ran_by=str(ran_by),
            executor=str(executor),
            result_md5=result_fingerprint(raw),
            scan=scan, raw=raw, folding=dict(folding or {}),
        )

    def verdict(self, candidate_start: int, intron: str) -> FilterResult:
        par = self.scan.for_candidate(candidate_start, intron)
        if par is None:
            return FilterResult(
                name=FILTER_NAME, state=FilterState.NOT_RUN,
                reason=(
                    f"La corrida {self.run_id} no incluye el par 3utr:{candidate_start} "
                    f"x {intron}: ese cassette no se consulto. NOT_RUN no es PASS."
                ),
            )
        mejor = par.best_cryptic
        cifra = (
            f"mejor críptico {mejor.fraction:.0%} del legítimo "
            f"(construccion:{mejor.position}, {mejor.kind})"
            if mejor is not None
            else "ningún críptico llega al umbral relativo"
        )
        conocido = (
            f" GTGAGCG: {par.known_cryptic.fraction:.0%} del legítimo."
            if par.known_cryptic is not None
            else " GTGAGCG: sin puntuar en este resultado."
        )
        plegado = self.folding.get((candidate_start, intron))
        estructura = ""
        if plegado is not None:
            estructura = (
                " ACCESIBILIDAD ESTRUCTURAL (análisis APARTE, número propio): "
                + ", ".join(f"{k} {v:.2f}" for k, v in sorted(plegado.items()))
                + "."
            )
        motivo = (
            f"[3utr:{candidate_start} x {intron}] REFERENTE INTERNO: donante legítimo "
            f"{par.legit_donor:.3f}, aceptor {par.legit_acceptor:.3f}. {cifra}."
            f"{conocido} Contexto declarado {par.context_5}/{par.context_3} nt. "
            f"Corrida {self.run_id} ({self.date}, {self.ran_by}, {self.executor}). "
            f"{NO_ABSOLUTE_THRESHOLD} {RELATIVE_ONLY} {USE_NOTE}{estructura}"
        )
        # PASS, nunca FAIL. Ver el docstring del modulo.
        return FilterResult(name=FILTER_NAME, state=FilterState.PASS, reason=motivo)

    def describe(self) -> list[str]:
        lineas = [
            f"CORRIDA {self.run_id} — {self.date} — corrida por {self.ran_by}",
            f"  ejecutor: {self.executor}",
            f"  resultado md5 {self.result_md5} · {len(self.scan.pairs)} par(es) "
            f"candidato x intrón",
        ]
        for par in self.scan.pairs:
            lineas.extend(f"  {l}" for l in par.describe())
        return lineas


@dataclass
class SpliceStore:
    """Inmutable: nada se sobrescribe. Repetir un `run_id` aborta."""

    #: Lo unico que este frente puede devolver. Hay un test que lo fija.
    POSSIBLE_VERDICTS = (FilterState.NOT_RUN, FilterState.PASS)

    runs: list[SpliceRun] = field(default_factory=list)

    def add(self, run: SpliceRun) -> None:
        ya = next((r for r in self.runs if r.run_id == run.run_id), None)
        if ya is not None:
            raise ShmirDesignError(mensaje_de_id_repetido(
                run_id=ya.run_id, date=ya.date, by=ya.ran_by,
                que_es="corrida de empalme",
                como_repetir=(
                    "Casi seguro has cogido el resultado viejo de SpliceAI: "
                    "comprueba el fichero, o vuelve a correrlo y sube ESE."
                ),
            ))
        self.runs.append(run)

    @property
    def latest(self) -> SpliceRun | None:
        return self.runs[-1] if self.runs else None

    def verdict_for(self, candidate_start: int, intron: str) -> FilterResult:
        """El veredicto del par. Sin corrida, NOT_RUN — nunca FAIL."""
        ultima = self.latest
        if ultima is None:
            return FilterResult(
                name=FILTER_NAME, state=FilterState.NOT_RUN,
                reason=(
                    f"No hay ninguna corrida de predicción de sitios de splicing para "
                    f"3utr:{candidate_start} x {intron}. NOT_RUN no es PASS: no se ha "
                    f"consultado, que no es lo mismo que salir limpio."
                ),
            )
        return ultima.verdict(candidate_start, intron)

    def history(self) -> list[str]:
        lineas: list[str] = []
        for corrida in self.runs:
            lineas.extend(corrida.describe())
            lineas.append("")
        return lineas
