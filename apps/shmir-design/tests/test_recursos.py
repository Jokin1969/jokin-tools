"""Tests del cargador de recursos desde el manifiesto (mejora 3).

`--usar-manifiesto` existe en el CLI, pero la interfaz no tenia forma de llegar a los
ficheros de referencia: le pasaba tres de los catorce parametros de `tile_utr`, asi que
el semaforo verde era estructuralmente inalcanzable desde el navegador y el generador de
bloques nunca podia comprobar `hits_transgen`.

Esto es el mismo cableado, pero devolviendo los objetos ya cargados en vez de rellenar
argumentos de linea de comandos, para que la pagina no tenga que saber que cargador va
con cada fichero.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.manifest import (
    LEGACY_COLUMNS,
    MANIFEST_COLUMNS,
    MANIFEST_NAME,
    ROLES,
)
from shmir_design.resources import LOADERS, ResourceSet, load_from_manifest

SONDA = "GCGTCAGTACGATCGAATTACT" * 20
CASETE = "GGCCATACTAGCATCGGATCAG" * 8


class TestCadaRolTieneCargador(unittest.TestCase):

    def test_no_falta_ninguno(self):
        self.assertEqual({r.role for r in ROLES}, set(LOADERS))

    def test_ni_sobra_ninguno(self):
        for role in LOADERS:
            self.assertIn(role, {r.role for r in ROLES})


class TestCarga(unittest.TestCase):

    def _directorio(self, ficheros: dict[str, str]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        filas = []
        for nombre, contenido in ficheros.items():
            (d / nombre).write_text(contenido, encoding="utf-8")
            datos = (d / nombre).read_bytes()
            md5 = hashlib.md5(datos, usedforsecurity=False).hexdigest()
            filas.append(
                f"{nombre}\tprueba\t{len(datos)}\t{md5}\t2026-08-25\tpuesto por el test\n"
            )
        (d / MANIFEST_NAME).write_text(
            "\t".join(LEGACY_COLUMNS) + "\n" + "".join(filas), encoding="utf-8"
        )
        return d

    def test_un_manifiesto_con_todo_ausente_no_carga_nada_y_no_revienta(self):
        """Un manifiesto SIN filas es otra cosa y ya aborta: eso no cambia."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        (d / MANIFEST_NAME).write_text(
            "\t".join(LEGACY_COLUMNS) + "\n"
            "aav_casete.fa\ttransgen\t\t\t\tno descargado todavia\n",
            encoding="utf-8",
        )
        recursos = load_from_manifest(d)
        self.assertIsInstance(recursos, ResourceSet)
        self.assertEqual(recursos.connected, ())

    def test_carga_el_casete_del_transgen(self):
        d = self._directorio({"aav_casete.fa": ">c\n" + CASETE + "\n"})
        recursos = load_from_manifest(d)
        self.assertIsNotNone(recursos.transgene_db)
        self.assertIn("aav_casete.fa", recursos.connected)

    def test_la_version_sale_del_manifiesto(self):
        d = self._directorio({"aav_casete.fa": ">c\n" + CASETE + "\n"})
        self.assertIn("2026-08-25", load_from_manifest(d).transgene_db.provenance)

    def test_el_refseq_necesita_el_gen_diana(self):
        d = self._directorio({"refseq_rna.fa": ">diana\n" + SONDA + "\n"})
        recursos = load_from_manifest(d)
        self.assertIsNone(recursos.specificity_db)
        self.assertTrue(any("target" in n for n in recursos.notes))

    def test_con_gen_diana_si_lo_carga(self):
        d = self._directorio({"refseq_rna.fa": ">diana\n" + SONDA + "\n"})
        recursos = load_from_manifest(d, target="diana")
        self.assertIsNotNone(recursos.specificity_db)
        self.assertEqual(recursos.specificity_target, "diana")

    def test_un_fichero_sin_md5_no_se_carga(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        (d / "aav_casete.fa").write_text(">c\n" + CASETE + "\n", encoding="utf-8")
        (d / MANIFEST_NAME).write_text(
            "\t".join(LEGACY_COLUMNS) + "\naav_casete.fa\tt\t\t\t\tsin registrar\n",
            encoding="utf-8",
        )
        recursos = load_from_manifest(d)
        self.assertIsNone(recursos.transgene_db)

    def test_sin_manifiesto_aborta_diciendo_donde_deberia_estar(self):
        with tempfile.TemporaryDirectory() as vacio:
            with self.assertRaises(ShmirDesignError) as ctx:
                load_from_manifest(vacio)
            self.assertIn(MANIFEST_NAME, str(ctx.exception))

    def test_el_estado_del_directorio_viaja_con_los_recursos(self):
        d = self._directorio({"aav_casete.fa": ">c\n" + CASETE + "\n"})
        self.assertIsNotNone(load_from_manifest(d).status)

    def test_las_notas_dicen_que_se_conecto(self):
        d = self._directorio({"aav_casete.fa": ">c\n" + CASETE + "\n"})
        self.assertTrue(load_from_manifest(d).format_text())


class TestLoQueSeLePuedePasarATileUtr(unittest.TestCase):

    def test_los_campos_son_los_parametros_de_tile_utr(self):
        import inspect

        from shmir_design.tiling import tile_utr

        parametros = set(inspect.signature(tile_utr).parameters)
        for campo in (
            "specificity_db", "specificity_target", "transgene_db", "mature",
            "abundance", "utr3_set", "expression", "apa_sites", "mask",
        ):
            self.assertIn(campo, parametros, campo)
            self.assertIn(campo, ResourceSet.__dataclass_fields__, campo)

    def test_as_kwargs_no_incluye_lo_que_no_es_de_tile_utr(self):
        recursos = ResourceSet()
        for clave in recursos.as_kwargs():
            self.assertNotIn(clave, ("connected", "notes", "status"))


if __name__ == "__main__":
    unittest.main()
