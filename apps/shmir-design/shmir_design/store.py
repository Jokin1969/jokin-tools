"""Persistencia: un proyecto en disco, en TEXTO, y append-only de verdad.

DECISION DE ARQUITECTURA (2026-08-26), y va antes que los modales para que los tres
guarden en el mismo sitio:

    data/proyectos/<slug>/proyecto.json    la entrada: md5, longitud, especie, anatomia
    data/proyectos/<slug>/registro.jsonl   el log APPEND-ONLY de todo lo demas

**Por que JSONL y no SQLite**, que tambien es stdlib y tambien sobrevive a la sesion:
este proyecto ya decidio que el manifiesto va en texto y versionado porque «un veredicto
no es auditable dentro de un año» si no se puede leer con `cat`. Un `.db` binario no se
diffea, no se grepea y no se lee sin la app — y el registro de un veredicto tiene que
sobrevivir a la app que lo escribio. Si algun dia hacen falta consultas de verdad,
SQLite se construye DESDE este log; al reves no.

**Un solo directorio y un solo log por proyecto.** Si cada modal abriera el suyo, la
ficha tendria que buscar en tres sitios y el dia que se añada un cuarto modal se
quedaria fuera sin que nadie lo note. Es la misma leccion de `offtarget_seed`: un frente
que no se ve no existe.

**El «nada se sobrescribe» deja de ser una convencion**: cada linea lleva el md5 de la
anterior, asi que editar o borrar una linea vieja rompe la cadena y `verify()` lo dice,
con el numero de linea.

Python 3.11+, solo `json`, `hashlib` y `pathlib` (regla 6).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ShmirDesignError

PROJECT_FILE = "proyecto.json"
LOG_FILE = "registro.jsonl"

#: Los tipos de registro. CERRADO a proposito: si cada modal se inventa su etiqueta, el
#: log deja de poder leerse sin saber quien lo escribio.
RECORD_KINDS = (
    "corrida_blast",      # modal de especificidad
    "corrida_seed",       # modal de colision de seed
    "corrida_offtarget",  # modal de carga de off-targets por seed
    "corrida_empalme",    # modal de prediccion de sitios de splicing (el cuarto)
    "seleccion",          # candidatos elegidos a mano
    "descarte",           # candidatos descartados a mano
    "veredicto",          # un frente cerrado con su procedencia
    "nota",               # texto libre del responsable, fechado
)

WHAT_THE_CHAIN_DOES_NOT_DO = (
    "La cadena de md5 NO IMPIDE editar el log —nada lo impide, es un fichero— y no "
    "pretende impedirlo. Lo que hace es volverlo VISIBLE: `verify()` recalcula la cadena "
    "y aborta diciendo en que línea se rompe. Es la misma disciplina que el md5 del "
    "manifiesto: no evita que alguien cambie un fichero, evita que el cambio pase "
    "inadvertido."
)

#: Lo que deja de ser fiable cuando la anatomia no se pudo resolver.
UNRELIABLE_NOTE = (
    "Sin anatomía no se sabe donde empieza el 3'UTR, así que TODO lo que dependa de esa "
    "frontera queda NO_FIABLE: los tercios, las etiquetas proximal/medio/distal y las "
    "zonas de polyA —incluida la distancia al extremo 3', que es la que decide si una "
    "señal es terminal—. Los filtros de secuencia (GC, homopolimero, asimetría, G4) no "
    "dependen de ella y siguen valiendo."
)


@dataclass(frozen=True)
class Project:
    slug: str
    created: str
    sequence_md5: str
    sequence_length: int
    species: str
    anatomy: dict | None
    anatomy_source: str

    @property
    def reliable(self) -> bool:
        """¿Se sabe donde empieza el 3'UTR? Si no, medio informe es NO_FIABLE."""
        return bool(self.anatomy) and self.anatomy_source != "sin_resolver"

    @property
    def why_unreliable(self) -> str:
        return "" if self.reliable else UNRELIABLE_NOTE

    def as_dict(self) -> dict:
        return {
            "slug": self.slug,
            "created": self.created,
            "sequence_md5": self.sequence_md5,
            "sequence_length": self.sequence_length,
            "species": self.species,
            "anatomy": self.anatomy,
            "anatomy_source": self.anatomy_source,
        }

    def describe(self) -> list[str]:
        lineas = [
            f"Proyecto {self.slug} — creado {self.created}",
            f"  entrada: {self.sequence_length} nt / md5 {self.sequence_md5}",
            f"  especie: {self.species or 'SIN DECLARAR'}",
            f"  anatomía: {self.anatomy_source}"
            + ("" if self.reliable else "  ← NO_FIABLE"),
        ]
        if not self.reliable:
            lineas.append(f"  {self.why_unreliable}")
        return lineas


