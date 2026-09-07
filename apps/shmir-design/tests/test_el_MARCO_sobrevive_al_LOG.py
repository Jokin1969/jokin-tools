"""El marco de las posiciones NO sobrevivia al log, y volvia como `3utr:` siempre.

**Reportado el 2026-09-07 con la pagina cortada por la mitad**: `3utr:1768 no cabe en
ningun 3'UTR conocido del proyecto: el mas largo mide 1606 nt`, debajo de la tabla de
candidatos y del bloque de percentiles, y con todo lo de abajo —modales, descargas, paso
5— borrado. Es la novena de la familia del marco, y llega DESPUES de `coords.Position`,
del guardia que impide teclear el prefijo y de los 37 literales corregidos.

**La via que ninguno de los tres guardias veia.** No es un literal ni un prefijo
tecleado: es que el marco **se pierde al escribir el log** —`save_offtarget_run` y
`save_seed_run` no guardaban el campo— y al releer, `LoadResult` y `SeedResult` lo
reponen con su VALOR POR DEFECTO, que era `Frame.UTR3`. Medido sobre el proyecto real,
antes del arreglo:

    marcos al crear la corrida:  {'tx'}
    marcos tras releer el log:   {'3utr'}

Asi que la errata nº 122 —«el bloque de off-targets no miente en el marco»— estaba
arreglada **solo mientras el objeto viviera en memoria**. La contramedida se le puso al
emisor; la capa de persistencia reconstruia el mismo objeto SIN ella, y podia hacerlo en
silencio porque el campo tenia un valor por defecto.

**Y lo que hace que esto se vea tarde**: el techo de `coords` es 1606 —el 3'UTR humano,
que es el mas largo que conoce el proyecto—, asi que de los once candidatos del panel
murino sobre el TRANSCRITO solo abortan los cuatro que pasan de 1606. Los otros siete se
imprimen mal Y EN SILENCIO: `3utr:1398` por `tx:1398`, que es `3utr:449`. El invariante
caza lo imposible, no lo equivocado (principio nº 9).

**Por que ningun test lo cazo** (principio nº 22, y es la otra mitad del hallazgo): los
fixtures de off-targets y de seed tilan el 3'UTR PELADO —`tile_utr(load_3utr(...))`—, y
ahi `tiled_frame` ya es `UTR3`. Sobre ese fixture, un `Frame.UTR3` escrito a mano y uno
derivado son INDISTINGUIBLES. Un fixture que hace coincidir los dos marcos no puede
delatar a quien confunde los dos marcos, corran los tests que corran.

Regla 5: escrito antes.
"""

import unittest

from shmir_design import presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.coords import Frame
from shmir_design.offtarget import DEFAULTS as OFFTARGET_DEFAULTS
from shmir_design.offtarget import Provenance, build_catalog, run_scan
from shmir_design.reference import (
    REFERENCES, fixture_available, load_3utr, load_reference,
)
from shmir_design.trabajo import reference_dir

RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]
MATURE = reference_dir() / "mature.fa"
HAY = fixture_available(RATON) and fixture_available(HUMANO) and MATURE.exists()


def _procedencia():
    """La del catalogo MINIMO de este test, declarada como lo que es.

    Dos 3'UTR de referencia verificados por md5, NO el transcriptoma. Se declara asi
    para que ninguna salida de un test pueda confundirse con una corrida de verdad.
    """
    from shmir_design.identidad import result_fingerprint

    registros = ((RATON.accession, load_3utr(RATON)), (HUMANO.accession, load_3utr(HUMANO)))
    return registros, Provenance(
        source="fixtures del proyecto (NO es el transcriptoma)",
        assembly="n/a — dos 3'UTR de referencia, no un ensamblaje",
        table="data/reference/NM_011170.3.fa + NM_000311.5.fa",
        table_date="2026-08-26",
        representative="uno por gen porque solo hay dos genes",
        version="fixtures-2026-08-26",
        md5=result_fingerprint("".join(s for _, s in registros)),
    )


def _panel_sobre_el_transcrito():
    """El mRNA ENTERO con su anatomia: el unico caso donde `tx` y `3utr` NO coinciden."""
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO
    )
    return secuencia, anatomia, presentation.page_run(
        species="raton", sequence=secuencia, anatomy=anatomia
    )


