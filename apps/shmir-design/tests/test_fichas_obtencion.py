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
from tests.tabla_medida import TABLA

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
    from shmir_design.apa import resolve_measured
    from shmir_design.selection import (
        SelectionConfig,
        blocking_fronts,
        select_from_report,
    )
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(RATON)
    nombres: set[str] = set()
    for medido in (resolve_measured(utr3, TABLA), None):
        informe = tile_utr(utr3)
        seleccion = select_from_report(
            informe, SelectionConfig(n_candidates=10, apa_immune_quota=4)
        )
        nombres |= {f.name for f in blocking_fronts(informe, seleccion)}

    # Y los intrones que faltan: un intron que no tenemos es un NOT_RUN como cualquier
    # otro y tiene que decir como se resuelve. Se toman los que DECLARAN ficha, no todos:
    # `mvm_actual` esta disponible y no necesita ninguna.
    from shmir_design.introns import INTRONS

    nombres |= {i.ficha for i in INTRONS.values() if i.ficha}

    # Y TERCERA FAMILIA (2026-09-02): las fichas que declara el GESTOR. `blocking_fronts`
    # sale de los filtros de un CANDIDATO, asi que no ve un frente que se cierra con un
    # fichero y no se le pregunta a cada ventana — el plasmido del andamio es el primero.
    # Se toma de `species.required_files`, que es la unica fuente de los ficheros del
    # deposito: asi un fichero nuevo cuya ficha no exista rompe la suite, que es de lo
    # que va este test.
    from shmir_design.species import required_files, resolve

    nombres |= {
        f.ficha for f in required_files(resolve("raton")) if f.ficha
    }
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

    def test_hay_una_por_cada_uno_de_los_TRECE_de_hoy(self):
        """Once frentes —el cuarto modal añadio `empalme_sitios` y el plasmido de SGEP
        añade `contextos_del_andamio`— mas los DOS intrones que faltan del registro."""
        self.assertEqual(len(obtencion.load_all()), 13)


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
        self.assertIn("hexámero", texto.lower())

    def test_y_AVISA_de_que_las_coordenadas_son_GENOMICAS(self):
        texto = self._ficha("fraccion_isoforma_larga").render().lower()
        self.assertIn("genomica", texto)
        self.assertIn("resta", texto)


