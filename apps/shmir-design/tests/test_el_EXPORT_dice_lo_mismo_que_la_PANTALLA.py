"""El export de candidatos dice lo MISMO que la pantalla. Si no, dice MENOS.

Regla 5: escritos antes.

**Reportado el 2026-09-07**, con el fichero delante y con la pregunta ya planteada por
quien lo reporta: *«¿`empalme_sitios` y `offtarget_seed` tienen columna en el export de
candidatos, o sólo en la tabla de pantalla? Si sólo en pantalla, es la novena tabla del
guardia de `_filter_columns` — y entonces el export es un artefacto que dice menos que la
pantalla, que es peor que al revés porque el export es lo que viaja»*.

**Y era eso.** `outputs.tsv_selected` construía sus columnas de
`window.filters` —los filtros de la VENTANA— y no recibía `stores` nunca. Consecuencias,
las dos medidas antes de tocar nada:

  - `offtarget_seed` **no tenía columna** en el export y **sí** en la tabla de sitios de
    la pantalla, que deriva las suyas de `blocking_fronts`;
  - las columnas que sí salían —`especificidad`, `seed_colision`— eran el estado del
    **filtro de ventana**, no el veredicto del frente con la corrida guardada encima. O
    sea que una corrida de BLAST podía cerrar el frente en pantalla y el export seguía
    diciendo `NOT_RUN` de los mismos once candidatos.

**Peor que al revés, y por eso es prioritario**: la pantalla se mira con la app delante y
el export es lo que se manda por correo, se adjunta a un pedido y se lee dentro de un año.

### `empalme_sitios` NO se colapsa a una columna: va UNA POR INTRÓN

Su unidad es el par candidato × intrón (`PAIR_UNIT_FRONTS`), y darle una columna por
candidato colapsaría justo lo que ese frente existe para comparar — el mismo módulo
dentro de dos arquitecturas distintas. Las columnas se DERIVAN de los intrones que la
corrida guardada consultó: sin corrida no hay intrones que nombrar, así que sale una
columna `empalme_sitios` en `NOT_RUN` diciendo que nadie ha preguntado.

Es la misma forma que `por_hebra` en `STORE_FOR_FRONT`: un frente cuya unidad no es el
candidato da varias columnas, no una fundida.
"""

import unittest

from shmir_design import outputs, presentation
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


class _AlmacenPorHebra:
    """La superficie mínima de un almacén de los que se consultan por `query_name`."""

    def __init__(self, consultas, *, frente):
        self._consultas = frozenset(consultas)
        self._frente = frente
        self.runs = ("una corrida",)

    def history(self, consulta):
        return ("x",) if consulta in self._consultas else ()

    def verdict_for(self, consulta):
        return FilterResult(
            name=self._frente, state=FilterState.PASS, reason="corrida de prueba",
        )


def _columnas_offtarget():
    """Las columnas de `offtarget_seed`, DERIVADAS de los ejes que las emiten.

    Hebra x catalogo. Escritas aqui, este test no podria ver un eje emitido mal — que
    es justo lo que existe para comprobar (principio nº 13).
    """
    return [
        f"offtarget_seed:{hebra}:{catalogo}"
        for hebra in presentation.STRANDS
        for catalogo in presentation.catalogue_slugs(ESPECIE)
    ]


def _almacen_offtarget(corrida):
    """Un almacén que ha consultado a TODO el panel, por las dos hebras."""
    consultas = [
        presentation.query_name(ESPECIE, c.start, hebra)
        for c in corrida.selection.selection.chosen
        for hebra in presentation.STRANDS
    ]
    return {"offtarget": _AlmacenPorHebra(consultas, frente="offtarget_seed")}


@unittest.skipUnless(HAY, "falta el fixture del ratón")
class TestElExportLLEVAlosFrentes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.cabecera = presentation.tsv_header(outputs.tsv_selected(
            cls.corrida.selection, species=ESPECIE, tiling=cls.corrida.tiling,
        ))

    def test_TODA_columna_de_frente_de_la_pantalla_esta_en_el_export(self):
        """Derivado, no listado: un frente nuevo entra solo en las dos."""
        de_pantalla = presentation.front_columns(self.corrida.tiling, self.corrida.selection, species="raton")
        faltan = [c for c in de_pantalla if c not in self.cabecera]
        self.assertEqual(
            faltan, [],
            "el export dice MENOS que la pantalla, y el export es lo que viaja",
        )

    def test_offtarget_seed_sale_POR_HEBRA_y_no_fundido(self):
        # Y POR CATALOGO desde el 2026-09-09: los slugs se piden a `catalogue_slugs`,
        # que los deriva de la especie. La columna fundida no puede quedar.
        for columna in _columnas_offtarget():
            self.assertIn(columna, self.cabecera)
        self.assertNotIn("offtarget_seed", self.cabecera)

    def test_empalme_sitios_tambien_esta_aunque_no_tenga_columna_en_pantalla(self):
        """El único frente sin columna en la tabla de sitios, y aquí sí sale.

        En pantalla se lee en su propio modal, con las 22 construcciones delante; el
        export no tiene modal, así que sin columna el frente desaparece del artefacto
        que viaja.
        """
        self.assertTrue(
            [c for c in self.cabecera if c.startswith("empalme_sitios")],
            self.cabecera,
        )

    def test_sin_corrida_de_empalme_NO_se_inventan_intrones(self):
        """Una sola columna y en `NOT_RUN`: nadie ha preguntado por ningún par."""
        columnas = [c for c in self.cabecera if c.startswith("empalme_sitios")]
        self.assertEqual(columnas, ["empalme_sitios"])


