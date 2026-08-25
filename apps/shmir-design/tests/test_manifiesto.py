"""Tests del manifiesto de `data/reference/` (tanda C).

Regla 5: escritos antes que `shmir_design/manifest.py`.

Para que existe: sin un registro versionado de QUE fichero se uso y con que checksum,
una corrida de hace tres meses no es reproducible y un veredicto no es auditable dentro
de un año. El manifiesto se versiona en git; los FASTA NO — un RefSeq RNA completo no
tiene por que entrar en el repositorio.

Una linea por fichero: nombre, filtro al que sirve, tamaño, md5, fecha y origen.
"""

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design.errors import ShmirDesignError
from shmir_design.manifest import (
    MANIFEST_COLUMNS,
    MANIFEST_NAME,
    EntryStatus,
    Manifest,
    ManifestEntry,
    check_directory,
    load_manifest,
    parse_manifest,
)

CABECERA = "\t".join(MANIFEST_COLUMNS)

TABLA = f"""\
# Manifiesto de data/reference/. Versionado en git; los ficheros NO.
{CABECERA}
NM_011170.3.fa\ttranscrito de referencia (raton)\t2249\t44fb8cd80883844cde5e53bbc367b176\t2026-08-25\tNCBI efetch, descarga manual
mature.fa\tcolision de seed (nivel aviso)\t\t\t\tmiRBase, descarga manual
"""


def _md5(datos: bytes) -> str:
    return hashlib.md5(datos, usedforsecurity=False).hexdigest()


