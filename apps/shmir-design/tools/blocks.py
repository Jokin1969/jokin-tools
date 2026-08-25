"""Generador de bloques listos para pedir, sobre candidatos ya calculados.

    # sobre la tabla comparativa que produjo design.py
    python3 apps/shmir-design/tools/blocks.py \
        --tabla salida/raton_comparativa.tsv --elegir 1,3,5 --out bloques/

    # o directamente sobre guias sueltas
    python3 apps/shmir-design/tools/blocks.py --guia TTTAGTACTGGATGGAACGGCC --out bloques/

Escribe tres ficheros: `bloques.fasta` (los dos niveles de cada candidato, con y sin
brazos de homologia), `bloques.tsv` (una fila por candidato con el resultado de cada
comprobacion) y `hoja_de_pedido.txt` (secuencias en bloques de 60 y que enzimas usar).

Codigo de salida: 0 si todo pasa, 1 si alguna comprobacion sale FAIL —las salidas se
escriben igual, para poder mirarlas—, 2 si no se pudo ni construir.

Python 3.11+ (regla 6).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.blocks import (  # noqa: E402
    blocks_fasta,
    blocks_tsv,
    build_block,
    order_sheet,
)
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.filters import FilterState  # noqa: E402
from shmir_design.polya import read_fasta_sequence  # noqa: E402


def leer_tabla(path: Path) -> list[tuple[str, str]]:
    """Devuelve (etiqueta, guia) de cada fila. `#` al principio es comentario."""
    try:
        texto = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ShmirDesignError(
            f"No se pudo leer la tabla de candidatos {path} ({exc}); se aborta."
        ) from exc

    filas = [l for l in texto.splitlines() if l.strip() and not l.startswith("#")]
    if not filas:
        raise ShmirDesignError(
            f"{path}: la tabla no tiene ninguna fila de datos; se aborta en vez de "
            f"escribir una hoja de pedido en blanco."
        )
    cabecera = filas[0].split("\t")
    if "guia" not in cabecera:
        raise ShmirDesignError(
            f"{path}: la tabla no tiene columna 'guia' (las que hay: "
            f"{', '.join(cabecera)}); se aborta."
        )
    indice = cabecera.index("guia")
    etiqueta = (
        cabecera.index("inicio_transcrito")
        if "inicio_transcrito" in cabecera
        else None
    )

    candidatos: list[tuple[str, str]] = []
    for numero, fila in enumerate(filas[1:], start=1):
        campos = fila.split("\t")
        if len(campos) <= indice:
            raise ShmirDesignError(
                f"{path}, fila {numero}: tiene {len(campos)} campo(s) y la columna "
                f"'guia' es la {indice + 1}; se aborta en vez de saltarse la fila."
            )
        nombre = campos[etiqueta] if etiqueta is not None else str(numero)
        candidatos.append((nombre, campos[indice].strip()))
    if not candidatos:
        raise ShmirDesignError(f"{path}: no hay ninguna fila de candidato; se aborta.")
    return candidatos


def aplicar_seleccion(
    candidatos: list[tuple[str, str]], elegir: str | None
) -> list[tuple[str, str]]:
    if not elegir:
        return candidatos
    elegidos: list[tuple[str, str]] = []
    for trozo in elegir.split(","):
        trozo = trozo.strip()
        try:
            numero = int(trozo)
        except ValueError as exc:
            raise ShmirDesignError(
                f"--elegir: {trozo!r} no es un numero de fila ({exc})."
            ) from exc
        if not 1 <= numero <= len(candidatos):
            raise ShmirDesignError(
                f"--elegir: la fila {numero} no existe; la tabla tiene "
                f"{len(candidatos)} candidato(s)."
            )
        elegidos.append(candidatos[numero - 1])
    return elegidos


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, help="Directorio de salida (obligatorio)")
    parser.add_argument(
        "--tabla", type=Path, help="TSV comparativo que produjo design.py"
    )
    parser.add_argument(
        "--elegir", help="Filas de la tabla, 1-based y separadas por comas: 1,3,5"
    )
    parser.add_argument(
        "--guia", action="append", default=[], help="Guia suelta; se puede repetir"
    )
    parser.add_argument("--especie", default="candidato")
    parser.add_argument(
        "--reoptimizar-espaciadores", action="store_true",
        help="Si el 97-mero no conserva su estructura dentro del intron con los "
             "espaciadores estandar, genera unos nuevos PARA ESA GUIA. Genera "
             "secuencia de novo, asi que va apagado por defecto; el cassette "
             "resultante deja de ser intercambiable con el modulo NheI-SacI estandar.",
    )
    parser.add_argument(
        "--receptor", type=Path,
        help="FASTA del plasmido receptor. Sin el, los brazos de Gibson del cassette "
             "quedan en NOT_RUN: caen fuera del cassette y no se inventan.",
    )

    args = parser.parse_args(argv)

    try:
        if args.out is None:
            raise ShmirDesignError("Hace falta --out con el directorio de salida.")
        if not args.guia and not args.tabla:
            raise ShmirDesignError(
                "Hace falta --guia (se puede repetir) o --tabla con el TSV comparativo."
            )
        if args.guia and args.tabla:
            raise ShmirDesignError(
                "--guia y --tabla son incompatibles: o se eligen filas de la tabla, o "
                "se dan las guias a mano."
            )

        if args.guia:
            candidatos = [(str(i), g.strip().upper()) for i, g in enumerate(args.guia, 1)]
        else:
            candidatos = aplicar_seleccion(leer_tabla(args.tabla), args.elegir)

        vistas = set()
        for _, guia in candidatos:
            if guia in vistas:
                raise ShmirDesignError(
                    f"La guia {guia} viene repetida; se aborta en vez de pedir dos "
                    f"veces el mismo bloque."
                )
            vistas.add(guia)

        receptor = read_fasta_sequence(args.receptor) if args.receptor else None
        bloques = [
            build_block(
                guia,
                recipient=receptor,
                reoptimize_spacers=args.reoptimizar_espaciadores,
            )
            for _, guia in candidatos
        ]

        args.out.mkdir(parents=True, exist_ok=True)
        hoja = order_sheet(bloques, species=args.especie)
        salidas = {
            "bloques.fasta": blocks_fasta(bloques, species=args.especie),
            "bloques.tsv": blocks_tsv(bloques, species=args.especie),
            "hoja_de_pedido.txt": hoja,
        }
        for nombre, contenido in salidas.items():
            (args.out / nombre).write_text(contenido + "\n", encoding="utf-8")
        print(hoja)
        print(f"\n  Escrito en {args.out}: {', '.join(sorted(salidas))}\n")

        fallos = [
            (b.guide, r.name) for b in bloques for r in b.checks
            if r.state is FilterState.FAIL
        ]
        if fallos:
            for guia, nombre in fallos:
                print(f"FALLA — {guia}: {nombre}", file=sys.stderr)
            return 1
    except (ShmirDesignError, ValueError, OSError) as exc:
        # rule2-ok: frontera CLI. El fallo se imprime entero y sale con codigo 2; no se
        # deja una hoja de pedido a medias que parezca lista para encargar.
        print(f"PARA — {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
