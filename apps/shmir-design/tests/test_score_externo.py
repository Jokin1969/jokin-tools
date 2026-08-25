"""Tests de la columna `score_externo` y de las features de SplashRNA.

Regla 5: escritos antes que `shmir_design/external_score.py`.

Lo que este modulo NO hace es tan importante como lo que hace. No hay clasificador
propio, no hay modelo entrenado con numeros sacados de la literatura y no hay ningun
numero calculado aqui viajando con la etiqueta de miRarchitect o de SplashRNA. Si nadie
ha dado un score, la columna va VACIA — que es lo que dice la regla 3 sobre no confundir
"no se midio" con un valor.

La guia de referencia es la de SGEP (TAGATAAGCATTATAATTCCTA), validada empiricamente y
ya presente en el proyecto: no se fabrica ninguna secuencia para estos tests (regla 1).
"""

import unittest
from pathlib import Path

from shmir_design.errors import ShmirDesignError
from shmir_design.external_score import (
    FEATURE_COLUMNS,
    MIRARCHITECT_API,
    SPLASHRNA_API,
    MANUAL_URL,
    SCORE_COLUMNS,
    VERIFICACION,
    ExternalScore,
    ScoreSource,
    manual_instructions,
    merge_scores,
    splashrna_features,
)

#: Guia de SGEP en notacion ARN, la misma que usa el resto del proyecto.
SGEP_GUIDE = "UAGAUAAGCAUUAUAAUUCCUA"


class TestFuentes(unittest.TestCase):

    def test_las_cuatro_fuentes_y_ninguna_mas(self):
        self.assertEqual(
            {f.value for f in ScoreSource},
            {"mirarchitect_api", "splashrna_api", "splashrna_features",
             "manual_mirarchitect"},
        )


class TestColumnaVacia(unittest.TestCase):

    def test_sin_score_las_dos_columnas_van_vacias(self):
        columnas = ExternalScore().as_columns()
        self.assertEqual(columnas["score_externo"], "")
        self.assertEqual(columnas["fuente_score"], "")

    def test_sin_score_no_va_a_cero(self):
        # Cero es un score malo; vacio es "nadie lo ha puntuado". Confundirlos es
        # exactamente lo que prohibe la regla 3.
        self.assertNotEqual(ExternalScore().as_columns()["score_externo"], "0")

    def test_un_score_importado_a_mano_dice_de_donde_vino(self):
        columnas = ExternalScore(
            value=0.87, source=ScoreSource.MANUAL_MIRARCHITECT
        ).as_columns()
        self.assertEqual(columnas["score_externo"], "0.870")
        self.assertEqual(columnas["fuente_score"], "manual_mirarchitect")

    def test_un_valor_sin_fuente_es_un_error(self):
        # Un numero sin procedencia no es auditable: de donde salio es parte del dato.
        with self.assertRaises(ShmirDesignError):
            ExternalScore(value=0.87)

    def test_una_fuente_sin_valor_tambien_es_un_error(self):
        with self.assertRaises(ShmirDesignError):
            ExternalScore(source=ScoreSource.MANUAL_MIRARCHITECT)

    def test_las_dos_columnas_estan_declaradas(self):
        self.assertEqual(SCORE_COLUMNS, ("score_externo", "fuente_score"))


