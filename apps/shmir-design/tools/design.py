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

from shmir_design.apa import load_apa_sites  # noqa: E402
from shmir_design.anatomy import (  # noqa: E402
    Anatomy,
    Region,
    TileRange,
    RegionSource,
    check_cds_boundaries,
    cds_stop_codon_ok,
)
from shmir_design.genbank import load_genbank_cds  # noqa: E402
from shmir_design.conservation import (  # noqa: E402
    MIN_BLOCK_LENGTH,
    Utr3,
    build_conservation_report,
)
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.hard_filters import DEFAULT_THRESHOLDS, Thresholds  # noqa: E402
from shmir_design.masking import load_mask_file, load_rmsk  # noqa: E402
from shmir_design.outputs import (  # noqa: E402
    fasta_guides,
    text_report,
    tsv_all_windows,
    tsv_oligos,
    tsv_selected,
)
from shmir_design.orf import (  # noqa: E402
    find_orfs,
    format_cds_suggestion,
    propose_cds,
)
from shmir_design.polya import PolyAMode, read_fasta_sequence  # noqa: E402
from shmir_design.reference import REFERENCES, load_3utr  # noqa: E402
from shmir_design.scaffold import SGEP_SCAFFOLD, load_scaffold  # noqa: E402
from shmir_design.mirna import (  # noqa: E402
    load_abundance_list,
    load_mature_fa,
)
from shmir_design.seed_load import (  # noqa: E402
    load_expression_table,
    load_utr3_set,
)
from shmir_design.seeds import BOOTSTRAP_SEEDS, parse_seed_table  # noqa: E402
from shmir_design.selection import SelectionConfig, select_from_report  # noqa: E402
from shmir_design.specificity import load_database  # noqa: E402
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


SIN_ANATOMIA = (
    "no se ha resuelto donde acaba el CDS, asi que no se sabe que tramo del "
    "transcrito es cada posicion y la anatomia queda SIN RESOLVER. Tilar de todos "
    "modos trataria el 5'UTR y el CDS como si fueran 3'UTR: los tercios saldrian "
    "corridos y habria candidatos del ORF presentados como candidatos del 3'UTR. "
    "Hay tres formas de resolverlo, por orden de fiabilidad:\n"
    "  1. --genbank FICHERO.gb  — el CDS anotado del RefSeq (lo mas fiable)\n"
    "  2. --cds INICIO FIN      — las coordenadas a mano\n"
    "  3. --region 3utr         — declarar que la secuencia YA es el 3'UTR\n"
    "Si no sabes cuales son, --proponer-cds calcula el marco mas largo y te enseña "
    "el comando; la propuesta no decide por ti."
)


REGIONES_CLI = {"5utr": Region.UTR5, "cds": Region.CDS, "3utr": Region.UTR3}


def parse_cuota_region(texto: str) -> tuple[tuple[Region, int], ...]:
    """`3utr=7,cds=3` -> ((Region.UTR3, 7), (Region.CDS, 3))."""
    cuota: list[tuple[Region, int]] = []
    for trozo in texto.split(","):
        if "=" not in trozo:
            raise ValueError(
                f"--cuota-region: {trozo!r} no tiene la forma REGION=NUMERO. Ejemplo: "
                f"--cuota-region 3utr=7,cds=3"
            )
        nombre, _, numero = trozo.partition("=")
        clave = nombre.strip().lower()
        if clave not in REGIONES_CLI:
            raise ValueError(
                f"--cuota-region: region {nombre.strip()!r} desconocida; las que hay "
                f"son {', '.join(sorted(REGIONES_CLI))}."
            )
        try:
            cuantos = int(numero)
        except ValueError as exc:
            raise ValueError(
                f"--cuota-region: {numero!r} no es un numero entero ({exc})."
            ) from exc
        cuota.append((REGIONES_CLI[clave], cuantos))
    return tuple(cuota)


