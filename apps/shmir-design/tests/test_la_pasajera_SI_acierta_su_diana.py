"""Reconocer la propia diana y contar un off-target son DOS umbrales, no uno.

**Salió al verificar la corrida de 88 del 2026-09-05**: la nota «esta consulta no tiene
NINGÚN acierto contra su propia diana — eso NO es una buena noticia» saltaba en **75 de
las 88 pasajeras**. No es una propiedad de esos candidatos: es que el mínimo con el que
se reconoce la propia diana estaba derivado de la sonda **sin mirar la hebra**.

**La pasajera pierde DOS posiciones contra su propia diana, y las dos son CONVENIO**:

- su **posición 1** es el desapareamiento deliberado del bulge basal;
- su **posición 22** es el complemento de la posición 1 de la guía, que el pipeline
  **fuerza a T** para que AGO2 cargue la hebra — así que sólo casa con el genoma cuando
  el genoma ya tenía una T ahí.

Medido sobre las 88: la pasajera alinea **20 nt** contra su diana en 75 casos y 21 en los
13 en que la T ya estaba. Con `ALLOWED_TRUNCATION = 1` para las dos hebras, esas 75 no
encontraban su blanco y la app emitía una alarma sobre una construcción impecable.

**Y son dos preguntas, no un umbral mal puesto** (principio nº 27): los dos convenios se
definen respecto de la diana PRETENDIDA, así que contra un off-target no existen. Lo que
se afloja es el mínimo para **reconocer la propia diana**; el de contar un off-target como
grave no se toca — y por eso los veredictos no se mueven.

Regla 5: escrito antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import specificity  # noqa: E402


class Acierto:
    """Lo mínimo que `judge_hits` necesita, con los nombres que lee."""

    def __init__(self, subject, aligned, mismatches=0, antisense=True):
        self.transcript = self.subject = subject
        self.aligned = aligned
        self.mismatches = mismatches
        self.antisense = antisense

    def describe(self):
        return f"{self.subject} {self.aligned} nt"


DIANA = ("NM_011170.3", "NM_001278256.1")


class TestLosDosConvenios(unittest.TestCase):
    """Lo que se afloja se DERIVA de los convenios ya declarados, no es un número."""

    def test_estan_declarados_los_dos(self):
        self.assertEqual(specificity.OWN_TARGET_TRUNCATION["guia"], 1)
        self.assertEqual(specificity.OWN_TARGET_TRUNCATION["pasajera"], 2)

    def test_y_el_motivo_los_NOMBRA(self):
        texto = specificity.WHY_THE_PASSENGER_LOSES_TWO
        self.assertIn("bulge", texto.lower())
        self.assertIn("AGO2", texto)

    def test_una_hebra_no_declarada_ABORTA(self):
        # Deducirla daría un umbral con la forma correcta y el convenio equivocado.
        with self.assertRaises(Exception):
            specificity.own_target_minimum(22, strand="tercera")


class TestLaPasajeraENCUENTRA_su_diana(unittest.TestCase):

    def _juicio(self, hebra, alineado):
        hits = [Acierto(DIANA[0], alineado,
                        antisense=specificity.EXPECTED_ORIENTATION[hebra])]
        return specificity.judge_hits(
            hits, target_accessions=DIANA, min_aligned=21, strand=hebra,
            probe_length=22, expected_antisense=specificity.EXPECTED_ORIENTATION[hebra],
        )

    def test_con_20_nt_la_pasajera_SI_la_encuentra(self):
        # El caso de 75 de las 88: pierde sus dos posiciones de convenio.
        self.assertFalse(self._juicio("pasajera", 20).sin_diana)

    def test_y_la_GUIA_con_20_nt_NO(self):
        # La guía sólo pierde su posición 1: 20 nt es un acierto recortado de más.
        self.assertTrue(self._juicio("guia", 20).sin_diana)

    def test_la_guia_con_21_si(self):
        self.assertFalse(self._juicio("guia", 21).sin_diana)


class TestElOFFTARGET_no_se_afloja(unittest.TestCase):
    """Los convenios son respecto de la diana PRETENDIDA: fuera no existen."""

    def test_un_ajeno_de_20_nt_NO_cuenta_como_grave(self):
        ajeno = [Acierto("NM_999999.1", 20, antisense=False)]
        fallo = specificity.judge_hits(
            ajeno, target_accessions=DIANA, min_aligned=21, strand="pasajera",
            probe_length=22,
        )
        self.assertEqual(fallo.graves, ())

    def test_y_uno_de_21_SI(self):
        ajeno = [Acierto("NM_999999.1", 21, antisense=False)]
        fallo = specificity.judge_hits(
            ajeno, target_accessions=DIANA, min_aligned=21, strand="pasajera",
            probe_length=22,
        )
        self.assertEqual(len(fallo.graves), 1)


if __name__ == "__main__":
    unittest.main()
