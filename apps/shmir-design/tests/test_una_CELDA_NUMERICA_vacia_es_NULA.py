"""Una celda numerica vacia se escribe `None`, no `""`.

**Reportado (2026-09-11), errata nº 164.** En la salida del proceso de produccion:

    pyarrow.lib.ArrowInvalid: ("Could not convert '' with type str: tried to convert
    to int64", 'Conversion failed for column rango with type object')

La regla de este proyecto es que un numero que no se calculo va **vacio, nunca a cero**.
Lo que esa regla NO dice es COMO se escribe el vacio, y se venia escribiendo `""` — que
es una CADENA. `site_table_rows` emitia 11 enteros y 273 cadenas vacias en la columna
`rango`.

**LO QUE PASA NO ES QUE REVIENTE.** Medido sobre el Streamlit que corre la app: el fallo
de Arrow lo captura `convert_pandas_df_to_arrow_table`, lo registra con un
`_LOGGER.info` —de ahi el traceback entero en el log, bajo «Applying automatic fixes»— y
**se recupera** convirtiendo la columna ENTERA a texto.

**Y ahi esta el fallo que no se ve**: una columna de puestos en TEXTO ordena
lexicograficamente, asi que con once candidatos el **10 y el 11 se cuelan entre el 1 y el
2**. La tabla se pinta perfecta y se ordena mal — la familia de siempre.

El arreglo va en el PINTOR UNICO y no en el emisor que se conocia: son 26 tablas, y
arreglar la que salio en el log dejaria a las otras 25 esperando su turno (principio
nº 31).

Regla 5: escritos antes. Python 3.11+, solo biblioteca estandar (regla 6).
"""

import re
import unittest
from pathlib import Path

from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.reference import REFERENCES, fixture_available, load_reference
from shmir_design import presentation as P

PAGINA = (
    Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"
).read_text(encoding="utf-8")

HUMANO = REFERENCES["NM_000311.5"]


class TestLaMecanica(unittest.TestCase):
    """Sin panel de por medio."""

    def test_una_columna_MIXTA_pasa_a_NULA(self):
        filas = P.table_cells([{"rango": 1}, {"rango": ""}, {"rango": 11}])
        self.assertEqual([f["rango"] for f in filas], [1, None, 11])

    def test_y_UNA_DE_TEXTO_NO_se_toca(self):
        """La otra mitad: en una columna de texto, `""` ES el valor.

        Sin este caso, «normaliza los vacios» y «borra todos los vacios» darian igual, y
        una celda de motivo vacia pasaria a `None` — que en el TSV sale igual pero en la
        tabla deja de ser una cadena.
        """
        filas = P.table_cells([{"motivo": "GC"}, {"motivo": ""}])
        self.assertEqual([f["motivo"] for f in filas], ["GC", ""])

    def test_un_BOOL_no_cuenta_como_numero(self):
        # `bool` hereda de `int`, asi que sin el control una columna de True/False/""
        # se trataria como numerica y su vacio cambiaria de tipo.
        filas = P.table_cells([{"elegido": True}, {"elegido": ""}])
        self.assertEqual([f["elegido"] for f in filas], [True, ""])

    def test_un_None_que_ya_venia_se_queda(self):
        filas = P.table_cells([{"asimetria": 5.1}, {"asimetria": None}])
        self.assertEqual([f["asimetria"] for f in filas], [5.1, None])

    def test_lo_que_no_es_una_fila_se_devuelve_TAL_CUAL(self):
        # Adivinar la forma de algo que no es una tabla es como se pierde una tabla
        # entera sin ningun error.
        self.assertEqual(P.table_cells(["texto"]), ["texto"])
        self.assertEqual(P.table_cells([]), [])
        self.assertEqual(P.table_cells(None), [])

    def test_NO_se_recorre_dos_veces(self):
        """Con un generador, el segundo recorrido sale vacío y la tabla se pierde."""
        filas = P.table_cells(iter([{"rango": 1}, {"rango": ""}]))
        self.assertEqual([f["rango"] for f in filas], [1, None])


class TestElTSVnoImprimeLaPalabraNone(unittest.TestCase):

    def test_un_None_sale_VACIO(self):
        texto = P.table_tsv(P.table_cells([{"rango": 1}, {"rango": ""}]))
        # `split` y no `splitlines`: la última fila ES la celda vacía, y `splitlines` la
        # descartaría — un test que no puede ver la fila que comprueba.
        self.assertEqual(texto.split("\n"), ["rango", "1", ""])

    def test_y_NO_como_la_palabra(self):
        # Un «None» en la columna del puesto es un texto que parece un dato.
        self.assertNotIn("None", P.table_tsv([{"rango": None}]))


class TestElTextoDeUnaCelda(unittest.TestCase):
    """`cell_text` es la ÚNICA regla de «qué se imprime en una celda»."""

    def test_None_sale_VACIO(self):
        self.assertEqual(P.cell_text(None), "")

    def test_pero_el_CERO_NO(self):
        """La mitad que sostiene toda la regla: vacío y cero no son lo mismo.

        Si `cell_text` tratara el cero como vacío, un conteo legítimo de cero
        desaparecería de la tabla — que es el error contrario y peor.
        """
        self.assertEqual(P.cell_text(0), "0")
        self.assertEqual(P.cell_text(0.0), "0.0")

    def test_y_la_cadena_vacia_se_queda_vacia(self):
        self.assertEqual(P.cell_text(""), "")


