#!/usr/bin/env python3
"""Genera el informe-documento (markdown + docx + pdf) desde la linea de ordenes.

El boton de la pagina y esto hacen LO MISMO y llaman a la misma funcion: si divergieran,
el informe que se entrega no seria el que se revisa. Sale parcial o completo segun los
frentes; no hay una opcion para pedir uno u otro, porque eso permitiria presentar como
completo algo que no lo esta.

Uso:

    python3 tools/informe.py --fasta data/reference/NM_011170.3.fa \\
        --especie mouse --fecha 2026-08-26 --salida /tmp/informe

Los tres ficheros salen con el sufijo `_parcial` o `_completo` en el nombre: el estado
viaja en el nombre del fichero, no solo dentro.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from shmir_design.presentation import informe_documento, informe_files  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.fetch import parse_fasta_payload  # noqa: E402
from shmir_design.polya import normalize_sequence  # noqa: E402
from shmir_design.resolve import check_boundaries, resolve_anatomy  # noqa: E402
from shmir_design.selection import SelectionConfig, select_from_report  # noqa: E402
from shmir_design.tiling import tile_utr  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasta", required=True, help="FASTA de lo que se va a tilar")
    parser.add_argument("--especie", required=True, help="nombre de la especie")
    parser.add_argument(
        "--fecha", required=True,
        help="fecha del informe. Obligatoria: un informe sin fecha no se puede situar",
    )
    parser.add_argument("--salida", required=True, help="prefijo de los ficheros")
    parser.add_argument("--candidatos", type=int, default=10)
    # La anatomia NO se adivina: hay tres vias y hay que elegir una. Sin ella, un mRNA
    # completo se tilaria entero como si fuera 3'UTR y con el todos los tercios.
    anatomia = parser.add_mutually_exclusive_group(required=True)
    anatomia.add_argument("--genbank", help="el .gb del RefSeq: el CDS lo declara el")
    anatomia.add_argument("--cds", help="coordenadas del CDS, 1-based: `inicio-fin`")
    anatomia.add_argument(
        "--region-3utr", action="store_true",
        help="lo que se pasa YA es el 3'UTR entero",
    )
    args = parser.parse_args(argv)

    ruta_fasta = Path(args.fasta)
    _, cruda = parse_fasta_payload(
        ruta_fasta.read_text(encoding="utf-8"), source=str(ruta_fasta)
    )
    secuencia = normalize_sequence(cruda, name=f"secuencia de {ruta_fasta}")
    cds = None
    if args.cds:
        inicio, _, fin = args.cds.partition("-")
        cds = (int(inicio), int(fin))
    anat = resolve_anatomy(
        name=args.especie, sequence=secuencia,
        genbank=Path(args.genbank) if args.genbank else None,
        cds=cds, whole_is_utr3=args.region_3utr or None,
    )
    for aviso in check_boundaries(secuencia, anat):
        print(f"AVISO: {aviso}")
    # `resolve_measured` recibe la ANATOMIA y coloca la tabla en el marco que toca. No
    # se le desplazan las coordenadas aqui: convertir marcos a mano es justo el fallo
    # que este proyecto lleva cazando desde el principio.
    informe = tile_utr(
        secuencia, anatomy=anat,
        # La tabla la resuelve `tile_utr` del FICHERO del gestor: aqui no se pasa.
    )
    seleccion = select_from_report(
        informe, SelectionConfig(n_candidates=args.candidatos, apa_immune_quota=4)
    )
    # La anatomia se PASA, no se deduce: el CLI la tiene resuelta y la pagina tambien,
    # asi que el mismo documento sale con la misma seccion por los dos caminos. Sin esto,
    # el informe descargado desde el navegador traeria una tabla que el del CLI no, que es
    # justo la divergencia entre frontales que este proyecto lleva cazando.
    documento = informe_documento(
        seleccion, informe, species=args.especie, generated=args.fecha,
        anatomy_source=anat.source.value, anatomy=anat,
    )

    destino = Path(args.salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    entregables = informe_files(documento, stem=destino.name)
    # AQUI UN FORMATO ROTO ABORTA, y en la pagina no. No es incoherencia: son dos
    # situaciones distintas. En la pagina cada entregable tiene su sitio en pantalla, asi
    # que el motivo se ve y los otros dos siguen sirviendo; aqui no hay nadie mirando
    # tres columnas — un CLI que escribe dos ficheros de tres y sale con 0 deja media
    # entrega que parece completa.
    rotos = [e for e in entregables if e["error"]]
    if rotos:
        raise ShmirDesignError(
            "No se han podido generar todos los formatos del informe, así que no se "
            "escribe ninguno: una entrega a medias no se distingue de una completa.\n"
            + "\n".join(f"  {e['nombre']}: {e['error']}" for e in rotos)
        )
    for entregable in entregables:
        ruta = destino.parent / entregable["nombre"]
        ruta.write_bytes(entregable["datos"])
        print(f"{ruta}  ({len(entregable['datos'])} bytes)")

    print(f"\nEstado: {documento.state}")
    if documento.open_fronts:
        print("Frentes abiertos: " + ", ".join(documento.open_fronts))
        print(
            "No se pide oligo hasta que todos tengan veredicto. Cada uno lleva su ficha "
            "de obtencion dentro del informe, en la seccion 3."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
