"""Persistencia: un proyecto en disco, en texto, y APPEND-ONLY de verdad.

Regla 5: escritos antes. Regla 6: solo `json`, `pathlib` y `hashlib` — stdlib.

DECISION DE ARQUITECTURA (2026-08-26). El mecanismo mas simple que sobrevive a la sesion
y que los TRES modales comparten:

    data/proyectos/<slug>/proyecto.json    la entrada: md5, longitud, especie, anatomia
    data/proyectos/<slug>/registro.jsonl   el log APPEND-ONLY de todo lo demas

Por que JSONL y no SQLite —que tambien es stdlib—: este proyecto ya decidio que el
manifiesto va en TEXTO y versionado porque «un veredicto no es auditable dentro de un
año» si no se puede leer con `cat`. Un `.db` binario no se puede diffear, no se puede
grepear y no se puede leer sin la app. El registro de un veredicto tiene que sobrevivir
a la app que lo escribio.

Y el «nada se sobrescribe» deja de ser una convencion: cada linea lleva el md5 de la
ANTERIOR, asi que editar una linea vieja rompe la cadena y `verify()` lo dice. No impide
el borrado —nada lo impide— pero lo hace VISIBLE, que es lo que la disciplina de este
proyecto pide siempre.
"""

import json
import tempfile
import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.store import Project, ProjectStore


def _abrir(tmp, **cambios):
    base = dict(
        slug="raton_prnp",
        sequence="ACGT" * 30,
        species="Mus musculus",
        anatomy=None,
        anatomy_source="fixture_verificado",
        created="2026-08-26",
    )
    base.update(cambios)
    return ProjectStore.create(Path(tmp), **base)


