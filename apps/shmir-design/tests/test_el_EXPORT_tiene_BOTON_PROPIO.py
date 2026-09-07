"""El export bueno tiene botón propio, y gana al icono de Streamlit por posición.

`st.dataframe` pinta SIEMPRE, en la esquina de cada tabla, un icono de descarga que
produce `<marca de tiempo>_export.csv`: lo construye el navegador con la tabla ya
pintada, así que sale sin el sello `# BUILD:`, sin las columnas de frente y con las
columnas de la VISTA. No se puede quitar —es de Streamlit— y taparlo sería peor.

Lo que sí está en nuestra mano es que el botón de verdad esté ANTES y se vea más. Hasta
hoy no había ninguno: `tsv_selected` llegaba a la interfaz por un único camino,
`output_bundle`, o sea DENTRO del zip. El único botón visible sobre esa tabla era el que
no es nuestro.

Es el principio nº 55 en su variante nueva: **no lo escribimos nosotros, pero lo servimos
nosotros** — un artefacto que no controlamos compitiendo con uno que sí, y ganando por
posición.
"""

import re
import unittest
from pathlib import Path

from shmir_design import outputs, presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.scaffold import SGEP_SCAFFOLD

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)
#: El nombre CIENTÍFICO es lo que el desplegable pone en `species` (`species_options`),
#: así que es lo que llega al nombre del fichero. Lleva un espacio: ése es el caso.
ESPECIE = "Mus musculus"
PAGINA = Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py"


def _corrida():
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO,
    )
    return presentation.page_run(
        species=ESPECIE, sequence=secuencia, anatomy=anatomia,
    ), anatomia


