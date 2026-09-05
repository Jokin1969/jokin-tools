"""Ninguna tabla que se exporta acorta una secuencia.

**De donde sale (2026-09-02)**: se reporto un heptamero de SEIS caracteres en la columna
`heptamero` del CSV descargable. Los tres productores del heptamero se midieron y los
tres dan siete, asi que ese caso concreto NO se reprodujo y no se le asigna causa. Lo que
si se decidio es que la clase de fallo tenga guardia.

**Por que hace falta un guardia y no basta con haberlo medido una vez** (principio nº 14,
«haber comprobado una vez no es seguir comprobando»): este fallo no da ningun error. Un
heptamero truncado a seis SIGUE SIENDO una seed valida y DISTINTA, asi que la carga que
sale a su lado es un numero correcto para otra pregunta. Es la familia del «Alu 0 %».

**Y no es un analisis del fuente: se CORREN las tablas.** Un barrido de AST buscando
rebanadas no distingue `guia[:8]` de una etiqueta cortada, y las que importan son las
tablas tal como salen. Por eso este auditor tila el 3'UTR murino de verdad y mira lo que
emiten los productores.

Es un GUARDIA, no un trinquete: el numero correcto es cero.

  - **La columna de secuencia NO se declara por su nombre**: se DERIVA del contenido, asi
    que una columna nueva entra sola. Lo que si se declara es de donde sale su LONGITUD
    ESPERADA, y una columna de secuencia sin esa declaracion ABORTA — ignorarla dejaria
    el guardia en «las columnas de las que alguien se acordo».
  - Y la longitud esperada **se deriva del objeto que produjo la tabla**, nunca de un
    numero escrito: escribir un 7 para el heptamero seria afirmar que la ventana es 2-8,
    que es justo lo que hay que comprobar (principio nº 13). Con `2-7` mide seis y eso
    es CORRECTO.

La corrida de colision de seed —la del CSV que se reporto— no entra aqui porque necesita
barrer `mature.fa` (5,6 MB) y este auditor corre en cada `npm run check:shmir`. La cubre
`tests/test_ninguna_tabla_TRUNCA_una_secuencia.py`, con el mismo `check_no_truncation`.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import audit, comparative, presentation  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.polya import ALL_SIGNALS  # noqa: E402
from shmir_design.reference import REFERENCES, fixture_available, load_3utr  # noqa: E402
from shmir_design.scaffold import SGEP_SCAFFOLD  # noqa: E402
from shmir_design.selection import default_config, select_from_report  # noqa: E402
from shmir_design.tiling import tile_utr  # noqa: E402

RATON = REFERENCES["NM_011170.3"]


@dataclass(frozen=True)
class Informe:
    tablas: tuple[str, ...] = ()
    columnas: int = 0
    hallazgos: tuple[str, ...] = field(default_factory=tuple)
    #: Sin el fixture del raton no hay tablas que mirar. NO es «cero hallazgos».
    sin_fixture: bool = False


def _unico(valores, que: str) -> int:
    largos = set(valores)
    if len(largos) != 1:
        raise ShmirDesignError(
            f"{que}: no todos miden lo mismo ({sorted(largos)}), así que no hay una "
            f"longitud esperada que declarar. Se aborta en vez de coger una."
        )
    return largos.pop()


def auditar() -> Informe:
    if not fixture_available(RATON):
        return Informe(sin_fixture=True)

    informe = tile_utr(load_3utr(RATON))
    seleccion = select_from_report(informe, default_config())

    ventana = _unico((v.window.length for v in informe.windows), "las ventanas tiladas")
    guia = _unico(
        (
            len(seleccion.windows[elegido.label].evaluation.guide)
            for elegido in seleccion.selection.chosen
        ),
        "las guías del panel",
    )
    hexamero = _unico((len(h) for h in ALL_SIGNALS), "los hexámeros de polyA")

    cabecera, *cuerpo = comparative.comparative_rows(seleccion, SGEP_SCAFFOLD)
    tabla_comparativa = [dict(zip(cabecera, fila, strict=True)) for fila in cuerpo]
    gblock = _unico(
        (
            len(f["gblock_149"])
            for f in tabla_comparativa
            if str(f["gblock_149"]).strip()
        ),
        "los módulos NheI-SacI",
    ) if any(str(f["gblock_149"]).strip() for f in tabla_comparativa) else 0
    # La feature de SplashRNA es la MISMA ventana de seed que el heptamero del modal:
    # se deriva del mismo sitio en vez de escribir un 7 en dos.
    from shmir_design.seed_scan import DEFAULTS as SEED_DEFAULTS  # noqa: PLC0415

    tablas = {
        "candidate_rows": (
            presentation.candidate_rows(seleccion),
            {"diana": ventana, "guia": guia, "pasajera": guia,
             "polyA_hexamero": hexamero},
        ),
        "site_table_rows": (
            presentation.site_table_rows(informe, seleccion),
            {"guia": guia, "pasajera": guia},
        ),
        "window_rows": (
            presentation.window_rows(informe), {"diana": ventana, "guia": guia},
        ),
        "seed_preview_rows": (
            presentation.seed_preview_rows(seleccion, species="mouse"),
            {"secuencia": guia, "heptamero": SEED_DEFAULTS.length,
             "nucleo": SEED_DEFAULTS.length - 1},
        ),
        "comparative_rows": (
            tabla_comparativa,
            {"diana": ventana, "guia": guia, "pasajera": guia,
             "gblock_149": gblock, "polyA_hexamero": hexamero,
             "feat_seed": SEED_DEFAULTS.length},
        ),
    }

    hallazgos: list[str] = []
    columnas = 0
    for nombre, (filas, esperado) in tablas.items():
        columnas += len(audit.sequence_columns(filas))
        try:
            audit.check_no_truncation(filas, expected=esperado, table=nombre)
        except ShmirDesignError as exc:
            # rule2-ok: el hallazgo ES el producto de esta herramienta. Se recoge
            # entero y se imprime; no se degrada a nada.
            hallazgos.append(str(exc))
    return Informe(
        tablas=tuple(tablas), columnas=columnas, hallazgos=tuple(hallazgos),
    )


def render(informe: Informe) -> str:
    lineas = ["", "  Truncamiento en las tablas que se exportan:"]
    if informe.sin_fixture:
        lineas.append(
            "    NO COMPROBADO — falta el fixture del 3'UTR murino, así que no hay "
            "ninguna tabla que mirar. No es «cero hallazgos»."
        )
        lineas.append("")
        return "\n".join(lineas)
    lineas.append(
        f"    {len(informe.tablas)} tabla(s), {informe.columnas} columna(s) de secuencia "
        f"derivadas del contenido."
    )
    if not informe.hallazgos:
        lineas.append("    0 — el número correcto. No es un trinquete: es un guardia.")
    for hallazgo in informe.hallazgos:
        lineas.append(f"    ⚠  {hallazgo}")
    lineas.append("")
    lineas.append(f"  {audit.WHY_TRUNCATION_IS_SILENT}")
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    informe = auditar()
    print(render(informe))
    return 1 if informe.hallazgos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
