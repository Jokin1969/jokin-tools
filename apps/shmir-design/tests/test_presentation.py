"""Tests de las funciones que alimentan la interfaz.

Regla 5: escritos antes que `shmir_design/presentation.py`.

La UI no puede tener logica: todo lo que decide algo —el semaforo, las filas de la
tabla, el mapa— vive aqui y se prueba aqui, sin Streamlit de por medio.
"""

import unittest

from shmir_design.anatomy import Anatomy, RegionSource
from shmir_design.conservation import Utr3, build_conservation_report
from shmir_design.masking import RepeatMask
from shmir_design.polya import POLYA_COLUMNS
from shmir_design.presentation import (
    anatomy_rows,
    candidate_rows,
    map_svg,
    output_bundle,
    status_light,
    window_rows,
)
from shmir_design.reference import REFERENCES
from shmir_design.scaffold import SGEP_SCAFFOLD
from shmir_design.mirna import AbundanceList, parse_mature_fa
from shmir_design.seeds import BOOTSTRAP_SEEDS
from shmir_design.specificity import SpecificityDatabase
from shmir_design.selection import SelectionConfig, select_from_report
from shmir_design.tiling import tile_utr

SONDA = "GCGTCAGTACGATCGAATTACT" * 30
BLOQUE = "TTTTCTATATTTGTAACTTTGCATGT"


def piezas(seeds=None, mask=None, specificity=False, transgene=False, mirna=False):
    """`specificity=True` carga una base minima donde la unica diana es la sonda.

    `transgene=True` carga un casete de prueba SIN ningun sitio de la sonda: es lo que
    pasa con los candidatos del 3'UTR contra el casete real, que no lleva ni una base
    del 3'UTR nativo.
    """
    base = (
        SpecificityDatabase(
            name="base de prueba",
            version="2026-08-25",
            checksum="0" * 32,
            records={"diana": SONDA},
        )
        if specificity
        else None
    )
    casete = (
        SpecificityDatabase(
            name="casete de prueba",
            version="2026-08-25",
            checksum="0" * 32,
            records={"casete": "GGCCATACTAGCATCGGATCAG" * 8},
        )
        if transgene
        else None
    )
    maduros = (
        parse_mature_fa(
            ">mmu-sonda-1 sonda de mecanismo\nUCCCCCCCGCGGGGGGGGGGGG\n",
            source="sonda", version="sonda", checksum="0" * 32,
        )
        if mirna
        else None
    )
    abundantes = (
        AbundanceList(
            names=frozenset({"mmu-sonda-1"}),
            source="sonda", version="sonda", checksum="0" * 32,
        )
        if mirna
        else None
    )
    tiling = tile_utr(
        SONDA,
        seeds=seeds,
        mask=mask,
        mature=maduros,
        abundance=abundantes,
        specificity_db=base,
        specificity_target="diana" if base else None,
        transgene_db=casete,
    )
    return tiling, select_from_report(tiling, SelectionConfig(n_candidates=3))


class TestSemaforo(unittest.TestCase):
    """El semaforo mira los CANDIDATOS SELECCIONADOS, que son los que se pedirian.

    Mirar todas las ventanas dejaria el verde inalcanzable en cuanto se enmascara algo:
    una ventana con N nunca se evalua, y eso no significa que un filtro no haya corrido.
    Lo que importa es si lo que vas a encargar esta filtrado del todo.
    """

    def test_ambar_si_algun_filtro_quedo_en_not_run(self):
        _, seleccion = piezas()
        luz = status_light(seleccion)
        self.assertEqual(luz.color, "ambar")
        self.assertIn("seed", luz.pending)
        self.assertIn("repeticiones", luz.pending)

    def test_el_ambar_dice_cuales_faltan_en_el_titular(self):
        _, seleccion = piezas()
        luz = status_light(seleccion)
        self.assertIn("seed", luz.headline + luz.detail)
        self.assertIn("repeticiones", luz.headline + luz.detail)

    def test_verde_solo_si_corrieron_todos(self):
        mask = RepeatMask(intervals=((1, 5),), source="prueba")
        _, seleccion = piezas(
            seeds=BOOTSTRAP_SEEDS, mask=mask, specificity=True,
            transgene=True, mirna=True,
        )
        luz = status_light(seleccion)
        self.assertEqual(luz.color, "verde")
        self.assertEqual(luz.pending, ())

    def test_el_ambar_recuerda_que_not_run_no_es_pass(self):
        _, seleccion = piezas()
        self.assertIn("NOT_RUN", status_light(seleccion).detail)

    def test_las_ventanas_descartadas_se_cuentan_aparte_del_semaforo(self):
        """Que una ventana no sea candidata no es que falte un filtro por correr.

        El texto DECIA «no evaluables (bases desconocidas o enmascaradas)» y contaba
        otra cosa: las que no pasan los filtros biofísicos. Sobre la corrida real eran
        1763, y ni una tenía una N ni estaba enmascarada — fallaban GC y homopolímero.
        Afirmar una causa que no se ha comprobado es el fallo del «comprueba que
        Streamlit está instalado» y el del «Alu 0 %» obtenido sin buscar Alu.
        """
        mask = RepeatMask(intervals=((1, 5),), source="prueba")
        _, seleccion = piezas(
            seeds=BOOTSTRAP_SEEDS, mask=mask, specificity=True,
            transgene=True, mirna=True,
        )
        luz = status_light(seleccion)
        self.assertEqual(luz.color, "verde")
        # El número va CON su total: un descartado sin total no se puede leer.
        self.assertIn(f"{luz.tiled} ventanas tiladas", luz.detail)
        self.assertIn("filtros biofísicos", luz.detail)
        self.assertNotIn("bases desconocidas", luz.detail)

    def test_sin_candidatos_no_hay_verde(self):
        tiling = tile_utr("N" * 200)
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=3))
        luz = status_light(seleccion)
        self.assertEqual(luz.color, "ambar")
        self.assertIn("ningún candidato", luz.headline.lower())


