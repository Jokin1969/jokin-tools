"""La segunda vía entrega un FICHERO sin pasar por la descarga del navegador.

**El caso, y lo que se midió antes de escribir nada (errata nº 130).** Reportado el
2026-09-08 con tres observaciones a la vez: el botón rojo del export no descarga, el
icono de descarga de la tabla de Streamlit tampoco, y el bloque copiable SÍ funciona.

La lectura que se le dio —«el icono es cliente puro, sin pasar por el servidor, así que
el contenido llega a la página y no sale del navegador»— es correcta sobre el ORIGEN de
los bytes y **no separa los dos casos muertos**. Medido sobre el `bundle` de Streamlit
1.62.0 que instala el hub:

- `DownloadButton` termina en
  `createDownloadLinkElement({url, filename}).click()`, o sea un `<a download>`
  sintético;
- el icono de la tabla intenta `showSaveFilePicker` y, si falla, cae a
  `Blob` + `<a download>`.

**Los dos acaban en el mismo sitio: una pulsación sintética sobre un `<a download>`.**
El bloque copiable no —es texto en la página—, y es el único que funciona. O sea que lo
que comparten los dos muertos no es el transporte: es la maquinaria de descarga del
navegador.

De ahí esta vía: el mismo contenido servido por `/app/static/` con **`text/plain`**, que
el navegador PINTA en una pestaña en vez de entregárselo al gestor de descargas. Y se
abre con un enlace que pulsa una persona, no con un `click()` de un script.

**El sufijo `.txt` es el mecanismo entero y por eso lleva control adversario**: sin él,
`.tsv` sale como `text/tab-separated-values` y `.fa` como `application/octet-stream`, y
los dos vuelven a la maquinaria de descarga — que es justo lo que esta vía existe para
esquivar.
"""

from __future__ import annotations

import mimetypes
import re
import unittest
from pathlib import Path

from shmir_design import segunda_via
from shmir_design.errors import ShmirDesignError


class TestLaUrlLlevaElPrefijoDelMontaje(unittest.TestCase):
    def setUp(self):
        self.dir = Path(__file__).resolve().parent / "_tmp_segunda_via"

    def tearDown(self):
        if self.dir.exists():
            for hijo in self.dir.iterdir():
                hijo.unlink()
            self.dir.rmdir()

    def test_con_el_hub_delante_la_url_empieza_por_shmir(self):
        entrega = segunda_via.publish(
            "mouse_seleccionados.tsv", "a\tb\n1\t2\n",
            directory=self.dir, base_path="/shmir", inline=True
        )
        self.assertEqual(
            entrega["url"], "/shmir/app/static/mouse_seleccionados.tsv.txt"
        )

    def test_en_local_no_hay_prefijo_y_eso_es_la_VERDAD_no_un_defecto(self):
        entrega = segunda_via.publish(
            "mouse_seleccionados.tsv", "a\tb\n", directory=self.dir, base_path="", inline=True
        )
        self.assertEqual(entrega["url"], "/app/static/mouse_seleccionados.tsv.txt")

    def test_sin_declarar_el_prefijo_ABORTA(self):
        # Principio nº 58: el prefijo del montaje entra por parámetro y no tiene valor
        # por defecto. Con `/shmir` supuesto, la app en local daría un enlace roto; con
        # `''` supuesto, la del hub daría un 404 del hub. Las dos, en silencio.
        with self.assertRaises(TypeError):
            segunda_via.publish("x.tsv", "a", directory=self.dir)  # type: ignore[call-arg]

    def test_un_prefijo_que_no_empieza_por_barra_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            segunda_via.publish(
                "x.tsv", "a", directory=self.dir, base_path="shmir", inline=True
            )


class TestElPrefijoSeNORMALIZA(unittest.TestCase):
    """`server.baseUrlPath` se guarda tal cual se pasa: tres formas, un montaje."""

    def test_las_tres_formas_dan_el_mismo_prefijo(self):
        for crudo in ("/shmir", "shmir", "/shmir/", " shmir/ "):
            with self.subTest(crudo=crudo):
                self.assertEqual(segunda_via.mount_prefix(crudo), "/shmir")

    def test_en_local_sigue_siendo_vacio(self):
        for crudo in ("", "/", "   "):
            with self.subTest(crudo=crudo):
                self.assertEqual(segunda_via.mount_prefix(crudo), "")


