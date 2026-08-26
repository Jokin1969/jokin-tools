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
    "--inmunes-antes", "1252",
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
                f"El diseño fallo con codigo {proceso.returncode}; no se regenera el "
                f"golden con una salida incompleta.\n{proceso.stdout}\n{proceso.stderr}"
            )
        return (Path(tmp) / "raton_informe.txt").read_text(encoding="utf-8")


def main() -> int:
    informe = generar(GOLDEN)
    antes = GOLDEN.read_text(encoding="utf-8") if GOLDEN.is_file() else ""
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(informe, encoding="utf-8")
    lineas = len(informe.splitlines())
    if antes == informe:
        print(f"Sin cambios: {GOLDEN} ({lineas} lineas).")
    else:
        print(f"Regenerado {GOLDEN}: {lineas} lineas (antes {len(antes.splitlines())}).")
        print("Revisa el diff ANTES de commitear: es la salida entera del informe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
