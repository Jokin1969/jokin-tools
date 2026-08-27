#!/usr/bin/env python3
"""Barrido de longitudes de espaciador sobre un intrón: emite la CURVA entera.

No elige nada. Emite, para cada longitud probada, la accesibilidad de los tres elementos
frágiles —donante, punto de ramificación y tracto— y el donante→punto resultante, con la
dispersión entre varias secuencias de la misma longitud. Ver `shmir_design/barrido.py`
para por qué hay réplicas y por qué el criterio es relativo y no un umbral.

    python3 tools/barrer_espaciadores.py [intrón]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design import barrido, blocks  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402

#: 5' AGRESIVO: paso fino abajo, que es donde interesa saber si se puede recortar.
#: 3' CONSERVADOR: paso fino arriba, que es donde quedarse corto cuesta el empalme.
LARGOS_5 = (0, 2, 4, 6, 8, 10, 12, 15, 20, 30, 45)
LARGOS_3 = (0, 10, 20, 25, 30, 35, 40, 45)

#: La guía de referencia del proyecto. El módulo cambia con ella, y el plegado también:
#: esto es UNA corrida, no un resultado general.
GUIA = "TATTTAATGTCAGTCTGATAGC"


def main(argv=None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    intron = argumentos[0] if argumentos else "mvm_actual"
    modulo = blocks.build_block(GUIA, available=False).module
    print(__doc__)
    print(f"Intrón: {intron} · módulo de {len(modulo)} nt (guía {GUIA})")
    print("=" * 78)
    for lado, largos, otro in (
        ("5", LARGOS_5, barrido.STARTING_POINT["3"]),
        ("3", LARGOS_3, barrido.STARTING_POINT["5"]),
    ):
        try:
            curva = barrido.sweep_side(
                intron, side=lado, lengths=largos, other=otro, module=modulo
            )
        except ShmirDesignError as exc:
            # rule2-ok: el motivo entero va al informe, que es la salida de esto.
            print(f"\nLado {lado}': NO SE PUDO BARRER. {exc}")
            continue
        print()
        print("\n".join(curva.describe()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
