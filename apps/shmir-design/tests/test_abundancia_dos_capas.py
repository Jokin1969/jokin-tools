"""La abundancia en cerebro son DOS capas, no una lista.

Regla 5: escritos antes.

- **Nucleo, FAIL duro, EN CODIGO y sin cita**: es consenso del campo, autorizado por el
  responsable del proyecto el 2026-08-26. Compartir seed con uno de estos no da
  off-targets dispersos: SECUESTRA UN PROGRAMA REGULADOR NEURONAL COMPLETO.
- **Capa ampliada, AVISO, de fichero**: el resto de `mmu-` por encima de un umbral de
  abundancia tomado de un dataset publicado de small RNA-seq de cerebro murino. El
  fichero lleva en cabecera la REFERENCIA y el UMBRAL; sin ellos la capa es `NOT_RUN`,
  y `NOT_RUN` no es `PASS`.

Esto REVIERTE una regla anterior del proyecto —«no hay ninguna lista de miARN escrita en
el codigo»— y por eso la autorizacion va escrita, con fecha y con el motivo. Lo que no
cambia es que la capa ampliada necesita su fichero con procedencia.

Y la familia miR-30 se señala APARTE: el andamio es miR-E, derivado de miR-30a, asi que
una colision ahi tiene otra lectura y peor.
"""

import unittest

from shmir_design.filters import FilterState
from shmir_design.mirna import (
    CORE_ABUNDANT,
    CORE_AUTHORIZATION,
    MIR30_FAMILY,
    core_hits,
    parse_abundance_list,
)


class TestElNucleo(unittest.TestCase):

    def test_estan_los_diez_que_se_pidieron(self):
        self.assertEqual(
            [m.label for m in CORE_ABUNDANT],
            [
                "miR-124-3p", "miR-9-5p", "let-7 (familia)", "miR-128-3p",
                "miR-181a-5p", "miR-125b-5p", "miR-30 (familia)", "miR-26a-5p",
                "miR-99a-5p", "miR-138-5p",
            ],
        )

    def test_la_autorizacion_esta_escrita_con_fecha_y_motivo(self):
        self.assertIn("2026-08-26", CORE_AUTHORIZATION)
        self.assertIn("consenso del campo", CORE_AUTHORIZATION)
        self.assertIn("responsable del proyecto", CORE_AUTHORIZATION)

    def test_casa_con_el_prefijo_de_especie_de_miRBase(self):
        self.assertTrue(core_hits(["mmu-miR-124-3p"]))
        self.assertTrue(core_hits(["hsa-miR-124-3p"]))

    def test_no_casa_con_otro_miARN_parecido(self):
        # miR-124-5p no es miR-124-3p, y miR-1245 no es miR-124.
        self.assertFalse(core_hits(["mmu-miR-124-5p"]))
        self.assertFalse(core_hits(["mmu-miR-1245-3p"]))

    def test_las_familias_casan_por_familia(self):
        for nombre in ("mmu-let-7a-5p", "mmu-let-7g-5p", "mmu-miR-30c-5p"):
            with self.subTest(nombre):
                self.assertTrue(core_hits([nombre]))

    def test_pero_let_7_no_se_come_a_miR_7(self):
        self.assertFalse(core_hits(["mmu-miR-7a-5p"]))

    def test_la_familia_miR_30_se_señala_APARTE(self):
        marcados = core_hits(["mmu-miR-30a-5p", "mmu-miR-124-3p"])
        de_30 = [h for h in marcados if h.family is MIR30_FAMILY]
        self.assertEqual([h.name for h in de_30], ["mmu-miR-30a-5p"])

    def test_y_su_motivo_dice_por_que_es_PEOR(self):
        motivo = core_hits(["mmu-miR-30a-5p"])[0].reason
        self.assertIn("miR-E", motivo)
        self.assertIn("miR-30a", motivo)

    def test_el_motivo_del_nucleo_dice_lo_del_programa_regulador(self):
        motivo = core_hits(["mmu-miR-124-3p"])[0].reason.lower()
        self.assertIn("programa regulador neuronal", motivo)
        # La frase contrasta las dos cosas a proposito: NO son off-targets dispersos.
        self.assertIn("no produce off-targets dispersos", motivo)


