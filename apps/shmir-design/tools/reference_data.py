"""Paso 0: verifica las referencias y extrae los 3'UTR.

Por defecto **no toca la red**: lee los fixtures versionados de `data/reference/` y
comprueba longitud, extremos y md5 contra `shmir_design/reference.py`. El rigor no
cambia por leer de disco — si un checksum no coincide, PARA y no escribe nada.

    python3 apps/shmir-design/tools/reference_data.py

La descarga es un camino opcional, para cuando haya salida a internet. La URL base va
siempre por parametro: este proyecto no escribe URLs que no haya verificado (regla 4).

    python3 apps/shmir-design/tools/reference_data.py --fetch \\
        --efetch-url https://<host verificado>/entrez/eutils/efetch.fcgi

Lo descargado se verifica ANTES de escribirse como fixture: un fichero que no pasa el
checksum no llega al repositorio.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.fetch import (  # noqa: E402
    build_efetch_url,
    download_text,
    min_interval_seconds,
    parse_fasta_payload,
)
from shmir_design.reference import (  # noqa: E402
    PACKAGE_REFERENCE_DIR,
    REFERENCES,
    ReferenceTranscript,
    extract_3utr,
    find_fixture,
    fixture_filename,
    load_reference,
    reference_dirs,
    sequence_md5,
    verify_transcript,
)

WRAP = 70
PREVIEW_LINES = 3


def wrap_fasta(sequence: str, width: int = WRAP) -> str:
    return "\n".join(sequence[i : i + width] for i in range(0, len(sequence), width))


def mask(url: str) -> str:
    """Oculta la clave de API al imprimir la peticion."""
    if "api_key=" not in url:
        return url
    head, _, tail = url.partition("api_key=")
    return head + "api_key=***" + tail.partition("&")[1] + tail.partition("&")[2]


def report_transcript(
    reference: ReferenceTranscript, sequence: str, origin: str
) -> None:
    print(f"  origen: {origin}")
    print(f"  longitud {len(sequence)} nt ✓   md5 {sequence_md5(sequence)} ✓")
    utr3 = extract_3utr(sequence, reference)
    start, end = reference.utr3
    print(f"  3'UTR {start}-{end}: {len(utr3)} nt ✓   md5 {sequence_md5(utr3)} ✓")


def verify_one(accession: str, args: argparse.Namespace) -> None:
    reference = REFERENCES[accession]
    print(f"\n── {accession} ({reference.organism}, {reference.gene}) ──")
    path = find_fixture(reference, data_dir=args.data_dir)
    sequence = load_reference(reference, data_dir=args.data_dir)
    report_transcript(reference, sequence, str(path))


def fetch_one(accession: str, args: argparse.Namespace) -> None:
    reference = REFERENCES[accession]
    url = build_efetch_url(
        args.efetch_url,
        accession,
        api_key=args.api_key,
        tool=args.tool,
        email=args.email,
    )
    print(f"\n── {accession} ({reference.organism}, {reference.gene}) ──")
    print(f"GET {mask(url)}")

    payload = download_text(url, timeout=args.timeout)
    preview = "\n".join(payload.splitlines()[:PREVIEW_LINES])
    print("Respuesta cruda (primeras líneas):")
    print("\n".join(f"  | {line}" for line in preview.splitlines()))

    header, sequence = parse_fasta_payload(payload, source=url)
    canonical = verify_transcript(sequence, reference)
    report_transcript(reference, canonical, url)

    destino = Path(args.data_dir) if args.data_dir else PACKAGE_REFERENCE_DIR
    destino.mkdir(parents=True, exist_ok=True)
    fixture = destino / fixture_filename(reference)
    fixture.write_text(f">{header}\n{wrap_fasta(canonical)}\n", encoding="utf-8")
    print(f"  escrito {fixture}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--accession",
        action="append",
        choices=sorted(REFERENCES),
        help="Accession a verificar (repetible). Por defecto, todos los del registro.",
    )
    parser.add_argument(
        "--data-dir",
        help="Directorio de fixtures. Por defecto se miran, en orden: "
        + ", ".join(str(d) for d in reference_dirs()),
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Descargar en vez de leer el fixture, y escribirlo tras verificarlo.",
    )
    parser.add_argument(
        "--efetch-url",
        help="Base VERIFICADA del endpoint efetch. Obligatoria con --fetch: el código "
        "no fija ninguna URL sin verificar (regla 4).",
    )
    parser.add_argument("--api-key", help="Clave de API de NCBI (límite 10 req/s).")
    parser.add_argument("--tool", default="shmir-design", help="Parámetro de cortesia.")
    parser.add_argument("--email", help="Parámetro de cortesia recomendado por NCBI.")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)

    if args.fetch and not args.efetch_url:
        print(
            "reference_data: --fetch necesita --efetch-url con una base verificada; "
            "el código no fija ninguna URL sin verificar (regla 4).",
            file=sys.stderr,
        )
        return 2
    if args.efetch_url and not args.fetch:
        print(
            "reference_data: --efetch-url solo tiene sentido con --fetch.",
            file=sys.stderr,
        )
        return 2

    accessions = args.accession or sorted(REFERENCES)
    interval = min_interval_seconds(has_api_key=bool(args.api_key))
    if args.fetch:
        print(
            f"Descargando {len(accessions)} referencia(s), 1 petición cada "
            f"{interval:.2f} s como máximo (límite de NCBI, por IP)."
        )
    else:
        print(f"Verificando {len(accessions)} referencia(s) desde fixtures (sin red).")

    for index, accession in enumerate(accessions):
        try:
            if args.fetch:
                if index:
                    time.sleep(interval)
                fetch_one(accession, args)
            else:
                verify_one(accession, args)
        except (ShmirDesignError, ValueError) as exc:
            # rule2-ok: frontera CLI. El fallo se imprime entero en stderr y sale con
            # codigo 2; no se escribe ningun fichero y no se pasa a la siguiente
            # referencia, porque el paso 0 aborta el pipeline entero.
            print(f"\nPARA — {accession}: {exc}", file=sys.stderr)
            return 2

    print("\nTodas las referencias verificadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
