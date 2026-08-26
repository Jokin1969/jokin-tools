"""La direccion de la escala se DERIVA del dato, y el andamio manda sobre el uso.

Regla 5: escritos antes de la funcionalidad.

Dos cosas que un score externo no puede traer implicitas:

1. **La direccion.** Nadie declara en el fichero si menor es mejor. Lo que si se puede
   comprobar es que el ORDEN DE LAS FILAS sea monotono en el score: si el fichero viene
   en el orden de ranking de la fuente, eso fija la direccion. Si no lo es, el orden de
   las filas no es un ranking y no se puede sacar ningun rank de el.
2. **El andamio.** Un score de procesamiento medido sobre miR-30a no ordena candidatos
   de miR-E: miR-E existe porque procesa distinto (Fellmann 2013), asi que el sesgo cae
   justo sobre lo que el score dice medir.

Datos reales: el fichero de la corrida manual sobre el 3'UTR de Prnp murino.
"""

import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.external_score import (
    EVIDENCE,
    ScoreSource,
    check_orderable,
    file_order_direction,
    lower_is_better,
)

SCORES = Path(__file__).resolve().parent.parent / "data" / "reference" / "mirarchitect_prnp_raton.tsv"


class TestDireccionDerivada(unittest.TestCase):

    def test_orden_ascendente_significa_menor_es_mejor(self):
        self.assertTrue(file_order_direction([("a", 1.0), ("b", 2.0), ("c", 9.0)]))

    def test_orden_descendente_significa_mayor_es_mejor(self):
        self.assertFalse(file_order_direction([("a", 9.0), ("b", 2.0), ("c", 1.0)]))

    def test_un_orden_que_no_es_monotono_aborta(self):
        # Entonces el orden de las filas no es un ranking, y sacar un rank de el seria
        # inventarselo.
        with self.assertRaises(ShmirDesignError) as caja:
            file_order_direction([("a", 1.0), ("b", 9.0), ("c", 2.0)])
        self.assertIn("no es monotono", str(caja.exception))

    def test_los_empates_no_rompen_la_monotonia(self):
        self.assertTrue(file_order_direction([("a", 1.0), ("b", 1.0), ("c", 2.0)]))

    def test_con_una_sola_fila_no_se_puede_derivar(self):
        with self.assertRaises(ShmirDesignError):
            file_order_direction([("a", 1.0)])

    def test_la_derivada_tiene_que_coincidir_con_la_registrada(self):
        # Si el fichero dice una cosa y el registro otra, uno de los dos esta mal y no
        # se elige por nuestra cuenta.
        with self.assertRaises(ShmirDesignError) as caja:
            check_orderable(
                ScoreSource.MANUAL_MIRARCHITECT,
                derived_lower_is_better=False,
                file_scaffold="miR-E", design_scaffold="miR-E",
            )
        self.assertIn("direccion", str(caja.exception).lower())


class TestEvidencia(unittest.TestCase):

    def test_la_direccion_de_miRarchitect_esta_registrada_con_su_evidencia(self):
        evidencia = EVIDENCE[ScoreSource.MANUAL_MIRARCHITECT]
        self.assertTrue(evidencia.lower_is_better)
        self.assertGreaterEqual(len(evidencia.pairs), 5)

    def test_la_evidencia_es_monotona_consigo_misma(self):
        # Si alguien mete un par que rompe la monotonia, la evidencia deja de serlo.
        evidencia = EVIDENCE[ScoreSource.MANUAL_MIRARCHITECT]
        puestos = [r for r, _ in evidencia.pairs]
        scores = [s for _, s in evidencia.pairs]
        self.assertEqual(puestos, sorted(puestos))
        self.assertEqual(scores, sorted(scores))

    def test_lower_is_better_sigue_abortando_para_una_fuente_no_registrada(self):
        with self.assertRaises(ShmirDesignError):
            lower_is_better(ScoreSource.SPLASHRNA_FEATURES)


class TestAndamio(unittest.TestCase):

    def test_el_mismo_andamio_deja_ordenar(self):
        check_orderable(
            ScoreSource.MANUAL_MIRARCHITECT,
            derived_lower_is_better=True,
            file_scaffold="miR-E", design_scaffold="miR-E",
        )

    def test_un_andamio_distinto_prohibe_ordenar(self):
        with self.assertRaises(ShmirDesignError) as caja:
            check_orderable(
                ScoreSource.MANUAL_MIRARCHITECT,
                derived_lower_is_better=True,
                file_scaffold="miR-30a", design_scaffold="miR-E",
            )
        texto = str(caja.exception)
        self.assertIn("miR-30a", texto)
        self.assertIn("miR-E", texto)

    def test_el_mensaje_explica_por_que_y_no_solo_que(self):
        with self.assertRaises(ShmirDesignError) as caja:
            check_orderable(
                ScoreSource.MANUAL_MIRARCHITECT,
                derived_lower_is_better=True,
                file_scaffold="miR-30a", design_scaffold="miR-E",
            )
        self.assertIn("procesamiento", str(caja.exception).lower())

    def test_sin_andamio_declarado_no_se_supone_que_coincide(self):
        with self.assertRaises(ShmirDesignError):
            check_orderable(
                ScoreSource.MANUAL_MIRARCHITECT,
                derived_lower_is_better=True,
                file_scaffold=None, design_scaffold="miR-E",
            )


@unittest.skipUnless(SCORES.is_file(), f"NOT_RUN: falta {SCORES.name}")
class TestSobreElFicheroReal(unittest.TestCase):

    def scores(self):
        return [
            (l.split("\t")[0], float(l.split("\t")[1]))
            for l in SCORES.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("guia_dna")
        ]

    def test_el_fichero_viene_en_orden_de_ranking(self):
        # 25 filas en orden estrictamente creciente de score no es casualidad: el
        # fichero viene en el orden de la fuente, y ese orden es el ranking.
        self.assertTrue(file_order_direction(self.scores()))

    def test_y_eso_confirma_que_menor_es_mejor(self):
        self.assertEqual(
            file_order_direction(self.scores()),
            EVIDENCE[ScoreSource.MANUAL_MIRARCHITECT].lower_is_better,
        )


if __name__ == "__main__":
    unittest.main()


class TestNombreDelAndamio(unittest.TestCase):
    """El andamio del proyecto se llama `miR-E / SGEP`; el fichero dira `miR-E`."""

    def test_miR_E_y_miR_E_SGEP_son_el_mismo(self):
        check_orderable(
            ScoreSource.MANUAL_MIRARCHITECT, derived_lower_is_better=True,
            file_scaffold="miR-E", design_scaffold="miR-E / SGEP",
        )

    def test_miR_30a_no_es_miR_E_SGEP(self):
        with self.assertRaises(ShmirDesignError):
            check_orderable(
                ScoreSource.MANUAL_MIRARCHITECT, derived_lower_is_better=True,
                file_scaffold="miR-30a", design_scaffold="miR-E / SGEP",
            )

    def test_no_se_acerca_por_parecido(self):
        # `miR-30` y `miR-30a` NO son el mismo andamio.
        with self.assertRaises(ShmirDesignError):
            check_orderable(
                ScoreSource.MANUAL_MIRARCHITECT, derived_lower_is_better=True,
                file_scaffold="miR-30", design_scaffold="miR-30a",
            )
