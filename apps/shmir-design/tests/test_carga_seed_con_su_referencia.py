"""`carga_seed` sale con su percentil y con los controles, o no se puede leer.

**Reportado (2026-09-03)**, y con la observación que lo motiva: *«carga_seed es la primera
columna que discrimina de verdad — de 1.054 a 19.020, factor 18 entre el mejor y el peor.
Pero le falta el percentil contra la nula por permutación y los controles de miR-124,
miR-9 y let-7: sin ellos, 19.020 no se puede interpretar. Estaba en el diseño del modal y
no aparece en el export.»*

Es la regla de redacción del propio proyecto —**toda cifra comparativa con su
referencia**— aplicada a la única columna que todavía salía desnuda. Y es el principio
nº 23 otra vez: la nula y los controles **se calculan** en el modal de off-targets y se
guardan en el registro; lo que faltaba es que llegaran al artefacto que se lee.

### LA DECISIÓN QUE HAY QUE DEJAR ESCRITA: no hay percentil de `carga_seed`

`carga_seed` es un TOTAL —la suma de tres clases de sitio— y `offtarget.WHY_NOT_SUMMED`
prohíbe sumar las clases, porque la represión esperada de un 8mer y la de un 6mer no se
parecen en nada. Así que **el percentil que se pidió no puede calcularse sobre 19.020**:
sería un percentil de una cantidad que este proyecto tiene decidido que no significa nada.

Lo que sí se puede, y es lo que se hace: emitir **cada clase con su percentil pegado**,
que es la misma forma que `describe_sequence` («longitud y md5 JUNTOS») — una cifra
comparativa nunca se separa de su referencia. Y los controles aparte, como MAGNITUD: la
nula dice si un número es raro para esa composición, y los controles dicen qué es «muchos
sitios» en biología. Son dos referencias distintas y ninguna sustituye a la otra.

Regla 5: escritos antes.
"""

import unittest

from shmir_design import presentation


class _NulaFalsa:
    def __init__(self, valor):
        self._valor = valor

    def percentile(self, clase, valor):
        return self._valor


class _CorridaFalsa:
    """Con la MISMA forma que `OfftargetRun`: `result_for` y `scan`."""

    def __init__(self, scan):
        self.scan = scan
        self.run_id = "offtarget-2026-09-03-abc"
        self.date = "2026-09-03"
        self.source = "UCSC (mm39)"

    def result_for(self, consulta):
        return next((r for r in self.scan.results if r.query == consulta), None)


class _AlmacenFalso:
    """Con la MISMA forma que `OfftargetStore`: `latest(consulta)`."""

    def __init__(self, scan):
        self.corrida = _CorridaFalsa(scan)

    def latest(self, consulta):
        return self.corrida if self.corrida.result_for(consulta) else None


def _scan(starts, *, con_controles=True):
    from shmir_design.offtarget import SITE_CLASSES, Control
    from shmir_design.presentation import query_name

    class _Cuentas:
        def __init__(self):
            self.sites = {c: 10 + i for i, c in enumerate(SITE_CLASSES)}
            self.transcripts = {c: 5 for c in SITE_CLASSES}

    class _Resultado:
        def __init__(self, inicio, hebra, consulta):
            self.start = inicio
            self.strand = hebra
            self.query = consulta
            self.counts = _Cuentas()
            self.percentiles = {c: 97.5 for c in SITE_CLASSES}

    class _Scan:
        def __init__(self):
            # LA CLAVE SE PIDE, no se escribe: un test que escribe la clave por la
            # que pregunta coincide por construcción (principio nº 25).
            self.results = tuple(
                _Resultado(s, "guia", query_name("raton", s, "guia")) for s in starts
            )
            self.controls = (
                tuple(
                    Control(
                        name=f"mmu-{n}", heptamer="ACGTACG",
                        sites={c: 1000 for c in SITE_CLASSES},
                    )
                    for n in ("miR-124-3p", "miR-9-5p", "let-7a-5p")
                )
                if con_controles else ()
            )

        def for_strand(self, hebra):
            return tuple(r for r in self.results if r.strand == hebra)

    return _Scan()


class TestSinCorridaElNumeroNOsePresentaCOMOlegible(unittest.TestCase):
    """Un total sin referencia no se emite como si se pudiera leer."""

    def test_sin_almacen_las_columnas_van_VACIAS_y_nunca_a_cero(self):
        vista = presentation.seed_load_reference(
            stores=None, species="raton", starts=(10, 20)
        )
        self.assertFalse(vista["hay"])
        self.assertEqual(vista["por_candidato"], {})
        self.assertEqual(vista["controles"], [])

    def test_y_el_texto_DICE_que_falta_y_como_se_consigue(self):
        vista = presentation.seed_load_reference(
            stores=None, species="raton", starts=(10, 20)
        )
        self.assertIn("NOT_RUN", vista["texto"])
        self.assertIn("percentil", vista["texto"])
        # Los tres controles se nombran aunque no haya corrida: son parte de lo que falta.
        for control in ("miR-124-3p", "miR-9-5p", "let-7a-5p"):
            self.assertIn(control, vista["texto"])


class TestConCorridaLLEGANelPercentilYlosControles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vista = presentation.seed_load_reference(
            stores={"offtarget": _AlmacenFalso(_scan((10, 20)))},
            species="raton", starts=(10, 20),
        )

    def test_cada_clase_lleva_su_percentil_PEGADO(self):
        from shmir_design.offtarget import SITE_CLASSES

        for inicio in (10, 20):
            celdas = self.vista["por_candidato"][inicio]
            for clase in SITE_CLASSES:
                self.assertIn("p97.5", celdas[clase])

    def test_NO_hay_percentil_del_total(self):
        # `carga_seed` es una suma de clases y `WHY_NOT_SUMMED` prohibe sumarlas: un
        # percentil de 19.020 seria el percentil de una cantidad que no se refiere a nada.
        celdas = self.vista["por_candidato"][10]
        self.assertNotIn("carga_seed", celdas)
        self.assertNotIn("total", celdas)

    def test_los_TRES_controles_salen_con_su_conteo(self):
        nombres = [c["nombre"] for c in self.vista["controles"]]
        self.assertEqual(len(nombres), 3)
        for esperado in ("miR-124-3p", "miR-9-5p", "let-7a-5p"):
            self.assertTrue(any(esperado in n for n in nombres), nombres)

    def test_los_controles_NO_llevan_percentil_y_se_dice_por_que(self):
        # Un percentil se calcula contra la nula de SU PROPIA composicion, asi que el de
        # un control contra la nuestra no querria decir nada. Aportan MAGNITUD.
        for control in self.vista["controles"]:
            self.assertNotIn("percentil", control)
        self.assertIn("magnitud", self.vista["texto"].lower())


class TestLaTablaDeCandidatosLLEVAlasColumnas(unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main()
