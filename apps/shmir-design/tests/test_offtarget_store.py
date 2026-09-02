"""El almacen del tercer modal. Mismo patron que los otros dos.

Regla 5: escritos antes.

Dos cosas que este almacen tiene que garantizar y que los otros no piden igual:

  - **nunca FAIL**: este frente es DESEMPATE, no filtro, asi que ningun camino puede
    devolver un veredicto que excluya a nadie;
  - **el percentil y el limite superior viajan con el veredicto**: un conteo sin
    percentil no es interpretable, y un percentil sin la advertencia de que las tres
    limitaciones sobrestiman se lee como una medida.
"""

import unittest
from pathlib import Path

from shmir_design import offtarget, offtarget_store
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

from shmir_design.presentation import query_name

# EL NOMBRE DE UNA CONSULTA SE PIDE, NO SE ESCRIBE. Estos tests transcribian
# `raton_pos200_guia`, que es un formato que la app YA NO PRODUCE —el slug de la especie
# es `mouse`, no `raton`—: coincidian consigo mismos, asi que el desfase no se veia. Es
# la mitad que dejo pasar la errata nº 44. Ver `data/claves_derivadas.toml`.
def Q(inicio, hebra="guia", especie="mouse"):
    return query_name(especie, inicio, hebra)


DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"
MATURE = DATOS / "mature.fa"
RATON = REFERENCES["NM_011170.3"]
HUMANO = REFERENCES["NM_000311.5"]
HAY = MATURE.is_file() and fixture_available(RATON) and fixture_available(HUMANO)


