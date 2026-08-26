"""Referencias verificadas y comprobacion de checksum (paso 0 del pipeline).

El proyecto ya sufrio una vez la entrega de una secuencia fabricada con metadatos
correctos alrededor. Este modulo existe para que eso no vuelva a colar: una secuencia
solo se acepta si su longitud, sus extremos y su md5 coinciden con la referencia. Si
algo no cuadra, se aborta — no se continua con la secuencia que haya.

Los valores del registro los verifico el responsable del proyecto (accession, anatomia
del transcrito y md5). Las secuencias NO estan aqui: se descargan y se comprueban.
Convenio del md5: secuencia en MAYUSCULAS, sin cabecera y sin saltos de linea.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .errors import (
    ChecksumMismatchError,
    FetchError,
    MissingSequenceError,
    ShmirDesignError,
)
from .fetch import parse_fasta_payload

#: Los datos de referencia son fixtures versionados, no descargas en tiempo de
#: ejecucion: la red no es una dependencia del analisis. La verificacion no cambia.
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_REFERENCE_DIR = PACKAGE_ROOT / "data" / "reference"
REPO_REFERENCE_DIR = PACKAGE_ROOT.parent.parent / "data" / "reference"
DEFAULT_REFERENCE_DIRS = (PACKAGE_REFERENCE_DIR, REPO_REFERENCE_DIR)

ABORT_HINT = (
    "PARA: no continues con la secuencia que tengas. "
    "Regla 1: no se sustituye ni se reconstruye una secuencia que no verifica."
)


def canonical_form(sequence: str | None, *, name: str = "secuencia") -> str:
    """Forma canonica para el md5: sin cabecera, sin espacios, en mayusculas.

    A diferencia de `polya.normalize_sequence`, aqui NO se traduce U a T: el md5 debe
    calcularse sobre lo que se descargo, no sobre una version reescrita.
    """
    if sequence is None:
        raise MissingSequenceError(
            f"No hay {name} que verificar; se aborta el paso 0 (descarga + checksum)."
        )
    cleaned = "".join(sequence.split()).upper()
    if not cleaned:
        raise MissingSequenceError(
            f"La {name} esta vacia; se aborta el paso 0 (descarga + checksum)."
        )
    return cleaned


def sequence_md5(sequence: str | None, *, name: str = "secuencia") -> str:
    canonical = canonical_form(sequence, name=name)
    return hashlib.md5(canonical.encode("ascii"), usedforsecurity=False).hexdigest()


@dataclass(frozen=True)
class ReferenceTranscript:
    accession: str
    slug: str
    organism: str
    gene: str
    length: int
    md5: str
    starts_with: str
    ends_with: str
    utr5: tuple[int, int]
    cds: tuple[int, int]
    utr3: tuple[int, int]
    utr3_md5: str

    def __post_init__(self) -> None:
        tramos = (
            ("5'UTR", self.utr5),
            ("CDS", self.cds),
            ("3'UTR", self.utr3),
        )
        esperado_inicio = 1
        for nombre, (start, end) in tramos:
            if start != esperado_inicio or end < start:
                raise ValueError(
                    f"{self.accession}: el tramo {nombre} declarado {start}-{end} no "
                    f"continua en {esperado_inicio}; anatomia incoherente, se aborta."
                )
            esperado_inicio = end + 1
        if self.utr3[1] != self.length:
            raise ValueError(
                f"{self.accession}: el 3'UTR termina en {self.utr3[1]} pero el "
                f"transcrito mide {self.length} nt; anatomia incoherente, se aborta."
            )
        if self.cds_length % 3 != 0:
            raise ValueError(
                f"{self.accession}: el CDS mide {self.cds_length} nt, que no es "
                f"multiplo de 3; anatomia incoherente, se aborta."
            )
        for nombre, valor in (("md5", self.md5), ("utr3_md5", self.utr3_md5)):
            if len(valor) != 32 or any(c not in "0123456789abcdef" for c in valor):
                raise ValueError(
                    f"{self.accession}: {nombre}={valor!r} no es un md5 hexadecimal "
                    f"de 32 caracteres; se aborta."
                )
        if len(self.starts_with) > self.length or len(self.ends_with) > self.length:
            raise ValueError(
                f"{self.accession}: los extremos declarados no caben en un transcrito "
                f"de {self.length} nt; se aborta."
            )

    @property
    def utr5_length(self) -> int:
        return self.utr5[1] - self.utr5[0] + 1

    @property
    def cds_length(self) -> int:
        return self.cds[1] - self.cds[0] + 1

    @property
    def utr3_length(self) -> int:
        return self.utr3[1] - self.utr3[0] + 1

    @property
    def protein_length(self) -> int:
        """Aminoacidos, sin contar el codon de parada."""
        return self.cds_length // 3 - 1


REFERENCES: dict[str, ReferenceTranscript] = {
    "NM_011170.3": ReferenceTranscript(
        accession="NM_011170.3",
        slug="mouse",
        organism="Mus musculus",
        gene="Prnp",
        length=2191,
        md5="44fb8cd80883844cde5e53bbc367b176",
        starts_with="CCCCTTTCCACTCCCGGCTCCCCCGCGTTG",
        ends_with="CATTAAATAGAAGCTATGATGAACACCTGG",
        utr5=(1, 184),
        cds=(185, 949),
        utr3=(950, 2191),
        utr3_md5="19f5fa2a77a87892770e2affdc90e0e4",
    ),
    "NM_000311.5": ReferenceTranscript(
        accession="NM_000311.5",
        slug="human",
        organism="Homo sapiens",
        gene="PRNP",
        length=2435,
        md5="e28a945d24ce53e0d1d93ba5b55a532a",
        starts_with="GCCAGTCGCTGACAGCCGCGGCGCCGCGAG",
        ends_with="CTGAAATTAAACGAGCGAAGATGAGCACCA",
        utr5=(1, 67),
        cds=(68, 829),
        utr3=(830, 2435),
        utr3_md5="f7fdb4a88d4834dbbf9a23edf9ec85dc",
    ),
}


def verify_transcript(sequence: str | None, reference: ReferenceTranscript) -> str:
    """Comprueba longitud, extremos y md5. Devuelve la secuencia canonica o aborta."""
    canonical = canonical_form(sequence, name=f"secuencia de {reference.accession}")

    if len(canonical) != reference.length:
        raise ChecksumMismatchError(
            f"{reference.accession}: la secuencia mide {len(canonical)} nt y la "
            f"referencia dice {reference.length} nt. {ABORT_HINT}"
        )

    if not canonical.startswith(reference.starts_with):
        raise ChecksumMismatchError(
            f"{reference.accession}: el extremo 5' empieza por "
            f"{canonical[:len(reference.starts_with)]!r} y se esperaba "
            f"{reference.starts_with!r}. {ABORT_HINT}"
        )
    if not canonical.endswith(reference.ends_with):
        raise ChecksumMismatchError(
            f"{reference.accession}: el extremo 3' termina en "
            f"{canonical[-len(reference.ends_with):]!r} y se esperaba "
            f"{reference.ends_with!r}. {ABORT_HINT}"
        )

    obtained = sequence_md5(canonical)
    if obtained != reference.md5:
        raise ChecksumMismatchError(
            f"{reference.accession}: md5 {obtained} y la referencia dice "
            f"{reference.md5}. La secuencia descargada NO es la que dice ser. "
            f"{ABORT_HINT}"
        )
    return canonical


def extract_3utr(sequence: str | None, reference: ReferenceTranscript) -> str:
    """Extrae el 3'UTR del transcrito ya verificado y comprueba tambien su md5."""
    canonical = verify_transcript(sequence, reference)
    start, end = reference.utr3
    utr3 = canonical[start - 1 : end]

    if len(utr3) != reference.utr3_length:
        raise ChecksumMismatchError(
            f"{reference.accession}: el 3'UTR extraido mide {len(utr3)} nt y se "
            f"esperaban {reference.utr3_length} nt. {ABORT_HINT}"
        )
    obtained = sequence_md5(utr3)
    if obtained != reference.utr3_md5:
        raise ChecksumMismatchError(
            f"{reference.accession}: el 3'UTR extraido ({start}-{end}) tiene md5 "
            f"{obtained} y la referencia dice {reference.utr3_md5}. La extraccion no "
            f"coincide con la anatomia verificada. {ABORT_HINT}"
        )
    return utr3