def resolver_anatomia(
    *,
    nombre: str,
    secuencia: str,
    coords,
    genbank,
    genbank_md5,
    region: str,
    desde_fixture: bool,
) -> Anatomy:
    """Fija la anatomia por una de las tres vias, o aborta. Nunca adivina.

    Antes habia aqui un `else: whole_is_utr3(...)` que convertia el "no se" en un
    "todo es 3'UTR" silencioso. Ese camino ya no existe.
    """
    if desde_fixture:
        # Los fixtures de REFERENCES ya son 3'UTR extraidos y comprobados por md5.
        return Anatomy.whole_is_utr3(
            len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
        )
    if genbank is not None:
        anotacion = load_genbank_cds(genbank, expected_md5=genbank_md5)
        anotacion.check_against_sequence_length(len(secuencia))
        return Anatomy.from_cds(
            cds=anotacion.cds,
            length=len(secuencia),
            source=RegionSource.ANOTACION_GENBANK,
        )
    if coords:
        return Anatomy.from_cds(
            cds=(coords[0], coords[1]),
            length=len(secuencia),
            source=RegionSource.CDS_DECLARADA,
        )
    if region == "3utr":
        return Anatomy.whole_is_utr3(
            len(secuencia), source=RegionSource.TODO_3UTR_DECLARADO
        )
    raise ShmirDesignError(f"{nombre}: {SIN_ANATOMIA}")