class TestLasDOSviasDeESPECIFICIDAD(unittest.TestCase):
    """La base de BLAST se consigue por DOS caminos, y elegir mal cuesta 80 GB.

    LO QUE LO OBLIGA, y es una descarga real de este proyecto: la ficha mandaba al FTP
    de BLAST del NCBI y punto, asi que la unica via escrita era la EXHAUSTIVA — decenas
    de GB de transcritos de TODOS los organismos para consultar veinte guias de una sola
    especie. La via barata existia y estaba a la vista: el mismo Table Browser del que ya
    sale `transcriptoma_3utr.fa`, con la especie del diseño y decenas de MB.

    Y las dos comparten el paso que NO ESTABA EN NINGUNA: `makeblastdb`. Un FASTA no es
    una base de BLAST, asi que sin el la orden que da la app no puede correr — y eso se
    descubre DESPUES de la descarga, que es cuando ya no tiene arreglo barato.
    """

    @classmethod
    def setUpClass(cls):
        cls.raton = species_mod.resolve("mouse")
        cls.ficha = obtencion.resolve_ficha("especificidad", species=cls.raton)
        cls.texto = cls.ficha.render()

    def _pasos_de(self, via):
        return [p for p in self.ficha.steps if via in p]

    # ── las dos vias existen, y una esta RECOMENDADA ──────────────────────────────

    def test_hay_DOS_vias_declaradas_y_las_dos_tienen_pasos(self):
        self.assertTrue(self._pasos_de("VÍA A"), "no hay pasos de la via de UCSC")
        self.assertTrue(self._pasos_de("VÍA B"), "no hay pasos de la via de NCBI")

    def test_la_RECOMENDADA_es_la_de_UCSC_y_es_la_URL_de_la_ficha(self):
        self.assertIn("RECOMENDADA", " ".join(self._pasos_de("VÍA A")))
        # La URL de cabecera es la que se sigue por defecto: si apuntara al FTP, la via
        # cara volveria a ser la primera que se lee.
        self.assertIn("genome.ucsc.edu", self.ficha.url)

    def test_y_la_de_NCBI_sigue_ESCRITA_con_su_URL(self):
        # No se borra: es la exhaustiva, y la unica que trae los PREDICHOS.
        self.assertIn("ftp.ncbi.nlm.nih.gov/blast/db", self.texto)

    def test_las_DOS_dicen_lo_que_PESAN_porque_es_lo_que_decide(self):
        self.assertIn("MB", self.texto)
        self.assertIn("GB", self.texto)
        self.assertIn("80 GB", self.texto)

    # ── lo que cada via NO da ─────────────────────────────────────────────────────

    def test_UCSC_avisa_de_que_CURATED_no_trae_los_PREDICHOS(self):
        via = " ".join(self._pasos_de("VÍA A")) + " " + " ".join(self.ficha.warnings)
        self.assertIn("Curated", via)
        self.assertIn("XM_", via)
        self.assertIn("XR_", via)

    def test_y_dice_la_CONSECUENCIA_no_solo_el_hecho(self):
        """Cero predichos en el resultado no es «no hay off-targets contra predichos».

        Es el «Alu 0 %» otra vez: un cero obtenido sin buscar. Decir que Curated no los
        trae y no decir como se lee el resultado deja el numero listo para leerse mal.
        """
        avisos = " ".join(self.ficha.warnings)
        self.assertIn("no es", avisos.lower())
        self.assertIn("predich", avisos.lower())

    def test_NCBI_avisa_de_que_hay_que_FILTRAR_y_por_que(self):
        via = " ".join(self._pasos_de("VÍA B")) + " " + " ".join(self.ficha.warnings)
        self.assertIn("-entrez_query", via)
        self.assertIn("local", via.lower())

    # ── el paso que faltaba, y esta en LAS DOS ────────────────────────────────────

    def test_makeblastdb_esta_en_LAS_DOS_vias(self):
        for via in ("VÍA A", "VÍA B"):
            with self.subTest(via=via):
                self.assertTrue(
                    any("makeblastdb" in p for p in self._pasos_de(via)),
                    f"{via} no construye la base: un FASTA no es una base de BLAST y la "
                    f"orden de la app no puede correr contra el.",
                )

    def test_y_va_en_los_PASOS_no_solo_en_un_AVISO(self):
        """Un aviso se lee en diagonal; un paso se ejecuta.

        Control adversario de la comprobacion de arriba: si `makeblastdb` viviera solo
        en los avisos, aquel test pasaria igual buscando en el render entero.
        """
        self.assertIn("makeblastdb", " ".join(self.ficha.steps))

    def test_dice_con_esas_palabras_que_un_FASTA_no_es_una_BASE(self):
        self.assertIn("no es una base de BLAST", self.texto)

    def test_las_dos_vias_acaban_en_el_MISMO_artefacto_declarable(self):
        """Las dos producen un FASTA, y por eso el md5 del manifiesto significa algo.

        La base preformateada del NCBI no da ningun FASTA que registrar, asi que por esa
        via sin el paso de filtrado no habria nada que apuntar en el manifiesto — y la
        procedencia del veredicto se quedaria sin su unica ancla.
        """
        fichero = next(f for f in self.ficha.files if f.name.endswith(".fa"))
        self.assertEqual(fichero.name, "refseq_rna.fa")
        for via in ("VÍA A", "VÍA B"):
            with self.subTest(via=via):
                self.assertTrue(
                    any("refseq_rna.fa" in p for p in self._pasos_de(via)),
                    f"{via} no dice que lo que se guarda y se declara es ese FASTA.",
                )

    def test_el_comando_de_FILTRADO_se_puede_PEGAR_sin_editarlo(self):
        """`-taxids` quiere el numero pelado, y `{taxid}` trae el prefijo `txid`.

        Es la leccion de la errata nº 40 un piso mas abajo: un comando que la ficha da
        para copiar y que hay que editar antes de pegarlo no es un comando, es un
        ejercicio — y el que lo edite mal se entera al final. Por eso el numero se
        DERIVA del taxid declarado (`{taxid_numero}`) en vez de pedirle al lector que lo
        recorte.
        """
        paso = next(p for p in self.ficha.steps if "-taxids" in p)
        self.assertIn("-taxids 10090", paso)
        self.assertNotIn("-taxids txid", paso)
        self.assertNotIn("<", paso)

    def test_y_avisa_de_que_el_NOMBRE_de_la_base_viaja_con_el_resultado(self):
        # La base construida no se llama `refseq_rna` de serie, asi que `-db` cambia —
        # y un ajuste cambiado se marca y viaja. Aqui eso es CORRECTO, no un descuido.
        self.assertIn("-db", self.texto)


