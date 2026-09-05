"""El CUARTO modal: prediccion de sitios de splicing. Y en que se diferencia.

Regla 5: escritos antes.

Los otros tres preguntan sobre una guia de 22 nt. Este pregunta sobre el **cassette
montado**, asi que la unidad es el par **candidato x intron**: diez candidatos y tres
intrones son treinta consultas, no una lista de diez.

Y hay una diferencia mas grande todavia: **SpliceAI no fue entrenado para esto**. Se
entreno sobre secuencia genomica humana con ventana de 10.000 nt para predecir el efecto
de variantes. Un cassette de AAV no se le parece — no hay contexto genomico, las
longitudes son atipicas y la composicion tambien. Consecuencia, y va ANTES del boton:

  - las puntuaciones ABSOLUTAS no son interpretables, y no hay umbral que aplicar;
  - solo vale la comparacion RELATIVA contra un referente INTERNO: el donante legitimo
    del mismo intron, en la misma corrida;
  - nada de esto es un veredicto.
"""

import unittest

from shmir_design import blocks, introns, spliceai
from shmir_design.errors import ShmirDesignError
from shmir_design.filters import FilterState
from shmir_design.reference import REFERENCES, fixture_available, load_3utr
from shmir_design.scaffold import SGEP_SCAFFOLD

RATON = REFERENCES["NM_011170.3"]
HAY = fixture_available(RATON)


def _panel(n=3):
    from shmir_design.selection import SelectionConfig, select_from_report
    from shmir_design.tiling import tile_utr

    utr3 = load_3utr(RATON)
    return utr3, select_from_report(tile_utr(utr3), SelectionConfig(n_candidates=n))


