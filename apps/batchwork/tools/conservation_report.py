"""Informe de bloques conservados entre los 3'UTR de dos especies (paso 14).

    python3 apps/batchwork/tools/conservation_report.py \\
        apps/batchwork/tests/data/mouse_3utr.fasta \\
        apps/batchwork/tests/data/human_3utr.fasta

Los bloques se imprimen SIEMPRE, aunque ninguna ventana pase los filtros: la decision
de usarlos es del usuario. Los FASTA se obtienen con `tools/fetch_data.py`, que
verifica los checksums; este programa no descarga nada.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from batchwork.conservation import (  # noqa: E402
    MIN_BLOCK_LENGTH,
    Utr3,
    build_conservation_report,
)
from batchwork.errors import BatchworkError  # noqa: E402
from batchwork.hard_filters import WINDOW_SIZE  # noqa: E402
from batchwork.polya import read_fasta_sequence  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("fasta_a", type=Path, help="3'UTR de la primera especie")
    parser.add_argument("fasta_b", type=Path, help="3'UTR de la segunda especie")
    parser.add_argument("--name-a", default="especie_a")
    parser.add_argument("--name-b", default="especie_b")
    parser.add_argument("--min-length", type=int, default=MIN_BLOCK_LENGTH)
    parser.add_argument("--window-size", type=int, default=WINDOW_SIZE)
    args = parser.parse_args(argv)

    try:
        report = build_conservation_report(
            Utr3(args.name_a, read_fasta_sequence(args.fasta_a)),
            Utr3(args.name_b, read_fasta_sequence(args.fasta_b)),
            min_length=args.min_length,
            window_size=args.window_size,
        )
    except (BatchworkError, ValueError) as exc:
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
