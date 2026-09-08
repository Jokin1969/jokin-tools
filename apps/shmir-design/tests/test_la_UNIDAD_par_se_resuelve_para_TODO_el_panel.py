"""Con una corrida GUARDADA de verdad, `empalme_sitios` se resuelve par a par.

Regla 5: escrito antes.

**Pedido el 2026-09-07, con la corrida ya guardada y el frente todavía abierto**:
*«Comprueba que la unidad candidato × intrón se resuelve para los once — la corrida cubre
22 pares, once candidatos × dos intrones»*.

Los tests que había de este frente usan un almacén FALSO: comprueban la regla
(`_estado_por_par`, `PAIR_UNIT_FRONTS`) y no atraviesan el camino de verdad — el que va
del fichero de SpliceAI al `registro.jsonl`, y de ahí a la celda de la tabla y al
veredicto del candidato. Es el principio nº 17: entre lo que la alcanzabilidad ve y lo
que el golden lee vive el código llamado desde caminos que nadie recorre. **Un cliente
que no se parece al real no prueba nada.**

Aquí se usa el resultado REAL versionado —`data/medido/spliceai_dos_intrones_2026-09-05.tsv`,
las diez construcciones del panel de entonces con las DOS arquitecturas—, se guarda en un
proyecto de verdad, se vuelve a abrir, y se mira lo que dicen la tabla y el veredicto.

### Y lo que encontró

Los pares se resolvían y **la celda seguía diciendo `NOT_RUN`**: `front_columns` derivaba
la columna `empalme_sitios` de `blocking_fronts` —siempre la tuvo— y **nadie podía
resolverla**, porque el único camino que contesta una columna sale de `STORE_FOR_FRONT` y
este frente no está ahí (su regla vive en `PAIR_UNIT_FRONTS`, que sólo consultaban las
tarjetas). Y un `NOT_RUN` en una celda **arrastra el veredicto de la fila**: por eso los
once candidatos salían `INCOMPLETE` con la corrida dentro del proyecto.

### El panel de la corrida NO es el de hoy, y eso también se comprueba

La corrida guardada es la del panel de entonces. `3utr:359` entró el 2026-09-07 y **no
está en ella**, así que su celda tiene que decir `SIN_CONSULTAR` —«hay corridas de este
frente y ninguna miró a este candidato», que se arregla lanzando una corrida, no
consiguiendo un fichero— y NO `PASS` por contagio ni `NOT_RUN` por descuido.
"""

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tests.nombres_heredados import por_nombre_heredado, starts_del_medido  # noqa: E402

from shmir_design import presentation, spliceai  # noqa: E402
from shmir_design.anatomy import Anatomy, RegionSource  # noqa: E402
from shmir_design.filters import FilterState  # noqa: E402
from shmir_design.reference import (  # noqa: E402
    REFERENCES, fixture_available, load_reference, sequence_md5,
)
from shmir_design.scaffold import SGEP_SCAFFOLD  # noqa: E402

RATON = REFERENCES["NM_011170.3"]
CASETE = RAIZ / "data" / "reference" / "aav_casete.fa"
MEDIDO = RAIZ / "data" / "medido" / "spliceai_dos_intrones_2026-09-05.tsv"
HAY = fixture_available(RATON) and CASETE.exists() and MEDIDO.exists()
ESPECIE = "raton"
INTRONES = ("mvm_actual", "intron_quimerico")

#: Los valores que SON un estado de filtro. La fila lleva además texto —el sitio, la
#: diana— y meterlo en la agregación revienta con «`3utr:1018` no es un FilterState».
_VALORES = {e.value for e in FilterState}


def _casete() -> str:
    return "".join(
        l.strip() for l in CASETE.read_text("utf-8").splitlines()
        if not l.startswith(">")
    )


def _resultado(panel) -> str:
    """El fichero medido, con el md5 de la construcción de HOY.

    Las PUNTUACIONES no se tocan: salen tal cual de la corrida del 2026-09-05. Lo que se
    reescribe es la columna `md5`, porque aquella corrida se montó sobre un casete cuyo
    flanco 3' medía 112 nt menos y la construcción no se puede reconstruir bit a bit.
    Los nombres son los de entonces y se leen con `tests/nombres_heredados.py`.
    """
    por_nombre = por_nombre_heredado(panel.constructions)
    lineas = ["# convencion: spliceai"]
    with MEDIDO.open("r", encoding="utf-8") as f:
        lineas.append(next(f).rstrip("\n"))
        for fila in f:
            nombre, _md5, pos, tipo, pun = fila.rstrip("\n").split("\t")
            construccion = por_nombre.get(nombre)
            if construccion is not None:
                lineas.append(
                    "\t".join((nombre, construccion.md5, pos, tipo, pun))
                )
    return "\n".join(lineas) + "\n"


