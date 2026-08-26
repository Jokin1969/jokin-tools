"""El APA sube a FRENTE BLOQUEANTE. DECIDIDO (2026-08-26).

Regla 5: escritos antes.

La cuenta que lo decide: los sitios inmunes por tramo son 20/0/0 —todos en el tercio
proximal— y el espaciado deja meter cuatro. Con un panel de diez, eso significa que
SEIS DE LOS DIEZ candidatos comparten un unico modo de fallo, y el rebalanceo tiene tope
en cuatro plazas.

La consecuencia, que va escrita con esas palabras: si la fraccion de isoforma corta es
alta, seis de diez candidatos entran al cribado con un TECHO INDISTINGUIBLE DE UN shmiR
MALO. Un candidato con techo 0,3 y uno que simplemente no funciona dan la misma lectura
en la placa.

Por eso `fraccion_isoforma_larga` deja de ser «importante» y pasa a ser el CUARTO frente
bloqueante, junto a especificidad, repetitivos y seed a nivel FAIL. Y lo publicado va
antes que el banco, con la palabra confirmacion.
"""

import unittest
from pathlib import Path

from shmir_design.polya import Tercio
from shmir_design.selection import SelectionConfig, blocking_fronts, select_from_report

DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
RATON = DIR / "NM_011170.3.fa"


def _piezas(candidatos=10):
    from shmir_design.reference import REFERENCES, load_3utr
    from shmir_design.tiling import tile_utr

    tiling = tile_utr(load_3utr(REFERENCES["NM_011170.3"]))
    seleccion = select_from_report(
        tiling,
        SelectionConfig(
            n_candidates=candidatos,
            apa_immune_quota=4,
            apa_immune_before=303,
            tercio_quota=(
                (Tercio.PROXIMAL, 4), (Tercio.MEDIO, 3), (Tercio.DISTAL, 2),
            ),
        ),
    )
    return tiling, seleccion


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestElAPAEsUnFrenteBloqueante(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiling, cls.seleccion = _piezas()
        cls.frentes = blocking_fronts(cls.tiling, cls.seleccion)

    def test_el_APA_se_SUMA_a_los_filtros_en_NOT_RUN(self):
        # Cuantos frentes de recurso haya depende de que ficheros se hayan cargado; lo
        # que fija este test es que el APA es UNO MAS, no uno de ellos. El empalme del
        # intron es otro que tampoco sale de ningun filtro de ventana.
        self.assertEqual(
            len(self.frentes), len(self.seleccion.not_run_filters) + 2
        )

    def test_y_uno_de_ellos_es_el_APA(self):
        self.assertIn("fraccion_isoforma_larga", [f.name for f in self.frentes])

    def test_los_demas_son_los_filtros_en_NOT_RUN(self):
        de_recurso = {f.name for f in self.frentes} - {
            "fraccion_isoforma_larga", "empalme_intron"
        }
        self.assertEqual(de_recurso, set(self.seleccion.not_run_filters))

    def test_con_los_tres_ficheros_cargados_quedarian_CINCO(self):
        # especificidad, repeticiones, seed_colision, el APA y el empalme del intron.
        # Los otros dos frentes de esta corrida (seed y transgen) se cierran con
        # mature.fa y el casete, que no se versionan; por eso la cuenta se comprueba asi
        # y no con un numero clavado. El empalme NO se cierra con ningun fichero: sus
        # tres lecturas son de banco.
        aparte = {"fraccion_isoforma_larga", "empalme_intron"}
        de_recurso = {f.name for f in self.frentes} - aparte
        pendientes = de_recurso - {"seed", "transgen"}
        self.assertEqual(
            sorted(pendientes | aparte),
            [
                "empalme_intron", "especificidad", "fraccion_isoforma_larga",
                # Dos ejes distintos con el mismo fichero detras: `repeticiones` mira la
                # estabilidad del genoma AAV, `repeticion_polimorfica` la viabilidad
                # clinica. Cuentan como dos frentes porque son dos preguntas.
                "repeticion_polimorfica", "repeticiones", "seed_colision",
            ],
        )

    def test_el_frente_del_APA_trae_la_cuenta_que_lo_justifica(self):
        apa = [f for f in self.frentes if f.name == "fraccion_isoforma_larga"][0]
        self.assertIn("6 de 10", apa.reason)
        self.assertIn("20/0/0", apa.reason)
        self.assertIn("cuatro", apa.reason.lower())

    def test_y_la_frase_que_explica_POR_QUE_bloquea(self):
        apa = [f for f in self.frentes if f.name == "fraccion_isoforma_larga"][0]
        self.assertIn("INDISTINGUIBLE DE UN shmiR MALO", apa.reason)

    def test_cita_la_medida_de_PolyA_DB_y_por_que_no_basta_EN_ESTA_corrida(self):
        # ACTUALIZADO 2026-08-26: ya hay medida (PolyA_DB v4.1). El frente sigue
        # bloqueando porque la conversion genomico↔transcrito no esta comprobada, y un
        # numero que depende de una conversion sin comprobar no es un techo medido.
        apa = [f for f in self.frentes if f.name == "fraccion_isoforma_larga"][0]
        self.assertIn("PolyA_DB", apa.reason)
        self.assertIn("0.86", apa.reason)
        # Esta corrida se hace SIN pasar la tabla medida, asi que el techo sigue
        # indeterminado aqui. Que la tabla exista no la aplica: se aplica por md5.
        self.assertIn("NO ENTRA EN ESTA CORRIDA", apa.reason)
        self.assertIn("md5", apa.reason)
        self.assertTrue(apa.blocking)

    def test_sin_candidatos_con_techo_el_frente_NO_existe(self):
        # Si todos fueran inmunes, la fraccion no bloquearia nada. El frente sale del
        # dato, no de una lista fija.
        from shmir_design.reference import REFERENCES, load_3utr
        from shmir_design.tiling import tile_utr

        tiling = tile_utr(load_3utr(REFERENCES["NM_011170.3"]))
        solo_inmunes = select_from_report(
            tiling,
            SelectionConfig(
                n_candidates=4, apa_immune_quota=4, apa_immune_before=303,
                require_one_per_tercio=False,
            ),
        )
        nombres = [f.name for f in blocking_fronts(tiling, solo_inmunes)]
        self.assertNotIn("fraccion_isoforma_larga", nombres)


@unittest.skipUnless(RATON.is_file(), "NOT_RUN: falta data/reference/NM_011170.3.fa")
class TestLoQueDiceElInforme(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from shmir_design.outputs import text_report
        from shmir_design.scaffold import SGEP_SCAFFOLD

        tiling, seleccion = _piezas()
        cls.texto = text_report(
            species="raton", tiling=tiling, selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
        )

    def test_el_informe_cuenta_los_frentes_e_incluye_el_APA(self):
        self.assertIn("PROVISIONAL EN 8 FRENTE(S)", self.texto)
        self.assertIn("fraccion_isoforma_larga:", self.texto)

    def test_y_el_APA_esta_entre_ellos_con_su_cifra(self):
        self.assertIn("fraccion_isoforma_larga", self.texto)
        self.assertIn("6 de 10", self.texto)

    def test_no_se_pide_oligo_hasta_que_TODOS_tengan_veredicto(self):
        self.assertIn("NO SE PIDE OLIGO", self.texto)
        self.assertIn("tengan veredicto", self.texto)
