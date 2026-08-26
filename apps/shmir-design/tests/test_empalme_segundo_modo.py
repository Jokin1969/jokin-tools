"""Los uATG son un SEGUNDO modo de fallo, y el donante criptico se comprueba hoy.

Regla 5: escritos antes.

Si el intron se retiene pasan DOS cosas distintas, no una con un detalle:

  (a) la horquilla se queda en el 5'UTR del mRNA maduro;
  (b) el ribosoma escanea desde el extremo 5' y se encuentra al menos cinco AUG antes
      del legitimo.

El segundo actua **aunque la horquilla no estorbara nada**, asi que no es una nota al
pie del primero. Y dentro del segundo hay un caso peor que los demas: un uAUG EN MARCO
que llegue al ORF sin codon de parada da PrP con extension N-terminal — algo que se
produce y que un Western podria confundir con la DN.

Y una cosa se puede cerrar hoy, sin ningun fichero: si entre el donante criptico
`GTGAGCG` del flanco 5' de miR-E y el aceptor legitimo del MVM hay o no un aceptor
utilizable.
"""

import unittest

from shmir_design import splicing
from shmir_design.blocks import INTRON_LENGTH, PIECES
from shmir_design.scaffold import REFERENCE_HAIRPIN


def _intron() -> str:
    def s(n):
        return PIECES[n].sequence

    return (
        s("MVM5") + s("espaciador5") + s("NheI") + s("contexto5") + REFERENCE_HAIRPIN
        + s("contexto3") + s("SacI") + s("espaciador3") + s("MVM3")
    )


class TestSonDosModosDeFallo(unittest.TestCase):

    def test_estan_SEPARADOS_y_numerados(self):
        texto = splicing.RETENTION_MODES
        self.assertIn("(a)", texto)
        self.assertIn("(b)", texto)

    def test_el_primero_es_la_horquilla_en_el_5UTR(self):
        self.assertIn("horquilla", splicing.RETENTION_MODES)
        self.assertIn("5'UTR", splicing.RETENTION_MODES)

    def test_el_segundo_es_el_ESCANEO(self):
        self.assertIn("escanea", splicing.RETENTION_MODES)
        self.assertIn("AUG", splicing.RETENTION_MODES)

    def test_y_dice_que_el_segundo_actua_AUNQUE_el_primero_no(self):
        self.assertIn("aunque", splicing.RETENTION_MODES.lower())


class TestElEscaneoDeUATG(unittest.TestCase):

    def setUp(self):
        self.intron = _intron()
        self.uatgs = splicing.scan_upstream_atgs(self.intron)

    def test_hay_al_menos_CINCO(self):
        self.assertGreaterEqual(len(self.uatgs), 5)

    def test_con_la_horquilla_de_referencia_son_OCHO(self):
        self.assertEqual(len(self.uatgs), 8)

    def test_cada_uno_trae_posicion_contexto_y_Kozak(self):
        for u in self.uatgs:
            self.assertGreaterEqual(u.offset, 1)
            self.assertIn("ATG", u.context)
            self.assertIn(u.strength, ("FUERTE", "adecuado", "debil"))

    def test_el_criterio_de_Kozak_va_DECLARADO_no_citado(self):
        self.assertIn("-3", splicing.KOZAK_CRITERION)
        self.assertIn("+4", splicing.KOZAK_CRITERION)
        self.assertIn("declarad", splicing.KOZAK_CRITERION.lower())

    def test_el_de_MVM5_en_16_es_FUERTE_y_EN_MARCO(self):
        u = next(x for x in self.uatgs if x.offset == 16)
        self.assertEqual(u.strength, "FUERTE")
        self.assertTrue(u.in_frame)
        self.assertEqual(u.distance_to_orf, 318)

    def test_PERO_no_da_extension_porque_PARA_a_los_10_codones(self):
        # Es la diferencia entre «uORF» y «PrP con extension N-terminal», y es
        # exactamente la que decide si el Western puede confundirse.
        u = next(x for x in self.uatgs if x.offset == 16)
        self.assertEqual(u.stop_after_codons, 10)
        self.assertEqual(u.outcome, "uORF")

    def test_NINGUNO_da_extension_N_terminal_con_esta_horquilla(self):
        self.assertEqual(
            [u.offset for u in self.uatgs if u.outcome == "EXTENSION_N_TERMINAL"], []
        )

    def test_y_eso_se_dice_como_RESULTADO_no_como_ausencia_de_noticia(self):
        texto = splicing.describe_upstream_atgs(self.uatgs)
        self.assertIn("EXTENSION", texto.upper())
        self.assertIn("ninguno", texto.lower())

    def test_los_de_fuera_de_marco_NO_dan_extension(self):
        for u in self.uatgs:
            if not u.in_frame:
                self.assertNotEqual(u.outcome, "EXTENSION_N_TERMINAL")

    def test_hay_una_TERCERA_categoria_el_uORF_que_SOLAPA_el_inicio(self):
        # Fuera de marco y SIN parada antes del ATG legitimo: el ribosoma sigue
        # elongando al pasar por el, asi que no puede reiniciar ahi. Es peor que un uORF
        # que termina antes, y meterlo en el mismo saco lo escondia.
        solapantes = [u.offset for u in self.uatgs if u.outcome == "uORF_SOLAPANTE"]
        self.assertEqual(solapantes, [210, 237])

    def test_y_el_texto_lo_dice_aparte(self):
        texto = splicing.describe_upstream_atgs(self.uatgs)
        self.assertIn("SOLAPA", texto)
        self.assertIn("reiniciar", texto)

    def test_se_dice_de_QUE_PIEZA_es_cada_uno(self):
        piezas = {u.piece for u in self.uatgs}
        self.assertIn("MVM5", piezas)
        self.assertIn("horquilla", piezas)

    def test_la_cuenta_DEPENDE_de_la_guia_y_se_avisa(self):
        # Tres de los ocho estan en la horquilla, asi que otro candidato da otra cuenta.
        self.assertEqual(sum(1 for u in self.uatgs if u.piece == "horquilla"), 3)
        self.assertIn("POR CANDIDATO", splicing.describe_upstream_atgs(self.uatgs))

    def test_sin_intron_no_hay_nada_que_escanear(self):
        self.assertEqual(splicing.scan_upstream_atgs(""), ())


