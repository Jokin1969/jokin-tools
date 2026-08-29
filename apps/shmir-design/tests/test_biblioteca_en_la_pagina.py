"""La biblioteca en la página: filas, elección y el adaptador que la hace transparente.

La regla 6 sigue mandando: la página no decide. Recibe FILAS ya montadas y un objeto que
se comporta igual que un fichero subido, para que todo lo que hay aguas abajo —
`_fasta_sequence`, `resolve_anatomy`— no se entere de si vino del navegador o del
volumen. Si aguas abajo hubiera que distinguirlos, serían dos caminos que divergen, y
este proyecto ya lleva cuatro divergencias entre frontales.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shmir_design import biblioteca, presentation

FASTA = b">NM_011170.3 Mus musculus Prnp\nACGTACGTACGTACGTACGTAC\n"


class TestLasFilas(unittest.TestCase):

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.entrada = biblioteca.guardar(
            "mrna_diseno", nombre="raton.fa", data=FASTA,
            date="2026-08-27", base=self.base,
        )

    def test_una_fila_por_entrada_con_lo_que_la_pagina_pinta(self):
        filas = presentation.library_rows("mrna_diseno", base=self.base)
        self.assertEqual(len(filas), 1)
        fila = filas[0]
        for clave in ("id", "nombre", "etiqueta", "guardado", "bytes"):
            self.assertIn(clave, fila)
        self.assertEqual(fila["nombre"], "raton.fa")

    def test_la_etiqueta_YA_viene_montada(self):
        # La página no concatena: si concatenara, la regla 6 se rompe por el sitio más
        # tonto y el formato acaba distinto en cada uno de los cuatro huecos.
        fila = presentation.library_rows("mrna_diseno", base=self.base)[0]
        self.assertIn("raton.fa", fila["etiqueta"])
        self.assertIn(self.entrada.id[:8], fila["etiqueta"])

    def test_una_ranura_vacia_da_CERO_filas_y_no_falla(self):
        self.assertEqual(presentation.library_rows("mrna_segunda", base=self.base), [])

    def test_la_nota_dice_donde_vive_y_que_sobrevive(self):
        nota = presentation.library_note()
        self.assertIn("volumen", nota.lower())
        self.assertIn("redespliegue", nota.lower())


class TestElADAPTADOR(unittest.TestCase):
    """Un fichero de la biblioteca se comporta igual que uno subido."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.entrada = biblioteca.guardar(
            "mrna_diseno", nombre="raton.fa", data=FASTA,
            date="2026-08-27", base=self.base,
        )

    def test_tiene_name_y_getvalue__que_es_todo_lo_que_usa_la_pagina(self):
        guardado = presentation.library_file("mrna_diseno", self.entrada.id, base=self.base)
        self.assertEqual(guardado.name, "raton.fa")
        self.assertEqual(guardado.getvalue(), FASTA)

    def test_y_el_parseo_de_verdad_lo_traga_igual(self):
        # La comprobación que vale: no que tenga los dos métodos, sino que la función
        # que consume el hueco lo acepte sin cambiar nada.
        from shmir_design.fetch import parse_fasta_payload

        guardado = presentation.library_file("mrna_diseno", self.entrada.id, base=self.base)
        _, secuencia = parse_fasta_payload(
            guardado.getvalue().decode("utf-8"), source=guardado.name
        )
        self.assertEqual(secuencia.replace("\n", ""), "ACGTACGTACGTACGTACGTAC")

    def test_pedir_uno_que_no_esta_ABORTA(self):
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError):
            presentation.library_file("mrna_diseno", "0" * 32, base=self.base)


class TestLaPaginaLoUSA(unittest.TestCase):

    def _fuente(self):
        return (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")

    def test_los_CUATRO_huecos_pasan_por_el_panel(self):
        fuente = self._fuente()
        for ranura in biblioteca.SLOTS:
            with self.subTest(ranura):
                self.assertIn(f'"{ranura}"', fuente)

    def test_la_pagina_no_importa_biblioteca_directamente(self):
        # Pasa por `presentation`, como el resto: es lo que impide que la página empiece
        # a decidir sobre el almacén.
        fuente = self._fuente()
        self.assertNotIn("from shmir_design.biblioteca import", fuente)
        self.assertNotIn("import biblioteca", fuente)

    def test_y_sigue_sin_LOGICA(self):
        from tests.sin_logica import comprobar_sin_logica

        fuente = self._fuente()
        inicio = fuente.index("def _panel_biblioteca(")
        fin = fuente.index("\ndef ", inicio + 10)
        comprobar_sin_logica(self, fuente[inicio:fin])


if __name__ == "__main__":
    unittest.main()
