"""Qué frentes EXISTEN no es qué frentes están abiertos HOY.

Regla 5: escrito antes.

**Reportado el 2026-09-08**, al rechazar una corrida de off-targets ya guardada:

    pending_after_duplicate no conoce el frente 'offtarget_seed'.
    Los que hay son: empalme_intron, empalme_sitios, especificidad,
    fraccion_isoforma_larga, seed, seed_colision, transgen.

`offtarget_seed` existe: tiene almacén en `STORE_FOR_FRONT`, ficha de obtención, corridas
guardadas y dos columnas en el export. Lo que pasa es que **`blocking_fronts` no es la
lista de los frentes que existen: es la de los que están ABIERTOS en esta corrida**. Un
frente cuyo fichero ya está en el depósito deja de salir de ahí — y con él dejaba de
existir para todo lo que preguntara por su NOMBRE.

Es el principio nº 19 otra vez, y encima con el comentario delante: el código que valida
decía, escrito, *«la pregunta era por el NOMBRE y la comprobación miraba el CONTENIDO»*
— y validaba contra `blocking_fronts`, que es contenido. Saber la regla no basta si no se
aplica al eje que toca.

### La reproducción usa un fichero de verdad

No hace falta el transcriptoma para verlo: con la **máscara murina** puesta,
`repeticiones` y `repeticion_polimorfica` dejan de estar en `blocking_fronts` por el
mismo motivo —su fichero está—, así que el aborto se dispara sobre dos frentes que
existen desde el primer día.
"""

import unittest
from pathlib import Path

from shmir_design import masking, presentation
from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.errors import ShmirDesignError
from shmir_design.informe_doc import declared_fronts
from shmir_design.reference import REFERENCES, fixture_available, load_3utr, load_reference
from shmir_design.selection import (
    SelectionConfig,
    blocking_fronts,
    default_config,
    select_from_report,
)
from shmir_design.tiling import tile_utr

RATON = REFERENCES["NM_011170.3"]
RAIZ = Path(__file__).resolve().parent.parent / "data" / "reference"
HAY = fixture_available(RATON)
HAY_MASCARA = (RAIZ / "rmsk_mouse.out").is_file() and (RAIZ / "rmsk_mouse.tbl").is_file()


def _corrida(*, mask=None):
    secuencia = load_reference(RATON)
    anatomia = Anatomy.from_cds(
        cds=RATON.cds, length=len(secuencia), source=RegionSource.FIXTURE_VERIFICADO,
    )
    informe = tile_utr(secuencia, anatomy=anatomia, mask=mask)
    return informe, select_from_report(informe, default_config())


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLaListaDeclaradaEstaCOMPLETA(unittest.TestCase):

    def test_offtarget_seed_esta_DECLARADO(self):
        """El caso reportado, por su nombre."""
        self.assertIn("offtarget_seed", declared_fronts())

    def test_todo_frente_que_el_nucleo_puede_EMITIR_esta_declarado(self):
        """En las configuraciones que dan listas DISTINTAS, no en una sola.

        `fraccion_isoforma_larga` sólo sale con tabla de APA medido y
        `repeticiones`/`repeticion_polimorfica` sólo sin máscara: con una sola corrida la
        lista sale corta y un frente se cuela sin declarar. Es la misma razón por la que
        `tests/test_fichas_obtencion.py` mira dos.
        """
        emitidos = set()
        configuraciones = [None] + ([_mascara()] if HAY_MASCARA else [])
        for mask in configuraciones:
            informe, seleccion = _corrida(mask=mask)
            emitidos |= {f.name for f in blocking_fronts(informe, seleccion)}
        utr3 = load_3utr(RATON)
        informe = tile_utr(utr3)
        seleccion = select_from_report(informe, SelectionConfig(n_candidates=10))
        emitidos |= {f.name for f in blocking_fronts(informe, seleccion)}
        self.assertEqual(sorted(emitidos - declared_fronts()), [])

    def test_y_ningun_declarado_es_HUERFANO(self):
        """En las dos direcciones: un nombre declarado que nadie emite es un fantasma."""
        informe, seleccion = _corrida()
        emitidos = {f.name for f in blocking_fronts(informe, seleccion)}
        self.assertEqual(sorted(declared_fronts() - emitidos), [])


