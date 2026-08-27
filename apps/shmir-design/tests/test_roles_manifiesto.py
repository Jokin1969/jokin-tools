"""Tests de la correspondencia fichero → filtro (mejora de operatividad 1).

De las 64 flags del CLI, 31 solo servian para señalar un fichero de referencia y repetir
su procedencia — nombre, version y md5 que el manifiesto YA registra. Peor que verboso:
se podia pasar `--refseq-version 2024` apuntando a un fichero de 2026 y nadie se
enteraba, porque la version se teclea aparte del fichero.

`ROLES` es el unico sitio donde vive esa correspondencia. Va en codigo —no como septima
columna del manifiesto— porque el formato de seis columnas esta fijado, y porque una
correspondencia editable desde un fichero de datos permitiria reasignar un fichero a otro
filtro sin que se vea en el diff.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path

from shmir_design.guide_fixture import fixture_path
from shmir_design.manifest import (
    LEGACY_COLUMNS,
    MANIFEST_NAME,
    ROLES,
    EntryStatus,
    check_directory,
    load_manifest,
    role_of,
    roles_available,
)

DIRECTORIO = fixture_path().parent


class TestLaTablaDeRoles(unittest.TestCase):

    #: El unico rol cuyo `replaces` esta VACIO, y con motivo: la tabla de PolyA_DB
    #: nunca fue alcanzable por una flag — estaba CABLEADA en `apa.POLYA_DB_PRNP`. No
    #: sustituye a ninguna opcion porque no habia ninguna: sustituye a una constante.
    #: Se declara aqui en vez de inventarle una flag que no existio.
    SIN_FLAG_PREVIA = {"polyadb"}

    def test_cada_rol_declara_fichero_y_para_que_sirve(self):
        for rol in ROLES:
            self.assertTrue(rol.filename, rol)
            self.assertTrue(rol.what, rol.filename)
            if rol.role not in self.SIN_FLAG_PREVIA:
                self.assertTrue(rol.replaces, rol.filename)

    def test_el_rol_SIN_flag_previa_es_el_declarado_y_no_otro(self):
        # Una excepcion que crece sin que nadie la mire deja de ser una excepcion.
        vacios = {r.role for r in ROLES if not r.replaces}
        self.assertEqual(vacios, self.SIN_FLAG_PREVIA)

    def test_los_identificadores_no_se_repiten(self):
        ids = [r.role for r in ROLES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_los_ficheros_no_se_repiten(self):
        nombres = [r.filename for r in ROLES]
        self.assertEqual(len(nombres), len(set(nombres)))

    def test_todo_rol_tiene_su_linea_en_el_manifiesto(self):
        """Si alguien añade un rol y olvida el manifiesto, esto lo caza."""
        manifiesto = load_manifest(DIRECTORIO / MANIFEST_NAME)
        for rol in ROLES:
            with self.subTest(fichero=rol.filename):
                manifiesto.entry(rol.filename)

    def test_role_of_encuentra_el_rol_por_nombre_de_fichero(self):
        self.assertEqual(role_of("refseq_rna.fa").role, "refseq")

    def test_un_fichero_sin_rol_devuelve_None_en_vez_de_adivinar(self):
        self.assertIsNone(role_of("no_existe.fa"))

    def test_cada_rol_dice_que_flags_sustituye(self):
        self.assertIn("--refseq", role_of("refseq_rna.fa").replaces)

    def test_las_flags_sustituidas_son_muchas(self):
        """El argumento de la mejora: hay bastante que colapsar."""
        self.assertGreaterEqual(sum(len(r.replaces) for r in ROLES), 20)


class TestQueSePuedeUsarDelDirectorio(unittest.TestCase):

    def _directorio(self, filas: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        (d / MANIFEST_NAME).write_text(
            "\t".join(LEGACY_COLUMNS) + "\n" + filas, encoding="utf-8"
        )
        return d

    def test_un_fichero_ausente_no_aporta_su_rol(self):
        d = self._directorio("refseq_rna.fa\tespecificidad\t\t\t\tmanual\n")
        self.assertEqual(roles_available(check_directory(d)), ())

    def test_solo_entran_los_que_estan_en_OK(self):
        """SIN_REGISTRAR no vale: sin md5 no hay version, y sin version no hay
        procedencia que poner en el informe."""
        datos = b">x\nACGT\n"
        md5 = hashlib.md5(datos, usedforsecurity=False).hexdigest()
        d = self._directorio(
            f"refseq_rna.fa\tespecificidad\t6\t{md5}\t2026-01-01\tmanual\n"
            "mature.fa\tseed\t\t\t\tmiRBase\n"
        )
        (d / "refseq_rna.fa").write_bytes(datos)
        (d / "mature.fa").write_bytes(datos)
        disponibles = {r.filename for r in roles_available(check_directory(d))}
        self.assertIn("refseq_rna.fa", disponibles)
        self.assertNotIn("mature.fa", disponibles)

    def test_un_fichero_que_no_es_el_que_dice_ser_no_entra(self):
        d = self._directorio(
            f"refseq_rna.fa\tespecificidad\t6\t{'0' * 32}\t2026-01-01\tmanual\n"
        )
        (d / "refseq_rna.fa").write_bytes(b">x\nACGT\n")
        self.assertEqual(roles_available(check_directory(d)), ())

    def test_en_el_repositorio_de_verdad_no_hay_ninguno_todavia(self):
        estado = check_directory(DIRECTORIO)
        ausentes = {
            r.entry.name for r in estado.results if r.status is EntryStatus.AUSENTE
        }
        for rol in roles_available(estado):
            self.assertNotIn(rol.filename, ausentes)


if __name__ == "__main__":
    unittest.main()
