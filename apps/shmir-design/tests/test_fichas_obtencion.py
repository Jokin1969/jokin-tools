"""Cada `NOT_RUN` tiene que decir COMO SE RESUELVE.

Regla 5: escritos antes.

Hoy la app dice que fichero falta. No dice de donde sale, y por eso el usuario lo
pregunta FUERA de la app. Esa es la dependencia que estas fichas rompen: quien no haya
estado en estas conversaciones tiene que poder conseguir el fichero y subirlo.

Dos cosas que estos tests fijan y que son las que hacen que esto no se pudra:

  - **todo frente tiene ficha**: un frente nuevo sin ficha hace fallar la suite;
  - **y toda ficha corresponde a un frente**: una ficha huerfana es documentacion de algo
    que ya no existe, y eso engaña igual.
"""

import unittest
from pathlib import Path

from shmir_design import obtencion, species as species_mod
from shmir_design.errors import ShmirDesignError
from shmir_design.reference import REFERENCES, fixture_available, load_3utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)
DIRECTORIO = Path(__file__).resolve().parent.parent / "data" / "obtencion"


def _frentes_de_verdad() -> set[str]:
    """Lo que una ficha de obtencion puede documentar. Son DOS familias, no una.

    La primera son los FRENTES que emite el nucleo, en dos configuraciones distintas —dos
    y no una: `fraccion_isoforma_larga` solo aparece con tabla de APA medido, asi que con
    una sola corrida la lista saldria corta y un frente podria colarse sin ficha—.

    La segunda son los INTRONES que faltan del registro (`introns.INTRONS`). Se añadieron
    con el cuarto modal, cuya unidad de analisis es el par candidato x intron: un intron
    que no tenemos es un `NOT_RUN` como cualquier otro, y tiene que decir como se resuelve
    igual que un fichero de referencia. Meterlos aqui es lo que hace que un intron nuevo
    sin ficha rompa la suite, que es de lo que va este test.
    """
    from shmir_design.apa import POLYA_DB_PRNP, resolve_measured
    from shmir_design.selection import (
        SelectionConfig,
        blocking_fronts,
        select_from_report,
    )
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(RATON)
    nombres: set[str] = set()
    for medido in (resolve_measured(utr3, POLYA_DB_PRNP), None):
        informe = tile_utr(utr3, measured_apa=medido)
        seleccion = select_from_report(
            informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
        )
        nombres |= {f.name for f in blocking_fronts(informe, seleccion)}

    # Y los intrones que faltan: un intron que no tenemos es un NOT_RUN como cualquier
    # otro y tiene que decir como se resuelve. Se toman los que DECLARAN ficha, no todos:
    # `mvm_actual` esta disponible y no necesita ninguna.
    from shmir_design.introns import INTRONS

    nombres |= {i.ficha for i in INTRONS.values() if i.ficha}
    return nombres