# ─── Fixtures versionados ────────────────────────────────────────────────────
def fixture_filename(reference: ReferenceTranscript) -> str:
    return f"{reference.accession}.fa"


def reference_dirs(data_dir: Path | str | None = None) -> tuple[Path, ...]:
    return (Path(data_dir),) if data_dir is not None else DEFAULT_REFERENCE_DIRS


def fixture_available(
    reference: ReferenceTranscript,
    *,
    data_dir: Path | str | None = None,
) -> bool:
    """¿Esta el fixture en disco? Pregunta, no intento fallido: no lanza."""
    return any(
        (directory / fixture_filename(reference)).is_file()
        for directory in reference_dirs(data_dir)
    )


def find_fixture(
    reference: ReferenceTranscript,
    *,
    data_dir: Path | str | None = None,
) -> Path:
    """Localiza el fixture del transcrito. Si no esta, aborta diciendo donde busco."""
    candidates = [d / fixture_filename(reference) for d in reference_dirs(data_dir)]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    buscados = ", ".join(str(c) for c in candidates)
    raise MissingSequenceError(
        f"No se encontro el fixture {fixture_filename(reference)} de "
        f"{reference.accession}; se buscó en: {buscados}. Se aborta el paso 0: sin "
        f"secuencia no hay analisis y no se genera ninguna. Anadelo al repositorio o "
        f"descargalo con tools/reference_data.py --fetch --efetch-url <base verificada>."
    )


