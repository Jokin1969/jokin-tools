"""La clave con la que se BUSCA una corrida es la misma con la que se GENERO.

**El hallazgo, y es latente.** `build_dossier` arma la clave a mano —
`f"{species}_pos{start}_guia"`— con la especie TAL CUAL se la pasen. El FASTA de consulta
la arma con `presentation.query_name`, que usa el SLUG desde la errata nº 42. Son dos
definiciones del mismo identificador, y ya han divergido: con `species="Mus musculus"` una
dice `Mus musculus_pos959_guia` y la otra `mouse_pos959_guia`.

**Hoy no se nota porque nadie llama a `build_dossier` con un almacen lleno** — la ficha
sale con uno vacio y todos los frentes en NOT_RUN. O sea: el fallo esta esperando a que
alguien cablee el almacen, y entonces `verdict_for` **no encontraria nada** y el sintoma
seria el mismo que el de ahora. Se habria arreglado el cableado y seguiria sin funcionar.

Es el principio nº 13 —una constante que cita algo se DERIVA, no se transcribe— sobre una
CLAVE en vez de sobre un dato.
"""

import unittest

from shmir_design import presentation


class TestLaCLAVEsaleDeUNsitio(unittest.TestCase):

    def test_la_misma_funcion_arma_el_FASTA_y_la_busqueda(self):
        from shmir_design import dossier

        # No se compara el texto: se comprueba que `dossier` llama a `query_name` en vez
        # de volver a escribir el formato. Comparar dos cadenas iguales dejaria pasar dos
        # implementaciones que hoy coinciden y mañana no.
        import inspect

        fuente = inspect.getsource(dossier.build_dossier)
        self.assertIn("query_name", fuente)
        self.assertNotIn('f"{species}_pos{start}_guia"', fuente)

    def test_y_las_de_SEED_y_OFF_TARGET_tambien(self):
        """Las tres, no solo la de BLAST.

        Arreglar solo la primera habria dejado a las otras dos esperando su turno con el
        mismo fallo — y el sintoma seria identico: una corrida guardada que la ficha no
        encuentra. Un comentario protege su tabla; un mecanismo protege la siguiente.
        """
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "shmir_design" / "dossier.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('f"{species}_pos{start}_{hebra}"', fuente)

    def test_y_el_alias_NO_cambia_la_clave(self):
        # `mouse`, `raton` y `Mus musculus` son la MISMA especie. Si la clave cambiara con
        # el alias, una corrida guardada desde la pagina no la encontraria el informe.
        claves = {
            presentation.query_name(alias, 959, "guia")
            for alias in ("mouse", "raton", "Mus musculus")
        }
        self.assertEqual(claves, {"mouse_pos959_guia"})


if __name__ == "__main__":
    unittest.main()
