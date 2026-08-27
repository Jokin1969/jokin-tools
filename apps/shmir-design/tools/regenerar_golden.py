#!/usr/bin/env python3
"""Regenera el informe de referencia (`tests/golden/`) que fija la salida ENTERA.

El test `tests/test_informe_golden.py` compara el informe COMPLETO contra el fichero de
esta carpeta. No comprueba que aparezcan unos fragmentos: comprueba que no falte ni
sobre NADA. Es la contramedida a un borrado real de 127 lineas —el bloque del TECHO y
los inmunes enteros— que ningun test de presencia detecto, porque cada test miraba lo
que el se esperaba y nadie miraba el conjunto.

Uso:

    python3 tools/regenerar_golden.py

Solo se regenera A MANO y el diff entra en la revision: si el fichero cambia sin que
nadie haya tocado el informe a proposito, eso es exactamente lo que hay que ver.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GOLDEN = RAIZ / "tests" / "golden" / "raton_informe.txt"
FICHA = RAIZ / "tests" / "golden" / "ficha_raton_200.txt"
DOCUMENTO = RAIZ / "tests" / "golden" / "informe_documento.md"
PAGINA = RAIZ / "tests" / "golden" / "pagina_raton.txt"

#: La fecha del documento va FIJADA: si saliera la de hoy, el golden
#: cambiaria cada dia y el diff dejaria de significar nada.
FECHA_GOLDEN = "2026-08-26"

#: La corrida que se fija. Solo ficheros VERSIONADOS: el golden tiene que poder
#: regenerarse con un clon limpio del repositorio, sin pedirle nada a nadie.
ARGV = [
    "--fasta", "data/reference/NM_011170.3.fa",
    "--name", "raton",
    "--genbank", "data/reference/NM_011170.3.gb",
    "--fasta-b", "data/reference/NM_000311.5.fa",
    "--name-b", "humano",
    "--genbank-b", "data/reference/NM_000311.5.gb",
    "--convergencia", "data/reference/mirarchitect_prnp_export_buena.csv",
    "--min-block", "22",
    "--candidates", "10",
    "--inmunes", "4",
    "--sin-manifiesto",
]


def generar(destino: Path) -> str:
    """Corre el diseño de verdad y devuelve el informe del raton."""
    with tempfile.TemporaryDirectory() as tmp:
        proceso = subprocess.run(
            [sys.executable, "tools/design.py", *ARGV, "--out", tmp],
            cwd=RAIZ, capture_output=True, text=True,
        )
        if proceso.returncode != 0:
            raise SystemExit(
                f"El diseño fallo con código {proceso.returncode}; no se regenera el "
                f"golden con una salida incompleta.\n{proceso.stdout}\n{proceso.stderr}"
            )
        return (Path(tmp) / "raton_informe.txt").read_text(encoding="utf-8")


def generar_ficha() -> str:
    """La ficha de `3utr:200`, con la misma disciplina que el informe: entera.

    Se fija la del `200` porque es el candidato que mas cosas reune a la vez: inmune al
    truncamiento, marcado en el esterico, sin techo, con un hexamero promovido por medida
    a 14 nt y sin ninguna corrida de BLAST — o sea, con `NOT_RUN` visible.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ))
    from shmir_design.apa import POLYA_DB_PRNP, resolve_measured
    from shmir_design.dossier import build_dossier
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(REFERENCES["NM_011170.3"])
    informe = tile_utr(utr3, measured_apa=resolve_measured(utr3, POLYA_DB_PRNP))
    seleccion = select_from_report(
        informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
    )
    return build_dossier(
        species="raton", tiling=informe, selection=seleccion, start=200,
        # Con `target` la ficha puede contar los sitios de esta seed en su PROPIA diana,
        # que es lo que descubrio que cuatro del panel tienen un segundo sitio.
        target=utr3,
    ).render()


