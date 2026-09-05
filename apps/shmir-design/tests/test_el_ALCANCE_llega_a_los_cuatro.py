"""El alcance que ofrece el selector es el que aceptan los cuatro modales.

**Reportado (2026-09-05)**: *«el selector de alcance ofrece "Todos los sitios elegibles —
86" y luego lo rechaza … Son dos definiciones de qué candidatos valen en el mismo flujo,
y gana la restrictiva»*.

Y con el diagnóstico correcto, que es de quien lo reportó: *«si es el mismo `panel` que se
pasa aguas abajo sin mirar el alcance elegido, están los cuatro»*. **Están los cuatro**, y
por tres caminos distintos:

| modal | cómo resolvía el inicio | qué hacía con uno de fuera del panel |
|---|---|---|
| especificidad | `{c.start: c for c in selection.chosen}` en `blast_query` | **aborta** |
| colisión de seed | lo mismo en `seed_scan._strands` | **aborta** |
| carga de off-targets | usa `_strands` del anterior | **aborta** |
| empalme | `[c for c in chosen if c.start in starts]` | **NO aborta: emite el panel** |

El cuarto es el peor: el selector anuncia 172 consultas, la app emite 20 y no dice nada.
Es la errata nº 97 otra vez, entrando por el eje del alcance.

**El arreglo no es cuatro parches.** Un inicio se resuelve a su candidato en UN SOLO
sitio, `ReportSelection.choices_for`, que es el objeto que tiene los dos conjuntos —el
panel y los sitios elegibles—. `presentation._choices_de` ya lo hacía bien y estaba en la
capa que el núcleo no puede llamar, así que la definición buena era inalcanzable
justamente para quien la necesitaba.

Regla 5: escrito antes.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from shmir_design import presentation, spliceai  # noqa: E402
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.errors import ShmirDesignError  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_reference,
)
from shmir_design.scaffold import SGEP_SCAFFOLD  # noqa: E402

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _corrida():
    tx = load_reference(RATON)
    anat = Anatomy.from_cds(
        cds=RATON.cds, length=len(tx), source=RegionSource.FIXTURE_VERIFICADO,
    )
    return presentation.page_run(species="raton", sequence=tx, anatomy=anat)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElResolutorEsUNO(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sel = _corrida().selection
        cls.panel = tuple(c.start for c in cls.sel.selection.chosen)
        cls.todos = presentation.scope_starts(cls.sel, "elegibles")

    def test_el_alcance_grande_es_MAYOR_que_el_panel(self):
        # Si no lo fuera, el test no probaría nada: no habría inicios de fuera.
        self.assertGreater(len(self.todos), len(self.panel))
        self.assertTrue(set(self.panel) <= set(self.todos))

    def test_vive_en_ReportSelection_que_es_quien_tiene_los_DOS_conjuntos(self):
        elegidos = self.sel.choices_for(self.todos)
        self.assertEqual(len(elegidos), len(self.todos))
        self.assertEqual([c.start for c in elegidos], sorted(self.todos))

    def test_y_presentation_DELEGA_en_vez_de_repetirlo(self):
        propios = [c.start for c in presentation._choices_de(self.sel, self.todos)]
        del_nucleo = [c.start for c in self.sel.choices_for(self.todos)]
        self.assertEqual(propios, del_nucleo)

    def test_un_inicio_QUE_NO_ES_DE_NADIE_sigue_abortando(self):
        # Lo que se abre es el panel→elegibles, no cualquier número.
        with self.assertRaises(ShmirDesignError):
            self.sel.choices_for((7,))


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLosCuatroACEPTANelAlcanceGrande(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sel = _corrida().selection
        cls.todos = presentation.scope_starts(cls.sel, "elegibles")
        cls.fuera = tuple(
            s for s in cls.todos
            if s not in {c.start for c in cls.sel.selection.chosen}
        )[:3]

    def test_especificidad_emite_el_FASTA_de_los_de_fuera(self):
        fasta = presentation.blast_query(
            self.sel, species="raton", starts=self.fuera,
            guides=True, passengers=False,
        )
        self.assertEqual(len(fasta.records), len(self.fuera))

    def test_colision_de_seed_los_previsualiza(self):
        filas = presentation.seed_preview_rows(
            self.sel, species="raton", starts=self.fuera,
        ) if hasattr(presentation, "seed_preview_rows") else None
        from shmir_design import seed_scan
        filas = seed_scan.preview_rows(
            self.sel, species="raton", starts=self.fuera,
            guides=True, passengers=False,
        )
        self.assertEqual(len(filas), len(self.fuera))

    def test_empalme_MONTA_los_de_fuera_en_vez_de_emitir_el_panel(self):
        # El fallo peor: no abortaba, emitía 10 y el selector anunciaba 172.
        panel = spliceai.build_panel(
            self.sel, intron_names=("mvm_actual",), scaffold=SGEP_SCAFFOLD,
            starts=self.fuera,
        )
        self.assertEqual(
            sorted(c.candidate_start for c in panel.constructions), sorted(self.fuera)
        )

    def test_y_el_alcance_GRANDE_entero_sale_en_los_cuatro_recuentos(self):
        filas = presentation.blast_candidate_rows(
            self.sel, species="raton", starts=self.todos,
        )
        self.assertEqual(len(filas), len(self.todos))
        # y la marca de panel sigue DERIVÁNDOSE, que es lo que la hace significar algo
        self.assertEqual(
            sum(1 for f in filas if f["panel"]), len(self.sel.selection.chosen)
        )


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElMENSAJEnoCulpaAlaEntrada(unittest.TestCase):
    """*«"Una guía que no existe aquí" sugiere que pedí algo raro»*."""

    def test_el_motivo_habla_de_ventanas_ELEGIBLES_no_del_panel(self):
        sel = _corrida().selection
        with self.assertRaises(ShmirDesignError) as ctx:
            sel.choices_for((7,))
        texto = str(ctx.exception)
        self.assertIn("elegible", texto)
        self.assertNotIn("no existe aquí", texto)


class TestNadieVUELVE_a_resolver_un_inicio_por_su_cuenta(unittest.TestCase):
    """El guardia mecánico: un quinto modal no puede reintroducirlo.

    Cuatro modales, tres implementaciones y un fallo — arreglarlos de uno en uno deja
    exactamente el mismo hueco para el siguiente.

    **CALIBRADO MIDIENDO** (principio nº 34), porque la forma del fallo y la condición
    que lo hace posible no son la misma cosa:

    | criterio | hallazgos | reales |
    |---|---|---|
    | «indexa el panel por inicio» | 2 | 1 — `site_table_rows` lo hace para MARCAR filas que ya vienen del tilado, y eso es correcto |
    | «recibe `starts` y construye algo sobre el panel» | 2 | 1 — `blast_candidate_rows` hace un CONJUNTO de inicios, y de ahí sale la marca `panel` que la errata nº 32 obligó a derivar |
    | **«recibe `starts` y construye un ÍNDICE inicio→candidato sobre el panel»** | **1** | **1** |

    Las dos distinciones son de significado y no de sintaxis. **Recibir el alcance** es lo
    que hace peligroso resolverlo: una función que no lo recibe está mirando otra cosa. Y
    **un `dict` inicio→candidato RESUELVE, un `set` de inicios sólo MARCA**: con el
    conjunto no se puede sacar la guía de nadie, así que no puede rechazar ni mentir.

    Con cualquiera de los dos criterios anchos queda un falso positivo, y un guardia con
    falsos positivos se acaba apagando — el falso positivo empuja a quitar la
    comprobación, que es exactamente lo que este guardia viene a evitar.
    """

    #: Quien SÍ puede: es el dueño de los dos conjuntos.
    DUEÑO = "selection.py"
    #: Los nombres con los que el alcance viaja hasta el núcleo.
    ALCANCE = {"starts", "pedidos"}

    def _culpables(self, fuentes):
        import ast

        salida = []
        for nombre, texto in fuentes:
            if nombre == self.DUEÑO:
                continue
            arbol = ast.parse(texto)
            for fn in ast.walk(arbol):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                args = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
                if not (args & self.ALCANCE):
                    continue
                for nodo in ast.walk(fn):
                    # Sólo el `dict`: un `set` de inicios marca, no resuelve.
                    if not isinstance(nodo, ast.DictComp):
                        continue
                    if "selection.chosen" in ast.unparse(nodo):
                        salida.append(f"{nombre}:{fn.name}: {ast.unparse(nodo)}")
        return salida

    def test_quien_recibe_el_alcance_NO_lo_resuelve_contra_el_panel(self):
        raiz = RAIZ / "shmir_design"
        fuentes = [
            (f.name, f.read_text(encoding="utf-8")) for f in sorted(raiz.glob("*.py"))
        ]
        self.assertEqual(
            self._culpables(fuentes), [],
            "reciben el alcance y lo resuelven contra el panel en vez de pedírselo a "
            "`ReportSelection.choices_for`: con el alcance grande rechazan o mienten.",
        )

    def test_y_el_guardia_MUERDE_sobre_el_codigo_QUE_HABIA(self):
        # Sin esto, «ningún culpable» y «el patrón no lo encuentra nadie» dan el mismo
        # verde (errata nº 29). Es `blast_query` tal cual estaba.
        antes = (
            "def blast_query(selection, *, species, starts, guides, passengers):\n"
            "    pedidos = list(starts)\n"
            "    por_inicio = {c.start: c for c in selection.selection.chosen}\n"
            "    return por_inicio\n"
        )
        self.assertEqual(len(self._culpables([("antes.py", antes)])), 1)

    def test_y_NO_muerde_donde_solo_se_MARCA_una_fila(self):
        # Los dos falsos positivos que descartaron los criterios anchos, tal cual son.
        sin_alcance = (
            "def site_table_rows(tiling, selection, selected=None):\n"
            "    por_inicio = {c.start: c for c in selection.selection.chosen}\n"
            "    return por_inicio\n"
        )
        conjunto = (
            "def blast_candidate_rows(selection, species, starts=None):\n"
            "    del_panel = {c.start for c in selection.selection.chosen}\n"
            "    return del_panel\n"
        )
        self.assertEqual(self._culpables([("a.py", sin_alcance)]), [])
        self.assertEqual(self._culpables([("b.py", conjunto)]), [])


if __name__ == "__main__":
    unittest.main()
