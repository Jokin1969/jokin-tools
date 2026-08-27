"""Que lo que la app calcula SOBREVIVA a cerrar la pestaña.

Regla 5: escritos antes.

**El hueco que esto cierra, y era el mas grande que quedaba.** La capa de persistencia
—`store.py`, JSONL append-only, la cadena de md5— estaba construida y testada, y
**`store.save_*` no se llamaba desde NINGUN sitio**. Los cuatro modales calculaban,
pintaban, y al cerrar la pestaña no quedaba nada: corrias el BLAST, subias el
`-outfmt 6`, veias el veredicto, y al dia siguiente habia que repetirlo entero.

Es el mismo patron del codigo sin caller que este proyecto ya ha tenido dos veces
(`triple_motive_rows`, `intron_folding`), un nivel mas arriba y sobre la pieza que se
decidio con mas cuidado: «un veredicto tiene que sobrevivir a la app que lo escribio».
"""

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from shmir_design import presentation, store, trabajo
from shmir_design.errors import ShmirDesignError

# Una secuencia REAL del proyecto, no inventada (regla 1): el 3'UTR murino de
# referencia si esta, y si no el test se salta de forma visible.
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)
SECUENCIA = load_3utr(RATON) if HAY else ""
MD5 = hashlib.md5(SECUENCIA.encode("ascii")).hexdigest() if HAY else ""