class TestElNavegadorLoPINTAenVezDeDescargarlo(unittest.TestCase):
    """El sufijo `.txt` no es cosmético: es lo que decide qué hace el navegador."""

    def setUp(self):
        self.dir = Path(__file__).resolve().parent / "_tmp_segunda_via_tipo"

    def tearDown(self):
        if self.dir.exists():
            for hijo in self.dir.iterdir():
                hijo.unlink()
            self.dir.rmdir()

    def test_el_fichero_publicado_sale_como_text_plain(self):
        entrega = segunda_via.publish(
            "mouse_seleccionados.tsv", "a\tb\n", directory=self.dir, base_path="/shmir", inline=True
        )
        self.assertEqual(mimetypes.guess_type(entrega["fichero"])[0], "text/plain")

    def test_CONTROL_ADVERSARIO_sin_el_sufijo_volveria_a_la_descarga(self):
        # Si esto dejara de ser cierto, el sufijo no estaría haciendo nada y la vía
        # sería la misma que falla, con otro nombre.
        for nombre in ("mouse_seleccionados.tsv", "panel.fa", "panel.fasta"):
            with self.subTest(nombre=nombre):
                self.assertNotEqual(mimetypes.guess_type(nombre)[0], "text/plain")

    def test_CRUZADO_contra_la_funcion_que_lo_decide_de_verdad(self):
        # Principio nº 5: quien elige el `Content-Type` de `/app/static/` es Streamlit,
        # no `mimetypes`. Si algún día dejaran de coincidir, esta vía se rompería en
        # silencio — el fichero bajaría en vez de pintarse.
        try:
            from streamlit.web.server.component_file_utils import guess_content_type
        except ImportError:  # pragma: no cover
            # rule2-ok: Streamlit es dependencia SÓLO de la interfaz; el núcleo corre
            # sin ella. No se esconde ningún fallo — el motivo sale en el skip.
            self.skipTest("Streamlit no está instalado; es dependencia sólo de la UI")
        entrega = segunda_via.publish(
            "panel.fa", ">x\nACGT\n", directory=self.dir, base_path="/shmir", inline=True
        )
        self.assertEqual(guess_content_type(str(entrega["ruta"])), "text/plain")
        self.assertEqual(guess_content_type("/x/panel.fa"), "application/octet-stream")


class TestElContenidoYElNombreDeVerdad(unittest.TestCase):
    def setUp(self):
        self.dir = Path(__file__).resolve().parent / "_tmp_segunda_via_cont"

    def tearDown(self):
        if self.dir.exists():
            for hijo in self.dir.iterdir():
                hijo.unlink()
            self.dir.rmdir()

    def test_el_contenido_llega_INTACTO(self):
        texto = "# BUILD: abc123\ncandidato\testado\n3utr:60\tPASS\n"
        entrega = segunda_via.publish(
            "mouse_seleccionados.tsv", texto, directory=self.dir, base_path="/shmir", inline=True
        )
        self.assertEqual(entrega["ruta"].read_text(encoding="utf-8"), texto)
        self.assertEqual(entrega["bytes"], len(texto.encode("utf-8")))

    def test_dice_con_QUE_NOMBRE_hay_que_guardarlo(self):
        # El fichero servido lleva `.txt` para que se pinte; el que hace falta en disco
        # es el de verdad. Callarlo dejaría un `.txt` alimentando a SpliceAI.
        entrega = segunda_via.publish(
            "panel.fa", ">x\nACGT\n", directory=self.dir, base_path="/shmir", inline=True
        )
        self.assertEqual(entrega["guardar_como"], "panel.fa")

    def test_publicar_dos_veces_el_mismo_nombre_NO_acumula(self):
        for texto in ("uno\n", "dos\n"):
            entrega = segunda_via.publish(
                "x.tsv", texto, directory=self.dir, base_path="/shmir", inline=True
            )
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["x.tsv.txt"])
        self.assertEqual(entrega["ruta"].read_text(encoding="utf-8"), "dos\n")


