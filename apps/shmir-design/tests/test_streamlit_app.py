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

from tests.pagina import sin_proyectos

APP = Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no está instalado (pip install -r requirements-ui.txt)")
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

    def test_y_la_SECUENCIA_se_pide_DESPUES_de_elegirla(self):
        """La invariante es el ORDEN, no la palabra.

        Este test decia `assertIn("FASTA", ...)` y empezo a fallar cuando el mensaje paso
        a hablar de «la secuencia del mensajero» en vez del formato del fichero — que es
        una mejora, no una regresion. Anclar una invariante a una palabra concreta la
        rompe cada vez que alguien escribe mejor la frase, y el arreglo comodo habria
        sido devolver la jerga.
        """
        app = self.run_app()
        app.selectbox[0].set_value("Mus musculus").run()
        textos = " ".join(info.value for info in app.info).lower()
        self.assertIn("sube la secuencia", textos)
        # Y que ya NO pide la especie: eso es lo que demuestra que se paso de paso.
        self.assertNotIn("elige una especie", textos)

    def test_los_umbrales_muestran_su_valor_por_defecto(self):
        app = self.run_app()
        etiquetas = " ".join(widget.label for widget in app.sidebar.number_input)
        for esperado in ("GC mínimo (por defecto: 0.3", "Homopolímero máximo (por defecto: 3)",
                         "Asimetría mínima, kcal/mol (por defecto: 0.5)",
                         "Candidatos por especie (por defecto: 11)",
                         "Espaciado mínimo entre sitios, nt (por defecto: 50)"):
            with self.subTest(esperado):
                self.assertIn(esperado, etiquetas)

    def test_los_umbrales_arrancan_en_su_valor_por_defecto(self):
        app = self.run_app()
        valores = {w.label.split(" (")[0]: w.value for w in app.sidebar.number_input}
        self.assertAlmostEqual(valores["GC mínimo"], 0.30)
        self.assertAlmostEqual(valores["GC máximo"], 0.52)
        self.assertEqual(valores["Homopolímero máximo"], 3)
        self.assertEqual(valores["Candidatos por especie"], 11)
        self.assertEqual(valores["Espaciado mínimo entre sitios, nt"], 50)


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no está instalado (pip install -r requirements-ui.txt)")
class TestFicherosDeReferencia(unittest.TestCase):
    """El GESTOR del paso 3, y la casilla global que ya no existe.

    El panel VIVIA EN LA BARRA LATERAL y la lista de frentes abiertos en el paso 3: dos
    sitios para la misma pregunta, y habia que mirar los dos para saber en que punto
    estabas. Ahora es UNA tabla en el paso 3, y por eso estos tests miran el cuerpo de la
    pagina y no `app.sidebar`.

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
        etiquetas = [w.label for w in app.checkbox] + [w.label for w in app.sidebar.checkbox]
        self.assertNotIn("Usar los de data/reference/", etiquetas)

    def test_siguen_los_dos_controles_que_SI_son_decisiones(self):
        app = self.run_app()
        etiquetas = [w.label for w in app.checkbox] + [w.label for w in app.sidebar.checkbox]
        etiquetas += [w.label for w in app.sidebar.text_input]
        # «Gen diana (accession)» ya no está: la diana la declara
        # `data/diana/variantes.toml` y pedirla además a mano eran dos respuestas a la
        # misma pregunta, ganando la peor (una variante, sin procedencia).
        self.assertIn("Calcular accesibilidad (lento)", etiquetas)
        self.assertNotIn("Gen diana (accession)", etiquetas)

    def test_la_accesibilidad_arranca_apagada(self):
        app = self.run_app()
        valores = {w.label: w.value for w in app.sidebar.checkbox}
        self.assertFalse(valores["Calcular accesibilidad (lento)"])

    def test_la_diana_NO_se_pide_en_ningun_campo(self):
        """La única forma de declararla es su tabla. Y eso se comprueba, no se supone.

        El campo pedía UN accession a mano para algo que `data/diana/variantes.toml` ya
        declara por especie, con TODAS sus variantes y con procedencia. Un campo que
        vuelva a aparecer sería la segunda respuesta otra vez.
        """
        app = self.run_app()
        etiquetas = [w.label for w in app.sidebar.text_input] + [
            w.label for w in app.text_input
        ]
        self.assertFalse([e for e in etiquetas if "diana" in e.lower()], etiquetas)

    def test_sin_especie_NO_se_llega_al_gestor_y_se_dice_por_que(self):
        # Con el panel en la barra lateral salía siempre, con un «elige una especie».
        # Ahora vive en el paso 3, y sin especie la página no llega hasta ahí: lo que
        # tiene que estar es el motivo, y el desplegable SIN valor por defecto.
        app = self.run_app(especie=None)
        self.assertIsNone(app.selectbox[0].value)
        etiquetas = [w.label for w in app.get("file_uploader")]
        self.assertEqual([e for e in etiquetas if e.startswith("Subir ")], [])

    def test_los_AUSENTES_salen_con_su_hueco_de_subida(self):
        # Sólo los ausentes. `rmsk_mouse.out`, `mature.fa` y `aav_casete.fa` están en el
        # directorio de referencia del paquete, así que salen con sus CUATRO botones y
        # no con «Subir»: la versión anterior de este test los pedía como huecos porque
        # el panel no distinguía presente de ausente.
        app = self.run_app()
        etiquetas = [w.label for w in app.get("file_uploader")]
        for esperado in ("Subir refseq_rna.fa", "Subir transcriptoma_3utr.fa",
                         "Subir expresion_cerebro.tsv"):
            with self.subTest(esperado):
                self.assertIn(esperado, etiquetas)

    def test_y_los_PRESENTES_con_sus_CUATRO_acciones(self):
        # El criterio del panel: sobre lo que ya está se puede actuar sin salir de ahí.
        app = self.run_app()
        botones = [b.label for b in app.button] + [b.label for b in app.get("toggle")]
        descargas = [b.label for b in app.get("download_button")]
        self.assertIn("Ver", botones)
        self.assertIn("Reemplazar", botones)
        self.assertIn("Borrar", botones)
        self.assertIn("Descargar", descargas)

    def test_cada_fila_dice_QUE_FRENTE_cierra(self):
        """Ya NO se agrupa por frente: el orden es por IMPACTO —lo que falta arriba, lo
        resuelto abajo—, que es lo que se viene a mirar. Pero el frente no se pierde por
        eso: viaja EN LA FILA. Un fichero sin frente visible es un fichero del que no se
        sabe para que sirve."""
        app = self.run_app()
        texto = " ".join(m.value for m in app.get("markdown"))
        texto += " ".join(e.label for e in app.get("expander"))
        for frente in ("especificidad", "repeticiones", "seed", "transgen"):
            with self.subTest(frente):
                self.assertIn(frente, texto)

    def test_presentes_y_ausentes_salen_en_LA_MISMA_tabla(self):
        # Lo que este cambio existe para arreglar: antes eran dos sitios —los frentes
        # abiertos en el paso 3 y la subida en la barra lateral— y habia que mirar los
        # dos para saber en que punto estabas.
        app = self.run_app()
        etiquetas = [w.label for w in app.get("file_uploader")]
        self.assertTrue(any(e.startswith("Subir ") for e in etiquetas))
        self.assertEqual([w.label for w in app.sidebar.get("file_uploader")
                          if w.label.startswith("Subir ")], [])

    def test_elegir_OTRA_ESPECIE_explica_los_frentes_ANTES_de_teclear_el_nombre(self):
        """La pregunta que se contesta es «¿me sirve esta app para mi especie?».

        Contestarla despues de teclear el nombre es no contestarla.
        """
        app = self.run_app(especie="otra especie (no declarada)")
        avisos = " ".join(w.value for w in app.warning)
        self.assertIn("NO está declarada", avisos)
        pies = " ".join(c.value for c in app.main.caption)
        self.assertIn("colisión de seed", pies)
        self.assertIn("species.SPECIES", pies)

    def test_y_el_recuento_de_frentes_SIGUE_saliendo_antes_de_ejecutar_nada(self):
        """El contador se mudo al paso 5 y cambio de forma —«N de 7 frentes cerrados»,
        con barra—, pero se sigue pudiendo ver sin haber corrido nada."""
        app = self.run_app()
        textos = " ".join(p.proto.text for p in app.get("progress"))
        self.assertIn("de 8 frentes cerrados", textos)


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no está instalado (pip install -r requirements-ui.txt)")
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


@unittest.skipUnless(STREAMLIT, "NOT_RUN: Streamlit no está instalado (pip install -r requirements-ui.txt)")
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



# EL DIRECTORIO DE PROYECTOS SE DECLARA, no se hereda de la máquina. Desde que la primera
# pregunta de la app es «¿retomas un proyecto guardado?», lo que se pinta arriba del todo
# depende de si hay proyectos guardados — y sin declararlo, ése es el del paquete. Con un
# proyecto de prueba dentro, `app.selectbox[0]` deja de ser el de la especie y saltan 24
# tests de ficheros que no tienen nada que ver: un fallo así no dice lo que pasa, dice que
# has roto media app. Ver `tests/pagina.py`.
#
# Va como `setUpModule` y no como gestor de contexto porque tiene que estar puesto durante
# TODOS los `.run()`: cada `set_value(...).run()` vuelve a ejecutar el script de la página.
_ENTORNO_DE_PAGINA = None


def setUpModule():
    global _ENTORNO_DE_PAGINA
    _ENTORNO_DE_PAGINA = sin_proyectos()
    _ENTORNO_DE_PAGINA.__enter__()


def tearDownModule():
    if _ENTORNO_DE_PAGINA is not None:
        _ENTORNO_DE_PAGINA.__exit__(None, None, None)

if __name__ == "__main__":
    unittest.main()
