"""Que un fichero no esté en el manifiesto es un HECHO del depósito, no una excepción.

Regla 5: escrito con la traza de producción delante.

**EL CASE (2026-09-09).** Se abre el modal de especificidad en humano y la página entera
se cae:

    KeyError: "…/manifest.tsv: no hay ninguna entrada para 'refseq_rna_human.fa'…"
    File "…/ui/streamlit_app.py", line 3425, in <module>  main()

**El guardia estaba escrito y la pregunta no le llegaba** — principio nº 33. En
`read_deposit`:

    try:
        entrada = load_manifest(manifiesto).entry(nombre)
    except ShmirDesignError:
        # rule2-ok: que el fichero no tenga linea es un HECHO sobre el deposito…
        entrada = None

El comentario dice EXACTAMENTE lo correcto. Lo que falla es que `Manifest.entry` lanza un
**`KeyError` pelado**, no un `ShmirDesignError`, así que ese `except` no ha capturado
nunca nada: **cualquier** fichero requerido sin línea tumbaba la página, y el estado «no
está» es el estado NORMAL de un depósito a medias — que es justo lo que el panel existe
para enseñar.

Y por eso llega hasta arriba: `main()` recoge `ShmirDesignError`, así que un `KeyError`
se salta la frontera entera y borra la página por debajo (errata nº 137).

Dos arreglos, y el segundo es el que generaliza:

  · `read_deposit` pregunta con `find`, que DEVUELVE `None` para esta pregunta. Un estado
    normal no se pregunta con una excepción;
  · `Manifest.entry` lanza el error del proyecto y no un `KeyError` pelado. Su mensaje ya
    era un mensaje del proyecto; lo que no era del proyecto es el tipo, y un tipo ajeno se
    salta todas las fronteras que este código tiene escritas.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from shmir_design import deposito, species
from shmir_design.errors import ShmirDesignError
from shmir_design.manifest import load_manifest

RAIZ = Path(__file__).resolve().parent.parent
REFERENCIA = RAIZ / "data" / "reference"


class TestElCasoDeProduccion(unittest.TestCase):
    """El depósito REAL, al que le falta la línea de `refseq_rna_human.fa`."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        shutil.copy(REFERENCIA / "manifest.tsv", cls.tmp / "manifest.tsv")

    def test_la_premisa_sigue_siendo_cierta(self):
        # CONTROL: si algún día ese fichero entra al manifiesto, este test dejaría de
        # reproducir nada y hay que buscar otro rol sin línea.
        texto = (self.tmp / "manifest.tsv").read_text(encoding="utf-8")
        self.assertNotIn("refseq_rna_human.fa", texto)

    def test_read_deposit_NO_revienta(self):
        fichero = deposito.read_deposit(
            "refseq", species=species.resolve("human"), directory=self.tmp
        )
        self.assertFalse(fichero.present)
        self.assertFalse(fichero.registered)

    def test_y_la_fila_del_modal_se_puede_pintar(self):
        from shmir_design.presentation import deposit_for_run

        filas = deposit_for_run(
            "corrida_blast", species="human", directory=self.tmp
        )
        self.assertTrue(filas)
        for fila in filas:
            with self.subTest(fila["rol"]):
                self.assertIn("presente", fila)
                self.assertTrue(str(fila["texto"]).strip())

    def test_y_OFRECE_la_subida_en_vez_de_caerse(self):
        filas = __import__(
            "shmir_design.presentation", fromlist=["deposit_for_run"]
        ).deposit_for_run("corrida_blast", species="human", directory=self.tmp)
        refseq = [f for f in filas if f["rol"] == "refseq"]
        self.assertEqual(len(refseq), 1)
        self.assertTrue(refseq[0]["ofrecer_subida"])


class TestNingunErrorDELPROYECTOEsUnKeyErrorPelado(unittest.TestCase):
    """Un tipo ajeno se salta todas las fronteras que este código tiene escritas."""

    def test_entry_lanza_el_error_del_proyecto(self):
        manifiesto = load_manifest(REFERENCIA / "manifest.tsv")
        with self.assertRaises(ShmirDesignError):
            manifiesto.entry("no_existe_este_fichero.fa")

    def test_y_el_mensaje_sigue_diciendo_CUALES_hay(self):
        manifiesto = load_manifest(REFERENCIA / "manifest.tsv")
        with self.assertRaises(ShmirDesignError) as caso:
            manifiesto.entry("no_existe_este_fichero.fa")
        self.assertIn("no_existe_este_fichero.fa", str(caso.exception))
        self.assertIn("mature.fa", str(caso.exception))

    def test_find_sigue_contestando_SIN_excepcion(self):
        # Es la funcion con la que se pregunta un estado normal, y tiene que seguir ahi:
        # preguntar «¿esta registrado?» con un try/except es lo que produjo el fallo.
        manifiesto = load_manifest(REFERENCIA / "manifest.tsv")
        self.assertIsNone(manifiesto.find("no_existe_este_fichero.fa"))
        self.assertIsNotNone(manifiesto.find("mature.fa"))


if __name__ == "__main__":
    unittest.main()
