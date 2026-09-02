"""Los cuatro arreglos que devuelven la autosuficiencia a la interfaz.

Regla 5: escritos antes. Regla 6: la pagina pinta, `presentation.py` decide.

El criterio de aceptacion, el de siempre: **alguien que no haya estado en estas
conversaciones tiene que poder abrir la app y llegar a un informe sin abrir una terminal
ni conocer el arbol de directorios**. Lo que rompia eso eran cuatro cosas, y las cuatro
se arreglan aqui:

  1. una caja de texto libre para la especie, con `modelo` de valor inicial — que parece
     configurado y deja dos modales rotos sin decir por que;
  2. unos ficheros se suben por la interfaz y otros hay que DEPOSITAR en
     `data/reference/`, que es un directorio del repositorio;
  3. una casilla «Usar los de `data/reference/`» cuyo unico efecto posible al
     desmarcarla es dejarlo todo en NOT_RUN sin decir por que;
  4. una primera pantalla que no dice en que orden se tocan las cosas.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from shmir_design import deposito, manifest, presentation, species
from shmir_design.errors import ShmirDesignError
from tests.sin_logica import comprobar_sin_logica

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "reference"
PAGINA = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")

CONEJO = "Oryctolagus cuniculus"


# ─────────────────────────── 1. el desplegable de especies ───────────────────────────


class TestElDesplegableDeEspecies(unittest.TestCase):

    def test_las_opciones_salen_de_species_SPECIES_y_de_ningun_otro_sitio(self):
        opciones = presentation.species_options()
        declaradas = {e.scientific for e in species.SPECIES.values()}
        nombradas = {o["cientifico"] for o in opciones if o["declarada"]}
        self.assertEqual(nombradas, declaradas)

    def test_cada_una_lleva_su_NOMBRE_COMPLETO(self):
        for opcion in presentation.species_options():
            if opcion["declarada"]:
                self.assertIn(" ", opcion["cientifico"], opcion)
                self.assertTrue(opcion["etiqueta"].startswith(opcion["cientifico"]))

    def test_NO_hay_valor_por_defecto_hay_que_elegir(self):
        """`modelo` como valor inicial es PEOR que vacio: parece configurado."""
        self.assertIsNone(presentation.species_default())

    def test_y_la_pagina_no_preselecciona_ninguna(self):
        self.assertTrue("species_default()" in PAGINA, "la pagina no pide el defecto")
        self.assertFalse(
            '"Nombre de la especie modelo", "modelo"' in PAGINA,
            "la pagina sigue preseleccionando «modelo»",
        )

    def test_hay_una_opcion_EXPLICITA_de_otra_especie(self):
        opciones = presentation.species_options()
        otras = [o for o in opciones if not o["declarada"]]
        self.assertEqual(len(otras), 1)
        self.assertIn("no declarada", otras[0]["etiqueta"])

    def test_la_caja_de_texto_libre_solo_aparece_al_elegir_esa_opcion(self):
        self.assertTrue(presentation.species_needs_name(presentation.OTHER_SPECIES))
        self.assertFalse(presentation.species_needs_name("Mus musculus"))

    def test_elegir_otra_especie_DICE_que_frentes_quedan_cerrados(self):
        nota = presentation.species_choice_note(presentation.OTHER_SPECIES)
        self.assertTrue(nota["bloquea"])
        cerrados = " ".join(nota["cerrados"]).lower()
        self.assertIn("seed", cerrados)
        self.assertIn("especificidad", cerrados)

    def test_y_DICE_COMO_declararla_nombrando_donde(self):
        nota = presentation.species_choice_note(presentation.OTHER_SPECIES)
        self.assertIn("species.SPECIES", nota["como_declararla"])
        for pieza in ("mirbase_prefix", "taxid", "ucsc_assembly"):
            self.assertIn(pieza, nota["como_declararla"])

    def test_una_especie_declarada_no_bloquea_nada(self):
        nota = presentation.species_choice_note("Mus musculus")
        self.assertFalse(nota["bloquea"])
        self.assertEqual(nota["cerrados"], [])

    def test_una_especie_tecleada_pero_no_declarada_bloquea_IGUAL(self):
        """Elegir «otra especie» y escribir «conejo» no la declara."""
        nota = presentation.species_choice_note(CONEJO)
        self.assertTrue(nota["bloquea"])
        self.assertTrue(nota["cerrados"])

    def test_sin_especie_elegida_no_se_puede_seguir(self):
        with self.assertRaises(ShmirDesignError):
            presentation.species_choice_note("")


# ─────────────────── 2. la vista POR FICHERO, con UN solo contador ───────────────────


class TestLosFicherosQueNecesitaCadaEspecie(unittest.TestCase):

    def test_hay_una_fila_por_FICHERO_no_por_frente(self):
        filas = species.required_files(species.resolve("Mus musculus"))
        nombres = [f.filename for f in filas]
        self.assertEqual(len(nombres), len(set(nombres)), "un fichero, una fila")

    def test_cada_fichero_dice_QUE_FRENTES_desbloquea(self):
        filas = {f.role: f for f in species.required_files(species.resolve("raton"))}
        self.assertIn("repeticiones", filas["rmsk"].fronts)
        self.assertIn("repeticion_polimorfica", filas["rmsk"].fronts)
        self.assertTrue(all(f.fronts for f in filas.values()))

    def test_el_nombre_LLEVA_LA_ESPECIE_donde_toca(self):
        conejo = {f.role: f for f in species.required_files(species.resolve(CONEJO))}
        self.assertEqual(conejo["rmsk"].filename, "rmsk_oryctolagus_cuniculus.out")
        self.assertEqual(conejo["rmsk"].companion, "rmsk_oryctolagus_cuniculus.tbl")

    def test_y_el_raton_conserva_los_nombres_que_YA_ESTAN_en_el_manifiesto(self):
        raton = {f.role: f for f in species.required_files(species.resolve("raton"))}
        self.assertEqual(raton["rmsk"].filename, "rmsk_mouse.out")
        self.assertEqual(raton["mirbase"].filename, "mature.fa")
        self.assertEqual(raton["transgen"].filename, "aav_casete.fa")

    def test_los_roles_son_EXACTAMENTE_los_del_manifiesto(self):
        roles = {f.role for f in species.required_files(species.resolve("raton"))}
        self.assertEqual(roles, {r.role for r in manifest.ROLES})

    def test_cada_fichero_trae_la_FICHA_que_dice_como_conseguirlo(self):
        from shmir_design import obtencion

        fichas = set(obtencion.load_all())
        for fila in species.required_files(species.resolve("raton")):
            self.assertIn(fila.ficha, fichas, fila.filename)

    def test_UN_SOLO_CONTADOR_fixture_report_se_DERIVA_de_required_files(self):
        """Dos contadores del mismo suceso que discrepen es un fallo silencioso."""
        especie = species.resolve(CONEJO)
        de_ficheros = {
            frente
            for fila in species.required_files(especie)
            for frente in fila.fronts
        }
        informe = species.fixture_report(especie, have=())
        for fila in informe.rows:
            if fila.available or not fila.missing:
                continue
            self.assertTrue(
                fila.files, f"{fila.front}: no dice de que ficheros depende"
            )
            for nombre in fila.files:
                self.assertIn(
                    nombre,
                    [f.filename for f in species.required_files(especie)]
                    + [f.companion for f in species.required_files(especie)],
                    fila.front,
                )
        self.assertTrue(de_ficheros)


class TestElPanelDeFicherosDeReferencia(unittest.TestCase):

    def test_dice_cuales_ESTAN_y_cuales_NO(self):
        filas = presentation.reference_panel_rows("raton", directory=DATOS)
        por_nombre = {f["nombre"]: f for f in filas}
        self.assertTrue(por_nombre["mature.fa"]["presente"])
        self.assertFalse(por_nombre["refseq_rna.fa"]["presente"])

    def test_los_que_YA_ESTAN_en_data_reference_se_detectan_SOLOS(self):
        """Depositarlos ahi deja de ser necesario, pero sigue funcionando."""
        filas = presentation.reference_panel_rows("raton", directory=DATOS)
        detectados = [f["nombre"] for f in filas if f["presente"]]
        self.assertIn("rmsk_mouse.out", detectados)

    def test_un_fichero_de_OTRA_especie_no_cuenta_como_presente(self):
        filas = presentation.reference_panel_rows(CONEJO, directory=DATOS)
        self.assertFalse(any(f["presente"] for f in filas if f["role"] == "rmsk"))

    def test_cada_fila_trae_el_boton_de_subida_con_las_extensiones(self):
        for fila in presentation.reference_panel_rows("raton", directory=DATOS):
            self.assertTrue(fila["extensiones"], fila["nombre"])

    def test_y_trae_la_ficha_de_obtencion_PARA_ESA_ESPECIE(self):
        filas = presentation.reference_panel_rows(CONEJO, directory=DATOS)
        rmsk = next(f for f in filas if f["role"] == "rmsk")
        self.assertIn("oryctolagus_cuniculus", rmsk["ficha"]["texto"])

    def test_el_hermano_obligatorio_sale_como_fila_PROPIA(self):
        nombres = [
            f["nombre"] for f in presentation.reference_panel_rows("raton", directory=DATOS)
        ]
        self.assertIn("rmsk_mouse.out", nombres)
        self.assertIn("rmsk_mouse.tbl", nombres)

    def test_el_resumen_cuenta_frentes_no_ficheros(self):
        resumen = presentation.reference_panel_summary("raton", directory=DATOS)
        self.assertIn("cerrables", resumen)
        self.assertIn("total", resumen)
        self.assertLessEqual(resumen["cerrables"], resumen["total"])

    def test_y_el_recuento_esta_ANTES_de_ejecutar_nada(self):
        """No hace falta ni haber subido la secuencia para saberlo."""
        resumen = presentation.reference_panel_summary(CONEJO, directory=DATOS)
        # DOS: el barrido biofisico y los contextos del andamio. El segundo NO es
        # de esta especie ni de ninguna —SGEP es el vector del ANDAMIO—, asi
        # que un conejo lo tiene cerrado desde el primer dia. Es el unico
        # fichero del deposito del que eso es cierto.
        self.assertEqual(resumen["cerrables"], 2)


# ────────────────────── 3. la subida: validacion, md5 y manifiesto ──────────────────────


class _ConDirectorio(unittest.TestCase):
    """Cada test trabaja sobre una COPIA del directorio real: no se toca el del repo."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = self.tmp / "reference"
        self.dir.mkdir()
        (self.dir / manifest.MANIFEST_NAME).write_text(
            (DATOS / manifest.MANIFEST_NAME).read_text(encoding="utf-8"),
            encoding="utf-8",
        )