class TestFilasDeTabla(unittest.TestCase):

    def test_una_fila_por_candidato_con_una_columna_por_filtro(self):
        _, seleccion = piezas()
        filas = candidate_rows(seleccion)
        self.assertEqual(len(filas), len(seleccion.selection.chosen))
        for filtro in ("GC", "homopolimero", "asimetria", "G4_diana", "G4_guia",
                       "zona_prohibida_polyA", "repeticiones", "seed"):
            with self.subTest(filtro):
                self.assertIn(filtro, filas[0])

    def test_la_fila_lleva_posicion_tercio_veredicto_y_secuencias(self):
        _, seleccion = piezas()
        fila = candidate_rows(seleccion)[0]
        for columna in ("rango", "inicio", "fin", "region", "inicio_3utr", "tercio",
                        "asimetria", "diana", "guia", "veredicto"):
            with self.subTest(columna):
                self.assertIn(columna, fila)

    def test_el_valor_de_la_asimetria_no_lo_pisa_el_estado_del_filtro(self):
        """El filtro se llama 'asimetria' y el numero tambien se llamaba asi: uno
        machacaba al otro y la tabla perdia el valor. Son dos columnas distintas."""
        _, seleccion = piezas()
        fila = candidate_rows(seleccion)[0]
        self.assertIn(fila["asimetria"], ("PASS", "FAIL", "NOT_RUN"))
        self.assertIsInstance(fila["asimetria_kcal"], float)
        elegido = seleccion.selection.chosen[0]
        self.assertAlmostEqual(fila["asimetria_kcal"], round(elegido.asymmetry, 2))

    def test_cada_filtro_tiene_su_columna_con_su_estado(self):
        _, seleccion = piezas()
        elegido = seleccion.selection.chosen[0]
        ventana = seleccion.window_of(elegido)
        fila = candidate_rows(seleccion)[0]
        for resultado in ventana.filters:
            with self.subTest(resultado.name):
                self.assertEqual(fila[resultado.name], resultado.state.value)

    def test_ninguna_columna_de_filtro_pisa_a_otra_columna(self):
        """Guardia contra futuras colisiones de nombres al fusionar diccionarios."""
        tiling, seleccion = piezas()
        nombres_filtro = {r.name for r in tiling.windows[0].filters}
        otras = {"rango", "inicio", "fin", "region", "inicio_3utr", "fin_3utr",
                 "tercio", "asimetria_kcal", "bandera_polyA_debil",
                 "biofisicos_ok", "riesgo_APA", "veredicto", "diana", "guia",
                 "carga_seed", "accesibilidad", *POLYA_COLUMNS}
        self.assertEqual(nombres_filtro & otras, set())
        self.assertEqual(
            len(candidate_rows(seleccion)[0]), len(nombres_filtro) + len(otras)
        )

    def test_los_estados_son_texto_no_booleanos(self):
        _, seleccion = piezas()
        self.assertIn(candidate_rows(seleccion)[0]["seed"], ("PASS", "FAIL", "NOT_RUN"))

    def test_todas_las_ventanas_caben_en_window_rows(self):
        tiling, _ = piezas()
        self.assertEqual(len(window_rows(tiling)), len(tiling.windows))

    def test_window_rows_tambien_separa_valor_y_estado_de_la_asimetria(self):
        tiling, _ = piezas()
        fila = window_rows(tiling)[0]
        self.assertIn(fila["asimetria"], ("PASS", "FAIL", "NOT_RUN"))
        self.assertIsInstance(fila["asimetria_kcal"], float)


