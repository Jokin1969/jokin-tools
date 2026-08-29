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

from shmir_design import masking  # noqa: E402
from shmir_design.apa import ApaExcluded, load_apa_sites  # noqa: E402
from shmir_design.splicing import intronless_control, plan_from_records  # noqa: E402
from shmir_design.anatomy import (  # noqa: E402
    Anatomy,
    Region,
    TileRange,
    RegionSource,
    check_cds_boundaries,
    cds_stop_codon_ok,
)
from shmir_design.resolve import (  # noqa: E402
    SIN_ANATOMIA,
    check_boundaries,
    resolve_anatomy,
)
from shmir_design.conservation import (  # noqa: E402
    MIN_BLOCK_LENGTH,
    Utr3,
    build_conservation_report,
)
from shmir_design.blocks import (  # noqa: E402
    blocks_fasta,
    blocks_tsv,
    build_block,
    order_sheet,
)
from shmir_design.comparative import comparative_tsv  # noqa: E402
from shmir_design.cost import estimate_cost  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.manifest import (  # noqa: E402
    MANIFEST_NAME,
    check_directory,
    load_manifest,
    roles_available,
)
from shmir_design.hard_filters import DEFAULT_THRESHOLDS, Thresholds  # noqa: E402
from shmir_design.masking import load_rmsk  # noqa: E402
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
from shmir_design.reference import (  # noqa: E402
    REFERENCES,
    fixture_filename,
    load_3utr,
)
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
from shmir_design.selection import (  # noqa: E402
    SelectionConfig,
    default_config,
    select_from_report,
)
from shmir_design.specificity import load_database  # noqa: E402
from shmir_design.tiling import RESOLVER_MEDIDA, tile_utr  # noqa: E402

DEFAULT_PAIR = {"raton": "NM_011170.3", "humano": "NM_000311.5"}

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "reference"


def estado_de_los_datos(directorio: Path, *, permitir_sin_manifiesto: bool):
    """Comprueba el directorio de referencias ANTES de correr nada y lo imprime.

    Sin esto, una corrida de hace tres meses no es reproducible: no queda registro de
    con que version de cada base se saco el veredicto.
    """
    try:
        estado = check_directory(directorio)
    except ShmirDesignError as exc:
        if permitir_sin_manifiesto:
            print(
                f"  ⚠  Sin manifiesto en {directorio} ({exc}). Se sigue por "
                f"--sin-manifiesto, pero esta corrida NO es reproducible.\n"
            )
            return None, None
        raise ShmirDesignError(
            f"{exc} Si de verdad quieres correr sin registro de procedencia, repite con "
            f"--sin-manifiesto; la corrida no será reproducible."
        ) from exc

    print(estado.format_text())
    print()
    if estado.mismatched:
        nombres = ", ".join(r.entry.name for r in estado.mismatched)
        raise ShmirDesignError(
            f"Hay ficheros de referencia que NO son los que dicen ser ({nombres}); se "
            f"aborta antes de usarlos para ningún veredicto."
        )
    return estado, load_manifest(directorio / MANIFEST_NAME)

PISTA_CLI = (
    "\nEn este CLI: --genbank FICHERO.gb, --cds INICIO FIN, o --region 3utr.\n"
    "Si no sabes cuales son, --proponer-cds calcula el marco más largo y te enseña "
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
                f"--cuota-region: región {nombre.strip()!r} desconocida; las que hay "
                f"son {', '.join(sorted(REGIONES_CLI))}."
            )
        try:
            cuantos = int(numero)
        except ValueError as exc:
            raise ValueError(
                f"--cuota-region: {numero!r} no es un número entero ({exc})."
            ) from exc
        cuota.append((REGIONES_CLI[clave], cuantos))
    return tuple(cuota)