@unittest.skipUnless(HAY, "falta el fixture del ratón")
class TestLaCELDA_es_la_MISMA(unittest.TestCase):
    """No basta con que la columna exista: tiene que decir lo mismo, letra por letra."""

    @classmethod
    def setUpClass(cls):
        cls.corrida = _corrida()
        cls.almacenes = _almacen_offtarget(cls.corrida)

    def _export(self, stores):
        # Por `presentation.tsv_rows`, que salta el sello `# BUILD:`. `splitlines()[0]`
        # dejó de ser la cabecera el día que el fichero declara qué versión lo produjo.
        crudo = presentation.tsv_rows(outputs.tsv_selected(
            self.corrida.selection, species=ESPECIE,
            tiling=self.corrida.tiling, stores=stores,
        ))
        cabecera = crudo[0]
        return [dict(zip(cabecera, fila, strict=True)) for fila in crudo[1:]]

    def test_con_la_corrida_guardada_el_export_dice_PASS_como_la_pantalla(self):
        filas = self._export(self.almacenes)
        pantalla = presentation.site_table_rows(
            self.corrida.tiling, self.corrida.selection,
            species=ESPECIE, stores=self.almacenes,
        )
        por_inicio = {f["inicio"]: f for f in pantalla}
        for fila in filas:
            inicio = int(fila["inicio"].split(":")[-1])
            with self.subTest(inicio):
                for columna in _columnas_offtarget():
                    self.assertEqual(fila[columna], por_inicio[inicio][columna])
                    self.assertEqual(fila[columna], "PASS")

    def test_control_adversario_SIN_almacenes_la_misma_celda_NO_dice_PASS(self):
        """Sin esto, «coincide» y «la columna no mira nada» dan el mismo verde."""
        filas = self._export(None)
        for fila in filas:
            for columna in _columnas_offtarget():
                self.assertNotEqual(fila[columna], "PASS")

    def test_y_el_VEREDICTO_cuenta_lo_mismo_que_las_celdas(self):
        """La fila no puede decir `PASS` en una celda e ignorarla en su veredicto.

        Es la errata nº 51 dentro del export: dos números del mismo suceso, uno al lado
        del otro y los dos con pinta de medida.
        """
        for fila in self._export(self.almacenes):
            estados = {
                k: v for k, v in fila.items()
                if v in {e.value for e in FilterState}
            }
            self.assertEqual(
                fila["veredicto"], presentation.verdict_with_stores(estados)
            )


class TestElGuardiaDelExport(unittest.TestCase):
    """Mecánico: el export no puede volver a construir sus columnas por su cuenta.

    El guardia que ya había cubre `_filter_columns` dentro de `presentation.py` y por
    eso no vio esto: el export vive en `outputs.py` y montaba las suyas de
    `window.filters` a mano. La regla es la misma un módulo más allá — **quien emita un
    estado por filtro pide las columnas a `presentation`**, que es donde se decide qué
    dicen los almacenes.
    """

    def test_tsv_selected_acepta_tiling_y_stores(self):
        import inspect

        firma = inspect.signature(outputs.tsv_selected).parameters
        self.assertIn("tiling", firma)
        self.assertIn("stores", firma)

    def test_no_monta_sus_columnas_de_window_filters(self):
        import ast
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "shmir_design" / "outputs.py"
        ).read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        funcion = next(
            n for n in ast.walk(arbol)
            if isinstance(n, ast.FunctionDef) and n.name == "tsv_selected"
        )
        # `r.name for r in ...filters` era exactamente la línea que dejaba fuera a los
        # frentes sin filtro de ventana. Que no vuelva.
        atributos = [
            n.attr for n in ast.walk(funcion) if isinstance(n, ast.Attribute)
        ]
        self.assertNotIn("filters", atributos)


if __name__ == "__main__":
    unittest.main()
