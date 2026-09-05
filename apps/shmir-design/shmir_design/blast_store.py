"""El almacen de corridas de BLAST: inmutable, validado y sin sobrescribir.

Una corrida es un REGISTRO, no un estado. Se añade, no se pisa: una corrida nueva sobre
el mismo candidato se suma al historial y la ficha enseña la ultima. Borrar la anterior
seria perder por que se volvio a correr.

Lo que hace que esto valga algo son las cuatro reglas de aceptacion, y cada una tiene su
prueba:

  1. Un resultado con parametros NO ESTANDAR no puede presentarse como veredicto
     estandar. Los ajustes tocados VIAJAN con el registro.
  2. Un resultado cuyo md5 de consulta no coincida SE RECHAZA. Es lo que nos pasó con el
     CSV de miRarchitect: un fichero de otra corrida pegado por error, que entra y
     parece un dato.
  3. Un `-remote` NO cierra el frente. La base de NCBI cambia entre corridas.
  4. Un candidato sin corrida sigue en `NOT_RUN`, y VISIBLE. El almacen no relaja la
     regla 3: no haber corrido y haber corrido limpio no se parecen en nada.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import blast
from .errors import ShmirDesignError
from .identidad import mensaje_de_id_repetido, result_fingerprint
from .filters import FilterResult, FilterState

FILTER_NAME = "especificidad"


@dataclass(frozen=True)
class BlastDatabase:
    """Contra que se corrio. Sin procedencia no hay veredicto."""

    name: str
    version: str
    md5: str | None
    remote: bool

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("La base necesita nombre; se aborta.")
        if not self.remote and (not self.version.strip() or not self.md5):
            raise ValueError(
                f"La base local {self.name!r} necesita versión y md5: sin ellos la "
                f"corrida no es reproducible y no puede dar veredicto. Si de verdad fue "
                f"remota, marcala como tal. Se aborta."
            )

    @property
    def reproducible(self) -> bool:
        return not self.remote

    def describe(self) -> str:
        if self.remote:
            return (
                f"{self.name} vía -remote — NO REPRODUCIBLE: la base de NCBI CAMBIA "
                f"entre corridas, así que este resultado no se puede repetir y no vale "
                f"como veredicto. Es exploracion."
            )
        return (
            f"{self.name} local, versión {self.version}, md5 {self.md5} — reproducible."
        )


@dataclass(frozen=True)
class BlastRun:
    """Una corrida. Inmutable: se añade al historial, nunca se pisa."""

    run_id: str
    date: str
    uploaded_by: str
    query_md5: str
    result_md5: str
    params: blast.BlastParams
    database: BlastDatabase
    raw: str
    hits: tuple[blast.BlastHit, ...]
    query_names: tuple[str, ...] = ()
    #: `(nombre, longitud)` de cada sonda del FASTA de consulta. De aqui sale cuanto
    #: tiene que alinear un acierto para contar, y por eso viaja CON la corrida: un
    #: veredicto tiene que poder rederivarse de lo que el log guarda (errata nº 57).
    query_lengths: tuple[tuple[str, int], ...] = ()

    @classmethod
    def create(
        cls, *, run_id: str, date: str, uploaded_by: str,
        params: blast.BlastParams, database: BlastDatabase,
        query: blast.QueryFasta, raw: str,
    ) -> "BlastRun":
        for campo, valor in (
            ("run_id", run_id), ("date", date), ("uploaded_by", uploaded_by),
        ):
            if not str(valor).strip():
                raise ValueError(
                    f"Una corrida necesita {campo}: sin el, el registro no es auditable "
                    f"y no se sabe de quien viene. Se aborta."
                )
        if params.remote != database.remote:
            raise ValueError(
                f"Incoherencia: los parámetros dicen remote={params.remote} y la base "
                f"dice remote={database.remote}. Uno de los dos está mal y no se elige "
                f"por nuestra cuenta. Se aborta."
            )
        return cls(
            run_id=str(run_id), date=str(date), uploaded_by=str(uploaded_by),
            query_md5=query.md5,
            result_md5=result_fingerprint(raw),
            params=params, database=database, raw=str(raw),
            hits=blast.parse_outfmt6(raw), query_names=query.names,
            query_lengths=tuple(
                (nombre, len(secuencia)) for nombre, secuencia in query.records
            ),
        )

    @property
    def gives_verdict(self) -> bool:
        """Solo cierra el frente una corrida ESTANDAR contra una base REPRODUCIBLE."""
        return self.params.can_give_verdict and self.database.reproducible

    def hits_for(self, query_name: str) -> tuple[blast.BlastHit, ...]:
        return tuple(h for h in self.hits if h.query == query_name)

    def _judge(self, hits, *, diana, sonda, hebra, esperada):
        """El juicio, en UN SOLO SITIO. Lo llaman `verdict` y `judged_call`.

        Existe porque el informe necesita los aciertos GRAVES —para decir contra QUE gen
        acerto, que es lo unico accionable— y recalcularlos por su cuenta seria la
        segunda definicion del mismo numero: bastaria con que uno derivara el minimo de
        otra forma para que la celda y el informe dijeran cosas distintas.
        """
        from .specificity import (  # noqa: PLC0415
            ALLOWED_TRUNCATION, judge_hits,
        )

        return judge_hits(
            hits,
            target_accessions=diana,
            min_aligned=sonda - ALLOWED_TRUNCATION,
            expected_antisense=esperada,
            strand=hebra,
            probe_length=sonda if hebra is not None else None,
        )

    def judged_call(self, query_name: str, *, species: str = ""):
        """El `SpecificityCall` de esa consulta, o `None` si esta corrida no puede juzgar.

        `None` NO es «limpio»: es que aqui no hay veredicto, y quien llama lo dice.
        """
        from .presentation import strand_of  # noqa: PLC0415
        from .specificity import (  # noqa: PLC0415
            EXPECTED_ORIENTATION, target_accessions,
        )

        if not self.gives_verdict:
            return None
        hits = self.hits_for(query_name)
        try:
            diana = target_accessions(species)
        except ShmirDesignError:
            # rule2-ok: sin diana declarada no hay juicio posible, y el motivo entero ya
            # lo emite `verdict`. Aqui se devuelve `None`, que quien llama distingue.
            return None
        sondas = dict(self.query_lengths)
        implicadas = [sondas[h.query] for h in hits if h.query in sondas]
        if not implicadas:
            implicadas = [max(h.qend for h in hits)] if hits else []
        if not implicadas:
            return None
        hebra = strand_of(query_name)
        return self._judge(
            hits, diana=diana, sonda=min(implicadas), hebra=hebra,
            esperada=EXPECTED_ORIENTATION[hebra],
        )

    def verdict(
        self, query_name: str | None = None, *, species: str = "",
    ) -> FilterResult:
        """El estado del frente segun ESTA corrida. `NOT_RUN` si no puede cerrarlo.

        `species` decide QUE variantes de transcrito son la diana. Sin ella no se puede
        eximir el propio blanco, asi que la corrida sale `NO_CIERRA` con el motivo.
        """
        if not self.gives_verdict:
            motivos = self.params.why_no_verdict
            if not self.database.reproducible:
                motivos = (
                    "`-remote`: EXPLORACION, nunca veredicto. " + self.database.describe()
                    + " " + motivos
                ).strip()
            # ESTADO PROPIO, no `NOT_RUN`. Hay resultado y se puede leer; lo que pasa
            # es que no defiende un veredicto. El motivo va AQUI, en el veredicto, y no
            # en una nota al lado: quien lee la celda tiene que saber si repetir o
            # empezar.
            return FilterResult(
                name=FILTER_NAME,
                state=FilterState.NO_CIERRA,
                reason=(
                    f"Hay corrida ({self.run_id}, {self.date}) pero NO CIERRA EL FRENTE: "
                    f"{motivos} Se arregla REPITIENDO la corrida sin eso — no hay que "
                    f"volver a empezar."
                ),
            )
        from .presentation import strand_of  # noqa: PLC0415
        from .specificity import (  # noqa: PLC0415
            ALLOWED_TRUNCATION, EXPECTED_ORIENTATION, NO_TARGET_HIT_NOTE,
            WRONG_ORIENTATION_NOTE, judge_hits, target_accessions,
        )

        hits = self.hits if query_name is None else self.hits_for(query_name)
        # LA DIANA SE DECLARA Y SIN ELLA NO HAY VEREDICTO. Un gen tiene varias variantes
        # de transcrito y TODAS son la diana: sin esta lista, cada candidato fallaba
        # contra su propio blanco (errata nº 56). Si la especie no las declara, esto sale
        # `NO_CIERRA` con el motivo — nunca un `PASS` por una lista vacia.
        try:
            diana = target_accessions(species)
        except ShmirDesignError as exc:
            # rule2-ok: NO se traga nada — el motivo entero viaja DENTRO del veredicto,
            # que es donde lo lee quien mira la celda. Relanzar aqui tiraria la pagina
            # por una especie sin variantes declaradas, y el estado correcto de ese caso
            # existe y es `NO_CIERRA`: hay corrida y no puede dar veredicto.
            return FilterResult(
                name=FILTER_NAME,
                state=FilterState.NO_CIERRA,
                reason=(
                    f"Hay corrida ({self.run_id}, {self.date}) y NO PUEDE dar veredicto: "
                    f"{exc}"
                ),
            )
        # EL MINIMO SE DERIVA DE LA SONDA DE CADA CONSULTA, no se escribe: un `21` seria
        # el `> 1` otra vez, un numero con «la sonda mide 22» metido dentro. Con varias
        # consultas manda la mas corta, que no puede descartar ninguna entera.
        sondas = dict(self.query_lengths)
        implicadas = [sondas[h.query] for h in hits if h.query in sondas]
        # CORRIDAS ANTERIORES A QUE SE REGISTRARA LA SONDA. No se les niega el veredicto
        # —estan guardadas y son buenas— sino que se acota la longitud con el propio
        # resultado: `qend` nunca pasa de la sonda, y el acierto contra la diana la
        # recorre entera, asi que el maximo la clava. Si ningun acierto llegara al
        # extremo, la cota sale CORTA y el error va hacia CONTAR DE MAS, que es la
        # direccion segura. Se dice en el motivo, no se calla.
        acotada = not implicadas
        if acotada:
            implicadas = [max(h.qend for h in hits)] if hits else []
        if not implicadas:
            return FilterResult(
                name=FILTER_NAME,
                state=FilterState.NO_CIERRA,
                reason=(
                    f"Hay corrida ({self.run_id}, {self.date}) y NO PUEDE dar veredicto: "
                    f"no hay ningún acierto del que derivar cuánto tiene que alinear uno "
                    f"para contar, y ese mínimo no se escribe a mano."
                ),
            )
        # LA ORIENTACION ES UNA COMPROBACION, NO UN DESCARTE (errata nº 57). La hebra se
        # le PIDE a quien monta el nombre de la consulta.
        esperada = (
            EXPECTED_ORIENTATION[strand_of(query_name)]
            if query_name is not None else None
        )
        # Y LA HEBRA VIAJA TAMBIEN AL MINIMO DE LA PROPIA DIANA. La pasajera pierde DOS
        # posiciones de convenio contra su blanco —el bulge basal y la T forzada de la
        # posicion 1 de la guia—, asi que con el minimo de los ajenos «no acertaba contra
        # su diana» en 75 de las 88 consultas del 2026-09-05. Es otra pregunta y lleva
        # otro minimo; el de los ajenos no se afloja y los veredictos no se mueven.
        hebra = strand_of(query_name) if query_name is not None else None
        fallo = self._judge(
            hits, diana=diana, sonda=min(implicadas), hebra=hebra, esperada=esperada,
        )
        # EL MOTIVO DICE CONTRA QUE ACERTO. Antes decia `FAIL` y un recuento, asi que un
        # fallo contra la propia diana era indistinguible de uno real — y se vio en un
        # intercambio en vez de en dos segundos.
        detalle = (
            " Aciertos fuera de la diana: "
            + "; ".join(h.describe() for h in fallo.graves) + "."
            if fallo.graves else ""
        )
        exentos = (
            f" Eximidos por ser la propia diana ({', '.join(sorted(diana))}): "
            + "; ".join(h.describe() for h in fallo.exentos) + "."
            if fallo.exentos else ""
        )
        leves = (
            f" AVISO: {len(fallo.leves)} sitio(s) con 2 desapareamientos fuera de la "
            f"diana: " + "; ".join(h.describe() for h in fallo.leves) + "."
            if fallo.leves else ""
        )
        parciales = (
            f" Descartados {fallo.parciales} acierto(s) PARCIALES (alinean menos de "
            f"{min(implicadas) - ALLOWED_TRUNCATION} nt de la sonda): un parcial clavado "
            f"trae `mismatches` 0 y no es un off-target."
            + (
                " La longitud de la sonda no está registrada en esta corrida —es "
                "anterior— así que se acotó con el propio resultado; el error posible "
                "va hacia contar de más."
                if acotada else ""
            )
            if fallo.parciales else ""
        )
        orientacion = (
            f" {WRONG_ORIENTATION_NOTE} Acierto(s) afectado(s): "
            + "; ".join(h.describe() for h in fallo.orientacion_rara) + "."
            if fallo.orientacion_rara else ""
        )
        sin_diana = f" {NO_TARGET_HIT_NOTE}" if fallo.sin_diana else ""
        return FilterResult(
            name=FILTER_NAME,
            state=fallo.state,
            reason=(
                f"Corrida {self.run_id} ({self.date}, {self.uploaded_by}) sobre "
                f"{self.database.describe()} Parámetros estándar. "
                f"{len(hits)} hit(s) en total."
                f"{detalle}{exentos}{leves}{parciales}{orientacion}{sin_diana}"
                f" OJO: esto NO cubre los off-targets mediados por seed — son un frente "
                f"aparte y ningún alineador los ve."
            ),
        )

    def describe(self) -> list[str]:
        lineas = [
            f"CORRIDA {self.run_id} — {self.date} — subida por {self.uploaded_by}",
            f"  consulta md5 {self.query_md5} · resultado md5 {self.result_md5}",
            f"  base: {self.database.describe()}",
            f"  {len(self.hits)} hit(s) en el crudo, guardado sin tocar.",
        ]
        lineas.extend(f"  {l}" for l in self.params.describe())
        return lineas


def validate_upload(
    *, raw: str, query: blast.QueryFasta, declared_query_md5: str,
    panel_names,
) -> tuple[blast.BlastHit, ...]:
    """Comprueba que el resultado es DE ESTA consulta antes de dejarlo entrar.

    Dos comprobaciones, y las dos abortan:

    - el md5 del FASTA de consulta que se declara al subir tiene que ser el del FASTA
      que la app genero;
    - toda `query` del resultado tiene que estar en el panel.

    Es el fallo del CSV de miRarchitect: un fichero de otra corrida pegado por error
    entra, cuadra de forma y produce un analisis entero sobre el dato equivocado.
    """
    esperado = query.md5
    if str(declared_query_md5).strip().lower() != esperado:
        raise ShmirDesignError(
            f"El md5 del FASTA de consulta no coincide: se declara "
            f"{declared_query_md5!r} y el que genero esta app es {esperado!r}. Se "
            f"RECHAZA: casi seguro es el resultado de OTRA CORRIDA. Es exactamente lo "
            f"que pasó con el CSV de miRarchitect — un fichero ajeno que entra, cuadra "
            f"de forma y produce un análisis entero sobre el dato equivocado."
        )
    hits = blast.parse_outfmt6(raw)
    conocidos = set(panel_names)
    ajenas = sorted({h.query for h in hits} - conocidos)
    if ajenas:
        raise ShmirDesignError(
            f"El resultado trae consulta(s) que no están en el panel: "
            f"{', '.join(ajenas)}. Se RECHAZA. O el fichero es de otra corrida o el "
            f"panel cambio después de descargar el FASTA; en los dos casos hay que "
            f"volver a generar la consulta, no aceptar esto."
        )
    return hits


@dataclass
class BlastStore:
    """Historial por consulta. Nada se sobrescribe."""

    runs: list[BlastRun] = field(default_factory=list)

    def add(self, run: BlastRun) -> None:
        ya = next((r for r in self.runs if r.run_id == run.run_id), None)
        if ya is not None:
            # El id lleva el md5 del RESULTADO (errata nº 48), asi que un choque
            # significa una sola cosa y el mensaje puede DECIR COMO SALIR en vez de
            # abortar a secas.
            raise ShmirDesignError(mensaje_de_id_repetido(
                run_id=ya.run_id, date=ya.date, by=ya.uploaded_by,
                que_es="corrida de BLAST",
                como_repetir=(
                    "Casi seguro has cogido el fichero de resultados viejo: "
                    "comprueba la ruta del `-out`, o vuelve a lanzar el `blastn` y "
                    "sube ESE."
                ),
            ))
        self.runs.append(run)

    def history(self, query_name: str) -> tuple[BlastRun, ...]:
        return tuple(
            sorted(
                (r for r in self.runs if query_name in r.query_names),
                key=lambda r: (r.date, r.run_id),
            )
        )

    def latest(self, query_name: str) -> BlastRun | None:
        historial = self.history(query_name)
        return historial[-1] if historial else None

    def deciding_run(self, query_name: str):
        """La corrida que MANDA sobre este frente, y por que no es «la ultima».

        DECIDIDO (2026-09-01), planteado antes de que pasara: se sube una corrida buena y
        despues, por probar, una `-remote`. Con «manda la ultima», la exploracion tumba un
        veredicto ganado con una base local de decenas de GB.

        Y la salida NO es «manda la mejor», que esconderia una FAIL posterior — repetir
        contra una base mejor y sacar FAIL tiene que degradar. Ni borrar la anterior, que
        rompe el log.

        LA REGLA sale de que `NO_CIERRA` **no es un veredicto peor: es NINGUN veredicto**.
        Una corrida que no puede cerrar no es evidencia sobre este candidato — no habla de
        el. Asi que manda **la ultima que PUEDE dar veredicto**; entre esas, la ultima
        siempre, sea mejor o peor; y si ninguna puede, la ultima de todas con su motivo.
        """
        historial = self.history(query_name)
        if not historial:
            return None, ()
        con_veredicto = [r for r in historial if r.gives_verdict]
        if not con_veredicto:
            return historial[-1], ()
        manda = con_veredicto[-1]
        # Las que llegaron DESPUES y no pueden cerrar. No cambian el veredicto y NO se
        # callan: quien subio la ultima se quedaria creyendo que es la que cuenta.
        posteriores = tuple(
            r for r in historial[historial.index(manda) + 1:] if not r.gives_verdict
        )
        return manda, posteriores

    def verdict_for(self, query_name: str, *, species: str = "") -> FilterResult:
        """`NOT_RUN` VISIBLE cuando no hay corrida. El almacen no relaja la regla 3."""
        ultima, posteriores = self.deciding_run(query_name)
        if ultima is None:
            return FilterResult(
                name=FILTER_NAME,
                state=FilterState.NOT_RUN,
                reason=(
                    f"No hay ninguna corrida de BLAST asociada a {query_name}. "
                    f"NOT_RUN no es PASS: no haber corrido y haber corrido limpio no se "
                    f"parecen en nada, y el almacen no cambia esa disciplina."
                ),
            )
        resultado = ultima.verdict(query_name, species=species)
        if not posteriores:
            return resultado
        ids = ", ".join(r.run_id for r in posteriores)
        return FilterResult(
            name=resultado.name,
            state=resultado.state,
            reason=(
                f"{resultado.reason} Hay {len(posteriores)} corrida(s) POSTERIOR(es) que "
                f"no cierran el frente ({ids}) y por eso no mandan: una corrida que no "
                f"puede dar veredicto no es evidencia sobre este candidato. Siguen en el "
                f"historial."
            ),
        )
