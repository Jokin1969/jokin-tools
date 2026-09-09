"""El humano SALE del modo asumido el 2026-09-09, y la app tiene que decirlo.

Regla 5: escrito antes.

Este fichero se llamaba `test_humano_en_modo_asumido.py` y fijaba el estado contrario:
que las dos `ATTAAA` humanas (`3utr:955` y `3utr:1167`) estaban clasificadas por
canonicidad y **sin un solo dato de uso**, porque la única tabla del depósito era la
murina y se aplica **por md5 del 3'UTR**.

**Llegó el dato** (`polya_db_human.tsv`, PolyA_DB v4.1, hg38, PRNP, Gene ID 5621) y esa
premisa caducó. El test se mueve con la decisión en vez de bloquearla — principio nº 56:
un test que fija una decisión se mueve cuando la decisión se mueve.

Lo que cambia, medido: las dos `ATTAAA` pasan de ASUMIDAS a **CONFIRMADAS por medida**, y
aparece una tercera señal que la predicción no daba — el `AGTAAA` de `3utr:233`, clase
`Other` para PolyA_DB, **PROMOVIDA por uso medido**. Es el caso inverso exacto del
`AATATA` murino de `3utr:236`, y el que demuestra que el modo sin medida era la hipótesis
menos conservadora también aquí.

**LO QUE NO CAMBIA, y es la mitad que hay que seguir protegiendo**: la tabla murina sigue
sin aplicarse al humano. Que ahora haya una humana no lo demuestra — lo demuestra
ponerle la murina SOLA delante, que es lo que hace `TestLaMURINAsigueSINaplicarse`. Sin
ese control, «no se aplica la ajena» y «se aplica la propia» dan el mismo verde.

Y sigue faltando `apa_medido_human.tsv`, que es OTRO rol: la medida ya convertida a
coordenadas de 3'UTR, cuyo caso es un 3'-end seq de cerebro. El frente lo cierran los
DOS, y hoy lo cierra el primero.
"""

import unittest

from shmir_design.polya import SignalClass
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.species import required_files, resolve
from shmir_design.tiling import tile_utr

HUMANO = REFERENCES["NM_000311.5"]
HAY = fixture_available(HUMANO)


class TestElGestorLoPIDE(unittest.TestCase):
    def test_hay_una_fila_de_APA_para_el_humano_y_lleva_su_especie(self):
        fila = next(f for f in required_files(resolve("human")) if f.role == "apa")
        self.assertEqual(fila.filename, "apa_medido_human.tsv")

    def test_y_el_del_raton_NO_sirve_para_el(self):
        # No es una precaucion teorica: la tabla se aplica por md5 del 3'UTR.
        murino = next(f for f in required_files(resolve("mouse")) if f.role == "apa")
        humano = next(f for f in required_files(resolve("human")) if f.role == "apa")
        self.assertNotEqual(murino.filename, humano.filename)


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture humano")
class TestSusSeñalesYaSonMEDIDA(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.informe = tile_utr(load_3utr(HUMANO))

    def test_la_tabla_HUMANA_se_aplica(self):
        self.assertIsNotNone(self.informe.measured_apa)
        self.assertEqual(self.informe.measured_apa.table.assembly, "hg38")

    def test_y_no_es_porque_se_excluyera(self):
        # `None` aqui significaria «esta tabla no habla de esta secuencia», que es
        # distinto de «alguien la excluyo». Si fueran lo mismo, no se sabria cual es.
        self.assertEqual(self.informe.apa_excluded_reason, "")

    def test_son_TRES_y_las_tres_por_MEDIDA(self):
        apa = [
            s for s in self.informe.signals
            if s.classification is SignalClass.APA_POSSIBLE
        ]
        self.assertEqual([s.position for s in apa], [233, 955, 1167])
        for s in apa:
            with self.subTest(s.position):
                self.assertEqual(s.evidence, "medida")

    def test_la_TERCERA_la_trae_la_medida_y_la_prediccion_NO_la_daba(self):
        # `AGTAAA` es variante rara: por la cascada saldria `OTRA`. Entra porque
        # PolyA_DB mide uso en ese sitio, igual que el `AATATA` murino de 3utr:236.
        tercera = next(
            s for s in self.informe.signals
            if s.classification is SignalClass.APA_POSSIBLE and s.position == 233
        )
        self.assertEqual(tercera.motif, "AGTAAA")
        self.assertNotIn(tercera.motif, ("AATAAA", "ATTAAA"))
        # La frase «SUBIDA aquí por MEDIDA de uso» la emite el bloque de TECHOS, no la
        # etiqueta de clase: la etiqueta dice la VIA (medido) y el bloque dice qué habria
        # pasado sin el dato. Se comprueba donde se emite.
        from shmir_design.selection import apa_ceiling_table

        texto = "\n".join(f.describe() for f in apa_ceiling_table(self.informe))
        self.assertIn("SUBIDA aquí por MEDIDA de uso", texto)

    def test_y_NINGUNA_etiqueta_dice_ya_asumido(self):
        for s in self.informe.signals:
            if s.classification is SignalClass.APA_POSSIBLE:
                with self.subTest(s.position):
                    self.assertNotIn("asumido", s.classification_label)


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture humano")
class TestLaMURINAsigueSINaplicarse(unittest.TestCase):
    """El control que la tabla humana NO sustituye.

    Que la propia se aplique no dice nada de que la ajena se rechace: son dos
    afirmaciones y sólo una la comprueba el caso feliz. Se le pone la murina SOLA
    delante del 3'UTR humano, que es el caso que este fichero fijaba desde el principio.
    """

    def setUp(self):
        import shutil
        from pathlib import Path
        from tempfile import TemporaryDirectory

        origen = Path(__file__).resolve().parent.parent / "data" / "reference"
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        shutil.copy(origen / "polya_db_mouse.tsv",
                    Path(self.tmp.name) / "polya_db_mouse.tsv")

    def test_con_la_murina_SOLA_el_humano_no_promueve_nada(self):
        informe = tile_utr(load_3utr(HUMANO), reference_dir=self.tmp.name)
        self.assertIsNone(informe.measured_apa)

    def test_y_el_motivo_dice_que_es_por_md5_y_no_que_falte(self):
        informe = tile_utr(load_3utr(HUMANO), reference_dir=self.tmp.name)
        self.assertIn("md5", informe.apa_missing_reason.lower())


class TestLaFichaSIGUEsiendoDELaESPECIE(unittest.TestCase):
    def test_nombra_hg38_y_PRNP(self):
        from shmir_design.obtencion import resolve_ficha

        texto = resolve_ficha(
            "fraccion_isoforma_larga", species=resolve("human")
        ).render()
        self.assertIn("hg38", texto)
        self.assertIn("PRNP", texto)

    def test_y_dice_QUE_SE_PIERDE_mientras_no_este(self):
        from shmir_design.obtencion import resolve_ficha

        texto = resolve_ficha(
            "fraccion_isoforma_larga", species=resolve("human")
        ).render().lower()
        self.assertIn("asumido", texto)

    def test_la_del_raton_no_habla_de_hg38(self):
        from shmir_design.obtencion import resolve_ficha

        texto = resolve_ficha(
            "fraccion_isoforma_larga", species=resolve("mouse")
        ).render()
        self.assertNotIn("hg38", texto)


if __name__ == "__main__":
    unittest.main()
