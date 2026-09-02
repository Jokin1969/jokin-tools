"""La carga de seed se cuenta DONDE SE LEE, no en las 407 ventanas elegibles.

**Reportado el 2026-09-02**: «un retraso enorme en el proceso», justo despues de que el
transcriptoma por fin entrara. MEDIDO antes de tocar nada, que es lo que separa esto de
una optimizacion a ojo:

  · barrido puro                          226 M nt/s
  · una ventana contra 84 MB              0,4-0,7 s
  · x 407 ventanas que pasan los biofisicos   3-4 MINUTOS
  · y eso EN CADA rerun de la pagina: cada tecla, cada boton, cada subida.

Sin el transcriptoma la corrida entera tarda 0,33 s. O sea: no es el servidor, es un
trabajo que crece con el tamaño del fichero y se repetia por ventana.

POR QUE SE PUEDE ACOTAR, y no es una excusa: `carga_seed` **no alimenta ninguna
seleccion ni ningun veredicto** —lo dice `selection.py` en su propio comentario, «es un
numero comparativo y por eso nunca estuvo en `not_run_filters`»—. Es una COLUMNA.

Y EL PRECEDENTE ESTA EN LA MISMA FUNCION, tres lineas mas arriba: la colision de seed ya
se acota «por coste» a las ventanas que superan los biofisicos, con su NOT_RUN y su
motivo escrito. Esto es el mismo escalon una vez mas.

LO QUE NO SE RELAJA: un `NOT_RUN` con su motivo, nunca un cero ni una celda vacia que se
lea como cero. Y donde SI se cuenta, el numero es EL MISMO — es la misma funcion con las
mismas entradas.
"""

import unittest
from pathlib import Path

from shmir_design.filters import FilterState
from shmir_design.seed_load import Utr3Set
from shmir_design.tiling import tile_utr

#: Sustrato REAL: el transcrito murino del repositorio, troceado en registros. No hace
#: falta que sea grande — lo que se comprueba aqui es CUANTAS ventanas lo barren, no
#: cuanto tarda; el tiempo esta medido arriba y no se mete en un test, que dependeria de
#: la maquina y fallaria sin que nadie haya tocado nada (leccion del golden con tiempos).
_FA = Path(__file__).resolve().parent.parent / "data" / "reference" / "NM_011170.3.fa"
HAY = _FA.is_file()
if HAY:
    _TX = "".join(
        l.strip() for l in _FA.read_text(encoding="utf-8").splitlines()
        if not l.startswith(">")
    ).upper()
    # El 3'UTR, no el transcrito entero: sin anatomia, `tile_utr` trata lo que se le da
    # COMO 3'UTR, y el invariante de rango de `coords` aborta —correctamente— con una
    # posicion de 2191 etiquetada `3utr:`. El 3'UTR murino empieza en 950.
    SECUENCIA = _TX[949:]
    UTRS = Utr3Set(
        records=tuple(
            (f"NM_trozo_{i}", SECUENCIA[i * 300 : (i + 1) * 300])
            for i in range(len(SECUENCIA) // 300)
        ),
        source="el transcrito del repositorio, troceado",
        version="banco",
        checksum="0" * 32,
    )
else:  # pragma: no cover - el fixture esta en el repositorio
    SECUENCIA, UTRS = "", None


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestSoloSeCuentaDondeSeLEE(unittest.TestCase):

    def test_sin_acotar_lo_cuenta_en_TODAS_las_elegibles(self):
        # El comportamiento de antes, que es el que sigue teniendo el CLI: una corrida
        # por lotes puede permitirselo, una pagina interactiva no.
        informe = tile_utr(SECUENCIA, utr3_set=UTRS)
        con_numero = [w for w in informe.windows if _tiene_numero(w)]
        self.assertGreater(len(con_numero), 10)

    def test_acotado_a_unos_INICIOS_solo_los_cuenta_ahi(self):
        objetivo = frozenset(w.window.start for w in _elegibles(SECUENCIA)[:3])
        informe = tile_utr(SECUENCIA, utr3_set=UTRS, seed_load_starts=objetivo)
        con_numero = {w.window.start for w in informe.windows if _tiene_numero(w)}
        self.assertEqual(con_numero, set(objetivo))

    def test_y_el_NUMERO_es_EL_MISMO_donde_se_cuenta(self):
        # Lo que no puede cambiar: acotar decide DONDE se cuenta, no CUANTO sale.
        objetivo = frozenset(w.window.start for w in _elegibles(SECUENCIA)[:3])
        todo = {w.window.start: w.carga_seed for w in tile_utr(
            SECUENCIA, utr3_set=UTRS).windows}
        acotado = {w.window.start: w.carga_seed for w in tile_utr(
            SECUENCIA, utr3_set=UTRS, seed_load_starts=objetivo).windows}
        for inicio in objetivo:
            self.assertEqual(todo[inicio].counts, acotado[inicio].counts)
            self.assertEqual(todo[inicio].total, acotado[inicio].total)


@unittest.skipUnless(HAY, "falta data/reference/NM_011170.3.fa")
class TestLoQueSaleDondeNoSeCUENTA(unittest.TestCase):
    """Ni un cero ni una celda vacia: `NOT_RUN` con el motivo."""

    def setUp(self):
        objetivo = frozenset(w.window.start for w in _elegibles(SECUENCIA)[:1])
        self.informe = tile_utr(
            SECUENCIA, utr3_set=UTRS, seed_load_starts=objetivo
        )
        self.fuera = [
            w for w in self.informe.windows
            if w.carga_seed is not None and w.window.start not in objetivo
        ]

    def test_las_demas_salen_NOT_RUN(self):
        self.assertTrue(self.fuera)
        for w in self.fuera:
            with self.subTest(w.window.start):
                self.assertIs(w.carga_seed.state, FilterState.NOT_RUN)

    def test_y_el_motivo_dice_POR_COSTE_y_donde_SI_se_cuenta(self):
        motivo = self.fuera[0].carga_seed.reason
        self.assertIn("coste", motivo.lower())
        self.assertIn("panel", motivo.lower())

    def test_su_columna_va_VACIA_y_no_a_cero(self):
        # Regla de siempre: no haber contado y contar cero son cosas distintas.
        self.assertEqual(self.fuera[0].carga_seed.as_column(), "")


def _tiene_numero(w) -> bool:
    return w.carga_seed is not None and w.carga_seed.total is not None


def _elegibles(secuencia):
    """Las ventanas que el propio tilado considera escaneables, PEDIDAS a el.

    Se reconocen porque son las que reciben la colision de seed cuando hay `mature`; sin
    fichero, las que superan los biofisicos. Se deriva del informe en vez de recalcular
    el criterio aqui, que seria escribir dos veces la misma regla.
    """
    from shmir_design.filters import biophysical_ok

    return [
        w for w in tile_utr(secuencia).windows
        if w.evaluation.asymmetry is not None
        and biophysical_ok(list(w.evaluation.filters) + [w.zona_prohibida])
    ]


if __name__ == "__main__":
    unittest.main()
