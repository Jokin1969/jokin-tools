"""Escribe el 3'UTR a FICHERO, con su md5, para pegarlo en una herramienta externa.

    python3 apps/shmir-design/tools/export_utr3.py \\
        --fasta data/reference/NM_011170.3.fa \\
        --genbank data/reference/NM_011170.3.gb --out /tmp

Existe por la errata nº 4 del registro: un 3'UTR anunciado como «1242 nt verificados»
que traia 1246, pegado desde una conversacion a un formulario. Todo lo que salio de esa
corrida quedo inservible y costo varias tandas averiguar por que.

Por eso este programa **no imprime la secuencia**. Escribe un fichero cuyo nombre lleva
la longitud y el md5, y ese fichero es el que se sube. Si la herramienta pide texto
pegado, se pega el cuerpo del fichero — no lo que haya en una pantalla.

Codigo de salida:
  0  escrito
  2  no se pudo leer o la anatomia no se pudo resolver

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.fetch import parse_fasta_payload  # noqa: E402
from shmir_design.polya import normalize_sequence  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    check_declared_length,
    sequence_md5,
    write_sequence_file,
)
from shmir_design.resolve import check_boundaries, resolve_anatomy  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--fasta", type=Path, required=True)
    parser.add_argument("--genbank", type=Path, help="La via mas fiable de la anatomia.")
    parser.add_argument("--cds", type=int, nargs=2, metavar=("INICIO", "FIN"))
    parser.add_argument("--out", type=Path, required=True, help="Directorio de salida.")
    parser.add_argument(
        "--longitud-esperada", type=int,
        help="Si la das, se comprueba contra la cadena ENTREGADA y se aborta si no "
             "cuadra. Es la comprobacion de una linea que habria parado la errata nº 4.",
    )
    args = parser.parse_args(argv)

    try:
        _, bruta = parse_fasta_payload(
            args.fasta.read_text(encoding="utf-8"), source=str(args.fasta)
        )
        secuencia = normalize_sequence(bruta, name=str(args.fasta))
        anatomia = resolve_anatomy(
            name=args.fasta.name,
            sequence=secuencia,
            genbank=args.genbank,
            cds=tuple(args.cds) if args.cds else None,
            hint="\nEn este programa: --genbank FICHERO.gb o --cds INICIO FIN.",
        )
        check_boundaries(secuencia, anatomia)
        inicio, fin = anatomia.utr3
        utr3 = secuencia[inicio - 1 : fin]
        if args.longitud_esperada is not None:
            check_declared_length(
                utr3, args.longitud_esperada, name=f"3'UTR de {args.fasta.name}"
            )
        args.out.mkdir(parents=True, exist_ok=True)
        destino = write_sequence_file(
            utr3,
            directory=args.out,
            stem=f"{args.fasta.stem}_3utr",
            note=(
                f"3'UTR {inicio}-{fin} del transcrito; anatomia por "
                f"{anatomia.source.describe()}"
            ),
        )
    except (ShmirDesignError, OSError, UnicodeDecodeError) as exc:
        # rule2-ok: frontera CLI. No se escribe nada si algo falla.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    print(f"Escrito {destino}")
    print(f"  {len(utr3)} nt — md5 canonico {sequence_md5(utr3)}")
    print("  Sube ESTE fichero. No copies la secuencia de una pantalla: lo que se")
    print("  pierde al copiar son las carreras de homopolimero, y eso no se ve.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
