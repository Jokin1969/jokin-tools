"""Los percentiles de carga salen DESTACADOS, y la convergencia de dos señales con ellos.

Regla 5: escritos antes.

**Pedido el 2026-09-07**, con la corrida delante y con la lectura ya hecha por quien lo
pide: *«los percentiles de carga son el primer eje que reparte de verdad. `3utr:819` está
en el percentil 99,7 — de mil seeds aleatorias de su composición, sólo tres tienen más
sitios. Y es el mismo que ya tenía dos sitios `7mer-m8` en la propia diana. Dos señales
independientes sobre el mismo candidato. Que eso salga destacado: es desempate, no filtro,
pero es el primer número que separa a los once de forma clara. Y `3utr:1018` sale bien
colocado en los dos ejes»*.

### Qué había y qué faltaba

El percentil **ya salía**, pegado a su conteo en la celda de cada clase
(`seed_load_reference`, 2026-09-03) — que es la regla del proyecto: toda cifra comparativa
con su referencia. Lo que no salía es la LECTURA: con once candidatos × cuatro clases hay
44 celdas, y el hallazgo se queda dentro de la tabla. Es el mismo caso que el punto de
ramificación —calculado, y había que comparar cuatro columnas a ojo sobre 22 filas— y el
mismo principio nº 23: dos artefactos leen el mismo estado y sólo uno lo cuenta.

### Y la convergencia es lo que no se puede leer de ninguna tabla

Son **dos ejes independientes y dos tablas distintas**: el percentil sale de la nula por
permutación contra el transcriptoma, y el autoconteo de barrer la PROPIA diana. Que
coincidan en el mismo candidato no lo dice ninguna de las dos por separado, y cruzarlas a
mano es lo que nadie hace.

**Todo se DERIVA de la corrida guardada.** Ni un percentil escrito: con otra corrida —o
con otro panel— el destacado señala a otro candidato, o a ninguno, y se entera solo.
"""

import unittest

from shmir_design.coords import Frame

from shmir_design import presentation
from shmir_design.filters import FilterResult, FilterState
from shmir_design.identidad import run_id

ESPECIE = "raton"


class _Cuentas:
    def __init__(self, sitios):
        self.sites = dict(sitios)


class _Resultado:
    #: EL MARCO VIAJA EN EL RESULTADO, igual que en `offtarget.LoadResult`. Este doble lo
    #: lleva porque la lectura lo LEE de aqui: escribirlo en `seed_load_highlights` fue el
    #: emisor de la errata nº 138 —`3utr:1768` por `tx:1768`— y un doble sin este campo
    #: dejaria de probar el camino que la app recorre.
    def __init__(self, sitios, percentiles, frame=Frame.UTR3):
        self.counts = _Cuentas(sitios)
        self.percentiles = dict(percentiles)
        self.frame = frame


class _Autoconteo:
    def __init__(self, query, ocurrencias):
        self.query = query
        self.occurrences = ocurrencias
        self.expected = 1
        self.target_label = "3utr:1-1242"
        self.sites = {}
        self.detail = ()

    @property
    def anomalous(self):
        return self.occurrences != self.expected

    def describe(self):
        return f"{self.query}: {self.occurrences} sitio(s) en {self.target_label}."


class _Scan:
    def __init__(self, autoconteos):
        self.controls = ()
        self.self_counts = dict(autoconteos)

    @property
    def anomalous_self_counts(self):
        return tuple(s for s in self.self_counts.values() if s.anomalous)


class _Corrida:
    def __init__(self, resultados, autoconteos):
        # El id se PIDE, no se teclea: aquí sólo es la etiqueta de un almacén falso, y
        # aun así escribirlo es la forma que tiene un test de coincidir consigo mismo.
        self.run_id = run_id(
            kind="corrida_offtarget", date="2026-09-06", result_md5="6d81dab8",
        )
        self.date = "2026-09-06"
        self.source = "transcriptoma_3utr.fa"
        self._resultados = resultados
        self.scan = _Scan(autoconteos)

    def result_for(self, consulta):
        return self._resultados.get(consulta)


class _Almacen:
    def __init__(self, corrida):
        self._corrida = corrida
        self.runs = (corrida,)

    def latest(self, consulta):
        return self._corrida if self._corrida.result_for(consulta) else None

    def history(self, consulta):
        return (self._corrida,) if self._corrida.result_for(consulta) else ()

    def verdict_for(self, consulta):
        return FilterResult(
            name="offtarget_seed", state=FilterState.PASS, reason="corrida de prueba",
        )


#: Las cifras REALES de la corrida `ot-2026-09-06-6d81dab8`, tal y como se reportaron.
#: Aquí son la ENTRADA del test, no su valor esperado: lo que se comprueba es la lectura
#: que la app deriva de ellas.
MEDIDO = {
    819: {"8mer": (12, 95.3), "7mer-m8": (31, 99.7)},
    553: {"8mer": (7, 79.5), "7mer-m8": (9, 61.0)},
    10: {"8mer": (2, 10.7), "7mer-m8": (3, 9.3)},
    1018: {"8mer": (4, 32.6), "7mer-m8": (5, 19.7)},
}
#: `3utr:819` tiene DOS sitios `7mer-m8` en el propio 3'UTR de Prnp; los demás, uno.
AUTOCONTEO = {819: 2, 553: 1, 10: 1, 1018: 1}


