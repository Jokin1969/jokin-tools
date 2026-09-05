"""El hallazgo de la corrida: un sitio de empalme que **cambia con la guía**.

**Medido (2026-09-05)**, y es literalmente lo que este frente existe para encontrar: un
**aceptor** en `construccion:3261` —dentro del módulo de 149 nt, sobre un `AG` real—
puntúa **0,075 en `3utr:959`**, **0,012 en `3utr:1684`** y por debajo de 0,01 en las otras
ocho. El `GTGAGCG`, que es el críptico que motivó el modal, puntúa **cero en las diez**.

**El valor no es la alarma.** En el peor caso llega al 11 % del donante legítimo, muy por
debajo del 50 % que dispara el aviso. Lo que vale es que **existe un eje por el que la guía
modula el empalme y ahora está medido** — así que sale DESTACADO, no como una nota al pie.

Y el efecto general va con él: el **donante legítimo**, que es el mismo sitio en las diez
construcciones, va de **0,664 a 0,871** — un **31 %** con el módulo a más de 100 nt.

`exclusive_rows` no lo cubre: busca crípticos que una construcción tiene y **ninguna** de
sus hermanas, y éste aparece en dos de diez. La pregunta no es «¿es exclusivo?» sino
**«¿varía con la guía?»**.

Regla 5: escritos antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation, spliceai  # noqa: E402
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_reference,
)
from shmir_design.scaffold import SGEP_SCAFFOLD  # noqa: E402

RATON = REFERENCES["NM_011170.3"]
CASETE = RAIZ / "data" / "reference" / "aav_casete.fa"
MEDIDO = RAIZ / "data" / "medido" / "spliceai_mvm_actual_2026-09-05.tsv"
HAY = fixture_available(RATON) and CASETE.exists() and MEDIDO.exists()


def _scan():
    tx = load_reference(RATON)
    anat = Anatomy.from_cds(
        cds=RATON.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
    )
    corrida = presentation.page_run(species="raton", sequence=tx, anatomy=anat)
    casete = "".join(
        l.strip() for l in CASETE.read_text("utf-8").splitlines()
        if not l.startswith(">")
    )
    panel = spliceai.build_panel(
        corrida.selection, intron_names=("mvm_actual",), scaffold=SGEP_SCAFFOLD,
        cassette=casete, context_nt=5000,
    )
    por_nombre = {c.name: c for c in panel.constructions}
    lineas = ["# convencion: spliceai"]
    with MEDIDO.open("r", encoding="utf-8") as f:
        lineas.append(next(f).rstrip("\n"))
        for fila in f:
            nombre, _md5, pos, tipo, pun = fila.rstrip("\n").split("\t")
            if nombre in por_nombre:
                lineas.append(
                    "\t".join((nombre, por_nombre[nombre].md5, pos, tipo, pun))
                )
    crudo = "\n".join(lineas) + "\n"
    return panel, spliceai.scan_from_result(crudo, constructions=panel.constructions)


@unittest.skipUnless(HAY, "faltan la referencia murina, el casete o el medido")
class TestElSitioQueVARIA_con_la_guia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.panel, cls.scan = _scan()
        cls.variables = spliceai.guide_dependent_sites(cls.scan)

    def test_sale_el_ACEPTOR_del_modulo(self):
        posiciones = {(s.position, s.kind) for s in self.variables}
        self.assertIn((3261, "aceptor"), posiciones)

    def test_y_trae_LAS_DIEZ_puntuaciones(self):
        sitio = next(
            s for s in self.variables if (s.position, s.kind) == (3261, "aceptor")
        )
        self.assertEqual(len(sitio.scores), 10)
        self.assertAlmostEqual(sitio.maximum, 0.0751, places=3)
        self.assertAlmostEqual(
            sitio.scores["mvm_actual__3utr959"], 0.0751, places=3,
        )

    def test_cae_DENTRO_del_intron_no_en_el_contexto(self):
        sitio = next(
            s for s in self.variables if (s.position, s.kind) == (3261, "aceptor")
        )
        self.assertEqual(sitio.region, "intron")

    def test_el_sitio_del_CONTEXTO_no_sale_porque_NO_varia(self):
        """El donante de 1517 es el más fuerte de las diez y NO depende de la guía."""
        posiciones = {(s.position, s.kind) for s in self.variables}
        self.assertNotIn((1517, "donante"), posiciones)

    def test_ORDENADO_por_cuanto_varia_no_por_su_valor(self):
        recorridos = [s.spread for s in self.variables]
        self.assertEqual(recorridos, sorted(recorridos, reverse=True))

    def test_el_criterio_es_RELATIVO_y_no_un_corte_absoluto(self):
        # Lo que decide es que la razón entre hermanas sea grande, no que el número lo
        # sea: aquí el máximo es 0,075 y aun así el sitio es el hallazgo.
        sitio = next(
            s for s in self.variables if (s.position, s.kind) == (3261, "aceptor")
        )
        self.assertLess(sitio.maximum, 0.1)
        self.assertGreater(sitio.spread, 1.0)


@unittest.skipUnless(HAY, "faltan la referencia murina, el casete o el medido")
class TestSaleDESTACADO_y_no_al_pie(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.panel, cls.scan = _scan()
        cls.destacados = presentation.splice_highlights(cls.scan)

    def test_hay_un_destacado_PROPIO_y_esta_activo(self):
        bloque = self.destacados["depende_de_la_guia"]
        self.assertTrue(bloque["activo"])
        self.assertIn("3261", bloque["texto"])
        self.assertIn("construcción:3261", bloque["texto"])

    def test_dice_que_el_VALOR_no_es_la_alarma(self):
        texto = self.destacados["depende_de_la_guia"]["texto"]
        self.assertIn("11", texto)
        self.assertIn("eje", texto.lower())

    def test_y_la_MODULACION_del_legitimo_va_con_el(self):
        bloque = self.destacados["modulacion"]
        self.assertTrue(bloque["activo"])
        self.assertIn("31", bloque["texto"])
        self.assertIn("0,664", bloque["texto"])
        self.assertIn("0,871", bloque["texto"])

    def test_las_filas_llevan_LAS_DIEZ_para_poder_mirarlas(self):
        filas = presentation.splice_guide_dependent_rows(self.scan)
        fila = next(f for f in filas if f["posicion"] == 3261)
        self.assertEqual(fila["region"], "intron")
        self.assertEqual(len(fila["por_construccion"]), 10)
        self.assertIn("3utr:959", str(fila["por_construccion"]))


if __name__ == "__main__":
    unittest.main()
