"""Informe de bloques conservados entre los 3'UTR de dos especies (paso 14).

    python3 apps/shmir-design/tools/conservation_report.py

Sin argumentos compara los dos 3'UTR de referencia, extraidos de los fixtures de
`data/reference/` y verificados por checksum al cargarlos. Con `--fasta-a` y `--fasta-b`
compara dos FASTA cualesquiera (los dos, o ninguno).

Los bloques se imprimen SIEMPRE, aunque ninguna ventana pase los filtros: la decision
de usarlos es del usuario. Este programa no toca la red.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.conservation import (  # noqa: E402
    MIN_BLOCK_LENGTH,
    Utr3,
    build_conservation_report,
)
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.hard_filters import WINDOW_SIZE  # noqa: E402
from shmir_design.polya import read_fasta_sequence  # noqa: E402
from shmir_design.reference import REFERENCES, load_3utr  # noqa: E402

DEFAULT_PAIR = ("NM_011170.3", "NM_000311.5")
DEFAULT_NAMES = {"NM_011170.3": "raton", "NM_000311.5": "humano"}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--fasta-a", type=Path, help="3'UTR de la primera especie")
    parser.add_argument("--fasta-b", type=Path, help="3'UTR de la segunda especie")
    parser.add_argument("--name-a", default="especie_a")
    parser.add_argument("--name-b", default="especie_b")
    parser.add_argument("--min-length", type=int, default=MIN_BLOCK_LENGTH)
    parser.add_argument("--window-size", type=int, default=WINDOW_SIZE)
    args = parser.parse_args(argv)

    if bool(args.fasta_a) != bool(args.fasta_b):
        print(
            "conservation_report: --fasta-a y --fasta-b van juntos; sin ninguno de los "
            "dos se comparan los 3'UTR de referencia.",
            file=sys.stderr,
        )
        return 2

    try:
        if args.fasta_a:
            utr_a = Utr3(args.name_a, read_fasta_sequence(args.fasta_a))
            utr_b = Utr3(args.name_b, read_fasta_sequence(args.fasta_b))
        else:
            utr_a, utr_b = (
                Utr3(DEFAULT_NAMES[accession], load_3utr(REFERENCES[accession]))
                for accession in DEFAULT_PAIR
            )
        report = build_conservation_report(
            utr_a,
            utr_b,
            min_length=args.min_length,
            window_size=args.window_size,
        )
    except (ShmirDesignError, ValueError) as exc:
        # rule2-ok: frontera CLI. El fallo se imprime entero en stderr y sale con
        # codigo 2; no se imprime ningun informe parcial que pueda leerse como bueno.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    print(report.format_text())
    if report.passing_windows() == 0 and report.blocks:
        print(
            "\nNinguna ventana pasa todos los filtros. Los bloques siguen siendo "
            "candidatos de alto valor: decides tu.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