class TestElProyecto(unittest.TestCase):

    def test_se_crea_en_disco_y_es_TEXTO(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            self.assertTrue(almacen.project_path.is_file())
            self.assertTrue(almacen.log_path.is_file())
            json.loads(almacen.project_path.read_text(encoding="utf-8"))

    def test_guarda_md5_y_longitud_de_la_entrada(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            self.assertEqual(almacen.project.sequence_length, 120)
            self.assertEqual(len(almacen.project.sequence_md5), 32)

    def test_guarda_la_especie_y_de_donde_sale_la_anatomia(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            self.assertEqual(almacen.project.species, "Mus musculus")
            self.assertEqual(almacen.project.anatomy_source, "fixture_verificado")

    def test_SIN_anatomia_el_proyecto_se_marca_NO_FIABLE(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp, anatomy=None, anatomy_source="sin_resolver")
            self.assertFalse(almacen.project.reliable)

    def test_y_dice_QUE_deja_de_ser_fiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            motivo = _abrir(tmp, anatomy_source="sin_resolver").project.why_unreliable
            for trozo in ("tercio", "proximal", "polyA"):
                self.assertIn(trozo, motivo)

    def test_con_anatomia_SI_es_fiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(
                tmp, anatomy={"utr5": [1, 10], "cds": [11, 100], "utr3": [101, 120]},
                anatomy_source="anotacion_genbank",
            )
            self.assertTrue(almacen.project.reliable)
            self.assertEqual(almacen.project.why_unreliable, "")

    def test_reabrirlo_lee_lo_mismo(self):
        with tempfile.TemporaryDirectory() as tmp:
            _abrir(tmp)
            otra = ProjectStore.open(Path(tmp), "raton_prnp")
            self.assertEqual(otra.project.sequence_md5, _abrir(tmp + "/x").project.sequence_md5)

    def test_crear_uno_que_ya_existe_ABORTA(self):
        with tempfile.TemporaryDirectory() as tmp:
            _abrir(tmp)
            with self.assertRaises(ShmirDesignError):
                _abrir(tmp)

    def test_abrir_uno_que_no_existe_ABORTA(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ShmirDesignError):
                ProjectStore.open(Path(tmp), "no_existe")


class TestElLogEsAPPEND_ONLY(unittest.TestCase):

    def test_cada_registro_lleva_su_numero_y_su_fecha(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            r = almacen.append("corrida_blast", {"run_id": "r1"}, date="2026-08-26")
            self.assertEqual(r.seq, 1)
            self.assertEqual(r.date, "2026-08-26")

    def test_los_registros_se_SUMAN(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            almacen.append("corrida_blast", {"run_id": "r1"}, date="2026-08-26")
            almacen.append("corrida_blast", {"run_id": "r2"}, date="2026-08-27")
            self.assertEqual(len(almacen.records("corrida_blast")), 2)

    def test_sobreviven_a_reabrir(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            almacen.append("seleccion", {"starts": [10, 60]}, date="2026-08-26")
            del almacen
            otra = ProjectStore.open(Path(tmp), "raton_prnp")
            self.assertEqual(len(otra.records("seleccion")), 1)
            self.assertEqual(otra.records("seleccion")[0].payload["starts"], [10, 60])

    def test_se_pueden_filtrar_por_tipo(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            almacen.append("corrida_blast", {"a": 1}, date="d")
            almacen.append("corrida_seed", {"b": 2}, date="d")
            self.assertEqual(len(almacen.records("corrida_blast")), 1)
            self.assertEqual(len(almacen.records()), 2)

    def test_un_tipo_desconocido_ABORTA(self):
        # Si cada modal se inventa su etiqueta, el log deja de poder leerse.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                _abrir(tmp).append("lo_que_sea", {}, date="d")

    def test_un_payload_que_no_es_JSON_ABORTA_al_escribir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ShmirDesignError):
                _abrir(tmp).append("seleccion", {"x": object()}, date="d")


class TestLaCADENAHaceVisibleUnaEdicion(unittest.TestCase):

    def test_un_log_intacto_VERIFICA(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            almacen.append("corrida_blast", {"run_id": "r1"}, date="d")
            almacen.append("corrida_seed", {"run_id": "s1"}, date="d")
            almacen.verify()

    def test_editar_una_linea_VIEJA_rompe_la_cadena(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            almacen.append("corrida_blast", {"run_id": "r1"}, date="d")
            almacen.append("corrida_seed", {"run_id": "s1"}, date="d")
            lineas = almacen.log_path.read_text(encoding="utf-8").splitlines()
            crudo = json.loads(lineas[0])
            crudo["payload"]["run_id"] = "OTRO"
            lineas[0] = json.dumps(crudo, ensure_ascii=False, sort_keys=True)
            almacen.log_path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
            with self.assertRaises(ShmirDesignError) as ctx:
                ProjectStore.open(Path(tmp), "raton_prnp").verify()
            self.assertIn("cadena", str(ctx.exception).lower())

    def test_borrar_una_linea_de_en_medio_tambien(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            for i in range(3):
                almacen.append("seleccion", {"i": i}, date="d")
            lineas = almacen.log_path.read_text(encoding="utf-8").splitlines()
            del lineas[1]
            almacen.log_path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
            with self.assertRaises(ShmirDesignError):
                ProjectStore.open(Path(tmp), "raton_prnp").verify()

    def test_el_mensaje_dice_QUE_linea(self):
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            almacen.append("seleccion", {"i": 0}, date="d")
            almacen.append("seleccion", {"i": 1}, date="d")
            lineas = almacen.log_path.read_text(encoding="utf-8").splitlines()
            lineas[0] = lineas[0].replace('"i": 0', '"i": 9')
            almacen.log_path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
            with self.assertRaises(ShmirDesignError) as ctx:
                ProjectStore.open(Path(tmp), "raton_prnp").verify()
            self.assertIn("1", str(ctx.exception))

    def test_lo_que_NO_hace_va_escrito(self):
        from shmir_design import store

        texto = store.WHAT_THE_CHAIN_DOES_NOT_DO
        self.assertIn("no impide", texto.lower())
        self.assertIn("visible", texto.lower())


class TestLosTresModalesGuardanEnElMISMOSitio(unittest.TestCase):

    def test_los_tipos_declarados_cubren_los_tres(self):
        from shmir_design.store import RECORD_KINDS

        for esperado in ("corrida_blast", "corrida_seed", "seleccion", "descarte"):
            self.assertIn(esperado, RECORD_KINDS)

    def test_y_no_hay_dos_almacenes(self):
        # Un solo directorio por proyecto, un solo log. Si cada modal abriera el suyo,
        # la ficha tendria que buscar en tres sitios y uno se quedaria fuera.
        with tempfile.TemporaryDirectory() as tmp:
            almacen = _abrir(tmp)
            almacen.append("corrida_blast", {"x": 1}, date="d")
            almacen.append("corrida_seed", {"x": 2}, date="d")
            almacen.append("seleccion", {"x": 3}, date="d")
            ficheros = sorted(p.name for p in almacen.root.iterdir())
            self.assertEqual(ficheros, ["proyecto.json", "registro.jsonl"])


if __name__ == "__main__":
    unittest.main()


class TestLosDosAlmacenesGuardanAHI(unittest.TestCase):
    """Que «los tres modales guardan en el mismo sitio» sea cierto, no declarado."""

    def _proyecto(self, tmp):
        return _abrir(tmp)

    def test_una_corrida_de_BLAST_se_persiste_y_se_recupera(self):
        from shmir_design import blast
        from shmir_design.blast_store import BlastDatabase, BlastRun
        from shmir_design.store import load_blast_store, save_blast_run

        consulta = blast.QueryFasta.from_records((("raton_pos10_guia", "ACGTACGTACGT"),))
        corrida = BlastRun.create(
            run_id="r1", date="2026-08-26", uploaded_by="responsable",
            params=blast.DEFAULTS,
            database=BlastDatabase("refseq_rna", "2026-08-26", "a" * 32, False),
            query=consulta,
            raw="raton_pos10_guia\tNM_1\t100.0\t12\t0\t0\t1\t12\t1\t12\t1e-5\t24.0\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            almacen = self._proyecto(tmp)
            save_blast_run(almacen, corrida)
            otra = ProjectStore.open(Path(tmp), "raton_prnp")
            recuperado = load_blast_store(otra)
            self.assertEqual(len(recuperado.runs), 1)
            self.assertEqual(recuperado.runs[0].run_id, "r1")
            self.assertEqual(recuperado.runs[0].query_md5, corrida.query_md5)

    def test_el_veredicto_sobrevive_al_reinicio(self):
        from shmir_design import blast
        from shmir_design.blast_store import BlastDatabase, BlastRun
        from shmir_design.store import load_blast_store, save_blast_run

        consulta = blast.QueryFasta.from_records((("raton_pos10_guia", "ACGTACGTACGT"),))
        corrida = BlastRun.create(
            run_id="r1", date="2026-08-26", uploaded_by="responsable",
            params=blast.DEFAULTS,
            database=BlastDatabase("refseq_rna", "2026-08-26", "a" * 32, False),
            query=consulta,
            raw="raton_pos10_guia\tNM_1\t100.0\t12\t0\t0\t1\t12\t1\t12\t1e-5\t24.0\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            save_blast_run(self._proyecto(tmp), corrida)
            recuperado = load_blast_store(ProjectStore.open(Path(tmp), "raton_prnp"))
            from shmir_design.filters import FilterState

            self.assertIsNot(
                recuperado.verdict_for("raton_pos10_guia").state, FilterState.NOT_RUN
            )

    def test_los_parametros_MODIFICADOS_sobreviven_tambien(self):
        # Si al recargar se perdieran, un veredicto no estandar pasaria por estandar.
        from shmir_design import blast
        from shmir_design.blast_store import BlastDatabase, BlastRun
        from shmir_design.store import load_blast_store, save_blast_run

        consulta = blast.QueryFasta.from_records((("raton_pos10_guia", "ACGTACGTACGT"),))
        corrida = BlastRun.create(
            run_id="r1", date="2026-08-26", uploaded_by="responsable",
            params=blast.DEFAULTS.with_changes(word_size=11),
            database=BlastDatabase("refseq_rna", "2026-08-26", "a" * 32, False),
            query=consulta,
            raw="raton_pos10_guia\tNM_1\t100.0\t12\t0\t0\t1\t12\t1\t12\t1e-5\t24.0\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            save_blast_run(self._proyecto(tmp), corrida)
            recuperado = load_blast_store(ProjectStore.open(Path(tmp), "raton_prnp"))
            self.assertEqual(recuperado.runs[0].params.modified(), ("word_size",))
            self.assertFalse(recuperado.runs[0].gives_verdict)

    def test_la_seleccion_a_mano_tambien_se_guarda(self):
        from shmir_design.store import save_selection, selected_starts

        with tempfile.TemporaryDirectory() as tmp:
            almacen = self._proyecto(tmp)
            save_selection(almacen, starts=(10, 60, 143), date="2026-08-26", by="yo")
            otra = ProjectStore.open(Path(tmp), "raton_prnp")
            self.assertEqual(selected_starts(otra), (10, 60, 143))

    def test_una_seleccion_nueva_NO_pisa_la_anterior(self):
        from shmir_design.store import save_selection, selected_starts

        with tempfile.TemporaryDirectory() as tmp:
            almacen = self._proyecto(tmp)
            save_selection(almacen, starts=(10,), date="2026-08-26", by="yo")
            save_selection(almacen, starts=(10, 60), date="2026-08-27", by="yo")
            self.assertEqual(len(almacen.records("seleccion")), 2)
            self.assertEqual(selected_starts(almacen), (10, 60))