def _almacenes():
    resultados, autoconteos = {}, {}
    for inicio, clases in MEDIDO.items():
        consulta = presentation.query_name(ESPECIE, inicio, "guia")
        resultados[consulta] = _Resultado(
            {c: v[0] for c, v in clases.items()},
            {c: v[1] for c, v in clases.items()},
        )
        autoconteos[consulta] = _Autoconteo(consulta, AUTOCONTEO[inicio])
    return {"offtarget": _Almacen(_Corrida(resultados, autoconteos))}


class TestElDestacadoDeLaCarga(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.destacados = presentation.seed_load_highlights(
            stores=_almacenes(), species=ESPECIE, starts=sorted(MEDIDO),
        )

    def test_hay_un_destacado_PROPIO_y_esta_activo(self):
        bloque = self.destacados["carga"]
        self.assertTrue(bloque["activo"])

    def test_nombra_al_MAS_CARGADO_y_su_percentil(self):
        texto = self.destacados["carga"]["texto"]
        self.assertIn("3utr:819", texto)
        self.assertIn("99,7", texto)

    def test_el_percentil_se_dice_EN_PALABRAS_ademas_de_en_numero(self):
        """«p99,7» no se lee. «de mil, sólo tres tienen más sitios» sí."""
        texto = self.destacados["carga"]["texto"]
        self.assertIn("1.000", texto)
        self.assertIn("3", texto)

    def test_la_CONVERGENCIA_sale_como_bloque_propio(self):
        bloque = self.destacados["convergencia"]
        self.assertTrue(bloque["activo"])
        self.assertIn("3utr:819", bloque["texto"])
        self.assertIn("independientes", bloque["texto"].lower())

    def test_y_dice_POR_QUE_son_dos_señales_y_no_una(self):
        """Dos tablas distintas: la nula contra el transcriptoma y la propia diana."""
        texto = self.destacados["convergencia"]["texto"]
        self.assertIn("propia diana", texto)
        self.assertIn("permutación", texto)

    def test_los_BIEN_COLOCADOS_tambien_salen(self):
        """No sólo la alarma: el que está bajo en todos los ejes es información."""
        bloque = self.destacados["bien_colocados"]
        self.assertTrue(bloque["activo"])
        self.assertIn("3utr:1018", bloque["texto"])
        self.assertIn("3utr:10", bloque["texto"])
        self.assertNotIn("3utr:819", bloque["texto"])

    def test_el_USO_va_pegado_y_dice_que_es_DESEMPATE(self):
        self.assertTrue(self.destacados["uso"]["activo"])
        texto = self.destacados["uso"]["texto"]
        self.assertIn("desempate", texto.lower())
        self.assertIn("nunca", texto.lower())

    def test_el_umbral_va_DECLARADO_como_parametro(self):
        self.assertIsInstance(presentation.PERCENTIL_DESTACADO, float)
        self.assertIn(
            str(presentation.PERCENTIL_DESTACADO).replace(".", ","),
            self.destacados["carga"]["texto"],
        )


class TestElControlAdversario(unittest.TestCase):
    """Sin esto, «no hay convergencia» y «esto no cruza nada» dan lo mismo."""

    def test_sin_autoconteo_anomalo_NO_hay_convergencia_y_el_resto_sigue(self):
        resultados, autoconteos = {}, {}
        for inicio, clases in MEDIDO.items():
            consulta = presentation.query_name(ESPECIE, inicio, "guia")
            resultados[consulta] = _Resultado(
                {c: v[0] for c, v in clases.items()},
                {c: v[1] for c, v in clases.items()},
            )
            autoconteos[consulta] = _Autoconteo(consulta, 1)
        destacados = presentation.seed_load_highlights(
            stores={"offtarget": _Almacen(_Corrida(resultados, autoconteos))},
            species=ESPECIE, starts=sorted(MEDIDO),
        )
        self.assertFalse(destacados["convergencia"]["activo"])
        # Y el destacado de la carga SIGUE activo: son dos cosas distintas.
        self.assertTrue(destacados["carga"]["activo"])

    def test_con_todos_BAJOS_no_se_destaca_ninguno(self):
        resultados, autoconteos = {}, {}
        for inicio in MEDIDO:
            consulta = presentation.query_name(ESPECIE, inicio, "guia")
            resultados[consulta] = _Resultado(
                {"8mer": 1, "7mer-m8": 1}, {"8mer": 10.0, "7mer-m8": 12.0},
            )
            autoconteos[consulta] = _Autoconteo(consulta, 1)
        destacados = presentation.seed_load_highlights(
            stores={"offtarget": _Almacen(_Corrida(resultados, autoconteos))},
            species=ESPECIE, starts=sorted(MEDIDO),
        )
        self.assertFalse(destacados["carga"]["activo"])

    def test_SIN_CORRIDA_no_se_inventa_ninguna_lectura(self):
        destacados = presentation.seed_load_highlights(
            stores=None, species=ESPECIE, starts=sorted(MEDIDO),
        )
        for clave in ("carga", "convergencia", "bien_colocados", "uso"):
            with self.subTest(clave):
                self.assertFalse(destacados[clave]["activo"])
        # Y el texto de la carga NO dice que nadie esté cargado: dice que nadie ha
        # mirado. Son dos cosas y el «Alu 0 %» es confundirlas.
        self.assertIn("NOT_RUN", destacados["carga"]["texto"])


if __name__ == "__main__":
    unittest.main()
