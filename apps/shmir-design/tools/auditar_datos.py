#!/usr/bin/env python3
"""¿Qué datos concretos de una especie siguen viviendo en el código?

Es la generalización de lo que ya pasó tres veces —`rmsk_mouse.out` conectado por rol,
`txid10090` por defecto, `mmu-` por defecto—: **un dato de UNA especie escrito en el
código funciona callado y sobre otra produce un resultado con la forma correcta**.

Separa TRES cosas, y la distinción es lo único que hace útil el informe:

  · **DATO** — una medida, una tabla o una lista de una especie concreta. Debería estar
    en un fichero del gestor, con md5 y procedencia: en código no es auditable dentro
    de un año y no se puede cambiar sin tocar el código.
  · **DECLARACIÓN** — un valor que el proyecto DECIDE y que no sale de ninguna medida.
    Va en código a propósito, porque es la fuente única y en un fichero se podría
    cambiar sin que se viera en el diff.
  · **PROSA** — razonamiento, avisos y motivos. Van pegados a lo que explican.

No falla nunca: es un informe. Lo que falla es el test, si aparece una constante
sospechosa sin clasificar o queda una entrada muerta en la tabla.

    python3 tools/auditar_datos.py
"""

import ast
import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAQUETE = RAIZ / "shmir_design"
TABLA = RAIZ / "data" / "datos_en_codigo.toml"

#: Que hace sospechosa a una constante: que nombre algo de UNA especie o UN gen. Es
#: deliberadamente amplia — un falso positivo cuesta una linea en la tabla; un falso
#: negativo es un dato murino escondido en el codigo.
PISTAS = re.compile(
    r"prnp|mmu-|hsa-|mus musculus|homo sapiens|raton|ratón|txid10090|txid9606|"
    r"mm39|mm10|hg38|131937|131938|polya_db|miR-124|miR-9-|let-7|G130E|W144Y|pAAV",
    re.IGNORECASE,
)

CATEGORIAS = ("dato", "declaracion", "prosa")


def _constantes():
    """Constantes de modulo (NOMBRE_EN_MAYUSCULAS) cuyo valor nombra una especie o gen."""
    for ruta in sorted(PAQUETE.glob("*.py")):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        for nodo in arbol.body:
            objetivo = None
            if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1:
                objetivo = nodo.targets[0]
            elif isinstance(nodo, ast.AnnAssign):
                objetivo = nodo.target
            if not isinstance(objetivo, ast.Name):
                continue
            nombre = objetivo.id
            if not nombre.replace("_", "").isupper():
                continue
            texto = ast.unparse(nodo)
            if PISTAS.search(texto):
                yield f"{ruta.stem}.{nombre}", nodo.lineno, len(texto)


def auditar() -> dict:
    datos = tomllib.loads(TABLA.read_text(encoding="utf-8"))
    declarado = {e["simbolo"]: e for e in datos.get("constante", ())}
    encontradas = dict((s, (n, t)) for s, n, t in _constantes())

    entradas = []
    for simbolo, (linea, tamano) in sorted(encontradas.items()):
        ficha = declarado.get(simbolo)
        if ficha is None:
            continue
        entradas.append({**ficha, "linea": linea, "tamano": tamano})

    por_categoria: dict[str, list] = {c: [] for c in CATEGORIAS}
    for entrada in entradas:
        por_categoria.setdefault(entrada["categoria"], []).append(entrada)

    return {
        "entradas": entradas,
        "sin_clasificar": [s for s in encontradas if s not in declarado],
        "huerfanas": [s for s in declarado if s not in encontradas],
        "por_categoria": por_categoria,
    }


def main() -> int:
    informe = auditar()
    print(__doc__)
    print("=" * 78)
    for categoria, titulo in (
        ("dato", "DATO — debería estar en un fichero del gestor"),
        ("declaracion", "DECLARACIÓN — va en código a propósito"),
        ("prosa", "PROSA — va pegada a lo que explica"),
    ):
        filas = informe["por_categoria"].get(categoria, [])
        print()
        print(f"── {titulo} ({len(filas)}) ──")
        for fila in filas:
            destino = f"  → {fila['fichero']}" if fila.get("fichero") else ""
            print(f"  {fila['simbolo']}:{fila['linea']}{destino}")
            for linea in _envolver(fila["motivo"], 74):
                print(f"      {linea}")
    if informe["sin_clasificar"]:
        print()
        print("SIN CLASIFICAR (hacen fallar el test):")
        for s in sorted(informe["sin_clasificar"]):
            print(f"  {s}")
    if informe["huerfanas"]:
        print()
        print("HUÉRFANAS — en la tabla y ya no en el código:")
        for s in sorted(informe["huerfanas"]):
            print(f"  {s}")
    return 0


def _envolver(texto: str, ancho: int) -> list[str]:
    palabras, linea, salida = texto.split(), "", []
    for palabra in palabras:
        if linea and len(linea) + 1 + len(palabra) > ancho:
            salida.append(linea)
            linea = palabra
        else:
            linea = f"{linea} {palabra}".strip()
    if linea:
        salida.append(linea)
    return salida


if __name__ == "__main__":
    sys.exit(main())
