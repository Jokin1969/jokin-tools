"""El modal no vuelve a pedir lo que el depósito ya tiene, y lo lee de UN SOLO SITIO.

**Reportado con el modal delante (2026-09-02)**: el de carga de off-targets NO VEIA el
depósito —pedía soltar `transcriptoma_3utr.fa` aunque ya estuviera dentro— y además
pedía los SEIS campos de `offtarget.Provenance` que ya se habían declarado al subirlo.
El de BLAST hacía lo mismo con la base: nombre, versión y md5 tecleados con la línea del
manifiesto delante.

Son DOS COPIAS DEL MISMO DATO, y esa es la enfermedad, no el número de casillas: la del
depósito la escribió quien subió el fichero, la del modal la teclea quien corre, y nada
las ata. Cuando divergen ninguna dice cuál manda; y quien no se acuerda del ensamblaje
se lo inventa, con lo que el conteo sale con la FORMA CORRECTA sobre el genoma
equivocado.

**Y la distinción de fondo, con las palabras con que se pidió**: el modal estaba pidiendo
procedencia de un FICHERO, no de una corrida. La del fichero pertenece al depósito; la de
la corrida es fecha, quién y parámetros.

Regla 5: escritos antes.
"""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from shmir_design import deposito, insumos, manifest, offtarget, presentation, species
from shmir_design.errors import ShmirDesignError

from tests.test_el_transcriptoma_ENTRA import UCSC
from tests.test_la_procedencia_se_pide_al_SUBIR import PROCEDENCIA

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "reference"
PAGINA = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
RATON = species.resolve("raton")


class TestLoQueElDepositoSABE(unittest.TestCase):

    def test_un_fichero_que_ESTA_sale_con_su_md5_y_su_linea(self):
        fichero = deposito.read_deposit("mirbase", species=RATON, directory=DATOS)
        self.assertTrue(fichero.present)
        self.assertTrue(fichero.registered)
        self.assertEqual(fichero.md5, fichero.entry.md5)

    def test_uno_que_NO_esta_lo_dice_y_NO_inventa_nada(self):
        fichero = deposito.read_deposit("transcriptoma", species=RATON, directory=DATOS)
        self.assertFalse(fichero.present)
        self.assertEqual(fichero.md5, "")
        self.assertIn("NOT_RUN no es PASS", fichero.describe())

    def test_el_NOMBRE_lo_pone_el_gestor_y_no_se_escribe_aqui(self):
        # Errata nº 47: un nombre escrito en un segundo sitio no da un error, da un «no
        # se ha podido comprobar» perpetuo. Se cruza contra la unica fuente.
        for fila in species.required_files(RATON):
            with self.subTest(fila.role):
                fichero = deposito.read_deposit(
                    fila.role, species=RATON, directory=DATOS
                )
                self.assertEqual(fichero.filename, fila.filename)

    def test_un_rol_que_esta_especie_no_necesita_ABORTA(self):
        # Devolver «no esta» lo haria indistinguible de un fichero que falta.
        with self.assertRaises(ShmirDesignError):
            deposito.read_deposit("no_existe", species=RATON, directory=DATOS)