class TestElDonanteCRIPTICO(unittest.TestCase):

    def setUp(self):
        self.analisis = splicing.cryptic_donor_scan(_intron())

    def test_el_donante_criptico_esta_en_el_offset_98(self):
        self.assertEqual(self.analisis.donor_offset, 98)
        self.assertEqual(self.analisis.donor_motif, "GTGAGCG")

    def test_el_aceptor_legitimo_esta_al_final_del_intron(self):
        self.assertEqual(self.analisis.acceptor_offset, INTRON_LENGTH - 1)

    def test_se_miran_TODOS_los_AG_del_intervalo(self):
        self.assertEqual(len(self.analisis.candidates), 13)

    def test_el_legitimo_tiene_un_tracto_de_9_pirimidinas(self):
        self.assertEqual(self.analisis.acceptor_tract, 9)

    def test_y_NINGUN_criptico_pasa_de_3(self):
        self.assertEqual(max(c.tract for c in self.analisis.candidates), 3)

    def test_veredicto_NO_hay_aceptor_criptico_utilizable(self):
        self.assertFalse(self.analisis.usable_cryptic_acceptor)

    def test_el_criterio_va_declarado_como_PARAMETRO_no_como_cita(self):
        self.assertIn("declarad", splicing.SPLICE_SITE_CRITERION.lower())
        self.assertIn("no es una cita", splicing.SPLICE_SITE_CRITERION.lower())

    def test_PERO_el_riesgo_NO_se_cierra_y_se_dice_por_que(self):
        # El donante criptico no NECESITA un aceptor criptico: el legitimo del MVM esta
        # aguas abajo y es perfectamente utilizable. Es la correccion que importa.
        texto = "\n".join(self.analisis.describe())
        self.assertIn("NO se cierra", texto)
        self.assertIn("no necesita", texto.lower())

    def test_y_emite_el_TAMAÑO_del_producto_criptico(self):
        # Es lo que lo hace confundible: banda intermedia, no ausente.
        self.assertEqual(self.analisis.retained_if_cryptic, 97)
        self.assertIn("97", "\n".join(self.analisis.describe()))

    def test_ese_tamaño_es_DISTINTO_de_los_otros_dos(self):
        self.assertNotIn(self.analisis.retained_if_cryptic, (0, INTRON_LENGTH))


class TestLaCuartaLectura(unittest.TestCase):

    def setUp(self):
        self.lecturas = {l.name: l for l in splicing.splicing_readouts()}

    def test_ahora_son_CUATRO(self):
        self.assertEqual(len(self.lecturas), 4)

    def test_la_nueva_se_llama_secuencia_de_la_union(self):
        self.assertIn("secuencia_union_exon_exon", self.lecturas)

    def test_es_la_que_DE_VERDAD_cierra_el_frente(self):
        motivo = self.lecturas["secuencia_union_exon_exon"].requirement
        self.assertIn("la que cierra", motivo.lower())

    def test_dice_que_la_lectura_de_exito_es_la_SECUENCIA_no_la_ALTURA(self):
        motivo = self.lecturas["secuencia_union_exon_exon"].requirement
        self.assertIn("no la altura", motivo.lower())

    def test_nombra_el_donante_criptico_y_su_banda(self):
        motivo = self.lecturas["secuencia_union_exon_exon"].requirement
        self.assertIn("GTGAGCG", motivo)
        self.assertIn("97", motivo)


if __name__ == "__main__":
    unittest.main()


class TestElNumeroDelCripticoNoSeTECLEA(unittest.TestCase):
    """`CRYPTIC_RETAINED` tiene que salir de la secuencia, no de una constante suelta."""

    def test_coincide_con_lo_que_mide_el_intron_de_verdad(self):
        analisis = splicing.cryptic_donor_scan(_intron())
        self.assertEqual(analisis.retained_if_cryptic, splicing.CRYPTIC_RETAINED)
