"""El modal avisa ANTES de correr, no despues de guardar.

**Lo que pide el responsable del proyecto**: si falta lo que hace falta, decirlo antes de
pedirle al usuario que se baje una base de decenas de GB y eche horas de BLAST.

**Y lo que se comprobo antes de escribirlo, porque la premisa habia cambiado.** «Sin
`refseq_rna.fa` en el deposito, cualquier corrida saldra NOT_RUN» era cierto hasta que la
tabla empezo a leer los almacenes. Hoy, MEDIDO: la celda de la tabla SI pasa a `PASS` con
una corrida buena y sin el fichero — lo que se queda atras es el FRENTE (la tarjeta, el
semaforo y el bloque de frentes del informe), que sale de `blocking_fronts` y depende del
filtro de la ventana, que si necesita la base cargada.

Asi que el aviso dice **eso**, que es lo que pasa, y no lo que se suponia. Un aviso que
explica una causa sin comprobarla es el principio nº 3, y este proyecto lleva cinco.
"""

import unittest

from shmir_design import blast, presentation


class TestElAVISOsaleANTES(unittest.TestCase):

    def test_sin_la_base_declarada_hay_aviso(self):
        avisos = presentation.blast_readiness(species="raton", directory=None)
        self.assertTrue(avisos)

    def test_y_NO_dice_que_la_corrida_sera_inutil(self):
        """Porque ya no lo es: la celda de la tabla cambia igual. Medido."""
        texto = " ".join(
            a["texto"] for a in presentation.blast_readiness(
                species="raton", directory=None
            )
        ).lower()
        self.assertNotIn("no podrá dar veredicto", texto)

    def test_dice_QUE_se_queda_sin_cerrar(self):
        texto = " ".join(
            a["texto"] for a in presentation.blast_readiness(
                species="raton", directory=None
            )
        ).lower()
        self.assertIn("frente", texto)

    def test_y_NOMBRA_el_fichero_que_falta(self):
        texto = " ".join(
            a["texto"] for a in presentation.blast_readiness(
                species="raton", directory=None
            )
        )
        self.assertIn("refseq_rna.fa", texto)

    def test_no_BLOQUEA_la_subida(self):
        # La corrida sirve igual para la tabla y para el informe: bloquearla seria peor
        # que el aviso que sustituye.
        for aviso in presentation.blast_readiness(species="raton", directory=None):
            self.assertFalse(aviso["bloquea"])

    def test_con_la_base_en_el_deposito_NO_hay_aviso(self):
        """Control adversario: si saliera siempre, no distinguiria nada."""
        from tests.test_estados_de_fichero import deposito_completo

        with deposito_completo() as directorio:
            self.assertEqual(
                presentation.blast_readiness(species="raton", directory=directorio), []
            )


class TestElMODALloPINTA(unittest.TestCase):

    def test_la_pagina_lo_llama_antes_del_uploader(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertTrue(
            "blast_readiness" in fuente,
            "la pagina no llama a `blast_readiness`: el aviso corre y no llega a "
            "ninguna pantalla, que es media comprobacion.",
        )
        # ANTES: si sale despues del `file_uploader`, llega cuando ya se ha corrido.
        self.assertLess(
            fuente.index("blast_readiness("),
            fuente.index('"Soltar aquí el resultado (-outfmt 6)"'),
        )


if __name__ == "__main__":
    unittest.main()