class TestAnatomia(unittest.TestCase):

    def test_con_transcrito_verificado_da_los_tres_tramos(self):
        filas = anatomy_rows(REFERENCES["NM_011170.3"])
        tramos = {f["tramo"] for f in filas}
        self.assertEqual(tramos, {"5'UTR", "CDS", "3'UTR"})
        utr3 = next(f for f in filas if f["tramo"] == "3'UTR")
        self.assertEqual(utr3["longitud"], 1242)
        self.assertEqual(utr3["origen"], "verificado")

    def test_sin_transcrito_lo_dice_en_vez_de_adivinar(self):
        filas = anatomy_rows(None, utr3_length=660)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["tramo"], "3'UTR")
        self.assertIn("declarad", filas[0]["origen"])


class TestMapa(unittest.TestCase):

    def test_es_un_svg(self):
        tiling, seleccion = piezas()
        svg = map_svg(tiling, seleccion)
        self.assertTrue(svg.strip().startswith("<svg"))
        self.assertTrue(svg.strip().endswith("</svg>"))

    def test_marca_cada_candidato_CON_SU_MARCO(self):
        # La posición va etiquetada, como en cualquier otra salida: el mapa RECIBE el
        # marco de la anatomía (`report.frame`) en vez de suponer `3utr`. Aquí lo tilado
        # ES el 3'UTR, así que el marco es `3utr` — y se dice, no se calla.
        tiling, seleccion = piezas()
        svg = map_svg(tiling, seleccion)
        for choice in seleccion.selection.chosen:
            with self.subTest(choice.start):
                self.assertIn(f'data-candidato="3utr:{choice.start}"', svg)

    def test_marca_las_señales_de_poliadenilacion(self):
        secuencia = "ACGT" * 20 + "AATAAA" + "ACGT" * 20
        tiling = tile_utr(secuencia)
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=1))
        svg = map_svg(tiling, seleccion)
        self.assertIn('data-senal="3utr:81"', svg)

    def test_marca_las_zonas_enmascaradas(self):
        mask = RepeatMask(intervals=((100, 200),), source="prueba")
        tiling, seleccion = piezas(mask=mask)
        svg = map_svg(tiling, seleccion)
        self.assertIn('data-mascara="3utr:100-200"', svg)

    def test_marca_los_bloques_conservados(self):
        tiling, seleccion = piezas()
        conservacion = build_conservation_report(
            Utr3("a", "N" * 100 + BLOQUE + "N" * 100),
            Utr3("b", "N" * 50 + BLOQUE + "N" * 150),
        )
        svg = map_svg(tiling, seleccion, conservation=conservacion, species="a")
        self.assertIn("data-bloque=", svg)

    def test_sin_bloques_no_falla(self):
        tiling, seleccion = piezas()
        self.assertIn("<svg", map_svg(tiling, seleccion, conservation=None))

    def test_las_coordenadas_no_se_salen_del_lienzo(self):
        tiling, seleccion = piezas()
        svg = map_svg(tiling, seleccion)
        self.assertNotIn("x=\"-", svg)


