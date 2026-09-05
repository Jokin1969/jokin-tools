"""«Descargar todo»: la copia de seguridad es UN BOTÓN, no una tarea de disciplina.

**Pedido el 2026-09-02**, con el motivo delante:

    El volumen es la única copia de todo lo que pone un frente en verde, y con él se iría
    la procedencia. Que la copia de seguridad sea un botón, no una tarea de disciplina.

Y es exacto. Los ficheros que ponen un frente en verde —`mature.fa`, el casete, el
plásmido del andamio, el transcriptoma— **no van en git**: no entran en un repositorio, y
por eso viven sólo en el volumen. Con ellos se iría el `manifest.tsv` de trabajo, que es
donde está su md5, su fecha, su origen y su ensamblaje — o sea **la procedencia**, que es
lo único que hace auditable un veredicto dentro de un año.

Hasta hoy había un botón «Descargar» POR FICHERO y el manifiesto no tenía ninguno: la
copia de seguridad existía como posibilidad y no como acción. Eso no es una copia de
seguridad, es un recordatorio.

Regla 5: escritos antes.
"""

import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from shmir_design import gestor, manifest, presentation
from shmir_design.errors import ShmirDesignError

DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"


class _ConDeposito(unittest.TestCase):
    """Un depósito de verdad en un temporal, con proyecto y biblioteca."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = self.tmp / "reference"
        self.dir.mkdir()
        for nombre in ("manifest.tsv", "rmsk_mouse.out", "rmsk_mouse.tbl"):
            shutil.copy2(DATOS / nombre, self.dir / nombre)
        self.proyectos = self.tmp / "proyectos"
        self.almacen = presentation.project_create(
            self.proyectos, slug="uno", date="2026-09-01",
            sequence="ACGTACGTACGTACGTACGTAC", species="mouse",
            anatomy=None, anatomy_source="sin_resolver",
        )
        self.almacen.append("nota", {"texto": "lo que decidí"}, date="2026-09-01")

    def _zip(self, **extra):
        crudo = gestor.export_all(
            self.dir, projects=self.proyectos, date="2026-09-02", **extra
        )
        return zipfile.ZipFile(io.BytesIO(crudo)), crudo


class TestLoQueLLEVA(_ConDeposito):

    def test_lleva_los_ficheros_del_deposito(self):
        zf, _ = self._zip()
        for nombre in ("rmsk_mouse.out", "rmsk_mouse.tbl"):
            with self.subTest(nombre):
                self.assertIn(f"reference/{nombre}", zf.namelist())

    def test_y_el_MANIFIESTO_que_no_tenia_boton_propio(self):
        # Es lo que lleva la procedencia: md5, fecha, origen, ensamblaje. Sin él, los
        # ficheros son secuencias sin saber de dónde salieron.
        zf, _ = self._zip()
        self.assertIn("reference/manifest.tsv", zf.namelist())

    def test_y_los_LOGS_de_cada_proyecto_con_sus_DOS_piezas(self):
        zf, _ = self._zip()
        # LAS DOS: `proyecto.json` identifica la entrada —md5 y longitud de la
        # secuencia— y `registro.jsonl` lleva lo que se decidió. Uno sin el otro no se
        # puede leer dentro de un año.
        self.assertIn("proyectos/uno/proyecto.json", zf.namelist())
        self.assertIn("proyectos/uno/registro.jsonl", zf.namelist())

    def test_el_contenido_es_el_MISMO_byte_a_byte(self):
        zf, _ = self._zip()
        self.assertEqual(
            zf.read("reference/rmsk_mouse.out"),
            (self.dir / "rmsk_mouse.out").read_bytes(),
        )

    def test_y_el_log_del_proyecto_se_lee_tal_cual(self):
        zf, _ = self._zip()
        lineas = zf.read("proyectos/uno/registro.jsonl").decode("utf-8").splitlines()
        self.assertIn("lo que decidí", json.loads(lineas[0])["payload"]["texto"])


class TestElLEEME(_ConDeposito):
    """Un zip sin nada que lo explique es un montón de ficheros dentro de un año."""

    def _leeme(self) -> str:
        zf, _ = self._zip()
        return zf.read("LEEME.txt").decode("utf-8")

    def test_dice_QUE_es_y_de_DONDE_salio(self):
        texto = self._leeme()
        self.assertIn(str(self.dir), texto)
        self.assertIn(str(self.proyectos), texto)
        self.assertIn("2026-09-02", texto)

    def test_lleva_el_INVENTARIO_con_md5_para_poder_comprobarlo_sin_la_app(self):
        texto = self._leeme()
        crudo = (self.dir / "rmsk_mouse.out").read_bytes()
        from shmir_design.identidad import file_fingerprint

        self.assertIn(file_fingerprint(crudo), texto)

    def test_y_DICE_como_se_restaura(self):
        # Sin esto es un zip que nadie sabe dónde va, y el sitio importa: el directorio
        # de trabajo se declara por variable de entorno.
        self.assertIn("SHMIR_REFERENCE_DIR", self._leeme())
        self.assertIn("SHMIR_PROJECT_DIR", self._leeme())

    def test_y_AVISA_de_lo_que_esta_copia_NO_cubre(self):
        # Es una foto, no un respaldo continuo: lo que se suba después no está aquí.
        self.assertIn("no se actualiza sola", self._leeme().lower())


class TestLoQueNOhaceEnSILENCIO(_ConDeposito):

    def test_un_fichero_ILEGIBLE_aborta_en_vez_de_omitirlo(self):
        # Media copia que parece completa es peor que ninguna: mismo criterio que
        # `seed_reference_dir`, que aborta antes que dejar un directorio incompleto con
        # pinta de completo. Aquí además nadie miraría el zip hasta que hiciera falta.
        #
        # NO se prueba con `chmod 000`: como root eso no impide leer, así que el control
        # se SALTABA — y un control que no corre en el entorno donde se corren los tests
        # es exactamente lo que este proyecto no acepta. Se prueba la pieza que decide,
        # con una ruta que de verdad no se puede leer.
        with self.assertRaises(ShmirDesignError) as caja:
            gestor._bytes_de(self.dir / "no_existe.fa", que="un fichero de prueba")
        self.assertIn("media copia", str(caja.exception))

    def test_un_proyecto_al_que_le_falta_su_LOG_aborta_la_copia_entera(self):
        # La misma regla un nivel más arriba y sin depender de permisos: una entrada sin
        # su log no dice nada, y guardar sólo una mitad sería peor que no guardar.
        (self.proyectos / "uno" / "registro.jsonl").unlink()
        with self.assertRaises(ShmirDesignError) as caja:
            self._zip()
        self.assertIn("uno", str(caja.exception))

    def test_sin_proyectos_la_copia_SE_HACE_igual_y_lo_dice(self):
        # No haber creado ninguno es lo normal el primer día, no un fallo.
        vacio = self.tmp / "sin_proyectos"
        crudo = gestor.export_all(self.dir, projects=vacio, date="2026-09-02")
        zf = zipfile.ZipFile(io.BytesIO(crudo))
        self.assertIn("reference/manifest.tsv", zf.namelist())
        self.assertIn("ningún proyecto", zf.read("LEEME.txt").decode("utf-8"))

    def test_un_deposito_que_NO_EXISTE_aborta(self):
        with self.assertRaises(ShmirDesignError):
            gestor.export_all(self.tmp / "no_esta", projects=self.proyectos,
                              date="2026-09-02")

    def test_el_zip_se_puede_ABRIR_y_no_esta_corrupto(self):
        zf, _ = self._zip()
        self.assertIsNone(zf.testzip())


class TestElINVENTARIO_antes_de_pulsar(_ConDeposito):
    """Cuánto va a pesar se dice ANTES: el transcriptoma son 84 MB."""

    def test_dice_cuantos_ficheros_y_cuanto_pesan(self):
        informe = presentation.backup_inventory(
            directory=self.dir, projects=self.proyectos
        )
        self.assertEqual(informe["ficheros"], 3)
        self.assertGreater(informe["bytes"], 0)
        self.assertEqual(informe["proyectos"], 1)

    def test_y_lo_dice_en_un_TEXTO_ya_montado(self):
        # La página no formatea tamaños (regla 6).
        informe = presentation.backup_inventory(
            directory=self.dir, projects=self.proyectos
        )
        self.assertIn("3", informe["texto"])
        self.assertTrue(informe["texto"].strip())

    def test_el_inventario_NO_construye_el_zip(self):
        # Se pinta en CADA repintado: si montara el zip, con el transcriptoma dentro la
        # página tardaría un minuto por clic. Es la lección de la errata nº 59.
        import inspect

        fuente = inspect.getsource(presentation.backup_inventory)
        self.assertNotIn("export_all", fuente)
        self.assertNotIn("zipfile", fuente)


class TestLaPAGINA(unittest.TestCase):

    def setUp(self):
        crudo = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        # SIN COMENTARIOS **NI DOCSTRINGS**. Anclar un guardia al texto de una
        # explicación ya dio un verde falso (errata nº 54) y aquí daba un ROJO falso: el
        # docstring del panel NOMBRA a `st.download_button` justo para decir por qué va
        # detrás de un botón. Se mira el código, no la prosa que lo explica.
        import re

        sin_docstrings = re.sub(r'"""[\s\S]*?"""', "", crudo)
        self.fuente = "\n".join(
            l for l in sin_docstrings.splitlines() if not l.strip().startswith("#")
        )

    def test_el_gestor_tiene_el_boton(self):
        self.assertIn("_descargar_todo", self.fuente)

    def test_y_el_zip_se_construye_SOLO_al_pulsar_no_en_cada_repintado(self):
        # `st.download_button` necesita los datos ya hechos, así que montarlo en línea
        # significa montarlo SIEMPRE. Va detrás de un botón que lo prepara.
        panel = self.fuente.split("def _descargar_todo", 1)[1].split("\ndef ")[0]
        self.assertIn("st.button", panel)
        self.assertLess(panel.index("st.button"), panel.index("st.download_button"))

    def test_y_la_pagina_NO_monta_el_zip_ni_calcula_tamaños(self):
        panel = self.fuente.split("def _descargar_todo", 1)[1].split("\ndef ")[0]
        for prohibido in ("zipfile", "/ 1024", "len("):
            with self.subTest(prohibido):
                self.assertNotIn(prohibido, panel)


if __name__ == "__main__":
    unittest.main()