class TestFormato(unittest.TestCase):

    def test_las_columnas_son_las_pedidas(self):
        for columna in ("nombre", "filtro", "tamaño", "md5", "fecha", "origen"):
            self.assertIn(columna, MANIFEST_COLUMNS)

    def test_el_fichero_se_llama_manifest_tsv(self):
        self.assertEqual(MANIFEST_NAME, "manifest.tsv")

    def test_lee_las_dos_entradas(self):
        manifiesto = parse_manifest(TABLA, source="sonda")
        self.assertEqual(len(manifiesto.entries), 2)

    def test_ignora_los_comentarios(self):
        self.assertEqual(len(parse_manifest(TABLA, source="s").entries), 2)

    def test_una_entrada_sin_md5_es_valida_pero_queda_sin_registrar(self):
        manifiesto = parse_manifest(TABLA, source="s")
        self.assertEqual(manifiesto.entry("mature.fa").md5, "")

    def test_guarda_el_origen(self):
        manifiesto = parse_manifest(TABLA, source="s")
        self.assertIn("NCBI", manifiesto.entry("NM_011170.3.fa").origin)

    def test_guarda_el_filtro_al_que_sirve(self):
        manifiesto = parse_manifest(TABLA, source="s")
        self.assertIn("seed", manifiesto.entry("mature.fa").filter_name)

    def test_una_cabecera_distinta_aborta(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_manifest("nombre\tmd5\nx\ty\n", source="s")
        self.assertIn("cabecera", str(ctx.exception).lower())

    def test_un_manifiesto_vacio_aborta(self):
        with self.assertRaises(ShmirDesignError):
            parse_manifest(f"{CABECERA}\n", source="s")

    def test_un_nombre_repetido_aborta(self):
        doble = TABLA + "NM_011170.3.fa\totra cosa\t1\tx\t2026-01-01\tinventado\n"
        with self.assertRaises(ShmirDesignError) as ctx:
            parse_manifest(doble, source="s")
        self.assertIn("NM_011170.3.fa", str(ctx.exception))

    def test_un_md5_que_no_es_hexadecimal_aborta(self):
        malo = TABLA.replace("44fb8cd80883844cde5e53bbc367b176", "no-es-un-md5")
        with self.assertRaises(ShmirDesignError):
            parse_manifest(malo, source="s")

    def test_un_tamaño_no_numerico_aborta(self):
        malo = TABLA.replace("\t2249\t", "\tmucho\t")
        with self.assertRaises(ShmirDesignError):
            parse_manifest(malo, source="s")

    def test_una_fila_corta_aborta_en_vez_de_saltarse(self):
        with self.assertRaises(ShmirDesignError):
            parse_manifest(f"{CABECERA}\nsolo_nombre\n", source="s")

    def test_pedir_una_entrada_que_no_esta_aborta(self):
        with self.assertRaises(KeyError):
            parse_manifest(TABLA, source="s").entry("no_existe.fa")


class TestEstadoDelDirectorio(unittest.TestCase):

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _preparar(self, contenido: bytes | None = b">x\nACGT\n"):
        directorio = Path(self._tmp.name)
        (directorio / MANIFEST_NAME).write_text(TABLA, encoding="utf-8")
        if contenido is not None:
            (directorio / "NM_011170.3.fa").write_bytes(contenido)
        return directorio

    def test_un_fichero_ausente_sale_AUSENTE(self):
        estado = check_directory(self._preparar(contenido=None))
        self.assertIs(estado.status_of("NM_011170.3.fa"), EntryStatus.AUSENTE)

    def test_un_fichero_presente_con_md5_distinto_NO_COINCIDE(self):
        estado = check_directory(self._preparar())
        self.assertIs(estado.status_of("NM_011170.3.fa"), EntryStatus.NO_COINCIDE)

    def test_un_fichero_presente_con_el_md5_bueno_sale_OK(self):
        directorio = self._preparar(contenido=None)
        datos = b"contenido de prueba"
        (directorio / "NM_011170.3.fa").write_bytes(datos)
        tabla = TABLA.replace("44fb8cd80883844cde5e53bbc367b176", _md5(datos))
        tabla = tabla.replace("\t2249\t", f"\t{len(datos)}\t")
        (directorio / MANIFEST_NAME).write_text(tabla, encoding="utf-8")
        estado = check_directory(directorio)
        self.assertIs(estado.status_of("NM_011170.3.fa"), EntryStatus.OK)

    def test_un_fichero_sin_md5_en_el_manifiesto_sale_SIN_REGISTRAR(self):
        directorio = self._preparar()
        (directorio / "mature.fa").write_bytes(b"lo que sea")
        estado = check_directory(directorio)
        self.assertIs(estado.status_of("mature.fa"), EntryStatus.SIN_REGISTRAR)

    def test_el_SIN_REGISTRAR_trae_el_md5_calculado_para_apuntarlo(self):
        directorio = self._preparar()
        datos = b"lo que sea"
        (directorio / "mature.fa").write_bytes(datos)
        estado = check_directory(directorio)
        self.assertEqual(estado.result_of("mature.fa").computed_md5, _md5(datos))

    def test_un_fichero_de_mas_se_avisa_pero_no_es_un_error(self):
        directorio = self._preparar()
        (directorio / "sobrante.fa").write_bytes(b">x\n")
        estado = check_directory(directorio)
        self.assertIn("sobrante.fa", estado.unlisted)

    def test_el_propio_manifiesto_no_cuenta_como_sobrante(self):
        estado = check_directory(self._preparar())
        self.assertNotIn(MANIFEST_NAME, estado.unlisted)

    def test_los_markdown_de_procedencia_tampoco(self):
        directorio = self._preparar()
        (directorio / "PROCEDENCIA.md").write_text("x", encoding="utf-8")
        self.assertNotIn("PROCEDENCIA.md", check_directory(directorio).unlisted)

    def test_sin_manifiesto_aborta_diciendo_donde_deberia_estar(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ShmirDesignError) as ctx:
                check_directory(Path(tmp))
            self.assertIn(MANIFEST_NAME, str(ctx.exception))


class TestQueFiltrosPuedenCorrer(unittest.TestCase):

    def test_un_fichero_OK_deja_correr_su_filtro(self):
        entrada = ManifestEntry(
            name="x.fa", filter_name="especificidad", size=4, md5="0" * 32,
            date="2026-01-01", origin="prueba",
        )
        self.assertTrue(entrada.usable(EntryStatus.OK))

    def test_un_fichero_AUSENTE_no(self):
        entrada = ManifestEntry(
            name="x.fa", filter_name="especificidad", size=0, md5="",
            date="", origin="prueba",
        )
        self.assertFalse(entrada.usable(EntryStatus.AUSENTE))

    def test_un_NO_COINCIDE_tampoco_aunque_el_fichero_este(self):
        entrada = ManifestEntry(
            name="x.fa", filter_name="especificidad", size=4, md5="0" * 32,
            date="", origin="prueba",
        )
        self.assertFalse(entrada.usable(EntryStatus.NO_COINCIDE))

    def test_un_SIN_REGISTRAR_se_puede_usar_pero_no_es_auditable(self):
        entrada = ManifestEntry(
            name="x.fa", filter_name="especificidad", size=0, md5="",
            date="", origin="prueba",
        )
        self.assertTrue(entrada.usable(EntryStatus.SIN_REGISTRAR))

    def test_el_resumen_separa_los_que_pueden_correr_de_los_que_no(self):
        with TemporaryDirectory() as tmp:
            directorio = Path(tmp)
            (directorio / MANIFEST_NAME).write_text(TABLA, encoding="utf-8")
            estado = check_directory(directorio)
        self.assertEqual(estado.runnable, ())
        self.assertEqual(len(estado.not_run), 2)

    def test_el_texto_dice_que_filtro_queda_en_NOT_RUN(self):
        with TemporaryDirectory() as tmp:
            directorio = Path(tmp)
            (directorio / MANIFEST_NAME).write_text(TABLA, encoding="utf-8")
            texto = check_directory(directorio).format_text()
        self.assertIn("NOT_RUN", texto)
        self.assertIn("colision de seed", texto)

    def test_el_texto_es_una_tabla_con_una_fila_por_fichero(self):
        with TemporaryDirectory() as tmp:
            directorio = Path(tmp)
            (directorio / MANIFEST_NAME).write_text(TABLA, encoding="utf-8")
            texto = check_directory(directorio).format_text()
        self.assertIn("NM_011170.3.fa", texto)
        self.assertIn("mature.fa", texto)


class TestLineasParaElInforme(unittest.TestCase):
    """Cada informe copia las lineas del manifiesto de los ficheros que USO."""

    def test_devuelve_solo_las_pedidas(self):
        manifiesto = parse_manifest(TABLA, source="s")
        lineas = manifiesto.provenance_lines(["mature.fa"])
        self.assertEqual(len(lineas), 1)
        self.assertIn("mature.fa", lineas[0])

    def test_la_linea_lleva_md5_fecha_y_origen(self):
        manifiesto = parse_manifest(TABLA, source="s")
        linea = manifiesto.provenance_lines(["NM_011170.3.fa"])[0]
        for trozo in ("44fb8cd8", "2026-08-25", "NCBI"):
            self.assertIn(trozo, linea)

    def test_pedir_un_fichero_que_no_esta_en_el_manifiesto_lo_dice(self):
        manifiesto = parse_manifest(TABLA, source="s")
        linea = manifiesto.provenance_lines(["fantasma.fa"])[0]
        self.assertIn("NO ESTA EN EL MANIFIESTO", linea)

    def test_sin_ficheros_usados_lo_dice_en_vez_de_callar(self):
        manifiesto = parse_manifest(TABLA, source="s")
        self.assertTrue(manifiesto.provenance_lines([]))


class TestElManifiestoDelRepositorio(unittest.TestCase):
    """El manifiesto de verdad tiene que existir y cuadrar con los md5 del codigo."""

    RUTA = Path(__file__).resolve().parent.parent / "data" / "reference" / MANIFEST_NAME

    def test_existe(self):
        self.assertTrue(self.RUTA.is_file(), self.RUTA)

    def test_se_parsea(self):
        self.assertTrue(load_manifest(self.RUTA).entries)

    def test_el_manifiesto_no_copia_el_md5_canonico_en_la_columna_del_fichero(self):
        """Son DOS checksums distintos y confundirlos daria NO_COINCIDE para siempre.

        El md5 de la tabla es el del fichero en disco; el de `reference.py` es el de la
        secuencia canonica (mayusculas, sin cabecera, sin saltos). Copiar uno en el otro
        haria que el fichero bueno se rechazara.
        """
        from shmir_design.reference import REFERENCES, fixture_filename

        manifiesto = load_manifest(self.RUTA)
        canonicos = {r.md5 for r in REFERENCES.values()}
        for referencia in REFERENCES.values():
            entrada = manifiesto.entry(fixture_filename(referencia))
            self.assertNotIn(entrada.md5, canonicos, referencia.accession)

    def test_pero_el_origen_deja_escrito_el_md5_canonico(self):
        """El vinculo entre los dos checksums tiene que quedar documentado."""
        from shmir_design.reference import REFERENCES, fixture_filename

        manifiesto = load_manifest(self.RUTA)
        for referencia in REFERENCES.values():
            entrada = manifiesto.entry(fixture_filename(referencia))
            self.assertIn(referencia.md5, entrada.origin, referencia.accession)

    def test_hay_una_entrada_por_cada_fichero_que_el_proyecto_espera(self):
        manifiesto = load_manifest(self.RUTA)
        for nombre in ("mature.fa", "rmsk_mouse.out", "aav_casete.fa"):
            manifiesto.entry(nombre)  # aborta si falta

    def test_toda_entrada_declara_a_que_filtro_sirve(self):
        for entrada in load_manifest(self.RUTA).entries:
            self.assertTrue(entrada.filter_name, entrada.name)

    def test_toda_entrada_declara_su_origen(self):
        for entrada in load_manifest(self.RUTA).entries:
            self.assertTrue(entrada.origin, entrada.name)


if __name__ == "__main__":
    unittest.main()


class TestIntegracionConElDiseño(unittest.TestCase):
    """La tabla de estado sale ANTES de correr, y la procedencia va en el informe."""

    def _correr(self, extra=None):
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO

        from tools.design import main

        tmp = Path(tempfile.mkdtemp())
        fa = tmp / "sonda.fa"
        fa.write_text(">sonda\n" + "GCGTCAGTACGATCGAATTACT" * 20 + "\n")
        salida = StringIO()
        with redirect_stdout(salida), redirect_stderr(salida):
            codigo = main(
                ["--fasta", str(fa), "--out", str(tmp), "--region", "3utr"]
                + (extra or [])
            )
        return codigo, salida.getvalue(), tmp

    def test_la_tabla_de_estado_se_imprime_antes_de_correr(self):
        codigo, salida, _ = self._correr()
        self.assertEqual(codigo, 0, salida)
        self.assertIn("── Ficheros de referencia", salida)

    def test_la_tabla_sale_antes_que_el_informe(self):
        _, salida, _ = self._correr()
        self.assertLess(
            salida.index("── Ficheros de referencia"),
            salida.index("═══ Diseño de shmiR"),
        )

    def test_el_informe_lleva_la_procedencia_de_lo_que_uso(self):
        _, salida, tmp = self._correr()
        texto = list(tmp.glob("*informe*.txt"))[0].read_text(encoding="utf-8")
        self.assertIn("Procedencia de los ficheros de referencia usados", texto)

    def test_sin_ficheros_usados_el_informe_lo_dice(self):
        _, _, tmp = self._correr()
        texto = list(tmp.glob("*informe*.txt"))[0].read_text(encoding="utf-8")
        self.assertIn("No se uso ningun fichero de referencia", texto)

    def test_un_directorio_sin_manifiesto_aborta_el_diseño(self):
        import tempfile

        with tempfile.TemporaryDirectory() as vacio:
            codigo, salida, _ = self._correr(["--datos", vacio])
        self.assertEqual(codigo, 2)
        self.assertIn("--sin-manifiesto", salida)

    def test_y_con_sin_manifiesto_sigue_pero_avisando(self):
        import tempfile

        with tempfile.TemporaryDirectory() as vacio:
            codigo, salida, tmp = self._correr(
                ["--datos", vacio, "--sin-manifiesto"]
            )
        self.assertEqual(codigo, 0, salida)
        texto = list(tmp.glob("*informe*.txt"))[0].read_text(encoding="utf-8")
        self.assertIn("NO es reproducible", texto)