class TestElNUMERO_del_TAXID_es_UN_MARCADOR_MAS(unittest.TestCase):
    """Se DERIVA del taxid declarado; no es una segunda fuente del mismo dato."""

    def test_con_raton_sale_el_numero_pelado(self):
        raton = species_mod.resolve("mouse")
        self.assertEqual(raton.taxid, "txid10090")
        valores = obtencion._values(raton)
        self.assertEqual(valores["taxid_numero"], "10090")

    def test_con_una_especie_SIN_taxid_dice_que_NO_esta_declarado(self):
        conejo = species_mod.resolve("conejo")
        valores = obtencion._values(conejo)
        self.assertEqual(valores["taxid_numero"], "")
        # Y el hueco se explica con el MISMO texto que el del taxid: dos redacciones del
        # mismo agujero acaban discrepando, y una diria donde se declara y la otra no.
        self.assertEqual(
            obtencion.undeclared_note("taxid_numero", cientifico=conejo.scientific),
            obtencion.undeclared_note("taxid", cientifico=conejo.scientific),
        )


class TestUnHUECO_se_avisa_UNA_vez(unittest.TestCase):
    """Dos marcadores del mismo dato son un solo agujero, y un solo aviso.

    `{taxid}` y `{taxid_numero}` salen del mismo campo declarado, asi que una especie sin
    taxid abria DOS huecos con el mismo texto y el panel lo pintaba dos veces. Dos avisos
    identicos se leen como dos problemas, y el segundo no dice nada que no dijera el
    primero: es ruido en la unica pantalla que existe para decir que falta.
    """

    def test_el_taxid_sin_declarar_avisa_UNA_sola_vez(self):
        conejo = species_mod.resolve("conejo")
        ficha = obtencion.resolve_ficha("especificidad", species=conejo)
        nota = obtencion.undeclared_note("taxid", cientifico=conejo.scientific)
        self.assertEqual(list(ficha.warnings).count(nota), 1)

    def test_y_los_dos_huecos_SIGUEN_declarados(self):
        # Deduplicar el AVISO no es tapar el hueco: los dos siguen en `undeclared`, que
        # es lo que dice que marcadores se quedaron sin resolver.
        ficha = obtencion.resolve_ficha(
            "especificidad", species=species_mod.resolve("conejo")
        )
        self.assertIn("taxid", ficha.undeclared)
        self.assertIn("taxid_numero", ficha.undeclared)


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
        self.assertIn("no está declarado", texto.lower())
        self.assertNotIn("mmu-", texto)

    def test_y_ese_hueco_sale_como_AVISO_no_enterrado_en_un_paso(self):
        ficha = obtencion.resolve_ficha("seed_colision", species=self.conejo)
        self.assertTrue(ficha.undeclared)
        self.assertTrue(any("miRBase" in a for a in ficha.warnings))

    def test_el_ensamblaje_de_UCSC_tambien_se_DECLARA_no_se_adivina(self):
        raton = obtencion.resolve_ficha("offtarget_seed", species=self.raton)
        conejo = obtencion.resolve_ficha("offtarget_seed", species=self.conejo)
        self.assertIn("mm39", raton.render())
        self.assertIn("no está declarado", conejo.render().lower())
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