def load_reference(
    reference: ReferenceTranscript,
    *,
    data_dir: Path | str | None = None,
) -> str:
    """Lee el fixture y lo verifica: longitud, extremos y md5. Aborta si algo falla."""
    path = find_fixture(reference, data_dir=data_dir)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MissingSequenceError(
            f"No se pudo leer el fixture {path} ({exc}); se aborta el paso 0."
        ) from exc
    except UnicodeDecodeError as exc:
        raise MissingSequenceError(
            f"El fixture {path} no es UTF-8 valido ({exc}); se aborta el paso 0."
        ) from exc

    try:
        _, sequence = parse_fasta_payload(raw, source=str(path))
    except FetchError as exc:
        raise MissingSequenceError(
            f"El fixture {path} no es un FASTA de un unico registro ({exc}); "
            f"se aborta el paso 0."
        ) from exc

    return verify_transcript(sequence, reference)


def load_3utr(
    reference: ReferenceTranscript,
    *,
    data_dir: Path | str | None = None,
) -> str:
    """3'UTR verificado del transcrito, extraido del fixture por sus coordenadas."""
    return extract_3utr(load_reference(reference, data_dir=data_dir), reference)


def _normalizada(sequence: str, *, name: str) -> str:
    """Mayusculas, sin espacios ni saltos. Importado aqui para no crear un ciclo."""
    from .polya import normalize_sequence  # noqa: PLC0415

    return normalize_sequence(sequence, name=name)


def check_declared_length(sequence: str, declared: int, *, name: str) -> None:
    """La longitud anunciada se cuenta sobre la cadena ENTREGADA, no sobre la prevista.

    Esta es la comprobacion de una linea que no existia y que habria parado la errata
    nº 4 del registro: un 3'UTR anunciado como «1242 nt verificados» que en realidad
    traia 1246. Contar lo que se pretendia entregar en vez de lo entregado es el fallo,
    y no lo caza ningun test de consistencia interna.
    """
    if declared < 0:
        raise ShmirDesignError(
            f"{name}: se ha anunciado una longitud negativa ({declared}). Se aborta."
        )
    if len(sequence) != declared:
        raise ShmirDesignError(
            f"{name}: se anuncia una longitud de {declared} nt y la cadena ENTREGADA "
            f"mide {len(sequence)}. Se aborta: la longitud se cuenta sobre lo que de "
            f"verdad se entrega, no sobre lo que se pretendia entregar, y esa "
            f"diferencia ya ha corrido un 3'UTR entero una vez."
        )


def write_sequence_file(
    sequence: str, *, directory: Path | str, stem: str, note: str = ""
) -> Path:
    """Escribe una secuencia a fichero CON su md5, para pegarla en una herramienta.

    Nunca a stdout: lo que se copia de una pantalla pierde caracteres, y lo que pierde
    caracteres son las carreras de homopolimero. Lo que se usa es el fichero, y su
    nombre lleva el md5 para que no se pueda confundir con otra version.
    """
    limpia = _normalizada(sequence, name=stem)
    checksum = sequence_md5(limpia)
    destino = Path(directory) / f"{stem}_{len(limpia)}nt_{checksum[:12]}.txt"
    lineas = [
        f"# {stem} — {len(limpia)} nt — md5 canonico {checksum}",
        "# Este fichero es lo que se pega en la herramienta externa. No copies de una",
        "# pantalla: lo que se pierde al copiar son las carreras de homopolimero, y eso",
        "# no se ve. Si la herramienta pide texto plano, pega el cuerpo de aqui abajo.",
    ]
    if note:
        lineas.append(f"# {note}")
    lineas.extend(limpia[i : i + 60] for i in range(0, len(limpia), 60))
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return destino


def read_sequence_file(path: Path | str) -> str:
    """Relee un fichero escrito por `write_sequence_file` COMPROBANDO su md5.

    La simetria es el punto: lo que se escribio con su checksum se vuelve a leer
    verificandolo. Un fichero que se haya editado a mano por el camino no pasa de aqui.
    """
    ruta = Path(path)
    texto = ruta.read_text(encoding="utf-8")
    cabeceras = [l for l in texto.splitlines() if l.startswith("#")]
    cuerpo = "".join(
        l.strip() for l in texto.splitlines() if not l.startswith(("#", ">"))
    )
    limpia = _normalizada(cuerpo, name=ruta.name)
    declarados = [
        palabra
        for linea in cabeceras
        for palabra in linea.split()
        if len(palabra) == 32 and all(c in "0123456789abcdef" for c in palabra)
    ]
    if not declarados:
        raise ShmirDesignError(
            f"{ruta}: no trae ningun md5 en su cabecera, asi que no se puede comprobar "
            f"que sea lo que dice ser. Se aborta: un fichero de secuencia sin checksum "
            f"es exactamente lo que hay que dejar de aceptar."
        )
    real = sequence_md5(limpia)
    if real not in declarados:
        raise ShmirDesignError(
            f"{ruta}: la cabecera declara md5 {declarados[0]} y el contenido da {real}. "
            f"El fichero se ha tocado desde que se escribio; se aborta."
        )
    return limpia
