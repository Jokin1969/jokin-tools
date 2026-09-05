"""Los proyectos se pueden BORRAR, RENOMBRAR y fechar con un calendario.

**Pedido el 2026-09-02**: «mejorar un poco el sistema para guardar proyectos. En especial
para ir borrando los antiguos y que me permita editar el nombre y añademe un calendario
(con Hoy) para añadir la fecha».

Las tres cosas tocan un log que este proyecto tiene decidido que es **append-only y
auditable**, así que ninguna se hace a la ligera:

  - **BORRAR** es lo único de la app que destruye un registro. No se puede deshacer y no
    se puede regenerar: una corrida de BLAST son horas de cómputo fuera de aquí. Así que
    va con el plan delante —qué se pierde, contado— y con la descarga al lado, que es lo
    que hace que el registro sea tuyo y no de la app (mismo criterio que `gestor.download`).
  - **RENOMBRAR** cambia el nombre VISIBLE y NO el slug: el slug es la identidad, nombra
    el directorio y viaja en los mensajes. Y el cambio se APUNTA en el log, porque un
    proyecto que ayer se llamaba otra cosa es justo lo que hace irreconocible un registro
    de hace un año.
  - **LA FECHA** deja de teclearse. Una fecha a mano se equivoca en silencio —`2026-09-02`
    y `2026-09-20` se parecen— y ya provocó una salida falsa: ante un `run_id` repetido, la
    tentación era cambiar la fecha (errata nº 48).

Regla 5: escritos antes.
"""

import datetime
import shutil
import tempfile
import unittest
from pathlib import Path

from shmir_design import presentation, store
from shmir_design.errors import ShmirDesignError

SECUENCIA = "ACGTACGTACGTACGTACGTAC"


class _ConProyectos(unittest.TestCase):

    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.raiz, True)

    def _crear(self, slug="prueba", date="2026-09-01"):
        return presentation.project_create(
            self.raiz, slug=slug, date=date, sequence=SECUENCIA, species="mouse",
            anatomy=None, anatomy_source="sin_resolver",
        )


# ─────────────────────────── el nombre visible ───────────────────────────


class TestElNOMBRE_se_puede_editar(_ConProyectos):

    def test_por_defecto_el_nombre_es_el_slug(self):
        almacen = self._crear()
        self.assertEqual(almacen.project.display_name, "prueba")

    def test_renombrar_cambia_lo_que_se_VE(self):
        almacen = self._crear()
        presentation.project_rename(almacen, "Prnp ratón — panel definitivo",
                                    date="2026-09-02")
        vuelto = presentation.project_open(self.raiz, "prueba")
        self.assertEqual(vuelto.project.display_name, "Prnp ratón — panel definitivo")

    def test_y_NO_cambia_el_slug(self):
        # El slug nombra el directorio y viaja en los mensajes: cambiarlo dejaría sin
        # abrir cualquier referencia anterior.
        almacen = self._crear()
        presentation.project_rename(almacen, "otro nombre", date="2026-09-02")
        vuelto = presentation.project_open(self.raiz, "prueba")
        self.assertEqual(vuelto.project.slug, "prueba")
        self.assertTrue((self.raiz / "prueba").is_dir())

    def test_el_cambio_QUEDA_EN_EL_LOG(self):
        # Un proyecto que ayer se llamaba otra cosa es lo que hace irreconocible un
        # registro de hace un año. El renombrado es un suceso, no un ajuste.
        almacen = self._crear()
        presentation.project_rename(almacen, "el nombre bueno", date="2026-09-02")
        notas = presentation.project_open(self.raiz, "prueba").records("nota")
        self.assertEqual(len(notas), 1)
        self.assertIn("prueba", notas[0].payload["texto"])
        self.assertIn("el nombre bueno", notas[0].payload["texto"])

    def test_y_la_CADENA_sigue_valiendo(self):
        almacen = self._crear()
        presentation.project_rename(almacen, "otro", date="2026-09-02")
        presentation.project_open(self.raiz, "prueba").verify()  # aborta si se rompió

    def test_un_nombre_VACIO_se_rechaza(self):
        # Vaciarlo dejaría el proyecto sin nombre visible y volvería al slug SIN dejar
        # rastro de que alguien lo quiso cambiar. Se aborta.
        almacen = self._crear()
        with self.assertRaises(ShmirDesignError):
            presentation.project_rename(almacen, "   ", date="2026-09-02")

    def test_renombrar_al_MISMO_nombre_no_escribe_nada(self):
        # Un `nota` por cada clic sin cambio ensucia el log, que es lo que se lee para
        # saber qué pasó.
        almacen = self._crear()
        presentation.project_rename(almacen, "uno", date="2026-09-02")
        presentation.project_rename(
            presentation.project_open(self.raiz, "prueba"), "uno", date="2026-09-02"
        )
        self.assertEqual(
            len(presentation.project_open(self.raiz, "prueba").records("nota")), 1
        )

    def test_un_proyecto_VIEJO_sin_nombre_se_sigue_abriendo(self):
        # `proyecto.json` escrito antes de que existiera el campo.
        almacen = self._crear()
        import json

        datos = json.loads(almacen.project_path.read_text(encoding="utf-8"))
        del datos["title"]
        almacen.project_path.write_text(json.dumps(datos), encoding="utf-8")
        self.assertEqual(
            presentation.project_open(self.raiz, "prueba").project.display_name, "prueba"
        )