class _ConDeposito(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = self.tmp / "reference"
        self.dir.mkdir()
        (self.dir / manifest.MANIFEST_NAME).write_text(
            (DATOS / manifest.MANIFEST_NAME).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def _subir_transcriptoma(self, **extra):
        return deposito.accept_upload(
            self.dir, filename="transcriptoma_3utr.fa",
            payload=UCSC.encode("utf-8"), species=RATON,
            origin="UCSC Table Browser", date="2026-09-01",
            **{**PROCEDENCIA, **extra},
        )


class TestLaProcedenciaVUELVE_del_manifiesto(_ConDeposito):
    """Lo que se declaró al subir es lo que el modal enseña. Cero campos que rellenar."""

    def test_los_SIETE_campos_de_Provenance_salen_del_deposito(self):
        self._subir_transcriptoma()
        fichero = deposito.read_deposit(
            "transcriptoma", species=RATON, directory=self.dir
        )
        campos = fichero.provenance_fields()
        self.assertEqual(
            set(campos), set(offtarget.Provenance.__dataclass_fields__)
        )
        # Y montan un `Provenance` de verdad: es la prueba de que no falta ninguno —esa
        # clase ABORTA con cualquiera vacio.
        procedencia = offtarget.Provenance(**campos)
        self.assertEqual(procedencia.assembly, PROCEDENCIA["assembly"])
        self.assertEqual(procedencia.md5, fichero.md5)

    def test_la_version_sale_de_la_FECHA_como_en_resources(self):
        # No es un campo nuevo: `resources` ya usa `entry.date or entry.md5` para todos.
        # Inventarse aqui otra regla daria dos versiones del mismo fichero.
        self._subir_transcriptoma()
        fichero = deposito.read_deposit(
            "transcriptoma", species=RATON, directory=self.dir
        )
        self.assertEqual(fichero.provenance_fields()["version"], "2026-09-01")

    def test_una_linea_VIEJA_dice_QUE_le_falta(self):
        # Un manifiesto de antes de estas columnas se sigue leyendo y sus cuatro campos
        # salen vacios, que es la verdad: nadie los registro. Lo que no puede pasar es
        # que eso se lea como procedencia completa.
        (self.dir / "transcriptoma_3utr.fa").write_text(UCSC, encoding="utf-8")
        fichero = deposito.read_deposit(
            "transcriptoma", species=RATON, directory=self.dir
        )
        self.assertEqual(
            fichero.missing_provenance,
            ("ensamblaje", "tabla", "fecha_tabla", "representante"),
        )
        self.assertIn("Reemplázalo por el gestor", fichero.describe())

    def test_y_un_rol_que_NO_las_pide_no_sale_con_huecos(self):
        # Un casete de AAV no sale de ninguna tabla: ahi el vacio es la VERDAD, y
        # pedirlas seria inventarse un hueco.
        fichero = deposito.read_deposit("transgen", species=RATON, directory=DATOS)
        self.assertEqual(fichero.missing_provenance, ())

    def test_si_el_fichero_de_disco_NO_es_el_registrado_se_DICE(self):
        # La procedencia registrada seria la de OTRO fichero, y se adjuntaria al
        # veredicto con la forma correcta.
        self._subir_transcriptoma()
        (self.dir / "transcriptoma_3utr.fa").write_text(
            UCSC + ">otro\nGGGGCCCCGGGGCCCCGGGGCC\n", encoding="utf-8"
        )
        fichero = deposito.read_deposit(
            "transcriptoma", species=RATON, directory=self.dir
        )
        self.assertTrue(fichero.stale_md5)
        self.assertIn("OTRO fichero", fichero.describe())


class TestLosCUATRO_MODALES_preguntan_al_mismo_sitio(unittest.TestCase):
    """«Que la lectura del depósito salga de un solo sitio», como `_filter_columns`."""

    def test_hay_una_fila_por_INSUMO_declarado_de_esa_corrida(self):
        filas = presentation.deposit_for_run(
            "corrida_offtarget", species="raton", directory=DATOS
        )
        self.assertEqual(
            [f["rol"] for f in filas],
            [i.rol for i in insumos.insumos_de("corrida_offtarget")],
        )

    def test_TODOS_los_tipos_de_corrida_tienen_panel(self):
        # Un quinto modal que no declare sus insumos falla aqui, no el dia que alguien
        # busque por que su corrida no vio el deposito.
        for tipo in insumos.CONSUMIDOS:
            with self.subTest(tipo):
                presentation.deposit_for_run(
                    tipo, species="raton", directory=DATOS
                )

    def test_la_corrida_de_empalme_sale_VACIA_y_DICE_por_que(self):
        # Vacia es una decision tomada; ausente seria una que nadie miro.
        self.assertEqual(
            presentation.deposit_for_run(
                "corrida_empalme", species="raton", directory=DATOS
            ),
            [],
        )
        self.assertIn(
            "no consume",
            presentation.deposit_note("corrida_empalme").lower(),
        )

    def test_la_fila_dice_si_hay_que_OFRECER_SUBIDA(self):
        # «Sólo ofrece subida propia si el fichero no está.»
        falta = presentation.deposit_for_run(
            "corrida_offtarget", species="raton", directory=DATOS
        )[0]
        self.assertFalse(falta["presente"])
        self.assertTrue(falta["ofrecer_subida"])
        esta = presentation.deposit_for_run(
            "corrida_seed", species="raton", directory=DATOS
        )[0]
        self.assertTrue(esta["presente"])
        self.assertFalse(esta["ofrecer_subida"])

    def test_toda_lectura_pasa_por_read_deposit(self):
        import inspect

        # La cadena entera, eslabon a eslabon: el panel llama a la fila, la fila al
        # lector. Ningun consumidor se salta el ultimo.
        self.assertIn(
            "deposit_file", inspect.getsource(presentation.deposit_for_run)
        )
        for nombre in (
            "deposit_file", "offtarget_catalog_from_deposit",
            "blast_database_from_deposit",
        ):
            with self.subTest(nombre):
                self.assertIn(
                    "read_deposit",
                    inspect.getsource(getattr(presentation, nombre)),
                )


class TestLaPAGINA_no_abre_el_deposito_por_su_cuenta(unittest.TestCase):
    """Regla 6, y el motivo de `offtarget_seed`: si cada modal lo abriera, el quinto se
    quedaria fuera sin que nadie lo note."""

    def _modal(self, nombre: str) -> str:
        trozo = PAGINA.split(f"def {nombre}(", 1)[1]
        return re.split(r"\ndef ", trozo, maxsplit=1)[0]

    def test_los_cuatro_modales_PINTAN_el_panel_del_deposito(self):
        for modal in (
            "_modal_blast", "_modal_seed", "_modal_offtarget", "_modal_empalme",
        ):
            with self.subTest(modal):
                self.assertIn("_panel_deposito", self._modal(modal))

    def test_y_la_pagina_NO_carga_el_manifiesto(self):
        # La LLAMADA, no el nombre: el panel NOMBRA a `read_deposit` en su docstring
        # para decir por donde pasa la lectura, y eso es lo contrario de saltarsela. Un
        # guardia que salta sobre una mencion se acaba apagando — y anclarlo al texto de
        # un comentario ya dio un verde falso una vez (errata nº 54).
        self.assertNotIn("load_manifest(", PAGINA)
        self.assertNotIn("read_deposit(", PAGINA)

    def test_el_modal_de_offtarget_ya_NO_pide_los_seis_campos(self):
        modal = self._modal("_modal_offtarget")
        for campo in offtarget.Provenance.__dataclass_fields__:
            with self.subTest(campo):
                self.assertNotIn(f'"{campo}"', modal)

    def test_ni_el_de_BLAST_los_TRES_de_la_base(self):
        modal = self._modal("_modal_blast")
        self.assertNotIn('st.text_input("Base"', modal)
        self.assertNotIn('st.text_input("Versión"', modal)
        self.assertNotIn('st.text_input("md5 de la base"', modal)


if __name__ == "__main__":
    unittest.main()
