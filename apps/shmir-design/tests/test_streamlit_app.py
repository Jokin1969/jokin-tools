"""Comprobacion de que la interfaz arranca y no toma decisiones por su cuenta.

La logica se prueba en `test_presentation.py`; aqui solo se verifica que el script se
ejecuta sin excepciones, que los umbrales salen con sus valores por defecto visibles y
que sin ficheros no se pinta ningun resultado.

Se salta de forma visible si Streamlit no esta instalado: el nucleo no depende de el.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shmir_design.external_score import EXTERNAL_TOOLS  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest

    STREAMLIT = True
except ImportError:  # rule2-ok: ausencia de una dependencia OPCIONAL de la interfaz.
    # No se traga ningun fallo: el motivo se enseña en el mensaje del skip y el nucleo
    # sigue siendo stdlib pura.
    STREAMLIT = False

APP = Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no esta instalado (pip install -r requirements-ui.txt)")
class TestArranque(unittest.TestCase):

    def run_app(self):
        app = AppTest.from_file(str(APP), default_timeout=60).run()
        return app

    def test_arranca_sin_excepciones(self):
        app = self.run_app()
        self.assertEqual(list(app.exception), [])

    def test_lo_PRIMERO_que_pide_es_la_especie(self):
        """Antes pedia el FASTA y la especie iba en una caja de texto con «modelo».

        El orden importa: sin especie no se sabe que ficheros hacen falta ni se puede
        comprobar que los que hay son de esta especie.
        """
        app = self.run_app()
        textos = " ".join(info.value for info in app.info)
        self.assertIn("Elige una especie", textos)

    def test_y_el_FASTA_se_pide_DESPUES_de_elegirla(self):
        app = self.run_app()
        app.selectbox[0].set_value("Mus musculus").run()
        textos = " ".join(info.value for info in app.info)
        self.assertIn("FASTA", textos)

    def test_los_umbrales_muestran_su_valor_por_defecto(self):
        app = self.run_app()
        etiquetas = " ".join(widget.label for widget in app.sidebar.number_input)
        for esperado in ("GC mínimo (por defecto: 0.3", "Homopolímero máximo (por defecto: 3)",
                         "Asimetría mínima, kcal/mol (por defecto: 0.5)",
                         "Candidatos por especie (por defecto: 6)",
                         "Espaciado mínimo entre sitios, nt (por defecto: 50)"):
            with self.subTest(esperado):
                self.assertIn(esperado, etiquetas)

    def test_los_umbrales_arrancan_en_su_valor_por_defecto(self):
        app = self.run_app()
        valores = {w.label.split(" (")[0]: w.value for w in app.sidebar.number_input}
        self.assertAlmostEqual(valores["GC mínimo"], 0.30)
        self.assertAlmostEqual(valores["GC máximo"], 0.52)
        self.assertEqual(valores["Homopolímero máximo"], 3)
        self.assertEqual(valores["Candidatos por especie"], 6)
        self.assertEqual(valores["Espaciado mínimo entre sitios, nt"], 50)


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no esta instalado (pip install -r requirements-ui.txt)")
class TestFicherosDeReferencia(unittest.TestCase):
    """El panel de la barra lateral, y la casilla global que ya no existe.

    La casilla «Usar los de `data/reference/`» era una TRAMPA: su unico efecto posible al
    desmarcarla era dejar todos los filtros con fichero en NOT_RUN sin decir por que. Y
    la mitad de los ficheros no se podian subir por la interfaz — habia que depositarlos
    a mano en un directorio del repositorio, que es justo lo que quien usa esta app no
    conoce. Estos tests fijan las dos cosas.
    """

    def run_app(self, especie="Mus musculus"):
        app = AppTest.from_file(str(APP), default_timeout=60).run()
        if especie is not None:
            app.selectbox[0].set_value(especie).run()
        return app

    def test_la_casilla_GLOBAL_ya_no_existe(self):
        app = self.run_app()
        etiquetas = [w.label for w in app.sidebar.checkbox]
        self.assertNotIn("Usar los de data/reference/", etiquetas)

    def test_siguen_los_dos_controles_que_SI_son_decisiones(self):
        app = self.run_app()
        etiquetas = [w.label for w in app.sidebar.checkbox]
        etiquetas += [w.label for w in app.sidebar.text_input]
        for esperado in ("Gen diana (accession)", "Calcular accesibilidad (lento)"):
            with self.subTest(esperado):
                self.assertIn(esperado, etiquetas)

    def test_la_accesibilidad_arranca_apagada(self):
        app = self.run_app()
        valores = {w.label: w.value for w in app.sidebar.checkbox}
        self.assertFalse(valores["Calcular accesibilidad (lento)"])

    def test_el_gen_diana_arranca_vacio(self):
        # Si trajera un accession por defecto, la especificidad se correria contra una
        # diana que nadie ha declarado. Vacio significa vacio.
        app = self.run_app()
        valores = {w.label: w.value for w in app.sidebar.text_input}
        self.assertEqual(valores["Gen diana (accession)"], "")

    def test_sin_especie_el_panel_dice_que_hay_que_elegirla(self):
        app = self.run_app(especie=None)
        textos = " ".join(c.value for c in app.sidebar.caption)
        self.assertIn("Elige una especie", textos)

    def test_con_especie_sale_un_HUECO_DE_SUBIDA_por_fichero(self):
        app = self.run_app()
        etiquetas = [w.label for w in app.sidebar.get("file_uploader")]
        for esperado in ("Subir rmsk_mouse.out", "Subir rmsk_mouse.tbl",
                         "Subir mature.fa", "Subir refseq_rna.fa",
                         "Subir transcriptoma_3utr.fa"):
            with self.subTest(esperado):
                self.assertIn(esperado, etiquetas)

    def test_elegir_OTRA_ESPECIE_explica_los_frentes_ANTES_de_teclear_el_nombre(self):
        """La pregunta que se contesta es «¿me sirve esta app para mi especie?».

        Contestarla despues de teclear el nombre es no contestarla.
        """
        app = self.run_app(especie="otra especie (no declarada)")
        avisos = " ".join(w.value for w in app.warning)
        self.assertIn("NO esta declarada", avisos)
        pies = " ".join(c.value for c in app.main.caption)
        self.assertIn("colision de seed", pies)
        self.assertIn("species.SPECIES", pies)

    def test_y_el_recuento_de_frentes_sale_ANTES_de_ejecutar_nada(self):
        app = self.run_app()
        textos = " ".join(c.value for c in app.sidebar.caption)
        self.assertIn("frentes cerrables", textos)


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no esta instalado (pip install -r requirements-ui.txt)")
class TestEnlacesExternos(unittest.TestCase):
    """Los tres enlaces, arriba y visibles desde el primer momento.

    Antes de subir nada: son sitios a los que se va a contrastar un diseño, y estaban
    solo en el informe, o sea al final de la corrida. Las direcciones vienen de
    `external_score.EXTERNAL_TOOLS`, no de la pagina: la interfaz no tiene datos propios.
    """

    def run_app(self):
        return AppTest.from_file(str(APP), default_timeout=60).run()

    def test_estan_los_tres_antes_de_subir_ningun_fichero(self):
        app = self.run_app()
        etiquetas = [b.label for b in app.get("link_button")]
        for herramienta in EXTERNAL_TOOLS:
            with self.subTest(herramienta.name):
                self.assertIn(herramienta.name, " ".join(etiquetas))

    def test_apuntan_a_las_direcciones_del_nucleo(self):
        app = self.run_app()
        urls = {b.url for b in app.get("link_button")}
        for herramienta in EXTERNAL_TOOLS:
            with self.subTest(herramienta.name):
                self.assertIn(herramienta.url, urls)

    def test_cada_uno_lleva_su_ayuda(self):
        app = self.run_app()
        ayudas = " ".join(b.help or "" for b in app.get("link_button"))
        self.assertIn("score_externo", ayudas)


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no esta instalado (pip install -r requirements-ui.txt)")
class TestAnatomiaEnLaInterfaz(unittest.TestCase):
    """La pagina tiene que poder resolver la anatomia por las mismas tres vias.

    No las tenia: no habia forma de subir un `.gb`, asi que el lector de GenBank era
    inalcanzable desde el navegador. Y las coordenadas del 3'UTR venian con 1..longitud
    por defecto, o sea que «todo es 3'UTR» era lo que pasaba si no tocabas nada — el
    mismo agujero que se cerro en el CLI, reabierto por la puerta de atras.
    """

    def run_app(self):
        app = AppTest.from_file(str(APP), default_timeout=60).run()
        # Los huecos de secuencia son el PASO 2: salen despues de elegir la especie.
        return app.selectbox[0].set_value("Mus musculus").run()

    def test_hay_un_hueco_para_el_genbank_de_cada_especie(self):
        app = self.run_app()
        etiquetas = [w.label for w in app.main.get("file_uploader")]
        self.assertIn("GenBank de la especie del diseño (.gb, PREFERENTE)", etiquetas)
        self.assertIn("GenBank de la segunda especie (.gb, opcional)", etiquetas)

    def test_el_genbank_acepta_las_extensiones_de_genbank(self):
        app = self.run_app()
        for widget in app.main.get("file_uploader"):
            if "GenBank" in widget.label:
                with self.subTest(widget.label):
                    self.assertIn(".gb", list(widget.proto.type))

    def test_el_fasta_no_acepta_un_gb(self):
        # Si alguien arrastra el .gb al hueco del mRNA, el navegador lo rechaza: no se
        # queda a medias leyendolo como si fuera FASTA.
        app = self.run_app()
        for widget in app.main.get("file_uploader"):
            if widget.label.startswith("mRNA"):
                with self.subTest(widget.label):
                    self.assertNotIn(".gb", list(widget.proto.type))


if __name__ == "__main__":
    unittest.main()
