"""El catalogo de off-targets se abre AL PULSAR, no en cada repintado.

**Reportado (2026-09-11), errata nº 160**: se pulsa «Contar off-targets — Homo sapiens
contra human», la pagina se queda en **«Connecting»** y de ahi no sale.

«Connecting» es el cartel de RECONEXION de Streamlit: el WebSocket con el servidor se ha
caido. **No es que la corrida siga**, es que del otro lado ya no hay nadie — o el proceso
ha muerto, o lleva tanto sin contestar que el cliente lo ha dado por perdido. Lo que este
fichero cierra no es la causa —esa no se ha podido reproducir desde aqui y no se le asigna
(principio nº 3)— sino lo que SI esta medido y es indefendible por su cuenta:

    `_modal_offtarget` llamaba a `offtarget_catalog_from_deposit` FUERA del boton.

Esa funcion lee el fichero entero, le calcula el md5, lo parsea y le audita las isoformas.
Y en Streamlit **cada tecla es un repintado**, asi que eso se ejecutaba en cada pulsacion.

**MEDIDO en este entorno** sobre FASTA sintetico —se mide COSTE, no biologia— con las
mismas funciones que corre la app:

    abrir + auditar   ~29 Mnt/s      construir el indice   ~4 Mnt/s, ~3,2 B de RSS por nt

o sea, con un catalogo humano de ~170 Mnt: **~6 s y ~340 MB por tecla** antes siquiera de
pulsar, y al pulsar **~42 s mas y un pico de ~550 MB** por encima de lo que ya ocupa
Streamlit. Es la errata nº 59 en el camino vivo y con un fichero veinte veces mayor.

Lo que hace falta ANTES de correr no es el catalogo: es saber **cual es y que esta**, y eso
lo dice la linea del manifiesto, que ya esta leida. El fichero se abre cuando se pulsa.

**Guardia, no trinquete: el numero correcto es CERO.** Y mira el FUENTE por la razon de
siempre — `AppTest` no llega al estado DISEÑADO, asi que ningun test recorre este modal.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import ast
import inspect
import re
import unittest
from pathlib import Path

from shmir_design import presentation

PAGINA = (
    Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
).read_text(encoding="utf-8")

#: Lo que NO puede correr fuera del boton, con el motivo de cada uno. Se declara por
#: NOMBRE y no por fichero: son los dos que abren el catalogo entero.
CAROS = ("offtarget_catalog_from_deposit", "offtarget_run")


def _cuerpo(nombre: str) -> str:
    trozo = PAGINA.split(f"def {nombre}(", 1)[1]
    return re.split(r"\ndef ", trozo, maxsplit=1)[0]


def fuera_del_boton(fuente: str, *, caros=CAROS) -> list[tuple[str, int]]:
    """`(nombre, linea)` de cada llamada cara que NO cuelga de un `st.button`.

    Se resuelve sobre el AST y no por sangrado: una llamada dentro de un `with` dentro
    del `if` sigue colgando del boton, y contarla seria un falso positivo — un guardia
    con falsos positivos se acaba apagando.
    """
    arbol = ast.parse(fuente)
    protegidas: set[int] = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.If):
            continue
        if not any(
            isinstance(x, ast.Attribute) and x.attr == "button"
            for x in ast.walk(nodo.test)
        ):
            continue
        for hijo in ast.walk(nodo):
            if isinstance(hijo, ast.Call) and isinstance(hijo.func, ast.Name):
                protegidas.add(id(hijo))
    fallos = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Name):
            continue
        if nodo.func.id in caros and id(nodo) not in protegidas:
            fallos.append((nodo.func.id, nodo.lineno))
    return fallos


class TestElCatalogoSoloSeAbreAlPulsar(unittest.TestCase):

    def test_cero_llamadas_caras_fuera_del_boton(self):
        fallos = fuera_del_boton(PAGINA)
        self.assertEqual(
            fallos, [],
            "la página abre el catálogo fuera del botón, o sea en CADA repintado — y en "
            "Streamlit cada tecla es un repintado: "
            + ", ".join(f"{n} (línea {l})" for n, l in fallos),
        )

    def test_Y_EL_DETECTOR_MUERDE_sobre_la_forma_que_habia(self):
        """CONTROL ADVERSARIO con la forma REAL del fallo (principio nº 18)."""
        antes = (
            "import streamlit as st\n"
            "from shmir_design.presentation import offtarget_catalog_from_deposit\n"
            "def _modal_offtarget(nombre, elegido):\n"
            "    catalogo = offtarget_catalog_from_deposit(\n"
            "        species=nombre, directory=None, role=str(elegido['rol']),\n"
            "    )\n"
            "    if st.button('Contar'):\n"
            "        return catalogo\n"
        )
        self.assertEqual(
            fuera_del_boton(antes), [("offtarget_catalog_from_deposit", 4)],
        )

    def test_y_NO_muerde_cuando_cuelga_del_boton_aunque_sea_dentro_de_un_with(self):
        """La otra mitad: así es EXACTAMENTE como queda el arreglo."""
        bueno = (
            "import streamlit as st\n"
            "from shmir_design.presentation import offtarget_catalog_from_deposit\n"
            "def _modal_offtarget(nombre, elegido, resumen):\n"
            "    if st.button('Contar'):\n"
            "        with st.spinner(resumen['coste']):\n"
            "            catalogo = offtarget_catalog_from_deposit(\n"
            "                species=nombre, directory=None, role=str(elegido['rol']),\n"
            "            )\n"
            "            return catalogo\n"
        )
        self.assertEqual(fuera_del_boton(bueno), [])

    def test_el_detector_HA_MIRADO_de_verdad(self):
        """Prueba de vida (principio nº 51): que esas llamadas existan en la página."""
        for nombre in CAROS:
            with self.subTest(nombre):
                self.assertIn(
                    f"{nombre}(", PAGINA,
                    f"la página ya no llama a {nombre}: este guardia dejó de cubrir el "
                    f"camino que lo motiva y hay que mirar por qué.",
                )


class TestLaVistaBarataNOabreElFichero(unittest.TestCase):
    """Lo que se pinta antes de correr sale del MANIFIESTO, no del fichero."""

    def test_el_resumen_no_lee_ni_parsea_nada(self):
        fuente = inspect.getsource(presentation.offtarget_catalog_summary)
        for prohibido in ("read_text", "validate_upload", "build_catalog", "open("):
            with self.subTest(prohibido):
                self.assertNotIn(
                    prohibido, fuente,
                    f"el resumen llama a `{prohibido}`: entonces vuelve a costar el "
                    f"fichero entero en cada repintado, que es lo que esto cierra.",
                )

    def test_sin_fichero_lo_dice_y_no_inventa_coste(self):
        from shmir_design.trabajo import reference_dir

        vista = presentation.offtarget_catalog_summary(
            species="raton", directory=reference_dir(),
        )
        # Con el catálogo ausente —que es el caso de este repositorio— no hay nada que
        # costear: un coste sobre un fichero que no está sería un número inventado.
        self.assertFalse(vista["presente"])
        self.assertEqual(vista["coste"], "")
        self.assertTrue(vista["nombre"])

    def test_el_coste_se_DERIVA_de_tasas_medidas_y_del_TAMAÑO(self):
        # No es un texto fijo: sale de multiplicar tasas medidas por los MB de ESE
        # fichero. Con otro catálogo dice otra cosa, y se entera solo (principio nº 13).
        tasas = presentation.COSTE_DEL_CATALOGO
        self.assertGreater(tasas["abrir_mnt_por_s"], 0)
        self.assertGreater(tasas["indice_mnt_por_s"], 0)
        self.assertGreater(tasas["indice_bytes_por_nt"], 0)
        fuente = inspect.getsource(presentation.offtarget_catalog_summary)
        self.assertIn("COSTE_DEL_CATALOGO", fuente)

    def test_y_el_coste_del_modal_YA_NO_se_declara_SIN_MEDIR(self):
        # Estaba declarado `medido=False` —«aquí nadie ha cronometrado cuánto»— y el
        # botón se ofrecía igual. Medirlo es lo que permite decir antes de pulsar si el
        # contenedor tiene margen.
        coste = presentation.COSTE_POR_ALCANCE["corrida_offtarget"]
        self.assertTrue(coste.medido)
        self.assertIn("memoria", coste.texto.lower())


if __name__ == "__main__":
    unittest.main()
