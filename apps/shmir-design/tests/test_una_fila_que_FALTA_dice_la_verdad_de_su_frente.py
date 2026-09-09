"""Un frente que cierra con una corrida de FUERA no «necesita» su fichero.

Regla 5: escrito antes.

Reportado con la captura del gestor: la fila de `refseq_rna_human.fa` dice **«Falta, y
sin él no se puede cerrar: especificidad»**, y debajo ofrece el hueco de subida. Se
suelta el fichero de 320,9 MB y sale una X roja.

**Las dos mitades de esa fila son falsas desde el 2026-09-03**, y por motivos distintos:

  · **«sin él no se puede cerrar»** — dejó de ser cierto con la errata nº 68: un frente
    cierra IGUAL por fichero que por CORRIDA GUARDADA que cubra todo el panel, y lo fija
    `test_TODO_frente_con_almacen_se_puede_cerrar.py`. La frase gemela que vivía en
    `blast_readiness` se corrigió el 2026-09-04 **y ésta se quedó**: un arreglo en un
    emisor no protege al siguiente (principio nº 31);
  · **y ofrecer la subida** manda a conseguir cientos de MB que el filtro de la ventana
    **no puede usar**: `specificity.scanner_budget` tiene su techo medido en 5,45 MB
    (errata nº 84), así que una base de RefSeq de verdad se conecta y el filtro sale
    NOT_RUN con el motivo. Subirla para eso es la errata nº 40 por la otra puerta — la
    contradicción cobrada DESPUÉS de la descarga.

`especificidad` es el único caso hoy, y **no por ser un frente con almacén** —los otros
tres también lo tienen— sino porque **su corrida ocurre FUERA de la app**: `blast.Disabled`
dice que este software no lanza el BLAST y no puede. Los de seed y off-targets los calcula
la app, y para calcularlos necesita su fichero. Por eso se DECLARA en vez de deducirse.
"""

import unittest

from shmir_design import presentation


class TestLaDeclaracionEsCoherente(unittest.TestCase):

    def test_todo_frente_declarado_TIENE_almacen(self):
        # Un frente que no puede recoger una corrida no se cierra con ninguna, asi que
        # declararlo aqui seria decir que hay una salida que no existe.
        for frente in presentation.FRENTES_QUE_CIERRA_UNA_CORRIDA_DE_FUERA:
            with self.subTest(frente):
                self.assertIn(frente, presentation.STORE_FOR_FRONT)

    def test_y_no_estan_TODOS_los_frentes_con_almacen(self):
        # CONTROL: si estuvieran todos, esta distincion no distinguiria nada y la fila
        # diria lo mismo del transcriptoma, que la app SI necesita para calcular.
        self.assertLess(
            len(presentation.FRENTES_QUE_CIERRA_UNA_CORRIDA_DE_FUERA),
            len(presentation.STORE_FOR_FRONT),
        )

    def test_cada_uno_dice_DONDE_se_corre(self):
        for frente, texto in presentation.FRENTES_QUE_CIERRA_UNA_CORRIDA_DE_FUERA.items():
            with self.subTest(frente):
                self.assertTrue(texto.strip(), "sin motivo, es una lista sin argumento")


class TestLaFilaQueFALTA(unittest.TestCase):

    def _por_que(self, frentes):
        fila = {"que_desbloquea": "lo que sea", "nombre": "x.fa", "frentes": frentes}
        return presentation._por_que(fila, "FALTA", {})

    def test_la_de_especificidad_NO_dice_que_sin_el_no_se_puede_cerrar(self):
        texto = self._por_que(("especificidad",))
        self.assertNotIn("no se puede cerrar", texto)

    def test_dice_la_OTRA_via_con_su_nombre(self):
        texto = self._por_que(("especificidad",))
        self.assertIn("corrida", texto.lower())

    def test_y_avisa_del_TECHO_del_escaner_con_su_numero(self):
        # Sin la cifra, «grande» no es accionable: hay que poder mirar el fichero y
        # saber si sirve ANTES de subirlo.
        texto = self._por_que(("especificidad",))
        self.assertIn("5,45 MB", texto)

    def test_un_frente_que_la_app_SI_calcula_sigue_diciendolo(self):
        # CONTROL ADVERSARIO: sin el, «ninguna fila miente» y «se le quito el aviso a
        # todas» dan el mismo verde. El transcriptoma hace falta de verdad.
        texto = self._por_que(("offtarget_seed",))
        self.assertIn("no se puede cerrar", texto)


class TestElTechoSaleDeDONDESeMide(unittest.TestCase):

    def test_la_cifra_se_DERIVA_de_MAX_SCANNABLE_NT(self):
        # Principio nº 13: transcrita, envejece sola el dia que el escaner se acelere.
        from shmir_design.specificity import MAX_SCANNABLE_NT

        self.assertIn(
            f"{MAX_SCANNABLE_NT / 1e6:.2f}".replace(".", ",") + " MB",
            presentation.SCANNER_CEILING_NOTE,
        )


if __name__ == "__main__":
    unittest.main()