class TestNuncaEsVeredicto(unittest.TestCase):

    def test_el_modulo_no_conoce_los_estados_de_los_filtros(self):
        # Sobre el FUENTE, como el test de orf.py: si el modulo no importa FilterState
        # no puede convertir un score en un PASS ni en un FAIL por accidente.
        fuente = (
            Path(__file__).resolve().parent.parent
            / "shmir_design" / "external_score.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("FilterState", fuente)
        self.assertNotIn("FilterResult", fuente)

    def test_ninguna_columna_devuelve_pass_ni_fail(self):
        columnas = {
            **ExternalScore().as_columns(),
            **ExternalScore(0.9, ScoreSource.MANUAL_MIRARCHITECT).as_columns(),
            **splashrna_features(SGEP_GUIDE),
        }
        for clave, valor in columnas.items():
            with self.subTest(clave):
                self.assertNotIn(valor, ("PASS", "FAIL", "NOT_RUN", "NO_APLICA"))


class TestFeatures(unittest.TestCase):

    def test_las_features_son_columnas_separadas_no_un_score(self):
        features = splashrna_features(SGEP_GUIDE)
        self.assertEqual(tuple(features), FEATURE_COLUMNS)
        self.assertNotIn("score_externo", features)

    def test_asimetria(self):
        self.assertEqual(splashrna_features(SGEP_GUIDE)["feat_asimetria"], "+1.36")

    def test_gc_de_la_guia(self):
        self.assertEqual(splashrna_features(SGEP_GUIDE)["feat_GC_guia"], "0.227")

    def test_posicion_1(self):
        self.assertEqual(splashrna_features(SGEP_GUIDE)["feat_pos1"], "U")

    def test_posiciones_2_a_7(self):
        features = splashrna_features(SGEP_GUIDE)
        self.assertEqual(
            [features[f"feat_pos{i}"] for i in range(2, 8)],
            ["A", "G", "A", "U", "A", "A"],
        )

    def test_composicion_del_seed(self):
        features = splashrna_features(SGEP_GUIDE)
        self.assertEqual(features["feat_seed"], "AGAUAAG")
        self.assertEqual(features["feat_GC_seed"], "0.286")
        self.assertEqual(features["feat_AU_seed"], "0.714")

    def test_gc_del_bucle_sale_del_andamio(self):
        # Con el andamio miR-E fijo esta columna es constante, y eso es un hecho del
        # diseño, no un descuido: cambia si cambia el andamio.
        self.assertEqual(splashrna_features(SGEP_GUIDE)["feat_GC_bucle"], "0.421")

    def test_una_guia_corta_aborta_en_vez_de_rellenar(self):
        with self.assertRaises(ShmirDesignError):
            splashrna_features(SGEP_GUIDE[:7])

    def test_acepta_la_guia_en_notacion_ADN_y_responde_en_ARN(self):
        self.assertEqual(
            splashrna_features("TAGATAAGCATTATAATTCCTA"),
            splashrna_features(SGEP_GUIDE),
        )


class TestInstruccionesManuales(unittest.TestCase):

    def texto(self):
        return manual_instructions([SGEP_GUIDE])

    def test_dice_que_el_endpoint_no_se_ha_podido_comprobar_y_cuando(self):
        # No es lo mismo "no existe" que "no he podido comprobarlo", y la diferencia
        # importa: el proxy de este entorno devuelve 403 a todo.
        texto = self.texto()
        self.assertIn("no se ha podido comprobar", texto)
        self.assertIn(VERIFICACION, texto)

    def test_da_la_url_para_pegarla_a_mano(self):
        self.assertIn(MANUAL_URL, self.texto())

    def test_dice_que_pegar(self):
        texto = self.texto()
        self.assertIn(SGEP_GUIDE.replace("U", "T"), texto)
        self.assertIn("miR-E", texto)

    def test_da_el_comando_de_importacion_entero(self):
        self.assertIn(
            "tools/import_scores.py --fuente mirarchitect --tsv resultados.tsv",
            self.texto(),
        )

    def test_una_guia_repetida_se_lista_una_sola_vez(self):
        # Dos candidatos pueden compartir guia (un 3'UTR con repeticiones), y pegar la
        # misma secuencia dos veces en el formulario es tiempo de alguien.
        texto = manual_instructions([SGEP_GUIDE, SGEP_GUIDE])
        self.assertEqual(texto.count(SGEP_GUIDE.replace("U", "T")), 1)

    def test_sin_guias_no_aparece_ninguna_secuencia(self):
        # Sin candidatos las instrucciones siguen sirviendo, pero no puede colarse una
        # linea que parezca una guia: eso seria fabricar secuencia (regla 1).
        texto = manual_instructions([])
        self.assertNotIn("Guias que hay que pegar", texto)
        parecen_secuencia = [
            linea for linea in texto.splitlines()
            if linea.strip() and set(linea.strip()) <= set("ACGTU")
        ]
        self.assertEqual(parecen_secuencia, [])


class TestPlausibilidad(unittest.TestCase):
    """La comprobacion que pidio el usuario: si alguna API funciona, la guia de SGEP
    tiene que salir en el cuartil superior del rango.

    Hoy no hay ninguna API contra la que correrla —el proxy de este entorno rechaza
    toda conexion saliente con 403— asi que el test se SALTA de forma visible en vez de
    aprobar en silencio. El dia que haya endpoint, cambia una constante y corre.
    """

    def test_ninguna_api_esta_cableada_como_verificada(self):
        from shmir_design import external_score

        self.assertIsNone(external_score.MIRARCHITECT_API)
        self.assertIsNone(external_score.SPLASHRNA_API)

    @unittest.skipUnless(
        MIRARCHITECT_API or SPLASHRNA_API,
        "NOT_RUN: no hay ninguna API verificada contra la que correr la comprobacion "
        "de plausibilidad (403 del proxy, ver external_score.VERIFICACION)",
    )
    def test_la_guia_de_SGEP_sale_en_el_cuartil_superior(self):
        # SGEP esta validada empiricamente: si un endpoint la puntua en el cuartil
        # INFERIOR, no esta devolviendo lo que parece o los parametros van mal. Se
        # aborta y se documenta, no se acepta el numero.
        raise AssertionError(
            "hay un endpoint declarado en external_score pero nadie ha escrito la "
            "llamada ni la escala del score; no se aprueba en silencio"
        )


if __name__ == "__main__":
    unittest.main()


TABLA = (
    "# comentario que hay que conservar\n"
    "guia\tveredicto\tscore_externo\tfuente_score\tknockdown_medido\n"
    f"{SGEP_GUIDE}\tINCOMPLETE\t\t\t\n"
    "UAGAUAAGCAUUAUAAUUCCUG\tINCOMPLETE\t\t\t\n"
)


class TestMergeScores(unittest.TestCase):
    """Importar scores puntuados a mano dentro de la tabla comparativa.

    Se aborta ante cualquier cosa que huela a fichero equivocado: una guia que no esta
    en la tabla, un score que no es un numero, una guia repetida. Meter un score en la
    fila de otro candidato seria peor que no tener score.
    """

    def test_rellena_la_fila_de_su_guia(self):
        resultado = merge_scores(
            TABLA, f"{SGEP_GUIDE}\t0.91\n", source=ScoreSource.MANUAL_MIRARCHITECT
        )
        filas = [l.split("\t") for l in resultado.text.splitlines() if not l.startswith("#")]
        cabecera = filas[0]
        fila = next(f for f in filas[1:] if f[cabecera.index("guia")] == SGEP_GUIDE)
        self.assertEqual(fila[cabecera.index("score_externo")], "0.910")
        self.assertEqual(fila[cabecera.index("fuente_score")], "manual_mirarchitect")

    def test_las_guias_sin_score_siguen_vacias(self):
        resultado = merge_scores(
            TABLA, f"{SGEP_GUIDE}\t0.91\n", source=ScoreSource.MANUAL_MIRARCHITECT
        )
        filas = [l.split("\t") for l in resultado.text.splitlines() if not l.startswith("#")]
        otra = next(f for f in filas[1:] if f[0] != SGEP_GUIDE)
        self.assertEqual(otra[filas[0].index("score_externo")], "")
        self.assertEqual(otra[filas[0].index("fuente_score")], "")

    def test_dice_cuantas_relleno_y_cuantas_no(self):
        resultado = merge_scores(
            TABLA, f"{SGEP_GUIDE}\t0.91\n", source=ScoreSource.MANUAL_MIRARCHITECT
        )
        self.assertEqual(resultado.filled, (SGEP_GUIDE,))
        self.assertEqual(len(resultado.untouched), 1)
        self.assertIn("1 de 2", resultado.format_text())

    def test_conserva_los_comentarios_de_la_tabla(self):
        resultado = merge_scores(
            TABLA, f"{SGEP_GUIDE}\t0.91\n", source=ScoreSource.MANUAL_MIRARCHITECT
        )
        self.assertIn("# comentario que hay que conservar", resultado.text)

    def test_acepta_la_guia_del_formulario_en_ADN(self):
        resultado = merge_scores(
            TABLA,
            f"{SGEP_GUIDE.replace('U', 'T')}\t0.91\n",
            source=ScoreSource.MANUAL_MIRARCHITECT,
        )
        self.assertEqual(resultado.filled, (SGEP_GUIDE,))

    def test_salta_la_cabecera_del_fichero_de_resultados(self):
        resultado = merge_scores(
            TABLA, f"guia\tscore\n{SGEP_GUIDE}\t0.91\n",
            source=ScoreSource.MANUAL_MIRARCHITECT,
        )
        self.assertEqual(resultado.filled, (SGEP_GUIDE,))

    def test_una_guia_que_no_esta_en_la_tabla_aborta(self):
        # Un score para una guia que nadie diseño significa que el fichero no es de
        # esta corrida. Meterlo igual seria pegar numeros a ciegas.
        with self.assertRaises(ShmirDesignError) as caja:
            merge_scores(
                TABLA, "UAAAAAAAAAAAAAAAAAAAAA\t0.5\n",
                source=ScoreSource.MANUAL_MIRARCHITECT,
            )
        self.assertIn("UAAAAAAAAAAAAAAAAAAAAA", str(caja.exception))

    def test_un_score_que_no_es_un_numero_aborta(self):
        with self.assertRaises(ShmirDesignError) as caja:
            merge_scores(
                TABLA, f"{SGEP_GUIDE}\talto\n", source=ScoreSource.MANUAL_MIRARCHITECT
            )
        self.assertIn("alto", str(caja.exception))

    def test_una_guia_repetida_aborta(self):
        with self.assertRaises(ShmirDesignError):
            merge_scores(
                TABLA, f"{SGEP_GUIDE}\t0.9\n{SGEP_GUIDE}\t0.4\n",
                source=ScoreSource.MANUAL_MIRARCHITECT,
            )

    def test_una_tabla_sin_las_columnas_del_score_aborta(self):
        with self.assertRaises(ShmirDesignError) as caja:
            merge_scores(
                "guia\tveredicto\nUAGAUAAGCAUUAUAAUUCCUA\tPASS\n",
                f"{SGEP_GUIDE}\t0.9\n",
                source=ScoreSource.MANUAL_MIRARCHITECT,
            )
        self.assertIn("score_externo", str(caja.exception))

    def test_un_fichero_de_resultados_vacio_aborta(self):
        # Importar nada y decir que fue bien es el peor resultado posible: el usuario
        # se quedaria creyendo que la tabla lleva scores.
        with self.assertRaises(ShmirDesignError):
            merge_scores(TABLA, "", source=ScoreSource.MANUAL_MIRARCHITECT)

    def test_una_linea_con_una_sola_columna_aborta(self):
        with self.assertRaises(ShmirDesignError):
            merge_scores(
                TABLA, f"{SGEP_GUIDE}\n", source=ScoreSource.MANUAL_MIRARCHITECT
            )

    def test_no_toca_ninguna_otra_columna(self):
        resultado = merge_scores(
            TABLA, f"{SGEP_GUIDE}\t0.91\n", source=ScoreSource.MANUAL_MIRARCHITECT
        )
        original = [l.split("\t") for l in TABLA.splitlines() if not l.startswith("#")]
        nuevas = [l.split("\t") for l in resultado.text.splitlines() if not l.startswith("#")]
        for antes, despues in zip(original, nuevas):
            self.assertEqual(antes[:2], despues[:2])
            self.assertEqual(antes[4], despues[4])
