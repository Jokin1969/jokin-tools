"""Diseño completo: del 3'UTR a los oligos, en el orden de operaciones fijado.

    python3 apps/shmir-design/tools/design.py --out salida/

Sin `--fasta` usa los dos 3'UTR de referencia, extraidos de los fixtures de
`data/reference/` y verificados por checksum. No toca la red.

Orden de operaciones (no se cambia):

  1. enmascarar repeticiones y RETILAR
  2. aplicar todos los filtros duros
  3. ordenar los supervivientes por asimetria
  4. agrupar ventanas contiguas en sitios independientes
  5. seleccion voraz: espaciado minimo de 50 nt entre sitios elegidos y cuota de al
     menos un candidato por tercio del 3'UTR

Escribe por especie: TSV de todas las ventanas con el estado de cada filtro, TSV de
seleccionados, FASTA de guias para BLAST, TSV de oligos ensamblados e informe de texto.

Mientras haya filtros en NOT_RUN la seleccion es PROVISIONAL y ningun candidato esta
aprobado. El informe lo dice y los TSV lo llevan en una columna.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.conservation import (  # noqa: E402
    MIN_BLOCK_LENGTH,
    Utr3,
    build_conservation_report,
)
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.hard_filters import DEFAULT_THRESHOLDS, Thresholds  # noqa: E402
from shmir_design.masking import load_mask_file  # noqa: E402
from shmir_design.outputs import (  # noqa: E402
    fasta_guides,
    text_report,
    tsv_all_windows,
    tsv_oligos,
    tsv_selected,
)
from shmir_design.polya import read_fasta_sequence  # noqa: E402
from shmir_design.reference import REFERENCES, load_3utr  # noqa: E402
from shmir_design.scaffold import SGEP_SCAFFOLD, load_scaffold  # noqa: E402
from shmir_design.seeds import BOOTSTRAP_SEEDS, parse_seed_table  # noqa: E402
from shmir_design.selection import SelectionConfig, select_from_report  # noqa: E402
from shmir_design.tiling import tile_utr  # noqa: E402

DEFAULT_PAIR = {"raton": "NM_011170.3", "humano": "NM_000311.5"}


def load_seeds(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer el fichero de seeds {path} ({exc}); se aborta el diseño."
        ) from exc
    return parse_seed_table(text, source=str(path))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, help="Directorio de salida (obligatorio)")
    parser.add_argument("--fasta", type=Path, help="3'UTR suelto en FASTA")
    parser.add_argument("--name", default="3utr", help="Nombre de especie para --fasta")
    parser.add_argument(
        "--fasta-b", type=Path, help="Segundo 3'UTR: compara las dos especies"
    )
    parser.add_argument("--name-b", default="especie_b", help="Nombre para --fasta-b")
    parser.add_argument("--candidates", type=int, default=SelectionConfig().n_candidates)
    parser.add_argument("--min-spacing", type=int, default=SelectionConfig().min_spacing)
    parser.add_argument("--scaffold", type=Path, help="Andamio en TOML")
    parser.add_argument("--seeds", type=Path, help="Tabla de seeds `seed familia`")
    parser.add_argument("--bootstrap-seeds", action="store_true")
    parser.add_argument("--repeats", type=Path, help="Intervalos repetitivos `inicio fin`")
    parser.add_argument("--min-block", type=int, default=MIN_BLOCK_LENGTH)
    parser.add_argument("--gc-min", type=float, default=DEFAULT_THRESHOLDS.gc_min)
    parser.add_argument("--gc-max", type=float, default=DEFAULT_THRESHOLDS.gc_max)
    parser.add_argument(
        "--max-homopolymer", type=int, default=DEFAULT_THRESHOLDS.max_homopolymer
    )
    parser.add_argument(
        "--min-asymmetry", type=float, default=DEFAULT_THRESHOLDS.min_asymmetry
    )
    parser.add_argument(
        "--polya-flank", type=int, default=DEFAULT_THRESHOLDS.polya_flank
    )
    args = parser.parse_args(argv)

    if args.out is None:
        print("design: falta --out con el directorio de salida.", file=sys.stderr)
        return 2
    if args.seeds and args.bootstrap_seeds:
        print("design: --seeds y --bootstrap-seeds son excluyentes.", file=sys.stderr)
        return 2
    if args.fasta_b and not args.fasta:
        print(
            "design: --fasta-b necesita --fasta; son las dos especies que se comparan.",
            file=sys.stderr,
        )
        return 2

    try:
        scaffold = load_scaffold(args.scaffold) if args.scaffold else SGEP_SCAFFOLD
        seeds = BOOTSTRAP_SEEDS if args.bootstrap_seeds else None
        if args.seeds:
            seeds = load_seeds(args.seeds)
        mask = load_mask_file(args.repeats) if args.repeats else None
        config = SelectionConfig(
            n_candidates=args.candidates, min_spacing=args.min_spacing
        )
        thresholds = Thresholds(
            gc_min=args.gc_min,
            gc_max=args.gc_max,
            max_homopolymer=args.max_homopolymer,
            min_asymmetry=args.min_asymmetry,
            polya_flank=args.polya_flank,
        )

        if args.fasta:
            secuencias = {args.name: read_fasta_sequence(args.fasta)}
            transcripts = {args.name: None}
            if args.fasta_b:
                if args.name_b == args.name:
                    raise ValueError(
                        f"Las dos especies se llaman igual ({args.name!r}); se aborta "
                        f"para no mezclar sus salidas."
                    )
                secuencias[args.name_b] = read_fasta_sequence(args.fasta_b)
                transcripts[args.name_b] = None
        else:
            secuencias = {
                nombre: load_3utr(REFERENCES[accession])
                for nombre, accession in DEFAULT_PAIR.items()
            }
            transcripts = {
                nombre: REFERENCES[accession]
                for nombre, accession in DEFAULT_PAIR.items()
            }

        conservation = None
        if len(secuencias) == 2:
            (nombre_a, seq_a), (nombre_b, seq_b) = secuencias.items()
            conservation = build_conservation_report(
                Utr3(nombre_a, seq_a),
                Utr3(nombre_b, seq_b),
                min_length=args.min_block,
                thresholds=thresholds,
            )

        args.out.mkdir(parents=True, exist_ok=True)
        for especie, secuencia in secuencias.items():
            tiling = tile_utr(
                secuencia, seeds=seeds, mask=mask, thresholds=thresholds
            )
            seleccion = select_from_report(tiling, config)
            informe = text_report(
                species=especie,
                tiling=tiling,
                selection=seleccion,
                scaffold=scaffold,
                transcript=transcripts[especie],
                conservation=conservation,
            )
            salidas = {
                f"{especie}_ventanas.tsv": tsv_all_windows(tiling),
                f"{especie}_seleccionados.tsv": tsv_selected(seleccion, species=especie),
                f"{especie}_guias.fasta": fasta_guides(seleccion, species=especie),
                f"{especie}_oligos.tsv": tsv_oligos(
                    seleccion, scaffold, species=especie
                ),
                f"{especie}_informe.txt": informe,
            }
            for nombre, contenido in salidas.items():
                (args.out / nombre).write_text(contenido + "\n", encoding="utf-8")
            print(informe)
            print(f"\n  Escrito en {args.out}: {', '.join(sorted(salidas))}\n")
    except (ShmirDesignError, ValueError, OSError) as exc:
        # rule2-ok: frontera CLI. El fallo se imprime entero en stderr y sale con
        # codigo 2; no se deja un directorio de salida a medias que parezca un diseño
        # terminado.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