class TestLaSubidaPorLaInterfaz(_ConDirectorio):

    def test_un_fichero_valido_se_ESCRIBE_y_queda_presente(self):
        crudo = (DATOS / "aav_casete.fa").read_bytes()
        resultado = deposito.accept_upload(
            self.dir, filename="aav_casete.fa", payload=crudo,
            species=species.resolve("raton"), origin="subido por la interfaz",
            date="2026-08-26",
        )
        self.assertTrue((self.dir / "aav_casete.fa").is_file())
        self.assertEqual(resultado.role, "transgen")

    def test_y_su_md5_se_CALCULA_del_fichero_no_se_declara(self):
        import hashlib

        crudo = (DATOS / "aav_casete.fa").read_bytes()
        resultado = deposito.accept_upload(
            self.dir, filename="aav_casete.fa", payload=crudo,
            species=species.resolve("raton"), origin="subido", date="2026-08-26",
        )
        self.assertEqual(
            resultado.md5, hashlib.md5(crudo, usedforsecurity=False).hexdigest()
        )

    def test_y_QUEDA_REGISTRADO_en_el_manifiesto(self):
        crudo = (DATOS / "aav_casete.fa").read_bytes()
        resultado = deposito.accept_upload(
            self.dir, filename="aav_casete.fa", payload=crudo,
            species=species.resolve("raton"), origin="subido", date="2026-08-26",
        )
        vuelto = manifest.load_manifest(self.dir / manifest.MANIFEST_NAME)
        entrada = vuelto.entry("aav_casete.fa")
        self.assertEqual(entrada.md5, resultado.md5)
        self.assertEqual(entrada.size, len(crudo))

    def test_el_registro_dice_que_se_subio_POR_LA_INTERFAZ(self):
        crudo = (DATOS / "aav_casete.fa").read_bytes()
        deposito.accept_upload(
            self.dir, filename="aav_casete.fa", payload=crudo,
            species=species.resolve("raton"), origin="subido por la interfaz",
            date="2026-08-26",
        )
        entrada = manifest.load_manifest(
            self.dir / manifest.MANIFEST_NAME
        ).entry("aav_casete.fa")
        self.assertIn("interfaz", entrada.origin)

    def test_un_fichero_que_NO_ES_lo_que_dice_ser_se_RECHAZA_y_NO_se_escribe(self):
        with self.assertRaises(ShmirDesignError):
            deposito.accept_upload(
                self.dir, filename="aav_casete.fa", payload=b"no soy un fasta\n",
                species=species.resolve("raton"), origin="subido", date="2026-08-26",
            )
        self.assertFalse((self.dir / "aav_casete.fa").is_file())

    def test_y_el_manifiesto_NO_se_toca_si_la_validacion_falla(self):
        antes = (self.dir / manifest.MANIFEST_NAME).read_text(encoding="utf-8")
        with self.assertRaises(ShmirDesignError):
            deposito.accept_upload(
                self.dir, filename="mature.fa", payload=b"basura\n",
                species=species.resolve("raton"), origin="subido", date="2026-08-26",
            )
        self.assertEqual(
            (self.dir / manifest.MANIFEST_NAME).read_text(encoding="utf-8"), antes
        )

    def test_un_nombre_que_esta_especie_NO_NECESITA_se_rechaza_diciendolo(self):
        with self.assertRaises(ShmirDesignError) as caja:
            deposito.accept_upload(
                self.dir, filename="rmsk_mouse.out", payload=b"x",
                species=species.resolve(CONEJO), origin="subido", date="2026-08-26",
            )
        texto = str(caja.exception)
        self.assertIn("rmsk_oryctolagus_cuniculus.out", texto)

    def test_el_ROL_se_resuelve_para_una_especie_QUE_NO_ES_EL_RATON(self):
        """`manifest.ROLES` trae `rmsk_mouse.out` ESCRITO, asi que buscar el rol por el
        nombre del fichero dejaba sin subir todo lo de cualquier otra especie."""
        conejo = species.resolve(CONEJO)
        fila = species.file_for(conejo, "rmsk_oryctolagus_cuniculus.out")
        self.assertIsNotNone(fila)
        self.assertEqual(deposito.role_for(conejo, "rmsk_oryctolagus_cuniculus.out").role,
                         "rmsk")

    def test_y_una_subida_suya_ya_NO_falla_por_el_rol_sino_por_el_CONTENIDO(self):
        with self.assertRaises(ShmirDesignError) as caja:
            deposito.accept_upload(
                self.dir, filename="rmsk_oryctolagus_cuniculus.out",
                payload=b"esto no es la salida de RepeatMasker\n",
                species=species.resolve(CONEJO), origin="subido", date="2026-08-26",
            )
        self.assertNotIn("no tiene rol", str(caja.exception))

    def test_volver_a_subirlo_ACTUALIZA_la_linea_no_la_duplica(self):
        crudo = (DATOS / "aav_casete.fa").read_bytes()
        for _ in range(2):
            deposito.accept_upload(
                self.dir, filename="aav_casete.fa", payload=crudo,
                species=species.resolve("raton"), origin="subido", date="2026-08-26",
            )
        texto = (self.dir / manifest.MANIFEST_NAME).read_text(encoding="utf-8")
        self.assertEqual(
            sum(1 for l in texto.splitlines() if l.startswith("aav_casete.fa\t")), 1
        )

    def test_los_comentarios_del_manifiesto_SOBREVIVEN_a_la_escritura(self):
        crudo = (DATOS / "aav_casete.fa").read_bytes()
        deposito.accept_upload(
            self.dir, filename="aav_casete.fa", payload=crudo,
            species=species.resolve("raton"), origin="subido", date="2026-08-26",
        )
        texto = (self.dir / manifest.MANIFEST_NAME).read_text(encoding="utf-8")
        self.assertIn("OJO CON LOS TRES CHECKSUMS", texto)

    def test_el_hermano_que_falta_se_NOMBRA_en_el_resultado(self):
        crudo = (DATOS / "rmsk_mouse.out").read_bytes()
        resultado = deposito.accept_upload(
            self.dir, filename="rmsk_mouse.out", payload=crudo,
            species=species.resolve("raton"), origin="subido", date="2026-08-26",
        )
        self.assertIn("rmsk_mouse.tbl", resultado.still_missing)

    def test_y_mientras_falte_el_frente_NO_se_abre(self):
        crudo = (DATOS / "rmsk_mouse.out").read_bytes()
        resultado = deposito.accept_upload(
            self.dir, filename="rmsk_mouse.out", payload=crudo,
            species=species.resolve("raton"), origin="subido", date="2026-08-26",
        )
        self.assertFalse(resultado.fronts_opened)

    def test_con_los_dos_el_frente_SI_se_abre(self):
        for nombre in ("rmsk_mouse.out", "rmsk_mouse.tbl"):
            resultado = deposito.accept_upload(
                self.dir, filename=nombre, payload=(DATOS / nombre).read_bytes(),
                species=species.resolve("raton"), origin="subido", date="2026-08-26",
            )
        self.assertIn("repeticiones", resultado.fronts_opened)


