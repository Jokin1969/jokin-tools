"""Estado de `data/reference/`: que hay, que falta y que filtros podran correr.

    python3 apps/shmir-design/tools/check_data.py
    python3 apps/shmir-design/tools/check_data.py --dir otra/carpeta --tsv

No lanza ningun diseño ni escribe nada: valida el directorio contra su manifiesto y
imprime la tabla. Sirve para saber en diez segundos si merece la pena correr.

Codigo de salida:
  0  todo registrado y comprobado
  1  falta algun fichero, o hay alguno presente sin registrar en el manifiesto
  2  algun fichero NO es el que dice ser, o no se pudo leer el manifiesto

Python 3.11+ (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.manifest import (  # noqa: E402
    EntryStatus,
    check_directory,
)

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "reference"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dir", type=Path, default=DEFAULT_DIR,
        help="Directorio a comprobar (por defecto, data/reference/).",
    )
    parser.add_argument(
        "--tsv", action="store_true", help="Salida en TSV en vez de tabla legible."
    )
    args = parser.parse_args(argv)

    try:
        estado = check_directory(args.dir)
    except (ShmirDesignError, OSError) as exc:
        # rule2-ok: frontera CLI. Sin manifiesto no se puede decir nada del directorio.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    if args.tsv:
        filas = ["nombre\testado\tfiltro\tmd5_manifiesto\tmd5_calculado\tdetalle"]
        for resultado in sorted(estado.results, key=lambda r: r.entry.name):
            filas.append(
                "\t".join(
                    (
                        resultado.entry.name,
                        resultado.status.value,
                        resultado.entry.filter_name,
                        resultado.entry.md5,
                        resultado.computed_md5,
                        resultado.detail.replace("\t", " "),
                    )
                )
            )
        print("\n".join(filas))
    else:
        print(estado.format_text())

    if estado.mismatched:
        return 2
    if any(r.status is not EntryStatus.OK for r in estado.results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