#: Que argumento del CLI recibe la ruta, la version y el md5 de cada rol. Solo estos
#: tres: lo demas (el gen diana, el sistema de coordenadas) no es un fichero y el
#: manifiesto no lo sabe.
DESTINOS = {
    "refseq": ("refseq", "refseq_version", "refseq_md5"),
    "mirbase": ("mirbase", "mirbase_version", "mirbase_md5"),
    "abundancia": ("abundancia", "abundancia_version", "abundancia_md5"),
    "transcriptoma": (
        "transcriptoma_3utr", "transcriptoma_version", "transcriptoma_md5",
    ),
    "expresion": ("expresion", None, None),
    "rmsk": ("rmsk", "rmsk_version", "rmsk_md5"),
    "transgen": ("transgen", "transgen_version", "transgen_md5"),
    "apa": ("apa_medido", "apa_version", "apa_md5"),
    # `polyadb` NO SE CONECTA POR AQUI, y `None` lo dice: la tabla de PolyA_DB la
    # resuelve `tile_utr` por su cuenta del directorio de referencia (`find_polyadb`),
    # asi que no hay bandera que rellenar. Antes ni siquiera estaba, y `--usar-manifiesto`
    # —«la forma normal de correr»— reventaba con un `KeyError: 'polyadb'` contra el
    # manifiesto de verdad. Ningun test lo veia porque todos montan un manifiesto
    # PARCIAL en un temporal, sin ese rol.
    #
    # `None` es una DECISION declarada, no un hueco: un rol que faltara del diccionario
    # vuelve a ser el KeyError, y `tests/test_roles_del_manifiesto.py` cruza las dos
    # listas en las dos direcciones para que no pueda volver a pasar.
    "polyadb": None,
}


def conectar_desde_manifiesto(args, estado) -> None:
    """Rellena los argumentos de fichero a partir del manifiesto.

    Una flag explicita MANDA sobre el manifiesto —hace falta para poder probar un
    fichero suelto sin registrarlo— pero se dice en la consola: sobrescribir en silencio
    lo que dice el registro de procedencia es justo lo que este atajo viene a evitar.
    """
    disponibles = roles_available(estado)
    if not disponibles:
        print(
            "  --usar-manifiesto: ningún fichero de referencia está en OK, así que no "
            "hay nada que conectar. Los filtros que dependen de uno quedaran en "
            "NOT_RUN.\n"
        )
        return

    print("  --usar-manifiesto conecta:")
    for rol in disponibles:
        conexion = DESTINOS[rol.role]
        if conexion is None:
            continue  # lo resuelve el nucleo, no hay bandera que rellenar
        destino, version, md5 = conexion
        entrada = estado.result_of(rol.filename).entry
        if getattr(args, destino) is not None:
            print(
                f"    {rol.filename:<24} NO se conecta: --{destino.replace('_', '-')} "
                f"explicito manda sobre el manifiesto."
            )
            continue
        setattr(args, destino, args.datos / rol.filename)
        if version is not None:
            setattr(args, version, entrada.date or entrada.md5)
        if md5 is not None:
            setattr(args, md5, entrada.md5)
        if rol.role == "rmsk":
            # Ni la especie ni el resumen se teclean: la primera sale del organismo de
            # la referencia que el manifiesto declara en `accession`, el segundo del
            # `.tbl` hermano. Si falta cualquiera de los dos, la carga aborta despues —
            # aqui no se rellena con nada por defecto.
            from shmir_design.reference import REFERENCES

            referencia = REFERENCES.get(entrada.accession)
            if referencia is not None and not args.rmsk_especie:
                args.rmsk_especie = referencia.organism.lower()
            if not args.rmsk_biblioteca:
                args.rmsk_biblioteca = entrada.library or None
            resumen = (args.datos / rol.filename).with_suffix(".tbl")
            if args.rmsk_resumen is None and resumen.is_file():
                args.rmsk_resumen = resumen
        print(
            f"    {rol.filename:<24} → {rol.what}  ({entrada.date or 'sin fecha'}, "
            f"md5 {entrada.md5[:8]}…)"
        )
    print()


def _conservacion_polya(especie: str, secuencias: dict, anatomias: dict):
    """¿Esta la señal canonica en el 3'UTR de la OTRA especie de esta corrida?

    Solo se puede contestar si hay dos especies (--fasta-b). Con una sola devuelve None
    y el informe lo dice como NOT_RUN, no como «no esta conservada»: no haber comparado
    y haber comparado sin encontrarla son cosas distintas.
    """
    from shmir_design.polya import CANONICAL_SIGNAL, signal_conservation

    otras = [n for n in secuencias if n != especie]
    if len(otras) != 1:
        return None
    otra = otras[0]
    anatomia = anatomias[otra]
    if not anatomia.utr3:
        return None
    utr3 = secuencias[otra][anatomia.utr3[0] - 1 : anatomia.utr3[1]]
    return signal_conservation(CANONICAL_SIGNAL, utr3, other_name=otra)