# ─────────────────────────── borrar los antiguos ───────────────────────────


class TestBORRAR(_ConProyectos):

    def test_el_plan_dice_QUE_SE_PIERDE_antes_de_borrar(self):
        almacen = self._crear()
        almacen.append("nota", {"texto": "una nota"}, date="2026-09-01")
        plan = presentation.project_delete_plan(self.raiz, "prueba")
        self.assertIn("prueba", plan["texto"])
        self.assertEqual(plan["registros"], 1)

    def test_y_DICE_que_una_corrida_no_se_regenera(self):
        # No es un fichero de referencia, que se vuelve a bajar: una corrida de BLAST
        # son horas de computo FUERA de esta app.
        almacen = self._crear()
        almacen.append("nota", {"texto": "x"}, date="2026-09-01")
        self.assertIn(
            "NO SE PUEDE VOLVER A CALCULAR",
            presentation.project_delete_plan(self.raiz, "prueba")["texto"],
        )

    def test_un_proyecto_VACIO_lo_dice_y_es_otra_cosa(self):
        # Borrar uno sin ningun registro no pierde nada, y el plan no puede sonar igual
        # que borrar uno con doce corridas.
        self._crear()
        plan = presentation.project_delete_plan(self.raiz, "prueba")
        self.assertEqual(plan["registros"], 0)
        self.assertTrue(plan["vacio"])

    def test_el_plan_NO_borra_nada(self):
        self._crear()
        presentation.project_delete_plan(self.raiz, "prueba")
        self.assertTrue((self.raiz / "prueba").is_dir())

    def test_borrar_se_lleva_el_directorio_entero(self):
        self._crear()
        presentation.project_delete(self.raiz, "prueba")
        self.assertFalse((self.raiz / "prueba").exists())

    def test_y_devuelve_lo_que_se_fue(self):
        almacen = self._crear()
        almacen.append("nota", {"texto": "x"}, date="2026-09-01")
        texto = presentation.project_delete(self.raiz, "prueba")
        self.assertIn("prueba", texto)
        self.assertIn("1", texto)

    def test_borrar_uno_que_no_existe_ABORTA(self):
        # Devolver «hecho» sobre algo que no estaba se leeria como que se borro.
        with self.assertRaises(ShmirDesignError):
            presentation.project_delete(self.raiz, "no_esta")

    def test_no_se_sale_del_directorio_de_proyectos(self):
        # El slug llega de un desplegable, pero el guardia es el mismo que ya protege
        # `project_open`: un nombre no es una ruta.
        with self.assertRaises(ShmirDesignError):
            presentation.project_delete(self.raiz, "../otro")

    def test_borrar_uno_NO_toca_los_demas(self):
        self._crear("uno")
        self._crear("dos")
        presentation.project_delete(self.raiz, "uno")
        self.assertTrue((self.raiz / "dos").is_dir())

    def test_uno_con_la_CADENA_ROTA_se_puede_descargar_y_borrar(self):
        # Es justo el que sobra. Si borrar exigiera `verify()`, un log corrupto seria
        # imposible de quitar — y lo que exige la cadena sana es ESCRIBIR en el, no
        # llevarselo.
        almacen = self._crear()
        almacen.append("nota", {"texto": "x"}, date="2026-09-01")
        almacen.log_path.write_text(
            almacen.log_path.read_text(encoding="utf-8").replace("x", "otra cosa"),
            encoding="utf-8",
        )
        with self.assertRaises(ShmirDesignError):  # el guardia sigue mordiendo
            presentation.project_open(self.raiz, "prueba")
        self.assertIn("otra cosa", presentation.project_export(self.raiz, "prueba"))
        presentation.project_delete(self.raiz, "prueba")
        self.assertFalse((self.raiz / "prueba").exists())

    def test_el_registro_se_puede_DESCARGAR_antes(self):
        # Es lo que hace que el registro sea tuyo y no de la app, igual que en el gestor
        # de ficheros de referencia.
        almacen = self._crear()
        almacen.append("nota", {"texto": "lo que decidí"}, date="2026-09-01")
        crudo = presentation.project_export(self.raiz, "prueba")
        self.assertIn("lo que decidí", crudo)
        self.assertIn("prueba", crudo)

    def test_y_lo_descargado_lleva_las_DOS_piezas(self):
        # `proyecto.json` identifica la entrada y `registro.jsonl` lleva lo que se
        # decidió: uno sin el otro no se puede leer dentro de un año.
        almacen = self._crear()
        almacen.append("nota", {"texto": "x"}, date="2026-09-01")
        crudo = presentation.project_export(self.raiz, "prueba")
        self.assertIn(store.PROJECT_FILE, crudo)
        self.assertIn(store.LOG_FILE, crudo)


