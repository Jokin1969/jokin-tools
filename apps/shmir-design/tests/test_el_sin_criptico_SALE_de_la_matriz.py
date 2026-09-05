"""`mvm_sin_criptico` se RETIRA de la matriz, y la decisión que lo diseñó se queda.

**Decidido (2026-09-05)**, con las palabras con que se decidió: *«se diseñó para eliminar
el GTGAGCG, y ese sitio puntúa 0,0000 en las veinte construcciones con las dos
arquitecturas. Un intrón que arregla un problema que no existe»*.

Y la parte que importa del registro no es que sobrara, sino **por qué se creyó que hacía
falta**: *«el criterio de secuencia decía que GTGAGCG empataba con el donante legítimo
—score 5 contra 5 sobre `MAG|GTRAGT`— y un modelo entrenado sobre intrones reales lo
puntúa en cero. El consenso posicional sobrestima porque cuenta coincidencias sin
contexto»*.

**Retirar no es borrar.** La regla del desempate, la base elegida y el motivo se quedan
registrados: la variante está **a un gBlock** si el gel muestra que el MVM empalma mal.
Misma disciplina que un frente CERRADO, que sigue saliendo en el informe con su motivo —
borrarlo dejaría al siguiente lector sin saber si se resolvió o si nadie lo miró.

Regla 5: escrito antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import intron_design, introns  # noqa: E402


class TestSaleDeLaMatriz(unittest.TestCase):

    def test_esta_RETIRADO_y_lo_declara(self):
        self.assertTrue(introns.get("mvm_sin_criptico").retired)

    def test_y_los_otros_dos_NO(self):
        for nombre in ("mvm_actual", "intron_quimerico"):
            self.assertFalse(introns.get(nombre).retired, nombre)

    def test_el_motivo_dice_QUE_SE_MIDIO_y_sobre_cuantas(self):
        motivo = introns.get("mvm_sin_criptico").retired
        self.assertIn("GTGAGCG", motivo)
        self.assertIn("veinte", motivo)
        # No basta con «no hacía falta»: tiene que decir contra qué se comprobó.
        self.assertIn("SpliceAI", motivo)

    def test_y_dice_QUE_LO_DEVOLVERIA(self):
        # Un retirado sin condición de vuelta se lee como borrado.
        self.assertIn("gel", introns.get("mvm_sin_criptico").retired)

    def test_no_sale_en_los_DISPONIBLES_para_montar(self):
        self.assertNotIn("mvm_sin_criptico", [i.name for i in introns.buildable()])

    def test_pero_SIGUE_en_el_registro(self):
        # Retirar no es borrar: un intrón que no se ve no existe.
        self.assertIn("mvm_sin_criptico", introns.INTRONS)

    def test_y_sale_en_los_RETIRADOS_con_su_motivo(self):
        retirados = {i.name: i.retired for i in introns.retired()}
        self.assertIn("mvm_sin_criptico", retirados)
        self.assertTrue(retirados["mvm_sin_criptico"].strip())


class TestLaDecisionNO_se_borra(unittest.TestCase):
    """Está a un gBlock: si el gel dice que el MVM empalma mal, no se vuelve a razonar."""

    def test_la_regla_del_desempate_sigue_escrita(self):
        self.assertTrue(intron_design.TIEBREAK_MOTIF.strip())

    def test_y_el_criterio_entero_tambien(self):
        self.assertTrue(intron_design.INSERTION_RATIONALE.strip())

    def test_la_app_sigue_sabiendo_diseñarla(self):
        # Lo que se retira es su plaza en la matriz, no la capacidad de construirla.
        self.assertTrue(callable(intron_design.design_variant))


class TestLaLECCION_va_al_registro(unittest.TestCase):
    """*«Ésa es la lección, no que el intrón sobrara»*."""

    def test_el_motivo_nombra_al_consenso_posicional(self):
        motivo = introns.get("mvm_sin_criptico").retired
        self.assertIn("consenso", motivo.lower())

    def test_y_dice_POR_QUE_sobrestima(self):
        self.assertIn("sin contexto", introns.get("mvm_sin_criptico").retired)


if __name__ == "__main__":
    unittest.main()