def _barrido_orf(especie: str, secuencias: dict, anatomias: dict):
    """Identidad exacta >= 22 nt entre los DOS ORF, con la cascada aplicada.

    Solo si hay dos especies y las dos traen CDS. Con una sola no hay nada que comparar
    y se devuelve None: el informe no imprime el bloque en vez de imprimir un cero.
    """
    from shmir_design.orf_sweep import orf_sweep

    otras = [n for n in secuencias if n != especie]
    if len(otras) != 1:
        return None
    otra = otras[0]
    if anatomias[especie].cds is None or anatomias[otra].cds is None:
        return None
    def orf(nombre: str) -> str:
        inicio, fin = anatomias[nombre].cds
        return secuencias[nombre][inicio - 1 : fin]
    return orf_sweep(
        orf(especie), orf(otra),
        species=(especie, otra),
        cds_start=(anatomias[especie].cds[0], anatomias[otra].cds[0]),
    )


def _convergencia(ruta: Path, *, tiling, seleccion):
    """Cruza el export externo con NUESTROS sitios elegibles, por secuencia.

    La referencia es el conjunto COMPLETO de sitios elegibles, no los elegidos: contra
    un subconjunto casi todo parece nuevo. Va escrita en la salida.
    """
    from shmir_design.coords import Frame, frame_of
    from shmir_design.mirarchitect import parse_export
    from shmir_design.selection import is_eligible
    from shmir_design.spacing import ReferenceSet, compare_sites, convergence

    export = parse_export(ruta.read_text(encoding="utf-8"), source=str(ruta))
    # El cruce va por SECUENCIA, nunca por la coordenada que declara el fichero: las
    # ventanas tiladas ya traen su diana, asi que la diana externa se busca entre ellas.
    por_diana: dict[str, int] = {}
    for ventana in tiling.windows:
        por_diana.setdefault(ventana.evaluation.sequence, ventana.window.start)
    tabla = str.maketrans("ACGT", "TGCA")
    externos: dict[int, str] = {}
    sin_mapear = 0
    for fila in export.rows:
        diana = fila.guide.translate(tabla)[::-1]
        inicio = por_diana.get(diana)
        if inicio is None:
            sin_mapear += 1
            continue
        externos[inicio] = fila.guide
    if not externos:
        raise ShmirDesignError(
            f"Ninguna de las {len(export.rows)} guías de {ruta} mapea sobre la "
            f"secuencia analizada; se aborta el bloque de convergencia en vez de "
            f"declarar «cero sitios exclusivos» sobre un cruce vacío."
        )
    sitios = {
        sitio.best.start: seleccion.windows[sitio.best.label].evaluation.guide
        for sitio in seleccion.selection.sites
    }
    marco = frame_of(tiling.anatomy) if tiling.anatomy is not None else Frame.UTR3
    comparacion = compare_sites(
        candidates=externos,
        reference=ReferenceSet(
            label=f"los {len(sitios)} sitios elegibles (la tabla COMPLETA)",
            starts=sitios,
            frame=marco,
        ),
    )
    return convergence(
        comparacion,
        eligible={w.window.start for w in tiling.windows if is_eligible(w)},
        method_a="nuestra cascada de filtros duros",
        method_b=(
            f"fuente externa ({ruta.name}, {len(export.rows)} filas, "
            f"{sin_mapear} sin mapear)"
        ),
    )


