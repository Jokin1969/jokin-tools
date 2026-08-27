"""Los valores por defecto que nadie avisaba si no se cambiaban.

Regla 5: escritos antes.

`DEFAULT_PREFIXES`, el `mmu-` de `seed_scan` y el `txid10090` de `blast` eran el mismo
patron que `rmsk_mouse.out` conectado por rol: un valor que funciona callado y que sobre
otra especie produce un resultado con la forma correcta. Un `txid10090` sobre una
secuencia de conejo tiene que ser IMPOSIBLE, no improbable.

Lo que se fija aqui:

  - el UNICO origen de los tres es `species.resolve()`, y una especie sin el valor
    declarado ABORTA diciendo donde se declara;
  - el nucleo de abundancia sigue corriendo fuera de raton —excluir por una lista
    prestada es defendible— pero MARCADO `LISTA_DE_OTRA_ESPECIE`;
  - `specificity` acepta cualquier taxid DECLARADO: la validacion es que corresponda a
    la especie, no que este en una lista blanca;
  - el vector del proyecto es el murino y la app lo DICE en vez de emitir el modulo con
    las piezas equivocadas.
"""

import unittest

from shmir_design import blast, blocks, mirna, seed_scan, specificity, species
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState

CONEJO = "Oryctolagus cuniculus"


class TestLosAliasVanDECLARADOS(unittest.TestCase):

    def test_raton_y_mouse_son_LA_MISMA_especie(self):
        self.assertEqual(species.resolve("raton").slug, "mouse")
        self.assertEqual(species.resolve("Mus musculus").slug, "mouse")

    def test_humano_y_human_tambien(self):
        self.assertEqual(species.resolve("humano").slug, "human")

    def test_y_van_en_una_tabla_no_deducidos(self):
        self.assertIn("raton", species.ALIASES)
        self.assertEqual(species.ALIASES["raton"], "mouse")

    def test_una_especie_desconocida_NO_se_convierte_en_otra(self):
        self.assertEqual(species.resolve(CONEJO).slug, "oryctolagus_cuniculus")
        self.assertFalse(species.resolve(CONEJO).known)


class TestElPrefijoDeMiRBase(unittest.TestCase):

    def test_sale_de_species_y_de_ningun_otro_sitio(self):
        self.assertEqual(species.mirbase_prefix("raton"), "mmu-")
        self.assertEqual(species.mirbase_prefix("humano"), "hsa-")

    def test_una_especie_sin_prefijo_declarado_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as caja:
            species.mirbase_prefix(CONEJO)
        texto = str(caja.exception)
        self.assertIn("mirbase.org", texto)
        self.assertIn("species.SPECIES", texto)

    def test_y_el_motivo_dice_por_que_no_se_deduce(self):
        with self.assertRaises(ShmirDesignError) as caja:
            species.mirbase_prefix(CONEJO)
        self.assertIn("CERO colisiones", str(caja.exception))

    def test_SeedParams_ya_NO_trae_mmu_por_defecto(self):
        self.assertIsNone(seed_scan.SeedParams().species_prefix)

    def test_y_usarlo_sin_declararlo_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            seed_scan.SeedParams().require_prefix()

    def test_VACIO_y_SIN_DECLARAR_son_dos_valores_distintos(self):
        """`""` = todas las especies, elegido. `None` = nadie lo ha dicho."""
        self.assertEqual(seed_scan.SeedParams(species_prefix="").require_prefix(), "")
        self.assertTrue(seed_scan.SeedParams(species_prefix="").declared)
        self.assertFalse(seed_scan.SeedParams().declared)

    def test_la_especie_NO_cuenta_como_ajuste_modificado(self):
        humano = seed_scan.SeedParams.for_species("humano")
        self.assertEqual(humano.modified(), ())
        self.assertTrue(humano.is_standard)


class TestElTaxid(unittest.TestCase):

    def test_sale_de_species_y_de_ningun_otro_sitio(self):
        self.assertEqual(specificity.taxid_for("raton"), "txid10090")
        self.assertEqual(specificity.taxid_for("human"), "txid9606")

    def test_BlastParams_ya_NO_trae_txid10090_por_defecto(self):
        self.assertEqual(blast.BlastParams().entrez_query, "")

    def test_y_generar_la_orden_sin_organismo_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as caja:
            blast.BlastParams().command(query_path="q.fa")
        self.assertIn("species.taxid", str(caja.exception))

    def test_una_especie_sin_taxid_declarado_ABORTA_al_pedirlo(self):
        with self.assertRaises(ShmirDesignError) as caja:
            blast.BlastParams.for_species(CONEJO)
        self.assertIn("Taxonomy Browser", str(caja.exception))

    def test_y_el_motivo_dice_QUE_pasaria_con_el_taxid_de_otra(self):
        with self.assertRaises(ShmirDesignError) as caja:
            specificity.taxid_for(CONEJO)
        self.assertIn("forma correcta", str(caja.exception))