def _corrida():
    from shmir_design.mirna import load_mature_fa
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(RATON)
    seleccion = select_from_report(
        tile_utr(utr3), SelectionConfig(n_candidates=10)
    )
    catalogo = offtarget.build_catalog(
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
    return seleccion, offtarget.run_scan(
        seleccion,
        catalog=catalogo,
        mature=load_mature_fa(MATURE, version="23"),
        species="raton",
        starts=(seleccion.selection.chosen[0].start,),
        guides=True,
        passengers=True,
        target=utr3,
        target_label="3'UTR de Prnp (raton)",
    )


class TestElNombreDelFrente(unittest.TestCase):

    def test_es_offtarget_seed_y_NO_especificidad(self):
        self.assertEqual(offtarget_store.FILTER_NAME, "offtarget_seed")
        self.assertNotEqual(offtarget_store.FILTER_NAME, "especificidad")

    def test_sin_corrida_el_veredicto_es_NOT_RUN_y_nombra_el_fichero(self):
        almacen = offtarget_store.OfftargetStore()
        veredicto = almacen.verdict_for(Q(10))
        self.assertIs(veredicto.state, FilterState.NOT_RUN)
        self.assertIn(offtarget.MISSING_FILE, veredicto.reason)

    def test_y_NOT_RUN_no_es_cero(self):
        almacen = offtarget_store.OfftargetStore()
        texto = almacen.verdict_for(Q(10)).reason.lower()
        self.assertIn("no es cero", texto)

    def test_NO_existe_un_veredicto_por_candidato(self):
        """Guia y pasajera son dos consultas, igual que en el modal de colision."""
        self.assertFalse(hasattr(offtarget_store.OfftargetStore, "verdict_for_candidate"))


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o alguno de los dos fixtures")
class TestElAlmacen(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.seleccion, cls.scan = _corrida()

    def _run(self, run_id="OT-1"):
        return offtarget_store.OfftargetRun.create(
            run_id=run_id, date="2026-08-26", ran_by="jokin", scan=self.scan,
        )

    def test_una_corrida_necesita_id_fecha_y_quien(self):
        for campo in ("run_id", "date", "ran_by"):
            with self.assertRaises(ValueError):
                offtarget_store.OfftargetRun.create(
                    **{
                        **{"run_id": "OT-1", "date": "2026-08-26", "ran_by": "jokin"},
                        campo: "  ",
                        "scan": self.scan,
                    }
                )

    def test_repetir_un_id_ABORTA_porque_nada_se_sobrescribe(self):
        almacen = offtarget_store.OfftargetStore()
        almacen.add(self._run())
        with self.assertRaises(ShmirDesignError):
            almacen.add(self._run())

    def test_una_corrida_nueva_se_AÑADE_y_la_ficha_enseña_la_ultima(self):
        almacen = offtarget_store.OfftargetStore()
        almacen.add(self._run("OT-1"))
        almacen.add(
            offtarget_store.OfftargetRun.create(
                run_id="OT-2", date="2026-08-27", ran_by="jokin", scan=self.scan,
            )
        )
        consulta = self.scan.results[0].query
        self.assertEqual(len(almacen.history(consulta)), 2)
        self.assertEqual(almacen.latest(consulta).run_id, "OT-2")

    def test_el_veredicto_NUNCA_es_FAIL(self):
        almacen = offtarget_store.OfftargetStore()
        almacen.add(self._run())
        for resultado in self.scan.results:
            veredicto = almacen.verdict_for(resultado.query)
            self.assertIsNot(
                veredicto.state, FilterState.FAIL,
                "Este frente es DESEMPATE, no filtro: no puede excluir a nadie.",
            )
            self.assertIs(veredicto.state, FilterState.PASS)

    def test_el_veredicto_trae_LAS_CUATRO_clases_con_su_percentil(self):
        almacen = offtarget_store.OfftargetStore()
        almacen.add(self._run())
        motivo = almacen.verdict_for(self.scan.results[0].query).reason
        for clase in offtarget.SITE_CLASSES:
            self.assertIn(clase, motivo)
        self.assertIn("p", motivo)

    def test_y_trae_el_aviso_de_LIMITE_SUPERIOR(self):
        almacen = offtarget_store.OfftargetStore()
        almacen.add(self._run())
        motivo = almacen.verdict_for(self.scan.results[0].query).reason.lower()
        self.assertIn("límite superior", motivo)

    def test_y_dice_que_es_DESEMPATE(self):
        almacen = offtarget_store.OfftargetStore()
        almacen.add(self._run())
        motivo = almacen.verdict_for(self.scan.results[0].query).reason.lower()
        self.assertIn("desempate", motivo)

    def test_una_consulta_que_no_esta_en_la_corrida_sigue_NOT_RUN(self):
        almacen = offtarget_store.OfftargetStore()
        almacen.add(self._run())
        self.assertIs(
            almacen.verdict_for(Q(99999)).state, FilterState.NOT_RUN
        )

    def test_el_md5_del_resultado_y_la_procedencia_del_fichero_quedan_guardados(self):
        corrida = self._run()
        self.assertEqual(len(corrida.result_md5), 32)
        descripcion = " ".join(corrida.describe())
        self.assertIn("ensamblaje", descripcion)
        self.assertIn(self.scan.provenance.table_date, descripcion)
        self.assertIn(self.scan.provenance.md5, descripcion)

    def test_si_el_catalogo_esta_INFLADO_el_veredicto_lo_dice(self):
        """Un conteo sobre un fichero con isoformas repetidas no se presenta a secas."""
        almacen = offtarget_store.OfftargetStore()
        almacen.add(self._run())
        motivo = almacen.verdict_for(self.scan.results[0].query).reason
        self.assertIn("comprobar", motivo.lower())

    def test_unos_ajustes_modificados_VIAJAN_con_el_veredicto(self):
        from dataclasses import replace

        scan = replace(
            self.scan, params=offtarget.OfftargetParams(null_seed=99)
        )
        corrida = offtarget_store.OfftargetRun.create(
            run_id="OT-9", date="2026-08-26", ran_by="jokin", scan=scan,
        )
        almacen = offtarget_store.OfftargetStore()
        almacen.add(corrida)
        motivo = almacen.verdict_for(scan.results[0].query).reason
        self.assertIn("MODIFICADOS", motivo)
        self.assertIn("null_seed", motivo)


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o alguno de los dos fixtures")
class TestLaPersistencia(unittest.TestCase):
    """La corrida sobrevive a la sesion, y en el MISMO log que los otros dos modales."""

    @classmethod
    def setUpClass(cls):
        cls.seleccion, cls.scan = _corrida()

    def _proyecto(self, carpeta):
        from shmir_design import store as store_mod

        proyecto = store_mod.ProjectStore.create(
            carpeta, slug="p", created="2026-08-26",
            sequence=load_3utr(RATON), species="raton",
            anatomy={"utr3_start": 1}, anatomy_source="genbank",
        )
        return store_mod, proyecto

    def test_el_tipo_de_registro_esta_declarado_en_el_log(self):
        from shmir_design import store as store_mod

        self.assertIn("corrida_offtarget", store_mod.RECORD_KINDS)

    def test_se_guarda_y_se_vuelve_a_leer_con_LOS_MISMOS_percentiles(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            store_mod, proyecto = self._proyecto(Path(tmp))
            corrida = offtarget_store.OfftargetRun.create(
                run_id="OT-1", date="2026-08-26", ran_by="jokin", scan=self.scan,
            )
            store_mod.save_offtarget_run(proyecto, corrida)

            de_vuelta = store_mod.load_offtarget_store(
                store_mod.ProjectStore.open(Path(tmp), "p")
            )
            consulta = self.scan.results[0].query
            original = self.scan.results[0]
            leido = de_vuelta.latest(consulta).result_for(consulta)
            self.assertEqual(leido.counts.sites, original.counts.sites)
            self.assertEqual(leido.percentiles, original.percentiles)
            self.assertEqual(leido.patterns.heptamer, original.patterns.heptamer)

    def test_la_procedencia_del_fichero_VIAJA_al_log(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            store_mod, proyecto = self._proyecto(Path(tmp))
            store_mod.save_offtarget_run(
                proyecto,
                offtarget_store.OfftargetRun.create(
                    run_id="OT-1", date="2026-08-26", ran_by="jokin", scan=self.scan,
                ),
            )
            crudo = (Path(tmp) / "p" / store_mod.LOG_FILE).read_text(encoding="utf-8")
            self.assertIn(self.scan.provenance.table_date, crudo)
            self.assertIn(self.scan.provenance.md5, crudo)

    def test_la_nula_se_guarda_como_HISTOGRAMA_no_como_diez_mil_numeros(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            store_mod, proyecto = self._proyecto(Path(tmp))
            store_mod.save_offtarget_run(
                proyecto,
                offtarget_store.OfftargetRun.create(
                    run_id="OT-1", date="2026-08-26", ran_by="jokin", scan=self.scan,
                ),
            )
            crudo = (Path(tmp) / "p" / store_mod.LOG_FILE).read_text(encoding="utf-8")
            self.assertLess(
                len(crudo), 200_000,
                "La nula son 10.000 sorteos por clase: guardarlos uno a uno haría el "
                "log ilegible con `cat`, que es justo lo que se decidio evitar.",
            )
            de_vuelta = store_mod.load_offtarget_store(
                store_mod.ProjectStore.open(Path(tmp), "p")
            )
            consulta = self.scan.results[0].query
            nula = de_vuelta.latest(consulta).scan.nulls
            self.assertEqual(
                {c: n.draws for c, n in nula.items()},
                {c: n.draws for c, n in self.scan.nulls.items()},
            )


if __name__ == "__main__":
    unittest.main()
