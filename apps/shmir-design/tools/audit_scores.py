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

from shmir_design.audit import Span, audit_scores  # noqa: E402
from shmir_design.mirarchitect import parse_export  # noqa: E402
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
    fuente = parser.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--tsv", type=Path, help="Fichero de scores de dos columnas.")
    fuente.add_argument(
        "--csv", type=Path,
        help="Export limpio de miRarchitect. Trae la diana, asi que el sitio se toma "
             "de ella y el match es EXACTO sobre 22 nt, sin descartar la posicion 1.",
    )
    parser.add_argument("--fasta", type=Path, required=True, help="FASTA del transcrito.")
    parser.add_argument(
        "--guardar-sitios", type=Path,
        help="Escribe un TSV con las guias que SI existen en la referencia y la "
             "coordenada de su match (no la que declara el fichero). Sirve para "
             "cruzarlas despues contra otra corrida.",
    )
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
        utr3 = secuencia[args.utr3_desde - 1 :]
        if args.csv is not None:
            export = parse_export(
                args.csv.read_text(encoding="utf-8-sig"), source=str(args.csv)
            )
            filas = [(f.guide, f.score) for f in export.rows]
            # Con la diana en el fichero, el sitio se toma de ella: match exacto de los
            # 22 nt, sin el atajo de descartar la posicion 1.
            sitios = [
                (f.guide, Span.of(utr3.find(f.target) + 1, f.target))
                for f in export.rows
                if utr3.find(f.target) >= 0
            ]
        else:
            filas = _scores(args.tsv.read_text(encoding="utf-8"), source=str(args.tsv))
            sitios = None
        auditoria = audit_scores(filas, utr3)
        if sitios is None:
            sitios = [(e.guide, e.span) for e in auditoria.entries if e.span is not None]
    except (ShmirDesignError, OSError, UnicodeDecodeError) as exc:
        # rule2-ok: frontera CLI. Sin poder leer, no se audita nada.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    print(auditoria.format_text())
    if args.guardar_sitios is not None:
        filas = ["guia\tinicio_3utr\tfin_3utr\tlongitud"]
        filas += [
            f"{guia}\t{v.start}\t{v.end}\t{v.length}" for guia, v in sitios
        ]
        args.guardar_sitios.write_text("\n".join(filas) + "\n", encoding="utf-8")
        print(f"\nEscrito {args.guardar_sitios} con {len(filas) - 1} sitio(s).")
        print("  La coordenada es la del MATCH sobre la referencia, no la que declara")
        print("  el fichero. Esa es la unica que sirve para cruzar dos corridas.")
    problemas = (
        any(not e.maps for e in auditoria.entries)
        or any(e.prefix_of for e in auditoria.entries)
        or bool(auditoria.sites_absent_from_reference)
    )
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