ENTRADA = {
    "species": "Mus musculus",
    "anatomy": {"utr3_start": 1, "utr3_end": 1242},
    "anatomy_source": "fixture_verificado",
}


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del raton")
class _ConProyectos(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _crear(self, slug="prnp-raton", **cambios):
        datos = {**ENTRADA, "sequence": SECUENCIA, **cambios}
        return presentation.project_create(
            self.tmp, slug=slug, date="2026-08-27", **datos
        )


# ─────────────── donde viven los proyectos ───────────────


class TestDondeVivenLosProyectos(unittest.TestCase):

    def test_por_defecto_van_junto_al_paquete(self):
        self.assertTrue(str(trabajo.projects_dir(env={})).endswith("proyectos"))

    def test_pero_se_pueden_DECLARAR_como_el_de_referencia(self):
        self.assertEqual(
            trabajo.projects_dir(env={trabajo.PROJECT_ENV_VAR: "/data/shmir/proyectos"}),
            Path("/data/shmir/proyectos"),
        )

    def test_una_ruta_relativa_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            trabajo.projects_dir(env={trabajo.PROJECT_ENV_VAR: "proyectos"})

    def test_y_el_motivo_es_EL_MISMO_que_el_de_los_ficheros(self):
        """En un despliegue, dentro de la imagen el log se pierde en cada redespliegue —
        y el log es justo lo que tiene que sobrevivir a la app."""
        self.assertIn("efimero", trabajo.WHY_A_WORKING_DIR.lower())


# ─────────────── crear y abrir ───────────────


class TestCrearYAbrir(_ConProyectos):

    def test_crear_deja_el_proyecto_EN_DISCO(self):
        almacen = self._crear()
        self.assertTrue((self.tmp / "prnp-raton" / store.PROJECT_FILE).is_file())
        self.assertEqual(almacen.project.sequence_md5, MD5)

    def test_y_se_puede_VOLVER_a_abrir(self):
        self._crear()
        vuelto = presentation.project_open(self.tmp, "prnp-raton")
        self.assertEqual(vuelto.project.sequence_length, 1242)

    def test_crear_dos_veces_el_mismo_slug_ABORTA(self):
        self._crear()
        with self.assertRaises(ShmirDesignError):
            self._crear()

    def test_abrir_uno_que_no_existe_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            presentation.project_open(self.tmp, "no-existe")

    def test_ABRIR_CON_OTRA_SECUENCIA_SE_RECHAZA(self):
        """Es el fallo del CSV de miRarchitect por la puerta de la persistencia: seguir
        apuntando corridas de OTRA secuencia en el log de esta."""
        self._crear()
        with self.assertRaises(ShmirDesignError) as caja:
            presentation.project_open(self.tmp, "prnp-raton", expect_md5="b" * 32)
        texto = str(caja.exception).lower()
        self.assertIn("md5", texto)
        self.assertIn("otra secuencia", texto)

    def test_y_con_el_md5_bueno_abre(self):
        self._crear()
        vuelto = presentation.project_open(self.tmp, "prnp-raton", expect_md5=MD5)
        self.assertIsNotNone(vuelto)

    def test_la_lista_sale_con_lo_que_hace_falta_para_ELEGIR(self):
        self._crear("uno")
        self._crear("dos", sequence=SECUENCIA[:800])
        filas = {f["slug"]: f for f in presentation.project_list(self.tmp)}
        self.assertEqual(set(filas), {"uno", "dos"})
        for fila in filas.values():
            for clave in ("creado", "md5", "longitud", "especie", "fiable", "corridas"):
                self.assertIn(clave, fila)

    def test_sin_ningun_proyecto_la_lista_va_VACIA_y_no_aborta(self):
        self.assertEqual(presentation.project_list(self.tmp), [])

    def test_un_proyecto_sin_anatomia_sale_marcado_NO_FIABLE(self):
        almacen = self._crear("sin-anatomia", anatomy=None, anatomy_source="sin_resolver")
        self.assertFalse(almacen.project.reliable)
        fila = next(f for f in presentation.project_list(self.tmp) if f["slug"] == "sin-anatomia")
        self.assertFalse(fila["fiable"])


# ─────────────── guardar cada modal ───────────────


class TestGuardarLasCorridas(_ConProyectos):

    def test_la_SELECCION_manual_se_guarda_y_vuelve(self):
        almacen = self._crear()
        presentation.save_selection(almacen, starts=(60, 449, 1018), date="2026-08-27",
                                    by="joaquin")
        vuelto = presentation.project_open(self.tmp, "prnp-raton")
        self.assertEqual(presentation.selected_starts(vuelto), (60, 449, 1018))

    def test_y_una_seleccion_NUEVA_no_pisa_la_vieja_la_SUCEDE(self):
        almacen = self._crear()
        presentation.save_selection(almacen, starts=(60,), date="2026-08-27", by="a")
        presentation.save_selection(almacen, starts=(60, 449), date="2026-08-27", by="a")
        vuelto = presentation.project_open(self.tmp, "prnp-raton")
        self.assertEqual(presentation.selected_starts(vuelto), (60, 449))
        # Las DOS siguen en el log: el almacen es append-only.
        self.assertEqual(len(vuelto.records("seleccion")), 2)

    def test_el_log_se_puede_leer_con_cat(self):
        almacen = self._crear()
        presentation.save_selection(almacen, starts=(60,), date="2026-08-27", by="a")
        texto = (self.tmp / "prnp-raton" / store.LOG_FILE).read_text(encoding="utf-8")
        self.assertIn("seleccion", texto)
        self.assertIn("60", texto)

    def test_la_CADENA_se_verifica(self):
        almacen = self._crear()
        presentation.save_selection(almacen, starts=(60,), date="2026-08-27", by="a")
        presentation.project_open(self.tmp, "prnp-raton").verify()   # no lanza

    def test_y_editar_una_linea_vieja_lo_DELATA(self):
        almacen = self._crear()
        for starts in ((60,), (60, 449)):
            presentation.save_selection(almacen, starts=starts, date="2026-08-27", by="a")
        ruta = self.tmp / "prnp-raton" / store.LOG_FILE
        lineas = ruta.read_text(encoding="utf-8").splitlines()
        lineas[0] = lineas[0].replace('"60"', '"61"').replace("60", "61")
        ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        with self.assertRaises(ShmirDesignError):
            presentation.project_open(self.tmp, "prnp-raton").verify()


class TestLosCuatroModalesGuardanEN_EL_MISMO_LOG(_ConProyectos):
    """Un solo directorio y un solo log. Si cada modal abriera el suyo, la ficha
    tendria que buscar en cuatro sitios."""

    def test_el_tipo_de_registro_del_cuarto_modal_EXISTE(self):
        self.assertIn("corrida_empalme", store.RECORD_KINDS)

    def test_y_RECORD_KINDS_sigue_CERRADO(self):
        almacen = self._crear()
        # `ValueError` es lo que lanza: la etiqueta desconocida es un error de
        # programacion del que la usa, no una condicion del dominio.
        with self.assertRaises((ShmirDesignError, ValueError)):
            almacen.append("lo_que_sea", {}, date="2026-08-27")

    def test_hay_un_save_y_un_load_por_modal(self):
        for nombre in ("blast", "seed", "offtarget", "splice"):
            self.assertTrue(hasattr(store, f"save_{nombre}_run"), nombre)
            self.assertTrue(hasattr(store, f"load_{nombre}_store"), nombre)

    def test_presentation_los_expone_TODOS(self):
        for nombre in ("blast", "seed", "offtarget", "splice"):
            self.assertTrue(hasattr(presentation, f"save_{nombre}_run"), nombre)

    def test_load_stores_devuelve_LOS_CUATRO(self):
        almacen = self._crear()
        almacenes = presentation.load_stores(almacen)
        self.assertEqual(
            set(almacenes), {"blast", "seed", "offtarget", "splice"}
        )


class TestLaFichaVE_EL_CUARTO_MODAL(unittest.TestCase):

    def test_build_dossier_acepta_el_almacen_del_cuarto_modal(self):
        import inspect

        from shmir_design.dossier import build_dossier

        self.assertIn("splice_store", inspect.signature(build_dossier).parameters)


class TestLaPaginaGUARDA(unittest.TestCase):

    def test_la_pagina_llama_a_crear_o_abrir_proyecto(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertTrue("project_create(" in fuente, "la pagina no crea proyectos")
        self.assertTrue("project_open(" in fuente, "la pagina no abre proyectos")

    def test_y_guarda_lo_que_calculan_los_modales(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        for nombre in ("save_blast_run", "save_seed_run", "save_offtarget_run",
                       "save_splice_run", "save_selection"):
            self.assertTrue(nombre in fuente, f"la pagina no llama a {nombre}")


if __name__ == "__main__":
    unittest.main()
