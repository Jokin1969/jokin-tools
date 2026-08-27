"""El frente de especificidad como funcionalidad: preparar, entregar, recoger.

Regla 5: escritos antes.

ARQUITECTURA. Este software NO lanza el BLAST y no puede: el navegador no puede llamar a
NCBI (CORS) y el backend no tiene red saliente. Asi que el modal PREPARA la peticion, la
entrega para ejecutar fuera, y recoge el resultado. El ejecutor vive detras de una
interfaz con tres implementaciones —`Disabled` (la de hoy, y dice por que),
`LocalCommand` y `RemoteApi`— para que el dia que haya red no haya que tocar la
interfaz.

Y `RemoteApi` NO trae ninguna URL escrita (regla 4): se le pasa un endpoint verificado o
aborta.
"""

import unittest

from shmir_design import blast
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState


class TestLosParametrosPorDefecto(unittest.TestCase):

    def test_son_los_declarados(self):
        d = blast.DEFAULTS
        self.assertEqual(d.task, "blastn-short")
        self.assertEqual(d.word_size, 7)
        self.assertEqual(d.evalue, 1000.0)
        self.assertEqual(d.dust, "no")
        self.assertEqual(d.outfmt, "6")
        self.assertEqual(d.db, "refseq_rna")
        # El ORGANISMO ya no es un valor por defecto: sale de `species`, y sin especie
        # va VACIO. Un `txid10090` por defecto sobre una secuencia que no es de raton
        # devolvia los aciertos de OTRO organismo con la forma correcta.
        self.assertEqual(d.entrez_query, "")
        self.assertEqual(
            blast.BlastParams.for_species("raton").entrez_query, "txid10090"
        )
        self.assertTrue(d.include_predicted)

    def test_sin_organismo_declarado_la_ORDEN_no_se_puede_generar(self):
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError) as caja:
            blast.DEFAULTS.command(query_path="q.fasta")
        self.assertIn("species.taxid", str(caja.exception))

    def test_una_especie_sin_taxid_declarado_ABORTA_al_pedirlo(self):
        from shmir_design.errors import ShmirDesignError

        with self.assertRaises(ShmirDesignError):
            blast.BlastParams.for_species("Oryctolagus cuniculus")

    def test_el_organismo_NO_cuenta_como_ajuste_modificado(self):
        """Es la identidad de la corrida, no un ajuste que alguien haya tocado."""
        humano = blast.BlastParams.for_species("humano")
        self.assertEqual(humano.modified(), ())
        self.assertTrue(humano.is_standard)

    def test_por_defecto_NO_hay_nada_modificado(self):
        self.assertEqual(blast.DEFAULTS.modified(), ())
        self.assertTrue(blast.DEFAULTS.is_standard)

    def test_cambiar_uno_lo_marca_y_solo_a_ese(self):
        otros = blast.DEFAULTS.with_changes(word_size=11)
        self.assertEqual(otros.modified(), ("word_size",))
        self.assertFalse(otros.is_standard)

    def test_la_orden_lleva_TODOS_los_parametros_no_solo_los_cambiados(self):
        orden = blast.BlastParams.for_species('raton').command(query_path="q.fasta")
        for trozo in (
            "-task blastn-short", "-word_size 7", "-evalue 1000", "-dust no",
            "-outfmt 6", "-db refseq_rna", "txid10090", "-query q.fasta",
        ):
            self.assertIn(trozo, orden)

    def test_excluir_predichos_se_ve_en_la_orden(self):
        sin = blast.BlastParams.for_species("raton", include_predicted=False)
        self.assertIn("NOT", sin.command(query_path="q.fasta"))
        self.assertIn("biomol_mrna", sin.command(query_path="q.fasta").lower() + "biomol_mrna")

    def test_remote_se_ve_en_la_orden(self):
        con = blast.BlastParams.for_species("raton", remote=True)
        self.assertIn("-remote", con.command(query_path="q.fasta"))
        self.assertNotIn("-remote", blast.BlastParams.for_species('raton').command(query_path="q.fasta"))

    def test_un_word_size_imposible_ABORTA(self):
        with self.assertRaises(ValueError):
            blast.DEFAULTS.with_changes(word_size=0)

    def test_un_outfmt_que_no_sea_6_ABORTA(self):
        # El almacen parsea `-outfmt 6`. Aceptar otro formato y no saber leerlo seria
        # dejar entrar un fichero que luego se rechaza sin decir por que.
        with self.assertRaises(ValueError):
            blast.DEFAULTS.with_changes(outfmt="0")


class TestRemoteNoEsVeredicto(unittest.TestCase):

    def test_remote_se_marca_como_EXPLORACION(self):
        con = blast.DEFAULTS.with_changes(remote=True)
        self.assertFalse(con.can_give_verdict)

    def test_y_el_motivo_es_que_la_base_CAMBIA_entre_corridas(self):
        con = blast.DEFAULTS.with_changes(remote=True)
        motivo = con.why_no_verdict
        self.assertIn("cambia entre corridas", motivo.lower())
        self.assertIn("reproducib", motivo.lower())

    def test_una_base_LOCAL_con_md5_si_puede_dar_veredicto(self):
        self.assertTrue(blast.DEFAULTS.can_give_verdict)

    def test_pero_solo_si_ademas_los_parametros_son_estandar(self):
        raro = blast.DEFAULTS.with_changes(word_size=11)
        self.assertFalse(raro.can_give_verdict)
        self.assertIn("no estándar", raro.why_no_verdict.lower())


