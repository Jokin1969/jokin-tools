"""El modal de seed dice que el nucleo es una lista PRESTADA. Regla 5: escrito antes.

**La decision que incumplia** (2026-08-26, opcion **a**): fuera del raton el veredicto de
`CORE_ABUNDANT` sale igual, **marcado**, porque *«excluir por una lista prestada es
defendible; no decirlo, no»*. `CoreHit` implementa los tres estados —coincide, prestada,
no declarada— y `CoreHit.reason` añade el aviso.

**Ese aviso llegaba al filtro del tilado y NO al modal.** `mirna.py` pasa `species=`;
`seed_scan.run_scan` llamaba a `core_hits(nombres)` **sin especie** y solo usaba el
booleano `core`, asi que la razon con el aviso no se construia nunca. El modal es el
camino que ESCRIBE en el almacen, alimenta la ficha y produce el **bloque exportable**,
que es «material para defender la seleccion» y se lee sin la app delante.

Es el principio nº 33: el guardia estaba y la pregunta no le llegaba — `run_scan` TIENE
la especie en su firma.

**Medido antes de escribir esto**, corriendo el modal sobre los 103 sitios elegibles del
humano (206 consultas, `hsa-`, ventana 2-8): **un FAIL de nucleo**, la pasajera de
`3utr:671` contra `hsa-miR-128-3p`. Y buscando «otra especie», «murino», «raton»,
«mouse» y «autoriz» en TODO lo que el modal emite —destacados incluidos—: **ninguna
aparece**.
"""

import unittest
from pathlib import Path

from shmir_design.mirna import CORE_ABUNDANT, CORE_SPECIES, load_mature_fa
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design.resolve import resolve_anatomy
from shmir_design.seed_scan import SeedParams, run_scan
from shmir_design import presentation

DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"
MADUROS = DATOS / "mature.fa"
HUMANO = REFERENCES["NM_000311.5"]
HAY = MADUROS.is_file() and fixture_available(HUMANO)

#: El candidato humano cuya PASAJERA casa con un miARN del nucleo. Se DERIVA en el
#: propio test —no se da por bueno— y esta aqui para que el fallo diga cual se esperaba.
COLISION_HUMANA = "hsa-miR-128-3p"


def _scan(especie: str):
    secuencia = load_reference(HUMANO)
    anatomia = resolve_anatomy(
        name=especie, sequence=secuencia, genbank=DATOS / "NM_000311.5.gb",
    )
    corrida = presentation.page_run(
        species=especie, sequence=secuencia, anatomy=anatomia,
    )
    sitios = [s.best.start for s in corrida.selection.selection.sites]
    return run_scan(
        corrida.selection,
        mature=load_mature_fa(MADUROS, version="fixture del repositorio"),
        params=SeedParams.for_species(especie),
        species=especie, starts=sitios, guides=True, passengers=True,
    )


@unittest.skipUnless(HAY, "NOT_RUN: falta mature.fa o el fixture humano")
class TestElAvisoLLEGAalModal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scan = _scan("humano")
        cls.fails = [r for r in cls.scan.results if r.level == "FAIL"]

    def test_el_caso_existe_y_es_alcanzable_en_humano(self):
        # Sin esto, «el aviso sale» y «no hay ningun FAIL que avisar» dan el mismo verde.
        self.assertTrue(self.fails, "No hay ningun FAIL de nucleo en el humano")
        nombres = {c.name for r in self.fails for c in r.collisions if c.core}
        self.assertIn(COLISION_HUMANA, nombres)

    def test_el_BLOQUE_EXPORTABLE_dice_que_la_lista_es_de_otra_especie(self):
        # Es el artefacto que viaja: se lee sin la app delante.
        texto = self.scan.export_block().lower()
        self.assertIn("otra especie", texto)

    def test_y_nombra_la_especie_para_la_que_ESTA_autorizada(self):
        from shmir_design.species import resolve

        self.assertIn(
            resolve(CORE_SPECIES).scientific.lower(), self.scan.export_block().lower()
        )

    def test_el_aviso_va_PEGADO_al_veredicto_de_esa_hebra(self):
        # No en una nota general al principio: quien copia una linea se lleva el
        # veredicto sin la cabecera. Misma regla que el marco de las coordenadas.
        fila = self.fails[0].describe().lower()
        self.assertIn("otra especie", fila)

    def test_y_en_el_RATON_no_sale_ninguna_marca(self):
        # Control adversario: pegarlo siempre tambien pasaria los de arriba, y un aviso
        # que sale siempre deja de leerse.
        raton = _scan("raton")
        self.assertNotIn("otra especie", raton.export_block().lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
