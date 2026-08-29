"""La página no navega el modelo. Y lo que quede, que no esté detrás de un clic.

Regla 5: escrito antes.

Corolario de la errata nº 17, extendido: la regla 6 dice que la página no contiene
lógica, y esto dice algo más concreto — **cada `a.b.c` en la página es una suposición
sobre el modelo que ningún test comprueba**. El `AttributeError` del modal de empalme no
fue mala suerte: fue una navegación en el único sitio donde no la mira nadie.

Y no todas cuestan lo mismo. Una que está detrás de un `if st.button(...)` **no la
recorre ninguna suite** —ni el golden de la corrida, que pinta la página sin pulsar
nada, ni el test de humo, que sólo comprueba que responde—, así que su primer lector es
el usuario. Ésas son cero, y este test las mantiene a cero.

Recuento al escribir esto: de 9 accesos se pasó a 1, y el que queda es
`upload.getvalue().decode`, que es la API de Streamlit para un fichero subido — contrato
de otra gente, no modelo nuestro.
"""

import unittest


class TestBajoClicNoQuedaNinguna(unittest.TestCase):
    def setUp(self):
        import importlib.util
        from pathlib import Path

        ruta = Path(__file__).resolve().parents[1] / "tools" / "auditar_navegacion.py"
        spec = importlib.util.spec_from_file_location("auditar_navegacion", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        self.informe = modulo.auditar()

    def test_cero_navegaciones_detras_de_un_boton(self):
        culpables = [f"streamlit_app.py:{n}  {c}" for n, c, _ in self.informe["bajo_clic"]]
        self.assertEqual(
            culpables, [],
            "Un acceso al modelo detrás de un clic no lo recorre ninguna suite: su "
            "primer lector es el usuario. Muévelo a `presentation`.\n"
            + "\n".join(culpables),
        )

    def test_y_las_que_quedan_no_son_del_modelo(self):
        nuestras = [
            c for _, c, _ in self.informe["siempre"] if not c.startswith("upload.")
        ]
        self.assertEqual(nuestras, [], "\n".join(nuestras))


class TestLasFuncionesQueLasSUSTITUYEN(unittest.TestCase):
    """Y que hagan lo que la página hacía, que es la otra mitad."""

    @classmethod
    def setUpClass(cls):
        from shmir_design.reference import REFERENCES, fixture_available, load_3utr
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        cls.hay = fixture_available(REFERENCES["NM_011170.3"])
        if cls.hay:
            cls.seleccion = select_from_report(
                tile_utr(load_3utr(REFERENCES["NM_011170.3"])),
                SelectionConfig(n_candidates=3),
            )

    def test_chosen_starts_da_los_mismos_inicios(self):
        if not self.hay:
            self.skipTest("NOT_RUN: falta el fixture del ratón")
        from shmir_design.presentation import chosen_starts

        self.assertEqual(
            chosen_starts(self.seleccion),
            [c.start for c in self.seleccion.selection.chosen],
        )

    def test_has_selection_dice_lo_mismo_que_el_booleano(self):
        if not self.hay:
            self.skipTest("NOT_RUN: falta el fixture del ratón")
        from shmir_design.presentation import has_selection

        self.assertTrue(has_selection(self.seleccion))

    def test_anatomy_source_label_saca_la_via(self):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.presentation import anatomy_source_label

        anatomia = Anatomy(
            length=2191, utr3=(950, 2191), cds=(185, 949),
            source=RegionSource.ANOTACION_GENBANK,
        )
        self.assertEqual(
            anatomy_source_label(anatomia), RegionSource.ANOTACION_GENBANK.value
        )

    def test_y_sin_anatomia_no_revienta(self):
        from shmir_design.presentation import anatomy_source_label

        self.assertTrue(anatomy_source_label("lo que sea"))


if __name__ == "__main__":
    unittest.main()
