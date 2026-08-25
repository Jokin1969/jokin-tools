"""Paso 0: descarga las referencias, verifica sus checksums y extrae los 3'UTR.

La URL base del endpoint es OBLIGATORIA por linea de comandos: este proyecto no
escribe URLs que no haya verificado (regla 4). Cuando el endpoint quede verificado
desde aqui y anotado en `docs/endpoints-verificados.md`, podra fijarse por defecto.

    python3 apps/batchwork/tools/fetch_data.py \\
        --efetch-url https://<host verificado>/entrez/eutils/efetch.fcgi

Si un md5 no coincide, el programa PARA y no escribe nada: ni el transcrito ni el
3'UTR. Una secuencia que no verifica no se usa, no se corrige y no se completa.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from batchwork.errors import BatchworkError  # noqa: E402
from batchwork.fetch import (  # noqa: E402
    build_efetch_url,
    download_text,
    min_interval_seconds,
    parse_fasta_payload,
)
from batchwork.reference import (  # noqa: E402
    REFERENCES,
    extract_3utr,
    sequence_md5,
    verify_transcript,
)

DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "data"
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
    print("Respuesta cruda (primeras lineas):")
    print("\n".join(f"  | {line}" for line in preview.splitlines()))

    header, sequence = parse_fasta_payload(payload, source=url)
    print(f"Cabecera: {header}")

    canonical = verify_transcript(sequence, reference)
    print(f"  longitud {len(canonical)} nt ✓   md5 {sequence_md5(canonical)} ✓")

    utr3 = extract_3utr(canonical, reference)
    start, end = reference.utr3
    print(f"  3'UTR {start}-{end}: {len(utr3)} nt ✓   md5 {sequence_md5(utr3)} ✓")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = args.out_dir / f"{accession}.fa"
    utr3_path = args.out_dir / f"{reference.slug}_3utr.fasta"
    transcript_path.write_text(
        f">{header}\n{wrap_fasta(canonical)}\n", encoding="utf-8"
    )
    utr3_path.write_text(
        f">{accession}|3UTR|{start}-{end}|{len(utr3)} nt|"
        f"md5={sequence_md5(utr3)}\n{wrap_fasta(utr3)}\n",
        encoding="utf-8",
    )
    print(f"  escrito {transcript_path}")
    print(f"  escrito {utr3_path}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--efetch-url",
        required=True,
        help="Base VERIFICADA del endpoint efetch. Obligatoria: el codigo no fija "
        "ninguna URL sin verificar (regla 4).",
    )
    parser.add_argument(
        "--accession",
        action="append",
        choices=sorted(REFERENCES),
        help="Accession a descargar (repetible). Por defecto, todos los del registro.",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--api-key", help="Clave de API de NCBI (sube el limite a 10/s).")
    parser.add_argument("--tool", default="batchwork", help="Parametro de cortesia.")
    parser.add_argument("--email", help="Parametro de cortesia recomendado por NCBI.")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)

    accessions = args.accession or sorted(REFERENCES)
    interval = min_interval_seconds(has_api_key=bool(args.api_key))
    print(
        f"Descargando {len(accessions)} referencia(s), "
        f"1 peticion cada {interval:.2f} s como maximo (limite de NCBI por IP)."
    )

    for index, accession in enumerate(accessions):
        if index:
            time.sleep(interval)
        try:
            fetch_one(accession, args)
        except (BatchworkError, ValueError) as exc:
            # rule2-ok: frontera CLI. El fallo se imprime entero en stderr y sale con
            # codigo 2; no se escribe ningun fichero y no se pasa al siguiente
            # accession, porque el paso 0 aborta el pipeline entero.
            print(f"\nPARA — {accession}: {exc}", file=sys.stderr)
            return 2

    print("\nTodas las referencias verificadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