# ─────────────── la lista, para poder decidir CUAL borrar ───────────────


class TestLaLISTA_deja_ver_cual_esta_viejo(_ConProyectos):

    def test_cada_fila_dice_su_ULTIMA_actividad(self):
        almacen = self._crear()
        almacen.append("nota", {"texto": "x"}, date="2026-08-30")
        almacen.append("nota", {"texto": "y"}, date="2026-09-01")
        fila = presentation.project_list(self.raiz)[0]
        self.assertEqual(fila["ultima"], "2026-09-01")

    def test_uno_SIN_registros_lo_dice_y_no_finge_una_fecha(self):
        # Poner ahi la de creacion mezclaria «no se ha tocado» con «se toco el dia que
        # se creo», que es justo lo que hay que distinguir para borrar.
        self._crear()
        fila = presentation.project_list(self.raiz)[0]
        self.assertEqual(fila["ultima"], "")
        self.assertTrue(fila["vacio"])

    def test_y_su_NOMBRE_visible(self):
        almacen = self._crear()
        presentation.project_rename(almacen, "el bueno", date="2026-09-02")
        self.assertEqual(presentation.project_list(self.raiz)[0]["nombre"], "el bueno")


# ─────────────────────────── la fecha, con calendario ───────────────────────────


class TestLaFECHA_sale_de_un_calendario(unittest.TestCase):
    """La página pinta el calendario; el formato lo pone `presentation` (regla 6)."""

    def test_una_fecha_se_convierte_a_la_forma_del_log(self):
        self.assertEqual(
            presentation.date_text(datetime.date(2026, 9, 2)), "2026-09-02"
        )

    def test_sin_fecha_devuelve_VACIO_y_no_la_de_hoy(self):
        # Vacio hace que el nucleo aborte diciendo que falta la fecha. Poner la de hoy
        # seria inventarse el dato: la fecha de descarga de un fichero NO es hoy.
        self.assertEqual(presentation.date_text(None), "")

    def test_un_texto_que_ya_es_una_fecha_pasa_tal_cual(self):
        self.assertEqual(presentation.date_text("2026-09-02"), "2026-09-02")

    def test_un_RANGO_aborta(self):
        # `st.date_input` devuelve una TUPLA en modo rango, y una tupla convertida a
        # texto entra en el log con la forma correcta y sin significado.
        with self.assertRaises(ShmirDesignError):
            presentation.date_text((datetime.date(2026, 9, 1), datetime.date(2026, 9, 2)))

    def test_hoy_es_HOY_y_se_deriva(self):
        self.assertEqual(
            presentation.today_text(), datetime.date.today().isoformat()
        )


