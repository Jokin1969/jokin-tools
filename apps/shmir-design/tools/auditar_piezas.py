"""¿Lo que cada pieza del módulo dice de dónde viene se sostiene contra el fichero?

Sale de lo que se pidió «de paso» al hacer del plásmido de SGEP un fichero de primera
clase: **audita si queda algún dato más en esa situación**. De las 12 piezas de
`blocks.PIECES`, sólo dos declaraban coordenadas en un plásmido —los dos contextos, que
ahora se DERIVAN—. Lo que apareció al mirar las otras diez es de otra clase: **diez dicen
de dónde vienen y nadie lo estaba comprobando**, teniendo el fichero en el depósito.

**Es un INFORME, no un guardia**, y la distinción importa: aquí el número correcto NO es
cero. `NO_ESTA` es un estado legítimo cuando la procedencia ya no afirma lo contrario —
las dianas de clonaje no están en el receptor y eso es coherente, porque el parental lleva
el intrón vacío—. Lo que aborta es `tests/test_el_plasmido_de_SGEP_es_de_primera_clase.py`,
que fija los estados MEDIDOS: si una pieza cambia de estado, el test lo dice.

Lo que este informe sí hace es que una pieza NUEVA con una procedencia que ningún fichero
sostiene salga a la vista el día que se añade, y no tres meses después.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design.blocks import audit_pieces_against_plasmids  # noqa: E402


@dataclass(frozen=True)
class Informe:
    filas: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def por_estado(self) -> dict[str, int]:
        cuenta: dict[str, int] = {}
        for fila in self.filas:
            cuenta[str(fila["estado"])] = cuenta.get(str(fila["estado"]), 0) + 1
        return dict(sorted(cuenta.items()))


def auditar() -> Informe:
    return Informe(filas=tuple(audit_pieces_against_plasmids()))


def render(informe: Informe) -> str:
    lineas = ["", "  Procedencia de las piezas del módulo, contra los plásmidos:"]
    for estado, n in informe.por_estado.items():
        lineas.append(f"    {n:>3}  {estado}")
    sospechosas = [f for f in informe.filas if f["estado"] in ("NO_ESTA", "AMBIGUA")]
    for fila in sospechosas:
        lineas.append(f"    ·  {fila['pieza']}: {fila['detalle']}")
    lineas.append("")
    lineas.append(
        "  Es un INFORME: aquí el número correcto NO es cero. Lo que fija los estados "
        "medidos es el test."
    )
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    print(render(auditar()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
