"""La contradicción del donante, el riesgo compartido, y por qué van las dos a síntesis.

Regla 5: escritos antes.

**Tres cosas que salen de la misma medida** y que este fichero fija:

1. **LA CONTRADICCIÓN DEL DONANTE, y se DERIVA.** Del mismo donante legítimo, SpliceAI
   dice que el quimérico es mejor (0,966 frente a 0,873) y el plegado dice lo contrario
   (0,533 frente a 0,889). No se promedian y no se reconcilian: **la secuencia dice que
   el sitio existe, el plegado dice si se puede usar.** Que discrepen es información, no
   ruido. Sale como DESTACADO propio y no como nota al pie, y se calcula cruzando los dos
   veredictos por elemento — no está escrito «el donante se contradice».

2. **VAN LAS DOS A SÍNTESIS. DECIDIDO (2026-09-07).** Ninguna medida las separa de forma
   unánime, así que la matriz deja de ser «uno gana»: son dos arquitecturas que hay que
   probar las dos, y el gel decide.

3. **EL RIESGO COMPARTIDO, en UN bloque.** El punto de ramificación es el menos accesible
   de los cuatro **en las dos** —o sea que es propiedad del elemento, no de un intrón— y
   la geometría donante→punto está **fuera de rango en las dos**. Los dos ejes miran el
   mismo sitio, así que es el candidato a **causa común** si el empalme falla en ambas.
   Separados en dos notas se leen como dos observaciones sueltas.
"""

import unittest

from shmir_design import intron_folding, presentation
from shmir_design.filters import FilterState
from shmir_design.folding import VIENNA_AVAILABLE

#: Filas de prueba con el plegado DE ACUERDO con SpliceAI en el donante: es el control
#: adversario de que la contradicción se deriva y no está escrita.
FILAS_DE_ACUERDO = tuple(
    {"construccion": f"c{i}", "intron": nombre, "estado": FilterState.PASS,
     "donante": donante, "punto_de_ramificacion": 0.30,
     "tracto_polipirimidinas": 0.50, "aceptor": 0.90}
    for i, (nombre, donante) in enumerate(
        (("mvm_actual", 0.40), ("intron_quimerico", 0.80))
    )
)


class TestLaContradiccionSE_DERIVA(unittest.TestCase):

    def test_si_el_plegado_COINCIDE_con_SpliceAI_no_hay_contradiccion(self):
        """El control adversario. Si saliera contradicción aquí, no estaría midiendo."""
        contradicciones = presentation.folding_contradictions(FILAS_DE_ACUERDO)
        self.assertEqual([c["elemento"] for c in contradicciones], [])

    def test_y_SpliceAI_solo_puntua_DOS_de_los_cuatro_y_se_dice(self):
        """El silencio no puede leerse como acuerdo.

        SpliceAI puntúa sitios de splicing: del punto de ramificación y del tracto no
        dice nada, así que ahí no hay contraste que hacer — y eso es distinto de que
        coincidan.
        """
        cruzados = set(presentation.SPLICEAI_ELEMENT_SCORES)
        self.assertEqual(cruzados, {"donante", "aceptor"})
        sin_cruzar = set(intron_folding.ELEMENTS) - cruzados
        texto = presentation.folding_highlights(FILAS_DE_ACUERDO)["contradiccion"]
        for elemento in sin_cruzar:
            self.assertIn(elemento, texto["texto"])


