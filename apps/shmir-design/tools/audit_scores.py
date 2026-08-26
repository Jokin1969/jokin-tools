"""Audita un fichero de scores externo contra el 3'UTR de referencia.

    python3 apps/shmir-design/tools/audit_scores.py \\
        --tsv data/reference/mirarchitect_prnp_raton.tsv \\
        --fasta data/reference/NM_011170.3.fa --utr3-desde 950

No cruza nada ni escribe ninguna tabla: solo dice que le pasa al fichero. Tabula las
longitudes, dice que guias no mapean sobre el 3'UTR y como se restauran, si alguna fila
es prefijo de otra, y si hay sitios de restriccion que no estan en el 3'UTR — señal de
que se ha colado contexto de clonaje donde deberia haber guia.

Ningun intervalo se escribe a mano: se derivan y se comprueban (`audit.Span`).

Codigo de salida:
  0  todas las guias mapean
  1  alguna no mapea, o hay filas duplicadas, o hay sitios ajenos
  2  no se pudo leer algo

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.audit import audit_scores  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.fetch import parse_fasta_payload  # noqa: E402
from shmir_design.polya import normalize_sequence  # noqa: E402


def _scores(texto: str, *, source: str) -> list[tuple[str, float]]:
    filas: list[tuple[str, float]] = []
    for numero, cruda in enumerate(texto.splitlines(), start=1):
        linea = cruda.strip()
        if not linea or linea.startswith("#"):
            continue
        campos = linea.split("\t")
        if len(campos) < 2 or campos[0].upper() in ("GUIA", "GUIA_DNA", "GUIDE"):
            if len(campos) < 2:
                raise ShmirDesignError(
                    f"{source}, linea {numero}: se esperaban dos columnas y llego "
                    f"{linea!r}."
                )
            continue
        try:
            filas.append((campos[0], float(campos[1])))
        except ValueError as exc:
            raise ShmirDesignError(
                f"{source}, linea {numero}: {campos[1]!r} no es un numero."
            ) from exc
    return filas


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tsv", type=Path, required=True, help="Fichero de scores.")
    parser.add_argument("--fasta", type=Path, required=True, help="FASTA del transcrito.")
    parser.add_argument(
        "--utr3-desde", type=int, required=True,
        help="Primera posicion del 3'UTR sobre el transcrito, 1-based. No se adivina.",
    )
    args = parser.parse_args(argv)

    try:
        _, bruta = parse_fasta_payload(
            args.fasta.read_text(encoding="utf-8"), source=str(args.fasta)
        )
        secuencia = normalize_sequence(bruta, name=str(args.fasta))
        if not 1 <= args.utr3_desde <= len(secuencia):
            raise ShmirDesignError(
                f"--utr3-desde {args.utr3_desde} cae fuera de una secuencia de "
                f"{len(secuencia)} nt."
            )
        auditoria = audit_scores(
            _scores(args.tsv.read_text(encoding="utf-8"), source=str(args.tsv)),
            secuencia[args.utr3_desde - 1 :],
        )
    except (ShmirDesignError, OSError, UnicodeDecodeError) as exc:
        # rule2-ok: frontera CLI. Sin poder leer, no se audita nada.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    print(auditoria.format_text())
    problemas = (
        any(not e.maps for e in auditoria.entries)
        or any(e.prefix_of for e in auditoria.entries)
        or bool(auditoria.sites_absent_from_reference)
    )
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