@unittest.skipUnless(HAY, "falta el fixture del ratón")
class TestElBotonExiste(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.corrida, cls.anatomia = _corrida()

    def _boton(self, stores=None):
        return presentation.selected_export_file(
            self.corrida.selection, species=ESPECIE,
            tiling=self.corrida.tiling, stores=stores,
        )

    def test_trae_nombre_etiqueta_datos_y_mime(self):
        """La página no decide ninguna de las cuatro cosas (regla 6)."""
        boton = self._boton()
        for campo in ("nombre", "etiqueta", "datos", "mime", "nota"):
            with self.subTest(campo):
                self.assertTrue(boton[campo], f"{campo} vacío")

    def test_el_nombre_NO_lleva_espacios(self):
        """`Mus musculus_seleccionados.tsv` era el nombre, con el espacio dentro.

        Sale de `species`, que es el nombre científico. Un nombre de fichero con un
        espacio se parte al pegarlo en una consola y se cita raro en un correo, y el
        fichero que VIAJA es justo éste.
        """
        nombre = self._boton()["nombre"]
        self.assertEqual(nombre, "Mus_musculus_seleccionados.tsv")
        self.assertNotIn(" ", nombre)

    def test_la_etiqueta_dice_QUE_contiene_y_no_como_se_llama(self):
        """Un botón que se llama como el fichero se lee como una lista de ficheros.

        Es la lección de los tres botones del informe, que se reportó como «no encuentro
        dónde se descarga el informe» con los tres delante.
        """
        boton = self._boton()
        self.assertNotIn(".tsv", boton["etiqueta"])
        self.assertIn(boton["nombre"], boton["nota"])

    def test_los_datos_empiezan_por_el_sello_BUILD(self):
        from shmir_design.identidad import BUILD_PREFIX

        primera = self._boton()["datos"].splitlines()[0]
        self.assertTrue(primera.startswith(BUILD_PREFIX), primera)

    def test_es_TSV_de_verdad_y_el_mime_lo_dice(self):
        boton = self._boton()
        cabecera = presentation.tsv_header(boton["datos"])
        self.assertGreater(len(cabecera), 1)
        self.assertIn("tab-separated", boton["mime"])


@unittest.skipUnless(HAY, "falta el fixture del ratón")
class TestUnContenidoUnNombre(unittest.TestCase):
    """El botón y el zip llevan el MISMO fichero: no puede tener dos nombres."""

    @classmethod
    def setUpClass(cls):
        cls.corrida, cls.anatomia = _corrida()

    def test_el_nombre_del_boton_es_UNA_entrada_del_zip(self):
        boton = presentation.selected_export_file(
            self.corrida.selection, species=ESPECIE, tiling=self.corrida.tiling,
        )
        zip_ = presentation.output_bundle(
            species=ESPECIE, tiling=self.corrida.tiling,
            selection=self.corrida.selection, scaffold=SGEP_SCAFFOLD,
        )
        self.assertIn(boton["nombre"], zip_)

    def test_y_el_CONTENIDO_es_el_mismo(self):
        """Mismo nombre y otro contenido sería peor que dos nombres."""
        boton = presentation.selected_export_file(
            self.corrida.selection, species=ESPECIE, tiling=self.corrida.tiling,
        )
        zip_ = presentation.output_bundle(
            species=ESPECIE, tiling=self.corrida.tiling,
            selection=self.corrida.selection, scaffold=SGEP_SCAFFOLD,
        )
        self.assertEqual(boton["datos"], zip_[boton["nombre"]])

    def test_NINGUNA_entrada_del_zip_lleva_un_espacio(self):
        """El espacio no era sólo de este fichero: eran los seis."""
        zip_ = presentation.output_bundle(
            species=ESPECIE, tiling=self.corrida.tiling,
            selection=self.corrida.selection, scaffold=SGEP_SCAFFOLD,
        )
        for nombre in zip_:
            with self.subTest(nombre):
                self.assertNotIn(" ", nombre)


@unittest.skipUnless(HAY, "falta el fixture del ratón")
class TestLleva_LO_QUE_EL_ICONO_NO(unittest.TestCase):
    """Lo que distingue este fichero del `_export.csv` que pinta Streamlit."""

    @classmethod
    def setUpClass(cls):
        cls.corrida, cls.anatomia = _corrida()

    def test_lleva_las_columnas_de_FRENTE_que_la_vista_no_tiene(self):
        cabecera = presentation.tsv_header(presentation.selected_export_file(
            self.corrida.selection, species=ESPECIE, tiling=self.corrida.tiling,
        )["datos"])
        for columna in ("offtarget_seed:guia", "offtarget_seed:pasajera"):
            with self.subTest(columna):
                self.assertIn(columna, cabecera)

    def test_dice_MAS_columnas_que_la_tabla_de_la_pantalla(self):
        """Si dijera lo mismo, el icono de Streamlit valdría y esto sobraría."""
        pantalla = presentation.site_table_rows(
            self.corrida.tiling, self.corrida.selection, species=ESPECIE,
        )
        cabecera = presentation.tsv_header(presentation.selected_export_file(
            self.corrida.selection, species=ESPECIE, tiling=self.corrida.tiling,
        )["datos"])
        self.assertGreater(len(cabecera), len(pantalla[0]))


class TestLaPaginaLoPoneANTES(unittest.TestCase):
    """MÁS CERCA QUE EL ICONO. El icono sale en la esquina de la tabla al pasar el ratón.

    No se puede quitar y taparlo sería peor, así que lo único que queda es que el nuestro
    esté antes en la página. Se comprueba sobre el FUENTE porque es una propiedad del
    orden del código, que es lo que Streamlit pinta de arriba abajo.
    """

    @classmethod
    def setUpClass(cls):
        cls.fuente = PAGINA.read_text("utf-8")

    def test_el_boton_del_export_va_ANTES_de_la_tabla_del_panel(self):
        boton = self.fuente.find("selected_export_file")
        tabla = self.fuente.find("site_table_rows(")
        self.assertNotEqual(boton, -1, "la página no llama a `selected_export_file`")
        self.assertNotEqual(tabla, -1, "no se encuentra la tabla del panel")
        self.assertLess(boton, tabla, "el botón se pinta DESPUÉS de la tabla")

    def test_la_pagina_no_monta_el_nombre_del_fichero(self):
        """Regla 6: el nombre lo decide `presentation`, no la vista."""
        self.assertNotIn("_seleccionados.tsv", self.fuente)

    def test_la_pagina_AVISA_de_que_el_icono_no_es_este_fichero(self):
        """Callarlo deja los dos botones pareciéndose, que es el fallo entero."""
        self.assertIn("EXPORT_VS_ICONO_NOTE", self.fuente)


class TestLaNotaDelIcono(unittest.TestCase):

    def test_nombra_el_patron_del_fichero_de_streamlit(self):
        """Sin el nombre, quien ya lo tiene en Descargas no sabe que es ése."""
        self.assertIn("_export.csv", presentation.EXPORT_VS_ICONO_NOTE)

    def test_y_NO_manda_a_mirar_el_DESPLIEGUE(self):
        """El diagnóstico equivocado cuesta más que ninguno (principio nº 47).

        La nota dice QUÉ contiene cada uno de los dos ficheros. No adivina por qué falta
        algo, y sobre todo no manda a mirar el despliegue: eso es justo lo que se hizo
        durante días mientras el dato estaba en el nombre del fichero.

        Lo que NO prohíbe es nombrar el sello: decir «sin el sello de versión» es
        describir el contenido del otro fichero, que es para lo que la nota existe.
        """
        baja = presentation.EXPORT_VS_ICONO_NOTE.lower()
        for palabra in ("despliegue", "desplegad", "redespliegue", "caché", "cache"):
            with self.subTest(palabra):
                self.assertNotIn(palabra, baja)


if __name__ == "__main__":
    unittest.main()
