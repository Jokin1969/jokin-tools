"""Barrido del ORF conservado raton/humano: la otra via.

Regla 5: escritos antes.

El 3'UTR no da un shmiR unico para las tres cosas (ver test_consecuencia_bloque). El ORF
si tiene tramos de identidad exacta >= 22 nt, y ahi la pregunta se puede volver a hacer
— con la MISMA cascada, y con las mismas reglas sobre lo que no aplica.

Lo que SI aplica fuera del 3'UTR: GC, homopolimeros, asimetria, seeds, repetitivos y
especificidad. Lo que NO: polyA, APA y los tercios, que son heuristicas del 3'UTR. Salen
`NO_APLICA`, nunca `PASS` — la regla 3 lo dice y el bloque 9 ya lo implementaba para las
ventanas del ORF.

Contexto que NO es un detalle: el ORF del casete AAV esta CODON-OPTIMIZADO, asi que el
transgen es resistente a una guia contra el ORF nativo sin recodificar nada. El obstaculo
clasico de la via ORF —que la guia apague tambien el transgen— no existe en este
backbone.

Datos reales: NM_011170.3 (CDS 185..949) y NM_000311.5 (CDS 68..829).
"""

import unittest

from shmir_design.filters import FilterState
from shmir_design.orf_sweep import ORF_NOT_APPLICABLE, orf_sweep
from shmir_design.reference import REFERENCES, fixture_available

RATON, HUMANO = REFERENCES["NM_011170.3"], REFERENCES["NM_000311.5"]


def _orfs():
    from shmir_design.reference import load_reference

    a = load_reference(RATON)
    b = load_reference(HUMANO)
    return (
        a[RATON.cds[0] - 1 : RATON.cds[1]],
        b[HUMANO.cds[0] - 1 : HUMANO.cds[1]],
    )


