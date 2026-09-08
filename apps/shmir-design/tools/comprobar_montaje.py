#!/usr/bin/env python3
"""Comprueba el plásmido MONTADO A MANO contra lo que emitió la app.

No genera ningún plásmido: un vector de 5.400 pb ensamblado por código es demasiada
superficie para un error silencioso. Lo que hace es cerrar el último eslabón sin red —
entre lo que la app emite y lo que acaba en el vector no había ninguna comprobación.

Compara POR SECUENCIA, no por coordenadas: busca el fragmento dentro del plásmido y lo
contrasta letra por letra. Una feature corrida un nucleótido no lo engaña.

Uso:

    python3 tools/comprobar_montaje.py --plasmido montado.dna \\
        --fragmentos salida/mouse_fragmentos.fasta

El plásmido puede venir en GenBank, FASTA, secuencia pelada o `.dna` de SnapGene. Sale
con código 1 si alguna comprobación FALLA, para que valga en un guion.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.filters import FilterState  # noqa: E402
from shmir_design.montaje import check_before_pasting, verify_assembly  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plasmido", required=True,
        help="el plásmido montado: GenBank, FASTA, secuencia pelada o `.dna`",
    )
    parser.add_argument(
        "--fragmentos", required=True,
        help="el FASTA de fragmentos que emitió la app (`<especie>_fragmentos.fasta`)",
    )
    parser.add_argument(
        "--antes-de-pegar", action="store_true",
        help="el plásmido que se da es el RECEPTOR, todavía sin el fragmento: "
             "comprueba QUÉ INTRÓN lleva y si el fragmento va ahí. Es la pregunta que "
             "hay que hacerse mientras todavía se puede no pegar, y no se puede "
             "reconstruir después: sobre el montado el intrón anterior ya no está.",
    )
    parser.add_argument(
        "--cambio-de-arquitectura", action="store_true",
        help="con --antes-de-pegar: declara que la sustitución cambia de intrón a "
             "propósito. Sin declararlo, una cruzada es FAIL; declarándolo, lo que "
             "falla es que no haya cambio.",
    )
    parser.add_argument(
        "--intron-previo", default="",
        help="el intrón que había ANTES, si no es el del casete parental. Encontrarlo "
             "todavía dentro es el fallo que esto caza: pegado al lado en vez de encima.",
    )
    args = parser.parse_args(argv)

    try:
        crudo = Path(args.plasmido).read_bytes()
        fasta = Path(args.fragmentos).read_text(encoding="utf-8")
        if args.antes_de_pegar:
            informe = check_before_pasting(
                crudo, fasta,
                architecture_change=args.cambio_de_arquitectura,
                name=Path(args.plasmido).name,
            )
        else:
            informe = verify_assembly(
                crudo, fasta,
                name=Path(args.plasmido).name,
                previous_intron=args.intron_previo,
            )
    except (ShmirDesignError, OSError) as exc:
        # rule2-ok: frontera CLI. El fallo sale entero por stderr y con codigo 2; no se
        # imprime un informe a medias que parezca una comprobacion hecha.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    print(informe.render())
    return 1 if informe.verdict_state is FilterState.FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
