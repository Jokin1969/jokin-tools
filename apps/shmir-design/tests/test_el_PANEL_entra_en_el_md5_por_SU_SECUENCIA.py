"""El `result_md5` de una corrida de seed distingue paneles por SU SECUENCIA.

**Reportado (2026-09-11, persistente).** Con el panel HUMANO activo, `seed_colision`
contra `mmu-` se rechazaba al guardar por `result_md5` repetido: el mismo md5 que la
corrida `mmu-` del panel MURINO, hecha dias antes. Son candidatos DISTINTOS sobre
secuencias distintas (PRNP humano vs PRNP murino), pero PRNP esta tan conservado que los
heptameros de seed —y por tanto el mapa seed->colision— salen iguales en los dos.

El crudo del que sale el `result_md5` ya llevaba el organismo del eje (errata nº 48) y la
posicion y el slug de cada consulta (errata nº 42). Eso distingue dos paneles cuando sus
posiciones o su especie difieren —lo fija `test_el_BLOQUEO_dice_de_QUE_PANEL_es`—, pero
deja un flanco: dos paneles que coincidieran POSICION A POSICION, con seeds conservadas,
tenian crudos identicos porque el crudo NO llevaba la SECUENCIA del candidato. Dos
secuencias distintas en la misma posicion daban el mismo md5.

Este fichero fija que la SECUENCIA consultada entra en el md5. La huella del conjunto
consultado va en el crudo —de donde sale la huella— y NO en el bloque exportable, que es
lo que descarga la pagina: el fichero descargable no cambia (regla del reporte).

Regla 5: escrito antes. Python 3.11+, solo biblioteca estandar (regla 6).
"""

import unittest

from shmir_design.identidad import result_fingerprint
from shmir_design.seed_scan import DEFAULTS, run_scan


class _MaduroFalso:
    """La superficie minima de una tabla de maduros para `run_scan`."""

    provenance = "fixture de test"
    checksum = "0" * 32
    version = "test"

    def __init__(self, seeds):
        self.seeds = dict(seeds)


class _Eleccion:
    def __init__(self, start):
        self.start = start


class _Ventana:
    def __init__(self, guia):
        class _Ev:
            pass

        self.evaluation = _Ev()
        self.evaluation.guide = guia


class _SeleccionFalsa:
    """Un panel: cada posicion trae SU secuencia guia. `anatomy` no hace falta aqui."""

    anatomy = None

    def __init__(self, guia_por_inicio):
        self._guia = dict(guia_por_inicio)

    def choices_for(self, starts):
        return [_Eleccion(s) for s in starts]

    def window_of(self, choice):
        return _Ventana(self._guia[choice.start])


#: Dos guias de 22 nt (el largo de brazo del andamio miR-E) que COMPARTEN la seed 2-8
#: pero difieren en el resto: es el peor caso del reporte —seed conservada, secuencia
#: distinta— en su forma minima.
GUIA_A = "TACGACGTACGTACGTACGTAC"
GUIA_B = "TACGACGTAAAAAAAAAAAAAA"


def _corre(species, guia_por_inicio, *, organism="mouse", passengers=False):
    inicios = tuple(guia_por_inicio)
    seed = DEFAULTS.seed_of(GUIA_A)
    maduros = _MaduroFalso({seed: ["mmu-miR-216b-5p"]})
    seleccion = _SeleccionFalsa(guia_por_inicio)
    return run_scan(
        seleccion, mature=maduros, params=DEFAULTS, species=species,
        starts=inicios, guides=True, passengers=passengers, organism=organism,
    )


class TestLaSecuenciaEntraEnElMd5(unittest.TestCase):
    def setUp(self):
        # La seed de las dos guias es la misma: si no lo fuera, el test probaria otra cosa.
        self.assertEqual(DEFAULTS.seed_of(GUIA_A), DEFAULTS.seed_of(GUIA_B))

    def test_el_caso_reportado_HUMANO_vs_MURINO_da_md5_DISTINTO(self):
        """Posiciones distintas y seeds conservadas: no es «el mismo fichero»."""
        humano = _corre("human", {825: GUIA_A, 939: GUIA_A, 1019: GUIA_A})
        raton = _corre("mouse", {60: GUIA_B, 143: GUIA_B, 200: GUIA_B})
        self.assertNotEqual(
            result_fingerprint(humano.raw), result_fingerprint(raton.raw)
        )

    def test_NI_SIQUIERA_con_el_MISMO_slug_y_las_MISMAS_POSICIONES(self):
        """El flanco que faltaba: mismo eje, mismo slug, mismas posiciones, seed igual.

        Lo unico que difiere es la SECUENCIA. Sin ella dentro del crudo, estos DOS
        paneles colisionaban —era la mitad no cubierta del reporte—.
        """
        mismas = (825, 939, 1019)
        uno = _corre("human", {p: GUIA_A for p in mismas})
        otro = _corre("human", {p: GUIA_B for p in mismas})
        self.assertNotEqual(
            result_fingerprint(uno.raw), result_fingerprint(otro.raw)
        )

    def test_el_MISMO_panel_da_el_MISMO_md5(self):
        """El dedupe legitimo sigue: repetir la MISMA corrida es «el mismo fichero»."""
        mismas = {825: GUIA_A, 939: GUIA_A}
        uno = _corre("human", dict(mismas))
        otro = _corre("human", dict(mismas))
        self.assertEqual(
            result_fingerprint(uno.raw), result_fingerprint(otro.raw)
        )

    def test_la_huella_del_panel_NO_llega_al_fichero_DESCARGABLE(self):
        """La identidad del panel va en el crudo (la huella), no en `export_block`.

        `export_block` es lo que descarga la pagina; el reporte pedia no cambiarlo.
        """
        scan = _corre("human", {825: GUIA_A}, passengers=True)
        self.assertIn("# panel", scan.raw)
        self.assertNotIn("# panel", scan.export_block())


class TestElControlAdversario(unittest.TestCase):
    """Sin la linea del panel, el caso extremo SI colisiona: es lo que la compra.

    Sin este control, «no colisionan» y «el test no compara nada» dan el mismo verde.
    """

    def test_quitando_la_linea_del_panel_los_dos_crudos_COINCIDEN(self):
        mismas = (825, 939, 1019)
        uno = _corre("human", {p: GUIA_A for p in mismas}).raw
        otro = _corre("human", {p: GUIA_B for p in mismas}).raw

        def sin_panel(crudo):
            return "\n".join(
                linea for linea in crudo.splitlines()
                if not linea.startswith("# panel")
            )

        self.assertEqual(sin_panel(uno), sin_panel(otro))


if __name__ == "__main__":
    unittest.main()