@unittest.skipUnless(HAY and HAY_MASCARA, "faltan el fixture murino o su máscara")
class TestElCasoREPRODUCIDO(unittest.TestCase):
    """Con la máscara puesta, dos frentes que EXISTEN salen de `blocking_fronts`."""

    @classmethod
    def setUpClass(cls):
        cls.informe, cls.seleccion = _corrida(mask=_mascara())
        cls.abiertos = {f.name for f in blocking_fronts(cls.informe, cls.seleccion)}

    def test_el_caso_existe_dos_frentes_dejan_de_estar_ABIERTOS(self):
        """Control adversario: sin esto, el test de abajo no probaría nada."""
        self.assertEqual(
            sorted(declared_fronts() - self.abiertos),
            ["repeticion_polimorfica", "repeticiones"],
        )

    def test_y_pending_after_duplicate_NO_aborta_por_ellos(self):
        for frente in sorted(declared_fronts() - self.abiertos):
            with self.subTest(frente):
                # Sin almacenes se calla, que es lo correcto; lo que NO puede es abortar.
                resultado = presentation.pending_after_duplicate(
                    self.informe, self.seleccion, species="raton", front=frente,
                )
                self.assertIs(resultado["activo"], False)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestElGuardiaSIGUEMordiendo(unittest.TestCase):
    """El arreglo no puede ser dejar de comprobar el nombre."""

    def test_un_frente_INVENTADO_sigue_abortando(self):
        informe, seleccion = _corrida()
        with self.assertRaises(ShmirDesignError) as caja:
            presentation.pending_after_duplicate(
                informe, seleccion, species="raton", front="frente_que_no_existe",
            )
        mensaje = str(caja.exception)
        self.assertIn("frente_que_no_existe", mensaje)
        # Y el mensaje NOMBRA los que hay, para que un error de tecleo se vea de una vez.
        self.assertIn("offtarget_seed", mensaje)


def _mascara():
    return masking.load_rmsk(
        RAIZ / "rmsk_mouse.out", version="test",
        expected_species=RATON.organism, summary_path=RAIZ / "rmsk_mouse.tbl",
    )


if __name__ == "__main__":
    unittest.main()


#: TODA tabla del proyecto que se indexe POR FRENTE. Es la lista que el reporte pedía
#: —*«la misma familia que `NO_CABE_COLUMNA_POR_CANDIDATO` y `STORE_FOR_FRONT`: una lista
#: que declara los frentes no está completa, y el que falta es invisible para todo lo que
#: la consulta»*— y por eso el mecanismo no es arreglar una: es cruzarlas TODAS contra el
#: registro.
#:
#: Las de aquí son SUBCONJUNTOS legítimos —no todo frente tiene almacén, ni umbral, ni
#: criterio relativo—, así que lo que se exige no es que estén completas sino que **no
#: nombren nada que no exista**: un frente mal escrito en cualquiera de ellas es
#: invisible exactamente igual que uno que falta, y no da ningún error.
#:
#: Añadir una tabla nueva indexada por frente y NO ponerla aquí deja el hueco abierto. Es
#: el mismo trato que `store.RECORD_KINDS`.
def _tablas_por_frente():
    from shmir_design import informe_doc, presentation

    return {
        "presentation.STORE_FOR_FRONT": set(presentation.STORE_FOR_FRONT),
        "presentation.NO_CABE_COLUMNA_POR_CANDIDATO": set(
            presentation.NO_CABE_COLUMNA_POR_CANDIDATO
        ),
        "presentation.PAIR_UNIT_FRONTS": set(presentation.PAIR_UNIT_FRONTS),
        "informe_doc.BENCH_FRONTS": set(informe_doc.BENCH_FRONTS),
        "informe_doc.UPLOADED_FRONTS": set(informe_doc.UPLOADED_FRONTS),
        "informe_doc._FRONT_SOURCE_ATTR": set(informe_doc._FRONT_SOURCE_ATTR),
        "informe_doc._FRONT_THRESHOLDS": set(informe_doc._FRONT_THRESHOLDS),
        "informe_doc.RELATIVE_CRITERION": set(informe_doc.RELATIVE_CRITERION),
    }


class TestNingunaTablaPorFrenteNOMBRAunFantasma(unittest.TestCase):
    """El mecanismo: se cruzan TODAS, no se arregla una.

    Un nombre mal escrito en una tabla indexada por frente **no da ningún error**: la
    entrada simplemente no se encuentra nunca, y el frente que debía cubrir se comporta
    como si no estuviera declarado. Es el mismo silencio del reporte, un nivel más abajo.
    """

    def test_ninguna_tabla_nombra_un_frente_que_no_existe(self):
        declarados = declared_fronts()
        for nombre, tabla in _tablas_por_frente().items():
            with self.subTest(nombre):
                self.assertEqual(sorted(tabla - declarados), [], nombre)

    def test_el_detector_MIRA_de_verdad(self):
        """Control adversario: si las tablas salieran vacías, todo pasaría solo."""
        tablas = _tablas_por_frente()
        self.assertGreaterEqual(len(tablas), 8)
        self.assertTrue(all(tablas.values()), "alguna tabla salió vacía")

    def test_y_TODO_frente_declarado_tiene_ficha_de_obtencion(self):
        """Un `NOT_RUN` que no dice cómo se resuelve manda a preguntar FUERA de la app."""
        from shmir_design.obtencion import load_all

        self.assertEqual(sorted(declared_fronts() - set(load_all())), [])