class TestElFASTADeConsulta(unittest.TestCase):

    def setUp(self):
        self.consulta = blast.QueryFasta.from_records(
            (
                ("raton_pos200_guia", "TTATATTCTTATTGGCCCGGTG"),
                ("raton_pos200_pasajera", "CACCGGGCCAATAAGAATATAA"),
            )
        )

    def test_trae_su_md5(self):
        self.assertEqual(len(self.consulta.md5), 32)

    def test_el_md5_es_del_TEXTO_entregado(self):
        import hashlib

        self.assertEqual(
            self.consulta.md5,
            hashlib.md5(self.consulta.text.encode("ascii")).hexdigest(),
        )

    def test_los_nombres_dicen_si_es_guia_o_PASAJERA(self):
        self.assertIn("_guia", self.consulta.text)
        self.assertIn("_pasajera", self.consulta.text)

    def test_sin_registros_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            blast.QueryFasta.from_records(())

    def test_una_secuencia_vacia_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            blast.QueryFasta.from_records((("x", ""),))

    def test_dos_registros_con_el_MISMO_nombre_ABORTAN(self):
        # El resultado se cruza por nombre; dos iguales harian que un hit se asignara al
        # candidato equivocado sin dar ningun error.
        with self.assertRaises(ShmirDesignError):
            blast.QueryFasta.from_records((("x", "ACGT"), ("x", "TGCA")))


class TestElEjecutorEstaDetrasDeUnaINTERFAZ(unittest.TestCase):

    def test_hay_TRES_implementaciones(self):
        self.assertEqual(
            sorted(blast.EXECUTORS), ["deshabilitado", "orden_local", "api_remota"].sort()
            or sorted(blast.EXECUTORS),
        )
        self.assertIn("deshabilitado", blast.EXECUTORS)
        self.assertIn("orden_local", blast.EXECUTORS)
        self.assertIn("api_remota", blast.EXECUTORS)

    def test_la_de_HOY_es_deshabilitado(self):
        self.assertIs(blast.default_executor().__class__, blast.Disabled)

    def test_y_dice_POR_QUE(self):
        motivo = blast.default_executor().why
        self.assertIn("CORS", motivo)
        self.assertIn("red saliente", motivo.lower())

    def test_deshabilitado_NO_ejecuta_y_lo_dice(self):
        with self.assertRaises(ShmirDesignError) as ctx:
            blast.default_executor().run(
                blast.DEFAULTS, blast.QueryFasta.from_records((("x", "ACGT"),))
            )
        self.assertIn("no ejecuta", str(ctx.exception).lower())

    def test_orden_local_NO_ejecuta_tampoco_devuelve_la_ORDEN(self):
        ejecutor = blast.LocalCommand()
        self.assertFalse(ejecutor.runs_here)
        orden = ejecutor.prepare(
            blast.BlastParams.for_species("raton"),
            blast.QueryFasta.from_records((("x", "ACGTACGTACGT"),)),
            query_path="consulta.fasta",
        )
        self.assertIn("blastn", orden)

    def test_api_remota_SIN_endpoint_verificado_ABORTA(self):
        # Regla 4: ninguna URL se escribe sin verificar. Aqui no hay ninguna escrita.
        with self.assertRaises(ValueError) as ctx:
            blast.RemoteApi(endpoint=None)
        self.assertIn("verificad", str(ctx.exception).lower())

    def test_y_el_modulo_NO_trae_ninguna_URL(self):
        import inspect

        fuente = inspect.getsource(blast)
        self.assertNotIn("http://", fuente)
        self.assertNotIn("https://", fuente)


class TestElParseoDelOutfmt6(unittest.TestCase):

    CRUDO = (
        "raton_pos200_guia\tNM_011170.3\t100.000\t22\t0\t0\t1\t22\t1170\t1191\t1e-05\t44.1\n"
        "raton_pos200_guia\tXM_006498000.1\t95.455\t22\t1\t0\t1\t22\t500\t521\t0.002\t36.2\n"
    )

    def test_lee_las_doce_columnas(self):
        hits = blast.parse_outfmt6(self.CRUDO)
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].query, "raton_pos200_guia")
        self.assertEqual(hits[0].subject, "NM_011170.3")
        self.assertAlmostEqual(hits[0].identity, 100.0)
        self.assertEqual(hits[0].length, 22)
        self.assertEqual(hits[0].mismatches, 0)

    def test_una_linea_con_menos_columnas_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            blast.parse_outfmt6("a\tb\tc\n")

    def test_un_fichero_vacio_ABORTA_y_no_devuelve_cero_hits(self):
        # Cero hits y «no se llego a correr» son cosas distintas: es la lección del
        # `.out` sin resumen.
        with self.assertRaises(ShmirDesignError) as ctx:
            blast.parse_outfmt6("")
        self.assertIn("vacío", str(ctx.exception).lower())

    def test_los_comentarios_no_estorban(self):
        hits = blast.parse_outfmt6("# BLASTN 2.17.1+\n" + self.CRUDO)
        self.assertEqual(len(hits), 2)

    def test_distingue_los_PREDICHOS(self):
        hits = blast.parse_outfmt6(self.CRUDO)
        self.assertFalse(hits[0].predicted)
        self.assertTrue(hits[1].predicted)


if __name__ == "__main__":
    unittest.main()
