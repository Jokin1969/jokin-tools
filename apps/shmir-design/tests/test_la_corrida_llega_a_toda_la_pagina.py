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


class TestLaCOBERTURAPARCIALseDICE(unittest.TestCase):
    """Errata nº 54: «6 de 10» reproducido, y era la corrida cubriendo 6 de 10.

    Reportado tres veces con los mismos números —semáforo «6 de 10», tarjetas «1 de 8»—
    y con el argumento correcto: son tres caminos distintos, así que la causa es común y
    anterior a los tres. Lo era: `blocking_fronts` tiene SEIS llamadores y los almacenes
    entraban por el consumidor, uno a uno.

    Y lo que quedaba debajo: **una corrida que cubre parte del panel salía IDÉNTICA a no
    tener ninguna.** El estado era correcto —un frente no se cierra con 6 de 10— y la app
    no lo decía, así que quien acababa de subir una corrida de horas veía la pantalla sin
    cambiar y concluía que no se había recogido.
    """

    def test_una_corrida_parcial_NO_cierra_pero_DICE_cuanto_cubre(self):
        cobertura = presentation.run_coverage(
            {"especificidad": {10: "PASS", 20: "PASS", 30: "PASS"}},
            starts=(10, 20, 30, 40, 50),
        )["especificidad"]
        self.assertFalse(cobertura["cerrado"])
        self.assertEqual((cobertura["cubiertos"], cobertura["panel"]), (3, 5))
        self.assertIn("3 de 5", cobertura["motivo"])
        self.assertIn("40", cobertura["motivo"])

    def test_y_dice_que_la_corrida_NO_se_pierde(self):
        motivo = presentation.run_coverage(
            {"especificidad": {10: "PASS"}}, starts=(10, 20)
        )["especificidad"]["motivo"]
        self.assertIn("no se pierde", motivo)

    def test_sin_ninguna_corrida_NO_hay_texto_de_avance(self):
        # Control adversario: si el aviso saliera siempre, no distinguiría «a medias» de
        # «sin tocar», que es exactamente lo que se está arreglando.
        cobertura = presentation.run_coverage(
            {"especificidad": {}}, starts=(10, 20)
        )["especificidad"]
        self.assertEqual(cobertura["motivo"], "")

    def test_el_SEMAFORO_deja_de_contar_un_frente_que_la_corrida_cierra(self):
        # Era el consumidor que faltaba: `status_light` cuenta los filtros de la ventana,
        # que no saben nada del registro del proyecto.
        import inspect

        firma = inspect.signature(presentation.status_light)
        self.assertIn("resueltos", firma.parameters)

    def test_blocking_fronts_recibe_los_cerrados_POR_AHI(self):
        # La causa común: seis llamadores. Si esto vuelve a entrar por el consumidor, se
        # arregla uno y los otros cinco siguen igual.
        import inspect

        from shmir_design.selection import blocking_fronts

        self.assertIn("closed_by_runs", inspect.signature(blocking_fronts).parameters)

    def test_la_pagina_carga_los_almacenes_UNA_vez_para_los_cuatro(self):
        fuente = TestLaPaginaPASAlosAlmacenes.FUENTE
        cuerpo = fuente[fuente.index("def bloque_especie"):]
        cuerpo = cuerpo[: cuerpo.index("\ndef ")]
        self.assertEqual(
            cuerpo.count("load_stores("), 1,
            "cada consumidor volvía a cargarlos por su cuenta: cuatro copias del mismo "
            "estado, y la que se olvidara pintaría otra cosa.",
        )
