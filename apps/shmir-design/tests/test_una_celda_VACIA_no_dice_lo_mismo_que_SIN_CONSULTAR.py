"""Una celda de carga en blanco no distingue «nadie lo ha medido» de «no estabas».

**Reportado el 2026-09-07 con el panel nuevo aplicado**: *«`3utr:359` sale con
`carga_8mer` y `carga_7mer-m8` vacías, y es el único de los once. La corrida de
off-targets es del panel anterior. Y una celda vacía no dice qué le pasa: los otros diez
traen número y percentil; éste, nada. Debería decir `SIN_CONSULTAR` como acordamos —
vacío se lee como "no se ha medido nunca" y lo que hay es "se midió el panel anterior y
éste no estaba"»*.

Es la **errata nº 55 en la familia de los números comparativos**. Allí se separó
`SIN_CONSULTAR` de `NOT_RUN` en las columnas de estado —«a este candidato no se le ha
preguntado» y «falta el fichero» son dos causas y se arreglan con cosas distintas— y esta
familia se quedó fuera porque **no tiene columna de estado**: el estado va DENTRO de la
celda, que es lo que ya hizo la errata nº 91 con `NOT_RUN` y `NO_PEDIDO`.

**Y la diferencia decide qué se hace, que es el criterio para separar dos estados**:
vacío manda a conseguir el fichero del transcriptoma; `SIN_CONSULTAR` manda a repetir la
corrida con el alcance que incluya a este candidato — que es lo que hay que hacer, y en
una corrida que son ≥10.000 sorteos por consulta la diferencia se paga.

Regla 5: escrito antes.
"""

import unittest

from shmir_design import identidad, presentation
from shmir_design.coords import Frame
from shmir_design.filters import FilterState
from shmir_design.offtarget import SITE_CLASSES

ESPECIE = "raton"
#: Los del panel que la corrida SÍ consultó, y el que entró después. Es la forma exacta
#: del caso: la corrida es del panel anterior y `3utr:359` no estaba en él.
CONSULTADOS = (10, 553, 819, 1018)
EL_NUEVO = 359


class _Cuentas:
    def __init__(self, sitios):
        self.sites = dict(sitios)


class _Resultado:
    def __init__(self, sitios, percentiles):
        self.counts = _Cuentas(sitios)
        self.percentiles = dict(percentiles)
        self.frame = Frame.UTR3


#: La fecha de la corrida falsa. Escrita UNA vez, porque el id se DERIVA de ella.
FECHA = "2026-09-06"


class _Corrida:
    # DERIVADO, no transcrito (principio nº 25): un id escrito a mano coincide con su
    # formato por construcción y deja de delatar el día que el formato cambie.
    run_id = identidad.run_id(
        kind="corrida_offtarget",
        date=FECHA,
        result_md5=identidad.result_fingerprint("corrida de prueba"),
    )
    date = FECHA
    source = "transcriptoma de prueba"

    class scan:
        controls = ()
        self_counts: dict = {}

    def __init__(self, resultados):
        self._resultados = resultados

    def result_for(self, consulta):
        return self._resultados.get(consulta)


class _Almacen:
    def __init__(self, corrida):
        self._corrida = corrida
        #: LO QUE DISTINGUE LOS DOS CASOS. Un almacén con corridas y sin resultado para
        #: este candidato no es un almacén vacío, y hasta hoy daban la misma celda.
        self.runs = (corrida,) if corrida is not None else ()

    def latest(self, consulta):
        if self._corrida is None:
            return None
        return self._corrida if self._corrida.result_for(consulta) else None

    def verdict_for(self, consulta):
        from shmir_design.filters import FilterResult

        return FilterResult(
            name="offtarget_seed", state=FilterState.PASS, reason="corrida de prueba",
        )


def _almacenes(*, con_corrida=True):
    if not con_corrida:
        return {"offtarget": _Almacen(None)}
    resultados = {
        presentation.query_name(ESPECIE, inicio, "guia"): _Resultado(
            {c: 3 for c in SITE_CLASSES}, {c: 40.0 for c in SITE_CLASSES},
        )
        for inicio in CONSULTADOS
    }
    return {"offtarget": _Almacen(_Corrida(resultados))}


class TestTresCeldasDistintas(unittest.TestCase):

    def _celdas(self, inicio, *, con_corrida=True):
        return presentation.seed_load_columns(
            stores=_almacenes(con_corrida=con_corrida), species=ESPECIE, start=inicio,
        )

    def test_el_CONSULTADO_trae_el_numero_con_su_percentil(self):
        celda = self._celdas(CONSULTADOS[0])["carga_8mer"]
        self.assertIn("3", celda)
        self.assertIn("p", celda)

    def test_el_QUE_NO_ESTABA_dice_SIN_CONSULTAR(self):
        for clase in SITE_CLASSES:
            with self.subTest(clase):
                self.assertEqual(
                    self._celdas(EL_NUEVO)[f"carga_{clase}"],
                    presentation.SIN_CONSULTAR,
                    "una celda en blanco no distingue «no estabas en la corrida» de "
                    "«nadie lo ha medido nunca», y se arreglan con cosas distintas.",
                )

    def test_y_SIN_NINGUNA_corrida_sigue_VACIA(self):
        # El control adversario: si `SIN_CONSULTAR` saliera también aquí, diría que hay
        # una corrida que no incluye a nadie — y lo que hay es que no hay ninguna.
        for clase in SITE_CLASSES:
            with self.subTest(clase):
                self.assertEqual(
                    self._celdas(EL_NUEVO, con_corrida=False)[f"carga_{clase}"], "",
                )

    def test_sin_almacenes_tampoco_se_inventa_un_estado(self):
        celdas = presentation.seed_load_columns(
            stores=None, species=ESPECIE, start=EL_NUEVO,
        )
        self.assertEqual(set(celdas.values()), {""})

    def test_NUNCA_a_cero(self):
        # La regla de siempre: un número comparativo que no se calculó va vacío o con su
        # estado, jamás a cero — un cero se lee como una medida.
        celdas = self._celdas(EL_NUEVO)
        self.assertNotIn("0", set(celdas.values()))


class TestLaTablaYelExportDicenLoMismo(unittest.TestCase):
    """Las dos superficies leen las mismas celdas, así que no pueden discrepar."""

    def test_es_la_MISMA_funcion_la_que_las_monta(self):
        import inspect

        for fuente in (
            inspect.getsource(presentation.candidate_rows),
            inspect.getsource(
                __import__("shmir_design.comparative", fromlist=["comparative_rows"])
                .comparative_rows
            ),
        ):
            self.assertIn("seed_load_columns(", fuente)


if __name__ == "__main__":
    unittest.main()