class TestDescargas(unittest.TestCase):

    def test_el_paquete_trae_las_seis_salidas(self):
        """La UI tiene que entregar lo MISMO que el CLI, no un subconjunto."""
        tiling, seleccion = piezas()
        bundle = output_bundle(
            species="sonda",
            tiling=tiling,
            selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
        )
        self.assertEqual(
            sorted(bundle),
            [
                "sonda_comparativa.tsv",
                "sonda_guias.fasta",
                "sonda_informe.txt",
                "sonda_oligos.tsv",
                "sonda_seleccionados.tsv",
                "sonda_ventanas.tsv",
            ],
        )

    def test_con_bloques_se_añaden_las_tres_salidas_de_pedido(self):
        tiling, seleccion = piezas()
        bundle = output_bundle(
            species="sonda",
            tiling=tiling,
            selection=seleccion,
            scaffold=SGEP_SCAFFOLD,
            blocks=True,
        )
        for nombre in (
            "sonda_bloques.fasta", "sonda_bloques.tsv", "sonda_hoja_de_pedido.txt"
        ):
            self.assertIn(nombre, bundle)

    def test_las_filas_de_bloque_llevan_una_columna_por_comprobacion(self):
        from shmir_design.presentation import block_rows

        _, seleccion = piezas()
        filas = block_rows(seleccion, SGEP_SCAFFOLD)
        self.assertTrue(filas)
        for nombre in ("longitudes", "sitios_unicos", "plegado_en_intron"):
            self.assertIn(f"check:{nombre}", filas[0])

    def test_el_modulo_de_cada_fila_mide_149(self):
        from shmir_design.presentation import block_rows

        _, seleccion = piezas()
        for fila in block_rows(seleccion, SGEP_SCAFFOLD):
            self.assertEqual(len(fila["modulo_149"]), 149)

    def test_todo_el_contenido_es_texto_no_vacio(self):
        tiling, seleccion = piezas()
        bundle = output_bundle(
            species="sonda", tiling=tiling, selection=seleccion, scaffold=SGEP_SCAFFOLD
        )
        for nombre, contenido in bundle.items():
            with self.subTest(nombre):
                self.assertIsInstance(contenido, str)
                self.assertTrue(contenido.strip())


if __name__ == "__main__":
    unittest.main()


class TestColumnasNuevasEnLaTabla(unittest.TestCase):
    """La UI no puede comprimir los campos nuevos en un solo estado (bloques 3, 1b, 4)."""

    def test_los_cinco_campos_de_polyA_van_por_separado(self):
        _, seleccion = piezas()
        fila = candidate_rows(seleccion)[0]
        for campo in POLYA_COLUMNS:
            self.assertIn(campo, fila)

    def test_la_carga_de_seed_y_la_accesibilidad_tienen_columna(self):
        _, seleccion = piezas()
        fila = candidate_rows(seleccion)[0]
        self.assertIn("carga_seed", fila)
        self.assertIn("accesibilidad", fila)

    def test_sin_calcular_van_vacias_y_no_a_cero(self):
        _, seleccion = piezas()
        fila = candidate_rows(seleccion)[0]
        self.assertEqual(fila["carga_seed"], "")
        self.assertEqual(fila["accesibilidad"], "")

    def test_el_riesgo_APA_dice_si_es_prediccion(self):
        _, seleccion = piezas()
        self.assertIn("prediccion", str(candidate_rows(seleccion)[0]["riesgo_APA"]))


class TestAmbarGraduado(unittest.TestCase):
    """El ambar sin grados deja de informar cuando siempre esta ambar.

    Con nueve filtros que dependen de un fichero, "faltan 2 de 9" y "faltan 8 de 9" son
    situaciones muy distintas y antes se veian igual. Ahora el titular lleva la cuenta.
    """

    def test_el_titular_dice_cuantos_faltan_de_cuantos(self):
        _, seleccion = piezas()
        luz = status_light(seleccion)
        self.assertEqual(luz.color, "ambar")
        self.assertIn(f"{len(luz.pending)} de {luz.total}", luz.headline)

    def test_el_total_es_el_numero_de_filtros_de_un_candidato(self):
        tiling, seleccion = piezas()
        self.assertEqual(status_light(seleccion).total, len(tiling.windows[0].filters))

    def test_cuantos_corrieron_es_el_complemento(self):
        _, seleccion = piezas()
        luz = status_light(seleccion)
        self.assertEqual(luz.ran, luz.total - len(luz.pending))

    def test_menos_pendientes_da_un_titular_distinto(self):
        """Regresion del problema: dos situaciones distintas no pueden leerse igual."""
        _, pocos = piezas(seeds=BOOTSTRAP_SEEDS, specificity=True)
        _, muchos = piezas()
        self.assertNotEqual(
            status_light(pocos).headline, status_light(muchos).headline
        )
        self.assertLess(
            len(status_light(pocos).pending), len(status_light(muchos).pending)
        )

    def test_el_verde_sigue_diciendo_que_corrieron_todos(self):
        mask = RepeatMask(intervals=((1, 5),), source="prueba")
        _, seleccion = piezas(
            seeds=BOOTSTRAP_SEEDS, mask=mask, specificity=True,
            transgene=True, mirna=True,
        )
        luz = status_light(seleccion)
        self.assertEqual(luz.color, "verde")
        self.assertEqual(luz.pending, ())
        self.assertEqual(luz.ran, luz.total)

    def test_sin_candidatos_no_finge_una_cuenta(self):
        tiling = tile_utr("N" * 200)
        seleccion = select_from_report(tiling, SelectionConfig(n_candidates=3))
        luz = status_light(seleccion)
        self.assertEqual(luz.total, 0)
        self.assertEqual(luz.ran, 0)


