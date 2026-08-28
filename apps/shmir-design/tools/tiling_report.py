"""Tiling del 3'UTR: contadores de referencia y TSV completo (pasos 3 y 15).

Sin argumentos trocea los dos 3'UTR de referencia, extraidos de los fixtures de
`data/reference/` y verificados por checksum al cargarlos. No toca la red.

    python3 apps/shmir-design/tools/tiling_report.py
    python3 apps/shmir-design/tools/tiling_report.py --bootstrap-seeds --tsv salida/

Dos contadores DISTINTOS, a proposito:

  biofisicos_ok  ventanas que superan todos los filtros biofisicos (GC, homopolimero,
                 asimetria, G4 diana, G4 guia, zona prohibida de poliadenilacion)
  aptas          ventanas con veredicto PASS, que ademas superan los externos

Con miRBase ausente `aptas` es 0: la seed queda en NOT_RUN y NOT_RUN no es PASS.

`--bootstrap-seeds` carga una lista de 12 seeds que sirve para probar la mecanica y
NO para cribar candidatos. El filtro real necesita `mature.fa` de miRBase completo.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.polya import read_fasta_sequence  # noqa: E402
from shmir_design.reference import REFERENCES, load_3utr  # noqa: E402
from shmir_design.seeds import BOOTSTRAP_SEEDS, parse_seed_table  # noqa: E402
from shmir_design.tiling import tile_utr  # noqa: E402

DEFAULT_PAIR = {"raton": "NM_011170.3", "humano": "NM_000311.5"}


def load_seed_set(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer el fichero de seeds {path} ({exc}); se aborta el tiling "
            f"en vez de correr con el filtro de seed a medias."
        ) from exc
    return parse_seed_table(text, source=str(path))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--fasta", type=Path, help="3'UTR suelto en FASTA")
    parser.add_argument("--name", default="3utr", help="Nombre para --fasta")
    parser.add_argument(
        "--bootstrap-seeds",
        action="store_true",
        help="Usar la lista de arranque de 12 seeds (mecanica, NO filtro real)",
    )
    parser.add_argument("--tsv", type=Path, help="Directorio donde escribir los TSV")
    args = parser.parse_args(argv)

    try:
        # Sin `--seeds`: una tabla suelta no trae procedencia, y el filtro real sale
        # de `mature.fa` por el gestor. Lo unico que queda es la lista de ARRANQUE, que
        # ya lleva su fecha de caducidad declarada (`seeds.bootstrap_expiry_note`).
        seeds = BOOTSTRAP_SEEDS if args.bootstrap_seeds else None

        if args.fasta:
            entradas = {args.name: read_fasta_sequence(args.fasta)}
        else:
            entradas = {
                nombre: load_3utr(REFERENCES[accession])
                for nombre, accession in DEFAULT_PAIR.items()
            }

        for nombre, secuencia in entradas.items():
            report = tile_utr(secuencia, seeds=seeds)
            print(f"\n── {nombre} ──")
            print(report.format_text())
            if args.tsv:
                args.tsv.mkdir(parents=True, exist_ok=True)
                destino = args.tsv / f"{nombre}_ventanas.tsv"
                destino.write_text(report.format_tsv() + "\n", encoding="utf-8")
                print(f"  TSV: {destino}")
    except (ShmirDesignError, ValueError) as exc:
        # rule2-ok: frontera CLI. El fallo se imprime entero en stderr y sale con
        # codigo 2; no se imprime ningun conteo parcial que pueda leerse como bueno.
        print(f"\nPARA — {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