@unittest.skipUnless(
    fixture_available(RATON) and fixture_available(HUMANO),
    "NOT_RUN: faltan los fixtures de los dos transcritos",
)
class TestElBarridoDelORF(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        orf_a, orf_b = _orfs()
        cls.barrido = orf_sweep(
            orf_a, orf_b,
            species=("raton", "humano"),
            cds_start=(RATON.cds[0], HUMANO.cds[0]),
        )

    def test_los_dos_ORF_miden_lo_que_dice_la_anotacion(self):
        self.assertEqual(self.barrido.lengths, (765, 762))

    def test_hay_CUATRO_bloques_de_identidad_exacta_de_22_o_mas(self):
        self.assertEqual([b.length for b in self.barrido.blocks], [32, 23, 23, 22])

    def test_caben_16_ventanas_dentro_de_ellos(self):
        self.assertEqual(self.barrido.windows, 16)

    def test_y_DOS_superan_los_filtros_de_secuencia(self):
        self.assertEqual(len(self.barrido.passing), 2)

    def test_las_dos_estan_en_el_bloque_de_23_nt(self):
        # ORF raton 523-545, humano 526-548.
        for candidato in self.barrido.passing:
            with self.subTest(candidato.orf_start_a):
                self.assertIn(candidato.orf_start_a, (523, 524))

    def test_las_coordenadas_salen_TAMBIEN_en_el_transcrito(self):
        # El ORF empieza en tx:185 del raton: la ventana de ORF 523 es tx:707.
        candidato = min(self.barrido.passing, key=lambda c: c.orf_start_a)
        self.assertEqual(candidato.tx_start_a, 185 + 523 - 1)

    def test_la_diana_es_la_MISMA_en_las_dos_especies(self):
        # Es el sentido de todo el barrido: por eso una sola guia sirve para las dos.
        for candidato in self.barrido.passing:
            with self.subTest(candidato.orf_start_a):
                self.assertEqual(candidato.target_a, candidato.target_b)


@unittest.skipUnless(
    fixture_available(RATON) and fixture_available(HUMANO),
    "NOT_RUN: faltan los fixtures de los dos transcritos",
)
class TestLoQueNoAplicaFueraDel3UTR(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        orf_a, orf_b = _orfs()
        cls.barrido = orf_sweep(
            orf_a, orf_b,
            species=("raton", "humano"),
            cds_start=(RATON.cds[0], HUMANO.cds[0]),
        )

    def test_polyA_APA_y_tercios_salen_NO_APLICA(self):
        self.assertEqual(
            set(ORF_NOT_APPLICABLE), {"zona_prohibida_polyA", "APA", "tercio"}
        )
        for candidato in self.barrido.passing:
            estados = {r.name: r.state for r in candidato.not_applicable}
            for nombre in ORF_NOT_APPLICABLE:
                with self.subTest((candidato.orf_start_a, nombre)):
                    self.assertIs(estados[nombre], FilterState.NO_APLICA)

    def test_NO_APLICA_no_es_PASS_y_el_motivo_lo_dice(self):
        candidato = self.barrido.passing[0]
        for resultado in candidato.not_applicable:
            with self.subTest(resultado.name):
                self.assertIsNot(resultado.state, FilterState.PASS)
                self.assertIn("3'UTR", resultado.reason)

    def test_los_filtros_por_recurso_siguen_en_NOT_RUN(self):
        # seeds, repetitivos y especificidad SI aplican en el ORF: sin fichero, NOT_RUN.
        candidato = self.barrido.passing[0]
        pendientes = {r.name for r in candidato.pending}
        self.assertEqual(pendientes, {"seed_colision", "repeticiones", "especificidad"})
        for resultado in candidato.pending:
            with self.subTest(resultado.name):
                self.assertIs(resultado.state, FilterState.NOT_RUN)

    def test_el_texto_dice_lo_del_casete_codon_optimizado(self):
        texto = "\n".join(self.barrido.describe()).lower()
        self.assertIn("codón-optimizado", texto)
        self.assertIn("resistente", texto)
        self.assertIn("sin\n  recodificar", texto)

    def test_y_no_promete_un_veredicto_que_no_tiene(self):
        texto = "\n".join(self.barrido.describe())
        self.assertIn("NOT_RUN", texto)
        self.assertNotIn("APROBADO", texto)


@unittest.skipUnless(
    fixture_available(RATON) and fixture_available(HUMANO),
    "NOT_RUN: faltan los fixtures de los dos transcritos",
)
class TestElContextoDeLaVentana(unittest.TestCase):
    """El codon se CALCULA; la anotacion estructural se declara y se marca como tal."""

    @classmethod
    def setUpClass(cls):
        orf_a, orf_b = _orfs()
        cls.barrido = orf_sweep(
            orf_a, orf_b,
            species=("raton", "humano"),
            cds_start=(RATON.cds[0], HUMANO.cds[0]),
        )
        cls.primero = min(cls.barrido.passing, key=lambda c: c.orf_start_a)

    def test_la_ventana_empieza_en_el_primer_nucleotido_de_un_codon(self):
        self.assertEqual((self.primero.orf_start_a - 1) % 3, 0)

    def test_el_codon_calculado_es_el_175_en_raton(self):
        self.assertEqual(self.primero.codon_a, 175)

    def test_y_el_176_en_humano_porque_el_ORF_humano_es_3_nt_mas_corto(self):
        self.assertEqual(self.primero.codon_b, 176)

    def test_la_ventana_cubre_ocho_codones(self):
        self.assertEqual(self.primero.codon_span_a, (175, 182))

    def test_la_parte_declarada_va_marcada_como_DECLARADA(self):
        # ACTUALIZADO 2026-08-26: el desajuste de numeracion se RESOLVIO —el «143» era
        # contaminacion con el W144Y del plasmido— y el codon, el peptido y las
        # cisteinas pasaron a VERIFICADOS. Lo unico que sigue declarado es la helice.
        texto = "\n".join(self.barrido.describe())
        self.assertIn("DECLARADO por el responsable", texto)
        self.assertIn("sin comprobar aquí", texto)
        self.assertIn("VERIFICADO aquí traduciendo", texto)

    def test_gnomAD_queda_como_OBLIGATORIO_y_con_el_motivo(self):
        texto = "\n".join(self.barrido.describe())
        self.assertIn("gnomAD", texto)
        self.assertIn("sinonimo", texto.lower())
        self.assertIn("NOT_RUN", texto)

    def test_la_propiedad_clave_de_alcance_esta_escrita(self):
        texto = "\n".join(self.barrido.describe())
        self.assertIn("PRNP humano", texto)
        self.assertIn("Tg650", texto)
        self.assertIn("NO alcanza el transgén", texto)


@unittest.skipUnless(
    fixture_available(RATON) and fixture_available(HUMANO),
    "NOT_RUN: faltan los fixtures de los dos transcritos",
)
class TestLaNotaCorregida(unittest.TestCase):
    """Codon, peptido y cisteinas: VERIFICADOS traduciendo los ORF del repositorio.

    La asignacion de helice sigue siendo declarada. Separar las dos cosas es el punto:
    la nota anterior mezclaba una numeracion equivocada (codon 143, contaminacion con el
    W144Y del plasmido) y un «segundo puente disulfuro» que no existe.

    PrP tiene UN solo puente. Y eso se puede comprobar aqui sin estructura: en el ORF
    murino solo hay TRES cisteinas —22, 178 y 213— y la 22 esta en el peptido señal, asi
    que 178-213 es el unico par posible. En humano, 6/22/179/214.
    """

    @classmethod
    def setUpClass(cls):
        orf_a, orf_b = _orfs()
        cls.barrido = orf_sweep(
            orf_a, orf_b,
            species=("raton", "humano"),
            cds_start=(RATON.cds[0], HUMANO.cds[0]),
        )
        cls.primero = min(cls.barrido.passing, key=lambda c: c.orf_start_a)
        cls.texto = "\n".join(cls.barrido.describe())

    def test_el_peptido_se_traduce_y_es_VHDCVNIT(self):
        self.assertEqual(self.primero.peptide, "VHDCVNIT")

    def test_es_el_MISMO_peptido_en_las_dos_especies(self):
        self.assertEqual(self.primero.peptide, self.primero.peptide_b)

    def test_la_cisteina_esta_en_la_POSICION_4_de_la_ventana(self):
        self.assertEqual(self.primero.peptide[3], "C")
        self.assertEqual(self.primero.cysteine_codon_a, 178)
        self.assertEqual(self.primero.cysteine_codon_b, 179)

    def test_solo_hay_UN_par_de_cisteinas_posible_fuera_del_peptido_señal(self):
        # Es lo que sostiene «un solo puente disulfuro» sin necesitar estructura.
        self.assertEqual(self.barrido.cysteines_a, (22, 178, 213))
        self.assertEqual(self.barrido.cysteines_b, (6, 22, 179, 214))

    def test_la_nota_dice_UN_puente_y_no_dos(self):
        self.assertIn("UN solo puente disulfuro", self.texto)
        self.assertIn("C178-C213", self.texto)
        self.assertIn("C179-C214", self.texto)

    def test_lo_verificado_va_marcado_como_VERIFICADO_y_como(self):
        self.assertIn("VERIFICADO aquí traduciendo", self.texto)

    def test_la_helice_sigue_siendo_DECLARADA(self):
        self.assertIn("helice B", self.texto)
        self.assertIn("DECLARADO por el responsable", self.texto)
        self.assertIn("173", self.texto)

    def test_ya_no_queda_rastro_del_143_ni_del_segundo_puente(self):
        self.assertNotIn("143", self.texto)
        self.assertNotIn("segundo puente", self.texto)