class TestUnaSolaEspecie(unittest.TestCase):
    """La interfaz exigia DOS FASTA para arrancar; el CLI corre con uno.

    La corrida murina es de una especie. Que la pagina bloquee el caso mas comun no es
    un detalle de presentacion, asi que la decision —¿hay bloques conservados que
    calcular?— vive aqui, con test, y no en la pagina.
    """

    def test_con_dos_secuencias_hay_informe_de_conservacion(self):
        from shmir_design.presentation import conservation_for

        bloque = "TTTTCTATATTTGTAACTTTGCATGT"
        informe = conservation_for(
            {
                "modelo": "GCGTCAGTACGATCGAATTACT" * 10 + bloque,
                "diana": "ACGTCAGTACGATCGAATTAGT" * 8 + bloque,
            }
        )
        self.assertIsNotNone(informe)
        self.assertTrue(informe.blocks)

    def test_con_una_sola_no_hay_nada_que_comparar(self):
        from shmir_design.presentation import conservation_for

        self.assertIsNone(conservation_for({"raton": "GCGTCAGTACGATCGAATTACT" * 10}))

    def test_con_ninguna_tampoco_revienta(self):
        from shmir_design.presentation import conservation_for

        self.assertIsNone(conservation_for({}))

    def test_con_mas_de_dos_aborta_en_vez_de_elegir_dos(self):
        from shmir_design.errors import ShmirDesignError
        from shmir_design.presentation import conservation_for

        with self.assertRaises(ShmirDesignError):
            conservation_for({"a": "ACGT" * 10, "b": "ACGT" * 10, "c": "ACGT" * 10})

    def test_el_paquete_de_salidas_funciona_sin_conservacion(self):
        tiling, seleccion = piezas()
        bundle = output_bundle(
            species="sonda", tiling=tiling, selection=seleccion,
            scaffold=SGEP_SCAFFOLD, conservation=None,
        )
        texto = bundle["sonda_informe.txt"]
        self.assertIn("No se comparo con otra especie", texto)


class TestFilasDeAnatomiaResuelta(unittest.TestCase):
    """Con una anatomia resuelta, la tabla enseña los tres tramos y su procedencia.

    Antes, sin transcrito verificado, solo se podia enseñar una fila «3'UTR 1..n,
    declarado por ti». Ahora la interfaz resuelve la anatomia igual que el CLI —por
    GenBank o por coordenadas— asi que hay 5'UTR y CDS que enseñar, y de donde salieron.
    """

    def _anatomia(self):
        return Anatomy.from_cds(
            cds=(45, 146), length=586, source=RegionSource.ANOTACION_GENBANK
        )

    def test_salen_los_tres_tramos(self):
        filas = anatomy_rows(None, anatomy=self._anatomia())
        self.assertEqual([f["tramo"] for f in filas], ["5'UTR", "CDS", "3'UTR"])

    def test_las_coordenadas_son_las_de_la_anatomia(self):
        filas = {f["tramo"]: (f["inicio"], f["fin"]) for f in anatomy_rows(None, anatomy=self._anatomia())}
        self.assertEqual(filas["CDS"], (45, 146))
        self.assertEqual(filas["3'UTR"], (147, 586))

    def test_cada_fila_dice_de_donde_salio(self):
        for fila in anatomy_rows(None, anatomy=self._anatomia()):
            with self.subTest(fila["tramo"]):
                self.assertIn("GenBank", fila["origen"])

    def test_un_3utr_declarado_entero_sale_como_tal(self):
        anatomia = Anatomy.whole_is_utr3(
            440, source=RegionSource.TODO_3UTR_DECLARADO
        )
        filas = anatomy_rows(None, anatomy=anatomia)
        self.assertEqual([f["tramo"] for f in filas], ["3'UTR"])
        self.assertIn("3'UTR", filas[0]["origen"])

    def test_el_transcrito_verificado_sigue_mandando(self):
        # Si hay referencia verificada, es la que se enseña: no se sustituye por una
        # anatomia declarada.
        referencia = REFERENCES["NM_011170.3"]
        filas = anatomy_rows(referencia, anatomy=self._anatomia())
        self.assertEqual([f["origen"] for f in filas], ["verificado"] * 3)
