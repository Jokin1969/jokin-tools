"""Una tarjeta de frente no repite el mismo texto, y menos en dos colores.

**Reportado (2026-09-05)**, con la tarjeta delante: *«se repite el mensaje que dice que
ya está hecho. Uno en verde y otro en amarillo»*, y **«pasa en casi todas»** — en todas
las cerradas por corrida guardada, que con un proyecto trabajado son casi todas.

**El texto es el mismo objeto, escrito una vez y leído por dos campos.** Cuando una
corrida cubre el panel entero, `run_coverage` emite su motivo y ese motivo va a los DOS
sitios:

- a `cerrados`, que `blocking_fronts` pone en `frente.reason` → `resultado` → **verde**;
- a `avance`, que la tarjeta pinta → **ámbar**.

**Y el segundo no es sólo una repetición: es del color equivocado.** `avance` existe por
la errata nº 54 —«un frente con corrida para 6 de 10 no puede pintarse igual que uno que
nadie ha tocado»— o sea **para la cobertura PARCIAL**. Sobre un frente cerrado el ámbar
dice «pendiente» justo debajo de un verde que dice «cerrado»: dos estados pintando lo
mismo, que es el principio nº 36 dentro de una sola tarjeta.

Regla 5: escrito antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation  # noqa: E402
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_reference,
)

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)

PANEL = (10, 60, 143, 200, 449, 553, 652, 735, 819, 1018, 1071)


class TestElAVANCE_es_solo_de_lo_PARCIAL(unittest.TestCase):
    """`avance` contesta «cuánto falta», y de un frente cerrado no falta nada."""

    def test_cubierto_ENTERO_no_deja_avance(self):
        estados = {"especificidad": {s: "PASS" for s in PANEL}}
        fila = presentation.run_coverage(estados, starts=PANEL)["especificidad"]
        self.assertTrue(fila["cerrado"])
        self.assertEqual(fila["avance"], "")

    def test_cubierto_A_MEDIAS_si(self):
        # El caso que motivó `avance`: 6 de 10 no se pinta como uno sin tocar.
        estados = {"especificidad": {s: "PASS" for s in PANEL[:6]}}
        fila = presentation.run_coverage(estados, starts=PANEL)["especificidad"]
        self.assertFalse(fila["cerrado"])
        self.assertTrue(fila["avance"].strip())
        self.assertIn("6", fila["avance"])

    def test_y_el_MOTIVO_del_cierre_sigue_estando(self):
        # Lo que se quita es la COPIA en ámbar, no la información: el motivo del
        # cierre viaja igual y es el que la tarjeta pinta en verde.
        estados = {"especificidad": {s: "PASS" for s in PANEL}}
        fila = presentation.run_coverage(estados, starts=PANEL)["especificidad"]
        self.assertIn("CERRADO", fila["motivo"])


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestNingunaTARJETA_repite_un_texto(unittest.TestCase):
    """El guardia, sobre las tarjetas de verdad y en los dos estados."""

    @classmethod
    def setUpClass(cls):
        tx = load_reference(RATON)
        anat = Anatomy.from_cds(
            cds=RATON.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.corrida = presentation.page_run(species="raton", sequence=tx, anatomy=anat)

    #: Los campos de texto que la tarjeta pinta UNO DEBAJO DE OTRO. Si dos llevan lo
    #: mismo, el lector ve el mismo mensaje dos veces — y con dos colores, dos estados.
    VISIBLES = ("resultado", "avance", "motivo", "por_que_aparte", "encabezado")

    def _repetidos(self, tarjeta):
        vistos: dict[str, str] = {}
        choques = []
        for campo in self.VISIBLES:
            texto = (tarjeta.get(campo) or "").strip()
            if not texto:
                continue
            if texto in vistos:
                choques.append(f"{tarjeta['frente']}: {vistos[texto]} == {campo}")
            vistos[texto] = campo
        return choques

    def test_sin_ninguna_corrida(self):
        tarjetas = presentation.front_card_rows(self.corrida, species="raton")
        choques = [c for t in tarjetas for c in self._repetidos(t)]
        self.assertEqual(choques, [], "\n".join(choques))

    def test_y_CON_un_frente_cerrado_por_corrida(self):
        # El caso reportado. Se construye la tarjeta por el mismo camino que la página.
        tarjetas = presentation.front_card_rows(
            self.corrida, species="raton", stores=None,
        )
        # La cobertura entra por `closed_by_panel`, así que se comprueba el efecto
        # sobre la tarjeta: un frente cerrado no puede llevar `avance`.
        for tarjeta in tarjetas:
            if tarjeta["estado"] == "HECHO":
                with self.subTest(tarjeta["frente"]):
                    self.assertEqual(tarjeta["avance"], "")

    def test_el_guardia_MUERDE(self):
        # Sin esto, «ninguna repite» y «el detector no mira nada» dan el mismo verde.
        falsa = {
            "frente": "x", "resultado": "CERRADO por corrida guardada: los 10.",
            "avance": "CERRADO por corrida guardada: los 10.", "motivo": "",
            "por_que_aparte": "", "encabezado": "",
        }
        self.assertEqual(len(self._repetidos(falsa)), 1)


if __name__ == "__main__":
    unittest.main()