class TestLaPAGINA_pinta_el_calendario_y_no_teclea_fechas(unittest.TestCase):
    """Regla 6: la página pinta el calendario; el formato lo pone `presentation`."""

    def setUp(self):
        crudo = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        # SIN COMENTARIOS. Anclar un guardia al texto de un comentario ya dio un verde
        # falso una vez (errata nº 54) y aquí daría un rojo falso: los comentarios
        # NOMBRAN a `date_text` para decir por dónde pasa la conversión.
        self.fuente = "\n".join(
            l for l in crudo.splitlines() if not l.strip().startswith("#")
        )

    def test_ninguna_fecha_se_TECLEA_ya(self):
        # Un `text_input` de fecha es la vía por la que se cuela un dato equivocado con
        # la forma correcta. Se buscan por el nombre del campo, que es el que se ve.
        for etiqueta in ('"Fecha"', '"Fecha de descarga (AAAA-MM-DD)"', '"Fecha (AAAA-MM-DD)"'):
            with self.subTest(etiqueta):
                self.assertNotIn(f"st.text_input({etiqueta}", self.fuente)
                self.assertNotIn(f"st.sidebar.text_input({etiqueta}", self.fuente)

    def test_y_TODAS_pasan_por_date_text(self):
        # Sin eso, lo que devuelve el widget —un `datetime.date`, o una tupla en modo
        # rango— llegaría al log convertido a texto por la página.
        self.assertEqual(
            self.fuente.count("date_input("), self.fuente.count("date_text(")
        )

    def test_las_de_AHORA_vienen_con_hoy_y_las_AJENAS_no(self):
        # Una corrida se guarda hoy; un fichero se descargó otro día. Poner hoy en la
        # segunda sería inventarse el dato.
        # CUATRO pasan ahora: el proyecto, la corrida, la seleccion y la biblioteca.
        self.assertEqual(self.fuente.count('value="today"'), 4)
        # TRES son de un fichero que se descargo OTRO dia: los dos del gestor —subir y
        # reemplazar— y el del modal de off-targets.
        self.assertEqual(self.fuente.count("value=None"), 3)

    def test_la_pagina_NO_convierte_ninguna_fecha_por_su_cuenta(self):
        for prohibido in ("isoformat()", "strftime(", "datetime.date.today()"):
            with self.subTest(prohibido):
                self.assertNotIn(prohibido, self.fuente)

    def test_el_panel_de_gestion_EXISTE_y_pide_el_plan_antes_de_borrar(self):
        self.assertIn("_gestionar_proyectos", self.fuente)
        # El plan va ANTES del boton de confirmar, no despues.
        panel = self.fuente.split("def _gestionar_proyectos", 1)[1]
        self.assertLess(
            panel.index("project_delete_plan"), panel.index("project_delete(")
        )

    def test_y_la_pagina_no_decide_QUE_se_pierde(self):
        panel = self.fuente.split("def _gestionar_proyectos", 1)[1]
        for prohibido in ("len(", "sorted(", ".records()"):
            with self.subTest(prohibido):
                self.assertNotIn(prohibido, panel.split("st.divider()")[0])


class TestElPanelSE_PINTA_de_verdad(_ConProyectos):
    """No basta con que esté escrito: se ejecuta con proyectos reales delante.

    `AppTest` no puede llegar aquí —la página no llega a `_panel_proyecto` sin un fichero
    subido, y no sabe rellenar un `file_uploader`—, así que el panel se invoca
    directamente. En modo «bare» los botones valen `False`, o sea que esto recorre la
    rama de PINTAR: es lo que distingue «el panel está escrito» de «el panel corre».
    """

    def _panel(self):
        import importlib.util

        ruta = Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        spec = importlib.util.spec_from_file_location("pagina_shmir", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo._gestionar_proyectos

    def test_con_dos_proyectos_y_uno_renombrado(self):
        almacen = self._crear("uno")
        presentation.project_rename(almacen, "el bueno", date="2026-09-02")
        self._crear("dos")
        catalogo = presentation.project_options(self.raiz)
        self._panel()("mouse", self.raiz, catalogo, "2026-09-02")

    def test_y_sin_ninguno_no_revienta(self):
        catalogo = presentation.project_options(self.raiz)
        self._panel()("mouse", self.raiz, catalogo, "2026-09-02")


if __name__ == "__main__":
    unittest.main()
