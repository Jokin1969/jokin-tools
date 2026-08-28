"""Donde vive `data/reference/` cuando la app corre en un servidor.

Regla 5: escritos antes.

El panel de subida escribe en `data/reference/`, que hasta ahora era **el directorio del
paquete**. En local eso esta bien. En un despliegue no: el sistema de ficheros de la
imagen es efimero, asi que cada redespliegue se llevaria por delante todo lo subido —y la
linea del manifiesto con ello— sin que nadie se entere hasta que un frente vuelva a salir
NOT_RUN. Peor: `manifest.tsv` esta versionado, asi que escribirlo dentro de la imagen deja
el arbol de trabajo sucio contra el siguiente despliegue.

La salida es una indireccion, no un cambio de sitio: **el directorio de TRABAJO se
declara**, y por defecto es el del paquete, que es lo que hace que en local no cambie
nada. Y se **siembra** desde el versionado, porque los fixtures que si estan en git tienen
que seguir estando el primer dia.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from shmir_design import manifest, reference, trabajo
from shmir_design.errors import ShmirDesignError

VERSIONADO = Path(__file__).resolve().parent.parent / "data" / "reference"


class TestElDirectorioPorDefecto(unittest.TestCase):

    def test_sin_declarar_nada_es_el_DEL_PAQUETE(self):
        """En local no cambia nada, que es la condicion para que esto sea aceptable."""
        self.assertEqual(trabajo.reference_dir(env={}), reference.PACKAGE_REFERENCE_DIR)

    def test_declarado_manda_el_declarado(self):
        self.assertEqual(
            trabajo.reference_dir(env={trabajo.ENV_VAR: "/data/shmir/reference"}),
            Path("/data/shmir/reference"),
        )

    def test_vacio_NO_es_declarado(self):
        """`SHMIR_REFERENCE_DIR=` es no haberlo puesto, no «la raiz»."""
        self.assertEqual(trabajo.reference_dir(env={trabajo.ENV_VAR: "  "}),
                         reference.PACKAGE_REFERENCE_DIR)

    def test_una_ruta_RELATIVA_aborta(self):
        """Relativa a que. Un directorio de trabajo que depende del cwd deja los
        ficheros en un sitio distinto segun quien arranque el proceso."""
        with self.assertRaises(ShmirDesignError) as caja:
            trabajo.reference_dir(env={trabajo.ENV_VAR: "datos/ref"})
        self.assertIn("absoluta", str(caja.exception))

    def test_lee_el_ENTORNO_de_verdad_si_no_se_le_pasa_ninguno(self):
        anterior = os.environ.get(trabajo.ENV_VAR)
        os.environ[trabajo.ENV_VAR] = "/tmp/ref-de-prueba"
        try:
            self.assertEqual(trabajo.reference_dir(), Path("/tmp/ref-de-prueba"))
        finally:
            if anterior is None:
                del os.environ[trabajo.ENV_VAR]
            else:
                os.environ[trabajo.ENV_VAR] = anterior


class TestLaSiembra(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.destino = self.tmp / "reference"

    def test_sobre_un_directorio_VACIO_copia_lo_versionado(self):
        informe = trabajo.seed_reference_dir(self.destino, source=VERSIONADO)
        self.assertTrue((self.destino / manifest.MANIFEST_NAME).is_file())
        self.assertIn(manifest.MANIFEST_NAME, informe.copied)

    def test_y_copia_los_fixtures_que_SI_estan_en_git(self):
        trabajo.seed_reference_dir(self.destino, source=VERSIONADO)
        for nombre in ("NM_011170.3.fa", "NM_011170.3.gb", "rmsk_mouse.out", "rmsk_mouse.tbl"):
            self.assertTrue((self.destino / nombre).is_file(), nombre)

    def test_NO_pisa_lo_que_ya_hay(self):
        """Lo subido por el usuario manda sobre la copia de la imagen. Al reves, un
        redespliegue borraria el fichero bueno y lo dejaria en NOT_RUN sin decir nada."""
        self.destino.mkdir(parents=True)
        (self.destino / "NM_011170.3.fa").write_text("MIO", encoding="utf-8")
        informe = trabajo.seed_reference_dir(self.destino, source=VERSIONADO)
        self.assertEqual(
            (self.destino / "NM_011170.3.fa").read_text(encoding="utf-8"), "MIO"
        )
        self.assertIn("NM_011170.3.fa", informe.kept)

    def test_el_manifiesto_TAMPOCO_se_pisa(self):
        """Es el que lleva los md5 de lo subido: pisarlo es perder la procedencia."""
        self.destino.mkdir(parents=True)
        propio = (VERSIONADO / manifest.MANIFEST_NAME).read_text(encoding="utf-8")
        # La fila se MONTA con `entry_row`, no se teclea con tabuladores contados a
        # mano: al entrar las tres columnas de la anatomia, la version tecleada se
        # quedo en diez campos y el manifiesto dejo de parsearse. La leccion es la
        # misma que la del propio invariante de ancho de fila.
        fila = manifest.entry_row(
            manifest.ManifestEntry(
                name="subido.fa", filter_name="x", size=1, md5="0" * 32,
                date="2026-08-26", origin="mio",
            )
        )
        (self.destino / manifest.MANIFEST_NAME).write_text(
            propio + fila + "\n", encoding="utf-8",
        )
        trabajo.seed_reference_dir(self.destino, source=VERSIONADO)
        vuelto = manifest.load_manifest(self.destino / manifest.MANIFEST_NAME)
        self.assertIsNotNone(vuelto.find("subido.fa"))

    def test_sembrar_dos_veces_no_cambia_nada(self):
        trabajo.seed_reference_dir(self.destino, source=VERSIONADO)
        segunda = trabajo.seed_reference_dir(self.destino, source=VERSIONADO)
        self.assertEqual(segunda.copied, ())

    def test_el_resultado_queda_VALIDO_para_el_manifiesto(self):
        trabajo.seed_reference_dir(self.destino, source=VERSIONADO)
        estado = manifest.check_directory(self.destino)
        self.assertTrue(estado.results)

    def test_si_el_origen_no_existe_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            trabajo.seed_reference_dir(self.destino, source=self.tmp / "no-existe")


class TestLaInterfazUSA_EL_DIRECTORIO_DE_TRABAJO(unittest.TestCase):

    def test_la_pagina_ya_no_escribe_en_el_del_paquete(self):
        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertTrue("reference_dir()" in fuente, "la pagina no pide el de trabajo")
        self.assertFalse(
            "directory=PACKAGE_REFERENCE_DIR" in fuente,
            "la pagina sigue escribiendo en el directorio del paquete",
        )


if __name__ == "__main__":
    unittest.main()
