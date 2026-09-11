"""La diana humana esta declarada, y lo que su procedencia AFIRMA se comprueba.

**De donde sale.** El 2026-09-09 se corrio el BLAST del panel humano y el frente de
especificidad seguia sin cerrar: `NO_CIERRA` en los once. La corrida estaba bien —se leia,
daba veredicto, parametros estandar— y lo que faltaba era la entrada del humano en
`data/diana/variantes.toml`, **ausente a proposito** hasta que hubiera una corrida de la
que sacar las variantes. Declarada el 2026-09-11 con los accessions de esa corrida.

**Lo que este fichero comprueba NO es que la lista sea correcta** —eso pide RefSeq y aqui
no hay red (regla 4)— sino algo que si se puede: que **la unica afirmacion contrastable de
su procedencia lo sea de verdad**. La procedencia dice que `NM_000311.5` es la referencia
versionada del panel humano; eso vive en `reference.REFERENCES` y se cruza.

Es el principio nº 11 aplicado a una tabla de datos: cuando la prosa afirma un hecho que
el codigo tiene, o lo emite el generador o lo contrasta un test — porque la prosa es la
que alguien va a leer, y la que se queda atras.

Python 3.11+, solo biblioteca estandar (regla 6).
"""

import tomllib
import unittest
from pathlib import Path

from shmir_design import reference
from shmir_design.species import resolve
from shmir_design.specificity import target_accessions

TABLA = (
    Path(__file__).resolve().parent.parent / "data" / "diana" / "variantes.toml"
)


def tabla() -> dict:
    with TABLA.open("rb") as f:
        return tomllib.load(f)


class TestElHumanoEstaDeclarado(unittest.TestCase):

    def test_target_accessions_ya_no_aborta(self):
        self.assertTrue(target_accessions("human"))

    def test_y_el_REPRESENTANTE_es_la_referencia_versionada(self):
        """La afirmacion contrastable de la procedencia, contrastada.

        No se escribe `NM_000311.5` como valor esperado: se le PIDE a `REFERENCES` cual es
        el transcrito humano del proyecto (principio nº 13). Si algun dia la referencia
        cambia de version, esto lo dice en vez de dejar la tabla citando una vieja.
        """
        humano = [
            ref.accession for ref in reference.REFERENCES.values()
            if resolve(ref.organism).slug == "human"
        ]
        self.assertEqual(len(humano), 1, f"referencias humanas: {humano}")
        self.assertIn(humano[0], target_accessions("human"))

    def test_todas_las_accessions_son_de_RefSeq_curado(self):
        """`NM_` es lo que RefSeq Curated trae. Es la forma, no la existencia.

        Un `XM_`/`XR_` aqui seria un PREDICHO, y la propia procedencia declara que la
        fuente no los trae: si apareciera uno, la lista y su procedencia estarian
        diciendo cosas distintas.
        """
        for accession in target_accessions("human"):
            with self.subTest(accession):
                self.assertTrue(accession.startswith("NM_"))

    def test_no_hay_accessions_repetidas(self):
        accessions = target_accessions("human")
        self.assertEqual(len(accessions), len(set(accessions)))


class TestLaTablaExigeLoMISMOaTODAS(unittest.TestCase):
    """Derivado de la tabla: una especie nueva queda cubierta sin tocar este test."""

    def test_cada_especie_declara_procedencia_Y_verificado(self):
        for especie, entrada in tabla().items():
            with self.subTest(especie):
                self.assertTrue(entrada.get("accessions"))
                self.assertTrue((entrada.get("procedencia") or "").strip())
                # `verificado` dice QUE SE HA COMPROBADO Y QUE NO. Sin el, una lista
                # aportada de memoria y una cruzada contra material visto se leen igual.
                self.assertTrue(
                    (entrada.get("verificado") or "").strip(),
                    f"{especie} no declara `verificado`",
                )

    def test_y_el_representante_de_cada_una_es_su_referencia_versionada(self):
        """El mismo cruce para TODAS, no solo para el humano.

        Es lo que hace que esto sea un mecanismo y no un arreglo de un caso: el dia que
        entre una tercera especie, su representante se cruza sola.
        """
        for ref in reference.REFERENCES.values():
            slug = resolve(ref.organism).slug
            if slug not in tabla():
                continue  # sin diana declarada: ese caso lo cubre `especie_sin_diana`
            with self.subTest(slug):
                self.assertIn(ref.accession, target_accessions(slug))


if __name__ == "__main__":
    unittest.main()
