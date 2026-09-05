"""La tabla lee las corridas guardadas. Es el criterio de aceptacion, escrito como test.

Se acordo con el responsable del proyecto ANTES de implementarlo, para que pudiera
comprobarlo sin abrir el codigo:

  1. la columna `especificidad` de un candidato con corrida deja de decir `NOT_RUN`;
  2. una corrida `-remote` da `NO_CIERRA`, no `NOT_RUN` ni `PASS`;
  3. un candidato SIN corrida NO se contagia — control adversario: si todos cambiaran,
     la tabla no estaria leyendo nada, estaria pintando otra cosa;
  4. y el contador de la confirmacion dice cuantos veredictos cambiaron, con el CERO
     visible: «guardada, 0 veredictos actualizados» es la señal de que algo no encaja, y
     hasta hoy no existia.
"""

import unittest

from shmir_design import blast, presentation
from shmir_design.blast_store import BlastDatabase, BlastRun, BlastStore

GUIA_FICTICIA = "TTATATTCTTATTGGCCCGGTG"


def _piezas():
    from tests.test_corrida_de_la_pagina import _entrada

    sec, anat = _entrada()
    corrida = presentation.page_run(species="raton", sequence=sec, anatomy=anat)
    return corrida.tiling, corrida.selection


def _almacen_con(inicio, *, remota=False, run_id="r1"):
    consulta = presentation.query_name("raton", inicio, "guia")
    almacen = BlastStore()
    almacen.add(
        BlastRun.create(
            run_id=run_id, date="2026-09-01", uploaded_by="responsable",
            params=blast.BlastParams.for_species("raton", remote=remota),
            database=BlastDatabase(
                name="refseq_mouse", version="v1", md5="a" * 32, remote=remota,
            ),
            query=blast.QueryFasta.from_records(((consulta, GUIA_FICTICIA),)),
            raw=(
                f"{consulta}\tNM_011170.3\t100.000\t22\t0\t0\t1\t22\t1170\t1191"
                f"\t1e-05\t44.1\n"
            ),
        )
    )
    return almacen


class TestLaTABLAcambiaConLaCorrida(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling, cls.seleccion = _piezas()
        cls.primero = cls.seleccion.selection.chosen[0].start

    def _fila(self, stores):
        filas = presentation.site_table_rows(
            self.tiling, self.seleccion, species="raton", stores=stores
        )
        return next(f for f in filas if f["inicio"] == self.primero)

    def test_1_SIN_almacen_la_columna_dice_NOT_RUN(self):
        self.assertEqual(self._fila(None)["especificidad"], "NOT_RUN")

    def test_2_CON_una_corrida_buena_deja_de_decir_NOT_RUN(self):
        estado = self._fila({"blast": _almacen_con(self.primero)})["especificidad"]
        self.assertNotEqual(estado, "NOT_RUN")
        self.assertIn(estado, ("PASS", "FAIL"))

    def test_3_una_corrida_REMOTA_da_NO_CIERRA(self):
        estado = self._fila(
            {"blast": _almacen_con(self.primero, remota=True)}
        )["especificidad"]
        self.assertEqual(estado, "NO_CIERRA")

    def test_4_los_OTROS_candidatos_NO_se_contagian(self):
        """Control adversario. Si todos cambiaran, la tabla no leeria: pintaria otra cosa."""
        filas = presentation.site_table_rows(
            self.tiling, self.seleccion, species="raton",
            stores={"blast": _almacen_con(self.primero)},
        )
        otros = [
            f for f in filas
            if f["inicio"] != self.primero and f["elegido"]
        ]
        self.assertTrue(otros)
        for fila in otros:
            with self.subTest(inicio=fila["inicio"]):
                # `SIN_CONSULTAR` desde 2026-09-02 (errata nº 55): hay corridas de este
                # frente y ninguna miró a este candidato, que NO es lo mismo que no
                # haber corrido nada. Lo que se comprueba aquí sigue siendo lo de antes:
                # que el veredicto del que sí se consultó NO se contagia al resto.
                self.assertEqual(fila["especificidad"], presentation.SIN_CONSULTAR)

    def test_5_los_OTROS_FRENTES_del_mismo_candidato_no_se_mueven(self):
        # Una corrida de BLAST cierra especificidad y NADA MAS. Si moviera otra columna,
        # estaria contagiando un veredicto que nadie ha ganado.
        fila = self._fila({"blast": _almacen_con(self.primero)})
        self.assertEqual(fila["repeticiones"], "NOT_RUN")


class TestElCONTADORdeLaConfirmacion(unittest.TestCase):
    """«Guardada en el log» se lee como «hecho». Tiene que decir QUE cambio."""

    @classmethod
    def setUpClass(cls):
        cls.tiling, cls.seleccion = _piezas()
        cls.primero = cls.seleccion.selection.chosen[0].start

    def test_una_corrida_que_cierra_cambia_UN_veredicto(self):
        resumen = presentation.verdicts_changed(
            self.tiling, self.seleccion, species="raton",
            before=None, after={"blast": _almacen_con(self.primero)},
        )
        self.assertEqual(resumen["cambiados"], 1)
        self.assertIn("1", resumen["texto"])

    def test_y_el_CERO_se_dice_con_esas_palabras(self):
        """La señal que no existia: guardar sin que cambie nada."""
        almacen = _almacen_con(self.primero)
        resumen = presentation.verdicts_changed(
            self.tiling, self.seleccion, species="raton",
            before={"blast": almacen}, after={"blast": almacen},
        )
        self.assertEqual(resumen["cambiados"], 0)
        self.assertIn("0", resumen["texto"])

    def test_el_texto_del_CERO_avisa_de_que_algo_no_encaja(self):
        almacen = _almacen_con(self.primero)
        texto = presentation.verdicts_changed(
            self.tiling, self.seleccion, species="raton",
            before={"blast": almacen}, after={"blast": almacen},
        )["texto"].lower()
        self.assertIn("no encaja", texto)


class TestElAVISOdelDESACUERDOseBORRA(unittest.TestCase):
    """Su causa se acabo. Un aviso que sobrevive manda a desconfiar de algo correcto."""

    def test_ya_no_existe_la_constante(self):
        self.assertFalse(hasattr(presentation, "TABLE_LAGS_REPORT"))

    def test_ni_la_pagina_lo_pinta(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("TABLE_LAGS_REPORT", fuente)


if __name__ == "__main__":
    unittest.main()