@unittest.skipUnless(HAY, "NOT_RUN: faltan los fixtures o mature.fa")
class TestElMarcoSobreviveAlLog(unittest.TestCase):
    """Guardar y releer una corrida no puede cambiar en que espacio van sus posiciones."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from pathlib import Path

        from shmir_design.mirna import load_mature_fa
        from shmir_design.seed_scan import DEFAULTS as SEED_DEFAULTS
        from shmir_design.seed_scan import run_scan as seed_scan_run

        cls.secuencia, cls.anatomia, cls.corrida = _panel_sobre_el_transcrito()
        cls.starts = tuple(presentation.chosen_starts(cls.corrida.selection))
        registros, procedencia = _procedencia()
        catalogo = build_catalog(registros, provenance=procedencia)
        maduros = load_mature_fa(MATURE, version="23")

        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        payload, fuente = presentation.anatomy_payload(cls.anatomia)
        almacen = presentation.project_create(
            base, slug="panel_del_transcrito", date="2026-09-07",
            sequence=cls.secuencia, species="raton",
            anatomy=payload, anatomy_source=fuente,
        )
        escaneo = run_scan(
            cls.corrida.selection, catalog=catalogo, mature=maduros,
            params=OFFTARGET_DEFAULTS, species="raton", starts=cls.starts,
            guides=True, passengers=True, target=cls.corrida.utr3,
            target_label="3'UTR de raton",
        )
        cls.marcos_al_crear = {r.frame for r in escaneo.results}
        presentation.save_offtarget_run(
            almacen,
            presentation.offtarget_run_from_scan(
                escaneo, date="2026-09-07", ran_by="test"
            ),
        )
        seed = seed_scan_run(
            cls.corrida.selection, mature=maduros, params=SEED_DEFAULTS,
            species="raton", starts=cls.starts, guides=True, passengers=True,
        )
        cls.marcos_seed_al_crear = {r.frame for r in seed.results}
        presentation.save_seed_run(
            almacen,
            presentation.seed_run_from_scan(seed, date="2026-09-07", ran_by="test"),
        )
        cls.base, cls.slug = base, "panel_del_transcrito"
        cls.almacenes = presentation.load_stores(
            presentation.project_open(base, "panel_del_transcrito")
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_lo_tilado_es_el_TRANSCRITO(self):
        # Si esto deja de ser `tx`, el resto de la clase no prueba nada: sobre un tilado
        # del 3'UTR los dos marcos coinciden y el fallo es invisible.
        from shmir_design import coords

        self.assertIs(coords.frame_of(self.anatomia), Frame.TX)

    def test_al_CREAR_la_corrida_el_marco_ya_era_el_del_transcrito(self):
        self.assertEqual(self.marcos_al_crear, {Frame.TX})
        self.assertEqual(self.marcos_seed_al_crear, {Frame.TX})

    def test_y_al_RELEER_el_log_sigue_siendolo(self):
        corrida = self.almacenes["offtarget"].runs[0]
        self.assertEqual(
            {r.frame for r in corrida.scan.results}, {Frame.TX},
            "el log ha devuelto las posiciones del transcrito en el espacio del 3'UTR: "
            "el campo no se guardaba y el valor por defecto lo repuso.",
        )

    def test_tambien_en_la_corrida_de_seed(self):
        corrida = self.almacenes["seed"].runs[0]
        self.assertEqual({r.frame for r in corrida.scan.results}, {Frame.TX})

    def test_la_tabla_del_modal_de_una_corrida_RELEIDA_dice_tx(self):
        corrida = self.almacenes["offtarget"].runs[0]
        filas = presentation.offtarget_result_rows(corrida.scan)
        etiquetas = {f["candidato"] for f in filas}
        self.assertTrue(all(e.startswith("tx:") for e in etiquetas), sorted(etiquetas))

    def test_los_percentiles_DESTACADOS_no_abortan_y_van_en_tx(self):
        # El emisor concreto que reventó la página: `seed_load_highlights` etiquetaba
        # los inicios del panel con `Frame.UTR3` escrito a mano.
        destacados = presentation.seed_load_highlights(
            stores=self.almacenes, species="raton", starts=self.starts,
        )
        texto = " ".join(
            destacados[c]["texto"] for c in ("carga", "convergencia", "bien_colocados")
        )
        self.assertNotIn("3utr:", texto)
        self.assertIn("tx:", texto)


@unittest.skipUnless(HAY, "NOT_RUN: faltan los fixtures o mature.fa")
class TestUnaCorridaVIEJASinMarcoNoSeLoINVENTA(unittest.TestCase):
    """La otra mitad: los registros escritos ANTES de que el campo existiera.

    El marco no se pone por defecto y tampoco se adivina: se DERIVA de la anatomia que
    el propio proyecto guarda, que es la del panel sobre el que se corrio. Un valor por
    defecto habria contestado `3utr` a un log del transcrito, que es exactamente lo que
    esto cierra.
    """

    def test_sin_el_campo_el_marco_sale_de_la_anatomia_del_proyecto(self):
        import json
        import tempfile
        from pathlib import Path

        secuencia, anatomia, corrida = _panel_sobre_el_transcrito()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload, fuente = presentation.anatomy_payload(anatomia)
            almacen = presentation.project_create(
                base, slug="viejo", date="2026-09-07", sequence=secuencia,
                species="raton", anatomy=payload, anatomy_source=fuente,
            )
            registros, procedencia = _procedencia()
            from shmir_design.mirna import load_mature_fa

            escaneo = run_scan(
                corrida.selection, catalog=build_catalog(registros, provenance=procedencia),
                mature=load_mature_fa(MATURE, version="23"),
                params=OFFTARGET_DEFAULTS, species="raton",
                starts=tuple(presentation.chosen_starts(corrida.selection))[:2],
                guides=True, passengers=False, target=corrida.utr3,
                target_label="3'UTR de raton",
            )
            presentation.save_offtarget_run(
                almacen,
                presentation.offtarget_run_from_scan(
                    escaneo, date="2026-09-07", ran_by="test"
                ),
            )
            # Se le QUITA el campo a mano: asi queda como lo escribio la version que no
            # lo guardaba. El registro se reescribe entero para que la cadena de md5
            # siga cuadrando.
            log = next(base.glob("viejo/*.jsonl"))
            lineas = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
            for linea in lineas:
                for resultado in linea.get("payload", {}).get("results", []):
                    resultado.pop("frame", None)
            log.write_text(
                "".join(json.dumps(l, ensure_ascii=False, sort_keys=True) + "\n"
                        for l in lineas),
                encoding="utf-8",
            )
            from shmir_design.store import ProjectStore, load_offtarget_store

            releido = load_offtarget_store(ProjectStore.open(base, "viejo"))
            self.assertEqual(
                {r.frame for r in releido.runs[0].scan.results}, {Frame.TX},
                "un registro sin el campo tiene que sacar el marco de la anatomía del "
                "proyecto, no de un valor por defecto.",
            )


if __name__ == "__main__":
    unittest.main()
