"""El aviso del proyecto sin entrada nombra el paso que lo cierra, y no lo transcribe.

**Reportado (2026-09-04)**, al abrir un proyecto guardado de antes: el aviso dice «súbela
como siempre y el proyecto se abrirá igual», y quien lo lee sube la secuencia y espera que
el proyecto se abra **solo**. No se abre: hay que ir a la barra lateral, marcar la casilla
de guardar y elegirlo en el desplegable — y **ese es el momento** en que el proyecto se
abre con la secuencia delante y la migración se escribe.

O sea que el mensaje describía el 80 % del camino y se callaba el paso que lo cierra. Es
la misma familia que la ficha de obtención que describía un fichero y el cargador leía
otro: **una instrucción que se lee correcta de principio a fin y no lleva a donde dice**.

Y el nombre de la casilla **no se transcribe** (principio nº 13): si el aviso escribiera
«marca "Guardar esta corrida en un proyecto"» por su cuenta, el día que esa casilla se
llame de otra forma el aviso mandaría a buscar un control que no existe — con la forma
correcta y sin dar ningún error.

Regla 5: escritos antes.
"""

import unittest
from pathlib import Path

from shmir_design import presentation

FUENTE = (
    Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
).read_text(encoding="utf-8")


class TestElAvisoLlevaHastaElFinal(unittest.TestCase):
    def test_nombra_la_casilla_por_su_nombre_de_verdad(self):
        self.assertIn(
            presentation.PROJECT_SAVE_TOGGLE, presentation.PROJECT_WITHOUT_ENTRY,
            "el aviso no dice dónde se abre el proyecto una vez subida la secuencia, "
            "que es el paso donde su entrada queda guardada.",
        )

    def test_y_dice_que_ahi_es_donde_se_GUARDA(self):
        texto = presentation.PROJECT_WITHOUT_ENTRY.lower()
        self.assertIn("barra lateral", texto)
        self.assertIn("se reabre solo", texto)

    def test_y_del_md5_no_se_reconstruye_nada(self):
        # Regla 1 por su lado bueno, y no se pierde al reescribir el mensaje.
        self.assertIn("md5", presentation.PROJECT_WITHOUT_ENTRY)
        self.assertIn("no se inventa", presentation.PROJECT_WITHOUT_ENTRY)


class TestLaCasillaSeLLAMAdesdeUnSitio(unittest.TestCase):
    """Un nombre que sale en dos textos distintos se desincroniza en los dos."""

    def test_la_pagina_usa_la_constante_y_no_el_literal(self):
        limpia = "\n".join(
            l for l in FUENTE.split("\n") if not l.lstrip().startswith("#")
        )
        self.assertIn("PROJECT_SAVE_TOGGLE", limpia)
        self.assertNotIn(f'"{presentation.PROJECT_SAVE_TOGGLE}"', limpia)


if __name__ == "__main__":
    unittest.main()