# ─────────── A. la unidad de analisis NO es el candidato ───────────


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del raton")
class TestLaUnidadEsElPar(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.seleccion = _panel(3)

    def _construcciones(self, nombres=("mvm_actual",)):
        return spliceai.build_constructions(
            self.seleccion,
            intron_names=nombres,
            scaffold=SGEP_SCAFFOLD,
        )

    def test_tres_candidatos_por_UN_intron_son_TRES_consultas(self):
        self.assertEqual(len(self._construcciones()), 3)

    def test_y_cada_una_declara_su_candidato_Y_su_intron(self):
        for c in self._construcciones():
            self.assertTrue(c.candidate_start > 0)
            self.assertEqual(c.intron, "mvm_actual")

    def test_un_intron_QUE_NO_TENEMOS_no_produce_consultas_pero_SE_VE(self):
        """NOT_RUN visible: un intron que no se ve no existe."""
        informe = spliceai.intron_report(("mvm_actual", "mvm_sin_criptico"))
        estados = {f["intron"]: f["estado"] for f in informe}
        self.assertIs(estados["mvm_actual"], FilterState.PASS)
        self.assertIs(estados["mvm_sin_criptico"], FilterState.NOT_RUN)

    def test_y_pedir_construcciones_de_uno_que_falta_ABORTA(self):
        with self.assertRaises(ShmirDesignError):
            self._construcciones(("mvm_sin_criptico",))

    def test_la_construccion_lleva_el_INTRON_ENTERO_con_el_modulo_dentro(self):
        c = self._construcciones()[0]
        self.assertIn(blocks.PIECES["MVM5"].sequence, c.sequence)
        self.assertIn(blocks.PIECES["MVM3"].sequence, c.sequence)

    def test_y_contexto_EXONICO_a_los_dos_lados(self):
        c = self._construcciones()[0]
        self.assertGreater(c.context_5, 0)
        self.assertGreater(c.context_3, 0)

    def test_la_VENTANA_DE_CONTEXTO_viaja_con_el_resultado(self):
        """Cambia el resultado, asi que sin registrarla no es reproducible."""
        c = self._construcciones()[0]
        self.assertIn("contexto", c.describe().lower())
        self.assertIn(str(c.context_5), c.describe())

    def test_cada_construccion_lleva_su_md5(self):
        for c in self._construcciones():
            self.assertEqual(len(c.md5), 32)

    def test_dos_candidatos_distintos_dan_md5_distintos(self):
        md5s = {c.md5 for c in self._construcciones()}
        self.assertEqual(len(md5s), 3)

    def test_SIN_casete_el_contexto_son_los_5_nt_de_las_piezas_Y_SE_DICE(self):
        """Cinco nt es esencialmente NINGUN contexto para un modelo que mira miles.

        No se esconde: sale en la fila, viaja con el resultado, y `context_note()` dice
        con esas palabras que es poco y como conseguir mas.
        """
        c = self._construcciones()[0]
        self.assertEqual((c.context_5, c.context_3), (5, 5))
        nota = spliceai.context_note(self._construcciones())
        self.assertIn("casete", nota.lower())
        self.assertTrue(nota.strip())

    def test_CON_casete_el_contexto_se_saca_de_la_secuencia_REAL(self):
        from pathlib import Path

        casete = Path("data/reference/aav_casete.fa")
        if not casete.is_file():
            self.skipTest("NOT_RUN: falta data/reference/aav_casete.fa")
        from shmir_design.fetch import parse_fasta_payload

        secuencia = parse_fasta_payload(
            casete.read_text(encoding="utf-8"), source="aav_casete.fa"
        )
        cs = spliceai.build_constructions(
            self.seleccion, intron_names=("mvm_actual",),
            scaffold=SGEP_SCAFFOLD, cassette=secuencia, context_nt=100,
        )
        self.assertEqual((cs[0].context_5, cs[0].context_3), (100, 100))

    def test_y_pedir_mas_contexto_del_que_hay_NO_lo_inventa(self):
        """Regla 1: si el casete no da para tanto, se da lo que hay y se DICE."""
        from pathlib import Path

        casete = Path("data/reference/aav_casete.fa")
        if not casete.is_file():
            self.skipTest("NOT_RUN: falta data/reference/aav_casete.fa")
        from shmir_design.fetch import parse_fasta_payload

        secuencia = parse_fasta_payload(
            casete.read_text(encoding="utf-8"), source="aav_casete.fa"
        )
        cs = spliceai.build_constructions(
            self.seleccion, intron_names=("mvm_actual",),
            scaffold=SGEP_SCAFFOLD, cassette=secuencia, context_nt=100000,
        )
        # Se recorta a lo que el casete da; nunca se rellena.
        self.assertLess(cs[0].context_5, 100000)
        self.assertGreater(cs[0].context_5, 0)

    def test_el_FASTA_lleva_el_md5_en_la_cabecera(self):
        fasta = spliceai.constructions_fasta(self._construcciones())
        self.assertEqual(fasta.count(">"), 3)
        for c in self._construcciones():
            self.assertIn(c.md5, fasta)


# ─────────── B. SpliceAI no fue entrenado para esto ───────────


class TestLoQueSE_DICE_ANTES_DEL_BOTON(unittest.TestCase):

    def test_dice_para_QUE_fue_entrenado(self):
        texto = spliceai.NOT_TRAINED_FOR_THIS
        self.assertIn("10.000", texto)
        self.assertIn("variantes", texto.lower())
        self.assertIn("human", texto.lower())

    def test_y_que_un_cassette_de_AAV_no_se_le_parece(self):
        self.assertIn("AAV", spliceai.NOT_TRAINED_FOR_THIS)

    def test_las_puntuaciones_ABSOLUTAS_no_son_interpretables(self):
        texto = spliceai.NO_ABSOLUTE_THRESHOLD
        self.assertIn("absolut", texto.lower())
        self.assertIn("umbral", texto.lower())

    def test_solo_vale_la_comparacion_RELATIVA_contra_el_LEGITIMO(self):
        texto = spliceai.RELATIVE_ONLY
        self.assertIn("donante legítimo", texto.lower())
        self.assertIn("misma corrida", texto.lower())

    def test_y_se_dice_que_es_el_MISMO_criterio_de_los_aceptores_cripticos(self):
        self.assertIn("pirimidina", spliceai.RELATIVE_ONLY.lower())

    def test_la_ventana_de_contexto_se_declara_porque_CAMBIA_el_resultado(self):
        self.assertIn("cambia el resultado", spliceai.CONTEXT_MATTERS.lower())

    def test_NADA_de_esto_es_un_veredicto(self):
        self.assertIn("no es un veredicto", spliceai.USE_NOTE.lower())

    def test_y_el_uso_es_DESEMPATE_Y_ALERTA_nunca_filtro(self):
        texto = spliceai.USE_NOTE.lower()
        self.assertIn("desempate", texto)
        self.assertIn("nunca filtro", texto)

    def test_los_bloques_salen_para_pintar_TODOS(self):
        bloques = spliceai.warning_blocks()
        self.assertGreaterEqual(len(bloques), 4)
        for b in bloques:
            self.assertTrue(b["texto"].strip())
            self.assertTrue(b["activo"])


# ─────────── C. ejecucion: patron BLAST, y sin inventar la orden ───────────


class TestElEjecutor(unittest.TestCase):

    def test_el_de_HOY_no_ejecuta_y_dice_por_que(self):
        ejecutor = spliceai.Disabled()
        self.assertFalse(ejecutor.runs_here)
        self.assertIn("no tiene red", ejecutor.why.lower())

    def test_y_llamarlo_ABORTA_en_vez_de_devolver_vacio(self):
        with self.assertRaises(ShmirDesignError):
            spliceai.Disabled().run(constructions=())

    def test_LocalCommand_NO_trae_ninguna_orden_escrita(self):
        """Regla 4 generalizada: la invocacion de SpliceAI no se ha verificado desde
        este proyecto, asi que no se escribe — se pide."""
        with self.assertRaises(ValueError) as caja:
            spliceai.LocalCommand(command="")
        self.assertIn("verificad", str(caja.exception).lower())

    def test_con_una_orden_dada_la_prepara_pero_no_la_lanza(self):
        ejecutor = spliceai.LocalCommand(command="mi-spliceai --entrada {fasta}")
        orden = ejecutor.prepare(fasta_path="construcciones.fa")
        self.assertIn("construcciones.fa", orden)
        with self.assertRaises(ShmirDesignError):
            ejecutor.run(constructions=())

    def test_el_modulo_NO_tiene_ni_una_URL_escrita(self):
        from pathlib import Path

        fuente = Path(spliceai.__file__).read_text(encoding="utf-8")
        codigo = "\n".join(
            l for l in fuente.splitlines()
            if not l.strip().startswith("#") and "http" in l
        )
        self.assertEqual(codigo, "", f"hay URLs en el código:\n{codigo}")


# ─────────── validacion al subir: por md5, y rechaza ───────────


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del raton")
class TestLaValidacionDelResultado(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.seleccion = _panel(2)
        cls.construcciones = spliceai.build_constructions(
            cls.seleccion, intron_names=("mvm_actual",),
            scaffold=SGEP_SCAFFOLD,
        )

    def _tsv(self, construcciones=None, md5=None):
        cs = construcciones or self.construcciones
        filas = [spliceai.RESULT_HEADER]
        for c in cs:
            filas.append(
                "\t".join([c.name, md5 or c.md5, "1", "donante", "0.90"])
            )
        return "\n".join(filas) + "\n"

    def test_un_resultado_de_LA_MISMA_corrida_entra(self):
        sitios = spliceai.parse_result(self._tsv(), constructions=self.construcciones)
        self.assertEqual(len(sitios), len(self.construcciones))

    def test_un_md5_QUE_NO_CUADRA_se_rechaza(self):
        with self.assertRaises(ShmirDesignError) as caja:
            spliceai.parse_result(
                self._tsv(md5="0" * 32), constructions=self.construcciones
            )
        self.assertIn("md5", str(caja.exception).lower())

    def test_y_el_motivo_nombra_el_fallo_del_CSV_de_miRarchitect(self):
        with self.assertRaises(ShmirDesignError) as caja:
            spliceai.parse_result(
                self._tsv(md5="0" * 32), constructions=self.construcciones
            )
        self.assertIn("otra corrida", str(caja.exception).lower())

    def test_una_construccion_QUE_NO_ES_DEL_PANEL_se_rechaza(self):
        texto = (
            spliceai.RESULT_HEADER + "\n"
            + "\t".join(["inventada", "0" * 32, "1", "donante", "0.9"]) + "\n"
        )
        with self.assertRaises(ShmirDesignError):
            spliceai.parse_result(texto, constructions=self.construcciones)

    def test_un_resultado_VACIO_aborta(self):
        """Cero sitios y «no llego a correr» son cosas distintas."""
        with self.assertRaises(ShmirDesignError) as caja:
            spliceai.parse_result(
                spliceai.RESULT_HEADER + "\n", constructions=self.construcciones
            )
        self.assertIn("no distingue", str(caja.exception).lower())

    def test_un_tipo_desconocido_aborta(self):
        texto = (
            spliceai.RESULT_HEADER + "\n"
            + "\t".join([
                self.construcciones[0].name, self.construcciones[0].md5,
                "1", "loquesea", "0.9",
            ]) + "\n"
        )
        with self.assertRaises(ShmirDesignError):
            spliceai.parse_result(texto, constructions=self.construcciones)


if __name__ == "__main__":
    unittest.main()


# ─────────── D. que se reporta ───────────


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del raton")
class TestElResultado(unittest.TestCase):
    """Las puntuaciones de este test son INVENTADAS y eso esta bien: son la salida de un
    modelo externo, no una secuencia biologica. Lo que se prueba es la ARITMETICA de la
    comparacion relativa, que es nuestra."""

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.seleccion = _panel(3)
        cls.construcciones = spliceai.build_constructions(
            cls.seleccion, intron_names=("mvm_actual",),
            scaffold=SGEP_SCAFFOLD,
        )

    def _puntuar(self, extra=None):
        """Un resultado con el legitimo alto y, si se pide, cripticos añadidos."""
        filas = [spliceai.RESULT_HEADER]
        for c in self.construcciones:
            filas.append("\t".join([c.name, c.md5, str(c.donor_position), "donante", "0.95"]))
            filas.append("\t".join([c.name, c.md5, str(c.acceptor_position), "aceptor", "0.90"]))
            filas.append("\t".join([c.name, c.md5, str(c.cryptic_position), "donante", "0.30"]))
            for pos, tipo, valor in (extra or {}).get(c.name, ()):
                filas.append("\t".join([c.name, c.md5, str(pos), tipo, str(valor)]))
        return spliceai.scan_from_result(
            "\n".join(filas) + "\n", constructions=self.construcciones
        )

    def test_sale_una_fila_POR_PAR_candidato_x_intron(self):
        scan = self._puntuar()
        self.assertEqual(len(scan.pairs), 3)

    def test_cada_par_trae_el_LEGITIMO_de_los_dos_tipos(self):
        par = self._puntuar().pairs[0]
        self.assertAlmostEqual(par.legit_donor, 0.95)
        self.assertAlmostEqual(par.legit_acceptor, 0.90)

    def test_el_criptico_sale_como_FRACCION_del_legitimo(self):
        par = self._puntuar().pairs[0]
        self.assertAlmostEqual(par.best_cryptic.fraction, 0.30 / 0.95, places=4)

    def test_y_con_su_POSICION_y_su_TIPO(self):
        par = self._puntuar().pairs[0]
        self.assertGreater(par.best_cryptic.position, 0)
        self.assertIn(par.best_cryptic.kind, ("donante", "aceptor"))

    def test_el_GTGAGCG_sale_POR_SU_NOMBRE_aunque_no_sea_el_mejor(self):
        """Es el criptico conocido y el motivo por el que existe este modal."""
        scan = self._puntuar(extra={
            c.name: ((c.cryptic_position + 40, "donante", 0.80),)
            for c in self.construcciones
        })
        par = scan.pairs[0]
        self.assertIsNotNone(par.known_cryptic)
        self.assertAlmostEqual(par.known_cryptic.score, 0.30)
        # Y el MEJOR es otro, para que se vea que son cosas distintas.
        self.assertAlmostEqual(par.best_cryptic.score, 0.80)

    def test_y_se_dice_QUE_motivo_es(self):
        par = self._puntuar().pairs[0]
        self.assertIn("GTGAGCG", par.known_cryptic.note)

    def test_solo_salen_los_cripticos_por_encima_del_umbral_RELATIVO_declarado(self):
        scan = self._puntuar(extra={
            c.name: ((c.cryptic_position + 40, "donante", 0.001),)
            for c in self.construcciones
        })
        posiciones = [s.position for s in scan.pairs[0].cryptics]
        self.assertNotIn(self.construcciones[0].cryptic_position + 40, posiciones)

    def test_el_umbral_relativo_va_DECLARADO_no_citado(self):
        self.assertIn("declarado", spliceai.RELATIVE_THRESHOLD_NOTE.lower())
        self.assertGreater(spliceai.RELATIVE_THRESHOLD, 0)

    def test_un_legitimo_de_CERO_aborta_en_vez_de_dividir(self):
        """Sin referente no hay comparacion relativa, que es lo unico que vale aqui."""
        filas = [spliceai.RESULT_HEADER]
        c = self.construcciones[0]
        filas.append("\t".join([c.name, c.md5, str(c.donor_position), "donante", "0.0"]))
        filas.append("\t".join([c.name, c.md5, str(c.acceptor_position), "aceptor", "0.9"]))
        with self.assertRaises(ShmirDesignError) as caja:
            spliceai.scan_from_result(
                "\n".join(filas) + "\n", constructions=(c,)
            )
        self.assertIn("referente", str(caja.exception).lower())


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del raton")
class TestLaColumnaCOMPARATIVA(unittest.TestCase):
    """Lo accionable: que guias introducen cripticos que las otras no.

    Si nueve dan un perfil limpio y una no, esa se cambia. Es una comparacion ENTRE
    construcciones, no un umbral absoluto.
    """

    @classmethod
    def setUpClass(cls):
        cls.utr3, cls.seleccion = _panel(3)
        cls.construcciones = spliceai.build_constructions(
            cls.seleccion, intron_names=("mvm_actual",),
            scaffold=SGEP_SCAFFOLD,
        )

    def _scan(self, propios):
        filas = [spliceai.RESULT_HEADER]
        for c in self.construcciones:
            filas.append("\t".join([c.name, c.md5, str(c.donor_position), "donante", "1.0"]))
            filas.append("\t".join([c.name, c.md5, str(c.acceptor_position), "aceptor", "1.0"]))
            for pos, valor in propios.get(c.name, ()):
                filas.append("\t".join([c.name, c.md5, str(pos), "donante", str(valor)]))
        return spliceai.scan_from_result(
            "\n".join(filas) + "\n", constructions=self.construcciones
        )

    def test_si_TODAS_comparten_los_mismos_cripticos_ninguna_es_exclusiva(self):
        comun = 200
        scan = self._scan({c.name: ((comun, 0.5),) for c in self.construcciones})
        filas = spliceai.exclusive_rows(scan)
        self.assertTrue(all(not f["exclusivos"] for f in filas))

    def test_pero_si_UNA_trae_uno_propio_SALE_señalada(self):
        rara = self.construcciones[0]
        propios = {c.name: ((200, 0.5),) for c in self.construcciones}
        propios[rara.name] = ((200, 0.5), (240, 0.7))
        filas = {f["construccion"]: f for f in spliceai.exclusive_rows(self._scan(propios))}
        self.assertTrue(filas[rara.name]["exclusivos"])
        for otra in self.construcciones[1:]:
            self.assertFalse(filas[otra.name]["exclusivos"])

    def test_y_eso_es_lo_ACCIONABLE_y_va_escrito(self):
        self.assertIn("cambia", spliceai.WHAT_IS_ACTIONABLE.lower())

    def test_la_comparacion_es_ENTRE_construcciones_no_contra_un_umbral(self):
        self.assertIn("entre construcciones", spliceai.WHAT_IS_ACTIONABLE.lower())


# ─────────── F. uso: nunca puede excluir a nadie ───────────


@unittest.skipUnless(HAY, "NOT_RUN: falta el fixture del raton")
class TestElVeredictoNO_PUEDE_SER_FAIL(unittest.TestCase):

    def test_solo_NOT_RUN_o_PASS(self):
        from shmir_design.splice_store import SpliceStore

        self.assertEqual(
            set(SpliceStore.POSSIBLE_VERDICTS), {FilterState.NOT_RUN, FilterState.PASS}
        )

    def test_sin_corrida_es_NOT_RUN(self):
        from shmir_design.splice_store import SpliceStore

        self.assertIs(SpliceStore().verdict_for(3, "mvm_actual").state, FilterState.NOT_RUN)

    def test_y_NO_existe_un_verdict_que_devuelva_FAIL(self):
        from pathlib import Path

        from shmir_design import splice_store

        fuente = Path(splice_store.__file__).read_text(encoding="utf-8")
        cuerpo = fuente.split("def verdict_for")[1].split("\n    def ")[0]
        # `FilterState.FAIL`, no la palabra: el docstring dice «nunca FAIL» a proposito.
        self.assertNotIn("FilterState.FAIL", cuerpo)
        # Y en TODO el modulo tampoco hay ninguno.
        self.assertNotIn("FilterState.FAIL", fuente)