class TestLaSubidaDesdePresentation(_ConDirectorio):
    """La pagina no valida, no calcula md5 y no escribe el manifiesto: llama aqui."""

    def test_devuelve_filas_para_pintar_y_no_objetos_del_nucleo(self):
        crudo = (DATOS / "aav_casete.fa").read_bytes()
        filas = presentation.accept_reference_upload(
            "raton", directory=self.dir, filename="aav_casete.fa", payload=crudo,
            date="2026-08-26",
        )
        self.assertIn("md5", filas)
        self.assertIn("texto", filas)
        self.assertIsInstance(filas["texto"], str)

    def test_la_pagina_NO_calcula_ningun_md5(self):
        """El md5 sale del fichero y lo calcula el nucleo, nunca la pagina."""
        self.assertFalse("hashlib" in PAGINA, "la pagina calcula checksums")
        # `sequence_md5` SI se llama: es una funcion del nucleo, con test. Lo que no
        # puede haber es la pagina calculandolo por su cuenta.
        self.assertTrue("sequence_md5(" in PAGINA)

    def test_ni_escribe_en_data_reference_ni_toca_el_manifiesto(self):
        inicio = PAGINA.index("def _panel_refinamiento(")
        fin = PAGINA.index("\ndef ", inicio + 10)
        panel = PAGINA[inicio:fin]
        for prohibido in ("write_bytes(", "write_text(", "manifest", "open("):
            self.assertFalse(prohibido in panel, f"el panel usa {prohibido}")