@unittest.skipUnless(HAY, "faltan la referencia murina, el casete o el medido")
class TestElCaminoENTERO(unittest.TestCase):
    """Del fichero de SpliceAI al veredicto del candidato, sin almacenes falsos."""

    @classmethod
    def setUpClass(cls):
        secuencia = load_reference(RATON)
        anatomia = Anatomy.from_cds(
            cds=RATON.cds, length=len(secuencia),
            source=RegionSource.FIXTURE_VERIFICADO,
        )
        cls.corrida = presentation.page_run(
            species=ESPECIE, sequence=secuencia, anatomy=anatomia,
        )
        cls.de_la_corrida = starts_del_medido(MEDIDO)
        panel = spliceai.build_panel(
            cls.corrida.selection, intron_names=INTRONES, scaffold=SGEP_SCAFFOLD,
            starts=cls.de_la_corrida, cassette=_casete(), context_nt=5000,
        )
        crudo = _resultado(panel)
        scan = spliceai.scan_from_result(crudo, constructions=panel.constructions)
        cls.pares = len(scan.pairs)

        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        payload, fuente = presentation.anatomy_payload(anatomia)
        almacen = presentation.project_create(
            base, slug="corrida-de-empalme", date="2026-09-05",
            sequence=secuencia, species=ESPECIE, anatomy=payload,
            anatomy_source=fuente,
        )
        presentation.save_splice_run(
            almacen,
            presentation.splice_run_from_scan(
                scan, raw=crudo, date="2026-09-05",
                ran_by="test", executor="fichero versionado",
            ),
        )
        # SE VUELVE A ABRIR: lo que se comprueba es lo que sobrevive al log, no lo que
        # quedó en memoria. Es el ciclo entero, como el de la persistencia.
        cls.almacenes = presentation.load_stores(
            presentation.project_open(
                base, "corrida-de-empalme",
                sequence=secuencia, expect_md5=sequence_md5(secuencia),
            )
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _fila(self, inicio):
        filas = presentation.site_table_rows(
            self.corrida.tiling, self.corrida.selection,
            species=ESPECIE, stores=self.almacenes,
        )
        return next(f for f in filas if f["inicio"] == inicio)

    def test_la_corrida_cubre_DIEZ_candidatos_por_DOS_intrones(self):
        """Veinte pares: la unidad es el par, así que se cuentan pares."""
        self.assertEqual(self.pares, len(self.de_la_corrida) * len(INTRONES))
        self.assertEqual(len(self.de_la_corrida), 10)

    def test_cada_candidato_de_la_corrida_queda_CONTESTADO(self):
        for inicio in self.de_la_corrida:
            with self.subTest(inicio):
                estado = self._fila(inicio)["empalme_sitios"]
                self.assertNotIn(estado, presentation.ESTADOS_SIN_RESPUESTA)

    def test_y_la_CELDA_deja_de_ser_una_laguna_para_el_veredicto(self):
        """El fallo real: la celda no la resolvía nadie y el veredicto la contaba.

        El veredicto sigue siendo `INCOMPLETE` —quedan `especificidad`,
        `offtarget_seed` y los demás sin fichero— y eso es correcto. Lo que este test
        exige es que `empalme_sitios` **ya no sea uno de los que lo impiden**: antes lo
        era siempre, con la corrida guardada delante.
        """
        for inicio in self.de_la_corrida:
            with self.subTest(inicio):
                fila = self._fila(inicio)
                lagunas = [
                    k for k, v in fila.items()
                    if isinstance(v, str) and v in presentation.ESTADOS_SIN_RESPUESTA
                ]
                self.assertNotIn("empalme_sitios", lagunas)
                self.assertTrue(
                    lagunas, "control adversario: sin lagunas este test no mide nada"
                )

    def test_el_frente_NO_se_cierra_porque_la_corrida_es_del_panel_VIEJO(self):
        """Nueve de los once, y los dos que faltan se NOMBRAN.

        `3utr:359` entró el 2026-09-07 y `3utr:1071` el 2026-09-06: los dos son
        posteriores a esta corrida. Un frente sólo se cierra si lo cubre TODO el panel —
        con nueve de once, «cerrado» daría por comprobados dos que nadie miró.
        """
        estados = presentation.panel_states_by_front(
            self.corrida.tiling, self.corrida.selection,
            species=ESPECIE, stores=self.almacenes,
        )["estados"]["empalme_sitios"]
        contestados = [
            i for i, e in estados.items()
            if e not in presentation.ESTADOS_SIN_RESPUESTA
        ]
        faltan = sorted(set(estados) - set(contestados))
        self.assertEqual(len(contestados), 9)
        self.assertEqual(
            [self.corrida.tiling.utr3_of(i) for i in faltan], [359, 1071]
        )

    def test_un_candidato_QUE_LA_CORRIDA_NO_MIRO_dice_SIN_CONSULTAR(self):
        """`3utr:359` entró en el panel DESPUÉS de esta corrida.

        Y eso no es `NOT_RUN` —hay corridas de este frente— ni `PASS` por contagio: se
        arregla lanzando una corrida que lo incluya, no consiguiendo un fichero.
        """
        fuera = [
            c.start for c in self.corrida.selection.selection.chosen
            if c.start not in self.de_la_corrida
        ]
        self.assertTrue(fuera, "el panel de hoy es el mismo que el de la corrida")
        for inicio in fuera:
            with self.subTest(inicio):
                self.assertEqual(
                    self._fila(inicio)["empalme_sitios"], presentation.SIN_CONSULTAR
                )

    def test_el_EXPORT_lo_dice_POR_INTRON_y_no_fundido(self):
        """La comparación entre arquitecturas es para lo que el frente existe."""
        from shmir_design import outputs, presentation

        cabecera = presentation.tsv_header(outputs.tsv_selected(
            self.corrida.selection, species=ESPECIE,
            tiling=self.corrida.tiling, stores=self.almacenes,
        ))
        for intron in INTRONES:
            self.assertIn(f"empalme_sitios:{intron}", cabecera)
        self.assertNotIn("empalme_sitios", cabecera)


if __name__ == "__main__":
    unittest.main()
