"""Ninguna columna de secuencia de una tabla exportada sale corta.

**De dónde sale (2026-09-02)**: se reportó un heptámero de SEIS caracteres en la columna
`heptamero` del CSV descargable. Los TRES productores del heptámero se midieron y los
tres dan siete, así que ese caso concreto NO se reprodujo y no se le asigna causa — decir
«era esto» sin haberlo comprobado es el principio nº 3.

Lo que sí se decidió es que la clase de fallo tenga guardia. Es de las que no dan ningún
error: **un heptámero truncado a seis sigue siendo una seed válida y DISTINTA**, así que
la carga que sale a su lado es un número correcto para otra pregunta. La familia del
«Alu 0 %».

**Y el guardia no es una lista de columnas**: la columna de secuencia se DERIVA del
contenido, así que una columna nueva entra sola — y si no declara su longitud esperada,
ABORTA. Ignorarla lo dejaría en «las columnas de las que alguien se acordó».

Regla 5: escritos antes.
"""

import unittest
from pathlib import Path

from shmir_design import audit, comparative, presentation
from shmir_design.errors import ShmirDesignError
from shmir_design.polya import ALL_SIGNALS
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.scaffold import SGEP_SCAFFOLD
from shmir_design.seed_scan import DEFAULTS as SEED_DEFAULTS
from shmir_design.selection import default_config, select_from_report
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _piezas():
    utr3 = load_3utr(RATON)
    informe = tile_utr(utr3)
    return informe, select_from_report(informe, default_config())


def _largo_de_ventana(informe) -> int:
    """La longitud de la diana, DERIVADA de las ventanas del propio informe."""
    largos = {v.window.length for v in informe.windows}
    if len(largos) != 1:  # pragma: no cover - el tilado es de longitud fija
        raise AssertionError(f"las ventanas no miden todas lo mismo: {sorted(largos)}")
    return largos.pop()


def _largo_de_guia(seleccion) -> int:
    largos = {
        len(seleccion.windows[elegido.label].evaluation.guide)
        for elegido in seleccion.selection.chosen
    }
    if len(largos) != 1:  # pragma: no cover
        raise AssertionError(f"las guias no miden todas lo mismo: {sorted(largos)}")
    return largos.pop()


def _largo_de_hexamero() -> int:
    largos = {len(h) for h in ALL_SIGNALS}
    if len(largos) != 1:  # pragma: no cover
        raise AssertionError("los hexameros de polyA no miden todos lo mismo")
    return largos.pop()


def _largo_de_heptamero() -> int:
    """De la VENTANA de la corrida, no de un 7 escrito.

    Escribir el 7 aquí sería afirmar que la ventana es 2-8, que es justo lo que el
    guardia tiene que comprobar. Con `2-7` esta cifra baja sola y la tabla sigue
    cuadrando (principio nº 13).
    """
    return SEED_DEFAULTS.length