# ─────────────── 4. la casilla global desaparece; ignorar es POR FICHERO ───────────────


class TestLaCasillaGlobalYaNoExiste(unittest.TestCase):

    def test_no_queda_ni_rastro_de_ella_en_la_pagina(self):
        self.assertFalse("Usar los de data/reference/" in PAGINA, "sigue la casilla")

    def test_si_un_fichero_esta_y_es_valido_SE_USA_sin_preguntar(self):
        self.assertTrue("load_from_manifest" in PAGINA, "ya no se conecta nada")
        self.assertFalse("usar_manifiesto" in PAGINA, "sigue la casilla global")

    def test_por_que_era_una_trampa_queda_ESCRITO(self):
        self.assertIn("efecto posible", deposito.WHY_NO_GLOBAL_TOGGLE)
        self.assertIn("NOT_RUN", deposito.WHY_NO_GLOBAL_TOGGLE)


class TestIgnorarUnFicheroEsPOR_FICHERO_Y_CON_MOTIVO(unittest.TestCase):

    def test_ignorar_sin_motivo_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            deposito.Ignored(filename="mature.fa", reason="")

    def test_con_motivo_se_construye(self):
        ignorado = deposito.Ignored(
            filename="mature.fa", reason="es la release 22 y la corrida pide la 23"
        )
        self.assertIn("release 22", ignorado.reason)

    def test_el_motivo_VIAJA_al_veredicto_no_se_queda_en_la_pantalla(self):
        from shmir_design.resources import load_from_manifest

        recursos = load_from_manifest(
            DATOS,
            ignore=(deposito.Ignored(filename="mature.fa", reason="prueba del motivo"),),
        )
        self.assertIsNone(recursos.mature)
        self.assertTrue(
            any("prueba del motivo" in n for n in recursos.notes), recursos.notes
        )

    def test_y_dice_QUE_FICHERO_se_ignoro_no_solo_que_algo_falta(self):
        from shmir_design.resources import load_from_manifest

        recursos = load_from_manifest(
            DATOS,
            ignore=(deposito.Ignored(filename="mature.fa", reason="prueba del motivo"),),
        )
        self.assertTrue(any("mature.fa" in n for n in recursos.notes))

    def test_el_rmsk_del_RATON_no_se_conecta_para_otra_especie(self):
        """Es el mismo agujero que `RepeatMask.query_length` cierra un nivel mas abajo:
        `--usar-manifiesto` conectaba el `.out` POR SU ROL sin mirar que se diseñaba."""
        from shmir_design.resources import load_from_manifest

        recursos = load_from_manifest(DATOS, species=species.resolve(CONEJO))
        self.assertIsNone(recursos.mask)
        self.assertNotIn("rmsk_mouse.out", recursos.connected)

    def test_y_con_el_raton_SI(self):
        from shmir_design.resources import load_from_manifest

        recursos = load_from_manifest(DATOS, species=species.resolve("raton"))
        self.assertIsNotNone(recursos.mask)

    def test_sin_ignorar_nada_el_fichero_se_usa(self):
        from shmir_design.reference import PACKAGE_REFERENCE_DIR
        from shmir_design.resources import load_from_manifest

        recursos = load_from_manifest(PACKAGE_REFERENCE_DIR)
        self.assertIsNotNone(recursos.mature)


