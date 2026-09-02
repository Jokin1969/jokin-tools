"""Una corrida valida llega a la TABLA, al VEREDICTO, a las TARJETAS y al SEMAFORO.

**Reportado con el proyecto delante (2026-09-02)**: proyecto `Intento_10`, corrida
`blast-...-da94fcf3...`, la seccion «¿Siguen valiendo las corridas guardadas?» dice
`PASS` —o sea que la comparacion de md5 contra `refseq_rna.fa` funciona— y aun asi el
semaforo dice «Hechas 6 de 10», las tarjetas «1 de 8», los diez candidatos salen
`INCOMPLETE` y el informe sigue listando `especificidad` entre los frentes abiertos.

Y quien lo reporto pidio distinguir cual de los dos fallos era, porque son distintos.
**Son LOS DOS**, y cada uno tiene su sitio:

1. **`stores` no llegaba a `site_table_rows` en el camino real de la pagina.** La funcion
   lo acepta desde hace dias y sus tests pasan; la pagina llamaba
   `site_table_rows(tiling, seleccion, species=..., selected=...)` **sin `stores=`**. Es
   la quinta vez de esta familia —`triple_motive_rows`, `intron_folding`, `store.save_*`,
   `page_run`— y la primera con la capacidad ya cableada y probada: lo que faltaba era el
   argumento en la unica llamada que se ejecuta.
2. **Y ademas faltaban TRES consumidores.** El veredicto de cada candidato, las tarjetas
   y el semaforo no miran los almacenes: salen del informe de tilado. Aunque `stores`
   hubiera llegado a la tabla, la celda habria cambiado y todo lo demas no — que es
   exactamente el otro fallo que se pedia distinguir.

Regla 5: escritos antes.
"""

import unittest
from pathlib import Path

from shmir_design import presentation


class TestLaPaginaPASAlosAlmacenes(unittest.TestCase):
    """El fallo nº 1, y se comprueba sobre el fuente porque es una LLAMADA que falta."""

    FUENTE = (
        Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
    ).read_text(encoding="utf-8")

    def test_la_tabla_de_sitios_recibe_stores(self):
        # Se busca en la LLAMADA, no en el fichero: `stores=` aparece en otras llamadas
        # y con eso el test pasaria sin que la tabla lo recibiera.
        inicio = self.FUENTE.index("site_table_rows(\n")
        llamada = self.FUENTE[inicio : self.FUENTE.index("),", inicio)]
        self.assertIn(
            "stores=", llamada,
            "la página pinta la tabla SIN los almacenes: la capacidad está cableada y "
            "probada, y la única llamada que se ejecuta no la usa.",
        )

    def test_las_tarjetas_reciben_stores(self):
        self.assertIn("front_card_rows(corrida, species=nombre, stores=", self.FUENTE)


class TestLosCuatroConsumidores(unittest.TestCase):
    """El fallo nº 2. Sin almacenes nada cambia; con ellos, cambian los cuatro."""

    def _estados(self):
        return {"especificidad": "PASS"}

    def test_el_veredicto_del_candidato_cuenta_lo_que_dicen_los_almacenes(self):
        # INCOMPLETE porque un frente esta NOT_RUN; con la corrida encima, deja de estarlo.
        antes = presentation.verdict_with_stores(
            {"especificidad": "NOT_RUN", "GC": "PASS"}
        )
        despues = presentation.verdict_with_stores({"especificidad": "PASS", "GC": "PASS"})
        self.assertEqual(antes, "INCOMPLETE")
        self.assertEqual(despues, "PASS")

    def test_un_FAIL_del_almacen_manda_igual_que_uno_del_filtro(self):
        self.assertEqual(
            presentation.verdict_with_stores({"especificidad": "FAIL", "GC": "PASS"}),
            "FAIL",
        )

    def test_NO_CIERRA_impide_aprobar(self):
        self.assertEqual(
            presentation.verdict_with_stores(
                {"especificidad": "NO_CIERRA", "GC": "PASS"}
            ),
            "INCOMPLETE",
        )


class TestUnFrenteSoloSeCierraSiLOCUBRETODOelPanel(unittest.TestCase):
    """La regla que impide un cierre falso, y es la mitad que no se puede omitir."""

    def test_con_todos_los_candidatos_cubiertos_el_frente_se_cierra(self):
        cerrados = presentation.fronts_closed_by_runs(
            {"especificidad": {10: "PASS", 20: "PASS"}}, starts=(10, 20)
        )
        self.assertIn("especificidad", cerrados)

    def test_con_SOLO_ALGUNOS_no_se_cierra_y_dice_cuantos(self):
        cerrados = presentation.fronts_closed_by_runs(
            {"especificidad": {10: "PASS"}}, starts=(10, 20)
        )
        self.assertNotIn("especificidad", cerrados)

    def test_un_NOT_RUN_del_almacen_NO_cierra(self):
        cerrados = presentation.fronts_closed_by_runs(
            {"especificidad": {10: "NOT_RUN", 20: "PASS"}}, starts=(10, 20)
        )
        self.assertNotIn("especificidad", cerrados)

    def test_un_FAIL_SI_cierra_el_frente(self):
        # Un frente se cierra CONSIGUIENDO la respuesta, no consiguiendo un PASS. Un FAIL
        # es una respuesta: el candidato cae, y el frente deja de estar abierto.
        cerrados = presentation.fronts_closed_by_runs(
            {"especificidad": {10: "FAIL", 20: "PASS"}}, starts=(10, 20)
        )
        self.assertIn("especificidad", cerrados)

    def test_sin_almacenes_no_cierra_nada(self):
        self.assertEqual(presentation.fronts_closed_by_runs(None, starts=(10,)), {})


if __name__ == "__main__":
    unittest.main()