def comprobar_fronteras(
    secuencia: str, anatomia: Anatomy, *, permitir_sin_parada: bool
) -> tuple[str, ...]:
    """Comprueba el CDS declarado contra las bases. El codon de parada es aviso duro."""
    if anatomia.cds is None:
        return tuple(anatomia.warnings)
    avisos = tuple(anatomia.warnings) + check_cds_boundaries(secuencia, anatomia)
    if cds_stop_codon_ok(secuencia, anatomia) is False and not permitir_sin_parada:
        detalle = next((a for a in avisos if "codon de parada" in a), "")
        raise ShmirDesignError(
            f"{detalle} Se aborta el diseño: un CDS corrido corre tambien el 3'UTR, y "
            f"con el todas las posiciones y los tercios. Comprueba las coordenadas, o "
            f"pasa --genbank, o repite con --permitir-cds-sin-codon-parada si sabes "
            f"que este CDS es asi a proposito."
        )
    return avisos


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
    parser.add_argument(
        "--rmsk", type=Path,
        help="Salida de RepeatMasker (.out) o tabla rmsk de UCSC, en coordenadas de la "
             "secuencia consultada. En raton el riesgo son los SINE B1/B2.",
    )
    parser.add_argument("--rmsk-version", help="Version del rmsk; obligatoria")
    parser.add_argument("--rmsk-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument("--min-block", type=int, default=MIN_BLOCK_LENGTH)
    parser.add_argument("--refseq", type=Path, help="FASTA local de RefSeq RNA")
    parser.add_argument("--refseq-name", default="RefSeq RNA")
    parser.add_argument("--refseq-version", help="Version o fecha de descarga")
    parser.add_argument("--refseq-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--target", help="Accession del gen diana, para no contarlo como off-target"
    )
    parser.add_argument(
        "--mirbase", type=Path,
        help="mature.fa de miRBase. Con el corre `seed_colision` en sus dos niveles y "
             "se retira el filtro `seed` de la lista de arranque.",
    )
    parser.add_argument("--mirbase-version", help="Version de miRBase; obligatoria")
    parser.add_argument("--mirbase-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--mirbase-especies", default="mmu-,hsa-",
        help="Prefijos de especie que se leen de mature.fa (por defecto mmu-,hsa-).",
    )
    parser.add_argument(
        "--abundancia", type=Path,
        help="Lista curada de miARN abundantes en el tejido (MirGeneDB). Es la UNICA "
             "fuente del nivel FAIL; sin ella ese nivel queda en NOT_RUN.",
    )
    parser.add_argument("--abundancia-version", help="Version de la lista; obligatoria")
    parser.add_argument("--abundancia-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--transcriptoma-3utr", type=Path,
        help="FASTA de los 3'UTR del transcriptoma, para contar la carga de "
             "off-targets por seed. Es un numero comparativo, no un filtro.",
    )
    parser.add_argument("--transcriptoma-version", help="Version; obligatoria")
    parser.add_argument("--transcriptoma-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--expresion", type=Path,
        help="Tabla `transcrito<TAB>valor` para ponderar la carga de seed.",
    )
    parser.add_argument(
        "--apa-medido", type=Path,
        help="Tabla `posicion<TAB>fraccion<TAB>nombre` de sitios de poliadenilacion "
             "MEDIDOS (PolyA_DB, PolyASite). Con ella, el dato sustituye a la "
             "prediccion de riesgo_APA y se puede dar el techo de knockdown.",
    )
    parser.add_argument("--apa-version", help="Version de la tabla; obligatoria")
    parser.add_argument("--apa-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--apa-coords", choices=("3utr", "transcrito"), default="3utr",
        help="En que coordenadas estan las posiciones de --apa-medido.",
    )
    parser.add_argument(
        "--accesibilidad", action="store_true",
        help="Calcula la accesibilidad de cada diana con ViennaRNA (ventanas de "
             "contexto ±80 y ±150 nt). Es un criterio de DESEMPATE, nunca un filtro, y "
             "es lento: por eso va aparte.",
    )
    parser.add_argument(
        "--transgen", type=Path,
        help="FASTA del casete AAV completo (ITR a ITR). Los candidatos que lo tocan "
             "apagarian la propia construccion terapeutica.",
    )
    parser.add_argument("--transgen-name", default="casete del transgen")
    parser.add_argument("--transgen-version", help="Version del vector; obligatoria")
    parser.add_argument("--transgen-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--cds", nargs=2, type=int, metavar=("INICIO", "FIN"),
        help="Coordenadas 1-based del CDS en la secuencia de --fasta. Con esto se "
             "etiqueta cada ventana (5'UTR/CDS/3'UTR) y los tercios se calculan sobre "
             "el 3'UTR.",
    )
    parser.add_argument(
        "--cds-b", nargs=2, type=int, metavar=("INICIO", "FIN"),
        help="Lo mismo para --fasta-b.",
    )
    parser.add_argument(
        "--genbank", type=Path,
        help="Fichero GenBank del transcrito de --fasta: de ahi sale el CDS anotado, "
             "que es mas fiable que declararlo a mano.",
    )
    parser.add_argument("--genbank-b", type=Path, help="Lo mismo para --fasta-b.")
    parser.add_argument(
        "--genbank-md5", help="md5 esperado del --genbank; si no cuadra, PARA."
    )
    parser.add_argument("--genbank-b-md5", help="md5 esperado del --genbank-b.")
    parser.add_argument(
        "--proponer-cds", action="store_true",
        help="Calcula el marco de lectura mas largo de --fasta, lo enseña con el "
             "comando --cds para pegar, y NO diseña nada. La propuesta no fija la "
             "anatomia: eso lo decide una persona.",
    )
    parser.add_argument(
        "--permitir-cds-sin-codon-parada", action="store_true",
        help="Sigue adelante aunque el CDS declarado no termine en codon de parada. "
             "Por defecto eso aborta, porque casi siempre es un desplazamiento de "
             "coordenadas que corre todo el 3'UTR sin avisar.",
    )
    parser.add_argument(
        "--polyA-modo", choices=[m.value for m in PolyAMode],
        default=PolyAMode.ESCALONADO.value,
        help="Criterio de poliadenilacion: 'estricto' tumba toda ventana que solape "
             "cualquier hexamero; 'escalonado' solo las señales fuertes; 'permisivo' "
             "solo las que quedan por detras del sitio de corte de la señal terminal. "
             "El informe saca el top-N bajo los tres, siempre.",
    )
    parser.add_argument(
        "--cuota-region", metavar="REGION=N[,REGION=N]",
        help="Reparto de los candidatos por region, p.ej. '3utr=7,cds=3'. Sin esto "
             "solo entran candidatos del 3'UTR: una ventana del ORF puede ser diana "
             "valida, pero eso se pide, no se cuela. La suma tiene que ser igual a "
             "--candidates.",
    )
    parser.add_argument(
        "--tile-desde", type=int, metavar="POS",
        help="Primera posicion a tilar. Por defecto, el principio de la secuencia.",
    )
    parser.add_argument(
        "--tile-hasta", type=int, metavar="POS",
        help="Ultima posicion a tilar. Por defecto, el final de la secuencia.",
    )
    parser.add_argument(
        "--tile-coords", choices=("transcrito", "3utr"), default="transcrito",
        help="En que coordenadas van --tile-desde/--tile-hasta. '3utr' permite pedir "
             "p.ej. la cobertura proximal 1-400 tal y como se piensa, sin sumar a mano "
             "el desplazamiento del 3'UTR.",
    )
    parser.add_argument(
        "--region", choices=("transcrito", "3utr"), default="transcrito",
        help="'3utr' declara que la secuencia dada YA es el 3'UTR. No hay valor por "
             "defecto que resuelva la anatomia: sin --cds, sin --genbank y sin "
             "--region 3utr el diseño aborta en vez de adivinar.",
    )
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
        if args.repeats and args.rmsk:
            raise ValueError(
                "--repeats y --rmsk declaran los dos la mascara de repeticiones. Elige "
                "uno: si no coinciden, no hay forma de saber cual vale."
            )
        if args.rmsk and not args.rmsk_version:
            raise ValueError(
                "--rmsk necesita --rmsk-version: sin procedencia el enmascarado no es "
                "auditable. Se aborta."
            )
        if args.rmsk:
            mask = load_rmsk(
                args.rmsk, version=args.rmsk_version, expected_md5=args.rmsk_md5
            )
        else:
            mask = load_mask_file(args.repeats) if args.repeats else None

        maduros = None
        if args.mirbase:
            if not args.mirbase_version:
                raise ValueError(
                    "--mirbase necesita --mirbase-version: sin procedencia el veredicto "
                    "no es auditable. Se aborta."
                )
            maduros = load_mature_fa(
                args.mirbase,
                version=args.mirbase_version,
                expected_md5=args.mirbase_md5,
                prefixes=tuple(
                    p.strip() for p in args.mirbase_especies.split(",") if p.strip()
                ),
            )

        abundantes = None
        if args.abundancia:
            if not args.mirbase:
                raise ValueError(
                    "--abundancia sin --mirbase no sirve de nada: la lista de "
                    "abundantes decide cuales de las colisiones importan, y sin la "
                    "tabla de maduros no hay colisiones que clasificar."
                )
            if not args.abundancia_version:
                raise ValueError(
                    "--abundancia necesita --abundancia-version: el nivel FAIL se "
                    "apoya en esta lista y sin procedencia no es auditable."
                )
            abundantes = load_abundance_list(
                args.abundancia,
                version=args.abundancia_version,
                expected_md5=args.abundancia_md5,
            )

        transcriptoma = None
        if args.transcriptoma_3utr:
            if not args.transcriptoma_version:
                raise ValueError(
                    "--transcriptoma-3utr necesita --transcriptoma-version. Se aborta."
                )
            transcriptoma = load_utr3_set(
                args.transcriptoma_3utr,
                version=args.transcriptoma_version,
                expected_md5=args.transcriptoma_md5,
            )

        expresion = None
        if args.expresion:
            if not args.transcriptoma_3utr:
                raise ValueError(
                    "--expresion sin --transcriptoma-3utr no sirve de nada: no hay "
                    "sitios que ponderar."
                )
            expresion = load_expression_table(args.expresion)

        apa_sitios = None
        if args.apa_medido:
            if not args.apa_version:
                raise ValueError(
                    "--apa-medido necesita --apa-version: este dato SUSTITUYE a una "
                    "prediccion, asi que sin procedencia no vale. Se aborta."
                )
            apa_sitios = load_apa_sites(
                args.apa_medido,
                version=args.apa_version,
                expected_md5=args.apa_md5,
                coords=args.apa_coords,
            )

        transgen_db = None
        if args.transgen:
            if not args.transgen_version:
                raise ValueError(
                    "--transgen necesita --transgen-version: sin procedencia el "
                    "veredicto no es auditable. Se aborta."
                )
            transgen_db = load_database(
                args.transgen,
                name=args.transgen_name,
                version=args.transgen_version,
                expected_md5=args.transgen_md5,
            )

        refseq = None
        if args.refseq:
            if not args.refseq_version:
                raise ValueError(
                    "--refseq necesita --refseq-version: sin procedencia el veredicto "
                    "de especificidad no es auditable."
                )
            if not args.target:
                raise ValueError(
                    "--refseq necesita --target con el accession del gen diana: sin el, "
                    "todo sitio parece un off-target."
                )
            refseq = load_database(
                args.refseq,
                name=args.refseq_name,
                version=args.refseq_version,
                expected_md5=args.refseq_md5,
            )
        config = SelectionConfig(
            n_candidates=args.candidates,
            min_spacing=args.min_spacing,
            region_quota=(
                parse_cuota_region(args.cuota_region) if args.cuota_region else None
            ),
        )
        thresholds = Thresholds(
            gc_min=args.gc_min,
            gc_max=args.gc_max,
            max_homopolymer=args.max_homopolymer,
            min_asymmetry=args.min_asymmetry,
            polya_flank=args.polya_flank,
        )

        if args.cds and args.region == "3utr":
            raise ValueError(
                "--cds y --region 3utr son incompatibles: o la secuencia es el "
                "transcrito con su CDS, o ya es el 3'UTR."
            )
        if args.genbank and args.cds:
            raise ValueError(
                "--genbank y --cds declaran los dos la misma frontera. Elige uno: si "
                "no coinciden, no hay forma de saber cual vale."
            )
        if args.genbank and args.region == "3utr":
            raise ValueError(
                "--genbank y --region 3utr son incompatibles: un GenBank describe el "
                "transcrito completo, no un 3'UTR suelto."
            )

        if args.proponer_cds:
            if not args.fasta:
                raise ValueError(
                    "--proponer-cds necesita --fasta: la propuesta se calcula sobre la "
                    "secuencia que se da."
                )
            secuencia = read_fasta_sequence(args.fasta)
            marcos = find_orfs(secuencia)
            print(
                format_cds_suggestion(
                    propose_cds(secuencia), alternatives=max(0, len(marcos) - 1)
                )
            )
            return 0

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

        anatomias, avisos_anatomia, rangos = {}, {}, {}
        for nombre, secuencia in secuencias.items():
            es_a = nombre == args.name
            anatomias[nombre] = resolver_anatomia(
                nombre=nombre,
                secuencia=secuencia,
                coords=args.cds if es_a else args.cds_b,
                genbank=args.genbank if es_a else args.genbank_b,
                genbank_md5=args.genbank_md5 if es_a else args.genbank_b_md5,
                region=args.region,
                desde_fixture=transcripts[nombre] is not None,
            )
            rangos[nombre] = TileRange.resolve(
                anatomias[nombre],
                start=args.tile_desde,
                end=args.tile_hasta,
                coords=args.tile_coords,
            )
            avisos_anatomia[nombre] = comprobar_fronteras(
                secuencia,
                anatomias[nombre],
                permitir_sin_parada=args.permitir_cds_sin_codon_parada,
            )

        conservation = None
        if len(secuencias) == 2:
            (nombre_a, seq_a), (nombre_b, seq_b) = secuencias.items()
            # Los bloques conservados se buscan entre los 3'UTR, no entre transcritos.
            utr3_a = seq_a[anatomias[nombre_a].utr3[0] - 1 : anatomias[nombre_a].utr3[1]]
            utr3_b = seq_b[anatomias[nombre_b].utr3[0] - 1 : anatomias[nombre_b].utr3[1]]
            conservation = build_conservation_report(
                Utr3(nombre_a, utr3_a),
                Utr3(nombre_b, utr3_b),
                min_length=args.min_block,
                thresholds=thresholds,
            )

        args.out.mkdir(parents=True, exist_ok=True)
        for especie, secuencia in secuencias.items():
            tiling = tile_utr(
                secuencia,
                seeds=seeds,
                mask=mask,
                anatomy=anatomias[especie],
                tile_range=rangos[especie],
                polya_mode=PolyAMode(args.polyA_modo),
                specificity_db=refseq,
                transgene_db=transgen_db,
                mature=maduros,
                abundance=abundantes,
                utr3_set=transcriptoma,
                expression=expresion,
                accessibility=args.accesibilidad,
                apa_sites=apa_sitios,
                specificity_target=args.target,
                thresholds=thresholds,
            )
            seleccion = select_from_report(tiling, config)
            informe = text_report(
                species=especie,
                tiling=tiling,
                selection=seleccion,
                scaffold=scaffold,
                transcript=transcripts[especie],
                conservation=conservation,
                anatomy_warnings=avisos_anatomia[especie],
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