def config_de_seleccion(args) -> SelectionConfig:
    """La configuracion de seleccion del CLI. Sale de `default_config()`, como la pagina.

    ANTES ERA UN `SelectionConfig(...)` PELADO, y ahi vivia la SEXTA divergencia entre
    los dos frontales: `--inmunes` valia **0** por defecto y la decision del proyecto es
    **4** (`DEFAULT_IMMUNE_QUOTA`). Como nadie pasa nunca esa bandera, el CLI corria
    SIEMPRE con la cuota apagada y daba otro panel:

        pagina  →  3utr: 10, 60, 143, **200**, 449, 553, 652, 735, 819, 1018
        CLI     →  3utr: 10, 60, 143, **359**, 449, 553, 652, 735, 819, 1018

    `3utr:359` (+4,82) desplaza a `3utr:200` (+3,80) por asimetria, asi que el panel del
    CLI se quedaba con TRES inmunes en vez de cuatro — y no lo decia nadie, porque los
    dos son del tercio proximal y la cuota de tercios se cumple igual. Es literalmente el
    fallo que `default_config()` existe para cerrar, arreglado en la pagina y no aqui.

    Y la frontera de la inmunidad NO se recibe: `select_from_report` la DERIVA del
    informe. Un corte tecleado no se entera de que un sitio medido lo adelante — paso de
    `3utr:303` a `3utr:251` y la cifra escrita a mano siguio ahi sin dar ningun error.
    """
    return default_config(
        n_candidates=args.candidates,
        min_spacing=args.min_spacing,
        region_quota=(
            parse_cuota_region(args.cuota_region) if args.cuota_region else None
        ),
        spread_coverage=args.reparto_rango,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, help="Directorio de salida (obligatorio)")
    parser.add_argument(
        "--datos", type=Path, default=DEFAULT_DATA_DIR,
        help="Directorio de ficheros de referencia con su manifest.tsv. Se comprueba "
             "ANTES de correr nada y su estado se imprime.",
    )
    parser.add_argument(
        "--usar-manifiesto", action="store_true",
        help="Conecta solo cada fichero de --datos que este en OK con el filtro que le "
             "toca, con la versión y el md5 del propio manifiesto. Sustituye a las 31 "
             "flags de fontaneria; una flag explicita sigue mandando sobre esto.",
    )
    parser.add_argument(
        "--sin-manifiesto", action="store_true",
        help="Sigue adelante aunque no haya manifiesto. La corrida no será "
             "reproducible y el informe lo dira.",
    )
    parser.add_argument("--fasta", type=Path, help="3'UTR suelto en FASTA")
    parser.add_argument("--name", default="3utr", help="Nombre de especie para --fasta")
    parser.add_argument(
        "--fasta-b", type=Path, help="Segundo 3'UTR: compara las dos especies"
    )
    parser.add_argument("--name-b", default="especie_b", help="Nombre para --fasta-b")
    parser.add_argument("--candidates", type=int, default=SelectionConfig().n_candidates)
    parser.add_argument(
        "--convergencia", type=Path, default=None,
        help=(
            "Export de la fuente externa (CSV de miRarchitect) para declarar en el "
            "informe la convergencia con nuestra cascada. Se cruza por SECUENCIA, y "
            "SOLO contra la especie de --name: un export de raton no mapea sobre el "
            "3'UTR humano, y cruzarlo daria un «cero sitios exclusivos» sobre un cruce "
            "vacío. Para la segunda especie hace falta su propio export."
        ),
    )
    parser.add_argument("--min-spacing", type=int, default=SelectionConfig().min_spacing)
    parser.add_argument("--scaffold", type=Path, help="Andamio en TOML")
    parser.add_argument("--bootstrap-seeds", action="store_true")
    parser.add_argument(
        "--rmsk", type=Path,
        help="Salida de RepeatMasker (.out) o tabla rmsk de UCSC, en coordenadas de la "
             "secuencia consultada. En raton el riesgo son los SINE B1/B2.",
    )
    parser.add_argument("--rmsk-version", help="Versión del rmsk; obligatoria")
    parser.add_argument("--rmsk-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--rmsk-especie",
        help=(
            "Especie de la BIBLIOTECA que se esperaba (p. ej. «mus musculus»). "
            "Obligatoria con un .out: es lo único que distingue una corrida buena de "
            "una contra otra especie, que sale con formato correcto y cifras plausibles."
        ),
    )
    parser.add_argument(
        "--rmsk-resumen", type=Path,
        help=(
            "El .tbl de la corrida. Obligatorio con un .out: la línea de la especie "
            "vive ahi y no en el .out, y sin los ceros por familia un fichero sin filas "
            "no distingue «no habia repetitivos» de «la corrida no llego a correr»."
        ),
    )
    parser.add_argument("--rmsk-biblioteca", help="Biblioteca usada (p. ej. Dfam_3.0)")
    parser.add_argument("--min-block", type=int, default=MIN_BLOCK_LENGTH)
    parser.add_argument("--refseq", type=Path, help="FASTA local de RefSeq RNA")
    parser.add_argument("--refseq-name", default="RefSeq RNA")
    parser.add_argument("--refseq-version", help="Versión o fecha de descarga")
    parser.add_argument("--refseq-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--target", help="Accession del gen diana, para no contarlo como off-target"
    )
    parser.add_argument(
        "--mirbase", type=Path,
        help="mature.fa de miRBase. Con el corre `seed_colision` en sus dos niveles y "
             "se retira el filtro `seed` de la lista de arranque.",
    )
    parser.add_argument("--mirbase-version", help="Versión de miRBase; obligatoria")
    parser.add_argument("--mirbase-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--abundancia", type=Path,
        help="Lista curada de miARN abundantes en el tejido (MirGeneDB). Es la ÚNICA "
             "fuente del nivel FAIL; sin ella ese nivel queda en NOT_RUN.",
    )
    parser.add_argument("--abundancia-version", help="Versión de la lista; obligatoria")
    parser.add_argument("--abundancia-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--transcriptoma-3utr", type=Path,
        help="FASTA de los 3'UTR del transcriptoma, para contar la carga de "
             "off-targets por seed. Es un número comparativo, no un filtro.",
    )
    parser.add_argument("--transcriptoma-version", help="Versión; obligatoria")
    parser.add_argument("--transcriptoma-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--expresion", type=Path,
        help="Tabla `transcrito<TAB>valor` para ponderar la carga de seed.",
    )
    parser.add_argument(
        "--apa-medido", type=Path,
        help="Tabla `posicion<TAB>fraccion<TAB>nombre` de sitios de poliadenilación "
             "MEDIDOS (PolyA_DB, PolyASite) ADICIONAL. NO es un interruptor: la tabla "
             "de PolyA_DB que el proyecto ya tiene se aplica SIEMPRE que hable de la "
             "secuencia analizada, sin pedirla. Esto añade otra.",
    )
    parser.add_argument(
        "--ignorar-apa-medido", metavar="MOTIVO",
        help="Excluir A PROPÓSITO la tabla de APA medido, con el motivo escrito. Es la "
             "única forma de que no entre: sin ella una señal con uso medido se trata "
             "como no funcional, que es la hipotesis MENOS conservadora. El motivo viaja "
             "al veredicto — sin el, «se decidio no usarla» y «nadie se acordo» son el "
             "mismo resultado mudo. Mismo criterio que ignorar un fichero del deposito.",
    )
    parser.add_argument("--apa-version", help="Versión de la tabla; obligatoria")
    parser.add_argument("--apa-md5", help="md5 esperado; si no cuadra, PARA")
    parser.add_argument(
        "--apa-coords", choices=("3utr", "transcrito"), default="3utr",
        help="En que coordenadas están las posiciones de --apa-medido.",
    )
    parser.add_argument(
        "--estimar", action="store_true",
        help="No diseña nada: tila, cuenta cuántas ventanas pasarian por cada filtro "
             "caro, mide UNA invocación real de cada uno y dice cuanto va a tardar. "
             "Para saber en unos segundos si merece la pena lanzarlo.",
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
             "apagarian la propia construcción terapeutica.",
    )
    parser.add_argument("--transgen-name", default="casete del transgén")
    parser.add_argument("--transgen-version", help="Versión del vector; obligatoria")
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
             "que es más fiable que declararlo a mano.",
    )
    parser.add_argument("--genbank-b", type=Path, help="Lo mismo para --fasta-b.")
    parser.add_argument(
        "--genbank-md5", help="md5 esperado del --genbank; si no cuadra, PARA."
    )
    parser.add_argument("--genbank-b-md5", help="md5 esperado del --genbank-b.")
    parser.add_argument(
        "--proponer-cds", action="store_true",
        help="Calcula el marco de lectura más largo de --fasta, lo enseña con el "
             "comando --cds para pegar, y NO diseña nada. La propuesta no fija la "
             "anatomía: eso lo decide una persona.",
    )
    parser.add_argument(
        "--nota", type=Path, action="append", default=[],
        help="Fichero de texto que se copia TAL CUAL dentro del informe. Para que un "
             "resultado que se calculo aparte —una comparación de dos corridas, por "
             "ejemplo— viaje en el documento y no solo en el log. Se puede repetir.",
    )
    parser.add_argument(
        "--permitir-cds-sin-codon-parada", action="store_true",
        help="Sigue adelante aunque el CDS declarado no termine en codón de parada. "
             "Por defecto eso aborta, porque casi siempre es un desplazamiento de "
             "coordenadas que corre todo el 3'UTR sin avisar.",
    )
    parser.add_argument(
        "--bloques", action="store_true",
        help="Emite además los bloques listos para pedir de los candidatos elegidos: "
             "módulo NheI-SacI de 149 nt, cassette MluI-AgeI de 318 pb, versiones con "
             "brazos de Gibson y hoja de pedido.",
    )
    parser.add_argument(
        "--reoptimizar-espaciadores", action="store_true",
        help="Con --bloques: genera espaciadores de novo para las guías cuyo 97-mero "
             "no sobreviva dentro del intrón estándar. Genera secuencia, va apagado "
             "por defecto y lo que produce se marca en toda la salida.",
    )
    parser.add_argument(
        "--reparto-rango", action="store_true",
        help="Reparte los candidatos por los extremos de los parámetros dudosos (GC "
             "alto y bajo, accesibilidad alta y baja, delante y detrás del APA, con y "
             "sin bandera de polyA) en vez de coger los mejores por asimetría. Si el "
             "objetivo es correlacionar parámetros contra el knockdown medido, los "
             "puntos tienen que estar repartidos.",
    )
    parser.add_argument(
        "--cuota-region", metavar="REGION=N[,REGION=N]",
        help="Reparto de los candidatos por región, p.ej. '3utr=7,cds=3'. Sin esto "
             "solo entran candidatos del 3'UTR: una ventana del ORF puede ser diana "
             "valida, pero eso se pide, no se cuela. La suma tiene que ser igual a "
             "--candidates.",
    )
    parser.add_argument(
        "--tile-desde", type=int, metavar="POS",
        help="Primera posición a tilar. Por defecto, el principio de la secuencia.",
    )
    parser.add_argument(
        "--tile-hasta", type=int, metavar="POS",
        help="Última posición a tilar. Por defecto, el final de la secuencia.",
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
             "defecto que resuelva la anatomía: sin --cds, sin --genbank y sin "
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

    if args.out is None and not args.estimar:
        print("design: falta --out con el directorio de salida.", file=sys.stderr)
        return 2
    if args.fasta_b and not args.fasta:
        print(
            "design: --fasta-b necesita --fasta; son las dos especies que se comparan.",
            file=sys.stderr,
        )
        return 2

    try:
        estado_datos, manifiesto = estado_de_los_datos(
            args.datos, permitir_sin_manifiesto=args.sin_manifiesto
        )
        usados: list[str] = []

        if args.usar_manifiesto:
            if estado_datos is None:
                raise ShmirDesignError(
                    f"--usar-manifiesto necesita un {MANIFEST_NAME} en {args.datos}: "
                    f"es de donde salen el fichero, la versión y el md5 de cada filtro."
                )
            conectar_desde_manifiesto(args, estado_datos)

        scaffold = load_scaffold(args.scaffold) if args.scaffold else SGEP_SCAFFOLD
        seeds = BOOTSTRAP_SEEDS if args.bootstrap_seeds else None
        if args.rmsk and not args.rmsk_version:
            raise ValueError(
                "--rmsk necesita --rmsk-version: sin procedencia el enmascarado no es "
                "auditable. Se aborta."
            )
        if args.rmsk:
            es_out = Path(args.rmsk).suffix.lower() == ".out"
            if es_out and not args.rmsk_especie:
                raise ValueError(
                    "--rmsk apunta a un .out y falta --rmsk-especie. Es lo único que "
                    "distingue una corrida contra la biblioteca correcta de una contra "
                    "otra especie: la equivocada sale con formato correcto y cifras "
                    "plausibles. Se aborta."
                )
            if es_out and not args.rmsk_resumen:
                raise ValueError(
                    "--rmsk apunta a un .out y falta --rmsk-resumen (.tbl). La línea de "
                    "la especie vive en el resumen, no en el .out —ninguno la trae— y "
                    "sin los ceros por familia un fichero sin filas no distingue «no "
                    "habia repetitivos» de «la corrida no llego a correr». Se aborta."
                )
            mask = load_rmsk(
                args.rmsk,
                version=args.rmsk_version,
                expected_md5=args.rmsk_md5,
                expected_species=args.rmsk_especie,
                library=args.rmsk_biblioteca,
                summary_path=args.rmsk_resumen,
            )
        else:
            mask = None

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
                # SIN `prefixes`: se indexa el fichero ENTERO y el filtro por especie es
                # de quien PREGUNTA, no de quien carga. Habia una bandera para teclearlo
                # y era la puerta de atras al prefijo equivocado, que da CERO colisiones
                # y parece una buena noticia. Ver `mirna.DEFAULT_PREFIXES`.
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
                    "predicción, así que sin procedencia no vale. Se aborta."
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
        config = config_de_seleccion(args)
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
            anatomias[nombre] = resolve_anatomy(
                name=nombre,
                sequence=secuencia,
                cds=args.cds if es_a else args.cds_b,
                genbank=args.genbank if es_a else args.genbank_b,
                genbank_md5=args.genbank_md5 if es_a else args.genbank_b_md5,
                whole_is_utr3=args.region == "3utr",
                from_fixture=transcripts[nombre] is not None,
                hint=PISTA_CLI,
            )
            rangos[nombre] = TileRange.resolve(
                anatomias[nombre],
                start=args.tile_desde,
                end=args.tile_hasta,
                coords=args.tile_coords,
            )
            avisos_anatomia[nombre] = check_boundaries(
                secuencia,
                anatomias[nombre],
                allow_no_stop=args.permitir_cds_sin_codon_parada,
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

        # Los ficheros que de verdad se han usado: sus lineas del manifiesto van al
        # informe. Un veredicto sin esto no es auditable dentro de un año.
        for ruta in (
            args.refseq, args.mirbase, args.abundancia, args.transcriptoma_3utr,
            args.expresion, args.transgen, args.rmsk, args.apa_medido,
            args.genbank, args.genbank_b,
        ):
            if ruta is not None:
                usados.append(Path(ruta).name)
        if not args.fasta:
            usados.extend(
                fixture_filename(REFERENCES[accession])
                for accession in DEFAULT_PAIR.values()
            )

        if args.estimar:
            for especie, secuencia in secuencias.items():
                print(f"\n═══ {especie} ═══")
                print(
                    estimate_cost(
                        sequence=secuencia,
                        anatomy=anatomias[especie],
                        tile_range=rangos[especie],
                        thresholds=thresholds,
                        specificity_db=refseq,
                        specificity_target=args.target,
                        transgene_db=transgen_db,
                        mature=maduros,
                        abundance=abundantes,
                        utr3_set=transcriptoma,
                        accessibility=args.accesibilidad,
                    ).format_text()
                )
            print()
            return 0

        notas = tuple(
            Path(ruta).read_text(encoding="utf-8").rstrip("\n") for ruta in args.nota
        )
        args.out.mkdir(parents=True, exist_ok=True)
        for especie, secuencia in secuencias.items():
            # La tabla de PolyA_DB se coloca sola sobre la secuencia que le corresponde
            # y solo sobre esa: la condicion es el md5 canonico del 3'UTR, asi que
            # sobre cualquier otra devuelve None y no se promueve ninguna señal.
            # La medida ENTRA SOLA: `tile_utr` la resuelve por su cuenta contra el
            # md5 del 3'UTR. Aqui solo se recoge la EXCLUSION deliberada, que es la
            # unica forma de que no entre y exige motivo escrito. Ver
            # `apa.WHY_MEASURE_IS_NOT_A_FLAG`: es un veredicto, no una ordenacion.
            medido = (
                ApaExcluded(reason=args.ignorar_apa_medido)
                if args.ignorar_apa_medido
                else RESOLVER_MEDIDA
            )
            tiling = tile_utr(
                secuencia,
                # La especie del diseño VIAJA: sin ella el nucleo de abundancia no puede
                # decir si la lista que usa es la de esta especie o una prestada.
                species=especie,
                measured_apa=medido,
                seeds=seeds,
                mask=mask,
                anatomy=anatomias[especie],
                tile_range=rangos[especie],
                # El criterio es ESCALONADO. DECIDIDO (2026-08-26) con la tabla delante, y
                # el informe emite el top-N bajo los TRES criterios de todos modos,
                # asi que una bandera para cambiarlo reproducia una decision que la
                # propia salida ya documenta.
                polya_mode=PolyAMode.ESCALONADO,
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
            convergencias = {}
            if args.convergencia is not None and especie == args.name:
                convergencias[especie] = _convergencia(
                    args.convergencia, tiling=tiling, seleccion=seleccion
                )
            # El detalle POR VENTANA del triple motivo necesita un informe tilado SIN
            # mascara: con ella el paso 15 retila y esas ventanas ya no estan en la
            # piscina, asi que la lista saldria vacia — que no es lo mismo que limpia.
            # Y los DOS desfases van explicitos y por nombre (masking.triple_motive_rows
            # no admite omitir ninguno): el de busqueda en la mascara y el de etiquetado.
            triple = None
            mordida = None
            if mask is not None:
                sin_mascara = tile_utr(
                    secuencia,
                    measured_apa=medido,
                    seeds=seeds,
                    anatomy=anatomias[especie],
                    tile_range=rangos[especie],
                    # El criterio es ESCALONADO. DECIDIDO (2026-08-26) con la tabla delante, y
                # el informe emite el top-N bajo los TRES criterios de todos modos,
                # asi que una bandera para cambiarlo reproducia una decision que la
                # propia salida ya documenta.
                polya_mode=PolyAMode.ESCALONADO,
                    # `umbrales` NO EXISTE en este modulo y estuvo aqui desde que se
                    # cableo el triple motivo: la variable se llama `thresholds`, tres
                    # lineas mas arriba en esta misma funcion. O sea que TODA corrida del
                    # CLI con `--rmsk` abortaba con un NameError, y el bloque que este
                    # `tile_utr` alimenta —el que se escribio justo porque «existia solo
                    # porque alguien lo corria a mano»— no habia corrido NUNCA.
                    #
                    # Ningun test lo cazo porque ninguno corria el CLI CON mascara: los
                    # del triple motivo llaman a `triple_motive_rows` ellos mismos, que
                    # es exactamente la ceguera que describe la alcanzabilidad — el
                    # llamador de verdad no lo ejecutaba nadie. Lo cazo escribir un test
                    # que corre `main()` con `--rmsk`, y ese test se queda.
                    thresholds=thresholds,
                )
                inicio_utr3 = anatomias[especie].utr3[0]
                triple = masking.triple_motive_rows(
                    sin_mascara,
                    mask,
                    # El informe tila el MISMO transcrito sobre el que se corrio
                    # RepeatMasker, asi que para BUSCAR en la mascara no hay desfase...
                    mask_offset=0,
                    # ...y para ETIQUETAR hay que pasar de transcrito a 3'UTR, que es
                    # RESTAR el inicio del 3'UTR menos uno. El signo importa y no es
                    # cosmetico: con el contrario salio `3utr:2613` sobre un transcrito
                    # de 2435 nt, y lo cazo el invariante de rango en el acto.
                    label_offset=inicio_utr3 - 1,
                )
                # Del MISMO informe sin mascara y con los MISMOS dos desfases: si se
                # calculara del tilado con mascara, el paso 15 ya habria retilado y
                # saldria cero — el numero que esto existe para poder leer.
                mordida = masking.mask_bite(
                    sin_mascara, mask, mask_offset=0, label_offset=inicio_utr3 - 1
                )
            informe = text_report(
                species=especie,
                tiling=tiling,
                selection=seleccion,
                scaffold=scaffold,
                triple_motive=triple,
                mask_bite=mordida,
                convergence=convergencias.get(especie),
                polya_conservation=_conservacion_polya(
                    especie, secuencias, anatomias
                ),
                orf_sweep=_barrido_orf(especie, secuencias, anatomias),
                transcript=transcripts[especie],
                conservation=conservation,
                anatomy_warnings=avisos_anatomia[especie],
                notes=notas,
                provenance=(
                    manifiesto.provenance_lines(usados)
                    if manifiesto is not None
                    else (
                        "Sin manifiesto: no hay registro de procedencia y esta corrida "
                        "NO es reproducible.",
                    )
                ),
            )
            salidas = {
                f"{especie}_ventanas.tsv": tsv_all_windows(tiling),
                f"{especie}_seleccionados.tsv": tsv_selected(seleccion, species=especie),
                f"{especie}_guias.fasta": fasta_guides(seleccion, species=especie),
                f"{especie}_oligos.tsv": tsv_oligos(
                    seleccion, scaffold, species=especie
                ),
                f"{especie}_comparativa.tsv": comparative_tsv(
                    seleccion, scaffold, with_header=True,
                    anatomy=anatomias[especie],
                ),
                f"{especie}_informe.txt": informe,
            }
            if args.bloques:
                bloques = [
                    build_block(
                        seleccion.window_of(c).evaluation.guide.replace("U", "T"),
                        scaffold=scaffold,
                        transgene=seleccion.window_of(c).transgen_detalle,
                        reoptimize_spacers=args.reoptimizar_espaciadores,
                    )
                    for c in seleccion.selection.chosen
                ]
                salidas[f"{especie}_bloques.fasta"] = blocks_fasta(
                    bloques, species=especie
                )
                salidas[f"{especie}_bloques.tsv"] = blocks_tsv(
                    bloques, species=especie
                )
                # El control sin intron y las ventanas de cebador salen del CASETE, que
                # ya viaja en la base del transgen: no hace falta pasarlos aparte.
                plan_empalme, _ = plan_from_records(
                    transgen_db.records if transgen_db is not None else None
                )
                control = None
                if plan_empalme is not None and plan_empalme.location.empty:
                    control = intronless_control(
                        transgen_db.records[plan_empalme.location.plasmid_name],
                        name=plan_empalme.location.plasmid_name,
                    )
                salidas[f"{especie}_hoja_de_pedido.txt"] = order_sheet(
                    bloques, species=especie,
                    intronless=control, rtpcr=plan_empalme,
                )
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