def generar_documento() -> str:
    """El informe-documento entero, en su fuente markdown.

    Hoy sale PARCIAL porque hay frentes abiertos, y eso es parte de lo que fija: el dia
    que se cierre uno, el golden lo enseñara en el diff.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ))
    from shmir_design.apa import POLYA_DB_PRNP, resolve_measured
    from shmir_design.informe_doc import build_document
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(REFERENCES["NM_011170.3"])
    informe = tile_utr(utr3, measured_apa=resolve_measured(utr3, POLYA_DB_PRNP))
    seleccion = select_from_report(
        informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
    )
    return build_document(
        species="mouse", tiling=informe, selection=seleccion,
        generated=FECHA_GOLDEN,
        anatomy_source="lo tilado ES el 3'UTR (fixture verificado por md5)",
        dossier_starts=(200,), target=utr3,
    ).markdown()


def generar_pagina() -> str:
    """El camino de la PAGINA, entero, con lo que el usuario sube: el `.gb` murino.

    Es el golden que faltaba. Los otros tres fijan salidas del nucleo; este fija la
    juntura entre piezas —anatomia, tilado, estimacion, mapa, semaforo, informe— que es
    donde aparecieron los tres fallos de la primera ejecucion real con 2.767 tests en
    verde.

    Solo ficheros VERSIONADOS, como los demas: sin manifiesto, para que se regenere con
    un clon limpio.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ))
    from shmir_design.anatomy import Anatomy, RegionSource
    from shmir_design.presentation import page_snapshot
    from shmir_design.reference import REFERENCES, load_reference
    from shmir_design.selection import SelectionConfig

    referencia = REFERENCES["NM_011170.3"]
    secuencia = load_reference(referencia)
    return page_snapshot(
        species="raton",
        sequence=secuencia,
        anatomy=Anatomy.from_cds(
            cds=referencia.cds,
            length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        ),
        generated=FECHA_GOLDEN,
        config=SelectionConfig(n_candidates=10, apa_immune_quota=4),
    )


def main() -> int:
    informe = generar(GOLDEN)
    antes = GOLDEN.read_text(encoding="utf-8") if GOLDEN.is_file() else ""
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(informe, encoding="utf-8")
    lineas = len(informe.splitlines())
    if antes == informe:
        print(f"Sin cambios: {GOLDEN} ({lineas} lineas).")
    else:
        print(f"Regenerado {GOLDEN}: {lineas} líneas (antes {len(antes.splitlines())}).")
        print("Revisa el diff ANTES de commitear: es la salida entera del informe.")

    ficha = generar_ficha()
    previa = FICHA.read_text(encoding="utf-8") if FICHA.is_file() else ""
    FICHA.write_text(ficha, encoding="utf-8")
    if previa == ficha:
        print(f"Sin cambios: {FICHA} ({len(ficha.splitlines())} lineas).")
    else:
        print(f"Regenerada {FICHA}: {len(ficha.splitlines())} lineas.")
        print("Revisa también ese diff: la ficha se compara ENTERA.")

    documento = generar_documento()
    anterior = DOCUMENTO.read_text(encoding="utf-8") if DOCUMENTO.is_file() else ""
    DOCUMENTO.write_text(documento, encoding="utf-8")
    if anterior == documento:
        print(f"Sin cambios: {DOCUMENTO} ({len(documento.splitlines())} lineas).")
    else:
        print(f"Regenerado {DOCUMENTO}: {len(documento.splitlines())} lineas.")
        print("Y ese también entero: es el informe que se entrega.")

    pagina = generar_pagina()
    previo = PAGINA.read_text(encoding="utf-8") if PAGINA.is_file() else ""
    PAGINA.write_text(pagina, encoding="utf-8")
    if previo == pagina:
        print(f"Sin cambios: {PAGINA} ({len(pagina.splitlines())} lineas).")
    else:
        print(f"Regenerado {PAGINA}: {len(pagina.splitlines())} lineas.")
        print("Este es el camino de la PAGINA: leelo entero, es donde se junta todo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