class TestLaTABLAdelDOCUMENTOnoImprimeNone(unittest.TestCase):
    """El golden lo cazó: `str(f[c])` metía «None» en 273 filas del informe."""

    def test_una_celda_None_sale_VACIA(self):
        from shmir_design.informe_doc import table

        bloque = table(("rango",), [(1,), (None,)])
        self.assertEqual(bloque.rows, (("1",), ("",)))

    def test_la_regla_vive_en_EL_CONSTRUCTOR_no_en_cada_llamador(self):
        """Principio nº 31: eran CUATRO sitios construyendo celdas a mano.

        Con la regla en los llamadores, la tabla número cinco volvería a imprimir
        «None» — y el golden sólo cubre las que ya están en él.
        """
        import inspect

        from shmir_design import informe_doc

        self.assertIn("cell_text(c)", inspect.getsource(informe_doc.table))
        self.assertNotIn(
            "str(f[c])", inspect.getsource(informe_doc),
            "alguna tabla del documento vuelve a convertir sus celdas por su cuenta.",
        )


class TestElPintorUNICOloAplica(unittest.TestCase):
    """Mira el FUENTE: `AppTest` no llega al estado DISEÑADO y ninguna tabla se pinta."""

    def _cuerpo(self, nombre: str) -> str:
        trozo = PAGINA.split(f"def {nombre}(", 1)[1]
        return re.split(r"\ndef ", trozo, maxsplit=1)[0]

    def test_el_pintor_normaliza_antes_de_pintar(self):
        cuerpo = self._cuerpo("_tabla")
        self.assertIn("table_cells(", cuerpo)
        # Y ANTES de las dos salidas: la pintada y la que se lleva tienen que decir lo
        # mismo. Si se normalizara sólo una, el TSV y la tabla discreparían.
        self.assertLess(cuerpo.index("table_cells("), cuerpo.index("st.dataframe("))
        self.assertLess(cuerpo.index("table_cells("), cuerpo.index("table_tsv("))

    def test_y_SIGUE_habiendo_un_solo_pintor(self):
        # Prueba de vida (principio nº 51): si apareciera un segundo `st.dataframe`,
        # esta normalización dejaría de cubrir todas las tablas y nadie se enteraría.
        self.assertEqual(
            PAGINA.count("st.dataframe("), 1,
            "hay más de un sitio que pinta tablas: el arreglo cubre uno solo.",
        )


@unittest.skipUnless(
    fixture_available(HUMANO), "NOT_RUN: falta data/reference/NM_000311.5.fa"
)
class TestSobreLaTablaDEVERDAD(unittest.TestCase):
    """El caso real: el panel humano, que es donde salió."""

    @classmethod
    def setUpClass(cls):
        secuencia = load_reference(HUMANO)
        anatomia = Anatomy.from_cds(
            cds=HUMANO.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        corrida = P.page_run(species="human", sequence=secuencia, anatomy=anatomia)
        cls.corrida = corrida
        cls.filas = P.site_table_rows(
            corrida.tiling, corrida.selection, species="human"
        )

    def _mixtas(self, filas):
        """Columnas que llevan a la vez un número y una cadena vacía."""
        columnas = {c for f in filas for c in f}
        return sorted(
            col for col in columnas
            if any(isinstance(f.get(col), (int, float))
                   and not isinstance(f.get(col), bool) for f in filas)
            and any(isinstance(f.get(col), str) and f.get(col) == "" for f in filas)
        )

    def test_el_EMISOR_ya_no_mezcla(self):
        self.assertEqual(self._mixtas(self.filas), [])

    def test_y_EL_DETECTOR_MUERDE_sobre_la_forma_que_habia(self):
        """CONTROL ADVERSARIO con la forma REAL del fallo (principio nº 18).

        Sin él, «ninguna columna mezcla» y «el detector no mira nada» dan el mismo verde.
        """
        antes = [dict(f, rango="" if f.get("rango") is None else f["rango"])
                 for f in self.filas]
        self.assertEqual(self._mixtas(antes), ["rango"])

    def test_EL_PUESTO_SIGUE_ESTANDO_y_el_resto_sigue_vacio(self):
        """No se pierde ningún dato: es la condición del arreglo."""
        con_puesto = [f for f in self.filas if f.get("rango") is not None]
        self.assertEqual(
            sorted(f["rango"] for f in con_puesto),
            list(range(1, len(self.corrida.selection.selection.chosen) + 1)),
        )
        self.assertTrue(all(f.get("elegido") for f in con_puesto))

    def test_y_EL_PANEL_SIGUE_SALIENDO_PRIMERO_y_EN_ORDEN(self):
        # `panel_first` ordena por `isinstance(rango, int)`, así que si el vacío hubiera
        # pasado a texto en vez de a nulo esto seguiría pasando — y si el puesto hubiera
        # pasado a texto, no.
        ordenadas = P.panel_first(P.table_cells(self.filas))
        n = len(self.corrida.selection.selection.chosen)
        self.assertEqual([f["rango"] for f in ordenadas[:n]], list(range(1, n + 1)))

    def test_NINGUNA_tabla_grande_del_panel_mezcla(self):
        """El barrido, no el emisor: la familia reaparece en cada tabla nueva."""
        for nombre, filas in (
            ("site_table_rows", self.filas),
            ("candidate_rows", P.candidate_rows(self.corrida.selection)),
            ("window_rows", P.window_rows(self.corrida.tiling)),
        ):
            with self.subTest(nombre):
                self.assertEqual(self._mixtas(P.table_cells(filas)), [])


if __name__ == "__main__":
    unittest.main()
