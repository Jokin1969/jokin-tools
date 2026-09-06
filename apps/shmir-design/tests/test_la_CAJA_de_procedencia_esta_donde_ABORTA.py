"""La caja para declarar la procedencia va DONDE aparece el problema, no sólo en el gestor.

Reportado dos veces por el responsable del proyecto (2026-09-04 y 2026-09-06), la segunda
con el texto YA arreglado delante: el aviso nombraba el paso correcto —la fila del gestor,
en «Ficheros de referencia»— y aun así seguía bloqueado. Y es que un aviso que nombra el
paso correcto **sigue siendo un aviso**: hay que ir a buscarlo, es otro paso de la página,
y quien está en el modal está bloqueado EN el modal.

Es la errata nº 83 llevada hasta el final: allí el texto no nombraba el paso que cierra el
problema; aquí lo nombra y la salida seguía estando en otro sitio.

LO QUE ESTE TEST PROTEGE no es que la caja se pinte —eso lo ve un ojo— sino que la FILA
del modal traiga todo lo que la caja necesita para escribir. Una caja pintada sobre una
fila incompleta se ve igual de bien y revienta al pulsar, que es peor que no tenerla.
"""

import re
import unittest
from pathlib import Path

from shmir_design import presentation

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = (RAIZ / "ui" / "streamlit_app.py").read_text(encoding="utf-8")


NOMBRE = "transcriptoma_3utr.fa"


def _deposito_como_produccion() -> Path:
    """El fichero DENTRO y su línea SIN los cuatro campos de tabla, que es el estado en
    el que el modal aborta. El del repositorio no vale: ahí el transcriptoma no está."""
    import hashlib
    import tempfile

    from shmir_design.manifest import MANIFEST_COLUMNS

    directorio = Path(tempfile.mkdtemp())
    (directorio / NOMBRE).write_text(">a\nACGT\n", encoding="utf-8")
    fila = {c: "" for c in MANIFEST_COLUMNS}
    fila.update({
        "nombre": NOMBRE,
        "filtro": "carga de off-targets por seed",
        "tamaño": "8",
        "md5": hashlib.md5((directorio / NOMBRE).read_bytes()).hexdigest(),
        "fecha_descarga": "2026-09-02",
        "origen": "JCC",
    })
    (directorio / "manifest.tsv").write_text(
        "\t".join(MANIFEST_COLUMNS) + "\n"
        + "\t".join(fila[c] for c in MANIFEST_COLUMNS) + "\n",
        encoding="utf-8",
    )
    return directorio


def _cuerpo(nombre: str) -> str:
    inicio = PAGINA.index(f"def {nombre}(")
    resto = PAGINA[inicio:]
    return resto[: resto.index("\ndef ", 1)]


class TestLaCajaSeOfreceEnElModal(unittest.TestCase):
    def test_el_panel_del_modal_llama_a_la_MISMA_caja_del_gestor(self):
        """La misma función, no una segunda: dos formularios para lo mismo acabarían
        escribiendo cosas distintas."""
        self.assertIn("_declarar_procedencia(", _cuerpo("_panel_deposito"))

    def test_y_sigue_estando_en_el_gestor(self):
        """No se mueve: se ofrece en los dos sitios donde el problema se ve."""
        self.assertIn("_declarar_procedencia(", _cuerpo("_fila_presente"))


