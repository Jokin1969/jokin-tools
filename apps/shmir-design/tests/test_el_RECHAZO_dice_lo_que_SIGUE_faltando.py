"""Un rechazo por fichero repetido dice ADEMAS lo que sigue faltando.

Regla 5: escrito antes.

**Reportado el 2026-09-07**, con el aborto en pantalla y en estas palabras: *«resulta que
ahora no te deja seguir»*. El guardia hacia lo que debe —el fichero soltado es byte a byte
el de una corrida ya registrada— y aun asi la lectura fue esa, y la lectura importa: quien
lo suelta estaba intentando **cubrir a `3utr:359`**, que entro en el panel DESPUES de esa
corrida.

El mensaje del almacen dice **que no es una corrida nueva** y **por que**. Lo que no puede
decir es si la corrida anterior cubre lo que se venia a cubrir: `ProjectStore.append` no
sabe cual es el panel de hoy — y no deberia saberlo, es la capa que escribe el log.

**Principio nº 47: la salida va donde esta el BLOQUEO.** El bloqueo esta en el boton de
guardar, asi que la cobertura pendiente se emite ahi, junto al aborto. Sin ella el usuario
tiene que ir a buscar la tarjeta del frente, en otra parte de la pagina, para enterarse de
que la corrida vieja deja fuera justo a los dos que le faltan.

Y se DERIVA de `panel_states_by_front`, que es el unico sitio donde se decide si un frente
esta contestado (errata nº 68). Recalcularlo aqui seria la segunda regla para la misma
pregunta.
"""

import unittest

from shmir_design import coords, presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.filters import FilterResult, FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_reference

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)
ESPECIE = "raton"


def _corrida():
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO,
    )
    return presentation.page_run(
        species=ESPECIE, sequence=secuencia, anatomy=anatomia
    )


class _Par:
    def __init__(self, start, intron):
        self.candidate_start = int(start)
        self.intron = intron


class _Scan:
    def __init__(self, pares):
        self.pairs = tuple(pares)


class _CorridaDeEmpalme:
    def __init__(self, cubiertos):
        self.scan = _Scan(_Par(s, "mvm_actual") for s in cubiertos)
        self.candidate_frame = coords.tiled_frame(None)


class _AlmacenDeEmpalme:
    """La superficie minima de `SpliceStore`: `latest` y `verdict_for(start, intron)`.

    Se copia la forma REAL —la corrida con sus pares dentro— y no una comoda: el camino
    que resuelve este frente pasa por `scan.pairs`, asi que un doble que contestara
    directamente probaria otra cosa. Un cliente que no se parece al real no prueba nada.
    """

    def __init__(self, cubiertos):
        self._cubiertos = frozenset(int(c) for c in cubiertos)
        self.latest = _CorridaDeEmpalme(sorted(self._cubiertos))
        self.runs = (self.latest,)

    def verdict_for(self, start, intron, *, frame=None):
        return FilterResult(
            name="empalme_sitios", state=FilterState.PASS, reason="corrida de prueba",
        )


@unittest.skipUnless(HAY, "falta el fixture del raton")
class TestLoQueSigueFaltando(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.panel = [c.start for c in cls.corrida.selection.selection.chosen]

    def _pendiente(self, cubiertos):
        return presentation.pending_after_duplicate(
            self.corrida.tiling, self.corrida.selection,
            species=ESPECIE, front="empalme_sitios",
            stores={"splice": _AlmacenDeEmpalme(cubiertos)},
        )

    def test_NOMBRA_a_los_que_la_corrida_anterior_NO_cubre(self):
        faltan = self.panel[-2:]
        pendiente = self._pendiente([s for s in self.panel if s not in faltan])
        self.assertTrue(pendiente["activo"])
        for start in faltan:
            with self.subTest(start):
                self.assertIn(str(start), pendiente["texto"])

    def test_dice_CUANTOS_de_CUANTOS_y_no_solo_los_que_faltan(self):
        """«2 sin cubrir» no se lee igual que «9 de 11»: la segunda situa la primera."""
        pendiente = self._pendiente(self.panel[:-2])
        self.assertIn(str(len(self.panel) - 2), pendiente["texto"])
        self.assertIn(str(len(self.panel)), pendiente["texto"])

    def test_y_DICE_QUE_HACER_con_ellos(self):
        """Un aborto que no nombra la salida es lo que se lee como «no me deja seguir»."""
        texto = self._pendiente(self.panel[:-2])["texto"].lower()
        self.assertIn("corrida", texto)

    def test_si_la_anterior_CUBRE_el_panel_entero_NO_se_inventa_nada_pendiente(self):
        """Control adversario: sin el, «faltan dos» y «no miro nada» darian lo mismo."""
        pendiente = self._pendiente(self.panel)
        self.assertFalse(pendiente["activo"])
        # Y lo DICE, en vez de callar: que no falte nada es informacion — significa que
        # el fichero repetido era, ademas, el que ya lo contestaba todo.
        self.assertTrue(pendiente["texto"])

    def test_SIN_ALMACENES_no_afirma_que_falte_el_panel_entero(self):
        """No haber podido mirar no es «no cubre a nadie». El `.out` sin resumen."""
        pendiente = presentation.pending_after_duplicate(
            self.corrida.tiling, self.corrida.selection,
            species=ESPECIE, front="empalme_sitios", stores=None,
        )
        self.assertFalse(pendiente["activo"])

    def test_un_frente_que_NO_EXISTE_aborta_en_vez_de_salir_vacio(self):
        """Un frente mal escrito daria «no falta nada», que es el peor de los verdes."""
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError):
            presentation.pending_after_duplicate(
                self.corrida.tiling, self.corrida.selection,
                species=ESPECIE, front="frente_inventado",
                stores={"splice": _AlmacenDeEmpalme(self.panel)},
            )


if __name__ == "__main__":
    unittest.main()