@unittest.skipUnless(VIENNA_AVAILABLE, "NOT_RUN: ViennaRNA no está instalado")
class TestSobreLasVEINTIDOS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.anatomy import Anatomy, RegionSource
        from shmir_design.reference import (
            REFERENCES, fixture_available, load_reference,
        )

        cls.raton = REFERENCES["NM_011170.3"]
        cls.hay = fixture_available(cls.raton)
        if not cls.hay:
            return
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.spliceai import build_panel

        secuencia = load_reference(cls.raton)
        anatomia = Anatomy.from_cds(
            cds=cls.raton.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        corrida = presentation.page_run(
            species="raton", sequence=secuencia, anatomy=anatomia
        )
        panel = build_panel(
            corrida.selection,
            intron_names=("mvm_actual", "intron_quimerico"),
            scaffold=SGEP_SCAFFOLD,
        )
        cls.filas = presentation.splice_folding_rows(
            panel.constructions,
            module_of=lambda c: presentation.splice_module_of(
                c, selection=corrida.selection, scaffold=SGEP_SCAFFOLD
            ),
        )

    def setUp(self):
        if not self.hay:
            self.skipTest("NOT_RUN: falta data/reference/NM_011170.3.fa")

    def test_la_contradiccion_ES_el_DONANTE_y_solo_el_donante(self):
        contradicciones = presentation.folding_contradictions(self.filas)
        self.assertEqual([c["elemento"] for c in contradicciones], ["donante"])
        fila = contradicciones[0]
        self.assertEqual(fila["gana_spliceai"], "intron_quimerico")
        self.assertEqual(fila["gana_plegado"], "mvm_actual")

    def test_y_sale_DESTACADA_con_la_lectura_de_las_dos_preguntas(self):
        destacado = presentation.folding_highlights(self.filas)["contradiccion"]
        self.assertTrue(destacado["activo"])
        texto = destacado["texto"].lower()
        self.assertIn("la secuencia dice que el sitio existe", texto)
        self.assertIn("el plegado dice si se puede usar", texto)
        self.assertIn("no se promedian", texto)
        # Y las cuatro cifras, o no se puede discutir.
        for cifra in ("0,966", "0,873", "0,533", "0,889"):
            self.assertIn(cifra, destacado["texto"])

    def test_el_RIESGO_COMPARTIDO_sale_en_UN_solo_bloque(self):
        """Los dos ejes juntos: son el mismo sitio visto dos veces."""
        riesgo = presentation.shared_branch_risk(self.filas)
        self.assertEqual(riesgo["elemento"], "punto_de_ramificacion")
        # (a) menos accesible en LAS DOS — propiedad del elemento.
        self.assertEqual(
            sorted(riesgo["menos_accesible_en"]),
            ["intron_quimerico", "mvm_actual"],
        )
        # (b) geometría fuera de rango en LAS DOS, DERIVADA y no escrita.
        self.assertEqual(
            sorted(riesgo["geometria_atipica_en"]),
            ["intron_quimerico", "mvm_actual"],
        )
        # Y las dos mitades en el MISMO texto, con la lectura que las une.
        self.assertIn("causa común", riesgo["texto"].lower())
        self.assertIn("los dos ejes", riesgo["texto"].lower())

    def test_y_ese_riesgo_es_un_DESTACADO_del_modal(self):
        destacado = presentation.folding_highlights(self.filas)["riesgo_compartido"]
        self.assertTrue(destacado["activo"])
        self.assertIn("causa común", destacado["texto"].lower())


class TestVanLasDosASintesis(unittest.TestCase):
    """La matriz deja de ser «uno gana». DECIDIDO (2026-09-07)."""

    def test_la_decision_esta_escrita_con_su_fecha(self):
        from shmir_design.introns import BOTH_ARCHITECTURES_GO

        self.assertIn("2026-09-07", BOTH_ARCHITECTURES_GO)
        self.assertIn("las dos", BOTH_ARCHITECTURES_GO.lower())
        self.assertIn("gel", BOTH_ARCHITECTURES_GO.lower())

    def test_y_sale_en_la_nota_de_arquitecturas(self):
        from shmir_design.introns import BOTH_ARCHITECTURES_GO

        self.assertIn(BOTH_ARCHITECTURES_GO, presentation.intron_architecture_note())

    def test_y_en_el_INFORME_descargable(self):
        # Decide qué se sintetiza: no puede vivir sólo en la página (principio nº 23).
        from shmir_design.informe_doc import _seccion_arquitecturas
        from shmir_design.introns import BOTH_ARCHITECTURES_GO

        texto = "\n".join(b.text for b in _seccion_arquitecturas().blocks)
        self.assertIn(BOTH_ARCHITECTURES_GO, texto)

    def test_el_RIESGO_COMPARTIDO_entra_en_el_INFORME(self):
        """Dice dónde mirar PRIMERO si el empalme falla, y eso se lee sin la app delante."""
        from shmir_design.informe_doc import _seccion_arquitecturas

        texto = "\n".join(b.text for b in _seccion_arquitecturas().blocks)
        self.assertIn("causa común", texto.lower())
        self.assertIn("punto_de_ramificacion", texto)

    def test_lo_REGISTRADO_y_lo_VIVO_pasan_por_LA_MISMA_regla(self):
        """El informe no puede plegar en cada repintado, así que lee la medida escrita.

        Lo que NO puede pasar es que sea otra regla: las medias registradas se pasan por
        las MISMAS funciones, así que el informe y el modal no pueden discrepar en la
        lectura — sólo en de dónde sale el número, y eso lo revalida el test que
        recalcula las medias de las 22.
        """
        filas = presentation.recorded_folding_rows()
        self.assertEqual(
            [c["elemento"] for c in presentation.folding_contradictions(filas)],
            ["donante"],
        )
        self.assertEqual(
            intron_folding.weakest_element(filas), "punto_de_ramificacion"
        )

    def test_la_TABLA_del_informe_se_deriva_de_las_medias(self):
        """Una fila y su ganador no pueden decir cosas distintas: salen del mismo sitio."""
        por_elemento = {f[0]: f for f in presentation.INTRON_FOLDING_AXES}
        for elemento, medias in presentation.INTRON_FOLDING_MEANS.items():
            fila = por_elemento[elemento]
            mejor = max(medias, key=lambda a: medias[a])
            self.assertEqual(fila[3], mejor, elemento)

    def test_la_pagina_pinta_los_destacados_del_plegado(self):
        from pathlib import Path

        fuente = Path("ui/streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("folding_highlights", fuente)


if __name__ == "__main__":
    unittest.main()
