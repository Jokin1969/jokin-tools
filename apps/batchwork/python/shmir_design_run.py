"""Puente entre Batchwork y el CLI de shmir-design.

No contiene logica: añade `apps/shmir-design` al `sys.path` y llama a
`tools.design.main()`, que es el mismo punto de entrada que se usa por linea de
comandos y que tiene sus tests. Si algo cambia en el diseño, cambia alli.

Batchwork lee de stdout las lineas `PROGRESS:` / `ERROR:` / `WARN:`; el resto (el
informe completo) se ignora, asi que el informe sigue saliendo tal cual en los ficheros.
"""

import sys
from pathlib import Path

SHMIR_ROOT = Path(__file__).resolve().parents[2] / "shmir-design"


def main(argv):
    if not SHMIR_ROOT.is_dir():
        print(
            f"ERROR::No se encuentra el proyecto shmir-design en {SHMIR_ROOT}; "
            f"se aborta el diseño.",
            flush=True,
        )
        return 2

    sys.path.insert(0, str(SHMIR_ROOT))
    from tools.design import main as design_main  # noqa: E402

    print("PROGRESS:0:1:Analizando el 3'UTR...", flush=True)
    code = design_main(argv)
    if code == 0:
        print("PROGRESS:1:1:Diseño terminado", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
