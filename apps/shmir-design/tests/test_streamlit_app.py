"""Comprobacion de que la interfaz arranca y no toma decisiones por su cuenta.

La logica se prueba en `test_presentation.py`; aqui solo se verifica que el script se
ejecuta sin excepciones, que los umbrales salen con sus valores por defecto visibles y
que sin ficheros no se pinta ningun resultado.

Se salta de forma visible si Streamlit no esta instalado: el nucleo no depende de el.
"""

import unittest
from pathlib import Path

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

    def test_pide_los_dos_fasta_antes_de_calcular_nada(self):
        app = self.run_app()
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


if __name__ == "__main__":
    unittest.main()
