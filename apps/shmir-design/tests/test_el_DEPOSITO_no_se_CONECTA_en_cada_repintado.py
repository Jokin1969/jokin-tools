"""Conectar el deposito cuesta el deposito entero, y no se hace en cada repintado.

**Reportado (2026-09-11), errata nº 161**: «Generar los bloques listos para pedir de Homo
sapiens» se queda en «Connecting». Y antes, «Contar off-targets» hacia lo mismo. Dos
botones que no comparten codigo cayendo igual apuntan a una causa COMUN y arriba, no a
dos arreglos abajo — que es la leccion de la errata nº 55.

**Lo que se midio.** La rama de los bloques es INSTANTANEA con el humano: el vector es el
plasmido murino, asi que `block_rows` devuelve la lista vacia y el fragmento no se emite
sin casete. Lo caro esta antes, y corre pase lo que pase:

    recursos = load_from_manifest(reference_dir(), species=…)

`load_from_manifest` CONECTA todos los ficheros del deposito por su rol, y eso incluye el
catalogo de transcriptoma. Medido sobre FASTA sintetico —se mide COSTE, no biologia— con
el mismo `seed_load.load_utr3_set` que corre la app:

    ~36 MB/s   y   ~4,4 MB de RSS por MB de fichero

o sea, con `transcriptoma_3utr_human.fa` (~170 MB): **~5 s y ~750 MB**. Y el humano
declara DOS catalogos —el de la diana y el del fondo murino—, asi que son ~250 MB de
fichero y **~1,1 GB de RSS**. En CADA repintado, y en Streamlit **cada tecla es un
repintado**; durante el repintado conviven la copia vieja y la nueva, asi que el pico
dobla.

Es la errata nº 59 un piso mas arriba: alli era el barrido por ventana, aqui es la
CONEXION entera.

**La causa del «Connecting» no se declara** (principio nº 3): no hay catalogo humano en
este repositorio ni acceso al contenedor. Lo que si se declara es que esto no se puede
sostener aunque no fuera la causa.

**Guardia, no trinquete: el numero correcto es CERO.** Y mira el FUENTE por la razon de
siempre — `AppTest` no llega al estado DISEÑADO, asi que ningun test recorre esto.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import ast
import re
import unittest
from pathlib import Path

from shmir_design import presentation

PAGINA_RUTA = Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
PAGINA = PAGINA_RUTA.read_text(encoding="utf-8")


def _cuerpo(nombre: str) -> str:
    trozo = PAGINA.split(f"def {nombre}(", 1)[1]
    return re.split(r"\ndef ", trozo, maxsplit=1)[0]


def conexiones_sin_cache(fuente: str) -> list[int]:
    """Las lineas donde se llama a `load_from_manifest` SIN preguntar por la cache.

    El criterio es de SIGNIFICADO y no de forma: lo que hace segura una conexion es que
    la funcion que la contiene consulte antes `cached_run` con la huella del deposito.
    Exigir una forma concreta —un `if` determinado, un envoltorio— daria hallazgos
    ciertos sobre codigo correcto el dia que alguien la escriba de otra manera, y un
    guardia con falsos positivos se acaba apagando (principio nº 34).
    """
    arbol = ast.parse(fuente)
    fallos: list[int] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        llamadas = {
            x.func.id for x in ast.walk(nodo)
            if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
        }
        if "load_from_manifest" not in llamadas:
            continue
        if {"cached_run", "deposit_fingerprint"} <= llamadas:
            continue
        fallos.extend(
            x.lineno for x in ast.walk(nodo)
            if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
            and x.func.id == "load_from_manifest"
        )
    return fallos


class TestLaConexionSeReutiliza(unittest.TestCase):

    def test_cero_conexiones_sin_cache(self):
        fallos = conexiones_sin_cache(PAGINA)
        self.assertEqual(
            fallos, [],
            "la página conecta el depósito sin preguntar por la caché, o sea en CADA "
            f"repintado: líneas {fallos}",
        )

    def test_Y_EL_DETECTOR_MUERDE_sobre_la_forma_que_habia(self):
        """CONTROL ADVERSARIO con la forma REAL del fallo (principio nº 18)."""
        antes = (
            "from shmir_design.resources import load_from_manifest\n"
            "def main():\n"
            "    recursos = load_from_manifest(reference_dir(), species=x)\n"
            "    return recursos\n"
        )
        self.assertEqual(conexiones_sin_cache(antes), [3])

    def test_y_NO_muerde_sobre_la_forma_arreglada(self):
        bueno = (
            "from shmir_design.resources import load_from_manifest\n"
            "from shmir_design.presentation import cached_run, deposit_fingerprint\n"
            "def main():\n"
            "    huella = deposit_fingerprint(reference_dir(), species=x)\n"
            "    guardado = cached_run(st.session_state.get('recursos'), huella)\n"
            "    recursos = guardado['resultado']\n"
            "    if recursos is None:\n"
            "        recursos = load_from_manifest(reference_dir(), species=x)\n"
            "    return recursos\n"
        )
        self.assertEqual(conexiones_sin_cache(bueno), [])

    def test_el_detector_HA_MIRADO_de_verdad(self):
        """Prueba de vida (principio nº 51): que la página siga conectando el depósito."""
        self.assertIn("load_from_manifest(", PAGINA)
        self.assertIn("deposit_fingerprint(", PAGINA)


class TestLaHuellaDelDeposito(unittest.TestCase):
    """La huella no puede costar lo que cuesta conectar: si no, no arregla nada."""

    def setUp(self):
        from shmir_design.trabajo import reference_dir

        self.raiz = reference_dir()

    def test_la_misma_carpeta_da_la_MISMA_huella(self):
        self.assertEqual(
            presentation.deposit_fingerprint(self.raiz, species="human"),
            presentation.deposit_fingerprint(self.raiz, species="human"),
        )

    def test_y_OTRA_ESPECIE_da_OTRA(self):
        # No es cosmético: la especie decide QUÉ roles se conectan, así que la misma
        # carpeta con otra especie es otra conexión.
        self.assertNotEqual(
            presentation.deposit_fingerprint(self.raiz, species="human"),
            presentation.deposit_fingerprint(self.raiz, species="raton"),
        )

    def test_un_fichero_NUEVO_cambia_la_huella(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "uno.fa").write_text(">a\nACGT\n")
            antes = presentation.deposit_fingerprint(raiz, species="human")
            (raiz / "dos.fa").write_text(">b\nACGT\n")
            self.assertNotEqual(
                antes, presentation.deposit_fingerprint(raiz, species="human")
            )

    def test_y_un_fichero_REEMPLAZADO_tambien(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            fichero = raiz / "uno.fa"
            fichero.write_text(">a\nACGT\n")
            antes = presentation.deposit_fingerprint(raiz, species="human")
            fichero.write_text(">a\nACGTACGTACGT\n")
            self.assertNotEqual(
                antes, presentation.deposit_fingerprint(raiz, species="human")
            )

    def test_NO_LEE_los_ficheros(self):
        # Es la condición entera: una huella que leyera el depósito costaría lo mismo
        # que conectarlo, y entonces no arreglaría nada. Se dice, además, en el propio
        # docstring — el md5 se descarta A PROPÓSITO.
        import inspect

        fuente = inspect.getsource(presentation.deposit_fingerprint)
        for prohibido in ("read_text", "read_bytes", "open(", "md5(" ):
            with self.subTest(prohibido):
                self.assertNotIn(prohibido, fuente)
        self.assertIn("st_size", fuente)
        self.assertIn("st_mtime", fuente)

    def test_y_LO_QUE_NO_VE_va_escrito(self):
        # Un fichero editado a mano conservando tamaño y mtime no mueve la huella. Ahí
        # manda el cargador, que sí compara md5 — y decirlo es lo que impide leer esta
        # huella como una garantía de integridad.
        import inspect

        doc = inspect.getdoc(presentation.deposit_fingerprint) or ""
        self.assertIn("md5", doc)
        self.assertIn("manda el cargador", doc)


if __name__ == "__main__":
    unittest.main()
