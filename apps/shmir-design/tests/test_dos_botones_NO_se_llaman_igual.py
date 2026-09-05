"""Dos botones que bajan cosas distintas no pueden llamarse casi igual.

**Errata nº 78 (2026-09-04).** Se llamaban «Descargar todo (zip)» y «Descargar todo
(.zip)» — **un punto de diferencia** — y bajan cosas distintas: uno los ficheros que acaba
de generar el diseño, el otro la copia de seguridad del volumen entero.

No es estilo. Con esos dos nombres, un reporte de «no me baja el zip» no identifica cuál,
y **reproduje el que no era**, de punta a punta y midiendo, antes de darme cuenta. Que dos
botones sólo se distingan por un signo de puntuación es un problema de la interfaz antes
que de quien los confunde — y lo dijo quien lo reportó, con razón.

**El guardia mide la distancia entre las etiquetas de descarga**, así que no protege sólo
a estos dos: el día que entre un tercer zip, se entera.

Regla 5: escritos antes.
"""

import re
import unittest
from pathlib import Path

FUENTE = (
    Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
).read_text(encoding="utf-8")

#: Qué se considera «casi igual»: lo mismo tras quitar todo lo que no es una letra. Un
#: punto, un paréntesis o un espacio no distinguen dos botones — es exactamente lo que
#: pasó.
def _esqueleto(etiqueta: str) -> str:
    return re.sub(r"[^0-9a-záéíóúñ]+", "", etiqueta.lower())


def _etiquetas_de_descarga() -> list[str]:
    """Las etiquetas de los `download_button`, resueltas cuando son una constante.

    Se resuelven contra `presentation` porque las decisiones de texto viven allí
    (regla 6): buscar sólo literales dejaría fuera justo a las que están bien puestas.
    """
    from shmir_design import presentation

    etiquetas = []
    for llamada in re.finditer(r"st\.download_button\(\s*([^,\n]+)", FUENTE):
        crudo = llamada.group(1).strip()
        if crudo.startswith(('"', "'")):
            etiquetas.append(crudo[1:-1])
        elif re.fullmatch(r"[A-Z_][A-Z0-9_]*", crudo):
            valor = getattr(presentation, crudo, None)
            if isinstance(valor, str):
                etiquetas.append(valor)
    return etiquetas


class TestNingunParDeBotonesSeConfunde(unittest.TestCase):
    def test_hay_etiquetas_que_mirar(self):
        # CONTROL: si el detector dejara de encontrar ninguna, el test de abajo pasaría
        # sin comprobar nada — «cero pares confundibles» y «no miré» darían el mismo
        # verde. Es la errata nº 29 aplicada a un guardia de dos líneas.
        self.assertGreaterEqual(len(_etiquetas_de_descarga()), 2)

    def test_ninguna_pareja_es_LA_MISMA_sin_puntuacion(self):
        etiquetas = _etiquetas_de_descarga()
        vistos: dict[str, str] = {}
        choques = []
        for etiqueta in etiquetas:
            clave = _esqueleto(etiqueta)
            if clave in vistos and vistos[clave] != etiqueta:
                choques.append((vistos[clave], etiqueta))
            vistos.setdefault(clave, etiqueta)
        self.assertEqual(
            choques, [],
            "hay botones de descarga que sólo se distinguen por puntuación: un reporte "
            "de «no me baja el zip» no diría cuál es.",
        )

    def test_el_guardia_MUERDE_con_el_par_de_antes(self):
        # Sin esto, «ningún par choca» y «el criterio no distingue nada» dan el mismo
        # verde. Con los dos nombres que había, tiene que chocar.
        self.assertEqual(
            _esqueleto("Descargar todo (zip)"), _esqueleto("Descargar todo (.zip)")
        )

    def test_y_los_dos_de_hoy_dicen_QUE_bajan(self):
        from shmir_design.presentation import (
            DOWNLOAD_BUTTON_BACKUP,
            DOWNLOAD_BUTTON_RESULTS,
        )

        # «Todo» no dice nada: qué es «todo» depende de dónde estés en la página.
        for etiqueta in (DOWNLOAD_BUTTON_BACKUP, DOWNLOAD_BUTTON_RESULTS):
            with self.subTest(etiqueta):
                self.assertNotIn("todo (", etiqueta.lower())
        self.assertNotEqual(
            _esqueleto(DOWNLOAD_BUTTON_BACKUP), _esqueleto(DOWNLOAD_BUTTON_RESULTS)
        )


if __name__ == "__main__":
    unittest.main()
