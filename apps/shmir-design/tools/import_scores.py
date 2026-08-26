"""Mete en la tabla comparativa scores puntuados FUERA de este programa.

    python3 apps/shmir-design/tools/import_scores.py \\
        --fuente mirarchitect --tsv resultados.tsv \\
        --comparativa raton_comparativa.tsv --out raton_con_scores.tsv

El fichero de resultados son dos columnas, `guia<TAB>score`, tal y como se copian del
formulario de miRarchitect (ver el bloque «Score externo» del informe). Las guias pueden
venir en ADN o en ARN.

Este programa NO calcula ningun score y no hay forma de que lo haga: la unica fuente
aceptada es `mirarchitect`, que se escribe como `manual_mirarchitect` en la columna
`fuente_score`. Un numero calculado aqui con etiqueta ajena seria el peor resultado
posible, igual que una secuencia inventada.

Sin `--out` la tabla resultante va a la salida estandar y el fichero de entrada no se
toca. El resumen va siempre a stderr, asi que se puede redirigir la tabla sin mezclarlos.

Codigo de salida:
  0  scores importados
  2  no se pudo leer algo, o los dos ficheros no son de la misma corrida

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.external_score import ScoreSource, merge_scores  # noqa: E402
from shmir_design.scaffold import SGEP_SCAFFOLD  # noqa: E402

#: Lo que se puede importar y con que etiqueta queda. Solo hay puntuaciones HECHAS A
#: MANO en un servicio externo: no existe ninguna opcion que escriba `splashrna_features`
#: ni nada calculado en este repositorio.
FUENTES = {"mirarchitect": ScoreSource.MANUAL_MIRARCHITECT}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--fuente", required=True, choices=sorted(FUENTES),
        help="De donde salieron los scores. Solo puntuaciones externas hechas a mano.",
    )
    parser.add_argument(
        "--tsv", type=Path, required=True,
        help="TSV de dos columnas `guia<TAB>score` copiado del servicio.",
    )
    parser.add_argument(
        "--comparativa", type=Path, required=True,
        help="La tabla comparativa de la corrida (`<especie>_comparativa.tsv`).",
    )
    parser.add_argument(
        "--andamio", required=True,
        help="Con que andamio se puntuo el fichero (p. ej. miR-30a). Obligatorio: un "
             "score de procesamiento medido sobre otro andamio no ordena estos "
             "candidatos, y suponer que coincide es lo que no se puede hacer.",
    )
    parser.add_argument(
        "--offset", type=int,
        help="Cuanto hay que sumar a las coordenadas de la fuente para llevarlas a las "
             "del transcrito (p. ej. 949 si la fuente numera sobre el 3'UTR). NO se "
             "usa para cruzar —el cruce va por secuencia— pero queda escrito en "
             "fuente_score, porque un score cruzado con offset y otro sin el no son el "
             "mismo dato.",
    )
    parser.add_argument(
        "--out", type=Path,
        help="Donde escribir la tabla con los scores. Sin esto va a stdout y el "
             "fichero de entrada no se toca.",
    )
    args = parser.parse_args(argv)

    try:
        resultado = merge_scores(
            args.comparativa.read_text(encoding="utf-8"),
            args.tsv.read_text(encoding="utf-8"),
            source=FUENTES[args.fuente],
            source_name=str(args.tsv),
            offset=args.offset,
            file_scaffold=args.andamio,
            design_scaffold=SGEP_SCAFFOLD.name,
        )
    except (ShmirDesignError, OSError, UnicodeDecodeError) as exc:
        # rule2-ok: frontera CLI. No se escribe NADA si algo falla: media tabla
        # importada seria peor que ninguna.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    if args.out is None:
        print(resultado.text, end="")
    else:
        args.out.write_text(resultado.text, encoding="utf-8")
        print(f"Escrito {args.out}", file=sys.stderr)
    print(resultado.format_text(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
