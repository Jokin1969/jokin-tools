"""Salida de oligos: monta la horquilla miR-E de 97 nt lista para pedir.

    python3 apps/shmir-design/tools/oligo.py --guide UAAAGUGCAAGCCAAUAAUAAC
    python3 apps/shmir-design/tools/oligo.py --target GTTATTATTGGCTTGCACTTTG

Con `--target` se transforma primero la diana en guia (complementario reverso con la U
forzada en la posicion 1, paso 6). Con `--guide` se toma la guia tal cual, en ARN o ADN.

El andamio (flancos y loop) esta verificado contra SGEP #111170. La regla del
desapareamiento de la pasajera NO lo esta: sale un aviso en cada oligo y no debe
darse por buena hasta verificarla contra un segundo plasmido miR-E (#111177).

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.hard_filters import evaluate_window, guide_from_target  # noqa: E402
from shmir_design.folding import check_fold  # noqa: E402
from shmir_design.gblock import build_gblock  # noqa: E402
from shmir_design.scaffold import build_hairpin  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--guide", help="Guia de 22 nt (ARN o ADN)")
    parser.add_argument("--target", help="Ventana diana de 22 nt")
    parser.add_argument(
        "--skip-filters",
        action="store_true",
        help="No evaluar los filtros de la ventana diana antes de montar el oligo",
    )
    args = parser.parse_args(argv)

    if bool(args.guide) == bool(args.target):
        print(
            "oligo: pasa --guide o --target, uno de los dos.",
            file=sys.stderr,
        )
        return 2

    try:
        if args.target:
            evaluacion = None if args.skip_filters else evaluate_window(args.target)
            guide = guide_from_target(args.target)
        else:
            evaluacion, guide = None, args.guide

        hairpin = build_hairpin(guide)
    except (ShmirDesignError, ValueError) as exc:
        # rule2-ok: frontera CLI. El fallo se imprime entero en stderr y sale con
        # codigo 2; no se imprime ningun oligo a medias, que es lo unico que alguien
        # podria acabar pidiendo a un sintetizador.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    if evaluacion is not None:
        print(f"Ventana diana {evaluacion.sequence} — veredicto {evaluacion.verdict.value}")
        for resultado in evaluacion.filters:
            print(f"  {resultado.name:<13} {resultado.state.value:<7} {resultado.reason}")
        print()

    print(hairpin.format_text())
    print()
    plegado = check_fold(hairpin)
    print(f"  plegado        {plegado.state.value:<7} {plegado.reason}")
    print()
    print(build_gblock(hairpin).format_text())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
