"""Una corrida REAL de carga de off-targets, declarada en un solo sitio.

**No es un fixture sintético** (regla 5): el catálogo son los dos 3'UTR versionados del
repositorio y las seeds salen de `mature.fa`, así que lo único que se declara aquí es
CONTRA QUÉ CATÁLOGO se entiende contada la corrida — que es exactamente el eje que abre
la decisión del 2026-09-08. Su procedencia lo dice con esas palabras: **no es el
transcriptoma**, y por eso las cifras que salen de aquí no se citan en ninguna prosa.

Vive fuera de `test_offtarget_store.py` porque desde el eje de catálogo la necesitan dos
ficheros de test, y dos constructores de la misma corrida son dos corridas que pueden
dejar de parecerse sin que nada falle (principio nº 13).
"""

from pathlib import Path

from shmir_design import offtarget
from shmir_design.offtarget_store import OfftargetRun, OfftargetStore
from shmir_design.presentation import query_name
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"
MATURE = DATOS / "mature.fa"
RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]
HAY = MATURE.is_file() and fixture_available(RATON) and fixture_available(HUMANO)


def _catalogo():
    utr3 = load_3utr(RATON)
    return utr3, offtarget.build_catalog(
        [
            ("NM_011170.3_utr3", utr3),
            ("NM_000311.5_utr3", load_3utr(HUMANO)),
        ],
        provenance=offtarget.Provenance(
            source="fixtures del proyecto (NO es el transcriptoma)",
            assembly="n/a — dos 3'UTR de referencia, no un ensamblaje",
            table="data/reference/NM_011170.3.fa + NM_000311.5.fa",
            table_date="2026-08-26",
            representative="uno por gen porque solo hay dos genes",
            version="fixtures-2026-08-26",
            md5="0" * 32,
        ),
    )


def corrida(*, background: str, species: str = "raton", starts=None):
    """`(seleccion, scan)` sobre el panel murino, contada contra `background`.

    `background` se pasa TAL CUAL —incluida la cadena vacía—: los tests del eje
    necesitan poder construir la corrida de antes del eje, que es la que no declara
    catálogo, y ésa sólo se puede montar saltándose el guardia de `run_scan`.
    """
    from shmir_design.mirna import load_mature_fa
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    utr3, catalogo = _catalogo()
    seleccion = select_from_report(tile_utr(utr3), SelectionConfig(n_candidates=10))
    pedidos = (
        tuple(starts) if starts is not None
        else (seleccion.selection.chosen[0].start,)
    )
    scan = offtarget.run_scan(
        seleccion,
        catalog=catalogo,
        mature=load_mature_fa(MATURE, version="23"),
        species=species,
        starts=pedidos,
        guides=True,
        passengers=True,
        target=utr3,
        target_label="3'UTR de Prnp (raton)",
        # UNA CORRIDA SIN CATALOGO NO SE PUEDE PEDIR, y eso es el guardia haciendo su
        # trabajo. Para construir la de ANTES del eje se declara uno y se retira
        # despues, abajo: fabricarla por otra via seria saltarse el mismo guardia sin
        # dejar rastro de que se hizo a proposito.
        background=background or species,
    )
    if not str(background).strip():
        from dataclasses import replace

        scan = replace(scan, background="")
    return seleccion, scan


def almacen(*, background: str, species: str = "raton", starts=None,
            run_id: str = "off-2026-09-09-fixture") -> OfftargetStore:
    """El almacén con esa corrida dentro, listo para preguntarle un veredicto."""
    _, scan = corrida(background=background, species=species, starts=starts)
    tienda = OfftargetStore()
    tienda.add(
        OfftargetRun.create(
            run_id=run_id, date="2026-09-09", ran_by="la suite", scan=scan,
        )
    )
    return tienda


def consultas(*, species: str = "raton", starts=None) -> tuple[str, ...]:
    """Los nombres de consulta de esa corrida. Se PIDEN, no se escriben."""
    seleccion, scan = corrida(background=species, species=species, starts=starts)
    return tuple(r.query for r in scan.results)
