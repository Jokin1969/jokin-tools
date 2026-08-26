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

from shmir_design.alignment import align  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.fetch import parse_fasta_payload  # noqa: E402
from shmir_design.mirarchitect import compare_exports, parse_export  # noqa: E402
from shmir_design.polya import normalize_sequence  # noqa: E402
from shmir_design.reference import read_sequence_file  # noqa: E402


def _secuencia(ruta: Path) -> str:
    """Un FASTA, un fichero de `export_utr3.py` (y se le comprueba el md5), o texto."""
    crudo = ruta.read_text(encoding="utf-8")
    if crudo.lstrip().startswith(">"):
        _, crudo = parse_fasta_payload(crudo, source=str(ruta))
        return normalize_sequence(crudo, name=str(ruta))
    if any(l.startswith("#") for l in crudo.splitlines()):
        return read_sequence_file(ruta)
    return normalize_sequence(crudo, name=str(ruta))


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
    parser.add_argument(
        "--entrada-a", type=Path,
        help="La secuencia que se le paso a la PRIMERA corrida. Con las dos entradas se "
             "calculan las posiciones divergentes y la comparacion sale ESTRATIFICADA: "
             "sin ellas no hay estratos y el resultado vale mucho menos.",
    )
    parser.add_argument("--entrada-b", type=Path, help="Lo mismo para la segunda.")
    parser.add_argument("--out", type=Path, help="Escribe el bloque a fichero.")
    args = parser.parse_args(argv)

    try:
        _, bruta = parse_fasta_payload(
            args.fasta.read_text(encoding="utf-8"), source=str(args.fasta)
        )
        secuencia = normalize_sequence(bruta, name=str(args.fasta))
        utr3 = secuencia[args.utr3_desde - 1 :]
        divergentes = frozenset()
        perfil = ""
        alineado = None
        if (args.entrada_a is None) != (args.entrada_b is None):
            raise ShmirDesignError(
                "Hacen falta las DOS entradas o ninguna: con una sola no hay nada que "
                "alinear y no se puede estratificar."
            )
        if args.entrada_a is not None:
            # Cada entrada se alinea contra la REFERENCIA, no una contra otra: los
            # sitios se cruzan por su posicion sobre la referencia, asi que las
            # posiciones divergentes tienen que estar en ESE sistema de coordenadas.
            # Alinear las dos entradas entre si las daria en el de una de ellas.
            alineados = [
                align(utr3, _secuencia(ruta))
                for ruta in (args.entrada_a, args.entrada_b)
            ]
            divergentes = frozenset().union(*(a.ref_positions for a in alineados))
            # Para los tres estados hace falta UN alineamiento con sus carreras. Se usa
            # el de la entrada que difiera de la referencia; si difieren las dos, se
            # avisa de que la clasificacion se hace con la primera.
            con_diferencias = [a for a in alineados if a.differences]
            alineado = con_diferencias[0] if con_diferencias else alineados[0]
            perfil = "\n\n".join(
                f"── Entrada {letra} contra la referencia ──\n" + a.format_text()
                for letra, a in zip("AB", alineados)
                if a.differences
            )
            if len(con_diferencias) > 1:
                perfil += (
                    "\n\n  OJO: las DOS entradas difieren de la referencia. Los tres "
                    "estados se calculan\n  con el alineamiento de la primera; las "
                    "posiciones divergentes son la union de las dos."
                )
        comparacion = compare_exports(
            parse_export(args.a.read_text(encoding="utf-8-sig"), source=str(args.a)),
            parse_export(args.b.read_text(encoding="utf-8-sig"), source=str(args.b)),
            utr3,
            axis=args.eje,
            divergent_positions=divergentes,
            alignment=alineado,
        )
    except (ShmirDesignError, OSError, UnicodeDecodeError) as exc:
        # rule2-ok: frontera CLI.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    texto = (perfil + "\n\n" if perfil else "") + comparacion.format_text()
    print(texto)
    if args.out is not None:
        args.out.write_text(texto + "\n", encoding="utf-8")
        print(f"\nEscrito {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
