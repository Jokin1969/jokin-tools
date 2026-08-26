"""Cruza dos corridas de miRarchitect por SITIO sobre el 3'UTR de referencia.

    python3 apps/shmir-design/tools/compare_exports.py \\
        --a corrida_vieja.csv --b corrida_buena.csv \\
        --fasta data/reference/NM_011170.3.fa --utr3-desde 950 \\
        --eje "secuencia de entrada (1246 nt fabricados frente a 1242 verificados)" \\
        --out nota_sensibilidad.txt

Contesta dos preguntas distintas con la misma aritmetica, y por eso `--eje` es
obligatorio:

- **Sensibilidad a la entrada.** Mismo andamio, entrada distinta. Cuanto mueve la
  puntuacion una perturbacion del 0,3 % con el resto de variables identicas.
- **Magnitud del andamio.** Misma entrada, andamio distinto. Mismo sitio, dos
  puntuaciones, y la diferencia atribuible al andamio — con lo que el `NO_ORDENAR` deja
  de ser una prohibicion a ciegas y pasa a tener una magnitud medida.

Con `--out` escribe el bloque a fichero, para que entre en el documento y no solo en el
log. Ese bloque se puede pegar en un informe con `design.py --nota`.

Codigo de salida:
  0  cruzado
  2  no se pudo leer algo

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.fetch import parse_fasta_payload  # noqa: E402
from shmir_design.mirarchitect import compare_exports, parse_export  # noqa: E402
from shmir_design.polya import normalize_sequence  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--a", type=Path, required=True, help="Primer export.")
    parser.add_argument("--b", type=Path, required=True, help="Segundo export.")
    parser.add_argument("--fasta", type=Path, required=True)
    parser.add_argument("--utr3-desde", type=int, required=True)
    parser.add_argument(
        "--eje", required=True,
        help="QUE cambia entre las dos corridas. Obligatorio: la misma cifra significa "
             "una cosa si cambio la entrada y otra si cambio el andamio.",
    )
    parser.add_argument("--out", type=Path, help="Escribe el bloque a fichero.")
    args = parser.parse_args(argv)

    try:
        _, bruta = parse_fasta_payload(
            args.fasta.read_text(encoding="utf-8"), source=str(args.fasta)
        )
        secuencia = normalize_sequence(bruta, name=str(args.fasta))
        utr3 = secuencia[args.utr3_desde - 1 :]
        comparacion = compare_exports(
            parse_export(args.a.read_text(encoding="utf-8-sig"), source=str(args.a)),
            parse_export(args.b.read_text(encoding="utf-8-sig"), source=str(args.b)),
            utr3,
            axis=args.eje,
        )
    except (ShmirDesignError, OSError, UnicodeDecodeError) as exc:
        # rule2-ok: frontera CLI.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    texto = comparacion.format_text()
    print(texto)
    if args.out is not None:
        args.out.write_text(texto + "\n", encoding="utf-8")
        print(f"\nEscrito {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