class TestLaFilaTraeLoQueLaCajaNECESITA(unittest.TestCase):
    """Las claves se DERIVAN del código de la caja Y DE TODO LO QUE LA CAJA LLAMA con la
    fila, y se comprueban sobre la fila REAL que cada frontal construye, en el estado que
    reproduce producción: el fichero DENTRO y su línea SIN los cuatro campos.

    LA VERSIÓN ANTERIOR DE ESTE TEST PASÓ Y EL MODAL REVENTÓ (errata nº 123). Miraba sólo
    el cuerpo de `_declarar_procedencia`, así que encontró `especie` —la clave que YO
    había roto— y no `etiqueta`, que la lee `_casillas_de_procedencia`, un nivel más
    abajo. Un guardia calibrado sobre el caso que ya se conoce no cubre el conjunto: es
    el principio nº 34 por el lado que no se ve, porque el caso conocido siempre pasa.

    Y encima probaba sobre el depósito del repositorio, donde el transcriptoma NO está —
    así que la rama con `falta_procedencia` no lleno ni se ejecutaba. Un fixture que no
    reproduce el estado del fallo valida el comprobador y no el caso (principio nº 18).
    """

    @classmethod
    def setUpClass(cls):
        # TRANSITIVO: el cuerpo de la caja MÁS el de cada ayudante al que le pasa `fila`.
        # Con un solo nivel, `_casillas_de_procedencia` queda fuera y con ella `clave`,
        # `etiqueta` y `ayuda` — que es exactamente lo que reventó.
        cuerpo = _cuerpo("_declarar_procedencia")
        vistos, pendientes, cuerpos = set(), [cuerpo], [cuerpo]
        while pendientes:
            actual = pendientes.pop()
            for ayudante in set(re.findall(r"(_[a-z_]+)\(\s*fila\b", actual)):
                if ayudante in vistos:
                    continue
                vistos.add(ayudante)
                # Se comprueba que exista ANTES de pedirlo, en vez de capturar el fallo:
                # la expresion puede casar un nombre que no es una funcion de la pagina,
                # y tragarse un error para eso esconderia tambien un ayudante real que
                # dejara de existir (regla 2).
                if f"def {ayudante}(" not in PAGINA:
                    continue
                siguiente = _cuerpo(ayudante)
                cuerpos.append(siguiente)
                pendientes.append(siguiente)
        cls.ayudantes = vistos
        texto = "\n".join(cuerpos)
        cls.claves = set(re.findall(r"fila(?:\.get)?[\[(]\"([a-z_]+)\"", texto))
        # Y las claves de CADA ELEMENTO de las listas que la caja recorre, que es el
        # nivel que faltaba: `campo["etiqueta"]` no es `fila["etiqueta"]`.
        cls.claves_de_campo = set(re.findall(r"campo\[\"([a-z_]+)\"\]", texto))

    def test_el_test_mira_MAS_DE_UN_NIVEL(self):
        """Control adversario del propio detector: si dejara de seguir a los ayudantes,
        volvería a pasar con el modal roto."""
        self.assertIn("_casillas_de_procedencia", self.ayudantes)

    def test_y_encuentra_las_claves_de_los_DOS_niveles(self):
        self.assertTrue(self.claves)
        self.assertIn("etiqueta", self.claves_de_campo)

    def test_la_fila_del_MODAL_las_trae_todas(self):
        fila = presentation.deposit_file(
            "transcriptoma", species="raton", directory=_deposito_como_produccion(),
        )
        self._comprobar(fila, "modal")

    def test_y_la_del_GESTOR_tambien(self):
        panel = presentation.refinement_panel(
            "raton", directory=_deposito_como_produccion()
        )
        fila = next(f for f in panel["filas"] if f["nombre"] == NOMBRE)
        self._comprobar(fila, "gestor")

    def _comprobar(self, fila, quien):
        faltan = sorted(self.claves - set(fila))
        self.assertEqual(faltan, [], f"la fila del {quien} no trae: {faltan}")
        # EL ESTADO DEL FALLO, no uno cualquiera: si aquí no falta procedencia, la caja
        # ni se pinta y este test no prueba nada.
        self.assertTrue(
            fila["falta_procedencia"], f"el fixture del {quien} no reproduce el fallo"
        )
        for campo in fila["procedencia_pedida"]:
            with self.subTest(quien=quien, campo=campo):
                self.assertEqual(sorted(self.claves_de_campo - set(campo)), [])


if __name__ == "__main__":
    unittest.main()
