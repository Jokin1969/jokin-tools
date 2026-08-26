"""La convergencia con la fuente externa es un HALLAZGO, no un parametro.

Regla 5: escritos antes.

Dos metodos independientes, con criterios distintos, sobre el mismo 3'UTR verificado:
nuestra cascada de filtros duros y miRarchitect. Resultado: CERO sitios exclusivos de la
fuente externa contra los 90 sitios elegibles, con coincidencias exactas (3utr:735, base
a base) y a 1 nt (3utr:1017↔1018, 3utr:552↔553, 3utr:1075↔1076).

Lectura, y va escrita en el informe: el espacio de ventanas viables esta SATURADO bajo
los filtros duros. La convergencia externa no discrimina entre candidatos y NO puede
usarse para elegir. Es un dato de calibracion de nuestra propia cascada — para el
suplementario, no para el ranking.

La referencia es fija y esta decidida: los 90 sitios elegibles.
"""

import unittest
from pathlib import Path

from shmir_design.coords import Frame
from shmir_design.spacing import ReferenceSet, compare_sites, convergence

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"
EXPORT = DIR / "mirarchitect_prnp_export_buena.csv"


def _piezas():
    from shmir_design.fetch import parse_fasta_payload
    from shmir_design.mirarchitect import parse_export
    from shmir_design.polya import normalize_sequence
    from shmir_design.selection import SelectionConfig, is_eligible, select_from_report
    from shmir_design.tiling import tile_utr

    _, bruta = parse_fasta_payload(RATON.read_text(encoding="utf-8"), source="fa")
    utr3 = normalize_sequence(bruta, name="NM_011170.3")[949:]
    tiling = tile_utr(utr3)
    seleccion = select_from_report(tiling, SelectionConfig(n_candidates=6))
    export = parse_export(EXPORT.read_text(encoding="utf-8"), source="buena")
    tabla = str.maketrans("ACGT", "TGCA")
    externos = {}
    for fila in export.rows:
        diana = fila.guide.translate(tabla)[::-1]
        indice = utr3.find(diana)
        if indice != -1:
            externos[indice + 1] = fila.guide
    sitios = {
        s.best.start: seleccion.windows[s.best.label].evaluation.guide
        for s in seleccion.selection.sites
    }
    elegibles = {w.window.start for w in tiling.windows if is_eligible(w)}
    return utr3, externos, sitios, elegibles


@unittest.skipUnless(
    RATON.is_file() and EXPORT.is_file(),
    "NOT_RUN: faltan los fixtures de la corrida murina",
)
class TestElHallazgoDeSaturacion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.externos, cls.sitios, cls.elegibles = _piezas()
        comparacion = compare_sites(
            candidates=cls.externos,
            reference=ReferenceSet(
                label="los 90 sitios elegibles",
                starts=cls.sitios,
                frame=Frame.UTR3,
            ),
        )
        cls.hallazgo = convergence(
            comparacion,
            eligible=cls.elegibles,
            method_a="nuestra cascada de filtros duros",
            method_b="miRarchitect (andamio miR-30a)",
        )

    def test_cuatro_coincidencias_EXACTAS(self):
        self.assertEqual(self.hallazgo.exact, (221, 735, 810, 1018))

    def test_735_es_la_misma_ventana_base_a_base(self):
        self.assertEqual(self.utr3[734:756], self.hallazgo.window_of(735, self.utr3))

    def test_seis_coincidencias_a_1_nt(self):
        self.assertEqual(
            self.hallazgo.within_1nt,
            ((337, 338), (516, 517), (552, 553), (1017, 1018), (1024, 1025), (1075, 1076)),
        )

    def test_el_unico_exclusivo_es_1200(self):
        self.assertEqual(self.hallazgo.exclusive, (1200,))

    def test_y_no_es_UTILIZABLE_porque_no_pasa_nuestros_filtros(self):
        # Cero sitios exclusivos UTILIZABLES: es la cifra del hallazgo.
        self.assertEqual(self.hallazgo.exclusive_usable, ())

    def test_la_cifra_del_hallazgo_es_CERO(self):
        self.assertEqual(len(self.hallazgo.exclusive_usable), 0)


@unittest.skipUnless(
    RATON.is_file() and EXPORT.is_file(),
    "NOT_RUN: faltan los fixtures de la corrida murina",
)
class TestComoSeDeclaraEnElInforme(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        utr3, externos, sitios, elegibles = _piezas()
        comparacion = compare_sites(
            candidates=externos,
            reference=ReferenceSet(
                label="los 90 sitios elegibles", starts=sitios, frame=Frame.UTR3
            ),
        )
        cls.texto = "\n".join(
            convergence(
                comparacion,
                eligible=elegibles,
                method_a="nuestra cascada de filtros duros",
                method_b="miRarchitect (andamio miR-30a)",
            ).describe()
        )

    def test_lo_declara_como_HALLAZGO(self):
        self.assertIn("HALLAZGO", self.texto)

    def test_nombra_los_dos_metodos(self):
        self.assertIn("nuestra cascada de filtros duros", self.texto)
        self.assertIn("miRarchitect", self.texto)

    def test_da_las_cifras(self):
        self.assertIn("24", self.texto)   # candidatos externos mapeados
        self.assertIn("90", self.texto)   # sitios de la referencia
        self.assertIn("0 sitios exclusivos", self.texto)

    def test_dice_saturado(self):
        self.assertIn("saturado", self.texto.lower())

    def test_dice_que_NO_puede_usarse_para_elegir(self):
        bajo = self.texto.lower()
        self.assertIn("no discrimina", bajo)
        self.assertIn("no puede usarse para elegir", bajo)

    def test_lo_manda_al_suplementario_como_calibracion(self):
        bajo = self.texto.lower()
        self.assertIn("calibracion", bajo)
        self.assertIn("suplementario", bajo)

    def test_las_posiciones_van_etiquetadas(self):
        self.assertIn("3utr:735", self.texto)
        self.assertIn("3utr:1017", self.texto)

    def test_no_llama_validacion_a_esto(self):
        # Que dos metodos coincidan donde solo cabe coincidir no valida nada: si el
        # espacio esta saturado, la coincidencia es forzosa.
        self.assertIn("no es una validacion", self.texto.lower())