class TestLoQueABORTA(unittest.TestCase):
    def setUp(self):
        self.dir = Path(__file__).resolve().parent / "_tmp_segunda_via_abort"

    def tearDown(self):
        if self.dir.exists():
            for hijo in self.dir.iterdir():
                hijo.unlink()
            self.dir.rmdir()

    def test_una_RUTA_en_el_nombre_se_cae_entera(self):
        # Misma regla que `presentation.upload_path`: sobrevive el NOMBRE, se cae todo
        # lo que va delante. Aquí el nombre lo pone la app, pero la regla no se relaja
        # por eso: es la que hace que no haya que acertar con la lista de formas de
        # escribir `..`.
        entrega = segunda_via.publish(
            "../../fuera.tsv", "a\n", directory=self.dir, base_path="/shmir", inline=True
        )
        self.assertEqual(entrega["ruta"].parent.resolve(), self.dir.resolve())
        self.assertEqual(entrega["url"], "/shmir/app/static/fuera.tsv.txt")

    def test_un_nombre_que_NO_es_una_cadena_ABORTA_en_vez_de_convertirse(self):
        # Errata nº 50: `str(objeto)` fabrica un nombre de su `repr`, con la forma
        # correcta y sin ningún error.
        with self.assertRaises(ShmirDesignError):
            segunda_via.publish(
                Path("x.tsv"), "a\n", directory=self.dir, base_path="/shmir", inline=True
            )

    def test_un_directorio_que_no_se_puede_crear_ABORTA_con_el_MOTIVO(self):
        estorbo = Path(__file__).resolve().parent / "_tmp_segunda_via_fichero"
        estorbo.write_text("no soy un directorio\n", encoding="utf-8")
        try:
            with self.assertRaises(ShmirDesignError) as cm:
                segunda_via.publish(
                    "x.tsv", "a\n", directory=estorbo / "dentro", base_path="/shmir", inline=True
                )
            self.assertIn(str(estorbo / "dentro"), str(cm.exception))
        finally:
            estorbo.unlink()

    def test_lo_que_no_cabe_en_la_ruta_estatica_ABORTA_en_vez_de_dar_un_404(self):
        # El tope es de Streamlit (`MAX_APP_STATIC_FILE_SIZE`): por encima devuelve 404,
        # o sea una pestaña vacía. Decirlo aquí es la diferencia entre «no cabe» y «la
        # segunda vía tampoco funciona».
        with self.assertRaises(ShmirDesignError) as cm:
            segunda_via.publish(
                "x.tsv", "a", directory=self.dir, base_path="/shmir", inline=True,
                max_bytes=0,
            )
        self.assertIn("404", str(cm.exception))


class TestLaViaNoCOMPARTEmecanismo(unittest.TestCase):
    """Una vía y su alternativa no pueden compartir el mecanismo que falla."""

    def test_el_modulo_no_llama_a_ninguna_descarga_de_streamlit(self):
        # La LLAMADA, no la mención: el docstring NOMBRA `createDownloadLinkElement`
        # porque es la evidencia medida, y un guardia que muerda ahí es un guardia con
        # falsos positivos — o sea uno que alguien acaba apagando. Y el módulo es del
        # NÚCLEO, así que tampoco puede importar Streamlit (regla 6).
        fuente = Path(segunda_via.__file__).read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\bdownload_button\s*\(", fuente))
        self.assertIsNone(re.search(r"^\s*(import|from)\s+streamlit", fuente, re.M))

    def test_CONTROL_del_guardia_anterior(self):
        # Sin esto, «no llama a ninguna descarga» y «el detector no mira nada» dan el
        # mismo verde (errata nº 29).
        self.assertIsNotNone(re.search(r"\bdownload_button\s*\(", "st.download_button(x)"))
        self.assertIsNotNone(
            re.search(r"^\s*(import|from)\s+streamlit", "import streamlit as st", re.M)
        )

    def test_el_motivo_dice_lo_que_se_MIDIO_y_no_lo_que_se_supone(self):
        # Principio nº 3: el texto que acompaña a esta vía no puede afirmar una causa
        # de la errata nº 130 —que sigue SIN ASIGNAR—, sino lo que sí está medido.
        motivo = segunda_via.WHY_A_SECOND_ROUTE
        self.assertIn("sin causa asignada", motivo.lower())
        for adivinanza in ("casi seguro", "probablemente", "lo más probable"):
            self.assertNotIn(adivinanza, motivo.lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