class TestLaCapaAmpliadaNecesitaProcedencia(unittest.TestCase):

    CABECERA = (
        "# referencia: dataset publicado de small RNA-seq de cerebro murino "
        "(pendiente de citar)\n"
        "# umbral: 100 RPM\n"
    )

    def _lista(self, texto):
        return parse_abundance_list(
            texto, source="sonda", version="sonda", checksum="0" * 32
        )

    def test_con_referencia_y_umbral_la_capa_corre(self):
        lista = self._lista(self.CABECERA + "mmu-miR-1a-3p\n")
        self.assertTrue(lista.usable)
        self.assertEqual(lista.threshold, "100 RPM")

    def test_sin_referencia_la_capa_es_NOT_RUN(self):
        lista = self._lista("# umbral: 100 RPM\nmmu-miR-1a-3p\n")
        self.assertFalse(lista.usable)
        self.assertIn("referencia", lista.missing_reason.lower())

    def test_sin_umbral_tambien(self):
        lista = self._lista("# referencia: algo\nmmu-miR-1a-3p\n")
        self.assertFalse(lista.usable)
        self.assertIn("umbral", lista.missing_reason.lower())

    def test_una_capa_sin_procedencia_NO_se_usa_para_avisar(self):
        # Si se usara, un aviso sin umbral parece un veredicto y no lo es.
        lista = self._lista("mmu-miR-1a-3p\n")
        self.assertFalse(lista.usable)
        self.assertEqual(lista.names, frozenset())


class TestElFiltroConLasDosCapas(unittest.TestCase):
    """Sin fichero, el NUCLEO sigue dando FAIL: no necesita recurso."""

    def _mature(self, entradas):
        from shmir_design.mirna import parse_mature_fa

        texto = "".join(f">{n} X\n{s}\n" for n, s in entradas)
        return parse_mature_fa(
            texto, source="sonda", version="sonda", checksum="0" * 32,
            prefixes=("mmu-", "hsa-"),
        )

    def test_sin_lista_ampliada_una_colision_del_nucleo_es_FAIL(self):
        from shmir_design.mirna import filter_seed_collision
        from shmir_design.reference import REFERENCES, fixture_available, load_3utr

        if not fixture_available(REFERENCES["NM_011170.3"]):
            self.skipTest("NOT_RUN: falta el fixture murino")
        utr3 = load_3utr(REFERENCES["NM_011170.3"])
        diana = utr3[59:81]
        guia = "T" + diana.translate(str.maketrans("ACGT", "TGCA"))[::-1][1:]
        maduro = "U" + guia[1:8].replace("T", "U") + "ACGUACGUACGUAC"
        mature = self._mature([("mmu-miR-124-3p", maduro)])
        resultado = filter_seed_collision(guia, mature, None)
        self.assertIs(resultado.state, FilterState.FAIL)
        self.assertIn("miR-124-3p", resultado.reason)

    def test_el_alfabeto_se_normaliza_antes_de_comparar(self):
        # El maduro de miRBase viene en ARN (U) y la guia en ADN (T). Sin convertir,
        # CERO colisiones — y eso parece una buena noticia.
        from shmir_design.mirna import filter_seed_collision
        from shmir_design.reference import REFERENCES, fixture_available, load_3utr

        if not fixture_available(REFERENCES["NM_011170.3"]):
            self.skipTest("NOT_RUN: falta el fixture murino")
        utr3 = load_3utr(REFERENCES["NM_011170.3"])
        diana = utr3[59:81]
        guia = "T" + diana.translate(str.maketrans("ACGT", "TGCA"))[::-1][1:]
        en_arn = self._mature([("mmu-miR-124-3p", "U" + guia[1:8].replace("T", "U") + "ACGUACGUACGUAC")])
        en_adn = self._mature([("mmu-miR-124-3p", "T" + guia[1:8] + "ACGTACGTACGTAC")])
        self.assertIs(
            filter_seed_collision(guia, en_arn, None).state,
            filter_seed_collision(guia, en_adn, None).state,
        )
