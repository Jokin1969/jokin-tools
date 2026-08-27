"""El frente de especificidad: preparar la peticion, entregarla, recoger el resultado.

**Este modulo NO lanza el BLAST, y no es un descuido.** El navegador no puede llamar a
NCBI —CORS— y este backend no tiene red saliente. Asi que lo que se hace es:

  1. **preparar**: construir el FASTA de consulta con su md5 y la orden `blastn` completa
     con los parametros elegidos;
  2. **entregar**: la orden se copia y se ejecuta fuera, en local o contra `-remote`;
  3. **recoger**: se sube el `-outfmt 6`, se valida y se almacena (`blast_store.py`).

El ejecutor vive detras de una interfaz con TRES implementaciones para que el dia que
haya red no haya que tocar la interfaz: `Disabled` (la de hoy, y dice por que),
`LocalCommand` y `RemoteApi`.

**Ninguna URL escrita aqui** (regla 4): `RemoteApi` exige un endpoint verificado y aborta
sin el. Hay un test que lee el fuente de este modulo y comprueba que no hay ni un `http`.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from .errors import ShmirDesignError

FASTA_WRAP = 60

#: Cuantas columnas trae `-outfmt 6`. Menos de esas y no es ese formato.
OUTFMT6_COLUMNS = 12

#: Prefijos de RefSeq PREDICHOS (no revisados). Se distinguen porque un hit contra un
#: modelo predicho no es lo mismo que uno contra un transcrito curado.
PREDICTED_PREFIXES = ("XM_", "XR_", "XP_")


@dataclass(frozen=True)
class BlastParams:
    """Los parametros efectivos. COMPLETOS, no solo los que se cambiaron."""

    task: str = "blastn-short"
    word_size: int = 7
    evalue: float = 1000.0
    dust: str = "no"
    outfmt: str = "6"
    db: str = "refseq_rna"
    #: Filtro por organismo. VACIO = NO DECLARADO, que no es «todas»: el unico origen
    #: es `species.taxid()`, y `command()` aborta sin el. Antes valia `txid10090` por
    #: defecto, asi que una consulta de conejo salia filtrada a raton sin que nadie
    #: avisara — y el resultado tenia la forma correcta.
    entrez_query: str = ""
    include_predicted: bool = True
    remote: bool = False

    def __post_init__(self) -> None:
        if self.word_size < 4:
            raise ValueError(
                f"word_size={self.word_size} invalido: por debajo de 4 blastn-short no "
                f"siembra y la corrida no significa nada. Se aborta."
            )
        if self.evalue <= 0:
            raise ValueError(
                f"evalue={self.evalue} invalido: tiene que ser positivo. Se aborta."
            )
        if self.outfmt != "6":
            raise ValueError(
                f"outfmt={self.outfmt!r}: este almacen solo sabe leer `-outfmt 6`. "
                f"Aceptar otro formato dejaria entrar un fichero que luego se rechaza "
                f"sin poder decir por que. Se aborta al elegirlo, no al subirlo."
            )
        if not self.db.strip():
            raise ValueError("La base no puede ir vacía; se aborta.")

    def with_changes(self, **cambios) -> "BlastParams":
        return replace(self, **cambios)

    @classmethod
    def for_species(cls, name: str, **cambios) -> "BlastParams":
        """Los parametros de UNA especie. El taxid sale de `species`, no se teclea."""
        from .species import taxid

        return cls(entrez_query=taxid(name), **cambios)

    def modified(self) -> tuple[str, ...]:
        """Que campos difieren de los valores por defecto. En orden estable.

        El ORGANISMO no cuenta como «ajuste modificado»: es parte de la IDENTIDAD de la
        corrida, no un ajuste que alguien haya tocado. Marcarlo en rojo por no ser raton
        haria que toda corrida de otra especie pareciera no estandar, y entonces el rojo
        dejaria de significar lo que significa.
        """
        base = BlastParams(entrez_query=self.entrez_query)
        return tuple(
            campo
            for campo in (
                "task", "word_size", "evalue", "dust", "outfmt", "db",
                "entrez_query", "include_predicted", "remote",
            )
            if getattr(self, campo) != getattr(base, campo)
        )

    @property
    def is_standard(self) -> bool:
        """Sin ningun ajuste tocado. `remote` cuenta como ajuste."""
        return not self.modified()

    @property
    def can_give_verdict(self) -> bool:
        """Solo una corrida ESTANDAR contra una base LOCAL cierra el frente."""
        return not self.remote and not self.modified()

    @property
    def why_no_verdict(self) -> str:
        if self.can_give_verdict:
            return ""
        motivos = []
        if self.remote:
            motivos.append(
                "`-remote` es EXPLORACION, nunca veredicto: la base de NCBI CAMBIA "
                "entre corridas, así que el resultado no es reproducible y dentro de un "
                "año nadie puede repetirlo. Solo una base LOCAL con md5 en el "
                "manifiesto da veredicto."
            )
        tocados = [c for c in self.modified() if c != "remote"]
        if tocados:
            motivos.append(
                "parámetros NO ESTÁNDAR (" + ", ".join(tocados) + "): un veredicto "
                "obtenido con ajustes cambiados no puede ser indistinguible de uno "
                "estándar. Es la misma lección del `.out` sin especie."
            )
        return " ".join(motivos)

    def entrez_expression(self) -> str:
        """La expresion de Entrez completa, con los predichos dentro o fuera."""
        if not self.entrez_query:
            raise ShmirDesignError(
                "No hay organismo declarado para esta consulta, así que la orden de "
                "BLAST saldria SIN filtro de especie o —peor— con el de otra. El taxid "
                "no se teclea ni se hereda de un valor por defecto: sale de "
                "`species.taxid(nombre)`, que aborta si esa especie no lo tiene "
                "declarado. Usa `BlastParams.for_species(nombre)`."
            )
        partes = [f"{self.entrez_query}[ORGN]"]
        if not self.include_predicted:
            # Excluir los modelos predichos es EXCLUIRLOS, y se ve en la orden.
            partes.append(
                "NOT (" + " OR ".join(f"{p}[ACCN]" for p in ("XM_", "XR_")) + ")"
            )
        return " AND ".join(partes)

    def command(self, *, query_path: str, out_path: str | None = None) -> str:
        """La orden `blastn` COMPLETA. Todos los parametros, no solo los cambiados."""
        trozos = [
            "blastn",
            f"-task {self.task}",
            f"-db {self.db}",
            f"-word_size {self.word_size}",
            f"-evalue {self.evalue:g}",
            f"-dust {self.dust}",
            f"-outfmt {self.outfmt}",
            f'-entrez_query "{self.entrez_expression()}"',
            f"-query {query_path}",
        ]
        if self.remote:
            trozos.insert(3, "-remote")
        if out_path:
            trozos.append(f"-out {out_path}")
        return " ".join(trozos)

    def describe(self) -> list[str]:
        tocados = self.modified()
        lineas = [
            f"task={self.task}  word_size={self.word_size}  evalue={self.evalue:g}  "
            f"dust={self.dust}  outfmt={self.outfmt}",
            f"db={self.db}  organismo={self.entrez_query}  "
            f"predichos={'SI' if self.include_predicted else 'NO'}  "
            f"remote={'SI' if self.remote else 'no'}",
        ]
        if tocados:
            lineas.append(
                "AJUSTES MODIFICADOS: " + ", ".join(tocados)
                + ". Viajan con el resultado y NO se pierden: un veredicto con "
                "parámetros cambiados no puede leerse como uno estándar."
            )
        else:
            lineas.append("Todos los ajustes en su valor por defecto.")
        if not self.can_give_verdict:
            lineas.append(f"NO CIERRA EL FRENTE: {self.why_no_verdict}")
        return lineas


DEFAULTS = BlastParams()


@dataclass(frozen=True)
class QueryFasta:
    """El FASTA de consulta, con su md5. Lo que se descarga y lo que se compara luego."""

    records: tuple[tuple[str, str], ...]
    text: str

    @classmethod
    def from_records(cls, records) -> "QueryFasta":
        registros = tuple((str(n), "".join(str(s).split()).upper()) for n, s in records)
        if not registros:
            raise ShmirDesignError(
                "No hay ninguna consulta seleccionada: no se emite un FASTA vacío, que "
                "es exactamente lo que produce una corrida que parece haber corrido. "
                "Se aborta."
            )
        vistos = set()
        lineas = []
        for nombre, secuencia in registros:
            if not secuencia:
                raise ShmirDesignError(
                    f"La consulta {nombre!r} no trae secuencia; se aborta en vez de "
                    f"emitir un registro vacío (regla 1)."
                )
            if nombre in vistos:
                raise ShmirDesignError(
                    f"El nombre de consulta {nombre!r} aparece dos veces. El resultado "
                    f"se cruza POR NOMBRE, así que dos iguales asignarian un hit al "
                    f"candidato equivocado sin dar ningún error. Se aborta."
                )
            vistos.add(nombre)
            lineas.append(f">{nombre}")
            lineas.extend(
                secuencia[i:i + FASTA_WRAP]
                for i in range(0, len(secuencia), FASTA_WRAP)
            )
        return cls(records=registros, text="\n".join(lineas) + "\n")

    @property
    def md5(self) -> str:
        return hashlib.md5(self.text.encode("ascii")).hexdigest()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(n for n, _ in self.records)

    def describe(self) -> str:
        return (
            f"FASTA de consulta: {len(self.records)} registro(s), "
            f"{len(self.text)} B / md5 {self.md5}. Ese md5 es el que tiene que traer el "
            f"resultado: sin el, un fichero de otra corrida entra sin que nadie lo note."
        )


# ─── El ejecutor, detras de una interfaz ─────────────────────────────────────


class Executor:
    """Interfaz. Tres implementaciones, y la de hoy es `Disabled`."""

    name = "interfaz"
    runs_here = False
    why = ""

    def prepare(self, params: BlastParams, query: QueryFasta, *, query_path: str) -> str:
        return params.command(query_path=query_path)

    def run(self, params: BlastParams, query: QueryFasta) -> str:
        raise NotImplementedError


class Disabled(Executor):
    """La de HOY. No ejecuta nada y dice exactamente por que."""

    name = "deshabilitado"
    runs_here = False
    why = (
        "Este software no ejecuta el BLAST y no puede: el navegador no puede llamar a "
        "NCBI (CORS) y este backend no tiene red saliente. Lo que hace es PREPARAR la "
        "petición —FASTA de consulta con md5 y la orden completa— para ejecutarla fuera, "
        "y RECOGER el resultado. No es una limitacion escondida: es la arquitectura."
    )

    def run(self, params: BlastParams, query: QueryFasta) -> str:
        raise ShmirDesignError(
            f"El ejecutor «{self.name}» NO EJECUTA. {self.why} Usa la orden que da "
            f"`prepare()` y sube el `-outfmt 6` resultante."
        )


class LocalCommand(Executor):
    """Da la orden para ejecutar EN LOCAL. Tampoco ejecuta desde aqui."""

    name = "orden_local"
    runs_here = False
    why = (
        "La orden se ejecuta en la máquina de quien la copia, contra una base LOCAL. Es "
        "el único camino que puede dar VEREDICTO, porque una base local tiene md5 y "
        "entra en el manifiesto."
    )

    def run(self, params: BlastParams, query: QueryFasta) -> str:
        raise ShmirDesignError(
            f"El ejecutor «{self.name}» prepara la orden pero no la lanza desde aquí. "
            f"{self.why}"
        )


class RemoteApi(Executor):
    """Para el dia que haya red. SIN URL escrita: se le pasa una verificada o aborta."""

    name = "api_remota"
    runs_here = True
    why = (
        "Lanza la consulta contra un endpoint. Hoy no hay ninguno verificado desde este "
        "proyecto, así que hay que pasarselo — y verificarlo antes (regla 4)."
    )

    def __init__(self, *, endpoint: str | None):
        if not endpoint or not str(endpoint).strip():
            raise ValueError(
                "RemoteApi necesita un endpoint VERIFICADO. Aquí no hay ninguna URL "
                "escrita a propósito (regla 4): se comprueba que responde y que el "
                "formato es el esperado, se anota en docs/endpoints-verificados.md, y "
                "entonces se pasa. Se aborta."
            )
        self.endpoint = str(endpoint).strip()

    def run(self, params: BlastParams, query: QueryFasta) -> str:
        raise ShmirDesignError(
            f"El endpoint {self.endpoint!r} no se ha verificado desde este proyecto y "
            f"este módulo no llama a ninguna URL por su cuenta. Se aborta (regla 4)."
        )


EXECUTORS = {
    "deshabilitado": Disabled,
    "orden_local": LocalCommand,
    "api_remota": RemoteApi,
}


def default_executor() -> Executor:
    """El de hoy. Cambiarlo es cambiar UNA linea, no la interfaz."""
    return Disabled()


# ─── El resultado ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BlastHit:
    query: str
    subject: str
    identity: float
    length: int
    mismatches: int
    gapopen: int
    qstart: int
    qend: int
    sstart: int
    send: int
    evalue: float
    bitscore: float

    @property
    def predicted(self) -> bool:
        return self.subject.upper().startswith(PREDICTED_PREFIXES)


def parse_outfmt6(text: str) -> tuple[BlastHit, ...]:
    """Lee un `-outfmt 6`. Un fichero vacio ABORTA: cero hits no es «no corrio»."""
    lineas = [
        l for l in str(text).splitlines()
        if l.strip() and not l.lstrip().startswith("#")
    ]
    if not lineas:
        raise ShmirDesignError(
            "El fichero de resultados está VACÍO (ni una fila de datos). Cero hits y "
            "«la corrida no llego a correr» son cosas distintas y este fichero no las "
            "distingue — es la misma lección del `.out` de RepeatMasker sin resumen. "
            "Se aborta: si de verdad no hubo hits, hace falta el log de la corrida."
        )
    hits = []
    for numero, linea in enumerate(lineas, start=1):
        campos = linea.rstrip("\n").split("\t")
        if len(campos) != OUTFMT6_COLUMNS:
            raise ShmirDesignError(
                f"Fila {numero} del resultado: {len(campos)} columnas y `-outfmt 6` "
                f"tiene {OUTFMT6_COLUMNS}. O no es ese formato o el fichero viene "
                f"recortado; se aborta en vez de leer las columnas corridas."
            )
        try:
            hits.append(
                BlastHit(
                    query=campos[0], subject=campos[1], identity=float(campos[2]),
                    length=int(campos[3]), mismatches=int(campos[4]),
                    gapopen=int(campos[5]), qstart=int(campos[6]), qend=int(campos[7]),
                    sstart=int(campos[8]), send=int(campos[9]),
                    evalue=float(campos[10]), bitscore=float(campos[11]),
                )
            )
        except ValueError as exc:
            raise ShmirDesignError(
                f"Fila {numero} del resultado: no se pudo leer un número ({exc}); se "
                f"aborta el parseo en vez de saltarse la fila."
            ) from exc
    return tuple(hits)