# ───────────────────────── 5. la primera pantalla guia ─────────────────────────


class TestLosCuatroPasos(unittest.TestCase):

    def test_son_CINCO_y_en_su_orden(self):
        """Eran cuatro hasta que los ficheros de referencia se partieron en sus DOS
        momentos: el 3 pide lo imprescindible para diseñar y el 5, lo que refina."""
        pasos = presentation.steps_rows(species="", sequence_loaded=False, directory=DATOS)
        self.assertEqual([p["numero"] for p in pasos], [1, 2, 3, 4, 5])
        titulos = " · ".join(p["titulo"].lower() for p in pasos)
        self.assertIn("especie", titulos)
        self.assertIn("secuencia", titulos)
        self.assertIn("ficheros de referencia", titulos)
        self.assertIn("diseñar", titulos)
        self.assertIn("refinamiento", titulos)

    def test_sin_especie_solo_el_primero_esta_ABIERTO(self):
        pasos = presentation.steps_rows(species="", sequence_loaded=False, directory=DATOS)
        self.assertEqual([p["numero"] for p in pasos if p["abierto"]], [1])

    def test_con_especie_y_sin_secuencia_se_abre_el_segundo(self):
        pasos = presentation.steps_rows(
            species="raton", sequence_loaded=False, directory=DATOS
        )
        por_numero = {p["numero"]: p for p in pasos}
        self.assertTrue(por_numero[2]["abierto"])
        self.assertFalse(por_numero[4]["abierto"])

    def test_el_PASO_5_DICE_CUANTOS_FRENTES_se_van_a_poder_cerrar(self):
        """El recuento se MUDO del paso 3 al 5 cuando los ficheros se partieron en sus
        dos momentos: no es un requisito para empezar, es el estado del refinamiento."""
        pasos = presentation.steps_rows(
            species="raton", sequence_loaded=True, directory=DATOS, designed=True
        )
        quinto = next(p for p in pasos if p["numero"] == 5)
        self.assertIsNotNone(quinto["cerrables"])
        self.assertIn(str(quinto["cerrables"]), quinto["detalle"])
        self.assertIn(str(quinto["total_frentes"]), quinto["detalle"])

    def test_y_la_cifra_esta_CALCULADA_antes_de_ejecutar_nada(self):
        """Se sigue pudiendo saber que frentes cierran sin haber corrido: lo que cambia
        es DONDE se enseña, no cuando se puede saber."""
        pasos = presentation.steps_rows(
            species=CONEJO, sequence_loaded=False, directory=DATOS
        )
        quinto = next(p for p in pasos if p["numero"] == 5)
        self.assertEqual(quinto["cerrables"], 2)  # ver arriba: + los contextos

    def test_el_paso_3_NO_bloquea_se_puede_diseñar_con_frentes_abiertos(self):
        """Un frente abierto deja los candidatos en INCOMPLETE, no impide correr."""
        pasos = presentation.steps_rows(
            species=CONEJO, sequence_loaded=True, directory=DATOS
        )
        self.assertTrue(next(p for p in pasos if p["numero"] == 4)["abierto"])

    def test_pero_lo_DICE_con_las_palabras_de_siempre(self):
        pasos = presentation.steps_rows(
            species=CONEJO, sequence_loaded=True, directory=DATOS
        )
        cuarto = next(p for p in pasos if p["numero"] == 4)
        self.assertIn("INCOMPLETE", cuarto["detalle"])

    def test_la_pagina_los_pinta_NUMERADOS(self):
        self.assertTrue("steps_rows(" in PAGINA, "la pagina no pinta los pasos")
        for titulo in ("1)", "2)", "3)", "4)"):
            self.assertTrue(titulo in PAGINA, f"falta el paso {titulo}")


class TestLaPaginaSigueSinLOGICA(unittest.TestCase):

    def test_el_panel_de_ficheros_no_decide_nada(self):
        inicio = PAGINA.index("def _panel_refinamiento(")
        fin = PAGINA.index("def ", inicio + 10)
        panel = PAGINA[inicio:fin]
        comprobar_sin_logica(self, panel)


if __name__ == "__main__":
    unittest.main()