class TestTAXIDS_YA_NO_ES_UNA_LISTA_BLANCA(unittest.TestCase):
    """La validacion es «tiene taxid declarado», no «esta en una lista de dos»."""

    def test_el_frente_ya_no_esta_cerrado_a_DOS_especies(self):
        declaradas = {
            nombre for nombre, e in species.SPECIES.items() if e.taxid
        }
        self.assertEqual(declaradas, {"mouse", "human"})
        # Lo que importa no es cuantas hay hoy, sino que AÑADIR una la habilite sin
        # tocar `specificity`: la lista blanca ya no existe.
        nueva = species.Species(
            "Oryctolagus cuniculus", "conejo_de_prueba", "xxx-", "txid9986", "oryCun2"
        )
        species.SPECIES["conejo_de_prueba"] = nueva
        try:
            self.assertEqual(specificity.taxid_for("conejo_de_prueba"), "txid9986")
            self.assertIn(
                "txid9986",
                specificity.blast_command("q.fa", "conejo_de_prueba"),
            )
        finally:
            del species.SPECIES["conejo_de_prueba"]


class TestElNucleoDeAbundanciaFueraDeRATON(unittest.TestCase):
    """Opcion (a): el veredicto sale, MARCADO. Excluir por una lista prestada es
    defendible; no decirlo, no."""

    def test_con_raton_no_lleva_marca(self):
        hit = mirna.core_hits(["mmu-miR-124-3p"], species="raton")[0]
        self.assertFalse(hit.borrowed)
        self.assertNotIn(mirna.BORROWED_LIST_MARK, hit.reason)

    def test_con_otra_especie_el_FAIL_SIGUE_saliendo(self):
        hits = mirna.core_hits(["ocu-let-7a-5p"], species=CONEJO)
        self.assertEqual(len(hits), 1)

    def test_pero_MARCADO_como_lista_de_otra_especie(self):
        hit = mirna.core_hits(["ocu-let-7a-5p"], species=CONEJO)[0]
        self.assertTrue(hit.borrowed)
        self.assertIn(mirna.BORROWED_LIST_MARK, hit.reason)

    def test_y_el_motivo_dice_que_PUEDE_acertar(self):
        hit = mirna.core_hits(["ocu-let-7a-5p"], species=CONEJO)[0]
        self.assertIn("Puede que acierte", hit.reason)
        self.assertIn("let-7", hit.reason)

    def test_sin_especie_declarada_hay_un_TERCER_estado(self):
        """No haber podido comprobarlo no es que coincida."""
        hit = mirna.core_hits(["mmu-miR-124-3p"])[0]
        self.assertFalse(hit.declared)
        self.assertFalse(hit.borrowed)
        self.assertIn(mirna.UNDECLARED_SPECIES_MARK, hit.reason)

    def test_la_lista_declara_PARA_QUE_especie_esta_autorizada(self):
        self.assertEqual(mirna.CORE_SPECIES, "mouse")


class TestElIndiceDeMaduros(unittest.TestCase):

    def test_por_defecto_se_indexa_TODO_el_fichero(self):
        """`("mmu-","hsa-")` dejaba fuera del indice a las demas SIN AVISAR."""
        self.assertEqual(mirna.DEFAULT_PREFIXES, ())

    def test_los_dos_historicos_conservan_su_nombre(self):
        self.assertEqual(mirna.HISTORICAL_PREFIXES, ("mmu-", "hsa-"))


class TestElVectorEsMURINO_Y_LA_APP_LO_DICE(unittest.TestCase):

    def test_con_raton_aplica(self):
        self.assertTrue(blocks.vector_applies_to("raton").applies)

    def test_con_otra_especie_NO_APLICA(self):
        aplicabilidad = blocks.vector_applies_to(CONEJO)
        self.assertFalse(aplicabilidad.applies)
        self.assertIs(aplicabilidad.state, FilterState.NO_APLICA)

    def test_y_el_motivo_nombra_las_CUATRO_cosas_que_no_se_emiten(self):
        nota = blocks.vector_applies_to(CONEJO).note
        for pieza in ("MÓDULO", "CASSETTE", "HOJA DE PEDIDO", "CONTROL SIN INTRÓN"):
            self.assertIn(pieza, nota)

    def test_y_dice_que_NO_se_parametriza_sino_que_se_sustituye(self):
        nota = blocks.vector_applies_to(CONEJO).note
        self.assertIn("no se parametriza", nota)
        self.assertIn("OTRO plásmido", nota)

    def test_el_plasmido_va_NOMBRADO(self):
        self.assertIn("mouse_PrP", blocks.VECTOR_DESCRIPTION)

    def test_presentation_NO_emite_bloques_para_otra_especie(self):
        from shmir_design import presentation
        from shmir_design.reference import REFERENCES, fixture_available, load_3utr

        raton = REFERENCES["NM_011170.3"]
        if not fixture_available(raton):
            self.skipTest("NOT_RUN: falta el fixture del raton")
        from shmir_design.scaffold import SGEP_SCAFFOLD
        from shmir_design.selection import SelectionConfig, select_from_report
        from shmir_design.tiling import tile_utr

        informe = tile_utr(load_3utr(raton))
        seleccion = select_from_report(informe, SelectionConfig(n_candidates=3))
        self.assertTrue(
            presentation.block_rows(seleccion, SGEP_SCAFFOLD, species="raton")
        )
        self.assertEqual(
            presentation.block_rows(seleccion, SGEP_SCAFFOLD, species=CONEJO), []
        )

    def test_y_la_pagina_enseña_el_motivo_al_lado(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("vector_note", fuente)


if __name__ == "__main__":
    unittest.main()