@unittest.skipUnless(HAY, "falta el fixture del 3'UTR murino")
class TestLasTablasDeLaPagina(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.informe, cls.seleccion = _piezas()
        cls.ventana = _largo_de_ventana(cls.informe)
        cls.guia = _largo_de_guia(cls.seleccion)
        cls.hexamero = _largo_de_hexamero()

    def test_la_tabla_de_candidatos(self):
        audit.check_no_truncation(
            presentation.candidate_rows(self.seleccion),
            expected={
                "diana": self.ventana,
                "guia": self.guia,
                "polyA_hexamero": self.hexamero,
            },
            table="candidate_rows",
        )

    def test_la_tabla_de_sitios_con_una_columna_por_frente(self):
        audit.check_no_truncation(
            presentation.site_table_rows(self.informe, self.seleccion),
            expected={"guia": self.guia},
            table="site_table_rows",
        )

    def test_la_tabla_de_ventanas(self):
        audit.check_no_truncation(
            presentation.window_rows(self.informe),
            expected={"diana": self.ventana},
            table="window_rows",
        )

    def test_la_tabla_previa_del_modal_de_seed(self):
        # Es la que lleva la columna que se reporto.
        audit.check_no_truncation(
            presentation.seed_preview_rows(self.seleccion, species="mouse"),
            expected={
                "secuencia": self.guia,
                "heptamero": _largo_de_heptamero(),
                # El nucleo es el heptamero menos la base de la posicion 8: se DERIVA
                # del mismo sitio, no se escribe un 6.
                "nucleo": _largo_de_heptamero() - 1,
            },
            table="seed_preview_rows",
        )


@unittest.skipUnless(HAY, "falta el fixture del 3'UTR murino")
class TestLaTablaCOMPARATIVA(unittest.TestCase):
    """La que se descarga como TSV: es de la que se leyó la columna reportada."""

    def test_ninguna_de_sus_columnas_de_secuencia_sale_corta(self):
        informe, seleccion = _piezas()
        filas = comparative.comparative_rows(seleccion, SGEP_SCAFFOLD)
        cabecera, *cuerpo = filas
        tabla = [dict(zip(cabecera, fila, strict=True)) for fila in cuerpo]
        largo_guia = _largo_de_guia(seleccion)
        audit.check_no_truncation(
            tabla,
            expected={
                "diana": _largo_de_ventana(informe),
                "guia": largo_guia,
                # La pasajera sale VACIA sin motor de plegado —se elige plegando— y una
                # celda vacia no se comprueba: no haber calculado no es haber truncado.
                "pasajera": largo_guia,
                # El modulo NheI-SacI. Su longitud la declara el propio generador.
                "gblock_149": _largo_de_gblock(tabla),
                "polyA_hexamero": _largo_de_hexamero(),
                # La feature de SplashRNA: es la MISMA ventana 2-8 que el heptamero del
                # modal, y por eso se deriva del mismo sitio. Salio al escribir el
                # guardia: era una columna de secuencia sin nadie mirandola.
                "feat_seed": _largo_de_heptamero(),
            },
            table="comparative_rows",
        )


def _largo_de_gblock(tabla) -> int:
    largos = {len(f["gblock_149"]) for f in tabla if str(f["gblock_149"]).strip()}
    if not largos:
        return 0
    if len(largos) != 1:  # pragma: no cover
        raise AssertionError(f"los modulos no miden todos lo mismo: {sorted(largos)}")
    return largos.pop()


MATURE = Path(__file__).resolve().parent.parent / "data" / "reference" / "mature.fa"


@unittest.skipUnless(
    HAY and MATURE.is_file(), "NOT_RUN: falta mature.fa o el fixture del raton"
)
class TestLaTablaDEL_CSV_DESCARGABLE(unittest.TestCase):
    """La del modal de colisión de seed: es la columna que se reportó.

    Corre el scan de verdad contra `mature.fa`. Medir sobre una tabla fabricada aquí
    probaría el fixture y no el productor — que es justo el fallo del principio nº 18.
    """

    @classmethod
    def setUpClass(cls):
        from shmir_design import seed_scan
        from shmir_design.mirna import load_mature_fa

        maduros = load_mature_fa(MATURE, version="23")
        informe = tile_utr(load_3utr(RATON), mature=maduros)
        seleccion = select_from_report(informe, default_config())
        cls.scan = seed_scan.run_scan(
            seleccion, mature=maduros, params=seed_scan.DEFAULTS, species="raton",
            starts=tuple(c.start for c in seleccion.selection.chosen),
            guides=True, passengers=True,
        )

    def test_el_heptamero_de_cada_fila_mide_lo_que_su_VENTANA_declara(self):
        audit.check_no_truncation(
            presentation.seed_result_rows(self.scan),
            # De la ventana DE LA CORRIDA, no de la de por defecto: si alguien corre
            # `2-7`, el heptamero mide seis Y ESO ES CORRECTO. El guardia compara contra
            # lo que esa corrida declara, que es lo unico que distingue las dos cosas.
            expected={"heptamero": self.scan.params.length},
            table="seed_result_rows",
        )


class TestElGuardiaMUERDE(unittest.TestCase):
    """Control adversario: sin esto, «ninguna tabla trunca» y «el guardia no mira nada»
    darían el mismo verde."""

    def test_una_celda_corta_ABORTA(self):
        with self.assertRaises(ShmirDesignError) as caja:
            audit.check_no_truncation(
                [{"heptamero": "ACGTACG"}, {"heptamero": "ACGTAC"}],
                expected={"heptamero": 7}, table="prueba",
            )
        self.assertIn("mide 6", str(caja.exception))

    def test_una_columna_de_secuencia_SIN_DECLARAR_aborta(self):
        with self.assertRaises(ShmirDesignError):
            audit.check_no_truncation(
                [{"guia": "ACGTACGTACGTACGTACGTAC"}], expected={}, table="prueba",
            )

    def test_una_columna_que_NO_es_secuencia_no_estorba(self):
        audit.check_no_truncation(
            [{"estado": "PASS", "motivo": "sin hallazgos"}], expected={}, table="prueba",
        )

    def test_las_celdas_VACIAS_no_cuentan(self):
        # No haber calculado y haber truncado son cosas distintas; un `NOT_RUN` deja la
        # celda vacia a proposito (regla 3).
        audit.check_no_truncation(
            [{"guia": "ACGTACGTACGTACGTACGTAC"}, {"guia": ""}],
            expected={"guia": 22}, table="prueba",
        )

    def test_y_una_columna_corta_de_dos_letras_no_se_confunde_con_secuencia(self):
        # `AT`, `GC` y `CG` son etiquetas. Un guardia con falsos positivos se apaga.
        self.assertEqual(audit.sequence_columns([{"par": "GC"}, {"par": "AT"}]), ())


if __name__ == "__main__":
    unittest.main()