@dataclass(frozen=True)
class Record:
    seq: int
    kind: str
    date: str
    payload: dict
    prev_md5: str
    md5: str

    def as_dict(self) -> dict:
        return {
            "seq": self.seq, "kind": self.kind, "date": self.date,
            "payload": self.payload, "prev_md5": self.prev_md5, "md5": self.md5,
        }


def _line_md5(seq: int, kind: str, date: str, payload: dict, prev: str) -> str:
    cuerpo = json.dumps(
        {"seq": seq, "kind": kind, "date": date, "payload": payload, "prev_md5": prev},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.md5(cuerpo.encode("utf-8")).hexdigest()


@dataclass
class ProjectStore:
    root: Path
    project: Project
    _records: list[Record] = field(default_factory=list)

    # ── crear / abrir ────────────────────────────────────────────────────────
    @classmethod
    def create(
        cls, base: Path | str, *, slug: str, sequence: str, species: str,
        anatomy: dict | None, anatomy_source: str, created: str,
    ) -> "ProjectStore":
        raiz = Path(base) / slug
        if raiz.exists():
            raise ShmirDesignError(
                f"El proyecto {slug!r} ya existe en {raiz}. No se sobrescribe: si es "
                f"otra corrida, va con otro slug; si es la misma, se abre con `open()`. "
                f"Se aborta."
            )
        limpia = "".join(str(sequence).split()).upper()
        if not limpia:
            raise ShmirDesignError(
                "Un proyecto necesita su secuencia de entrada: sin ella no hay md5 que "
                "guardar y el proyecto no identifica nada. Se aborta (regla 1)."
            )
        raiz.mkdir(parents=True)
        proyecto = Project(
            slug=slug, created=created,
            sequence_md5=hashlib.md5(limpia.encode("ascii")).hexdigest(),
            sequence_length=len(limpia), species=species,
            anatomy=anatomy, anatomy_source=anatomy_source,
        )
        (raiz / PROJECT_FILE).write_text(
            json.dumps(proyecto.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (raiz / LOG_FILE).write_text("", encoding="utf-8")
        return cls(root=raiz, project=proyecto)

    @classmethod
    def open(cls, base: Path | str, slug: str) -> "ProjectStore":
        raiz = Path(base) / slug
        fichero = raiz / PROJECT_FILE
        if not fichero.is_file():
            raise ShmirDesignError(
                f"No hay ningún proyecto {slug!r} en {raiz}: falta {PROJECT_FILE}. Se "
                f"aborta en vez de crear uno vacío que parezca el de antes."
            )
        try:
            crudo = json.loads(fichero.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ShmirDesignError(
                f"{fichero} no es JSON válido ({exc}); se aborta la apertura del "
                f"proyecto en vez de seguir con los campos que se hayan podido leer."
            ) from exc
        almacen = cls(root=raiz, project=Project(**crudo))
        almacen._load()
        return almacen

    # ── el log ───────────────────────────────────────────────────────────────
    @property
    def project_path(self) -> Path:
        return self.root / PROJECT_FILE

    @property
    def log_path(self) -> Path:
        return self.root / LOG_FILE

    def _load(self) -> None:
        self._records = []
        texto = self.log_path.read_text(encoding="utf-8") if self.log_path.is_file() else ""
        for numero, linea in enumerate(texto.splitlines(), start=1):
            if not linea.strip():
                continue
            try:
                crudo = json.loads(linea)
            except json.JSONDecodeError as exc:
                raise ShmirDesignError(
                    f"{self.log_path}, línea {numero}: no es JSON válido ({exc}); se "
                    f"aborta la lectura del registro."
                ) from exc
            self._records.append(Record(**crudo))

    def append(self, kind: str, payload: dict, *, date: str) -> Record:
        """Añade un registro. Nunca sobrescribe: el fichero se abre en modo `a`."""
        if kind not in RECORD_KINDS:
            raise ValueError(
                f"Tipo de registro {kind!r} desconocido; los que hay son "
                f"{', '.join(RECORD_KINDS)}. Se aborta: si cada modal se inventa su "
                f"etiqueta, el log deja de poder leerse sin saber quien lo escribio."
            )
        if not str(date).strip():
            raise ValueError("Un registro necesita fecha; se aborta.")
        try:
            json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except TypeError as exc:
            raise ShmirDesignError(
                f"El contenido del registro {kind!r} no es serializable a JSON ({exc}); "
                f"se aborta en vez de escribir una línea que luego no se pueda leer."
            ) from exc

        anterior = self._records[-1].md5 if self._records else ""
        seq = len(self._records) + 1
        registro = Record(
            seq=seq, kind=kind, date=str(date), payload=payload,
            prev_md5=anterior, md5=_line_md5(seq, kind, str(date), payload, anterior),
        )
        with self.log_path.open("a", encoding="utf-8") as salida:
            salida.write(
                json.dumps(registro.as_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            )
        self._records.append(registro)
        return registro

    def records(self, kind: str | None = None) -> tuple[Record, ...]:
        if kind is not None and kind not in RECORD_KINDS:
            raise ValueError(f"Tipo {kind!r} desconocido; se aborta.")
        return tuple(r for r in self._records if kind is None or r.kind == kind)

    def verify(self) -> None:
        """Recalcula la cadena. Aborta diciendo EN QUE LINEA se rompe."""
        anterior = ""
        for indice, registro in enumerate(self._records, start=1):
            esperado = _line_md5(
                registro.seq, registro.kind, registro.date, registro.payload, anterior
            )
            if registro.seq != indice:
                raise ShmirDesignError(
                    f"{self.log_path}: la cadena está rota en la línea {indice} — el "
                    f"registro dice ser el nº {registro.seq}. Falta una línea o se "
                    f"reordenaron. {WHAT_THE_CHAIN_DOES_NOT_DO}"
                )
            if registro.prev_md5 != anterior or registro.md5 != esperado:
                raise ShmirDesignError(
                    f"{self.log_path}: la cadena está rota en la línea {indice}. El "
                    f"contenido de esa línea o de una anterior ha cambiado después de "
                    f"escribirse. {WHAT_THE_CHAIN_DOES_NOT_DO}"
                )
            anterior = registro.md5

    def describe(self) -> list[str]:
        lineas = list(self.project.describe())
        lineas.append(f"  registro: {len(self._records)} entrada(s) en {self.log_path}")
        por_tipo: dict[str, int] = {}
        for registro in self._records:
            por_tipo[registro.kind] = por_tipo.get(registro.kind, 0) + 1
        for tipo in RECORD_KINDS:
            if tipo in por_tipo:
                lineas.append(f"    {tipo:<16} {por_tipo[tipo]}")
        return lineas


# ─── Adaptadores: los modales guardan AQUI, no cada uno en el suyo ───────────
#
# `BlastStore` y `SeedStore` siguen siendo lo que eran —el historial en memoria de una
# sesion— y ganan durabilidad por aqui. Lo que NO se hace es que cada uno abra su
# fichero: un solo log por proyecto, o el dia que se añada un cuarto modal la ficha se
# dejaria uno fuera sin que nadie lo note.


def save_blast_run(store: ProjectStore, run) -> Record:
    """Persiste una corrida de BLAST en el log del proyecto."""
    return store.append(
        "corrida_blast",
        {
            "run_id": run.run_id,
            "uploaded_by": run.uploaded_by,
            "query_md5": run.query_md5,
            "result_md5": run.result_md5,
            "query_names": list(run.query_names),
            "params": {
                campo: getattr(run.params, campo)
                for campo in (
                    "task", "word_size", "evalue", "dust", "outfmt", "db",
                    "entrez_query", "include_predicted", "remote",
                )
            },
            "database": {
                "name": run.database.name, "version": run.database.version,
                "md5": run.database.md5, "remote": run.database.remote,
            },
            "raw": run.raw,
        },
        date=run.date,
    )


def load_blast_store(store: ProjectStore):
    """Reconstruye el `BlastStore` desde el log. Con los parametros TAL CUAL se usaron.

    Si al recargar se perdiera un ajuste modificado, un veredicto no estandar pasaria
    por estandar — que es justo lo que el modal existe para impedir.
    """
    from .blast import BlastParams, QueryFasta
    from .blast_store import BlastDatabase, BlastRun, BlastStore

    almacen = BlastStore()
    for registro in store.records("corrida_blast"):
        datos = registro.payload
        # El FASTA de consulta no se guarda entero: lo que identifica la corrida es su
        # md5, y ese si esta. Se reconstruye un objeto con los mismos nombres y md5.
        consulta = _QueryEcho(
            md5=datos["query_md5"], names=tuple(datos["query_names"])
        )
        almacen.add(
            BlastRun(
                run_id=datos["run_id"], date=registro.date,
                uploaded_by=datos["uploaded_by"], query_md5=datos["query_md5"],
                result_md5=datos["result_md5"],
                params=BlastParams(**datos["params"]),
                database=BlastDatabase(**datos["database"]),
                raw=datos["raw"],
                hits=_parse(datos["raw"]),
                query_names=consulta.names,
            )
        )
    return almacen


def _parse(raw: str):
    from .blast import parse_outfmt6

    return parse_outfmt6(raw)


@dataclass(frozen=True)
class _QueryEcho:
    """Lo minimo de una consulta que hace falta para volver a leer una corrida."""

    md5: str
    names: tuple[str, ...]


def save_seed_run(store: ProjectStore, run) -> Record:
    """Persiste una corrida de colision de seed."""
    return store.append(
        "corrida_seed",
        {
            "run_id": run.run_id,
            "ran_by": run.ran_by,
            "source": run.source,
            "result_md5": run.result_md5,
            # El md5 del fichero de maduros va como CAMPO, no dentro de `source`.
            # Es lo que hace comparable una corrida vieja con el fichero de hoy; ver
            # `insumos.CONSUMIDOS`.
            "mature_md5": run.scan.mature_md5,
            "mature_version": run.scan.mature_version,
            "params": {
                "window": run.params.window,
                "species_prefix": run.params.species_prefix,
                "level": run.params.level,
            },
            "raw": run.raw,
            "results": [
                {
                    "start": r.start, "strand": r.strand, "query": r.query,
                    "sequence": r.sequence, "heptamer": r.heptamer,
                    "window": r.window, "level": r.level,
                    "collisions": [
                        {"name": c.name, "core": c.core, "mir30": c.mir30}
                        for c in r.collisions
                    ],
                }
                for r in run.results
            ],
            "base_rate": {
                "matures": run.scan.base_rate.matures,
                "distinct": run.scan.base_rate.distinct,
                "space": run.scan.base_rate.space,
                "window": run.scan.base_rate.window,
                "species_prefix": run.scan.base_rate.species_prefix,
            },
        },
        date=run.date,
    )


def load_seed_store(store: ProjectStore):
    """Reconstruye el `SeedStore` desde el log, con la ventana de cada resultado."""
    from .seed_scan import BaseRate, SeedCollision, SeedParams, SeedResult, SeedScan
    from .seed_store import SeedRun, SeedStore

    almacen = SeedStore()
    for registro in store.records("corrida_seed"):
        datos = registro.payload
        resultados = tuple(
            SeedResult(
                start=r["start"], strand=r["strand"], query=r["query"],
                sequence=r["sequence"], heptamer=r["heptamer"], window=r["window"],
                level=r["level"],
                collisions=tuple(
                    SeedCollision(name=c["name"], core=c["core"], mir30=c["mir30"])
                    for c in r["collisions"]
                ),
            )
            for r in datos["results"]
        )
        scan = SeedScan(
            params=SeedParams(**datos["params"]), source=datos["source"],
            results=resultados, base_rate=BaseRate(**datos["base_rate"]),
            raw=datos["raw"],
            # `.get` con "" para las corridas escritas ANTES de que este campo
            # existiera: la cadena vacia se lee como «la corrida no lo guardo», que es
            # lo que `insumos.obsoleta` distingue de «no coincide». Convertirla en un
            # md5 inventado seria peor que no tenerla.
            mature_md5=datos.get("mature_md5", ""),
            mature_version=datos.get("mature_version", ""),
        )
        almacen.add(
            SeedRun(
                run_id=datos["run_id"], date=registro.date, ran_by=datos["ran_by"],
                source=datos["source"], result_md5=datos["result_md5"], scan=scan,
            )
        )
    return almacen


def _null_to_json(null) -> dict:
    """La nula va como HISTOGRAMA, no como 10.000 numeros por clase.

    Es exacto —el percentil se recalcula igual— y deja el log legible con `cat`, que es
    la razon por la que se eligio JSONL y no un `.db`. Guardar los sorteos uno a uno
    harian 40.000 enteros por corrida y el fichero dejaria de poder leerse.
    """
    from collections import Counter

    return {
        "draws": null.draws,
        "seed": null.seed,
        "criterion": null.criterion,
        "distinct_heptamers": list(null.distinct_heptamers),
        "histograms": {
            clase: {str(v): n for v, n in sorted(Counter(valores).items())}
            for clase, valores in null.by_class.items()
        },
    }


def _null_from_json(datos: dict):
    from .offtarget import Null

    por_clase = {}
    for clase, histograma in datos["histograms"].items():
        valores: list[int] = []
        for texto, n in histograma.items():
            valores.extend([int(texto)] * int(n))
        por_clase[clase] = tuple(sorted(valores))
    return Null(
        draws=datos["draws"], seed=datos["seed"], criterion=datos["criterion"],
        by_class=por_clase,
        distinct_heptamers=tuple(datos["distinct_heptamers"]),
    )


def save_offtarget_run(store: ProjectStore, run) -> Record:
    """Persiste una corrida de carga de off-targets por seed."""
    scan = run.scan
    return store.append(
        "corrida_offtarget",
        {
            "run_id": run.run_id,
            "ran_by": run.ran_by,
            "source": run.source,
            "result_md5": run.result_md5,
            # Esta corrida consume DOS ficheros: el catalogo (`provenance.md5`) y el
            # de maduros. Ver `insumos.CONSUMIDOS`.
            "mature_md5": scan.mature_md5,
            "mature_version": scan.mature_version,
            "params": {
                "null_draws": scan.params.null_draws,
                "null_seed": scan.params.null_seed,
                "species_prefix": scan.params.species_prefix,
            },
            "provenance": {
                "source": scan.provenance.source,
                "assembly": scan.provenance.assembly,
                "table": scan.provenance.table,
                "table_date": scan.provenance.table_date,
                "representative": scan.provenance.representative,
                "version": scan.provenance.version,
                "md5": scan.provenance.md5,
            },
            "audit": {
                "records": scan.audit.records,
                "distinct_ids": scan.audit.distinct_ids,
                "repeated_ids": [list(x) for x in scan.audit.repeated_ids],
                "duplicate_sequence_groups": scan.audit.duplicate_sequence_groups,
                "records_in_duplicates": scan.audit.records_in_duplicates,
                "genes": scan.audit.genes,
                "multi_isoform_genes": [
                    list(x) for x in scan.audit.multi_isoform_genes
                ],
            },
            "results": [
                {
                    "start": r.start, "strand": r.strand, "query": r.query,
                    "sequence": r.sequence, "heptamer": r.patterns.heptamer,
                    "sites": r.counts.sites, "transcripts": r.counts.transcripts,
                    "percentiles": r.percentiles,
                }
                for r in scan.results
            ],
            "controls": [
                {"name": c.name, "heptamer": c.heptamer, "sites": c.sites}
                for c in scan.controls
            ],
            "self_counts": {
                consulta: {
                    "target_label": s.target_label,
                    "occurrences": s.occurrences,
                    "sites": s.sites,
                }
                for consulta, s in scan.self_counts.items()
            },
            "nulls": {
                clave: _null_to_json(nula) for clave, nula in scan.nulls.items()
            },
            "raw": scan.raw,
        },
        date=run.date,
    )


def load_offtarget_store(store: ProjectStore):
    """Reconstruye el `OfftargetStore` desde el log, percentiles incluidos."""
    from .offtarget import (
        Control,
        Counts,
        IsoformAudit,
        LoadResult,
        OfftargetParams,
        OfftargetScan,
        Provenance,
        SelfCount,
        patterns_from_heptamer,
    )
    from .offtarget_store import OfftargetRun, OfftargetStore

    almacen = OfftargetStore()
    for registro in store.records("corrida_offtarget"):
        datos = registro.payload
        auditoria = dict(datos["audit"])
        auditoria["repeated_ids"] = tuple(
            tuple(x) for x in auditoria["repeated_ids"]
        )
        auditoria["multi_isoform_genes"] = tuple(
            tuple(x) for x in auditoria["multi_isoform_genes"]
        )
        scan = OfftargetScan(
            params=OfftargetParams(**datos["params"]),
            source=datos["source"],
            provenance=Provenance(**datos["provenance"]),
            audit=IsoformAudit(**auditoria),
            results=tuple(
                LoadResult(
                    start=r["start"], strand=r["strand"], query=r["query"],
                    sequence=r["sequence"],
                    patterns=patterns_from_heptamer(r["heptamer"]),
                    counts=Counts(sites=r["sites"], transcripts=r["transcripts"]),
                    percentiles=r["percentiles"],
                )
                for r in datos["results"]
            ),
            nulls={
                clave: _null_from_json(valor)
                for clave, valor in datos["nulls"].items()
            },
            controls=tuple(
                Control(name=c["name"], heptamer=c["heptamer"], sites=c["sites"])
                for c in datos["controls"]
            ),
            self_counts={
                consulta: SelfCount(
                    query=consulta, target_label=s["target_label"],
                    occurrences=s["occurrences"], sites=s["sites"],
                )
                for consulta, s in datos["self_counts"].items()
            },
            raw=datos["raw"],
            # Mismo criterio que en la corrida de seed: "" = la corrida no lo guardo.
            mature_md5=datos.get("mature_md5", ""),
            mature_version=datos.get("mature_version", ""),
        )
        almacen.add(
            OfftargetRun(
                run_id=datos["run_id"], date=registro.date, ran_by=datos["ran_by"],
                source=datos["source"], result_md5=datos["result_md5"], scan=scan,
            )
        )
    return almacen


def save_selection(store: ProjectStore, *, starts, date: str, by: str) -> Record:
    """La seleccion a mano. Una nueva se AÑADE; la vigente es la ultima."""
    return store.append(
        "seleccion",
        {"starts": sorted(int(s) for s in starts), "by": str(by)},
        date=date,
    )


def selected_starts(store: ProjectStore) -> tuple[int, ...]:
    """La seleccion VIGENTE: la ultima registrada. Las anteriores siguen en el log."""
    registros = store.records("seleccion")
    return tuple(registros[-1].payload["starts"]) if registros else ()


# ─────────────────── el cuarto modal ───────────────────
#
# Se guarda el CRUDO del resultado ademas de lo interpretado. Es lo mismo que hacen los
# otros tres y por la misma razon: lo interpretado depende de como interprete esta
# version del codigo, y el crudo no. Si mañana cambia la forma de comparar contra el
# referente, el crudo sigue permitiendo recalcularlo; al reves no.


def save_splice_run(store: ProjectStore, run) -> Record:
    """Persiste una corrida de prediccion de sitios de splicing."""
    return store.append(
        "corrida_empalme",
        {
            "run_id": run.run_id,
            "ran_by": run.ran_by,
            "executor": run.executor,
            "result_md5": run.result_md5,
            "pairs": [
                {
                    "construction": p.construction,
                    "candidate_start": p.candidate_start,
                    "intron": p.intron,
                    "legit_donor": p.legit_donor,
                    "legit_acceptor": p.legit_acceptor,
                    "context_5": p.context_5,
                    "context_3": p.context_3,
                    "cryptics": [
                        {
                            "position": c.position, "kind": c.kind,
                            "score": c.score, "fraction": c.fraction, "note": c.note,
                        }
                        for c in p.cryptics
                    ],
                    "known_cryptic": (
                        None if p.known_cryptic is None
                        else {
                            "position": p.known_cryptic.position,
                            "kind": p.known_cryptic.kind,
                            "score": p.known_cryptic.score,
                            "fraction": p.known_cryptic.fraction,
                            "note": p.known_cryptic.note,
                        }
                    ),
                }
                for p in run.scan.pairs
            ],
            # La accesibilidad estructural va en la MISMA corrida y SEPARADA del resto:
            # son dos preguntas y mezclarlas seria dar por medido lo que se ha predicho.
            "folding": {
                f"{inicio}|{intron}": valores
                for (inicio, intron), valores in run.folding.items()
            },
            "raw": run.raw,
        },
        date=run.date,
    )


def load_splice_store(store: ProjectStore):
    """Reconstruye el `SpliceStore` desde el log."""
    from .splice_store import SpliceRun, SpliceStore
    from .spliceai import Cryptic, PairResult, SpliceScan

    almacen = SpliceStore()
    for registro in store.records("corrida_empalme"):
        datos = registro.payload

        def _criptico(bruto):
            return None if bruto is None else Cryptic(
                position=bruto["position"], kind=bruto["kind"],
                score=bruto["score"], fraction=bruto["fraction"],
                note=bruto.get("note", ""),
            )

        pares = tuple(
            PairResult(
                construction=p["construction"],
                candidate_start=p["candidate_start"],
                intron=p["intron"],
                legit_donor=p["legit_donor"],
                legit_acceptor=p["legit_acceptor"],
                cryptics=tuple(_criptico(c) for c in p["cryptics"]),
                known_cryptic=_criptico(p["known_cryptic"]),
                context_5=p["context_5"],
                context_3=p["context_3"],
            )
            for p in datos["pairs"]
        )
        plegado = {}
        for clave, valores in datos.get("folding", {}).items():
            inicio, _, intron = clave.partition("|")
            plegado[(int(inicio), intron)] = valores
        almacen.add(
            SpliceRun(
                run_id=datos["run_id"], date=registro.date, ran_by=datos["ran_by"],
                executor=datos["executor"], result_md5=datos["result_md5"],
                scan=SpliceScan(pairs=pares), raw=datos["raw"], folding=plegado,
            )
        )
    return almacen