class TestLasFichasSonDATOS(unittest.TestCase):
    """Un fichero versionado por ficha, no texto en el codigo."""

    def test_viven_en_data_obtencion_y_son_ficheros(self):
        self.assertTrue(DIRECTORIO.is_dir())
        self.assertTrue(list(DIRECTORIO.glob("*.toml")))

    def test_el_directorio_NO_esta_ignorado_por_git(self):
        """Los ficheros de datos grandes no van a git; estos SI: son documentacion."""
        import subprocess

        salida = subprocess.run(
            ["git", "check-ignore", "-q", str(next(DIRECTORIO.glob("*.toml")))],
            capture_output=True,
        )
        self.assertNotEqual(
            salida.returncode, 0, "Las fichas de obtencion tienen que versionarse."
        )

    def test_se_cargan_todas_sin_excepcion(self):
        fichas = obtencion.load_all()
        self.assertEqual(len(fichas), len(list(DIRECTORIO.glob("*.toml"))))

    def test_una_ficha_sin_pregunta_ABORTA_al_cargarla(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "x.toml"
            ruta.write_text('frente = "x"\n', encoding="utf-8")
            with self.assertRaises(ShmirDesignError):
                obtencion.load_ficha(ruta)

    def test_el_nombre_del_fichero_y_el_frente_tienen_que_CUADRAR(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "otro_nombre.toml"
            ruta.write_text(
                'frente = "especificidad"\npregunta = "?"\nfuente = "x"\nurl = "y"\n'
                'tamano = "z"\nvalidacion = "v"\npasos = ["uno"]\n',
                encoding="utf-8",
            )
            with self.assertRaises(ShmirDesignError):
                obtencion.load_ficha(ruta)


@unittest.skipUnless(HAY, "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestTodoFrenteTieneFicha(unittest.TestCase):

    def test_ningun_frente_se_queda_sin_ficha(self):
        faltan = sorted(_frentes_de_verdad() - set(obtencion.load_all()))
        self.assertEqual(
            faltan, [],
            f"Frente(s) sin ficha de obtencion: {faltan}. Un NOT_RUN que no dice como "
            f"resolverse manda al usuario a preguntar FUERA de la app, que es justo la "
            f"dependencia que esto viene a romper. Añade "
            f"data/obtencion/<frente>.toml.",
        )

    def test_y_ninguna_ficha_es_HUERFANA(self):
        sobran = sorted(set(obtencion.load_all()) - _frentes_de_verdad())
        self.assertEqual(
            sobran, [],
            f"Ficha(s) de un frente que ya no existe: {sobran}. Documentacion de algo "
            f"que no esta engaña igual que la ausencia.",
        )

    def test_hay_una_por_cada_uno_de_los_DOCE_de_hoy(self):
        """Diez frentes —el cuarto modal añadio `empalme_sitios`— mas los DOS intrones
        que faltan del registro."""
        self.assertEqual(len(obtencion.load_all()), 12)


class TestElContenidoDeCadaFicha(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fichas = obtencion.load_all()

    def test_todas_dicen_QUE_PREGUNTA_responde_el_frente(self):
        for nombre, ficha in self.fichas.items():
            self.assertTrue(ficha.question.strip(), nombre)
            self.assertGreater(len(ficha.question), 30, nombre)

    def test_todas_traen_fuente_y_URL(self):
        for nombre, ficha in self.fichas.items():
            self.assertTrue(ficha.source.strip(), nombre)
            self.assertTrue(
                ficha.url.startswith("http") or ficha.url == obtencion.NO_URL,
                f"{nombre}: {ficha.url!r}",
            )

    def test_todas_traen_PASOS_concretos(self):
        for nombre, ficha in self.fichas.items():
            self.assertTrue(ficha.steps, nombre)

    def test_todas_dicen_como_se_VALIDA_al_subirlo(self):
        for nombre, ficha in self.fichas.items():
            self.assertTrue(ficha.validation.strip(), nombre)

    def test_todas_traen_tamaño_aproximado(self):
        for nombre, ficha in self.fichas.items():
            self.assertTrue(ficha.size.strip(), nombre)

    def test_la_que_no_se_cierra_con_ningun_fichero_lo_DICE(self):
        empalme = self.fichas["empalme_intron"]
        self.assertTrue(empalme.no_file)
        self.assertTrue(empalme.why_no_file.strip())
        self.assertEqual(empalme.files, ())

    def test_las_demas_nombran_el_fichero_EXACTO(self):
        for nombre, ficha in self.fichas.items():
            if ficha.no_file:
                continue
            self.assertTrue(ficha.files, nombre)
            for fichero in ficha.files:
                self.assertTrue(fichero.name.strip(), nombre)
                self.assertTrue(fichero.why.strip(), nombre)

    def test_las_que_piden_metadatos_dicen_POR_QUE(self):
        for nombre, ficha in self.fichas.items():
            for metadato in ficha.metadata:
                self.assertTrue(metadato.why.strip(), f"{nombre}/{metadato.name}")


class TestElContenidoQueYaEstaResuelto(unittest.TestCase):
    """Lo que el responsable del proyecto ya ha hecho a mano, escrito una vez."""

    @classmethod
    def setUpClass(cls):
        cls.raton = species_mod.resolve("mouse")
        cls.fichas = obtencion.load_all()

    def _ficha(self, nombre):
        return obtencion.resolve_ficha(nombre, species=self.raton)

    def test_repetitivos_manda_a_repeatmasker_con_sus_opciones(self):
        ficha = self._ficha("repeticiones")
        texto = ficha.render()
        self.assertIn("repeatmasker.org", texto)
        self.assertIn("RepeatMasking", texto)
        self.assertIn("DNA source", texto)
        self.assertIn("tar file", texto)
        self.assertIn("email", texto)

    def test_y_el_tbl_es_OBLIGATORIO_con_su_motivo(self):
        ficha = self._ficha("repeticiones")
        tbl = next(f for f in ficha.files if f.name.endswith(".tbl"))
        self.assertTrue(tbl.required)
        self.assertIn("especie", tbl.why.lower())
        self.assertIn("indistinguible", ficha.render().lower())

    def test_y_pide_anotar_version_de_RepeatMasker_y_biblioteca_Dfam(self):
        nombres = " ".join(m.name for m in self._ficha("repeticiones").metadata)
        self.assertIn("RepeatMasker", nombres)
        self.assertIn("Dfam", nombres)

    def test_colision_de_seed_manda_a_mirbase_y_pide_el_RELEASE(self):
        ficha = self._ficha("seed_colision")
        texto = ficha.render()
        self.assertIn("mirbase.org", texto)
        self.assertIn("mature.fa", texto)
        self.assertIn("release", texto.lower())
        self.assertIn("renumera", texto.lower())

    def test_carga_de_offtargets_manda_al_Table_Browser_con_sus_opciones(self):
        texto = self._ficha("offtarget_seed").render()
        self.assertIn("Table Browser", texto)
        self.assertIn("NCBI RefSeq", texto)
        self.assertIn("sequence", texto)
        self.assertIn("3' UTR Exons", texto)

    def test_y_dice_que_las_isoformas_NO_se_filtran_a_mano(self):
        texto = self._ficha("offtarget_seed").render().lower()
        self.assertIn("a mano", texto)
        self.assertIn("la app", texto)

    def test_especificidad_dice_que_la_app_da_el_comando_y_el_usuario_lo_corre(self):
        texto = self._ficha("especificidad").render().lower()
        self.assertIn("outfmt 6", texto)
        self.assertIn("la app", texto)

    def test_el_techo_de_APA_manda_a_PolyA_DB_v4_con_su_URL(self):
        texto = self._ficha("fraccion_isoforma_larga").render()
        self.assertIn("exon.apps.wistar.org/polya_db/v4", texto)
        self.assertIn("PAS Summary", texto)
        self.assertIn("PAS Expression", texto)

    def test_y_pide_las_CUATRO_columnas_por_su_nombre(self):
        texto = self._ficha("fraccion_isoforma_larga").render()
        for columna in ("PSE_3'READS", "AvgRPM_3READS"):
            self.assertIn(columna, texto)
        self.assertIn("hexamero", texto.lower())

    def test_y_AVISA_de_que_las_coordenadas_son_GENOMICAS(self):
        texto = self._ficha("fraccion_isoforma_larga").render().lower()
        self.assertIn("genomica", texto)
        self.assertIn("resta", texto)


class TestLaFichaSeADAPTA_A_LA_ESPECIE(unittest.TestCase):
    """No vale decir «miRBase» cuando el usuario ha cargado conejo."""

    def setUp(self):
        self.conejo = species_mod.resolve("Oryctolagus cuniculus")
        self.raton = species_mod.resolve("mouse")

    def test_el_nombre_del_fichero_de_rmsk_lleva_la_especie(self):
        raton = obtencion.resolve_ficha("repeticiones", species=self.raton)
        conejo = obtencion.resolve_ficha("repeticiones", species=self.conejo)
        self.assertIn("rmsk_mouse.out", [f.name for f in raton.files])
        self.assertIn(
            "rmsk_oryctolagus_cuniculus.out", [f.name for f in conejo.files]
        )

    def test_los_pasos_nombran_la_especie_CIENTIFICA_en_DNA_source(self):
        texto = obtencion.resolve_ficha("repeticiones", species=self.conejo).render()
        self.assertIn("Oryctolagus cuniculus", texto)

    def test_con_raton_el_prefijo_de_miRBase_sale_TAL_CUAL(self):
        texto = obtencion.resolve_ficha("seed_colision", species=self.raton).render()
        self.assertIn("mmu-", texto)

    def test_con_conejo_dice_que_el_prefijo_NO_ESTA_DECLARADO(self):
        ficha = obtencion.resolve_ficha("seed_colision", species=self.conejo)
        texto = ficha.render()
        self.assertIn("no esta declarado", texto.lower())
        self.assertNotIn("mmu-", texto)

    def test_y_ese_hueco_sale_como_AVISO_no_enterrado_en_un_paso(self):
        ficha = obtencion.resolve_ficha("seed_colision", species=self.conejo)
        self.assertTrue(ficha.undeclared)
        self.assertTrue(any("miRBase" in a for a in ficha.warnings))

    def test_el_ensamblaje_de_UCSC_tambien_se_DECLARA_no_se_adivina(self):
        raton = obtencion.resolve_ficha("offtarget_seed", species=self.raton)
        conejo = obtencion.resolve_ficha("offtarget_seed", species=self.conejo)
        self.assertIn("mm39", raton.render())
        self.assertIn("no esta declarado", conejo.render().lower())
        self.assertTrue(conejo.undeclared)

    def test_una_ficha_sin_resolver_NO_se_puede_renderizar(self):
        """Con marcadores dentro, el texto mentiria a medias. Se aborta."""
        cruda = obtencion.load_all()["repeticiones"]
        with self.assertRaises(ShmirDesignError):
            cruda.render()

    def test_un_frente_que_no_existe_ABORTA_nombrando_los_que_hay(self):
        with self.assertRaises(ShmirDesignError) as caja:
            obtencion.resolve_ficha("inventado", species=self.raton)
        self.assertIn("repeticiones", str(caja.exception))


class TestLaFichaEnLaInterfaz(unittest.TestCase):

    def test_presentation_da_las_filas_ya_resueltas(self):
        from shmir_design import presentation

        filas = presentation.obtencion_rows("repeticiones", species="mouse")
        self.assertTrue(filas["pasos"])
        self.assertTrue(filas["ficheros"])
        self.assertIn("repeatmasker.org", filas["url"])

    def test_y_para_un_frente_cerrado_no_hace_falta_ficha_pero_existe(self):
        from shmir_design import presentation

        filas = presentation.obtencion_rows("fraccion_isoforma_larga", species="mouse")
        self.assertTrue(filas["pregunta"])

    def test_la_pagina_enseña_la_ficha_de_cada_NOT_RUN(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("obtencion_rows", fuente)


if __name__ == "__main__":
    unittest.main()
